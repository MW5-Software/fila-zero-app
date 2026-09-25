"""Filiais: a tela onde o admin do cliente cadastra as unidades da empresa.

Segue `contas/views_cargos.py` de perto — o mesmo padrão (tabela dentro do cartão, barra de filtro no mesmo cartão, ações da
linha abrindo modal, "Novo" no cabeçalho da página) —, com R46 valendo em
cheio: filtro, ordenação por coluna e paginação por `comum.listagem.
montar_pagina`.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.permissoes import pode
from nucleo.components import (
    Alert, Badge, Box, Button, Card, Cell, Column, Form, FormGrid,
    IconButton, Modal, Option, PageHeader, Raw, Select, Table, TextInput,
)
from nucleo.layout import Crumb
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render

from .caixas_da_filial import caixas
from .filiais import (
    FILTRAVEIS, ORDENAVEIS, ROTULOS, empresa_do_pedido, empresas_da_conta,
    filiais_da_empresa, pode_desativar, pode_remover,
)
from comum.exportacao import ColunaDeExportacao, botoes, preparar_exportacao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import montar_pagina
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
        Column("filial", pagina.cabecalho("filial", ROTULOS["filial"]), strong=True,
               render=lambda f: str(f)),
        Column("cnpj", pagina.cabecalho("cnpj", ROTULOS["cnpj"]),
               render=lambda f: f.cnpj or "—"),
        Column("municipio", pagina.cabecalho("municipio", ROTULOS["municipio"]),
               render=lambda f: f"{f.municipio}/{f.uf}" if f.municipio else "—"),
        Column("situacao", pagina.cabecalho("situacao", ROTULOS["situacao"]),
               align="center", render=lambda f: Badge(
            label="Ativa" if f.ativa else "Inativa",
            tone="primary" if f.ativa else "neutral")),
    ]


def _id_do_modal(acao: str, filial_pk: int) -> str:
    """Ver o par exato em `contas.views_usuarios._id_do_modal` — mesma regra:
    o gatilho na linha e o `Modal` de verdade nunca podem divergir sobre o
    id, então os dois calculam pela mesma função."""
    return f"filial-{filial_pk}-{acao}"


def _pode_editar(request) -> bool:
    """Criar, editar e remover filial: `filiais.editar`, do dono e da MW5. A
    tela abre com `filiais.ativar` (25/09/2026), e quem tem só essa — o
    supervisor — liga e desliga a loja e mais nada. Conferido no POST
    (`filiais`), e não só escondido aqui."""
    return pode(request.usuario, "filiais.editar")


def _acoes_da_linha(filial: Filial, *, editar: bool = True) -> Box:
    # `wrap=False` e `align="end"`: a coluna de ações é estreita, e `.box`
    # nasce com `flex-wrap: wrap` — sem isto os ícones caem um embaixo do
    # outro e esticam a altura de toda linha da tabela.
    estado = IconButton(
        icon="x-circle" if filial.ativa else "check-circle",
        title="Desativar" if filial.ativa else "Ativar",
        attrs={"data-open-modal": _id_do_modal("estado", filial.pk)})
    botoes = [estado]
    if editar:
        botoes = [
            IconButton(icon="edit", title=_("Editar"),
                       attrs={"data-open-modal": _id_do_modal("editar", filial.pk)}),
            estado,
            IconButton(icon="trash", title=_("Remover"),
                       attrs={"data-open-modal": _id_do_modal("remover", filial.pk)}),
        ]
    return Box(direction="row", gap="sm", wrap=False, align="end",
               cross="center", body=botoes)


def _campo_de_empresa(empresas, escolhida) -> "Select | None":
    """O seletor de empresa do modal de criar (23/09/2026, pedido do cliente:
    "quando eu for criar filial num dono de conta com mais de uma empresa,
    preciso de um seletor para dizer de qual filial é aquela empresa").

    Só aparece para quem tem mais de uma: com uma empresa só, o campo seria uma
    pergunta com uma resposta única. Nasce na empresa escolhida na tela, que é
    a que a lista está mostrando.
    """
    if len(empresas) <= 1:
        return None
    return Select(name="empresa", label=_("Empresa"), span=12, required=True,
                  value=str(escolhida.pk) if escolhida else "",
                  help=_("A filial nasce nesta empresa."),
                  options=[Option(str(e.pk), str(e)) for e in empresas])


def _modal_criar_filial(request, empresas=(), escolhida=None) -> Modal:
    campo = _campo_de_empresa(empresas, escolhida)
    return Modal(id="filial-criar", title=_("Nova filial"), size="lg",
        body=Form(action=reverse("filiais"), children=[
            Raw(html=campo_csrf(request)),
            Raw(html=_campo_oculto("acao", "criar")),
            FormGrid(children=[*([campo] if campo else []), *_campos({})]),
            # As caixas dos módulos de negócio (`plataforma.caixas_da_filial`)
            # — no Fila Zero, o fim do turno da loja.
            *[caixa.desenhar(None) for caixa in caixas()],
            Button(label=_("Criar filial"), variant="primary", type="submit"),
        ]))


def _empresa_oculta(escolhida) -> list:
    """A empresa escolhida viaja no POST das ações que mexem numa filial já
    existente: é ela que diz onde a ação procura a filial — e para onde a tela
    volta. Sem isto, editar a filial da segunda empresa cairia em "Filial não
    encontrada", porque o POST seria lido na empresa do cabeçalho.
    """
    if escolhida is None:
        return []
    return [Raw(html=_campo_oculto("empresa", str(escolhida.pk)))]


def _modais_de_filial(request, filial: Filial, escolhida=None, *,
                      editar: bool = True) -> list[Modal]:
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

    modais = [
        Modal(id=_id_do_modal("editar", filial.pk), title=f"Editar {filial}",
              size="lg", body=Form(action=reverse("filiais"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", "salvar")),
                  Raw(html=_campo_oculto("filial", str(filial.pk))),
                  *_empresa_oculta(escolhida),
                  FormGrid(children=_campos(valores)),
                  *[caixa.desenhar(filial) for caixa in caixas()],
                  Button(label=_("Salvar"), variant="primary", type="submit"),
              ])),
        Modal(id=_id_do_modal("estado", filial.pk), title=rotulo_de_estado,
              body=Form(action=reverse("filiais"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", acao_de_estado)),
                  Raw(html=_campo_oculto("filial", str(filial.pk))),
                  *_empresa_oculta(escolhida),
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
                  *_empresa_oculta(escolhida),
                  Alert(tone="danger",
                        message=f'Remover a filial "{filial}"? Esta ação '
                                f'não pode ser desfeita.'),
                  Button(label=_("Remover"), variant="danger", type="submit"),
              ])),
    ]
    # Quem só ativa e desativa (o supervisor, 25/09/2026) recebe só a folha
    # de ativar/desativar: as outras nem viajam na página.
    return modais if editar else [modais[1]]


def _desenhar(request, erro: "str | None" = None) -> HttpResponse:
    env = ambiente()
    with use_environment(env):
        site = montar_site(request)

        escolhida = empresa_do_pedido(request)
        empresas = empresas_da_conta(empresa_atual(request))
        editar = _pode_editar(request)

        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=_("Filiais"),
                       subtitle="As unidades desta empresa, e quem pode "
                                "escolhê-las no cabeçalho.",
                       actions=[
                           *([Button(label=_("Nova filial"), variant="primary",
                                     attrs={"data-open-modal": "filial-criar"})]
                             if editar else []),
                           *botoes(request),
                       ]),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))

        # O seletor de empresa (23/09/2026). O dono de conta com mais de uma
        # empresa cadastra a filial de qualquer uma delas, e no celular o
        # seletor do cabeçalho está escondido (`.ctx-mid` some abaixo de
        # 1000px): sem este campo, a tela só enxergava a empresa em que a
        # SESSÃO estava, e a filial recém-criada na outra não aparecia.
        if len(empresas) > 1:
            conteudo.append(Card(
                attrs={"data-empresa": "filtro"},
                body=Form(method="get", action=reverse("filiais"),
                          children=FormGrid(children=[
                              Select(name="empresa", label=_("Empresa"), span=4,
                                     value=str(escolhida.pk) if escolhida else "",
                                     options=[Option(str(e.pk), str(e))
                                              for e in empresas]),
                              Cell(span=2, children=Button(
                                  label=_("Ver"), variant="primary",
                                  type="submit")),
                          ]))))

        listagem = montar_pagina(
            request, filiais_da_empresa(request, escolhida), ordenaveis=ORDENAVEIS,
            padrao="filial", filtraveis=FILTRAVEIS,
            # A empresa escolhida viaja nos links de ordenar, filtrar e
            # paginar: sem ela, tocar numa coluna devolvia a lista para a
            # empresa do cabeçalho.
            preservar=("empresa",))
        filiais_existentes = listagem.linhas

        conteudo.append(Card(
            title=_("Filiais existentes"), padded=False,
            body=[
                # Filtros salvos (item 27): os desta pessoa nesta tela.
                listagem.barra,
                Table(columns=_colunas_da_lista(listagem), rows=filiais_existentes,
                      row_actions=lambda f: _acoes_da_linha(f, editar=editar)),
                listagem.paginacao,
            ],
        ))

        modais = [_modal_criar_filial(request, empresas, escolhida)] if editar else []
        for filial in filiais_existentes:
            modais.extend(_modais_de_filial(request, filial, escolhida, editar=editar))

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


def _frase_da_recusa(erro) -> str:
    """A `ValidationError` de uma caixa de módulo virada em frase para a tela —
    o mesmo par de `plataforma.views_empresa._frase_da_recusa`."""
    if getattr(erro, "messages", None):
        return " ".join(str(mensagem) for mensagem in erro.messages)
    return str(erro)


def _gravar_caixas(request, filial: Filial) -> None:
    """O que as caixas dos módulos de negócio receberam no POST. Dentro do
    mesmo `atomic` da filial: a `ValidationError` de uma delas desfaz o
    formulário inteiro, e a tela mostra a frase."""
    for caixa in caixas():
        caixa.gravar(request, filial)


def _voltar(request, empresa) -> HttpResponseRedirect:
    """A volta para a tela, mantendo a empresa escolhida.

    Sem isto, criar a filial da segunda empresa devolvia a lista da PRIMEIRA e
    a filial nova não aparecia — quem cadastrou criaria de novo, achando que
    não gravou.
    """
    dona = empresa_atual(request)
    if empresa is not None and (dona is None or empresa.pk != dona.pk):
        return HttpResponseRedirect(f"{reverse('filiais')}?empresa={empresa.pk}")
    return HttpResponseRedirect(reverse("filiais"))


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
    # A filial nasce na empresa ESCOLHIDA na tela, que é a do cabeçalho quando
    # ninguém escolheu nada — nunca sem empresa, que era o que acontecia até
    # 14/09/2026 e fazia a filial nova não pertencer a ninguém.
    empresa = empresa_do_pedido(request)
    if empresa is None:
        return _desenhar(
            request, erro=_("Escolha uma empresa no cabeçalho antes de criar "
                            "uma filial."))
    dados["empresa"] = empresa
    # `atomic()`: se `registrar` falhar, a filial recém-criada desfaz
    # junto — nunca uma filial criada sem ninguém saber quem criou.
    try:
        with transaction.atomic():
            filial = Filial.objects.create(**dados)
            _gravar_caixas(request, filial)
            registrar(ACOES.FILIAL_CRIADA, request.usuario, alvo=str(filial),
                      request=request)
    except ValidationError as recusa:
        return _desenhar(request, erro=_frase_da_recusa(recusa))
    return _voltar(request, empresa)


def _acao_salvar(request, filial) -> HttpResponse:
    dados = {nome: request.POST.get(nome, "").strip() for nome, _resto, _resto in CAMPOS}
    erro = _validar(dados)
    if erro:
        return _desenhar(request, erro=erro)
    try:
        with transaction.atomic():
            for nome, valor in dados.items():
                setattr(filial, nome, valor)
            filial.save(update_fields=[nome for nome, _resto, _resto in CAMPOS])
            _gravar_caixas(request, filial)
            registrar(ACOES.FILIAL_EDITADA, request.usuario, alvo=str(filial),
                      request=request)
    except ValidationError as recusa:
        return _desenhar(request, erro=_frase_da_recusa(recusa))
    return _voltar(request, empresa_do_pedido(request))


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
            # recusa pelo que está acontecendo na filial (no Fila Zero, a fila
            # tranca a mesma linha para bater o ponto) não pode ver "ninguém"
            # e, no instante seguinte, alguém entrar na loja que vai ser
            # desativada.
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
    return _voltar(request, empresa_do_pedido(request))


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
    return _voltar(request, empresa_do_pedido(request))


ACOES_SEM_FILIAL = {"criar": _acao_criar}

ACOES_COM_FILIAL = {
    "salvar": _acao_salvar,
    "ativar": _acao_ativar,
    "desativar": _acao_desativar,
    "remover": _acao_remover,
}


#: As ações que pedem `filiais.editar`. Ativar e desativar pedem só a
#: permissão da tela, `filiais.ativar` (25/09/2026).
_SO_QUEM_EDITA = {"criar", "salvar", "remover"}


@exigir_permissao("filiais.ativar")
@exigir_modulo_ligado("filiais")
def filiais(request) -> HttpResponse:
    """A tela de Filiais: uma rota, um `acao` no corpo do POST decide o quê."""
    if request.method != "POST":
        # A exportação roda aqui dentro, depois dos guardas.
        if request.GET.get("formato"):
            exportacao = preparar_exportacao(
                request, queryset=filiais_da_empresa(request, empresa_do_pedido(request)),
                colunas=COLUNAS_DE_EXPORTACAO,
                ordenaveis=ORDENAVEIS, padrao="filial",
                filtraveis=FILTRAVEIS, titulo=_("Filiais"))
            if exportacao is not None:
                return exportacao
        return _desenhar(request)

    acao = request.POST.get("acao", "")
    if acao in _SO_QUEM_EDITA and not _pode_editar(request):
        # A mesma resposta da barreira para o que não se pode: não existe.
        return HttpResponseNotFound()

    sem_filial = ACOES_SEM_FILIAL.get(acao)
    if sem_filial is not None:
        return sem_filial(request)

    com_filial = ACOES_COM_FILIAL.get(acao)
    if com_filial is None:
        return HttpResponseRedirect(reverse("filiais"))

    # A partir daqui toda ação mexe numa filial JÁ existente.
    filial = filiais_da_empresa(request, empresa_do_pedido(request)).filter(
        pk=id_do_post(request, "filial")).first()
    if filial is None:
        return _desenhar(request, erro=_("Filial não encontrada."))


    return com_filial(request, filial)
