"""Toda resposta de erro da API tem o mesmo formato.

O app decide pelo `codigo`, e mostra a `mensagem`. Um formato por tipo de erro
— o do Ninja para schema, o do Django para validação de model, HTML para 404 —
seria um `if` por tipo em cada tela do app.
"""

import pytest
from django.test import Client

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.api_de_teste")]


def test_validacao_do_model_vira_422_no_formato():
    resposta = Client().get("/api/teste/invalido")
    assert resposta.status_code == 422
    erro = resposta.json()["erro"]
    assert erro["codigo"] == "validacao"
    assert erro["campos"] == {"quantidade": ["Deve ser maior que zero."]}
    assert erro["mensagem"]


def test_corpo_invalido_vira_422_no_formato_da_casa_e_nao_no_do_ninja():
    resposta = Client().post("/api/teste/corpo", {"quantidade": "muitos"},
                             content_type="application/json")
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert "detail" not in corpo
    assert corpo["erro"]["codigo"] == "validacao"
    assert "quantidade" in corpo["erro"]["campos"]


def test_http404_vira_nao_existe_sem_revelar_o_motivo():
    from comum.respostas_da_api import nao_existe

    resposta = Client().get("/api/teste/some")
    assert resposta.status_code == 404
    assert resposta.content == nao_existe().content
    assert b"segredo do caminho" not in resposta.content


def test_corpo_valido_passa():
    resposta = Client().post("/api/teste/corpo", {"quantidade": 3},
                             content_type="application/json")
    assert resposta.status_code == 200
    assert resposta.json() == {"quantidade": 3}
