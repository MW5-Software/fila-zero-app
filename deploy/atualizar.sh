#!/bin/bash
# O atualizador do VPS — preso ao authorized_keys (ver a spec do painel).
# Lê $SSH_ORIGINAL_COMMAND e aceita DUAS ordens; qualquer outra coisa é
# recusada e registrada. Nenhuma string de fora entra em comando: o único
# valor variável é o commit de `voltar`, validado por regex de hash.
set -euo pipefail

DIA="${KRONOS_DIR:-/opt/kronos}"
# KRONOS_LOG existe só para o teste redirecionar (o usuário "deploy" no VPS
# não escreve em /var/log sem essa variável apontar para outro lugar); em
# produção nunca é definida, e o log cai onde a spec pede.
LOG="${KRONOS_LOG:-/var/log/kronos-atualizar.log}"
ordem="${SSH_ORIGINAL_COMMAND:-}"

# Registrar NUNCA pode bloquear a ação. Se `$LOG` não for gravável (VPS mal
# provisionada, /var/log sem permissão para o usuário "deploy"), o `>>`
# falharia e o `set -e` derrubaria o script ali mesmo — em TODAS as ordens,
# inclusive na recusa: as 60 instalações responderiam falha a tudo, com um
# motivo que não explica nada, e o painel pintaria vermelho sem ninguém
# achar a causa. Um arquivo de log sem permissão não pode ser o que impede
# uma atualização de acontecer. Por isso o `2>/dev/null || true`: engole
# especificamente o erro de escrita do log, nada mais.
#
# Isto pareceria contradizer a regra de `comum/auditoria.py` — lá,
# corretamente, o registro nunca engole exceção, porque é a ÚNICA memória
# da ação e vive na mesma transação dela. Aqui a trilha que vale é outra:
# o modelo `Acao` do painel (Task 8) grava quem clicou, quando e a saída
# capturada — esse é o registro que não pode se perder. Este arquivo aqui
# é conveniência local, não a fonte da verdade; perder uma linha dele não
# apaga o que aconteceu, só tira um diagnóstico extra do VPS.
registra() { echo "$(date '+%F %T') $*" >> "$LOG" 2>/dev/null || true; }

if [ "$ordem" = "atualizar" ]; then
    registra "atualizar: inicio"
    # DESPINA a tag antes de puxar — mas só a LINHA, nunca o arquivo. `.env`
    # é do operador: é onde ele guarda DJANGO_SECRET_KEY e KRONOS_BANCO, que
    # o compose exige com `${...:?}`. Uma versão anterior deste script fazia
    # `rm -f` no arquivo inteiro para despinar a tag — e apagava junto as
    # credenciais da instalação, derrubando o `up -d` seguinte com "defina
    # DJANGO_SECRET_KEY". NÃO restaure o `rm -f`: o requisito é despinar a
    # tag, não esvaziar o `.env` de outra pessoa. Sem `voltar` ter rodado
    # antes, a linha não existe e o `sed` não muda nada (arquivo ausente
    # também não é erro: não há tag para despinar).
    if [ -f "$DIA/deploy/.env" ]; then
        sed -i '/^KRONOS_TAG=/d' "$DIA/deploy/.env"
    fi
    docker compose -f "$DIA/deploy/docker-compose.vps.yml" pull
    docker compose -f "$DIA/deploy/docker-compose.vps.yml" up -d
elif [[ "$ordem" =~ ^voltar\ ([0-9a-f]{7,40})$ ]]; then
    tag="${BASH_REMATCH[1]}"
    registra "voltar: $tag"
    mkdir -p "$DIA/deploy"
    # Mesma regra: troca a LINHA, preserva o resto do `.env` do operador.
    # Tira uma fixação anterior (se houver) antes de acrescentar a nova, ou
    # dois `voltar` seguidos deixariam duas linhas `KRONOS_TAG` — e o
    # compose lê a última, mas o arquivo mentiria para quem o abrisse.
    touch "$DIA/deploy/.env"
    sed -i '/^KRONOS_TAG=/d' "$DIA/deploy/.env"
    echo "KRONOS_TAG=$tag" >> "$DIA/deploy/.env"
    docker compose -f "$DIA/deploy/docker-compose.vps.yml" pull
    docker compose -f "$DIA/deploy/docker-compose.vps.yml" up -d
else
    registra "RECUSADA: '$ordem'"
    exit 2
fi

# Saúde: o sistema responde? Falha aqui sai não-zero (set -e) e o painel
# vê o vermelho com o motivo.
curl -fsS http://localhost:8000/entrar > /dev/null
registra "ok: saude respondeu"
