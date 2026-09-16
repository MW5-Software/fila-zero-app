"""Toda linha ligada a uma conta carrega o GUID do titular dela.

É a regra da casa desde 14/09/2026 (`conta_guid`), e até 16/09 ela só era
cobrada nas tabelas de NEGÓCIO: `test_regra_do_inquilino.py` isentava as apps
`plataforma` e `contas` inteiras, como "globais da instalação". Era verdade
para marca, módulo e parâmetro — e deixou passar Filial e AparenciaDaEmpresa,
que são de uma empresa, e a trilha de auditoria, que é de gente de uma conta.

A varredura daqui não isenta app nenhuma: toda tabela nossa tem `conta_guid`,
ou está em `DA_INSTALACAO` com o motivo escrito.
"""

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError

from comum.auditoria import registrar
from contas.models import Nivel, RegistroDeAuditoria, Usuario
from nucleo.permissoes import User
from plataforma.models import AparenciaDaEmpresa, Empresa, Filial
from tests.conftest import abrir_conta, email_de, por_na_conta

#: Apps do Django: não são tabelas nossas.
DO_DJANGO = {"admin", "auth", "contenttypes", "sessions"}

#: Tabelas que não pertencem a conta nenhuma, e por quê. Entrar aqui precisa
#: doer um pouco: é a lista que deixou Filial passar quando era "a app
#: plataforma inteira".
DA_INSTALACAO = {
    "plataforma.Marca": "a marca do produto nesta instalação, a mesma para todos",
    "plataforma.ImagemDaMarca": "o logo e o favicon da marca da instalação",
    "plataforma.Modulo": "quais módulos a instalação tem ligados",
    "plataforma.Parametro": "configuração da instalação, que só a MW5 mexe",
    "plataforma.Falha": "erro técnico do servidor, lido só pela MW5",
}


def _tabelas_nossas():
    return [m for m in apps.get_models() if m._meta.app_label not in DO_DJANGO]


def test_toda_tabela_nossa_tem_conta_guid_ou_um_motivo():
    sem_guid = {
        m._meta.label for m in _tabelas_nossas()
        if not any(campo.column == "conta_guid" for campo in m._meta.fields)
    }
    assert sem_guid == set(DA_INSTALACAO), (
        "Tabela sem `conta_guid`. Se ela é de uma conta, dê a coluna "
        "(`contas.inquilino.ModeloDaEmpresa`, ou `_conta_da_empresa` na "
        "plataforma); se é da instalação, escreva o motivo em DA_INSTALACAO.")


def test_tabela_de_uma_empresa_aponta_a_conta_pelo_guid_do_usuario():
    """Coluna com o nome certo não basta: tem de ser FK para `Usuario.guid`,
    senão `filter(conta=<guid>)` compara com qualquer coisa."""
    usuario = apps.get_model("contas", "Usuario")
    errados = []
    for modelo in _tabelas_nossas():
        campos = {c.name: c for c in modelo._meta.fields}
        if "empresa" not in campos:
            continue
        conta = campos.get("conta")
        if (conta is None or conta.related_model is not usuario
                or conta.to_fields != ["guid"]
                or conta.column != "conta_guid"):
            errados.append(modelo._meta.label)
    assert errados == []


@pytest.fixture
def alfa(db):
    return Empresa.objects.create(razao_social="Alfa Ltda")


class TestFilialLevaAConta:

    def test_a_matriz_nasce_com_a_conta_do_titular(self, db):
        titular = Usuario.objects.create_user(
            email="dona@teste.com", password="x", nivel=Nivel.TITULAR)
        empresa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
        assert empresa.filiais.get(e_matriz=True).conta_id == titular.guid

    def test_sem_titular_fica_sem_conta_e_ganha_quando_ele_chega(self, alfa):
        matriz = alfa.filiais.get(e_matriz=True)
        loja = Filial.objects.create(empresa=alfa, nome="Loja", apelido="Loja")
        assert (matriz.conta_id, loja.conta_id) == (None, None)

        titular = abrir_conta(alfa, "conta-alfa")

        matriz.refresh_from_db()
        loja.refresh_from_db()
        assert matriz.conta_id == loja.conta_id == titular.guid

    def test_a_filial_nova_herda_a_conta_da_empresa(self, alfa):
        titular = abrir_conta(alfa, "conta-alfa")
        loja = Filial.objects.create(empresa=alfa, nome="Loja", apelido="Loja")
        assert loja.conta_id == titular.guid

    def test_conta_de_outra_empresa_e_recusada(self, alfa):
        abrir_conta(alfa, "conta-alfa")
        beta = Empresa.objects.create(razao_social="Beta Ltda")
        dono_beta = abrir_conta(beta, "conta-beta")
        with pytest.raises(ValidationError):
            Filial.objects.create(empresa=alfa, nome="Loja", apelido="Loja",
                                  conta=dono_beta)


class TestAparenciaLevaAConta:

    def test_a_aparencia_herda_a_conta_da_empresa(self, alfa):
        titular = abrir_conta(alfa, "conta-alfa")
        aparencia = AparenciaDaEmpresa.objects.create(empresa=alfa)
        assert aparencia.conta_id == titular.guid

    def test_a_troca_de_titular_leva_a_aparencia_junto(self, alfa):
        AparenciaDaEmpresa.objects.create(empresa=alfa)
        titular = abrir_conta(alfa, "conta-alfa")
        assert AparenciaDaEmpresa.objects.get(empresa=alfa).conta_id == titular.guid


class TestATrilhaLevaAConta:

    def _ultima(self):
        return RegistroDeAuditoria.objects.order_by("-pk").first()

    def test_o_titular_grava_a_propria_conta(self, alfa):
        titular = abrir_conta(alfa, "conta-alfa")
        registrar("TESTE", titular)
        assert self._ultima().conta_guid == titular.guid

    def test_o_usuario_da_conta_grava_a_conta_do_titular(self, alfa):
        titular = abrir_conta(alfa, "conta-alfa")
        ana = Usuario.objects.create_user(email=email_de("ana"), password="x",
                                          nivel=Nivel.MEMBRO)
        por_na_conta(ana, alfa)
        registrar("TESTE", ana)
        assert self._ultima().conta_guid == titular.guid

    def test_o_retrato_da_sessao_acha_a_conta_pelo_login(self, alfa):
        """É o que `request.usuario` é nas telas: não traz a conta."""
        titular = abrir_conta(alfa, "conta-alfa")
        registrar("TESTE", User(id=str(titular.pk), name="Dona",
                                login=titular.email.upper()))
        assert self._ultima().conta_guid == titular.guid

    def test_a_mw5_nao_e_de_conta_nenhuma(self, db):
        mw5 = Usuario.objects.create_user(email="mw5@teste.com", password="x",
                                          nivel=Nivel.MASTER)
        registrar("TESTE", mw5)
        assert self._ultima().conta_guid is None

    def test_login_recusado_de_ninguem_fica_sem_conta(self, db):
        registrar("ENTRADA_RECUSADA", "ninguem@teste.com")
        assert self._ultima().conta_guid is None
