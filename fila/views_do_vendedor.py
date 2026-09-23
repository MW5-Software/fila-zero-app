"""O painel do vendedor no Início (spec 2026-09-16).

É o painel da gestão recortado pela pessoa, montado com as MESMAS peças
(`views_indicadores._filtros`, `_painel`, `_listas`): o vendedor aprende a
ler um painel só, e uma correção no desenho vale para os dois.

A loja é a do cabeçalho (V4), e o ranking é o da loja, sem o que é conversa
do gerente (V5).
"""

from __future__ import annotations

from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import Card, Column, PageHeader, Table
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render

from . import indicadores as ind
from . import metas as regras_de_meta
from .periodo import periodo_anterior, periodo_do_pedido
from .valores import em_reais
from .views_indicadores import (_attrs_da_linha, _filtros, _listas, _painel, _pct,
                                _primeiro_do_ranking, cartao_do_ranking,
                                mes_do_ranking, meses_do_ranking)

__all__ = ["inicio_do_vendedor"]

#: O que o vendedor ordena no ranking. Pausa, ticket, "cliente pediu" e
#: atendimentos ficam de fora (V5): tempo de pausa do colega é conversa do
#: gerente, e não placar. Fora daqui, `?ordenar=` forjado cai no padrão.
ORDENAVEIS = {chave: campos for chave, campos in ind.ORDENAVEIS_DO_RANKING.items()
              if chave in ("nome", "vendido", "vendas", "conversao")}
ORDENAVEIS_COM_META = {**ORDENAVEIS,
                       "pct_meta": ind.ORDENAVEIS_DO_RANKING_COM_META["pct_meta"]}
_FILTRAVEIS = {"nome": ColunaFiltravel("nome", "Vendedor")}


def _colunas(pagina, posicoes, com_meta):
    colunas = [
        # Sem cabeçalho ordenável: a posição é sempre pelo vendido, e "ordenar
        # por posição" seria ordenar pelo vendido com outro nome.
        Column("posicao", str(_("Posição")), align="num",
               render=lambda p: f"{posicoes[p.pk]}º"),
        Column("nome", pagina.cabecalho("nome", str(_("Vendedor"))), strong=True,
               render=lambda p: p.nome or p.email),
        Column("vendido", pagina.cabecalho("vendido", str(_("Vendido"))), align="num",
               render=lambda p: em_reais(p.vendido)),
        Column("vendas", pagina.cabecalho("vendas", str(_("Vendas"))), align="num"),
        Column("conversao", pagina.cabecalho("conversao", str(_("Conversão"))),
               align="num", render=lambda p: _pct(p.conversao)),
    ]
    if com_meta:
        colunas.append(Column("pct_meta", pagina.cabecalho("pct_meta", str(_("% da meta"))),
                              align="num", render=lambda p: _pct(p.pct_meta)))
    return colunas


def _onde_estou(posicoes, pessoa) -> str:
    minha = posicoes.get(pessoa.pk)
    if minha is None:
        # Não há linha para destacar: dizer isso evita o vendedor procurar
        # por si numa tabela em que ele não está.
        return str(_("Você não fechou atendimento no período."))
    return str(_("Você está em %(posicao)sº de %(total)s.")
               % {"posicao": minha, "total": len(posicoes)})


def _blocos(request, empresa, loja, pessoa) -> list:
    periodo = periodo_do_pedido(request.GET)
    lojas = (loja,)
    recorte = ind.Recorte(empresa, lojas, periodo)
    anterior = ind.Recorte(empresa, lojas, periodo_anterior(periodo))
    n = ind.numeros(recorte, vendedor=pessoa)
    a = ind.numeros(anterior, vendedor=pessoa)
    # O ranking é do mês, e não do período do painel (17/09/2026).
    mes = mes_do_ranking(request)
    do_mes = ind.recorte_do_mes(empresa, lojas, mes)
    # As posições saem do recorte inteiro, antes do filtro por nome da
    # tabela: buscar "Ana" não pode fazer a Ana virar a primeira.
    posicoes = ind.posicoes_por_vendido(do_mes)
    consulta = ind.ranking(do_mes, mes)
    # O primeiro da loja, pelo vendido, antes do filtro por nome da tabela —
    # mesma conta do painel da gestão (`_primeiro_do_ranking`).
    primeiro = _primeiro_do_ranking(consulta)
    listagem = montar_pagina(request, consulta,
                             ordenaveis=ORDENAVEIS_COM_META,
                             padrao=ind.PADRAO_DO_RANKING,
                             filtraveis=_FILTRAVEIS,
                             preservar=("periodo", "ranking_mes"))
    return [
        # Uma loja só nas "permitidas": `_filtros` não desenha o campo de loja.
        _filtros(request, periodo, [loja], None),
        _painel(periodo, loja, n, a, anterior, ind.por_dia(recorte, vendedor=pessoa),
                meta=regras_de_meta.meta_da_pessoa(recorte, pessoa)),
        _listas(recorte, n, vendedor=pessoa),
        cartao_do_ranking(
             request, mes, meses=meses_do_ranking(recorte, mes),
             subtitulo=_onde_estou(posicoes, pessoa),
             attrs={"data-ind": "ranking-da-loja"}, body=[
                 listagem.barra,
                 Table(columns=_colunas(listagem, posicoes, com_meta=True),
                       rows=listagem.linhas,
                       row_attrs=lambda linha: _attrs_da_linha(
                           linha, primeiro=primeiro, pessoa=pessoa)),
                 listagem.paginacao,
             ]),
    ]


def inicio_do_vendedor(request, empresa, loja, pessoa) -> HttpResponse:
    """O Início do vendedor: o "Olá" com a data, como para todo mundo, e o
    painel dele logo abaixo."""
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
                *_blocos(request, empresa, loja, pessoa),
            ],
            crumbs=[Crumb("Início")],
            user=request.usuario)
        return render(pagina)
