"""A tela de Usuários: onde o admin do cliente administra quem existe nesta
instalação, e em quais perfis está.

Os testes de fronteira (`TestAFronteiraComAMw5`) são os mais importantes
desta suíte inteira: são a prova de que esta tela — a mais sensível de toda a
entrega — não vira o meio de um admin do cliente cunhar a própria promoção,
em vinte instalações.
"""

import re

import pytest
from django.contrib.auth.models import Permission
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

SENHA = "segredo-de-teste"


def _senha_temporaria_de(html: str) -> str:
    """Extrai a senha temporária que a tela mostrou uma única vez.

    O texto é `Login "<login>": <senha>. Anote agora …` — a senha vem de
    `get_random_string`, sempre letras e dígitos, então parar no primeiro
    ponto depois dos dois-pontos é seguro: a senha em si nunca contém um. As
    aspas não entram no padrão porque o autoescape do template as vira
    `&#34;`, não `"` literal.
    """
    encontrado = re.search(r"Login [^:]*: ([A-Za-z0-9]+)\.", html)
    assert encontrado, f"não achei a senha temporária na tela: {html!r}"
    return encontrado.group(1)


@pytest.fixture(autouse=True)
def _todo_mundo_na_mesma_conta(db, monkeypatch):
    """Toda pessoa criada nestes testes nasce na MESMA conta.

    Estes testes são sobre as AÇÕES da tela (criar, editar, senha, ativar,
    remover), e foram escritos quando a instalação era de um cliente só e
    quem tinha a permissão administrava todo mundo. Neste produto o alcance
    exige vínculo — e um alvo sem vínculo simplesmente não existe para quem
    chama, que é a regra certa e está provada em
    `tests/test_usuarios_alcance.py`.

    Sem isto, cada teste daqui teria uma linha de `dar_acesso` repetida, e a
    primeira esquecida daria um vermelho que parece bug da tela e é falta de
    cadastro no teste.
    """
    from contas.models import GerenteDeUsuario

    from tests.conftest import dar_acesso

    original = GerenteDeUsuario.create_user

    def com_vinculo(self, *args, **kwargs):
        """O PRIMEIRO vira o Admin dono; os outros entram na conta dele.

        Era `dar_acesso(pessoa)` para todo mundo, o que promovia todos a
        ADMIN. Com uma conta por empresa isso parou de funcionar por um
        motivo que é a mudança em si: dois Admins não cabem na mesma
        empresa, então o segundo ficava sem conta — e sem conta ele não
        alcança ninguém, nem a si mesmo. A tela abria vazia.
        """
        from plataforma.models import Empresa

        from tests.conftest import por_na_conta

        pessoa = original(self, *args, **kwargs)
        empresa = Empresa.objects.first()
        if empresa is None:
            return pessoa
        if empresa.dono_id is None:
            dar_acesso(pessoa, empresas=[empresa])
        else:
            por_na_conta(pessoa, empresa)
        return pessoa

    monkeypatch.setattr(GerenteDeUsuario, "create_user", com_vinculo)


@pytest.fixture
def pessoa_admin(db):
    """A pessoa por trás de `admin_do_cliente`: um usuário COMUM com
    `usuarios.editar` — não um superusuário.

    A diferença é o ponto inteiro desta suíte: os testes de fronteira
    provam o que o admin do CLIENTE pode e não pode. Com superusuário, os
    seis passariam por acidente e a fronteira ficaria sem prova.
    """
    pessoa = Usuario.objects.create_user(email="admin@teste.com", password=SENHA)
    pessoa.user_permissions.add(Permission.objects.get(codename="usuarios_editar"))
    # Neste produto administrar gente exige dizer DE QUAL empresa — ver
    # `dar_acesso` em `tests/conftest.py`.
    from tests.conftest import dar_acesso

    dar_acesso(pessoa)
    return pessoa


@pytest.fixture
def mw5_logada(db):
    """Um `Client` logado como a MW5 — superusuária.

    Existe porque a fronteira desta tela passou a ter DOIS lados de verdade:
    o que o gestor do cliente faz (cadastrar gente da empresa dele) e o que
    só a MW5 faz (dizer o que essa gente pode). `admin_do_cliente` continua
    sendo o primeiro; esta é o segundo.
    """
    Usuario.objects.create_superuser(email="a-mw5@teste.com", password=SENHA)
    c = Client()
    c.post(reverse("entrar"), {"usuario": "a-mw5@teste.com", "senha": SENHA})
    return c


@pytest.fixture
def admin_do_cliente(pessoa_admin):
    """Um `Client` já logado como `pessoa_admin` — é ele que os testes do
    brief chamam diretamente (`admin_do_cliente.get(...)`)."""
    c = Client()
    c.post(reverse("entrar"), {"usuario": "admin@teste.com", "senha": SENHA})
    return c


@pytest.mark.django_db
class TestAFronteiraComAMw5:
    """A tela de Usuários é onde o admin do cliente trabalha. Se ela deixar
    escapar `is_superuser`, ele cunha a própria promoção — em vinte
    instalações. Estes testes são a fronteira inteira.
    """

    def test_o_formulario_nao_oferece_superusuario(self, admin_do_cliente):
        html = admin_do_cliente.get(reverse("usuarios")).content.decode()
        assert "is_superuser" not in html
        assert "is_staff" not in html
        assert "superusu" not in html.lower()

    def test_postar_superusuario_direto_nao_promove(self, admin_do_cliente, db):
        """A tela não oferece — mas o POST é do cliente, e ele pode inventar
        o campo. A view tem que ignorar."""
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Novo",
            "email": "novo@teste.com",
            "is_superuser": "true", "is_staff": "true",
        })
        novo = Usuario.objects.get(email="novo@teste.com")
        assert novo.is_superuser is False
        assert novo.is_staff is False

    def test_editar_alguem_nao_permite_promover(self, admin_do_cliente, db):
        alvo = Usuario.objects.create_user(email="alvo@teste.com", password=SENHA)
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Alvo",
            "is_superuser": "true",
        })
        alvo.refresh_from_db()
        assert alvo.is_superuser is False

    def test_o_usuario_da_mw5_nao_aparece_na_lista(self, admin_do_cliente):
        """Correção ao brief: `assert LOGIN not in html` não pode falhar
        nunca — toda página carrega `<script src=".../mw5.js">`
        (`nucleo/templates/layout/page.html:39`), então o literal "mw5"
        sempre está na página, tela nenhuma à parte. A prova de verdade é a
        linha da tabela e o alvo das ações: nem o login aparece como texto de
        célula, nem o pk da MW5 aparece como valor do campo oculto `id` que
        toda ação (editar, senha, ativar/desativar, remover) lê.

        Uma segunda correção sobre a própria correção: `f'value="{mw5.pk}"'`
        solto colide com o pk de qualquer OUTRA coisa numérica na página —
        aqui, uma opção de outra tabela cujo pk coincide por acaso com o da
        MW5 (ambos nascem 1 na base de teste). O campo que teria o pk da
        MW5 como alvo de ação se chama `id`; a asserção
        precisa mirar nesse nome para não estourar por coincidência de outra
        tabela."""
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        mw5 = Usuario.objects.get(email=EMAIL)
        html = admin_do_cliente.get(reverse("usuarios")).content.decode()
        assert ">mw5<" not in html
        assert f'name="id" value="{mw5.pk}"' not in html

    def test_o_admin_do_cliente_nao_desativa_a_mw5(self, admin_do_cliente):
        """Seria a forma de trancar a MW5 do lado de fora."""
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        mw5 = Usuario.objects.get(email=EMAIL)
        admin_do_cliente.post(reverse("usuarios"),
                              {"acao": "desativar", "id": str(mw5.pk)})
        mw5.refresh_from_db()
        assert mw5.is_active is True

    def test_o_admin_do_cliente_nao_remove_a_mw5(self, admin_do_cliente):
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        mw5 = Usuario.objects.get(email=EMAIL)
        admin_do_cliente.post(reverse("usuarios"),
                              {"acao": "remover", "id": str(mw5.pk)})
        assert Usuario.objects.filter(email=EMAIL).exists()


class TestQuemEntra:
    def test_o_admin_com_a_permissao_abre(self, admin_do_cliente):
        assert admin_do_cliente.get(reverse("usuarios")).status_code == 200

    def test_usuario_comum_nao_descobre_que_a_tela_existe(self, db):
        Usuario.objects.create_user(email="comum@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "comum@teste.com", "senha": SENHA})
        assert c.get(reverse("usuarios")).status_code == 404

    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("usuarios"))
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]


@pytest.mark.django_db
class TestALista:
    def test_busca_por_login(self, admin_do_cliente):
        Usuario.objects.create_user(email="joana@teste.com", password=SENHA)
        Usuario.objects.create_user(email="pedro@teste.com", password=SENHA)

        html = admin_do_cliente.get(reverse("usuarios"), {"f:login:contem": "joana"}) \
            .content.decode()
        assert ">joana@teste.com<" in html
        assert ">pedro@teste.com<" not in html

    def test_busca_por_nome(self, admin_do_cliente):
        Usuario.objects.create_user(
            email="joana@teste.com", password=SENHA, nome="Joana Silva")
        Usuario.objects.create_user(
            email="pedro@teste.com", password=SENHA, nome="Pedro Souza")

        html = admin_do_cliente.get(reverse("usuarios"), {"f:nome:contem": "Souza"}) \
            .content.decode()
        assert "Pedro Souza" in html
        assert "Joana Silva" not in html


@pytest.mark.django_db
class TestCriarEditarRemover:
    def test_editar_troca_o_nome(self, admin_do_cliente, db):
        alvo = Usuario.objects.create_user(
            email="alvo@teste.com", password=SENHA, nome="Nome Antigo")
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Nome Novo",
        })
        alvo.refresh_from_db()
        assert alvo.nome == "Nome Novo"

    def test_resetar_senha_mostra_uma_vez_e_derruba_a_antiga(
            self, admin_do_cliente, db):
        alvo = Usuario.objects.create_user(
            email="alvo@teste.com", password="senha-original")

        resposta = admin_do_cliente.post(
            reverse("usuarios"), {"acao": "senha", "id": str(alvo.pk)})
        html_com_a_senha = resposta.content.decode()
        senha_nova = _senha_temporaria_de(html_com_a_senha)

        # Não fica gravada em lugar nenhum: uma SEGUNDA visita à tela não
        # mostra a mesma senha de novo.
        segunda_visita = admin_do_cliente.get(reverse("usuarios")).content.decode()
        assert senha_nova not in segunda_visita

        senha_antiga_falha = Client().post(
            reverse("entrar"), {"usuario": "alvo@teste.com", "senha": "senha-original"})
        assert "Credenciais inválidas." in senha_antiga_falha.content.decode()

        senha_nova_funciona = Client().post(
            reverse("entrar"), {"usuario": "alvo@teste.com", "senha": senha_nova})
        assert senha_nova_funciona.status_code == 302

    def test_ativar_e_desativar(self, admin_do_cliente, db):
        alvo = Usuario.objects.create_user(email="alvo@teste.com", password=SENHA)
        assert alvo.is_active is True

        admin_do_cliente.post(
            reverse("usuarios"), {"acao": "desativar", "id": str(alvo.pk)})
        alvo.refresh_from_db()
        assert alvo.is_active is False

        admin_do_cliente.post(
            reverse("usuarios"), {"acao": "ativar", "id": str(alvo.pk)})
        alvo.refresh_from_db()
        assert alvo.is_active is True

    def test_remover(self, admin_do_cliente, db):
        alvo = Usuario.objects.create_user(email="alvo@teste.com", password=SENHA)
        admin_do_cliente.post(
            reverse("usuarios"), {"acao": "remover", "id": str(alvo.pk)})
        assert not Usuario.objects.filter(pk=alvo.pk).exists()

    def test_desativar_alguem_derruba_a_sessao_aberta_dela_na_hora(
            self, admin_do_cliente, db):
        """Já vale sozinho, porque `BackendDjango.buscar` roda a cada
        requisição (`contas/backend.py`) — mas sem este teste, ninguém prova
        que a tela de Usuários de fato chama a ação que aciona isso."""
        alvo = Usuario.objects.create_user(email="alvo@teste.com", password=SENHA)
        sessao_do_alvo = Client()
        sessao_do_alvo.post(reverse("entrar"), {"usuario": "alvo@teste.com", "senha": SENHA})
        assert sessao_do_alvo.get("/").status_code == 200

        admin_do_cliente.post(
            reverse("usuarios"), {"acao": "desativar", "id": str(alvo.pk)})

        resposta = sessao_do_alvo.get("/")
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]


@pytest.mark.django_db
class TestNaoTrancarAPropriaConta:
    """Requisito que o brief não escreve: o mesmo defeito de trancar a MW5
    do lado de fora, virado para dentro — desativar ou remover a própria
    conta deixaria a instalação sem ninguém para administrar gente."""

    def test_nao_desativa_a_propria_conta(self, admin_do_cliente, pessoa_admin):
        admin_do_cliente.post(
            reverse("usuarios"), {"acao": "desativar", "id": str(pessoa_admin.pk)})
        pessoa_admin.refresh_from_db()
        assert pessoa_admin.is_active is True

    def test_nao_remove_a_propria_conta(self, admin_do_cliente, pessoa_admin):
        admin_do_cliente.post(
            reverse("usuarios"), {"acao": "remover", "id": str(pessoa_admin.pk)})
        assert Usuario.objects.filter(pk=pessoa_admin.pk).exists()


@pytest.mark.django_db
class TestPermissaoSoDaMw5:
    """A caixa de Perfis saiu da tela (14/09/2026): o que a pessoa pode vem do
    cargo da alocação. O que continua valendo é a recusa do POST forjado.
    """

    def test_post_forjado_com_permissoes_nao_concede_nada(
            self, admin_do_cliente):
        """O titular escreve o formulário à mão com permissões dentro — o campo
        antigo `perfis` e um `permissoes` inventado —, e o servidor ignora os
        dois: membro não tem permissão direta, e a tela só grava cargo por
        alocação."""
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Laranja",
            "email": "laranja@teste.com",
            "perfis": ["1"], "permissoes": ["parametros_editar"],
        })
        criado = Usuario.objects.get(email="laranja@teste.com")
        assert not criado.user_permissions.exists()

    def test_a_filial_saiu_da_tela(self, mw5_logada):
        """Nem a caixa, nem a coluna, nem o filtro.

        Filial é herança do KRONOS.net, onde a instalação era de UM cliente.
        Aqui o inquilino é a empresa, e `usuario.filiais` não era lido em
        lugar nenhum fora desta tela. Deixar a coluna sem a caixa teria sido
        pior: uma coluna que ninguém consegue mais preencher.
        """
        html = mw5_logada.get(reverse("usuarios")).content.decode()
        assert 'name="filiais"' not in html
        assert "filtro_filial" not in html


@pytest.mark.django_db
class TestONivelTrazAPermissao:
    """O nível de titular (e o da MW5) traz as permissões de `contas/fabrica.py`
    como permissão direta. O de membro não traz nenhuma: a dele é a do cargo da
    alocação, e é isso que `tests/test_alocacoes_na_tela.py` prova.
    """

    def test_promover_a_titular_da_o_que_falta(self, mw5_logada, db):
        """**Era `promover_a_vendedor`.** O vendedor parou em 09/09/2026 e
        ficou com as mesmas chaves do comprador, então promover de um para o
        outro deixou de mudar coisa alguma — o teste passaria sem provar
        nada. Quem hoje ganha chave ao subir é o TITULAR, e só a MW5 concede
        esse nível.
        """
        from contas.models import Nivel

        mw5_logada.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Sobe",
            "email": "sobe@teste.com",
            "nivel": str(int(Nivel.MEMBRO)),
        })
        pessoa = Usuario.objects.get(email="sobe@teste.com")
        assert "empresa_editar" not in _diretas(pessoa)

        mw5_logada.post(reverse("usuarios"), {
            "acao": "editar", "id": str(pessoa.pk), "nome": "Sobe",
            "nivel": str(int(Nivel.TITULAR)),
        })
        assert "empresa_editar" in _diretas(pessoa)

    def test_rebaixar_RETIRA_o_que_o_nivel_antigo_dava(self, mw5_logada, db):
        """A metade que se esquece. Somar a permissão do nível novo sem tirar
        a do antigo tornaria a promoção reversível e o rebaixamento não — um
        titular rebaixado a membro continuaria editando o catálogo."""
        from contas.models import Nivel

        mw5_logada.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Desce",
            "email": "desce@teste.com",
            "nivel": str(int(Nivel.TITULAR)),
        })
        pessoa = Usuario.objects.get(email="desce@teste.com")
        assert "empresa_editar" in _diretas(pessoa)

        mw5_logada.post(reverse("usuarios"), {
            "acao": "editar", "id": str(pessoa.pk), "nome": "Desce",
            "nivel": str(int(Nivel.MEMBRO)),
        })
        # Membro não tem permissão direta nenhuma: a dele é a do cargo da
        # alocação. Rebaixar a membro apaga TODAS as diretas, não só as que
        # o nível de titular dava a mais.
        assert _diretas(pessoa) == set()

@pytest.mark.django_db
class TestQuemCadastraContinuaVendoQuemCadastrou:
    """Cadastrar não pode fazer a pessoa sumir na mesma requisição.

    `_vincular_a_conta` existe para isso — quem cadastra põe o cadastrado na
    conta dele —, e a ORDEM em que ela é chamada já anulou o próprio efeito
    uma vez: ela vinculava, e o `_salvar_acesso` logo depois desfazia. A
    pessoa era criada e sumia da lista na mesma requisição.

    Não aparecia em teste nenhum porque todo teste desta suíte criava gente
    por `create_user` (com `dar_acesso` no monkeypatch), e não pela tela.
    """

    def test_criado_sem_marcar_empresa_continua_na_lista(
            self, admin_do_cliente):
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Órfão",
            "email": "orfao@teste.com",
        })
        html = admin_do_cliente.get(reverse("usuarios")).content.decode()
        assert "orfao" in html

    def test_o_admin_nao_muda_ninguem_de_conta(self, admin_do_cliente, db):
        """Era `test_a_empresa_marcada_vence_a_herdada`, e a regra virou.

        Enquanto uma pessoa alcançava várias empresas, o que o Admin marcava
        na tela era escolha e vencia a herança. Agora só existe UMA conta
        para ele oferecer — a dele —, e um POST forjado com o id de outra
        precisa ser ignorado: mudar alguém de conta é mudá-lo de cliente, e
        leva junto tudo o que ele enxerga. Quem recusa é `_salvar_conta`, no
        servidor, e não a tela que não desenha o campo.
        """
        from contas.alcance import conta_de, usuario_de
        from contas.models import Nivel
        from plataforma.models import Empresa

        meu = usuario_de(Usuario.objects.get(email="admin@teste.com"))
        alheia = Usuario.objects.create_user(
            email="admin-de-fora@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        outra = Empresa.objects.create(razao_social="Segunda Ltda",
                                       dono=alheia)

        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Uma",
            "email": "soumadeuma@teste.com",
            "conta": str(alheia.pk),
        })

        nova = usuario_de(Usuario.objects.get(email="soumadeuma@teste.com"))
        assert conta_de(nova) == meu, "o POST forjado mudou a pessoa de conta"
        assert outra.dono_id == alheia.pk


@pytest.mark.django_db
class TestOEmailEObrigatorioNoCadastro:
    """Conta sem e-mail é conta sem como avisar ninguém de nada — nem de
    senha nova, nem de orçamento respondido. Exigir no cadastro impede a
    conta nascer torta; exigir na EDIÇÃO trancaria toda conta que nasceu
    antes desta regra, e trocar um nome passaria a depender de descobrir o
    e-mail de alguém.
    """

    def test_sem_email_nao_cria(self, admin_do_cliente):
        """Procura pelo NOME e não pelo e-mail: sem e-mail no POST não há
        endereço para procurar, e uma busca por um e-mail que ninguém mandou
        passaria mesmo se a view tivesse criado a pessoa."""
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Sem Mail",
        })
        assert not Usuario.objects.filter(nome="Sem Mail").exists()

    def test_email_torto_nao_cria(self, admin_do_cliente):
        """O `required` do HTML não vale nada contra um POST escrito à mão —
        quem exige é a view."""
        resposta = admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Torto",
            "email": "isto nao e um email",
        })
        assert not Usuario.objects.filter(nome="Torto").exists()
        assert "e-mail válido" in resposta.content.decode()

    def test_com_email_grava_o_email(self, admin_do_cliente):
        """Espaço em volta cai; o DOMÍNIO desce para minúsculas e a parte
        antes do @ não. Não é escolha desta tela — é o `normalize_email` do
        Django, e está afirmado aqui para ninguém "corrigir" achando defeito:
        o domínio não diferencia maiúscula, a caixa postal pode diferenciar.
        """
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Com Mail",
            "email": " Alguem@Exemplo.com ",
        })
        assert Usuario.objects.get(
            nome="Com Mail").email == "Alguem@exemplo.com"

    def test_editar_sem_email_nao_apaga_o_que_tinha(
            self, admin_do_cliente, db):
        """Vazio no editar é "não mexe", e não "apaga". Um formulário que
        limpa um dado por omissão apaga em silêncio o que ninguém pediu para
        apagar."""
        alvo = Usuario.objects.create_user(
            email="tinha@exemplo.com", password=SENHA)
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Tinha",
        })
        alvo.refresh_from_db()
        assert alvo.email == "tinha@exemplo.com"

    def test_editar_com_email_novo_troca(self, admin_do_cliente, db):
        alvo = Usuario.objects.create_user(
            email="velho@exemplo.com", password=SENHA)
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Troca",
            "email": "novo@exemplo.com",
        })
        alvo.refresh_from_db()
        assert alvo.email == "novo@exemplo.com"


@pytest.mark.django_db
class TestOLoginNaoSeDuplica:
    """O e-mail virou a PORTA, e duas pessoas não podem ter a mesma.

    **São duas travas, e as duas precisam existir.** Quem TRANCA é o banco:
    `unique=True` na coluna, e a constraint `email_unico_sem_caixa` para o
    mesmo endereço em outra caixa (o porquê está em
    `contas.models.Usuario.Meta`, e a prova de que ela é do BANCO está em
    `tests/test_usuario_model.py`). Nenhum caminho passa por baixo dela — nem
    shell, nem script de carga.

    Estes casos provam a outra metade, que é a razão de a view checar ANTES
    de gravar: chegar na tranca do banco por uma tela é HTTP 500 dentro do
    `atomic()`, na cara de quem estava só corrigindo um erro de digitação. Por
    isso cada caso afirma `status_code == 200` junto da frase — um 500 é
    exatamente o defeito que eles existem para pegar.
    """

    def test_editar_para_um_email_ja_cadastrado_e_recusado_com_frase(
            self, admin_do_cliente, db):
        """**Era HTTP 500.** `_acao_criar` já checava a colisão; `_acao_editar`
        gravava por cima e estourava `IntegrityError`."""
        Usuario.objects.create_user(
            email="ocupado@teste.com", password=SENHA)
        alvo = Usuario.objects.create_user(
            email="livre@teste.com", password=SENHA)

        resposta = admin_do_cliente.post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Alvo",
            "email": "ocupado@teste.com",
        })

        assert resposta.status_code == 200
        assert "Já existe alguém com o login" in resposta.content.decode()
        alvo.refresh_from_db()
        assert alvo.email == "livre@teste.com"

    def test_editar_mantendo_o_proprio_email_continua_valendo(
            self, admin_do_cliente, db):
        """A recusa não pode pegar a própria pessoa: a ficha reenvia o e-mail
        que já está lá, e isso não é duplicata nenhuma."""
        alvo = Usuario.objects.create_user(
            email="mesmo@teste.com", password=SENHA)

        resposta = admin_do_cliente.post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Nome Trocado",
            "email": "mesmo@teste.com",
        })

        # 302: salvou e voltou para a lista. Se a recusa pegasse a própria
        # pessoa, seria 200 com a frase — e ninguém trocaria mais um nome.
        assert resposta.status_code == 302
        alvo.refresh_from_db()
        assert alvo.nome == "Nome Trocado"
        assert alvo.email == "mesmo@teste.com"

    def test_criar_com_o_mesmo_email_em_outra_caixa_e_recusado(
            self, admin_do_cliente, db):
        """A coluna é única em caixa EXATA, então o banco deixaria as duas
        conviverem — e aí `get_by_natural_key`, que é insensível, acharia as
        DUAS e a tela de entrada estouraria com `MultipleObjectsReturned`.
        A porta é insensível; a recusa precisa ser também."""
        Usuario.objects.create_user(
            email="Ana@teste.com", password=SENHA)

        resposta = admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Outra Ana", "email": "ana@teste.com",
        })

        # 200 com a frase, e não o 500 que a constraint do banco daria se a
        # view deixasse o `INSERT` chegar até lá.
        assert resposta.status_code == 200
        assert "Já existe alguém com o login" in resposta.content.decode()
        assert Usuario.objects.filter(
            email__iexact="ana@teste.com").count() == 1

    def test_editar_para_o_mesmo_email_em_outra_caixa_e_recusado(
            self, admin_do_cliente, db):
        Usuario.objects.create_user(
            email="Bento@teste.com", password=SENHA)
        alvo = Usuario.objects.create_user(
            email="outro@teste.com", password=SENHA)

        resposta = admin_do_cliente.post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Alvo",
            "email": "bento@teste.com",
        })

        assert resposta.status_code == 200
        assert "Já existe alguém com o login" in resposta.content.decode()
        alvo.refresh_from_db()
        assert alvo.email == "outro@teste.com"


@pytest.mark.django_db
class TestAColunaDaListaEONivel:
    """A coluna é o NÍVEL: a pergunta que se faz olhando esta tabela é "o que
    essa pessoa é?" — a MW5, um titular ou um membro."""

    def _linhas(self, html) -> list:
        """As células de DADO de cada linha, sem a de ações.

        A coluna de Ações passou a ser a PRIMEIRA em 10/09/2026 (era a última
        no design system). Sem descartá-la aqui, todo índice deste arquivo
        andava um para o lado e os testes falavam de outra coluna — que foi
        exatamente o que aconteceu.
        """
        import re

        return [[re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<td.*?</td>", tr, re.S)][1:]
                for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S)[1:]]

    def _com_nivel(self, login, nivel):
        """O nível é gravado DEPOIS de criar, e não no `create_user`.

        `admin_do_cliente` monkeypatcheia `create_user` para dar vínculo de
        empresa a toda pessoa nova (ver a fixture lá em cima), e esse vínculo
        vem com nível. Passar o nível na criação faria o monkeypatch
        sobrescrevê-lo logo em seguida.
        """
        pessoa = Usuario.objects.create_user(
            email=f"{login}@teste.com", password=SENHA)
        pessoa.nivel = nivel
        pessoa.save(update_fields=["nivel"])
        return pessoa

    def test_a_coluna_mostra_o_nivel(self, admin_do_cliente, db):
        from contas.models import Nivel

        self._com_nivel("membro.x", Nivel.MEMBRO)
        html = admin_do_cliente.get(reverse("usuarios")).content.decode()
        assert "Nível" in html
        assert "Membro" in html
        assert ">Perfis<" not in html

    def test_quem_nunca_foi_configurado_aparece_como_membro(
            self, mw5_logada, db):
        """**O traço acabou, e o motivo é a troca do usuário.**

        A coluna escrevia "—" para quem não tinha linha de `Acesso`. Com
        `nivel` virando COLUNA da pessoa, com padrão, a linha sem nível deixou
        de existir — toda pessoa tem um, e o padrão é o menos poderoso.

        Só a MW5 vê essa linha: para quem não é superusuário, pessoa sem conta
        não aparece na lista (`pessoas_alcancadas`).
        """
        Usuario.objects.create_user(email="sem.acesso@teste.com", password=SENHA)
        linhas = self._linhas(
            mw5_logada.get(reverse("usuarios")).content.decode())
        dela = [l for l in linhas if len(l) > 2 and "sem.acesso" in l[1]]
        assert dela and dela[0][2] == "Membro", linhas

    def test_o_filtro_por_nivel_devolve_so_aquele_nivel(self, mw5_logada, db):
        """Olha as LINHAS da tabela, e não a página inteira: um login pode
        aparecer em outro lugar da página (a caixa de conta, por exemplo) e a
        asserção acusaria vazamento do filtro."""
        from contas.models import Nivel

        self._com_nivel("titular.y", Nivel.TITULAR)
        self._com_nivel("membro.y", Nivel.MEMBRO)
        linhas = self._linhas(mw5_logada.get(
            reverse("usuarios"),
            {"f:nivel:igual": str(int(Nivel.TITULAR))}).content.decode())
        logins = [l[1] for l in linhas if len(l) > 1]
        assert "titular.y@teste.com" in logins
        assert "membro.y@teste.com" not in logins

    def test_ordena_pela_hierarquia_e_nao_pelo_alfabeto(self, mw5_logada, db):
        """O NÚMERO do nível, e não o rótulo: "Master, Membro, Titular" é ordem
        alfabética, e não diz nada sobre quem manda em quem.

        **Os logins são escolhidos ao contrário de propósito.** O membro se
        chama `a.` e o titular `z.`, então a ordem alfabética é o INVERSO da
        hierarquia. Com nomes na mesma sequência dos dois critérios, este
        teste passava verde mesmo com a ordenação caindo no desempate por
        login — provado por mutação.
        """
        from contas.models import Nivel

        self._com_nivel("a.membro", Nivel.MEMBRO)
        self._com_nivel("z.titular", Nivel.TITULAR)
        crescente = self._linhas(mw5_logada.get(
            reverse("usuarios"), {"ordenar": "nivel"}).content.decode())
        niveis = [l[2] for l in crescente if len(l) > 2]
        assert niveis.index("Titular") < niveis.index("Membro"), niveis

        decrescente = self._linhas(mw5_logada.get(
            reverse("usuarios"), {"ordenar": "-nivel"}).content.decode())
        invertidos = [l[2] for l in decrescente if len(l) > 2]
        assert invertidos.index("Membro") < invertidos.index("Titular")

    def test_o_arquivo_exportado_leva_o_nivel(self, admin_do_cliente, db):
        from contas.models import Nivel

        self._com_nivel("exporta.eu", Nivel.MEMBRO)
        resposta = admin_do_cliente.get(reverse("usuarios"),
                                        {"exportar": "csv"})
        assert resposta.status_code == 200
        conteudo = b"".join(resposta.streaming_content).decode("utf-8-sig") \
            if resposta.streaming else resposta.content.decode("utf-8-sig")
        assert "Nível" in conteudo
        assert "Membro" in conteudo


@pytest.mark.django_db
class TestOPostCriaNaContaDeQuemCria:
    """O POST de criar não tem campo de conta para quem não é MW5: a pessoa
    nasce na conta de quem a criou, sem ninguém escolher nada."""

    def test_o_post_continua_sendo_o_de_sempre(self, admin_do_cliente):
        """A prova de que nada mudou do lado de cá: o mesmo POST cria o
        usuário na conta de quem o criou, sem ninguém escolher nada."""
        from contas.alcance import conta_de, usuario_de

        meu = usuario_de(Usuario.objects.get(email="admin@teste.com"))
        admin_do_cliente.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Por Ficha",
            "email": "porficha@teste.com",
        })
        nova = usuario_de(Usuario.objects.get(email="porficha@teste.com"))
        assert conta_de(nova) == meu

def _diretas(pessoa) -> set:
    """As permissões DIRETAS da pessoa, relidas do banco.

    `.all()` sobre a M2M de um objeto já carregado devolve o cache do
    prefetch anterior — e o teste passaria olhando o estado de antes do POST,
    que é o jeito silencioso de um teste destes não provar nada."""
    pessoa.refresh_from_db()
    return set(pessoa.user_permissions.values_list("codename", flat=True))


@pytest.mark.django_db
class TestASenhaPodeVirDigitada:
    """Antes, toda pessoa nova nascia com uma senha aleatória que a tela
    mostrava uma vez — e quem cadastra tinha de copiar e repassar.

    Na prática quem cadastra já combinou a senha com a pessoa (ou usa um
    padrão da casa), e o gerado virava um passo a mais entre o cadastro e o
    primeiro login. Pedido em 10/09/2026.
    """

    def _criar(self, cliente, senha=None, **extra):
        """`senha_da_pessoa` e não `senha`: o mesmo POST carrega o cadastro da
        empresa, que tem um campo `senha` — a do banco Oracle do cliente."""
        dados = {"acao": "criar", "nome": "Zeca", "email": "zeca@teste.com",
                 **extra}
        if senha is not None:
            dados["senha_da_pessoa"] = senha
        return cliente.post(reverse("usuarios"), dados)

    def test_o_formulario_oferece_o_campo(self, mw5_logada):
        html = mw5_logada.get(reverse("usuarios")).content.decode()
        assert 'name="senha_da_pessoa"' in html
        assert "Em branco, gera uma" in html

    def test_a_senha_digitada_e_a_que_entra(self, mw5_logada):
        self._criar(mw5_logada, senha="pinhao-2026")

        dele = Client()
        entrada = dele.post(reverse("entrar"),
                            {"usuario": "zeca@teste.com",
                             "senha": "pinhao-2026"})
        assert entrada.status_code == 302

    def test_com_senha_digitada_a_tela_nao_mostra_senha_nenhuma(
            self, mw5_logada):
        """Quem digitou já sabe a senha. Repeti-la numa faixa na tela é expor
        à toa o que já está na mão de quem cadastrou."""
        html = self._criar(mw5_logada, senha="pinhao-2026").content.decode()

        assert "pinhao-2026" not in html
        assert "Senha temporária gerada" not in html

    def test_em_branco_continua_gerando_e_mostrando(self, mw5_logada):
        """É o caminho de quem cadastra em lote e não quer inventar senha —
        e era o comportamento de antes."""
        html = self._criar(mw5_logada, senha="   ").content.decode()

        assert "Senha temporária gerada" in html
        senha = _senha_temporaria_de(html)
        dele = Client()
        assert dele.post(reverse("entrar"),
                         {"usuario": "zeca@teste.com",
                          "senha": senha}).status_code == 302

    def test_senha_curta_e_recusada_e_ninguem_e_criado(self, mw5_logada):
        """O mesmo mínimo da troca de senha em Meu Perfil: uma porta que
        aceita menos que a outra é a porta que vale."""
        from nucleo.permissoes import SENHA_MINIMA

        resposta = self._criar(mw5_logada, senha="123")

        assert "pelo menos" in resposta.content.decode()
        assert not Usuario.objects.filter(email="zeca@teste.com").exists()
        assert SENHA_MINIMA == 8

    def test_a_senha_da_pessoa_nao_se_mistura_com_a_do_banco(
            self, mw5_logada, monkeypatch):
        """**A colisão que a suíte pegou.** O cadastro de usuário e o da
        EMPRESA vão no mesmo POST, e a empresa tem um campo `senha` — a do
        banco Oracle do cliente. Com o mesmo nome nos dois, criar um titular
        com empresa gravava uma senha no lugar da outra: a pessoa entrava com
        a senha do Oracle, ou não entrava com nenhuma.
        """
        from contas.models import Nivel
        from plataforma.cifra import VARIAVEL, gerar_chave
        from plataforma.models import Empresa

        # A senha do banco do cliente é guardada CIFRADA, e sem a chave o
        # cadastro da empresa recusa — e recusar desfaz o titular junto
        # (tudo ou nada). Sem isto o teste ficaria vermelho por um motivo que
        # não é o dele.
        monkeypatch.setenv(VARIAVEL, gerar_chave())

        mw5_logada.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Dona", "email": "dona@teste.com",
            "nivel": str(int(Nivel.TITULAR)),
            "senha_da_pessoa": "so-da-pessoa",
            "razao_social": "Normadin Ltda", "municipio": "Cascavel",
            "uf": "PR", "host": "kronos.normadin", "porta": "1521",
            "banco": "ORCL", "tabela": "PRODUTOS", "usuario": "portal",
            "senha": "so-do-oracle"})

        dela = Client()
        assert dela.post(reverse("entrar"),
                         {"usuario": "dona@teste.com",
                          "senha": "so-da-pessoa"}).status_code == 302, (
            "a senha da pessoa não é a que ela digitou")

        pessoa = Usuario.objects.get(email="dona@teste.com")
        assert not pessoa.check_password("so-do-oracle"), (
            "a senha do banco do cliente virou a senha de entrada da pessoa")
        assert Empresa.objects.filter(dono=pessoa).exists()


@pytest.mark.django_db
class TestAContaSoAparecePraQuemTemConta:
    """"O campo de ligação com a empresa deve aparecer apenas quando usuário
    é comprador ou vendedor" — 10/09/2026.

    O TITULAR **é** a conta e o MASTER não é cliente de nenhuma. Perguntar "de
    quem esta pessoa é" para os dois oferece uma escolha que não existe — e a
    resposta que alguém escolhesse seria descartada no servidor, sem
    explicação nenhuma na tela.
    """

    def _titular(self):
        from contas.models import Nivel
        from plataforma.models import Empresa

        titular = Usuario.objects.create_user(
            email="dona@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        Empresa.objects.create(razao_social="Normadin", dono=titular)
        return titular

    def test_a_caixa_da_conta_declara_os_niveis_que_a_escondem(
            self, mw5_logada):
        from contas.models import Nivel

        """A tela esconde por script; o atributo é o contrato entre os dois.

        Lista de níveis (`0,1`) e não "todos menos um": no dia em que existir
        um quinto nível, quem o criar decide de que lado ele cai em vez de
        herdar a resposta por acidente.
        """
        self._titular()
        html = mw5_logada.get(reverse("usuarios")).content.decode()

        esperado = f'data-nivel-sem-conta="{int(Nivel.MASTER)},{int(Nivel.TITULAR)}"'
        assert esperado in html

    def test_a_caixa_desliga_os_campos_quando_some(self, mw5_logada):
        """Campo escondido continua sendo ENVIADO. Sem desligar, quem
        escolhesse a conta e depois trocasse para Titular mandaria a conta
        junto — e o servidor a descartaria, o que funciona mas depende de ele
        lembrar."""
        self._titular()
        html = mw5_logada.get(reverse("usuarios")).content.decode()
        i = html.index("data-nivel-sem-conta")

        assert "data-desligar-escondido" in html[i - 200:i + 200]

    def test_o_titular_nunca_fica_com_dono_mesmo_com_conta_no_post(
            self, mw5_logada):
        """A trava de verdade, no servidor: a tela esconder é conveniência."""
        from contas.models import Nivel

        titular = self._titular()

        mw5_logada.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Outro", "email": "outro@teste.com",
            "nivel": str(int(Nivel.TITULAR)), "conta": str(titular.pk)})

        novo = Usuario.objects.get(email="outro@teste.com")
        assert novo.dono_id is None, (
            "um titular ficou pendurado na conta de outro titular")

    def test_o_comprador_continua_recebendo_a_conta(self, mw5_logada):
        from contas.models import Nivel

        titular = self._titular()

        mw5_logada.post(reverse("usuarios"), {
            "acao": "criar", "nome": "Zé", "email": "ze@teste.com",
            "nivel": str(int(Nivel.MEMBRO)), "conta": str(titular.pk)})

        assert Usuario.objects.get(email="ze@teste.com").dono_id == titular.pk
