"""Filiais: a tela onde o admin do cliente cadastra as unidades da empresa.

Segue `contas/views_cargos.py` de perto — o mesmo padrão (tabela dentro do cartão, barra de filtro no mesmo cartão, ações da
linha abrindo modal, "Novo" no cabeçalho da página) —, com R46 valendo em
cheio: filtro, ordenação por coluna e paginação por `comum.listagem.
montar_pagina`.
"""

from __future__ import annotations

from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import (
    Alert, Badge, Box, Button, Card, Column, Form, FormGrid,
    IconButton, Modal, PageHeader, Raw, Table, TextInput,
)
from nucleo.layout import Crumb
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render

from .filiais import pode_desativar, pode_remover
from comum.exportacao import ColunaDeExportacao, botoes, preparar_exportacao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.pedido import id_do_post
from .models import Filial
from .parametro_catalogo import valor_de
from .contexto import empresa_atual
from .site import montar_site

__all__ = ["filiais"]

#: Os campos que os modais de criar e editar oferecem, na ordem em que
#: aparecem. Mesma forma de `plataforma.views_empresa.CAMPOS`.
CAMPOS = (
    ("nome", "Nome", 6),
    ("apelido", "Apelido", 6),
    ("cnpj", "CNPJ", 4),
    ("logradouro", "Logradouro", 8),
    ("numero", "Número", 2),
    ("complemento", "Complemento", 4),
    ("bairro", "Bairro", 4),
    ("municipio", "Município", 4),
    ("uf", "UF", 2),
    ("cep", "CEP", 3),
)

#: `nome` e `apelido` são os únicos campos que o model exige
#: (`Filial.nome`/`Filial.apelido` não são `blank=True`) — `apelido` porque
#: é o que aparece no seletor do cabeçalho, e uma filial sem apelido
#: nenhum ficaria em branco ali.
OBRIGATORIOS = frozenset({"nome", "apelido"})


def _campo_oculto(nome: str, valor: str) -> str:
    """Ver o par exato em `contas.views_usuarios._campo_oculto` — mesma regra:
    `nucleo/` não tem componente de campo oculto, só `Raw` para HTML cru já
    confiável. `valor` nunca é texto de fora sem controle: é sempre um `pk`
    ou uma constante fixa desta view."""
    from django.utils.html import format_html

    return format_html(
        '<input type="hidden" name="{}" value="{}">', nome, valor,
    )


def _validar(dados: dict[str, str]) -> "str | None":
    if not dados.get("nome", "").strip():
        return "Informe o nome da filial."
    if not dados.get("apelido", "").strip():
        return "Informe o apelido da filial."
    return None


#: Os atributos que ligam a máscara do `mw5.js` no campo — o mesmo par
#: `data-mascara`/`inputmode` que `nucleo.campos` usa por dentro. A validação
#: de verdade mora no model; isto aqui só formata enquanto se digita.
ATRIBUTOS_DE_MASCARA = {
    "cnpj": {"data-mascara": "cnpj", "inputmode": "numeric"},
    "cpf": {"data-mascara": "cpf", "inputmode": "numeric"},
    "cep": {"data-mascara": "cep", "inputmode": "numeric"},
}


def _campos(valores: dict[str, str]) -> list[TextInput]:
    return [
        TextInput(name=nome, label=rotulo, span=cols, value=valores.get(nome, ""),
                  required=nome in OBRIGATORIOS,
                  attrs=ATRIBUTOS_DE_MASCARA.get(nome, {}))
        for nome, rotulo, cols in CAMPOS
    ]


def _colunas_da_lista(pagina) -> list[Column]:
    """`pagina.cabecalho` transforma o rótulo em link de ordenar — ver
    `comum.listagem` e R46."""
    return [
        Column("filial", pagina.cabecalho("filial", "Filial"), strong=True,
               render=lambda f: str(f)),
        Column("cnpj", pagina.cabecalho("cnpj", "CNPJ"),
               render=lambda f: f.cnpj or "—"),
        Column("municipio", pagina.cabecalho("municipio", "Município/UF"),
               render=lambda f: f"{f.municipio}/{f.uf}" if f.municipio else "—"),
        Column("situacao", pagina.cabecalho("situacao", "Situação"),
               align="center", render=lambda f: Badge(
            label="Ativa" if f.ativa else "Inativa",
            tone="primary" if f.ativa else "neutral")),
    ]


def _id_do_modal(acao: str, filial_pk: int) -> str:
    """Ver o par exato em `contas.views_usuarios._id_do_modal` — mesma regra:
    o gatilho na linha e o `Modal` de verdade nunca podem divergir sobre o
    id, então os dois calculam pela mesma função."""
    return f"filial-{filial_pk}-{acao}"


def _acoes_da_linha(filial: Filial) -> Box:
    # `wrap=False` e `align="end"`: a coluna de ações é estreita, e `.box`
    # nasce com `flex-wrap: wrap` — sem isto os ícones caem um embaixo do
    # outro e esticam a altura de toda linha da tabela.
    return Box(direction="row", gap="sm", wrap=False, align="end",
               cross="center", body=[
        IconButton(icon="edit", title=_("Editar"),
                   attrs={"data-open-modal": _id_do_modal("editar", filial.pk)}),
        IconButton(
            icon="x-circle" if filial.ativa else "check-circle",
            title="Desativar" if filial.ativa else "Ativar",
            attrs={"data-open-modal": _id_do_modal("estado", filial.pk)}),
        IconButton(icon="trash", title=_("Remover"),
                   attrs={"data-open-modal": _id_do_modal("remover", filial.pk)}),
    ])


def _modal_criar_filial(request) -> Modal:
    return Modal(id="filial-criar", title=_("Nova filial"), size="lg",
        body=Form(action=reverse("filiais"), children=[
            Raw(html=campo_csrf(request)),
            Raw(html=_campo_oculto("acao", "criar")),
            FormGrid(children=_campos({})),
            Button(label=_("Criar filial"), variant="primary", type="submit"),
        ]))


def _modais_de_filial(request, filial: Filial) -> list[Modal]:
    """Um `Modal` de editar, um de ativar/desativar e um de remover — cada
    um com o próprio `<form>`, nascendo fechado, em `overlays=`. Mesmo papel
    de `contas.views_usuarios._modais_de_usuario`."""
    valores = {nome: getattr(filial, nome) or "" for nome, _resto, _resto in CAMPOS}

    if filial.ativa:
        acao_de_estado, rotulo_de_estado = "desativar", "Desativar"
        aviso_de_estado = Alert(
            tone="warn", message=f'Desativar "{filial}"? A filial deixa de '
                                  f'aparecer no seletor de quem a usa até '
                                  f'ser ativada de novo.')
    else:
        acao_de_estado, rotulo_de_estado = "ativar", "Ativar"
        aviso_de_estado = Alert(tone="info", message=f'Ativar "{filial}" de novo?')

    return [
        Modal(id=_id_do_modal("editar", filial.pk), title=f"Editar {filial}",
              size="lg", body=Form(action=reverse("filiais"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", "salvar")),
                  Raw(html=_campo_oculto("filial", str(filial.pk))),
                  FormGrid(children=_campos(valores)),
                  Button(label=_("Salvar"), variant="primary", type="submit"),
              ])),
        Modal(id=_id_do_modal("estado", filial.pk), title=rotulo_de_estado,
              body=Form(action=reverse("filiais"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", acao_de_estado)),
                  Raw(html=_campo_oculto("filial", str(filial.pk))),
                  aviso_de_estado,
                  Button(label=rotulo_de_estado,
                         variant="danger" if acao_de_estado == "desativar" else "primary",
                         type="submit"),
              ])),
        # Nomeia o que seria removido, como o brief pede. A recusa de
        # verdade continua vindo do servidor (`pode_remover`, chamado de
        # dentro de `filiais()`) — este `Alert` é só a confirmação da
        # interface, e nunca substitui aquela checagem.
        Modal(id=_id_do_modal("remover", filial.pk), title=_("Remover filial"),
              body=Form(action=reverse("filiais"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", "remover")),
                  Raw(html=_campo_oculto("filial", str(filial.pk))),
                  Alert(tone="danger",
                        message=f'Remover a filial "{filial}"? Esta ação '
                                f'não pode ser desfeita.'),
                  Button(label=_("Remover"), variant="danger", type="submit"),
              ])),
    ]


#: `chave da URL -> campo(s) do ORM` — só o que esta lista declara pode
#: entrar em `order_by` (ver `comum.listagem._resolver_ordenacao`).
def _filiais_da_empresa(request):
    """As filiais que ESTA tela enxerga: as da empresa do contexto, e só elas.

    **É a trava desta tela, e é o que permitiu dar `filiais.editar` ao
    titular** (14/09/2026). Até ali ela listava `Filial.objects.all()` — as
    filiais da instalação inteira —, o que era aceitável enquanto só a MW5 a
    abria e seria vazamento na mão de um cliente: o titular da Alfa veria, e
    editaria, as lojas da Beta.

    Listagem, exportação e TODAS as ações passam por aqui. Uma ação que
    buscasse a filial por conta própria seria a porta para o id de outra
    empresa chegar pelo POST.

    Sem empresa no contexto, nada: `none()` e não `all()`, porque o erro de
    faltar contexto não pode ser mostrar tudo.
    """
    empresa = empresa_atual(request)
    if empresa is None:
        return Filial.objects.none()
    return Filial.objects.filter(empresa=empresa)


_ORDENAVEIS = {
    "filial": ("apelido", "nome"),
    "cnpj": ("cnpj",),
    "municipio": ("municipio", "uf"),
    "situacao": ("ativa", "apelido"),
}

_FILTRAVEIS = {
    "filial": ColunaFiltravel(("apelido", "nome"), "Filial"),
    # Caixa de escolha, não campo de digitar — mesmo raciocínio da coluna
    # "Situação" de `contas.views_usuarios`: ativa ou inativa são dois
    # valores conhecidos, e um campo de texto sobre eles convida ao erro.
    "situacao": ColunaFiltravel("ativa", "Situação", tipo="opcoes",
                                opcoes=lambda: [("1", "Ativa"), ("0", "Inativa")]),
}


def _desenhar(request, erro: "str | None" = None) -> HttpResponse:
    env = ambiente()
    with use_environment(env):
        site = montar_site(request)

        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=_("Filiais"),
                       subtitle="As unidades desta empresa, e quem pode "
                                "escolhê-las no cabeçalho.",
                       actions=[
                           Button(label=_("Nova filial"), variant="primary",
                                  attrs={"data-open-modal": "filial-criar"}),
                           *botoes(request),
                       ]),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))

        listagem = montar_pagina(
            request, _filiais_da_empresa(request), ordenaveis=_ORDENAVEIS,
            padrao="filial", filtraveis=_FILTRAVEIS)
        filiais_existentes = listagem.linhas

        conteudo.append(Card(
            title=_("Filiais existentes"), padded=False,
            body=[
                # Filtros salvos (item 27): os desta pessoa nesta tela.
                listagem.barra,
                Table(columns=_colunas_da_lista(listagem), rows=filiais_existentes,
                      row_actions=_acoes_da_linha),
                listagem.paginacao,
            ],
        ))

        modais = [_modal_criar_filial(request)]
        for filial in filiais_existentes:
            modais.extend(_modais_de_filial(request, filial))

        pagina = site.page(
            # `full`: a tela usa a largura toda — mesmo motivo de
            # `contas.views_cargos`/`views_usuarios`.
            title=_("Filiais"),
            width="full",
            stylesheets=["/static/plataforma/listagem.css"],
            content=conteudo,
            crumbs=[Crumb(_("Filiais"))],
            user=getattr(request, "usuario", None),
            overlays=modais,
        )
        return render(pagina)


#: As colunas que saem no arquivo e no papel — as MESMAS da tabela, com o
#: valor em texto no lugar do Badge.
COLUNAS_DE_EXPORTACAO = (
    ColunaDeExportacao("filial", "Filial", lambda f: str(f)),
    ColunaDeExportacao("cnpj", "CNPJ", lambda f: f.cnpj),
    ColunaDeExportacao("municipio", "Município/UF",
                       lambda f: f"{f.municipio}/{f.uf}" if f.municipio else ""),
    ColunaDeExportacao("situacao", "Situação",
                       lambda f: "Ativa" if f.ativa else "Inativa"),
)


# Acesso da MW5 vem de `is_superuser`... (a mesma ordem de guardas de
# `contas/views_usuarios.py` vale aqui).
# ---------------------------------------------------------------------------
# As ações do POST, uma função cada. Mesma razão e mesmo formato de
# `contas.views_usuarios`: a cadeia de `if acao == ...` media complexidade 19
# — a mais alta do código autoral — e a view voltou a fazer uma coisa só.
#
# Duas tabelas: `criar` não mexe em ninguém existente; as outras recebem a
# filial já resolvida pelo despacho, e nenhuma busca a própria.
# ---------------------------------------------------------------------------


def _acao_criar(request) -> HttpResponse:
    dados = {nome: request.POST.get(nome, "").strip() for nome, _resto, _resto in CAMPOS}
    erro = _validar(dados)
    if erro:
        return _desenhar(request, erro=erro)
    # `nova_filial_nasce_ativa` (`plataforma.parametro`): o processo de
    # cada cliente decide se a filial recém-criada já entra no ar ou
    # nasce em preparação — não `Filial.ativa` default, que é o mesmo
    # padrão só que fixo no código para toda instalação.
    dados["ativa"] = valor_de("nova_filial_nasce_ativa")
    # A filial nasce na empresa do contexto — nunca sem empresa, que era o
    # que acontecia até 14/09/2026 e fazia a filial nova não pertencer a
    # ninguém.
    empresa = empresa_atual(request)
    if empresa is None:
        return _desenhar(
            request, erro=_("Escolha uma empresa no cabeçalho antes de criar "
                            "uma filial."))
    dados["empresa"] = empresa
    # `atomic()`: se `registrar` falhar, a filial recém-criada desfaz
    # junto — nunca uma filial criada sem ninguém saber quem criou.
    with transaction.atomic():
        filial = Filial.objects.create(**dados)
        registrar(ACOES.FILIAL_CRIADA, request.usuario, alvo=str(filial), request=request)
    return HttpResponseRedirect(reverse("filiais"))


def _acao_salvar(request, filial) -> HttpResponse:
    dados = {nome: request.POST.get(nome, "").strip() for nome, _resto, _resto in CAMPOS}
    erro = _validar(dados)
    if erro:
        return _desenhar(request, erro=erro)
    with transaction.atomic():
        for nome, valor in dados.items():
            setattr(filial, nome, valor)
        filial.save(update_fields=[nome for nome, _resto, _resto in CAMPOS])
        registrar(ACOES.FILIAL_EDITADA, request.usuario, alvo=str(filial), request=request)
    return HttpResponseRedirect(reverse("filiais"))


def _trocar_estado(request, filial, ativar: bool) -> HttpResponse:
    """Liga ou desliga `filial`.

    Duas ações, uma função — mesmo formato de
    `contas.views_usuarios._trocar_estado`. A trava vale só para desativar:
    reativar nunca deixa a instalação sem filial. A frase da recusa vem de
    `plataforma.filiais.pode_desativar` e nunca é reescrita aqui, para esta
    ação e "remover" não divergirem com o tempo.
    """
    with transaction.atomic():
        if not ativar:
            # A linha da filial trancada ANTES de perguntar: um módulo que
            # recusa pelo que está acontecendo na filial (a fila tranca a
            # mesma linha para bater o ponto) não pode ver "ninguém" e, no
            # instante seguinte, alguém entrar na loja que vai ser desativada.
            Filial.objects.select_for_update().filter(pk=filial.pk).first()
            motivo = pode_desativar(filial)
            if motivo:
                return _desenhar(request, erro=motivo)
        filial.ativa = ativar
        filial.save(update_fields=["ativa"])
        registrar(
            ACOES.FILIAL_ATIVADA if ativar else ACOES.FILIAL_DESATIVADA,
            request.usuario, alvo=str(filial), request=request,
        )
    return HttpResponseRedirect(reverse("filiais"))


def _acao_ativar(request, filial) -> HttpResponse:
    return _trocar_estado(request, filial, ativar=True)


def _acao_desativar(request, filial) -> HttpResponse:
    return _trocar_estado(request, filial, ativar=False)


def _acao_remover(request, filial) -> HttpResponse:
    motivo = pode_remover(filial)
    if motivo:
        return _desenhar(request, erro=motivo)
    with transaction.atomic():
        # Registrado ANTES do `delete()` — depois dele não sobra
        # `str(filial)` nenhum para ler, e uma falha aqui, dentro do
        # mesmo `atomic()`, desfaz a remoção junto: nunca um registro
        # de remoção que sobrevive a uma remoção que não aconteceu.
        registrar(ACOES.FILIAL_REMOVIDA, request.usuario, alvo=str(filial), request=request)
        filial.delete()
    return HttpResponseRedirect(reverse("filiais"))
    return HttpResponseRedirect(reverse("filiais"))


ACOES_SEM_FILIAL = {"criar": _acao_criar}

ACOES_COM_FILIAL = {
    "salvar": _acao_salvar,
    "ativar": _acao_ativar,
    "desativar": _acao_desativar,
    "remover": _acao_remover,
}


@exigir_permissao("filiais.editar")
@exigir_modulo_ligado("filiais")
def filiais(request) -> HttpResponse:
    """A tela de Filiais: uma rota, um `acao` no corpo do POST decide o quê."""
    if request.method != "POST":
        # A exportação roda aqui dentro, depois dos guardas.
        if request.GET.get("formato"):
            exportacao = preparar_exportacao(
                request, queryset=_filiais_da_empresa(request),
                colunas=COLUNAS_DE_EXPORTACAO,
                ordenaveis=_ORDENAVEIS, padrao="filial",
                filtraveis=_FILTRAVEIS, titulo=_("Filiais"))
            if exportacao is not None:
                return exportacao
        return _desenhar(request)

    acao = request.POST.get("acao", "")

    sem_filial = ACOES_SEM_FILIAL.get(acao)
    if sem_filial is not None:
        return sem_filial(request)

    com_filial = ACOES_COM_FILIAL.get(acao)
    if com_filial is None:
        return HttpResponseRedirect(reverse("filiais"))

    # A partir daqui toda ação mexe numa filial JÁ existente.
    filial = _filiais_da_empresa(request).filter(
        pk=id_do_post(request, "filial")).first()
    if filial is None:
        return _desenhar(request, erro=_("Filial não encontrada."))


    return com_filial(request, filial)
