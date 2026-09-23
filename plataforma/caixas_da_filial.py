"""Caixas que um módulo de negócio acrescenta ao formulário da FILIAL.

Mesma porta de `plataforma.caixas_da_empresa`, um nível abaixo: a tela de
Filiais é da base, e a base não conhece os módulos (`CLAUDE.md` §3), mas é
natural o negócio ter uma escolha que vale para UMA loja — no Fila Zero, a hora
em que o turno dela termina, que é o que decide quando quem ficou na fila sai
sozinho.

O módulo registra a caixa no `ready()` do app dele: uma função que DESENHA
(recebe a filial, ou `None` ao criar) e uma que GRAVA o que veio no POST
(recebe a requisição e a filial já gravada). O dado mora numa tabela do próprio
módulo.

**Quem grava levanta `ValidationError` para recusar**, e a tela desfaz o
formulário inteiro (o `atomic` da gravação) e mostra a frase — a mesma porta
que a caixa da empresa já usa.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

__all__ = ["CaixaDaFilial", "caixas", "registrar"]


@dataclass(frozen=True)
class CaixaDaFilial:
    #: Identifica a caixa: registrar de novo a mesma chave (o `ready()` roda
    #: mais de uma vez nos testes) substitui, e não duplica.
    chave: str
    desenhar: Callable
    gravar: Callable


_CAIXAS: "dict[str, CaixaDaFilial]" = {}


def registrar(caixa: CaixaDaFilial) -> None:
    _CAIXAS[caixa.chave] = caixa


def caixas() -> "list[CaixaDaFilial]":
    """Na ordem em que foram registradas."""
    return list(_CAIXAS.values())