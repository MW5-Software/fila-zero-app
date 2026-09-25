"""Em que filial esta requisição está — e o que acontece quando ela deixa de
valer.

Desde a virada dos cargos (14/09/2026), a filial se alcança pela ALOCAÇÃO, e
sempre dentro da empresa atual; antes era `Filial.usuarios`.

O teste que mais importa aqui é `test_filial_perdida_e_descartada_e_cai_
numa_valida`: é o comportamento que dá nome à Task (tirar o acesso vale na
hora), e é o mais fácil de "passar sem provar nada" se a asserção for frouxa
— por isso ele afirma os três fatos junto: não é 500 (aqui, não levanta
exceção), não é a filial perdida, e é uma das que a pessoa ainda alcança.
"""

import pytest
from contas.models import Usuario
from django.test import RequestFactory

from comum.sessao import CHAVE as CHAVE_USUARIO
from tests.conftest import alocar, matriz_do_teste, por_na_conta

pytestmark = pytest.mark.django_db


def _pedido(user_django=None, sessao=None):
    """Um `request` com sessão de mentira — mesmo truque de
    `tests/test_guarda.py`: um dict basta, `filial_atual`/`escolher` só
    chamam `.get` e `__setitem__`."""
    pedido = RequestFactory().get("/")
    pedido.session = dict(sessao or {})
    if user_django is not None:
        pedido.session[CHAVE_USUARIO] = str(user_django.pk)
    return pedido


@pytest.fixture
def ana():
    return Usuario.objects.create_user(email="ana@teste.com", password="x")


@pytest.fixture
def raiz():
    return Usuario.objects.create_superuser(email="raiz@teste.com", password="x")


@pytest.fixture
def matriz():
    from plataforma.models import Filial

    return matriz_do_teste()


@pytest.fixture
def loja(matriz):
    from plataforma.models import Filial

    return Filial.objects.create(empresa=matriz.empresa, nome="Loja 1", apelido="Loja 1")


class TestFiliaisDe:
    def test_superusuario_alcanca_toda_ativa_sem_alocacao_nenhuma(self, raiz, matriz, loja):
        from contas.backend import BackendDjango
        from plataforma.contexto import filiais_de

        user = BackendDjango().buscar(str(raiz.pk))
        assert set(filiais_de(user, matriz.empresa)) == {matriz, loja}

    def test_pessoa_comum_so_alcanca_o_que_foi_liberado(self, ana, matriz, loja):
        from contas.backend import BackendDjango
        from plataforma.contexto import filiais_de

        alocar(ana, loja.empresa, "vendedor", filial=loja)
        user = BackendDjango().buscar(str(ana.pk))

        assert set(filiais_de(user, matriz.empresa)) == {loja}

    def test_pessoa_sem_nenhuma_alocacao_nao_alcanca_nada(self, ana, matriz, loja):
        from contas.backend import BackendDjango
        from plataforma.contexto import filiais_de

        user = BackendDjango().buscar(str(ana.pk))
        assert list(filiais_de(user, matriz.empresa)) == []

    def test_filial_desativada_some_ate_para_superusuario(self, raiz, matriz, loja):
        from contas.backend import BackendDjango
        from plataforma.contexto import filiais_de

        loja.ativa = False
        loja.save()
        user = BackendDjango().buscar(str(raiz.pk))

        assert loja not in filiais_de(user, matriz.empresa)

    def test_none_nao_alcanca_filial_nenhuma(self, matriz):
        from plataforma.contexto import filiais_de

        assert list(filiais_de(None)) == []


class TestFilialAtual:
    def test_sem_escolha_na_sessao_vem_a_primeira_alcancada(self, ana, loja):
        from plataforma.contexto import filial_atual

        alocar(ana, loja.empresa, "vendedor", filial=loja)
        pedido = _pedido(ana)

        assert filial_atual(pedido) == loja

    def test_sem_escolha_na_sessao_a_matriz_vem_antes_de_quem_a_passa_no_alfabeto(self, raiz, matriz):
        """O defeito que se viu no app em 15/09/2026: com "Filial 1" e "Matriz"
        na mesma `ordem`, entrar caía na "Filial 1" — a primeira pelo nome. Quem
        alcança a Matriz começa nela. Desde 16/09/2026 o seletor também a põe na
        frente (`Filial.Meta.ordering`), e as duas regras dizem a mesma coisa."""
        from contas.backend import BackendDjango
        from plataforma.contexto import filiais_de, filial_atual
        from plataforma.models import Filial

        filial_1 = Filial.objects.create(empresa=matriz.empresa, nome="Filial 1", apelido="Filial 1")
        pedido = _pedido(raiz)

        assert filial_atual(pedido) == matriz
        assert list(filiais_de(BackendDjango().buscar(str(raiz.pk)), matriz.empresa))[:2] == [matriz, filial_1]

    def test_pessoa_sem_filial_nenhuma_recebe_none(self, ana):
        from plataforma.contexto import filial_atual

        pedido = _pedido(ana)
        assert filial_atual(pedido) is None

    def test_a_escolha_gravada_na_sessao_e_respeitada(self, ana, matriz, loja):
        from plataforma.contexto import CHAVE, filial_atual

        alocar(ana, matriz.empresa, "vendedor", filial=matriz)
        alocar(ana, loja.empresa, "vendedor", filial=loja)
        pedido = _pedido(ana, {CHAVE: str(loja.pk)})

        assert filial_atual(pedido) == loja

    def test_filial_perdida_e_descartada_e_cai_numa_valida(self, ana, matriz, loja):
        """A pessoa escolheu `loja`, depois perdeu o acesso a ela (só
        `matriz` sobrou). A leitura seguinte não pode ser 500, nem devolver
        `loja` — tem que cair para `matriz`, a única que ainda vale."""
        from plataforma.contexto import CHAVE, filial_atual

        alocar(ana, matriz.empresa, "vendedor", filial=matriz)
        alocar(ana, loja.empresa, "vendedor", filial=loja)
        pedido = _pedido(ana, {CHAVE: str(loja.pk)})
        assert filial_atual(pedido) == loja  # linha de base: a escolha vale

        ana.alocacoes.filter(filial=loja).delete()  # a alocação na loja sai

        atual = filial_atual(pedido)
        assert atual is not None
        assert atual != loja
        assert atual == matriz

    def test_filial_desativada_na_sessao_tambem_e_descartada(self, ana, matriz, loja):
        from plataforma.contexto import CHAVE, filial_atual

        alocar(ana, matriz.empresa, "vendedor", filial=matriz)
        alocar(ana, loja.empresa, "vendedor", filial=loja)
        pedido = _pedido(ana, {CHAVE: str(loja.pk)})

        loja.ativa = False
        loja.save()

        assert filial_atual(pedido) == matriz

    def test_id_invalido_na_sessao_nao_derruba_a_requisicao(self, ana, matriz):
        """Um valor que nem é id (sessão adulterada, ou dado de uma versão
        antiga) não pode virar 500 — só é descartado, como qualquer outro
        id que não vale mais."""
        from plataforma.contexto import CHAVE, filial_atual

        alocar(ana, matriz.empresa, "vendedor", filial=matriz)
        pedido = _pedido(ana, {CHAVE: "não-é-um-id"})

        assert filial_atual(pedido) == matriz

    def test_ninguem_logado_nao_tem_filial(self):
        from plataforma.contexto import filial_atual

        assert filial_atual(_pedido()) is None


class TestEscolher:
    def test_escolhe_uma_filial_alcancada_e_grava_na_sessao(self, ana, loja):
        from plataforma.contexto import CHAVE, escolher

        alocar(ana, loja.empresa, "vendedor", filial=loja)
        pedido = _pedido(ana)

        escolhida = escolher(pedido, str(loja.pk))

        assert escolhida == loja
        assert pedido.session[CHAVE] == loja.pk

    def test_recusa_filial_que_a_pessoa_nao_alcanca(self, ana, matriz, loja):
        """`matriz` existe e está ativa — só `ana` não tem alocação nela."""
        from plataforma.contexto import CHAVE, escolher

        pedido = _pedido(ana)
        escolhida = escolher(pedido, str(matriz.pk))

        assert escolhida is None
        assert CHAVE not in pedido.session

    def test_recusa_id_que_nao_e_de_filial_nenhuma(self, ana):
        from plataforma.contexto import escolher

        pedido = _pedido(ana)
        assert escolher(pedido, "não-é-um-id") is None

    def test_recusa_filial_desativada(self, ana, loja):
        from plataforma.contexto import escolher

        alocar(ana, loja.empresa, "vendedor", filial=loja)
        loja.ativa = False
        loja.save()
        pedido = _pedido(ana)

        assert escolher(pedido, str(loja.pk)) is None


class TestNiveisDeContexto:
    """O contexto do cabeçalho só existe para quem tem o que escolher.

    Foi para dois níveis (empresa em texto, filial em seletor), depois para
    um (a empresa, escolhível) e em 09/09/2026 para **zero na maior parte das
    sessões**: a conta da maioria tem uma empresa só, e um seletor de uma
    opção é um botão que não faz nada ocupando o lugar em que a pessoa
    procura o que faz.

    Ele volta para quem alcança mais de uma: a MW5, onde a pergunta é "qual
    CONTA estou olhando", e o titular cuja conta tem várias empresas
    (17/09/2026).
    Os testes do arranjo antigo foram reescritos, não removidos: a pergunta é
    a mesma, mudou a resposta certa.
    """

    def test_quem_e_de_uma_conta_nao_tem_o_que_trocar(self, ana, matriz):
        from plataforma.contexto import niveis_de_contexto

        assert niveis_de_contexto(_pedido(ana)) == []

    def test_quem_alcanca_uma_filial_so_tambem_ve_a_filial(self, ana, loja):
        """25/09/2026, pedido do cliente: "não tá mostrando o seletor de filial
        quando é só uma". A filial é o lugar em que a pessoa está — é ela que
        decide o que a pessoa pode —, e sem o seletor o cabeçalho não dizia em
        que loja a sessão estava. A empresa continua escondida com uma só."""
        from plataforma.contexto import niveis_de_contexto

        alocar(ana, loja.empresa, "vendedor", filial=loja)

        niveis = niveis_de_contexto(_pedido(ana))
        assert [n.nivel for n in niveis] == [1]
        assert [o.valor for o in niveis[0].opcoes] == [str(loja.pk)]
        assert niveis[0].atual == str(loja.pk)

    def test_a_MW5_escolhe_entre_as_contas(self, ana):
        from contas.models import Nivel
        from plataforma.contexto import niveis_de_contexto
        from plataforma.models import Empresa

        alfa = Empresa.objects.create(razao_social="Alfa Ltda")
        beta = Empresa.objects.create(razao_social="Beta Ltda")
        ana.nivel = Nivel.MASTER
        ana.save(update_fields=["nivel"])

        contexto = niveis_de_contexto(_pedido(ana))[0]
        valores = {o.valor for o in contexto.opcoes}
        assert {str(alfa.pk), str(beta.pk)} <= valores
        assert contexto.atual in valores
        assert contexto.rotulo == "Conta", (
            "para a MW5 a pergunta não é em que empresa ela está trabalhando "
            "— ela não trabalha dentro de nenhuma")

    def test_o_admin_de_uma_conta_nao_ve_a_empresa_alheia(self, ana):
        """Por ataque: a empresa semeada existe e não é dela.

        Sem seletor não há como escolher a alheia — mas a prova continua
        sendo a mesma, sobre `empresas_de`, porque é ela que o seletor lia e
        é ela que o inquilino lê.
        """
        from contas.models import Nivel
        from plataforma.contexto import empresas_de
        from plataforma.models import Empresa

        alheia = Empresa.objects.first()
        minha = Empresa.objects.create(razao_social="Alfa Ltda")
        ana.nivel = Nivel.TITULAR
        ana.save(update_fields=["nivel"])
        por_na_conta(ana, minha)

        assert list(empresas_de(ana)) == [minha]
        assert alheia not in list(empresas_de(ana))

    def test_pessoa_sem_conta_nao_alcanca_nem_a_semeada(self, ana):
        """Ausência de cadastro é restritiva: sem conta, nenhuma empresa —
        nem a semeada."""
        from plataforma.contexto import empresa_atual, empresas_de

        assert list(empresas_de(ana)) == []
        assert empresa_atual(_pedido(ana)) is None


class TestExigirFilial:
    """`exigir_filial` ainda não está presa a rota nenhuma (não há tela de
    negócio nesta Task para compor com ela) — testada direto, do mesmo jeito
    que `tests/test_guarda.py::TestExigirPermissao` testa `exigir_permissao`
    sem depender de uma URL registrada."""

    def _view_protegida(self):
        from django.http import HttpResponse

        from comum.guardas_de_modulo import exigir_filial

        @exigir_filial
        def tela(request):
            return HttpResponse("conteudo de negocio")

        return tela

    def test_com_filial_a_tela_roda_normalmente(self, ana, loja):
        from contas.backend import BackendDjango

        alocar(ana, loja.empresa, "vendedor", filial=loja)
        pedido = _pedido(ana)
        pedido.usuario = BackendDjango().buscar(str(ana.pk))

        resposta = self._view_protegida()(pedido)

        assert resposta.status_code == 200
        assert resposta.content == b"conteudo de negocio"

    def test_sem_filial_nenhuma_mostra_uma_tela_dizendo_o_que_falta(self, ana):
        from contas.backend import BackendDjango

        pedido = _pedido(ana)
        pedido.usuario = BackendDjango().buscar(str(ana.pk))

        resposta = self._view_protegida()(pedido)

        assert resposta.status_code == 200
        assert b"conteudo de negocio" not in resposta.content
        assert "filial" in resposta.content.decode().lower()
