"""A exportação de listagens: o que está na tela é o que sai no arquivo.

O filtro e a ordenação vêm da MESMA URL da tela e passam pelo MESMO
`comum.listagem.preparar_consulta` que desenha a tabela — não existe
segunda implementação de filtro para a planilha divergir da tela.

Dois formatos, decisões diferentes:

- **xlsx de verdade** (`openpyxl`): é o que o roadmap pede, e CSV aberto no
  Excel brasileiro tropeça em acento e separador — planilha certa ou nada.
- **PDF pela impressão** (`formato=impressao`): devolve uma página limpa de
  papel (sem shell, sem menu) que chama `window.print()`; quem salva em PDF
  usa o próprio diálogo do navegador. Uma engine de PDF na imagem seria
  peso nas vinte instalações — e refazeria pior (margens, fonte, quebra de
  página) o que o navegador já faz melhor.

Uma tela entra aqui por `responder_formato`: se `?formato=` pede um formato
conhecido, recebe a resposta pronta; senão recebe `None` e desenha a tela
normal como sempre. Entrada ruim nunca derruba nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.timezone import localtime

from nucleo.components import Column, Table

__all__ = ["FORMATOS", "ColunaDeExportacao", "botoes", "em_impressao",
           "em_xlsx", "preparar_exportacao"]

#: Os formatos que existem. Conjunto fechado de propósito: um quarto formato
#: é decisão de projeto, não um `elif` que uma view inventa sozinha.
FORMATOS = frozenset({"xlsx", "impressao"})

#: Content-Type oficial de `.xlsx`. Literal aqui porque é contrato do
#: formato — e é o que faz o navegador baixar em vez de tentar renderizar.
CONTENT_TYPE_XLSX = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@dataclass(frozen=True)
class ColunaDeExportacao:
    """Uma coluna do arquivo: rótulo no cabeçalho, função que extrai o valor.

    É a mesma ideia da coluna da tabela na tela (`nucleo.components.
    Column`), mas devolvendo VALOR e não HTML — arquivo leva dado, não
    marcação.
    """

    chave: str
    rotulo: str
    valor: Callable[[Any], object]


def _texto(valor: object) -> str:
    """O valor como texto de célula. `None`/vazio viram string vazia — e
    não `"None"` escrito na célula, que é o jeito Python de dizer que não
    olhou."""
    if valor is None:
        return ""
    return str(valor)


def _nome_do_arquivo(titulo: str) -> str:
    from django.utils.text import slugify

    return f"{slugify(titulo) or 'exportacao'}.xlsx"


def em_xlsx(colunas: Sequence[ColunaDeExportacao], linhas, titulo: str) -> HttpResponse:
    """A planilha. Cabeçalho = rótulos; uma linha por registro.

    Exportar filtro sem resultado NÃO é erro: sai a planilha com o
    cabeçalho — quem recebeu precisa saber o que ELA teria, e não receber
    um 404 que parece "a exportação quebrou".
    """
    from openpyxl import Workbook

    planilha = Workbook()
    folha = planilha.active
    # O formato limita o nome da aba a 31 caracteres — cortar aqui evita
    # exceção dentro do openpyxl com um título comprido de tela.
    folha.title = titulo[:31] or "Exportação"
    folha.append([c.rotulo for c in colunas])
    for linha in linhas:
        folha.append([_texto(c.valor(linha)) for c in colunas])

    resposta = HttpResponse(content_type=CONTENT_TYPE_XLSX)
    resposta["Content-Disposition"] = \
        f'attachment; filename="{_nome_do_arquivo(titulo)}"'
    planilha.save(resposta)
    return resposta


_PAGINA_DE_PAPEL = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{titulo}</title>
<link rel="stylesheet" href="/tema.css">
<link rel="stylesheet" href="/static/nucleo/mw5.css">
<link rel="stylesheet" href="/static/plataforma/impressao.css">
</head>
<body class="papel">
<header class="papel-cabecalho">
  <h1>{titulo}</h1>
  <p class="papel-carimbo">Emitido em {agora} · {quantidade}</p>{subtitulo}
</header>
{tabela}
<script>window.print();</script>
</body>
</html>"""


def _tabela_de_papel(colunas: Sequence[ColunaDeExportacao], linhas) -> str:
    """A mesma `Table` do design system, alimentada com VALORES das colunas
    de exportação — o papel sai com a cara do sistema, sem segunda tabela
    desenhada à mão."""
    env_do_componente = None  # `Table.render` cria/usa o ambiente corrente
    colunas_componente = [
        Column(c.chave, c.rotulo,
               render=lambda registro, c=c: _texto(c.valor(registro)) or "—")
        for c in colunas
    ]
    return str(Table(columns=colunas_componente,
                     rows=list(linhas)).render(env_do_componente))


def em_impressao(colunas: Sequence[ColunaDeExportacao], linhas,
                 titulo: str, subtitulo: str = "") -> HttpResponse:
    """A página de papel: título, carimbo de quando/quanto, a tabela, e o
    convite ao diálogo de impressão."""
    registros = list(linhas)
    quantidade = f"{len(registros)} registro" + ("s" if len(registros) != 1 else "")
    html = _PAGINA_DE_PAPEL.format(
        titulo=format_html("{}", titulo),
        agora=localtime().strftime("%d/%m/%Y %H:%M"),
        quantidade=quantidade,
        subtitulo=(f'\n  <p class="papel-filtro">{format_html("{}", subtitulo)}</p>'
                   if subtitulo else ""),
        tabela=_tabela_de_papel(colunas, registros),
    )
    return HttpResponse(html)


def botoes(request) -> list:
    """Os dois gatilhos da tela: Excel e Imprimir, no cabeçalho.

    São âncoras com a querystring CORRENTE carregada (`Raw` com o mesmo
    HTML confiável do "Limpar" da barra de filtro): o filtro que está na
    URL é o que vai para o arquivo — sem JS, sem formulário extra, e o
    link de impressão abre direto o diálogo do navegador.
    """
    from nucleo.components import Raw

    def _href(formato: str) -> str:
        params = request.GET.copy()
        params["formato"] = formato
        params.pop("pagina", None)  # o arquivo não tem página 2
        query = params.urlencode()
        return f"{request.path}?{query}" if query else \
            f"{request.path}?formato={formato}"

    # Os dois eram `ghost` — sem fundo e sem borda —, e viravam dois textos
    # cinzas ao lado do título, indistinguíveis do que estava escrito em
    # volta. Agora cada um diz o que é pelo peso:
    #
    # - **Exportar Excel** no verde do formato (`.btn.excel`, em
    #   `plataforma/static/plataforma/kronos.css`). É a associação que faz
    #   alguém achar o botão sem ler, como o vermelho do PDF.
    # - **Imprimir** no `.btn` puro, que já é branco com borda. Tem contorno
    #   — logo é botão — sem competir com o verde ao lado nem com a ação
    #   principal da tela.
    #
    # O rótulo é "Exportar Excel", com o verbo: "Excel" sozinho nomeia um
    # programa, não uma ação, e ao lado de "Imprimir" (que é verbo) a dupla
    # ficava desalinhada — um dizia o que fazer, o outro dizia para onde ir.
    return [
        Raw(html=format_html(
            '<a class="btn excel" href="{}">Exportar Excel</a>',
            _href("xlsx"))),
        Raw(html=format_html('<a class="btn" href="{}">Imprimir</a>',
                             _href("impressao"))),
    ]


def preparar_exportacao(request, *, queryset, colunas: Sequence[ColunaDeExportacao],
                        ordenaveis: dict, padrao: str,
                        filtraveis: "dict[str, ColunaFiltravel] | None" = None,
                        titulo: str, subtitulo_fn: "Callable[[Any], str] | None" = None):
    """A porta única da view: `?formato=` conhecido vira resposta pronta;
    qualquer outra coisa devolve `None`, e a view desenha a tela normal.

    Roda DEPOIS dos guardas da rota (é chamado de dentro da view), então
    exportar exige exatamente a permissão de ver — quem não vê a tela não
    baixa o arquivo dela disfarçado de planilha.

    `subtitulo_fn(request)` diz, na página de papel, qual filtro estava
    valendo — lido dos MESMOS valores que `preparar_consulta` aplicou.
    """
    formato = request.GET.get("formato", "")
    if formato not in FORMATOS:
        return None

    from comum.listagem import preparar_consulta

    consulta, crus = preparar_consulta(
        request, queryset, ordenaveis=ordenaveis, padrao=padrao,
        filtraveis=filtraveis)
    linhas = list(consulta)

    if formato == "xlsx":
        return em_xlsx(colunas, linhas, titulo=titulo)

    subtitulo = subtitulo_fn(crus) if subtitulo_fn else ""
    return em_impressao(colunas, linhas, titulo=titulo, subtitulo=subtitulo)
