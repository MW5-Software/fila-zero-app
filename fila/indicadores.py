"""As contas dos indicadores da fila (spec 2026-09-15, entrega 2).

Tudo é calculado na hora sobre o histórico (D2): a correção do gerente muda o
número na mesma hora, e não há resumo diário para ficar mentindo.

Duas regras valem para toda função daqui:
- **atendimento entra pela hora do fim**, e aberto não entra: o lançamento é
  do momento em que fechou, e aberto ainda não tem resultado;
- **toda consulta passa por `objects.da_empresa` e pelas lojas do recorte.**
  Nunca `irrestritos`: esta é a camada que as telas usam.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import NamedTuple

from django.db.models import (Case, Count, DateTimeField, DecimalField,
                              DurationField, ExpressionWrapper, F, FloatField,
                              IntegerField,
                              OuterRef, Q, Subquery, Sum, Value, When)
from django.db.models.functions import Coalesce, Greatest, Least, TruncDate, TruncHour
from django.utils import timezone

from .estado import nome_de
from .models import Atendimento, ItemVendido, Pausa, Presenca, Resultado
from .periodo import Periodo, inicio_do_dia

__all__ = ["ORDENAVEIS_DO_RANKING", "PADRAO_DO_RANKING", "Esquecido", "Fatia",
           "Numeros", "Posicao", "Recorte", "Variacao", "esquecidos",
           "lojas_com_permissao", "lojas_com_relatorio", "motivos", "numeros", "pausa_por_tipo",
           "por_dia", "por_grupo", "posicao_no_mes", "ranking", "variacao"]

ZERO = Decimal("0")
_DINHEIRO = DecimalField(max_digits=14, decimal_places=2)


@dataclass(frozen=True)
class Recorte:
    empresa: object
    lojas: tuple
    periodo: Periodo


@dataclass(frozen=True)
class Numeros:
    atendimentos: int
    vendas: int
    vendido: Decimal
    pediu: int
    vendas_pediu: int

    @property
    def conversao(self) -> "float | None":
        # Sem atendimento é "nada", e não 0%: 0% diria que a loja atendeu e
        # não vendeu, e ela não atendeu ninguém.
        return round(100 * self.vendas / self.atendimentos, 1) if self.atendimentos else None

    @property
    def ticket(self) -> "Decimal | None":
        return (self.vendido / self.vendas).quantize(Decimal("0.01")) if self.vendas else None

    @property
    def conversao_pediu(self) -> "float | None":
        return round(100 * self.vendas_pediu / self.pediu, 1) if self.pediu else None


@dataclass(frozen=True)
class Variacao:
    valor: float
    unidade: str

    @property
    def sobe(self) -> bool:
        return self.valor > 0


def variacao(atual, anterior, *, pontos: bool = False) -> "Variacao | None":
    """A seta ao lado do número. Conversão varia em pontos percentuais: de 20%
    para 24% é "↑ 4 p.p.", e não "↑ 20%", que ninguém lê certo. Anterior zero
    não tem seta: não existe "cresceu x%" a partir de nada."""
    if atual is None or anterior is None:
        return None
    if pontos:
        return Variacao(round(float(atual) - float(anterior), 1), "p.p.")
    if not anterior:
        return None
    return Variacao(round((float(atual) - float(anterior)) * 100 / float(anterior), 1), "%")


def _atendimentos(recorte: Recorte):
    return (Atendimento.objects.da_empresa(recorte.empresa)
            .filter(filial__in=recorte.lojas, fim__gte=recorte.periodo.de,
                    fim__lt=recorte.periodo.ate))


def numeros(recorte: Recorte, vendedor=None) -> Numeros:
    consulta = _atendimentos(recorte)
    if vendedor is not None:
        consulta = consulta.filter(vendedor=vendedor)
    venda = Q(resultado=Resultado.VENDEU)
    return Numeros(**consulta.aggregate(
        atendimentos=Count("pk"),
        vendas=Count("pk", filter=venda),
        vendido=Coalesce(Sum("total", filter=venda), Value(ZERO), output_field=_DINHEIRO),
        pediu=Count("pk", filter=Q(cliente_pediu=True)),
        vendas_pediu=Count("pk", filter=venda & Q(cliente_pediu=True)),
    ))


def por_grupo(recorte: Recorte) -> "list[tuple[str, Decimal]]":
    return [(linha["grupo__nome"], linha["valor"]) for linha in (
        ItemVendido.objects.da_empresa(recorte.empresa)
        .filter(atendimento__filial__in=recorte.lojas,
                atendimento__fim__gte=recorte.periodo.de,
                atendimento__fim__lt=recorte.periodo.ate)
        .values("grupo__nome").annotate(valor=Sum("valor"))
        .order_by("-valor", "grupo__nome"))]


def motivos(recorte: Recorte) -> "list[tuple[str, int]]":
    return [(linha["motivo__nome"], linha["n"]) for linha in (
        _atendimentos(recorte).filter(resultado=Resultado.NAO_VENDEU)
        .values("motivo__nome").annotate(n=Count("pk"))
        .order_by("-n", "motivo__nome"))]


def pausa_por_tipo(recorte: Recorte) -> "list[tuple[str, int]]":
    """Minutos de pausa por tipo. Só pausas fechadas, e só a parte de cada uma
    que cai dentro do período: a pausa das 23:40 às 00:20 conta 20 minutos em
    cada dia."""
    de, ate = recorte.periodo.de, recorte.periodo.ate
    dentro = ExpressionWrapper(
        Least("fim", Value(ate, output_field=DateTimeField()))
        - Greatest("inicio", Value(de, output_field=DateTimeField())),
        output_field=DurationField())
    linhas = (Pausa.objects.da_empresa(recorte.empresa)
              .filter(filial__in=recorte.lojas, fim__isnull=False,
                      inicio__lt=ate, fim__gt=de)
              .annotate(dentro=dentro)
              .values("tipo__nome").annotate(total=Sum("dentro"))
              .order_by("-total", "tipo__nome"))
    return [(linha["tipo__nome"], int(linha["total"].total_seconds() // 60))
            for linha in linhas]


class Fatia(NamedTuple):
    rotulo: str
    atendimentos: int
    vendido: Decimal
    vendas: int


def por_dia(recorte: Recorte) -> "list[Fatia]":
    """(rótulo, atendimentos, vendido, vendas) por dia; por hora quando o
    período é um dia só. Os vazios aparecem com zero: um gráfico que pula o dia
    sem atendimento esconde justamente o dia ruim. As vendas vêm junto para a
    conversão e o ticket de cada dia, que o Início também desenha."""
    fuso = timezone.get_current_timezone()
    por_hora = recorte.periodo.dias == 1
    fatia = TruncHour("fim", tzinfo=fuso) if por_hora else TruncDate("fim", tzinfo=fuso)
    venda = Q(resultado=Resultado.VENDEU)
    achados = {
        linha["fatia"]: (linha["n"], linha["v"], linha["vendas"]) for linha in (
            _atendimentos(recorte).annotate(fatia=fatia).values("fatia")
            .annotate(n=Count("pk"), vendas=Count("pk", filter=venda),
                      v=Coalesce(Sum("total", filter=venda), Value(ZERO),
                                 output_field=_DINHEIRO))
            .order_by("fatia"))}
    linhas = []
    if por_hora:
        for hora in range(24):
            momento = recorte.periodo.de + timedelta(hours=hora)
            linhas.append(Fatia(f"{hora}h", *_numa_fatia(achados.get(momento))))
        return linhas
    dia = timezone.localdate(recorte.periodo.de)
    fim = timezone.localdate(recorte.periodo.ate)
    while dia < fim:
        linhas.append(Fatia(dia.strftime("%d/%m"), *_numa_fatia(achados.get(dia))))
        dia += timedelta(days=1)
    return linhas


def _numa_fatia(achado):
    n, v, vendas = achado or (0, ZERO, 0)
    return n, v, vendas


@dataclass(frozen=True)
class Esquecido:
    o_que: str
    nome: str
    loja: object
    desde: datetime


def esquecidos(empresa, lojas, agora: "datetime | None" = None) -> "list[Esquecido]":
    """O que ficou aberto de um dia para o outro (D7)."""
    hoje = inicio_do_dia(timezone.localdate(agora or timezone.now()))
    achados = []
    fontes = (
        ("Presença aberta", Presenca, "pessoa", "entrada", Q(saida__isnull=True)),
        ("Atendimento aberto", Atendimento, "vendedor", "inicio", Q(fim__isnull=True)),
        ("Pausa aberta", Pausa, "pessoa", "inicio", Q(fim__isnull=True)),
    )
    for rotulo, model, quem, comeco, aberto in fontes:
        for linha in (model.objects.da_empresa(empresa)
                      .filter(aberto, filial__in=lojas, **{f"{comeco}__lt": hoje})
                      .select_related(quem, "filial").defer(f"{quem}__avatar")):
            achados.append(Esquecido(rotulo, nome_de(getattr(linha, quem)),
                                     linha.filial, getattr(linha, comeco)))
    return sorted(achados, key=lambda e: e.desde)


def lojas_com_permissao(pessoa, empresa, permissao: str) -> list:
    """As lojas em que o cargo da pessoa traz `permissao` (ou o coringa
    `fila.*`), pelo mesmo `contas.lugar` que decide a permissão em toda tela.
    O gerente de uma loja não a tem em outra; supervisor e titular, em todas.
    Os indicadores e as metas saem daqui (decisão P-7 do plano das metas)."""
    from contas.lugar import filiais_da_pessoa, permissoes_em

    if pessoa is None or empresa is None:
        return []
    return [loja for loja in filiais_da_pessoa(pessoa, empresa)
            if pessoa.is_superuser
            or {permissao, "fila.*"} & permissoes_em(pessoa, empresa, loja)]


def lojas_com_relatorio(pessoa, empresa) -> list:
    return lojas_com_permissao(pessoa, empresa, "fila.relatorios")


def _por_pessoa(consulta, campo_da_pessoa: str, expressao, saida, zero):
    """Uma subconsulta que agrega `consulta` para a pessoa da linha de fora.

    Subconsulta, e não `annotate` pela relação: `Atendimento.vendedor` e
    `Pausa.pessoa` não têm relação reversa (`related_name="+"`), de propósito,
    para ninguém atravessar do usuário para o histórico sem passar pela
    empresa.
    """
    return Coalesce(
        Subquery(consulta.filter(**{campo_da_pessoa: OuterRef("pk")})
                 .order_by().values(campo_da_pessoa)
                 .annotate(x=expressao).values("x")[:1], output_field=saida),
        Value(zero, output_field=saida), output_field=saida)


ORDENAVEIS_DO_RANKING = {
    "nome": ("nome",),
    "vendido": ("vendido", "conversao", "nome"),
    "atendimentos": ("atendimentos", "nome"),
    "vendas": ("vendas", "nome"),
    "conversao": ("conversao", "nome"),
    "ticket": ("ticket", "nome"),
    "pediu": ("pediu", "nome"),
    "pausa": ("pausa", "nome"),
}
PADRAO_DO_RANKING = "-vendido"


def ranking(recorte: Recorte):
    """As pessoas que fecharam atendimento como vendedor no recorte, com as
    colunas do ranking. Quem fechou no lugar delas (`fechado_por`) não
    aparece por isso: a venda é de quem atendeu."""
    from contas.models import Usuario

    base = _atendimentos(recorte)
    venda = Q(resultado=Resultado.VENDEU)
    de, ate = recorte.periodo.de, recorte.periodo.ate
    pausas = (Pausa.objects.da_empresa(recorte.empresa)
              .filter(filial__in=recorte.lojas, fim__isnull=False,
                      inicio__lt=ate, fim__gt=de)
              .annotate(dentro=ExpressionWrapper(
                  Least("fim", Value(ate, output_field=DateTimeField()))
                  - Greatest("inicio", Value(de, output_field=DateTimeField())),
                  output_field=DurationField())))
    inteiro = IntegerField()
    return (Usuario.objects.filter(pk__in=base.values("vendedor"))
            .defer("avatar")
            .annotate(
                atendimentos=_por_pessoa(base, "vendedor", Count("pk"), inteiro, 0),
                vendas=_por_pessoa(base, "vendedor", Count("pk", filter=venda), inteiro, 0),
                vendido=_por_pessoa(base, "vendedor", Sum("total", filter=venda), _DINHEIRO, ZERO),
                pediu=_por_pessoa(base, "vendedor", Count("pk", filter=Q(cliente_pediu=True)), inteiro, 0),
                pausa=_por_pessoa(pausas, "pessoa", Sum("dentro"), DurationField(), timedelta(0)),
            )
            .annotate(
                conversao=Case(When(atendimentos=0, then=Value(None)),
                               default=ExpressionWrapper(F("vendas") * 100.0 / F("atendimentos"),
                                                         output_field=FloatField()),
                               output_field=FloatField()),
                ticket=Case(When(vendas=0, then=Value(None)),
                            default=ExpressionWrapper(F("vendido") / F("vendas"),
                                                      output_field=_DINHEIRO),
                            output_field=_DINHEIRO),
            ))


@dataclass(frozen=True)
class Posicao:
    posicao: int
    total: int


def posicao_no_mes(pessoa, loja, agora: "datetime | None" = None) -> "Posicao | None":
    """A posição da pessoa no ranking de vendido da loja, no mês corrente,
    entre quem vendeu algo. Mesmo valor, mesma posição."""
    agora = agora or timezone.now()
    hoje = timezone.localdate(agora)
    mes = Periodo(inicio_do_dia(hoje.replace(day=1)),
                  inicio_do_dia(hoje + timedelta(days=1)), "mes", "Este mês")
    totais = dict(
        _atendimentos(Recorte(loja.empresa, (loja,), mes))
        .filter(resultado=Resultado.VENDEU)
        .values("vendedor").annotate(v=Sum("total"))
        .values_list("vendedor", "v"))
    meu = totais.get(pessoa.pk)
    if not meu:
        return None
    return Posicao(1 + sum(1 for v in totais.values() if v > meu), len(totais))
