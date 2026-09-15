"""Meu Perfil: a pessoa troca a própria senha.

O teste que mais importa é o de continuar dentro depois da troca. Sem ele, a
pessoa troca a senha e é deslogada sem explicação — um defeito que parece
aleatório para quem usa e é óbvio para quem lê o Django.
"""

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

SENHA = "segredo-de-teste"


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(email="ana@teste.com", password=SENHA)


@pytest.fixture
def logada(ana):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
    return c


class TestATela:
    def test_quem_entrou_ve_a_tela(self, logada):
        resposta = logada.get(reverse("perfil"))
        assert resposta.status_code == 200
        assert "Meu Perfil" in resposta.content.decode()

    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("perfil"))
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_traz_o_token_csrf(self, logada):
        """Sem ele o POST da troca de senha morre em 403 — a tela desenharia
        certo e não funcionaria."""
        assert "csrfmiddlewaretoken" in logada.get(reverse("perfil")).content.decode()

    def test_traz_os_tres_campos_de_senha(self, logada):
        html = logada.get(reverse("perfil")).content.decode()
        for nome in ("senha_atual", "senha_nova", "senha_confirma"):
            assert f'name="{nome}"' in html

    def test_carrega_o_recortador_da_foto(self, logada):
        """Sem o Cropper e o `mw5-recorte.js`, escolher o arquivo não gera o
        recorte, o campo oculto `recorte` vai vazio, e a foto nunca salva: o
        servidor responde "o arquivo está vazio" para quem acabou de escolher
        uma foto. Foi assim desde a cópia do KRONOS.net até 15/09/2026. A ordem
        importa: o `mw5-recorte.js` usa o `window.Cropper`."""
        html = logada.get(reverse("perfil")).content.decode()
        assert "/static/nucleo/cropper.min.css" in html
        cropper = html.find("/static/nucleo/cropper.min.js")
        recorte = html.find("/static/nucleo/mw5-recorte.js")
        assert -1 < cropper < recorte

    def test_a_senha_nunca_volta_no_html(self, logada):
        assert SENHA not in logada.get(reverse("perfil")).content.decode()


class TestTrocarASenha:
    def test_troca_e_continua_dentro(self, logada, ana):
        """O Django invalida a sessão ao trocar a senha. Se isto falhar, a
        pessoa é deslogada sem explicação no meio da própria tela."""
        nova = "uma-senha-nova-longa"
        logada.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": nova, "senha_confirma": nova,
        })
        ana.refresh_from_db()
        assert ana.check_password(nova)
        assert logada.get(reverse("perfil")).status_code == 200

    def test_a_troca_marca_a_data_da_senha(self, logada, ana):
        """`senha_definida_em` é o que faz a expiração (Bloco 7) contar a
        partir de agora, e não da marca antiga — sem isto a senha nova
        venceria na data da senha VELHA."""
        from datetime import timedelta

        from django.utils import timezone

        Usuario.objects.filter(pk=ana.pk).update(
            senha_definida_em=timezone.now() - timedelta(days=400))
        nova = "uma-senha-nova-longa"
        logada.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": nova, "senha_confirma": nova,
        })
        ana.refresh_from_db()
        assert timezone.now() - ana.senha_definida_em < timedelta(minutes=1)

    def test_a_senha_antiga_para_de_valer(self, logada, ana):
        """O login deste projeto responde 302 no sucesso e 200 só na
        recusa (`contas/views.py::_desenhar` redesenha o formulário com 200
        de propósito — 401 dispararia a caixa nativa do navegador) — então o
        200 abaixo já prova que a senha antiga não abre mais a sessão."""
        nova = "uma-senha-nova-longa"
        logada.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": nova, "senha_confirma": nova,
        })
        assert Client().post(
            reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA}
        ).status_code == 200

    def test_sem_a_senha_atual_certa_nao_troca(self, logada, ana):
        """Sessão roubada não vira senha trocada."""
        logada.post(reverse("perfil_senha"), {
            "senha_atual": "a-errada", "senha_nova": "uma-senha-nova-longa",
            "senha_confirma": "uma-senha-nova-longa",
        })
        ana.refresh_from_db()
        assert ana.check_password(SENHA)

    def test_senha_nova_curta_e_recusada_citando_o_minimo(self, logada, ana):
        """A asserção precisa da frase de erro, não do texto de ajuda fixo:
        `campos_da_senha()` sempre escreve "Mínimo de N caracteres." ao lado
        do campo, erro ou não — checar só esse texto deixaria o teste verde
        mesmo com a checagem de tamanho neutralizada."""
        from nucleo.permissoes import SENHA_MINIMA

        resposta = logada.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": "curta", "senha_confirma": "curta",
        }, follow=True)
        ana.refresh_from_db()
        assert ana.check_password(SENHA)
        assert f"pelo menos {SENHA_MINIMA} caracteres" in resposta.content.decode()

    def test_a_confirmacao_precisa_bater(self, logada, ana):
        logada.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": "uma-senha-nova-longa",
            "senha_confirma": "outra-senha-nova-longa",
        })
        ana.refresh_from_db()
        assert ana.check_password(SENHA)

    def test_so_aceita_post(self, logada):
        assert logada.get(reverse("perfil_senha")).status_code == 405

    def test_troca_bem_sucedida_mostra_confirmacao(self, logada, ana):
        """Sucesso não pode ficar mudo: sem isto a pessoa manda o formulário,
        cai num redirect e não vê nenhum sinal de que funcionou."""
        from contas.views_perfil import MENSAGEM_SENHA_TROCADA

        nova = "uma-senha-nova-longa"
        resposta = logada.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": nova, "senha_confirma": nova,
        }, follow=True)
        assert MENSAGEM_SENHA_TROCADA in resposta.content.decode()

    def test_o_sinalizador_de_sucesso_nunca_ecoa_o_valor(self, logada):
        """A tela lê a presença de `?ok=`, nunca o valor — colar qualquer
        coisa na URL não pode voltar refletido no HTML."""
        from contas.views_perfil import MENSAGEM_SENHA_TROCADA

        html = logada.get(reverse("perfil") + "?ok=<script>alert(1)</script>").content.decode()
        assert MENSAGEM_SENHA_TROCADA in html
        assert "<script>alert(1)</script>" not in html
