"""Os indicadores da fila no Início (spec 2026-09-15, entrega 2).

Desde 15/09/2026 o dashboard mora na raiz, abaixo do "Olá" (pedido do João):
é a primeira coisa que a gestão vê ao entrar. `/fila/indicadores` ficou só
como redirecionamento, para link antigo não quebrar.

As lojas que a pessoa enxerga saem de `fila.indicadores.lojas_com_relatorio`,
e a `?loja=` da URL só filtra DENTRO delas: uma loja forjada não amplia o
recorte, ela é descartada e o painel mostra todas as lojas permitidas.

**O painel abre em "Todas as lojas"** (18/09/2026, pedido do cliente: "aquela
área de filtros de datas e loja, tem que vir todas as lojas como default").
Entre 17/09/2026 e esta data ele abria na loja do cabeçalho — foi o próprio
cliente que desfez a decisão: quem trabalha na Matriz abria o Início e não via
o vendedor do Centro, e a rede só aparecia trocando o filtro à mão. Com uma
loja só não há escolha, e ela é o recorte.
"""

from __future__ import annotations

import math
from datetime import timedelta

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.pedido import inteiro_do_texto
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


def _empresas_do_pedido(request, pessoa):
    """`(empresas do recorte, empresa)`, com `empresa` nula em "Todas as
    empresas" (17/09/2026).

    A mesma regra da loja, um nível acima: sem `?empresa=` válida vale a do
    cabeçalho, e "todas" só existe para quem alcança mais de uma. Uma empresa
    forjada é descartada, e o recorte cai na do cabeçalho — ela nunca amplia
    o alcance.
    """
    from plataforma.contexto import empresa_atual

    alcancadas = ind.empresas_com_relatorio(pessoa)
    do_cabecalho = empresa_atual(request)
    if len(alcancadas) > 1 and request.GET.get("empresa") == TODAS:
        return alcancadas, None
    escolhida = inteiro_do_texto(request.GET.get("empresa", ""))
    uma = [e for e in alcancadas if e.pk == escolhida]
    if not uma:
        uma = [e for e in alcancadas if do_cabecalho and e.pk == do_cabecalho.pk]
    uma = uma or alcancadas[:1]
    return uma, (uma[0] if uma else None)


def _lojas_do_pedido(request, permitidas):
    """`(lojas do recorte, loja)`, com `loja` nula em "Todas as lojas".

    **O painel abre em "Todas as lojas"** (18/09/2026, pedido do cliente:
    "aquela área de filtros de datas e loja, tem que vir todas as lojas como
    default"). Entre 17/09/2026 e esta data ele abria na loja do cabeçalho, e
    foi o próprio cliente que desfez a decisão: quem trabalha na Matriz abria
    o Início e não via o vendedor do Centro — a rede só aparecia trocando o
    filtro à mão.

    Com UMA loja permitida não há escolha: ela é o recorte, e "todas" seria ela
    mesma. Uma `?loja=` que não é de nenhuma permitida é descartada, e o
    recorte cai nas permitidas — como antes, o pedido nunca amplia o alcance.
    """
    if len(permitidas) <= 1:
        return list(permitidas), (permitidas[0] if permitidas else None)
    escolhida = inteiro_do_texto(request.GET.get("loja", ""))
    uma = [loja for loja in permitidas if loja.pk == escolhida]
    if uma:
        return uma, uma[0]
    return list(permitidas), None


def _filtros(request, periodo, permitidas, loja, empresas=(), empresa=None):
    campos = [
        # Só atalhos desde 17/09/2026: De/Até saíram a pedido do cliente.
        # "Todas as lojas" é opção comum, e não `empty_label`: o do design
        # system nasce `disabled`, e quem escolhia uma loja não voltava a
        # "Todas" (revisão final, 15/09/2026; o mesmo motivo escrito em
        # `comum/listagem.py`).
        Select(name="periodo", label=_("Período"), span=3, value=periodo.chave,
               options=[Option(chave, rotulo) for chave, rotulo in ATALHOS]),
    ]
    # A empresa vem antes da loja: é ela que contém as lojas, e a ordem dos
    # campos é a da hierarquia (17/09/2026).
    if len(empresas) > 1:
        campos.append(Select(
            name="empresa", label=_("Empresa"), span=3,
            value=str(empresa.pk) if empresa else TODAS,
            options=[*(Option(str(e.pk), str(e)) for e in empresas),
                     Option(TODAS, _("Todas as empresas"))]))
    if len(permitidas) > 1:
        campos.append(Select(
            name="loja", label=_("Loja"), span=3, value=str(loja.pk) if loja else TODAS,
            options=[*(Option(str(l.pk), str(l)) for l in permitidas),
                     Option(TODAS, _("Todas as lojas"))]))
    campos.append(Cell(span=2, children=Button(label=_("Aplicar"), variant="primary",
                                                type="submit")))
    # O filtro do ranking e o MÊS dele viajam junto: o `<form method="get">`
    # troca a querystring inteira, e aplicar o período apagava os dois.
    # `ranking_mes` NÃO é campo desta barra (o seletor do mês mora no cartão do
    # ranking), e por isso ele viaja como campo oculto: sem isto, trocar o
    # período devolvia o ranking para o mês atual sem ninguém pedir
    # (18/09/2026, quando o mês passou a ser escolhido numa lista).
    for chave, valor in request.GET.items():
        if chave not in ("periodo", "empresa", "loja", "pagina") and valor:
            campos.append(Raw(html=format_html(
                '<input type="hidden" name="{}" value="{}">', chave, valor)))
    # Sem título: o período e a loja escolhidos já estão nos campos, e o
    # cabeçalho do painel logo abaixo diz os dois por extenso.
    return Card(attrs={"data-ind": "filtros"},
                body=Form(method="get", action=reverse("inicio"),
                          children=FormGrid(children=campos)))


def _desde(instante) -> str:
    """A hora no fuso da loja: o banco devolve em UTC, e 21:30 de São Paulo
    aparecia como 00:30 do dia seguinte (revisão final, 15/09/2026).

    "Ontem, 14:01" quando foi ontem: é o caso da imensa maioria dos
    esquecidos, e uma data escrita obriga quem lê a calcular quantos dias
    faz. Mais antigo que isso, a data — aí o número é a informação.
    """
    from django.utils import timezone

    local = timezone.localtime(instante)
    ontem = timezone.localdate() - timedelta(days=1)
    if local.date() == ontem:
        return _("ontem, %(hora)s") % {"hora": local.strftime("%H:%M")}
    return local.strftime("%d/%m, %H:%M")


#: O que ficou aberto, em uma palavra. A frase inteira ("Presença aberta")
#: era repetida linha a linha embaixo de um título que já diz "ficou aberto".
_ETIQUETAS = {
    "presenca": gettext_lazy("Presença"),
    "atendimento": gettext_lazy("Atendimento"),
    "pausa": gettext_lazy("Pausa"),
}


def _por_loja_e_pessoa(lista):
    """As pendências agrupadas: uma linha por PESSOA, dentro da loja dela.

    Bia com a presença e o atendimento abertos eram duas linhas iguais, com o
    mesmo nome, a mesma loja e o mesmo link — e o link se repetia em todas,
    cinco vezes na mesma loja. Agrupado, a loja aparece uma vez, com um link
    só, e a pessoa uma vez, com o que ficou aberto ao lado.
    """
    lojas: dict = {}
    for esquecido in lista:
        pessoas = lojas.setdefault(esquecido.loja, {})
        tipos, desde = pessoas.get(esquecido.nome, ([], esquecido.desde))
        tipos.append(esquecido.tipo)
        # O mais antigo manda: é ele que diz há quanto tempo aquilo está lá.
        pessoas[esquecido.nome] = (tipos, min(desde, esquecido.desde))
    return lojas


def _linha_do_esquecido(nome, tipos, desde) -> str:
    etiquetas = ", ".join(str(_ETIQUETAS.get(t, t)) for t in tipos)
    return format_html(
        '<li><b>{}</b><span>{}</span><time>{}</time></li>',
        nome, etiquetas, _desde(desde))


def _esquecidos(lista):
    if not lista:
        return ""
    lojas = _por_loja_e_pessoa(lista)
    pendencias = sum(len(pessoas) for pessoas in lojas.values())
    # O link troca para a loja DO ITEM e volta para a fila: apontar para
    # `/fila` abria a loja da sessão, onde a pessoa esquecida não está
    # (revisão final, 15/09/2026). Um por LOJA, e não por linha.
    blocos = format_html_join("", '<li><div class="ind-esq-loja"><strong>{}</strong>'
                              '<a class="btn sm" href="{}">{}</a></div>'
                              '<ul class="ind-esq-linhas">{}</ul></li>', (
        (str(loja), trocar_e_abrir_a_fila(loja), _("Abrir a fila desta loja"),
         format_html_join("", "{}", (
             (_linha_do_esquecido(nome, tipos, desde),)
             for nome, (tipos, desde) in sorted(
                 pessoas.items(), key=lambda p: p[1][1]))))
        for loja in sorted(lojas, key=str) for pessoas in [lojas[loja]]))
    resumo = ngettext("%(quantas)d pessoa com pendência",
                      "%(quantas)d pessoas com pendência",
                      pendencias) % {"quantas": pendencias}
    lojas_texto = ngettext("em %(quantas)d loja", "em %(quantas)d lojas",
                           len(lojas)) % {"quantas": len(lojas)}
    return Alert(tone="warn", title=_("Ficou aberto de um dia para o outro"),
                 attrs={"data-esquecidos": ""},
                 message=Raw(html=format_html(
                     '<p class="ind-esq-resumo">{} {}. {}</p>'
                     '<ul class="ind-esq">{}</ul>',
                     resumo, lojas_texto,
                     _("Encerre pela fila de cada loja."), blocos)))


_FILTRAVEIS = {"nome": ColunaFiltravel("nome", "Vendedor")}
_FILTRAVEIS_POR_LOJA = {**_FILTRAVEIS, "loja": ColunaFiltravel("loja_nome", "Loja")}


def _primeiro_do_ranking(consulta):
    """A linha do primeiro lugar do ranking, pelo VENDIDO.

    Pelo vendido, e não pela linha de cima da tabela (23/09/2026, pedido do
    cliente: "colocar uma faixa amarela para destacar o vendedor que está em
    primeiro"): a ordem da tabela é a que a pessoa escolheu, e ordenar por nome
    ou por conversão não elege outro primeiro. É a mesma regra de
    `indicadores.posicoes_por_vendido`, que já vale no painel do vendedor.

    `[:1]`, e não `.first()`: em "Todas as lojas" a consulta vem embrulhada por
    `_ConsultaPorLoja`, e o `.first()` delegado devolveria o dicionário cru —
    sem a loja que a linha carrega.
    """
    ordenada = consulta.order_by("-vendido")
    return (ordenada[:1] or [None])[0]


def _attrs_da_linha(linha, primeiro=None, pessoa=None, por_loja=False) -> dict:
    """Os atributos da linha do ranking.

    Quem está em primeiro ganha a faixa (`.ind-primeiro`), e no painel do
    vendedor a própria linha se marca como "eu" (`.ind-eu`, com
    `aria-current`). Os dois juntos, e não um `row_attrs` em cada tela: a mesma
    linha pode ser as duas coisas — o vendedor que lidera a loja —, e duas
    listas de classe separadas se sobrescreveriam.
    """
    classes = []
    if primeiro is not None and linha.pk == primeiro.pk and (
            not por_loja or linha.loja_id == primeiro.loja_id):
        classes.append("ind-primeiro")
    sou_eu = pessoa is not None and linha.pk == pessoa.pk
    if sou_eu:
        classes.append("ind-eu")
    attrs = {"class": " ".join(classes)} if classes else {}
    if sou_eu:
        attrs["aria-current"] = "true"
    return attrs


def _colunas(pagina, com_meta=False, por_loja=False, varias_empresas=False):
    """As colunas do ranking. `pagina.cabecalho` transforma o rótulo em link
    de ordenar — ver `comum.listagem` e R46."""
    colunas = [
        Column("nome", pagina.cabecalho("nome", str(_("Vendedor"))), strong=True,
               render=lambda p: p.nome or p.email),
        *([Column("loja", pagina.cabecalho("loja", str(_("Loja"))),
                  render=lambda p: _nome_da_loja(p.loja, varias_empresas))]
          if por_loja else []),
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


def _lado_a_lado(titulo, marca, linhas):
    """Uma lista comparando os pedaços do recorte (lojas ou empresas), com a
    barra do vendido medindo cada um contra o maior. Lista, e não `<table>`:
    são poucas linhas, sem filtro nem página que façam sentido, e a barra
    compara de relance."""
    maior = max((float(n.vendido) for _nome, n in linhas), default=0) or 1
    itens = format_html_join("", (
        '<li><span class="ind-loja-nome">{}</span>'
        '<span class="ind-loja-num"><small>{}</small><b>{}</b></span>'
        '<span class="ind-loja-num"><small>{}</small><b>{}</b></span>'
        '<span class="ind-loja-num"><small>{}</small><b>{}</b></span>'
        '<span class="ind-loja-num"><small>{}</small><b>{}</b></span>'
        '<span class="ind-rank-barra"><span style="width: {}%"></span></span></li>'), (
        (nome,
         _("Vendido"), em_reais(n.vendido),
         _("Atendimentos"), n.atendimentos,
         _("Conversão"), _pct(n.conversao),
         _("Ticket médio"), _dinheiro(n.ticket),
         f"{100 * float(n.vendido) / maior:.2f}")
        for nome, n in linhas))
    return Card(title=titulo, attrs={"data-ind": marca},
                body=Raw(html=format_html('<ol class="ind-lojas">{}</ol>', itens)))


def _por_empresa(recorte):
    return _lado_a_lado(_("Por empresa"), "por-empresa",
                        [(str(l.empresa), l.numeros) for l in ind.por_empresa(recorte)])


def _nome_da_loja(loja, varias_empresas: bool) -> str:
    """"Matriz" ou "Matriz · Beta Ltda".

    Cada empresa nasce com a SUA Matriz: com várias empresas no recorte, duas
    linhas "Matriz" não diriam de qual delas são (17/09/2026).
    """
    return f"{loja} · {loja.empresa}" if varias_empresas else str(loja)


def _por_loja(recorte):
    """As lojas lado a lado, só em "Todas as lojas": é a separação que a soma
    esconde. Lista, e não `<table>`: são poucas linhas, sem filtro nem página
    que façam sentido, e a barra do vendido compara as lojas de relance."""
    varias = len(recorte.todas) > 1
    return _lado_a_lado(_("Por loja"), "por-loja",
                        [(_nome_da_loja(l.loja, varias), l.numeros)
                         for l in ind.por_loja(recorte)])


def mes_do_ranking(request):
    """O mês do ranking, de `?ranking_mes=2026-09`. Vazio, inválido ou
    futuro cai no mês atual: mês que não começou não tem posição."""
    atual = regras_de_meta.primeiro_do_mes(timezone.localdate())
    return min(regras_de_meta.mes_do_texto(request.GET.get("ranking_mes")), atual)


def meses_do_ranking(recorte, escolhido, agora: "datetime | None" = None) -> list:
    """Os meses que o seletor do ranking oferece, do mais novo para o mais
    antigo.

    Do mês atual até o primeiro mês com atendimento no recorte: a lista é o que
    existe NAQUELAS lojas, e não um intervalo de anos inventado. O mês pedido
    pela URL entra mesmo sem atendimento nenhum — link salvo abre com o mês
    dele marcado —, e mês FUTURO não entra: mês que não começou não tem
    posição.

    Só o alcance do `recorte` importa (`do_recorte`); o período dele não é
    lido. Custa uma consulta `MIN` por página, e é ela que evita um seletor de
    trezentos meses numa loja que abriu ontem.
    """
    from django.db.models import Min

    from .models import Atendimento

    agora = agora or timezone.now()
    atual = regras_de_meta.primeiro_do_mes(timezone.localdate(agora))
    primeiro = ind.do_recorte(Atendimento, recorte).aggregate(m=Min("inicio"))["m"]
    inicio = atual if primeiro is None else min(
        atual, timezone.localtime(primeiro).date().replace(day=1))
    inicio = min(inicio, escolhido)
    meses, mes = [], atual
    while mes >= inicio:
        meses.append(mes)
        mes = regras_de_meta.mes_anterior(mes)
    return meses


def _seletor_do_mes(request, mes, meses):
    """O mês do ranking num `<select>`, no lugar das setas (18/09/2026).

    Um `<select>` de verdade dentro de um `<form method="get">`: sem JavaScript
    a pessoa escolhe e aperta "Abrir"; com ele, o `mw5.js` envia no `change`
    (`data-auto-enviar`, o mesmo do seletor de loja do cabeçalho). Os outros
    filtros viajam em campos ocultos, menos `pagina` — a página de outro mês
    pode nem existir.
    """
    from nucleo.views import _MESES

    ocultos = [Raw(html=format_html('<input type="hidden" name="{}" value="{}">',
                                    chave, valor))
               for chave, valor in request.GET.items()
               if chave not in ("ranking_mes", "pagina") and valor]
    return Form(method="get", action=request.path,
                attrs={"data-ind": "mes-do-ranking"}, children=[
                    *ocultos,
                    Select(name="ranking_mes", value=f"{mes:%Y-%m}",
                           attrs={"data-auto-enviar": "",
                                  "aria-label": str(_("Mês do ranking"))},
                           options=[Option(
                               f"{m:%Y-%m}",
                               f"{_MESES[m.month - 1].capitalize()} de {m.year}")
                               for m in meses]),
                    Button(label=_("Abrir"), type="submit", size="sm"),
                ])


def cartao_do_ranking(request, mes, *, subtitulo=None, attrs=None, body=None,
                      meses=()):
    """O cartão do ranking com o mês no título e o seletor no cabeçalho.

    Desde 17/09/2026 o ranking tem o próprio mês, e não o período do painel:
    em "7 dias", ninguém sabia de quando era a posição. Desde 18/09/2026 o mês
    se escolhe numa LISTA, e não em setas: quem abria um mês distante clicava
    uma vez por mês, e o mês futuro aparecia como uma seta que sumia em vez de
    uma opção que não existe (`meses_do_ranking`).
    """
    from nucleo.views import _MESES

    titulo = _("Ranking de %(mes)s") % {"mes": f"{_MESES[mes.month - 1]} de {mes.year}"}
    return Card(title=titulo, subtitle=subtitulo, padded=False, attrs=attrs or {},
                header_actions=_seletor_do_mes(request, mes, meses), body=body)


def blocos_dos_indicadores(request, empresa, permitidas) -> list:
    """Os blocos do dashboard (filtros, esquecidos, números, gráficos e
    ranking).

    `permitidas` são as lojas da empresa do cabeçalho, que quem chama já tirou
    do alcance do cargo. Em "Todas as empresas" (17/09/2026) as lojas passam a
    ser as das empresas alcançadas, pela mesma regra, uma empresa por vez.
    """
    from contas.identidade import usuario_de

    periodo = periodo_do_pedido(request.GET)
    pessoa = usuario_de(request.usuario)
    empresas, escolhida = _empresas_do_pedido(request, pessoa)
    if escolhida is None:
        # "Todas as empresas": as lojas de cada uma, pela mesma pergunta de
        # sempre (`lojas_com_relatorio`), e o campo Loja fica com todas.
        permitidas = [loja for e in empresas
                      for loja in ind.lojas_com_relatorio(pessoa, e)]
    elif escolhida.pk != empresa.pk:
        empresa = escolhida
        permitidas = ind.lojas_com_relatorio(pessoa, escolhida)
    lojas, loja = _lojas_do_pedido(request, permitidas)
    recorte = ind.Recorte(empresa, tuple(lojas), periodo, tuple(empresas))
    anterior = ind.Recorte(empresa, tuple(lojas), periodo_anterior(periodo),
                           tuple(empresas))
    n, a = ind.numeros(recorte), ind.numeros(anterior)
    mes_da_meta = regras_de_meta.mes_do_periodo(periodo)
    # O aviso de quem ficou aberto vem ANTES dos filtros (18/09/2026, pedido do
    # cliente). Entre o filtro e os resultados ele ficava no meio do caminho de
    # quem só queria trocar o período, e parecia mais um bloco do painel de
    # números; em cima, é a primeira coisa que a gestão lê ao abrir o Início —
    # e é uma pendência, não um filtro.
    blocos = [
        _esquecidos(ind.esquecidos(empresa, lojas)),
        _filtros(request, periodo, permitidas, loja,
                 empresas=ind.empresas_com_relatorio(pessoa), empresa=escolhida),
        _painel(periodo, loja, n, a, anterior, ind.por_dia(recorte),
                meta=regras_de_meta.meta_do_recorte(recorte)),
        _listas(recorte, n),
    ]
    todas = loja is None
    mes = mes_do_ranking(request)
    do_mes = ind.recorte_do_mes(empresa, tuple(lojas), mes, tuple(empresas))
    ordenaveis = ind.ORDENAVEIS_DO_RANKING_COM_META
    if escolhida is None:
        blocos.insert(3, _por_empresa(recorte))
    if todas:
        blocos.insert(3, _por_loja(recorte))
        # Uma linha por pessoa em cada loja: somada, a venda do Centro parecia
        # ser da Matriz.
        consulta = ind.ranking_por_loja(do_mes, mes)
        ordenaveis = {**ordenaveis, "loja": ("loja_nome", "nome")}
    else:
        consulta = ind.ranking(do_mes, mes)
    # Quem está em primeiro, calculado ANTES da listagem: `montar_pagina`
    # ordena, filtra e fatia, e o primeiro lugar não pode depender disso.
    primeiro = _primeiro_do_ranking(consulta)
    listagem = montar_pagina(request, consulta,
                             ordenaveis=ordenaveis,
                             padrao=ind.PADRAO_DO_RANKING,
                             filtraveis=_FILTRAVEIS_POR_LOJA if todas else _FILTRAVEIS,
                             preservar=("periodo", "empresa", "loja",
                                        "ranking_mes"))
    blocos.append(cartao_do_ranking(request, mes, meses=meses_do_ranking(recorte, mes),
                                    attrs={"data-ind": "ranking"}, body=[
        listagem.barra,
        Table(columns=_colunas(listagem, com_meta=True, por_loja=todas,
                               varias_empresas=len(empresas) > 1),
              rows=listagem.linhas,
              row_attrs=lambda linha: _attrs_da_linha(
                  linha, primeiro=primeiro, por_loja=todas)),
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
