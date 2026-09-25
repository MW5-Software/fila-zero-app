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


def _bloco(css: str, marcador: str) -> str:
    """O bloco da regra que contém `marcador`: do `{` anterior ao `}` seguinte.

    Ler o bloco pelo marcador, e não pela posição da regra no arquivo, é o que
    deixa estas asserções apontarem para a regra certa mesmo com a folha
    reordenada — e há três regras com o MESMO seletor do seletor do contexto
    (a de fora, a do `@supports` e a do chevron por variável).
    """
    i = css.index(marcador)
    return css[css.rindex("{", 0, i) + 1:css.index("}", i)]


def test_a_pilula_so_vale_onde_o_has_vale(css):
    """O espaço do ícone (`padding-left`) mora na MESMA regra que desenha o
    ícone. Num navegador sem `:has` as duas somem juntas, e o seletor fica o
    de antes — e não um campo com um buraco à esquerda."""
    # Pelo marcador de dentro do bloco, e não pela posição do seletor: há mais
    # de uma regra com este seletor (o chevron por variável, o `position` do
    # chevron absoluto), e a primeira do arquivo deixou de ser a da pílula.
    bloco = _bloco(css, "min-width: 240px")
    # O vão dos dois lados é o mesmo desde 18/09/2026 (`0 34px`): o ícone mora à
    # esquerda e o chevron à direita, e é ele que deixa o texto no meio.
    assert "padding: 0 34px" in bloco
    assert "border-radius: 999px" in bloco


def test_o_campo_da_pilula_nao_e_posicionado(css):
    """O ícone da esquerda é um `::before` do `.ctx-nivel`, e o campo é
    desenhado POR BAIXO dele.

    **Custou um ícone sumido** (18/09/2026). Para ancorar o chevron absoluto eu
    pus `position: relative` no CAMPO, e aí a ordem de pintura mudou: um
    elemento posicionado pinta DEPOIS dos pseudo-elementos do contêiner, então o
    campo passou a cobrir o ícone. O ícone continuava no documento — o cliente
    viu a pílula sem ele e reclamou, com razão. Quem ancora o chevron é o
    `.ctx-nivel`, que já é posicionado.
    """
    bloco = _bloco(css, "min-width: 240px")
    assert "position: relative" not in bloco
    assert "position: absolute" not in bloco


def test_o_texto_fica_no_meio_da_pilula(css):
    """18/09/2026, pedido do cliente: o nome no MEIO da pílula.

    São DOIS caminhos, e os dois precisam disto: o seletor nativo é uma caixa
    de texto (`text-align`), e o desenhado por nós (`appearance: base-select`)
    é uma caixa flex (`justify-content`). E o chevron sai do fluxo: como item
    flex, ele entraria na conta e centraria o grupo [texto + ícone] — deixando
    o TEXTO fora do centro, que foi exatamente o defeito relatado.
    """
    assert "text-align: center" in _bloco(css, "min-width: 240px")
    assert "justify-content: center" in _bloco(css, "display: inline-flex")
    assert "position: absolute" in _bloco(css, "right: 13px")


def test_a_pilula_tem_largura_para_o_nome_da_empresa(css):
    """18/09/2026, pedido do cliente: 230px cortava o nome da empresa e o da
    loja justamente em quem tem mais de uma — o caso em que o seletor existe —,
    e um nome curto encolhia a pílula até virar um selo com um vão do lado. O
    `max-width` continua: nome de sessenta caracteres não pode empurrar o
    avatar e o idioma para fora da tela."""
    bloco = _bloco(css, "min-width: 240px")

    assert "min-width: 240px" in bloco
    assert "max-width: 420px" in bloco
    assert "max-width: 230px" not in bloco


def test_a_lista_desenhada_por_nos_vive_dentro_do_supports(css):
    """`appearance: base-select` é melhoria progressiva: onde o navegador não
    a entende (Firefox e Safari, hoje), a lista tem de continuar sendo a
    NATIVA — feia, mas funcionando. Fora do `@supports`, o `appearance` cairia
    para `none` nesses navegadores e o seletor viraria um retângulo sem seta e
    sem lista."""
    assert "@supports (appearance: base-select) {" in css

    bloco = css.split("@supports (appearance: base-select) {")[1]
    for peça in ("::picker(select)", "::picker-icon", "option::checkmark"):
        assert peça in bloco, f"{peça} escapou do @supports"


def test_o_realce_do_teclado_acompanha_o_do_rato(css):
    """A seta do teclado move o `:checked` dentro da lista aberta. Sem o mesmo
    fundo do `:hover`, quem não usa rato não vê onde está."""
    regra = ".ctx .ctx-sel option:hover,\n  .ctx .ctx-sel option:focus {"
    assert regra in css


def test_as_duas_pilulas_nunca_passam_uma_por_cima_da_outra(css):
    """25/09/2026, com o print do cliente: "viu aqui que ficou grudado?".

    Cada pílula tem 240px de mínimo, e as duas somam 488px com o vão; a faixa
    do meio do cabeçalho é 2/4 da largura, e abaixo de ~1340px ela é MENOR que
    isso (medido: 321px a 1001px, e a segunda pílula entrava 75px por cima da
    primeira). A faixa vira contêiner, e com as duas pílulas nela cada uma
    tem no MÁXIMO metade dela menos meio vão — o mínimo de 240px também cede,
    senão ele continuaria empurrando uma sobre a outra."""
    faixa = css.split(".ctx-mid {")[1].split("}")[0]
    assert "container-type: inline-size" in faixa

    duas = css.split(".ctx:has(> .ctx-nivel + .ctx-nivel) .ctx-nivel:has(> .ctx-sel) > .ctx-sel {")
    assert len(duas) > 1, "falta a regra do par de pílulas"
    bloco = duas[1].split("}")[0]
    assert "min-width: min(240px, calc(50cqw - 4px))" in bloco
    assert "max-width: min(420px, calc(50cqw - 4px))" in bloco
