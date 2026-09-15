"""A home: uma saudação e a data de hoje, nada além disso.

`demonstracao` (a vitrine dos 58 componentes) tem a suíte própria em
`tests/test_demonstracao.py` — mudou de endereço para `/demonstracao`, mas
continua sendo testada lá. Esta suíte só cobre o que entrou no lugar dela em
"/".
"""

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from django.utils.timezone import localtime

pytestmark = pytest.mark.django_db

#: Duplicado de propósito, e não importado de `nucleo.views`: o teste prova
#: o texto que a tela mostra, não que a implementação chamou a própria
#: tabela — a mesma lógica por trás de `test_demonstracao.py` afirmar pelo
#: texto renderizado, nunca pela classe CSS ou pela função interna.
_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
_DIAS_DA_SEMANA = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)


def _data_de_hoje_por_extenso() -> str:
    agora = localtime()
    return (
        f"{_DIAS_DA_SEMANA[agora.weekday()]}, {agora.day} de "
        f"{_MESES[agora.month - 1]} de {agora.year}"
    )


@pytest.fixture
def html():
    Usuario.objects.create_user(
        email="ana@teste.com", password="segredo-de-teste", nome="Ana Paula")
    c = Client()
    c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
    resposta = c.get(reverse("home"))
    assert resposta.status_code == 200
    return resposta.content.decode()


class TestAHomeSaudaEMostraAData:
    def test_a_saudacao_usa_o_primeiro_nome(self, html):
        assert "Olá, Ana!" in html

    def test_a_data_de_hoje_aparece_por_extenso_em_portugues(self, html):
        assert _data_de_hoje_por_extenso() in html

    def test_o_pageheader_desenha_a_moldura(self, html):
        assert 'class="pagehead"' in html

    def test_a_vitrine_de_componentes_nao_mora_mais_aqui(self, html):
        """A prova de que a mudança de fato aconteceu: o texto que só
        `demonstracao` emite (`tests/test_demonstracao.py`) não aparece na
        home."""
        assert "O design system inteiro, numa tela" not in html

    def test_o_shell_continua_em_volta(self, html):
        assert "<aside" in html and 'class="side-nav"' in html
        assert "<header" in html
        assert "<footer" in html


class TestSemNome:
    def test_sem_first_name_a_saudacao_nao_quebra(self, db):
        Usuario.objects.create_user(email="semnome@teste.com", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"usuario": "semnome@teste.com", "senha": "segredo-de-teste"})
        resposta = c.get(reverse("home"))
        assert resposta.status_code == 200


class TestQuemEntra:
    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("home"))
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_a_home_e_a_demonstracao_sao_rotas_diferentes(self, db):
        assert reverse("home") == "/"
        assert reverse("demonstracao") == "/demonstracao"
