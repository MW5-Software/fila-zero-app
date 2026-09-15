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


def test_salvar_grava_e_a_propria_linha_vem_travada(rede):
    from fila.metas import meta_da_loja

    gil = logado("gil")
    html = _get(gil)
    assert f'name="valor_{rede.gil.pk}"' in html
    import re
    propria = re.search(rf'<input[^>]*name="valor_{rede.gil.pk}"[^>]*>', html).group(0)
    assert "disabled" in propria
    resposta = gil.post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "250.000,00", f"valor_{rede.caio.pk}": "30000",
        f"valor_{rede.gil.pk}": "99999"})
    assert resposta.status_code == 302
    mes = timezone.localdate().replace(day=1)
    assert meta_da_loja(rede.centro, mes) == Decimal("250000")
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
    assert 'value="180000,00"' in resposta.content.decode()
    assert not MetaDeVenda.irrestritos.filter(mes=mes).exists()


def test_soma_dos_vendedores_ao_lado_da_meta_da_loja(rede):
    gil = logado("gil")
    gil.post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "50000", f"valor_{rede.caio.pk}": "30000"})
    assert "Vendedores somam R$ 30.000,00 de R$ 50.000,00" in _get(gil)
