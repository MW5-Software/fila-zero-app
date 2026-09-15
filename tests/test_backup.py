"""O backup e a restauração — Bloco 7 (item 36).

Tudo que é dado desta instalação mora no banco (avatar, logo e favicon são
bytes em tabela — decisão antida e deliberada), então UM dump é o backup
completo. O que este módulo entrega:

- `backupar` (management command): dump do banco em arquivo com data no
  nome, num diretório configurável, podando os mais velhos que a retenção.
  Em produção (Postgres) é `pg_dump` em formato custom comprimido; no
  desenvolvimento (SQLite) é a cópia consistente da API de backup do
  próprio SQLite — o mecanismo muda, o comando não.
- `restaurar` (management command): o caminho de volta, com `--confirmar`
  OBRIGATÓRIO — restaurar por cima do banco vivo é a ação mais destrutiva
  do sistema, e acidente de tab-completion não pode custar os dados do
  cliente.

O limite, nomeado: este comando faz o dump LOCAL. Levar o arquivo para
fora do VPS (outro disco, outro estado) é procedimento de operação — o
cron no README documenta o agendamento; o transporte é do backup de quem
opera, porque credencial de armazém remoto na imagem das vinte instalações
seria vinte lugares para vazar.
"""

import os
import re
import shutil
from pathlib import Path

from django.test import override_settings
from django.core.management import call_command
from django.core.management.base import CommandError

import pytest

from plataforma.backup import (
    argumentos_pg_dump, caminho_do_diretorio, nome_do_arquivo, podar,
)


class TestONomeDoArquivo:
    def test_tem_o_prefixo_e_a_data_no_nome(self):
        """`.tar.gz` desde 10/09/2026: o backup deixou de ser só o dump e
        passou a ser um pacote com o banco E a pasta de mídia (a foto de
        produto saiu do `BinaryField`). A extensão mudou junto de propósito —
        um `.backup` que por dentro é tar enganaria quem o abrisse."""
        nome = nome_do_arquivo()
        assert re.fullmatch(r"kronos-\d{4}-\d{2}-\d{2}-\d{6}\.tar\.gz", nome), nome

    def test_dois_chamados_no_mesmo_segundo_nao_colidem_no_teste(self):
        """O nome só precisa ser determinístico por instante — a poda conta
        no mtime do arquivo, e não no nome."""
        assert nome_do_arquivo() == nome_do_arquivo()


class TestODiretorio:
    def test_o_padrao_e_dentro_do_projeto(self, settings, tmp_path):
        settings.BASE_DIR = tmp_path
        assert caminho_do_diretorio() == tmp_path / "backups"

    def test_a_variavel_de_ambiente_vence(self, settings, tmp_path, monkeypatch):
        monkeypatch.setenv("KRONOS_BACKUP_DIR", str(tmp_path / "fora"))
        settings.BASE_DIR = tmp_path
        assert caminho_do_diretorio() == tmp_path / "fora"


class TestAPoda:
    def test_mantem_os_mais_novos_e_nao_toca_arquivo_de_outro_nome(self, tmp_path):
        from datetime import datetime, timedelta

        agora = datetime.now().timestamp()
        nomes = []
        # **Os dois formatos misturados, de propósito.** O backup virou pacote
        # (`.tar.gz`) em 10/09/2026 e os antigos (`.backup`) continuam no
        # diretório de quem já rodava — uma poda que só enxergasse a extensão
        # nova deixaria os velhos para sempre, e o diretório cresceria ao lado
        # da retenção funcionando.
        for posicao, dias in enumerate((10, 8, 6, 4, 2)):
            extensao = ".backup" if posicao % 2 == 0 else ".tar.gz"
            alvo = tmp_path / f"kronos-2026-08-{28 - dias:02d}-000000{extensao}"
            alvo.write_bytes(b"x")
            import os

            os.utime(alvo, (agora - dias * 86400, agora - dias * 86400))
            nomes.append(alvo)
        estranho = tmp_path / "nao-e-backup.txt"
        estranho.write_text("nada")

        podados = podar(tmp_path, manter=2)

        # Os dois mais novos ficam; os três mais velhos saem.
        sobraram = {p.name for p in tmp_path.glob("kronos-*")}
        assert sobraram == {nomes[-1].name, nomes[-2].name}
        assert all(p in podados for p in nomes[:3])
        assert estranho.exists()

    def test_manter_maior_que_a_quantidade_nao_apaga_nada(self, tmp_path):
        (tmp_path / "kronos-2026-08-28-000000.backup").write_bytes(b"x")
        assert podar(tmp_path, manter=30) == []


class TestOsArgumentosDoPgDump:
    def test_a_url_vira_argumentos_sem_senha_no_comando(self):
        """A senha NUNCA vai na linha de comando: `ps aux` do VPS mostraria.
        Ela vai de `PGPASSWORD`, que é ambiente do processo filho."""
        argv, ambiente = argumentos_pg_dump(
            "postgres://usuario:segredo@banco.local:5433/kronos_cliente")
        assert argv[:2] == ["pg_dump", "--no-owner"]
        assert "-Fc" in argv
        assert "-h" in argv and "banco.local" in argv
        assert "-p" in argv and "5433" in argv
        assert "-U" in argv and "usuario" in argv
        assert argv[-1] == "kronos_cliente"
        juntos = " ".join(argv)
        assert "segredo" not in juntos
        assert ambiente["PGPASSWORD"] == "segredo"

    def test_url_que_nao_e_postgres_e_recusada(self):
        with pytest.raises(ValueError):
            argumentos_pg_dump("mysql://alguem:senha@host/db")


#: `pg_dump` e `pg_restore` na máquina que roda a suíte.
#:
#: O ciclo inteiro só se prova com os binários de verdade — foi por isso que
#: ele viveu em SQLite por tanto tempo, e por isso a dívida
#: (`docs/superpowers/divida-2026-08-27-backup-em-postgres.md`) ficou aberta.
#: No CI eles existem, e o workflow FALHA antes da suíte se não existirem:
#: um teste de backup que passa por ter sido pulado é pior que nenhum.
_TEM_CLIENTE = all(shutil.which(b) for b in ("pg_dump", "pg_restore"))

#: O módulo do COMANDO, e não `plataforma.backup`: ele faz
#: `from plataforma.backup import nome_do_arquivo`, então a referência já
#: está ligada e trocar na origem não alcança quem já importou.
_COMANDO = "plataforma.management.commands.backupar"

precisa_do_cliente = pytest.mark.skipif(
    not _TEM_CLIENTE,
    reason="pg_dump/pg_restore não estão nesta máquina — o ciclo real só "
           "roda onde eles existem (é o caso do CI)")


@pytest.fixture
def banco_de_verdade(tmp_path, django_db_blocker):
    """Um banco POSTGRES próprio, criado e destruído por este fixture.

    **Por que um banco à parte e não o dos testes.** `restaurar` roda
    `pg_restore --clean`, que DERRUBA e recria cada objeto do banco. Fazer
    isso no banco da suíte levaria junto o schema que os outros testes
    esperam encontrar — e o estrago apareceria como falhas aleatórias em
    arquivos que não têm nada a ver com backup.

    **Por que não o `db` do pytest-django.** Ele embrulha o teste numa
    transação NA CONEXÃO que este fixture precisa fechar e reapontar; fechar
    conexão alheia em transação é o deadlock exato. Mesmo motivo do fixture
    de SQLite que este substitui.

    O re-apontamento é DIRETO no `settings_dict` da conexão: a conexão viva
    guarda o dicionário de quando nasceu, e trocar `settings.DATABASES` lá
    fora não a move de banco — o `migrate` correria no banco de sempre.
    """
    import os

    import dj_database_url
    from django.core.management import call_command
    from django.db import connection

    url_base = os.environ["KRONOS_BANCO"]
    nome = f"ciclo_backup_{os.getpid()}"
    partes = dj_database_url.parse(url_base)
    url_do_ciclo = _trocar_o_banco(url_base, nome)

    with django_db_blocker.unblock():
        _no_servidor(partes, f'DROP DATABASE IF EXISTS "{nome}"')
        _no_servidor(partes, f'CREATE DATABASE "{nome}"')

        original = dict(connection.settings_dict)
        anterior = os.environ.get("KRONOS_BANCO")
        connection.close()
        connection.settings_dict = {**original, "NAME": nome,
                                    "TEST": {**original.get("TEST", {}),
                                             "NAME": nome}}
        # Os comandos leem `KRONOS_BANCO` do ambiente para montar o argv do
        # `pg_dump` — apontar só a conexão do Django deixaria o dump indo
        # para o banco errado, que é o jeito mais silencioso de este teste
        # passar sem provar nada.
        os.environ["KRONOS_BANCO"] = url_do_ciclo
        call_command("migrate", verbosity=0)
        try:
            yield nome
        finally:
            connection.close()
            connection.settings_dict = original
            if anterior is None:
                os.environ.pop("KRONOS_BANCO", None)
            else:
                os.environ["KRONOS_BANCO"] = anterior
            connection.close()
            _no_servidor(partes, f'DROP DATABASE IF EXISTS "{nome}"')


def _trocar_o_banco(url: str, nome: str) -> str:
    """A mesma URL apontando para outro banco no mesmo servidor."""
    from urllib.parse import urlsplit, urlunsplit

    partes = urlsplit(url)
    return urlunsplit(partes._replace(path=f"/{nome}"))


def _no_servidor(partes: dict, sql: str) -> None:
    """Roda um comando no banco `postgres`, fora de transação.

    `CREATE DATABASE` e `DROP DATABASE` não rodam dentro de transação, e o
    psycopg abre uma por padrão — daí o `autocommit`.
    """
    import psycopg

    with psycopg.connect(
            host=partes["HOST"], port=partes["PORT"], user=partes["USER"],
            password=partes["PASSWORD"], dbname="postgres",
            autocommit=True) as conexao:
        conexao.execute(sql)


@precisa_do_cliente
class TestOCicloEmPostgres:
    """**O que esta dívida era**: `backupar` e `restaurar` tinham dois
    caminhos, SQLite e Postgres. O ciclo INTEIRO — gravar, fazer backup,
    destruir, restaurar, conferir que voltou — só existia para o SQLite. O
    caminho do Postgres, que é o que roda em produção, era provado só por
    dublê: que o `pg_dump` recebia os argumentos certos, e que as recusas
    recusavam. Nunca que o backup e a restauração FUNCIONAM.

    Backup é o código que ninguém executa por meses e que precisa funcionar
    no pior dia. Aqui ele roda de verdade: `pg_dump` escreve o arquivo,
    `pg_restore` repõe por cima, e o dado volta.
    """

    def test_o_dump_e_um_arquivo_de_verdade_com_conteudo(
            self, tmp_path, banco_de_verdade, settings):
        from plataforma.models import Marca

        Marca.objects.create(client_name="Quem vai no dump")
        settings.BASE_DIR = tmp_path
        call_command("backupar", verbosity=0)

        arquivos = list((tmp_path / "backups").glob("kronos-*.tar.gz"))
        assert len(arquivos) == 1
        # **O arquivo é o PACOTE, e o dump vive DENTRO dele** (10/09/2026).
        # Antes a assinatura `PGDMP` era conferida no próprio arquivo; hoje
        # ela é conferida no item extraído — que é onde ela ainda prova a
        # mesma coisa: que o `pg_dump` rodou e produziu um dump de verdade,
        # e não que algum byte foi escrito.
        import tarfile

        with tarfile.open(arquivos[0], "r:gz") as pacote:
            dump = pacote.extractfile("banco.dump").read()
        assert dump[:5] == b"PGDMP"
        assert len(dump) > 1000

    def test_dois_backups_vivem_juntos_e_a_retencao_poda(
            self, tmp_path, banco_de_verdade, settings, monkeypatch):
        settings.BASE_DIR = tmp_path
        monkeypatch.setattr(_COMANDO + ".nome_do_arquivo",
                            lambda: "kronos-2026-01-01-000001.tar.gz")
        call_command("backupar", verbosity=0)
        monkeypatch.setattr(_COMANDO + ".nome_do_arquivo",
                            lambda: "kronos-2026-01-02-000002.tar.gz")
        call_command("backupar", verbosity=0)
        assert len(list((tmp_path / "backups").glob("kronos-*.tar.gz"))) == 2

        call_command("backupar", manter=1, verbosity=0)
        assert len(list((tmp_path / "backups").glob("kronos-*.tar.gz"))) == 1

    def test_sem_confirmar_e_recusado_antes_de_tocar_em_qualquer_coisa(
            self, tmp_path, banco_de_verdade, settings):
        from plataforma.models import Marca

        Marca.objects.create(client_name="Intacta")
        settings.BASE_DIR = tmp_path
        call_command("backupar", verbosity=0)
        arquivo = next((tmp_path / "backups").glob("kronos-*.tar.gz"))

        with pytest.raises(CommandError, match="confirmar"):
            call_command("restaurar", str(arquivo), verbosity=0)
        # A recusa é ANTES de tocar em qualquer coisa: o banco continua como
        # estava. Restaurar por cima do banco vivo é a ação mais destrutiva
        # do sistema, e acidente de tab-completion não pode custar os dados.
        assert Marca.objects.count() == 1

    def test_o_ciclo_inteiro_devolve_as_FOTOS_tambem(
            self, tmp_path, banco_de_verdade, settings, monkeypatch):
        """**A prova que a mudança de 10/09/2026 exigia, e que faltava.**

        Quando a foto de produto saiu do `BinaryField` para o disco, o
        `pg_dump` deixou de ser o backup completo. O `backupar` passou a
        empacotar a pasta junto e o `restaurar` a devolvê-la — e nada
        exercitava esse caminho de ponta a ponta.

        O buraco era duplo, e o segundo é o que ensina: os quatro testes de
        ciclo real são PULADOS nesta máquina (não há `pg_dump` instalado) e
        só rodam no CI. Eu mudei o formato do arquivo, rodei a suíte local
        verde, e as quatro quebraram no CI procurando `.backup`. Teste que
        não roda onde se trabalha é teste que avisa tarde.

        Aqui a pasta é destruída ENTRE o backup e a restauração, como um
        disco trocado faria.
        """
        from plataforma.midia import raiz

        settings.BASE_DIR = tmp_path
        midia = tmp_path / "midia-do-ciclo"
        monkeypatch.setenv("KRONOS_MIDIA", str(midia))
        foto = midia / "arquivos" / "7" / "uma.jpg"
        foto.parent.mkdir(parents=True)
        foto.write_bytes(b"os-bytes-da-foto")
        assert raiz() == midia

        call_command("backupar", verbosity=0)
        arquivo = next((tmp_path / "backups").glob("kronos-*.tar.gz"))

        # O disco some — é o caso que o backup existe para atender.
        import shutil

        shutil.rmtree(midia)
        assert not foto.exists()

        call_command("restaurar", str(arquivo), confirmar=True, verbosity=0)

        assert foto.is_file(), (
            "o banco voltou e os arquivos não — um backup que restaura o "
            "cadastro sem as imagens dele")
        assert foto.read_bytes() == b"os-bytes-da-foto"

    def test_restaurar_guarda_a_pasta_anterior_em_vez_de_apagar(
            self, tmp_path, banco_de_verdade, settings, monkeypatch):
        """Se a extração falhasse no meio, o que havia antes precisa ainda
        estar no disco — com nome — para quem precisar voltar."""
        settings.BASE_DIR = tmp_path
        midia = tmp_path / "midia-do-ciclo"
        monkeypatch.setenv("KRONOS_MIDIA", str(midia))
        (midia / "produtos").mkdir(parents=True)
        (midia / "produtos" / "antiga.jpg").write_bytes(b"a-que-estava-la")

        call_command("backupar", verbosity=0)
        arquivo = next((tmp_path / "backups").glob("kronos-*.tar.gz"))
        (midia / "produtos" / "depois.jpg").write_bytes(b"gravada-depois")

        call_command("restaurar", str(arquivo), confirmar=True, verbosity=0)

        anterior = midia.with_name(midia.name + ".anterior")
        assert (anterior / "produtos" / "depois.jpg").is_file(), (
            "a pasta anterior foi apagada em vez de ficar ao lado")
        assert not (midia / "produtos" / "depois.jpg").exists(), (
            "o que foi gravado DEPOIS do backup não pode sobreviver a ele")

    def test_o_ciclo_inteiro_backup_destroi_restaura(
            self, tmp_path, banco_de_verdade, settings):
        """A prova que faltava, e agora contra o banco de produção: o que foi
        gravado DEPOIS do backup some, e o que existia ANTES volta.

        Restauração que nunca foi testada é esperança, não backup.
        """
        from plataforma.models import Marca

        Marca.objects.create(client_name="Da época do backup")
        settings.BASE_DIR = tmp_path
        call_command("backupar", verbosity=0)
        arquivo = next((tmp_path / "backups").glob("kronos-*.tar.gz"))

        Marca.objects.create(client_name="Depois do backup")
        assert Marca.objects.count() == 2

        call_command("restaurar", str(arquivo), confirmar=True, verbosity=0)

        from django.db import connection

        connection.close()  # o `pg_restore --clean` derrubou os objetos
        nomes = set(Marca.objects.values_list("client_name", flat=True))
        assert nomes == {"Da época do backup"}


@precisa_do_cliente
class TestOQueOComandoDizNoCicloReal:
    """A mensagem é parte do comando: quem roda `backupar` num cron às três da
    manhã lê o log, não o código."""

    def test_o_sucesso_diz_onde_o_arquivo_ficou(
            self, tmp_path, banco_de_verdade, settings, capsys):
        settings.BASE_DIR = tmp_path
        call_command("backupar")
        saida = capsys.readouterr().out
        assert str(tmp_path / "backups") in saida

    def test_a_poda_diz_quantos_apagou(
            self, tmp_path, banco_de_verdade, settings, capsys, monkeypatch):
        settings.BASE_DIR = tmp_path
        for dia in (1, 2, 3):
            monkeypatch.setattr(
                _COMANDO + ".nome_do_arquivo",
                lambda dia=dia: f"kronos-2026-01-0{dia}-00000{dia}.backup")
            call_command("backupar", verbosity=0)

        capsys.readouterr()
        call_command("backupar", manter=1)
        assert "3" in capsys.readouterr().out

    def test_restaurar_diz_de_onde_repos(
            self, tmp_path, banco_de_verdade, settings, capsys):
        settings.BASE_DIR = tmp_path
        call_command("backupar", verbosity=0)
        arquivo = next((tmp_path / "backups").glob("kronos-*.tar.gz"))

        capsys.readouterr()
        call_command("restaurar", str(arquivo), confirmar=True)
        assert arquivo.name in capsys.readouterr().out


# ---------------------------------------------------------------------------
# O caminho de PRODUÇÃO (Postgres) e as recusas.
#
# Estas classes nasceram de uma auditoria que mediu a cobertura destes dois
# comandos em 56% e 57%: o que estava coberto era o SQLite do
# desenvolvimento, e o que estava DESCOBERTO era justamente o caminho que
# roda nas vinte instalações — `pg_dump`, `pg_restore`, e toda recusa.
#
# Backup é o código que ninguém executa por meses e que precisa funcionar no
# pior dia. Testar o caminho fácil e deixar o de produção sem rede era o
# risco mais caro do relatório.
#
# O subprocesso é dublado de propósito: o que se testa aqui é o CONTRATO com
# o `pg_dump` (que argumentos recebe, o que acontece quando ele falha, o que
# a mensagem revela), não o `pg_dump` em si — ele não está instalado na
# máquina de teste, e depender disso tornaria a suíte refém do ambiente.
# ---------------------------------------------------------------------------

from unittest import mock  # noqa: E402


class _Vendor:
    """Finge o vendor da conexão sem tocar no banco de verdade."""

    def __init__(self, vendor):
        self.vendor = vendor
        self.connection = None
        self.settings_dict = {"NAME": ":memory:"}

    def close(self):
        pass


class TestBackuparEmPostgres:
    def test_sem_kronos_banco_recusa_dizendo_o_que_falta(self, tmp_path):
        with mock.patch.dict(
                "os.environ",
                {"KRONOS_BANCO": "", "KRONOS_BACKUP_DIR": str(tmp_path)},
                clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")):
            with pytest.raises(CommandError, match="KRONOS_BANCO"):
                call_command("backupar")

    def test_chama_o_pg_dump_e_grava_a_saida_no_arquivo(self, tmp_path):
        """O contrato com o `pg_dump`: recebe os argumentos que
        `argumentos_pg_dump` monta, e a saída padrão dele vira o arquivo."""
        chamadas = {}

        def falso_run(argv, **kwargs):
            chamadas["argv"] = argv
            chamadas["env"] = kwargs.get("env", {})
            kwargs["stdout"].write(b"dump-de-mentira")
            return mock.Mock(returncode=0, stderr=b"")

        with mock.patch.dict(
                "os.environ",
                {"KRONOS_BANCO": "postgres://gente:senha@maquina:5432/base",
                 "KRONOS_BACKUP_DIR": str(tmp_path)},
                clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")), \
             mock.patch("subprocess.run", falso_run):
            call_command("backupar", verbosity=0)

        gerados = list(tmp_path.glob("*.tar.gz"))
        assert len(gerados) == 1
        # O dump não é mais o arquivo: ele é UM item DENTRO do pacote, ao
        # lado da pasta de mídia (10/09/2026).
        import tarfile

        with tarfile.open(gerados[0], "r:gz") as pacote:
            assert pacote.extractfile("banco.dump").read() == b"dump-de-mentira"
        assert chamadas["argv"][0] == "pg_dump"
        # A senha NUNCA vai na linha de comando: `ps` de qualquer processo do
        # servidor a leria. Vai no ambiente do subprocesso.
        assert not any("senha" in str(a) for a in chamadas["argv"])
        assert chamadas["env"].get("PGPASSWORD") == "senha"

    def test_pg_dump_falhando_apaga_o_arquivo_pela_metade(self, tmp_path):
        """Um arquivo truncado no diretório de backup é pior que arquivo
        nenhum: na hora do desespero alguém restauraria a metade."""
        def falso_run(argv, **kwargs):
            kwargs["stdout"].write(b"metade")
            return mock.Mock(returncode=1, stderr=b"FATAL: senha errada para o host interno")

        with mock.patch.dict(
                "os.environ",
                {"KRONOS_BANCO": "postgres://gente:senha@maquina:5432/base",
                 "KRONOS_BACKUP_DIR": str(tmp_path)},
                clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")), \
             mock.patch("subprocess.run", falso_run):
            with pytest.raises(CommandError) as erro:
                call_command("backupar", verbosity=0)

        assert list(tmp_path.glob("*.backup")) == []
        # A mensagem manda olhar o log, e NÃO repete o stderr: ele carrega
        # máquina e banco, e a tela de quem operou não é lugar para isso.
        assert "log do container" in str(erro.value)
        assert "maquina" not in str(erro.value)
        assert "senha errada" not in str(erro.value)


class TestRestaurarEmPostgres:
    def test_sem_confirmar_recusa_antes_de_qualquer_coisa(self, tmp_path):
        alvo = tmp_path / "qualquer.backup"
        alvo.write_bytes(b"x")
        with pytest.raises(CommandError, match="--confirmar"):
            call_command("restaurar", str(alvo))

    def test_arquivo_inexistente_recusa_dizendo_o_caminho(self, tmp_path):
        sumido = tmp_path / "nao-existe.backup"
        with pytest.raises(CommandError, match="não encontrado"):
            call_command("restaurar", str(sumido), confirmar=True)

    def test_banco_que_nao_e_postgres_recusa_com_o_motivo(self, tmp_path):
        """O caminho de SQLite saiu dos dois comandos em 09/09/2026 (ver o
        cabeçalho de `backupar`): este produto roda em Postgres, e o segundo
        mecanismo vivo já tinha custado uma instalação com dois bancos.

        A recusa continua sendo o comportamento — ela é a diferença entre
        parar e restaurar num lugar que ninguém conferiu."""
        alvo = tmp_path / "qualquer.backup"
        alvo.write_bytes(b"x")
        with mock.patch("django.db.connection", _Vendor("sqlite")):
            with pytest.raises(CommandError, match="não implementada"):
                call_command("restaurar", str(alvo), confirmar=True, verbosity=0)

    def test_chama_o_pg_restore_com_o_que_repoe_por_cima(self, tmp_path):
        """`--clean --if-exists` é o que faz a restauração repor por cima do
        banco existente em vez de esbarrar no que já está lá."""
        alvo = tmp_path / "backup.backup"
        alvo.write_bytes(b"dump")
        chamadas = {}

        def falso_run(argv, **kwargs):
            chamadas["argv"] = argv
            return mock.Mock(returncode=0, stderr=b"")

        with mock.patch.dict(
                "os.environ",
                {"KRONOS_BANCO": "postgres://gente:senha@maquina:5432/base",
                 "KRONOS_BACKUP_DIR": str(tmp_path)},
                clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")), \
             mock.patch("subprocess.run", falso_run):
            call_command("restaurar", str(alvo), confirmar=True, verbosity=0)

        assert chamadas["argv"][0] == "pg_restore"
        for bandeira in ("--clean", "--if-exists", "--no-owner"):
            assert bandeira in chamadas["argv"], bandeira

        # O NOME DO BANCO com `-d`, e é o que faltava. Este teste existia,
        # dublava o subprocesso e passava com o comando QUEBRADO: ele conferia
        # as bandeiras e não o banco, e o `pg_restore` recusava antes de
        # começar ("one of -d/--dbname and -f/--file must be specified").
        #
        # É o retrato exato do que a dívida dizia: provar o CONTRATO com o
        # binário não é provar que o comando funciona. Quem achou foi o ciclo
        # de verdade, em `TestOCicloEmPostgres`.
        assert chamadas["argv"][-2:] == ["-d", "base"]

    def test_pg_restore_falhando_vira_recusa_sem_vazar_o_stderr(self, tmp_path):
        alvo = tmp_path / "backup.backup"
        alvo.write_bytes(b"dump")

        def falso_run(argv, **kwargs):
            return mock.Mock(returncode=1, stderr=b"FATAL: base interna recusou")

        with mock.patch.dict(
                "os.environ",
                {"KRONOS_BANCO": "postgres://gente:senha@maquina:5432/base",
                 "KRONOS_BACKUP_DIR": str(tmp_path)},
                clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")), \
             mock.patch("subprocess.run", falso_run):
            with pytest.raises(CommandError) as erro:
                call_command("restaurar", str(alvo), confirmar=True, verbosity=0)

        assert "log do container" in str(erro.value)
        assert "base interna" not in str(erro.value)


class TestBancoNaoSuportado:
    def test_backupar_recusa_o_que_nao_sabe_fazer(self, tmp_path):
        with mock.patch.dict("os.environ",
                             {"KRONOS_BACKUP_DIR": str(tmp_path)}, clear=False), \
             mock.patch("django.db.connection", _Vendor("oracle")):
            with pytest.raises(CommandError, match="oracle"):
                call_command("backupar", verbosity=0)

    def test_restaurar_recusa_o_que_nao_sabe_fazer(self, tmp_path):
        alvo = tmp_path / "backup.backup"
        alvo.write_bytes(b"dump")
        with mock.patch("django.db.connection", _Vendor("oracle")):
            with pytest.raises(CommandError, match="oracle"):
                call_command("restaurar", str(alvo), confirmar=True, verbosity=0)


class TestOQueOComandoDIZ:
    """As recusas que não precisam de banco nenhum. O que o comando diz no
    ciclo REAL está em `TestOQueOComandoDizNoCicloReal`, acima."""

    def test_url_de_banco_invalida_vira_recusa_legivel(self, tmp_path):
        """`argumentos_pg_dump` recusa o que não sabe montar; o comando
        traduz isso em recusa do comando, e não em traceback."""
        with mock.patch.dict(
                "os.environ",
                {"KRONOS_BANCO": "mysql://alguem:senha@host/base",
                 "KRONOS_BACKUP_DIR": str(tmp_path)},
                clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")):
            with pytest.raises(CommandError):
                call_command("backupar", verbosity=0)

    def test_restaurar_em_postgres_sem_kronos_banco_recusa(self, tmp_path):
        alvo = tmp_path / "backup.backup"
        alvo.write_bytes(b"dump")
        with mock.patch.dict("os.environ", {"KRONOS_BANCO": ""}, clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")):
            with pytest.raises(CommandError, match="KRONOS_BANCO"):
                call_command("restaurar", str(alvo), confirmar=True, verbosity=0)


class TestOPacoteLevaAsFotos:
    """**O backup deixou de ser o dump no dia em que a foto saiu do banco.**

    Até 10/09/2026 `pg_dump` ERA o backup completo — o README dizia isso, e
    era verdade: avatar, logo e foto de produto eram bytes em tabela. Com a
    foto indo para `midia/` (ver `catalogo/armazenamento.py`), um dump sozinho
    passou a restaurar um catálogo sem nenhuma imagem.

    O defeito desse tipo não aparece quando se faz o backup: aparece meses
    depois, no pior dia, quando alguém restaura num servidor novo. Por isso os
    testes abaixo são sobre o PACOTE, e não sobre o comando ter rodado.
    """

    def _pacote(self, tmp_path, midia):
        """Roda o `backupar` com o pg_dump dublado e devolve o arquivo."""
        def falso_run(argv, **kwargs):
            kwargs["stdout"].write(b"dump-de-mentira")
            return mock.Mock(returncode=0, stderr=b"")

        with mock.patch.dict(
                "os.environ",
                {"KRONOS_BANCO": "postgres://gente:senha@maquina:5432/base",
                 "KRONOS_BACKUP_DIR": str(tmp_path / "backups"),
                 "KRONOS_MIDIA": str(midia)},
                clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")), \
             mock.patch("subprocess.run", falso_run):
            call_command("backupar", verbosity=0)
        return next((tmp_path / "backups").glob("*.tar.gz"))

    def test_a_pasta_de_midia_vai_dentro_do_pacote(self, tmp_path):
        import tarfile

        midia = tmp_path / "midia" / "produtos" / "7"
        midia.mkdir(parents=True)
        (midia / "uma.jpg").write_bytes(b"foto-de-mentira")

        pacote = self._pacote(tmp_path, tmp_path / "midia")

        with tarfile.open(pacote, "r:gz") as tar:
            dentro = tar.getnames()
            assert "banco.dump" in dentro
            achado = [n for n in dentro if n.endswith("uma.jpg")]
            assert achado, f"a foto não entrou no pacote: {dentro}"
            assert tar.extractfile(achado[0]).read() == b"foto-de-mentira"

    def test_sem_pasta_de_midia_o_pacote_sai_assim_mesmo(self, tmp_path):
        """Instalação que ainda não recebeu foto nenhuma. O backup não pode
        recusar por causa de uma pasta que nunca foi criada."""
        import tarfile

        pacote = self._pacote(tmp_path, tmp_path / "midia-que-nao-existe")

        with tarfile.open(pacote, "r:gz") as tar:
            assert "banco.dump" in tar.getnames()

    def test_o_pacote_incompleto_nao_fica_com_nome_de_backup_bom(self, tmp_path):
        """Interrompido no meio, ele não pode ficar no diretório parecendo
        íntegro: o `restaurar` o encontraria, e a poda ainda o contaria como
        um dos que se mantém — empurrando um backup bom para fora."""
        def falso_run(argv, **kwargs):
            kwargs["stdout"].write(b"metade")
            return mock.Mock(returncode=1, stderr=b"FATAL: caiu")

        destino = tmp_path / "backups"
        with mock.patch.dict(
                "os.environ",
                {"KRONOS_BANCO": "postgres://g:s@m:5432/b",
                 "KRONOS_BACKUP_DIR": str(destino),
                 "KRONOS_MIDIA": str(tmp_path / "midia")},
                clear=False), \
             mock.patch("django.db.connection", _Vendor("postgresql")), \
             mock.patch("subprocess.run", falso_run):
            with pytest.raises(CommandError):
                call_command("backupar", verbosity=0)

        assert not list(destino.glob("*.tar.gz"))


class TestORestaurarLeOsDoisFormatos:
    """Um backup de ontem não pode virar arquivo inútil por mudança nossa."""

    def test_reconhece_o_pacote_pelos_bytes_e_nao_pela_extensao(self, tmp_path):
        """O nome do arquivo é escolhido por quem restaura, e restaurar é a
        operação mais destrutiva que existe aqui. Um `.tar.gz` renomeado para
        `.backup` iria direto ao `pg_restore`, que recusaria falando de
        formato — e a pessoa concluiria que o backup está corrompido."""
        import tarfile

        from plataforma.backup import e_pacote

        disfarcado = tmp_path / "kronos-2026-09-10-120000.backup"
        with tarfile.open(disfarcado, "w:gz") as tar:
            dump = tmp_path / "banco.dump"
            dump.write_bytes(b"x")
            tar.add(dump, arcname="banco.dump")
        assert e_pacote(disfarcado) is True

        antigo = tmp_path / "kronos-2026-09-01-120000.backup"
        antigo.write_bytes(b"PGDMP\x00qualquer-coisa")
        assert e_pacote(antigo) is False

    def test_a_poda_alcanca_os_dois_formatos(self, tmp_path):
        """Sem isto os backups do formato antigo nunca mais seriam apagados,
        e o diretório cresceria para sempre ao lado da poda funcionando."""
        import time

        from plataforma.backup import podar

        for i, nome in enumerate(["kronos-a.backup", "kronos-b.tar.gz",
                                  "kronos-c.tar.gz"]):
            alvo = tmp_path / nome
            alvo.write_bytes(b"x")
            # `mtime` crescente: a poda ordena por ele, não pelo nome.
            os.utime(alvo, (1000 + i, 1000 + i))
            time.sleep(0)

        podados = podar(tmp_path, manter=1)

        assert {p.name for p in podados} == {"kronos-a.backup", "kronos-b.tar.gz"}
        assert (tmp_path / "kronos-c.tar.gz").exists()
