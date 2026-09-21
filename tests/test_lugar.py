"""Onde a pessoa está, e o que ela pode ali (spec 2026-09-14, "Onde a pessoa
está"). Funções puras sobre `Alocacao`; quem as liga à requisição é a Task 2.
"""

import pytest

from contas.lugar import (
    alcance_em, alocacao_vigente, empresas_da_pessoa, filiais_da_pessoa,
    permissoes_do_cargo, permissoes_em, pode_administrar, pode_dar,
)
from contas.models import Alcance, Alocacao, Cargo, Nivel, Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def conta():
    """Titular, empresa com Matriz + Norte + Sul, e os cargos de fábrica."""
    from plataforma.models import Empresa, Filial

    from contas.fabrica import aplicar

    titular = Usuario.objects.create_user(
        email="dono-lugar@teste.com", password="x", nivel=Nivel.TITULAR)
    aplicar(titular, Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    norte = Filial.objects.create(empresa=empresa, nome="Norte", apelido="Norte")
    sul = Filial.objects.create(empresa=empresa, nome="Sul", apelido="Sul")
    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}
    return titular, empresa, norte, sul, cargos


def _membro(titular, login):
    return Usuario.objects.create_user(
        email=f"{login}@teste.com", password="x", nivel=Nivel.MEMBRO,
        dono=titular)


class TestOsLugares:
    def test_pessoa_sem_alocacao_nao_alcanca_nada(self, conta):
        titular, empresa, *_ = conta
        ana = _membro(titular, "ana")
        assert list(empresas_da_pessoa(ana)) == []
        assert list(filiais_da_pessoa(ana, empresa)) == []

    def test_alocacao_na_filial_abre_so_ela(self, conta):
        titular, empresa, norte, sul, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert list(empresas_da_pessoa(ana)) == [empresa]
        assert list(filiais_da_pessoa(ana, empresa)) == [norte]

    def test_alocacao_na_empresa_inteira_abre_todas_as_ativas(self, conta):
        from plataforma.models import Filial

        titular, empresa, norte, sul, cargos = conta
        sul.ativa = False
        sul.save()
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa,
                                cargo=cargos["supervisor"])
        nova = Filial.objects.create(empresa=empresa, nome="Leste", apelido="Leste")
        alcancadas = set(filiais_da_pessoa(ana, empresa))
        assert norte in alcancadas and nova in alcancadas
        assert sul not in alcancadas

    def test_titular_alcanca_as_filiais_da_empresa_dele_e_nao_as_de_outra(self, conta):
        from plataforma.models import Empresa

        titular, empresa, norte, *_ = conta
        outro = Usuario.objects.create_user(
            email="outro-lugar@teste.com", password="x", nivel=Nivel.TITULAR)
        beta = Empresa.objects.create(razao_social="Beta Ltda", dono=outro)
        assert norte in set(filiais_da_pessoa(titular, empresa))
        assert list(filiais_da_pessoa(titular, beta)) == []

    def test_pessoa_que_mudou_de_conta_perde_as_alocacoes_antigas(self, conta):
        titular, empresa, norte, _s, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        outro = Usuario.objects.create_user(
            email="outro-conta@teste.com", password="x", nivel=Nivel.TITULAR)
        ana.dono = outro
        ana.save(update_fields=["dono"])
        assert list(empresas_da_pessoa(ana)) == []
        assert alocacao_vigente(ana, empresa, norte) is None


class TestAMaisEspecificaGanha:
    def test_vendedor_na_norte_e_gerente_da_empresa_e_vendedor_na_norte(self, conta):
        titular, empresa, norte, sul, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=cargos["supervisor"])
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert alocacao_vigente(ana, empresa, norte).cargo.nome == "vendedor"
        assert alocacao_vigente(ana, empresa, sul).cargo.nome == "supervisor"
        # As duas não somam: na Norte ela não administra ninguém.
        assert "usuarios.editar" not in permissoes_em(ana, empresa, norte)
        assert "usuarios.editar" in permissoes_em(ana, empresa, sul)

    def test_filial_de_outra_empresa_nao_escolhe_alocacao(self, conta):
        from plataforma.models import Empresa, Filial

        titular, empresa, norte, _s, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=cargos["cliente"])
        outro = Usuario.objects.create_user(
            email="outro-fil@teste.com", password="x", nivel=Nivel.TITULAR)
        beta = Empresa.objects.create(razao_social="Beta Ltda", dono=outro)
        alheia = Filial.objects.create(empresa=beta, nome="X", apelido="X")
        assert alocacao_vigente(ana, empresa, alheia).cargo.nome == "cliente"


class TestAsPermissoes:
    def test_cargo_traduz_para_o_vocabulario_do_nucleo(self, conta):
        *_, cargos = conta
        # O gerente de fábrica do Fila Zero traz também a fila.
        assert permissoes_do_cargo(cargos["gerente"]) == frozenset(
            {"usuarios.editar", "fila.ver", "fila.participar",
             "fila.gerenciar", "fila.relatorios", "fila.metas"})

    def test_membro_sem_alocacao_nao_pode_nada(self, conta):
        titular, empresa, norte, *_ = conta
        assert permissoes_em(_membro(titular, "ana"), empresa, norte) == frozenset()

    def test_titular_tem_as_de_fabrica_so_na_empresa_dele(self, conta):
        from contas.fabrica import aplicar
        from plataforma.models import Empresa

        titular, empresa, norte, *_ = conta
        aplicar(titular, Nivel.TITULAR)
        assert "usuarios.editar" in permissoes_em(titular, empresa, norte)
        outro = Usuario.objects.create_user(
            email="outro-perm@teste.com", password="x", nivel=Nivel.TITULAR)
        beta = Empresa.objects.create(razao_social="Beta Ltda", dono=outro)
        assert permissoes_em(titular, beta, None) == frozenset()

    def test_alcance_do_titular_e_a_empresa_e_do_membro_e_o_do_cargo(self, conta):
        titular, empresa, norte, _s, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert alcance_em(titular, empresa, norte) == Alcance.EMPRESA
        assert alcance_em(ana, empresa, norte) == Alcance.FILIAL
        assert alcance_em(_membro(titular, "bia"), empresa, norte) == Alcance.PROPRIOS


class TestEscalada:
    def _gerente_na_norte(self, conta):
        titular, empresa, norte, _s, cargos = conta
        gil = _membro(titular, "gil")
        Alocacao.objects.create(pessoa=gil, empresa=empresa, filial=norte,
                                cargo=cargos["gerente"])
        return gil

    def test_gerente_da_vendedor_na_filial_dele(self, conta):
        _t, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        assert pode_dar(gil, empresa, norte, cargos["vendedor"])

    def test_gerente_nao_aloca_fora_da_filial_dele(self, conta):
        _t, empresa, _n, sul, cargos = conta
        gil = self._gerente_na_norte(conta)
        assert not pode_dar(gil, empresa, sul, cargos["vendedor"])
        assert not pode_dar(gil, empresa, None, cargos["vendedor"])

    def test_gerente_nao_cria_supervisor_mesmo_com_as_mesmas_permissoes(self, conta):
        """R7: a diferença entre os dois é o ALCANCE."""
        _t, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        assert not pode_dar(gil, empresa, norte, cargos["supervisor"])

    def test_vendedor_nao_aloca_ninguem(self, conta):
        titular, empresa, norte, _s, cargos = conta
        vera = _membro(titular, "vera")
        Alocacao.objects.create(pessoa=vera, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert not pode_dar(vera, empresa, norte, cargos["cliente"])

    def test_cargo_de_outra_conta_nunca(self, conta):
        titular, empresa, norte, *_ = conta
        outro = Usuario.objects.create_user(
            email="outro-esc@teste.com", password="x", nivel=Nivel.TITULAR)
        alheio = Cargo.objects.get(conta=outro, nome="cliente")
        assert not pode_dar(titular, empresa, norte, alheio)

    def test_titular_da_qualquer_cargo_da_conta(self, conta):
        titular, empresa, _n, _s, cargos = conta
        assert pode_dar(titular, empresa, None, cargos["supervisor"])

    def test_a_lista_vazia_de_pode_conceder_e_a_regra_de_hoje(self, conta):
        """17/09/2026: lista vazia não tranca nada. Conta que já existe não
        muda de comportamento sem alguém marcar a lista em /cargos."""
        _t, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        cargos["gerente"].pode_conceder.clear()
        assert pode_dar(gil, empresa, norte, cargos["vendedor"])
        assert pode_dar(gil, empresa, norte, cargos["gerente"])

    def test_com_a_lista_o_gerente_so_da_o_que_esta_nela(self, conta):
        _t, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        cargos["gerente"].pode_conceder.set([cargos["vendedor"]])
        assert pode_dar(gil, empresa, norte, cargos["vendedor"])
        assert not pode_dar(gil, empresa, norte, cargos["gerente"])
        assert not pode_dar(gil, empresa, norte, cargos["representante"])

    def test_a_lista_nunca_afrouxa_as_travas_de_antes(self, conta):
        """Marcar Supervisor na lista do Gerente não o faz poder dar
        Supervisor: o alcance maior continua recusando (R7)."""
        _t, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        cargos["gerente"].pode_conceder.set([cargos["supervisor"]])
        assert not pode_dar(gil, empresa, norte, cargos["supervisor"])

    def test_o_titular_nao_e_preso_pela_lista(self, conta):
        titular, empresa, norte, _s, cargos = conta
        cargos["gerente"].pode_conceder.set([cargos["vendedor"]])
        assert pode_dar(titular, empresa, norte, cargos["gerente"])

    def test_gerente_alocado_em_duas_lojas_aloca_nas_duas(self, conta):
        """Alocar em mais de uma loja é uma linha por loja, e sempre foi
        assim: o teste existe para isso não sumir sem aviso."""
        _t, empresa, norte, sul, cargos = conta
        gil = self._gerente_na_norte(conta)
        Alocacao.objects.create(pessoa=gil, empresa=empresa, filial=sul,
                                cargo=cargos["gerente"])
        assert pode_dar(gil, empresa, norte, cargos["vendedor"])
        assert pode_dar(gil, empresa, sul, cargos["vendedor"])

    def test_titular_nao_da_cargo_com_permissao_que_ele_nao_tem(self, conta):
        """A trava 2 vale para o titular também: um cargo que carregue o que
        ele não tem (um cargo gravado antes desta trava, por exemplo) não sai
        das mãos dele."""
        from django.contrib.auth.models import Permission

        titular, empresa, _n, _s, cargos = conta
        cargos["supervisor"].permissoes.add(
            Permission.objects.get(codename="parametros_editar"))
        assert not pode_dar(titular, empresa, None, cargos["supervisor"])

    def test_gerente_nao_administra_supervisor_nem_a_si_mesmo(self, conta):
        titular, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        sara = _membro(titular, "sara")
        Alocacao.objects.create(pessoa=sara, empresa=empresa, cargo=cargos["supervisor"])
        vera = _membro(titular, "vera")
        Alocacao.objects.create(pessoa=vera, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert pode_administrar(gil, vera)
        assert not pode_administrar(gil, sara)
        assert not pode_administrar(gil, gil)
        assert not pode_administrar(gil, titular)

    def test_pessoa_sem_alocacao_so_o_titular_administra(self, conta):
        titular, *_ = conta
        gil = self._gerente_na_norte(conta)
        nova = _membro(titular, "nova")
        assert pode_administrar(titular, nova)
        assert not pode_administrar(gil, nova)
