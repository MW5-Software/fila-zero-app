"""As metas de venda da fila (spec 2026-09-15-fila-metas, entrega 3).

O registro, as regras de `fila/metas.py` e as contas do acompanhamento. As
contas recebem o relógio (`agora`) para cada dia do mês ser provado, e não o
dia em que a suíte roda.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from tests.fila_cenario import nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db

SETEMBRO = date(2026, 9, 1)


def local(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def loja():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(empresa=empresa, matriz=matriz, titular=titular,
                           ana=pessoa_na_loja("ana", empresa, matriz),
                           bia=pessoa_na_loja("bia", empresa, matriz))


def meta(loja, valor="1000", pessoa=None, mes=SETEMBRO, filial=None):
    from fila.models import MetaDeVenda

    return MetaDeVenda.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, pessoa=pessoa,
        mes=mes, valor=Decimal(valor))


def _estoura(**kwargs):
    with pytest.raises(IntegrityError), transaction.atomic():
        meta(**kwargs)


# --- O registro --------------------------------------------------------------

def test_uma_meta_da_loja_por_mes(loja):
    meta(loja)
    _estoura(loja=loja, valor="2000")
    meta(loja, mes=date(2026, 10, 1))


def test_uma_meta_por_pessoa_loja_e_mes(loja):
    meta(loja, pessoa=loja.ana)
    _estoura(loja=loja, pessoa=loja.ana, valor="2000")
    # A da loja e a de outra pessoa no mesmo mês convivem.
    meta(loja)
    meta(loja, pessoa=loja.bia)


def test_a_mesma_pessoa_tem_meta_em_duas_lojas(loja):
    centro = nova_loja(loja.empresa, "Centro")
    meta(loja, pessoa=loja.ana)
    meta(loja, pessoa=loja.ana, filial=centro)


def test_mes_fora_do_dia_1_e_valor_zero_o_banco_recusa(loja):
    _estoura(loja=loja, mes=date(2026, 9, 15))
    _estoura(loja=loja, valor="0")
