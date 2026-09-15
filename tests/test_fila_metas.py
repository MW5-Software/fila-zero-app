"""As metas de venda da fila (spec 2026-09-15-fila-metas, entrega 3).

O registro, as regras de `fila/metas.py` e as contas do acompanhamento. As
contas recebem o relógio (`agora`) para cada dia do mês ser provado, e não o
dia em que a suíte roda.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from tests.fila_cenario import nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db

SETEMBRO = date(2026, 9, 1)


def local(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def loja():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(empresa=empresa, matriz=matriz, titular=titular,
                           ana=pessoa_na_loja("ana", empresa, matriz),
                           bia=pessoa_na_loja("bia", empresa, matriz))


def meta(loja, valor="1000", pessoa=None, mes=SETEMBRO, filial=None):
    from fila.models import MetaDeVenda

    return MetaDeVenda.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, pessoa=pessoa,
        mes=mes, valor=Decimal(valor))


def _estoura(**kwargs):
    with pytest.raises(IntegrityError), transaction.atomic():
        meta(**kwargs)


# --- O registro --------------------------------------------------------------

def test_uma_meta_da_loja_por_mes(loja):
    meta(loja)
    _estoura(loja=loja, valor="2000")
    meta(loja, mes=date(2026, 10, 1))


def test_uma_meta_por_pessoa_loja_e_mes(loja):
    meta(loja, pessoa=loja.ana)
    _estoura(loja=loja, pessoa=loja.ana, valor="2000")
    # A da loja e a de outra pessoa no mesmo mês convivem.
    meta(loja)
    meta(loja, pessoa=loja.bia)


def test_a_mesma_pessoa_tem_meta_em_duas_lojas(loja):
    centro = nova_loja(loja.empresa, "Centro")
    meta(loja, pessoa=loja.ana)
    meta(loja, pessoa=loja.ana, filial=centro)


def test_mes_fora_do_dia_1_e_valor_zero_o_banco_recusa(loja):
    _estoura(loja=loja, mes=date(2026, 9, 15))
    _estoura(loja=loja, valor="0")


# --- O mês e o acompanhamento (contas puras) -----------------------------------

from fila.metas import acompanhar, mes_do_texto, mes_encerrado  # noqa: E402

DIA_15 = local(2026, 9, 15, 14)


def test_mes_do_texto():
    assert mes_do_texto("2026-10", DIA_15) == date(2026, 10, 1)
    assert mes_do_texto("2026-1", DIA_15) == date(2026, 1, 1)
    # Vazio, inválido, "²" (isdigit sem ser ASCII) e ano absurdo: mês atual.
    for texto in ("", None, "2026-13", "setembro", "2026-²", "20²6-09", "1500-01"):
        assert mes_do_texto(texto, DIA_15) == SETEMBRO


def test_mes_encerrado():
    assert mes_encerrado(date(2026, 8, 1), DIA_15)
    assert not mes_encerrado(SETEMBRO, DIA_15)
    assert not mes_encerrado(date(2026, 10, 1), DIA_15)


def test_dia_15_falta_por_dia_e_projecao():
    a = acompanhar(Decimal("30000"), Decimal("18600"), SETEMBRO, DIA_15,
                   vendido_ate_ontem=Decimal("17000"))
    assert a.atingido == 62.0
    assert (a.falta, a.excedente, a.batida) == (Decimal("11400"), Decimal("0"), False)
    # Do dia 15 ao 30, contando hoje: 16 dias.
    assert a.dias_restantes == 16
    assert a.por_dia == Decimal("712.50")
    # 17.000 em 14 dias fechados, num mês de 30.
    assert a.projecao == Decimal("36428.57")
    assert a.ultimo_dia == date(2026, 9, 30) and not a.encerrado


def test_dia_1_nao_tem_projecao():
    a = acompanhar(Decimal("30000"), Decimal("5000"), SETEMBRO, local(2026, 9, 1, 10),
                   vendido_ate_ontem=Decimal("0"))
    assert a.dias_restantes == 30
    assert a.projecao is None


def test_ultimo_dia_o_por_dia_e_a_falta_inteira():
    a = acompanhar(Decimal("30000"), Decimal("29000"), SETEMBRO, local(2026, 9, 30, 9))
    assert a.dias_restantes == 1 and a.por_dia == Decimal("1000.00")


def test_meta_batida_nao_tem_por_dia():
    a = acompanhar(Decimal("30000"), Decimal("31000"), SETEMBRO, DIA_15)
    assert a.batida and a.excedente == Decimal("1000") and a.por_dia is None


def test_mes_passado_sem_ritmo():
    a = acompanhar(Decimal("20000"), Decimal("18400"), date(2026, 8, 1), DIA_15,
                   vendido_ate_ontem=Decimal("18400"))
    assert a.encerrado and a.atingido == 92.0 and a.falta == Decimal("1600")
    assert (a.dias_restantes, a.por_dia, a.projecao) == (None, None, None)


def test_mes_futuro_nao_tem_acompanhamento():
    with pytest.raises(ValueError):
        acompanhar(Decimal("1"), Decimal("0"), date(2026, 10, 1), DIA_15)


# --- A lista, gravar e copiar ---------------------------------------------------

from fila import metas as regras  # noqa: E402


def _chaves(linhas):
    return [(l.pessoa.nome, l.na_loja, l.propria) for l in linhas]


def test_lojas_com_metas_pelo_cargo(loja):
    from fila.metas import lojas_com_metas

    centro = nova_loja(loja.empresa, "Centro")
    gil = pessoa_na_loja("gil", loja.empresa, centro, cargo="gerente")
    sara = pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    assert lojas_com_metas(gil, loja.empresa) == [centro]
    assert set(lojas_com_metas(sara, loja.empresa)) == {loja.matriz, centro}
    assert lojas_com_metas(loja.ana, loja.empresa) == []


def test_a_lista_traz_quem_participa_e_quem_saiu_com_meta(loja):
    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")  # não participa
    centro = nova_loja(loja.empresa, "Centro")
    caio = pessoa_na_loja("caio", loja.empresa, centro)
    meta(loja, pessoa=caio, valor="5000")  # já teve meta aqui, hoje está no Centro
    linhas = regras.pessoas_da_lista(loja.matriz, SETEMBRO, gil)
    assert _chaves(linhas) == [("Ana", True, False), ("Bia", True, False),
                               ("Caio", False, False), ("Gil", True, True)]
    assert linhas[2].valor == Decimal("5000")


def test_gravar_cria_altera_apaga_e_audita(loja):
    from contas.models import RegistroDeAuditoria
    from fila.models import MetaDeVenda

    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    dia = local(2026, 9, 10, 9)
    assert regras.gravar(loja.matriz, SETEMBRO, gil,
                         {"loja": "250.000,00", str(loja.ana.pk): "30000"},
                         agora=dia) == 2
    assert regras.meta_da_loja(loja.matriz, SETEMBRO) == Decimal("250000")
    assert regras.gravar(loja.matriz, SETEMBRO, gil,
                         {"loja": "250000", str(loja.ana.pk): ""}, agora=dia) == 1
    assert not MetaDeVenda.irrestritos.filter(pessoa=loja.ana).exists()
    acoes = list(RegistroDeAuditoria.objects.values_list("acao", flat=True))
    assert acoes.count("fila_meta_definida") == 2
    assert acoes.count("fila_meta_removida") == 1


def test_campo_ausente_nao_mexe(loja):
    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    meta(loja, pessoa=loja.ana, valor="30000")
    regras.gravar(loja.matriz, SETEMBRO, gil, {"loja": "1000"}, agora=local(2026, 9, 10))
    assert regras.pessoas_da_lista(loja.matriz, SETEMBRO, gil)[0].valor == Decimal("30000")


def test_valor_invalido_recusa_tudo_e_nao_grava_nada(loja):
    from fila.models import MetaDeVenda

    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    with pytest.raises(regras.ValoresInvalidos) as recusa:
        regras.gravar(loja.matriz, SETEMBRO, gil,
                      {"loja": "1000", str(loja.ana.pk): "abc", str(loja.bia.pk): "0"},
                      agora=local(2026, 9, 10))
    assert set(recusa.value.erros) == {str(loja.ana.pk), str(loja.bia.pk)}
    assert not MetaDeVenda.irrestritos.exists()


def test_ninguem_grava_a_propria_nem_de_fora_da_lista(loja):
    from fila.models import MetaDeVenda

    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    de_fora = pessoa_na_loja("zeca", loja.empresa, nova_loja(loja.empresa, "Norte"))
    regras.gravar(loja.matriz, SETEMBRO, gil,
                  {str(gil.pk): "99999", str(de_fora.pk): "99999"},
                  agora=local(2026, 9, 10))
    assert not MetaDeVenda.irrestritos.exists()


def test_mes_encerrado_recusa_gravar(loja):
    from fila.acoes import Recusa

    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    with pytest.raises(Recusa):
        regras.gravar(loja.matriz, date(2026, 8, 1), gil, {"loja": "1000"},
                      agora=local(2026, 9, 10))


def test_copiar_preenche_so_o_vazio_e_nao_traz_quem_saiu(loja):
    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    agosto = date(2026, 8, 1)
    centro = nova_loja(loja.empresa, "Centro")
    caio = pessoa_na_loja("caio", loja.empresa, centro)
    meta(loja, valor="200000", mes=agosto)
    meta(loja, pessoa=loja.ana, valor="25000", mes=agosto)
    meta(loja, pessoa=loja.bia, valor="20000", mes=agosto)
    meta(loja, pessoa=caio, valor="9000", mes=agosto)
    meta(loja, pessoa=loja.bia, valor="22000")  # setembro já tem a da Bia
    linhas = regras.pessoas_da_lista(loja.matriz, SETEMBRO, gil)
    assert regras.copiar_do_anterior(loja.matriz, SETEMBRO, linhas) == {
        "loja": "200000,00", str(loja.ana.pk): "25000,00"}
