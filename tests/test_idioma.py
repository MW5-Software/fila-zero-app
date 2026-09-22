"""O seletor de idioma: a moldura em castelhano, o catálogo como está.

O portal vai ser vendido no Paraguai. O que muda de língua é o SISTEMA —
menu, botões, mensagens. O catálogo não: nome de peça, família e aplicação
são dado que o cliente digitou, moram em linha de tabela, e nenhum arquivo de
tradução alcança linha de tabela. Estes testes fixam as duas metades, porque
a segunda é a que vira reclamação de defeito se ninguém tiver escrito que é
assim de propósito.
"""

import pytest
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import translation

from comum.idioma import CHAVE_IDIOMA, idioma_da_requisicao
from contas.models import Nivel, Usuario
from plataforma.models import Empresa
from tests.conftest import por_na_conta

SENHA = "segredo-de-teste"


@pytest.fixture
def pessoa(db):
    quem = Usuario.objects.create_user(
        email="dona@teste.com", password=SENHA, nivel=Nivel.TITULAR)
    Empresa.objects.create(razao_social="Normadin", dono=quem)
    return quem


@pytest.fixture
def logada(pessoa):
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": pessoa.email, "senha": SENHA})
    return cliente


class TestDeOndeVemOIdioma:
    def test_sem_nada_vale_o_padrao_da_instalacao(self):
        pedido = RequestFactory().get("/")
        pedido.session = {}
        assert idioma_da_requisicao(pedido) == "pt-br"

    def test_a_sessao_decide(self):
        pedido = RequestFactory().get("/")
        pedido.session = {CHAVE_IDIOMA: "es"}
        assert idioma_da_requisicao(pedido) == "es"

    def test_idioma_que_nao_existe_e_ignorado(self):
        """`translation.activate("xx")` não falha — ativa um catálogo vazio, e
        a tela sai com as frases em branco. Um código inventado na barra de
        endereço não pode chegar lá."""
        pedido = RequestFactory().get("/")
        pedido.session = {CHAVE_IDIOMA: "xx"}
        assert idioma_da_requisicao(pedido) == "pt-br"

    @pytest.mark.django_db
    def test_a_coluna_da_pessoa_vale_quando_a_sessao_nao_diz(self, pessoa):
        """A sessão da CASA (`usuario_id`), e não `request.user`: aqui o
        login não é o do `django.contrib.auth`, e para o middleware do Django
        todo mundo neste sistema é anônimo."""
        from comum.sessao import CHAVE

        pessoa.idioma = "es"
        pessoa.save(update_fields=["idioma"])
        pedido = RequestFactory().get("/")
        pedido.session = {CHAVE: pessoa.pk}

        assert idioma_da_requisicao(pedido) == "es"

    @pytest.mark.django_db
    def test_a_escolha_de_agora_vence_a_coluna(self, pessoa):
        """"Escolhi agora, vale agora" — e é o que faz a escolha feita na
        tela de ENTRADA continuar valendo depois do login."""
        from comum.sessao import CHAVE

        pessoa.idioma = "pt-br"
        pessoa.save(update_fields=["idioma"])
        pedido = RequestFactory().get("/")
        pedido.session = {CHAVE: pessoa.pk, CHAVE_IDIOMA: "es"}

        assert idioma_da_requisicao(pedido) == "es"


@pytest.mark.django_db
class TestATrocaPelaTela:
    def test_o_perfil_oferece_os_dois(self, logada):
        html = logada.get(reverse("perfil")).content.decode()
        assert "Português" in html
        assert "Español" in html

    def test_trocar_grava_na_pessoa_e_volta(self, logada, pessoa):
        resposta = logada.post(reverse("idioma"),
                               {"idioma": "es", "voltar": "/perfil"})

        pessoa.refresh_from_db()
        assert pessoa.idioma == "es"
        assert resposta.status_code == 302
        assert resposta["Location"] == "/perfil"

    def test_a_tela_seguinte_ja_vem_em_castelhano(self, logada):
        logada.post(reverse("idioma"), {"idioma": "es", "voltar": "/perfil"})

        html = logada.get(reverse("perfil")).content.decode()
        assert "Mi Perfil" in html
        assert "Meu Perfil" not in html, (
            "sobrou português na tela — se a frase vier do `nucleo`, ela "
            "precisa entrar por PARÂMETRO (o design system é porte verbatim "
            "e não se emenda), como `titulo=` e o menu do avatar já fazem")

    def test_idioma_inventado_nao_grava(self, logada, pessoa):
        logada.post(reverse("idioma"), {"idioma": "klingon"})

        pessoa.refresh_from_db()
        assert pessoa.idioma == "pt-br"

    def test_so_por_post(self, logada):
        """Trocar idioma muda estado da conta: um `<img src="/idioma">` numa
        página qualquer não pode trocar o idioma de quem a abrir."""
        assert logada.get(reverse("idioma")).status_code == 405

    @pytest.mark.parametrize("fora", ["/\\outro.site", "//outro.site", "/\t/outro.site"])
    def test_barra_invertida_tambem_e_fora_de_casa(self, logada, fora):
        """`/\\outro.site` começa com `/` e não com `//`, e passava na trava; o
        navegador lê a barra invertida como barra, e descarta o tab de
        `/\\t/outro.site`, e nos dois casos vai para o outro host (auditoria de
        21/09/2026)."""
        resposta = logada.post(reverse("idioma"), {"idioma": "es", "voltar": fora})
        assert resposta["Location"] == "/"

    def test_voltar_para_fora_de_casa_e_recusado(self, logada):
        """`?voltar=https://outro.site` faria desta rota um trampolim: o link
        sai do nosso domínio e quem clicou jura que estava dentro do
        sistema."""
        resposta = logada.post(reverse("idioma"),
                               {"idioma": "es", "voltar": "https://outro.site"})
        assert resposta["Location"] == "/"

    def test_precisa_estar_logado(self):
        resposta = Client().post(reverse("idioma"), {"idioma": "es"})
        assert resposta.status_code in (302, 404)


@pytest.mark.django_db
class TestOBotaoDoCabecalho:
    """O seletor mora no cabeçalho, à esquerda do sino — pedido de 09/09/2026.

    Antes ele existia só em Meu Perfil, que é onde a preferência é gravada.
    Duas telas de distância para uma escolha que a pessoa faz olhando a tela
    errada é uma a mais.
    """

    def _bloco(self, cliente, rota="perfil"):
        html = cliente.get(reverse(rota)).content.decode()
        inicio = html.index('<form class="idioma-botao"')
        return html, html[inicio:html.index("</form>", inicio)]

    def _resumo(self, bloco):
        """Só o `<summary>` — o que se vê com o menu FECHADO."""
        return bloco[bloco.index("<summary"):bloco.index("</summary>")]

    def test_aparece_ao_lado_do_sino(self, logada):
        html, _bloco = self._bloco(logada)
        canto = html[html.index('class="h-actions"'):]
        assert canto.index("idioma-botao") < canto.index("data-notifications"), (
            "o seletor de idioma não está ANTES do sino no canto direito")

    def test_fechado_mostra_a_bandeira_de_ONDE_SE_ESTA(self, logada):
        """A primeira versão mostrava para onde o clique levava, e estava
        errada: com a tela inteira em português, um "ES" no canto faz a
        pessoa achar que está em castelhano."""
        from plataforma.idioma_no_cabecalho import BANDEIRAS

        _html, bloco = self._bloco(logada)
        resumo = self._resumo(bloco)

        assert str(BANDEIRAS["pt-br"]) in resumo
        assert str(BANDEIRAS["es"]) not in resumo

    def test_tem_seta_porque_tem_menu(self, logada):
        """A seta é o que conta que existem outras línguas. Ela só pode
        existir porque existe menu de verdade — seta sem menu é a tela
        prometendo o que não cumpre."""
        _html, bloco = self._bloco(logada)

        assert "idioma-seta" in self._resumo(bloco)
        assert "<details" in bloco

    def test_o_menu_lista_todos_os_idiomas(self, logada):
        from django.conf import settings

        _html, bloco = self._bloco(logada)
        painel = bloco[bloco.index('class="idioma-opcoes"'):]

        for codigo, rotulo in settings.LANGUAGES:
            assert f'value="{codigo}"' in painel
            assert str(rotulo) in painel

    def test_o_idioma_corrente_vem_marcado_no_menu(self, logada):
        _html, bloco = self._bloco(logada)
        painel = bloco[bloco.index('class="idioma-opcoes"'):]
        atual = painel[painel.index('value="pt-br"'):]

        assert 'aria-current="true"' in atual[:200]

    def test_depois_de_trocar_a_bandeira_fechada_vira_a_outra(self, logada):
        from plataforma.idioma_no_cabecalho import BANDEIRAS

        logada.post(reverse("idioma"), {"idioma": "es", "voltar": "/perfil"})
        _html, bloco = self._bloco(logada)

        assert str(BANDEIRAS["es"]) in self._resumo(bloco)

    def test_volta_para_a_pagina_onde_a_pessoa_estava(self, logada):
        """A tela do catálogo trocando de idioma não pode devolver a pessoa
        na home — ela estava procurando uma peça."""
        _html, bloco = self._bloco(logada)
        assert 'name="voltar" value="/perfil"' in bloco

    def test_quem_nao_entrou_nao_ve_o_botao(self):
        """Sem conta não há onde gravar. A tela de entrada tem a escolha
        dela, em link, pelo motivo escrito em `contas/views_idioma.py`."""
        html = Client().get(reverse("entrar")).content.decode()
        assert "idioma-botao" not in html

    def test_o_menu_e_um_formulario_com_token(self, logada):
        """Trocar idioma grava na conta: `<img src="/idioma">` numa página
        qualquer não pode trocar o idioma de quem a abrir."""
        _html, bloco = self._bloco(logada)

        assert 'method="post"' in bloco
        assert 'action="/idioma"' in bloco
        assert "csrfmiddlewaretoken" in bloco


@pytest.mark.django_db
class TestATelaDeEntrada:
    def test_oferece_o_outro_idioma(self):
        html = Client().get(reverse("entrar")).content.decode()
        assert "Español" in html
        assert "?idioma=es" in html

    def test_o_link_troca_e_a_entrada_muda_de_lingua(self):
        cliente = Client()
        cliente.get(reverse("entrar") + "?idioma=es")

        assert cliente.session[CHAVE_IDIOMA] == "es"
        html = cliente.get(reverse("entrar")).content.decode()
        assert "Português" in html

    def test_a_escolha_atravessa_o_login(self, pessoa):
        """O caso do cliente paraguaio: escolheu na porta, entrou, e o
        sistema continua falando com ele."""
        cliente = Client()
        cliente.get(reverse("entrar") + "?idioma=es")
        cliente.post(reverse("entrar"),
                     {"usuario": pessoa.email, "senha": SENHA})

        html = cliente.get(reverse("perfil")).content.decode()
        assert "Mi Perfil" in html



def test_o_idioma_nao_vaza_de_uma_requisicao_para_a_outra(db):
    """A ativação do Django é por THREAD, e o servidor reaproveita threads.
    Sem o `finally` do middleware, a requisição seguinte herdaria o
    castelhano de quem passou antes — defeito que não aparece em
    desenvolvimento (uma pessoa só) e em produção vira "a tela mudou de
    idioma sozinha"."""
    cliente = Client()
    cliente.get(reverse("entrar") + "?idioma=es")
    cliente.get(reverse("entrar"))

    assert translation.get_language() == "pt-br"
