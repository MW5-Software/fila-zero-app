"""A tela de Cargos: o titular monta os cargos da conta dele.

Substitui Perfis no menu do titular (14/09/2026, pedido do João: "a gente ainda
está usando a terminologia errada"). Edita `contas.Cargo`, a tabela do plano 1 —
e não `Perfil`. **As permissões ainda não passam a valer pelo cargo**: isso é o
plano 2. Esta tela é o cadastro.

Duas travas são o coração dela, e cada uma tem teste com duas contas:

- **Só o titular e a MW5 editam cargos, por NÍVEL e não por permissão**
  (spec 2026-09-14). Se editar cargo fosse uma permissão marcável num cargo,
  quem a tivesse marcaria permissão nova no próprio cargo e se promoveria.
- **A tela só enxerga os cargos da conta do contexto.** Cargo de outra conta
  pedido pelo id não é tocado.
"""

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from contas.fabrica import aplicar
from contas.models import Alcance, Alocacao, Cargo, Nivel, Usuario

SENHA = "segredo-de-teste"


def _titular(login, razao):
    from plataforma.models import Empresa

    pessoa = Usuario.objects.create_user(
        email=f"{login}@teste.com", password=SENHA, nivel=Nivel.TITULAR)
    aplicar(pessoa, Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social=razao, dono=pessoa)
    return pessoa, empresa


def _entrar(login):
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": f"{login}@teste.com",
                                     "senha": SENHA})
    return cliente


@pytest.fixture
def cenario(db):
    dono_alfa, alfa = _titular("dono-alfa-cargo", "Alfa Ltda")
    dono_beta, beta = _titular("dono-beta-cargo", "Beta Ltda")
    Cargo.objects.create(conta=dono_beta, nome="so-da-beta",
                         rotulo="SoDaBeta")
    return {"dono_alfa": dono_alfa, "alfa": alfa, "dono_beta": dono_beta,
            "beta": beta, "cliente": _entrar("dono-alfa-cargo")}


def _post(cenario, **dados):
    return cenario["cliente"].post(reverse("cargos"), dados)


class TestQuemEntra:
    def test_o_titular_abre_e_ve_os_cargos_de_fabrica(self, cenario):
        resposta = cenario["cliente"].get(reverse("cargos"))
        assert resposta.status_code == 200
        html = resposta.content.decode()
        for rotulo in ("Supervisor", "Gerente", "Vendedor", "Representante",
                       "Cliente"):
            assert rotulo in html

    def test_membro_com_a_permissao_nao_entra(self, cenario):
        """A trava é o NÍVEL. Um membro que recebesse `cargos.editar` por
        algum caminho continua sem a tela."""
        membro = Usuario.objects.create_user(
            email="membro-cargo@teste.com", password=SENHA,
            nivel=Nivel.MEMBRO, dono=cenario["dono_alfa"])
        membro.user_permissions.add(Permission.objects.get(codename="cargos_editar"))
        assert _entrar("membro-cargo").get(reverse("cargos")).status_code == 404

    def test_a_fabrica_do_titular_da_cargos_editar(self):
        from contas.fabrica import DE_FABRICA

        assert "cargos.editar" in DE_FABRICA[Nivel.TITULAR]


class TestSoAContaDele:
    def test_a_lista_nao_mostra_cargo_de_outra_conta(self, cenario):
        html = cenario["cliente"].get(reverse("cargos")).content.decode()
        assert "SoDaBeta" not in html

    def test_a_exportacao_nao_leva_cargo_de_outra_conta(self, cenario):
        resposta = cenario["cliente"].get(reverse("cargos"),
                                          {"formato": "impressao"})
        assert resposta.status_code == 200
        html = resposta.content.decode("utf-8", "replace")
        assert "Supervisor" in html
        assert "SoDaBeta" not in html

    @pytest.mark.parametrize("acao", ["salvar", "remover"])
    def test_cargo_de_outra_conta_pedido_pelo_id_nao_e_tocado(self, cenario,
                                                             acao):
        alheio = Cargo.objects.get(nome="so-da-beta")
        resposta = _post(cenario, acao=acao, cargo=str(alheio.pk),
                         rotulo="Invadido", alcance="empresa")
        assert "Cargo não encontrado" in resposta.content.decode()
        alheio.refresh_from_db()
        assert alheio.rotulo == "SoDaBeta"


class TestCriarEditar:
    def test_criar_um_cargo_na_conta_dele_e_audita(self, cenario):
        from contas.models import RegistroDeAuditoria

        _post(cenario, acao="criar", rotulo="Faturista", alcance="filial",
              e_cliente="1", permissoes=["usuarios_editar"])

        cargo = Cargo.objects.get(conta=cenario["dono_alfa"], nome="faturista")
        assert cargo.alcance == Alcance.FILIAL
        assert cargo.e_cliente is True
        assert cargo.de_fabrica is False
        assert list(cargo.permissoes.values_list("codename", flat=True)) == [
            "usuarios_editar"]
        assert RegistroDeAuditoria.objects.filter(acao="cargo_criado").exists()

    def test_nome_repetido_na_conta_e_recusado_com_frase(self, cenario):
        resposta = _post(cenario, acao="criar", rotulo="Vendedor",
                         alcance="filial")
        assert "Já existe um cargo" in resposta.content.decode()
        assert Cargo.objects.filter(conta=cenario["dono_alfa"],
                                    nome="vendedor").count() == 1

    def test_o_mesmo_nome_em_outra_conta_nao_atrapalha(self, cenario):
        _post(cenario, acao="criar", rotulo="So da Beta", alcance="filial")
        assert Cargo.objects.filter(conta=cenario["dono_alfa"],
                                    nome="so-da-beta").exists()

    def test_editar_troca_rotulo_alcance_cliente_e_permissoes(self, cenario):
        from contas.models import RegistroDeAuditoria

        vendedor = Cargo.objects.get(conta=cenario["dono_alfa"], nome="vendedor")
        _post(cenario, acao="salvar", cargo=str(vendedor.pk),
              rotulo="Vendedor Externo", alcance="proprios",
              permissoes=["usuarios_editar"])

        vendedor.refresh_from_db()
        assert vendedor.rotulo == "Vendedor Externo"
        assert vendedor.nome == "vendedor"
        assert vendedor.alcance == Alcance.PROPRIOS
        assert vendedor.e_cliente is False
        assert set(vendedor.permissoes.values_list("codename", flat=True)) == {
            "usuarios_editar"}
        assert RegistroDeAuditoria.objects.filter(acao="cargo_editado").exists()

    def test_alcance_invalido_e_recusado(self, cenario):
        resposta = _post(cenario, acao="criar", rotulo="Estranho",
                         alcance="universo")
        assert resposta.status_code == 200
        assert not Cargo.objects.filter(nome="estranho").exists()


class TestNinguemSePromove:
    def test_as_caixas_nao_oferecem_cargos(self, cenario):
        html = cenario["cliente"].get(reverse("cargos")).content.decode()
        assert 'value="cargos_editar"' not in html
        assert 'value="usuarios_editar"' in html

    def test_cargos_editar_forjado_no_post_nao_entra_no_cargo(self, cenario):
        _post(cenario, acao="criar", rotulo="Promovido", alcance="empresa",
              permissoes=["cargos_editar", "usuarios_editar"])
        cargo = Cargo.objects.get(conta=cenario["dono_alfa"], nome="promovido")
        assert set(cargo.permissoes.values_list("codename", flat=True)) == {
            "usuarios_editar"}


class TestRemover:
    def test_cargo_de_fabrica_nao_se_remove(self, cenario):
        gerente = Cargo.objects.get(conta=cenario["dono_alfa"], nome="gerente")
        resposta = _post(cenario, acao="remover", cargo=str(gerente.pk))
        assert Cargo.objects.filter(pk=gerente.pk).exists()
        assert "de fábrica" in resposta.content.decode()

    def test_cargo_com_alocacao_nao_se_remove_e_diz_quantas(self, cenario):
        _post(cenario, acao="criar", rotulo="Caixa", alcance="filial")
        caixa = Cargo.objects.get(conta=cenario["dono_alfa"], nome="caixa")
        membro = Usuario.objects.create_user(
            email="caixa-pessoa@teste.com", password=SENHA,
            nivel=Nivel.MEMBRO, dono=cenario["dono_alfa"])
        Alocacao.objects.create(pessoa=membro, empresa=cenario["alfa"],
                                cargo=caixa)

        resposta = _post(cenario, acao="remover", cargo=str(caixa.pk))

        assert Cargo.objects.filter(pk=caixa.pk).exists()
        assert "1 pessoa" in resposta.content.decode()

    def test_cargo_criado_e_vazio_se_remove_e_audita(self, cenario):
        from contas.models import RegistroDeAuditoria

        _post(cenario, acao="criar", rotulo="Temporario", alcance="filial")
        cargo = Cargo.objects.get(conta=cenario["dono_alfa"], nome="temporario")
        _post(cenario, acao="remover", cargo=str(cargo.pk))
        assert not Cargo.objects.filter(pk=cargo.pk).exists()
        assert RegistroDeAuditoria.objects.filter(acao="cargo_removido").exists()


def test_a_tabela_ordena_por_coluna(cenario):
    """R46 — `tests/test_regra_tabela.py` cobra; aqui diz o mesmo na tela."""
    assert "ordenar=" in cenario["cliente"].get(reverse("cargos")).content.decode()

