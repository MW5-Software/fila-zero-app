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


def test_a_recusa_sai_no_idioma_de_quem_agiu(loja):
    """As frases de recusa passam pelo gettext no momento da recusa, com o
    nome e a posição por `%(...)s`, para o castelhano mudar a ordem."""
    from django.utils import translation

    from fila.acoes import Recusa, bater_ponto, vou_atender

    for p in (loja.ana, loja.bia):
        bater_ponto(p, loja.matriz)
    with translation.override("es"), pytest.raises(Recusa) as recusa:
        vou_atender(loja.bia, loja.matriz)
    assert recusa.value.frase == "El turno es de Ana. Usted es el 2º de la fila."


# --- Loja desativada com gente dentro (revisão final, B9) -------------------
# Regra escolhida pelo João em 15/09/2026: recusar a desativação enquanto
# houver presença aberta, em vez de fechar as presenças junto.

def test_loja_com_gente_presente_nao_se_desativa(loja):
    from fila.acoes import bater_ponto, sair_da_loja
    from plataforma.filiais import pode_desativar

    # Outra loja ativa: sem ela a recusa viria por ser a última ativa.
    nova_loja(loja.empresa, "Centro")
    assert pode_desativar(loja.matriz) is None

    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    assert pode_desativar(loja.matriz) == (
        "Há 2 pessoas presentes nesta loja. Tire todas da loja na página da "
        "fila antes de desativar.")

    sair_da_loja(loja.ana, loja.matriz)
    assert "Há 1 pessoa presente" in pode_desativar(loja.matriz)
    sair_da_loja(loja.bia, loja.matriz)
    assert pode_desativar(loja.matriz) is None


def test_presenca_esquecida_de_outro_dia_tambem_prende(loja):
    from datetime import timedelta

    from django.utils import timezone

    from fila.models import Presenca
    from plataforma.filiais import pode_desativar

    nova_loja(loja.empresa, "Centro")
    Presenca.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                pessoa=loja.caio,
                                entrada=timezone.now() - timedelta(days=3))
    assert "Há 1 pessoa presente" in pode_desativar(loja.matriz)


def test_ponto_em_loja_desativada_e_recusado(loja):
    """A outra metade da trava: a desativação confere quem está presente com a
    linha da loja trancada, e o ponto relê a loja depois da mesma trava."""
    from fila.acoes import Recusa, bater_ponto
    from fila.models import Presenca

    loja.matriz.ativa = False
    loja.matriz.save(update_fields=["ativa"])
    with pytest.raises(Recusa) as recusa:
        bater_ponto(loja.ana, loja.matriz)
    assert str(recusa.value) == "Esta loja está desativada."
    assert not Presenca.irrestritos.filter(pessoa=loja.ana).exists()


def test_tela_de_filiais_recusa_desativar_loja_com_gente(loja):
    from django.urls import reverse

    from fila.acoes import bater_ponto
    from plataforma.models import Modulo
    from tests.fila_cenario import logado

    nova_loja(loja.empresa, "Centro")
    Modulo.objects.update_or_create(chave="filiais", defaults={"ativo": True})
    bater_ponto(loja.ana, loja.matriz)
    resposta = logado("sylvia").post(
        reverse("filiais"), {"acao": "desativar", "filial": str(loja.matriz.pk)})
    loja.matriz.refresh_from_db()
    assert loja.matriz.ativa is True
    assert "Há 1 pessoa presente nesta loja" in resposta.content.decode()


# --- Entre empresas (spec 2026-09-17, E5) ------------------------------------

def test_o_ponto_e_um_so_em_qualquer_empresa(loja):
    """A pessoa alocada em duas EMPRESAS da mesma conta continua com um ponto
    aberto por vez: chegar na loja da outra empresa fecha a presença da
    primeira, como já acontecia entre lojas da mesma empresa."""
    from contas.models import Alocacao, Cargo
    from fila.acoes import bater_ponto
    from fila.models import LugarNaFila, Presenca
    from plataforma.models import Empresa, Filial

    beta = Empresa.objects.create(razao_social="Beta Ltda",
                                  dono_id=loja.empresa.dono_id)
    loja_beta = Filial.objects.get(empresa=beta, e_matriz=True)
    Alocacao.objects.create(pessoa=loja.ana, empresa=beta, filial=loja_beta,
                            cargo=Cargo.objects.get(conta_id=beta.conta_id,
                                                    nome="vendedor"))
    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.ana, loja_beta)

    aberta = Presenca.irrestritos.get(pessoa=loja.ana, saida__isnull=True)
    assert aberta.filial == loja_beta and aberta.empresa_id == beta.pk
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).filial == loja_beta
    assert Presenca.irrestritos.filter(pessoa=loja.ana).count() == 2


def test_atendendo_numa_empresa_a_recusa_diz_a_loja_e_a_empresa(loja):
    from contas.models import Alocacao, Cargo
    from fila.acoes import Recusa, bater_ponto, vou_atender
    from plataforma.models import Empresa, Filial

    beta = Empresa.objects.create(razao_social="Beta Ltda",
                                  dono_id=loja.empresa.dono_id)
    loja_beta = Filial.objects.get(empresa=beta, e_matriz=True)
    Alocacao.objects.create(pessoa=loja.ana, empresa=beta, filial=loja_beta,
                            cargo=Cargo.objects.get(conta_id=beta.conta_id,
                                                    nome="vendedor"))
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        bater_ponto(loja.ana, loja_beta)
    frase = recusa.value.frase
    assert str(loja.matriz) in frase and str(loja.empresa) in frase


# --- O fluxo da empresa (spec 2026-09-17-fluxo-da-fila-por-empresa) ---------

def _com_espera(loja):
    from fila.fluxo import FluxoDaFila, definir_fluxo

    definir_fluxo(loja.empresa, FluxoDaFila.ESPERA)
    return loja


def test_no_fluxo_de_hoje_lancar_volta_para_o_fim(loja):
    """A regressão da Sylvia: o fluxo padrão não muda em nada."""
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.models import Estado, LugarNaFila

    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja.cad.motivo.pk))
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
    assert _ordem(loja.matriz) == ["Bia", "Ana"]


def test_no_fluxo_de_espera_lancar_tira_da_fila(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.models import Estado, LugarNaFila, Pausa

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja.cad.motivo.pk))
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_ESPERA
    assert _ordem(loja.matriz) == ["Bia"]
    # Espera não é pausa: nenhuma linha de pausa, e nada a fechar depois.
    assert not Pausa.irrestritos.exists()


def test_entrar_na_fila_poe_no_fim(loja):
    from fila.acoes import bater_ponto, entrar_na_fila, finalizar, vou_atender
    from fila.models import Estado, LugarNaFila

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja.cad.motivo.pk))
    entrar_na_fila(loja.ana, loja.matriz)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
    assert _ordem(loja.matriz) == ["Bia", "Ana"]


def test_entrar_na_fila_de_quem_ja_esta_na_fila(loja):
    from fila.acoes import Recusa, bater_ponto, entrar_na_fila

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        entrar_na_fila(loja.ana, loja.matriz)
    assert recusa.value.frase == "Você já está na fila."


def test_entrar_na_fila_de_quem_atende_ou_esta_em_pausa(loja):
    from fila.acoes import Recusa, bater_ponto, entrar_na_fila, pausar, vou_atender

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        entrar_na_fila(loja.ana, loja.matriz)
    assert recusa.value.frase == "Finalize o atendimento primeiro."

    bater_ponto(loja.bia, loja.matriz)
    pausar(loja.bia, loja.matriz, loja.cad.tipo.pk)
    with pytest.raises(Recusa) as recusa:
        entrar_na_fila(loja.bia, loja.matriz)
    assert recusa.value.frase == "Encerre a pausa primeiro."


@pytest.mark.parametrize("acao", ["vou_atender", "cliente_pediu"])
def test_quem_esta_em_espera_nao_atende_sem_entrar_na_fila(loja, acao):
    """Tela velha (dois aparelhos, toque duplo): o POST de atender chega de
    quem já está em espera. Com a fila vazia isto era um 500."""
    from fila import acoes
    from fila.models import Atendimento, Estado, LugarNaFila

    _com_espera(loja)
    acoes.bater_ponto(loja.ana, loja.matriz)
    acoes.vou_atender(loja.ana, loja.matriz)
    acoes.finalizar(loja.ana, loja.matriz, _nao_venda(loja.cad.motivo.pk))
    with pytest.raises(acoes.Recusa) as recusa:
        getattr(acoes, acao)(loja.ana, loja.matriz)
    assert recusa.value.frase == "Você está em espera. Entre na fila primeiro."
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_ESPERA
    assert Atendimento.irrestritos.count() == 1


def test_encerrar_a_pausa_segue_o_fluxo_da_empresa(loja):
    from fila.acoes import bater_ponto, pausar, voltar_para_a_fila
    from fila.models import Estado, LugarNaFila, Pausa

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    voltar_para_a_fila(loja.ana, loja.matriz)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_ESPERA
    # A pausa fecha do mesmo jeito: o que muda é só para onde a pessoa vai.
    assert Pausa.irrestritos.get(pessoa=loja.ana).fim is not None


def test_bater_o_ponto_continua_entrando_na_fila(loja):
    from fila.acoes import bater_ponto
    from fila.models import Estado, LugarNaFila

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
