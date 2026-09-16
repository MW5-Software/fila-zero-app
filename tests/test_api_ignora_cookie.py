"""Em `/api/` a sessão vem do cabeçalho, e o cookie é IGNORADO.

É o que torna seguro o Ninja isentar as rotas dele de CSRF: um site malicioso
consegue fazer o navegador de alguém mandar o cookie da web, mas não um
cabeçalho `Authorization`. Se a API aceitasse o cookie, qualquer página aberta
no navegador de quem está logado na web agiria na API em nome dela.
"""

from importlib import import_module

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from django.test import RequestFactory

from comum.sessao import CHAVE
from comum.sessao_por_cabecalho import MiddlewareDeSessao, chave_do_cabecalho

pytestmark = pytest.mark.django_db

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


def _sessao_com(**dados) -> str:
    sessao = SessionStore()
    for chave, valor in dados.items():
        sessao[chave] = valor
    sessao.save()
    return sessao.session_key


def _passar(request, efeito=None):
    """Roda o middleware em volta de uma view que só lê (e, se pedido, mexe
    na) sessão. Devolve `(o que a view leu, a resposta)`."""
    lido = {}

    def vista(req):
        lido.update(req.session.items())
        if efeito is not None:
            efeito(req)
        return HttpResponse("ok")

    resposta = MiddlewareDeSessao(vista)(request)
    return lido, resposta


class TestDeOndeVemASessao:
    def test_na_api_o_cabecalho_traz_a_sessao(self):
        chave = _sessao_com(**{CHAVE: "7"})
        pedido = RequestFactory().get("/api/v1/eu", HTTP_AUTHORIZATION=f"Bearer {chave}")
        lido, resposta = _passar(pedido)
        assert lido.get(CHAVE) == "7"

    def test_na_api_o_cookie_e_ignorado(self):
        chave = _sessao_com(**{CHAVE: "7"})
        pedido = RequestFactory().get("/api/v1/eu")
        pedido.COOKIES[settings.SESSION_COOKIE_NAME] = chave
        lido, resposta = _passar(pedido)
        assert CHAVE not in lido

    def test_cabecalho_invalido_nao_cai_para_o_cookie(self):
        chave = _sessao_com(**{CHAVE: "7"})
        pedido = RequestFactory().get("/api/v1/eu", HTTP_AUTHORIZATION="Bearer lixo")
        pedido.COOKIES[settings.SESSION_COOKIE_NAME] = chave
        lido, resposta = _passar(pedido)
        assert CHAVE not in lido

    def test_fora_da_api_o_cabecalho_e_ignorado(self):
        chave = _sessao_com(**{CHAVE: "7"})
        pedido = RequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {chave}")
        lido, resposta = _passar(pedido)
        assert CHAVE not in lido

    def test_fora_da_api_o_cookie_continua_valendo(self):
        chave = _sessao_com(**{CHAVE: "7"})
        pedido = RequestFactory().get("/")
        pedido.COOKIES[settings.SESSION_COOKIE_NAME] = chave
        lido, resposta = _passar(pedido)
        assert lido.get(CHAVE) == "7"


class TestOQueARespostaDaApiGrava:
    def test_nunca_grava_cookie_e_guarda_a_mudanca(self):
        chave = _sessao_com(**{CHAVE: "7"})
        pedido = RequestFactory().get("/api/v1/eu", HTTP_AUTHORIZATION=f"Bearer {chave}")

        def mexer(req):
            req.session["marca"] = 1

        lido, resposta = _passar(pedido, mexer)
        assert settings.SESSION_COOKIE_NAME not in resposta.cookies
        assert SessionStore(chave)["marca"] == 1

    def test_sessao_sem_ninguem_dentro_nao_vira_linha(self):
        """Toda requisição passa por `_renovar_sessao`, que mexe na sessão.
        Sem a trava, cada chamada anônima criaria uma linha que ninguém usa."""
        antes = Session.objects.count()

        def mexer(req):
            req.session["marca"] = 1

        _passar(RequestFactory().get("/api/versao"), mexer)
        _passar(RequestFactory().get("/api/versao", HTTP_AUTHORIZATION="Bearer vencida"), mexer)
        assert Session.objects.count() == antes

    def test_a_resposta_varia_pelo_cabecalho(self):
        lido, resposta = _passar(RequestFactory().get("/api/versao"))
        assert "Authorization" in resposta["Vary"]


class TestOCabecalho:
    @pytest.mark.parametrize("bruto, esperado", [
        ("Bearer abc123", "abc123"),
        ("bearer abc123", "abc123"),
        ("Token abc123", None),
        ("Bearer ", None),
        ("", None),
    ])
    def test_le_so_o_esquema_bearer(self, bruto, esperado):
        pedido = RequestFactory().get("/api/versao", HTTP_AUTHORIZATION=bruto)
        assert chave_do_cabecalho(pedido) == esperado


class TestDePontaAPonta:
    """Os testes acima rodam o middleware isolado; estes, a pilha inteira."""

    def test_quem_entrou_na_web_nao_entra_na_api_pelo_cookie(self):
        from django.test import Client
        from django.urls import reverse

        from contas.models import Usuario

        Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
        web = Client()
        web.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        assert web.get("/").status_code == 200
        assert web.get("/api/v1/eu").status_code == 401

    def test_uma_acao_forjada_com_o_cookie_nao_age_na_api(self):
        """Sair pela API com o cookie da web não derruba a sessão da web."""
        from django.test import Client
        from django.urls import reverse

        from contas.models import Usuario

        Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
        web = Client()
        web.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        web.delete("/api/v1/sessao")
        assert web.get("/").status_code == 200
