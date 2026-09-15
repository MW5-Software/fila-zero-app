"""Gráficos desenhados no servidor, em SVG.

Sem biblioteca de JavaScript, e não por economia: o projeto gerado passaria a
ter dependência de build, o módulo gerado emitiria um `<canvas>` com um blob de
JSON no lugar de componentes que alguém edita à mão, e `<canvas>` não enxerga os
tokens de tema nem sai na impressão. SVG resolve os três, e o `<title>` dentro
de cada forma ainda dá tooltip nativo de graça.

A geometria mora em funções puras, fora do componente e fora do template. É
onde os erros de gráfico se escondem — uma fatia que não fecha o círculo, um
eixo que termina em 1.284 em vez de 2.000 — e função pura é o que se testa sem
renderizar nada.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, ClassVar, Sequence

from ..rendering import Component
from ..theme.tokens import CHART_COLORS

#: Os passos que fazem um eixo legível. 2.5 está aí porque 1.000 → 2.500 lê
#: melhor do que 1.000 → 5.000 quando o maior valor é 2.400.
_PASSOS = (1.0, 2.0, 2.5, 5.0, 10.0)


def maximo_redondo(valores: "Sequence[float]") -> float:
    """O topo do eixo, num número que uma pessoa lê.

    Sem isto o eixo termina exatamente no maior valor, e o gráfico ganha um
    "1.284" no topo que não diz nada a ninguém.
    """
    # `isfinite` não é paranoia: o leitor do painel entrega o que a pessoa
    # digitou, e um número de 309 dígitos vira `inf` em ponto flutuante. Sem o
    # filtro, `math.floor(math.log10(inf))` estoura em `OverflowError` e a
    # prévia inteira cai — justamente o que ela nunca pode fazer.
    maior = max((v for v in valores if v > 0 and math.isfinite(v)), default=0.0)
    if maior <= 0:
        return 1.0
    base = 10.0 ** math.floor(math.log10(maior))
    for passo in _PASSOS:
        if maior <= passo * base:
            return passo * base
    return 10.0 * base


def marcas_do_eixo(maximo: float, quantas: int = 4) -> "list[float]":
    """As linhas de grade, do zero ao topo."""
    return [maximo * i / quantas for i in range(quantas + 1)]


def fatias(valores: "Sequence[float]") -> "list[tuple[float, float]]":
    """Ângulo inicial e final de cada fatia, das 12 horas em sentido horário.

    Valor negativo vira zero: fatia negativa não existe num círculo, e derrubar
    o gráfico inteiro por causa de um seria pior do que omitir aquela.
    """
    positivos = [max(v, 0.0) for v in valores]
    total = sum(positivos)
    if total <= 0:
        return []

    saida: list[tuple[float, float]] = []
    angulo = 0.0
    for valor in positivos:
        fim = angulo + (valor / total) * 360.0
        saida.append((angulo, fim))
        angulo = fim
    # O último fecha exatamente em 360: acumular float deixa 359.99999 e abre
    # um fio de fundo entre a última fatia e a primeira.
    if saida:
        saida[-1] = (saida[-1][0], 360.0)
    return saida


def _ponto(centro: "tuple[float, float]", raio: float, angulo: float) -> "tuple[float, float]":
    rad = math.radians(angulo - 90.0)   # -90: zero grau às 12 horas
    return (centro[0] + raio * math.cos(rad), centro[1] + raio * math.sin(rad))


def _n(valor: float) -> str:
    """Coordenada com duas casas — o `d` do path fica legível no HTML."""
    return f"{valor:.2f}".rstrip("0").rstrip(".") or "0"


def arco(
    inicio: float,
    fim: float,
    raio: float,
    raio_interno: float = 0.0,
    centro: "tuple[float, float]" = (0.0, 0.0),
) -> str:
    """O atributo `d` de uma fatia. Com `raio_interno`, um pedaço de donut."""
    if fim - inicio >= 359.999:
        return _volta_inteira(raio, raio_interno, centro)

    grande = 1 if fim - inicio > 180.0 else 0
    x1, y1 = _ponto(centro, raio, inicio)
    x2, y2 = _ponto(centro, raio, fim)

    if raio_interno <= 0:
        return (f"M {_n(centro[0])},{_n(centro[1])} L {_n(x1)},{_n(y1)} "
                f"A {_n(raio)} {_n(raio)} 0 {grande} 1 {_n(x2)},{_n(y2)} Z")

    x3, y3 = _ponto(centro, raio_interno, fim)
    x4, y4 = _ponto(centro, raio_interno, inicio)
    return (f"M {_n(x1)},{_n(y1)} "
            f"A {_n(raio)} {_n(raio)} 0 {grande} 1 {_n(x2)},{_n(y2)} "
            f"L {_n(x3)},{_n(y3)} "
            f"A {_n(raio_interno)} {_n(raio_interno)} 0 {grande} 0 {_n(x4)},{_n(y4)} Z")


def _volta_inteira(raio: float, raio_interno: float, centro: "tuple[float, float]") -> str:
    """Um ponto só ocupa o círculo inteiro — e arco de 360° começa e termina no
    mesmo lugar, então o navegador não desenha nada. Dois semicírculos."""
    cx, cy = centro
    topo, base = _n(cy - raio), _n(cy + raio)
    fora = (f"M {_n(cx)},{topo} "
            f"A {_n(raio)} {_n(raio)} 0 1 1 {_n(cx)},{base} "
            f"A {_n(raio)} {_n(raio)} 0 1 1 {_n(cx)},{topo} Z")
    if raio_interno <= 0:
        return fora
    t2, b2 = _n(cy - raio_interno), _n(cy + raio_interno)
    return (fora + f" M {_n(cx)},{t2} "
            f"A {_n(raio_interno)} {_n(raio_interno)} 0 1 0 {_n(cx)},{b2} "
            f"A {_n(raio_interno)} {_n(raio_interno)} 0 1 0 {_n(cx)},{t2} Z")


def pontos_da_linha(
    valores: "Sequence[float]",
    maximo: float,
    largura: float,
    altura: float,
) -> "list[tuple[float, float]]":
    """As coordenadas da curva. Y cresce para baixo, como no SVG."""
    if not valores:
        return []
    escala = (lambda v: altura - (v / maximo) * altura) if maximo > 0 else (lambda v: altura)
    if len(valores) == 1:
        return [(largura / 2, escala(valores[0]))]
    passo = largura / (len(valores) - 1)
    return [(i * passo, escala(v)) for i, v in enumerate(valores)]


def formatar_numero(valor: float) -> str:
    """No padrão brasileiro: ponto no milhar, vírgula no decimal."""
    if float(valor).is_integer():
        return f"{int(valor):,}".replace(",", ".")
    return f"{valor:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


#: Os cinco tipos. `pie` e `donut` são o mesmo desenho com raio interno.
KINDS: tuple[str, ...] = ("bar", "bar_h", "line", "pie", "donut")
LEGENDAS: tuple[str, ...] = ("right", "bottom", "none")

#: O sistema de coordenadas interno. O SVG escala por CSS; estes números só
#: decidem a proporção do desenho.
_LARGURA = 320.0
_RAIO = 60.0
_FURO = 36.0
_MARGEM_ESQUERDA = 44.0   # espaço para os rótulos do eixo Y
_MARGEM_BAIXO = 22.0      # espaço para os rótulos do eixo X
_LIMITE_DO_ROTULO = 14    # caracteres antes de truncar no eixo
#: Na barra deitada o rótulo é o do eixo Y, e ali só existem os 44 da margem
#: esquerda. A 9px, catorze caracteres passariam da borda do viewBox e sairiam
#: cortados; oito cabem.
_LIMITE_DO_ROTULO_DEITADO = 8


@dataclass
class DataPoint:
    """Um ponto: uma barra, uma fatia ou um vértice da linha."""

    label: str
    value: float = 0.0
    #: Vazio segue a paleta da marca pela posição. Preenchido, manda.
    color: str = ""


@dataclass
class Chart(Component):
    """Um gráfico em SVG, desenhado no servidor.

    Numa **linha** os pontos formam uma curva só: a cor é do gráfico inteiro,
    `DataPoint.color` é ignorado, e a legenda não aparece — legenda de uma
    série só é ruído. Nos outros quatro cada ponto tem cor e entra na legenda.
    """

    template: ClassVar[str] = "components/chart.html"

    points: "list[DataPoint]" = field(default_factory=list)
    kind: str = "bar"
    title: str = ""
    legend: str = "right"
    axis: bool = True
    #: A altura do desenho no sistema de coordenadas interno, que tem 320 de
    #: largura. O SVG escala uniformemente para a largura do container, então
    #: este número é a **proporção** do gráfico: 180 numa caixa de 320px dá
    #: 180px de altura, e numa de 640px dá 360px. Escalar só em X — que é o que
    #: `preserveAspectRatio="none"` fazia — esticava o texto e os cantos
    #: arredondados junto.
    height: int = 180
    #: Só a linha usa. Vazio cai no `--chart-1`.
    color: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(
                f"kind deve ser um de {', '.join(KINDS)} — recebido {self.kind!r}"
            )
        if self.legend not in LEGENDAS:
            raise ValueError(
                f"legend deve ser um de {', '.join(LEGENDAS)} — "
                f"recebido {self.legend!r}"
            )
        if not 80 <= self.height <= 600:
            raise ValueError(
                f"height deve ficar entre 80 e 600 — recebido {self.height!r}"
            )

    # ---------- o que o template enxerga ----------

    def template_context(self) -> "dict[str, Any]":
        return {"c": self, "g": self._geometria()}

    @property
    def redondo(self) -> bool:
        return self.kind in ("pie", "donut")

    @property
    def mostra_legenda(self) -> bool:
        # A linha nunca: uma curva só não tem o que legendar.
        return bool(self.points) and self.legend != "none" and self.kind != "line"

    def cor_de(self, indice: int) -> str:
        """A cor de um ponto: a dele, senão o token da posição, ciclando."""
        ponto = self.points[indice]
        if ponto.color:
            return ponto.color
        return f"var(--chart-{indice % CHART_COLORS + 1})"

    def resumo(self) -> str:
        """O gráfico em texto, para quem não vê o desenho."""
        itens = ", ".join(f"{p.label} {formatar_numero(p.value)}" for p in self.points)
        return f"{self.title}: {itens}" if self.title else itens

    # ---------- geometria ----------

    def _geometria(self) -> "dict[str, Any]":
        valores = [p.value for p in self.points]
        if not self.points:
            return {"vazio": True}

        comum = {
            "vazio": False,
            "legenda": [
                {"cor": self.cor_de(i), "label": p.label,
                 "valor": formatar_numero(p.value)}
                for i, p in enumerate(self.points)
            ],
        }
        if self.redondo:
            return {**comum, "fatias": self._fatias_desenhadas(valores)}
        if self.kind == "line":
            return {**comum, **self._linha_desenhada(valores)}
        return {**comum, **self._barras_desenhadas(valores)}

    def _fatias_desenhadas(self, valores: "list[float]") -> list:
        furo = _FURO if self.kind == "donut" else 0.0
        pedacos = fatias(valores)
        if not pedacos:
            # Todos zero: um anel neutro, para a caixa não ficar vazia.
            return [{"d": arco(0, 360, _RAIO, furo, (_RAIO, _RAIO)),
                     "cor": "var(--outline)", "label": "", "valor": ""}]
        return [
            {"d": arco(ini, fim, _RAIO, furo, (_RAIO, _RAIO)),
             "cor": self.cor_de(i),
             "label": self.points[i].label,
             "valor": formatar_numero(self.points[i].value)}
            for i, (ini, fim) in enumerate(pedacos)
        ]

    def _barras_desenhadas(self, valores: "list[float]") -> dict:
        maximo = maximo_redondo(valores)
        deitada = self.kind == "bar_h"
        area_l = _LARGURA - _MARGEM_ESQUERDA
        area_a = float(self.height) - _MARGEM_BAIXO
        quantas = len(valores)
        vao = (area_a if deitada else area_l) / quantas
        grossura = vao * 0.62

        barras = []
        for i, ponto in enumerate(self.points):
            fatia = max(ponto.value, 0.0) / maximo if maximo else 0.0
            centro = i * vao + (vao - grossura) / 2
            if deitada:
                caixa = {"x": _MARGEM_ESQUERDA, "y": centro,
                         "w": max(fatia * area_l, 0.0), "h": grossura,
                         # A linha de base do rótulo, na altura do meio da
                         # barra. Sai daqui e não do template: geometria é
                         # deste módulo, e `+ 3` solto na marcação é o tipo de
                         # conta que ninguém sabe de onde veio.
                         "rotulo_y": centro + grossura / 2 + 3.0}
            else:
                comprimento = max(fatia * area_a, 0.0)
                caixa = {"x": _MARGEM_ESQUERDA + centro, "y": area_a - comprimento,
                         "w": grossura, "h": comprimento,
                         "rotulo_x": _MARGEM_ESQUERDA + centro + grossura / 2}
            barras.append({**caixa, "cor": self.cor_de(i),
                           "label": ponto.label,
                           "curto": _truncar(
                               ponto.label,
                               _LIMITE_DO_ROTULO_DEITADO if deitada
                               else _LIMITE_DO_ROTULO),
                           "valor": formatar_numero(ponto.value)})
        return {"barras": barras, "deitada": deitada,
                "marcas": self._marcas(maximo, area_a, area_l, deitada),
                "area_l": area_l, "area_a": area_a}

    def _linha_desenhada(self, valores: "list[float]") -> dict:
        maximo = maximo_redondo(valores)
        area_l = _LARGURA - _MARGEM_ESQUERDA
        area_a = float(self.height) - _MARGEM_BAIXO
        pontos = pontos_da_linha(valores, maximo, area_l, area_a)
        return {
            "curva": " ".join(f"{_MARGEM_ESQUERDA + x:.2f},{y:.2f}" for x, y in pontos),
            "vertices": [
                {"x": _MARGEM_ESQUERDA + x, "y": y,
                 "label": self.points[i].label,
                 "curto": _truncar(self.points[i].label),
                 "valor": formatar_numero(self.points[i].value)}
                for i, (x, y) in enumerate(pontos)
            ],
            "cor_da_linha": self.color or "var(--chart-1)",
            "marcas": self._marcas(maximo, area_a, area_l, False),
            "area_l": area_l, "area_a": area_a,
        }

    def _marcas(self, maximo: float, area_a: float, area_l: float,
                deitada: bool) -> list:
        if not self.axis:
            return []
        valores = marcas_do_eixo(maximo)
        ultimo = len(valores) - 1
        return [
            {"texto": formatar_numero(v),
             "y": area_a - (v / maximo) * area_a if maximo else area_a,
             "x": _MARGEM_ESQUERDA + (v / maximo) * area_l if maximo else _MARGEM_ESQUERDA,
             # A última marca do eixo deitado cai exatamente em x=320, a borda
             # do viewBox: centrada ali, metade do número fica fora do desenho.
             # Ancorar no fim traz o texto para dentro.
             "ancora": "fim" if deitada and i == ultimo else "meio",
             "deitada": deitada}
            for i, v in enumerate(valores)
        ]


def _truncar(texto: str, limite: int = _LIMITE_DO_ROTULO) -> str:
    """Rótulo que não cabe no eixo. O inteiro continua no `<title>`.

    O `rstrip` tira o espaço que sobraria antes das reticências: "Ordens …"
    parece erro de digitação, "Ordens…" parece corte.
    """
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"
