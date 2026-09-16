"""`api.py` e `views*.py` são duas cascas sobre a MESMA regra.

Se uma se apoiar na outra, a regra volta a morar na casca: a API passa a
depender de função que monta HTML, ou a tela passa a depender de schema do
Ninja — e no dia em que uma das duas mudar, a outra quebra ou, pior, diverge
em silêncio. A regra mora em módulo de serviço (`filiais.py`, `contexto.py`,
`entrada.py`), e as duas cascas importam de lá.
"""

from __future__ import annotations

import ast
from pathlib import Path

PASTAS = ("comum", "plataforma", "contas", "modulos")


def _arquivos(aceita) -> list[Path]:
    achados = []
    for pasta in PASTAS:
        for caminho in Path(pasta).rglob("*.py"):
            if "__pycache__" in caminho.parts or "migrations" in caminho.parts:
                continue
            if aceita(caminho.name):
                achados.append(caminho)
    return sorted(achados)


def _importados(caminho: Path) -> set[str]:
    """Todo nome importado, com os pontos do import relativo preservados.

    `from .views_filiais import CAMPOS` vira `.views_filiais` e
    `.views_filiais.CAMPOS`; `from . import views` vira `.views`.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(apelido.name for apelido in no.names)
        elif isinstance(no, ast.ImportFrom):
            base = "." * no.level + (no.module or "")
            nomes.add(base)
            separador = "." if no.module else ""
            nomes.update(f"{base}{separador}{apelido.name}" for apelido in no.names)
    return nomes


def _partes(nome: str) -> list[str]:
    return [parte for parte in nome.split(".") if parte]


def _e_view(nome: str) -> bool:
    return any(p == "views" or p.startswith("views_") for p in _partes(nome))


def _e_api(nome: str) -> bool:
    return "api" in _partes(nome)


def _e_arquivo_de_view(nome: str) -> bool:
    return nome == "views.py" or nome.startswith("views_")


def test_api_nao_importa_view():
    problemas = [f"{caminho}: {nome}"
                 for caminho in _arquivos(lambda n: n == "api.py")
                 for nome in sorted(_importados(caminho)) if _e_view(nome)]
    assert not problemas, (
        f"api.py importando view: {problemas}. Tire a regra da view para um "
        f"módulo de serviço e importe de lá nas duas cascas.")


def test_view_nao_importa_api():
    problemas = [f"{caminho}: {nome}"
                 for caminho in _arquivos(_e_arquivo_de_view)
                 for nome in sorted(_importados(caminho)) if _e_api(nome)]
    assert not problemas, f"view importando api: {problemas}"


def test_a_varredura_enxerga_as_duas_pontas():
    """Uma varredura que não acha arquivo nenhum passa sempre — e ensina que
    está tudo certo."""
    assert _arquivos(lambda n: n == "api.py"), "nenhum api.py encontrado"
    assert _arquivos(_e_arquivo_de_view), "nenhuma view encontrada"


def test_api_py_nao_adia_as_anotacoes():
    """`from __future__ import annotations` num `api.py` quebra toda operação
    com guarda e corpo: a anotação vira texto, o Ninja a resolve pelos
    `__globals__` da função embrulhada — os do módulo da guarda —, não acha o
    schema e passa a ler o corpo como query string. Achado em 15/09/2026, na
    primeira operação que tinha as duas coisas (`plataforma.api.trocar_filial`),
    com 500 em todo POST."""
    problemas = []
    for caminho in _arquivos(lambda n: n == "api.py"):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        for no in arvore.body:
            if isinstance(no, ast.ImportFrom) and no.module == "__future__" and \
                    any(apelido.name == "annotations" for apelido in no.names):
                problemas.append(str(caminho))
    assert not problemas, f"api.py com anotação adiada: {problemas}"
