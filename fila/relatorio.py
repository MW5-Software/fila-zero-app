"""O relatório da fila como DADO (28/09/2026, spec
`docs/superpowers/specs/2026-09-28-relatorios-da-fila-design.md`).

Seções com colunas tipadas e linhas, e nada de HTML nem de planilha: o Excel e
o papel (`fila/relatorio_saida.py`) desenham o MESMO dado, e um número não pode
sair de um jeito na planilha e de outro no PDF.

Toda conta sai de `fila/indicadores.py` e `fila/metas.py`, as do painel do
Início. A única consulta nova é a lista de lançamentos
(`indicadores.lancamentos_do_recorte`), que o painel não tem.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, NamedTuple

from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from . import indicadores as ind
from .estado import nome_de
from .metas import mes_do_periodo
from .periodo import periodo_anterior, periodo_do_pedido
from .valores import em_reais

__all__ = ["Coluna", "PADRAO", "PERIODOS", "Relatorio", "Secao", "formatar",
           "chamada_do_periodo", "montar", "periodo_escolhido", "placar"]

#: Os períodos que o cliente pediu ("diário, semanal, mensal, mês passado"),
#: mais o ontem, que é o diário de quem fecha o dia na manhã seguinte. As
#: CHAVES são as de `fila.periodo.ATALHOS`, para o período do relatório ser o
#: mesmo do painel. "Semanal" são os últimos 7 dias (decisão do cliente).
PERIODOS: "tuple[tuple[str, str], ...]" = (
    ("hoje", gettext_lazy("Diário (hoje)")),
    ("ontem", gettext_lazy("Ontem")),
    ("7dias", gettext_lazy("Semanal (últimos 7 dias)")),
    ("mes", gettext_lazy("Mensal (este mês)")),
    ("mes_passado", gettext_lazy("Mês passado")),
)
PADRAO = "mes"


def periodo_escolhido(chave, agora=None):
    """O período do pedido, só entre os do relatório; o resto cai no padrão."""
    if chave not in dict(PERIODOS):
        chave = PADRAO
    return periodo_do_pedido({"periodo": chave}, agora)


@dataclass(frozen=True)
class Coluna:
    rotulo: str
    valor: Callable[[Any], object]
    #: `texto`, `inteiro`, `dinheiro`, `porcento` ou `minutos`. É o que faz o
    #: Excel gravar NÚMERO (somável) e o papel escrever "R$ 1.200,00".
    tipo: str = "texto"


@dataclass(frozen=True)
class Secao:
    titulo: str
    colunas: "tuple[Coluna, ...]"
    linhas: list
    #: Qual seção é, para o papel desenhar cada uma do jeito dela sem depender
    #: do TÍTULO, que é traduzido (28/09/2026).
    chave: str = ""


@dataclass(frozen=True)
class Relatorio:
    titulo: str
    empresa: str
    lojas: str
    periodo: str
    gerado_por: str
    gerado_em: datetime
    secoes: "tuple[Secao, ...]"
    nome_do_arquivo: str
    #: O que o papel precisa além das seções (28/09/2026): os números do
    #: período e do anterior, para o placar, o intervalo em dia local e os
    #: nomes das lojas, para a chamada da capa.
    total: "ind.Numeros | None" = None
    anterior: "ind.Numeros | None" = None
    intervalo: "tuple | None" = None
    nomes_das_lojas: tuple = ()
    #: O período fatia a fatia (`indicadores.por_dia`: por dia, ou por hora
    #: num dia só), para o gráfico do papel.
    serie: tuple = ()
    #: A chave do período (`mes`, `7dias`…), para a chamada da capa.
    chave: str = ""


class LinhaDoResumo(NamedTuple):
    rotulo: str
    numeros: "ind.Numeros"


#: Os meses por extenso, para a chamada da capa. Aqui, e não os do Django:
#: no meio da data ("1 a 28 de setembro") o nome do mês vai em minúscula.
MESES = (gettext_lazy("janeiro"), gettext_lazy("fevereiro"), gettext_lazy("março"),
         gettext_lazy("abril"), gettext_lazy("maio"), gettext_lazy("junho"),
         gettext_lazy("julho"), gettext_lazy("agosto"), gettext_lazy("setembro"),
         gettext_lazy("outubro"), gettext_lazy("novembro"), gettext_lazy("dezembro"))


def _dia_por_extenso(dia, *, com_ano=True) -> str:
    texto = _("%(dia)s de %(mes)s") % {"dia": dia.day, "mes": MESES[dia.month - 1]}
    return _("%(data)s de %(ano)s") % {"data": texto, "ano": dia.year} if com_ano else texto


def _intervalo_por_extenso(de, ate) -> str:
    """"de 1 a 15 de setembro de 2026", "de 25 de agosto a 3 de setembro de
    2026", ou "em 28 de setembro de 2026" quando é um dia só."""
    if de == ate:
        return _("em %(dia)s") % {"dia": _dia_por_extenso(de)}
    if (de.year, de.month) == (ate.year, ate.month):
        inicio = str(de.day)
    else:
        inicio = _dia_por_extenso(de, com_ano=de.year != ate.year)
    return _("de %(de)s a %(ate)s") % {"de": inicio, "ate": _dia_por_extenso(ate)}


def _dias(periodo) -> tuple:
    """O período em dias locais: `ate` é exclusivo, e o último dia é o de
    antes dele."""
    return (timezone.localtime(periodo.de).date(),
            timezone.localtime(periodo.ate - timedelta(microseconds=1)).date())


def _lojas_por_extenso(nomes) -> str:
    """"Matriz e Centro", "A, B e C"; com mais de três, o número: a lista
    inteira de uma rede não cabe numa linha da capa."""
    if len(nomes) > 3:
        return _("%(n)s lojas") % {"n": len(nomes)}
    if len(nomes) <= 1:
        return "".join(nomes)
    return _("%(lista)s e %(ultima)s") % {"lista": ", ".join(nomes[:-1]), "ultima": nomes[-1]}


def _maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def chamada_do_periodo(relatorio: "Relatorio") -> "tuple[str, str]":
    """(título, apoio) da capa: "Setembro de 2026", e embaixo "De 1 a 28 de
    setembro de 2026 · Matriz e Centro". Era uma frase longa com o resultado
    ("…as 2 lojas atenderam 173 clientes e venderam…"), e o cliente a trocou
    por uma chamada no mesmo dia (28/09/2026): os números já estão nos
    cartões logo abaixo, e a frase os dizia duas vezes."""
    de, ate = relatorio.intervalo
    lojas = _lojas_por_extenso(relatorio.nomes_das_lojas)
    if de == ate:
        # Um dia só: a data É o título, e o apoio fica com as lojas.
        return _maiuscula(_dia_por_extenso(de)), lojas
    if relatorio.chave in ("mes", "mes_passado"):
        titulo = _("%(mes)s de %(ano)s") % {"mes": _maiuscula(str(MESES[de.month - 1])),
                                            "ano": de.year}
    else:
        titulo = _("Últimos %(n)s dias") % {"n": (ate - de).days + 1}
    return titulo, f"{_maiuscula(_intervalo_por_extenso(de, ate))} · {lojas}"


class NumeroDoPlacar(NamedTuple):
    rotulo: str
    valor: str
    #: "▲ 12,5%", "▼ 7,3 p.p." ou "" quando não há com o que comparar. A seta
    #: vai junto da cor para o papel impresso em preto e branco.
    variacao: str
    sobe: "bool | None"


def placar(relatorio: "Relatorio") -> "list[NumeroDoPlacar]":
    """Os cinco números do período, cada um com a variação contra o anterior."""
    n, a = relatorio.total, relatorio.anterior

    def um(rotulo, atual, antes, tipo, *, pontos=False):
        v = ind.variacao(atual, antes, pontos=pontos) if a is not None else None
        if v is None or v.valor == 0:
            return NumeroDoPlacar(rotulo, formatar(atual, tipo), "", None)
        numero = f"{abs(v.valor):.1f}".replace(".", ",")
        texto = f"{'▲' if v.sobe else '▼'} {numero}" + (" p.p." if pontos else "%")
        return NumeroDoPlacar(rotulo, formatar(atual, tipo), texto, v.sobe)

    return [
        um(_("Atendimentos"), n.atendimentos, a and a.atendimentos, "inteiro"),
        um(_("Vendas"), n.vendas, a and a.vendas, "inteiro"),
        um(_("Conversão"), n.conversao, a and a.conversao, "porcento", pontos=True),
        um(_("Vendido"), n.vendido, a and a.vendido, "dinheiro"),
        um(_("Ticket médio"), n.ticket, a and a.ticket, "dinheiro"),
    ]


def formatar(valor, tipo: str) -> str:
    """O valor como o papel o escreve. Vazio é "—", como no painel."""
    if valor is None or valor == "":
        return "—"
    if tipo == "dinheiro":
        return em_reais(Decimal(valor))
    if tipo == "porcento":
        return f"{float(valor):.1f}%".replace(".", ",")
    if tipo == "minutos":
        minutos = int(valor.total_seconds() // 60) if isinstance(valor, timedelta) else int(valor)
        return f"{minutos} min"
    return str(valor)


def _minutos(valor) -> int:
    return int(valor.total_seconds() // 60) if isinstance(valor, timedelta) else int(valor or 0)


def _numeros(rotulo_do_onde: str) -> "tuple[Coluna, ...]":
    return (
        Coluna(rotulo_do_onde, lambda l: l.rotulo),
        Coluna(_("Atendimentos"), lambda l: l.numeros.atendimentos, "inteiro"),
        Coluna(_("Vendas"), lambda l: l.numeros.vendas, "inteiro"),
        Coluna(_("Conversão"), lambda l: l.numeros.conversao, "porcento"),
        Coluna(_("Vendido"), lambda l: l.numeros.vendido, "dinheiro"),
        Coluna(_("Ticket médio"), lambda l: l.numeros.ticket, "dinheiro"),
    )


def _resumo(recorte) -> Secao:
    linhas = [LinhaDoResumo(_("Total"), ind.numeros(recorte))]
    linhas += [LinhaDoResumo(str(d.loja), d.numeros) for d in ind.por_loja(recorte)]
    if len(recorte.empresas) > 1:
        linhas += [LinhaDoResumo(str(d.empresa), d.numeros) for d in ind.por_empresa(recorte)]
    return Secao(_("Resumo"), _numeros(_("Onde")), linhas)


def _variacao_por_extenso(valor: float, unidade: str) -> str:
    """"+12,5 %" e "-7,5 p.p.". A vírgula decimal entra SÓ no número: trocar
    o ponto da frase inteira escrevia a unidade da conversão "p,p," (visto
    no PDF salvo pelo Chrome, 28/09/2026)."""
    return f"{valor:+.1f}".replace(".", ",") + f" {unidade}"


def _comparacao(recorte, anterior) -> Secao:
    """Cada indicador neste período, no anterior e a variação. Aba própria
    porque mistura unidades numa coluna só; por isso os valores já vão
    escritos (texto), e não como número."""
    n, a = ind.numeros(recorte), ind.numeros(anterior)

    def var(atual, antes, *, pontos=False):
        v = ind.variacao(atual, antes, pontos=pontos)
        return "—" if v is None else _variacao_por_extenso(v.valor, v.unidade)

    linhas = [
        (_("Atendimentos"), str(n.atendimentos), str(a.atendimentos),
         var(n.atendimentos, a.atendimentos)),
        (_("Vendas"), str(n.vendas), str(a.vendas), var(n.vendas, a.vendas)),
        (_("Conversão"), formatar(n.conversao, "porcento"), formatar(a.conversao, "porcento"),
         var(n.conversao, a.conversao, pontos=True)),
        (_("Vendido"), formatar(n.vendido, "dinheiro"), formatar(a.vendido, "dinheiro"),
         var(n.vendido, a.vendido)),
        (_("Ticket médio"), formatar(n.ticket, "dinheiro"), formatar(a.ticket, "dinheiro"),
         var(n.ticket, a.ticket)),
    ]
    return Secao(_("Comparação"), (
        Coluna(_("Indicador"), lambda l: l[0]),
        Coluna(_("Neste período"), lambda l: l[1]),
        Coluna(_("No período anterior"), lambda l: l[2]),
        Coluna(_("Variação"), lambda l: l[3]),
    ), linhas)


def _vendedores(recorte) -> Secao:
    mes = mes_do_periodo(recorte.periodo)
    linhas = list(ind.ranking_por_loja(recorte, mes).order_by("loja_nome", "-vendido", "nome"))
    colunas = [
        Coluna(_("Loja"), lambda l: l["loja_nome"]),
        Coluna(_("Vendedor"), lambda l: l["nome"]),
        Coluna(_("Atendimentos"), lambda l: l["atendimentos"], "inteiro"),
        Coluna(_("Vendas"), lambda l: l["vendas"], "inteiro"),
        Coluna(_("Conversão"), lambda l: l["conversao"], "porcento"),
        Coluna(_("Vendido"), lambda l: l["vendido"], "dinheiro"),
        Coluna(_("Ticket médio"), lambda l: l["ticket"], "dinheiro"),
        Coluna(_("Cliente pediu"), lambda l: l["pediu"], "inteiro"),
        Coluna(_("Pausa"), lambda l: l["pausa"], "minutos"),
    ]
    # A meta é MENSAL: dividir o vendido de 7 dias pela meta do mês seria um
    # número errado com cara de certo. Fora dos meses, a coluna não existe.
    if mes is not None:
        colunas.append(Coluna(_("% da meta"), lambda l: l.get("pct_meta"), "porcento"))
    return Secao(_("Vendedores"), tuple(colunas), linhas)


def grupos_do_lancamento(atendimento) -> str:
    return "; ".join(f"{i.grupo.nome} {em_reais(i.valor)}" for i in atendimento.itens.all())


def motivo_do_lancamento(a) -> str:
    """O motivo da não venda, e "Fechado sem lançamento" para a do ponto
    esquecido, que não tem motivo. Usado pela planilha e pelo papel."""
    if a.resultado != "nao_vendeu":
        return ""
    return a.motivo.nome if a.motivo_id else str(ind.SEM_LANCAMENTO)


def _lancamentos(recorte) -> Secao:
    def quando(a):
        return timezone.localtime(a.fim).strftime("%d/%m/%Y %H:%M")

    motivo = motivo_do_lancamento

    def fechado_por(a):
        return nome_de(a.fechado_por) if a.fechado_por_id and a.fechado_por_id != a.vendedor_id else ""

    return Secao(_("Lançamentos"), (
        Coluna(_("Data e hora"), quando),
        Coluna(_("Loja"), lambda a: str(a.filial)),
        Coluna(_("Vendedor"), lambda a: nome_de(a.vendedor)),
        Coluna(_("Resultado"), lambda a: _("Vendeu") if a.resultado == "vendeu" else _("Não vendeu")),
        Coluna(_("Valor"), lambda a: a.total if a.resultado == "vendeu" else None, "dinheiro"),
        Coluna(_("Grupos"), grupos_do_lancamento),
        Coluna(_("Motivo"), motivo),
        Coluna(_("Observação"), lambda a: a.observacao),
        Coluna(_("Mídia"), lambda a: a.midia.nome if a.midia_id else ""),
        Coluna(_("Cliente pediu"), lambda a: _("Sim") if a.cliente_pediu else ""),
        Coluna(_("Fechado por"), fechado_por),
    ), list(ind.lancamentos_do_recorte(recorte)))


def _periodo_por_extenso(periodo) -> str:
    rotulo = dict(PERIODOS).get(periodo.chave, periodo.rotulo)
    de = timezone.localtime(periodo.de).strftime("%d/%m/%Y")
    ate = timezone.localtime(periodo.ate - timedelta(microseconds=1)).strftime("%d/%m/%Y")
    return f"{rotulo} · {de}" if de == ate else f"{rotulo} · {de} {_('a')} {ate}"


def montar(recorte, *, rotulo_da_empresa: str, gerado_por: str, agora=None) -> Relatorio:
    agora = agora or timezone.now()
    anterior = ind.Recorte(recorte.empresa, recorte.lojas,
                           periodo_anterior(recorte.periodo, agora), recorte.empresas)
    secoes = tuple(replace(secao, chave=chave) for chave, secao in (
        ("resumo", _resumo(recorte)),
        ("comparacao", _comparacao(recorte, anterior)),
        ("vendedores", _vendedores(recorte)),
        ("motivos", Secao(_("Motivos"), (Coluna(_("Motivo"), lambda l: l[0]),
                                         Coluna(_("Atendimentos"), lambda l: l[1], "inteiro")),
                          ind.motivos(recorte))),
        ("midias", Secao(_("Mídias"), (
            Coluna(_("Mídia"), lambda l: l[0]),
            Coluna(_("Atendimentos"), lambda l: l[1], "inteiro"),
            Coluna(_("Vendas"), lambda l: l[2], "inteiro"),
            Coluna(_("Conversão"), lambda l: 100 * l[2] / l[1] if l[1] else None, "porcento"),
        ), ind.midias(recorte))),
        ("grupos", Secao(_("Grupos"), (Coluna(_("Grupo de item"), lambda l: l[0]),
                                       Coluna(_("Vendido"), lambda l: l[1], "dinheiro")),
                         ind.por_grupo(recorte))),
        ("pausas", Secao(_("Pausas"), (Coluna(_("Tipo de pausa"), lambda l: l[0]),
                                       Coluna(_("Minutos"), lambda l: l[1], "inteiro")),
                         ind.pausa_por_tipo(recorte))),
        ("lancamentos", _lancamentos(recorte)),
    ))
    lojas = ", ".join(str(l) for l in recorte.lojas)
    return Relatorio(
        # O nome do item do menu (28/09/2026, pedido do cliente: "mudar o nome
        # do relatório para o nome dos menus novos"); era "Relatório da fila".
        titulo=_("Relatórios gerais"), empresa=rotulo_da_empresa, lojas=lojas,
        periodo=_periodo_por_extenso(recorte.periodo), gerado_por=gerado_por,
        gerado_em=agora, secoes=secoes,
        # O sublinhado da chave vira hífen: "mes_passado" num nome de arquivo
        # em que todo o resto é separado por hífen parecia outro campo.
        nome_do_arquivo=slugify(f"relatorio-{rotulo_da_empresa}-"
                                f"{recorte.periodo.chave.replace('_', '-')}-"
                                f"{timezone.localtime(agora):%Y-%m-%d}"),
        total=ind.numeros(recorte), anterior=ind.numeros(anterior),
        intervalo=_dias(recorte.periodo),
        nomes_das_lojas=tuple(str(l) for l in recorte.lojas),
        serie=tuple(ind.por_dia(recorte)), chave=recorte.periodo.chave)
