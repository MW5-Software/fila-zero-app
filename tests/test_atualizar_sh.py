"""O vocabulário fechado do atualizador do VPS.

O painel não manda comando: manda uma palavra. Este teste prova a porta:
só `atualizar` e `voltar <commit>` passam; commit é hash validado; texto
livre nunca chega ao shell.
"""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "atualizar.sh"


def rodar(
    ordem: str, tmp_path: Path, log_path: "str | None" = None,
) -> "tuple[int, str]":
    """Roda o script com `docker` e `curl` falsos, capturando o que eles
    receberam (gravado em `chamadas.txt` pelo falso).

    `log_path` permite apontar `KRONOS_LOG` para um lugar ingravável — o
    cenário do VPS mal provisionado: `/var/log` sem permissão para o
    usuário `deploy`."""
    falso = tmp_path / "bin"
    falso.mkdir(exist_ok=True)
    (falso / "docker").write_text(
        '#!/bin/bash\necho "docker $@" >> "$DIA/chamadas.txt"\nexit 0\n')
    (falso / "curl").write_text(
        '#!/bin/bash\necho "curl $@" >> "$DIA/chamadas.txt"\nexit 0\n')
    for f in (falso / "docker", falso / "curl"):
        f.chmod(0o755)
    ambiente = {
        "PATH": f"{falso}:{__import__('os').environ['PATH']}",
        "DIA": str(tmp_path),
        "KRONOS_DIR": str(tmp_path),
        # Sem isso o script tenta escrever em /var/log de verdade — e falha
        # com permissão negada para quem roda o teste sem ser root.
        "KRONOS_LOG": log_path or str(tmp_path / "kronos-atualizar.log"),
        "SSH_ORIGINAL_COMMAND": ordem,
    }
    pronto = subprocess.run(
        ["bash", str(SCRIPT)], env=ambiente, capture_output=True, text=True)
    chamadas = (tmp_path / "chamadas.txt")
    return pronto.returncode, chamadas.read_text() if chamadas.exists() else ""


def test_atualizar_roda_pull_e_up(tmp_path):
    codigo, chamadas = rodar("atualizar", tmp_path)
    assert codigo == 0
    assert "pull" in chamadas and "up -d" in chamadas


def test_voltar_com_commit_valido_fixa_a_tag(tmp_path):
    codigo, chamadas = rodar("voltar a1b2c3d", tmp_path)
    assert codigo == 0
    conteudo = (tmp_path / "deploy" / ".env").read_text()
    assert conteudo == "KRONOS_TAG=a1b2c3d\n"
    assert "pull" in chamadas


def test_atualizar_despina_a_tag_que_voltar_tinha_fixado(tmp_path):
    """O ciclo que morde na emergência: voltar às pressas, corrigir, atualizar.

    Sem tirar a linha `KRONOS_TAG` do `.env`, a instalação que voltou uma
    vez fica presa naquela versão para sempre — `atualizar` puxa a mesma
    imagem velha e o container sobe com sucesso, então nada acusa. Este
    teste é o que transforma isso em vermelho.

    A asserção é sobre o CONTEÚDO, não sobre o arquivo existir: `atualizar`
    mexe na linha, nunca apaga o `.env` inteiro (ele é do operador — ver
    `test_atualizar_preserva_as_variaveis_do_operador_no_env` logo abaixo,
    que é quem prova isso de verdade)."""
    rodar("voltar a1b2c3d", tmp_path)
    arquivo = tmp_path / "deploy" / ".env"
    assert "KRONOS_TAG=a1b2c3d" in arquivo.read_text()
    rodar("atualizar", tmp_path)
    assert "KRONOS_TAG" not in arquivo.read_text()


def test_voltar_preserva_as_variaveis_do_operador_no_env(tmp_path):
    """`.env` é do operador — é onde ele guarda `DJANGO_SECRET_KEY` e
    `KRONOS_BANCO`, que o compose exige com `${...:?}`. `voltar` só
    acrescenta a linha da tag; o resto do arquivo não é dele para mexer."""
    deploy_dir = tmp_path / "deploy"
    deploy_dir.mkdir()
    (deploy_dir / ".env").write_text(
        "DJANGO_SECRET_KEY=abc\nKRONOS_BANCO=postgres://x\n")
    codigo, _ = rodar("voltar a1b2c3d", tmp_path)
    assert codigo == 0
    conteudo = (deploy_dir / ".env").read_text()
    assert "DJANGO_SECRET_KEY=abc" in conteudo
    assert "KRONOS_BANCO=postgres://x" in conteudo
    assert "KRONOS_TAG=a1b2c3d" in conteudo


def test_atualizar_preserva_as_variaveis_do_operador_no_env(tmp_path):
    """O defeito que uma correção anterior deste script criou: um `rm -f`
    no `.env` inteiro para despinar a tag apagava junto as credenciais da
    instalação, e o `up -d` seguinte falhava com "defina
    DJANGO_SECRET_KEY" — em todas as 60, no primeiro clique em Atualizar.
    Este é o teste que teria pego aquele defeito."""
    deploy_dir = tmp_path / "deploy"
    deploy_dir.mkdir()
    (deploy_dir / ".env").write_text(
        "DJANGO_SECRET_KEY=abc\nKRONOS_BANCO=postgres://x\n"
        "KRONOS_TAG=a1b2c3d\n")
    codigo, _ = rodar("atualizar", tmp_path)
    assert codigo == 0
    conteudo = (deploy_dir / ".env").read_text()
    assert "KRONOS_TAG" not in conteudo
    assert "DJANGO_SECRET_KEY=abc" in conteudo
    assert "KRONOS_BANCO=postgres://x" in conteudo


def test_atualizar_sem_env_continua_funcionando(tmp_path):
    """Instalação nova, nunca voltou: não há `.env` nenhum, e não é erro —
    não existe tag para despinar."""
    assert not (tmp_path / "deploy" / ".env").exists()
    codigo, chamadas = rodar("atualizar", tmp_path)
    assert codigo == 0
    assert "pull" in chamadas and "up -d" in chamadas


def test_voltar_duas_vezes_nao_duplica_a_linha_da_tag(tmp_path):
    rodar("voltar a1b2c3d", tmp_path)
    rodar("voltar 9988776", tmp_path)
    conteudo = (tmp_path / "deploy" / ".env").read_text()
    assert conteudo.count("KRONOS_TAG=") == 1
    assert "KRONOS_TAG=9988776" in conteudo


def test_ordem_desconhecida_e_recusada_sem_chamar_docker(tmp_path):
    codigo, chamadas = rodar("rm -rf /", tmp_path)
    assert codigo == 2
    assert chamadas == ""


def test_voltar_com_texto_livre_e_recusado(tmp_path):
    codigo, _ = rodar("voltar algo; rm -rf /", tmp_path)
    assert codigo == 2


def test_ordem_desconhecida_sai_2_mesmo_com_log_ingravavel(tmp_path):
    """VPS mal provisionado: `/var/log` sem permissão para o `deploy`.

    Registrar não pode bloquear a recusa — se pudesse, um log quebrado
    faria o script morrer com o código errado (1, do `set -e` na falha de
    escrita) em vez do 2 que a recusa exige, e ninguém saberia diferenciar
    "ordem recusada" de "log quebrado" só olhando o código de saída."""
    log_impossivel = str(tmp_path / "diretorio-que-nao-existe" / "log.txt")
    codigo, chamadas = rodar("rm -rf /", tmp_path, log_path=log_impossivel)
    assert codigo == 2
    assert chamadas == ""


def test_atualizar_completa_mesmo_com_log_ingravavel(tmp_path):
    """O mesmo cenário, na ordem que interessa de verdade: `atualizar` não
    pode falhar por causa de um log que ninguém vai ler naquele momento —
    a atualização em si (pull, up, saúde) é o que importa."""
    log_impossivel = str(tmp_path / "diretorio-que-nao-existe" / "log.txt")
    codigo, chamadas = rodar("atualizar", tmp_path, log_path=log_impossivel)
    assert codigo == 0
    assert "pull" in chamadas and "up -d" in chamadas
