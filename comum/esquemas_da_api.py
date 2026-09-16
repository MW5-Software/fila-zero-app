"""Os pedaços de schema que toda API da casa repete.

`Pagina` é a R46 no contrato: toda lista herda dela, e
`tests/test_regra_tabela.py` recusa lista que não herde.
"""

from __future__ import annotations

from ninja import Schema

__all__ = ["ColunaDaLista", "OpcaoDaColuna", "Pagina"]


class OpcaoDaColuna(Schema):
    valor: str
    rotulo: str


class ColunaDaLista(Schema):
    chave: str
    rotulo: str
    tipo: str | None
    operadores: list[str]
    ordenavel: bool
    opcoes: list[OpcaoDaColuna] | None


class Pagina(Schema):
    """Herde e declare `itens: list[<SeuItem>]`."""

    pagina: int
    por_pagina: int
    total: int
    ordenar: str
    colunas: list[ColunaDaLista]
