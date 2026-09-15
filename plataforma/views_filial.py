"""A troca de filial no cabeçalho."""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from comum.auditoria import ACOES, registrar
from comum.confirmacao import tela_de_confirmacao
from comum.guardas_de_acesso import exigir_login

from .contexto import CHAVE, escolher, filial_permitida

__all__ = ["filial_trocar"]


@exigir_login
def filial_trocar(request) -> HttpResponse:
    """Troca a filial do contexto para o resto desta sessão.

    A ação de verdade só roda em POST — a mesma razão de `contas.views.sair`:
    um `<img src="/filial/trocar?filial=9">` em qualquer página não pode
    mudar o contexto de quem a abriu por baixo dela. A proteção contra CSRF
    de verdade (o token) é a mesma do resto do projeto — a
    `CsrfViewMiddleware` padrão do Django, ligada em `config/settings.py`;
    nenhuma view deste projeto marca `@csrf_exempt`, e esta também não.

    GET não é 405 sozinho: mostra a confirmação ("Trabalhar em <filial>?"),
    com um `<form method="post">` de verdade dentro que dispara a troca —
    ver `comum.confirmacao.tela_de_confirmacao`. O id vem de `?filial_id=`, e
    é validado por `filial_permitida` ANTES de aparecer na pergunta: a tela
    nunca nomeia uma filial que a pessoa não alcança.

    404 para um id que a pessoa não pode usar — mesmo vocabulário das outras
    guardas (`comum.guardas_de_acesso.exigir_permissao`,
    `comum.guardas_de_modulo.exigir_modulo_ligado`): quem não pode não precisa
    saber se o id existia, se era de outra instalação, ou se a filial estava
    desativada. Vale tanto para o GET (a confirmação) quanto para o POST (a
    troca de verdade).
    """
    if request.method == "GET":
        # `CHAVE`, a mesma constante do `name` do seletor do cabeçalho e da
        # sessão. Era `"filial"` escrito à mão, e o seletor manda `filial_id`:
        # o mesmo defeito que `empresa_trocar` já teve, com as duas pontas
        # testadas e verdes.
        filial = filial_permitida(request, request.GET.get(CHAVE, ""))
        if filial is None:
            return HttpResponseNotFound()
        return tela_de_confirmacao(
            request, titulo=_("Trocar filial"),
            pergunta=f"Trabalhar em {filial}?",
            rotulo_botao="Confirmar",
            action=reverse("filial_trocar"),
            campos_ocultos={CHAVE: str(filial.pk)},
        )
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])

    filial = escolher(request, request.POST.get(CHAVE, ""))
    if filial is None:
        return HttpResponseNotFound()

    registrar(ACOES.FILIAL_TROCADA, request.usuario, alvo=str(filial), request=request)
    return HttpResponseRedirect("/")
