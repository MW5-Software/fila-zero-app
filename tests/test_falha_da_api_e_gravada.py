"""Exceção numa rota de API vira linha em `Falha`, e o app recebe JSON.

O tratador padrão do Ninja erra dos dois jeitos: com `DEBUG` ele engole a
exceção e devolve o traceback em texto (a tela de Falhas não vê nada); sem
`DEBUG` ele re-levanta, o middleware grava, e o app recebe a página 500 em
HTML, que não tem como ler.
"""

import pytest
from django.test import Client

from plataforma.models import Falha

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.api_de_teste")]


def _ultima():
    return Falha.objects.order_by("-pk").first()


def test_excecao_na_api_vira_linha_em_falha():
    antes = Falha.objects.count()
    resposta = Client().get("/api/teste/explode")
    assert resposta.status_code == 500
    assert Falha.objects.count() == antes + 1
    assert "explodiu de propósito" in _ultima().resumo
    assert _ultima().caminho == "/api/teste/explode"


def test_o_app_recebe_o_id_e_nunca_o_traceback():
    resposta = Client().get("/api/teste/explode")
    erro = resposta.json()["erro"]
    assert erro["codigo"] == "falha"
    assert erro["id"] == str(_ultima().guid)
    texto = resposta.content.decode()
    assert "Traceback" not in texto
    assert "explodiu" not in texto


def test_em_debug_quem_grava_e_o_middleware_e_uma_vez_so(settings):
    settings.DEBUG = True
    antes = Falha.objects.count()
    resposta = Client(raise_request_exception=False).get("/api/teste/explode")
    assert resposta.status_code == 500
    assert Falha.objects.count() == antes + 1


def test_a_api_de_verdade_usa_o_mesmo_tratador():
    """Sem isto, o teste acima provaria a API de mentira e mais nada."""
    from config.api import api
    from plataforma.api_tratadores import tratar_falha

    assert api._exception_handlers[Exception] is tratar_falha
