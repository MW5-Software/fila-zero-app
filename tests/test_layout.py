"""O shell: a tela não constrói sidebar nem header, ela os recebe.

É esta indireção que garante que as 20 instalações desenham o mesmo shell —
uma tela não tem como recriar o cabeçalho, porque não o constrói.
"""

import pytest

from nucleo.layout import Crumb, NavItem
from nucleo.permissoes import User
from nucleo.rendering import create_environment, use_environment
from nucleo.site import Site
from nucleo.theme import Brand


@pytest.fixture(autouse=True)
def ambiente():
    with use_environment(create_environment()):
        yield


@pytest.fixture
def site():
    return Site(
        brand=Brand(client_name="Teste", system_name="Portal de Teste",
                    primary="#1e40af"),
        nav=[
            NavItem("Início", "home", "/"),
            NavItem("Frete", "truck", "/frete", permission="frete.ver"),
            NavItem("Usuários", "users", "/usuarios", permission="usuarios.ver"),
        ],
    )


class TestOShell:
    def test_a_pagina_traz_sidebar_header_e_rodape(self, site):
        """Afirma o shell pela marcação estrutural, e não por texto que
        sobrevive a `chrome=False` — "Portal de Teste" vem de
        `document_title` e aparece em `<title>` mesmo sem shell."""
        html = str(site.page(title="Início", content="miolo").render())
        assert "miolo" in html
        assert "<aside" in html and 'class="side-nav"' in html
        assert "<header" in html
        assert "<footer" in html

    def test_sem_chrome_o_shell_nao_e_desenhado(self, site):
        """A tela de login é a única situação em que o shell não se aplica."""
        sem = str(site.page(title="x", content="miolo", chrome=False).render())
        assert "miolo" in sem
        assert "<aside" not in sem
        assert "<header" not in sem
        assert "<footer" not in sem

    def test_o_titulo_da_tela_aparece(self, site):
        html = str(site.page(title="Simulador de Frete", content="").render())
        assert "Simulador de Frete" in html

    def test_a_trilha_aparece_quando_informada(self, site):
        html = str(site.page(
            title="KM Padrão", content="",
            crumbs=[Crumb("Consultas", "/consultas"), Crumb("KM Padrão", "")],
        ).render())
        assert "Consultas" in html


class TestOMenuFiltraPorPermissao:
    def test_quem_nao_tem_a_permissao_nao_ve_o_item(self, site):
        ana = User(id="1", name="Ana", permissions={"frete.ver"})
        html = str(site.page(title="x", content="", user=ana).render())
        assert "/frete" in html
        assert "/usuarios" not in html

    def test_item_sem_permissao_declarada_aparece_para_quem_entrou(self, site):
        ana = User(id="1", name="Ana", permissions=set())
        html = str(site.page(title="x", content="", user=ana).render())
        assert "Início" in html

    def test_superusuario_ve_tudo(self, site):
        raiz = User(id="9", name="MW5", superuser=True)
        html = str(site.page(title="x", content="", user=raiz).render())
        assert "/frete" in html
        assert "/usuarios" in html

    def test_sem_usuario_nenhum_item_com_permissao_aparece(self, site):
        """O padrão de `Site.can` é a checagem real, e não um 'mostra tudo':
        esquecer de ligar a auth não pode virar vazamento de menu."""
        html = str(site.page(title="x", content="", user=None).render())
        assert "/frete" not in html
        assert "/usuarios" not in html


class TestOTema:
    def test_a_folha_de_tema_e_referenciada_no_caminho_configurado(self, site):
        site.theme_href = "/tema.css"
        html = str(site.page(title="x", content="").render())
        assert "/tema.css" in html
