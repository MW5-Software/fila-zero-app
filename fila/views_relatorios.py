"""A tela dos relatórios (28/09/2026, spec 2026-09-28-relatorios-da-fila).

Escolhe o período, a loja e a empresa, e devolve a tela ou o arquivo pelo
`?formato=` (os de `comum.exportacao.FORMATOS`). O recorte sai da MESMA porta
do painel (`views_indicadores.escolha_do_pedido`): o dono vê todas as lojas,
o supervisor as da empresa dele e o gerente as dele, e a `?loja=` forjada cai
dentro do alcance.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _

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

from . import indicadores as ind
from .estado import nome_de
from .relatorio import PADRAO, PERIODOS, montar, periodo_escolhido
from .relatorio_saida import em_impressao, em_xlsx
from .views_indicadores import TODAS, escolha_do_pedido

__all__ = ["relatorios"]


def _opcoes(pares, escolhido) -> str:
    return format_html_join("", '<option value="{}"{}>{}</option>', (
        (valor, format_html(" selected") if str(valor) == str(escolhido) else "", rotulo)
        for valor, rotulo in pares))


def _formulario(chave, escolha, empresas_alcancadas) -> str:
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
        reverse("fila_relatorios"), format_html_join("", "{}", ((c,) for c in campos)),
        _("Gerar PDF"), _("Gerar Excel"))


@exigir_permissao("fila.relatorios")
@exigir_modulo_ligado("fila")
def relatorios(request) -> HttpResponse:
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
        relatorio = montar(escolha.recorte, rotulo_da_empresa=rotulo,
                           gerado_por=nome_de(pessoa))
        return em_xlsx(relatorio) if formato == "xlsx" else em_impressao(relatorio)

    with use_environment(ambiente()):
        site = montar_site(request)
        corpo = (Alert(tone="info", message=_("Nenhuma loja em que você tira relatório."))
                 if escolha is None or not escolha.lojas else
                 Card(body=Raw(html=_formulario(chave, escolha,
                                                ind.empresas_com_relatorio(pessoa)))))
        pagina = site.page(
            title=_("Relatórios"), width="full",
            stylesheets=["/static/fila/relatorio.css"],
            content=[aviso_de_personificacao(request),
                     PageHeader(title=_("Relatórios"),
                                subtitle=_("Os números das lojas que você acompanha, "
                                           "em PDF ou Excel.")),
                     corpo],
            crumbs=[Crumb(_("Relatórios"))], user=request.usuario)
        return render(pagina)
