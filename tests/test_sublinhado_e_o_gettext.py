"""Num módulo que traduz, `_` é o `gettext` — e não a variável de descarte.

**O defeito, encontrado em 09/09/2026 traduzindo a vitrine.** O módulo passou
a importar `gettext as _`, e três linhas antigas usavam `_` como "não me
interessa este valor":

    rotulo, _ = CAMPOS_DE_BUSCA[pedido["campo"]]

A partir dali, dentro daquela função, `_` era `None` — e a primeira chamada de
`_("Limpar tudo")` respondia `TypeError: 'NoneType' object is not callable`. A
tela inteira caía com 500, e só quando a pessoa tinha um filtro ativo.

É armadilha de dois lados: `_` como descarte é idiomático em Python, e
`gettext as _` é o padrão do Django. Os dois juntos, no mesmo arquivo, se
anulam em silêncio — e o teste que pegaria isso é o que passa por aquele ramo
específico da tela.

A varredura recusa o encontro dos dois: num módulo que importa `_` para
traduzir, `_` não pode ser nome de variável. Use `_campos`, `_resto`, `_qual`
— sublinhado na frente do nome diz a mesma coisa e não colide.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTAS = ("contas", "plataforma", "comum", "modulos",
          "config")


def _traduz(arvore: ast.Module) -> bool:
    """O módulo importa alguma coisa com o apelido `_`?"""
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom):
            if any(a.asname == "_" for a in no.names):
                return True
    return False


def _atribuicoes(arvore: ast.Module) -> list[int]:
    """As linhas em que `_` recebe valor — de qualquer forma."""
    linhas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name) and no.id == "_" and isinstance(
                no.ctx, (ast.Store, ast.Del)):
            linhas.append(no.lineno)
    return sorted(set(linhas))


def test_nenhum_modulo_usa_sublinhado_para_as_duas_coisas():
    culpados = []
    for pasta in PASTAS:
        for arquivo in (RAIZ / pasta).rglob("*.py"):
            if "migrations" in arquivo.parts:
                continue
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            if not _traduz(arvore):
                continue
            culpados += [f"{arquivo.relative_to(RAIZ)}:{n}"
                         for n in _atribuicoes(arvore)]

    assert culpados == [], (
        "`_` está sendo usado como variável num módulo que importa `_` para "
        f"traduzir — a tradução vira `None` dali para a frente: {culpados}")
