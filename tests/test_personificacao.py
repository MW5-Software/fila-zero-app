"""Personificação: a MW5 vê o sistema como um cliente vê, sem pedir a senha
dele.

É a tarefa mais fácil de fazer errado com segurança de toda esta entrega —
por isso os testes de recusa vêm primeiro, antes de qualquer teste de
caminho feliz. Cada um prova uma forma específica de a personificação virar
uma porta para o que ela nunca deveria ser: escalada lateral para dentro da
própria conta da MW5, encadeamento que esconde quem é o original, ou uma
trilha de auditoria que mente sobre quem realmente agiu.
"""

import re

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from django.urls.resolvers import URLPattern, URLResolver

SENHA = "segredo-de-teste"

#: O marcador estável do aviso (`comum.personificacao.aviso`) — um `attrs`
#: no componente, não o texto visível, para o teste continuar valendo se a
#: cópia do aviso mudar amanhã.
MARCADOR_DO_AVISO = b'data-personificacao="aviso"'


@pytest.fixture
def raiz(db) -> Usuario:
    """Um superusuário DE TESTE, separado da `mw5` semeada — a `mw5` nasce
    sem senha utilizável (`contas.mw5.garantir_usuario_mw5`), e forçar uma
    nela só para logar neste teste confundiria com a conta de verdade que
    toda instalação semeia."""
    return Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)


@pytest.fixture
def raiz_logado(raiz) -> Client:
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
    return c


@pytest.fixture
def alvo(db) -> Usuario:
    return Usuario.objects.create_user(
        email="zeca@teste.com", password=SENHA, nome="Zeca")


@pytest.fixture
def admin_do_cliente(db) -> Usuario:
    """Um usuário COMUM com `usuarios.editar` — não um superusuário. A
    diferença é o ponto inteiro dos testes de fronteira desta suíte, mesmo
    raciocínio de `tests/test_tela_usuarios.py::pessoa_admin`."""
    pessoa = Usuario.objects.create_user(email="admin@teste.com", password=SENHA)
    pessoa.user_permissions.add(Permission.objects.get(codename="usuarios_editar"))
    return pessoa


@pytest.fixture
def admin_do_cliente_logado(admin_do_cliente) -> Client:
    c = Client()
    c.post(reverse("entrar"), {"usuario": "admin@teste.com", "senha": SENHA})
    return c


@pytest.mark.django_db
class TestSoSuperusuarioPersonifica:
    """`admin_do_cliente` tem `usuarios.editar` — a permissão que abre a
    tela de Usuários — mas não é superusuário. Se isso bastasse para
    personificar, a tela mais sensível da entrega viraria o meio de um
    admin do cliente cunhar a própria promoção por outra porta."""

    def test_admin_do_cliente_recebe_404(self, admin_do_cliente_logado, alvo):
        resposta = admin_do_cliente_logado.post(
            reverse("personificar"), {"id": str(alvo.pk)})
        assert resposta.status_code == 404

    def test_a_recusa_nao_personifica_de_fato(
        self, admin_do_cliente_logado, admin_do_cliente, alvo,
    ):
        from comum.sessao import CHAVE_ALVO

        admin_do_cliente_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        assert CHAVE_ALVO not in admin_do_cliente_logado.session

    def test_iniciar_recusa_sozinho_sem_depender_so_da_rota(
        self, admin_do_cliente, alvo,
    ):
        """A rota (`@exigir_permissao("mw5.personificar")`) já barra
        `admin_do_cliente` antes de `iniciar` rodar uma linha — o que faz
        este teste específico nunca ficar vermelho se só a GUARDA quebrar,
        sem `iniciar` ter mudado nada. Chamar `iniciar` direto, por fora da
        rota, é o que prova a defesa em profundidade que o docstring da
        função promete: mesmo sem a guarda, a função recusa sozinha."""
        from django.test import RequestFactory

        from comum.personificacao import PersonificacaoRecusada, iniciar
        from comum.sessao import CHAVE

        pedido = RequestFactory().post("/personificar")
        pedido.session = {CHAVE: str(admin_do_cliente.pk)}
        with pytest.raises(PersonificacaoRecusada):
            iniciar(pedido, str(alvo.pk))


@pytest.mark.django_db
class TestNinguemPersonificaUmSuperusuario:
    """Sem esta trava, personificação vira um segundo caminho de escalada
    lateral para dentro da própria conta da MW5 — mesmo entre duas contas
    de superusuário."""

    def test_alvo_superusuario_recebe_404(self, raiz_logado, db):
        outro = Usuario.objects.create_superuser(email="outro@teste.com", password=SENHA)
        resposta = raiz_logado.post(reverse("personificar"), {"id": str(outro.pk)})
        assert resposta.status_code == 404

    def test_a_recusa_nao_personifica_de_fato(self, raiz_logado, raiz, db):
        from comum.sessao import CHAVE_ALVO

        outro = Usuario.objects.create_superuser(email="outro@teste.com", password=SENHA)
        raiz_logado.post(reverse("personificar"), {"id": str(outro.pk)})
        assert CHAVE_ALVO not in raiz_logado.session


@pytest.mark.django_db
class TestNaoEncadeia:
    """Quem já personifica alguém e consegue personificar de novo apaga o
    rastro de quem era o original de verdade — a segunda personificação
    substituiria a primeira, e ninguém mais saberia dizer quem começou."""

    def test_a_segunda_tentativa_recebe_404(self, raiz_logado, alvo, db):
        outro_alvo = Usuario.objects.create_user(
            email="mario@teste.com", password=SENHA)
        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})

        resposta = raiz_logado.post(
            reverse("personificar"), {"id": str(outro_alvo.pk)})

        assert resposta.status_code == 404

    def test_o_alvo_continua_sendo_o_primeiro(self, raiz_logado, alvo, db):
        from comum.sessao import CHAVE_ALVO

        outro_alvo = Usuario.objects.create_user(
            email="mario@teste.com", password=SENHA)
        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        raiz_logado.post(reverse("personificar"), {"id": str(outro_alvo.pk)})

        assert raiz_logado.session[CHAVE_ALVO] == str(alvo.pk)

    def test_iniciar_recusa_sozinho_sem_depender_so_da_rota(self, raiz, alvo, db):
        """Mesmo raciocínio do teste homônimo em `TestSoSuperusuarioPersonifica`:
        a rota já barra a segunda tentativa porque `usuario_da_sessao`
        devolve o ALVO (nunca superusuário) enquanto a primeira
        personificação dura — o que deixaria uma quebra dentro de `iniciar`
        sem nenhum teste que a pegasse. Chamar `iniciar` direto, com uma
        sessão que já personifica, prova a recusa da própria função."""
        from django.test import RequestFactory

        from comum.personificacao import PersonificacaoRecusada, iniciar
        from comum.sessao import CHAVE, CHAVE_ALVO

        outro_alvo = Usuario.objects.create_user(
            email="mario@teste.com", password=SENHA)
        pedido = RequestFactory().post("/personificar")
        pedido.session = {CHAVE: str(raiz.pk), CHAVE_ALVO: str(alvo.pk)}
        with pytest.raises(PersonificacaoRecusada):
            iniciar(pedido, str(outro_alvo.pk))


@pytest.mark.django_db
class TestVoltarASerEu:
    def test_encerra_a_personificacao(self, raiz_logado, alvo):
        from comum.sessao import CHAVE_ALVO

        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        assert CHAVE_ALVO in raiz_logado.session

        raiz_logado.post(reverse("voltar_a_ser_eu"))
        assert CHAVE_ALVO not in raiz_logado.session

    def test_restaura_o_acesso_a_uma_tela_so_da_mw5(self, raiz_logado, alvo):
        """Prova indireta, mas concreta, de que a identidade efetiva volta a
        ser a do original: `mw5.modulos` só abre para superusuário (ver
        `TestTelasDaMw5FechadasAoPersonificar`), e fica fechada enquanto
        `alvo` (usuário comum) é quem a sessão personifica."""
        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        assert raiz_logado.get(reverse("modulos")).status_code == 404

        raiz_logado.post(reverse("voltar_a_ser_eu"))
        assert raiz_logado.get(reverse("modulos")).status_code == 200

    def test_o_original_restaurado_e_lido_do_banco_de_novo(self, raiz_logado, alvo, raiz):
        """"Voltar a ser eu" não pode devolver um retrato congelado de quem
        entrou no login: tem que ler o original DE NOVO no banco, a cada
        requisição — mesmo raciocínio de `contas.backend.BackendDjango.buscar`.
        Provado mudando `raiz` DEPOIS da personificação já ter terminado, e
        checando que a mudança aparece sem exigir um novo login."""
        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        raiz_logado.post(reverse("voltar_a_ser_eu"))

        raiz.nome = "Raiz Renomeada Depois"
        raiz.save(update_fields=["nome"])

        html = raiz_logado.get(reverse("usuarios")).content.decode()
        assert "Raiz Renomeada Depois" in html


@pytest.mark.django_db
class TestLoginLimpaPersonificacaoOrfa:
    """Achado da revisão externa: `entrar_na_sessao` gravava `CHAVE`, mas
    nunca apagava `CHAVE_ALVO` — uma sessão que já personificava, ao
    receber um SEGUNDO login válido (de OUTRA pessoa, na mesma sessão),
    ficava com `{usuario_id: <quem logou agora>, usuario_personificado_id:
    <quem a sessão personificava antes>}`. Como `usuario_da_sessao` prefere
    `CHAVE_ALVO`, quem acabou de logar passaria a ver as telas de quem a
    sessão personificava antes dele — e qualquer ação sua gravaria uma
    trilha que afirma algo falso: que ELE personificou o alvo, quando nunca
    chamou a rota `personificar` nem tinha a permissão para isso. Reproduz
    os três passos exatos do relator."""

    def test_o_segundo_login_nao_herda_a_personificacao_do_primeiro(
        self, alvo, db,
    ):
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria
        from comum.sessao import CHAVE, CHAVE_ALVO

        raiz = Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)
        mario = Usuario.objects.create_user(email="mario@teste.com", password=SENHA)

        sessao = Client()
        sessao.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
        sessao.post(reverse("personificar"), {"id": str(alvo.pk)})
        assert sessao.session[CHAVE_ALVO] == str(alvo.pk)

        # SEM encerrar a personificação em curso, `mario` loga NA MESMA
        # sessão, com a própria senha válida — o cenário exato do relator.
        sessao.post(reverse("entrar"), {"usuario": "mario@teste.com", "senha": SENHA})

        assert CHAVE_ALVO not in sessao.session
        assert sessao.session[CHAVE] == str(mario.pk)

        # `mario` vê a PRÓPRIA identidade, não a de `zeca` (nome "Zeca" só
        # apareceria no cabeçalho se a sessão ainda estivesse personificando).
        html = sessao.get("/").content.decode()
        assert "Zeca" not in html

        # Qualquer ação de `mario` a partir daqui grava em nome DELE, nunca
        # de `zeca` — a trilha de auditoria não pode afirmar que `zeca` fez
        # algo, nem que `mario` personificou alguém.
        sessao.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": "senha-nova-123",
            "senha_confirma": "senha-nova-123",
        })
        registro = RegistroDeAuditoria.objects.get(acao=ACOES.SENHA_TROCADA)
        assert registro.autor_login == "mario@teste.com"
        assert registro.detalhe == ""
        assert not RegistroDeAuditoria.objects.filter(autor_login="zeca@teste.com").exists()

    def test_o_login_tambem_fecha_a_janela_na_trilha_de_auditoria(
        self, alvo, db,
    ):
        """A limpeza de sessão sozinha (teste acima) não bastava: um
        `.pop(CHAVE_ALVO, None)` cru fechava a personificação sem deixar
        `PERSONIFICACAO_ENCERRADA` nenhum — a janela em que `raiz` agiu como
        `zeca` ficava sem fim registrado, mesmo com a sessão já sã de novo."""
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        raiz = Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)
        mario = Usuario.objects.create_user(email="mario@teste.com", password=SENHA)

        sessao = Client()
        sessao.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
        sessao.post(reverse("personificar"), {"id": str(alvo.pk)})

        sessao.post(reverse("entrar"), {"usuario": "mario@teste.com", "senha": SENHA})

        registro = RegistroDeAuditoria.objects.get(acao=ACOES.PERSONIFICACAO_ENCERRADA)
        assert registro.autor_login == "raiz@teste.com"
        assert registro.alvo == "zeca@teste.com"


@pytest.mark.django_db
class TestOCookieAdulteradoNaoViraSessao:
    """A sessão vive no banco (`SESSION_ENGINE` não é sobrescrito em
    `config/settings.py` — o padrão do Django é `db`); o cookie carrega só a
    chave de sessão, e não existe valor de personificação nele para
    adulterar. A prova que importa não é "a assinatura resiste" — é que um
    valor editado não vira sessão NENHUMA, personificando ou não."""

    def test_valor_editado_cai_para_o_login(self, raiz_logado, alvo):
        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})

        valor_de_verdade = raiz_logado.cookies[settings.SESSION_COOKIE_NAME].value
        ultimo = valor_de_verdade[-1]
        adulterado = valor_de_verdade[:-1] + ("0" if ultimo != "0" else "1")

        cliente_adulterado = Client()
        cliente_adulterado.cookies[settings.SESSION_COOKIE_NAME] = adulterado
        resposta = cliente_adulterado.get("/")

        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]


@pytest.mark.django_db
class TestAuditoria:
    def test_inicio_registra_o_original_como_autor_e_o_alvo_como_alvo(
        self, raiz_logado, alvo,
    ):
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})

        registro = RegistroDeAuditoria.objects.get(acao=ACOES.PERSONIFICACAO_INICIADA)
        assert registro.autor_login == "raiz@teste.com"
        assert registro.alvo == "zeca@teste.com"

    def test_fim_registra_o_original_como_autor_e_o_alvo_como_alvo(
        self, raiz_logado, alvo,
    ):
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        raiz_logado.post(reverse("voltar_a_ser_eu"))

        registro = RegistroDeAuditoria.objects.get(acao=ACOES.PERSONIFICACAO_ENCERRADA)
        assert registro.autor_login == "raiz@teste.com"
        assert registro.alvo == "zeca@teste.com"

    def test_acao_feita_personificando_leva_a_nota_de_quem_realmente_agia(
        self, raiz_logado, alvo,
    ):
        """A linha continua atribuída ao ALVO (`autor_login` == "zeca") —
        foi em nome dele que a troca de senha aconteceu, e é isso que quem
        lê a tela dele mais tarde precisa ver. Mas sem a nota em `detalhe`,
        a trilha diria que `zeca` decidiu trocar a própria senha sozinho,
        quando foi `raiz` personificando-o — exatamente a mentira por
        omissão que esta nota existe para fechar."""
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        raiz_logado.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": "senha-nova-123",
            "senha_confirma": "senha-nova-123",
        })

        registro = RegistroDeAuditoria.objects.get(acao=ACOES.SENHA_TROCADA)
        assert registro.autor_login == "zeca@teste.com"
        assert "raiz" in registro.detalhe


@pytest.mark.django_db
class TestOMenuEODoAlvo:
    def test_o_menu_e_o_do_alvo_nao_o_do_superusuario(self, raiz_logado, alvo):
        """Prova pela AUSÊNCIA, não pela presença: `raiz` (superusuário) vê
        "Usuários" no menu por causa do atalho de `pode()` para
        superusuário (`nucleo.permissoes.pode`) — mesmo sem ter
        `usuarios.editar` marcada em lugar nenhum. `alvo` não tem NENHUMA
        permissão. Se o item continuasse aparecendo depois de
        `personificar`, o menu desenhado ainda seria o de `raiz` — o item
        só some se `plataforma.menu.montar` estiver mesmo recebendo o
        `User` do alvo."""
        antes = raiz_logado.get("/").content.decode()
        assert "Usuários" in antes

        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})

        durante = raiz_logado.get("/").content.decode()
        assert "Usuários" not in durante


@pytest.mark.django_db
class TestTelasDaMw5FechadasAoPersonificar:
    """Já decorre do desenho, sem mecanismo novo nenhum: `usuario_da_sessao`
    devolve o ALVO enquanto personifica, o alvo nunca é superusuário
    (`alvo_personificavel` filtra `is_superuser=False`), e `pode()` só
    libera `mw5.*` para superusuário — a permissão nunca é concedível por
    `Perfil` porque "mw5" não é um módulo declarado em `plataforma.declaracao`
    (ver `contas.backend.permissoes_de`). Estes testes provam o que já é
    verdade, em vez de acrescentar uma segunda trava por cima."""

    def test_aparencia_fecha_personificando(self, raiz_logado, alvo):
        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        assert raiz_logado.get(reverse("aparencia")).status_code == 404

    def test_modulos_fecha_personificando(self, raiz_logado, alvo):
        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        assert raiz_logado.get(reverse("modulos")).status_code == 404


@pytest.mark.django_db
class TestOOriginalERecheckadoACadaRequisicao:
    """Achado da revisão final do branch: `usuario_da_sessao` honrava
    `CHAVE_ALVO` sem nunca voltar a checar o original — uma vez a
    personificação em curso, com o alvo resolvendo, a função devolvia o
    alvo direto, sem perguntar de novo se quem personifica ainda pode. Duas
    formas concretas de essa falta custar caro, e as duas cobertas aqui:
    desativar o original não derruba nada (a sessão segue navegando como o
    alvo), e rebaixá-lo — tirar o superusuário, sem desativar a conta —
    também não: a sessão continua vendo e agindo como o alvo mesmo depois
    de a autoridade que abriu a personificação ter sumido."""

    def test_original_desativado_nao_navega_mais_como_o_alvo(self, raiz, alvo):
        from django.test import RequestFactory
        from comum.sessao import CHAVE, CHAVE_ALVO, usuario_da_sessao

        pedido = RequestFactory().get("/")
        pedido.session = {CHAVE: str(raiz.pk), CHAVE_ALVO: str(alvo.pk)}
        # Sanidade: a personificação está mesmo em curso antes da mutação.
        assert usuario_da_sessao(pedido).login == "zeca@teste.com"

        raiz.is_active = False
        raiz.save(update_fields=["is_active"])

        assert usuario_da_sessao(pedido) is None

    def test_original_rebaixado_deixa_de_ser_visto_como_o_alvo(self, raiz, alvo):
        from django.test import RequestFactory
        from comum.sessao import CHAVE, CHAVE_ALVO, usuario_da_sessao

        pedido = RequestFactory().get("/")
        pedido.session = {CHAVE: str(raiz.pk), CHAVE_ALVO: str(alvo.pk)}
        # Sanidade: a personificação está mesmo em curso antes da mutação.
        assert usuario_da_sessao(pedido).login == "zeca@teste.com"

        raiz.is_superuser = False
        raiz.save(update_fields=["is_superuser"])

        vista = usuario_da_sessao(pedido)
        assert vista is not None
        assert vista.login == "raiz@teste.com"


@pytest.mark.django_db
class TestSairEnquantoPersonifica:
    """Achado da revisão final do branch: `sair` lia `usuario_da_sessao` —
    o ALVO, enquanto a personificação dura — e gravava `SAIU` em nome dele.
    A trilha dizia que `zeca` saiu, quando ele nunca chamou a rota nem
    esteve aqui de verdade, e nenhuma linha fechava a personificação em
    curso: a janela em que `raiz` agiu como `zeca` ficava aberta para
    sempre no papel, mesmo com a sessão inteira já derrubada."""

    def test_saiu_e_registrado_em_nome_do_original_nao_do_alvo(
        self, raiz_logado, alvo,
    ):
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        raiz_logado.post(reverse("sair"))

        registro = RegistroDeAuditoria.objects.get(acao=ACOES.SAIU)
        assert registro.autor_login == "raiz@teste.com"
        assert registro.alvo == "raiz@teste.com"

    def test_sair_tambem_encerra_a_personificacao_na_trilha(
        self, raiz_logado, alvo,
    ):
        from comum.auditoria import ACOES
        from contas.models import RegistroDeAuditoria

        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})
        raiz_logado.post(reverse("sair"))

        registro = RegistroDeAuditoria.objects.get(
            acao=ACOES.PERSONIFICACAO_ENCERRADA)
        assert registro.autor_login == "raiz@teste.com"
        assert registro.alvo == "zeca@teste.com"


class TestARotaDePersonificarNaoFicaSemGuarda:
    """Achado da revisão final do branch: a Task 11 pinou a checagem
    INTERNA de `iniciar` (com `RequestFactory`, nas classes acima), mas
    nenhum teste pinava a guarda EXTERNA da rota — trocar
    `@exigir_permissao("mw5.personificar")` por `@exigir_login` em
    `contas.views.personificar` deixava a suíte inteira verde, porque
    `iniciar` já recusa sozinha quem não é superusuário. O docstring do
    módulo (`contas/personificacao.py`) é claro: a tela mais sensível desta
    entrega não pode ficar de pé em cima de uma guarda só. Este teste
    cobre a camada que ficava descoberta."""

    def test_a_view_carrega_a_permissao_certa(self):
        from contas.views import personificar

        assert getattr(personificar, "permissao", None) == "mw5.personificar"


@pytest.mark.django_db
class TestAsDuasRotasSoAceitamPost:
    """Mesmo raciocínio de `contas.views.sair`: um link ou uma tag `<img>`
    numa página qualquer não pode disparar personificação nenhuma."""

    def test_personificar_recusa_get(self, raiz_logado):
        assert raiz_logado.get(reverse("personificar")).status_code == 405

    def test_voltar_a_ser_eu_recusa_get(self, raiz_logado):
        assert raiz_logado.get(reverse("voltar_a_ser_eu")).status_code == 405


def _caminho_concreto(padrao: URLPattern) -> "str | None":
    """O caminho de verdade de `padrao`, com qualquer conversor de rota
    (`<int:...>`, `<str:...>`) trocado por um valor de mentira — só existe
    um caso destes no projeto inteiro (`avatar/<int:usuario_id>`), e ele nem
    entra na varredura (não é HTML — ver o filtro de `Content-Type` abaixo).
    """
    rota = str(padrao.pattern)

    def _valor_de_mentira(m: "re.Match") -> str:
        return {"int": "1", "slug": "x", "uuid":
                 "00000000-0000-0000-0000-000000000000"}.get(m.group(1), "x")

    return re.sub(r"<(\w+):\w+>", _valor_de_mentira, rota)


def _rotas_com_caminho():
    """Toda rota do projeto, como `(nome, caminho)` — caminha
    `get_resolver().url_patterns` recursivamente, nunca `reverse()`, mesmo
    motivo de `tests/test_guarda.py::_rotas_do_projeto`: uma rota com
    argumento faria `reverse()` sem args levantar, e a varredura pularia a
    rota em silêncio. Nenhum `include()` deste projeto tem prefixo
    (`config/urls.py` monta todos com `path("", include(...))`), então o
    padrão da própria rota já é o caminho inteiro.
    """
    from django.urls import get_resolver

    def caminhar(padroes):
        for padrao in padroes:
            if isinstance(padrao, URLResolver):
                yield from caminhar(padrao.url_patterns)
            elif isinstance(padrao, URLPattern):
                yield padrao.name, _caminho_concreto(padrao)

    return list(caminhar(get_resolver().url_patterns))


@pytest.mark.django_db
class TestOAvisoApareceEmTodaTela:
    """A varredura irmã de `tests/test_guarda.py`: para toda rota que
    responde 200 a um GET enquanto a sessão personifica, o aviso
    (`comum.personificacao.aviso`) tem que estar na resposta. Uma tela nova
    que esqueça de chamar o helper vira teste vermelho aqui — no lugar de
    alguém fazer besteira em nome de outra pessoa sem perceber que está
    personificando."""

    #: Rotas onde a ausência do aviso é aceitável, e o motivo de cada uma —
    #: mesmo espírito de `comum.guardas_de_acesso.TELAS_ABERTAS`: uma lista curta,
    #: com o motivo ao lado, para "esqueci" nunca virar razão de entrar aqui.
    ISENTAS = frozenset({
        # A tela de login: sempre 200 a um GET, com ou sem sessão de
        # personificação em curso, porque não lê `request.usuario` nenhum
        # para decidir o que desenhar — é `LoginPage` fora do shell
        # (`chrome=False`), não a tela autenticada que o aviso protege.
        "entrar",
        # `sair`, por GET, é a confirmação "tem certeza?"
        # (`comum.confirmacao.tela_de_confirmacao`) — mesma razão de
        # `entrar`: roda fora do shell (`Page` direto, sem `Site`), de
        # propósito, porque `sair` também precisa funcionar com sessão
        # quebrada ou inexistente (`comum.guardas_de_acesso.TELAS_ABERTAS`), e uma
        # tela que dependesse de `request.usuario` para montar o aviso
        # quebraria justo nesse caso. `filial_trocar` usa a mesma tela de
        # confirmação, mas não entra aqui: o GET dela só chega a 200 com um
        # `?filial=` válido, que este teste genérico nunca manda — nada a
        # isentar na prática.
        "sair",
    })
    # `demonstracao` (`nucleo/views.py`, a home em "/") NÃO está isenta:
    # apesar de viver dentro de `nucleo/`, é a única view daquele pacote que
    # este projeto escreve (importa de `contas/`, o que nenhum arquivo
    # portado do design system faz) — o congelamento desta tarefa nunca
    # cobriu este arquivo. Ver `task-11-report.md` (adendo) para a decisão.

    def test_toda_rota_200_mostra_o_aviso(self, raiz_logado, alvo):
        # Um alvo com o máximo de telas alcançáveis, para a varredura
        # exercitar de verdade — não só passar por não ter achado nada.
        # Pelo cargo: desde a virada, a permissão direta de um membro não vale.
        from tests.conftest import dar_permissoes

        dar_permissoes(alvo, "usuarios_editar", "cargos_editar", "exemplo_ver")

        from plataforma.models import Modulo
        Modulo.objects.filter(chave="exemplo").update(ativo=True)

        raiz_logado.post(reverse("personificar"), {"id": str(alvo.pk)})

        sem_aviso = []
        for nome, caminho in _rotas_com_caminho():
            if nome in self.ISENTAS:
                continue
            resposta = raiz_logado.get("/" + caminho)
            if resposta.status_code != 200:
                continue
            if not resposta.get("Content-Type", "").startswith("text/html"):
                continue
            if MARCADOR_DO_AVISO not in resposta.content:
                sem_aviso.append(nome or f"<rota sem nome: {caminho!r}>")

        assert not sem_aviso, (
            f"rotas 200 sem o aviso de personificação: {sem_aviso}. Ou "
            f"chame `comum.personificacao.aviso(request)` no `content=` da "
            f"tela, ou justifique a isenção em `ISENTAS`."
        )


@pytest.mark.django_db
class TestAApiAvisaEmTodaResposta:
    """O equivalente, para a API, do aviso que toda tela mostra.

    Um cabeçalho em TODA resposta de `/api/`, e não um campo em cada schema:
    campo se esquece numa operação nova; o middleware não tem como esquecer.
    """

    def _personificar(self, alvo):
        from tests.conftest import cliente_da_api, sessao_do_token

        api, token = cliente_da_api("raiz@teste.com", SENHA)
        sessao = sessao_do_token(token)
        sessao["usuario_personificado_id"] = str(alvo.pk)
        sessao.save()
        return api

    def _caminhos_sem_parametro(self):
        from tests.conftest import operacoes_da_api

        return sorted({caminho for caminho, op in operacoes_da_api()
                       if "GET" in op.methods and "{" not in caminho})

    def test_toda_operacao_leva_o_aviso(self, raiz, alvo):
        api = self._personificar(alvo)
        caminhos = [*self._caminhos_sem_parametro(), "/api/nao-existe"]
        assert len(caminhos) > 1
        for caminho in caminhos:
            assert api.get(caminho).get("X-Vendo-Como") == str(alvo.guid), caminho

    def test_sem_personificacao_nao_ha_aviso(self, raiz):
        from tests.conftest import cliente_da_api

        api, token = cliente_da_api("raiz@teste.com", SENHA)
        assert "X-Vendo-Como" not in api.get("/api/v1/eu")

    def test_original_rebaixado_perde_o_aviso(self, raiz, alvo):
        api = self._personificar(alvo)
        Usuario.objects.filter(pk=raiz.pk).update(is_superuser=False)
        assert "X-Vendo-Como" not in api.get("/api/v1/eu")
