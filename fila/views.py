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
    """A raiz. A gestão vê os indicadores da fila abaixo da saudação; quem
    vende na loja do cabeçalho, o painel dele (spec 2026-09-16); o resto, a
    saudação.

    Quem só tem a fila de vendedor era mandado daqui para `/fila` (D-4), e
    por isso nunca via o Início. O desvio passou para a entrada
    (`fila.sinais.destino_do_vendedor`): ele continua entrando pela fila, e a
    raiz é dele quando quiser.
    """
    from nucleo.views import home
    from plataforma.contexto import empresa_atual
    from plataforma.models import Modulo

    from .indicadores import lojas_com_relatorio
    from .views_do_vendedor import inicio_do_vendedor
    from .views_indicadores import inicio_com_indicadores

    if not Modulo.objects.filter(chave="fila", ativo=True).exists():
        return home(request)
    empresa = empresa_atual(request)
    permitidas = lojas_com_relatorio(usuario_de(request.usuario), empresa)
    if permitidas:
        return inicio_com_indicadores(request, empresa, permitidas)
    # `pode` já traz as permissões do cargo NA loja do cabeçalho: o vendedor
    # de uma loja que só vê a outra não ganha painel na outra.
    loja = filial_atual(request)
    if loja is not None and pode(request.usuario, "fila.participar"):
        return inicio_do_vendedor(request, empresa, loja, usuario_de(request.usuario))
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
    # A saída pelo fim do turno roda ANTES de medir a versão: sem isto, a
    # pessoa sairia e a tela continuaria mostrando a fila antiga até alguém
    # recarregar a página inteira.
    from .turno import aplicar as aplicar_o_turno

    aplicar_o_turno(filial)
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
    # A mídia vale para os dois resultados, e mora FORA dos blocos que a
    # folha esconde (25/09/2026).
    midia_id = id_do_post(request, "midia")
    if resultado != Resultado.VENDEU:
        return Lancamento(
            resultado=resultado,
            motivo_id=id_do_post(request, "motivo"),
            observacao=request.POST.get("observacao", ""),
            midia_id=midia_id)
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
    return Lancamento(resultado=resultado, itens=tuple(itens), midia_id=midia_id)


def _pessoa_do_post(request) -> int:
    pessoa_id = id_do_post(request, "pessoa")
    if pessoa_id is None:
        raise Recusa(_("Essa pessoa não está nesta loja."))
    return pessoa_id


_DO_VENDEDOR = {
    "ponto": lambda r, f, p: acoes.bater_ponto(p, f),
    "atender": lambda r, f, p: acoes.vou_atender(p, f),
    "cliente_pediu": lambda r, f, p: acoes.cliente_pediu(p, f),
    # O 2º ou o 3º da fila põe o 1º em atendimento (25/09/2026). A regra de
    # quem pode é do domínio (`acoes.colega_atendendo`), sob a trava.
    "colega_atendendo": lambda r, f, p: acoes.colega_atendendo(
        p, f, _pessoa_do_post(r)),
    "finalizar": lambda r, f, p: acoes.finalizar(p, f, _lancamento(r)),
    "pausar": lambda r, f, p: acoes.pausar(p, f, id_do_post(r, "tipo")),
    "voltar": lambda r, f, p: acoes.voltar_para_a_fila(p, f),
    "entrar_na_fila": lambda r, f, p: acoes.entrar_na_fila(p, f),
    "sair": lambda r, f, p: acoes.sair_da_loja(p, f),
}

def _pausa_fixa(request) -> "str | None":
    """A pausa da gestão escolhida na folha do gerente (25/09/2026). O campo
    é o mesmo `tipo` das pausas cadastradas: nelas vem o id, e aqui o nome da
    pausa fixa. Só a folha do GERENTE passa por aqui — o `pausar` do vendedor
    lê o id e nada mais, e por isso não há como ele pedir uma destas."""
    from .models import PausaFixa

    valor = request.POST.get("tipo", "")
    return valor if valor in PausaFixa.values else None


def _motivo(request) -> str:
    """O motivo da correção. `motivo_da_correcao`, e não `observacao`: a folha
    de fechar já tem a observação da não venda, e os dois iriam no POST."""
    return request.POST.get("motivo_da_correcao", "")


_DO_GERENTE = {
    "tirar": lambda r, f, p: correcoes.tirar_da_loja(
        p, f, _pessoa_do_post(r),
        _lancamento(r) if r.POST.get("resultado") else None,
        observacao=_motivo(r), request=r),
    "fechar": lambda r, f, p: correcoes.fechar_atendimento(
        p, f, _pessoa_do_post(r), _lancamento(r), observacao=_motivo(r), request=r),
    "tirar_pausa": lambda r, f, p: correcoes.tirar_da_pausa(
        p, f, _pessoa_do_post(r), observacao=_motivo(r), request=r),
    # `id_do_post` transforma "²", vazio e número gigante em `None`, que
    # `mover` recusa com frase em vez de 500.
    "mover": lambda r, f, p: correcoes.mover(
        p, f, _pessoa_do_post(r), id_do_post(r, "posicao"),
        observacao=_motivo(r), request=r),
    "por_na_fila": lambda r, f, p: correcoes.por_na_fila(
        p, f, _pessoa_do_post(r), observacao=_motivo(r), request=r),
    "por_em_pausa": lambda r, f, p: correcoes.por_em_pausa(
        p, f, _pessoa_do_post(r), id_do_post(r, "tipo"),
        fixa=_pausa_fixa(r), observacao=_motivo(r), request=r),
    "recolocar": lambda r, f, p: correcoes.recolocar(
        p, f, _pessoa_do_post(r), id_do_post(r, "posicao"),
        observacao=_motivo(r), request=r),
    "editar": lambda r, f, p: correcoes.editar_lancamento(
        p, f, id_do_post(r, "atendimento"), _lancamento(r),
        observacao=_motivo(r), request=r),
}


@exigir_permissao("fila.ver")
@exigir_modulo_ligado("fila")
def agir(request) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    acao = request.POST.get("acao", "")
    if acao in _DO_VENDEDOR:
        # Bater o ponto é de quem atende, e quem gerencia a loja não atende
        # (`tela.atende`, 18/09/2026): o gerente e o dono da conta passam por
        # aqui e tomam 404 — a tela nem desenha o botão, e o POST forjado cai
        # no mesmo lugar. As OUTRAS ações do vendedor seguem presas só a
        # `fila.participar`, de propósito: quem já estava na loja quando esta
        # regra entrou no ar termina o atendimento dele, em vez de ficar preso.
        if acao == "ponto" and not tela.atende(request.usuario):
            return HttpResponseNotFound()
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
