"""A trilha de auditoria: quem fez, o quê, quando.

O teste que mais importa é o primeiro. Um registro que aponta para uma chave
estrangeira morre junto com a pessoa que ele descrevia — e é exatamente da
pessoa removida que alguém vai perguntar, seis meses depois.
"""

import base64
from contextlib import contextmanager

import pytest


@pytest.fixture(autouse=True)
def _todo_mundo_na_mesma_empresa(db, monkeypatch):
    """Toda pessoa criada neste arquivo nasce vinculada à empresa semeada.

    Estes testes foram escritos quando a instalação era de um cliente só e
    quem tinha a permissão administrava todo mundo. Neste produto o alcance
    exige vínculo (ver `tests/test_usuarios_alcance.py`), e um alvo sem
    vínculo não existe para quem chama — que é a regra certa.
    """
    from contas.models import GerenteDeUsuario

    from tests.conftest import dar_acesso

    original = GerenteDeUsuario.create_user

    def com_vinculo(self, *args, **kwargs):
        """O PRIMEIRO vira o Admin dono; os outros entram na conta dele.

        Era `dar_acesso(pessoa)` para todo mundo, o que promovia todos a
        ADMIN. Com uma conta por empresa (09/09/2026) isso parou de
        funcionar, e por um motivo que é a mudança em si: dois Admins não
        cabem na mesma empresa, então o segundo ficava sem conta — e sem
        conta ele não alcança ninguém, nem a si mesmo.
        """
        from plataforma.models import Empresa

        from tests.conftest import por_na_conta

        pessoa = original(self, *args, **kwargs)
        empresa = empresa_do_teste()
        if empresa is None:
            return pessoa
        if empresa.dono_id is None:
            dar_acesso(pessoa, empresas=[empresa])
        else:
            por_na_conta(pessoa, empresa)
        return pessoa

    monkeypatch.setattr(GerenteDeUsuario, "create_user", com_vinculo)
from django.contrib.auth.models import Permission
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from tests.conftest import (
    alocar, dar_permissoes,
    email_de, empresa_do_teste, matriz_do_teste, por_na_conta)

SENHA = "segredo-de-teste"


def _promover_a_dono(pessoa) -> None:
    """`pessoa` vira o Admin dono da empresa semeada, tomando o lugar de quem
    estiver lá — e leva junto quem já era daquela conta.

    Trocar o dono é o que estes testes precisam e o que a TELA nunca faria:
    lá a conta é de quem a criou. Aqui ela é detalhe de cenário, e escrever
    isso à mão em cada um seria seis linhas repetidas trinta vezes.
    """
    from contas.models import Nivel

    # `empresa_do_teste` CRIA quando não há: a semeadura do `post_migrate`
    # acabou em 09/09/2026, e sem ela `Empresa.objects.first()` devolvia
    # `None` — o ator não virava dono de nada e todo cenário desta suíte
    # respondia 404 em vez de agir.
    empresa = empresa_do_teste()

    antigo_dono_id = empresa.dono_id
    pessoa.nivel = Nivel.TITULAR
    pessoa.dono = None
    pessoa.save(update_fields=["nivel", "dono"])

    empresa.dono = pessoa
    empresa.save(update_fields=["dono"])

    if antigo_dono_id is not None and antigo_dono_id != pessoa.pk:
        # O dono anterior vira membro da conta nova, e leva a gente dele:
        # sem isto, os alvos criados antes ficariam apontando para um Admin
        # que não é mais dono de nada, e sumiriam do alcance do ator.
        # Um a um, e não `update(dono=...)`: é o `save` que acerta a
        # `conta_guid` junto com o dono.
        for membro in Usuario.objects.filter(dono_id=antigo_dono_id):
            membro.dono = pessoa
            membro.save(update_fields=["dono"])
        Usuario.objects.filter(pk=antigo_dono_id).update(
            nivel=Nivel.MEMBRO, dono=pessoa)


def _cliente_logado(username: str, senha: str = SENHA, *, superuser: bool = False,
                     permissoes: tuple[str, ...] = ()) -> Client:
    """Uma pessoa criada, com as permissões pedidas, já logada — um `Client`
    pronto para postar nas telas que os cenários abaixo exercitam."""
    email = email_de(username)
    if superuser:
        Usuario.objects.create_superuser(email=email, password=senha)
    else:
        pessoa = Usuario.objects.create_user(email=email, password=senha)
        for codename in permissoes:
            pessoa.user_permissions.add(Permission.objects.get(codename=codename))
        # **Quem age aqui é o dono da conta**, e por isso a promoção é
        # explícita em vez de depender de quem foi criado primeiro. Estes
        # cenários criam o ALVO antes do ator (o alvo precisa existir para
        # ser desativado), e a regra do `com_vinculo` — o primeiro vira dono
        # — punha a conta no alvo: o ator entrava como membro, não
        # administrava ninguém, e a tela respondia 404 em vez de agir. O
        # teste ficava verde-escuro: nada estourava, e a razão era que nada
        # acontecia.
        _promover_a_dono(pessoa)
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": email, "senha": senha})
    return cliente


#: Um payload de Aparência que passa por `_validar` (hex válido, e nenhum
#: par fundo/texto declarado o suficiente para reprovar no contraste) — o
#: mesmo conjunto mínimo de campos que `test_tela_aparencia.py` já usa.
_PAYLOAD_DE_APARENCIA_VALIDO = {
    "client_name": "Cliente de teste", "primary": "#276b2e",
    "accent": "#872d00", "radius": "12px", "sidebar_width": "256px",
}

#: Assinatura de verdade, corpo de mentira — mesmo truque de
#: `tests/test_avatar.py`: `validar` decide pelo prefixo, então isto basta
#: para exercitar o caminho sem carregar imagem de verdade.
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
_URL_DE_DADOS_PNG = "data:image/png;base64," + base64.b64encode(_PNG).decode()


def _cenario_entrou():
    Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
    Client().post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
    return email_de("ana"), email_de("ana")


def _cenario_entrada_recusada():
    Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
    Client().post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "chute"})
    return email_de("ana"), email_de("ana")


def _cenario_saiu():
    cliente = _cliente_logado("ana")
    cliente.post(reverse("sair"))
    return email_de("ana"), email_de("ana")


def _cenario_usuario_criado():
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    # Sem campo "login": o e-mail É o login desde que o usuário passou a ser
    # nosso, e a tela deixou de oferecer os dois.
    cliente.post(reverse("usuarios"),
                 {"acao": "criar", "nome": "Zeca", "email": email_de("zeca")})
    return email_de("admin"), email_de("zeca")


def _cenario_usuario_editado():
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    alvo = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    cliente.post(reverse("usuarios"), {"acao": "editar", "id": str(alvo.pk), "nome": "Zeca Editado"})
    return email_de("admin"), email_de("zeca")


def _cenario_usuario_desativado():
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    alvo = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    cliente.post(reverse("usuarios"), {"acao": "desativar", "id": str(alvo.pk)})
    return email_de("admin"), email_de("zeca")


def _cenario_usuario_reativado():
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    alvo = Usuario.objects.create_user(
        email="zeca@teste.com", password=SENHA, is_active=False)
    cliente.post(reverse("usuarios"), {"acao": "ativar", "id": str(alvo.pk)})
    return email_de("admin"), email_de("zeca")


def _cenario_senha_resetada():
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    alvo = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    cliente.post(reverse("usuarios"), {"acao": "senha", "id": str(alvo.pk)})
    return email_de("admin"), email_de("zeca")


def _cenario_usuario_removido():
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    alvo = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    cliente.post(reverse("usuarios"), {"acao": "remover", "id": str(alvo.pk)})
    return email_de("admin"), email_de("zeca")


def _cenario_senha_trocada():
    cliente = _cliente_logado("ana")
    cliente.post(reverse("perfil_senha"), {
        "senha_atual": SENHA, "senha_nova": "senha-nova-123",
        "senha_confirma": "senha-nova-123",
    })
    return email_de("ana"), email_de("ana")


def _cenario_foto_alterada():
    cliente = _cliente_logado("ana")
    cliente.post(reverse("perfil_foto"), {"recorte": _URL_DE_DADOS_PNG})
    return email_de("ana"), email_de("ana")


@contextmanager
def _catalogo_so_com(*specs):
    """Troca `_DECLARADOS` (o catálogo global de módulos do código) por só
    `specs`, e devolve o de antes ao sair — mesmo padrão de `catalogo_limpo`
    em `tests/test_tela_modulos.py`.

    Sem isto, os módulos "de alicerce" que o app `contas` registra sozinho no
    `ready()` (`cargos`, `usuarios` — ver `contas/modulo.py`, ambos
    `ativo_por_padrao=True`) entrariam em `declarados()` junto do módulo de
    teste. A tela de Módulos desliga tudo que não estiver marcado no POST, e
    um POST que só marca o módulo de teste desligaria os dois de alicerce
    junto — registrando `MODULO_DESLIGADO` para eles também, e quebrando a
    contagem que este cenário verifica.
    """
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    for spec in specs:
        declaracao._DECLARADOS[spec.chave] = spec
    try:
        yield
    finally:
        declaracao._DECLARADOS.clear()
        declaracao._DECLARADOS.update(guardado)


def _cenario_modulo_ligado():
    from plataforma.declaracao import ModuloSpec

    with _catalogo_so_com(ModuloSpec(chave="frete", rotulo="Frete")):
        cliente = _cliente_logado("raiz", superuser=True)
        cliente.post(reverse("modulos"), {"ligados": ["frete"]})
    return email_de("raiz"), "frete"


def _cenario_modulo_desligado():
    from plataforma.catalogo import semear
    from plataforma.declaracao import ModuloSpec
    from plataforma.models import Modulo

    with _catalogo_so_com(ModuloSpec(chave="frete", rotulo="Frete")):
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)
        cliente = _cliente_logado("raiz", superuser=True)
        cliente.post(reverse("modulos"), {"ligados": []})
    return email_de("raiz"), "frete"


def _cenario_aparencia_alterada():
    cliente = _cliente_logado("raiz", superuser=True)
    cliente.post(reverse("aparencia"), _PAYLOAD_DE_APARENCIA_VALIDO)
    return email_de("raiz"), "aparência"


#: PNG mínimo pela assinatura — `nucleo.images.validar` decide pelo prefixo.
_PNG_DA_MARCA = b"\x89PNG\r\n\x1a\n" + b"so a assinatura importa"


def _cenario_logo_alterado():
    from django.core.files.uploadedfile import SimpleUploadedFile

    cliente = _cliente_logado("raiz", superuser=True)
    cliente.post(reverse("aparencia_logo"), {
        "lugar": "login",
        "arquivo": SimpleUploadedFile("logo.png", _PNG_DA_MARCA),
    })
    return email_de("raiz"), "Tela de entrada"


def _cenario_logo_removido():
    from django.core.files.uploadedfile import SimpleUploadedFile
    from plataforma.models import ImagemDaMarca

    ImagemDaMarca.objects.create(lugar="sidebar", conteudo=_PNG_DA_MARCA)
    cliente = _cliente_logado("raiz", superuser=True)
    cliente.post(reverse("aparencia_logo"),
                 {"lugar": "sidebar", "acao": "remover"})
    return email_de("raiz"), "Menu lateral"


def _cenario_menu_da_empresa_alterado():
    from plataforma.models import Empresa

    empresa = Empresa.objects.create(razao_social="Menu Ltda")
    cliente = _cliente_logado("raiz", superuser=True)
    cliente.post(reverse("empresa_menu", args=[empresa.pk]),
                 {"acao": "cores", "sidebar_bg": "#112233",
                  "sidebar_text": ""})
    return email_de("raiz"), "Menu Ltda"


def _cenario_personificacao_iniciada():
    cliente = _cliente_logado("raiz", superuser=True)
    zeca = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    cliente.post(reverse("personificar"), {"id": str(zeca.pk)})
    return email_de("raiz"), email_de("zeca")


def _cenario_personificacao_encerrada():
    cliente = _cliente_logado("raiz", superuser=True)
    zeca = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    cliente.post(reverse("personificar"), {"id": str(zeca.pk)})
    cliente.post(reverse("voltar_a_ser_eu"))
    return email_de("raiz"), email_de("zeca")


def _cenario_filial_trocada():
    from plataforma.models import Filial

    # A "Matriz" já vem semeada (`plataforma.empresa.garantir_matriz`) — o
    # superusuário a alcança sem precisar de linha em `Filial.usuarios`.
    matriz = matriz_do_teste()
    cliente = _cliente_logado("raiz", superuser=True)
    cliente.post(reverse("filial_trocar"), {"filial_id": str(matriz.pk)})
    return email_de("raiz"), "Matriz"


def _cenario_empresa_editada():
    """O `alvo` passou a ser o NOME da empresa, e não a palavra "empresa".

    Enquanto havia uma linha só, "empresa" identificava sem ambiguidade o que
    tinha mudado. Com o cadastro de várias, uma trilha que só diz "empresa"
    não responde a pergunta que a trilha existe para responder: QUAL.
    """
    from plataforma.models import Empresa

    cliente = _cliente_logado("admin", permissoes=("empresa_editar",))
    alvo = empresa_do_teste()
    cliente.post(reverse("empresa"), {
        "acao": "salvar", "empresa": str(alvo.pk),
        "razao_social": "Nova Razão Social",
    })
    return email_de("admin"), "Nova Razão Social"


def _ligar_filiais():
    """Os cenários de filial precisam do módulo LIGADO: neste produto ele
    nasce desligado (ver `tests/test_modulo_filiais.py`), e a rota responde
    404. O vocabulário de auditoria continua tendo as ações de filial, e elas
    continuam valendo — para quando alguém ligar."""
    from plataforma.models import Modulo

    Modulo.objects.filter(chave="filiais").update(ativo=True)


def _cenario_senha_do_banco_vista(monkeypatch=None):
    """Alguém clicou no olho e leu a senha do banco de um cliente.

    Ler credencial é um ATO, e por isso entra no vocabulário: "quem viu, e
    quando" é a pergunta que se faz depois de um vazamento, e ela precisa ter
    resposta. É a única ação aqui que não altera nada — e é justamente por
    não alterar que ela passaria despercebida sem um registro próprio.
    """
    import os

    from plataforma.cifra import VARIAVEL, gerar_chave
    from plataforma.models import Empresa

    os.environ[VARIAVEL] = gerar_chave()
    try:
        cliente = _cliente_logado("admin", permissoes=("empresa_editar",))
        alvo = empresa_do_teste()
        alvo.definir_senha("segredo-do-oracle")
        alvo.save()
        _dar_acesso_as_empresas("admin")
        cliente.get(reverse("empresa_senha", args=[alvo.pk]))
        return email_de("admin"), str(alvo)
    finally:
        os.environ.pop(VARIAVEL, None)


def _dar_acesso_as_empresas(login: str) -> None:
    """A rota da senha recorta pelo ALCANCE, e não só pela permissão: sem o
    vínculo, o `admin` deste cenário receberia 404 e nada seria registrado —
    e o teste falharia por falta de cadastro, não por defeito da trilha."""
    from contas.models import Nivel
    from plataforma.models import Empresa

    pessoa = Usuario.objects.get(email=email_de(login))
    pessoa.nivel = Nivel.TITULAR
    pessoa.save(update_fields=["nivel"])
    por_na_conta(pessoa, empresa_do_teste())


def _cenario_filial_criada():
    _ligar_filiais()
    cliente = _cliente_logado("admin", permissoes=("filiais_editar",))
    cliente.post(reverse("filiais"), {
        "acao": "criar", "nome": "Loja Sorriso", "apelido": "Sorriso",
    })
    return email_de("admin"), "Sorriso"


def _cenario_filial_editada():
    _ligar_filiais()
    from plataforma.models import Filial

    cliente = _cliente_logado("admin", permissoes=("filiais_editar",))
    filial = matriz_do_teste()
    cliente.post(reverse("filiais"), {
        "acao": "salvar", "filial": str(filial.pk),
        "nome": "Matriz", "apelido": "Sede",
    })
    return email_de("admin"), "Sede"


def _cenario_filial_ativada():
    _ligar_filiais()
    from plataforma.models import Filial

    cliente = _cliente_logado("admin", permissoes=("filiais_editar",))
    # Com empresa: desde 14/09/2026 a tela só alcança as filiais da empresa do
    # contexto (`plataforma.views_filiais._filiais_da_empresa`), e uma filial
    # sem empresa não aparece para ninguém — o POST voltaria "Filial não
    # encontrada" e o teste acusaria falta de auditoria pela razão errada.
    filial = Filial.objects.create(
        nome="Loja 1", apelido="Loja 1", ativa=False,
        empresa=matriz_do_teste().empresa)
    cliente.post(reverse("filiais"), {"acao": "ativar", "filial": str(filial.pk)})
    return email_de("admin"), "Loja 1"


def _cenario_filial_desativada():
    _ligar_filiais()
    from plataforma.models import Filial

    cliente = _cliente_logado("admin", permissoes=("filiais_editar",))
    # Uma segunda filial ativa, para a Matriz não ser a ÚLTIMA ativa — regra
    # (a) do desenho recusaria a desativação sozinha (`plataforma.filiais.
    # pode_desativar`), e este cenário testa o registro do sucesso.
    # Na empresa da Matriz: a regra da última ativa conta dentro da empresa
    # desde 14/09/2026, e uma loja sem empresa não liberaria a desativação.
    matriz = matriz_do_teste()
    Filial.objects.create(nome="Loja 1", apelido="Loja 1",
                          empresa=matriz.empresa)
    cliente.post(reverse("filiais"), {"acao": "desativar", "filial": str(matriz.pk)})
    return email_de("admin"), "Matriz"


def _cenario_filial_removida():
    _ligar_filiais()
    from plataforma.models import Filial

    cliente = _cliente_logado("admin", permissoes=("filiais_editar",))
    # DUAS filiais, e as duas montadas aqui.
    #
    # A "Matriz" vinha do `post_migrate`, que a semeava em toda instalação —
    # e a semeadura acabou em 09/09/2026. Sem ela, a "Loja 1" era a ÚNICA, e
    # `plataforma.filiais.pode_remover` recusa deixar a instalação sem filial
    # ativa nenhuma: o POST voltava com a frase da recusa e o teste acusava
    # falta de registro de auditoria, que é verdade e não é a razão.
    #
    # E com empresa: a tela só alcança as filiais da empresa do contexto, e
    # uma filial sem empresa não aparece para ninguém.
    matriz_do_teste()
    filial = Filial.objects.create(nome="Loja 1", apelido="Loja 1",
                                   empresa=empresa_do_teste())
    cliente.post(reverse("filiais"), {"acao": "remover", "filial": str(filial.pk)})
    return email_de("admin"), "Loja 1"


def _cenario_parametro_alterado():
    # `nova_filial_nasce_ativa` (`plataforma.parametro`) é `so_mw5=False`:
    # o admin do cliente pode gravá-lo sem ser superusuário.
    cliente = _cliente_logado("admin", permissoes=("parametros_editar",))
    cliente.post(reverse("parametros"), {
        "acao": "salvar", "chave": "nova_filial_nasce_ativa",
    })
    return email_de("admin"), "Nova filial nasce ativa"


def _cenario_parametro_restaurado():
    from plataforma.parametro_catalogo import definir

    definir("nova_filial_nasce_ativa", "0")
    cliente = _cliente_logado("admin", permissoes=("parametros_editar",))
    cliente.post(reverse("parametros"), {
        "acao": "restaurar", "chave": "nova_filial_nasce_ativa",
    })
    return email_de("admin"), "Nova filial nasce ativa"


@pytest.mark.django_db
class TestOsRegistrosSobrevivem:
    def test_remover_a_pessoa_nao_apaga_o_que_ela_fez(self):
        from comum.auditoria import ACOES, registrar
        from contas.models import RegistroDeAuditoria

        # O dono da conta primeiro: `Empresa.dono` é `PROTECT`, e o Zeca,
        # sendo o primeiro criado, viraria dono e não poderia ser apagado —
        # que é a regra certa (apagar a conta deixaria a empresa órfã) e não
        # é o assunto deste teste.
        _cliente_logado("dono-da-conta")
        zeca = Usuario.objects.create_user(
            email="zeca@teste.com", password=SENHA, nome="Zeca")
        registrar(ACOES.CARGO_CRIADO, zeca, alvo="Conferente")
        zeca.delete()

        registro = RegistroDeAuditoria.objects.get(acao=ACOES.CARGO_CRIADO)
        assert registro.autor_login == "zeca@teste.com"
        assert registro.autor_nome == "Zeca"
        assert registro.alvo == "Conferente"


@pytest.mark.django_db
class TestAEntrada:
    def test_entrar_registra(self, db):
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        Client().post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        assert RegistroDeAuditoria.objects.filter(
            acao=ACOES.ENTROU, autor_login="ana@teste.com").exists()

    def test_a_tentativa_recusada_tambem_registra(self, db):
        """É o que se olha quando alguém pergunta 'tentaram entrar na minha
        conta?'. Sem isto, a pergunta não tem resposta."""
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        Client().post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "chute"})
        assert RegistroDeAuditoria.objects.filter(
            acao=ACOES.ENTRADA_RECUSADA, autor_login="ana@teste.com").exists()

    def test_a_senha_nunca_aparece_no_registro(self, db):
        """Em campo nenhum, nem na tentativa recusada — que é justamente onde
        a senha digitada estaria mais à mão para ser guardada por engano."""
        from contas.models import RegistroDeAuditoria

        Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "chute-secreto"})
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})

        for registro in RegistroDeAuditoria.objects.all():
            texto = " ".join([
                registro.acao, registro.autor_login, registro.autor_nome,
                registro.alvo, registro.detalhe,
            ])
            assert "chute-secreto" not in texto
            assert SENHA not in texto


@pytest.mark.django_db
class TestAppendOnly:
    def test_uma_linha_gravada_nao_se_altera(self):
        from comum.auditoria import ACOES, registrar
        from contas.models import RegistroDeAuditoria, RegistroImutavel

        ana = Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        registrar(ACOES.ENTROU, ana)
        registro = RegistroDeAuditoria.objects.get()

        registro.acao = ACOES.SAIU
        with pytest.raises(RegistroImutavel):
            registro.save()
        # E a recusa realmente recusou: a linha no banco continua com a
        # ação original, não com `ACOES.SAIU` que a atribuição em memória
        # (acima) só mudou no objeto Python, sem gravar.
        assert RegistroDeAuditoria.objects.get().acao == ACOES.ENTROU

    def test_uma_linha_gravada_nao_se_apaga(self):
        from comum.auditoria import ACOES, registrar
        from contas.models import RegistroDeAuditoria, RegistroImutavel

        ana = Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        registrar(ACOES.ENTROU, ana)
        with pytest.raises(RegistroImutavel):
            RegistroDeAuditoria.objects.get().delete()
        # E a recusa realmente recusou: a linha continua no banco.
        assert RegistroDeAuditoria.objects.count() == 1


#: As três ações do catálogo são genéricas de propósito — o QUE mudou vai em
#: `alvo` ("Segmentos: Agrícola"), e não em doze constantes. Ver o comentário
#: em `comum/auditoria.py`.


#: Uma linha por ação de `ACOES` — o cenário faz a ação de verdade acontecer
#: (via `Client`, como um navegador faria) e devolve o `(autor_login, alvo)`
#: esperado. `ACOES.<nome>` mora só no `id=`, lido do próprio nome da
#: função — assim a tabela nunca esquece de nomear a ação que testa.
def _cenario_cargo_criado():
    """A tela de Cargos (14/09/2026). Quem entra é o titular — a trava da tela é
    o NÍVEL, e `_cliente_logado` promove o ator a dono da empresa semeada."""
    cliente = _cliente_logado("dono-cargos", permissoes=("cargos_editar",))
    cliente.post(reverse("cargos"), {
        "acao": "criar", "rotulo": "Faturista", "alcance": "filial"})
    return email_de("dono-cargos"), "Faturista"


def _cenario_cargo_editado():
    from contas.models import Cargo

    cliente = _cliente_logado("dono-cargos", permissoes=("cargos_editar",))
    vendedor = Cargo.objects.get(conta__email=email_de("dono-cargos"),
                                 nome="vendedor")
    cliente.post(reverse("cargos"), {
        "acao": "salvar", "cargo": str(vendedor.pk),
        "rotulo": "Vendedor Externo", "alcance": "filial"})
    return email_de("dono-cargos"), "Vendedor Externo"


def _cenario_cargo_removido():
    from contas.models import Cargo

    cliente = _cliente_logado("dono-cargos", permissoes=("cargos_editar",))
    dono = Usuario.objects.get(email=email_de("dono-cargos"))
    caixa = Cargo.objects.create(conta=dono, nome="caixa", rotulo="Caixa")
    cliente.post(reverse("cargos"), {"acao": "remover", "cargo": str(caixa.pk)})
    return email_de("dono-cargos"), "Caixa"


def _cenario_alocacao_criada():
    """O titular cadastra alguém já alocado: a trilha diz quem, com qual cargo
    e onde — é o que se pergunta depois de alguém ver o que não devia."""
    from contas.models import Cargo

    cliente = _cliente_logado("dono-aloc", permissoes=("usuarios_editar",))
    empresa = empresa_do_teste()
    cargo = Cargo.objects.get(conta_id=empresa.conta_id, nome="cliente")
    cliente.post(reverse("usuarios"), {
        "acao": "criar", "nome": "Zeca", "email": email_de("zeca"),
        "alocacoes": "1", "aloc_empresa": str(empresa.pk), "aloc_filial": "",
        "aloc_cargo": str(cargo.pk)})
    return email_de("dono-aloc"), f"Zeca — Cliente em {empresa}"


def _cenario_alocacao_removida():
    from contas.models import Alocacao, Cargo

    cliente = _cliente_logado("dono-aloc", permissoes=("usuarios_editar",))
    dono = Usuario.objects.get(email=email_de("dono-aloc"))
    empresa = empresa_do_teste()
    zeca = Usuario.objects.create_user(email=email_de("zeca"), password=SENHA,
                                       nome="Zeca", dono=dono)
    Alocacao.objects.create(pessoa=zeca, empresa=empresa, cargo=Cargo.objects.get(
        conta_id=empresa.conta_id, nome="cliente"))
    cliente.post(reverse("usuarios"), {
        "acao": "editar", "id": str(zeca.pk), "nome": "Zeca", "alocacoes": "1"})
    return email_de("dono-aloc"), f"Zeca — Cliente em {empresa}"


def _loja_com_gente_da_fila():
    """A Matriz com a Zeca na fila, e a dona logada com as permissões da fila.

    Pelo domínio (`fila.acoes`) e não pela tela: o que este arquivo prova é a
    LINHA da trilha, e a tela da fila tem os testes dela
    (`tests/test_fila_pagina.py`)."""
    from contas.models import Usuario
    from fila.acoes import bater_ponto
    from tests.fila_cenario import cadastros

    _cliente_logado("dona-fila", permissoes=(
        "fila_ver", "fila_participar", "fila_gerenciar", "fila_cadastros"))
    dona = Usuario.objects.get(email=email_de("dona-fila"))
    empresa, matriz = empresa_do_teste(), matriz_do_teste()
    zeca = Usuario.objects.create_user(email=email_de("zeca"), password=SENHA,
                                       nome="Zeca")
    alocar(zeca, empresa, "vendedor", filial=matriz)
    bater_ponto(zeca, matriz)
    return dona, zeca, matriz, cadastros(empresa)


def _cenario_fila_pessoa_tirada():
    from fila.correcoes import tirar_da_loja

    dona, zeca, matriz, _cad = _loja_com_gente_da_fila()
    tirar_da_loja(dona, matriz, zeca.pk, observacao="motivo do teste")
    return email_de("dona-fila"), f"Zeca em {matriz}"


def _cenario_fila_atendimento_fechado():
    from fila.acoes import Lancamento, vou_atender
    from fila.correcoes import fechar_atendimento

    dona, zeca, matriz, cad = _loja_com_gente_da_fila()
    vou_atender(zeca, matriz)
    fechar_atendimento(dona, matriz, zeca.pk,
                       Lancamento("nao_vendeu", motivo_id=cad.motivo.pk),
                       observacao="motivo do teste")
    return email_de("dona-fila"), f"Zeca em {matriz}"


def _cenario_fila_pausa_encerrada():
    from fila.acoes import pausar
    from fila.correcoes import tirar_da_pausa

    dona, zeca, matriz, cad = _loja_com_gente_da_fila()
    pausar(zeca, matriz, cad.tipo.pk)
    tirar_da_pausa(dona, matriz, zeca.pk, observacao="motivo do teste")
    return email_de("dona-fila"), f"Zeca em {matriz}"


def _cenario_fila_lancamento_corrigido():
    from fila.acoes import Lancamento, finalizar, vou_atender
    from fila.correcoes import editar_lancamento
    from fila.models import Atendimento

    dona, zeca, matriz, cad = _loja_com_gente_da_fila()
    vou_atender(zeca, matriz)
    finalizar(zeca, matriz, Lancamento("nao_vendeu", motivo_id=cad.motivo.pk))
    editar_lancamento(dona, matriz, Atendimento.irrestritos.get().pk,
                      Lancamento("nao_vendeu", motivo_id=cad.motivo.pk,
                                 observacao="voltou depois"),
                      observacao="motivo do teste")
    return email_de("dona-fila"), f"Atendimento de Zeca em {matriz}"


def _cenario_fila_pausa_iniciada():
    from fila.correcoes import por_em_pausa

    dona, zeca, matriz, cad = _loja_com_gente_da_fila()
    por_em_pausa(dona, matriz, zeca.pk, cad.tipo.pk, observacao="foi ao banco")
    return email_de("dona-fila"), f"Zeca em {matriz}"


def _cenario_fila_posto_na_fila():
    from fila.acoes import Lancamento, finalizar, vou_atender
    from fila.correcoes import por_na_fila
    from plataforma.models import FluxoDaFila

    dona, zeca, matriz, cad = _loja_com_gente_da_fila()
    matriz.empresa.fluxo_da_fila = FluxoDaFila.ESPERA
    matriz.empresa.save(update_fields=["fluxo_da_fila"])
    vou_atender(zeca, matriz)
    finalizar(zeca, matriz, Lancamento("nao_vendeu", motivo_id=cad.motivo.pk))
    por_na_fila(dona, matriz, zeca.pk, observacao="cliente chegou")
    return email_de("dona-fila"), f"Zeca em {matriz}"


def _cenario_fila_posicao_movida():
    from contas.models import Usuario
    from fila.acoes import bater_ponto
    from fila.correcoes import mover

    dona, zeca, matriz, _cad = _loja_com_gente_da_fila()
    yara = Usuario.objects.create_user(email=email_de("yara"), password=SENHA,
                                       nome="Yara")
    alocar(yara, empresa_do_teste(), "vendedor", filial=matriz)
    bater_ponto(yara, matriz)
    mover(dona, matriz, yara.pk, 1, observacao="chegou antes")
    return email_de("dona-fila"), f"Yara em {matriz}"


def _cenario_fila_cadastro_criado():
    cliente = _cliente_logado("dona-cad", permissoes=("fila_ver", "fila_cadastros"))
    cliente.post(reverse("fila_grupos"), {"acao": "criar", "nome": "Sofás",
                                          "ordem": "0"})
    return email_de("dona-cad"), "Grupo de item: Sofás"


def _cenario_fila_cadastro_editado():
    from fila.models import MotivoDeNaoVenda

    cliente = _cliente_logado("dona-cad", permissoes=("fila_ver", "fila_cadastros"))
    motivo = MotivoDeNaoVenda.irrestritos.create(empresa=empresa_do_teste(),
                                                 nome="Caro")
    cliente.post(reverse("fila_motivos"), {"acao": "salvar", "id": str(motivo.pk),
                                           "nome": "Achou caro", "ordem": "0",
                                           "ativo": "1"})
    return email_de("dona-cad"), "Motivo de não venda: Achou caro"


def _cenario_fila_cadastro_removido():
    from fila.models import TipoDePausa

    cliente = _cliente_logado("dona-cad", permissoes=("fila_ver", "fila_cadastros"))
    tipo = TipoDePausa.irrestritos.create(empresa=empresa_do_teste(), nome="Café")
    cliente.post(reverse("fila_pausas"), {"acao": "remover", "id": str(tipo.pk)})
    return email_de("dona-cad"), "Tipo de pausa: Café"


def _cenario_fila_meta_definida():
    from django.utils import timezone

    from fila.metas import gravar

    dona, zeca, matriz, _cad = _loja_com_gente_da_fila()
    mes = timezone.localdate().replace(day=1)
    gravar(matriz, mes, dona, {str(zeca.pk): "5000"})
    return email_de("dona-fila"), f"{matriz}: Zeca em {mes:%m/%Y}"


def _cenario_fila_meta_removida():
    from django.utils import timezone

    from fila.metas import gravar

    dona, zeca, matriz, _cad = _loja_com_gente_da_fila()
    mes = timezone.localdate().replace(day=1)
    gravar(matriz, mes, dona, {"loja": "90000"})
    gravar(matriz, mes, dona, {"loja": ""})
    return email_de("dona-fila"), f"{matriz}: a loja em {mes:%m/%Y}"


_CENARIOS = {
    "ENTROU": _cenario_entrou,
    "ENTRADA_RECUSADA": _cenario_entrada_recusada,
    "SAIU": _cenario_saiu,
    "USUARIO_CRIADO": _cenario_usuario_criado,
    "USUARIO_EDITADO": _cenario_usuario_editado,
    "USUARIO_DESATIVADO": _cenario_usuario_desativado,
    "USUARIO_REATIVADO": _cenario_usuario_reativado,
    "SENHA_RESETADA": _cenario_senha_resetada,
    "SENHA_TROCADA": _cenario_senha_trocada,
    "USUARIO_REMOVIDO": _cenario_usuario_removido,
    "FOTO_ALTERADA": _cenario_foto_alterada,
    "CARGO_CRIADO": _cenario_cargo_criado,
    "CARGO_EDITADO": _cenario_cargo_editado,
    "CARGO_REMOVIDO": _cenario_cargo_removido,
    "ALOCACAO_CRIADA": _cenario_alocacao_criada,
    "ALOCACAO_REMOVIDA": _cenario_alocacao_removida,
    "MODULO_LIGADO": _cenario_modulo_ligado,
    "MODULO_DESLIGADO": _cenario_modulo_desligado,
    "APARENCIA_ALTERADA": _cenario_aparencia_alterada,
    "LOGO_ALTERADO": _cenario_logo_alterado,
    "LOGO_REMOVIDO": _cenario_logo_removido,
    "MENU_DA_EMPRESA_ALTERADO": _cenario_menu_da_empresa_alterado,
    "PERSONIFICACAO_INICIADA": _cenario_personificacao_iniciada,
    "PERSONIFICACAO_ENCERRADA": _cenario_personificacao_encerrada,
    "FILIAL_TROCADA": _cenario_filial_trocada,
    "EMPRESA_EDITADA": _cenario_empresa_editada,
    "SENHA_DO_BANCO_VISTA": _cenario_senha_do_banco_vista,
    "FILIAL_CRIADA": _cenario_filial_criada,
    "FILIAL_EDITADA": _cenario_filial_editada,
    "FILIAL_ATIVADA": _cenario_filial_ativada,
    "FILIAL_DESATIVADA": _cenario_filial_desativada,
    "FILIAL_REMOVIDA": _cenario_filial_removida,
    "PARAMETRO_ALTERADO": _cenario_parametro_alterado,
    "PARAMETRO_RESTAURADO": _cenario_parametro_restaurado,
    "FILA_PESSOA_TIRADA": _cenario_fila_pessoa_tirada,
    "FILA_ATENDIMENTO_FECHADO": _cenario_fila_atendimento_fechado,
    "FILA_PAUSA_ENCERRADA": _cenario_fila_pausa_encerrada,
    "FILA_LANCAMENTO_CORRIGIDO": _cenario_fila_lancamento_corrigido,
    "FILA_POSICAO_MOVIDA": _cenario_fila_posicao_movida,
    "FILA_PAUSA_INICIADA": _cenario_fila_pausa_iniciada,
    "FILA_POSTO_NA_FILA": _cenario_fila_posto_na_fila,
    "FILA_CADASTRO_CRIADO": _cenario_fila_cadastro_criado,
    "FILA_CADASTRO_EDITADO": _cenario_fila_cadastro_editado,
    "FILA_CADASTRO_REMOVIDO": _cenario_fila_cadastro_removido,
    "FILA_META_DEFINIDA": _cenario_fila_meta_definida,
    "FILA_META_REMOVIDA": _cenario_fila_meta_removida,
}


@pytest.mark.django_db
class TestCadaAcaoDoVocabularioRegistra:
    """Uma ação de `ACOES` que não aparece nesta tabela é uma ação que a
    trilha de auditoria não sabe contar — e este teste falharia mostrando o
    nome faltando, e não só um número de casos a menos."""

    def test_o_vocabulario_inteiro_esta_coberto(self):
        from comum.auditoria import ACOES

        nomes_do_vocabulario = {
            nome for nome in vars(ACOES) if not nome.startswith("_")
        }
        assert nomes_do_vocabulario == set(_CENARIOS)

    @pytest.mark.parametrize("nome_da_acao", sorted(_CENARIOS), )
    def test_a_acao_registra_com_autor_e_alvo_certos(self, nome_da_acao):
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        acao = getattr(ACOES, nome_da_acao)
        cenario = _CENARIOS[nome_da_acao]
        autor_login_esperado, alvo_esperado = cenario()

        registro = RegistroDeAuditoria.objects.get(acao=acao)
        assert registro.autor_login == autor_login_esperado
        assert registro.alvo == alvo_esperado


@pytest.mark.django_db
class TestAcaoRecusadaNaoRegistra:
    def test_o_admin_do_cliente_tentando_desativar_a_mw5_nao_registra(self):
        """`_alcancavel` (contas/views_usuarios.py) já recusa qualquer ação
        contra a MW5 antes de tocar numa linha — a trilha de auditoria
        precisa concordar: nenhum registro para uma ação que não aconteceu."""
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria
        from contas.mw5 import EMAIL, garantir_usuario_mw5

        garantir_usuario_mw5()
        mw5 = Usuario.objects.get(email=EMAIL)
        cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))

        resposta = cliente.post(
            reverse("usuarios"), {"acao": "desativar", "id": str(mw5.pk)})

        mw5.refresh_from_db()
        assert mw5.is_active is True
        assert resposta.status_code == 200
        assert not RegistroDeAuditoria.objects.filter(
            acao=ACOES.USUARIO_DESATIVADO).exists()


@pytest.mark.django_db
class TestOCampoNuncaEstoura:
    def test_um_login_maior_que_o_campo_e_cortado_no_tamanho_declarado(self):
        """Django não aplica `max_length` sozinho — isso é `full_clean()`,
        que `objects.create()` (o caminho de `registrar`) nunca chama.
        SQLite (o motor destes testes) deixa o `VARCHAR` estourar sem
        reclamar; Postgres (produção, `config/settings.py`) levanta
        `DataError`, e pela regra de não engolir exceção esse erro sobe —
        derrubando a tela de login para quem colar um login gigante, e
        levando junto o próprio registro da tentativa recusada (o `INSERT`
        falha antes do commit). O limite é lido de `_meta`, nunca de um
        número batido à mão aqui: o teste continua valendo se o campo for
        redimensionado amanhã."""
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        limite = RegistroDeAuditoria._meta.get_field("autor_login").max_length
        login_gigante = "a" * (limite * 10)

        Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        Client().post(
            reverse("entrar"), {"usuario": login_gigante, "senha": "chute"})

        registro = RegistroDeAuditoria.objects.get(acao=ACOES.ENTRADA_RECUSADA)
        assert len(registro.autor_login) <= limite
        limite_do_alvo = RegistroDeAuditoria._meta.get_field("alvo").max_length
        assert len(registro.alvo) <= limite_do_alvo


@pytest.mark.django_db
class TestFalhaAoRegistrarDesfazOEfeito:
    def test_falha_na_segunda_chamada_de_registrar_desfaz_os_dois_modulos(
            self, monkeypatch):
        """O cenário que a revisão mediu: dois módulos marcados, a segunda
        chamada de `registrar` falha — sem transação, os dois módulos
        ficavam ligados no banco e só um registro existia. Com
        `transaction.atomic()` cercando as trocas e o laço de `registrar`
        inteiro (`plataforma/views.py::modulos`), a falha desfaz os dois
        `Modulo.update()` junto com o `registrar` que já tinha ido: nenhum
        módulo fica ligado sem o registro correspondente."""
        import plataforma.views as views_da_plataforma
        from plataforma.catalogo import semear
        from plataforma.declaracao import ModuloSpec
        from plataforma.models import Modulo

        with _catalogo_so_com(
            ModuloSpec(chave="frete-a", rotulo="Frete A"),
            ModuloSpec(chave="frete-b", rotulo="Frete B"),
        ):
            semear()
            cliente = _cliente_logado("raiz", superuser=True)

            chamadas = []

            def registrar_que_falha_na_segunda(*args, **kwargs):
                chamadas.append((args, kwargs))
                if len(chamadas) == 2:
                    raise RuntimeError("falha forçada, só para o teste")

            monkeypatch.setattr(
                views_da_plataforma, "registrar", registrar_que_falha_na_segunda)

            with pytest.raises(RuntimeError):
                cliente.post(
                    reverse("modulos"), {"ligados": ["frete-a", "frete-b"]})

            assert len(chamadas) == 2
            assert Modulo.objects.get(chave="frete-a").ativo is False
            assert Modulo.objects.get(chave="frete-b").ativo is False

        from contas.models import RegistroDeAuditoria

        assert not RegistroDeAuditoria.objects.filter(
            alvo__in=["frete-a", "frete-b"]).exists()


def _registrar_que_falha(*args, **kwargs):
    raise RuntimeError("falha forçada, só para o teste")


def _efeito_sobrevive_cargos_criar(monkeypatch) -> bool:
    import contas.views_cargos as views
    from contas.models import Cargo

    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    cliente = _cliente_logado("admin", permissoes=("cargos_editar",))
    with pytest.raises(RuntimeError):
        cliente.post(reverse("cargos"), {"acao": "criar", "rotulo": "Conferente",
                                         "alcance": "proprios"})
    return Cargo.objects.filter(rotulo="Conferente").exists()


def _efeito_sobrevive_cargos_salvar(monkeypatch) -> bool:
    import contas.views_cargos as views
    from contas.models import Cargo

    cliente = _cliente_logado("admin", permissoes=("cargos_editar",))
    dono = Usuario.objects.get(email=email_de("admin"))
    cargo = Cargo.objects.create(conta=dono, nome="conferente", rotulo="Conferente")
    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    with pytest.raises(RuntimeError):
        cliente.post(reverse("cargos"), {
            "acao": "salvar", "cargo": str(cargo.pk), "rotulo": "Conferente",
            "alcance": "proprios", "permissoes": ["catalogo_ver"],
        })
    return cargo.permissoes.exists()


def _delete_que_falha(self, *args, **kwargs):
    raise RuntimeError("falha forçada, só para o teste")


def _efeito_sobrevive_cargos_remover(monkeypatch) -> bool:
    """Diferente dos outros cenários: aqui é `.delete()`, não `registrar`,
    que precisa falhar. Em `contas.views_cargos` (ação `remover`), `registrar`
    roda ANTES do `delete()` — depois de apagado não sobraria `cargo.rotulo`
    para descrever. Forçar `registrar` a falhar nunca alcançaria `delete()`, e
    o teste não provaria nada. O efeito que a transação protege AQUI é o
    inverso: se `delete()` falhar, o registro de remoção que JÁ tinha sido
    inserido não pode sobreviver — a trilha não pode dizer "cargo removido"
    para um cargo que continua no banco."""
    from comum.auditoria import ACOES
    from contas.models import Cargo, RegistroDeAuditoria

    cliente = _cliente_logado("admin", permissoes=("cargos_editar",))
    dono = Usuario.objects.get(email=email_de("admin"))
    cargo = Cargo.objects.create(conta=dono, nome="conferente", rotulo="Conferente")
    monkeypatch.setattr(Cargo, "delete", _delete_que_falha)
    with pytest.raises(RuntimeError):
        cliente.post(reverse("cargos"), {"acao": "remover", "cargo": str(cargo.pk)})
    return RegistroDeAuditoria.objects.filter(
        acao=ACOES.CARGO_REMOVIDO, alvo="Conferente").exists()


def _efeito_sobrevive_usuarios_criar(monkeypatch) -> bool:
    import contas.views_usuarios as views

    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    with pytest.raises(RuntimeError):
        cliente.post(reverse("usuarios"),
                      {"acao": "criar", "login": "zeca", "nome": "Zeca", "email": "zeca@exemplo.com"})
    return Usuario.objects.filter(email="zeca@teste.com").exists()


def _efeito_sobrevive_usuarios_editar(monkeypatch) -> bool:
    import contas.views_usuarios as views

    alvo = Usuario.objects.create_user(
        email="zeca@teste.com", password=SENHA, nome="Zeca")
    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    with pytest.raises(RuntimeError):
        cliente.post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Zeca Editado",
        })
    alvo.refresh_from_db()
    return alvo.first_name == "Zeca Editado"


def _efeito_sobrevive_usuarios_senha(monkeypatch) -> bool:
    import contas.views_usuarios as views

    alvo = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    with pytest.raises(RuntimeError):
        cliente.post(reverse("usuarios"), {"acao": "senha", "id": str(alvo.pk)})
    alvo.refresh_from_db()
    return not alvo.check_password(SENHA)


def _efeito_sobrevive_usuarios_desativar(monkeypatch) -> bool:
    import contas.views_usuarios as views

    alvo = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    with pytest.raises(RuntimeError):
        cliente.post(reverse("usuarios"), {"acao": "desativar", "id": str(alvo.pk)})
    alvo.refresh_from_db()
    return alvo.is_active is False


def _efeito_sobrevive_usuarios_remover(monkeypatch) -> bool:
    """Mesmo raciocínio de `_efeito_sobrevive_cargos_remover`: em
    `contas.views_usuarios.usuarios` (ação `remover`), `registrar` também
    roda ANTES do `delete()` — pela mesma razão (depois de apagado não
    sobra `alvo.username` para descrever). É `.delete()` que precisa falhar
    para exercitar a `atomic()`; forçar `registrar` nunca chegaria lá."""
    from comum.auditoria import ACOES
    from contas.models import RegistroDeAuditoria

    alvo = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    monkeypatch.setattr(Usuario, "delete", _delete_que_falha)
    cliente = _cliente_logado("admin", permissoes=("usuarios_editar",))
    with pytest.raises(RuntimeError):
        cliente.post(reverse("usuarios"), {"acao": "remover", "id": str(alvo.pk)})
    return RegistroDeAuditoria.objects.filter(
        acao=ACOES.USUARIO_REMOVIDO, alvo="zeca@teste.com").exists()


def _efeito_sobrevive_perfil_senha(monkeypatch) -> bool:
    import contas.views_perfil as views

    cliente = _cliente_logado("ana")
    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    with pytest.raises(RuntimeError):
        cliente.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": "senha-nova-123",
            "senha_confirma": "senha-nova-123",
        })
    ana = Usuario.objects.get(email="ana@teste.com")
    return not ana.check_password(SENHA)


def _efeito_sobrevive_perfil_foto(monkeypatch) -> bool:
    import contas.views_perfil as views

    ana_client = _cliente_logado("ana")
    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    with pytest.raises(RuntimeError):
        ana_client.post(reverse("perfil_foto"), {"recorte": _URL_DE_DADOS_PNG})
    ana = Usuario.objects.get(email="ana@teste.com")
    return bool(ana.avatar)


def _efeito_sobrevive_aparencia(monkeypatch) -> bool:
    import plataforma.views as views
    from plataforma.models import Marca

    monkeypatch.setattr(views, "registrar", _registrar_que_falha)
    cliente = _cliente_logado("raiz", superuser=True)
    with pytest.raises(RuntimeError):
        cliente.post(reverse("aparencia"), _PAYLOAD_DE_APARENCIA_VALIDO)
    return Marca.objects.exists()


#: Um cenário por handler mutante que cerca efeito e `registrar` no mesmo
#: `transaction.atomic()` — todo `with transaction.atomic():` do projeto
#: exceto `plataforma.views.modulos`, já pinado por
#: `TestFalhaAoRegistrarDesfazOEfeito`, acima. Cada função devolve `True` só
#: se o EFEITO sobreviveu à falha — o que a `atomic()` correta nunca deixa
#: acontecer.
#:
#: A maioria força `registrar` a falhar (mesmo golpe daquele teste,
#: generalizado). As duas ações "remover" (`cargos_remover`,
#: `usuarios_remover`) são a exceção, de propósito: nos dois handlers,
#: `registrar` roda ANTES do `delete()` (para poder descrever o que foi
#: removido) — forçar `registrar` a falhar ali nunca alcançaria o
#: `delete()`, com ou sem `atomic()`, e o teste não provaria nada sobre a
#: transação. Nesses dois, é o `.delete()` que é forçado a falhar, e o
#: efeito sob prova é o inverso: o registro de remoção (que JÁ tinha sido
#: inserido) não pode sobreviver a um `delete()` que falhou depois dele.
_HANDLERS_MUTANTES = {
    "cargos_criar": _efeito_sobrevive_cargos_criar,
    "cargos_salvar": _efeito_sobrevive_cargos_salvar,
    "cargos_remover": _efeito_sobrevive_cargos_remover,
    "usuarios_criar": _efeito_sobrevive_usuarios_criar,
    "usuarios_editar": _efeito_sobrevive_usuarios_editar,
    "usuarios_senha": _efeito_sobrevive_usuarios_senha,
    "usuarios_desativar": _efeito_sobrevive_usuarios_desativar,
    "usuarios_remover": _efeito_sobrevive_usuarios_remover,
    "perfil_senha": _efeito_sobrevive_perfil_senha,
    "perfil_foto": _efeito_sobrevive_perfil_foto,
    "aparencia": _efeito_sobrevive_aparencia,
}


@pytest.mark.django_db
class TestCadaAcaoMutanteDesfazOEfeitoSeRegistrarFalha:
    """A varredura irmã de `TestFalhaAoRegistrarDesfazOEfeito`, que só
    prova o mecanismo em `plataforma.views.modulos` — o único
    `transaction.atomic()` do projeto que tinha teste próprio. Uma mutação
    que trocasse `criar`'s `atomic()` por um `nullcontext()` (que não desfaz
    nada) deixava a suíte inteira verde: nenhum teste forçava `registrar` a
    falhar em handler nenhum além daquele. Mesmo formato de
    `TestCadaAcaoDoVocabularioRegistra`, acima: uma linha desta tabela que
    faltasse seria um handler cuja transação ninguém prova."""

    @pytest.mark.parametrize("nome_do_handler", sorted(_HANDLERS_MUTANTES))
    def test_o_efeito_nao_sobrevive_a_falha_no_registrar(
            self, nome_do_handler, monkeypatch):
        sobreviveu = _HANDLERS_MUTANTES[nome_do_handler](monkeypatch)
        assert not sobreviveu, (
            f"o efeito de {nome_do_handler!r} sobreviveu a uma falha em "
            f"`registrar` — a `atomic()` que devia cercar os dois não está "
            f"cercando, ou não existe."
        )
