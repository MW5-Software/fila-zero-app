"""O erro em produção: onde cai, quem vê — Bloco 7 (item 35).

Três respostas para uma pergunta só:

- **ONDE CAI**: no log do container (stdout, `docker logs`) com o traceback
  inteiro — é o que a MW5 olha no VPS — E numa tabela da própria instalação
  (`Falha`, append-only como a auditoria): o erro que deu cara de "sumiu" às
  3h da manhã fica consultável dentro do sistema, sem SSH.
- **QUEM VÊ**: a MW5, na tela `/mw5/falhas` — mesma fronteira das telas da
  casa (`mw5.falhas` nunca é concedível; só superusuário passa). O cliente
  NUNCA vê traceback: a página dele diz que o problema foi registrado.
- **O QUE NÃO PODE ACONTECER**: o registro da falha engolir a falha. Se o
  banco estiver caído (e for ELE o motivo do 500), o middleware tenta
  gravar, desiste em silêncio, e a exceção ORIGINAL sobe intacta.
"""

import pytest
from contas.models import Usuario
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse

SENHA = "segredo-de-teste"


class TestOMiddleware:
    def _pedido(self, usuario=None):
        request = RequestFactory().get("/rota-que-estoura")
        request.session = {"usuario_id": str(usuario.pk)} if usuario else {}
        return request

    def _middleware(self):
        from plataforma.falhas import MiddlewareDeFalhas

        def resposta_ruim(request):
            raise ValueError("estourou de propósito")

        return MiddlewareDeFalhas(resposta_ruim)

    def _middleware_como_o_django_monta(self):
        """O middleware com o MESMO embrulho que o Django põe em volta dele.

        **É este o teste que faltava.** `_middleware()` acima monta o
        middleware em volta de uma função que levanta direto — cenário que
        não existe na pilha real: o Django embrulha cada camada em
        `convert_exception_to_response`, então a exceção de uma view já virou
        uma resposta 500 antes de voltar ao `__call__`. O middleware tinha só
        um `try/except` ali, nunca via nada, e `/mw5/falhas` ficava vazia para
        sempre — com esta suíte inteira verde.
        """
        from django.core.handlers.exception import convert_exception_to_response
        from plataforma.falhas import MiddlewareDeFalhas

        def view_que_estoura(request):
            raise ValueError("estourou de propósito")

        return MiddlewareDeFalhas(convert_exception_to_response(view_que_estoura))

    def test_grava_a_excecao_da_view_na_pilha_de_verdade(self, db):
        from plataforma.models import Falha

        middleware = self._middleware_como_o_django_monta()
        pedido = self._pedido()
        # Aqui a exceção NÃO sobe: o Django já a converteu em resposta. É
        # exatamente por isso que `process_exception` precisa existir.
        resposta = middleware.process_exception(pedido, ValueError("estourou de propósito"))
        assert resposta is None, (
            "devolver resposta aqui tomaria do Django a decisão de como é a "
            "página de erro")
        falha = Falha.objects.get()
        assert falha.caminho == "/rota-que-estoura"
        assert "estourou de propósito" in falha.resumo

    def test_nao_grava_a_mesma_falha_duas_vezes(self, db):
        """Os dois caminhos (o gancho e o `__call__`) existem juntos, e uma
        exceção que passe pelos dois não pode virar duas linhas."""
        from plataforma.falhas import MiddlewareDeFalhas
        from plataforma.models import Falha

        erro = ValueError("estourou de propósito")
        pedido = self._pedido()
        MiddlewareDeFalhas._registrar(pedido, erro)
        MiddlewareDeFalhas._registrar(pedido, erro)
        assert Falha.objects.count() == 1

    def test_a_excecao_sobe_intacta_depois_de_gravada(self, db):
        with pytest.raises(ValueError, match="estourou de propósito"):
            self._middleware()(self._pedido())

    def test_a_falha_fica_no_banco_com_rota_e_resumo(self, db):
        with pytest.raises(ValueError):
            self._middleware()(self._pedido())
        from plataforma.models import Falha

        falha = Falha.objects.get()
        assert falha.caminho == "/rota-que-estoura"
        assert falha.metodo == "GET"
        assert "estourou de propósito" in falha.resumo
        assert "ValueError" in falha.traceback

    def test_o_autor_vai_como_texto(self, db):
        """Mesma regra da auditoria: o registro sobrevive à pessoa."""
        ana = Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        with pytest.raises(ValueError):
            self._middleware()(self._pedido(usuario=ana))
        from plataforma.models import Falha

        falha = Falha.objects.get()
        assert falha.autor_login == "ana@teste.com"
        ana.delete()
        falha_fresca = Falha.objects.get()
        assert falha_fresca.autor_login == "ana@teste.com"

    def test_se_o_banco_estiver_caido_a_original_sobe_igual(self, db, monkeypatch):
        """O 500 por banco caído não pode virar dois 500 nem sumir: o
        registro falha em silêncio e a exceção original sobe."""
        from plataforma import falhas

        def gravar_quebrado(*a, **k):
            raise RuntimeError("banco fora do ar")

        monkeypatch.setattr(falhas, "_gravar", gravar_quebrado)
        with pytest.raises(ValueError, match="estourou de propósito"):
            self._middleware()(self._pedido())
        from plataforma.models import Falha

        assert Falha.objects.count() == 0

    def test_append_only_como_a_auditoria(self, db):
        with pytest.raises(ValueError):
            self._middleware()(self._pedido())
        from plataforma.models import Falha, FalhaImutavel

        falha = Falha.objects.get()
        with pytest.raises(FalhaImutavel):
            falha.save()
        with pytest.raises(FalhaImutavel):
            falha.delete()


class TestATela:
    @pytest.fixture
    def raiz_logado(self, db):
        Usuario.objects.create_superuser(email="raiz@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
        return c

    def _uma_falha(self):
        from plataforma.models import Falha

        Falha.objects.create(caminho="/frete", metodo="GET",
                             autor_login="ana@teste.com", autor_nome="Ana",
                             resumo="ValueError: estourou",
                             traceback="Traceback ...")

    def test_so_a_mw5_ve(self, db):
        Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        assert c.get(reverse("falhas")).status_code == 404
        assert Client().get(reverse("falhas")).status_code == 302

    def test_a_mais_recente_primeiro_com_o_que_importa(self, raiz_logado):
        self._uma_falha()
        html = raiz_logado.get(reverse("falhas")).content.decode()
        assert "/frete" in html
        assert "ana" in html
        assert "ValueError: estourou" in html

    def test_leitura_pura_como_a_auditoria(self, raiz_logado):
        self._uma_falha()
        assert raiz_logado.post(reverse("falhas"), {}).status_code == 405

    def test_o_menu_da_mw5_ganha_o_item(self, raiz_logado):
        html = raiz_logado.get(reverse("home")).content.decode()
        assert "Falhas" in html


class TestAsPaginasDeErro:
    def test_o_cliente_nunca_ve_traceback(self, db):
        """A página de 500 é à prova do próprio sistema: se a montagem
        bonita falhar, cai num HTML cru — e em nenhum dos dois casos sai
        traceback, settings nem caminho de máquina."""
        from django.test import override_settings

        from plataforma.falhas import pagina_de_erro

        pedido = RequestFactory().get("/onde-estourou")
        with override_settings(DEBUG=False):
            resposta = pagina_de_erro(pedido)
        assert resposta.status_code == 500
        corpo = resposta.content.decode()
        assert "ValueError" not in corpo
        assert "estourou" not in corpo
        assert "/home/" not in corpo

    def test_o_404_nao_parece_defeito_do_cliente(self, db):
        c = Client()
        resposta = c.get("/rota-que-nunca-existiu")
        assert resposta.status_code == 404
        assert "não existe" in resposta.content.decode().lower() or \
            "encontrada" in resposta.content.decode().lower()


class TestOLog:
    def test_o_erro_sai_no_log_com_traceback(self, db, caplog):
        """`docker logs` é o primeiro lugar onde se olha no VPS — o
        `django.request` tem que derrubar o traceback lá, com nível ERROR."""
        import logging

        from plataforma.falhas import MiddlewareDeFalhas

        def resposta_ruim(request):
            raise ValueError("estourou no log")

        with caplog.at_level(logging.ERROR, logger="plataforma.falhas"):
            with pytest.raises(ValueError):
                MiddlewareDeFalhas(resposta_ruim)(
                    RequestFactory().get("/x"))
        assert any(r.levelno == logging.ERROR and "estourou no log" in r.message
                   for r in caplog.records)
