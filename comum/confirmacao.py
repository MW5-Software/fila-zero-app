"""Uma pergunta antes de agir — para toda ação que só pode rodar por POST.

`contas.views.sair` e `plataforma.views_filial.filial_trocar` têm a mesma
forma: a ação de verdade só acontece em POST (um `<img src="...">` numa
página qualquer não pode nem derrubar sessão, nem trocar o contexto de
quem a abriu). Mas nem todo jeito de chegar até a rota é um clique num
`<button type="submit">` — o próprio cabeçalho do design system ainda
desenha "Sair" como `<a href="/sair">` (`nucleo/templates/layout/
header.html`, port congelado), e é assim que alguém sem JavaScript, ou
clicando esse link puro, chega em GET. Até esta correção, GET nas duas
respondia 405 e a ação não acontecia por essa porta nenhuma — "Sair" pelo
cabeçalho estava, na prática, quebrado.

A saída não é aceitar GET como a ação de verdade (isso reabriria o mesmo
`<img src="...">` que o POST-only existe para fechar): é GET perguntar, e
só o clique num botão de verdade — que só existe dentro de um `<form
method="post">` — disparar o POST que já fazia tudo. Esta tela é esse
"tem certeza?", compartilhada pelas duas rotas para não virar duas cópias
do mesmo formulário.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from nucleo.components import Button, Card, Form, Raw
from nucleo.layout import Page
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render

from comum.csrf import campo_csrf

__all__ = ["tela_de_confirmacao"]


def _campo_oculto(nome: str, valor: str) -> str:
    """Um `<input type="hidden">` cru, no mesmo estilo de `campo_csrf`
    (`contas/csrf.py`): estas telas não emitem formulário via nenhum
    `ModelForm`, então cada campo extra que precisa viajar escondido no
    POST — a filial escolhida, por exemplo — é montado à mão, e não
    reimplementado a cada chamador."""
    return format_html('<input type="hidden" name="{}" value="{}">', nome, valor)


def tela_de_confirmacao(
    request,
    *,
    titulo: str,
    pergunta: str,
    rotulo_botao: str,
    action: str,
    voltar_href: str = "/",
    campos_ocultos: "dict[str, str] | None" = None,
) -> HttpResponse:
    """Um `Card` com um `Form` de um botão só: a pergunta no título, o
    campo de CSRF (mais os `campos_ocultos` que o chamador precisar — a
    filial escolhida, por exemplo, para `filial_trocar` saber qual é ao
    receber o POST desta mesma tela), o botão que confirma (POST) e um
    link de volta.

    Sem `Site`/menu/cabeçalho, de propósito — a mesma razão de `LoginPage`
    (`contas/views.py::_desenhar`) ser a única outra tela sem esse shell:
    `sair` roda mesmo com sessão quebrada ou inexistente
    (`comum.guardas_de_acesso.TELAS_ABERTAS` já documenta isso), e uma tela que
    dependesse de `request.usuario` para montar o menu quebraria
    justamente no caso em que mais precisa funcionar.
    """
    from plataforma.marca import marca_da_instalacao

    campos: list = [Raw(html=campo_csrf(request))]
    for nome, valor in (campos_ocultos or {}).items():
        campos.append(Raw(html=_campo_oculto(nome, valor)))

    env = ambiente()
    with use_environment(env):
        conteudo = Card(
            title=pergunta,
            body=Form(action=action, children=[
                *campos,
                Button(label=rotulo_botao, variant="primary", type="submit"),
                Button(label=_("Cancelar"), href=voltar_href),
            ]),
        )
        pagina = Page(
            brand=marca_da_instalacao(),
            title=titulo,
            content=conteudo,
            width="narrow",
            theme_href="/tema.css",
        )
        return render(pagina)
