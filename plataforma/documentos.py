"""A validação dos documentos brasileiros: CPF, CNPJ, IE e CEP.

A máscara (`nucleo.campos.MASCARAS`) ajuda quem digita; quem decide se o
documento vale é a leitura dos dígitos AQUI — e o que vai para o banco é
`documento_limpo`: um formato só, só dígitos (IE pode ser ISENTO), para
duas gravações do mesmo documento nunca divergirem por causa do traço.

O limite, nomeado de propósito: CPF e CNPJ têm dígito verificador
verificável de verdade. A Inscrição Estadual NÃO — cada UF tem os próprios
pesos, são vinte e sete regras que só prestam testadas contra dado oficial;
enquanto essa tabela não chegar, IE é validada na ESTRUTURA (só dígitos,
tamanho plausível, ou ISENTO), e o limite está escrito na frase da recusa.
CEP é estrutural também: existir ou não é consulta ao serviço dos Correios,
que é outra conversa.
"""

from __future__ import annotations

import re

__all__ = ["documento_limpo", "erro_de_cep", "erro_de_cnpj", "erro_de_cpf",
           "erro_de_ie"]

_SO_DIGITOS = re.compile(r"\D")

#: Tamanhos de IE que existem no Brasil, dos mais curtos aos mais longos —
#: estrutura, não regra de UF (ver o docstring do módulo).
_TAMANHOS_DE_IE = range(2, 15)


def _digitos(valor: str) -> str:
    return _SO_DIGITOS.sub("", valor or "")


def documento_limpo(tipo: str, valor: str) -> str:
    """O formato canônico de gravação. Máscara é visual; dado gravado tem
    UM formato."""
    if tipo == "ie":
        limpo = (valor or "").strip().upper()
        return "" if not limpo else limpo
    return _digitos(valor)


def _erro_pelo_verificador(digitos: str, pesos_primeiro: tuple[int, ...],
                           pesos_segundo: tuple[int, ...]) -> "str | None":
    """O motor comum dos dois verificadores: dois dígitos, cada um é o
    complemento do resto da soma ponderada (módulo 11)."""
    if len(digitos) != len(pesos_primeiro) + 2:
        return None  # tamanho errado: a mensagem específica vem de cima

    def _dv(corpo: str, pesos: tuple[int, ...]) -> int:
        resto = sum(int(d) * p for d, p in zip(corpo, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    corpo = digitos[:-2]
    if digitos[-2] != str(_dv(corpo, pesos_primeiro)):
        return None
    if digitos[-1] != str(_dv(digitos[:-1], pesos_segundo)):
        return None
    return None  # passou


def erro_de_cpf(valor: str) -> "str | None":
    """A frase da recusa, ou `None`. Recebe formatado ou não — quem decide
    é a leitura dos dígitos."""
    digitos = _digitos(valor)
    if len(digitos) != 11:
        return "O CPF precisa ter 11 dígitos."
    if digitos == digitos[0] * 11:
        return "Este CPF não é válido (sequência repetida)."
    # Pesos do CPF: 10..2 no primeiro dígito, 11..2 no segundo.
    p1 = tuple(range(10, 1, -1))
    p2 = tuple(range(11, 1, -1))
    def dv(corpo, pesos):
        resto = sum(int(d) * p for d, p in zip(corpo, pesos)) % 11
        return 0 if resto < 2 else 11 - resto
    if int(digitos[9]) != dv(digitos[:9], p1) or \
            int(digitos[10]) != dv(digitos[:10], p2):
        return "Este CPF não é válido (dígito verificador não confere)."
    return None


def erro_de_cnpj(valor: str) -> "str | None":
    digitos = _digitos(valor)
    if len(digitos) != 14:
        return "O CNPJ precisa ter 14 dígitos."
    if digitos == digitos[0] * 14:
        return "Este CNPJ não é válido (sequência repetida)."
    def dv(corpo, pesos):
        resto = sum(int(d) * p for d, p in zip(corpo, pesos)) % 11
        return 0 if resto < 2 else 11 - resto
    # Pesos do CNPJ: a rodilha 5..2 + 9..2, deslocada uma casa no segundo.
    p1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    p2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    if int(digitos[12]) != dv(digitos[:12], p1) or \
            int(digitos[13]) != dv(digitos[:13], p2):
        return "Este CNPJ não é válido (dígito verificador não confere)."
    return None


def erro_de_cep(valor: str) -> "str | None":
    digitos = _digitos(valor)
    if len(digitos) != 8:
        return "O CEP precisa ter 8 dígitos."
    return None


def erro_de_ie(valor: str) -> "str | None":
    """IE na estrutura — o limite das vinte e sete regras está no docstring
    do módulo e na própria frase, para ninguém confiar demais."""
    limpo = (valor or "").strip().upper()
    if not limpo:
        return None
    if limpo == "ISENTO" or limpo.rstrip(".") == "ISENTA":
        return None
    digitos = _digitos(limpo)
    if len(digitos) != len(limpo):
        return (
            "A Inscrição Estadual aceita só dígitos (ou ISENTO). "
            "A validação do dígito por estado ainda não existe aqui."
        )
    if len(digitos) not in _TAMANHOS_DE_IE:
        return "A Inscrição Estadual tem um tamanho impossível."
    return None
