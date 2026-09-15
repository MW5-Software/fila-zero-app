# Identidade e acesso no SaaS — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar o núcleo de identidade do Portal de Vendas para o modelo de
SaaS: a conta é o usuário Admin, o usuário é próprio (`contas.Usuario`) com
login por e-mail, toda tabela nossa ganha GUID, e vendedor e comprador saem
dos níveis para virarem papéis do perfil.

**Architecture:** Onze tarefas, cada uma terminando com a suíte VERDE. A ordem
foi escolhida para isso: o papel entra no perfil **antes** de os níveis
antigos saírem, então nunca existe um momento em que os seis lugares que
decidem visibilidade fiquem sem entrada. A troca de `AUTH_USER_MODEL` é uma
tarefa só, atômica por necessidade — não existe meio-caminho verde nela.

**Tech Stack:** Django 5.2, Postgres 16, pytest + pytest-django, `uv`.

**Spec:** `docs/superpowers/specs/2026-09-02-saas-identidade-e-acesso-design.md`

## Global Constraints

Estas valem para **toda** tarefa. Não repetidas nos passos.

- **Comentário diz POR QUÊ, não o quê.** Português, frase inteira. O código já
  diz o que faz; o que se perde é a razão, e é ela que impede alguém de
  "simplificar" de volta para o defeito.
- **Teste com dente.** Depois de escrever um teste, quebre o código de
  propósito e veja o teste ficar vermelho. Mutação que não produz vermelho é
  suspeita de mutação que não aconteceu.
- **`nucleo/` é porte verbatim e não se emenda.** Correção do design system
  vai em `plataforma/static/plataforma/kronos.css`, com o motivo ao lado.
- **Commit em português**, longo, dizendo o que estava errado antes e por que
  a correção é essa. `feat:`/`fix:`/`refactor:`/`docs:`.
- **Nunca** adicionar Claude como coautor nem rodapé de "gerado com". Autor:
  `git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br"`.
- **Nada de produção, servidor, FTP ou credencial** sem autorização explícita.
- Comando da suíte:
  `DJANGO_DEBUG=1 KRONOS_BANCO="postgresql://kronos:kronos@127.0.0.1:5434/kronos" .venv/bin/python -m pytest -q`
- Ponto de partida: **1739 testes passam, 7 skipped.** Toda tarefa termina com
  esse número ou maior.

---

## Estrutura de arquivos

| arquivo | responsabilidade | tarefa |
|---|---|---|
| `comum/guid.py` (novo) | a base `ComGuid` | 1 |
| `tests/test_regra_guid.py` (novo) | varredura: model nosso sem GUID | 1 |
| `contas/models.py` | `Usuario`, `Perfil` | 2, 3, 4 |
| `contas/inquilino.py` (movido de `acesso/`) | `ModeloDaEmpresa`, `GerenteDaEmpresa` | 2 |
| `contas/alcance.py` (movido de `acesso/`) | quem alcança o quê | 2, 7 |
| `contas/fabrica.py` (movido de `acesso/`) | permissão por nível | 6, 8 |
| `contas/papel.py` (novo) | `tem_papel()` | 5 |
| `contas/planos.py` (novo) | limites por plano | 10 |
| `contas/backend.py` | autenticação e sessão | 2 |
| `contas/mw5.py` | o usuário da MW5 | 2 |
| `plataforma/models.py` | `Empresa.dono` | 7 |
| `catalogo/preco.py`, `catalogo/views_vitrine.py` | trocam nível por papel | 5 |
| `orcamento/visibilidade.py`, `orcamento/views.py` | idem | 5 |

O app `acesso/` deixa de existir na tarefa 2.

**A decisão 4 da spec (filial é cadastro, não fronteira) não tem tarefa, e é
de propósito:** ela descreve o que já é verdade hoje. Filial existe, pertence
à empresa, e nenhuma tabela de negócio aponta para ela; o vínculo do usuário
já é com a empresa inteira. Não há trabalho — há uma decisão de NÃO fazer, e
ela está na spec para ninguém acrescentar `filial_id` por hábito.

**Nome da tabela de ligação usuário↔perfil:** a spec a chama de
`contas_usuario_perfis`, mas a M2M continua declarada em `Perfil.usuarios`, e
o Django nomeia pela classe que declara — `contas_perfil_usuarios`. Não vale
mover a declaração só pelo nome: `Perfil` é quem tem a M2M para `Permission`
ao lado, e as duas juntas são a definição de perfil.

---

### Task 1: A base do GUID e a varredura que a exige

**Files:**
- Create: `comum/guid.py`
- Create: `tests/test_regra_guid.py`
- Modify: `acesso/inquilino.py` (a `ModeloDaEmpresa` passa a herdar)
- Modify: `plataforma/models.py` (`Empresa`, `Filial`, `Modulo`, `Falha`)
- Modify: `contas/models.py` (`Perfil`, `RegistroDeAuditoria`)

**Interfaces:**
- Produces: `comum.guid.ComGuid` — model abstrato com o campo `guid`
  (`UUIDField`, `unique=True`, `default=uuid4`, `editable=False`).

- [ ] **Step 1: Escrever a varredura, que vai falhar**

```python
# tests/test_regra_guid.py
"""Toda tabela NOSSA carrega um GUID.

Existe porque o pedido é "um identificador estável em todas as tabelas", e um
pedido desses só se cumpre por varredura: a tabela de amanhã nasce sem ele se
depender de alguém lembrar, e a falta só aparece no dia em que alguém de fora
pede o registro por um id que não existe.

As tabelas do Django (`auth_permission`, `django_content_type`,
`django_session`) ficam de fora porque não são nossas — não há onde
acrescentar coluna nelas, e é essa a mesma razão pela qual o usuário passou a
ser próprio.
"""

import pytest
from django.apps import apps

#: Os nossos apps. Um app novo entra aqui, e é de propósito que a lista seja
#: explícita: `INSTALLED_APPS` inteiro traria os do Django junto.
APPS_DA_CASA = ("contas", "plataforma", "catalogo", "orcamento", "comum")

#: Sem GUID, com o motivo ao lado. Uma isenção sem motivo vira gaveta, e
#: gaveta ninguém relê.
ISENTOS: dict[str, str] = {}


def _models_da_casa():
    for model in apps.get_models():
        if model._meta.app_label not in APPS_DA_CASA:
            continue
        if model._meta.auto_created:      # tabelas de ligação M2M
            continue
        yield model


def test_todo_model_nosso_tem_guid():
    faltando = [
        m._meta.label for m in _models_da_casa()
        if not any(f.name == "guid" for f in m._meta.fields)
        and m._meta.label not in ISENTOS
    ]
    assert faltando == [], (
        f"models sem GUID: {faltando}. Herde `comum.guid.ComGuid` — ou "
        f"acrescente a `ISENTOS` com o motivo escrito ao lado."
    )


def test_o_guid_e_unico_e_nao_editavel():
    """Único porque é ele que identifica a linha de fora; não editável porque
    um identificador que muda não identifica nada."""
    from catalogo.models import Produto

    campo = Produto._meta.get_field("guid")
    assert campo.unique is True
    assert campo.editable is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `DJANGO_DEBUG=1 KRONOS_BANCO="postgresql://kronos:kronos@127.0.0.1:5434/kronos" .venv/bin/python -m pytest tests/test_regra_guid.py -q`
Expected: FAIL — `models sem GUID: ['contas.Perfil', 'plataforma.Empresa', ...]`

- [ ] **Step 3: Escrever a base**

```python
# comum/guid.py
"""O identificador que atravessa a fronteira do sistema.

Toda tabela nossa carrega um GUID. Não é a chave primária, e a diferença é
deliberada: como chave, ele seria impossível de aplicar "em todas as tabelas"
— as do Django continuariam `bigint`, e o banco ficaria metade em UUID e
metade em inteiro, que é justo a falta de uniformidade que o pedido quer
evitar. Como coluna, toda linha nossa tem um, sem exceção.

O custo do outro caminho cai no lugar mais quente: `empresa_id` está em quase
todo índice do sistema, e trocá-la por UUID multiplica por quatro o tamanho
dela em cada um.

`uuid4` (aleatório) e não `uuid7` (ordenado no tempo): o ordenado existe para
não fragmentar o índice a cada inserção, e isso pesa quando o UUID é a CHAVE.
Aqui ele é um índice secundário. `uuidv7` também é nativo só no Postgres 18, e
este roda em 16.

Ver `docs/superpowers/specs/2026-09-02-saas-identidade-e-acesso-design.md`.
"""

from __future__ import annotations

from uuid import uuid4

from django.db import models

__all__ = ["ComGuid"]


class ComGuid(models.Model):
    guid = models.UUIDField(
        "GUID", unique=True, default=uuid4, editable=False,
        help_text="Identificador estável desta linha para fora do sistema.",
    )

    class Meta:
        abstract = True
```

- [ ] **Step 4: Fazer os models herdarem**

Em `acesso/inquilino.py`, `class ModeloDaEmpresa(models.Model)` vira
`class ModeloDaEmpresa(ComGuid)` — as 16 tabelas de negócio ganham de uma vez.

Em `plataforma/models.py`: `Empresa`, `Filial`, `Modulo`, `Falha`.
Em `contas/models.py`: `Perfil`, `RegistroDeAuditoria`.

Cada uma troca `models.Model` por `ComGuid` na declaração da classe. Nenhuma
outra mudança.

- [ ] **Step 5: Gerar e aplicar a migração**

```bash
DJANGO_DEBUG=1 KRONOS_BANCO="postgresql://kronos:kronos@127.0.0.1:5434/kronos" .venv/bin/python manage.py makemigrations --name guid
DJANGO_DEBUG=1 KRONOS_BANCO="postgresql://kronos:kronos@127.0.0.1:5434/kronos" .venv/bin/python manage.py migrate
```

**Atenção:** `default=uuid4` numa coluna `unique` de tabela com linhas exige
que o Django preencha linha a linha. O `makemigrations` vai perguntar; aceite
o padrão único por linha. Se ele oferecer um valor fixo, RECUSE — um GUID
igual em todas as linhas é o oposto do que a coluna existe para ser.

- [ ] **Step 6: Rodar a varredura e a suíte**

Run: `... -m pytest tests/test_regra_guid.py -q`
Expected: PASS

Run: `... -m pytest -q`
Expected: 1741 passed (1739 + 2 novos)

- [ ] **Step 7: Mutação — provar o dente**

Tire `ComGuid` de `plataforma.Empresa` (volte a `models.Model`), rode
`tests/test_regra_guid.py` e confirme VERMELHO nomeando `plataforma.Empresa`.
Restaure.

- [ ] **Step 8: Commit**

```bash
git add comum/guid.py tests/test_regra_guid.py acesso/inquilino.py plataforma/models.py contas/models.py */migrations/
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -F - <<'MSG'
feat: toda tabela nossa carrega um GUID

O identificador estável que a integração e a URL passam a citar. Coluna
única, não chave primária: como chave seria impossível cumprir "em todas as
tabelas" — as do Django continuariam bigint, e o banco ficaria metade em UUID.
E o custo cairia no lugar mais quente, porque `empresa_id` está em quase todo
índice do sistema.

Uma varredura recusa model nosso sem a coluna, na forma das cinco que já
existem: a tabela de amanhã nasce com GUID sem ninguém lembrar.
MSG
```

---

### Task 2: O usuário próprio, e as migrações do zero

**A tarefa grande.** Não existe meio-caminho verde: trocar `AUTH_USER_MODEL`
quebra ~450 pontos de uma vez, e a suíte é o que aponta cada um.

**Files:**
- Modify: `contas/models.py` (nasce `Usuario`)
- Modify: `config/settings.py` (`AUTH_USER_MODEL`)
- Modify: `contas/backend.py`, `contas/mw5.py`, `contas/views.py`
- Move: `acesso/inquilino.py` → `contas/inquilino.py`; `acesso/alcance.py` →
  `contas/alcance.py`; `acesso/fabrica.py` → `contas/fabrica.py`
- Delete: `acesso/` inteiro, e **todas** as migrações de todos os apps
- Test: a suíte inteira

**Interfaces:**
- Produces: `contas.models.Usuario` — `USERNAME_FIELD = "email"`, campos
  `email`, `nome`, `telefone`, `guid`, `nivel`, `dono`, `plano`.
- Produces: `contas.models.Nivel` — `IntegerChoices` ainda com os quatro
  valores de hoje (MASTER=0, ADMIN=1, VENDEDOR=2, COMPRADOR=3). **Reduzir para
  três é a Task 6**, depois de ninguém mais ler os dois últimos.

- [ ] **Step 1: Escrever os testes do usuário novo**

```python
# tests/test_usuario_model.py
"""O usuário deste produto: próprio, e com login por e-mail.

`auth_user` é criado por uma migração dentro do pacote do Django. Não é
possível acrescentar coluna nela — e era por isso que `nivel` morava em
`acesso_acesso`, uma tabela 1:1 ao lado. Com o produto virando SaaS, viriam
mais três colunas (`dono`, `plano`, `guid`) para o mesmo lugar.

Quatro tabelas viram uma.
"""

import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
class TestOUsuarioProprio:
    def test_o_model_do_projeto_e_o_nosso(self):
        assert get_user_model()._meta.label == "contas.Usuario"

    def test_entra_por_email_e_nao_por_apelido(self):
        """Num sistema que se assina, ninguém inventa apelido para entrar."""
        Usuario = get_user_model()
        assert Usuario.USERNAME_FIELD == "email"
        assert not any(f.name == "username" for f in Usuario._meta.fields)

    def test_o_email_e_unico(self):
        """É o login. Dois iguais seriam duas pessoas com a mesma porta."""
        from django.db import IntegrityError

        Usuario = get_user_model()
        Usuario.objects.create_user(email="a@b.com", nome="A", password="x")
        with pytest.raises(IntegrityError):
            Usuario.objects.create_user(email="a@b.com", nome="B", password="x")

    def test_nome_e_um_campo_so(self):
        """Como no `kronos-api2`. `first_name`/`last_name` obrigam toda tela a
        decidir como juntar os dois, e a primeira que decidir diferente das
        outras vira o defeito."""
        Usuario = get_user_model()
        pessoa = Usuario.objects.create_user(
            email="c@d.com", nome="Vera Souza", password="x")
        assert pessoa.nome == "Vera Souza"
        assert pessoa.get_full_name() == "Vera Souza"

    def test_o_superusuario_nasce_pelo_email(self):
        Usuario = get_user_model()
        chefe = Usuario.objects.create_superuser(
            email="mw5@mw5.com.br", nome="MW5", password="x")
        assert chefe.is_superuser and chefe.is_staff

    def test_tem_guid(self):
        Usuario = get_user_model()
        pessoa = Usuario.objects.create_user(
            email="e@f.com", nome="E", password="x")
        assert pessoa.guid is not None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_usuario_model.py -q`
Expected: FAIL — `contas.Usuario` não existe.

- [ ] **Step 3: Escrever o model e o manager**

```python
# contas/models.py — no topo do arquivo, antes de Perfil
from django.contrib.auth.models import AbstractUser, BaseUserManager


class Nivel(models.IntegerChoices):
    """A ordem dos números é do mais poderoso para o menos, como na origem —
    é o que faz `nivel <= Nivel.ADMIN` significar "admin ou acima" sem ninguém
    precisar decorar a lista."""

    MASTER = 0, "Master"
    ADMIN = 1, "Admin"
    # Os dois abaixo saem na Task 6, depois que o papel do perfil assumir o
    # lugar deles. Ficam aqui até lá para nenhuma tela quebrar no meio.
    VENDEDOR = 2, "Vendedor"
    COMPRADOR = 3, "Comprador"


class GerenteDeUsuario(BaseUserManager):
    """`create_user` do Django exige `username`, que este model não tem.

    O manager próprio existe só para isso: trocar o campo de identidade por
    `email` e normalizá-lo. `normalize_email` baixa o DOMÍNIO para minúsculas
    e preserva a parte antes do @ — o domínio não diferencia maiúscula, a
    caixa postal pode.
    """

    use_in_migrations = True

    def _criar(self, email, nome, password, **extras):
        if not email:
            raise ValueError("O e-mail é o login: não pode ficar vazio.")
        pessoa = self.model(
            email=self.normalize_email(email), nome=nome, **extras)
        pessoa.set_password(password)
        pessoa.save(using=self._db)
        return pessoa

    def create_user(self, email, nome="", password=None, **extras):
        extras.setdefault("is_staff", False)
        extras.setdefault("is_superuser", False)
        return self._criar(email, nome, password, **extras)

    def create_superuser(self, email, nome="", password=None, **extras):
        extras.setdefault("is_staff", True)
        extras.setdefault("is_superuser", True)
        extras.setdefault("nivel", Nivel.MASTER)
        if not extras["is_staff"] or not extras["is_superuser"]:
            raise ValueError("Superusuário nasce com is_staff e is_superuser.")
        return self._criar(email, nome, password, **extras)


class Usuario(ComGuid, AbstractUser):
    """A pessoa, e — quando é Admin — a CONTA.

    Herda `AbstractUser` e não `AbstractBaseUser`: o Portal já tem tela de
    perfil, avatar, auditoria e personificação em cima do encanamento do
    Django (grupos, permissões, `date_joined`, `is_active`), e `AbstractUser`
    preserva tudo isso. O que muda é a identidade — `username` sai, `email`
    entra — e `first_name`/`last_name` viram um `nome` só, como no
    `kronos-api2`.
    """

    username = None
    first_name = None
    last_name = None

    email = models.EmailField("e-mail", unique=True)
    nome = models.CharField("nome", max_length=255)
    telefone = models.CharField("telefone", max_length=20, blank=True, default="")

    nivel = models.IntegerField(
        "nível de acesso", choices=Nivel.choices, default=Nivel.COMPRADOR)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    objects = GerenteDeUsuario()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ("nome", "email")

    def __str__(self) -> str:
        return self.nome or self.email

    def get_full_name(self) -> str:
        """O `AbstractUser` monta o nome juntando `first_name` e `last_name`,
        que aqui não existem. Sem esta linha, toda tela que mostra o nome de
        alguém mostraria string vazia."""
        return self.nome

    def get_short_name(self) -> str:
        return self.nome.split(" ")[0] if self.nome else self.email
```

`dono` e `plano` **não** entram agora — são a Task 7 e a Task 10. Manter esta
tarefa no mínimo que já é enorme.

- [ ] **Step 4: Apontar o `AUTH_USER_MODEL`**

```python
# config/settings.py, junto dos outros ajustes de autenticação
# O usuário é deste projeto, e não o `auth.User` do Django. O motivo está em
# `contas/models.py::Usuario` e na spec de 02/09: `auth_user` nasce de uma
# migração dentro do pacote do Django e não aceita coluna nova, e este produto
# precisa de cinco.
AUTH_USER_MODEL = "contas.Usuario"
```

- [ ] **Step 5: Mover o app `acesso/` para dentro de `contas/`**

```bash
git mv acesso/inquilino.py contas/inquilino.py
git mv acesso/alcance.py  contas/alcance.py
git mv acesso/fabrica.py  contas/fabrica.py
git rm -r acesso/
```

`acesso/models.py` (o `Acesso` e o `Nivel`) some: o `Nivel` foi para
`contas/models.py` no passo 3, e as colunas do `Acesso` vão para o `Usuario` —
`nivel` agora, `dono` na Task 7.

As três M2M de `Acesso` viram M2M do `Usuario`:

```python
# contas/models.py, dentro de Usuario
empresas = models.ManyToManyField(
    "plataforma.Empresa", verbose_name="empresas",
    related_name="pessoas", blank=True)

compradores = models.ManyToManyField(
    "self", verbose_name="compradores da carteira", symmetrical=False,
    related_name="vendedores", blank=True)
```

Trocar todo `from acesso.` por `from contas.` no projeto:

```bash
grep -rl "from acesso\.\|import acesso" --include=*.py . | grep -v '\.venv' \
  | xargs sed -i 's/from acesso\./from contas./g; s/import acesso/import contas/g'
```

Depois disso, `contas/alcance.py` precisa parar de importar `Acesso` e passar
a ler direto do usuário: onde havia `acesso_de(u).nivel`, agora é `u.nivel`;
onde havia `acesso.empresas`, agora é `u.empresas`. A função `acesso_de`
deixa de existir e quem a chamava passa a usar o próprio usuário.

- [ ] **Step 6: Apagar todas as migrações e gerar a inicial**

```bash
# `-not -path`, e NUNCA `-prune`: o `-delete` do find implica `-depth`, que
# desliga o `-prune` em silêncio — a primeira versão deste comando apagou as
# migrações do próprio Django dentro do `.venv`, e o projeto só voltou a subir
# depois de `uv sync --reinstall-package django`.
find . -not -path "./.venv/*" -name "0*.py" -path "*/migrations/*" -print -delete
DJANGO_DEBUG=1 KRONOS_BANCO="postgresql://kronos:kronos@127.0.0.1:5434/kronos" .venv/bin/python manage.py makemigrations contas plataforma catalogo orcamento
```

**A ordem importa:** `contas` primeiro, porque todo o resto aponta para o
usuário.

Recriar o banco de desenvolvimento do zero:

```bash
docker exec -i portal-de-vendas-banco-1 psql -U kronos -d postgres -c \
  "DROP DATABASE kronos; CREATE DATABASE kronos OWNER kronos;"
DJANGO_DEBUG=1 KRONOS_BANCO="postgresql://kronos:kronos@127.0.0.1:5434/kronos" .venv/bin/python manage.py migrate
```

O dado de demonstração (11 produtos, 3 empresas) se perde. Está previsto na
spec.

- [ ] **Step 7: Ajustar a autenticação**

`contas/mw5.py`: `LOGIN = "mw5"` vira `EMAIL = "mw5@mw5.com.br"`, e o
`get_or_create` passa a procurar por `email=`. O model histórico do
`post_migrate` continua sendo obtido por `apps.get_model("contas", "Usuario")`
em vez de `("auth", "User")`.

`contas/backend.py`:
- `authenticate(username=login, ...)` → `authenticate(username=login, ...)`
  continua igual: o Django passa o valor para o `USERNAME_FIELD`, seja qual
  for o nome dele. **Não trocar para `email=`** — o `ModelBackend` lê o
  parâmetro chamado `username`.
- `_para_o_nucleo`: `usuario.get_full_name().strip() or usuario.username` vira
  `usuario.nome or usuario.email`; `login=usuario.username` vira
  `login=usuario.email`.

`contas/views.py`: o campo do formulário continua `name="usuario"` (é o que o
`nucleo/layout.py` emite); só o rótulo na tela vira "E-mail".

- [ ] **Step 8: A renomeação mecânica**

```bash
# nos testes: create_user(username="x") -> create_user(email="x@teste.com", nome="X")
grep -rn "username=" tests/ | wc -l   # ~207 pontos
```

Faça em lotes por arquivo, rodando a suíte a cada lote. Regra de conversão:

| antes | depois |
|---|---|
| `create_user(username="ana", password=S)` | `create_user(email="ana@teste.com", nome="Ana", password=S)` |
| `create_superuser(username="mw5", ...)` | `create_superuser(email="mw5@teste.com", nome="MW5", ...)` |
| `first_name="Vera"` | `nome="Vera"` |
| `post(reverse("entrar"), {"usuario": "ana", ...})` | `{"usuario": "ana@teste.com", ...}` |
| `User.objects.get(username="ana")` | `Usuario.objects.get(email="ana@teste.com")` |

- [ ] **Step 9: Rodar a suíte até verde**

Run: `... -m pytest -q`
Expected: 1741+ passed. Espere várias rodadas.

- [ ] **Step 10: Provar que o login por e-mail funciona de ponta a ponta**

```python
# acrescentar em tests/test_login.py
@pytest.mark.django_db
def test_entra_com_o_email_e_nao_com_apelido(client):
    """A prova que atravessa: a tela de entrada, o backend e a sessão."""
    from django.contrib.auth import get_user_model

    get_user_model().objects.create_user(
        email="vera@premix.com", nome="Vera", password="segredo-de-teste")
    resposta = client.post(reverse("entrar"),
                           {"usuario": "vera@premix.com",
                            "senha": "segredo-de-teste"})
    assert resposta.status_code == 302
```

- [ ] **Step 11: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -F - <<'MSG'
feat: o usuário passa a ser deste projeto, e entra por e-mail

`auth_user` nasce de uma migração dentro do pacote do Django, no `.venv`. Não
é possível acrescentar coluna nela: editar o arquivo do Django some no próximo
`uv sync`, `ALTER TABLE` cru dá uma coluna que o ORM não conhece, e reabrir a
classe em tempo de execução quebra na próxima versão. O Django oferece dois
caminhos, e só dois — tabela 1:1 ao lado, ou usuário próprio.

`acesso_acesso` era a tabela 1:1, e existia justamente por isso. Com o produto
virando SaaS, viriam mais três colunas para o mesmo lugar. Quatro tabelas
viram uma.

Igual ao `kronos-api2`, que já fez esta troca: `nome` em vez de
`first_name`/`last_name`, e login por e-mail — num sistema que se assina,
ninguém inventa apelido para entrar.

As migrações foram refeitas do zero. Só era possível agora: trocar
`AUTH_USER_MODEL` num projeto com migrações existentes é a operação mais
dolorosa do Django, e depois da primeira instalação de cliente este caminho
desaparece.
MSG
```

---

### Task 3: Avatar e marca de senha viram colunas

**Files:**
- Modify: `contas/models.py` (colunas no `Usuario`; `Avatar` e `MarcaDeSenha` saem)
- Modify: `contas/views_perfil.py`, `contas/backend.py`
- Test: `tests/test_avatar.py`, `tests/test_marca_de_senha.py`

**Interfaces:**
- Produces: `Usuario.avatar` (`BinaryField`), `Usuario.avatar_tipo` (`CharField`),
  `Usuario.senha_definida_em` (`DateTimeField`).

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_avatar.py — acrescentar
@pytest.mark.django_db
def test_o_avatar_e_coluna_do_usuario_e_nao_tabela():
    """Duas tabelas 1:1 a mais fariam toda consulta sobre uma pessoa juntar
    quatro. É o "o que podia ser coluna vira coluna" da spec de 02/09."""
    from django.apps import apps
    from django.contrib.auth import get_user_model

    Usuario = get_user_model()
    assert any(f.name == "avatar" for f in Usuario._meta.fields)
    assert any(f.name == "avatar_tipo" for f in Usuario._meta.fields)
    assert not apps.is_installed("contas") or not any(
        m._meta.model_name == "avatar" for m in apps.get_models())
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_avatar.py -q`
Expected: FAIL

- [ ] **Step 3: Mover os campos**

```python
# contas/models.py, dentro de Usuario
#: A foto, como bytes no próprio banco. Não vai para uma pasta no disco
#: porque, com vinte instalações, uma pasta é vinte lugares para lembrar de
#: incluir no backup — e um deles sempre escapa.
avatar = models.BinaryField("avatar", null=True, blank=True)
#: O media type que `nucleo.images.validar` decidiu pelo CONTEÚDO — nunca o
#: que o navegador declarou ao enviar.
avatar_tipo = models.CharField("tipo do avatar", max_length=40,
                               blank=True, default="")
#: Quando a senha foi definida pela última vez.
senha_definida_em = models.DateTimeField("senha definida em",
                                          null=True, blank=True)
```

Apagar as classes `Avatar` e `MarcaDeSenha` de `contas/models.py`.

- [ ] **Step 4: Ajustar quem lia**

`contas/backend.py::_para_o_nucleo`: `Avatar.objects.filter(usuario=usuario).exists()`
vira `bool(usuario.avatar)`.

`contas/views_perfil.py`: gravar passa a ser `usuario.avatar = bytes;
usuario.avatar_tipo = tipo; usuario.save(update_fields=[...])`.

Onde `MarcaDeSenha` era escrita, agora é
`usuario.senha_definida_em = timezone.now()`.

- [ ] **Step 5: Migração e suíte**

```bash
... manage.py makemigrations contas --name avatar_e_senha_viram_colunas
... manage.py migrate
... -m pytest -q
```
Expected: verde

- [ ] **Step 6: Commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "refactor: avatar e marca de senha viram colunas do usuário

Eram duas tabelas 1:1, e existiam pelo mesmo motivo de `acesso_acesso`: não
dava para acrescentar coluna no \`auth_user\`. Com o usuário próprio, dá — e
toda consulta sobre uma pessoa deixa de juntar quatro tabelas."
```

---

### Task 4: O perfil ganha dono e papel

Nada lê o papel ainda — é a Task 5. Esta termina verde por ser aditiva.

**Files:**
- Modify: `contas/models.py` (`Perfil`)
- Test: `tests/test_perfis.py`

**Interfaces:**
- Produces: `contas.models.Papel` — `TextChoices` com `COMPRADOR` e `VENDEDOR`.
- Produces: `Perfil.dono` (FK `Usuario`), `Perfil.papel` (`CharField`),
  e a restrição `perfil_unico_por_conta`.

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_perfis.py — acrescentar
@pytest.mark.django_db
class TestOPerfilEDaConta:
    """Com cada Admin criando os dele, "vendedor" existiria em várias contas.

    O nome era único no sistema inteiro, o que fazia o segundo cliente a
    cadastrar um perfil "Vendedor" tomar erro por causa de um cliente que ele
    não conhece.
    """

    def _admin(self, email):
        from django.contrib.auth import get_user_model
        from contas.models import Nivel

        return get_user_model().objects.create_user(
            email=email, nome=email, password="x", nivel=Nivel.ADMIN)

    def test_duas_contas_podem_ter_o_mesmo_nome_de_perfil(self):
        from contas.models import Perfil

        a, b = self._admin("a@x.com"), self._admin("b@x.com")
        Perfil.objects.create(dono=a, nome="vendedor", rotulo="Vendedor")
        Perfil.objects.create(dono=b, nome="vendedor", rotulo="Vendedor")
        assert Perfil.objects.filter(nome="vendedor").count() == 2

    def test_a_mesma_conta_nao_repete_o_nome(self):
        from django.db import IntegrityError
        from contas.models import Perfil

        a = self._admin("c@x.com")
        Perfil.objects.create(dono=a, nome="vendedor", rotulo="Vendedor")
        with pytest.raises(IntegrityError):
            Perfil.objects.create(dono=a, nome="vendedor", rotulo="Outro")

    def test_o_perfil_declara_o_papel(self):
        """Linhas do banco apontam para compradores
        (`catalogo_preco.comprador_id`). O sistema precisa responder "quem são
        os compradores desta empresa?", e isso não sai de permissão —
        permissão diz o que se ABRE, não o que se É."""
        from contas.models import Papel, Perfil

        a = self._admin("d@x.com")
        p = Perfil.objects.create(dono=a, nome="comprador",
                                  rotulo="Comprador", papel=Papel.COMPRADOR)
        assert p.papel == Papel.COMPRADOR

    def test_papel_vazio_e_o_normal(self):
        """"Financeiro" não é comprador nem vendedor, e a maioria dos perfis
        é assim."""
        from contas.models import Perfil

        a = self._admin("e@x.com")
        p = Perfil.objects.create(dono=a, nome="financeiro", rotulo="Financeiro")
        assert p.papel == ""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_perfis.py -q`
Expected: FAIL — `Perfil` não tem `dono`.

- [ ] **Step 3: Implementar**

```python
# contas/models.py
class Papel(models.TextChoices):
    """O que a pessoa É no negócio — diferente do que ela PODE abrir.

    Mora no perfil, e não na pessoa, porque quem dá o perfil "Comprador" a
    alguém está dizendo que ela é compradora: as duas coisas não podem
    discordar. Como coluna da pessoa, nada impediria papel de vendedor com
    perfil de comprador, e os seis lugares que decidem visibilidade
    divergiriam da tela.
    """

    COMPRADOR = "comprador", "Comprador"
    VENDEDOR = "vendedor", "Vendedor"


# dentro de Perfil
dono = models.ForeignKey(
    "contas.Usuario", verbose_name="conta", on_delete=models.CASCADE,
    related_name="perfis_criados", null=True, blank=True,
    help_text="O Admin dono deste perfil. Nulo nos perfis da MW5.")

papel = models.CharField(
    "papel", max_length=20, choices=Papel.choices, blank=True, default="")

# e a Meta
class Meta:
    verbose_name = "perfil"
    verbose_name_plural = "perfis"
    ordering = ("rotulo",)
    constraints = [
        models.UniqueConstraint(
            fields=("dono", "nome"), name="perfil_unico_por_conta",
            violation_error_message="Já existe um perfil com este nome nesta conta."),
    ]
```

O `unique=True` sai de `nome`: a unicidade passa a ser por conta.

- [ ] **Step 4: Migração, suíte, mutação**

```bash
... manage.py makemigrations contas --name perfil_da_conta_com_papel
... manage.py migrate
... -m pytest -q
```

Mutação: tire a `UniqueConstraint` e confirme que
`test_a_mesma_conta_nao_repete_o_nome` fica vermelho.

- [ ] **Step 5: Commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: o perfil é da conta e declara o papel

O nome era único no sistema inteiro — com cada Admin criando os dele, o
segundo cliente a cadastrar um \"Vendedor\" tomaria erro por causa de um
cliente que ele não conhece. Passa a ser único DENTRO da conta.

E o perfil ganha \`papel\`: comprador, vendedor, ou nenhum. Mora aqui e não na
pessoa porque quem dá o perfil \"Comprador\" a alguém está dizendo que ela é
compradora, e as duas coisas não podem discordar."
```

---

### Task 5: `tem_papel()` e os seis lugares

**Files:**
- Create: `contas/papel.py`
- Modify: `catalogo/preco.py:76`, `catalogo/views_vitrine.py:871`,
  `orcamento/visibilidade.py:54`, `orcamento/views.py:542`,
  `contas/alcance.py:128`
- Test: `tests/test_papel.py`

**Interfaces:**
- Consumes: `contas.models.Papel`, `Perfil.papel` (Task 4)
- Produces: `contas.papel.tem_papel(usuario, papel) -> bool` e
  `contas.papel.papel_de(usuario) -> str` — devolve `Papel.COMPRADOR`,
  `Papel.VENDEDOR` ou `""`.

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_papel.py
"""Quem é comprador, quem é vendedor — e como o sistema descobre.

Seis lugares decidem visibilidade de dado por isto. Enquanto era nível, a
resposta vinha de uma coluna; agora vem dos perfis da pessoa.
"""

import pytest


def _pessoa(email, papel=""):
    from django.contrib.auth import get_user_model
    from contas.models import Nivel, Perfil

    Usuario = get_user_model()
    dono = Usuario.objects.create_user(
        email=f"dono-{email}", nome="Dono", password="x", nivel=Nivel.ADMIN)
    p = Usuario.objects.create_user(email=email, nome=email, password="x")
    if papel:
        perfil = Perfil.objects.create(
            dono=dono, nome=papel, rotulo=papel.title(), papel=papel)
        p.perfis.add(perfil)
    return p


@pytest.mark.django_db
class TestOPapelVemDoPerfil:
    def test_quem_tem_perfil_de_comprador_e_comprador(self):
        from contas.models import Papel
        from contas.papel import tem_papel

        assert tem_papel(_pessoa("a@x.com", Papel.COMPRADOR), Papel.COMPRADOR)

    def test_quem_nao_tem_perfil_nenhum_nao_tem_papel(self):
        from contas.models import Papel
        from contas.papel import papel_de, tem_papel

        pessoa = _pessoa("b@x.com")
        assert papel_de(pessoa) == ""
        assert not tem_papel(pessoa, Papel.COMPRADOR)

    def test_comprador_vence_quando_ha_dois(self):
        """É o papel que mais RESTRINGE o que se vê, e errar para o lado
        restritivo é o único jeito seguro de errar."""
        from contas.models import Papel, Perfil
        from contas.papel import papel_de

        pessoa = _pessoa("c@x.com", Papel.VENDEDOR)
        outro = Perfil.objects.create(
            dono=pessoa.perfis.first().dono, nome="comp2",
            rotulo="Comprador 2", papel=Papel.COMPRADOR)
        pessoa.perfis.add(outro)
        assert papel_de(pessoa) == Papel.COMPRADOR

    def test_perfil_sem_papel_nao_da_papel(self):
        from contas.papel import papel_de

        pessoa = _pessoa("d@x.com")
        from contas.models import Perfil
        dono = pessoa.__class__.objects.get(email="dono-d@x.com")
        pessoa.perfis.add(Perfil.objects.create(
            dono=dono, nome="financeiro", rotulo="Financeiro"))
        assert papel_de(pessoa) == ""

    def test_none_nao_tem_papel(self):
        """O visitante que ainda não entrou. `None` nunca pode nada — é o caso
        mais comum em rota pública e o que mais dói errar."""
        from contas.models import Papel
        from contas.papel import tem_papel

        assert not tem_papel(None, Papel.COMPRADOR)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_papel.py -q`
Expected: FAIL — `contas.papel` não existe.

- [ ] **Step 3: Implementar**

```python
# contas/papel.py
"""O que a pessoa é no negócio, lido dos perfis dela.

Substitui as seis perguntas `nivel == Nivel.COMPRADOR` que decidiam
visibilidade de dado. Enquanto comprador e vendedor eram níveis, a resposta
vinha de uma coluna; com eles virando perfis, vem daqui.

**Função e não método do model** pelo mesmo motivo de `contas/alcance.py`:
existem dois tipos de usuário nesta casa — o do ORM e a dataclass congelada
que o design system usa — e uma função resolve pelos dois sem que quem chama
precise saber qual tem na mão.
"""

from __future__ import annotations

from .models import Papel

__all__ = ["papel_de", "tem_papel"]

#: A ordem da precedência quando alguém tem dois. Comprador vence porque é o
#: papel que mais RESTRINGE o que se vê: ele enxerga os próprios orçamentos,
#: o vendedor enxerga os da carteira. Errar para o lado restritivo é o único
#: jeito seguro de errar.
_PRECEDENCIA = (Papel.COMPRADOR, Papel.VENDEDOR)


def papel_de(usuario) -> str:
    """`Papel.COMPRADOR`, `Papel.VENDEDOR` ou `""`.

    `""` para quem não entrou, para quem não tem perfil, e para quem só tem
    perfis sem papel — "Financeiro" não é comprador nem vendedor, e a maioria
    dos perfis é assim.
    """
    if usuario is None or not getattr(usuario, "pk", None):
        return ""
    papeis = set(
        usuario.perfis.exclude(papel="").values_list("papel", flat=True))
    for candidato in _PRECEDENCIA:
        if candidato in papeis:
            return candidato
    return ""


def tem_papel(usuario, papel: str) -> bool:
    return papel_de(usuario) == papel
```

- [ ] **Step 4: Trocar os seis lugares**

| arquivo | antes | depois |
|---|---|---|
| `catalogo/preco.py:76` | `acesso is None or acesso.nivel != Nivel.COMPRADOR` | `not tem_papel(usuario, Papel.COMPRADOR)` |
| `catalogo/views_vitrine.py:871` | `acesso is not None and acesso.nivel == Nivel.COMPRADOR` | `tem_papel(usuario, Papel.COMPRADOR)` |
| `orcamento/visibilidade.py:54` | `acesso.nivel == Nivel.COMPRADOR` | `tem_papel(usuario, Papel.COMPRADOR)` |
| `orcamento/views.py:542` | `acesso is not None and acesso.nivel == Nivel.COMPRADOR` | `tem_papel(request.usuario, Papel.COMPRADOR)` |
| `contas/alcance.py:128` | `acesso.e_vendedor` | `tem_papel(usuario, Papel.VENDEDOR)` |

Onde a função recebia `acesso` e agora precisa do usuário, passar
`request.usuario` — as cinco já têm o `request` ou o usuário à mão.

- [ ] **Step 5: Rodar a suíte**

Run: `... -m pytest -q`
Expected: **vários vermelhos**, porque os testes existentes criam gente com
`nivel=Nivel.COMPRADOR` e agora o papel vem do perfil. Cada um vira: criar o
perfil com papel e pôr a pessoa nele. Use uma função de apoio em
`tests/conftest.py`:

```python
def dar_papel(pessoa, papel, dono=None):
    """Põe `pessoa` num perfil com o papel pedido.

    Existe porque a suíte inteira criava gente dizendo `nivel=COMPRADOR`, e o
    papel deixou de ser nível. Sem isto, cada teste repetiria quatro linhas de
    cadastro — e o primeiro que esquecesse uma daria um vermelho que parece
    defeito da tela e é falta de cadastro no teste.
    """
    from contas.models import Nivel, Perfil

    Usuario = pessoa.__class__
    dono = dono or Usuario.objects.filter(nivel=Nivel.ADMIN).first() or pessoa
    perfil, _ = Perfil.objects.get_or_create(
        dono=dono, nome=papel, defaults={"rotulo": papel.title(), "papel": papel})
    pessoa.perfis.add(perfil)
    return perfil
```

- [ ] **Step 6: Mutação**

Troque `_PRECEDENCIA` para `(Papel.VENDEDOR, Papel.COMPRADOR)` e confirme que
`test_comprador_vence_quando_ha_dois` fica vermelho. Restaure.

- [ ] **Step 7: Commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: quem é comprador e quem é vendedor vem do perfil

Seis lugares decidem visibilidade de dado perguntando isto — quais orçamentos
a pessoa vê, qual preço, o que a vitrine mostra, quem pode cancelar, e a
carteira do vendedor. Todos perguntavam ao NÍVEL.

Com comprador e vendedor virando perfis, a resposta muda de lugar mas não de
natureza: \`tem_papel()\` lê dos perfis da pessoa. Comprador vence quando há
dois, porque é o papel que mais restringe o que se vê — errar para o lado
restritivo é o único jeito seguro de errar."
```

---

### Task 6: Os níveis viram três

Agora ninguém mais lê `VENDEDOR` nem `COMPRADOR` — a Task 5 tirou o último.

**Files:**
- Modify: `contas/models.py` (`Nivel`), `contas/fabrica.py`
- Test: `tests/test_nivel.py`

**Interfaces:**
- Produces: `Nivel` com `MASTER=0`, `ADMIN=1`, `USUARIO=2`.

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_nivel.py
"""Três níveis, e a ordem carrega peso.

Vendedor e comprador saíram: eles diziam o que a pessoa FAZ, e isso virou
papel do perfil. O que sobra diz o que ela é na estrutura da CONTA — e é isso
que um nível deve dizer num produto vendido por assinatura.
"""

import pytest


def test_sao_tres_e_na_ordem_do_poder():
    from contas.models import Nivel

    assert [n.value for n in Nivel] == [0, 1, 2]
    assert Nivel.MASTER < Nivel.ADMIN < Nivel.USUARIO


def test_vendedor_e_comprador_nao_sao_mais_niveis():
    """A regressão que este teste guarda: alguém reintroduzir o nível e passar
    a existir DUAS respostas para "esta pessoa é compradora?" — a do nível e a
    do perfil — que divergem no primeiro cadastro feito por uma das duas."""
    from contas.models import Nivel

    assert not hasattr(Nivel, "VENDEDOR")
    assert not hasattr(Nivel, "COMPRADOR")


def test_o_padrao_e_o_menos_poderoso():
    """Cadastro novo que nascesse ADMIN seria escalação por omissão."""
    from contas.models import Nivel, Usuario

    assert Usuario._meta.get_field("nivel").default == Nivel.USUARIO
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_nivel.py -q`
Expected: FAIL

- [ ] **Step 3: Implementar**

```python
# contas/models.py
class Nivel(models.IntegerChoices):
    """O que a pessoa é na estrutura da CONTA — não o que ela faz no negócio.

    A ordem dos números é do mais poderoso para o menos: é o que faz
    `nivel <= Nivel.ADMIN` significar "admin ou acima" sem ninguém decorar a
    lista.

    Vendedor e comprador não estão aqui de propósito. Eles diziam o que a
    pessoa FAZ, e isso virou papel do perfil (`contas/papel.py`): num produto
    de assinatura, o nível responde "quem manda em quem", e quem manda é a
    conta.
    """

    MASTER = 0, "Master"
    ADMIN = 1, "Admin"
    USUARIO = 2, "Usuário"
```

E `default=Nivel.USUARIO` no campo do `Usuario`.

Em `contas/fabrica.py`, `DE_FABRICA` perde as duas entradas de vendedor e
comprador e fica com três. O que era operacional daqueles dois migra para os
perfis pré-determinados da Task 9.

- [ ] **Step 4: Migração e suíte**

```bash
... manage.py makemigrations contas --name tres_niveis
... manage.py migrate
... -m pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: três níveis — Master, Admin e Usuário

Vendedor e comprador saem. Eles diziam o que a pessoa FAZ, e isso virou papel
do perfil na tarefa anterior. Num produto de assinatura, o nível responde
\"quem manda em quem\", e quem manda é a conta.

Um teste guarda a regressão de alguém reintroduzi-los: com o nível de volta,
passariam a existir DUAS respostas para \"esta pessoa é compradora?\", e elas
divergem no primeiro cadastro feito por uma das duas."
```

---

### Task 7: O dono — a conta existe

**Files:**
- Modify: `contas/models.py` (`Usuario.dono`), `plataforma/models.py` (`Empresa.dono`)
- Modify: `contas/alcance.py`
- Modify: `plataforma/views_empresa.py` (quem cria empresa)
- Test: `tests/test_conta.py`

**Interfaces:**
- Produces: `Usuario.dono` (FK self, `PROTECT`, nulo em Master e Admin),
  `Empresa.dono` (FK `Usuario`, `PROTECT`).
- Produces: `contas.alcance.conta_de(usuario) -> Usuario | None` — devolve o
  Admin dono, ou o próprio se ele for Admin, ou `None` para o Master.

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_conta.py
"""A conta é o usuário Admin.

Não existe tabela `conta`: o Admin É a assinatura. As empresas e os usuários
apontam para ele.
"""

import pytest


@pytest.fixture
def conta(db):
    from django.contrib.auth import get_user_model
    from contas.models import Nivel
    from plataforma.models import Empresa

    Usuario = get_user_model()
    admin = Usuario.objects.create_user(
        email="joao@silva.com", nome="João", password="x", nivel=Nivel.ADMIN)
    e1 = Empresa.objects.create(razao_social="Metalúrgica Ltda", dono=admin)
    e2 = Empresa.objects.create(razao_social="Distribuidora Ltda", dono=admin)
    ana = Usuario.objects.create_user(
        email="ana@silva.com", nome="Ana", password="x",
        nivel=Nivel.USUARIO, dono=admin)
    ana.empresas.set([e1])
    return {"admin": admin, "e1": e1, "e2": e2, "ana": ana}


@pytest.mark.django_db
class TestAConta:
    def test_o_admin_nao_tem_dono(self):
        """"Sem dono" é o que define ser uma conta. Um Admin apontando para si
        é um ciclo que toda consulta precisa lembrar de cortar — e a primeira
        que esquecer devolve o próprio dono misturado com os subordinados."""
        from django.contrib.auth import get_user_model
        from contas.models import Nivel

        admin = get_user_model().objects.create_user(
            email="z@x.com", nome="Z", password="x", nivel=Nivel.ADMIN)
        assert admin.dono is None

    def test_o_admin_alcanca_as_empresas_dele_pela_coluna(self, conta):
        """Sem tabela de ligação: a empresa aponta para o dono. Só o nível 2
        precisa de vínculo explícito, porque ele alcança um PEDAÇO."""
        from contas.alcance import empresas_alcancadas

        alcancadas = set(empresas_alcancadas(conta["admin"]))
        assert alcancadas == {conta["e1"], conta["e2"]}

    def test_o_usuario_alcanca_so_o_que_foi_vinculado(self, conta):
        from contas.alcance import empresas_alcancadas

        assert set(empresas_alcancadas(conta["ana"])) == {conta["e1"]}

    def test_o_usuario_do_vizinho_nao_alcanca_nada_daqui(self, conta):
        """A trava do condomínio, agora entre CONTAS."""
        from django.contrib.auth import get_user_model
        from contas.alcance import empresas_alcancadas
        from contas.models import Nivel

        Usuario = get_user_model()
        outro = Usuario.objects.create_user(
            email="rival@outra.com", nome="Rival", password="x",
            nivel=Nivel.ADMIN)
        subordinado = Usuario.objects.create_user(
            email="sub@outra.com", nome="Sub", password="x",
            nivel=Nivel.USUARIO, dono=outro)
        assert list(empresas_alcancadas(subordinado)) == []

    def test_nao_se_apaga_um_admin_que_tem_gente(self, conta):
        """`PROTECT`: apagar a conta com equipe dentro deixaria pessoas sem
        dono — e sem dono elas não alcançam nada, o que é sumiço silencioso."""
        from django.db.models import ProtectedError

        with pytest.raises(ProtectedError):
            conta["admin"].delete()

    def test_conta_de(self, conta):
        from contas.alcance import conta_de

        assert conta_de(conta["ana"]) == conta["admin"]
        assert conta_de(conta["admin"]) == conta["admin"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_conta.py -q`
Expected: FAIL

- [ ] **Step 3: Implementar as colunas**

```python
# contas/models.py, dentro de Usuario
dono = models.ForeignKey(
    "self", verbose_name="conta", on_delete=models.PROTECT,
    null=True, blank=True, related_name="subordinados",
    help_text="O Admin dono desta conta. Nulo no Master e no próprio Admin.")
```

```python
# plataforma/models.py, dentro de Empresa
dono = models.ForeignKey(
    "contas.Usuario", verbose_name="conta", on_delete=models.PROTECT,
    null=True, blank=True, related_name="empresas_proprias",
    help_text="O Admin dono desta empresa. Nulo só na semeada da instalação.")
```

- [ ] **Step 4: `conta_de` e o alcance**

```python
# contas/alcance.py
def conta_de(usuario):
    """O Admin dono da conta desta pessoa.

    O próprio, quando ela É o Admin; `None` para o Master, que não pertence a
    conta nenhuma — ele é da MW5.
    """
    from .models import Nivel

    if usuario is None:
        return None
    nivel = getattr(usuario, "nivel", None)
    if nivel == Nivel.MASTER:
        return None
    if nivel == Nivel.ADMIN:
        return usuario
    return getattr(usuario, "dono", None)
```

`empresas_alcancadas` passa a ter três caminhos:

```python
def empresas_alcancadas(usuario):
    """As empresas que esta pessoa alcança.

    O MASTER vê todas — ele é a MW5. O ADMIN vê as que são dele, pela coluna
    `dono` da empresa e sem tabela de ligação. O nível 2 vê as que foram
    vinculadas a ele, e a consulta ainda cruza com o dono: um vínculo com
    empresa de outra conta não pode valer nem se alguém o gravar à mão.
    """
    from plataforma.models import Empresa
    from .models import Nivel

    if usuario is None:
        return Empresa.objects.none()
    if getattr(usuario, "superuser", False) or usuario.nivel == Nivel.MASTER:
        return Empresa.objects.all()
    if usuario.nivel == Nivel.ADMIN:
        return Empresa.objects.filter(dono=usuario)
    return Empresa.objects.filter(pessoas=usuario, dono=usuario.dono)
```

- [ ] **Step 5: Quem cria empresa**

`plataforma/views_empresa.py::_e_master` vira `_pode_criar_empresa`, e passa a
aceitar `nivel <= Nivel.ADMIN`. Ao criar, `dono` recebe `conta_de(request.usuario)`.

- [ ] **Step 6: Migração, suíte, mutação**

Mutação: tire o `dono=usuario.dono` do filtro do nível 2 e confirme que
`test_o_usuario_do_vizinho_nao_alcanca_nada_daqui` fica vermelho.

- [ ] **Step 7: Commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: a conta existe — o Admin é dono das empresas e da equipe

Não existe tabela \`conta\`: o Admin É a assinatura. As empresas apontam para
ele, e os usuários dele também.

O Admin alcança as empresas dele pela coluna, sem tabela de ligação — só o
nível 2 tem vínculo explícito, porque ele alcança um pedaço. E o vínculo do
nível 2 é cruzado com o dono na consulta: um vínculo com empresa de outra
conta não vale nem se alguém o gravar à mão."
```

---

### Task 8: Duas naturezas de poder, e o teto do perfil

**Files:**
- Modify: `contas/permissoes.py` (a partição do catálogo)
- Modify: `contas/fabrica.py`
- Modify: `contas/views_perfis.py` (o teto)
- Test: `tests/test_fronteira_do_sistema.py`

**Interfaces:**
- Produces: `contas.permissoes.E_DE_SISTEMA` — conjunto de prefixos que só o
  Master alcança.
- Produces: `contas.permissoes.permissoes_da_conta()` — o que o Admin pode
  conceder.

- [ ] **Step 1: Escrever o teste de ataque**

```python
# tests/test_fronteira_do_sistema.py
"""A fronteira entre a MW5 e o assinante.

O Admin cria e edita perfis — é o dono da conta e organiza a equipe dele. Sem
teto, isso e "o Admin não alcança o sistema" seriam contraditórios: bastaria
montar um perfil com tudo e dá-lo a si mesmo.
"""

import pytest


@pytest.mark.django_db
class TestOAdminNaoAlcancaOSistema:
    def test_o_catalogo_de_permissoes_parte_em_dois(self):
        from contas.permissoes import E_DE_SISTEMA, permissoes_da_conta

        da_conta = {p.codename for p in permissoes_da_conta()}
        assert not any(
            c.startswith(prefixo) for c in da_conta for prefixo in E_DE_SISTEMA)

    def test_aparencia_modulos_e_falhas_sao_de_sistema(self):
        """São as três que já eram `so_mw5=True`. No SaaS ganham nome."""
        from contas.permissoes import E_DE_SISTEMA

        for chave in ("aparencia", "modulos", "falhas"):
            assert chave in E_DE_SISTEMA

    def test_o_admin_nao_monta_perfil_com_permissao_de_sistema(self, client):
        """O ataque: ele forja o POST com o id da permissão de Aparência."""
        from django.contrib.auth.models import Permission
        from django.urls import reverse
        from django.contrib.auth import get_user_model
        from contas.models import Nivel, Perfil

        Usuario = get_user_model()
        admin = Usuario.objects.create_user(
            email="dono@x.com", nome="Dono", password="s3nh4",
            nivel=Nivel.ADMIN)
        client.post(reverse("entrar"), {"usuario": "dono@x.com",
                                        "senha": "s3nh4"})
        de_sistema = Permission.objects.filter(
            codename__startswith="aparencia_").first()

        client.post(reverse("perfis"), {
            "acao": "criar", "rotulo": "Tudo",
            "permissoes": [str(de_sistema.pk)]})

        perfil = Perfil.objects.get(rotulo="Tudo")
        assert de_sistema not in perfil.permissoes.all(), (
            "o Admin montou um perfil com permissão de sistema")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_fronteira_do_sistema.py -q`
Expected: FAIL

- [ ] **Step 3: Implementar a partição**

```python
# contas/permissoes.py
#: Os módulos que só a MW5 alcança. Já eram `so_mw5=True` em
#: `plataforma/modulo.py`; no SaaS a distinção ganha nome, porque deixou de
#: ser "a MW5 e o cliente" e virou "o sistema e a conta".
E_DE_SISTEMA = frozenset({"aparencia", "modulos", "falhas", "parametros"})


def permissoes_da_conta():
    """O que um Admin pode conceder: tudo, menos o que é do sistema.

    É o teto do perfil. Sem ele, "o Admin edita perfis" e "o Admin não alcança
    o sistema" seriam contraditórios — bastaria montar um perfil com tudo e
    dá-lo a si mesmo.
    """
    from django.contrib.auth.models import Permission

    consulta = Permission.objects.filter(
        content_type__app_label=APP_DOS_MODULOS)
    for prefixo in E_DE_SISTEMA:
        consulta = consulta.exclude(codename__startswith=f"{prefixo}_")
    return consulta
```

- [ ] **Step 4: Aplicar o teto na tela de perfis**

`contas/views_perfis.py`: onde as permissões são oferecidas e onde são
salvas, usar `permissoes_da_conta()` quando quem edita não é Master. **Nos
dois lugares** — oferecer menos do que se aceita é o buraco clássico: a tela
esconde e o formulário forjado passa.

- [ ] **Step 5: Suíte, mutação**

Mutação: no salvar, volte a aceitar `Permission.objects.all()` e confirme que
`test_o_admin_nao_monta_perfil_com_permissao_de_sistema` fica vermelho.

- [ ] **Step 6: Commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: o catálogo de permissões parte em sistema e conta

O Admin pode tudo dentro das empresas dele, e nada do sistema — Aparência,
Módulos, Falhas e Parâmetros. Eram \`so_mw5=True\`; no SaaS a distinção ganha
nome, porque deixou de ser \"a MW5 e o cliente\" e virou \"o sistema e a
conta\".

O teto vale nos DOIS lugares: onde a tela oferece e onde o servidor grava.
Oferecer menos do que se aceita é o buraco clássico — a tela esconde e o
formulário forjado passa."
```

---

### Task 9: Os perfis pré-determinados, copiados por conta

**Files:**
- Create: `contas/perfis_de_fabrica.py`
- Modify: `contas/views_usuarios.py` (ao criar um Admin)
- Test: `tests/test_perfis_de_fabrica.py`

**Interfaces:**
- Consumes: `Perfil.dono`, `Perfil.papel` (Task 4); `permissoes_da_conta()` (Task 8)
- Produces: `contas.perfis_de_fabrica.semear_para(admin) -> int`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_perfis_de_fabrica.py
"""Os perfis que toda conta nova recebe.

São CÓPIAS, e não um perfil compartilhado: o Admin edita os dele, e um perfil
compartilhado e editável mudaria o "Vendedor" de todas as contas de uma vez.
"""

import pytest


def _admin(email="dono@x.com"):
    from django.contrib.auth import get_user_model
    from contas.models import Nivel

    return get_user_model().objects.create_user(
        email=email, nome="Dono", password="x", nivel=Nivel.ADMIN)


@pytest.mark.django_db
class TestOsPerfisDeFabrica:
    def test_a_conta_nova_recebe_os_tres(self):
        from contas.models import Perfil
        from contas.perfis_de_fabrica import semear_para

        admin = _admin()
        semear_para(admin)
        nomes = set(Perfil.objects.filter(dono=admin).values_list("nome", flat=True))
        assert {"comprador", "vendedor", "financeiro"} <= nomes

    def test_o_comprador_e_o_vendedor_vem_com_papel(self):
        from contas.models import Papel, Perfil
        from contas.perfis_de_fabrica import semear_para

        admin = _admin("a@x.com")
        semear_para(admin)
        assert Perfil.objects.get(dono=admin, nome="comprador").papel == Papel.COMPRADOR
        assert Perfil.objects.get(dono=admin, nome="vendedor").papel == Papel.VENDEDOR

    def test_o_financeiro_nao_tem_papel(self):
        """Ele não é comprador nem vendedor — abre telas, não carrega
        natureza."""
        from contas.models import Perfil
        from contas.perfis_de_fabrica import semear_para

        admin = _admin("b@x.com")
        semear_para(admin)
        assert Perfil.objects.get(dono=admin, nome="financeiro").papel == ""

    def test_sao_copias_e_nao_compartilhados(self):
        """Duas contas, dois "Vendedor" — e editar um não toca no outro."""
        from contas.models import Perfil
        from contas.perfis_de_fabrica import semear_para

        a, b = _admin("c@x.com"), _admin("d@x.com")
        semear_para(a)
        semear_para(b)
        assert Perfil.objects.filter(nome="vendedor").count() == 2

    def test_semear_duas_vezes_nao_duplica(self):
        from contas.models import Perfil
        from contas.perfis_de_fabrica import semear_para

        admin = _admin("e@x.com")
        semear_para(admin)
        assert semear_para(admin) == 0
        assert Perfil.objects.filter(dono=admin, nome="vendedor").count() == 1

    def test_nenhum_de_fabrica_carrega_permissao_de_sistema(self):
        """Se um deles trouxesse, a conta nova nasceria com o teto furado."""
        from contas.models import Perfil
        from contas.permissoes import E_DE_SISTEMA
        from contas.perfis_de_fabrica import semear_para

        admin = _admin("f@x.com")
        semear_para(admin)
        for perfil in Perfil.objects.filter(dono=admin):
            for permissao in perfil.permissoes.all():
                assert not any(permissao.codename.startswith(f"{p}_")
                               for p in E_DE_SISTEMA)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_perfis_de_fabrica.py -q`
Expected: FAIL

- [ ] **Step 3: Implementar**

```python
# contas/perfis_de_fabrica.py
"""Os perfis que toda conta nova recebe, prontos para usar.

**São cópias por conta, e não perfis compartilhados.** O Admin edita os dele —
um perfil compartilhado e editável mudaria o "Vendedor" de todas as contas de
uma vez, e a conta que não pediu a mudança descobriria isso pelo suporte.

O custo dessa escolha, dito: melhorar o "Vendedor" de fábrica não propaga para
quem já existe. É o mesmo buraco do nível, e a spec de 02/09 o nomeia — falta
um `manage.py reaplicar_perfis`.
"""

from __future__ import annotations

from .models import Papel

__all__ = ["DE_FABRICA", "semear_para"]

#: `(nome, rótulo, papel, permissões)`. As permissões são ditas no vocabulário
#: do núcleo (`modulo.acao`), como em `contas/fabrica.py`.
DE_FABRICA: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("comprador", "Comprador", Papel.COMPRADOR,
     ("catalogo.ver", "orcamentos.ver")),
    ("vendedor", "Vendedor", Papel.VENDEDOR,
     ("catalogo.ver", "catalogo.editar",
      "orcamentos.ver", "orcamentos.acompanhar")),
    # Sem papel: ele abre telas, não carrega natureza. Não é comprador nem
    # vendedor, e a maioria dos perfis de um cliente é assim.
    ("financeiro", "Financeiro", "",
     ("orcamentos.ver", "orcamentos.acompanhar")),
)


def semear_para(admin) -> int:
    """Cria os perfis de fábrica que esta conta ainda não tem. Devolve quantos.

    Idempotente: rodar de novo não duplica e **não mexe** no que já existe —
    o Admin pode ter editado o "Vendedor" dele, e uma segunda passada não pode
    desfazer isso.
    """
    from django.contrib.auth.models import Permission

    from .models import Perfil

    existentes = set(
        Perfil.objects.filter(dono=admin).values_list("nome", flat=True))
    criados = 0
    for nome, rotulo, papel, permissoes in DE_FABRICA:
        if nome in existentes:
            continue
        perfil = Perfil.objects.create(
            dono=admin, nome=nome, rotulo=rotulo, papel=papel)
        perfil.permissoes.set(Permission.objects.filter(
            codename__in=[p.replace(".", "_") for p in permissoes]))
        criados += 1
    return criados
```

- [ ] **Step 4: Chamar quando um Admin nasce**

Em `contas/views_usuarios.py::_acao_criar`, dentro do `atomic()`: se o nível
gravado for `ADMIN`, chamar `semear_para(novo)`.

- [ ] **Step 5: Suíte e mutação**

Mutação: faça `semear_para` sobrescrever as permissões de um perfil existente
e confirme que `test_semear_duas_vezes_nao_duplica` fica vermelho.

- [ ] **Step 6: Commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: toda conta nova nasce com Comprador, Vendedor e Financeiro

São cópias por conta, e não perfis compartilhados: o Admin edita os dele, e um
perfil compartilhado e editável mudaria o \"Vendedor\" de todas as contas de
uma vez — a conta que não pediu a mudança descobriria pelo suporte.

O custo está escrito no módulo: melhorar o de fábrica não propaga para quem já
existe."
```

---

### Task 10: Os planos, preparados e desligados

**Files:**
- Create: `contas/planos.py`
- Modify: `contas/models.py` (`Usuario.plano`)
- Modify: `plataforma/views_empresa.py`, `contas/views_usuarios.py`
- Test: `tests/test_planos.py`

**Interfaces:**
- Produces: `contas.planos.cabe_mais_uma_empresa(conta) -> str | None` e
  `cabe_mais_um_usuario(conta) -> str | None` — devolvem a frase da recusa ou
  `None`.

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_planos.py
"""Os limites por plano, prontos e desligados.

A cobrança não existe ainda. O que existe é o LUGAR onde ela vai encostar: uma
função só, chamada pelas duas telas que criam, respondendo sempre que sim.
Quando a cobrança entrar, é essa função que muda — e as telas já estarão
chamando.
"""

import pytest


def _conta(plano=""):
    from django.contrib.auth import get_user_model
    from contas.models import Nivel

    return get_user_model().objects.create_user(
        email=f"conta-{plano or 'sem'}@x.com", nome="Conta", password="x",
        nivel=Nivel.ADMIN, plano=plano)


@pytest.mark.django_db
class TestOsLimites:
    def test_sem_plano_nao_ha_limite(self):
        """Hoje ninguém tem plano, e o produto não pode parar de funcionar
        por causa de uma cobrança que ainda não existe."""
        from contas.planos import cabe_mais_uma_empresa

        assert cabe_mais_uma_empresa(_conta()) is None

    def test_o_limite_conta_usuarios_ALEM_do_dono(self):
        """5 usuários = o dono mais 5 logins. O dono não ocupa vaga — é o que
        a maioria dos SaaS faz, e evita "paguei 5 e só posso pôr 4"."""
        from django.contrib.auth import get_user_model
        from contas.models import Nivel
        from contas.planos import PLANOS, cabe_mais_um_usuario

        conta = _conta("prata")
        limite = PLANOS["prata"].usuarios
        Usuario = get_user_model()
        for i in range(limite):
            Usuario.objects.create_user(
                email=f"u{i}@x.com", nome=f"U{i}", password="x",
                nivel=Nivel.USUARIO, dono=conta)
        recusa = cabe_mais_um_usuario(conta)
        assert recusa is not None and str(limite) in recusa

    def test_a_frase_diz_o_plano_e_o_limite(self):
        """Recusa que não diz o número manda a pessoa adivinhar quanto ela
        comprou."""
        from contas.planos import PLANOS, cabe_mais_uma_empresa
        from plataforma.models import Empresa

        conta = _conta("prata")
        for i in range(PLANOS["prata"].empresas):
            Empresa.objects.create(razao_social=f"E{i}", dono=conta)
        recusa = cabe_mais_uma_empresa(conta)
        assert "Prata" in recusa and str(PLANOS["prata"].empresas) in recusa
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_planos.py -q`
Expected: FAIL

- [ ] **Step 3: Implementar**

```python
# contas/planos.py
"""Quanto cabe em cada plano.

**Preparado e desligado.** A cobrança não existe; o que existe é o lugar onde
ela vai encostar. As duas telas que criam já chamam estas funções, e hoje elas
respondem sempre que sim para quem não tem plano — o produto não pode parar de
funcionar por causa de uma cobrança que ainda não foi feita.

Declarado em código, na forma dos parâmetros que já existem: mudar um limite é
mudar uma linha e subir a imagem, e vale nas sessenta instalações de uma vez.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PLANOS", "Plano", "cabe_mais_um_usuario", "cabe_mais_uma_empresa"]


@dataclass(frozen=True)
class Plano:
    rotulo: str
    empresas: int
    #: **Além do dono.** O Admin não ocupa vaga: 5 usuários são 6 logins.
    usuarios: int


PLANOS: dict[str, Plano] = {
    "prata": Plano("Prata", empresas=1, usuarios=5),
    "ouro": Plano("Ouro", empresas=5, usuarios=25),
}


def _plano_de(conta) -> "Plano | None":
    if conta is None:
        return None
    return PLANOS.get(getattr(conta, "plano", "") or "")


def cabe_mais_uma_empresa(conta) -> "str | None":
    """A frase da recusa, ou `None` quando cabe.

    Devolve a frase e não um booleano pelo mesmo motivo de
    `contas.perfis.pode_remover`: a tela precisa dizer o motivo, e dois lugares
    escrevendo a mesma frase divergiriam com o tempo.
    """
    plano = _plano_de(conta)
    if plano is None:
        return None
    from plataforma.models import Empresa

    quantas = Empresa.objects.filter(dono=conta).count()
    if quantas < plano.empresas:
        return None
    return (f"O plano {plano.rotulo} permite {plano.empresas} "
            f"empresa{'s' if plano.empresas > 1 else ''}, e esta conta já tem "
            f"{quantas}.")


def cabe_mais_um_usuario(conta) -> "str | None":
    plano = _plano_de(conta)
    if plano is None:
        return None
    quantos = conta.subordinados.count()
    if quantos < plano.usuarios:
        return None
    return (f"O plano {plano.rotulo} permite {plano.usuarios} usuários além "
            f"do dono, e esta conta já tem {quantos}.")
```

E a coluna:

```python
# contas/models.py, dentro de Usuario
plano = models.CharField(
    "plano", max_length=20, blank=True, default="",
    help_text="Só faz sentido no Admin. Vazio significa sem limite.")
```

- [ ] **Step 4: Chamar nas duas telas**

`plataforma/views_empresa.py::_acao_criar` e
`contas/views_usuarios.py::_acao_criar`, antes de gravar:

```python
recusa = cabe_mais_uma_empresa(conta_de(request.usuario))
if recusa:
    return _desenhar(request, erro=recusa)
```

- [ ] **Step 5: Suíte e commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: os limites por plano, prontos e desligados

A cobrança não existe. O que existe é o lugar onde ela vai encostar: uma
função só, chamada pelas duas telas que criam, respondendo sempre que sim para
quem não tem plano. Quando a cobrança entrar, é essa função que muda.

O limite conta usuários ALÉM do dono: 5 usuários são 6 logins."
```

---

### Task 11: O GUID nas URLs desta fatia

**Files:**
- Modify: `plataforma/urls.py`, `contas/urls.py`
- Modify: `plataforma/views_empresa.py`, `contas/views_perfil.py`
- Test: `tests/test_url_por_guid.py`

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_url_por_guid.py
"""As rotas desta fatia falam GUID.

Um link com `/empresa/3` diz que a instalação tem três clientes. Não é
vazamento de dado, é vazamento de TAMANHO — e num produto vendido por
assinatura isso aparece em captura de tela, em suporte e em demonstração.

As sete rotas do catálogo seguem com inteiro até o catálogo ser refeito. A
coluna já está lá, esperando.
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_a_rota_da_senha_do_banco_usa_guid(cliente_admin, db):
    from plataforma.models import Empresa

    empresa = Empresa.objects.first()
    url = reverse("empresa_senha", args=[empresa.guid])
    assert str(empresa.guid) in url
    assert f"/{empresa.pk}/" not in url
    assert cliente_admin.get(url).status_code == 200


@pytest.mark.django_db
def test_o_id_inteiro_deixa_de_abrir(cliente_admin, db):
    """A rota velha não pode continuar valendo em paralelo: duas portas para o
    mesmo recurso são duas chances de uma delas esquecer a checagem."""
    from plataforma.models import Empresa

    empresa = Empresa.objects.first()
    assert cliente_admin.get(f"/empresa/{empresa.pk}/senha").status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `... -m pytest tests/test_url_por_guid.py -q`
Expected: FAIL

- [ ] **Step 3: Implementar**

```python
# plataforma/urls.py
path("empresa/<uuid:guid>/senha", views_empresa.senha_do_banco,
     name="empresa_senha"),
```

```python
# contas/urls.py
path("avatar/<uuid:guid>", views_perfil.avatar, name="avatar"),
```

As views trocam `filter(pk=pk)` por `filter(guid=guid)`; `contas/backend.py`
troca `reverse("avatar", args=[usuario.pk])` por `args=[usuario.guid]`.

- [ ] **Step 4: Suíte e commit**

```bash
git add -A && git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: as rotas de empresa e avatar falam GUID

Um link com \`/empresa/3\` diz que a instalação tem três clientes. Não é
vazamento de dado, é vazamento de tamanho — e num produto de assinatura isso
aparece em captura de tela, em suporte e em demonstração.

As sete rotas do catálogo seguem com inteiro até o catálogo ser refeito. A
coluna já está lá."
```

---

## Fecho

Depois da Task 11:

- [ ] Rodar a suíte inteira e conferir o número final
- [ ] `manage.py makemigrations --check --dry-run` → "No changes detected"
- [ ] `manage.py check --deploy` → só os dois avisos de HSTS já conhecidos
- [ ] Atualizar `CLAUDE.md` §7: a hierarquia deixou de ser "o que ainda não
      está definido" e passou a ser o que a spec de 02/09 descreve
- [ ] Atualizar `README.md`: o login é por e-mail

## Fora deste plano, e nomeado

- `manage.py reaplicar_perfis` — mudar a regra de um perfil não reescreve quem
  já existe
- Autocadastro, cobrança e confirmação por e-mail
- Escopo por filial
- As sete rotas do catálogo com id inteiro
