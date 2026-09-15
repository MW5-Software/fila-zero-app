# Plano 1 de 3: Cargos e alocações — o modelo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar as tabelas e as semeaduras de Cargos e alocações — `Cargo`, os cinco cargos de fábrica, `Alocacao`, a Matriz de toda empresa e `Orcamento.filial` — sem mudar ainda de onde vem a permissão de ninguém.

**Architecture:** Este é o primeiro de três planos. Ao fim dele o banco já tem o destino de tudo o que o desenho pede, e o sistema continua funcionando exatamente como hoje: `permissoes_de`, `do_contexto`, perfis e papéis não mudam. O plano 2 faz a virada (lugar, permissão pelo cargo, alcance, migração dos dados de hoje). O plano 3 faz as telas e a limpeza.

**Tech Stack:** Django 5.2, Python 3.13, Postgres 16, pytest + pytest-django, `django-test-migrations`.

**Spec:** `docs/superpowers/specs/2026-09-14-cargos-e-alocacoes-design.md`

## Por que três planos

A ordem do spec (modelo → lugar → alcance → telas → migração → limpeza) não
deixa software funcionando entre as fases. Trocar a fonte da permissão para o
cargo (fase 2) antes de migrar os dados (fase 5) deixa todo mundo sem permissão,
e quebra de uma vez os testes que montam gente por `dar_papel` e perfis. Então:

1. **Este plano** — as tabelas e as semeaduras, sem ligar em nada.
2. **A virada** — lugar e permissão pelo cargo, alcance, `e_cliente`, helpers de
   teste e a migração dos dados de hoje, juntos. A permissão só muda de fonte no
   mesmo passo em que o dado ganha o destino novo.
3. **Telas e limpeza** — cargos, alocações no cadastro de usuário, nova empresa,
   filiais; saem `Perfil`, `Papel` e `Filial.usuarios`; documentação.

## Global Constraints

- **Branch:** `cargos-e-alocacoes`, criada a partir da `main` antes da Task 1. Nada deste plano vai para a `main` sem pedido.
- **Rodar a suíte:** `cd /home/mw5/projetos/portal-de-vendas && DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings`
- **Um arquivo:** acrescente o caminho do teste ao comando acima.
- **Os 9 testes do ciclo real de backup** pulam sem `pg_dump`. Para rodá-los, crie na pasta de rascunho da sessão os scripts `pg_dump`, `pg_restore`, `psql`, `createdb`, `dropdb`, cada um com `exec docker run --rm -i --network host -e PGPASSWORD="$PGPASSWORD" postgres:16-alpine <comando> "$@"`, e ponha a pasta no começo do `PATH`. Rode com eles antes de cada commit que toque em migração.
- **Autor dos commits:** `João Victor Vancim <developer1@kronos.net.br>` via `git -c user.name=... -c user.email=...`. **Nunca** coautor Claude, nunca rodapé de "gerado com" (`CLAUDE.md` §5).
- **Commit em português, longo**, dizendo o que estava errado antes e por que a mudança é essa.
- **Comentário diz POR QUÊ**, em português, frase inteira.
- **Teste com dente:** toda trava deste plano é quebrada de propósito uma vez para ver vermelho, e desfeita. O passo está escrito em cada task.
- **`Cargo` e `Alocacao` moram no app `contas`**, que é isento da varredura do inquilino (`tests/test_regra_do_inquilino.py`, `APPS_DA_PLATAFORMA`). Por isso o isolamento entre contas delas é provado por teste próprio, e não pela varredura.
- **`NULL` não é igual a `NULL` numa unicidade do Postgres.** Toda unicidade com coluna anulável vira duas restrições parciais, e o teste grava a duplicata com a coluna vazia e exige `IntegrityError`.
- **`test_documentacao_nao_mente.py` confere a contagem de arquivos de teste no `CLAUDE.md`.** Cada task que cria arquivo de teste atualiza o número em todas as ocorrências (`ls tests/test_*.py | wc -l`).

## Mapa de arquivos

| arquivo | responsabilidade |
|---|---|
| `contas/models.py` | ganha `Alcance`, `Cargo` e `Alocacao` |
| `contas/cargos_de_fabrica.py` | a lista dos cinco cargos, `semear_cargos` e `garantir_cargos_de_fabrica` |
| `contas/apps.py` | liga o `post_save` do titular que semeia os cargos |
| `plataforma/apps.py` | chama `garantir_cargos_de_fabrica` no `post_migrate`; liga o `post_save` da empresa que cria a Matriz |
| `plataforma/models.py` | `Filial.e_matriz` e a unicidade da Matriz |
| `orcamento/models.py` | `Orcamento.filial` |
| `orcamento/visibilidade.py` | `carrinho_de` grava a Matriz no orçamento novo |
| `tests/conftest.py` | `matriz_do_teste` deixa de criar uma segunda Matriz |
| `tests/test_cargos_modelo.py` | Cargo |
| `tests/test_cargos_de_fabrica.py` | a semeadura |
| `tests/test_alocacao_modelo.py` | Alocacao |
| `tests/test_matriz.py` | a Matriz |
| `tests/test_migracao_matriz_e_filial_do_orcamento.py` | as duas migrações de dados |

---

### Task 1: `Cargo`

**Files:**
- Modify: `contas/models.py`
- Create: `contas/migrations/0013_cargo.py` (gerada)
- Test: `tests/test_cargos_modelo.py`

**Interfaces:**
- Produces:
  - `contas.models.Alcance` — `TextChoices` com `PROPRIOS = "proprios"`, `FILIAL = "filial"`, `EMPRESA = "empresa"`
  - `contas.models.Cargo` — campos `guid`, `conta` (FK `Usuario.guid`, coluna `conta_guid`), `nome` (slug), `rotulo`, `permissoes` (M2M `Permission`, `related_name="cargos"`), `alcance`, `e_cliente`, `de_fabrica`, `criado_em`; `related_name="cargos_da_conta"` no titular; unicidade `cargo_unico_por_conta` em `(conta, nome)`

- [ ] **Step 1: Criar a branch e medir a base**

```bash
cd /home/mw5/projetos/portal-de-vendas
git checkout -b cargos-e-alocacoes
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings 2>&1 | tail -2
```

Expected: tudo verde. Anote o número — é a base para comparar ao fim de cada task.

- [ ] **Step 2: Write the failing test**

Create `tests/test_cargos_modelo.py`:

```python
"""O cargo: um conjunto de permissões com nome, alcance e marca de cliente.

Substitui o `Perfil` (spec 2026-09-14, D9). Neste plano ele só existe: nenhuma
permissão de ninguém vem dele ainda — isso é o plano 2.

Mora no app `contas`, que a varredura do inquilino isenta. Por isso o
isolamento entre contas é provado aqui, e não por ela.
"""

import pytest
from django.contrib.auth.models import Permission
from django.db import IntegrityError

from contas.models import Alcance, Cargo, Nivel, Usuario


@pytest.fixture
def titular(db):
    return Usuario.objects.create_user(
        email="dono-cargo@teste.com", password="x", nivel=Nivel.TITULAR)


def test_o_cargo_guarda_a_conta_pelo_guid(titular):
    """A mesma identidade estável que `conta_guid` usa em toda linha de negócio
    — e não o id sequencial desta instalação."""
    cargo = Cargo.objects.create(conta=titular, nome="faturista",
                                 rotulo="Faturista", alcance=Alcance.FILIAL)
    cargo.refresh_from_db()
    assert cargo.conta_id == titular.guid


def test_o_alcance_padrao_e_o_minimo(titular):
    """Cargo novo sem alcance escolhido enxerga só os próprios registros. É o
    erro seguro: ver de menos se corrige na tela, ver de mais já vazou."""
    cargo = Cargo.objects.create(conta=titular, nome="caixa", rotulo="Caixa")
    assert cargo.alcance == Alcance.PROPRIOS
    assert cargo.e_cliente is False
    assert cargo.de_fabrica is False


def test_o_nome_e_unico_por_conta(titular):
    Cargo.objects.create(conta=titular, nome="faturista", rotulo="Faturista")
    with pytest.raises(IntegrityError):
        Cargo.objects.create(conta=titular, nome="faturista", rotulo="Outro")


def test_duas_contas_podem_ter_o_mesmo_nome(db, titular):
    """"Faturista" de um cliente não pode bater no "Faturista" de outro que ele
    nem conhece — o defeito que o `Perfil` teve até ganhar dono."""
    outro = Usuario.objects.create_user(
        email="outro-dono@teste.com", password="x", nivel=Nivel.TITULAR)
    Cargo.objects.create(conta=titular, nome="faturista", rotulo="Faturista")
    Cargo.objects.create(conta=outro, nome="faturista", rotulo="Faturista")
    assert Cargo.objects.filter(nome="faturista").count() == 2


def test_o_cargo_carrega_permissoes(titular):
    ver = Permission.objects.get(codename="catalogo_ver")
    cargo = Cargo.objects.create(conta=titular, nome="consulta",
                                 rotulo="Consulta")
    cargo.permissoes.add(ver)
    assert list(cargo.permissoes.values_list("codename", flat=True)) == [
        "catalogo_ver"]


def test_os_cargos_de_uma_conta_nao_aparecem_na_outra(db, titular):
    outro = Usuario.objects.create_user(
        email="outro-dono2@teste.com", password="x", nivel=Nivel.TITULAR)
    Cargo.objects.create(conta=titular, nome="so-do-titular", rotulo="X")
    assert not outro.cargos_da_conta.filter(nome="so-do-titular").exists()
    assert titular.cargos_da_conta.filter(nome="so-do-titular").exists()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_cargos_modelo.py`

Expected: FAIL com `ImportError: cannot import name 'Alcance' from 'contas.models'`.

- [ ] **Step 4: Escrever o model**

Em `contas/models.py`, logo **depois** da classe `Perfil` (antes de `RegistroImutavel`):

```python
class Alcance(models.TextChoices):
    """Quais registros um cargo enxerga.

    Mora no cargo, e não no código, por uma decisão do desenho (spec
    2026-09-14, D5): cargo criado depois pelo titular escolhe o alcance numa
    caixa, e nenhuma regra do sistema depende do NOME de um cargo. Um
    "Coordenador" criado amanhã enxerga a filial porque alguém marcou "a
    filial", e não porque um `if` conhece a palavra.
    """

    PROPRIOS = "proprios", "Os próprios"
    FILIAL = "filial", "A filial"
    EMPRESA = "empresa", "A empresa"


class Cargo(ComGuid):
    """O que uma pessoa pode fazer, e quais registros enxerga, NUM LUGAR.

    Substitui o `Perfil` (spec 2026-09-14, D9). A diferença que importa não é o
    nome: o perfil valia para a pessoa no sistema inteiro, e o cargo vale na
    alocação — a mesma pessoa pode ser Gerente numa filial e Vendedora noutra
    (D1). O cargo em si não sabe de lugar; quem liga cargo a lugar é
    `Alocacao`.

    **Neste momento nada lê este model para decidir permissão.** A virada é o
    plano 2; até lá `contas.backend.permissoes_de` continua somando perfis e
    permissões diretas, como sempre.
    """

    #: A conta dona do cargo, pela identidade estável — o GUID do titular, na
    #: coluna `conta_guid`, a mesma convenção de toda linha de negócio desde
    #: 14/09/2026.
    #:
    #: `CASCADE`: apagar o titular leva os cargos da conta. Na prática isso não
    #: acontece sozinho — `Empresa.dono` é `PROTECT` e `Alocacao.cargo` também —,
    #: e um cargo sem conta não teria a quem pertencer.
    conta = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="conta", to_field="guid",
        db_column="conta_guid", on_delete=models.CASCADE,
        related_name="cargos_da_conta",
        help_text=_("A conta dona deste cargo, pelo GUID do titular."))

    nome = models.SlugField("nome", max_length=60)
    rotulo = models.CharField("rótulo", max_length=120)
    permissoes = models.ManyToManyField(
        Permission, verbose_name="permissões", blank=True,
        related_name="cargos")
    #: `PROPRIOS` como padrão: ver de menos se corrige na tela; ver de mais já
    #: vazou.
    alcance = models.CharField(
        "alcance", max_length=20, choices=Alcance.choices,
        default=Alcance.PROPRIOS)
    #: O cargo se comporta como CLIENTE: preço de cliente, compra na vitrine,
    #: orçamento próprio. Existe porque o alcance não diz isso — um Vendedor
    #: pode enxergar "os próprios" e não ser cliente de ninguém.
    e_cliente = models.BooleanField("é cliente", default=False)
    #: Veio da semeadura (`contas/cargos_de_fabrica.py`). A tela não oferece
    #: apagar: a próxima semeadura o recriaria em silêncio.
    de_fabrica = models.BooleanField("de fábrica", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "cargo"
        verbose_name_plural = "cargos"
        ordering = ("rotulo",)
        constraints = [
            models.UniqueConstraint(
                fields=("conta", "nome"), name="cargo_unico_por_conta",
                violation_error_message=(
                    "Já existe um cargo com este nome nesta conta.")),
        ]

    def __str__(self) -> str:
        return self.rotulo
```

Confira que `settings`, `Permission` e `_` já estão importados no topo de `contas/models.py` — o `Perfil` usa os três.

- [ ] **Step 5: Gerar a migração**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py makemigrations contas -n cargo`

Expected: `contas/migrations/0013_cargo.py` com `Create model Cargo`. Abra e confira `to_field='guid'`, `db_column='conta_guid'` e a restrição `cargo_unico_por_conta`.

- [ ] **Step 6: Run test to verify it passes**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_cargos_modelo.py tests/test_regra_guid.py`

Expected: 6 passed em `test_cargos_modelo.py`, e `test_regra_guid.py` verde com `Cargo` na varredura.

- [ ] **Step 7: Suíte inteira, contagem e commit**

```bash
N=$(ls tests/test_*.py | wc -l) && sed -i -E "s/\b[0-9]{2,3} arquivos\b/$N arquivos/g" CLAUDE.md
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings 2>&1 | tail -2
git add contas/models.py contas/migrations/0013_cargo.py tests/test_cargos_modelo.py CLAUDE.md
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat(cargos): o model Cargo, ainda sem ligar em nada

O Perfil valia para a pessoa no sistema inteiro. O desenho de 14/09 pede cargo
por lugar: a mesma pessoa Gerente numa filial e Vendedora noutra. Este é o
primeiro passo, e só cria a tabela — nenhuma permissão de ninguém vem dela ainda.

A conta vai pelo GUID do titular (conta_guid), a mesma identidade estável de toda
linha de negócio. O alcance mora no cargo e não no código, para cargo criado
depois escolher numa caixa em vez de depender de um if que conhece o nome; o
padrão é 'os próprios', porque ver de menos se corrige na tela e ver de mais já
vazou."
```

Confira antes do `git add` se a contagem de arquivos mudou em outro lugar do `CLAUDE.md`: o `sed` troca todas as ocorrências de "NN arquivos", e só a contagem de testes deve casar.

---

### Task 2: Os cinco cargos de fábrica

**Files:**
- Create: `contas/cargos_de_fabrica.py`
- Modify: `contas/apps.py`, `plataforma/apps.py`
- Test: `tests/test_cargos_de_fabrica.py`

**Interfaces:**
- Consumes: `contas.models.Cargo`, `contas.models.Alcance`, `contas.models.Nivel`
- Produces:
  - `contas.cargos_de_fabrica.DE_FABRICA: tuple[tuple[str, str, str, bool, tuple[str, ...]], ...]` — `(nome, rotulo, alcance, e_cliente, permissoes)`
  - `contas.cargos_de_fabrica.semear_cargos(conta, apps=None, using=None) -> int`
  - `contas.cargos_de_fabrica.garantir_cargos_de_fabrica(apps=None, using=None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cargos_de_fabrica.py`:

```python
"""Toda conta nasce com Supervisor, Gerente, Vendedor, Representante e Cliente.

Os valores iniciais estão no spec 2026-09-14 ("Os cargos de fábrica e o que eles
trazem"), e todos são editáveis pelo titular depois. A semeadura só CRIA o que
falta: rodar de novo não pode desfazer o ajuste que o titular fez.
"""

import pytest

from contas.cargos_de_fabrica import (DE_FABRICA, garantir_cargos_de_fabrica,
                                      semear_cargos)
from contas.models import Alcance, Cargo, Nivel, Usuario


def _permissoes(cargo):
    return set(cargo.permissoes.values_list("codename", flat=True))


@pytest.fixture
def titular(db):
    return Usuario.objects.create_user(
        email="dono-fabrica@teste.com", password="x", nivel=Nivel.TITULAR)


def test_a_lista_de_fabrica_e_a_do_spec():
    assert [(nome, alcance, cliente) for nome, _r, alcance, cliente, _p
            in DE_FABRICA] == [
        ("supervisor", "empresa", False),
        ("gerente", "filial", False),
        ("vendedor", "filial", False),
        ("representante", "filial", False),
        ("cliente", "proprios", True),
    ]


def test_o_titular_novo_nasce_com_os_cinco(titular):
    """O `post_save` semeia. Titular nasce por mais de um caminho (a tela de
    usuários, o shell, um teste), e cada caminho que lembrasse de semear seria
    um caminho que um dia esquece."""
    nomes = set(Cargo.objects.filter(conta=titular)
                .values_list("nome", flat=True))
    assert nomes == {"supervisor", "gerente", "vendedor", "representante",
                     "cliente"}
    assert all(c.de_fabrica for c in Cargo.objects.filter(conta=titular))


def test_as_permissoes_iniciais(titular):
    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}
    assert _permissoes(cargos["supervisor"]) == {
        "catalogo_ver", "catalogo_editar", "orcamentos_ver",
        "orcamentos_acompanhar", "usuarios_editar"}
    assert _permissoes(cargos["vendedor"]) == {
        "catalogo_ver", "orcamentos_ver", "orcamentos_acompanhar"}
    assert _permissoes(cargos["cliente"]) == {"catalogo_ver", "orcamentos_ver"}
    assert cargos["cliente"].e_cliente is True
    assert cargos["gerente"].alcance == Alcance.FILIAL


def test_quem_nao_e_titular_nao_ganha_cargos(db):
    """Cargo é da CONTA, e conta é o titular. Pessoa da conta não tem cargos
    próprios, e a MW5 não é conta de ninguém."""
    membro = Usuario.objects.create_user(
        email="membro-fabrica@teste.com", password="x", nivel=Nivel.VENDEDOR)
    mw5 = Usuario.objects.create_user(
        email="mw5-fabrica@teste.com", password="x", nivel=Nivel.MASTER)
    assert not Cargo.objects.filter(conta__in=[membro, mw5]).exists()


def test_semear_de_novo_nao_duplica(titular):
    assert semear_cargos(titular) == 0
    assert Cargo.objects.filter(conta=titular).count() == 5


def test_semear_de_novo_nao_desfaz_o_ajuste_do_titular(titular):
    vendedor = Cargo.objects.get(conta=titular, nome="vendedor")
    vendedor.permissoes.clear()
    vendedor.alcance = Alcance.PROPRIOS
    vendedor.save()

    semear_cargos(titular)

    vendedor.refresh_from_db()
    assert vendedor.alcance == Alcance.PROPRIOS
    assert _permissoes(vendedor) == set()


def test_promover_a_titular_semeia(db):
    """`dar_acesso` e a tela de usuários promovem com `save(update_fields=...)`.
    O receptor precisa pegar esse caminho, e não só o `create`."""
    pessoa = Usuario.objects.create_user(
        email="promovida@teste.com", password="x", nivel=Nivel.VENDEDOR)
    pessoa.nivel = Nivel.TITULAR
    pessoa.save(update_fields=["nivel"])
    assert Cargo.objects.filter(conta=pessoa).count() == 5


def test_garantir_cobre_titular_que_ja_existia(titular):
    """O `post_migrate` da instalação que atualiza: titulares que nasceram antes
    desta mudança ganham os cargos na primeira `migrate`."""
    Cargo.objects.filter(conta=titular).delete()
    assert garantir_cargos_de_fabrica() == 5
    assert Cargo.objects.filter(conta=titular).count() == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_cargos_de_fabrica.py`

Expected: FAIL com `ModuleNotFoundError: No module named 'contas.cargos_de_fabrica'`.

- [ ] **Step 3: Escrever a semeadura**

Create `contas/cargos_de_fabrica.py`:

```python
"""Os cinco cargos com que toda conta nasce, e como eles chegam lá.

Os valores vêm do spec 2026-09-14 ("Os cargos de fábrica e o que eles trazem").
São **iniciais**: o titular edita permissões e alcance de qualquer um depois, e
por isso a semeadura só CRIA o que falta e nunca toca no que já existe —
rodá-la de novo desfaria o ajuste que o titular fez.

**Por que dois caminhos de semeadura, e não um.**

- `post_save` do titular (`contas/apps.py`): a conta nova nasce com os cargos.
  Titular nasce por mais de um caminho — a tela de usuários, o shell, um teste —,
  e cada caminho que lembrasse de semear seria um que um dia esquece.
- `post_migrate` (`plataforma/apps.py`): o titular que já existia antes desta
  mudança ganha os cargos na primeira `migrate` da atualização. Não é migração
  de dados de propósito: as `Permission` de módulo só existem depois de
  `contas.permissoes.materializar`, que também roda no `post_migrate` — numa
  migração elas podem ainda não estar lá, e o cargo nasceria vazio para sempre.

**Permissão que não existe é pulada, e não é erro.** Um módulo desligado do
código deixa de ter a permissão materializada; o cargo nasce sem ela em vez de
derrubar o cadastro de um titular.
"""

from __future__ import annotations

__all__ = ["DE_FABRICA", "garantir_cargos_de_fabrica", "semear_cargos"]

#: `(nome, rotulo, alcance, e_cliente, permissoes)`. Alcance em texto e
#: permissões no vocabulário do núcleo (`modulo.acao`), para esta lista não
#: depender de model nenhum.
DE_FABRICA: "tuple[tuple[str, str, str, bool, tuple[str, ...]], ...]" = (
    ("supervisor", "Supervisor", "empresa", False,
     ("catalogo.ver", "catalogo.editar", "orcamentos.ver",
      "orcamentos.acompanhar", "usuarios.editar")),
    ("gerente", "Gerente", "filial", False,
     ("catalogo.ver", "catalogo.editar", "orcamentos.ver",
      "orcamentos.acompanhar", "usuarios.editar")),
    #: Vendedor e Representante nascem com alcance FILIAL e com
    #: `orcamentos.acompanhar`: com "os próprios" não veriam orçamento nenhum
    #: (o orçamento não tem responsável, só `comprador`), e sem acompanhar o
    #: alcance não teria tela onde valer. Reverte o "parado de propósito" que
    #: `contas/fabrica.py` registra para o nível VENDEDOR em 09/09/2026.
    ("vendedor", "Vendedor", "filial", False,
     ("catalogo.ver", "orcamentos.ver", "orcamentos.acompanhar")),
    ("representante", "Representante", "filial", False,
     ("catalogo.ver", "orcamentos.ver", "orcamentos.acompanhar")),
    #: O que `Nivel.COMPRADOR` dá hoje em `contas/fabrica.py`.
    ("cliente", "Cliente", "proprios", True,
     ("catalogo.ver", "orcamentos.ver")),
)

#: Nível TITULAR congelado como literal: esta função roda com modelos
#: históricos no `post_migrate`, e a escala de `Nivel` já mudou duas vezes.
_TITULAR = 1


def _modelos(apps):
    if apps is None:
        from django.apps import apps as apps_reais

        apps = apps_reais
    return (apps.get_model("contas", "Cargo"),
            apps.get_model("auth", "Permission"))


def semear_cargos(conta, apps=None, using=None) -> int:
    """Dá à `conta` os cargos de fábrica que ela ainda não tem. Devolve quantos
    criou."""
    from .permissoes import CONTENT_TYPE

    Cargo, Permission = _modelos(apps)
    cargos = Cargo.objects.db_manager(using) if using else Cargo.objects
    permissoes = (Permission.objects.db_manager(using) if using
                  else Permission.objects)

    tem = set(cargos.filter(conta_id=conta.guid)
              .values_list("nome", flat=True))
    app_label, model = CONTENT_TYPE
    criados = 0
    for nome, rotulo, alcance, e_cliente, chaves in DE_FABRICA:
        if nome in tem:
            continue
        cargo = cargos.create(conta_id=conta.guid, nome=nome, rotulo=rotulo,
                              alcance=alcance, e_cliente=e_cliente,
                              de_fabrica=True)
        cargo.permissoes.set(permissoes.filter(
            content_type__app_label=app_label, content_type__model=model,
            codename__in=[chave.replace(".", "_") for chave in chaves]))
        criados += 1
    return criados


def garantir_cargos_de_fabrica(apps=None, using=None) -> int:
    """Semeia todo titular desta instalação. Devolve quantos cargos criou.

    Chamado no `post_migrate`. Numa `migrate` parcial, ou revertendo para antes
    de `contas.0013`, o model histórico ainda não tem `Cargo` — e aí não há o
    que semear.
    """
    try:
        _modelos(apps)
    except LookupError:
        return 0
    if apps is None:
        from django.apps import apps as apps_reais

        apps = apps_reais
    Usuario = apps.get_model("contas", "Usuario")
    pessoas = Usuario.objects.db_manager(using) if using else Usuario.objects
    return sum(semear_cargos(titular, apps=apps, using=using)
               for titular in pessoas.filter(nivel=_TITULAR))
```

- [ ] **Step 4: Ligar os dois caminhos**

Em `contas/apps.py`, no fim de `ready()`:

```python
        from django.db.models.signals import post_save

        # `dispatch_uid` para o receptor não ser ligado duas vezes se `ready()`
        # for chamado de novo num teste — a conta nova nasceria semeada duas
        # vezes, e a segunda bateria na unicidade `cargo_unico_por_conta`.
        post_save.connect(_semear_cargos_do_titular, sender="contas.Usuario",
                          dispatch_uid="contas_semear_cargos_do_titular")
```

E, fora da classe, no fim do arquivo:

```python
def _semear_cargos_do_titular(sender, instance, **kwargs):
    """A conta nova nasce com os cinco cargos de fábrica.

    Em todo `save`, e não só no `created`: `dar_acesso` e a tela de usuários
    promovem a titular com `save(update_fields=["nivel"])`. A semeadura é
    idempotente — só cria o que falta —, então o custo nos outros saves é uma
    consulta.
    """
    from .models import Nivel

    if instance.nivel != Nivel.TITULAR:
        return
    from .cargos_de_fabrica import semear_cargos

    semear_cargos(instance)
```

Em `plataforma/apps.py`, dentro de `_semear_apos_migrar`, logo **depois** da chamada `garantir_perfis_do_sistema(apps, using=using)`:

```python
    # Depois de materializar, nunca antes: os cargos de fábrica nascem com
    # `Permission` de módulo, e elas só existem depois de `materializar`. É por
    # isso que isto é `post_migrate` e não migração de dados — ver
    # `contas/cargos_de_fabrica.py`. Import tardio pelo mesmo motivo dos de cima.
    from contas.cargos_de_fabrica import garantir_cargos_de_fabrica

    garantir_cargos_de_fabrica(apps, using=using)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_cargos_de_fabrica.py`

Expected: 8 passed.

- [ ] **Step 6: Provar a trava de idempotência**

Troque em `semear_cargos` o `if nome in tem: continue` por nada (apague as duas linhas) e rode `test_semear_de_novo_nao_duplica`. Deve ficar vermelho com `IntegrityError` na `cargo_unico_por_conta`. Desfaça e rode de novo para ver verde.

- [ ] **Step 7: Suíte inteira**

Run: a suíte inteira.

Expected: tudo verde. **Se algo quebrar**, a causa esperada é teste que conta `Permission` ligadas a M2M, ou teste que monta titular com `password` e confere quantas linhas foram criadas. A correção é no teste — contar só o que ele criou —, nunca desligar a semeadura.

- [ ] **Step 8: Contagem e commit**

```bash
N=$(ls tests/test_*.py | wc -l) && sed -i -E "s/\b[0-9]{2,3} arquivos\b/$N arquivos/g" CLAUDE.md
git add contas/cargos_de_fabrica.py contas/apps.py plataforma/apps.py tests/test_cargos_de_fabrica.py CLAUDE.md
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat(cargos): toda conta nasce com os cinco cargos de fábrica

Supervisor, Gerente, Vendedor, Representante e Cliente, com o alcance e as
permissões iniciais do desenho de 14/09. São iniciais: a semeadura só cria o que
falta e nunca mexe no que existe, senão rodar de novo desfaria o ajuste do titular.

Dois caminhos. O post_save do titular cobre a conta nova, inclusive a promovida
por save(update_fields=[nivel]) — que é como dar_acesso e a tela de usuários
promovem. O post_migrate cobre o titular que já existia antes da atualização, e é
post_migrate e não migração de dados porque as Permission de módulo só existem
depois de materializar: numa migração o cargo poderia nascer vazio para sempre."
```

---

### Task 3: `Alocacao`

**Files:**
- Modify: `contas/models.py`
- Create: `contas/migrations/0014_alocacao.py` (gerada)
- Test: `tests/test_alocacao_modelo.py`

**Interfaces:**
- Consumes: `Cargo`, `Nivel`, `plataforma.Empresa`, `plataforma.Filial`
- Produces: `contas.models.Alocacao` — campos `guid`, `conta` (`conta_guid`), `pessoa` (`related_name="alocacoes"`), `empresa`, `filial` (anulável = empresa inteira), `cargo`, `criada_em`; restrições `alocacao_unica_na_filial` e `alocacao_unica_na_empresa_inteira`

- [ ] **Step 1: Write the failing test**

Create `tests/test_alocacao_modelo.py`:

```python
"""A alocação: esta pessoa, neste lugar, com este cargo.

O cargo é da ALOCAÇÃO e não da pessoa (spec 2026-09-14, D1). Filial vazia é a
empresa inteira (D8). O titular e a MW5 não são alocados (D3).

Neste plano a alocação só existe e se valida; quem a lê para decidir lugar e
permissão é o plano 2.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from contas.models import Alocacao, Cargo, Nivel, Usuario


@pytest.fixture
def conta(db):
    """Um titular, a empresa dele, uma filial, um membro e o cargo Vendedor."""
    from plataforma.models import Empresa, Filial

    titular = Usuario.objects.create_user(
        email="dono-aloc@teste.com", password="x", nivel=Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    norte = Filial.objects.create(empresa=empresa, nome="Norte",
                                  apelido="Norte", ordem=5)
    ana = Usuario.objects.create_user(
        email="ana-aloc@teste.com", password="x", nivel=Nivel.VENDEDOR,
        dono=titular)
    vendedor = Cargo.objects.get(conta=titular, nome="vendedor")
    return titular, empresa, norte, ana, vendedor


def test_aloca_numa_filial(conta):
    titular, empresa, norte, ana, vendedor = conta
    alocacao = Alocacao.objects.create(pessoa=ana, empresa=empresa,
                                       filial=norte, cargo=vendedor)
    assert alocacao.conta_id == titular.guid


def test_aloca_na_empresa_inteira(conta):
    _t, empresa, _n, ana, vendedor = conta
    alocacao = Alocacao.objects.create(pessoa=ana, empresa=empresa,
                                       cargo=vendedor)
    assert alocacao.filial_id is None


def test_empresa_inteira_e_filial_convivem_para_a_mesma_pessoa(conta):
    """É o que dá sentido a "a mais específica ganha" (plano 2)."""
    titular, empresa, norte, ana, vendedor = conta
    gerente = Cargo.objects.get(conta=titular, nome="gerente")
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=gerente)
    Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                            cargo=vendedor)
    assert ana.alocacoes.count() == 2


def test_duas_alocacoes_na_mesma_filial_falham(conta):
    _t, empresa, norte, ana, vendedor = conta
    Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                            cargo=vendedor)
    with pytest.raises(IntegrityError):
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=vendedor)


def test_duas_alocacoes_na_empresa_inteira_falham(conta):
    """**O teste que justifica a segunda restrição.** `NULL` não é igual a
    `NULL` numa unicidade do Postgres: com uma restrição só, esta segunda linha
    entraria."""
    _t, empresa, _n, ana, vendedor = conta
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=vendedor)
    with pytest.raises(IntegrityError):
        Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=vendedor)


def test_cargo_de_outra_conta_e_recusado(conta, db):
    _t, empresa, _n, ana, _v = conta
    outro = Usuario.objects.create_user(
        email="outro-aloc@teste.com", password="x", nivel=Nivel.TITULAR)
    alheio = Cargo.objects.get(conta=outro, nome="vendedor")
    with pytest.raises(ValidationError, match="cargo"):
        Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=alheio)


def test_pessoa_de_outra_conta_e_recusada(conta, db):
    _t, empresa, _n, _a, vendedor = conta
    outro = Usuario.objects.create_user(
        email="outro-dono-aloc@teste.com", password="x", nivel=Nivel.TITULAR)
    estranha = Usuario.objects.create_user(
        email="estranha@teste.com", password="x", nivel=Nivel.VENDEDOR,
        dono=outro)
    with pytest.raises(ValidationError, match="pessoa"):
        Alocacao.objects.create(pessoa=estranha, empresa=empresa,
                                cargo=vendedor)


def test_o_titular_nao_e_alocado(conta):
    """D3: o dono alcança tudo por ser dono. Alocá-lo daria a ele um cargo que
    poderia tirar dele mesmo o acesso à própria conta."""
    titular, empresa, _n, _a, vendedor = conta
    with pytest.raises(ValidationError, match="pessoa"):
        Alocacao.objects.create(pessoa=titular, empresa=empresa,
                                cargo=vendedor)


def test_filial_de_outra_empresa_e_recusada(conta):
    from plataforma.models import Empresa, Filial

    titular, empresa, _n, ana, vendedor = conta
    outra = Empresa.objects.create(razao_social="Beta Ltda")
    longe = Filial.objects.create(empresa=outra, nome="Longe", apelido="Longe")
    with pytest.raises(ValidationError, match="filial"):
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=longe,
                                cargo=vendedor)


def test_empresa_sem_titular_nao_recebe_alocacao(conta):
    from plataforma.models import Empresa

    _t, _e, _n, ana, vendedor = conta
    orfa = Empresa.objects.create(razao_social="Sem Dono Ltda")
    with pytest.raises(ValidationError):
        Alocacao.objects.create(pessoa=ana, empresa=orfa, cargo=vendedor)


def test_cargo_com_alocacao_nao_se_apaga(conta):
    """`PROTECT` no banco, e não só uma frase na tela: a tela nunca é a única
    porta."""
    from django.db.models import ProtectedError

    _t, empresa, _n, ana, vendedor = conta
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=vendedor)
    with pytest.raises(ProtectedError):
        vendedor.delete()
```

**Nota sobre `dar_acesso`/`abrir_conta`:** este teste cria a empresa com `dono=titular` direto, e isso só funciona se `Empresa.objects.create(razao_social=..., dono=...)` não exigir CNPJ. Os testes de `tests/test_regra_do_inquilino.py` já fazem exatamente isso, então funciona.

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_alocacao_modelo.py`

Expected: FAIL com `ImportError: cannot import name 'Alocacao'`.

- [ ] **Step 3: Escrever o model**

Em `contas/models.py`, logo depois de `Cargo`:

```python
class Alocacao(ComGuid):
    """Esta pessoa, neste lugar, com este cargo.

    O cargo é da alocação, e não da pessoa (spec 2026-09-14, D1): a mesma Ana é
    Gerente na filial Centro e Vendedora na Norte. `filial` vazia é a empresa
    inteira, inclusive as filiais criadas depois (D8).

    **A unicidade são DUAS restrições parciais.** `NULL` não é igual a `NULL`
    numa unicidade do Postgres, e a filial vazia é justamente a alocação mais
    ampla: com uma restrição só, a mesma pessoa poderia ter duas alocações "na
    empresa inteira" com cargos diferentes, e "qual cargo vale" deixaria de ter
    resposta. As duas restrições permitem, de propósito, uma alocação na empresa
    inteira E outra numa filial — é o que dá sentido a "a mais específica ganha".

    **O titular e a MW5 não são alocados** (D3). O dono alcança tudo por ser
    dono; alocá-lo daria a ele um cargo capaz de tirar dele o acesso à própria
    conta.

    Não herda `ModeloDaEmpresa`, embora tenha `empresa`: o manager dele lê o
    lugar da requisição, e é JUSTAMENTE a alocação que decide o lugar. Herdar
    faria a pergunta "onde a pessoa está?" depender da resposta.
    """

    conta = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="conta", to_field="guid",
        db_column="conta_guid", on_delete=models.CASCADE, related_name="+",
        help_text=_("A conta dona desta alocação, pelo GUID do titular."))
    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="pessoa",
        on_delete=models.CASCADE, related_name="alocacoes")
    empresa = models.ForeignKey(
        "plataforma.Empresa", verbose_name="empresa",
        on_delete=models.PROTECT, related_name="alocacoes")
    #: Vazia é a empresa inteira.
    filial = models.ForeignKey(
        "plataforma.Filial", verbose_name="filial", null=True, blank=True,
        on_delete=models.PROTECT, related_name="alocacoes")
    #: `PROTECT`: cargo com gente dentro não se apaga pelo banco, e não só pela
    #: frase da tela — a tela nunca é a única porta.
    cargo = models.ForeignKey(
        Cargo, verbose_name="cargo", on_delete=models.PROTECT,
        related_name="alocacoes")
    criada_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "alocação"
        verbose_name_plural = "alocações"
        constraints = [
            models.UniqueConstraint(
                fields=("pessoa", "empresa", "filial"),
                condition=models.Q(filial__isnull=False),
                name="alocacao_unica_na_filial"),
            models.UniqueConstraint(
                fields=("pessoa", "empresa"),
                condition=models.Q(filial__isnull=True),
                name="alocacao_unica_na_empresa_inteira"),
        ]

    def clean(self) -> None:
        """As quatro recusas. Cada uma protege a fronteira entre contas, que é a
        única classe de defeito que este produto não pode ter."""
        super().clean()
        if not self.empresa_id:
            return
        erros = {}
        empresa = self.empresa
        if empresa.conta_id is None:
            erros["empresa"] = ("A empresa precisa ter um titular antes de "
                                "receber alocações.")
        else:
            if self.cargo_id and self.cargo.conta_id != empresa.conta_id:
                erros["cargo"] = "Este cargo não é da conta desta empresa."
            if self.pessoa_id:
                pessoa = self.pessoa
                if pessoa.nivel <= Nivel.TITULAR:
                    erros["pessoa"] = ("O titular e a MW5 não são alocados: "
                                       "eles alcançam a conta inteira.")
                elif pessoa.dono_id != empresa.dono_id:
                    erros["pessoa"] = "Esta pessoa não é desta conta."
        if self.filial_id and self.filial.empresa_id != self.empresa_id:
            erros["filial"] = "Esta filial não é desta empresa."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        """A conta vem da empresa — nunca de quem chama —, e então valida.

        `validate_constraints=False`: a unicidade é decidida pelo BANCO, sem
        corrida entre duas requisições, como em `ModeloDaEmpresa.save`.
        """
        if self.empresa_id:
            self.conta_id = self.empresa.conta_id
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        onde = self.filial or self.empresa
        return f"{self.pessoa} — {self.cargo} em {onde}"
```

Confira que `ValidationError` está importado no topo de `contas/models.py`; se não estiver, `from django.core.exceptions import ValidationError`.

- [ ] **Step 4: Gerar a migração**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py makemigrations contas -n alocacao`

Expected: `contas/migrations/0014_alocacao.py`. **Abra e confira as duas `UniqueConstraint`** — uma com `condition=Q(filial__isnull=False)` e outra com `Q(filial__isnull=True)`. Confira também que ela depende de uma migração de `plataforma`.

- [ ] **Step 5: Run test to verify it passes**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_alocacao_modelo.py`

Expected: 11 passed.

- [ ] **Step 6: Provar as duas travas que mais importam**

1. Comente a restrição `alocacao_unica_na_empresa_inteira`, gere uma migração temporária (`makemigrations contas -n mutacao`), rode `test_duas_alocacoes_na_empresa_inteira_falham`. Deve dar `DID NOT RAISE`. Desfaça o comentário e **apague** a migração temporária.
2. Troque `elif pessoa.dono_id != empresa.dono_id:` por `elif False:` e rode `test_pessoa_de_outra_conta_e_recusada`. Vermelho. Desfaça.

- [ ] **Step 7: Suíte inteira, contagem e commit**

```bash
ls contas/migrations/ | tail -3    # nenhuma migração "mutacao" sobrando
N=$(ls tests/test_*.py | wc -l) && sed -i -E "s/\b[0-9]{2,3} arquivos\b/$N arquivos/g" CLAUDE.md
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings 2>&1 | tail -2
git add contas/models.py contas/migrations/0014_alocacao.py tests/test_alocacao_modelo.py CLAUDE.md
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat(cargos): a alocação — esta pessoa, neste lugar, com este cargo

O cargo é da alocação e não da pessoa, e filial vazia é a empresa inteira. A
unicidade são duas restrições parciais porque NULL não é igual a NULL no
Postgres: com uma só, a mesma pessoa teria duas alocações na empresa inteira e
'qual cargo vale' deixaria de ter resposta. A mutação foi feita, e tirar a segunda
restrição deixa o teste em DID NOT RAISE.

As quatro recusas protegem a fronteira entre contas: cargo de outra conta, pessoa
de outra conta, filial de outra empresa, e empresa sem titular. O titular e a MW5
não são alocados, porque alcançam a conta inteira e um cargo poderia tirar do
dono o acesso à própria conta.

Não herda ModeloDaEmpresa embora tenha empresa: o manager dela leria o lugar da
requisição, e é justamente a alocação que decide o lugar."
```

---

### Task 4: Toda empresa tem a Matriz

**Files:**
- Modify: `plataforma/models.py`, `plataforma/apps.py`, `tests/conftest.py`
- Create: `plataforma/migrations/0005_filial_e_matriz.py` (gerada), `plataforma/migrations/0006_toda_empresa_tem_matriz.py`
- Test: `tests/test_matriz.py`

**Interfaces:**
- Produces: `plataforma.models.Filial.e_matriz: bool`; restrição `uma_matriz_por_empresa`; empresa nova nasce com `Filial(e_matriz=True, nome="Matriz")`

- [ ] **Step 1: Write the failing test**

Create `tests/test_matriz.py`:

```python
"""Toda empresa tem a Matriz (spec 2026-09-14, D7).

A Matriz é marcada por `e_matriz`, e não pelo nome: o titular pode renomeá-la, e
uma regra que procurasse a palavra "Matriz" deixaria de achar a filial no dia do
primeiro "Loja Centro".
"""

import pytest
from django.db import IntegrityError


@pytest.fixture
def empresa(db):
    from plataforma.models import Empresa

    return Empresa.objects.create(razao_social="Alfa Ltda")


def test_empresa_nova_nasce_com_a_matriz(empresa):
    matriz = empresa.filiais.get(e_matriz=True)
    assert matriz.nome == "Matriz"
    assert matriz.ativa is True


def test_editar_a_empresa_nao_cria_outra_matriz(empresa):
    empresa.razao_social = "Alfa Comércio Ltda"
    empresa.save()
    assert empresa.filiais.filter(e_matriz=True).count() == 1


def test_uma_matriz_por_empresa(empresa):
    from plataforma.models import Filial

    with pytest.raises(IntegrityError):
        Filial.objects.create(empresa=empresa, nome="Outra", apelido="Outra",
                              e_matriz=True)


def test_duas_empresas_tem_cada_uma_a_sua(empresa, db):
    from plataforma.models import Empresa, Filial

    Empresa.objects.create(razao_social="Beta Ltda")
    assert Filial.objects.filter(e_matriz=True).count() == 2


def test_a_matriz_renomeada_continua_sendo_a_matriz(empresa):
    matriz = empresa.filiais.get(e_matriz=True)
    matriz.nome = "Loja Centro"
    matriz.apelido = "Centro"
    matriz.save()
    assert empresa.filiais.get(e_matriz=True).nome == "Loja Centro"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_matriz.py`

Expected: FAIL com `FieldError: Cannot resolve keyword 'e_matriz'`.

- [ ] **Step 3: O campo e a restrição**

Em `plataforma/models.py`, na classe `Filial`, logo depois de `ordem`:

```python
    #: A filial com que a empresa nasceu (spec 2026-09-14, D7). Marcada por
    #: campo e não pelo nome: o titular pode renomeá-la, e uma regra que
    #: procurasse "Matriz" deixaria de achá-la no primeiro "Loja Centro".
    e_matriz = models.BooleanField("é a matriz", default=False)
```

E na `Meta` de `Filial` (hoje ela só tem `verbose_name`, `verbose_name_plural` e `ordering`), acrescente:

```python
        constraints = [
            # Parcial: só as linhas marcadas contam. Sem `condition`, a
            # restrição proibiria a segunda filial NÃO matriz da mesma empresa.
            models.UniqueConstraint(
                fields=("empresa",), condition=models.Q(e_matriz=True),
                name="uma_matriz_por_empresa"),
        ]
```

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py makemigrations plataforma -n filial_e_matriz`

Expected: `plataforma/migrations/0005_filial_e_matriz.py` com `AddField` e `AddConstraint`.

- [ ] **Step 4: A empresa nova nasce com a Matriz**

Em `plataforma/apps.py`, no fim de `PlataformaConfig.ready()`:

```python
        from django.db.models.signals import post_save

        post_save.connect(_criar_a_matriz, sender="plataforma.Empresa",
                          dispatch_uid="plataforma_criar_a_matriz")
```

E, no nível do módulo:

```python
def _criar_a_matriz(sender, instance, created, **kwargs):
    """A empresa nova nasce com a filial Matriz (spec 2026-09-14, D7).

    No `post_save` e não na tela: empresa nasce por mais de um caminho (a tela
    do titular, o shell, a restauração de um backup, um teste), e cada caminho
    que lembrasse seria um que um dia esquece — e empresa sem filial não tem
    onde alocar ninguém.

    **Esta semeadura já existiu e saiu** em 09/09/2026: ela rodava no
    `post_migrate` e criava uma Matriz pendurada numa empresa sem dono. Aqui ela
    nasce presa à empresa que acabou de ser criada, e só no `created`.

    `raw`: `loaddata` e a restauração gravam a Matriz que já vem no arquivo.
    Criar outra aqui bateria na `uma_matriz_por_empresa`.
    """
    if not created or kwargs.get("raw"):
        return
    from .models import Filial

    Filial.objects.create(empresa=instance, nome="Matriz", apelido="Matriz",
                          ordem=0, e_matriz=True)
```

- [ ] **Step 5: As empresas que já existem**

Create `plataforma/migrations/0006_toda_empresa_tem_matriz.py`:

```python
"""Toda empresa que já existe ganha a sua Matriz (spec 2026-09-14, D7).

Três casos, e a regra de cada um é a menos surpreendente possível:

1. Empresa sem filial nenhuma → ganha uma filial "Matriz".
2. Empresa com uma filial chamada "Matriz" (sem caixa e sem espaço) → essa é a
   matriz. É o nome que a semeadura antiga usava até 09/09/2026.
3. Empresa com filiais e nenhuma chamada "Matriz" → a de menor (`ordem`, `pk`)
   vira a matriz. É a primeira do seletor do cabeçalho, que é a que as pessoas
   já viam como "a principal".

**Filial sem empresa não é resolvida aqui.** Não há como deduzir de quem ela é, e
o plano 2 é quem a trata (a migração que torna `Filial.empresa` obrigatória para
com erro e lista os ids).

`desfazer` só desmarca: as filiais criadas no caso 1 ficam, porque apagá-las
poderia levar junto alocação ou orçamento que já as usa.
"""

from django.db import migrations


def _marcar(apps, schema_editor):
    Empresa = apps.get_model("plataforma", "Empresa")
    Filial = apps.get_model("plataforma", "Filial")

    for empresa in Empresa.objects.all().iterator():
        filiais = Filial.objects.filter(empresa=empresa)
        if filiais.filter(e_matriz=True).exists():
            continue
        if not filiais.exists():
            Filial.objects.create(empresa=empresa, nome="Matriz",
                                  apelido="Matriz", ordem=0, e_matriz=True)
            continue
        pelo_nome = [f for f in filiais
                     if (f.nome or "").strip().casefold() == "matriz"]
        escolhida = (pelo_nome[0] if pelo_nome
                     else filiais.order_by("ordem", "pk").first())
        Filial.objects.filter(pk=escolhida.pk).update(e_matriz=True)


def _desmarcar(apps, schema_editor):
    apps.get_model("plataforma", "Filial").objects.update(e_matriz=False)


class Migration(migrations.Migration):

    dependencies = [
        ("plataforma", "0005_filial_e_matriz"),
    ]

    operations = [
        migrations.RunPython(_marcar, _desmarcar),
    ]
```

- [ ] **Step 6: Run the Matriz test**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_matriz.py`

Expected: 5 passed.

- [ ] **Step 7: `matriz_do_teste` não pode criar uma segunda Matriz**

Em `tests/conftest.py`, a função `matriz_do_teste` hoje procura uma filial chamada "Matriz", e se não achar cria a empresa e **depois** cria a filial "Matriz". Com a empresa nascendo com a Matriz, isso gera duas. Troque o corpo por:

```python
    from plataforma.models import Empresa, Filial

    ja = Filial.objects.filter(e_matriz=True).first() or \
        Filial.objects.filter(nome="Matriz").first()
    if ja is not None:
        return ja
    empresa = Empresa.objects.first() or Empresa.objects.create(
        razao_social="Empresa do Teste")
    # A empresa nasce com a Matriz desde 14/09/2026 (`plataforma/apps.py`).
    # Uma empresa que já existia antes do teste pode não ter — por isso o
    # `or create`, e com `e_matriz` para não haver duas.
    return (empresa.filiais.filter(e_matriz=True).first()
            or Filial.objects.create(nome="Matriz", apelido="Matriz",
                                     empresa=empresa, e_matriz=True))
```

Mantenha a docstring que já existe acima do corpo, e acrescente a ela a frase: _"Desde 14/09/2026 a empresa nasce com a Matriz, e esta função devolve a que já existe em vez de criar uma segunda."_

- [ ] **Step 8: Suíte inteira — e o que é esperado quebrar**

Run: a suíte inteira.

Toda empresa criada em teste passa a trazer uma filial ativa a mais. Três classes de falha são esperadas, e cada uma tem a correção certa:

1. **Teste que conta filiais** (`Filial.objects.count()`, `len(...)` numa lista de filiais) → conte a partir de antes da ação, ou exclua a Matriz: `Filial.objects.exclude(e_matriz=True)`.
2. **Teste de "última filial ativa"** (`plataforma/filiais.py`, `pode_desativar`), que monta uma filial solta e espera a recusa → a Matriz de uma empresa criada no mesmo teste é outra filial ativa. Use a Matriz como a filial do teste, em vez de criar uma segunda.
3. **Teste que cria uma filial chamada "Matriz" para a empresa** → use `empresa.filiais.get(e_matriz=True)`.

**O que NÃO se faz:** desligar o receptor em teste, ou afrouxar uma asserção sobre comportamento de produto. Se uma falha não cair nas três classes acima, pare e investigue — ela é um defeito, não um teste velho.

Liste as falhas e corrija uma classe de cada vez, rodando o arquivo afetado entre elas.

- [ ] **Step 9: Provar a trava da unicidade parcial**

Tire o `condition=models.Q(e_matriz=True)` da restrição, gere migração temporária, rode `tests/test_matriz.py tests/test_tela_filiais.py`. Criar a segunda filial de uma empresa deve quebrar com `IntegrityError` — é a prova de que a `condition` é o que permite várias filiais. Desfaça e apague a migração temporária.

- [ ] **Step 10: Conferir a migração num banco com dado**

```bash
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py migrate plataforma 2>&1 | tail -3
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py shell -c "
from plataforma.models import Empresa
sem = [e.pk for e in Empresa.objects.all() if not e.filiais.filter(e_matriz=True).exists()]
print('empresas sem matriz:', sem)"
```

Expected: `empresas sem matriz: []`. Este é o banco de desenvolvimento `kronos`, local — nunca o de uma instalação.

- [ ] **Step 11: Contagem e commit**

```bash
N=$(ls tests/test_*.py | wc -l) && sed -i -E "s/\b[0-9]{2,3} arquivos\b/$N arquivos/g" CLAUDE.md
git add plataforma tests CLAUDE.md
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat(filiais): toda empresa nasce com a Matriz, marcada por campo

A alocação precisa de lugar, e empresa sem filial não tem onde alocar ninguém.
A empresa nova nasce com a Matriz no post_save; as que já existem ganham a delas
numa migração de dados — a filial chamada Matriz, senão a primeira do seletor,
senão uma nova.

Marcada por e_matriz e não pelo nome: o titular pode renomeá-la, e procurar a
palavra deixaria de achá-la no primeiro 'Loja Centro'. A unicidade é parcial; sem
a condition ela proibiria a segunda filial da mesma empresa, e a mutação provou
isso.

A semeadura da Matriz já existiu e saiu em 09/09, quando rodava no post_migrate e
pendurava filial em empresa sem dono. Aqui ela nasce presa à empresa recém-criada,
só no created, e pula o raw para a restauração de backup não criar uma segunda."
```

---

### Task 5: `Orcamento.filial`

**Files:**
- Modify: `orcamento/models.py`, `orcamento/visibilidade.py`
- Create: `orcamento/migrations/0004_orcamento_filial.py` (gerada), `orcamento/migrations/0005_o_orcamento_vai_para_a_matriz.py`
- Test: `tests/test_migracao_matriz_e_filial_do_orcamento.py`, e acrescentar um teste em `tests/test_orcamento.py`

**Interfaces:**
- Consumes: `Filial.e_matriz` (Task 4)
- Produces: `orcamento.models.Orcamento.filial` — FK `plataforma.Filial`, anulável neste plano, `related_name="orcamentos"`; `carrinho_de` grava a Matriz da empresa

- [ ] **Step 1: Write the failing tests**

Em `tests/test_orcamento.py`, dentro da classe `TestOCarrinhoDoContexto` (ela já tem o `_pedido` e usa a fixture `cenario`), acrescente:

```python
    def test_o_carrinho_novo_nasce_na_matriz(self, cenario):
        """Sem filial, o alcance "a filial" do plano 2 não teria o que filtrar.

        Na MATRIZ da empresa, e não na filial do cabeçalho: `filial_atual` ainda
        lê `Filial.usuarios`, que não sabe de empresa, e poderia devolver uma
        filial de outra. O plano 2 troca para o lugar da requisição.
        """
        cenario["orcamento"].fechar()
        novo = carrinho_de(self._pedido(cenario["ana"], cenario["alfa"]))
        assert novo.filial is not None
        assert novo.filial.e_matriz is True
        assert novo.filial.empresa_id == cenario["alfa"].pk
```

O `fechar()` é o mesmo de `test_cria_quando_nao_ha_nenhum`, logo acima: sem ele, `carrinho_de` devolve o orçamento que a fixture criou direto no banco, e esse não passou pela função.

Create `tests/test_migracao_matriz_e_filial_do_orcamento.py`:

```python
"""As duas migrações de dados deste plano, num banco antigo de verdade.

`plataforma.0006` dá a Matriz a quem não tem; `orcamento.0005` põe cada
orçamento que já existe na Matriz da empresa dele. Testadas com o `Migrator`,
como `test_migracao_uma_conta_uma_empresa.py`, e com a mesma trava de só tocar
banco de teste.
"""

import pytest
from django_test_migrations.migrator import Migrator

TITULAR = 1


@pytest.fixture
def migrador(django_db_setup, django_db_blocker):
    """Ver o docstring da fixture de mesmo nome em
    `tests/test_migracao_uma_conta_uma_empresa.py`: o `Migrator` REVERTE o
    esquema e não desfaz se o teste morrer no meio."""
    from django.db import connection

    nome = connection.settings_dict["NAME"]
    assert nome.startswith("test_"), (
        f"o Migrator ia mexer em {nome!r}, que não é banco de teste")
    with django_db_blocker.unblock():
        yield Migrator()


def _antes(migrador):
    return migrador.apply_initial_migration(
        [("plataforma", "0005_filial_e_matriz"),
         ("orcamento", "0003_alter_itemdoorcamento_conta_alter_orcamento_conta"),
         ("contas", "0014_alocacao")])


def test_empresa_sem_filial_ganha_a_matriz(migrador):
    velho = _antes(migrador)
    Empresa = velho.apps.get_model("plataforma", "Empresa")
    alfa = Empresa.objects.create(razao_social="Alfa Ltda")

    novo = migrador.apply_tested_migration(
        ("plataforma", "0006_toda_empresa_tem_matriz"))
    Filial = novo.apps.get_model("plataforma", "Filial")
    assert Filial.objects.get(empresa_id=alfa.pk, e_matriz=True).nome == \
        "Matriz"


def test_a_filial_chamada_matriz_vira_a_matriz(migrador):
    velho = _antes(migrador)
    Empresa = velho.apps.get_model("plataforma", "Empresa")
    Filial = velho.apps.get_model("plataforma", "Filial")
    alfa = Empresa.objects.create(razao_social="Alfa Ltda")
    Filial.objects.create(empresa=alfa, nome="Loja 1", apelido="L1", ordem=0)
    antiga = Filial.objects.create(empresa=alfa, nome=" matriz ",
                                   apelido="M", ordem=9)

    novo = migrador.apply_tested_migration(
        ("plataforma", "0006_toda_empresa_tem_matriz"))
    Filial = novo.apps.get_model("plataforma", "Filial")
    assert Filial.objects.get(empresa_id=alfa.pk, e_matriz=True).pk == antiga.pk


def test_sem_matriz_pelo_nome_a_primeira_do_seletor_vira(migrador):
    velho = _antes(migrador)
    Empresa = velho.apps.get_model("plataforma", "Empresa")
    Filial = velho.apps.get_model("plataforma", "Filial")
    alfa = Empresa.objects.create(razao_social="Alfa Ltda")
    Filial.objects.create(empresa=alfa, nome="Norte", apelido="N", ordem=5)
    primeira = Filial.objects.create(empresa=alfa, nome="Sul", apelido="S",
                                     ordem=1)

    novo = migrador.apply_tested_migration(
        ("plataforma", "0006_toda_empresa_tem_matriz"))
    Filial = novo.apps.get_model("plataforma", "Filial")
    assert Filial.objects.get(empresa_id=alfa.pk, e_matriz=True).pk == \
        primeira.pk


def test_o_orcamento_existente_vai_para_a_matriz(migrador):
    velho = _antes(migrador)
    Usuario = velho.apps.get_model("contas", "Usuario")
    Empresa = velho.apps.get_model("plataforma", "Empresa")
    Orcamento = velho.apps.get_model("orcamento", "Orcamento")
    dono = Usuario.objects.create(email="dono-mig@x.com", password="x",
                                  nivel=TITULAR)
    alfa = Empresa.objects.create(razao_social="Alfa Ltda", dono=dono,
                                  conta_id=dono.guid)
    comprador = Usuario.objects.create(email="comp-mig@x.com", password="x",
                                       nivel=3, dono=dono)
    orcamento = Orcamento.objects.create(empresa=alfa, conta_id=dono.guid,
                                         comprador=comprador, numero=1)

    novo = migrador.apply_tested_migration(
        [("plataforma", "0006_toda_empresa_tem_matriz"),
         ("orcamento", "0005_o_orcamento_vai_para_a_matriz")])
    Orcamento = novo.apps.get_model("orcamento", "Orcamento")
    migrado = Orcamento.objects.select_related("filial").get(pk=orcamento.pk)
    assert migrado.filial.e_matriz is True
    assert migrado.filial.empresa_id == alfa.pk
```

**Atenção ao `numero`:** o model histórico de `Orcamento` não roda o `save` de verdade, e `numero` é `editable=False`. Se `Orcamento.objects.create` recusar ou exigir outros campos obrigatórios, leia `orcamento/migrations/0001_initial.py` e passe o que ela declara como obrigatório. Não mude a migração para caber no teste.

- [ ] **Step 2: Run tests to verify they fail**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_migracao_matriz_e_filial_do_orcamento.py "tests/test_orcamento.py::TestOCarrinhoDoContexto"`

Expected: FAIL — `orcamento.0004` e `0005` não existem, e `Orcamento` não tem `filial`.

- [ ] **Step 3: O campo**

Em `orcamento/models.py`, na classe `Orcamento`, logo depois de `comprador`:

```python
    #: Em que filial o orçamento aconteceu (spec 2026-09-14). Sem ela, o alcance
    #: "a filial" de um cargo não teria o que filtrar.
    #:
    #: **Anulável neste plano, de propósito.** Os orçamentos que já existem vão
    #: para a Matriz numa migração de dados, e a coluna vira obrigatória no
    #: plano 2, junto com a virada — torná-la obrigatória agora exigiria que toda
    #: criação de orçamento soubesse de filial antes de existir o lugar da
    #: requisição.
    #:
    #: `PROTECT`: filial com orçamento não se apaga, e o histórico de venda não
    #: some junto com a loja.
    filial = models.ForeignKey(
        "plataforma.Filial", verbose_name="filial", null=True, blank=True,
        on_delete=models.PROTECT, related_name="orcamentos")
```

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py makemigrations orcamento -n orcamento_filial`

- [ ] **Step 4: A migração de dados**

Create `orcamento/migrations/0005_o_orcamento_vai_para_a_matriz.py`:

```python
"""Cada orçamento que já existe vai para a Matriz da empresa dele.

Depende de `plataforma.0006`, que garante que toda empresa tem Matriz. Se mesmo
assim a empresa de um orçamento estiver sem ela, a migração PARA e lista os ids:
um orçamento sem filial sobreviveria até o plano 2 tornar a coluna obrigatória, e
aí a falha seria mais longe de onde nasceu.

`desfazer` esvazia a coluna: nenhuma informação anterior se perde, porque antes
dela não havia filial nenhuma.
"""

from django.db import migrations


def _para_a_matriz(apps, schema_editor):
    Orcamento = apps.get_model("orcamento", "Orcamento")
    Filial = apps.get_model("plataforma", "Filial")

    matriz_de = dict(Filial.objects.filter(e_matriz=True)
                     .values_list("empresa_id", "pk"))
    sem = set()
    for empresa_id in (Orcamento.objects.filter(filial__isnull=True)
                       .values_list("empresa_id", flat=True).distinct()):
        matriz = matriz_de.get(empresa_id)
        if matriz is None:
            sem.add(empresa_id)
            continue
        Orcamento.objects.filter(empresa_id=empresa_id,
                                 filial__isnull=True).update(filial_id=matriz)
    if sem:
        raise RuntimeError(
            "Orçamentos de empresas sem Matriz; empresas: "
            f"{sorted(sem)[:10]}. Rode plataforma.0006 antes.")


def _esvaziar(apps, schema_editor):
    apps.get_model("orcamento", "Orcamento").objects.update(filial=None)


class Migration(migrations.Migration):

    dependencies = [
        ("orcamento", "0004_orcamento_filial"),
        ("plataforma", "0006_toda_empresa_tem_matriz"),
    ]

    operations = [
        migrations.RunPython(_para_a_matriz, _esvaziar),
    ]
```

- [ ] **Step 5: O carrinho novo nasce na Matriz**

Em `orcamento/visibilidade.py`, em `carrinho_de`, troque o `return Orcamento.irrestritos.create(...)` do fim por:

```python
    # Na MATRIZ, e não na filial do cabeçalho, neste momento: `filial_atual`
    # ainda lê `Filial.usuarios`, que não sabe de empresa, e poderia devolver
    # filial de outra empresa. O plano 2 troca pelo lugar da requisição.
    matriz = empresa.filiais.filter(e_matriz=True).first()
    return Orcamento.irrestritos.create(
        empresa=empresa, comprador_id=pessoa.pk, filial=matriz)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings tests/test_migracao_matriz_e_filial_do_orcamento.py tests/test_orcamento.py`

Expected: tudo verde.

- [ ] **Step 7: Suíte inteira com o ciclo real de backup**

Com o `pg_dump` via docker no `PATH` (ver Global Constraints), rode a suíte inteira.

Expected: tudo verde e **nenhum teste pulado**. As migrações novas passam pelo ciclo backup → destrói → restaura, e é esse ciclo que pega uma migração que só funciona em banco vazio.

- [ ] **Step 8: Conferir no banco local**

```bash
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py migrate 2>&1 | tail -3
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py shell -c "
from orcamento.models import Orcamento
print('orçamentos sem filial:', Orcamento.irrestritos.filter(filial__isnull=True).count())"
```

Expected: `orçamentos sem filial: 0`.

- [ ] **Step 9: Contagem e commit**

```bash
N=$(ls tests/test_*.py | wc -l) && sed -i -E "s/\b[0-9]{2,3} arquivos\b/$N arquivos/g" CLAUDE.md
git add orcamento tests CLAUDE.md
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat(orcamento): o orçamento sabe em que filial aconteceu

Sem filial, o alcance 'a filial' de um cargo não teria o que filtrar. O orçamento
novo nasce na Matriz da empresa, e os que já existem vão para ela numa migração de
dados que para com erro se alguma empresa estiver sem Matriz — um orçamento sem
filial chegaria até o plano 2 e falharia longe de onde nasceu.

Matriz e não a filial do cabeçalho, por ora: filial_atual ainda lê
Filial.usuarios, que não sabe de empresa, e poderia devolver a filial de outra. A
coluna fica anulável até o plano 2, que troca pelo lugar da requisição e a torna
obrigatória."
```

---

## Ao fim deste plano

- Tabelas novas: `Cargo`, `Alocacao`. Coluna nova: `Filial.e_matriz`, `Orcamento.filial`.
- Semeaduras: os cinco cargos de toda conta; a Matriz de toda empresa.
- **Nenhum comportamento de acesso mudou.** `permissoes_de`, `do_contexto`, `empresa_atual`, `filial_atual`, `Perfil` e `Papel` estão como estavam.

O plano 2 (a virada) é escrito a partir daqui, lendo o código que este plano deixou, e começa pelo que o spec chama de "Onde a pessoa está, e o que ela pode ali".

## Pendências deixadas pela execução (14/09/2026)

Registradas na revisão final e nas revisões por tarefa; nenhuma bloqueia o
merge, e cada uma diz em que plano deve ser olhada.

- **Plano 2** — `Orcamento.filial` vira obrigatória: declarar no docstring da
  migração a invariante de que toda empresa tem Matriz (post_save + `0006`).
- **Plano 2** — `catalogo/migrations/0005` semeia ficha para empresa sem titular,
  e `catalogo/0011` recusa isso depois. Só aparece ao reconstruir o histórico
  sobre uma empresa órfã (é o que impede `reset()` em
  `tests/test_migracao_uma_conta_uma_empresa.py`). Um teste transacional futuro
  que faça login e rode depois desse arquivo pode encontrar o banco de teste sem
  `django_session`.
- **Plano 3** — `plataforma/filiais.py::pode_desativar` conta filiais ativas da
  instalação inteira, não da empresa; com uma Matriz por empresa, a recusa de
  "última filial ativa" quase nunca dispara.
- **Plano 3** — com Matriz em toda empresa, `filiais_de(superusuário)` e
  `exigir_filial` passam a achar filial para a MW5 onde antes podiam não achar.
- **Plano 3** — `Filial.save` usa `full_clean(validate_constraints=False)`: a
  tela de filiais não pode deixar marcar `e_matriz`, ou a segunda Matriz vira
  `IntegrityError` (500) em vez de frase.
- **Qualquer** — `0006` com duas filiais ATIVAS chamadas "Matriz" na mesma
  empresa escolhe pela ordem da consulta; o chave de `DE_FABRICA` digitada errado
  casaria zero permissões em silêncio; `Alocacao.save` com `empresa_id`
  inexistente levanta `DoesNotExist` e não `ValidationError`.
