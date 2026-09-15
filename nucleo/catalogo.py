"""Onde um cadastro acha o outro.

Um `Resource` que aponta para outro precisa de duas coisas dele: a lista de
registros, para montar o `<select>`, e o rótulo de cada um. E o que apaga
precisa da pergunta inversa — quem aponta para mim?

**Por que um catálogo, e não um import.** Cada cadastro gerado é um módulo
próprio. Com importação direta, `pedidos.py` importaria `clientes.py`; dois
cadastros que se apontam dariam ciclo de import, e a ordem dos `import` no
`main.py` passaria a importar. Aqui o registro acontece quando o `Resource`
nasce, e a busca é **preguiçosa** — na hora de desenhar a tela, não na de
carregar o módulo.

A chave é a **rota** (`/clientes`), que é o que o `Resource` conhece de si
mesmo e o que o campo guarda em `Campo.alvo`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .resource import Resource

__all__ = ["apontam_para", "esquecer_tudo", "procurar", "registrar"]

#: Módulo-nível de propósito: é o único jeito de dois módulos que não se
#: importam se acharem. Reregistrar a mesma rota sobrescreve — é o que faz um
#: teste que monta o mesmo recurso duas vezes não acumular duplicata.
_POR_ROTA: "dict[str, Resource]" = {}


def registrar(recurso: "Resource") -> None:
    _POR_ROTA[recurso.rota] = recurso


def procurar(rota: str) -> "Resource | None":
    """O recurso daquela rota, ou `None`.

    `None`, e não erro: um cadastro pode ter sido removido do menu depois de
    outro passar a apontar para ele, e derrubar a tela de Pedidos porque
    alguém apagou Clientes é pior do que mostrar um campo que não dá para
    preencher. Quem chama decide o que fazer com a ausência.
    """
    return _POR_ROTA.get(rota)


def apontam_para(rota: str) -> "list[tuple[Resource, str]]":
    """Quem aponta para esta rota, e por qual coluna.

    A pergunta que o remover faz. Devolve pares `(recurso, coluna)` — a coluna
    porque é ela que a contagem precisa filtrar, e pedi-la de novo depois
    obrigaria a repetir a regra do `_id`.
    """
    achados = []
    for recurso in _POR_ROTA.values():
        for campo in recurso.campos:
            if campo.tipo == "relacao" and campo.alvo == rota:
                achados.append((recurso, campo.nome))
    return achados


def esquecer_tudo() -> None:
    """Só para teste. O catálogo é global, e um caso que registra três
    cadastros contaminaria o seguinte."""
    _POR_ROTA.clear()
