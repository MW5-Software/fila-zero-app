"""A máscara de valor (17/09/2026): o campo de dinheiro só aceita números, e
os centavos empurram ("150000" vira "1.500,00"), como numa maquininha.

A máscara é conveniência: sem JavaScript o campo aceita texto livre, e quem
decide o número é `fila.valores.ler_valor`. Por isso a prova tem duas pontas:
o script formata como o cliente pediu, e tudo o que ele produz o servidor lê
como o mesmo número.
"""

import json
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "fila" / "static" / "fila" / "valor.js"

CASOS = [
    ("", ""),
    ("1", "0,01"),
    ("15", "0,15"),
    ("1500", "15,00"),
    ("150000", "1.500,00"),
    ("12345678", "123.456,78"),
    ("0001", "0,01"),
    ("abc", ""),
    ("0", ""),
    # Colado de um orçamento, ou o valor que o servidor já desenhou.
    ("R$ 1.500,50", "1.500,50"),
    ("1.500,50", "1.500,50"),
]


def _mascarar_no_node(textos):
    if shutil.which("node") is None:
        pytest.skip("sem node no PATH para rodar o script da máscara")
    programa = (
        "global.window = {}; global.document = {addEventListener() {}};"
        f"require({json.dumps(str(SCRIPT))});"
        f"console.log(JSON.stringify({json.dumps(textos)}.map(window.mascararValor)));"
    )
    saida = subprocess.run(["node", "-e", programa], capture_output=True, text=True,
                           check=True, timeout=20)
    return json.loads(saida.stdout)


def test_a_mascara_empurra_os_centavos():
    assert _mascarar_no_node([t for t, _e in CASOS]) == [e for _t, e in CASOS]


@pytest.mark.parametrize("formatado", [e for _t, e in CASOS if e])
def test_o_servidor_le_o_que_a_mascara_produz(formatado):
    from fila.valores import ler_valor

    esperado = Decimal(formatado.replace(".", "").replace(",", "."))
    assert ler_valor(formatado) == esperado


@pytest.mark.django_db
def test_a_folha_de_venda_usa_a_mascara():
    from tests.fila_cenario import cadastros, logado, pessoa_na_loja, sylvia

    empresa, matriz, _titular = sylvia()
    cadastros(empresa)
    pessoa_na_loja("ana", empresa, matriz)
    html = logado("ana").get("/fila?folha=finalizar").content.decode()
    assert 'name="valor" inputmode="numeric" data-valor' in html
    assert "/static/fila/valor.js" in html
