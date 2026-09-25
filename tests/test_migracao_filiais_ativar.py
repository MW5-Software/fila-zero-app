"""`contas/0009`: `filiais.ativar` chega a quem já existia (25/09/2026).

A tela de Filiais passou a abrir por `filiais.ativar`. Sem a migração, o
titular e o supervisor que já existiam não a ganhariam — e o cargo criado
pelo titular com `filiais.editar` — esse continua abrindo porque
`contas.backend.traduzir` dá `filiais.ativar` junto com `filiais.editar`.
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


def test_quem_ja_existia_ganha_filiais_ativar(migrador):
    velho = migrador.apply_initial_migration(("contas", "0008_alter_cargo_alcance"))
    Permission = velho.apps.get_model("auth", "Permission")
    ContentType = velho.apps.get_model("contenttypes", "ContentType")
    Permission.objects.filter(codename="filiais_ativar").delete()
    tipo, _ = ContentType.objects.get_or_create(app_label="plataforma", model="modulo")
    editar, _ = Permission.objects.get_or_create(
        codename="filiais_editar", content_type=tipo, defaults={"name": "filiais: editar"})
    Usuario = velho.apps.get_model("contas", "Usuario")
    Cargo = velho.apps.get_model("contas", "Cargo")
    titular = Usuario.objects.create(email="dono@teste.com", password="x", nivel=1)
    membro = Usuario.objects.create(email="ana@teste.com", password="x", nivel=2,
                                    dono=titular)
    supervisor = Cargo.objects.create(conta_id=titular.guid, nome="supervisor",
                                      rotulo="Supervisor", alcance="empresa",
                                      de_fabrica=True)
    do_dono = Cargo.objects.create(conta_id=titular.guid, nome="lojista",
                                   rotulo="Lojista", alcance="empresa")
    do_dono.permissoes.add(editar)
    vendedor = Cargo.objects.create(conta_id=titular.guid, nome="vendedor",
                                    rotulo="Vendedor", alcance="filial",
                                    de_fabrica=True)

    novo = migrador.apply_tested_migration(("contas", "0009_filiais_ativar"))
    Usuario = novo.apps.get_model("contas", "Usuario")
    Cargo = novo.apps.get_model("contas", "Cargo")

    def de(obj, rel):
        return set(getattr(obj, rel).values_list("codename", flat=True))

    assert {"filiais_ativar", "filiais_editar"} <= de(
        Usuario.objects.get(pk=titular.pk), "user_permissions")
    assert not Usuario.objects.get(pk=membro.pk).user_permissions.exists()
    assert "filiais_ativar" in de(Cargo.objects.get(pk=supervisor.pk), "permissoes")
    # O cargo com "editar" não ganha a linha: `traduzir` a dá junto.
    assert "filiais_ativar" not in de(Cargo.objects.get(pk=do_dono.pk), "permissoes")
    assert "filiais_ativar" not in de(Cargo.objects.get(pk=vendedor.pk), "permissoes")
