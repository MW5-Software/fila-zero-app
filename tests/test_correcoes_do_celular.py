"""As correções de celular de 18/09/2026, presas na folha.

São regras de CSS, e o Python que as usa não sabe que elas existem: apagar a
linha não deixa nada vermelho na suíte. Cada uma nasceu de um defeito que o
cliente viu no telefone, e as medidas saíram do Chrome headless com 390px de
largura — o navegador não roda na suíte, então o que sobra para cobrar é a
regra.

**Um teste destes não prova que a tela está certa**: prova que a decisão
continua escrita. Quem mexer na folha vai ler o motivo antes de apagar.
"""

from pathlib import Path

import pytest

KRONOS = Path("plataforma/static/plataforma/kronos.css")
USUARIOS = Path("contas/static/contas/usuarios.css")
EMPRESA = Path("plataforma/static/plataforma/empresa.css")
FILA = Path("fila/static/fila/fila.css")

#: O celular das telas: 390px de largura, e o `@media` das duas folhas de tela.
CELULAR = 620


@pytest.fixture(scope="module")
def kronos() -> str:
    return KRONOS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def usuarios() -> str:
    return USUARIOS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def empresa() -> str:
    return EMPRESA.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def fila() -> str:
    return FILA.read_text(encoding="utf-8")


def _bloco(css: str, seletor: str) -> str:
    """O texto de dentro da ÚLTIMA regra deste seletor.

    Da última, e não da primeira: a folha desta casa corrige regras que já
    existem — há duas com o seletor do campo de arquivo —, e é a de baixo que
    vale. (O par `_bloco` de `test_cabecalho_em_pilulas.py` procura por um
    texto de dentro do bloco; aqui o que muda é o seletor, e por isso o
    marcador é o próprio.)
    """
    i = css.rindex(seletor)
    return css[css.index("{", i) + 1:css.index("}", i)]


def test_o_campo_de_arquivo_do_perfil_encolhe(kronos):
    """O nome do arquivo vazava do cartão, e a página inteira rolava de lado.

    O `<input type="file">` do `nucleo` não encolhe: a largura mínima do
    conteúdo — o botão nativo mais "Nenhum arquivo escolhido" — é maior que a
    coluna ao lado do avatar. Medido em 18/09/2026: o campo ia até 399px numa
    tela de 390 (`scrollWidth` 399 contra `clientWidth` 390).

    `min-width: 0` é o que faltava: item de flex nasce com `min-width: auto`, e
    `auto` quer dizer "nunca menor que o meu conteúdo".
    """
    assert "min-width: 0" in _bloco(kronos, '.recorte-atual input[type="file"]')


def test_os_botoes_do_rodape_centralizam_no_celular(usuarios, empresa):
    """Largura inteira não centraliza nada: falta o rótulo dentro do botão.

    As duas telas — Usuário e Empresa — empilham os botões e os esticam no
    celular desde sempre, e o `.btn` é uma caixa flex que herda
    `justify-content: normal`, que quer dizer `flex-start`. Medido em
    18/09/2026 na tela de Empresa: botão de 335px começando em x=43, e o texto
    a partir de x=60 — o cliente leu isso como "botão não centralizado".
    """
    for css, seletor in ((usuarios, ".ct-rodape .btn"),
                         (empresa, ".ep-rodape .btn")):
        bloco = _bloco(css, seletor)

        assert "justify-content: center" in bloco, seletor
        assert "width: 100%" in bloco, seletor
        assert f"@media (max-width: {CELULAR}px)" in css, seletor


def test_o_cabecalho_da_fila_no_celular_cabe_o_logo_do_computador(fila):
    """O logo encolhia no celular, e era o único lugar do sistema onde isso
    acontecia.

    A marca do produto é EMPILHADA — símbolo, "Kronos" e a linha "ERP | CRM" —
    e a 44px as três se colam: o desenho da palavra encosta na linha de baixo e
    o conjunto se lê como logo cortado (18/09/2026, "logo do Kronos no celular
    tá cortado"). O desenho nunca foi recortado — medido no Chrome em 390px, o
    campo de 63x44 com `object-fit: contain` bate com a fonte, pixel a pixel —,
    era o TAMANHO.

    A faixa sobe para 80px e o logo fica com os 60px do computador: a regra do
    celular que o encolhia não existe mais, e a de cima é a única.
    """
    assert "--header-h: 80px" in fila
    # A regra do celular era um par de seletores numa linha só, e ela morreu:
    # se este par voltar, o logo volta a encolher.
    assert ".fila-marca, .fila-marca img" not in fila
    assert "height: 60px" in _bloco(fila, ".fila-marca img {")