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

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .periodo import ANOS_ACEITOS

__all__ = ["Acompanhamento", "Linha", "MES_ENCERRADO", "MetaDoRecorte", "ValoresInvalidos",
           "acompanhar", "copiar_do_anterior", "gravar", "lojas_com_metas",
           "mes_anterior", "mes_do_texto", "mes_do_periodo", "mes_encerrado", "mes_seguinte", "meta_do_recorte",
           "meta_da_loja", "pessoas_da_lista", "primeiro_do_mes",
           "ultimo_do_mes", "valor_do_campo"]

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


#: `gettext_lazy`: constante de módulo, lida no idioma de quem abre a tela.
MES_ENCERRADO = gettext_lazy("Mês encerrado: as metas não se editam mais.")


def lojas_com_metas(pessoa, empresa) -> list:
    from .indicadores import lojas_com_permissao

    return lojas_com_permissao(pessoa, empresa, "fila.metas")


def _metas_do_mes(loja, mes):
    from .models import MetaDeVenda

    return MetaDeVenda.objects.da_empresa(loja.empresa).filter(filial=loja, mes=mes)


def meta_da_loja(loja, mes) -> "Decimal | None":
    return (_metas_do_mes(loja, mes).filter(pessoa__isnull=True)
            .values_list("valor", flat=True).first())


@dataclass(frozen=True)
class Linha:
    pessoa: object
    valor: "Decimal | None"
    na_loja: bool
    propria: bool


def _participa(pessoa, loja) -> bool:
    from contas.lugar import permissoes_em

    return bool({"fila.participar", "fila.*"}
                & permissoes_em(pessoa, loja.empresa, loja))


def pessoas_da_lista(loja, mes, editor) -> "list[Linha]":
    """Quem tem meta de pessoa nesta loja e mês (decisão P-5 do plano):

    - quem está alocado na loja (ou na empresa inteira) e, NESTE lugar,
      participa da fila;
    - mais quem já tem meta aqui neste mês e não está mais na loja: a meta
      continua valendo, e sumir com ela da tela a esconderia de quem edita.

    O titular não entra: não tem alocação, e a meta é de quem trabalha na fila.
    """
    from contas.models import Usuario

    valores = dict(_metas_do_mes(loja, mes).filter(pessoa__isnull=False)
                   .values_list("pessoa_id", "valor"))
    candidatas = (Usuario.objects
                  .filter(Q(alocacoes__filial=loja)
                          | Q(alocacoes__empresa=loja.empresa,
                              alocacoes__filial__isnull=True))
                  .filter(is_active=True).distinct().defer("avatar"))
    na_loja = {p.pk: p for p in candidatas if _participa(p, loja)}
    sairam = Usuario.objects.filter(pk__in=set(valores) - set(na_loja)).defer("avatar")
    linhas = [Linha(p, valores.get(p.pk), True, p.pk == editor.pk)
              for p in na_loja.values()]
    linhas += [Linha(p, valores[p.pk], False, p.pk == editor.pk) for p in sairam]
    return sorted(linhas, key=lambda l: ((l.pessoa.nome or l.pessoa.email).lower(),
                                         l.pessoa.pk))


def valor_do_campo(valor: "Decimal | None") -> str:
    return "" if valor is None else f"{valor:.2f}".replace(".", ",")


class ValoresInvalidos(Exception):
    """Algum valor não serve; `erros` diz qual campo e por quê. Nada foi
    gravado: meia tela salva deixaria a loja com metas que ninguém conferiu."""

    def __init__(self, erros: "dict[str, str]"):
        super().__init__("valores inválidos")
        self.erros = erros


def _ler(texto: str) -> "tuple[Decimal | None, str | None]":
    """(valor, erro). Vazio é (None, None): apagar a meta."""
    from .acoes import MAIOR_VALOR
    from .valores import ler_valor

    if not texto.strip():
        return None, None
    valor = ler_valor(texto)
    if valor is None:
        return None, _("Digite um valor em reais.")
    if valor <= ZERO:
        return None, _("A meta precisa ser maior que zero.")
    if valor > MAIOR_VALOR:
        return None, _("Valor alto demais.")
    return valor, None


def _alvo(loja, pessoa, mes) -> str:
    from .estado import nome_de

    quem = nome_de(pessoa) if pessoa is not None else "a loja"
    return f"{loja}: {quem} em {mes:%m/%Y}"


def gravar(loja, mes, editor, valores: "dict[str, str | None]", *,
           agora: "datetime | None" = None, request=None) -> int:
    """Grava as metas do mês desta loja, tudo ou nada.

    Só as chaves da lista montada AQUI valem (decisão P-3 do plano): a da
    loja e a de cada pessoa da lista que não é quem edita. Campo ausente não
    mexe (P-4); vazio apaga. A linha da loja é trancada, como na fila: dois
    gerentes salvando juntos estourariam a trava do banco com 500.
    """
    from comum.auditoria import ACOES, registrar

    from .acoes import Recusa, _travar
    from .models import MetaDeVenda

    if mes_encerrado(mes, agora):
        raise Recusa(str(MES_ENCERRADO))
    alvos: "dict[str, object | None]" = {"loja": None}
    for linha in pessoas_da_lista(loja, mes, editor):
        if not linha.propria:
            alvos[str(linha.pessoa.pk)] = linha.pessoa

    lidos, erros = {}, {}
    for chave in alvos:
        texto = valores.get(chave)
        if texto is None:
            continue
        valor, erro = _ler(texto)
        if erro:
            erros[chave] = erro
        else:
            lidos[chave] = valor
    if erros:
        raise ValoresInvalidos(erros)

    mudancas = 0
    with transaction.atomic():
        _travar(loja)
        for chave, valor in lidos.items():
            pessoa = alvos[chave]
            atual = _metas_do_mes(loja, mes).filter(pessoa=pessoa).first()
            antes = valor_do_campo(atual.valor) if atual else "sem meta"
            if valor is None:
                if atual is None:
                    continue
                atual.delete()
                registrar(ACOES.FILA_META_REMOVIDA, editor,
                          alvo=_alvo(loja, pessoa, mes), detalhe=f"era {antes}",
                          request=request)
            elif atual is None or atual.valor != valor:
                if atual is None:
                    MetaDeVenda.objects.create(empresa=loja.empresa, filial=loja,
                                               pessoa=pessoa, mes=mes, valor=valor)
                else:
                    atual.valor = valor
                    atual.save(update_fields=["valor", "alterada_em"])
                registrar(ACOES.FILA_META_DEFINIDA, editor,
                          alvo=_alvo(loja, pessoa, mes),
                          detalhe=f"{valor_do_campo(valor)}; era {antes}",
                          request=request)
            else:
                continue
            mudancas += 1
    return mudancas


def copiar_do_anterior(loja, mes, linhas: "list[Linha]") -> "dict[str, str]":
    """O que o mês anterior tinha, só para os campos vazios deste mês.

    Não grava (M6): a pessoa confere e salva. A meta que já existe neste mês
    não é trocada. Quem saiu da loja não volta a ter meta por cópia: ele só
    está em `linhas` quando já tem meta neste mês, e aí o campo não é vazio.
    """
    anterior = mes_anterior(mes)
    antes = dict(_metas_do_mes(loja, anterior).filter(pessoa__isnull=False)
                 .values_list("pessoa_id", "valor"))
    copia = {}
    if meta_da_loja(loja, mes) is None:
        da_loja = meta_da_loja(loja, anterior)
        if da_loja is not None:
            copia["loja"] = valor_do_campo(da_loja)
    for linha in linhas:
        if linha.valor is None and linha.pessoa.pk in antes:
            copia[str(linha.pessoa.pk)] = valor_do_campo(antes[linha.pessoa.pk])
    return copia


def mes_do_periodo(periodo) -> "date | None":
    """O mês do calendário do período, se ele for um mês inteiro dos atalhos.
    Em "7 dias" ou num intervalo, a meta do mês não tem com o que comparar."""
    if periodo.chave not in ("mes", "mes_passado"):
        return None
    return timezone.localdate(periodo.de).replace(day=1)


@dataclass(frozen=True)
class MetaDoRecorte:
    acompanhamento: Acompanhamento
    lojas_com_meta: int
    lojas: int
    soma_vendedores: Decimal


def meta_do_recorte(recorte, agora: "datetime | None" = None) -> "MetaDoRecorte | None":
    """A meta das lojas do recorte contra o vendido DESSAS lojas.

    Em "Todas as lojas" com uma loja sem meta, somar a meta das outras e
    comparar com o vendido de todas faria a meta parecer batida por causa da
    loja sem meta; por isso as duas pontas saem das mesmas lojas.
    """
    from .indicadores import Recorte, numeros
    from .models import MetaDeVenda
    from .periodo import Periodo, inicio_do_dia

    agora = agora or timezone.now()
    mes = mes_do_periodo(recorte.periodo)
    if mes is None:
        return None
    por_loja = dict(MetaDeVenda.objects.da_empresa(recorte.empresa)
                    .filter(filial__in=recorte.lojas, mes=mes, pessoa__isnull=True)
                    .values_list("filial_id", "valor"))
    if not por_loja:
        return None
    com_meta = tuple(l for l in recorte.lojas if l.pk in por_loja)
    # M2: o painel diz se as metas dos vendedores cobrem a da loja.
    soma_vendedores = sum(
        MetaDeVenda.objects.da_empresa(recorte.empresa)
        .filter(filial__in=com_meta, mes=mes, pessoa__isnull=False)
        .values_list("valor", flat=True), ZERO)
    vendido = numeros(Recorte(recorte.empresa, com_meta, recorte.periodo)).vendido
    ate_ontem = None
    if recorte.periodo.ate > agora:
        ontem = Periodo(recorte.periodo.de, inicio_do_dia(timezone.localdate(agora)),
                        "intervalo", "")
        ate_ontem = numeros(Recorte(recorte.empresa, com_meta, ontem)).vendido
    return MetaDoRecorte(
        acompanhar(sum(por_loja.values(), ZERO), vendido, mes, agora, ate_ontem),
        len(com_meta), len(recorte.lojas), soma_vendedores)
