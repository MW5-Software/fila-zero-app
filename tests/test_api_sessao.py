"""Entrar e sair pela API — o mesmo núcleo da tela de entrada."""

from datetime import timedelta

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from comum.auditoria import ACOES
from comum.sessao import CHAVE_ALVO
from contas.models import RegistroDeAuditoria, Usuario
from tests.conftest import cliente_da_api, sessao_do_token

pytestmark = [pytest.mark.django_db]

SENHA = "segredo-de-teste"


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(email="ana@teste.com", password=SENHA,
                                       nome="Ana", idioma="pt-br")


def _entrar(email, senha, **extra):
    return Client().post("/api/v1/sessao", {"email": email, "senha": senha},
                         content_type="application/json", **extra)


def _parametro(nome, valor):
    from plataforma.models import Parametro

    Parametro.objects.update_or_create(chave=nome, defaults={"valor": str(valor)})


class TestEntrar:
    def test_credencial_certa_devolve_token(self, ana):
        resposta = _entrar("ana@teste.com", SENHA)
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["token"]
        assert corpo["senha_expirada"] is False

    def test_o_token_abre_a_api(self, ana):
        api, token = cliente_da_api("ana@teste.com", SENHA)
        assert api.get("/api/v1/eu").status_code == 200

    def test_a_resposta_nao_grava_cookie(self, ana):
        assert settings.SESSION_COOKIE_NAME not in _entrar("ana@teste.com", SENHA).cookies

    def test_a_recusa_nao_distingue_os_tres_casos(self, ana):
        Usuario.objects.create_user(email="ze@teste.com", password=SENHA, is_active=False)
        respostas = [_entrar("ana@teste.com", "errada"),
                     _entrar("ninguem@teste.com", SENHA),
                     _entrar("ze@teste.com", SENHA)]
        assert {r.status_code for r in respostas} == {401}
        assert len({r.content for r in respostas}) == 1

    def test_a_recusa_fica_na_trilha(self, ana):
        _entrar("ana@teste.com", "errada")
        assert RegistroDeAuditoria.objects.filter(
            acao=ACOES.ENTRADA_RECUSADA, alvo="ana@teste.com").exists()

    def test_o_acerto_fica_na_trilha(self, ana):
        _entrar("ana@teste.com", SENHA)
        assert RegistroDeAuditoria.objects.filter(
            acao=ACOES.ENTROU, alvo="ana@teste.com").exists()

    def test_login_por_cima_de_personificacao_nao_herda_o_alvo(self, ana):
        Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)
        zeca = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
        api, token = cliente_da_api("raiz@teste.com", SENHA)
        sessao = sessao_do_token(token)
        sessao[CHAVE_ALVO] = str(zeca.pk)
        sessao.save()
        assert api.get("/api/v1/eu").json()["pessoa"]["email"] == "zeca@teste.com"

        nova = api.post("/api/v1/sessao", {"email": "ana@teste.com", "senha": SENHA},
                        content_type="application/json")
        assert nova.status_code == 200
        outra = Client(HTTP_AUTHORIZATION=f"Bearer {nova.json()['token']}")
        assert outra.get("/api/v1/eu").json()["pessoa"]["email"] == "ana@teste.com"
        assert api.get("/api/v1/eu").status_code == 401


class TestSair:
    def test_sair_mata_o_token(self, ana):
        api, token = cliente_da_api("ana@teste.com", SENHA)
        assert api.delete("/api/v1/sessao").status_code == 204
        assert api.get("/api/v1/eu").status_code == 401

    def test_sair_fica_na_trilha(self, ana):
        api, token = cliente_da_api("ana@teste.com", SENHA)
        api.delete("/api/v1/sessao")
        assert RegistroDeAuditoria.objects.filter(
            acao=ACOES.SAIU, alvo="ana@teste.com").exists()

    def test_sair_sem_sessao_nao_quebra(self, db):
        assert Client().delete("/api/v1/sessao").status_code == 204


class TestOBancoDecideACadaRequisicao:
    def test_desativar_derruba_o_token(self, ana):
        api, token = cliente_da_api("ana@teste.com", SENHA)
        Usuario.objects.filter(pk=ana.pk).update(is_active=False)
        resposta = api.get("/api/v1/eu")
        assert resposta.status_code == 401
        assert resposta.json()["erro"]["codigo"] == "sem_sessao"

    def test_o_relogio_de_inatividade_vale_para_o_token(self, ana):
        _parametro("minutos_de_sessao", 1)
        api, token = cliente_da_api("ana@teste.com", SENHA)
        assert sessao_do_token(token).get_expiry_age() == 60


@pytest.mark.urls("tests.api_de_teste")
class TestSenhaVencida:
    def _vencida(self, ana):
        _parametro("dias_para_expirar_senha", 30)
        Usuario.objects.filter(pk=ana.pk).update(
            senha_definida_em=timezone.now() - timedelta(days=40))

    def test_o_login_avisa(self, ana):
        self._vencida(ana)
        assert _entrar("ana@teste.com", SENHA).json()["senha_expirada"] is True

    def test_eu_continua_aberto(self, ana):
        self._vencida(ana)
        api, token = cliente_da_api("ana@teste.com", SENHA)
        assert api.get("/api/v1/eu").status_code == 200

    def test_o_resto_prende(self, ana):
        self._vencida(ana)
        api, token = cliente_da_api("ana@teste.com", SENHA)
        resposta = api.get("/api/teste/guardada")
        assert resposta.status_code == 403
        assert resposta.json()["erro"]["codigo"] == "senha_expirada"


class TestIdioma:
    def test_sem_pessoa_a_api_segue_o_aparelho(self, db):
        resposta = Client().get("/api/v1/eu", HTTP_ACCEPT_LANGUAGE="es-PY,es;q=0.9")
        assert resposta["Content-Language"] == "es"

    def test_com_pessoa_vale_a_coluna_e_nao_o_aparelho(self, ana):
        api, token = cliente_da_api("ana@teste.com", SENHA)
        resposta = api.get("/api/v1/eu", HTTP_ACCEPT_LANGUAGE="es")
        assert resposta["Content-Language"] == "pt-br"

    def test_a_web_continua_sem_ouvir_o_navegador(self, db):
        resposta = Client().get("/entrar", HTTP_ACCEPT_LANGUAGE="es")
        assert resposta["Content-Language"] == settings.LANGUAGE_CODE
