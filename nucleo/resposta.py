"""A ponte entre um componente e uma resposta HTTP do Django.

O Django tem um sistema de templates próprio, e este projeto não o usa para
desenhar tela: o componente já sabe virar HTML, e passar por um segundo motor
de template só para embrulhar o resultado seria uma camada sem trabalho.

O `TEMPLATES` do `settings.py` continua existindo para o que o Django precisa
dele — mensagens de erro, e o admin quando ele entrar.
"""

from __future__ import annotations

from django.http import HttpResponse

from .rendering import Component, get_environment, use_environment

__all__ = ["render"]


def render(component: Component, status: int = 200) -> HttpResponse:
    """Renderiza um componente e devolve a resposta pronta."""
    env = get_environment()
    with use_environment(env):
        html = str(component.render(env))
    return HttpResponse(html, status=status, content_type="text/html; charset=utf-8")
