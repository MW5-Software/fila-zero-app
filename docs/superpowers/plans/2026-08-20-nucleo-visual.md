# Núcleo Visual do KRONOS.net — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Colocar um projeto Django de pé com todo o design system da MW5 dentro dele, ao ponto de uma tela do KRONOS.net sair visualmente equivalente à de `sementes-premix` sem uma linha de CSS escrita à mão.

**Architecture:** Portar o pacote `mw5_admin` (hoje FastAPI) para um app Django chamado `nucleo`. A maior parte é cópia com ajuste de caminho de import: dos 31 arquivos do pacote, 27 não conhecem FastAPI. O Django **não** renderiza os componentes pelo sistema de templates dele — os componentes já sabem se renderizar em Jinja, e uma view apenas devolve o HTML pronto. A suíte de testes existente do `mw5_admin` viaja junto e é a especificação de cada porte: um módulo só está portado quando os testes que já o cobriam passam contra o novo caminho.

**Tech Stack:** Python 3.13 (via `uv`), Django 5.2 LTS, Jinja2, pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-08-20-kronos-net-matriz-design.md`

## Global Constraints

- **Fonte do porte:** `/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin/` — referida abaixo como `$FONTE`. A suíte fonte é `/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/tests/` — referida como `$FONTE_TESTES`. **Somente leitura.** Nada neste plano escreve em `criadordesitesmw5`.
- **Python 3.13**, não 3.14: o Django 5.2 LTS não suporta 3.14, e a `/usr/bin/python3` desta máquina é 3.14. O ambiente é criado com `uv venv --python 3.13`.
- **Nenhuma cor, fonte ou caminho de logo em arquivo `.py` ou `.html`** fora de `nucleo/theme/brand.py`. Regra 3 da spec.
- **Nenhum módulo importa outro módulo.** Em entrega 1 não existem módulos ainda; a regra vale para o que for criado.
- **Marca vem de `brand.yaml` nesta entrega.** A tabela `marca` é entrega 3. Não criar model de marca aqui.
- **Não portar** nada de `mw5_generator` — é a ferramenta que gera um projeto por cliente, e a premissa do KRONOS.net é que não existe geração por cliente. Teste portado que dependa dela não se adia: sai. **Não portar** `app.py`, `auth/guards.py`, `dados/resource.py`, `dados/sql.py` — são os quatro arquivos acoplados a FastAPI, e o que os substitui é entrega 2 e 3. Também fora: `images.py` (upload, entrega 3), `auth/backend.py`, `auth/banco.py`, `auth/kronos.py`, `auth/session.py`, `auth/passwords.py` (entrega 2).
- **Idioma:** código, comentários, docstrings, nomes de teste e mensagens de commit em português, como no `mw5_admin` e no `sementes-premix`. **Exceção: conteúdo portado não se traduz.** Boa parte da suíte do `mw5_admin` tem nomes de teste em inglês (`test_hex_roundtrip_is_exact`), e renomeá-los quebraria a única propriedade que dá valor a este porte — a de que o arquivo portado difere da origem apenas nos pontos que o plano nomeia, verificável por `diff`. Sem isso, ressincronizar com o `mw5_admin` no futuro vira leitura manual. A regra de idioma vale para o que se **escreve** aqui; o que se **copia** fica como está. O boilerplate gerado pelo `django-admin` cai na mesma exceção.
- **Commits:** um por tarefa, no formato `tipo: descrição` (`feat`, `test`, `chore`, `fix`).

## Estrutura de arquivos ao fim da entrega

```
kronos-net/
├─ pyproject.toml               deps, pytest, DJANGO_SETTINGS_MODULE
├─ manage.py
├─ config/                      o projeto Django
│  ├─ settings.py
│  ├─ urls.py
│  └─ wsgi.py, asgi.py
├─ nucleo/                      o app: design system inteiro
│  ├─ apps.py
│  ├─ rendering.py              base do componente + ambiente Jinja
│  ├─ resposta.py               render() -> HttpResponse
│  ├─ theme/
│  │  ├─ __init__.py, color.py, tokens.py, brand.py, css.py
│  ├─ components/
│  │  ├─ __init__.py, primitives.py, containers.py, data.py,
│  │  │  forms.py, charts.py, permissions.py
│  ├─ icons.py, icons_lucide.json
│  ├─ campos.py, descricao.py, catalogo.py
│  ├─ permissoes.py             User, pode(), SENHA_MINIMA
│  ├─ layout.py, site.py
│  ├─ views.py, urls.py         /tema.css e a tela de demonstração
│  ├─ templates/                58 arquivos .html (components/ e layout/)
│  └─ static/nucleo/            mw5.css, mw5.js, htmx.min.js, cropper
└─ tests/                       a suíte portada
```

**Por que `nucleo/permissoes.py` existe nesta entrega:** `site.py` importa `pode` e `layout.py` importa `SENHA_MINIMA`. São dataclasses e uma função pura, sem framework. O `contas/` da entrega 2 constrói a autenticação de verdade **em cima** disso — produz objetos `User` e os entrega ao `Site`. Sem este arquivo, `layout.py` e `site.py` não carregam.

**Por que a rota do tema é `/tema.css` e não `/static/theme.css`:** o `django.contrib.staticfiles` serve tudo sob `/static/` em desenvolvimento, e uma rota nossa dentro desse prefixo depende da ordem das URLs para funcionar. Um caminho próprio elimina a ambiguidade. `Site.theme_href` é configurável exatamente para isto.

---

### Task 1: Projeto Django de pé

**Files:**
- Create: `pyproject.toml`
- Create: `manage.py`, `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`
- Create: `nucleo/__init__.py`, `nucleo/apps.py`
- Test: `tests/test_projeto.py`

**Interfaces:**
- Consumes: nada.
- Produces: o app Django `nucleo` registrado em `INSTALLED_APPS`; `DJANGO_SETTINGS_MODULE=config.settings` resolvido pelo pytest; comando `.venv/bin/pytest` funcionando a partir da raiz do repositório.

- [ ] **Step 1: Criar o ambiente e instalar as dependências**

```bash
cd /home/mw5/projetos/kronos-net
uv venv --python 3.13
.venv/bin/python -m ensurepip --upgrade
.venv/bin/pip install "django>=5.2,<6" "jinja2>=3.1" "pyyaml>=6.0" "pytest>=8.0" "pytest-django>=4.9"
.venv/bin/python -c "import django; print(django.get_version())"
```

Esperado: imprime `5.2.x`.

- [ ] **Step 2: Escrever o `pyproject.toml`**

```toml
[project]
name = "kronos-net"
version = "0.1.0"
description = "A matriz KRONOS.net — um sistema, N instalações"
requires-python = ">=3.13,<3.14"
dependencies = [
    "django>=5.2,<6",
    "jinja2>=3.1",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-django>=4.9"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 3: Escrever o teste que falha**

Criar `tests/test_projeto.py`:

```python
"""O projeto Django sobe, e o app do design system está dentro dele.

Um teste bobo de propósito: se ele falha, nada mais do plano roda, e o erro
aparece aqui em vez de aparecer disfarçado de import quebrado três tarefas
adiante.
"""

from django.conf import settings


def test_o_app_do_nucleo_esta_instalado():
    assert "nucleo" in settings.INSTALLED_APPS


def test_o_projeto_passa_no_check_do_django():
    from django.core.management import call_command

    call_command("check")
```

- [ ] **Step 4: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_projeto.py -v`
Esperado: FAIL — `ModuleNotFoundError: No module named 'config'`.

- [ ] **Step 5: Criar o esqueleto do projeto**

```bash
.venv/bin/django-admin startproject config .
mkdir -p nucleo
touch nucleo/__init__.py
```

Criar `nucleo/apps.py`:

```python
from django.apps import AppConfig


class NucleoConfig(AppConfig):
    """O design system: tema, componentes, layout.

    Não tem model nenhum nesta entrega, e é de propósito: o núcleo desenha
    tela, não guarda dado. Quem guarda é `plataforma` e `contas`.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "nucleo"
```

- [ ] **Step 6: Ajustar `config/settings.py`**

Substituir o `INSTALLED_APPS` gerado por:

```python
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "nucleo",
]
```

Ao final do arquivo, garantir:

```python
STATIC_URL = "/static/"
```

`django.contrib.admin`, `auth`, `sessions` e `messages` entram na entrega 2, junto com o `contas/`. Instalá-los agora traria migrações e um banco que nada nesta entrega usa.

Remover de `MIDDLEWARE` as entradas que dependem de apps não instalados, deixando:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]
```

- [ ] **Step 7: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_projeto.py -v`
Esperado: PASS, 2 testes.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml manage.py config nucleo tests
git commit -m "chore: projeto Django de pe, com o app do nucleo registrado"
```

---

### Task 2: `nucleo/rendering.py` — a base de todo componente

**Files:**
- Create: `nucleo/rendering.py` (de `$FONTE/rendering.py`)
- Create: `nucleo/resposta.py`
- Test: `tests/test_rendering.py`

**Interfaces:**
- Consumes: o app `nucleo` da Task 1.
- Produces:
  - `nucleo.rendering.Component` — dataclass base; `template: ClassVar[str]`, `template_context() -> dict`, `render(env=None) -> Markup`, `__html__()`.
  - `nucleo.rendering.create_environment(*extra_loaders) -> jinja2.Environment`
  - `nucleo.rendering.get_environment() -> Environment`
  - `nucleo.rendering.use_environment(env)` — context manager
  - `nucleo.rendering.render_all(value) -> Markup`
  - `nucleo.rendering.html_attrs(values: dict | None) -> Markup`
  - `nucleo.rendering.Renderable` — alias de `Any`
  - `nucleo.resposta.render(component, status=200) -> django.http.HttpResponse`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_rendering.py`:

```python
"""A base do componente e a ponte com o Django.

O que importa aqui é que a árvore de componentes renderiza sozinha (um filho
que é componente vira HTML sem ninguém pedir) e que o HTML sai escapado por
padrão — um rótulo com `<script>` dentro não pode virar script na tela.
"""

from dataclasses import dataclass, field
from typing import ClassVar

import pytest
from markupsafe import Markup

from nucleo.rendering import (
    Component,
    create_environment,
    html_attrs,
    render_all,
    use_environment,
)
from nucleo.resposta import render


@dataclass
class Caixa(Component):
    template: ClassVar[str] = ""
    conteudo: object = ""

    def render(self, env=None) -> Markup:
        return Markup(f"<div>{render_all(self.conteudo)}</div>")


def test_componente_dentro_de_componente_renderiza_sozinho():
    fora = Caixa(conteudo=Caixa(conteudo="oi"))
    assert str(fora.render()) == "<div><div>oi</div></div>"


def test_lista_de_filhos_vira_html_concatenado():
    assert str(render_all([Caixa(conteudo="a"), Caixa(conteudo="b")])) == (
        "<div>a</div><div>b</div>"
    )


def test_texto_cru_sai_escapado():
    assert str(render_all("<script>x</script>")) == (
        "&lt;script&gt;x&lt;/script&gt;"
    )


def test_none_e_false_nao_desenham_nada():
    assert str(render_all(None)) == ""
    assert str(render_all(False)) == ""


def test_atributos_html_escapam_valor_e_trocam_underscore_por_traco():
    saida = str(html_attrs({"hx_get": "/a?b=1&c=2", "data_x": True, "y": None}))
    assert 'hx-get="/a?b=1&amp;c=2"' in saida
    assert "data-x" in saida
    assert "y" not in saida


def test_componente_sem_template_declarado_recusa_renderizar():
    @dataclass
    class SemTemplate(Component):
        pass

    with pytest.raises(NotImplementedError):
        SemTemplate().render()


def test_o_ambiente_acha_os_templates_do_pacote():
    env = create_environment()
    with use_environment(env):
        assert env.get_template("components/button.html") is not None


def test_render_devolve_resposta_do_django_com_html_dentro():
    resposta = render(Caixa(conteudo="pronto"))
    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith("text/html")
    assert resposta.content.decode() == "<div>pronto</div>"
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_rendering.py -v`
Esperado: FAIL — `ModuleNotFoundError: No module named 'nucleo.rendering'`.

- [ ] **Step 3: Copiar `rendering.py` e ajustar os dois pontos que mudam**

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
cp "$FONTE/rendering.py" nucleo/rendering.py
sed -i 's/PackageLoader("mw5_admin", "templates")/PackageLoader("nucleo", "templates")/' nucleo/rendering.py
grep -n 'PackageLoader\|static' nucleo/rendering.py
```

O `grep` deve mostrar `PackageLoader("nucleo", "templates")` e a função `estatico`, que hoje resolve `Path(__file__).parent / "static" / nome` e devolve `/static/{nome}`.

No Django, o estático de um app mora em `<app>/static/<app>/` e é servido em `/static/<app>/`. **O caminho no disco e o da URL têm de mudar juntos** — mudar só um faz a versão sair na URL de um arquivo que o navegador não acha. Substituir o corpo da função `estatico` por:

```python
        arquivo = Path(__file__).parent / "static" / "nucleo" / nome
        try:
            return f"/static/nucleo/{nome}?v={int(arquivo.stat().st_mtime)}"
        except OSError:
            return f"/static/nucleo/{nome}"
```

A docstring da função explica por que a versão está ali — trocar o `mw5.css` e o navegador continuar servindo o de ontem custou uma tarde de conserto no escuro. Mantê-la.

O resto do arquivo fica como está. Ele não conhece FastAPI.

- [ ] **Step 4: Escrever `nucleo/resposta.py`**

```python
"""A ponte entre um componente e uma resposta HTTP do Django.

O Django tem um sistema de templates próprio, e este projeto não o usa para
desenhar tela: o componente já sabe virar HTML, e passar por um segundo motor
de template só para embrulhar o resultado seria uma camada sem trabalho.

O `TEMPLATES` do `settings.py` continua existindo para o que o Django precisa
dele — mensagens de erro, e o admin quando ele entrar.
"""

from __future__ import annotations

from django.http import HttpResponse

from .rendering import Component, get_environment, use_environment

__all__ = ["render"]


def render(component: Component, status: int = 200) -> HttpResponse:
    """Renderiza um componente e devolve a resposta pronta."""
    env = get_environment()
    with use_environment(env):
        html = str(component.render(env))
    return HttpResponse(html, status=status, content_type="text/html; charset=utf-8")
```

- [ ] **Step 5: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_rendering.py -v`
Esperado: 7 testes PASS e 1 FAIL — `test_o_ambiente_acha_os_templates_do_pacote`, porque `nucleo/templates/` ainda não existe (chega na Task 6). Marcar esse teste temporariamente:

```python
@pytest.mark.xfail(reason="templates chegam na Task 6", strict=True)
def test_o_ambiente_acha_os_templates_do_pacote():
```

Rodar de novo. Esperado: 8 PASS (1 como xfail).

- [ ] **Step 6: Commit**

```bash
git add nucleo/rendering.py nucleo/resposta.py tests/test_rendering.py
git commit -m "feat: a base do componente e a ponte com o Django"
```

---

### Task 3: `nucleo/theme/` — a cor primária deriva a paleta

**Files:**
- Create: `nucleo/theme/__init__.py`, `color.py`, `tokens.py`, `brand.py`, `css.py` (de `$FONTE/theme/`)
- Test: `tests/test_theme.py` (de `$FONTE_TESTES/test_theme.py`, 700 linhas)

**Interfaces:**
- Consumes: nada da Task 2 — o tema não renderiza HTML.
- Produces:
  - `nucleo.theme.Brand` — dataclass frozen. Construtores: `Brand(client_name=..., primary=..., accent=...)`, `Brand.from_dict(data: dict) -> Brand`, `Brand.from_yaml(path) -> Brand`. Métodos: `tokens(mode: str = "light") -> dict[str, str]`, `with_overrides(mode, **values) -> Brand`.
  - Campos de `Brand` usados adiante: `client_name`, `system_name`, `primary`, `accent`, `default_theme`, `font_display`, `font_body`, `radius`, `density`, `sidebar_width`, `assets`, `login`, `header`, `footer`, `areas`.
  - `nucleo.theme.render_theme_css(brand: Brand) -> str`
  - `nucleo.theme.Color`, `contrast_ratio(a, b) -> float`, `readable_on(fundo) -> str`, `legivel_sobre`, `mix`
  - `nucleo.theme.Assets` (`logo_for(lugar) -> str`), `LoginBrand`, `FooterBrand`, `AreaColors`, `HeaderBrand`
  - `nucleo.theme.TOKEN_NAMES`

- [ ] **Step 1: Portar a suíte de testes primeiro**

```bash
FONTE_TESTES=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/tests
cp "$FONTE_TESTES/test_theme.py" tests/test_theme.py
sed -i 's/\bmw5_admin\b/nucleo/g' tests/test_theme.py
grep -c "mw5_admin" tests/test_theme.py
```

Esperado do `grep -c`: `0`.

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_theme.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'nucleo.theme'`.

- [ ] **Step 3: Copiar o pacote do tema**

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
cp -r "$FONTE/theme" nucleo/theme
rm -rf nucleo/theme/__pycache__
grep -rn "mw5_admin" nucleo/theme/ || echo "nenhum import absoluto — nada a ajustar"
```

Os imports de `theme/` são todos relativos (`from .color import Color`, `from . import tokens as _tokens`), então não há o que reescrever.

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_theme.py -v`
Esperado: PASS na suíte inteira.

Se algum teste falhar citando `brand.yaml`, é porque ele carrega um arquivo de exemplo por caminho relativo. Nesse caso, copiar o arquivo citado para `tests/fixtures/` e ajustar o caminho no teste — não alterar `brand.py`.

- [ ] **Step 5: Acrescentar o teste de contraste da marca**

É o teste nº 4 da spec, e o código que ele exercita chega nesta tarefa. Acrescentar ao fim de `tests/test_theme.py`:

```python
class TestContrasteDaMarca:
    """Cor escolhida no painel não pode deixar texto ilegível.

    A tela de Aparência (entrega 3) recusa a combinação no momento da escolha.
    O que se garante aqui é que a função que ela vai consultar diz a verdade
    para as cores que um cliente realmente escolheria.

    `test_text_over_primary_is_legible_in_both_modes`, já na suíte, cobre o
    mesmo par para UMA marca — a VetPlan. O que falta é a varredura: a cor vem
    de um seletor no painel, e o amarelo que alguém vai escolher amanhã nunca
    passou por teste nenhum.
    """

    #: Cores primárias plausíveis, do azul da MW5 ao verde do Sementes, mais
    #: dois extremos: um amarelo claríssimo e um quase-preto.
    CORES = [
        "#1e40af", "#276b2e", "#872d00", "#0f766e",
        "#b91c1c", "#facc15", "#f8fafc", "#111827",
    ]

    @pytest.mark.parametrize("modo", ["light", "dark"])
    @pytest.mark.parametrize("primaria", CORES)
    def test_o_texto_escolhido_para_a_primaria_e_legivel(self, primaria, modo):
        """`contrast_ratio` aceita string ou `Color` — aqui os tokens já são
        string, e envolvê-los em `Color(...)` seria erro: o construtor pede
        r, g, b separados. De hex se constrói com `Color.from_hex`."""
        tokens = Brand(client_name="Teste", primary=primaria).tokens(modo)
        assert contrast_ratio(tokens["primary"], tokens["on-primary"]) >= 4.5

    @pytest.mark.parametrize("modo", ["light", "dark"])
    @pytest.mark.parametrize("primaria", CORES)
    def test_o_texto_do_corpo_e_legivel_sobre_a_superficie(self, primaria, modo):
        tokens = Brand(client_name="Teste", primary=primaria).tokens(modo)
        assert contrast_ratio(tokens["surface"], tokens["on-surface"]) >= 7.0
```

- [ ] **Step 6: Rodar o teste novo**

Run: `.venv/bin/pytest tests/test_theme.py::TestContrasteDaMarca -v`
Esperado: PASS, 32 testes (8 cores x 2 modos x 2 assercoes).

Os valores medidos contra o `mw5_admin` de origem ficam entre 5.47 e 17.78 — nenhum perto do limite. Este teste falhando e sinal de regressao real na derivacao da paleta, e nao de um limite apertado demais.

Se algum falhar, **não relaxar o limite de 4.5**: é o mínimo da WCAG AA para texto normal. Falha aqui significa que `readable_on` escolhe mal para aquela cor, e o conserto é em `theme/color.py` ou `theme/tokens.py`.

- [ ] **Step 7: Commit**

```bash
git add nucleo/theme tests/test_theme.py
git commit -m "feat: o tema — a cor primaria deriva a paleta inteira

Inclui o teste de contraste da marca, exigido pela spec: nenhuma cor
primaria plausivel produz texto ilegivel, no claro ou no escuro."
```

---

### Task 4: `nucleo/icons.py` — os ícones da casa e a cauda longa

**Files:**
- Create: `nucleo/icons.py`, `nucleo/icons_lucide.json` (de `$FONTE/`)
- Create: `NOTICE`
- Test: `tests/test_icons.py`, `tests/test_busca_de_icones_em_portugues.py`

**Interfaces:**
- Consumes: nada.
- Produces: `nucleo.icons` — módulo com o conjunto próprio (67 ícones) e o do Lucide (~2000), mais a busca em português. É o que `components/primitives.Icon` consome na Task 6.

- [ ] **Step 1: Portar os dois testes**

```bash
FONTE_TESTES=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/tests
cp "$FONTE_TESTES/test_icons.py" tests/test_icons.py
cp "$FONTE_TESTES/test_busca_de_icones_em_portugues.py" tests/test_busca_de_icones_em_portugues.py
sed -i 's/\bmw5_admin\b/nucleo/g' tests/test_icons.py tests/test_busca_de_icones_em_portugues.py
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_icons.py tests/test_busca_de_icones_em_portugues.py -v`
Esperado: erro de coleta — `ImportError: cannot import name 'icons' from 'nucleo'`.

- [ ] **Step 3: Copiar o módulo e o arquivo de desenhos**

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
cp "$FONTE/icons.py" nucleo/icons.py
cp "$FONTE/icons_lucide.json" nucleo/icons_lucide.json
grep -n "mw5_admin\|__file__" nucleo/icons.py
```

O `grep` deve mostrar que o JSON é lido por caminho relativo a `__file__`, que continua correto. Nenhum ajuste.

- [ ] **Step 4: Trazer o aviso de licença junto**

O `icons_lucide.json` é software de terceiros sob licença ISC, e a atribuição viaja com o arquivo. Copiar o `NOTICE` da origem e cortar as seções que não se aplicam a esta entrega:

```bash
FONTE_RAIZ=/home/mw5/projetos/criadordesitesmw5
cp "$FONTE_RAIZ/NOTICE" NOTICE
```

Editar `NOTICE`: no bloco do Lucide, trocar o caminho `packages/mw5_admin/mw5_admin/icons_lucide.json` por `nucleo/icons_lucide.json`, e trocar a menção a `icons.py` do design system por `nucleo/icons.py`. Manter os blocos do htmx e do Cropper.js — os arquivos chegam na Task 9.

- [ ] **Step 5: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_icons.py tests/test_busca_de_icones_em_portugues.py -v`
Esperado: PASS nas duas suítes.

- [ ] **Step 6: Commit**

```bash
git add nucleo/icons.py nucleo/icons_lucide.json NOTICE tests/test_icons.py tests/test_busca_de_icones_em_portugues.py
git commit -m "feat: a biblioteca de icones, com a busca em portugues"
```

---

### Task 5: `nucleo/campos.py` — os tipos de campo de formulário

**Files:**
- Create: `nucleo/campos.py`, `nucleo/descricao.py`, `nucleo/catalogo.py` (de `$FONTE/campos.py`, `$FONTE/descricao.py`, `$FONTE/dados/catalogo.py`)
- Test: `tests/test_campos.py`

**Interfaces:**
- Consumes: `nucleo.rendering.create_environment`, `use_environment` (Task 2). Os testes deste módulo renderizam campos de verdade.
- Produces:
  - `nucleo.campos.Campo` — dataclass do campo
  - `nucleo.campos.TIPOS_DE_CAMPO` — os nove tipos
  - `nucleo.campos.campos_de_json(dados) -> list[Campo]` — leitura tolerante
  - `nucleo.campos.montar_campos(campos, ...)` — o que vira formulário na tela
  - `nucleo.campos.nome_do_campo(...)`
  - `nucleo.descricao.Chamada`, `nucleo.descricao.instanciar`
  - `nucleo.catalogo.procurar(rota)`, `registrar`, `apontam_para`, `esquecer_tudo`

- [ ] **Step 1: Portar o teste**

```bash
FONTE_TESTES=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/tests
cp "$FONTE_TESTES/test_campos.py" tests/test_campos.py
sed -i 's/\bmw5_admin\b/nucleo/g' tests/test_campos.py
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_campos.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'nucleo.campos'`.

- [ ] **Step 3: Copiar os três arquivos e desfazer o único acoplamento**

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
cp "$FONTE/campos.py" nucleo/campos.py
cp "$FONTE/descricao.py" nucleo/descricao.py
cp "$FONTE/dados/catalogo.py" nucleo/catalogo.py
```

`campos.py` tem um import tardio de `from .dados import catalogo`, dentro de `_opcoes_da_relacao`. O pacote `dados/` inteiro é entrega 3; só o `catalogo.py` vem agora, porque é Python puro (a referência a `Resource` está sob `TYPE_CHECKING`). Ajustar o import:

```bash
sed -i 's/^    from \.dados import catalogo$/    from . import catalogo/' nucleo/campos.py
grep -n "import catalogo" nucleo/campos.py
```

Esperado: `    from . import catalogo`.

Com o catálogo vazio — que é o caso em toda esta entrega — `procurar()` devolve `None` e `_opcoes_da_relacao` devolve `([], False)`, o que desabilita o `<select>` em vez de derrubar a tela. É o comportamento que a docstring da função já promete.

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_campos.py -v`
Esperado: os testes que não renderizam passam; os que renderizam um campo falham com `TemplateNotFound`, porque `nucleo/templates/` chega na Task 6.

Marcar a classe ou os testes que falham por `TemplateNotFound` com:

```python
@pytest.mark.xfail(reason="templates chegam na Task 6", strict=True)
```

Rodar de novo. Esperado: 0 FAIL.

- [ ] **Step 5: Commit**

```bash
git add nucleo/campos.py nucleo/descricao.py nucleo/catalogo.py tests/test_campos.py
git commit -m "feat: os tipos de campo de formulario, e o catalogo que a relacao consulta"
```

---

### Task 6: `nucleo/components/` — a biblioteca de componentes

**Files:**
- Create: `nucleo/components/__init__.py`, `primitives.py`, `containers.py`, `data.py`, `forms.py`, `charts.py`, `permissions.py` (de `$FONTE/components/`)
- Create: `nucleo/templates/components/*.html` (52 arquivos, de `$FONTE/templates/components/`)
- Test: `tests/test_components.py`, `tests/test_charts.py`, `tests/test_espacamento_do_formulario.py`

**Interfaces:**
- Consumes: `nucleo.rendering` (Task 2), `nucleo.icons` (Task 4).
- Produces: `nucleo.components` exportando, entre outros — os nomes exatos que `layout.py` e `site.py` importam na Task 8:
  - Contêineres: `Accordion`, `AccordionItem`, `ActionBar`, `Alert`, `Box`, `Card`, `DashedButton`, `Drawer`, `Dropdown`, `DropdownItem`, `EmptyState`, `ErrorState`, `DefinitionList`, `Fact`, `Heading`, `ItemRow`, `Mapa`, `Modal`, `ModuleCard`, `ModuleGrid`, `PageHeader`, `SectionLabel`, `Cell`, `Slot`, `StatCard`, `Step`, `Stepper`, `Summary`, `Tab`, `Tabs`, `Timeline`, `TimelineEvent`, `Toast`
  - Dados: `Column`, `FilterBar`, `Pagination`, `Table`
  - Formulário: `Checkbox`, `FileInput`, `Form`, `FormGrid`, `InputGroup`, `Option`, `SearchInput`, `Select`, `Textarea`, `TextInput`
  - Primitivos: `Avatar`, `Badge`, `Button`, `Icon`, `IconButton`, `Pill`, `Raw`, `Spinner`, `TONES`
  - Gráficos: `Chart`, `DataPoint`, `CHART_KINDS`
  - Permissão: `Protected` (recebe `allowed: bool` já resolvido — não consulta usuário)
  - Constantes de layout: `ALINHAMENTOS`, `DIRECOES`, `ESPACAMENTOS`, `TRANSVERSAIS`, `HOSTS_DE_MAPA`

- [ ] **Step 1: Portar as três suítes**

```bash
FONTE_TESTES=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/tests
cp "$FONTE_TESTES/test_components.py" tests/test_components.py
cp "$FONTE_TESTES/test_charts.py" tests/test_charts.py
cp "$FONTE_TESTES/test_espacamento_do_formulario.py" tests/test_espacamento_do_formulario.py
sed -i 's/\bmw5_admin\b/nucleo/g' tests/test_components.py tests/test_charts.py tests/test_espacamento_do_formulario.py
```

`test_espacamento_do_formulario.py` lê o CSS por caminho de arquivo. Conferir e corrigir o caminho:

```bash
grep -n "Path(" tests/test_espacamento_do_formulario.py
```

Ajustar o caminho apontado para `nucleo/static/nucleo/mw5.css`. O arquivo em si chega na Task 9, então este teste vai ficar xfail até lá.

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_components.py tests/test_charts.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'nucleo.components'`.

- [ ] **Step 3: Copiar o pacote e os templates**

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
cp -r "$FONTE/components" nucleo/components
rm -rf nucleo/components/__pycache__
mkdir -p nucleo/templates
cp -r "$FONTE/templates/components" nucleo/templates/components
grep -rn "mw5_admin" nucleo/components/ || echo "nenhum import absoluto"
ls nucleo/templates/components | wc -l
```

Esperado: `51` templates, e nenhum import absoluto — os componentes usam `from ..rendering import ...` e `from .. import icons`.

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_components.py tests/test_charts.py -v`
Esperado: PASS nas duas suítes.

- [ ] **Step 5: Tirar o xfail do teste de ambiente da Task 2**

Agora que `nucleo/templates/` existe, remover a marca `@pytest.mark.xfail` de `test_o_ambiente_acha_os_templates_do_pacote` em `tests/test_rendering.py`, e as marcas de `TemplateNotFound` em `tests/test_campos.py`.

Run: `.venv/bin/pytest tests/ -v`
Esperado: PASS em tudo, exceto `test_espacamento_do_formulario.py`, que ainda espera o `mw5.css` da Task 9. Deixá-lo marcado como xfail com `reason="mw5.css chega na Task 9"`.

- [ ] **Step 6: Commit**

```bash
git add nucleo/components nucleo/templates/components tests/
git commit -m "feat: a biblioteca de componentes e os 52 templates"
```

---

### Task 7: `nucleo/permissoes.py` — quem está logado e o que pode

**Files:**
- Create: `nucleo/permissoes.py` (de `$FONTE/auth/models.py`, mais uma constante de `$FONTE/auth/backend.py`)
- Test: `tests/test_permissoes.py` (recorte de `$FONTE_TESTES/test_auth.py`)

**Interfaces:**
- Consumes: nada.
- Produces:
  - `nucleo.permissoes.User` — dataclass frozen: `id: str`, `name: str`, `login: str = ""`, `role_label: str = ""`, `avatar: str = ""`, `superuser: bool = False`, `permissions: frozenset[str]`. Propriedades `display_name`, `first_name`.
  - `nucleo.permissoes.pode(user: User | None, permission: str) -> bool` — `None` nunca pode; permissão vazia libera; superusuário passa em tudo; `modulo.*` cobre `modulo.acao`.
  - `nucleo.permissoes.NivelDeContexto` — `nivel: int`, `rotulo: str`, `atual: str`, `opcoes: list[OpcaoDeContexto]`
  - `nucleo.permissoes.OpcaoDeContexto` — `valor: str`, `rotulo: str`
  - `nucleo.permissoes.SENHA_MINIMA = 8`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_permissoes.py`:

```python
"""O que a pessoa pode, do ponto de vista de quem desenha a tela.

O `contas/` da entrega 2 vai produzir estes objetos a partir da base do
Django. O que se garante aqui é a regra, e ela é independente de onde a
pessoa veio: LDAP, Oracle do cliente ou tabela nossa.
"""

import pytest

from nucleo.permissoes import SENHA_MINIMA, NivelDeContexto, OpcaoDeContexto, User, pode


class TestOQueAPessoaPode:
    def test_ninguem_deslogado_pode_coisa_nenhuma(self):
        assert pode(None, "frete.ver") is False

    def test_permissao_vazia_libera_para_quem_entrou(self):
        assert pode(User(id="1", name="Ana"), "") is True

    def test_permissao_vazia_nao_libera_para_quem_nao_entrou(self):
        assert pode(None, "") is False

    def test_a_permissao_exata_vale(self):
        ana = User(id="1", name="Ana", permissions={"frete.ver"})
        assert pode(ana, "frete.ver") is True

    def test_permissao_de_outro_modulo_nao_vale(self):
        ana = User(id="1", name="Ana", permissions={"frete.ver"})
        assert pode(ana, "vendas.ver") is False

    def test_o_coringa_do_modulo_cobre_a_acao(self):
        gestor = User(id="2", name="Bruno", permissions={"frete.*"})
        assert pode(gestor, "frete.editar") is True

    def test_o_coringa_cobre_a_acao_criada_amanha(self):
        """A razão de o coringa existir: `frete.exportar` ainda não foi escrita
        em perfil nenhum, e quem tem o módulo inteiro já a tem."""
        gestor = User(id="2", name="Bruno", permissions={"frete.*"})
        assert pode(gestor, "frete.exportar") is True

    def test_quem_marcou_acao_por_acao_nao_ganha_a_acao_nova(self):
        apertado = User(
            id="3", name="Célia",
            permissions={"frete.ver", "frete.editar", "frete.remover"},
        )
        assert pode(apertado, "frete.exportar") is False

    def test_superusuario_passa_em_tudo(self):
        raiz = User(id="4", name="MW5", superuser=True)
        assert pode(raiz, "qualquer.coisa") is True


class TestOUsuario:
    def test_as_permissoes_congelam_na_construcao(self):
        ana = User(id="1", name="Ana", permissions=["frete.ver"])
        assert isinstance(ana.permissions, frozenset)
        with pytest.raises(AttributeError):
            ana.permissions.add("frete.editar")

    def test_o_primeiro_nome_sai_do_nome_inteiro(self):
        assert User(id="1", name="Ana Paula Souza").first_name == "Ana"

    def test_nome_em_branco_nao_derruba_o_primeiro_nome(self):
        assert User(id="1", name="   ").first_name == ""


class TestContexto:
    def test_um_nivel_carrega_as_opcoes_e_a_atual(self):
        nivel = NivelDeContexto(
            nivel=2, rotulo="Filial", atual="3",
            opcoes=[OpcaoDeContexto("3", "Campinas"),
                    OpcaoDeContexto("7", "Ribeirão Preto")],
        )
        assert nivel.atual == "3"
        assert [o.rotulo for o in nivel.opcoes] == ["Campinas", "Ribeirão Preto"]


def test_a_senha_minima_e_de_oito():
    assert SENHA_MINIMA == 8
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_permissoes.py -v`
Esperado: FAIL — `ModuleNotFoundError: No module named 'nucleo.permissoes'`.

- [ ] **Step 3: Copiar e acrescentar a constante**

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
cp "$FONTE/auth/models.py" nucleo/permissoes.py
```

Editar `nucleo/permissoes.py`: acrescentar ao `__all__` o nome `SENHA_MINIMA`, e logo abaixo dos imports:

```python
#: O tamanho mínimo de uma senha. Mora aqui, e não em `contas/`, porque a tela
#: de perfil (`layout.PerfilPage`) precisa dele para escrever a dica ao lado do
#: campo — e o layout não pode depender de um app que ainda nem existe.
SENHA_MINIMA = 8
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_permissoes.py -v`
Esperado: PASS, 14 testes.

- [ ] **Step 5: Commit**

```bash
git add nucleo/permissoes.py tests/test_permissoes.py
git commit -m "feat: o usuario logado e a regra de permissao, com o coringa por modulo"
```

---

### Task 8: `nucleo/layout.py` e `nucleo/site.py` — o shell da tela

**Files:**
- Create: `nucleo/layout.py`, `nucleo/site.py` (de `$FONTE/layout.py`, `$FONTE/site.py`)
- Create: `nucleo/templates/layout/*.html` (8 arquivos, de `$FONTE/templates/layout/`)
- Test: `tests/test_layout.py`

**Interfaces:**
- Consumes: `nucleo.components` (Task 6), `nucleo.permissoes.pode` e `SENHA_MINIMA` (Task 7), `nucleo.theme.Brand` (Task 3).
- Produces:
  - `nucleo.layout.NavItem`, `Crumb`, `Breadcrumb`, `UserInfo`, `Sidebar`, `Header`, `Footer`, `Page`, `LoginPage`, `PerfilPage`, `ContextSwitcher`, `ContextLevel`, `ContextOption`
  - `nucleo.site.Site` — dataclass. Campos: `brand: Brand`, `nav: Sequence[NavItem]`, `home_href="/"`, `logout_href="/sair"`, `account_href="/perfil"`, `show_notifications=True`, `stylesheets: list[str]`, `scripts: list[str]`, `theme_href`, `context_line`, `can`.
  - `Site.page(*, title, content, path="/", crumbs=(), user=None, width="wide", action_bar="", overlays="", toasts=(), chrome=True, scripts=(), stylesheets=()) -> Page` — monta a página inteira. `chrome=False` derruba sidebar, header e rodapé; é o que a tela de login usa.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_layout.py`:

```python
"""O shell: a tela não constrói sidebar nem header, ela os recebe.

É esta indireção que garante que as 20 instalações desenham o mesmo shell —
uma tela não tem como recriar o cabeçalho, porque não o constrói.
"""

import pytest

from nucleo.layout import Crumb, NavItem
from nucleo.permissoes import User
from nucleo.rendering import create_environment, use_environment
from nucleo.site import Site
from nucleo.theme import Brand


@pytest.fixture(autouse=True)
def ambiente():
    with use_environment(create_environment()):
        yield


@pytest.fixture
def site():
    return Site(
        brand=Brand(client_name="Teste", system_name="Portal de Teste",
                    primary="#1e40af"),
        nav=[
            NavItem("Início", "home", "/"),
            NavItem("Frete", "truck", "/frete", permission="frete.ver"),
            NavItem("Usuários", "users", "/usuarios", permission="usuarios.ver"),
        ],
    )


class TestOShell:
    def test_a_pagina_traz_sidebar_header_e_rodape(self, site):
        html = str(site.page(title="Início", content="miolo").render())
        assert "miolo" in html
        assert "Portal de Teste" in html

    def test_sem_chrome_o_shell_nao_e_desenhado(self, site):
        """A tela de login é a única situação em que o shell não se aplica."""
        com = str(site.page(title="x", content="miolo").render())
        sem = str(site.page(title="x", content="miolo", chrome=False).render())
        assert len(sem) < len(com)
        assert "miolo" in sem

    def test_o_titulo_da_tela_aparece(self, site):
        html = str(site.page(title="Simulador de Frete", content="").render())
        assert "Simulador de Frete" in html

    def test_a_trilha_aparece_quando_informada(self, site):
        html = str(site.page(
            title="KM Padrão", content="",
            crumbs=[Crumb("Consultas", "/consultas"), Crumb("KM Padrão", "")],
        ).render())
        assert "Consultas" in html


class TestOMenuFiltraPorPermissao:
    def test_quem_nao_tem_a_permissao_nao_ve_o_item(self, site):
        ana = User(id="1", name="Ana", permissions={"frete.ver"})
        html = str(site.page(title="x", content="", user=ana).render())
        assert "/frete" in html
        assert "/usuarios" not in html

    def test_item_sem_permissao_declarada_aparece_para_quem_entrou(self, site):
        ana = User(id="1", name="Ana", permissions=set())
        html = str(site.page(title="x", content="", user=ana).render())
        assert "Início" in html

    def test_superusuario_ve_tudo(self, site):
        raiz = User(id="9", name="MW5", superuser=True)
        html = str(site.page(title="x", content="", user=raiz).render())
        assert "/frete" in html
        assert "/usuarios" in html

    def test_sem_usuario_nenhum_item_com_permissao_aparece(self, site):
        """O padrão de `Site.can` é a checagem real, e não um 'mostra tudo':
        esquecer de ligar a auth não pode virar vazamento de menu."""
        html = str(site.page(title="x", content="", user=None).render())
        assert "/frete" not in html
        assert "/usuarios" not in html


class TestOTema:
    def test_a_folha_de_tema_e_referenciada_no_caminho_configurado(self, site):
        site.theme_href = "/tema.css"
        html = str(site.page(title="x", content="").render())
        assert "/tema.css" in html
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_layout.py -v`
Esperado: erro de coleta — `ModuleNotFoundError: No module named 'nucleo.layout'`.

- [ ] **Step 3: Copiar os dois módulos e os templates de layout**

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
cp "$FONTE/layout.py" nucleo/layout.py
cp "$FONTE/site.py" nucleo/site.py
cp -r "$FONTE/templates/layout" nucleo/templates/layout
ls nucleo/templates/layout | wc -l
```

Esperado: `8` templates.

- [ ] **Step 4: Redirecionar os dois imports de `auth`**

`site.py` importa `pode` no topo; `layout.py` importa `SENHA_MINIMA` num import tardio, dentro de `PerfilPage`. Ambos apontam para o pacote `auth` que não foi portado.

```bash
sed -i 's/^from \.auth import pode$/from .permissoes import pode/' nucleo/site.py
sed -i 's/^        from \.auth import SENHA_MINIMA$/        from .permissoes import SENHA_MINIMA/' nucleo/layout.py
grep -rn "\.auth" nucleo/site.py nucleo/layout.py || echo "nenhuma referencia a auth restante"
```

Esperado: a última linha imprime `nenhuma referencia a auth restante`.

- [ ] **Step 5: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_layout.py -v`
Esperado: PASS, 9 testes (4 em TestOShell, 4 em TestOMenuFiltraPorPermissao, 1 em TestOTema).

- [ ] **Step 6: Rodar a suíte inteira**

Run: `.venv/bin/pytest tests/ -v`
Esperado: tudo PASS, com `test_espacamento_do_formulario.py` ainda em xfail.

- [ ] **Step 7: Commit**

```bash
git add nucleo/layout.py nucleo/site.py nucleo/templates/layout tests/test_layout.py
git commit -m "feat: o shell — sidebar, header, rodape e a montagem da pagina

O menu filtra por permissao no padrao, e nao por 'mostra tudo': esquecer
de ligar a auth quebra o teste em vez de vazar item de menu."
```

---

### Task 9: Estáticos e a rota do tema

**Files:**
- Create: `nucleo/static/nucleo/mw5.css`, `mw5.js`, `mw5-recorte.js`, `htmx.min.js`, `cropper.min.js`, `cropper.min.css` (de `$FONTE/static/`)
- Create: `nucleo/views.py`, `nucleo/urls.py`
- Modify: `config/urls.py`
- Test: `tests/test_estaticos.py`, `tests/test_espacamento_do_formulario.py`, `tests/test_mascaras.py`

**Interfaces:**
- Consumes: `nucleo.theme.render_theme_css` (Task 3), `nucleo.site.Site` (Task 8).
- Produces:
  - `nucleo.views.tema_css(request) -> HttpResponse` — devolve o CSS gerado, `content_type="text/css"`, `Cache-Control: no-cache`.
  - Rota nomeada `tema` em `/tema.css`.
  - `nucleo.views.SITE` — o `Site` de demonstração usado pelas views desta entrega. É provisório e some na entrega 3, quando o `Site` passa a ser montado a partir do banco.

- [ ] **Step 1: Copiar os estáticos**

```bash
FONTE=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin
mkdir -p nucleo/static/nucleo
cp "$FONTE/static/"* nucleo/static/nucleo/
ls nucleo/static/nucleo
```

Esperado: `cropper.min.css cropper.min.js htmx.min.js mw5-recorte.js mw5.css mw5.js`.

- [ ] **Step 2: Escrever o teste que falha**

Criar `tests/test_estaticos.py`:

```python
"""A folha de tema é gerada na requisição, e os estáticos levam versão na URL.

O tema não é compilado de propósito: trocar a cor de um cliente é gravar no
banco e recarregar. Se ele virasse arquivo, mudar de cor exigiria publicar
versão nova — e a spec fecha o contrário disso.
"""

import re

import pytest
from django.test import Client
from django.urls import reverse

from nucleo.rendering import create_environment, use_environment


@pytest.fixture(autouse=True)
def ambiente():
    with use_environment(create_environment()):
        yield


class TestAFolhaDeTema:
    def test_a_rota_do_tema_responde_css(self):
        resposta = Client().get(reverse("tema"))
        assert resposta.status_code == 200
        assert resposta["Content-Type"].startswith("text/css")

    def test_o_css_traz_as_custom_properties_da_marca(self):
        corpo = Client().get(reverse("tema")).content.decode()
        assert "--primary:" in corpo
        assert ":root{" in corpo

    def test_o_css_traz_a_camada_do_modo_escuro(self):
        corpo = Client().get(reverse("tema")).content.decode()
        assert ':root[data-theme="dark"]' in corpo

    def test_o_navegador_e_proibido_de_guardar_a_folha(self):
        """Tema gerado e navegador guardando dão o pior par possível: a cor
        muda no banco e o cliente continua vendo a de ontem."""
        resposta = Client().get(reverse("tema"))
        assert resposta["Cache-Control"] == "no-cache"


class TestAVersaoNaURLDoEstatico:
    def test_o_css_do_design_system_sai_com_versao(self):
        env = create_environment()
        url = env.globals["estatico"]("mw5.css")
        assert re.fullmatch(r"/static/nucleo/mw5\.css\?v=\d+", url)

    def test_arquivo_inexistente_sai_sem_versao_em_vez_de_derrubar(self):
        """A pagina tem que abrir mesmo com um caminho torto: um estatico que
        sumiu nao pode derrubar a tela inteira."""
        env = create_environment()
        assert env.globals["estatico"]("nao-existe.css") == "/static/nucleo/nao-existe.css"
```

- [ ] **Step 3: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_estaticos.py -v`
Esperado: FAIL — `NoReverseMatch: Reverse for 'tema' not found`.

- [ ] **Step 4: Escrever `nucleo/views.py`**

```python
"""As views do núcleo: a folha de tema e a tela de demonstração.

O `SITE` daqui é provisório. Na entrega 3 o `Site` passa a ser montado a partir
do banco da instalação — marca, módulos ligados e ajustes de menu. Enquanto
isso, ele existe para que haja o que desenhar.
"""

from __future__ import annotations

from django.http import HttpResponse

from .site import Site
from .theme import Brand, render_theme_css

__all__ = ["SITE", "tema_css"]

MARCA = Brand(
    client_name="KRONOS.net",
    system_name="KRONOS.net",
    primary="#1e40af",
    accent="#872d00",
)

SITE = Site(brand=MARCA, theme_href="/tema.css")


def tema_css(request) -> HttpResponse:
    """A folha de tema do cliente, gerada na requisição.

    `no-cache` porque o conteúdo muda quando alguém mexe na cor, e não quando
    um arquivo é publicado: um navegador que guarda esta folha mostra a cor de
    ontem sem nenhum sinal de que está errado.
    """
    resposta = HttpResponse(render_theme_css(SITE.brand), content_type="text/css")
    resposta["Cache-Control"] = "no-cache"
    return resposta
```

- [ ] **Step 5: Escrever `nucleo/urls.py` e ligá-lo ao projeto**

Criar `nucleo/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("tema.css", views.tema_css, name="tema"),
]
```

Substituir `config/urls.py` por:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("nucleo.urls")),
]
```

- [ ] **Step 6: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_estaticos.py -v`
Esperado: PASS, 6 testes.

- [ ] **Step 7: Tirar o xfail do espaçamento e portar as máscaras**

```bash
FONTE_TESTES=/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/tests
cp "$FONTE_TESTES/test_mascaras.py" tests/test_mascaras.py
sed -i 's/\bmw5_admin\b/nucleo/g' tests/test_mascaras.py
grep -n "Path(" tests/test_mascaras.py
```

Ajustar o caminho do `mw5.js` para `nucleo/static/nucleo/mw5.js`. Remover o `@pytest.mark.xfail` de `tests/test_espacamento_do_formulario.py`.

Run: `.venv/bin/pytest tests/test_mascaras.py tests/test_espacamento_do_formulario.py -v`
Esperado: PASS. `test_mascaras.py` pula os testes que precisam de `node` se ele não estiver instalado — a mensagem é `sem node: esta garantia fica sem guarda`, e pular aqui é aceitável.

- [ ] **Step 8: Commit**

```bash
git add nucleo/static nucleo/views.py nucleo/urls.py config/urls.py tests/
git commit -m "feat: os estaticos do design system e a folha de tema gerada na requisicao"
```

---

### Task 10: A tela de demonstração

**Files:**
- Modify: `nucleo/views.py`
- Modify: `nucleo/urls.py`
- Test: `tests/test_demonstracao.py`

**Interfaces:**
- Consumes: tudo das tarefas anteriores.
- Produces: rota nomeada `demonstracao` em `/`, que desenha uma página com todos os componentes do design system dentro do shell.

Esta é a tarefa que fecha o critério de pronto da entrega: uma tela do KRONOS.net visualmente equivalente à de `sementes-premix`, sem CSS escrito à mão.

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_demonstracao.py`:

```python
"""A tela que prova a entrega: todo componente desenhando dentro do shell.

Ela não é decorativa. É o que se abre no navegador para comparar lado a lado
com o `sementes-premix`, e é o que quebra quando um componente portado perde
o template pelo caminho.
"""

import pytest
from django.test import Client
from django.urls import reverse


@pytest.fixture
def html():
    resposta = Client().get(reverse("demonstracao"))
    assert resposta.status_code == 200
    return resposta.content.decode()


class TestATelaDesenha:
    def test_a_pagina_abre(self, html):
        assert "<html" in html.lower()

    def test_o_shell_esta_em_volta(self, html):
        assert "KRONOS.net" in html

    def test_a_folha_de_tema_e_carregada(self, html):
        assert "/tema.css" in html

    def test_o_css_do_design_system_e_carregado_com_versao(self, html):
        assert "/static/nucleo/mw5.css?v=" in html


class TestOsComponentesAparecem:
    """Um por família, pelo texto que a tela mostra.

    Pelo texto, e não pela classe CSS: o nome de uma classe é detalhe interno
    do template, e um teste preso a ele quebra numa renomeação que não mudou
    nada para quem olha a tela. Se um template sumiu no porte, a renderização
    levanta antes de chegar aqui — o valor deste teste é dizer qual família.
    """

    @pytest.mark.parametrize(
        "familia,texto",
        [
            ("PageHeader", "O design system inteiro, numa tela"),
            ("StatCard", "Instalações"),
            ("Alert", "Um aviso de atenção."),
            ("Pill", "Ativo"),
            ("Badge", "3"),
            ("Avatar", "Ana Paula"),
            ("Button", "Primário"),
            ("Table", "Ribeirão Preto"),
            ("Tabs", "Conteúdo da primeira."),
            ("Timeline", "Há dois dias"),
            ("EmptyState", "Nenhum registro ainda."),
            ("Modal", "O conteúdo do modal."),
        ],
    )
    def test_a_familia_aparece_na_tela(self, html, familia, texto):
        assert texto in html, f"{familia} não desenhou"

    def test_o_card_desenha_a_moldura(self, html):
        """Uma asserção estrutural, para o caso de o texto aparecer solto na
        página porque o `Card` em volta parou de renderizar."""
        assert 'class="card' in html


class TestOsDoisTemas:
    def test_o_css_serve_claro_e_escuro(self):
        corpo = Client().get(reverse("tema")).content.decode()
        assert ':root[data-theme="light"]' in corpo
        assert ':root[data-theme="dark"]' in corpo

    def test_a_tela_tem_o_botao_de_alternar_tema(self, html):
        assert "data-theme" in html
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `.venv/bin/pytest tests/test_demonstracao.py -v`
Esperado: FAIL — `NoReverseMatch: Reverse for 'demonstracao' not found`.

- [ ] **Step 3: Escrever a view de demonstração**

Acrescentar a `nucleo/views.py`:

```python
from .components import (
    Alert, Avatar, Badge, Box, Button, Card, Column, EmptyState, Modal,
    PageHeader, Pill, StatCard, Tab, Table, Tabs, Timeline, TimelineEvent,
)
from .layout import Crumb, NavItem
from .permissoes import User
from .rendering import create_environment, use_environment
from .resposta import render as render_componente

#: O menu da demonstração. Escrito à mão de propósito e só aqui: na entrega 3
#: o menu passa a ser montado a partir dos módulos ligados no banco, e este
#: bloco some junto com o `SITE` acima.
NAV_DEMO = [
    NavItem("Início", "home", "/"),
    NavItem("Componentes", "grid", "/"),
]

VISITANTE = User(id="0", name="Ana Paula Souza", role_label="Demonstração",
                 superuser=True)


def _miolo():
    """Todo componente do design system, uma vez cada.

    Os nomes de parâmetro saem das dataclasses de `components/`: o corpo de um
    contêiner é `body`, não `children`; o texto de um `Alert` é `message`; o de
    um `Pill` e de um `Badge` é `label`. As variantes de `Button` são as quatro
    de `Button.VARIANTS` — `default`, `primary`, `ghost`, `danger`. Os tons são
    os cinco de `TONES` — `neutral`, `ok`, `info`, `warn`, `danger`.
    """
    return [
        PageHeader(title="Componentes",
                   subtitle="O design system inteiro, numa tela"),
        Card(title="Números", body=Box(body=[
            StatCard(label="Instalações", value="20"),
            StatCard(label="Módulos", value="7"),
        ])),
        Card(title="Avisos", body=[
            Alert(message="Um aviso informativo.", tone="info"),
            Alert(message="Um aviso de atenção.", tone="warn"),
            Alert(message="Um aviso de erro.", tone="danger"),
        ]),
        Card(title="Marcadores", body=Box(body=[
            Pill(label="Ativo", tone="ok"),
            Badge(label="3"),
            Avatar(name="Ana Paula"),
        ])),
        Card(title="Ações", body=Box(body=[
            Button(label="Primário", variant="primary"),
            Button(label="Comum"),
            Button(label="Discreto", variant="ghost"),
            Button(label="Remover", variant="danger"),
        ])),
        Card(title="Tabela", padded=False, body=Table(
            columns=[Column("cidade", "Cidade"), Column("uf", "UF")],
            rows=[{"cidade": "Campinas", "uf": "SP"},
                  {"cidade": "Ribeirão Preto", "uf": "SP"}],
        )),
        Card(title="Abas", body=Tabs(tabs=[
            Tab(label="Uma", body="Conteúdo da primeira.", active=True),
            Tab(label="Outra", body="Conteúdo da segunda."),
        ])),
        Card(title="Linha do tempo", body=Timeline(events=[
            TimelineEvent(label="Criado", when="Há dois dias", state="done"),
            TimelineEvent(label="Aprovado", when="Ontem"),
        ])),
        Card(title="Vazio", body=EmptyState(
            title="Nada por aqui", message="Nenhum registro ainda.")),
    ]


def demonstracao(request):
    """A tela que prova a entrega 1."""
    env = create_environment()
    with use_environment(env):
        SITE.nav = NAV_DEMO
        pagina = SITE.page(
            title="Componentes",
            content=_miolo(),
            crumbs=[Crumb("Núcleo", "/"), Crumb("Componentes")],
            user=VISITANTE,
            overlays=Modal(id="exemplo", title="Um modal",
                           body="O conteúdo do modal."),
        )
    return render_componente(pagina)
```

Se algum parâmetro divergir, o componente levanta `TypeError` na construção e o teste aponta a linha. A lista completa dos campos de cada dataclass sai de:

```bash
grep -n "^class \|^    [a-z_]*:" nucleo/components/containers.py nucleo/components/primitives.py
```

- [ ] **Step 4: Registrar a rota**

Em `nucleo/urls.py`:

```python
urlpatterns = [
    path("", views.demonstracao, name="demonstracao"),
    path("tema.css", views.tema_css, name="tema"),
]
```

- [ ] **Step 5: Rodar e verificar que passa**

Run: `.venv/bin/pytest tests/test_demonstracao.py -v`
Esperado: PASS.

- [ ] **Step 6: Abrir no navegador e comparar**

```bash
.venv/bin/python manage.py runserver 8000
```

Abrir `http://127.0.0.1:8000/`. Conferir a olho, contra as telas do `sementes-premix`:

1. A barra lateral tem a largura e o espaçamento do padrão.
2. O cabeçalho traz logo e título. **Não** procure botão de alternar tema: o design system removeu esse seletor deliberadamente, e `test_nao_ha_mais_botao_de_tema` garante a ausência dele (`Header` não tem campo `theme_toggle`, e nenhum template emite `data-theme-toggle`). Para conferir o item 3, alterne pelo atributo `data-theme` no elemento raiz.
3. Alternar para escuro muda a tela inteira, sem nenhum trecho preso no claro.
4. Estreitar a janela abaixo de 820px recolhe a barra lateral.
5. Nenhum erro no console do navegador.

Item que falhar vira correção **no componente ou no token**, nunca CSS solto na view — a regra 3 da spec vale aqui.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `.venv/bin/pytest tests/ -v`
Esperado: tudo PASS, nenhum xfail restante além dos skips por ausência de `node`.

- [ ] **Step 8: Commit**

```bash
git add nucleo/views.py nucleo/urls.py tests/test_demonstracao.py
git commit -m "feat: a tela de demonstracao — todo componente dentro do shell

Fecha a entrega 1: uma tela do KRONOS.net sai equivalente a do
sementes-premix, sem CSS escrito a mao."
```

---

## Critério de pronto da entrega

- `.venv/bin/pytest tests/` verde, sem xfail.
- `http://127.0.0.1:8000/` desenha todos os componentes dentro do shell, em claro e escuro.
- Nenhum arquivo `.py` ou `.html` fora de `nucleo/theme/brand.py` contém cor, fonte ou caminho de logo. Conferir com:

```bash
grep -rn "#[0-9a-fA-F]\{6\}" nucleo/ --include=*.py --include=*.html \
  | grep -v "nucleo/theme/brand.py" \
  | grep -v "nucleo/icons_lucide.json"
```

Esperado: nenhuma linha. Exceções legítimas a documentar caso apareçam: valores
dentro de `nucleo/theme/tokens.py`, que é onde a derivação da paleta mora, e os
dois defaults de `readable_on` em `nucleo/theme/color.py:246-247`
(`light="#ffffff"`, `dark="#101014"`) — a opção de texto legível quando nenhuma
cor de marca foi passada, não uma cor de marca em si.

## O que esta entrega deliberadamente não faz

- Não tem model, não tem migração, não tem banco. `contas/` é entrega 2; `plataforma/` é entrega 3.
- A marca vem de um `Brand` escrito em `views.py`. A tabela `marca` e a tela de Aparência são entrega 3.
- O menu é uma lista escrita à mão na view de demonstração. A montagem a partir dos módulos ligados é entrega 3.
- Não há login. `VISITANTE` é um `User` construído na mão para a demonstração desenhar.
- `dados/resource.py` e `dados/sql.py` não foram portados: o CRUD declarativo sobre o ORM do Django é entrega 3.
