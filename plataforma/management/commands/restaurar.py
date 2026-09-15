"""O comando `restaurar`: o caminho de volta do backup.

A ação mais destrutiva do sistema inteiro — por cima do banco vivo — por
isso exige `--confirmar` explicitamente. Tab-completion e hábito de
`up-arrow` não podem custar os dados do cliente.

Postgres: `pg_restore --clean --if-exists` do dump custom. SQLite: fecha as
conexões do processo e repõe o arquivo (é o banco de desenvolvimento — em
produção o banco é o Postgres do compose).

Uso: `python manage.py restaurar backups/kronos-...backup --confirmar`
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from plataforma.backup import (
    DENTRO_BANCO, DENTRO_MIDIA, argumentos_pg_dump, e_pacote,
)


class Command(BaseCommand):
    help = "Restaura um backup por cima do banco desta instalação."

    def add_arguments(self, parser):
        parser.add_argument("arquivo", type=str)
        parser.add_argument("--confirmar", action="store_true",
                            help="Obrigatório: restaurar apaga o estado ATUAL do banco.")

    def handle(self, *args, **opcoes):
        if not opcoes.get("confirmar"):
            raise CommandError(
                "Restaurar APAGA o estado atual do banco. Releia o arquivo "
                "certo e rode de novo com --confirmar.")

        origem = Path(opcoes["arquivo"])
        if not origem.is_file():
            raise CommandError(f"Arquivo não encontrado: {origem}")

        from django.db import connection

        # Só Postgres, como no `backupar` — o caminho de SQLite saiu com ele
        # em 09/09/2026, e o porquê está escrito lá.
        if connection.vendor != "postgresql":
            raise CommandError(
                f"Restauração não implementada para {connection.vendor!r} "
                f"— este produto roda em Postgres (ver KRONOS_BANCO).")

        # **Os dois formatos**: o pacote de hoje (dump + mídia) e o dump
        # sozinho, de antes de 10/09/2026. Um backup de ontem não pode virar
        # arquivo inútil por causa de uma mudança nossa — e quem restaura um
        # antigo precisa SABER que ele não traz foto nenhuma, antes de
        # descobrir pela tela.
        if e_pacote(origem):
            self._restaurar_pacote(origem)
        else:
            self._restaurar_postgres(origem)
            self.stdout.write(self.style.WARNING(
                "Este backup é do formato antigo: só o banco. As fotos de "
                "produto NÃO vieram nele (elas saíram do banco em "
                "10/09/2026) — o catálogo vai abrir sem imagem."))

        if opcoes.get("verbosity", 1):
            self.stdout.write(self.style.SUCCESS(
                f"Restaurado de {origem}."))

    def _restaurar_pacote(self, origem: Path) -> None:
        """O pacote: o dump por cima do banco, e a pasta de mídia no lugar.

        **O banco primeiro, a mídia depois.** Se o `pg_restore` falhar, a
        pasta atual fica intocada — e uma pasta de fotos que sobrou é o
        estado recuperável; um banco restaurado apontando para arquivos que
        foram substituídos por outros, não.

        **A mídia vai para o lado e só depois é trocada.** A pasta antiga é
        renomeada, não apagada: se a extração falhar no meio, o que havia
        antes ainda está no disco, com nome, para quem precisar voltar.

        `filter="data"` na extração porque um tar carrega o que quem o montou
        quis — link simbólico para fora, caminho absoluto, permissão de
        execução. Aqui o tar é nosso, mas restaurar aceita o arquivo que
        mandarem, e esse é o dia em que a diferença aparece.
        """
        import tarfile
        import tempfile

        from plataforma.midia import raiz as raiz_da_midia

        with tempfile.TemporaryDirectory() as temporario:
            pasta = Path(temporario)
            with tarfile.open(origem, "r:gz") as pacote:
                pacote.extractall(pasta, filter="data")

            dump = pasta / DENTRO_BANCO
            if not dump.is_file():
                raise CommandError(
                    f"O pacote não tem {DENTRO_BANCO} dentro — ele não foi "
                    f"gerado por `manage.py backupar`.")
            self._restaurar_postgres(dump)

            vinda = pasta / DENTRO_MIDIA
            destino = raiz_da_midia()
            if not vinda.exists():
                self.stdout.write(self.style.WARNING(
                    "O pacote não trazia pasta de mídia — o banco foi "
                    "restaurado e o catálogo vai abrir sem imagem."))
                return
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.exists():
                aposentada = destino.with_name(f"{destino.name}.anterior")
                if aposentada.exists():
                    import shutil

                    shutil.rmtree(aposentada)
                destino.rename(aposentada)
                self.stdout.write(
                    f"A pasta de mídia anterior ficou em {aposentada}.")
            import shutil

            shutil.move(str(vinda), str(destino))

    def _restaurar_postgres(self, origem: Path) -> None:
        url = os.environ.get("KRONOS_BANCO", "")
        if not url:
            raise CommandError("KRONOS_BANCO não está definida.")
        argv, ambiente = argumentos_pg_dump(url)
        # `pg_restore` no lugar do pg_dump, com os mesmos argumentos de
        # conexão, mais o que faz a restauração por cima do existente.
        argv[0] = "pg_restore"
        argv[1:1] = ["--clean", "--if-exists", "--no-owner"]

        # O NOME DO BANCO PRECISA DE `-d`. O `pg_dump` aceita o banco como
        # último argumento posicional; o `pg_restore` NÃO — ele recusa com
        # "one of -d/--dbname and -f/--file must be specified" e nem começa.
        # Reaproveitar o argv do dump trocando só o argv[0] parecia
        # economia e era um comando que nunca rodou: o teste que existia
        # dublava o subprocesso e conferia a FORMA do argv, então via o
        # nome no lugar certo para o pg_dump e dava verde.
        argv[-1:] = ["-d", argv[-1]]

        # Fecha as conexões do processo antes de repor — o mesmo que o
        # caminho do SQLite já fazia, e aqui por um motivo mais forte:
        # `--clean` DERRUBA cada objeto antes de recriar, e um objeto em uso
        # por esta própria conexão não cai.
        from django.db import connection as conexao

        conexao.close()

        pronto = subprocess.run(argv, stdin=open(origem, "rb"),
                                stderr=subprocess.PIPE,
                                env={**os.environ, **ambiente})
        if pronto.returncode != 0:
            raise CommandError(
                "pg_restore terminou com erro — veja o log do container.")
