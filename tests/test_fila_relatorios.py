"""Os relatórios da fila (spec 2026-09-28-relatorios-da-fila-design).

O cliente: "um relatório que pode ser tirado pelo dono da conta, supervisor
ou gerente, e cada um é focado em uma coisa — o dono de tudo, o supervisor do
que ele é cadastrado, e o gerente no que ele é cadastrado —, diário, semanal,
mensal e mês passado". Todo número sai das contas do painel: se o papel e a
tela discordassem, ninguém saberia em qual acreditar.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import cadastros, logado, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


def local(*args):
    return timezone.make_aware(datetime(*args))


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


def atendimento(rede, pessoa, loja, fim, *, valor=None, motivo="padrao", midia=None,
                itens=()):
    """Um atendimento FECHADO em `fim`. `valor` None é não venda; `motivo=None`
    é a não venda sem motivo (a do ponto esquecido)."""
    from fila.models import Atendimento, ItemVendido, Presenca

    presenca = Presenca.irrestritos.create(empresa=rede.empresa, filial=loja,
                                          pessoa=pessoa, entrada=fim, saida=fim)
    a = Atendimento.irrestritos.create(
        empresa=rede.empresa, filial=loja, vendedor=pessoa, presenca=presenca,
        inicio=fim - timedelta(minutes=5), fim=fim,
        resultado="vendeu" if valor else "nao_vendeu",
        motivo=None if valor else (rede.cad.motivo if motivo == "padrao" else motivo),
        midia=midia, total=Decimal(valor or 0))
    for grupo, v in itens:
        ItemVendido.irrestritos.create(empresa=rede.empresa, atendimento=a,
                                       grupo=grupo, valor=Decimal(v))
    return a


def _recorte(rede, chave="mes", lojas=None, agora=None):
    from fila.indicadores import Recorte
    from fila.relatorio import periodo_escolhido

    return Recorte(rede.empresa, tuple(lojas or (rede.matriz, rede.centro)),
                   periodo_escolhido(chave, agora))


def _secao(relatorio, titulo):
    return next(s for s in relatorio.secoes if s.titulo == titulo)


class TestOPeriodo:
    def test_as_cinco_escolhas_e_o_padrao(self):
        from fila.relatorio import PADRAO, PERIODOS, periodo_escolhido

        assert [c for c, _r in PERIODOS] == ["hoje", "ontem", "7dias", "mes", "mes_passado"]
        assert PADRAO == "mes"
        assert periodo_escolhido("15dias").chave == "mes"
        assert periodo_escolhido(None).chave == "mes"


class TestOConteudo:
    def test_as_secoes_na_ordem(self, rede):
        from fila.relatorio import montar

        r = montar(_recorte(rede), rotulo_da_empresa=str(rede.empresa), gerado_por="Sylvia")
        assert [s.titulo for s in r.secoes] == [
            "Resumo", "Comparação", "Vendedores", "Motivos", "Mídias", "Grupos",
            "Pausas", "Lançamentos"]
        assert r.gerado_por == "Sylvia"
        assert "Matriz" in r.lojas and "Centro" in r.lojas

    def test_o_resumo_bate_com_o_painel(self, rede):
        from fila.indicadores import numeros
        from fila.relatorio import montar

        agora = timezone.now()
        atendimento(rede, rede.ana, rede.matriz, agora, valor="300")
        atendimento(rede, rede.caio, rede.centro, agora)
        recorte = _recorte(rede)
        r = montar(recorte, rotulo_da_empresa=str(rede.empresa), gerado_por="Sylvia")
        total = _secao(r, "Resumo").linhas[0]
        n = numeros(recorte)
        assert total.rotulo == "Total"
        assert (total.numeros.atendimentos, total.numeros.vendas, total.numeros.vendido) == (
            n.atendimentos, n.vendas, n.vendido)
        assert [l.rotulo for l in _secao(r, "Resumo").linhas[1:]] == ["Matriz", "Centro"]

    def test_vendedor_em_duas_lojas_tem_duas_linhas(self, rede):
        from fila.relatorio import montar
        from tests.conftest import alocar

        alocar(rede.ana, rede.empresa, "vendedor", filial=rede.centro)
        agora = timezone.now()
        atendimento(rede, rede.ana, rede.matriz, agora, valor="100")
        atendimento(rede, rede.ana, rede.centro, agora, valor="200")
        r = montar(_recorte(rede), rotulo_da_empresa="x", gerado_por="x")
        linhas = [(l["loja_nome"], l["nome"]) for l in _secao(r, "Vendedores").linhas]
        assert sorted(linhas) == [("Centro", "Ana"), ("Matriz", "Ana")]

    def test_o_pct_da_meta_so_nos_periodos_de_mes(self, rede):
        from fila.relatorio import montar

        agora = timezone.now()
        atendimento(rede, rede.ana, rede.matriz, agora, valor="100")
        for chave, tem in (("mes", True), ("7dias", False), ("hoje", False)):
            r = montar(_recorte(rede, chave), rotulo_da_empresa="x", gerado_por="x")
            rotulos = [c.rotulo for c in _secao(r, "Vendedores").colunas]
            assert ("% da meta" in rotulos) is tem, chave

    def test_a_pausa_da_gestao_fica_fora_da_pausa_do_vendedor(self, rede):
        from fila.models import Pausa, Presenca
        from fila.relatorio import montar

        agora = timezone.now().replace(microsecond=0)
        atendimento(rede, rede.ana, rede.matriz, agora, valor="100")
        presenca = Presenca.irrestritos.filter(pessoa=rede.ana).first()
        inicio = agora - timedelta(hours=2)
        Pausa.irrestritos.create(empresa=rede.empresa, pessoa=rede.ana, filial=rede.matriz,
                                 presenca=presenca, tipo=rede.cad.tipo, inicio=inicio,
                                 fim=inicio + timedelta(minutes=10))
        Pausa.irrestritos.create(empresa=rede.empresa, pessoa=rede.ana, filial=rede.matriz,
                                 presenca=presenca, fixa="gestao",
                                 inicio=inicio + timedelta(minutes=20),
                                 fim=inicio + timedelta(minutes=50))
        # "7dias", e não "hoje": as pausas começam duas horas atrás, e a suíte
        # rodando entre 00:00 e 02:00 as poria no dia anterior.
        r = montar(_recorte(rede, "7dias"), rotulo_da_empresa="x", gerado_por="x")
        ana = next(l for l in _secao(r, "Vendedores").linhas if l["nome"] == "Ana")
        assert ana["pausa"] == timedelta(minutes=10)
        pausas = dict(_secao(r, "Pausas").linhas)
        assert pausas == {"Gestão": 30, "Almoço": 10}

    def test_nao_venda_sem_motivo_no_lancamento(self, rede):
        from fila.relatorio import formatar, montar

        atendimento(rede, rede.ana, rede.matriz, timezone.now(), motivo=None)
        r = montar(_recorte(rede), rotulo_da_empresa="x", gerado_por="x")
        secao = _secao(r, "Lançamentos")
        coluna = next(c for c in secao.colunas if c.rotulo == "Motivo")
        assert formatar(coluna.valor(secao.linhas[0]), coluna.tipo) == "Fechado sem lançamento"

    def test_lancamentos_so_os_fechados_no_periodo(self, rede):
        from fila.indicadores import lancamentos_do_recorte
        from fila.models import Atendimento, Presenca

        agora = timezone.now()
        dentro = atendimento(rede, rede.ana, rede.matriz, agora, valor="100",
                             itens=[(rede.cad.grupo, "100")])
        atendimento(rede, rede.ana, rede.matriz, agora - timedelta(days=70), valor="50")
        presenca = Presenca.irrestritos.filter(pessoa=rede.caio).first() or \
            Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                        pessoa=rede.caio, entrada=agora)
        Atendimento.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                       vendedor=rede.caio, presenca=presenca, inicio=agora)
        assert [a.pk for a in lancamentos_do_recorte(_recorte(rede))] == [dentro.pk]

    def test_a_lista_de_lancamentos_nao_cresce_em_consultas(self, rede):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from fila.relatorio import montar

        agora = timezone.now()

        def medir():
            with CaptureQueriesContext(connection) as c:
                r = montar(_recorte(rede), rotulo_da_empresa="x", gerado_por="x")
                secao = _secao(r, "Lançamentos")
                for linha in secao.linhas:
                    for coluna in secao.colunas:
                        coluna.valor(linha)
            return len(c)

        atendimento(rede, rede.ana, rede.matriz, agora, valor="100",
                    itens=[(rede.cad.grupo, "100")])
        poucas = medir()
        for _i in range(6):
            atendimento(rede, rede.caio, rede.centro, agora, valor="50",
                        itens=[(rede.cad.grupo2, "50")])
        assert medir() <= poucas

    def test_recorte_vazio_sai_com_as_secoes(self, rede):
        from fila.relatorio import montar

        r = montar(_recorte(rede, "hoje"), rotulo_da_empresa="x", gerado_por="x")
        assert len(r.secoes) == 8
        assert _secao(r, "Lançamentos").linhas == []
        assert _secao(r, "Resumo").linhas[0].numeros.atendimentos == 0

    def test_formatar(self):
        from fila.relatorio import formatar

        assert formatar(Decimal("1200"), "dinheiro") == "R$ 1.200,00"
        assert formatar(12.345, "porcento") == "12,3%"
        assert formatar(None, "porcento") == "—"
        assert formatar(timedelta(minutes=90), "minutos") == "90 min"
        assert formatar(3, "inteiro") == "3"
