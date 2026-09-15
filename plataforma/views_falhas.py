"""A tela `/mw5/falhas`: o que estourou nesta instalação, para a MW5 ler.

A metade "quem vê" do item 35. Leitura pura como a Auditoria — registro de
passado não se edita —, com o trio de R46 (filtro por caminho/autor/método,
ordenação, paginação). O traceback completo fica no `docker logs`; aqui
aparece o resumo, que é o que decide "é urgente?" sem abrir nada.
"""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseNotAllowed
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from nucleo.components import Card, Column, PageHeader, Table
from nucleo.layout import Crumb
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render
from comum.listagem import ColunaFiltravel, montar_pagina

from comum.guardas_de_acesso import exigir_permissao

from comum.exportacao import ColunaDeExportacao, botoes, preparar_exportacao
from .models import Falha

__all__ = ["falhas"]

_ORDENAVEIS = {
    "quando": "quando",
    "caminho": "caminho",
    "autor": ("autor_login", "autor_nome"),
}

_FILTRAVEIS = {
    "caminho": ColunaFiltravel("caminho", "Caminho"),
    "autor": ColunaFiltravel(("autor_login", "autor_nome"), "Autor"),
    "metodo": ColunaFiltravel("metodo", "Método"),
    "quando": ColunaFiltravel("quando", "Data", tipo="data"),
}

COLUNAS_DE_EXPORTACAO = (
    ColunaDeExportacao("quando", "Quando",
                       lambda f: localtime(f.quando).strftime("%d/%m/%Y %H:%M:%S")),
    ColunaDeExportacao("caminho", "Caminho", lambda f: f.caminho),
    ColunaDeExportacao("metodo", "Método", lambda f: f.metodo),
    ColunaDeExportacao("autor", "Autor", lambda f: f.autor_login),
    ColunaDeExportacao("resumo", "Erro", lambda f: f.resumo),
)


def _colunas_da_lista(pagina) -> list[Column]:
    def _autor(falha):
        if not falha.autor_login:
            return "—"
        if falha.autor_nome and falha.autor_nome != falha.autor_login:
            return f"{falha.autor_nome} ({falha.autor_login})"
        return falha.autor_login

    return [
        Column("quando", pagina.cabecalho("quando", "Quando"),
               render=lambda f: localtime(f.quando).strftime("%d/%m/%Y %H:%M:%S")),
        Column("caminho", pagina.cabecalho("caminho", "Caminho"),
               render=lambda f: f"{f.metodo} {f.caminho}"),
        Column("autor", pagina.cabecalho("autor", "Autor"), render=_autor),
        Column("resumo", _("Erro"), render=lambda f: f.resumo),
    ]


def _desenhar(request) -> HttpResponse:
    from .site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        conteudo = [
            PageHeader(title=_("Falhas"),
                       subtitle="Os erros que estouraram nesta instalação, "
                                "mais recentes primeiro. O traceback inteiro "
                                "está no log do container."),
        ]
        listagem = montar_pagina(
            request, Falha.objects.all(),
            ordenaveis=_ORDENAVEIS, padrao="-quando", filtraveis=_FILTRAVEIS)
        conteudo.append(Card(
            title=_("Registros"), padded=False,
            body=[
                listagem.barra,
                Table(columns=_colunas_da_lista(listagem), rows=listagem.linhas),
                listagem.paginacao,
            ],
        ))
        pagina = site.page(
            title=_("Falhas"),
            width="full",
            stylesheets=["/static/plataforma/listagem.css"],
            content=conteudo,
            crumbs=[Crumb(_("Falhas"))],
            user=getattr(request, "usuario", None),
        )
        return render(pagina)


# Mesma fronteira de Aparência/Módulos: `mw5.falhas` nunca é concedível
# (não é módulo), só o superusuário passa — quem vê o erro da instalação
# inteira é quem opera a plataforma.
@exigir_permissao("mw5.falhas")
def falhas(request) -> HttpResponse:
    """Leitura pura, com a exportação do Bloco 4 de graça."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    exportacao = preparar_exportacao(
        request, queryset=Falha.objects.all(),
        colunas=COLUNAS_DE_EXPORTACAO,
        ordenaveis=_ORDENAVEIS, padrao="-quando", filtraveis=_FILTRAVEIS,
        titulo=_("Falhas"))
    if exportacao is not None:
        return exportacao
    return _desenhar(request)
