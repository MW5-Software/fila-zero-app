"""O cruzamento entre o que o código declara e o que o banco valeu, para
parâmetros — o par de `plataforma/catalogo.py`, para módulos.

A regra central é a mesma, e mora só aqui pelo mesmo motivo que ela mora só
em `catalogo.modulos_ligados()`: se cada tela reimplementasse "linha no
banco vence, senão o padrão do código", duas telas divergiriam no primeiro
ajuste feito de um lado só.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .parametro_declaracao import ParametroSpec, declarados

__all__ = [
    "ParametroEfetivo", "converter", "definir", "normalizar",
    "parametros_efetivos", "restaurar", "valor_de",
]


@dataclass(frozen=True)
class ParametroEfetivo:
    """Um parâmetro como ele vale **nesta instalação** — já com o valor
    resolvido (banco se houver linha, padrão do código senão) e a marca de
    qual dos dois foi usado, para a tela poder dizer "isto está no padrão"
    ou "isto foi mudado aqui" sem reconsultar o banco."""

    chave: str
    rotulo: str
    tipo: str
    grupo: str
    ajuda: str
    so_mw5: bool
    padrao: Any
    valor: Any
    no_padrao: bool


def _por_chave(chave: str) -> ParametroSpec:
    especificado = {spec.chave: spec for spec in declarados()}.get(chave)
    if especificado is None:
        raise ValueError(f"parâmetro {chave!r} não foi declarado no código")
    return especificado


def converter(tipo: str, bruto: str) -> Any:
    """`bruto` (sempre texto, o que `Parametro.valor` guarda) já no tipo que
    o parâmetro declarou. Único lugar que sabe ler o banco — mesma razão do
    docstring de `valor_de`, abaixo."""
    if tipo == "numero":
        return int(bruto)
    if tipo == "sim_nao":
        return bruto == "1"
    return bruto


def normalizar(tipo: str, bruto) -> "tuple[str | None, str | None]":
    """`bruto`, o que a tela recebeu do POST, validado e já no formato de
    texto que `Parametro.valor` grava — ou `None` com a frase do erro.

    Separado de `definir` (abaixo) de propósito: a tela precisa validar
    ANTES de abrir a transação que grava e audita, do mesmo jeito que
    `plataforma.views_empresa._validar` roda fora do `atomic()` — gravar e
    só depois descobrir que o dado era inválido deixaria a auditoria falando
    de uma escrita que nunca deveria ter acontecido.
    """
    if tipo == "numero":
        try:
            return str(int(bruto)), None
        except (TypeError, ValueError):
            return None, "Informe um número inteiro."
    if tipo == "sim_nao":
        # Vem de um `Checkbox`: o navegador só manda o campo quando
        # marcado — desmarcado é a CHAVE ausente do POST, não um valor
        # vazio. `bruto` chega `None` nesse caso, e `None` é falso.
        return ("1" if bruto else "0"), None
    return bruto, None


def valor_de(chave: str) -> Any:
    """O valor de `chave` **nesta instalação**, já convertido para o tipo
    que o código declarou — nunca uma string crua que cada chamador
    converteria à própria maneira (é assim que duas telas acabam
    discordando se `"0"` quer dizer falso).

    Ausência de linha em `Parametro` é o padrão declarado, e não um erro:
    é o que faz um padrão novo, numa versão nova do código, alcançar toda
    instalação que nunca mexeu nesta chave — sem migração de dado nenhuma.
    """
    spec = _por_chave(chave)
    linha = _Parametro().objects.filter(chave=chave).first()
    if linha is None:
        return spec.padrao
    return converter(spec.tipo, linha.valor)


def parametros_efetivos() -> "tuple[ParametroEfetivo, ...]":
    """Todo parâmetro declarado, na ordem de `declarados()`, com o valor
    desta instalação já resolvido.

    Uma linha em `Parametro` cuja chave não corresponde a nenhum
    `ParametroSpec` declarado é ignorada — nem aparece aqui, nem em
    `valor_de` — pelo mesmo motivo de `plataforma.catalogo.modulos_ligados`:
    um parâmetro removido do código deixa a linha para trás, e ela não pode
    voltar a valer só porque ninguém a apagou. Isso é automático aqui: o
    laço caminha `declarados()`, nunca as linhas do banco.
    """
    linhas = {linha.chave: linha for linha in _Parametro().objects.all()}

    saida = []
    for spec in declarados():
        linha = linhas.get(spec.chave)
        if linha is None:
            valor, no_padrao = spec.padrao, True
        else:
            valor, no_padrao = converter(spec.tipo, linha.valor), False
        saida.append(ParametroEfetivo(
            chave=spec.chave, rotulo=spec.rotulo, tipo=spec.tipo,
            grupo=spec.grupo, ajuda=spec.ajuda, so_mw5=spec.so_mw5,
            padrao=spec.padrao, valor=valor, no_padrao=no_padrao,
        ))
    return tuple(saida)


def definir(chave: str, valor_normalizado: str) -> None:
    """Grava `valor_normalizado` (já validado por `normalizar`, acima) para
    `chave`. Cria a linha se esta é a primeira vez que a instalação muda
    este parâmetro; atualiza se já existia."""
    _Parametro().objects.update_or_create(chave=chave, defaults={"valor": valor_normalizado})


def restaurar(chave: str) -> None:
    """Apaga a linha de `chave` — e não grava o padrão nela.

    A diferença importa: apagar faz esta instalação voltar a ler o padrão
    do CÓDIGO a cada chamada de `valor_de`, então um padrão que mude numa
    versão futura alcança esta instalação de novo. Gravar o padrão de hoje
    congelaria o valor de hoje para sempre, e pareceria "restaurado" sem
    nunca mais acompanhar o código.
    """
    _Parametro().objects.filter(chave=chave).delete()


def _Parametro():
    from .models import Parametro

    return Parametro
