"""`Usuario.conta`: a conta da pessoa pelo GUID, na coluna `conta_guid`.

Toda tabela de negócio carrega `conta_guid` desde 14/09/2026; o usuário ficou
de fora e só apontava para a conta por `dono` (o id do titular). A coluna é a
mesma convenção das outras: o GUID do titular. Três regras, decididas com o
João:

- convive com `dono`, como `Empresa.conta` convive com `Empresa.dono`, e é
  DERIVADA dele a cada gravação — não se grava `conta` à mão;
- o titular aponta para o PRÓPRIO GUID: toda linha da conta, inclusive ele,
  tem o mesmo `conta_guid`, e um filtro pela coluna traz a conta inteira;
- a MW5 (MASTER e superusuário) não é de conta nenhuma: nula.
"""

import pytest

from contas.models import Nivel, Usuario

pytestmark = pytest.mark.django_db


def _titular(login="dono"):
    return Usuario.objects.create_user(
        email=f"{login}@teste.com", password="x", nivel=Nivel.TITULAR)


def test_a_coluna_se_chama_conta_guid_e_aponta_para_o_guid():
    campo = Usuario._meta.get_field("conta")
    assert campo.column == "conta_guid"
    assert campo.target_field.name == "guid"


def test_o_titular_e_a_propria_conta():
    titular = _titular()
    titular.refresh_from_db()
    assert titular.conta_id == titular.guid


def test_o_membro_leva_o_guid_do_titular():
    titular = _titular()
    ana = Usuario.objects.create_user(email="ana@teste.com", password="x",
                                      nivel=Nivel.MEMBRO, dono=titular)
    ana.refresh_from_db()
    assert ana.conta_id == titular.guid


def test_trocar_o_dono_com_update_fields_leva_a_conta_junto():
    """O caminho que as telas usam (`save(update_fields=["dono"])`). Sem
    acrescentar `conta` aos campos gravados, o objeto mudaria em memória e o
    banco ficaria com a conta antiga."""
    alfa, beta = _titular("alfa"), _titular("beta")
    ana = Usuario.objects.create_user(email="ana@teste.com", password="x",
                                      nivel=Nivel.MEMBRO, dono=alfa)
    ana.dono = beta
    ana.save(update_fields=["dono"])

    assert Usuario.objects.get(pk=ana.pk).conta_id == beta.guid


def test_promover_a_titular_pelo_nivel_vira_a_propria_conta():
    alfa = _titular("alfa")
    ana = Usuario.objects.create_user(email="ana@teste.com", password="x",
                                      nivel=Nivel.MEMBRO, dono=alfa)
    ana.nivel = Nivel.TITULAR
    ana.dono = None
    ana.save(update_fields=["nivel", "dono"])

    assert Usuario.objects.get(pk=ana.pk).conta_id == ana.guid


def test_membro_sem_dono_nao_tem_conta():
    solto = Usuario.objects.create_user(email="solto@teste.com", password="x")
    assert Usuario.objects.get(pk=solto.pk).conta_id is None


def test_a_mw5_nao_e_de_conta_nenhuma():
    master = Usuario.objects.create_user(email="mw5@teste.com", password="x",
                                         nivel=Nivel.MASTER)
    raiz = Usuario.objects.create_superuser(email="raiz@teste.com", password="x")
    assert Usuario.objects.get(pk=master.pk).conta_id is None
    assert Usuario.objects.get(pk=raiz.pk).conta_id is None


def test_a_conta_inteira_sai_por_um_filtro_so():
    titular = _titular()
    ana = Usuario.objects.create_user(email="ana@teste.com", password="x",
                                      nivel=Nivel.MEMBRO, dono=titular)
    _titular("outro")

    assert set(Usuario.objects.filter(conta=titular.guid)) == {titular, ana}


def test_o_titular_sem_equipe_ainda_se_remove():
    """Apontar para si mesmo não pode trancar a remoção: com `PROTECT`, o
    titular protegeria a própria linha e nunca sairia."""
    titular = _titular()
    titular.delete()
    assert not Usuario.objects.filter(email="dono@teste.com").exists()
