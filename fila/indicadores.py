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
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple

from django.db.models import (Case, CharField, Count, DateTimeField, DecimalField,
                              DurationField, ExpressionWrapper, F, FloatField,
                              IntegerField,
                              OuterRef, Q, Subquery, Sum, Value, When)
from django.db.models.functions import (Cast, Coalesce, Greatest, Least,
                                       NullIf, TruncDate, TruncHour)
from django.utils import timezone

from .estado import nome_de
from .models import Atendimento, ItemVendido, Pausa, Presenca, Resultado
from .periodo import Periodo, inicio_do_dia

__all__ = ["ORDENAVEIS_DO_RANKING", "ORDENAVEIS_DO_RANKING_COM_META", "PADRAO_DO_RANKING", "Esquecido", "Fatia",
           "Numeros", "Posicao", "Recorte", "Variacao", "esquecidos",
           "lojas_com_permissao", "lojas_com_relatorio", "motivos", "numeros", "pausa_por_tipo",
           "do_recorte", "empresas_com_relatorio", "por_dia", "por_grupo",
           "por_empresa", "por_loja", "posicao_no_mes", "posicoes_por_vendido", "ranking",
           "ranking_por_loja", "recorte_do_mes", "variacao"]

ZERO = Decimal("0")
_DINHEIRO = DecimalField(max_digits=14, decimal_places=2)


@dataclass(frozen=True)
class Recorte:
    """O que o painel está olhando: a empresa (ou VÁRIAS, desde 17/09/2026), as
    lojas dentro delas e o período.

    `empresa` continua sendo a do cabeçalho, e é ela que vale quando o recorte
    é de uma só. `empresas` preenchido é o "Todas as empresas" do titular, e
    as duas pontas vêm sempre do ALCANCE da pessoa, nunca do pedido.
    """

    empresa: object
    lojas: tuple
    periodo: Periodo
    empresas: tuple = ()

    @property
    def todas(self) -> tuple:
        return self.empresas or (self.empresa,)


def do_recorte(model, recorte):
    """As linhas de `model` dentro do recorte, pelo inquilino.

    Com uma empresa, é `da_empresa`, a porta de sempre. Com várias, é
    `da_conta` (que filtra pelo `conta_guid`) recortado por `empresa__in`: as
    empresas do recorte são todas da MESMA conta, porque saem do alcance da
    pessoa (`empresas_com_relatorio`), e nunca de um id do pedido. Sem o
    `da_conta` por baixo, o filtro seria só uma lista de ids — e lista de ids
    é o que um pedido forjado sabe imitar.
    """
    empresas = recorte.todas
    if len(empresas) == 1:
        return model.objects.da_empresa(empresas[0])
    return (model.objects.da_conta(empresas[0].conta_id)
            .filter(empresa__in=empresas))


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


def recorte_do_mes(empresa, lojas, mes: date, empresas=()) -> Recorte:
    """O mês inteiro de `mes` (dia 1), para o ranking. O fim é o dia 1 do mês
    seguinte: no mês em andamento, o que ainda não aconteceu não conta."""
    from .metas import mes_seguinte

    return Recorte(empresa, tuple(lojas),
                   Periodo(inicio_do_dia(mes), inicio_do_dia(mes_seguinte(mes)),
                           "ranking", f"{mes:%m/%Y}"),
                   tuple(empresas))


def _atendimentos(recorte: Recorte, vendedor=None):
    consulta = (do_recorte(Atendimento, recorte)
                .filter(filial__in=recorte.lojas, fim__gte=recorte.periodo.de,
                        fim__lt=recorte.periodo.ate))
    return consulta if vendedor is None else consulta.filter(vendedor=vendedor)


def numeros(recorte: Recorte, vendedor=None) -> Numeros:
    consulta = _atendimentos(recorte, vendedor)
    venda = Q(resultado=Resultado.VENDEU)
    return Numeros(**consulta.aggregate(
        atendimentos=Count("pk"),
        vendas=Count("pk", filter=venda),
        vendido=Coalesce(Sum("total", filter=venda), Value(ZERO), output_field=_DINHEIRO),
        pediu=Count("pk", filter=Q(cliente_pediu=True)),
        vendas_pediu=Count("pk", filter=venda & Q(cliente_pediu=True)),
    ))


def por_grupo(recorte: Recorte, vendedor=None) -> "list[tuple[str, Decimal]]":
    itens = (do_recorte(ItemVendido, recorte)
             .filter(atendimento__filial__in=recorte.lojas,
                     atendimento__fim__gte=recorte.periodo.de,
                     atendimento__fim__lt=recorte.periodo.ate))
    if vendedor is not None:
        itens = itens.filter(atendimento__vendedor=vendedor)
    return [(linha["grupo__nome"], linha["valor"]) for linha in (
        itens.values("grupo__nome").annotate(valor=Sum("valor"))
        .order_by("-valor", "grupo__nome"))]


def motivos(recorte: Recorte, vendedor=None) -> "list[tuple[str, int]]":
    return [(linha["motivo__nome"], linha["n"]) for linha in (
        _atendimentos(recorte, vendedor).filter(resultado=Resultado.NAO_VENDEU)
        .values("motivo__nome").annotate(n=Count("pk"))
        .order_by("-n", "motivo__nome"))]


def pausa_por_tipo(recorte: Recorte, vendedor=None) -> "list[tuple[str, int]]":
    """Minutos de pausa por tipo. Só pausas fechadas, e só a parte de cada uma
    que cai dentro do período: a pausa das 23:40 às 00:20 conta 20 minutos em
    cada dia."""
    de, ate = recorte.periodo.de, recorte.periodo.ate
    dentro = ExpressionWrapper(
        Least("fim", Value(ate, output_field=DateTimeField()))
        - Greatest("inicio", Value(de, output_field=DateTimeField())),
        output_field=DurationField())
    pausas = (do_recorte(Pausa, recorte)
              .filter(filial__in=recorte.lojas, fim__isnull=False,
                      inicio__lt=ate, fim__gt=de))
    if vendedor is not None:
        pausas = pausas.filter(pessoa=vendedor)
    linhas = (pausas.annotate(dentro=dentro)
              .values("tipo__nome").annotate(total=Sum("dentro"))
              .order_by("-total", "tipo__nome"))
    return [(linha["tipo__nome"], int(linha["total"].total_seconds() // 60))
            for linha in linhas]


class Fatia(NamedTuple):
    rotulo: str
    atendimentos: int
    vendido: Decimal
    vendas: int


def por_dia(recorte: Recorte, vendedor=None) -> "list[Fatia]":
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
            _atendimentos(recorte, vendedor).annotate(fatia=fatia).values("fatia")
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


def empresas_com_relatorio(pessoa) -> list:
    """As empresas em que a pessoa lê indicadores em ALGUMA loja (17/09/2026).

    É a lista que o campo "Empresa" do painel oferece, e a que "Todas as
    empresas" soma. Sai do alcance (`contas.lugar.empresas_da_pessoa`) e da
    permissão em cada loja — as duas perguntas que o resto do painel já faz,
    uma por empresa.
    """
    from contas.lugar import empresas_da_pessoa

    if pessoa is None:
        return []
    return [empresa for empresa in empresas_da_pessoa(pessoa).order_by("razao_social")
            if lojas_com_relatorio(pessoa, empresa)]


def por_empresa(recorte: Recorte) -> "list[DaEmpresa]":
    """Os números de cada empresa do recorte, lado a lado — o "Por loja" um
    nível acima."""
    return [DaEmpresa(empresa,
                      numeros(Recorte(empresa,
                                      tuple(l for l in recorte.lojas
                                            if l.empresa_id == empresa.pk),
                                      recorte.periodo)))
            for empresa in recorte.todas]


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
ORDENAVEIS_DO_RANKING_COM_META = {
    **ORDENAVEIS_DO_RANKING,
    "meta": ("meta", "nome"),
    "pct_meta": ("pct_meta", "nome"),
}
PADRAO_DO_RANKING = "-vendido"


def ranking(recorte: Recorte, mes: "date | None" = None):
    """As pessoas que fecharam atendimento como vendedor no recorte, com as
    colunas do ranking. Quem fechou no lugar delas (`fechado_por`) não
    aparece por isso: a venda é de quem atendeu."""
    from contas.models import Usuario

    base = _atendimentos(recorte)
    venda = Q(resultado=Resultado.VENDEU)
    de, ate = recorte.periodo.de, recorte.periodo.ate
    pausas = (do_recorte(Pausa, recorte)
              .filter(filial__in=recorte.lojas, fim__isnull=False,
                      inicio__lt=ate, fim__gt=de)
              .annotate(dentro=ExpressionWrapper(
                  Least("fim", Value(ate, output_field=DateTimeField()))
                  - Greatest("inicio", Value(de, output_field=DateTimeField())),
                  output_field=DurationField())))
    inteiro = IntegerField()
    consulta = (Usuario.objects.filter(pk__in=base.values("vendedor"))
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
    if mes is None:
        return consulta
    # A meta do vendedor em "Todas as lojas" é a soma das metas dele nas lojas
    # do recorte, e o % é o vendido dele nessas lojas sobre essa soma. Sem
    # Coalesce: sem meta é "—", e não meta zero.
    from .models import MetaDeVenda

    metas = (do_recorte(MetaDeVenda, recorte)
             .filter(filial__in=recorte.lojas, mes=mes, pessoa__isnull=False))
    real = FloatField()
    return (consulta
            .annotate(meta=Subquery(
                metas.filter(pessoa=OuterRef("pk")).order_by().values("pessoa")
                .annotate(x=Sum("valor")).values("x")[:1], output_field=_DINHEIRO))
            .annotate(pct_meta=Case(
                When(meta__isnull=True, then=Value(None)),
                default=ExpressionWrapper(
                    Cast("vendido", real) * 100.0 / Cast("meta", real),
                    output_field=real),
                output_field=real)))


class _LinhaPorLoja(dict):
    """Uma linha de `ranking_por_loja`: o dicionário do `values()` lido como
    objeto, para a MESMA coluna da tela (`p.nome`, `p.vendido`) desenhar as
    duas consultas."""

    __getattr__ = dict.__getitem__


class _ConsultaPorLoja:
    """Embrulha a consulta de `ranking_por_loja` para as linhas saírem como
    `_LinhaPorLoja`, com a loja já carregada. A listagem só filtra, ordena,
    conta e fatia: o resto vai direto à consulta de verdade."""

    def __init__(self, consulta, lojas):
        self._consulta, self._lojas = consulta, {l.pk: l for l in lojas}

    def filter(self, *args, **kwargs):
        return _ConsultaPorLoja(self._consulta.filter(*args, **kwargs), self._lojas.values())

    def order_by(self, *campos):
        return _ConsultaPorLoja(self._consulta.order_by(*campos), self._lojas.values())

    def count(self) -> int:
        return self._consulta.count()

    def __getitem__(self, fatia):
        return [_LinhaPorLoja(linha, loja=self._lojas[linha["loja_id"]])
                for linha in self._consulta[fatia]]

    def __iter__(self):
        return iter(self[:])

    def __getattr__(self, nome):
        return getattr(self._consulta, nome)


def ranking_por_loja(recorte: Recorte, mes: "date | None" = None):
    """O ranking de "Todas as lojas": uma linha por pessoa EM CADA loja.

    Somar a pessoa entre as lojas (o `ranking`) escondia de onde veio a venda:
    na tela da Sylvia, o vendedor do Centro aparecia no meio da Matriz
    (17/09/2026). A pausa e a meta também são as daquela loja.

    Agrupa o próprio atendimento por vendedor e loja, e não parte do usuário,
    porque a linha é o par, e o usuário não tem relação reversa com o
    histórico (ver `_por_pessoa`). `pk` é o do vendedor, para a mesma regra de
    posição e de "sou eu" valer nas duas consultas.
    """
    venda = Q(resultado=Resultado.VENDEU)
    de, ate = recorte.periodo.de, recorte.periodo.ate
    pausas = (do_recorte(Pausa, recorte)
              .filter(pessoa=OuterRef("vendedor"), filial=OuterRef("filial"),
                      fim__isnull=False, inicio__lt=ate, fim__gt=de)
              .order_by().values("pessoa")
              .annotate(x=Sum(ExpressionWrapper(
                  Least("fim", Value(ate, output_field=DateTimeField()))
                  - Greatest("inicio", Value(de, output_field=DateTimeField())),
                  output_field=DurationField())))
              .values("x")[:1])
    consulta = (_atendimentos(recorte).order_by()
                .values("vendedor", "filial")
                .annotate(
                    pk=F("vendedor"), loja_id=F("filial"),
                    nome=Coalesce(NullIf("vendedor__nome", Value("")), "vendedor__email",
                                  output_field=CharField()),
                    loja_nome=F("filial__apelido"),
                    atendimentos=Count("pk"),
                    vendas=Count("pk", filter=venda),
                    vendido=Coalesce(Sum("total", filter=venda), Value(ZERO),
                                     output_field=_DINHEIRO),
                    pediu=Count("pk", filter=Q(cliente_pediu=True)),
                    pausa=Coalesce(Subquery(pausas, output_field=DurationField()),
                                   Value(timedelta(0)), output_field=DurationField()))
                .annotate(
                    conversao=Case(When(atendimentos=0, then=Value(None)),
                                   default=ExpressionWrapper(F("vendas") * 100.0 / F("atendimentos"),
                                                             output_field=FloatField()),
                                   output_field=FloatField()),
                    ticket=Case(When(vendas=0, then=Value(None)),
                                default=ExpressionWrapper(F("vendido") / F("vendas"),
                                                          output_field=_DINHEIRO),
                                output_field=_DINHEIRO)))
    if mes is not None:
        from .models import MetaDeVenda

        real = FloatField()
        meta = (do_recorte(MetaDeVenda, recorte)
                .filter(pessoa=OuterRef("vendedor"), filial=OuterRef("filial"), mes=mes)
                .values("valor")[:1])
        consulta = (consulta
                    .annotate(meta=Subquery(meta, output_field=_DINHEIRO))
                    .annotate(pct_meta=Case(
                        When(meta__isnull=True, then=Value(None)),
                        default=ExpressionWrapper(
                            Cast("vendido", real) * 100.0 / Cast("meta", real),
                            output_field=real),
                        output_field=real)))
    return _ConsultaPorLoja(consulta, recorte.lojas)


@dataclass(frozen=True)
class DaLoja:
    loja: object
    numeros: Numeros


@dataclass(frozen=True)
class DaEmpresa:
    empresa: object
    numeros: Numeros


def por_loja(recorte: Recorte) -> "list[DaLoja]":
    """Os números de cada loja do recorte, lado a lado, na ordem do recorte
    (a do seletor). Uma consulta por loja: são poucas, e `numeros` já é a
    conta que o painel usa, então as duas telas não divergem."""
    return [DaLoja(loja, numeros(Recorte(loja.empresa, (loja,), recorte.periodo)))
            for loja in recorte.lojas]


def posicoes_por_vendido(recorte: Recorte) -> "dict[int, int]":
    """A posição de cada pessoa do ranking pelo vendido, qualquer que seja a
    ordem em que a tabela está (spec 2026-09-16, V5): reordenar por conversão
    não pode fazer alguém "subir" para o primeiro lugar. Mesmo vendido, mesma
    posição, e quem atendeu sem vender entra, no fim.

    Em Python, e não com `Rank()` na consulta do ranking: a tabela filtra por
    nome, e uma window function roda DEPOIS do filtro — buscar "Ana" a faria
    virar a primeira. Uma loja tem dezenas de vendedores."""
    venda = Q(resultado=Resultado.VENDEU)
    totais = dict(
        _atendimentos(recorte).values("vendedor")
        .annotate(v=Coalesce(Sum("total", filter=venda), Value(ZERO),
                             output_field=_DINHEIRO))
        .values_list("vendedor", "v"))
    return {pessoa: 1 + sum(1 for outro in totais.values() if outro > v)
            for pessoa, v in totais.items()}


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
