"""A troca de empresa no cabeçalho.

Espelha `views_filial.filial_trocar`, e o espelho é deliberado: neste produto
a empresa é o contexto (ver `plataforma/contexto.py`), mas as regras de
segurança da troca são as mesmas, e reescrevê-las de outro jeito criaria duas
versões da mesma proteção — a segunda sempre com uma delas faltando.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.http import (
    HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from comum.auditoria import ACOES, registrar
from comum.confirmacao import tela_de_confirmacao
from comum.guardas_de_acesso import exigir_login

from .contexto import (
    CHAVE, CHAVE_EMPRESA, empresa_atual, empresa_permitida, escolher_empresa)

__all__ = ["empresa_trocar"]


@exigir_login
def empresa_trocar(request) -> HttpResponse:
    """Troca a empresa do contexto para o resto desta sessão.

    **POST para agir**, pela mesma razão de `contas.views.sair`: um
    `<img src="/empresa/trocar?empresa_id=9">` numa página qualquer não pode
    mudar o contexto de quem a abriu por baixo dela.

    GET não é 405: mostra a confirmação, com um `<form method="post">` de
    verdade dentro. O id vem de `?empresa_id=` e é validado ANTES de aparecer
    na pergunta — a tela nunca nomeia uma empresa que a pessoa não alcança, o
    que já seria contar que ela existe.

    **Um nome só, `CHAVE_EMPRESA`, nas duas pontas e nos dois métodos.** O
    seletor do cabeçalho é um `<form method="get">` cujo `<select>` se chama
    `CHAVE_EMPRESA` (ver `plataforma.site.construir_context_switcher`), então
    é esse o nome que chega aqui. Escrever o nome à mão de novo — era
    `"empresa"` — dava 404 em toda troca pelo cabeçalho, com as duas pontas
    testadas e verdes: o teste da emenda está em
    `tests/test_cabecalho_contexto.py`.

    **404 para id que a pessoa não alcança**, nunca 403 — mesmo vocabulário
    das outras guardas desta casa: quem não pode não precisa saber se o id
    existia, se era de outra empresa, ou se estava lá. Vale para o GET e para
    o POST.
    """
    if request.method == "GET":
        empresa = empresa_permitida(request, request.GET.get(CHAVE_EMPRESA, ""))
        if empresa is None:
            return HttpResponseNotFound()
        # O cabeçalho manda os dois selects para cá num formulário só
        # (`plataforma.site.construir_context_switcher`). Empresa igual à atual
        # com filial pedida é troca de FILIAL, e a confirmação dela mora lá —
        # que também é quem valida o id.
        filial_pedida = request.GET.get(CHAVE, "")
        if filial_pedida and empresa == empresa_atual(request):
            return HttpResponseRedirect(
                reverse("filial_trocar") + "?" + urlencode({CHAVE: filial_pedida}))
        return tela_de_confirmacao(
            request, titulo=_("Trocar empresa"),
            pergunta=f"Trabalhar em {empresa}?",
            rotulo_botao="Confirmar",
            action=reverse("empresa_trocar"),
            campos_ocultos={CHAVE_EMPRESA: str(empresa.pk)},
        )
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])

    empresa = escolher_empresa(request, request.POST.get(CHAVE_EMPRESA, ""))
    if empresa is None:
        return HttpResponseNotFound()

    registrar(ACOES.FILIAL_TROCADA, request.usuario,
              alvo=str(empresa), request=request)
    return HttpResponseRedirect("/")
