"""Os indicadores vistos por quem os usa (spec, "Quem vê o quê").

Desde 15/09/2026 o dashboard mora no Início (`/`), abaixo do "Olá", e não mais
numa tela própria: `/fila/indicadores` só redireciona para lá.
"""

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
    resposta = cliente.get("/", params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_quem_nao_tem_relatorios_ve_so_a_saudacao(rede):
    """Representante não traz fila.relatorios: o Início continua sendo só o
    "Olá" com a data."""
    pessoa_na_loja("rita", rede.empresa, rede.centro, cargo="representante")
    html = _html(logado("rita"))
    assert "Olá, Rita!" in html
    assert "Ranking de vendedores" not in html


def test_gestao_ve_o_dashboard_abaixo_da_saudacao(rede):
    html = _html(logado("gil"), periodo="hoje")
    assert html.index("Olá, Gil!") < html.index("Ranking de vendedores")


def test_vendedor_continua_caindo_na_fila(rede):
    resposta = logado("ana").get("/")
    assert resposta.status_code == 302 and resposta["Location"] == reverse("fila")


def test_a_tela_antiga_redireciona_para_o_inicio_com_os_filtros(rede):
    resposta = logado("gil").get("/fila/indicadores?periodo=hoje&ordenar=-vendas")
    assert resposta.status_code == 302
    assert resposta["Location"] == "/?periodo=hoje&ordenar=-vendas"


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


def test_o_menu_nao_tem_mais_o_atalho_dos_indicadores(rede):
    assert 'href="/fila/indicadores"' not in _html(logado("gil"))


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


def test_a_linha_de_comparacao_so_aparece_quando_ha_base(rede):
    """Diagramação do Início (15/09/2026): todo número tem a linha de apoio,
    mas "Comparado a …" embaixo de "Sem base para comparar" se contradiz."""
    from fila.models import Atendimento

    sem_base = _html(logado("sylvia"), periodo="hoje")
    assert "Sem base para comparar" in sem_base
    assert "Comparado a" not in sem_base

    ontem = _venda_hoje(rede, rede.caio, rede.centro, "100")
    Atendimento.irrestritos.filter(pk=ontem.pk).update(
        inicio=ontem.inicio - timedelta(days=1), fim=ontem.fim - timedelta(days=1))
    _venda_hoje(rede, rede.caio, rede.centro, "300")
    # A venda de ontem caiu antes da mesma hora de hoje: é base para "Hoje".
    com_base = _html(logado("sylvia"), periodo="hoje")
    assert "Comparado a" in com_base


# --- Os gráficos desenhados no servidor (15/09/2026) ------------------------
# O `Chart` do design system saiu do Início: o texto escalava com a caixa, o
# eixo cortava o número de cima e a escala de contagem saía "37,50".

def test_escala_redonda_e_inteira_na_contagem():
    from fila.graficos import escala

    assert escala(93_000) == (100_000, 25_000)
    assert escala(37) == (40, 10)
    # Contagem nunca tem marca quebrada: 2,5 vira 5, e não 3.
    assert escala(9, inteiro=True) == (10, 5)
    assert escala(6, inteiro=True) == (6, 2)
    assert escala(2, inteiro=True) == (2, 1)
    assert escala(0) == (4, 1)


def test_dinheiro_curto_do_eixo():
    from fila.graficos import dinheiro_curto

    assert dinheiro_curto(50_000) == "R$ 50 mil"
    assert dinheiro_curto(62_500) == "R$ 62,5 mil"
    assert dinheiro_curto(1_200_000) == "R$ 1,2 mi"
    assert dinheiro_curto(850) == "R$ 850"
    assert dinheiro_curto(0) == "R$ 0"


def test_coluna_sem_valor_fica_vazia_e_a_dica_diz_traco():
    """Conversão de um dia sem atendimento não é uma barra de zero: zero
    diria que a loja atendeu e não vendeu."""
    from fila.graficos import Coluna, colunas

    html = colunas("conversao", "Conversão por dia", [
        Coluna("01", "01/09", 50.0, "50,0%"),
        Coluna("02", "02/09", None, "—"),
    ], marca=str)
    assert '<li class="ind-col borda-e" style="--h: 0.0000%">' in html
    assert "<b>—</b>" in html
    # A marca de cima cobre a maior barra, em passo redondo: 50 em passos
    # de 20 vai até 60, e a barra de 50 fica em cinco sextos.
    assert '<li style="--y: 100.0000%"><span>60</span></li>' in html
    assert 'style="--h: 83.3333%"' in html


def test_lista_ranqueada_mede_a_barra_pelo_maior_e_a_parte_pelo_total():
    from fila.graficos import lista_ranqueada

    html = lista_ranqueada([("Sofás", 300, "R$ 300,00"), ("Mesas", 100, "R$ 100,00")], "venda")
    assert 'width: 100.00%' in html and 'width: 33.33%' in html
    assert ">75%<" in html and ">25%<" in html


def test_o_painel_abre_no_vendido_e_marca_o_dia_em_andamento(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    html = _html(logado("sylvia"), periodo="mes")
    assert '<input type="radio" name="ind-serie" value="vendido" checked>' in html
    assert html.count('name="ind-serie"') == 4
    assert 'class="ind-serie visivel" data-serie="vendido"' in html
    # Hoje é a última coluna do mês em andamento, listrada e com "até agora".
    assert "ind-col agora" in html and "até agora" in html
    assert "<svg" not in html.split("Ranking de vendedores")[0].split("ind-painel")[1]


def test_periodo_terminado_nao_tem_coluna_em_andamento(rede):
    from fila.models import Atendimento

    ontem = _venda_hoje(rede, rede.caio, rede.centro, "100")
    Atendimento.irrestritos.filter(pk=ontem.pk).update(
        inicio=ontem.inicio - timedelta(days=1), fim=ontem.fim - timedelta(days=1))
    # Por hora (um dia só) e por dia (intervalo que acabou ontem): nenhum dos
    # dois caminhos pode listrar a última coluna.
    assert "ind-col agora" not in _html(logado("sylvia"), periodo="ontem")
    ontem_local = timezone.localdate() - timedelta(days=1)
    intervalo = _html(logado("sylvia"), de=str(ontem_local - timedelta(days=3)),
                      ate=str(ontem_local))
    assert "ind-serie" in intervalo and "ind-col agora" not in intervalo


def test_as_listas_dizem_o_total_no_subtitulo(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    html = _html(logado("sylvia"), periodo="hoje")
    assert "1 venda" in html
    assert "0 atendimentos sem venda" in html
