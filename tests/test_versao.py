"""O RG da imagem: qual commit está rodando aqui.

O painel das 60 instalações lê este endereço para pintar o quadro de
verde/amarelo. Aberto de propósito (como /tema.css): um commit curto não
revela nada, e o painel precisa ler ANTES de qualquer sessão.
"""

import pytest
from django.test import Client
from django.urls import reverse


def test_responde_o_commit_do_arquivo(settings, tmp_path):
    """`BASE_DIR` apontado para `tmp_path`, e não escrevendo no diretório do
    projeto: teste que deixa arquivo para trás suja a árvore e faz o teste
    seguinte depender da ordem em que rodou."""
    settings.BASE_DIR = tmp_path
    (tmp_path / "VERSAO").write_text("a1b2c3d\n")
    resposta = Client().get(reverse("versao"))
    assert resposta.status_code == 200
    assert resposta.json() == {"commit": "a1b2c3d"}


def test_sem_arquivo_diz_desenvolvimento(settings, tmp_path):
    settings.BASE_DIR = tmp_path          # vazio: não há VERSAO aqui
    assert Client().get(reverse("versao")).json() == \
        {"commit": "desenvolvimento"}


def test_a_rota_responde_sem_nenhuma_sessao(settings, tmp_path):
    """Aberta de propósito. `Client()` sem login é o que prova — e o que a
    varredura de `tests/test_guarda.py` exige que esteja declarado em
    `TELAS_ABERTAS`, com o motivo ao lado."""
    settings.BASE_DIR = tmp_path
    assert "sessionid" not in Client().cookies
    assert Client().get(reverse("versao")).status_code == 200
