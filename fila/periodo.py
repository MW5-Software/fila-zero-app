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

__all__ = ["ANOS_ACEITOS", "ATALHOS", "PADRAO", "Periodo", "inicio_do_dia",
           "periodo_anterior", "periodo_do_pedido"]

#: Os últimos N dias terminam hoje, e hoje conta como um deles.
DIAS_DOS_ATALHOS = (7, 15, 30, 60, 90)

#: Desde 17/09/2026 o período é só por atalho: o intervalo livre (De/Até)
#: saiu da tela a pedido do cliente. Os dois meses ficam porque a meta é
#: mensal, e é neles que a faixa da meta aparece.
#:
#: **"Últimos", e não só o número** (18/09/2026, pedido do cliente): "30 dias"
#: sozinho não dizia se eram os trinta que passaram ou os trinta que vêm, e o
#: campo convive com "Este mês" e "Mês passado" na mesma lista. A CHAVE não
#: mudou (`30dias`), então link salvo continua abrindo o mesmo período.
ATALHOS: "tuple[tuple[str, str], ...]" = (
    ("hoje", "Hoje"), ("ontem", "Ontem"),
    *((f"{n}dias", f"Últimos {n} dias") for n in DIAS_DOS_ATALHOS),
    ("mes", "Este mês"), ("mes_passado", "Mês passado"),
)
PADRAO = "mes"


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


#: Os anos que um mês pedido pela URL pode tocar (`metas.mes_do_texto`).
#: `date` aceita do ano 1 ao 9999, e as contas de um dia a mais ou do mês
#: anterior estouravam nas pontas com 500 (revisão final, 15/09/2026).
ANOS_ACEITOS = range(2000, 2101)


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

    chave = get.get("periodo", "")
    rotulos = dict(ATALHOS)
    # Um link salvo com `de`/`ate` do intervalo antigo cai aqui também: abre
    # no padrão, e não num intervalo que a tela já não mostra.
    if chave not in rotulos:
        chave = PADRAO
    amanha = inicio_do_dia(hoje + timedelta(days=1))
    limites = {
        "hoje": (inicio_do_dia(hoje), amanha),
        "ontem": (inicio_do_dia(hoje - timedelta(days=1)), inicio_do_dia(hoje)),
        **{f"{n}dias": (inicio_do_dia(hoje - timedelta(days=n - 1)), amanha)
           for n in DIAS_DOS_ATALHOS},
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
