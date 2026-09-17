"""A tela do histórico das correções (spec 2026-09-17, C5)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.fila_cenario import logado, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


@pytest.fixture
def rede():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    centro = nova_loja(empresa, "Centro")
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, centro=centro, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        caio=pessoa_na_loja("caio", empresa, centro),
        gil=pessoa_na_loja("gil", empresa, centro, cargo="gerente"),
        sara=pessoa_na_loja("sara", empresa, None, cargo="supervisor"))


def _correcao(rede, loja, pessoa, autor, observacao, acao="mover", quando=None):
    from fila.models import CorrecaoNaFila

    return CorrecaoNaFila.irrestritos.create(
        empresa=rede.empresa, filial=loja, pessoa=pessoa, autor=autor, acao=acao,
        observacao=observacao, detalhe="de 2º para 1º",
        momento=quando or timezone.now())


def _html(cliente, **params):
    resposta = cliente.get("/fila/historico", params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_vendedor_nao_abre(rede):
    assert logado("caio").get("/fila/historico").status_code == 404


def test_gerente_ve_so_a_loja_dele_e_a_forjada_cai_na_dele(rede):
    _correcao(rede, rede.centro, rede.caio, rede.gil, "chegou antes")
    _correcao(rede, rede.matriz, rede.ana, rede.sara, "foi ao banco")
    gil = logado("gil")
    html = _html(gil)
    assert "chegou antes" in html and "foi ao banco" not in html
    assert "foi ao banco" not in _html(gil, loja=str(rede.matriz.pk))


def test_supervisor_ve_todas_as_lojas(rede):
    _correcao(rede, rede.centro, rede.caio, rede.gil, "chegou antes")
    _correcao(rede, rede.matriz, rede.ana, rede.sara, "foi ao banco")
    html = _html(logado("sara"), loja="todas")
    assert "chegou antes" in html and "foi ao banco" in html


def test_periodo_padrao_e_hoje(rede):
    _correcao(rede, rede.centro, rede.caio, rede.gil, "de hoje")
    _correcao(rede, rede.centro, rede.caio, rede.gil, "da semana passada",
              quando=timezone.now() - timedelta(days=8))
    gil = logado("gil")
    html = _html(gil)
    assert "de hoje" in html and "da semana passada" not in html
    assert "da semana passada" in _html(gil, periodo="30dias")


def test_colunas_filtro_e_acao_por_extenso(rede):
    from tests.test_regra_tabela import (
        _MARCADOR_FILTRO, _MARCADOR_PAGINACAO, _PADRAO_CABECALHO_ORDENAVEL)

    _correcao(rede, rede.centro, rede.caio, rede.gil, "chegou antes")
    html = _html(logado("gil"))
    assert _MARCADOR_FILTRO in html and _MARCADOR_PAGINACAO in html
    assert _PADRAO_CABECALHO_ORDENAVEL.search(html)
    assert "Mudou de posição" in html and "de 2º para 1º" in html
    filtrado = _html(logado("gil"), **{"f:observacao:contem": "banco"})
    assert "chegou antes" not in filtrado


def test_a_pagina_da_fila_tem_o_link_so_para_a_gestao(rede):
    gil = logado("gil")
    assert 'href="/fila/historico"' in gil.get("/fila").content.decode()
    assert 'href="/fila/historico"' not in logado("caio").get("/fila").content.decode()
