# KRONOS base

A base de todo SaaS da MW5: conta, empresa, filial, usuário, cargos e
alocações, permissão, auditoria, aparência, módulos, parâmetros, backup e o
design system (`nucleo`). Não tem módulo de negócio — cada SaaS nasce copiando
esta pasta e acrescentando os dele. Ver `CLAUDE.md` antes de mexer e
`PROVENIENCIA.md` para de onde ela veio.

## Variáveis de ambiente

`config/settings.py` falha fechado de propósito: fora de desenvolvimento
local, esquecer uma variável tem que travar a subida do processo, não
abrir uma brecha silenciosa.

| Variável | Obrigatória | Efeito |
|---|---|---|
| `DJANGO_DEBUG` | Não (padrão `False`) | `"1"` liga `DEBUG=True`. Sem ela, `DEBUG` é `False`. |
| `DJANGO_SECRET_KEY` | **Sim, fora de `DJANGO_DEBUG=1`** | A chave de sessão/assinatura. Sem ela e sem `DJANGO_DEBUG=1`, o settings levanta `ImproperlyConfigured` na hora — não sobe com um valor padrão conhecido. |
| `DJANGO_ALLOWED_HOSTS` | Não | Lista separada por vírgula (`exemplo.com,outro.exemplo.com`). Vazia por padrão. |

Por quê: a imagem é a mesma para mais de 20 VPS. Uma `SECRET_KEY` fixa
commitada, ou um fallback que ninguém percebe que está usando, faria um
cookie de sessão forjado numa instalação valer nas vinte.

### Rodar localmente

Sem banco de dados de produção nem chave real — só desenvolvimento:

```bash
export DJANGO_DEBUG=1
.venv/bin/python manage.py runserver
```

Com `DJANGO_DEBUG=1`, `SECRET_KEY` cai no valor óbvio de desenvolvimento
(`django-insecure-somente-para-desenvolvimento-local`) e o processo sobe
sem mais nada configurado.

### Rodar em produção

`DJANGO_DEBUG` fica de fora (ou `"0"`), e `DJANGO_SECRET_KEY` é
obrigatória — uma chave própria por instalação, nunca reaproveitada entre
VPS.

## Testes

A suíte inteira (pytest + pytest-django) também precisa de uma das duas
variáveis acima, pela mesma razão: o settings é importado no início da
coleta de testes.

```bash
DJANGO_DEBUG=1 .venv/bin/pytest
```

ou, para exercitar o caminho de produção (`DEBUG=False`) com uma chave de
verdade:

```bash
DJANGO_SECRET_KEY="qualquer-coisa-para-este-teste" .venv/bin/pytest
```

`manage.py check`:

```bash
DJANGO_DEBUG=1 .venv/bin/python manage.py check
```

## Rodar em contêiner

A imagem (`Dockerfile`) é a mesma que sobe nas vinte VPS: base
`python:3.13-slim`, dependências instaladas a partir de `pyproject.toml`,
estáticos coletados em build (`collectstatic`), servida por `gunicorn`. O
`docker-compose.yml` sobe dois serviços — `banco` (Postgres) e `app` — nesta
ordem: o `healthcheck` do banco faz o compose só liberar a `app` quando o
Postgres já aceita conexão (`condition: service_healthy`). Isso importa
porque `/tema.css` consulta o banco a cada requisição, e é essa folha que a
tela de login carrega — subir a `app` antes do banco responder derrubaria a
primeira tela que qualquer pessoa vê.

**Nenhuma variável exigida tem valor padrão na imagem.** Um `ENV` com
segredo ficaria gravado em toda camada (`docker history`), e viajaria com a
imagem para qualquer registry. As variáveis exigidas em tempo de execução:

| Variável | Efeito |
|---|---|
| `DJANGO_SECRET_KEY` | Obrigatória. O compose usa `${DJANGO_SECRET_KEY:?defina DJANGO_SECRET_KEY antes de subir}` — sem ela definida no ambiente de quem sobe, o `docker compose up` recusa começar. Uma chave gerada a cada boot deslogaria todo mundo a cada restart, e duas réplicas atrás de um balanceador não reconheceriam a sessão uma da outra. |
| `KRONOS_BANCO` | **Obrigatória, inclusive em desenvolvimento e na suíte.** URL do Postgres desta instalação; no compose já vem apontada para o serviço `banco`. Sem ela o `settings` levanta `ImproperlyConfigured` na hora — não existe mais caminho de SQLite. Ver "Rodar local" abaixo. |
| `PORTAL_CHAVE_DE_CIFRAGEM` | Só para quem cadastra a **conexão do Kronos** numa empresa. A senha do banco do cliente é guardada cifrada (Fernet), e esta é a chave. Sem ela, o cadastro de empresa recusa gravar senha e explica isso na tela — o resto do cadastro funciona igual. **Uma por instalação, nunca a mesma nas sessenta**: a chave commitada seria a mesma em todas, e um dump de qualquer uma abriria o Oracle de todas. Gere com `python -c "from plataforma.cifra import gerar_chave; print(gerar_chave())"`. |
| `DJANGO_ALLOWED_HOSTS` | Hosts aceitos por esta instalação. No compose, `localhost,127.0.0.1` por padrão — troque para o domínio real em produção. |
| `KRONOS_BACKUP_DIR` | Onde o `backupar` grava os dumps. Padrão: `backups/` dentro do projeto. |
| `KRONOS_BACKUP_KEEP` | Quantos backups recentes o `backupar` mantém (poda os mais velhos). Padrão: 30. |
| `KRONOS_MIDIA` | Onde os **arquivos da instalação** moram em disco (`plataforma/midia.py`). Padrão: `midia/` dentro do projeto. **No compose tem de ser um volume**: sem isso, um `docker compose up --build` apaga os arquivos junto com o contêiner. A pasta fica FORA de `static/` de propósito — o arquivo é de uma empresa, e quem o protege é a guarda da rota, não o segredo do nome do arquivo. |

### Rodar local

O banco é **Postgres, sempre** — em desenvolvimento e na suíte também. Havia
um caminho de SQLite quando `KRONOS_BANCO` estava vazio, e ele saiu: o
esquema era o mesmo nos dois, o comportamento não (transação,
`CheckConstraint`, ordenação com acento, `distinct`, tipo de coluna). As
vinte instalações rodam Postgres, e testar noutro banco é provar a coisa
errada. O outro custo apareceu antes: com os dois caminhos vivos, a mesma
instalação tinha DOIS bancos, e `runserver` sem a variável caía no SQLite
sem avisar — cadastrava-se num e olhava-se no outro.

```bash
export DJANGO_SECRET_KEY=qualquer-coisa-local
docker compose up -d banco          # o Postgres, publicado em 127.0.0.1:5435

export DJANGO_DEBUG=1
export KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5435/kronos

uv sync --extra dev
uv run python manage.py migrate
uv run python manage.py runserver
uv run pytest -q
```

A porta é **5435**: a 5432 é de outro projeto desta máquina, a 5433 é do
KRONOS.net e a 5434 é do Portal de Vendas. Apontar para a porta errada abre o
banco de outro produto sem nenhum aviso — e todos têm as MESMAS tabelas da
base, o que torna o engano invisível até alguém gravar no lugar errado. Ela
atende só `127.0.0.1`: o banco responde a quem está na máquina, não à rede.

**Confira a base antes de `migrate`.** O mesmo servidor Postgres pode guardar
bases de produtos diferentes com nomes parecidos. Para saber de que código é
uma base antes de apontar este checkout para ela:

```bash
docker compose exec banco psql -U kronos -d postgres -c "
  select datname from pg_database where datname like 'kronos%';"
docker compose exec banco psql -U kronos -d kronos -c "
  select app, name from django_migrations order by id desc limit 5;"
```

A última migração listada tem de existir em `<app>/migrations/` deste
checkout. Se não existir, a base é de outro código.

### Backup e restauração

O backup é **um arquivo só**: `kronos-<data>.tar.gz`, com o dump do banco
(`banco.dump`) e a pasta de mídia (`midia/`) dentro.

**Um dump sozinho não é o backup.** Avatar e logo são bytes em tabela — são
poucos e pequenos —, mas o arquivo que cresce sem teto mora em disco (no
Portal de Vendas, a foto de produto: chegava a 60 GB dentro do Postgres).
Restaurar só o dump num servidor novo traria o cadastro **sem os arquivos**.
Por isso o `backupar` empacota os dois: um gesto e um
arquivo é o que faz o backup acontecer de verdade, e é o que quem restaura
— meses depois, no pior dia — não tem como esquecer pela metade.

```bash
# backup (dentro do container; grava em KRONOS_BACKUP_DIR, podando por KRONOS_BACKUP_KEEP)
docker compose exec -T app python manage.py backupar

# agendamento no VPS (crontab -e) — todo dia às 3h:
0 3 * * * cd /caminho/do/produto && docker compose exec -T app python manage.py backupar

# restauração — APAGA o estado atual; --confirmar é obrigatório
docker compose exec -T app python manage.py restaurar backups/kronos-2026-09-11-030000.tar.gz --confirmar
```

**Os backups antigos (`.backup`) continuam sendo aceitos**, e o `restaurar`
reconhece qual é qual pelos BYTES, não pela extensão — o nome do arquivo é
escolhido por quem restaura, e restaurar é a operação mais destrutiva daqui.
Ao receber um do formato antigo ele avisa, em vez de deixar a pessoa
descobrir pela tela, que aquele backup não traz arquivo nenhum.

A pasta de mídia anterior não é apagada na restauração: ela vira
`midia.anterior`, para quem precisar voltar.

O dump é local ao VPS de propósito: levar para fora (outro disco, outro
estado) é procedimento de quem opera — credencial de armazém remoto na
imagem seria vinte lugares para vazar. O que o item pede está aqui: o
mecanismo testado (o ciclo backup → destrói → restaura tem teste) e a
poda por retenção.

A `app` roda `migrate` na subida (antes do `gunicorn`), e é isso que aciona
a semeadura dos módulos (`post_migrate`, ver `plataforma/apps.py`): todo
`migrate` — seja instalação nova, seja atualização — semeia desligado
qualquer módulo que o código já declara e o banco ainda não tem.

**Migração de dados parada é o sistema fora do ar**, porque a `app` roda
`migrate && gunicorn`. Toda migração de dados que um SaaS escrever sobre esta
base segue a regra da casa — preenche o que sabe deduzir e para com erro no
que não sabe, listando todos os casos —, e vem com a conferência para rodar
com a versão antiga no ar, aqui neste README. (O Portal de Vendas tem as duas
que vieram antes desta base: a do `conta_guid` e a dos cargos.)

### Subir

```bash
export DJANGO_SECRET_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build
```

### Como conferir que está funcionando

Com o sistema no ar (roteiro de aceite da base — percorra na ordem):

**Preparar**

O usuário da MW5 **nasce com a instalação** (no `post_migrate`, junto com os
módulos e as permissões) — não há `createsuperuser` a rodar. Ele nasce sem
senha utilizável de propósito: a mesma senha padrão nas sessenta instalações
não é senha nenhuma. Quem a define é você, na primeira entrada:

```bash
docker compose exec app python manage.py shell -c "
from contas.models import Usuario
u = Usuario.objects.get(email='mw5@mw5.com.br')
u.set_password('a-senha-que-voce-quiser')
u.is_active = True
u.save()
print('ok:', u.email, u.check_password('a-senha-que-voce-quiser'))"
```

Fora do Docker, o mesmo comando com `.venv/bin/python manage.py shell -c …`.

Três coisas que este comando carrega, e que custam quando faltam:

- **O login é o E-MAIL** (`mw5@mw5.com.br`), não `mw5`. O usuário é o deste
  projeto (`contas.models.Usuario`) desde a troca do `AUTH_USER_MODEL` —
  `django.contrib.auth.models.User` não existe mais como tabela de gente aqui,
  e o comando que ia buscá-lo por `username` levantava `DoesNotExist`.
- **`is_active = True`** não é enfeite: desativar este usuário é exatamente
  como um cliente trancaria a MW5 do lado de dentro, e este comando é como se
  destranca. Ver `contas/mw5.py`.
- **Senha não se recupera**, só se troca: o que está no banco é hash. Perdeu,
  roda de novo.

1. **Entrar como a MW5** (`mw5@mw5.com.br` + a senha de cima).

**Aparência (Bloco 3)**

2. `/mw5/aparencia` — trocar a cor primária e salvar: a tela inteira muda.
3. Ainda na Aparência, mexer em Densidade, Sombras, Tabela listrada e no
   Arredondamento dos controles — **a tela recolore enquanto você digita**
   (prévia ao vivo), e só vira de fato quando salvar.
4. No card "Logos e favicon", enviar um PNG para a Tela de entrada e outro
   para o Menu lateral; salvar; enviar um `.ico` ou PNG pequeno como
   Favicon. O logo aparece na barra lateral na hora, e o favicon na aba.
   Enviar um arquivo que não é imagem tem que ser recusado com frase na
   tela. Remover volta ao texto do nome.

**Módulos, Perfis e Usuários**

5. `/mw5/modulos` — os módulos declarados estão lá, desligados por padrão
   os de negócio. Ligar o Exemplo.
6. `/perfis` — criar um perfil "Consulta" marcando `exemplo: ver`.
7. `/usuarios` — criar uma pessoa ("Ana"), pôr no perfil "Consulta" e marcar
   a filial dela. A senha pode vir **digitada no próprio cadastro**; deixando
   o campo em branco, o sistema gera uma temporária e a mostra na tela —
   **anote**, porque ela não volta a aparecer.
8. Sair, entrar como Ana: vê o Exemplo no menu, **não vê** as telas da MW5,
   e o seletor de filial no cabeçalho mostra a que ela pode.
9. `/perfil` como Ana — trocar a senha e continuar dentro; mandar uma foto
   e ver o avatar mudar no cabeçalho.

**Empresa, Filiais, Parâmetros (como MW5)**

10. `/empresa` — gravar razão social, CNPJ válido (ex.: `04.252.011/0001-10`)
    e CEP. CNPJ com dígito errado é recusado com frase; os campos formatam
    enquanto você digita.
11. `/filiais` — criar uma filial com apelido; desativar a Matriz tem que
    ser recusado (última ativa). Filtrar por Situação, ordenar por coluna.
12. `/parametros` — mudar `itens_por_pagina` para 5 e salvar: as listagens
    paginam a 5 linhas.

**Auditoria, Exportação, Filtros salvos (Bloco 4)**

13. `/auditoria` — tudo o que você fez acima está lá, mais recente primeiro,
    com rótulo legível ("Usuário criado", não `usuario_criado`). Filtrar
    por ação na caixa, por autor, pelo período.
14. Com um filtro aplicado, clicar **Excel**: a planilha sai com as MESMAS
    linhas filtradas. Clicar **Imprimir**: abre a página de papel e o
    diálogo de impressão (salvar em PDF sai daí).
15. Salvar o filtro corrente com um nome ("Zeca"); a faixa "Filtros salvos"
    guarda o atalho; clicar nele reaplica tudo. Estrela marca favorito;
    × remove. Outro usuário não vê os seus.
16. Entrar como MW5, `/usuarios`, personificar a Ana: o aviso fica em toda
    tela, o menu é o dela, e cada início/fim cai na auditoria.

**Caminho de atualização**

17. Declare um módulo novo no código (copie `modulos/exemplo/` trocando
    chave, rótulo e rota), rode `docker compose exec app python manage.py
    migrate` e `restart app` — o módulo novo tem que aparecer em
    `/mw5/modulos`, desligado, sem migração manual nenhuma.

## Painel de versões (repositório `kronos-painel`)

Um painel separado (Django, VPS próprio da MW5) mostra quais instalações
do KRONOS.net estão desatualizadas e permite atualizar (ou voltar) cada
uma com um clique, por SSH — sem depender de acesso manual a cada VPS.
Metade das peças desse fluxo mora aqui, neste repositório:

- `GET /versao` (`nucleo/views.py`) — rota aberta que devolve
  `{"commit": "<sha ou 'desenvolvimento'>"}`, lido do arquivo `VERSAO`
  gravado em tempo de build. É o que o painel consulta em cada
  instalação para saber o que está rodando.
- `Dockerfile` — recebe `--build-arg GIT_SHA=<sha>` e grava `VERSAO`
  dentro da imagem.
- `deploy/docker-compose.vps.yml` — o compose que roda nos VPS das
  instalações: só baixa a imagem do GHCR (nunca compila), lendo a tag
  de `KRONOS_TAG` (padrão `latest`) — é o que faz "voltar uma versão"
  ser o mesmo fluxo de sempre, só fixando a tag anterior.
- `deploy/atualizar.sh` — o script preso no `authorized_keys` de cada
  VPS: aceita só duas ordens (`atualizar`, `voltar <commit>`), nunca
  texto livre. Registra em `/var/log/kronos-atualizar.log` (essa
  gravação nunca bloqueia a atualização — ver o README do painel para o
  porquê e a pegadinha de diagnóstico que isso implica).
- `.github/workflows/imagem.yml` — a cada push na `main`, constrói a
  imagem uma vez e publica no GHCR (`ghcr.io/mw5-software/kronosnet`),
  com o commit e `latest` como tags.

**O roteiro completo de provisionamento e o roteiro de aceite** (cadastrar
uma instalação no painel, colar a chave, instalar este script, pinar a
identidade do VPS, atualizar, quebrar de propósito, voltar, conferir a
trilha) estão no `README.md` do repositório `kronos-painel` — leia-o
antes de colocar uma instalação nova no ar, porque metade dos passos
(o lado do painel) não tem como ficar documentada aqui.

**O que ainda não foi provado contra a coisa real** (nada disso impede o
uso, mas é honesto registrar): o workflow acima nunca rodou de verdade —
ninguém confirmou que ele constrói, que o GHCR aceita o push, ou que o
compose do VPS consegue puxar a imagem publicada; e as versões das
actions usadas (`checkout@v4`, `login-action@v3`, `build-push-action@v6`)
não foram conferidas contra o upstream. Ambos entram no primeiro push de
verdade na `main`.

## Estrutura

- `nucleo/` — o app do design system: componentes (`nucleo/components/`),
  layout de shell (`nucleo/layout.py`, `nucleo/templates/layout/`), tema
  (`nucleo/theme/`), permissões (`nucleo/permissoes.py`).
- `config/` — settings, urls, wsgi/asgi da matriz Django.
- `docs/superpowers/` — plano e especificação desta entrega.
- `.superpowers/sdd/` — registro de execução (briefs, relatórios, decisões
  do controlador). Não versionado; ver `docs/superpowers/` para o que foi
  transcrito de lá.
