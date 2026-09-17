"""Duas empresas na mesma conta (spec 2026-09-17).

O que se prova aqui é o ISOLAMENTO: a fronteira do dado de negócio é a
empresa, e o `conta_guid` continua obrigatório e igual nas duas.
"""

import pytest

from tests.conftest import abrir_conta, alocar, email_de

pytestmark = pytest.mark.django_db

SENHA = "segredo-de-teste"


@pytest.fixture
def duas_empresas():
    from types import SimpleNamespace

    from contas.models import Usuario
    from plataforma.models import Empresa, Filial

    from tests.conftest import empresa_do_teste

    alfa = empresa_do_teste()
    titular = Usuario.objects.filter(pk=alfa.dono_id).first()
    if titular is None:
        titular = abrir_conta(alfa, "sylvia", SENHA)
        alfa.refresh_from_db()
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=titular)
    return SimpleNamespace(
        titular=titular, alfa=alfa, beta=beta,
        loja_alfa=Filial.objects.filter(empresa=alfa, e_matriz=True).first(),
        loja_beta=Filial.objects.filter(empresa=beta, e_matriz=True).first())


def test_a_conta_tem_duas_empresas_e_cada_uma_nasce_com_a_matriz(duas_empresas):
    d = duas_empresas
    assert list(d.titular.empresas_da_conta.order_by("pk")) == [d.alfa, d.beta]
    assert d.loja_alfa is not None and d.loja_beta is not None
    assert d.loja_alfa.empresa_id == d.alfa.pk and d.loja_beta.empresa_id == d.beta.pk


def test_as_duas_empresas_levam_o_mesmo_conta_guid(duas_empresas):
    d = duas_empresas
    assert d.alfa.conta_id == d.titular.guid == d.beta.conta_id
    assert d.loja_beta.conta_id == d.titular.guid


def test_o_dado_de_negocio_de_uma_empresa_nao_aparece_na_outra(duas_empresas):
    from fila.models import GrupoDeItem

    d = duas_empresas
    so_de_alfa = GrupoDeItem.irrestritos.create(empresa=d.alfa, nome="Sofás")
    so_de_beta = GrupoDeItem.irrestritos.create(empresa=d.beta, nome="Tapetes")
    assert list(GrupoDeItem.objects.da_empresa(d.alfa)) == [so_de_alfa]
    assert list(GrupoDeItem.objects.da_empresa(d.beta)) == [so_de_beta]
    # `da_conta` soma as duas, e isso é escolha (spec E2).
    assert set(GrupoDeItem.objects.da_conta(d.titular.guid)) == {so_de_alfa, so_de_beta}
    assert so_de_beta.conta_id == d.titular.guid


def test_uma_pessoa_alocada_nas_duas_alcanca_as_duas(duas_empresas):
    from contas.lugar import empresas_da_pessoa, filiais_da_pessoa
    from contas.models import Nivel, Usuario

    d = duas_empresas
    ana = Usuario.objects.create_user(email=email_de("ana-duas"), password=SENHA,
                                      nivel=Nivel.MEMBRO, dono=d.titular)
    alocar(ana, d.alfa, "vendedor", filial=d.loja_alfa)
    alocar(ana, d.beta, "vendedor", filial=d.loja_beta)
    assert set(empresas_da_pessoa(ana)) == {d.alfa, d.beta}
    assert list(filiais_da_pessoa(ana, d.beta)) == [d.loja_beta]
