"""O usuário interno da MW5, criado pela instalação.

A spec diz que ele nasce com a instalação, não aparece na lista de usuários do
cliente, e o admin dele não consegue apagar nem editar. As duas últimas ainda
não têm tela nem teste — dependem da gestão de usuários de uma tarefa
posterior deste plano; aqui só a semeadura é coberta.
"""

import pytest


@pytest.mark.django_db
class TestOUsuarioMw5:
    def test_nasce_com_a_instalacao(self):
        from contas.models import Usuario
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        assert Usuario.objects.filter(email=EMAIL).exists()

    def test_nasce_superusuario(self):
        """É a fronteira inteira entre a MW5 e o cliente."""
        from contas.models import Usuario
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        assert Usuario.objects.get(email=EMAIL).is_superuser is True

    def test_nasce_sem_senha_utilizavel(self):
        """Senha padrão em vinte instalações seria a mesma senha em vinte
        instalações. A MW5 define a dela na primeira vez."""
        from contas.models import Usuario
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        assert Usuario.objects.get(email=EMAIL).has_usable_password() is False

    def test_garantir_duas_vezes_nao_recria(self):
        """A primeira chamada tem que criar de verdade — sem apagar a linha
        que o `post_migrate` da suíte já semeou antes deste teste rodar, uma
        implementação que nunca cria passaria aqui do mesmo jeito, porque só
        a devolução da *segunda* chamada seria conferida."""
        from contas.models import Usuario
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        Usuario.objects.filter(email=EMAIL).delete()

        assert garantir_usuario_mw5() is True
        assert garantir_usuario_mw5() is False

    def test_garantir_nao_reseta_a_senha_ja_definida(self):
        """A atualização não pode derrubar o acesso da MW5."""
        from contas.models import Usuario
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        u = Usuario.objects.get(email=EMAIL)
        u.set_password("a-que-a-mw5-definiu")
        u.save()

        garantir_usuario_mw5()
        assert Usuario.objects.get(email=EMAIL).check_password("a-que-a-mw5-definiu")

    def test_nasce_master(self):
        """O nível é COLUNA da pessoa desde que o usuário passou a ser nosso,
        e toda coluna tem padrão — o desta é COMPRADOR. Sem dizer o nível
        aqui, a MW5 nasceria comprador, e `catalogo.preco` passaria a
        procurar um preço negociado dela mesma. Antes disto ela simplesmente
        não tinha linha de nível, e "nenhum" era a resposta certa."""
        from contas.models import Nivel, Usuario
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        assert Usuario.objects.get(email=EMAIL).nivel == Nivel.MASTER

    def test_garantir_reativa_se_alguem_desativou(self):
        """Desativar o usuário da MW5 seria a forma de um cliente se trancar
        por dentro. A atualização desfaz."""
        from contas.models import Usuario
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        Usuario.objects.filter(email=EMAIL).update(is_active=False)
        garantir_usuario_mw5()
        assert Usuario.objects.get(email=EMAIL).is_active is True


@pytest.mark.django_db
class TestOUsuarioSemeadoNaInstalacao:
    """Estes dois não chamam `garantir_usuario_mw5()` — o alvo aqui é a linha
    que o `post_migrate` já semeou na construção do banco de teste, a mesma
    que existe em qualquer instalação nova. Chamar a função de novo testaria
    a função, não a semeadura; a classe acima já cobre a função."""

    def test_nao_consegue_entrar_enquanto_a_senha_e_inutilizavel(self):
        from django.test import Client
        from django.urls import reverse
        from contas.mw5 import EMAIL

        c = Client()
        # A chave lida por `entrar` é `usuario`/`senha` — ver
        # `tests/test_tela_aparencia.py`.
        c.post(reverse("entrar"), {"usuario": EMAIL, "senha": "qualquer-coisa"})
        assert c.session.get("usuario_id") is None

    def test_apos_a_mw5_definir_senha_entra_e_abre_tela_soh_dela(self):
        from contas.models import Usuario
        from django.test import Client
        from django.urls import reverse
        from contas.mw5 import EMAIL

        u = Usuario.objects.get(email=EMAIL)
        u.set_password("a-que-a-mw5-definiu")
        u.save()

        c = Client()
        c.post(reverse("entrar"), {"usuario": EMAIL, "senha": "a-que-a-mw5-definiu"})
        assert c.get(reverse("modulos")).status_code == 200
