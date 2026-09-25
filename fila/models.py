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
    "MetaDeVenda", "Midia", "MotivoDeNaoVenda", "Pausa", "Presenca", "Resultado",
    "TipoDePausa",
]


class Estado(models.TextChoices):
    NA_FILA = "na_fila", _("Na fila")
    ATENDENDO = "atendendo", _("Atendendo")
    EM_PAUSA = "em_pausa", _("Em pausa")
    #: Fora da fila por vontade da pessoa, com o ponto aberto: o fluxo em que
    #: quem lança o atendimento só volta à fila quando quiser (spec
    #: 2026-09-17-fluxo-da-fila-por-empresa). **Não é pausa**: não existe
    #: linha de `Pausa`, e o tempo aqui não entra em indicador de pausa
    #: nenhum.
    EM_ESPERA = "em_espera", _("Em espera")


class Resultado(models.TextChoices):
    VENDEU = "vendeu", _("Vendeu")
    NAO_VENDEU = "nao_vendeu", _("Não vendeu")


class FluxoDaFila(models.TextChoices):
    """O que acontece com o vendedor depois que o atendimento é lançado
    (spec 2026-09-17-fluxo-da-fila-por-empresa).

    Mora na EMPRESA, e não na loja: a rede trabalha do mesmo jeito nas lojas
    dela, e um campo por loja seria a mesma resposta repetida em cada uma, com
    a chance de duas divergirem por esquecimento.
    """

    VOLTA = "volta_para_a_fila", _("Volta para o fim da fila")
    ESPERA = "espera", _("Fica em espera e entra na fila quando quiser")


class FluxoDaEmpresa(ModeloDaEmpresa):
    """O fluxo da fila de UMA empresa — uma linha por empresa, e só quando ela
    muda do padrão.

    Era a coluna `plataforma.Empresa.fluxo_da_fila` até 21/09/2026: a base
    carregava um campo de um módulo de negócio, e o Fila Zero nunca mais
    recebia a base limpa. Aqui ele é da fila, e a base não sabe que existe
    (`fila/fluxo.py` lê e grava; a caixa da tela de Empresas é registrada pela
    fila em `plataforma.caixas_da_empresa`).

    **Sem linha é o padrão** (`VOLTA`, o fluxo da Sylvia): nenhuma empresa
    precisa de linha para funcionar como sempre funcionou.
    """

    fluxo = models.CharField(
        _("fluxo da fila"), max_length=20, choices=FluxoDaFila.choices,
        default=FluxoDaFila.VOLTA)

    class Meta(ModeloDaEmpresa.Meta):
        verbose_name = _("fluxo da fila da empresa")
        verbose_name_plural = _("fluxos da fila das empresas")
        constraints = [
            models.UniqueConstraint(fields=["empresa"],
                                    name="fila_um_fluxo_por_empresa"),
        ]


class TurnoDaLoja(ModeloDaEmpresa):
    """O turno de UMA loja: a hora em que ele termina.

    Na LOJA, e não na empresa (23/09/2026, decisão do cliente): a rede tem
    lojas que fecham em horas diferentes, e um horário por empresa obrigaria a
    última a esperar a primeira. **Sem linha não há turno** — e sem turno não
    há saída automática: nenhuma loja precisa de linha para funcionar como
    sempre funcionou (mesma forma de `FluxoDaEmpresa`).

    `fim` é a hora de FECHAR a loja. Quem ainda estiver dentro uma hora depois
    dela sai sozinho (`fila/turno.py`), menos quem está atendendo: fechar um
    atendimento aberto sozinho perderia a venda que o vendedor está lançando.
    """

    filial = models.OneToOneField(
        "plataforma.Filial", verbose_name=_("loja"),
        on_delete=models.CASCADE, related_name="turno",
        help_text=_("A loja deste turno."))
    fim = models.TimeField(_("fim do turno"))

    class Meta(ModeloDaEmpresa.Meta):
        verbose_name = _("turno da loja")
        verbose_name_plural = _("turnos das lojas")


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


class Midia(Cadastro):
    """Por qual canal o cliente chegou — Instagram, indicação, passando na
    porta (25/09/2026, pedido do cliente). Vale para a venda E para a não
    venda: a pergunta é "que canal traz cliente que compra", e ela precisa dos
    dois lados."""

    class Meta(Cadastro.Meta):
        verbose_name = _("mídia")
        verbose_name_plural = _("mídias")


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
            # **Uma presença aberta por pessoa, em toda a instalação.** Vale
            # entre lojas e, desde 17/09/2026, entre EMPRESAS da mesma conta:
            # a pessoa está numa loja de cada vez, e bater o ponto na loja de
            # outra empresa fecha a presença anterior (`acoes.bater_ponto`).
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
    #: Nula nos atendimentos de antes de 25/09/2026, e nos da empresa que não
    #: tem mídia ativa nenhuma: a regra de exigir mora em
    #: `fila.acoes._validar_midia`, e não no banco, por causa dos dois.
    midia = models.ForeignKey(Midia, verbose_name=_("mídia"),
                              on_delete=models.PROTECT, null=True,
                              blank=True, related_name="+")
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
                                name="fila_atendimento_do_dia"),
                   # Os indicadores (entrega 2) filtram por empresa, loja e
                   # período a cada tela aberta.
                   models.Index(fields=["empresa", "filial", "fim"],
                                name="fila_atendimento_periodo")]


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
        # O tempo em pausa dos indicadores (entrega 2) filtra por loja e
        # período.
        indexes = [models.Index(fields=["filial", "inicio"],
                                name="fila_pausa_periodo")]


class MetaDeVenda(ModeloDaEmpresa):
    """Quanto a loja, ou um vendedor naquela loja, deve vender no mês
    (spec 2026-09-15-fila-metas).

    **Uma tabela para as duas metas**: `pessoa` nula é a meta da loja. A regra,
    a tela e as consultas são as mesmas, e duas tabelas duplicariam cada uma.
    Chama-se `MetaDeVenda`, e não `Meta`, porque todo model já tem uma classe
    interna `Meta` (decisão P-1 do plano).
    """

    filial = _loja()
    pessoa = _pessoa(_("vendedor"), null=True, blank=True)
    mes = models.DateField(_("mês"))
    valor = models.DecimalField(_("valor"), max_digits=12, decimal_places=2)
    #: A versão da página da fila olha para cá: trocar uma meta por outra com
    #: a mesma soma não mudaria contagem nem total (decisão P-2 do plano).
    alterada_em = models.DateTimeField(_("alterada em"), auto_now=True)

    class Meta(ModeloDaEmpresa.Meta):
        verbose_name = _("meta de venda")
        verbose_name_plural = _("metas de venda")
        # No banco, e não só na tela: quem grava por fora (shell, migração, a
        # próxima tela) não cria a segunda meta do mês nem a meta do dia 15.
        constraints = [
            models.UniqueConstraint(
                fields=["filial", "mes"], condition=Q(pessoa__isnull=True),
                name="fila_uma_meta_da_loja_por_mes"),
            models.UniqueConstraint(
                fields=["filial", "pessoa", "mes"],
                condition=Q(pessoa__isnull=False),
                name="fila_uma_meta_por_pessoa_loja_e_mes"),
            models.CheckConstraint(condition=Q(mes__day=1),
                                   name="fila_meta_no_dia_1"),
            models.CheckConstraint(condition=Q(valor__gt=0),
                                   name="fila_meta_positiva"),
        ]


class AcaoDeCorrecao(models.TextChoices):
    MOVER = "mover", _("Mudou de posição")
    PAUSAR = "pausar", _("Pôs em pausa")
    TIRAR_PAUSA = "tirar_pausa", _("Tirou da pausa")
    FECHAR = "fechar", _("Fechou o atendimento")
    TIRAR = "tirar", _("Tirou da loja")
    EDITAR = "editar", _("Corrigiu o lançamento")
    POR_NA_FILA = "por_na_fila", _("Pôs na fila")


class CorrecaoNaFila(ModeloDaEmpresa):
    """Uma correção do gerente, com o motivo (spec 2026-09-17, C2).

    Tabela própria, e não só a auditoria: o histórico é lido por loja,
    vendedor e período, e a auditoria não tem essas colunas; filtrar por elas
    viraria busca em texto. A auditoria continua recebendo a mesma correção.
    """

    filial = _loja()
    pessoa = _pessoa(_("vendedor"))
    #: Quem corrigiu como a ação o recebe: em "ver como", a pessoa vista. Quem
    #: agiu de verdade está na auditoria, que anota a personificação.
    autor = _pessoa(_("quem corrigiu"))
    acao = models.CharField(_("ação"), max_length=12, choices=AcaoDeCorrecao.choices)
    observacao = models.CharField(_("motivo"), max_length=200)
    #: O que mudou, escrito pelo sistema ("de 5º para 1º", "Almoço").
    detalhe = models.CharField(_("detalhe"), max_length=300, blank=True)
    momento = models.DateTimeField(_("quando"))

    class Meta(ModeloDaEmpresa.Meta):
        verbose_name = _("correção na fila")
        verbose_name_plural = _("correções na fila")
        # A tela de histórico filtra por loja e período.
        indexes = [models.Index(fields=["filial", "momento"],
                                name="fila_correcao_periodo")]
