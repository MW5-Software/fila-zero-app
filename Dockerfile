# Imagem única do KRONOS.net, distribuída para mais de 20 VPS. Cada
# instalação define as variáveis abaixo por fora (compose, `.env` do host, ou
# o painel do orquestrador) — NENHUMA delas tem valor padrão nesta imagem, e
# nenhuma entra como `ENV`: `docker history` mostra o valor de todo `ENV` de
# toda camada, e uma imagem que segue para um registry levaria o segredo
# junto. As mesmas 20 instalações reaproveitariam a mesma chave se ela
# viajasse com a imagem — o que a spec proíbe (ver `config/settings.py`).
#
# Variáveis exigidas em tempo de execução (não em build):
#   DJANGO_SECRET_KEY     — chave de sessão/assinatura, própria por instalação.
#   KRONOS_BANCO           — URL do Postgres desta instalação.
#   DJANGO_ALLOWED_HOSTS   — hosts aceitos por esta instalação.
#
# `DJANGO_DEBUG` não é exigida: sem ela, o padrão já é `DEBUG=False` (falha
# fechado, ver `config/settings.py`).

FROM python:3.13-slim

# O cliente do Postgres: o `backupar`/`restaurar` (Bloco 7) chama pg_dump/
# pg_restore — sem este pacote, o backup da instalação nasceria quebrado
# (foi assim que o defeito apareceu: o comando só falha na hora de rodar).
# `--no-install-recommends` para não arrastar o servidor junto.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Saída sem buffer: os logs do gunicorn aparecem em ordem no `docker logs`,
# em vez de ficarem presos no buffer do processo até ele encerrar.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# O RG da imagem (ver /versao): o Actions passa o commit em --build-arg;
# sem ele (build local), o valor óbvio de desenvolvimento.
ARG GIT_SHA=desenvolvimento
RUN echo "$GIT_SHA" > /app/VERSAO

# Dependências antes do código: uma camada só muda quando o `pyproject.toml`
# muda, não a cada alteração de código — reconstrução mais rápida.
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY . .

# `collectstatic` roda em build, não em subida: é conteúdo do design system
# versionado no código, não algo que dependa de banco ou de segredo — ao
# contrário de `/tema.css`, que é gerado por requisição (ver README).
# `DJANGO_SECRET_KEY` não existe neste estágio; qualquer variável exigida em
# tempo de execução só precisa estar presente quando o processo sobe, e
# `collectstatic` não lê o banco nem a chave de sessão.
#
# **A URL abaixo é de mentira, e é de propósito.** `config/settings.py` falha
# fechado sem `KRONOS_BANCO` — decisão tomada depois que uma instalação subiu
# apontando para o SQLite sem ninguém perceber, e ela não se afrouxa por
# causa do build. Só que `collectstatic` importa o settings inteiro antes de
# copiar o primeiro arquivo, e aí a construção da imagem parava aqui:
#
#     django.core.exceptions.ImproperlyConfigured: KRONOS_BANCO é obrigatória
#
# Uma URL sintática, sem servidor do outro lado, satisfaz o import sem abrir
# conexão nenhuma — `collectstatic` não consulta o banco. Ela vale só nesta
# linha, não vira `ENV`: gravada na imagem, seria o padrão silencioso que a
# falha fechada existe para impedir.
RUN DJANGO_DEBUG=1 \
    KRONOS_BANCO=postgresql://build:build@127.0.0.1:5432/build \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
