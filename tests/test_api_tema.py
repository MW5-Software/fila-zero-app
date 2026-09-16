"""`GET /api/tema` — os mesmos tokens do `/tema.css`, para o app.

A web não tem uma cor escrita na folha do design system: tudo sai de
`nucleo.theme.tokens.build`. O app segue a mesma ideia, e esta rota é a ponte.
Se ela devolvesse outra coisa que não `Brand.tokens`, o app e a web divergiriam
em silêncio no dia em que alguém mexesse numa das duas.
"""

import pytest
from django.test import Client

from plataforma.marca import marca_da_instalacao

pytestmark = pytest.mark.django_db


def test_aberta_e_igual_ao_que_a_web_desenha():
    """Os tokens da marca COM os ajustes que a folha da casa aplica por cima —
    é o que a web desenha de fato. Sem os ajustes, o logo do app saía menor que
    o da web (72px na entrada contra os 112px da `kronos.css`)."""
    from plataforma.marca import AJUSTES_DA_FOLHA_DA_CASA

    resposta = Client().get("/api/tema")
    assert resposta.status_code == 200
    corpo = resposta.json()
    marca = marca_da_instalacao()
    assert corpo["padrao"] == marca.default_theme
    assert corpo["claro"] == {**marca.tokens("light"), **AJUSTES_DA_FOLHA_DA_CASA}
    assert corpo["escuro"] == {**marca.tokens("dark"), **AJUSTES_DA_FOLHA_DA_CASA}
    assert corpo["claro"]["logo-login-h"] == "112px"


def test_os_ajustes_sao_os_da_kronos_css():
    """Os ajustes moram em dois lugares — a `:root` da `kronos.css`, que a web
    lê, e `AJUSTES_DA_FOLHA_DA_CASA`, que a API entrega ao app. Este teste é o
    que impede os dois de divergirem: mudou um, fica vermelho até mudar o outro."""
    import re
    from pathlib import Path

    from plataforma.marca import AJUSTES_DA_FOLHA_DA_CASA

    folha = Path("plataforma/static/plataforma/kronos.css").read_text(encoding="utf-8")
    raiz = re.search(r"^:root\s*\{(.*?)\}", folha, re.S | re.M)
    assert raiz, "a kronos.css perdeu o bloco :root dos ajustes"
    na_folha = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", raiz.group(1)))
    assert na_folha == AJUSTES_DA_FOLHA_DA_CASA


def test_traz_todo_token_que_a_web_declara():
    from nucleo.theme.tokens import TOKEN_NAMES

    corpo = Client().get("/api/tema").json()
    assert set(TOKEN_NAMES) <= set(corpo["claro"])
    assert set(TOKEN_NAMES) <= set(corpo["escuro"])
