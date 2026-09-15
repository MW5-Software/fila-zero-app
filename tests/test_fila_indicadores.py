"""As contas dos indicadores (spec, "As regras de cálculo").

Cada cenário grava atendimentos com hora conhecida, direto nos models: o que
se prova aqui é a CONTA, e a fila tem os testes dela.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from fila.indicadores import (Recorte, esquecidos, lojas_com_relatorio,
                              motivos, numeros, pausa_por_tipo, por_dia,
                              por_grupo, variacao)
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
        ("01/09", 1, Decimal("100")), ("02/09", 0, Decimal("0")), ("03/09", 1, Decimal("0"))]


def test_por_dia_de_um_dia_so_e_por_hora(loja):
    atendimento(loja, loja.ana, local(2026, 9, 1, 10), local(2026, 9, 1, 10, 5), vendeu="100")
    um_dia = Periodo(local(2026, 9, 1), local(2026, 9, 2), "hoje", "Hoje")
    linhas = por_dia(_recorte(loja, um_dia))
    assert len(linhas) == 24
    assert linhas[10] == ("10h", 1, Decimal("100"))


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
