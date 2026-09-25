"""A mídia: por qual canal o cliente chegou (25/09/2026, pedido do cliente).

"Uma lógica de parametrização igual motivos de não venda, pausa e etc, que vai
chamar mídia — de qual canal o cliente veio —, e esse campo vai ter na venda e
na não venda." O cadastro é o quarto da mesma tela (`test_fila_cadastros.py`
prova a tela); aqui se prova o que é só dela:

- **obrigatória em todo fechamento** — o do vendedor, o do gerente que fecha
  no lugar dele e o "tirar da loja" com atendimento aberto;
- **menos quando a empresa não tem mídia ativa nenhuma**: sem esta saída, a
  fila de toda empresa travaria no dia em que isto fosse ao ar, antes de
  alguém cadastrar a primeira mídia;
- a correção do gerente troca a mídia, e o lançamento antigo, que nasceu sem,
  pode continuar sem;
- os indicadores contam por mídia, com "Sem mídia" para os números fecharem.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import (  # noqa: F401  (relogio é fixture)
    cadastros, logado, nova_loja, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    from types import SimpleNamespace

    from fila.models import Midia

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        gil=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        cad=cadastros(empresa),
        insta=Midia.irrestritos.create(empresa=empresa, nome="Instagram"),
        google=Midia.irrestritos.create(empresa=empresa, nome="Google"))


def _nao_venda(loja, midia=None):
    from fila.acoes import Lancamento

    return Lancamento("nao_vendeu", motivo_id=loja.cad.motivo.pk,
                      midia_id=midia.pk if midia else None)


def _venda(loja, midia=None):
    from fila.acoes import ItemLancado, Lancamento

    return Lancamento("vendeu", (ItemLancado(loja.cad.grupo.pk, Decimal("100")),),
                      midia_id=midia.pk if midia else None)


def _atendendo(loja, pessoa=None):
    from fila.acoes import bater_ponto, vou_atender

    pessoa = pessoa or loja.ana
    bater_ponto(pessoa, loja.matriz)
    vou_atender(pessoa, loja.matriz)
    return pessoa


def _ultimo():
    from fila.models import Atendimento

    return Atendimento.irrestritos.latest("pk")


# --- O fechamento -----------------------------------------------------------

@pytest.mark.parametrize("lancar", [_venda, _nao_venda])
def test_a_venda_e_a_nao_venda_gravam_a_midia(loja, lancar):
    from fila.acoes import finalizar

    _atendendo(loja)
    finalizar(loja.ana, loja.matriz, lancar(loja, loja.insta))
    assert _ultimo().midia == loja.insta


@pytest.mark.parametrize("lancar", [_venda, _nao_venda])
def test_sem_midia_nao_fecha(loja, lancar):
    from fila.acoes import Recusa, finalizar

    _atendendo(loja)
    with pytest.raises(Recusa, match="Escolha a mídia"):
        finalizar(loja.ana, loja.matriz, lancar(loja))
    assert _ultimo().fim is None, "a recusa não pode fechar o atendimento"


def test_empresa_sem_midia_ativa_fecha_sem_ela(loja):
    """A fila não trava no dia em que a mídia vai ao ar: sem nenhuma ativa
    cadastrada, o campo não existe na folha e não é cobrado."""
    from fila.acoes import finalizar
    from fila.models import Midia

    Midia.irrestritos.filter(empresa=loja.empresa).update(ativo=False)
    _atendendo(loja)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    assert _ultimo().midia is None


def test_midia_desativada_ou_de_outra_empresa_e_recusada(loja):
    from fila.acoes import Recusa, finalizar
    from fila.models import Midia
    from plataforma.models import Empresa

    outra = Empresa.objects.create(razao_social="Outra Ltda", dono=loja.titular)
    alheia = Midia.irrestritos.create(empresa=outra, nome="Rádio")
    loja.google.ativo = False
    loja.google.save()
    _atendendo(loja)
    for midia in (alheia, loja.google):
        with pytest.raises(Recusa, match="Mídia não encontrada"):
            finalizar(loja.ana, loja.matriz, _nao_venda(loja, midia))


def test_o_gerente_que_fecha_ou_tira_da_loja_tambem_escolhe(loja):
    from fila.acoes import Recusa
    from fila.correcoes import fechar_atendimento, tirar_da_loja

    _atendendo(loja)
    with pytest.raises(Recusa, match="Escolha a mídia"):
        fechar_atendimento(loja.gil, loja.matriz, loja.ana.pk, _nao_venda(loja),
                           observacao="esqueceu de lançar")
    with pytest.raises(Recusa, match="Escolha a mídia"):
        tirar_da_loja(loja.gil, loja.matriz, loja.ana.pk, _nao_venda(loja),
                      observacao="foi embora")
    tirar_da_loja(loja.gil, loja.matriz, loja.ana.pk, _nao_venda(loja, loja.google),
                  observacao="foi embora")
    assert _ultimo().midia == loja.google


# --- A correção -------------------------------------------------------------

def test_a_correcao_troca_a_midia_e_a_trilha_diz(loja):
    from fila.acoes import finalizar
    from fila.correcoes import editar_lancamento
    from fila.models import CorrecaoNaFila

    _atendendo(loja)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja, loja.insta))
    atendimento = _ultimo()
    editar_lancamento(loja.gil, loja.matriz, atendimento.pk,
                      _nao_venda(loja, loja.google), observacao="era do Google")

    atendimento.refresh_from_db()
    assert atendimento.midia == loja.google
    detalhe = CorrecaoNaFila.irrestritos.latest("pk").detalhe
    assert "mídia: Instagram" in detalhe and "mídia: Google" in detalhe


def test_a_midia_desativada_depois_continua_valendo_na_correcao(loja):
    from fila.acoes import finalizar
    from fila.correcoes import editar_lancamento

    _atendendo(loja)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja, loja.insta))
    loja.insta.ativo = False
    loja.insta.save()
    editar_lancamento(loja.gil, loja.matriz, _ultimo().pk,
                      _nao_venda(loja, loja.insta), observacao="só a observação")
    assert _ultimo().midia == loja.insta


def test_o_lancamento_antigo_sem_midia_pode_continuar_sem(loja):
    """Quem fechou antes da mídia existir não tem uma, e corrigir o motivo
    daquele atendimento não pode exigir inventar o canal."""
    from fila.acoes import finalizar
    from fila.correcoes import editar_lancamento
    from fila.models import Midia

    Midia.irrestritos.filter(empresa=loja.empresa).update(ativo=False)
    _atendendo(loja)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    Midia.irrestritos.filter(empresa=loja.empresa).update(ativo=True)

    editar_lancamento(loja.gil, loja.matriz, _ultimo().pk, _nao_venda(loja),
                      observacao="acertando o motivo")
    assert _ultimo().midia is None


def test_corrigir_so_a_midia_muda_a_versao_da_loja(loja, relogio):
    """As outras telas da loja só se redesenham quando a versão muda; a
    correção só da mídia não mexe em total nem em motivo."""
    from fila.acoes import finalizar
    from fila.estado import versao_da_fila

    relogio[0] = timezone.now()   # a versão olha os lançamentos de HOJE
    _atendendo(loja)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja, loja.insta))
    antes = versao_da_fila(loja.matriz)
    # Direto no banco, e não por `editar_lancamento`: a correção também conta
    # na versão, e o que se prova aqui é a parte da mídia.
    type(_ultimo()).irrestritos.filter(pk=_ultimo().pk).update(midia=loja.google)
    assert versao_da_fila(loja.matriz) != antes


# --- A página ---------------------------------------------------------------

def test_a_folha_de_fechar_oferece_so_as_ativas(loja):
    loja.google.ativo = False
    loja.google.save()
    _atendendo(loja)
    html = logado("ana").get(reverse("fila")).content.decode()

    assert 'name="midia"' in html
    assert ">Instagram<" in html
    assert ">Google<" not in html


def test_sem_midia_cadastrada_a_folha_nao_tem_o_campo(loja):
    from fila.models import Midia

    Midia.irrestritos.filter(empresa=loja.empresa).delete()
    _atendendo(loja)
    assert 'name="midia"' not in logado("ana").get(reverse("fila")).content.decode()


def test_fechar_pela_pagina_grava_a_midia(loja):
    _atendendo(loja)
    logado("ana").post(reverse("fila_agir"), {
        "acao": "finalizar", "resultado": "nao_vendeu",
        "motivo": str(loja.cad.motivo.pk), "midia": str(loja.insta.pk)})
    assert _ultimo().midia == loja.insta


def test_os_lancamentos_de_hoje_mostram_a_midia(loja, relogio):
    from fila.acoes import finalizar

    relogio[0] = timezone.now()   # a lista é a de HOJE
    _atendendo(loja)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja, loja.insta))
    html = logado("gil").get(reverse("fila")).content.decode()
    assert '<span class="fila-lanc-midia">Instagram</span>' in html


def test_a_correcao_pela_pagina_abre_com_a_midia_marcada(loja):
    from fila.acoes import finalizar

    _atendendo(loja)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja, loja.insta))
    html = logado("gil").get(
        f"{reverse('fila')}?folha=editar&atendimento={_ultimo().pk}").content.decode()
    assert f'name="midia" value="{loja.insta.pk}" checked' in html


# --- Os indicadores ---------------------------------------------------------

def _local(*args):
    return timezone.make_aware(datetime(*args))


def test_por_midia_conta_atendimentos_vendas_e_os_sem_midia(loja):
    from fila.indicadores import Recorte, midias
    from fila.models import Atendimento, Presenca
    from fila.periodo import Periodo

    presenca = Presenca.irrestritos.create(
        empresa=loja.empresa, filial=loja.matriz, pessoa=loja.ana,
        entrada=_local(2026, 9, 1, 8), saida=_local(2026, 9, 30, 18))
    d = _local(2026, 9, 10, 10)

    def grava(midia, vendeu):
        Atendimento.irrestritos.create(
            empresa=loja.empresa, filial=loja.matriz, vendedor=loja.ana,
            presenca=presenca, inicio=d, fim=d, midia=midia,
            resultado="vendeu" if vendeu else "nao_vendeu",
            motivo=None if vendeu else loja.cad.motivo,
            total=Decimal("100" if vendeu else "0"))

    for midia, vendeu in ((loja.insta, True), (loja.insta, False),
                          (loja.insta, True), (loja.google, False), (None, True)):
        grava(midia, vendeu)

    setembro = Periodo(_local(2026, 9, 1), _local(2026, 10, 1), "intervalo", "setembro")
    recorte = Recorte(loja.empresa, (loja.matriz,), setembro)
    assert midias(recorte) == [("Instagram", 3, 2), ("Google", 1, 0),
                               ("Sem mídia", 1, 1)]
    assert midias(recorte, vendedor=loja.gil) == []


def test_o_painel_mostra_a_lista_por_midia(loja):
    html = logado("sylvia").get(reverse("inicio")).content.decode()
    assert "Por mídia" in html


def test_a_porcentagem_da_lista_por_midia_e_a_conversao():
    """Na lista "Por mídia" a porcentagem é a CONVERSÃO do canal, e não a
    fatia do total: com as duas lado a lado ninguém sabia qual era qual (visto
    no navegador antes de ir ao ar). As outras listas continuam com a fatia."""
    from fila.graficos import lista_ranqueada
    from fila.views_indicadores import _atendidos_e_vendas, _conversao

    html = lista_ranqueada(
        [("Instagram", 3, _atendidos_e_vendas(3, 2), _conversao(3, 2)),
         ("Google", 1, _atendidos_e_vendas(1, 0), _conversao(1, 0))], "venda")
    assert '<span class="ind-rank-valor">2 de 3</span>' in html
    assert '<span class="ind-rank-parte">67%</span>' in html
    assert '<span class="ind-rank-parte">0%</span>' in html
    assert '<span class="ind-rank-parte">75%</span>' not in html, "a fatia do total"


def test_as_opcoes_cadastradas_saem_em_caixa_alta_nas_folhas(loja):
    """25/09/2026, com o print da folha na mão: "aqui está aparecendo como
    foi cadastrado em vez de transformar tudo em maiúsculo". A caixa alta dos
    cadastros (18/09/2026) valia só para a LISTA do cadastro; agora vale também
    para as opções das folhas da fila — mídias, motivos, tipos de pausa e o
    grupo de item. Pela folha, e não pelo dado: o nome continua gravado como a
    pessoa escreveu. Nome de pessoa (a folha de mover) não entra."""
    import re
    from pathlib import Path

    _atendendo(loja)
    html = logado("ana").get(reverse("fila")).content.decode()
    for legenda in ("Como o cliente chegou?", "Por que não comprou?"):
        assert re.search(r'<fieldset class="fila-opcoes fila-cadastro[^"]*">\s*'
                         r'<legend class="msec-title">' + re.escape(legenda), html), legenda
    assert 'class="ctl fila-cadastro" name="grupo"' in html

    folha = Path("fila/static/fila/fila.css").read_text(encoding="utf-8")
    assert re.search(r"\.fila-cadastro \.fila-opcao > span[^{]*\{\s*text-transform: uppercase", folha)
    assert "select.fila-cadastro option" in folha
