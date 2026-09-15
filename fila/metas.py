"""As metas de venda da fila (spec 2026-09-15-fila-metas, entrega 3).

As regras moram aqui, e não nas telas: a tela de metas, o painel do Início,
o ranking e "Seus números" leem a mesma conta, e quatro cópias divergiriam no
primeiro ajuste. Toda função que depende do dia recebe `agora`, para o teste
provar o dia 1, o dia 15 e o último dia sem esperar o calendário.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from .periodo import ANOS_ACEITOS

__all__ = ["Acompanhamento", "acompanhar", "mes_anterior", "mes_do_texto",
           "mes_encerrado", "mes_seguinte", "primeiro_do_mes", "ultimo_do_mes"]

ZERO = Decimal("0")
CENTAVO = Decimal("0.01")


def _hoje(agora: "datetime | None") -> date:
    return timezone.localdate(agora or timezone.now())


def primeiro_do_mes(dia: date) -> date:
    return dia.replace(day=1)


def ultimo_do_mes(mes: date) -> date:
    return mes.replace(day=calendar.monthrange(mes.year, mes.month)[1])


def mes_anterior(mes: date) -> date:
    return primeiro_do_mes(primeiro_do_mes(mes) - timedelta(days=1))


def mes_seguinte(mes: date) -> date:
    return ultimo_do_mes(mes) + timedelta(days=1)


def mes_do_texto(texto: "str | None", agora: "datetime | None" = None) -> date:
    """`?mes=2026-09` -> 1º/09/2026. Vazio ou inválido cai no mês atual, nunca
    num erro: a URL é digitável e compartilhável (decisão P-8 do plano)."""
    atual = primeiro_do_mes(_hoje(agora))
    partes = (texto or "").strip().split("-")
    if len(partes) != 2:
        return atual
    ano, mes = partes
    # `isascii`, porque "²".isdigit() é verdade e int("²") estoura (revisão
    # final do Fila Zero, 15/09/2026).
    if not (ano.isascii() and ano.isdigit() and len(ano) == 4
            and mes.isascii() and mes.isdigit() and 1 <= len(mes) <= 2):
        return atual
    if int(ano) not in ANOS_ACEITOS or not 1 <= int(mes) <= 12:
        return atual
    return date(int(ano), int(mes), 1)


def mes_encerrado(mes: date, agora: "datetime | None" = None) -> bool:
    """Mês antes do atual. A meta dele não se edita (M6): mudar a régua depois
    do resultado desmente o que já foi cobrado."""
    return mes < primeiro_do_mes(_hoje(agora))


@dataclass(frozen=True)
class Acompanhamento:
    meta: Decimal
    vendido: Decimal
    atingido: float
    falta: Decimal
    excedente: Decimal
    encerrado: bool
    ultimo_dia: date
    dias_restantes: "int | None"
    por_dia: "Decimal | None"
    projecao: "Decimal | None"

    @property
    def batida(self) -> bool:
        return self.falta == ZERO


def acompanhar(meta: Decimal, vendido: Decimal, mes: date,
               agora: "datetime | None" = None,
               vendido_ate_ontem: "Decimal | None" = None) -> Acompanhamento:
    """Quanto da meta já foi feito e o ritmo que falta (M5).

    - **por dia** divide o que falta pelos dias que restam CONTANDO hoje: é o
      que a loja ainda pode vender hoje.
    - **projeção** usa só os dias FECHADOS: no dia 1 às 10h, uma venda de
      R$ 5.000 projetaria R$ 150.000, e o dia pela metade puxaria o número
      para baixo no resto do mês. Por isso o dia 1 não tem projeção.
    - Mês encerrado não tem ritmo: não há dia para vender.
    """
    hoje = _hoje(agora)
    atual = primeiro_do_mes(hoje)
    if mes > atual:
        raise ValueError("Mês futuro não tem acompanhamento.")
    ultimo = ultimo_do_mes(mes)
    falta = max(meta - vendido, ZERO)
    excedente = max(vendido - meta, ZERO)
    atingido = round(float(vendido * 100 / meta), 1)
    if mes < atual:
        return Acompanhamento(meta, vendido, atingido, falta, excedente, True,
                              ultimo, None, None, None)
    dias_restantes = ultimo.day - hoje.day + 1
    por_dia = (None if falta == ZERO
               else (falta / dias_restantes).quantize(CENTAVO, ROUND_HALF_UP))
    fechados = hoje.day - 1
    projecao = (None if not fechados or vendido_ate_ontem is None
                else (vendido_ate_ontem / fechados * ultimo.day)
                .quantize(CENTAVO, ROUND_HALF_UP))
    return Acompanhamento(meta, vendido, atingido, falta, excedente, False,
                          ultimo, dias_restantes, por_dia, projecao)
