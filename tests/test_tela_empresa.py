"""A tela de Empresas: o cadastro de clientes deste portal.

Era "um formulário, uma linha, sem tabela nenhuma" — herdado do KRONOS.net,
onde a empresa é dado da instalação. Aqui a instalação é uma só, da MW5, e as
empresas são os clientes dela: a tela virou cadastro, com criar, editar,
trocar a senha do banco e remover.

Um teste chamado `test_nunca_cria_uma_segunda_linha` morava aqui e provava
exatamente o CONTRÁRIO do que este produto quer. Ficou no lugar de
`test_criar_cria_uma_nova`, logo abaixo — a mesma tela, a promessa invertida.
"""

import os

import pytest
from django.contrib.auth.models import Permission
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from tests.conftest import abrir_conta, empresa_do_teste, matriz_do_teste, por_na_conta

SENHA = "segredo-de-teste"


@pytest.fixture
def admin_do_cliente(db):
    """Um usuário COMUM com `empresa.editar` — não um superusuário. Com
    superusuário, tudo passaria por acidente.

    **Com `Acesso` e vínculo**, porque é isso que um admin de verdade é: a
    permissão abre a ROTA, o vínculo decide QUAIS empresas ele enxerga. Sem o
    vínculo a tela sai vazia — e é o comportamento certo, provado em
    `TestOAdminSoVeAsEmpresasDele`."""
    from contas.models import Nivel
    from plataforma.models import Empresa

    pessoa = Usuario.objects.create_user(email="admin@teste.com", password=SENHA)
    pessoa.user_permissions.add(Permission.objects.get(codename="empresa_editar"))
    pessoa.nivel = Nivel.MASTER
    pessoa.save(update_fields=["nivel"])
    por_na_conta(pessoa, empresa_do_teste())
    return pessoa


@pytest.fixture
def cliente_admin(admin_do_cliente):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "admin@teste.com", "senha": SENHA})
    return c


class TestQuemEntra:
    def test_o_admin_com_a_permissao_abre(self, cliente_admin):
        assert cliente_admin.get(reverse("empresa")).status_code == 200

    def test_usuario_comum_nao_descobre_que_a_tela_existe(self, db):
        Usuario.objects.create_user(email="comum@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "comum@teste.com", "senha": SENHA})
        assert c.get(reverse("empresa")).status_code == 404

    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("empresa"))
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_modulo_desligado_e_404_mesmo_com_a_permissao(self, cliente_admin, db):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="empresa").update(ativo=False)
        assert cliente_admin.get(reverse("empresa")).status_code == 404


class TestALista:
    def test_mostra_a_empresa_que_existe(self, cliente_admin):
        """Era `test_mostra_os_dados_ja_semeados`: a tela abria com a empresa
        que o `post_migrate` criava, chamada literalmente "Empresa".

        A semeadura acabou em 09/09/2026 (ver
        `tests/test_instalacao_nasce_sem_empresa.py`), então o teste cria a
        sua. A pergunta continua a mesma: a lista da MW5 mostra o que existe,
        e não um formulário em branco.
        """
        from plataforma.models import Empresa

        Empresa.objects.create(razao_social="Normadin Ltda")
        html = cliente_admin.get(reverse("empresa")).content.decode()

        assert 'value="Normadin Ltda"' in html

    def test_salvar_grava_os_campos_e_audita(self, cliente_admin, db):
        from contas.models import RegistroDeAuditoria
        from plataforma.models import Empresa

        alvo = empresa_do_teste()
        cliente_admin.post(reverse("empresa"), {
            "acao": "salvar",
            "empresa": str(alvo.pk),
            "razao_social": "Transportes Aurora Ltda",
            "nome_fantasia": "Aurora",
            # CNPJ com o dígito verificador fechando (a validação do item 28
            # recusa o que não fecha — ver `plataforma.documentos`).
            "cnpj": "04.252.011/0001-10",
            "municipio": "Cuiabá",
            "uf": "MT",
        })

        alvo.refresh_from_db()
        assert alvo.razao_social == "Transportes Aurora Ltda"
        assert alvo.nome_fantasia == "Aurora"
        assert alvo.municipio == "Cuiabá"
        assert RegistroDeAuditoria.objects.filter(acao="empresa_editada").exists()

    def test_criar_cria_uma_nova(self, cliente_admin, db):
        """Esta tela já criou, parou de criar e voltou a criar — e as três
        razões estão certas.

        Enquanto a empresa era dado da instalação, o teste garantia que um
        segundo POST NÃO criava uma segunda linha. Depois passou a criar,
        porque são os clientes do portal. Em 09/09/2026 parou: a conta tinha
        UMA empresa, que nascia no cadastro do titular. Em 17/09/2026 a conta
        passou a ter várias, e a segunda precisa nascer em algum lugar — aqui,
        e só para a MW5 (`TestAMW5CriaEmpresaDeNovo`).
        """
        from plataforma.models import Empresa

        antes = Empresa.objects.count()
        cliente_admin.post(reverse("empresa"),
                           {"acao": "criar", "razao_social": "Cliente Novo Ltda"})

        assert Empresa.objects.count() == antes + 1
        assert Empresa.objects.filter(razao_social="Cliente Novo Ltda").exists()

    def test_razao_social_vazia_e_recusada_com_frase_na_tela(self, cliente_admin, db):
        from plataforma.models import Empresa

        alvo = _nova("Tinha Nome Ltda")
        resposta = cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk), "razao_social": "  "})

        alvo.refresh_from_db()
        assert alvo.razao_social == "Tinha Nome Ltda"
        assert "Informe a razão social." in resposta.content.decode()

    def test_remover_empresa_com_filial_e_recusado_com_frase_na_tela(
            self, cliente_admin, db):
        """A recusa vem do banco (`PROTECT`), e não de uma checagem que uma
        rota nova poderia esquecer de repetir.

        A frase mudou junto com a causa. Antes ela era fixa — "tem filial
        cadastrada... apague as filiais dela primeiro" — e a view chutava:
        `Filial` era, em agosto, a única tabela apontando para `Empresa`. Hoje
        são dezesseis. Agora a frase NOMEIA o que segura, e é isso que este
        teste passou a exigir: "não pode ser removida" passaria com a mensagem
        velha, que citava filiais inexistentes.
        """
        from plataforma.models import Empresa, Filial

        com_filial = matriz_do_teste().empresa
        resposta = cliente_admin.post(reverse("empresa"),
                                      {"acao": "remover", "empresa": str(com_filial.pk)})

        corpo = resposta.content.decode()
        assert Empresa.objects.filter(pk=com_filial.pk).exists()
        assert "Não dá para remover" in corpo
        assert "filia" in corpo.lower(), (
            "a frase precisa nomear o que segura, e aqui é filial")

    def _com_alocacoes(self, razao, login, quantas):
        """Uma empresa segurada por ALOCAÇÕES, além da Matriz com que nasce."""
        from contas.models import Alocacao, Cargo, Nivel, Usuario
        from plataforma.models import Empresa

        empresa = Empresa.objects.create(razao_social=razao)
        titular = abrir_conta(empresa, login)
        empresa.refresh_from_db()
        cargo = Cargo.objects.get(conta=titular, nome="vendedor")
        for n in range(quantas):
            pessoa = Usuario.objects.create_user(
                email=f"{login}-{n}@teste.com", password="x",
                nivel=Nivel.MEMBRO, dono=titular)
            Alocacao.objects.create(pessoa=pessoa, empresa=empresa, cargo=cargo)
        return empresa

    def test_a_frase_nomeia_o_que_REALMENTE_segura(self, cliente_admin, db):
        """O caso que produziu esta correção: uma empresa segurada por OUTRA
        tabela recebia uma frase falando só de filiais, e mandando apagar o
        que não era o impedimento inteiro. No Portal de Vendas era o
        catálogo; na base, a alocação serve ao mesmo teste."""
        from plataforma.models import Empresa

        alvo = self._com_alocacoes("Com Gente Ltda", "conta-com-gente", 2)

        corpo = cliente_admin.post(
            reverse("empresa"),
            {"acao": "remover", "empresa": str(alvo.pk)}).content.decode()

        assert Empresa.objects.filter(pk=alvo.pk).exists()
        assert "2 alocações" in corpo, corpo[corpo.find("Não dá"):][:200]

    def test_a_frase_lista_TODAS_as_tabelas_que_seguram(self, cliente_admin, db):
        """E não só a primeira: quem lê precisa saber o tamanho do trabalho
        antes de começar. Descobrir mais um impedimento a cada tentativa é o
        jeito mais cansativo de apagar uma linha."""
        alvo = self._com_alocacoes("Cheia Ltda", "conta-cheia", 1)

        corpo = cliente_admin.post(
            reverse("empresa"),
            {"acao": "remover", "empresa": str(alvo.pk)}).content.decode()
        frase = corpo[corpo.find("Não dá para remover"):][:220]
        for pedaco in ("filia", "aloca"):
            assert pedaco in frase.lower(), (pedaco, frase)


class TestOAdminSoVeAsEmpresasDele:
    """O vazamento que esta tela tinha, e por que ele passou tanto tempo:
    ela foi escrita quando a empresa era UMA linha por instalação — não havia
    o que recortar. Depois que a empresa virou cadastro de várias, a grade
    continuou mostrando todas.

    O sintoma na tela era explícito e ninguém leu: o seletor do cabeçalho
    mostrava duas empresas e a lista abaixo dele mostrava quatro.
    """

    @pytest.fixture
    def cenario(self, db):
        from contas.models import Nivel
        from plataforma.models import Empresa

        alfa = Empresa.objects.create(razao_social="Alfa Ltda",
                                      host="oracle.alfa.local")
        beta = Empresa.objects.create(razao_social="Beta Ltda",
                                      host="oracle.beta.local")

        ana = Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        ana.user_permissions.add(
            Permission.objects.get(codename="empresa_editar"))
        ana.nivel = Nivel.TITULAR
        ana.save(update_fields=["nivel"])
        por_na_conta(ana, alfa)

        cliente = Client()
        cliente.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        return {"cliente": cliente, "alfa": alfa, "beta": beta}

    def test_a_lista_mostra_so_as_dele(self, cenario):
        html = cenario["cliente"].get(reverse("empresa")).content.decode()
        assert "Alfa Ltda" in html
        assert "Beta Ltda" not in html

    def test_o_host_da_outra_nao_vaza(self, cenario):
        """O host do Oracle é o que mais dói vazar nesta tela: é o endereço
        do banco do cliente do concorrente."""
        html = cenario["cliente"].get(reverse("empresa")).content.decode()
        assert "oracle.beta.local" not in html

    def test_a_exportacao_tambem_recorta(self, cenario):
        """Uma tela que recorta a lista e não recorta o Excel entrega pelo
        arquivo o que escondeu na tela."""
        resposta = cenario["cliente"].get(reverse("empresa"),
                                          {"formato": "impressao"})
        conteudo = resposta.content.decode()
        assert "Alfa Ltda" in conteudo
        assert "Beta Ltda" not in conteudo

    def test_editar_a_empresa_de_outro_admin_nao_acha(self, cenario):
        cenario["cliente"].post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(cenario["beta"].pk),
            "razao_social": "Invadida"})
        cenario["beta"].refresh_from_db()
        assert cenario["beta"].razao_social == "Beta Ltda"

    def test_o_titular_nao_cria_empresa(self, cenario):
        """Criar uma empresa é criar um INQUILINO, e isso é da MW5.

        A recusa mudou de forma em 09/09/2026: não é mais uma frase dizendo
        "é da MW5" — é que esta tela não cria mais para ninguém. A empresa
        nasce no cadastro do titular, e quem cadastra titular é só a MW5.
        """
        from plataforma.models import Empresa

        cenario["cliente"].post(reverse("empresa"), {
            "acao": "criar", "razao_social": "Gama Ltda"})
        assert not Empresa.objects.filter(razao_social="Gama Ltda").exists()

    def test_o_admin_nao_remove_empresa(self, cenario):
        from plataforma.models import Empresa

        cenario["cliente"].post(reverse("empresa"), {
            "acao": "remover", "empresa": str(cenario["alfa"].pk)})
        assert Empresa.objects.filter(pk=cenario["alfa"].pk).exists()

    def test_a_tela_nao_oferece_o_que_ele_nao_pode(self, cenario):
        """Botão que abre um modal para depois recusar é um caminho que só
        existe para terminar em erro."""
        html = cenario["cliente"].get(reverse("empresa")).content.decode()
        assert "Nova empresa" not in html
        assert "empresa-criar" not in html


def _nova(razao_social: str, **campos):
    """A empresa, criada DIRETO no banco.

    Criar pela tela de Empresas deixou de existir em 09/09/2026: a empresa
    nasce no cadastro do titular, junto com a conta. Os testes deste arquivo
    são sobre o FORMULÁRIO dela — senha cifrada, em branco mantém, razão
    social obrigatória —, e essas regras valem na edição do mesmo jeito.
    Passar pela tela de Usuários só para chegar aqui provaria o cadastro de
    usuário, não o formulário de empresa.
    """
    from plataforma.models import Empresa

    return Empresa.objects.create(razao_social=razao_social, **campos)


@pytest.mark.django_db
class TestASenhaDoBancoNoProprioFormulario:
    """A senha do banco do cliente deixou de exigir um segundo modal.

    Ela morava separada, e o motivo era bom: só entra por `definir_senha()`,
    que cifra, e um campo solto no meio dos outros convidava a atribuir a
    coluna direto. O que estava errado era a conclusão — a trava não é a tela
    separada, é o `clean()` do model, que recusa qualquer valor sem o prefixo
    do Fernet. Com ela de pé, o campo pode morar no formulário, e quem
    cadastra deixa de precisar salvar, procurar a linha e abrir outro modal
    para completar o que já tinha em mãos.
    """

    @pytest.fixture
    def com_chave(self, monkeypatch):
        from plataforma.cifra import VARIAVEL, gerar_chave

        monkeypatch.setenv(VARIAVEL, gerar_chave())

    def test_a_senha_grava_cifrada_no_mesmo_post(self, cliente_admin, com_chave):
        from plataforma.models import Empresa

        nova = _nova("Com Senha Ltda")
        cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(nova.pk),
            "razao_social": "Com Senha Ltda",
            "host": "10.0.0.9", "senha": "segredo-do-cliente"})
        nova.refresh_from_db()
        assert nova.senha.startswith("gAAAAA"), (
            "gravou em texto claro — a senha não passou por definir_senha()")
        assert nova.senha_clara == "segredo-do-cliente"

    def test_em_branco_MANTEM_a_que_ja_existe(self, cliente_admin, com_chave):
        """A regra mudou de sentido junto com o lugar do campo.

        No modal separado, em branco APAGAVA — e fazia sentido lá, porque
        abrir aquele modal era um ato deliberado sobre a senha. Num formulário
        onde o campo aparece toda vez que alguém corrige o CEP, apagar por
        omissão destruiria a conexão de quem só queria arrumar o endereço.
        """
        from plataforma.models import Empresa

        alvo = _nova("Mantem Ltda")
        cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Mantem Ltda", "senha": "a-que-vale"})

        cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Mantem Ltda", "municipio": "Sorriso",
            "senha": ""})
        alvo.refresh_from_db()
        assert alvo.municipio == "Sorriso", "o resto do formulário gravou"
        assert alvo.senha_clara == "a-que-vale", "a senha foi apagada"

    def test_a_senha_nunca_volta_para_a_tela(self, cliente_admin, com_chave):
        """Nem em claro, nem cifrada. O campo vem sempre vazio, inclusive ao
        editar: o sistema não sabe devolvê-la, e um campo que mostrasse algo
        estaria mostrando outra coisa."""
        from plataforma.models import Empresa

        alvo = _nova("Segreda Ltda")
        cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Segreda Ltda", "senha": "nao-pode-vazar"})
        alvo.refresh_from_db()

        html = cliente_admin.get(reverse("empresa")).content.decode()
        assert "nao-pode-vazar" not in html
        assert alvo.senha not in html

    def test_sem_a_chave_da_instalacao_a_tela_EXPLICA(self, cliente_admin):
        """Sem `PORTAL_CHAVE_DE_CIFRAGEM`, `definir_senha` levanta
        `ImproperlyConfigured` — e isso subia até a página de erro: quem
        tentasse cadastrar uma empresa com senha via "Algo inesperado
        aconteceu" e ficava sem a empresa, porque o `atomic()` desfaz tudo.
        Erro de configuração da instalação não pode parecer defeito do sistema
        para quem está preenchendo um formulário."""
        from plataforma.cifra import VARIAVEL
        from plataforma.models import Empresa

        alvo = _nova("Sem Chave Ltda")

        os.environ.pop(VARIAVEL, None)
        resposta = cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Sem Chave Ltda", "senha": "x"})
        assert resposta.status_code == 200
        alvo.refresh_from_db()
        assert alvo.senha == "", "gravou a senha sem a chave da instalação"
        assert VARIAVEL in resposta.content.decode()

    def test_sem_senha_nenhuma_a_empresa_salva_igual(self, cliente_admin):
        """A conexão pode ficar em branco — a empresa entra no cadastro antes
        de ela existir. Sem este caminho, a chave de cifragem viraria
        pré-requisito para mexer em qualquer empresa."""
        alvo = _nova("Sem Conexao Ltda")

        cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Sem Conexao Ltda", "municipio": "Toledo"})

        alvo.refresh_from_db()
        assert alvo.municipio == "Toledo"


@pytest.mark.django_db
class TestOModalEmDuasColunas:
    def test_cadastro_a_esquerda_conexao_a_direita(self, cliente_admin):
        html = cliente_admin.get(reverse("empresa")).content.decode()
        assert "ep-duas" in html and "ep-lado" in html
        for titulo in ("Identidade", "Endereço", "Conexão com o Kronos"):
            assert titulo in html

    def test_o_modal_separado_de_senha_nao_existe_mais(self, cliente_admin):
        html = cliente_admin.get(reverse("empresa")).content.decode()
        assert "Gravar senha" not in html
        assert 'title="Senha do banco"' not in html


@pytest.mark.django_db
class TestOOlhoDaSenhaDoBanco:
    """A senha gravada pode ser VISTA — e só por uma rota, sob demanda.

    A alternativa óbvia era mandar o valor no `value` do campo. Ela é errada
    por um motivo que não aparece olhando o modal: a lista de empresas desenha
    um modal de edição POR LINHA. A senha embutida poria a credencial do
    Oracle de todos os clientes no código-fonte de cada carregamento da
    página — em `Ctrl+U`, no cache do navegador, em qualquer captura de tela
    da lista, e no histórico de quem só queria conferir um CEP.
    """

    @pytest.fixture
    def com_senha(self, cliente_admin, monkeypatch):
        from plataforma.cifra import VARIAVEL, gerar_chave
        from plataforma.models import Empresa

        monkeypatch.setenv(VARIAVEL, gerar_chave())
        alvo = _nova("Com Olho Ltda", host="oracle.local")
        cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Com Olho Ltda",
            "host": "oracle.local", "senha": "segredo-do-oracle"})
        alvo.refresh_from_db()
        return alvo

    def test_a_rota_devolve_a_senha_em_claro(self, cliente_admin, com_senha):
        resposta = cliente_admin.get(
            reverse("empresa_senha", args=[com_senha.pk]))
        assert resposta.status_code == 200
        assert resposta.json()["senha"] == "segredo-do-oracle"

    def test_a_senha_NAO_vai_no_html_da_lista(self, cliente_admin, com_senha):
        """O teste que justifica a rota existir."""
        html = cliente_admin.get(reverse("empresa")).content.decode()
        assert "segredo-do-oracle" not in html
        assert com_senha.senha not in html, "nem o texto cifrado"

    def test_ver_a_senha_fica_na_trilha(self, cliente_admin, com_senha):
        """Ler credencial é um ATO, não uma consulta: quem viu e quando é a
        pergunta que se faz depois de um vazamento, e ela precisa ter
        resposta."""
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        antes = RegistroDeAuditoria.objects.count()
        cliente_admin.get(reverse("empresa_senha", args=[com_senha.pk]))
        assert RegistroDeAuditoria.objects.count() == antes + 1
        registro = RegistroDeAuditoria.objects.order_by("-id").first()
        assert registro.acao == ACOES.SENHA_DO_BANCO_VISTA
        assert "Com Olho" in registro.alvo

    def test_a_senha_do_VIZINHO_da_404(self, com_senha, db):
        """404 e não 403: 403 confirmaria que aquele id existe.

        É a mesma regra do produto do vizinho no catálogo, e aqui vale mais:
        do outro lado do id está a credencial do banco de outro cliente.

        O ator NÃO pode ser `cliente_admin`: aquela fixture cria um MASTER, e
        master alcança todas as empresas por desenho — o teste passaria por
        acidente, provando nada. Aqui é um gestor comum, vinculado a uma
        empresa só, que é o caso em que o vazamento aconteceria.
        """
        from contas.models import Nivel
        from plataforma.models import Empresa

        minha = Empresa.objects.create(razao_social="A Minha Ltda")
        gestor = Usuario.objects.create_user(
            email="gestor.vizinho@teste.com", password=SENHA)
        gestor.user_permissions.add(
            Permission.objects.get(codename="empresa_editar"))
        gestor.nivel = Nivel.TITULAR
        gestor.save(update_fields=["nivel"])
        por_na_conta(gestor, minha)

        cliente = Client()
        cliente.post(reverse("entrar"),
                     {"usuario": "gestor.vizinho@teste.com", "senha": SENHA})
        # A dele abre...
        assert cliente.get(
            reverse("empresa_senha", args=[minha.pk])).status_code == 200
        # ...e a do vizinho não existe para ele.
        resposta = cliente.get(reverse("empresa_senha", args=[com_senha.pk]))
        assert resposta.status_code == 404
        assert "segredo-do-oracle" not in resposta.content.decode()

    def test_sem_senha_gravada_devolve_vazio_e_nao_registra(
            self, cliente_admin, db):
        """Não é acesso a credencial nenhuma — registrar encheria a trilha de
        linhas que não dizem nada, e trilha cheia de ruído é trilha que
        ninguém lê."""
        from contas.models import RegistroDeAuditoria
        from plataforma.models import Empresa
        from contas.alcance import usuario_de

        # A empresa nasce da conta de quem a criou. `cliente_admin` é um
        # MASTER (ver a fixture), e o MASTER alcança todas sem vínculo — não
        # há o que ligar aqui, e ligar seria dar conta à MW5.
        vazia = Empresa.objects.create(razao_social="Vazia Ltda")

        antes = RegistroDeAuditoria.objects.count()
        resposta = cliente_admin.get(reverse("empresa_senha", args=[vazia.pk]))
        assert resposta.json()["senha"] == ""
        assert RegistroDeAuditoria.objects.count() == antes

    def test_quem_nao_pode_editar_empresa_nao_ve(self, com_senha, db):
        """A rota é guardada pela MESMA permissão que já permite TROCAR a
        senha. Quem pode trocar já pode tornar a antiga inútil — ver não é
        escalada. Quem não pode nem isso, não chega aqui."""
        from contas.models import Nivel

        Usuario.objects.create_user(
            email="curioso@teste.com", password=SENHA,
            nivel=Nivel.MEMBRO)
        cliente = Client()
        cliente.post(reverse("entrar"),
                     {"usuario": "curioso@teste.com", "senha": SENHA})
        resposta = cliente.get(reverse("empresa_senha", args=[com_senha.pk]))
        assert resposta.status_code in (302, 403, 404)
        assert "segredo-do-oracle" not in resposta.content.decode()

    def test_o_olho_so_aparece_para_quem_tem_senha(self, cliente_admin,
                                                   com_senha):
        """Um olho que revela vazio é um botão que mente."""
        from plataforma.models import Empresa

        sem = Empresa.objects.create(razao_social="Sem Senha Ltda")
        html = cliente_admin.get(reverse("empresa")).content.decode()
        assert f'data-ep-senha="{com_senha.pk}"' in html
        assert f'data-ep-senha="{sem.pk}"' not in html


@pytest.mark.django_db
class TestOTitularVeAEmpresaDele:
    """O titular vê a TABELA das empresas da conta dele, como em toda outra
    tela de cadastro desta casa.

    **É a segunda vez que esta tela troca de forma, e as duas razões estão
    certas.** Em 09/09 ela virou formulário direto: com uma linha só, a tabela
    é busca e paginação sobre um registro, e são três passos até o campo que a
    pessoa veio mudar. Em 10/09 voltou a ser tabela, por decisão de quem usa —
    o que pesou mais foi o resto do sistema: toda tela de cadastro aqui é
    tabela com filtro, ordenação e paginação (R46), e uma que foge disso
    obriga quem já aprendeu o padrão a aprender uma exceção.

    O que NÃO mudou nas duas idas: ele não cria e não remove. A primeira
    empresa nasce no cadastro dele, as outras a MW5 cadastra (17/09/2026), e
    remover é da MW5.
    """

    @pytest.fixture
    def titular(self, db):
        from contas.fabrica import aplicar
        from contas.models import Nivel
        from plataforma.models import Empresa

        pessoa = Usuario.objects.create_user(
            email="titular@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        Empresa.objects.create(razao_social="Normadin Ltda", dono=pessoa)
        aplicar(pessoa, Nivel.TITULAR)
        c = Client()
        c.post(reverse("entrar"),
               {"usuario": "titular@teste.com", "senha": SENHA})
        return c

    def test_ele_ve_a_tabela_com_a_empresa_dele(self, titular):
        html = titular.get(reverse("empresa")).content.decode()

        assert "<table" in html, "a tabela sumiu"
        assert "Normadin Ltda" in html

    def test_a_tabela_dele_tem_uma_linha_so(self, titular, db):
        """A empresa da conta, e nenhuma outra. É o inquilino, e é a metade
        que mais importa desta tela: a tabela de um titular nunca pode
        mostrar o cliente do lado."""
        from plataforma.models import Empresa

        Empresa.objects.create(razao_social="Do Vizinho Ltda")

        html = titular.get(reverse("empresa")).content.decode()

        assert "Normadin Ltda" in html
        assert "Do Vizinho" not in html

    def test_ele_nao_ve_a_conexao_com_o_kronos(self, titular):
        """Host, banco, usuário e senha do Oracle são a ligação da INSTALAÇÃO
        com o Kronos: quem a monta é a MW5, e quem erra ali derruba a carga do
        catálogo de um cliente. O titular edita os dados da empresa dele; a
        conexão não é dado dele."""
        html = titular.get(reverse("empresa")).content.decode()

        assert 'name="host"' not in html
        assert 'name="senha"' not in html
        assert "Conexão com o Kronos" not in html

    def test_o_post_forjado_dele_nao_troca_o_host(self, titular, db):
        """A trava de verdade: esconder o campo evita o engano, mas o POST
        forjado chegaria igual — e trocar o host é apontar a carga do
        catálogo do cliente para outro banco."""
        from plataforma.models import Empresa

        empresa = Empresa.objects.get(razao_social="Normadin Ltda")
        empresa.host = "kronos.normadin"
        empresa.save(update_fields=["host"])

        titular.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(empresa.pk),
            "razao_social": "Normadin Ltda",
            "host": "servidor.do.atacante", "porta": "1521",
            "banco": "OUTRO", "usuario": "invasor"})

        empresa.refresh_from_db()
        assert empresa.host == "kronos.normadin", (
            "o titular trocou o host da conexão por POST forjado")

    def test_o_post_forjado_dele_nao_troca_a_senha_do_banco(self, titular, db,
                                                            monkeypatch):
        """A senha entra por outra porta (`definir_senha`, que cifra), então
        ela precisa da mesma trava escrita duas vezes — uma por porta."""
        from plataforma.cifra import VARIAVEL, gerar_chave
        from plataforma.models import Empresa

        monkeypatch.setenv(VARIAVEL, gerar_chave())
        empresa = Empresa.objects.get(razao_social="Normadin Ltda")
        antes = empresa.senha

        titular.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(empresa.pk),
            "razao_social": "Normadin Ltda", "senha": "trocada-por-ele"})

        empresa.refresh_from_db()
        assert empresa.senha == antes

    def test_ele_continua_editando_os_dados_da_empresa(self, titular, db):
        """A trava é da CONEXÃO, e não da tela: o que é dado dele continua
        sendo dele."""
        from plataforma.models import Empresa

        empresa = Empresa.objects.get(razao_social="Normadin Ltda")

        titular.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(empresa.pk),
            "razao_social": "Normadin Peças Ltda", "municipio": "Cascavel"})

        empresa.refresh_from_db()
        assert empresa.razao_social == "Normadin Peças Ltda"
        assert empresa.municipio == "Cascavel"

    def test_a_mw5_continua_editando_a_conexao(self, cliente_admin, db):
        from plataforma.models import Empresa

        empresa = Empresa.objects.create(razao_social="Da MW5 Ltda")

        cliente_admin.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(empresa.pk),
            "razao_social": "Da MW5 Ltda", "host": "kronos.novo"})

        empresa.refresh_from_db()
        assert empresa.host == "kronos.novo"

    def test_ele_edita_pelo_lapis(self, titular):
        html = titular.get(reverse("empresa")).content.decode()

        assert 'name="razao_social"' in html, (
            "o modal de editar não foi montado")

    def test_ele_nao_remove(self, titular):
        """O botão não fica desabilitado: fica ausente. Um ícone que abre um
        modal para depois recusar é um caminho que só existe para terminar em
        erro."""
        html = titular.get(reverse("empresa")).content.decode()

        assert "remover" not in html.lower()

    def test_ele_nao_cria(self, titular):
        html = titular.get(reverse("empresa")).content.decode()

        assert "Nova empresa" not in html

    def test_a_conta_sem_empresa_recebe_uma_frase(self, db):
        """Estado que a migração `0008` produz de verdade: dois titulares
        disputavam a mesma empresa e o segundo ficou sem nenhuma. Sem a
        frase, ele abre a tela vazia e não tem como saber que o problema não
        é dele."""
        from contas.fabrica import aplicar
        from contas.models import Nivel

        orfao = Usuario.objects.create_user(
            email="orfao@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        aplicar(orfao, Nivel.TITULAR)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "orfao@teste.com",
                                   "senha": SENHA})

        html = c.get(reverse("empresa")).content.decode()

        assert "ainda não tem empresa" in html
        assert 'name="razao_social"' not in html

    def test_a_MW5_continua_vendo_a_lista(self, cliente_admin):
        """Ela atende VÁRIAS contas, e é para ela que a tabela com filtro e
        paginação existe. Tirar a lista dos dois seria trocar um problema por
        outro."""
        html = cliente_admin.get(reverse("empresa")).content.decode()

        assert "<table" in html


@pytest.mark.django_db
class TestAMW5CriaEmpresaDeNovo:
    """17/09/2026: com várias empresas por conta, "Nova empresa" volta — para
    a MW5, que é quem cadastra inquilino. A PRIMEIRA empresa continua nascendo
    no cadastro do titular; as outras se cadastram aqui."""

    @pytest.fixture
    def cenario(self, db):
        from contas.fabrica import aplicar
        from contas.models import Nivel
        from plataforma.models import Empresa

        mw5 = Usuario.objects.create_user(email="mw5-emp@teste.com", password=SENHA)
        mw5.user_permissions.add(
            Permission.objects.get(codename="empresa_editar"))
        mw5.nivel = Nivel.MASTER
        mw5.save(update_fields=["nivel"])
        titular = Usuario.objects.create_user(
            email="dono-emp@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        aplicar(titular, Nivel.TITULAR)
        alfa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "mw5-emp@teste.com", "senha": SENHA})
        dele = Client()
        dele.post(reverse("entrar"), {"usuario": "dono-emp@teste.com", "senha": SENHA})
        return {"mw5": c, "titular": titular, "alfa": alfa, "dele": dele}

    def test_a_mw5_ve_o_botao(self, cenario):
        html = cenario["mw5"].get(reverse("empresa")).content.decode()
        assert "Nova empresa" in html

    def test_a_mw5_cria_e_a_empresa_nasce_com_a_matriz(self, cenario):
        from plataforma.models import Empresa, Filial

        cenario["mw5"].post(reverse("empresa"), {
            "acao": "criar", "razao_social": "Segunda Ltda",
            "dono": str(cenario["titular"].pk)})
        nova = Empresa.objects.get(razao_social="Segunda Ltda")
        assert nova.dono_id == cenario["titular"].pk
        assert nova.conta_id == cenario["titular"].guid
        assert Filial.objects.filter(empresa=nova, e_matriz=True).exists()

    def test_a_empresa_pode_nascer_sem_dono_e_a_mw5_liga_depois(self, cenario):
        """Estado normal: a MW5 cadastra a empresa antes de existir a conta
        dela (o comentário de `Empresa.dono` diz isso desde sempre)."""
        from plataforma.models import Empresa

        cenario["mw5"].post(reverse("empresa"), {
            "acao": "criar", "razao_social": "Sem Dono Ltda"})
        assert Empresa.objects.get(razao_social="Sem Dono Ltda").dono_id is None

    def test_o_titular_continua_sem_criar(self, cenario):
        from plataforma.models import Empresa

        cenario["dele"].post(reverse("empresa"), {
            "acao": "criar", "razao_social": "Nao Deve Existir Ltda"})
        assert not Empresa.objects.filter(razao_social="Nao Deve Existir Ltda").exists()
        assert "Nova empresa" not in cenario["dele"].get(
            reverse("empresa")).content.decode()

    def test_a_tabela_do_titular_mostra_as_duas_empresas(self, cenario):
        from plataforma.models import Empresa

        Empresa.objects.create(razao_social="Beta Ltda", dono=cenario["titular"])
        html = cenario["dele"].get(reverse("empresa")).content.decode()
        assert "Alfa Ltda" in html and "Beta Ltda" in html
        assert "Empresas" in html


@pytest.mark.django_db
class TestOFluxoDaFilaDaEmpresa:
    """17/09/2026: a empresa escolhe o que acontece depois de lançar o
    atendimento — voltar ao fim da fila (o de sempre) ou ficar em espera."""

    @pytest.fixture
    def titular(self, db):
        from contas.fabrica import aplicar
        from contas.models import Nivel
        from plataforma.models import Empresa

        pessoa = Usuario.objects.create_user(
            email="dono-fluxo@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        Empresa.objects.create(razao_social="Normadin Ltda", dono=pessoa)
        aplicar(pessoa, Nivel.TITULAR)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "dono-fluxo@teste.com",
                                   "senha": SENHA})
        return c

    def test_o_padrao_e_o_fluxo_de_hoje(self, db):
        from plataforma.models import Empresa, FluxoDaFila

        nova = Empresa.objects.create(razao_social="Padrao Ltda")
        assert nova.fluxo_da_fila == FluxoDaFila.VOLTA

    def test_o_titular_troca_o_fluxo_pela_tela(self, titular):
        from plataforma.models import Empresa, FluxoDaFila

        alvo = Empresa.objects.get(razao_social="Normadin Ltda")
        titular.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Normadin Ltda", "fluxo_da_fila": "espera"})
        alvo.refresh_from_db()
        assert alvo.fluxo_da_fila == FluxoDaFila.ESPERA

    def test_valor_forjado_nao_troca_o_fluxo(self, titular):
        from plataforma.models import Empresa, FluxoDaFila

        alvo = Empresa.objects.get(razao_social="Normadin Ltda")
        titular.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Normadin Ltda", "fluxo_da_fila": "voar"})
        alvo.refresh_from_db()
        assert alvo.fluxo_da_fila == FluxoDaFila.VOLTA

    def test_a_tela_oferece_as_duas_opcoes(self, titular):
        html = titular.get(reverse("empresa")).content.decode()
        assert 'name="fluxo_da_fila"' in html
        assert "Volta para o fim da fila" in html and "Fica em espera" in html
