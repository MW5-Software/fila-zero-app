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
    """Sem JavaScript: um GET com os campos e dois botões que mandam o
    `formato`. O PDF abre noutra aba, para a tela continuar ali."""
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
        '<button class="btn primary" type="submit" name="formato" value="impressao" formtarget="_blank">{}</button>'
        '<button class="btn" type="submit" name="formato" value="xlsx">{}</button>'
        '</div></form>',
        acao, format_html_join("", "{}", ((c,) for c in campos)),
        _("Gerar PDF"), _("Gerar Excel"))


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
    if tipo == "midias":
        relatorio = por_midia.montar(escolha.recorte, rotulo_da_empresa=rotulo,
                                     gerado_por=nome_de(pessoa))
        return (por_midia.em_xlsx(relatorio) if formato == "xlsx"
                else por_midia.em_impressao(relatorio))
    relatorio = montar(escolha.recorte, rotulo_da_empresa=rotulo, gerado_por=nome_de(pessoa))
    return em_xlsx(relatorio) if formato == "xlsx" else em_impressao(
        relatorio, com_logo=logo_da_empresa_de(request) is not None)


def _tela(request, tipo: str) -> HttpResponse:
    from plataforma.site import montar_site

    pessoa = usuario_de(request.usuario)
    empresa = empresa_atual(request)
    chave = request.GET.get("periodo") if request.GET.get("periodo") in dict(PERIODOS) else PADRAO
    periodo = periodo_escolhido(chave)
    permitidas = ind.lojas_com_relatorio(pessoa, empresa)
    formato = request.GET.get("formato")
    escolha = escolha_do_pedido(request, empresa, permitidas, periodo) if permitidas else None

    if escolha is not None and escolha.lojas and formato in ("xlsx", "impressao"):
        rotulo = str(escolha.empresa) if escolha.escolhida else _("Todas as empresas")
        return _gerar(request, tipo, escolha, rotulo, pessoa, formato)

    info = _TIPOS[tipo]
    with use_environment(ambiente()):
        site = montar_site(request)
        corpo = (Alert(tone="info", message=_("Nenhuma loja em que você tira relatório."))
                 if escolha is None or not escolha.lojas else
                 Card(body=Raw(html=_formulario(reverse(info["rota"]), chave, escolha,
                                                ind.empresas_com_relatorio(pessoa)))))
        pagina = site.page(
            title=str(info["titulo"]), width="full",
            stylesheets=["/static/fila/relatorio.css"],
            content=[aviso_de_personificacao(request),
                     PageHeader(title=str(info["titulo"]), subtitle=str(info["apoio"])),
                     corpo],
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
