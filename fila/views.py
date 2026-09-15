"""As telas da fila."""

from __future__ import annotations

from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import PageHeader
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.site import montar_site

__all__ = ["fila"]


# Provisória: a rota do `ModuloSpec` precisa existir e estar guardada desde
# que o módulo é declarado (`tests/test_rota_do_modulo_bate_com_url.py` e
# `tests/test_guarda_modulo.py`). A página de verdade chega na Task 6 do plano.
@exigir_permissao("fila.ver")
@exigir_modulo_ligado("fila")
def fila(request) -> HttpResponse:
    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        pagina = site.page(
            title=_("Fila da vez"),
            content=[aviso_de_personificacao(request),
                     PageHeader(title=_("Fila da vez"))],
            user=getattr(request, "usuario", None),
        )
        return render(pagina)
