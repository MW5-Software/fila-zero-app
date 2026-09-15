"""A tela de indicadores vista por quem a usa (spec, "Quem vê o quê")."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import cadastros, logado, nova_loja, pessoa_na_loja, sylvia

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
        sara=pessoa_na_loja("sara", empresa, None, cargo="supervisor"),
        cad=cadastros(empresa))


def _venda_hoje(rede, pessoa, loja, valor):
    from fila.models import Atendimento, Presenca

    agora = timezone.now()
    presenca = Presenca.irrestritos.create(empresa=rede.empresa, filial=loja,
                                          pessoa=pessoa, entrada=agora, saida=agora)
    return Atendimento.irrestritos.create(
        empresa=rede.empresa, filial=loja, vendedor=pessoa, presenca=presenca,
        inicio=agora - timedelta(minutes=5), fim=agora, resultado="vendeu",
        total=Decimal(valor))


def _html(cliente, **params):
    resposta = cliente.get(reverse("fila_indicadores"), params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_vendedor_nao_tem_a_tela(rede):
    assert logado("ana").get(reverse("fila_indicadores")).status_code == 404


def test_gerente_ve_so_a_loja_dele_e_a_forjada_e_descartada(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.ana, rede.matriz, "9000")
    gil = logado("gil")
    html = _html(gil, periodo="hoje")
    assert "Caio" in html and "Ana" not in html
    assert "R$ 700,00" in html
    forjada = _html(gil, periodo="hoje", loja=str(rede.matriz.pk))
    assert "Ana" not in forjada and "R$ 9.000,00" not in forjada


def test_supervisor_ve_todas_e_filtra_por_loja(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.ana, rede.matriz, "300")
    sara = logado("sara")
    assert "R$ 1.000,00" in _html(sara, periodo="hoje")
    so_matriz = _html(sara, periodo="hoje", loja=str(rede.matriz.pk))
    assert "R$ 300,00" in so_matriz and "Caio" not in so_matriz


def test_titular_ve_a_empresa(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    assert "Caio" in _html(logado("sylvia"), periodo="hoje")


def test_ranking_tem_filtro_ordenacao_e_paginacao(rede):
    from tests.test_regra_tabela import (
        _MARCADOR_FILTRO, _MARCADOR_PAGINACAO, _PADRAO_CABECALHO_ORDENAVEL)

    _venda_hoje(rede, rede.caio, rede.centro, "700")
    html = _html(logado("sylvia"), periodo="hoje")
    assert "<table" in html
    assert _MARCADOR_FILTRO in html and _MARCADOR_PAGINACAO in html
    assert _PADRAO_CABECALHO_ORDENAVEL.search(html)


def test_aviso_de_esquecidos(rede):
    from fila.models import Presenca

    Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                pessoa=rede.caio,
                                entrada=timezone.now() - timedelta(days=2))
    html = _html(logado("gil"), periodo="hoje")
    assert "Presença aberta" in html
    assert "Caio" in html


def test_sem_atendimento_mostra_traco_e_nao_zero_por_cento(rede):
    html = _html(logado("sylvia"), periodo="hoje")
    assert "0%" not in html
    assert "—" in html


def test_periodo_invalido_nao_estoura(rede):
    assert "Este mês" in _html(logado("sylvia"), de="2026-99-99", ate="x")


def test_menu_mostra_o_atalho_para_o_gerente_e_nao_para_o_vendedor(rede):
    assert 'href="/fila/indicadores"' in logado("gil").get("/").content.decode()
    ana = logado("ana").get("/fila").content.decode()
    assert 'href="/fila/indicadores"' not in ana
