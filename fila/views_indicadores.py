"""Os indicadores da fila no Início (spec 2026-09-15, entrega 2).

Desde 15/09/2026 o dashboard mora na raiz, abaixo do "Olá" (pedido do João):
é a primeira coisa que a gestão vê ao entrar. `/fila/indicadores` ficou só
como redirecionamento, para link antigo não quebrar.

As lojas que a pessoa enxerga saem de `fila.indicadores.lojas_com_relatorio`,
e a `?loja=` da URL só filtra DENTRO delas: uma loja forjada não amplia o
recorte, ela é descartada e a tela mostra as permitidas.
"""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import (Alert, Button, Card, Cell, Chart, Column,
                               DataPoint, Form, FormGrid, Option,
                               PageHeader, Raw, Select, Table, TextInput)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render

from . import indicadores as ind
from .periodo import ATALHOS, periodo_anterior, periodo_do_pedido
from .tela import trocar_e_abrir_a_fila
from .valores import em_reais

__all__ = ["blocos_dos_indicadores", "indicadores", "inicio_com_indicadores"]


def _pct(valor) -> str:
    return "—" if valor is None else f"{valor:.1f}%".replace(".", ",")


def _dinheiro(valor) -> str:
    return "—" if valor is None else em_reais(valor)


def _variacao_html(v):
    if v is None:
        return ""
    classe = "sobe" if v.valor > 0 else "desce" if v.valor < 0 else "igual"
    seta = "↑" if v.valor > 0 else "↓" if v.valor < 0 else "="
    numero = f"{abs(v.valor):.1f}".replace(".", ",")
    unidade = v.unidade if v.unidade == "%" else f" {v.unidade}"
    return format_html('<span class="ind-variacao {}">{} {}{}</span>',
                       classe, seta, numero, unidade)


def _numero(rotulo, valor, variacao, apoio=""):
    return Card(body=Raw(html=format_html(
        '<div class="ind-numero"><span class="ind-numero-l">{}</span>'
        '<span class="ind-numero-n">{}</span>{}'
        '<span class="ind-numero-apoio">{}</span></div>',
        rotulo, valor, _variacao_html(variacao), apoio)))


def _serie_do_tempo(linhas, periodo):
    """Os rótulos curtos da série por dia ou por hora, para caberem no eixo.

    Por dia com mais de dez dias, só o número do dia ("05"): "05/09" em trinta
    barras se atropela. Por hora, só o horário da loja (8h às 21h) e o que
    tiver movimento fora dele: 24 barras de madrugada vazia espremem as do
    expediente.
    """
    if periodo.dias == 1:
        horas = [i for i, (_r, n, _v) in enumerate(linhas) if n]
        ini = min([8, *horas]) if horas else 8
        fim = max([21, *horas]) if horas else 21
        # Rótulo só nas horas pares: um por barra, em 14 ou mais barras, se
        # atropela no eixo.
        return [(r if i % 2 == 0 else "", n, v)
                for i, (r, n, v) in enumerate(linhas[ini:fim + 1], start=ini)]
    if len(linhas) > 10:
        return [(r[:2], n, v) for r, n, v in linhas]
    return linhas


def _grafico(titulo, pontos, tipo, span=6, altura=180):
    corpo = (Chart(kind=tipo, points=pontos, height=altura,
                   legend="none" if tipo != "donut" else "right")
             if any(p.value for p in pontos)
             else Raw(html=format_html('<p class="ind-vazio">{}</p>',
                                       _("Nada no período."))))
    return Cell(span=span, children=Card(title=titulo, body=corpo))


def _lojas_do_pedido(request, permitidas):
    try:
        escolhida = int(request.GET.get("loja", ""))
    except ValueError:
        return permitidas, None
    uma = [loja for loja in permitidas if loja.pk == escolhida]
    return (uma, uma[0]) if uma else (permitidas, None)


def _filtros(request, periodo, permitidas, loja):
    campos = [
        # As opções neutras ("Intervalo", "Todas as lojas") são opções comuns,
        # e não `empty_label`: o do design system nasce `disabled`, e quem
        # escolhia uma loja não voltava a "Todas" (revisão final, 15/09/2026;
        # o mesmo motivo escrito em `comum/listagem.py`).
        Select(name="periodo", label=_("Período"), span=3,
               value=periodo.chave if periodo.chave != "intervalo" else "",
               options=[Option("", _("Intervalo")),
                        *(Option(chave, rotulo) for chave, rotulo in ATALHOS)]),
        TextInput(name="de", label=_("De"), type="date", span=2,
                  value=request.GET.get("de", "")),
        TextInput(name="ate", label=_("Até"), type="date", span=2,
                  value=request.GET.get("ate", "")),
    ]
    if len(permitidas) > 1:
        campos.append(Select(
            name="loja", label=_("Loja"), span=3, value=str(loja.pk) if loja else "",
            options=[Option("", _("Todas as lojas")),
                     *(Option(str(l.pk), str(l)) for l in permitidas)]))
    campos.append(Cell(span=2, children=Button(label=_("Aplicar"), variant="primary",
                                                type="submit")))
    # A ordenação e o filtro do ranking viajam junto: o `<form method="get">`
    # troca a querystring inteira, e aplicar o período apagava os dois.
    for chave, valor in request.GET.items():
        if chave not in ("periodo", "de", "ate", "loja", "pagina") and valor:
            campos.append(Raw(html=format_html(
                '<input type="hidden" name="{}" value="{}">', chave, valor)))
    return Card(title=_("Indicadores da fila"),
                subtitle=f"{periodo.rotulo}, {loja or _('todas as lojas')}",
                body=Form(method="get", action=reverse("inicio"),
                          children=FormGrid(children=campos)))


def _desde(instante) -> str:
    """A hora no fuso da loja: o banco devolve em UTC, e 21:30 de São Paulo
    aparecia como 00:30 do dia seguinte (revisão final, 15/09/2026)."""
    from django.utils import timezone

    return timezone.localtime(instante).strftime("%d/%m %H:%M")


def _esquecidos(lista):
    if not lista:
        return ""
    # O link troca para a loja DO ITEM e volta para a fila: apontar para
    # `/fila` abria a loja da sessão, onde a pessoa esquecida não está
    # (revisão final, 15/09/2026).
    itens = format_html_join("", '<li>{}: {} em {}, desde {}. <a href="{}">{}</a></li>', (
        (e.o_que, e.nome, e.loja, _desde(e.desde),
         trocar_e_abrir_a_fila(e.loja), _("Abrir a fila desta loja")) for e in lista))
    return Alert(tone="warn", title=_("Ficou aberto de um dia para o outro"),
                 attrs={"data-esquecidos": ""},
                 message=Raw(html=format_html("<ul>{}</ul>", itens)))


_FILTRAVEIS = {"nome": ColunaFiltravel("nome", "Vendedor")}


def _colunas(pagina):
    return [
        Column("nome", pagina.cabecalho("nome", str(_("Vendedor"))), strong=True,
               render=lambda p: p.nome or p.email),
        Column("vendido", pagina.cabecalho("vendido", str(_("Vendido"))), align="num",
               render=lambda p: em_reais(p.vendido)),
        Column("atendimentos", pagina.cabecalho("atendimentos", str(_("Atendimentos"))), align="num"),
        Column("vendas", pagina.cabecalho("vendas", str(_("Vendas"))), align="num"),
        Column("conversao", pagina.cabecalho("conversao", str(_("Conversão"))), align="num",
               render=lambda p: _pct(p.conversao)),
        Column("ticket", pagina.cabecalho("ticket", str(_("Ticket médio"))), align="num",
               render=lambda p: _dinheiro(p.ticket)),
        Column("pediu", pagina.cabecalho("pediu", str(_("Cliente pediu"))), align="num"),
        Column("pausa", pagina.cabecalho("pausa", str(_("Pausa"))), align="num",
               render=lambda p: f"{int(p.pausa.total_seconds() // 60)} min"),
    ]


def blocos_dos_indicadores(request, empresa, permitidas) -> list:
    """Os blocos do dashboard (filtros, esquecidos, números, gráficos e
    ranking) para as lojas `permitidas`, que quem chama já tirou do alcance do
    cargo (`indicadores.lojas_com_relatorio`)."""
    periodo = periodo_do_pedido(request.GET)
    lojas, loja = _lojas_do_pedido(request, permitidas)
    recorte = ind.Recorte(empresa, tuple(lojas), periodo)
    anterior = ind.Recorte(empresa, tuple(lojas), periodo_anterior(periodo))
    n, a = ind.numeros(recorte), ind.numeros(anterior)
    blocos = [
        _filtros(request, periodo, permitidas, loja),
        _esquecidos(ind.esquecidos(empresa, lojas)),
        FormGrid(children=[
            Cell(span=3, children=_numero(_("Atendimentos"), n.atendimentos,
                                          ind.variacao(n.atendimentos, a.atendimentos))),
            Cell(span=3, children=_numero(
                _("Conversão"), _pct(n.conversao),
                ind.variacao(n.conversao, a.conversao, pontos=True),
                _("Cliente pediu: %(quantos)s, %(conversao)s")
                % {"quantos": n.pediu, "conversao": _pct(n.conversao_pediu)})),
            Cell(span=3, children=_numero(_("Vendido"), em_reais(n.vendido),
                                          ind.variacao(n.vendido, a.vendido))),
            Cell(span=3, children=_numero(_("Ticket médio"), _dinheiro(n.ticket),
                                          ind.variacao(n.ticket, a.ticket))),
        ]),
    ]
    dias = _serie_do_tempo(ind.por_dia(recorte), periodo)
    # Série do tempo numa cor só: cor por barra, num gráfico de dias,
    # sugere categorias diferentes onde só há o mesmo número no tempo.
    cor = "var(--chart-1)"
    blocos.append(FormGrid(children=[
        _grafico(_("Atendimentos por hora") if periodo.dias == 1 else _("Atendimentos por dia"),
                 [DataPoint(r, n_, cor) for r, n_, _v in dias], "bar"),
        _grafico(_("Vendido por hora") if periodo.dias == 1 else _("Vendido por dia"),
                 [DataPoint(r, float(v)) for r, _n, v in dias], "line"),
        _grafico(_("Vendido por grupo de item"),
                 [DataPoint(g, float(v)) for g, v in ind.por_grupo(recorte)],
                 "bar_h"),
        _grafico(_("Motivos de não venda"),
                 [DataPoint(m, q) for m, q in ind.motivos(recorte)], "donut"),
        # Todos em metades, mesmo sobrando o quinto sozinho: o desenho
        # escala pela largura da caixa, e o texto junto. Em terços ficava
        # ilegível; na largura toda, enorme (conferido em 15/09/2026).
        _grafico(_("Minutos em pausa por tipo"),
                 [DataPoint(t, m) for t, m in ind.pausa_por_tipo(recorte)],
                 "bar_h"),
    ]))
    listagem = montar_pagina(request, ind.ranking(recorte),
                             ordenaveis=ind.ORDENAVEIS_DO_RANKING,
                             padrao=ind.PADRAO_DO_RANKING,
                             filtraveis=_FILTRAVEIS,
                             preservar=("periodo", "de", "ate", "loja"))
    blocos.append(Card(title=_("Ranking de vendedores"), padded=False, body=[
        listagem.barra,
        Table(columns=_colunas(listagem), rows=listagem.linhas),
        listagem.paginacao,
    ]))
    return blocos


def inicio_com_indicadores(request, empresa, permitidas) -> HttpResponse:
    """O Início da gestão: o "Olá" com a data, como para todo mundo, e o
    dashboard logo abaixo."""
    from nucleo.views import _data_de_hoje
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        pagina = site.page(
            title="Início", width="full",
            stylesheets=["/static/plataforma/listagem.css",
                         "/static/fila/indicadores.css"],
            content=[
                aviso_de_personificacao(request),
                PageHeader(title=site.resolve_nome("Olá, {nome}!", request.usuario),
                           subtitle=_data_de_hoje()),
                *blocos_dos_indicadores(request, empresa, permitidas),
            ],
            crumbs=[Crumb("Início")],
            user=request.usuario)
        return render(pagina)


# A tela própria saiu (15/09/2026): o endereço antigo leva ao Início com os
# mesmos filtros, para link salvo ou compartilhado não quebrar. As guardas
# ficam, para quem não pode continuar tomando 404 e as varreduras enxergarem
# a rota guardada.
@exigir_permissao("fila.relatorios")
@exigir_modulo_ligado("fila")
def indicadores(request) -> HttpResponse:
    consulta = request.GET.urlencode()
    return HttpResponseRedirect(reverse("inicio") + (f"?{consulta}" if consulta else ""))
