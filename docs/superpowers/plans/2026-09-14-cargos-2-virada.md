# Plano 2 de 3: Cargos e alocações — a virada, e o fim do Perfil

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A permissão e o que cada pessoa enxerga passam a vir do CARGO da alocação dela no lugar em que está trabalhando; os dados de hoje migram para cargos e alocações; `Perfil`, `Papel`, `Filial.usuarios`, a tela de Perfis e os níveis VENDEDOR/COMPRADOR saem do sistema.

**Architecture:** Uma peça nova, `contas/lugar.py`, responde "onde a pessoa está e o que ela pode ali" a partir de `Alocacao`. `comum.sessao.usuario_da_sessao` passa a devolver o `User` com as permissões do lugar (titular e MW5 continuam com as de `contas/fabrica.py`), e `plataforma.contexto` passa a ler as alocações para empresa e filial. `e_cliente` e `alcance` do cargo substituem o papel do perfil. Por fora, `pode()`, `exigir_permissao` e `do_contexto` continuam sendo as mesmas portas.

**Tech Stack:** Django 5.2, Python 3.13, Postgres 16, pytest + pytest-django, `django-test-migrations`.

**Spec:** `docs/superpowers/specs/2026-09-14-cargos-e-alocacoes-design.md`

## O que mudou em relação ao plano 1

O plano 1 dividia o trabalho em três: modelo, virada, telas e limpeza. Em
14/09/2026 o João disse: **"Não tem mais perfil, é tudo cargo agora."** Por
isso este plano leva junto tudo o que é preciso para o Perfil sair: a tela
Alocações no cadastro de usuário (sem ela, ninguém teria como dar cargo a
alguém) e a limpeza de `Perfil`, `Papel` e dos níveis antigos.

**Fica para o plano 3:** várias empresas por conta. Isso inclui tirar a trava
`uma_empresa_por_conta`, o botão "Nova empresa", `EMPRESA_CRIADA` e o seletor
de empresa para o titular. Neste plano uma conta continua tendo uma empresa, e
todo o código novo já trata a empresa como uma entre várias.

## Decisões que o spec não respondia (rulings)

- **R1 — Os perfis globais da `contas/0006`.** Eles têm `dono=None`, nome
  "comprador" ou "vendedor" e nenhuma permissão, e existem nas instalações
  reais. Na migração viram o cargo de fábrica **Cliente** ou **Vendedor** da
  conta de cada pessoa, sem mexer nas permissões do cargo. A regra "as
  permissões do perfil prevalecem" do spec vale só para perfil **com**
  permissões. Um perfil de papel sem permissão era só um marcador, porque a
  permissão vinha do nível. Aplicar a regra a ele zeraria o que o cliente
  vê.
- **R2 — O perfil chamado "comprador" vira "cliente"** ("Comprador passa a se
  chamar Cliente", spec D4), inclusive nos perfis de conta.
- **R3 — Pessoa cujos perfis viram cargos diferentes na mesma empresa: a
  migração para com erro e lista quem é.** Uma alocação por lugar tem um
  cargo só. Escolher um dos cargos seria tirar acesso em silêncio.
- **R4 — Permissão direta.** A migração só para por permissão direta que vá
  além do que o nível da pessoa já dava (`catalogo.ver` e `orcamentos.ver`)
  e que o cargo novo não cobre. As permissões do nível foram gravadas por
  `contas.fabrica.aplicar` e não são concessão de ninguém. Depois de migrar,
  as permissões diretas de quem não é titular são apagadas.
- **R5 — Pessoa sem conta** (`dono` nulo e nível abaixo de titular): não
  ganha alocação e não bloqueia a migração. Ela não alcançava empresa
  nenhuma antes.
- **R6 — Quem tem `usuarios.editar` sem ser titular** administra uma pessoa
  só se TODAS as alocações dela forem lugares que ele alcança, com cargos
  que ele poderia dar ali (`contas.lugar.pode_administrar`). Sem essa regra,
  um Gerente trocaria a senha de um Supervisor e entraria como ele. Pessoa
  sem alocação só é administrada pelo titular e pela MW5.
- **R7 — "Poder dar um cargo" compara permissões E alcance.** Supervisor e
  Gerente de fábrica têm as mesmas permissões e diferem só no alcance
  (empresa × filial). Comparando só permissões, um Gerente criaria um
  Supervisor e passaria a ver a empresa inteira pela mão de outro.
- **R8 — O cabeçalho tem dois níveis** quando há o que escolher. A empresa
  aparece quando a pessoa alcança mais de uma (hoje, só a MW5), e a filial
  quando ela alcança mais de uma na empresa atual. O formulário do
  `ContextSwitcher` é um só e envia os dois selects para uma `action`; por
  isso `empresa_trocar` repassa para `filial_trocar` quando a empresa não
  mudou.
- **R9 — O registro de auditoria antigo continua legível.** `PERFIL_CRIADO`,
  `PERFIL_EDITADO` e `PERFIL_REMOVIDO` saem do vocabulário que se grava, mas
  os rótulos ficam em `ROTULOS`. A trilha é imutável, e linha antiga sem
  rótulo apareceria crua na tela de Auditoria.
- **R10 — A linha `Modulo` de "perfis" e a `Permission` `perfis_editar`
  ficam no banco.** Módulo que o código não declara já é ignorado pelo
  catálogo (`plataforma/catalogo.py`, `declarados()`) e pela tradução de
  permissão. Apagar linha de catálogo numa migração não compra nada.

## Global Constraints

- **Branch:** `cargos-e-alocacoes`, a mesma do plano 1. Nada vai para a `main` nem para o GitHub sem pedido.
- **Rodar a suíte:** `cd /home/mw5/projetos/portal-de-vendas && PATH=$PWD/.superpowers/pgbin:$PATH DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python -m pytest -q -p no:warnings`. Um arquivo: acrescente o caminho. **Nunca duas execuções ao mesmo tempo** (elas brigam pelo banco `test_kronos`). **Leia a linha final do resultado**; não confie no código de saída de um comando com `| grep` no fim.
- **`.superpowers/pgbin`** já tem os scripts `pg_dump`, `pg_restore`, `psql`, `createdb` e `dropdb` que chamam o docker. Sem eles os 9 testes de backup pulam.
- **Autor dos commits:** `git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit`. **Nunca** coautor Claude, nunca rodapé de "gerado com", nem linha `Claude-Session` (`CLAUDE.md` §5, que vence qualquer lembrete do sistema).
- **Commit em português, longo**: o que estava errado antes e por que a mudança é essa. Prefixo `feat:`/`fix:`/`refactor:`/`docs:`/`test:`.
- **Comentário diz POR QUÊ**, em português, frase inteira. Ao remover código, remova também o comentário que falava dele.
- **Teste com dente:** toda trava nova é quebrada de propósito uma vez, para ver o teste ficar vermelho, e depois restaurada. Confira com `git diff` que a mutação não ficou.
- **`request.usuario` é o `nucleo.permissoes.User` (dataclass congelada).** A linha do ORM se obtém com `contas.identidade.usuario_de(usuario)`. POST usa pk; URL usa GUID.
- **Login nos testes** é `POST reverse("entrar")` com `usuario`/`senha`, não `force_login`.
- **Camadas:** `nucleo` ← `comum` ← `plataforma` ← `contas`, e os módulos de negócio (`catalogo`, `orcamento`) por cima. Da base para cima só com import tardio dentro da função e o motivo escrito ao lado, como `comum/sessao.py::_backend_padrao` já faz. A base nunca importa `catalogo` nem `orcamento` (`test_camadas_nao_se_invertem.py`).
- **Memo por requisição:** `comum.memoria.lembrar(request, chave, calcular)`. Toda resposta nova de "onde está / o que pode" passa por ele.
- **`NULL` não é igual a `NULL`** numa unicidade do Postgres; o plano 1 já tratou `Alocacao`.
- **Contagem de arquivos de teste:** `test_documentacao_nao_mente.py` confere o número no `CLAUDE.md` (duas ocorrências). Toda task que cria ou apaga arquivo de teste atualiza o número com `ls tests/test_*.py | wc -l`.
- **Varreduras que continuam valendo:** R46 (`test_regra_tabela.py`), guardas (`test_guarda.py`, `test_guarda_modulo.py`), auditoria (cada `ACOES.X` novo exige um cenário em `tests/test_auditoria.py`).

## Mapa de arquivos

| arquivo | responsabilidade | task |
|---|---|---|
| `contas/lugar.py` (novo) | lugares alcançados, alocação vigente, permissões do cargo, cliente e alcance atuais, clientes alcançados, `pode_dar`, `pode_administrar`, `com_permissoes_do_lugar` | 1, 2, 3 |
| `contas/backend.py` | `traduzir`; `permissoes_de` só com as diretas; MEMBRO nasce sem permissão | 2 |
| `comum/sessao.py` | `identidade_da_sessao` (quem é) × `usuario_da_sessao` (quem é + o que pode no lugar) | 2 |
| `plataforma/contexto.py` | empresa e filial pelas alocações; filial dentro da empresa atual; dois níveis no cabeçalho | 2, 4 |
| `contas/alcance.py` | `empresas_alcancadas`/`empresa_de` pela alocação; `pessoas_alcancadas` com R6; sai `compradores_alcancados` | 2, 3, 5 |
| `tests/conftest.py` | `alocar`, `cargo_com`; `dar_acesso`/`dar_papel` passam a alocar | 2, 7 |
| `catalogo/preco.py`, `catalogo/views_vitrine.py`, `catalogo/views_produto.py` | `e_cliente` e `clientes_alcancados` no lugar do papel e da carteira | 3 |
| `orcamento/visibilidade.py`, `orcamento/views.py` | orçamentos pelo alcance; carrinho na filial atual | 3 |
| `contas/views_usuarios.py` | sai a carteira (3); entra o bloco Alocações, saem Perfis e o painel de nível (5) | 3, 5 |
| `contas/static/contas/alocacoes.js` (novo) | "+ Acrescentar alocação" | 5 |
| `plataforma/site.py`, `plataforma/views_empresa_contexto.py`, `plataforma/views_filial.py` | seletor de filial | 4 |
| `comum/auditoria.py` | `ALOCACAO_CRIADA`, `ALOCACAO_REMOVIDA` | 5 |
| `contas/migrations/0017_perfis_viram_cargos.py` (nova) | a migração dos dados | 6 |
| `plataforma/migrations/0008_filial_tem_empresa.py`, `orcamento/migrations/0006_orcamento_filial_obrigatoria.py` (novas) | as colunas viram `NOT NULL` | 6 |
| `README.md` | a conferência antes de atualizar | 6 |
| `contas/migrations/0018_o_perfil_sai.py`, `plataforma/migrations/0009_filial_usuarios_sai.py` (novas) | saem `Perfil` e `Filial.usuarios`; `Nivel` com MEMBRO | 7 |
| `contas/models.py`, `contas/fabrica.py`, `contas/modulo.py`, `contas/urls.py`, `contas/apps.py`, `plataforma/apps.py`, `contas/caixas_de_permissao.py`, `contas/views_cargos.py` | limpeza | 7 |
| apagados: `contas/papel.py` (3), `contas/perfis.py`, `contas/views_perfis.py` (7), e os testes que só falavam deles | limpeza | 3, 7 |
| `CLAUDE.md` §7 | a hierarquia nova | 7 |

---

### Task 1: `contas/lugar.py` — onde a pessoa está e o que pode ali (ainda sem ligar)

**Files:**
- Create: `contas/lugar.py`
- Test: `tests/test_lugar.py`
- Modify: `contas/backend.py` (extrair `traduzir`)
- Modify: `CLAUDE.md` (contagem de testes)

**Interfaces:**
- Produces (todas recebem a linha do ORM `Usuario`, nunca a dataclass):
  - `empresas_da_pessoa(pessoa: Usuario | None) -> QuerySet[Empresa]`
  - `filiais_da_pessoa(pessoa: Usuario | None, empresa: Empresa | None) -> QuerySet[Filial]` (só ATIVAS)
  - `alocacao_vigente(pessoa, empresa, filial) -> Alocacao | None`
  - `permissoes_do_cargo(cargo: Cargo) -> frozenset[str]` (vocabulário `modulo.acao`)
  - `permissoes_em(pessoa, empresa, filial) -> frozenset[str]`
  - `alcance_em(pessoa, empresa, filial) -> str` (um valor de `Alcance`)
  - `pode_dar(editor, empresa, filial, cargo) -> bool`
  - `pode_administrar(editor, alvo) -> bool`
  - Em `contas/backend.py`: `traduzir(codenames: Iterable[str]) -> frozenset[str]`

- [ ] **Step 1: Extrair `traduzir` de `permissoes_de`**

Em `contas/backend.py`, mova o laço que converte codename em `modulo.acao`
(com o filtro de `codenames_autogerados` e de `chaves` declaradas) para uma
função pública. Assim o cargo reaproveita o mesmo filtro, e uma segunda
tradução divergiria na primeira permissão nova. `permissoes_de` passa a ser:

```python
def traduzir(codenames) -> frozenset[str]:
    """Codenames de `Permission` do app de módulos -> `modulo.acao`.

    Uma tradução só, usada pela permissão direta e pela do cargo: duas
    tradutoras com o mesmo filtro divergiriam no dia em que o filtro mudasse
    numa só — e o filtro é o que impede `mw5_aparencia` de virar acesso.
    """
    from django.apps import apps as apps_registrados

    from plataforma.declaracao import declarados

    codenames_autogerados = {
        f"{verbo}_{modelo._meta.model_name}"
        for modelo in apps_registrados.get_app_config(APP_DOS_MODULOS).get_models()
        for verbo in modelo._meta.default_permissions
    }
    chaves = {spec.chave for spec in declarados()}
    concedidas: set[str] = set()
    for codename in codenames:
        if codename in codenames_autogerados:
            continue
        modulo, separador, acao = codename.partition("_")
        if not separador or modulo not in chaves:
            continue
        concedidas.add(f"{modulo}.{acao}")
    return frozenset(concedidas)
```

Mantenha os comentários de POR QUÊ que já estavam no laço (autogeradas, sem
sublinhado, módulo inexistente), agora dentro de `traduzir`. `permissoes_de`
continua com a mesma consulta (perfis + diretas; quem muda isso é a Task 2) e
termina em `return traduzir(permissoes)`. Acrescente `"traduzir"` ao
`__all__`.

- [ ] **Step 2: Rodar `tests/test_contas_backend.py` e `tests/test_permissoes_de_modulo.py`**

Expected: PASS. É refatoração pura.

- [ ] **Step 3: Escrever os testes de `contas/lugar.py`**

`tests/test_lugar.py`:

```python
"""Onde a pessoa está, e o que ela pode ali (spec 2026-09-14, "Onde a pessoa
está"). Funções puras sobre `Alocacao`; quem as liga à requisição é a Task 2.
"""

import pytest

from contas.lugar import (
    alcance_em, alocacao_vigente, empresas_da_pessoa, filiais_da_pessoa,
    permissoes_do_cargo, permissoes_em, pode_administrar, pode_dar,
)
from contas.models import Alcance, Alocacao, Cargo, Nivel, Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def conta():
    """Titular, empresa com Matriz + Norte + Sul, e os cargos de fábrica."""
    from plataforma.models import Empresa, Filial

    titular = Usuario.objects.create_user(
        email="dono-lugar@teste.com", password="x", nivel=Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    norte = Filial.objects.create(empresa=empresa, nome="Norte", apelido="Norte", ordem=5)
    sul = Filial.objects.create(empresa=empresa, nome="Sul", apelido="Sul", ordem=6)
    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}
    return titular, empresa, norte, sul, cargos


def _membro(titular, login):
    return Usuario.objects.create_user(
        email=f"{login}@teste.com", password="x", nivel=Nivel.COMPRADOR,
        dono=titular)


class TestOsLugares:
    def test_pessoa_sem_alocacao_nao_alcanca_nada(self, conta):
        titular, empresa, *_ = conta
        ana = _membro(titular, "ana")
        assert list(empresas_da_pessoa(ana)) == []
        assert list(filiais_da_pessoa(ana, empresa)) == []

    def test_alocacao_na_filial_abre_so_ela(self, conta):
        titular, empresa, norte, sul, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert list(empresas_da_pessoa(ana)) == [empresa]
        assert list(filiais_da_pessoa(ana, empresa)) == [norte]

    def test_alocacao_na_empresa_inteira_abre_todas_as_ativas(self, conta):
        from plataforma.models import Filial

        titular, empresa, norte, sul, cargos = conta
        sul.ativa = False
        sul.save()
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa,
                                cargo=cargos["supervisor"])
        nova = Filial.objects.create(empresa=empresa, nome="Leste", apelido="Leste", ordem=7)
        alcancadas = set(filiais_da_pessoa(ana, empresa))
        assert norte in alcancadas and nova in alcancadas
        assert sul not in alcancadas

    def test_titular_alcanca_as_filiais_da_empresa_dele_e_nao_as_de_outra(self, conta):
        from plataforma.models import Empresa

        titular, empresa, norte, *_ = conta
        outro = Usuario.objects.create_user(
            email="outro-lugar@teste.com", password="x", nivel=Nivel.TITULAR)
        beta = Empresa.objects.create(razao_social="Beta Ltda", dono=outro)
        assert norte in set(filiais_da_pessoa(titular, empresa))
        assert list(filiais_da_pessoa(titular, beta)) == []

    def test_pessoa_que_mudou_de_conta_perde_as_alocacoes_antigas(self, conta):
        titular, empresa, norte, _s, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        outro = Usuario.objects.create_user(
            email="outro-conta@teste.com", password="x", nivel=Nivel.TITULAR)
        ana.dono = outro
        ana.save(update_fields=["dono"])
        assert list(empresas_da_pessoa(ana)) == []
        assert alocacao_vigente(ana, empresa, norte) is None


class TestAMaisEspecificaGanha:
    def test_vendedor_na_norte_e_gerente_da_empresa_e_vendedor_na_norte(self, conta):
        titular, empresa, norte, sul, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=cargos["supervisor"])
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert alocacao_vigente(ana, empresa, norte).cargo.nome == "vendedor"
        assert alocacao_vigente(ana, empresa, sul).cargo.nome == "supervisor"
        # As duas não somam: na Norte ela não edita catálogo.
        assert "catalogo.editar" not in permissoes_em(ana, empresa, norte)
        assert "catalogo.editar" in permissoes_em(ana, empresa, sul)

    def test_filial_de_outra_empresa_nao_escolhe_alocacao(self, conta):
        from plataforma.models import Empresa, Filial

        titular, empresa, norte, _s, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=cargos["cliente"])
        outro = Usuario.objects.create_user(
            email="outro-fil@teste.com", password="x", nivel=Nivel.TITULAR)
        beta = Empresa.objects.create(razao_social="Beta Ltda", dono=outro)
        alheia = Filial.objects.create(empresa=beta, nome="X", apelido="X", ordem=9)
        assert alocacao_vigente(ana, empresa, alheia).cargo.nome == "cliente"


class TestAsPermissoes:
    def test_cargo_traduz_para_o_vocabulario_do_nucleo(self, conta):
        *_, cargos = conta
        assert permissoes_do_cargo(cargos["cliente"]) == frozenset(
            {"catalogo.ver", "orcamentos.ver"})

    def test_membro_sem_alocacao_nao_pode_nada(self, conta):
        titular, empresa, norte, *_ = conta
        assert permissoes_em(_membro(titular, "ana"), empresa, norte) == frozenset()

    def test_titular_tem_as_de_fabrica_so_na_empresa_dele(self, conta):
        from contas.fabrica import aplicar
        from plataforma.models import Empresa

        titular, empresa, norte, *_ = conta
        aplicar(titular, Nivel.TITULAR)
        assert "usuarios.editar" in permissoes_em(titular, empresa, norte)
        outro = Usuario.objects.create_user(
            email="outro-perm@teste.com", password="x", nivel=Nivel.TITULAR)
        beta = Empresa.objects.create(razao_social="Beta Ltda", dono=outro)
        assert permissoes_em(titular, beta, None) == frozenset()

    def test_alcance_do_titular_e_a_empresa_e_do_membro_e_o_do_cargo(self, conta):
        titular, empresa, norte, _s, cargos = conta
        ana = _membro(titular, "ana")
        Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert alcance_em(titular, empresa, norte) == Alcance.EMPRESA
        assert alcance_em(ana, empresa, norte) == Alcance.FILIAL
        assert alcance_em(_membro(titular, "bia"), empresa, norte) == Alcance.PROPRIOS


class TestEscalada:
    def _gerente_na_norte(self, conta):
        titular, empresa, norte, _s, cargos = conta
        gil = _membro(titular, "gil")
        Alocacao.objects.create(pessoa=gil, empresa=empresa, filial=norte,
                                cargo=cargos["gerente"])
        return gil

    def test_gerente_da_vendedor_na_filial_dele(self, conta):
        _t, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        assert pode_dar(gil, empresa, norte, cargos["vendedor"])

    def test_gerente_nao_aloca_fora_da_filial_dele(self, conta):
        _t, empresa, _n, sul, cargos = conta
        gil = self._gerente_na_norte(conta)
        assert not pode_dar(gil, empresa, sul, cargos["vendedor"])
        assert not pode_dar(gil, empresa, None, cargos["vendedor"])

    def test_gerente_nao_cria_supervisor_mesmo_com_as_mesmas_permissoes(self, conta):
        """R7: a diferença entre os dois é o ALCANCE."""
        _t, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        assert not pode_dar(gil, empresa, norte, cargos["supervisor"])

    def test_vendedor_nao_aloca_ninguem(self, conta):
        titular, empresa, norte, _s, cargos = conta
        vera = _membro(titular, "vera")
        Alocacao.objects.create(pessoa=vera, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert not pode_dar(vera, empresa, norte, cargos["cliente"])

    def test_cargo_de_outra_conta_nunca(self, conta):
        titular, empresa, norte, *_ = conta
        outro = Usuario.objects.create_user(
            email="outro-esc@teste.com", password="x", nivel=Nivel.TITULAR)
        alheio = Cargo.objects.get(conta=outro, nome="cliente")
        assert not pode_dar(titular, empresa, norte, alheio)

    def test_titular_da_qualquer_cargo_da_conta(self, conta):
        titular, empresa, _n, _s, cargos = conta
        assert pode_dar(titular, empresa, None, cargos["supervisor"])

    def test_gerente_nao_administra_supervisor_nem_a_si_mesmo(self, conta):
        titular, empresa, norte, _s, cargos = conta
        gil = self._gerente_na_norte(conta)
        sara = _membro(titular, "sara")
        Alocacao.objects.create(pessoa=sara, empresa=empresa, cargo=cargos["supervisor"])
        vera = _membro(titular, "vera")
        Alocacao.objects.create(pessoa=vera, empresa=empresa, filial=norte,
                                cargo=cargos["vendedor"])
        assert pode_administrar(gil, vera)
        assert not pode_administrar(gil, sara)
        assert not pode_administrar(gil, gil)
        assert not pode_administrar(gil, titular)

    def test_pessoa_sem_alocacao_so_o_titular_administra(self, conta):
        titular, *_ = conta
        gil = self._gerente_na_norte(conta)
        nova = _membro(titular, "nova")
        assert pode_administrar(titular, nova)
        assert not pode_administrar(gil, nova)
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `... -m pytest -q -p no:warnings tests/test_lugar.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'contas.lugar'`.

- [ ] **Step 5: Escrever `contas/lugar.py`**

```python
"""Onde a pessoa está, e o que ela pode ali.

A mudança que este módulo carrega (spec 2026-09-14, D1 e D9): a permissão
deixou de ser da PESSOA e passou a ser do CARGO da alocação dela NUM LUGAR. A
mesma Ana é Gerente na Centro e Vendedora na Norte, e o que ela pode depende de
onde está trabalhando agora.

**Funções sobre a linha do ORM, e não sobre a requisição.** Quem traduz a
requisição (sessão, empresa e filial atuais) para estas perguntas é a camada de
cima (`com_permissoes_do_lugar` e as funções `*_atual`, Task 2). Separado assim,
cada regra se testa com três linhas de cadastro, sem sessão nem cliente HTTP.

**O titular e a MW5 não têm cargo** (D3). Eles alcançam por serem quem são, e as
permissões deles continuam as de `contas/fabrica.py`. Se o dono dependesse de um
cargo, bastaria editar esse cargo para ele se trancar para fora da própria conta.

**Uma alocação só vale na conta atual da pessoa.** Toda consulta confere
`pessoa.dono_id == empresa.dono_id`. Mudar alguém de conta tem de valer na
requisição seguinte, sem depender de ninguém lembrar de apagar as alocações
antigas.
"""

from __future__ import annotations

from django.db.models import QuerySet

from nucleo.permissoes import User, pode
from plataforma.models import Empresa, Filial

from .backend import permissoes_de, traduzir
from .models import Alcance, Alocacao, Cargo, Nivel, Usuario

__all__ = [
    "alcance_em", "alocacao_vigente", "empresas_da_pessoa", "filiais_da_pessoa",
    "permissoes_do_cargo", "permissoes_em", "pode_administrar", "pode_dar",
]

#: Do menor para o maior. "Poder dar" um cargo exige alcance igual ou menor que
#: o de quem dá (R7).
_TAMANHO_DO_ALCANCE = {Alcance.PROPRIOS: 0, Alcance.FILIAL: 1, Alcance.EMPRESA: 2}


def _ve_tudo(pessoa: Usuario) -> bool:
    return pessoa.is_superuser or pessoa.nivel == Nivel.MASTER


def _e_dono(pessoa: Usuario, empresa: Empresa) -> bool:
    return pessoa.nivel == Nivel.TITULAR and empresa.dono_id == pessoa.pk


def _membro_da_conta(pessoa: Usuario, empresa: Empresa) -> bool:
    return (pessoa.nivel > Nivel.TITULAR and not pessoa.is_superuser
            and pessoa.dono_id is not None and pessoa.dono_id == empresa.dono_id)


def empresas_da_pessoa(pessoa: "Usuario | None") -> "QuerySet[Empresa]":
    """As empresas que a pessoa alcança. MASTER: todas. Titular: as da conta
    dele. Membro: só onde tem alocação, e só na conta atual dele."""
    if pessoa is None or not pessoa.pk:
        return Empresa.objects.none()
    if _ve_tudo(pessoa):
        return Empresa.objects.all()
    if pessoa.nivel == Nivel.TITULAR:
        return Empresa.objects.filter(dono=pessoa)
    if pessoa.dono_id is None:
        return Empresa.objects.none()
    return Empresa.objects.filter(
        dono_id=pessoa.dono_id, alocacoes__pessoa=pessoa).distinct()


def filiais_da_pessoa(pessoa: "Usuario | None",
                      empresa: "Empresa | None") -> "QuerySet[Filial]":
    """As filiais ATIVAS de `empresa` que a pessoa alcança.

    Uma alocação na empresa inteira abre todas as filiais, inclusive as criadas
    depois (D8). Por isso a resposta é uma consulta às filiais da empresa, e não
    uma lista copiada no dia em que a pessoa foi alocada.
    """
    if pessoa is None or empresa is None or not pessoa.pk:
        return Filial.objects.none()
    ativas = Filial.objects.filter(empresa=empresa, ativa=True)
    if _ve_tudo(pessoa) or _e_dono(pessoa, empresa):
        return ativas
    if not _membro_da_conta(pessoa, empresa):
        return ativas.none()
    minhas = Alocacao.objects.filter(pessoa=pessoa, empresa=empresa)
    if minhas.filter(filial__isnull=True).exists():
        return ativas
    return ativas.filter(alocacoes__in=minhas).distinct()


def alocacao_vigente(pessoa, empresa, filial) -> "Alocacao | None":
    """A alocação que vale aqui: a da filial exata, senão a da empresa inteira.

    **A mais específica ganha; as duas não somam.** Quem é Supervisor da empresa
    e Vendedor na Norte é Vendedor quando está na Norte. Somar deixaria o cargo
    menor sem efeito nenhum, e ninguém conseguiria restringir alguém numa filial.
    """
    if pessoa is None or empresa is None or not _membro_da_conta(pessoa, empresa):
        return None
    minhas = Alocacao.objects.select_related("cargo").filter(
        pessoa=pessoa, empresa=empresa)
    if filial is not None and filial.empresa_id == empresa.pk:
        exata = minhas.filter(filial=filial).first()
        if exata is not None:
            return exata
    return minhas.filter(filial__isnull=True).first()


def permissoes_do_cargo(cargo: Cargo) -> frozenset[str]:
    from .backend import APP_DOS_MODULOS

    return traduzir(cargo.permissoes.filter(
        content_type__app_label=APP_DOS_MODULOS).values_list("codename", flat=True))


def permissoes_em(pessoa, empresa, filial) -> frozenset[str]:
    """O que a pessoa pode NESTE lugar.

    Titular: as de fábrica, só dentro da empresa dele. MASTER: as de fábrica em
    qualquer uma. Membro: as do cargo da alocação vigente, ou nenhuma.
    """
    if pessoa is None or empresa is None:
        return frozenset()
    if _ve_tudo(pessoa) or _e_dono(pessoa, empresa):
        return permissoes_de(pessoa)
    vigente = alocacao_vigente(pessoa, empresa, filial)
    return permissoes_do_cargo(vigente.cargo) if vigente else frozenset()


def alcance_em(pessoa, empresa, filial) -> str:
    """Quais registros a pessoa enxerga aqui. Sem alocação, `PROPRIOS`: ver de
    menos se corrige; ver de mais já vazou."""
    if pessoa is not None and empresa is not None and (
            _ve_tudo(pessoa) or _e_dono(pessoa, empresa)):
        return Alcance.EMPRESA
    vigente = alocacao_vigente(pessoa, empresa, filial)
    return vigente.cargo.alcance if vigente else Alcance.PROPRIOS


def pode_dar(editor, empresa, filial, cargo) -> bool:
    """Se `editor` pode alocar alguém com `cargo` neste lugar.

    As três travas do spec ("Quem pode mexer em quê"), conferidas aqui e não na
    tela, para o POST forjado passar pelo mesmo lugar que o formulário:

    1. o lugar é um que o editor alcança; na empresa inteira, só quem alcança a
       empresa inteira;
    2. o editor tem `usuarios.editar` ali e todas as permissões do cargo;
    3. o alcance do cargo não é maior que o do editor (R7).
    """
    if editor is None or empresa is None or cargo is None:
        return False
    if empresa.conta_id is None or cargo.conta_id != empresa.conta_id:
        return False
    if filial is not None and filial.empresa_id != empresa.pk:
        return False
    if _ve_tudo(editor):
        return True
    if editor.nivel == Nivel.TITULAR:
        return _e_dono(editor, empresa)
    if filial is None:
        if not Alocacao.objects.filter(pessoa=editor, empresa=empresa,
                                       filial__isnull=True).exists():
            return False
    elif not filiais_da_pessoa(editor, empresa).filter(pk=filial.pk).exists():
        return False
    retrato = User(id=str(editor.pk), name="",
                   permissions=permissoes_em(editor, empresa, filial))
    if not pode(retrato, "usuarios.editar"):
        return False
    if not all(pode(retrato, p) for p in permissoes_do_cargo(cargo)):
        return False
    return (_TAMANHO_DO_ALCANCE[cargo.alcance]
            <= _TAMANHO_DO_ALCANCE[alcance_em(editor, empresa, filial)])


def pode_administrar(editor, alvo) -> bool:
    """Se `editor` pode editar, trocar a senha, desativar ou remover `alvo`.

    Para quem não é titular (R6): só se TODA alocação do alvo for uma que o
    editor poderia ter dado. Sem isto, um Gerente trocaria a senha de um
    Supervisor e entraria como ele. **Ninguém administra a si mesmo por esta
    porta**, e é isso que impede alguém de editar a própria alocação.
    """
    if editor is None or alvo is None or alvo.is_superuser:
        return False
    if _ve_tudo(editor):
        return True
    if alvo.pk == editor.pk or alvo.nivel <= Nivel.TITULAR:
        return False
    if editor.nivel == Nivel.TITULAR:
        return alvo.dono_id == editor.pk
    if alvo.dono_id is None or alvo.dono_id != editor.dono_id:
        return False
    alocacoes = list(alvo.alocacoes.select_related("empresa", "filial", "cargo"))
    return bool(alocacoes) and all(
        pode_dar(editor, a.empresa, a.filial, a.cargo) for a in alocacoes)
```

Import no topo de `plataforma.models` é o mesmo que `contas/alcance.py` já faz:
`contas` fica acima de `plataforma`.

- [ ] **Step 6: Rodar e ver passar**

Run: `... tests/test_lugar.py tests/test_contas_backend.py`
Expected: PASS.

- [ ] **Step 7: Mutações (uma de cada vez; ver vermelho; desfazer)**

1. Em `alocacao_vigente`, trocar a ordem: procurar primeiro `filial__isnull=True`. Deve falhar `test_vendedor_na_norte_e_gerente_da_empresa_e_vendedor_na_norte`.
2. Em `pode_dar`, apagar a comparação de `_TAMANHO_DO_ALCANCE`. Deve falhar `test_gerente_nao_cria_supervisor_mesmo_com_as_mesmas_permissoes`.
3. Em `_membro_da_conta`, apagar `pessoa.dono_id == empresa.dono_id`. Deve falhar `test_pessoa_que_mudou_de_conta_perde_as_alocacoes_antigas`.
4. Em `pode_administrar`, apagar `alvo.pk == editor.pk or`. Deve falhar `test_gerente_nao_administra_supervisor_nem_a_si_mesmo`.

Confira com `git diff contas/lugar.py` que nenhuma mutação ficou.

- [ ] **Step 8: Contagem no `CLAUDE.md`, suíte inteira, commit**

Atualize "NN arquivos" (duas ocorrências) com `ls tests/test_*.py | wc -l`.
Rode a suíte inteira. Commit `feat(cargos): onde a pessoa está e o que o cargo dela pode ali`, com uma mensagem que diga que as funções ainda não estão ligadas em nada e explique as regras R6 e R7.

---

### Task 2: A virada — a permissão e o lugar vêm da alocação

**Files:**
- Modify: `contas/backend.py`, `comum/sessao.py`, `plataforma/contexto.py`, `contas/alcance.py`, `contas/lugar.py`, `orcamento/visibilidade.py` (comentário do carrinho), `tests/conftest.py`
- Test: `tests/test_virada_do_lugar.py` (novo); reescrever `tests/test_contexto_filial.py`; ajustar os testes que davam permissão direta a quem não é titular

**Interfaces:**
- Consumes: Task 1 inteira.
- Produces:
  - `comum.sessao.identidade_da_sessao(request, backend=None) -> User | None`: quem é, com as permissões que o backend deu (as de fábrica para titular e MW5; nenhuma para membro).
  - `comum.sessao.usuario_da_sessao(request, backend=None) -> User | None`: quem é e o que pode NO LUGAR. Mesma assinatura de hoje.
  - `contas.lugar.com_permissoes_do_lugar(request, user: User) -> User`
  - `plataforma.contexto.filiais_de(user, empresa=None)`: a filial passa a ser DENTRO da empresa (sem `empresa`, usa `empresa_atual`).
  - `tests.conftest.alocar(pessoa, empresa=None, cargo="cliente", filial=None) -> Alocacao`
  - `tests.conftest.cargo_com(empresa, *chaves, nome="cargo-de-teste", alcance="empresa", e_cliente=False) -> Cargo`

- [ ] **Step 1: Escrever os testes da virada**

`tests/test_virada_do_lugar.py`, com login por `POST /entrar`:

```python
"""A permissão vem do cargo da alocação no lugar em que a pessoa está.

Prova, pelo cliente HTTP, as cinco propriedades do spec ("Como se prova"):
sem alocação não vê nada; lugar forjado cai no primeiro permitido; a mais
específica ganha; tirar a alocação vale na requisição seguinte; titular não
depende de cargo.
"""

import pytest
from django.test import Client
from django.urls import reverse

from contas.models import Alocacao, Cargo, Nivel, Usuario
from nucleo.permissoes import pode

pytestmark = pytest.mark.django_db


@pytest.fixture
def conta():
    from contas.fabrica import aplicar
    from plataforma.models import Empresa, Filial

    titular = Usuario.objects.create_user(
        email="dono-virada@teste.com", password="x", nivel=Nivel.TITULAR)
    aplicar(titular, Nivel.TITULAR)
    empresa = Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
    norte = Filial.objects.create(empresa=empresa, nome="Norte", apelido="Norte", ordem=5)
    sul = Filial.objects.create(empresa=empresa, nome="Sul", apelido="Sul", ordem=6)
    cargos = {c.nome: c for c in Cargo.objects.filter(conta=titular)}
    return titular, empresa, norte, sul, cargos


def _entrar(email):
    cliente = Client()
    cliente.post(reverse("entrar"), {"usuario": email, "senha": "x"})
    return cliente


def _membro(titular, login):
    return Usuario.objects.create_user(
        email=f"{login}@teste.com", password="x", nivel=Nivel.COMPRADOR, dono=titular)


def _user_da(cliente):
    """O `User` que a próxima requisição veria, montado como as guardas o montam."""
    from django.test import RequestFactory

    from comum.sessao import usuario_da_sessao

    request = RequestFactory().get("/")
    request.session = cliente.session
    return usuario_da_sessao(request)


def test_membro_sem_alocacao_nao_ve_catalogo(conta):
    titular, *_ = conta
    ana = _membro(titular, "ana")
    ana.user_permissions.set([])
    assert _entrar(ana.email).get("/catalogo").status_code == 404


def test_permissao_direta_de_membro_nao_vale_mais(conta):
    from django.contrib.auth.models import Permission

    titular, *_ = conta
    ana = _membro(titular, "ana")
    ana.user_permissions.add(Permission.objects.get(codename="catalogo_ver"))
    assert not pode(_user_da(_entrar(ana.email)), "catalogo.ver")


def test_a_mais_especifica_ganha_pela_filial_da_sessao(conta):
    from plataforma.contexto import CHAVE

    titular, empresa, norte, sul, cargos = conta
    ana = _membro(titular, "ana")
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=cargos["supervisor"])
    Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                            cargo=cargos["vendedor"])
    cliente = _entrar(ana.email)
    sessao = cliente.session
    sessao[CHAVE] = norte.pk
    sessao.save()
    assert not pode(_user_da(cliente), "catalogo.editar")
    sessao[CHAVE] = sul.pk
    sessao.save()
    assert pode(_user_da(cliente), "catalogo.editar")


def test_filial_forjada_cai_na_primeira_permitida(conta):
    from plataforma.contexto import CHAVE, filial_atual

    titular, empresa, norte, sul, cargos = conta
    ana = _membro(titular, "ana")
    Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                            cargo=cargos["vendedor"])
    cliente = _entrar(ana.email)
    sessao = cliente.session
    sessao[CHAVE] = sul.pk
    sessao.save()
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    request.session = cliente.session
    assert filial_atual(request) == norte


def test_tirar_a_alocacao_vale_na_requisicao_seguinte(conta):
    titular, empresa, norte, _s, cargos = conta
    ana = _membro(titular, "ana")
    alocacao = Alocacao.objects.create(pessoa=ana, empresa=empresa, filial=norte,
                                       cargo=cargos["vendedor"])
    cliente = _entrar(ana.email)
    assert cliente.get("/catalogo").status_code == 200
    alocacao.delete()
    assert cliente.get("/catalogo").status_code == 404


def test_titular_nao_depende_de_cargo(conta):
    titular, *_ = conta
    assert pode(_user_da(_entrar(titular.email)), "usuarios.editar")


def test_perfil_nao_da_mais_permissao(conta):
    """A virada: o Perfil ainda existe até a Task 7, mas deixou de ser fonte."""
    from django.contrib.auth.models import Permission

    from contas.models import Perfil

    titular, empresa, norte, _s, cargos = conta
    ana = _membro(titular, "ana")
    Alocacao.objects.create(pessoa=ana, empresa=empresa, cargo=cargos["cliente"])
    perfil = Perfil.objects.create(dono=titular, nome="extra", rotulo="Extra")
    perfil.permissoes.add(Permission.objects.get(codename="usuarios_editar"))
    perfil.usuarios.add(ana)
    assert not pode(_user_da(_entrar(ana.email)), "usuarios.editar")
```

Se `/catalogo` não for a rota exata do módulo de catálogo, use a rota que
`catalogo/modulo.py` declara e que exige `catalogo.ver`.

- [ ] **Step 2: Rodar e ver falhar**

Expected: FAIL em quase todos (a permissão ainda vem de diretas + perfis).

- [ ] **Step 3: `contas/backend.py` — membro nasce sem permissão; perfil deixa de ser fonte**

```python
def permissoes_de(usuario: Usuario) -> frozenset[str]:
    """As permissões DIRETAS da pessoa, no vocabulário do núcleo.

    Desde a virada dos cargos (spec 2026-09-14, D9), só o titular e a MW5 têm
    permissão direta que vale: são as de `contas/fabrica.py`. Para quem é
    membro de uma conta, a permissão vem do cargo da alocação no lugar em que
    ele está (`contas.lugar.com_permissoes_do_lugar`).

    O `Perfil` deixou de ser fonte. Dois jeitos de conceder a mesma coisa é o
    defeito que o `Group` já tinha causado aqui, e foi o motivo de o `Perfil`
    existir.
    """
    return traduzir(
        Permission.objects.filter(user=usuario, content_type__app_label=APP_DOS_MODULOS)
        .values_list("codename", flat=True).distinct())
```

Em `_para_o_nucleo`:

```python
    # Membro nasce SEM permissão: a dele depende do lugar, e o lugar só se
    # resolve com a requisição na mão (`comum.sessao.usuario_da_sessao`). Um
    # `User` de membro que saísse daqui já com permissão seria a porta por onde
    # uma permissão direta esquecida continuaria valendo.
    manda_por_si = usuario.is_superuser or usuario.nivel <= Nivel.TITULAR
    ...
        permissions=permissoes_de(usuario) if manda_por_si else frozenset(),
```

Importe `Nivel` de `.models`. Tire do docstring antigo o parágrafo sobre
"forma canônica é pelo Perfil" e o que falava de `perfis__usuarios`. Os
parágrafos sobre `Group`, o nome do grupo e o módulo desligado continuam
verdadeiros e ficam.

- [ ] **Step 4: `comum/sessao.py` — identidade × usuário no lugar**

Renomeie o corpo atual de `usuario_da_sessao` para `identidade_da_sessao`,
com o mesmo docstring (ajuste a primeira frase). Crie a função nova:

```python
def usuario_da_sessao(request, backend=None) -> "User | None":
    """Quem esta requisição VÊ, com o que essa pessoa pode NO LUGAR em que está.

    Duas etapas, e a ordem é imposta pela dependência (spec 2026-09-14, "Onde a
    pessoa está"): a permissão depende do lugar, e o lugar depende da pessoa.
    `identidade_da_sessao` resolve a pessoa; `contas.lugar` resolve o lugar e
    põe as permissões do cargo.

    Quem resolve o lugar (`plataforma.contexto`) lê `identidade_da_sessao`,
    NUNCA esta função. Senão perguntar o lugar pediria as permissões, e pedir as
    permissões perguntaria o lugar.

    Backend injetado (teste de guarda com gente de mentira) volta sem passar
    pelo lugar: a gente dele não existe no banco para ter alocação.
    """
    identidade = identidade_da_sessao(request, backend)
    if identidade is None or backend is not None:
        return identidade
    return lembrar(request, f"sessao:no-lugar:{identidade.id}",
                   lambda: _no_lugar(request, identidade))


def _no_lugar(request, identidade: User) -> User:
    """Import tardio pelo mesmo motivo de `_backend_padrao`: a sessão é
    infraestrutura, e o lugar é de `contas`."""
    from contas.lugar import com_permissoes_do_lugar

    return com_permissoes_do_lugar(request, identidade)
```

Acrescente `"identidade_da_sessao"` ao `__all__`. `usuario_original_da_sessao`
continua como está.

- [ ] **Step 5: `contas/lugar.py` — `com_permissoes_do_lugar`**

```python
def com_permissoes_do_lugar(request, user: User) -> User:
    """O `user` da sessão com as permissões do cargo no lugar atual.

    Titular e MW5 voltam como vieram: as permissões deles são as de fábrica, que
    o backend já pôs. Para o membro, o cargo da alocação vigente na empresa e
    filial atuais, ou nenhuma permissão.
    """
    from dataclasses import replace

    from plataforma.contexto import empresa_atual, filial_atual

    pessoa = usuario_de(user)
    if pessoa is None or _ve_tudo(pessoa) or pessoa.nivel <= Nivel.TITULAR:
        return user
    vigente = alocacao_vigente(pessoa, empresa_atual(request), filial_atual(request))
    permissoes = permissoes_do_cargo(vigente.cargo) if vigente else frozenset()
    return replace(user, permissions=permissoes)
```

Importe `usuario_de` de `.identidade` e acrescente o nome ao `__all__`.

- [ ] **Step 6: `plataforma/contexto.py` — a empresa e a filial pelas alocações**

- Troque todo `usuario_da_sessao` deste arquivo por `identidade_da_sessao`, com um comentário numa das trocas explicando a recursão que isso evita.
- `_decidir`: no ramo `permitidas.count() == 1`, `return permitidas.first()` (sai o `empresa_de`).
- `filiais_de(user, empresa=None)`:

```python
def filiais_de(user, empresa=None):
    """As filiais ativas que `user` alcança DENTRO de `empresa`.

    Até 14/09/2026 lia `Filial.usuarios`, que não sabia de empresa: podia
    devolver filial de outra empresa, e por isso o carrinho gravava a Matriz.
    Agora a filial é sempre uma filial da empresa em que se está.
    """
    from contas.identidade import usuario_de
    from contas.lugar import filiais_da_pessoa

    if user is None:
        return Filial.objects.none()
    return filiais_da_pessoa(usuario_de(user), empresa)
```

- `filial_atual(request)`: memorizada (`lembrar(request, "contexto:filial", ...)`), com `permitidas = filiais_de(identidade_da_sessao(request), empresa_atual(request))`. O resto (id da sessão conferido e, se não bater, `first()`) fica igual.
- `filial_permitida`: `filiais_de(identidade_da_sessao(request), empresa_atual(request))`.
- `escolher_empresa`: depois de gravar a empresa, `request.session.pop(CHAVE, None)`, com o comentário: "trocar de empresa leva a filial para a primeira permitida dentro dela".
- Reescreva os docstrings que citam `Filial.usuarios` e "a filial está desligada".

- [ ] **Step 7: `contas/alcance.py` — empresas pela alocação**

```python
def empresa_de(usuario) -> "Empresa | None":
    ...  # docstring: None para o MASTER; para os outros, a primeira empresa alcançada
    pessoa = usuario_de(usuario)
    if pessoa is None or _ve_tudo(usuario, pessoa):
        return None
    return empresas_da_pessoa(pessoa).first()


def empresas_alcancadas(usuario):
    pessoa = usuario_de(usuario)
    if _ve_tudo(usuario, pessoa):
        return Empresa.objects.all()
    return empresas_da_pessoa(pessoa)
```

`from .lugar import empresas_da_pessoa` no topo (`lugar` não importa
`alcance`). `compradores_alcancados` e `pessoas_alcancadas` ficam como estão
nesta task.

- [ ] **Step 8: Helpers de teste em `tests/conftest.py`**

```python
#: O nível de quem é membro de uma conta. Até a Task 7 é `COMPRADOR` (3); lá
#: vira `MEMBRO` (2), e só esta linha muda.
def _nivel_de_membro():
    from contas.models import Nivel

    return Nivel.COMPRADOR


def cargo_com(empresa, *chaves, nome="cargo-de-teste", alcance="empresa",
              e_cliente=False):
    """Um cargo da conta de `empresa` com exatamente as permissões pedidas
    (`"modulo.acao"`). Para o teste que precisa de "alguém que pode X" sem
    depender do que os cargos de fábrica trazem hoje."""
    from django.contrib.auth.models import Permission

    from contas.models import Cargo

    cargo, _ = Cargo.objects.get_or_create(
        conta_id=empresa.conta_id, nome=nome,
        defaults={"rotulo": nome.title(), "alcance": alcance, "e_cliente": e_cliente})
    cargo.permissoes.set(Permission.objects.filter(
        content_type__app_label="plataforma",
        codename__in=[c.replace(".", "_") for c in chaves]))
    return cargo


def alocar(pessoa, empresa=None, cargo="cliente", filial=None):
    """Aloca `pessoa` em `empresa` (filial vazia = empresa inteira) com `cargo`,
    que pode ser o nome de um cargo de fábrica ou um `Cargo`.

    É o cadastro que dá permissão a um membro desde a virada. Sem ele, um teste
    que só criava a pessoa com permissão direta passaria a tomar 404 e parecer
    defeito da tela. Idempotente por lugar: chamar de novo troca o cargo.
    """
    from contas.models import Alocacao, Cargo

    empresa = empresa or empresa_do_teste()
    if pessoa.nivel <= 1 or pessoa.is_superuser:
        pessoa.nivel = _nivel_de_membro()
        pessoa.save(update_fields=["nivel"])
    por_na_conta(pessoa, empresa)
    empresa.refresh_from_db()
    if isinstance(cargo, str):
        cargo = Cargo.objects.get(conta_id=empresa.conta_id, nome=cargo)
    alocacao, _ = Alocacao.objects.update_or_create(
        pessoa=pessoa, empresa=empresa, filial=filial, defaults={"cargo": cargo})
    return alocacao
```

Ajuste `dar_acesso`: quando `nivel` for `Nivel.VENDEDOR` ou `Nivel.COMPRADOR`,
depois de `por_na_conta`, chame
`alocar(pessoa, alvo[0], "vendedor" if nivel == Nivel.VENDEDOR else "cliente")`
(se `alvo` não estiver vazio).

Ajuste `dar_papel(pessoa, papel, dono=None)`: pare de criar `Perfil`. A empresa
é `Empresa.objects.filter(dono_id=pessoa.dono_id).first() or empresa_do_teste()`,
e a chamada é `alocar(pessoa, empresa, "cliente" if papel == "comprador" else "vendedor")`.
Devolva a alocação. O docstring diz que o nome ficou para não mexer em dezenas
de chamadas, e que o papel virou cargo.

- [ ] **Step 9: Rodar a suíte inteira e consertar o que a virada quebrou**

Vai quebrar muita coisa, e é esperado. Regras para consertar, **nesta ordem de preferência**:

1. **Teste que criava alguém com permissão direta para abrir uma tela** (`user_permissions.add` em quem não é titular; lista com `grep -rln user_permissions tests`): se o ator age como dono da conta, promova-o a titular com `dar_acesso(pessoa)` (sem nível) e `aplicar(pessoa, Nivel.TITULAR)`, ou deixe a permissão direta num titular. Se o teste fala de alguém que NÃO é dono, troque a permissão direta por `alocar(pessoa, empresa, cargo_com(empresa, "modulo.acao", ...))`.
2. **Teste que afirmava que o Perfil dá permissão** (`test_perfis.py`, `test_contas_backend.py`, `test_tela_perfis.py` e outros): se ele prova só que "perfil concede", **apague o teste** e diga isso no commit, porque o perfil deixou de conceder. Se ele prova outra coisa usando perfil como meio, troque o meio por `alocar`/`cargo_com`.
3. **`tests/test_contexto_filial.py`**: reescreva a partir de alocações (alocação na filial, na empresa inteira, filial desativada, id forjado, perda da alocação na hora). Os casos de negócio continuam os mesmos; muda só o cadastro.
4. **Vendedor** (`dar_acesso(nivel=VENDEDOR)` virou o cargo Vendedor, que tem `orcamentos.acompanhar` e alcance filial): o teste que afirmava "o vendedor não acompanha orçamento" (`test_o_vendedor_esta_parado.py`) é da regra que o spec reverteu. Apague o arquivo inteiro na Task 3, junto com a carteira; nesta task, deixe-o falhando só se ele não passar, e anote no relatório.
5. **Nunca** ajuste um teste para passar mudando o que ele afirma sobre fronteira entre contas ou sobre MW5. Se um teste desses falhar, é defeito do código novo: pare e conserte o código.

Registre no relatório, por arquivo, o que foi convertido, apagado e por quê.

- [ ] **Step 10: Mutações**

1. Em `usuario_da_sessao`, devolver `identidade` sem passar por `_no_lugar`: deve falhar `test_a_mais_especifica_ganha_pela_filial_da_sessao`.
2. Em `_para_o_nucleo`, trocar `if manda_por_si else frozenset()` por sempre `permissoes_de`: deve falhar `test_permissao_direta_de_membro_nao_vale_mais`.
3. Em `filial_atual`, aceitar o id da sessão sem conferir em `permitidas`: deve falhar `test_filial_forjada_cai_na_primeira_permitida`.

- [ ] **Step 11: Suíte inteira verde, contagem no `CLAUDE.md`, commit**

Commit `feat(cargos): a permissão vem do cargo da alocação no lugar em que a pessoa está`. A mensagem explica a ordem pessoa → lugar → permissões, a separação `identidade_da_sessao` × `usuario_da_sessao` e a recursão que ela evita, o perfil deixando de ser fonte, e os testes apagados com o motivo.

---

### Task 3: Cliente e alcance no lugar do papel; sai a carteira

**Files:**
- Modify: `contas/lugar.py`, `catalogo/preco.py`, `catalogo/views_vitrine.py`, `catalogo/views_produto.py`, `orcamento/visibilidade.py`, `orcamento/views.py`, `contas/alcance.py`, `contas/views_usuarios.py`
- Delete: `contas/papel.py`, `tests/test_papel.py`, `tests/test_o_vendedor_esta_parado.py`
- Test: `tests/test_alcance_do_cargo.py` (novo); ajustar `tests/test_orcamento.py`, `tests/test_preco.py`, `tests/test_catalogo_vitrine.py`, `tests/test_catalogo_produto.py`, `tests/test_acesso_alcance.py`, `tests/test_usuarios_alcance.py`, `tests/test_conta_nasce_com_empresa.py`

**Interfaces:**
- Consumes: Task 2 (`usuario_da_sessao`, `filial_atual`, `empresa_atual` pelas alocações).
- Produces em `contas/lugar.py`:
  - `cargo_atual(request) -> Cargo | None`
  - `e_cliente(request) -> bool`
  - `alcance_atual(request) -> str`
  - `clientes_alcancados(request) -> QuerySet[Usuario]`
- Muda: `catalogo.preco.precificar(consulta, request)` e `precos_de(produtos, request)` (antes recebiam `usuario`).

- [ ] **Step 1: Escrever os testes do alcance**

`tests/test_alcance_do_cargo.py`: uma conta com Norte e Sul, dois clientes
(`c1` alocado na Norte e `c2` na Sul, ambos com o cargo Cliente), um orçamento
de cada um gravado com a filial deles (`Orcamento.irrestritos.create(empresa=..., comprador=..., filial=...)`), e três atores:

- Vera: Vendedor na Norte (alcance filial);
- Sara: Supervisor na empresa inteira (alcance empresa);
- `c1`: Cliente (os próprios).

Cada teste loga pelo `POST /entrar`, põe a filial na sessão quando precisa e
chama `orcamento.visibilidade.da_empresa`/`meus` com um `RequestFactory`
que carrega `request.session` e `request.usuario = usuario_da_sessao(request)`.
Os casos:

```python
def test_vendedor_na_norte_acompanha_so_os_da_norte(...):
    assert set(da_empresa(req_vera)) == {orc_c1}

def test_supervisor_acompanha_a_empresa_inteira(...):
    assert set(da_empresa(req_sara)) == {orc_c1, orc_c2}

def test_cliente_nao_acompanha_ninguem_e_ve_os_proprios(...):
    assert list(da_empresa(req_c1)) == []
    assert set(meus(req_c1)) == {orc_c1}

def test_cargo_criado_pelo_titular_com_alcance_proprios_ve_so_os_dele(...):
    # cargo_com(empresa, "orcamentos.ver", "orcamentos.acompanhar", alcance="proprios")
    # alocado na Norte: da_empresa devolve só orçamentos em que ele é o comprador

def test_e_cliente_decide_o_preco_negociado(...):
    # Preco para c1 num produto; precificar(consulta, req_c1) mostra o negociado,
    # precificar(consulta, req_vera) mostra o preco_base

def test_clientes_alcancados_seguem_o_alcance(...):
    assert set(clientes_alcancados(req_vera)) == {c1}
    assert set(clientes_alcancados(req_sara)) == {c1, c2}

def test_cliente_alocado_na_empresa_inteira_aparece_para_a_filial(...):
    # c3 com Cliente na empresa inteira aparece em clientes_alcancados(req_vera)

def test_carrinho_nasce_na_filial_atual(...):
    # carrinho_de(req_c1).filial == norte
```

Escreva cada teste completo, com cadastro e asserts. Os blocos acima dizem
o que cada um afirma.

- [ ] **Step 2: Rodar e ver falhar**

- [ ] **Step 3: `contas/lugar.py` — as quatro perguntas da requisição**

```python
def _pessoa_e_lugar(request):
    from comum.sessao import identidade_da_sessao
    from plataforma.contexto import empresa_atual, filial_atual

    return (usuario_de(identidade_da_sessao(request)),
            empresa_atual(request), filial_atual(request))


def cargo_atual(request) -> "Cargo | None":
    from comum.memoria import lembrar

    def calcular():
        pessoa, empresa, filial = _pessoa_e_lugar(request)
        vigente = alocacao_vigente(pessoa, empresa, filial)
        return vigente.cargo if vigente else None

    return lembrar(request, "lugar:cargo", calcular)


def e_cliente(request) -> bool:
    """Substitui `tem_papel(usuario, Papel.COMPRADOR)` nos quatro lugares que
    perguntavam isso (spec, `e_cliente`). É do cargo, e não do alcance: sem
    carteira, Vendedor e Cliente podem ter o mesmo alcance."""
    cargo = cargo_atual(request)
    return bool(cargo and cargo.e_cliente)


def alcance_atual(request) -> str:
    pessoa, empresa, filial = _pessoa_e_lugar(request)
    return alcance_em(pessoa, empresa, filial)


def clientes_alcancados(request) -> "QuerySet[Usuario]":
    """Os clientes que quem está olhando enxerga na empresa atual.

    Substitui `compradores_alcancados`, que lia o papel do perfil e a carteira
    (D6: a carteira sai da regra e fica no banco, sem uso). Cliente é quem tem
    alocação com cargo `e_cliente` nesta empresa. Alocado na empresa inteira,
    ele pertence a todas as filiais.
    """
    from django.db.models import Q

    pessoa, empresa, filial = _pessoa_e_lugar(request)
    if pessoa is None or empresa is None:
        return Usuario.objects.none()
    alocacoes = Alocacao.objects.filter(empresa=empresa, cargo__e_cliente=True)
    alcance = alcance_em(pessoa, empresa, filial)
    if alcance == Alcance.FILIAL:
        if filial is None:
            return Usuario.objects.none()
        alocacoes = alocacoes.filter(Q(filial=filial) | Q(filial__isnull=True))
    clientes = Usuario.objects.filter(
        pk__in=alocacoes.values("pessoa_id"), dono_id=empresa.dono_id)
    if alcance == Alcance.PROPRIOS:
        return clientes.filter(pk=pessoa.pk)
    return clientes
```

Acrescente os quatro nomes ao `__all__`.

- [ ] **Step 4: Trocar os consumidores**

- `catalogo/preco.py`: `_comprador_id(request)` devolve `usuario_de(request.usuario).pk if e_cliente(request) else None`. `precificar(consulta, request)` e `precos_de(produtos, request)` recebem `request`. Atualize o docstring do módulo (sai "compradores_alcancados"). Troque as chamadas em `catalogo/views_vitrine.py` para passar `request`.
- `catalogo/views_vitrine.py::_tem_preco_proprio(request)`: `return e_cliente(request)`.
- `catalogo/views_produto.py` (`_aba_precos`, `_acao_precos_salvar`): `alcancados = list(clientes_alcancados(request).order_by("email"))`. O produto já vem de `do_contexto`, então é da empresa atual.
- `orcamento/views.py`: `e_comprador = e_cliente(request)`. Ajuste o comentário: o CARGO decide a pergunta, e a permissão decide se a rota abre.
- `orcamento/visibilidade.py`:

```python
def da_empresa(request):
    """Os orçamentos que quem está olhando ACOMPANHA, COM os cancelados, pelo
    ALCANCE do cargo no lugar atual (spec, "O alcance vira filtro"). Titular e
    MW5 veem a empresa atual inteira."""
    from contas.lugar import alcance_atual, e_cliente
    from contas.models import Alcance
    from plataforma.contexto import filial_atual

    pessoa = usuario_de(getattr(request, "usuario", None))
    if pessoa is None or e_cliente(request):
        return Orcamento.objects.none()
    base = Orcamento.objects.do_contexto(request)
    alcance = alcance_atual(request)
    if alcance == Alcance.EMPRESA:
        return base
    if alcance == Alcance.FILIAL:
        filial = filial_atual(request)
        return base.filter(filial=filial) if filial else base.none()
    return base.filter(comprador_id=pessoa.pk)
```

  Em `carrinho_de`, grave `filial=filial_atual(request) or empresa.filiais.filter(e_matriz=True).first()`, e troque o comentário "o plano 2 troca" pelo motivo atual: a filial é a do lugar, e a Matriz é só o caso de quem não alcança filial ativa nenhuma.
- `contas/alcance.py`: apague `compradores_alcancados` e os imports de `Papel` e `tem_papel`. Tire do docstring do módulo o parágrafo da carteira.
- `contas/views_usuarios.py`: apague o bloco da carteira (`_bloco_de_carteira`, `_salvar_carteira`, `_carteira_de`, `_carteira_possivel`), as chamadas deles em criar e editar, e o `data-nivel-vendedor` que só servia ao bloco. `Usuario.compradores` **fica no model** (D6).
- Apague `contas/papel.py`, `tests/test_papel.py` e `tests/test_o_vendedor_esta_parado.py`. `grep -rn "contas.papel\|tem_papel\|papel_de\|compradores_alcancados" --include=*.py . | grep -v .venv` tem de voltar vazio fora de migrações.

- [ ] **Step 5: Ajustar os testes antigos**

- `test_usuarios_alcance.py::TestACarteiraSeMontaNaTela`: apague a classe (a carteira saiu da tela, D6).
- `test_acesso_alcance.py`: os testes de `compradores_alcancados` viram testes de `clientes_alcancados` quando provam fronteira entre contas ou entre clientes; os que provam carteira saem.
- `test_orcamento.py`, `test_preco.py`, `test_catalogo_vitrine.py`, `test_catalogo_produto.py`, `test_conta_nasce_com_empresa.py`, `test_personificacao_condominio.py`: ajuste as chamadas para as assinaturas novas e o cadastro para `alocar`. A regra do Step 9 da Task 2 continua valendo: afirmação sobre fronteira não se afrouxa.

- [ ] **Step 6: Mutações**

1. Em `da_empresa`, trocar o ramo `FILIAL` por `return base`: deve falhar `test_vendedor_na_norte_acompanha_so_os_da_norte`.
2. Em `e_cliente`, devolver sempre `False`: deve falhar `test_e_cliente_decide_o_preco_negociado`.
3. Em `clientes_alcancados`, apagar `dono_id=empresa.dono_id`: escreva antes um teste de fronteira em que uma pessoa de OUTRA conta tem alocação apontando para esta empresa, criada com `Alocacao.objects.bulk_create`, que pula o `clean`. Ele deve ficar vermelho com a mutação.

- [ ] **Step 7: Suíte inteira, contagem, commit**

Commit `feat(cargos): cliente e alcance vêm do cargo; sai a carteira da regra`.

---

### Task 4: O seletor de filial no cabeçalho

**Files:**
- Modify: `plataforma/contexto.py` (`niveis_de_contexto`), `plataforma/site.py` (`construir_context_switcher`), `plataforma/views_empresa_contexto.py`, `plataforma/views_filial.py`
- Test: `tests/test_cabecalho_contexto.py`, `tests/test_filial_trocar.py`

**Interfaces:**
- Consumes: `filiais_de(user, empresa)`, `filial_atual`, `empresa_atual`.
- Produces: `niveis_de_contexto(request)` devolve de 0 a 2 níveis, com `nivel=0` para a empresa e `nivel=1` para a filial.

- [ ] **Step 1: Testes que falham**

Em `tests/test_cabecalho_contexto.py`:
- Membro com alocação na Norte e na Sul: o HTML da página inicial tem `<select` com `name="filial_id"`, as duas filiais como opções e a atual `selected`.
- Membro com uma filial só: nenhum `name="filial_id"` no HTML.
- Titular com Matriz e Norte: tem o seletor de filial e não tem o de empresa.
- MW5 com duas empresas: tem os dois, e o `action` do form é `reverse("empresa_trocar")`.

Em `tests/test_filial_trocar.py`:
- `GET /filial/trocar?filial_id=<norte>` mostra a confirmação. Hoje a view lê `?filial=`, e o seletor do cabeçalho manda `filial_id`: é o mesmo defeito que `empresa_trocar` já teve.
- `GET /empresa/trocar?empresa_id=<atual>&filial_id=<norte>` redireciona para a confirmação de filial.
- Filial de outra empresa: 404 nos dois.

- [ ] **Step 2: Implementar**

`niveis_de_contexto`:

```python
    user = identidade_da_sessao(request)
    atual = empresa_atual(request)
    niveis = []
    empresas = list(empresas_de(user))
    if len(empresas) > 1:
        niveis.append(NivelDeContexto(
            nivel=0, rotulo=_("Conta"), atual=str(atual.pk) if atual else "",
            opcoes=[OpcaoDeContexto(str(e.pk), str(e)) for e in empresas]))
    filiais = list(filiais_de(user, atual)) if atual else []
    if len(filiais) > 1:
        filial = filial_atual(request)
        niveis.append(NivelDeContexto(
            nivel=1, rotulo=_("Filial"), atual=str(filial.pk) if filial else "",
            opcoes=[OpcaoDeContexto(str(f.pk), str(f)) for f in filiais]))
    return niveis
```

Reescreva o docstring e o comentário "sem seletor quando não há o que
selecionar", que continua valendo, agora para cada nível.

`construir_context_switcher`: um `ContextLevel` por nível. Nível 0 usa
`name=CHAVE_EMPRESA` e o rótulo `rotulos[0]`; nível 1 usa `name=CHAVE` e
`rotulos[1]` se existir, senão `nivel.rotulo`. O `action` é
`reverse("empresa_trocar")` se houver nível 0, senão
`reverse("filial_trocar")`. Escreva ao lado o motivo (R8: um formulário só,
os dois selects vão juntos).

`empresa_trocar` (GET), antes da confirmação:

```python
        # R8: o cabeçalho manda os dois selects para cá. Empresa igual à atual
        # com filial pedida é troca de FILIAL, e a confirmação dela mora lá.
        pedida = request.GET.get(CHAVE, "")
        if pedida and empresa == empresa_atual(request):
            return HttpResponseRedirect(
                reverse("filial_trocar") + "?" + urlencode({CHAVE: pedida}))
```

`filial_trocar` (GET): `filial_permitida(request, request.GET.get(CHAVE, ""))`,
com o comentário do nome único nas duas pontas. Atualize os testes antigos
que usavam `?filial=`.

- [ ] **Step 3: Mutação**

Trocar o `name=CHAVE` do nível 1 por `"filial"`: o teste do HTML deve falhar.

- [ ] **Step 4: Suíte inteira e commit**

Commit `feat(contexto): o cabeçalho escolhe a filial quando a pessoa alcança mais de uma`.

---

### Task 5: Alocações no cadastro de usuário; saem Perfis e o painel de nível

**Files:**
- Modify: `contas/views_usuarios.py`, `contas/alcance.py` (`pessoas_alcancadas`), `comum/auditoria.py`
- Create: `contas/static/contas/alocacoes.js`
- Test: `tests/test_alocacoes_na_tela.py` (novo); `tests/test_auditoria.py` (cenários novos); ajustar `tests/test_tela_usuarios.py`, `tests/test_usuarios_alcance.py`

**Interfaces:**
- Consumes: `contas.lugar.pode_dar`, `pode_administrar`, `empresas_da_pessoa`, `filiais_da_pessoa`.
- Produces:
  - campos do POST `aloc_empresa`, `aloc_filial` (`""` = a empresa inteira) e `aloc_cargo`, em listas paralelas (`getlist`), com pk;
  - `ACOES.ALOCACAO_CRIADA` e `ACOES.ALOCACAO_REMOVIDA`, com alvo `str(alocacao)`.

- [ ] **Step 1: Testes que falham**

`tests/test_alocacoes_na_tela.py`, sempre pelo `POST /usuarios` com `acao`,
como `tests/test_tela_usuarios.py` já faz (copie de lá o formato dos campos de
criar e editar):

- Titular cria pessoa com uma linha (Norte, Vendedor): nasce a `Alocacao`, e a pessoa é membro.
- Titular edita pessoa trocando Norte/Vendedor por empresa inteira/Supervisor: fica só a nova.
- Linha em branco é ignorada; linha repetida (mesma empresa e filial) vira uma alocação só.
- **Escalada, pelo POST forjado:**
  - Gerente na Norte cria pessoa com Sul/Vendedor: recusado com frase, e nada é gravado (nem a pessoa).
  - Gerente na Norte cria pessoa com Norte/Supervisor: recusado.
  - Gerente cria pessoa sem nenhuma linha: recusado ("Aloque a pessoa em pelo menos um lugar."). Sem essa trava ele criaria alguém que só o titular enxerga.
  - Gerente edita o Supervisor pelo pk: 404 ou "não encontrado", como hoje para alvo fora do alcance.
  - Gerente edita a si mesmo: idem.
  - Cargo de outra conta pelo pk: recusado.
  - Filial de outra empresa pelo pk: recusado.
- MW5 promove alguém a titular mandando linhas de alocação junto: vira titular, sem alocação (o titular não é alocado, D3).
- A tela não mostra mais a seção "Perfis" nem o painel de nível (`data-ct-resumo`), e mostra "+ Acrescentar alocação".
- Gerente vê na listagem só quem ele administra (R6).

- [ ] **Step 2: `pessoas_alcancadas` com R6**

```python
    if pessoa is None:
        return Usuario.objects.none()
    if pessoa.e_titular_ou_acima:
        return Usuario.objects.filter(is_superuser=False, dono=pessoa).distinct()
    # Membro com `usuarios.editar` (Supervisor, Gerente): só quem ele poderia
    # ter alocado (R6). Em Python, e não numa consulta: a regra compara
    # permissões e alcance de cargo, e uma conta tem dezenas de pessoas, não
    # milhares.
    candidatos = Usuario.objects.filter(dono_id=pessoa.dono_id, is_superuser=False)
    ids = [c.pk for c in candidatos if pode_administrar(pessoa, c)]
    return Usuario.objects.filter(pk__in=ids)
```

Isso só vale para quem abre a tela, porque a rota continua exigindo
`usuarios.editar` no lugar atual.

- [ ] **Step 3: O bloco Alocações**

Em `contas/views_usuarios.py`:

- `_lugares_oferecidos(request)`: empresas de `empresas_da_pessoa(editor)` e, para cada uma, `filiais_da_pessoa(editor, empresa)`. Os cargos são `Cargo.objects.filter(conta_id__in=[e.conta_id ...])`. A tela OFERECE o que o editor alcança, e quem RECUSA é o POST, por `pode_dar`.
- `_linhas_de_alocacao(oferta, enviado=None, alvo=None)`: uma `<div class="cd-linha">` por alocação existente do alvo, ou pelas linhas enviadas no POST que voltou com erro, mais uma em branco. Cada linha tem três `<select>`:
  - `aloc_empresa`;
  - `aloc_filial`, com a primeira opção `""` "Todas as filiais" e as demais rotuladas `"Filial (Empresa)"` quando há mais de uma empresa;
  - `aloc_cargo`.
  E um botão Remover.
- `_bloco_de_alocacoes(...)`: seção "Alocações", com as linhas dentro de `<div class="cd-lista" id="aloc-lista">` e o botão `<button type="button" data-aloc-mais="aloc-lista">+ Acrescentar alocação</button>`. Escape todo texto com `escape`/`format_html`, como o resto do arquivo faz.
- `contas/static/contas/alocacoes.js`: repetidor mínimo (clonar a última linha, limpar os selects, acrescentar; Remover apaga, menos a última). **É cópia do padrão de `catalogo/static/catalogo/cadastro.js::ligarRepetidores`, e não import**: a base não pode depender de módulo de negócio (`test_camadas_nao_se_invertem.py`). Escreva isso no topo do arquivo. Carregue o script na página de Usuários do mesmo jeito que a página carrega os estáticos dela hoje.
- `_ler_alocacoes(request, editor, alvo)` devolve `(linhas, erro)`. Para cada índice de `zip(getlist("aloc_empresa"), getlist("aloc_filial"), getlist("aloc_cargo"))`:
  - pule a linha sem empresa e sem cargo;
  - resolva a empresa em `empresas_da_pessoa(editor)`, a filial em `Filial.objects.filter(empresa=empresa)` (ou `None` para `""`) e o cargo em `Cargo.objects.filter(conta_id=empresa.conta_id)` (qualquer um que não resolva: erro "Lugar ou cargo inválido.");
  - confira `pode_dar(editor, empresa, filial, cargo)` (se não puder: erro "Você não pode dar o cargo X em Y.");
  - deduplique por `(empresa.pk, filial.pk if filial else None)`, e a última linha vence.
- `_gravar_alocacoes(request, alvo, linhas)`:
  - se `alvo.nivel <= Nivel.TITULAR`, apague as alocações dele e saia;
  - senão, apague as alocações cujo lugar não está em `linhas` (`registrar(ACOES.ALOCACAO_REMOVIDA, ...)` para cada uma), atualize o cargo das que ficaram no mesmo lugar e crie as novas (`ALOCACAO_CRIADA`). Tudo dentro do `atomic()` que `_acao_criar`/`_acao_editar` já abrem.
- `_acao_criar` e `_acao_editar`: leia as alocações ANTES de gravar qualquer coisa. Se houver erro, devolva o formulário com as linhas enviadas e sem escrita. Editor que não é titular nem MW5 e manda zero linhas ao criar: erro "Aloque a pessoa em pelo menos um lugar.".
- Saem `_bloco_de_perfis`, `_salvar_perfis`, `_concede_permissao` (e a chamada dele), `_resumo_do_nivel`, `_duas_colunas` (o formulário volta a ter uma coluna) e o import de `PERGUNTAS`/`responde`. `contas/fabrica.py` mantém as duas constantes até a Task 7.
- Nível: `_niveis_que_pode_conceder` devolve `[Nivel.TITULAR, Nivel.COMPRADOR]` para MW5/superusuário (o rótulo muda na Task 7) e `[]` para os demais, e aí o seletor não é desenhado. Pessoa criada por quem não é MW5 nasce com o nível padrão do model. Em `_salvar_acesso`, chame `aplicar(usuario, nivel)` só quando o nível resultante for TITULAR ou MASTER; para membro, `usuario.user_permissions.clear()`, com o comentário "a permissão do membro é do cargo".

- [ ] **Step 4: Auditoria**

Em `comum/auditoria.py`, `ALOCACAO_CRIADA` e `ALOCACAO_REMOVIDA` com rótulos
"Alocação criada" e "Alocação removida". Em `tests/test_auditoria.py`, um
cenário de cada, pelo POST da tela, com o titular como ator (siga o formato de
`_cenario_cargo_criado`).

- [ ] **Step 5: Ajustar os testes antigos**

Em `tests/test_tela_usuarios.py`:
- saem `TestPermissaoSoDaMw5` (a caixa de Perfis sumiu; mantenha só o teste de que o POST forjado com `perfis` não concede nada, que continua verdadeiro);
- saem `TestOPainelDoNivel` e o teste das duas colunas;
- em `TestONivelTrazAPermissao`, ficam só os testes sobre TITULAR e MASTER;
- `TestNaoDaParaSubirDeNivel` e `TestAFronteiraComAMw5` ficam e precisam continuar verdes sem afrouxar.

- [ ] **Step 6: Mutações**

1. Em `_ler_alocacoes`, pular o `pode_dar`: devem falhar os testes de escalada.
2. Em `pessoas_alcancadas`, devolver `candidatos` inteiro: deve falhar "Gerente vê na listagem só quem ele administra".
3. Em `_acao_criar`, gravar a pessoa antes de ler as alocações: deve falhar o "nada é gravado (nem a pessoa)".

- [ ] **Step 7: Suíte inteira, contagem, commit**

Commit `feat(usuarios): alocações no cadastro da pessoa; saem os Perfis da tela`.

---

### Task 6: A migração dos dados de hoje

**Files:**
- Create: `contas/migrations/0017_perfis_viram_cargos.py`, `plataforma/migrations/0008_filial_tem_empresa.py`, `orcamento/migrations/0006_orcamento_filial_obrigatoria.py`
- Modify: `plataforma/models.py` (`Filial.empresa` sem `null`), `orcamento/models.py` (`Orcamento.filial` sem `null`), `README.md`
- Test: `tests/test_migracao_perfis_viram_cargos.py` (novo)

**Interfaces:**
- Consumes: os models históricos até `contas.0016`, `plataforma.0007` e `orcamento.0005`.
- Produces: a instalação migrada sem nenhuma pessoa de nível VENDEDOR (2) ou COMPRADOR (3) sem alocação, desde que ela tenha conta com empresa; todos com nível 2; nenhuma permissão direta em quem não é titular.

- [ ] **Step 1: Os testes da migração (Migrator)**

`tests/test_migracao_perfis_viram_cargos.py`. Copie a fixture `migrador` de
`tests/test_migracao_uma_conta_uma_empresa.py`, **com `transactional_db` e
`migrador.reset()` no fim**, como corrigido no plano 1 (commit `30016ac`).
Estado antigo: `apply_initial_migration([("contas", "0016_o_titular_edita_cargos"), ("plataforma", "0007_a_ordem_do_cadastro"), ("orcamento", "0005_o_orcamento_vai_para_a_matriz")])`.
Migrada: `apply_tested_migration([("contas", "0017_perfis_viram_cargos"), ("plataforma", "0008_filial_tem_empresa"), ("orcamento", "0006_orcamento_filial_obrigatoria")])`.
Cada teste monta o dado antigo com os models históricos (níveis como literais: `TITULAR, VENDEDOR, COMPRADOR = 1, 2, 3`), porque o `post_save` que cria a Matriz e os cargos não roda com model histórico. Crie a Matriz (`Filial(e_matriz=True)`) à mão.

Os casos:

1. Comprador no perfil global "comprador" (`dono=None`, sem permissão) vira alocação na empresa inteira com o cargo `cliente` da conta dele, e o cargo `cliente` continua com `catalogo_ver` e `orcamentos_ver` (R1).
2. Vendedor sem perfil nenhuma, pelo nível, vira `vendedor` na empresa inteira.
3. Vendedor em `Filial.usuarios` da Norte vira alocação na Norte.
4. Perfil de conta "financeiro" com `auditoria_ver` e sem papel vira cargo `financeiro` com a mesma permissão, alcance `proprios` e `e_cliente=False`, e a pessoa é alocada nele.
5. Perfil de conta com papel vendedor e nome novo vira cargo com alcance `filial`.
6. Perfil de conta chamado "gerente", com permissões, se funde no cargo de fábrica `gerente`: o cargo fica com as permissões do perfil e continua `de_fabrica`.
7. Perfil de conta chamado "comprador" com permissões se funde em `cliente` (R2).
8. Conta sem cargos de fábrica recebe os cinco, com permissões, mesmo sem `Permission` materializada: apague as `Permission` de `catalogo_ver` antes de migrar e confira que ela existe e está no cargo depois.
9. Nível: 3 e 2 viram 2; titular continua 1.
10. Permissão direta de membro que o nível dava (`catalogo_ver`) some sem bloquear (R4).
11. **Para:** permissão direta `usuarios_editar` num comprador. `apply_tested_migration` levanta um erro cuja mensagem contém o e-mail da pessoa.
12. **Para:** filial sem empresa. A mensagem contém o id da filial.
13. **Para:** pessoa em dois perfis de conta que viram cargos diferentes (R3). A mensagem contém o e-mail.
14. **Para:** pessoa em `Filial.usuarios` de uma filial de OUTRA conta. A mensagem contém o e-mail.
15. Pessoa sem conta (`dono=None`, nível 3) não ganha alocação e não bloqueia (R5).
16. Orçamento com `filial` nula ganha a Matriz da empresa dele.

Nos casos que param, confira também que nada foi gravado. O Postgres desfaz
a migração inteira: depois do erro, `migrador.reset()` e a fixture seguinte
recomeçam limpas.

- [ ] **Step 2: Rodar e ver falhar**

Expected: FAIL (`KeyError`/`NodeNotFoundError` para `0017`).

- [ ] **Step 3: Escrever `contas/migrations/0017_perfis_viram_cargos.py`**

```python
"""Os perfis viram cargos e as pessoas ganham alocações (spec 2026-09-14,
"A migração do que existe hoje").

A regra é a mesma do `conta_guid`: **preenche o que sabe deduzir e para com erro
no que não sabe**, listando TODOS os casos de uma vez. Uma subida parada para
consertar um caso, depois outro, depois outro, é o portal fora do ar três vezes.
A conferência do `README.md` lista os mesmos casos com a versão antiga no ar.

**Sem desfazer.** A fusão de perfis e a troca de nível apagam informação que não
volta. Para voltar, restaure o backup de antes.

Decisões que o spec não respondia, com o raciocínio no plano
`docs/superpowers/plans/2026-09-14-cargos-2-virada.md` (R1–R5):

- perfil global de papel (`dono` nulo, da `0006`) é marcador, e vira o cargo de
  fábrica sem mexer nas permissões dele;
- perfil chamado "comprador" vira "cliente";
- pessoa com perfis que viram cargos diferentes na mesma empresa: para;
- permissão direta só para a migração se for além do que o nível dava;
- pessoa sem conta não ganha alocação.

**As `Permission` de módulo são criadas aqui quando faltam**, pelo mesmo motivo
da `0016`: elas nascem no `post_migrate`, depois de todas as migrações, e um
cargo de fábrica criado sem elas ficaria vazio para sempre (a semeadura só cria
o que falta).
"""

from django.db import migrations

_TITULAR, _VENDEDOR, _COMPRADOR, _MEMBRO = 1, 2, 3, 2
_TIPO = ("plataforma", "modulo")

#: Congelado de `contas/cargos_de_fabrica.py` em 14/09/2026. Migração não importa
#: código vivo: ele muda, e a migração tem de fazer hoje o que fazia no dia.
_DE_FABRICA = (
    ("supervisor", "Supervisor", "empresa", False,
     ("catalogo_ver", "catalogo_editar", "orcamentos_ver",
      "orcamentos_acompanhar", "usuarios_editar")),
    ("gerente", "Gerente", "filial", False,
     ("catalogo_ver", "catalogo_editar", "orcamentos_ver",
      "orcamentos_acompanhar", "usuarios_editar")),
    ("vendedor", "Vendedor", "filial", False,
     ("catalogo_ver", "orcamentos_ver", "orcamentos_acompanhar")),
    ("representante", "Representante", "filial", False,
     ("catalogo_ver", "orcamentos_ver", "orcamentos_acompanhar")),
    ("cliente", "Cliente", "proprios", True, ("catalogo_ver", "orcamentos_ver")),
)

#: O que `contas/fabrica.py` gravava como permissão direta nos dois níveis que
#: saem, depois da `0011`. Direta igual a isto não é concessão de ninguém (R4).
_DO_NIVEL = {_VENDEDOR: {"catalogo_ver", "orcamentos_ver"},
             _COMPRADOR: {"catalogo_ver", "orcamentos_ver"}}

_ALCANCE_DO_PAPEL = {"comprador": "proprios", "vendedor": "filial", "": "proprios"}
_CARGO_DO_PAPEL_GLOBAL = {"comprador": "cliente", "vendedor": "vendedor"}


def _permissao(apps, codename):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    tipo, _ = ContentType.objects.get_or_create(app_label=_TIPO[0], model=_TIPO[1])
    modulo, _, acao = codename.partition("_")
    permissao, _ = Permission.objects.get_or_create(
        codename=codename, content_type=tipo,
        defaults={"name": f"{modulo}: {acao}"})
    return permissao


def _cargos_de_fabrica(apps, titular):
    Cargo = apps.get_model("contas", "Cargo")
    for nome, rotulo, alcance, e_cliente, codenames in _DE_FABRICA:
        cargo, criado = Cargo.objects.get_or_create(
            conta_id=titular.guid, nome=nome,
            defaults={"rotulo": rotulo, "alcance": alcance,
                      "e_cliente": e_cliente, "de_fabrica": True})
        if criado:
            cargo.permissoes.set([_permissao(apps, c) for c in codenames])


def _migrar(apps, schema_editor):
    Usuario = apps.get_model("contas", "Usuario")
    Perfil = apps.get_model("contas", "Perfil")
    Cargo = apps.get_model("contas", "Cargo")
    Alocacao = apps.get_model("contas", "Alocacao")
    Empresa = apps.get_model("plataforma", "Empresa")
    Filial = apps.get_model("plataforma", "Filial")
    Orcamento = apps.get_model("orcamento", "Orcamento")

    erros = []

    for filial in Filial.objects.filter(empresa__isnull=True):
        erros.append(f"filial sem empresa: id {filial.pk} ({filial.nome})")

    for titular in Usuario.objects.filter(nivel=_TITULAR):
        _cargos_de_fabrica(apps, titular)

    def cargo_do_perfil(perfil, conta):
        """O cargo da `conta` para onde este perfil vai (R1, R2)."""
        codenames = set(perfil.permissoes.values_list("codename", flat=True))
        if perfil.dono_id is None and perfil.papel in _CARGO_DO_PAPEL_GLOBAL:
            return Cargo.objects.get(conta_id=conta.guid,
                                     nome=_CARGO_DO_PAPEL_GLOBAL[perfil.papel])
        nome = "cliente" if perfil.nome == "comprador" else perfil.nome
        cargo = Cargo.objects.filter(conta_id=conta.guid, nome=nome).first()
        if cargo is None:
            cargo = Cargo.objects.create(
                conta_id=conta.guid, nome=nome, rotulo=perfil.rotulo,
                alcance=_ALCANCE_DO_PAPEL.get(perfil.papel, "proprios"),
                e_cliente=perfil.papel == "comprador")
            cargo.permissoes.set(perfil.permissoes.all())
        elif codenames:
            # Um perfil com o nome de um cargo que já existe se funde nele, e
            # as permissões do perfil prevalecem. Um perfil SEM permissão não
            # sobrescreve (R1): ele era só marcador de papel.
            cargo.permissoes.set(perfil.permissoes.all())
        return cargo

    for pessoa in Usuario.objects.filter(nivel__in=(_VENDEDOR, _COMPRADOR),
                                         is_superuser=False):
        conta = pessoa.dono
        empresa = Empresa.objects.filter(dono=conta).first() if conta else None
        if empresa is None:
            continue  # R5
        cargos = {cargo_do_perfil(p, conta) for p in pessoa.perfis.all()}
        if not cargos:
            nome = "cliente" if pessoa.nivel == _COMPRADOR else "vendedor"
            cargos = {Cargo.objects.get(conta_id=conta.guid, nome=nome)}
        if len(cargos) > 1:
            erros.append(f"{pessoa.email}: perfis que viram cargos diferentes "
                         f"({', '.join(sorted(c.nome for c in cargos))})")
            continue
        (cargo,) = cargos
        filiais = list(pessoa.filiais.all())
        alheias = [f for f in filiais if f.empresa_id != empresa.pk]
        if alheias:
            erros.append(f"{pessoa.email}: em filial de outra conta "
                         f"(ids {', '.join(str(f.pk) for f in alheias)})")
            continue
        for filial in filiais or [None]:
            Alocacao.objects.get_or_create(
                pessoa=pessoa, empresa=empresa, filial=filial,
                defaults={"cargo": cargo, "conta_id": empresa.conta_id})

        diretas = set(pessoa.user_permissions.filter(
            content_type__app_label=_TIPO[0]).values_list("codename", flat=True))
        do_cargo = set(cargo.permissoes.values_list("codename", flat=True))
        sobra = diretas - _DO_NIVEL[pessoa.nivel] - do_cargo
        if sobra:
            erros.append(f"{pessoa.email}: permissão direta que o cargo "
                         f"{cargo.nome} não cobre ({', '.join(sorted(sobra))})")

    for orcamento in Orcamento.objects.filter(filial__isnull=True):
        matriz = Filial.objects.filter(empresa_id=orcamento.empresa_id,
                                       e_matriz=True).first()
        if matriz is None:
            erros.append(f"orçamento {orcamento.pk}: empresa sem Matriz")
        else:
            orcamento.filial = matriz
            orcamento.save(update_fields=["filial"])

    if erros:
        raise RuntimeError(
            "A migração dos cargos parou. Nada foi gravado. Resolva com a versão "
            "antiga no ar (ver a conferência no README) e suba de novo:\n- "
            + "\n- ".join(erros))

    membros = Usuario.objects.filter(nivel__in=(_VENDEDOR, _COMPRADOR))
    for pessoa in membros.iterator():
        pessoa.user_permissions.clear()
    membros.update(nivel=_MEMBRO)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0016_o_titular_edita_cargos"),
        ("plataforma", "0007_a_ordem_do_cadastro"),
        ("orcamento", "0005_o_orcamento_vai_para_a_matriz"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(_migrar, migrations.RunPython.noop)]
```

`Alocacao` histórica não tem o `save` com `full_clean`; por isso a
`conta_id` vai explícita.

Confira no model histórico o `related_name` de `Filial.usuarios`
(`plataforma/migrations/0001_initial.py`, esperado `"filiais"`). Se for outro,
use o nome que estiver lá.

- [ ] **Step 4: As colunas obrigatórias**

- `plataforma/models.py`: `Filial.empresa` sem `null=True, blank=True`. Gere `plataforma/0008_filial_tem_empresa` com `makemigrations plataforma -n filial_tem_empresa` e acrescente a dependência `("contas", "0017_perfis_viram_cargos")`.
- `orcamento/models.py`: `Orcamento.filial` sem `null`. Gere `orcamento/0006_orcamento_filial_obrigatoria` com a mesma dependência, e ponha no docstring da migração a invariante pedida nas pendências do plano 1: "toda empresa tem Matriz (`post_save` + `plataforma/0006`), e por isso o `carrinho_de` sempre acha filial".
- Rode `makemigrations --check --dry-run`: tem de dizer "No changes detected".

- [ ] **Step 5: Rodar os testes da migração e ver passar**

- [ ] **Step 6: A conferência no README**

Na seção de atualização do `README.md`, junto da conferência do `conta_guid`,
acrescente "Antes de atualizar para os cargos", com um bloco
`manage.py shell -c` que roda **com a versão antiga no ar** e imprime:

- filiais sem empresa (**bloqueia**);
- pessoas com nível 2 ou 3 em perfis que não são o mesmo cargo (**bloqueia**);
- pessoas com permissão direta além de `catalogo_ver`/`orcamentos_ver` e fora dos perfis delas (**bloqueia**);
- pessoas em filial de outra conta (**bloqueia**);
- perfis sem papel que vão virar "os próprios" (**aviso**).

Use só models que existem na versão antiga (`Perfil`, `Filial.usuarios`) e
escreva ao lado o motivo. Não inclua credencial nem host.

- [ ] **Step 7: Aplicar no banco local de desenvolvimento**

`DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/kronos .venv/bin/python manage.py migrate`.
Se parar, leia a lista, corrija o dado local à mão, e registre no relatório o
que era e o que foi feito. É o ensaio da atualização real.

- [ ] **Step 8: Mutações**

1. Tirar o `elif codenames:` (sobrescrever sempre): deve falhar o caso 1.
2. Tirar o `- _DO_NIVEL[pessoa.nivel]`: deve falhar o caso 10.
3. Trocar o `raise` por `pass`: devem falhar os casos 11 a 14.

- [ ] **Step 9: Suíte inteira (com `pgbin`), contagem, commit**

Commit `feat(cargos): a migração dos perfis e níveis para cargos e alocações`.

---

### Task 7: Limpeza — saem Perfil, Papel, `Filial.usuarios` e os níveis antigos

**Files:**
- Modify: `contas/models.py`, `plataforma/models.py`, `contas/fabrica.py`, `contas/modulo.py`, `contas/apps.py`, `plataforma/apps.py`, `contas/urls.py`, `contas/caixas_de_permissao.py`, `contas/views_cargos.py`, `contas/views_usuarios.py`, `comum/auditoria.py`, `tests/conftest.py`, `CLAUDE.md`
- Create: `contas/migrations/0018_o_perfil_sai.py`, `plataforma/migrations/0009_filial_usuarios_sai.py` (geradas)
- Delete: `contas/perfis.py`, `contas/views_perfis.py`, `tests/test_tela_perfis.py`, `tests/test_perfis.py`, `tests/test_perfis_regras.py`, `tests/test_modulo_perfis.py`
- Test: `tests/test_o_perfil_saiu.py` (novo)

**Interfaces:**
- Produces: `Nivel` = `MASTER (0)`, `TITULAR (1)`, `MEMBRO (2)`; `Usuario.nivel` com padrão `MEMBRO`.

- [ ] **Step 1: O teste que tranca a saída**

`tests/test_o_perfil_saiu.py`:

```python
"""O Perfil saiu (14/09/2026: "Não tem mais perfil, é tudo cargo agora").
Tranca a volta por descuido: um import, uma rota ou um módulo que o traga de
volta fica vermelho aqui antes de virar dois jeitos de dar permissão."""

import pytest
from django.urls import NoReverseMatch, reverse


def test_nao_existe_mais_model_perfil_nem_papel():
    import contas.models as modelos

    assert not hasattr(modelos, "Perfil")
    assert not hasattr(modelos, "Papel")


def test_nao_existe_mais_rota_de_perfis():
    with pytest.raises(NoReverseMatch):
        reverse("perfis")


def test_modulo_perfis_nao_e_declarado():
    from plataforma.declaracao import declarados

    assert "perfis" not in {spec.chave for spec in declarados()}


def test_niveis_sao_master_titular_e_membro():
    from contas.models import Nivel

    assert [(n.value, n.name) for n in Nivel] == [
        (0, "MASTER"), (1, "TITULAR"), (2, "MEMBRO")]


def test_filial_nao_tem_mais_usuarios():
    from plataforma.models import Filial

    assert "usuarios" not in {f.name for f in Filial._meta.get_fields()}
```

- [ ] **Step 2: Rodar e ver falhar**

- [ ] **Step 3: Remover**

- `contas/models.py`: apagar `Papel` e `Perfil`. Em `Nivel`, `MEMBRO = 2, "Membro"`, com um comentário dizendo que o 2 era VENDEDOR, que o 3 (COMPRADOR) foi migrado para 2 em `0017`, e que o cargo substituiu os dois. `nivel` com `default=Nivel.MEMBRO`. Tire o comentário sobre `e_vendedor`/`e_comprador`. Atualize o `__all__`.
- `plataforma/models.py`: apagar `Filial.usuarios`.
- `makemigrations contas -n o_perfil_sai` e `makemigrations plataforma -n filial_usuarios_sai`. Confira que a `0018` depende da `0017` e a `plataforma/0009` da `0008`, e escreva no docstring de cada uma que o dado já foi copiado em `0017`.
- `contas/perfis.py`, `contas/views_perfis.py`: apagar. `contas/urls.py`: tirar a rota. `contas/modulo.py`: tirar `MODULO_PERFIS` e o comentário dele; em `MODULO_USUARIOS`, reescreva o comentário que cita `MODULO_PERFIS`. `contas/apps.py`: tirar o registro. `plataforma/apps.py` (ou onde estiver): tirar a chamada a `garantir_perfis_do_sistema`.
- `contas/fabrica.py`: tirar `perfis.*` do MASTER e as entradas VENDEDOR e COMPRADOR, com `_RESPOSTAS` e `PERGUNTAS` se ninguém mais os usar (`grep`). Reescreva o docstring do módulo: o nível dá a permissão do titular e da MW5; a do membro é do cargo.
- `contas/caixas_de_permissao.py` e `contas/views_cargos.py`: `SEM_MODULOS = frozenset({"cargos"})`.
- `contas/views_usuarios.py`: o seletor de nível da MW5 oferece `TITULAR` e `MEMBRO`. Tire as referências a `Nivel.VENDEDOR`/`COMPRADOR`.
- `comum/auditoria.py`: tire `PERFIL_CRIADO`, `PERFIL_EDITADO` e `PERFIL_REMOVIDO` do vocabulário gravável e mantenha os rótulos em `ROTULOS` (R9), com o comentário. Se `test_auditoria.py` cobra cenário para todo item de `ROTULOS`, separe em `ROTULOS_HISTORICOS` e escreva o porquê.
- `tests/conftest.py`: `_nivel_de_membro` devolve `Nivel.MEMBRO`; `dar_papel` (se ainda chamado) fica; apague o que citar `Perfil`.
- `grep -rn "Nivel.VENDEDOR\|Nivel.COMPRADOR\|Perfil\b\|Papel\b\|perfis\b" --include=*.py . | grep -v "\.venv\|/migrations/"`: tudo o que sobrar fora de migração e de `test_o_perfil_saiu.py` é resto a limpar. "Meu perfil" (`/perfil`, `views_perfil.py`) NÃO é isto e fica.
- Os testes apagados estão na lista de Files. Os de migração antigos (`test_migracao_papel_do_nivel.py` e outros) usam models históricos e ficam, desde que passem. Se um deles importar `Nivel.COMPRADOR` vivo, troque pelo literal `3`.

- [ ] **Step 4: `CLAUDE.md` §7**

Reescreva "A hierarquia de usuários":
- três níveis (MASTER, TITULAR, MEMBRO), e o cargo da alocação no lugar do papel;
- `contas/lugar.py` como a porta de "onde está / o que pode";
- `identidade_da_sessao` × `usuario_da_sessao`, e por que `plataforma.contexto` só lê a primeira;
- as travas R6/R7 de quem aloca;
- a carteira fora da regra (D6);
- o parágrafo "O que ainda não foi decidido" (VENDEDOR/COMPRADOR) sai;
- "`Perfil` é um conjunto de permissões..." sai, e o parágrafo sobre `mw5.*` troca "concedido num Perfil" por "concedido num cargo";
- "A carteira é a segunda fronteira" vira "O alcance do cargo é a segunda fronteira".

Atualize a contagem de arquivos de teste (duas ocorrências).

- [ ] **Step 5: Mutação**

Recolocar `MODULO_PERFIS` no registro: `test_modulo_perfis_nao_e_declarado` deve falhar.

- [ ] **Step 6: Suíte inteira (com `pgbin`), `makemigrations --check`, migrar o banco local, commit**

Commit `refactor(cargos): saem Perfil, Papel, Filial.usuarios e os níveis VENDEDOR/COMPRADOR`.

---

## Ao fim deste plano

- Ninguém tem permissão por Perfil; o Perfil não existe.
- Membro só vê e pode o que o cargo da alocação dá no lugar em que está.
- O cadastro de usuário aloca, com as travas de escalada no POST.
- O cabeçalho escolhe a filial.
- A migração leva uma instalação existente para o modelo novo, ou para com a lista do que precisa ser resolvido antes.

**Plano 3:** várias empresas por conta (sai `uma_empresa_por_conta`, "Nova empresa", `EMPRESA_CRIADA`, seletor de empresa para o titular) e o módulo de filiais nascendo ligado (D7).
