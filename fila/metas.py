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
           "mes_anterior", "mes_do_texto", "mes_do_periodo", "mes_encerrado", "mes_seguinte", "meta_da_pessoa", "meta_do_recorte",
           "meta_da_loja", "metas_do_mes", "pessoas_da_lista", "primeiro_do_mes",
           "Ritmo", "repartir", "ritmo",
           "ultimo_do_mes", "valor_do_campo", "vendido_no_mes"]

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
    """Quem desta loja entra na lista da meta: quem ATENDE nela.

    Atende quem bate ponto, e quem gerencia a loja não atende
    (`fila/quem_atende.py`, 18/09/2026): o gerente e o supervisor ficam fora da
    lista, e o dono da conta nunca esteve nela — ela sai das alocações, e ele
    não tem uma.

    O parâmetro `meta_para_gestor` (padrão NÃO) devolve a meta a quem gerencia,
    para a loja em que o gerente também vende. É por isso que a decisão é
    parâmetro, e não código: é operação do cliente, e não arquitetura.
    """
    from contas.lugar import permissoes_em
    from plataforma.parametro_catalogo import valor_de

    from .quem_atende import atende

    permissoes = permissoes_em(pessoa, loja.empresa, loja)
    if atende(permissoes):
        return True
    # Quem não atende e não gerencia a loja (Representante, Cliente) fica fora
    # com o parâmetro ligado ou desligado: a meta é de quem trabalha na loja.
    if not {"fila.gerenciar", "fila.*"} & permissoes:
        return False
    return valor_de("meta_para_gestor")


def pessoas_da_lista(loja, mes, editor) -> "list[Linha]":
    """Quem tem meta de pessoa nesta loja e mês (decisão P-5 do plano):

    - quem está alocado na loja (ou na empresa inteira) e, NESTE lugar,
      atende a fila (`_participa`: bate ponto quem atende, e quem gerencia a
      loja não atende);
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
    """O valor no campo, como a máscara o deixaria ("180.000,00"). Sem o ponto
    de milhar, o primeiro dígito digitado reformatava o campo inteiro na cara
    de quem edita (17/09/2026)."""
    from .valores import em_reais

    return "" if valor is None else em_reais(valor)[3:]


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
    linhas = pessoas_da_lista(loja, mes, editor)
    alvos: "dict[str, object | None]" = {"loja": None}
    for linha in linhas:
        if not linha.propria:
            alvos[str(linha.pessoa.pk)] = linha.pessoa
    valores = _distribuir(loja, mes, linhas, valores)

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


def metas_do_mes(loja, mes) -> "dict[int | None, Decimal]":
    """As metas da loja no mês, pela pessoa (`None` é a da loja). A tela mostra
    a do mês anterior embaixo de cada campo, como referência."""
    return dict(_metas_do_mes(loja, mes).values_list("pessoa_id", "valor"))


def vendido_no_mes(loja, mes) -> "dict[int, Decimal]":
    """O vendido de cada pessoa NESTA loja no mês, pela hora do fim, como o
    ranking. Só quem vendeu aparece."""
    from django.db.models import Sum

    from .indicadores import _atendimentos, recorte_do_mes
    from .models import Resultado

    return dict(_atendimentos(recorte_do_mes(loja.empresa, (loja,), mes))
                .filter(resultado=Resultado.VENDEU).order_by()
                .values("vendedor").annotate(v=Sum("total"))
                .values_list("vendedor", "v"))


def repartir(total: Decimal, partes: int) -> "list[Decimal]":
    """`total` em `partes` que somam exatamente `total`. O centavo que sobra
    da divisão vai para as primeiras: 100 em 3 é 33,34 + 33,33 + 33,33, e não
    três 33,33 que deixariam a loja um centavo descoberta."""
    centavos = int((total / CENTAVO).to_integral_value(ROUND_HALF_UP))
    base, sobra = divmod(centavos, partes)
    return [Decimal(base + (1 if i < sobra else 0)) * CENTAVO for i in range(partes)]


def _distribuir(loja, mes, linhas: "list[Linha]",
                valores: "dict[str, str | None]") -> "dict[str, str | None]":
    """A meta da loja vira meta individual IGUAL para quem ficou em branco.

    Sem botão e sem JavaScript (18/09/2026, pedido do cliente): quem digita a
    meta geral e salva já deixou a loja distribuída, e depois acerta um por um
    à mão — quem tem valor digitado fica com o dele, e a distribuição não passa
    por cima.

    **Só quando a meta da loja é DEFINIDA ou MUDA nesta gravação.** O campo em
    branco quer dizer "apagar" nas gravações em que ela não mudou, e sem esta
    distinção não haveria mais como tirar a meta de uma pessoa sem tirar a da
    loja junto — ou seja, a distribuição automática comeria a remoção (M6).

    A parte é `meta da loja / nº de vendedores ATIVOS`, o mesmo número para
    todos, e o centavo que não divide vai para os primeiros (`repartir`). Quem
    saiu da loja não recebe nada: a meta dele é o que já estava lá.
    Campo ausente do POST não é campo vazio — não se mexe nele (P-4).
    """
    da_loja, erro = _ler(valores.get("loja") or "")
    if da_loja is None or erro or meta_da_loja(loja, mes) == da_loja:
        return valores
    ativos = [linha for linha in linhas if linha.na_loja and not linha.propria]
    # Loja sem vendedor ativo (a que acabou de nascer, ou a que ficou só com
    # quem já saiu): não há por quem dividir, e `repartir(x, 0)` estouraria a
    # tela com 500 no primeiro salvamento da meta da loja.
    if not ativos:
        return valores
    campos = dict(valores)
    for linha, parte in zip(ativos, repartir(da_loja, len(ativos))):
        chave = str(linha.pessoa.pk)
        if chave in valores and not (campos.get(chave) or "").strip() and parte:
            campos[chave] = valor_do_campo(parte)
    return campos


@dataclass(frozen=True)
class Ritmo:
    """A barra de uma meta na tela. `esperado` é onde a barra deveria estar
    hoje para bater a meta no fim do mês (o traço dentro dela)."""

    estado: str   # sem_meta | futuro | no_ritmo | atras | bateu | nao_bateu
    pct: "float | None" = None
    esperado: "float | None" = None

    @property
    def largura(self) -> float:
        return min(self.pct or 0.0, 100.0)


#: Abaixo desta fração do esperado, a pessoa está "atrás". A folga existe
#: porque venda não é linear: sábado vende o que a terça não vendeu, e a barra
#: vermelha toda terça seria alarme que ninguém mais lê.
FOLGA_DO_RITMO = 0.85


def ritmo(meta: "Decimal | None", vendido: Decimal, mes: date,
          agora: "datetime | None" = None) -> Ritmo:
    if meta is None:
        return Ritmo("sem_meta")
    hoje = _hoje(agora)
    atual = primeiro_do_mes(hoje)
    if mes > atual:
        return Ritmo("futuro")
    pct = round(float(vendido * 100 / meta), 1)
    if mes < atual:
        return Ritmo("bateu" if vendido >= meta else "nao_bateu", pct)
    esperado = round(100 * hoje.day / ultimo_do_mes(mes).day, 1)
    if vendido >= meta:
        return Ritmo("bateu", pct, esperado)
    return Ritmo("no_ritmo" if pct >= esperado * FOLGA_DO_RITMO else "atras", pct, esperado)


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


def _vendido_ate_ontem(empresa, lojas, periodo, agora, vendedor=None) -> "Decimal | None":
    """O vendido do período até o fim de ontem, para a projeção (M5). `None`
    em período terminado: mês encerrado não tem ritmo."""
    from .indicadores import Recorte, numeros
    from .periodo import Periodo, inicio_do_dia

    if periodo.ate <= agora:
        return None
    ontem = Periodo(periodo.de, inicio_do_dia(timezone.localdate(agora)), "intervalo", "")
    return numeros(Recorte(empresa, lojas, ontem), vendedor=vendedor).vendido


def meta_do_recorte(recorte, agora: "datetime | None" = None) -> "MetaDoRecorte | None":
    """A meta das lojas do recorte contra o vendido DESSAS lojas.

    Em "Todas as lojas" com uma loja sem meta, somar a meta das outras e
    comparar com o vendido de todas faria a meta parecer batida por causa da
    loja sem meta; por isso as duas pontas saem das mesmas lojas.
    """
    from .indicadores import Recorte, numeros
    from .models import MetaDeVenda

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
    ate_ontem = _vendido_ate_ontem(recorte.empresa, com_meta, recorte.periodo, agora)
    return MetaDoRecorte(
        acompanhar(sum(por_loja.values(), ZERO), vendido, mes, agora, ate_ontem),
        len(com_meta), len(recorte.lojas), soma_vendedores)


def meta_da_pessoa(recorte, pessoa, agora: "datetime | None" = None) -> "MetaDoRecorte | None":
    """A meta de `pessoa` nas lojas do recorte contra o vendido DELA nelas: o
    painel do vendedor (spec 2026-09-16). A meta da loja não entra: ela não é
    a régua de ninguém em particular.

    Devolve o mesmo `MetaDoRecorte` do painel da gestão, para a mesma faixa
    desenhar os dois, com as lojas todas "com meta" e sem soma de vendedores:
    as frases de cobertura e de "N de M lojas" são conversa da gestão.
    """
    from .indicadores import numeros
    from .models import MetaDeVenda

    agora = agora or timezone.now()
    mes = mes_do_periodo(recorte.periodo)
    if mes is None:
        return None
    valores = list(MetaDeVenda.objects.da_empresa(recorte.empresa)
                   .filter(filial__in=recorte.lojas, mes=mes, pessoa=pessoa)
                   .values_list("valor", flat=True))
    if not valores:
        return None
    vendido = numeros(recorte, vendedor=pessoa).vendido
    ate_ontem = _vendido_ate_ontem(recorte.empresa, recorte.lojas, recorte.periodo,
                                   agora, vendedor=pessoa)
    lojas = len(recorte.lojas)
    return MetaDoRecorte(acompanhar(sum(valores, ZERO), vendido, mes, agora, ate_ontem),
                         lojas, lojas, ZERO)
