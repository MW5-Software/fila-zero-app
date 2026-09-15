"""A tela do módulo Exemplo.

Não faz nada de negócio — o módulo inteiro existe para provar o mecanismo da
matriz, do código até a tela (ver `tests/test_modulo_exemplo.py`).
"""

from __future__ import annotations

from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _

from comum.guardas_de_acesso import exigir_permissao
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import Card, PageHeader
from nucleo.layout import Crumb
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render
from comum.guardas_de_modulo import exigir_modulo_ligado
from plataforma.site import montar_site

__all__ = ["exemplo"]


# A ordem dos decoradores importa: `exigir_permissao` fica por fora, porque é
# ele quem cuida de sessão ausente (redireciona) e quem marca `exige_login`
# na view — o atributo que a varredura de `tests/test_guarda.py` exige em toda
# rota. `exigir_modulo_ligado` fica por dentro: só é alcançado depois que
# login e permissão já passaram, e tranca por conta própria quando o cliente
# não tem o módulo ligado — inclusive para o superusuário.
@exigir_permissao("exemplo.ver")
@exigir_modulo_ligado("exemplo")
def exemplo(request) -> HttpResponse:
    """A tela que prova que o módulo Exemplo está de pé nesta instalação."""
    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        pagina = site.page(
            # `full`: a tela usa a largura toda. Estas telas são tabela e
            # formulário — espremer uma tabela em 1400px num monitor largo
            # desperdiça a metade direita e ainda quebra coluna.
            title=_("Exemplo"),
            width="full",
            content=[
                aviso_de_personificacao(request),
                PageHeader(
                    title=_("Exemplo"),
                    subtitle=_("Esta tela só abre com o módulo ligado e a permissão exemplo.ver."),
                ),
                Card(
                    title=_("Está de pé"),
                    body="Declarado no código, semeado desligado, ligado na "
                         "tela de Módulos, e agora visível para quem tem "
                         "permissão — sem ninguém editar código.",
                ),
            ],
            crumbs=[Crumb(_("Exemplo"))],
            user=getattr(request, "usuario", None),
        )
        # A renderização precisa acontecer AQUI dentro do `with` — ver o
        # comentário equivalente em `plataforma/views.py`.
        return render(pagina)
