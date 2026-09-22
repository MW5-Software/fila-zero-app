"""O gerente corrige a fila e os lançamentos da loja dele (D7).

Quem chama confere `fila.gerenciar` NO LUGAR (a view, pelo `request.usuario`
já com as permissões do cargo na loja atual): o gerente de uma loja não tem a
permissão em outra, e o supervisor tem na empresa inteira. Aqui se confere o
que a permissão não diz: que a pessoa e o atendimento são DESTA loja, e que
ninguém corrige a si mesmo (desvio D-3 do plano).

Toda correção grava na auditoria dentro da mesma transação: se a trilha
falhar, a correção desfaz junto (ver `comum.auditoria.registrar`).
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import BooleanField, ExpressionWrapper, Q
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from comum.auditoria import registrar

from .auditoria import ACOES_DA_FILA

from . import acoes
from .acoes import (Recusa, _abrir_pausa, _depois_do_atendimento,
                    _gravar_lancamento, _fechar_atendimento, _lugar_na_loja,
                    _sair, _travar, _validar, _voltar_ao_fim)
from .estado import na_fila, nome_de
from .models import AcaoDeCorrecao, Atendimento, CorrecaoNaFila, Estado, Pausa, Resultado
from .periodo import inicio_do_dia
from .valores import em_reais

__all__ = ["descrever", "editar_lancamento", "fechar_atendimento",
           "lancamentos_de_hoje", "ler_observacao", "mover", "por_em_pausa",
           "por_na_fila",
           "tirar_da_loja",
           "tirar_da_pausa"]

NAO_CORRIGE_A_SI = gettext_lazy("Você não corrige a si mesmo.")


def _agora():
    """A MESMA hora das ações do vendedor, lida pelo módulo delas e não
    importada por nome: a correção grava `na_fila_desde` na mesma fila que
    as ações, e dois relógios (o do teste num, o de verdade no outro) punham
    quem voltou depois na frente de quem já esperava."""
    return acoes._agora()
NAO_ENCONTRADO = gettext_lazy("Essa pessoa não está nesta loja.")
MOTIVO_CURTO = gettext_lazy("Escreva o motivo da correção.")
MOTIVO_LONGO = gettext_lazy("O motivo cabe em 200 caracteres.")
NAO_ESTA_NA_FILA = gettext_lazy("Essa pessoa não está na fila.")
NAO_ESTA_EM_ESPERA = gettext_lazy("Essa pessoa não está em espera.")
_MICRO = timedelta(microseconds=1)


def ler_observacao(texto) -> str:
    """O motivo da correção, obrigatório (spec 2026-09-17, C1). Três
    caracteres barram o "." digitado só para passar; duzentos cabem numa
    linha do histórico. Lido ANTES da trava: recusa barata não segura a fila
    da loja."""
    limpo = " ".join(str(texto or "").split())
    if len(limpo) < 3:
        raise Recusa(MOTIVO_CURTO)
    if len(limpo) > 200:
        raise Recusa(MOTIVO_LONGO)
    return limpo


def _registrar(autor, filial, pessoa_id, acao, observacao, detalhe, agora, *,
               auditoria, alvo, request=None) -> None:
    """O histórico e a auditoria juntos, na transação da correção: se um
    falhar, a correção desfaz inteira."""
    CorrecaoNaFila.irrestritos.create(
        empresa=filial.empresa, filial=filial, pessoa_id=pessoa_id, autor=autor,
        acao=acao, observacao=observacao, detalhe=detalhe[:300], momento=agora)
    trilha = f"{detalhe} | motivo: {observacao}" if detalhe else f"motivo: {observacao}"
    registrar(auditoria, autor, alvo=alvo, detalhe=trilha, request=request)


def descrever(atendimento) -> str:
    if atendimento.resultado == Resultado.VENDEU:
        itens = "; ".join(f"{item.grupo.nome} {em_reais(item.valor)}"
                          for item in atendimento.itens.select_related("grupo")
                          .order_by("pk"))
        return f"vendeu {em_reais(atendimento.total)} ({itens})"
    if atendimento.resultado == Resultado.NAO_VENDEU:
        observacao = f" ({atendimento.observacao})" if atendimento.observacao else ""
        return f"não vendeu: {atendimento.motivo.nome}{observacao}"
    return "aberto"


def _lugar_de_outro(autor, filial, pessoa_id):
    if pessoa_id == autor.pk:
        raise Recusa(NAO_CORRIGE_A_SI)
    try:
        # Pelo MÓDULO, e não pelo nome importado, como `_agora()`: é assim que
        # o teste de concorrência força a demora entre ler e gravar também na
        # correção, e prova a trava em vez da sorte.
        return acoes._lugar_na_loja(pessoa_id, filial)
    except Recusa:
        raise Recusa(NAO_ENCONTRADO) from None


def _alvo(lugar, filial) -> str:
    return f"{nome_de(lugar.pessoa)} em {filial}"


def tirar_da_loja(autor, filial, pessoa_id, lancamento=None, *, observacao,
                  request=None):
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        agora = _agora()
        detalhe = ""
        if lugar.estado == Estado.ATENDENDO:
            # Quem esqueceu de sair no meio de um atendimento: o gerente fecha
            # como não venda, com o motivo que escolher. Venda ele lança
            # antes, por "fechar atendimento", sabendo o que foi vendido.
            if lancamento is None or lancamento.resultado != Resultado.NAO_VENDEU:
                raise Recusa(_("Ela está atendendo. Escolha o motivo da não "
                               "venda para fechar o atendimento."))
            atendimento = Atendimento.irrestritos.get(
                vendedor_id=pessoa_id, fim__isnull=True)
            _fechar_atendimento(atendimento, lancamento, agora,
                                fechado_por=autor)
            detalhe = f"atendimento fechado: {descrever(atendimento)}"
        alvo = _alvo(lugar, filial)
        _sair(lugar, agora, fechada_por=autor)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.TIRAR, observacao,
                   detalhe, agora, auditoria=ACOES_DA_FILA.FILA_PESSOA_TIRADA, alvo=alvo,
                   request=request)


def fechar_atendimento(autor, filial, pessoa_id, lancamento, *, observacao,
                       request=None):
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.ATENDENDO:
            raise Recusa(_("Essa pessoa não está atendendo."))
        atendimento = Atendimento.irrestritos.get(vendedor_id=pessoa_id,
                                                  fim__isnull=True)
        agora = _agora()
        _fechar_atendimento(atendimento, lancamento, agora, fechado_por=autor)
        # Pelo fluxo da empresa, como quando é o próprio vendedor que lança
        # (spec 2026-09-17): quem fechou não muda para onde a pessoa vai.
        _depois_do_atendimento(lugar, filial, agora)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.FECHAR, observacao,
                   descrever(atendimento), agora,
                   auditoria=ACOES_DA_FILA.FILA_ATENDIMENTO_FECHADO,
                   alvo=_alvo(lugar, filial), request=request)


def tirar_da_pausa(autor, filial, pessoa_id, *, observacao, request=None):
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.EM_PAUSA:
            raise Recusa(_("Essa pessoa não está em pausa."))
        pausa = Pausa.irrestritos.select_related("tipo").get(
            pessoa_id=pessoa_id, fim__isnull=True)
        agora = _agora()
        pausa.fim = agora
        pausa.save(update_fields=["fim"])
        _voltar_ao_fim(lugar, agora)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.TIRAR_PAUSA, observacao,
                   pausa.tipo.nome, agora, auditoria=ACOES_DA_FILA.FILA_PAUSA_ENCERRADA,
                   alvo=_alvo(lugar, filial), request=request)


def editar_lancamento(autor, filial, atendimento_id, lancamento, *,
                      observacao, request=None):
    """Troca o que foi lançado num atendimento FECHADO. Não reabre, não muda
    o fim nem o resultado: corrigir "vendeu" para "não vendeu" apagaria uma
    venda do ranking com um clique, e isso é outra conversa."""
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        atendimento = (Atendimento.objects.da_empresa(filial.empresa)
                       .select_related("vendedor", "motivo")
                       .filter(pk=atendimento_id, filial=filial,
                               fim__isnull=False).first()
                       if atendimento_id is not None else None)
        if atendimento is None:
            raise Recusa(_("Lançamento não encontrado."))
        if atendimento.vendedor_id == autor.pk:
            raise Recusa(NAO_CORRIGE_A_SI)
        if lancamento.resultado != atendimento.resultado:
            raise Recusa(_("O resultado não muda na correção."))
        antes = descrever(atendimento)
        grupos, motivo, total = _validar(
            filial.empresa, lancamento,
            ja_usados=frozenset(atendimento.itens.values_list("grupo_id",
                                                              flat=True)),
            ja_usado_motivo=atendimento.motivo_id)
        _gravar_lancamento(atendimento, lancamento, grupos, motivo, total)
        depois = descrever(atendimento)
        _registrar(autor, filial, atendimento.vendedor_id, AcaoDeCorrecao.EDITAR,
                   observacao, f"antes: {antes}; depois: {depois}", _agora(),
                   auditoria=ACOES_DA_FILA.FILA_LANCAMENTO_CORRIGIDO,
                   alvo=f"Atendimento de {nome_de(atendimento.vendedor)} em {filial}",
                   request=request)


def lancamentos_de_hoje(filial, dia=None):
    """Os atendimentos fechados da loja no dia local (o de hoje por padrão),
    do mais recente para o mais antigo."""
    dia = dia or timezone.localdate()
    inicio = inicio_do_dia(dia)
    return (Atendimento.objects.da_empresa(filial.empresa)
            .filter(filial=filial, fim__gte=inicio,
                    fim__lt=inicio + timedelta(days=1))
            .select_related("vendedor", "motivo").defer("vendedor__avatar")
            .annotate(tem_foto=ExpressionWrapper(
                Q(vendedor__avatar__isnull=False), output_field=BooleanField()))
            .order_by("-fim"))


def _instante_entre(outros, posicao):
    """O `na_fila_desde` que põe alguém na `posicao` (1…N) de uma fila que,
    sem ele, é `outros`. `None` quando não cabe um instante entre os vizinhos.

    Não há número de posição guardado (entrega 1): um número precisaria ser
    renumerado a cada saída, e renumerar sob concorrência é onde as filas se
    perdem. Estritamente entre os vizinhos, e não igual a um deles: no empate
    quem decide é o `pk`, e aí a pessoa podia cair do lado errado.
    """
    if posicao == 1:
        return outros[0].na_fila_desde - _MICRO
    if posicao == len(outros) + 1:
        return outros[-1].na_fila_desde + _MICRO
    antes, depois = outros[posicao - 2].na_fila_desde, outros[posicao - 1].na_fila_desde
    if depois - antes < 2 * _MICRO:
        return None
    return antes + (depois - antes) / 2


def _espacar(outros) -> None:
    """Dois microssegundos entre cada um, na ordem de agora, a partir do
    primeiro: abre lugar para encaixar quando os vizinhos estão colados.
    Só roda sob a trava da loja."""
    base = outros[0].na_fila_desde
    for i, lugar in enumerate(outros):
        lugar.na_fila_desde = base + 2 * i * _MICRO
        lugar.save(update_fields=["na_fila_desde"])


def mover(autor, filial, pessoa_id, posicao, *, observacao, request=None):
    """Põe quem está na fila na `posicao` escolhida pelo gerente (C3)."""
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.NA_FILA:
            raise Recusa(NAO_ESTA_NA_FILA)
        fila = list(na_fila(filial))
        if posicao is None or not 1 <= posicao <= len(fila):
            raise Recusa(_("Escolha uma posição da fila."))
        atual = next(i for i, l in enumerate(fila, 1) if l.pk == lugar.pk)
        if posicao == atual:
            raise Recusa(_("Essa pessoa já está nessa posição."))
        outros = [l for l in fila if l.pk != lugar.pk]
        instante = _instante_entre(outros, posicao)
        if instante is None:
            _espacar(outros)
            instante = _instante_entre(outros, posicao)
        lugar.na_fila_desde = instante
        lugar.save(update_fields=["na_fila_desde"])
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.MOVER, observacao,
                   f"de {atual}º para {posicao}º", _agora(),
                   auditoria=ACOES_DA_FILA.FILA_POSICAO_MOVIDA, alvo=_alvo(lugar, filial),
                   request=request)


def por_em_pausa(autor, filial, pessoa_id, tipo_id, *, observacao, request=None):
    """O vendedor foi ao banco e não apertou "Pausa" (C4). Só quem está na
    fila: quem atende tem o atendimento fechado antes, pela mesma folha."""
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        # Em espera também: a pessoa saiu da fila por conta própria, e pôr em
        # pausa é dizer por que ela não está disponível (spec 2026-09-17).
        if lugar.estado not in (Estado.NA_FILA, Estado.EM_ESPERA):
            raise Recusa(NAO_ESTA_NA_FILA)
        agora = _agora()
        tipo = _abrir_pausa(lugar, filial, tipo_id, agora)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.PAUSAR, observacao,
                   tipo.nome, agora, auditoria=ACOES_DA_FILA.FILA_PAUSA_INICIADA,
                   alvo=_alvo(lugar, filial), request=request)


def por_na_fila(autor, filial, pessoa_id, *, observacao, request=None):
    """O gerente põe na fila quem está em espera (spec 2026-09-17).

    Entra no FIM, como quem entra sozinho: a ordem da fila é a hora de
    entrada, e o gerente que quer alguém na frente usa "Mudar de posição".
    """
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado == Estado.NA_FILA:
            raise Recusa(_("Essa pessoa já está na fila."))
        if lugar.estado != Estado.EM_ESPERA:
            raise Recusa(NAO_ESTA_EM_ESPERA)
        agora = _agora()
        _voltar_ao_fim(lugar, agora)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.POR_NA_FILA,
                   observacao, "", agora, auditoria=ACOES_DA_FILA.FILA_POSTO_NA_FILA,
                   alvo=_alvo(lugar, filial), request=request)
