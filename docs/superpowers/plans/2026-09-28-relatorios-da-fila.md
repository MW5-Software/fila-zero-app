# Relatórios da fila — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma tela `/fila/relatorios` em que dono, supervisor e gerente geram, em PDF e Excel, o relatório das lojas que alcançam, por dia, ontem, semana (7 dias), mês e mês passado.

**Architecture:** Três peças. `fila/relatorio.py` monta o relatório como DADO (seções com colunas tipadas e linhas), só com as contas que o painel já usa (`fila/indicadores.py`, `fila/metas.py`). `fila/relatorio_saida.py` transforma esse dado em Excel (openpyxl, uma aba por seção) e em página de impressão (template Jinja da fila). `fila/views_relatorios.py` é a tela: resolve o recorte pela MESMA porta do painel (extraída de `views_indicadores.blocos_dos_indicadores`) e devolve a tela ou o arquivo pelo `?formato=`.

**Tech Stack:** Django 5.2, Jinja2 (ambiente da fila), openpyxl (já dependência), pytest + Postgres (`KRONOS_BANCO`).

**Spec:** `docs/superpowers/specs/2026-09-28-relatorios-da-fila-design.md`

## Global Constraints

- Permissão da tela: `fila.relatorios` (nenhuma permissão nova).
- Lojas: só por `fila.indicadores.lojas_com_relatorio`; empresas: só por `empresas_com_relatorio`; `?loja=`/`?empresa=` só escolhem DENTRO do alcance.
- Períodos, nesta ordem e com estes rótulos: `hoje` "Diário (hoje)", `ontem` "Ontem", `7dias` "Semanal (últimos 7 dias)", `mes` "Mensal (este mês)", `mes_passado` "Mês passado". Padrão: `mes`.
- Formatos: `?formato=xlsx` e `?formato=impressao` (os de `comum.exportacao.FORMATOS`).
- Todo número sai de `fila/indicadores.py`/`fila/metas.py`; nenhuma conta nova além da lista de lançamentos.
- % da meta só em `mes` e `mes_passado`; nos outros, "—" (vazio no Excel).
- A pausa do vendedor não conta pausa da gestão (as consultas de `ranking_por_loja` já filtram `fixa=""`).
- A tela funciona sem JavaScript.
- Comentário diz POR QUÊ, em português; commit em português, longo, autor `João Victor Vancim <developer1@kronos.net.br>`, sem coautor.
- Rodar testes: `export KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5440/kronos; DJANGO_DEBUG=1 .venv/bin/python -m pytest -q -p no:cacheprovider <arquivo>`.
- Teste com dente: depois de verde, quebrar o código de propósito, ver vermelho, desfazer.

## Review Focus

1. **Recorte vazio** — período sem atendimento nenhum: o relatório sai com as seções e as tabelas vazias (e "—" nos números), e não quebra nem devolve 404. Teste na Task 1 (`test_recorte_vazio_sai_com_as_secoes`) e na Task 2 (`test_excel_do_recorte_vazio_abre`).
2. **Vendedor com duas lojas** — aparece numa linha por loja em "Vendedores", nunca somado. Teste na Task 1 (`test_vendedor_em_duas_lojas_tem_duas_linhas`).
3. **Não venda sem motivo** (a do ponto esquecido) — o lançamento diz "Fechado sem lançamento", e não "None". Teste na Task 1 (`test_nao_venda_sem_motivo_no_lancamento`).
4. **Nome com caractere de HTML** (loja "A&B <Centro>") — sai escapado no PDF e cru no Excel. Teste na Task 3 (`test_nome_com_html_sai_escapado`).
5. **Gerente com a loja do cabeçalho diferente** — o gerente de uma loja que abre com o cabeçalho em outra loja em que não gerencia recebe 404 (a guarda lê a permissão no lugar atual, como o painel), e com o cabeçalho na loja dele vê só ela. Teste na Task 4 (`test_gerente_so_ve_a_loja_dele`).

---

## Arquivos

| arquivo | o que é |
|---|---|
| `fila/indicadores.py` | + `lancamentos_do_recorte(recorte)` |
| `fila/relatorio.py` (novo) | `Coluna`, `Secao`, `Relatorio`, `PERIODOS`, `PADRAO`, `formatar`, `montar` |
| `fila/relatorio_saida.py` (novo) | `em_xlsx(relatorio)`, `em_impressao(relatorio)` |
| `fila/templates/fila/relatorio.html` (novo) | a página de papel |
| `fila/static/fila/relatorio.css` (novo) | a folha do papel |
| `fila/views_indicadores.py` | extrai `escolha_do_pedido` de `blocos_dos_indicadores` |
| `fila/views_relatorios.py` (novo) | a tela `relatorios` |
| `fila/urls.py`, `fila/modulo.py` | rota e item de menu |
| `locale/es/LC_MESSAGES/django.po/.mo` | castelhano |
| `CLAUDE.md` | a seção dos relatórios e a contagem de arquivos de teste |
| `tests/test_fila_relatorios.py` (novo) | todos os testes desta entrega |
| `tests/test_fila_modulo.py` | o menu com o item novo |

---

### Task 1: O relatório como dado (`fila/relatorio.py` + `lancamentos_do_recorte`)

**Files:**
- Create: `fila/relatorio.py`
- Modify: `fila/indicadores.py` (nova função depois de `pausa_por_tipo`; `__all__`)
- Modify: `docs/superpowers/specs/2026-09-28-relatorios-da-fila-design.md` (aba "Comparação" e aba "Relatório")
- Test: `tests/test_fila_relatorios.py`

**Interfaces:**
- Consumes: `fila.indicadores` (`Recorte`, `numeros`, `variacao`, `por_loja`, `por_empresa`, `ranking_por_loja`, `motivos`, `midias`, `por_grupo`, `pausa_por_tipo`, `_atendimentos`), `fila.periodo` (`periodo_do_pedido`, `periodo_anterior`), `fila.metas.mes_do_periodo`, `fila.estado.nome_de`, `fila.valores.em_reais`.
- Produces:
  - `fila.indicadores.lancamentos_do_recorte(recorte) -> QuerySet[Atendimento]`
  - `fila.relatorio.PERIODOS: tuple[tuple[str, str], ...]`, `PADRAO = "mes"`
  - `fila.relatorio.periodo_escolhido(chave: str | None, agora=None) -> Periodo`
  - `@dataclass(frozen=True) Coluna(rotulo: str, valor: Callable[[Any], object], tipo: str = "texto")` — `tipo` ∈ `texto`, `inteiro`, `dinheiro`, `porcento`, `minutos`
  - `@dataclass(frozen=True) Secao(titulo: str, colunas: tuple[Coluna, ...], linhas: list)`
  - `@dataclass(frozen=True) Relatorio(titulo, empresa: str, lojas: str, periodo: str, gerado_por: str, gerado_em: datetime, secoes: tuple[Secao, ...], nome_do_arquivo: str)`
  - `fila.relatorio.formatar(valor, tipo: str) -> str`
  - `fila.relatorio.montar(recorte, *, rotulo_da_empresa: str, gerado_por: str, agora=None) -> Relatorio`

- [ ] **Step 1: Ajustar a especificação**

Em `docs/superpowers/specs/2026-09-28-relatorios-da-fila-design.md`, na seção "Os formatos", troque a frase do Excel por:

```markdown
- **Excel** (`openpyxl`, já dependência): um arquivo com a aba **Relatório**
  (empresa, lojas, período, quem gerou e quando) e uma aba por seção —
  Resumo, Comparação, Vendedores, Motivos, Mídias, Grupos, Pausas,
  Lançamentos. A comparação com o período anterior é aba própria porque
  mistura unidades (contagem, R$ e pontos de conversão) numa coluna só.
  Valores numéricos saem como número (e não texto), com formato de moeda nas
  colunas de dinheiro e de porcentagem na conversão, para quem abre poder
  somar e filtrar. Nome do arquivo: `relatorio-<empresa>-<período>-<data>.xlsx`.
```

E no item 1 de "O conteúdo", troque "com a variação contra o período anterior" por "e, numa seção à parte (Comparação), cada indicador neste período, no anterior e a variação".

- [ ] **Step 2: Escrever os testes que falham**

Crie `tests/test_fila_relatorios.py`:

```python
"""Os relatórios da fila (spec 2026-09-28-relatorios-da-fila-design).

O cliente: "um relatório que pode ser tirado pelo dono da conta, supervisor
ou gerente, e cada um é focado em uma coisa — o dono de tudo, o supervisor do
que ele é cadastrado, e o gerente no que ele é cadastrado —, diário, semanal,
mensal e mês passado". Todo número sai das contas do painel: se o papel e a
tela discordassem, ninguém saberia em qual acreditar.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import cadastros, logado, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


def local(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def rede():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    centro = nova_loja(empresa, "Centro")
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, centro=centro, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        caio=pessoa_na_loja("caio", empresa, centro),
        gil=pessoa_na_loja("gil", empresa, centro, cargo="gerente"),
        sara=pessoa_na_loja("sara", empresa, None, cargo="supervisor"),
        cad=cadastros(empresa))


def atendimento(rede, pessoa, loja, fim, *, valor=None, motivo="padrao", midia=None,
                itens=()):
    """Um atendimento FECHADO em `fim`. `valor` None é não venda; `motivo=None`
    é a não venda sem motivo (a do ponto esquecido)."""
    from fila.models import Atendimento, ItemVendido, Presenca

    presenca = Presenca.irrestritos.create(empresa=rede.empresa, filial=loja,
                                          pessoa=pessoa, entrada=fim, saida=fim)
    a = Atendimento.irrestritos.create(
        empresa=rede.empresa, filial=loja, vendedor=pessoa, presenca=presenca,
        inicio=fim - timedelta(minutes=5), fim=fim,
        resultado="vendeu" if valor else "nao_vendeu",
        motivo=None if valor else (rede.cad.motivo if motivo == "padrao" else motivo),
        midia=midia, total=Decimal(valor or 0))
    for grupo, v in itens:
        ItemVendido.irrestritos.create(empresa=rede.empresa, atendimento=a,
                                       grupo=grupo, valor=Decimal(v))
    return a


def _recorte(rede, chave="mes", lojas=None, agora=None):
    from fila.indicadores import Recorte
    from fila.relatorio import periodo_escolhido

    return Recorte(rede.empresa, tuple(lojas or (rede.matriz, rede.centro)),
                   periodo_escolhido(chave, agora))


def _secao(relatorio, titulo):
    return next(s for s in relatorio.secoes if s.titulo == titulo)


class TestOPeriodo:
    def test_as_cinco_escolhas_e_o_padrao(self):
        from fila.relatorio import PADRAO, PERIODOS, periodo_escolhido

        assert [c for c, _r in PERIODOS] == ["hoje", "ontem", "7dias", "mes", "mes_passado"]
        assert PADRAO == "mes"
        assert periodo_escolhido("15dias").chave == "mes"
        assert periodo_escolhido(None).chave == "mes"


class TestOConteudo:
    def test_as_secoes_na_ordem(self, rede):
        from fila.relatorio import montar

        r = montar(_recorte(rede), rotulo_da_empresa=str(rede.empresa), gerado_por="Sylvia")
        assert [s.titulo for s in r.secoes] == [
            "Resumo", "Comparação", "Vendedores", "Motivos", "Mídias", "Grupos",
            "Pausas", "Lançamentos"]
        assert r.gerado_por == "Sylvia"
        assert "Matriz" in r.lojas and "Centro" in r.lojas

    def test_o_resumo_bate_com_o_painel(self, rede):
        from fila.indicadores import numeros
        from fila.relatorio import montar

        agora = timezone.now()
        atendimento(rede, rede.ana, rede.matriz, agora, valor="300")
        atendimento(rede, rede.caio, rede.centro, agora)
        recorte = _recorte(rede)
        r = montar(recorte, rotulo_da_empresa=str(rede.empresa), gerado_por="Sylvia")
        total = _secao(r, "Resumo").linhas[0]
        n = numeros(recorte)
        assert total.rotulo == "Total"
        assert (total.numeros.atendimentos, total.numeros.vendas, total.numeros.vendido) == (
            n.atendimentos, n.vendas, n.vendido)
        assert [l.rotulo for l in _secao(r, "Resumo").linhas[1:]] == ["Matriz", "Centro"]

    def test_vendedor_em_duas_lojas_tem_duas_linhas(self, rede):
        from fila.relatorio import montar
        from tests.conftest import alocar

        alocar(rede.ana, rede.empresa, "vendedor", filial=rede.centro)
        agora = timezone.now()
        atendimento(rede, rede.ana, rede.matriz, agora, valor="100")
        atendimento(rede, rede.ana, rede.centro, agora, valor="200")
        r = montar(_recorte(rede), rotulo_da_empresa="x", gerado_por="x")
        linhas = [(l["loja_nome"], l["nome"]) for l in _secao(r, "Vendedores").linhas]
        assert sorted(linhas) == [("Centro", "Ana"), ("Matriz", "Ana")]

    def test_o_pct_da_meta_so_nos_periodos_de_mes(self, rede):
        from fila.relatorio import montar

        agora = timezone.now()
        atendimento(rede, rede.ana, rede.matriz, agora, valor="100")
        for chave, tem in (("mes", True), ("7dias", False), ("hoje", False)):
            r = montar(_recorte(rede, chave), rotulo_da_empresa="x", gerado_por="x")
            rotulos = [c.rotulo for c in _secao(r, "Vendedores").colunas]
            assert ("% da meta" in rotulos) is tem, chave

    def test_a_pausa_da_gestao_fica_fora_da_pausa_do_vendedor(self, rede):
        from fila.models import Pausa, Presenca
        from fila.relatorio import montar

        agora = timezone.now().replace(microsecond=0)
        atendimento(rede, rede.ana, rede.matriz, agora, valor="100")
        presenca = Presenca.irrestritos.filter(pessoa=rede.ana).first()
        inicio = agora - timedelta(hours=2)
        Pausa.irrestritos.create(empresa=rede.empresa, pessoa=rede.ana, filial=rede.matriz,
                                 presenca=presenca, tipo=rede.cad.tipo, inicio=inicio,
                                 fim=inicio + timedelta(minutes=10))
        Pausa.irrestritos.create(empresa=rede.empresa, pessoa=rede.ana, filial=rede.matriz,
                                 presenca=presenca, fixa="gestao",
                                 inicio=inicio + timedelta(minutes=20),
                                 fim=inicio + timedelta(minutes=50))
        # "7dias", e não "hoje": as pausas começam duas horas atrás, e a suíte
        # rodando entre 00:00 e 02:00 as poria no dia anterior.
        r = montar(_recorte(rede, "7dias"), rotulo_da_empresa="x", gerado_por="x")
        ana = next(l for l in _secao(r, "Vendedores").linhas if l["nome"] == "Ana")
        assert ana["pausa"] == timedelta(minutes=10)
        pausas = dict(_secao(r, "Pausas").linhas)
        assert pausas == {"Gestão": 30, "Almoço": 10}

    def test_nao_venda_sem_motivo_no_lancamento(self, rede):
        from fila.relatorio import formatar, montar

        atendimento(rede, rede.ana, rede.matriz, timezone.now(), motivo=None)
        r = montar(_recorte(rede), rotulo_da_empresa="x", gerado_por="x")
        secao = _secao(r, "Lançamentos")
        coluna = next(c for c in secao.colunas if c.rotulo == "Motivo")
        assert formatar(coluna.valor(secao.linhas[0]), coluna.tipo) == "Fechado sem lançamento"

    def test_lancamentos_so_os_fechados_no_periodo(self, rede):
        from fila.indicadores import lancamentos_do_recorte
        from fila.models import Atendimento, Presenca

        agora = timezone.now()
        dentro = atendimento(rede, rede.ana, rede.matriz, agora, valor="100",
                             itens=[(rede.cad.grupo, "100")])
        atendimento(rede, rede.ana, rede.matriz, agora - timedelta(days=70), valor="50")
        presenca = Presenca.irrestritos.filter(pessoa=rede.caio).first() or \
            Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                        pessoa=rede.caio, entrada=agora)
        Atendimento.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                       vendedor=rede.caio, presenca=presenca, inicio=agora)
        assert [a.pk for a in lancamentos_do_recorte(_recorte(rede))] == [dentro.pk]

    def test_a_lista_de_lancamentos_nao_cresce_em_consultas(self, rede):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from fila.relatorio import montar

        agora = timezone.now()

        def medir():
            with CaptureQueriesContext(connection) as c:
                r = montar(_recorte(rede), rotulo_da_empresa="x", gerado_por="x")
                secao = _secao(r, "Lançamentos")
                for linha in secao.linhas:
                    for coluna in secao.colunas:
                        coluna.valor(linha)
            return len(c)

        atendimento(rede, rede.ana, rede.matriz, agora, valor="100",
                    itens=[(rede.cad.grupo, "100")])
        poucas = medir()
        for _i in range(6):
            atendimento(rede, rede.caio, rede.centro, agora, valor="50",
                        itens=[(rede.cad.grupo2, "50")])
        assert medir() <= poucas

    def test_recorte_vazio_sai_com_as_secoes(self, rede):
        from fila.relatorio import montar

        r = montar(_recorte(rede, "hoje"), rotulo_da_empresa="x", gerado_por="x")
        assert len(r.secoes) == 8
        assert _secao(r, "Lançamentos").linhas == []
        assert _secao(r, "Resumo").linhas[0].numeros.atendimentos == 0

    def test_formatar(self):
        from fila.relatorio import formatar

        assert formatar(Decimal("1200"), "dinheiro") == "R$ 1.200,00"
        assert formatar(12.345, "porcento") == "12,3%"
        assert formatar(None, "porcento") == "—"
        assert formatar(timedelta(minutes=90), "minutos") == "90 min"
        assert formatar(3, "inteiro") == "3"
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `DJANGO_DEBUG=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_fila_relatorios.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'fila.relatorio'`.

- [ ] **Step 4: `lancamentos_do_recorte` em `fila/indicadores.py`**

Depois de `pausa_por_tipo`, e acrescente `"lancamentos_do_recorte"` ao `__all__`:

```python
def lancamentos_do_recorte(recorte: Recorte):
    """Os atendimentos FECHADOS no período, um por linha, do mais antigo para
    o mais novo — a seção "Lançamentos" do relatório (28/09/2026). Pela mesma
    porta das outras contas (`_atendimentos`: entra pela hora do fim, aberto
    não entra), para a lista e os totais saírem do mesmo recorte. Uma
    consulta por tabela, e não por linha: num mês da rede inteira são
    centenas de linhas."""
    from django.db.models import Prefetch

    itens = ItemVendido.irrestritos.select_related("grupo").order_by("pk")
    return (_atendimentos(recorte)
            .select_related("filial", "vendedor", "motivo", "midia", "fechado_por")
            .defer("vendedor__avatar", "fechado_por__avatar")
            .prefetch_related(Prefetch("itens", queryset=itens))
            .order_by("fim", "pk"))
```

- [ ] **Step 5: Criar `fila/relatorio.py`**

```python
"""O relatório da fila como DADO (28/09/2026, spec
`docs/superpowers/specs/2026-09-28-relatorios-da-fila-design.md`).

Seções com colunas tipadas e linhas, e nada de HTML nem de planilha: o Excel e
o papel (`fila/relatorio_saida.py`) desenham o MESMO dado, e um número não pode
sair de um jeito na planilha e de outro no PDF.

Toda conta sai de `fila/indicadores.py` e `fila/metas.py`, as do painel do
Início. A única consulta nova é a lista de lançamentos
(`indicadores.lancamentos_do_recorte`), que o painel não tem.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, NamedTuple

from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from . import indicadores as ind
from .estado import nome_de
from .metas import mes_do_periodo
from .periodo import periodo_anterior, periodo_do_pedido
from .valores import em_reais

__all__ = ["Coluna", "PADRAO", "PERIODOS", "Relatorio", "Secao", "formatar",
           "montar", "periodo_escolhido"]

#: Os períodos que o cliente pediu ("diário, semanal, mensal, mês passado"),
#: mais o ontem, que é o diário de quem fecha o dia na manhã seguinte. As
#: CHAVES são as de `fila.periodo.ATALHOS`, para o período do relatório ser o
#: mesmo do painel. "Semanal" são os últimos 7 dias (decisão do cliente).
PERIODOS: "tuple[tuple[str, str], ...]" = (
    ("hoje", gettext_lazy("Diário (hoje)")),
    ("ontem", gettext_lazy("Ontem")),
    ("7dias", gettext_lazy("Semanal (últimos 7 dias)")),
    ("mes", gettext_lazy("Mensal (este mês)")),
    ("mes_passado", gettext_lazy("Mês passado")),
)
PADRAO = "mes"


def periodo_escolhido(chave, agora=None):
    """O período do pedido, só entre os do relatório; o resto cai no padrão."""
    if chave not in dict(PERIODOS):
        chave = PADRAO
    return periodo_do_pedido({"periodo": chave}, agora)


@dataclass(frozen=True)
class Coluna:
    rotulo: str
    valor: Callable[[Any], object]
    #: `texto`, `inteiro`, `dinheiro`, `porcento` ou `minutos`. É o que faz o
    #: Excel gravar NÚMERO (somável) e o papel escrever "R$ 1.200,00".
    tipo: str = "texto"


@dataclass(frozen=True)
class Secao:
    titulo: str
    colunas: "tuple[Coluna, ...]"
    linhas: list


@dataclass(frozen=True)
class Relatorio:
    titulo: str
    empresa: str
    lojas: str
    periodo: str
    gerado_por: str
    gerado_em: datetime
    secoes: "tuple[Secao, ...]"
    nome_do_arquivo: str


class LinhaDoResumo(NamedTuple):
    rotulo: str
    numeros: "ind.Numeros"


def formatar(valor, tipo: str) -> str:
    """O valor como o papel o escreve. Vazio é "—", como no painel."""
    if valor is None or valor == "":
        return "—"
    if tipo == "dinheiro":
        return em_reais(Decimal(valor))
    if tipo == "porcento":
        return f"{float(valor):.1f}%".replace(".", ",")
    if tipo == "minutos":
        minutos = int(valor.total_seconds() // 60) if isinstance(valor, timedelta) else int(valor)
        return f"{minutos} min"
    return str(valor)


def _minutos(valor) -> int:
    return int(valor.total_seconds() // 60) if isinstance(valor, timedelta) else int(valor or 0)


def _numeros(rotulo_do_onde: str) -> "tuple[Coluna, ...]":
    return (
        Coluna(rotulo_do_onde, lambda l: l.rotulo),
        Coluna(_("Atendimentos"), lambda l: l.numeros.atendimentos, "inteiro"),
        Coluna(_("Vendas"), lambda l: l.numeros.vendas, "inteiro"),
        Coluna(_("Conversão"), lambda l: l.numeros.conversao, "porcento"),
        Coluna(_("Vendido"), lambda l: l.numeros.vendido, "dinheiro"),
        Coluna(_("Ticket médio"), lambda l: l.numeros.ticket, "dinheiro"),
    )


def _resumo(recorte) -> Secao:
    linhas = [LinhaDoResumo(_("Total"), ind.numeros(recorte))]
    linhas += [LinhaDoResumo(str(d.loja), d.numeros) for d in ind.por_loja(recorte)]
    if len(recorte.empresas) > 1:
        linhas += [LinhaDoResumo(str(d.empresa), d.numeros) for d in ind.por_empresa(recorte)]
    return Secao(_("Resumo"), _numeros(_("Onde")), linhas)


def _comparacao(recorte, anterior) -> Secao:
    """Cada indicador neste período, no anterior e a variação. Aba própria
    porque mistura unidades numa coluna só; por isso os valores já vão
    escritos (texto), e não como número."""
    n, a = ind.numeros(recorte), ind.numeros(anterior)

    def var(atual, antes, *, pontos=False):
        v = ind.variacao(atual, antes, pontos=pontos)
        return "—" if v is None else f"{v.valor:+.1f} {v.unidade}".replace(".", ",")

    linhas = [
        (_("Atendimentos"), str(n.atendimentos), str(a.atendimentos),
         var(n.atendimentos, a.atendimentos)),
        (_("Vendas"), str(n.vendas), str(a.vendas), var(n.vendas, a.vendas)),
        (_("Conversão"), formatar(n.conversao, "porcento"), formatar(a.conversao, "porcento"),
         var(n.conversao, a.conversao, pontos=True)),
        (_("Vendido"), formatar(n.vendido, "dinheiro"), formatar(a.vendido, "dinheiro"),
         var(n.vendido, a.vendido)),
        (_("Ticket médio"), formatar(n.ticket, "dinheiro"), formatar(a.ticket, "dinheiro"),
         var(n.ticket, a.ticket)),
    ]
    return Secao(_("Comparação"), (
        Coluna(_("Indicador"), lambda l: l[0]),
        Coluna(_("Neste período"), lambda l: l[1]),
        Coluna(_("No período anterior"), lambda l: l[2]),
        Coluna(_("Variação"), lambda l: l[3]),
    ), linhas)


def _vendedores(recorte) -> Secao:
    mes = mes_do_periodo(recorte.periodo)
    linhas = list(ind.ranking_por_loja(recorte, mes).order_by("loja_nome", "-vendido", "nome"))
    colunas = [
        Coluna(_("Loja"), lambda l: l["loja_nome"]),
        Coluna(_("Vendedor"), lambda l: l["nome"]),
        Coluna(_("Atendimentos"), lambda l: l["atendimentos"], "inteiro"),
        Coluna(_("Vendas"), lambda l: l["vendas"], "inteiro"),
        Coluna(_("Conversão"), lambda l: l["conversao"], "porcento"),
        Coluna(_("Vendido"), lambda l: l["vendido"], "dinheiro"),
        Coluna(_("Ticket médio"), lambda l: l["ticket"], "dinheiro"),
        Coluna(_("Cliente pediu"), lambda l: l["pediu"], "inteiro"),
        Coluna(_("Pausa"), lambda l: l["pausa"], "minutos"),
    ]
    # A meta é MENSAL: dividir o vendido de 7 dias pela meta do mês seria um
    # número errado com cara de certo. Fora dos meses, a coluna não existe.
    if mes is not None:
        colunas.append(Coluna(_("% da meta"), lambda l: l.get("pct_meta"), "porcento"))
    return Secao(_("Vendedores"), tuple(colunas), linhas)


def _grupos_do(atendimento) -> str:
    return "; ".join(f"{i.grupo.nome} {em_reais(i.valor)}" for i in atendimento.itens.all())


def _lancamentos(recorte) -> Secao:
    def quando(a):
        return timezone.localtime(a.fim).strftime("%d/%m/%Y %H:%M")

    def motivo(a):
        if a.resultado != "nao_vendeu":
            return ""
        return a.motivo.nome if a.motivo_id else str(ind.SEM_LANCAMENTO)

    def fechado_por(a):
        return nome_de(a.fechado_por) if a.fechado_por_id and a.fechado_por_id != a.vendedor_id else ""

    return Secao(_("Lançamentos"), (
        Coluna(_("Data e hora"), quando),
        Coluna(_("Loja"), lambda a: str(a.filial)),
        Coluna(_("Vendedor"), lambda a: nome_de(a.vendedor)),
        Coluna(_("Resultado"), lambda a: _("Vendeu") if a.resultado == "vendeu" else _("Não vendeu")),
        Coluna(_("Valor"), lambda a: a.total if a.resultado == "vendeu" else None, "dinheiro"),
        Coluna(_("Grupos"), _grupos_do),
        Coluna(_("Motivo"), motivo),
        Coluna(_("Observação"), lambda a: a.observacao),
        Coluna(_("Mídia"), lambda a: a.midia.nome if a.midia_id else ""),
        Coluna(_("Cliente pediu"), lambda a: _("Sim") if a.cliente_pediu else ""),
        Coluna(_("Fechado por"), fechado_por),
    ), list(ind.lancamentos_do_recorte(recorte)))


def _periodo_por_extenso(periodo) -> str:
    rotulo = dict(PERIODOS).get(periodo.chave, periodo.rotulo)
    de = timezone.localtime(periodo.de).strftime("%d/%m/%Y")
    ate = timezone.localtime(periodo.ate - timedelta(microseconds=1)).strftime("%d/%m/%Y")
    return f"{rotulo} · {de}" if de == ate else f"{rotulo} · {de} {_('a')} {ate}"


def montar(recorte, *, rotulo_da_empresa: str, gerado_por: str, agora=None) -> Relatorio:
    agora = agora or timezone.now()
    anterior = ind.Recorte(recorte.empresa, recorte.lojas,
                           periodo_anterior(recorte.periodo, agora), recorte.empresas)
    secoes = (
        _resumo(recorte),
        _comparacao(recorte, anterior),
        _vendedores(recorte),
        Secao(_("Motivos"), (Coluna(_("Motivo"), lambda l: l[0]),
                             Coluna(_("Atendimentos"), lambda l: l[1], "inteiro")),
              ind.motivos(recorte)),
        Secao(_("Mídias"), (
            Coluna(_("Mídia"), lambda l: l[0]),
            Coluna(_("Atendimentos"), lambda l: l[1], "inteiro"),
            Coluna(_("Vendas"), lambda l: l[2], "inteiro"),
            Coluna(_("Conversão"), lambda l: 100 * l[2] / l[1] if l[1] else None, "porcento"),
        ), ind.midias(recorte)),
        Secao(_("Grupos"), (Coluna(_("Grupo de item"), lambda l: l[0]),
                            Coluna(_("Vendido"), lambda l: l[1], "dinheiro")),
              ind.por_grupo(recorte)),
        Secao(_("Pausas"), (Coluna(_("Tipo de pausa"), lambda l: l[0]),
                            Coluna(_("Minutos"), lambda l: l[1], "inteiro")),
              ind.pausa_por_tipo(recorte)),
        _lancamentos(recorte),
    )
    lojas = ", ".join(str(l) for l in recorte.lojas)
    return Relatorio(
        titulo=_("Relatório da fila"), empresa=rotulo_da_empresa, lojas=lojas,
        periodo=_periodo_por_extenso(recorte.periodo), gerado_por=gerado_por,
        gerado_em=agora, secoes=secoes,
        nome_do_arquivo=slugify(f"relatorio-{rotulo_da_empresa}-{recorte.periodo.chave}-"
                                f"{timezone.localtime(agora):%Y-%m-%d}"))
```

Observação: o teste `test_a_pausa_da_gestao_fica_fora_da_pausa_do_vendedor` compara `dict(_secao(r, "Pausas").linhas)` — as linhas de `pausa_por_tipo` já são `(tipo, minutos)`.

- [ ] **Step 6: Rodar e ver passar**

Run: `DJANGO_DEBUG=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_fila_relatorios.py`
Expected: PASS em todos.

- [ ] **Step 7: Teste com dente**

Troque, em `_vendedores`, `if mes is not None:` por `if True:`; rode; `test_o_pct_da_meta_so_nos_periodos_de_mes` deve falhar. Desfaça. Troque em `lancamentos_do_recorte` o `prefetch_related(...)` por nada; rode; `test_a_lista_de_lancamentos_nao_cresce_em_consultas` deve falhar. Desfaça.

- [ ] **Step 8: Commit**

```bash
git add fila/relatorio.py fila/indicadores.py tests/test_fila_relatorios.py docs/superpowers/specs/2026-09-28-relatorios-da-fila-design.md
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -F - <<'EOF'
feat: o relatório da fila como dado

Primeira peça dos relatórios (spec 2026-09-28): `fila/relatorio.py` monta
o relatório em seções de colunas tipadas — Resumo, Comparação,
Vendedores, Motivos, Mídias, Grupos, Pausas e Lançamentos —, sem HTML nem
planilha, para o Excel e o papel desenharem o MESMO dado. Toda conta sai
de `fila/indicadores.py` e `fila/metas.py`, as do painel; a única nova é
a lista de lançamentos (`lancamentos_do_recorte`), uma consulta por
tabela. O % da meta só existe nos períodos de mês, e a pausa da gestão
fica fora da pausa do vendedor. A especificação ganha a aba Comparação,
que mistura unidades e por isso é aba própria.
EOF
```

---

### Task 2: O Excel (`fila/relatorio_saida.em_xlsx`)

**Files:**
- Create: `fila/relatorio_saida.py`
- Test: `tests/test_fila_relatorios.py` (acrescentar a classe `TestOExcel`)

**Interfaces:**
- Consumes: `fila.relatorio` (`Relatorio`, `Secao`, `Coluna`, `montar`), `comum.exportacao.CONTENT_TYPE_XLSX`.
- Produces: `fila.relatorio_saida.em_xlsx(relatorio: Relatorio) -> HttpResponse`.

- [ ] **Step 1: Testes que falham** — acrescente a `tests/test_fila_relatorios.py`:

```python
class TestOExcel:
    def _abrir(self, resposta):
        from io import BytesIO

        from openpyxl import load_workbook

        return load_workbook(BytesIO(resposta.content))

    def test_as_abas_e_o_cabecalho(self, rede):
        from fila.relatorio import montar
        from fila.relatorio_saida import em_xlsx

        agora = timezone.now()
        atendimento(rede, rede.ana, rede.matriz, agora, valor="1200",
                    itens=[(rede.cad.grupo, "1200")])
        r = montar(_recorte(rede), rotulo_da_empresa="Sylvia Design", gerado_por="Sylvia")
        resposta = em_xlsx(r)
        assert resposta["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert f'filename="{r.nome_do_arquivo}.xlsx"' in resposta["Content-Disposition"]
        livro = self._abrir(resposta)
        assert livro.sheetnames == ["Relatório", "Resumo", "Comparação", "Vendedores",
                                    "Motivos", "Mídias", "Grupos", "Pausas", "Lançamentos"]
        capa = {linha[0]: linha[1] for linha in livro["Relatório"].iter_rows(values_only=True)}
        assert capa["Empresa"] == "Sylvia Design" and capa["Gerado por"] == "Sylvia"

    def test_dinheiro_e_numero_e_nao_texto(self, rede):
        from fila.relatorio import montar
        from fila.relatorio_saida import em_xlsx

        atendimento(rede, rede.ana, rede.matriz, timezone.now(), valor="1200")
        livro = self._abrir(em_xlsx(montar(_recorte(rede), rotulo_da_empresa="x",
                                           gerado_por="x")))
        resumo = livro["Resumo"]
        cabecalho = [c.value for c in resumo[1]]
        vendido = resumo.cell(row=2, column=cabecalho.index("Vendido") + 1)
        conversao = resumo.cell(row=2, column=cabecalho.index("Conversão") + 1)
        assert vendido.value == 1200 and "R$" in vendido.number_format
        assert conversao.value == 1.0 and "%" in conversao.number_format

    def test_excel_do_recorte_vazio_abre(self, rede):
        from fila.relatorio import montar
        from fila.relatorio_saida import em_xlsx

        livro = self._abrir(em_xlsx(montar(_recorte(rede, "hoje"),
                                           rotulo_da_empresa="x", gerado_por="x")))
        assert livro["Lançamentos"].max_row == 1   # só o cabeçalho
```

- [ ] **Step 2: Rodar e ver falhar** — `ModuleNotFoundError: No module named 'fila.relatorio_saida'`.

- [ ] **Step 3: Criar `fila/relatorio_saida.py` com o Excel**

```python
"""O relatório no papel e na planilha (28/09/2026).

Os dois leem o MESMO `fila.relatorio.Relatorio`. O Excel grava NÚMERO nas
colunas de número (somável, filtrável), com o formato de moeda e de
porcentagem na célula; o papel escreve o texto com `relatorio.formatar`.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _

from comum.exportacao import CONTENT_TYPE_XLSX

from .relatorio import Relatorio, formatar

__all__ = ["em_impressao", "em_xlsx"]

_FORMATO = {"dinheiro": 'R$ #,##0.00', "porcento": "0.0%", "inteiro": "0",
            "minutos": "0"}


def _celula(valor, tipo):
    """O valor que a célula GRAVA. Porcentagem vai como fração (12,5% é
    0,125), que é o que o formato `0.0%` do Excel espera."""
    if valor is None or valor == "":
        return None
    if tipo == "dinheiro":
        return float(Decimal(valor))
    if tipo == "porcento":
        return float(valor) / 100
    if tipo == "minutos":
        return int(valor.total_seconds() // 60) if isinstance(valor, timedelta) else int(valor)
    if tipo == "inteiro":
        return int(valor)
    return str(valor)


def em_xlsx(relatorio: Relatorio) -> HttpResponse:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    livro = Workbook()
    capa = livro.active
    capa.title = _("Relatório")
    for rotulo, valor in (
            (_("Relatório"), relatorio.titulo), (_("Empresa"), relatorio.empresa),
            (_("Lojas"), relatorio.lojas), (_("Período"), relatorio.periodo),
            (_("Gerado por"), relatorio.gerado_por),
            (_("Gerado em"), timezone.localtime(relatorio.gerado_em).strftime("%d/%m/%Y %H:%M"))):
        capa.append([rotulo, valor])
    for secao in relatorio.secoes:
        # O formato limita o nome da aba a 31 caracteres.
        folha = livro.create_sheet(secao.titulo[:31])
        folha.append([c.rotulo for c in secao.colunas])
        for celula in folha[1]:
            celula.font = Font(bold=True)
        for linha in secao.linhas:
            folha.append([_celula(c.valor(linha), c.tipo) for c in secao.colunas])
        for indice, coluna in enumerate(secao.colunas, start=1):
            formato = _FORMATO.get(coluna.tipo)
            if formato:
                for (celula,) in folha.iter_rows(min_row=2, min_col=indice, max_col=indice):
                    celula.number_format = formato
    resposta = HttpResponse(content_type=CONTENT_TYPE_XLSX)
    resposta["Content-Disposition"] = f'attachment; filename="{relatorio.nome_do_arquivo}.xlsx"'
    livro.save(resposta)
    return resposta
```

- [ ] **Step 4: Rodar e ver passar** (as três de `TestOExcel`).

- [ ] **Step 5: Teste com dente** — troque em `_celula` o ramo `dinheiro` para `return str(valor)`; `test_dinheiro_e_numero_e_nao_texto` deve falhar. Desfaça.

- [ ] **Step 6: Commit**

```bash
git add fila/relatorio_saida.py tests/test_fila_relatorios.py
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -F - <<'EOF'
feat: o relatório da fila em Excel

`fila/relatorio_saida.em_xlsx` grava o relatório numa planilha com a aba
Relatório (empresa, lojas, período, quem gerou e quando) e uma aba por
seção. As colunas de dinheiro, porcentagem, contagem e minutos saem como
NÚMERO, com o formato na célula, para quem abre poder somar e filtrar; a
exportação das listas grava texto, e isso serve para listagem, não para
relatório de números.
EOF
```

---

### Task 3: O PDF (a página de papel)

**Files:**
- Modify: `fila/relatorio_saida.py` (acrescentar `em_impressao`)
- Create: `fila/templates/fila/relatorio.html`, `fila/static/fila/relatorio.css`
- Test: `tests/test_fila_relatorios.py` (classe `TestOPapel`)

**Interfaces:**
- Consumes: `fila.ambiente.ambiente_da_fila`, `fila.relatorio.formatar`, `comum.estaticos.versionado`.
- Produces: `fila.relatorio_saida.em_impressao(relatorio: Relatorio) -> HttpResponse`.

- [ ] **Step 1: Testes que falham**

```python
class TestOPapel:
    def test_as_secoes_e_o_cabecalho(self, rede):
        from fila.relatorio import montar
        from fila.relatorio_saida import em_impressao

        atendimento(rede, rede.ana, rede.matriz, timezone.now(), valor="1200")
        r = montar(_recorte(rede), rotulo_da_empresa="Sylvia Design", gerado_por="Sylvia")
        html = em_impressao(r).content.decode()
        for titulo in ("Resumo", "Comparação", "Vendedores", "Motivos", "Mídias",
                       "Grupos", "Pausas", "Lançamentos"):
            assert f"<h2>{titulo}</h2>" in html
        assert "Sylvia Design" in html and r.periodo in html and "Gerado por Sylvia" in html
        assert "R$ 1.200,00" in html
        assert "window.print()" in html
        # Os lançamentos por último: é a seção longa.
        assert html.index("<h2>Lançamentos</h2>") > html.index("<h2>Pausas</h2>")

    def test_nome_com_html_sai_escapado(self, rede):
        from fila.relatorio import montar
        from fila.relatorio_saida import em_impressao

        rede.centro.apelido = "A&B <Centro>"
        rede.centro.save()
        atendimento(rede, rede.caio, rede.centro, timezone.now(), valor="10")
        html = em_impressao(montar(_recorte(rede), rotulo_da_empresa="x",
                                   gerado_por="x")).content.decode()
        assert "A&amp;B &lt;Centro&gt;" in html
        assert "<Centro>" not in html
```

- [ ] **Step 2: Rodar e ver falhar** — `ImportError: cannot import name 'em_impressao'`.

- [ ] **Step 3: O template `fila/templates/fila/relatorio.html`**

```jinja
{# O relatório no papel (28/09/2026). Fora do shell, como a impressão das
   listas (`comum.exportacao`): o navegador salva em PDF pelo próprio diálogo,
   sem motor de PDF na imagem. Nomes de loja e de pessoa são DADO e saem
   escapados pelo autoescape do ambiente da fila. #}
<!DOCTYPE html>
<html lang="{{ idioma }}">
<head>
<meta charset="utf-8">
<title>{{ r.titulo }} — {{ r.empresa }}</title>
<link rel="stylesheet" href="/tema.css">
<link rel="stylesheet" href="{{ folha_do_sistema }}">
<link rel="stylesheet" href="{{ folha_da_impressao }}">
<link rel="stylesheet" href="{{ folha_do_relatorio }}">
</head>
<body class="papel relatorio">
<header class="papel-cabecalho">
  <h1>{{ r.titulo }}</h1>
  <p class="relatorio-onde"><strong>{{ r.empresa }}</strong> · {{ r.lojas }}</p>
  <p class="relatorio-periodo">{{ r.periodo }}</p>
  <p class="papel-carimbo">{{ traduzir("Gerado por") }} {{ r.gerado_por }} · {{ gerado_em }}</p>
</header>
{% for s in r.secoes %}
<section class="relatorio-secao">
  <h2>{{ s.titulo }}</h2>
  {% if s.linhas %}
  <table>
    <thead><tr>{% for c in s.colunas %}<th{% if c.tipo != "texto" %} class="num"{% endif %}>{{ c.rotulo }}</th>{% endfor %}</tr></thead>
    <tbody>
    {% for linha in s.linhas %}
      <tr>{% for c in s.colunas %}<td{% if c.tipo != "texto" %} class="num"{% endif %}>{{ formatar(c.valor(linha), c.tipo) }}</td>{% endfor %}</tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="relatorio-vazio">{{ traduzir("Nada no período.") }}</p>
  {% endif %}
</section>
{% endfor %}
<script>window.print();</script>
</body>
</html>
```

- [ ] **Step 4: A folha `fila/static/fila/relatorio.css`**

```css
/* O relatório no papel (28/09/2026). Só tokens do tema, como toda folha da
   fila. O cabeçalho da tabela se repete em cada página impressa
   (`table-header-group`): numa lista de lançamentos de várias páginas, sem
   ele a segunda página é uma coluna de números sem nome. */
.relatorio { max-width: 1100px; margin: 0 auto; padding: 24px; }
.relatorio-onde, .relatorio-periodo { margin: 4px 0; color: var(--on-surface-2); }
.relatorio-secao { margin-top: 28px; }
.relatorio-secao h2 { font-size: 16px; margin: 0 0 8px; }
.relatorio table { width: 100%; border-collapse: collapse; font-size: 12px; }
.relatorio th, .relatorio td { padding: 6px 8px; border-bottom: 1px solid var(--outline-2); text-align: left; }
.relatorio .num { text-align: right; font-variant-numeric: tabular-nums; }
.relatorio thead { display: table-header-group; }
.relatorio tr { break-inside: avoid; }
.relatorio-vazio { color: var(--on-surface-2); margin: 0; }
@media print { .relatorio { padding: 0; } }
```

- [ ] **Step 5: `em_impressao` em `fila/relatorio_saida.py`**

```python
def em_impressao(relatorio: Relatorio) -> HttpResponse:
    from django.utils.translation import get_language

    from comum.estaticos import versionado

    from .ambiente import ambiente_da_fila

    html = ambiente_da_fila().get_template("fila/relatorio.html").render(
        r=relatorio, formatar=formatar, idioma=get_language() or "pt-BR",
        gerado_em=timezone.localtime(relatorio.gerado_em).strftime("%d/%m/%Y %H:%M"),
        folha_do_sistema=versionado("/static/nucleo/mw5.css"),
        folha_da_impressao=versionado("/static/plataforma/impressao.css"),
        folha_do_relatorio=versionado("/static/fila/relatorio.css"))
    return HttpResponse(html)
```

Confira que `ambiente_da_fila()` tem `autoescape` ligado e o filtro/global `traduzir` (é o ambiente das páginas da fila; se `traduzir` não for global lá, passe `traduzir=_` no `render`).

- [ ] **Step 6: Rodar e ver passar** (as duas de `TestOPapel`).

- [ ] **Step 7: Teste com dente** — renderize com `{{ formatar(...) | safe }}` no lugar; `test_nome_com_html_sai_escapado` deve falhar (a loja sai crua no Lançamentos). Desfaça.

- [ ] **Step 8: Commit**

```bash
git add fila/relatorio_saida.py fila/templates/fila/relatorio.html fila/static/fila/relatorio.css tests/test_fila_relatorios.py
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -F - <<'EOF'
feat: o relatório da fila no papel

`em_impressao` desenha o relatório numa página fora do shell que chama o
diálogo de impressão, como a exportação das listas: o navegador salva em
PDF, sem motor de PDF na imagem. Cabeçalho com empresa, lojas, período,
quem gerou e quando; as oito seções em ordem, os lançamentos por último;
o cabeçalho de cada tabela se repete nas páginas impressas. Nomes de loja
e de pessoa saem escapados.
EOF
```

---

### Task 4: A tela, a rota e o menu

**Files:**
- Modify: `fila/views_indicadores.py` (extrair `escolha_do_pedido`)
- Create: `fila/views_relatorios.py`
- Modify: `fila/urls.py`, `fila/modulo.py`, `tests/test_fila_modulo.py`
- Test: `tests/test_fila_relatorios.py` (classe `TestATela`)

**Interfaces:**
- Consumes: `fila.relatorio` (`PERIODOS`, `PADRAO`, `periodo_escolhido`, `montar`), `fila.relatorio_saida` (`em_xlsx`, `em_impressao`), `fila.indicadores` (`Recorte`, `lojas_com_relatorio`, `empresas_com_relatorio`).
- Produces:
  - `fila.views_indicadores.escolha_do_pedido(request, empresa, permitidas, periodo) -> Escolha`, com `@dataclass(frozen=True) Escolha(empresa, empresas: tuple, escolhida, permitidas: list, lojas: list, loja, recorte: ind.Recorte)`.
  - `fila.views_relatorios.relatorios(request) -> HttpResponse`, rota `fila_relatorios` em `/fila/relatorios`.

- [ ] **Step 1: Testes que falham**

```python
class TestATela:
    def _get(self, cliente, **params):
        return cliente.get(reverse("fila_relatorios"), params)

    def _na_loja(self, cliente, loja):
        from plataforma.contexto import CHAVE

        sessao = cliente.session
        sessao[CHAVE] = loja.pk
        sessao.save()
        return cliente

    def test_quem_entra(self, rede):
        assert self._get(logado("sylvia")).status_code == 200
        assert self._get(logado("sara")).status_code == 200
        assert self._get(self._na_loja(logado("gil"), rede.centro)).status_code == 200
        assert self._get(logado("ana")).status_code == 404

    def test_gerente_so_ve_a_loja_dele(self, rede):
        gil = self._na_loja(logado("gil"), rede.centro)
        html = self._get(gil).content.decode()
        assert "Centro" in html and f'value="{rede.matriz.pk}"' not in html
        # A loja forjada cai na dele: o PDF sai só com o Centro.
        papel = self._get(gil, formato="impressao", loja=str(rede.matriz.pk)).content.decode()
        assert "Centro" in papel and "Matriz" not in papel.split("<h2>Resumo</h2>")[0]

    def test_o_dono_ve_todas_e_escolhe_uma(self, rede):
        dono = logado("sylvia")
        papel = self._get(dono, formato="impressao").content.decode()
        assert "Matriz, Centro" in papel or "Centro, Matriz" in papel
        so_centro = self._get(dono, formato="impressao", loja=str(rede.centro.pk)).content.decode()
        cabecalho = so_centro.split("<h2>Resumo</h2>")[0]
        assert "Centro" in cabecalho and "Matriz" not in cabecalho

    def test_o_excel_pela_tela(self, rede):
        resposta = self._get(logado("sylvia"), formato="xlsx", periodo="mes_passado")
        assert resposta["Content-Type"].startswith("application/vnd.openxmlformats")
        assert "mes-passado" in resposta["Content-Disposition"]

    def test_a_tela_sem_javascript(self, rede):
        html = self._get(logado("sylvia")).content.decode()
        assert '<form' in html and 'method="get"' in html
        for chave in ("hoje", "ontem", "7dias", "mes", "mes_passado"):
            assert f'value="{chave}"' in html
        assert 'name="formato" value="impressao"' in html
        assert 'name="formato" value="xlsx"' in html
```

E em `tests/test_fila_modulo.py`:
- no conjunto das rotas dos atalhos, acrescente `"/fila/relatorios"`;
- no conjunto das permissões dos atalhos, acrescente `"fila.relatorios"`;
- na lista de filhos de "Gerenciar Fila", acrescente `("Relatórios", "/fila/relatorios")` depois de `("Histórico da fila", "/fila/historico")`.

- [ ] **Step 2: Rodar e ver falhar** — `NoReverseMatch: 'fila_relatorios'` e o menu.

- [ ] **Step 3: Extrair `escolha_do_pedido` em `fila/views_indicadores.py`**

Acrescente perto de `_lojas_do_pedido`:

```python
@dataclass(frozen=True)
class Escolha:
    """O recorte que o pedido escolheu, dentro do alcance da pessoa. Uma porta
    só para o painel e os relatórios (28/09/2026): o papel e a tela precisam
    do MESMO recorte, e duas cópias desta regra divergiriam na primeira
    mudança."""

    empresa: object
    empresas: tuple
    escolhida: object
    permitidas: list
    lojas: list
    loja: object
    recorte: "ind.Recorte"


def escolha_do_pedido(request, empresa, permitidas, periodo) -> Escolha:
    from contas.identidade import usuario_de

    pessoa = usuario_de(request.usuario)
    empresas, escolhida = _empresas_do_pedido(request, pessoa)
    if escolhida is None:
        permitidas = [loja for e in empresas
                      for loja in ind.lojas_com_relatorio(pessoa, e)]
    elif escolhida.pk != empresa.pk:
        empresa = escolhida
        permitidas = ind.lojas_com_relatorio(pessoa, escolhida)
    lojas, loja = _lojas_do_pedido(request, permitidas)
    return Escolha(empresa, tuple(empresas), escolhida, list(permitidas), lojas, loja,
                   ind.Recorte(empresa, tuple(lojas), periodo, tuple(empresas)))
```

E em `blocos_dos_indicadores` troque o trecho de `pessoa = usuario_de(...)` até `recorte = ind.Recorte(...)` por:

```python
    escolha = escolha_do_pedido(request, empresa, permitidas, periodo)
    pessoa = usuario_de(request.usuario)
    empresa, empresas, escolhida = escolha.empresa, escolha.empresas, escolha.escolhida
    permitidas, lojas, loja = escolha.permitidas, escolha.lojas, escolha.loja
    recorte = escolha.recorte
```

(`from dataclasses import dataclass` no topo, se faltar.) Rode `tests/test_fila_tela_indicadores.py` e `tests/test_fila_painel_do_vendedor.py`: tudo verde, porque o comportamento do painel não muda.

- [ ] **Step 4: Criar `fila/views_relatorios.py`**

```python
"""A tela dos relatórios (28/09/2026, spec 2026-09-28-relatorios-da-fila).

Escolhe o período, a loja e a empresa, e devolve a tela ou o arquivo pelo
`?formato=` (os de `comum.exportacao.FORMATOS`). O recorte sai da MESMA porta
do painel (`views_indicadores.escolha_do_pedido`): o dono vê todas as lojas,
o supervisor as da empresa dele e o gerente as dele, e a `?loja=` forjada cai
dentro do alcance.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.components import Alert, Card, PageHeader, Raw
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from . import indicadores as ind
from .estado import nome_de
from .relatorio import PADRAO, PERIODOS, montar, periodo_escolhido
from .relatorio_saida import em_impressao, em_xlsx
from .views_indicadores import TODAS, escolha_do_pedido

__all__ = ["relatorios"]


def _opcoes(pares, escolhido) -> str:
    return format_html_join("", '<option value="{}"{}>{}</option>', (
        (valor, format_html(" selected") if str(valor) == str(escolhido) else "", rotulo)
        for valor, rotulo in pares))


def _formulario(chave, escolha, empresas_alcancadas) -> str:
    """Sem JavaScript: um GET com os campos e dois botões que mandam o
    `formato`. O PDF abre noutra aba, para a tela continuar ali."""
    campos = [format_html(
        '<label class="f"><span class="lbl">{}</span><select class="ctl" name="periodo">{}</select></label>',
        _("Período"), _opcoes(PERIODOS, chave))]
    if len(empresas_alcancadas) > 1:
        campos.append(format_html(
            '<label class="f"><span class="lbl">{}</span><select class="ctl" name="empresa">{}</select></label>',
            _("Empresa"), _opcoes([(TODAS, _("Todas as empresas"))]
                                  + [(e.pk, str(e)) for e in empresas_alcancadas],
                                  escolha.escolhida.pk if escolha.escolhida else TODAS)))
    if len(escolha.permitidas) > 1:
        campos.append(format_html(
            '<label class="f"><span class="lbl">{}</span><select class="ctl" name="loja">{}</select></label>',
            _("Loja"), _opcoes([(TODAS, _("Todas as lojas"))]
                               + [(l.pk, str(l)) for l in escolha.permitidas],
                               escolha.loja.pk if escolha.loja else TODAS)))
    return format_html(
        '<form method="get" action="{}" class="relatorio-form">{}'
        '<div class="relatorio-botoes">'
        '<button class="btn primary" type="submit" name="formato" value="impressao" formtarget="_blank">{}</button>'
        '<button class="btn" type="submit" name="formato" value="xlsx">{}</button>'
        '</div></form>',
        reverse("fila_relatorios"), format_html_join("", "{}", ((c,) for c in campos)),
        _("Gerar PDF"), _("Gerar Excel"))


@exigir_permissao("fila.relatorios")
@exigir_modulo_ligado("fila")
def relatorios(request) -> HttpResponse:
    from plataforma.site import montar_site

    pessoa = usuario_de(request.usuario)
    empresa = empresa_atual(request)
    chave = request.GET.get("periodo") if request.GET.get("periodo") in dict(PERIODOS) else PADRAO
    periodo = periodo_escolhido(chave)
    permitidas = ind.lojas_com_relatorio(pessoa, empresa)
    formato = request.GET.get("formato")
    escolha = escolha_do_pedido(request, empresa, permitidas, periodo) if permitidas else None

    if escolha is not None and escolha.lojas and formato in ("xlsx", "impressao"):
        rotulo = str(escolha.empresa) if escolha.escolhida else _("Todas as empresas")
        relatorio = montar(escolha.recorte, rotulo_da_empresa=rotulo,
                           gerado_por=nome_de(pessoa))
        return em_xlsx(relatorio) if formato == "xlsx" else em_impressao(relatorio)

    with use_environment(ambiente()):
        site = montar_site(request)
        corpo = (Alert(tone="info", message=_("Nenhuma loja em que você tira relatório."))
                 if escolha is None or not escolha.lojas else
                 Card(body=Raw(html=_formulario(chave, escolha,
                                                ind.empresas_com_relatorio(pessoa)))))
        pagina = site.page(
            title=_("Relatórios"), width="full",
            stylesheets=["/static/fila/relatorio.css"],
            content=[aviso_de_personificacao(request),
                     PageHeader(title=_("Relatórios"),
                                subtitle=_("Os números das lojas que você acompanha, "
                                           "em PDF ou Excel.")),
                     corpo],
            crumbs=[Crumb(_("Relatórios"))], user=request.usuario)
        return render(pagina)
```

Acrescente em `fila/static/fila/relatorio.css`:

```css
/* A tela (e não o papel): os campos numa linha que quebra no celular, e os
   dois botões juntos. */
.relatorio-form { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; }
.relatorio-form .f { min-width: 200px; flex: 1 1 200px; }
.relatorio-botoes { display: flex; gap: 8px; flex-wrap: wrap; }
```

- [ ] **Step 5: Rota e menu**

Em `fila/urls.py`, depois de `fila_historico`:

```python
    path("fila/relatorios", views_relatorios.relatorios, name="fila_relatorios"),
```
(e `views_relatorios` no `from . import (...)`).

Em `fila/modulo.py`, logo depois do atalho de "Histórico da fila":

```python
        # Os relatórios (28/09/2026): de quem lê os indicadores, e por isso
        # pela mesma permissão do painel.
        Atalho(rotulo=_("Relatórios"), rota="/fila/relatorios",
               permissao="fila.relatorios", grupo="Gerenciar Fila"),
```

- [ ] **Step 6: Rodar e ver passar** — `tests/test_fila_relatorios.py`, `tests/test_fila_modulo.py`, `tests/test_fila_tela_indicadores.py`, `tests/test_guarda.py`, `tests/test_guarda_modulo.py`, `tests/test_personificacao.py`, `tests/test_id_do_post.py`.

- [ ] **Step 7: Teste com dente** — em `relatorios`, troque `permitidas = ind.lojas_com_relatorio(pessoa, empresa)` por todas as filiais da empresa (`list(empresa.filiais.all())`); `test_gerente_so_ve_a_loja_dele` deve falhar. Desfaça.

- [ ] **Step 8: Commit**

```bash
git add fila/views_indicadores.py fila/views_relatorios.py fila/urls.py fila/modulo.py fila/static/fila/relatorio.css tests/test_fila_relatorios.py tests/test_fila_modulo.py
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -F - <<'EOF'
feat: a tela dos relatórios da fila

"Relatórios" em Gerenciar Fila: período (diário, ontem, semanal, mensal e
mês passado), loja e empresa, e dois botões — Gerar PDF e Gerar Excel.
Abre com `fila.relatorios`, a permissão do painel. O recorte sai de
`escolha_do_pedido`, extraída do painel para as duas telas lerem a MESMA
regra: o dono vê todas as lojas, o supervisor as da empresa dele, o
gerente as dele, e a loja forjada na URL cai dentro do alcance. A tela
funciona sem JavaScript.
EOF
```

---

### Task 5: Castelhano, documentação e conferência no navegador

**Files:**
- Modify: `locale/es/LC_MESSAGES/django.po` (+ compilar `.mo`), `CLAUDE.md`

- [ ] **Step 1: As frases no `django.po`** — acrescente, cada uma só se ainda não existir (`grep -c '^msgid "<frase>"$'`): "Diário (hoje)" → "Diario (hoy)"; "Semanal (últimos 7 dias)" → "Semanal (últimos 7 días)"; "Mensal (este mês)" → "Mensual (este mes)"; "Relatório da fila" → "Informe de la fila"; "Relatórios" → "Informes"; "Relatório" → "Informe"; "Resumo" → "Resumen"; "Comparação" → "Comparación"; "Vendedores" → "Vendedores"; "Motivos" → "Motivos"; "Mídias" já existe; "Grupos" → "Grupos"; "Pausas" → "Pausas"; "Lançamentos" → "Registros"; "Onde" → "Dónde"; "Total" → "Total"; "Indicador" → "Indicador"; "Neste período" → "En este período"; "No período anterior" → "En el período anterior"; "Variação" → "Variación"; "Data e hora" → "Fecha y hora"; "Resultado" → "Resultado"; "Valor" → "Valor"; "Observação" → "Observación"; "Fechado por" → "Cerrado por"; "Sim" → "Sí"; "Minutos" → "Minutos"; "Gerado por" → "Generado por"; "Gerado em" → "Generado en"; "Empresa"/"Lojas"/"Período" (conferir se existem); "Gerar PDF" → "Generar PDF"; "Gerar Excel" → "Generar Excel"; "Nenhuma loja em que você tira relatório." → "Ninguna tienda en la que usted saca informes."; "Os números das lojas que você acompanha, em PDF ou Excel." → "Los números de las tiendas que usted acompaña, en PDF o Excel."; "a" → "a". Compile: `.venv/bin/pybabel compile -d locale -D django`.

- [ ] **Step 2: `CLAUDE.md`** — no §10, depois de "### As metas (entrega 3)", uma seção:

```markdown
### Os relatórios (28/09/2026)

Spec `docs/superpowers/specs/2026-09-28-relatorios-da-fila-design.md`; plano
`docs/superpowers/plans/2026-09-28-relatorios-da-fila.md`.

- **`/fila/relatorios`**, em Gerenciar Fila, por `fila.relatorios` — a
  permissão do painel: quem lê os números na tela lê os mesmos no papel.
- **O recorte é o do painel** (`views_indicadores.escolha_do_pedido`, extraída
  para as duas telas): o dono vê todas as lojas, o supervisor as da empresa,
  o gerente as dele; a loja forjada cai dentro do alcance.
- **O relatório é DADO** (`fila/relatorio.py`: seções de colunas tipadas), e o
  Excel e o papel (`fila/relatorio_saida.py`) desenham o mesmo dado. Toda conta
  sai de `fila/indicadores.py`; a única nova é `lancamentos_do_recorte`.
- **O % da meta só nos períodos de mês**, e a pausa da gestão fora da pausa do
  vendedor, como no painel.
- **O Excel grava número** (moeda e porcentagem na célula), e não texto como a
  exportação das listas: relatório de números é para somar.
- **O PDF é a impressão do navegador**, como as listas, com o cabeçalho da
  tabela repetido em cada página.
```

E troque "153 arquivos" por "154 arquivos" (duas vezes). Confira com `ls tests/test_*.py | wc -l`.

- [ ] **Step 3: Suíte inteira** — `DJANGO_DEBUG=1 .venv/bin/python -m pytest -q -p no:cacheprovider`. Esperado: verde, fora os 4 de `tests/test_lugar.py` (mudança não commitada do usuário, que não é desta entrega).

- [ ] **Step 4: Navegador** — servidor local na 8015 (`DJANGO_DEBUG=1 .venv/bin/python manage.py runserver 127.0.0.1:8015`), logado como `sylvia@teste.com` (senha local `fila-local-123`): a tela em 390px e 1280px; o PDF aberto e salvo pelo Chrome headless (`page.pdf()`), conferindo as oito seções; o Excel baixado e aberto por `openpyxl`. Como `gil@teste.com`, com o cabeçalho no Centro, só o Centro.

- [ ] **Step 5: Commit**

```bash
git add locale/es/LC_MESSAGES/django.po locale/es/LC_MESSAGES/django.mo CLAUDE.md
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -F - <<'EOF'
docs: os relatórios da fila no CLAUDE.md, e o castelhano deles

A seção dos relatórios no §10 (o recorte do painel, o relatório como
dado, o % da meta só nos meses, o Excel com número e o PDF pela
impressão) e as frases da tela e do relatório em castelhano. Conferido
no navegador: a tela em 390px e 1280px, o PDF salvo pelo Chrome e o
Excel aberto por script.
EOF
```
