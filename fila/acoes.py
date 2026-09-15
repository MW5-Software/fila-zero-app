"""O que o vendedor faz na fila, decidido no servidor e sob trava (D9).

Cada ação:
1. abre transação e tranca a linha da LOJA (`_travar`, desvio D-2 do plano);
2. relê o lugar da pessoa DEPOIS da trava e confere se a ação cabe;
3. grava tudo ou nada;
4. ou levanta `Recusa` com a frase que a tela mostra.

A leitura antes da trava não vale: dois "Vou atender" do mesmo vendedor (dois
toques, dois aparelhos) leriam os dois "na fila", e o segundo estouraria na
restrição do banco com erro 500 em vez de uma frase.

**`irrestritos` aqui dentro, e não `objects`.** Quem chama (a view) já decidiu
a loja pelo contexto da sessão e a passa pronta; as consultas daqui filtram
por essa loja ou pela pessoa, que é de uma conta só. Os cadastros escolhidos
pelo POST são a exceção: vêm de fora, e por isso passam por
`objects.da_empresa`, que recusa o id de outra conta.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from plataforma.models import Filial

from .estado import na_fila, nome_de, posicao_de
from .models import (Atendimento, Estado, GrupoDeItem, ItemVendido,
                     LugarNaFila, MotivoDeNaoVenda, Pausa, Presenca,
                     Resultado, TipoDePausa)

__all__ = ["ItemLancado", "Lancamento", "Recusa", "bater_ponto",
           "cliente_pediu", "finalizar", "pausar", "sair_da_loja",
           "voltar_para_a_fila", "vou_atender"]

NAO_ESTA_NA_LOJA = "Você não está nesta loja. Bata o ponto primeiro."


class Recusa(Exception):
    """A ação não cabe no estado de agora. `frase` vai para a tela como está."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


@dataclass(frozen=True)
class ItemLancado:
    grupo_id: int
    valor: Decimal


@dataclass(frozen=True)
class Lancamento:
    resultado: str
    itens: "tuple[ItemLancado, ...]" = ()
    motivo_id: "int | None" = None
    observacao: str = ""


def _agora():
    """Um ponto só para a hora, para o teste poder fazer o relógio andar."""
    return timezone.now()


def _travar(*filiais) -> None:
    """Tranca a fila das lojas. Em ordem de `pk`: duas ações que trancam as
    mesmas duas lojas em ordens diferentes esperariam uma pela outra para
    sempre."""
    pks = sorted({f.pk for f in filiais})
    list(Filial.objects.select_for_update().filter(pk__in=pks).order_by("pk"))


def _lugar(pessoa_id):
    return (LugarNaFila.irrestritos.select_related("filial", "presenca", "pessoa")
            .filter(pessoa_id=pessoa_id).first())


def _lugar_na_loja(pessoa_id, filial) -> LugarNaFila:
    lugar = _lugar(pessoa_id)
    if lugar is None or lugar.filial_id != filial.pk:
        raise Recusa(NAO_ESTA_NA_LOJA)
    return lugar


def _voltar_ao_fim(lugar, agora) -> None:
    lugar.estado = Estado.NA_FILA
    lugar.na_fila_desde = agora
    lugar.desde = agora
    lugar.save(update_fields=["estado", "na_fila_desde", "desde"])


def _sair(lugar, agora, fechada_por=None) -> None:
    """Fecha pausa aberta e presença, e apaga o lugar. Quem chama já recusou
    (ou fechou) o atendimento aberto."""
    Pausa.irrestritos.filter(pessoa_id=lugar.pessoa_id,
                             fim__isnull=True).update(fim=agora)
    presenca = lugar.presenca
    presenca.saida = agora
    presenca.fechada_por = fechada_por
    presenca.save(update_fields=["saida", "fechada_por"])
    lugar.delete()


def bater_ponto(pessoa, filial) -> None:
    with transaction.atomic():
        antes = _lugar(pessoa.pk)
        _travar(filial, *([antes.filial] if antes else []))
        lugar = _lugar(pessoa.pk)
        if lugar is not None and lugar.filial_id == filial.pk:
            raise Recusa("Você já está nesta loja.")
        if lugar is not None and lugar.estado == Estado.ATENDENDO:
            raise Recusa(f"Você está atendendo em {lugar.filial}. "
                         f"Finalize lá antes de entrar aqui.")
        agora = _agora()
        if lugar is not None:
            # Uma presença aberta por pessoa: chegar numa loja fecha a outra.
            _sair(lugar, agora)
        presenca = Presenca.irrestritos.create(
            empresa=filial.empresa, pessoa=pessoa, filial=filial,
            entrada=agora)
        LugarNaFila.irrestritos.create(
            empresa=filial.empresa, pessoa=pessoa, filial=filial,
            presenca=presenca, estado=Estado.NA_FILA, na_fila_desde=agora,
            desde=agora)


def _abrir_atendimento(lugar, filial, *, pediu: bool) -> None:
    agora = _agora()
    Atendimento.irrestritos.create(
        empresa=filial.empresa, filial=filial, vendedor_id=lugar.pessoa_id,
        presenca=lugar.presenca, inicio=agora, cliente_pediu=pediu)
    lugar.estado = Estado.ATENDENDO
    lugar.desde = agora
    lugar.save(update_fields=["estado", "desde"])


def _exigir_na_fila(lugar) -> None:
    if lugar.estado == Estado.ATENDENDO:
        raise Recusa("Você já está atendendo.")
    if lugar.estado == Estado.EM_PAUSA:
        raise Recusa("Você está em pausa. Volte para a fila primeiro.")


def vou_atender(pessoa, filial) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        _exigir_na_fila(lugar)
        primeiro = na_fila(filial).first()
        if primeiro.pk != lugar.pk:
            raise Recusa(f"A vez é de {nome_de(primeiro.pessoa)}. "
                         f"Você é o {posicao_de(lugar)}º da fila.")
        _abrir_atendimento(lugar, filial, pediu=False)


def cliente_pediu(pessoa, filial) -> None:
    """Fora da vez (D3). Quem estava em primeiro continua em primeiro, porque
    ninguém mais mudou de `na_fila_desde`."""
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        _exigir_na_fila(lugar)
        _abrir_atendimento(lugar, filial, pediu=True)


def _validar(empresa, lancamento, *, ja_usados=frozenset(),
             ja_usado_motivo=None):
    """Confere o lançamento e devolve `(grupos por id, motivo, total)`.

    `ja_usados`/`ja_usado_motivo` servem à correção do gerente (Task 4): o
    grupo que já estava no atendimento continua aceito mesmo desativado
    depois, para corrigir o valor não obrigar a trocar o grupo.
    """
    if lancamento.resultado == Resultado.VENDEU:
        if lancamento.motivo_id is not None:
            raise Recusa("Venda não tem motivo de não venda.")
        if not lancamento.itens:
            raise Recusa("Informe pelo menos um grupo com valor.")
        if any(item.valor is None or item.valor <= 0
               for item in lancamento.itens):
            raise Recusa("Todo valor precisa ser maior que zero.")
        ids = {item.grupo_id for item in lancamento.itens}
        grupos = {g.pk: g for g in GrupoDeItem.objects.da_empresa(empresa)
                  .filter(pk__in=ids)
                  if g.ativo or g.pk in ja_usados}
        if set(grupos) != ids:
            raise Recusa("Grupo de item não encontrado.")
        total = sum((item.valor for item in lancamento.itens), Decimal("0"))
        return grupos, None, total
    if lancamento.resultado == Resultado.NAO_VENDEU:
        if lancamento.itens:
            raise Recusa("Não venda não tem grupo nem valor.")
        motivo = (MotivoDeNaoVenda.objects.da_empresa(empresa)
                  .filter(pk=lancamento.motivo_id).first()
                  if lancamento.motivo_id is not None else None)
        if motivo is None or not (motivo.ativo or motivo.pk == ja_usado_motivo):
            raise Recusa("Escolha o motivo.")
        return {}, motivo, Decimal("0")
    raise Recusa("Escolha se vendeu ou não.")


def _gravar_lancamento(atendimento, lancamento, grupos, motivo, total) -> None:
    atendimento.resultado = lancamento.resultado
    atendimento.motivo = motivo
    atendimento.observacao = (lancamento.observacao.strip()[:280]
                              if motivo is not None else "")
    atendimento.total = total
    atendimento.save(update_fields=["resultado", "motivo", "observacao",
                                    "total", "fechado_por", "fim"])
    atendimento.itens.all().delete()
    # Um a um, e não `bulk_create`: é o `save` do `ModeloDaEmpresa` que
    # preenche a conta, e o `bulk_create` o pula.
    for item in lancamento.itens:
        ItemVendido.irrestritos.create(
            empresa=atendimento.empresa, atendimento=atendimento,
            grupo=grupos[item.grupo_id], valor=item.valor)


def _fechar_atendimento(atendimento, lancamento, agora, fechado_por=None):
    grupos, motivo, total = _validar(atendimento.empresa, lancamento)
    atendimento.fim = agora
    atendimento.fechado_por = fechado_por
    _gravar_lancamento(atendimento, lancamento, grupos, motivo, total)


def finalizar(pessoa, filial, lancamento) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        if lugar.estado != Estado.ATENDENDO:
            raise Recusa("Você não está atendendo.")
        atendimento = Atendimento.irrestritos.get(vendedor=pessoa,
                                                  fim__isnull=True)
        agora = _agora()
        _fechar_atendimento(atendimento, lancamento, agora)
        _voltar_ao_fim(lugar, agora)


def pausar(pessoa, filial, tipo_id) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        _exigir_na_fila(lugar)
        tipo = (TipoDePausa.objects.da_empresa(filial.empresa)
                .filter(pk=tipo_id, ativo=True).first()
                if tipo_id is not None else None)
        if tipo is None:
            raise Recusa("Escolha o tipo de pausa.")
        agora = _agora()
        Pausa.irrestritos.create(empresa=filial.empresa, pessoa=pessoa,
                                 filial=filial, presenca=lugar.presenca,
                                 tipo=tipo, inicio=agora)
        lugar.estado = Estado.EM_PAUSA
        lugar.desde = agora
        lugar.save(update_fields=["estado", "desde"])


def voltar_para_a_fila(pessoa, filial) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        if lugar.estado != Estado.EM_PAUSA:
            raise Recusa("Você não está em pausa.")
        agora = _agora()
        Pausa.irrestritos.filter(pessoa=pessoa, fim__isnull=True).update(
            fim=agora)
        _voltar_ao_fim(lugar, agora)


def sair_da_loja(pessoa, filial) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        if lugar.estado == Estado.ATENDENDO:
            raise Recusa("Finalize o atendimento antes de sair da loja.")
        _sair(lugar, _agora())
