"""As unidades federativas pelo IBGE: sigla, código de 2 dígitos, nome.

O dado pequeno e estável do item 29. Os municípios NÃO estão aqui — ver o
docstring de `tests/test_uf.py` e o limite registrado abaixo deles.
"""

from __future__ import annotations

#: Sigla → (código IBGE,). O código de 2 dígitos é o que a nota fiscal e
#: os arquivos oficiais usam; a numeração segue a ordem alfabética das UFs,
#: com os saltos oficiais (…17 → 21…) que o IBGE reservou e nunca distribuiu.
CODIGO_IBGE: dict[str, int] = {
    "RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17,
    "MA": 21, "PI": 22, "CE": 23, "RN": 24, "PB": 25, "PE": 26, "AL": 27,
    "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41,
    "SC": 42, "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53,
}

#: Sigla → nome por extenso, para dropdown e relatório.
NOME: dict[str, str] = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima",
    "PA": "Pará", "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão",
    "PI": "Piauí", "CE": "Ceará", "RN": "Rio Grande do Norte",
    "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas", "SE": "Sergipe",
    "BA": "Bahia", "MG": "Minas Gerais", "ES": "Espírito Santo",
    "RJ": "Rio de Janeiro", "SP": "São Paulo", "PR": "Paraná",
    "SC": "Santa Catarina", "RS": "Rio Grande do Sul",
    "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "GO": "Goiás",
    "DF": "Distrito Federal",
}

__all__ = ["CODIGO_IBGE", "NOME", "erro_de_uf", "ufs_ordenadas"]


def erro_de_uf(valor: str) -> "str | None":
    """A frase da recusa, ou `None`. Aceita minúsculas — normalizar é com
    quem grava (o model faz). Vazio é livre: campo opcional."""
    sigla = (valor or "").strip().upper()
    if not sigla:
        return None
    if len(sigla) != 2 or sigla not in CODIGO_IBGE:
        return (
            f"“{valor}” não é uma UF — use a sigla do estado "
            f"(AC, AL, AP, AM, BA, CE, DF, ES, GO, MA, MT, MS, MG, PA, PB, "
            f"PR, PE, PI, RJ, RN, RS, RO, RR, SC, SP, SE, TO)."
        )
    return None


def ufs_ordenadas() -> "list[tuple[str, str]]":
    """Os pares `(sigla, nome)` por ordem alfabética do NOME — a ordem de
    quem escolhe, e não a numeração oficial."""
    return sorted(((sigla, nome) for sigla, nome in NOME.items()),
                  key=lambda par: par[1])
