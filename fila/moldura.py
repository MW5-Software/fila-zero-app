"""A moldura padrão dos relatórios no papel (28/09/2026).

O cliente: "vamos padronizar os relatórios, começando com um foot, no canto
esquerdo a data que foi emitido, o usuário que emitiu, no centro a logo do
Kronos e no canto direito a paginação; no topo, logo do cliente, filtros à
mostra". Os dois relatórios (por mídia e gerais) usam esta moldura, e o que
é de cada um fica entre o topo e o rodapé.

**O rodapé mora na MARGEM da folha** (`@page` com `@bottom-left`,
`@bottom-center` e `@bottom-right`): o PDF é a impressão do navegador, e só
ali o Chrome sabe o número da página e o total (`counter(page)`,
`counter(pages)`). Fora da margem não há como numerar sem motor de PDF no
servidor — e ele é o que `comum/exportacao.py` decidiu não ter. O texto de
cada canto vai numa string de CSS montada aqui, com o escape de
`texto_de_css`, porque o nome de quem emitiu é dado.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

__all__ = ["Moldura", "folha_da_pagina", "logo_do_kronos", "moldura_de", "texto_de_css"]

#: A marca do produto no rodapé do papel — a mesma do rodapé do sistema
#: (R48: o rodapé é a assinatura de quem fez, e não troca por cliente).
_LOGO = Path(__file__).resolve().parent.parent / "plataforma/static/plataforma/marca/kronos-footer.png"
#: Altura da logo no papel, em px de CSS; a largura segue a proporção. Era
#: 30, e o cliente pediu duas vezes: "tem que aumentar a logo do footer para
#: ser legível" (foi a 46) e "maior, a logo do Kronos tem que ser legível" —
#: a marca é empilhada, e o nome e o "ERP | CRM" são uma fração da altura.
_ALTURA_DA_LOGO = 64


@dataclass(frozen=True)
class Moldura:
    empresa: str
    #: `(rótulo, valor)` na ordem em que aparecem no topo.
    filtros: tuple
    emitido: str
    com_logo: bool = False
    #: A folha que vai no `<style>` da página, já pronta para o `@page`.
    folha: str = field(default="", compare=False)

    @property
    def logo_do_rodape(self) -> str:
        return logo_do_kronos()


def texto_de_css(texto: str) -> str:
    """`texto` como string de CSS, entre aspas. O nome de quem emitiu é dado
    do cliente e vai DENTRO da folha: uma aspa fecharia a string e o resto do
    nome viraria regra, e um "</style>" fecharia a própria folha no HTML. A
    barra invertida vem primeiro, senão ela escaparia os escapes seguintes."""
    for de, para in (("\\", "\\\\"), ('"', '\\"'), ("\n", "\\A "), ("<", "\\3C ")):
        texto = texto.replace(de, para)
    return f'"{texto}"'


@lru_cache(maxsize=1)
def logo_do_kronos() -> str:
    """A logo do KRONOS embutida num SVG do tamanho do rodapé.

    Embutida, e não por endereço: na margem da folha o Chrome não buscou a
    imagem pelo endereço (medido na conferência de 28/09/2026 — o texto e a
    paginação saíram, a logo não), e embutida ela não depende do cookie de
    quem imprime. SVG por fora porque a margem não aceita tamanho: a imagem
    sai no tamanho próprio, e o PNG tem 482×336 — o SVG diz o tamanho, e o
    PNG por dentro continua nítido no papel.
    """
    from PIL import Image

    with Image.open(_LOGO) as imagem:
        largura, altura = imagem.size
    png = base64.b64encode(_LOGO.read_bytes()).decode()
    exibida = round(largura * _ALTURA_DA_LOGO / altura)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{exibida}" '
           f'height="{_ALTURA_DA_LOGO}" viewBox="0 0 {largura} {altura}">'
           f'<image width="{largura}" height="{altura}" '
           f'href="data:image/png;base64,{png}"/></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _paginacao() -> str:
    """ "Página 2 de 3" como conteúdo de CSS: a frase traduzida, com os dois
    números trocados pelos contadores da página."""
    frase = _("Página %(pagina)s de %(paginas)s")
    antes, resto = frase.split("%(pagina)s", 1)
    meio, depois = resto.split("%(paginas)s", 1)
    partes = [texto_de_css(antes) if antes else "", "counter(page)",
              texto_de_css(meio) if meio else "", "counter(pages)",
              texto_de_css(depois) if depois else ""]
    return " ".join(p for p in partes if p)


def folha_da_pagina(emitido: str) -> str:
    """O `@page` dos três cantos. A margem de baixo cresce para caber a logo;
    o tamanho e o resto da margem são de cada relatório."""
    return mark_safe(
        "@page {\n"
        # 64px de logo são ~17mm: a margem de baixo cresce para ela caber.
        "  margin-bottom: 24mm;\n"
        f"  @bottom-left {{ content: {texto_de_css(emitido)}; font: 9px sans-serif; "
        "color: #555; vertical-align: middle; }\n"
        f'  @bottom-center {{ content: url("{logo_do_kronos()}"); vertical-align: middle; }}\n'
        f"  @bottom-right {{ content: {_paginacao()}; font: 9px sans-serif; "
        "color: #555; vertical-align: middle; }\n"
        "}")


def moldura_de(*, empresa: str, periodo: str, lojas: str, gerado_por: str, gerado_em,
               com_logo: bool = False) -> Moldura:
    quando = timezone.localtime(gerado_em)
    emitido = _("Emitido em %(data)s às %(hora)s por %(quem)s") % {
        "data": quando.strftime("%d/%m/%Y"), "hora": quando.strftime("%H:%M"),
        "quem": gerado_por}
    return Moldura(
        empresa=empresa,
        # O período em duas linhas — o tipo em cima, as datas embaixo —: numa
        # linha só ("Mensal (este mês) · 01/09/2026 a 28/09/2026") ele empurrava
        # "Lojas" para uma segunda fileira no A4 em pé. A folha mostra a
        # quebra (`white-space: pre-line`).
        filtros=((_("Período"), periodo.replace(" · ", "\n")), (_("Empresa"), empresa),
                 (_("Lojas"), lojas)),
        emitido=emitido, com_logo=com_logo, folha=folha_da_pagina(emitido))
