"""O que veio no corpo da requisição, convertido — e por que converter não é
detalhe.

**O defeito, encontrado em 09/09/2026 escrevendo teste de recusa.** Treze
telas faziam `filter(pk=request.POST.get("alvo"))` com o id direto do
formulário. Com um id que não é número — o campo vazio de um `<select>` que
ninguém escolheu, um valor adulterado na mão — o Django não devolve lista
vazia: ele levanta `ValueError: Field 'id' expected a number but got ''`, e a
tela responde 500.

Isso é errado por dois motivos, e o segundo é o que importa:

1. O 500 apaga o trabalho da pessoa. O formulário do produto tem sessenta
   campos, e um `<select>` deixado em branco derrubava a página inteira em vez
   de dizer "escolha o produto".
2. **É a diferença entre recusa e erro.** A casa tem um vocabulário só para
   quem manda id que não alcança: a ação não acontece e a tela recarrega
   dizendo por quê — nunca uma exceção, que conta ao atacante que o caminho
   existe e ele só errou o formato.

`id_do_post` devolve `int` ou `None`, e `None` num `filter(pk=...)` vira `IS
NULL` — nenhuma linha, que é exatamente a resposta certa.
"""

from __future__ import annotations

__all__ = ["id_do_post"]


def id_do_post(request, campo: str) -> "int | None":
    """O id inteiro que veio em `campo`, ou `None` se não veio um número.

    Aceita negativo de propósito: `-1` não é id de nada nesta casa, e
    recusá-lo aqui pelo SINAL seria uma segunda regra escondida num
    conversor. Quem decide se o id alcança alguma coisa é a consulta, com o
    filtro de inquilino — não este `if`.
    """
    bruto = (request.POST.get(campo) or "").strip()
    digitos = bruto[1:] if bruto.startswith("-") else bruto
    # `isascii`, porque "²".isdigit() é verdade e int("²") estoura; e no
    # máximo 18 dígitos, porque um id maior que o bigint estoura a consulta no
    # Postgres. Os dois viravam 500 (revisão final do Fila Zero, 15/09/2026).
    if not (digitos.isascii() and digitos.isdigit() and len(digitos) <= 18):
        return None
    return int(bruto)
