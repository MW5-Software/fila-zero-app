"""Cargos: a tela onde o titular monta os cargos da conta dele.

Nasceu em 14/09/2026 no lugar de Perfis no menu do titular. Edita `contas.Cargo`
(o modelo do plano 1 de Cargos e alocações) — nome, alcance, "é cliente" e as
permissões. É daqui que vem a permissão de todo membro da conta, pelo cargo da
alocação (`contas.lugar`).

Tabela com R46, modais, uma rota com um `acao` no POST, e duas travas:

1. **Quem edita é o NÍVEL, não a permissão.** `cargos.editar` só põe a tela no
   menu. Se editar cargo dependesse só dela, um cargo que a carregasse deixaria
   quem o tem marcar permissão nova no próprio cargo e se promover. Por isso a
   view confere o nível (titular ou MW5) depois das guardas, e as caixas nunca
   oferecem as permissões de Cargos (`SEM_MODULOS`).
2. **A tela só enxerga os cargos da conta do contexto** — a dona da empresa
   escolhida no cabeçalho. Listagem, exportação e toda ação passam por
   `_cargos_da_conta`; o id de um cargo de outra conta chegando pelo POST vira
   "Cargo não encontrado".
"""

from __future__ import annotations

from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.exportacao import ColunaDeExportacao, botoes, preparar_exportacao
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.pedido import id_do_post
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import (
    Alert, Box, Button, Card, Checkbox, Column, Form, FormGrid, IconButton,
    Modal, PageHeader, Raw, Select, Table, TextInput,
)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render

from .backend import APP_DOS_MODULOS
from .caixas_de_permissao import grupos_de_checkboxes, permissoes_oferecidas
from .cargos import pode_remover
from .identidade import usuario_de
from .models import Alcance, Cargo, Nivel

__all__ = ["cargos"]

#: Os módulos cujas permissões um cargo NUNCA carrega. Ver o item 1 do
#: cabeçalho: Cargos e Perfis são as duas telas que concedem acesso, e quem as
#: tivesse pelo cargo poderia conceder a si mesmo o que quisesse.
SEM_MODULOS = frozenset({"cargos"})

NAO_ENCONTRADO = _("Cargo não encontrado.")


def _conta(request):
    """A conta do contexto: a dona da empresa escolhida no cabeçalho.

    Pela empresa, e não pela pessoa: para o titular dá o mesmo resultado (a
    empresa dele é dele), e para a MW5 — que não é de conta nenhuma — é a única
    resposta com sentido: ela edita os cargos da conta que está olhando.
    """
    from plataforma.contexto import empresa_atual

    empresa = empresa_atual(request)
    return empresa.dono if empresa is not None and empresa.dono_id else None


def _cargos_da_conta(request):
    """A única porta da tela para `Cargo`. Sem conta no contexto, nada —
    `none()` e nunca "todos"."""
    conta = _conta(request)
    if conta is None:
        return Cargo.objects.none()
    return Cargo.objects.filter(conta=conta)


def _com_contagens(consulta):
    """As contagens por `annotate`, para poder ordenar por elas (R46).
    `distinct=True` nas duas: dois `JOIN` de muitos-para-muitos sem ele
    multiplicam as linhas e inflam as duas contagens."""
    return consulta.annotate(
        num_pessoas=Count("alocacoes__pessoa", distinct=True),
        num_permissoes=Count("permissoes", distinct=True),
    )


def _pode_editar_cargos(request) -> bool:
    """Titular ou MW5 — pelo nível. Ver o item 1 do cabeçalho."""
    pessoa = usuario_de(getattr(request, "usuario", None))
    if pessoa is None:
        return False
    return pessoa.is_superuser or pessoa.nivel <= Nivel.TITULAR


def _contagem(quantidade: int, singular: str, plural: str) -> str:
    return f"{quantidade} {singular if quantidade == 1 else plural}"


def _campo_oculto(nome: str, valor: str) -> Raw:
    """`nucleo/` não tem componente de campo oculto. `valor` é sempre um `pk` ou uma constante desta
    view, nunca texto de fora."""
    return Raw(html=format_html('<input type="hidden" name="{}" value="{}">',
                                nome, valor))


def _colunas(pagina) -> "list[Column]":
    return [
        Column("rotulo", pagina.cabecalho("cargo", "Cargo"), strong=True),
        Column("alcance", pagina.cabecalho("alcance", "Enxerga"),
               render=lambda c: c.get_alcance_display()),
        Column("cliente", "Cliente", align="center",
               render=lambda c: "Sim" if c.e_cliente else "—"),
        Column("pessoas", pagina.cabecalho("pessoas", "Pessoas"),
               render=lambda c: _contagem(c.num_pessoas, "pessoa", "pessoas")),
        Column("permissoes", pagina.cabecalho("permissoes", "Permissões"),
               render=lambda c: _contagem(c.num_permissoes, "permissão",
                                          "permissões")),
    ]


def _id_do_modal(acao: str, cargo_pk: int) -> str:
    return f"cargo-{cargo_pk}-{acao}"


def _acoes_da_linha(cargo: Cargo) -> Box:
    botoes_da_linha = [
        IconButton(icon="edit", title=_("Editar"),
                   attrs={"data-open-modal": _id_do_modal("editar", cargo.pk)}),
    ]
    # Cargo de fábrica não oferece remover: a recusa viria sempre. A trava de
    # verdade continua no servidor (`pode_remover`).
    if not cargo.de_fabrica:
        botoes_da_linha.append(IconButton(
            icon="trash", title=_("Remover"),
            attrs={"data-open-modal": _id_do_modal("remover", cargo.pk)}))
    return Box(direction="row", gap="sm", wrap=False, align="end",
               cross="center", body=botoes_da_linha)


def _campos_do_cargo(rotulo="", alcance=Alcance.PROPRIOS, e_cliente=False):
    return FormGrid(children=[
        TextInput(name="rotulo", label=_("Nome do cargo"), span=6,
                  value=rotulo, required=True),
        Select(name="alcance", label=_("Enxerga"), span=4, value=alcance,
               options=list(Alcance.choices)),
        Checkbox(name="e_cliente", value="1", label=_("É cliente"),
                 checked=e_cliente,
                 help=_("O cargo é de quem compra da empresa, e não de quem "
                        "trabalha nela.")),
    ])


def _modal_criar(request, oferecidas) -> Modal:
    return Modal(id="cargo-criar", title=_("Novo cargo"), size="lg",
        body=Form(action=reverse("cargos"), children=[
            Raw(html=campo_csrf(request)),
            _campo_oculto("acao", "criar"),
            _campos_do_cargo(),
            *grupos_de_checkboxes(frozenset(), oferecidas),
            Button(label=_("Criar cargo"), variant="primary", type="submit"),
        ]))


def _modais_do_cargo(request, cargo: Cargo, oferecidas) -> "list[Modal]":
    marcadas = frozenset(cargo.permissoes.values_list("codename", flat=True))
    modais = [
        Modal(id=_id_do_modal("editar", cargo.pk),
              title=f"Editar {cargo.rotulo}", size="lg",
              body=Form(action=reverse("cargos"), children=[
                  Raw(html=campo_csrf(request)),
                  _campo_oculto("acao", "salvar"),
                  _campo_oculto("cargo", str(cargo.pk)),
                  _campos_do_cargo(cargo.rotulo, cargo.alcance, cargo.e_cliente),
                  *grupos_de_checkboxes(marcadas, oferecidas),
                  Button(label=_("Salvar"), variant="primary", type="submit"),
              ])),
    ]
    if not cargo.de_fabrica:
        modais.append(Modal(
            id=_id_do_modal("remover", cargo.pk), title=_("Remover cargo"),
            body=Form(action=reverse("cargos"), children=[
                Raw(html=campo_csrf(request)),
                _campo_oculto("acao", "remover"),
                _campo_oculto("cargo", str(cargo.pk)),
                Alert(tone="danger",
                      message=f'Remover o cargo "{cargo.rotulo}"? Esta ação '
                              f'não pode ser desfeita.'),
                Button(label=_("Remover"), variant="danger", type="submit"),
            ])))
    return modais


_ORDENAVEIS = {
    "cargo": "rotulo",
    "alcance": ("alcance", "rotulo"),
    "pessoas": ("num_pessoas", "rotulo"),
    "permissoes": ("num_permissoes", "rotulo"),
}

_FILTRAVEIS = {
    "cargo": ColunaFiltravel("rotulo", "Cargo"),
    # Caixa de escolha: são três valores conhecidos.
    "alcance": ColunaFiltravel("alcance", "Enxerga", tipo="opcoes",
                               opcoes=lambda: list(Alcance.choices)),
}

COLUNAS_DE_EXPORTACAO = (
    ColunaDeExportacao("cargo", "Cargo", lambda c: c.rotulo),
    ColunaDeExportacao("alcance", "Enxerga", lambda c: c.get_alcance_display()),
    ColunaDeExportacao("cliente", "Cliente", lambda c: "Sim" if c.e_cliente else ""),
    ColunaDeExportacao("pessoas", "Pessoas", lambda c: c.num_pessoas),
    ColunaDeExportacao("permissoes", "Permissões", lambda c: c.num_permissoes),
)


def _desenhar(request, erro=None) -> HttpResponse:
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        oferecidas = permissoes_oferecidas(SEM_MODULOS)

        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=_("Cargos"),
                       subtitle=_("Os cargos desta conta: o que cada um pode "
                                  "fazer e quais registros enxerga."),
                       actions=[
                           Button(label=_("Novo cargo"), variant="primary",
                                  attrs={"data-open-modal": "cargo-criar"}),
                           *botoes(request),
                       ]),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))

        listagem = montar_pagina(
            request, _com_contagens(_cargos_da_conta(request)),
            ordenaveis=_ORDENAVEIS, padrao="cargo", filtraveis=_FILTRAVEIS)

        conteudo.append(Card(
            title=_("Cargos da conta"), padded=False,
            body=[
                listagem.barra,
                Table(columns=_colunas(listagem), rows=listagem.linhas,
                      row_actions=_acoes_da_linha),
                listagem.paginacao,
            ],
        ))

        modais = [_modal_criar(request, oferecidas)]
        for cargo in listagem.linhas:
            modais.extend(_modais_do_cargo(request, cargo, oferecidas))

        pagina = site.page(
            title=_("Cargos"),
            width="full",
            stylesheets=["/static/plataforma/listagem.css"],
            content=conteudo,
            crumbs=[Crumb(_("Cargos"))],
            user=getattr(request, "usuario", None),
            overlays=modais,
        )
        return render(pagina)


def _salvar_permissoes(cargo: Cargo, enviadas) -> None:
    """Troca só a fatia que a tela ofereceu: permissão de módulo desligado não
    tem caixa, e um `.set()` cego a arrancaria em silêncio.

    **Com uma diferença:** o que é de `SEM_MODULOS` nunca sobrevive, nem vindo
    do POST nem já gravado. Um cargo com `cargos.editar` é a
    escalada que esta tela existe para não permitir.
    """
    permitidos = {codename for codename, _r, _c, _m in
                  permissoes_oferecidas(SEM_MODULOS)}
    validos = set(enviadas) & permitidos
    proibidos = {f"{chave}_" for chave in SEM_MODULOS}

    fora_do_oferecido = [
        p for p in cargo.permissoes.exclude(
            content_type__app_label=APP_DOS_MODULOS, codename__in=permitidos)
        if not any(p.codename.startswith(prefixo) for prefixo in proibidos)
    ]
    escolhidas = Permission.objects.filter(
        content_type__app_label=APP_DOS_MODULOS, codename__in=validos)
    cargo.permissoes.set(fora_do_oferecido + list(escolhidas))


def _dados_do_post(request):
    """`(rotulo, alcance, e_cliente, erro)` do formulário."""
    rotulo = request.POST.get("rotulo", "").strip()
    alcance = request.POST.get("alcance", "")
    if not rotulo:
        return rotulo, alcance, False, _("Informe o nome do cargo.")
    if alcance not in Alcance.values:
        return rotulo, alcance, False, _("Escolha o que o cargo enxerga.")
    return rotulo, alcance, bool(request.POST.get("e_cliente")), None


def _acao_criar(request) -> HttpResponse:
    conta = _conta(request)
    if conta is None:
        return _desenhar(request, erro=_("Escolha uma empresa no cabeçalho "
                                         "antes de criar um cargo."))
    rotulo, alcance, e_cliente, erro = _dados_do_post(request)
    if erro:
        return _desenhar(request, erro=erro)
    nome = slugify(rotulo)
    if not nome:
        return _desenhar(request, erro=_("Informe um nome com letras ou números."))
    if Cargo.objects.filter(conta=conta, nome=nome).exists():
        return _desenhar(request, erro=f'Já existe um cargo chamado "{rotulo}".')
    with transaction.atomic():
        cargo = Cargo.objects.create(conta=conta, nome=nome, rotulo=rotulo,
                                     alcance=alcance, e_cliente=e_cliente)
        _salvar_permissoes(cargo, request.POST.getlist("permissoes"))
        registrar(ACOES.CARGO_CRIADO, request.usuario, alvo=cargo.rotulo,
                  request=request)
    return HttpResponseRedirect(reverse("cargos"))


def _acao_salvar(request, cargo: Cargo) -> HttpResponse:
    rotulo, alcance, e_cliente, erro = _dados_do_post(request)
    if erro:
        return _desenhar(request, erro=erro)
    with transaction.atomic():
        # `nome` não muda: é o identificador estável, e é por ele que a
        # semeadura reconhece o cargo de fábrica. O que a tela edita é o rótulo.
        cargo.rotulo = rotulo
        cargo.alcance = alcance
        cargo.e_cliente = e_cliente
        cargo.save(update_fields=["rotulo", "alcance", "e_cliente"])
        _salvar_permissoes(cargo, request.POST.getlist("permissoes"))
        registrar(ACOES.CARGO_EDITADO, request.usuario, alvo=cargo.rotulo,
                  request=request)
    return HttpResponseRedirect(reverse("cargos"))


def _acao_remover(request, cargo: Cargo) -> HttpResponse:
    motivo = pode_remover(cargo)
    if motivo:
        return _desenhar(request, erro=motivo)
    with transaction.atomic():
        # Registrado antes do `delete()`: depois dele não há rótulo para ler,
        # e uma falha aqui desfaz a remoção junto.
        registrar(ACOES.CARGO_REMOVIDO, request.usuario, alvo=cargo.rotulo,
                  request=request)
        cargo.delete()
    return HttpResponseRedirect(reverse("cargos"))


ACOES_COM_CARGO = {"salvar": _acao_salvar, "remover": _acao_remover}


# A ordem das guardas é a de toda tela desta casa: `exigir_permissao` por fora
# (cuida de sessão ausente e marca `exige_login`), `exigir_modulo_ligado` por
# dentro. A trava por NÍVEL vem depois das duas.
@exigir_permissao("cargos.editar")
@exigir_modulo_ligado("cargos")
def cargos(request) -> HttpResponse:
    """A tela de Cargos: uma rota, um `acao` no POST decide o quê."""
    if not _pode_editar_cargos(request):
        # 404 e não 403, como as outras telas que a pessoa não alcança: quem
        # não pode não precisa saber que a tela existe.
        return HttpResponseNotFound()

    if request.method != "POST":
        if request.GET.get("formato"):
            exportacao = preparar_exportacao(
                request, queryset=_com_contagens(_cargos_da_conta(request)),
                colunas=COLUNAS_DE_EXPORTACAO, ordenaveis=_ORDENAVEIS,
                padrao="cargo", filtraveis=_FILTRAVEIS, titulo=_("Cargos"))
            if exportacao is not None:
                return exportacao
        return _desenhar(request)

    acao = request.POST.get("acao", "")
    if acao == "criar":
        return _acao_criar(request)
    faz = ACOES_COM_CARGO.get(acao)
    if faz is None:
        return HttpResponseRedirect(reverse("cargos"))
    cargo = _cargos_da_conta(request).filter(
        pk=id_do_post(request, "cargo")).first()
    if cargo is None:
        return _desenhar(request, erro=NAO_ENCONTRADO)
    return faz(request, cargo)
