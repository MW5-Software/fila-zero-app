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
