"""A tela de entrada em castelhano — e os dois defeitos que ela teve.

**O primeiro: o seletor não mudava nada.** Trocar o idioma na porta trocava o
idioma, e a tela continuava idêntica — porque NADA do que se lê ali é texto
nosso no código. "Acessar Painel", "E-mail", "Manter conectado", "Entrar" são
campos do `LoginBrand`, que o cliente edita na tela de Aparência. Para quem
olha, isso se lê de um jeito só: "o botão não funciona".

A saída é a mesma do menu: traduz-se o que ainda é NOSSO. Frase igual ao
padrão do produto passa pelo arquivo de tradução; frase que o cliente trocou
passa intacta, porque a palavra é dele.

**O segundo: o gabarito da comparação estava traduzido.** A lista de "frases
que são nossas" foi escrita com `gettext_lazy`, então cada entrada dela virava
o texto no idioma ATIVO — com a tela em castelhano, o gabarito também estava
em castelhano, não casava com a marca (que está em português no banco), e
nada era traduzido. É o tipo de defeito que só aparece no segundo idioma:
em português o gabarito e a marca coincidem, e tudo parece certo.
"""

import pytest
from django.test import Client
from django.urls import reverse

from comum.idioma import CHAVE_IDIOMA
from plataforma.entrada import CAMPOS_DE_TEXTO, NOSSAS, traduzir_a_entrada
from plataforma.marca import marca_da_instalacao


def _texto(html: str) -> str:
    import re

    corpo = html[html.index("login-card"):html.index("</main>")]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", corpo))


class TestOGabaritoGuardaOPortugues:
    def test_as_frases_nossas_estao_em_portugues(self):
        """`gettext_noop` marca para o extrator e devolve o original — é o
        que faz esta lista continuar sendo gabarito."""
        assert "Acessar Painel" in NOSSAS
        assert "Entrar" in NOSSAS

    def test_o_gabarito_nao_muda_com_o_idioma_ativo(self):
        from django.utils import translation

        with translation.override("es"):
            assert "Acessar Painel" in NOSSAS, (
                "o gabarito virou castelhano junto com a tela — é o defeito "
                "de 10/09/2026, e ele deixa a entrada inteira em português")


@pytest.mark.django_db
class TestOQueTraduzEOQueNao:
    def test_a_frase_do_produto_e_traduzida(self):
        from django.utils import translation

        with translation.override("es"):
            login = traduzir_a_entrada(marca_da_instalacao().login)

        assert login.title == "Acceder al Panel"
        assert login.submit_label == "Ingresar"

    def test_a_frase_que_o_cliente_trocou_passa_intacta(self):
        """A palavra é dele. Traduzir "Entre no portal da Ferragem Silva"
        seria reescrever o texto que o cliente pagou para escrever."""
        from dataclasses import replace
        from django.utils import translation

        marca = marca_da_instalacao()
        dele = replace(marca.login, title="Portal da Ferragem Silva")

        with translation.override("es"):
            traduzida = traduzir_a_entrada(dele)

        assert traduzida.title == "Portal da Ferragem Silva"

    def test_em_portugues_nada_muda(self):
        original = marca_da_instalacao().login
        assert traduzir_a_entrada(original) == original

    def test_a_lista_de_campos_cobre_o_que_e_texto(self):
        """`LoginBrand` ganhar um campo de texto novo não acrescenta nada em
        `CAMPOS_DE_TEXTO` sozinho — e o campo novo ficaria em português sem
        ninguém perceber."""
        from nucleo.theme.brand import LoginBrand

        de_texto = {
            campo for campo, valor in vars(LoginBrand()).items()
            if isinstance(valor, str) and valor
            and not campo.endswith(("_url", "_color"))
        }
        assert de_texto <= set(CAMPOS_DE_TEXTO), (
            f"campo de texto do LoginBrand fora de CAMPOS_DE_TEXTO: "
            f"{de_texto - set(CAMPOS_DE_TEXTO)}")


@pytest.mark.django_db
class TestATelaDeVerdade:
    def test_em_castelhano_a_entrada_inteira_muda(self):
        cliente = Client()
        cliente.get(reverse("entrar") + "?idioma=es")
        texto = _texto(cliente.get(reverse("entrar")).content.decode())

        for frase in ("Acceder al Panel", "Ingresar",
                      "Mantener la sesión abierta"):
            assert frase in texto, f"faltou traduzir: {frase!r}"
        assert "Acessar Painel" not in texto
        assert "Manter conectado" not in texto

    def test_o_seletor_e_um_menu_com_bandeira_e_nao_texto_solto(self):
        """Ele nasceu como um `<p>` com um link dentro, sem estilo nenhum, no
        meio do formulário — entre a senha e o "Manter conectado"."""
        html = Client().get(reverse("entrar")).content.decode()

        assert "idioma-na-entrada" in html
        assert "bandeira" in html
        assert "login-idiomas" not in html, "voltou o parágrafo de texto puro"

    def test_o_seletor_fica_fora_do_formulario_de_senha(self):
        """Link dentro do formulário de senha confunde o leitor de tela — e,
        antes disso, confundia o olho."""
        html = Client().get(reverse("entrar")).content.decode()
        fim_do_form = html.index("</form>")

        assert html.index("idioma-na-entrada") > fim_do_form

    def test_a_escolha_fica_na_sessao(self):
        cliente = Client()
        cliente.get(reverse("entrar") + "?idioma=es")
        assert cliente.session[CHAVE_IDIOMA] == "es"
