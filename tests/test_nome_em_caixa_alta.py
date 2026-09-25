"""O NOME em caixa alta nas listas de Usuários, Empresas e Cargos
(25/09/2026, pedido do cliente: "passar tudo para maiúsculo — usuário,
empresa, cargo — NOME, igual Configurações da Fila").

**Pela folha, e não pelo dado**, como nos cadastros da fila
(`fila/static/fila/cadastros.css`): o nome continua gravado como a pessoa o
escreveu, e é assim que ele aparece no cabeçalho, no menu do avatar e na
trilha. A caixa alta é a leitura destas listas, e só delas.
"""

import re
from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse

from contas.models import Nivel, Usuario

pytestmark = pytest.mark.django_db

SENHA = "segredo-de-teste"
_CELULA = '<span class="nome-em-caixa-alta">{}</span>'


@pytest.fixture
def titular():
    from contas.fabrica import aplicar
    from plataforma.models import Empresa

    dono = Usuario.objects.create_user(
        email="dono-caixa@teste.com", password=SENHA, nome="Dona Rosa",
        nivel=Nivel.TITULAR)
    aplicar(dono, Nivel.TITULAR)
    Empresa.objects.create(razao_social="Alfa Móveis Ltda", dono=dono)
    Usuario.objects.create_user(email="ana-caixa@teste.com", password=SENHA,
                                nome="Ana Souza", nivel=Nivel.MEMBRO, dono=dono)
    return dono


def _html(email, rota):
    c = Client()
    c.post(reverse("entrar"), {"usuario": email, "senha": SENHA})
    resposta = c.get(reverse(rota))
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_a_folha_poe_a_classe_em_caixa_alta():
    folha = Path("plataforma/static/plataforma/listagem.css").read_text()
    assert re.search(r"\.nome-em-caixa-alta\s*\{\s*text-transform:\s*uppercase",
                     folha)


def test_usuarios(titular):
    assert _CELULA.format("Ana Souza") in _html(titular.email, "usuarios")


def test_cargos(titular):
    assert _CELULA.format("Vendedor") in _html(titular.email, "cargos")


def test_empresas():
    raiz = Usuario.objects.create_superuser(email="raiz-caixa@teste.com",
                                            password=SENHA)
    from plataforma.models import Empresa

    Empresa.objects.create(razao_social="Beta Estofados Ltda")
    assert _CELULA.format("Beta Estofados Ltda") in _html(raiz.email, "empresa")


def test_o_dado_continua_como_foi_escrito(titular):
    assert Usuario.objects.get(email="ana-caixa@teste.com").nome == "Ana Souza"
