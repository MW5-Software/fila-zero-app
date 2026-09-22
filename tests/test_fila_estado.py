from decimal import Decimal

import pytest

from tests.fila_cenario import (  # noqa: F401
    cadastros, nova_loja, pessoa_na_loja, relogio, sylvia)


@pytest.mark.parametrize("texto, esperado", [
    ("1500", Decimal("1500")), ("1.500,50", Decimal("1500.50")),
    ("1500,5", Decimal("1500.50")), ("1500.50", Decimal("1500.50")),
    (" R$ 2.000 ", Decimal("2000")), ("1.234.567,8", Decimal("1234567.80")),
    ("", None), ("abc", None), ("1,2,3", None), ("-5", None),
])
def test_ler_valor(texto, esperado):
    from fila.valores import ler_valor

    assert ler_valor(texto) == esperado


@pytest.mark.django_db
def test_retrato_separa_atendendo_fila_e_pausa_e_marca_quem_ve(relogio):
    from fila.acoes import bater_ponto, pausar, vou_atender
    from fila.estado import retrato

    empresa, matriz, _ = sylvia()
    cad = cadastros(empresa)
    ana, bia, caio, duda = (pessoa_na_loja(n, empresa, matriz)
                            for n in ("ana", "bia", "caio", "duda"))
    for p in (ana, bia, caio, duda):
        bater_ponto(p, matriz)
    vou_atender(ana, matriz)
    pausar(duda, matriz, cad.tipo.pk)

    r = retrato(matriz, caio)
    assert [l.nome for l in r.atendendo] == ["Ana"]
    assert [(l.nome, l.posicao) for l in r.fila] == [("Bia", 1), ("Caio", 2)]
    assert [(l.nome, l.tipo_de_pausa) for l in r.em_pausa] == [("Duda", "Almoço")]
    assert r.meu.nome == "Caio" and r.meu.e_voce and r.meu.posicao == 2


@pytest.mark.django_db
def test_retrato_de_uma_loja_nunca_traz_gente_de_outra(relogio):
    from fila.acoes import bater_ponto
    from fila.estado import retrato

    empresa, matriz, _ = sylvia()
    centro = nova_loja(empresa, "Centro")
    bater_ponto(pessoa_na_loja("ana", empresa, matriz), matriz)
    bater_ponto(pessoa_na_loja("bia", empresa, centro), centro)
    assert [l.nome for l in retrato(centro, None).fila] == ["Bia"]


@pytest.mark.django_db
def test_a_versao_muda_quando_a_fila_muda_e_so_entao(relogio):
    from fila.acoes import bater_ponto, sair_da_loja, vou_atender
    from fila.estado import versao_da_fila

    empresa, matriz, _ = sylvia()
    centro = nova_loja(empresa, "Centro")
    ana = pessoa_na_loja("ana", empresa, matriz)
    bia = pessoa_na_loja("bia", empresa, centro)

    vazia = versao_da_fila(matriz)
    assert versao_da_fila(matriz) == vazia        # nada mudou
    bater_ponto(ana, matriz)
    com_ana = versao_da_fila(matriz)
    assert com_ana != vazia
    bater_ponto(bia, centro)                      # outra loja
    assert versao_da_fila(matriz) == com_ana
    vou_atender(ana, matriz)
    atendendo = versao_da_fila(matriz)
    assert atendendo != com_ana
    from fila.acoes import Lancamento, finalizar

    finalizar(ana, matriz, Lancamento("nao_vendeu",
                                      motivo_id=cadastros(empresa).motivo.pk))
    assert versao_da_fila(matriz) != atendendo
    sair_da_loja(ana, matriz)
    assert versao_da_fila(matriz) != atendendo


@pytest.mark.django_db
def test_o_retrato_separa_quem_esta_em_espera(relogio):
    """Espera é estado próprio: não entra na fila nem na pausa (spec
    2026-09-17-fluxo-da-fila-por-empresa)."""
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.estado import retrato
    from fila.models import Estado
    from fila.fluxo import FluxoDaFila, definir_fluxo
    from tests.fila_cenario import cadastros, pessoa_na_loja, sylvia

    empresa, matriz, _titular = sylvia()
    definir_fluxo(empresa, FluxoDaFila.ESPERA)
    cad = cadastros(empresa)
    ana = pessoa_na_loja("ana", empresa, matriz)
    bia = pessoa_na_loja("bia", empresa, matriz)
    bater_ponto(ana, matriz)
    bater_ponto(bia, matriz)
    vou_atender(ana, matriz)
    from fila.acoes import Lancamento

    finalizar(ana, matriz, Lancamento("nao_vendeu", motivo_id=cad.motivo.pk))

    r = retrato(matriz, ana)
    assert [l.pessoa_id for l in r.em_espera] == [ana.pk]
    assert [l.pessoa_id for l in r.fila] == [bia.pk]
    assert r.em_pausa == []
    assert r.meu is not None and r.meu.estado == Estado.EM_ESPERA
    assert r.meu.posicao is None
