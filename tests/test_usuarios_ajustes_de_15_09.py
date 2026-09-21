"""Três ajustes na tela de Usuários pedidos em 15/09/2026: o titular não é
alocado (e a tela para de oferecer), o nível MEMBRO se chama "Usuário", e a
tabela diz a empresa de cada pessoa."""

import re

import pytest
from django.test import Client
from django.urls import reverse

from contas.models import Alocacao, Cargo, Nivel, Usuario
from plataforma.models import Empresa

SENHA = "segredo-de-teste"

pytestmark = pytest.mark.django_db


def _entrar(email):
    cliente = Client()
    resposta = cliente.post(reverse("entrar"), {"usuario": email, "senha": SENHA})
    assert resposta.status_code == 302, "o login do teste não entrou"
    return cliente


def _linhas(html) -> list[list[str]]:
    """As células de dado de cada linha da tabela, sem a coluna de ações."""
    return [[re.sub(r"<[^>]+>", "", c).strip()
             for c in re.findall(r"<td.*?</td>", tr, re.S)][1:]
            for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S)[1:]]


@pytest.fixture
def cenario():
    from contas.fabrica import aplicar

    titular = Usuario.objects.create_user(
        email="dono@teste.com", password=SENHA, nome="Dono", nivel=Nivel.TITULAR)
    aplicar(titular, Nivel.TITULAR)
    alfa = Empresa.objects.create(razao_social="Alfa Indústria Ltda",
                                  nome_fantasia="Alfa", dono=titular)
    ana = Usuario.objects.create_user(
        email="ana@teste.com", password=SENHA, nome="Ana", nivel=Nivel.MEMBRO,
        dono=titular)
    Alocacao.objects.create(pessoa=ana, empresa=alfa,
                            cargo=Cargo.objects.get(conta=titular, nome="vendedor"))
    # Uma segunda conta: sem ela, o filtro por empresa passaria mesmo
    # ignorado, porque só haveria gente da Alfa na lista.
    dono_beta = Usuario.objects.create_user(
        email="beta@teste.com", password=SENHA, nome="Beta", nivel=Nivel.TITULAR)
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=dono_beta)
    # A MW5 que ENTRA é superusuária, e superusuário não aparece na lista; a
    # pessoa da MW5 que aparece — e não tem empresa — é um MASTER comum.
    Usuario.objects.create_user(email="equipe@mw5.com", password=SENHA,
                                nome="Equipe", nivel=Nivel.MASTER)
    Usuario.objects.create_superuser(email="mw5@teste.com", password=SENHA)
    return {"titular": titular, "alfa": alfa, "ana": ana, "beta": beta}


class TestOTitularNaoEAlocado:

    def test_o_bloco_de_alocacoes_some_para_titular_e_master(self, cenario):
        """O mesmo par nível↔bloco que já esconde a Conta: o atributo diz os
        níveis em que o bloco não vale, e o script o esconde e desliga."""
        html = _entrar("mw5@teste.com").get(reverse("usuarios")).content.decode()
        blocos = re.findall(r"<[^>]+data-nivel-sem-alocacao=\"([^\"]+)\"[^>]*>", html)
        assert blocos, "o bloco de alocações não diz em que níveis ele some"
        assert set(blocos[0].split(",")) == {str(int(Nivel.MASTER)),
                                             str(int(Nivel.TITULAR))}

    def test_o_script_esconde_todos_os_blocos_do_formulario(self):
        """`querySelectorAll`, e não `querySelector`: o formulário tem o bloco
        da conta E o de alocações, e o primeiro achado não pode ser o único."""
        from pathlib import Path

        script = Path("contas/static/contas/usuarios.js").read_text()
        assert "data-nivel-sem-alocacao" in script
        assert 'querySelectorAll("[data-nivel-sem-conta], [data-nivel-sem-alocacao]")' in script

    def test_criar_titular_com_linha_de_alocacao_no_post_nao_aloca(self, cenario):
        """O servidor é a tranca: um POST com linha de alocação num titular
        (formulário velho, ou forjado) cria o titular sem alocação."""
        cargo = Cargo.objects.get(conta=cenario["titular"], nome="vendedor")
        _entrar("mw5@teste.com").post(reverse("usuarios"), {
            "acao": "criar", "nome": "Novo Dono", "email": "novo@teste.com",
            "nivel": str(int(Nivel.TITULAR)), "razao_social": "Gama Ltda",
            "alocacoes": "1", "aloc_empresa": [str(cenario["alfa"].pk)],
            "aloc_filial": [""], "aloc_cargo": [str(cargo.pk)]})
        novo = Usuario.objects.filter(email="novo@teste.com").first()
        assert novo is not None and novo.nivel == Nivel.TITULAR
        assert not novo.alocacoes.exists()


class TestOMembroSeChamaUsuario:

    def test_o_rotulo_do_nivel(self):
        assert Nivel.MEMBRO.label == "Usuário"
        assert int(Nivel.MEMBRO) == 2, "o número é o que o banco guarda"

    def test_a_tela_escreve_usuario_e_nao_membro(self, cenario):
        """O rótulo continua onde o NÍVEL é escrito — no seletor da ficha, de
        onde a MW5 escolhe —, e não na tabela: a coluna dela virou CARGO em
        18/09/2026 (pedido do cliente), porque "Usuário" para quase todo mundo
        não respondia "quem é o gerente aqui?"."""
        html = _entrar("mw5@teste.com").get(reverse("usuarios")).content.decode()

        assert ">Usuário</option>" in html
        assert "Membro" not in html


class TestAColunaEmpresa:

    def _tabela(self, cenario, **query):
        html = _entrar("mw5@teste.com").get(reverse("usuarios"), query).content.decode()
        return {l[1]: l for l in _linhas(html) if len(l) > 1}

    def test_titular_e_usuario_mostram_a_empresa_da_conta(self, cenario):
        tabela = self._tabela(cenario)
        assert "Alfa" in tabela["dono@teste.com"]
        assert "Alfa" in tabela["ana@teste.com"]

    def test_mw5_nao_tem_empresa(self, cenario):
        assert "—" in self._tabela(cenario)["equipe@mw5.com"]

    def test_filtra_pela_empresa(self, cenario):
        from comum.listagem import nome_do_campo

        assert "beta@teste.com" in self._tabela(cenario)
        tabela = self._tabela(cenario, **{nome_do_campo("empresa", "contem"): "alf"})
        assert set(tabela) == {"dono@teste.com", "ana@teste.com"}

    def test_a_coluna_nao_custa_uma_consulta_por_linha(self, cenario):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        cliente = _entrar("mw5@teste.com")
        with CaptureQueriesContext(connection) as poucas:
            cliente.get(reverse("usuarios"))
        for n in range(6):
            Usuario.objects.create_user(
                email=f"extra{n}@teste.com", password=SENHA, nivel=Nivel.MEMBRO,
                dono=cenario["titular"])
        with CaptureQueriesContext(connection) as muitas:
            cliente.get(reverse("usuarios"))
        # A tela já custava 2 consultas por pessoa antes desta coluna (os
        # modais de cada linha) — medido com o código anterior. O que a
        # coluna não pode é somar uma leitura de EMPRESA por pessoa.
        def de_empresa(contexto):
            # Fora a lista de contas do seletor de cada modal
            # (`dono_id IS NOT NULL`), que já existia uma por linha.
            return [q for q in contexto.captured_queries
                    if '"plataforma_empresa"' in q["sql"]
                    and "IS NOT NULL" not in q["sql"]]
        assert len(de_empresa(muitas)) == len(de_empresa(poucas)), (
            len(de_empresa(poucas)), len(de_empresa(muitas)))

    def test_a_exportacao_leva_a_empresa(self, cenario):
        """Pela impressão: é HTML, e dá para ler a coluna sem abrir planilha.
        As duas saídas usam as mesmas `COLUNAS_DE_EXPORTACAO`."""
        html = _entrar("mw5@teste.com").get(
            reverse("usuarios"), {"formato": "impressao"}).content.decode()
        assert re.search(r"<th[^>]*>\s*Empresa\s*</th>", html), html[:500]
        assert "Alfa" in html


class TestAColunaEmpresaComVarias:
    """17/09/2026: a conta passou a ter várias empresas, e a subconsulta
    trazia UMA por pessoa — a segunda sumia da tela."""

    def test_a_coluna_mostra_as_duas_empresas_da_pessoa(self, cenario):
        from plataforma.models import Empresa, Filial

        from tests.conftest import alocar

        titular = Usuario.objects.get(email="dono@teste.com")
        beta = Empresa.objects.create(razao_social="Gama Ltda", dono=titular)
        ana = Usuario.objects.get(email="ana@teste.com")
        alocar(ana, beta, "vendedor",
               filial=Filial.objects.get(empresa=beta, e_matriz=True))
        html = _entrar("mw5@teste.com").get(reverse("usuarios")).content.decode()
        celulas = " | ".join({l[1]: l for l in _linhas(html) if len(l) > 1}["ana@teste.com"])
        assert "Alfa" in celulas and "Gama" in celulas

    def test_o_titular_mostra_as_empresas_da_conta_dele(self, cenario):
        from plataforma.models import Empresa

        titular = Usuario.objects.get(email="dono@teste.com")
        Empresa.objects.create(razao_social="Gama Ltda", dono=titular)
        html = _entrar("mw5@teste.com").get(reverse("usuarios")).content.decode()
        celulas = " | ".join({l[1]: l for l in _linhas(html) if len(l) > 1}["dono@teste.com"])
        assert "Alfa" in celulas and "Gama" in celulas
