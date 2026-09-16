"""A sessão do Django, lida do cabeçalho em `/api/` e do cookie no resto.

**O token do app É a chave da sessão Django.** Toda a máquina de identidade
lê `request.session` — quem entrou, a personificação, a inatividade, a senha
vencida, a filial escolhida. Autenticar o app por outro meio (JWT, a tabela de
token do DRF) obrigaria a reescrever essa máquina ao lado da primeira: dois
jeitos de ser alguém, o defeito que o `Group` e o `Perfil` já causaram aqui.
Só o transporte muda.

**Em `/api/` o cookie é IGNORADO, e isso não é detalhe.** O Ninja isenta as
rotas dele de CSRF, e isso só é seguro porque a sessão da API vem de um
cabeçalho que um site malicioso não consegue fazer o navegador mandar. Se a
API aceitasse também o cookie, qualquer página aberta no navegador de quem
está logado na web agiria na API em nome dela. Isentar de CSRF e ignorar o
cookie são uma decisão só — `tests/test_api_ignora_cookie.py` cobra a segunda.

Pelo mesmo motivo o cabeçalho é ignorado fora de `/api/`: a web continua só
com cookie, e com o CSRF de sempre.
"""

from __future__ import annotations

from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.cache import patch_vary_headers

from .sessao import CHAVE

__all__ = ["MiddlewareDeSessao", "PREFIXO_DA_API", "chave_do_cabecalho", "e_da_api"]

PREFIXO_DA_API = "/api/"

_ESQUEMA = "bearer "


def e_da_api(caminho: str) -> bool:
    return caminho.startswith(PREFIXO_DA_API)


def chave_do_cabecalho(request) -> "str | None":
    """A chave de `Authorization: Bearer <chave>`, ou `None`.

    O esquema é comparado sem caixa porque a RFC 7235 diz que ele não tem
    caixa, e cliente HTTP escreve `bearer` minúsculo sem pedir licença.
    """
    bruto = request.META.get("HTTP_AUTHORIZATION", "")
    if bruto[:len(_ESQUEMA)].lower() != _ESQUEMA:
        return None
    return bruto[len(_ESQUEMA):].strip() or None


class MiddlewareDeSessao(SessionMiddleware):
    """O `SessionMiddleware` do Django, com a origem da chave escolhida pelo
    caminho. Fora de `/api/` é o dele, sem mudar uma linha."""

    def process_request(self, request):
        if not e_da_api(request.path):
            return super().process_request(request)
        request.session = self.SessionStore(chave_do_cabecalho(request))
        return None

    def process_response(self, request, response):
        if not e_da_api(request.path):
            return super().process_response(request, response)
        patch_vary_headers(response, ("Authorization",))
        sessao = getattr(request, "session", None)
        if sessao is None:
            return response
        # Só grava sessão com alguém DENTRO. `_renovar_sessao` mexe na sessão
        # em toda requisição; sem esta condição, cada chamada anônima e cada
        # token vencido criariam uma linha de sessão sem dono. Depois de sair,
        # `flush()` já apagou a linha e a sessão está vazia: nada a gravar.
        # E nunca cookie: o app guarda o token, e um cookie aqui seria a porta
        # que o docstring do módulo fecha.
        if sessao.modified and CHAVE in sessao and response.status_code < 500:
            try:
                sessao.save()
            except UpdateError:
                # A sessão foi apagada por outra requisição no meio desta (a
                # pessoa saiu em outro aparelho). A web responde 400; aqui não
                # há o que salvar, e a próxima chamada já recebe 401.
                pass
        return response
