"""A meta da loja distribuída AO VIVO (18/09/2026, pedido do cliente).

O cliente digitava a meta da loja e só via a meta dos vendedores depois de
salvar. Agora o valor aparece enquanto ele digita — quem faz isso é
`fila/static/fila/metas.js`, e o servidor continua fazendo a MESMA conta ao
salvar (`fila/metas._distribuir`), que é a rede de quem está sem JavaScript.

Este arquivo prova as duas pontas que dá para provar sem navegador:

- **a conta do script é a mesma do servidor** — o `.js` roda no node e o
  resultado é comparado com `fila.metas.repartir`, como
  `tests/test_fila_mascara_de_valor.py` faz com a máscara. Duas contas que
  divergem dariam um número na tela e outro no banco;
- **a tela entrega ao script o que ele precisa** para saber quem está na loja
  (`data-na-loja`) e qual campo é o da meta da loja (`data-campo-loja`).
"""

import json
import shutil
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parent.parent / "fila" / "static" / "fila"
          / "metas.js")

#: `(centavos, partes)`: o centavo que não divide vai para as primeiras.
CASOS = [(10000, 3), (1, 3), (9000000, 2), (123457, 7), (100, 1), (5, 4),
         (99999999, 13)]


def _repartir_no_node(centavos: int, partes: int) -> list:
    if shutil.which("node") is None:
        pytest.skip("sem node no PATH para rodar o script das metas")
    programa = (
        # O mínimo para o script carregar: ele sai cedo sem `[data-metas]`, e a
        # conta que interessa é pendurada no `window` antes disso.
        "global.window = {};"
        "global.document = {querySelector() { return null; },"
        " addEventListener() {}};"
        f"require({json.dumps(str(SCRIPT))});"
        f"console.log(JSON.stringify(window.repartirMetas({centavos}, {partes})));"
    )
    saida = subprocess.run(["node", "-e", programa], capture_output=True,
                           text=True, check=True, timeout=20)
    return [Decimal(c) / 100 for c in json.loads(saida.stdout)]


@pytest.mark.parametrize("centavos, partes", CASOS)
def test_a_conta_do_script_e_a_mesma_do_servidor(centavos, partes):
    from fila.metas import repartir

    do_script = _repartir_no_node(centavos, partes)

    assert do_script == repartir(Decimal(centavos) / 100, partes)
    assert sum(do_script) == Decimal(centavos) / 100, "a loja ficou descoberta"


@pytest.mark.django_db
def test_a_tela_entrega_ao_script_quem_esta_na_loja():
    """`data-na-loja` é o que impede o script de dar parte a quem já saiu da
    loja, e `data-campo-loja` é o que separa o campo da meta da loja dos campos
    dos vendedores — só ele dispara a distribuição."""
    from tests.fila_cenario import logado, nova_loja, pessoa_na_loja, sylvia

    from fila.models import MetaDeVenda

    empresa, matriz, titular = sylvia()
    pessoa_na_loja("ana", empresa, matriz)
    centro = nova_loja(empresa, "Centro")
    caio = pessoa_na_loja("caio", empresa, centro)
    # Caio tem meta na Matriz e hoje está no Centro: ele aparece na lista da
    # Matriz, e é justamente quem NÃO pode receber parte da meta de lá.
    MetaDeVenda.irrestritos.create(empresa=empresa, filial=matriz, pessoa=caio,
                                   mes=date(2026, 9, 1), valor=Decimal("500"))
    html = logado("sylvia").get("/fila/metas").content.decode()

    assert "data-campo-loja" in html
    assert 'data-na-loja="1"' in html
    assert 'data-na-loja="0"' in html, "quem saiu da loja tem de estar marcado"
    assert "/static/fila/metas.js" in html