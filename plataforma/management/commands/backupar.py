"""O comando `backupar`: o dump da instalação num arquivo com data.

`pg_dump -Fc` — formato custom comprimido, o que o `restaurar` (e o
`pg_restore`) lê.

**Havia um segundo caminho, para SQLite, e ele saiu em 09/09/2026.** O
projeto passou a exigir Postgres em toda instalação, com o `settings`
falhando fechado sem `KRONOS_BANCO` — e o comentário que está lá conta o
preço de ter tido os dois caminhos vivos: a mesma instalação chegou a ter
DOIS bancos, cadastrando-se num e olhando-se no outro. O caminho de SQLite
daqui era o último resto disso: código que nenhum banco desta casa alcança,
num comando que ninguém executa por meses e que precisa funcionar no pior
dia. Vendor que não seja Postgres agora é recusa, não um segundo mecanismo.

Uso: `python manage.py backupar` (opcional `--manter N`, que é o padrão de
`KRONOS_BACKUP_KEEP`, ou 30).
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from plataforma.backup import (
    DENTRO_BANCO, DENTRO_MIDIA, argumentos_pg_dump, caminho_do_diretorio,
    nome_do_arquivo, podar,
)


class Command(BaseCommand):
    help = "Faz o backup do banco desta instalação."

    def add_arguments(self, parser):
        parser.add_argument("--manter", type=int, default=None,
                            help="Quantos backups recentes manter no diretório.")

    def handle(self, *args, **opcoes):
        from django.conf import settings
        from django.db import connection

        diretorio = caminho_do_diretorio()
        diretorio.mkdir(parents=True, exist_ok=True)
        destino = diretorio / nome_do_arquivo()

        if connection.vendor != "postgresql":
            raise CommandError(
                f"Backup não implementado para o banco {connection.vendor!r} "
                f"— este produto roda em Postgres (ver KRONOS_BANCO).")
        self._empacotar(destino)

        manter = opcoes.get("manter")
        if manter is None:
            manter = int(os.environ.get("KRONOS_BACKUP_KEEP", "30"))
        podados = podar(diretorio, manter=max(manter, 1))

        if opcoes.get("verbosity", 1):
            self.stdout.write(self.style.SUCCESS(
                f"Backup em {destino} "
                f"({datetime.now():%d/%m/%Y %H:%M:%S})."))
            if podados:
                self.stdout.write(
                    f"Poda: {len(podados)} backup(s) velho(s) apagado(s).")

    def _empacotar(self, destino: Path) -> None:
        """O dump E a pasta de mídia, num arquivo só.

        **Um gesto e um arquivo**, e é essa a propriedade que faz o backup
        acontecer de verdade. Quando a foto de produto saiu do banco
        (10/09/2026), o `pg_dump` deixou de ser o backup completo: restaurar
        num servidor novo traria o catálogo sem nenhuma foto. Deixar os dois
        artefatos separados seria transferir para quem restaura a obrigação
        de lembrar do segundo — no pior dia, e meses depois de alguém ter
        montado isso.

        **Escreve num temporário e renomeia.** Um backup interrompido no meio
        não pode ficar no diretório com nome de backup bom: o `restaurar`
        acharia um `.tar.gz` truncado, e a poda ainda contaria ele como um
        dos que se mantém — empurrando um backup íntegro para fora.
        """
        import tarfile
        import tempfile

        from plataforma.midia import raiz as raiz_da_midia

        parcial = destino.with_suffix(destino.suffix + ".parcial")
        with tempfile.TemporaryDirectory() as temporario:
            dump = Path(temporario) / DENTRO_BANCO
            self._backup_postgres(dump)
            with tarfile.open(parcial, "w:gz") as pacote:
                pacote.add(dump, arcname=DENTRO_BANCO)
                midia = raiz_da_midia()
                if midia.exists():
                    pacote.add(midia, arcname=DENTRO_MIDIA)
        parcial.replace(destino)

    def _backup_postgres(self, destino: Path) -> None:
        url = os.environ.get("KRONOS_BANCO", "")
        if not url:
            raise CommandError(
                "KRONOS_BANCO não está definida — não sei a qual banco "
                "fazer o dump.")
        try:
            argv, ambiente = argumentos_pg_dump(url)
        except ValueError as erro:
            raise CommandError(str(erro)) from erro
        with open(destino, "wb") as saida:
            pronto = subprocess.run(argv, stdout=saida,
                                    stderr=subprocess.PIPE,
                                    env={**os.environ, **ambiente})
        if pronto.returncode != 0:
            destino.unlink(missing_ok=True)
            # O stderr do pg_dump pode conter a máquina/banco — vai para o
            # log do processo, e não para a frase que a tela mostra.
            raise CommandError(
                "pg_dump terminou com erro — veja o log do container.")
