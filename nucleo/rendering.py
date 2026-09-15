"""A base de todo componente do design system.

Um componente é uma dataclass tipada com um template Jinja ao lado. A classe é a
API pública — é ela que o gerador constrói programaticamente e que o editor
autocompleta; o template é a única fonte do markup, para que ninguém precise
caçar HTML dentro de string Python.

Composição é por árvore, não por concatenação de texto: um `Card` recebe outros
componentes como filhos e o Jinja os renderiza sozinho, porque todo componente
implementa `__html__`. Na prática isso significa que `{{ c.footer }}` num
template simplesmente funciona, seja o footer uma string, um botão ou uma lista
de botões — e nada disso escapa HTML por acidente.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Iterable, Iterator

from jinja2 import (
    ChoiceLoader,
    Environment,
    PackageLoader,
    StrictUndefined,
    select_autoescape,
)
from markupsafe import Markup

__all__ = [
    "Component",
    "Renderable",
    "create_environment",
    "get_environment",
    "use_environment",
    "html_attrs",
    "render_all",
]

Renderable = Any  # str, Component, ou iterável de qualquer um dos dois

_environment: ContextVar["Environment | None"] = ContextVar(
    "nucleo_environment", default=None
)
_default_environment: "Environment | None" = None


def create_environment(*extra_loaders: Any) -> Environment:
    """Cria o ambiente Jinja do design system.

    Os loaders extras vêm antes do nosso, então um projeto pode sobrescrever o
    template de um componente colocando um arquivo de mesmo nome na própria
    pasta — a saída de emergência para quando um cliente precisa de uma variação
    que não vale a pena generalizar.
    """
    env = Environment(
        loader=ChoiceLoader([*extra_loaders, PackageLoader("nucleo", "templates")]),
        autoescape=select_autoescape(default=True, default_for_string=True),
        trim_blocks=True,
        lstrip_blocks=True,
        # Errar o nome de uma variável tem que quebrar na hora, não render vazio:
        # um botão que some silenciosamente é muito pior de achar do que um erro.
        undefined=StrictUndefined,
    )
    env.filters["render"] = render_all
    env.filters["attrs"] = html_attrs

    # Importado aqui dentro, e não no topo, porque `components` depende deste
    # módulo. O import tardio quebra o ciclo sem precisar de camada extra.
    from .components.primitives import Icon

    def icon(name: str, size: str = "", **kwargs: Any) -> Markup:
        return Icon(name=name, size=size, **kwargs).render(env)

    env.globals["icon"] = icon

    def estatico(nome: str) -> str:
        """A URL de um arquivo do `static/`, com a versão dele junto.

        Sem isso o navegador guarda o CSS e não pergunta mais: quem mexe no
        `mw5.css` continua vendo a versão de ontem, e o defeito que ele acabou
        de consertar segue na tela. Custou uma tarde inteira de conserto no
        escuro — três correções feitas contra uma folha que o navegador nem
        estava usando.

        A data de modificação do arquivo, e não um número escrito à mão: assim
        ninguém precisa lembrar de trocá-lo, e ela muda exatamente quando o
        conteúdo muda. Arquivo que não existe sai sem versão em vez de derrubar
        a tela — a página tem que abrir mesmo com um caminho torto.
        """
        arquivo = Path(__file__).parent / "static" / "nucleo" / nome
        try:
            return f"/static/nucleo/{nome}?v={int(arquivo.stat().st_mtime)}"
        except OSError:
            return f"/static/nucleo/{nome}"

    env.globals["estatico"] = estatico
    return env


def html_attrs(values: "dict[str, Any] | None") -> Markup:
    """Converte um dicionário em atributos HTML, escapando os valores.

    É o que permite passar `hx-get`, `data-*` ou `aria-*` para qualquer
    componente sem precisar de um campo dedicado por atributo. `True` vira
    atributo booleano; `None` e `False` somem.
    """
    if not values:
        return Markup("")
    parts: list[str] = []
    for name, value in values.items():
        if value is None or value is False:
            continue
        name = str(name).replace("_", "-")
        if value is True:
            parts.append(Markup.escape(name))
        else:
            parts.append(f'{Markup.escape(name)}="{Markup.escape(value)}"')
    return Markup(" " + " ".join(parts)) if parts else Markup("")


def get_environment() -> Environment:
    """O ambiente ativo — o da aplicação, ou um padrão para uso isolado/testes."""
    current = _environment.get()
    if current is not None:
        return current
    global _default_environment
    if _default_environment is None:
        _default_environment = create_environment()
    return _default_environment


@contextmanager
def use_environment(env: Environment) -> Iterator[Environment]:
    token = _environment.set(env)
    try:
        yield env
    finally:
        _environment.reset(token)


def render_all(value: Renderable) -> Markup:
    """Renderiza qualquer coisa que possa ir para dentro de um componente."""
    if value is None or value is False:
        return Markup("")
    if hasattr(value, "__html__"):
        return Markup(value.__html__())
    if isinstance(value, (list, tuple)) or (
        isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict))
    ):
        return Markup("").join(render_all(item) for item in value)
    return Markup.escape(value)


@dataclass
class Component:
    """Classe base. Subclasses declaram `template` e seus próprios campos."""

    #: Caminho do template dentro de `nucleo/templates/`.
    template: ClassVar[str] = ""

    def template_context(self) -> dict[str, Any]:
        """O que o template enxerga. Sobrescreva para acrescentar derivados."""
        return {"c": self}

    def render(self, env: "Environment | None" = None) -> Markup:
        if not self.template:
            raise NotImplementedError(
                f"{type(self).__name__} não declarou `template`"
            )
        env = env or get_environment()
        return Markup(env.get_template(self.template).render(**self.template_context()))

    def __html__(self) -> str:
        return str(self.render())

    def __str__(self) -> str:  # pragma: no cover - conveniência em depuração
        return str(self.render())
