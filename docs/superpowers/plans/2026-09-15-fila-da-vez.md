# Fila da vez (entrega 1) — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pôr a fila da vez das lojas da Sylvia Design na tela de cada vendedor (`/fila`), gravando ponto, atendimentos, vendas por grupo, não vendas com motivo e pausas, com as correções do gerente e os três cadastros no dashboard.

**Architecture:** um app de negócio `fila/` por cima da base. As regras moram em funções de domínio (`fila/acoes.py` para o vendedor, `fila/correcoes.py` para o gerente) que trancam a linha da `Filial` com `select_for_update` e recusam com uma frase (`Recusa`). A página `/fila` é HTML do servidor (Jinja, ambiente próprio do app) que funciona sem JavaScript; o JavaScript só consulta `GET /fila/estado` a cada 3 s e troca os pedaços de HTML quando a versão muda, e manda as ações por `fetch`.

**Tech Stack:** Django 5.2, Python 3.13, Postgres 16, Jinja2 (`nucleo`), JavaScript sem biblioteca, CSS próprio.

**Spec:** `docs/superpowers/specs/2026-09-15-fila-da-vez-design.md`

## Global Constraints

- Tudo em português do Brasil: código, comentário, mensagem de commit, frase de tela. Comentário diz POR QUÊ, em frase inteira.
- Commit: `git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit`. **Nunca** `Co-Authored-By`, nunca rodapé de "gerado com". Mensagem longa, com `feat:`/`fix:`/`test:`/`docs:`, dizendo o que faltava e por que é assim.
- Teste com dente: todo teste novo é visto VERMELHO uma vez, quebrando o código de propósito, antes de valer. O passo "quebre e veja falhar" está escrito em cada tarefa; não pule.
- Nada de produção, servidor, FTP, credencial ou `git push`.
- Não usar Playwright nem navegador; tela se confere com `django.test.Client`.
- Nunca rodar duas suítes `pytest` ao mesmo tempo. Suíte inteira (~2 min) em segundo plano. Não usar `pkill -f`.
- Todo model da fila herda `contas.inquilino.ModeloDaEmpresa` (que já traz `ComGuid`). Tela lê por `Model.objects.da_empresa(...)`; `irrestritos` só dentro de `fila/acoes.py`/`fila/correcoes.py` onde o comentário diz por quê.
- Guardas de toda view: `@exigir_permissao(...)` por fora, `@exigir_modulo_ligado("fila")` por dentro.
- Permissões (com o desvio D-1 abaixo): `fila.ver`, `fila.participar`, `fila.gerenciar`, `fila.cadastros`.
- Portas do Fila Zero: banco `127.0.0.1:5436`, app `8005`. Marca `"Fila Zero"`. `pyproject` `fila-zero`. Imagem `ghcr.io/mw5-software/fila-zero`.
- Paleta da página `/fila` (fixa, não vem da marca): Concreto `#ECEEED` (fundo), Grafite `#1E2530` (texto), Veludo `#0E4F54` (na fila), Latão `#B5893A` ("é a sua vez"/atendendo, a única cor quente), Ardósia `#6B7480` (pausa e texto secundário), Venda `#2F7A4B` (confirmação de venda). Estado sempre com rótulo + ícone, nunca só cor.
- Tipos: Bricolage Grotesque (auto-hospedada; número da posição, "É a sua vez", total; algarismos tabulares) e Plus Jakarta Sans (texto; já está em `plataforma/static/plataforma/fontes/`).
- A página `/fila` não tem `<table>` (R46 vale para tabela; a fila é lista).

**Comando de teste** (a partir de `/home/mw5/projetos/fila-zero-app`; o banco é o container do Portal, base `fila_zero`):

```bash
PATH=/home/mw5/projetos/portal-de-vendas/.superpowers/pgbin:$PATH DJANGO_DEBUG=1 \
KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/fila_zero \
.venv/bin/python -m pytest -q -p no:warnings <alvo>
```

Abaixo, `$PYTEST <alvo>` abrevia essa linha inteira.

## Desvios do spec, decididos aqui

- **D-1 — nasce `fila.ver`.** O menu da base (`plataforma/menu.py`, `_entradas_do_modulo`) põe o módulo na barra pela PRIMEIRA permissão declarada e some com os atalhos de quem não a tem. Com `fila.participar` na frente, o Supervisor (só `fila.gerenciar`) não teria link para `/fila` e quem tivesse só `fila.cadastros` não veria os cadastros. `fila.ver` ("vê a fila da loja") vem primeiro e é dada a todo cargo que tem qualquer permissão da fila. `/fila` e `/fila/estado` exigem `fila.ver`; bater o ponto e agir exigem `fila.participar`; corrigir exige `fila.gerenciar`. O teste "sem `fila.participar` a página responde 404" do spec vira "sem `fila.ver` responde 404, e com `fila.ver` sem `fila.participar` a página abre sem os botões de ponto". Custo se errado: uma permissão a mais na tela de Cargos.
- **D-2 — a trava é a linha da `Filial`, e não as linhas de `LugarNaFila`.** Loja sem ninguém não tem linha de `LugarNaFila` para trancar, e dois pontos simultâneos da mesma pessoa passariam juntos. A linha da filial sempre existe. Ponto que troca de loja tranca as duas, em ordem de `pk`, para não haver impasse.
- **D-3 — ninguém corrige a si mesmo.** O gerente também participa da fila; corrigir o próprio lançamento seria o vendedor corrigindo a si mesmo, que o spec proíbe. Mesma regra de `contas.lugar.pode_administrar`.
- **D-4 — quem "só tem a fila" cai em `/fila`.** "Só `fila.participar`" vira: não é superusuário, tem `fila.participar`, e todas as permissões estão em `{fila.ver, fila.participar}`. A raiz `/` passa por `fila.views.inicio`, registrada antes de `nucleo.urls`.
- **D-5 — remover usuário com histórico.** `Presenca`, `Atendimento` e `Pausa` apontam para o usuário com `PROTECT`. A tela de Usuários passa a responder a `ProtectedError` com frase ("tem histórico gravado; desative em vez de remover") em vez de 500.

## Arquivos

```
fila/__init__.py
fila/apps.py                 AppConfig, registra o módulo no ready()
fila/modulo.py               ModuloSpec "fila" com os atalhos dos cadastros
fila/models.py               cadastros, Presenca, LugarNaFila, Atendimento, ItemVendido, Pausa
fila/migrations/0001_initial.py
fila/acoes.py                Recusa, Lancamento, ItemLancado; as ações do vendedor
fila/estado.py               ordem, posição, versão e o retrato da fila de uma loja
fila/correcoes.py            as correções do gerente, com auditoria
fila/valores.py              ler_valor("1.234,56") -> Decimal
fila/ambiente.py             ambiente Jinja do app, guardado por processo
fila/tela.py                 monta o contexto e os pedaços de HTML da página
fila/views.py                inicio, fila, estado, agir
fila/views_cadastros.py      as três telas de cadastro (R46)
fila/urls.py
fila/templates/fila/pagina.html, _painel.html, _lista.html, _barra.html,
                    _folhas.html, _lancamentos.html, sem_loja.html
fila/static/fila/fila.css, fila.js, fontes/bricolage.woff2, fontes/OFL.txt
tests/fila_cenario.py        montagem de cenário (não é arquivo de teste)
tests/test_fila_modulo.py, test_fila_modelos.py, test_fila_acoes.py,
tests/test_fila_concorrencia.py, test_fila_estado.py, test_fila_correcoes.py,
tests/test_fila_cadastros.py, test_fila_pagina.py
```

Modificados: `config/settings.py`, `config/urls.py`, `contas/fabrica.py`, `contas/cargos_de_fabrica.py`, `contas/views_usuarios.py`, `comum/auditoria.py`, `plataforma/marca.py`, `pyproject.toml`, `docker-compose.yml`, `.github/workflows/publicar-imagem.yml`, `deploy/docker-compose.vps.yml`, as varreduras que listam pastas, `tests/test_auditoria.py`, `CLAUDE.md`, `README.md`, `locale/es/LC_MESSAGES/django.po`.

---
### Task 1: A identidade do Fila Zero e o esqueleto do app `fila`

**Files:**
- Create: `fila/__init__.py`, `fila/apps.py`, `fila/modulo.py`, `fila/models.py` (vazio por ora, só a docstring), `fila/urls.py` (lista vazia), `tests/test_fila_modulo.py`
- Modify: `config/settings.py` (INSTALLED_APPS), `config/urls.py`, `contas/fabrica.py`, `contas/cargos_de_fabrica.py`, `plataforma/marca.py:110-116`, `pyproject.toml:2-4`, `docker-compose.yml:14-21,64-65`, `.github/workflows/publicar-imagem.yml:48-49`, `deploy/docker-compose.vps.yml:13`, `README.md` (portas), `CLAUDE.md` ("Como rodar": portas)
- Modify (varreduras): `tests/test_camadas_nao_se_invertem.py:45` (`NEGOCIO`), `tests/test_id_do_post.py:27`, `tests/test_sublinhado_e_o_gettext.py:27`, `tests/test_html_preguicoso_nao_e_seguro.py:25`, `tests/test_regra_guid.py:19` (`APPS_DA_CASA`), `tests/test_esconder_vence_o_display.py:37` (`PASTAS_ESTATICAS`), `tests/test_variavel_de_cor_existe.py:31` (`FOLHAS`)

**Interfaces:**
- Produces: app `fila` instalado; `fila.modulo.MODULO` com `chave="fila"`, `rota="/fila"`, `permissoes=("fila.ver", "fila.participar", "fila.gerenciar", "fila.cadastros")`; atalhos `/fila/grupos`, `/fila/motivos`, `/fila/pausas`; cargos de fábrica e titular com as permissões da tabela do spec (mais `fila.ver`).

- [ ] **Step 1: Ambiente**

```bash
cd /home/mw5/projetos/fila-zero-app
uv sync --extra dev
docker exec portal-de-vendas-banco-1 createdb -U kronos fila_zero || true
```

Esperado: `.venv/bin/python` existe; `createdb` cria ou diz que já existe.

- [ ] **Step 2: Suíte da base verde antes de mexer**

Rodar `$PYTEST` inteiro em segundo plano. Esperado: tudo passa (a base tem 1856 passed, 1 skipped). Se algo falhar aqui, pare: o defeito é da cópia, não desta tarefa.

- [ ] **Step 3: Escrever o teste que falha**

`tests/test_fila_modulo.py`:

```python
"""O módulo da fila existe, nasce ligado e dá a cada cargo o que o spec diz.

A tabela de cargos do spec (2026-09-15, "Permissões e cargos") é a fonte. Um
cargo de fábrica sem `fila.participar` é uma instalação em que nenhum vendedor
consegue bater o ponto no primeiro dia, e ninguém percebe até a loja abrir.
"""

import pytest

from tests.conftest import empresa_do_teste, abrir_conta

PERMISSOES_DA_FILA = ("fila.ver", "fila.participar", "fila.gerenciar",
                      "fila.cadastros")


def test_o_modulo_esta_declarado_com_as_quatro_permissoes():
    from plataforma.declaracao import declarados

    spec = next(s for s in declarados() if s.chave == "fila")
    # `fila.ver` primeiro: é a permissão que põe o módulo no menu (D-1).
    assert spec.permissoes == PERMISSOES_DA_FILA
    assert spec.rota == "/fila"
    assert spec.ativo_por_padrao is True
    assert {a.rota for a in spec.atalhos} == {
        "/fila/grupos", "/fila/motivos", "/fila/pausas"}
    assert {a.permissao for a in spec.atalhos} == {"fila.cadastros"}


@pytest.mark.django_db
def test_o_modulo_nasce_ligado():
    from plataforma.models import Modulo

    assert Modulo.objects.get(chave="fila").ativo is True


@pytest.mark.django_db
@pytest.mark.parametrize("cargo, esperadas", [
    ("vendedor", {"fila_ver", "fila_participar"}),
    ("gerente", {"fila_ver", "fila_participar", "fila_gerenciar"}),
    ("supervisor", {"fila_ver", "fila_gerenciar"}),
    ("representante", set()),
    ("cliente", set()),
])
def test_os_cargos_de_fabrica_trazem_a_fila(cargo, esperadas):
    from contas.models import Cargo

    empresa = empresa_do_teste()
    abrir_conta(empresa, "sylvia")
    empresa.refresh_from_db()
    codenames = set(Cargo.objects.get(conta_id=empresa.conta_id, nome=cargo)
                    .permissoes.values_list("codename", flat=True))
    assert {c for c in codenames if c.startswith("fila_")} == esperadas


def test_o_titular_traz_as_quatro():
    from contas.fabrica import DE_FABRICA
    from contas.models import Nivel

    assert set(PERMISSOES_DA_FILA) <= set(DE_FABRICA[Nivel.TITULAR])
    assert "fila.*" in DE_FABRICA[Nivel.MASTER]


def test_a_marca_e_o_fila_zero():
    from plataforma.marca import MARCA_PADRAO

    assert MARCA_PADRAO.client_name == "Fila Zero"
    assert MARCA_PADRAO.system_name == "Fila Zero"
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `$PYTEST tests/test_fila_modulo.py`
Esperado: FAIL (`KeyError: 'fila'` e as asserções de marca/cargos).

- [ ] **Step 5: O app**

`fila/__init__.py`: vazio.

`fila/apps.py`:

```python
from django.apps import AppConfig


class FilaConfig(AppConfig):
    """A fila da vez das lojas — o produto do Fila Zero.

    O registro do módulo roda em `ready()`, e não na importação de `modulo.py`,
    pelo motivo escrito em `modulos/exemplo/apps.py`: registrar no corpo do
    arquivo faria o registro depender da ordem de import entre os apps.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "fila"
    verbose_name = "Fila da vez"

    def ready(self) -> None:
        from plataforma.declaracao import registrar

        from .modulo import MODULO

        registrar(MODULO)
```

`fila/modulo.py`:

```python
"""O que o módulo da fila diz sobre si.

`ativo_por_padrao=True`, contra a regra geral da R47: a fila É o produto. Uma
instalação do Fila Zero com a fila desligada não serve para nada, e esperar a
MW5 ligar em cada instalação nova é um dia de loja sem fila.

`fila.ver` vem PRIMEIRO de propósito (desvio D-1 do plano de 15/09/2026): o
menu da base põe o módulo na barra pela primeira permissão e some com os
atalhos de quem não a tem. Com outra na frente, o supervisor, que só corrige,
não acharia a fila, e quem só cuida dos cadastros não veria os cadastros.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from plataforma.declaracao import Atalho, ModuloSpec

MODULO = ModuloSpec(
    chave="fila",
    rotulo=_("Fila da vez"),
    icone="users",
    grupo="Vendas",
    rota="/fila",
    permissoes=("fila.ver", "fila.participar", "fila.gerenciar",
                "fila.cadastros"),
    atalhos=(
        Atalho(rotulo=_("Grupos de item"), rota="/fila/grupos",
               permissao="fila.cadastros", grupo="Cadastro",
               pai=_("Fila da vez")),
        Atalho(rotulo=_("Motivos de não venda"), rota="/fila/motivos",
               permissao="fila.cadastros", grupo="Cadastro",
               pai=_("Fila da vez")),
        Atalho(rotulo=_("Tipos de pausa"), rota="/fila/pausas",
               permissao="fila.cadastros", grupo="Cadastro",
               pai=_("Fila da vez")),
    ),
    ativo_por_padrao=True,
)
```

`fila/models.py`: só `"""As tabelas da fila da vez. Ver o spec de 15/09/2026."""` por ora.

`fila/urls.py`:

```python
from django.urls import path

from . import views  # noqa: F401  (as rotas entram nas tarefas seguintes)

urlpatterns: list = []
```

e `fila/views.py` só com a docstring `"""As telas da fila."""`.

`config/settings.py`: acrescentar `"fila",` em `INSTALLED_APPS` logo depois de `"modulos.exemplo",`.
`config/urls.py`: acrescentar `path("", include("fila.urls")),` **antes** de `path("", include("nucleo.urls")),` (a Task 6 põe a raiz `/` lá e ela precisa ganhar da do `nucleo`).

- [ ] **Step 6: As permissões de nascença**

`contas/cargos_de_fabrica.py`, trocar `DE_FABRICA` e o parágrafo acima dele:

```python
#: **No Fila Zero, as permissões da fila** (spec 2026-09-15, "Permissões e
#: cargos", e o desvio D-1 do plano: `fila.ver` acompanha toda permissão da
#: fila, porque é ela que põe a fila no menu). Representante e Cliente não
#: estão na loja atendendo, e por isso não trazem nada da fila.
DE_FABRICA: "tuple[tuple[str, str, str, bool, tuple[str, ...]], ...]" = (
    ("supervisor", "Supervisor", "empresa", False,
     ("usuarios.editar", "fila.ver", "fila.gerenciar")),
    ("gerente", "Gerente", "filial", False,
     ("usuarios.editar", "fila.ver", "fila.participar", "fila.gerenciar")),
    ("vendedor", "Vendedor", "filial", False,
     ("fila.ver", "fila.participar")),
    ("representante", "Representante", "filial", False, ()),
    ("cliente", "Cliente", "proprios", True, ()),
)
```

`contas/fabrica.py`: em `Nivel.MASTER` acrescentar `"fila.*"`; em `Nivel.TITULAR` acrescentar `"fila.cadastros", "fila.gerenciar", "fila.participar", "fila.ver"`, com o comentário: `#: **A fila (Fila Zero):** a Sylvia atende, corrige e mantém os cadastros.`

Rodar `$PYTEST tests/test_cargos_de_fabrica.py tests/test_fabrica*.py` — se algum teste da base contar permissões exatas de um cargo, ajuste o número esperado ali dizendo no comentário que a fila entrou.

- [ ] **Step 7: A identidade**

- `plataforma/marca.py:110-116`: `client_name="Fila Zero"`, `system_name="Fila Zero"`; o comentário vira `#: **No Fila Zero, a marca de nascença é "Fila Zero".** O cliente troca na tela de Aparência.`
- `pyproject.toml`: `name = "fila-zero"`, `description = "Fila Zero — a fila da vez das lojas, sobre a KRONOS base"`.
- `docker-compose.yml`: `127.0.0.1:5436:5432` e `8005:8000`; os comentários passam a dizer `5436: a 5435 é da KRONOS base e a 5434 do Portal de Vendas` e `8005: a 8004 é da KRONOS base e a 8003 do Portal de Vendas`.
- workflow e `deploy/docker-compose.vps.yml`: `kronos-base` → `fila-zero`.
- `README.md` e `CLAUDE.md` ("Como rodar"): 5435 → 5436, 8004 → 8005, e a frase das portas cita a KRONOS base (5435/8004) entre as dos outros produtos.
- Rodar `$PYTEST tests/test_documentacao_nao_mente.py tests/test_marca.py` e corrigir o que falar da marca antiga.

- [ ] **Step 8: As varreduras enxergam a pasta nova**

- `NEGOCIO = ("catalogo", "orcamento", "modulos", "fila")` e o comentário ganha `\`fila\` é o negócio do Fila Zero.`
- `PASTAS` de `test_id_do_post.py`, `test_sublinhado_e_o_gettext.py`, `test_html_preguicoso_nao_e_seguro.py`: acrescentar `"fila"`.
- `APPS_DA_CASA = ("contas", "plataforma", "comum", "fila")`.
- `PASTAS_ESTATICAS`: acrescentar `Path("fila/static")`.
- `FOLHAS` de `test_variavel_de_cor_existe.py`: acrescentar `*sorted(Path("fila/static/fila").glob("*.css")),`.

- [ ] **Step 9: Rodar e ver passar**

Run: `$PYTEST tests/test_fila_modulo.py`
Esperado: PASS.

- [ ] **Step 10: Quebrar de propósito**

Tirar `"fila.participar"` do vendedor em `cargos_de_fabrica.py` → o parametrizado de `vendedor` fica vermelho. Pôr `"fila.participar"` antes de `"fila.ver"` em `modulo.py` → o primeiro teste fica vermelho. Desfazer os dois.

- [ ] **Step 11: Suíte inteira**

`$PYTEST` inteiro em segundo plano. Esperado: verde. `test_documentacao_nao_mente.py` confere o número de arquivos: o `CLAUDE.md` diz `97 arquivos` em dois lugares; com `test_fila_modulo.py` são 98 — atualize os dois.

- [ ] **Step 12: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: o Fila Zero ganha identidade e o módulo da fila

A cópia da KRONOS base ainda se chamava KRONOS, publicava a imagem da base e
usava as portas dela: subir os dois na mesma máquina abria o banco da base
pelo Fila Zero, com as mesmas tabelas e sem aviso. Marca, pyproject, imagem
e portas (5436/8005) passam a ser do produto.

Nasce o app fila com o ModuloSpec ligado de fábrica, porque a fila é o
produto. As permissões são quatro, e não as três do spec: o menu da base
entra pelo primeiro nome declarado e some com os atalhos de quem não o tem,
então fila.ver vem na frente para o supervisor achar a fila e quem cuida dos
cadastros achar os cadastros (desvio D-1 do plano).

Vendedor, gerente, supervisor e titular nascem com o que a tabela do spec
diz; as varreduras que listam pastas passam a olhar para fila/."
```

---

### Task 2: As tabelas da fila

**Files:**
- Modify: `fila/models.py`, `contas/views_usuarios.py:1427-1456` (`_acao_remover`, D-5)
- Create: `fila/migrations/__init__.py`, `fila/migrations/0001_initial.py` (gerada), `tests/fila_cenario.py`, `tests/test_fila_modelos.py`

**Interfaces:**
- Consumes: app `fila` da Task 1.
- Produces (usado por todas as tarefas seguintes):
  - `fila.models.Estado` (`NA_FILA="na_fila"`, `ATENDENDO="atendendo"`, `EM_PAUSA="em_pausa"`), `fila.models.Resultado` (`VENDEU="vendeu"`, `NAO_VENDEU="nao_vendeu"`).
  - `GrupoDeItem`, `MotivoDeNaoVenda`, `TipoDePausa` (`nome`, `ordem`, `ativo`, mais `empresa`/`conta`/`guid`).
  - `Presenca(pessoa, filial, entrada, saida, fechada_por)`, `LugarNaFila(pessoa, filial, presenca, estado, na_fila_desde, desde)`, `Atendimento(filial, vendedor, presenca, inicio, fim, cliente_pediu, resultado, motivo, observacao, total, fechado_por)`, `ItemVendido(atendimento, grupo, valor)` com `related_name="itens"`, `Pausa(pessoa, filial, presenca, tipo, inicio, fim)`.
  - `tests/fila_cenario.py`: `SENHA`, `sylvia() -> (empresa, matriz, titular)`, `nova_loja(empresa, apelido) -> Filial`, `pessoa_na_loja(login, empresa, filial, cargo="vendedor") -> Usuario`, `cadastros(empresa) -> SimpleNamespace(grupo, grupo2, motivo, tipo)`, `logado(login) -> Client`, `relogio` (fixture em `tests/fila_cenario.py`, importada pelos testes).

- [ ] **Step 1: O cenário**

`tests/fila_cenario.py`:

```python
"""A montagem de cenário dos testes da fila. Não é arquivo de teste.

Mora num arquivo só porque todo teste da fila precisa da mesma loja com a
mesma gente, e oito cópias da montagem divergiriam no primeiro ajuste.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as tz
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse

from tests.conftest import (
    abrir_conta, alocar, email_de, empresa_do_teste, matriz_do_teste)

SENHA = "segredo-de-teste"


def sylvia():
    """A empresa do teste com a Sylvia titular, a Matriz e as permissões
    diretas do nível (a tela de Usuários aplica ao gravar; o teste, à mão)."""
    from contas.fabrica import aplicar
    from contas.models import Nivel, Usuario

    empresa = empresa_do_teste()
    if empresa.dono_id is None:
        titular = abrir_conta(empresa, "sylvia", SENHA)
        aplicar(titular, Nivel.TITULAR)
        empresa.refresh_from_db()
    titular = Usuario.objects.get(pk=empresa.dono_id)
    return empresa, matriz_do_teste(), titular


def nova_loja(empresa, apelido):
    from plataforma.models import Filial

    return Filial.objects.create(empresa=empresa, nome=f"Loja {apelido}",
                                 apelido=apelido)


def pessoa_na_loja(login, empresa, filial, cargo="vendedor"):
    """Uma pessoa da conta, alocada NA LOJA com um cargo de fábrica."""
    from contas.models import Usuario

    pessoa = Usuario.objects.create_user(
        email=email_de(login), password=SENHA, nome=login.title(),
        dono_id=empresa.dono_id)
    alocar(pessoa, empresa, cargo, filial=filial)
    return pessoa


def cadastros(empresa):
    from fila.models import GrupoDeItem, MotivoDeNaoVenda, TipoDePausa

    return SimpleNamespace(
        grupo=GrupoDeItem.irrestritos.create(empresa=empresa, nome="Sofás"),
        grupo2=GrupoDeItem.irrestritos.create(empresa=empresa, nome="Tapetes"),
        motivo=MotivoDeNaoVenda.irrestritos.create(empresa=empresa,
                                                   nome="Só olhando"),
        tipo=TipoDePausa.irrestritos.create(empresa=empresa, nome="Almoço"),
    )


def logado(login):
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": email_de(login),
                                     "senha": SENHA})
    return cliente


@pytest.fixture
def relogio(monkeypatch):
    """Um relógio que anda um minuto a cada leitura.

    A ordem da fila é a hora em que se entrou nela. Com o relógio de verdade,
    duas ações seguidas num teste podem cair no mesmo microssegundo e a ordem
    vira sorteio; com este, cada ação acontece depois da anterior, sempre.
    """
    atual = [datetime(2026, 9, 15, 13, 0, tzinfo=tz.utc)]

    def agora():
        atual[0] += timedelta(minutes=1)
        return atual[0]

    import fila.acoes

    monkeypatch.setattr(fila.acoes, "_agora", agora)
    return atual
```

(A fixture `relogio` só funciona a partir da Task 3, quando `fila/acoes.py` existe; esta tarefa não a usa.)

- [ ] **Step 2: O teste que falha**

`tests/test_fila_modelos.py`:

```python
"""As travas que são do banco, e não da tela.

"Um aberto por pessoa" escrito só na view deixa passar quem grava por fora —
um shell, uma migração, a próxima tela. A restrição parcial não deixa.
"""

from datetime import datetime, timezone as tz
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from tests.fila_cenario import cadastros, pessoa_na_loja, sylvia

AGORA = datetime(2026, 9, 15, 13, 0, tzinfo=tz.utc)

pytestmark = pytest.mark.django_db


def _presenca(empresa, filial, pessoa, saida=None):
    from fila.models import Presenca

    return Presenca.irrestritos.create(empresa=empresa, filial=filial,
                                       pessoa=pessoa, entrada=AGORA,
                                       saida=saida)


def test_duas_presencas_abertas_da_mesma_pessoa_o_banco_recusa():
    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    _presenca(empresa, matriz, ana, saida=AGORA)   # fechada não conta
    _presenca(empresa, matriz, ana)
    with pytest.raises(IntegrityError), transaction.atomic():
        _presenca(empresa, matriz, ana)


def test_dois_atendimentos_abertos_do_mesmo_vendedor_o_banco_recusa():
    from fila.models import Atendimento

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    presenca = _presenca(empresa, matriz, ana)
    Atendimento.irrestritos.create(empresa=empresa, filial=matriz,
                                   vendedor=ana, presenca=presenca,
                                   inicio=AGORA)
    with pytest.raises(IntegrityError), transaction.atomic():
        Atendimento.irrestritos.create(empresa=empresa, filial=matriz,
                                       vendedor=ana, presenca=presenca,
                                       inicio=AGORA)


def test_duas_pausas_abertas_da_mesma_pessoa_o_banco_recusa():
    from fila.models import Pausa

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    presenca = _presenca(empresa, matriz, ana)
    tipo = cadastros(empresa).tipo
    Pausa.irrestritos.create(empresa=empresa, filial=matriz, pessoa=ana,
                             presenca=presenca, tipo=tipo, inicio=AGORA)
    with pytest.raises(IntegrityError), transaction.atomic():
        Pausa.irrestritos.create(empresa=empresa, filial=matriz, pessoa=ana,
                                 presenca=presenca, tipo=tipo, inicio=AGORA)


def test_uma_pessoa_tem_um_lugar_na_fila_so():
    from fila.models import Estado, LugarNaFila

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    presenca = _presenca(empresa, matriz, ana)
    dados = dict(empresa=empresa, filial=matriz, pessoa=ana,
                 presenca=presenca, estado=Estado.NA_FILA,
                 na_fila_desde=AGORA, desde=AGORA)
    LugarNaFila.irrestritos.create(**dados)
    with pytest.raises(IntegrityError), transaction.atomic():
        LugarNaFila.irrestritos.create(**dados)


def test_nome_de_cadastro_e_unico_na_empresa_sem_diferenca_de_caixa():
    from fila.models import GrupoDeItem

    empresa, _, _ = sylvia()
    GrupoDeItem.irrestritos.create(empresa=empresa, nome="Sofás")
    with pytest.raises(IntegrityError), transaction.atomic():
        GrupoDeItem.irrestritos.create(empresa=empresa, nome="SOFÁS")


def test_valor_de_item_vendido_precisa_ser_positivo():
    from fila.models import Atendimento, ItemVendido

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    presenca = _presenca(empresa, matriz, ana)
    atendimento = Atendimento.irrestritos.create(
        empresa=empresa, filial=matriz, vendedor=ana, presenca=presenca,
        inicio=AGORA, fim=AGORA, resultado="vendeu", total=Decimal("0"))
    with pytest.raises(IntegrityError), transaction.atomic():
        ItemVendido.irrestritos.create(empresa=empresa,
                                       atendimento=atendimento,
                                       grupo=cadastros(empresa).grupo,
                                       valor=Decimal("0"))


def test_cadastro_usado_nao_se_apaga():
    from django.db.models import ProtectedError

    from fila.models import Pausa

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    tipo = cadastros(empresa).tipo
    Pausa.irrestritos.create(empresa=empresa, filial=matriz, pessoa=ana,
                             presenca=_presenca(empresa, matriz, ana),
                             tipo=tipo, inicio=AGORA)
    with pytest.raises(ProtectedError):
        tipo.delete()


def test_filial_com_historico_da_fila_nao_se_remove():
    """A base pergunta ao próprio Django se alguma tabela de negócio protege
    a filial (`plataforma/filiais.py`, `_protegida`). A fila tem de responder."""
    from plataforma.filiais import _protegida

    empresa, _, _ = sylvia()
    from tests.fila_cenario import nova_loja

    loja = nova_loja(empresa, "Centro")
    ana = pessoa_na_loja("ana", empresa, loja)
    _presenca(empresa, loja, ana)
    assert _protegida(loja)
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `$PYTEST tests/test_fila_modelos.py`
Esperado: FAIL com `ImportError` (`cannot import name 'Presenca'`).

- [ ] **Step 4: Os models**

`fila/models.py`:

```python
"""As tabelas da fila da vez. Ver o spec de 15/09/2026.

Toda tabela herda `ModeloDaEmpresa`: a Sylvia Design é UMA conta nesta
instalação, mas a regra do inquilino não pergunta quantas contas há hoje.

**O estado de agora e o histórico são tabelas separadas.** `LugarNaFila` é uma
linha por pessoa presente, e é só ela que a consulta de 3 em 3 segundos lê:
poucas linhas por loja, sempre rápidas. `Presenca`, `Atendimento` e `Pausa`
crescem para sempre e só são escritas quando algo acontece.

**Os "um aberto por pessoa" são restrições do banco**, e não só da tela: quem
grava por fora (um shell, uma migração, a próxima tela) não passa.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from contas.inquilino import ModeloDaEmpresa

__all__ = [
    "Atendimento", "Estado", "GrupoDeItem", "ItemVendido", "LugarNaFila",
    "MotivoDeNaoVenda", "Pausa", "Presenca", "Resultado", "TipoDePausa",
]


class Estado(models.TextChoices):
    NA_FILA = "na_fila", _("Na fila")
    ATENDENDO = "atendendo", _("Atendendo")
    EM_PAUSA = "em_pausa", _("Em pausa")


class Resultado(models.TextChoices):
    VENDEU = "vendeu", _("Vendeu")
    NAO_VENDEU = "nao_vendeu", _("Não vendeu")


class Cadastro(ModeloDaEmpresa):
    """O que os três cadastros têm em comum.

    **Cadastro usado não se apaga, desativa.** Os lançamentos apontam para ele
    com `PROTECT`: apagar o motivo "Só olhando" apagaria a razão de cem não
    vendas do ano passado, e o dashboard perderia a pergunta que ele existe
    para responder.
    """

    nome = models.CharField(_("nome"), max_length=80)
    ordem = models.PositiveIntegerField(_("ordem"), default=0)
    ativo = models.BooleanField(_("ativo"), default=True)

    # A `Meta` herda a do `ModeloDaEmpresa` por extenso: declarar uma `Meta`
    # nova sem herdar perde `default_manager_name`, e o backup exportaria zero
    # linhas destas tabelas (ver `contas/inquilino.py`).
    class Meta(ModeloDaEmpresa.Meta):
        abstract = True
        ordering = ("ordem", "nome")
        constraints = [
            # Sem diferença de caixa: "Sofás" e "SOFÁS" na mesma lista de
            # opções é o vendedor escolhendo ao acaso, e o dashboard contando
            # dois grupos que são um.
            models.UniqueConstraint(
                Lower("nome"), "empresa",
                name="%(app_label)s_%(class)s_nome_unico"),
        ]

    def __str__(self) -> str:
        return self.nome


class GrupoDeItem(Cadastro):
    class Meta(Cadastro.Meta):
        verbose_name = _("grupo de item")
        verbose_name_plural = _("grupos de item")


class MotivoDeNaoVenda(Cadastro):
    class Meta(Cadastro.Meta):
        verbose_name = _("motivo de não venda")
        verbose_name_plural = _("motivos de não venda")


class TipoDePausa(Cadastro):
    class Meta(Cadastro.Meta):
        verbose_name = _("tipo de pausa")
        verbose_name_plural = _("tipos de pausa")


def _pessoa(verbose, **extra):
    """FK para o usuário com `PROTECT`: o histórico da loja não some quando a
    pessoa sai da empresa. Quem sai é desativado (desvio D-5 do plano)."""
    return models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=verbose,
                             on_delete=models.PROTECT, related_name="+",
                             **extra)


def _loja():
    return models.ForeignKey("plataforma.Filial", verbose_name=_("loja"),
                             on_delete=models.PROTECT, related_name="+")


class Presenca(ModeloDaEmpresa):
    """O ponto: a pessoa chegou na loja e está disponível para a fila (D1).

    Não é controle de jornada e não tem relatório de horas.
    """

    pessoa = _pessoa(_("pessoa"))
    filial = _loja()
    entrada = models.DateTimeField(_("entrada"))
    saida = models.DateTimeField(_("saída"), null=True, blank=True)
    #: Preenchido só quando quem fechou foi o gerente (D7).
    fechada_por = _pessoa(_("fechada por"), null=True, blank=True)

    class Meta(ModeloDaEmpresa.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa"], condition=Q(saida__isnull=True),
                name="fila_uma_presenca_aberta_por_pessoa"),
        ]


class LugarNaFila(ModeloDaEmpresa):
    """Onde a pessoa está AGORA. Nasce no ponto e some quando ela sai da loja.

    **A ordem da fila é `na_fila_desde` crescente entre quem está `na_fila`.**
    Voltar para o fim (D2) é gravar a hora de agora; não há número de posição
    guardado, porque um número guardado precisaria ser renumerado a cada
    saída, e renumerar sob concorrência é onde as filas se perdem.
    """

    pessoa = models.OneToOneField(settings.AUTH_USER_MODEL,
                                  verbose_name=_("pessoa"),
                                  on_delete=models.PROTECT, related_name="+")
    filial = _loja()
    presenca = models.ForeignKey(Presenca, verbose_name=_("presença"),
                                 on_delete=models.PROTECT, related_name="+")
    estado = models.CharField(_("estado"), max_length=12,
                              choices=Estado.choices, default=Estado.NA_FILA)
    na_fila_desde = models.DateTimeField(_("na fila desde"))
    #: Quando entrou no estado atual, para o "há quanto tempo" da tela.
    desde = models.DateTimeField(_("desde"))

    class Meta(ModeloDaEmpresa.Meta):
        indexes = [models.Index(fields=["filial", "estado", "na_fila_desde"],
                                name="fila_lugar_ordem")]


class Atendimento(ModeloDaEmpresa):
    filial = _loja()
    vendedor = _pessoa(_("vendedor"))
    presenca = models.ForeignKey(Presenca, verbose_name=_("presença"),
                                 on_delete=models.PROTECT, related_name="+")
    inicio = models.DateTimeField(_("início"))
    fim = models.DateTimeField(_("fim"), null=True, blank=True)
    #: Aberto por "Cliente pediu por mim" (D3): o dashboard não conta como vez
    #: furada.
    cliente_pediu = models.BooleanField(_("cliente pediu"), default=False)
    resultado = models.CharField(_("resultado"), max_length=12, blank=True,
                                 choices=Resultado.choices)
    motivo = models.ForeignKey(MotivoDeNaoVenda, verbose_name=_("motivo"),
                               on_delete=models.PROTECT, null=True,
                               blank=True, related_name="+")
    observacao = models.CharField(_("observação"), max_length=280,
                                  blank=True)
    total = models.DecimalField(_("total"), max_digits=12, decimal_places=2,
                                default=Decimal("0"))
    fechado_por = _pessoa(_("fechado por"), null=True, blank=True)

    class Meta(ModeloDaEmpresa.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["vendedor"], condition=Q(fim__isnull=True),
                name="fila_um_atendimento_aberto_por_vendedor"),
        ]
        indexes = [models.Index(fields=["filial", "fim"],
                                name="fila_atendimento_do_dia")]


class ItemVendido(ModeloDaEmpresa):
    atendimento = models.ForeignKey(Atendimento, verbose_name=_("atendimento"),
                                    on_delete=models.CASCADE,
                                    related_name="itens")
    grupo = models.ForeignKey(GrupoDeItem, verbose_name=_("grupo"),
                              on_delete=models.PROTECT, related_name="+")
    valor = models.DecimalField(_("valor"), max_digits=12, decimal_places=2)

    class Meta(ModeloDaEmpresa.Meta):
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0),
                                   name="fila_item_vendido_valor_positivo"),
        ]


class Pausa(ModeloDaEmpresa):
    pessoa = _pessoa(_("pessoa"))
    filial = _loja()
    presenca = models.ForeignKey(Presenca, verbose_name=_("presença"),
                                 on_delete=models.PROTECT, related_name="+")
    tipo = models.ForeignKey(TipoDePausa, verbose_name=_("tipo"),
                             on_delete=models.PROTECT, related_name="+")
    inicio = models.DateTimeField(_("início"))
    fim = models.DateTimeField(_("fim"), null=True, blank=True)

    class Meta(ModeloDaEmpresa.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa"], condition=Q(fim__isnull=True),
                name="fila_uma_pausa_aberta_por_pessoa"),
        ]
```

- [ ] **Step 5: A migração**

```bash
mkdir -p fila/migrations && touch fila/migrations/__init__.py
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/fila_zero \
  .venv/bin/python manage.py makemigrations fila --name initial
```

Esperado: `fila/migrations/0001_initial.py` criado sem pergunta interativa. Abra e confira que as quatro restrições e o `CheckConstraint` estão lá.

- [ ] **Step 6: Rodar e ver passar**

Run: `$PYTEST tests/test_fila_modelos.py tests/test_regra_do_inquilino.py tests/test_regra_guid.py`
Esperado: PASS.

- [ ] **Step 7: Quebrar de propósito**

Apagar a `condition=Q(saida__isnull=True)` da presença (e regenerar a migração num rascunho, sem commit) → `test_duas_presencas...` fica vermelho de outro jeito (a fechada já colide). Trocar `Lower("nome")` por `"nome"` → o teste de caixa fica vermelho. Desfazer e voltar a migração ao estado do Step 5 (`git checkout fila/migrations` depois de a primeira versão estar no índice, ou gerar de novo).

- [ ] **Step 8: D-5 — remover usuário com histórico**

Teste em `tests/test_fila_modelos.py`:

```python
def test_remover_usuario_com_historico_na_fila_responde_com_frase():
    from django.urls import reverse

    from contas.models import Usuario
    from tests.fila_cenario import logado

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    _presenca(empresa, matriz, ana, saida=AGORA)
    resposta = logado("sylvia").post(reverse("usuarios"), {
        "acao": "remover", "id": str(ana.pk)})
    assert resposta.status_code == 200
    assert "histórico" in resposta.content.decode()
    assert Usuario.objects.filter(pk=ana.pk).exists()
```

Rodar: vermelho (500 por `ProtectedError`). Em `contas/views_usuarios.py`, `_acao_remover`, trocar o bloco final por:

```python
    try:
        with transaction.atomic():
            # Registrado ANTES do `delete()`: depois dele não sobra ninguém
            # para ler login e nome — e, dentro do mesmo `atomic()`, uma
            # falha aqui desfaz o registro junto com a remoção, então não há
            # risco de um registro de remoção sobreviver a uma remoção que
            # não aconteceu.
            registrar(ACOES.USUARIO_REMOVIDO, request.usuario, alvo=alvo.email, request=request)
            alvo.delete()
    except ProtectedError:
        # Um módulo de negócio guarda o histórico desta pessoa com `PROTECT`
        # (no Fila Zero, ponto, atendimentos e pausas). Apagar levaria o
        # histórico junto, e o banco recusa; sem esta frase a recusa chegaria
        # como "Algo inesperado aconteceu". O `atomic` já desfez o registro.
        return _desenhar(request, erro=(
            f"{alvo.email} tem histórico gravado. Desative em vez de "
            f"remover."))
    return HttpResponseRedirect(reverse("usuarios"))
```

com `from django.db.models import ProtectedError` no topo. Rodar: verde. Quebrar (tirar o `except`) e ver vermelho; desfazer.

- [ ] **Step 9: Suíte inteira** em segundo plano; atualizar `97`→`99` arquivos no `CLAUDE.md` (dois lugares) se `test_documentacao_nao_mente.py` acusar. Esperado: verde.

- [ ] **Step 10: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: as tabelas da fila da vez

Nascem os três cadastros (grupos de item, motivos de não venda, tipos de
pausa), a presença, o lugar de agora na fila, o atendimento com os itens
vendidos e a pausa, todos com a coluna do inquilino.

O estado de agora (LugarNaFila) fica separado do histórico porque a tela
pergunta a cada 3 segundos, e a pergunta tem de ler poucas linhas. A ordem
da fila é a hora em que se entrou nela, e não um número guardado: número
guardado precisaria ser renumerado a cada saída, sob concorrência.

Os 'um aberto por pessoa' são restrições parciais do banco, e o nome de
cadastro é único por empresa sem diferença de caixa. Cadastro usado é
PROTECT: desativa, não apaga.

A tela de Usuários passa a responder com frase quando a pessoa tem histórico
protegido, em vez de 500."
```

---

### Task 3: As ações do vendedor, a ordem e a versão

**Files:**
- Create: `fila/acoes.py`, `fila/estado.py`, `fila/valores.py`, `tests/test_fila_acoes.py`, `tests/test_fila_estado.py`, `tests/test_fila_concorrencia.py`

**Interfaces:**
- Consumes: models da Task 2; `tests/fila_cenario.py`.
- Produces:
  - `fila.acoes.Recusa(Exception)` com `.frase: str`.
  - `fila.acoes.ItemLancado(grupo_id: int, valor: Decimal)`, `fila.acoes.Lancamento(resultado: str, itens: tuple[ItemLancado, ...] = (), motivo_id: int | None = None, observacao: str = "")`.
  - `bater_ponto(pessoa, filial) -> None`, `vou_atender(pessoa, filial) -> None`, `cliente_pediu(pessoa, filial) -> None`, `finalizar(pessoa, filial, lancamento) -> None`, `pausar(pessoa, filial, tipo_id) -> None`, `voltar_para_a_fila(pessoa, filial) -> None`, `sair_da_loja(pessoa, filial) -> None`. Todas levantam `Recusa`.
  - Internas reusadas pela Task 4: `_agora()`, `_travar(*filiais)`, `_lugar_na_loja(pessoa_id, filial) -> LugarNaFila` (levanta `Recusa`), `_validar(empresa, lancamento, *, ja_usados=frozenset(), ja_usado_motivo=None) -> tuple[dict[int, GrupoDeItem], MotivoDeNaoVenda | None, Decimal]`, `_fechar_atendimento(atendimento, lancamento, agora, fechado_por=None)`, `_voltar_ao_fim(lugar, agora)`, `_sair(lugar, agora, fechada_por=None)`.
  - `fila.estado.nome_de(pessoa) -> str`, `na_fila(filial) -> QuerySet[LugarNaFila]` (em ordem), `posicao_de(lugar) -> int | None` (1 = primeiro), `versao_da_fila(filial) -> str`, `retrato(filial, pessoa) -> Retrato`, com `Linha(pessoa_id, nome, estado, desde, posicao, tipo_de_pausa, e_voce)` e `Retrato(versao, atendendo, fila, em_pausa, meu)` (`meu: Linha | None`).
  - `fila.valores.ler_valor(texto: str) -> Decimal | None`.

- [ ] **Step 1: Os testes das ações**

`tests/test_fila_acoes.py`:

```python
"""As transições da fila (spec, "As transições") e as recusas.

Cada teste diz a regra que prova. O relógio anda um minuto por ação
(`tests/fila_cenario.relogio`), então "entrou depois" é sempre verdade.
"""

from decimal import Decimal

import pytest

from tests.fila_cenario import (  # noqa: F401  (relogio é fixture)
    cadastros, nova_loja, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        caio=pessoa_na_loja("caio", empresa, matriz),
        cad=cadastros(empresa))


def _ordem(filial):
    from fila.estado import na_fila

    return [lugar.pessoa.nome for lugar in na_fila(filial)]


def _venda(cad, *valores):
    from fila.acoes import ItemLancado, Lancamento

    return Lancamento("vendeu", tuple(
        ItemLancado(cad.grupo.pk, Decimal(v)) for v in valores))


def _nao_venda(motivo_id, observacao=""):
    from fila.acoes import Lancamento

    return Lancamento("nao_vendeu", motivo_id=motivo_id,
                      observacao=observacao)


# --- A ordem ---------------------------------------------------------------

def test_quem_bate_o_ponto_entra_no_fim(loja):
    from fila.acoes import bater_ponto

    for p in (loja.ana, loja.bia, loja.caio):
        bater_ponto(p, loja.matriz)
    assert _ordem(loja.matriz) == ["Ana", "Bia", "Caio"]


def test_finalizar_manda_para_o_fim(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender

    for p in (loja.ana, loja.bia):
        bater_ponto(p, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    assert _ordem(loja.matriz) == ["Bia"]
    finalizar(loja.ana, loja.matriz, _venda(loja.cad, "100"))
    assert _ordem(loja.matriz) == ["Bia", "Ana"]


def test_voltar_da_pausa_manda_para_o_fim(loja):
    from fila.acoes import bater_ponto, pausar, voltar_para_a_fila

    for p in (loja.ana, loja.bia):
        bater_ponto(p, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    voltar_para_a_fila(loja.ana, loja.matriz)
    assert _ordem(loja.matriz) == ["Bia", "Ana"]


# --- A vez -------------------------------------------------------------------

def test_so_o_primeiro_tem_vou_atender(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender
    from fila.models import Atendimento

    for p in (loja.ana, loja.bia):
        bater_ponto(p, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        vou_atender(loja.bia, loja.matriz)
    assert recusa.value.frase == "A vez é de Ana. Você é o 2º da fila."
    assert not Atendimento.irrestritos.exists()


def test_cliente_pediu_funciona_fora_da_vez_e_nao_mexe_no_primeiro(loja):
    from fila.acoes import bater_ponto, cliente_pediu
    from fila.models import Atendimento

    for p in (loja.ana, loja.bia, loja.caio):
        bater_ponto(p, loja.matriz)
    cliente_pediu(loja.caio, loja.matriz)
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.vendedor == loja.caio
    assert atendimento.cliente_pediu is True
    assert _ordem(loja.matriz) == ["Ana", "Bia"]


def test_tela_velha_vou_atender_de_quem_ja_nao_e_o_primeiro(loja):
    """Ana e Bia veem a Ana em primeiro; a Ana atende; a tela velha da Bia
    ainda mostra a Ana. O "Vou atender" da Bia é aceito, porque AGORA ela é a
    primeira — a vez é decidida no servidor (D9), não na tela."""
    from fila.acoes import Recusa, bater_ponto, vou_atender

    for p in (loja.ana, loja.bia, loja.caio):
        bater_ponto(p, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa):
        vou_atender(loja.caio, loja.matriz)
    vou_atender(loja.bia, loja.matriz)


# --- Venda e não venda -----------------------------------------------------

def test_venda_com_varios_grupos_total_e_a_soma(loja):
    from fila.acoes import (ItemLancado, Lancamento, bater_ponto, finalizar,
                            vou_atender)
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, Lancamento("vendeu", (
        ItemLancado(loja.cad.grupo.pk, Decimal("1500.50")),
        ItemLancado(loja.cad.grupo2.pk, Decimal("300")))))
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.resultado == "vendeu"
    assert atendimento.total == Decimal("1800.50")
    assert atendimento.fim is not None
    assert atendimento.itens.count() == 2


@pytest.mark.parametrize("caso", ["sem_item", "zero", "negativo",
                                  "desativado", "outra_empresa", "com_motivo"])
def test_venda_invalida_e_recusada(loja, caso):
    from fila.acoes import (ItemLancado, Lancamento, Recusa, bater_ponto,
                            finalizar, vou_atender)
    from fila.models import GrupoDeItem

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    grupo = loja.cad.grupo.pk
    lancamento = {
        "sem_item": Lancamento("vendeu", ()),
        "zero": Lancamento("vendeu", (ItemLancado(grupo, Decimal("0")),)),
        "negativo": Lancamento("vendeu", (ItemLancado(grupo, Decimal("-1")),)),
        "desativado": None,
        "outra_empresa": None,
        "com_motivo": Lancamento("vendeu", (ItemLancado(grupo, Decimal("5")),),
                                 motivo_id=loja.cad.motivo.pk),
    }[caso]
    if caso == "desativado":
        GrupoDeItem.irrestritos.filter(pk=grupo).update(ativo=False)
        lancamento = Lancamento("vendeu", (ItemLancado(grupo, Decimal("5")),))
    if caso == "outra_empresa":
        lancamento = Lancamento("vendeu", (
            ItemLancado(_grupo_de_outra_conta().pk, Decimal("5")),))
    with pytest.raises(Recusa):
        finalizar(loja.ana, loja.matriz, lancamento)
    from fila.models import Estado, LugarNaFila

    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.ATENDENDO


def _grupo_de_outra_conta():
    from fila.models import GrupoDeItem
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    outra = Empresa.objects.create(razao_social="Concorrente", nome_fantasia="Concorrente")
    abrir_conta(outra, "concorrente")
    outra.refresh_from_db()
    return GrupoDeItem.irrestritos.create(empresa=outra, nome="Sofás")


def test_nao_venda_grava_motivo_e_observacao_e_total_zero(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz,
              _nao_venda(loja.cad.motivo.pk, "  volta sábado  "))
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.resultado == "nao_vendeu"
    assert atendimento.motivo == loja.cad.motivo
    assert atendimento.observacao == "volta sábado"
    assert atendimento.total == Decimal("0")
    assert atendimento.itens.count() == 0


@pytest.mark.parametrize("caso", ["sem_motivo", "desativado", "outra_empresa",
                                  "com_item", "sem_resultado"])
def test_nao_venda_invalida_e_recusada(loja, caso):
    from fila.acoes import (ItemLancado, Lancamento, Recusa, bater_ponto,
                            finalizar, vou_atender)
    from fila.models import MotivoDeNaoVenda

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    motivo = loja.cad.motivo.pk
    if caso == "desativado":
        MotivoDeNaoVenda.irrestritos.filter(pk=motivo).update(ativo=False)
    if caso == "outra_empresa":
        outro = _grupo_de_outra_conta()
        motivo = MotivoDeNaoVenda.irrestritos.create(
            empresa=outro.empresa, nome="Caro").pk
    lancamento = {
        "sem_motivo": _nao_venda(None),
        "desativado": _nao_venda(motivo),
        "outra_empresa": _nao_venda(motivo),
        "com_item": Lancamento("nao_vendeu", (
            ItemLancado(loja.cad.grupo.pk, Decimal("5")),), motivo_id=motivo),
        "sem_resultado": Lancamento("", motivo_id=motivo),
    }[caso]
    with pytest.raises(Recusa):
        finalizar(loja.ana, loja.matriz, lancamento)


# --- O lugar -----------------------------------------------------------------

def test_ponto_em_outra_loja_fecha_a_presenca_da_primeira(loja):
    from fila.acoes import bater_ponto
    from fila.models import LugarNaFila, Presenca

    centro = nova_loja(loja.empresa, "Centro")
    from contas.models import Alocacao, Cargo

    Alocacao.objects.create(pessoa=loja.ana, empresa=loja.empresa,
                            filial=centro, cargo=Cargo.objects.get(
                                conta_id=loja.empresa.conta_id,
                                nome="vendedor"))
    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.ana, centro)
    assert Presenca.irrestritos.filter(pessoa=loja.ana,
                                       saida__isnull=True).get().filial == centro
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).filial == centro
    assert _ordem(loja.matriz) == []


def test_ponto_em_outra_loja_recusado_se_atendendo(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender

    centro = nova_loja(loja.empresa, "Centro")
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        bater_ponto(loja.ana, centro)
    assert "Finalize" in recusa.value.frase


def test_sair_da_loja_fecha_presenca_e_pausa(loja):
    from fila.acoes import bater_ponto, pausar, sair_da_loja
    from fila.models import LugarNaFila, Pausa, Presenca

    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    sair_da_loja(loja.ana, loja.matriz)
    assert not LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    assert not Presenca.irrestritos.filter(saida__isnull=True).exists()
    assert not Pausa.irrestritos.filter(fim__isnull=True).exists()


def test_sair_da_loja_recusado_se_atendendo(loja):
    from fila.acoes import Recusa, bater_ponto, sair_da_loja, vou_atender

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa):
        sair_da_loja(loja.ana, loja.matriz)


@pytest.mark.parametrize("acao", ["vou_atender", "cliente_pediu", "pausar",
                                  "voltar_para_a_fila", "sair_da_loja"])
def test_quem_nao_bateu_o_ponto_nao_age(loja, acao):
    import fila.acoes as acoes

    argumentos = (loja.cad.tipo.pk,) if acao == "pausar" else ()
    with pytest.raises(acoes.Recusa) as recusa:
        getattr(acoes, acao)(loja.ana, loja.matriz, *argumentos)
    assert recusa.value.frase == "Você não está nesta loja. Bata o ponto primeiro."


def test_pausa_com_tipo_desativado_e_recusada(loja):
    from fila.acoes import Recusa, bater_ponto, pausar
    from fila.models import TipoDePausa

    bater_ponto(loja.ana, loja.matriz)
    TipoDePausa.irrestritos.update(ativo=False)
    with pytest.raises(Recusa):
        pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)


def test_fechado_nao_reabre(loja):
    """Finalizar de novo não mexe no atendimento já fechado: a pessoa não
    está mais atendendo, e a ação é recusada."""
    from fila.acoes import Recusa, bater_ponto, finalizar, vou_atender

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _venda(loja.cad, "10"))
    with pytest.raises(Recusa):
        finalizar(loja.ana, loja.matriz, _venda(loja.cad, "99"))
```

- [ ] **Step 2: Os testes do valor, do retrato e da versão**

`tests/test_fila_estado.py`:

```python
from decimal import Decimal

import pytest

from tests.fila_cenario import (  # noqa: F401
    cadastros, nova_loja, pessoa_na_loja, relogio, sylvia)


@pytest.mark.parametrize("texto, esperado", [
    ("1500", Decimal("1500")), ("1.500,50", Decimal("1500.50")),
    ("1500,5", Decimal("1500.50")), ("1500.50", Decimal("1500.50")),
    (" R$ 2.000 ", Decimal("2000")), ("1.234.567,8", Decimal("1234567.80")),
    ("", None), ("abc", None), ("1,2,3", None), ("-5", None),
])
def test_ler_valor(texto, esperado):
    from fila.valores import ler_valor

    assert ler_valor(texto) == esperado


@pytest.mark.django_db
def test_retrato_separa_atendendo_fila_e_pausa_e_marca_quem_ve(relogio):
    from fila.acoes import bater_ponto, pausar, vou_atender
    from fila.estado import retrato

    empresa, matriz, _ = sylvia()
    cad = cadastros(empresa)
    ana, bia, caio, duda = (pessoa_na_loja(n, empresa, matriz)
                            for n in ("ana", "bia", "caio", "duda"))
    for p in (ana, bia, caio, duda):
        bater_ponto(p, matriz)
    vou_atender(ana, matriz)
    pausar(duda, matriz, cad.tipo.pk)

    r = retrato(matriz, caio)
    assert [l.nome for l in r.atendendo] == ["Ana"]
    assert [(l.nome, l.posicao) for l in r.fila] == [("Bia", 1), ("Caio", 2)]
    assert [(l.nome, l.tipo_de_pausa) for l in r.em_pausa] == [("Duda", "Almoço")]
    assert r.meu.nome == "Caio" and r.meu.e_voce and r.meu.posicao == 2


@pytest.mark.django_db
def test_retrato_de_uma_loja_nunca_traz_gente_de_outra(relogio):
    from fila.acoes import bater_ponto
    from fila.estado import retrato

    empresa, matriz, _ = sylvia()
    centro = nova_loja(empresa, "Centro")
    bater_ponto(pessoa_na_loja("ana", empresa, matriz), matriz)
    bater_ponto(pessoa_na_loja("bia", empresa, centro), centro)
    assert [l.nome for l in retrato(centro, None).fila] == ["Bia"]


@pytest.mark.django_db
def test_a_versao_muda_quando_a_fila_muda_e_so_entao(relogio):
    from fila.acoes import bater_ponto, sair_da_loja, vou_atender
    from fila.estado import versao_da_fila

    empresa, matriz, _ = sylvia()
    centro = nova_loja(empresa, "Centro")
    ana = pessoa_na_loja("ana", empresa, matriz)
    bia = pessoa_na_loja("bia", empresa, centro)

    vazia = versao_da_fila(matriz)
    assert versao_da_fila(matriz) == vazia        # nada mudou
    bater_ponto(ana, matriz)
    com_ana = versao_da_fila(matriz)
    assert com_ana != vazia
    bater_ponto(bia, centro)                      # outra loja
    assert versao_da_fila(matriz) == com_ana
    vou_atender(ana, matriz)
    atendendo = versao_da_fila(matriz)
    assert atendendo != com_ana
    from fila.acoes import Lancamento, finalizar

    finalizar(ana, matriz, Lancamento("nao_vendeu",
                                      motivo_id=cadastros(empresa).motivo.pk))
    assert versao_da_fila(matriz) != atendendo
    sair_da_loja(ana, matriz)
    assert versao_da_fila(matriz) != atendendo
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `$PYTEST tests/test_fila_acoes.py tests/test_fila_estado.py`
Esperado: FAIL com `ModuleNotFoundError: No module named 'fila.acoes'` (e `fila.valores`).

- [ ] **Step 4: O valor digitado**

`fila/valores.py`:

```python
"""O valor que o vendedor digita no celular, lido como dinheiro.

O teclado decimal do celular brasileiro dá vírgula; o de computador, às vezes
ponto; e quem copia de um orçamento traz "R$ 1.500,50". As três formas
precisam dar o mesmo número, e o que não for número vira `None` (a ação
recusa com frase) em vez de uma exceção.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

__all__ = ["ler_valor"]

_NUMERO = re.compile(r"\d+(?:\.\d+)?")
#: Um ponto só, seguido de exatamente três dígitos: é milhar ("2.000"), e não
#: decimal. Ninguém digita preço com três casas; quem digita "2.000" quer dois
#: mil, e ler dois reais seria a venda sumindo do ranking sem erro nenhum.
_MILHAR = re.compile(r"\d{1,3}(?:\.\d{3})+")


def ler_valor(texto: str) -> "Decimal | None":
    limpo = (texto or "").replace("R$", "").replace(" ", "").strip()
    if not limpo:
        return None
    if "," in limpo:
        # Com vírgula, ela é a decimal e os pontos são de milhar.
        if limpo.count(",") > 1:
            return None
        limpo = limpo.replace(".", "").replace(",", ".")
    elif _MILHAR.fullmatch(limpo):
        limpo = limpo.replace(".", "")
    if not _NUMERO.fullmatch(limpo):
        return None
    try:
        return Decimal(limpo).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
```

- [ ] **Step 5: O retrato e a versão**

`fila/estado.py`:

```python
"""A fila de uma loja, lida: quem atende, quem espera (em ordem), quem pausa.

Tudo aqui lê por `objects.da_empresa(filial.empresa)` e filtra pela loja: a
consulta que esquecesse a loja traria a fila da empresa inteira, e a que
esquecesse a empresa viria vazia (`contas/inquilino.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Max

from .models import Estado, LugarNaFila, Pausa

__all__ = ["Linha", "Retrato", "na_fila", "nome_de", "posicao_de",
           "retrato", "versao_da_fila"]


def nome_de(pessoa) -> str:
    return (getattr(pessoa, "nome", "") or "").strip() or pessoa.email


def _da_loja(filial):
    return LugarNaFila.objects.da_empresa(filial.empresa).filter(filial=filial)


def na_fila(filial):
    """Quem espera, em ordem. O `pk` desempata o improvável empate de hora,
    para a ordem nunca depender de como o banco devolveu as linhas."""
    return (_da_loja(filial).filter(estado=Estado.NA_FILA)
            .select_related("pessoa").order_by("na_fila_desde", "pk"))


def posicao_de(lugar) -> "int | None":
    if lugar.estado != Estado.NA_FILA:
        return None
    for posicao, pk in enumerate(na_fila(lugar.filial).values_list("pk", flat=True), 1):
        if pk == lugar.pk:
            return posicao
    return None


def versao_da_fila(filial) -> str:
    """Muda a cada gravação na fila desta loja, e só então (spec, D8).

    Toda ação grava `desde` (e voltar para a fila grava `na_fila_desde`), e
    sair da loja apaga a linha: quantas linhas há e o maior dos dois instantes
    bastam. Não precisa de tabela de versão, que seria mais uma escrita por
    clique e mais uma coisa para esquecer de atualizar.
    """
    dados = _da_loja(filial).aggregate(
        linhas=Count("pk"), desde=Max("desde"), fila=Max("na_fila_desde"))

    def marca(instante: "datetime | None") -> str:
        return str(int(instante.timestamp() * 1_000_000)) if instante else "0"

    return f"{dados['linhas']}.{marca(dados['desde'])}.{marca(dados['fila'])}"


@dataclass(frozen=True)
class Linha:
    pessoa_id: int
    nome: str
    estado: str
    desde: datetime
    posicao: "int | None"
    tipo_de_pausa: str
    e_voce: bool


@dataclass(frozen=True)
class Retrato:
    versao: str
    atendendo: "list[Linha]"
    fila: "list[Linha]"
    em_pausa: "list[Linha]"
    meu: "Linha | None"


def retrato(filial, pessoa) -> Retrato:
    """A loja inteira numa leitura. `pessoa` pode ser `None` (quem só vê)."""
    pessoa_id = getattr(pessoa, "pk", None)
    lugares = list(_da_loja(filial).select_related("pessoa")
                   .order_by("na_fila_desde", "pk"))
    tipos = dict(Pausa.objects.da_empresa(filial.empresa)
                 .filter(filial=filial, fim__isnull=True)
                 .values_list("pessoa_id", "tipo__nome"))
    posicao = 0
    atendendo, fila, em_pausa = [], [], []
    for lugar in lugares:
        if lugar.estado == Estado.NA_FILA:
            posicao += 1
        linha = Linha(
            pessoa_id=lugar.pessoa_id, nome=nome_de(lugar.pessoa),
            estado=lugar.estado, desde=lugar.desde,
            posicao=posicao if lugar.estado == Estado.NA_FILA else None,
            tipo_de_pausa=tipos.get(lugar.pessoa_id, ""),
            e_voce=lugar.pessoa_id == pessoa_id)
        {Estado.NA_FILA: fila, Estado.ATENDENDO: atendendo,
         Estado.EM_PAUSA: em_pausa}[lugar.estado].append(linha)
    atendendo.sort(key=lambda l: l.desde)
    em_pausa.sort(key=lambda l: l.desde)
    meu = next((l for l in (*atendendo, *fila, *em_pausa) if l.e_voce), None)
    return Retrato(versao=versao_da_fila(filial), atendendo=atendendo,
                   fila=fila, em_pausa=em_pausa, meu=meu)
```

- [ ] **Step 6: As ações**

`fila/acoes.py`:

```python
"""O que o vendedor faz na fila, decidido no servidor e sob trava (D9).

Cada ação:
1. abre transação e tranca a linha da LOJA (`_travar`, desvio D-2 do plano);
2. relê o lugar da pessoa DEPOIS da trava e confere se a ação cabe;
3. grava tudo ou nada;
4. ou levanta `Recusa` com a frase que a tela mostra.

A leitura antes da trava não vale: dois "Vou atender" do mesmo vendedor (dois
toques, dois aparelhos) leriam os dois "na fila", e o segundo estouraria na
restrição do banco com erro 500 em vez de uma frase.

**`irrestritos` aqui dentro, e não `objects`.** Quem chama (a view) já decidiu
a loja pelo contexto da sessão e a passa pronta; as consultas daqui filtram
por essa loja ou pela pessoa, que é de uma conta só. Os cadastros escolhidos
pelo POST são a exceção: vêm de fora, e por isso passam por
`objects.da_empresa`, que recusa o id de outra conta.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from plataforma.models import Filial

from .estado import na_fila, nome_de, posicao_de
from .models import (Atendimento, Estado, GrupoDeItem, ItemVendido,
                     LugarNaFila, MotivoDeNaoVenda, Pausa, Presenca,
                     Resultado, TipoDePausa)

__all__ = ["ItemLancado", "Lancamento", "Recusa", "bater_ponto",
           "cliente_pediu", "finalizar", "pausar", "sair_da_loja",
           "voltar_para_a_fila", "vou_atender"]

NAO_ESTA_NA_LOJA = "Você não está nesta loja. Bata o ponto primeiro."


class Recusa(Exception):
    """A ação não cabe no estado de agora. `frase` vai para a tela como está."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


@dataclass(frozen=True)
class ItemLancado:
    grupo_id: int
    valor: Decimal


@dataclass(frozen=True)
class Lancamento:
    resultado: str
    itens: "tuple[ItemLancado, ...]" = ()
    motivo_id: "int | None" = None
    observacao: str = ""


def _agora():
    """Um ponto só para a hora, para o teste poder fazer o relógio andar."""
    return timezone.now()


def _travar(*filiais) -> None:
    """Tranca a fila das lojas. Em ordem de `pk`: duas ações que trancam as
    mesmas duas lojas em ordens diferentes esperariam uma pela outra para
    sempre."""
    pks = sorted({f.pk for f in filiais})
    list(Filial.objects.select_for_update().filter(pk__in=pks).order_by("pk"))


def _lugar(pessoa_id):
    return (LugarNaFila.irrestritos.select_related("filial", "presenca", "pessoa")
            .filter(pessoa_id=pessoa_id).first())


def _lugar_na_loja(pessoa_id, filial) -> LugarNaFila:
    lugar = _lugar(pessoa_id)
    if lugar is None or lugar.filial_id != filial.pk:
        raise Recusa(NAO_ESTA_NA_LOJA)
    return lugar


def _voltar_ao_fim(lugar, agora) -> None:
    lugar.estado = Estado.NA_FILA
    lugar.na_fila_desde = agora
    lugar.desde = agora
    lugar.save(update_fields=["estado", "na_fila_desde", "desde"])


def _sair(lugar, agora, fechada_por=None) -> None:
    """Fecha pausa aberta e presença, e apaga o lugar. Quem chama já recusou
    (ou fechou) o atendimento aberto."""
    Pausa.irrestritos.filter(pessoa_id=lugar.pessoa_id,
                             fim__isnull=True).update(fim=agora)
    presenca = lugar.presenca
    presenca.saida = agora
    presenca.fechada_por = fechada_por
    presenca.save(update_fields=["saida", "fechada_por"])
    lugar.delete()


def bater_ponto(pessoa, filial) -> None:
    with transaction.atomic():
        antes = _lugar(pessoa.pk)
        _travar(filial, *([antes.filial] if antes else []))
        lugar = _lugar(pessoa.pk)
        if lugar is not None and lugar.filial_id == filial.pk:
            raise Recusa("Você já está nesta loja.")
        if lugar is not None and lugar.estado == Estado.ATENDENDO:
            raise Recusa(f"Você está atendendo em {lugar.filial}. "
                         f"Finalize lá antes de entrar aqui.")
        agora = _agora()
        if lugar is not None:
            # Uma presença aberta por pessoa: chegar numa loja fecha a outra.
            _sair(lugar, agora)
        presenca = Presenca.irrestritos.create(
            empresa=filial.empresa, pessoa=pessoa, filial=filial,
            entrada=agora)
        LugarNaFila.irrestritos.create(
            empresa=filial.empresa, pessoa=pessoa, filial=filial,
            presenca=presenca, estado=Estado.NA_FILA, na_fila_desde=agora,
            desde=agora)


def _abrir_atendimento(lugar, filial, *, pediu: bool) -> None:
    agora = _agora()
    Atendimento.irrestritos.create(
        empresa=filial.empresa, filial=filial, vendedor_id=lugar.pessoa_id,
        presenca=lugar.presenca, inicio=agora, cliente_pediu=pediu)
    lugar.estado = Estado.ATENDENDO
    lugar.desde = agora
    lugar.save(update_fields=["estado", "desde"])


def _exigir_na_fila(lugar) -> None:
    if lugar.estado == Estado.ATENDENDO:
        raise Recusa("Você já está atendendo.")
    if lugar.estado == Estado.EM_PAUSA:
        raise Recusa("Você está em pausa. Volte para a fila primeiro.")


def vou_atender(pessoa, filial) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        _exigir_na_fila(lugar)
        primeiro = na_fila(filial).first()
        if primeiro.pk != lugar.pk:
            raise Recusa(f"A vez é de {nome_de(primeiro.pessoa)}. "
                         f"Você é o {posicao_de(lugar)}º da fila.")
        _abrir_atendimento(lugar, filial, pediu=False)


def cliente_pediu(pessoa, filial) -> None:
    """Fora da vez (D3). Quem estava em primeiro continua em primeiro, porque
    ninguém mais mudou de `na_fila_desde`."""
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        _exigir_na_fila(lugar)
        _abrir_atendimento(lugar, filial, pediu=True)


def _validar(empresa, lancamento, *, ja_usados=frozenset(),
             ja_usado_motivo=None):
    """Confere o lançamento e devolve `(grupos por id, motivo, total)`.

    `ja_usados`/`ja_usado_motivo` servem à correção do gerente (Task 4): o
    grupo que já estava no atendimento continua aceito mesmo desativado
    depois, para corrigir o valor não obrigar a trocar o grupo.
    """
    if lancamento.resultado == Resultado.VENDEU:
        if lancamento.motivo_id is not None:
            raise Recusa("Venda não tem motivo de não venda.")
        if not lancamento.itens:
            raise Recusa("Informe pelo menos um grupo com valor.")
        if any(item.valor is None or item.valor <= 0
               for item in lancamento.itens):
            raise Recusa("Todo valor precisa ser maior que zero.")
        ids = {item.grupo_id for item in lancamento.itens}
        grupos = {g.pk: g for g in GrupoDeItem.objects.da_empresa(empresa)
                  .filter(pk__in=ids)
                  if g.ativo or g.pk in ja_usados}
        if set(grupos) != ids:
            raise Recusa("Grupo de item não encontrado.")
        total = sum((item.valor for item in lancamento.itens), Decimal("0"))
        return grupos, None, total
    if lancamento.resultado == Resultado.NAO_VENDEU:
        if lancamento.itens:
            raise Recusa("Não venda não tem grupo nem valor.")
        motivo = (MotivoDeNaoVenda.objects.da_empresa(empresa)
                  .filter(pk=lancamento.motivo_id).first()
                  if lancamento.motivo_id is not None else None)
        if motivo is None or not (motivo.ativo or motivo.pk == ja_usado_motivo):
            raise Recusa("Escolha o motivo.")
        return {}, motivo, Decimal("0")
    raise Recusa("Escolha se vendeu ou não.")


def _gravar_lancamento(atendimento, lancamento, grupos, motivo, total) -> None:
    atendimento.resultado = lancamento.resultado
    atendimento.motivo = motivo
    atendimento.observacao = (lancamento.observacao.strip()[:280]
                              if motivo is not None else "")
    atendimento.total = total
    atendimento.save(update_fields=["resultado", "motivo", "observacao",
                                    "total", "fechado_por", "fim"])
    atendimento.itens.all().delete()
    # Um a um, e não `bulk_create`: é o `save` do `ModeloDaEmpresa` que
    # preenche a conta, e o `bulk_create` o pula.
    for item in lancamento.itens:
        ItemVendido.irrestritos.create(
            empresa=atendimento.empresa, atendimento=atendimento,
            grupo=grupos[item.grupo_id], valor=item.valor)


def _fechar_atendimento(atendimento, lancamento, agora, fechado_por=None):
    grupos, motivo, total = _validar(atendimento.empresa, lancamento)
    atendimento.fim = agora
    atendimento.fechado_por = fechado_por
    _gravar_lancamento(atendimento, lancamento, grupos, motivo, total)


def finalizar(pessoa, filial, lancamento) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        if lugar.estado != Estado.ATENDENDO:
            raise Recusa("Você não está atendendo.")
        atendimento = Atendimento.irrestritos.get(vendedor=pessoa,
                                                  fim__isnull=True)
        agora = _agora()
        _fechar_atendimento(atendimento, lancamento, agora)
        _voltar_ao_fim(lugar, agora)


def pausar(pessoa, filial, tipo_id) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        _exigir_na_fila(lugar)
        tipo = (TipoDePausa.objects.da_empresa(filial.empresa)
                .filter(pk=tipo_id, ativo=True).first()
                if tipo_id is not None else None)
        if tipo is None:
            raise Recusa("Escolha o tipo de pausa.")
        agora = _agora()
        Pausa.irrestritos.create(empresa=filial.empresa, pessoa=pessoa,
                                 filial=filial, presenca=lugar.presenca,
                                 tipo=tipo, inicio=agora)
        lugar.estado = Estado.EM_PAUSA
        lugar.desde = agora
        lugar.save(update_fields=["estado", "desde"])


def voltar_para_a_fila(pessoa, filial) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        if lugar.estado != Estado.EM_PAUSA:
            raise Recusa("Você não está em pausa.")
        agora = _agora()
        Pausa.irrestritos.filter(pessoa=pessoa, fim__isnull=True).update(
            fim=agora)
        _voltar_ao_fim(lugar, agora)


def sair_da_loja(pessoa, filial) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        if lugar.estado == Estado.ATENDENDO:
            raise Recusa("Finalize o atendimento antes de sair da loja.")
        _sair(lugar, _agora())
```

Nota: `test_quem_nao_bateu_o_ponto_nao_age` exige que `pausar` recuse por "não está na loja" ANTES de olhar o tipo — a ordem acima já faz isso.

- [ ] **Step 7: Rodar e ver passar**

Run: `$PYTEST tests/test_fila_acoes.py tests/test_fila_estado.py`
Esperado: PASS.

- [ ] **Step 8: Quebrar de propósito, uma de cada vez**

1. Em `vou_atender`, apagar o `if primeiro.pk != lugar.pk` → `test_so_o_primeiro_tem_vou_atender` vermelho.
2. Em `_voltar_ao_fim`, tirar `lugar.na_fila_desde = agora` → os dois testes "manda para o fim" vermelhos.
3. Em `_validar`, trocar `item.valor <= 0` por `item.valor < 0` → caso `zero` vermelho.
4. Em `_validar`, trocar `GrupoDeItem.objects.da_empresa(empresa)` por `GrupoDeItem.irrestritos` → caso `outra_empresa` vermelho.
5. Em `versao_da_fila`, tirar `linhas` da string → `test_a_versao_muda...` vermelho no `sair_da_loja`? Se não ficar, é porque o máximo muda junto; nesse caso quebre tirando `desde` e veja o `vou_atender` não mudar a versão.
Desfazer cada uma.

- [ ] **Step 9: A concorrência (D9)**

`tests/test_fila_concorrencia.py`:

```python
"""Dois "Vou atender" ao mesmo tempo dão um atendimento e uma recusa, nunca
dois e nunca um erro 500.

Transacional de verdade, com duas threads, cada uma com a própria conexão:
dentro da transação única do `db` normal não há concorrência para provar.

A demora entre ler e gravar é FORÇADA (`_lugar_na_loja` espera depois de
ler). Sem ela as duas threads quase sempre se revezam por sorte, e o teste
passaria com o código sem trava — que é o teste sem dente que a casa não
aceita.
"""

import threading
import time

import pytest
from django.db import connection

from tests.fila_cenario import pessoa_na_loja, sylvia


@pytest.mark.django_db(transaction=True)
def test_dois_vou_atender_simultaneos_dao_um_atendimento_e_uma_recusa(monkeypatch):
    import fila.acoes as acoes
    from fila.models import Atendimento

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    acoes.bater_ponto(ana, matriz)

    ler_de_verdade = acoes._lugar_na_loja

    def ler_devagar(pessoa_id, filial):
        lugar = ler_de_verdade(pessoa_id, filial)
        time.sleep(0.3)
        return lugar

    monkeypatch.setattr(acoes, "_lugar_na_loja", ler_devagar)

    largada = threading.Barrier(2)
    resultados = []

    def tocar():
        try:
            largada.wait()
            acoes.vou_atender(ana, matriz)
            resultados.append("ok")
        except acoes.Recusa:
            resultados.append("recusa")
        except Exception as erro:  # o defeito que este teste existe para pegar
            resultados.append(f"erro: {type(erro).__name__}")
        finally:
            connection.close()

    threads = [threading.Thread(target=tocar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(resultados) == ["ok", "recusa"]
    assert Atendimento.irrestritos.count() == 1
```

Rodar: `$PYTEST tests/test_fila_concorrencia.py` → PASS. **Quebrar:** trocar o corpo de `_travar` por `return` → o teste fica vermelho (`["erro: IntegrityError", "ok"]`). Desfazer. Se o teste da suíte inteira deixar tabelas sujas para o arquivo seguinte, é porque o `transaction=True` já limpa com `flush`; não acrescente limpeza à mão sem ver o erro primeiro.

- [ ] **Step 10: Suíte inteira** em segundo plano, com os números de arquivos do `CLAUDE.md` atualizados se a varredura acusar. Esperado: verde.

- [ ] **Step 11: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: as ações do vendedor na fila, sob trava

Bater o ponto, vou atender, cliente pediu por mim, finalizar com venda ou
não venda, pausa, voltar para a fila e sair da loja viram funções de domínio
em fila/acoes.py. Cada uma tranca a linha da loja, relê o estado da pessoa
depois da trava e grava tudo ou nada; o que não cabe vira Recusa com a
frase da tela.

A trava é a linha da filial, e não as linhas da fila: loja vazia não tem
linha de fila para trancar (desvio D-2 do plano). O teste de concorrência
força a demora entre ler e gravar, porque sem ela duas threads se revezam
por sorte e o teste passaria com o código sem trava.

A ordem é a hora em que se entrou na fila; a versão que a tela consulta é o
número de linhas mais os dois maiores instantes da loja, e não muda quando
outra loja mexe na dela."
```

---

### Task 4: As correções do gerente, com auditoria

**Files:**
- Create: `fila/correcoes.py`, `tests/test_fila_correcoes.py`
- Modify: `fila/valores.py` (acrescenta `em_reais`), `comum/auditoria.py` (`ACOES` e `ROTULOS`), `tests/test_auditoria.py` (`_CENARIOS`)

**Interfaces:**
- Consumes: `fila.acoes` (`Recusa`, `Lancamento`, `_agora`, `_travar`, `_lugar_na_loja`, `_validar`, `_gravar_lancamento`, `_fechar_atendimento`, `_voltar_ao_fim`, `_sair`), `fila.estado.nome_de`.
- Produces:
  - `fila.valores.em_reais(valor: Decimal) -> str` (`Decimal("1800.5")` → `"R$ 1.800,50"`).
  - `fila.correcoes.tirar_da_loja(autor, filial, pessoa_id, lancamento=None, *, request=None)`, `fechar_atendimento(autor, filial, pessoa_id, lancamento, *, request=None)`, `tirar_da_pausa(autor, filial, pessoa_id, *, request=None)`, `editar_lancamento(autor, filial, atendimento_id, lancamento, *, request=None)`, `lancamentos_de_hoje(filial) -> QuerySet[Atendimento]`, `descrever(atendimento) -> str`. Todas levantam `fila.acoes.Recusa`. `autor` é o `Usuario` do ORM.
  - `ACOES.FILA_PESSOA_TIRADA`, `FILA_ATENDIMENTO_FECHADO`, `FILA_PAUSA_ENCERRADA`, `FILA_LANCAMENTO_CORRIGIDO`.
  - **Quem chama confere `fila.gerenciar` no lugar** (a view, Task 6). As funções daqui não conferem permissão: conferem loja, empresa e D-3.

- [ ] **Step 1: O teste que falha**

`tests/test_fila_correcoes.py`:

```python
"""As correções de D7: o que o gerente faz no lugar do vendedor.

Toda correção grava na auditoria e nenhuma reabre o que foi fechado.
"""

from decimal import Decimal

import pytest

from tests.fila_cenario import (  # noqa: F401
    cadastros, nova_loja, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz,
        gerente=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        cad=cadastros(empresa))


def _nao_venda(loja, observacao=""):
    from fila.acoes import Lancamento

    return Lancamento("nao_vendeu", motivo_id=loja.cad.motivo.pk,
                      observacao=observacao)


def _venda(loja, *pares):
    from fila.acoes import ItemLancado, Lancamento

    return Lancamento("vendeu", tuple(ItemLancado(g.pk, Decimal(v))
                                      for g, v in pares))


def _ultima_trilha():
    from contas.models import RegistroDeAuditoria

    return RegistroDeAuditoria.objects.order_by("-pk").first()


def test_em_reais():
    from fila.valores import em_reais

    assert em_reais(Decimal("1800.5")) == "R$ 1.800,50"
    assert em_reais(Decimal("0")) == "R$ 0,00"


def test_tirar_da_loja_quem_esqueceu_de_sair(loja):
    from fila.acoes import bater_ponto
    from fila.correcoes import tirar_da_loja
    from fila.models import LugarNaFila, Presenca

    bater_ponto(loja.ana, loja.matriz)
    tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk)
    assert not LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    presenca = Presenca.irrestritos.get(pessoa=loja.ana)
    assert presenca.saida is not None
    assert presenca.fechada_por == loja.gerente
    trilha = _ultima_trilha()
    assert trilha.acao == "fila_pessoa_tirada"
    assert trilha.alvo == "Ana em Matriz"


def test_tirar_da_loja_quem_esta_atendendo_fecha_como_nao_venda(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender
    from fila.correcoes import tirar_da_loja
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa):
        tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk)   # sem motivo
    tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, _nao_venda(loja))
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.resultado == "nao_vendeu"
    assert atendimento.fechado_por == loja.gerente


def test_fechar_atendimento_manda_o_vendedor_para_o_fim(loja):
    from fila.acoes import bater_ponto, vou_atender
    from fila.correcoes import fechar_atendimento
    from fila.estado import na_fila
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    fechar_atendimento(loja.gerente, loja.matriz, loja.ana.pk,
                       _venda(loja, (loja.cad.grupo, "250")))
    assert [l.pessoa_id for l in na_fila(loja.matriz)] == [loja.bia.pk, loja.ana.pk]
    atendimento = Atendimento.irrestritos.get()
    assert atendimento.fechado_por == loja.gerente
    assert atendimento.total == Decimal("250")
    assert _ultima_trilha().acao == "fila_atendimento_fechado"


def test_tirar_da_pausa(loja):
    from fila.acoes import bater_ponto, pausar
    from fila.correcoes import tirar_da_pausa
    from fila.models import Estado, LugarNaFila, Pausa

    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    tirar_da_pausa(loja.gerente, loja.matriz, loja.ana.pk)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
    assert Pausa.irrestritos.get().fim is not None
    assert _ultima_trilha().detalhe == "Almoço"


def test_editar_lancamento_troca_grupos_e_valores_e_grava_antes_e_depois(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.correcoes import editar_lancamento
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _venda(loja, (loja.cad.grupo, "100")))
    atendimento = Atendimento.irrestritos.get()
    fim = atendimento.fim
    editar_lancamento(loja.gerente, loja.matriz, atendimento.pk, _venda(
        loja, (loja.cad.grupo, "80"), (loja.cad.grupo2, "40")))
    atendimento.refresh_from_db()
    assert atendimento.total == Decimal("120")
    assert atendimento.fim == fim                 # não reabre, não re-fecha
    assert atendimento.itens.count() == 2
    trilha = _ultima_trilha()
    assert trilha.acao == "fila_lancamento_corrigido"
    assert "antes: vendeu R$ 100,00" in trilha.detalhe
    assert "depois: vendeu R$ 120,00" in trilha.detalhe


def test_editar_lancamento_nao_troca_o_resultado(loja):
    from fila.acoes import Recusa, bater_ponto, finalizar, vou_atender
    from fila.correcoes import editar_lancamento
    from fila.models import Atendimento

    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    with pytest.raises(Recusa):
        editar_lancamento(loja.gerente, loja.matriz,
                          Atendimento.irrestritos.get().pk,
                          _venda(loja, (loja.cad.grupo, "10")))


def test_editar_atendimento_aberto_ou_de_outra_loja_e_recusado(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender
    from fila.correcoes import editar_lancamento
    from fila.models import Atendimento

    centro = nova_loja(loja.empresa, "Centro")
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    aberto = Atendimento.irrestritos.get()
    with pytest.raises(Recusa):
        editar_lancamento(loja.gerente, loja.matriz, aberto.pk, _nao_venda(loja))
    with pytest.raises(Recusa):
        editar_lancamento(loja.gerente, centro, aberto.pk, _nao_venda(loja))


def test_ninguem_corrige_a_si_mesmo(loja):
    """Desvio D-3 do plano."""
    from fila.acoes import Recusa, bater_ponto, pausar
    from fila.correcoes import tirar_da_pausa

    bater_ponto(loja.gerente, loja.matriz)
    pausar(loja.gerente, loja.matriz, loja.cad.tipo.pk)
    with pytest.raises(Recusa) as recusa:
        tirar_da_pausa(loja.gerente, loja.matriz, loja.gerente.pk)
    assert recusa.value.frase == "Você não corrige a si mesmo."


def test_correcao_em_quem_esta_em_outra_loja_e_recusada(loja):
    from fila.acoes import Recusa, bater_ponto
    from fila.correcoes import tirar_da_loja

    centro = nova_loja(loja.empresa, "Centro")
    bater_ponto(loja.ana, centro)
    with pytest.raises(Recusa):
        tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk)


def test_lancamentos_de_hoje_so_os_fechados_da_loja(loja):
    from datetime import date

    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.correcoes import lancamentos_de_hoje

    centro = nova_loja(loja.empresa, "Centro")
    for pessoa, filial in ((loja.ana, loja.matriz), (loja.bia, centro)):
        bater_ponto(pessoa, filial)
        vou_atender(pessoa, filial)
        finalizar(pessoa, filial, _nao_venda(loja))
    assert [a.vendedor_id for a in lancamentos_de_hoje(
        loja.matriz, dia=date(2026, 9, 15))] == [loja.ana.pk]
```

A fixture `relogio` começa em 15/09/2026 13:00 UTC (10:00 em São Paulo), e por isso o último teste passa o dia explicitamente: com `timezone.localdate()` ele só passaria nesse dia.

- [ ] **Step 2: Rodar e ver falhar**

Run: `$PYTEST tests/test_fila_correcoes.py`
Esperado: FAIL (`ImportError: cannot import name 'em_reais'`, `No module named 'fila.correcoes'`).

- [ ] **Step 3: `em_reais`**

Acrescentar a `fila/valores.py` (e `"em_reais"` em `__all__`):

```python
def em_reais(valor: Decimal) -> str:
    """`Decimal("1800.5")` -> `"R$ 1.800,50"`. Escrito à mão, e não pelo
    `locale` do sistema: o contêiner da VPS não tem `pt_BR` instalado, e a
    tela sairia "R$ 1,800.50" só em produção."""
    inteiro, _ponto, centavos = f"{valor:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"
```

- [ ] **Step 4: O vocabulário da auditoria**

`comum/auditoria.py`, no lugar do comentário "As ações dos módulos de negócio de cada SaaS entram aqui":

```python
    # As correções da fila do Fila Zero (`fila/correcoes.py`). As ações do
    # próprio vendedor NÃO entram: já são o histórico da fila, e uma linha de
    # trilha por clique afogaria o que a auditoria existe para mostrar.
    FILA_PESSOA_TIRADA = "fila_pessoa_tirada"
    FILA_ATENDIMENTO_FECHADO = "fila_atendimento_fechado"
    FILA_PAUSA_ENCERRADA = "fila_pausa_encerrada"
    FILA_LANCAMENTO_CORRIGIDO = "fila_lancamento_corrigido"
```

E em `ROTULOS`:

```python
    ACOES.FILA_PESSOA_TIRADA: "Pessoa tirada da loja",
    ACOES.FILA_ATENDIMENTO_FECHADO: "Atendimento fechado pelo gerente",
    ACOES.FILA_PAUSA_ENCERRADA: "Pausa encerrada pelo gerente",
    ACOES.FILA_LANCAMENTO_CORRIGIDO: "Lançamento corrigido",
```

Confira o tamanho do campo `acao` (`grep -n "acao = " contas/models.py`): `fila_lancamento_corrigido` tem 25 caracteres.

- [ ] **Step 5: As correções**

`fila/correcoes.py`:

```python
"""O gerente corrige a fila e os lançamentos da loja dele (D7).

Quem chama confere `fila.gerenciar` NO LUGAR (a view, pelo `request.usuario`
já com as permissões do cargo na loja atual): o gerente de uma loja não tem a
permissão em outra, e o supervisor tem na empresa inteira. Aqui se confere o
que a permissão não diz: que a pessoa e o atendimento são DESTA loja, e que
ninguém corrige a si mesmo (desvio D-3 do plano).

Toda correção grava na auditoria dentro da mesma transação: se a trilha
falhar, a correção desfaz junto (ver `comum.auditoria.registrar`).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from comum.auditoria import ACOES, registrar

from .acoes import (Recusa, _agora, _gravar_lancamento, _fechar_atendimento,
                    _lugar_na_loja, _sair, _travar, _validar, _voltar_ao_fim)
from .estado import nome_de
from .models import Atendimento, Estado, Pausa, Resultado
from .valores import em_reais

__all__ = ["descrever", "editar_lancamento", "fechar_atendimento",
           "lancamentos_de_hoje", "tirar_da_loja", "tirar_da_pausa"]

NAO_CORRIGE_A_SI = "Você não corrige a si mesmo."
NAO_ENCONTRADO = "Essa pessoa não está nesta loja."


def descrever(atendimento) -> str:
    if atendimento.resultado == Resultado.VENDEU:
        itens = "; ".join(f"{item.grupo.nome} {em_reais(item.valor)}"
                          for item in atendimento.itens.select_related("grupo")
                          .order_by("pk"))
        return f"vendeu {em_reais(atendimento.total)} ({itens})"
    if atendimento.resultado == Resultado.NAO_VENDEU:
        observacao = f" ({atendimento.observacao})" if atendimento.observacao else ""
        return f"não vendeu: {atendimento.motivo.nome}{observacao}"
    return "aberto"


def _lugar_de_outro(autor, filial, pessoa_id):
    if pessoa_id == autor.pk:
        raise Recusa(NAO_CORRIGE_A_SI)
    try:
        return _lugar_na_loja(pessoa_id, filial)
    except Recusa:
        raise Recusa(NAO_ENCONTRADO) from None


def _alvo(lugar, filial) -> str:
    return f"{nome_de(lugar.pessoa)} em {filial}"


def tirar_da_loja(autor, filial, pessoa_id, lancamento=None, *, request=None):
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        agora = _agora()
        detalhe = ""
        if lugar.estado == Estado.ATENDENDO:
            # Quem esqueceu de sair no meio de um atendimento: o gerente fecha
            # como não venda, com o motivo que escolher. Venda ele lança
            # antes, por "fechar atendimento", sabendo o que foi vendido.
            if lancamento is None or lancamento.resultado != Resultado.NAO_VENDEU:
                raise Recusa("Ela está atendendo. Escolha o motivo da não "
                             "venda para fechar o atendimento.")
            atendimento = Atendimento.irrestritos.get(
                vendedor_id=pessoa_id, fim__isnull=True)
            _fechar_atendimento(atendimento, lancamento, agora,
                                fechado_por=autor)
            detalhe = f"atendimento fechado: {descrever(atendimento)}"
        alvo = _alvo(lugar, filial)
        _sair(lugar, agora, fechada_por=autor)
        registrar(ACOES.FILA_PESSOA_TIRADA, autor, alvo=alvo, detalhe=detalhe,
                  request=request)


def fechar_atendimento(autor, filial, pessoa_id, lancamento, *, request=None):
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.ATENDENDO:
            raise Recusa("Essa pessoa não está atendendo.")
        atendimento = Atendimento.irrestritos.get(vendedor_id=pessoa_id,
                                                  fim__isnull=True)
        agora = _agora()
        _fechar_atendimento(atendimento, lancamento, agora, fechado_por=autor)
        _voltar_ao_fim(lugar, agora)
        registrar(ACOES.FILA_ATENDIMENTO_FECHADO, autor,
                  alvo=_alvo(lugar, filial), detalhe=descrever(atendimento),
                  request=request)


def tirar_da_pausa(autor, filial, pessoa_id, *, request=None):
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.EM_PAUSA:
            raise Recusa("Essa pessoa não está em pausa.")
        pausa = Pausa.irrestritos.select_related("tipo").get(
            pessoa_id=pessoa_id, fim__isnull=True)
        agora = _agora()
        pausa.fim = agora
        pausa.save(update_fields=["fim"])
        _voltar_ao_fim(lugar, agora)
        registrar(ACOES.FILA_PAUSA_ENCERRADA, autor,
                  alvo=_alvo(lugar, filial), detalhe=pausa.tipo.nome,
                  request=request)


def editar_lancamento(autor, filial, atendimento_id, lancamento, *,
                      request=None):
    """Troca o que foi lançado num atendimento FECHADO. Não reabre, não muda
    o fim nem o resultado: corrigir "vendeu" para "não vendeu" apagaria uma
    venda do ranking com um clique, e isso é outra conversa."""
    with transaction.atomic():
        _travar(filial)
        atendimento = (Atendimento.objects.da_empresa(filial.empresa)
                       .select_related("vendedor", "motivo")
                       .filter(pk=atendimento_id, filial=filial,
                               fim__isnull=False).first()
                       if atendimento_id is not None else None)
        if atendimento is None:
            raise Recusa("Lançamento não encontrado.")
        if atendimento.vendedor_id == autor.pk:
            raise Recusa(NAO_CORRIGE_A_SI)
        if lancamento.resultado != atendimento.resultado:
            raise Recusa("O resultado não muda na correção.")
        antes = descrever(atendimento)
        grupos, motivo, total = _validar(
            filial.empresa, lancamento,
            ja_usados=frozenset(atendimento.itens.values_list("grupo_id",
                                                              flat=True)),
            ja_usado_motivo=atendimento.motivo_id)
        _gravar_lancamento(atendimento, lancamento, grupos, motivo, total)
        depois = descrever(atendimento)
        registrar(ACOES.FILA_LANCAMENTO_CORRIGIDO, autor,
                  alvo=f"Atendimento de {nome_de(atendimento.vendedor)} em {filial}",
                  detalhe=f"antes: {antes}; depois: {depois}", request=request)


def lancamentos_de_hoje(filial, dia=None):
    """Os atendimentos fechados da loja no dia local (o de hoje por padrão),
    do mais recente para o mais antigo."""
    dia = dia or timezone.localdate()
    inicio = timezone.make_aware(datetime.combine(dia, time.min))
    return (Atendimento.objects.da_empresa(filial.empresa)
            .filter(filial=filial, fim__gte=inicio,
                    fim__lt=inicio + timedelta(days=1))
            .select_related("vendedor", "motivo").order_by("-fim"))
```

- [ ] **Step 6: Os cenários da auditoria**

`tests/test_auditoria.py`, antes de `_CENARIOS`:

```python
def _loja_com_gente_da_fila():
    """A Matriz com a Zeca na fila, e a dona logada com as permissões da fila.

    Pelo domínio (`fila.acoes`) e não pela tela: o que este arquivo prova é a
    LINHA da trilha, e a tela da fila tem os testes dela
    (`tests/test_fila_pagina.py`)."""
    from contas.models import Usuario
    from fila.acoes import bater_ponto
    from tests.fila_cenario import cadastros

    _cliente_logado("dona-fila", permissoes=(
        "fila_ver", "fila_participar", "fila_gerenciar", "fila_cadastros"))
    dona = Usuario.objects.get(email=email_de("dona-fila"))
    empresa, matriz = empresa_do_teste(), matriz_do_teste()
    zeca = Usuario.objects.create_user(email=email_de("zeca"), password=SENHA,
                                       nome="Zeca")
    alocar(zeca, empresa, "vendedor", filial=matriz)
    bater_ponto(zeca, matriz)
    return dona, zeca, matriz, cadastros(empresa)


def _cenario_fila_pessoa_tirada():
    from fila.correcoes import tirar_da_loja

    dona, zeca, matriz, _cad = _loja_com_gente_da_fila()
    tirar_da_loja(dona, matriz, zeca.pk)
    return email_de("dona-fila"), f"Zeca em {matriz}"


def _cenario_fila_atendimento_fechado():
    from fila.acoes import Lancamento, vou_atender
    from fila.correcoes import fechar_atendimento

    dona, zeca, matriz, cad = _loja_com_gente_da_fila()
    vou_atender(zeca, matriz)
    fechar_atendimento(dona, matriz, zeca.pk,
                       Lancamento("nao_vendeu", motivo_id=cad.motivo.pk))
    return email_de("dona-fila"), f"Zeca em {matriz}"


def _cenario_fila_pausa_encerrada():
    from fila.acoes import pausar
    from fila.correcoes import tirar_da_pausa

    dona, zeca, matriz, cad = _loja_com_gente_da_fila()
    pausar(zeca, matriz, cad.tipo.pk)
    tirar_da_pausa(dona, matriz, zeca.pk)
    return email_de("dona-fila"), f"Zeca em {matriz}"


def _cenario_fila_lancamento_corrigido():
    from fila.acoes import Lancamento, finalizar, vou_atender
    from fila.correcoes import editar_lancamento
    from fila.models import Atendimento

    dona, zeca, matriz, cad = _loja_com_gente_da_fila()
    vou_atender(zeca, matriz)
    finalizar(zeca, matriz, Lancamento("nao_vendeu", motivo_id=cad.motivo.pk))
    editar_lancamento(dona, matriz, Atendimento.irrestritos.get().pk,
                      Lancamento("nao_vendeu", motivo_id=cad.motivo.pk,
                                 observacao="voltou depois"))
    return email_de("dona-fila"), f"Atendimento de Zeca em {matriz}"
```

e em `_CENARIOS`:

```python
    "FILA_PESSOA_TIRADA": _cenario_fila_pessoa_tirada,
    "FILA_ATENDIMENTO_FECHADO": _cenario_fila_atendimento_fechado,
    "FILA_PAUSA_ENCERRADA": _cenario_fila_pausa_encerrada,
    "FILA_LANCAMENTO_CORRIGIDO": _cenario_fila_lancamento_corrigido,
```

Acrescentar `matriz_do_teste` ao `from tests.conftest import (...)` do topo se ainda não estiver lá. A `_cliente_logado` promove a dona a titular com as permissões diretas pedidas; a Zeca entra na conta dela pelo `com_vinculo` do arquivo.

- [ ] **Step 7: Rodar e ver passar**

Run: `$PYTEST tests/test_fila_correcoes.py tests/test_auditoria.py`
Esperado: PASS.

- [ ] **Step 8: Quebrar de propósito**

1. Tirar o `if pessoa_id == autor.pk` → `test_ninguem_corrige_a_si_mesmo` vermelho.
2. Em `editar_lancamento`, tirar `fim__isnull=False` → `test_editar_atendimento_aberto...` vermelho.
3. Comentar o `registrar` de `tirar_da_pausa` → o parametrizado `FILA_PAUSA_ENCERRADA` de `test_auditoria.py` vermelho.
Desfazer.

- [ ] **Step 9: Suíte inteira** em segundo plano; números de arquivos do `CLAUDE.md`. Esperado: verde.

- [ ] **Step 10: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: o gerente corrige a fila da loja dele

Tirar da loja quem esqueceu de sair (fechando o atendimento aberto como não
venda, com o motivo que ele escolher), fechar o atendimento no lugar do
vendedor, tirar da pausa e corrigir o lançamento de um atendimento fechado.

A permissão é conferida por quem chama, no lugar em que a sessão está; aqui
se confere o que a permissão não diz: a pessoa e o atendimento são desta
loja, e ninguém corrige a si mesmo (desvio D-3 do plano). Corrigir não
reabre e não troca vendeu por não vendeu.

Cada correção grava na auditoria na mesma transação, com o antes e o depois
no detalhe; os quatro nomes novos têm cenário em test_auditoria.py."
```

---

### Task 5: Os três cadastros no dashboard

**Files:**
- Create: `fila/views_cadastros.py`, `tests/test_fila_cadastros.py`
- Modify: `fila/urls.py`, `comum/auditoria.py`, `tests/test_auditoria.py`

**Interfaces:**
- Consumes: `GrupoDeItem`, `MotivoDeNaoVenda`, `TipoDePausa` (Task 2); `fila.cadastros` (Task 1).
- Produces: rotas `fila_grupos` (`/fila/grupos`), `fila_motivos` (`/fila/motivos`), `fila_pausas` (`/fila/pausas`); POST com `acao` ∈ `criar`/`salvar`/`remover`, campos `nome`, `ordem`, `ativo` (`"1"` marcado) e `id`; `ACOES.FILA_CADASTRO_CRIADO/EDITADO/REMOVIDO` com alvo `"<Rótulo do cadastro>: <nome>"` (ex.: `"Grupo de item: Sofás"`).

- [ ] **Step 1: O teste que falha**

`tests/test_fila_cadastros.py`:

```python
"""Grupos de item, motivos de não venda e tipos de pausa (spec, "Cadastros").

Os três são a mesma tela com outro model; o parametrizado prova os três de
uma vez, e uma tela que divergir das outras fica vermelha sozinha.
"""

import pytest
from django.urls import reverse

from tests.fila_cenario import logado, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db

TELAS = [("fila_grupos", "GrupoDeItem", "Grupo de item"),
         ("fila_motivos", "MotivoDeNaoVenda", "Motivo de não venda"),
         ("fila_pausas", "TipoDePausa", "Tipo de pausa")]


def _model(nome):
    import fila.models

    return getattr(fila.models, nome)


@pytest.mark.parametrize("rota, model, rotulo", TELAS)
def test_criar_editar_desativar_e_remover(rota, model, rotulo):
    from contas.models import RegistroDeAuditoria

    empresa, _, _ = sylvia()
    cliente = logado("sylvia")
    Model = _model(model)

    assert cliente.post(reverse(rota), {"acao": "criar", "nome": "Primeiro",
                                        "ordem": "2"}).status_code == 302
    linha = Model.irrestritos.get(empresa=empresa)
    assert (linha.nome, linha.ordem, linha.ativo) == ("Primeiro", 2, True)
    assert RegistroDeAuditoria.objects.filter(
        acao="fila_cadastro_criado", alvo=f"{rotulo}: Primeiro").exists()

    cliente.post(reverse(rota), {"acao": "salvar", "id": str(linha.pk),
                                 "nome": "Renomeado", "ordem": "1"})
    linha.refresh_from_db()
    assert (linha.nome, linha.ordem, linha.ativo) == ("Renomeado", 1, False)

    cliente.post(reverse(rota), {"acao": "remover", "id": str(linha.pk)})
    assert not Model.irrestritos.filter(pk=linha.pk).exists()


@pytest.mark.parametrize("rota, model, rotulo", TELAS)
def test_nome_repetido_sem_diferenca_de_caixa_responde_com_frase(rota, model, rotulo):
    empresa, _, _ = sylvia()
    _model(model).irrestritos.create(empresa=empresa, nome="Almoço")
    resposta = logado("sylvia").post(reverse(rota), {
        "acao": "criar", "nome": "ALMOÇO", "ordem": "0"})
    assert resposta.status_code == 200
    assert "Já existe" in resposta.content.decode()


def test_cadastro_usado_nao_se_remove_e_a_tela_diz_por_que():
    from datetime import datetime, timezone as tz

    from fila.models import Pausa, Presenca, TipoDePausa

    empresa, matriz, _ = sylvia()
    ana = pessoa_na_loja("ana", empresa, matriz)
    tipo = TipoDePausa.irrestritos.create(empresa=empresa, nome="Café")
    agora = datetime(2026, 9, 15, 13, tzinfo=tz.utc)
    presenca = Presenca.irrestritos.create(empresa=empresa, filial=matriz,
                                           pessoa=ana, entrada=agora,
                                           saida=agora)
    Pausa.irrestritos.create(empresa=empresa, filial=matriz, pessoa=ana,
                             presenca=presenca, tipo=tipo, inicio=agora,
                             fim=agora)
    resposta = logado("sylvia").post(reverse("fila_pausas"), {
        "acao": "remover", "id": str(tipo.pk)})
    assert resposta.status_code == 200
    assert "Em uso: desative em vez de remover." in resposta.content.decode()
    assert TipoDePausa.irrestritos.filter(pk=tipo.pk).exists()


def test_id_de_outra_conta_no_post_nao_e_encontrado():
    from fila.models import GrupoDeItem
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    sylvia()
    outra = Empresa.objects.create(razao_social="Concorrente",
                                   nome_fantasia="Concorrente")
    abrir_conta(outra, "concorrente")
    outra.refresh_from_db()
    alheio = GrupoDeItem.irrestritos.create(empresa=outra, nome="Sofás")
    resposta = logado("sylvia").post(reverse("fila_grupos"), {
        "acao": "remover", "id": str(alheio.pk)})
    assert "não encontrado" in resposta.content.decode()
    assert GrupoDeItem.irrestritos.filter(pk=alheio.pk).exists()


def test_sem_fila_cadastros_a_tela_nao_existe():
    empresa, matriz, _ = sylvia()
    pessoa_na_loja("gil", empresa, matriz, cargo="gerente")
    assert logado("gil").get(reverse("fila_grupos")).status_code == 404


def test_a_lista_mostra_so_a_empresa_do_contexto():
    from fila.models import GrupoDeItem

    empresa, _, _ = sylvia()
    GrupoDeItem.irrestritos.create(empresa=empresa, nome="Sofás")
    html = logado("sylvia").get(reverse("fila_grupos")).content.decode()
    assert "Sofás" in html
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `$PYTEST tests/test_fila_cadastros.py`
Esperado: FAIL (`NoReverseMatch: 'fila_grupos'`).

- [ ] **Step 3: O vocabulário**

`comum/auditoria.py`, depois das correções da fila:

```python
    # Os três cadastros da fila; o alvo leva o nome do cadastro na frente
    # ("Grupo de item: Sofás"), porque os três dividem as mesmas três ações.
    FILA_CADASTRO_CRIADO = "fila_cadastro_criado"
    FILA_CADASTRO_EDITADO = "fila_cadastro_editado"
    FILA_CADASTRO_REMOVIDO = "fila_cadastro_removido"
```

`ROTULOS`: `"Cadastro da fila criado"`, `"Cadastro da fila editado"`, `"Cadastro da fila removido"`.

- [ ] **Step 4: A tela**

`fila/views_cadastros.py`:

```python
"""Grupos de item, motivos de não venda e tipos de pausa.

Uma tela para os três, e não três cópias: são a mesma tabela (nome, ordem,
ativo) com outro model, e três cópias divergiriam no primeiro ajuste. O que
muda de uma para outra mora em `Cadastro` (o dataclass abaixo).

Padrão da casa (R46): filtro, ordenação e paginação; criar e editar em modal;
uma rota com `acao` no POST. **Cadastro usado não se remove** (a FK dos
lançamentos é `PROTECT`), e a tela diz "em uso, desative" em vez de estourar.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.pedido import id_do_post
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import (
    Alert, Box, Button, Card, Checkbox, Column, Form, FormGrid, IconButton,
    Modal, PageHeader, Raw, Table, TextInput,
)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from .models import GrupoDeItem, MotivoDeNaoVenda, TipoDePausa

__all__ = ["grupos", "motivos", "pausas"]


@dataclass(frozen=True)
class Cadastro:
    model: type
    rota: str
    titulo: str
    rotulo: str
    subtitulo: str
    novo: str


GRUPOS = Cadastro(GrupoDeItem, "fila_grupos", _("Grupos de item"),
                  "Grupo de item",
                  _("O que se vende: o vendedor escolhe o grupo ao lançar a venda."),
                  _("Novo grupo"))
MOTIVOS = Cadastro(MotivoDeNaoVenda, "fila_motivos", _("Motivos de não venda"),
                   "Motivo de não venda",
                   _("Por que o cliente não comprou: um motivo por atendimento."),
                   _("Novo motivo"))
PAUSAS = Cadastro(TipoDePausa, "fila_pausas", _("Tipos de pausa"),
                  "Tipo de pausa",
                  _("Por que o vendedor saiu da fila por um tempo."),
                  _("Novo tipo"))

NAO_ENCONTRADO = _("Cadastro não encontrado.")
EM_USO = _("Em uso: desative em vez de remover.")

_ORDENAVEIS = {"nome": "nome", "ordem": ("ordem", "nome"),
               "ativo": ("-ativo", "nome")}
_FILTRAVEIS = {
    "nome": ColunaFiltravel("nome", "Nome"),
    "ativo": ColunaFiltravel("ativo", "Situação", tipo="opcoes",
                             opcoes=lambda: [("True", "Ativo"),
                                             ("False", "Inativo")]),
}


def _linhas(request, cadastro):
    return cadastro.model.objects.do_contexto(request)


def _oculto(nome: str, valor: str) -> Raw:
    """`valor` é sempre um `pk` ou uma constante desta view."""
    return Raw(html=format_html('<input type="hidden" name="{}" value="{}">',
                                nome, valor))


def _campos(nome="", ordem=0, ativo=True, com_ativo=False):
    campos = [
        TextInput(name="nome", label=_("Nome"), span=8, value=nome,
                  required=True, maxlength=80),
        TextInput(name="ordem", label=_("Ordem"), span=4, type="number",
                  value=str(ordem)),
    ]
    if com_ativo:
        campos.append(Checkbox(
            name="ativo", value="1", label=_("Ativo"), checked=ativo,
            help=_("Desativado some das opções do vendedor e continua nos "
                   "lançamentos antigos.")))
    return FormGrid(children=campos)


def _modais(request, cadastro, linhas) -> list:
    acao = reverse(cadastro.rota)
    modais = [Modal(id="cadastro-criar", title=cadastro.novo, body=Form(
        action=acao, children=[
            Raw(html=campo_csrf(request)), _oculto("acao", "criar"),
            _campos(), Button(label=_("Criar"), variant="primary",
                              type="submit")]))]
    for linha in linhas:
        modais.append(Modal(
            id=f"cadastro-{linha.pk}-editar", title=f"Editar {linha.nome}",
            body=Form(action=acao, children=[
                Raw(html=campo_csrf(request)), _oculto("acao", "salvar"),
                _oculto("id", str(linha.pk)),
                _campos(linha.nome, linha.ordem, linha.ativo, com_ativo=True),
                Button(label=_("Salvar"), variant="primary", type="submit")])))
        modais.append(Modal(
            id=f"cadastro-{linha.pk}-remover", title=_("Remover"),
            body=Form(action=acao, children=[
                Raw(html=campo_csrf(request)), _oculto("acao", "remover"),
                _oculto("id", str(linha.pk)),
                Alert(tone="danger", message=(
                    f'Remover "{linha.nome}"? Só é possível se nunca foi '
                    f'usado em um lançamento.')),
                Button(label=_("Remover"), variant="danger", type="submit")])))
    return modais


def _acoes_da_linha(linha) -> Box:
    return Box(direction="row", gap="sm", wrap=False, align="end",
               cross="center", body=[
                   IconButton(icon="edit", title=_("Editar"), attrs={
                       "data-open-modal": f"cadastro-{linha.pk}-editar"}),
                   IconButton(icon="trash", title=_("Remover"), attrs={
                       "data-open-modal": f"cadastro-{linha.pk}-remover"}),
               ])


def _desenhar(request, cadastro, erro=None) -> HttpResponse:
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        listagem = montar_pagina(request, _linhas(request, cadastro),
                                 ordenaveis=_ORDENAVEIS, padrao="ordem",
                                 filtraveis=_FILTRAVEIS)
        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=cadastro.titulo, subtitle=cadastro.subtitulo,
                       actions=[Button(label=cadastro.novo, variant="primary",
                                       attrs={"data-open-modal": "cadastro-criar"})]),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))
        conteudo.append(Card(title=cadastro.titulo, padded=False, body=[
            listagem.barra,
            Table(columns=[
                Column("nome", listagem.cabecalho("nome", "Nome"), strong=True),
                Column("ordem", listagem.cabecalho("ordem", "Ordem"),
                       align="center"),
                Column("ativo", listagem.cabecalho("ativo", "Situação"),
                       render=lambda l: "Ativo" if l.ativo else "Inativo"),
            ], rows=listagem.linhas, row_actions=_acoes_da_linha),
            listagem.paginacao,
        ]))
        pagina = site.page(
            title=cadastro.titulo, width="full",
            stylesheets=["/static/plataforma/listagem.css"],
            content=conteudo, crumbs=[Crumb(cadastro.titulo)],
            user=getattr(request, "usuario", None),
            overlays=_modais(request, cadastro, listagem.linhas))
        return render(pagina)


def _ler(request):
    nome = (request.POST.get("nome") or "").strip()[:80]
    try:
        ordem = max(0, int(request.POST.get("ordem") or 0))
    except ValueError:
        ordem = 0
    return nome, ordem, request.POST.get("ativo") == "1"


def _alvo(cadastro, linha) -> str:
    return f"{cadastro.rotulo}: {linha.nome}"


def _tela(request, cadastro) -> HttpResponse:
    if request.method != "POST":
        return _desenhar(request, cadastro)
    acao = request.POST.get("acao", "")
    empresa = empresa_atual(request)
    if empresa is None:
        return _desenhar(request, cadastro, erro=_(
            "Escolha uma empresa no cabeçalho antes de cadastrar."))

    if acao == "criar":
        nome, ordem, _ativo = _ler(request)
        if not nome:
            return _desenhar(request, cadastro, erro=_("Informe o nome."))
        try:
            with transaction.atomic():
                linha = cadastro.model.irrestritos.create(
                    empresa=empresa, nome=nome, ordem=ordem)
                registrar(ACOES.FILA_CADASTRO_CRIADO, request.usuario,
                          alvo=_alvo(cadastro, linha), request=request)
        except IntegrityError:
            return _desenhar(request, cadastro,
                             erro=f'Já existe "{nome}" nesta lista.')
        return HttpResponseRedirect(reverse(cadastro.rota))

    linha = _linhas(request, cadastro).filter(
        pk=id_do_post(request, "id")).first()
    if linha is None:
        return _desenhar(request, cadastro, erro=NAO_ENCONTRADO)

    if acao == "salvar":
        nome, ordem, ativo = _ler(request)
        if not nome:
            return _desenhar(request, cadastro, erro=_("Informe o nome."))
        antes = _alvo(cadastro, linha)
        try:
            with transaction.atomic():
                linha.nome, linha.ordem, linha.ativo = nome, ordem, ativo
                linha.save(update_fields=["nome", "ordem", "ativo"])
                registrar(ACOES.FILA_CADASTRO_EDITADO, request.usuario,
                          alvo=_alvo(cadastro, linha),
                          detalhe=f"era {antes}; {'ativo' if ativo else 'inativo'}",
                          request=request)
        except IntegrityError:
            return _desenhar(request, cadastro,
                             erro=f'Já existe "{nome}" nesta lista.')
        return HttpResponseRedirect(reverse(cadastro.rota))

    if acao == "remover":
        try:
            with transaction.atomic():
                registrar(ACOES.FILA_CADASTRO_REMOVIDO, request.usuario,
                          alvo=_alvo(cadastro, linha), request=request)
                linha.delete()
        except ProtectedError:
            # O `atomic` desfaz o registro junto: a trilha não conta uma
            # remoção que não aconteceu.
            return _desenhar(request, cadastro, erro=EM_USO)
        return HttpResponseRedirect(reverse(cadastro.rota))

    return HttpResponseRedirect(reverse(cadastro.rota))


@exigir_permissao("fila.cadastros")
@exigir_modulo_ligado("fila")
def grupos(request) -> HttpResponse:
    return _tela(request, GRUPOS)


@exigir_permissao("fila.cadastros")
@exigir_modulo_ligado("fila")
def motivos(request) -> HttpResponse:
    return _tela(request, MOTIVOS)


@exigir_permissao("fila.cadastros")
@exigir_modulo_ligado("fila")
def pausas(request) -> HttpResponse:
    return _tela(request, PAUSAS)
```

A `IntegrityError` dentro de `transaction.atomic()` desfaz só o bloco; a view continua usável.

`fila/urls.py`:

```python
from django.urls import path

from . import views, views_cadastros  # noqa: F401

urlpatterns = [
    path("fila/grupos", views_cadastros.grupos, name="fila_grupos"),
    path("fila/motivos", views_cadastros.motivos, name="fila_motivos"),
    path("fila/pausas", views_cadastros.pausas, name="fila_pausas"),
]
```

- [ ] **Step 5: Cenários da auditoria**

`tests/test_auditoria.py`:

```python
def _cenario_fila_cadastro_criado():
    cliente = _cliente_logado("dona-cad", permissoes=("fila_ver", "fila_cadastros"))
    cliente.post(reverse("fila_grupos"), {"acao": "criar", "nome": "Sofás",
                                          "ordem": "0"})
    return email_de("dona-cad"), "Grupo de item: Sofás"


def _cenario_fila_cadastro_editado():
    from fila.models import MotivoDeNaoVenda

    cliente = _cliente_logado("dona-cad", permissoes=("fila_ver", "fila_cadastros"))
    motivo = MotivoDeNaoVenda.irrestritos.create(empresa=empresa_do_teste(),
                                                 nome="Caro")
    cliente.post(reverse("fila_motivos"), {"acao": "salvar", "id": str(motivo.pk),
                                           "nome": "Achou caro", "ordem": "0",
                                           "ativo": "1"})
    return email_de("dona-cad"), "Motivo de não venda: Achou caro"


def _cenario_fila_cadastro_removido():
    from fila.models import TipoDePausa

    cliente = _cliente_logado("dona-cad", permissoes=("fila_ver", "fila_cadastros"))
    tipo = TipoDePausa.irrestritos.create(empresa=empresa_do_teste(), nome="Café")
    cliente.post(reverse("fila_pausas"), {"acao": "remover", "id": str(tipo.pk)})
    return email_de("dona-cad"), "Tipo de pausa: Café"
```

e as três chaves `"FILA_CADASTRO_CRIADO"`, `"FILA_CADASTRO_EDITADO"`, `"FILA_CADASTRO_REMOVIDO"` em `_CENARIOS`. Nos cenários de editar e remover, a empresa só tem titular depois de `_cliente_logado`, por isso o `create` vem depois dele.

- [ ] **Step 6: Rodar e ver passar**

Run: `$PYTEST tests/test_fila_cadastros.py tests/test_auditoria.py tests/test_regra_tabela.py tests/test_guarda.py tests/test_personificacao.py tests/test_id_do_post.py`
Esperado: PASS. `test_regra_tabela.py` visita `/fila/grupos` como superusuário: se ela acusar filtro ou paginação faltando, é a tela; não isente.

- [ ] **Step 7: Quebrar de propósito**

1. Trocar `_linhas(...).filter(pk=...)` por `cadastro.model.irrestritos.filter(pk=...)` → `test_id_de_outra_conta...` vermelho.
2. Tirar o `except ProtectedError` → `test_cadastro_usado...` vermelho (500).
3. Tirar `listagem.barra` → `test_regra_tabela.py` vermelho.
Desfazer.

- [ ] **Step 8: Suíte inteira** em segundo plano; números do `CLAUDE.md`. Esperado: verde.

- [ ] **Step 9: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: os cadastros da fila no dashboard

Grupos de item, motivos de não venda e tipos de pausa ganham tela no grupo
Cadastro, com filtro, ordenação e paginação (R46), criar e editar em modal e
remover só o que nunca foi usado. Os três são uma tela só com outro model:
três cópias divergiriam no primeiro ajuste.

Cadastro usado é PROTECT nos lançamentos; a tela responde 'em uso, desative
em vez de remover' em vez de 500, e o registro da remoção se desfaz junto.
O nome repetido sem diferença de caixa, recusado pelo banco, vira frase.

Criar, editar e remover vão para a auditoria com o nome do cadastro no alvo."
```

---

### Task 6: A página `/fila` servida pelo servidor (sem JavaScript)

A página inteira funciona com formulários e links comuns: cada ação é um POST
que volta para `/fila`, e as folhas (finalizar, pausa, tirar da loja, editar)
abrem por `?folha=` na própria URL. A Task 7 põe o visual aprovado e o
JavaScript por cima, sem mudar o HTML de forma que esta tarefa perca valor.

**Files:**
- Create: `fila/ambiente.py`, `fila/tela.py`, `fila/templates/fila/pagina.html`, `_painel.html`, `_lista.html`, `_barra.html`, `_folhas.html`, `_lancamentos.html`, `sem_loja.html`, `fila/static/fila/fila.css` e `fila/static/fila/fila.js` (vazios, só com o comentário de cabeçalho; a Task 7 preenche), `tests/test_fila_pagina.py`
- Modify: `fila/views.py`, `fila/urls.py`

**Interfaces:**
- Consumes: `fila.acoes.*`, `fila.correcoes.*`, `fila.estado.retrato/versao_da_fila/nome_de`, `fila.valores.ler_valor/em_reais`.
- Produces:
  - Rotas: `inicio` (`/`), `fila` (`/fila`), `fila_estado` (`GET /fila/estado?versao=`), `fila_agir` (`POST /fila/agir`).
  - `POST /fila/agir` campos: `acao` ∈ `ponto`, `atender`, `cliente_pediu`, `finalizar`, `pausar`, `voltar`, `sair` (vendedor, `fila.participar`) e `tirar`, `fechar`, `tirar_pausa`, `editar` (gerente, `fila.gerenciar`); `pessoa` (id, nas do gerente), `atendimento` (id, em `editar`), `tipo` (id), `resultado`, listas `grupo`/`valor`, `motivo` (id), `observacao`.
  - Com cabeçalho `X-Fila: 1` o POST responde JSON `{"ok": bool, "frase": str, "versao": str, "html": {"painel", "lista", "barra", "lancamentos"}}`; sem ele, redireciona para `/fila` e guarda a recusa em `request.session["fila:recusa"]`.
  - `GET /fila/estado?versao=X` responde `{"versao": str, "mudou": false}` quando nada mudou, ou `{"versao", "mudou": true, "html": {...}}`.
  - IDs de elementos que a Task 7 usa: `#fila-painel`, `#fila-lista`, `#fila-barra`, `#fila-lancamentos`, `#fila-recusa`; `<body data-estado-url data-agir-url data-versao>`; folhas `<dialog id="folha-finalizar|folha-pausa|folha-tirar|folha-editar">`; links que abrem folha levam `data-folha="finalizar"` (e `data-pessoa`); formulários de ação levam `data-acao`; linha de item de venda `.item-vendido` com `select[name=grupo]` e `input[name=valor]`; `<output class="total">`; tempo relativo `<time data-desde="ISO">`.
  - `fila.tela.so_a_fila(user) -> bool` (D-4).

- [ ] **Step 1: O teste que falha**

`tests/test_fila_pagina.py`:

```python
"""A página da fila vista por quem a usa: vendedor, gerente, supervisor.

Pelo `django.test.Client`, sem navegador. Cada teste diz a regra; os de
permissão e isolamento são os que o spec lista em "Como se prova".
"""

import json
from types import SimpleNamespace

import pytest
from django.urls import reverse

from tests.fila_cenario import (  # noqa: F401
    cadastros, logado, nova_loja, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz,
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        gil=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        cad=cadastros(empresa))


def _agir(cliente, **dados):
    return cliente.post(reverse("fila_agir"), dados)


def _agir_js(cliente, **dados):
    resposta = cliente.post(reverse("fila_agir"), dados, HTTP_X_FILA="1")
    return json.loads(resposta.content)


def _html(cliente, url="/fila"):
    resposta = cliente.get(url)
    assert resposta.status_code == 200
    return resposta.content.decode()


# --- O caminho do vendedor ---------------------------------------------------

def test_vendedor_bate_o_ponto_e_e_a_vez_dele(loja):
    ana = logado("ana")
    assert "Bater o ponto" in _html(ana)
    assert _agir(ana, acao="ponto").status_code == 302
    html = _html(ana)
    assert "É a sua vez" in html
    assert "Vou atender" in html


def test_o_segundo_ve_a_posicao(loja):
    _agir(logado("ana"), acao="ponto")
    bia = logado("bia")
    _agir(bia, acao="ponto")
    html = _html(bia)
    assert "Sua vez em" in html
    assert "uma pessoa na sua frente" in html
    assert "Cliente pediu por mim" in html


def test_finalizar_com_venda_pela_pagina(loja):
    from fila.models import Atendimento

    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    assert 'name="grupo"' in _html(ana, "/fila?folha=finalizar")
    _agir(ana, acao="finalizar", resultado="vendeu",
          grupo=[str(loja.cad.grupo.pk), str(loja.cad.grupo2.pk), ""],
          valor=["1.500,50", "300", ""])
    atendimento = Atendimento.irrestritos.get()
    assert str(atendimento.total) == "1800.50"


def test_recusa_sem_javascript_aparece_uma_vez(loja):
    _agir(logado("ana"), acao="ponto")
    bia = logado("bia")
    _agir(bia, acao="ponto")
    _agir(bia, acao="atender")
    assert "A vez é de Ana. Você é o 2º da fila." in _html(bia)
    assert "A vez é de Ana" not in _html(bia)


def test_acao_com_javascript_devolve_o_estado_novo(loja):
    resposta = _agir_js(logado("ana"), acao="ponto")
    assert resposta["ok"] is True
    assert "É a sua vez" in resposta["html"]["painel"]
    assert set(resposta["html"]) == {"painel", "lista", "barra", "lancamentos"}
    recusa = _agir_js(logado("ana"), acao="ponto")
    assert recusa == {**recusa, "ok": False, "frase": "Você já está nesta loja."}


def test_estado_so_manda_html_quando_mudou(loja):
    ana = logado("ana")
    primeira = json.loads(ana.get(reverse("fila_estado")).content)
    assert primeira["mudou"] is True
    url = reverse("fila_estado") + "?versao=" + primeira["versao"]
    assert json.loads(ana.get(url).content) == {
        "versao": primeira["versao"], "mudou": False}
    _agir(logado("bia"), acao="ponto")
    depois = json.loads(ana.get(url).content)
    assert depois["mudou"] is True and "Bia" in depois["html"]["lista"]


def test_a_pagina_nao_tem_tabela():
    """R46 vale para tabela; a fila é lista (Global Constraints)."""
    empresa, matriz, _ = sylvia()
    pessoa_na_loja("ana", empresa, matriz)
    assert "<table" not in _html(logado("ana"))


# --- Quem vê o quê -----------------------------------------------------------

def test_sem_fila_ver_as_tres_rotas_nao_existem(loja):
    pessoa_na_loja("rita", loja.empresa, loja.matriz, cargo="representante")
    rita = logado("rita")
    assert rita.get(reverse("fila")).status_code == 404
    assert rita.get(reverse("fila_estado")).status_code == 404
    assert _agir(rita, acao="ponto").status_code == 404


def test_supervisor_ve_a_fila_sem_bater_o_ponto_e_acha_no_menu(loja):
    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    sara = logado("sara")
    html = _html(sara)
    assert "Bater o ponto" not in html
    assert _agir(sara, acao="ponto").status_code == 404
    assert 'href="/fila"' in _html(sara, "/")      # D-1


def test_vendedor_nao_corrige(loja):
    _agir(logado("bia"), acao="ponto")
    assert _agir(logado("ana"), acao="tirar",
                 pessoa=str(loja.bia.pk)).status_code == 404


def test_gerente_corrige_na_loja_dele(loja):
    from fila.models import LugarNaFila

    _agir(logado("ana"), acao="ponto")
    _agir(logado("gil"), acao="tirar", pessoa=str(loja.ana.pk))
    assert not LugarNaFila.irrestritos.exists()


def test_gerente_de_outra_loja_nao_corrige_a_matriz(loja):
    from fila.models import LugarNaFila

    centro = nova_loja(loja.empresa, "Centro")
    pessoa_na_loja("caio", loja.empresa, centro, cargo="gerente")
    _agir(logado("ana"), acao="ponto")
    caio = logado("caio")
    _agir(caio, acao="tirar", pessoa=str(loja.ana.pk))
    assert LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    assert "Essa pessoa não está nesta loja." in _html(caio)


def test_supervisor_corrige_na_empresa(loja):
    from fila.models import LugarNaFila

    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    _agir(logado("ana"), acao="ponto")
    _agir(logado("sara"), acao="tirar", pessoa=str(loja.ana.pk))
    assert not LugarNaFila.irrestritos.exists()


def test_gerente_edita_lancamento_de_hoje_pela_pagina(loja):
    from fila.models import Atendimento

    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk))
    atendimento = Atendimento.irrestritos.get()
    gil = logado("gil")
    assert "Lançamentos de hoje" in _html(gil)
    assert 'name="atendimento"' in _html(
        gil, f"/fila?folha=editar&atendimento={atendimento.pk}")
    _agir(gil, acao="editar", atendimento=str(atendimento.pk),
          resultado="nao_vendeu", motivo=str(loja.cad.motivo.pk),
          observacao="volta amanhã")
    atendimento.refresh_from_db()
    assert atendimento.observacao == "volta amanhã"


def test_sem_loja_a_pagina_diz_o_que_falta(db):
    from contas.models import Usuario

    Usuario.objects.create_superuser(email="raiz@teste.com", password="x")
    from django.test import Client

    raiz = Client()
    raiz.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "x"})
    html = _html(raiz)
    assert "Você ainda não está em nenhuma loja" in html


# --- Isolamento --------------------------------------------------------------

def test_tipo_de_pausa_de_outra_conta_e_recusado(loja):
    from fila.models import Pausa, TipoDePausa
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    outra = Empresa.objects.create(razao_social="Concorrente",
                                   nome_fantasia="Concorrente")
    abrir_conta(outra, "concorrente")
    outra.refresh_from_db()
    alheio = TipoDePausa.irrestritos.create(empresa=outra, nome="Almoço")
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="pausar", tipo=str(alheio.pk))
    assert not Pausa.irrestritos.exists()
    assert "Escolha o tipo de pausa." in _html(ana)


def test_id_que_nao_e_numero_nao_estoura(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    assert _agir(ana, acao="pausar", tipo="abc").status_code == 302
    assert _agir(ana, acao="finalizar", resultado="vendeu", grupo=["x"],
                 valor=["10"]).status_code == 302


# --- Onde se cai depois de entrar (D-4) -----------------------------------

def test_quem_so_tem_a_fila_cai_nela_depois_de_entrar(loja):
    from django.test import Client

    cliente = Client()
    resposta = cliente.post(reverse("entrar"), {
        "usuario": loja.ana.email, "senha": "segredo-de-teste"}, follow=True)
    assert resposta.redirect_chain[-1][0] == reverse("fila")


def test_quem_tem_mais_que_a_fila_cai_no_painel(loja):
    resposta = logado("gil").get("/")
    assert resposta.status_code == 200
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `$PYTEST tests/test_fila_pagina.py`
Esperado: FAIL (`NoReverseMatch: 'fila_agir'`).

- [ ] **Step 3: O ambiente Jinja do app e os filtros de tela**

`fila/ambiente.py`:

```python
"""O ambiente Jinja da página da fila, criado uma vez por processo.

A página da fila é a única, com a de entrar, fora do shell do dashboard, e os
templates dela moram em `fila/templates/`. `comum.ambiente.ambiente()` com
loader extra criaria um ambiente NOVO a cada requisição (o custo medido no
cabeçalho de `comum/ambiente.py`), e a fila é consultada a cada 3 segundos
por todo vendedor da rede. Por isso o app guarda o dele.

`_ensinar_a_traduzir` é importado de `comum.ambiente` mesmo sendo privado: é
o único jeito de o `traduzir(...)` dos templates daqui ser o mesmo da casa, e
um segundo mecanismo de tradução divergiria em silêncio.
"""

from __future__ import annotations

from functools import lru_cache

__all__ = ["ambiente_da_fila"]


@lru_cache(maxsize=1)
def ambiente_da_fila():
    from django.conf import settings
    from jinja2 import FileSystemLoader

    from comum.ambiente import _ensinar_a_traduzir
    from comum.estaticos import versionado
    from nucleo.rendering import create_environment

    from .tela import ha_quanto, hora_local, pessoas_na_frente
    from .valores import em_reais

    env = create_environment(
        FileSystemLoader(str(settings.BASE_DIR / "fila" / "templates")),
        FileSystemLoader(str(settings.BASE_DIR / "plataforma" / "templates")))
    _ensinar_a_traduzir(env)
    env.filters["ha_quanto"] = ha_quanto
    env.filters["hora"] = hora_local
    env.filters["reais"] = em_reais
    env.filters["na_frente"] = pessoas_na_frente
    env.globals["estatico"] = versionado
    return env
```

- [ ] **Step 4: `fila/tela.py`**

```python
"""O que a página da fila mostra, montado a partir do retrato da loja.

Separado da view para o POST com JavaScript, a consulta de 3 em 3 segundos e
a página inteira desenharem os MESMOS pedaços: se cada um montasse o próprio
HTML, a tela mudaria de cara depois da primeira consulta.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone
from markupsafe import Markup

from comum.csrf import campo_csrf
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.permissoes import pode
from nucleo.rendering import use_environment

from .ambiente import ambiente_da_fila
from .correcoes import lancamentos_de_hoje
from .estado import nome_de, retrato
from .models import (Atendimento, Estado, GrupoDeItem, LugarNaFila,
                     MotivoDeNaoVenda, TipoDePausa)

__all__ = ["PEDACOS", "ha_quanto", "hora_local", "pagina", "pedacos",
           "pessoas_na_frente", "sem_loja", "so_a_fila"]

#: Os pedaços que a consulta troca, com o template de cada um.
PEDACOS = {"painel": "fila/_painel.html", "lista": "fila/_lista.html",
           "barra": "fila/_barra.html", "lancamentos": "fila/_lancamentos.html"}

#: O que o vendedor tem. Quem tem SÓ isto não tem o que fazer no dashboard.
_SO_DO_VENDEDOR = frozenset({"fila.ver", "fila.participar"})

@dataclass(frozen=True)
class Alvo:
    """A pessoa sobre quem o gerente abriu uma folha de correção."""

    pessoa_id: int
    nome: str


_POR_EXTENSO = ("", "uma", "duas", "três", "quatro", "cinco", "seis", "sete",
                "oito", "nove", "dez")


def so_a_fila(user) -> bool:
    """Desvio D-4: cai direto em `/fila` quem só tem a fila de vendedor."""
    if user is None or user.superuser:
        return False
    permissoes = frozenset(user.permissions)
    return "fila.participar" in permissoes and permissoes <= _SO_DO_VENDEDOR


def ha_quanto(instante, agora=None) -> str:
    minutos = int(((agora or timezone.now()) - instante).total_seconds() // 60)
    if minutos < 1:
        return "agora"
    if minutos < 60:
        return f"há {minutos} min"
    return f"há {minutos // 60} h {minutos % 60:02d} min"


def hora_local(instante) -> str:
    return timezone.localtime(instante).strftime("%H:%M")


def pessoas_na_frente(posicao: int) -> str:
    frente = posicao - 1
    numero = _POR_EXTENSO[frente] if frente < len(_POR_EXTENSO) else str(frente)
    return f"{numero} {'pessoa' if frente == 1 else 'pessoas'} na sua frente"


def _lancamento_em_edicao(request, filial):
    if request.GET.get("folha") != "editar":
        return None
    try:
        atendimento_id = int(request.GET.get("atendimento", ""))
    except ValueError:
        return None
    return (Atendimento.objects.da_empresa(filial.empresa)
            .filter(pk=atendimento_id, filial=filial, fim__isnull=False)
            .select_related("vendedor", "motivo").first())


def _alvo_da_folha(request, filial):
    """A pessoa sobre quem o gerente abriu uma folha (`?pessoa=`), se ela está
    nesta loja. Id forjado ou de outra loja vira `None`, e a folha abre sem
    alvo — o POST confere de novo."""
    try:
        pessoa_id = int(request.GET.get("pessoa", ""))
    except ValueError:
        return None
    lugar = (LugarNaFila.objects.da_empresa(filial.empresa)
             .filter(filial=filial, pessoa_id=pessoa_id)
             .select_related("pessoa").first())
    return Alvo(lugar.pessoa_id, nome_de(lugar.pessoa)) if lugar else None


def _contexto(request, filial, recusa=""):
    pessoa = usuario_de(request.usuario)
    empresa = filial.empresa
    pode_gerenciar = pode(request.usuario, "fila.gerenciar")
    return {
        "r": retrato(filial, pessoa),
        "Estado": Estado,
        "filial": filial,
        "nome": nome_de(pessoa) if pessoa else "",
        "eu_id": pessoa.pk if pessoa else None,
        "agora": timezone.now(),
        "pode_participar": pode(request.usuario, "fila.participar"),
        "pode_gerenciar": pode_gerenciar,
        "mostra_painel": not so_a_fila(request.usuario),
        "csrf": Markup(campo_csrf(request)),
        "url_fila": reverse("fila"),
        "url_agir": reverse("fila_agir"),
        "url_estado": reverse("fila_estado"),
        "url_sair": reverse("sair"),
        "grupos": list(GrupoDeItem.objects.da_empresa(empresa).filter(ativo=True)),
        "motivos": list(MotivoDeNaoVenda.objects.da_empresa(empresa).filter(ativo=True)),
        "tipos": list(TipoDePausa.objects.da_empresa(empresa).filter(ativo=True)),
        "lancamentos": list(lancamentos_de_hoje(filial)) if pode_gerenciar else [],
        "folha": request.GET.get("folha", ""),
        "alvo": _alvo_da_folha(request, filial) if pode_gerenciar else None,
        "editando": _lancamento_em_edicao(request, filial) if pode_gerenciar else None,
        "recusa": recusa,
    }


def _aviso(request, env) -> Markup:
    componente = aviso_de_personificacao(request)
    if not componente:
        return Markup("")
    with use_environment(env):
        return Markup(componente.render(env))


def pagina(request, filial, recusa="") -> str:
    env = ambiente_da_fila()
    contexto = _contexto(request, filial, recusa)
    contexto["aviso"] = _aviso(request, env)
    return env.get_template("fila/pagina.html").render(**contexto)


def pedacos(request, filial) -> "tuple[str, dict[str, str]]":
    """`(versao, {pedaço: html})` de UMA leitura: a versão devolvida é a do
    retrato que desenhou o HTML, e não uma lida antes ou depois."""
    env = ambiente_da_fila()
    contexto = _contexto(request, filial)
    html = {nome: env.get_template(template).render(**contexto)
            for nome, template in PEDACOS.items()}
    return contexto["r"].versao, html


def sem_loja(request) -> str:
    env = ambiente_da_fila()
    return env.get_template("fila/sem_loja.html").render(
        aviso=_aviso(request, env), url_sair=reverse("sair"),
        mostra_painel=not so_a_fila(request.usuario))
```

- [ ] **Step 5: As views e as rotas**

`fila/views.py`:

```python
"""As rotas da fila: a raiz, a página, a consulta e as ações.

As ações do vendedor pedem `fila.participar`; as do gerente, `fila.gerenciar`
— as duas conferidas por `pode(request.usuario, ...)`, que já traz as
permissões do cargo NA LOJA atual (`comum.sessao.usuario_da_sessao`). O
gerente de uma loja não tem `fila.gerenciar` em outra, e é essa a trava de
"corrige a loja dele"; a de "a pessoa é desta loja" mora em `fila.correcoes`.
"""

from __future__ import annotations

from django.http import (HttpResponse, HttpResponseNotAllowed,
                         HttpResponseNotFound, HttpResponseRedirect,
                         JsonResponse)
from django.urls import reverse

from comum.guardas_de_acesso import exigir_login, exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.pedido import id_do_post
from contas.identidade import usuario_de
from nucleo.permissoes import pode
from plataforma.contexto import filial_atual

from . import acoes, correcoes, tela
from .acoes import ItemLancado, Lancamento, Recusa
from .estado import versao_da_fila
from .valores import ler_valor

__all__ = ["agir", "estado", "fila", "inicio"]

SEM_LOJA = "Você ainda não está em nenhuma loja."
CHAVE_DA_RECUSA = "fila:recusa"


@exigir_login
def inicio(request) -> HttpResponse:
    """A raiz. Quem só tem a fila de vendedor não tem o que fazer no
    dashboard, e cairia numa saudação vazia a cada login (D-4)."""
    from nucleo.views import home
    from plataforma.models import Modulo

    if (tela.so_a_fila(request.usuario)
            and Modulo.objects.filter(chave="fila", ativo=True).exists()):
        return HttpResponseRedirect(reverse("fila"))
    return home(request)


@exigir_permissao("fila.ver")
@exigir_modulo_ligado("fila")
def fila(request) -> HttpResponse:
    filial = filial_atual(request)
    if filial is None:
        return HttpResponse(tela.sem_loja(request))
    recusa = request.session.pop(CHAVE_DA_RECUSA, "")
    return HttpResponse(tela.pagina(request, filial, recusa))


@exigir_permissao("fila.ver")
@exigir_modulo_ligado("fila")
def estado(request) -> JsonResponse:
    filial = filial_atual(request)
    if filial is None:
        return JsonResponse({"versao": "", "mudou": False})
    # A versão sozinha é uma consulta; o retrato inteiro, só quando mudou.
    if request.GET.get("versao") == versao_da_fila(filial):
        return JsonResponse({"versao": request.GET["versao"], "mudou": False})
    versao, html = tela.pedacos(request, filial)
    return JsonResponse({"versao": versao, "mudou": True, "html": html})


def _lancamento(request) -> Lancamento:
    itens = []
    for grupo, valor in zip(request.POST.getlist("grupo"),
                            request.POST.getlist("valor")):
        if not grupo.strip() and not valor.strip():
            continue      # a linha vazia que a folha oferece a mais
        try:
            grupo_id = int(grupo)
        except ValueError:
            raise Recusa("Escolha o grupo de cada valor.") from None
        quantia = ler_valor(valor)
        if quantia is None:
            raise Recusa(f'Valor inválido: "{valor}".')
        itens.append(ItemLancado(grupo_id, quantia))
    return Lancamento(
        resultado=request.POST.get("resultado", ""), itens=tuple(itens),
        motivo_id=id_do_post(request, "motivo"),
        observacao=request.POST.get("observacao", ""))


def _pessoa_do_post(request) -> int:
    pessoa_id = id_do_post(request, "pessoa")
    if pessoa_id is None:
        raise Recusa("Essa pessoa não está nesta loja.")
    return pessoa_id


_DO_VENDEDOR = {
    "ponto": lambda r, f, p: acoes.bater_ponto(p, f),
    "atender": lambda r, f, p: acoes.vou_atender(p, f),
    "cliente_pediu": lambda r, f, p: acoes.cliente_pediu(p, f),
    "finalizar": lambda r, f, p: acoes.finalizar(p, f, _lancamento(r)),
    "pausar": lambda r, f, p: acoes.pausar(p, f, id_do_post(r, "tipo")),
    "voltar": lambda r, f, p: acoes.voltar_para_a_fila(p, f),
    "sair": lambda r, f, p: acoes.sair_da_loja(p, f),
}

_DO_GERENTE = {
    "tirar": lambda r, f, p: correcoes.tirar_da_loja(
        p, f, _pessoa_do_post(r),
        _lancamento(r) if r.POST.get("resultado") else None, request=r),
    "fechar": lambda r, f, p: correcoes.fechar_atendimento(
        p, f, _pessoa_do_post(r), _lancamento(r), request=r),
    "tirar_pausa": lambda r, f, p: correcoes.tirar_da_pausa(
        p, f, _pessoa_do_post(r), request=r),
    "editar": lambda r, f, p: correcoes.editar_lancamento(
        p, f, id_do_post(r, "atendimento"), _lancamento(r), request=r),
}


@exigir_permissao("fila.ver")
@exigir_modulo_ligado("fila")
def agir(request) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    acao = request.POST.get("acao", "")
    if acao in _DO_VENDEDOR:
        executar, precisa = _DO_VENDEDOR[acao], "fila.participar"
    elif acao in _DO_GERENTE:
        executar, precisa = _DO_GERENTE[acao], "fila.gerenciar"
    else:
        return HttpResponseNotFound()
    if not pode(request.usuario, precisa):
        return HttpResponseNotFound()

    filial = filial_atual(request)
    pessoa = usuario_de(request.usuario)
    frase = ""
    if filial is None or pessoa is None:
        frase = SEM_LOJA
    else:
        try:
            executar(request, filial, pessoa)
        except Recusa as recusa:
            frase = recusa.frase

    if request.headers.get("X-Fila") == "1":
        resposta = {"ok": not frase, "frase": frase}
        if filial is not None:
            resposta["versao"], resposta["html"] = tela.pedacos(request, filial)
        return JsonResponse(resposta)
    if frase:
        request.session[CHAVE_DA_RECUSA] = frase
    return HttpResponseRedirect(reverse("fila"))
```

`fila/urls.py` passa a ter, antes das rotas de cadastro:

```python
    path("", views.inicio, name="inicio"),
    path("fila", views.fila, name="fila"),
    path("fila/estado", views.estado, name="fila_estado"),
    path("fila/agir", views.agir, name="fila_agir"),
```

Se `test_guarda.py` acusar a raiz porque `nucleo.views.home` deixou de ser alcançável pelo resolver, não isente: a rota `home` continua registrada e decorada, só perde a corrida do `""` para `inicio`, que está decorada também.

- [ ] **Step 6: Os templates**

Todas as frases fixas passam por `traduzir(...)`. O ambiente é `StrictUndefined`: variável que não está no contexto quebra na hora, e é para quebrar.

`fila/templates/fila/pagina.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#1E2530">
<title>{{ traduzir("Fila da vez") }} — {{ filial }}</title>
<link rel="stylesheet" href="{{ estatico('/static/fila/fila.css') }}">
<script src="{{ estatico('/static/fila/fila.js') }}" defer></script>
</head>
<body class="fila" data-estado-url="{{ url_estado }}" data-agir-url="{{ url_agir }}" data-versao="{{ r.versao }}">
{{ aviso }}
<header class="topo">
  <div class="topo-onde">
    <span class="topo-loja">{{ filial }}</span>
    <span class="topo-nome">{{ nome }}</span>
  </div>
  <nav class="topo-links">
    {% if mostra_painel %}<a href="/">{{ traduzir("Painel") }}</a>{% endif %}
    <a href="{{ url_sair }}">{{ traduzir("Sair") }}</a>
  </nav>
</header>
<main class="miolo">
  <p id="fila-recusa" class="recusa" role="alert"{% if not recusa %} hidden{% endif %}>{{ recusa }}</p>
  <section id="fila-painel" class="painel-lugar" aria-live="polite">{% include "fila/_painel.html" %}</section>
  <section id="fila-lista" class="lista-lugar">{% include "fila/_lista.html" %}</section>
  <section id="fila-lancamentos" class="lancamentos-lugar"{% if not pode_gerenciar %} hidden{% endif %}>{% include "fila/_lancamentos.html" %}</section>
</main>
<nav id="fila-barra" class="barra">{% include "fila/_barra.html" %}</nav>
{% include "fila/_folhas.html" %}
</body>
</html>
```

`fila/templates/fila/_painel.html`:

```html
{% set meu = r.meu %}
{% if not pode_participar %}
<div class="painel painel-so-ve">
  <p class="painel-rotulo">{{ traduzir("Fila de agora") }}</p>
  <p class="painel-numero">{{ r.fila|length }}</p>
  <p class="painel-apoio">{{ r.atendendo|length }} {{ traduzir("atendendo") }}, {{ r.em_pausa|length }} {{ traduzir("em pausa") }}</p>
</div>
{% elif meu is none %}
<div class="painel painel-fora">
  <p class="painel-titulo">{{ traduzir("Você não está na fila") }}</p>
  <p class="painel-apoio">{{ traduzir("Bata o ponto quando chegar na loja para entrar no fim da fila.") }}</p>
</div>
{% elif meu.estado == Estado.NA_FILA and meu.posicao == 1 %}
<div class="painel painel-sua-vez">
  <p class="painel-titulo painel-grande">{{ traduzir("É a sua vez") }}</p>
  <p class="painel-apoio">{{ traduzir("O próximo cliente que entrar é seu.") }}</p>
</div>
{% elif meu.estado == Estado.NA_FILA %}
<div class="painel painel-na-fila">
  <p class="painel-rotulo">{{ traduzir("Sua vez em") }}</p>
  <p class="painel-numero">{{ meu.posicao }}</p>
  <p class="painel-apoio">{{ meu.posicao|na_frente }}</p>
</div>
{% elif meu.estado == Estado.ATENDENDO %}
<div class="painel painel-atendendo">
  <p class="painel-titulo">{{ traduzir("Atendendo") }}</p>
  <p class="painel-apoio">{{ traduzir("Começou às") }} {{ meu.desde|hora }}, <time data-desde="{{ meu.desde.isoformat() }}">{{ meu.desde|ha_quanto(agora) }}</time>.</p>
</div>
{% else %}
<div class="painel painel-pausa">
  <p class="painel-titulo">{{ traduzir("Em pausa") }}</p>
  <p class="painel-apoio">{{ meu.tipo_de_pausa }}, <time data-desde="{{ meu.desde.isoformat() }}">{{ meu.desde|ha_quanto(agora) }}</time>.</p>
</div>
{% endif %}
```

`fila/templates/fila/_lista.html`:

```html
{% macro corrigir(l) %}
{% if pode_gerenciar and not l.e_voce %}
<details class="corrigir">
  <summary>{{ traduzir("Corrigir") }}</summary>
  <div class="corrigir-opcoes">
  {% if l.estado == Estado.ATENDENDO %}
    <a href="{{ url_fila }}?folha=fechar&pessoa={{ l.pessoa_id }}" data-folha="fechar" data-pessoa="{{ l.pessoa_id }}" data-nome="{{ l.nome }}">{{ traduzir("Fechar atendimento") }}</a>
    <a href="{{ url_fila }}?folha=tirar&pessoa={{ l.pessoa_id }}" data-folha="tirar" data-pessoa="{{ l.pessoa_id }}" data-nome="{{ l.nome }}">{{ traduzir("Tirar da loja") }}</a>
  {% else %}
    {% if l.estado == Estado.EM_PAUSA %}
    <form method="post" action="{{ url_agir }}" data-acao>{{ csrf }}<input type="hidden" name="acao" value="tirar_pausa"><input type="hidden" name="pessoa" value="{{ l.pessoa_id }}"><button type="submit">{{ traduzir("Tirar da pausa") }}</button></form>
    {% endif %}
    <form method="post" action="{{ url_agir }}" data-acao>{{ csrf }}<input type="hidden" name="acao" value="tirar"><input type="hidden" name="pessoa" value="{{ l.pessoa_id }}"><button type="submit">{{ traduzir("Tirar da loja") }}</button></form>
  {% endif %}
  </div>
</details>
{% endif %}
{% endmacro %}

<h2 class="secao">{{ traduzir("Atendendo") }}</h2>
{% if r.atendendo %}
<ul class="lista">
  {% for l in r.atendendo %}
  <li class="linha linha-atendendo{% if l.e_voce %} linha-voce{% endif %}">
    <span class="linha-marca" aria-hidden="true">{{ icon("user", "sm") }}</span>
    <span class="linha-nome">{{ l.nome }}{% if l.e_voce %} <em>{{ traduzir("(você)") }}</em>{% endif %}</span>
    <time class="linha-tempo" data-desde="{{ l.desde.isoformat() }}">{{ l.desde|ha_quanto(agora) }}</time>
    {{ corrigir(l) }}
  </li>
  {% endfor %}
</ul>
{% else %}<p class="vazio">{{ traduzir("Ninguém atendendo agora.") }}</p>{% endif %}

<h2 class="secao">{{ traduzir("Na fila") }}</h2>
{% if r.fila %}
<ol class="lista">
  {% for l in r.fila %}
  <li class="linha linha-na-fila{% if l.e_voce %} linha-voce{% endif %}">
    <span class="linha-marca linha-posicao">{{ l.posicao }}</span>
    <span class="linha-nome">{{ l.nome }}{% if l.e_voce %} <em>{{ traduzir("(você)") }}</em>{% endif %}</span>
    <time class="linha-tempo" data-desde="{{ l.desde.isoformat() }}">{{ l.desde|ha_quanto(agora) }}</time>
    {{ corrigir(l) }}
  </li>
  {% endfor %}
</ol>
{% else %}<p class="vazio">{{ traduzir("A fila está vazia.") }}</p>{% endif %}

{% if r.em_pausa %}
<h2 class="secao">{{ traduzir("Em pausa") }}</h2>
<ul class="lista">
  {% for l in r.em_pausa %}
  <li class="linha linha-pausa{% if l.e_voce %} linha-voce{% endif %}">
    <span class="linha-marca" aria-hidden="true">{{ icon("clock", "sm") }}</span>
    <span class="linha-nome">{{ l.nome }}{% if l.e_voce %} <em>{{ traduzir("(você)") }}</em>{% endif %} <small>{{ l.tipo_de_pausa }}</small></span>
    <time class="linha-tempo" data-desde="{{ l.desde.isoformat() }}">{{ l.desde|ha_quanto(agora) }}</time>
    {{ corrigir(l) }}
  </li>
  {% endfor %}
</ul>
{% endif %}
```

`fila/templates/fila/_barra.html`:

```html
{% macro botao(acao, rotulo, classe="") %}
<form method="post" action="{{ url_agir }}" data-acao>{{ csrf }}<input type="hidden" name="acao" value="{{ acao }}"><button type="submit" class="{{ classe }}">{{ rotulo }}</button></form>
{% endmacro %}
{% set meu = r.meu %}
{% if pode_participar %}
<div class="barra-miolo">
{% if meu is none %}
  {{ botao("ponto", traduzir("Bater o ponto e entrar na fila"), "principal") }}
{% elif meu.estado == Estado.NA_FILA %}
  {% if meu.posicao == 1 %}
  {{ botao("atender", traduzir("Vou atender"), "principal principal-vez") }}
  {% else %}
  {{ botao("cliente_pediu", traduzir("Cliente pediu por mim"), "principal") }}
  {% endif %}
  <div class="barra-secundaria">
    <a href="{{ url_fila }}?folha=pausa" data-folha="pausa">{{ traduzir("Pausa") }}</a>
    {% if meu.posicao == 1 %}{{ botao("cliente_pediu", traduzir("Cliente pediu por mim"), "secundario") }}{% endif %}
    {{ botao("sair", traduzir("Sair da loja"), "secundario") }}
  </div>
{% elif meu.estado == Estado.ATENDENDO %}
  <a class="principal principal-vez" href="{{ url_fila }}?folha=finalizar" data-folha="finalizar">{{ traduzir("Finalizar atendimento") }}</a>
{% else %}
  {{ botao("voltar", traduzir("Voltar para a fila"), "principal") }}
  <div class="barra-secundaria">{{ botao("sair", traduzir("Sair da loja"), "secundario") }}</div>
{% endif %}
</div>
{% endif %}
```

`fila/templates/fila/_folhas.html` (as folhas; `open` quando a URL pediu, que é o caminho sem JavaScript):

```html
{% macro itens(linhas) %}
<div class="itens">
  {% for item in linhas %}
  <div class="item-vendido">
    <select name="grupo" aria-label="{{ traduzir('Grupo de item') }}">
      <option value="">{{ traduzir("Grupo") }}</option>
      {% for g in grupos %}<option value="{{ g.pk }}"{% if item and item.grupo_id == g.pk %} selected{% endif %}>{{ g.nome }}</option>{% endfor %}
    </select>
    <input name="valor" inputmode="decimal" autocomplete="off" placeholder="0,00" aria-label="{{ traduzir('Valor') }}" value="{{ (item.valor|reais)[3:] if item else '' }}">
  </div>
  {% endfor %}
</div>
<button type="button" class="outro-grupo" data-outro-grupo>{{ traduzir("+ outro grupo") }}</button>
<p class="total-linha">{{ traduzir("Total") }} <output class="total">R$ 0,00</output></p>
{% endmacro %}

{% macro motivos_de(escolhido=None) %}
<fieldset class="motivos">
  <legend>{{ traduzir("Por que não comprou?") }}</legend>
  {% for m in motivos %}
  <label class="opcao"><input type="radio" name="motivo" value="{{ m.pk }}"{% if escolhido == m.pk %} checked{% endif %}> {{ m.nome }}</label>
  {% endfor %}
</fieldset>
{% endmacro %}

{% macro fechamento(acao, titulo, pessoa_id) %}
<form method="post" action="{{ url_agir }}" data-acao>
  {{ csrf }}
  <input type="hidden" name="acao" value="{{ acao }}">
  {# A folha do gerente sempre tem o campo: o JavaScript preenche a pessoa ao abrir. #}
  {% if acao != "finalizar" %}<input type="hidden" name="pessoa" value="{{ pessoa_id or '' }}">{% endif %}
  <h2 class="folha-titulo">{{ titulo }}</h2>
  <div class="resultado">
    <label class="resultado-opcao resultado-vendeu"><input type="radio" name="resultado" value="vendeu" required> {{ traduzir("Vendeu") }}</label>
    <label class="resultado-opcao resultado-nao"><input type="radio" name="resultado" value="nao_vendeu" required> {{ traduzir("Não vendeu") }}</label>
  </div>
  <div class="so-venda">{{ itens([none, none, none]) }}</div>
  <div class="so-nao-venda">
    {{ motivos_de() }}
    <label class="campo">{{ traduzir("Observação") }} <textarea name="observacao" maxlength="280" rows="2"></textarea></label>
  </div>
  <div class="folha-acoes">
    <a href="{{ url_fila }}" data-fechar-folha>{{ traduzir("Cancelar") }}</a>
    <button type="submit" class="principal">{{ traduzir("Lançar") }}</button>
  </div>
</form>
{% endmacro %}

{% if pode_participar %}
<dialog id="folha-finalizar" class="folha"{% if folha == "finalizar" %} open{% endif %}>
  {{ fechamento("finalizar", traduzir("Como terminou o atendimento?"), none) }}
</dialog>

<dialog id="folha-pausa" class="folha"{% if folha == "pausa" %} open{% endif %}>
  <form method="post" action="{{ url_agir }}" data-acao>
    {{ csrf }}<input type="hidden" name="acao" value="pausar">
    <h2 class="folha-titulo">{{ traduzir("Pausa para quê?") }}</h2>
    <fieldset class="motivos">
      {% for t in tipos %}
      <label class="opcao"><input type="radio" name="tipo" value="{{ t.pk }}" required> {{ t.nome }}</label>
      {% endfor %}
    </fieldset>
    <p class="folha-apoio">{{ traduzir("Ao voltar, você entra no fim da fila.") }}</p>
    <div class="folha-acoes">
      <a href="{{ url_fila }}" data-fechar-folha>{{ traduzir("Cancelar") }}</a>
      <button type="submit" class="principal">{{ traduzir("Sair para a pausa") }}</button>
    </div>
  </form>
</dialog>
{% endif %}

{% if pode_gerenciar %}
<dialog id="folha-fechar" class="folha"{% if folha == "fechar" and alvo %} open{% endif %}>
  {{ fechamento("fechar", traduzir("Fechar o atendimento"), alvo.pessoa_id if alvo else "") }}
</dialog>

<dialog id="folha-tirar" class="folha"{% if folha == "tirar" and alvo %} open{% endif %}>
  <form method="post" action="{{ url_agir }}" data-acao>
    {{ csrf }}<input type="hidden" name="acao" value="tirar">
    <input type="hidden" name="pessoa" value="{{ alvo.pessoa_id if alvo else '' }}">
    <input type="hidden" name="resultado" value="nao_vendeu">
    <h2 class="folha-titulo">{{ traduzir("Tirar da loja") }} <span data-nome>{{ alvo.nome if alvo else "" }}</span></h2>
    <p class="folha-apoio">{{ traduzir("Ela está atendendo. O atendimento fecha como não venda.") }}</p>
    {{ motivos_de() }}
    <div class="folha-acoes">
      <a href="{{ url_fila }}" data-fechar-folha>{{ traduzir("Cancelar") }}</a>
      <button type="submit" class="principal">{{ traduzir("Tirar da loja") }}</button>
    </div>
  </form>
</dialog>

{% if editando %}
<dialog id="folha-editar" class="folha" open>
  <form method="post" action="{{ url_agir }}">
    {{ csrf }}<input type="hidden" name="acao" value="editar">
    <input type="hidden" name="atendimento" value="{{ editando.pk }}">
    <input type="hidden" name="resultado" value="{{ editando.resultado }}">
    <h2 class="folha-titulo">{{ traduzir("Corrigir o lançamento de") }} {{ editando.vendedor.nome or editando.vendedor.email }}</h2>
    {% if editando.resultado == "vendeu" %}
      {{ itens(editando.itens.all()|list + [none]) }}
    {% else %}
      {{ motivos_de(editando.motivo_id) }}
      <label class="campo">{{ traduzir("Observação") }} <textarea name="observacao" maxlength="280" rows="2">{{ editando.observacao }}</textarea></label>
    {% endif %}
    <div class="folha-acoes">
      <a href="{{ url_fila }}">{{ traduzir("Cancelar") }}</a>
      <button type="submit" class="principal">{{ traduzir("Salvar correção") }}</button>
    </div>
  </form>
</dialog>
{% endif %}
{% endif %}
```

`fila/templates/fila/_lancamentos.html`:

```html
{% if pode_gerenciar %}
<h2 class="secao">{{ traduzir("Lançamentos de hoje") }}</h2>
{% if lancamentos %}
<ul class="lista lancamentos">
  {% for a in lancamentos %}
  <li class="linha">
    <span class="linha-nome">{{ a.vendedor.nome or a.vendedor.email }}
      <small>{% if a.resultado == "vendeu" %}{{ a.total|reais }}{% else %}{{ traduzir("Não vendeu") }}: {{ a.motivo.nome }}{% endif %}{% if a.cliente_pediu %}, {{ traduzir("cliente pediu") }}{% endif %}</small>
    </span>
    <span class="linha-tempo">{{ a.fim|hora }}</span>
    {% if a.vendedor_id != eu_id %}
    <a class="linha-editar" href="{{ url_fila }}?folha=editar&atendimento={{ a.pk }}">{{ traduzir("Editar") }}</a>
    {% endif %}
  </li>
  {% endfor %}
</ul>
{% else %}<p class="vazio">{{ traduzir("Nenhum atendimento fechado hoje.") }}</p>{% endif %}
{% endif %}
```

O gerente não vê "Editar" no próprio lançamento (D-3); `eu_id` vem do contexto.

`fila/templates/fila/sem_loja.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ traduzir("Fila da vez") }}</title>
<link rel="stylesheet" href="{{ estatico('/static/fila/fila.css') }}">
</head>
<body class="fila">
{{ aviso }}
<main class="miolo sem-loja">
  <h1 class="painel-titulo">{{ traduzir("Você ainda não está em nenhuma loja") }}</h1>
  <p class="painel-apoio">{{ traduzir("Peça a quem cuida da equipe para alocar você na loja em que trabalha, na tela de Usuários.") }}</p>
  <p class="topo-links">{% if mostra_painel %}<a href="/">{{ traduzir("Painel") }}</a>{% endif %} <a href="{{ url_sair }}">{{ traduzir("Sair") }}</a></p>
</main>
</body>
</html>
```

`fila/static/fila/fila.css` e `fila/static/fila/fila.js`: por ora só `/* A folha da página da fila. Preenchida na Task 7. */` e `// O comportamento da página da fila. Preenchido na Task 7.`

- [ ] **Step 7: Rodar e ver passar**

Run: `$PYTEST tests/test_fila_pagina.py`
Esperado: PASS. Os erros mais prováveis: variável faltando no contexto (`UndefinedError`, acrescente em `_contexto`), nome de ícone inexistente (troque por um de `nucleo/icons.py`) e `raiz` sem empresa caindo em `sem_loja`.

- [ ] **Step 8: Quebrar de propósito**

1. Em `agir`, trocar `"fila.gerenciar"` por `"fila.ver"` → `test_vendedor_nao_corrige` vermelho.
2. Em `tela.so_a_fila`, devolver sempre `False` → `test_quem_so_tem_a_fila_cai_nela...` vermelho.
3. Em `views.estado`, tirar o `if request.GET.get("versao") == ...` → `test_estado_so_manda_html_quando_mudou` vermelho.
4. Em `_lancamento`, tirar o `continue` das linhas vazias → `test_finalizar_com_venda_pela_pagina` vermelho.
Desfazer.

- [ ] **Step 9: As varreduras da casa**

Run: `$PYTEST tests/test_guarda.py tests/test_guarda_modulo.py tests/test_personificacao.py tests/test_regra_tabela.py tests/test_id_do_post.py tests/test_camadas_nao_se_invertem.py tests/test_rota_do_modulo_bate_com_url.py`
Esperado: PASS. `test_personificacao.py` visita `/fila` personificando um alvo sem a fila (404, fica de fora) e a raiz (`inicio`, com o aviso do `home`).

- [ ] **Step 10: Suíte inteira** em segundo plano; números do `CLAUDE.md`. Esperado: verde.

- [ ] **Step 11: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: a página da fila, fora do dashboard

/fila mostra a loja em que a pessoa está: o estado dela em cima (a posição,
é a sua vez, atendendo, em pausa), a lista de quem atende, espera e pausa, e
as ações do estado de agora no rodapé. Finalizar, pausa, tirar da loja e
corrigir lançamento abrem folhas pela própria URL, e tudo funciona com
formulário comum: a Task seguinte põe o JavaScript por cima.

As ações vão para POST /fila/agir: as do vendedor pedem fila.participar e as
do gerente fila.gerenciar, conferidas no lugar da sessão. Com X-Fila a
resposta já traz os pedaços de HTML novos; GET /fila/estado só manda HTML
quando a versão da loja mudou.

Quem só tem a fila de vendedor cai em /fila depois de entrar, e quem está
sem loja lê o que falta em vez de uma fila vazia."
```

---

### Task 7: O visual aprovado e o JavaScript da página

**Files:**
- Create: `fila/static/fila/fontes/bricolage.woff2`, `fila/static/fila/fontes/OFL.txt`
- Modify: `fila/static/fila/fila.css`, `fila/static/fila/fila.js`, `tests/test_fila_pagina.py`

**Interfaces:**
- Consumes: os IDs, classes e atributos `data-*` listados na Task 6 (não renomeie nenhum).
- Produces: a página no visual aprovado; consulta de 3 em 3 s; ações por `fetch`; folhas como `<dialog>` modal.

**Direção aprovada (resumo para quem não viu a conversa):** celular primeiro. Topo fino com a loja e o nome. Painel de estado grande: "Sua vez em" / o número da posição enorme em Bricolage / "duas pessoas na sua frente". Quando é a vez, o painel inteiro fica Latão com "É a sua vez" e o rodapé tem um botão só, largo, "Vou atender". A fila em linhas alinhadas à esquerda, sem cartões, títulos de seção em caixa de frase, tempo numa coluna própria à direita. Barra de ações presa no rodapé. No computador, duas colunas: estado (preso ao rolar) à esquerda, fila à direita. A folha de finalizar sobe de baixo: Vendeu / Não vendeu, linhas de grupo e valor com o total em Bricolage, motivos como lista de toque e observação. Movimento só em dois momentos: a posição que muda e a vez que chega (com vibração, se o aparelho deixar); `prefers-reduced-motion` desliga os dois.

- [ ] **Step 1: O teste que falha**

Acrescentar a `tests/test_fila_pagina.py`:

```python
class TestOVisualTemOQueFoiAprovado:
    """Sem navegador (regra da casa): o que se prova aqui é que a folha e o
    script estão servidos e carregam o combinado — a cor de cada estado, a
    fonte auto-hospedada e o respeito a quem pediu menos movimento."""

    FOLHA = "fila/static/fila/fila.css"
    SCRIPT = "fila/static/fila/fila.js"

    def _folha(self):
        from pathlib import Path

        return Path(self.FOLHA).read_text(encoding="utf-8")

    def test_a_paleta_aprovada_esta_declarada(self):
        folha = self._folha().upper()
        for cor in ("#ECEEED", "#1E2530", "#0E4F54", "#B5893A", "#6B7480",
                    "#2F7A4B"):
            assert cor in folha, cor

    def test_a_fonte_e_auto_hospedada_e_existe(self):
        """Todo `url(...)` da folha aponta para arquivo do repositório: um
        relativo resolve em `fila/static/fila/`, e `/static/<app>/...` em
        `<app>/static/<app>/...`. Nada vem de fora."""
        import re
        from pathlib import Path

        enderecos = re.findall(r"url\(\"([^\"]+)\"\)", self._folha())
        assert enderecos, "a folha não declara @font-face"
        for endereco in enderecos:
            assert not endereco.startswith(("http:", "https:", "//")), endereco
            if endereco.startswith("/static/"):
                app = endereco.split("/")[2]
                arquivo = Path(app) / "static" / endereco[len("/static/"):]
            else:
                arquivo = Path("fila/static/fila") / endereco
            assert arquivo.exists(), endereco
        assert Path("fila/static/fila/fontes/bricolage.woff2").read_bytes()[:4] == b"wOF2"

    def test_movimento_respeita_quem_pediu_menos(self):
        assert "prefers-reduced-motion" in self._folha()

    def test_o_script_consulta_a_cada_tres_segundos(self):
        from pathlib import Path

        script = Path(self.SCRIPT).read_text(encoding="utf-8")
        assert "3000" in script
        assert "X-Fila" in script

    @pytest.mark.django_db
    def test_a_pagina_carrega_folha_e_script_versionados(self, loja):
        html = _html(logado("ana"))
        assert "/static/fila/fila.css?v=" in html
        assert "/static/fila/fila.js?v=" in html
```

A folha abaixo escreve todo `url(...)` com aspas duplas; o teste lê só esse formato.

- [ ] **Step 2: Rodar e ver falhar**

Run: `$PYTEST tests/test_fila_pagina.py -k Visual`
Esperado: FAIL (paleta ausente, fonte ausente).

- [ ] **Step 3: A fonte**

```bash
mkdir -p fila/static/fila/fontes
curl -fsSL -o fila/static/fila/fontes/bricolage.woff2 \
  https://cdn.jsdelivr.net/npm/@fontsource-variable/bricolage-grotesque@5/files/bricolage-grotesque-latin-wght-normal.woff2
curl -fsSL -o fila/static/fila/fontes/OFL.txt \
  https://cdn.jsdelivr.net/npm/@fontsource-variable/bricolage-grotesque@5/LICENSE
head -c 4 fila/static/fila/fontes/bricolage.woff2   # esperado: wOF2
```

CDN pública de fonte livre (OFL), baixada uma vez para dentro do repositório: nenhuma página carrega nada de fora, igual à Plus Jakarta Sans da base.

- [ ] **Step 4: A folha**

`fila/static/fila/fila.css`:

```css
/* A página da fila (Fila Zero). Fora do shell do dashboard, por isso tem
   tokens próprios: a cor de cada ESTADO é fixa e não vem da marca do
   cliente. Um vendedor que troca de loja, ou de empresa, lê "é a sua vez"
   na mesma cor; se a marca de um cliente fosse latão, a vez sumiria na tela.
   Todo estado tem rótulo e ícone além da cor. */

@font-face {
  font-family: "Bricolage Grotesque";
  src: url("fontes/bricolage.woff2") format("woff2");
  font-weight: 200 800;
  font-display: swap;
}
@font-face {
  font-family: "Plus Jakarta Sans";
  src: url("/static/plataforma/fontes/jakarta-400.woff2") format("woff2");
  font-weight: 400;
  font-display: swap;
}
@font-face {
  font-family: "Plus Jakarta Sans";
  src: url("/static/plataforma/fontes/jakarta-600.woff2") format("woff2");
  font-weight: 600;
  font-display: swap;
}
@font-face {
  font-family: "Plus Jakarta Sans";
  src: url("/static/plataforma/fontes/jakarta-700.woff2") format("woff2");
  font-weight: 700;
  font-display: swap;
}

:root {
  --concreto: #ECEEED;
  --grafite: #1E2530;
  --veludo: #0E4F54;
  --latao: #B5893A;
  --ardosia: #6B7480;
  --venda: #2F7A4B;
  --papel: #F7F8F7;
  --linha: #D5D9D8;
  --perigo: #9B2C2C;
  --exibicao: "Bricolage Grotesque", "Plus Jakarta Sans", system-ui, sans-serif;
  --texto: "Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --barra-altura: 5.5rem;
}

/* O script esconde e mostra com `hidden`; sem esta regra, um `display` de
   classe venceria o atributo e a seção escondida continuaria na tela
   (`tests/test_esconder_vence_o_display.py`). */
[hidden] { display: none !important; }

*, *::before, *::after { box-sizing: border-box; }

body.fila {
  margin: 0;
  min-height: 100dvh;
  background: var(--concreto);
  color: var(--grafite);
  font: 400 1rem/1.5 var(--texto);
  padding-bottom: calc(var(--barra-altura) + env(safe-area-inset-bottom));
  -webkit-text-size-adjust: 100%;
}

a { color: var(--veludo); }
:focus-visible { outline: 3px solid var(--latao); outline-offset: 2px; }

/* --- Topo ---------------------------------------------------------------- */
.topo {
  display: flex; align-items: center; justify-content: space-between;
  gap: 1rem; padding: .75rem 1rem;
  background: var(--grafite); color: var(--concreto);
}
.topo-onde { display: flex; flex-direction: column; line-height: 1.2; }
.topo-loja { font-weight: 700; }
.topo-nome { font-size: .875rem; color: #B9C0C9; }
.topo-links { display: flex; gap: 1rem; font-size: .875rem; }
.topo-links a { color: var(--concreto); }

.miolo { padding: 1rem; max-width: 72rem; margin: 0 auto; }

.recusa {
  margin: 0 0 1rem; padding: .75rem 1rem; border-radius: .5rem;
  background: #F6E7C8; color: var(--grafite); border-left: 4px solid var(--latao);
  font-weight: 600;
}

/* --- O painel de estado -------------------------------------------------- */
.painel {
  padding: 1.25rem 1rem 1.5rem; border-radius: .75rem;
  background: var(--papel); border: 1px solid var(--linha);
}
.painel p { margin: 0; }
.painel-rotulo { font-weight: 600; color: var(--ardosia); }
.painel-numero {
  font: 800 clamp(5rem, 28vw, 9rem)/.9 var(--exibicao);
  font-variant-numeric: tabular-nums; letter-spacing: -.04em;
  color: var(--veludo); margin: .25rem 0 .5rem !important;
}
.painel-titulo { font: 700 1.5rem/1.2 var(--exibicao); }
.painel-grande { font-size: clamp(2.5rem, 12vw, 4rem); letter-spacing: -.02em; }
.painel-apoio { color: var(--ardosia); margin-top: .25rem !important; }

.painel-na-fila { border-left: 6px solid var(--veludo); }
.painel-sua-vez { background: var(--latao); border-color: var(--latao); color: var(--grafite); }
.painel-sua-vez .painel-apoio { color: var(--grafite); }
.painel-atendendo { border-left: 6px solid var(--latao); }
.painel-pausa { border-left: 6px solid var(--ardosia); }

/* --- A lista ------------------------------------------------------------- */
.secao { font: 700 1.125rem/1.3 var(--exibicao); margin: 1.5rem 0 .5rem; }
.lista { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--linha); }
.linha {
  display: grid; grid-template-columns: 2.25rem 1fr auto; align-items: center;
  column-gap: .75rem; padding: .75rem 0; border-bottom: 1px solid var(--linha);
}
.linha-marca { display: inline-flex; justify-content: center; color: var(--ardosia); }
.linha-posicao { font: 700 1.25rem/1 var(--exibicao); font-variant-numeric: tabular-nums; color: var(--veludo); }
.linha-nome { font-weight: 600; }
.linha-nome small { display: block; font-weight: 400; color: var(--ardosia); }
.linha-nome em { font-style: normal; font-weight: 400; color: var(--ardosia); }
.linha-tempo { font-size: .875rem; color: var(--ardosia); font-variant-numeric: tabular-nums; text-align: right; }
.linha-atendendo .linha-marca { color: var(--latao); }
.linha-voce { background: linear-gradient(90deg, rgba(14, 79, 84, .08), transparent 70%); }
.linha-editar { grid-column: 3; justify-self: end; font-size: .875rem; }
.vazio { color: var(--ardosia); margin: .5rem 0; }

.corrigir { grid-column: 2 / 4; }
.corrigir summary { cursor: pointer; font-size: .875rem; color: var(--veludo); }
.corrigir-opcoes { display: flex; flex-wrap: wrap; gap: .5rem; padding-top: .5rem; }
.corrigir-opcoes form { margin: 0; }
.corrigir-opcoes button, .corrigir-opcoes a {
  font: 600 .875rem/1 var(--texto); padding: .5rem .75rem; border-radius: .375rem;
  border: 1px solid var(--linha); background: var(--papel); color: var(--grafite);
  text-decoration: none; cursor: pointer;
}

/* --- A barra de ações ---------------------------------------------------- */
.barra {
  position: fixed; inset: auto 0 0 0; z-index: 10;
  padding: .75rem 1rem calc(.75rem + env(safe-area-inset-bottom));
  background: var(--papel); border-top: 1px solid var(--linha);
}
.barra-miolo { max-width: 40rem; margin: 0 auto; display: grid; gap: .5rem; }
.barra form { margin: 0; }
.principal {
  display: block; width: 100%; min-height: 3.25rem; padding: .75rem 1rem;
  border: 0; border-radius: .625rem; cursor: pointer; text-align: center;
  font: 700 1.125rem/1.2 var(--texto); text-decoration: none;
  background: var(--veludo); color: #fff;
}
.principal-vez { background: var(--latao); color: var(--grafite); }
.principal[disabled] { opacity: .6; cursor: progress; }
.barra-secundaria { display: flex; gap: 1rem; justify-content: center; align-items: center; flex-wrap: wrap; }
.barra-secundaria a, .secundario {
  background: none; border: 0; padding: .25rem; cursor: pointer;
  font: 600 .9375rem/1.2 var(--texto); color: var(--veludo); text-decoration: underline;
}

/* --- As folhas ----------------------------------------------------------- */
.folha {
  width: 100%; max-width: 36rem; max-height: 92dvh; margin: auto auto 0;
  padding: 1.25rem 1rem calc(1rem + env(safe-area-inset-bottom));
  border: 0; border-radius: 1rem 1rem 0 0; background: var(--papel); color: var(--grafite);
}
.folha::backdrop { background: rgba(30, 37, 48, .55); }
.folha[open]:not(:modal) { position: fixed; inset: auto 0 0 0; z-index: 20; box-shadow: 0 -8px 24px rgba(30, 37, 48, .25); }
.folha-titulo { font: 700 1.375rem/1.2 var(--exibicao); margin: 0 0 1rem; }
.folha-apoio { color: var(--ardosia); }
.folha-acoes { display: grid; grid-template-columns: auto 1fr; gap: 1rem; align-items: center; margin-top: 1rem; }

.resultado { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin-bottom: 1rem; }
.resultado-opcao {
  display: flex; align-items: center; justify-content: center; gap: .5rem;
  min-height: 3rem; border-radius: .625rem; border: 2px solid var(--linha);
  font-weight: 700; cursor: pointer;
}
.resultado-vendeu:has(input:checked) { border-color: var(--venda); background: rgba(47, 122, 75, .12); }
.resultado-nao:has(input:checked) { border-color: var(--ardosia); background: rgba(107, 116, 128, .12); }

.itens { display: grid; gap: .5rem; }
.item-vendido { display: grid; grid-template-columns: 1fr 8rem; gap: .5rem; }
.item-vendido select, .item-vendido input, .campo textarea {
  width: 100%; min-height: 3rem; padding: .5rem .75rem; border-radius: .5rem;
  border: 1px solid var(--linha); background: #fff; color: var(--grafite);
  font: 400 1rem/1.3 var(--texto);
}
.item-vendido input { text-align: right; font-variant-numeric: tabular-nums; }
.outro-grupo { margin-top: .5rem; background: none; border: 0; padding: .25rem 0; color: var(--veludo); font: 600 1rem/1 var(--texto); cursor: pointer; }
.total-linha { display: flex; justify-content: space-between; align-items: baseline; margin: 1rem 0 0; font-weight: 600; }
.total { font: 800 2rem/1 var(--exibicao); font-variant-numeric: tabular-nums; color: var(--venda); }

.motivos { border: 0; margin: 0; padding: 0; display: grid; gap: .25rem; }
.motivos legend { font-weight: 700; margin-bottom: .5rem; }
.opcao {
  display: flex; align-items: center; gap: .75rem; min-height: 3rem; padding: 0 .75rem;
  border-radius: .5rem; border: 1px solid var(--linha); background: #fff; cursor: pointer;
}
.opcao:has(input:checked) { border-color: var(--veludo); box-shadow: inset 0 0 0 1px var(--veludo); }
.campo { display: grid; gap: .25rem; margin-top: 1rem; font-weight: 600; }

.sem-loja { padding-top: 3rem; max-width: 32rem; }

/* O aviso de personificação é o componente do design system, que esta página
   não carrega inteiro: só o suficiente para ele ser lido. */
body.fila > .alert { display: flex; gap: .75rem; padding: .75rem 1rem; background: #F6E7C8; }
body.fila > .alert svg { width: 1.25rem; height: 1.25rem; flex: none; }
body.fila > .alert .at { font-weight: 700; }
body.fila > .alert form { margin-top: .5rem; }

.sem-sinal .topo::after { content: "Sem conexão"; font-size: .75rem; padding: .125rem .5rem; border-radius: 1rem; background: var(--latao); color: var(--grafite); }

/* --- Movimento: só dois momentos ----------------------------------------- */
@keyframes vez-chegou { from { transform: scale(.96); } 60% { transform: scale(1.02); } to { transform: none; } }
@keyframes posicao-mudou { from { transform: translateY(.35em); opacity: .3; } to { transform: none; opacity: 1; } }
.chegou .painel-sua-vez { animation: vez-chegou .45s ease-out; }
.mudou .painel-numero { animation: posicao-mudou .35s ease-out; }
@media (prefers-reduced-motion: reduce) {
  .chegou .painel-sua-vez, .mudou .painel-numero { animation: none; }
}

/* --- Computador: duas colunas -------------------------------------------- */
@media (min-width: 900px) {
  body.fila {
    display: grid; padding-bottom: 0;
    grid-template-columns: minmax(20rem, 26rem) 1fr;
    grid-template-rows: auto auto auto 1fr;
    grid-template-areas: "topo topo" "recusa lista" "painel lista" "barra lista";
    column-gap: 2rem;
  }
  body.fila > .alert { grid-column: 1 / -1; }
  .topo { grid-area: topo; }
  .miolo { display: contents; }
  .recusa { grid-area: recusa; margin: 1rem 0 0 1.5rem; }
  .painel-lugar { grid-area: painel; padding: 1rem 0 0 1.5rem; }
  .lista-lugar { grid-area: lista; padding: 0 1.5rem 2rem 0; max-width: 48rem; }
  .lancamentos-lugar { grid-column: 2; padding: 0 1.5rem 2rem 0; max-width: 48rem; }
  .barra { grid-area: barra; position: sticky; top: 1rem; align-self: start; margin: 1rem 0 0 1.5rem; border: 1px solid var(--linha); border-radius: .75rem; }
  .painel-lugar { position: sticky; top: 1rem; align-self: start; }
  .folha { margin: auto; border-radius: 1rem; }
  .sem-loja { grid-column: 1 / -1; margin: 0 auto; }
}
```

Depois de escrever, rode `$PYTEST tests/test_variavel_de_cor_existe.py tests/test_esconder_vence_o_display.py`: toda `var(--x)` citada precisa estar declarada no `:root` acima.

- [ ] **Step 5: O script**

`fila/static/fila/fila.js`:

```js
// O comportamento da página da fila (Fila Zero).
//
// A página funciona inteira sem este arquivo (formulários e links comuns).
// Ele acrescenta três coisas: a consulta de 3 em 3 segundos (D8 do spec), as
// ações sem recarregar a página, e as folhas como diálogo. Tudo que ele
// desenha vem do servidor pronto: não há HTML montado aqui, para a tela não
// mudar de cara depois da primeira consulta.
(function () {
  "use strict";

  var INTERVALO = 3000;          // D8: a cada 3 segundos
  var INTERVALO_SEM_SINAL = 10000;
  var corpo = document.body;
  var versao = corpo.dataset.versao || "";
  var urlEstado = corpo.dataset.estadoUrl;
  var urlAgir = corpo.dataset.agirUrl;
  var esperando = null;

  function el(id) { return document.getElementById(id); }

  function haQuanto(iso) {
    var minutos = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (minutos < 1) return "agora";
    if (minutos < 60) return "há " + minutos + " min";
    var resto = minutos % 60;
    return "há " + Math.floor(minutos / 60) + " h " + (resto < 10 ? "0" : "") + resto + " min";
  }

  function atualizarTempos() {
    document.querySelectorAll("time[data-desde]").forEach(function (t) {
      t.textContent = haQuanto(t.dataset.desde);
    });
  }

  function numeroDaPosicao() {
    var n = document.querySelector("#fila-painel .painel-numero");
    return n ? n.textContent.trim() : "";
  }

  // Troca os pedaços e marca os dois únicos momentos com movimento: a vez
  // que chega e a posição que muda.
  function trocar(html, novaVersao) {
    if (!html) return;
    var eraVez = !!document.querySelector("#fila-painel .painel-sua-vez");
    var posicaoAntes = numeroDaPosicao();
    ["painel", "lista", "barra", "lancamentos"].forEach(function (nome) {
      var lugar = el("fila-" + nome);
      if (lugar && typeof html[nome] === "string") lugar.innerHTML = html[nome];
    });
    if (novaVersao) { versao = novaVersao; corpo.dataset.versao = novaVersao; }
    var eVez = !!document.querySelector("#fila-painel .painel-sua-vez");
    var painel = el("fila-painel");
    painel.classList.remove("chegou", "mudou");
    void painel.offsetWidth;   // recomeça a animação
    if (eVez && !eraVez) {
      painel.classList.add("chegou");
      if (navigator.vibrate) navigator.vibrate([180, 80, 180]);
    } else if (posicaoAntes && numeroDaPosicao() !== posicaoAntes) {
      painel.classList.add("mudou");
    }
    atualizarTempos();
  }

  function mostrarRecusa(frase) {
    var caixa = el("fila-recusa");
    if (!caixa) return;
    caixa.textContent = frase || "";
    caixa.hidden = !frase;
  }

  function agendar(espera) {
    clearTimeout(esperando);
    esperando = setTimeout(consultar, espera);
  }

  function consultar() {
    if (document.hidden) { agendar(INTERVALO); return; }
    fetch(urlEstado + "?versao=" + encodeURIComponent(versao), {
      credentials: "same-origin", headers: { "X-Fila": "1" }
    }).then(function (r) {
      if (r.redirected || !r.ok) throw new Error("estado " + r.status);
      return r.json();
    }).then(function (dados) {
      corpo.classList.remove("sem-sinal");
      if (dados.mudou) trocar(dados.html, dados.versao);
      agendar(INTERVALO);
    }).catch(function () {
      // Celular que perde sinal: avisa e tenta de novo mais devagar, sem
      // derrubar a página nem empilhar pedidos.
      corpo.classList.add("sem-sinal");
      agendar(INTERVALO_SEM_SINAL);
    });
  }

  // --- As folhas ---------------------------------------------------------
  function abrirFolha(nome, gatilho) {
    var folha = el("folha-" + nome);
    if (!folha) return false;
    var form = folha.querySelector("form");
    if (form) form.reset();
    if (gatilho && gatilho.dataset.pessoa) {
      var campo = folha.querySelector("input[name=pessoa]");
      if (campo) campo.value = gatilho.dataset.pessoa;
      var nome_ = folha.querySelector("[data-nome]");
      if (nome_) nome_.textContent = gatilho.dataset.nome || "";
    }
    ajustarResultado(folha);
    somar(folha);
    if (folha.open) folha.close();
    folha.showModal();
    return true;
  }

  function fecharFolhas() {
    document.querySelectorAll("dialog.folha[open]").forEach(function (d) { d.close(); });
  }

  function ajustarResultado(folha) {
    var escolhido = folha.querySelector("input[name=resultado]:checked");
    var venda = folha.querySelector(".so-venda");
    var naoVenda = folha.querySelector(".so-nao-venda");
    if (venda) venda.hidden = !escolhido || escolhido.value !== "vendeu";
    if (naoVenda) naoVenda.hidden = !escolhido || escolhido.value !== "nao_vendeu";
  }

  function lerValor(texto) {
    var limpo = (texto || "").replace(/R\$|\s/g, "");
    if (limpo.indexOf(",") >= 0) limpo = limpo.replace(/\./g, "").replace(",", ".");
    else if (/^\d{1,3}(\.\d{3})+$/.test(limpo)) limpo = limpo.replace(/\./g, "");
    var n = Number(limpo);
    return isFinite(n) && n > 0 ? n : 0;
  }

  function somar(escopo) {
    escopo.querySelectorAll(".itens").forEach(function (itens) {
      var total = 0;
      itens.querySelectorAll("input[name=valor]").forEach(function (i) { total += lerValor(i.value); });
      var saida = itens.parentNode.querySelector("output.total");
      if (saida) {
        saida.textContent = "R$ " + total.toLocaleString("pt-BR", {
          minimumFractionDigits: 2, maximumFractionDigits: 2 });
      }
    });
  }

  // --- Ações -------------------------------------------------------------
  function enviar(form) {
    var botao = form.querySelector("button[type=submit]");
    if (botao) botao.disabled = true;
    fetch(urlAgir, {
      method: "POST", credentials: "same-origin",
      headers: { "X-Fila": "1" }, body: new FormData(form)
    }).then(function (r) {
      if (!r.ok) throw new Error("agir " + r.status);
      return r.json();
    }).then(function (dados) {
      mostrarRecusa(dados.frase);
      if (dados.ok) fecharFolhas();
      trocar(dados.html, dados.versao);
    }).catch(function () {
      mostrarRecusa("Sem conexão. Tente de novo.");
    }).then(function () {
      if (botao && document.contains(botao)) botao.disabled = false;
    });
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.matches("form[data-acao]")) return;
    e.preventDefault();
    enviar(form);
  });

  document.addEventListener("click", function (e) {
    var gatilho = e.target.closest("[data-folha]");
    if (gatilho && abrirFolha(gatilho.dataset.folha, gatilho)) {
      e.preventDefault();
      return;
    }
    if (e.target.closest("[data-fechar-folha]")) {
      e.preventDefault();
      fecharFolhas();
      return;
    }
    var outro = e.target.closest("[data-outro-grupo]");
    if (outro) {
      var itens = outro.parentNode.querySelector(".itens");
      var modelo = itens.querySelector(".item-vendido:last-child");
      var copia = modelo.cloneNode(true);
      copia.querySelector("select").selectedIndex = 0;
      copia.querySelector("input").value = "";
      itens.appendChild(copia);
      copia.querySelector("select").focus();
    }
  });

  document.addEventListener("change", function (e) {
    if (e.target.name === "resultado") ajustarResultado(e.target.closest("dialog"));
  });
  document.addEventListener("input", function (e) {
    if (e.target.name === "valor") somar(e.target.closest("form"));
  });

  // Folha aberta pela URL (sem JavaScript ela abriu com `open`): vira modal.
  document.querySelectorAll("dialog.folha[open]").forEach(function (folha) {
    ajustarResultado(folha);
    somar(folha);
    folha.close();
    folha.showModal();
  });

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) agendar(0);
  });

  setInterval(atualizarTempos, 30000);
  if (urlEstado) agendar(INTERVALO);
})();
```

A folha de editar lançamento não tem `data-acao` no formulário de propósito: ela abre por navegação (`?folha=editar`) e volta por redirecionamento, porque a edição é rara e precisa do lançamento carregado pelo servidor.

- [ ] **Step 6: Rodar e ver passar**

Run: `$PYTEST tests/test_fila_pagina.py tests/test_variavel_de_cor_existe.py tests/test_esconder_vence_o_display.py tests/test_estaticos.py`
Esperado: PASS.

- [ ] **Step 7: Quebrar de propósito**

1. Trocar `#B5893A` por `#B5893B` na folha → paleta vermelha.
2. Apagar o bloco `prefers-reduced-motion` → vermelho.
3. Apagar a regra `[hidden]` → `test_esconder_vence_o_display.py` vermelho (se não ficar, a varredura não olha `fila/static`: volte à Task 1, Step 8).
Desfazer.

- [ ] **Step 8: Conferência manual (sem navegador automatizado)**

Suba o servidor e confira pelo menos pelo `curl` que a página, a folha, o script e a fonte respondem 200:

```bash
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/fila_zero \
  .venv/bin/python manage.py runserver 127.0.0.1:8005   # em segundo plano
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8005/static/fila/fila.css
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8005/static/fila/fila.js
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8005/static/fila/fontes/bricolage.woff2
```

Esperado: `200` três vezes. Pare o servidor pela porta (`ss -ltnp | grep 8005` e `kill <pid>`), nunca com `pkill -f`. A conferência visual no celular é do João; diga no relatório que ela não foi feita.

- [ ] **Step 9: Suíte inteira** em segundo plano. Esperado: verde.

- [ ] **Step 10: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: o visual da fila e a consulta de 3 em 3 segundos

A página ganha a direção aprovada: fundo concreto, texto grafite, veludo
para quem está na fila, latão só para a vez e o atendimento, ardósia para a
pausa e verde só na confirmação da venda. As cores de estado são fixas e não
vêm da marca do cliente, e todo estado tem rótulo e ícone além da cor.

O número da posição e 'É a sua vez' saem em Bricolage Grotesque,
auto-hospedada (OFL) ao lado da Plus Jakarta Sans da base. Celular primeiro,
com a barra de ações presa no rodapé; no computador, estado à esquerda e
fila à direita.

O script consulta /fila/estado a cada 3 segundos e só troca o HTML quando a
versão mudou; manda as ações por fetch e abre as folhas como diálogo. O
movimento fica em dois momentos, a vez que chega (com vibração) e a posição
que muda, e some com prefers-reduced-motion. Sem o script a página continua
funcionando com formulários comuns."
```

---

### Task 8: Documentação, castelhano e a entrega

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `PROVENIENCIA.md`, `docs/superpowers/specs/2026-09-15-fila-da-vez-design.md`, `locale/es/LC_MESSAGES/django.po` (e o `.mo` compilado)

**Interfaces:**
- Consumes: tudo das Tasks 1–7.
- Produces: `CLAUDE.md` que descreve o Fila Zero sem mentir (`test_documentacao_nao_mente.py`), frases da moldura da fila em castelhano, spec com os desvios registrados.

- [ ] **Step 1: O spec registra os desvios**

No fim de "Decisões" do spec, acrescentar a seção:

```markdown
### Ajustes do plano de implementação (15/09/2026)

O plano `docs/superpowers/plans/2026-09-15-fila-da-vez.md` decidiu cinco
pontos que este desenho não respondia. Em resumo:

- **`fila.ver`** nasce como quarta permissão e vem primeiro: o menu da base
  entra pela primeira permissão do módulo, e sem ela o supervisor não acharia
  a fila. `/fila` pede `fila.ver`; bater o ponto, `fila.participar`.
- **A trava é a linha da filial**, e não as linhas da fila (loja vazia não tem
  o que trancar).
- **Ninguém corrige a si mesmo**, gerente incluído.
- **Cai direto em `/fila`** quem só tem `fila.ver` e `fila.participar`.
- **Usuário com histórico não se remove**: a tela diz para desativar.
```

E na tabela "Permissões e cargos", acrescentar a linha `| \`fila.ver\` | a página da fila da loja e o item no menu |` no topo, e `fila.ver` em Vendedor, Gerente, Supervisor e Titular.

- [ ] **Step 2: O CLAUDE.md**

1. Título e primeiro parágrafo: `# Fila Zero — o que você precisa saber antes de mexer`, dizendo que é o SaaS da fila da vez das lojas, nascido da KRONOS base (commit `be166c4`, `PROVENIENCIA.md`), e que a base continua descrita nas seções dela.
2. §1 ("Como um SaaS nasce daqui") vira "Como a base se usa aqui": o roteiro fica, com a nota de que o Fila Zero já o seguiu (identidade, app `fila/`, varreduras, permissões de nascença).
3. Nova seção **"§10. A fila da vez"** (antes de "Como rodar"), com:
   - o problema em duas frases e o link para o spec e o plano;
   - as quatro permissões e a tabela de cargos;
   - onde mora cada regra: `fila/acoes.py` (vendedor, sob trava da filial), `fila/correcoes.py` (gerente, com auditoria), `fila/estado.py` (ordem = `na_fila_desde`, versão), `fila/tela.py` + `fila/templates/fila/` (a página fora do shell, ambiente Jinja próprio em `fila/ambiente.py`), `fila/views_cadastros.py`;
   - o que custa esquecer: ler antes de trancar (dois atendimentos, 500); `bulk_create` de `ItemVendido` pula a conta; cadastro usado é `PROTECT` (desativa); a página não tem `<table>`; cor de estado não vem da marca; a página funciona sem JavaScript e o script só troca HTML do servidor;
   - a entrega 2 (dashboard) ainda não existe.
4. §3: acrescentar `fila/` na lista de pastas ("o negócio do Fila Zero").
5. §5: nenhuma varredura nova; se alguma lista de pastas foi mexida, nada a dizer além de §1.
6. "Como rodar": portas 5436/8005 (já feito na Task 1) e o número de arquivos de teste que `ls tests/test_*.py | wc -l` der, nos dois lugares.

Rodar `$PYTEST tests/test_documentacao_nao_mente.py` até ficar verde. Não troque número à mão sem contar.

- [ ] **Step 3: README e PROVENIENCIA**

- `README.md`: primeiro parágrafo diz o que é o Fila Zero; a tabela de portas cita 5436/8005; uma seção curta "A fila" com as rotas `/fila`, `/fila/estado`, `/fila/agir`, `/fila/grupos`, `/fila/motivos`, `/fila/pausas`.
- `PROVENIENCIA.md`: acrescentar "O que o Fila Zero pôs por cima": o app `fila/`, as permissões nos cargos de fábrica e no titular, a resposta da tela de Usuários ao `ProtectedError` (mudança de base que vale levar de volta à KRONOS base).

- [ ] **Step 4: O castelhano**

Seguir a receita de `docs/superpowers/specs/2026-09-09-idioma-castelhano.md` com `fila` nas pastas:

```bash
.venv/bin/python -m babel.messages.frontend extract -F babel.cfg -k traduzir \
  -o locale/portal.pot --no-location contas plataforma comum modulos fila
.venv/bin/python -m babel.messages.frontend update -i locale/portal.pot \
  -d locale -D django --no-fuzzy-matching --ignore-obsolete
```

Preencher em `locale/es/LC_MESSAGES/django.po` o `msgstr` de toda frase nova da fila (as de `fila/modulo.py`, `fila/models.py`, `fila/views_cadastros.py` e dos templates `fila/templates/fila/*.html`), em castelhano do Paraguai e no tratamento que o `.po` já usa, que é "usted" ("No puede desactivar su propia cuenta."). Exemplos: "Fila da vez" → "Turno de atención", "É a sua vez" → "Es su turno", "Vou atender" → "Voy a atender", "Bater o ponto e entrar na fila" → "Marcar llegada y entrar a la fila", "Voltar para a fila" → "Volver a la fila", "Não vendeu" → "No vendió", "Lançamentos de hoje" → "Registros de hoy".

**As frases de recusa de `fila/acoes.py` e `fila/correcoes.py` não passam por tradução nesta entrega**: são montadas com nome e número (`"A vez é de Ana. Você é o 2º da fila."`), e traduzir pede `%(nome)s` em cada uma. Registre isso no §9 do `CLAUDE.md` como em aberto.

```bash
.venv/bin/python -m babel.messages.frontend compile -d locale -D django
```

Rodar `$PYTEST tests/test_idioma.py tests/test_entrada_em_castelhano.py`. Esperado: PASS.

- [ ] **Step 5: Suíte inteira**

`$PYTEST` inteiro em segundo plano. Esperado: verde, com o número de testes maior que o da base (1856 passed, 1 skipped). Anote o número exato no relatório.

- [ ] **Step 6: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "docs: o CLAUDE.md passa a descrever o Fila Zero

O CLAUDE.md ainda se apresentava como a KRONOS base, e quem abrisse a pasta
para mexer na fila não acharia onde as regras moram nem o que custa
esquecê-las. Ele ganha a seção da fila (permissões, onde mora cada regra, a
trava da loja, a página fora do shell) e continua descrevendo a base nas
seções dela.

O spec registra os cinco ajustes que o plano decidiu (fila.ver, a trava na
filial, ninguém corrige a si mesmo, quem só tem a fila cai nela, usuário com
histórico não se remove). O README e o PROVENIENCIA dizem o que o Fila Zero
pôs por cima da base, e as frases da moldura da fila ganham castelhano; as
frases de recusa montadas com nome ficam em português, anotado como em
aberto."
```

---

## Self-review do plano (feito ao escrever)

**Cobertura do spec:**

| spec | tarefa |
|---|---|
| D1 ponto = presença | T2 (`Presenca`), T3 (`bater_ponto`) |
| D2 volta para o fim | T3 (`_voltar_ao_fim`, testes de ordem) |
| D3 primeiro atende, cliente pediu | T3 |
| D4 venda com vários grupos | T2 (`ItemVendido`), T3 (`_validar`), T6 (linhas grupo/valor), T7 (total) |
| D5 não venda com um motivo | T3, T6 |
| D6 pausa com tipo | T3, T6 |
| D7 gerente corrige, sem fechamento automático | T4, T6 |
| D8 consulta de 3 s, versão | T3 (`versao_da_fila`), T6 (`/fila/estado`), T7 (script) |
| D9 trava no servidor | T3 (`_travar`, teste de concorrência) |
| Permissões e cargos | T1 (+ D-1) |
| Regras de lugar | T3 (troca de loja), T6 (`filial_atual`, gerente de outra loja) |
| Modelo de dados e restrições | T2 |
| Regras de gravação | T3, T4 (não reabre, resultado não muda) |
| `/fila` fora do dashboard, login, sem loja, gerente e lançamentos | T6, T7 |
| Cadastros no dashboard (R46) | T5 |
| Auditoria (7 ações) | T4, T5 |
| Identidade do produto | T1, T8 |
| Como se prova (lista inteira) | T2–T7, cada item com teste nomeado |

**Tipos e nomes conferidos entre tarefas:** `Recusa.frase`, `Lancamento(resultado, itens, motivo_id, observacao)`, `ItemLancado(grupo_id, valor)`, `retrato(filial, pessoa) -> Retrato(versao, atendendo, fila, em_pausa, meu)`, `Linha(pessoa_id, nome, estado, desde, posicao, tipo_de_pausa, e_voce)`, `lancamentos_de_hoje(filial, dia=None)`, rotas `fila`, `fila_estado`, `fila_agir`, `fila_grupos`, `fila_motivos`, `fila_pausas`, `inicio`.
