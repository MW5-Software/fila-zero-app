"""O trio de toda tela de listagem: filtro, ordenação e paginação.

R46 (`docs/superpowers/decisoes-2026-08-20-fatia-fina.md`) tornou os três
obrigatórios em toda tela com tabela, sem exceção. A razão de existir este
módulo — e não uma cópia por tela — é que a próxima tela custe o mesmo que as
primeiras custaram, não o dobro.

Mora em `plataforma/`, e não em `contas/`, pelo mesmo motivo de
`comum.guardas_de_modulo`: é infraestrutura que qualquer tela de qualquer app
vai precisar, não um detalhe de contas de usuário.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from django.db.models import Q, QuerySet
from django.utils.html import format_html

from nucleo.components import Pagination as _PaginacaoNucleo, Raw

__all__ = ["OPERADORES", "PARAM_ORDENAR", "PARAM_PAGINA", "POR_PAGINA",
           "Pagina", "montar_pagina", "nome_do_campo"]

#: 25 linhas por página — o PADRÃO do código, e não mais o número que
#: `montar_pagina` de fato usa: cada instalação pode mudá-lo pelo parâmetro
#: `itens_por_pagina` (`plataforma.parametro.PARAMETRO_ITENS_POR_PAGINA`,
#: que lê esta constante como o próprio `padrao` — uma fonte só para o
#: mesmo número). `montar_pagina` lê o valor efetivo por
#: `plataforma.parametro_catalogo.valor_de`, nunca esta constante direto.
POR_PAGINA = 25

#: Nomes dos parâmetros de querystring — os mesmos nas duas telas, para que
#: um link de ordenar ou paginar escrito numa tela sirva de referência para
#: a próxima sem inventar vocabulário novo.
PARAM_ORDENAR = "ordenar"
PARAM_PAGINA = "pagina"

#: `f:<coluna>:<operador>` — o mesmo vocabulário do `sementes-premix`
#: (`app/tela_grid.py`), de propósito: é o padrão que já existe nos sistemas
#: da MW5, e a matriz não inventa um segundo para dizer a mesma coisa. O
#: separador é `:` porque nome de coluna tem ponto e espaço ("Vl. Unit." é
#: real lá), e um separador que aparece no nome quebraria a leitura na coluna
#: errada.
PREFIXO_FILTRO = "f:"

#: Que campos cada tipo de coluna ganha, e como cada um se lê. Tipo
#: desconhecido cai em texto: um campo a mais é melhor que uma coluna sem
#: filtro nenhum.
OPERADORES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "data": (("de", "de", "date"), ("ate", "até", "date")),
    "numero": (("min", "mínimo", "text"), ("max", "máximo", "text")),
    "texto": (("contem", "contém", "text"),),
    #: Coluna de valores conhecidos e poucos — perfil, situação. Vira uma
    #: caixa de escolha, não um campo de digitar: quem filtra por "ativo"
    #: não deveria ter de adivinhar se o sistema escreve "Ativo", "ativo"
    #: ou "1", e um campo de texto sobre lista fechada convida ao erro.
    "opcoes": (("igual", "", "select"),),
}

#: Como cada operador vira `lookup` do ORM. É o par do dicionário acima: o de
#: cima diz o que a tela desenha, este diz o que a consulta faz.
LOOKUPS = {"contem": "icontains", "de": "gte", "ate": "lte",
           "min": "gte", "max": "lte", "igual": "exact"}

TODOS_OS_OPERADORES = frozenset(LOOKUPS)


def nome_do_campo(chave: str, operador: str) -> str:
    """O `name` do campo de filtro da coluna `chave` para `operador`."""
    return f"{PREFIXO_FILTRO}{chave}:{operador}"


def _instante_do_dia(modelo, campo: str, operador: str, digitado: str):
    """A data crua do formulário virada em INSTANTE, quando o campo é
    `DateTimeField`.

    O `<input type="date">` manda `"2026-08-02"`, e comparar um instantão
    com uma data nua tem duas armadilhas: o Django avisa (e em produção,
    avisa a cada busca) sobre datetime sem fuso, e `"até"` viraria teto na
    MEIA-NOITE do dia escolhido — excluindo exatamente o dia que a pessoa
    pediu. Então: "de" começa às 00:00 do dia com fuso; "até" termina no
    último microssegundo dele.

    Devolve o `datetime` consciente, a própria string quando o campo é
    `DateField` (comparação com data é direta), ou `None` quando a data não
    se interpreta — e aí o filtro NÃO é aplicado: data quebrada que virasse
    consulta era um 500 por caractere digitado errado.
    """
    from datetime import datetime, time

    from django.db import models as _models
    from django.utils import timezone

    try:
        campo_real = modelo._meta.get_field(campo)
    except Exception:
        return digitado
    if not isinstance(campo_real, _models.DateTimeField):
        return digitado
    try:
        dia = datetime.strptime(digitado, "%Y-%m-%d").date()
    except ValueError:
        return None
    hora = time.min if operador == "de" else time.max
    return timezone.make_aware(datetime.combine(dia, hora))


def _partes_do_filtro(chave_crua: str) -> "tuple[str, str] | None":
    """`f:login:contem` -> `("login", "contem")`, ou `None`.

    Corta no ÚLTIMO `:`: o nome da coluna vem antes e pode ter qualquer coisa
    dentro, menos os dois-pontos do operador no fim."""
    if not chave_crua.startswith(PREFIXO_FILTRO):
        return None
    resto = chave_crua[len(PREFIXO_FILTRO):]
    coluna, separador, operador = resto.rpartition(":")
    if not separador or not coluna or operador not in TODOS_OS_OPERADORES:
        return None
    return coluna, operador

#: `chave da URL -> campo(s) real(is) do ORM`. Um valor pode ser um único
#: campo ou uma tupla (para desempate estável, como "nome" cair para
#: `first_name, last_name, username`). NUNCA é o parâmetro cru que chega em
#: `?ordenar=`: é o mapa que decide o que `?ordenar=` pode significar.
Ordenaveis = dict[str, "str | tuple[str, ...]"]


@dataclass(frozen=True)
class ColunaFiltravel:
    """Uma coluna que ganha campo de filtro na barra.

    `campos` são os campos reais do ORM em que a busca procura — a coluna
    "Nome" pode nascer de `first_name` e `last_name`, e quem digita não sabe
    disso. `tipo` decide quais operadores ela ganha (ver `OPERADORES`).
    """

    campos: "str | tuple[str, ...]"
    rotulo: str
    tipo: str = "texto"
    #: Só para `tipo="opcoes"`: os pares `(valor, rótulo)` da caixa de
    #: escolha. É um `Callable` e não uma lista pronta porque as opções
    #: costumam vir do banco (os cargos que existem HOJE nesta instalação) —
    #: uma lista avaliada na importação do módulo congelaria o que existia
    #: quando o processo subiu.
    opcoes: "Callable[[], Sequence[tuple[str, str]]] | None" = None

    @property
    def lista_de_campos(self) -> tuple[str, ...]:
        return (self.campos,) if isinstance(self.campos, str) else self.campos


@dataclass(frozen=True)
class Pagina:
    """O que uma tela de listagem precisa para desenhar as três partes:
    as linhas já fatiadas, o componente `Pagination` do nucleo pronto (com
    `url_for_page` preservando filtro e ordenação), um `cabecalho()` para
    transformar o rótulo de qualquer coluna ordenável num link, e o valor
    efetivo da ordenação em curso — para a tela repassar num campo oculto
    dentro do próprio `FilterBar`, e o filtro não apagar a ordenação quando
    for submetido (ver o comentário de `_url_com` sobre a via inversa)."""

    linhas: list[Any]
    paginacao: _PaginacaoNucleo
    cabecalho: Callable[[str, str], str]
    ordenar_atual: str
    #: A `FilterBar` pronta, com um campo por operador de cada coluna
    #: filtrável, já preenchida com o que está valendo — ou `""` quando a
    #: tela não declarou coluna filtrável nenhuma.
    barra: Any = ""


def _partir(valor: str) -> tuple[str, bool]:
    """`"nome"` -> `("nome", False)`; `"-nome"` -> `("nome", True)` — o sinal
    de menos é a convenção do próprio `order_by` do Django, reaproveitada
    aqui em vez de inventar outra."""
    valor = (valor or "").strip()
    if valor.startswith("-"):
        return valor[1:], True
    return valor, False


def _resolver_ordenacao(
    bruto: str, ordenaveis: Ordenaveis, padrao: str,
) -> tuple[str, bool, tuple[str, ...]]:
    """`(chave, desc, campos_orm)` — `bruto` (o `?ordenar=` da requisição)
    nunca chega ao `order_by` diretamente: só a CHAVE dele é lida, e só
    passa se `ordenaveis` a declarar. Uma chave ausente, vazia ou forjada
    (`?ordenar=senha`, `?ordenar=--`) cai no `padrao` em vez de levantar —
    a mesma postura de `_pagina_valida` abaixo: entrada ruim vira o padrão
    sensato, nunca um 500."""
    chave, desc = _partir(bruto)
    if chave not in ordenaveis:
        chave, desc = _partir(padrao)
    campos = ordenaveis[chave]
    if isinstance(campos, str):
        campos = (campos,)
    if desc:
        campos = tuple(f"-{campo}" for campo in campos)
    return chave, desc, campos


def _pagina_valida(bruto: "str | None") -> int:
    """`?pagina=` sempre vira um inteiro >= 1. Ausente, vazio, não numérico,
    zero ou negativo caem todos em 1 — nenhum deles é motivo para a tela
    responder 500 por causa de um parâmetro de URL que qualquer pessoa pode
    digitar à mão."""
    try:
        numero = int(bruto)
    except (TypeError, ValueError):
        return 1
    return numero if numero >= 1 else 1


def _url_com(request, overrides: "dict[str, Any]") -> str:
    """A URL atual — caminho e querystring —, com os parâmetros de
    `overrides` trocados (ou removidos, se o valor for `None`) e TODO o
    resto preservado.

    É isto que resolve a metade "ordenar/paginar preserva o filtro" do
    defeito clássico: um link de ordenar ou de próxima página montado só com
    o parâmetro que mudou (`f"?{param}={valor}"`) apaga em silêncio
    qualquer `?q=` que já estivesse na URL. Partindo de `request.GET.copy()`
    em vez de uma string nova, o que já estava lá sobrevive por padrão — só
    muda o que a chamada pediu para mudar.

    A OUTRA metade — o filtro apagando a ordenação — não é este mecanismo:
    `FilterBar` é um `<form method="get">` de verdade, e o navegador
    substitui a querystring inteira pelos campos do formulário na
    submissão. Por isso `Pagina.ordenar_atual` existe: a tela usa esse
    valor para pôr um campo oculto de `ordenar` dentro do próprio
    `FilterBar`, e a submissão do filtro devolve a ordenação junto.
    """
    params = request.GET.copy()
    for chave, valor in overrides.items():
        if valor is None:
            params.pop(chave, None)
        else:
            params[chave] = str(valor)
    query = params.urlencode()
    return f"{request.path}?{query}" if query else request.path


def _filtro_pedido(chave_crua: str, valor, filtraveis):
    """`(coluna, operador, digitado)` do parâmetro da URL — ou `None` quando
    ele não vira filtro nenhum.

    **Coluna que a tela não declarou filtrável é ignorada**, e o mesmo vale
    para operador que aquele tipo de coluna não oferece: o parâmetro vem da
    URL, e a URL é do lado de fora — só o que a tela declarou pode virar
    consulta.
    """
    partes = _partes_do_filtro(chave_crua)
    if not partes:
        return None
    chave_coluna, operador = partes
    coluna = filtraveis.get(chave_coluna)
    digitado = (valor or "").strip()
    if coluna is None or not digitado:
        return None
    permitidos = {op for op, _, _ in
                  OPERADORES.get(coluna.tipo, OPERADORES["texto"])}
    if operador not in permitidos:
        return None
    return coluna, operador, digitado


def _alternativas(model, coluna, operador: str, digitado: str):
    """O `Q` de UMA coluna: OU entre os campos dela.

    A "Nome" procura em nome e sobrenome, e as duas alternativas são a mesma
    pergunta. Entre COLUNAS diferentes quem combina é o `filter` de quem
    chama, com E — dois filtros preenchidos estreitam o resultado, nunca
    alargam.
    """
    from django.db.models import Q

    lookup = LOOKUPS[operador]
    alternativas = Q()
    for campo in coluna.lista_de_campos:
        valor_final = digitado
        if operador in ("de", "ate"):
            valor_final = _instante_do_dia(model, campo, operador, digitado)
            if valor_final is None:
                continue
        alternativas |= Q(**{f"{campo}__{lookup}": valor_final})
    return alternativas


def preparar_consulta(
    request,
    queryset: QuerySet,
    *,
    ordenaveis: Ordenaveis,
    padrao: str,
    filtraveis: "dict[str, ColunaFiltravel] | None" = None,
) -> "tuple[QuerySet, dict[str, str]]":
    """O filtro e a ordenação da URL aplicados ao queryset — SEM paginar.

    É a parte de `montar_pagina` que a EXPORTAÇÃO também precisa: o arquivo
    que sai tem que ser exatamente o que está na tela, então filtro e ordem
    não podem existir em duas versões. Devolve `(queryset, crus)` — os
    valores digitados que valeram, para a barra se redesenhar preenchida.

    A documentação completa das regras (coluna não declarada é ignorada,
    entre campos de uma coluna é OU, entre colunas é E, `?ordenar=` só vale
    por chave declarada) vale aqui por referência.
    """
    filtraveis = filtraveis or {}
    crus: dict[str, str] = {}
    for chave_crua, valor in request.GET.items():
        pedido = _filtro_pedido(chave_crua, valor, filtraveis)
        if pedido is None:
            continue
        coluna, operador, digitado = pedido
        alternativas = _alternativas(queryset.model, coluna, operador, digitado)
        if not alternativas:
            continue
        crus[chave_crua] = digitado
        queryset = queryset.filter(alternativas)

    _, _, campos = _resolver_ordenacao(
        request.GET.get(PARAM_ORDENAR, ""), ordenaveis, padrao)
    return queryset.order_by(*campos), crus


def montar_pagina(
    request,
    queryset: QuerySet,
    *,
    ordenaveis: Ordenaveis,
    padrao: str,
    filtraveis: "dict[str, ColunaFiltravel] | None" = None,
    preservar: "Sequence[str]" = (),
) -> Pagina:
    """Lê `?ordenar=` e `?pagina=` da requisição atual e devolve a `Pagina`
    pronta para a tela desenhar.

    `queryset` chega SEM `order_by` (e já filtrado, se a tela tiver
    filtro) — quem ordena é esta função, e só por uma chave que
    `ordenaveis` declarou. `padrao` é a chave (com ou sem `-` na frente) a
    valer quando `?ordenar=` está ausente ou não bate com nada declarado.
    """
    # Filtra ANTES de ordenar e paginar: o total que a paginação mostra tem
    # que ser o total do que a pessoa está vendo, não o da tabela inteira.
    queryset, crus = preparar_consulta(
        request, queryset, ordenaveis=ordenaveis, padrao=padrao,
        filtraveis=filtraveis)
    # Só para saber qual coluna está ativa (a seta do cabeçalho e o campo
    # oculto da barra): os campos do ORM já foram aplicados acima.
    chave, desc, _ = _resolver_ordenacao(
        request.GET.get(PARAM_ORDENAR, ""), ordenaveis, padrao)

    # Import adiado: `parametro_catalogo` não é importado no topo do arquivo
    # de propósito — evita ciclo com `plataforma.parametro`, que declara o
    # parâmetro abaixo e importa `POR_PAGINA` DESTE módulo (ver o docstring
    # dela). Por essa mesma razão `POR_PAGINA` continua existindo aqui: é o
    # padrão que a declaração referencia, e não um número duplicado à parte.
    from plataforma.parametro_catalogo import valor_de

    por_pagina = valor_de("itens_por_pagina")

    total = queryset.count()
    numero = _pagina_valida(request.GET.get(PARAM_PAGINA))
    inicio = (numero - 1) * por_pagina
    linhas = list(queryset[inicio:inicio + por_pagina])
    # Página pedida além do fim de verdade (a lista encolheu desde o último
    # clique, ou o número foi forjado na mão) — volta pra 1 em vez de
    # desenhar uma tabela vazia por acidente de aritmética, com resultado
    # que existe mas mora noutra página.
    if not linhas and total and numero != 1:
        numero = 1
        linhas = list(queryset[:por_pagina])

    def url_for_page(pagina: int) -> str:
        return _url_com(request, {PARAM_PAGINA: pagina})

    def cabecalho(chave_coluna: str, rotulo: str) -> str:
        ativa = chave_coluna == chave
        # Ativa e ascendente -> clicar desce. Qualquer outro caso (inativa,
        # ou ativa e já descendente) -> clicar volta a ascendente. Só dois
        # estados: a regra pede ordenação por coluna, não um ciclo de três
        # com "sem ordenação nenhuma" no meio.
        proxima = f"-{chave_coluna}" if (ativa and not desc) else chave_coluna
        href = _url_com(
            request, {PARAM_ORDENAR: proxima, PARAM_PAGINA: None})
        seta = (" ↓" if desc else " ↑") if ativa else ""
        return format_html('<a href="{}">{}{}</a>', href, rotulo, seta)

    ordenar_atual = f"-{chave}" if desc else chave

    def _barra():
        """A barra de filtros: um campo por operador de cada coluna
        filtrável, na ordem em que a tela as declarou.

        ACIMA da tabela e numa linha só — o mesmo desenho do
        `sementes-premix` (`app/tela_grid.py::_barra`), e pelo motivo que
        aprenderam lá: a barra do design system quebra linha, e cada filtro a
        mais empurrava a tabela para baixo da dobra. A folha deste projeto
        (`static/plataforma/listagem.css`) troca a quebra por rolagem
        lateral, então a tabela fica onde está.
        """
        if not filtraveis:
            return ""
        from nucleo.components import FilterBar, Select, TextInput

        campos_da_barra = []
        for chave_coluna, coluna in filtraveis.items():
            operadores = OPERADORES.get(coluna.tipo, OPERADORES["texto"])
            for operador, como_se_le, tipo_do_campo in operadores:
                nome = nome_do_campo(chave_coluna, operador)
                # Um operador só ("contém") não precisa dizer qual é: o
                # rótulo vira "Login contém", que é ruído. Com dois ou mais,
                # o sufixo é o que distingue "de" de "até".
                rotulo = (coluna.rotulo if len(operadores) == 1
                          else f"{coluna.rotulo} {como_se_le}")
                if tipo_do_campo == "select":
                    # "Todos" entra como OPÇÃO, e não por `empty_label`: o
                    # `empty_label` do design system nasce `disabled` — certo
                    # para um cadastro, onde a opção neutra é um lembrete de
                    # escolher, e errado aqui, onde voltar a "Todos" é
                    # justamente como se tira o filtro. Com `disabled`, quem
                    # filtrasse por Gestor não conseguia mais desfiltrar pela
                    # própria caixa.
                    campos_da_barra.append(Select(
                        name=nome, label=rotulo,
                        value=crus.get(nome, ""),
                        options=[("", "Todos"),
                                 *(coluna.opcoes() if coluna.opcoes else ())],
                        span=3))
                    continue
                campos_da_barra.append(TextInput(
                    name=nome, label=rotulo, type=tipo_do_campo,
                    value=crus.get(nome, ""), span=3))

        # Os parâmetros que a TELA usa fora da tabela (`preservar`) viajam em
        # campos ocultos e no "Limpar": o `<form method="get">` troca a
        # querystring inteira, e buscar na tabela apagava o período e a loja
        # escolhidos acima dela (indicadores do Fila Zero, 15/09/2026).
        mantidos = [(chave, request.GET[chave]) for chave in preservar
                    if request.GET.get(chave)]
        extras = []
        if crus:
            # `<a>`, e não botão: limpar é ir para a tela sem filtro nenhum, e
            # um botão dentro deste `<form>` submeteria o formulário em vez de
            # navegar.
            limpar = request.path
            if mantidos:
                from urllib.parse import urlencode

                limpar = f"{request.path}?{urlencode(mantidos)}"
            extras.append(Raw(html=format_html(
                '<a class="btn ghost filtro-limpar" href="{}">Limpar</a>',
                limpar)))

        return FilterBar(
            fields=[
                *campos_da_barra,
                # A ordenação em curso viaja num campo oculto: um
                # `<form method="get">` substitui a querystring inteira ao ser
                # submetido, e sem isto filtrar apagaria a coluna que a pessoa
                # acabou de ordenar.
                Raw(html=format_html(
                    '<input type="hidden" name="{}" value="{}">',
                    PARAM_ORDENAR, ordenar_atual)),
                *(Raw(html=format_html('<input type="hidden" name="{}" value="{}">',
                                       chave, valor))
                  for chave, valor in mantidos),
            ],
            # "Buscar", não "Filtrar": é o verbo que a pessoa usa para o que
            # está fazendo. O botão é azul (`.card .filters` na folha deste
            # projeto) porque é a ação principal do bloco.
            action=request.path, submit_label="Buscar", extra_actions=extras,
        )

    return Pagina(
        linhas=linhas,
        paginacao=_PaginacaoNucleo(
            page=numero, per_page=por_pagina, total=total,
            url_for_page=url_for_page),
        cabecalho=cabecalho,
        ordenar_atual=ordenar_atual,
        barra=_barra(),
    )
