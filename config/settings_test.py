"""Settings de TESTE — nunca de produção.

`manage.py` e `config/wsgi.py` (o que o `Dockerfile`/`docker-compose.yml`
sobem em produção) apontam os dois, à mão, para `config.settings` — nunca
para este módulo. Só `pyproject.toml` (`[tool.pytest.ini_options]`) aponta
para cá, e só quando a suíte roda. Trocar `DJANGO_SETTINGS_MODULE` fora do
`pytest`, ou apontar produção para este arquivo por engano, reintroduziria o
próprio problema que ele existe para evitar (ver abaixo) fora do lugar onde
isso é seguro.

Medido, não estimado: os 838 testes da suíte levam 331s com o hasher de
senha de produção (PBKDF2, Django 5.2, 1.000.000 de iterações) e 18,4s com o
hasher rápido abaixo — 94,5% do tempo da suíte inteira é custo de hashing,
multiplicado por todo `create_user(password=...)`, `authenticate` e
`set_password` que a entrega usa. Nenhuma fixture patológica: só o custo do
algoritmo de produção, correto e caro de propósito, rodando um milhão de
vezes a mais do que qualquer teste precisa para provar o que testa.

**Isto não muda como senha nenhuma é verificada em produção.** Este arquivo
só é lido pelo `pytest` (`DJANGO_SETTINGS_MODULE` em `pyproject.toml`); o
`Dockerfile`, o `docker-compose.yml`, `manage.py` e `config/wsgi.py` — os
quatro lugares que decidem o que sobe numa instalação de verdade — nunca o
importam, direta ou indiretamente. Nenhum teste desta suíte afirma nada
sobre QUAL algoritmo está em uso (não há um só `assert` sobre
`PASSWORD_HASHERS`, o nome do hasher, ou o formato do hash gravado) — a
troca não tira força de teste nenhum, só tempo de parede.
"""

import os

# **A suíte é desenvolvimento**, e sem dizer nada ela roda em DEBUG. Sem esta
# linha, `pytest` sem `DJANGO_DEBUG=1` exportado dava cerca de 540 falhas, todas
# 301 para HTTPS: fora de DEBUG, `config.settings` liga o redirecionamento e
# os cookies seguros, e o `Client` de teste fala HTTP. `setdefault`, e não
# atribuição: quem exporta `DJANGO_DEBUG=0` para provar o caminho de produção
# continua podendo. Antes do `import` abaixo, porque é lá que a variável é
# lida.
os.environ.setdefault("DJANGO_DEBUG", "1")

from .settings import *  # noqa: E402,F401,F403

#: `MD5PasswordHasher`, não `PBKDF2PasswordHasher` (o de produção, o
#: `AUTH_PASSWORD_HASHERS[0]` padrão do Django): é o hasher rápido que a
#: própria documentação do Django recomenda para teste — inseguro de
#: propósito (sem iteração nenhuma), e é exatamente por ser inseguro que
#: nunca pode aparecer fora deste arquivo.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# O app de mentira que prova a trava do inquilino
# (`tests/app_do_inquilino/`). Só aqui, nunca em `config/settings.py`: é
# código de teste, e um model de teste no catálogo de produção viraria uma
# tabela vazia em toda instalação.
INSTALLED_APPS = [*INSTALLED_APPS, "tests.app_do_inquilino"]  # noqa: F405
