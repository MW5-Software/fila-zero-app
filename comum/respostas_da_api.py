"""O formato de erro da API — um só.

O `codigo` é estável e é por ele que o app decide o que fazer; a `mensagem`
sai traduzida para o idioma da pessoa e é só para mostrar.
"""

from __future__ import annotations

from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _

from .guardas_de_acesso import Barreira

__all__ = ["erro", "nao_existe", "resposta_da_barreira"]


def erro(status: int, codigo: str, mensagem, campos=None, extra=None) -> JsonResponse:
    corpo = {"codigo": codigo, "mensagem": str(mensagem)}
    if campos:
        corpo["campos"] = {str(campo): [str(m) for m in mensagens]
                           for campo, mensagens in campos.items()}
    if extra:
        corpo.update(extra)
    return JsonResponse({"erro": corpo}, status=status)


_POR_BARREIRA = {
    Barreira.SEM_SESSAO: (401, _("Entre de novo para continuar.")),
    Barreira.SENHA_EXPIRADA: (403, _("Sua senha venceu. Troque-a para continuar.")),
    # Uma frase só para "sem permissão" e "módulo desligado": a mesma razão do
    # 404 da web — quem não pode não descobre por qual dos dois motivos.
    Barreira.NAO_EXISTE: (404, _("Não encontrado.")),
    Barreira.SEM_FILIAL: (409, _("Nenhuma filial liberada para você.")),
}


def resposta_da_barreira(obstaculo: Barreira) -> JsonResponse:
    status, mensagem = _POR_BARREIRA[obstaculo]
    return erro(status, obstaculo.value, mensagem)


def nao_existe() -> JsonResponse:
    """Para a operação que procura algo pelo GUID e não acha — ou acha fora do
    alcance. Mesmo corpo da guarda: um GUID de outra conta não pode ser
    distinguível de um GUID que nunca existiu."""
    return resposta_da_barreira(Barreira.NAO_EXISTE)
