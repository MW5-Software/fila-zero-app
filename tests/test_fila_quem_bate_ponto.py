"""Quem bate ponto é quem atende (18/09/2026, pedido do cliente).

O ponto é a porta da fila, e a fila é de quem está no salão atendendo. O
supervisor, o gerente e o dono da conta não atendem, e por isso não entram na
fila. Eles continuam abrindo a fila, corrigindo e lendo os números: o que sai é
só a participação.

**A regra mora em `fila.tela.atende`**, e não na ausência de `fila.participar`:
`contas.lugar.pode_dar` exige que quem aloca tenha as permissões do cargo que
concede, e um gerente sem `fila.participar` deixaria de poder cadastrar
Vendedor. O teste que guarda essa razão está no fim deste arquivo — sem ele,
"limpar a permissão do gerente" pareceria a arrumação óbvia.

**Quem TRANCA é a rota, não a tela.** `fila.views.agir` recusa a ação `ponto`
para quem não atende, e é isso que este arquivo prova: o botão some da tela e o
POST forjado toma 404 — a mesma regra de duas camadas do resto da casa
("esconder item de menu nunca é proteção").
"""

from types import SimpleNamespace

import pytest
from django.urls import reverse

from tests.conftest import email_de
from tests.fila_cenario import (  # noqa: F401
    cadastros, logado, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        sara=pessoa_na_loja("sara", empresa, matriz, cargo="supervisor"),
        gil=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        cad=cadastros(empresa))


def _ponto(login):
    return logado(login).post(reverse("fila_agir"), {"acao": "ponto"})


def _na_fila() -> set:
    """Quem está na loja. `irrestritos` porque `objects` é o manager do
    inquilino, e fora de uma requisição ele responde vazio — a lista vazia que
    faria este arquivo inteiro passar sem provar nada."""
    from fila.models import LugarNaFila

    return set(LugarNaFila.irrestritos.values_list("pessoa__email", flat=True))


def test_o_vendedor_bate_ponto(loja):
    """O outro lado da regra: sem este, tirar o ponto de todo mundo passaria no
    teste, e a loja abriria sem ninguém conseguir entrar na fila."""
    assert _ponto("ana").status_code == 302
    assert _na_fila() == {email_de("ana")}


def test_o_gerente_nao_bate_ponto(loja):
    assert _ponto("gil").status_code == 404
    assert _na_fila() == set()


def test_o_supervisor_nao_bate_ponto(loja):
    assert _ponto("sara").status_code == 404
    assert _na_fila() == set()


def test_o_dono_da_conta_nao_bate_ponto(loja):
    assert _ponto("sylvia").status_code == 404
    assert _na_fila() == set()


def test_a_tela_do_gerente_nao_oferece_o_ponto(loja):
    """A tela e a rota dizem a mesma coisa: o botão não aparece para quem
    tomaria 404 se apertasse."""
    html = logado("gil").get(reverse("fila")).content.decode()
    assert "Bater o ponto" not in html
    assert "Entrar na fila" not in html


def test_o_gerente_continua_corrigindo_quem_esta_na_fila(loja):
    """Corrigir não é atender: o que o gerente perdeu foi o ponto, e não a
    loja. Sem esta prova, uma "simplificação" futura que amarrasse a correção
    à participação tiraria dele o trabalho inteiro."""
    from fila.models import LugarNaFila

    assert _ponto("ana").status_code == 302
    ana = LugarNaFila.irrestritos.get().pessoa
    resposta = logado("gil").post(reverse("fila_agir"), {
        "acao": "tirar", "pessoa": str(ana.pk), "resultado": "nao_vendeu",
        "motivo": str(loja.cad.motivo.pk), "motivo_da_correcao": "foi embora"})
    assert resposta.status_code == 302
    assert _na_fila() == set()


def test_o_dono_da_conta_continua_abrindo_a_fila_e_os_indicadores(loja):
    """Ele deixa de atender, e não de gerir: a fila abre para ele (leitura e
    correção) e o Início continua sendo o painel da gestão."""
    assert logado("sylvia").get(reverse("fila")).status_code == 200
    assert logado("sylvia").get(reverse("inicio")).status_code == 200


def test_o_gerente_continua_podendo_cadastrar_vendedor(loja):
    """A razão de a regra NÃO ser "tirar `fila.participar` do cargo".

    `pode_dar` exige que quem aloca tenha todas as permissões do cargo que
    concede (`contas/lugar.py`). Sem `fila.participar` no cargo do Gerente, ele
    deixaria de poder conceder o cargo de Vendedor, e a conta nova ficaria sem
    vendedor nenhum. Quem "arrumar" a regra tirando a permissão vê vermelho
    aqui.
    """
    from contas.lugar import pode_dar
    from contas.models import Cargo

    vendedor = Cargo.objects.get(conta_id=loja.empresa.conta_id, nome="vendedor")
    assert pode_dar(loja.gil, loja.empresa, loja.matriz, vendedor) is True