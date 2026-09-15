"""Os gráficos do Início, desenhados no servidor em HTML e CSS.

Por que não o `Chart` do design system (15/09/2026, o João não gostou dos
gráficos): ele desenha um SVG de 320 unidades que escala com a caixa, e o
TEXTO escala junto — minúsculo num terço da tela, enorme na tela toda. Além
disso o eixo cortava o número de cima ("50" virava meio "50"), a escala saía
quebrada numa contagem ("37,50 atendimentos"), o rótulo longo era truncado
("Ilumina…") e cada barra ganhava uma cor sem significado.

Aqui a letra tem tamanho de letra, a escala é redonda (e inteira para
contagem), o nome nunca é cortado e a cor diz alguma coisa. Nenhum HTML é
montado em JavaScript: a troca de série é CSS (`fila/static/fila/indicadores.css`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from django.utils.html import format_html, format_html_join

__all__ = ["Coluna", "colunas", "dinheiro_curto", "escala", "lista_ranqueada"]


def escala(maximo, marcas: int = 4, inteiro: bool = False) -> "tuple[float, float]":
    """(topo, passo) de um eixo que começa no zero.

    O passo é 1, 2, 2,5 ou 5 vezes uma potência de dez: é o que se lê de
    relance. Em contagem o passo é inteiro, porque "12,5 atendimentos" não
    existe. O topo é o primeiro múltiplo do passo que cobre o maior valor,
    para a barra mais alta nunca vazar do desenho.
    """
    maximo = float(maximo or 0)
    if maximo <= 0:
        return (float(marcas), 1.0)
    bruto = maximo / marcas
    potencia = 10 ** math.floor(math.log10(bruto))
    passo = next(m * potencia for m in (1, 2, 2.5, 5, 10) if m * potencia >= bruto)
    if inteiro:
        passo = float(max(1, math.ceil(passo)))
        # 2,5 arredondado para cima vira 3, que não é redondo: sobe para 5.
        if passo == 3:
            passo = 5.0
    return (math.ceil(maximo / passo) * passo, passo)


def dinheiro_curto(valor) -> str:
    """ "R$ 50 mil", "R$ 1,2 mi": o eixo tem uns 70 pixels de largura, e
    "R$ 100.000,00" não cabe nem se lê de relance."""
    valor = float(valor)
    if valor >= 1_000_000:
        numero, sufixo = valor / 1_000_000, " mi"
    elif valor >= 1_000:
        numero, sufixo = valor / 1_000, " mil"
    else:
        numero, sufixo = valor, ""
    texto = f"{numero:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"R$ {texto}{sufixo}"


@dataclass(frozen=True)
class Coluna:
    rotulo: str        # o que o eixo mostra ("06", "14h"); vazio para pular
    quando: str        # o que a dica mostra ("06/09", "14h")
    valor: "float | Decimal | int | None"
    texto: str         # o valor escrito por inteiro, na dica
    agora: bool = False  # a fatia em andamento: hoje, ou a hora de agora


def colunas(serie: str, rotulo_da_serie: str, lista: "list[Coluna]", *,
            marca, inteiro: bool = False, visivel: bool = False,
            agora_texto: str = ""):
    """Um gráfico de colunas no tempo, com grade redonda e dica por coluna.

    `marca` escreve o valor de uma marca do eixo. `valor` nulo é "não se
    aplica" (conversão de um dia sem atendimento): a coluna fica vazia e a
    dica diz "—", em vez de uma barra de zero que diria "atendeu e não
    vendeu".
    """
    maior = max((float(c.valor) for c in lista if c.valor is not None), default=0)
    topo, passo = escala(maior, inteiro=inteiro)
    quantas = round(topo / passo)
    grade = format_html_join("", '<li style="--y: {}%"><span>{}</span></li>', (
        (f"{100 * i / quantas:.4f}", marca(passo * i)) for i in range(quantas + 1)))
    ultimo = len(lista) - 1

    def coluna(i, c):
        altura = 0 if c.valor is None else 100 * float(c.valor) / topo
        classes = ["ind-col"]
        if c.agora:
            classes.append("agora")
        # A dica das pontas abre para dentro: centralizada, ela vazava do
        # cartão na primeira e na última coluna.
        if i < 2:
            classes.append("borda-e")
        elif i > ultimo - 2:
            classes.append("borda-d")
        quando = format_html("{} <em>{}</em>", c.quando, agora_texto) if c.agora else c.quando
        return (" ".join(classes), f"{altura:.4f}", quando, c.texto, c.rotulo)

    corpo = format_html_join("", (
        '<li class="{}" style="--h: {}%">'
        '<span class="ind-col-dica">{}<b>{}</b></span>'
        '<span class="ind-col-barra"></span>'
        '<span class="ind-col-rot">{}</span></li>'),
        (coluna(i, c) for i, c in enumerate(lista)))
    return format_html(
        '<figure class="ind-serie{}" data-serie="{}">'
        '<figcaption class="ind-oculto">{}</figcaption>'
        '<div class="ind-plot"><ul class="ind-grade" aria-hidden="true">{}</ul>'
        '<ol class="ind-colunas">{}</ol></div></figure>',
        " visivel" if visivel else "", serie, rotulo_da_serie, grade, corpo)


def lista_ranqueada(linhas: "list[tuple[str, float, str]]", tom: str):
    """Nome, valor escrito e a fatia do total, com a barra embaixo.

    A barra mede contra o MAIOR (o primeiro enche a linha, e a diferença entre
    os de baixo aparece); a porcentagem escrita é do TOTAL, que é a pergunta
    "quanto disso veio daqui". Uma cor só por lista: a ordem já diz quem é
    quem, e o arco-íris sugeria categorias que não existem.
    """
    total = sum(float(v) for _n, v, _t in linhas) or 1
    maior = max((float(v) for _n, v, _t in linhas), default=0) or 1
    itens = format_html_join("", (
        '<li><span class="ind-rank-nome">{}</span>'
        '<span class="ind-rank-valor">{}</span>'
        '<span class="ind-rank-parte">{}%</span>'
        '<span class="ind-rank-barra"><span style="width: {}%"></span></span></li>'), (
        (nome, texto, round(100 * float(v) / total), f"{100 * float(v) / maior:.2f}")
        for nome, v, texto in linhas))
    return format_html('<ol class="ind-rank" data-tom="{}">{}</ol>', tom, itens)
