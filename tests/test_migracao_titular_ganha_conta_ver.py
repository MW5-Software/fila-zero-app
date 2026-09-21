"""`contas/0007`: o titular que já existe ganha `conta.ver` — de verdade.

A `0006` pulava quando não achava a permissão, e numa instalação que já estava
no ar ela não existia: `conta_ver` é de um módulo novo (a tela de Conta), e só
nasce no `post_migrate`, DEPOIS das migrações. O `post_migrate` cria a linha,
mas não a dá a ninguém, e nenhum titular que já existia ganhava a tela. A
`0006` fica como está (já rodou onde rodou), e a `0007` cria a linha que falta
e dá a permissão (auditoria de 21/09/2026, achado ao levar a tela ao Portal).
"""

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def migrador(transactional_db):
    """Só banco de teste, e o esquema volta ao HEAD no fim."""
    from django.db import connection
    from django_test_migrations.migrator import Migrator

    assert connection.settings_dict["NAME"].startswith("test_")
    migrator = Migrator()
    try:
        yield migrator
    finally:
        migrator.reset()


def test_o_titular_que_ja_existia_ganha_conta_ver_mesmo_sem_a_permissao(migrador):
    velho = migrador.apply_initial_migration(("contas", "0006_titular_ganha_conta_ver"))
    Permission = velho.apps.get_model("auth", "Permission")
    Permission.objects.filter(codename="conta_ver").delete()
    Usuario = velho.apps.get_model("contas", "Usuario")
    titular = Usuario.objects.create(email="dono@teste.com", password="x", nivel=1)
    membro = Usuario.objects.create(email="ana@teste.com", password="x", nivel=2,
                                    dono=titular)

    novo = migrador.apply_tested_migration(("contas", "0007_titular_ganha_conta_ver_de_verdade"))
    Usuario = novo.apps.get_model("contas", "Usuario")
    tem = set(Usuario.objects.get(pk=titular.pk).user_permissions
              .values_list("codename", flat=True))
    assert "conta_ver" in tem
    assert not Usuario.objects.get(pk=membro.pk).user_permissions.exists()


def test_a_permissao_criada_e_a_mesma_que_o_materializar_reconhece(migrador):
    """Mesmo `codename` e mesmo tipo (`plataforma.modulo`): senão o
    `post_migrate` criaria uma segunda, e o titular teria a que ninguém lê."""
    velho = migrador.apply_initial_migration(("contas", "0006_titular_ganha_conta_ver"))
    velho.apps.get_model("auth", "Permission").objects.filter(
        codename="conta_ver").delete()

    novo = migrador.apply_tested_migration(("contas", "0007_titular_ganha_conta_ver_de_verdade"))
    Permission = novo.apps.get_model("auth", "Permission")
    criada = Permission.objects.get(codename="conta_ver")
    assert (criada.content_type.app_label, criada.content_type.model) == (
        "plataforma", "modulo")
