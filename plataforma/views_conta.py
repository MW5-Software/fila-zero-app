"""A tela de Conta (spec 2026-09-17, E4): o topo da hierarquia.

Conta → empresas → lojas. Ela responde "o que é esta conta e o que tem dentro
dela": o titular (que É a conta), as empresas e as lojas de cada uma.

**É leitura.** Quem cadastra empresa é a MW5, na tela de Empresas, e quem
cadastra loja é o titular, na tela de Lojas. Um segundo caminho para o mesmo
cadastro diverge no primeiro campo novo — foi o motivo de "Nova empresa" ter
saído e voltado num lugar só.

A conta mostrada é a da EMPRESA DO CABEÇALHO: para o titular é a dele, e para
a MW5 é a do cliente que ela está olhando. Assim a tela não precisa de um
seletor próprio, que seria um segundo lugar para escolher a mesma coisa.
"""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseNotFound
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import Alert, Card, Cell, FormGrid, PageHeader, Raw
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render

from .contexto import _e_da_mw5, empresa_atual

__all__ = ["conta"]


def _titular_da_conta(request):
    """O titular da conta que esta sessão está olhando, pela empresa do
    cabeçalho. `None` quando não há empresa (a MW5 sem cliente escolhido, ou
    a conta que ficou sem empresa)."""
    empresa = empresa_atual(request)
    return getattr(empresa, "dono", None)


def _quadro(rotulo, valor) -> Cell:
    return Cell(span=3, children=Raw(html=format_html(
        '<div class="conta-quadro"><span>{}</span><strong>{}</strong></div>',
        rotulo, valor)))


def _empresas_e_lojas(titular):
    """Uma linha por empresa, com as lojas ativas dela embaixo.

    Lista, e não `<table>`: são poucas linhas, sem filtro nem página que
    façam sentido (R46 vale para tabela que lista registros), e o que
    interessa é a hierarquia — a loja aparece dentro da empresa a que
    pertence.
    """
    from .models import Empresa, Filial

    empresas = list(Empresa.objects.filter(dono=titular).order_by("razao_social"))
    lojas: dict = {}
    for filial in (Filial.objects.filter(empresa__in=empresas, ativa=True)
                   .order_by("-e_matriz", "apelido")):
        lojas.setdefault(filial.empresa_id, []).append(filial)
    itens = format_html_join("", (
        '<li><div class="conta-empresa"><strong>{}</strong><span>{}</span></div>'
        '<div class="conta-lojas">{}</div></li>'), (
        (str(e), e.cnpj or _("sem CNPJ"),
         format_html_join(", ", "{}", ((str(f),) for f in lojas.get(e.pk, [])))
         or _("sem loja cadastrada"))
        for e in empresas))
    return empresas, Raw(html=format_html('<ol class="conta-lista">{}</ol>', itens))


@exigir_permissao("conta.ver")
@exigir_modulo_ligado("conta")
def conta(request) -> HttpResponse:
    from contas.models import Usuario

    from .site import montar_site

    titular = _titular_da_conta(request)
    # 404, e não 403, como toda tela que a pessoa não alcança: quem não pode
    # não precisa saber que ela existe. O membro nunca chega aqui porque a
    # permissão é do titular; a MW5 chega pela empresa que está olhando.
    if titular is None and not _e_da_mw5(getattr(request, "usuario", None)):
        return HttpResponseNotFound()

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=_("Conta"),
                       subtitle=_("O cliente, as empresas dele e as lojas de "
                                  "cada uma.")),
        ]
        if titular is None:
            conteudo.append(Alert(tone="info", message=_(
                "Escolha uma empresa no cabeçalho para ver a conta dela.")))
        else:
            empresas, lista = _empresas_e_lojas(titular)
            pessoas = Usuario.objects.filter(conta_id=titular.guid,
                                             is_active=True).count()
            conteudo += [
                Card(title=_("Quem é a conta"), body=FormGrid(children=[
                    _quadro(_("Titular"), titular.nome or titular.email),
                    _quadro(_("E-mail"), titular.email),
                    _quadro(ngettext("Empresa", "Empresas", len(empresas)),
                            len(empresas)),
                    _quadro(ngettext("Pessoa", "Pessoas", pessoas), pessoas),
                ])),
                Card(title=_("Empresas e lojas"), body=lista),
            ]
        pagina = site.page(
            title=_("Conta"), width="full",
            stylesheets=["/static/plataforma/conta.css"],
            content=conteudo, crumbs=[Crumb(_("Conta"))],
            user=getattr(request, "usuario", None))
        return render(pagina)
