"""`plataforma.filiais.pode_desativar` e `pode_remover`, isolados da tela —
mesmo molde de `contas.cargos.pode_remover`: a frase mora num lugar só.
"""

import pytest
from contas.models import Usuario
from tests.conftest import matriz_do_teste

pytestmark = pytest.mark.django_db


@pytest.fixture
def matriz():
    from plataforma.models import Filial

    return matriz_do_teste()


@pytest.fixture
def loja(matriz):
    from plataforma.models import Filial

    # Na empresa da Matriz: desde 14/09/2026 a regra da última ativa conta
    # dentro da empresa, e uma loja sem empresa não contaria.
    return Filial.objects.create(empresa=matriz.empresa, nome="Loja 1",
                                 apelido="Loja 1", ordem=1)


class TestPodeDesativar:
    def test_recusa_desativar_a_ultima_filial_ativa(self, matriz):
        from plataforma.filiais import pode_desativar

        assert pode_desativar(matriz) == (
            "Esta é a última filial ativa desta empresa. Ative outra "
            "antes de desativar ou remover esta."
        )

    def test_libera_desativar_quando_ha_outra_ativa(self, matriz, loja):
        from plataforma.filiais import pode_desativar

        assert pode_desativar(matriz) is None
        assert pode_desativar(loja) is None

    def test_filial_ja_inativa_nao_precisa_de_recusa(self, matriz, loja):
        """Já está desativada — não há o que recusar de novo."""
        from plataforma.filiais import pode_desativar

        loja.ativa = False
        loja.save()

        assert pode_desativar(loja) is None


class TestPodeRemover:
    def test_recusa_com_gente_alocada(self, matriz, loja):
        """A alocação aponta para a filial com `PROTECT`: sem a frase, remover
        daria erro 500. Era a contagem de `Filial.usuarios`, que saiu com a
        virada dos cargos (14/09/2026)."""
        from plataforma.filiais import pode_remover
        from tests.conftest import alocar

        alocar(Usuario.objects.create_user(email="zeca@teste.com", password="x"),
               loja.empresa, "vendedor", filial=loja)

        assert pode_remover(loja) == (
            "Esta filial tem pessoas alocadas e não pode ser removida. "
            "Remova as alocações antes.")

    def test_recusa_remover_a_ultima_ativa_mesmo_vazia(self, matriz, loja):
        """A loja, e não a Matriz: a Matriz não se remove em caso nenhum desde
        14/09/2026, e a recusa viria por esse motivo."""
        from plataforma.filiais import pode_remover

        matriz.ativa = False
        matriz.save(update_fields=["ativa"])
        assert pode_remover(loja) == (
            "Esta é a última filial ativa desta empresa. Ative outra "
            "antes de desativar ou remover esta."
        )

    def test_libera_remover_filial_vazia_com_outra_ativa_de_pe(self, matriz, loja):
        from plataforma.filiais import pode_remover

        assert pode_remover(loja) is None


class TestModuloRecusaDesativar:
    """A base pergunta aos módulos pelo sinal `antes_de_desativar`, porque não
    pode importá-los (no Fila Zero, a loja com gente presente)."""

    def test_a_frase_do_modulo_recusa(self, matriz, loja):
        from plataforma.filiais import antes_de_desativar, pode_desativar

        def recusa(sender, filial, **kwargs):
            return "Tem gente aqui." if filial.pk == loja.pk else None

        antes_de_desativar.connect(recusa, dispatch_uid="teste_recusa")
        try:
            assert pode_desativar(loja) == "Tem gente aqui."
            assert pode_desativar(matriz) is None
        finally:
            antes_de_desativar.disconnect(dispatch_uid="teste_recusa")
        assert pode_desativar(loja) is None
