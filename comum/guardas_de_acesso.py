"""As guardas de rota.

Esconder um item do menu **não** é controle de acesso: quem digitar o
endereço na barra do navegador tem que bater numa porta trancada. Estas duas
guardas são essa porta, e o teste de varredura em `tests/test_guarda.py` é o
que impede alguém de criar uma tela e esquecer de pô-la.
"""

from __future__ import annotations

from functools import wraps

from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.urls import reverse

from nucleo.permissoes import pode

from comum.sessao import usuario_da_sessao

__all__ = ["TELAS_ABERTAS", "exigir_login", "exigir_permissao"]

#: As rotas que podem viver sem guarda, e o motivo de cada uma. Uma lista
#: curta e explícita: qualquer nome que entre aqui devia doer um pouco.
TELAS_ABERTAS = frozenset({
    "entrar",  # a porta
    "tema",    # a folha que a própria tela de login precisa carregar
    # `sair` precisa funcionar mesmo com sessão inválida ou órfã (conta
    # apagada ou desativada depois do login: `usuario_da_sessao` não
    # reconstrói ninguém nesse caso). Atrás de `exigir_login`, essa sessão
    # quebrada nunca seria flushada — a pessoa ficaria sem conseguir sair de
    # verdade. `sair_da_sessao` já é segura de chamar sem sessão nenhuma.
    "sair",
    # O logo da tela de entrada e o favicon do `<head>` precisam existir
    # ANTES de qualquer sessão — é a mesma razão de `/tema.css`. A defesa
    # não é guarda de login: é a peneira na gravação (`ImagemDaMarca.save`
    # só aceita o que `nucleo.images.validar` aprova) e os cabeçalhos
    # seguros na resposta (`plataforma/views_marca`).
    "marca_imagem",
    # O RG da versão: o painel das instalações lê antes de qualquer
    # sessão — um commit curto não revela nada (spec do painel).
    "versao",
})


#: As rotas que continuam abertas para quem tem a senha vencida — trocar a
#: própria senha (e a foto, que mora na mesma tela) e sair. Nada mais: a
#: pessoa entra no dia da senha vencida e a primeira tela é a troca.
LIBERADAS_COM_SENHA_EXPIRADA = frozenset({
    "perfil", "perfil_senha", "perfil_foto", "sair",
})


def _presa_pela_senha(request) -> bool:
    """A sessão tem senha vencida E esta rota não é uma das liberadas?

    Durante personificação, nunca: quem está vendo é o alvo, e "trocar a
    senha" nesta tela trocaria a DELE — sequestrar a sessão da MW5 para
    isso seria um jeito acidental de resetar senha alheia.
    """
    if not request.session.get("senha_expirada"):
        return False
    if "usuario_personificado_id" in request.session:
        return False
    return request.resolver_match.url_name not in LIBERADAS_COM_SENHA_EXPIRADA


def exigir_login(view):
    """Sem sessão, vai para a tela de entrada. Com a senha vencida, vai para
    a troca dela — e não sai de lá até trocar.

    A flag mora na sessão (`comum.sessao.CHAVE_SENHA_EXPIRADA`), posta no
    login; `exigir_permissao` aplica a mesma porta.
    """

    @wraps(view)
    def guardada(request, *args, **kwargs):
        user = usuario_da_sessao(request)
        if user is None:
            return HttpResponseRedirect(reverse("entrar"))
        if _presa_pela_senha(request):
            return HttpResponseRedirect(reverse("perfil") + "?expirada=1")
        request.usuario = user
        return view(request, *args, **kwargs)

    guardada.exige_login = True
    return guardada


def exigir_permissao(nome: str):
    """Sem a permissão, a rota responde como se não existisse.

    404 e não 403, de propósito: quem não pode não precisa descobrir que a
    tela existe. A resposta é montada à mão (`HttpResponseNotFound`), e não
    por `raise Http404`: levantar a exceção deixaria a conversão em resposta
    a cargo do handler do Django, que em `DEBUG=True` mostra uma página
    técnica listando os padrões de URL tentados — exatamente a pista que
    esta guarda existe para não dar.
    """

    def decorar(view):
        @wraps(view)
        def guardada(request, *args, **kwargs):
            user = usuario_da_sessao(request)
            if user is None:
                return HttpResponseRedirect(reverse("entrar"))
            if _presa_pela_senha(request):
                return HttpResponseRedirect(reverse("perfil") + "?expirada=1")
            if not pode(user, nome):
                return HttpResponseNotFound()
            request.usuario = user
            return view(request, *args, **kwargs)

        guardada.exige_login = True
        guardada.permissao = nome
        return guardada

    return decorar
