"""Qual idioma esta requisição fala, e de onde essa resposta vem.

**Só a MOLDURA.** Menu, botões, rótulos e mensagens do sistema existem em
português e em castelhano; o catálogo, não. Nome de peça, família e aplicação
são dado que o cliente digitou e moram em linha de tabela — nenhum arquivo de
tradução alcança linha de tabela. Um paraguaio vê a moldura em castelhano e a
peça em português até alguém traduzir o conteúdo, e isso é o combinado, não
defeito.

**Por que um middleware da casa e não o `LocaleMiddleware` do Django.** O de
lá decide por prefixo de URL, cookie e cabeçalho do navegador. Aqui a resposta
é outra e mais simples: o idioma é uma coluna da PESSOA. Quem entrou tem
preferência gravada, que sobrevive ao logout — e à sessão, que é derrubada
inteira ao trocar de senha ou encerrar uma personificação. O navegador não
opina: um vendedor brasileiro atendendo de um computador configurado em
espanhol continua vendo o sistema em português.

Antes de entrar, ninguém tem coluna — aí sim vale a escolha guardada na
sessão pela tela de idioma, e o padrão da instalação quando nem isso existe.
"""

from __future__ import annotations

from django.conf import settings
from django.utils import translation

__all__ = ["CHAVE_IDIOMA", "MiddlewareDeIdioma", "idioma_da_requisicao"]

#: Onde a escolha de quem ainda não entrou fica guardada. Some no login: a
#: partir dali quem manda é a coluna da pessoa.
CHAVE_IDIOMA = "idioma"


def _existe(codigo: str) -> bool:
    return any(codigo == chave for chave, _ in settings.LANGUAGES)


def _e_da_api(request) -> bool:
    from .sessao_por_cabecalho import e_da_api

    return e_da_api(getattr(request, "path", ""))


def _do_aparelho(request) -> str:
    """O idioma do aparelho, para a API ANTES de haver pessoa.

    **Só na API.** Na web o navegador não opina (docstring do módulo): quem
    ainda não entrou escolhe na tela de entrada, e a escolha fica na sessão.
    O app não tem essa tela antes do login, e o celular de um paraguaio já diz
    `es-PY`. Depois do login, a coluna da pessoa vence o aparelho, como na web.
    """
    from django.utils.translation import get_supported_language_variant
    from django.utils.translation.trans_real import parse_accept_lang_header

    bruto = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    for codigo, peso in parse_accept_lang_header(bruto):
        if codigo == "*":
            continue
        try:
            return get_supported_language_variant(codigo)
        except LookupError:
            continue
    return ""


def idioma_da_requisicao(request) -> str:
    """O idioma desta requisição: a escolha desta sessão, senão a coluna de
    quem entrou, senão — só na API, antes de haver pessoa — o do aparelho
    (`_do_aparelho`), senão o padrão da instalação.

    **A sessão na frente da coluna, e não o contrário.** "Escolhi agora, vale
    agora" é o que a pessoa espera ao clicar — e é o que faz a escolha feita
    na tela de ENTRADA continuar valendo depois do login, quando a coluna
    ainda diz o padrão. Trocar em Meu Perfil grava os dois, então elas não
    ficam discordando por muito tempo.

    Código que não é um dos declarados em `LANGUAGES` é ignorado — ele pode
    ter vindo de uma sessão antiga ou de um `?idioma=` digitado na barra, e
    `translation.activate("xx")` não falha: ele ativa um catálogo vazio e a
    tela sai com metade das frases em branco.
    """
    sessao = getattr(request, "session", None)
    escolhido = sessao.get(CHAVE_IDIOMA, "") if sessao is not None else ""

    if not escolhido:
        escolhido = getattr(_pessoa_da_vez(request), "idioma", "") or ""

    if not escolhido and _e_da_api(request):
        escolhido = _do_aparelho(request)

    return escolhido if _existe(escolhido) else settings.LANGUAGE_CODE


def _pessoa_da_vez(request):
    """A linha do banco de quem está olhando, ou `None`.

    **`request.user` não serve**: esta casa não usa o login do
    `django.contrib.auth` — a sessão guarda o id e o backend reconstrói a
    pessoa a cada requisição (`comum.sessao`). Para o middleware do Django,
    todo mundo aqui é anônimo.

    Import tardio, e pelo mesmo motivo de `comum.auditoria._modelo`: `comum`
    é a camada de baixo e `contas` é a de cima; importar no topo daqui
    fecharia o ciclo que a separação das duas existiu para quebrar.

    Não custa consulta a mais: `usuario_da_sessao` é memorizada por
    requisição (`comum.memoria`) e `usuario_de` guarda a linha no próprio
    retrato — a leitura que este middleware faz é a mesma que a primeira
    guarda faria alguns milissegundos depois.
    """
    from contas.identidade import usuario_de

    from .sessao import usuario_da_sessao

    try:
        return usuario_de(usuario_da_sessao(request))
    except Exception:
        # Requisição sem sessão utilizável (uma varredura, um teste que
        # injeta `dict` cru) não pode derrubar a página inteira por causa do
        # IDIOMA. Sem pessoa, vale o padrão.
        return None


class MiddlewareDeIdioma:
    """Ativa o idioma da requisição e o desativa no fim.

    **O `finally` não é zelo**: a ativação do Django é por THREAD, e o
    servidor reaproveita threads entre requisições. Sem desativar, a
    requisição seguinte naquela thread herdaria o castelhano de quem passou
    antes — um defeito que não aparece em desenvolvimento (uma pessoa só) e
    aparece em produção como "a tela mudou de idioma sozinha".

    `Content-Language` na resposta porque a página realmente varia de idioma:
    é o que impede um cache compartilhado de servir a versão em castelhano a
    quem pediu português.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        idioma = idioma_da_requisicao(request)
        translation.activate(idioma)
        request.idioma = idioma
        try:
            resposta = self.get_response(request)
        finally:
            translation.deactivate()
        resposta.setdefault("Content-Language", idioma)
        return resposta
