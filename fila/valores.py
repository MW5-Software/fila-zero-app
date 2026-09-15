"""O valor que o vendedor digita no celular, lido como dinheiro.

O teclado decimal do celular brasileiro dá vírgula; o de computador, às vezes
ponto; e quem copia de um orçamento traz "R$ 1.500,50". As três formas
precisam dar o mesmo número, e o que não for número vira `None` (a ação
recusa com frase) em vez de uma exceção.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

__all__ = ["em_reais", "ler_valor"]

_NUMERO = re.compile(r"\d+(?:\.\d+)?")
#: Um ponto só, seguido de exatamente três dígitos: é milhar ("2.000"), e não
#: decimal. Ninguém digita preço com três casas; quem digita "2.000" quer dois
#: mil, e ler dois reais seria a venda sumindo do ranking sem erro nenhum.
_MILHAR = re.compile(r"\d{1,3}(?:\.\d{3})+")


def ler_valor(texto: str) -> "Decimal | None":
    limpo = (texto or "").replace("R$", "").replace(" ", "").strip()
    if not limpo:
        return None
    if "," in limpo:
        # Com vírgula, ela é a decimal e os pontos são de milhar.
        if limpo.count(",") > 1:
            return None
        limpo = limpo.replace(".", "").replace(",", ".")
    elif _MILHAR.fullmatch(limpo):
        limpo = limpo.replace(".", "")
    if not _NUMERO.fullmatch(limpo):
        return None
    try:
        return Decimal(limpo).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def em_reais(valor: Decimal) -> str:
    """`Decimal("1800.5")` -> `"R$ 1.800,50"`. Escrito à mão, e não pelo
    `locale` do sistema: o contêiner da VPS não tem `pt_BR` instalado, e a
    tela sairia "R$ 1,800.50" só em produção."""
    inteiro, _ponto, centavos = f"{valor:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"
