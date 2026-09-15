"""O espaço entre o último campo e o botão de enviar.

Um `<form>` cru não separa nada: o botão nascia colado no campo de cima, tão
perto que lia como parte dele. O `Card` em volta e a grade de campos já tinham
o próprio ritmo; o que faltava era entre um filho do formulário e o seguinte.

Removido no porte: `TestOBlocoFormularioDoConstrutor.test_o_botao_deixa_de_nascer_colado`
testava o painel do `mw5_generator` (o construtor de sites, um projeto por
cliente). O KRONOS.net é uma matriz única — não há geração por cliente —,
então esse código nunca vai existir aqui. Decisão de arquitetura registrada
nas Global Constraints do plano (commit `375bbcd`).
"""

import re
from pathlib import Path

from nucleo.components import (Button, FilterBar, Form, FormGrid,
                                  SearchInput, TextInput)
from nucleo.rendering import render_all

CSS = (Path(__file__).resolve().parents[1] / "nucleo" / "static"
       / "nucleo" / "mw5.css").read_text(encoding="utf-8")


def _form() -> str:
    return render_all([Form(action="/x", children=[
        FormGrid(children=[TextInput(name="a", label="Campo")]),
        Button(label="Salvar", variant="primary", type="submit"),
    ])])


class TestAClasseExiste:
    def test_o_componente_form_carrega_a_classe(self):
        """Ela existe só para a regra de espaçamento — sem a classe no
        template, a regra mira um seletor que nada casa."""
        assert '<form class="form"' in _form()

    def test_e_a_regra_existe(self):
        assert re.search(r"\.form > \* \+ \* \{[^}]*margin-top", CSS)


class TestONaoAlcancaOsOutrosFormularios:
    """O login, a barra de filtros e o perfil também são `<form>`, e os três têm
    layout próprio. A barra de filtros é uma FILEIRA: uma margem no topo do
    botão dela quebraria a linha em duas."""

    def test_a_regra_nao_e_solta_no_form(self):
        assert not re.search(r"(?m)^form > \* \+ \*", CSS)

    def test_a_barra_de_filtros_nao_ganha_a_classe(self):
        html = render_all([FilterBar(action="/x", fields=[
            SearchInput(name="busca", label="Buscar")])])
        assert '<form class="card filters"' in html
        assert 'class="form"' not in html

    def test_o_login_tambem_nao(self):
        gabarito = (Path(__file__).resolve().parents[1] / "nucleo"
                    / "templates" / "layout" / "login.html").read_text(encoding="utf-8")
        assert '<form method="post"' in gabarito
        assert 'class="form"' not in gabarito


class TestOMesmoRitmoDaTelaInteira:
    def test_os_tres_espacamentos_empilhados_batem(self):
        """`main > * + *`, `.formgrid + .formgrid` e `.form > * + *` respondem à
        MESMA pergunta — quanto separa duas coisas empilhadas. Três respostas
        diferentes seriam três ritmos na mesma tela."""
        valores = set()
        for seletor in (r"main > \* \+ \*", r"\.formgrid \+ \.formgrid",
                        r"\.form > \* \+ \*"):
            regra = re.search(seletor + r" \{[^}]*margin-top:\s*(\d+)px", CSS)
            assert regra, f"`{seletor}` sumiu ou deixou de espaçar"
            valores.add(regra.group(1))
        assert len(valores) == 1, f"ritmos diferentes na mesma tela: {valores}"
