"""Caixas que um módulo de negócio acrescenta ao formulário da empresa.

A tela de Empresas é da base, e a base não conhece os módulos (`CLAUDE.md`
§3). Mas é natural o negócio ter uma escolha que vale para a empresa inteira —
no Fila Zero, o que acontece com o vendedor depois de lançar o atendimento. Até
21/09/2026 isso era uma coluna de `plataforma.Empresa` e uma caixa escrita
dentro de `views_empresa.py`, e o Fila Zero nunca mais recebia a base limpa.

Agora o módulo registra uma caixa no `ready()` do app dele: uma função que
DESENHA a caixa (recebe a empresa, ou `None` ao criar) e uma que GRAVA o que
veio no POST (recebe a requisição e a empresa já gravada). O dado mora numa
tabela do próprio módulo.

**Quem grava levanta `ValidationError` para recusar**, e a tela desfaz o
formulário inteiro (o `atomic` da gravação) e mostra a frase — a mesma porta
que a recusa do model da empresa já usa.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

__all__ = ["CaixaDaEmpresa", "caixas", "registrar"]


@dataclass(frozen=True)
class CaixaDaEmpresa:
    #: Identifica a caixa: registrar de novo a mesma chave (o `ready()` roda
    #: mais de uma vez nos testes) substitui, e não duplica.
    chave: str
    desenhar: Callable
    gravar: Callable


_CAIXAS: "dict[str, CaixaDaEmpresa]" = {}


def registrar(caixa: CaixaDaEmpresa) -> None:
    _CAIXAS[caixa.chave] = caixa


def caixas() -> "list[CaixaDaEmpresa]":
    """Na ordem em que foram registradas."""
    return list(_CAIXAS.values())
