"""O erro em produção: onde cai, quem vê — Bloco 7 (item 35).

O `MiddlewareDeFalhas` é a porta única: toda exceção que sobe de uma view
grava uma linha em `plataforma.models.Falha` (append-only) e sobe INTACTA —
quem transforma exceção em página 500 segue sendo o Django. O registro
engolir a falha é o pior desfecho possível (o 500 por banco caído viraria
dois 500), então a gravação é embrulhada em `try` que desiste em silêncio.

As páginas (`pagina_de_erro`, `pagina_nao_encontrada`) são À PROVA do
próprio sistema: primeiro tentam a página bonita com o tema; se a própria
montagem falhar (o banco pode ser a causa do 500), caem num HTML cru. Em
nenhum dos dois casos sai traceback, setting ou caminho de máquina — quem
lê traceback é a MW5, em `/mw5/falhas` ou no `docker logs`.
"""

from __future__ import annotations

import logging
import traceback as _traceback

from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

__all__ = ["MiddlewareDeFalhas", "pagina_de_erro", "pagina_nao_encontrada", "registrar_falha"]

#: Teto do traceback gravado. O inteiro vai para o log; no banco basta o
#: começo — é consulta, não arquivo.
_TETO_DO_TRACEBACK = 8000


def _gravar(request, erro: BaseException) -> "Falha | None":
    """A linha da falha, ou `None` se não deu para gravar. Levantar aqui é
    proibido — o chamador depende."""
    try:
        from .models import Falha

        autor_login = autor_nome = ""
        try:
            from comum.sessao import usuario_da_sessao

            usuario = usuario_da_sessao(request)
            if usuario is not None:
                autor_login = usuario.login
                autor_nome = usuario.nome
        except Exception:
            pass  # a falha pode SER a sessão; o registro vale sem autor

        origem = _traceback.format_exc()
        return Falha.objects.create(
            caminho=getattr(request, "path", "")[:255],
            metodo=getattr(request, "method", "")[:10],
            autor_login=autor_login[:150],
            autor_nome=autor_nome[:150],
            resumo=f"{type(erro).__name__}: {erro}"[:255],
            traceback=origem[:_TETO_DO_TRACEBACK],
        )
    except Exception:
        pass  # engolir DE PROPÓSITO — ver o docstring do módulo
    return None


#: Marca posta na própria exceção depois de gravada, para os dois caminhos
#: abaixo nunca registrarem a mesma falha duas vezes.
_JA_GRAVADA = "_falha_ja_registrada"


def registrar_falha(request, erro: BaseException) -> "Falha | None":
    """Grava a falha uma vez só e escreve no log. Devolve a linha, ou `None`
    se ela já tinha sido gravada ou a gravação falhou.

    É o caminho do middleware e o do tratador de exceção da API
    (`plataforma.api_tratadores`). Um caminho só, com a mesma marca
    `_JA_GRAVADA`: gravar por dois caminhos diferentes é como a mesma falha
    vira duas linhas — ou nenhuma.

    `_gravar` é buscada no módulo a cada chamada, e não guardada: é o que
    deixa `tests/test_falhas.py` trocá-la por uma que quebra.
    """
    try:
        if getattr(erro, _JA_GRAVADA, False):
            return None
        setattr(erro, _JA_GRAVADA, True)
        falha = _gravar(request, erro)
        logging.getLogger("plataforma.falhas").exception(
            "500 em %s %s: %s",
            getattr(request, "path", "?"),
            getattr(request, "method", "?"), erro)
        return falha
    except Exception:
        return None


class MiddlewareDeFalhas:
    """Grava a exceção e a devolve ao Django — nunca a come.

    **`process_exception` é o caminho que funciona, e o `__call__` é a rede
    embaixo dele.** Isto já esteve errado, e o defeito era invisível: havia
    só o `try/except` em volta de `self.get_response(request)`. Parece o
    certo e não é — o Django embrulha cada camada em
    `convert_exception_to_response`, então a exceção de uma VIEW já virou uma
    resposta 500 antes de voltar para cá, e o `except` nunca disparava.
    Resultado: `/mw5/falhas` ficava permanentemente vazia, e a tela que
    existe para a MW5 ver o que estourou sem entrar no VPS não via nada.

    O teste que deveria ter pego montava o middleware em volta de uma função
    que levanta direto, sem o embrulho — provava um cenário que não acontece
    na pilha real. `tests/test_falhas.py` passou a exercitar as duas coisas.

    O `__call__` continua porque o `process_exception` só é chamado para
    exceções de VIEW: uma que suba de um middleware abaixo deste não passa
    por lá, e essa ainda chega aqui.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def process_exception(self, request, erro):
        """O gancho que o Django chama com a exceção da view ainda viva.

        Devolve `None` de propósito: quem transforma exceção em página 500
        continua sendo o Django. Retornar uma resposta aqui tomaria para este
        middleware uma decisão que não é dele.
        """
        self._registrar(request, erro)
        return None

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as erro:
            self._registrar(request, erro)
            raise

    @staticmethod
    def _registrar(request, erro) -> None:
        # O engolir mora em `registrar_falha`: se a gravação falhar por
        # qualquer motivo, a exceção ORIGINAL sobe — nunca uma segunda por cima.
        registrar_falha(request, erro)


def _html_cru() -> HttpResponse:
    """O último soco: HTML sem dependência nenhuma. Cor neutra da casa,
    sem nada que possa faltar."""
    corpo = (
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<title>Problema inesperado</title></head>"
        "<body style=\"font-family:system-ui;padding:48px;\">"
        "<h1>Algo inesperado aconteceu</h1>"
        "<p>O problema foi registrado e quem opera o sistema já pode vê-lo. "
        "Tente de novo; se persistir, fale com o suporte.</p>"
        "<p><a href='/'>Voltar ao início</a></p>"
        "</body></html>"
    )
    return HttpResponse(corpo, status=500)


def pagina_de_erro(request) -> HttpResponse:
    """A página de 500. Bonita quando dá, crua quando não dá — nunca
    vazia, nunca com traceback."""
    try:
        from nucleo.components import Alert, PageHeader
        from nucleo.layout import Page
        from comum.ambiente import ambiente
        from nucleo.rendering import use_environment
        from nucleo.resposta import render

        with use_environment(ambiente()):
            from .site import montar_site

            site = montar_site(request)
            pagina = site.page(
                title=_("Problema inesperado"),
                content=[
                    PageHeader(title=_("Algo inesperado aconteceu")),
                    Alert(
                        tone="danger",
                        message="O problema foi registrado e quem opera o "
                                "sistema já pode vê-lo. Tente de novo; se "
                                "persistir, fale com o suporte.",
                    ),
                ],
            )
            resposta = render(pagina)
            resposta.status_code = 500
            return resposta
    except Exception:
        return _html_cru()


def pagina_nao_encontrada(request, exception=None) -> HttpResponse:
    """A página de 404 — o endereço que não existe não é defeito do cliente,
    e a página diz o caminho, em vez de um "Error not found" em inglês."""
    try:
        from nucleo.components import Alert, EmptyState, PageHeader
        from comum.ambiente import ambiente
        from nucleo.rendering import use_environment
        from nucleo.resposta import render

        with use_environment(ambiente()):
            from .site import montar_site

            site = montar_site(request)
            pagina = site.page(
                title=_("Página não encontrada"),
                content=[
                    PageHeader(title=_("Página não encontrada")),
                    Alert(
                        tone="info",
                        message="O endereço acessado não existe neste "
                                "sistema. Se o link veio de alguém, "
                                "provavelmente está velho.",
                    ),
                    EmptyState(
                        titulo=_("Nada neste endereço"),
                        texto=_("Confira o endereço ou volte ao início pelo menu."),
                    ),
                ],
            )
            resposta = render(pagina)
            resposta.status_code = 404
            return resposta
    except Exception:
        return HttpResponse(
            format_html("<h1>Página não encontrada</h1><p>O endereço {} "
                        "não existe neste sistema.</p>", request.path),
            status=404,
        )
