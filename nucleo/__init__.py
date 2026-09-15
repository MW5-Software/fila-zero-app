"""KRONOS.net — o nucleo: tema, componentes e layout do design system.

A superficie de topo e o contrato que as telas consomem. Ela cresce a cada
tarefa da entrega: hoje o tema, a base do componente, quem está logado e o
shell que monta a página em volta do conteúdo.
"""

from .permissoes import User, pode
from .rendering import Component, create_environment, use_environment
from .resposta import render
from .site import Site
from .theme import Brand, render_theme_css

__all__ = [
    "Brand",
    "Component",
    "Site",
    "User",
    "create_environment",
    "pode",
    "render",
    "render_theme_css",
    "use_environment",
]
