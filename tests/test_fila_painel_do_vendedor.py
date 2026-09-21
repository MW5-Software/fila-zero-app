"""O painel do vendedor no Início, visto por ele (spec 2026-09-16)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from tests.fila_cenario import cadastros, logado, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        gil=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        cad=cadastros(empresa))


def _atendimento(loja, pessoa, valor=None, filial=None, motivo=None, grupo=None):
    """Um atendimento fechado agora. `valor` None é não venda."""
    from fila.models import Atendimento, ItemVendido, Presenca

    agora = timezone.now()
    filial = filial or loja.matriz
    presenca = Presenca.irrestritos.create(empresa=loja.empresa, filial=filial,
                                          pessoa=pessoa, entrada=agora, saida=agora)
    a = Atendimento.irrestritos.create(
        empresa=loja.empresa, filial=filial, vendedor=pessoa, presenca=presenca,
        inicio=agora - timedelta(minutes=5), fim=agora,
        resultado="vendeu" if valor else "nao_vendeu",
        motivo=None if valor else (motivo or loja.cad.motivo),
        total=Decimal(valor or 0))
    if valor and grupo:
        ItemVendido.irrestritos.create(empresa=loja.empresa, atendimento=a,
                                       grupo=grupo, valor=Decimal(valor))
    return a


def _html(cliente, **params):
    resposta = cliente.get("/", params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def _antes_do_ranking(html):
    return html.split('data-ind="ranking-da-loja"')[0]


def test_o_vendedor_ve_o_painel_dele_abaixo_da_saudacao(loja):
    html = _html(logado("ana"), periodo="hoje")
    assert html.index("Olá, Ana!") < html.index('data-ind="painel"')
    assert 'data-ind="ranking-da-loja"' in html
    assert 'data-ind="ranking"' not in html


def test_os_numeros_as_listas_e_o_grafico_sao_so_dele(loja):
    _atendimento(loja, loja.ana, "300", grupo=loja.cad.grupo)
    _atendimento(loja, loja.bia, "7000", grupo=loja.cad.grupo2)
    antes = _antes_do_ranking(_html(logado("ana"), periodo="hoje"))
    assert "R$ 300,00" in antes
    assert "R$ 7.000,00" not in antes and "R$ 7.300,00" not in antes
    assert "Sofás" in antes and "Tapetes" not in antes


def test_so_a_loja_do_cabecalho(loja):
    from contas.models import Alocacao, Cargo
    from plataforma.contexto import CHAVE

    centro = nova_loja(loja.empresa, "Centro")
    Alocacao.objects.create(pessoa=loja.ana, empresa=loja.empresa, filial=centro,
                            cargo=Cargo.objects.get(conta_id=loja.empresa.conta_id,
                                                    nome="vendedor"))
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.ana, "900", filial=centro)
    ana = logado("ana")
    for filial, aparece, some in ((loja.matriz, "R$ 300,00", "R$ 900,00"),
                                  (centro, "R$ 900,00", "R$ 300,00")):
        sessao = ana.session
        sessao[CHAVE] = filial.pk
        sessao.save()
        antes = _antes_do_ranking(_html(ana, periodo="hoje"))
        assert aparece in antes and some not in antes
        assert str(filial) in antes
    assert 'name="loja"' not in _html(ana, periodo="hoje")


def test_o_ranking_nao_mostra_o_que_e_do_gerente(loja):
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.bia, "500")
    ranking = _html(logado("ana"), periodo="hoje").split('data-ind="ranking-da-loja"')[1]
    for coluna in ("Vendido", "Vendas", "Conversão", "Posição"):
        assert coluna in ranking
    for coluna in ("Pausa", "Ticket médio", "Cliente pediu", "Atendimentos"):
        assert f">{coluna}<" not in ranking
    assert "Bia" in ranking and "R$ 500,00" in ranking


def test_a_posicao_e_por_vendido_mesmo_reordenado(loja):
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.bia, "500")
    _atendimento(loja, loja.bia)
    _atendimento(loja, loja.bia)
    # Por conversão, Ana (100%) vem antes de Bia (33%), mas Bia continua 1ª.
    html = _html(logado("ana"), periodo="hoje", ordenar="-conversao")
    ranking = html.split('data-ind="ranking-da-loja"')[1]
    assert ranking.index("Ana") < ranking.index("Bia")
    assert "Você está em 2º de 2." in html
    linha_da_ana = ranking.split("Ana")[0].rsplit("<tr", 1)[1]
    assert "2º" in linha_da_ana


def test_ordenar_por_pausa_nao_vale_para_o_vendedor(loja):
    """A coluna não existe para ele; a URL forjada cai na ordem padrão."""
    _atendimento(loja, loja.ana, "300")
    html = _html(logado("ana"), periodo="hoje", ordenar="-pausa")
    assert 'data-ind="ranking-da-loja"' in html


def test_a_linha_dele_vem_marcada(loja):
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.bia, "500")
    ranking = _html(logado("ana"), periodo="hoje").split('data-ind="ranking-da-loja"')[1]
    marcada = ranking.split('aria-current="true"')[1].split("</tr>")[0]
    assert "Ana" in marcada and "Bia" not in marcada
    assert ranking.count('aria-current="true"') == 1


def test_quem_nao_fechou_atendimento_ve_a_frase_e_nenhuma_linha_marcada(loja):
    _atendimento(loja, loja.bia, "500")
    html = _html(logado("ana"), periodo="hoje")
    assert "Você não fechou atendimento no período." in html
    assert 'aria-current="true"' not in html.split('data-ind="ranking-da-loja"')[1]


def test_o_ranking_tem_filtro_e_paginacao_e_sem_cabecalho_clicavel(loja):
    """A emenda à R46 de 18/09/2026 vale para o ranking do vendedor também: a
    posição é sempre pelo vendido, e o cabeçalho clicável convidava a ordenar
    por outra coisa."""
    from tests.test_regra_tabela import (
        _MARCADOR_FILTRO, _MARCADOR_PAGINACAO, _PADRAO_CABECALHO_ORDENAVEL)

    _atendimento(loja, loja.ana, "300")
    html = _html(logado("ana"), periodo="hoje")
    assert _MARCADOR_FILTRO in html and _MARCADOR_PAGINACAO in html
    assert not _PADRAO_CABECALHO_ORDENAVEL.search(html)


def test_buscar_no_ranking_nao_muda_a_posicao(loja):
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.bia, "500")
    ranking = _html(logado("ana"), periodo="hoje", **{"f:nome:contem": "Ana"}).split(
        'data-ind="ranking-da-loja"')[1]
    assert "Bia" not in ranking.split("</form>", 1)[-1]
    assert "2º" in ranking


def test_a_meta_dele_aparece_so_no_mes_e_nao_a_da_loja(loja):
    from fila.metas import primeiro_do_mes
    from fila.models import MetaDeVenda

    mes = primeiro_do_mes(timezone.localdate())
    _atendimento(loja, loja.ana, "250")
    MetaDeVenda.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                   pessoa=None, mes=mes, valor=Decimal("90000"))
    ana = logado("ana")
    assert 'data-ind="meta"' not in _html(ana, periodo="mes")
    MetaDeVenda.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                   pessoa=loja.ana, mes=mes, valor=Decimal("1000"))
    html = _html(ana, periodo="mes")
    assert 'data-ind="meta"' in html and "Faltam R$ 750,00" in html
    assert "R$ 90.000,00" not in _antes_do_ranking(html)
    assert "lojas com meta" not in html and "metas dos vendedores" not in html
    assert 'data-ind="meta"' not in _html(ana, periodo="7dias")
    assert "% da meta" in _html(ana, periodo="mes")
    # O ranking é do mês desde 17/09/2026: a coluna vale em qualquer período.
    assert "% da meta" in _html(ana, periodo="hoje")


def test_sem_esquecidos_no_painel_do_vendedor(loja):
    from fila.models import Presenca

    Presenca.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                pessoa=loja.bia,
                                entrada=timezone.now() - timedelta(days=2))
    assert "Ficou aberto de um dia para o outro" not in _html(logado("ana"), periodo="hoje")


def test_o_gerente_continua_com_o_painel_da_gestao(loja):
    html = _html(logado("gil"), periodo="hoje")
    assert 'data-ind="ranking"' in html and 'data-ind="ranking-da-loja"' not in html


def test_quem_so_ve_a_fila_recebe_a_saudacao(loja):
    from tests.conftest import alocar, cargo_com

    rui = pessoa_na_loja("rui", loja.empresa, loja.matriz)
    alocar(rui, loja.empresa, cargo_com(loja.empresa, "fila.ver", nome="so-ve",
                                        alcance="filial"), filial=loja.matriz)
    html = _html(logado("rui"))
    assert "Olá, Rui!" in html and 'data-ind="painel"' not in html


def test_vendedor_sem_loja_recebe_a_saudacao_e_nao_500(loja):
    from contas.models import Alocacao

    Alocacao.objects.filter(pessoa=loja.ana).delete()
    html = _html(logado("ana"))
    assert "Olá, Ana!" in html and 'data-ind="painel"' not in html


def test_sem_atendimento_mostra_traco(loja):
    html = _html(logado("ana"), periodo="hoje")
    assert "Nenhum atendimento fechado no período." in html


def test_o_ranking_da_loja_e_a_posicao_sao_do_mes(loja):
    """17/09/2026: em "Hoje", a posição dizia o lugar de hoje, e o vendedor
    lia como o do mês. Agora o ranking tem o próprio mês."""
    from datetime import timedelta

    from django.utils import timezone

    from fila.models import Atendimento

    antigo = _atendimento(loja, loja.bia, "900")
    fim = timezone.localtime().replace(day=1, hour=12) - timedelta(days=1)
    Atendimento.irrestritos.filter(pk=antigo.pk).update(inicio=fim, fim=fim)
    _atendimento(loja, loja.ana, "100")
    ranking = _html(logado("ana"), periodo="mes_passado").split('data-ind="ranking-da-loja"')[1]
    assert "Você está em 1º de 1." in ranking
    assert "Bia" not in ranking
