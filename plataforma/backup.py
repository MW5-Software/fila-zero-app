"""O mecanismo do backup: nomes, diretório, retenção e os argumentos do
`pg_dump`.

O que é PURO mora aqui (e é testado sem banco nem subprocesso); os comandos
(`manage.py backupar` / `restaurar`) só costuram isto com o mecanismo certo
para o banco da instalação.

Ver o docstring de `tests/test_backup.py` para as decisões e o limite do
transporte remoto.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

__all__ = ["DENTRO_BANCO", "DENTRO_MIDIA", "EXTENSOES", "argumentos_pg_dump",
           "caminho_do_diretorio", "e_pacote", "nome_do_arquivo", "podar"]

#: O prefixo que a poda reconhece como seu. Arquivo de outro nome no mesmo
#: diretório NUNCA é tocado.
PREFIXO = "kronos-"

#: **Duas extensões, e a velha continua valendo.** Até 10/09/2026 o backup
#: era só o dump (`.backup`); desde que a foto de produto saiu do banco
#: (`catalogo/armazenamento.py`), ele é um pacote com o dump E a pasta de
#: mídia. A poda precisa reconhecer os dois, senão os backups antigos nunca
#: mais seriam apagados e o diretório cresceria para sempre; e o `restaurar`
#: precisa LER os dois, senão um backup de ontem vira um arquivo inútil.
EXTENSOES = (".tar.gz", ".backup")

#: Os dois nomes dentro do pacote. Fixos de propósito: o `restaurar` procura
#: por eles, e um nome que dependesse da data faria a restauração ter de
#: adivinhar.
DENTRO_BANCO = "banco.dump"
DENTRO_MIDIA = "midia"


def nome_do_arquivo() -> str:
    """`kronos-2026-08-26-143005.tar.gz` — ordenável pelo próprio nome."""
    return datetime.now().strftime(f"{PREFIXO}%Y-%m-%d-%H%M%S.tar.gz")


def e_pacote(caminho: Path) -> bool:
    """Se este arquivo é o pacote novo (dump + mídia) ou o dump sozinho.

    Decidido pelos BYTES (a assinatura do gzip), nunca pela extensão: o nome
    do arquivo é escolhido por quem restaura, e restaurar é a operação mais
    destrutiva que existe aqui. Um `.tar.gz` renomeado para `.backup` iria
    direto para o `pg_restore`, que recusaria com uma mensagem sobre formato
    — e a pessoa concluiria que o backup está corrompido.
    """
    with open(caminho, "rb") as arquivo:
        return arquivo.read(2) == b"\x1f\x8b"


def caminho_do_diretorio() -> Path:
    """Onde os dumps vivem: `KRONOS_BACKUP_DIR`, ou `backups/` do projeto."""
    de_fora = os.environ.get("KRONOS_BACKUP_DIR", "")
    if de_fora:
        return Path(de_fora)
    from django.conf import settings

    return Path(settings.BASE_DIR) / "backups"


def podar(diretorio: Path, manter: int) -> list[Path]:
    """Apaga os dumps mais velhos, ficando com os `manter` mais novos.

    Só toca em arquivo com o prefixo do backup — o diretório pode ser o
    mesmo de outra coisa. Devolve o que apagou.
    """
    dumps = sorted(
        (p for p in diretorio.iterdir()
         if p.is_file() and p.name.startswith(PREFIXO)
         and p.name.endswith(EXTENSOES)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    podados = dumps[manter:]
    for velho in podados:
        velho.unlink()
    return podados


def argumentos_pg_dump(url: str) -> "tuple[list[str], dict[str, str]]":
    """`KRONOS_BANCO` → (argv do pg_dump, ambiente do processo filho).

    A senha vai de `PGPASSWORD` e NUNCA no argv: a linha de comando é
    pública dentro do próprio VPS (`ps aux`), e segredo em argv é segredo
    lido por qualquer processo da máquina.
    """
    partes = urlsplit(url)
    if partes.scheme not in ("postgres", "postgresql"):
        raise ValueError(
            "O backup por pg_dump espera um banco Postgres em KRONOS_BANCO.")
    argv = ["pg_dump", "--no-owner", "-Fc"]
    if partes.hostname:
        argv += ["-h", partes.hostname]
    if partes.port:
        argv += ["-p", str(partes.port)]
    if partes.username:
        argv += ["-U", partes.username]
    ambiente: dict[str, str] = {}
    if partes.password:
        ambiente["PGPASSWORD"] = partes.password
    # O pathname vem com a barra inicial: `kronos_cliente`, não `/kronos_...`
    argv.append((partes.path or "").lstrip("/"))
    return argv, ambiente
