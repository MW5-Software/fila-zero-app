"""`fila/0009`: o Supervisor de fábrica que já existe ganha `fila.participar`.

Sem ela, `contas.lugar.pode_dar` recusava ao Supervisor os dois cargos da lista
dele — Vendedor e Gerente trazem `fila.participar` — e o cliente viu:
"supervisor não cadastrou gerente" (25/09/2026). A semeadura só cria cargo que
falta, e por isso a conta que já existe precisa desta migração.
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


def test_so_o_supervisor_de_fabrica_ganha_participar(migrador):
    velho = migrador.apply_initial_migration(("fila", "0008_turnodaloja"))
    Permission = velho.apps.get_model("auth", "Permission")
    Permission.objects.filter(codename="fila_participar").delete()
    Usuario = velho.apps.get_model("contas", "Usuario")
    Cargo = velho.apps.get_model("contas", "Cargo")
    titular = Usuario.objects.create(email="dono@teste.com", password="x", nivel=1)
    fabrica = Cargo.objects.create(conta_id=titular.guid, nome="supervisor",
                                   rotulo="Supervisor", alcance="empresa",
                                   de_fabrica=True)
    do_titular = Cargo.objects.create(conta_id=titular.guid, nome="supervisor-2",
                                      rotulo="Supervisor 2", alcance="empresa")

    novo = migrador.apply_tested_migration(
        ("fila", "0009_supervisor_ganha_participar"))
    Cargo = novo.apps.get_model("contas", "Cargo")
    tem = set(Cargo.objects.get(pk=fabrica.pk).permissoes
              .values_list("codename", flat=True))
    assert "fila_participar" in tem
    assert not Cargo.objects.get(pk=do_titular.pk).permissoes.exists()
    criada = novo.apps.get_model("auth", "Permission").objects.get(
        codename="fila_participar")
    assert (criada.content_type.app_label, criada.content_type.model) == (
        "plataforma", "modulo")
