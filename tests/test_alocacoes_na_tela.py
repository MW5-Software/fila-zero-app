"""O bloco de Alocações do cadastro de usuário (plano 2 dos cargos, task 5).

É por aqui que alguém ganha cargo desde que o Perfil saiu, e por isso é aqui
que um Gerente mal-intencionado tentaria criar um Supervisor, alocar fora da
filial dele ou mexer na própria alocação. Toda recusa é provada pelo POST
forjado — a tela esconder a opção nunca é a proteção.
"""

import pytest
from django.test import Client
from django.urls import reverse

from contas.models import Alocacao, Cargo, Nivel, Usuario
from nucleo.permissoes import pode
from plataforma.models import Empresa, Filial

SENHA = "segredo-de-teste"

pytestmark = pytest.mark.django_db


def _entrar(email):
    c = Client()
    c.post(reverse("entrar"), {"usuario": email, "senha": SENHA})
    return c


@pytest.fixture
def conta():
    from contas.fabrica import aplicar

    titular = Usuario.objects.create_user(
        email="dono-tela@teste.com", password=SENHA, nivel=Nivel.TITULAR)
    aplicar(titular, Nivel.TITULAR)
    alfa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    norte = Filial.objects.create(empresa=alfa, nome="Norte", apelido="Norte")
    sul = Filial.objects.create(empresa=alfa, nome="Sul", apelido="Sul")
    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}

    def membro(login, cargo, filial=None):
        pessoa = Usuario.objects.create_user(
            email=f"{login}@teste.com", password=SENHA, nome=login.title(),
            nivel=Nivel.MEMBRO, dono=titular)
        Alocacao.objects.create(pessoa=pessoa, empresa=alfa, filial=filial,
                                cargo=cargos[cargo])
        return pessoa

    gil = membro("gil", "gerente", norte)
    sara = membro("sara", "supervisor")
    vera = membro("vera", "vendedor", norte)
    return {"titular": titular, "alfa": alfa, "norte": norte, "sul": sul,
            "cargos": cargos, "gil": gil, "sara": sara, "vera": vera}


def _criar(cliente, email, *linhas, **extra):
    """POST de criar com as linhas `(empresa, filial ou None, cargo)`."""
    dados = {"acao": "criar", "nome": "Nova Pessoa", "email": email,
             "alocacoes": "1",
             "aloc_empresa": [str(e.pk) for e, _f, _c in linhas],
             "aloc_filial": [str(f.pk) if f else "" for _e, f, _c in linhas],
             "aloc_cargo": [str(c.pk) for _e, _f, c in linhas], **extra}
    return cliente.post(reverse("usuarios"), dados)


def _lugares(pessoa):
    return {(a.filial.nome if a.filial else "", a.cargo.nome)
            for a in pessoa.alocacoes.select_related("filial", "cargo")}


class TestOTitularAloca:
    def test_cria_ja_alocado_e_como_membro(self, conta):
        _criar(_entrar(conta["titular"].email), "nova@teste.com",
               (conta["alfa"], conta["norte"], conta["cargos"]["vendedor"]))

        nova = Usuario.objects.get(email="nova@teste.com")
        assert _lugares(nova) == {("Norte", "vendedor")}
        assert nova.nivel > Nivel.TITULAR
        assert nova.dono_id == conta["titular"].pk

    def test_quem_foi_criado_como_supervisor_ja_entra_podendo(self, conta):
        """O defeito que parece que funcionou: uma conta que loga e não vê
        nada. Desde a virada, a permissão vem do cargo da alocação."""
        _criar(_entrar(conta["titular"].email), "sup@teste.com",
               (conta["alfa"], None, conta["cargos"]["supervisor"]),
               senha_da_pessoa="senha-do-supervisor")

        cliente = Client()
        cliente.post(reverse("entrar"), {"usuario": "sup@teste.com",
                                         "senha": "senha-do-supervisor"})
        assert cliente.get("/usuarios").status_code == 200

    def test_editar_troca_as_alocacoes(self, conta):
        vera = conta["vera"]
        _entrar(conta["titular"].email).post(reverse("usuarios"), {
            "acao": "editar", "id": str(vera.pk), "nome": "Vera",
            "alocacoes": "1", "aloc_empresa": str(conta["alfa"].pk),
            "aloc_filial": "", "aloc_cargo": str(conta["cargos"]["supervisor"].pk)})

        assert _lugares(vera) == {("", "supervisor")}

    def test_editar_sem_o_bloco_no_post_nao_apaga_alocacao(self, conta):
        """Um POST que não passou pela tela (sem o marcador `alocacoes`) não
        pode tirar o lugar de alguém por não ter mandado linha nenhuma."""
        vera = conta["vera"]
        _entrar(conta["titular"].email).post(reverse("usuarios"), {
            "acao": "editar", "id": str(vera.pk), "nome": "Vera Nova"})

        assert _lugares(vera) == {("Norte", "vendedor")}

    def test_linha_em_branco_some_e_repetida_vira_uma(self, conta):
        alfa, norte, cargos = conta["alfa"], conta["norte"], conta["cargos"]
        _entrar(conta["titular"].email).post(reverse("usuarios"), {
            "acao": "criar", "nome": "Dupla", "email": "dupla@teste.com",
            "alocacoes": "1",
            "aloc_empresa": [str(alfa.pk), "", str(alfa.pk)],
            "aloc_filial": [str(norte.pk), "", str(norte.pk)],
            "aloc_cargo": [str(cargos["vendedor"].pk), "",
                           str(cargos["representante"].pk)]})

        assert _lugares(Usuario.objects.get(email="dupla@teste.com")) == {
            ("Norte", "representante")}


class TestEscaladaPeloPost:
    def test_gerente_nao_aloca_em_outra_filial(self, conta):
        resposta = _criar(_entrar(conta["gil"].email), "fora@teste.com",
                          (conta["alfa"], conta["sul"], conta["cargos"]["vendedor"]))

        assert not Usuario.objects.filter(email="fora@teste.com").exists()
        assert "Você não pode dar o cargo" in resposta.content.decode()

    def test_gerente_nao_cria_supervisor(self, conta):
        _criar(_entrar(conta["gil"].email), "super@teste.com",
               (conta["alfa"], conta["norte"], conta["cargos"]["supervisor"]))

        assert not Usuario.objects.filter(email="super@teste.com").exists()

    def test_gerente_nao_cria_gente_sem_lugar(self, conta):
        resposta = _entrar(conta["gil"].email).post(reverse("usuarios"), {
            "acao": "criar", "nome": "Sem Lugar", "email": "semlugar@teste.com",
            "alocacoes": "1"})

        assert not Usuario.objects.filter(email="semlugar@teste.com").exists()
        assert "Aloque a pessoa em pelo menos um lugar." in resposta.content.decode()

    def test_gerente_da_vendedor_na_filial_dele(self, conta):
        """A linha de base: sem ela, as recusas acima passariam por uma tela
        que recusa tudo."""
        _criar(_entrar(conta["gil"].email), "novo-vendedor@teste.com",
               (conta["alfa"], conta["norte"], conta["cargos"]["vendedor"]))

        assert _lugares(Usuario.objects.get(email="novo-vendedor@teste.com")) == {
            ("Norte", "vendedor")}

    def test_gerente_nao_edita_o_supervisor(self, conta):
        sara = conta["sara"]
        _entrar(conta["gil"].email).post(reverse("usuarios"), {
            "acao": "editar", "id": str(sara.pk), "nome": "Tomada",
            "alocacoes": "1", "aloc_empresa": str(conta["alfa"].pk),
            "aloc_filial": str(conta["norte"].pk),
            "aloc_cargo": str(conta["cargos"]["vendedor"].pk)})

        sara.refresh_from_db()
        assert sara.nome == "Sara"
        assert _lugares(sara) == {("", "supervisor")}

    def test_ninguem_edita_a_propria_alocacao(self, conta):
        gil = conta["gil"]
        _entrar(gil.email).post(reverse("usuarios"), {
            "acao": "editar", "id": str(gil.pk), "nome": "Gil",
            "alocacoes": "1", "aloc_empresa": str(conta["alfa"].pk),
            "aloc_filial": "", "aloc_cargo": str(conta["cargos"]["gerente"].pk)})

        assert _lugares(gil) == {("Norte", "gerente")}

    def test_cargo_de_outra_conta_e_recusado(self, conta):
        outro = Usuario.objects.create_user(
            email="outro-dono@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        alheio = Cargo.objects.get(conta=outro, nome="cliente")

        resposta = _criar(_entrar(conta["titular"].email), "alheio@teste.com",
                          (conta["alfa"], None, alheio))

        assert not Usuario.objects.filter(email="alheio@teste.com").exists()
        assert "Lugar ou cargo inválido." in resposta.content.decode()

    def test_filial_de_outra_empresa_e_recusada(self, conta):
        outro = Usuario.objects.create_user(
            email="outro-fil@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        beta = Empresa.objects.create(razao_social="Beta Ltda", dono=outro)
        dela = Filial.objects.create(empresa=beta, nome="Beta Centro",
                                     apelido="Centro")

        _criar(_entrar(conta["titular"].email), "filial-alheia@teste.com",
               (conta["alfa"], dela, conta["cargos"]["cliente"]))

        assert not Usuario.objects.filter(email="filial-alheia@teste.com").exists()

    def test_gerente_lista_so_quem_administra(self, conta):
        html = _entrar(conta["gil"].email).get(reverse("usuarios")).content.decode()

        assert "vera@teste.com" in html
        assert "sara@teste.com" not in html
        assert "dono-tela@teste.com" not in html


class TestAMw5EOTitular:
    def test_promover_a_titular_leva_as_alocacoes(self, conta):
        """O titular não é alocado (D3): ele alcança a conta toda, e um cargo
        nele poderia trancá-lo para fora da própria conta."""
        Usuario.objects.create_superuser(email="mw5-tela@teste.com", password=SENHA)
        vera = conta["vera"]
        _entrar("mw5-tela@teste.com").post(reverse("usuarios"), {
            "acao": "editar", "id": str(vera.pk), "nome": "Vera",
            "nivel": str(int(Nivel.TITULAR)),
            "alocacoes": "1", "aloc_empresa": str(conta["alfa"].pk),
            "aloc_filial": "", "aloc_cargo": str(conta["cargos"]["cliente"].pk)})

        vera.refresh_from_db()
        assert vera.nivel == Nivel.TITULAR
        assert not vera.alocacoes.exists()


class TestATela:
    def test_mostra_alocacoes_e_nao_mostra_perfis_nem_o_painel_de_nivel(self, conta):
        html = _entrar(conta["titular"].email).get(reverse("usuarios")).content.decode()

        assert "+ Acrescentar alocação" in html
        assert 'name="aloc_cargo"' in html
        assert 'name="perfis"' not in html
        assert "data-ct-resumo" not in html

    def test_o_modal_de_editar_vem_com_a_alocacao_marcada(self, conta):
        import re

        html = _entrar(conta["titular"].email).get(reverse("usuarios")).content.decode()
        lista = re.search(
            rf'id="aloc-lista-{conta["vera"].pk}">(.*?)</div><button', html, re.S)
        assert lista, "o modal de editar de Vera não trouxe o bloco de alocações"
        assert f'value="{conta["norte"].pk}" selected' in lista.group(1)
        assert f'value="{conta["cargos"]["vendedor"].pk}" selected' in lista.group(1)

    def test_o_gerente_so_ganha_o_que_o_cargo_da(self, conta):
        """Fecha o ciclo pelo lado de quem edita: o Gerente abre a tela porque
        o cargo dele tem `usuarios.editar` na Norte."""
        from django.test import RequestFactory

        from comum.sessao import usuario_da_sessao

        pedido = RequestFactory().get("/")
        pedido.session = {"usuario_id": conta["gil"].pk}
        assert pode(usuario_da_sessao(pedido), "usuarios.editar")
