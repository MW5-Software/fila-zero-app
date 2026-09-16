"""A marca da tela é a da instalação com o menu da empresa por cima
(spec de 15/09/2026, §5).

Cada empresa pode ter logo, fundo e texto do menu, e SÓ isso: entrada,
rodapé e o resto do tema continuam da instalação. Quem decide qual empresa é
a pessoa VISTA — a MW5 vê a instalação, e em "ver como" vê a do cliente.
"""

import pytest
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from comum.sessao import CHAVE, CHAVE_ALVO
from contas.models import Usuario
from plataforma.marca import (
    CAMINHO_DO_LOGO_DA_EMPRESA, TOKENS_DO_MENU, folha_do_menu,
    marca_da_instalacao, marca_da_requisicao,
)
from plataforma.models import AparenciaDaEmpresa, Empresa
from tests.conftest import abrir_conta, alocar

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"png de mentira, so a assinatura importa"


def _pedido(pessoa, alvo=None):
    """Um request com a sessão de `pessoa` (e personificando `alvo`). Sessão
    como dicionário cru, como os testes de guarda já fazem."""
    pedido = RequestFactory().get("/")
    pedido.session = {CHAVE: str(pessoa.pk)}
    if alvo is not None:
        pedido.session[CHAVE_ALVO] = str(alvo.pk)
    return pedido


@pytest.fixture
def alfa():
    empresa = Empresa.objects.create(razao_social="Alfa")
    titular = abrir_conta(empresa, "tita")
    AparenciaDaEmpresa.objects.create(
        empresa=empresa, sidebar_bg="#112233", sidebar_text="#ffffff", logo=PNG)
    return empresa, titular


def _menu(marca):
    return marca.tokens("light")["sidebar-bg"]


class TestDeQuemEAMarca:

    def test_titular_ve_o_menu_da_empresa(self, alfa):
        _empresa, titular = alfa
        marca = marca_da_requisicao(_pedido(titular))
        assert _menu(marca) == "#112233"
        assert marca.assets.sidebar_logo == CAMINHO_DO_LOGO_DA_EMPRESA

    def test_membro_ve_o_menu_da_empresa_da_alocacao(self, alfa):
        empresa, _titular = alfa
        ana = Usuario.objects.create_user(email="ana@teste.com", password="x")
        alocar(ana, empresa)
        assert _menu(marca_da_requisicao(_pedido(ana))) == "#112233"

    def test_mw5_ve_a_da_instalacao(self, alfa):
        raiz = Usuario.objects.create_superuser(email="raiz@teste.com",
                                                password="x")
        assert _menu(marca_da_requisicao(_pedido(raiz))) == \
            _menu(marca_da_instalacao())

    def test_mw5_vendo_como_ve_a_do_cliente(self, alfa):
        _empresa, titular = alfa
        raiz = Usuario.objects.create_superuser(email="raiz@teste.com",
                                                password="x")
        assert _menu(marca_da_requisicao(_pedido(raiz, alvo=titular))) == \
            "#112233"

    def test_empresa_sem_aparencia_e_a_instalacao(self):
        beta = Empresa.objects.create(razao_social="Beta")
        titular = abrir_conta(beta, "titb")
        marca, instalacao = marca_da_requisicao(_pedido(titular)), \
            marca_da_instalacao()
        assert marca.tokens("light") == instalacao.tokens("light")
        assert marca.assets == instalacao.assets


class TestOQueMuda:

    def test_campo_em_branco_herda(self, alfa):
        empresa, titular = alfa
        aparencia = empresa.aparencia
        aparencia.sidebar_text = ""
        aparencia.logo = None
        aparencia.save()
        marca, instalacao = marca_da_requisicao(_pedido(titular)), \
            marca_da_instalacao()
        assert marca.tokens("light")["sidebar-text"] == \
            instalacao.tokens("light")["sidebar-text"]
        assert marca.assets.sidebar_logo == instalacao.assets.sidebar_logo

    def test_rodape_entrada_e_primaria_nao_mudam(self, alfa):
        _empresa, titular = alfa
        marca, instalacao = marca_da_requisicao(_pedido(titular)), \
            marca_da_instalacao()
        assert marca.assets.footer_logo == instalacao.assets.footer_logo
        assert marca.assets.login_logo == instalacao.assets.login_logo
        assert marca.tokens("light")["primary"] == \
            instalacao.tokens("light")["primary"]

    def test_hover_e_selecionado_acompanham_o_fundo_novo(self, alfa):
        """Derivados do fundo pelo tema: trocar a cor do menu e manter o
        hover calculado para o azul da instalação seria hover invisível."""
        _empresa, titular = alfa
        assert marca_da_requisicao(_pedido(titular)).tokens("light")[
            "sidebar-hover-bg"] != marca_da_instalacao().tokens("light")[
            "sidebar-hover-bg"]


class TestAFolhaDoMenu:

    def test_so_tem_variaveis_do_menu(self, alfa):
        _empresa, titular = alfa
        folha = folha_do_menu(marca_da_requisicao(_pedido(titular)))
        declaradas = {linha.strip().split(":")[0].lstrip("-")
                      for linha in folha.splitlines()
                      if linha.strip().startswith("--")}
        assert declaradas == set(TOKENS_DO_MENU)
        assert "--sidebar-bg:#112233;" in folha

    def test_tem_as_mesmas_camadas_do_tema(self, alfa):
        """`:root[data-theme="light"]` do `/tema.css` vence `:root` por
        especificidade; sem a mesma camada aqui, a cor da empresa perderia
        no navegador em que o tema foi escolhido."""
        _empresa, titular = alfa
        folha = folha_do_menu(marca_da_requisicao(_pedido(titular)))
        assert ':root[data-theme="light"]{' in folha
        assert ':root[data-theme="dark"]{' in folha


class TestOModelo:

    def test_logo_invalido_e_recusado(self):
        empresa = Empresa.objects.create(razao_social="Beta")
        with pytest.raises(ValidationError):
            AparenciaDaEmpresa(empresa=empresa, logo=b"nao-e-imagem").save()

    def test_o_tipo_do_logo_e_decidido_pelo_conteudo(self):
        empresa = Empresa.objects.create(razao_social="Beta")
        aparencia = AparenciaDaEmpresa(empresa=empresa, logo=PNG,
                                       logo_tipo="image/svg+xml")
        aparencia.save()
        assert aparencia.logo_tipo == "image/png"

    def test_cor_invalida_e_recusada(self):
        empresa = Empresa.objects.create(razao_social="Gama")
        with pytest.raises(ValidationError):
            AparenciaDaEmpresa(empresa=empresa, sidebar_bg="azul").save()

    def test_sem_logo_o_tipo_fica_vazio(self):
        empresa = Empresa.objects.create(razao_social="Delta")
        aparencia = AparenciaDaEmpresa.objects.create(empresa=empresa,
                                                      sidebar_bg="#000000")
        assert (aparencia.logo, aparencia.logo_tipo) == (None, "")


def _entrar(email, senha="x"):
    from django.test import Client
    from django.urls import reverse

    cliente = Client()
    resposta = cliente.post(reverse("entrar"), {"usuario": email, "senha": senha})
    assert resposta.status_code == 302, "o login do teste não entrou"
    return cliente


class TestAWeb:
    """A tela logada veste o menu da empresa; o `/tema.css` não muda."""

    def test_a_pagina_carrega_a_folha_da_empresa_depois_da_casa(self, alfa):
        from tests.conftest import email_de

        html = _entrar(email_de("tita")).get("/").content.decode()
        assert "/tema-da-empresa.css" in html
        assert (html.index("/static/plataforma/kronos.css")
                < html.index("/tema-da-empresa.css"))

    def test_a_folha_da_empresa_traz_a_cor_e_nao_vai_para_cache_compartilhado(
            self, alfa):
        from tests.conftest import email_de

        resposta = _entrar(email_de("tita")).get("/tema-da-empresa.css")
        assert resposta.status_code == 200
        assert resposta["Content-Type"].startswith("text/css")
        assert "--sidebar-bg:#112233;" in resposta.content.decode()
        assert "private" in resposta["Cache-Control"]

    def test_sem_sessao_a_folha_nao_abre(self, alfa):
        from django.test import Client

        assert Client().get("/tema-da-empresa.css").status_code in (302, 401, 404)

    def test_mw5_recebe_folha_vazia(self, alfa):
        Usuario.objects.create_superuser(email="raiz@teste.com", password="x")
        corpo = _entrar("raiz@teste.com").get("/tema-da-empresa.css").content
        assert b"--sidebar-bg" not in corpo

    def test_o_tema_da_instalacao_continua_igual_para_todos(self, alfa):
        from django.test import Client
        from tests.conftest import email_de

        anonimo = Client().get("/tema.css").content
        logado = _entrar(email_de("tita")).get("/tema.css").content
        assert anonimo == logado
        assert b"#112233" not in logado

    def test_o_logo_e_o_da_empresa_de_quem_pede(self, alfa):
        from nucleo.images import CABECALHOS_SEGUROS
        from tests.conftest import email_de

        resposta = _entrar(email_de("tita")).get(CAMINHO_DO_LOGO_DA_EMPRESA)
        assert resposta.status_code == 200
        assert resposta["Content-Type"] == "image/png"
        for chave, valor in CABECALHOS_SEGUROS.items():
            if chave != "Cache-Control":
                assert resposta[chave] == valor
        # `private` por cima do `no-cache` dos cabeçalhos seguros: a resposta
        # depende da sessão.
        assert resposta["Cache-Control"] == "private, no-cache"

    def test_o_logo_de_uma_empresa_nao_sai_para_outra(self, alfa):
        from tests.conftest import email_de

        beta = Empresa.objects.create(razao_social="Beta")
        abrir_conta(beta, "titb")
        resposta = _entrar(email_de("titb")).get(CAMINHO_DO_LOGO_DA_EMPRESA)
        assert resposta.status_code == 404

    def test_o_menu_aponta_para_o_logo_da_empresa(self, alfa):
        from tests.conftest import email_de

        html = _entrar(email_de("tita")).get("/").content.decode()
        assert f'src="{CAMINHO_DO_LOGO_DA_EMPRESA}' in html
