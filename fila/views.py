"""As rotas da fila: a raiz, a página, a consulta e as ações.

As ações do vendedor pedem `fila.participar`; as do gerente, `fila.gerenciar`
— as duas conferidas por `pode(request.usuario, ...)`, que já traz as
permissões do cargo NA LOJA atual (`comum.sessao.usuario_da_sessao`). O
gerente de uma loja não tem `fila.gerenciar` em outra, e é essa a trava de
"corrige a loja dele"; a de "a pessoa é desta loja" mora em `fila.correcoes`.
"""

from __future__ import annotations

from django.http import (HttpResponse, HttpResponseNotAllowed,
                         HttpResponseNotFound, HttpResponseRedirect,
                         JsonResponse)
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from comum.guardas_de_acesso import exigir_login, exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.pedido import id_do_post
from contas.identidade import usuario_de
from nucleo.permissoes import pode
from plataforma.contexto import filial_atual

from . import acoes, correcoes, tela
from .acoes import ItemLancado, Lancamento, Recusa
from .models import Resultado
from .estado import versao_da_fila
from .valores import ler_valor

__all__ = ["agir", "estado", "fila", "inicio"]

SEM_LOJA = gettext_lazy("Você ainda não está em nenhuma loja.")
CHAVE_DA_RECUSA = "fila:recusa"


@exigir_login
def inicio(request) -> HttpResponse:
    """A raiz. Quem só tem a fila de vendedor não tem o que fazer no
    dashboard, e cairia numa saudação vazia a cada login (D-4)."""
    from nucleo.views import home
    from plataforma.models import Modulo

    if (tela.so_a_fila(request.usuario)
            and Modulo.objects.filter(chave="fila", ativo=True).exists()):
        return HttpResponseRedirect(reverse("fila"))
    return home(request)


@exigir_permissao("fila.ver")
@exigir_modulo_ligado("fila")
def fila(request) -> HttpResponse:
    filial = filial_atual(request)
    if filial is None:
        return tela.sem_loja(request)
    recusa = request.session.pop(CHAVE_DA_RECUSA, "")
    return tela.pagina(request, filial, recusa)


@exigir_permissao("fila.ver")
@exigir_modulo_ligado("fila")
def estado(request) -> JsonResponse:
    filial = filial_atual(request)
    if filial is None:
        return JsonResponse({"versao": "", "mudou": False})
    # A versão sozinha é uma consulta; o retrato inteiro, só quando mudou.
    if request.GET.get("versao") == versao_da_fila(filial):
        return JsonResponse({"versao": request.GET["versao"], "mudou": False})
    versao, html = tela.pedacos(request, filial)
    return JsonResponse({"versao": versao, "mudou": True, "html": html})


def _lancamento(request) -> Lancamento:
    """O lançamento do POST, lido pelo resultado escolhido.

    A folha só ESCONDE o bloco da venda ou o da não venda; os campos do bloco
    escondido continuam indo no POST. Quem marcou "Vendeu", digitou um valor e
    mudou para "Não vendeu" mandava os dois, e a recusa falava de campos que
    ele não enxergava mais (revisão final, 15/09/2026). Por isso só se lê o
    que pertence ao resultado escolhido.
    """
    resultado = request.POST.get("resultado", "")
    if resultado != Resultado.VENDEU:
        return Lancamento(
            resultado=resultado,
            motivo_id=id_do_post(request, "motivo"),
            observacao=request.POST.get("observacao", ""))
    itens = []
    for grupo, valor in zip(request.POST.getlist("grupo"),
                            request.POST.getlist("valor")):
        if not grupo.strip() and not valor.strip():
            continue      # a linha vazia que a folha oferece a mais
        try:
            grupo_id = int(grupo)
        except ValueError:
            raise Recusa(_("Escolha o grupo de cada valor.")) from None
        quantia = ler_valor(valor)
        if quantia is None:
            raise Recusa(_('Valor inválido: "%(valor)s".') % {"valor": valor})
        itens.append(ItemLancado(grupo_id, quantia))
    return Lancamento(resultado=resultado, itens=tuple(itens))


def _pessoa_do_post(request) -> int:
    pessoa_id = id_do_post(request, "pessoa")
    if pessoa_id is None:
        raise Recusa(_("Essa pessoa não está nesta loja."))
    return pessoa_id


_DO_VENDEDOR = {
    "ponto": lambda r, f, p: acoes.bater_ponto(p, f),
    "atender": lambda r, f, p: acoes.vou_atender(p, f),
    "cliente_pediu": lambda r, f, p: acoes.cliente_pediu(p, f),
    "finalizar": lambda r, f, p: acoes.finalizar(p, f, _lancamento(r)),
    "pausar": lambda r, f, p: acoes.pausar(p, f, id_do_post(r, "tipo")),
    "voltar": lambda r, f, p: acoes.voltar_para_a_fila(p, f),
    "sair": lambda r, f, p: acoes.sair_da_loja(p, f),
}

_DO_GERENTE = {
    "tirar": lambda r, f, p: correcoes.tirar_da_loja(
        p, f, _pessoa_do_post(r),
        _lancamento(r) if r.POST.get("resultado") else None, request=r),
    "fechar": lambda r, f, p: correcoes.fechar_atendimento(
        p, f, _pessoa_do_post(r), _lancamento(r), request=r),
    "tirar_pausa": lambda r, f, p: correcoes.tirar_da_pausa(
        p, f, _pessoa_do_post(r), request=r),
    "editar": lambda r, f, p: correcoes.editar_lancamento(
        p, f, id_do_post(r, "atendimento"), _lancamento(r), request=r),
}


@exigir_permissao("fila.ver")
@exigir_modulo_ligado("fila")
def agir(request) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    acao = request.POST.get("acao", "")
    if acao in _DO_VENDEDOR:
        executar, precisa = _DO_VENDEDOR[acao], "fila.participar"
    elif acao in _DO_GERENTE:
        executar, precisa = _DO_GERENTE[acao], "fila.gerenciar"
    else:
        return HttpResponseNotFound()
    if not pode(request.usuario, precisa):
        return HttpResponseNotFound()

    filial = filial_atual(request)
    pessoa = usuario_de(request.usuario)
    frase = ""
    if filial is None or pessoa is None:
        frase = str(SEM_LOJA)
    else:
        try:
            executar(request, filial, pessoa)
        except Recusa as recusa:
            frase = recusa.frase

    if request.headers.get("X-Fila") == "1":
        resposta = {"ok": not frase, "frase": frase}
        if filial is not None:
            resposta["versao"], resposta["html"] = tela.pedacos(request, filial)
        return JsonResponse(resposta)
    if frase:
        request.session[CHAVE_DA_RECUSA] = frase
    return HttpResponseRedirect(reverse("fila"))
