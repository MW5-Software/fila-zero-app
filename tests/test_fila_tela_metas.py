"""A tela de metas (spec 2026-09-15-fila-metas, "Cadastro")."""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import logado, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


@pytest.fixture
def rede():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    centro = nova_loja(empresa, "Centro")
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, centro=centro,
        ana=pessoa_na_loja("ana", empresa, matriz),
        caio=pessoa_na_loja("caio", empresa, centro),
        gil=pessoa_na_loja("gil", empresa, centro, cargo="gerente"),
        sara=pessoa_na_loja("sara", empresa, None, cargo="supervisor"))


def _mes_atual() -> str:
    return f"{timezone.localdate():%Y-%m}"


def _get(cliente, **params):
    resposta = cliente.get(reverse("fila_metas"), params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_vendedor_nao_abre(rede):
    assert logado("caio").get(reverse("fila_metas")).status_code == 404


def test_gerente_ve_so_a_loja_dele_e_a_forjada_e_descartada(rede):
    html = _get(logado("gil"), loja=str(rede.matriz.pk))
    assert "Caio" in html and "Ana" not in html


def test_loja_da_url_que_nao_e_numero_nao_derruba(rede):
    for bruto in ("²", "9" * 30, "abc"):
        assert "Metas de venda" in _get(logado("sara"), loja=bruto)


def test_supervisor_escolhe_a_loja(rede):
    html = _get(logado("sara"), loja=str(rede.matriz.pk))
    assert "Ana" in html and "Caio" not in html


def test_salvar_grava(rede):
    from fila.metas import meta_da_loja

    gil = logado("gil")
    _get(gil)
    resposta = gil.post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "250.000,00", f"valor_{rede.caio.pk}": "30000",
        f"valor_{rede.gil.pk}": "99999"})
    assert resposta.status_code == 302
    mes = timezone.localdate().replace(day=1)
    assert meta_da_loja(rede.centro, mes) == Decimal("250000")
    from fila.models import MetaDeVenda
    # A linha do próprio Gil não existe na lista (ele gerencia, e quem gerencia
    # não tem meta), e o campo forjado com o pk dele não acha alvo: `gravar` só
    # lê as chaves da lista que ele mesmo montou.
    assert not MetaDeVenda.irrestritos.filter(pessoa=rede.gil).exists()


def test_a_propria_linha_vem_travada_com_o_parametro_ligado(rede):
    """Quem edita só aparece na lista quando também entra nela — no cargo de
    fábrica, isso é o `meta_para_gestor` marcado. Aí a linha dele vem
    DESABILITADA, e o POST com o pk dele não grava: ninguém define a própria
    meta (`fila/metas.gravar`)."""
    import re

    from plataforma.parametro_catalogo import definir

    definir("meta_para_gestor", "1")
    gil = logado("gil")
    html = _get(gil)
    assert f'name="valor_{rede.gil.pk}"' in html
    propria = re.search(rf'<input[^>]*name="valor_{rede.gil.pk}"[^>]*>', html).group(0)
    assert "disabled" in propria

    resposta = gil.post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "250.000,00", f"valor_{rede.caio.pk}": "30000",
        f"valor_{rede.gil.pk}": "99999"})
    assert resposta.status_code == 302
    from fila.models import MetaDeVenda
    assert not MetaDeVenda.irrestritos.filter(pessoa=rede.gil).exists()


def test_valor_invalido_mostra_o_erro_e_nao_grava(rede):
    from fila.models import MetaDeVenda

    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "1000", f"valor_{rede.caio.pk}": "abc"})
    assert resposta.status_code == 200
    assert "Digite um valor em reais." in resposta.content.decode()
    assert not MetaDeVenda.irrestritos.exists()


def test_mes_encerrado_so_leitura_e_post_forjado_recusado(rede):
    from fila.models import MetaDeVenda

    passado = date(2020, 1, 1)
    html = _get(logado("gil"), mes="2020-01")
    assert "Mês encerrado: as metas não se editam mais." in html
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": "2020-01", "loja": str(rede.centro.pk),
        "valor_loja": "1000"})
    assert resposta.status_code == 200
    assert not MetaDeVenda.irrestritos.filter(mes=passado).exists()


def test_copiar_preenche_e_nao_salva(rede):
    from fila.metas import mes_anterior
    from fila.models import MetaDeVenda

    mes = timezone.localdate().replace(day=1)
    MetaDeVenda.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                   pessoa=None, mes=mes_anterior(mes),
                                   valor=Decimal("180000"))
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "copiar", "mes": _mes_atual(), "loja": str(rede.centro.pk)})
    assert resposta.status_code == 200
    assert 'value="180.000,00"' in resposta.content.decode()
    assert not MetaDeVenda.irrestritos.filter(mes=mes).exists()


def test_soma_dos_vendedores_ao_lado_da_meta_da_loja(rede):
    gil = logado("gil")
    gil.post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "50000", f"valor_{rede.caio.pk}": "30000"})
    html = _get(gil)
    assert "As metas dos vendedores somam" in html and "R$ 30.000,00" in html
    assert "Faltam R$ 20.000,00 para cobrir a loja" in html


# --- A tela refeita (17/09/2026) --------------------------------------------

def _venda(rede, pessoa, loja, valor):
    from datetime import timedelta

    from fila.models import Atendimento, Presenca

    agora = timezone.now()
    presenca = Presenca.irrestritos.create(empresa=rede.empresa, filial=loja, pessoa=pessoa,
                                          entrada=agora, saida=agora)
    Atendimento.irrestritos.create(empresa=rede.empresa, filial=loja, vendedor=pessoa,
                                   presenca=presenca, inicio=agora - timedelta(minutes=5),
                                   fim=agora, resultado="vendeu", total=Decimal(valor))


def _meta(rede, loja, valor, pessoa=None, mes=None):
    from fila.models import MetaDeVenda

    MetaDeVenda.irrestritos.create(empresa=rede.empresa, filial=loja, pessoa=pessoa,
                                   mes=mes or timezone.localdate().replace(day=1),
                                   valor=Decimal(valor))


def test_o_mes_e_o_titulo_com_as_setas(rede):
    from fila.metas import mes_anterior, mes_seguinte
    from nucleo.views import _MESES

    hoje = timezone.localdate()
    html = _get(logado("gil"))
    assert f"{_MESES[hoje.month - 1].capitalize()} de {hoje.year}" in html
    mes = hoje.replace(day=1)
    assert f"mes={mes_anterior(mes):%Y-%m}" in html and f"mes={mes_seguinte(mes):%Y-%m}" in html
    assert f"Dia {hoje.day} de" in html


def test_cada_linha_mostra_o_vendido_a_meta_anterior_e_o_ritmo(rede):
    from fila.metas import mes_anterior

    mes = timezone.localdate().replace(day=1)
    _meta(rede, rede.centro, "40000", pessoa=rede.caio)
    _meta(rede, rede.centro, "28000", pessoa=rede.caio, mes=mes_anterior(mes))
    _venda(rede, rede.caio, rede.centro, "44000")
    html = _get(logado("gil"))
    linha = html[html.index(f'data-pessoa="{rede.caio.pk}"'):]
    linha = linha[:linha.index("</li>")]
    assert "R$ 44.000,00" in linha
    assert "R$ 28.000,00" in linha
    assert "Bateu" in linha and 'data-ritmo="bateu"' in linha


def test_a_regua_mostra_quem_cobre_a_meta_da_loja(rede):
    _meta(rede, rede.centro, "50000")
    _meta(rede, rede.centro, "30000", pessoa=rede.caio)
    html = _get(logado("gil"))
    regua = html[html.index('class="metas-regua"'):]
    regua = regua[:regua.index("</div>")]
    assert "Caio" in regua and "width: 60.00%" in regua


def test_salvar_ja_distribui_a_meta_da_loja(rede):
    """Sem botão desde 18/09/2026: salvar a meta geral deixa os vendedores com
    a parte igual, e a tela volta com tudo gravado."""
    from fila.models import MetaDeVenda

    dora = pessoa_na_loja("dora", rede.empresa, rede.centro)
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "90.000,00", f"valor_{rede.caio.pk}": "30.000,00",
        f"valor_{dora.pk}": ""})
    assert resposta.status_code == 302
    mes = timezone.localdate().replace(day=1)
    metas = dict(MetaDeVenda.irrestritos
                 .filter(mes=mes, pessoa__isnull=False)
                 .values_list("pessoa__nome", "valor"))
    assert metas == {"Caio": Decimal("30000"), "Dora": Decimal("45000")}


def test_a_soma_dos_vendedores_nao_passa_a_meta_da_loja(rede):
    """23/09/2026, pedido do cliente: "quando eu vou manualmente destrinchar a
    meta dos vendedores individualizada e ela passar o valor da meta total,
    colocar um aviso e não deixar salvar".

    O aviso sai no campo da meta da loja, que é a referência da soma, e NADA é
    gravado — nem a meta da loja, nem as dos vendedores.
    """
    from fila.models import MetaDeVenda

    dora = pessoa_na_loja("dora", rede.empresa, rede.centro)
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "100.000,00", f"valor_{rede.caio.pk}": "70.000,00",
        f"valor_{dora.pk}": "50.000,00"})
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "acima da meta da loja" in html
    assert "R$ 120.000,00" in html and "R$ 100.000,00" in html
    assert "Nada foi salvo" in html
    assert not MetaDeVenda.irrestritos.exists()


def test_a_distribuicao_tambem_respeita_o_teto(rede):
    """O caso que o cliente viveu: a meta da loja distribui a parte IGUAL para
    quem ficou em branco, e o que já estava digitado fica. Com a loja em
    R$ 90.000,00 e um vendedor em R$ 50.000,00, o vizinho em branco receberia
    R$ 45.000,00 e a soma passaria para R$ 95.000,00 — a gravação é recusada em
    vez de gravar a loja estourada."""
    from fila.models import MetaDeVenda

    dora = pessoa_na_loja("dora", rede.empresa, rede.centro)
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "90.000,00", f"valor_{rede.caio.pk}": "50.000,00",
        f"valor_{dora.pk}": ""})
    assert resposta.status_code == 200
    assert "R$ 95.000,00" in resposta.content.decode()
    assert not MetaDeVenda.irrestritos.exists()


def test_a_soma_igual_a_meta_da_loja_salva(rede):
    """O teto é a soma IGUAL: cobrir exatamente a loja é o que se quer."""
    from fila.models import MetaDeVenda

    dora = pessoa_na_loja("dora", rede.empresa, rede.centro)
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "100.000,00", f"valor_{rede.caio.pk}": "60.000,00",
        f"valor_{dora.pk}": "40.000,00"})
    assert resposta.status_code == 302
    mes = timezone.localdate().replace(day=1)
    assert MetaDeVenda.irrestritos.filter(mes=mes).count() == 3


def test_apagar_uma_meta_abaixo_do_teto_salva(rede):
    """A recusa não é uma parede: tirar a meta de quem estourou passa."""
    from fila.models import MetaDeVenda

    mes = timezone.localdate().replace(day=1)
    _meta(rede, rede.centro, "100000")
    _meta(rede, rede.centro, "60000", pessoa=rede.caio)
    _meta(rede, rede.centro, "60000", pessoa=rede.ana)
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        f"valor_{rede.ana.pk}": ""})
    assert resposta.status_code == 302
    assert not MetaDeVenda.irrestritos.filter(mes=mes, pessoa=rede.ana).exists()


def test_a_tela_nao_tem_botao_de_dividir(rede):
    """O botão saiu: a distribuição é do servidor, no salvar — a mesma tela
    funciona sem JavaScript e sem clique nenhum."""
    html = _get(logado("gil"))
    assert 'value="dividir"' not in html
    assert "Dividir" not in html


def test_mes_encerrado_nao_tem_salvar_nem_copiar(rede):
    html = _get(logado("gil"), mes="2020-01")
    assert "Salvar metas" not in html
    assert 'value="copiar"' not in html


def test_os_campos_de_valor_tem_a_mascara(rede):
    html = _get(logado("gil"))
    assert 'name="valor_loja" inputmode="numeric" data-valor' in html
    assert "/static/fila/valor.js" in html and "/static/fila/metas.js" in html
