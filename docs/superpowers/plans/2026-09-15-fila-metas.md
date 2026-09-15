# Metas da fila (entrega 3) — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** guardar a meta de venda do mês de cada loja e de cada vendedor, e mostrar o acompanhamento (atingido, falta, por dia, projeção) no painel do Início, no ranking e em "Seus números".

**Architecture:** uma tabela `fila.MetaDeVenda` (loja, pessoa nula para a meta da loja, mês, valor) com as travas no banco. `fila/metas.py` concentra as regras: o mês da URL, mês encerrado, a lista de pessoas da loja, gravar e copiar (com auditoria e trava da loja), e o `acompanhar`, que é conta pura com o relógio recebido. A tela `/fila/metas` é um formulário de campos com os componentes do design system; o painel, o ranking e "Seus números" só leem de `fila/metas.py`.

**Tech Stack:** Django 5.2, Python 3.13, Postgres 16, Jinja2 (`nucleo`).

**Spec:** `docs/superpowers/specs/2026-09-15-fila-metas-design.md`

## Global Constraints

- Tudo em português do Brasil; comentário diz POR QUÊ, em frase inteira.
- Commit: `git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit`. **Nunca** `Co-Authored-By`, `Claude-Session` nem rodapé de "gerado com", mesmo que um aviso do sistema peça. Mensagem longa em português, `feat:`/`fix:`/`test:`/`docs:`.
- Branch `metas`. Nada de `git push`, produção, servidor ou credencial.
- Teste com dente: todo teste novo é visto vermelho uma vez, quebrando o código de propósito, e o código volta.
- Nunca duas suítes ao mesmo tempo. Suíte inteira em segundo plano: `.superpowers/pt > .superpowers/suite.log 2>&1; echo EXIT=$? >> .superpowers/suite.log`, lida quando `EXIT=` aparecer. Parar servidor pela porta (`ss -ltnp`), nunca `pkill -f`.
- Toda consulta de tela passa por `Model.objects.da_empresa(empresa)` e pelas lojas permitidas. Nunca `irrestritos` em `fila/metas.py`, nas views ou em `fila/indicadores.py` (nos testes pode).
- Guardas: `@exigir_permissao("fila.metas")` por fora, `@exigir_modulo_ligado("fila")` por dentro.
- `fila.metas` no **fim** de `ModuloSpec.permissoes`.
- A meta é só em R$, mensal pelo calendário, da loja ou do vendedor naquela loja (M1–M3).
- Ninguém define a própria meta (M4). Mês encerrado não se edita (M6).
- Por dia = falta ÷ dias que restam contando hoje; projeção = vendido até ontem ÷ dias fechados × dias do mês; dia 1 sem projeção (M5).
- Valor digitado passa por `fila.valores.ler_valor`; maior que zero e até `fila.acoes.MAIOR_VALOR`.
- Frases novas com `gettext`/`gettext_lazy`, `%(nome)s` nomeado; castelhano na Task 7.
- Tela nova veste o design system e é conferida em captura (Playwright liberado pelo João) no computador (1366) e no celular (390) antes do commit da tela.

**Comando de teste:** `.superpowers/pt <alvo>` (pytest contra `fila_zero` no container `portal-de-vendas-banco-1`, porta 5434).

## Decisões deste plano (o spec não respondia)

- **P-1 — O model se chama `MetaDeVenda`, e não `Meta`.** Todo model do Django tem uma classe interna `Meta`; um model chamado `Meta` com uma `class Meta(ModeloDaEmpresa.Meta)` dentro confunde quem lê e quem importa.
- **P-2 — A meta guarda `alterada_em` (`auto_now`).** A versão da página da fila precisa mudar quando o gerente troca uma meta por outro valor com a mesma soma; a contagem e a soma não bastam.
- **P-3 — O POST da tela de metas não carrega id de pessoa.** O servidor monta a lista de pessoas da loja e lê só `valor_loja` e `valor_<pk>` de quem está nela. Campo de pessoa de fora da lista é ignorado, e o da própria pessoa também: não há id forjado para conferir.
- **P-4 — Campo ausente no POST não mexe na meta; campo vazio apaga.** O formulário sempre manda todos os campos; um POST parcial (forjado ou cortado) não apaga o que não mandou.
- **P-5 — Quem entra na lista:** pessoa ativa com alocação na loja (ou na empresa inteira) cujo cargo, NAQUELA loja, traz `fila.participar` (ou `fila.*`), mais quem tem meta de pessoa naquela loja e mês. O titular não entra (não tem alocação): a meta é de quem trabalha na fila.
- **P-6 — O ranking só lista quem fechou atendimento no período** (regra da entrega 2). Um vendedor com meta e nenhum atendimento não aparece nele; aparece na tela de metas e em "Seus números".
- **P-7 — `lojas_com_relatorio` vira um caso de `lojas_com_permissao(pessoa, empresa, permissao)`.** As lojas da tela de metas saem do mesmo molde, sem copiar a função.
- **P-8 — O mês na URL é `?mes=AAAA-MM`**; vazio, inválido ou fora de `periodo.ANOS_ACEITOS` cai no mês atual.

## Arquivos

```
fila/metas.py                          as regras das metas (Tasks 2, 3 e 5)
fila/views_metas.py                    a tela /fila/metas (Task 4)
fila/migrations/0003_metas_de_venda.py (gerada na Task 1)
tests/test_fila_metas.py               registro, regras e contas (Tasks 1, 2, 3 e 5)
tests/test_fila_tela_metas.py          a tela de metas (Task 4)
```

Modificados: `fila/models.py`, `fila/modulo.py`, `fila/urls.py`, `fila/indicadores.py`, `fila/views_indicadores.py`, `fila/static/fila/indicadores.css`, `fila/tela.py`, `fila/estado.py`, `fila/templates/fila/_meus.html`, `fila/static/fila/fila.css`, `comum/auditoria.py`, `contas/cargos_de_fabrica.py`, `contas/fabrica.py`, `tests/test_fila_modulo.py`, `tests/test_cargos_de_fabrica.py`, `tests/test_lugar.py`, `tests/test_fila_tela_indicadores.py`, `tests/test_fila_pagina.py`, `CLAUDE.md`, `docs/superpowers/specs/2026-09-15-fila-metas-design.md` (estado), `locale/`.

---

### Task 1: O registro e a permissão

**Files:**
- Modify: `fila/models.py`, `comum/auditoria.py`, `contas/cargos_de_fabrica.py`, `contas/fabrica.py`, `fila/modulo.py`, `tests/test_fila_modulo.py`, `tests/test_cargos_de_fabrica.py`, `tests/test_lugar.py`
- Create: `tests/test_fila_metas.py`, `fila/migrations/0003_metas_de_venda.py` (gerada)

**Interfaces:**
- Consumes: `contas.inquilino.ModeloDaEmpresa`; `fila.models._loja()`, `fila.models._pessoa(verbose, **extra)`.
- Produces:
  - `fila.models.MetaDeVenda` com `filial`, `pessoa` (nula = meta da loja), `mes: date` (dia 1), `valor: Decimal(12, 2)`, `alterada_em: datetime`.
  - `comum.auditoria.ACOES.FILA_META_DEFINIDA == "fila_meta_definida"`, `ACOES.FILA_META_REMOVIDA == "fila_meta_removida"`.
  - `ModuloSpec("fila").permissoes == ("fila.ver", "fila.participar", "fila.gerenciar", "fila.cadastros", "fila.relatorios", "fila.metas")`.
  - Gerente e supervisor de fábrica e o titular trazem `fila.metas`.

- [ ] **Step 1: Os testes da permissão**

`tests/test_fila_modulo.py`:
- `PERMISSOES_DA_FILA` ganha `"fila.metas"` no fim.
- no parametrizado `test_os_cargos_de_fabrica_trazem_a_fila`, `gerente` passa a `{"fila_ver", "fila_participar", "fila_gerenciar", "fila_relatorios", "fila_metas"}` e `supervisor` a `{"fila_ver", "fila_gerenciar", "fila_relatorios", "fila_metas"}`.

`tests/test_cargos_de_fabrica.py`: nas três asserções de supervisor e gerente (linhas ~53, ~55 e ~152), acrescentar `"fila_metas"`.

`tests/test_lugar.py::test_cargo_traduz_para_o_vocabulario_do_nucleo` (linha ~119): acrescentar `"fila.metas"` ao conjunto do gerente.

Run: `.superpowers/pt tests/test_fila_modulo.py tests/test_cargos_de_fabrica.py tests/test_lugar.py`
Expected: FAIL nas asserções de permissão.

- [ ] **Step 2: A permissão no código**

`fila/modulo.py`, em `permissoes`:

```python
    # fila.relatorios (entrega 2) e fila.metas (entrega 3) no fim: fila.ver
    # continua a primeira, que é a do menu.
    permissoes=("fila.ver", "fila.participar", "fila.gerenciar",
                "fila.cadastros", "fila.relatorios", "fila.metas"),
```

`contas/cargos_de_fabrica.py`: `"fila.metas"` no fim das tuplas de supervisor e de gerente, e no comentário acima delas a linha: `fila.metas (entrega 3): gerente e supervisor definem as metas do alcance deles.`

`contas/fabrica.py`, na lista do TITULAR: `"fila.cadastros", "fila.gerenciar", "fila.metas", "fila.participar", "fila.relatorios", "fila.ver",`.

Run: o comando do Step 1 → PASS.

- [ ] **Step 3: Os testes do registro**

Criar `tests/test_fila_metas.py`:

```python
"""As metas de venda da fila (spec 2026-09-15-fila-metas, entrega 3).

O registro, as regras de `fila/metas.py` e as contas do acompanhamento. As
contas recebem o relógio (`agora`) para cada dia do mês ser provado, e não o
dia em que a suíte roda.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from tests.fila_cenario import nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db

SETEMBRO = date(2026, 9, 1)


def local(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def loja():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(empresa=empresa, matriz=matriz, titular=titular,
                           ana=pessoa_na_loja("ana", empresa, matriz),
                           bia=pessoa_na_loja("bia", empresa, matriz))


def meta(loja, valor="1000", pessoa=None, mes=SETEMBRO, filial=None):
    from fila.models import MetaDeVenda

    return MetaDeVenda.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, pessoa=pessoa,
        mes=mes, valor=Decimal(valor))


def _estoura(**kwargs):
    with pytest.raises(IntegrityError), transaction.atomic():
        meta(**kwargs)


# --- O registro --------------------------------------------------------------

def test_uma_meta_da_loja_por_mes(loja):
    meta(loja)
    _estoura(loja=loja, valor="2000")
    meta(loja, mes=date(2026, 10, 1))


def test_uma_meta_por_pessoa_loja_e_mes(loja):
    meta(loja, pessoa=loja.ana)
    _estoura(loja=loja, pessoa=loja.ana, valor="2000")
    # A da loja e a de outra pessoa no mesmo mês convivem.
    meta(loja)
    meta(loja, pessoa=loja.bia)


def test_a_mesma_pessoa_tem_meta_em_duas_lojas(loja):
    centro = nova_loja(loja.empresa, "Centro")
    meta(loja, pessoa=loja.ana)
    meta(loja, pessoa=loja.ana, filial=centro)


def test_mes_fora_do_dia_1_e_valor_zero_o_banco_recusa(loja):
    _estoura(loja=loja, mes=date(2026, 9, 15))
    _estoura(loja=loja, valor="0")
```

Run: `.superpowers/pt tests/test_fila_metas.py`
Expected: FAIL (`ImportError: cannot import name 'MetaDeVenda'`).

- [ ] **Step 4: O model**

Em `fila/models.py`, acrescentar `"MetaDeVenda"` ao `__all__` e, no fim do arquivo:

```python
class MetaDeVenda(ModeloDaEmpresa):
    """Quanto a loja, ou um vendedor naquela loja, deve vender no mês
    (spec 2026-09-15-fila-metas).

    **Uma tabela para as duas metas**: `pessoa` nula é a meta da loja. A regra,
    a tela e as consultas são as mesmas, e duas tabelas duplicariam cada uma.
    Chama-se `MetaDeVenda`, e não `Meta`, porque todo model já tem uma classe
    interna `Meta` (decisão P-1 do plano).
    """

    filial = _loja()
    pessoa = _pessoa(_("vendedor"), null=True, blank=True)
    mes = models.DateField(_("mês"))
    valor = models.DecimalField(_("valor"), max_digits=12, decimal_places=2)
    #: A versão da página da fila olha para cá: trocar uma meta por outra com
    #: a mesma soma não mudaria contagem nem total (decisão P-2 do plano).
    alterada_em = models.DateTimeField(_("alterada em"), auto_now=True)

    class Meta(ModeloDaEmpresa.Meta):
        verbose_name = _("meta de venda")
        verbose_name_plural = _("metas de venda")
        # No banco, e não só na tela: quem grava por fora (shell, migração, a
        # próxima tela) não cria a segunda meta do mês nem a meta do dia 15.
        constraints = [
            models.UniqueConstraint(
                fields=["filial", "mes"], condition=Q(pessoa__isnull=True),
                name="fila_uma_meta_da_loja_por_mes"),
            models.UniqueConstraint(
                fields=["filial", "pessoa", "mes"],
                condition=Q(pessoa__isnull=False),
                name="fila_uma_meta_por_pessoa_loja_e_mes"),
            models.CheckConstraint(condition=Q(mes__day=1),
                                   name="fila_meta_no_dia_1"),
            models.CheckConstraint(condition=Q(valor__gt=0),
                                   name="fila_meta_positiva"),
        ]
```

Gerar a migração:

```bash
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/fila_zero \
  .venv/bin/python manage.py makemigrations fila --name metas_de_venda
```

Expected: `fila/migrations/0003_metas_de_venda.py` com `CreateModel` e as quatro constraints.

- [ ] **Step 5: As ações da auditoria**

`comum/auditoria.py`, em `ACOES`, depois de `FILA_CADASTRO_REMOVIDO`:

```python
    # As metas da fila (entrega 3); o alvo diz loja, de quem e o mês, e o
    # detalhe, o valor de antes.
    FILA_META_DEFINIDA = "fila_meta_definida"
    FILA_META_REMOVIDA = "fila_meta_removida"
```

e no dicionário de rótulos, depois de `ACOES.FILA_CADASTRO_REMOVIDO`:

```python
    ACOES.FILA_META_DEFINIDA: "Meta de venda definida",
    ACOES.FILA_META_REMOVIDA: "Meta de venda removida",
```

- [ ] **Step 6: Rodar e ver com dente**

Run: `.superpowers/pt tests/test_fila_metas.py tests/test_fila_modulo.py tests/test_cargos_de_fabrica.py tests/test_lugar.py tests/test_regra_do_inquilino.py tests/test_regra_guid.py tests/test_auditoria.py`
Expected: PASS.

Dente: a suíte cria o banco de teste pelas migrações. Apagar de `fila/migrations/0003_metas_de_venda.py` o `AddConstraint` (ou a entrada em `constraints`) de `fila_meta_no_dia_1`, rodar `.superpowers/pt tests/test_fila_metas.py::test_mes_fora_do_dia_1_e_valor_zero_o_banco_recusa` → FAIL, e devolver o arquivo com `git checkout -- fila/migrations/0003_metas_de_venda.py` se já commitado, ou desfazendo a edição. Idem uma vez para `fila_uma_meta_da_loja_por_mes` com `test_uma_meta_da_loja_por_mes`.

- [ ] **Step 7: Commit**

```bash
git add fila/models.py fila/migrations/0003_metas_de_venda.py comum/auditoria.py \
  contas/cargos_de_fabrica.py contas/fabrica.py fila/modulo.py \
  tests/test_fila_metas.py tests/test_fila_modulo.py tests/test_cargos_de_fabrica.py tests/test_lugar.py
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit
```

Mensagem: `feat: a meta de venda do mês e a permissão fila.metas`, com o corpo dizendo por que é uma tabela só, por que as travas moram no banco, e quem ganha a permissão.

---

### Task 2: As contas do acompanhamento

**Files:**
- Create: `fila/metas.py`
- Modify: `tests/test_fila_metas.py`

**Interfaces:**
- Consumes: `fila.periodo.ANOS_ACEITOS`.
- Produces (em `fila/metas.py`):
  - `primeiro_do_mes(dia: date) -> date`, `ultimo_do_mes(mes: date) -> date`, `mes_anterior(mes: date) -> date`, `mes_seguinte(mes: date) -> date`.
  - `mes_do_texto(texto: str | None, agora: datetime | None = None) -> date`.
  - `mes_encerrado(mes: date, agora: datetime | None = None) -> bool`.
  - `Acompanhamento` (frozen) com `meta: Decimal`, `vendido: Decimal`, `atingido: float`, `falta: Decimal`, `excedente: Decimal`, `encerrado: bool`, `ultimo_dia: date`, `dias_restantes: int | None`, `por_dia: Decimal | None`, `projecao: Decimal | None`, e a propriedade `batida -> bool`.
  - `acompanhar(meta: Decimal, vendido: Decimal, mes: date, agora: datetime | None = None, vendido_ate_ontem: Decimal | None = None) -> Acompanhamento`; `ValueError` para mês futuro.

- [ ] **Step 1: Os testes**

Acrescentar a `tests/test_fila_metas.py`:

```python
# --- O mês e o acompanhamento (contas puras) -----------------------------------

from fila.metas import acompanhar, mes_do_texto, mes_encerrado  # noqa: E402

DIA_15 = local(2026, 9, 15, 14)


def test_mes_do_texto():
    assert mes_do_texto("2026-10", DIA_15) == date(2026, 10, 1)
    assert mes_do_texto("2026-1", DIA_15) == date(2026, 1, 1)
    # Vazio, inválido, "²" (isdigit sem ser ASCII) e ano absurdo: mês atual.
    for texto in ("", None, "2026-13", "setembro", "2026-²", "1500-01"):
        assert mes_do_texto(texto, DIA_15) == SETEMBRO


def test_mes_encerrado():
    assert mes_encerrado(date(2026, 8, 1), DIA_15)
    assert not mes_encerrado(SETEMBRO, DIA_15)
    assert not mes_encerrado(date(2026, 10, 1), DIA_15)


def test_dia_15_falta_por_dia_e_projecao():
    a = acompanhar(Decimal("30000"), Decimal("18600"), SETEMBRO, DIA_15,
                   vendido_ate_ontem=Decimal("17000"))
    assert a.atingido == 62.0
    assert (a.falta, a.excedente, a.batida) == (Decimal("11400"), Decimal("0"), False)
    # Do dia 15 ao 30, contando hoje: 16 dias.
    assert a.dias_restantes == 16
    assert a.por_dia == Decimal("712.50")
    # 17.000 em 14 dias fechados, num mês de 30.
    assert a.projecao == Decimal("36428.57")
    assert a.ultimo_dia == date(2026, 9, 30) and not a.encerrado


def test_dia_1_nao_tem_projecao():
    a = acompanhar(Decimal("30000"), Decimal("5000"), SETEMBRO, local(2026, 9, 1, 10),
                   vendido_ate_ontem=Decimal("0"))
    assert a.dias_restantes == 30
    assert a.projecao is None


def test_ultimo_dia_o_por_dia_e_a_falta_inteira():
    a = acompanhar(Decimal("30000"), Decimal("29000"), SETEMBRO, local(2026, 9, 30, 9))
    assert a.dias_restantes == 1 and a.por_dia == Decimal("1000.00")


def test_meta_batida_nao_tem_por_dia():
    a = acompanhar(Decimal("30000"), Decimal("31000"), SETEMBRO, DIA_15)
    assert a.batida and a.excedente == Decimal("1000") and a.por_dia is None


def test_mes_passado_sem_ritmo():
    a = acompanhar(Decimal("20000"), Decimal("18400"), date(2026, 8, 1), DIA_15,
                   vendido_ate_ontem=Decimal("18400"))
    assert a.encerrado and a.atingido == 92.0 and a.falta == Decimal("1600")
    assert (a.dias_restantes, a.por_dia, a.projecao) == (None, None, None)


def test_mes_futuro_nao_tem_acompanhamento():
    with pytest.raises(ValueError):
        acompanhar(Decimal("1"), Decimal("0"), date(2026, 10, 1), DIA_15)
```

Run: `.superpowers/pt tests/test_fila_metas.py`
Expected: FAIL (`ModuleNotFoundError: No module named 'fila.metas'`).

- [ ] **Step 2: `fila/metas.py`**

```python
"""As metas de venda da fila (spec 2026-09-15-fila-metas, entrega 3).

As regras moram aqui, e não nas telas: a tela de metas, o painel do Início,
o ranking e "Seus números" leem a mesma conta, e quatro cópias divergiriam no
primeiro ajuste. Toda função que depende do dia recebe `agora`, para o teste
provar o dia 1, o dia 15 e o último dia sem esperar o calendário.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from .periodo import ANOS_ACEITOS

__all__ = ["Acompanhamento", "acompanhar", "mes_anterior", "mes_do_texto",
           "mes_encerrado", "mes_seguinte", "primeiro_do_mes", "ultimo_do_mes"]

ZERO = Decimal("0")
CENTAVO = Decimal("0.01")


def _hoje(agora: "datetime | None") -> date:
    return timezone.localdate(agora or timezone.now())


def primeiro_do_mes(dia: date) -> date:
    return dia.replace(day=1)


def ultimo_do_mes(mes: date) -> date:
    return mes.replace(day=calendar.monthrange(mes.year, mes.month)[1])


def mes_anterior(mes: date) -> date:
    return primeiro_do_mes(primeiro_do_mes(mes) - timedelta(days=1))


def mes_seguinte(mes: date) -> date:
    return ultimo_do_mes(mes) + timedelta(days=1)


def mes_do_texto(texto: "str | None", agora: "datetime | None" = None) -> date:
    """`?mes=2026-09` -> 1º/09/2026. Vazio ou inválido cai no mês atual, nunca
    num erro: a URL é digitável e compartilhável (decisão P-8 do plano)."""
    atual = primeiro_do_mes(_hoje(agora))
    partes = (texto or "").strip().split("-")
    if len(partes) != 2:
        return atual
    ano, mes = partes
    # `isascii`, porque "²".isdigit() é verdade e int("²") estoura (revisão
    # final do Fila Zero, 15/09/2026).
    if not (ano.isascii() and ano.isdigit() and len(ano) == 4
            and mes.isascii() and mes.isdigit() and 1 <= len(mes) <= 2):
        return atual
    if int(ano) not in ANOS_ACEITOS or not 1 <= int(mes) <= 12:
        return atual
    return date(int(ano), int(mes), 1)


def mes_encerrado(mes: date, agora: "datetime | None" = None) -> bool:
    """Mês antes do atual. A meta dele não se edita (M6): mudar a régua depois
    do resultado desmente o que já foi cobrado."""
    return mes < primeiro_do_mes(_hoje(agora))


@dataclass(frozen=True)
class Acompanhamento:
    meta: Decimal
    vendido: Decimal
    atingido: float
    falta: Decimal
    excedente: Decimal
    encerrado: bool
    ultimo_dia: date
    dias_restantes: "int | None"
    por_dia: "Decimal | None"
    projecao: "Decimal | None"

    @property
    def batida(self) -> bool:
        return self.falta == ZERO


def acompanhar(meta: Decimal, vendido: Decimal, mes: date,
               agora: "datetime | None" = None,
               vendido_ate_ontem: "Decimal | None" = None) -> Acompanhamento:
    """Quanto da meta já foi feito e o ritmo que falta (M5).

    - **por dia** divide o que falta pelos dias que restam CONTANDO hoje: é o
      que a loja ainda pode vender hoje.
    - **projeção** usa só os dias FECHADOS: no dia 1 às 10h, uma venda de
      R$ 5.000 projetaria R$ 150.000, e o dia pela metade puxaria o número
      para baixo no resto do mês. Por isso o dia 1 não tem projeção.
    - Mês encerrado não tem ritmo: não há dia para vender.
    """
    hoje = _hoje(agora)
    atual = primeiro_do_mes(hoje)
    if mes > atual:
        raise ValueError("Mês futuro não tem acompanhamento.")
    ultimo = ultimo_do_mes(mes)
    falta = max(meta - vendido, ZERO)
    excedente = max(vendido - meta, ZERO)
    atingido = round(float(vendido * 100 / meta), 1)
    if mes < atual:
        return Acompanhamento(meta, vendido, atingido, falta, excedente, True,
                              ultimo, None, None, None)
    dias_restantes = ultimo.day - hoje.day + 1
    por_dia = (None if falta == ZERO
               else (falta / dias_restantes).quantize(CENTAVO, ROUND_HALF_UP))
    fechados = hoje.day - 1
    projecao = (None if not fechados or vendido_ate_ontem is None
                else (vendido_ate_ontem / fechados * ultimo.day)
                .quantize(CENTAVO, ROUND_HALF_UP))
    return Acompanhamento(meta, vendido, atingido, falta, excedente, False,
                          ultimo, dias_restantes, por_dia, projecao)
```

- [ ] **Step 3: Rodar e ver com dente**

Run: `.superpowers/pt tests/test_fila_metas.py` → PASS.

Dente (um de cada vez, voltando depois):
- `dias_restantes = ultimo.day - hoje.day` (sem o `+ 1`) → `test_dia_15...` e `test_ultimo_dia...` FAIL.
- `fechados = hoje.day` → `test_dia_15...` e `test_dia_1...` FAIL.
- tirar `ano.isascii() and` e `mes.isascii() and` → `test_mes_do_texto` FAIL.

- [ ] **Step 4: Commit**

Mensagem: `feat: as contas do acompanhamento da meta`, com o corpo explicando por dia contando hoje e a projeção pelos dias fechados.

---

### Task 3: A lista, gravar e copiar

**Files:**
- Modify: `fila/metas.py`, `fila/indicadores.py`, `tests/test_fila_metas.py`

**Interfaces:**
- Consumes: `MetaDeVenda`; `fila.acoes.Recusa`, `fila.acoes.MAIOR_VALOR`, `fila.acoes._travar(*filiais)`; `fila.valores.ler_valor(texto) -> Decimal | None`; `comum.auditoria.ACOES`, `registrar(acao, autor, alvo="", detalhe="", *, request=None)`; `contas.lugar.filiais_da_pessoa`, `permissoes_em`; `fila.estado.nome_de(pessoa)`.
- Produces:
  - `fila.indicadores.lojas_com_permissao(pessoa, empresa, permissao: str) -> list[Filial]`; `lojas_com_relatorio(pessoa, empresa)` passa a chamá-la com `"fila.relatorios"`.
  - `fila.metas.lojas_com_metas(pessoa, empresa) -> list[Filial]`.
  - `fila.metas.Linha` (frozen): `pessoa: Usuario`, `valor: Decimal | None`, `na_loja: bool`, `propria: bool`.
  - `fila.metas.meta_da_loja(loja, mes) -> Decimal | None`.
  - `fila.metas.pessoas_da_lista(loja, mes, editor) -> list[Linha]` (ordem por nome).
  - `fila.metas.MES_ENCERRADO` (frase, `gettext_lazy`), `ValoresInvalidos(Exception)` com `.erros: dict[str, str]` (chave `"loja"` ou `str(pessoa.pk)`).
  - `fila.metas.gravar(loja, mes, editor, valores: dict[str, str | None], *, agora=None, request=None) -> int` (quantas metas mudaram). Chaves de `valores`: `"loja"` e `str(pessoa.pk)`; valor `None` = campo ausente (não mexe), `""` = apagar.
  - `fila.metas.copiar_do_anterior(loja, mes, linhas: list[Linha]) -> dict[str, str]` (só as chaves vazias; valor no formato `"30000,00"`).
  - `fila.metas.valor_do_campo(valor: Decimal | None) -> str` (`None` -> `""`, `Decimal("30000")` -> `"30000,00"`).

- [ ] **Step 1: Os testes**

Acrescentar a `tests/test_fila_metas.py`:

```python
# --- A lista, gravar e copiar ---------------------------------------------------

from fila import metas as regras  # noqa: E402


def _chaves(linhas):
    return [(l.pessoa.nome, l.na_loja, l.propria) for l in linhas]


def test_lojas_com_metas_pelo_cargo(loja):
    from fila.metas import lojas_com_metas

    centro = nova_loja(loja.empresa, "Centro")
    gil = pessoa_na_loja("gil", loja.empresa, centro, cargo="gerente")
    sara = pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    assert lojas_com_metas(gil, loja.empresa) == [centro]
    assert set(lojas_com_metas(sara, loja.empresa)) == {loja.matriz, centro}
    assert lojas_com_metas(loja.ana, loja.empresa) == []


def test_a_lista_traz_quem_participa_e_quem_saiu_com_meta(loja):
    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")  # não participa
    centro = nova_loja(loja.empresa, "Centro")
    caio = pessoa_na_loja("caio", loja.empresa, centro)
    meta(loja, pessoa=caio, valor="5000")  # já teve meta aqui, hoje está no Centro
    linhas = regras.pessoas_da_lista(loja.matriz, SETEMBRO, gil)
    assert _chaves(linhas) == [("Ana", True, False), ("Bia", True, False),
                               ("Caio", False, False), ("Gil", True, True)]
    assert linhas[2].valor == Decimal("5000")


def test_gravar_cria_altera_apaga_e_audita(loja):
    from contas.models import RegistroDeAuditoria
    from fila.models import MetaDeVenda

    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    dia = local(2026, 9, 10, 9)
    assert regras.gravar(loja.matriz, SETEMBRO, gil,
                         {"loja": "250.000,00", str(loja.ana.pk): "30000"},
                         agora=dia) == 2
    assert regras.meta_da_loja(loja.matriz, SETEMBRO) == Decimal("250000")
    assert regras.gravar(loja.matriz, SETEMBRO, gil,
                         {"loja": "250000", str(loja.ana.pk): ""}, agora=dia) == 1
    assert not MetaDeVenda.irrestritos.filter(pessoa=loja.ana).exists()
    acoes = list(RegistroDeAuditoria.objects.values_list("acao", flat=True))
    assert acoes.count("fila_meta_definida") == 2
    assert acoes.count("fila_meta_removida") == 1


def test_campo_ausente_nao_mexe(loja):
    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    meta(loja, pessoa=loja.ana, valor="30000")
    regras.gravar(loja.matriz, SETEMBRO, gil, {"loja": "1000"}, agora=local(2026, 9, 10))
    assert regras.pessoas_da_lista(loja.matriz, SETEMBRO, gil)[0].valor == Decimal("30000")


def test_valor_invalido_recusa_tudo_e_nao_grava_nada(loja):
    from fila.models import MetaDeVenda

    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    with pytest.raises(regras.ValoresInvalidos) as recusa:
        regras.gravar(loja.matriz, SETEMBRO, gil,
                      {"loja": "1000", str(loja.ana.pk): "abc", str(loja.bia.pk): "0"},
                      agora=local(2026, 9, 10))
    assert set(recusa.value.erros) == {str(loja.ana.pk), str(loja.bia.pk)}
    assert not MetaDeVenda.irrestritos.exists()


def test_ninguem_grava_a_propria_nem_de_fora_da_lista(loja):
    from fila.models import MetaDeVenda

    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    de_fora = pessoa_na_loja("zeca", loja.empresa, nova_loja(loja.empresa, "Norte"))
    regras.gravar(loja.matriz, SETEMBRO, gil,
                  {str(gil.pk): "99999", str(de_fora.pk): "99999"},
                  agora=local(2026, 9, 10))
    assert not MetaDeVenda.irrestritos.exists()


def test_mes_encerrado_recusa_gravar(loja):
    from fila.acoes import Recusa

    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    with pytest.raises(Recusa):
        regras.gravar(loja.matriz, date(2026, 8, 1), gil, {"loja": "1000"},
                      agora=local(2026, 9, 10))


def test_copiar_preenche_so_o_vazio_e_nao_traz_quem_saiu(loja):
    gil = pessoa_na_loja("gil", loja.empresa, loja.matriz, cargo="gerente")
    agosto = date(2026, 8, 1)
    centro = nova_loja(loja.empresa, "Centro")
    caio = pessoa_na_loja("caio", loja.empresa, centro)
    meta(loja, valor="200000", mes=agosto)
    meta(loja, pessoa=loja.ana, valor="25000", mes=agosto)
    meta(loja, pessoa=loja.bia, valor="20000", mes=agosto)
    meta(loja, pessoa=caio, valor="9000", mes=agosto)
    meta(loja, pessoa=loja.bia, valor="22000")  # setembro já tem a da Bia
    linhas = regras.pessoas_da_lista(loja.matriz, SETEMBRO, gil)
    assert regras.copiar_do_anterior(loja.matriz, SETEMBRO, linhas) == {
        "loja": "200000,00", str(loja.ana.pk): "25000,00"}
```

Run: `.superpowers/pt tests/test_fila_metas.py`
Expected: FAIL (`AttributeError: module 'fila.metas' has no attribute 'pessoas_da_lista'`).

- [ ] **Step 2: `lojas_com_permissao` em `fila/indicadores.py`**

Substituir `_cobre_relatorios` e `lojas_com_relatorio` por:

```python
def lojas_com_permissao(pessoa, empresa, permissao: str) -> list:
    """As lojas em que o cargo da pessoa traz `permissao` (ou o coringa
    `fila.*`), pelo mesmo `contas.lugar` que decide a permissão em toda tela.
    O gerente de uma loja não a tem em outra; supervisor e titular, em todas.
    Os indicadores e as metas saem daqui (decisão P-7 do plano das metas)."""
    from contas.lugar import filiais_da_pessoa, permissoes_em

    if pessoa is None or empresa is None:
        return []
    return [loja for loja in filiais_da_pessoa(pessoa, empresa)
            if pessoa.is_superuser
            or {permissao, "fila.*"} & permissoes_em(pessoa, empresa, loja)]


def lojas_com_relatorio(pessoa, empresa) -> list:
    return lojas_com_permissao(pessoa, empresa, "fila.relatorios")
```

e acrescentar `"lojas_com_permissao"` ao `__all__`.

- [ ] **Step 3: A lista, gravar e copiar em `fila/metas.py`**

Acrescentar aos imports:

```python
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
```

e ao `__all__`: `"Linha", "MES_ENCERRADO", "ValoresInvalidos", "copiar_do_anterior", "gravar", "lojas_com_metas", "meta_da_loja", "pessoas_da_lista", "valor_do_campo"`.

Código:

```python
#: `gettext_lazy`: constante de módulo, lida no idioma de quem abre a tela.
MES_ENCERRADO = gettext_lazy("Mês encerrado: as metas não se editam mais.")


def lojas_com_metas(pessoa, empresa) -> list:
    from .indicadores import lojas_com_permissao

    return lojas_com_permissao(pessoa, empresa, "fila.metas")


def _metas_do_mes(loja, mes):
    from .models import MetaDeVenda

    return MetaDeVenda.objects.da_empresa(loja.empresa).filter(filial=loja, mes=mes)


def meta_da_loja(loja, mes) -> "Decimal | None":
    return (_metas_do_mes(loja, mes).filter(pessoa__isnull=True)
            .values_list("valor", flat=True).first())


@dataclass(frozen=True)
class Linha:
    pessoa: object
    valor: "Decimal | None"
    na_loja: bool
    propria: bool


def _participa(pessoa, loja) -> bool:
    from contas.lugar import permissoes_em

    return bool({"fila.participar", "fila.*"}
                & permissoes_em(pessoa, loja.empresa, loja))


def pessoas_da_lista(loja, mes, editor) -> "list[Linha]":
    """Quem tem meta de pessoa nesta loja e mês (decisão P-5 do plano):

    - quem está alocado na loja (ou na empresa inteira) e, NESTE lugar,
      participa da fila;
    - mais quem já tem meta aqui neste mês e não está mais na loja: a meta
      continua valendo, e sumir com ela da tela a esconderia de quem edita.

    O titular não entra: não tem alocação, e a meta é de quem trabalha na fila.
    """
    from contas.models import Usuario

    valores = dict(_metas_do_mes(loja, mes).filter(pessoa__isnull=False)
                   .values_list("pessoa_id", "valor"))
    candidatas = (Usuario.objects
                  .filter(Q(alocacoes__filial=loja)
                          | Q(alocacoes__empresa=loja.empresa,
                              alocacoes__filial__isnull=True))
                  .filter(is_active=True).distinct().defer("avatar"))
    na_loja = {p.pk: p for p in candidatas if _participa(p, loja)}
    sairam = Usuario.objects.filter(pk__in=set(valores) - set(na_loja)).defer("avatar")
    linhas = [Linha(p, valores.get(p.pk), True, p.pk == editor.pk)
              for p in na_loja.values()]
    linhas += [Linha(p, valores[p.pk], False, p.pk == editor.pk) for p in sairam]
    return sorted(linhas, key=lambda l: ((l.pessoa.nome or l.pessoa.email).lower(),
                                         l.pessoa.pk))


def valor_do_campo(valor: "Decimal | None") -> str:
    return "" if valor is None else f"{valor:.2f}".replace(".", ",")


class ValoresInvalidos(Exception):
    """Algum valor não serve; `erros` diz qual campo e por quê. Nada foi
    gravado: meia tela salva deixaria a loja com metas que ninguém conferiu."""

    def __init__(self, erros: "dict[str, str]"):
        super().__init__("valores inválidos")
        self.erros = erros


def _ler(texto: str) -> "tuple[Decimal | None, str | None]":
    """(valor, erro). Vazio é (None, None): apagar a meta."""
    from .acoes import MAIOR_VALOR
    from .valores import ler_valor

    if not texto.strip():
        return None, None
    valor = ler_valor(texto)
    if valor is None:
        return None, _("Digite um valor em reais.")
    if valor <= ZERO:
        return None, _("A meta precisa ser maior que zero.")
    if valor > MAIOR_VALOR:
        return None, _("Valor alto demais.")
    return valor, None


def _alvo(loja, pessoa, mes) -> str:
    from .estado import nome_de

    quem = nome_de(pessoa) if pessoa is not None else "a loja"
    return f"{loja}: {quem} em {mes:%m/%Y}"


def gravar(loja, mes, editor, valores: "dict[str, str | None]", *,
           agora: "datetime | None" = None, request=None) -> int:
    """Grava as metas do mês desta loja, tudo ou nada.

    Só as chaves da lista montada AQUI valem (decisão P-3 do plano): a da
    loja e a de cada pessoa da lista que não é quem edita. Campo ausente não
    mexe (P-4); vazio apaga. A linha da loja é trancada, como na fila: dois
    gerentes salvando juntos estourariam a trava do banco com 500.
    """
    from comum.auditoria import ACOES, registrar

    from .acoes import Recusa, _travar
    from .models import MetaDeVenda

    if mes_encerrado(mes, agora):
        raise Recusa(str(MES_ENCERRADO))
    alvos: "dict[str, object | None]" = {"loja": None}
    for linha in pessoas_da_lista(loja, mes, editor):
        if not linha.propria:
            alvos[str(linha.pessoa.pk)] = linha.pessoa

    lidos, erros = {}, {}
    for chave in alvos:
        texto = valores.get(chave)
        if texto is None:
            continue
        valor, erro = _ler(texto)
        if erro:
            erros[chave] = erro
        else:
            lidos[chave] = valor
    if erros:
        raise ValoresInvalidos(erros)

    mudancas = 0
    with transaction.atomic():
        _travar(loja)
        for chave, valor in lidos.items():
            pessoa = alvos[chave]
            atual = _metas_do_mes(loja, mes).filter(pessoa=pessoa).first()
            antes = valor_do_campo(atual.valor) if atual else "sem meta"
            if valor is None:
                if atual is None:
                    continue
                atual.delete()
                registrar(ACOES.FILA_META_REMOVIDA, editor,
                          alvo=_alvo(loja, pessoa, mes), detalhe=f"era {antes}",
                          request=request)
            elif atual is None or atual.valor != valor:
                if atual is None:
                    MetaDeVenda.objects.create(empresa=loja.empresa, filial=loja,
                                               pessoa=pessoa, mes=mes, valor=valor)
                else:
                    atual.valor = valor
                    atual.save(update_fields=["valor", "alterada_em"])
                registrar(ACOES.FILA_META_DEFINIDA, editor,
                          alvo=_alvo(loja, pessoa, mes),
                          detalhe=f"{valor_do_campo(valor)}; era {antes}",
                          request=request)
            else:
                continue
            mudancas += 1
    return mudancas


def copiar_do_anterior(loja, mes, linhas: "list[Linha]") -> "dict[str, str]":
    """O que o mês anterior tinha, só para os campos vazios deste mês.

    Não grava (M6): a pessoa confere e salva. Quem saiu da loja não volta a
    ter meta por cópia, e a meta que já existe neste mês não é trocada.
    """
    anterior = mes_anterior(mes)
    antes = dict(_metas_do_mes(loja, anterior).filter(pessoa__isnull=False)
                 .values_list("pessoa_id", "valor"))
    copia = {}
    if meta_da_loja(loja, mes) is None:
        da_loja = meta_da_loja(loja, anterior)
        if da_loja is not None:
            copia["loja"] = valor_do_campo(da_loja)
    for linha in linhas:
        if linha.na_loja and linha.valor is None and linha.pessoa.pk in antes:
            copia[str(linha.pessoa.pk)] = valor_do_campo(antes[linha.pessoa.pk])
    return copia
```

`MetaDeVenda.objects.create` passa pelo `save` do `ModeloDaEmpresa`, que preenche a conta.

- [ ] **Step 4: Rodar e ver com dente**

Run: `.superpowers/pt tests/test_fila_metas.py tests/test_fila_indicadores.py tests/test_fila_tela_indicadores.py` → PASS.

Dente (um de cada vez, voltando depois):
- em `gravar`, tirar o `if not linha.propria:` (deixar só a atribuição) → `test_ninguem_grava_a_propria...` FAIL.
- em `gravar`, mover o `if erros: raise` para depois do `with` → `test_valor_invalido...` FAIL.
- em `copiar_do_anterior`, tirar `linha.na_loja and` → `test_copiar...` FAIL.
- em `pessoas_da_lista`, tirar `if _participa(p, loja)` → `test_a_lista...` FAIL (Sara aparece).

- [ ] **Step 5: Commit**

Mensagem: `feat: gravar e copiar as metas do mês, com a lista da loja`, com o corpo explicando P-3, P-4, P-5 e a trava da loja.

---

### Task 4: A tela `/fila/metas`

**Files:**
- Create: `fila/views_metas.py`, `tests/test_fila_tela_metas.py`
- Modify: `fila/urls.py`, `fila/modulo.py` (atalho), `tests/test_fila_modulo.py`, `fila/static/fila/indicadores.css` (nada; a tela usa só componentes), `CLAUDE.md` (contagem de arquivos de teste)

**Interfaces:**
- Consumes: Task 3 inteira; `contas.identidade.usuario_de`; `plataforma.contexto.empresa_atual`; `comum.csrf.campo_csrf(request)`; `comum.pedido.id_do_post`; `nucleo.components` (`Alert`, `Box`, `Button`, `Card`, `Form`, `FormGrid`, `Option`, `PageHeader`, `Raw`, `Select`, `TextInput`); `plataforma.site.montar_site`.
- Produces: rota `fila_metas` em `/fila/metas`, view `fila.views_metas.metas(request) -> HttpResponse`. Campos do formulário: `mes` (`AAAA-MM`), `loja` (pk), `valor_loja`, `valor_<pk>`, botão `acao` = `salvar` ou `copiar`.

- [ ] **Step 1: Os testes da tela**

Criar `tests/test_fila_tela_metas.py`:

```python
"""A tela de metas (spec 2026-09-15-fila-metas, "Cadastro")."""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import logado, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


@pytest.fixture
def rede():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    centro = nova_loja(empresa, "Centro")
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, centro=centro,
        ana=pessoa_na_loja("ana", empresa, matriz),
        caio=pessoa_na_loja("caio", empresa, centro),
        gil=pessoa_na_loja("gil", empresa, centro, cargo="gerente"),
        sara=pessoa_na_loja("sara", empresa, None, cargo="supervisor"))


def _mes_atual() -> str:
    return f"{timezone.localdate():%Y-%m}"


def _get(cliente, **params):
    resposta = cliente.get(reverse("fila_metas"), params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_vendedor_nao_abre(rede):
    assert logado("caio").get(reverse("fila_metas")).status_code == 404


def test_gerente_ve_so_a_loja_dele_e_a_forjada_e_descartada(rede):
    html = _get(logado("gil"), loja=str(rede.matriz.pk))
    assert "Caio" in html and "Ana" not in html


def test_supervisor_escolhe_a_loja(rede):
    html = _get(logado("sara"), loja=str(rede.matriz.pk))
    assert "Ana" in html and "Caio" not in html


def test_salvar_grava_e_a_propria_linha_vem_travada(rede):
    from fila.metas import meta_da_loja

    gil = logado("gil")
    html = _get(gil)
    assert f'name="valor_{rede.gil.pk}"' in html
    import re
    propria = re.search(rf'<input[^>]*name="valor_{rede.gil.pk}"[^>]*>', html).group(0)
    assert "disabled" in propria
    resposta = gil.post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "250.000,00", f"valor_{rede.caio.pk}": "30000",
        f"valor_{rede.gil.pk}": "99999"})
    assert resposta.status_code == 302
    mes = timezone.localdate().replace(day=1)
    assert meta_da_loja(rede.centro, mes) == Decimal("250000")
    from fila.models import MetaDeVenda
    assert not MetaDeVenda.irrestritos.filter(pessoa=rede.gil).exists()


def test_valor_invalido_mostra_o_erro_e_nao_grava(rede):
    from fila.models import MetaDeVenda

    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "1000", f"valor_{rede.caio.pk}": "abc"})
    assert resposta.status_code == 200
    assert "Digite um valor em reais." in resposta.content.decode()
    assert not MetaDeVenda.irrestritos.exists()


def test_mes_encerrado_so_leitura_e_post_forjado_recusado(rede):
    from fila.models import MetaDeVenda

    passado = date(2020, 1, 1)
    html = _get(logado("gil"), mes="2020-01")
    assert "Mês encerrado: as metas não se editam mais." in html
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "salvar", "mes": "2020-01", "loja": str(rede.centro.pk),
        "valor_loja": "1000"})
    assert resposta.status_code == 200
    assert not MetaDeVenda.irrestritos.filter(mes=passado).exists()


def test_copiar_preenche_e_nao_salva(rede):
    from fila.metas import mes_anterior
    from fila.models import MetaDeVenda

    mes = timezone.localdate().replace(day=1)
    MetaDeVenda.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                   pessoa=None, mes=mes_anterior(mes),
                                   valor=Decimal("180000"))
    resposta = logado("gil").post(reverse("fila_metas"), {
        "acao": "copiar", "mes": _mes_atual(), "loja": str(rede.centro.pk)})
    assert resposta.status_code == 200
    assert 'value="180000,00"' in resposta.content.decode()
    assert not MetaDeVenda.irrestritos.filter(mes=mes).exists()


def test_soma_dos_vendedores_ao_lado_da_meta_da_loja(rede):
    gil = logado("gil")
    gil.post(reverse("fila_metas"), {
        "acao": "salvar", "mes": _mes_atual(), "loja": str(rede.centro.pk),
        "valor_loja": "50000", f"valor_{rede.caio.pk}": "30000"})
    assert "Vendedores somam R$ 30.000,00 de R$ 50.000,00" in _get(gil)
```

E em `tests/test_fila_modulo.py::test_o_modulo_esta_declarado_com_as_quatro_permissoes`:

```python
    assert {a.rota for a in spec.atalhos} == {
        "/fila/grupos", "/fila/motivos", "/fila/pausas", "/fila/metas"}
    # Os indicadores moram no Início (15/09/2026): não há atalho para eles.
    assert {a.permissao for a in spec.atalhos} == {"fila.cadastros", "fila.metas"}
```

Run: `.superpowers/pt tests/test_fila_tela_metas.py tests/test_fila_modulo.py`
Expected: FAIL (`NoReverseMatch: 'fila_metas'`).

- [ ] **Step 2: Rota e atalho**

`fila/urls.py`: importar `views_metas` e acrescentar `path("fila/metas", views_metas.metas, name="fila_metas"),`.

`fila/modulo.py`, no fim de `atalhos`:

```python
        Atalho(rotulo=_("Metas"), rota="/fila/metas",
               permissao="fila.metas", grupo="Cadastro",
               pai="Fila da vez"),
```

- [ ] **Step 3: A view**

Criar `fila/views_metas.py`:

```python
"""A tela das metas de venda (spec 2026-09-15-fila-metas, "Cadastro").

Um formulário de campos, e não uma tabela: cada linha é um valor do mesmo
formulário, e uma loja tem dezenas de pessoas, não milhares (a R46 vale para
tabela que lista registros). As regras moram em `fila/metas.py`; aqui só se
desenha e se lê o POST.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _

from comum.ambiente import ambiente
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.pedido import id_do_post
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.components import (Alert, Box, Button, Card, Form, FormGrid,
                               Option, PageHeader, Raw, Select, TextInput)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from . import metas as regras
from .acoes import Recusa
from .estado import nome_de
from .valores import em_reais

__all__ = ["metas"]


def _loja_escolhida(request, permitidas):
    """A loja do pedido, só entre as permitidas; a forjada cai na primeira."""
    if request.method == "POST":
        pk = id_do_post(request, "loja")
    else:
        bruto = request.GET.get("loja", "")
        pk = int(bruto) if bruto.isascii() and bruto.isdigit() and len(bruto) <= 18 else None
    return next((l for l in permitidas if l.pk == pk), permitidas[0])


def _endereco(mes, loja) -> str:
    return reverse("fila_metas") + "?" + urlencode({"mes": f"{mes:%Y-%m}", "loja": loja.pk})


def _escolha(mes, loja, permitidas):
    anterior, seguinte = regras.mes_anterior(mes), regras.mes_seguinte(mes)
    campos = [
        TextInput(name="mes", label=_("Mês"), type="month", span=3,
                  value=f"{mes:%Y-%m}"),
    ]
    if len(permitidas) > 1:
        campos.append(Select(name="loja", label=_("Loja"), span=4, value=str(loja.pk),
                             options=[Option(str(l.pk), str(l)) for l in permitidas]))
    else:
        campos.append(Raw(html=f'<input type="hidden" name="loja" value="{loja.pk}">'))
    campos.append(Box(direction="row", gap="sm", children=[
        Button(label=_("Abrir"), variant="primary", type="submit"),
        Button(label=_("Mês anterior"), icon="chevron-left",
               href=_endereco(anterior, loja)),
        Button(label=_("Mês seguinte"), icon_right="chevron-right",
               href=_endereco(seguinte, loja)),
    ]))
    return Card(attrs={"data-metas": "escolha"},
                body=Form(method="get", action=reverse("fila_metas"),
                          children=FormGrid(children=campos)))


def _campo(nome, rotulo, valor, *, erro=None, travado=False, ajuda=None):
    return TextInput(name=nome, label=rotulo, value=valor, span=4, error=erro,
                     disabled=travado, help=ajuda, placeholder=_("Sem meta"),
                     attrs={"inputmode": "decimal", "autocomplete": "off"})


def _desenhar(request, loja, mes, permitidas, editor, *, digitados=None,
              erros=None, aviso=None) -> HttpResponse:
    from plataforma.site import montar_site

    digitados, erros = digitados or {}, erros or {}
    encerrado = regras.mes_encerrado(mes)
    linhas = regras.pessoas_da_lista(loja, mes, editor)
    da_loja = regras.meta_da_loja(loja, mes)
    soma = sum((l.valor for l in linhas if l.valor is not None), regras.ZERO)

    def valor(chave, salvo):
        return digitados.get(chave, regras.valor_do_campo(salvo))

    subtitulo = (_("Vendedores somam %(soma)s de %(loja)s")
                 % {"soma": em_reais(soma), "loja": em_reais(da_loja)}
                 if da_loja is not None else None)
    pessoas = []
    for l in linhas:
        ajuda = None
        if l.propria:
            ajuda = _("A sua meta é definida por outra pessoa.")
        elif not l.na_loja:
            ajuda = _("Não está mais nesta loja.")
        pessoas.append(_campo(f"valor_{l.pessoa.pk}", nome_de(l.pessoa),
                              valor(str(l.pessoa.pk), l.valor),
                              erro=erros.get(str(l.pessoa.pk)),
                              travado=encerrado or l.propria, ajuda=ajuda))

    corpo = [
        campo_csrf(request),
        Raw(html=f'<input type="hidden" name="mes" value="{mes:%Y-%m}">'
                 f'<input type="hidden" name="loja" value="{loja.pk}">'),
        Card(title=_("Meta da loja"), subtitle=subtitulo, body=FormGrid(children=[
            _campo("valor_loja", str(loja), valor("loja", da_loja),
                   erro=erros.get("loja"), travado=encerrado)])),
        Card(title=_("Metas dos vendedores"),
             body=FormGrid(children=pessoas) if pessoas else Raw(
                 html=f'<p class="ind-vazio">{_("Ninguém participa da fila nesta loja.")}</p>')),
    ]
    if not encerrado:
        corpo.append(Box(direction="row", gap="sm", children=[
            Button(label=_("Salvar metas"), variant="primary", type="submit",
                   attrs={"name": "acao", "value": "salvar"}),
            Button(label=_("Copiar metas do mês anterior"), type="submit",
                   attrs={"name": "acao", "value": "copiar"}),
        ]))

    conteudo = [
        aviso_de_personificacao(request),
        PageHeader(title=_("Metas de venda"),
                   subtitle=_("Quanto cada loja e cada vendedor deve vender no mês.")),
        _escolha(mes, loja, permitidas),
    ]
    if encerrado:
        conteudo.append(Alert(tone="info", message=str(regras.MES_ENCERRADO)))
    if aviso:
        conteudo.append(aviso)
    conteudo.append(Form(method="post", action=reverse("fila_metas"), children=corpo))

    with use_environment(ambiente()):
        site = montar_site(request)
        pagina = site.page(title=_("Metas de venda"), width="full",
                           stylesheets=["/static/fila/indicadores.css"],
                           content=conteudo, crumbs=[Crumb(_("Metas de venda"))],
                           user=request.usuario)
        return render(pagina)


@exigir_permissao("fila.metas")
@exigir_modulo_ligado("fila")
def metas(request) -> HttpResponse:
    editor = usuario_de(request.usuario)
    empresa = empresa_atual(request)
    permitidas = regras.lojas_com_metas(editor, empresa)
    if not permitidas:
        return _desenhar_sem_loja(request)
    loja = _loja_escolhida(request, permitidas)
    dados = request.POST if request.method == "POST" else request.GET
    mes = regras.mes_do_texto(dados.get("mes"))

    if request.method != "POST":
        return _desenhar(request, loja, mes, permitidas, editor)

    linhas = regras.pessoas_da_lista(loja, mes, editor)
    if request.POST.get("acao") == "copiar":
        copia = regras.copiar_do_anterior(loja, mes, linhas)
        aviso = Alert(tone="info", message=(
            _("Metas do mês anterior copiadas nos campos vazios. Confira e salve.")
            if copia else _("O mês anterior não tem meta para copiar.")))
        return _desenhar(request, loja, mes, permitidas, editor,
                         digitados=copia, aviso=aviso)

    chaves = ["loja", *(str(l.pessoa.pk) for l in linhas)]
    campos = {"loja": "valor_loja", **{str(l.pessoa.pk): f"valor_{l.pessoa.pk}"
                                       for l in linhas}}
    valores = {c: request.POST.get(campos[c]) for c in chaves}
    try:
        regras.gravar(loja, mes, editor, valores, request=request)
    except Recusa as recusa:
        return _desenhar(request, loja, mes, permitidas, editor,
                         aviso=Alert(tone="danger", message=str(recusa)))
    except regras.ValoresInvalidos as invalidos:
        digitados = {c: v for c, v in valores.items() if v is not None}
        return _desenhar(request, loja, mes, permitidas, editor,
                         digitados=digitados, erros=invalidos.erros,
                         aviso=Alert(tone="danger",
                                     message=_("Corrija os valores marcados. Nada foi salvo.")))
    return HttpResponseRedirect(_endereco(mes, loja))


def _desenhar_sem_loja(request) -> HttpResponse:
    from plataforma.site import montar_site

    with use_environment(ambiente()):
        site = montar_site(request)
        pagina = site.page(title=_("Metas de venda"), width="full", content=[
            aviso_de_personificacao(request),
            PageHeader(title=_("Metas de venda")),
            Alert(tone="info", message=_("Nenhuma loja em que você define metas.")),
        ], crumbs=[Crumb(_("Metas de venda"))], user=request.usuario)
        return render(pagina)
```

A tela responde 200 com o erro na própria página, como `views_cadastros`. Conferir, antes de rodar: `Box` aceita `direction` e `gap` (`grep -n "class Box" -A20 nucleo/components/containers.py`); se o nome do espaçamento for outro, usar o dele. Os ícones `chevron-left` e `chevron-right` precisam existir em `nucleo.icons.get` (`.venv/bin/python -c "from nucleo.icons import get; get('chevron-left'); get('chevron-right')"` com `DJANGO_SETTINGS_MODULE` e `KRONOS_BANCO` exportados); se não existirem, tirar o ícone.

- [ ] **Step 4: Rodar e ver com dente**

Run: `.superpowers/pt tests/test_fila_tela_metas.py tests/test_fila_modulo.py tests/test_guarda.py tests/test_guarda_modulo.py tests/test_personificacao.py tests/test_regra_tabela.py tests/test_id_do_post.py tests/test_sublinhado_e_o_gettext.py`
Expected: PASS.

Dente (um de cada vez, voltando depois):
- em `_loja_escolhida`, trocar `permitidas` pela lista de todas as filiais da empresa → `test_gerente_ve_so_a_loja_dele...` FAIL.
- em `_desenhar`, `travado=encerrado` para as pessoas (sem `or l.propria`) → `test_salvar_grava_e_a_propria_linha_vem_travada` FAIL.

- [ ] **Step 5: Contagem de arquivos no CLAUDE.md**

Esta tarefa e a Task 1 criam dois arquivos de teste. Contar: `ls tests/test_*.py | wc -l`, e trocar os "108 arquivos" do `CLAUDE.md` (duas ocorrências: §3 e "Como rodar") pelo número. Run: `.superpowers/pt tests/test_documentacao_nao_mente.py` → PASS.

- [ ] **Step 6: Conferir em captura**

Servidor de desenvolvimento (se não estiver de pé):

```bash
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/fila_zero \
  .venv/bin/python manage.py migrate
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/fila_zero \
  .venv/bin/python manage.py runserver 0.0.0.0:8005   # em segundo plano
```

Entrar como `sylvia@sylvia.test` / `fila1234`, abrir `/fila/metas`, salvar a meta da loja e de dois vendedores, copiar no mês seguinte, abrir o mês passado. Capturas de página inteira em 1366 e 390. Conferir: campos alinhados, erro ao lado do campo, linha travada legível, botões quebrando linha no celular. Ajustar o que destoar usando só componentes e tokens do tema.

- [ ] **Step 7: Commit**

Mensagem: `feat: a tela das metas de venda`, com o corpo dizendo por que não é tabela, o que o POST confere e como "copiar" funciona.

---

### Task 5: A meta no painel do Início e no ranking

**Files:**
- Modify: `fila/metas.py`, `fila/indicadores.py`, `fila/views_indicadores.py`, `fila/static/fila/indicadores.css`, `tests/test_fila_metas.py`, `tests/test_fila_tela_indicadores.py`

**Interfaces:**
- Consumes: `acompanhar`, `Acompanhamento` (Task 2); `MetaDeVenda`; `fila.indicadores.Recorte`, `numeros(recorte, vendedor=None) -> Numeros`; `fila.periodo.Periodo`, `inicio_do_dia`.
- Produces:
  - `fila.metas.MetaDoRecorte` (frozen): `acompanhamento: Acompanhamento`, `lojas_com_meta: int`, `lojas: int`, `soma_vendedores: Decimal` (metas de pessoa das lojas com meta, no mês).
  - `fila.metas.mes_do_periodo(periodo) -> date | None` (só `mes` e `mes_passado`).
  - `fila.metas.meta_do_recorte(recorte, agora=None) -> MetaDoRecorte | None`.
  - `fila.indicadores.ranking(recorte, mes: date | None = None)`: com `mes`, cada pessoa ganha `meta: Decimal | None` e `pct_meta: float | None`.
  - `fila.indicadores.ORDENAVEIS_DO_RANKING_COM_META` (as de sempre mais `meta` e `pct_meta`).
  - `fila.views_indicadores._painel(periodo, loja, n, a, anterior, fatias, meta=None)`.

- [ ] **Step 1: Os testes das contas**

Acrescentar a `tests/test_fila_metas.py`:

```python
# --- A meta do recorte (painel) e o ranking --------------------------------------

from tests.test_fila_indicadores import atendimento  # noqa: E402


def _periodo(chave):
    from fila.periodo import periodo_do_pedido

    return periodo_do_pedido({"periodo": chave})


def test_meta_do_recorte_so_em_mes_e_so_das_lojas_com_meta(loja):
    from fila.indicadores import Recorte
    from fila.metas import meta_do_recorte, primeiro_do_mes

    centro = nova_loja(loja.empresa, "Centro")
    agora = timezone.now()
    mes = primeiro_do_mes(timezone.localdate(agora))
    meta(loja, valor="10000", mes=mes)
    hoje = timezone.localtime(agora).replace(minute=0, second=0, microsecond=0)
    atendimento(loja, loja.ana, hoje, hoje, vendeu="1000")
    atendimento(loja, loja.bia, hoje, hoje, vendeu="9000", filial=centro)

    duas = (loja.matriz, centro)
    m = meta_do_recorte(Recorte(loja.empresa, duas, _periodo("mes")), agora)
    # O Centro não tem meta: nem a meta nem o vendido dele entram.
    assert (m.lojas_com_meta, m.lojas) == (1, 2)
    assert m.acompanhamento.vendido == Decimal("1000")
    assert m.acompanhamento.atingido == 10.0
    meta(loja, pessoa=loja.ana, valor="6000", mes=mes)
    meta(loja, pessoa=loja.bia, valor="9999", mes=mes, filial=centro)  # loja sem meta
    m = meta_do_recorte(Recorte(loja.empresa, duas, _periodo("mes")), agora)
    assert m.soma_vendedores == Decimal("6000")
    assert meta_do_recorte(Recorte(loja.empresa, duas, _periodo("7dias")), agora) is None
    assert meta_do_recorte(Recorte(loja.empresa, (centro,), _periodo("mes")), agora) is None


def test_ranking_com_meta_e_porcentagem(loja):
    from fila.indicadores import Recorte, ranking
    from fila.metas import primeiro_do_mes

    mes = primeiro_do_mes(timezone.localdate())
    meta(loja, pessoa=loja.ana, valor="4000", mes=mes)
    hoje = timezone.localtime().replace(minute=0, second=0, microsecond=0)
    atendimento(loja, loja.ana, hoje, hoje, vendeu="1000")
    atendimento(loja, loja.bia, hoje, hoje, vendeu="500")
    linhas = {p.nome: p for p in ranking(
        Recorte(loja.empresa, (loja.matriz,), _periodo("mes")), mes)}
    assert linhas["Ana"].meta == Decimal("4000") and linhas["Ana"].pct_meta == 25.0
    assert linhas["Bia"].meta is None and linhas["Bia"].pct_meta is None
```

Run: `.superpowers/pt tests/test_fila_metas.py`
Expected: FAIL (`ImportError: cannot import name 'meta_do_recorte'`).

- [ ] **Step 2: `meta_do_recorte` em `fila/metas.py`**

Acrescentar `"MetaDoRecorte", "mes_do_periodo", "meta_do_recorte"` ao `__all__` e:

```python
def mes_do_periodo(periodo) -> "date | None":
    """O mês do calendário do período, se ele for um mês inteiro dos atalhos.
    Em "7 dias" ou num intervalo, a meta do mês não tem com o que comparar."""
    if periodo.chave not in ("mes", "mes_passado"):
        return None
    return timezone.localdate(periodo.de).replace(day=1)


@dataclass(frozen=True)
class MetaDoRecorte:
    acompanhamento: Acompanhamento
    lojas_com_meta: int
    lojas: int
    soma_vendedores: Decimal


def meta_do_recorte(recorte, agora: "datetime | None" = None) -> "MetaDoRecorte | None":
    """A meta das lojas do recorte contra o vendido DESSAS lojas.

    Em "Todas as lojas" com uma loja sem meta, somar a meta das outras e
    comparar com o vendido de todas faria a meta parecer batida por causa da
    loja sem meta; por isso as duas pontas saem das mesmas lojas.
    """
    from .indicadores import Recorte, numeros
    from .models import MetaDeVenda
    from .periodo import Periodo, inicio_do_dia

    agora = agora or timezone.now()
    mes = mes_do_periodo(recorte.periodo)
    if mes is None:
        return None
    por_loja = dict(MetaDeVenda.objects.da_empresa(recorte.empresa)
                    .filter(filial__in=recorte.lojas, mes=mes, pessoa__isnull=True)
                    .values_list("filial_id", "valor"))
    if not por_loja:
        return None
    com_meta = tuple(l for l in recorte.lojas if l.pk in por_loja)
    # M2: o painel diz se as metas dos vendedores cobrem a da loja.
    soma_vendedores = sum(
        MetaDeVenda.objects.da_empresa(recorte.empresa)
        .filter(filial__in=com_meta, mes=mes, pessoa__isnull=False)
        .values_list("valor", flat=True), ZERO)
    vendido = numeros(Recorte(recorte.empresa, com_meta, recorte.periodo)).vendido
    ate_ontem = None
    if recorte.periodo.ate > agora:
        ontem = Periodo(recorte.periodo.de, inicio_do_dia(timezone.localdate(agora)),
                        "intervalo", "")
        ate_ontem = numeros(Recorte(recorte.empresa, com_meta, ontem)).vendido
    return MetaDoRecorte(
        acompanhar(sum(por_loja.values(), ZERO), vendido, mes, agora, ate_ontem),
        len(com_meta), len(recorte.lojas), soma_vendedores)
```

- [ ] **Step 3: O ranking com meta em `fila/indicadores.py`**

Acrescentar `Cast` ao import de `django.db.models.functions` e `date` ao de `datetime`. Mudar a assinatura para `def ranking(recorte: Recorte, mes: "date | None" = None):`, guardar a consulta de hoje em `consulta = (Usuario.objects ... )` e, antes do `return`:

```python
    if mes is None:
        return consulta
    # A meta do vendedor em "Todas as lojas" é a soma das metas dele nas lojas
    # do recorte, e o % é o vendido dele nessas lojas sobre essa soma. Sem
    # Coalesce: sem meta é "—", e não meta zero.
    from .models import MetaDeVenda

    metas = (MetaDeVenda.objects.da_empresa(recorte.empresa)
             .filter(filial__in=recorte.lojas, mes=mes, pessoa__isnull=False))
    real = FloatField()
    return (consulta
            .annotate(meta=Subquery(
                metas.filter(pessoa=OuterRef("pk")).order_by().values("pessoa")
                .annotate(x=Sum("valor")).values("x")[:1], output_field=_DINHEIRO))
            .annotate(pct_meta=Case(
                When(meta__isnull=True, then=Value(None)),
                default=ExpressionWrapper(
                    Cast("vendido", real) * 100.0 / Cast("meta", real),
                    output_field=real),
                output_field=real)))
```

e, depois de `ORDENAVEIS_DO_RANKING`:

```python
ORDENAVEIS_DO_RANKING_COM_META = {
    **ORDENAVEIS_DO_RANKING,
    "meta": ("meta", "nome"),
    "pct_meta": ("pct_meta", "nome"),
}
```

Acrescentar `"ORDENAVEIS_DO_RANKING_COM_META"` ao `__all__`. Arredondar `pct_meta` na tela (`_pct`), não na consulta.

Run: `.superpowers/pt tests/test_fila_metas.py` → PASS.

- [ ] **Step 4: Os testes da tela**

Acrescentar a `tests/test_fila_tela_indicadores.py`:

```python
# --- A meta no painel e no ranking (entrega 3) -------------------------------

def _meta_da_loja(rede, loja, valor, pessoa=None):
    from fila.metas import primeiro_do_mes
    from fila.models import MetaDeVenda

    return MetaDeVenda.irrestritos.create(
        empresa=rede.empresa, filial=loja, pessoa=pessoa,
        mes=primeiro_do_mes(timezone.localdate()), valor=Decimal(valor))


def test_a_faixa_da_meta_aparece_no_mes_e_some_em_7_dias(rede):
    _meta_da_loja(rede, rede.centro, "1000")
    _venda_hoje(rede, rede.caio, rede.centro, "250")
    gil = logado("gil")
    mes = _html(gil, periodo="mes")
    assert 'data-ind="meta"' in mes and "25,0%" in mes and "Faltam R$ 750,00" in mes
    assert 'data-ind="meta"' not in _html(gil, periodo="7dias")


def test_todas_as_lojas_diz_quantas_tem_meta(rede):
    _meta_da_loja(rede, rede.centro, "1000")
    _meta_da_loja(rede, rede.centro, "600", pessoa=rede.caio)
    html = _html(logado("sara"), periodo="mes")
    assert "1 de 2 lojas com meta" in html
    assert "As metas dos vendedores somam R$ 600,00, abaixo da meta da loja." in html


def test_ranking_ganha_meta_e_porcentagem_ordenaveis(rede):
    _meta_da_loja(rede, rede.centro, "1000", pessoa=rede.caio)
    _venda_hoje(rede, rede.caio, rede.centro, "500")
    html = _html(logado("gil"), periodo="mes", ordenar="-pct_meta")
    assert "% da meta" in html and "50,0%" in html
    assert "% da meta" not in _html(logado("gil"), periodo="hoje")
```

Run: `.superpowers/pt tests/test_fila_tela_indicadores.py` → FAIL nos três.

- [ ] **Step 5: A faixa e as colunas em `fila/views_indicadores.py`**

Imports: `from . import metas as regras_de_meta`.

Funções novas, antes de `_painel`:

```python
def _faixa_da_meta(m) -> str:
    """A meta do mês dentro do painel, entre os números e o gráfico: é a régua
    do vendido que está logo acima."""
    a = m.acompanhamento
    if a.encerrado:
        apoio = (_("Bateu a meta, %(acima)s acima.") % {"acima": em_reais(a.excedente)}
                 if a.batida else
                 _("Ficou em %(pct)s da meta, faltaram %(falta)s.")
                 % {"pct": _pct(a.atingido), "falta": em_reais(a.falta)})
    elif a.batida:
        apoio = _("Meta batida, %(acima)s acima.") % {"acima": em_reais(a.excedente)}
    else:
        apoio = (_("Faltam %(falta)s, %(por_dia)s por dia até %(ultimo)s.")
                 % {"falta": em_reais(a.falta), "por_dia": em_reais(a.por_dia),
                    "ultimo": f"{a.ultimo_dia:%d/%m}"})
        apoio += " " + (_("No ritmo atual, fecha em %(projecao)s.")
                        % {"projecao": em_reais(a.projecao)}
                        if a.projecao is not None else _("Projeção a partir de amanhã."))
    if m.soma_vendedores:
        cobre = (_("As metas dos vendedores somam %(soma)s e cobrem a da loja.")
                 if m.soma_vendedores >= a.meta else
                 _("As metas dos vendedores somam %(soma)s, abaixo da meta da loja."))
        apoio += " " + cobre % {"soma": em_reais(m.soma_vendedores)}
    if m.lojas_com_meta < m.lojas:
        apoio += " " + (_("%(com)s de %(total)s lojas com meta: a meta e o vendido desta faixa são só delas.")
                        % {"com": m.lojas_com_meta, "total": m.lojas})
    return format_html(
        '<div class="ind-meta" data-ind="meta">'
        '<div class="ind-meta-cab"><span>{} <b>{}</b></span><strong>{}</strong></div>'
        '<div class="ind-meta-barra{}"><span style="width: {}%"></span></div>'
        '<p class="ind-meta-apoio">{}</p></div>',
        _("Meta do mês"), em_reais(a.meta), _pct(a.atingido),
        " batida" if a.batida else "", f"{min(a.atingido, 100):.1f}", apoio)
```

Em `_painel`, acrescentar o parâmetro `meta=None` e trocar o `Raw` do corpo por:

```python
        body=Raw(html=format_html(
            '<div class="ind-painel"><div class="ind-abas" role="radiogroup" aria-label="{}">{}</div>'
            '{}<div class="ind-series">{}</div></div>',
            _("Número mostrado no gráfico"), abas,
            _faixa_da_meta(meta) if meta else "", series)))
```

Em `_colunas`, receber `com_meta=False` e, no fim, quando verdadeiro:

```python
    if com_meta:
        colunas += [
            Column("meta", pagina.cabecalho("meta", str(_("Meta"))), align="num",
                   render=lambda p: _dinheiro(p.meta)),
            Column("pct_meta", pagina.cabecalho("pct_meta", str(_("% da meta"))),
                   align="num", render=lambda p: _pct(p.pct_meta)),
        ]
    return colunas
```

(trocar o `return [ ... ]` atual por `colunas = [ ... ]`).

Em `blocos_dos_indicadores`:

```python
    mes_da_meta = regras_de_meta.mes_do_periodo(periodo)
    blocos = [
        _filtros(request, periodo, permitidas, loja),
        _esquecidos(ind.esquecidos(empresa, lojas)),
        _painel(periodo, loja, n, a, anterior, ind.por_dia(recorte),
                meta=regras_de_meta.meta_do_recorte(recorte)),
        _listas(recorte, n),
    ]
    listagem = montar_pagina(request, ind.ranking(recorte, mes_da_meta),
                             ordenaveis=(ind.ORDENAVEIS_DO_RANKING_COM_META
                                         if mes_da_meta else ind.ORDENAVEIS_DO_RANKING),
                             padrao=ind.PADRAO_DO_RANKING,
                             filtraveis=_FILTRAVEIS,
                             preservar=("periodo", "de", "ate", "loja"))
    blocos.append(Card(title=_("Ranking de vendedores"), padded=False, body=[
        listagem.barra,
        Table(columns=_colunas(listagem, com_meta=mes_da_meta is not None),
              rows=listagem.linhas),
        listagem.paginacao,
    ]))
```

- [ ] **Step 6: O desenho da faixa**

Em `fila/static/fila/indicadores.css`, depois do bloco das abas:

```css
/* --- A meta do mês, entre as abas e o gráfico ---------------------------- */

.ind-meta { padding: 16px var(--card-pad) 4px; display: grid; gap: 8px; }
.ind-meta-cab { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; font-size: 13.5px; color: var(--on-surface-2); }
.ind-meta-cab b { color: var(--on-surface); font-variant-numeric: tabular-nums; }
.ind-meta-cab strong { font-family: var(--font-display); font-size: 20px; font-weight: 800; color: var(--on-surface); font-variant-numeric: tabular-nums; }
.ind-meta-barra { height: 10px; border-radius: 5px; background: var(--surface-2); overflow: hidden; }
.ind-meta-barra > span { display: block; height: 100%; border-radius: 5px; background: var(--primary); }
/* Batida, a barra cheia fica verde: a mesma cor da seta que sobe. */
.ind-meta-barra.batida > span { background: var(--ok); }
.ind-meta-apoio { margin: 0; font-size: 13px; color: var(--on-surface-2); font-variant-numeric: tabular-nums; }
```

- [ ] **Step 7: Rodar, ver com dente e conferir em captura**

Run: `.superpowers/pt tests/test_fila_metas.py tests/test_fila_tela_indicadores.py tests/test_fila_indicadores.py tests/test_regra_tabela.py tests/test_variavel_de_cor_existe.py` → PASS.

Dente (um de cada vez, voltando depois):
- em `meta_do_recorte`, calcular o vendido com `recorte` inteiro em vez de `com_meta` → `test_meta_do_recorte...` FAIL.
- em `mes_do_periodo`, aceitar qualquer chave → `test_a_faixa_da_meta_aparece_no_mes_e_some_em_7_dias` FAIL.

Captura do Início (1366 e 390) em "Este mês" com meta cadastrada pela tela da Task 4, em "Mês passado" e numa loja sem meta. Conferir que a faixa não empurra o gráfico para fora do cartão e que o ranking com as duas colunas continua rolando dentro do cartão no celular.

- [ ] **Step 8: Commit**

Mensagem: `feat: a meta do mês no painel do Início e no ranking`, com o corpo explicando a comparação só das lojas com meta e a projeção.

---

### Task 6: A meta em "Seus números"

**Files:**
- Modify: `fila/tela.py`, `fila/estado.py`, `fila/templates/fila/_meus.html`, `fila/static/fila/fila.css`, `tests/test_fila_pagina.py`

**Interfaces:**
- Consumes: `acompanhar`, `primeiro_do_mes` (Task 2); `MetaDeVenda`.
- Produces: `MeusNumeros.meta: Acompanhamento | None`; `versao_da_fila(filial)` passa a mudar quando uma meta da loja no mês muda.

- [ ] **Step 1: Os testes**

Acrescentar a `tests/test_fila_pagina.py`:

```python
# --- A meta em "Seus números" (entrega 3) -------------------------------------

def _meta(loja, pessoa, valor, filial=None):
    from decimal import Decimal

    from django.utils import timezone

    from fila.models import MetaDeVenda

    return MetaDeVenda.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, pessoa=pessoa,
        mes=timezone.localdate().replace(day=1), valor=Decimal(valor))


def test_seus_numeros_mostram_a_meta_da_propria_pessoa(loja):
    _meta(loja, loja.ana, "4000")
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="vendeu",
          grupo=[str(loja.cad.grupo.pk)], valor=["1.000"])
    html = _html(ana)
    assert "Meta do mês" in html and "R$ 4.000,00" in html and "25%" in html
    assert "Faltam R$ 3.000,00" in html
    assert "Meta do mês" not in _html(logado("bia"))


def test_meta_de_outra_loja_nao_aparece(loja):
    centro = nova_loja(loja.empresa, "Centro")
    _meta(loja, loja.ana, "4000", filial=centro)
    assert "Meta do mês" not in _html(logado("ana"))


def test_a_versao_muda_quando_a_meta_muda(loja):
    from fila.estado import versao_da_fila

    antes = versao_da_fila(loja.matriz)
    m = _meta(loja, loja.ana, "4000")
    depois = versao_da_fila(loja.matriz)
    assert depois != antes
    m.valor = m.valor + 1
    m.save()
    assert versao_da_fila(loja.matriz) != depois
```

Run: `.superpowers/pt tests/test_fila_pagina.py` → FAIL nos três.

- [ ] **Step 2: A meta no pedaço e na versão**

`fila/tela.py`: `MeusNumeros` ganha o campo `meta: object = None` (último, com padrão) e o docstring ganha "e a meta do mês, se houver". Em `_meus_numeros`:

```python
    from .metas import acompanhar, primeiro_do_mes
    from .models import MetaDeVenda

    mes = numeros(Recorte(filial.empresa, lojas, periodo_do_pedido({"periodo": "mes"})),
                  vendedor=pessoa)
    # A meta da loja em que a pessoa está, como os números ao lado (P-2 do
    # plano dos indicadores). Sem projeção: o vendedor precisa do "quanto por
    # dia", e a projeção é conversa da gestão.
    minha = (MetaDeVenda.objects.da_empresa(filial.empresa)
             .filter(filial=filial, pessoa=pessoa,
                     mes=primeiro_do_mes(timezone.localdate()))
             .first())
    return MeusNumeros(
        hoje=numeros(Recorte(filial.empresa, lojas, periodo_do_pedido({"periodo": "hoje"})),
                     vendedor=pessoa),
        mes=mes,
        posicao=posicao_no_mes(pessoa, filial),
        meta=acompanhar(minha.valor, mes.vendido, minha.mes) if minha else None)
```

(importar `timezone` de `django.utils` se `fila/tela.py` ainda não importa).

`fila/estado.py`, em `versao_da_fila`, antes do `return`:

```python
    # A meta do mês aparece em "Seus números": o gerente que troca uma meta
    # precisa ver a tela do vendedor mudar sem ele recarregar (spec das metas).
    from django.utils import timezone

    from .models import MetaDeVenda

    metas = (MetaDeVenda.objects.da_empresa(filial.empresa)
             .filter(filial=filial, mes=timezone.localdate().replace(day=1))
             .aggregate(n=Count("pk"), quando=Max("alterada_em")))
```

e no `return`, acrescentar `f".{metas['n']}.{marca(metas['quando'])}"` ao fim da string.

- [ ] **Step 3: O template e o desenho**

`fila/templates/fila/_meus.html`, depois do `<div class="fila-meus-corpo">…</div>`:

```jinja
  {% if meus.meta %}
  {% set m = meus.meta %}
  <div class="fila-meus-meta">
    <p class="fila-meus-meta-cab"><span>{{ traduzir("Meta do mês") }} <b>{{ m.meta|reais }}</b></span><strong>{{ "%.0f"|format(m.atingido) }}%</strong></p>
    <div class="fila-meus-meta-barra{% if m.batida %} batida{% endif %}"><span style="width: {{ "%.1f"|format([m.atingido, 100]|min) }}%"></span></div>
    <p class="fila-meus-meta-apoio">{% if m.batida %}{{ traduzir("Meta batida") }}{% else %}{{ traduzir("Faltam") }} {{ m.falta|reais }}, {{ m.por_dia|reais }} {{ traduzir("por dia") }}{% endif %}</p>
  </div>
  {% endif %}
```

`fila/static/fila/fila.css`, perto das regras `.fila-meus-*`:

```css
/* A meta do mês em "Seus números": a mesma régua do painel da gestão. */
.fila-meus-meta { display: grid; gap: 6px; padding: 12px 16px 14px; border-top: 1px solid var(--outline-2); }
.fila-meus-meta-cab { margin: 0; display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-size: 13.5px; color: var(--on-surface-2); }
.fila-meus-meta-cab b { color: var(--on-surface); font-variant-numeric: tabular-nums; }
.fila-meus-meta-cab strong { font-family: var(--font-display); font-size: 18px; color: var(--on-surface); font-variant-numeric: tabular-nums; }
.fila-meus-meta-barra { height: 8px; border-radius: 4px; background: var(--surface-2); overflow: hidden; }
.fila-meus-meta-barra > span { display: block; height: 100%; background: var(--primary); }
.fila-meus-meta-barra.batida > span { background: var(--ok); }
.fila-meus-meta-apoio { margin: 0; font-size: 13px; color: var(--on-surface-2); font-variant-numeric: tabular-nums; }
```

Conferir que `traduzir` e o filtro `reais` existem no ambiente da fila (`grep -n "traduzir\|reais" fila/ambiente.py`) e que o Jinja aceita `[a, b]|min` (filtro nativo).

- [ ] **Step 4: Rodar, ver com dente e conferir em captura**

Run: `.superpowers/pt tests/test_fila_pagina.py tests/test_fila_estado.py` → PASS (se `tests/test_fila_estado.py` não existir, só o primeiro).

Dente (um de cada vez, voltando depois):
- tirar `filial=filial,` do filtro da meta em `_meus_numeros` → `test_meta_de_outra_loja_nao_aparece` FAIL.
- tirar `marca(metas['quando'])` da versão → `test_a_versao_muda_quando_a_meta_muda` FAIL.

Captura de `/fila` como `bia@sylvia.test` com meta cadastrada, em 390 e 1366.

- [ ] **Step 5: Commit**

Mensagem: `feat: a meta do mês em "Seus números"`, com o corpo explicando por que sem projeção e por que a versão olha `alterada_em`.

---

### Task 7: Castelhano, documentação e a suíte

**Files:**
- Modify: `locale/portal.pot`, `locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `CLAUDE.md`, `docs/superpowers/specs/2026-09-15-fila-metas-design.md`

- [ ] **Step 1: Extrair e traduzir**

```bash
.venv/bin/python -m babel.messages.frontend extract -F babel.cfg -o locale/portal.pot \
  --no-location --omit-header -k _ -k gettext -k gettext_lazy -k "ngettext:1,2" -k traduzir \
  --input-dirs=contas,plataforma,comum,modulos,fila
.venv/bin/python -m babel.messages.frontend update -i locale/portal.pot -d locale -D django \
  --no-fuzzy-matching --ignore-obsolete
```

Listar os vazios:

```bash
.venv/bin/python - <<'EOF'
from babel.messages.pofile import read_po
cat = read_po(open("locale/es/LC_MESSAGES/django.po", "rb"))
for m in cat:
    if m.id and (not m.string or (isinstance(m.string, tuple) and not all(m.string))):
        print(repr(m.id))
EOF
```

Preencher cada um em castelhano do Paraguai, registro "usted" (ex.: "Metas de venda" → "Metas de venta"; "Faltam" → "Faltan"; "Meta batida" → "Meta alcanzada"; "Mês encerrado: as metas não se editam mais." → "Mes cerrado: las metas ya no se editan."). Compilar:

```bash
.venv/bin/python -m babel.messages.frontend compile -d locale -D django
```

Run: `.superpowers/pt tests/test_castelhano.py tests/test_idioma.py` (os que existirem: `ls tests | grep -i "idioma\|castelhano"`) → PASS.

- [ ] **Step 2: Documentação**

`CLAUDE.md`:
- §9, item 5: `5. **As metas da fila** são a entrega 3: spec em `docs/superpowers/specs/2026-09-15-fila-metas-design.md` e plano em `docs/superpowers/plans/2026-09-15-fila-metas.md`.` (se tudo desta entrega entrou, trocar por uma linha dizendo que foram feitas e remover do "em aberto").
- §10: tabela "Quem pode o quê" ganha `| `fila.metas` | a tela `/fila/metas` e as metas da loja em que está |`, e uma subseção **"As metas (entrega 3)"** com quatro itens: a tabela `MetaDeVenda` (pessoa nula = loja) e as travas no banco; as regras em `fila/metas.py` com `agora` recebido; ninguém define a própria e mês encerrado não se edita, conferidos no POST; a projeção pelos dias fechados.

Spec: trocar **Estado** para `implementado na branch `metas` (plano de 15/09/2026)`.

Run: `.superpowers/pt tests/test_documentacao_nao_mente.py` → PASS.

- [ ] **Step 3: A suíte inteira**

```bash
.superpowers/pt > .superpowers/suite.log 2>&1; echo EXIT=$? >> .superpowers/suite.log
```

Em segundo plano; ler `tail -5 .superpowers/suite.log` quando aparecer `EXIT=`. Expected: `EXIT=0`. Falha: ler o `E ` do log, corrigir na tarefa que a causou, rodar de novo.

- [ ] **Step 4: Commit**

Mensagem: `docs: as metas no CLAUDE.md, no spec e em castelhano`.

---

## Self-review do plano

- **Cobertura do spec:** M1–M3 (registro, Task 1); M4 (permissão, Task 1; própria travada, Tasks 3 e 4); M5 (contas, Task 2; painel, Task 5; "Seus números", Task 6); M6 (mês encerrado e copiar, Tasks 2, 3 e 4). "Quem vê o quê" (Tasks 1 e 4). Auditoria (Tasks 1 e 3). Painel: faixa, "N de M lojas com meta", ranking com Meta e % ordenáveis (Task 5). "Seus números" e a versão (Task 6). Isolamento: todas as consultas por `objects.da_empresa`. "Como se prova": registro (Task 1), cadastro (Tasks 3 e 4), alcance (Tasks 3 e 4), cálculo com relógio fixo (Task 2), painel (Task 5), "Seus números" (Task 6), varreduras (Tasks 4, 5 e 7).
- **Soma dos vendedores cobre a da loja (M2):** no cadastro (Task 4, subtítulo "Vendedores somam") e no painel (Task 5, frase na faixa).
- **Nomes:** `MetaDeVenda`, `acompanhar`, `Acompanhamento.batida`, `pessoas_da_lista`, `Linha(pessoa, valor, na_loja, propria)`, `gravar(loja, mes, editor, valores, *, agora, request)`, `copiar_do_anterior(loja, mes, linhas)`, `valor_do_campo`, `meta_do_recorte`, `MetaDoRecorte(acompanhamento, lojas_com_meta, lojas)`, `mes_do_periodo`, `ranking(recorte, mes)`, `ORDENAVEIS_DO_RANKING_COM_META` conferidos entre as tarefas.
- **Verificações antes de escrever código** estão no próprio passo (assinatura de `render`, `Box`, ícones, filtros do ambiente da fila), porque dependem do `nucleo` e não foram abertas ao escrever o plano.
