# Várias empresas por conta — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a conta do cliente passa a ter várias empresas (conta → empresas → lojas), com o seletor de empresa no cabeçalho, o cadastro de empresa pela MW5 e o painel do titular podendo somar as empresas.

**Architecture:** cai a trava `uma_empresa_por_conta`; a **empresa** continua sendo a fronteira de toda consulta de negócio (`objects.da_empresa`), e o `conta_guid` continua obrigatório e derivado em toda tabela. O contexto do cabeçalho passa a valer para quem é de uma conta, e a marca segue a empresa escolhida.

**Tech Stack:** Django 5.2, Postgres, Jinja2, pytest (`KRONOS_BANCO` obrigatório).

**Spec:** `docs/superpowers/specs/2026-09-17-varias-empresas-por-conta-design.md`

## Global Constraints

- **O `conta_guid` não muda**: obrigatório em toda tabela de negócio, derivado da empresa no `save` (`contas/inquilino.py`, `plataforma/models.py::_conta_da_empresa`), nunca escrito à mão. `tests/test_toda_linha_da_conta_leva_o_guid.py` e `tests/test_regra_do_inquilino.py` continuam valendo sem isenção nova.
- **A fronteira do dado é a empresa**: toda consulta de negócio por `objects.da_empresa(...)` ou `do_contexto(request)`. `da_conta(...)` soma as empresas da conta, e isso passa a estar escrito.
- Rótulo do seletor: **"Empresa"** para quem é de uma conta; **"Conta"** para a MW5.
- Quem cria empresa é a **MW5**. O titular vê as empresas da conta dele.
- Frases novas em português no código e em castelhano no `django.po` (`.venv/bin/pybabel compile -d locale -D django`). Dado cadastrado não se traduz.
- Comentário diz POR QUÊ, em português. Commits longos em português, autor `João Victor Vancim <developer1@kronos.net.br>`, sem coautor.
- Testes: `export KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5436/kronos DJANGO_DEBUG=1` e `.venv/bin/python -m pytest -q -p no:warnings <arquivos>`.
- Teste com dente: depois de verde, quebre o código de propósito, veja vermelho, desfaça.
- Trabalhe na branch `varias-empresas`; cada task é um commit.

---

## Entrega 1 — a base

### Task 1: O `conftest` deixa de descartar a segunda empresa

**Files:**
- Modify: `tests/conftest.py:171-192` (`dar_acesso`)
- Test: `tests/test_conftest_ajuda.py` (criar)

**Interfaces:**
- Produces: `dar_acesso(pessoa, empresas=[a, b], ...)` cria alocação em TODAS as empresas passadas; `por_na_conta(pessoa, empresa)` inalterado.

- [ ] **Step 1: Write the failing test** (`tests/test_conftest_ajuda.py`)

```python
"""O que os ajudantes da suíte prometem. Um ajudante que descarta metade do
cenário em silêncio faz todo teste que depende dele passar sem provar nada —
foi o que `dar_acesso` fazia com a segunda empresa até 17/09/2026."""

import pytest

from tests.conftest import dar_acesso, empresa_do_teste

pytestmark = pytest.mark.django_db


def test_dar_acesso_aloca_em_todas_as_empresas_pedidas():
    from contas.models import Nivel, Usuario
    from plataforma.models import Empresa

    alfa = empresa_do_teste()
    titular = Usuario.objects.get(pk=alfa.dono_id) if alfa.dono_id else None
    assert titular is not None, "a empresa do teste precisa de titular"
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=titular)
    pessoa = Usuario.objects.create_user(email="dois-lugares@teste.com",
                                         password="x", nivel=Nivel.MEMBRO)
    dar_acesso(pessoa, empresas=[alfa, beta], nivel=Nivel.MEMBRO)
    assert set(pessoa.alocacoes.values_list("empresa_id", flat=True)) == {alfa.pk, beta.pk}
```

(O teste depende da trava já removida; ele fica vermelho até a Task 2. Rode-o junto com ela.)

- [ ] **Step 2: Implement** (`tests/conftest.py`, em `dar_acesso`)

Troque o bloco `if empresas is not None: alvo = list(empresas)[:1]` por:

```python
    # **Todas as empresas pedidas** (17/09/2026): a conta passou a ter várias,
    # e cortar em `[:1]` fazia um teste de duas empresas passar provando uma.
    alvo = list(empresas) if empresas is not None else [empresa_do_teste()]
```

e o `alocar` do fim por:

```python
    if pedido == Nivel.MEMBRO:
        for empresa in alvo:
            alocar(pessoa, empresa, "cliente")
```

`por_na_conta(pessoa, alvo[0] if alvo else None)` continua: a conta é uma só.

- [ ] **Step 3: Commit** (junto com a Task 2, porque o teste depende dela)

---

### Task 2: Cai a trava, e duas empresas não se misturam

**Files:**
- Modify: `plataforma/models.py:382-437` (comentário, `related_name`, trava)
- Create: `plataforma/migrations/0002_varias_empresas_por_conta.py` (gerada)
- Modify: `tests/test_acesso_alcance.py` (o teste da trava)
- Test: `tests/test_varias_empresas.py` (criar)

**Interfaces:**
- Consumes: `dar_acesso` da Task 1.
- Produces: `Empresa.dono` sem UNIQUE; `titular.empresas_da_conta` (era `empresa_da_conta`).

- [ ] **Step 1: Write the failing tests** (`tests/test_varias_empresas.py`)

```python
"""Duas empresas na mesma conta (spec 2026-09-17).

O que se prova aqui é o ISOLAMENTO: a fronteira do dado de negócio é a
empresa, e o `conta_guid` continua obrigatório e igual nas duas.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from tests.conftest import abrir_conta, alocar, email_de

pytestmark = pytest.mark.django_db

SENHA = "segredo-de-teste"


@pytest.fixture
def duas_empresas():
    from types import SimpleNamespace

    from contas.models import Usuario
    from plataforma.models import Empresa, Filial

    from tests.conftest import empresa_do_teste

    alfa = empresa_do_teste()
    titular = (Usuario.objects.get(pk=alfa.dono_id) if alfa.dono_id
               else abrir_conta(alfa, "sylvia", SENHA))
    alfa.refresh_from_db()
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=titular)
    return SimpleNamespace(
        titular=titular, alfa=alfa, beta=beta,
        loja_alfa=Filial.objects.filter(empresa=alfa, e_matriz=True).first(),
        loja_beta=Filial.objects.filter(empresa=beta, e_matriz=True).first())


def test_a_conta_tem_duas_empresas_e_cada_uma_nasce_com_a_matriz(duas_empresas):
    d = duas_empresas
    assert list(d.titular.empresas_da_conta.order_by("pk")) == [d.alfa, d.beta]
    assert d.loja_alfa is not None and d.loja_beta is not None
    assert d.loja_alfa.empresa_id == d.alfa.pk and d.loja_beta.empresa_id == d.beta.pk


def test_as_duas_empresas_levam_o_mesmo_conta_guid(duas_empresas):
    d = duas_empresas
    assert d.alfa.conta_id == d.titular.guid == d.beta.conta_id
    assert d.loja_beta.conta_id == d.titular.guid


def test_o_dado_de_negocio_de_uma_empresa_nao_aparece_na_outra(duas_empresas):
    from fila.models import GrupoDeItem

    d = duas_empresas
    so_de_alfa = GrupoDeItem.irrestritos.create(empresa=d.alfa, nome="Sofás")
    so_de_beta = GrupoDeItem.irrestritos.create(empresa=d.beta, nome="Tapetes")
    assert list(GrupoDeItem.objects.da_empresa(d.alfa)) == [so_de_alfa]
    assert list(GrupoDeItem.objects.da_empresa(d.beta)) == [so_de_beta]
    # `da_conta` soma as duas, e isso é escolha (spec E2).
    assert set(GrupoDeItem.objects.da_conta(d.titular.guid)) == {so_de_alfa, so_de_beta}
    assert so_de_beta.conta_id == d.titular.guid


def test_uma_pessoa_alocada_nas_duas_alcanca_as_duas(duas_empresas):
    from contas.lugar import empresas_da_pessoa, filiais_da_pessoa
    from contas.models import Nivel, Usuario

    d = duas_empresas
    ana = Usuario.objects.create_user(email=email_de("ana-duas"), password=SENHA,
                                      nivel=Nivel.MEMBRO, dono=d.titular)
    alocar(ana, d.alfa, "vendedor", filial=d.loja_alfa)
    alocar(ana, d.beta, "vendedor", filial=d.loja_beta)
    assert set(empresas_da_pessoa(ana)) == {d.alfa, d.beta}
    assert list(filiais_da_pessoa(ana, d.beta)) == [d.loja_beta]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_varias_empresas.py`
Expected: FAIL com `IntegrityError: Esta conta já tem uma empresa.`

- [ ] **Step 3: Remove the constraint** (`plataforma/models.py`)

No campo `dono` (`:382-398`), troque o comentário "Uma conta, uma empresa" por:

```python
    #: **O Admin dono desta empresa — a CONTA.** Uma conta tem VÁRIAS empresas
    #: desde 17/09/2026 (spec `2026-09-17-varias-empresas-por-conta`): o que
    #: separa o dado de negócio é a coluna `empresa`, e o `conta_guid` diz de
    #: quem é a linha.
```

e `related_name="empresa_da_conta"` por `related_name="empresas_da_conta"`.

Em `Meta.constraints`, apague o `UniqueConstraint` `uma_empresa_por_conta` inteiro (`:433-437`), deixando o de CNPJ.

- [ ] **Step 4: Fix the callers of the old `related_name`**

Run: `grep -rn "empresa_da_conta" --include=*.py . | grep -v .venv`
Troque cada um por `empresas_da_conta` (há ao menos `contas/views_usuarios.py:1482`, cuja frase vira "é a conta de %(n)s empresa(s)" com `ngettext`).

- [ ] **Step 5: Generate the migration**

Run: `.venv/bin/python manage.py makemigrations plataforma -n varias_empresas_por_conta`
Expected: `RemoveConstraint(model_name="empresa", name="uma_empresa_por_conta")` e a alteração do campo.

- [ ] **Step 6: Flip the test that asserted the constraint** (`tests/test_acesso_alcance.py:106-120`)

Troque `test_o_banco_recusa_a_segunda_empresa_da_mesma_conta` por:

```python
    def test_o_banco_aceita_a_segunda_empresa_da_mesma_conta(self):
        """17/09/2026: a trava `uma_empresa_por_conta` caiu. A conta é o
        cliente, e ele pode ter mais de uma pessoa jurídica."""
        titular = Usuario.objects.create_user(
            email="dono-duas@teste.com", password="x", nivel=Nivel.TITULAR)
        uma = Empresa.objects.create(razao_social="Uma Ltda", dono=titular)
        outra = Empresa.objects.create(razao_social="Outra Ltda", dono=titular)
        assert {e.pk for e in Empresa.objects.filter(dono=titular)} == {uma.pk, outra.pk}
```

(Confira o nome exato da classe e dos ajudantes do arquivo antes de escrever.)

- [ ] **Step 7: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_varias_empresas.py tests/test_conftest_ajuda.py tests/test_acesso_alcance.py tests/test_regra_do_inquilino.py tests/test_toda_linha_da_conta_leva_o_guid.py`
Expected: PASS. Dente: volte o `UniqueConstraint` e veja `tests/test_varias_empresas.py` vermelho; desfaça.

- [ ] **Step 8: Commit**

```bash
git add plataforma/models.py plataforma/migrations/0002_varias_empresas_por_conta.py tests/ contas/views_usuarios.py
git commit -m "feat: a conta passa a ter várias empresas"
```
(mensagem longa: o que a trava impedia, por que a fronteira continua sendo a empresa, e o conta_guid intacto.)

---

### Task 3: O cabeçalho oferece a empresa para quem é de uma conta

**Files:**
- Modify: `plataforma/contexto.py:66-115` (`empresa_atual`/`_decidir`), `:241-285` (`niveis_de_contexto`)
- Modify: `plataforma/site.py:62-68` (o comentário "só a MW5")
- Test: `tests/test_cabecalho_contexto.py`, `tests/test_contexto_filial.py`

**Interfaces:**
- Consumes: Task 2.
- Produces: `niveis_de_contexto` devolve o nível 0 para qualquer pessoa que alcance mais de uma empresa, com `rotulo` `"Conta"` para a MW5 e `"Empresa"` para os demais.

- [ ] **Step 1: Write the failing tests** (fim de `tests/test_cabecalho_contexto.py`)

```python
class TestOTitularComDuasEmpresas:
    """17/09/2026: o seletor de empresa deixou de ser só da MW5. O molde é o
    de `TestOSeletorDeFilial`, que já monta titular, empresa e filiais."""

    def _conta_com_duas(self):
        from contas.models import Nivel
        from plataforma.models import Empresa

        titular = Usuario.objects.create_user(
            email="dono-duas-cab@teste.com", password=SENHA, nivel=Nivel.TITULAR)
        alfa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
        beta = Empresa.objects.create(razao_social="Beta Ltda", dono=titular)
        return titular, alfa, beta

    def _logado(self, email=" dono-duas-cab@teste.com"):
        c = Client()
        c.post(reverse("entrar"), {"usuario": email.strip(), "senha": SENHA})
        return c

    def test_o_titular_ve_o_seletor_e_o_rotulo_diz_empresa(self, db):
        self._conta_com_duas()
        html = self._logado().get(reverse("home")).content.decode()
        assert ">Empresa</label>" in html
        assert "<select" in html and 'name="empresa_id"' in html
        assert "Alfa Ltda" in html and "Beta Ltda" in html

    def test_para_a_mw5_o_rotulo_continua_conta(self, db):
        from contas.models import Nivel
        from plataforma.models import Empresa

        Empresa.objects.create(razao_social="Alfa Ltda")
        Empresa.objects.create(razao_social="Beta Ltda")
        mw5 = Usuario.objects.create_user(email="mw5-cab@teste.com", password=SENHA)
        mw5.nivel = Nivel.MASTER
        mw5.save(update_fields=["nivel"])
        c = Client()
        c.post(reverse("entrar"), {"usuario": "mw5-cab@teste.com", "senha": SENHA})
        html = c.get(reverse("home")).content.decode()
        assert ">Conta</label>" in html and ">Empresa</label>" not in html

    def test_a_empresa_escolhida_na_sessao_vale_para_o_titular(self, db):
        from plataforma.contexto import CHAVE_EMPRESA

        _t, _alfa, beta = self._conta_com_duas()
        cliente = self._logado()
        sessao = cliente.session
        sessao[CHAVE_EMPRESA] = beta.pk
        sessao.save()
        html = cliente.get(reverse("home")).content.decode()
        assert f'value="{beta.pk}" selected' in html

    def test_id_de_empresa_que_ele_nao_alcanca_e_descartado(self, db):
        from plataforma.contexto import CHAVE_EMPRESA
        from plataforma.models import Empresa

        _t, alfa, beta = self._conta_com_duas()
        alheia = Empresa.objects.create(razao_social="De Outro Cliente Ltda")
        cliente = self._logado()
        sessao = cliente.session
        sessao[CHAVE_EMPRESA] = alheia.pk
        sessao.save()
        html = cliente.get(reverse("home")).content.decode()
        assert "De Outro Cliente Ltda" not in html
        assert f'value="{alfa.pk}" selected' in html or f'value="{beta.pk}" selected' in html
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_cabecalho_contexto.py -k DuasEmpresas`
Expected: FAIL (rótulo "Conta" e/ou nível ausente)

- [ ] **Step 3: Implement** (`plataforma/contexto.py`)

Em `empresa_atual`, troque o parágrafo "A sessão sobrevive para a MW5, e só" por:

```python
    A sessão vale para quem alcança MAIS DE UMA empresa — a MW5, e desde
    17/09/2026 também o titular com várias empresas na conta. Quem alcança
    uma só não passa pela sessão: o valor não vem do pedido, e id forjado
    deixa de ser caminho.
```

`_decidir` não muda: o `if permitidas.count() == 1` já faz isso.

Em `niveis_de_contexto`, troque o bloco do nível 0 por:

```python
    empresas = list(empresas_de(user))
    if len(empresas) > 1:
        # Para a MW5 a pergunta é "qual cliente estou olhando"; para quem é de
        # uma conta com várias empresas, "em qual das minhas estou".
        da_mw5 = getattr(user, "is_superuser", False)
        niveis.append(NivelDeContexto(
            nivel=0,
            rotulo=_("Conta") if da_mw5 else _("Empresa"),
            atual=str(atual.pk) if atual else "",
            opcoes=[OpcaoDeContexto(str(e.pk), str(e)) for e in empresas],
        ))
```

(Confira como `identidade_da_sessao` marca a MW5 neste projeto — se o retrato não tiver `is_superuser`, use `contas.alcance._ve_tudo` ou o equivalente que `empresas_de` usa.)

Em `plataforma/site.py:62-68`, atualize o comentário: o seletor volta a existir para quem tem várias empresas.

- [ ] **Step 4: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_cabecalho_contexto.py tests/test_contexto_filial.py tests/test_varias_empresas.py`
Expected: PASS. Os testes antigos que afirmam "conta com uma empresa não tem o que trocar" continuam valendo (a pessoa alcança uma só).

- [ ] **Step 5: Commit**

```bash
git add plataforma/contexto.py plataforma/site.py tests/test_cabecalho_contexto.py
git commit -m "feat: o seletor de empresa no cabeçalho para quem tem várias"
```

---

### Task 4: A marca segue a empresa do cabeçalho

**Files:**
- Modify: `plataforma/marca.py:240-252` (`empresa_da_marca`)
- Modify: `contas/alcance.py:71-86` (aviso em `empresa_de`)
- Test: `tests/test_marca_da_empresa.py` (ou o arquivo de marca que existir — confira com `ls tests | grep marca`)

**Interfaces:**
- Produces: `empresa_da_marca(request)` = `plataforma.contexto.empresa_atual(request)`.

- [ ] **Step 1: Write the failing test**

Em `tests/test_marca_da_empresa.py`, que já tem `_pedido(pessoa)` (request com
sessão crua), a fixture `alfa` e `_menu(marca)`:

```python
class TestComDuasEmpresasNaConta:
    """17/09/2026: a marca vinha de "a primeira empresa que a pessoa
    alcança"; com duas na conta, o menu podia ficar com o da outra."""

    def test_a_marca_segue_a_empresa_escolhida_no_cabecalho(self, alfa):
        from plataforma.contexto import CHAVE_EMPRESA

        empresa, titular = alfa
        beta = Empresa.objects.create(razao_social="Beta", dono=titular)
        AparenciaDaEmpresa.objects.create(
            empresa=beta, sidebar_bg="#445566", sidebar_text="#ffffff")

        pedido = _pedido(titular)
        pedido.session[CHAVE_EMPRESA] = beta.pk
        assert _menu(marca_da_requisicao(pedido)) == "#445566"

        na_alfa = _pedido(titular)
        na_alfa.session[CHAVE_EMPRESA] = empresa.pk
        assert _menu(marca_da_requisicao(na_alfa)) == "#112233"
```

- [ ] **Step 2: Run to verify it fails**

- [ ] **Step 3: Implement** (`plataforma/marca.py`)

```python
def empresa_da_marca(request):
    """A empresa cujo menu veste esta requisição: a ESCOLHIDA no cabeçalho
    (17/09/2026), e não "a primeira que a pessoa alcança" — com duas empresas
    na conta, a primeira podia não ser a que ela está olhando.

    `empresa_atual` já respeita o "ver como": ela lê a identidade da sessão, e
    em personificação essa identidade é a do cliente. A MW5 sem empresa
    escolhida continua vendo a instalação.
    """
    from .contexto import empresa_atual

    return empresa_atual(request)
```

Em `contas/alcance.py::empresa_de`, acrescente ao docstring:

```python
    **É a PRIMEIRA que a pessoa alcança, e não "a empresa dela"**: desde
    17/09/2026 a conta pode ter várias. Em requisição, use
    `plataforma.contexto.empresa_atual`.
```

- [ ] **Step 4: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/ -k "marca or aparencia or tema"`
Expected: PASS

- [ ] **Step 5: Commit**

---

### Task 5: `da_conta` e os clientes, ditos em voz alta

**Files:**
- Modify: `contas/inquilino.py:53-57` (docstring de `da_conta`)
- Modify: `contas/lugar.py:269-315` (docstrings de `clientes_alcancados` e `tem_cargo_de_cliente`)
- Test: `tests/test_varias_empresas.py`

- [ ] **Step 1: Write the failing test**

```python
def test_o_cliente_de_uma_empresa_nao_aparece_na_irma(duas_empresas, rf):
    """`clientes_alcancados` filtra as alocações pela empresa; este teste
    existe para isso não mudar sem alguém ver."""
    from contas.lugar import clientes_alcancados
    from contas.models import Nivel, Usuario
    from plataforma.contexto import CHAVE_EMPRESA

    d = duas_empresas
    de_alfa = Usuario.objects.create_user(email=email_de("cli-alfa"), password=SENHA,
                                          nivel=Nivel.MEMBRO, dono=d.titular)
    de_beta = Usuario.objects.create_user(email=email_de("cli-beta"), password=SENHA,
                                          nivel=Nivel.MEMBRO, dono=d.titular)
    alocar(de_alfa, d.alfa, "cliente")
    alocar(de_beta, d.beta, "cliente")

    pedido = rf.get("/")
    pedido.session = {CHAVE_EMPRESA: d.alfa.pk}
    pedido.user = pedido.usuario = d.titular
    assert list(clientes_alcancados(pedido)) == [de_alfa]
```

(`clientes_alcancados` lê a pessoa e o lugar por `_pessoa_e_lugar(request)`;
confira no código como montar o `request` de teste — se ele passar por
`comum.sessao.identidade_da_sessao`, use o cliente logado em vez do `rf`.)

- [ ] **Step 2: Run to verify it fails** (ele vai passar se a regra já estiver certa; nesse caso, quebre `clientes_alcancados` de propósito para vê-lo vermelho, e desfaça — é a prova de dente deste teste.)

- [ ] **Step 3: Write the docstrings**

`contas/inquilino.py::da_conta`:

```python
        """Todas as linhas da CONTA — de TODAS as empresas dela.

        Desde 17/09/2026 a conta pode ter várias empresas, e isto soma as
        duas de propósito: é a visão do titular. Quem quer uma empresa usa
        `da_empresa`, que é a porta de toda tela.
        """
```

`contas/lugar.py::tem_cargo_de_cliente`: acrescente "com várias empresas na conta, 'algum lugar' inclui todas elas — é a pergunta feita fora de requisição, onde não há empresa atual".

- [ ] **Step 4: Run + commit**

---

### Task 6: A suíte para de afirmar "uma conta, uma empresa"

**Files:**
- Modify: `tests/test_conta_nasce_com_empresa.py`, `tests/test_tela_empresa.py`, `tests/test_menu.py`, `tests/test_tela_aparencia.py`, `tests/test_usuarios_ajustes_de_15_09.py`, `tests/test_instalacao_nasce_sem_empresa.py`
- Modify: `CLAUDE.md` (§7 e §9) — só depois que a suíte estiver verde

- [ ] **Step 1: Find every one of them**

Run: `grep -rln "uma conta, uma empresa\|uma empresa por conta\|uma conta tem uma empresa" tests/ CLAUDE.md`

- [ ] **Step 2: For each test, decide and edit**

Regra: o teste que afirma a TRAVA muda de lado; o que descreve "quem alcança uma empresa não vê seletor" continua valendo (monte o cenário com uma empresa). Ajuste o texto dos docstrings para não mentir.

- [ ] **Step 3: Run the whole suite**

Run: `timeout 590 .venv/bin/python -m pytest -q -p no:warnings`
Expected: tudo verde. **Se algo falhar, pare e investigue** — é aqui que o efeito colateral aparece.

- [ ] **Step 4: Commit**

---

## Entrega 2 — as telas

### Task 7: Empresas — a MW5 cria, o titular vê as dele

**Files:**
- Modify: `plataforma/views_empresa.py:499-531` (título e frase), `:822` (`ACOES_SEM_ALVO`), `:633-680` (o formulário e `criar_do_post`)
- Test: `tests/test_tela_empresa.py`, `tests/test_conta_nasce_com_empresa.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestAMW5CriaEmpresa:
    """17/09/2026: com várias empresas por conta, "Nova empresa" volta — para
    a MW5, que é quem cadastra cliente."""

    def test_a_mw5_cria_e_a_empresa_nasce_com_a_matriz(self, cenario_da_mw5):
        from plataforma.models import Empresa, Filial

        resposta = cenario_da_mw5["cliente"].post(reverse("empresa"), {
            "acao": "criar", "razao_social": "Segunda Ltda",
            "dono": str(cenario_da_mw5["titular"].pk)})
        assert resposta.status_code in (200, 302)
        nova = Empresa.objects.get(razao_social="Segunda Ltda")
        assert nova.dono_id == cenario_da_mw5["titular"].pk
        assert nova.conta_id == cenario_da_mw5["titular"].guid
        assert Filial.objects.filter(empresa=nova, e_matriz=True).exists()

    def test_o_titular_continua_sem_criar(self, cenario_do_titular):
        from plataforma.models import Empresa

        cenario_do_titular["cliente"].post(reverse("empresa"), {
            "acao": "criar", "razao_social": "Nao Deve Existir Ltda"})
        assert not Empresa.objects.filter(razao_social="Nao Deve Existir Ltda").exists()

    def test_a_tabela_do_titular_mostra_as_duas_empresas(self, cenario_do_titular):
        from plataforma.models import Empresa

        Empresa.objects.create(razao_social="Beta Ltda",
                               dono=cenario_do_titular["titular"])
        html = cenario_do_titular["cliente"].get(reverse("empresa")).content.decode()
        assert "Alfa Ltda" in html and "Beta Ltda" in html
```

(Use as fixtures que `tests/test_tela_empresa.py` já tem para a MW5 e para o
titular; os nomes acima são os do molde — leia o topo do arquivo e reaproveite
os que existem, sem criar fixture repetida.)

- [ ] **Step 2: Run to verify they fail**

- [ ] **Step 3: Implement**

- `ACOES_SEM_ALVO = {"criar": _acao_criar}`, com `_acao_criar` recusando quem não é MW5 (`_e_master(request)`), lendo `campos_do_cadastro` e chamando `criar_do_post(request, dono=<titular escolhido>)`.
- O botão "Nova empresa" aparece só para a MW5.
- O título volta a ser "Empresas" também para o titular, e a frase de conta sem empresa continua.

- [ ] **Step 4: Run + commit**

---

### Task 8: Usuários mostra as empresas de cada pessoa

**Files:**
- Modify: `contas/views_usuarios.py:120-134` (`_com_empresa`), `:376` (dicionário por dono)
- Test: `tests/test_usuarios_ajustes_de_15_09.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a_coluna_mostra_as_duas_empresas_da_pessoa(db):
    """17/09/2026: a subconsulta trazia UMA empresa por pessoa, e com duas na
    conta a segunda sumia da tela."""
    from contas.models import Nivel, Usuario
    from plataforma.models import Empresa, Filial

    from tests.conftest import alocar

    titular = Usuario.objects.create_user(email="dono-col@teste.com",
                                          password=SENHA, nivel=Nivel.TITULAR)
    alfa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    beta = Empresa.objects.create(razao_social="Beta Ltda", dono=titular)
    ana = Usuario.objects.create_user(email="ana-col@teste.com", password=SENHA,
                                      nome="Ana", nivel=Nivel.MEMBRO, dono=titular)
    alocar(ana, alfa, "vendedor", filial=Filial.objects.get(empresa=alfa, e_matriz=True))
    alocar(ana, beta, "vendedor", filial=Filial.objects.get(empresa=beta, e_matriz=True))

    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": "dono-col@teste.com", "senha": SENHA})
    html = cliente.get(reverse("usuarios")).content.decode()
    linha = html[html.index("Ana"):]
    linha = linha[:linha.index("</tr>")]
    assert "Alfa Ltda" in linha and "Beta Ltda" in linha
```

- [ ] **Step 2: Run to verify it fails**

- [ ] **Step 3: Implement**

`_com_empresa` passa a anotar a lista de empresas das ALOCAÇÕES (e, para o titular, as empresas da conta dele), com `StringAgg` do Postgres:

```python
    from django.contrib.postgres.aggregates import StringAgg

    # `StringAgg`, e não subconsulta: a pessoa pode estar em várias empresas
    # desde 17/09/2026, e a subconsulta de antes trazia uma linha só.
    return pessoas.annotate(empresa_nome=StringAgg(
        Coalesce(NullIf("alocacoes__empresa__nome_fantasia", Value("")),
                 "alocacoes__empresa__razao_social"),
        delimiter=", ", distinct=True))
```

Para o titular (que não tem alocação), caia nas empresas da conta: `Coalesce(StringAgg(...), Subquery(<empresas da conta>))` ou uma segunda anotação — escolha e escreva o motivo.

O dicionário de `:376` passa a ser `{dono_id: [nomes]}` (`setdefault(...).append(...)`), e a tela junta com vírgula.

- [ ] **Step 4: Run + commit**

---

### Task 9: O módulo de Lojas nasce ligado

**Files:**
- Modify: `plataforma/modulo.py:93-101` (`ativo_por_padrao=True` no módulo `filiais`)
- Test: `tests/test_modulos.py` (ou o que cobre `ativo_por_padrao` — ache com `grep -rn "ativo_por_padrao" tests/`)

- [ ] **Step 1: Write the failing test** — o módulo `filiais` nasce ligado numa instalação nova.
- [ ] **Step 2: Run to verify it fails**
- [ ] **Step 3: Implement** — `ativo_por_padrao=True`, com o motivo ao lado (R47 pede o motivo escrito): sem a tela de Lojas, o titular com várias empresas não cadastra as lojas delas.
- [ ] **Step 4: Run + commit**

---

### Task 10: A tela de Conta

**Files:**
- Create: `plataforma/views_conta.py`
- Modify: `plataforma/urls.py`, `plataforma/modulo.py` (um `ModuloSpec` novo, `chave="conta"`, rota `/conta`, `ativo_por_padrao=True`, permissão `conta.ver`)
- Test: `tests/test_tela_conta.py` (criar)

- [ ] **Step 1: Write the failing tests**

```python
def test_o_titular_ve_os_dados_da_conta_e_as_empresas(conta_com_duas):
    html = conta_com_duas["cliente"].get("/conta").content.decode()
    assert conta_com_duas["titular"].email in html
    assert "Alfa Ltda" in html and "Beta Ltda" in html
    assert "2 empresas" in html


def test_o_vendedor_nao_abre(conta_com_duas):
    assert conta_com_duas["vendedor"].get("/conta").status_code == 404


def test_a_mw5_ve_a_conta_do_contexto(conta_com_duas):
    html = conta_com_duas["mw5"].get("/conta").content.decode()
    assert "Alfa Ltda" in html
```

Monte `conta_com_duas` no molde de `tests/test_tela_empresa.py`: titular com
duas empresas, um vendedor alocado numa delas, e a MW5 logada com a conta no
contexto.

- [ ] **Step 2: Run to verify they fail**

- [ ] **Step 3: Implement** — leitura: o nome da conta (o titular), o e-mail, quantas empresas e quantas pessoas, e a lista das empresas com as lojas de cada uma. Sem edição nesta entrega.

- [ ] **Step 4: Run + varreduras** (`tests/test_guarda.py`, `tests/test_guarda_modulo.py`, `tests/test_regra_tabela.py`, `tests/test_personificacao.py`, `tests/test_menu.py`) **+ commit**

---

## Entrega 3 — a fila

### Task 11: "Todas as empresas" no painel do titular

**Files:**
- Modify: `fila/indicadores.py` (recorte por várias empresas), `fila/views_indicadores.py` (o filtro, o bloco "Por empresa", a coluna Empresa)
- Test: `tests/test_fila_tela_indicadores.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_todas_as_empresas_soma_e_separa(rede_de_duas):
    """O espelho do "Todas as lojas" (commit 881ec60), um nível acima."""
    d = rede_de_duas
    _venda_hoje_em(d, d.ana, d.loja_alfa, "300")
    _venda_hoje_em(d, d.caio, d.loja_beta, "700")
    html = _html(d.titular_logado, periodo="hoje", empresa="todas")
    assert "R$ 1.000,00" in html
    assert 'data-ind="por-empresa"' in html
    por_empresa = html[html.index('data-ind="por-empresa"'):]
    assert "Alfa" in por_empresa and "Beta" in por_empresa
    ranking = html[html.index('data-ind="ranking"'):]
    import re
    assert re.search(r"<th[^>]*>\s*<a[^>]*>Empresa", ranking)


def test_o_padrao_continua_sendo_a_empresa_do_cabecalho(rede_de_duas):
    d = rede_de_duas
    _venda_hoje_em(d, d.ana, d.loja_alfa, "300")
    _venda_hoje_em(d, d.caio, d.loja_beta, "700")
    html = _html(d.titular_logado, periodo="hoje")
    assert "R$ 300,00" in html and "Caio" not in html
```

`rede_de_duas` monta as duas empresas, uma loja em cada, um vendedor em cada e
o titular logado com a alfa no cabeçalho; `_venda_hoje_em` é o `_venda_hoje`
que o arquivo já tem, recebendo a loja.

- [ ] **Step 2: Run to verify they fail**

- [ ] **Step 3: Implement**

`Recorte` ganha `empresas` (tupla) no lugar de `empresa`, e as consultas passam a filtrar `empresa__in=recorte.empresas` mantendo `filial__in=recorte.lojas`. O filtro da tela ganha o campo Empresa (só para quem alcança mais de uma), com a opção "Todas as empresas", e o bloco "Por empresa" espelha o "Por loja" de hoje.

**Atenção:** `objects.da_empresa(...)` recebe UMA empresa. Para o recorte de várias, use `objects.da_conta(<conta>)` filtrando `empresa__in=...`, e escreva ao lado por que isso é seguro (as empresas do recorte saem do alcance da pessoa).

- [ ] **Step 4: Run + commit**

---

### Task 12: Um ponto por vez, em qualquer empresa

**Files:**
- Modify: `fila/models.py` (comentário da restrição `fila_uma_presenca_aberta_por_pessoa`), `fila/acoes.py::bater_ponto` (a frase da recusa)
- Test: `tests/test_fila_acoes.py`

- [ ] **Step 1: Write the failing test**

```python
def test_nao_se_bate_ponto_em_duas_empresas_ao_mesmo_tempo(duas_empresas):
    """A restrição de uma presença aberta por pessoa já existia; o que
    faltava era a frase dizer de qual loja (e de qual empresa) sair."""
    from contas.models import Nivel, Usuario
    from fila.acoes import Recusa, bater_ponto

    from tests.conftest import alocar, email_de

    d = duas_empresas
    ana = Usuario.objects.create_user(email=email_de("ana-ponto"), password=SENHA,
                                      nivel=Nivel.MEMBRO, dono=d.titular)
    alocar(ana, d.alfa, "vendedor", filial=d.loja_alfa)
    alocar(ana, d.beta, "vendedor", filial=d.loja_beta)
    bater_ponto(ana, d.loja_alfa)
    with pytest.raises(Recusa) as recusa:
        bater_ponto(ana, d.loja_beta)
    assert str(d.loja_alfa) in recusa.value.frase
    assert str(d.alfa) in recusa.value.frase
```

- [ ] **Step 2: Run to verify it fails** (hoje a frase pode não citar a outra empresa)
- [ ] **Step 3: Implement** — a recusa passa a dizer a loja E a empresa; o comentário da restrição diz que ela vale entre empresas.
- [ ] **Step 4: Run + commit**

---

### Task 13: Castelhano, documentação e a suíte inteira

- [ ] **Step 1: Find the untranslated phrases** (o mesmo script do plano das correções do gerente, apontando para os arquivos tocados aqui)
- [ ] **Step 2: Add them to `locale/es/LC_MESSAGES/django.po` and compile**
- [ ] **Step 3: `CLAUDE.md`** — §7: "Uma conta, uma empresa" vira "Uma conta, VÁRIAS empresas", com o que continua valendo (o `conta_guid`, a empresa como fronteira, a Matriz por empresa). §9: saem os dois itens em aberto (várias empresas e o módulo de Filiais desligado). Atualize a contagem de arquivos de teste.
- [ ] **Step 4: Full suite** — `timeout 590 .venv/bin/python -m pytest -q -p no:warnings`
- [ ] **Step 5: Check in the browser** — com o servidor local: criar a segunda empresa como MW5, trocar de empresa no cabeçalho, ver a marca mudar, cadastrar loja na segunda, bater ponto e conferir o painel com "Todas as empresas". Em 390px e 1366px.
- [ ] **Step 6: Commit**
