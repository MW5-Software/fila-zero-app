"""O que cada pessoa alcança — e, principalmente, o que ela NÃO alcança.

Estes testes são escritos por ATAQUE, não por uso. Um teste que só confirma
que o vendedor vê os clientes dele passaria igual se a função devolvesse
`Usuario.objects.all()` — e o vazamento que ela existe para impedir é justamente
esse. Toda classe aqui tem pelo menos um caso do tipo "quem NÃO deveria ver
não vê".

O vazamento concreto que se está impedindo: um cliente lendo o orçamento — e
o PREÇO — de outro cliente, com o id digitado na barra do navegador.

Desde a virada dos cargos (14/09/2026) a segunda fronteira, a de dentro da
empresa, é o ALCANCE do cargo da alocação, e não mais a carteira.
"""

import pytest
from django.test import RequestFactory

from contas.alcance import empresa_de, empresas_alcancadas
from contas.lugar import clientes_alcancados
from contas.models import Nivel, Usuario
from plataforma.models import Empresa, Filial
from tests.conftest import alocar, por_na_conta


@pytest.fixture
def cenario(db):
    """Duas empresas. Na Alfa, duas filiais: o vendedor e um cliente na Norte,
    o outro cliente na Sul. Na Beta, um vendedor e um cliente.

    Duas empresas e duas filiais de propósito: com uma só de cada, uma função
    que devolvesse "todos" passaria em todos os testes.
    """
    alfa = Empresa.objects.create(razao_social="Alfa Ltda")
    beta = Empresa.objects.create(razao_social="Beta Ltda")

    def pessoa(login, nivel, empresas):
        u = Usuario.objects.create_user(
            email=f"{login}@teste.com", password="x", nivel=nivel)
        por_na_conta(u, empresas[0] if empresas else None)
        return u

    dados = {
        "alfa": alfa, "beta": beta,
        "master": pessoa("master", Nivel.MASTER, []),
        "admin_alfa": pessoa("admin_alfa", Nivel.TITULAR, [alfa]),
        # Dono da Beta. Era "admin de DUAS" até 09/09/2026, e o nome
        # sobreviveu à mudança para não renomear trinta chamadas — mas o que
        # ele prova agora é o oposto: são duas CONTAS, não um Admin com duas
        # empresas.
        "admin_dois": pessoa("admin_dois", Nivel.TITULAR, [beta]),
        "vend_alfa": pessoa("vend_alfa", Nivel.MEMBRO, [alfa]),
        "vend_beta": pessoa("vend_beta", Nivel.MEMBRO, [beta]),
        "compra_a1": pessoa("compra_a1", Nivel.MEMBRO, [alfa]),
        "compra_a2": pessoa("compra_a2", Nivel.MEMBRO, [alfa]),
        "compra_b1": pessoa("compra_b1", Nivel.MEMBRO, [beta]),
    }
    alfa.refresh_from_db()
    norte = Filial.objects.create(empresa=alfa, nome="Norte", apelido="Norte")
    sul = Filial.objects.create(empresa=alfa, nome="Sul", apelido="Sul")
    dados.update(norte=norte, sul=sul)
    alocar(dados["vend_alfa"], alfa, "vendedor", filial=norte)
    alocar(dados["compra_a1"], alfa, "cliente", filial=norte)
    alocar(dados["compra_a2"], alfa, "cliente", filial=sul)
    alocar(dados["vend_beta"], beta, "vendedor")
    alocar(dados["compra_b1"], beta, "cliente")
    return dados


def _nomes(qs):
    """Só a parte antes do @, para as asserções continuarem legíveis: o login
    é o e-mail inteiro, e `["compra_a1@teste.com", ...]` esconderia o que
    cada caso está provando atrás do domínio repetido."""
    return sorted(u.email.split("@")[0] for u in qs)


def _pedido(pessoa, empresa=None):
    """Uma requisição de `pessoa`, como a sessão a monta — `clientes_alcancados`
    pergunta o LUGAR, e o lugar vem da sessão."""
    from plataforma.contexto import CHAVE_EMPRESA

    request = RequestFactory().get("/")
    request.session = {"usuario_id": pessoa.pk}
    if empresa is not None:
        request.session[CHAVE_EMPRESA] = empresa.pk
    return request


@pytest.mark.django_db
class TestEmpresasAlcancadas:
    def test_master_alcanca_todas_sem_vinculo_nenhum(self, cenario):
        """Alcance ilimitado vem do NÍVEL, não de linhas de vínculo: uma
        linha é algo que alguém marca sem querer."""
        assert cenario["master"].dono_id is None
        assert empresas_alcancadas(cenario["master"]).count() == Empresa.objects.count()

    def test_admin_de_uma_nao_alcanca_a_outra(self, cenario):
        alcancadas = empresas_alcancadas(cenario["admin_alfa"])
        assert list(alcancadas) == [cenario["alfa"]]
        assert cenario["beta"] not in alcancadas

    def test_cada_admin_alcanca_a_dele_e_so(self, cenario):
        """Era `test_admin_de_duas_alcanca_as_duas`, e provava o contrário.

        Até 09/09/2026 um Admin alcançava empresas de contas diferentes, e
        esse era o caso que justificava o M2M. Desde então a fronteira é a
        CONTA: dois clientes são duas contas, e o Admin de uma nunca alcança
        a empresa da outra — nem depois de 17/09/2026, quando a conta passou
        a poder ter várias empresas SUAS.
        """
        assert list(empresas_alcancadas(cenario["admin_alfa"])) == [
            cenario["alfa"]]
        assert list(empresas_alcancadas(cenario["admin_dois"])) == [
            cenario["beta"]]

    def test_a_conta_pode_ter_a_segunda_empresa(self, cenario):
        """17/09/2026: a trava `uma_empresa_por_conta` caiu (spec
        `2026-09-17-varias-empresas-por-conta`). A conta é o CLIENTE, e o
        cliente pode ter mais de uma pessoa jurídica. O que separa o dado de
        negócio continua sendo a coluna `empresa` de cada linha."""
        alfa, admin = cenario["alfa"], cenario["admin_alfa"]
        segunda = Empresa.objects.create(razao_social="Alfa Dois Ltda", dono=admin)
        assert set(empresas_alcancadas(admin)) == {alfa, segunda}
        assert segunda.conta_id == admin.guid

    def test_membro_da_conta_sem_alocacao_nao_alcanca_a_empresa(self, cenario):
        """Ser da conta não basta: o membro alcança só onde tem alocação."""
        solto = Usuario.objects.create_user(
            email="membro-solto@teste.com", password="x", nivel=Nivel.MEMBRO,
            dono=cenario["admin_alfa"])
        assert not empresas_alcancadas(solto).exists()
        assert empresa_de(solto) is None

    def test_sem_vinculo_de_empresa_nao_alcanca_nada(self, db):
        """Ausência de configuração precisa ser restritiva. Liberar por
        omissão é como se abre porta sem querer.

        Era "sem `Acesso` cadastrado". Não existe mais essa condição: `nivel`
        virou coluna com padrão, então toda pessoa tem nível. O que continua
        podendo faltar — e é o que isola de verdade — é o VÍNCULO de empresa.
        """
        solto = Usuario.objects.create_user(email="solto@teste.com", password="x")
        assert not empresas_alcancadas(solto).exists()

    def test_superusuario_do_django_alcanca_tudo(self, cenario):
        """Quem administra a instalação não pode ficar de fora do próprio
        sistema por falta de uma linha de cadastro — como na origem."""
        raiz = Usuario.objects.create_superuser(email="raiz@teste.com", password="x")
        assert empresas_alcancadas(raiz).count() == Empresa.objects.count()


@pytest.mark.django_db
class TestOAtalhoDasFixtures:
    """`tests/conftest.py::dar_acesso` é fixture de quase toda a suíte, e um
    atalho que mente sobre o que gravou envenena todo teste que o chama.

    Ele já promoveu em silêncio: a condição era "o nível atual é o padrão da
    coluna", que não distingue "ninguém configurou" de "configuraram
    COMPRADOR de propósito". Quem pedisse só o vínculo recebia um ADMIN, com
    as permissões de fábrica junto — e o teste passava a provar outra coisa.
    """

    def test_sem_nivel_a_pessoa_vira_admin(self, db):
        from tests.conftest import dar_acesso

        pessoa = Usuario.objects.create_user(email="p@teste.com", password="x")
        assert dar_acesso(pessoa).nivel == Nivel.TITULAR

    def test_com_nivel_a_pessoa_fica_no_nivel_pedido(self, db):
        """MASTER inclusive: ele é `0`, e uma condição escrita com `or` o
        transformaria em ADMIN sem ninguém pedir."""
        from tests.conftest import dar_acesso

        for nivel in (Nivel.MASTER, Nivel.TITULAR, Nivel.MEMBRO):
            pessoa = Usuario.objects.create_user(
                email=f"n{int(nivel)}@teste.com", password="x")
            assert dar_acesso(pessoa, nivel=nivel).nivel == nivel

    def test_sem_nivel_o_resultado_nao_depende_do_nivel_que_a_pessoa_tinha(
            self, db):
        """**É esta a propriedade que a sentinela compra.**

        A versão com o defeito decidia olhando `pessoa.nivel`: promovia a
        ADMIN quem estivesse no padrão da coluna, e não encostava em quem já
        tivesse outro nível. Dois chamados idênticos davam resultados
        diferentes por causa de um estado que o chamador não mencionou — e é
        desse "às vezes" que nasce o comprador virando admin em silêncio.

        Agora quem decide é o ARGUMENTO, sempre: sem `nivel`, ADMIN, venha a
        pessoa de onde vier.
        """
        from tests.conftest import dar_acesso

        vendedor = Usuario.objects.create_user(
            email="v@teste.com", password="x", nivel=Nivel.MEMBRO)
        novato = Usuario.objects.create_user(email="n@teste.com", password="x")

        assert dar_acesso(vendedor).nivel == dar_acesso(novato).nivel

    def test_pedir_comprador_nao_promove_a_admin(self, cenario):
        """O caso que o defeito produzia: um comprador que só precisava do
        vínculo com a empresa saía ADMIN."""
        from tests.conftest import dar_acesso

        pessoa = Usuario.objects.create_user(email="c@teste.com", password="x")
        dar_acesso(pessoa, nivel=Nivel.MEMBRO,
                   empresas=[cenario["alfa"]])

        pessoa.refresh_from_db()
        assert pessoa.nivel == Nivel.MEMBRO
        assert empresa_de(pessoa) == cenario["alfa"]


@pytest.mark.django_db
class TestClientesAlcancados:
    def test_o_vendedor_ve_so_os_clientes_da_filial_dele(self, cenario):
        pedido = _pedido(cenario["vend_alfa"])
        assert _nomes(clientes_alcancados(pedido)) == ["compra_a1"]

    def test_o_vendedor_NAO_ve_o_cliente_da_outra_filial(self, cenario):
        """A prova de que existe uma SEGUNDA fronteira.

        `compra_a2` é da mesma empresa que o vendedor alcança — a fronteira
        do inquilino sozinha o deixaria passar. Quem o barra é o alcance
        "a filial" do cargo Vendedor.
        """
        assert "compra_a2" not in _nomes(clientes_alcancados(_pedido(cenario["vend_alfa"])))

    def test_o_vendedor_NAO_ve_cliente_de_outra_empresa(self, cenario):
        assert "compra_b1" not in _nomes(clientes_alcancados(_pedido(cenario["vend_alfa"])))

    def test_quem_perdeu_a_conta_nao_ve_ninguem(self, cenario):
        """Tirar a pessoa da conta precisa valer NA HORA, sem depender de
        alguém lembrar de apagar a alocação também."""
        vend = cenario["vend_alfa"]
        vend.dono = None
        vend.save(update_fields=["dono"])
        assert not clientes_alcancados(_pedido(vend)).exists()

    def test_cliente_na_empresa_inteira_aparece_para_a_filial(self, cenario):
        """Alocado na empresa inteira, o cliente é de todas as filiais."""
        geral = Usuario.objects.create_user(email="geral@teste.com", password="x")
        alocar(geral, cenario["alfa"], "cliente")
        assert "geral" in _nomes(clientes_alcancados(_pedido(cenario["vend_alfa"])))

    def test_quem_decide_e_o_cargo_e_nao_o_nivel(self, cenario):
        """Nível de VENDEDOR com cargo Cliente é cliente; nível de COMPRADOR
        sem alocação nenhuma não é. É o que continua valendo no dia em que os
        níveis antigos saírem do `IntegerChoices`."""
        com_cargo = Usuario.objects.create_user(
            email="com_cargo@teste.com", password="x", nivel=Nivel.MEMBRO)
        alocar(com_cargo, cenario["alfa"], "cliente")
        sem_cargo = Usuario.objects.create_user(
            email="sem_cargo@teste.com", password="x", nivel=Nivel.MEMBRO)
        por_na_conta(sem_cargo, cenario["alfa"])

        vistos = _nomes(clientes_alcancados(_pedido(cenario["admin_alfa"])))
        assert "com_cargo" in vistos, "o cargo de cliente não bastou"
        assert "sem_cargo" not in vistos, "o nível sozinho não deveria bastar"

    def test_o_titular_ve_os_clientes_da_empresa_dele(self, cenario):
        assert _nomes(clientes_alcancados(_pedido(cenario["admin_alfa"]))) == [
            "compra_a1", "compra_a2"]

    def test_o_titular_de_uma_NAO_ve_cliente_da_outra(self, cenario):
        assert "compra_b1" not in _nomes(clientes_alcancados(_pedido(cenario["admin_alfa"])))

    def test_o_cliente_ve_so_a_si_mesmo(self, cenario):
        assert _nomes(clientes_alcancados(_pedido(cenario["compra_a1"]))) == ["compra_a1"]

    def test_o_cliente_NAO_ve_o_colega_da_mesma_empresa(self, cenario):
        """O vazamento mais provável do sistema: dois clientes da mesma
        empresa, com preços diferentes, um lendo o do outro."""
        assert "compra_a2" not in _nomes(clientes_alcancados(_pedido(cenario["compra_a1"])))

    def test_o_master_ve_os_clientes_da_empresa_que_esta_olhando(self, cenario):
        """A MW5 olha uma conta de cada vez: a empresa escolhida no cabeçalho,
        e não o portal inteiro numa lista só."""
        pedido = _pedido(cenario["master"], cenario["alfa"])
        assert _nomes(clientes_alcancados(pedido)) == ["compra_a1", "compra_a2"]

    def test_quem_nao_tem_alocacao_nao_ve_ninguem(self, cenario):
        """**A fixture é `cenario`, e não `db`**: com o banco vazio, uma
        função que devolvesse todo mundo também devolveria vazio."""
        solto = Usuario.objects.create_user(email="solto@teste.com", password="x")
        por_na_conta(solto, cenario["alfa"])
        assert not clientes_alcancados(_pedido(solto)).exists()
