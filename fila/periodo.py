"""O período dos indicadores: o que a URL pede, e com o que comparar.

Sem banco, de propósito: é aritmética de datas, testável sozinha, e é onde um
indicador sai errado sem ninguém perceber — um "Hoje" comparado com o ontem
inteiro mostra queda em toda manhã.

Os limites são instantes com fuso (`TIME_ZONE` da instalação): `de` inclusivo,
`ate` exclusivo. Um dia é [00:00, 00:00 do dia seguinte).
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone

__all__ = ["ATALHOS", "PADRAO", "Periodo", "inicio_do_dia",
           "periodo_anterior", "periodo_do_pedido"]

ATALHOS: "tuple[tuple[str, str], ...]" = (
    ("hoje", "Hoje"), ("ontem", "Ontem"), ("7dias", "7 dias"),
    ("mes", "Este mês"), ("mes_passado", "Mês passado"),
)
PADRAO = "mes"

#: Decisão P-4 do plano: as contas são feitas na hora, e um intervalo de anos
#: numa rede grande é o pedido que derruba a tela.
MAIOR_INTERVALO_EM_DIAS = 366


@dataclass(frozen=True)
class Periodo:
    de: datetime
    ate: datetime
    chave: str
    rotulo: str

    @property
    def dias(self) -> int:
        return max(1, round((self.ate - self.de).total_seconds() / 86400))


def inicio_do_dia(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time.min))


def _data(texto: "str | None") -> "date | None":
    try:
        return date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def _mesmo_dia_no_mes_anterior(momento: datetime) -> datetime:
    """14:30 do dia 15 -> 14:30 do dia 15 do mês anterior; dia 31 num mês de
    30 dias cai no dia 30 (spec, "A comparação")."""
    local = timezone.localtime(momento)
    ano, mes = (local.year, local.month - 1) if local.month > 1 else (local.year - 1, 12)
    dia = min(local.day, calendar.monthrange(ano, mes)[1])
    return timezone.make_aware(datetime.combine(date(ano, mes, dia), local.time()))


def _primeiro_do_mes_anterior(dia: date) -> date:
    return (dia.replace(day=1) - timedelta(days=1)).replace(day=1)


def periodo_do_pedido(get: Mapping, agora: "datetime | None" = None) -> Periodo:
    agora = agora or timezone.now()
    hoje = timezone.localdate(agora)

    if get.get("de") or get.get("ate"):
        de, ate = _data(get.get("de")), _data(get.get("ate"))
        if de and ate and de <= ate and (ate - de).days <= MAIOR_INTERVALO_EM_DIAS:
            return Periodo(inicio_do_dia(de), inicio_do_dia(ate + timedelta(days=1)),
                           "intervalo", f"{de:%d/%m/%Y} a {ate:%d/%m/%Y}")

    chave = get.get("periodo", "")
    rotulos = dict(ATALHOS)
    if chave not in rotulos:
        chave = PADRAO
    amanha = inicio_do_dia(hoje + timedelta(days=1))
    limites = {
        "hoje": (inicio_do_dia(hoje), amanha),
        "ontem": (inicio_do_dia(hoje - timedelta(days=1)), inicio_do_dia(hoje)),
        "7dias": (inicio_do_dia(hoje - timedelta(days=6)), amanha),
        "mes": (inicio_do_dia(hoje.replace(day=1)), amanha),
        "mes_passado": (inicio_do_dia(_primeiro_do_mes_anterior(hoje)),
                        inicio_do_dia(hoje.replace(day=1))),
    }[chave]
    return Periodo(*limites, chave, rotulos[chave])


def periodo_anterior(periodo: Periodo, agora: "datetime | None" = None) -> Periodo:
    """O período com que comparar.

    Em andamento (ainda não terminou), compara até o MESMO PONTO: meio dia
    contra um dia inteiro mostraria queda em todo começo de dia. O mês compara
    pelo calendário (dia 15 com dia 15), e não por tamanho: meses têm tamanhos
    diferentes. Terminado, compara com o mesmo tamanho logo antes.
    """
    agora = agora or timezone.now()
    rotulo = "Período anterior"
    if periodo.chave in ("mes", "mes_passado"):
        de_anterior = inicio_do_dia(_primeiro_do_mes_anterior(timezone.localdate(periodo.de)))
        if periodo.ate > agora:
            return Periodo(de_anterior, _mesmo_dia_no_mes_anterior(agora), "anterior", rotulo)
        return Periodo(de_anterior, periodo.de, "anterior", rotulo)
    tamanho = periodo.ate - periodo.de
    de_anterior = periodo.de - tamanho
    if periodo.ate > agora:
        return Periodo(de_anterior, de_anterior + (agora - periodo.de), "anterior", rotulo)
    return Periodo(de_anterior, periodo.de, "anterior", rotulo)
