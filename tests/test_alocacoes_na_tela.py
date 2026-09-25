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


class TestOQueCadaCargoPodeConceder:
    """17/09/2026: a lista do cargo de quem edita é a última trava."""

    def test_gerente_com_a_lista_so_cria_o_que_esta_nela(self, conta):
        gil, cargos = conta["gil"], conta["cargos"]
        cargos["gerente"].pode_conceder.set([cargos["vendedor"]])
        cliente = _entrar("gil@teste.com")
        recusado = _criar(cliente, "novo-rep@teste.com",
                          (conta["alfa"], conta["norte"], cargos["representante"]))
        assert not Usuario.objects.filter(email="novo-rep@teste.com").exists()
        assert "Você não pode dar o cargo" in recusado.content.decode()
        _criar(cliente, "novo-vend@teste.com",
               (conta["alfa"], conta["norte"], cargos["vendedor"]))
        assert Usuario.objects.filter(email="novo-vend@teste.com").exists()

    @pytest.mark.parametrize("cargo", ["gerente", "vendedor"])
    def test_o_supervisor_de_fabrica_cria_o_que_a_lista_dele_diz(self, conta, cargo):
        """25/09/2026, pedido do cliente: "supervisor não cadastrou gerente".
        A lista dele dizia Gerente e Vendedor, mas `pode_dar` também exige que
        quem concede tenha TODAS as permissões do cargo, e o Supervisor de
        fábrica não trazia `fila.participar`, que os dois trazem: ele não
        criava nenhum dos dois."""
        email = f"novo-{cargo}-da-sara@teste.com"
        _criar(_entrar("sara@teste.com"), email,
               (conta["alfa"], conta["norte"], conta["cargos"][cargo]))

        assert _lugares(Usuario.objects.get(email=email)) == {("Norte", cargo)}

    def test_o_supervisor_ainda_nao_cria_supervisor(self, conta):
        _criar(_entrar("sara@teste.com"), "outra-sara@teste.com",
               (conta["alfa"], None, conta["cargos"]["supervisor"]))

        assert not Usuario.objects.filter(email="outra-sara@teste.com").exists()

    def test_sem_lista_o_gerente_continua_como_antes(self, conta):
        gil, cargos = conta["gil"], conta["cargos"]
        cargos["gerente"].pode_conceder.clear()
        cliente = _entrar("gil@teste.com")
        _criar(cliente, "outro-rep@teste.com",
               (conta["alfa"], conta["norte"], cargos["representante"]))
        assert Usuario.objects.filter(email="outro-rep@teste.com").exists()


def _opcoes(html, campo):
    """Os rótulos oferecidos na caixa `campo` da linha em branco do cadastro."""
    import re

    lista = re.search(r'id="aloc-lista-nova">(.*?)</div><button', html, re.S)
    assert lista, "a tela não trouxe o bloco de alocações do cadastro"
    caixa = re.search(rf'<select name="{campo}"[^>]*>(.*?)</select>',
                      lista.group(1), re.S)
    return [r for r in re.findall(r">([^<]*)</option>", caixa.group(1))]


class TestATelaSoOfereceOQueOPostAceita:
    """25/09/2026, pedido do cliente: "gerente tá podendo cadastrar qualquer
    usuário". O POST já recusava, mas a caixa oferecia todos os cargos da conta
    e "Todas as filiais", e só dizia não depois de salvar. Quem filtra é o
    próprio `pode_dar`, e não uma segunda regra."""

    def _html(self, email):
        return _entrar(email).get(reverse("usuarios")).content.decode()

    def test_o_gerente_so_ve_vendedor_e_a_loja_dele(self, conta):
        html = self._html("gil@teste.com")

        assert _opcoes(html, "aloc_cargo") == ["Cargo…", "Vendedor"]
        assert _opcoes(html, "aloc_filial") == ["Filial…", "Norte"]

    def test_o_supervisor_ve_gerente_e_vendedor(self, conta):
        html = self._html("sara@teste.com")

        assert _opcoes(html, "aloc_cargo") == ["Cargo…", "Gerente", "Vendedor"]
        assert "Todas as filiais" in _opcoes(html, "aloc_filial")

    def test_o_titular_continua_vendo_todos(self, conta):
        html = self._html(conta["titular"].email)

        assert _opcoes(html, "aloc_cargo") == [
            "Cargo…", "Cliente", "Gerente", "Representante", "Supervisor",
            "Vendedor"]
        assert "Todas as filiais" in _opcoes(html, "aloc_filial")


def test_com_duas_empresas_cada_uma_oferece_so_o_que_se_da_nela(conta):
    """A caixa guardava o que se pode dar por CONTA, e repetia a lista em toda
    empresa: gerente na Alfa e só vendedor na Beta, o Gil via "Vendedor
    (Beta Ltda)" e o POST recusava (revisão de código de 25/09/2026). Agora
    é por empresa, que é o que `pode_dar` responde."""
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=conta["titular"])
    centro_beta = Filial.objects.create(empresa=beta, nome="Centro B", apelido="Centro B")
    Alocacao.objects.create(pessoa=conta["gil"], empresa=beta, filial=centro_beta,
                            cargo=conta["cargos"]["vendedor"])

    html = _entrar("gil@teste.com").get(reverse("usuarios")).content.decode()
    cargos = _opcoes(html, "aloc_cargo")
    assert "Vendedor (Alfa Ltda)" in cargos
    assert "Vendedor (Beta Ltda)" not in cargos


class TestAPropriaPessoaNaTabela:
    """25/09/2026, pedido do cliente: "usuário ele mesmo não aparece na
    tabela". A lista era a de quem se pode ADMINISTRAR, e ninguém administra
    a si mesmo por esta tela. Ela aparece agora — sem editar, senha, ativar ou
    remover, que são de "Meu Perfil" —, e as ações continuam passando por
    `_alcancavel`, que não a inclui."""

    def _html(self, email):
        return _entrar(email).get(reverse("usuarios")).content.decode()

    def test_o_titular_e_o_gerente_se_veem(self, conta):
        for email, pessoa in ((conta["titular"].email, conta["titular"]),
                              ("gil@teste.com", conta["gil"])):
            html = self._html(email)
            linhas = html.split("<tbody")[1].split("</tbody>")[0]
            assert email in linhas
            assert f'data-open-modal="usuario-{pessoa.pk}-editar"' not in html
            assert f'id="usuario-{pessoa.pk}-editar"' not in html
            assert 'class="tag primary">você<' in html
            assert f'href="{reverse("perfil")}"' in html

    def test_continua_nao_se_editando_pelo_post(self, conta):
        gil = conta["gil"]
        _entrar("gil@teste.com").post(reverse("usuarios"), {
            "acao": "editar", "id": str(gil.pk), "nome": "Gil Novo"})
        gil.refresh_from_db()
        assert gil.nome == "Gil"
