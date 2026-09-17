"""As correções de D7: o que o gerente faz no lugar do vendedor.

Toda correção grava na auditoria e nenhuma reabre o que foi fechado.
"""

from decimal import Decimal

import pytest

from tests.fila_cenario import (  # noqa: F401
    cadastros, nova_loja, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db

MOTIVO = "esqueceu de sair"


@pytest.fixture
def loja(relogio):
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz,
        gerente=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        cad=cadastros(empresa))


def _nao_venda(loja, observacao=""):
    from fila.acoes import Lancamento

    return Lancamento("nao_vendeu", motivo_id=loja.cad.motivo.pk,
                      observacao=observacao)


def _venda(loja, *pares):
    from fila.acoes import ItemLancado, Lancamento

    return Lancamento("vendeu", tuple(ItemLancado(g.pk, Decimal(v))
                                      for g, v in pares))


def _ultima_trilha():
    from contas.models import RegistroDeAuditoria

    return RegistroDeAuditoria.objects.order_by("-pk").first()


def test_em_reais():
    from fila.valores import em_reais

    assert em_reais(Decimal("1800.5")) == "R$ 1.800,50"
    assert em_reais(Decimal("0")) == "R$ 0,00"


def test_tirar_da_loja_quem_esqueceu_de_sair(loja):
    from fila.acoes import bater_ponto
    from fila.correcoes import tirar_da_loja
    from fila.models import LugarNaFila, Presenca

    bater_ponto(loja.ana, loja.matriz)
    tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, observacao=MOTIVO)
    assert not LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    presenca = Presenca.irrestritos.get(pessoa=loja.ana)
    assert presenca.saida is not None
    assert presenca.fechada_por == loja.gerente
    trilha = _ultima_trilha()
    assert trilha.acao == "fila_pessoa_tirada"
    assert trilha.alvo == "Ana em Matriz"


def test_tirar_da_loja_quem_esta_atendendo_fecha_como_nao_venda(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender
    from fila.correcoes import tirar_da_loja
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa):
        tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, observacao=MOTIVO)   # sem motivo da não venda
    tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, _nao_venda(loja), observacao=MOTIVO)
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.resultado == "nao_vendeu"
    assert atendimento.fechado_por == loja.gerente


def test_fechar_atendimento_manda_o_vendedor_para_o_fim(loja):
    from fila.acoes import bater_ponto, vou_atender
    from fila.correcoes import fechar_atendimento
    from fila.estado import na_fila
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    fechar_atendimento(loja.gerente, loja.matriz, loja.ana.pk,
                       _venda(loja, (loja.cad.grupo, "250")), observacao=MOTIVO)
    assert [l.pessoa_id for l in na_fila(loja.matriz)] == [loja.bia.pk, loja.ana.pk]
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.fechado_por == loja.gerente
    assert atendimento.total == Decimal("250")
    assert _ultima_trilha().acao == "fila_atendimento_fechado"


def test_tirar_da_pausa(loja):
    from fila.acoes import bater_ponto, pausar
    from fila.correcoes import tirar_da_pausa
    from fila.models import Estado, LugarNaFila, Pausa

    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    tirar_da_pausa(loja.gerente, loja.matriz, loja.ana.pk, observacao=MOTIVO)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
    assert Pausa.irrestritos.get().fim is not None
    assert _ultima_trilha().detalhe == f"Almoço | motivo: {MOTIVO}"


def test_editar_lancamento_troca_grupos_e_valores_e_grava_antes_e_depois(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.correcoes import editar_lancamento
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _venda(loja, (loja.cad.grupo, "100")))
    atendimento = Atendimento.irrestritos.get()
    fim = atendimento.fim
    editar_lancamento(loja.gerente, loja.matriz, atendimento.pk, _venda(
        loja, (loja.cad.grupo, "80"), (loja.cad.grupo2, "40")), observacao=MOTIVO)
    atendimento.refresh_from_db()
    assert atendimento.total == Decimal("120")
    assert atendimento.fim == fim                 # não reabre, não re-fecha
    assert atendimento.itens.count() == 2
    trilha = _ultima_trilha()
    assert trilha.acao == "fila_lancamento_corrigido"
    assert "antes: vendeu R$ 100,00" in trilha.detalhe
    assert "depois: vendeu R$ 120,00" in trilha.detalhe


def test_editar_lancamento_nao_troca_o_resultado(loja):
    from fila.acoes import Recusa, bater_ponto, finalizar, vou_atender
    from fila.correcoes import editar_lancamento
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    with pytest.raises(Recusa):
        editar_lancamento(loja.gerente, loja.matriz,
                          Atendimento.irrestritos.get().pk,
                          _venda(loja, (loja.cad.grupo, "10")), observacao=MOTIVO)


def test_editar_atendimento_aberto_ou_de_outra_loja_e_recusado(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender
    from fila.correcoes import editar_lancamento
    from fila.models import Atendimento

    centro = nova_loja(loja.empresa, "Centro")
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    aberto = Atendimento.irrestritos.get()
    # A frase é conferida: um aberto também seria recusado por "o resultado
    # não muda" (aberto não tem resultado), e o teste passaria sem a trava de
    # só editar o que está fechado.
    with pytest.raises(Recusa) as recusa:
        editar_lancamento(loja.gerente, loja.matriz, aberto.pk,
                          _nao_venda(loja), observacao=MOTIVO)
    assert recusa.value.frase == "Lançamento não encontrado."
    with pytest.raises(Recusa) as recusa:
        editar_lancamento(loja.gerente, centro, aberto.pk, _nao_venda(loja), observacao=MOTIVO)
    assert recusa.value.frase == "Lançamento não encontrado."


def test_ninguem_corrige_a_si_mesmo(loja):
    """Desvio D-3 do plano."""
    from fila.acoes import Recusa, bater_ponto, pausar
    from fila.correcoes import tirar_da_pausa

    bater_ponto(loja.gerente, loja.matriz)
    pausar(loja.gerente, loja.matriz, loja.cad.tipo.pk)
    with pytest.raises(Recusa) as recusa:
        tirar_da_pausa(loja.gerente, loja.matriz, loja.gerente.pk, observacao=MOTIVO)
    assert recusa.value.frase == "Você não corrige a si mesmo."


def test_correcao_em_quem_esta_em_outra_loja_e_recusada(loja):
    from fila.acoes import Recusa, bater_ponto
    from fila.correcoes import tirar_da_loja

    centro = nova_loja(loja.empresa, "Centro")
    bater_ponto(loja.ana, centro)
    with pytest.raises(Recusa):
        tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, observacao=MOTIVO)


def test_lancamentos_de_hoje_so_os_fechados_da_loja(loja):
    from datetime import date

    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.correcoes import lancamentos_de_hoje

    centro = nova_loja(loja.empresa, "Centro")
    for pessoa, filial in ((loja.ana, loja.matriz), (loja.bia, centro)):
        bater_ponto(pessoa, filial)
        vou_atender(pessoa, filial)
        finalizar(pessoa, filial, _nao_venda(loja))
    assert [a.vendedor_id for a in lancamentos_de_hoje(
        loja.matriz, dia=date(2026, 9, 15))] == [loja.ana.pk]


# --- O histórico das correções (spec 2026-09-17) -----------------------------

def test_a_versao_da_fila_muda_com_uma_correcao(loja):
    """Mover grava um instante ENTRE os vizinhos: sem contar as correções, a
    versão não mudaria e as outras telas não veriam a ordem nova."""
    from django.utils import timezone

    from fila.estado import versao_da_fila
    from fila.models import CorrecaoNaFila

    antes = versao_da_fila(loja.matriz)
    CorrecaoNaFila.irrestritos.create(
        empresa=loja.empresa, filial=loja.matriz, pessoa=loja.ana,
        autor=loja.gerente, acao="mover", observacao="chegou antes",
        detalhe="de 2º para 1º", momento=timezone.now())
    assert versao_da_fila(loja.matriz) != antes


@pytest.mark.parametrize("texto, frase", [
    ("", "Escreva o motivo da correção."),
    ("  a  ", "Escreva o motivo da correção."),
    ("x" * 201, "O motivo cabe em 200 caracteres."),
])
def test_sem_motivo_nenhuma_correcao_acontece(loja, texto, frase):
    from fila.acoes import Recusa, bater_ponto
    from fila.correcoes import tirar_da_loja
    from fila.models import CorrecaoNaFila, LugarNaFila

    bater_ponto(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, observacao=texto)
    assert recusa.value.frase == frase
    assert LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    assert not CorrecaoNaFila.irrestritos.exists()


def test_o_motivo_junta_os_espacos():
    from fila.correcoes import ler_observacao

    assert ler_observacao("  foi   ao\nbanco ") == "foi ao banco"


def test_cada_correcao_grava_o_historico_e_a_auditoria(loja):
    from fila.acoes import bater_ponto, pausar, vou_atender
    from fila.correcoes import (editar_lancamento, fechar_atendimento,
                                tirar_da_loja, tirar_da_pausa)
    from fila.models import Atendimento, CorrecaoNaFila

    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    tirar_da_pausa(loja.gerente, loja.matriz, loja.ana.pk, observacao="voltou do almoço")
    vou_atender(loja.ana, loja.matriz)
    fechar_atendimento(loja.gerente, loja.matriz, loja.ana.pk,
                       _venda(loja, (loja.cad.grupo, "250")), observacao="esqueceu de lançar")
    editar_lancamento(loja.gerente, loja.matriz, Atendimento.irrestritos.get().pk,
                      _venda(loja, (loja.cad.grupo, "300")), observacao="valor errado")
    tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, observacao="foi embora")
    linhas = list(CorrecaoNaFila.irrestritos.order_by("momento")
                  .values_list("acao", "observacao", "detalhe", "pessoa_id", "autor_id"))
    assert [l[:2] for l in linhas] == [
        ("tirar_pausa", "voltou do almoço"), ("fechar", "esqueceu de lançar"),
        ("editar", "valor errado"), ("tirar", "foi embora")]
    assert linhas[0][2] == "Almoço"
    assert all(l[3] == loja.ana.pk and l[4] == loja.gerente.pk for l in linhas)
    assert _ultima_trilha().detalhe == "motivo: foi embora"
