"""Os indicadores vistos por quem os usa (spec, "Quem vê o quê").

Desde 15/09/2026 o dashboard mora no Início (`/`), abaixo do "Olá", e não mais
numa tela própria: `/fila/indicadores` só redireciona para lá.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
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
    assert 'data-ind="ranking"' not in html


def test_gestao_ve_o_dashboard_abaixo_da_saudacao(rede):
    html = _html(logado("gil"), periodo="hoje")
    assert html.index("Olá, Gil!") < html.index('data-ind="ranking"')


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


def test_supervisor_escolhe_todas_as_lojas_e_filtra_por_loja(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.ana, rede.matriz, "300")
    sara = logado("sara")
    assert "R$ 1.000,00" in _html(sara, periodo="hoje", loja="todas")
    so_centro = _html(sara, periodo="hoje", loja=str(rede.centro.pk))
    assert "R$ 700,00" in so_centro and "Ana" not in so_centro


# --- A loja do cabeçalho (17/09/2026) ---------------------------------------
# O painel somava todas as lojas quando a URL não dizia a loja, e o ranking da
# Sylvia na Matriz mostrava o vendedor do Centro como se fosse da Matriz.

def _na_loja(cliente, loja):
    from plataforma.contexto import CHAVE

    sessao = cliente.session
    sessao[CHAVE] = loja.pk
    sessao.save()
    return cliente


def test_titular_ve_a_loja_do_cabecalho(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.ana, rede.matriz, "300")
    na_matriz = _html(logado("sylvia"), periodo="hoje")
    assert "Ana" in na_matriz and "Caio" not in na_matriz
    assert "R$ 700,00" not in na_matriz
    no_centro = _html(_na_loja(logado("sylvia"), rede.centro), periodo="hoje")
    assert "Caio" in no_centro and "Ana" not in no_centro


def test_gerente_de_duas_lojas_ve_a_do_cabecalho(rede):
    from tests.conftest import alocar

    alocar(rede.gil, rede.empresa, "gerente", filial=rede.matriz)
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.ana, rede.matriz, "300")
    html = _html(_na_loja(logado("gil"), rede.centro), periodo="hoje")
    assert "Caio" in html and "Ana" not in html
    assert "Ana" in _html(_na_loja(logado("gil"), rede.matriz), periodo="hoje")


def test_todas_as_lojas_mostra_a_loja_de_cada_linha(rede):
    import re

    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.caio, rede.matriz, "200")
    html = _html(logado("sylvia"), periodo="hoje", loja="todas")
    ranking = html[html.index('data-ind="ranking"'):]
    assert re.search(r"<th[^>]*>\s*Loja", ranking)
    linhas = re.findall(r"<tr[^>]*>(.*?)</tr>", ranking, re.S)
    do_caio = [l for l in linhas if "Caio" in l]
    assert len(do_caio) == 2
    assert any("Centro" in l and "R$ 700,00" in l for l in do_caio)
    assert any("Matriz" in l and "R$ 200,00" in l for l in do_caio)


def test_o_bloco_por_loja_so_aparece_em_todas_as_lojas(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    todas = _html(logado("sylvia"), periodo="hoje", loja="todas")
    assert 'data-ind="por-loja"' in todas
    assert "Centro" in todas[todas.index('data-ind="por-loja"'):]
    assert 'data-ind="por-loja"' not in _html(logado("sylvia"), periodo="hoje")


def test_uma_loja_nao_tem_coluna_de_loja(rede):
    import re

    _venda_hoje(rede, rede.ana, rede.matriz, "300")
    html = _html(logado("sylvia"), periodo="hoje")
    assert not re.search(r"<th[^>]*>\s*Loja", html)


def test_gerente_de_uma_loja_nao_ganha_todas_as_lojas(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.ana, rede.matriz, "9000")
    html = _html(logado("gil"), periodo="hoje", loja="todas")
    assert "Caio" in html and "Ana" not in html
    assert 'data-ind="por-loja"' not in html


def test_ranking_tem_filtro_e_paginacao_e_sem_cabecalho_clicavel(rede):
    """R46 com a emenda de 18/09/2026: o cliente pediu as tabelas sem a
    ordenação por coluna, e o ranking é a primeira delas. O filtro por coluna e
    a paginação continuam — e é isso que este teste cobra."""
    from tests.test_regra_tabela import (
        _MARCADOR_FILTRO, _MARCADOR_PAGINACAO, _PADRAO_CABECALHO_ORDENAVEL)

    _venda_hoje(rede, rede.caio, rede.centro, "700")
    html = _html(logado("sylvia"), periodo="hoje", loja=str(rede.centro.pk))
    assert "<table" in html
    assert _MARCADOR_FILTRO in html and _MARCADOR_PAGINACAO in html
    assert not _PADRAO_CABECALHO_ORDENAVEL.search(html)


def test_aviso_de_esquecidos(rede):
    from fila.models import Presenca

    Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                pessoa=rede.caio,
                                entrada=timezone.now() - timedelta(days=2))
    html = _html(logado("gil"), periodo="hoje")
    # "Presença", e não "Presença aberta": o título do aviso já diz que ficou
    # aberto, e a frase inteira se repetia em cada linha.
    assert "Presença" in html
    assert "Caio" in html


def test_o_aviso_de_esquecidos_vem_antes_dos_filtros(rede):
    """18/09/2026, pedido do cliente: o aviso é a PRIMEIRA coisa da tela.

    Ele estava entre os filtros e os resultados, e ali ficava no caminho de
    quem só queria trocar o período — além de parecer mais um bloco do painel
    de números. Em cima, ele é a pendência que a gestão lê ao abrir o Início.
    """
    from fila.models import Presenca

    Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                pessoa=rede.caio,
                                entrada=timezone.now() - timedelta(days=2))
    html = _html(logado("gil"), periodo="hoje")
    assert (html.index("data-esquecidos") < html.index('data-ind="filtros"')
            < html.index('data-ind="painel"'))


def test_o_aviso_agrupa_por_loja_e_por_pessoa(rede):
    """Cinco pendências davam cinco linhas com o mesmo nome de loja e cinco
    vezes o mesmo link. Agora a loja aparece uma vez, com um link só, e a
    pessoa uma vez, com o que ficou aberto ao lado."""
    from fila.models import Atendimento, Presenca

    anteontem = timezone.now() - timedelta(days=2)
    do_caio = Presenca.irrestritos.create(
        empresa=rede.empresa, filial=rede.centro, pessoa=rede.caio,
        entrada=anteontem)
    Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                pessoa=rede.gil, entrada=anteontem)
    Atendimento.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                   vendedor=rede.caio, presenca=do_caio,
                                   inicio=anteontem)
    # O aviso é o único lugar da página com esses dois textos, então contar no
    # HTML inteiro conta dentro dele.
    html = _html(logado("sara"), periodo="hoje", loja="todas")

    assert html.count("Abrir a fila desta loja") == 1, "um link por loja"
    assert html.count("<b>Caio</b>") == 1, "uma linha por pessoa"
    assert "Presença, Atendimento" in html
    assert "2 pessoas com pendência em 1 loja" in html


def test_sem_atendimento_mostra_traco_e_nao_zero_por_cento(rede):
    html = _html(logado("sylvia"), periodo="hoje")
    assert "0%" not in html
    assert "—" in html


def test_periodo_invalido_nao_estoura(rede):
    assert "Este mês" in _html(logado("sylvia"), de="2026-99-99", ate="x", periodo="x")


def test_o_menu_nao_tem_mais_o_atalho_dos_indicadores(rede):
    assert 'href="/fila/indicadores"' not in _html(logado("gil"))


# --- Correções da revisão final (15/09/2026) -------------------------------

def test_todas_as_lojas_e_intervalo_podem_ser_escolhidos_de_volta(rede):
    """M5: as opções neutras vinham com `disabled` (o `empty_label` do design
    system), e quem filtrava uma loja não voltava a "Todas as lojas"."""
    import re

    html = _html(logado("sara"), periodo="hoje", loja=str(rede.centro.pk))
    todas = re.search(r'<option[^>]*value="todas"[^>]*>Todas as lojas</option>', html)
    assert todas and "disabled" not in todas.group(0)


def test_buscar_no_ranking_mantem_periodo_e_loja(rede):
    """M6: a barra de filtro do ranking é um formulário GET que só levava o
    filtro e a ordenação; período e loja sumiam."""
    html = _html(logado("sara"), periodo="mes_passado", loja=str(rede.centro.pk))
    assert '<input type="hidden" name="periodo" value="mes_passado">' in html
    assert f'<input type="hidden" name="loja" value="{rede.centro.pk}">' in html


def test_o_seletor_do_mes_entra_na_linha_do_cabecalho(rede):
    """O `.form` do design system espaça os filhos em coluna (`.form > * + *`
    põe 20px em cima de cada um), e o seletor do mês entra na LINHA do
    cabeçalho do cartão: sem zerar a margem de TODOS os filhos, o "Abrir" cai
    20px abaixo do campo. Zerar só o `.f` foi o primeiro jeito, e era o
    defeito — este teste lê a folha da tela e cobra o `> *`."""
    from pathlib import Path

    folha = Path("fila/static/fila/indicadores.css").read_text(encoding="utf-8")
    assert '[data-ind="mes-do-ranking"] > * { margin-top: 0; }' in folha


def test_os_dois_formularios_do_ranking_levam_um_o_filtro_do_outro(rede):
    """M6 para o par que o seletor de mês criou (18/09/2026): a barra de
    filtros leva o mês do ranking, e o formulário do mês leva período e loja.
    Sem os dois, aplicar um filtro devolvia o outro ao padrão."""
    mes = f"{_mes_passado():%Y-%m}"
    html = _html(logado("sara"), periodo="mes_passado",
                 loja=str(rede.centro.pk), ranking_mes=mes)
    assert f'<input type="hidden" name="ranking_mes" value="{mes}">' in html

    formulario = html[html.index('data-ind="mes-do-ranking"'):]
    formulario = formulario[:formulario.index("</form>")]
    assert '<input type="hidden" name="periodo" value="mes_passado">' in formulario
    assert f'<input type="hidden" name="loja" value="{rede.centro.pk}">' in formulario


def test_esquecido_leva_a_fila_da_loja_do_item(rede):
    """B7: o link abria a fila da loja da sessão, e não a do esquecido."""
    from fila.models import Presenca

    Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                pessoa=rede.caio,
                                entrada=timezone.now() - timedelta(days=2))
    html = _html(logado("sara"), periodo="hoje", loja="todas")
    assert f"/filial/trocar?filial_id={rede.centro.pk}&amp;voltar=%2Ffila" in html


def test_a_linha_de_comparacao_so_aparece_quando_ha_base(rede):
    """Diagramação do Início (15/09/2026): todo número tem a linha de apoio,
    mas "Comparado a …" embaixo de "Sem base para comparar" se contradiz."""
    from fila.models import Atendimento

    sem_base = _html(logado("sylvia"), periodo="hoje", loja=str(rede.centro.pk))
    assert "Sem base para comparar" in sem_base
    assert "Comparado a" not in sem_base

    ontem = _venda_hoje(rede, rede.caio, rede.centro, "100")
    Atendimento.irrestritos.filter(pk=ontem.pk).update(
        inicio=ontem.inicio - timedelta(days=1), fim=ontem.fim - timedelta(days=1))
    _venda_hoje(rede, rede.caio, rede.centro, "300")
    # A venda de ontem caiu antes da mesma hora de hoje: é base para "Hoje".
    com_base = _html(logado("sylvia"), periodo="hoje", loja=str(rede.centro.pk))
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
    html = _html(logado("sylvia"), periodo="mes", loja=str(rede.centro.pk))
    assert '<input type="radio" name="ind-serie" value="vendido" checked>' in html
    assert html.count('name="ind-serie"') == 4
    assert 'class="ind-serie visivel" data-serie="vendido"' in html
    # Hoje é a última coluna do mês em andamento, listrada e com "até agora".
    assert "ind-col agora" in html and "até agora" in html
    assert "<svg" not in html.split('data-ind="ranking"')[0].split("ind-painel")[1]


def test_periodo_terminado_nao_tem_coluna_em_andamento(rede):
    from fila.models import Atendimento

    ontem = _venda_hoje(rede, rede.caio, rede.centro, "100")
    Atendimento.irrestritos.filter(pk=ontem.pk).update(
        inicio=ontem.inicio - timedelta(days=1), fim=ontem.fim - timedelta(days=1))
    # Por hora (um dia só) e por dia (intervalo que acabou ontem): nenhum dos
    # dois caminhos pode listrar a última coluna.
    assert "ind-col agora" not in _html(logado("sylvia"), periodo="ontem", loja=str(rede.centro.pk))
    passado = _venda_hoje(rede, rede.caio, rede.centro, "100")
    fim_do_mes_passado = timezone.localtime().replace(day=1, hour=12) - timedelta(days=1)
    Atendimento.irrestritos.filter(pk=passado.pk).update(
        inicio=fim_do_mes_passado - timedelta(minutes=5), fim=fim_do_mes_passado)
    mes_passado = _html(logado("sylvia"), periodo="mes_passado", loja=str(rede.centro.pk))
    assert "ind-serie" in mes_passado and "ind-col agora" not in mes_passado


def test_as_listas_dizem_o_total_no_subtitulo(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    html = _html(logado("sylvia"), periodo="hoje", loja=str(rede.centro.pk))
    assert "1 venda" in html
    assert "0 atendimentos sem venda" in html


# --- A meta no painel e no ranking (entrega 3) -------------------------------

def _meta_da_loja(rede, loja, valor, pessoa=None):
    from fila.metas import primeiro_do_mes
    from fila.models import MetaDeVenda

    return MetaDeVenda.irrestritos.create(
        empresa=rede.empresa, filial=loja, pessoa=pessoa,
        mes=primeiro_do_mes(timezone.localdate()), valor=Decimal(valor))


def test_a_faixa_da_meta_aparece_no_mes_e_some_em_7_dias(rede):
    _meta_da_loja(rede, rede.centro, "1000")
    _venda_hoje(rede, rede.caio, rede.centro, "250")
    gil = logado("gil")
    mes = _html(gil, periodo="mes")
    assert 'data-ind="meta"' in mes and "25,0%" in mes and "Faltam R$ 750,00" in mes
    assert 'data-ind="meta"' not in _html(gil, periodo="7dias")


def test_todas_as_lojas_diz_quantas_tem_meta(rede):
    _meta_da_loja(rede, rede.centro, "1000")
    _meta_da_loja(rede, rede.centro, "600", pessoa=rede.caio)
    html = _html(logado("sara"), periodo="mes", loja="todas")
    assert "1 de 2 lojas com meta" in html
    assert "As metas dos vendedores somam R$ 600,00, abaixo da meta da loja." in html


def test_ranking_ganha_meta_e_porcentagem_ordenaveis(rede):
    _meta_da_loja(rede, rede.centro, "1000", pessoa=rede.caio)
    _venda_hoje(rede, rede.caio, rede.centro, "500")
    html = _html(logado("gil"), periodo="mes", ordenar="-pct_meta")
    assert "% da meta" in html and "50,0%" in html
    # O ranking é do mês desde 17/09/2026: a meta vale em qualquer período.
    assert "% da meta" in _html(logado("gil"), periodo="hoje")


def test_os_filtros_tem_os_atalhos_e_nao_tem_mais_de_e_ate(rede):
    """17/09/2026: o período é só por atalho (hoje a 90 dias e os dois meses);
    os campos De/Até saíram."""
    html = _html(logado("sylvia"), periodo="90dias")
    assert 'name="de"' not in html and 'name="ate"' not in html
    # "Últimos 90 dias" desde 18/09/2026: "90 dias" sozinho não dizia se eram
    # os que passaram ou os que vêm.
    assert '<option value="90dias" selected>Últimos 90 dias</option>' in html
    assert "Últimos 90 dias, Matriz" in html


# --- O ranking é do mês (17/09/2026) ----------------------------------------
# O ranking seguia o período do painel, e em "7 dias" ninguém sabia de quando
# era a posição. Agora ele tem o próprio mês, com as setas.

def _ranking(html):
    return html[html.index('data-ind="ranking"'):]


def _nome_do_mes(dia):
    from nucleo.views import _MESES

    return f"{_MESES[dia.month - 1]} de {dia.year}"


def _mes_passado():
    return timezone.localdate().replace(day=1) - timedelta(days=1)


def _para_o_mes_passado(atendimento):
    from fila.models import Atendimento

    fim = timezone.localtime().replace(day=1, hour=12) - timedelta(days=1)
    Atendimento.irrestritos.filter(pk=atendimento.pk).update(
        inicio=fim - timedelta(minutes=5), fim=fim)


def test_o_ranking_e_do_mes_e_nao_do_periodo(rede):
    _para_o_mes_passado(_venda_hoje(rede, rede.caio, rede.centro, "500"))
    _venda_hoje(rede, rede.gil, rede.centro, "80")
    html = _html(logado("gil"), periodo="mes_passado")
    assert "R$ 500,00" in html[:html.index('data-ind="ranking"')]
    ranking = _ranking(html)
    assert f"Ranking de {_nome_do_mes(timezone.localdate())}" in ranking
    assert "Caio" not in ranking and "Gil" in ranking


def test_o_seletor_do_mes_leva_ao_mes_passado_sem_perder_os_filtros(rede):
    """As setas viraram lista (18/09/2026): o mês passado é uma OPÇÃO, e o
    formulário dela leva o período e a loja de agora — e não a página, porque a
    página de outro mês pode nem existir."""
    _para_o_mes_passado(_venda_hoje(rede, rede.caio, rede.centro, "500"))
    mes = f"{_mes_passado():%Y-%m}"
    atual = _ranking(_html(logado("sara"), periodo="7dias",
                           loja=str(rede.centro.pk), pagina="2"))
    assert f'<option value="{mes}"' in atual, "o mês passado não está na lista"

    formulario = atual[atual.index('data-ind="mes-do-ranking"'):]
    formulario = formulario[:formulario.index("</form>")]
    assert '<input type="hidden" name="periodo" value="7dias">' in formulario
    assert f'<input type="hidden" name="loja" value="{rede.centro.pk}">' in formulario
    assert "pagina=" not in formulario

    passado = _ranking(_html(logado("sara"), periodo="7dias",
                             loja=str(rede.centro.pk), ranking_mes=mes))
    assert f"Ranking de {_nome_do_mes(_mes_passado())}" in passado
    assert f'<option value="{mes}" selected>' in passado
    assert "Caio" in passado and "R$ 500,00" in passado


def test_mes_futuro_ou_invalido_cai_no_mes_atual(rede):
    atual = f"Ranking de {_nome_do_mes(timezone.localdate())}"
    for mes in ("2999-01", "abc", "2026-13"):
        assert atual in _html(logado("gil"), ranking_mes=mes)


def test_o_seletor_do_mes_nao_oferece_mes_futuro(rede):
    """Mês que não começou não tem posição — e na lista ele nem aparece como
    opção, em vez de ser uma seta que some."""
    futuro = (timezone.localdate().replace(day=1) + timedelta(days=32))
    ranking = _ranking(_html(logado("gil")))
    assert 'aria-label="Mês do ranking"' in ranking
    assert f'<option value="{timezone.localdate():%Y-%m}" selected>' in ranking
    assert f'value="{futuro:%Y-%m}"' not in ranking


# --- Várias empresas na conta (spec 2026-09-17, E5) --------------------------

@pytest.fixture
def duas_empresas(rede):
    """A conta da Sylvia com uma segunda empresa, cada uma com a sua loja e o
    seu vendedor."""
    from types import SimpleNamespace

    from plataforma.models import Empresa, Filial

    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=rede.titular)
    loja_beta = Filial.objects.get(empresa=beta, e_matriz=True)
    return SimpleNamespace(
        rede=rede, alfa=rede.empresa, beta=beta,
        loja_alfa=rede.matriz, loja_beta=loja_beta,
        elis=pessoa_na_loja("elis", beta, loja_beta))


def _venda_em(empresa, pessoa, loja, valor):
    from fila.models import Atendimento, Presenca

    agora = timezone.now()
    presenca = Presenca.irrestritos.create(empresa=empresa, filial=loja,
                                           pessoa=pessoa, entrada=agora,
                                           saida=agora)
    return Atendimento.irrestritos.create(
        empresa=empresa, filial=loja, vendedor=pessoa, presenca=presenca,
        inicio=agora - timedelta(minutes=5), fim=agora, resultado="vendeu",
        total=Decimal(valor))


def _na_empresa(cliente, empresa):
    from plataforma.contexto import CHAVE_EMPRESA

    sessao = cliente.session
    sessao[CHAVE_EMPRESA] = empresa.pk
    sessao.save()
    return cliente


def test_o_painel_abre_na_empresa_do_cabecalho(duas_empresas):
    d = duas_empresas
    _venda_em(d.alfa, d.rede.ana, d.loja_alfa, "300")
    _venda_em(d.beta, d.elis, d.loja_beta, "700")
    # Com `loja=todas`, quem recorta é a EMPRESA do cabeçalho: sem ela, as
    # lojas das duas entrariam e o teste passaria pela loja, não pela empresa.
    na_alfa = _html(_na_empresa(logado("sylvia"), d.alfa), periodo="hoje",
                    loja="todas")
    assert "R$ 300,00" in na_alfa
    assert "Elis" not in na_alfa and "R$ 700,00" not in na_alfa
    na_beta = _html(_na_empresa(logado("sylvia"), d.beta), periodo="hoje",
                    loja="todas")
    assert "R$ 700,00" in na_beta and "Ana" not in na_beta


def test_todas_as_empresas_soma_e_separa(duas_empresas):
    d = duas_empresas
    _venda_em(d.alfa, d.rede.ana, d.loja_alfa, "300")
    _venda_em(d.beta, d.elis, d.loja_beta, "700")
    html = _html(logado("sylvia"), periodo="hoje", empresa="todas", loja="todas")
    assert "R$ 1.000,00" in html
    por_empresa = html[html.index('data-ind="por-empresa"'):]
    assert "Beta" in por_empresa
    ranking = _ranking(html)
    assert "Ana" in ranking and "Elis" in ranking


def test_o_campo_de_empresa_so_aparece_para_quem_alcanca_mais_de_uma(duas_empresas):
    d = duas_empresas
    com_duas = _html(logado("sylvia"), periodo="hoje")
    assert 'name="empresa"' in com_duas
    # O gerente do Centro alcança uma empresa só: para ele o campo não existe.
    assert 'name="empresa"' not in _html(logado("gil"), periodo="hoje")


def test_empresa_forjada_nao_amplia_o_recorte(duas_empresas):
    from plataforma.models import Empresa

    from tests.conftest import abrir_conta

    d = duas_empresas
    alheia = Empresa.objects.create(razao_social="De Outro Cliente Ltda")
    abrir_conta(alheia, "outro-dono")
    html = _html(logado("sylvia"), periodo="hoje", empresa=str(alheia.pk))
    assert "De Outro Cliente" not in html


def test_lojas_de_mesmo_nome_dizem_a_empresa(duas_empresas):
    """Cada empresa nasce com a SUA Matriz: em "Todas as empresas", duas
    linhas "Matriz" não diriam de qual delas são."""
    d = duas_empresas
    _venda_em(d.alfa, d.rede.ana, d.loja_alfa, "300")
    _venda_em(d.beta, d.elis, d.loja_beta, "700")
    html = _html(logado("sylvia"), periodo="hoje", empresa="todas", loja="todas")
    por_loja = html[html.index('data-ind="por-loja"'):html.index('data-ind="por-empresa"')]
    assert "Matriz · Beta Ltda" in por_loja
    ranking = _ranking(html)
    assert "Matriz · Beta Ltda" in ranking
