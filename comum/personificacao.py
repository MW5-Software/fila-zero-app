"""Ver o sistema como outra pessoa, sem deixar de ser quem de fato entrou.

Existe para a MW5 reproduzir exatamente o que um cliente vê ao relatar um
problema — sem pedir a senha dele, e sem que a trilha de auditoria minta
sobre quem agiu. É a tarefa mais fácil de fazer errado com segurança desta
entrega: quem personifica alguém tem, por definição, as costas cobertas por
ser superusuário, e todo desenho aqui existe para que essa cobertura nunca
vire uma segunda conta de superusuário, nem um jeito de apagar o próprio
rastro.

O desenho inteiro se apoia em uma decisão só, tomada em `contas/sessao.py`:
`CHAVE` (o original) nunca é trocada por `CHAVE_ALVO` (quem se está vendo
como) — as duas convivem, e `usuario_da_sessao` decide qual delas a
requisição enxerga. Por isso encerrar é só apagar uma chave: o original
nunca foi substituído, então não existe nada para restaurar, e portanto nada
que um cookie adulterado possa forjar no lugar dele.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from nucleo.components import Alert, Button, Form, Raw
from nucleo.permissoes import User
from nucleo.rendering import Renderable

from .auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from .sessao import (
    CHAVE_ALVO, usuario_da_sessao, usuario_original_da_sessao,
)

__all__ = [
    "PersonificacaoRecusada", "alvo_personificavel", "aviso", "encerrar",
    "iniciar", "original_de", "personificando",
]


class PersonificacaoRecusada(Exception):
    """Por que `iniciar` recusou. A view que chama vira isto em 404 — mesmo
    raciocínio de `contas/guardas.py::exigir_permissao`: quem não pode não
    precisa descobrir se o alvo existia, se já personificava alguém, ou se
    o alvo era superusuário. As três recusas parecem exatamente a mesma
    coisa por fora, de propósito."""


def personificando(request) -> bool:
    """Se esta sessão está vendo o sistema como outra pessoa agora."""
    return bool(request.session.get(CHAVE_ALVO))


def original_de(request, backend=None) -> "User | None":
    """Quem de fato entrou nesta sessão — o original, personificando ou não.

    Não é `usuario_da_sessao`: aquela devolve o alvo quando há
    personificação em curso (é o que faz o menu e as permissões virarem as
    do alvo em toda tela). Esta lê só `CHAVE`, a chave que a personificação
    nunca toca — é por isso que "voltar a ser eu" devolve o original de
    verdade, e não uma cópia que um cookie adulterado pudesse inventar.
    """
    return usuario_original_da_sessao(request, backend)


def alvo_personificavel(alvo_id):
    """O usuário que pode ser personificado com este id, ou `None`.

    `is_superuser=False`: ninguém personifica um superusuário, nem outro
    superusuário — sem esta trava, personificar viraria escalada lateral
    para dentro da própria conta da MW5. `is_active=True`: personificar
    alguém que não consegue mais entrar sozinho não tem sentido nenhum, e
    reaproveita a mesma leitura que `contas.backend.BackendDjango.buscar` já
    faz para qualquer sessão.

    Mesmo molde de `contas.views_usuarios._alcancavel`: o alvo inalcançável
    "não existe" para quem chama, em vez de existir com uma mensagem
    diferente — a mesma recusa, não um caminho novo por motivo.
    """
    try:
        pk = int(alvo_id)
    except (TypeError, ValueError):
        return None
    return get_user_model().objects.filter(
        pk=pk, is_superuser=False, is_active=True).first()


def iniciar(request, alvo_id: str) -> None:
    """Passa a ver o sistema como `alvo_id`, mantendo o original na sessão.

    Recusa (levanta `PersonificacaoRecusada`, nunca em silêncio) quando:

    - quem chama não é superusuário — `usuario_da_sessao` aqui só pode
      devolver o alvo se JÁ houvesse uma personificação em curso, então este
      mesmo `if` cobre as duas recusas de uma vez: um admin do cliente
      tentando personificar, e alguém que já personifica tentando encadear
      uma segunda (o alvo de agora nunca é superusuário — ver
      `alvo_personificavel` — e portanto nunca passaria neste `if` de
      qualquer forma);
    - o alvo não existe, está inativo, ou é superusuário — `alvo_personificavel`.

    Esta checagem repete a que a rota (decorada com `exigir_permissao`) já
    faz — de propósito: `iniciar` é chamável direto (é a interface que os
    testes de recusa exercitam), e a tela mais sensível desta entrega não
    fica de pé em cima de uma guarda só. Mesmo raciocínio de
    `contas.views_usuarios._alcancavel`: toda ação pergunta de novo, sozinha.
    """
    ator = usuario_da_sessao(request)
    if ator is None or not ator.superuser:
        raise PersonificacaoRecusada("só a MW5 personifica, e nunca em cadeia.")

    alvo = alvo_personificavel(alvo_id)
    if alvo is None:
        raise PersonificacaoRecusada("usuário não encontrado.")

    request.session[CHAVE_ALVO] = str(alvo.pk)
    # `ator`, nunca `alvo`, como autor: é o original quem decidiu personificar,
    # e é isso que a trilha tem que dizer sobre ESTE registro em particular —
    # ao contrário de toda ação praticada DEPOIS, que `registrar(request=...)`
    # atribui ao alvo com a nota de quem personificava. Sem `request=` aqui:
    # anotar "personificado por" na própria linha que abre a personificação
    # seria repetir, com outras palavras, o que `alvo=` já diz.
    registrar(ACOES.PERSONIFICACAO_INICIADA, ator, alvo=alvo.email)



def encerrar(request) -> None:
    """Encerra a personificação em curso. Sem nenhuma em curso, não faz
    nada — chamar contra uma sessão que já não personifica ninguém é o
    estado de repouso, não um erro.

    A ordem importa: lê original e alvo ANTES de apagar `CHAVE_ALVO`, porque
    depois de apagada não sobra mais quem descrever no registro.
    """
    if not personificando(request):
        return
    original = original_de(request)
    alvo = usuario_da_sessao(request)  # ainda o alvo — a chave não foi apagada
    del request.session[CHAVE_ALVO]
    registrar(
        ACOES.PERSONIFICACAO_ENCERRADA, original, alvo=alvo.login if alvo else "",
    )


def aviso(request) -> Renderable:
    """O aviso fixo de que a sessão está personificando, com o botão para
    voltar a ser quem de fato entrou.

    Pensado para entrar na FRENTE do `content=` de qualquer `Site.page(...)`
    já existente: devolve `""` fora de personificação, e `Site.page` engole
    string vazia como filho sem desenhar nada — quem chama não precisa de um
    `if` próprio. Quem esquece que está personificando é exatamente quem
    corre o risco de fazer, sem querer, alguma ação em nome de outra pessoa;
    este aviso é a defesa contra esse esquecimento, não contra alguém mal-
    intencionado (esse já está barrado pelas guardas de rota).
    """
    if not personificando(request):
        return ""
    original = original_de(request)
    alvo = usuario_da_sessao(request)
    nome_original = original.name if original else "?"
    nome_alvo = alvo.name if alvo else "?"
    return Alert(
        tone="warn",
        title=_("Você está vendo como outra pessoa"),
        attrs={"data-personificacao": "aviso"},
        message=[
            f"{nome_original} está vendo o sistema como {nome_alvo}. Toda "
            f"ação feita agora entra na trilha de auditoria em nome de "
            f"{nome_alvo}.",
            Form(action=reverse("voltar_a_ser_eu"), children=[
                Raw(html=campo_csrf(request)),
                Button(label=_("Voltar a ser eu"), variant="ghost", type="submit"),
            ]),
        ],
    )
