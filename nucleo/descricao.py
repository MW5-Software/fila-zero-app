"""A descrição de um componente a construir: o nome e os argumentos.

Movido para cá de `mw5_generator.corpo`: é infraestrutura genérica de "uma
descrição, dois consumidores" — o mesmo desenho documentado em `corpo.py` —, e
não é mais exclusiva de lá. `nucleo.campos` também precisa dela: os campos
de um formulário têm a própria descrição por tipo, instanciada por
`montar_campos` para o `Resource` desenhar de verdade, e o bloco Formulário de
`corpo.py` embute exatamente essa mesma descrição (`chamadas_dos_campos`)
dentro da própria árvore que ele instancia e escreve. As duas pontas têm que
reconhecer o mesmo `Chamada` — se cada lado tivesse a sua classe, `_escrever`
e `instanciar` do outro lado não a reconheceriam (`isinstance` falharia) e o
bloco Formulário pararia de desenhar ou de gerar código sem nenhum erro
explícito.

Por isso mora em `nucleo`: é o pacote que os dois lados já podem importar
— `mw5_generator` depende de `nucleo`, nunca o contrário.

[`mw5_generator` é vocabulário da fonte: não existe no KRONOS.net, que não
gera projeto por cliente.]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Chamada", "Codigo", "escrever", "instanciar"]


@dataclass
class Codigo:
    """Um valor que não é literal — uma `lambda`, tipicamente.

    Carrega as duas formas juntas: o objeto que a prévia usa e o texto que o
    arquivo gerado recebe. Declaradas lado a lado de propósito, porque
    escrever uma sem a outra é exatamente como a prévia e a pasta divergem.
    """

    fonte: str
    valor: Any


@dataclass
class Chamada:
    """Um componente a construir: o nome e os argumentos, nomeados ou não."""

    nome: str
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)


def instanciar(valor):
    from nucleo import components

    if isinstance(valor, Codigo):
        return valor.valor
    if isinstance(valor, Chamada):
        classe = getattr(components, valor.nome)
        return classe(*[instanciar(a) for a in valor.args],
                      **{k: instanciar(v) for k, v in valor.kwargs.items()})
    if isinstance(valor, list):
        return [instanciar(v) for v in valor]
    return valor


def escrever(valor, recuo: int) -> str:
    """Um valor em literal Python, com recuo legível."""
    espaco = " " * recuo
    if isinstance(valor, Codigo):
        return valor.fonte
    if isinstance(valor, Chamada):
        if not valor.args and not valor.kwargs:
            return f"{valor.nome}()"
        partes = [escrever(a, recuo + 4) for a in valor.args]
        partes += [f"{k}={escrever(v, recuo + 4)}" for k, v in valor.kwargs.items()]
        junto = ", ".join(partes)
        # Uma linha quando cabe; quebrado quando não. É o que deixa o arquivo
        # gerado parecer escrito por gente.
        if len(junto) + len(valor.nome) + recuo < 76 and "\n" not in junto:
            return f"{valor.nome}({junto})"
        dentro = ",\n".join(" " * (recuo + 4) + p for p in partes)
        return f"{valor.nome}(\n{dentro},\n{espaco})"
    if isinstance(valor, list):
        if not valor:
            return "[]"
        itens = [escrever(v, recuo + 4) for v in valor]
        junto = ", ".join(itens)
        if len(junto) + recuo < 72 and "\n" not in junto:
            return f"[{junto}]"
        dentro = ",\n".join(" " * (recuo + 4) + i for i in itens)
        return f"[\n{dentro},\n{espaco}]"
    if isinstance(valor, str):
        return _string_literal(valor)
    return repr(valor)


#: Os atalhos de escape que `repr()` também usa, além de barra invertida e da
#: aspa que delimita a string. O resto do arquivo gerado é todo em aspas
#: duplas; um `kind='bar'` no meio seria o único literal do arquivo escrito
#: diferente do que o desenvolvedor teria digitado.
_ATALHOS_DE_ESCAPE = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _string_literal(valor: str) -> str:
    """Uma string em literal Python, sempre entre aspas duplas.

    Segue a mesma regra de escape que `repr()` usa para `str`, só que sem
    alternar o tipo de aspa: todo caractere não imprimível (`isprintable()`
    falso) — NUL, `\\x1b`, separadores exóticos de Unicode, o que for — vira
    `\\xNN`/`\\uNNNN`/`\\UNNNNNNNN`, do mesmo jeito que `repr()` faria. Sem
    isso, um caractere de controle num campo de texto livre do painel geraria
    um arquivo `.py` com um byte cru que o `compile()` recusa.
    """
    partes = []
    for c in valor:
        if c == "\\":
            partes.append("\\\\")
        elif c == '"':
            partes.append('\\"')
        elif c in _ATALHOS_DE_ESCAPE:
            partes.append(_ATALHOS_DE_ESCAPE[c])
        elif c.isprintable():
            partes.append(c)
        else:
            ponto = ord(c)
            if ponto < 0x100:
                partes.append(f"\\x{ponto:02x}")
            elif ponto < 0x10000:
                partes.append(f"\\u{ponto:04x}")
            else:
                partes.append(f"\\U{ponto:08x}")
    return '"' + "".join(partes) + '"'
