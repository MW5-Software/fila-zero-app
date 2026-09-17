"""Os indicadores da fila no Início (spec 2026-09-15, entrega 2).

Desde 15/09/2026 o dashboard mora na raiz, abaixo do "Olá" (pedido do João):
é a primeira coisa que a gestão vê ao entrar. `/fila/indicadores` ficou só
como redirecionamento, para link antigo não quebrar.

As lojas que a pessoa enxerga saem de `fila.indicadores.lojas_com_relatorio`,
e a `?loja=` da URL só filtra DENTRO delas: uma loja forjada não amplia o
recorte, ela é descartada e a tela mostra a loja do cabeçalho.

Desde 17/09/2026 o painel abre na loja do cabeçalho, e "Todas as lojas" é uma
escolha explícita. Antes, sem `?loja=`, ele somava todas: a Sylvia na Matriz
via o vendedor do Centro no ranking, sem coluna que dissesse a loja.
"""

from __future__ import annotations

import math

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import (Alert, Button, Card, Cell, Column, Form,
                               FormGrid, Option, PageHeader, Raw, Select,
                               Table)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render

from . import graficos
from . import metas as regras_de_meta
from . import indicadores as ind
from .graficos import Coluna
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
        # A linha existe mesmo sem comparação: sem ela o cartão ficava mais
        # baixo que os vizinhos (diagramação do Início, 15/09/2026).
        return format_html('<span class="ind-variacao igual">{}</span>',
                           _("Sem base para comparar"))
    classe = "sobe" if v.valor > 0 else "desce" if v.valor < 0 else "igual"
    seta = "↑" if v.valor > 0 else "↓" if v.valor < 0 else "="
    numero = f"{abs(v.valor):.1f}".replace(".", ",")
    unidade = v.unidade if v.unidade == "%" else f" {v.unidade}"
    return format_html('<span class="ind-variacao {}">{} {}{}</span>',
                       classe, seta, numero, unidade)


def _comparado_a(periodo) -> str:
    """ "Comparado a 08/09 a 14/09", ou "a 14/09 até 11:34" quando o anterior
    é um pedaço de dia: diz de onde vem a seta, na linha de apoio."""
    from datetime import timedelta

    from django.utils import timezone

    de, ate = timezone.localtime(periodo.de), timezone.localtime(periodo.ate)
    hora = ""
    if ate.hour == 0 and ate.minute == 0:
        ultimo = (ate - timedelta(days=1)).date()
    else:
        ultimo, hora = ate.date(), ate.strftime("%H:%M")
    trecho = (f"{de:%d/%m}" if de.date() == ultimo
              else f"{de:%d/%m} a {ultimo:%d/%m}")
    # A hora só num dia só ("14/09 até 11:34"): em vários dias ela quebrava a
    # linha do cartão e não mudava a leitura.
    if hora and de.date() == ultimo:
        trecho += " " + str(_("até %(hora)s") % {"hora": hora})
    return str(_("Comparado a %(trecho)s") % {"trecho": trecho})


def _aba(serie, rotulo, valor, variacao, apoio="", marcada=False):
    """Um número do período que é também o botão da série do gráfico.

    É um rádio de verdade dentro do rótulo: troca pelo teclado, funciona sem
    JavaScript, e o CSS (`:has`) mostra a série marcada."""
    return format_html(
        '<label class="ind-aba"><input type="radio" name="ind-serie" value="{}"{}>'
        '<span class="ind-aba-l">{}</span><span class="ind-aba-n">{}</span>{}'
        '<span class="ind-aba-apoio">{}</span></label>',
        serie, mark_safe(" checked") if marcada else "", rotulo, valor,
        _variacao_html(variacao), apoio)


def _fatias_do_grafico(fatias, periodo, agora):
    """As colunas do gráfico: por hora, só o horário da loja (8h às 21h) e o
    que tiver movimento fora dele, porque 24 colunas de madrugada vazia
    espremem as do expediente; por dia, o número do dia no eixo.

    O rótulo do eixo pula de tanto em tanto quando as colunas passam de 31:
    um intervalo de meses teria centenas de "05" encavalados. A dica de cada
    coluna continua com a data inteira.
    """
    if periodo.dias == 1:
        com_movimento = [i for i, f in enumerate(fatias) if f.atendimentos]
        ini = min([8, *com_movimento])
        fim = max([21, *com_movimento])
        fatias = fatias[ini:fim + 1]
        atual = f"{agora.hour}h" if agora.date() == timezone.localtime(periodo.de).date() else None
        return [(f, f.rotulo, f.rotulo == atual) for f in fatias]
    # Período terminado não tem a coluna de hoje, e nenhuma fica listrada.
    hoje = f"{agora:%d/%m}"
    pulo = math.ceil(len(fatias) / 31)
    return [(f, f.rotulo[:2] if i % pulo == 0 else "", f.rotulo == hoje)
            for i, f in enumerate(fatias)]


def _por_cento(x) -> str:
    return f"{x:g}%".replace(".", ",")


def _faixa_da_meta(m) -> str:
    """A meta do mês dentro do painel, entre os números e o gráfico: é a régua
    do vendido que está logo acima."""
    a = m.acompanhamento
    if a.encerrado:
        apoio = (_("Bateu a meta, %(acima)s acima.") % {"acima": em_reais(a.excedente)}
                 if a.batida else
                 _("Ficou em %(pct)s da meta, faltaram %(falta)s.")
                 % {"pct": _pct(a.atingido), "falta": em_reais(a.falta)})
    elif a.batida:
        apoio = _("Meta batida, %(acima)s acima.") % {"acima": em_reais(a.excedente)}
    else:
        apoio = (_("Faltam %(falta)s, %(por_dia)s por dia até %(ultimo)s.")
                 % {"falta": em_reais(a.falta), "por_dia": em_reais(a.por_dia),
                    "ultimo": f"{a.ultimo_dia:%d/%m}"})
        apoio += " " + (_("No ritmo atual, fecha em %(projecao)s.")
                        % {"projecao": em_reais(a.projecao)}
                        if a.projecao is not None else _("Projeção a partir de amanhã."))
    if m.soma_vendedores:
        cobre = (_("As metas dos vendedores somam %(soma)s e cobrem a da loja.")
                 if m.soma_vendedores >= a.meta else
                 _("As metas dos vendedores somam %(soma)s, abaixo da meta da loja."))
        apoio += " " + cobre % {"soma": em_reais(m.soma_vendedores)}
    if m.lojas_com_meta < m.lojas:
        apoio += " " + (_("%(com)s de %(total)s lojas com meta: a meta e o vendido desta faixa são só delas.")
                        % {"com": m.lojas_com_meta, "total": m.lojas})
    return format_html(
        '<div class="ind-meta" data-ind="meta">'
        '<div class="ind-meta-cab"><span>{} <b>{}</b></span><strong>{}</strong></div>'
        '<div class="ind-meta-barra{}"><span style="width: {}%"></span></div>'
        '<p class="ind-meta-apoio">{}</p></div>',
        _("Meta do mês"), em_reais(a.meta), _pct(a.atingido),
        " batida" if a.batida else "", f"{min(a.atingido, 100):.1f}", apoio)


def _painel(periodo, loja, n, a, anterior, fatias, meta=None):
    """Os quatro números do período em cima e, embaixo, a série de um deles no
    tempo. Um cartão só: o número e o dia a dia dele são a mesma pergunta, e
    antes eram seis cartões soltos que repetiam o período em cada um."""
    agora = timezone.localtime()
    v_atendimentos = ind.variacao(n.atendimentos, a.atendimentos)
    v_conversao = ind.variacao(n.conversao, a.conversao, pontos=True)
    v_vendido = ind.variacao(n.vendido, a.vendido)
    v_ticket = ind.variacao(n.ticket, a.ticket)
    abas = format_html_join("", "{}", ((aba,) for aba in (
        _aba("atendimentos", _("Atendimentos"), n.atendimentos, v_atendimentos),
        _aba("conversao", _("Conversão"), _pct(n.conversao), v_conversao,
             _("Cliente pediu: %(quantos)s, %(conversao)s")
             % {"quantos": n.pediu, "conversao": _pct(n.conversao_pediu)}),
        # O vendido abre marcado: é o número que a dona olha primeiro.
        _aba("vendido", _("Vendido"), em_reais(n.vendido), v_vendido, marcada=True),
        _aba("ticket", _("Ticket médio"), _dinheiro(n.ticket), v_ticket),
    )))

    if not n.atendimentos:
        series = format_html('<p class="ind-vazio">{}</p>',
                             _("Nenhum atendimento fechado no período."))
    else:
        linhas = _fatias_do_grafico(fatias, periodo, agora)
        agora_texto = _("até agora")

        def serie(chave, rotulo, valor, texto, marca, inteiro=False):
            lista = []
            for f, eixo, e_agora in linhas:
                v = valor(f)
                lista.append(Coluna(eixo, f.rotulo, v, "—" if v is None else texto(v), e_agora))
            return graficos.colunas(chave, rotulo, lista, marca=marca, inteiro=inteiro,
                                    visivel=chave == "vendido", agora_texto=agora_texto)

        por_hora = periodo.dias == 1
        series = format_html_join("", "{}", ((s_,) for s_ in (
            serie("atendimentos",
                  _("Atendimentos por hora") if por_hora else _("Atendimentos por dia"),
                  lambda f: f.atendimentos, str, lambda x: str(int(x)), inteiro=True),
            serie("conversao",
                  _("Conversão por hora") if por_hora else _("Conversão por dia"),
                  lambda f: round(100 * f.vendas / f.atendimentos, 1) if f.atendimentos else None,
                  _pct, _por_cento),
            serie("vendido", _("Vendido por hora") if por_hora else _("Vendido por dia"),
                  lambda f: f.vendido, em_reais, graficos.dinheiro_curto),
            serie("ticket",
                  _("Ticket médio por hora") if por_hora else _("Ticket médio por dia"),
                  lambda f: f.vendido / f.vendas if f.vendas else None,
                  em_reais, graficos.dinheiro_curto),
        )))

    # "Comparado a …" uma vez, no cabeçalho, e só quando alguma seta existe:
    # embaixo de quatro "Sem base para comparar" ele se contradiria.
    tem_base = any(v is not None for v in (v_atendimentos, v_conversao, v_vendido, v_ticket))
    return Card(
        title=f"{periodo.rotulo}, {loja or _('todas as lojas')}",
        subtitle=_comparado_a(anterior.periodo) if tem_base else None,
        padded=False, attrs={"data-ind": "painel"},
        body=Raw(html=format_html(
            '<div class="ind-painel"><div class="ind-abas" role="radiogroup" aria-label="{}">{}</div>'
            '{}<div class="ind-series">{}</div></div>',
            _("Número mostrado no gráfico"), abas,
            _faixa_da_meta(meta) if meta else "", series)))


def _minutos_por_extenso(minutos: int) -> str:
    return f"{minutos} min" if minutos < 60 else f"{minutos // 60} h {minutos % 60:02d} min"


def _lista(titulo, subtitulo, linhas, tom):
    corpo = (Raw(html=graficos.lista_ranqueada(linhas, tom)) if linhas
             else Raw(html=format_html('<p class="ind-vazio">{}</p>', _("Nada no período."))))
    return Cell(span=4, children=Card(title=titulo, subtitle=subtitulo, body=corpo))


def _listas(recorte, n, vendedor=None):
    grupos = ind.por_grupo(recorte, vendedor)
    motivos = ind.motivos(recorte, vendedor)
    pausas = ind.pausa_por_tipo(recorte, vendedor)
    sem_venda = sum(q for _m, q in motivos)
    return FormGrid(attrs={"data-ind": "listas"}, children=[
        _lista(_("Vendido por grupo de item"),
               ngettext("%(n)s venda", "%(n)s vendas", n.vendas) % {"n": n.vendas},
               [(g, v, em_reais(v)) for g, v in grupos], "venda"),
        _lista(_("Motivos de não venda"),
               ngettext("%(n)s atendimento sem venda", "%(n)s atendimentos sem venda",
                        sem_venda) % {"n": sem_venda},
               [(m, q, str(q)) for m, q in motivos], "perda"),
        _lista(_("Tempo em pausa"),
               _("%(total)s no total") % {"total": _minutos_por_extenso(
                   sum(m for _t, m in pausas))},
               [(t, m, _minutos_por_extenso(m)) for t, m in pausas], "pausa"),
    ])


#: O valor de "Todas as lojas" no campo Loja. Texto, e não vazio: vazio é o
#: que chega quando ninguém escolheu, e aí vale a loja do cabeçalho.
TODAS = "todas"


def _lojas_do_pedido(request, permitidas):
    """`(lojas do recorte, loja)`, com `loja` nula em "Todas as lojas".

    Sem `?loja=` válida, vale a loja do cabeçalho: é onde a pessoa disse que
    está, e é a que o seletor lá em cima mostra. Se o cargo não traz
    relatório nela, a primeira permitida. "Todas" só existe para quem alcança
    mais de uma: com uma loja só, "todas" é ela mesma.
    """
    from plataforma.contexto import filial_atual

    if len(permitidas) > 1 and request.GET.get("loja") == TODAS:
        return permitidas, None
    try:
        escolhida = int(request.GET.get("loja", ""))
    except ValueError:
        escolhida = None
    if escolhida is None or not any(l.pk == escolhida for l in permitidas):
        cabecalho = filial_atual(request)
        escolhida = cabecalho.pk if cabecalho is not None else None
    uma = [l for l in permitidas if l.pk == escolhida] or list(permitidas[:1])
    return uma, uma[0]


def _filtros(request, periodo, permitidas, loja):
    campos = [
        # Só atalhos desde 17/09/2026: De/Até saíram a pedido do cliente.
        # "Todas as lojas" é opção comum, e não `empty_label`: o do design
        # system nasce `disabled`, e quem escolhia uma loja não voltava a
        # "Todas" (revisão final, 15/09/2026; o mesmo motivo escrito em
        # `comum/listagem.py`).
        Select(name="periodo", label=_("Período"), span=3, value=periodo.chave,
               options=[Option(chave, rotulo) for chave, rotulo in ATALHOS]),
    ]
    if len(permitidas) > 1:
        campos.append(Select(
            name="loja", label=_("Loja"), span=3, value=str(loja.pk) if loja else TODAS,
            options=[*(Option(str(l.pk), str(l)) for l in permitidas),
                     Option(TODAS, _("Todas as lojas"))]))
    campos.append(Cell(span=2, children=Button(label=_("Aplicar"), variant="primary",
                                                type="submit")))
    # A ordenação e o filtro do ranking viajam junto: o `<form method="get">`
    # troca a querystring inteira, e aplicar o período apagava os dois.
    for chave, valor in request.GET.items():
        if chave not in ("periodo", "loja", "pagina", "ranking_mes") and valor:
            campos.append(Raw(html=format_html(
                '<input type="hidden" name="{}" value="{}">', chave, valor)))
    # Sem título: o período e a loja escolhidos já estão nos campos, e o
    # cabeçalho do painel logo abaixo diz os dois por extenso.
    return Card(attrs={"data-ind": "filtros"},
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
_FILTRAVEIS_POR_LOJA = {**_FILTRAVEIS, "loja": ColunaFiltravel("loja_nome", "Loja")}


def _colunas(pagina, com_meta=False, por_loja=False):
    colunas = [
        Column("nome", pagina.cabecalho("nome", str(_("Vendedor"))), strong=True,
               render=lambda p: p.nome or p.email),
        *([Column("loja", pagina.cabecalho("loja", str(_("Loja"))),
                  render=lambda p: str(p.loja))] if por_loja else []),
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
    if com_meta:
        colunas += [
            Column("meta", pagina.cabecalho("meta", str(_("Meta"))), align="num",
                   render=lambda p: _dinheiro(p.meta)),
            Column("pct_meta", pagina.cabecalho("pct_meta", str(_("% da meta"))),
                   align="num", render=lambda p: _pct(p.pct_meta)),
        ]
    return colunas


def _por_loja(recorte):
    """As lojas lado a lado, só em "Todas as lojas": é a separação que a soma
    esconde. Lista, e não `<table>`: são poucas linhas, sem filtro nem página
    que façam sentido, e a barra do vendido compara as lojas de relance."""
    linhas = ind.por_loja(recorte)
    maior = max((float(l.numeros.vendido) for l in linhas), default=0) or 1
    itens = format_html_join("", (
        '<li><span class="ind-loja-nome">{}</span>'
        '<span class="ind-loja-num"><small>{}</small><b>{}</b></span>'
        '<span class="ind-loja-num"><small>{}</small><b>{}</b></span>'
        '<span class="ind-loja-num"><small>{}</small><b>{}</b></span>'
        '<span class="ind-loja-num"><small>{}</small><b>{}</b></span>'
        '<span class="ind-rank-barra"><span style="width: {}%"></span></span></li>'), (
        (l.loja,
         _("Vendido"), em_reais(l.numeros.vendido),
         _("Atendimentos"), l.numeros.atendimentos,
         _("Conversão"), _pct(l.numeros.conversao),
         _("Ticket médio"), _dinheiro(l.numeros.ticket),
         f"{100 * float(l.numeros.vendido) / maior:.2f}")
        for l in linhas))
    return Card(title=_("Por loja"), attrs={"data-ind": "por-loja"},
                body=Raw(html=format_html('<ol class="ind-lojas">{}</ol>', itens)))


def mes_do_ranking(request):
    """O mês do ranking, de `?ranking_mes=2026-09`. Vazio, inválido ou
    futuro cai no mês atual: mês que não começou não tem posição."""
    atual = regras_de_meta.primeiro_do_mes(timezone.localdate())
    return min(regras_de_meta.mes_do_texto(request.GET.get("ranking_mes")), atual)


def _endereco_do_mes(request, mes) -> str:
    """A URL de agora com outro mês no ranking. O resto da URL (período,
    loja, filtro e ordem) viaja junto; a página volta para a primeira, porque
    a de outro mês pode nem existir."""
    consulta = request.GET.copy()
    consulta["ranking_mes"] = f"{mes:%Y-%m}"
    consulta.pop("pagina", None)
    return f"{request.path}?{consulta.urlencode()}"


def cartao_do_ranking(request, mes, *, subtitulo=None, attrs=None, body=None):
    """O cartão do ranking com o mês no título e as setas no cabeçalho.

    Desde 17/09/2026 o ranking tem o próprio mês, e não o período do painel:
    em "7 dias", ninguém sabia de quando era a posição. O título diz o mês por
    extenso, e a seta do mês seguinte some no mês atual.
    """
    from nucleo.views import _MESES

    atual = regras_de_meta.primeiro_do_mes(timezone.localdate())
    setas = [Button(label="", icon="chevron-left", variant="ghost", size="sm",
                    href=_endereco_do_mes(request, regras_de_meta.mes_anterior(mes)),
                    title=str(_("Mês anterior")),
                    attrs={"aria-label": _("Mês anterior")})]
    if mes < atual:
        setas.append(Button(label="", icon="chevron-right", variant="ghost", size="sm",
                            href=_endereco_do_mes(request, regras_de_meta.mes_seguinte(mes)),
                            title=str(_("Mês seguinte")),
                            attrs={"aria-label": _("Mês seguinte")}))
    titulo = _("Ranking de %(mes)s") % {"mes": f"{_MESES[mes.month - 1]} de {mes.year}"}
    return Card(title=titulo, subtitle=subtitulo, padded=False, attrs=attrs or {},
                header_actions=setas, body=body)


def blocos_dos_indicadores(request, empresa, permitidas) -> list:
    """Os blocos do dashboard (filtros, esquecidos, números, gráficos e
    ranking) para as lojas `permitidas`, que quem chama já tirou do alcance do
    cargo (`indicadores.lojas_com_relatorio`)."""
    periodo = periodo_do_pedido(request.GET)
    lojas, loja = _lojas_do_pedido(request, permitidas)
    recorte = ind.Recorte(empresa, tuple(lojas), periodo)
    anterior = ind.Recorte(empresa, tuple(lojas), periodo_anterior(periodo))
    n, a = ind.numeros(recorte), ind.numeros(anterior)
    mes_da_meta = regras_de_meta.mes_do_periodo(periodo)
    blocos = [
        _filtros(request, periodo, permitidas, loja),
        _esquecidos(ind.esquecidos(empresa, lojas)),
        _painel(periodo, loja, n, a, anterior, ind.por_dia(recorte),
                meta=regras_de_meta.meta_do_recorte(recorte)),
        _listas(recorte, n),
    ]
    todas = loja is None
    mes = mes_do_ranking(request)
    do_mes = ind.recorte_do_mes(empresa, tuple(lojas), mes)
    ordenaveis = ind.ORDENAVEIS_DO_RANKING_COM_META
    if todas:
        blocos.insert(3, _por_loja(recorte))
        # Uma linha por pessoa em cada loja: somada, a venda do Centro parecia
        # ser da Matriz.
        consulta = ind.ranking_por_loja(do_mes, mes)
        ordenaveis = {**ordenaveis, "loja": ("loja_nome", "nome")}
    else:
        consulta = ind.ranking(do_mes, mes)
    listagem = montar_pagina(request, consulta,
                             ordenaveis=ordenaveis,
                             padrao=ind.PADRAO_DO_RANKING,
                             filtraveis=_FILTRAVEIS_POR_LOJA if todas else _FILTRAVEIS,
                             preservar=("periodo", "loja", "ranking_mes"))
    blocos.append(cartao_do_ranking(request, mes, attrs={"data-ind": "ranking"}, body=[
        listagem.barra,
        Table(columns=_colunas(listagem, com_meta=True, por_loja=todas),
              rows=listagem.linhas),
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
