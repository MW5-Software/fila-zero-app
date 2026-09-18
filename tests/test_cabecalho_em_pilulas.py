"""O contexto do cabeçalho em pílulas (18/09/2026).

O HTML é o do design system e não muda: continuam sendo os dois `<select>`
com `<label>`, e a troca continua funcionando sem JavaScript. O que muda é a
folha desta casa. Estes testes guardam as duas decisões que um "simplificar"
futuro apagaria sem perceber.
"""

from pathlib import Path

import pytest

FOLHA = Path("plataforma/static/plataforma/kronos.css")


@pytest.fixture(scope="module")
def css() -> str:
    return FOLHA.read_text(encoding="utf-8")


def test_o_rotulo_sai_de_vista_mas_nao_do_documento(css):
    """`display: none` tira o rótulo também do leitor de tela, e aí o campo
    vira "um seletor com nomes de empresa" para quem não vê o ícone. A receita
    é a da `.visually-hidden` do design system."""
    bloco = css.split(".ctx .ctx-nivel > label.ctx-rotulo {")[1].split("}")[0]

    assert "clip: rect(0 0 0 0)" in bloco
    assert "display: none" not in bloco


def test_o_icone_e_escolhido_pelo_id_do_seletor(css):
    """Pelo id, e nunca por `:first-child`: quem alcança uma empresa só e
    várias filiais tem UM nível na faixa, e ele é o da filial — pela ordem,
    essa pessoa veria o ícone de empresa em cima da loja dela."""
    assert ".ctx .ctx-nivel:has(> #ctx-empresa_id)" in css
    assert ".ctx .ctx-nivel:has(> #ctx-filial_id)" in css
    assert ".ctx .ctx-nivel:first-child" not in css


def test_a_pilula_so_vale_onde_o_has_vale(css):
    """O espaço do ícone (`padding-left`) mora na MESMA regra que desenha o
    ícone. Num navegador sem `:has` as duas somem juntas, e o seletor fica o
    de antes — e não um campo com um buraco à esquerda."""
    regra = ".ctx .ctx-nivel:has(> .ctx-sel) > .ctx-sel {"
    assert regra in css
    bloco = css.split(regra)[1].split("}")[0]
    assert "padding: 0 28px 0 34px" in bloco
    assert "border-radius: 999px" in bloco
