"""Quem atende na loja — uma regra só, lida em três lugares.

Bate ponto quem atende, e quem gerencia a loja não atende (18/09/2026, pedido
do cliente). A regra é `fila.participar` **e não** `fila.gerenciar`, e não a
ausência de `fila.participar` no cargo, por um motivo prático:
`contas.lugar.pode_dar` exige que quem aloca tenha as permissões do cargo que
concede — um gerente sem `fila.participar` deixaria de poder cadastrar
Vendedor, e a conta nova ficaria sem vendedor nenhum.

**Mora num módulo próprio, e não em `fila/tela.py`, porque as metas também
precisam dela.** A página e a rota do ponto leem `nucleo.permissoes.User` (que
já expandiu `fila.*`), e `fila/metas.py` lê o `frozenset` cru de
`contas.lugar.permissoes_em`; as duas pontas chegam aqui, para a regra não ter
duas versões que divergem no primeiro ajuste.
"""

from __future__ import annotations

__all__ = ["atende"]

#: O que faz alguém participar da fila, e o que faz alguém gerenciá-la. Os
#: coringas entram porque `fila.*` é a permissão da MW5 (`contas/fabrica.py`),
#: e ela não pode virar "atende" por engano.
_PARTICIPA = frozenset({"fila.participar", "fila.*"})
_GERENCIA = frozenset({"fila.gerenciar", "fila.*"})


def atende(permissoes) -> bool:
    """Se quem tem `permissoes` nesta loja bate ponto nela."""
    conjunto = frozenset(permissoes)
    return bool(_PARTICIPA & conjunto) and not (_GERENCIA & conjunto)