"""As permissões de módulo passam a existir como linha.

Sem isto, a tela de Perfis não tem o que oferecer: `ModuloSpec.permissoes`
declara `("exemplo.ver", "exemplo.editar")`, mas nada no banco corresponde, e
o admin do cliente não teria como marcar nada.
"""

import pytest

from plataforma.declaracao import ModuloSpec, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    yield
    declaracao._DECLARADOS.clear()
    declaracao._DECLARADOS.update(guardado)


@pytest.fixture
def frete(catalogo_limpo):
    registrar(ModuloSpec(chave="frete", rotulo="Frete", icone="truck",
                         grupo="Consultas", rota="/frete",
                         permissoes=("frete.ver", "frete.editar")))


@pytest.mark.django_db
class TestMaterializar:
    def test_cada_permissao_declarada_vira_uma_linha(self, frete):
        from django.contrib.auth.models import Permission
        from contas.permissoes import materializar

        materializar()
        codenames = set(Permission.objects.values_list("codename", flat=True))
        assert "frete_ver" in codenames
        assert "frete_editar" in codenames

    def test_o_coringa_do_modulo_tambem_nasce(self, frete):
        """`frete.*` é a forma canônica de conceder o módulo inteiro. Se ele
        não existir como linha, a tela de Perfis não consegue oferecê-lo."""
        from django.contrib.auth.models import Permission
        from contas.permissoes import materializar

        materializar()
        assert Permission.objects.filter(codename="frete_*").exists()

    def test_a_permissao_criada_e_traduzida_de_volta(self, frete, db):
        """A prova de que as duas pontas se encontram: o que a tela concede é
        o que `pode()` entende."""
        from django.contrib.auth.models import Permission
        from contas.models import Usuario
        from contas.backend import permissoes_de
        from contas.permissoes import materializar

        materializar()
        ana = Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
        ana.user_permissions.add(Permission.objects.get(codename="frete_ver"))
        assert "frete.ver" in permissoes_de(ana)

    def test_materializar_duas_vezes_nao_duplica(self, frete):
        from contas.permissoes import materializar

        materializar()
        assert materializar() == 0

    def test_o_rotulo_da_permissao_e_legivel(self, frete):
        """O `name` aparece na tela de Perfis. `frete_ver` não é rótulo."""
        from django.contrib.auth.models import Permission
        from contas.permissoes import materializar

        materializar()
        nome = Permission.objects.get(codename="frete_ver").name
        assert "frete" in nome.lower()
        assert nome != "frete_ver"

    def test_permissao_de_modulo_que_saiu_do_codigo_nao_e_apagada(self, frete):
        """Módulo removido do código deixa a permissão para trás. Apagar
        revogaria acesso de gente em vinte instalações numa atualização."""
        from django.contrib.auth.models import Permission
        from contas.permissoes import materializar
        from plataforma import declaracao

        materializar()
        declaracao._DECLARADOS.clear()
        materializar()
        assert Permission.objects.filter(codename="frete_ver").exists()


@pytest.mark.django_db
def test_o_migrate_materializa(frete):
    """Mesmo gancho que semeia os módulos: roda a cada `migrate`, então uma
    instalação existente ganha a permissão do módulo novo sem migração nova."""
    from django.contrib.auth.models import Permission
    from django.core.management import call_command

    call_command("migrate", verbosity=0)
    assert Permission.objects.filter(codename="frete_ver").exists()
