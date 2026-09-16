"""`GET /api/v1/eu` — tudo o que o app precisa para montar a moldura."""

import pytest
from django.test import Client

from comum.sessao import CHAVE_ALVO
from contas.backend import BackendDjango
from contas.models import Usuario
from plataforma.menu import montar
from plataforma.models import Empresa, Filial
from tests.conftest import (
    abrir_conta, alocar, cargo_com, cliente_da_api, email_de, sessao_do_token,
)

pytestmark = pytest.mark.django_db

SENHA = "segredo-de-teste"


def _eu(api):
    resposta = api.get("/api/v1/eu")
    assert resposta.status_code == 200, resposta.content
    return resposta.json()


def test_sem_token_401():
    resposta = Client().get("/api/v1/eu")
    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "sem_sessao"


def test_titular_ve_a_empresa_a_matriz_e_as_proprias_permissoes():
    from contas.fabrica import aplicar
    from contas.models import Nivel

    alfa = Empresa.objects.create(razao_social="Alfa")
    # `abrir_conta` só cria o titular e liga a empresa; as permissões de
    # fábrica vêm de `aplicar`, como na tela de Usuários.
    aplicar(abrir_conta(alfa, "tita", SENHA), Nivel.TITULAR)
    api, token = cliente_da_api(email_de("tita"), SENHA)
    eu = _eu(api)
    matriz = Filial.objects.get(empresa=alfa, e_matriz=True)
    assert eu["pessoa"]["email"] == email_de("tita")
    assert eu["empresa"]["guid"] == str(alfa.guid)
    assert eu["filial"]["guid"] == str(matriz.guid)
    assert "filiais.editar" in eu["permissoes"]
    assert eu["de_verdade"] is None
    assert eu["superusuario"] is False


def test_membro_a_alocacao_mais_especifica_ganha_e_nao_soma():
    alfa = Empresa.objects.create(razao_social="Alfa")
    abrir_conta(alfa, "tita", SENHA)
    norte = Filial.objects.create(empresa=alfa, nome="Norte", apelido="Norte")
    ana = Usuario.objects.create_user(email=email_de("ana"), password=SENHA)
    alocar(ana, alfa, cargo_com(alfa, "usuarios.editar", nome="amplo"))
    alocar(ana, alfa, cargo_com(alfa, "filiais.editar", nome="estreito"), filial=norte)
    api, token = cliente_da_api(email_de("ana"), SENHA)

    sessao = sessao_do_token(token)
    sessao["filial_id"] = norte.pk
    sessao.save()
    na_norte = _eu(api)
    assert na_norte["filial"]["guid"] == str(norte.guid)
    assert "filiais.editar" in na_norte["permissoes"]
    assert "usuarios.editar" not in na_norte["permissoes"]

    matriz = Filial.objects.get(empresa=alfa, e_matriz=True)
    sessao = sessao_do_token(token)
    sessao["filial_id"] = matriz.pk
    sessao.save()
    na_matriz = _eu(api)
    assert "usuarios.editar" in na_matriz["permissoes"]
    assert "filiais.editar" not in na_matriz["permissoes"]


def test_mw5_olha_uma_conta_so():
    alfa = Empresa.objects.create(razao_social="Alfa")
    abrir_conta(alfa, "tita", SENHA)
    beta = Empresa.objects.create(razao_social="Beta")
    abrir_conta(beta, "bete", SENHA)
    Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)
    api, token = cliente_da_api("raiz@teste.com", SENHA)
    eu = _eu(api)
    assert isinstance(eu["empresa"], dict)
    assert eu["empresa"]["guid"] in {str(alfa.guid), str(beta.guid)}
    assert eu["superusuario"] is True


def test_membro_sem_alocacao_nao_pode_nada():
    Usuario.objects.create_user(email=email_de("solta"), password=SENHA)
    api, token = cliente_da_api(email_de("solta"), SENHA)
    eu = _eu(api)
    assert eu["permissoes"] == []
    assert eu["empresa"] is None


def test_personificando_diz_quem_e_de_verdade():
    Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)
    zeca = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA, nome="Zeca")
    api, token = cliente_da_api("raiz@teste.com", SENHA)
    sessao = sessao_do_token(token)
    sessao[CHAVE_ALVO] = str(zeca.pk)
    sessao.save()
    eu = _eu(api)
    assert eu["pessoa"]["guid"] == str(zeca.guid)
    assert eu["de_verdade"]["email"] == "raiz@teste.com"


def test_o_menu_e_o_mesmo_da_web():
    raiz = Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)
    api, token = cliente_da_api("raiz@teste.com", SENHA)
    esperado = [str(item.label) for item in montar(BackendDjango().buscar(str(raiz.pk)))]
    assert [item["rotulo"] for item in _eu(api)["menu"]] == esperado
    assert esperado, "menu vazio não prova nada"


class TestOQueOCabecalhoEAGavetaPrecisam:
    """O que o app usa para desenhar o cabeçalho e a gaveta como a web: o logo da
    barra lateral, a foto (ou as iniciais) no avatar e a troca de idioma que
    grava na conta."""

    def _entrar(self, **extra):
        pessoa = Usuario.objects.create_user(email=email_de("ana"), password=SENHA, nome="Ana", **extra)
        api, token = cliente_da_api(email_de("ana"), SENHA)
        return pessoa, api

    def test_a_marca_traz_o_logo_da_barra_lateral(self):
        from plataforma.marca import marca_da_instalacao

        pessoa, api = self._entrar()
        assert _eu(api)["marca"]["logo_lateral"] == marca_da_instalacao().assets.sidebar_logo

    def test_sem_foto_diz_que_nao_tem_e_o_avatar_e_404(self):
        pessoa, api = self._entrar()
        assert _eu(api)["pessoa"]["tem_foto"] is False
        resposta = api.get("/api/v1/eu/avatar")
        assert resposta.status_code == 404
        assert resposta.json()["erro"]["codigo"] == "nao_existe"

    def test_com_foto_serve_os_bytes_com_os_cabecalhos_da_web(self):
        from nucleo.images import CABECALHOS_SEGUROS

        pessoa, api = self._entrar(avatar=b"\x89PNG-de-mentira", avatar_tipo="image/png")
        assert _eu(api)["pessoa"]["tem_foto"] is True
        resposta = api.get("/api/v1/eu/avatar")
        assert resposta.status_code == 200
        assert resposta.content == b"\x89PNG-de-mentira"
        assert resposta["Content-Type"] == "image/png"
        for chave, valor in CABECALHOS_SEGUROS.items():
            assert resposta[chave] == valor

    def test_personificando_o_avatar_e_o_de_quem_se_ve(self):
        Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)
        zeca = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA,
                                           avatar=b"foto-do-zeca", avatar_tipo="image/png")
        api, token = cliente_da_api("raiz@teste.com", SENHA)
        sessao = sessao_do_token(token)
        sessao[CHAVE_ALVO] = str(zeca.pk)
        sessao.save()
        assert api.get("/api/v1/eu/avatar").content == b"foto-do-zeca"

    def test_sem_sessao_o_avatar_e_401(self):
        assert Client().get("/api/v1/eu/avatar").status_code == 401

    def test_trocar_o_idioma_grava_na_conta(self):
        pessoa, api = self._entrar()
        resposta = api.post("/api/v1/eu/idioma", {"codigo": "es"}, content_type="application/json")
        assert resposta.status_code == 200
        pessoa.refresh_from_db()
        assert pessoa.idioma == "es"
        assert _eu(api)["idioma"] == "es"

    def test_idioma_que_nao_existe_e_recusado_e_nao_grava(self):
        pessoa, api = self._entrar()
        resposta = api.post("/api/v1/eu/idioma", {"codigo": "xx"}, content_type="application/json")
        assert resposta.status_code == 422
        assert resposta.json()["erro"]["codigo"] == "validacao"
        pessoa.refresh_from_db()
        assert pessoa.idioma == "pt-br"


class TestOMenuDaEmpresa:
    """A gaveta do app veste o menu da empresa, como a barra da web
    (spec de 15/09/2026, §5)."""

    PNG = b"\x89PNG\r\n\x1a\n" + b"png de mentira, so a assinatura importa"

    def _alfa(self, **aparencia):
        from plataforma.models import AparenciaDaEmpresa

        alfa = Empresa.objects.create(razao_social="Alfa")
        abrir_conta(alfa, "tita", SENHA)
        if aparencia:
            AparenciaDaEmpresa.objects.create(empresa=alfa, **aparencia)
        api, _token = cliente_da_api(email_de("tita"), SENHA)
        return alfa, api

    def test_a_marca_traz_as_cores_do_menu_da_empresa(self):
        from plataforma.marca import TOKENS_DO_MENU

        _alfa, api = self._alfa(sidebar_bg="#112233", sidebar_text="#ffffff")
        cores = _eu(api)["marca"]["cores_do_menu"]
        # Com os nomes dos tokens do tema, para a gaveta trocar um pelo outro
        # sem tabela de tradução — e com hover e selecionado já calculados.
        assert set(cores) == set(TOKENS_DO_MENU)
        assert cores["sidebar-bg"] == "#112233"

    def test_sem_aparencia_as_cores_sao_as_do_tema(self):
        _alfa, api = self._alfa()
        assert _eu(api)["marca"]["cores_do_menu"] is None

    def test_com_logo_o_endereco_e_o_da_api(self):
        """O app não manda cookie: o logo da empresa sai pela API, com o
        token, e não pela rota da web."""
        _alfa, api = self._alfa(logo=self.PNG)
        assert _eu(api)["marca"]["logo_lateral"] == "/api/v1/eu/logo-do-menu"

        resposta = api.get("/api/v1/eu/logo-do-menu")
        assert resposta.status_code == 200
        assert resposta["Content-Type"] == "image/png"

    def test_o_logo_da_api_exige_token(self):
        self._alfa(logo=self.PNG)
        assert Client().get("/api/v1/eu/logo-do-menu").status_code == 401

    def test_o_logo_da_api_e_o_da_empresa_do_token(self):
        self._alfa(logo=self.PNG)
        beta = Empresa.objects.create(razao_social="Beta")
        abrir_conta(beta, "titb", SENHA)
        api, _token = cliente_da_api(email_de("titb"), SENHA)
        resposta = api.get("/api/v1/eu/logo-do-menu")
        assert resposta.status_code == 404
        assert resposta.json()["erro"]["codigo"] == "nao_existe"
