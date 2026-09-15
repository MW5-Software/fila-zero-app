"""A folha de tema é gerada na requisição, e os estáticos levam versão na URL.

O tema não é compilado de propósito: trocar a cor de um cliente é gravar no
banco e recarregar. Se ele virasse arquivo, mudar de cor exigiria publicar
versão nova — e a spec fecha o contrário disso.
"""

import re

import pytest
from django.test import Client
from django.urls import reverse

from nucleo.rendering import create_environment, use_environment


@pytest.fixture(autouse=True)
def ambiente():
    with use_environment(create_environment()):
        yield


@pytest.mark.django_db  # /tema.css lê a marca do banco a cada requisição (Task 5)
class TestAFolhaDeTema:
    def test_a_rota_do_tema_responde_css(self):
        resposta = Client().get(reverse("tema"))
        assert resposta.status_code == 200
        assert resposta["Content-Type"].startswith("text/css")

    def test_o_css_traz_as_custom_properties_da_marca(self):
        corpo = Client().get(reverse("tema")).content.decode()
        assert "--primary:" in corpo
        assert ":root{" in corpo

    def test_o_css_traz_a_camada_do_modo_escuro(self):
        corpo = Client().get(reverse("tema")).content.decode()
        assert ':root[data-theme="dark"]' in corpo

    def test_o_navegador_e_proibido_de_guardar_a_folha(self):
        """Tema gerado e navegador guardando dão o pior par possível: a cor
        muda no banco e o cliente continua vendo a de ontem."""
        resposta = Client().get(reverse("tema"))
        assert resposta["Cache-Control"] == "no-cache"


class TestAVersaoNaURLDoEstatico:
    def test_o_css_do_design_system_sai_com_versao(self):
        env = create_environment()
        url = env.globals["estatico"]("mw5.css")
        assert re.fullmatch(r"/static/nucleo/mw5\.css\?v=\d+", url)

    def test_arquivo_inexistente_sai_sem_versao_em_vez_de_derrubar(self):
        """A pagina tem que abrir mesmo com um caminho torto: um estatico que
        sumiu nao pode derrubar a tela inteira."""
        env = create_environment()
        assert env.globals["estatico"]("nao-existe.css") == "/static/nucleo/nao-existe.css"


class TestOsEstaticosEmProducao:
    """O container roda com DEBUG=False e gunicorn — que não serve `/static/`.

    A imagem coleta os estáticos no build (ver o Dockerfile), mas ninguém os
    ENTREGAVA: o login abria em HTML puro, sem folha nenhuma. A suíte nunca
    pegou porque roda inteira com `DJANGO_DEBUG=1`, e com DEBUG o próprio
    Django serve `/static/` — o caminho de produção nunca era exercitado.
    Quem entrega agora é o whitenoise, o caminho canônico para uma imagem
    única sem nginx na frente.
    """

    def test_o_middleware_do_whitenoise_esta_de_pe(self):
        from django.conf import settings

        # Logo depois do SecurityMiddleware: precisa ver a requisição antes
        # de qualquer coisa que redirecione.
        assert settings.MIDDLEWARE[1] == \
            "whitenoise.middleware.WhiteNoiseMiddleware"

    def test_o_estatico_responde_mesmo_com_debug_falso(self, settings):
        """A prova do defeito: com DEBUG=False, `/static/` tem que responder.
        `WHITENOISE_USE_FINDERS` é para o teste não depender de collectstatic
        — em produção os arquivos vêm do `STATIC_ROOT` coletado no build."""
        settings.DEBUG = False
        settings.WHITENOISE_USE_FINDERS = True
        resposta = Client().get("/static/nucleo/mw5.css")
        assert resposta.status_code == 200
        assert resposta["Content-Type"].startswith("text/css")

    def test_o_estatico_que_nao_existe_e_404_mesmo_sem_debug(self, settings):
        settings.DEBUG = False
        settings.WHITENOISE_USE_FINDERS = True
        resposta = Client().get("/static/nucleo/nao-existe.css")
        assert resposta.status_code == 404


class TestAsFolhasDoProjetoSaemVersionadas:
    """Sem a versão no endereço, o navegador serve a folha do CACHE depois de
    um deploy — e a tela sai quebrada só para quem já tinha visitado. É o
    defeito que vira chamado de suporte e não vira correção, porque quem
    reporta não reproduz e quem recebe não vê."""

    def test_a_folha_da_casa_leva_a_versao(self, db):
        from contas.models import Usuario
        from django.test import Client
        from django.urls import reverse

        Usuario.objects.create_superuser(email="raiz@teste.com", password="segredo-x")
        cliente = Client()
        cliente.post(reverse("entrar"),
                     {"usuario": "raiz@teste.com", "senha": "segredo-x"})
        html = cliente.get("/").content.decode()
        assert "/static/plataforma/kronos.css?v=" in html

    def test_a_folha_da_ENTRADA_leva_a_versao(self, db):
        """A tela de entrada fica fora do shell, e por isso fora do
        `montar_site` que versiona as folhas — ela pede a folha da casa com a
        própria mão, e por muito tempo pediu SEM versão.

        O efeito só aparece para quem já visitou: o navegador tem a folha
        antiga em cache e uma correção de CSS nunca chega na primeira tela.
        Foi assim que o seletor de idioma estreou sem estilo nenhum, com a
        bandeira do tamanho do cartão (10/09/2026).
        """
        from django.test import Client
        from django.urls import reverse

        html = Client().get(reverse("entrar")).content.decode()
        assert "/static/plataforma/kronos.css?v=" in html, (
            "a folha da entrada voltou a sair sem versão — quem já visitou "
            "continua vendo o CSS velho na primeira tela")

    def test_a_folha_de_uma_tela_leva_a_versao(self, db):
        from contas.models import Usuario
        from django.test import Client
        from django.urls import reverse

        Usuario.objects.create_superuser(email="raiz@teste.com", password="segredo-x")
        cliente = Client()
        cliente.post(reverse("entrar"),
                     {"usuario": "raiz@teste.com", "senha": "segredo-x"})
        html = cliente.get(reverse("usuarios")).content.decode()
        assert "/static/plataforma/listagem.css?v=" in html

    def test_endereco_de_fora_passa_direto(self):
        from comum.estaticos import versionado

        assert versionado("//cdn.exemplo/x.css") == "//cdn.exemplo/x.css"
        assert versionado("/static/a.css?v=1") == "/static/a.css?v=1"

    def test_arquivo_que_nao_existe_sai_sem_versao(self):
        """Levantar aqui derrubaria a página inteira por causa de um detalhe
        de cache."""
        from comum.estaticos import versionado

        assert versionado("/static/nao/existe.css") == "/static/nao/existe.css"
