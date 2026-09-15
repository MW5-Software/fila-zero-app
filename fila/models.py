"""As tabelas da fila da vez. Ver o spec de 15/09/2026.

Toda tabela herda `ModeloDaEmpresa`: a Sylvia Design é UMA conta nesta
instalação, mas a regra do inquilino não pergunta quantas contas há hoje.

**O estado de agora e o histórico são tabelas separadas.** `LugarNaFila` é uma
linha por pessoa presente, e é só ela que a consulta de 3 em 3 segundos lê:
poucas linhas por loja, sempre rápidas. `Presenca`, `Atendimento` e `Pausa`
crescem para sempre e só são escritas quando algo acontece.

**Os "um aberto por pessoa" são restrições do banco**, e não só da tela: quem
grava por fora (um shell, uma migração, a próxima tela) não passa.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from contas.inquilino import ModeloDaEmpresa

__all__ = [
    "Atendimento", "Estado", "GrupoDeItem", "ItemVendido", "LugarNaFila",
    "MotivoDeNaoVenda", "Pausa", "Presenca", "Resultado", "TipoDePausa",
]


class Estado(models.TextChoices):
    NA_FILA = "na_fila", _("Na fila")
    ATENDENDO = "atendendo", _("Atendendo")
    EM_PAUSA = "em_pausa", _("Em pausa")


class Resultado(models.TextChoices):
    VENDEU = "vendeu", _("Vendeu")
    NAO_VENDEU = "nao_vendeu", _("Não vendeu")


class Cadastro(ModeloDaEmpresa):
    """O que os três cadastros têm em comum.

    **Cadastro usado não se apaga, desativa.** Os lançamentos apontam para ele
    com `PROTECT`: apagar o motivo "Só olhando" apagaria a razão de cem não
    vendas do ano passado, e o dashboard perderia a pergunta que ele existe
    para responder.
    """

    nome = models.CharField(_("nome"), max_length=80)
    ordem = models.PositiveIntegerField(_("ordem"), default=0)
    ativo = models.BooleanField(_("ativo"), default=True)

    # A `Meta` herda a do `ModeloDaEmpresa` por extenso: declarar uma `Meta`
    # nova sem herdar perde `default_manager_name`, e o backup exportaria zero
    # linhas destas tabelas (ver `contas/inquilino.py`).
    class Meta(ModeloDaEmpresa.Meta):
        abstract = True
        ordering = ("ordem", "nome")
        constraints = [
            # Sem diferença de caixa: "Sofás" e "SOFÁS" na mesma lista de
            # opções é o vendedor escolhendo ao acaso, e o dashboard contando
            # dois grupos que são um.
            models.UniqueConstraint(
                Lower("nome"), "empresa",
                name="%(app_label)s_%(class)s_nome_unico"),
        ]

    def __str__(self) -> str:
        return self.nome


class GrupoDeItem(Cadastro):
    class Meta(Cadastro.Meta):
        verbose_name = _("grupo de item")
        verbose_name_plural = _("grupos de item")


class MotivoDeNaoVenda(Cadastro):
    class Meta(Cadastro.Meta):
        verbose_name = _("motivo de não venda")
        verbose_name_plural = _("motivos de não venda")


class TipoDePausa(Cadastro):
    class Meta(Cadastro.Meta):
        verbose_name = _("tipo de pausa")
        verbose_name_plural = _("tipos de pausa")


def _pessoa(verbose, **extra):
    """FK para o usuário com `PROTECT`: o histórico da loja não some quando a
    pessoa sai da empresa. Quem sai é desativado (desvio D-5 do plano)."""
    return models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=verbose,
                             on_delete=models.PROTECT, related_name="+",
                             **extra)


def _loja():
    return models.ForeignKey("plataforma.Filial", verbose_name=_("loja"),
                             on_delete=models.PROTECT, related_name="+")


class Presenca(ModeloDaEmpresa):
    """O ponto: a pessoa chegou na loja e está disponível para a fila (D1).

    Não é controle de jornada e não tem relatório de horas.
    """

    pessoa = _pessoa(_("pessoa"))
    filial = _loja()
    entrada = models.DateTimeField(_("entrada"))
    saida = models.DateTimeField(_("saída"), null=True, blank=True)
    #: Preenchido só quando quem fechou foi o gerente (D7).
    fechada_por = _pessoa(_("fechada por"), null=True, blank=True)

    class Meta(ModeloDaEmpresa.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa"], condition=Q(saida__isnull=True),
                name="fila_uma_presenca_aberta_por_pessoa"),
        ]


class LugarNaFila(ModeloDaEmpresa):
    """Onde a pessoa está AGORA. Nasce no ponto e some quando ela sai da loja.

    **A ordem da fila é `na_fila_desde` crescente entre quem está `na_fila`.**
    Voltar para o fim (D2) é gravar a hora de agora; não há número de posição
    guardado, porque um número guardado precisaria ser renumerado a cada
    saída, e renumerar sob concorrência é onde as filas se perdem.
    """

    pessoa = models.OneToOneField(settings.AUTH_USER_MODEL,
                                  verbose_name=_("pessoa"),
                                  on_delete=models.PROTECT, related_name="+")
    filial = _loja()
    presenca = models.ForeignKey(Presenca, verbose_name=_("presença"),
                                 on_delete=models.PROTECT, related_name="+")
    estado = models.CharField(_("estado"), max_length=12,
                              choices=Estado.choices, default=Estado.NA_FILA)
    na_fila_desde = models.DateTimeField(_("na fila desde"))
    #: Quando entrou no estado atual, para o "há quanto tempo" da tela.
    desde = models.DateTimeField(_("desde"))

    class Meta(ModeloDaEmpresa.Meta):
        indexes = [models.Index(fields=["filial", "estado", "na_fila_desde"],
                                name="fila_lugar_ordem")]


class Atendimento(ModeloDaEmpresa):
    filial = _loja()
    vendedor = _pessoa(_("vendedor"))
    presenca = models.ForeignKey(Presenca, verbose_name=_("presença"),
                                 on_delete=models.PROTECT, related_name="+")
    inicio = models.DateTimeField(_("início"))
    fim = models.DateTimeField(_("fim"), null=True, blank=True)
    #: Aberto por "Cliente pediu por mim" (D3): o dashboard não conta como vez
    #: furada.
    cliente_pediu = models.BooleanField(_("cliente pediu"), default=False)
    resultado = models.CharField(_("resultado"), max_length=12, blank=True,
                                 choices=Resultado.choices)
    motivo = models.ForeignKey(MotivoDeNaoVenda, verbose_name=_("motivo"),
                               on_delete=models.PROTECT, null=True,
                               blank=True, related_name="+")
    observacao = models.CharField(_("observação"), max_length=280,
                                  blank=True)
    total = models.DecimalField(_("total"), max_digits=12, decimal_places=2,
                                default=Decimal("0"))
    fechado_por = _pessoa(_("fechado por"), null=True, blank=True)

    class Meta(ModeloDaEmpresa.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["vendedor"], condition=Q(fim__isnull=True),
                name="fila_um_atendimento_aberto_por_vendedor"),
        ]
        indexes = [models.Index(fields=["filial", "fim"],
                                name="fila_atendimento_do_dia")]


class ItemVendido(ModeloDaEmpresa):
    atendimento = models.ForeignKey(Atendimento, verbose_name=_("atendimento"),
                                    on_delete=models.CASCADE,
                                    related_name="itens")
    grupo = models.ForeignKey(GrupoDeItem, verbose_name=_("grupo"),
                              on_delete=models.PROTECT, related_name="+")
    valor = models.DecimalField(_("valor"), max_digits=12, decimal_places=2)

    class Meta(ModeloDaEmpresa.Meta):
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0),
                                   name="fila_item_vendido_valor_positivo"),
        ]


class Pausa(ModeloDaEmpresa):
    pessoa = _pessoa(_("pessoa"))
    filial = _loja()
    presenca = models.ForeignKey(Presenca, verbose_name=_("presença"),
                                 on_delete=models.PROTECT, related_name="+")
    tipo = models.ForeignKey(TipoDePausa, verbose_name=_("tipo"),
                             on_delete=models.PROTECT, related_name="+")
    inicio = models.DateTimeField(_("início"))
    fim = models.DateTimeField(_("fim"), null=True, blank=True)

    class Meta(ModeloDaEmpresa.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa"], condition=Q(fim__isnull=True),
                name="fila_uma_pausa_aberta_por_pessoa"),
        ]
