"""As guardas de rota.

Esconder um item do menu **não** é controle de acesso: quem digitar o
endereço na barra do navegador tem que bater numa porta trancada. Estas duas
guardas são essa porta, e o teste de varredura em `tests/test_guarda.py` é o
que impede alguém de criar uma tela e esquecer de pô-la.
"""

from __future__ import annotations

from enum import Enum
from functools import wraps

from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.urls import reverse

from nucleo.permissoes import pode

from comum.sessao import usuario_da_sessao

__all__ = [
    "Barreira", "LIBERADAS_COM_SENHA_EXPIRADA", "TELAS_ABERTAS", "barreira",
    "exigir_login", "exigir_permissao", "resposta_web",
]

#: As rotas que podem viver sem guarda, e o motivo de cada uma. Uma lista
#: curta e explícita: qualquer nome que entre aqui devia doer um pouco.
TELAS_ABERTAS = frozenset({
    "entrar",  # a porta
    "tema",    # a folha que a própria tela de login precisa carregar
    # `sair` precisa funcionar mesmo com sessão inválida ou órfã (conta
    # apagada ou desativada depois do login: `usuario_da_sessao` não
    # reconstrói ninguém nesse caso). Atrás de `exigir_login`, essa sessão
    # quebrada nunca seria flushada — a pessoa ficaria sem conseguir sair de
    # verdade. `sair_da_sessao` já é segura de chamar sem sessão nenhuma.
    "sair",
    # O logo da tela de entrada e o favicon do `<head>` precisam existir
    # ANTES de qualquer sessão — é a mesma razão de `/tema.css`. A defesa
    # não é guarda de login: é a peneira na gravação (`ImagemDaMarca.save`
    # só aceita o que `nucleo.images.validar` aprova) e os cabeçalhos
    # seguros na resposta (`plataforma/views_marca`).
    "marca_imagem",
    # O RG da versão: o painel das instalações lê antes de qualquer
    # sessão — um commit curto não revela nada (spec do painel).
    "versao",
})


#: As rotas que continuam abertas para quem tem a senha vencida — trocar a
#: própria senha (e a foto, que mora na mesma tela) e sair. Nada mais: a
#: pessoa entra no dia da senha vencida e a primeira tela é a troca.
LIBERADAS_COM_SENHA_EXPIRADA = frozenset({
    "perfil", "perfil_senha", "perfil_foto", "sair",
    # A operação `GET /api/v1/eu`: o app precisa saber quem é para desenhar a
    # tela de troca. A troca pela API chega quando um SaaS precisar dela.
    "eu",
})


class Barreira(Enum):
    """O que impede esta requisição de passar. O valor é o `codigo` que a API
    devolve — estável, porque é por ele que o app decide o que fazer."""

    SEM_SESSAO = "sem_sessao"
    SENHA_EXPIRADA = "senha_expirada"
    NAO_EXISTE = "nao_existe"
    SEM_FILIAL = "sem_filial"


def _nome_da_rota(request) -> "str | None":
    return getattr(getattr(request, "resolver_match", None), "url_name", None)


def _presa_pela_senha(request, nome_da_rota: "str | None") -> bool:
    """A sessão tem senha vencida E esta rota não é uma das liberadas?

    Durante personificação, nunca: quem está vendo é o alvo, e "trocar a
    senha" nesta tela trocaria a DELE — sequestrar a sessão da MW5 para
    isso seria um jeito acidental de resetar senha alheia.
    """
    if not request.session.get("senha_expirada"):
        return False
    if "usuario_personificado_id" in request.session:
        return False
    return nome_da_rota not in LIBERADAS_COM_SENHA_EXPIRADA


def barreira(request, *, exige_sessao: bool = True, permissao: "str | None" = None,
             modulo: "str | None" = None, exige_filial: bool = False,
             nome_da_rota: "str | None" = None) -> "Barreira | None":
    """O que impede a requisição de passar, ou `None`.

    **A decisão de acesso mora só aqui.** As guardas da web
    (`exigir_login`, `exigir_permissao`, `exigir_modulo_ligado`,
    `exigir_filial`) e as da API (`comum.guardas_da_api`) chamam esta função
    e só traduzem a resposta. Uma regra nova de acesso entra aqui e vale nos
    dois lados; escrita dentro de uma guarda, valeria num e faltaria no outro.

    A ordem é a das guardas de sempre: sessão, senha, permissão, módulo,
    filial. `exige_sessao=False` é para as guardas de módulo e de filial, que
    nunca decidem sobre login sozinhas — são compostas por dentro de uma
    guarda de login.

    `nome_da_rota`: a guarda da API informa o nome da função da operação. O
    `resolver_match.url_name` não serve lá — no Ninja, duas operações no mesmo
    caminho dividem o padrão de URL, e o nome resolvido seria o da primeira.
    """
    if exige_sessao or permissao is not None:
        user = usuario_da_sessao(request)
        if user is None:
            return Barreira.SEM_SESSAO
        nome = nome_da_rota if nome_da_rota is not None else _nome_da_rota(request)
        if _presa_pela_senha(request, nome):
            return Barreira.SENHA_EXPIRADA
        if permissao is not None and not pode(user, permissao):
            return Barreira.NAO_EXISTE
    if modulo is not None:
        from comum.guardas_de_modulo import modulo_ligado

        if not modulo_ligado(modulo):
            return Barreira.NAO_EXISTE
    if exige_filial:
        from plataforma.contexto import filial_atual

        if filial_atual(request) is None:
            return Barreira.SEM_FILIAL
    return None


def resposta_web(obstaculo: Barreira) -> HttpResponse:
    """A tradução da web. `SEM_FILIAL` não passa por aqui: a tela de aviso é
    de `exigir_filial`, que sabe desenhar."""
    if obstaculo is Barreira.SEM_SESSAO:
        return HttpResponseRedirect(reverse("entrar"))
    if obstaculo is Barreira.SENHA_EXPIRADA:
        return HttpResponseRedirect(reverse("perfil") + "?expirada=1")
    return HttpResponseNotFound()


def exigir_login(view):
    """Sem sessão, vai para a tela de entrada. Com a senha vencida, vai para
    a troca dela — e não sai de lá até trocar. A decisão é de `barreira`."""

    @wraps(view)
    def guardada(request, *args, **kwargs):
        obstaculo = barreira(request)
        if obstaculo is not None:
            return resposta_web(obstaculo)
        request.usuario = usuario_da_sessao(request)
        return view(request, *args, **kwargs)

    guardada.exige_login = True
    return guardada


def exigir_permissao(nome: str):
    """Sem a permissão, a rota responde como se não existisse.

    404 e não 403, de propósito: quem não pode não precisa descobrir que a
    tela existe. A resposta é montada à mão (`HttpResponseNotFound`), e não
    por `raise Http404`: levantar a exceção deixaria a conversão em resposta
    a cargo do handler do Django, que em `DEBUG=True` mostra uma página
    técnica listando os padrões de URL tentados — exatamente a pista que
    esta guarda existe para não dar.
    """

    def decorar(view):
        @wraps(view)
        def guardada(request, *args, **kwargs):
            obstaculo = barreira(request, permissao=nome)
            if obstaculo is not None:
                return resposta_web(obstaculo)
            request.usuario = usuario_da_sessao(request)
            return view(request, *args, **kwargs)

        guardada.exige_login = True
        guardada.permissao = nome
        return guardada

    return decorar
