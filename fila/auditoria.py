"""As ações da fila na trilha de auditoria.

Moravam na classe `ACOES` da base (`comum/auditoria.py`) até 21/09/2026, e era
isso que impedia a KRONOS base de voltar limpa para o Fila Zero: toda cópia
dela trazia a fila junto, ou apagava o que a fila usa. Agora a fila declara as
dela no `ready()` do app (`comum.auditoria.declarar_acoes`), e a base não sabe
que elas existem. O VALOR gravado no banco é o mesmo de antes: as linhas que
já estão na trilha continuam sendo lidas.
"""

from __future__ import annotations

__all__ = ["ACOES_DA_FILA", "ROTULOS_DA_FILA"]


class ACOES_DA_FILA:
    """As ações da fila, no mesmo formato de `comum.auditoria.ACOES`."""

    # As correções da fila do Fila Zero (`fila/correcoes.py`). As ações do
    # próprio vendedor NÃO entram: já são o histórico da fila, e uma linha de
    # trilha por clique afogaria o que a auditoria existe para mostrar.
    FILA_PESSOA_TIRADA = "fila_pessoa_tirada"
    FILA_ATENDIMENTO_FECHADO = "fila_atendimento_fechado"
    FILA_PAUSA_ENCERRADA = "fila_pausa_encerrada"
    FILA_LANCAMENTO_CORRIGIDO = "fila_lancamento_corrigido"
    FILA_POSICAO_MOVIDA = "fila_posicao_movida"
    FILA_PAUSA_INICIADA = "fila_pausa_iniciada"
    FILA_POSTO_NA_FILA = "fila_posto_na_fila"
    # Os três cadastros da fila; o alvo leva o nome do cadastro na frente
    # ("Grupo de item: Sofás"), porque os três dividem as mesmas três ações.
    FILA_CADASTRO_CRIADO = "fila_cadastro_criado"
    FILA_CADASTRO_EDITADO = "fila_cadastro_editado"
    FILA_CADASTRO_REMOVIDO = "fila_cadastro_removido"
    # As metas da fila (entrega 3); o alvo diz a loja, de quem e o mês, e o
    # detalhe, o valor novo e o de antes.
    FILA_META_DEFINIDA = "fila_meta_definida"
    FILA_META_REMOVIDA = "fila_meta_removida"


ROTULOS_DA_FILA = {
    ACOES_DA_FILA.FILA_PESSOA_TIRADA: "Pessoa tirada da loja",
    ACOES_DA_FILA.FILA_ATENDIMENTO_FECHADO: "Atendimento fechado pelo gerente",
    ACOES_DA_FILA.FILA_PAUSA_ENCERRADA: "Pausa encerrada pelo gerente",
    ACOES_DA_FILA.FILA_LANCAMENTO_CORRIGIDO: "Lançamento corrigido",
    ACOES_DA_FILA.FILA_POSICAO_MOVIDA: "Posição na fila mudada pelo gerente",
    ACOES_DA_FILA.FILA_PAUSA_INICIADA: "Pausa iniciada pelo gerente",
    ACOES_DA_FILA.FILA_POSTO_NA_FILA: "Posto na fila pelo gerente",
    ACOES_DA_FILA.FILA_CADASTRO_CRIADO: "Cadastro da fila criado",
    ACOES_DA_FILA.FILA_CADASTRO_EDITADO: "Cadastro da fila editado",
    ACOES_DA_FILA.FILA_CADASTRO_REMOVIDO: "Cadastro da fila removido",
    ACOES_DA_FILA.FILA_META_DEFINIDA: "Meta de venda definida",
    ACOES_DA_FILA.FILA_META_REMOVIDA: "Meta de venda removida",
}
