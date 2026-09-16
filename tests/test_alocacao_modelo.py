"""A alocação: esta pessoa, neste lugar, com este cargo.

O cargo é da ALOCAÇÃO e não da pessoa (spec 2026-09-14, D1). Filial vazia é a
empresa inteira (D8). O titular e a MW5 não são alocados (D3).

Neste plano a alocação só existe e se valida; quem a lê para decidir lugar e
permissão é o plano 2.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from contas.models import Alocacao, Cargo, Nivel, Usuario


@pytest.fixture
def conta(db):
    """Um titular, a empresa dele, uma filial, um membro e o cargo Vendedor."""
    from plataforma.models import Empresa, Filial

    titular = Usuario.objects.create_user(
        email="dono-aloc@teste.com", password="x", nivel=Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    norte = Filial.objects.create(empresa=empresa, nome="Norte",
                                  apelido="Norte")
    ana = Usuario.objects.create_user(
        email="ana-aloc@teste.com", password="x", nivel=Nivel.MEMBRO,
        dono=titular)
    vendedor = Cargo.objects.get(conta=titular, nome="vendedor")
    return titular, empresa, norte, ana, vendedor


def test_aloca_numa_filial(conta):
    titular, empresa, norte, ana, vendedor = conta
    alocacao = Alocacao.objects.create(pessoa=ana, empresa=empresa,
                                       filial=norte, cargo=vendedor)
    assert alocacao.conta_id == titular.guid


def test_aloca_na_empresa_inteira(conta):
    _t, empresa, _n, ana, vendedor = conta
    alocacao = Alocacao.objects.create(pessoa=ana, empresa=empresa,
                                       cargo=vendedor)
    assert alocacao.filial_id is None


def test_empresa_inteira_e_filial_convivem_para_a_mesma_pessoa(conta):
    """É o que dá sentido a "a mais específica ganha" (plano 2)."""
    titular, empresa, norte, ana, vendedor = conta
    gerente = Cargo.objects.get(conta=titular, nome="gerente")
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=gerente)
    Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                            cargo=vendedor)
    assert ana.alocacoes.count() == 2


def test_duas_alocacoes_na_mesma_filial_falham(conta):
    _t, empresa, norte, ana, vendedor = conta
    Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                            cargo=vendedor)
    with pytest.raises(IntegrityError):
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=vendedor)


def test_duas_alocacoes_na_empresa_inteira_falham(conta):
    """**O teste que justifica a segunda restrição.** `NULL` não é igual a
    `NULL` numa unicidade do Postgres: com uma restrição só, esta segunda linha
    entraria."""
    _t, empresa, _n, ana, vendedor = conta
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=vendedor)
    with pytest.raises(IntegrityError):
        Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=vendedor)


def test_cargo_de_outra_conta_e_recusado(conta, db):
    _t, empresa, _n, ana, _v = conta
    outro = Usuario.objects.create_user(
        email="outro-aloc@teste.com", password="x", nivel=Nivel.TITULAR)
    alheio = Cargo.objects.get(conta=outro, nome="vendedor")
    with pytest.raises(ValidationError, match="cargo"):
        Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=alheio)


def test_pessoa_de_outra_conta_e_recusada(conta, db):
    _t, empresa, _n, _a, vendedor = conta
    outro = Usuario.objects.create_user(
        email="outro-dono-aloc@teste.com", password="x", nivel=Nivel.TITULAR)
    estranha = Usuario.objects.create_user(
        email="estranha@teste.com", password="x", nivel=Nivel.MEMBRO,
        dono=outro)
    with pytest.raises(ValidationError, match="pessoa"):
        Alocacao.objects.create(pessoa=estranha, empresa=empresa,
                                cargo=vendedor)


def test_o_titular_nao_e_alocado(conta):
    """D3: o dono alcança tudo por ser dono. Alocá-lo daria a ele um cargo que
    poderia tirar dele mesmo o acesso à própria conta."""
    titular, empresa, _n, _a, vendedor = conta
    with pytest.raises(ValidationError, match="pessoa"):
        Alocacao.objects.create(pessoa=titular, empresa=empresa,
                                cargo=vendedor)


def test_filial_de_outra_empresa_e_recusada(conta):
    from plataforma.models import Empresa, Filial

    titular, empresa, _n, ana, vendedor = conta
    outra = Empresa.objects.create(razao_social="Beta Ltda")
    longe = Filial.objects.create(empresa=outra, nome="Longe", apelido="Longe")
    with pytest.raises(ValidationError, match="filial"):
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=longe,
                                cargo=vendedor)


def test_empresa_sem_titular_nao_recebe_alocacao(conta):
    from plataforma.models import Empresa

    _t, _e, _n, ana, vendedor = conta
    orfa = Empresa.objects.create(razao_social="Sem Dono Ltda")
    with pytest.raises(ValidationError):
        Alocacao.objects.create(pessoa=ana, empresa=orfa, cargo=vendedor)


def test_cargo_com_alocacao_nao_se_apaga(conta):
    """`PROTECT` no banco, e não só uma frase na tela: a tela nunca é a única
    porta."""
    from django.db.models import ProtectedError

    _t, empresa, _n, ana, vendedor = conta
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=vendedor)
    with pytest.raises(ProtectedError):
        vendedor.delete()


def test_trocar_o_titular_com_alocacao_e_recusado(conta):
    """D10: a alocação liga pessoa e cargo de UMA conta. Reatribuir o
    `conta_guid` da empresa em silêncio (o laço `dono_mudou` de
    `Empresa.save`) faria a alocação apontar para a conta nova enquanto
    `pessoa.dono` e `cargo.conta` continuam da conta antiga — uma linha que
    `Alocacao.clean()` recusaria se fosse criada assim. Nada pode mudar."""
    titular, empresa, _n, ana, vendedor = conta
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=vendedor)

    nova = Usuario.objects.create_user(
        email="nova-titular@teste.com", password="x", nivel=Nivel.TITULAR)
    empresa.dono = nova
    with pytest.raises(ValidationError, match="dono"):
        empresa.save(update_fields=["dono"])

    empresa.refresh_from_db()
    alocacao = empresa.alocacoes.get()
    assert empresa.dono_id == titular.pk
    assert empresa.conta_id == titular.guid
    assert alocacao.conta_id == titular.guid


def test_trocar_o_titular_sem_alocacao_continua_funcionando(conta):
    """A recusa é só quando há alocação — empresa vazia continua livre para
    trocar de titular (comportamento de `test_regra_do_inquilino.py`)."""
    titular, empresa, _n, _a, _v = conta

    nova = Usuario.objects.create_user(
        email="nova-titular-2@teste.com", password="x", nivel=Nivel.TITULAR)
    empresa.dono = nova
    empresa.save(update_fields=["dono"])

    empresa.refresh_from_db()
    assert empresa.dono_id == nova.pk
    assert empresa.conta_id == nova.guid
