"""As contas dos indicadores (spec, "As regras de cálculo").

Cada cenário grava atendimentos com hora conhecida, direto nos models: o que
se prova aqui é a CONTA, e a fila tem os testes dela.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from fila.indicadores import (Posicao, Recorte, esquecidos, lojas_com_relatorio,
                              motivos, numeros, pausa_por_tipo, por_dia,
                              por_grupo, posicoes_por_vendido, variacao)
from fila.periodo import Periodo
from tests.fila_cenario import cadastros, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


def local(*args):
    return timezone.make_aware(datetime(*args))


SETEMBRO = Periodo(local(2026, 9, 1), local(2026, 10, 1), "intervalo", "setembro")


@pytest.fixture
def loja():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(empresa=empresa, matriz=matriz, titular=titular,
                           ana=pessoa_na_loja("ana", empresa, matriz),
                           bia=pessoa_na_loja("bia", empresa, matriz),
                           cad=cadastros(empresa))


def _presenca(loja, pessoa, filial=None):
    from fila.models import Presenca

    return Presenca.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, pessoa=pessoa,
        entrada=local(2026, 9, 1, 8), saida=local(2026, 9, 30, 18))


def atendimento(loja, pessoa, inicio, fim, *, vendeu=None, motivo=None,
                pediu=False, filial=None, itens=()):
    """Grava um atendimento. `vendeu` é o total; `itens` são (grupo, valor)."""
    from fila.models import Atendimento, ItemVendido

    a = Atendimento.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, vendedor=pessoa,
        presenca=_presenca(loja, pessoa, filial), inicio=inicio, fim=fim,
        cliente_pediu=pediu,
        resultado="" if fim is None else ("vendeu" if vendeu is not None else "nao_vendeu"),
        motivo=None if vendeu is not None or fim is None else (motivo or loja.cad.motivo),
        total=Decimal(vendeu or 0))
    for grupo, valor in itens:
        ItemVendido.irrestritos.create(empresa=loja.empresa, atendimento=a,
                                       grupo=grupo, valor=Decimal(valor))
    return a


def _recorte(loja, periodo=SETEMBRO, lojas=None):
    return Recorte(loja.empresa, tuple(lojas or [loja.matriz]), periodo)


def test_os_numeros_do_periodo(loja):
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d + timedelta(minutes=20), vendeu="1000")
    atendimento(loja, loja.ana, d, d + timedelta(minutes=30), vendeu="500", pediu=True)
    atendimento(loja, loja.bia, d, d + timedelta(minutes=10))
    atendimento(loja, loja.bia, d, d + timedelta(minutes=10), pediu=True)
    n = numeros(_recorte(loja))
    assert (n.atendimentos, n.vendas, n.vendido) == (4, 2, Decimal("1500"))
    assert n.conversao == 50.0
    assert n.ticket == Decimal("750")
    assert (n.pediu, n.vendas_pediu, n.conversao_pediu) == (2, 1, 50.0)


def test_conta_pelo_fim_e_nao_pelo_inicio(loja):
    # Uma asserção por caso: os dois juntos dão 1 pelo fim E pelo início, e o
    # teste passaria com a regra trocada.
    atendimento(loja, loja.ana, local(2026, 8, 31, 23, 50),
                local(2026, 9, 1, 0, 10), vendeu="100")
    assert numeros(_recorte(loja)).atendimentos == 1
    atendimento(loja, loja.ana, local(2026, 9, 30, 23, 50),
                local(2026, 10, 1, 0, 10), vendeu="100")
    assert numeros(_recorte(loja)).atendimentos == 1


def test_aberto_nao_conta(loja):
    atendimento(loja, loja.ana, local(2026, 9, 10, 10), None)
    assert numeros(_recorte(loja)).atendimentos == 0


def test_sem_atendimento_conversao_e_ticket_sao_nada(loja):
    n = numeros(_recorte(loja))
    assert (n.conversao, n.ticket, n.conversao_pediu) == (None, None, None)


def test_outra_loja_e_outra_empresa_nao_entram(loja):
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    centro = nova_loja(loja.empresa, "Centro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="100", filial=centro)
    outra = Empresa.objects.create(razao_social="Concorrente", nome_fantasia="C")
    abrir_conta(outra, "concorrente")
    outra.refresh_from_db()
    assert numeros(_recorte(loja)).atendimentos == 0
    assert numeros(Recorte(outra, (loja.matriz,), SETEMBRO)).atendimentos == 0
    assert numeros(_recorte(loja, lojas=[loja.matriz, centro])).atendimentos == 1


def test_numeros_de_um_vendedor(loja):
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="100")
    atendimento(loja, loja.bia, d, d, vendeu="300")
    assert numeros(_recorte(loja), vendedor=loja.bia).vendido == Decimal("300")


def test_correcao_muda_o_numero(loja):
    from fila.models import Atendimento

    d = local(2026, 9, 10, 10)
    a = atendimento(loja, loja.ana, d, d, vendeu="100")
    Atendimento.irrestritos.filter(pk=a.pk).update(total=Decimal("250"))
    assert numeros(_recorte(loja)).vendido == Decimal("250")


def test_variacao():
    assert variacao(120, 100).valor == 20.0
    assert variacao(120, 100).unidade == "%"
    assert variacao(80, 100).sobe is False
    assert variacao(10, 0) is None
    assert variacao(None, 50) is None
    pontos = variacao(24.0, 20.0, pontos=True)
    assert (pontos.valor, pontos.unidade) == (4.0, "p.p.")


def test_por_grupo_inclui_grupo_desativado(loja):
    from fila.models import GrupoDeItem

    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="900",
                itens=[(loja.cad.grupo, "600"), (loja.cad.grupo2, "300")])
    GrupoDeItem.irrestritos.filter(pk=loja.cad.grupo.pk).update(ativo=False)
    assert por_grupo(_recorte(loja)) == [("Sofás", Decimal("600")),
                                         ("Tapetes", Decimal("300"))]


def test_motivos(loja):
    from fila.models import MotivoDeNaoVenda

    caro = MotivoDeNaoVenda.irrestritos.create(empresa=loja.empresa, nome="Caro")
    d = local(2026, 9, 10, 10)
    for m in (caro, caro, loja.cad.motivo):
        atendimento(loja, loja.ana, d, d, motivo=m)
    assert motivos(_recorte(loja)) == [("Caro", 2), ("Só olhando", 1)]


def test_pausa_fechada_cortada_nas_bordas(loja):
    from fila.models import Pausa

    presenca = _presenca(loja, loja.ana)
    Pausa.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                             pessoa=loja.ana, presenca=presenca, tipo=loja.cad.tipo,
                             inicio=local(2026, 9, 10, 23, 40),
                             fim=local(2026, 9, 11, 0, 20))
    Pausa.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                             pessoa=loja.bia, presenca=_presenca(loja, loja.bia),
                             tipo=loja.cad.tipo, inicio=local(2026, 9, 11, 9))
    dia_11 = Periodo(local(2026, 9, 11), local(2026, 9, 12), "intervalo", "11")
    assert pausa_por_tipo(_recorte(loja, dia_11)) == [("Almoço", 20)]


def test_por_dia_preenche_os_dias_vazios(loja):
    atendimento(loja, loja.ana, local(2026, 9, 1, 10), local(2026, 9, 1, 10), vendeu="100")
    atendimento(loja, loja.ana, local(2026, 9, 3, 10), local(2026, 9, 3, 10))
    tres_dias = Periodo(local(2026, 9, 1), local(2026, 9, 4), "intervalo", "1 a 3")
    assert por_dia(_recorte(loja, tres_dias)) == [
        ("01/09", 1, Decimal("100"), 1), ("02/09", 0, Decimal("0"), 0),
        ("03/09", 1, Decimal("0"), 0)]


def test_por_dia_de_um_dia_so_e_por_hora(loja):
    atendimento(loja, loja.ana, local(2026, 9, 1, 10), local(2026, 9, 1, 10, 5), vendeu="100")
    um_dia = Periodo(local(2026, 9, 1), local(2026, 9, 2), "hoje", "Hoje")
    linhas = por_dia(_recorte(loja, um_dia))
    assert len(linhas) == 24
    assert linhas[10] == ("10h", 1, Decimal("100"), 1)


def test_esquecidos_so_o_que_virou_o_dia(loja):
    from fila.models import Presenca

    agora = local(2026, 9, 15, 11)
    Presenca.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                pessoa=loja.ana, entrada=local(2026, 9, 14, 9))
    Presenca.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                pessoa=loja.bia, entrada=local(2026, 9, 15, 9))
    atendimento(loja, loja.titular, local(2026, 9, 14, 17), None)
    lista = esquecidos(loja.empresa, [loja.matriz], agora)
    assert sorted((e.o_que, e.nome) for e in lista) == [
        ("Atendimento aberto", "sylvia@teste.com"), ("Presença aberta", "Ana")]


def test_lojas_com_relatorio_pelo_alcance(loja):
    centro = nova_loja(loja.empresa, "Centro")
    gil = pessoa_na_loja("gil", loja.empresa, centro, cargo="gerente")
    sara = pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    assert lojas_com_relatorio(gil, loja.empresa) == [centro]
    assert set(lojas_com_relatorio(sara, loja.empresa)) == {loja.matriz, centro}
    assert set(lojas_com_relatorio(loja.titular, loja.empresa)) == {loja.matriz, centro}
    assert lojas_com_relatorio(loja.ana, loja.empresa) == []


def test_ranking_e_de_quem_atendeu_e_nao_de_quem_fechou(loja):
    from fila.indicadores import ranking

    d = local(2026, 9, 10, 10)
    a = atendimento(loja, loja.ana, d, d, vendeu="400")
    a.fechado_por = loja.bia
    a.save(update_fields=["fechado_por"])
    linhas = {p.pk: p for p in ranking(_recorte(loja))}
    assert set(linhas) == {loja.ana.pk}
    assert linhas[loja.ana.pk].vendido == Decimal("400")


def test_ranking_anota_as_colunas(loja):
    from fila.indicadores import ranking
    from fila.models import Pausa

    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="300")
    atendimento(loja, loja.ana, d, d, vendeu="100", pediu=True)
    atendimento(loja, loja.ana, d, d)
    atendimento(loja, loja.ana, d, d)
    Pausa.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                             pessoa=loja.ana, presenca=_presenca(loja, loja.ana),
                             tipo=loja.cad.tipo, inicio=local(2026, 9, 10, 12),
                             fim=local(2026, 9, 10, 12, 45))
    ana = ranking(_recorte(loja)).get(pk=loja.ana.pk)
    assert (ana.atendimentos, ana.vendas, ana.vendido, ana.pediu) == (4, 2, Decimal("400"), 1)
    assert type(ana.atendimentos) is int
    assert ana.conversao == 50.0
    assert ana.ticket == Decimal("200")
    assert ana.pausa == timedelta(minutes=45)


def test_ranking_ordena_por_vendido_e_soma_entre_lojas(loja):
    from fila.indicadores import PADRAO_DO_RANKING, ORDENAVEIS_DO_RANKING, ranking

    centro = nova_loja(loja.empresa, "Centro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="300")
    atendimento(loja, loja.ana, d, d, vendeu="300", filial=centro)
    atendimento(loja, loja.bia, d, d, vendeu="500")
    campos = tuple(f"-{c}" for c in ORDENAVEIS_DO_RANKING[PADRAO_DO_RANKING.lstrip("-")])
    ordem = ranking(_recorte(loja, lojas=[loja.matriz, centro])).order_by(*campos)
    assert [p.pk for p in ordem] == [loja.ana.pk, loja.bia.pk]


def test_posicao_no_mes_com_empate(loja):
    from fila.indicadores import posicao_no_mes

    caio = pessoa_na_loja("caio", loja.empresa, loja.matriz)
    agora = local(2026, 9, 20, 12)
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="500")
    atendimento(loja, loja.bia, d, d, vendeu="500")
    atendimento(loja, caio, d, d, vendeu="900")
    atendimento(loja, caio, local(2026, 8, 30, 10), local(2026, 8, 30, 10), vendeu="9999")
    # Quem só teve não venda no mês não entra na conta do "de N".
    dora = pessoa_na_loja("dora", loja.empresa, loja.matriz)
    atendimento(loja, dora, d, d)
    assert posicao_no_mes(caio, loja.matriz, agora) == Posicao(1, 3)
    assert posicao_no_mes(loja.ana, loja.matriz, agora) == Posicao(2, 3)
    assert posicao_no_mes(loja.bia, loja.matriz, agora) == Posicao(2, 3)


def test_posicao_sem_venda_no_mes(loja):
    from fila.indicadores import posicao_no_mes

    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d)
    assert posicao_no_mes(loja.ana, loja.matriz, local(2026, 9, 20)) is None


def test_esquecido_mostra_a_hora_local(loja):
    """B1: a hora do aviso saía em UTC (21:30 em São Paulo virava 00:30)."""
    from fila.models import Presenca
    from fila.views_indicadores import _desde

    presenca = Presenca.irrestritos.create(
        empresa=loja.empresa, filial=loja.matriz, pessoa=loja.ana,
        entrada=local(2026, 9, 14, 21, 30))
    presenca.refresh_from_db()
    assert _desde(presenca.entrada) == "14/09 21:30"


def test_versao_muda_quando_um_lancamento_de_hoje_e_corrigido(loja):
    """B6: a correção do gerente não mexia na fila, e as outras telas não
    viam o lançamento novo."""
    from fila.estado import versao_da_fila
    from fila.models import Atendimento

    agora = timezone.now()
    a = atendimento(loja, loja.ana, agora - timedelta(minutes=5), agora, vendeu="1500")
    antes = versao_da_fila(loja.matriz)
    Atendimento.irrestritos.filter(pk=a.pk).update(total=Decimal("150"))
    assert versao_da_fila(loja.matriz) != antes


# --- Recortado pelo vendedor (spec 2026-09-16) --------------------------------

def test_as_contas_de_um_vendedor_so_trazem_as_dele(loja):
    from fila.models import MotivoDeNaoVenda, Pausa

    caro = MotivoDeNaoVenda.irrestritos.create(empresa=loja.empresa, nome="Caro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="600", itens=[(loja.cad.grupo, "600")])
    atendimento(loja, loja.bia, d, d, vendeu="300", itens=[(loja.cad.grupo2, "300")])
    atendimento(loja, loja.ana, d, d, motivo=caro)
    atendimento(loja, loja.bia, d, d)
    for pessoa, minutos in ((loja.ana, 10), (loja.bia, 30)):
        Pausa.irrestritos.create(
            empresa=loja.empresa, filial=loja.matriz, pessoa=pessoa,
            presenca=_presenca(loja, pessoa), tipo=loja.cad.tipo,
            inicio=local(2026, 9, 10, 12), fim=local(2026, 9, 10, 12, minutos))
    r = _recorte(loja)
    assert por_grupo(r, vendedor=loja.ana) == [("Sofás", Decimal("600"))]
    assert motivos(r, vendedor=loja.ana) == [("Caro", 1)]
    assert pausa_por_tipo(r, vendedor=loja.ana) == [("Almoço", 10)]
    dia = Periodo(local(2026, 9, 10), local(2026, 9, 11), "intervalo", "10")
    assert por_dia(_recorte(loja, dia), vendedor=loja.ana)[10] == ("10h", 2, Decimal("600"), 1)
    # Sem vendedor, a loja inteira, como sempre foi.
    assert por_grupo(r) == [("Sofás", Decimal("600")), ("Tapetes", Decimal("300"))]
    assert pausa_por_tipo(r) == [("Almoço", 40)]


def test_posicoes_por_vendido_com_empate_e_quem_nao_vendeu(loja):
    caio = pessoa_na_loja("caio", loja.empresa, loja.matriz)
    dora = pessoa_na_loja("dora", loja.empresa, loja.matriz)
    d = local(2026, 9, 10, 10)
    atendimento(loja, caio, d, d, vendeu="900")
    atendimento(loja, loja.ana, d, d, vendeu="500")
    atendimento(loja, loja.bia, d, d, vendeu="500")
    atendimento(loja, dora, d, d)  # atendeu e não vendeu: entra, em último
    assert posicoes_por_vendido(_recorte(loja)) == {
        caio.pk: 1, loja.ana.pk: 2, loja.bia.pk: 2, dora.pk: 4}


def test_posicoes_so_do_recorte(loja):
    centro = nova_loja(loja.empresa, "Centro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="100")
    atendimento(loja, loja.bia, d, d, vendeu="999", filial=centro)
    assert posicoes_por_vendido(_recorte(loja)) == {loja.ana.pk: 1}


def test_ranking_por_loja_separa_a_pessoa_em_cada_loja(loja):
    """17/09/2026: em "Todas as lojas", quem vendeu na Matriz e no Centro
    aparecia numa linha só, somada, e sem dizer a loja — o vendedor do Centro
    parecia estar na Matriz. Agora é uma linha por pessoa em cada loja, e a
    pausa também é a daquela loja."""
    from fila.indicadores import ranking_por_loja
    from fila.models import Pausa

    centro = nova_loja(loja.empresa, "Centro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="300")
    atendimento(loja, loja.ana, d, d, vendeu="200", filial=centro)
    atendimento(loja, loja.ana, d, d, filial=centro)
    atendimento(loja, loja.bia, d, d, vendeu="500")
    Pausa.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                             pessoa=loja.ana, presenca=_presenca(loja, loja.ana),
                             tipo=loja.cad.tipo, inicio=local(2026, 9, 10, 12),
                             fim=local(2026, 9, 10, 12, 45))
    linhas = {(l.pk, l.loja_id): l
              for l in ranking_por_loja(_recorte(loja, lojas=[loja.matriz, centro]))}
    assert set(linhas) == {(loja.ana.pk, loja.matriz.pk), (loja.ana.pk, centro.pk),
                           (loja.bia.pk, loja.matriz.pk)}
    na_matriz, no_centro = linhas[loja.ana.pk, loja.matriz.pk], linhas[loja.ana.pk, centro.pk]
    assert (na_matriz.vendido, na_matriz.atendimentos, na_matriz.pausa) == (
        Decimal("300"), 1, timedelta(minutes=45))
    assert (no_centro.vendido, no_centro.atendimentos, no_centro.pausa) == (
        Decimal("200"), 2, timedelta(0))
    assert no_centro.conversao == 50.0 and no_centro.nome == "Ana"
    assert str(no_centro.loja) == str(centro)


def test_por_loja_compara_as_lojas_do_recorte(loja):
    from fila.indicadores import por_loja

    centro = nova_loja(loja.empresa, "Centro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="300")
    atendimento(loja, loja.ana, d, d, vendeu="200", filial=centro)
    atendimento(loja, loja.bia, d, d, filial=centro)
    linhas = {l.loja.pk: l.numeros for l in por_loja(_recorte(loja, lojas=[loja.matriz, centro]))}
    assert (linhas[loja.matriz.pk].vendido, linhas[loja.matriz.pk].atendimentos) == (Decimal("300"), 1)
    assert (linhas[centro.pk].vendido, linhas[centro.pk].conversao) == (Decimal("200"), 50.0)
