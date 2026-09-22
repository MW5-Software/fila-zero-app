"""O fluxo da fila de cada empresa: ler, gravar e a caixa da tela de Empresas.

O model é `fila.models.FluxoDaEmpresa`. Este módulo é a porta dele, para
ninguém consultar a tabela direto e esquecer que "sem linha" é o padrão.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import FluxoDaEmpresa, FluxoDaFila

__all__ = ["CAMPO", "FluxoDaFila", "caixa", "definir_fluxo", "fluxo_de",
           "gravar_do_post"]

#: O nome do campo no formulário da empresa. É o mesmo de quando o fluxo era
#: coluna da empresa, para o POST de uma tela aberta antes da mudança continuar
#: valendo.
CAMPO = "fluxo_da_fila"


def fluxo_de(empresa) -> str:
    """O fluxo da empresa; sem linha, o padrão (`VOLTA`)."""
    if empresa is None or empresa.pk is None:
        return FluxoDaFila.VOLTA
    return (FluxoDaEmpresa.irrestritos.filter(empresa_id=empresa.pk)
            .values_list("fluxo", flat=True).first() or FluxoDaFila.VOLTA)


def definir_fluxo(empresa, fluxo: str) -> None:
    """Grava o fluxo da empresa. Valor fora das opções é recusado pelo
    `full_clean` do model (`ValidationError`), e não normalizado aqui: a
    tela mostra a frase, e a regra fica num lugar só."""
    with transaction.atomic():
        linha = (FluxoDaEmpresa.irrestritos.select_for_update()
                 .filter(empresa_id=empresa.pk).first()
                 or FluxoDaEmpresa(empresa=empresa))
        linha.fluxo = fluxo
        # Sem a conta: quem a preenche é o `save()` de `ModeloDaEmpresa`, a
        # partir da empresa, e ela ainda está vazia numa linha nova.
        linha.full_clean(exclude=["conta"])
        linha.save()


def caixa(empresa):
    """A caixa "Fila da vez" do formulário da empresa (`empresa` é `None` ao
    criar)."""
    from nucleo.components import Box, FormGrid, Option, SectionLabel, Select

    return Box(body=[
        SectionLabel(label=_("Fila da vez")),
        FormGrid(children=[Select(
            name=CAMPO, label=_("Depois de lançar o atendimento"),
            span=12, value=fluxo_de(empresa),
            options=[Option(v, r) for v, r in FluxoDaFila.choices],
            help=_("Vale para todas as lojas desta empresa."))]),
    ])


def gravar_do_post(request, empresa) -> None:
    """Grava o que veio no POST do formulário da empresa.

    **Campo ausente não mexe** (a mesma regra das metas): um POST sem o fluxo
    — de uma tela que não o desenha, ou de um cliente antigo — deixa o valor
    gravado onde está. Valor inválido levanta `ValidationError`, e a tela de
    Empresas desfaz o formulário inteiro e mostra a frase.
    """
    if CAMPO not in request.POST:
        return
    try:
        definir_fluxo(empresa, request.POST[CAMPO].strip())
    except ValidationError as recusa:
        raise ValidationError({CAMPO: [_("Escolha um fluxo da fila válido.")]}) from recusa
