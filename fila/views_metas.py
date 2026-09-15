"""A tela das metas de venda (spec 2026-09-15-fila-metas, "Cadastro").

Um formulário de campos, e não uma tabela: cada linha é um valor do mesmo
formulário, e uma loja tem dezenas de pessoas, não milhares (a R46 vale para
tabela que lista registros). As regras moram em `fila/metas.py`; aqui só se
desenha e se lê o POST.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _

from comum.ambiente import ambiente
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.pedido import id_do_post, inteiro_do_texto
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.components import (Alert, Box, Button, Card, Cell, Form, FormGrid,
                               Option, PageHeader, Raw, Select, TextInput)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from . import metas as regras
from .acoes import Recusa
from .estado import nome_de
from .valores import em_reais

__all__ = ["metas"]


def _loja_escolhida(request, permitidas):
    """A loja do pedido, só entre as permitidas; a forjada cai na primeira."""
    # A mesma regra do id do POST para a URL: "²" e número gigante viram
    # "nenhuma", e a tela cai na primeira loja em vez de 500.
    pk = (id_do_post(request, "loja") if request.method == "POST"
          else inteiro_do_texto(request.GET.get("loja", "")))
    return next((l for l in permitidas if l.pk == pk), permitidas[0])


def _endereco(mes, loja) -> str:
    return reverse("fila_metas") + "?" + urlencode({"mes": f"{mes:%Y-%m}", "loja": loja.pk})


def _escolha(mes, loja, permitidas):
    anterior, seguinte = regras.mes_anterior(mes), regras.mes_seguinte(mes)
    campos = [
        TextInput(name="mes", label=_("Mês"), type="month", span=3,
                  value=f"{mes:%Y-%m}"),
    ]
    if len(permitidas) > 1:
        campos.append(Select(name="loja", label=_("Loja"), span=4, value=str(loja.pk),
                             options=[Option(str(l.pk), str(l)) for l in permitidas]))
    else:
        campos.append(Raw(html=format_html('<input type="hidden" name="loja" value="{}">', loja.pk)))
    # Os botões numa célula própria: soltos na grade, cada um ocupava uma
    # linha e a escolha virava uma coluna de botões.
    campos.append(Cell(span=5, children=Box(direction="row", gap="sm", body=[
        Button(label=_("Abrir"), variant="primary", type="submit"),
        Button(label=_("Mês anterior"), icon="chevron-left",
               href=_endereco(anterior, loja)),
        Button(label=_("Mês seguinte"), icon_right="chevron-right",
               href=_endereco(seguinte, loja)),
    ])))
    return Card(attrs={"data-metas": "escolha"},
                body=Form(method="get", action=reverse("fila_metas"),
                          children=FormGrid(children=campos)))


def _campo(nome, rotulo, valor, *, erro=None, travado=False, ajuda=None):
    return TextInput(name=nome, label=rotulo, value=valor, span=4, error=erro,
                     disabled=travado, help=ajuda, placeholder=_("Sem meta"),
                     attrs={"inputmode": "decimal", "autocomplete": "off"})


def _desenhar(request, loja, mes, permitidas, editor, *, digitados=None,
              erros=None, aviso=None) -> HttpResponse:
    from plataforma.site import montar_site

    digitados, erros = digitados or {}, erros or {}
    encerrado = regras.mes_encerrado(mes)
    linhas = regras.pessoas_da_lista(loja, mes, editor)
    da_loja = regras.meta_da_loja(loja, mes)
    soma = sum((l.valor for l in linhas if l.valor is not None), regras.ZERO)

    def valor(chave, salvo):
        return digitados.get(chave, regras.valor_do_campo(salvo))

    subtitulo = (_("Vendedores somam %(soma)s de %(loja)s")
                 % {"soma": em_reais(soma), "loja": em_reais(da_loja)}
                 if da_loja is not None else None)
    pessoas = []
    for l in linhas:
        ajuda = None
        if l.propria:
            ajuda = _("A sua meta é definida por outra pessoa.")
        elif not l.na_loja:
            ajuda = _("Não está mais nesta loja.")
        pessoas.append(_campo(f"valor_{l.pessoa.pk}", nome_de(l.pessoa),
                              valor(str(l.pessoa.pk), l.valor),
                              erro=erros.get(str(l.pessoa.pk)),
                              travado=encerrado or l.propria, ajuda=ajuda))

    corpo = [
        Raw(html=campo_csrf(request)),
        Raw(html=format_html('<input type="hidden" name="mes" value="{}">'
                             '<input type="hidden" name="loja" value="{}">',
                             f"{mes:%Y-%m}", loja.pk)),
        Card(title=_("Meta da loja"), subtitle=subtitulo, body=FormGrid(children=[
            _campo("valor_loja", str(loja), valor("loja", da_loja),
                   erro=erros.get("loja"), travado=encerrado)])),
        Card(title=_("Metas dos vendedores"),
             body=FormGrid(children=pessoas) if pessoas else Raw(html=format_html(
                 '<p class="ind-vazio">{}</p>', _("Ninguém participa da fila nesta loja.")))),
    ]
    if not encerrado:
        corpo.append(Box(direction="row", gap="sm", body=[
            Button(label=_("Salvar metas"), variant="primary", type="submit",
                   attrs={"name": "acao", "value": "salvar"}),
            Button(label=_("Copiar metas do mês anterior"), type="submit",
                   attrs={"name": "acao", "value": "copiar"}),
        ]))

    conteudo = [
        aviso_de_personificacao(request),
        PageHeader(title=_("Metas de venda"),
                   subtitle=_("Quanto cada loja e cada vendedor deve vender no mês.")),
        _escolha(mes, loja, permitidas),
    ]
    if encerrado:
        conteudo.append(Alert(tone="info", message=str(regras.MES_ENCERRADO)))
    if aviso:
        conteudo.append(aviso)
    conteudo.append(Form(method="post", action=reverse("fila_metas"), children=corpo))

    with use_environment(ambiente()):
        site = montar_site(request)
        pagina = site.page(title=_("Metas de venda"), width="full",
                           stylesheets=["/static/fila/indicadores.css"],
                           content=conteudo, crumbs=[Crumb(_("Metas de venda"))],
                           user=request.usuario)
        return render(pagina)


@exigir_permissao("fila.metas")
@exigir_modulo_ligado("fila")
def metas(request) -> HttpResponse:
    editor = usuario_de(request.usuario)
    empresa = empresa_atual(request)
    permitidas = regras.lojas_com_metas(editor, empresa)
    if not permitidas:
        return _desenhar_sem_loja(request)
    loja = _loja_escolhida(request, permitidas)
    dados = request.POST if request.method == "POST" else request.GET
    mes = regras.mes_do_texto(dados.get("mes"))

    if request.method != "POST":
        return _desenhar(request, loja, mes, permitidas, editor)

    linhas = regras.pessoas_da_lista(loja, mes, editor)
    if request.POST.get("acao") == "copiar":
        copia = regras.copiar_do_anterior(loja, mes, linhas)
        aviso = Alert(tone="info", message=(
            _("Metas do mês anterior copiadas nos campos vazios. Confira e salve.")
            if copia else _("O mês anterior não tem meta para copiar.")))
        return _desenhar(request, loja, mes, permitidas, editor,
                         digitados=copia, aviso=aviso)

    chaves = ["loja", *(str(l.pessoa.pk) for l in linhas)]
    campos = {"loja": "valor_loja", **{str(l.pessoa.pk): f"valor_{l.pessoa.pk}"
                                       for l in linhas}}
    valores = {c: request.POST.get(campos[c]) for c in chaves}
    try:
        regras.gravar(loja, mes, editor, valores, request=request)
    except Recusa as recusa:
        return _desenhar(request, loja, mes, permitidas, editor,
                         aviso=Alert(tone="danger", message=str(recusa)))
    except regras.ValoresInvalidos as invalidos:
        digitados = {c: v for c, v in valores.items() if v is not None}
        return _desenhar(request, loja, mes, permitidas, editor,
                         digitados=digitados, erros=invalidos.erros,
                         aviso=Alert(tone="danger",
                                     message=_("Corrija os valores marcados. Nada foi salvo.")))
    return HttpResponseRedirect(_endereco(mes, loja))


def _desenhar_sem_loja(request) -> HttpResponse:
    from plataforma.site import montar_site

    with use_environment(ambiente()):
        site = montar_site(request)
        pagina = site.page(title=_("Metas de venda"), width="full", content=[
            aviso_de_personificacao(request),
            PageHeader(title=_("Metas de venda")),
            Alert(tone="info", message=_("Nenhuma loja em que você define metas.")),
        ], crumbs=[Crumb(_("Metas de venda"))], user=request.usuario)
        return render(pagina)
