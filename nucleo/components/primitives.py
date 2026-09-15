"""Os componentes atômicos: ícone, botão, pill, badge, avatar, spinner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from markupsafe import Markup

from .. import icons
from ..rendering import Component, Renderable

__all__ = [
    "Avatar",
    "Badge",
    "Button",
    "Icon",
    "IconButton",
    "Pill",
    "Raw",
    "Spinner",
    "TONES",
]

#: Os tons semânticos que o design system reconhece. Usados por pill, badge e
#: alerta — sempre os mesmos nomes, para que um estado "atenção" tenha a mesma
#: cor esteja ele numa tabela, num aviso ou num toast.
TONES = ("neutral", "ok", "info", "warn", "danger")


def _validate(value: str, allowed: tuple[str, ...], field_name: str, owner: str) -> None:
    if value not in allowed:
        raise ValueError(
            f"{owner}.{field_name}={value!r} não existe. Use um de: {', '.join(allowed)}"
        )


@dataclass
class Icon(Component):
    """Um ícone do conjunto, herdando a cor do texto em volta."""

    template: ClassVar[str] = "components/icon.html"

    name: str
    size: str = ""  # "" | "sm" | "lg"
    css_class: str = ""
    label: str | None = None  # se preenchido, o ícone deixa de ser decorativo

    def __post_init__(self) -> None:
        _validate(self.size, ("", "sm", "lg"), "size", "Icon")
        icons.get(self.name)  # falha cedo se o nome estiver errado

    def template_context(self) -> dict[str, Any]:
        return {"c": self, "paths": Markup(icons.get(self.name))}


@dataclass
class Button(Component):
    """Botão ou link com cara de botão — a decisão sai do campo `href`.

    Um botão que navega deve ser `<a>` de verdade, para abrir em nova aba com
    ctrl+clique e aparecer no histórico. Um que dispara ação é `<button>`. Sai
    caro deixar essa escolha para quem chama, então ela é derivada aqui.
    """

    template: ClassVar[str] = "components/button.html"

    VARIANTS: ClassVar[tuple[str, ...]] = ("default", "primary", "ghost", "danger")

    label: str = ""
    variant: str = "default"
    size: str = ""  # "" | "sm" | "lg"
    icon: str | None = None
    icon_right: str | None = None
    href: str | None = None
    type: str = "button"  # submit | button | reset
    disabled: bool = False
    block: bool = False
    title: str | None = None
    css_class: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate(self.variant, self.VARIANTS, "variant", "Button")
        _validate(self.size, ("", "sm", "lg"), "size", "Button")
        _validate(self.type, ("button", "submit", "reset"), "type", "Button")
        if not self.label and not self.icon:
            raise ValueError("Button precisa de `label` ou `icon` — senão fica invisível")
        if self.icon and not self.label and not self.title:
            raise ValueError(
                "Button só com ícone precisa de `title`, senão quem usa leitor de tela "
                "não descobre o que ele faz"
            )

    @property
    def classes(self) -> str:
        parts = ["btn"]
        if self.variant != "default":
            parts.append(self.variant)
        if self.size:
            parts.append(self.size)
        if self.block:
            parts.append("block")
        if self.css_class:
            parts.append(self.css_class)
        return " ".join(parts)


@dataclass
class IconButton(Component):
    """Botão redondo só de ícone — o padrão do header (tema, sair, notificações)."""

    template: ClassVar[str] = "components/icon_button.html"

    icon: str
    title: str
    href: str | None = None
    badge: bool = False  # ponto vermelho de "tem novidade"
    css_class: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Pill(Component):
    """Indicador de estado. Vira botão quando recebe `attrs` de clique.

    Nos mocks o status de um contrato é clicável e abre o histórico — por isso a
    pill precisa saber virar `<button>` sem mudar de aparência.
    """

    template: ClassVar[str] = "components/pill.html"

    label: str
    tone: str = "neutral"
    small: bool = False
    interactive: bool = False
    title: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate(self.tone, TONES, "tone", "Pill")

    @property
    def classes(self) -> str:
        parts = ["pill", self.tone]
        if self.small:
            parts.append("sm")
        return " ".join(parts)


@dataclass
class Badge(Component):
    """Etiqueta curta: "NOVO", "RASCUNHO", o nome de um plano."""

    template: ClassVar[str] = "components/badge.html"

    label: str
    tone: str = "neutral"  # neutral | info | warn | primary | accent

    def __post_init__(self) -> None:
        _validate(
            self.tone, ("neutral", "info", "warn", "primary", "accent"), "tone", "Badge"
        )


@dataclass
class Avatar(Component):
    """Foto do usuário, ou as iniciais dele sobre o gradiente da marca."""

    template: ClassVar[str] = "components/avatar.html"

    name: str
    image: str | None = None
    size: str = ""  # "" | "sm" | "lg"
    css_class: str = ""

    def __post_init__(self) -> None:
        _validate(self.size, ("", "sm", "lg"), "size", "Avatar")

    @property
    def initials(self) -> str:
        """Primeira e última inicial — "Ana Paula Souza" vira "AS"."""
        parts = [p for p in self.name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][0].upper()
        return (parts[0][0] + parts[-1][0]).upper()


@dataclass
class Spinner(Component):
    """Indicador de carregamento. Com `label`, vira bloco centralizado."""

    template: ClassVar[str] = "components/spinner.html"

    label: str | None = None
    large: bool = False
    indicator: bool = False  # esconde até o HTMX marcar a requisição em curso


@dataclass
class Raw(Component):
    """Escotilha de emergência: HTML já confiável, injetado como está.

    Existe para gráficos gerados server-side e conteúdo vindo de um editor rico
    já sanitizado. Qualquer outro uso é sinal de que falta um componente.
    """

    template: ClassVar[str] = ""

    html: str

    def render(self, env: Any = None) -> Markup:
        return Markup(self.html)
