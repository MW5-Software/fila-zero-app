"""O cabeçalho desta casa: o do design system, mais o seletor de idioma.

**Por que existe um template nosso.** O `nucleo` é porte verbatim e não se
emenda (CLAUDE.md §2), e o `Header` de lá não tem lugar para um controle a
mais no canto direito — ele desenha sino, sair e avatar, e nada entre eles. O
próprio design system deixou a porta: `create_environment(*extra_loaders)`
põe os loaders do projeto ANTES do dele, "a saída de emergência para quando um
cliente precisa de uma variação que não vale a pena generalizar".

**O custo, dito por escrito**: `plataforma/templates/layout/header.html` é uma
CÓPIA do template de lá. Se o design system mudar o cabeçalho, a cópia não
muda junto — e a tela desta casa continua na versão velha, calada.
`tests/test_cabecalho_da_casa.py` existe para isso: ele compara os dois e fica
vermelho no dia em que o de lá andar, para alguém trazer a mudança à mão.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nucleo.layout import Header, LoginPage

__all__ = ["EntradaDaCasa", "HeaderDaCasa"]


@dataclass
class HeaderDaCasa(Header):
    """O `Header` com um campo a mais: o que desenhar antes do sino."""

    #: O seletor de idioma já montado. Vazio some — e some de verdade: uma
    #: instalação com um idioma só não ganha um botão que não faz nada.
    idioma: Any = ""


@dataclass
class EntradaDaCasa(LoginPage):
    """A `LoginPage` com um campo a mais: o seletor de idioma.

    Mesmo motivo do `HeaderDaCasa` — o componente do design system não tem
    lugar para um controle depois do formulário, e o `nucleo` não se emenda.
    A `LoginPage` expõe `fields`, mas ali é DENTRO do formulário de senha, que
    não é lugar de um link de idioma.
    """

    #: O controle já montado. Vazio some.
    idiomas: Any = ""
