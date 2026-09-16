"""Em que filial esta requisição está trabalhando.

A sessão guarda **só o id**, do mesmo jeito que `comum.sessao` guarda o de
quem entrou: `filial_atual` reconstrói a filial a cada requisição, nunca
confia no que ficou gravado. É o que faz **tirar o acesso de alguém a uma
filial valer na hora**, e não no próximo login — a mesma propriedade que
`BackendDjango.buscar` já dá para o usuário.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from comum.memoria import lembrar
# `identidade_da_sessao`, e nunca `usuario_da_sessao`, em todo este arquivo:
# a segunda põe as permissões do cargo, e para isso pergunta a empresa e a
# filial a este módulo. Ler a segunda aqui fecharia o círculo.
from comum.sessao import identidade_da_sessao

from .models import Empresa, Filial
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from nucleo.permissoes import NivelDeContexto, User

__all__ = [
    "CHAVE", "CHAVE_EMPRESA", "empresa_atual", "empresa_permitida",
    "empresas_de", "escolher", "escolher_empresa", "filial_permitida",
    "filial_permitida_por_guid",
    "filiais_de", "filial_atual", "niveis_de_contexto",
]

#: A mesma chave que o `name` do seletor de filial usa no HTML — ver
#: `plataforma.site.montar_site`. Uma constante só, para o nome do campo do
#: POST e a chave da sessão nunca divergirem em silêncio.
CHAVE = "filial_id"

#: A chave do contexto que VALE neste produto: a empresa.
#:
#: Aqui a empresa é um cadastro de várias (os clientes do portal) e a filial
#: está desligada — ver o roadmap. No KRONOS.net é o contrário: a empresa é
#: uma linha só, dado da instalação, e a filial é o que se escolhe. As duas
#: constantes convivem porque o código de filial fica de pé para o dia em
#: que ela for ligada; quem manda no cabeçalho hoje é esta.
CHAVE_EMPRESA = "empresa_id"


def empresas_de(user: "User | None") -> "QuerySet[Empresa]":
    """As empresas que `user` alcança, na ordem do seletor.

    Import tardio de `contas.alcance`: `contas` é a camada de FORA, e
    `contas.alcance` importa `plataforma.models` — o import no topo daqui
    inverteria a direção e fecharia o ciclo. É a mesma forma que o resto do
    projeto usa (ver `plataforma/apps.py`).
    """
    from contas.alcance import empresas_alcancadas

    if user is None:
        return Empresa.objects.none()
    return empresas_alcancadas(user)


def empresa_atual(request) -> "Empresa | None":
    """A empresa desta sessão.

    **Para quem é de uma conta, a sessão não é consultada.** A empresa vem da
    CONTA e das alocações (`contas.lugar.empresas_da_pessoa`), e essa é a mudança de 09/09/2026:
    antes a fronteira entre dois clientes passava por uma variável de sessão
    — a tela perguntava "em qual empresa você está?" e o inquilino lia a
    resposta. Sessão remendada e id forjado deixam de ser caminhos quando o
    valor não vem do pedido.

    A sessão sobrevive para a MW5, e só: ela é a única que alcança mais de
    uma, e para ela a pergunta é outra — "qual CONTA estou olhando".

    Mesma regra da filial para o id guardado: um id de uma empresa que a
    pessoa **deixou** de alcançar é descartado aqui, e é o que faz tirar o
    acesso de alguém valer NA HORA, e não no próximo login.
    """
    return lembrar(request, "contexto:empresa", lambda: _decidir(request))


def _decidir(request) -> "Empresa | None":
    """O corpo de `empresa_atual`, separado só para o memo poder envolvê-lo.

    Vale uma vez por requisição (ver `comum.memoria`): `do_contexto` chama
    `empresa_atual` uma vez por CONSULTA — a vitrine sozinha chama seis —, e
    cada chamada relia a pessoa, o alcance dela e a empresa. A resposta é a
    mesma nas seis: quem está olhando não muda no meio da renderização.
    """
    pessoa = identidade_da_sessao(request)
    permitidas = empresas_de(pessoa)

    # Quem alcança UMA empresa não passa pela sessão. Ler a sessão aqui daria
    # ao id forjado a chance de não casar com nada e cair no `first()` — o
    # mesmo resultado, por um caminho que alguém teria de reauditar a cada
    # mudança.
    if permitidas.count() == 1:
        return permitidas.first()

    id_na_sessao = request.session.get(CHAVE_EMPRESA)
    if id_na_sessao is not None:
        try:
            id_na_sessao = int(id_na_sessao)
        except (TypeError, ValueError):
            id_na_sessao = None
        else:
            escolhida = permitidas.filter(pk=id_na_sessao).first()
            if escolhida is not None:
                return escolhida

    return permitidas.first()


def empresa_permitida(request, empresa_id) -> "Empresa | None":
    """A empresa `empresa_id`, se a pessoa desta sessão a alcança — ou
    `None`, tanto para um id de empresa que ela não alcança quanto para um
    valor que nem chega a ser id. O campo vem de fora e não é confiável."""
    try:
        empresa_id = int(empresa_id)
    except (TypeError, ValueError):
        return None

    return empresas_de(identidade_da_sessao(request)).filter(pk=empresa_id).first()


def escolher_empresa(request, empresa_id) -> "Empresa | None":
    """Grava `empresa_id` na sessão, se a pessoa alcança essa empresa.
    Devolve a escolhida, ou `None` sem gravar nada."""
    escolhida = empresa_permitida(request, empresa_id)
    if escolhida is None:
        return None

    request.session[CHAVE_EMPRESA] = escolhida.pk
    # Trocar de empresa leva a filial para a primeira permitida dentro dela:
    # a filial guardada era da empresa anterior.
    request.session.pop(CHAVE, None)
    return escolhida


def filiais_de(user: "User | None", empresa: "Empresa | None" = None) -> "QuerySet[Filial]":
    """As filiais ativas que `user` alcança DENTRO de `empresa`, na ordem do
    seletor (`Filial.Meta.ordering`).

    Até 14/09/2026 lia `Filial.usuarios`, que não sabia de empresa: podia
    devolver filial de outra empresa, e por isso o carrinho gravava a Matriz.
    Agora a filial é sempre uma filial da empresa em que se está, alcançada
    pelas alocações da pessoa (`contas.lugar.filiais_da_pessoa`).

    Import tardio pelo mesmo motivo de `empresas_de`.
    """
    from contas.identidade import usuario_de
    from contas.lugar import filiais_da_pessoa

    if user is None:
        return Filial.objects.none()
    return filiais_da_pessoa(usuario_de(user), empresa)


def filial_atual(request) -> "Filial | None":
    """A filial escolhida nesta sessão, dentro da empresa atual — ou a primeira
    que a pessoa alcança nela, ou `None` quando não alcança nenhuma.

    Um id gravado na sessão para uma filial que a pessoa **deixou** de alcançar
    (perdeu a alocação, a filial foi desativada, ou é de outra empresa) é
    descartado aqui: nunca gera 500 e nunca devolve dado de uma filial fora do
    alcance. A sessão não é reescrita; a leitura é recalculada a cada
    requisição, e memorizada dentro dela (`comum.memoria`).
    """
    return lembrar(request, "contexto:filial", lambda: _decidir_filial(request))


def _decidir_filial(request) -> "Filial | None":
    permitidas = filiais_de(identidade_da_sessao(request), empresa_atual(request))

    id_na_sessao = request.session.get(CHAVE)
    if id_na_sessao is not None:
        try:
            id_na_sessao = int(id_na_sessao)
        except (TypeError, ValueError):
            id_na_sessao = None
        else:
            escolhida = permitidas.filter(pk=id_na_sessao).first()
            if escolhida is not None:
                return escolhida

    # Sem escolha, começa na Matriz — e não na primeira da ordem do seletor, que
    # desempata pelo nome: "Filial 1" passa na frente de "Matriz" no alfabeto, e
    # entrar caía numa filial qualquer. Quem não alcança a Matriz fica com a
    # primeira que alcança. O seletor continua na ordem de sempre.
    return permitidas.filter(e_matriz=True).first() or permitidas.first()


def filial_permitida(request, filial_id) -> "Filial | None":
    """A filial `filial_id`, se a pessoa desta sessão pode usá-la — ou
    `None`, tanto para um id que não é o de nenhuma filial alcançável
    quanto para um valor que nem chega a ser um id (o campo vem de fora, e
    não é confiável). Não grava nada na sessão: é só a validação, usada por
    `escolher` (que grava) e pela tela de confirmação de
    `plataforma.views_filial.filial_trocar` no GET — que precisa validar
    ANTES de nomear a filial na pergunta, para nunca nomear uma que a
    pessoa não alcança.
    """
    try:
        filial_id = int(filial_id)
    except (TypeError, ValueError):
        return None

    return filiais_de(identidade_da_sessao(request), empresa_atual(request)).filter(pk=filial_id).first()


def filial_permitida_por_guid(request, guid) -> "Filial | None":
    """`filial_permitida`, pelo GUID — o identificador que a API expõe.

    Texto que não é UUID vira `None`, e não 500: `filter(guid="lixo")` levanta
    `ValidationError` no Django, e o 404 de um GUID malformado precisa ser
    idêntico ao de um GUID de outra conta.
    """
    try:
        guid = uuid.UUID(str(guid))
    except (TypeError, ValueError, AttributeError):
        return None
    return filiais_de(identidade_da_sessao(request), empresa_atual(request)).filter(guid=guid).first()


def escolher(request, filial_id) -> "Filial | None":
    """Grava `filial_id` na sessão, se a pessoa pode usar essa filial.
    Devolve a filial escolhida, ou `None` sem gravar nada.
    """
    escolhida = filial_permitida(request, filial_id)
    if escolhida is None:
        return None

    request.session[CHAVE] = escolhida.pk
    return escolhida


def niveis_de_contexto(request) -> "list[NivelDeContexto]":
    """O contexto do cabeçalho: **a empresa e a filial, cada uma só quando há o
    que escolher**.

    A empresa aparece para quem alcança mais de uma — hoje, só a MW5, e para ela
    a pergunta é "qual CONTA estou olhando". A filial aparece para quem alcança
    mais de uma DENTRO da empresa atual (14/09/2026): desde a virada dos cargos,
    o que a pessoa pode depende da filial em que está, e o cabeçalho é onde ela
    escolhe.

    `rotulo` é só o nome genérico, o mesmo padrão de
    `HeaderBrand.context_labels` — este módulo não conhece `Brand` de
    propósito. Quem troca pelo rótulo que o cliente escolheu é
    `plataforma.site.construir_context_switcher`.
    """
    from nucleo.permissoes import NivelDeContexto, OpcaoDeContexto

    user = identidade_da_sessao(request)
    atual = empresa_atual(request)
    niveis = []

    # **Sem seletor quando não há o que selecionar**, nível a nível. Um
    # seletor de uma opção é um botão que não faz nada, ocupando o lugar em
    # que a pessoa procura o que faz. O nome da empresa continua aparecendo,
    # porque quem o mostra é a marca, não este seletor.
    empresas = list(empresas_de(user))
    if len(empresas) > 1:
        niveis.append(NivelDeContexto(
            nivel=0,
            # Para a MW5 a pergunta não é "em que empresa estou trabalhando"
            # — ela não trabalha dentro de nenhuma —, é "qual cliente estou
            # olhando". O rótulo diz isso.
            rotulo=_("Conta"),
            atual=str(atual.pk) if atual else "",
            opcoes=[OpcaoDeContexto(str(e.pk), str(e)) for e in empresas],
        ))

    filiais = list(filiais_de(user, atual)) if atual is not None else []
    if len(filiais) > 1:
        filial = filial_atual(request)
        niveis.append(NivelDeContexto(
            nivel=1,
            rotulo=_("Filial"),
            atual=str(filial.pk) if filial else "",
            opcoes=[OpcaoDeContexto(str(f.pk), str(f)) for f in filiais],
        ))

    return niveis
