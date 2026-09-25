"""O turno da loja e a saída automática (23/09/2026).

Pedido do cliente: *"criar o parâmetro de turno da empresa/filial por que vamos
fazer automatizar se o vendedor não saiu da fila, depois de uma hora do turno
ele sai sozinho"*. Duas escolhas dele no mesmo dia, e as duas têm teste aqui: o
horário é por FILIAL, e quem sai é quem está na fila, em espera ou em pausa —
quem está atendendo fica.

As horas são escritas no fuso da loja (`America/Sao_Paulo`), que é o relógio em
que o turno é cadastrado.
"""

from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import (  # noqa: F401
    logado, nova_loja, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        centro=nova_loja(empresa, "Centro"))


def _local(*partes) -> datetime:
    """Um instante no relógio da loja — o mesmo em que o turno é cadastrado."""
    return timezone.make_aware(datetime(*partes))


def _na_loja(pessoa, filial, entrada, estado=None):
    from fila.models import Estado, LugarNaFila, Presenca

    presenca = Presenca.irrestritos.create(empresa=filial.empresa, filial=filial,
                                          pessoa=pessoa, entrada=entrada)
    return LugarNaFila.irrestritos.create(
        empresa=filial.empresa, filial=filial, pessoa=pessoa, presenca=presenca,
        estado=estado or Estado.NA_FILA, na_fila_desde=entrada, desde=entrada)


def _linhas():
    from contas.models import RegistroDeAuditoria

    return RegistroDeAuditoria.objects.filter(acao="fila_saida_por_turno")


def test_uma_hora_depois_do_turno_quem_ficou_sai_sozinho(loja):
    from fila import turno
    from fila.models import LugarNaFila, Presenca

    turno.definir(loja.matriz, time(23, 0))
    lugar = _na_loja(loja.ana, loja.matriz, _local(2026, 9, 15, 18, 0))
    assert turno.aplicar(loja.matriz, _local(2026, 9, 16, 0, 15)) == 1

    assert not LugarNaFila.irrestritos.filter(pk=lugar.pk).exists()
    presenca = Presenca.irrestritos.get(pk=lugar.presenca_id)
    # A saída é gravada com a hora do PRAZO (00:00), e não com a hora em que
    # alguém abriu a página: quem ficou até 00:00 não pode aparecer como tendo
    # ficado até as 3h da manhã porque a primeira leitura do dia foi às 3h.
    assert presenca.saida == _local(2026, 9, 16, 0, 0)
    assert _linhas().count() == 1


def test_antes_do_prazo_ninguem_sai(loja):
    from fila import turno
    from fila.models import LugarNaFila

    turno.definir(loja.matriz, time(23, 0))
    lugar = _na_loja(loja.ana, loja.matriz, _local(2026, 9, 15, 18, 0))
    assert turno.aplicar(loja.matriz, _local(2026, 9, 15, 23, 30)) == 0
    assert LugarNaFila.irrestritos.filter(pk=lugar.pk).exists()


def test_quem_esta_atendendo_fica(loja):
    """Fechar sozinho um atendimento aberto perderia a venda que o vendedor
    está lançando — decisão do cliente no mesmo dia."""
    from fila import turno
    from fila.models import Estado, LugarNaFila

    turno.definir(loja.matriz, time(23, 0))
    lugar = _na_loja(loja.ana, loja.matriz, _local(2026, 9, 15, 18, 0),
                     estado=Estado.ATENDENDO)
    assert turno.aplicar(loja.matriz, _local(2026, 9, 16, 1, 0)) == 0
    assert LugarNaFila.irrestritos.filter(pk=lugar.pk).exists()


def test_quem_entrou_depois_do_prazo_fica(loja):
    """Quem bateu o ponto depois do prazo está numa jornada nova: tirá-lo na
    primeira leitura seria expulsar quem acabou de chegar."""
    from fila import turno
    from fila.models import LugarNaFila

    turno.definir(loja.matriz, time(23, 0))
    lugar = _na_loja(loja.ana, loja.matriz, _local(2026, 9, 16, 0, 30))
    assert turno.aplicar(loja.matriz, _local(2026, 9, 16, 1, 0)) == 0
    assert LugarNaFila.irrestritos.filter(pk=lugar.pk).exists()


def test_o_prazo_de_ontem_vale_de_madrugada(loja):
    """Loja que fecha 23:30 tem prazo à 00:30 do dia seguinte: sem olhar ontem,
    quem ficou só sairia no dia seguinte, quase 24 horas depois."""
    from fila import turno

    turno.definir(loja.matriz, time(23, 30))
    assert turno.prazo(loja.matriz, _local(2026, 9, 16, 0, 15)) is None
    assert turno.prazo(loja.matriz, _local(2026, 9, 16, 0, 45)) == _local(
        2026, 9, 16, 0, 30)


def test_o_turno_e_de_cada_loja(loja):
    """O horário é por FILIAL (decisão do cliente): a loja que fecha mais tarde
    não tira ninguém da fila cedo, e a que não tem turno não tira ninguém."""
    from fila import turno
    from fila.models import LugarNaFila

    turno.definir(loja.matriz, time(18, 0))
    da_matriz = _na_loja(loja.ana, loja.matriz, _local(2026, 9, 15, 12, 0))
    do_centro = _na_loja(loja.bia, loja.centro, _local(2026, 9, 15, 12, 0))

    agora = _local(2026, 9, 15, 20, 0)
    assert turno.fim_de(loja.centro) is None
    assert turno.aplicar(loja.centro, agora) == 0
    assert turno.aplicar(loja.matriz, agora) == 1
    assert not LugarNaFila.irrestritos.filter(pk=da_matriz.pk).exists()
    assert LugarNaFila.irrestritos.filter(pk=do_centro.pk).exists()


def test_sem_turno_nao_ha_saida_e_a_segunda_passada_nao_faz_nada(loja):
    from fila import turno
    from fila.models import LugarNaFila

    lugar = _na_loja(loja.ana, loja.matriz, _local(2026, 9, 15, 12, 0))
    assert turno.fim_de(loja.matriz) is None
    assert turno.aplicar(loja.matriz, _local(2026, 9, 16, 3, 0)) == 0
    assert LugarNaFila.irrestritos.filter(pk=lugar.pk).exists()

    turno.definir(loja.matriz, time(18, 0))
    agora = _local(2026, 9, 15, 20, 0)
    assert turno.aplicar(loja.matriz, agora) == 1
    # Idempotente: a segunda leitura não acha mais ninguém para tirar.
    assert turno.aplicar(loja.matriz, agora) == 0
    assert _linhas().count() == 1


# --- O turno se cadastra na tela da filial (23/09/2026) ---------------------

SENHA = "segredo-de-teste"


@pytest.fixture
def tela(db, modulo_filiais_ligado):
    """A tela de Filiais com a caixa do turno. Quem tem `filiais.editar` é o
    titular, e é ele que cadastra o turno da loja."""
    from types import SimpleNamespace

    from django.test import Client
    from django.urls import reverse

    from contas.fabrica import aplicar
    from contas.models import Nivel, Usuario
    from plataforma.models import Empresa, Filial

    titular = Usuario.objects.create_user(
        email="dono-turno@teste.com", password=SENHA, nivel=Nivel.TITULAR)
    aplicar(titular, Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social="Turno Ltda", dono=titular)
    matriz = Filial.objects.get(empresa=empresa, e_matriz=True)
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": "dono-turno@teste.com",
                                     "senha": SENHA})
    return SimpleNamespace(empresa=empresa, matriz=matriz, cliente=cliente)


def _salvar(tela, **extra):
    dados = {"acao": "salvar", "filial": str(tela.matriz.pk),
             "nome": tela.matriz.nome, "apelido": tela.matriz.apelido}
    dados.update(extra)
    return tela.cliente.post(reverse("filiais"), dados)


def test_o_modal_da_filial_pergunta_o_fim_do_turno(tela):
    html = tela.cliente.get(reverse("filiais")).content.decode()
    assert 'name="fim_do_turno"' in html
    # `type="time"`: o navegador do celular abre o relógio, e o que chega no
    # POST é HH:MM.
    assert 'type="time"' in html
    assert "Uma hora depois desta hora" in html


def test_salvar_o_turno_pela_tela_grava(tela):
    from fila import turno

    resposta = _salvar(tela, fim_do_turno="18:00")
    assert resposta.status_code == 302
    assert turno.fim_de(tela.matriz) == time(18, 0)


def test_a_hora_em_branco_apaga_o_turno(tela):
    from fila import turno

    _salvar(tela, fim_do_turno="18:00")
    _salvar(tela, fim_do_turno="")
    assert turno.fim_de(tela.matriz) is None


def test_hora_torta_recusa_e_nao_salva_a_filial(tela):
    """A caixa recusa com a frase da tela, e o `atomic` desfaz a filial junto:
    meia gravação deixaria a loja renomeada e sem turno."""
    from fila import turno

    resposta = _salvar(tela, nome="Loja Nova", apelido="Nova",
                       fim_do_turno="25:99")
    assert resposta.status_code == 200
    assert "Escreva a hora do turno assim: 18:00." in resposta.content.decode()
    tela.matriz.refresh_from_db()
    assert tela.matriz.apelido != "Nova"
    assert turno.fim_de(tela.matriz) is None


def test_a_filial_nova_ja_pode_nascer_com_turno(tela):
    from fila import turno
    from plataforma.models import Filial

    tela.cliente.post(reverse("filiais"), {
        "acao": "criar", "nome": "Loja Nova", "apelido": "Nova",
        "fim_do_turno": "22:30"})
    nova = Filial.objects.get(apelido="Nova")
    assert turno.fim_de(nova) == time(22, 30)


def test_a_pagina_da_fila_aplica_o_turno(loja):
    """A regra roda na LEITURA — não há cron nesta instalação, e a página (e a
    consulta de 3 em 3 segundos) passa por aqui. O relógio do cenário começa às
    10:00 da loja, então o prazo das 09:00 já passou."""
    from fila import turno
    from fila.models import LugarNaFila

    turno.definir(loja.matriz, time(8, 0))
    _na_loja(loja.ana, loja.matriz, _local(2026, 9, 15, 7, 0))
    resposta = logado("ana").get("/fila")
    assert resposta.status_code == 200
    assert not LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()

# --- A loja aberta de novo (25/09/2026) --------------------------------------
#
# Pedido do cliente: "primeiro que for abrir a loja, se tiver gente lá bugado,
# ele reseta a loja". Bater o ponto fecha o de quem ficou aberto de um DIA
# ANTERIOR, nesta loja — na fila, em espera, em pausa e atendendo (o
# atendimento de ontem fecha como não venda, sem lançamento) —, com a hora do
# fim daquele dia. O relógio do `relogio` está em 15/09/2026, 13h UTC.

def _ontem_as_18():
    return _local(2026, 9, 14, 18, 0)


def _fim_de_ontem():
    return _local(2026, 9, 15, 0, 0) - timedelta(seconds=1)


def _linhas_do_esquecido():
    from contas.models import RegistroDeAuditoria

    return RegistroDeAuditoria.objects.filter(acao="fila_ponto_esquecido_fechado")


@pytest.mark.parametrize("estado", ["na_fila", "em_espera", "em_pausa"])
def test_bater_o_ponto_fecha_o_ponto_esquecido_de_ontem(loja, estado):
    from fila.acoes import bater_ponto
    from fila.models import LugarNaFila, Pausa, Presenca

    lugar = _na_loja(loja.ana, loja.matriz, _ontem_as_18(), estado=estado)
    if estado == "em_pausa":
        from tests.fila_cenario import cadastros

        Pausa.irrestritos.create(empresa=loja.empresa, pessoa=loja.ana,
                                 filial=loja.matriz, presenca=lugar.presenca,
                                 tipo=cadastros(loja.empresa).tipo,
                                 inicio=_ontem_as_18())
    bater_ponto(loja.bia, loja.matriz)

    assert not LugarNaFila.irrestritos.filter(pk=lugar.pk).exists()
    assert Presenca.irrestritos.get(pk=lugar.presenca_id).saida == _fim_de_ontem()
    assert not Pausa.irrestritos.filter(pessoa=loja.ana, fim__isnull=True).exists()
    assert _linhas_do_esquecido().count() == 1
    assert LugarNaFila.irrestritos.filter(pessoa=loja.bia, filial=loja.matriz).exists()


def test_o_atendimento_de_ontem_fecha_como_nao_venda_sem_lancamento(loja):
    from fila.acoes import bater_ponto
    from fila.indicadores import Recorte, motivos
    from fila.models import Atendimento
    from fila.periodo import Periodo

    lugar = _na_loja(loja.ana, loja.matriz, _ontem_as_18(), estado="atendendo")
    atendimento = Atendimento.irrestritos.create(
        empresa=loja.empresa, filial=loja.matriz, vendedor=loja.ana,
        presenca=lugar.presenca, inicio=_ontem_as_18())
    bater_ponto(loja.bia, loja.matriz)

    atendimento.refresh_from_db()
    assert (atendimento.resultado, atendimento.motivo_id, atendimento.fim) == (
        "nao_vendeu", None, _fim_de_ontem())
    setembro = Periodo(_local(2026, 9, 1), _local(2026, 10, 1), "intervalo", "setembro")
    assert motivos(Recorte(loja.empresa, (loja.matriz,), setembro)) == [
        ("Fechado sem lançamento", 1)]


def test_quem_bateu_o_ponto_hoje_fica(loja):
    from fila.acoes import bater_ponto
    from fila.models import LugarNaFila

    lugar = _na_loja(loja.ana, loja.matriz, _local(2026, 9, 15, 8, 0))
    bater_ponto(loja.bia, loja.matriz)
    assert LugarNaFila.irrestritos.filter(pk=lugar.pk).exists()
    assert not _linhas_do_esquecido().exists()


def test_so_a_loja_em_que_se_bate_o_ponto(loja):
    from fila.acoes import bater_ponto
    from fila.models import LugarNaFila

    lugar = _na_loja(loja.ana, loja.centro, _ontem_as_18())
    bater_ponto(loja.bia, loja.matriz)
    assert LugarNaFila.irrestritos.filter(pk=lugar.pk).exists()


def test_quem_ficou_na_pausa_depois_da_meia_noite_nao_ganha_fim_antes_do_inicio(loja):
    """A hora da saída é o fim do dia da ENTRADA, mas nunca antes da última
    mudança de estado (`desde`): quem entrou em pausa às 00:30 não pode ter a
    pausa fechada às 23:59:59 da véspera."""
    from fila.acoes import bater_ponto
    from fila.models import Pausa
    from tests.fila_cenario import cadastros

    lugar = _na_loja(loja.ana, loja.matriz, _ontem_as_18(), estado="em_pausa")
    depois = _local(2026, 9, 15, 0, 30)
    lugar.desde = depois
    lugar.save(update_fields=["desde"])
    pausa = Pausa.irrestritos.create(
        empresa=loja.empresa, pessoa=loja.ana, filial=loja.matriz,
        presenca=lugar.presenca, tipo=cadastros(loja.empresa).tipo, inicio=depois)
    bater_ponto(loja.bia, loja.matriz)
    pausa.refresh_from_db()
    assert pausa.fim >= pausa.inicio
