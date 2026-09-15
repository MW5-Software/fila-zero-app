"""A política de moeda e número do Brasil, num lugar só.

Ver o docstring de `tests/test_formatos.py` para as três decisões: pt-BR
na saída, meio-ponto para cima, Decimal sempre.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

__all__ = ["arredondado", "moeda", "numero"]

_RUIDO = re.compile(r"[^\d.,-]")

#: A pontuação pt-BR fixa: ponto no milhar, vírgula no decimal. Montada à
#: mão (e não por locale) porque o `locale` do PROCESSO é o do servidor —
#: e a matriz roda em imagem slim cujo glibc não traz pt_BR instalado;
#: formatar por locale aqui era formato certo na minha máquina, errado no
#: container. A regra da moeda brasileira não varia com a máquina.
_MILHAR = "."
_DECIMAL = ","


def _decimal(valor) -> "Decimal | None":
    """O valor como `Decimal`, sem ruído binário de float; vazio é vazio."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, float):
        valor = repr(valor)
    limpo = _RUIDO.sub("", str(valor)).replace(",", ".").strip()
    if not limpo or limpo == "-":
        return None
    return Decimal(limpo)


def arredondado(valor, casas: int = 2) -> "Decimal | None":
    """Meio-ponto para CIMA (`ROUND_HALF_UP`) — o arredondamento do balcão."""
    quantidade = _decimal(valor)
    if quantidade is None:
        return None
    return quantidade.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)


def _em_grupos(inteira: str) -> str:
    """`1234567` → `1.234.567`, sem locale do processo."""
    partes = []
    while len(inteira) > 3:
        partes.insert(0, inteira[-3:])
        inteira = inteira[:-3]
    partes.insert(0, inteira)
    return _MILHAR.join(partes)


def numero(valor, casas: int = 2) -> str:
    """`1234.56` → `"1.234,56"` — a pontuação do Brasil, sem cifrão."""
    quantidade = arredondado(valor, casas)
    if quantidade is None:
        return ""
    negativo = quantidade < 0
    texto = f"{abs(quantidade):.{casas}f}"
    inteira, _, fracionaria = texto.partition(".")
    formatado = _em_grupos(inteira) + (_DECIMAL + fracionaria if fracionaria else "")
    return f"-{formatado}" if negativo else formatado


def moeda(valor, casas: int = 2) -> str:
    """`R$ 1.234,56`. Vazio entra, vazio sai — nunca um zero inventado."""
    formatado = numero(valor, casas)
    return f"R$ {formatado}" if formatado else ""
