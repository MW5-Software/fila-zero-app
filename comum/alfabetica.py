"""Ordem alfabética de verdade, a de dicionário.

**Por que a coluna carrega a colação, e não cada consulta** (16/09/2026). O
Postgres destas instalações é `postgres:16-alpine`, e no Alpine a colação
`en_US.utf8` do banco ordena BYTE a BYTE: "Abacaxi | Zinco | bomba | Ágil |
água". Maiúscula antes de minúscula e acento no fim — o cliente viu os
cadastros "fora de ordem alfabética" e tinha razão. A ICU (`und-x-icu`) vem
compilada no próprio Postgres e ordena como se lê: "Abacaxi | Ágil | água |
bomba | Zinco".

Presa na COLUNA (`db_collation`), todo `ORDER BY nome` sai certo sozinho: a
ordenação padrão do model, o clique no cabeçalho da tabela
(`comum.listagem`), a API, as caixas de escolha e a vitrine. Um `Collate()`
em cada consulta seria uma coisa a mais para lembrar em cada tela nova, e
quem esquecesse não veria defeito nenhum até cadastrar "Água".

`und-x-icu` é DETERMINÍSTICA: "a" e "A" continuam diferentes para `=`,
`UNIQUE` e `LIKE`, só a ordem muda. Uma colação não determinística
(insensível a caixa) quebraria `icontains`, que o filtro das tabelas usa.
"""

from __future__ import annotations

import unicodedata

__all__ = ["DE_DICIONARIO", "chave"]

#: O nome da colação ICU "raiz", que existe em todo Postgres compilado com
#: ICU (o padrão desde o 16, e o das imagens oficiais).
DE_DICIONARIO = "und-x-icu"


def chave(texto: str) -> tuple[str, str]:
    """A mesma ordem de dicionário, para lista ordenada em PYTHON.

    Existe porque há ordenação feita em memória, sobre o `prefetch` (a ficha
    técnica do produto, na tela e na vitrine), e o `sorted` do Python compara
    ponto de código — o mesmo defeito do banco: "Água" depois de "Zinco".
    Sem acento e sem caixa primeiro; o texto cru desempata, para "a" e "A"
    não trocarem de lugar a cada chamada.
    """
    sem_acento = "".join(
        letra for letra in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(letra))
    return sem_acento.casefold(), texto
