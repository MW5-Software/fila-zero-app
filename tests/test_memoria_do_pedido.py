"""A memória de pedido (`comum.memoria`), e a invariante que ela não pode
quebrar.

Uma página do catálogo fazia 73 consultas e 23 delas eram a mesma linha de
usuário: toda guarda, todo menu e todo `do_contexto` reconstruíam a
identidade do zero. Memorizar por requisição resolve — e foi DESFEITO uma
vez, porque a casa tem uma regra que um memo ingênuo derruba: *o banco decide
a cada requisição, nunca o que a sessão gravou no passado*
(`comum.sessao.usuario_da_sessao`).

A regra vale entre requisições, e um memo por requisição a respeita. O buraco
é a requisição que MUDA a resposta no meio do caminho — a tela que desativa
alguém, a que rebaixa o titular, a que encerra uma personificação —, e é por
isso que qualquer escrita avança a geração e joga o memo fora.

Estes testes são dessa metade: os de desempenho provam que o memo existe, os
de invalidação provam que ele não sobrevive a uma escrita. Sem os segundos, o
primeiro seria só uma otimização com uma porta atrás.
"""

import pytest
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from comum.memoria import esquecer, geracao, lembrar
from comum.sessao import CHAVE, usuario_da_sessao
from contas.models import Nivel, Usuario
from plataforma.models import Empresa
from tests.conftest import por_na_conta

SENHA = "segredo-de-teste"


@pytest.fixture
def pedido(db):
    """Uma requisição com sessão de verdade, como a que chega numa tela."""
    pessoa = Usuario.objects.create_user(
        email="quem@teste.com", password=SENHA, nivel=Nivel.TITULAR)
    Empresa.objects.create(razao_social="Normadin", dono=pessoa)
    request = RequestFactory().get("/")
    request.session = {CHAVE: pessoa.pk}
    return request, pessoa


class TestOMemoExiste:
    def test_calcula_uma_vez_por_pedido(self):
        chamadas = []
        request = RequestFactory().get("/")
        for _ in range(3):
            lembrar(request, "x", lambda: chamadas.append(1))
        assert len(chamadas) == 1

    def test_none_e_resposta_e_nao_ausencia(self):
        """`None` é resposta legítima — "esta pessoa não existe mais". Se o
        memo tratasse `None` como "ainda não calculei", ele repetiria a
        consulta justamente no caso que mais se repete."""
        chamadas = []
        request = RequestFactory().get("/")
        for _ in range(3):
            assert lembrar(request, "x", lambda: chamadas.append(1)) is None
        assert len(chamadas) == 1

    def test_dois_pedidos_nao_se_enxergam(self):
        um, outro = RequestFactory().get("/"), RequestFactory().get("/")
        assert lembrar(um, "x", lambda: "do um") == "do um"
        assert lembrar(outro, "x", lambda: "do outro") == "do outro"

    def test_sem_pedido_calcula_sempre(self):
        """Comando de linha, cron, função chamada direta: não há requisição
        de que lembrar, e o memo não pode inventar uma."""
        chamadas = []
        for _ in range(3):
            lembrar(None, "x", lambda: chamadas.append(1))
        assert len(chamadas) == 3

    def test_objeto_que_nao_aceita_atributo_nao_quebra(self):
        class Travado:
            __slots__ = ()

        chamadas = []
        for _ in range(2):
            lembrar(Travado(), "x", lambda: chamadas.append(1))
        assert len(chamadas) == 2

    @pytest.mark.django_db
    def test_a_identidade_nao_e_relida_a_cada_pergunta(self, pedido):
        request, _ = pedido
        usuario_da_sessao(request)
        with CaptureQueriesContext(connection) as cap:
            for _ in range(5):
                usuario_da_sessao(request)
        assert len(cap.captured_queries) == 0, (
            "a identidade voltou a ser relida por pergunta: "
            f"{len(cap.captured_queries)} consultas em 5 chamadas")


@pytest.mark.django_db
class TestAEscritaJogaOMemoFora:
    """A metade que faz o memo ser seguro."""

    def test_qualquer_escrita_avanca_a_geracao(self, pedido):
        _, pessoa = pedido
        antes = geracao()
        pessoa.save(update_fields=["nome"])
        assert geracao() != antes

    def test_a_escrita_de_outra_tabela_tambem(self, pedido):
        """Sem lista de tabelas de propósito — ver o docstring do módulo."""
        antes = geracao()
        Empresa.objects.create(razao_social="Outra Ltda")
        assert geracao() != antes

    def test_o_m2m_tambem(self, pedido):
        _, pessoa = pedido
        antes = geracao()
        pessoa.user_permissions.add(
            Permission.objects.get(codename="auditoria_ver"))
        assert geracao() != antes

    def test_desativar_no_meio_do_pedido_vale_na_hora(self, pedido):
        """O caso concreto que derrubou a primeira tentativa.

        A tela de usuários desativa alguém e SEGUE renderizando. Com um memo
        que não escuta escrita, o resto daquela requisição continuaria
        respondendo com o retrato de antes do POST — inclusive as guardas.
        """
        request, pessoa = pedido
        assert usuario_da_sessao(request) is not None

        pessoa.is_active = False
        pessoa.save(update_fields=["is_active"])

        assert usuario_da_sessao(request) is None, (
            "a requisição seguiu servindo a identidade de antes da escrita")

    def test_a_permissao_nova_vale_no_mesmo_pedido(self, pedido):
        request, pessoa = pedido
        antes = usuario_da_sessao(request)
        assert "auditoria.ver" not in (antes.permissions or set())

        pessoa.user_permissions.add(
            Permission.objects.get(codename="auditoria_ver"))

        depois = usuario_da_sessao(request)
        assert "auditoria.ver" in depois.permissions

    def test_a_empresa_do_contexto_tambem_e_relida(self, pedido):
        """`empresa_atual` é memorizada pelo mesmo mecanismo, e o inquilino
        inteiro pende dela: memo velho aqui é dado de outra empresa na tela.
        """
        from plataforma.contexto import empresa_atual

        request, pessoa = pedido
        assert empresa_atual(request).razao_social == "Normadin"

        empresa = Empresa.objects.get(dono=pessoa)
        empresa.razao_social = "Normadin Peças"
        empresa.save(update_fields=["razao_social"])

        assert empresa_atual(request).razao_social == "Normadin Peças"


@pytest.mark.django_db
class TestAPersonificacaoContinuaViva:
    """A invariante que o memo mais ameaça: personificar e voltar a ser eu
    passam por `usuario_da_sessao`, e as duas acontecem em requisições
    diferentes — mas quem as INICIA é um POST que escreve, e é essa escrita
    que precisa levar o memo junto.
    """

    def test_ver_como_e_voltar_valem_na_requisicao_seguinte(self):
        raiz = Usuario.objects.create_superuser(
            email="raiz@teste.com", password=SENHA)
        titular = Usuario.objects.create_user(
            email="dono@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        Empresa.objects.create(razao_social="Normadin", dono=titular)

        cliente = Client()
        cliente.post(reverse("entrar"), {"usuario": "raiz@teste.com",
                                         "senha": SENHA})
        cliente.post(reverse("personificar"), {"id": str(titular.pk)})
        html = cliente.get(reverse("home")).content.decode()
        assert "dono@teste.com" in html

        cliente.post(reverse("voltar_a_ser_eu"))
        html = cliente.get(reverse("home")).content.decode()
        assert "dono@teste.com" not in html


@pytest.mark.django_db
def test_esquecer_e_a_saida_manual(pedido):
    """`esquecer()` existe para quem escreve fora do ORM (SQL cru, `update`
    em massa) poder dizer que a resposta mudou."""
    request, _ = pedido
    lembrar(request, "x", lambda: "velho")
    esquecer()
    assert lembrar(request, "x", lambda: "novo") == "novo"
