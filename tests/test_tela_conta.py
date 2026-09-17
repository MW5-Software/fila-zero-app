"""A tela de Conta (spec 2026-09-17, E4).

O topo da hierarquia: conta → empresas → lojas. Ela responde "o que é esta
conta e o que tem dentro dela" — os dados do cliente, as empresas e as lojas
de cada uma. É leitura: quem cadastra empresa é a MW5, na tela de Empresas.
"""

import pytest
from django.test import Client
from django.urls import reverse

from contas.fabrica import aplicar
from contas.models import Nivel, Usuario

SENHA = "segredo-de-teste"


def _entrar(email):
    c = Client()
    c.post(reverse("entrar"), {"usuario": email, "senha": SENHA})
    return c


@pytest.fixture
def conta_com_duas(db):
    from plataforma.models import Empresa, Filial

    from tests.conftest import alocar

    titular = Usuario.objects.create_user(
        email="dono-conta@teste.com", password=SENHA, nome="Sylvia",
        nivel=Nivel.TITULAR)
    aplicar(titular, Nivel.TITULAR)
    alfa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=titular)
    Filial.objects.create(empresa=alfa, nome="Loja Centro", apelido="Centro")
    vendedor = Usuario.objects.create_user(
        email="vend-conta@teste.com", password=SENHA, nome="Ana",
        nivel=Nivel.MEMBRO, dono=titular)
    alocar(vendedor, alfa, "vendedor",
           filial=Filial.objects.get(empresa=alfa, e_matriz=True))
    mw5 = Usuario.objects.create_superuser(email="mw5-conta@teste.com",
                                           password=SENHA)
    return {"titular": titular, "alfa": alfa, "beta": beta, "mw5": mw5,
            "dele": _entrar("dono-conta@teste.com"),
            "vendedor": _entrar("vend-conta@teste.com"),
            "da_mw5": _entrar("mw5-conta@teste.com")}


def test_o_titular_ve_os_dados_da_conta_e_as_empresas(conta_com_duas):
    html = conta_com_duas["dele"].get(reverse("conta")).content.decode()
    assert "dono-conta@teste.com" in html
    assert "Alfa Ltda" in html and "Beta Ltda" in html
    assert "2" in html


def test_a_tela_mostra_as_lojas_de_cada_empresa(conta_com_duas):
    html = conta_com_duas["dele"].get(reverse("conta")).content.decode()
    assert "Centro" in html and "Matriz" in html


def test_o_vendedor_nao_abre(conta_com_duas):
    assert conta_com_duas["vendedor"].get(reverse("conta")).status_code == 404


def test_a_mw5_ve_a_conta_do_contexto(conta_com_duas):
    html = conta_com_duas["da_mw5"].get(reverse("conta")).content.decode()
    assert "Alfa Ltda" in html or "Beta Ltda" in html


def test_a_tela_nao_cadastra_empresa(conta_com_duas):
    """Quem cria empresa é a MW5, na tela de Empresas: dois caminhos para o
    mesmo cadastro divergem no primeiro campo novo."""
    html = conta_com_duas["dele"].get(reverse("conta")).content.decode()
    assert "Nova empresa" not in html
