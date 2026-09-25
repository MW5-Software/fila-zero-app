"""Entrar, ficar dentro, e sair.

A tela de login já existe como componente desde a entrega 1 (`LoginPage`).
O que esta tarefa acrescenta é a rota, a sessão e a saída.

Nota: o campo do identificador vem do próprio `LoginPage.campos_da_marca()`
(nucleo/layout.py), que o renderiza com `name="usuario"`. É essa chave que os
testes usam para POST — postar `login` não exerceria o mesmo caminho que um
navegador de verdade percorre. Ver task-3-report.md para o porquê.
"""

import re

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

#: O Django randomiza a máscara do token CSRF a cada chamada de `get_token`
#: (defesa contra BREACH) — o valor muda de resposta para resposta mesmo com o
#: secreto por trás sendo o mesmo. Sem normalizar isto, duas respostas iguais
#: em tudo que importa (mesmo aviso, mesmos campos) nunca bateriam byte a
#: byte. Ver task-3-report.md para o porquê.
_TOKEN_CSRF = re.compile(rb'name="csrfmiddlewaretoken" value="[^"]*"')


def _sem_variacao_do_csrf(conteudo: bytes) -> bytes:
    return _TOKEN_CSRF.sub(b'name="csrfmiddlewaretoken" value="x"', conteudo)


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        email="ana@teste.com", password="segredo-de-teste", nome="Ana",
    )


class TestATelaDeLogin:
    def test_a_tela_abre_para_quem_nao_entrou(self, db):
        resposta = Client().get(reverse("entrar"))
        assert resposta.status_code == 200

    def test_a_tela_traz_o_formulario_e_o_token_csrf(self, db):
        html = Client().get(reverse("entrar")).content.decode()
        assert "<form" in html
        assert "csrfmiddlewaretoken" in html

    def test_a_tela_carrega_a_folha_de_tema(self, db):
        html = Client().get(reverse("entrar")).content.decode()
        assert "/tema.css" in html

    def test_a_tela_de_login_nao_desenha_o_shell(self, db):
        """Login é a única tela sem barra lateral, cabeçalho e rodapé."""
        html = Client().get(reverse("entrar")).content.decode()
        assert "<aside" not in html
        assert "<footer" not in html


@pytest.mark.django_db
def test_entra_com_o_email_e_nao_com_apelido(client):
    """A prova que atravessa: a tela de entrada, o backend e a sessão.

    Existe separada das outras porque as outras já nasceram usando a fixture
    `ana` e não diriam nada se o `USERNAME_FIELD` voltasse a ser um apelido —
    elas provariam que "o valor do campo `usuario` autentica", que continua
    verdade nos dois mundos. Esta afirma o que mudou: o valor É o e-mail.
    """
    from django.contrib.auth import get_user_model

    get_user_model().objects.create_user(
        email="vera@premix.com", nome="Vera", password="segredo-de-teste")
    resposta = client.post(reverse("entrar"),
                           {"usuario": "vera@premix.com",
                            "senha": "segredo-de-teste"})
    assert resposta.status_code == 302


@pytest.mark.django_db
def test_o_apelido_sozinho_nao_entra(client):
    """O outro lado, e é ele que dá dente ao de cima: a parte antes do @ não
    é login nenhum. Sem este caso, um `USERNAME_FIELD` que aceitasse os dois
    passaria no teste acima sem ninguém notar."""
    from django.contrib.auth import get_user_model

    get_user_model().objects.create_user(
        email="vera@premix.com", nome="Vera", password="segredo-de-teste")
    resposta = client.post(reverse("entrar"),
                           {"usuario": "vera", "senha": "segredo-de-teste"})
    assert resposta.status_code == 200
    assert "Credenciais inválidas" in resposta.content.decode()


@pytest.mark.django_db
def test_o_rotulo_do_campo_diz_e_mail(client):
    """`nucleo/` emite o campo com `name="usuario"` e é porte verbatim que não
    se emenda — o que muda é o RÓTULO, posto em
    `plataforma.marca.ENTRADA_POR_EMAIL`. Uma tela que pedisse "Usuário" e
    recusasse "vera" seria a tela mentindo sobre o que ela quer."""
    html = client.get(reverse("entrar")).content.decode()
    assert 'name="usuario"' in html
    assert "E-mail" in html
    assert ">Usuário<" not in html


class TestEntrar:
    def test_credencial_certa_entra_e_redireciona(self, ana):
        c = Client()
        resposta = c.post(reverse("entrar"),
                          {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        assert resposta.status_code == 302
        assert resposta["Location"] == "/"

    def test_a_sessao_guarda_quem_entrou(self, ana):
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        assert c.session.get("usuario_id") == str(ana.pk)

    def test_senha_errada_nao_entra_e_avisa(self, ana):
        c = Client()
        resposta = c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "errada"})
        assert resposta.status_code == 200
        assert "usuario_id" not in c.session
        assert "inválidas" in resposta.content.decode()

    def test_o_aviso_nao_diz_qual_dos_dois_errou(self, ana):
        """A mesma resposta para login inexistente e senha errada."""
        c = Client()
        um = c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "errada"})
        outro = c.post(reverse("entrar"), {"usuario": "ninguem", "senha": "errada"})
        assert _sem_variacao_do_csrf(um.content) == _sem_variacao_do_csrf(outro.content)

    def test_a_senha_nao_volta_no_html(self, ana):
        """Senha errada não pode ser redesenhada dentro do formulário."""
        html = Client().post(
            reverse("entrar"), {"usuario": "ana@teste.com", "senha": "minha-senha-secreta"}
        ).content.decode()
        assert "minha-senha-secreta" not in html


class TestQuemJaEntrouNaoVeOLogin:
    """25/09/2026, o cliente: "eu tô logado e se eu acessar /entrar ele vai
    para o login, mas eu já estava logado". O GET de `/entrar` desenhava o
    formulário sem olhar a sessão, e a pessoa logada parecia deslogada."""

    def test_quem_ja_entrou_vai_para_onde_o_login_mandaria(self, ana):
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})

        resposta = c.get(reverse("entrar"))
        assert resposta.status_code == 302
        assert resposta["Location"] == "/"
        assert c.session.get("usuario_id") == str(ana.pk)

    def test_sessao_de_quem_foi_desativado_ve_o_formulario(self, ana):
        """A sessão guarda o id, mas quem decide é o banco a cada pedido: a
        pessoa desativada tem de poder ver o login, e não um laço de
        redirecionamentos entre `/entrar` e a raiz."""
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        ana.is_active = False
        ana.save()

        resposta = c.get(reverse("entrar"))
        assert resposta.status_code == 200
        assert 'name="usuario"' in resposta.content.decode()


class TestSair:
    def test_sair_esvazia_a_sessao(self, ana):
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        resposta = c.post(reverse("sair"))
        assert resposta.status_code == 302
        assert "usuario_id" not in c.session

    def test_sair_por_get_nao_derruba_a_sessao_sozinho(self, ana):
        """Sair é ação: um `<img src="/sair">` numa página qualquer não pode
        derrubar a sessão de quem abriu. GET não é 405 — é uma confirmação
        (ver `comum.confirmacao.tela_de_confirmacao`), e a sessão continua
        de pé até alguém de fato clicar o botão (POST)."""
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        resposta = c.get(reverse("sair"))
        assert resposta.status_code == 200
        assert c.session.get("usuario_id") == str(ana.pk)

    def test_sair_por_get_mostra_um_formulario_de_post_de_verdade(self, ana):
        """A confirmação precisa ser um `<form method="post">` de verdade,
        com o token de CSRF dentro — sem isso, o clique no botão nem
        chegaria a ser um POST válido."""
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        html = c.get(reverse("sair")).content.decode()

        assert f'action="{reverse("sair")}"' in html
        assert 'method="post"' in html
        assert "csrfmiddlewaretoken" in html

    def test_confirmar_a_saida_pelo_formulario_funciona(self, ana):
        """Fim a fim: GET pergunta, o POST que o formulário de fato dispara
        é o mesmo que já derrubava a sessão."""
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        c.get(reverse("sair"))  # a confirmação não muda nada sozinha

        resposta = c.post(reverse("sair"))
        assert resposta.status_code == 302
        assert "usuario_id" not in c.session


class TestOUsuarioDaSessao:
    def test_devolve_quem_entrou(self, ana):
        from comum.sessao import usuario_da_sessao

        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        pedido = c.get(reverse("entrar")).wsgi_request
        assert usuario_da_sessao(pedido).login == "ana@teste.com"

    def test_devolve_nada_para_quem_nao_entrou(self, db):
        from comum.sessao import usuario_da_sessao

        pedido = Client().get(reverse("entrar")).wsgi_request
        assert usuario_da_sessao(pedido) is None

    def test_desativar_alguem_derruba_a_sessao_aberta(self, ana):
        """`buscar` roda a cada requisição, e é isso que faz valer na hora."""
        from comum.sessao import usuario_da_sessao

        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        ana.is_active = False
        ana.save()
        pedido = c.get(reverse("entrar")).wsgi_request
        assert usuario_da_sessao(pedido) is None


class TestOCsrfEstaValendo:
    """A tranca da porta, provada — não afirmada.

    O `Client()` padrão ignora CSRF, então os outros testes de login passariam
    igual se o token sumisse do formulário. Estes dois usam
    `enforce_csrf_checks=True`, que é o comportamento real do navegador.
    """

    def test_sem_token_o_post_e_recusado(self, ana):
        c = Client(enforce_csrf_checks=True)
        resposta = c.post(reverse("entrar"),
                          {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        assert resposta.status_code == 403
        assert "usuario_id" not in c.session

    def test_com_o_token_da_propria_tela_o_post_passa(self, ana):
        """Pega o token da tela renderizada, como o navegador faria — se a
        injeção pelo `Raw` sumir, este teste fica vermelho."""
        c = Client(enforce_csrf_checks=True)
        html = c.get(reverse("entrar")).content.decode()
        token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)

        resposta = c.post(reverse("entrar"), {
            "usuario": "ana@teste.com", "senha": "segredo-de-teste",
            "csrfmiddlewaretoken": token,
        })
        assert resposta.status_code == 302
        assert c.session.get("usuario_id") == str(ana.pk)
