"""A primeira pergunta que o app faz: que API existe, e se ele está velho demais.

O celular tem um problema que a web não tem — o app instalado pode estar três
versões atrás. `app_minimo` é o que deixa o app dizer "atualize" em vez de
quebrar numa tela.
"""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_a_versao_responde_sem_sessao(settings):
    resposta = Client().get("/api/versao")
    assert resposta.status_code == 200
    assert resposta.json() == {"api": [1], "app_minimo": settings.APP_MINIMO}


def test_o_minimo_vem_do_settings(settings):
    settings.APP_MINIMO = "9.9.9"
    assert Client().get("/api/versao").json()["app_minimo"] == "9.9.9"


@pytest.mark.parametrize("caminho", ["/api/docs", "/api/openapi.json"])
def test_a_documentacao_do_ninja_nao_esta_no_ar(caminho):
    """A web responde 404 para não revelar a tela que a pessoa não pode. Um
    `/api/docs` aberto entregaria o mapa inteiro das rotas."""
    assert Client().get(caminho).status_code == 404
