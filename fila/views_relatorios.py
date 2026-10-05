"""A tela dos relatórios (28/09/2026, spec 2026-09-28-relatorios-da-fila).

Escolhe o período, a loja e a empresa, e devolve a tela ou o arquivo pelo
`?formato=` (os de `comum.exportacao.FORMATOS`). O recorte sai da MESMA porta
do painel (`views_indicadores.escolha_do_pedido`): o dono vê todas as lojas,
o supervisor as da empresa dele e o gerente as dele, e a `?loja=` forjada cai
dentro do alcance.
"""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.components import Alert, Card, PageHeader, Raw
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual
from plataforma.marca import logo_da_empresa_de

from . import indicadores as ind
from . import relatorio_midias as por_midia
from .estado import nome_de
from .relatorio import PADRAO, PERIODOS, montar, periodo_escolhido
from .relatorio_saida import em_impressao, em_xlsx
from .views_indicadores import TODAS, escolha_do_pedido

__all__ = ["relatorios", "relatorios_gerais", "relatorios_midias"]


def _opcoes(pares, escolhido) -> str:
    return format_html_join("", '<option value="{}"{}>{}</option>', (
        (valor, format_html(" selected") if str(valor) == str(escolhido) else "", rotulo)
        for valor, rotulo in pares))


def _formulario(acao, chave, escolha, empresas_alcancadas) -> str:
    """Sem JavaScript: um GET com os campos e o "Filtrar", que manda `ver=1` —
    é ele que faz o relatório aparecer embaixo (05/10/2026). O PDF e o Excel
    saíram daqui: ficam em cima do relatório, depois de a pessoa vê-lo."""
    campos = [format_html(
        '<label class="f"><span class="lbl">{}</span><select class="ctl" name="periodo">{}</select></label>',
        _("Período"), _opcoes(PERIODOS, chave))]
    if len(empresas_alcancadas) > 1:
        campos.append(format_html(
            '<label class="f"><span class="lbl">{}</span><select class="ctl" name="empresa">{}</select></label>',
            _("Empresa"), _opcoes([(TODAS, _("Todas as empresas"))]
                                  + [(e.pk, str(e)) for e in empresas_alcancadas],
                                  escolha.escolhida.pk if escolha.escolhida else TODAS)))
    if len(escolha.permitidas) > 1:
        campos.append(format_html(
            '<label class="f"><span class="lbl">{}</span><select class="ctl" name="loja">{}</select></label>',
            _("Loja"), _opcoes([(TODAS, _("Todas as lojas"))]
                               + [(l.pk, str(l)) for l in escolha.permitidas],
                               escolha.loja.pk if escolha.loja else TODAS)))
    return format_html(
        '<form method="get" action="{}" class="relatorio-form">{}'
        '<div class="relatorio-botoes">'
        '<button class="btn primary" type="submit" name="ver" value="1">{}</button>'
        '</div></form>',
        acao, format_html_join("", "{}", ((c,) for c in campos)), _("Filtrar"))


def _previa(acao, consulta: str) -> str:
    """O relatório filtrado, embaixo do filtro, e os dois botões em cima dele
    (05/10/2026, o cliente: "eu escolho o filtro e clico em filtrar, o
    relatório aparece em HTML primeiro embaixo do filtro para o cara ver,
    passar o mouse, ver os dados; daí, se ele quiser, vai ter os dois botões
    gerar PDF e Excel em cima").

    O relatório vem num QUADRO (`<iframe>`), e não costurado na página: é a
    MESMA página do PDF, só sem chamar a impressão (`formato=previa`) — o que
    a pessoa vê é o que vai para o papel, e as folhas do relatório (o `@page`,
    o `body.relatorio`) não se misturam com as da tela do sistema. A altura
    do quadro segue o conteúdo pelo `relatorio_previa.js`; sem ele, o quadro
    tem altura fixa e rola por dentro."""
    def endereco(formato):
        return f"{acao}?{consulta}&formato={formato}" if consulta else f"{acao}?formato={formato}"

    return format_html(
        '<section class="relatorio-previa">'
        '<div class="relatorio-acoes">'
        '<a class="btn primary" href="{}" target="_blank" rel="noopener">{}</a>'
        '<a class="btn" href="{}">{}</a>'
        '</div>'
        '<iframe class="relatorio-quadro" src="{}" title="{}"></iframe>'
        '</section>',
        endereco("impressao"), _("Gerar PDF"), endereco("xlsx"), _("Gerar Excel"),
        endereco("previa"), _("Prévia do relatório"))


#: Os dois relatórios da tela (28/09/2026, pedido do cliente: "tirar o menu
#: relatório de dentro do subnível, e colocar ele no nível 1, com subníveis de
#: relatórios por mídia e relatórios gerais"). Os dois têm os mesmos filtros e
#: o mesmo alcance; muda só o que sai no PDF e no Excel. O "gerais" é o
#: relatório visual, que tinha saído da tela quando o de mídias entrou.
_TIPOS = {
    "midias": {"titulo": _l("Relatórios por mídia"), "rota": "fila_relatorios_midias",
               "apoio": _l("Atendimentos, vendas e aproveitamento de cada loja, "
                           "por mídia, em PDF ou Excel.")},
    "gerais": {"titulo": _l("Relatórios gerais"), "rota": "fila_relatorios_gerais",
               "apoio": _l("Os números das lojas que você acompanha, em PDF ou Excel.")},
}


def _gerar(request, tipo, escolha, rotulo, pessoa, formato) -> HttpResponse:
    resposta = _arquivo(request, tipo, escolha, rotulo, pessoa, formato)
    if formato == "previa":
        # O middleware nega toda página dentro de quadro (DENY, contra quem
        # tentasse vestir a nossa num site de fora); a prévia é a única que a
        # própria casa põe num quadro, e só na mesma origem.
        resposta["X-Frame-Options"] = "SAMEORIGIN"
    return resposta


def _arquivo(request, tipo, escolha, rotulo, pessoa, formato) -> HttpResponse:
    # O topo da moldura mostra o filtro de loja como a pessoa o escolheu:
    # "Todas as lojas" quando ela podia escolher entre várias e não escolheu;
    # com uma loja só no alcance não houve escolha, e vale o nome dela.
    moldura = {"com_logo": logo_da_empresa_de(request) is not None,
               "lojas": (str(escolha.loja) if escolha.loja
                         else _("Todas as lojas") if len(escolha.permitidas) > 1 else None),
               # A prévia é a página do PDF sem chamar a impressão.
               "imprimir": formato != "previa"}
    if tipo == "midias":
        relatorio = por_midia.montar(escolha.recorte, rotulo_da_empresa=rotulo,
                                     gerado_por=nome_de(pessoa))
        return (por_midia.em_xlsx(relatorio) if formato == "xlsx"
                else por_midia.em_impressao(relatorio, **moldura))
    relatorio = montar(escolha.recorte, rotulo_da_empresa=rotulo, gerado_por=nome_de(pessoa))
    return em_xlsx(relatorio) if formato == "xlsx" else em_impressao(relatorio, **moldura)


def _tela(request, tipo: str) -> HttpResponse:
    from plataforma.site import montar_site

    pessoa = usuario_de(request.usuario)
    empresa = empresa_atual(request)
    chave = request.GET.get("periodo") if request.GET.get("periodo") in dict(PERIODOS) else PADRAO
    periodo = periodo_escolhido(chave)
    permitidas = ind.lojas_com_relatorio(pessoa, empresa)
    formato = request.GET.get("formato")
    escolha = escolha_do_pedido(request, empresa, permitidas, periodo) if permitidas else None

    if escolha is not None and escolha.lojas and formato in ("xlsx", "impressao", "previa"):
        rotulo = str(escolha.empresa) if escolha.escolhida else _("Todas as empresas")
        return _gerar(request, tipo, escolha, rotulo, pessoa, formato)

    info = _TIPOS[tipo]
    with use_environment(ambiente()):
        site = montar_site(request)
        acao = reverse(info["rota"])
        if escolha is None or not escolha.lojas:
            corpo = [Alert(tone="info", message=_("Nenhuma loja em que você tira relatório."))]
        else:
            corpo = [Card(body=Raw(html=_formulario(acao, chave, escolha,
                                                    ind.empresas_com_relatorio(pessoa))))]
            if request.GET.get("ver"):
                # Os filtros que a pessoa escolheu viajam para o quadro e para
                # os dois botões; o `ver` e o `formato` são da tela, não deles.
                consulta = request.GET.copy()
                consulta.pop("ver", None)
                consulta.pop("formato", None)
                corpo.append(Raw(html=_previa(acao, consulta.urlencode())))
        pagina = site.page(
            title=str(info["titulo"]), width="full",
            stylesheets=["/static/fila/relatorio.css"],
            scripts=["/static/fila/relatorio_previa.js"],
            content=[aviso_de_personificacao(request),
                     PageHeader(title=str(info["titulo"]), subtitle=str(info["apoio"])),
                     *corpo],
            # Um pedaço só: "Relatórios / Relatórios gerais" repetia a palavra
            # e não cabia na faixa do cabeçalho (saía "Rel… / Relatór…").
            crumbs=[Crumb(str(info["titulo"]))], user=request.usuario)
        return render(pagina)


@exigir_permissao("fila.relatorios")
@exigir_modulo_ligado("fila")
def relatorios_midias(request) -> HttpResponse:
    return _tela(request, "midias")


@exigir_permissao("fila.relatorios")
@exigir_modulo_ligado("fila")
def relatorios_gerais(request) -> HttpResponse:
    return _tela(request, "gerais")


@exigir_permissao("fila.relatorios")
@exigir_modulo_ligado("fila")
def relatorios(request) -> HttpResponse:
    """`/fila/relatorios` era a tela única até o menu ganhar os dois
    relatórios: o link salvo cai no de mídias — o que ela gerava por último —,
    com os mesmos filtros."""
    destino = reverse("fila_relatorios_midias")
    consulta = request.GET.urlencode()
    return HttpResponseRedirect(f"{destino}?{consulta}" if consulta else destino)
