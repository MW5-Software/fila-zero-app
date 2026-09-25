"""Toda conta nasce com Supervisor, Gerente, Vendedor, Representante e Cliente.

Os valores iniciais estão no spec 2026-09-14 ("Os cargos de fábrica e o que eles
trazem"), e todos são editáveis pelo titular depois. A semeadura só CRIA o que
falta: rodar de novo não pode desfazer o ajuste que o titular fez.
"""

import pytest

from contas.cargos_de_fabrica import (DE_FABRICA, garantir_cargos_de_fabrica,
                                      semear_cargos)
from contas.models import Alcance, Cargo, Nivel, Usuario


def _permissoes(cargo):
    return set(cargo.permissoes.values_list("codename", flat=True))


@pytest.fixture
def titular(db):
    return Usuario.objects.create_user(
        email="dono-fabrica@teste.com", password="x", nivel=Nivel.TITULAR)


def test_a_lista_de_fabrica_e_a_do_spec():
    assert [(nome, alcance, cliente) for nome, _r, alcance, cliente, _p
            in DE_FABRICA] == [
        ("supervisor", "empresa", False),
        ("gerente", "filial", False),
        ("vendedor", "filial", False),
        ("representante", "filial", False),
        ("cliente", "proprios", True),
    ]


def test_o_titular_novo_nasce_com_os_cinco(titular):
    """O `post_save` semeia. Titular nasce por mais de um caminho (a tela de
    usuários, o shell, um teste), e cada caminho que lembrasse de semear seria
    um caminho que um dia esquece."""
    nomes = set(Cargo.objects.filter(conta=titular)
                .values_list("nome", flat=True))
    assert nomes == {"supervisor", "gerente", "vendedor", "representante",
                     "cliente"}
    assert all(c.de_fabrica for c in Cargo.objects.filter(conta=titular))


def test_as_permissoes_iniciais(titular):
    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}
    # A base traz `usuarios.editar` para Supervisor e Gerente; o Fila Zero
    # acrescenta a fila (spec 2026-09-15): o supervisor corrige, o gerente
    # atende e corrige, o vendedor atende. O representante não está na loja.
    # O supervisor traz `fila_participar` desde 25/09/2026 só para poder
    # conceder Vendedor e Gerente (`contas.lugar.pode_dar`); ele não atende.
    assert _permissoes(cargos["supervisor"]) == {
        "usuarios_editar", "fila_ver", "fila_participar", "fila_gerenciar",
        "fila_relatorios", "fila_metas"}
    assert _permissoes(cargos["gerente"]) == {
        "usuarios_editar", "fila_ver", "fila_participar", "fila_gerenciar",
        "fila_relatorios", "fila_metas"}
    assert _permissoes(cargos["vendedor"]) == {"fila_ver", "fila_participar"}
    assert _permissoes(cargos["representante"]) == set()
    assert _permissoes(cargos["cliente"]) == set()
    assert cargos["cliente"].e_cliente is True
    assert cargos["supervisor"].alcance == Alcance.EMPRESA
    assert cargos["gerente"].alcance == Alcance.FILIAL
    assert cargos["vendedor"].alcance == Alcance.FILIAL
    assert cargos["representante"].alcance == Alcance.FILIAL


def test_quem_nao_e_titular_nao_ganha_cargos(db):
    """Cargo é da CONTA, e conta é o titular. Pessoa da conta não tem cargos
    próprios, e a MW5 não é conta de ninguém."""
    membro = Usuario.objects.create_user(
        email="membro-fabrica@teste.com", password="x", nivel=Nivel.MEMBRO)
    mw5 = Usuario.objects.create_user(
        email="mw5-fabrica@teste.com", password="x", nivel=Nivel.MASTER)
    assert not Cargo.objects.filter(conta__in=[membro, mw5]).exists()


def test_semear_de_novo_nao_duplica(titular):
    assert semear_cargos(titular) == 0
    assert Cargo.objects.filter(conta=titular).count() == 5


def test_semear_de_novo_nao_desfaz_o_ajuste_do_titular(titular):
    vendedor = Cargo.objects.get(conta=titular, nome="vendedor")
    vendedor.permissoes.clear()
    vendedor.alcance = Alcance.PROPRIOS
    vendedor.save()

    semear_cargos(titular)

    vendedor.refresh_from_db()
    assert vendedor.alcance == Alcance.PROPRIOS
    assert _permissoes(vendedor) == set()


def test_promover_a_titular_semeia(db):
    """`dar_acesso` e a tela de usuários promovem com `save(update_fields=...)`.
    O receptor precisa pegar esse caminho, e não só o `create`."""
    pessoa = Usuario.objects.create_user(
        email="promovida@teste.com", password="x", nivel=Nivel.MEMBRO)
    pessoa.nivel = Nivel.TITULAR
    pessoa.save(update_fields=["nivel"])
    assert Cargo.objects.filter(conta=pessoa).count() == 5


def test_o_update_last_login_nao_semeia(titular):
    """`update_last_login` (django.contrib.auth) grava com
    `save(update_fields=["last_login"])` A CADA LOGIN — sem pular este caso,
    todo login do titular faria uma consulta de semeadura que nunca acha
    nada para criar. `update_fields` sem `"nivel"` é o sinal de que a
    semeadura não tem o que fazer aqui: só uma PROMOÇÃO (`nivel` mudando)
    cria cargo novo."""
    Cargo.objects.filter(conta=titular).delete()

    titular.save(update_fields=["last_login"])

    assert Cargo.objects.filter(conta=titular).count() == 0


def test_garantir_cobre_titular_que_ja_existia(titular):
    """O `post_migrate` da instalação que atualiza: titulares que nasceram antes
    desta mudança ganham os cargos na primeira `migrate`."""
    Cargo.objects.filter(conta=titular).delete()
    assert garantir_cargos_de_fabrica() == 5
    assert Cargo.objects.filter(conta=titular).count() == 5


@pytest.mark.django_db(transaction=True)
def test_o_migrate_de_verdade_semeia_o_titular_que_ja_existia():
    """`test_garantir_cobre_titular_que_ja_existia` chama
    `garantir_cargos_de_fabrica()` direto, com `apps=None` — o ramo que usa o
    registro de apps REAL. Toda instalação existente passa pelo OUTRO ramo: o
    `post_migrate` de um `manage.py migrate` de verdade, que entrega ao
    receptor (`plataforma.apps._semear_apos_migrar`) o `apps` HISTÓRICO que o
    próprio `migrate` monta (`StateApps`, não `django.apps.apps`). Sem este
    teste, uma migração futura que quebrasse esse caminho (um `apps.get_model`
    que só existe no registro real, por exemplo) só apareceria na primeira
    atualização de uma instalação de cliente."""
    import django.core.management

    titular = Usuario.objects.create_user(
        email="dono-fabrica-migrate@teste.com", password="x",
        nivel=Nivel.TITULAR)
    Cargo.objects.filter(conta=titular).delete()
    assert Cargo.objects.filter(conta=titular).count() == 0

    django.core.management.call_command("migrate", verbosity=0)

    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}
    assert set(cargos) == {"supervisor", "gerente", "vendedor",
                           "representante", "cliente"}
    assert _permissoes(cargos["gerente"]) == {
        "usuarios_editar", "fila_ver", "fila_participar", "fila_gerenciar",
        "fila_relatorios", "fila_metas"}


def test_quem_cada_cargo_de_fabrica_pode_conceder(titular):
    """17/09/2026: o gerente cria vendedor; o supervisor é o gerente com
    alcance maior, e cria vendedor e gerente."""
    from contas.models import Cargo

    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}
    concede = {nome: sorted(c.pode_conceder.values_list("nome", flat=True))
               for nome, c in cargos.items()}
    assert concede["gerente"] == ["vendedor"]
    assert concede["supervisor"] == ["gerente", "vendedor"]
    assert concede["vendedor"] == [] and concede["cliente"] == []


def test_a_conta_que_ja_existia_ganha_a_lista_na_semeadura(titular):
    """Quem já tinha os cargos de fábrica recebe a lista na próxima
    `migrate` — é o caso do cliente de hoje, que não teria ganhado nada se a
    lista só valesse para conta nova. O que o titular apagou de propósito
    (lista vazia marcada à mão) não volta: só preenche quem está vazio E é
    de fábrica com lista declarada."""
    from contas.cargos_de_fabrica import garantir_cargos_de_fabrica
    from contas.models import Cargo

    gerente = Cargo.objects.get(conta=titular, nome="gerente")
    gerente.pode_conceder.clear()
    garantir_cargos_de_fabrica()
    gerente.refresh_from_db()
    assert list(gerente.pode_conceder.values_list("nome", flat=True)) == ["vendedor"]
