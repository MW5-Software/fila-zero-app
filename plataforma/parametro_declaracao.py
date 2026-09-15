"""O que um parâmetro diz sobre si.

Mesma filosofia do catálogo de módulos (`plataforma/declaracao.py`), e pelo
mesmo motivo — R47 (`docs/superpowers/decisoes-2026-08-20-fatia-fina.md`):
um parâmetro **declara** o que é; ele não grava linha nenhuma. O código diz
que o parâmetro existe, qual o tipo e qual o padrão; o banco só entra na
hora em que uma instalação de fato muda o valor (ver
`plataforma.parametro_catalogo`, que faz esse cruzamento).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["ParametroSpec", "TIPOS", "declarados", "registrar"]

#: Os três tipos que a tela sabe desenhar — nada além disso, de propósito:
#: R47 escolheu parâmetro (nível 2 é caro demais para hoje), e um quarto tipo
#: (uma lista de opções, uma cor) é exatamente o próximo degrau que a decisão
#: disse para não subir sem um segundo cliente pedindo.
TIPOS = ("texto", "numero", "sim_nao")

#: O tipo Python que `padrao` precisa ter para cada `tipo` declarado — o
#: mesmo tipo que `plataforma.parametro_catalogo.converter` devolve depois
#: de ler o banco. Checado em `__post_init__`: um padrão do tipo errado só
#: apareceria na tela, ou pior, na leitura de `valor_de`, e o autor do
#: parâmetro fica sabendo na hora, não em produção.
_TIPO_PYTHON: dict[str, type] = {"texto": str, "numero": int, "sim_nao": bool}


@dataclass(frozen=True)
class ParametroSpec:
    """A apresentação de um parâmetro, em português claro.

    "Eu sou o Itens por página. Meu tipo é número. Meu padrão é 25. Eu moro
    no grupo Listagens. Só a MW5 pode me mudar."
    """

    chave: str
    rotulo: str
    tipo: str
    padrao: Any
    grupo: str = "Geral"
    ajuda: str = ""
    #: Técnico é da MW5; regra de negócio é do admin do cliente (ver o
    #: docstring de `plataforma.views_parametros`, que é quem lê este campo
    #: para decidir o que cada pessoa vê e pode gravar).
    so_mw5: bool = False

    def __post_init__(self) -> None:
        if not self.chave.strip():
            raise ValueError("parâmetro sem chave")
        if not self.rotulo.strip():
            raise ValueError(f"parâmetro {self.chave!r} sem rótulo")
        if self.tipo not in TIPOS:
            raise ValueError(
                f"parâmetro {self.chave!r} declarou tipo {self.tipo!r}; "
                f"use um de {TIPOS}"
            )
        esperado = _TIPO_PYTHON[self.tipo]
        # `bool` é subclasse de `int` em Python — sem excluir isso, um
        # parâmetro `numero` aceitaria `padrao=True` calado, e a tela leria
        # "1" onde devia ler o inteiro que o autor quis dizer.
        if not isinstance(self.padrao, esperado) or (
            esperado is int and isinstance(self.padrao, bool)
        ):
            raise ValueError(
                f"parâmetro {self.chave!r} é do tipo {self.tipo!r}, mas o "
                f"padrão {self.padrao!r} não é {esperado.__name__}"
            )


#: O que o código declarou. Preenchido quando cada módulo é registrado em
#: `ready()` — ver `plataforma/apps.py`.
_DECLARADOS: dict[str, ParametroSpec] = {}


def registrar(spec: ParametroSpec) -> None:
    """Põe um parâmetro no catálogo do código.

    Chave repetida quebra na subida, de propósito — mesmo motivo de
    `plataforma.declaracao.registrar`: duas declarações para a mesma chave
    dariam duas leituras possíveis do mesmo valor, e descobrir isso em
    produção é bem pior que na subida.
    """
    if spec.chave in _DECLARADOS:
        raise ValueError(f"o parâmetro {spec.chave!r} já foi declarado")
    _DECLARADOS[spec.chave] = spec


def declarados() -> tuple[ParametroSpec, ...]:
    """Todos os parâmetros que existem no código, em ordem de chave."""
    return tuple(_DECLARADOS[c] for c in sorted(_DECLARADOS))
