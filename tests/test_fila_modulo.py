"""O módulo da fila existe, nasce ligado e dá a cada cargo o que o spec diz.

A tabela de cargos do spec (2026-09-15, "Permissões e cargos") é a fonte. Um
cargo de fábrica sem `fila.participar` é uma instalação em que nenhum vendedor
consegue bater o ponto no primeiro dia, e ninguém percebe até a loja abrir.
"""

import pytest

from tests.conftest import abrir_conta, empresa_do_teste

PERMISSOES_DA_FILA = ("fila.ver", "fila.participar", "fila.gerenciar",
                      "fila.cadastros", "fila.relatorios", "fila.metas")


def test_o_modulo_esta_declarado_com_as_quatro_permissoes():
    from plataforma.declaracao import declarados

    spec = next(s for s in declarados() if s.chave == "fila")
    # `fila.ver` primeiro: é a permissão que põe o módulo no menu (D-1).
    assert spec.permissoes == PERMISSOES_DA_FILA
    assert spec.rota == "/fila"
    assert spec.ativo_por_padrao is True
    assert {a.rota for a in spec.atalhos} == {
        "/fila/grupos", "/fila/motivos", "/fila/pausas", "/fila/metas",
        "/fila/historico"}
    # Os indicadores moram no Início (15/09/2026): não há atalho para eles.
    assert {a.permissao for a in spec.atalhos} == {"fila.cadastros", "fila.metas",
                                                   "fila.gerenciar"}


@pytest.mark.django_db
def test_o_menu_da_fila_como_o_cliente_pediu():
    """23/09/2026, pedido do cliente: "Metas vai ser um Menu de Nível 1, em vez
    de Fila da Vez muda para Configuração/Fila e em vez do menu chamar Vendas
    vai chamar Gerenciar Fila".

    **O teste olha o menu MONTADO**, e não as declarações: ninguém escreve o
    menu à mão — ele nasce do `ModuloSpec` e dos atalhos (`plataforma.menu`) —,
    e o que o cliente vê na barra é o resultado do cruzamento.
    """
    from nucleo.permissoes import User
    from plataforma.catalogo import semear
    from plataforma.menu import montar

    semear()
    grupos = {g.label: g for g in
              montar(User(id=1, name="MW5", login="mw5", superuser=True,
                          permissions=["*"]))}

    # O grupo "Vendas" virou "Gerenciar Fila", e "Cadastro" virou
    # "Configuração" — nenhum dos dois nomes antigos fica na barra.
    assert "Vendas" not in grupos and "Cadastro" not in grupos

    da_fila = grupos["Gerenciar Fila"]
    # **Metas de PRIMEIRO nível**, ao lado da página e do histórico: ela não é
    # filha de ninguém.
    assert [(i.label, i.href) for i in da_fila.children] == [
        ("Fila da vez", "/fila"),
        ("Histórico da fila", "/fila/historico"),
        ("Metas", "/fila/metas"),
    ]
    assert all(not i.children for i in da_fila.children), "Metas tem pai"

    # O cadastro da fila em "Configuração > Fila", e não num segundo "Fila da
    # vez" dentro do grupo dos cadastros.
    configuracao = grupos["Configuração"]
    pai = next(i for i in configuracao.children if i.label == "Fila")
    assert [f.label for f in pai.children] == [
        "Grupos de item", "Motivos de não venda", "Tipos de pausa"]
    assert not any(i.label == "Fila da vez" for i in configuracao.children)


@pytest.mark.django_db
def test_o_modulo_nasce_ligado():
    from plataforma.models import Modulo

    assert Modulo.objects.get(chave="fila").ativo is True


@pytest.mark.django_db
@pytest.mark.parametrize("cargo, esperadas", [
    ("vendedor", {"fila_ver", "fila_participar"}),
    ("gerente", {"fila_ver", "fila_participar", "fila_gerenciar",
                 "fila_relatorios", "fila_metas"}),
    ("supervisor", {"fila_ver", "fila_gerenciar", "fila_relatorios",
                    "fila_metas"}),
    ("representante", set()),
    ("cliente", set()),
])
def test_os_cargos_de_fabrica_trazem_a_fila(cargo, esperadas):
    from contas.models import Cargo

    empresa = empresa_do_teste()
    abrir_conta(empresa, "sylvia")
    empresa.refresh_from_db()
    codenames = set(Cargo.objects.get(conta_id=empresa.conta_id, nome=cargo)
                    .permissoes.values_list("codename", flat=True))
    assert {c for c in codenames if c.startswith("fila_")} == esperadas


def test_o_titular_traz_as_quatro():
    from contas.fabrica import DE_FABRICA
    from contas.models import Nivel

    assert set(PERMISSOES_DA_FILA) <= set(DE_FABRICA[Nivel.TITULAR])
    assert "fila.*" in DE_FABRICA[Nivel.MASTER]


def test_a_marca_e_o_fila_zero():
    from plataforma.marca import MARCA_PADRAO

    assert MARCA_PADRAO.client_name == "Fila Zero"
    assert MARCA_PADRAO.system_name == "Fila Zero"
