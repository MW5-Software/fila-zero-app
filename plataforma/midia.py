"""Onde a instalação guarda ARQUIVO — a raiz da mídia.

Isto é da INSTALAÇÃO, e não de um módulo de negócio. A pasta existe pela
mesma razão que o banco existe: é onde o que não é código fica. Qual módulo
põe coisa lá dentro é assunto dele.

**Por que este arquivo nasceu** (11/09/2026). A função morava em
`catalogo/armazenamento.py`, junto do código que grava foto de produto — e
`plataforma/management/commands/backupar.py` a importava de lá, para
empacotar a pasta junto do dump. Isso inverte as camadas
(`nucleo ← comum ← plataforma ← contas`, e módulo de negócio por cima de
todas): a base passou a depender de um módulo de negócio, e um produto irmão
que não tenha `catalogo` não consegue nem fazer backup.

Foi assim que o defeito apareceu: copiando esta base para um produto novo, o
`backupar` quebrou com `No module named 'catalogo'`. **A camada errada não dói
enquanto existe um consumidor só** — e é por isso que ela passa despercebida
justamente no produto onde nasceu.

No Portal de Vendas, `catalogo.armazenamento` continua sendo quem sabe gravar
FOTO DE PRODUTO. O que ele deixou de decidir é ONDE fica a pasta: isso é da
instalação, e todo módulo de negócio lê daqui.

`tests/test_camadas_nao_se_invertem.py` recusa a volta.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["VARIAVEL", "raiz"]

#: A variável que aponta a pasta numa instalação. Sem ela, `midia/` dentro do
#: projeto — que serve para desenvolvimento e é o que o compose monta como
#: volume.
VARIAVEL = "KRONOS_MIDIA"


def raiz() -> Path:
    """A pasta onde os arquivos desta instalação moram."""
    de_fora = os.environ.get(VARIAVEL, "")
    if de_fora:
        return Path(de_fora)
    from django.conf import settings

    return Path(settings.BASE_DIR) / "midia"
