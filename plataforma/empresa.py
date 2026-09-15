"""O módulo que semeava a empresa e a filial desta instalação — hoje vazio.

Ele existia pelo mesmo motivo do usuário da MW5 (`contas/mw5.py`): enquanto a instalação era de UM
cliente e a empresa era dado dela, sem uma linha de `Empresa` e de `Filial` a
instalação nova subia sem o que o cabeçalho mostra e sem filial para alguém
escolher.

**Com uma conta, uma empresa, isso virou o contrário.** Ver o comentário
abaixo e `tests/test_instalacao_nasce_sem_empresa.py`.

O arquivo fica em vez de ser apagado porque o comentário é o que impede a
semeadura de voltar — e um arquivo que some leva o motivo junto.
"""

from __future__ import annotations

__all__: list[str] = []


# As duas funções que moravam aqui — `garantir_empresa` e `garantir_matriz` —
# foram apagadas em 09/09/2026, e não só deixaram de ser chamadas.
#
# Elas criavam, em todo `migrate`, uma empresa e a filial "Matriz" dela. Com
# uma conta por empresa, o que isso produzia era uma empresa SEM DONO: ninguém
# a abre, ela fica na lista da MW5 sem nada explicando o que falta nela, e é o
# estado cujo caminho de criação foi fechado quando "Nova empresa" saiu da tela
# de Empresas.
#
# Deixá-las aqui sem chamador seria um gatilho carregado: a próxima pessoa que
# precisar de uma empresa de partida acha `garantir_empresa`, chama, e o
# defeito volta sem discussão. Ver
# `tests/test_instalacao_nasce_sem_empresa.py`.
