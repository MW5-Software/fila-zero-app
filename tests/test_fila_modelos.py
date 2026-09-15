"""As travas que são do banco, e não da tela.

"Um aberto por pessoa" escrito só na view deixa passar quem grava por fora —
um shell, uma migração, a próxima tela. A restrição parcial não deixa.
"""

from datetime import datetime, timezone as tz
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from tests.fila_cenario import cadastros, pessoa_na_loja, sylvia

AGORA = datetime(2026, 9, 15, 13, 0, tzinfo=tz.utc)

pytestmark = pytest.mark.django_db


def _presenca(empresa, filial, pessoa, saida=None):
    from fila.models import Presenca

    return Presenca.irrestritos.create(empresa=empresa, filial=filial,
                                       pessoa=pessoa, entrada=AGORA,
                                       saida=saida)


def test_duas_presencas_abertas_da_mesma_pessoa_o_banco_recusa():
    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    _presenca(empresa, matriz, ana, saida=AGORA)   # fechada não conta
    _presenca(empresa, matriz, ana)
    with pytest.raises(IntegrityError), transaction.atomic():
        _presenca(empresa, matriz, ana)


def test_dois_atendimentos_abertos_do_mesmo_vendedor_o_banco_recusa():
    from fila.models import Atendimento

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    presenca = _presenca(empresa, matriz, ana)
    Atendimento.irrestritos.create(empresa=empresa, filial=matriz,
                                   vendedor=ana, presenca=presenca,
                                   inicio=AGORA)
    with pytest.raises(IntegrityError), transaction.atomic():
        Atendimento.irrestritos.create(empresa=empresa, filial=matriz,
                                       vendedor=ana, presenca=presenca,
                                       inicio=AGORA)


def test_duas_pausas_abertas_da_mesma_pessoa_o_banco_recusa():
    from fila.models import Pausa

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    presenca = _presenca(empresa, matriz, ana)
    tipo = cadastros(empresa).tipo
    Pausa.irrestritos.create(empresa=empresa, filial=matriz, pessoa=ana,
                             presenca=presenca, tipo=tipo, inicio=AGORA)
    with pytest.raises(IntegrityError), transaction.atomic():
        Pausa.irrestritos.create(empresa=empresa, filial=matriz, pessoa=ana,
                                 presenca=presenca, tipo=tipo, inicio=AGORA)


def test_uma_pessoa_tem_um_lugar_na_fila_so():
    from fila.models import Estado, LugarNaFila

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    presenca = _presenca(empresa, matriz, ana)
    dados = dict(empresa=empresa, filial=matriz, pessoa=ana,
                 presenca=presenca, estado=Estado.NA_FILA,
                 na_fila_desde=AGORA, desde=AGORA)
    LugarNaFila.irrestritos.create(**dados)
    with pytest.raises(IntegrityError), transaction.atomic():
        LugarNaFila.irrestritos.create(**dados)


def test_nome_de_cadastro_e_unico_na_empresa_sem_diferenca_de_caixa():
    from fila.models import GrupoDeItem

    empresa, _, _ = sylvia()
    GrupoDeItem.irrestritos.create(empresa=empresa, nome="Sofás")
    with pytest.raises(IntegrityError), transaction.atomic():
        GrupoDeItem.irrestritos.create(empresa=empresa, nome="SOFÁS")


def test_valor_de_item_vendido_precisa_ser_positivo():
    from fila.models import Atendimento, ItemVendido

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    presenca = _presenca(empresa, matriz, ana)
    atendimento = Atendimento.irrestritos.create(
        empresa=empresa, filial=matriz, vendedor=ana, presenca=presenca,
        inicio=AGORA, fim=AGORA, resultado="vendeu", total=Decimal("0"))
    with pytest.raises(IntegrityError), transaction.atomic():
        ItemVendido.irrestritos.create(empresa=empresa,
                                       atendimento=atendimento,
                                       grupo=cadastros(empresa).grupo,
                                       valor=Decimal("0"))


def test_cadastro_usado_nao_se_apaga():
    from django.db.models import ProtectedError

    from fila.models import Pausa

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    tipo = cadastros(empresa).tipo
    Pausa.irrestritos.create(empresa=empresa, filial=matriz, pessoa=ana,
                             presenca=_presenca(empresa, matriz, ana),
                             tipo=tipo, inicio=AGORA)
    with pytest.raises(ProtectedError):
        tipo.delete()


def test_filial_com_historico_da_fila_nao_se_remove():
    """A base pergunta ao próprio Django se alguma tabela de negócio protege
    a filial (`plataforma/filiais.py`, `_protegida`). A fila tem de responder."""
    from plataforma.filiais import _protegida

    empresa, _, _ = sylvia()
    from tests.fila_cenario import nova_loja

    loja = nova_loja(empresa, "Centro")
    ana = pessoa_na_loja("ana", empresa, loja)
    _presenca(empresa, loja, ana)
    assert _protegida(loja)


def test_remover_usuario_com_historico_na_fila_responde_com_frase():
    from django.urls import reverse

    from contas.models import Usuario
    from tests.fila_cenario import logado

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    _presenca(empresa, matriz, ana, saida=AGORA)
    resposta = logado("sylvia").post(reverse("usuarios"), {
        "acao": "remover", "id": str(ana.pk)})
    assert resposta.status_code == 200
    assert "histórico" in resposta.content.decode()
    assert Usuario.objects.filter(pk=ana.pk).exists()
