"""As pausas da gestão: Administrativa e Gestão (25/09/2026, pedido do cliente).

"Preciso de 2 pausas fixas no código, pausa administrativa e de gestão, e só
o dono, supervisor e gerente vão poder usar elas, e para voltar na fila só
eles podem recolocar também, e vão ter que colocar qual lugar da fila o
vendedor vai voltar."

- fixas no código, e não cadastro: a `Pausa` tem um tipo cadastrado OU uma
  pausa fixa, e o banco recusa as duas coisas juntas e nenhuma;
- só quem gerencia a loja põe (pela folha "Pôr em pausa") e recoloca;
- o vendedor não as vê na folha dele e não sai delas sozinho;
- quem recoloca escolhe a posição, obrigatória, do 1º ao fim da fila;
- nos indicadores elas aparecem no "Tempo em pausa", mas não pesam no
  vendedor: foi a gestão que o tirou da fila, e não ele que parou.
"""

from datetime import datetime, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import (  # noqa: F401  (relogio é fixture)
    cadastros, logado, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db

MOTIVO = "reunião com a gerência"


@pytest.fixture
def loja(relogio):
    from types import SimpleNamespace

    from fila.acoes import bater_ponto

    empresa, matriz, titular = sylvia()
    loja = SimpleNamespace(
        empresa=empresa, matriz=matriz, titular=titular,
        gil=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        caio=pessoa_na_loja("caio", empresa, matriz),
        cad=cadastros(empresa))
    for pessoa in (loja.ana, loja.bia, loja.caio):
        bater_ponto(pessoa, matriz)
    return loja


def _ordem(filial):
    from fila.estado import na_fila

    return [lugar.pessoa.nome for lugar in na_fila(filial)]


def _por_na_administrativa(loja, pessoa=None):
    from fila.correcoes import por_em_pausa

    por_em_pausa(loja.gil, loja.matriz, (pessoa or loja.ana).pk, None,
                 fixa="administrativa", observacao=MOTIVO)


def _pausa_aberta(pessoa):
    from fila.models import Pausa

    return Pausa.irrestritos.get(pessoa=pessoa, fim__isnull=True)


# --- Pôr --------------------------------------------------------------------

def test_o_gerente_poe_na_pausa_administrativa(loja):
    from fila.estado import retrato
    from fila.models import CorrecaoNaFila, Estado, LugarNaFila

    _por_na_administrativa(loja)

    pausa = _pausa_aberta(loja.ana)
    assert (pausa.fixa, pausa.tipo_id) == ("administrativa", None)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_PAUSA
    linha = retrato(loja.matriz, loja.gil).em_pausa[0]
    assert (linha.tipo_de_pausa, linha.pausa_fixa) == ("Administrativa", True)
    assert CorrecaoNaFila.irrestritos.latest("pk").detalhe == "Administrativa"


def test_a_pausa_de_gestao_tambem(loja):
    from fila.correcoes import por_em_pausa

    por_em_pausa(loja.gil, loja.matriz, loja.ana.pk, None, fixa="gestao",
                 observacao=MOTIVO)
    assert _pausa_aberta(loja.ana).fixa == "gestao"


def test_pausa_fixa_que_nao_existe_e_recusada(loja):
    from fila.acoes import Recusa
    from fila.correcoes import por_em_pausa

    with pytest.raises(Recusa, match="Escolha o tipo de pausa"):
        por_em_pausa(loja.gil, loja.matriz, loja.ana.pk, None, fixa="almoco",
                     observacao=MOTIVO)


def test_o_banco_recusa_tipo_e_fixa_juntos_e_nenhum_dos_dois(loja):
    from fila.models import Pausa, Presenca

    presenca = Presenca.irrestritos.filter(pessoa=loja.bia).first()
    base = dict(empresa=loja.empresa, pessoa=loja.bia, filial=loja.matriz,
                presenca=presenca, inicio=timezone.now())
    for extra in ({"tipo": loja.cad.tipo, "fixa": "gestao"}, {}):
        with pytest.raises(IntegrityError), transaction.atomic():
            Pausa.irrestritos.create(**base, **extra)


# --- O vendedor -------------------------------------------------------------

def test_o_vendedor_nao_escolhe_a_pausa_fixa(loja):
    from fila.models import Pausa

    cliente = logado("ana")
    html = cliente.get(reverse("fila")).content.decode()
    pausa = html.split('id="folha-pausa"')[1].split("</form>")[0]
    assert "Administrativa" not in pausa and "Gestão" not in pausa

    cliente.post(reverse("fila_agir"), {"acao": "pausar", "tipo": "administrativa"})
    assert not Pausa.irrestritos.filter(pessoa=loja.ana).exists()


def test_o_vendedor_nao_sai_sozinho_da_pausa_fixa(loja):
    from fila.acoes import Recusa, voltar_para_a_fila

    _por_na_administrativa(loja)
    with pytest.raises(Recusa, match="Só a gestão"):
        voltar_para_a_fila(loja.ana, loja.matriz)

    html = logado("ana").get(reverse("fila")).content.decode()
    assert 'value="voltar"' not in html
    assert "Só a gestão tira você desta pausa." in html


def test_a_pausa_comum_continua_saindo_sozinha(loja):
    from fila.acoes import pausar, voltar_para_a_fila

    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    voltar_para_a_fila(loja.ana, loja.matriz)
    assert _ordem(loja.matriz)[-1] == "Ana"


# --- Recolocar --------------------------------------------------------------

@pytest.mark.parametrize("posicao, ordem", [
    (1, ["Ana", "Bia", "Caio"]),
    (2, ["Bia", "Ana", "Caio"]),
    (3, ["Bia", "Caio", "Ana"]),
])
def test_recolocar_na_posicao_escolhida(loja, posicao, ordem):
    from fila.correcoes import recolocar
    from fila.models import CorrecaoNaFila, Pausa

    _por_na_administrativa(loja)
    recolocar(loja.gil, loja.matriz, loja.ana.pk, posicao, observacao=MOTIVO)

    assert _ordem(loja.matriz) == ordem
    assert not Pausa.irrestritos.filter(pessoa=loja.ana, fim__isnull=True).exists()
    correcao = CorrecaoNaFila.irrestritos.latest("pk")
    assert (correcao.acao, correcao.detalhe) == (
        "recolocar", f"Administrativa → {posicao}º")


def test_recolocar_com_a_fila_vazia(loja):
    from fila.acoes import sair_da_loja
    from fila.correcoes import recolocar

    _por_na_administrativa(loja)
    sair_da_loja(loja.bia, loja.matriz)
    sair_da_loja(loja.caio, loja.matriz)
    recolocar(loja.gil, loja.matriz, loja.ana.pk, 1, observacao=MOTIVO)
    assert _ordem(loja.matriz) == ["Ana"]


def test_com_a_fila_vazia_a_folha_so_oferece_o_primeiro_lugar(loja):
    from fila.acoes import sair_da_loja

    _por_na_administrativa(loja)
    sair_da_loja(loja.bia, loja.matriz)
    sair_da_loja(loja.caio, loja.matriz)
    html = logado("gil").get(reverse("fila")).content.decode()
    folha = html.split('id="fila-posicoes"')[1].split("</fieldset>")[0]
    assert "1º · primeiro da fila" in folha
    assert folha.count('name="posicao"') == 1


@pytest.mark.parametrize("posicao", [None, 0, 4])
def test_a_posicao_e_obrigatoria_e_dentro_da_fila(loja, posicao):
    from fila.acoes import Recusa
    from fila.correcoes import recolocar

    _por_na_administrativa(loja)
    with pytest.raises(Recusa, match="Escolha a posição"):
        recolocar(loja.gil, loja.matriz, loja.ana.pk, posicao, observacao=MOTIVO)
    assert _pausa_aberta(loja.ana).fixa == "administrativa"


def test_recolocar_e_so_da_pausa_fixa_e_tirar_da_pausa_so_da_comum(loja):
    from fila.acoes import Recusa, pausar
    from fila.correcoes import recolocar, tirar_da_pausa

    pausar(loja.bia, loja.matriz, loja.cad.tipo.pk)
    with pytest.raises(Recusa, match="não está numa pausa da gestão"):
        recolocar(loja.gil, loja.matriz, loja.bia.pk, 1, observacao=MOTIVO)

    _por_na_administrativa(loja)
    with pytest.raises(Recusa, match="Recolocar na fila"):
        tirar_da_pausa(loja.gil, loja.matriz, loja.ana.pk, observacao=MOTIVO)


def test_so_quem_gerencia_recoloca(loja):
    from fila.models import Pausa

    _por_na_administrativa(loja)
    resposta = logado("bia").post(reverse("fila_agir"), {
        "acao": "recolocar", "pessoa": str(loja.ana.pk), "posicao": "1",
        "motivo_da_correcao": MOTIVO})
    assert resposta.status_code == 404
    assert Pausa.irrestritos.filter(pessoa=loja.ana, fim__isnull=True).exists()


def test_pela_pagina_o_gerente_poe_e_recoloca(loja):
    cliente = logado("gil")
    cliente.post(reverse("fila_agir"), {
        "acao": "por_em_pausa", "pessoa": str(loja.ana.pk), "tipo": "gestao",
        "motivo_da_correcao": MOTIVO})
    assert _pausa_aberta(loja.ana).fixa == "gestao"

    html = cliente.get(reverse("fila")).content.decode()
    assert 'data-estado="em_pausa_fixa"' in html
    folha = html.split('id="folha-recolocar"')[1].split("</form>")[0]
    assert 'name="posicao" value="1"' in folha and 'name="posicao" value="3"' in folha
    # Pela pessoa que fica NA FRENTE, como se fala numa fila (25/09/2026, com
    # o print do cliente: "ficou meio confuso"). Era "2º · antes de Caio".
    assert "1º · primeiro da fila" in folha
    assert "2º · depois de Bia" in folha
    assert "3º · depois de Caio (fim da fila)" in folha
    assert "antes de" not in folha

    cliente.post(reverse("fila_agir"), {
        "acao": "recolocar", "pessoa": str(loja.ana.pk), "posicao": "2",
        "motivo_da_correcao": MOTIVO})
    assert _ordem(loja.matriz) == ["Bia", "Ana", "Caio"]


def test_a_folha_do_gerente_oferece_as_fixas_separadas(loja):
    html = logado("gil").get(reverse("fila")).content.decode()
    folha = html.split('id="folha-por_em_pausa"')[1].split("</form>")[0]
    assert 'name="tipo" value="administrativa"' in folha
    assert 'name="tipo" value="gestao"' in folha
    assert f'name="tipo" value="{loja.cad.tipo.pk}"' in folha


# --- Indicadores ------------------------------------------------------------

def _local(*args):
    return timezone.make_aware(datetime(*args))


def test_aparece_no_tempo_em_pausa_e_nao_pesa_no_vendedor(loja):
    from fila.indicadores import Recorte, pausa_por_tipo, ranking, ranking_por_loja
    from fila.models import Atendimento, Pausa, Presenca
    from fila.periodo import Periodo

    presenca = Presenca.irrestritos.filter(pessoa=loja.ana).first()
    d = _local(2026, 9, 10, 10)
    Atendimento.irrestritos.create(
        empresa=loja.empresa, filial=loja.matriz, vendedor=loja.ana,
        presenca=presenca, inicio=d, fim=d, resultado="nao_vendeu",
        motivo=loja.cad.motivo)
    Pausa.irrestritos.create(empresa=loja.empresa, pessoa=loja.ana,
                             filial=loja.matriz, presenca=presenca,
                             tipo=loja.cad.tipo, inicio=d,
                             fim=d + timedelta(minutes=10))
    Pausa.irrestritos.create(empresa=loja.empresa, pessoa=loja.ana,
                             filial=loja.matriz, presenca=presenca,
                             fixa="gestao", inicio=d + timedelta(hours=1),
                             fim=d + timedelta(hours=1, minutes=30))

    setembro = Periodo(_local(2026, 9, 1), _local(2026, 10, 1), "intervalo", "setembro")
    recorte = Recorte(loja.empresa, (loja.matriz,), setembro)
    assert pausa_por_tipo(recorte) == [("Gestão", 30), ("Almoço", 10)]
    # O painel do vendedor é recortado por ele, e a pausa da gestão não é dele.
    assert pausa_por_tipo(recorte, vendedor=loja.ana) == [("Almoço", 10)]
    ana = next(l for l in ranking(recorte) if l.pk == loja.ana.pk)
    assert ana.pausa == timedelta(minutes=10)
    ana_na_loja = next(l for l in ranking_por_loja(recorte) if l["pk"] == loja.ana.pk)
    assert ana_na_loja["pausa"] == timedelta(minutes=10)


def test_as_posicoes_do_recolocar_seguem_a_fila_de_agora(loja):
    """As folhas são desenhadas quando a página abre, e a consulta de 3 em 3
    segundos troca só os pedaços. Com as posições congeladas, o gerente que
    punha alguém na pausa pela página via "2º · antes de Caio" com o próprio
    Caio na pausa (visto no navegador antes de ir ao ar). As posições são um
    pedaço, e vêm na consulta."""
    from fila.tela import PEDACOS

    assert "posicoes" in PEDACOS
    cliente = logado("gil")
    html = cliente.get(reverse("fila")).content.decode()
    assert '<div id="fila-posicoes">' in html.split('id="folha-recolocar"')[1]

    _por_na_administrativa(loja, loja.caio)
    dados = cliente.get(reverse("fila_estado"), {"versao": "velha"}).json()
    posicoes = dados["html"]["posicoes"]
    assert "2º · depois de Ana" in posicoes
    assert "3º · depois de Bia (fim da fila)" in posicoes
    assert "Caio" not in posicoes
