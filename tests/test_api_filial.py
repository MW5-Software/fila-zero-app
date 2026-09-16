"""Trocar a filial do contexto pela API — pelo mesmo caminho da tela."""

import uuid

import pytest
from django.test import Client

from comum.auditoria import ACOES
from contas.models import RegistroDeAuditoria
from plataforma.models import Empresa, Filial
from tests.conftest import abrir_conta, cliente_da_api, email_de

pytestmark = pytest.mark.django_db

SENHA = "segredo-de-teste"


@pytest.fixture
def cenario():
    alfa = Empresa.objects.create(razao_social="Alfa")
    abrir_conta(alfa, "tita", SENHA)
    norte = Filial.objects.create(empresa=alfa, nome="Norte", apelido="Norte")
    beta = Empresa.objects.create(razao_social="Beta")
    abrir_conta(beta, "bete", SENHA)
    da_beta = Filial.objects.create(empresa=beta, nome="Loja Beta", apelido="Loja Beta")
    api, token = cliente_da_api(email_de("tita"), SENHA)
    return {"api": api, "norte": norte, "da_beta": da_beta}


def _trocar(api, guid):
    return api.post("/api/v1/filial", {"guid": str(guid)}, content_type="application/json")


def test_troca_para_filial_alcancada(cenario):
    resposta = _trocar(cenario["api"], cenario["norte"].guid)
    assert resposta.status_code == 200
    assert resposta.json()["guid"] == str(cenario["norte"].guid)
    assert cenario["api"].get("/api/v1/eu").json()["filial"]["guid"] == str(cenario["norte"].guid)


def test_a_troca_fica_na_trilha(cenario):
    _trocar(cenario["api"], cenario["norte"].guid)
    assert RegistroDeAuditoria.objects.filter(acao=ACOES.FILIAL_TROCADA).exists()


def test_filial_de_outra_conta_e_404_e_nao_troca(cenario):
    antes = cenario["api"].get("/api/v1/eu").json()["filial"]
    resposta = _trocar(cenario["api"], cenario["da_beta"].guid)
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "nao_existe"
    assert cenario["api"].get("/api/v1/eu").json()["filial"] == antes


def test_outra_conta_inexistente_e_lixo_tem_o_mesmo_corpo(cenario):
    """Um GUID de outra conta não pode ser distinguível de um que nunca existiu."""
    de_outra = _trocar(cenario["api"], cenario["da_beta"].guid)
    inexistente = _trocar(cenario["api"], uuid.uuid4())
    lixo = _trocar(cenario["api"], "nao-e-guid")
    assert de_outra.status_code == inexistente.status_code == lixo.status_code == 404
    assert de_outra.content == inexistente.content == lixo.content


def test_sem_sessao_e_401(db):
    resposta = Client().post("/api/v1/filial", {"guid": str(uuid.uuid4())},
                             content_type="application/json")
    assert resposta.status_code == 401
