"""Grupos de item, motivos de não venda e tipos de pausa.

Uma tela para os três, e não três cópias: são a mesma tabela (nome, ordem,
ativo) com outro model, e três cópias divergiriam no primeiro ajuste. O que
muda de uma para outra mora em `Cadastro` (o dataclass abaixo).

Padrão da casa (R46): filtro, ordenação e paginação; criar e editar em modal;
uma rota com `acao` no POST. **Cadastro usado não se remove** (a FK dos
lançamentos é `PROTECT`), e a tela diz "em uso, desative" em vez de estourar.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.pedido import id_do_post
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import (
    Alert, Box, Button, Card, Checkbox, Column, Form, FormGrid, IconButton,
    Modal, PageHeader, Raw, Table, TextInput,
)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from .models import GrupoDeItem, MotivoDeNaoVenda, TipoDePausa

__all__ = ["grupos", "motivos", "pausas"]


@dataclass(frozen=True)
class Cadastro:
    model: type
    rota: str
    titulo: str
    rotulo: str
    subtitulo: str
    novo: str


GRUPOS = Cadastro(GrupoDeItem, "fila_grupos", _("Grupos de item"),
                  "Grupo de item",
                  _("O que se vende: o vendedor escolhe o grupo ao lançar a venda."),
                  _("Novo grupo"))
MOTIVOS = Cadastro(MotivoDeNaoVenda, "fila_motivos", _("Motivos de não venda"),
                   "Motivo de não venda",
                   _("Por que o cliente não comprou: um motivo por atendimento."),
                   _("Novo motivo"))
PAUSAS = Cadastro(TipoDePausa, "fila_pausas", _("Tipos de pausa"),
                  "Tipo de pausa",
                  _("Por que o vendedor saiu da fila por um tempo."),
                  _("Novo tipo"))

NAO_ENCONTRADO = _("Cadastro não encontrado.")
EM_USO = _("Em uso: desative em vez de remover.")

_ORDENAVEIS = {"nome": "nome", "ordem": ("ordem", "nome"),
               "ativo": ("-ativo", "nome")}
_FILTRAVEIS = {
    "nome": ColunaFiltravel("nome", "Nome"),
    "ativo": ColunaFiltravel("ativo", "Situação", tipo="opcoes",
                             opcoes=lambda: [("True", "Ativo"),
                                             ("False", "Inativo")]),
}


def _linhas(request, cadastro):
    return cadastro.model.objects.do_contexto(request)


def _oculto(nome: str, valor: str) -> Raw:
    """`valor` é sempre um `pk` ou uma constante desta view."""
    return Raw(html=format_html('<input type="hidden" name="{}" value="{}">',
                                nome, valor))


def _campos(nome="", ordem=0, ativo=True, com_ativo=False):
    campos = [
        TextInput(name="nome", label=_("Nome"), span=8, value=nome,
                  required=True, maxlength=80),
        TextInput(name="ordem", label=_("Ordem"), span=4, type="number",
                  value=str(ordem)),
    ]
    if com_ativo:
        campos.append(Checkbox(
            name="ativo", value="1", label=_("Ativo"), checked=ativo,
            help=_("Desativado some das opções do vendedor e continua nos "
                   "lançamentos antigos.")))
    return FormGrid(children=campos)


def _modais(request, cadastro, linhas) -> list:
    acao = reverse(cadastro.rota)
    modais = [Modal(id="cadastro-criar", title=cadastro.novo, body=Form(
        action=acao, children=[
            Raw(html=campo_csrf(request)), _oculto("acao", "criar"),
            _campos(), Button(label=_("Criar"), variant="primary",
                              type="submit")]))]
    for linha in linhas:
        modais.append(Modal(
            id=f"cadastro-{linha.pk}-editar", title=f"Editar {linha.nome}",
            body=Form(action=acao, children=[
                Raw(html=campo_csrf(request)), _oculto("acao", "salvar"),
                _oculto("id", str(linha.pk)),
                _campos(linha.nome, linha.ordem, linha.ativo, com_ativo=True),
                Button(label=_("Salvar"), variant="primary", type="submit")])))
        modais.append(Modal(
            id=f"cadastro-{linha.pk}-remover", title=_("Remover"),
            body=Form(action=acao, children=[
                Raw(html=campo_csrf(request)), _oculto("acao", "remover"),
                _oculto("id", str(linha.pk)),
                Alert(tone="danger", message=(
                    f'Remover "{linha.nome}"? Só é possível se nunca foi '
                    f'usado em um lançamento.')),
                Button(label=_("Remover"), variant="danger", type="submit")])))
    return modais


def _acoes_da_linha(linha) -> Box:
    return Box(direction="row", gap="sm", wrap=False, align="end",
               cross="center", body=[
                   IconButton(icon="edit", title=_("Editar"), attrs={
                       "data-open-modal": f"cadastro-{linha.pk}-editar"}),
                   IconButton(icon="trash", title=_("Remover"), attrs={
                       "data-open-modal": f"cadastro-{linha.pk}-remover"}),
               ])


def _desenhar(request, cadastro, erro=None) -> HttpResponse:
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        listagem = montar_pagina(request, _linhas(request, cadastro),
                                 ordenaveis=_ORDENAVEIS, padrao="ordem",
                                 filtraveis=_FILTRAVEIS)
        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=cadastro.titulo, subtitle=cadastro.subtitulo,
                       actions=[Button(label=cadastro.novo, variant="primary",
                                       attrs={"data-open-modal": "cadastro-criar"})]),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))
        conteudo.append(Card(title=cadastro.titulo, padded=False, body=[
            listagem.barra,
            Table(columns=[
                Column("nome", listagem.cabecalho("nome", "Nome"), strong=True),
                Column("ordem", listagem.cabecalho("ordem", "Ordem"),
                       align="center"),
                Column("ativo", listagem.cabecalho("ativo", "Situação"),
                       render=lambda l: "Ativo" if l.ativo else "Inativo"),
            ], rows=listagem.linhas, row_actions=_acoes_da_linha),
            listagem.paginacao,
        ]))
        pagina = site.page(
            title=cadastro.titulo, width="full",
            stylesheets=["/static/plataforma/listagem.css"],
            content=conteudo, crumbs=[Crumb(cadastro.titulo)],
            user=getattr(request, "usuario", None),
            overlays=_modais(request, cadastro, listagem.linhas))
        return render(pagina)


def _ler(request):
    nome = (request.POST.get("nome") or "").strip()[:80]
    try:
        ordem = max(0, int(request.POST.get("ordem") or 0))
    except ValueError:
        ordem = 0
    return nome, ordem, request.POST.get("ativo") == "1"


def _alvo(cadastro, linha) -> str:
    return f"{cadastro.rotulo}: {linha.nome}"


def _tela(request, cadastro) -> HttpResponse:
    if request.method != "POST":
        return _desenhar(request, cadastro)
    acao = request.POST.get("acao", "")
    empresa = empresa_atual(request)
    if empresa is None:
        return _desenhar(request, cadastro, erro=_(
            "Escolha uma empresa no cabeçalho antes de cadastrar."))

    if acao == "criar":
        nome, ordem, _ativo = _ler(request)
        if not nome:
            return _desenhar(request, cadastro, erro=_("Informe o nome."))
        try:
            with transaction.atomic():
                linha = cadastro.model.irrestritos.create(
                    empresa=empresa, nome=nome, ordem=ordem)
                registrar(ACOES.FILA_CADASTRO_CRIADO, request.usuario,
                          alvo=_alvo(cadastro, linha), request=request)
        except IntegrityError:
            return _desenhar(request, cadastro,
                             erro=f'Já existe "{nome}" nesta lista.')
        return HttpResponseRedirect(reverse(cadastro.rota))

    linha = _linhas(request, cadastro).filter(
        pk=id_do_post(request, "id")).first()
    if linha is None:
        return _desenhar(request, cadastro, erro=NAO_ENCONTRADO)

    if acao == "salvar":
        nome, ordem, ativo = _ler(request)
        if not nome:
            return _desenhar(request, cadastro, erro=_("Informe o nome."))
        antes = _alvo(cadastro, linha)
        try:
            with transaction.atomic():
                linha.nome, linha.ordem, linha.ativo = nome, ordem, ativo
                linha.save(update_fields=["nome", "ordem", "ativo"])
                registrar(ACOES.FILA_CADASTRO_EDITADO, request.usuario,
                          alvo=_alvo(cadastro, linha),
                          detalhe=f"era {antes}; {'ativo' if ativo else 'inativo'}",
                          request=request)
        except IntegrityError:
            return _desenhar(request, cadastro,
                             erro=f'Já existe "{nome}" nesta lista.')
        return HttpResponseRedirect(reverse(cadastro.rota))

    if acao == "remover":
        try:
            with transaction.atomic():
                registrar(ACOES.FILA_CADASTRO_REMOVIDO, request.usuario,
                          alvo=_alvo(cadastro, linha), request=request)
                linha.delete()
        except ProtectedError:
            # O `atomic` desfaz o registro junto: a trilha não conta uma
            # remoção que não aconteceu.
            return _desenhar(request, cadastro, erro=EM_USO)
        return HttpResponseRedirect(reverse(cadastro.rota))

    return HttpResponseRedirect(reverse(cadastro.rota))


@exigir_permissao("fila.cadastros")
@exigir_modulo_ligado("fila")
def grupos(request) -> HttpResponse:
    return _tela(request, GRUPOS)


@exigir_permissao("fila.cadastros")
@exigir_modulo_ligado("fila")
def motivos(request) -> HttpResponse:
    return _tela(request, MOTIVOS)


@exigir_permissao("fila.cadastros")
@exigir_modulo_ligado("fila")
def pausas(request) -> HttpResponse:
    return _tela(request, PAUSAS)
