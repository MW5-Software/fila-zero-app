"""As caixas de permissão da tela de Cargos.

Moravam na tela de Perfis, que saiu em 14/09/2026 junto com o model; ficaram
num arquivo próprio para a tela de Cargos não carregar a montagem das caixas
junto com a listagem.

**O que se oferece é o que está ligado nesta instalação** — `modulos_ligados()`,
não `declarados()`: oferecer o que o cliente não comprou é confuso, e o módulo
desligado nem aparece no menu dele.
"""

from __future__ import annotations

from nucleo.components import Box, Checkbox, FormGrid, SectionLabel
from plataforma.catalogo import modulos_ligados

from .permissoes import rotulo_de

__all__ = ["grupos_de_checkboxes", "permissoes_oferecidas"]


def permissoes_oferecidas(
    sem_modulos: "frozenset[str]" = frozenset(),
) -> "list[tuple[str, str, str, str]]":
    """`(codename, rótulo_da_permissão, chave_do_módulo, rótulo_do_módulo)` de
    toda permissão oferecida.

    `sem_modulos` tira módulos inteiros da oferta. É por onde a tela de Cargos
    recusa as permissões que permitiriam a alguém promover a si mesmo — ver
    `contas/views_cargos.py`.

    Módulo só da MW5 (`so_mw5`) nunca é oferecido: a permissão dele não existe
    como linha no banco (`contas.permissoes.materializar` pula), e uma caixa
    para ela prometeria uma concessão que não acontece.

    O coringa `<chave>_*` entra sempre, mesmo sem estar em
    `ModuloSpec.permissoes`: é ele que `materializar` cria à parte, e a forma
    canônica de conceder o módulo inteiro.
    """
    oferecidas = []
    for modulo in modulos_ligados():
        if modulo.so_mw5 or modulo.chave in sem_modulos:
            continue
        for permissao in modulo.permissoes:
            _resto, _resto, acao = permissao.partition(".")
            if not acao:
                continue
            codename = f"{modulo.chave}_{acao}"
            oferecidas.append((
                codename, rotulo_de(modulo.rotulo, acao),
                modulo.chave, modulo.rotulo,
            ))
        oferecidas.append((
            f"{modulo.chave}_*", rotulo_de(modulo.rotulo, "*"),
            modulo.chave, modulo.rotulo,
        ))
    return oferecidas


def grupos_de_checkboxes(
    marcadas: "frozenset[str]", oferecidas: "list[tuple[str, str, str, str]]",
) -> "list[Box]":
    """Um grupo por módulo — o rótulo do módulo como título da seção, e
    dentro, uma caixa por permissão, já marcada se `marcadas` a contém.

    Recebe `oferecidas` pronta (e não chama `permissoes_oferecidas()` de novo):
    esta função roda uma vez por modal desenhado, e recalcular bateria em
    `modulos_ligados()` (uma consulta ao banco) uma vez por modal à toa. Quem
    desenha a página inteira calcula uma vez só e repassa para todos.
    """
    por_modulo: "dict[str, list[Checkbox]]" = {}
    rotulo_do_modulo: "dict[str, str]" = {}
    for codename, rotulo, chave, rotulo_modulo in oferecidas:
        por_modulo.setdefault(chave, [])
        rotulo_do_modulo[chave] = rotulo_modulo
        por_modulo[chave].append(Checkbox(
            name="permissoes", value=codename, label=rotulo,
            checked=codename in marcadas,
        ))

    return [
        Box(body=[SectionLabel(label=rotulo_do_modulo[chave]),
                  FormGrid(children=caixas)])
        for chave, caixas in por_modulo.items()
    ]
