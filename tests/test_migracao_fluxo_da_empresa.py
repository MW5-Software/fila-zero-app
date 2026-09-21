"""`fila/0007` + `plataforma/0006`: o fluxo da fila sai da empresa sem se perder.

O caso que importa é o de uma instalação que já está no ar, com empresa no
fluxo de espera: depois das duas migrações, a escolha tem de estar na tabela
da fila, e a coluna da empresa tem de ter saído.
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


def test_o_fluxo_escolhido_vai_para_a_tabela_da_fila(migrador):
    velho = migrador.apply_initial_migration([
        ("plataforma", "0005_fluxo_da_fila"), ("fila", "0006_correcao_por_na_fila")])
    Usuario = velho.apps.get_model("contas", "Usuario")
    Empresa = velho.apps.get_model("plataforma", "Empresa")
    titular = Usuario.objects.create(email="dono@teste.com", password="x", nivel=1)
    titular.conta_id = titular.guid
    titular.save()
    em_espera = Empresa.objects.create(razao_social="Espera Ltda", dono=titular,
                                       conta_id=titular.guid,
                                       fluxo_da_fila="espera")
    padrao = Empresa.objects.create(razao_social="Padrao Ltda", dono=titular,
                                    conta_id=titular.guid,
                                    fluxo_da_fila="volta_para_a_fila")

    novo = migrador.apply_tested_migration([
        ("plataforma", "0006_empresa_sem_fluxo_da_fila"),
        ("fila", "0007_fluxo_da_empresa")])
    FluxoDaEmpresa = novo.apps.get_model("fila", "FluxoDaEmpresa")
    assert {(l.empresa_id, l.fluxo, l.conta_id)
            for l in FluxoDaEmpresa._default_manager.all()} == {
        (em_espera.pk, "espera", titular.guid)}
    assert not FluxoDaEmpresa._default_manager.filter(empresa_id=padrao.pk).exists()
    campos = {c.name for c in novo.apps.get_model(
        "plataforma", "Empresa")._meta.get_fields()}
    assert "fluxo_da_fila" not in campos
