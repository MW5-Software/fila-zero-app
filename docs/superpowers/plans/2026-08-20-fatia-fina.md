# Fatia Fina do KRONOS.net — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma passada estreita pelas entregas 2, 3 e 4 — login funcionando, banco, telas de Módulos e Aparência, um módulo de exemplo, menu montado sozinho, e a imagem Docker — para que o KRONOS.net rode de ponta a ponta e se configure sem editar código.

**Architecture:** Dois apps Django novos sobre o `nucleo` já portado. `contas/` implementa o contrato `AuthBackend` (`autenticar`/`buscar`) contra a base do Django e produz objetos `nucleo.permissoes.User`. `plataforma/` guarda a identidade da instalação: a tabela `marca` (que monta um `Brand` pelo construtor já validado) e a tabela `modulo` (o interruptor por cliente, semeada por migração a partir do que o código declara). O menu nasce do cruzamento de módulos ligados com as permissões do usuário.

**Tech Stack:** Python 3.13, Django 5.2 LTS, Jinja2, pytest + pytest-django, SQLite local, PostgreSQL em contêiner, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-20-kronos-net-matriz-design.md`

**Entrega anterior:** `docs/superpowers/plans/2026-08-20-nucleo-visual.md` (concluída — 556 testes). As decisões tomadas nela estão em `docs/superpowers/decisoes-2026-08-20-nucleo-visual.md` e **valem aqui também**.

## O que esta entrega dá, em uma frase

No fim, você sobe `docker compose up`, **entra com usuário e senha**, vê o menu com o módulo ligado; desliga ele na tela de Módulos e ele some; troca a cor na tela de Aparência e o sistema inteiro muda — **sem editar uma linha de código.**

## O que esta entrega deliberadamente NÃO dá

Auditoria, personificação, troca da própria senha, empresa/filial, autenticação pelo Oracle do cliente, painel central de versões da MW5, e o rollout nas VPS. Cada um engorda depois. **Ninguém vai subir nada em servidor nenhum nesta entrega** — a imagem é construída e testada localmente.

## Global Constraints

- **`nucleo/` é um porte literal e não se mexe.** Cada arquivo dele difere da origem (`/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin/`) só nos pontos autorizados, e isso é verificável por `diff`. Se uma tarefa parecer exigir mudança em `nucleo/`, **pare e escale** — provavelmente há outro caminho, e se não houver, a divergência precisa de autorização registrada.
- **Nenhuma cor, fonte ou caminho de logo em `.py` ou `.html`** fora de `nucleo/theme/`. Nem em template novo, nem em view, nem em model. Cor vem da tabela `marca`.
- **Nenhum CSS escrito à mão.** Tela nova se monta com os componentes de `nucleo.components`. Se faltar um componente, **escale** — não improvise `<style>`.
- **O settings falha fechado.** `DEBUG` só liga com `DJANGO_DEBUG=1`; `SECRET_KEY` é obrigatória fora de `DEBUG`. Não afrouxe isso para tirar fricção — `tests/test_projeto.py` trava a regra.
- **Rodar a suíte exige `DJANGO_DEBUG=1`:** `DJANGO_DEBUG=1 .venv/bin/pytest`.
- **Estado de partida:** 556 testes passando, 0 failed, 0 xfailed, 0 skipped, 0 warnings. **Preserve isso.** Nenhum `xfail` novo, nenhum skip silencioso.
- **Idioma:** código, comentários, docstrings, nomes de teste e mensagens de commit em português.
- **Commits:** um por tarefa, formato `tipo: descrição`. **Nunca `git commit --amend`.**
- **Esconder não é proteger.** Item fora do menu não é controle de acesso: a rota verifica módulo ligado e permissão de novo, sempre.

## Estrutura de arquivos ao fim da entrega

```
kronos-net/
├─ config/settings.py           + apps de auth, sessão, mensagens; DATABASES por ambiente
├─ contas/
│  ├─ models.py                 (vazio — usa o User do Django)
│  ├─ backend.py                BackendDjango: autenticar() e buscar()
│  ├─ sessao.py                 põe e tira o usuário da sessão
│  ├─ guardas.py                exigir_login, exigir_permissao
│  ├─ views.py                  entrar, sair
│  └─ urls.py
├─ plataforma/
│  ├─ models.py                 Marca, Modulo
│  ├─ declaracao.py             ModuloSpec, registrar(), declarados()
│  ├─ catalogo.py               modulos_ligados(), semear()
│  ├─ menu.py                   monta os NavItem a partir de módulos × permissão
│  ├─ marca.py                  Marca -> Brand
│  ├─ views.py                  tela de Módulos, tela de Aparência
│  ├─ urls.py
│  └─ migrations/
├─ modulos/
│  └─ exemplo/                  o módulo que prova o mecanismo
│     ├─ modulo.py              a declaração
│     ├─ views.py
│     └─ urls.py
├─ Dockerfile
├─ docker-compose.yml
└─ tests/
```

**Por que `contas/` não define um model de usuário:** o Django já tem `auth_user`, `auth_group` e `auth_permission`, com hash de senha feito certo. O `contas/` traduz isso para o retrato pobre que o `nucleo` consome (`nucleo.permissoes.User`). Criar um usuário próprio seria reescrever o que já existe e perder o hash.

---

### Task 1: Banco, apps de autenticação e o middleware de volta

**Files:**
- Modify: `config/settings.py`
- Create: `contas/__init__.py`, `contas/apps.py`, `contas/models.py`
- Create: `plataforma/__init__.py`, `plataforma/apps.py`
- Test: `tests/test_banco.py`

**Interfaces:**
- Consumes: nada.
- Produces: os apps `contas` e `plataforma` registrados; `django.contrib.auth`, `sessions`, `messages`, `contenttypes` e `staticfiles` instalados; `DATABASES` resolvido por ambiente (`KRONOS_BANCO`); `SessionMiddleware`, `AuthenticationMiddleware` e `MessageMiddleware` no `MIDDLEWARE`, junto dos que já estão.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_banco.py`:

```python
"""O banco da instalação existe e traz o que a autenticação precisa.

Um teste de fundação: se ele falha, nada mais desta entrega roda, e o erro
aparece aqui em vez de disfarçado três tarefas adiante.
"""

import pytest
from django.conf import settings


def test_os_apps_de_autenticacao_estao_instalados():
    for app in ("django.contrib.auth", "django.contrib.sessions",
                "django.contrib.contenttypes", "django.contrib.messages"):
        assert app in settings.INSTALLED_APPS


def test_os_apps_do_kronos_estao_instalados():
    assert "contas" in settings.INSTALLED_APPS
    assert "plataforma" in settings.INSTALLED_APPS


def test_o_middleware_de_sessao_e_de_autenticacao_esta_no_lugar():
    assert "django.contrib.sessions.middleware.SessionMiddleware" in settings.MIDDLEWARE
    assert "django.contrib.auth.middleware.AuthenticationMiddleware" in settings.MIDDLEWARE


def test_o_csrf_continua_ligado():
    """A entrega 1 achou o CsrfViewMiddleware removido por engano. Não volta a sair."""
    assert "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE
    assert "django.middleware.clickjacking.XFrameOptionsMiddleware" in settings.MIDDLEWARE


@pytest.mark.django_db
def test_o_usuario_do_django_grava_e_le():
    from django.contrib.auth.models import User

    User.objects.create_user(username="ana", password="segredo-de-teste")
    assert User.objects.filter(username="ana").exists()


@pytest.mark.django_db
def test_a_senha_nao_fica_em_texto_puro():
    """O Perform ON guarda senha em texto puro. Aqui isso não acontece nem por acidente."""
    from django.contrib.auth.models import User

    u = User.objects.create_user(username="bruno", password="segredo-de-teste")
    assert u.password != "segredo-de-teste"
    assert u.check_password("segredo-de-teste")
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_banco.py -v`
Esperado: FAIL — `django.contrib.auth` não está em `INSTALLED_APPS`.

- [ ] **Step 3: Criar os dois apps**

```bash
mkdir -p contas plataforma
touch contas/__init__.py plataforma/__init__.py
```

Criar `contas/apps.py`:

```python
from django.apps import AppConfig


class ContasConfig(AppConfig):
    """Login, sessão e a tradução do usuário do Django para o do núcleo.

    Não define model de usuário: o `auth_user` do Django já existe, já guarda
    a senha em hash, e reescrevê-lo seria perder isso.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "contas"
```

Criar `contas/models.py` vazio, com um comentário dizendo por que está vazio:

```python
"""Sem model próprio, de propósito — ver a docstring de `ContasConfig`."""
```

Criar `plataforma/apps.py`:

```python
from django.apps import AppConfig


class PlataformaConfig(AppConfig):
    """A identidade desta instalação: a marca e quais módulos estão ligados.

    É a parte "controlado por banco de dados" da spec: o código diz quais
    módulos existem, e as linhas daqui dizem quais estão ligados para este
    cliente.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "plataforma"
```

- [ ] **Step 4: Ajustar o `settings.py`**

Substituir `INSTALLED_APPS` por:

```python
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "nucleo",
    "contas",
    "plataforma",
]
```

Substituir `MIDDLEWARE` por:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

Substituir o bloco `DATABASES` por:

```python
# O banco de cada cliente. Local é SQLite, para não exigir serviço de pé
# em quem só quer rodar a suíte; em contêiner e em produção é Postgres, e
# `KRONOS_BANCO` traz a URL. O esquema é o mesmo nos dois — é isso que faz
# uma migração valer igual nas vinte instalações.
_BANCO = os.environ.get("KRONOS_BANCO", "")
if _BANCO:
    DATABASES = {"default": dj_database_url.parse(_BANCO, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "kronos.sqlite3",
        }
    }
```

Acrescentar no topo, junto dos outros imports: `import dj_database_url`.

Instalar a dependência e registrá-la:

```bash
.venv/bin/pip install "dj-database-url>=2.2"
```

Em `pyproject.toml`, acrescentar `"dj-database-url>=2.2"` à lista `dependencies`.

- [ ] **Step 5: Rodar e verificar que passa**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_banco.py -v`
Esperado: PASS, 6 testes.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest -q`
Esperado: 562 passed (556 + 6), 0 failed, 0 xfailed, 0 skipped, 0 warnings.

Se algum teste da entrega 1 quebrar, **pare e reporte qual** — instalar apps de auth não deveria afetar nenhum deles, e se afetou, é achado.

- [ ] **Step 7: Commit**

```bash
git add config/settings.py contas plataforma pyproject.toml tests/test_banco.py
git commit -m "feat: banco da instalacao e os apps de autenticacao do Django

O contas/ nao define model de usuario: o auth_user do Django ja guarda a
senha em hash, e reescreve-lo seria perder isso."
```

---

### Task 2: `contas/backend.py` — o usuário do Django vira usuário do núcleo

**Files:**
- Create: `contas/backend.py`
- Test: `tests/test_contas_backend.py`

**Interfaces:**
- Consumes: `nucleo.permissoes.User` (dataclass frozen: `id`, `name`, `login`, `role_label`, `avatar`, `superuser`, `permissions: frozenset[str]`), Task 1.
- Produces:
  - `contas.backend.BackendDjango` — implementa o contrato `AuthBackend` da origem:
    - `autenticar(login: str, senha: str) -> nucleo.permissoes.User | None`
    - `buscar(user_id: str) -> nucleo.permissoes.User | None`
  - `contas.backend.permissoes_de(usuario_django) -> frozenset[str]` — traduz grupos e permissões do Django para o formato `modulo.acao`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_contas_backend.py`:

```python
"""A tradução entre o usuário do Django e o usuário que o núcleo desenha.

O `nucleo.permissoes.User` é de propósito um retrato pobre: só o que a tela
precisa. É o que permite trocar a origem da gente — base do Django hoje,
Oracle do cliente amanhã — sem que nada acima perceba.
"""

import pytest
from django.contrib.auth.models import Group, Permission, User as UsuarioDjango

from contas.backend import BackendDjango, permissoes_de
from nucleo.permissoes import User, pode


@pytest.fixture
def backend():
    return BackendDjango()


@pytest.fixture
def ana(db):
    return UsuarioDjango.objects.create_user(
        username="ana", password="segredo-de-teste",
        first_name="Ana", last_name="Paula Souza",
    )


class TestAutenticar:
    def test_login_certo_devolve_o_usuario_do_nucleo(self, backend, ana):
        u = backend.autenticar("ana", "segredo-de-teste")
        assert isinstance(u, User)
        assert u.login == "ana"
        assert u.name == "Ana Paula Souza"

    def test_senha_errada_devolve_nada(self, backend, ana):
        assert backend.autenticar("ana", "errada") is None

    def test_login_inexistente_devolve_nada(self, backend, db):
        assert backend.autenticar("ninguem", "seja-la") is None

    def test_usuario_inativo_nao_entra(self, backend, ana):
        """Desativar alguém tem que valer na hora, não no próximo deploy."""
        ana.is_active = False
        ana.save()
        assert backend.autenticar("ana", "segredo-de-teste") is None

    def test_login_inexistente_e_senha_errada_nao_se_distinguem(self, backend, ana):
        """Quem chama não pode descobrir quais logins existem."""
        assert backend.autenticar("ana", "errada") is None
        assert backend.autenticar("ninguem", "errada") is None


class TestBuscar:
    def test_reconstroi_a_sessao_sem_senha(self, backend, ana):
        u = backend.buscar(str(ana.pk))
        assert u is not None and u.login == "ana"

    def test_usuario_desativado_some(self, backend, ana):
        ana.is_active = False
        ana.save()
        assert backend.buscar(str(ana.pk)) is None

    def test_id_que_nao_existe_devolve_nada(self, backend, db):
        assert backend.buscar("999999") is None

    def test_id_que_nao_e_numero_nao_derruba(self, backend, db):
        """Cookie adulterado não pode virar erro 500."""
        assert backend.buscar("nao-e-numero") is None


class TestPermissoes:
    def test_sem_grupo_nenhum_nao_pode_nada(self, backend, ana):
        u = backend.autenticar("ana", "segredo-de-teste")
        assert pode(u, "exemplo.ver") is False

    def test_permissao_de_modulo_ganha_o_ponto(self, backend, ana, db):
        """O Django não aceita ponto em codename, então a permissão de módulo
        se escreve `frete_ver` no banco e vira `frete.ver` aqui."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from plataforma.models import Modulo

        tipo = ContentType.objects.get_for_model(Modulo)
        ana.user_permissions.add(Permission.objects.create(
            codename="frete_ver", name="ver frete", content_type=tipo))

        assert "frete.ver" in permissoes_de(ana)

    def test_permissao_de_outro_app_passa_como_esta(self, backend, ana, db):
        """`auth.add_user` não é permissão de módulo. Traduzi-la produziria
        `add.user`, um nome que não existe em lugar nenhum."""
        ana.user_permissions.add(
            Permission.objects.get(codename="add_user"))

        traduzidas = permissoes_de(ana)
        assert "auth.add_user" in traduzidas
        assert "add.user" not in traduzidas

    def test_o_nome_do_grupo_vira_permissao_coringa(self, backend, ana, db):
        """Um grupo chamado `frete` dá `frete.*` — é assim que um perfil se diz
        por módulo, e não ação por ação."""
        ana.groups.add(Group.objects.create(name="frete"))
        assert "frete.*" in permissoes_de(ana)

    def test_superusuario_passa_em_tudo(self, backend, db):
        raiz = UsuarioDjango.objects.create_superuser(
            username="mw5", password="segredo-de-teste"
        )
        u = BackendDjango().buscar(str(raiz.pk))
        assert u.superuser is True
        assert pode(u, "qualquer.coisa") is True


class TestONome:
    def test_sem_nome_proprio_cai_no_login(self, backend, db):
        UsuarioDjango.objects.create_user(username="sonome", password="segredo-de-teste")
        u = backend.autenticar("sonome", "segredo-de-teste")
        assert u.name == "sonome"
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_contas_backend.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'contas.backend'`.

- [ ] **Step 3: Escrever `contas/backend.py`**

```python
"""Traduz o usuário do Django para o retrato que o núcleo desenha.

Implementa o contrato `AuthBackend` que o `mw5_admin` já definia — dois
métodos, `autenticar` e `buscar` — e é isto que permite trocar a origem da
gente sem que nada acima perceba. Hoje é a base do Django; a entrega que
ligar o Oracle do cliente escreve outro backend e mais nada muda.
"""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.models import User as UsuarioDjango

from nucleo.permissoes import User

__all__ = ["APP_DOS_MODULOS", "BackendDjango", "permissoes_de"]

#: O app onde moram as permissões de módulo. Só as deste app ganham a
#: tradução `modulo_acao` -> `modulo.acao`; as dos outros passam como estão.
APP_DOS_MODULOS = "plataforma"


def permissoes_de(usuario: UsuarioDjango) -> frozenset[str]:
    """As permissões da pessoa, no formato `modulo.acao` que o núcleo entende.

    Duas origens, e a segunda é a que importa no dia a dia:

    - as permissões do Django (`app_label.codename`), uma a uma;
    - **o nome de cada grupo vira o coringa daquele módulo** (`frete` →
      `frete.*`). É assim que um perfil se diz por módulo em vez de ação por
      ação — e é o que faz a ação criada amanhã já estar contida em quem tem
      o módulo inteiro, sem reabrir perfil em vinte instalações.
    """
    concedidas: set[str] = set()
    for permissao in usuario.get_all_permissions():
        app, _, codename = permissao.partition(".")
        if app == APP_DOS_MODULOS and "_" in codename:
            # `plataforma.frete_ver` -> `frete.ver`. O Django não aceita ponto
            # em codename, então a permissão de módulo se escreve com
            # sublinhado no banco e ganha o ponto aqui.
            modulo, _, acao = codename.partition("_")
            concedidas.add(f"{modulo}.{acao}")
        else:
            # Permissão de outro app passa como está. Ela não é permissão de
            # módulo, e traduzi-la produziria nomes que não existem.
            concedidas.add(permissao)

    coringas = {f"{grupo.name}.*" for grupo in usuario.groups.all()}
    return frozenset(concedidas | coringas)


def _para_o_nucleo(usuario: UsuarioDjango) -> User:
    nome = usuario.get_full_name().strip() or usuario.username
    return User(
        id=str(usuario.pk),
        name=nome,
        login=usuario.username,
        superuser=usuario.is_superuser,
        permissions=permissoes_de(usuario),
    )


class BackendDjango:
    """A gente desta instalação, vinda da base do próprio sistema."""

    def autenticar(self, login: str, senha: str) -> "User | None":
        """`None` para login inexistente, senha errada e usuário inativo — sem
        distinguir os três. Quem chama não pode descobrir quais logins existem.
        """
        usuario = authenticate(username=login, password=senha)
        if usuario is None or not usuario.is_active:
            return None
        return _para_o_nucleo(usuario)

    def buscar(self, user_id: str) -> "User | None":
        """Reconstrói a sessão a cada requisição, sem senha.

        É o que faz desativar alguém valer na hora. `None` derruba a sessão.
        """
        try:
            usuario = UsuarioDjango.objects.get(pk=int(user_id), is_active=True)
        except (UsuarioDjango.DoesNotExist, ValueError, TypeError):
            return None
        return _para_o_nucleo(usuario)
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_contas_backend.py -v`
Esperado: PASS, 14 testes.

- [ ] **Step 5: Rodar a suíte inteira e commitar**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest -q`

```bash
git add contas/backend.py tests/test_contas_backend.py
git commit -m "feat: o usuario do Django vira o usuario do nucleo

O nome do grupo vira o coringa do modulo: um grupo `frete` da `frete.*`.
E assim que um perfil se diz por modulo, e nao acao por acao."
```

---

### Task 3: Login, sessão e sair

**Files:**
- Create: `contas/sessao.py`, `contas/views.py`, `contas/urls.py`
- Modify: `config/urls.py`
- Test: `tests/test_login.py`

**Interfaces:**
- Consumes: `contas.backend.BackendDjango` (Task 2); `nucleo.layout.LoginPage` (dataclass: `brand: Brand`, `fields: Renderable`, `action: str = "/entrar"`, `error: str | None`, `theme_href: str`, `stylesheets: list[str]`, com o método `campos_da_marca()`); `nucleo.resposta.render`.
- Produces:
  - `contas.sessao.entrar_na_sessao(request, user: nucleo.permissoes.User) -> None`
  - `contas.sessao.sair_da_sessao(request) -> None`
  - `contas.sessao.usuario_da_sessao(request) -> nucleo.permissoes.User | None`
  - rotas nomeadas `entrar` (`/entrar`, GET e POST) e `sair` (`/sair`, POST)

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_login.py`:

```python
"""Entrar, ficar dentro, e sair.

A tela de login já existe como componente desde a entrega 1 (`LoginPage`).
O que esta tarefa acrescenta é a rota, a sessão e a saída.
"""

import pytest
from django.contrib.auth.models import User as UsuarioDjango
from django.test import Client
from django.urls import reverse


@pytest.fixture
def ana(db):
    return UsuarioDjango.objects.create_user(
        username="ana", password="segredo-de-teste", first_name="Ana",
    )


class TestATelaDeLogin:
    def test_a_tela_abre_para_quem_nao_entrou(self, db):
        resposta = Client().get(reverse("entrar"))
        assert resposta.status_code == 200

    def test_a_tela_traz_o_formulario_e_o_token_csrf(self, db):
        html = Client().get(reverse("entrar")).content.decode()
        assert "<form" in html
        assert "csrfmiddlewaretoken" in html

    def test_a_tela_carrega_a_folha_de_tema(self, db):
        html = Client().get(reverse("entrar")).content.decode()
        assert "/tema.css" in html

    def test_a_tela_de_login_nao_desenha_o_shell(self, db):
        """Login é a única tela sem barra lateral, cabeçalho e rodapé."""
        html = Client().get(reverse("entrar")).content.decode()
        assert "<aside" not in html
        assert "<footer" not in html


class TestEntrar:
    def test_credencial_certa_entra_e_redireciona(self, ana):
        c = Client()
        resposta = c.post(reverse("entrar"),
                          {"login": "ana", "senha": "segredo-de-teste"})
        assert resposta.status_code == 302
        assert resposta["Location"] == "/"

    def test_a_sessao_guarda_quem_entrou(self, ana):
        c = Client()
        c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
        assert c.session.get("usuario_id") == str(ana.pk)

    def test_senha_errada_nao_entra_e_avisa(self, ana):
        c = Client()
        resposta = c.post(reverse("entrar"), {"login": "ana", "senha": "errada"})
        assert resposta.status_code == 200
        assert "usuario_id" not in c.session
        assert "inválidas" in resposta.content.decode()

    def test_o_aviso_nao_diz_qual_dos_dois_errou(self, ana):
        """A mesma resposta para login inexistente e senha errada."""
        c = Client()
        um = c.post(reverse("entrar"), {"login": "ana", "senha": "errada"})
        outro = c.post(reverse("entrar"), {"login": "ninguem", "senha": "errada"})
        assert um.content == outro.content

    def test_a_senha_nao_volta_no_html(self, ana):
        """Senha errada não pode ser redesenhada dentro do formulário."""
        html = Client().post(
            reverse("entrar"), {"login": "ana", "senha": "minha-senha-secreta"}
        ).content.decode()
        assert "minha-senha-secreta" not in html


class TestSair:
    def test_sair_esvazia_a_sessao(self, ana):
        c = Client()
        c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
        resposta = c.post(reverse("sair"))
        assert resposta.status_code == 302
        assert "usuario_id" not in c.session

    def test_sair_por_get_nao_funciona(self, ana):
        """Sair é ação: um `<img src="/sair">` numa página qualquer não pode
        derrubar a sessão de quem abriu."""
        c = Client()
        c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
        resposta = c.get(reverse("sair"))
        assert resposta.status_code == 405
        assert c.session.get("usuario_id") == str(ana.pk)


class TestOUsuarioDaSessao:
    def test_devolve_quem_entrou(self, ana):
        from contas.sessao import usuario_da_sessao

        c = Client()
        c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
        pedido = c.get(reverse("entrar")).wsgi_request
        assert usuario_da_sessao(pedido).login == "ana"

    def test_devolve_nada_para_quem_nao_entrou(self, db):
        from contas.sessao import usuario_da_sessao

        pedido = Client().get(reverse("entrar")).wsgi_request
        assert usuario_da_sessao(pedido) is None

    def test_desativar_alguem_derruba_a_sessao_aberta(self, ana):
        """`buscar` roda a cada requisição, e é isso que faz valer na hora."""
        from contas.sessao import usuario_da_sessao

        c = Client()
        c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
        ana.is_active = False
        ana.save()
        pedido = c.get(reverse("entrar")).wsgi_request
        assert usuario_da_sessao(pedido) is None
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_login.py -v`
Esperado: FAIL — `NoReverseMatch: Reverse for 'entrar' not found`.

- [ ] **Step 3: Escrever `contas/sessao.py`**

```python
"""Quem está na sessão, e como entra e sai dela.

A sessão guarda **só o id**. O usuário é reconstruído a cada requisição pelo
`buscar` do backend — é isso que faz desativar alguém valer na hora, e não no
próximo login.
"""

from __future__ import annotations

from nucleo.permissoes import User

from .backend import BackendDjango

__all__ = ["entrar_na_sessao", "sair_da_sessao", "usuario_da_sessao"]

CHAVE = "usuario_id"


def entrar_na_sessao(request, user: User) -> None:
    """Grava quem entrou e gira o identificador da sessão.

    O `cycle_key` fecha a fixação de sessão: um identificador obtido antes do
    login deixa de valer no instante em que a pessoa entra.
    """
    request.session.cycle_key()
    request.session[CHAVE] = user.id


def sair_da_sessao(request) -> None:
    request.session.flush()


def usuario_da_sessao(request, backend=None) -> "User | None":
    """Quem está nesta requisição, ou `None`."""
    user_id = request.session.get(CHAVE)
    if not user_id:
        return None
    return (backend or BackendDjango()).buscar(user_id)
```

- [ ] **Step 4: Escrever `contas/views.py`**

```python
"""As duas telas de porta: entrar e sair."""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.urls import reverse

from nucleo.layout import LoginPage
from nucleo.rendering import create_environment, use_environment
from nucleo.resposta import render

from .backend import BackendDjango
from .sessao import entrar_na_sessao, sair_da_sessao

__all__ = ["entrar", "sair"]

#: A mesma frase para login inexistente, senha errada e usuário inativo.
#: Distinguir os três entrega a lista de quem existe a quem estiver tentando.
CREDENCIAIS_INVALIDAS = "Credenciais inválidas."


def _desenhar(request, marca, erro: "str | None" = None) -> HttpResponse:
    env = create_environment()
    with use_environment(env):
        pagina = LoginPage(
            brand=marca,
            action=reverse("entrar"),
            error=erro,
            theme_href="/tema.css",
        )
        return render(pagina, status=200 if erro is None else 200)


def entrar(request) -> HttpResponse:
    from plataforma.marca import marca_da_instalacao

    marca = marca_da_instalacao()
    if request.method != "POST":
        return _desenhar(request, marca)

    user = BackendDjango().autenticar(
        request.POST.get("login", ""), request.POST.get("senha", "")
    )
    if user is None:
        return _desenhar(request, marca, erro=CREDENCIAIS_INVALIDAS)

    entrar_na_sessao(request, user)
    return HttpResponseRedirect("/")


def sair(request) -> HttpResponse:
    """Só por POST: um `<img src="/sair">` numa página qualquer não pode
    derrubar a sessão de quem a abriu."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    sair_da_sessao(request)
    return HttpResponseRedirect(reverse("entrar"))
```

**Atenção:** `LoginPage` monta os campos a partir da marca (`campos_da_marca()`). O template precisa do token CSRF. Confira `nucleo/templates/layout/login.html` — se ele **não** emitir `{{ csrf_input }}` ou equivalente, **pare e escale**: mexer no template seria alterar conteúdo portado, e a saída certa é passar o token pelos `fields` da `LoginPage`, não editar `nucleo/`.

- [ ] **Step 5: Escrever `contas/urls.py` e ligar ao projeto**

`contas/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("entrar", views.entrar, name="entrar"),
    path("sair", views.sair, name="sair"),
]
```

Em `config/urls.py`, acrescentar antes do `include("nucleo.urls")`:

```python
    path("", include("contas.urls")),
```

- [ ] **Step 6: Rodar e verificar que passa**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_login.py -v`
Esperado: PASS, 14 testes (a contagem dos metodos declarados no Step 1).

- [ ] **Step 7: Rodar a suíte inteira e commitar**

```bash
git add contas/sessao.py contas/views.py contas/urls.py config/urls.py tests/test_login.py
git commit -m "feat: entrar, ficar dentro e sair

A sessao guarda so o id; o usuario e reconstruido a cada requisicao, e e
isso que faz desativar alguem valer na hora."
```

---

### Task 4: A guarda — nenhuma tela nasce aberta

**Files:**
- Create: `contas/guardas.py`
- Modify: `nucleo/views.py` (a view `demonstracao` passa a exigir login)
- Test: `tests/test_guarda.py`

**Interfaces:**
- Consumes: `contas.sessao.usuario_da_sessao` (Task 3).
- Produces:
  - `contas.guardas.exigir_login(view)` — decorator; sem sessão, redireciona para `entrar`
  - `contas.guardas.exigir_permissao(nome: str)` — decorator com argumento; sem a permissão, responde 404
  - `contas.guardas.TELAS_ABERTAS: frozenset[str]` — os nomes de rota que podem ficar sem guarda (`entrar`, `tema`)

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_guarda.py`:

```python
"""Nenhuma tela nasce aberta.

O teste que mais importa aqui é o último: ele percorre TODAS as rotas do
sistema e exige que cada uma esteja protegida. Uma tela nova sem guarda vira
teste vermelho antes de virar porta aberta — que é o contrário de descobrir
pelo telefone.
"""

import pytest
from django.contrib.auth.models import Group, User as UsuarioDjango
from django.test import Client
from django.urls import get_resolver, reverse


@pytest.fixture
def ana(db):
    return UsuarioDjango.objects.create_user(username="ana", password="segredo-de-teste")


@pytest.fixture
def logada(ana):
    c = Client()
    c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
    return c


class TestExigirLogin:
    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get("/")
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_quem_entrou_passa(self, logada):
        assert logada.get("/").status_code == 200

    def test_a_tela_de_login_nao_exige_login(self, db):
        assert Client().get(reverse("entrar")).status_code == 200

    def test_a_folha_de_tema_nao_exige_login(self, db):
        """A tela de login precisa dela antes de qualquer sessão existir."""
        assert Client().get(reverse("tema")).status_code == 200


class TestExigirPermissao:
    def test_sem_a_permissao_a_rota_responde_como_inexistente(self, db, ana):
        """404 e não 403: quem não pode não descobre que a tela existe."""
        from contas.guardas import exigir_permissao
        from django.http import HttpResponse
        from django.test import RequestFactory
        from contas.sessao import CHAVE

        @exigir_permissao("frete.ver")
        def tela(request):
            return HttpResponse("segredo")

        pedido = RequestFactory().get("/frete")
        pedido.session = {CHAVE: str(ana.pk)}
        assert tela(pedido).status_code == 404

    def test_com_a_permissao_passa(self, db, ana):
        from contas.guardas import exigir_permissao
        from django.http import HttpResponse
        from django.test import RequestFactory
        from contas.sessao import CHAVE

        ana.groups.add(Group.objects.create(name="frete"))

        @exigir_permissao("frete.ver")
        def tela(request):
            return HttpResponse("segredo")

        pedido = RequestFactory().get("/frete")
        pedido.session = {CHAVE: str(ana.pk)}
        assert tela(pedido).status_code == 200


class TestNenhumaTelaNasceAberta:
    """A rede que pega a tela nova que alguém esqueceu de proteger."""

    def test_toda_rota_exige_login_ou_esta_declarada_aberta(self):
        from contas.guardas import TELAS_ABERTAS

        desprotegidas = []
        for chave, (_, _, nome) in get_resolver().reverse_dict.items():
            if not isinstance(chave, str):
                continue
            if chave in TELAS_ABERTAS:
                continue
            view = _view_de(chave)
            if view is not None and not getattr(view, "exige_login", False):
                desprotegidas.append(chave)

        assert not desprotegidas, (
            f"rotas sem guarda: {desprotegidas}. Ou decore a view com "
            f"@exigir_login, ou declare em TELAS_ABERTAS dizendo por quê."
        )


def _view_de(nome: str):
    """A função por trás de um nome de rota."""
    from django.urls import resolve

    try:
        return resolve(reverse(nome)).func
    except Exception:
        return None
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_guarda.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'contas.guardas'`.

- [ ] **Step 3: Escrever `contas/guardas.py`**

```python
"""As guardas de rota.

Esconder um item do menu **não** é controle de acesso: quem digitar o
endereço na barra do navegador tem que bater numa porta trancada. Estas duas
guardas são essa porta, e o teste de varredura em `tests/test_guarda.py` é o
que impede alguém de criar uma tela e esquecer de pô-la.
"""

from __future__ import annotations

from functools import wraps

from django.http import Http404, HttpResponseRedirect
from django.urls import reverse

from nucleo.permissoes import pode

from .sessao import usuario_da_sessao

__all__ = ["TELAS_ABERTAS", "exigir_login", "exigir_permissao"]

#: As rotas que podem viver sem guarda, e o motivo de cada uma. Uma lista
#: curta e explícita: qualquer nome que entre aqui devia doer um pouco.
TELAS_ABERTAS = frozenset({
    "entrar",  # a porta
    "tema",    # a folha que a própria tela de login precisa carregar
})


def exigir_login(view):
    """Sem sessão, vai para a tela de entrada."""

    @wraps(view)
    def guardada(request, *args, **kwargs):
        user = usuario_da_sessao(request)
        if user is None:
            return HttpResponseRedirect(reverse("entrar"))
        request.usuario = user
        return view(request, *args, **kwargs)

    guardada.exige_login = True
    return guardada


def exigir_permissao(nome: str):
    """Sem a permissão, a rota responde como se não existisse.

    404 e não 403, de propósito: quem não pode não precisa descobrir que a
    tela existe.
    """

    def decorar(view):
        @wraps(view)
        def guardada(request, *args, **kwargs):
            user = usuario_da_sessao(request)
            if user is None:
                return HttpResponseRedirect(reverse("entrar"))
            if not pode(user, nome):
                raise Http404
            request.usuario = user
            return view(request, *args, **kwargs)

        guardada.exige_login = True
        guardada.permissao = nome
        return guardada

    return decorar
```

- [ ] **Step 4: Proteger a tela de demonstração**

Em `nucleo/views.py`, decorar a view `demonstracao` com `@exigir_login`.

**Isto é uma alteração em `nucleo/`, que é porte literal.** É autorizada e o motivo precisa ficar no código: `demonstracao` é view autoral desta base (não veio do `mw5_admin`), criada na entrega 1. Acrescente o import e o decorator, e um comentário curto dizendo que a view é autoral e por isso pode ser tocada.

Se, ao abrir o arquivo, a view `demonstracao` **não** for autoral ou houver dúvida, **pare e escale**.

- [ ] **Step 5: Rodar e verificar que passa**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_guarda.py -v`
Esperado: PASS, 7 testes.

**Atenção:** vários testes da entrega 1 batem em `/` sem sessão e esperavam 200. Eles vão quebrar — e é o comportamento certo. Ajuste `tests/test_demonstracao.py` para entrar antes de pedir a página, com uma fixture. **Não** afrouxe a guarda para os testes passarem; **não** declare `demonstracao` em `TELAS_ABERTAS`.

- [ ] **Step 6: Rodar a suíte inteira e commitar**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest -q`
Esperado: verde, sem `xfail` novo.

```bash
git add contas/guardas.py nucleo/views.py tests/
git commit -m "feat: nenhuma tela nasce aberta

A varredura de rotas exige guarda em toda view: tela nova sem protecao vira
teste vermelho antes de virar porta aberta."
```

---

### Task 5: A marca vem do banco

**Files:**
- Create: `plataforma/models.py`, `plataforma/marca.py`, `plataforma/migrations/__init__.py`
- Modify: `nucleo/views.py` (a `MARCA` fixa dá lugar à do banco)
- Test: `tests/test_marca.py`

**Interfaces:**
- Consumes: `nucleo.theme.Brand` e `Brand.from_dict(data: dict) -> Brand` (valida cor e recusa campo desconhecido).
- Produces:
  - `plataforma.models.Marca` — model com uma linha por instalação
  - `plataforma.marca.marca_da_instalacao() -> nucleo.theme.Brand` — a marca corrente, ou o padrão da MW5 se a tabela estiver vazia
  - `plataforma.models.Marca.para_brand(self) -> nucleo.theme.Brand`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_marca.py`:

```python
"""A marca sai do arquivo e vai para o banco.

Arquivo se troca com implantação; banco se troca por tela. Mudar uma frase da
tela de login não pode exigir publicar versão nova em vinte instalações.
"""

import pytest

from nucleo.theme import Brand


@pytest.mark.django_db
class TestAMarcaDaInstalacao:
    def test_sem_linha_no_banco_vem_o_padrao_da_mw5(self):
        from plataforma.marca import marca_da_instalacao

        marca = marca_da_instalacao()
        assert isinstance(marca, Brand)
        assert marca.client_name == "KRONOS.net"

    def test_a_linha_do_banco_vence_o_padrao(self):
        from plataforma.marca import marca_da_instalacao
        from plataforma.models import Marca

        Marca.objects.create(client_name="Sementes Premix", primary="#276b2e")
        marca = marca_da_instalacao()
        assert marca.client_name == "Sementes Premix"
        assert marca.primary == "#276b2e"

    def test_a_cor_primaria_deriva_a_paleta(self):
        """A tabela guarda uma cor; as outras trinta saem dela."""
        from plataforma.models import Marca

        tokens = Marca(client_name="X", primary="#276b2e").para_brand().tokens("light")
        assert tokens["primary"] == "#276b2e"
        assert "surface" in tokens and "on-surface" in tokens

    def test_cor_invalida_e_recusada_na_montagem(self):
        """`Brand` já valida cor. A tabela não reimplementa isso."""
        from plataforma.models import Marca

        with pytest.raises(ValueError):
            Marca(client_name="X", primary="nao-e-cor").para_brand()

    def test_as_cores_de_area_chegam_ao_brand(self):
        from plataforma.models import Marca

        marca = Marca(client_name="X", sidebar_bg="#276b2e",
                      sidebar_text="#ffffff").para_brand()
        assert marca.areas.sidebar_bg == "#276b2e"

    def test_campo_vazio_nao_vira_cor_vazia(self):
        """Campo em branco herda do tema; não vira `''` num token.

        O padrão de `AreaColors` é `None` (verificado no código), e é o `None`
        que faz o token cair no valor derivado da paleta. Passar `""` produziria
        `--sidebar-bg:;` no CSS — borda que some, texto invisível.
        """
        from plataforma.models import Marca

        marca = Marca(client_name="X").para_brand()
        assert marca.areas.sidebar_bg is None
        tokens = marca.tokens("light")
        assert all(v for v in tokens.values()), "algum token saiu vazio"


@pytest.mark.django_db
def test_a_folha_de_tema_usa_a_marca_do_banco(client):
    from plataforma.models import Marca

    Marca.objects.create(client_name="Sementes Premix", primary="#276b2e")
    css = client.get("/tema.css").content.decode()
    assert "#276b2e" in css or "276b2e" in css
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_marca.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'plataforma.models'`.

- [ ] **Step 3: Escrever `plataforma/models.py`**

```python
"""A identidade desta instalação, em banco.

Uma linha de `Marca` por instalação. Os nomes das colunas são os mesmos
campos do `brand.yaml` da entrega 1 — de propósito: `Brand.from_dict` já sabe
ler essa forma, já valida cor e já recusa campo desconhecido. A tabela não
reimplementa nada disso.
"""

from __future__ import annotations

from django.db import models

from nucleo.theme import Brand

__all__ = ["Marca"]


class Marca(models.Model):
    """A cara desta instalação. Só a MW5 edita."""

    client_name = models.CharField("nome do cliente", max_length=120)
    system_name = models.CharField("nome do sistema", max_length=120, blank=True)

    primary = models.CharField("cor primária", max_length=9, default="#1e40af")
    accent = models.CharField("cor de destaque", max_length=9, default="#872d00")

    radius = models.CharField("arredondamento", max_length=8, default="12px")
    density = models.CharField("densidade", max_length=16, default="normal")
    sidebar_width = models.CharField("largura do menu", max_length=8, default="256px")
    shadows = models.BooleanField("sombras", default=True)
    zebra = models.BooleanField("tabela listrada", default=False)

    # As cores por área. Em branco significa "herda do tema" — que é como
    # quase tudo fica. O Sementes Premix, por exemplo, tem a primária azul e
    # o menu verde, e é só isto que ele preenche.
    sidebar_bg = models.CharField("fundo do menu", max_length=9, blank=True)
    sidebar_text = models.CharField("texto do menu", max_length=9, blank=True)
    header_bg = models.CharField("fundo do cabeçalho", max_length=9, blank=True)
    header_text = models.CharField("texto do cabeçalho", max_length=9, blank=True)
    content_bg = models.CharField("fundo do conteúdo", max_length=9, blank=True)
    footer_bg = models.CharField("fundo do rodapé", max_length=9, blank=True)
    footer_text = models.CharField("texto do rodapé", max_length=9, blank=True)

    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "marca"
        verbose_name_plural = "marcas"

    def __str__(self) -> str:
        return self.client_name

    #: Os campos de cor por área, na ordem em que a tela os mostra.
    AREAS = (
        "sidebar_bg", "sidebar_text", "header_bg", "header_text",
        "content_bg", "footer_bg", "footer_text",
    )

    def para_brand(self) -> Brand:
        """Monta o `Brand` que o design system consome.

        Campo em branco é **omitido** do dicionário, e não passado como `""`:
        o `Brand` tem o próprio padrão para cada um, e mandar string vazia
        viraria um token vazio no CSS — borda que some, texto invisível.
        """
        dados: dict = {
            "client_name": self.client_name,
            "primary": self.primary,
            "accent": self.accent,
            "radius": self.radius,
            "density": self.density,
            "sidebar_width": self.sidebar_width,
            "shadows": self.shadows,
            "zebra": self.zebra,
        }
        if self.system_name:
            dados["system_name"] = self.system_name

        areas = {campo: getattr(self, campo) for campo in self.AREAS
                 if getattr(self, campo)}
        if areas:
            dados["areas"] = areas

        return Brand.from_dict(dados)
```

- [ ] **Step 4: Escrever `plataforma/marca.py`**

```python
"""Qual marca está valendo nesta instalação."""

from __future__ import annotations

from nucleo.theme import Brand

__all__ = ["MARCA_PADRAO", "marca_da_instalacao"]

#: A cara com que uma instalação nova nasce. Nada quebrado, nada em branco —
#: a MW5 troca pela do cliente na tela de Aparência.
MARCA_PADRAO = Brand(client_name="KRONOS.net", system_name="KRONOS.net")


def marca_da_instalacao() -> Brand:
    """A marca gravada, ou o padrão da MW5 se ninguém configurou ainda."""
    from .models import Marca

    linha = Marca.objects.first()
    return linha.para_brand() if linha else MARCA_PADRAO
```

- [ ] **Step 5: Ligar a folha de tema ao banco**

Em `nucleo/views.py`, a `MARCA` fixa e o `SITE` global dão lugar à marca do banco. A view `tema_css` passa a chamar `marca_da_instalacao()`.

**É alteração em `nucleo/`.** Autorizada: `views.py` é autoral desta base, não veio do `mw5_admin`, e o próprio comentário do arquivo já diz que o `SITE` é provisório e some quando a marca vier do banco — que é agora. Atualize o comentário para refletir o que passou a valer.

- [ ] **Step 6: Gerar a migração e rodar**

```bash
mkdir -p plataforma/migrations && touch plataforma/migrations/__init__.py
DJANGO_DEBUG=1 .venv/bin/python manage.py makemigrations plataforma
DJANGO_DEBUG=1 .venv/bin/pytest tests/test_marca.py -v
```

Esperado: PASS, 7 testes.

- [ ] **Step 7: Rodar a suíte inteira e commitar**

```bash
git add plataforma tests/test_marca.py nucleo/views.py
git commit -m "feat: a marca sai do arquivo e vai para o banco

Arquivo se troca com implantacao; banco se troca por tela. A tabela guarda a
mesma forma do brand.yaml, e Brand.from_dict continua sendo quem valida."
```

---

### Task 6: A tela de Aparência

**Files:**
- Create: `plataforma/views.py`, `plataforma/urls.py`
- Modify: `config/urls.py`
- Test: `tests/test_tela_aparencia.py`

**Interfaces:**
- Consumes: `plataforma.models.Marca` (Task 5); `contas.guardas.exigir_permissao` (Task 4); componentes de `nucleo.components` (`Card`, `Form`, `FormGrid`, `TextInput`, `Select`, `Checkbox`, `Button`, `PageHeader`, `Alert`).
- Produces: rota nomeada `aparencia` (`/mw5/aparencia`, GET e POST), exigindo a permissão `mw5.aparencia`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_tela_aparencia.py`:

```python
"""A tela onde a MW5 troca a cara de uma instalação.

O teste que fecha a promessa da entrega é o último: mudar a cor aqui muda o
sistema inteiro, sem tocar em código.
"""

import pytest
from django.contrib.auth.models import Group, User as UsuarioDjango
from django.test import Client
from django.urls import reverse


@pytest.fixture
def cliente_mw5(db):
    u = UsuarioDjango.objects.create_user(username="mw5", password="segredo-de-teste")
    u.groups.add(Group.objects.create(name="mw5"))
    c = Client()
    c.post(reverse("entrar"), {"login": "mw5", "senha": "segredo-de-teste"})
    return c


@pytest.fixture
def cliente_comum(db):
    UsuarioDjango.objects.create_user(username="ana", password="segredo-de-teste")
    c = Client()
    c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
    return c


class TestQuemEntra:
    def test_a_mw5_abre_a_tela(self, cliente_mw5):
        assert cliente_mw5.get(reverse("aparencia")).status_code == 200

    def test_o_admin_do_cliente_nao_ve_a_tela(self, cliente_comum):
        """Aparência é só da MW5. 404: quem não pode não descobre que existe."""
        assert cliente_comum.get(reverse("aparencia")).status_code == 404

    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("aparencia"))
        assert resposta.status_code == 302


class TestATela:
    def test_desenha_os_campos_da_marca(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert "Nome do cliente" in html
        assert "Cor primária" in html

    def test_traz_o_token_csrf(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert "csrfmiddlewaretoken" in html

    def test_mostra_os_valores_que_estao_valendo(self, cliente_mw5):
        from plataforma.models import Marca

        Marca.objects.create(client_name="Sementes Premix", primary="#276b2e")
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert "Sementes Premix" in html
        assert "#276b2e" in html


class TestSalvar:
    def test_salvar_grava_no_banco(self, cliente_mw5):
        from plataforma.models import Marca

        cliente_mw5.post(reverse("aparencia"), {
            "client_name": "Sementes Premix", "primary": "#276b2e",
            "accent": "#872d00", "radius": "12px", "density": "normal",
            "sidebar_width": "256px",
        })
        assert Marca.objects.get().client_name == "Sementes Premix"

    def test_salvar_duas_vezes_nao_cria_duas_linhas(self, cliente_mw5):
        """Uma instalação, uma marca."""
        from plataforma.models import Marca

        for nome in ("Um", "Dois"):
            cliente_mw5.post(reverse("aparencia"), {
                "client_name": nome, "primary": "#1e40af", "accent": "#872d00",
                "radius": "12px", "density": "normal", "sidebar_width": "256px",
            })
        assert Marca.objects.count() == 1

    def test_cor_invalida_nao_grava_e_avisa(self, cliente_mw5):
        from plataforma.models import Marca

        resposta = cliente_mw5.post(reverse("aparencia"), {
            "client_name": "X", "primary": "nao-e-cor", "accent": "#872d00",
            "radius": "12px", "density": "normal", "sidebar_width": "256px",
        })
        assert resposta.status_code == 200
        assert Marca.objects.count() == 0
        assert "cor" in resposta.content.decode().lower()

    def test_cor_ilegivel_e_recusada(self, cliente_mw5):
        """Amarelo claríssimo de fundo de menu com texto branco não passa —
        a pessoa descobre na hora, não depois de salvar."""
        from plataforma.models import Marca

        resposta = cliente_mw5.post(reverse("aparencia"), {
            "client_name": "X", "primary": "#1e40af", "accent": "#872d00",
            "radius": "12px", "density": "normal", "sidebar_width": "256px",
            "sidebar_bg": "#fffde7", "sidebar_text": "#ffffff",
        })
        assert resposta.status_code == 200
        assert Marca.objects.count() == 0
        assert "leg" in resposta.content.decode().lower()


@pytest.mark.django_db
def test_trocar_a_cor_muda_o_sistema_inteiro(cliente_mw5):
    """A promessa da entrega, num teste só."""
    antes = cliente_mw5.get(reverse("tema")).content.decode()
    cliente_mw5.post(reverse("aparencia"), {
        "client_name": "Sementes Premix", "primary": "#276b2e",
        "accent": "#872d00", "radius": "12px", "density": "normal",
        "sidebar_width": "256px",
    })
    depois = cliente_mw5.get(reverse("tema")).content.decode()
    assert antes != depois
    assert "276b2e" in depois
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_tela_aparencia.py -v`
Esperado: FAIL — `NoReverseMatch: Reverse for 'aparencia' not found`.

- [ ] **Step 3: Escrever a validação de contraste**

Em `plataforma/marca.py`, acrescentar:

```python
#: O mínimo da WCAG AA para texto normal. Abaixo disso a pessoa não lê.
CONTRASTE_MINIMO = 4.5


def conferir_legibilidade(fundo: str, texto: str) -> "str | None":
    """A frase de recusa, ou `None` se o par é legível.

    Recusar na hora da escolha, e não depois de salvar: quem escolhe amarelo
    claro de fundo com texto branco descobre no momento, não quando o cliente
    liga dizendo que não enxerga o menu.
    """
    from nucleo.theme import contrast_ratio

    if not fundo or not texto:
        return None
    razao = contrast_ratio(fundo, texto)
    if razao >= CONTRASTE_MINIMO:
        return None
    return (
        f"O texto não fica legível sobre esse fundo "
        f"(contraste {razao:.1f}, o mínimo é {CONTRASTE_MINIMO})."
    )
```

- [ ] **Step 4: Escrever `plataforma/views.py`**

A view monta o formulário com os componentes do design system — **nenhum HTML escrito à mão, nenhum CSS**. Estrutura:

```python
"""As telas que só a MW5 vê: Aparência e Módulos."""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from contas.guardas import exigir_permissao
from nucleo.components import (
    Alert, Button, Card, Checkbox, Form, FormGrid, PageHeader, TextInput,
)
from nucleo.rendering import create_environment, use_environment
from nucleo.resposta import render

from .marca import conferir_legibilidade, marca_da_instalacao
from .models import Marca

__all__ = ["aparencia"]

#: Os campos que a tela edita, na ordem em que aparecem: nome do campo no
#: model, rótulo, e quantas colunas ocupa na grade.
CAMPOS = (
    ("client_name", "Nome do cliente", 6),
    ("system_name", "Nome do sistema", 6),
    ("primary", "Cor primária", 3),
    ("accent", "Cor de destaque", 3),
    ("radius", "Arredondamento", 3),
    ("sidebar_width", "Largura do menu", 3),
    ("sidebar_bg", "Fundo do menu", 3),
    ("sidebar_text", "Texto do menu", 3),
    ("header_bg", "Fundo do cabeçalho", 3),
    ("header_text", "Texto do cabeçalho", 3),
    ("content_bg", "Fundo do conteúdo", 3),
    ("footer_bg", "Fundo do rodapé", 3),
    ("footer_text", "Texto do rodapé", 3),
)

#: Pares fundo/texto que precisam ser legíveis um sobre o outro.
PARES_DE_CONTRASTE = (
    ("sidebar_bg", "sidebar_text", "menu"),
    ("header_bg", "header_text", "cabeçalho"),
    ("footer_bg", "footer_text", "rodapé"),
)
```

O corpo da view: em `GET`, carrega a linha (ou uma `Marca()` em branco) e desenha; em `POST`, valida cor por `Brand.from_dict` (que já levanta `ValueError`), valida contraste pelos `PARES_DE_CONTRASTE`, e grava com `Marca.objects.update_or_create(pk=linha.pk if linha else None, defaults=...)` — ou apaga e cria, desde que sobre **uma linha só**.

A montagem da página usa `Site.page(...)` com o `Site` da instalação, dentro de `with use_environment(env)`, e o `return render(...)` **dentro** do `with` — a entrega 1 achou esse defeito e ele não deve voltar.

- [ ] **Step 5: Escrever `plataforma/urls.py` e ligar**

```python
from django.urls import path

from . import views

urlpatterns = [
    path("mw5/aparencia", views.aparencia, name="aparencia"),
]
```

Em `config/urls.py`, acrescentar `path("", include("plataforma.urls")),`.

- [ ] **Step 6: Rodar, ver a tela, commitar**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_tela_aparencia.py -v`
Esperado: PASS, 11 testes.

Suba o servidor, entre como um usuário do grupo `mw5`, abra `/mw5/aparencia`, **troque a cor primária, salve, e confira que a tela inteira mudou**. Se não mudar, pare e reporte.

```bash
git add plataforma tests/test_tela_aparencia.py config/urls.py
git commit -m "feat: a tela de Aparencia

Cor ilegivel e recusada na hora da escolha: quem poe texto branco em fundo
claro descobre no momento, e nao quando o cliente liga dizendo que nao le."
```

---

### Task 7: O catálogo de módulos — o código declara, o banco liga

**Files:**
- Create: `plataforma/declaracao.py`, `plataforma/catalogo.py`
- Modify: `plataforma/models.py` (acrescenta `Modulo`)
- Create: `plataforma/migrations/0002_semear_modulos.py`
- Test: `tests/test_catalogo_de_modulos.py`

**Interfaces:**
- Consumes: Task 5.
- Produces:
  - `plataforma.declaracao.ModuloSpec` — dataclass frozen: `chave: str`, `rotulo: str`, `icone: str`, `grupo: str`, `rota: str`, `permissoes: tuple[str, ...]`
  - `plataforma.declaracao.registrar(spec: ModuloSpec) -> None`
  - `plataforma.declaracao.declarados() -> tuple[ModuloSpec, ...]`
  - `plataforma.models.Modulo` — colunas `chave` (única), `ativo` (bool, padrão `False`), `rotulo` (override, em branco = usa o do código), `grupo` (override), `ordem` (int)
  - `plataforma.catalogo.semear(apps=None) -> int` — cria a linha faltante de cada módulo declarado, **desligada**; devolve quantas criou
  - `plataforma.catalogo.modulos_ligados() -> tuple[ModuloSpec, ...]`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_catalogo_de_modulos.py`:

```python
"""O código diz quais módulos existem; o banco diz quais estão ligados.

Esta é a peça central da spec. Sem ela, um módulo novo custa vinte
intervenções manuais — e é exatamente esse custo que o KRONOS.net existe para
eliminar.
"""

import pytest

from plataforma.declaracao import ModuloSpec, declarados, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    yield
    declaracao._DECLARADOS.clear()
    declaracao._DECLARADOS.update(guardado)


ESPECIE = ModuloSpec(
    chave="frete", rotulo="Frete", icone="truck", grupo="Consultas",
    rota="/frete", permissoes=("frete.ver", "frete.editar"),
)


class TestADeclaracao:
    def test_um_modulo_declarado_aparece(self, catalogo_limpo):
        registrar(ESPECIE)
        assert ESPECIE in declarados()

    def test_declarar_a_mesma_chave_duas_vezes_e_erro(self, catalogo_limpo):
        """Duas pastas com a mesma chave dariam menu duplicado e permissão
        ambígua. Melhor quebrar na subida."""
        registrar(ESPECIE)
        with pytest.raises(ValueError):
            registrar(ESPECIE)

    def test_a_declaracao_e_imutavel(self, catalogo_limpo):
        with pytest.raises(Exception):
            ESPECIE.rotulo = "outro"


@pytest.mark.django_db
class TestASemeadura:
    def test_o_modulo_novo_nasce_desligado(self, catalogo_limpo):
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        assert semear() == 1
        assert Modulo.objects.get(chave="frete").ativo is False

    def test_semear_duas_vezes_nao_duplica(self, catalogo_limpo):
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        assert semear() == 0
        assert Modulo.objects.filter(chave="frete").count() == 1

    def test_semear_nao_desliga_o_que_ja_estava_ligado(self, catalogo_limpo):
        """A atualização que traz o módulo novo não pode apagar a escolha que
        a MW5 já tinha feito nos outros."""
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)
        semear()
        assert Modulo.objects.get(chave="frete").ativo is True


@pytest.mark.django_db
class TestOsLigados:
    def test_so_vem_o_que_esta_ligado(self, catalogo_limpo):
        from plataforma.catalogo import modulos_ligados, semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        assert modulos_ligados() == ()

        Modulo.objects.filter(chave="frete").update(ativo=True)
        assert [m.chave for m in modulos_ligados()] == ["frete"]

    def test_linha_no_banco_sem_declaracao_no_codigo_e_ignorada(self, catalogo_limpo):
        """Um módulo removido do código deixa a linha para trás. Ela não pode
        virar item de menu apontando para rota que não existe."""
        from plataforma.catalogo import modulos_ligados
        from plataforma.models import Modulo

        Modulo.objects.create(chave="fantasma", ativo=True)
        assert modulos_ligados() == ()

    def test_desligar_nao_apaga_dado(self, catalogo_limpo):
        """Desligar some da tela; não apaga registro. Apagar dado de cliente
        numa chavinha seria caro demais."""
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        registrar(ESPECIE)
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)
        Modulo.objects.filter(chave="frete").update(ativo=False)
        assert Modulo.objects.filter(chave="frete").exists()
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_catalogo_de_modulos.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'plataforma.declaracao'`.

- [ ] **Step 3 (obrigacao herdada da Task 2): endurecer o coringa de grupo contra o catalogo**

A Task 2 deixou um risco residual aceito e documentado: `contas.backend.permissoes_de` cria o coringa `X.*` a partir de **qualquer** nome de grupo, sem conferir se `X` e um modulo de verdade. Hoje isso e inerte — coringa que nao cobre pergunta nenhuma —, e so agora, com `declarados()` existindo, da para fechar.

Duas coisas nesta tarefa, e as duas sao obrigatorias:

**(a) Restringir o coringa aos modulos declarados.** Em `contas/backend.py`, o conjunto de coringas passa a conter so os grupos cujo nome bate com uma chave de modulo declarada. Import tardio dentro da funcao, para nao criar dependencia de ordem de carga entre os apps.

```python
    from plataforma.declaracao import declarados

    chaves = {spec.chave for spec in declarados()}
    coringas = {f"{grupo.name}.*" for grupo in usuario.groups.all()
                if grupo.name in chaves}
```

O teste `test_o_coringa_sai_do_nome_do_grupo_sem_conferir_o_catalogo`, escrito na Task 2, **fixa o comportamento antigo e vai ficar vermelho**. Isso e esperado e desejado: ele existe para que esta mudanca seja deliberada. Substitua-o por um par que afirme a regra nova — grupo com nome de modulo declarado gera coringa; grupo com nome qualquer nao gera.

**(b) As permissoes que o Django gera sozinho.** Ao criar o model `Modulo`, o Django gera `add_modulo`, `change_modulo`, `delete_modulo` e `view_modulo` no app `plataforma` — todas com sublinhado, entao a traducao atual as transformaria em `add.modulo`, `change.modulo` e por ai. Nomes sem sentido no vocabulario do nucleo.

Escreva um teste que prove isso e trate: as permissoes autogeradas do proprio app da plataforma nao devem virar permissao de modulo. O criterio e o nome do modelo, nao uma lista fixa — uma lista envelhece quando a proxima tabela nascer.

- [ ] **Step 4: Escrever `plataforma/declaracao.py`**

```python
"""O que um módulo diz sobre si.

Um módulo **declara**; ele não registra rota, não escreve menu e não cria
permissão. Quem faz isso é a plataforma, lendo esta declaração. É o que faz
um módulo novo aparecer sozinho nas vinte instalações.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["ModuloSpec", "declarados", "registrar"]


@dataclass(frozen=True)
class ModuloSpec:
    """A apresentação de um módulo, em português claro.

    "Eu sou o Frete. Meu ícone é o caminhão. Eu moro no grupo Consultas. Minha
    rota é /frete. Eu crio as permissões frete.ver e frete.editar."
    """

    chave: str
    rotulo: str
    icone: str = ""
    grupo: str = "Geral"
    rota: str = ""
    permissoes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.chave.strip():
            raise ValueError("módulo sem chave")
        if not self.rotulo.strip():
            raise ValueError(f"módulo {self.chave!r} sem rótulo")


#: O que o código declarou. Preenchido quando cada `modulo.py` é importado.
_DECLARADOS: dict[str, ModuloSpec] = {}


def registrar(spec: ModuloSpec) -> None:
    """Põe um módulo no catálogo do código.

    Chave repetida quebra na subida, de propósito: duas pastas com a mesma
    chave dariam item de menu duplicado e permissão ambígua, e descobrir isso
    em produção é bem pior.
    """
    if spec.chave in _DECLARADOS:
        raise ValueError(f"o módulo {spec.chave!r} já foi declarado")
    _DECLARADOS[spec.chave] = spec


def declarados() -> tuple[ModuloSpec, ...]:
    """Todos os módulos que existem no código, em ordem de chave."""
    return tuple(_DECLARADOS[c] for c in sorted(_DECLARADOS))
```

- [ ] **Step 4: Acrescentar o model `Modulo`**

Em `plataforma/models.py`:

```python
class Modulo(models.Model):
    """O interruptor de um módulo nesta instalação.

    A linha nasce **desligada** e é criada pela migração, a partir do que o
    código declara. É o que impede um módulo novo de custar vinte
    intervenções manuais.

    Desligar não apaga dado nenhum: some da tela, e ligar de volta traz tudo.
    """

    chave = models.CharField("chave", max_length=60, unique=True)
    ativo = models.BooleanField("ligado", default=False)

    # Sobrescritas por cliente. Em branco significa "usa o que o código
    # declarou". Existem porque cliente pede nome e ordem próprios, e isso no
    # código viraria exceção por cliente — o custo que a matriz elimina.
    rotulo = models.CharField("rótulo", max_length=120, blank=True)
    grupo = models.CharField("grupo", max_length=120, blank=True)
    ordem = models.IntegerField("ordem", default=0)

    class Meta:
        verbose_name = "módulo"
        verbose_name_plural = "módulos"
        ordering = ("ordem", "chave")

    def __str__(self) -> str:
        return self.rotulo or self.chave
```

- [ ] **Step 5: Escrever `plataforma/catalogo.py`**

```python
"""O cruzamento entre o que o código declara e o que o banco liga."""

from __future__ import annotations

from .declaracao import ModuloSpec, declarados

__all__ = ["modulos_ligados", "semear"]


def semear(apps=None) -> int:
    """Cria a linha faltante de cada módulo declarado, desligada.

    Roda na migração, então roda em toda instalação que receber a versão. É
    esta função que faz o módulo novo aparecer sozinho nas vinte bases.

    **Não mexe em linha que já existe.** A atualização que traz o módulo novo
    não pode apagar a escolha que a MW5 já fez nos outros.
    """
    Modulo = apps.get_model("plataforma", "Modulo") if apps else _modulo()
    existentes = set(Modulo.objects.values_list("chave", flat=True))
    novas = [Modulo(chave=spec.chave, ativo=False)
             for spec in declarados() if spec.chave not in existentes]
    Modulo.objects.bulk_create(novas)
    return len(novas)


def modulos_ligados() -> tuple[ModuloSpec, ...]:
    """Os módulos ligados nesta instalação, na ordem configurada.

    Linha no banco sem declaração no código é **ignorada**: um módulo removido
    do código deixa a linha para trás, e ela não pode virar item de menu
    apontando para uma rota que não existe mais.
    """
    ligadas = _modulo().objects.filter(ativo=True).order_by("ordem", "chave")
    por_chave = {spec.chave: spec for spec in declarados()}
    return tuple(por_chave[linha.chave] for linha in ligadas
                 if linha.chave in por_chave)


def _modulo():
    from .models import Modulo

    return Modulo
```

- [ ] **Step 6: Escrever a migração que semeia**

```bash
DJANGO_DEBUG=1 .venv/bin/python manage.py makemigrations plataforma
```

Depois criar `plataforma/migrations/0002_semear_modulos.py` — uma `RunPython` que chama `semear(apps)` na subida e não faz nada na descida (a descida não apaga linha: dado de cliente não some numa migração reversa).

- [ ] **Step 7: Rodar e commitar**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_catalogo_de_modulos.py -v`
Esperado: PASS, 10 testes.

```bash
git add plataforma tests/test_catalogo_de_modulos.py
git commit -m "feat: o codigo diz quais modulos existem, o banco diz quais estao ligados

A migracao semeia a linha do modulo novo, desligada, em toda base que
receber a versao. Sem isso, modulo novo custa vinte intervencoes manuais."
```

---

### Task 8: O menu se monta sozinho

**Files:**
- Create: `plataforma/menu.py`
- Modify: `nucleo/views.py` (o `NAV_DEMO` escrito à mão dá lugar ao menu montado)
- Test: `tests/test_menu.py`

**Interfaces:**
- Consumes: `plataforma.catalogo.modulos_ligados` (Task 7); `nucleo.layout.NavItem` (`label`, `icon`, `href`, `permission`, `children`); `nucleo.permissoes.pode`.
- Produces: `plataforma.menu.montar(user: nucleo.permissoes.User | None) -> list[nucleo.layout.NavItem]`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_menu.py`:

```python
"""O menu nasce do cruzamento: módulos ligados × permissão de quem olha.

Ninguém escreve menu. O `nav.py` de 320 linhas escrito à mão do
`sementes-premix` deixa de existir aqui.
"""

import pytest

from nucleo.permissoes import User
from plataforma.declaracao import ModuloSpec, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    yield
    declaracao._DECLARADOS.clear()
    declaracao._DECLARADOS.update(guardado)


@pytest.fixture
def frete_ligado(catalogo_limpo, db):
    from plataforma.catalogo import semear
    from plataforma.models import Modulo

    registrar(ModuloSpec(chave="frete", rotulo="Frete", icone="truck",
                         grupo="Consultas", rota="/frete",
                         permissoes=("frete.ver",)))
    registrar(ModuloSpec(chave="vendas", rotulo="Vendas", icone="chart-bar",
                         grupo="Consultas", rota="/vendas",
                         permissoes=("vendas.ver",)))
    semear()
    Modulo.objects.filter(chave="frete").update(ativo=True)


@pytest.mark.django_db
class TestOMenu:
    def test_modulo_desligado_nao_aparece_nem_para_o_superusuario(self, frete_ligado):
        """Módulo que o cliente não comprou não existe. Nem para a MW5 dentro
        da instalação dele — para ligar, é a tela de Módulos."""
        from plataforma.menu import montar

        raiz = User(id="1", name="MW5", superuser=True)
        rotulos = _todos_os_rotulos(montar(raiz))
        assert "Frete" in rotulos
        assert "Vendas" not in rotulos

    def test_sem_a_permissao_o_item_some(self, frete_ligado):
        from plataforma.menu import montar

        ana = User(id="2", name="Ana", permissions=frozenset())
        assert "Frete" not in _todos_os_rotulos(montar(ana))

    def test_com_a_permissao_o_item_aparece(self, frete_ligado):
        from plataforma.menu import montar

        ana = User(id="2", name="Ana", permissions={"frete.ver"})
        assert "Frete" in _todos_os_rotulos(montar(ana))

    def test_o_coringa_do_modulo_tambem_serve(self, frete_ligado):
        from plataforma.menu import montar

        gestor = User(id="3", name="Bruno", permissions={"frete.*"})
        assert "Frete" in _todos_os_rotulos(montar(gestor))

    def test_sem_usuario_nao_sai_menu(self, frete_ligado):
        from plataforma.menu import montar

        assert montar(None) == []

    def test_os_itens_sao_agrupados_pelo_grupo_declarado(self, frete_ligado):
        from plataforma.menu import montar

        raiz = User(id="1", name="MW5", superuser=True)
        topo = montar(raiz)
        assert [i.label for i in topo] == ["Consultas"]
        assert [f.label for f in topo[0].children] == ["Frete"]

    def test_o_rotulo_do_banco_vence_o_do_codigo(self, frete_ligado):
        """Cliente pede nome próprio; no código isso viraria exceção por
        cliente, que é o custo que a matriz elimina."""
        from plataforma.menu import montar
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="frete").update(rotulo="Transporte")
        raiz = User(id="1", name="MW5", superuser=True)
        assert "Transporte" in _todos_os_rotulos(montar(raiz))


def _todos_os_rotulos(itens):
    saida = []
    for item in itens:
        saida.append(item.label)
        saida.extend(_todos_os_rotulos(item.children))
    return saida
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_menu.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'plataforma.menu'`.

- [ ] **Step 3: Escrever `plataforma/menu.py`**

O módulo monta os `NavItem` agrupando por `grupo`, aplicando as sobrescritas do banco (`rotulo`, `grupo`, `ordem`), e filtrando pela primeira permissão declarada de cada módulo. Grupo que fica sem filho visível não é desenhado.

Ponto que o código precisa deixar explícito num comentário: **esconder o item não é proteger a rota.** A rota checa de novo, com `exigir_permissao`.

- [ ] **Step 4: Ligar o menu à aplicação**

Em `nucleo/views.py`, o `NAV_DEMO` escrito à mão sai e o `Site.nav` passa a vir de `plataforma.menu.montar(request.usuario)`.

**É alteração em `nucleo/`.** Autorizada pelo mesmo motivo da Task 5: `views.py` é autoral, e o comentário do próprio arquivo já anunciava que o bloco sairia quando o menu viesse do banco.

Aproveite para **matar a mutação global** `SITE.nav = ...` que a revisão da entrega 1 registrou como pendência: o `Site` passa a ser montado por requisição, não a ser um global mutado.

- [ ] **Step 5: Rodar, ver, commitar**

Run: `DJANGO_DEBUG=1 .venv/bin/pytest -q`
Esperado: verde.

```bash
git add plataforma/menu.py nucleo/views.py tests/test_menu.py
git commit -m "feat: o menu se monta sozinho

Modulos ligados x permissao de quem olha. Ninguem escreve menu: o nav.py
escrito a mao deixa de existir."
```

---

### Task 9: A tela de Módulos

**Files:**
- Modify: `plataforma/views.py`, `plataforma/urls.py`
- Test: `tests/test_tela_modulos.py`

**Interfaces:**
- Consumes: `plataforma.catalogo` (Task 7), `plataforma.menu` (Task 8), `contas.guardas.exigir_permissao`.
- Produces: rota nomeada `modulos` (`/mw5/modulos`, GET e POST), exigindo `mw5.modulos`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_tela_modulos.py` com, no mínimo:

```python
"""A tela onde a MW5 liga o que o cliente comprou."""

import pytest
from django.contrib.auth.models import Group, User as UsuarioDjango
from django.test import Client
from django.urls import reverse

from plataforma.declaracao import ModuloSpec, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    yield
    declaracao._DECLARADOS.clear()
    declaracao._DECLARADOS.update(guardado)


@pytest.fixture
def cliente_mw5(db, catalogo_limpo):
    from plataforma.catalogo import semear

    registrar(ModuloSpec(chave="frete", rotulo="Frete", icone="truck",
                         grupo="Consultas", rota="/frete",
                         permissoes=("frete.ver",)))
    semear()
    u = UsuarioDjango.objects.create_superuser(
        username="mw5", password="segredo-de-teste")
    c = Client()
    c.post(reverse("entrar"), {"login": "mw5", "senha": "segredo-de-teste"})
    return c


class TestQuemEntra:
    def test_a_mw5_abre(self, cliente_mw5):
        assert cliente_mw5.get(reverse("modulos")).status_code == 200

    def test_o_admin_do_cliente_nao_ve(self, db, catalogo_limpo):
        UsuarioDjango.objects.create_user(username="ana", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
        assert c.get(reverse("modulos")).status_code == 404


class TestLigarEDesligar:
    def test_a_tela_lista_os_modulos_declarados(self, cliente_mw5):
        assert "Frete" in cliente_mw5.get(reverse("modulos")).content.decode()

    def test_ligar_grava(self, cliente_mw5):
        from plataforma.models import Modulo

        cliente_mw5.post(reverse("modulos"), {"ligados": ["frete"]})
        assert Modulo.objects.get(chave="frete").ativo is True

    def test_desligar_grava(self, cliente_mw5):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="frete").update(ativo=True)
        cliente_mw5.post(reverse("modulos"), {"ligados": []})
        assert Modulo.objects.get(chave="frete").ativo is False

    def test_desligar_nao_apaga_a_linha(self, cliente_mw5):
        from plataforma.models import Modulo

        cliente_mw5.post(reverse("modulos"), {"ligados": []})
        assert Modulo.objects.filter(chave="frete").exists()


@pytest.mark.django_db
def test_ligar_faz_o_modulo_aparecer_no_menu(cliente_mw5):
    """A promessa da entrega, do outro lado: ligar aqui muda a tela de lá."""
    antes = cliente_mw5.get("/").content.decode()
    assert "Frete" not in antes

    cliente_mw5.post(reverse("modulos"), {"ligados": ["frete"]})
    depois = cliente_mw5.get("/").content.decode()
    assert "Frete" in depois
```

- [ ] **Step 2: Rodar, ver falhar, implementar, ver passar**

A view lista `declarados()` com um `Checkbox` por módulo, marcado conforme a linha do banco, dentro de um `Form`. O `POST` liga o que veio em `ligados` e desliga o resto — **sem apagar linha**.

Run: `DJANGO_DEBUG=1 .venv/bin/pytest tests/test_tela_modulos.py -v`
Esperado: PASS, 7 testes.

- [ ] **Step 3: Commit**

```bash
git add plataforma tests/test_tela_modulos.py
git commit -m "feat: a tela de Modulos

Desligar some da tela e nao apaga dado: apagar registro de cliente numa
chavinha seria caro demais."
```

---

### Task 10: O módulo de exemplo

**Files:**
- Create: `modulos/__init__.py`, `modulos/exemplo/__init__.py`, `modulos/exemplo/modulo.py`, `modulos/exemplo/views.py`, `modulos/exemplo/urls.py`
- Modify: `config/settings.py` (registra o app), `config/urls.py`
- Test: `tests/test_modulo_exemplo.py`

**Interfaces:**
- Consumes: `plataforma.declaracao.ModuloSpec` e `registrar` (Task 7); `contas.guardas.exigir_permissao` (Task 4).
- Produces: o módulo `exemplo`, declarando a rota `/exemplo` e as permissões `exemplo.ver` e `exemplo.editar`.

- [ ] **Step 1: Escrever o teste que falha**

O teste prova o ciclo inteiro, que é o que esta tarefa existe para demonstrar:

```python
"""O caminho completo de um módulo, do código até a tela.

Este é o teste que prova o mecanismo da matriz: o módulo se declara no
código, a migração cria a linha desligada, a MW5 liga na tela, e ele aparece
no menu de quem tem permissão — sem ninguém editar código.
"""

import pytest
from django.contrib.auth.models import Group, User as UsuarioDjango
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestOCicloCompleto:
    def test_o_modulo_esta_declarado_no_codigo(self):
        from plataforma.declaracao import declarados

        assert "exemplo" in [m.chave for m in declarados()]

    def test_a_migracao_criou_a_linha_desligada(self):
        from plataforma.models import Modulo

        assert Modulo.objects.get(chave="exemplo").ativo is False

    def test_desligado_a_rota_nao_existe_nem_para_o_superusuario(self):
        """Módulo desligado não é só menu escondido: a porta está trancada."""
        UsuarioDjango.objects.create_superuser(
            username="mw5", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"login": "mw5", "senha": "segredo-de-teste"})
        assert c.get("/exemplo").status_code == 404

    def test_ligado_e_com_permissao_a_tela_abre(self):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="exemplo").update(ativo=True)
        ana = UsuarioDjango.objects.create_user(
            username="ana", password="segredo-de-teste")
        ana.groups.add(Group.objects.create(name="exemplo"))
        c = Client()
        c.post(reverse("entrar"), {"login": "ana", "senha": "segredo-de-teste"})
        assert c.get("/exemplo").status_code == 200

    def test_ligado_e_sem_permissao_a_tela_nao_abre(self):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="exemplo").update(ativo=True)
        UsuarioDjango.objects.create_user(
            username="bruno", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"login": "bruno", "senha": "segredo-de-teste"})
        assert c.get("/exemplo").status_code == 404
```

- [ ] **Step 2: Implementar**

`modulos/exemplo/modulo.py` declara o `ModuloSpec` e chama `registrar()` no `AppConfig.ready()` — não na importação do módulo, para não depender da ordem de import.

A view usa `@exigir_permissao("exemplo.ver")` **e** verifica que o módulo está ligado. Escreva essa verificação como uma guarda reutilizável em `plataforma/`, porque todo módulo futuro vai precisar dela — e um teste que só cheque a do exemplo não protege os próximos.

- [ ] **Step 3: Rodar, ver a tela, commitar**

Suba o servidor. Entre como MW5. Abra `/mw5/modulos`, ligue o Exemplo, e **veja ele aparecer no menu**. Desligue e veja sumir.

```bash
git add modulos config tests/test_modulo_exemplo.py plataforma
git commit -m "feat: o modulo de exemplo, e a guarda de modulo ligado

Prova o ciclo: declara no codigo, a migracao semeia desligado, a MW5 liga na
tela, aparece no menu de quem tem permissao. Sem editar codigo."
```

---

### Task 11: A imagem e o compose

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Modify: `README.md`
- Test: `tests/test_imagem.py`

**Interfaces:**
- Consumes: tudo.
- Produces: `docker compose up` sobe banco e aplicação, na ordem, e serve o sistema.

- [ ] **Step 1: Escrever o teste que falha**

O que dá para testar sem subir contêiner: que os arquivos existem, que o compose **recusa subir sem `DJANGO_SECRET_KEY`**, e que o `Dockerfile` não põe segredo em `ENV`.

```python
"""A imagem que vai para as vinte VPS.

O que se testa aqui é o que dá para testar sem Docker de pé: que o segredo
não entra na imagem, e que o compose recusa subir sem ele.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_o_dockerfile_existe():
    assert (RAIZ / "Dockerfile").is_file()


def test_o_segredo_nao_entra_como_env_na_imagem():
    """`docker history` mostra cada camada: um ENV com segredo viaja para o
    registry junto com a imagem."""
    texto = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.strip().startswith("ENV"):
            assert "SECRET" not in linha.upper()
            assert "SENHA" not in linha.upper()
            assert "PASSWORD" not in linha.upper()


def test_o_compose_exige_a_chave_de_sessao():
    texto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert "DJANGO_SECRET_KEY" in texto
    assert "?" in texto, "o compose deve recusar subir sem a chave (sintaxe ${VAR:?})"


def test_o_compose_espera_o_banco_ficar_pronto():
    """Subir a aplicação antes do banco dá erro de conexão na primeira tela."""
    texto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert "healthcheck" in texto
    assert "service_healthy" in texto


def test_o_readme_diz_como_subir():
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert "docker compose up" in texto
```

- [ ] **Step 2: Escrever o `Dockerfile`**

Base `python:3.13-slim`. Instala as dependências, copia o projeto, roda `collectstatic`, e sobe com `gunicorn`. **Nenhum `ENV` com segredo** — o cabeçalho do arquivo lista as variáveis exigidas e diz por que nenhuma tem valor padrão.

- [ ] **Step 3: Escrever o `docker-compose.yml`**

Dois serviços: `banco` (Postgres, com `healthcheck`) e `app` (depende do banco com `condition: service_healthy`). A chave entra como `${DJANGO_SECRET_KEY:?defina DJANGO_SECRET_KEY antes de subir}` — o `:?` faz o compose **recusar** subir sem ela.

A aplicação roda `migrate` na subida, o que executa a semeadura dos módulos.

- [ ] **Step 4: Subir de verdade e percorrer o caminho inteiro**

```bash
export DJANGO_SECRET_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build
```

Com o sistema no ar, percorra e **anote o resultado de cada passo**:

1. A tela de login abre
2. Criar um superusuário (`docker compose exec app python manage.py createsuperuser`) e entrar
3. `/mw5/modulos` lista o módulo Exemplo, desligado
4. Ligar o Exemplo — ele aparece no menu
5. Abrir a tela do Exemplo
6. `/mw5/aparencia` — trocar a cor primária e salvar
7. **O sistema inteiro mudou de cor**
8. Desligar o Exemplo — ele some do menu
9. Sair — volta para o login

**E o passo 10, que é o que nenhum dos outros pega — o caminho de ATUALIZAÇÃO:**

Os nove passos acima sobem num banco novo, e instalação nova funciona. As vinte instalações reais **não são novas**. Um defeito que só aparece ao atualizar passa por todos os nove.

Com o sistema ainda de pé, e o banco já migrado:

```bash
# 1. declare um módulo novo no código (copie `modulos/exemplo/` para
#    `modulos/segundo/`, trocando a chave, o rótulo e a rota)
# 2. reinicie a aplicação rodando as migrações, como um deploy faria
docker compose exec app python manage.py migrate
docker compose restart app
```

10. Abrir `/mw5/modulos`: **o módulo novo tem que estar lá, desligado.** Ligar, e ele aparece no menu.

Se ele não aparecer na lista, a semeadura não alcançou a instalação existente — e é exatamente esse o defeito que a promessa "módulo novo aparece sozinho nas vinte bases" existe para impedir. **Pare e reporte.**

Depois de conferir, remova `modulos/segundo/` — ele existe só para este passo.

Se algum passo falhar, **pare e reporte qual**. Este roteiro é o critério de pronto da entrega.

- [ ] **Step 5: Atualizar o `README.md` e commitar**

O `README` ganha a seção de subir em contêiner, as variáveis exigidas, e o roteiro acima como "como conferir que está funcionando".

```bash
git add Dockerfile docker-compose.yml .dockerignore README.md tests/test_imagem.py
git commit -m "feat: a imagem e o compose

O compose recusa subir sem DJANGO_SECRET_KEY: chave gerada a cada boot
deslogaria todo mundo a cada restart, e duas replicas nao se reconheceriam."
```

---

## Critério de pronto da entrega

O roteiro de nove passos da Task 11, Step 4, percorrido inteiro com o sistema em contêiner. Mais:

- `DJANGO_DEBUG=1 .venv/bin/pytest` verde, sem `xfail`, sem skip novo
- `DJANGO_DEBUG=1 .venv/bin/python manage.py check` limpo
- Nenhuma cor, fonte ou caminho de logo fora de `nucleo/theme/`:

```bash
grep -rnE "#[0-9a-fA-F]{6}" --include=*.py --include=*.html \
  nucleo/ contas/ plataforma/ modulos/ config/ \
  | grep -v "nucleo/theme/" | grep -v "nucleo/icons_lucide.json"
```

Esperado: nenhuma linha.

- `nucleo/` continua divergindo da origem só nos pontos autorizados, **mais** as três alterações que este plano autoriza explicitamente em `nucleo/views.py` (guarda de login, marca do banco, menu montado) — todas em código autoral, nenhuma em conteúdo portado:

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
for f in campos.py descricao.py layout.py site.py rendering.py icons.py; do
  echo "== $f"; diff "$FONTE/$f" "nucleo/$f"
done
```

## O que fica para depois

Auditoria e personificação; troca da própria senha e foto de perfil; telas de Usuários e de Perfis; empresa e filial; autenticação pelo Oracle do cliente; o painel central de versões da MW5; o inventário `kronos-net-clientes` e o rollout em escada nas VPS; e engordar o módulo de exemplo até virar um módulo de verdade.
