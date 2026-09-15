"""O titular e a empresa dele nascem no mesmo cadastro.

Uma conta tem UMA empresa (09/09/2026). Separar os dois cadastros seria pedir
para criar o titular, salvar, ir a Empresas, criar a empresa e ligar as duas —
quatro passos para dizer uma coisa só, e três chances de parar no meio e
deixar um titular sem empresa (que entra no sistema e não enxerga nada) ou uma
empresa sem titular (que ninguém abre).

**Só a MW5 abre conta.** Um usuário comum entra numa conta que já existe e não
traz empresa nenhuma; um titular criado por outra pessoa não seria titular de
coisa alguma.
"""

import pytest
from django.urls import reverse

from contas.alcance import empresa_de, usuario_de
from contas.models import Nivel, Usuario
from plataforma.models import Empresa
from django.test import Client

from tests.conftest import dar_acesso

SENHA = "segredo-de-teste"


def logado(pessoa) -> Client:
    """Entra pelo FORMULÁRIO, e não por `force_login`: a sessão carrega
    contexto que o login monta, e forçar deixaria o teste provando um estado
    que a tela nunca produz."""
    c = Client()
    c.post(reverse("entrar"), {"usuario": pessoa.email, "senha": SENHA})
    return c

EMPRESA = {
    "razao_social": "Normadin Indústria Ltda",
    "nome_fantasia": "Normadin",
    "cnpj": "11.222.333/0001-81",
    "municipio": "Cascavel", "uf": "PR",
    "host": "kronos.normadin", "porta": "1521", "banco": "ORCL",
    "tabela": "PRODUTOS", "usuario": "portal", "senha": "segredo",
}


@pytest.fixture(autouse=True)
def _com_chave_de_cifragem(monkeypatch):
    """A senha do banco do cliente é guardada CIFRADA, e sem a chave o
    cadastro recusa com uma frase — que é a regra certa, provada em
    `tests/test_tela_empresa.py`. Aqui ela só atrapalharia: todo teste deste
    arquivo cairia na mesma recusa antes de chegar no que ele quer provar.
    """
    from plataforma.cifra import VARIAVEL, gerar_chave

    monkeypatch.setenv(VARIAVEL, gerar_chave())


@pytest.fixture
def mw5(db):
    from contas.fabrica import aplicar

    pessoa = Usuario.objects.create_user(
        email="mw5@teste.com", password=SENHA)
    dar_acesso(pessoa, nivel=Nivel.MASTER, empresas=[])
    # `dar_acesso` grava o NÍVEL; quem traz as permissões dele é `aplicar`.
    # Sem isto o POST cai no guarda de `usuarios.editar` e responde 404 — e o
    # teste ficaria vermelho dizendo "o usuário não foi criado", que é
    # verdade e não é a razão.
    aplicar(pessoa, Nivel.MASTER)
    return pessoa


def _criar(cliente, **extra):
    dados = {"acao": "criar", "nome": "Titular", "email": "titular@teste.com",
             "nivel": str(int(Nivel.TITULAR)), **EMPRESA}
    dados.update(extra)
    return cliente.post(reverse("usuarios"), dados)


class TestNascemJuntos:
    def test_a_empresa_e_criada_com_o_titular(self, mw5):
        r = _criar(logado(mw5))
        import re
        h = r.content.decode()
        texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
        i = texto.lower().find("cnpj precisa")
        print("TEXTO:", texto[texto.find("Usu\u00e1rios", 400):][:400])

        titular = usuario_de(Usuario.objects.get(email="titular@teste.com"))
        assert titular.nivel == Nivel.TITULAR
        nova = Empresa.objects.get(razao_social="Normadin Indústria Ltda")
        assert nova.dono_id == titular.pk
        assert nova.conta_id == titular.guid
        assert empresa_de(titular) == nova

    def test_a_empresa_aparece_na_tela_de_empresas(self, mw5):
        """O outro lado do pedido: cadastrar aqui e ver lá. Sem isto, o
        cadastro poderia gravar numa coluna que a listagem não lê."""
        cliente = logado(mw5)
        _criar(cliente)

        html = cliente.get(reverse("empresa")).content.decode()
        assert "Normadin" in html

    def test_a_conexao_com_o_kronos_vem_junto(self, mw5):
        """Foi a decisão de 09/09: a ficha INTEIRA no mesmo formulário, e não
        só a identidade."""
        _criar(logado(mw5))

        nova = Empresa.objects.get(razao_social="Normadin Indústria Ltda")
        assert (nova.host, nova.banco, nova.tabela) == (
            "kronos.normadin", "ORCL", "PRODUTOS")

    def test_a_senha_do_banco_vai_cifrada(self, mw5):
        """Nunca em texto claro: a senha só entra por `definir_senha()`, e
        `Empresa.clean()` recusa qualquer valor que não tenha vindo de lá."""
        _criar(logado(mw5))

        nova = Empresa.objects.get(razao_social="Normadin Indústria Ltda")
        assert nova.senha and nova.senha != "segredo"
        assert nova.senha_clara == "segredo"


class TestSoOTitularTrazEmpresa:
    def test_usuario_comum_nao_cria_empresa(self, mw5):
        """Ele entra numa conta que já existe."""
        antes = Empresa.objects.count()
        _criar(logado(mw5), nivel=str(int(Nivel.MEMBRO)),
               email="comum@teste.com")

        assert Empresa.objects.count() == antes

    def test_titular_sem_razao_social_nasce_sem_empresa(self, mw5):
        """Formulário sem os campos da empresa não é erro: o titular nasce
        sem ela, que é um estado que o banco aceita e a tela de Empresas
        mostra. Exigir aqui trancaria o cadastro por causa de um campo que
        quem preenche pode não ter em mãos."""
        antes = Empresa.objects.count()
        logado(mw5).post(reverse("usuarios"), {
            "acao": "criar", "nome": "Sem Empresa",
            "email": "sem@teste.com", "nivel": str(int(Nivel.TITULAR))})

        assert Usuario.objects.filter(email="sem@teste.com").exists()
        assert Empresa.objects.count() == antes


class TestTudoOuNada:
    def test_empresa_recusada_desfaz_o_titular(self, mw5):
        """**A parte que só falha em produção se ninguém provar.**

        Um `return` de dentro do `atomic()` COMITARIA o usuário — o bloco só
        desfaz quando sai por exceção. O resultado seria um titular gravado
        cuja empresa foi recusada: alguém que entra no sistema, não enxerga
        nada, e não tem na tela uma linha dizendo por quê.
        """
        resposta = _criar(logado(mw5), cnpj="11.111.111/1111-11")

        assert resposta.status_code == 200
        assert "CNPJ" in resposta.content.decode()
        assert not Usuario.objects.filter(email="titular@teste.com").exists()
        assert not Empresa.objects.filter(nome_fantasia="Normadin").exists()


class TestSoAMW5AbreConta:
    def test_o_titular_nao_cria_outra_conta(self, mw5, db):
        """Um titular cadastra a equipe DELE — vendedor e comprador —, e ela
        entra na conta dele. Criar outro titular com empresa seria abrir um
        cliente novo dentro do portal, com catálogo e preços próprios.

        A trava é dupla e as duas metades importam: `_niveis_que_pode_conceder`
        tira TITULAR da caixa E recusa o valor no POST, e
        `_criar_a_empresa_da_conta` só roda para a MW5. Provar as duas juntas
        aqui é de propósito — a segunda é a que sobra quando alguém, um dia,
        mexer na primeira por um bom motivo.
        """
        # O titular é criado DIRETO, e não pela tela: quem nasce pela tela
        # recebe uma senha temporária aleatória, e `logado()` não teria como
        # entrar com ela. O que se prova aqui é o que ELE faz depois, não
        # como ele nasceu — isso já é assunto de `TestNascemJuntos`.
        from contas.fabrica import aplicar

        titular = Usuario.objects.create_user(
            email="titular@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        Empresa.objects.create(razao_social="Normadin", dono=titular)
        aplicar(titular, Nivel.TITULAR)
        antes = Empresa.objects.count()

        logado(titular).post(reverse("usuarios"), {
            "acao": "criar", "nome": "Outro", "email": "outro@teste.com",
            "nivel": str(int(Nivel.TITULAR)),
            "razao_social": "Concorrente SA"})

        assert Empresa.objects.count() == antes
        assert Usuario.objects.get(email="outro@teste.com").nivel != Nivel.TITULAR


class TestCriarSaiuDaTelaDeEmpresas:
    """**Um caminho só para criar empresa**, e ele passa pelo titular.

    A tela de Empresas tinha o próprio "Nova empresa". Com uma conta por
    empresa, o que ela criava era uma empresa SEM DONO — ninguém a abre, ela
    fica na lista sem nada explicando o que falta nela, e o titular que
    deveria ser o dono nunca soube que ela existe.

    Dois caminhos para o mesmo cadastro também divergem: o campo que entrasse
    num apareceria no outro semanas depois, ou nunca.
    """

    def test_a_tela_de_empresas_nao_oferece_criar(self, mw5):
        html = logado(mw5).get(reverse("empresa")).content.decode()

        assert "Nova empresa" not in html
        assert 'data-open-modal="empresa-criar"' not in html

    def test_o_post_de_criar_na_tela_de_empresas_nao_cria(self, mw5):
        """Esconder o botão não é fechar o caminho — o POST vem do cliente, e
        a rota continua de pé para editar e remover."""
        antes = Empresa.objects.count()

        logado(mw5).post(reverse("empresa"), {
            "acao": "criar", "razao_social": "Pela Porta dos Fundos Ltda"})

        assert Empresa.objects.count() == antes
        assert not Empresa.objects.filter(
            razao_social="Pela Porta dos Fundos Ltda").exists()


class TestOModalJaAbreEmTitular:
    """A MW5 abre esta tela para abrir CONTA, e o cadastro já vem pronto para
    isso: o nível marcado é Titular, e com ele o bloco da empresa aparece.

    Vinha marcando "Comprador" — o menor nível —, e aí o bloco da empresa
    nascia escondido: quem ia cadastrar um titular precisava primeiro
    descobrir que existia um seletor a mexer.
    """

    def _caixa_de_nivel(self, html: str) -> str:
        import re

        caixas = re.findall(r'<select[^>]*name="nivel".*?</select>', html,
                            re.S)
        assert caixas, "a caixa de nível não apareceu"
        return caixas[0]

    def test_a_caixa_ja_vem_em_titular(self, mw5):
        html = logado(mw5).get(reverse("usuarios")).content.decode()

        caixa = self._caixa_de_nivel(html)
        marcada = [l for l in caixa.splitlines() if "selected" in l]
        assert marcada, "nenhuma opção vem marcada"
        assert f'value="{int(Nivel.TITULAR)}"' in marcada[0], marcada[0]

    def test_o_master_nao_e_o_padrao(self, mw5):
        """Ele está na lista — a MW5 é uma equipe —, mas um padrão que
        concede o nível mais alto é o tipo de descuido que só aparece
        depois."""
        caixa = self._caixa_de_nivel(
            logado(mw5).get(reverse("usuarios")).content.decode())
        marcada = [l for l in caixa.splitlines() if "selected" in l][0]

        assert f'value="{int(Nivel.MASTER)}"' not in marcada

    def test_o_titular_nao_ve_caixa_de_nivel(self, mw5, db):
        """O titular cadastra membros da conta dele e não escolhe nível
        (14/09/2026): o que cada um faz vem do cargo da alocação."""
        from contas.fabrica import aplicar

        titular = Usuario.objects.create_user(
            email="titular@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        Empresa.objects.create(razao_social="Normadin", dono=titular)
        aplicar(titular, Nivel.TITULAR)

        html = logado(titular).get(reverse("usuarios")).content.decode()
        assert 'name="nivel"' not in html


class TestOBlocoEscondidoNaoTrancaOEnvio:
    """**Um `required` invisível trava o formulário inteiro.**

    Achado ao criar um VENDEDOR: o bloco da empresa some pelo script, mas o
    `razao_social` continuava `required`, e o navegador recusava a submissão
    com "An invalid form control with name='razao_social' is not focusable" —
    ele não consegue focar um campo escondido para explicar o que falta.
    Quem tentava criar um vendedor ficava preso numa tela sem nada dizendo o
    que houve.

    Quem RECUSA continua sendo o servidor, e a regra lá é outra e mais certa:
    sem razão social, o titular nasce sem empresa.
    """

    def test_nenhum_campo_da_empresa_e_required(self, mw5):
        import re

        html = logado(mw5).get(reverse("usuarios")).content.decode()
        campos = re.findall(r'<input[^>]*name="razao_social"[^>]*>', html)

        assert campos, "o campo da empresa sumiu do modal"
        for campo in campos:
            assert "required" not in campo, campo

    def test_o_membro_e_criado_sem_dados_de_empresa(self, mw5):
        """O caso que estourava: nível abaixo de titular, sem empresa junto."""
        from contas.models import Nivel

        logado(mw5).post(reverse("usuarios"), {
            "acao": "criar", "nome": "Vera Vendedora",
            "email": "vera@teste.com", "nivel": str(int(Nivel.MEMBRO))})

        vera = Usuario.objects.get(email="vera@teste.com")
        assert vera.nivel == Nivel.MEMBRO
        assert not Empresa.objects.filter(dono=vera).exists()

    def test_a_tela_de_empresas_continua_exigindo(self, mw5):
        """O `required` saiu do formulário EMBUTIDO, não do de Empresas: lá
        editar sem razão social é erro, e a tela diz isso antes da viagem."""
        import re

        alvo = Empresa.objects.create(razao_social="Tem Nome Ltda")
        html = logado(mw5).get(reverse("empresa")).content.decode()
        campos = re.findall(r'<input[^>]*name="razao_social"[^>]*>', html)

        assert campos, "o campo sumiu da tela de Empresas"
        assert any("required" in c for c in campos), (
            f"nenhum campo exigido em {len(campos)} encontrados (#{alvo.pk})")


