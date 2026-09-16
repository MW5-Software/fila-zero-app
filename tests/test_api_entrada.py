"""`GET /api/entrada` — a tela de entrada da web, em dados, para o app.

Tudo o que se lê na tela de entrada vem da marca (`LoginBrand`), que o cliente
edita na Aparência, e as frases que ele não trocou saem traduzidas
(`plataforma.entrada.traduzir_a_entrada`). O app desenha a mesma tela a partir
daqui — sem escrever "Acessar Painel" no próprio código, que é como app e web
passariam a dizer coisas diferentes no dia em que o cliente mudasse a frase.
"""

from dataclasses import replace

import pytest
from django.test import Client

from plataforma.entrada import traduzir_a_entrada
from plataforma.marca import marca_da_instalacao

pytestmark = pytest.mark.django_db


def _entrada(**cabecalhos):
    resposta = Client().get("/api/entrada", **cabecalhos)
    assert resposta.status_code == 200, resposta.content
    return resposta.json()


def test_aberta_e_igual_a_entrada_da_web_em_portugues():
    corpo = _entrada()
    login = marca_da_instalacao().login
    assert corpo["titulo"] == login.title
    assert corpo["rotulo_email"] == login.identifier_label
    assert corpo["dica_email"] == login.identifier_placeholder
    assert corpo["rotulo_senha"] == login.password_label
    assert corpo["dica_senha"] == login.password_placeholder
    assert corpo["mostrar_manter"] is login.show_remember
    assert corpo["rotulo_manter"] == login.remember_label
    assert corpo["mostrar_esqueceu"] is login.show_forgot
    assert corpo["rotulo_esqueceu"] == login.forgot_label
    assert corpo["endereco_esqueceu"] == login.forgot_url
    assert corpo["rotulo_botao"] == login.submit_label
    assert corpo["texto_suporte"] == login.support_text
    assert corpo["rotulo_suporte"] == login.support_label
    assert corpo["endereco_suporte"] == login.support_url
    assert corpo["logo"] == marca_da_instalacao().assets.login_logo


def test_em_castelhano_sai_traduzida_pela_mesma_funcao_da_web():
    from django.utils import translation

    corpo = _entrada(HTTP_ACCEPT_LANGUAGE="es-PY")
    with translation.override("es"):
        esperado = traduzir_a_entrada(marca_da_instalacao().login)
    assert corpo["titulo"] == esperado.title
    assert corpo["rotulo_botao"] == esperado.submit_label
    assert corpo["titulo"] != marca_da_instalacao().login.title, (
        "o castelhano não traduziu nada — confira locale/es")


def test_frase_trocada_pelo_cliente_passa_intacta(monkeypatch):
    from plataforma import marca as modulo_marca

    original = modulo_marca.marca_da_instalacao()
    trocada = replace(original, login=replace(original.login, title="Entre no portal da Ferragem"))
    monkeypatch.setattr(modulo_marca, "marca_da_instalacao", lambda: trocada)
    assert _entrada(HTTP_ACCEPT_LANGUAGE="es")["titulo"] == "Entre no portal da Ferragem"


def test_os_idiomas_sao_os_da_instalacao():
    from django.conf import settings

    assert [i["codigo"] for i in _entrada()["idiomas"]] == [codigo for codigo, nome in settings.LANGUAGES]
