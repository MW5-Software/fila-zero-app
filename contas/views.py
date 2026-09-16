"""As duas telas de porta: entrar e sair."""

from __future__ import annotations

from django.http import (
    HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound, HttpResponseRedirect,
)
from dataclasses import replace

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from nucleo.components import Raw
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render

from comum.estaticos import versionado
from plataforma.marca import FOLHA_DA_CASA

from .views_idioma import guardar_escolha
from comum.confirmacao import tela_de_confirmacao
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_login, exigir_permissao
from comum.personificacao import PersonificacaoRecusada, encerrar, iniciar

from .entrada import (CREDENCIAIS_INVALIDAS, autenticar_e_entrar,
                      destino_depois_de_entrar_para, sair_e_registrar)

__all__ = ["entrar", "personificar", "sair", "voltar_a_ser_eu"]


def _desenhar(request, marca, erro: "str | None" = None) -> HttpResponse:
    from plataforma.entrada import traduzir_a_entrada
    from plataforma.header import EntradaDaCasa
    from plataforma.idioma_no_cabecalho import seletor_da_entrada

    env = ambiente()
    with use_environment(env):
        pagina = EntradaDaCasa(
            # **A marca passa pelo tradutor.** Tudo que se lê nesta tela é
            # texto do `LoginBrand`, que o cliente edita — então trocar de
            # idioma mudava o idioma e a tela continuava igual. Ver
            # `plataforma/entrada.py`: traduz o que ainda é nosso, deixa
            # intacto o que o cliente escreveu.
            brand=replace(marca, login=traduzir_a_entrada(marca.login)),
            idiomas=seletor_da_entrada(request),
            action=reverse("entrar"),
            error=erro,
            theme_href="/tema.css",
            # A entrada fica fora do shell e por isso fora do `montar_site`:
            # a folha da casa precisa ser pedida aqui também, ou a correção
            # do design system vale em toda tela menos na primeira.
            #
            # **`versionado` pelo mesmo motivo, e ele faltava aqui.** Toda
            # outra tela pede a folha com a versão no endereço
            # (`SiteDoProduto.page`); esta pedia sem. O efeito só aparece para
            # quem JÁ visitou o sistema: o navegador tem a folha antiga em
            # cache, e uma correção de CSS nunca chega na primeira tela —
            # exatamente o que aconteceu com o seletor de idioma em
            # 10/09/2026, que saiu sem estilo nenhum e com a bandeira do
            # tamanho do cartão.
            stylesheets=[versionado(FOLHA_DA_CASA)],
        )
        # `campos_da_marca()` já rodou no `__post_init__` da LoginPage; o
        # token entra na frente dos campos visíveis, e não no lugar deles.
        pagina.fields = [Raw(html=campo_csrf(request)), *pagina.fields]
        # Senha errada redesenha o formulário com 200, e não 401: 401
        # dispararia a caixa de autenticação nativa do navegador — uma tela
        # que ninguém controla e da qual não se sai bem.
        return render(pagina)


def entrar(request) -> HttpResponse:
    from plataforma.marca import marca_da_instalacao

    marca = marca_da_instalacao()
    if request.method != "POST":
        # `?idioma=es` por LINK, e só aqui. Antes do login não há conta, não
        # há coluna e não há o que um pedido forjado consiga: a escolha vale
        # para a sessão anônima e some com ela. Exigir POST antes da entrada
        # custaria uma tela a mais justamente para quem abriu o sistema pela
        # primeira vez e não entende o que está escrito.
        pedido = request.GET.get("idioma", "")
        if pedido:
            guardar_escolha(request, pedido)
            return HttpResponseRedirect(reverse("entrar"))
        return _desenhar(request, marca)

    # A chave lida aqui precisa bater com o `name` que o campo realmente
    # ganha no HTML. `LoginPage.campos_da_marca()` (nucleo/layout.py) emite
    # o identificador como `name="usuario"` — não `"login"` — então é essa a
    # chave que o formulário de verdade envia.
    login_digitado = request.POST.get("usuario", "")
    user = autenticar_e_entrar(request, login_digitado, request.POST.get("senha", ""))
    if user is None:
        return _desenhar(request, marca, erro=CREDENCIAIS_INVALIDAS)
    return HttpResponseRedirect(destino_depois_de_entrar_para(request))


def sair(request) -> HttpResponse:
    """A ação só roda por POST: um `<img src="/sair">` numa página qualquer
    não pode derrubar a sessão de quem a abriu. GET não vira 405 sozinho —
    devolve uma tela perguntando "tem certeza?", com um `<form
    method="post">` de verdade dentro: é assim que "Sair" continua
    funcionando pelo link puro que o cabeçalho do design system ainda
    desenha (`<a href="/sair">`, `nucleo/templates/layout/header.html`,
    port congelado) sem reabrir a porta que o POST-only fecha — ver
    `comum.confirmacao.tela_de_confirmacao`.
    """
    if request.method == "GET":
        return tela_de_confirmacao(
            request, titulo=_("Sair"), pergunta="Sair do sistema?",
            rotulo_botao="Sair", action=reverse("sair"),
        )
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    # A ordem (encerrar a personificação, registrar quem saiu, derrubar a
    # sessão) mora em `contas.entrada.sair_e_registrar`, que a API também chama.
    sair_e_registrar(request)
    return HttpResponseRedirect(reverse("entrar"))


# `mw5.personificar` nunca é declarado como módulo (`plataforma.declaracao`):
# sem entrar em `chaves`, `contas.backend.permissoes_de` nunca traduz
# NENHUMA `Permission` para este nome — a única forma de `pode()` liberar é o
# atalho de superusuário. Mesma regra e mesmo motivo de `mw5.aparencia` e
# `mw5.modulos` em `plataforma/views.py`.
#
# Esta guarda sozinha também fecha o encadeamento: `exigir_permissao` lê
# `usuario_da_sessao`, que devolve o ALVO enquanto uma personificação já está
# em curso — e o alvo nunca é superusuário (`alvo_personificavel` garante
# isso ao entrar). Quem já personifica alguém, portanto, já falha aqui, antes
# mesmo de `iniciar` rodar uma linha.
@exigir_permissao("mw5.personificar")
def personificar(request) -> HttpResponse:
    """Começa a ver o sistema como o usuário do `id` do corpo do POST."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        iniciar(request, request.POST.get("id", ""))
    except PersonificacaoRecusada:
        # 404, e não 403: a mesma razão de `exigir_permissao` — quem não
        # pode não precisa saber se o alvo existia, se era superusuário, ou
        # se já havia uma personificação em curso.
        return HttpResponseNotFound()
    return HttpResponseRedirect("/")


@exigir_login
def voltar_a_ser_eu(request) -> HttpResponse:
    """Encerra a personificação em curso, se houver.

    `exigir_login`, não `exigir_permissao("mw5.personificar")`: quem chama
    isto é o ALVO visto pela sessão (é ele quem `usuario_da_sessao` devolve
    enquanto a personificação dura), e o alvo nunca teria essa permissão —
    exigi-la aqui tornaria impossível sair da personificação por esta rota.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    encerrar(request)
    return HttpResponseRedirect("/")
