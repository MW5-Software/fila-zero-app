"""O cargo: um conjunto de permissões com nome, alcance e marca de cliente.

Substitui o `Perfil` (spec 2026-09-14, D9), que saiu em 14/09/2026: é do cargo
da alocação que vem a permissão de todo membro de uma conta.

Mora no app `contas`, que a varredura do inquilino isenta. Por isso o
isolamento entre contas é provado aqui, e não por ela.
"""

import pytest
from django.contrib.auth.models import Permission
from django.db import IntegrityError

from contas.models import Alcance, Cargo, Nivel, Usuario


@pytest.fixture
def titular(db):
    return Usuario.objects.create_user(
        email="dono-cargo@teste.com", password="x", nivel=Nivel.TITULAR)


def test_o_cargo_guarda_a_conta_pelo_guid(titular):
    """A mesma identidade estável que `conta_guid` usa em toda linha de negócio
    — e não o id sequencial desta instalação."""
    cargo = Cargo.objects.create(conta=titular, nome="faturista",
                                 rotulo="Faturista", alcance=Alcance.FILIAL)
    cargo.refresh_from_db()
    assert cargo.conta_id == titular.guid


def test_o_alcance_padrao_e_o_minimo(titular):
    """Cargo novo sem alcance escolhido enxerga só os próprios registros. É o
    erro seguro: ver de menos se corrige na tela, ver de mais já vazou."""
    cargo = Cargo.objects.create(conta=titular, nome="caixa", rotulo="Caixa")
    assert cargo.alcance == Alcance.PROPRIOS
    assert cargo.e_cliente is False
    assert cargo.de_fabrica is False


def test_o_nome_e_unico_por_conta(titular):
    Cargo.objects.create(conta=titular, nome="faturista", rotulo="Faturista")
    with pytest.raises(IntegrityError):
        Cargo.objects.create(conta=titular, nome="faturista", rotulo="Outro")


def test_duas_contas_podem_ter_o_mesmo_nome(db, titular):
    """"Faturista" de um cliente não pode bater no "Faturista" de outro que ele
    nem conhece — o defeito que o `Perfil` teve até ganhar dono."""
    outro = Usuario.objects.create_user(
        email="outro-dono@teste.com", password="x", nivel=Nivel.TITULAR)
    Cargo.objects.create(conta=titular, nome="faturista", rotulo="Faturista")
    Cargo.objects.create(conta=outro, nome="faturista", rotulo="Faturista")
    assert Cargo.objects.filter(nome="faturista").count() == 2


def test_o_cargo_carrega_permissoes(titular):
    ver = Permission.objects.get(codename="usuarios_editar")
    cargo = Cargo.objects.create(conta=titular, nome="consulta",
                                 rotulo="Consulta")
    cargo.permissoes.add(ver)
    assert list(cargo.permissoes.values_list("codename", flat=True)) == [
        "usuarios_editar"]


def test_os_cargos_de_uma_conta_nao_aparecem_na_outra(db, titular):
    outro = Usuario.objects.create_user(
        email="outro-dono2@teste.com", password="x", nivel=Nivel.TITULAR)
    Cargo.objects.create(conta=titular, nome="so-do-titular", rotulo="X")
    assert not outro.cargos_da_conta.filter(nome="so-do-titular").exists()
    assert titular.cargos_da_conta.filter(nome="so-do-titular").exists()
