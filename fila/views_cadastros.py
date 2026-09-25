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
from comum.auditoria import registrar

from .auditoria import ACOES_DA_FILA
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

from .models import GrupoDeItem, Midia, MotivoDeNaoVenda, TipoDePausa

__all__ = ["grupos", "midias", "motivos", "pausas"]


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
MIDIAS = Cadastro(Midia, "fila_midias", _("Mídias"), "Mídia",
                  _("Por qual canal o cliente chegou: o vendedor escolhe ao "
                    "lançar a venda ou a não venda."),
                  _("Nova mídia"))

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


def _campos(nome="", ativo=True, com_ativo=False):
    """Os campos do modal de cadastro — sem a "Ordem" (18/09/2026).

    O cliente pediu que o campo saísse: primeiro saiu a COLUNA da tabela, e
    depois ele viu que o modal ainda pedia o número. A coluna continua no
    banco e continua mandando na ordem da lista (`padrao="ordem"`), mas quem
    a escreve agora é a tela: o item novo entra no FIM (`_proxima_ordem`), e
    editar não mexe no que já estava lá — zerar a ordem de quem tinha uma
    seria mexer, sem avisar, na posição de tudo que já existe.
    """
    campos = [
        TextInput(name="nome", label=_("Nome"), span=12, value=nome,
                  required=True, maxlength=80),
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
                _campos(linha.nome, linha.ativo, com_ativo=True),
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
                # O nome veste a classe que a folha da tela põe em CAIXA ALTA
                # (`fila/static/fila/cadastros.css`). É da FOLHA, e não do
                # dado: o cadastro continua gravado como a pessoa o escreveu,
                # e a folha de venda da fila mostra "Sofás" — a caixa alta é a
                # leitura desta lista, e só dela (18/09/2026, pedido do
                # cliente).
                Column("nome", listagem.cabecalho("nome", "Nome"), strong=True,
                       render=lambda l: format_html(
                           '<span class="cadastro-nome">{}</span>', l.nome)),
                # A coluna "Ordem" saiu em 18/09/2026, a pedido do cliente. O
                # campo continua no cadastro, e a lista continua saindo por ele
                # (`_ORDENAVEIS`, `padrao="ordem"`): o que saiu foi o número na
                # cara de quem lê a tela.
                Column("ativo", listagem.cabecalho("ativo", "Situação"),
                       render=lambda l: "Ativo" if l.ativo else "Inativo"),
            ], rows=listagem.linhas, row_actions=_acoes_da_linha),
            listagem.paginacao,
        ]))
        pagina = site.page(
            title=cadastro.titulo, width="full",
            # A folha da tela: o nome de cada item em caixa alta
            # (`fila/static/fila/cadastros.css`).
            stylesheets=["/static/plataforma/listagem.css",
                         "/static/fila/cadastros.css"],
            content=conteudo, crumbs=[Crumb(cadastro.titulo)],
            user=getattr(request, "usuario", None),
            overlays=_modais(request, cadastro, listagem.linhas))
        return render(pagina)


def _ler(request):
    """`(nome, ativo)` do POST. A "Ordem" não vem mais da tela."""
    nome = (request.POST.get("nome") or "").strip()[:80]
    return nome, request.POST.get("ativo") == "1"


def _proxima_ordem(linhas) -> int:
    """O número que põe o item novo no FIM da lista.

    A ordem da lista é a coluna `ordem` (`_ORDENAVEIS`, `padrao="ordem"`), e
    ela deixou de ser campo da tela: quem chega agora recebe o próximo número
    em vez de zero — com zero (o padrão da coluna) o item novo saltaria para o
    começo, na frente de tudo que o cliente já tinha ordenado.
    """
    from django.db.models import Max

    # O teto do inteiro do Postgres, aqui e não no POST: era o B4, quando o
    # número vinha do campo e 99999999999 estourava a coluna com 500. Agora o
    # número sai da própria lista, e uma lista que já chegou ao teto devolve o
    # teto em vez de estourar na linha seguinte.
    return min((linhas.aggregate(m=Max("ordem"))["m"] or 0) + 1, 2_147_483_647)


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
        nome, _ativo = _ler(request)
        if not nome:
            return _desenhar(request, cadastro, erro=_("Informe o nome."))
        try:
            with transaction.atomic():
                linha = cadastro.model.irrestritos.create(
                    empresa=empresa, nome=nome,
                    ordem=_proxima_ordem(_linhas(request, cadastro)))
                registrar(ACOES_DA_FILA.FILA_CADASTRO_CRIADO, request.usuario,
                          alvo=_alvo(cadastro, linha), request=request)
        except IntegrityError:
            return _desenhar(request, cadastro,
                             erro=_('Já existe "%(nome)s" nesta lista.') % {"nome": nome})
        return HttpResponseRedirect(reverse(cadastro.rota))

    linha = _linhas(request, cadastro).filter(
        pk=id_do_post(request, "id")).first()
    if linha is None:
        return _desenhar(request, cadastro, erro=NAO_ENCONTRADO)

    if acao == "salvar":
        nome, ativo = _ler(request)
        if not nome:
            return _desenhar(request, cadastro, erro=_("Informe o nome."))
        antes = _alvo(cadastro, linha)
        try:
            with transaction.atomic():
                # A ordem NÃO entra aqui: ela é do cadastro, não da tela.
                linha.nome, linha.ativo = nome, ativo
                linha.save(update_fields=["nome", "ativo"])
                registrar(ACOES_DA_FILA.FILA_CADASTRO_EDITADO, request.usuario,
                          alvo=_alvo(cadastro, linha),
                          detalhe=f"era {antes}; {'ativo' if ativo else 'inativo'}",
                          request=request)
        except IntegrityError:
            return _desenhar(request, cadastro,
                             erro=_('Já existe "%(nome)s" nesta lista.') % {"nome": nome})
        return HttpResponseRedirect(reverse(cadastro.rota))

    if acao == "remover":
        try:
            with transaction.atomic():
                registrar(ACOES_DA_FILA.FILA_CADASTRO_REMOVIDO, request.usuario,
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


@exigir_permissao("fila.cadastros")
@exigir_modulo_ligado("fila")
def midias(request) -> HttpResponse:
    return _tela(request, MIDIAS)
