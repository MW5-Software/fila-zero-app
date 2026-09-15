"""O período dos indicadores e a comparação com o anterior (spec, "A
comparação"). Sem banco: é aritmética de datas, e é onde um número sai
errado sem ninguém ver."""

from datetime import date, datetime

import pytest
from django.utils import timezone

from fila.periodo import periodo_anterior, periodo_do_pedido


def local(*args):
    return timezone.make_aware(datetime(*args))


AGORA = local(2026, 9, 15, 14, 30)


@pytest.mark.parametrize("chave, de, ate", [
    ("hoje", local(2026, 9, 15), local(2026, 9, 16)),
    ("ontem", local(2026, 9, 14), local(2026, 9, 15)),
    ("7dias", local(2026, 9, 9), local(2026, 9, 16)),
    ("mes", local(2026, 9, 1), local(2026, 9, 16)),
    ("mes_passado", local(2026, 8, 1), local(2026, 9, 1)),
])
def test_cada_atalho(chave, de, ate):
    p = periodo_do_pedido({"periodo": chave}, AGORA)
    assert (p.de, p.ate, p.chave) == (de, ate, chave)


def test_sem_nada_e_este_mes():
    assert periodo_do_pedido({}, AGORA).chave == "mes"


def test_intervalo_livre_inclui_o_ultimo_dia():
    p = periodo_do_pedido({"de": "2026-09-01", "ate": "2026-09-10"}, AGORA)
    assert (p.de, p.ate, p.chave) == (local(2026, 9, 1), local(2026, 9, 11),
                                      "intervalo")
    assert p.rotulo == "01/09/2026 a 10/09/2026"


@pytest.mark.parametrize("de, ate", [
    ("2026-09-10", "2026-09-01"),        # invertido
    ("ontem", "2026-09-01"),             # não é data
    ("2024-01-01", "2026-09-01"),        # mais de 366 dias (P-4)
    ("2026-09-01", ""),                  # meio intervalo
])
def test_intervalo_ruim_cai_no_padrao(de, ate):
    assert periodo_do_pedido({"de": de, "ate": ate}, AGORA).chave == "mes"


def test_atalho_desconhecido_cai_no_padrao():
    assert periodo_do_pedido({"periodo": "sempre"}, AGORA).chave == "mes"


def test_hoje_em_andamento_compara_com_ontem_ate_a_mesma_hora():
    anterior = periodo_anterior(periodo_do_pedido({"periodo": "hoje"}, AGORA), AGORA)
    assert (anterior.de, anterior.ate) == (local(2026, 9, 14), local(2026, 9, 14, 14, 30))


def test_mes_em_andamento_compara_ate_o_mesmo_dia_e_hora():
    anterior = periodo_anterior(periodo_do_pedido({"periodo": "mes"}, AGORA), AGORA)
    assert (anterior.de, anterior.ate) == (local(2026, 8, 1), local(2026, 8, 15, 14, 30))


def test_mes_passado_mais_curto_compara_ate_o_ultimo_dia_dele():
    agora = local(2026, 10, 31, 10, 0)
    anterior = periodo_anterior(periodo_do_pedido({"periodo": "mes"}, agora), agora)
    assert (anterior.de, anterior.ate) == (local(2026, 9, 1), local(2026, 9, 30, 10, 0))


def test_periodo_fechado_compara_com_o_mesmo_tamanho_logo_antes():
    ontem = periodo_do_pedido({"periodo": "ontem"}, AGORA)
    assert (periodo_anterior(ontem, AGORA).de, periodo_anterior(ontem, AGORA).ate) == (
        local(2026, 9, 13), local(2026, 9, 14))
    passado = periodo_anterior(periodo_do_pedido({"periodo": "mes_passado"}, AGORA), AGORA)
    assert (passado.de, passado.ate) == (local(2026, 7, 1), local(2026, 8, 1))


def test_sete_dias_em_andamento():
    anterior = periodo_anterior(periodo_do_pedido({"periodo": "7dias"}, AGORA), AGORA)
    assert (anterior.de, anterior.ate) == (local(2026, 9, 2), local(2026, 9, 8, 14, 30))
