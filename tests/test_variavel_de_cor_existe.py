"""Nenhuma folha desta casa pode citar uma variável que ninguém declara.

**`var(--nao-existe)` não é erro em CSS: é NADA.** A propriedade cai, o
navegador segue em frente sem avisar, e o resultado é um elemento sem fundo,
sem borda ou sem cor — que se lê como "estilo faltando", nunca como "nome
errado". Foi o que aconteceu em 10/09/2026 com `--surface-1`, que não existe:
os tokens do design system são `--surface`, `--surface-2` e `--surface-3`. O
painel da caixa de escolha nasceu transparente por cima do formulário, e o
"1" no fim do nome era tudo.

O nome errado é fácil de escrever justamente porque a família tem números: com
`surface-2` e `surface-3` na folha, `surface-1` parece o primeiro da série. E a
mesma armadilha vale para `outline`/`outline-2` e para `on-surface`.

**O conjunto do que existe não é uma lista escrita à mão** — ele sai do próprio
gerador do tema (`nucleo.theme.css.render_theme_css`), mais o que cada folha
declara por conta. Assim um token novo do design system passa a valer aqui
sozinho, sem ninguém lembrar de acrescentá-lo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

#: As folhas DESTA casa. O `nucleo/` é porte verbatim e não se emenda aqui
#: (ver CLAUDE.md) — varrer o que não se pode corrigir só produziria isenção.
FOLHAS = [
    *sorted(Path("catalogo/static/catalogo").glob("*.css")),
    *sorted(Path("plataforma/static/plataforma").glob("*.css")),
]

#: Variáveis que a própria página injeta no `style=` de um elemento, e que
#: portanto não aparecem declaradas em folha nenhuma. Cada uma com o motivo,
#: como manda a casa — isenção sem motivo vira gaveta.
DE_FORA: dict[str, str] = {
    # Nenhuma hoje. O dicionário existe para a primeira ter onde entrar COM o
    # motivo escrito ao lado, em vez de virar uma exceção solta na varredura.
}


def _declaradas_pelo_tema() -> set[str]:
    """O que `render_theme_css` emite — a fonte de verdade dos tokens."""
    from nucleo.theme.css import render_theme_css
    from plataforma.marca import MARCA_PADRAO

    return set(re.findall(r"(--[\w-]+)\s*:", render_theme_css(MARCA_PADRAO)))


def _declaradas_nas_folhas() -> set[str]:
    """O que as folhas declaram por conta própria, aqui e no `nucleo`."""
    nomes: set[str] = set()
    for caminho in [*FOLHAS, *sorted(Path("nucleo/static/nucleo").glob("*.css"))]:
        nomes |= set(re.findall(r"(--[\w-]+)\s*:",
                                caminho.read_text(encoding="utf-8")))
    return nomes


def _usadas(folha: Path) -> set[str]:
    return set(re.findall(r"var\(\s*(--[\w-]+)",
                          folha.read_text(encoding="utf-8")))


@pytest.mark.parametrize("folha", FOLHAS, ids=lambda f: f.name)
def test_toda_variavel_citada_existe(folha):
    existentes = (_declaradas_pelo_tema() | _declaradas_nas_folhas()
                  | set(DE_FORA))
    inventadas = sorted(_usadas(folha) - existentes)
    assert not inventadas, (
        f"{folha.name} cita variáveis que ninguém declara: {inventadas}. "
        f"Em CSS isso não é erro — a propriedade some em silêncio, e o "
        f"elemento aparece sem fundo, sem borda ou sem cor.")


def test_a_varredura_pegaria_o_caso_que_ja_falhou():
    """Prova de que ela não passa por passar: `--surface-1` é o nome de
    10/09/2026, e ele não pode estar entre os que existem."""
    existentes = _declaradas_pelo_tema() | _declaradas_nas_folhas()
    assert "--surface" in existentes
    assert "--surface-2" in existentes
    assert "--surface-1" not in existentes, (
        "se este nome passar a existir, a varredura para de pegar o defeito "
        "— e aí ela precisa de outro caso de prova")
