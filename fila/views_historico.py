"""O histórico das correções do gerente (spec 2026-09-17, C5).

Mesma regra de loja do painel do Início: as lojas saem do cargo
(`fila.gerenciar` em cada uma), e a tela abre em "Todas as lojas" para quem
alcança mais de uma (18/09/2026, o mesmo pedido do cliente no painel: o filtro
de loja vem com todas). Uma `?loja=` forjada não amplia o recorte.

O período abre em "Hoje", e não no padrão do painel ("Este mês"): o histórico
é o que o gerente confere no fim do dia, e um mês inteiro afogaria o de hoje.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.components import (Button, Card, Cell, Column, Form, FormGrid,
                               Option, PageHeader, Select, Table)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from .estado import nome_de
from .indicadores import lojas_com_permissao
from .models import AcaoDeCorrecao, CorrecaoNaFila
from .periodo import ATALHOS, periodo_do_pedido
from .views_indicadores import TODAS, _lojas_do_pedido

__all__ = ["historico"]

ORDENAVEIS = {
    "momento": ("momento", "pk"),
    "loja": ("filial__apelido", "momento"),
    "vendedor": ("pessoa__nome", "momento"),
    "acao": ("acao", "momento"),
    "autor": ("autor__nome", "momento"),
}
FILTRAVEIS = {
    "vendedor": ColunaFiltravel(("pessoa__nome", "pessoa__email"), "Vendedor"),
    "acao": ColunaFiltravel("acao", "Ação", tipo="opcoes",
                            opcoes=lambda: [(str(v), str(r))
                                            for v, r in AcaoDeCorrecao.choices]),
    "observacao": ColunaFiltravel("observacao", "Motivo"),
}


def _filtros(request, periodo, permitidas, loja):
    campos = [Select(name="periodo", label=_("Período"), span=3, value=periodo.chave,
                     options=[Option(c, r) for c, r in ATALHOS])]
    if len(permitidas) > 1:
        campos.append(Select(
            name="loja", label=_("Loja"), span=3, value=str(loja.pk) if loja else TODAS,
            options=[*(Option(str(l.pk), str(l)) for l in permitidas),
                     Option(TODAS, _("Todas as lojas"))]))
    campos.append(Cell(span=2, children=Button(label=_("Aplicar"), variant="primary",
                                               type="submit")))
    return Card(attrs={"data-historico": "filtros"},
                body=Form(method="get", action=reverse("fila_historico"),
                          children=FormGrid(children=campos)))


def _colunas(listagem):
    return [
        Column("momento", listagem.cabecalho("momento", str(_("Quando"))),
               render=lambda c: timezone.localtime(c.momento).strftime("%d/%m %H:%M")),
        Column("loja", listagem.cabecalho("loja", str(_("Loja"))),
               render=lambda c: str(c.filial)),
        Column("vendedor", listagem.cabecalho("vendedor", str(_("Vendedor"))),
               strong=True, render=lambda c: nome_de(c.pessoa)),
        Column("acao", listagem.cabecalho("acao", str(_("Ação"))),
               render=lambda c: format_html("{}<br><small>{}</small>",
                                            c.get_acao_display(), c.detalhe)),
        # Sem cabeçalho ordenável: ordenar por texto de motivo não é pergunta
        # que alguém faça; filtrar por ele é, e a barra faz isso.
        Column("observacao", str(_("Motivo")), render=lambda c: c.observacao),
        Column("autor", listagem.cabecalho("autor", str(_("Quem corrigiu"))),
               render=lambda c: nome_de(c.autor)),
    ]


@exigir_permissao("fila.gerenciar")
@exigir_modulo_ligado("fila")
def historico(request) -> HttpResponse:
    from plataforma.site import montar_site

    empresa = empresa_atual(request)
    permitidas = lojas_com_permissao(usuario_de(request.usuario), empresa,
                                     "fila.gerenciar")
    pedido = request.GET.copy()
    pedido.setdefault("periodo", "hoje")
    periodo = periodo_do_pedido(pedido)
    lojas, loja = _lojas_do_pedido(request, permitidas) if permitidas else ([], None)
    consulta = (CorrecaoNaFila.objects.da_empresa(empresa)
                .filter(filial__in=lojas, momento__gte=periodo.de,
                        momento__lt=periodo.ate)
                .select_related("filial", "pessoa", "autor")
                .defer("pessoa__avatar", "autor__avatar"))
    listagem = montar_pagina(request, consulta, ordenaveis=ORDENAVEIS,
                             padrao="-momento", filtraveis=FILTRAVEIS,
                             preservar=("periodo", "loja"))
    with use_environment(ambiente()):
        site = montar_site(request)
        pagina = site.page(
            title=_("Histórico da fila"), width="full",
            stylesheets=["/static/plataforma/listagem.css"],
            content=[
                aviso_de_personificacao(request),
                PageHeader(title=_("Histórico da fila"),
                           subtitle=_("As correções do gerente, com o motivo de "
                                      "cada uma.")),
                _filtros(request, periodo, permitidas, loja),
                Card(title=f"{periodo.rotulo}, {loja or _('todas as lojas')}",
                     padded=False, body=[listagem.barra,
                                         Table(columns=_colunas(listagem),
                                               rows=listagem.linhas),
                                         listagem.paginacao]),
            ],
            crumbs=[Crumb(_("Histórico da fila"))], user=request.usuario)
        return render(pagina)
