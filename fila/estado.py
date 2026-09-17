"""A fila de uma loja, lida: quem atende, quem espera (em ordem), quem pausa.

Tudo aqui lê por `objects.da_empresa(filial.empresa)` e filtra pela loja: a
consulta que esquecesse a loja traria a fila da empresa inteira, e a que
esquecesse a empresa viria vazia (`contas/inquilino.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db.models import BooleanField, Count, ExpressionWrapper, Max, Q, Sum

from .models import Estado, LugarNaFila, Pausa

__all__ = ["Linha", "Retrato", "na_fila", "nome_de", "posicao_de",
           "retrato", "versao_da_fila"]


def nome_de(pessoa) -> str:
    return (getattr(pessoa, "nome", "") or "").strip() or pessoa.email


def _da_loja(filial):
    return LugarNaFila.objects.da_empresa(filial.empresa).filter(filial=filial)


def na_fila(filial):
    """Quem espera, em ordem. O `pk` desempata o improvável empate de hora,
    para a ordem nunca depender de como o banco devolveu as linhas."""
    return (_da_loja(filial).filter(estado=Estado.NA_FILA)
            .select_related("pessoa").defer("pessoa__avatar")
            .order_by("na_fila_desde", "pk"))


def posicao_de(lugar) -> "int | None":
    if lugar.estado != Estado.NA_FILA:
        return None
    for posicao, pk in enumerate(na_fila(lugar.filial).values_list("pk", flat=True), 1):
        if pk == lugar.pk:
            return posicao
    return None


def versao_da_fila(filial) -> str:
    """Muda a cada gravação na fila desta loja, e só então (spec, D8).

    Toda ação grava `desde` (e voltar para a fila grava `na_fila_desde`), e
    sair da loja apaga a linha: quantas linhas há e o maior dos dois instantes
    bastam. Não precisa de tabela de versão, que seria mais uma escrita por
    clique e mais uma coisa para esquecer de atualizar.
    """
    dados = _da_loja(filial).aggregate(
        linhas=Count("pk"), desde=Max("desde"), fila=Max("na_fila_desde"))
    hoje = _lancamentos_de_hoje(filial).aggregate(
        n=Count("pk"), total=Sum("total"), motivos=Sum("motivo_id"))

    def marca(instante: "datetime | None") -> str:
        return str(int(instante.timestamp() * 1_000_000)) if instante else "0"

    # A meta do mês aparece em "Seus números": o gerente que troca uma meta
    # precisa ver a tela do vendedor mudar sem ele recarregar (spec das metas).
    from django.utils import timezone

    from .models import MetaDeVenda

    metas = (MetaDeVenda.objects.da_empresa(filial.empresa)
             .filter(filial=filial, mes=timezone.localdate().replace(day=1))
             .aggregate(n=Count("pk"), quando=Max("alterada_em")))

    # Mover grava um instante ENTRE os vizinhos, que não muda o maior
    # `na_fila_desde` nem o maior `desde`: sem contar as correções, as outras
    # telas não veriam a ordem nova (spec 2026-09-17).
    from .models import CorrecaoNaFila

    correcoes = (CorrecaoNaFila.objects.da_empresa(filial.empresa)
                 .filter(filial=filial)
                 .aggregate(n=Count("pk"), quando=Max("momento")))

    return (f"{dados['linhas']}.{marca(dados['desde'])}.{marca(dados['fila'])}"
            f".{hoje['n']}.{hoje['total'] or 0}.{hoje['motivos'] or 0}"
            f".{metas['n']}.{marca(metas['quando'])}"
            f".{correcoes['n']}.{marca(correcoes['quando'])}")


def _lancamentos_de_hoje(filial):
    """Os atendimentos fechados hoje na loja, para a versão: a correção do
    gerente não mexe na fila, e sem isto os lançamentos e o "Seus números" das
    outras telas ficavam velhos até alguém mexer na fila (revisão final,
    15/09/2026). Total e motivo pegam a correção de valor, de grupo e de
    motivo; só a da observação sozinha passa sem mudar a versão."""
    from django.utils import timezone

    from .models import Atendimento
    from .periodo import inicio_do_dia

    return (Atendimento.objects.da_empresa(filial.empresa)
            .filter(filial=filial, fim__gte=inicio_do_dia(timezone.localdate())))


@dataclass(frozen=True)
class Linha:
    pessoa_id: int
    nome: str
    estado: str
    desde: datetime
    posicao: "int | None"
    tipo_de_pausa: str
    e_voce: bool
    #: Se a pessoa tem foto (`/avatar/<id>`). Só o "tem", e não os bytes:
    #: a consulta de 3 em 3 segundos não pode carregar imagem.
    tem_foto: bool = False


@dataclass(frozen=True)
class Retrato:
    versao: str
    atendendo: "list[Linha]"
    fila: "list[Linha]"
    em_pausa: "list[Linha]"
    #: Fora da fila, com o ponto aberto (spec 2026-09-17). Ordenada por
    #: `desde`, como a pausa: quem está em espera não tem posição.
    em_espera: "list[Linha]"
    meu: "Linha | None"


def retrato(filial, pessoa) -> Retrato:
    """A loja inteira numa leitura. `pessoa` pode ser `None` (quem só vê)."""
    pessoa_id = getattr(pessoa, "pk", None)
    lugares = list(
        _da_loja(filial).select_related("pessoa").defer("pessoa__avatar")
        .annotate(tem_foto=ExpressionWrapper(
            Q(pessoa__avatar__isnull=False), output_field=BooleanField()))
        .order_by("na_fila_desde", "pk"))
    tipos = dict(Pausa.objects.da_empresa(filial.empresa)
                 .filter(filial=filial, fim__isnull=True)
                 .values_list("pessoa_id", "tipo__nome"))
    posicao = 0
    atendendo, fila, em_pausa, em_espera = [], [], [], []
    for lugar in lugares:
        if lugar.estado == Estado.NA_FILA:
            posicao += 1
        linha = Linha(
            pessoa_id=lugar.pessoa_id, nome=nome_de(lugar.pessoa),
            estado=lugar.estado, desde=lugar.desde,
            posicao=posicao if lugar.estado == Estado.NA_FILA else None,
            tipo_de_pausa=tipos.get(lugar.pessoa_id, ""),
            e_voce=lugar.pessoa_id == pessoa_id, tem_foto=lugar.tem_foto)
        {Estado.NA_FILA: fila, Estado.ATENDENDO: atendendo,
         Estado.EM_PAUSA: em_pausa,
         Estado.EM_ESPERA: em_espera}[lugar.estado].append(linha)
    atendendo.sort(key=lambda l: l.desde)
    em_pausa.sort(key=lambda l: l.desde)
    em_espera.sort(key=lambda l: l.desde)
    meu = next((l for l in (*atendendo, *fila, *em_pausa, *em_espera)
                if l.e_voce), None)
    return Retrato(versao=versao_da_fila(filial), atendendo=atendendo,
                   fila=fila, em_pausa=em_pausa, em_espera=em_espera, meu=meu)
