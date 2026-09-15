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


# --- Correções da revisão final (15/09/2026) -------------------------------

def test_todas_as_lojas_e_intervalo_podem_ser_escolhidos_de_volta(rede):
    """M5: as opções neutras vinham com `disabled` (o `empty_label` do design
    system), e quem filtrava uma loja não voltava a "Todas as lojas"."""
    import re

    html = _html(logado("sara"), periodo="hoje", loja=str(rede.centro.pk))
    todas = re.search(r'<option[^>]*value=""[^>]*>Todas as lojas</option>', html)
    assert todas and "disabled" not in todas.group(0)


def test_buscar_no_ranking_mantem_periodo_e_loja(rede):
    """M6: a barra de filtro do ranking é um formulário GET que só levava o
    filtro e a ordenação; período e loja sumiam."""
    html = _html(logado("sara"), periodo="mes_passado", loja=str(rede.centro.pk))
    assert '<input type="hidden" name="periodo" value="mes_passado">' in html
    assert f'<input type="hidden" name="loja" value="{rede.centro.pk}">' in html


def test_aplicar_os_filtros_mantem_a_ordenacao_do_ranking(rede):
    html = _html(logado("sara"), periodo="hoje", ordenar="-atendimentos")
    # Duas vezes: a barra do ranking já levava a ordenação; o que faltava era
    # o formulário do período e da loja levar também.
    assert html.count('<input type="hidden" name="ordenar" value="-atendimentos">') == 2


def test_esquecido_leva_a_fila_da_loja_do_item(rede):
    """B7: o link abria a fila da loja da sessão, e não a do esquecido."""
    from fila.models import Presenca

    Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                pessoa=rede.caio,
                                entrada=timezone.now() - timedelta(days=2))
    html = _html(logado("sara"), periodo="hoje")
    assert f"/filial/trocar?filial_id={rede.centro.pk}&amp;voltar=%2Ffila" in html
