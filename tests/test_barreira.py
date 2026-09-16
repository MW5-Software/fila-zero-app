"""Uma decisão de acesso, duas traduções.

`barreira` decide; a guarda da web responde em HTML e a da API em JSON. Cada
caso é conferido nos DOIS lados com a mesma requisição — é o que garante que
uma regra nova de acesso não vale num lado e falta no outro.
"""

import json
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from comum.guardas_da_api import (
    api_exigir_filial, api_exigir_login, api_exigir_modulo_ligado, api_exigir_permissao,
)
from comum.guardas_de_acesso import Barreira, barreira, exigir_login, exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.sessao import CHAVE, CHAVE_ALVO, CHAVE_SENHA_EXPIRADA
from contas.models import Usuario

pytestmark = pytest.mark.django_db

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


def _pedido(sessao: dict, url_name="usuarios"):
    pedido = RequestFactory().get("/qualquer")
    store = SessionStore()
    for chave, valor in sessao.items():
        store[chave] = valor
    pedido.session = store
    pedido.resolver_match = SimpleNamespace(url_name=url_name)
    return pedido


def _codigo(resposta) -> str:
    """A guarda é chamada direto, sem o cliente de teste — e só a resposta
    do cliente de teste tem `.json()`."""
    return json.loads(resposta.content)["erro"]["codigo"]


def _ok(request):
    return HttpResponse("passou")


def eu(request):
    """Mesmo nome da operação liberada com senha vencida."""
    return HttpResponse("passou")


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(email="ana@teste.com", password="x")


@pytest.fixture
def raiz(db):
    return Usuario.objects.create_superuser(email="raiz@teste.com", password="x")


class TestSemSessao:
    def test_decide(self):
        assert barreira(_pedido({})) is Barreira.SEM_SESSAO

    def test_web_manda_entrar(self):
        resposta = exigir_login(_ok)(_pedido({}))
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_api_responde_401(self):
        resposta = api_exigir_login(_ok)(_pedido({}))
        assert resposta.status_code == 401
        assert _codigo(resposta) == "sem_sessao"

    def test_login_vem_antes_do_modulo(self):
        """Anônimo numa rota de módulo desligado é 401, não 404: quem não
        entrou precisa saber onde entrar."""
        guardada = api_exigir_permissao("frete.ver")(
            api_exigir_modulo_ligado("fantasma")(_ok))
        assert guardada(_pedido({})).status_code == 401


class TestSenhaVencida:
    def _vencida(self, pessoa, url_name="usuarios"):
        return _pedido({CHAVE: str(pessoa.pk), CHAVE_SENHA_EXPIRADA: True}, url_name)

    def test_decide(self, ana):
        assert barreira(self._vencida(ana)) is Barreira.SENHA_EXPIRADA

    def test_web_manda_trocar(self, ana):
        resposta = exigir_login(_ok)(self._vencida(ana))
        assert resposta.status_code == 302
        assert "expirada=1" in resposta["Location"]

    def test_api_responde_403(self, ana):
        resposta = api_exigir_login(_ok)(self._vencida(ana))
        assert resposta.status_code == 403
        assert _codigo(resposta) == "senha_expirada"

    def test_api_libera_eu_pelo_nome_da_operacao(self, ana):
        """O nome vem da função, não do `resolver_match`: no Ninja, duas
        operações no mesmo caminho dividem o padrão de URL."""
        resposta = api_exigir_login(eu)(self._vencida(ana, url_name="outra"))
        assert resposta.status_code == 200

    def test_personificando_nao_prende(self, raiz, ana):
        pedido = _pedido({CHAVE: str(raiz.pk), CHAVE_ALVO: str(ana.pk),
                          CHAVE_SENHA_EXPIRADA: True})
        assert barreira(pedido) is None


class TestNaoExiste:
    def test_sem_permissao_decide(self, ana):
        pedido = _pedido({CHAVE: str(ana.pk)})
        assert barreira(pedido, permissao="frete.ver") is Barreira.NAO_EXISTE

    def test_sem_permissao_web_404(self, ana):
        pedido = _pedido({CHAVE: str(ana.pk)})
        assert exigir_permissao("frete.ver")(_ok)(pedido).status_code == 404

    def test_modulo_desligado_web_404(self, raiz):
        from plataforma.models import Modulo

        Modulo.objects.create(chave="fantasma", ativo=False)
        pedido = _pedido({CHAVE: str(raiz.pk)})
        assert exigir_modulo_ligado("fantasma")(_ok)(pedido).status_code == 404

    def test_na_api_os_dois_motivos_tem_o_mesmo_corpo(self, ana, raiz):
        """Quem não pode não descobre nem que a rota existe, nem por qual
        dos dois motivos não pode."""
        from plataforma.models import Modulo

        Modulo.objects.create(chave="fantasma", ativo=False)
        sem_permissao = api_exigir_permissao("frete.ver")(_ok)(
            _pedido({CHAVE: str(ana.pk)}))
        desligado = api_exigir_modulo_ligado("fantasma")(_ok)(
            _pedido({CHAVE: str(raiz.pk)}))
        assert sem_permissao.status_code == desligado.status_code == 404
        assert sem_permissao.content == desligado.content
        assert _codigo(sem_permissao) == "nao_existe"


class TestSemFilial:
    def test_decide_e_api_responde_409(self, ana):
        pedido = _pedido({CHAVE: str(ana.pk)})
        assert barreira(pedido, exige_filial=True) is Barreira.SEM_FILIAL
        resposta = api_exigir_login(api_exigir_filial(_ok))(pedido)
        assert resposta.status_code == 409
        assert _codigo(resposta) == "sem_filial"


class TestTudoCerto:
    def test_passa_e_poe_o_usuario(self, raiz):
        from plataforma.models import Modulo

        Modulo.objects.create(chave="fantasma", ativo=True)
        pedido = _pedido({CHAVE: str(raiz.pk)})
        guardada = api_exigir_permissao("frete.ver")(api_exigir_modulo_ligado("fantasma")(_ok))
        resposta = guardada(pedido)
        assert resposta.status_code == 200
        assert pedido.usuario.superuser is True


class TestAsMarcas:
    def test_as_guardas_da_api_marcam_a_funcao(self):
        guardada = api_exigir_permissao("filiais.editar")(
            api_exigir_modulo_ligado("filiais")(api_exigir_filial(_ok)))
        assert guardada.exige_login is True
        assert guardada.permissao == "filiais.editar"
        assert guardada.modulo == "filiais"
        assert guardada.exige_filial is True
        assert guardada.__name__ == "_ok"
