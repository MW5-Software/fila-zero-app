"""A tela de Filiais: tabela com filtro, ordenação e paginação (R46), ações
de linha em modal, e as três regras que protegem a instalação de ficar sem
filial usável.
"""

import pytest


@pytest.fixture(autouse=True)
def _com_filiais(modulo_filiais_ligado):
    """Este arquivo testa a tela de filiais, e neste produto o módulo nasce
    desligado — ver `tests/conftest.py`."""
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

from tests.conftest import alocar

SENHA = "segredo-de-teste"


@pytest.fixture
def admin_do_cliente(db):
    """O TITULAR de uma empresa, com as permissões de fábrica dele — não um
    superusuário.

    Até 14/09/2026 era um usuário comum sem empresa, com `filiais.editar` dado
    à mão, e a tela listava as filiais da instalação inteira. Desde que ela
    passou a enxergar só a empresa do contexto (`_filiais_da_empresa`), um
    usuário sem empresa não vê filial nenhuma — e o caso real de quem abre
    esta tela é o titular cadastrando as filiais da empresa dele.
    """
    from contas.fabrica import aplicar
    from contas.models import Nivel
    from plataforma.models import Empresa

    pessoa = Usuario.objects.create_user(email="admin@teste.com", password=SENHA,
                                         nivel=Nivel.TITULAR)
    aplicar(pessoa, Nivel.TITULAR)
    Empresa.objects.create(razao_social="Empresa do Admin Ltda", dono=pessoa)
    return pessoa


@pytest.fixture
def cliente_admin(admin_do_cliente):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "admin@teste.com", "senha": SENHA})
    return c


@pytest.fixture
def matriz(admin_do_cliente):
    """A Matriz da empresa do titular — a que a empresa ganha ao nascer."""
    from plataforma.models import Empresa

    return Empresa.objects.get(dono=admin_do_cliente).filiais.get(e_matriz=True)


class TestQuemEntra:
    def test_o_admin_com_a_permissao_abre(self, cliente_admin):
        assert cliente_admin.get(reverse("filiais")).status_code == 200

    def test_usuario_comum_nao_descobre_que_a_tela_existe(self, db):
        Usuario.objects.create_user(email="comum@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "comum@teste.com", "senha": SENHA})
        assert c.get(reverse("filiais")).status_code == 404

    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("filiais"))
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_modulo_desligado_e_404_mesmo_com_a_permissao(self, cliente_admin, db):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="filiais").update(ativo=False)
        assert cliente_admin.get(reverse("filiais")).status_code == 404


class TestALista:
    def test_mostra_a_matriz_semeada(self, cliente_admin, matriz):
        html = cliente_admin.get(reverse("filiais")).content.decode()
        assert "Matriz" in html

    def test_busca_por_filial(self, cliente_admin, matriz):
        from plataforma.models import Filial

        Filial.objects.create(empresa=matriz.empresa, nome="Loja Sorriso", apelido="Sorriso")

        import re

        html = cliente_admin.get(
            reverse("filiais"), {"f:filial:contem": "Sorriso"}).content.decode()
        # Sem o seletor de filial do cabeçalho, que lista todas as filiais que
        # a pessoa alcança de propósito — o que se testa aqui é a TABELA.
        html = re.sub(r'<form class="ctx".*?</form>', "", html, flags=re.S)
        assert "Sorriso" in html
        assert "Matriz" not in html

    def test_filtra_por_situacao(self, cliente_admin, matriz):
        from plataforma.models import Filial

        Filial.objects.create(empresa=matriz.empresa, nome="Loja X", apelido="X", ativa=False)

        html = cliente_admin.get(
            reverse("filiais"), {"f:situacao:igual": "0"}).content.decode()
        assert ">X<" in html
        assert "Matriz" not in html


class TestCriarEditarRemover:
    def test_criar_uma_filial_e_audita(self, cliente_admin, matriz):
        from contas.models import RegistroDeAuditoria
        from plataforma.models import Filial

        cliente_admin.post(reverse("filiais"), {
            "acao": "criar", "nome": "Loja Sorriso", "apelido": "Sorriso",
            "municipio": "Sorriso", "uf": "MT",
        })

        filial = Filial.objects.get(apelido="Sorriso")
        assert filial.municipio == "Sorriso"
        assert RegistroDeAuditoria.objects.filter(acao="filial_criada").exists()

    def test_criar_com_o_parametro_padrao_nasce_ativa(self, cliente_admin, matriz):
        """`nova_filial_nasce_ativa` (`plataforma.parametro`) tem padrão
        verdadeiro — o mesmo comportamento que `Filial.ativa` sempre teve
        antes deste parâmetro existir."""
        from plataforma.models import Filial

        cliente_admin.post(reverse("filiais"), {
            "acao": "criar", "nome": "Loja Sorriso", "apelido": "Sorriso",
        })
        assert Filial.objects.get(apelido="Sorriso").ativa is True

    def test_criar_com_o_parametro_desligado_nasce_inativa(self, cliente_admin, matriz):
        from plataforma.models import Filial
        from plataforma.parametro_catalogo import definir

        definir("nova_filial_nasce_ativa", "0")
        cliente_admin.post(reverse("filiais"), {
            "acao": "criar", "nome": "Loja Sorriso", "apelido": "Sorriso",
        })
        assert Filial.objects.get(apelido="Sorriso").ativa is False

    def test_criar_sem_apelido_e_recusado_com_frase_na_tela(self, cliente_admin, matriz):
        from plataforma.models import Filial

        resposta = cliente_admin.post(
            reverse("filiais"), {"acao": "criar", "nome": "Loja Sorriso"})

        assert not Filial.objects.filter(nome="Loja Sorriso").exists()
        assert "Informe o apelido da filial." in resposta.content.decode()

    def test_editar_troca_os_campos_e_audita(self, cliente_admin, matriz):
        from contas.models import RegistroDeAuditoria

        cliente_admin.post(reverse("filiais"), {
            "acao": "salvar", "filial": str(matriz.pk),
            "nome": "Matriz", "apelido": "Sede", "municipio": "Cuiabá",
        })

        matriz.refresh_from_db()
        assert matriz.apelido == "Sede"
        assert matriz.municipio == "Cuiabá"
        assert RegistroDeAuditoria.objects.filter(acao="filial_editada").exists()

    def test_ativar_e_desativar_com_outra_filial_ativa_de_pe(self, cliente_admin, matriz):
        from contas.models import RegistroDeAuditoria
        from plataforma.models import Filial

        loja = Filial.objects.create(empresa=matriz.empresa, nome="Loja 1", apelido="Loja 1")

        cliente_admin.post(
            reverse("filiais"), {"acao": "desativar", "filial": str(loja.pk)})
        loja.refresh_from_db()
        assert loja.ativa is False
        assert RegistroDeAuditoria.objects.filter(acao="filial_desativada").exists()

        cliente_admin.post(
            reverse("filiais"), {"acao": "ativar", "filial": str(loja.pk)})
        loja.refresh_from_db()
        assert loja.ativa is True
        assert RegistroDeAuditoria.objects.filter(acao="filial_ativada").exists()

    def test_remover_uma_filial_vazia_com_outra_ativa_de_pe(self, cliente_admin, matriz):
        from contas.models import RegistroDeAuditoria
        from plataforma.models import Filial

        loja = Filial.objects.create(empresa=matriz.empresa, nome="Loja 1", apelido="Loja 1")

        cliente_admin.post(
            reverse("filiais"), {"acao": "remover", "filial": str(loja.pk)})

        assert not Filial.objects.filter(pk=loja.pk).exists()
        assert RegistroDeAuditoria.objects.filter(acao="filial_removida").exists()


class TestNaoFicarSemFilialAtivaNenhuma:
    """Regra (a) do brief: a instalação nunca pode ficar sem filial ativa
    nenhuma. Mesma classe de defeito do admin se trancar fora
    (`contas.views_usuarios._e_voce_mesmo`), virada para a instalação
    inteira."""

    def test_recusa_desativar_a_ultima_filial_ativa(self, cliente_admin, matriz):
        from plataforma.models import Filial

        resposta = cliente_admin.post(
            reverse("filiais"), {"acao": "desativar", "filial": str(matriz.pk)})

        matriz.refresh_from_db()
        assert matriz.ativa is True
        assert "última filial ativa" in resposta.content.decode()

    def test_recusa_remover_a_ultima_filial_ativa(self, cliente_admin, matriz):
        """Com a Matriz desativada, a loja é a última ativa da empresa.

        A Matriz não entra aqui como a filial removida: desde 14/09/2026 ela não
        se remove em caso nenhum, e a recusa viria por esse motivo e não por
        ser a última ativa — o teste passaria sem provar esta regra.
        """
        from plataforma.models import Filial

        loja = Filial.objects.create(empresa=matriz.empresa, nome="Loja 1",
                                     apelido="Loja 1")
        cliente_admin.post(
            reverse("filiais"), {"acao": "desativar", "filial": str(matriz.pk)})

        resposta = cliente_admin.post(
            reverse("filiais"), {"acao": "remover", "filial": str(loja.pk)})

        assert Filial.objects.filter(pk=loja.pk).exists()
        assert "última filial ativa" in resposta.content.decode()

    def test_desativar_a_penultima_libera_a_desativacao_da_ultima_de_novo(
            self, cliente_admin, matriz):
        """Com duas filiais ativas, desativar uma é permitido; tentar
        desativar a que sobrou (agora a última) volta a ser recusado."""
        from plataforma.models import Filial

        loja = Filial.objects.create(empresa=matriz.empresa, nome="Loja 1", apelido="Loja 1")
        cliente_admin.post(
            reverse("filiais"), {"acao": "desativar", "filial": str(loja.pk)})

        resposta = cliente_admin.post(
            reverse("filiais"), {"acao": "desativar", "filial": str(matriz.pk)})

        matriz.refresh_from_db()
        assert matriz.ativa is True
        assert "última filial ativa" in resposta.content.decode()


class TestNaoRemoverFilialComGenteDentro:
    """Regra (b) do brief: filial com gente alocada não se remove, e a tela
    diz o motivo em vez de estourar o `PROTECT`."""

    def test_recusa_com_gente_alocada_e_diz_na_tela(self, cliente_admin, matriz):
        from plataforma.models import Filial

        loja = Filial.objects.create(empresa=matriz.empresa, nome="Loja 1", apelido="Loja 1")
        alocar(Usuario.objects.create_user(email="zeca@teste.com", password=SENHA),
               matriz.empresa, "vendedor", filial=loja)

        resposta = cliente_admin.post(
            reverse("filiais"), {"acao": "remover", "filial": str(loja.pk)})

        assert Filial.objects.filter(pk=loja.pk).exists()
        assert "Esta filial tem pessoas alocadas" in resposta.content.decode()


@pytest.mark.django_db
class TestDesativarNaoTrancaQuemEstaUsando:
    """Regra (c) do brief: desativar a filial de alguém que está
    trabalhando nela não pode derrubar a pessoa em 500 — ela cai para outra
    filial que ainda alcança, o mesmo mecanismo que `plataforma.contexto.
    filial_atual` já prova em `tests/test_contexto_filial.py`. Aqui é a
    prova fim a fim, pela tela de verdade."""

    def test_desativar_a_filial_de_alguem_a_deixa_numa_filial_valida(
            self, cliente_admin, matriz):
        from plataforma.contexto import CHAVE as CHAVE_FILIAL
        from plataforma.models import Filial

        loja = Filial.objects.create(empresa=matriz.empresa, nome="Loja 1", apelido="Loja 1")
        zeca = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
        # Representante, e não Vendedor: no Fila Zero quem só tem a fila de
        # vendedor cai em /fila ao pedir a raiz, e esta prova é pela tela do
        # shell. Os dois cargos têm o mesmo alcance de filial.
        alocar(zeca, matriz.empresa, "representante", filial=matriz)
        alocar(zeca, matriz.empresa, "representante", filial=loja)

        sessao_de_zeca = Client()
        sessao_de_zeca.post(reverse("entrar"), {"usuario": "zeca@teste.com", "senha": SENHA})
        sessao_de_zeca.post(reverse("filial_trocar"), {CHAVE_FILIAL: str(loja.pk)})

        cliente_admin.post(
            reverse("filiais"), {"acao": "desativar", "filial": str(loja.pk)})

        # A tela abre (não é 500) …
        resposta = sessao_de_zeca.get(reverse("home"))
        assert resposta.status_code == 200

        # … e o contexto dele caiu para uma filial que ele ainda alcança.
        #
        # A asserção era `"Matriz" in html`, quando o cabeçalho ainda
        # desenhava o seletor de FILIAL. Neste produto ele desenha o de
        # EMPRESA (ver `plataforma/contexto.py`), então o nome da filial não
        # passa mais pelo HTML — o que não muda nada sobre a regra que este
        # teste existe para provar. Ela se lê onde ela mora.
        from plataforma.contexto import filial_atual

        class _Requisicao:
            session = sessao_de_zeca.session

        assert filial_atual(_Requisicao()) == matriz
