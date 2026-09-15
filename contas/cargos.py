"""Quando um cargo pode ser removido.

Devolve a frase, e não um booleano, porque a tela precisa dizer o motivo, e duas telas
escrevendo a mesma frase à mão divergiriam com o tempo.
"""

from __future__ import annotations

__all__ = ["pode_remover"]


def pode_remover(cargo) -> "str | None":
    """A frase da recusa, ou `None` quando o cargo pode sair.

    **De fábrica não sai**: a próxima semeadura
    (`contas.cargos_de_fabrica.semear_cargos`) o recriaria em silêncio, e a
    pessoa removeria o mesmo cargo duas vezes sem entender. Editar pode.

    **Com alocação não sai**: `Alocacao.cargo` é `PROTECT`, e remover daria erro
    no banco em vez de dizer quantas pessoas estão nele.
    """
    if cargo.de_fabrica:
        return ("Este é um cargo de fábrica e não pode ser removido. Você pode "
                "renomeá-lo e mudar o que ele concede.")
    total = cargo.alocacoes.values("pessoa").distinct().count()
    if total == 1:
        return "Este cargo tem 1 pessoa alocada e não pode ser removido."
    if total > 1:
        return (f"Este cargo tem {total} pessoas alocadas e não pode ser "
                f"removido.")
    return None
