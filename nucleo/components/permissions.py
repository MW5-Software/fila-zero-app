"""Exibição condicional por permissão."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from markupsafe import Markup

from ..rendering import Component, Renderable, render_all

__all__ = ["Protected"]


@dataclass
class Protected(Component):
    """Mostra o conteúdo só quando `allowed` é verdadeiro.

    Recebe um booleano já resolvido em vez de consultar o usuário logado por
    conta própria. Isso mantém a biblioteca de componentes ignorante sobre como
    a autenticação funciona — o que importa porque cada cliente pode trocar o
    backend de permissões — e deixa o componente trivial de testar.

    Esconder um botão não é controle de acesso: a rota que ele chama tem que
    checar a permissão de novo. Aqui é só para não oferecer à pessoa uma ação
    que ela não pode concluir.
    """

    template: ClassVar[str] = ""

    allowed: bool = False
    children: Renderable = ""
    fallback: Renderable = ""

    def render(self, env: Any = None) -> Markup:
        return render_all(self.children if self.allowed else self.fallback)
