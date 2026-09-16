"""`X-Vendo-Como` em toda resposta de `/api/` enquanto houver personificação.

Na web, toda tela mostra o aviso (`tests/test_personificacao.py` cobra). No
app, quem mostra é ele — e só pode mostrar se souber. Um cabeçalho posto aqui
chega em toda resposta, inclusive a de erro e a de rota que não existe, sem
nenhuma operação precisar lembrar.

GUID e não nome: cabeçalho HTTP é latin-1, e "João" viraria codificação MIME
que o app teria de decodificar. O nome sai de `GET /api/v1/eu`.
"""

from __future__ import annotations

from .personificacao import personificando
from .sessao import identidade_da_sessao, usuario_original_da_sessao
from .sessao_por_cabecalho import e_da_api

__all__ = ["CABECALHO", "MiddlewareDoVendoComo"]

CABECALHO = "X-Vendo-Como"


def _guid_do_alvo(request) -> str:
    # Atalho, e não trava: sem personificação, quem se vê já é o original, e a
    # comparação abaixo daria vazio do mesmo jeito. Ele só poupa reconstruir
    # as duas pessoas em toda resposta da API de quem não personifica.
    if getattr(request, "session", None) is None or not personificando(request):
        return ""
    original = usuario_original_da_sessao(request)
    visto = identidade_da_sessao(request)
    # `identidade_da_sessao` só honra o alvo enquanto o original ainda é
    # superusuário; caída de volta para o original, não há quem avisar.
    if original is None or visto is None or str(visto.id) == str(original.id):
        return ""
    from contas.identidade import usuario_de

    pessoa = usuario_de(visto)
    return str(pessoa.guid) if pessoa is not None else ""


class MiddlewareDoVendoComo:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        if e_da_api(request.path):
            try:
                guid = _guid_do_alvo(request)
            except Exception:
                # O aviso não pode transformar uma resposta boa num 500 — nem
                # mascarar, com um segundo erro, o erro que já está saindo.
                guid = ""
            if guid:
                resposta[CABECALHO] = guid
        return resposta
