"""A base não importa módulo de NEGÓCIO. Nunca.

A direção é `nucleo ← comum ← plataforma ← contas`, com os módulos de negócio
(`catalogo`, `orcamento`, `modulos/*`) por cima de todas. Está no `CLAUDE.md`
§2 desde sempre, e até 11/09/2026 nada a cobrava: era uma frase.

**O defeito que produziu esta varredura.** Quando a foto de produto saiu do
banco (10/09), a raiz da pasta de mídia nasceu em `catalogo/armazenamento.py`
— junto do código que grava foto, que parecia o lugar. E
`plataforma/management/commands/backupar.py` passou a importar de lá, para
empacotar a pasta junto do dump.

Ninguém viu, porque **camada invertida não dói enquanto existe um consumidor
só**. O `catalogo` está instalado aqui, o import resolve, a suíte fecha verde.
Ela só apareceu no dia seguinte, copiando esta base para um produto novo: o
`backupar` quebrou com `No module named 'catalogo'` — um produto irmão sem
catálogo não conseguia nem fazer backup.

É a classe de defeito mais cara que uma base compartilhada tem, porque o
preço não é pago por quem a introduz: é pago meses depois, por quem copia.

**O que esta varredura NÃO faz.** Ela não desenha o grafo inteiro de imports
nem cobra a ordem entre `comum` e `plataforma` — para isso serve a revisão. Ela
cobra a fronteira que já foi cruzada, que é a que volta a ser cruzada: base
importando negócio.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

#: As camadas da BASE, de dentro para fora. Nenhuma pode importar negócio.
BASE = ("nucleo", "comum", "plataforma", "contas")

#: Os módulos de NEGÓCIO deste produto. Um produto irmão sobre a mesma base
#: não levaria nenhum deles — é essa a definição, e é por isso que a base não
#: pode depender deles.
#:
#: `modulos` entra pelo pacote: `modulos.exemplo` e qualquer outro que nasça
#: ali são negócio por construção.
NEGOCIO = ("catalogo", "orcamento", "modulos")

#: Import de base para negócio que é permitido, e o motivo de cada um.
#: **Vazia de propósito.** Se um dia precisar de entrada, ela vem com o porquê
#: escrito ao lado — e a pergunta antes de escrever é sempre a mesma: o que
#: está sendo importado é mesmo de negócio, ou é da instalação e nasceu no
#: lugar errado? Na única vez que isso aconteceu, era a segunda.
PERDOADOS: dict[str, str] = {}


def _arquivos_da_base() -> "list[Path]":
    achados: list[Path] = []
    for camada in BASE:
        achados += [p for p in Path(camada).rglob("*.py")
                    if "__pycache__" not in p.parts]
    return sorted(achados)


def _modulos_importados(arquivo: Path) -> "set[str]":
    """O primeiro pedaço de cada import do arquivo — inclusive os TARDIOS.

    Import dentro de função conta igual: foi exatamente assim que o defeito
    entrou (`from catalogo.armazenamento import raiz` dentro de um método),
    e uma varredura que só olhasse o topo do arquivo teria passado batido.

    Relativo (`from . import x`) não conta: ele nunca sai da própria camada,
    que é justamente o que se quer.
    """
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom):
            if no.level:            # `from .` / `from ..` — dentro de casa
                continue
            if no.module:
                nomes.add(no.module.split(".")[0])
    return nomes


@pytest.mark.parametrize("arquivo", _arquivos_da_base(),
                         ids=lambda p: str(p))
def test_a_base_nao_importa_modulo_de_negocio(arquivo):
    achados = sorted(_modulos_importados(arquivo) & set(NEGOCIO))
    if str(arquivo) in PERDOADOS:
        return
    assert not achados, (
        f"{arquivo} é da BASE e importa {achados}, que é módulo de NEGÓCIO. "
        f"A direção é `nucleo ← comum ← plataforma ← contas`, com negócio por "
        f"cima de todas — um produto irmão sem esse módulo não conseguiria "
        f"nem subir. Se o que se importa é da INSTALAÇÃO e nasceu no lugar "
        f"errado, mova-o para a base (foi o caso de `plataforma/midia.py`). "
        f"Se for mesmo de negócio, inverta a dependência."
    )


def test_a_varredura_olha_para_algum_arquivo():
    """Uma lista vazia fica verde para sempre — o pior estado de uma trava.

    O número não é fixo (a base cresce); o que se cobra é que as quatro
    camadas existam e tenham código.
    """
    arquivos = _arquivos_da_base()
    assert len(arquivos) > 50, len(arquivos)
    camadas = {p.parts[0] for p in arquivos}
    assert camadas == set(BASE), camadas


def test_toda_excecao_tem_motivo_escrito():
    vazios = [k for k, v in PERDOADOS.items() if not str(v).strip()]
    assert not vazios, f"exceção sem motivo escrito: {vazios}"


def test_o_import_tardio_tambem_e_visto(tmp_path):
    """A prova de que ela não passa por olhar pouco.

    O defeito real era um `from catalogo.armazenamento import raiz` DENTRO de
    um método — uma varredura que lesse só o topo do arquivo o teria deixado
    passar, e é o formato mais comum aqui (import tardio é o jeito da casa de
    evitar ciclo de carga entre apps).
    """
    alvo = tmp_path / "fingindo.py"
    alvo.write_text(
        "def f():\n    from catalogo.armazenamento import raiz\n    return raiz\n",
        encoding="utf-8")

    assert "catalogo" in _modulos_importados(alvo)


def test_o_claude_md_continua_declarando_a_direcao():
    """A varredura cobra o que o `CLAUDE.md` §2 promete. Se a frase sair de
    lá, a regra vira folclore — e quem lê o documento não sabe mais por que a
    suíte reclama."""
    texto = Path("CLAUDE.md").read_text(encoding="utf-8")
    assert re.search(r"`nucleo`\s*←\s*`comum`\s*←\s*`plataforma`\s*←\s*`contas`",
                     texto)
