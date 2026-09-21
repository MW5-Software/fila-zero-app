"""A tela de Parâmetros: o que o código declara, valendo por instalação.

Segue de perto `tests/test_tela_empresa.py` (uma tela sem tabela, sem
criar/remover de verdade — aqui "remover" é "restaurar ao padrão") e
`tests/test_modulo_exemplo.py` para a fronteira `so_mw5`.
"""

import pytest
from django.contrib.auth.models import Permission
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from tests.conftest import dar_permissoes

SENHA = "segredo-de-teste"


@pytest.fixture
def admin_do_cliente(db):
    """Um usuário COMUM com `parametros.editar` — não superusuário. Mesmo
    raciocínio de `tests/test_tela_empresa.py::admin_do_cliente`: com
    superusuário, a fronteira `so_mw5` passaria por acidente."""
    pessoa = Usuario.objects.create_user(email="admin@teste.com", password=SENHA)
    dar_permissoes(pessoa, "parametros_editar")
    return pessoa


@pytest.fixture
def cliente_admin(admin_do_cliente):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "admin@teste.com", "senha": SENHA})
    return c


@pytest.fixture
def raiz(db):
    return Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)


@pytest.fixture
def raiz_logado(raiz):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
    return c


class TestQuemEntra:
    def test_o_admin_com_a_permissao_abre(self, cliente_admin):
        assert cliente_admin.get(reverse("parametros")).status_code == 200

    def test_usuario_comum_nao_descobre_que_a_tela_existe(self, db):
        Usuario.objects.create_user(email="comum@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "comum@teste.com", "senha": SENHA})
        assert c.get(reverse("parametros")).status_code == 404

    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("parametros"))
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_modulo_desligado_e_404_mesmo_com_a_permissao(self, cliente_admin, db):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="parametros").update(ativo=False)
        assert cliente_admin.get(reverse("parametros")).status_code == 404


class TestAgrupamentoEValores:
    def test_mostra_o_rotulo_e_a_ajuda_de_um_parametro_visivel(self, cliente_admin):
        html = cliente_admin.get(reverse("parametros")).content.decode()
        assert "Nova filial nasce ativa" in html
        assert "uma filial recém-criada já aparece no seletor" in html

    def test_parametro_nunca_mudado_mostra_o_selo_de_padrao(self, cliente_admin):
        html = cliente_admin.get(reverse("parametros")).content.decode()
        assert "Padrão" in html

    def test_parametro_mudado_mostra_o_selo_de_personalizado(self, cliente_admin):
        from plataforma.parametro_catalogo import definir

        definir("nova_filial_nasce_ativa", "0")
        html = cliente_admin.get(reverse("parametros")).content.decode()
        assert "Personalizado" in html


class TestOParametroDaMetaDeGestor:
    """O parâmetro do Fila Zero (`fila/parametro.py`) no mesmo caminho dos da
    base: declarado no `ready()` do app, visível para quem tem
    `parametros.editar` (`so_mw5=False`, porque é regra de negócio) e gravável.

    Sem esta prova, o registro do parâmetro poderia ficar só no código do app
    e ninguém veria a caixa na tela — o defeito que o cliente descreveria como
    "pedi para configurar e não tem onde".
    """

    def test_o_admin_do_cliente_ve_o_parametro(self, cliente_admin):
        html = cliente_admin.get(reverse("parametros")).content.decode()
        assert "Meta para quem gerencia a loja" in html
        assert "Metas" in html

    def test_salvar_muda_o_que_vale_nesta_instalacao(self, cliente_admin, db):
        from plataforma.parametro_catalogo import valor_de

        assert valor_de("meta_para_gestor") is False
        cliente_admin.post(reverse("parametros"), {
            "acao": "salvar", "chave": "meta_para_gestor", "valor": "on",
        })
        assert valor_de("meta_para_gestor") is True


class TestAFronteiraSoMw5:
    """`itens_por_pagina` (`plataforma.parametro`) é `so_mw5=True` — o admin
    do cliente nem vê a linha, e não só porque ela vem desabilitada."""

    def test_admin_do_cliente_nao_ve_o_parametro_so_mw5(self, cliente_admin):
        html = cliente_admin.get(reverse("parametros")).content.decode()
        assert "Itens por página" not in html

    def test_a_mw5_ve_o_parametro_so_mw5(self, raiz_logado):
        html = raiz_logado.get(reverse("parametros")).content.decode()
        assert "Itens por página" in html

    def test_post_do_admin_do_cliente_para_o_parametro_so_mw5_e_recusado(
        self, cliente_admin, db,
    ):
        """Esconder na tela não bastaria sozinho — o POST tem que recusar
        de novo, mesmo que a pessoa forje o campo escondido."""
        from plataforma.parametro_catalogo import valor_de

        resposta = cliente_admin.post(reverse("parametros"), {
            "acao": "salvar", "chave": "itens_por_pagina", "valor": "999",
        })

        assert "Parâmetro não encontrado" in resposta.content.decode()
        assert valor_de("itens_por_pagina") == 25

    def test_a_mw5_consegue_gravar_o_parametro_so_mw5(self, raiz_logado, db):
        from plataforma.parametro_catalogo import valor_de

        raiz_logado.post(reverse("parametros"), {
            "acao": "salvar", "chave": "itens_por_pagina", "valor": "10",
        })
        assert valor_de("itens_por_pagina") == 10


class TestSalvar:
    def test_salvar_numero_grava_e_audita(self, raiz_logado, db):
        from contas.models import RegistroDeAuditoria
        from plataforma.parametro_catalogo import valor_de

        raiz_logado.post(reverse("parametros"), {
            "acao": "salvar", "chave": "itens_por_pagina", "valor": "50",
        })

        assert valor_de("itens_por_pagina") == 50
        assert RegistroDeAuditoria.objects.filter(
            acao="parametro_alterado", alvo="Itens por página",
        ).exists()

    def test_numero_invalido_e_recusado_com_frase_na_tela(self, raiz_logado, db):
        from plataforma.parametro_catalogo import valor_de

        resposta = raiz_logado.post(reverse("parametros"), {
            "acao": "salvar", "chave": "itens_por_pagina", "valor": "abacate",
        })

        assert "Informe um número inteiro" in resposta.content.decode()
        assert valor_de("itens_por_pagina") == 25

    def test_salvar_sim_nao_desmarcado_grava_falso(self, cliente_admin, db):
        from plataforma.parametro_catalogo import valor_de

        cliente_admin.post(reverse("parametros"), {
            "acao": "salvar", "chave": "nova_filial_nasce_ativa",
            # sem "valor": um `Checkbox` desmarcado não manda o campo.
        })
        assert valor_de("nova_filial_nasce_ativa") is False

    def test_salvar_sim_nao_marcado_grava_verdadeiro(self, cliente_admin, db):
        from plataforma.parametro_catalogo import definir, valor_de

        definir("nova_filial_nasce_ativa", "0")
        cliente_admin.post(reverse("parametros"), {
            "acao": "salvar", "chave": "nova_filial_nasce_ativa", "valor": "on",
        })
        assert valor_de("nova_filial_nasce_ativa") is True

    def test_chave_desconhecida_e_recusada(self, cliente_admin, db):
        resposta = cliente_admin.post(reverse("parametros"), {
            "acao": "salvar", "chave": "nao-existe", "valor": "x",
        })
        assert "Parâmetro não encontrado" in resposta.content.decode()


class TestRestaurar:
    def test_restaurar_apaga_a_linha_e_audita(self, cliente_admin, db):
        from contas.models import RegistroDeAuditoria
        from plataforma.models import Parametro
        from plataforma.parametro_catalogo import definir, valor_de

        definir("nova_filial_nasce_ativa", "0")
        cliente_admin.post(reverse("parametros"), {
            "acao": "restaurar", "chave": "nova_filial_nasce_ativa",
        })

        assert not Parametro.objects.filter(chave="nova_filial_nasce_ativa").exists()
        assert valor_de("nova_filial_nasce_ativa") is True
        assert RegistroDeAuditoria.objects.filter(
            acao="parametro_restaurado", alvo="Nova filial nasce ativa",
        ).exists()


class TestOMaiusculoDaTela:
    """18/09/2026, pedido do cliente: o título de cada parâmetro e o nome do
    grupo em MAIÚSCULAS.

    No CSS, e não no dado: o rótulo é a frase que o `ParametroSpec` declara e
    que o Babel traduz, e subir a caixa nele faria a frase do `gettext` ser a
    maiúscula — em castelhano também, e em toda leitura que não é tela.
    """

    def test_a_folha_da_tela_sobe_a_caixa_do_titulo_e_do_grupo(self):
        from pathlib import Path

        folha = Path("plataforma/static/plataforma/parametros.css").read_text(
            encoding="utf-8")
        assert ".ch h2, .seclabel { text-transform: uppercase; }" in folha

    def test_a_tela_carrega_a_folha(self, cliente_admin):
        html = cliente_admin.get(reverse("parametros")).content.decode()
        assert "/static/plataforma/parametros.css" in html

    def test_o_rotulo_no_html_continua_como_o_codigo_escreveu(self, cliente_admin):
        """O outro lado: se um dia alguém "resolver" o maiúsculo no `rotulo` do
        parâmetro, a frase do código vira maiúscula e este teste cai."""
        html = cliente_admin.get(reverse("parametros")).content.decode()
        assert "Meta para quem gerencia a loja" in html
        assert "META PARA QUEM GERENCIA A LOJA" not in html


class TestSemTabela:
    """R46 (filtro, ordenação, paginação) é sobre tela com `<table>` — esta
    tela é grupos de cartões e formulários, não uma listagem."""

    def test_a_tela_nao_desenha_tabela_nenhuma(self, cliente_admin):
        html = cliente_admin.get(reverse("parametros")).content.decode()
        assert "<table" not in html
