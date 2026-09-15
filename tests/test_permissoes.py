"""O que a pessoa pode, do ponto de vista de quem desenha a tela.

O `contas/` da entrega 2 vai produzir estes objetos a partir da base do
Django. O que se garante aqui é a regra, e ela é independente de onde a
pessoa veio: LDAP, Oracle do cliente ou tabela nossa.
"""

import pytest

from nucleo.permissoes import SENHA_MINIMA, NivelDeContexto, OpcaoDeContexto, User, pode


class TestOQueAPessoaPode:
    def test_ninguem_deslogado_pode_coisa_nenhuma(self):
        assert pode(None, "frete.ver") is False

    def test_permissao_vazia_libera_para_quem_entrou(self):
        assert pode(User(id="1", name="Ana"), "") is True

    def test_permissao_vazia_nao_libera_para_quem_nao_entrou(self):
        assert pode(None, "") is False

    def test_a_permissao_exata_vale(self):
        ana = User(id="1", name="Ana", permissions={"frete.ver"})
        assert pode(ana, "frete.ver") is True

    def test_permissao_de_outro_modulo_nao_vale(self):
        ana = User(id="1", name="Ana", permissions={"frete.ver"})
        assert pode(ana, "vendas.ver") is False

    def test_o_coringa_do_modulo_cobre_a_acao(self):
        gestor = User(id="2", name="Bruno", permissions={"frete.*"})
        assert pode(gestor, "frete.editar") is True

    def test_o_coringa_cobre_a_acao_criada_amanha(self):
        """A razão de o coringa existir: `frete.exportar` ainda não foi escrita
        em perfil nenhum, e quem tem o módulo inteiro já a tem."""
        gestor = User(id="2", name="Bruno", permissions={"frete.*"})
        assert pode(gestor, "frete.exportar") is True

    def test_quem_marcou_acao_por_acao_nao_ganha_a_acao_nova(self):
        apertado = User(
            id="3", name="Célia",
            permissions={"frete.ver", "frete.editar", "frete.remover"},
        )
        assert pode(apertado, "frete.exportar") is False

    def test_superusuario_passa_em_tudo(self):
        raiz = User(id="4", name="MW5", superuser=True)
        assert pode(raiz, "qualquer.coisa") is True


class TestOUsuario:
    def test_as_permissoes_congelam_na_construcao(self):
        ana = User(id="1", name="Ana", permissions=["frete.ver"])
        assert isinstance(ana.permissions, frozenset)
        with pytest.raises(AttributeError):
            ana.permissions.add("frete.editar")

    def test_o_primeiro_nome_sai_do_nome_inteiro(self):
        assert User(id="1", name="Ana Paula Souza").first_name == "Ana"

    def test_nome_em_branco_nao_derruba_o_primeiro_nome(self):
        assert User(id="1", name="   ").first_name == ""


class TestContexto:
    def test_um_nivel_carrega_as_opcoes_e_a_atual(self):
        nivel = NivelDeContexto(
            nivel=2, rotulo="Filial", atual="3",
            opcoes=[OpcaoDeContexto("3", "Campinas"),
                    OpcaoDeContexto("7", "Ribeirão Preto")],
        )
        assert nivel.atual == "3"
        assert [o.rotulo for o in nivel.opcoes] == ["Campinas", "Ribeirão Preto"]


def test_a_senha_minima_e_de_oito():
    assert SENHA_MINIMA == 8
