"""Dois "Vou atender" ao mesmo tempo dão um atendimento e uma recusa, nunca
dois e nunca um erro 500.

Transacional de verdade, com duas threads, cada uma com a própria conexão:
dentro da transação única do `db` normal não há concorrência para provar.

A demora entre ler e gravar é FORÇADA (`_lugar_na_loja` espera depois de
ler). Sem ela as duas threads quase sempre se revezam por sorte, e o teste
passaria com o código sem trava — que é o teste sem dente que a casa não
aceita.
"""

import threading
import time

import pytest
from django.db import connection

from tests.fila_cenario import pessoa_na_loja, sylvia


@pytest.mark.django_db(transaction=True)
def test_dois_vou_atender_simultaneos_dao_um_atendimento_e_uma_recusa(monkeypatch):
    import fila.acoes as acoes
    from fila.models import Atendimento

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    acoes.bater_ponto(ana, matriz)

    ler_de_verdade = acoes._lugar_na_loja

    def ler_devagar(pessoa_id, filial):
        lugar = ler_de_verdade(pessoa_id, filial)
        time.sleep(0.3)
        return lugar

    monkeypatch.setattr(acoes, "_lugar_na_loja", ler_devagar)

    largada = threading.Barrier(2)
    resultados = []

    def tocar():
        try:
            largada.wait()
            acoes.vou_atender(ana, matriz)
            resultados.append("ok")
        except acoes.Recusa:
            resultados.append("recusa")
        except Exception as erro:  # o defeito que este teste existe para pegar
            resultados.append(f"erro: {type(erro).__name__}")
        finally:
            connection.close()

    threads = [threading.Thread(target=tocar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(resultados) == ["ok", "recusa"]
    assert Atendimento.irrestritos.count() == 1


@pytest.mark.django_db(transaction=True)
def test_dois_gerentes_movendo_ao_mesmo_tempo_nao_empatam_a_fila(monkeypatch):
    """Dois gerentes põem pessoas diferentes em 1º ao mesmo tempo.

    A posição não é um número guardado: é o instante de `na_fila_desde`, e
    quem entra em 1º grava um microssegundo antes do primeiro que LEU. Sem a
    trava, os dois leem a mesma fila, calculam o mesmo instante e as duas
    pessoas ficam empatadas — e aí quem está na frente passa a ser decidido
    pelo `pk`, e não pelo gerente que mandou por último. Com a trava, o
    segundo lê a fila já com a gravação do primeiro.
    """
    import fila.acoes as acoes
    from fila.correcoes import mover
    from fila.models import LugarNaFila

    empresa, matriz, _ = sylvia()
    gil = pessoa_na_loja("gil", empresa, matriz, cargo="gerente")
    sara = pessoa_na_loja("sara", empresa, None, cargo="supervisor")
    ana = pessoa_na_loja("ana", empresa, matriz)
    bia = pessoa_na_loja("bia", empresa, matriz)
    caio = pessoa_na_loja("caio", empresa, matriz)
    for pessoa in (ana, bia, caio):
        acoes.bater_ponto(pessoa, matriz)

    ler_de_verdade = acoes._lugar_na_loja

    def ler_devagar(pessoa_id, filial):
        lugar = ler_de_verdade(pessoa_id, filial)
        time.sleep(0.3)
        return lugar

    monkeypatch.setattr(acoes, "_lugar_na_loja", ler_devagar)
    largada = threading.Barrier(2)
    resultados = {}

    def rodar(nome, autor, alvo):
        try:
            largada.wait()
            mover(autor, matriz, alvo.pk, 1, observacao="chegou antes")
            resultados[nome] = "ok"
        except acoes.Recusa:
            resultados[nome] = "recusa"
        except Exception as erro:   # o defeito que este teste existe para pegar
            resultados[nome] = f"erro: {type(erro).__name__}"
        finally:
            connection.close()

    threads = [threading.Thread(target=rodar, args=("gil", gil, bia)),
               threading.Thread(target=rodar, args=("sara", sara, caio))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not any(v.startswith("erro") for v in resultados.values()), resultados
    instantes = list(LugarNaFila.irrestritos.filter(pessoa__in=[bia, caio])
                     .values_list("na_fila_desde", flat=True))
    assert len(set(instantes)) == 2, "as duas pessoas ficaram no mesmo instante"
    assert [l.pessoa_id for l in acoes.na_fila(matriz)][2] == ana.pk


@pytest.mark.django_db(transaction=True)
def test_mover_e_vou_atender_ao_mesmo_tempo_nao_quebram_a_fila(monkeypatch):
    """O gerente move a Bia para o 1º enquanto a Ana, que é a 1ª, toca "Vou
    atender". A trava serializa: ou a Ana atende e a Bia fica sozinha na
    fila, ou a Bia passa na frente e a Ana é recusada. Nunca um 500, nunca
    dois atendimentos, nunca a Bia fora da fila."""
    import fila.acoes as acoes
    from fila.correcoes import mover
    from fila.estado import na_fila
    from fila.models import Atendimento

    empresa, matriz, _ = sylvia()
    gil = pessoa_na_loja("gil", empresa, matriz, cargo="gerente")
    ana = pessoa_na_loja("ana", empresa, matriz)
    bia = pessoa_na_loja("bia", empresa, matriz)
    acoes.bater_ponto(ana, matriz)
    acoes.bater_ponto(bia, matriz)

    ler_de_verdade = acoes._lugar_na_loja

    def ler_devagar(pessoa_id, filial):
        lugar = ler_de_verdade(pessoa_id, filial)
        time.sleep(0.3)
        return lugar

    monkeypatch.setattr(acoes, "_lugar_na_loja", ler_devagar)
    largada = threading.Barrier(2)
    resultados = {}

    def rodar(nome, acao):
        try:
            largada.wait()
            acao()
            resultados[nome] = "ok"
        except acoes.Recusa:
            resultados[nome] = "recusa"
        except Exception as erro:   # o defeito que este teste existe para pegar
            resultados[nome] = f"erro: {type(erro).__name__}"
        finally:
            connection.close()

    threads = [
        threading.Thread(target=rodar,
                         args=("atender", lambda: acoes.vou_atender(ana, matriz))),
        threading.Thread(target=rodar,
                         args=("mover", lambda: mover(gil, matriz, bia.pk, 1,
                                                      observacao="chegou antes"))),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not any(v.startswith("erro") for v in resultados.values()), resultados
    assert Atendimento.irrestritos.count() <= 1
    assert bia.pk in [l.pessoa_id for l in na_fila(matriz)]
