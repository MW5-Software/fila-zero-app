"""As transições da fila (spec, "As transições") e as recusas.

Cada teste diz a regra que prova. O relógio anda um minuto por ação
(`tests/fila_cenario.relogio`), então "entrou depois" é sempre verdade.
"""

from decimal import Decimal

import pytest

from tests.fila_cenario import (  # noqa: F401  (relogio é fixture)
    cadastros, nova_loja, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        caio=pessoa_na_loja("caio", empresa, matriz),
        cad=cadastros(empresa))


def _ordem(filial):
    from fila.estado import na_fila

    return [lugar.pessoa.nome for lugar in na_fila(filial)]


def _venda(cad, *valores):
    from fila.acoes import ItemLancado, Lancamento

    return Lancamento("vendeu", tuple(
        ItemLancado(cad.grupo.pk, Decimal(v)) for v in valores))


def _nao_venda(motivo_id, observacao=""):
    from fila.acoes import Lancamento

    return Lancamento("nao_vendeu", motivo_id=motivo_id,
                      observacao=observacao)


# --- A ordem ---------------------------------------------------------------

def test_quem_bate_o_ponto_entra_no_fim(loja):
    from fila.acoes import bater_ponto

    for p in (loja.ana, loja.bia, loja.caio):
        bater_ponto(p, loja.matriz)
    assert _ordem(loja.matriz) == ["Ana", "Bia", "Caio"]


def test_finalizar_manda_para_o_fim(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender

    for p in (loja.ana, loja.bia):
        bater_ponto(p, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    assert _ordem(loja.matriz) == ["Bia"]
    finalizar(loja.ana, loja.matriz, _venda(loja.cad, "100"))
    assert _ordem(loja.matriz) == ["Bia", "Ana"]


def test_voltar_da_pausa_manda_para_o_fim(loja):
    from fila.acoes import bater_ponto, pausar, voltar_para_a_fila

    for p in (loja.ana, loja.bia):
        bater_ponto(p, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    voltar_para_a_fila(loja.ana, loja.matriz)
    assert _ordem(loja.matriz) == ["Bia", "Ana"]


# --- A vez -------------------------------------------------------------------

def test_so_o_primeiro_tem_vou_atender(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender
    from fila.models import Atendimento

    for p in (loja.ana, loja.bia):
        bater_ponto(p, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        vou_atender(loja.bia, loja.matriz)
    assert recusa.value.frase == "A vez é de Ana. Você é o 2º da fila."
    assert not Atendimento.irrestritos.exists()


def test_cliente_pediu_funciona_fora_da_vez_e_nao_mexe_no_primeiro(loja):
    from fila.acoes import bater_ponto, cliente_pediu
    from fila.models import Atendimento

    for p in (loja.ana, loja.bia, loja.caio):
        bater_ponto(p, loja.matriz)
    cliente_pediu(loja.caio, loja.matriz)
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.vendedor == loja.caio
    assert atendimento.cliente_pediu is True
    assert _ordem(loja.matriz) == ["Ana", "Bia"]


def test_tela_velha_vou_atender_de_quem_ja_nao_e_o_primeiro(loja):
    """Ana e Bia veem a Ana em primeiro; a Ana atende; a tela velha da Bia
    ainda mostra a Ana. O "Vou atender" da Bia é aceito, porque AGORA ela é a
    primeira — a vez é decidida no servidor (D9), não na tela."""
    from fila.acoes import Recusa, bater_ponto, vou_atender

    for p in (loja.ana, loja.bia, loja.caio):
        bater_ponto(p, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa):
        vou_atender(loja.caio, loja.matriz)
    vou_atender(loja.bia, loja.matriz)


# --- Venda e não venda -----------------------------------------------------

def test_venda_com_varios_grupos_total_e_a_soma(loja):
    from fila.acoes import (ItemLancado, Lancamento, bater_ponto, finalizar,
                            vou_atender)
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, Lancamento("vendeu", (
        ItemLancado(loja.cad.grupo.pk, Decimal("1500.50")),
        ItemLancado(loja.cad.grupo2.pk, Decimal("300")))))
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.resultado == "vendeu"
    assert atendimento.total == Decimal("1800.50")
    assert atendimento.fim is not None
    assert atendimento.itens.count() == 2


@pytest.mark.parametrize("caso", ["sem_item", "zero", "negativo",
                                  "desativado", "outra_empresa", "com_motivo"])
def test_venda_invalida_e_recusada(loja, caso):
    from fila.acoes import (ItemLancado, Lancamento, Recusa, bater_ponto,
                            finalizar, vou_atender)
    from fila.models import GrupoDeItem

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    grupo = loja.cad.grupo.pk
    lancamento = {
        "sem_item": Lancamento("vendeu", ()),
        "zero": Lancamento("vendeu", (ItemLancado(grupo, Decimal("0")),)),
        "negativo": Lancamento("vendeu", (ItemLancado(grupo, Decimal("-1")),)),
        "desativado": None,
        "outra_empresa": None,
        "com_motivo": Lancamento("vendeu", (ItemLancado(grupo, Decimal("5")),),
                                 motivo_id=loja.cad.motivo.pk),
    }[caso]
    if caso == "desativado":
        GrupoDeItem.irrestritos.filter(pk=grupo).update(ativo=False)
        lancamento = Lancamento("vendeu", (ItemLancado(grupo, Decimal("5")),))
    if caso == "outra_empresa":
        lancamento = Lancamento("vendeu", (
            ItemLancado(_grupo_de_outra_conta().pk, Decimal("5")),))
    with pytest.raises(Recusa):
        finalizar(loja.ana, loja.matriz, lancamento)
    from fila.models import Estado, LugarNaFila

    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.ATENDENDO


def _grupo_de_outra_conta():
    from fila.models import GrupoDeItem
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    outra = Empresa.objects.create(razao_social="Concorrente", nome_fantasia="Concorrente")
    abrir_conta(outra, "concorrente")
    outra.refresh_from_db()
    return GrupoDeItem.irrestritos.create(empresa=outra, nome="Sofás")


def test_nao_venda_grava_motivo_e_observacao_e_total_zero(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz,
              _nao_venda(loja.cad.motivo.pk, "  volta sábado  "))
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.resultado == "nao_vendeu"
    assert atendimento.motivo == loja.cad.motivo
    assert atendimento.observacao == "volta sábado"
    assert atendimento.total == Decimal("0")
    assert atendimento.itens.count() == 0


@pytest.mark.parametrize("caso", ["sem_motivo", "desativado", "outra_empresa",
                                  "com_item", "sem_resultado"])
def test_nao_venda_invalida_e_recusada(loja, caso):
    from fila.acoes import (ItemLancado, Lancamento, Recusa, bater_ponto,
                            finalizar, vou_atender)
    from fila.models import MotivoDeNaoVenda

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    motivo = loja.cad.motivo.pk
    if caso == "desativado":
        MotivoDeNaoVenda.irrestritos.filter(pk=motivo).update(ativo=False)
    if caso == "outra_empresa":
        outro = _grupo_de_outra_conta()
        motivo = MotivoDeNaoVenda.irrestritos.create(
            empresa=outro.empresa, nome="Caro").pk
    lancamento = {
        "sem_motivo": _nao_venda(None),
        "desativado": _nao_venda(motivo),
        "outra_empresa": _nao_venda(motivo),
        "com_item": Lancamento("nao_vendeu", (
            ItemLancado(loja.cad.grupo.pk, Decimal("5")),), motivo_id=motivo),
        "sem_resultado": Lancamento("", motivo_id=motivo),
    }[caso]
    with pytest.raises(Recusa):
        finalizar(loja.ana, loja.matriz, lancamento)


# --- O lugar -----------------------------------------------------------------

def test_ponto_em_outra_loja_fecha_a_presenca_da_primeira(loja):
    from fila.acoes import bater_ponto
    from fila.models import LugarNaFila, Presenca

    centro = nova_loja(loja.empresa, "Centro")
    from contas.models import Alocacao, Cargo

    Alocacao.objects.create(pessoa=loja.ana, empresa=loja.empresa,
                            filial=centro, cargo=Cargo.objects.get(
                                conta_id=loja.empresa.conta_id,
                                nome="vendedor"))
    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.ana, centro)
    assert Presenca.irrestritos.filter(pessoa=loja.ana,
                                       saida__isnull=True).get().filial == centro
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).filial == centro
    assert _ordem(loja.matriz) == []


def test_ponto_em_outra_loja_recusado_se_atendendo(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender

    centro = nova_loja(loja.empresa, "Centro")
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        bater_ponto(loja.ana, centro)
    assert "Finalize" in recusa.value.frase


def test_sair_da_loja_fecha_presenca_e_pausa(loja):
    from fila.acoes import bater_ponto, pausar, sair_da_loja
    from fila.models import LugarNaFila, Pausa, Presenca

    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    sair_da_loja(loja.ana, loja.matriz)
    assert not LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    assert not Presenca.irrestritos.filter(saida__isnull=True).exists()
    assert not Pausa.irrestritos.filter(fim__isnull=True).exists()


def test_sair_da_loja_recusado_se_atendendo(loja):
    from fila.acoes import Recusa, bater_ponto, sair_da_loja, vou_atender

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa):
        sair_da_loja(loja.ana, loja.matriz)


@pytest.mark.parametrize("acao", ["vou_atender", "cliente_pediu", "pausar",
                                  "voltar_para_a_fila", "sair_da_loja"])
def test_quem_nao_bateu_o_ponto_nao_age(loja, acao):
    import fila.acoes as acoes

    argumentos = (loja.cad.tipo.pk,) if acao == "pausar" else ()
    with pytest.raises(acoes.Recusa) as recusa:
        getattr(acoes, acao)(loja.ana, loja.matriz, *argumentos)
    assert recusa.value.frase == "Você não está nesta loja. Bata o ponto primeiro."


def test_pausa_com_tipo_desativado_e_recusada(loja):
    from fila.acoes import Recusa, bater_ponto, pausar
    from fila.models import TipoDePausa

    bater_ponto(loja.ana, loja.matriz)
    TipoDePausa.irrestritos.update(ativo=False)
    with pytest.raises(Recusa):
        pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)


def test_fechado_nao_reabre(loja):
    """Finalizar de novo não mexe no atendimento já fechado: a pessoa não
    está mais atendendo, e a ação é recusada."""
    from fila.acoes import Recusa, bater_ponto, finalizar, vou_atender

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _venda(loja.cad, "10"))
    with pytest.raises(Recusa):
        finalizar(loja.ana, loja.matriz, _venda(loja.cad, "99"))
