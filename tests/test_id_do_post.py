"""Nenhuma tela filtra por um id do POST sem converter — a varredura, e o
defeito que ela impede de voltar.

Treze telas faziam `filter(pk=request.POST.get("alvo"))`. Com um id que não é
número — `<select>` deixado em branco, valor adulterado na mão — o Django não
devolve lista vazia: levanta `ValueError: Field 'id' expected a number but got
''` e a tela responde 500. Num formulário de sessenta campos, isso apaga o
trabalho da pessoa; e, do outro lado, troca a recusa silenciosa da casa ("a
ação não acontece e a tela recarrega") por uma exceção que conta ao atacante
que ele só errou o formato.

A varredura é do mesmo tipo das outras cinco (`test_guarda.py`,
`test_regra_tabela.py`...): a correção de hoje é fácil de desfazer sem querer,
porque a forma errada é mais curta que a certa.
"""

import ast
from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse

from comum.pedido import id_do_post

RAIZ = Path(__file__).resolve().parent.parent
PASTAS = ("contas", "plataforma", "comum", "modulos", "fila")


class TestOConversor:
    class _Pedido:
        def __init__(self, **dados):
            self.POST = dados

    def test_numero_vira_int(self):
        assert id_do_post(self._Pedido(alvo="42"), "alvo") == 42

    def test_espaco_em_volta_nao_atrapalha(self):
        assert id_do_post(self._Pedido(alvo="  42 "), "alvo") == 42

    def test_vazio_vira_none(self):
        """O `<select>` que ninguém escolheu — o caso que derrubava a tela."""
        assert id_do_post(self._Pedido(alvo=""), "alvo") is None

    def test_campo_ausente_vira_none(self):
        assert id_do_post(self._Pedido(), "alvo") is None

    def test_texto_vira_none(self):
        assert id_do_post(self._Pedido(alvo="'; drop"), "alvo") is None

    def test_digito_que_nao_e_ascii_vira_none(self):
        """"²".isdigit() é verdade e int("²") estoura: virava 500."""
        assert id_do_post(self._Pedido(alvo="²"), "alvo") is None

    def test_numero_maior_que_o_bigint_vira_none(self):
        """Um id maior que o bigint estoura a consulta no Postgres."""
        assert id_do_post(self._Pedido(alvo="9" * 19), "alvo") is None

    def test_negativo_passa(self):
        """Não é id de nada nesta casa; quem decide se alcança é a consulta
        com o filtro de inquilino, não este conversor."""
        assert id_do_post(self._Pedido(alvo="-1"), "alvo") == -1


class TestInteiroDoTexto:
    """A mesma regra fora do POST: o `?editar=` da URL, a quantidade de um
    carrinho, o campo de número de um cadastro. Veio do Portal de Vendas
    (15/09/2026), onde cada tela tinha o seu `isdigit()` com o mesmo furo."""

    def test_numero_e_sinal(self):
        from comum.pedido import inteiro_do_texto

        assert inteiro_do_texto(" 42 ") == 42
        assert inteiro_do_texto("-7") == -7

    def test_o_que_nao_e_numero_vira_none(self):
        from comum.pedido import inteiro_do_texto

        for bruto in ("", None, "abc", "²", "--5", "4 2", "1.5"):
            assert inteiro_do_texto(bruto) is None, bruto

    def test_o_teto_de_digitos_e_da_coluna(self):
        """18 cabe no bigint dos ids; 9 no inteiro comum."""
        from comum.pedido import inteiro_do_texto

        assert inteiro_do_texto("9" * 18) == int("9" * 18)
        assert inteiro_do_texto("9" * 19) is None
        assert inteiro_do_texto("9" * 9, digitos=9) == 999_999_999
        assert inteiro_do_texto("9" * 10, digitos=9) is None


def _fontes():
    for pasta in PASTAS:
        for arquivo in (RAIZ / pasta).rglob("*.py"):
            if "migrations" in arquivo.parts:
                continue
            yield arquivo


class _Caçador(ast.NodeVisitor):
    """Acha `request.POST.get(...)` (ou `request.POST[...]`) usado como valor
    de um argumento `pk=` ou `<campo>_id=`."""

    def __init__(self):
        self.achados: list[int] = []

    def _e_do_post(self, no) -> bool:
        if isinstance(no, ast.Subscript):
            no = no.value
        elif isinstance(no, ast.Call):
            no = no.func
        else:
            return False
        return (isinstance(no, ast.Attribute) and no.attr in ("get", "POST")
                and ast.unparse(no).startswith("request.POST"))

    def visit_Call(self, no):
        for palavra in no.keywords:
            if palavra.arg and (palavra.arg == "pk"
                                or palavra.arg.endswith("_id")):
                if self._e_do_post(palavra.value):
                    self.achados.append(no.lineno)
        self.generic_visit(no)


def test_nenhuma_tela_filtra_por_id_cru_do_post():
    culpados = []
    for arquivo in _fontes():
        cacador = _Caçador()
        cacador.visit(ast.parse(arquivo.read_text(encoding="utf-8")))
        culpados += [f"{arquivo.relative_to(RAIZ)}:{n}" for n in cacador.achados]

    assert culpados == [], (
        "id cru do POST indo para a consulta — use `comum.pedido.id_do_post`, "
        f"senão um `<select>` vazio responde 500: {culpados}")


@pytest.mark.django_db
class TestNaTelaDeVerdade:
    """A varredura prova que a forma errada sumiu; estes provam que a certa
    responde o que a casa promete — recusa, e não 500. Nas duas telas da base
    que resolvem o alvo por `id_do_post`; no Portal de Vendas eram as abas da
    bancada do produto."""

    @pytest.mark.parametrize("rota,campo,acao", [
        ("cargos", "cargo", "salvar"),
        ("cargos", "cargo", "remover"),
        ("filiais", "filial", "salvar"),
        ("filiais", "filial", "remover"),
    ])
    def test_id_vazio_nao_derruba_a_tela(self, rota, campo, acao, titular_logado):
        resposta = titular_logado.post(
            reverse(rota), {"acao": acao, campo: "", "rotulo": "X",
                            "alcance": "proprios", "nome": "X", "apelido": "X"})

        assert resposta.status_code in (200, 302), (
            f"{rota}/{acao} com {campo} vazio devolveu {resposta.status_code} "
            f"— a tela deveria recusar dizendo o motivo, e não estourar")


@pytest.fixture
def titular_logado(db, modulo_filiais_ligado):
    from contas.fabrica import aplicar
    from contas.models import Nivel
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    senha = "segredo-de-teste"
    empresa = Empresa.objects.create(razao_social="Alfa Ltda")
    pessoa = abrir_conta(empresa, "dona", senha)
    aplicar(pessoa, Nivel.TITULAR)

    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": "dona@teste.com",
                                     "senha": senha})
    return cliente
