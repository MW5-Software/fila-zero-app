"""Transforma um `Brand` nas custom properties CSS que o resto do sistema consome.

As três camadas do mock são preservadas de propósito:

1. `:root` — o tema padrão do projeto
2. `@media (prefers-color-scheme: dark)` — acompanha o sistema operacional
3. `:root[data-theme="..."]` — a escolha explícita do usuário, que vence as duas

A camada 2 só é emitida quando o projeto está em `default_theme: system`. Se o
cliente decidiu que o sistema dele é claro, seguir a preferência do SO seria
justamente o contrário do que ele pediu — mas o botão de alternar continua
funcionando, porque a camada 3 é sempre emitida.
"""

from __future__ import annotations

from .brand import Brand


def _block(selector: str, tokens: dict[str, str], indent: str = "") -> str:
    lines = [f"{indent}{selector}{{"]
    lines += [f"{indent}  --{name}:{value};" for name, value in tokens.items()]
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def render_theme_css(brand: Brand) -> str:
    """O CSS de tema completo de um cliente. Servido em `/static/theme.css`."""
    light = brand.tokens("light")
    dark = brand.tokens("dark")
    base = dark if brand.default_theme == "dark" else light

    parts = [
        f"/* Tema gerado para {brand.client_name}. Não edite à mão: a fonte é brand.yaml. */",
        _block(":root", base),
    ]
    if brand.default_theme == "system":
        parts.append(
            "@media (prefers-color-scheme:dark){\n"
            + _block(":root", dark, indent="  ")
            + "\n}"
        )
    parts.append(_block(':root[data-theme="light"]', light))
    parts.append(_block(':root[data-theme="dark"]', dark))
    return "\n".join(parts) + "\n"
