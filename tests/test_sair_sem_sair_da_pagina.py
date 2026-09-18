"""Sair sem trocar de página (18/09/2026).

O cabeçalho tinha um ícone solto de "sair" que levava a `/sair`: uma página
NUA — sem shell, sem menu, com um cartão encostado no canto — só para
perguntar "tem certeza?". Quem clicava sem querer perdia a tela em que estava
e voltava pelo histórico.

A partir daqui o caminho normal é o menu do avatar, onde "Sair" já mora junto
de "Meu Perfil", e a pergunta é um diálogo POR CIMA da página. **A página
`/sair` continua existindo e continua sendo a única que age**: o item do menu
é um `<a href="/sair">` de verdade, então quem está sem JavaScript cai na
confirmação de sempre — e nenhum `<img src="/sair">` derruba sessão nenhuma,
porque o POST continua sendo o único jeito de sair.
"""

import pytest
from django.test import Client
from django.urls import reverse

from tests.conftest import abrir_conta

SENHA = "segredo-de-teste"


@pytest.fixture
def logada(db):
    """A titular de uma empresa, logada — quem vê o cabeçalho inteiro."""
    from plataforma.models import Empresa

    empresa = Empresa.objects.create(razao_social="Alfa Ltda")
    abrir_conta(empresa, "sylvia", SENHA)
    c = Client()
    c.post(reverse("entrar"), {"usuario": "sylvia@teste.com", "senha": SENHA})
    return c


def _home(cliente) -> str:
    resposta = cliente.get(reverse("home"))
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_o_cabecalho_nao_tem_mais_o_icone_solto_de_sair(logada):
    """O quarto ícone do canto direito era o mais perigoso dos quatro, e o
    único sem rótulo escrito. Ele sai; quem o quiser de volta tem de explicar
    por que um clique acidental vale o preço."""
    html = _home(logada)

    assert 'class="iconbtn" href="/sair"' not in html


def test_o_sair_mora_no_menu_do_avatar(logada):
    """No mesmo menu de "Meu Perfil", em vermelho e por último — a ordem em
    que se lê, e a cor que o design system reserva para o que não se desfaz."""
    html = _home(logada)

    assert 'data-dropdown-open="mw5-menu-usuario"' in html
    assert 'href="/sair" class="danger" data-sair=""' in html


def test_o_item_do_menu_continua_sendo_um_link_de_verdade(logada):
    """Sem JavaScript o menu ainda abre? Não — mas o link é link, e `/sair`
    continua respondendo a confirmação de sempre. É o caminho que sobra, e ele
    não pode depender do diálogo."""
    html = _home(logada)
    assert 'href="/sair"' in html

    resposta = logada.get("/sair")
    assert resposta.status_code == 200
    assert 'action="/sair"' in resposta.content.decode()


def test_toda_tela_logada_traz_o_dialogo_fechado(logada):
    """O diálogo nasce em `overlays`, fechado, em qualquer tela do shell: o
    menu do avatar também está em qualquer tela, e um gatilho sem destino
    seria um botão que não faz nada."""
    html = _home(logada)

    assert 'id="sair-dialogo"' in html
    assert 'class="overlay" id="sair-dialogo"' in html, "o diálogo nasceu aberto"
    assert 'action="/sair"' in html and 'method="post"' in html
    assert "csrfmiddlewaretoken" in html


def test_a_pagina_da_fila_tambem_traz_o_dialogo(db):
    """A fila é a tela de quem trabalha em pé, e a única do produto sem menu
    lateral: se o diálogo dependesse do shell inteiro, o vendedor seria
    justamente quem ficaria sem ele."""
    from tests.fila_cenario import logado, pessoa_na_loja, sylvia

    empresa, matriz, _titular = sylvia()
    pessoa_na_loja("ana", empresa, matriz)
    html = logado("ana").get("/fila").content.decode()

    assert 'id="sair-dialogo"' in html
    assert 'class="iconbtn" href="/sair"' not in html


def test_a_entrada_nao_traz_o_dialogo(db):
    """Sem sessão não há de onde sair, e a tela de entrada não tem shell."""
    html = Client().get(reverse("entrar")).content.decode()

    assert "sair-dialogo" not in html


def test_o_script_do_dialogo_vem_em_toda_pagina(logada):
    """Quem abre o diálogo é ele, e ele é do site inteiro — não de uma tela."""
    assert "/static/plataforma/sair.js" in _home(logada)


def test_o_dialogo_diz_de_qual_sessao_se_esta_saindo(logada):
    """No balcão, o computador é compartilhado: a única dúvida real de quem
    vai sair é DE QUEM é a sessão aberta. O nome é o mesmo que o cabeçalho
    mostra."""
    assert "Você está conectado como sylvia@teste.com" in _home(logada)
