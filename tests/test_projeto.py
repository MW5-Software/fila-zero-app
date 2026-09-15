"""O projeto Django sobe, e o app do design system está dentro dele.

Um teste bobo de propósito: se ele falha, nada mais do plano roda, e o erro
aparece aqui em vez de aparecer disfarçado de import quebrado três tarefas
adiante.
"""

import os
import subprocess
import sys

from django.conf import settings


def test_o_app_do_nucleo_esta_instalado():
    assert "nucleo" in settings.INSTALLED_APPS


def test_o_projeto_passa_no_check_do_django():
    from django.core.management import call_command

    call_command("check")


def test_sem_secret_key_e_sem_debug_o_settings_recusa_subir():
    """Falha fechado, de propósito: fora de DEBUG, a ausência de
    DJANGO_SECRET_KEY não pode cair num fallback conhecido em silêncio — o
    processo tem que recusar subir. Um subprocesso, e não `importlib.reload`,
    porque `config.settings` já está importado (e com `DJANGO_SECRET_KEY`
    presente) no processo que roda esta suíte; um processo novo, com as duas
    variáveis ausentes, é o único jeito honesto de provar o caminho de
    inicialização do zero.

    Se algum dia alguém "resolver" a fricção reabrindo o padrão (por exemplo,
    devolvendo um valor fixo de SECRET_KEY), este teste fica vermelho.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS")
    }
    env["DJANGO_SETTINGS_MODULE"] = "config.settings"
    resultado = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=str(settings.BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode != 0
    assert "ImproperlyConfigured" in resultado.stderr
    assert "DJANGO_SECRET_KEY" in resultado.stderr


class TestOBancoESempreOMesmo:
    """Postgres em toda instalação, inclusive em desenvolvimento e na suíte.

    Havia aqui um caminho de SQLite quando `KRONOS_BANCO` estava vazio, com
    o comentário afirmando que "o esquema é o mesmo nos dois". O esquema é;
    o comportamento não — transação, `CheckConstraint`, ordenação com
    acento, `distinct`, tipo de coluna. Provar num banco e entregar noutro é
    provar a coisa errada.

    E o custo apareceu antes disso: com os dois caminhos vivos, a mesma
    instalação tinha DOIS bancos, porque `runserver` sem a variável caía no
    SQLite sem avisar — cadastrava-se num e olhava-se no outro.
    """

    def test_a_suite_roda_em_postgres(self):
        """Se este teste ficar vermelho, a suíte inteira está provando a
        coisa errada — e nada mais aqui dentro vale o que diz.

        É o único teste desta suíte cuja falha invalida os outros mil e
        quatrocentos, e por isso ele mora aqui, junto do `check`.
        """
        from django.db import connection

        assert connection.vendor == "postgresql", (
            f"a suíte está rodando em {connection.vendor!r}. O KRONOS roda "
            f"em Postgres em toda instalação; ver KRONOS_BANCO no README."
        )

    def test_o_settings_nao_tem_mais_caminho_de_sqlite(self):
        """A regra mora numa linha do `settings`, e recarregar o módulo para
        testá-la deixaria o processo com metade da configuração antiga (ver
        o topo deste arquivo). Então o que se verifica é o que sobrou: não
        existe engine de SQLite escrito em lugar nenhum da configuração.

        Sem isto, alguém "conserta" um dia de trabalho perdido pondo o
        fallback de volta, e nada acusa até a próxima divergência entre os
        dois bancos.
        """
        from pathlib import Path

        import config

        fonte = (Path(config.__file__).parent / "settings.py").read_text()
        assert "sqlite3" not in fonte, (
            "voltou um caminho de SQLite ao settings — ver o comentário de "
            "KRONOS_BANCO ali mesmo"
        )
