"""A rota que troca a filial do contexto — `POST /filial/trocar`.

Mesmo roteiro de `tests/test_login.py::TestSair`: a ação muda estado, então
GET nunca pode disparar (um `<img src="...">` em qualquer página não pode
trocar o contexto de quem a abriu por baixo dela).
"""

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from tests.conftest import alocar, matriz_do_teste

SENHA = "segredo-de-teste"

pytestmark = pytest.mark.django_db


@pytest.fixture
def matriz():
    from plataforma.models import Filial

    return matriz_do_teste()


@pytest.fixture
def loja(matriz):
    from plataforma.models import Filial

    return Filial.objects.create(empresa=matriz.empresa, nome="Loja 1", apelido="Loja 1")


@pytest.fixture
def ana(loja):
    pessoa = Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
    alocar(pessoa, loja.empresa, "vendedor", filial=loja)
    return pessoa


@pytest.fixture
def cliente_de_ana(ana):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
    return c


class TestMetodo:
    def test_get_sem_id_nao_tem_o_que_confirmar(self, cliente_de_ana):
        """Sem `?filial_id=`, não há filial nenhuma para perguntar sobre —
        mesmo vocabulário de recusa do resto da rota."""
        resposta = cliente_de_ana.get(reverse("filial_trocar"))
        assert resposta.status_code == 404

    def test_get_com_id_alcancado_confirma_sem_mudar_a_sessao(
        self, cliente_de_ana, loja,
    ):
        """GET não é mais 405: mostra a confirmação — e continua sem
        efeito nenhum sozinho, a mesma garantia de antes."""
        from plataforma.contexto import CHAVE

        resposta = cliente_de_ana.get(reverse("filial_trocar"), {"filial_id": str(loja.pk)})

        assert resposta.status_code == 200
        assert CHAVE not in cliente_de_ana.session

    def test_get_mostra_um_formulario_de_post_de_verdade_com_o_id(
        self, cliente_de_ana, loja,
    ):
        from plataforma.contexto import CHAVE

        html = cliente_de_ana.get(
            reverse("filial_trocar"), {"filial_id": str(loja.pk)},
        ).content.decode()

        assert f'action="{reverse("filial_trocar")}"' in html
        assert 'method="post"' in html
        assert "csrfmiddlewaretoken" in html
        assert f'name="{CHAVE}" value="{loja.pk}"' in html
        assert loja.apelido in html

    def test_get_com_id_nao_alcancado_e_404_e_nao_nomeia_a_filial(
        self, cliente_de_ana, matriz,
    ):
        """`matriz` existe e está ativa — só não foi liberada para `ana`. A
        confirmação não pode vazar o nome de uma filial que a pessoa não
        alcança."""
        resposta = cliente_de_ana.get(reverse("filial_trocar"), {"filial_id": str(matriz.pk)})

        assert resposta.status_code == 404
        assert matriz.apelido.encode() not in resposta.content

    def test_outro_metodo_e_recusado_com_405(self, cliente_de_ana, loja):
        resposta = cliente_de_ana.put(
            reverse("filial_trocar"), {"filial_id": str(loja.pk)},
        )
        assert resposta.status_code == 405

    def test_sem_sessao_manda_para_o_login(self, loja):
        resposta = Client().post(reverse("filial_trocar"), {"filial_id": str(loja.pk)})
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]


class TestConfirmarPeloFormulario:
    def test_o_post_que_o_formulario_da_confirmacao_dispara_funciona(
        self, cliente_de_ana, loja,
    ):
        """Fim a fim: GET pergunta (e nomeia o campo oculto como
        `plataforma.contexto.CHAVE`), o POST que o `<form>` de fato envia é
        o mesmo que já trocava a filial."""
        from plataforma.contexto import CHAVE, filial_atual

        cliente_de_ana.get(reverse("filial_trocar"), {"filial_id": str(loja.pk)})

        resposta = cliente_de_ana.post(reverse("filial_trocar"), {CHAVE: str(loja.pk)})

        assert resposta.status_code == 302
        pedido = cliente_de_ana.get(reverse("home")).wsgi_request
        assert filial_atual(pedido) == loja


class TestTrocaValida:
    def test_troca_grava_na_sessao_e_redireciona(self, cliente_de_ana, loja):
        from plataforma.contexto import CHAVE

        resposta = cliente_de_ana.post(reverse("filial_trocar"), {"filial_id": str(loja.pk)})

        assert resposta.status_code == 302
        assert cliente_de_ana.session[CHAVE] == loja.pk

    def test_a_troca_vale_na_proxima_requisicao(self, cliente_de_ana, loja):
        from plataforma.contexto import filial_atual

        cliente_de_ana.post(reverse("filial_trocar"), {"filial_id": str(loja.pk)})
        pedido = cliente_de_ana.get(reverse("home")).wsgi_request

        assert filial_atual(pedido) == loja


class TestTrocaRecusada:
    def test_recusa_filial_que_a_pessoa_nao_alcanca(self, cliente_de_ana, matriz):
        """`matriz` existe e está ativa — só `ana` não tem alocação nela
        (a fixture só a alocou na `loja`)."""
        resposta = cliente_de_ana.post(reverse("filial_trocar"), {"filial_id": str(matriz.pk)})
        assert resposta.status_code == 404

    def test_a_recusa_nao_muda_a_filial_do_contexto(self, cliente_de_ana, matriz, loja):
        from plataforma.contexto import filial_atual

        cliente_de_ana.post(reverse("filial_trocar"), {"filial_id": str(loja.pk)})
        cliente_de_ana.post(reverse("filial_trocar"), {"filial_id": str(matriz.pk)})

        pedido = cliente_de_ana.get(reverse("home")).wsgi_request
        assert filial_atual(pedido) == loja

    def test_recusa_id_que_nao_existe(self, cliente_de_ana):
        resposta = cliente_de_ana.post(reverse("filial_trocar"), {"filial_id": "999999"})
        assert resposta.status_code == 404


class TestOCabecalhoMandaOsDoisNiveisParaAEmpresa:
    """O formulário do cabeçalho é um só: quando há seletor de empresa, os dois
    selects vão para `empresa_trocar` (R8 do plano 2). Empresa igual à atual
    com filial pedida é troca de filial, e a rota repassa."""

    def test_mesma_empresa_com_filial_repassa_para_a_troca_de_filial(
            self, cliente_de_ana, loja):
        from plataforma.contexto import CHAVE, CHAVE_EMPRESA

        resposta = cliente_de_ana.get(reverse("empresa_trocar"), {
            CHAVE_EMPRESA: str(loja.empresa_id), CHAVE: str(loja.pk)})

        assert resposta.status_code == 302
        assert resposta["Location"] == (
            reverse("filial_trocar") + f"?{CHAVE}={loja.pk}")

    def test_o_repasse_nao_abre_filial_que_a_pessoa_nao_alcanca(
            self, cliente_de_ana, matriz):
        """O repasse não valida nada sozinho: quem recusa é a rota da filial,
        com o mesmo 404 de sempre."""
        from plataforma.contexto import CHAVE, CHAVE_EMPRESA

        resposta = cliente_de_ana.get(reverse("empresa_trocar"), {
            CHAVE_EMPRESA: str(matriz.empresa_id), CHAVE: str(matriz.pk)},
            follow=True)
        assert resposta.status_code == 404


class TestVoltarParaAPagina:
    """`?voltar=` leva de volta à página de onde a troca saiu (a fila, no Fila
    Zero), e só para um caminho desta instalação: um endereço de fora faria a
    troca de loja virar redirecionamento aberto para phishing."""

    def test_a_confirmacao_carrega_o_voltar(self, cliente_de_ana, loja):
        resposta = cliente_de_ana.get(
            reverse("filial_trocar"), {"filial_id": loja.pk, "voltar": "/fila"})
        assert '<input type="hidden" name="voltar" value="/fila"' in resposta.content.decode()

    def test_depois_da_troca_volta_para_a_pagina(self, cliente_de_ana, loja):
        resposta = cliente_de_ana.post(
            reverse("filial_trocar"), {"filial_id": loja.pk, "voltar": "/fila"})
        assert resposta["Location"] == "/fila"

    @pytest.mark.parametrize("voltar", ["https://golpe.example/", "//golpe.example",
                                        "javascript:alert(1)", "fila"])
    def test_endereco_de_fora_cai_na_raiz(self, cliente_de_ana, loja, voltar):
        resposta = cliente_de_ana.post(
            reverse("filial_trocar"), {"filial_id": loja.pk, "voltar": voltar})
        assert resposta["Location"] == "/"
