"""A MW5 configura o menu de cada empresa na tela de Empresas
(spec de 15/09/2026, §5). O titular não mexe: a cara de um cliente é assunto
da MW5, a mesma decisão da Aparência da instalação."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from contas.models import RegistroDeAuditoria, Usuario
from plataforma.models import AparenciaDaEmpresa, Empresa
from tests.conftest import abrir_conta, email_de

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"png de mentira, so a assinatura importa"


def _entrar(email, senha="x"):
    cliente = Client()
    resposta = cliente.post(reverse("entrar"), {"usuario": email, "senha": senha})
    assert resposta.status_code == 302, "o login do teste não entrou"
    return cliente


@pytest.fixture
def cenario():
    from contas.fabrica import aplicar
    from contas.models import Nivel

    alfa = Empresa.objects.create(razao_social="Alfa")
    aplicar(abrir_conta(alfa, "tita"), Nivel.TITULAR)
    Usuario.objects.create_superuser(email="raiz@teste.com", password="x")
    return {"alfa": alfa, "mw5": _entrar("raiz@teste.com"),
            "titular": _entrar(email_de("tita"))}


def _url(empresa):
    return reverse("empresa_menu", args=[empresa.pk])


def _aparencia(cenario):
    return AparenciaDaEmpresa.objects.filter(empresa=cenario["alfa"]).first()


class TestAMW5Configura:

    def test_grava_as_cores(self, cenario):
        resposta = cenario["mw5"].post(_url(cenario["alfa"]), {
            "acao": "cores", "sidebar_bg": "#112233", "sidebar_text": "#ffffff"})
        assert resposta.status_code == 302
        aparencia = _aparencia(cenario)
        assert (aparencia.sidebar_bg, aparencia.sidebar_text) == \
            ("#112233", "#ffffff")

    def test_envia_e_remove_o_logo(self, cenario):
        cenario["mw5"].post(_url(cenario["alfa"]), {
            "acao": "logo",
            "arquivo": SimpleUploadedFile("l.png", PNG, "image/png")})
        assert _aparencia(cenario).logo_tipo == "image/png"
        cenario["mw5"].post(_url(cenario["alfa"]), {"acao": "remover_logo"})
        assert _aparencia(cenario).logo_tipo == ""

    def test_trocar_o_logo_nao_apaga_as_cores(self, cenario):
        cenario["mw5"].post(_url(cenario["alfa"]), {
            "acao": "cores", "sidebar_bg": "#112233", "sidebar_text": ""})
        cenario["mw5"].post(_url(cenario["alfa"]), {
            "acao": "logo",
            "arquivo": SimpleUploadedFile("l.png", PNG, "image/png")})
        assert _aparencia(cenario).sidebar_bg == "#112233"

    def test_cor_invalida_nao_grava_e_explica(self, cenario):
        resposta = cenario["mw5"].post(_url(cenario["alfa"]), {
            "acao": "cores", "sidebar_bg": "azul", "sidebar_text": ""})
        assert resposta.status_code == 200
        assert "cor hexadecimal" in resposta.content.decode()
        aparencia = _aparencia(cenario)
        assert aparencia is None or aparencia.sidebar_bg == ""

    def test_texto_ilegivel_sobre_o_fundo_e_recusado(self, cenario):
        """A mesma conferência de contraste da Aparência: branco sobre amarelo
        claro não se lê, e a recusa é na hora da escolha."""
        resposta = cenario["mw5"].post(_url(cenario["alfa"]), {
            "acao": "cores", "sidebar_bg": "#ffff99", "sidebar_text": "#ffffff"})
        assert resposta.status_code == 200
        assert "legível" in resposta.content.decode()

    def test_logo_invalido_nao_grava(self, cenario):
        resposta = cenario["mw5"].post(_url(cenario["alfa"]), {
            "acao": "logo",
            "arquivo": SimpleUploadedFile("l.png", b"nao-e-imagem", "image/png")})
        assert resposta.status_code == 200
        aparencia = _aparencia(cenario)
        assert aparencia is None or aparencia.logo_tipo == ""

    def test_a_mudanca_fica_na_trilha(self, cenario):
        cenario["mw5"].post(_url(cenario["alfa"]), {
            "acao": "cores", "sidebar_bg": "#112233", "sidebar_text": ""})
        assert RegistroDeAuditoria.objects.filter(
            acao="menu_da_empresa_alterado").exists()

    def test_a_tela_de_empresas_da_mw5_tem_o_modal(self, cenario):
        html = cenario["mw5"].get(reverse("empresa")).content.decode()
        assert "Menu desta empresa" in html
        assert f'action="{_url(cenario["alfa"])}"' in html


class TestOTitularNao:

    def test_a_rota_responde_como_inexistente(self, cenario):
        resposta = cenario["titular"].post(_url(cenario["alfa"]), {
            "acao": "cores", "sidebar_bg": "#000000", "sidebar_text": ""})
        assert resposta.status_code == 404
        assert _aparencia(cenario) is None

    def test_a_tela_dele_nao_tem_o_modal(self, cenario):
        html = cenario["titular"].get(reverse("empresa")).content.decode()
        assert "Menu desta empresa" not in html


class TestOSeletorDeCor:
    """Cada campo de cor do modal ganha um seletor (15/09/2026). O texto fica:
    vazio quer dizer "herda da instalação", e o `<input type="color">` nativo
    não tem estado vazio."""

    def test_os_campos_de_cor_vem_marcados_com_a_cor_herdada(self, cenario):
        import re

        from plataforma.marca import marca_da_instalacao

        html = cenario["mw5"].get(reverse("empresa")).content.decode()
        tokens = marca_da_instalacao().tokens("light")
        for nome, token in (("sidebar_bg", "sidebar-bg"),
                            ("sidebar_text", "sidebar-text")):
            campo = re.search(rf'<input[^>]*name="{nome}"[^>]*>', html)
            assert campo, f"o campo {nome} sumiu do modal"
            assert "data-seletor-de-cor" in campo.group(0)
            # O seletor mostra a cor que VALE quando o campo está vazio.
            assert f'data-cor-herdada="{tokens[token]}"' in campo.group(0)

    def test_a_tela_carrega_o_script_do_seletor(self, cenario):
        html = cenario["mw5"].get(reverse("empresa")).content.decode()
        assert "/static/plataforma/seletor_de_cor.js" in html

    def test_o_script_sincroniza_os_dois_lados(self):
        from pathlib import Path

        script = Path("plataforma/static/plataforma/seletor_de_cor.js").read_text()
        assert 'type = "color"' in script
        # Seletor → texto, e texto → seletor.
        assert 'seletor.addEventListener("input"' in script
        assert 'campo.addEventListener("input"' in script
        # "#abc" também é cor válida no texto, mas o seletor só aceita
        # "#rrggbb": sem expandir, digitar a forma curta quebraria o seletor.
        assert "function seisDigitos" in script
