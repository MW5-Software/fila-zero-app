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

from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import BooleanField, ExpressionWrapper, Q
from django.utils import timezone

from comum.auditoria import ACOES, registrar

from . import acoes
from .acoes import (Recusa, _gravar_lancamento, _fechar_atendimento,
                    _lugar_na_loja, _sair, _travar, _validar, _voltar_ao_fim)
from .estado import nome_de
from .models import Atendimento, Estado, Pausa, Resultado
from .valores import em_reais

__all__ = ["descrever", "editar_lancamento", "fechar_atendimento",
           "lancamentos_de_hoje", "tirar_da_loja", "tirar_da_pausa"]

NAO_CORRIGE_A_SI = "Você não corrige a si mesmo."


def _agora():
    """A MESMA hora das ações do vendedor, lida pelo módulo delas e não
    importada por nome: a correção grava `na_fila_desde` na mesma fila que
    as ações, e dois relógios (o do teste num, o de verdade no outro) punham
    quem voltou depois na frente de quem já esperava."""
    return acoes._agora()
NAO_ENCONTRADO = "Essa pessoa não está nesta loja."


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
        return _lugar_na_loja(pessoa_id, filial)
    except Recusa:
        raise Recusa(NAO_ENCONTRADO) from None


def _alvo(lugar, filial) -> str:
    return f"{nome_de(lugar.pessoa)} em {filial}"


def tirar_da_loja(autor, filial, pessoa_id, lancamento=None, *, request=None):
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
                raise Recusa("Ela está atendendo. Escolha o motivo da não "
                             "venda para fechar o atendimento.")
            atendimento = Atendimento.irrestritos.get(
                vendedor_id=pessoa_id, fim__isnull=True)
            _fechar_atendimento(atendimento, lancamento, agora,
                                fechado_por=autor)
            detalhe = f"atendimento fechado: {descrever(atendimento)}"
        alvo = _alvo(lugar, filial)
        _sair(lugar, agora, fechada_por=autor)
        registrar(ACOES.FILA_PESSOA_TIRADA, autor, alvo=alvo, detalhe=detalhe,
                  request=request)


def fechar_atendimento(autor, filial, pessoa_id, lancamento, *, request=None):
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.ATENDENDO:
            raise Recusa("Essa pessoa não está atendendo.")
        atendimento = Atendimento.irrestritos.get(vendedor_id=pessoa_id,
                                                  fim__isnull=True)
        agora = _agora()
        _fechar_atendimento(atendimento, lancamento, agora, fechado_por=autor)
        _voltar_ao_fim(lugar, agora)
        registrar(ACOES.FILA_ATENDIMENTO_FECHADO, autor,
                  alvo=_alvo(lugar, filial), detalhe=descrever(atendimento),
                  request=request)


def tirar_da_pausa(autor, filial, pessoa_id, *, request=None):
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.EM_PAUSA:
            raise Recusa("Essa pessoa não está em pausa.")
        pausa = Pausa.irrestritos.select_related("tipo").get(
            pessoa_id=pessoa_id, fim__isnull=True)
        agora = _agora()
        pausa.fim = agora
        pausa.save(update_fields=["fim"])
        _voltar_ao_fim(lugar, agora)
        registrar(ACOES.FILA_PAUSA_ENCERRADA, autor,
                  alvo=_alvo(lugar, filial), detalhe=pausa.tipo.nome,
                  request=request)


def editar_lancamento(autor, filial, atendimento_id, lancamento, *,
                      request=None):
    """Troca o que foi lançado num atendimento FECHADO. Não reabre, não muda
    o fim nem o resultado: corrigir "vendeu" para "não vendeu" apagaria uma
    venda do ranking com um clique, e isso é outra conversa."""
    with transaction.atomic():
        _travar(filial)
        atendimento = (Atendimento.objects.da_empresa(filial.empresa)
                       .select_related("vendedor", "motivo")
                       .filter(pk=atendimento_id, filial=filial,
                               fim__isnull=False).first()
                       if atendimento_id is not None else None)
        if atendimento is None:
            raise Recusa("Lançamento não encontrado.")
        if atendimento.vendedor_id == autor.pk:
            raise Recusa(NAO_CORRIGE_A_SI)
        if lancamento.resultado != atendimento.resultado:
            raise Recusa("O resultado não muda na correção.")
        antes = descrever(atendimento)
        grupos, motivo, total = _validar(
            filial.empresa, lancamento,
            ja_usados=frozenset(atendimento.itens.values_list("grupo_id",
                                                              flat=True)),
            ja_usado_motivo=atendimento.motivo_id)
        _gravar_lancamento(atendimento, lancamento, grupos, motivo, total)
        depois = descrever(atendimento)
        registrar(ACOES.FILA_LANCAMENTO_CORRIGIDO, autor,
                  alvo=f"Atendimento de {nome_de(atendimento.vendedor)} em {filial}",
                  detalhe=f"antes: {antes}; depois: {depois}", request=request)


def lancamentos_de_hoje(filial, dia=None):
    """Os atendimentos fechados da loja no dia local (o de hoje por padrão),
    do mais recente para o mais antigo."""
    dia = dia or timezone.localdate()
    inicio = timezone.make_aware(datetime.combine(dia, time.min))
    return (Atendimento.objects.da_empresa(filial.empresa)
            .filter(filial=filial, fim__gte=inicio,
                    fim__lt=inicio + timedelta(days=1))
            .select_related("vendedor", "motivo").defer("vendedor__avatar")
            .annotate(tem_foto=ExpressionWrapper(
                Q(vendedor__avatar__isnull=False), output_field=BooleanField()))
            .order_by("-fim"))
