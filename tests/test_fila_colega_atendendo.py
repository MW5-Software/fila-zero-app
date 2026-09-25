"""O 2º e o 3º da fila põem o 1º em atendimento (25/09/2026, pedido do cliente).

"Se o cara que é o primeiro da fila foi atender e esqueceu de mexer no
sistema, o segundo e o terceiro podem colocar ele em atendimento via botão."
Quem está logo atrás é quem vê que o primeiro já está com um cliente, e é quem
fica travado esperando a vez que não anda.

- só o 2º e o 3º da fila, e só sobre quem é o 1º AGORA — conferido de novo na
  hora de gravar, sob a trava da loja;
- o 1º passa a atender como se tivesse tocado em "Vou atender";
- fica no histórico da loja quem pôs, porque é uma ação sobre outra pessoa.
"""

import pytest
from django.urls import reverse

from tests.fila_cenario import (  # noqa: F401  (relogio é fixture)
    cadastros, logado, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    from types import SimpleNamespace

    from fila.acoes import bater_ponto

    empresa, matriz, titular = sylvia()
    loja = SimpleNamespace(
        empresa=empresa, matriz=matriz,
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        caio=pessoa_na_loja("caio", empresa, matriz),
        dora=pessoa_na_loja("dora", empresa, matriz),
        cad=cadastros(empresa))
    for pessoa in (loja.ana, loja.bia, loja.caio, loja.dora):
        bater_ponto(pessoa, matriz)
    return loja


def _estado(pessoa):
    from fila.models import LugarNaFila

    return LugarNaFila.irrestritos.get(pessoa=pessoa).estado


@pytest.mark.parametrize("quem", ["bia", "caio"])
def test_o_segundo_e_o_terceiro_poem_o_primeiro_em_atendimento(loja, quem):
    from fila.acoes import colega_atendendo
    from fila.models import Atendimento, CorrecaoNaFila

    colega_atendendo(getattr(loja, quem), loja.matriz, loja.ana.pk)

    assert _estado(loja.ana) == "atendendo"
    atendimento = Atendimento.irrestritos.get(vendedor=loja.ana, fim__isnull=True)
    assert atendimento.cliente_pediu is False
    correcao = CorrecaoNaFila.irrestritos.latest("pk")
    assert (correcao.acao, correcao.autor_id, correcao.pessoa_id) == (
        "colega", getattr(loja, quem).pk, loja.ana.pk)


def test_o_quarto_nao_pode(loja):
    from fila.acoes import Recusa, colega_atendendo

    with pytest.raises(Recusa, match="Só o 2º e o 3º"):
        colega_atendendo(loja.dora, loja.matriz, loja.ana.pk)
    assert _estado(loja.ana) == "na_fila"


def test_so_sobre_quem_e_o_primeiro_agora(loja):
    from fila.acoes import Recusa, colega_atendendo

    with pytest.raises(Recusa, match="não é mais o 1º"):
        colega_atendendo(loja.caio, loja.matriz, loja.bia.pk)
    assert _estado(loja.bia) == "na_fila"


def test_quem_nao_esta_na_fila_nao_pode(loja):
    from fila.acoes import Recusa, colega_atendendo, pausar

    pausar(loja.bia, loja.matriz, loja.cad.tipo.pk)
    # Bia saiu da fila: Caio virou o 2º, e Bia não está mais nela.
    with pytest.raises(Recusa):
        colega_atendendo(loja.bia, loja.matriz, loja.ana.pk)
    assert _estado(loja.ana) == "na_fila"


def test_o_botao_aparece_so_para_o_segundo_e_o_terceiro(loja):
    marcador = 'data-folha="colega_atendendo"'
    assert marcador in logado("bia").get(reverse("fila")).content.decode()
    assert marcador in logado("caio").get(reverse("fila")).content.decode()
    assert marcador not in logado("dora").get(reverse("fila")).content.decode()
    assert marcador not in logado("ana").get(reverse("fila")).content.decode()


def test_pela_pagina(loja):
    logado("bia").post(reverse("fila_agir"), {
        "acao": "colega_atendendo", "pessoa": str(loja.ana.pk)})
    assert _estado(loja.ana) == "atendendo"
