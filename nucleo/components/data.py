"""Tabela, paginação e barra de filtros — o trio de toda tela de listagem."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from typing import Any, Callable, ClassVar, Sequence

from ..rendering import Component, Renderable
from .containers import EmptyState

__all__ = ["Column", "FilterBar", "Pagination", "Table"]


@dataclass
class Column:
    """Uma coluna da tabela.

    `render` recebe a linha inteira e devolve o que aparece na célula — é por
    onde entram pills de status, contadores e botões, sem que a tabela precise
    saber o que qualquer um deles significa.
    """

    key: str
    label: str
    align: str = ""  # "" | "center" | "num"
    width: str | None = None
    strong: bool = False
    muted: bool = False
    render: Callable[[Any], Renderable] | None = None

    def __post_init__(self) -> None:
        if self.align not in ("", "center", "num"):
            raise ValueError(
                f"Column.align={self.align!r} inválido — use '', 'center' ou 'num'"
            )

    def value_of(self, row: Any) -> Renderable:
        if self.render is not None:
            return self.render(row)
        if isinstance(row, dict):
            return row.get(self.key, "")
        return getattr(row, self.key, "")

    @property
    def header_classes(self) -> str:
        return self.align

    @property
    def cell_classes(self) -> str:
        parts = [p for p in (self.align,) if p]
        if self.strong:
            parts.append("strong")
        if self.muted:
            parts.append("muted")
        return " ".join(parts)


@dataclass
class Table(Component):
    """Tabela de listagem.

    Quando `rows` vem vazia, mostra o estado vazio no lugar do cabeçalho — uma
    tabela com títulos de coluna e nada embaixo parece defeito, não ausência
    de dados.
    """

    template: ClassVar[str] = "components/table.html"

    columns: Sequence[Column] = ()
    rows: Sequence[Any] = ()
    selectable: bool = False
    selection_name: str = "sel"
    row_actions: Callable[[Any], Renderable] | None = None
    row_attrs: Callable[[Any], dict[str, Any]] | None = None
    empty: EmptyState | None = None

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Table precisa de pelo menos uma coluna")
        if self.empty is None:
            self.empty = EmptyState(
                title="Nenhum registro encontrado",
                message="Ajuste os filtros ou cadastre o primeiro registro.",
            )

    @property
    def is_empty(self) -> bool:
        return len(self.rows) == 0

    def attrs_for(self, row: Any) -> dict[str, Any]:
        return self.row_attrs(row) if self.row_attrs else {}

    def actions_for(self, row: Any) -> Renderable:
        return self.row_actions(row) if self.row_actions else ""


@dataclass
class Pagination(Component):
    """Paginação. Colapsa o miolo com reticências quando há páginas demais."""

    template: ClassVar[str] = "components/pagination.html"

    page: int
    per_page: int
    total: int
    url_for_page: Callable[[int], str] = lambda p: f"?page={p}"
    window: int = 2  # quantas páginas mostrar de cada lado da atual

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("página começa em 1")
        if self.per_page < 1:
            raise ValueError("per_page precisa ser positivo")

    @property
    def pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))

    @property
    def first_item(self) -> int:
        return 0 if self.total == 0 else (self.page - 1) * self.per_page + 1

    @property
    def last_item(self) -> int:
        return min(self.page * self.per_page, self.total)

    def numbers(self) -> list[int | None]:
        """Os números a exibir. `None` marca onde entra o "…"."""
        last = self.pages
        if last <= 7:
            return list(range(1, last + 1))

        candidates = {1, last, self.page}
        for offset in range(1, self.window + 1):
            candidates.add(self.page - offset)
            candidates.add(self.page + offset)
        visible = sorted(p for p in candidates if 1 <= p <= last)

        result: list[int | None] = []
        previous: int | None = None
        for number in visible:
            if previous is not None and number - previous > 1:
                result.append(None)
            result.append(number)
            previous = number
        return result


@dataclass
class FilterBar(Component):
    """A faixa de filtros acima da tabela. É um `<form>` GET de verdade, para
    que o resultado filtrado tenha URL própria e possa ser compartilhado."""

    template: ClassVar[str] = "components/filter_bar.html"

    fields: Renderable = ""
    action: str = ""
    submit_label: str = "Filtrar"
    extra_actions: Renderable = ""
    attrs: dict[str, Any] = field(default_factory=dict)
