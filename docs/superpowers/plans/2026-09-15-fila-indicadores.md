# Indicadores da fila (entrega 2) — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dar à gestão a tela `/fila/indicadores` (números com comparação, gráficos, ranking e esquecidos) e ao vendedor a faixa "Seus números" na página `/fila`, calculando tudo na hora sobre o que a fila grava.

**Architecture:** `fila/periodo.py` resolve o período da URL e o período anterior, sem banco. `fila/indicadores.py` faz todas as contas sobre um `Recorte(empresa, lojas, periodo)`, sempre por `objects.da_empresa` e pelas lojas permitidas; o ranking é uma consulta de pessoas anotada por subconsultas (o `Atendimento.vendedor` não tem relação reversa). A tela usa os componentes do design system; a faixa do vendedor é um pedaço novo da página da fila.

**Tech Stack:** Django 5.2, Python 3.13, Postgres 16, Jinja2 (`nucleo`).

**Spec:** `docs/superpowers/specs/2026-09-15-fila-indicadores-design.md`

## Global Constraints

- Tudo em português do Brasil; comentário diz POR QUÊ.
- Commit: `git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit`. **Nunca** `Co-Authored-By` nem rodapé de "gerado com". Mensagem longa em português.
- Teste com dente: todo teste novo é visto vermelho uma vez, quebrando o código de propósito.
- Nada de produção, servidor, credencial ou `git push`.
- Nunca duas suítes ao mesmo tempo. Suíte inteira em segundo plano, com o resultado lido de `.superpowers/suite.log` (`.superpowers/pt > .superpowers/suite.log 2>&1; echo EXIT=$?`). Não usar `pkill -f`.
- Toda consulta de tela passa por `Model.objects.da_empresa(empresa)` e pelas lojas permitidas. Nunca `irrestritos` em `fila/indicadores.py` ou nas views.
- Guardas: `@exigir_permissao("fila.relatorios")` por fora, `@exigir_modulo_ligado("fila")` por dentro.
- Permissão nova `fila.relatorios`, no **fim** de `ModuloSpec.permissoes`.
- Atendimento entra no período pela hora do **fim**; aberto não entra.
- Conversão sem atendimento e ticket sem venda são "—", nunca 0.
- Variação da conversão em pontos percentuais; anterior zero sem seta.
- Tabela do ranking com filtro, ordenação e paginação (R46).
- Telas conferidas em captura (Playwright liberado pelo João nesta sessão) no computador e no celular antes do commit da tela.

**Comando de teste:** `.superpowers/pt <alvo>` (roda o pytest contra `fila_zero` no container do Portal).

## Decisões deste plano (o spec não respondia)

- **P-1 — "Atendimentos e vendas por dia" são dois gráficos.** O `Chart` do design system desenha uma série por gráfico. Saem "Atendimentos por dia" (barras) e "Vendido por dia" (linha); com um dia só, por hora.
- **P-2 — "Seus números" são os da loja em que a pessoa está.** A posição no ranking é da loja atual (spec), e números de outras lojas ao lado de uma posição desta confundiriam.
- **P-3 — Ordem descendente inverte o desempate inteiro.** `comum.listagem` inverte todos os campos da chave; o ranking padrão `-vendido` fica "vendido desc, conversão desc, nome desc". O nome só desempata o empate duplo.
- **P-4 — Intervalo livre de no máximo 366 dias.** Um intervalo maior cai no padrão: as contas são na hora (D2), e um "desde 2020" numa rede grande é o pedido que derruba a tela.

## Arquivos

```
fila/periodo.py                      Periodo, periodo_do_pedido, periodo_anterior, ATALHOS
fila/indicadores.py                  Recorte, Numeros, Variacao, Posicao, Esquecido e as contas
fila/views_indicadores.py            a tela /fila/indicadores
fila/static/fila/indicadores.css     variação ao lado do número e a grade da tela
fila/templates/fila/_meus.html       a faixa "Seus números"
fila/migrations/0002_indices_dos_indicadores.py
tests/test_fila_periodo.py
tests/test_fila_indicadores.py
tests/test_fila_tela_indicadores.py
```

Modificados: `fila/modulo.py`, `fila/models.py` (índices), `fila/urls.py`, `fila/tela.py`, `fila/templates/fila/pagina.html`, `fila/static/fila/fila.css`, `fila/static/fila/fila.js` (pedaço novo), `contas/cargos_de_fabrica.py`, `contas/fabrica.py`, `tests/test_fila_modulo.py`, `tests/test_cargos_de_fabrica.py`, `tests/test_lugar.py`, `tests/test_fila_pagina.py`, `CLAUDE.md`, `locale/es/LC_MESSAGES/django.po`.

---

### Task 1: O período

**Files:**
- Create: `fila/periodo.py`, `tests/test_fila_periodo.py`

**Interfaces:**
- Produces: `Periodo(de: datetime, ate: datetime, chave: str, rotulo: str)` (frozen; `de` inclusivo, `ate` exclusivo, ambos com fuso), propriedade `dias -> int`; `ATALHOS: tuple[tuple[str, str], ...]`; `PADRAO = "mes"`; `periodo_do_pedido(get: Mapping[str, str], agora: datetime | None = None) -> Periodo`; `periodo_anterior(periodo: Periodo, agora: datetime | None = None) -> Periodo`; `inicio_do_dia(dia: date) -> datetime`.

- [ ] **Step 1: Teste que falha**

`tests/test_fila_periodo.py`:

```python
"""O período dos indicadores e a comparação com o anterior (spec, "A
comparação"). Sem banco: é aritmética de datas, e é onde um número sai
errado sem ninguém ver."""

from datetime import date, datetime

import pytest
from django.utils import timezone

from fila.periodo import periodo_anterior, periodo_do_pedido


def local(*args):
    return timezone.make_aware(datetime(*args))


AGORA = local(2026, 9, 15, 14, 30)


@pytest.mark.parametrize("chave, de, ate", [
    ("hoje", local(2026, 9, 15), local(2026, 9, 16)),
    ("ontem", local(2026, 9, 14), local(2026, 9, 15)),
    ("7dias", local(2026, 9, 9), local(2026, 9, 16)),
    ("mes", local(2026, 9, 1), local(2026, 9, 16)),
    ("mes_passado", local(2026, 8, 1), local(2026, 9, 1)),
])
def test_cada_atalho(chave, de, ate):
    p = periodo_do_pedido({"periodo": chave}, AGORA)
    assert (p.de, p.ate, p.chave) == (de, ate, chave)


def test_sem_nada_e_este_mes():
    assert periodo_do_pedido({}, AGORA).chave == "mes"


def test_intervalo_livre_inclui_o_ultimo_dia():
    p = periodo_do_pedido({"de": "2026-09-01", "ate": "2026-09-10"}, AGORA)
    assert (p.de, p.ate, p.chave) == (local(2026, 9, 1), local(2026, 9, 11),
                                      "intervalo")
    assert p.rotulo == "01/09/2026 a 10/09/2026"


@pytest.mark.parametrize("de, ate", [
    ("2026-09-10", "2026-09-01"),        # invertido
    ("ontem", "2026-09-01"),             # não é data
    ("2024-01-01", "2026-09-01"),        # mais de 366 dias (P-4)
    ("2026-09-01", ""),                  # meio intervalo
])
def test_intervalo_ruim_cai_no_padrao(de, ate):
    assert periodo_do_pedido({"de": de, "ate": ate}, AGORA).chave == "mes"


def test_atalho_desconhecido_cai_no_padrao():
    assert periodo_do_pedido({"periodo": "sempre"}, AGORA).chave == "mes"


def test_hoje_em_andamento_compara_com_ontem_ate_a_mesma_hora():
    anterior = periodo_anterior(periodo_do_pedido({"periodo": "hoje"}, AGORA), AGORA)
    assert (anterior.de, anterior.ate) == (local(2026, 9, 14), local(2026, 9, 14, 14, 30))


def test_mes_em_andamento_compara_ate_o_mesmo_dia_e_hora():
    anterior = periodo_anterior(periodo_do_pedido({"periodo": "mes"}, AGORA), AGORA)
    assert (anterior.de, anterior.ate) == (local(2026, 8, 1), local(2026, 8, 15, 14, 30))


def test_mes_passado_mais_curto_compara_ate_o_ultimo_dia_dele():
    agora = local(2026, 10, 31, 10, 0)
    anterior = periodo_anterior(periodo_do_pedido({"periodo": "mes"}, agora), agora)
    assert (anterior.de, anterior.ate) == (local(2026, 9, 1), local(2026, 9, 30, 10, 0))


def test_periodo_fechado_compara_com_o_mesmo_tamanho_logo_antes():
    ontem = periodo_do_pedido({"periodo": "ontem"}, AGORA)
    assert (periodo_anterior(ontem, AGORA).de, periodo_anterior(ontem, AGORA).ate) == (
        local(2026, 9, 13), local(2026, 9, 14))
    passado = periodo_anterior(periodo_do_pedido({"periodo": "mes_passado"}, AGORA), AGORA)
    assert (passado.de, passado.ate) == (local(2026, 7, 1), local(2026, 8, 1))


def test_sete_dias_em_andamento():
    anterior = periodo_anterior(periodo_do_pedido({"periodo": "7dias"}, AGORA), AGORA)
    assert (anterior.de, anterior.ate) == (local(2026, 9, 2), local(2026, 9, 8, 14, 30))
```

- [ ] **Step 2: Rodar e ver falhar** — `.superpowers/pt tests/test_fila_periodo.py` → `ModuleNotFoundError: No module named 'fila.periodo'`.

- [ ] **Step 3: Implementação**

`fila/periodo.py`:

```python
"""O período dos indicadores: o que a URL pede, e com o que comparar.

Sem banco, de propósito: é aritmética de datas, testável sozinha, e é onde um
indicador sai errado sem ninguém perceber — um "Hoje" comparado com o ontem
inteiro mostra queda em toda manhã.

Os limites são instantes com fuso (`TIME_ZONE` da instalação): `de` inclusivo,
`ate` exclusivo. Um dia é [00:00, 00:00 do dia seguinte).
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone

__all__ = ["ATALHOS", "PADRAO", "Periodo", "inicio_do_dia",
           "periodo_anterior", "periodo_do_pedido"]

ATALHOS: "tuple[tuple[str, str], ...]" = (
    ("hoje", "Hoje"), ("ontem", "Ontem"), ("7dias", "7 dias"),
    ("mes", "Este mês"), ("mes_passado", "Mês passado"),
)
PADRAO = "mes"

#: Decisão P-4 do plano: as contas são feitas na hora, e um intervalo de anos
#: numa rede grande é o pedido que derruba a tela.
MAIOR_INTERVALO_EM_DIAS = 366


@dataclass(frozen=True)
class Periodo:
    de: datetime
    ate: datetime
    chave: str
    rotulo: str

    @property
    def dias(self) -> int:
        return max(1, round((self.ate - self.de).total_seconds() / 86400))


def inicio_do_dia(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time.min))


def _data(texto: "str | None") -> "date | None":
    try:
        return date.fromisoformat((texto or "").strip())
    except ValueError:
        return None


def _mesmo_dia_no_mes_anterior(momento: datetime) -> datetime:
    """14:30 do dia 15 -> 14:30 do dia 15 do mês anterior; dia 31 num mês de
    30 dias cai no dia 30 (spec, "A comparação")."""
    local = timezone.localtime(momento)
    ano, mes = (local.year, local.month - 1) if local.month > 1 else (local.year - 1, 12)
    dia = min(local.day, calendar.monthrange(ano, mes)[1])
    return timezone.make_aware(datetime.combine(date(ano, mes, dia), local.time()))


def _primeiro_do_mes_anterior(dia: date) -> date:
    return (dia.replace(day=1) - timedelta(days=1)).replace(day=1)


def periodo_do_pedido(get: Mapping, agora: "datetime | None" = None) -> Periodo:
    agora = agora or timezone.now()
    hoje = timezone.localdate(agora)

    if get.get("de") or get.get("ate"):
        de, ate = _data(get.get("de")), _data(get.get("ate"))
        if de and ate and de <= ate and (ate - de).days <= MAIOR_INTERVALO_EM_DIAS:
            return Periodo(inicio_do_dia(de), inicio_do_dia(ate + timedelta(days=1)),
                           "intervalo", f"{de:%d/%m/%Y} a {ate:%d/%m/%Y}")

    chave = get.get("periodo", "")
    rotulos = dict(ATALHOS)
    if chave not in rotulos:
        chave = PADRAO
    amanha = inicio_do_dia(hoje + timedelta(days=1))
    limites = {
        "hoje": (inicio_do_dia(hoje), amanha),
        "ontem": (inicio_do_dia(hoje - timedelta(days=1)), inicio_do_dia(hoje)),
        "7dias": (inicio_do_dia(hoje - timedelta(days=6)), amanha),
        "mes": (inicio_do_dia(hoje.replace(day=1)), amanha),
        "mes_passado": (inicio_do_dia(_primeiro_do_mes_anterior(hoje)),
                        inicio_do_dia(hoje.replace(day=1))),
    }[chave]
    return Periodo(*limites, chave, rotulos[chave])


def periodo_anterior(periodo: Periodo, agora: "datetime | None" = None) -> Periodo:
    """O período com que comparar.

    Em andamento (ainda não terminou), compara até o MESMO PONTO: meio dia
    contra um dia inteiro mostraria queda em todo começo de dia. O mês compara
    pelo calendário (dia 15 com dia 15), e não por tamanho: meses têm tamanhos
    diferentes. Terminado, compara com o mesmo tamanho logo antes.
    """
    agora = agora or timezone.now()
    rotulo = "Período anterior"
    if periodo.chave in ("mes", "mes_passado"):
        de_anterior = inicio_do_dia(_primeiro_do_mes_anterior(timezone.localdate(periodo.de)))
        if periodo.ate > agora:
            return Periodo(de_anterior, _mesmo_dia_no_mes_anterior(agora), "anterior", rotulo)
        return Periodo(de_anterior, periodo.de, "anterior", rotulo)
    tamanho = periodo.ate - periodo.de
    de_anterior = periodo.de - tamanho
    if periodo.ate > agora:
        return Periodo(de_anterior, de_anterior + (agora - periodo.de), "anterior", rotulo)
    return Periodo(de_anterior, periodo.de, "anterior", rotulo)
```

- [ ] **Step 4: Rodar e ver passar** — `.superpowers/pt tests/test_fila_periodo.py` → PASS.

- [ ] **Step 5: Quebrar de propósito** — trocar `de_anterior + (agora - periodo.de)` por `periodo.de` → os testes "em andamento" ficam vermelhos; tirar o `min(...)` do dia → o do mês mais curto estoura. Desfazer.

- [ ] **Step 6: Commit** (sem suíte inteira: arquivo novo sem dependentes; o `CLAUDE.md` conta arquivos de teste, então atualizar `N arquivos` nos dois lugares com `ls tests/test_*.py | wc -l` e rodar `.superpowers/pt tests/test_documentacao_nao_mente.py`)

```bash
git add fila/periodo.py tests/test_fila_periodo.py CLAUDE.md
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: o período dos indicadores da fila

Atalhos (hoje, ontem, 7 dias, este mês, mês passado) e intervalo livre,
lidos da URL, com o período anterior para a comparação. Período em
andamento compara até o mesmo ponto: hoje até 14:30 contra ontem até 14:30,
e o mês até o mesmo dia do mês anterior; senão toda manhã mostraria queda.
Data inválida, invertida ou intervalo de mais de um ano caem no padrão."
```

---

### Task 2: A permissão, os índices e as contas da gestão

**Files:**
- Create: `fila/indicadores.py`, `tests/test_fila_indicadores.py`, `fila/migrations/0002_indices_dos_indicadores.py` (gerada)
- Modify: `fila/modulo.py`, `fila/models.py` (Meta de `Atendimento` e `Pausa`), `contas/cargos_de_fabrica.py`, `contas/fabrica.py`, `tests/test_fila_modulo.py`, `tests/test_cargos_de_fabrica.py`, `tests/test_lugar.py`

**Interfaces:**
- Consumes: `fila.periodo.Periodo`, `inicio_do_dia`; models da entrega 1; `contas.lugar.filiais_da_pessoa(pessoa, empresa)`, `contas.lugar.permissoes_em(pessoa, empresa, filial)`.
- Produces:
  - `Recorte(empresa, lojas: tuple[Filial, ...], periodo: Periodo)` (frozen).
  - `Numeros(atendimentos: int, vendas: int, vendido: Decimal, pediu: int, vendas_pediu: int)` com propriedades `conversao -> float | None` (0–100), `ticket -> Decimal | None`, `conversao_pediu -> float | None`.
  - `Variacao(valor: float, unidade: str)` com `sobe -> bool`; `variacao(atual, anterior, *, pontos=False) -> Variacao | None`.
  - `numeros(recorte, vendedor=None) -> Numeros`.
  - `por_grupo(recorte) -> list[tuple[str, Decimal]]`, `motivos(recorte) -> list[tuple[str, int]]`, `pausa_por_tipo(recorte) -> list[tuple[str, int]]` (minutos), `por_dia(recorte) -> list[tuple[str, int, Decimal]]` (rótulo, atendimentos, vendido).
  - `Esquecido(o_que: str, nome: str, loja: Filial, desde: datetime)`; `esquecidos(empresa, lojas, agora=None) -> list[Esquecido]`.
  - `lojas_com_relatorio(pessoa, empresa) -> list[Filial]`.
  - `ModuloSpec.permissoes == ("fila.ver", "fila.participar", "fila.gerenciar", "fila.cadastros", "fila.relatorios")`.

- [ ] **Step 1: A permissão nova nos testes da entrega 1**

- `tests/test_fila_modulo.py`: `PERMISSOES_DA_FILA` ganha `"fila.relatorios"` no fim; o parametrizado de cargos passa a esperar `fila_relatorios` em `gerente` e `supervisor`; a asserção dos atalhos passa a `{"/fila/grupos", "/fila/motivos", "/fila/pausas", "/fila/indicadores"}` e as permissões dos atalhos a `{"fila.cadastros", "fila.relatorios"}`.
- `tests/test_cargos_de_fabrica.py`: supervisor e gerente esperam também `"fila_relatorios"` (as duas asserções de gerente e a de supervisor).
- `tests/test_lugar.py::test_cargo_traduz_para_o_vocabulario_do_nucleo`: acrescentar `"fila.relatorios"` ao conjunto do gerente.

Rodar `.superpowers/pt tests/test_fila_modulo.py tests/test_cargos_de_fabrica.py tests/test_lugar.py` → FAIL.

- [ ] **Step 2: A permissão no código**

`fila/modulo.py`: acrescentar `"fila.relatorios"` no **fim** de `permissoes`, com o comentário `# fila.relatorios (entrega 2) no fim: fila.ver continua a primeira, que é a do menu.`, e o atalho:

```python
        Atalho(rotulo=_("Indicadores da fila"), rota="/fila/indicadores",
               permissao="fila.relatorios", grupo="Vendas"),
```

`contas/cargos_de_fabrica.py`: `"fila.relatorios"` no fim das tuplas de supervisor e gerente, e no comentário: `fila.relatorios (entrega 2): gerente e supervisor leem os indicadores do alcance deles.`
`contas/fabrica.py`: `"fila.relatorios"` na lista do TITULAR (em ordem alfabética, depois de `"fila.participar"`).

Rodar os três arquivos do Step 1 → PASS.

- [ ] **Step 3: Os índices**

Em `fila/models.py`, `Atendimento.Meta.indexes` ganha `models.Index(fields=["empresa", "filial", "fim"], name="fila_atendimento_periodo")`, e `Pausa.Meta` ganha `indexes = [models.Index(fields=["filial", "inicio"], name="fila_pausa_periodo")]`, com o comentário: `# Os indicadores (entrega 2) filtram por empresa, loja e período a cada tela aberta.`

```bash
DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/fila_zero \
  .venv/bin/python manage.py makemigrations fila --name indices_dos_indicadores
```

- [ ] **Step 4: Os testes das contas**

`tests/test_fila_indicadores.py`:

```python
"""As contas dos indicadores (spec, "As regras de cálculo").

Cada cenário grava atendimentos com hora conhecida, direto nos models: o que
se prova aqui é a CONTA, e a fila tem os testes dela.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from fila.indicadores import (Recorte, esquecidos, lojas_com_relatorio,
                              motivos, numeros, pausa_por_tipo, por_dia,
                              por_grupo, variacao)
from fila.periodo import Periodo
from tests.fila_cenario import cadastros, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


def local(*args):
    return timezone.make_aware(datetime(*args))


SETEMBRO = Periodo(local(2026, 9, 1), local(2026, 10, 1), "intervalo", "setembro")


@pytest.fixture
def loja():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(empresa=empresa, matriz=matriz, titular=titular,
                           ana=pessoa_na_loja("ana", empresa, matriz),
                           bia=pessoa_na_loja("bia", empresa, matriz),
                           cad=cadastros(empresa))


def _presenca(loja, pessoa, filial=None):
    from fila.models import Presenca

    return Presenca.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, pessoa=pessoa,
        entrada=local(2026, 9, 1, 8), saida=local(2026, 9, 30, 18))


def atendimento(loja, pessoa, inicio, fim, *, vendeu=None, motivo=None,
                pediu=False, filial=None, itens=()):
    """Grava um atendimento. `vendeu` é o total; `itens` são (grupo, valor)."""
    from fila.models import Atendimento, ItemVendido

    a = Atendimento.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, vendedor=pessoa,
        presenca=_presenca(loja, pessoa, filial), inicio=inicio, fim=fim,
        cliente_pediu=pediu,
        resultado="" if fim is None else ("vendeu" if vendeu is not None else "nao_vendeu"),
        motivo=None if vendeu is not None or fim is None else (motivo or loja.cad.motivo),
        total=Decimal(vendeu or 0))
    for grupo, valor in itens:
        ItemVendido.irrestritos.create(empresa=loja.empresa, atendimento=a,
                                       grupo=grupo, valor=Decimal(valor))
    return a


def _recorte(loja, periodo=SETEMBRO, lojas=None):
    return Recorte(loja.empresa, tuple(lojas or [loja.matriz]), periodo)


def test_os_numeros_do_periodo(loja):
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d + timedelta(minutes=20), vendeu="1000")
    atendimento(loja, loja.ana, d, d + timedelta(minutes=30), vendeu="500", pediu=True)
    atendimento(loja, loja.bia, d, d + timedelta(minutes=10))
    atendimento(loja, loja.bia, d, d + timedelta(minutes=10), pediu=True)
    n = numeros(_recorte(loja))
    assert (n.atendimentos, n.vendas, n.vendido) == (4, 2, Decimal("1500"))
    assert n.conversao == 50.0
    assert n.ticket == Decimal("750")
    assert (n.pediu, n.vendas_pediu, n.conversao_pediu) == (2, 1, 50.0)


def test_conta_pelo_fim_e_nao_pelo_inicio(loja):
    atendimento(loja, loja.ana, local(2026, 8, 31, 23, 50),
                local(2026, 9, 1, 0, 10), vendeu="100")
    atendimento(loja, loja.ana, local(2026, 9, 30, 23, 50),
                local(2026, 10, 1, 0, 10), vendeu="100")
    assert numeros(_recorte(loja)).atendimentos == 1


def test_aberto_nao_conta(loja):
    atendimento(loja, loja.ana, local(2026, 9, 10, 10), None)
    assert numeros(_recorte(loja)).atendimentos == 0


def test_sem_atendimento_conversao_e_ticket_sao_nada(loja):
    n = numeros(_recorte(loja))
    assert (n.conversao, n.ticket, n.conversao_pediu) == (None, None, None)


def test_outra_loja_e_outra_empresa_nao_entram(loja):
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    centro = nova_loja(loja.empresa, "Centro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="100", filial=centro)
    outra = Empresa.objects.create(razao_social="Concorrente", nome_fantasia="C")
    abrir_conta(outra, "concorrente")
    outra.refresh_from_db()
    assert numeros(_recorte(loja)).atendimentos == 0
    assert numeros(Recorte(outra, (loja.matriz,), SETEMBRO)).atendimentos == 0
    assert numeros(_recorte(loja, lojas=[loja.matriz, centro])).atendimentos == 1


def test_numeros_de_um_vendedor(loja):
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="100")
    atendimento(loja, loja.bia, d, d, vendeu="300")
    assert numeros(_recorte(loja), vendedor=loja.bia).vendido == Decimal("300")


def test_correcao_muda_o_numero(loja):
    from fila.models import Atendimento

    d = local(2026, 9, 10, 10)
    a = atendimento(loja, loja.ana, d, d, vendeu="100")
    Atendimento.irrestritos.filter(pk=a.pk).update(total=Decimal("250"))
    assert numeros(_recorte(loja)).vendido == Decimal("250")


def test_variacao():
    assert variacao(120, 100).valor == 20.0
    assert variacao(120, 100).unidade == "%"
    assert variacao(80, 100).sobe is False
    assert variacao(10, 0) is None
    assert variacao(None, 50) is None
    pontos = variacao(24.0, 20.0, pontos=True)
    assert (pontos.valor, pontos.unidade) == (4.0, "p.p.")


def test_por_grupo_inclui_grupo_desativado(loja):
    from fila.models import GrupoDeItem

    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="900",
                itens=[(loja.cad.grupo, "600"), (loja.cad.grupo2, "300")])
    GrupoDeItem.irrestritos.filter(pk=loja.cad.grupo.pk).update(ativo=False)
    assert por_grupo(_recorte(loja)) == [("Sofás", Decimal("600")),
                                         ("Tapetes", Decimal("300"))]


def test_motivos(loja):
    from fila.models import MotivoDeNaoVenda

    caro = MotivoDeNaoVenda.irrestritos.create(empresa=loja.empresa, nome="Caro")
    d = local(2026, 9, 10, 10)
    for m in (caro, caro, loja.cad.motivo):
        atendimento(loja, loja.ana, d, d, motivo=m)
    assert motivos(_recorte(loja)) == [("Caro", 2), ("Só olhando", 1)]


def test_pausa_fechada_cortada_nas_bordas(loja):
    from fila.models import Pausa

    presenca = _presenca(loja, loja.ana)
    Pausa.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                             pessoa=loja.ana, presenca=presenca, tipo=loja.cad.tipo,
                             inicio=local(2026, 9, 10, 23, 40),
                             fim=local(2026, 9, 11, 0, 20))
    Pausa.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                             pessoa=loja.bia, presenca=_presenca(loja, loja.bia),
                             tipo=loja.cad.tipo, inicio=local(2026, 9, 11, 9))
    dia_11 = Periodo(local(2026, 9, 11), local(2026, 9, 12), "intervalo", "11")
    assert pausa_por_tipo(_recorte(loja, dia_11)) == [("Almoço", 20)]


def test_por_dia_preenche_os_dias_vazios(loja):
    atendimento(loja, loja.ana, local(2026, 9, 1, 10), local(2026, 9, 1, 10), vendeu="100")
    atendimento(loja, loja.ana, local(2026, 9, 3, 10), local(2026, 9, 3, 10))
    tres_dias = Periodo(local(2026, 9, 1), local(2026, 9, 4), "intervalo", "1 a 3")
    assert por_dia(_recorte(loja, tres_dias)) == [
        ("01/09", 1, Decimal("100")), ("02/09", 0, Decimal("0")), ("03/09", 1, Decimal("0"))]


def test_por_dia_de_um_dia_so_e_por_hora(loja):
    atendimento(loja, loja.ana, local(2026, 9, 1, 10), local(2026, 9, 1, 10, 5), vendeu="100")
    um_dia = Periodo(local(2026, 9, 1), local(2026, 9, 2), "hoje", "Hoje")
    linhas = por_dia(_recorte(loja, um_dia))
    assert len(linhas) == 24
    assert linhas[10] == ("10h", 1, Decimal("100"))


def test_esquecidos_so_o_que_virou_o_dia(loja):
    from fila.models import Presenca

    agora = local(2026, 9, 15, 11)
    Presenca.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                pessoa=loja.ana, entrada=local(2026, 9, 14, 9))
    Presenca.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                pessoa=loja.bia, entrada=local(2026, 9, 15, 9))
    atendimento(loja, loja.titular, local(2026, 9, 14, 17), None)
    lista = esquecidos(loja.empresa, [loja.matriz], agora)
    assert sorted((e.o_que, e.nome) for e in lista) == [
        ("Atendimento aberto", "sylvia@teste.com"), ("Presença aberta", "Ana")]


def test_lojas_com_relatorio_pelo_alcance(loja):
    centro = nova_loja(loja.empresa, "Centro")
    gil = pessoa_na_loja("gil", loja.empresa, centro, cargo="gerente")
    sara = pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    assert lojas_com_relatorio(gil, loja.empresa) == [centro]
    assert set(lojas_com_relatorio(sara, loja.empresa)) == {loja.matriz, centro}
    assert set(lojas_com_relatorio(loja.titular, loja.empresa)) == {loja.matriz, centro}
    assert lojas_com_relatorio(loja.ana, loja.empresa) == []
```

Antes de rodar, confirme o `nome` do titular criado por `tests/fila_cenario.sylvia` (`abrir_conta` não passa `nome`): se vier vazio, `nome_de` devolve o e-mail, que é o que o teste de esquecidos espera; ajuste a asserção se `email_de("sylvia")` for outro domínio (`grep -n "def email_de" -A6 tests/conftest.py`).

- [ ] **Step 5: Rodar e ver falhar** — `.superpowers/pt tests/test_fila_indicadores.py` → `ModuleNotFoundError: No module named 'fila.indicadores'`.

- [ ] **Step 6: Implementação**

`fila/indicadores.py`:

```python
"""As contas dos indicadores da fila (spec 2026-09-15, entrega 2).

Tudo é calculado na hora sobre o histórico (D2): a correção do gerente muda o
número na mesma hora, e não há resumo diário para ficar mentindo.

Duas regras valem para toda função daqui:
- **atendimento entra pela hora do fim**, e aberto não entra: o lançamento é
  do momento em que fechou, e aberto ainda não tem resultado;
- **toda consulta passa por `objects.da_empresa` e pelas lojas do recorte.**
  Nunca `irrestritos`: esta é a camada que as telas usam.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import (Count, DateTimeField, DecimalField, DurationField,
                              ExpressionWrapper, Q, Sum, Value)
from django.db.models.functions import Coalesce, Greatest, Least, TruncDate, TruncHour
from django.utils import timezone

from .estado import nome_de
from .models import Atendimento, ItemVendido, Pausa, Presenca, Resultado
from .periodo import Periodo, inicio_do_dia

__all__ = ["Esquecido", "Numeros", "Recorte", "Variacao", "esquecidos",
           "lojas_com_relatorio", "motivos", "numeros", "pausa_por_tipo",
           "por_dia", "por_grupo", "variacao"]

ZERO = Decimal("0")
_DINHEIRO = DecimalField(max_digits=14, decimal_places=2)


@dataclass(frozen=True)
class Recorte:
    empresa: object
    lojas: tuple
    periodo: Periodo


@dataclass(frozen=True)
class Numeros:
    atendimentos: int
    vendas: int
    vendido: Decimal
    pediu: int
    vendas_pediu: int

    @property
    def conversao(self) -> "float | None":
        # Sem atendimento é "nada", e não 0%: 0% diria que a loja atendeu e
        # não vendeu, e ela não atendeu ninguém.
        return round(100 * self.vendas / self.atendimentos, 1) if self.atendimentos else None

    @property
    def ticket(self) -> "Decimal | None":
        return (self.vendido / self.vendas).quantize(Decimal("0.01")) if self.vendas else None

    @property
    def conversao_pediu(self) -> "float | None":
        return round(100 * self.vendas_pediu / self.pediu, 1) if self.pediu else None


@dataclass(frozen=True)
class Variacao:
    valor: float
    unidade: str

    @property
    def sobe(self) -> bool:
        return self.valor > 0


def variacao(atual, anterior, *, pontos: bool = False) -> "Variacao | None":
    """A seta ao lado do número. Conversão varia em pontos percentuais: de 20%
    para 24% é "↑ 4 p.p.", e não "↑ 20%", que ninguém lê certo. Anterior zero
    não tem seta: não existe "cresceu x%" a partir de nada."""
    if atual is None or anterior is None:
        return None
    if pontos:
        return Variacao(round(float(atual) - float(anterior), 1), "p.p.")
    if not anterior:
        return None
    return Variacao(round((float(atual) - float(anterior)) * 100 / float(anterior), 1), "%")


def _atendimentos(recorte: Recorte):
    return (Atendimento.objects.da_empresa(recorte.empresa)
            .filter(filial__in=recorte.lojas, fim__gte=recorte.periodo.de,
                    fim__lt=recorte.periodo.ate))


def numeros(recorte: Recorte, vendedor=None) -> Numeros:
    consulta = _atendimentos(recorte)
    if vendedor is not None:
        consulta = consulta.filter(vendedor=vendedor)
    venda = Q(resultado=Resultado.VENDEU)
    return Numeros(**consulta.aggregate(
        atendimentos=Count("pk"),
        vendas=Count("pk", filter=venda),
        vendido=Coalesce(Sum("total", filter=venda), Value(ZERO), output_field=_DINHEIRO),
        pediu=Count("pk", filter=Q(cliente_pediu=True)),
        vendas_pediu=Count("pk", filter=venda & Q(cliente_pediu=True)),
    ))


def por_grupo(recorte: Recorte) -> "list[tuple[str, Decimal]]":
    return [(linha["grupo__nome"], linha["valor"]) for linha in (
        ItemVendido.objects.da_empresa(recorte.empresa)
        .filter(atendimento__filial__in=recorte.lojas,
                atendimento__fim__gte=recorte.periodo.de,
                atendimento__fim__lt=recorte.periodo.ate)
        .values("grupo__nome").annotate(valor=Sum("valor"))
        .order_by("-valor", "grupo__nome"))]


def motivos(recorte: Recorte) -> "list[tuple[str, int]]":
    return [(linha["motivo__nome"], linha["n"]) for linha in (
        _atendimentos(recorte).filter(resultado=Resultado.NAO_VENDEU)
        .values("motivo__nome").annotate(n=Count("pk"))
        .order_by("-n", "motivo__nome"))]


def pausa_por_tipo(recorte: Recorte) -> "list[tuple[str, int]]":
    """Minutos de pausa por tipo. Só pausas fechadas, e só a parte de cada uma
    que cai dentro do período: a pausa das 23:40 às 00:20 conta 20 minutos em
    cada dia."""
    de, ate = recorte.periodo.de, recorte.periodo.ate
    dentro = ExpressionWrapper(
        Least("fim", Value(ate, output_field=DateTimeField()))
        - Greatest("inicio", Value(de, output_field=DateTimeField())),
        output_field=DurationField())
    linhas = (Pausa.objects.da_empresa(recorte.empresa)
              .filter(filial__in=recorte.lojas, fim__isnull=False,
                      inicio__lt=ate, fim__gt=de)
              .annotate(dentro=dentro)
              .values("tipo__nome").annotate(total=Sum("dentro"))
              .order_by("-total", "tipo__nome"))
    return [(linha["tipo__nome"], int(linha["total"].total_seconds() // 60))
            for linha in linhas]


def por_dia(recorte: Recorte) -> "list[tuple[str, int, Decimal]]":
    """(rótulo, atendimentos, vendido) por dia; por hora quando o período é um
    dia só. Os vazios aparecem com zero: um gráfico que pula o dia sem
    atendimento esconde justamente o dia ruim."""
    fuso = timezone.get_current_timezone()
    por_hora = recorte.periodo.dias == 1
    fatia = TruncHour("fim", tzinfo=fuso) if por_hora else TruncDate("fim", tzinfo=fuso)
    venda = Q(resultado=Resultado.VENDEU)
    achados = {
        linha["fatia"]: (linha["n"], linha["v"]) for linha in (
            _atendimentos(recorte).annotate(fatia=fatia).values("fatia")
            .annotate(n=Count("pk"),
                      v=Coalesce(Sum("total", filter=venda), Value(ZERO),
                                 output_field=_DINHEIRO))
            .order_by("fatia"))}
    linhas = []
    if por_hora:
        for hora in range(24):
            momento = recorte.periodo.de + timedelta(hours=hora)
            n, v = achados.get(momento, (0, ZERO))
            linhas.append((f"{hora}h", n, v))
        return linhas
    dia = timezone.localdate(recorte.periodo.de)
    fim = timezone.localdate(recorte.periodo.ate)
    while dia < fim:
        n, v = achados.get(dia, (0, ZERO))
        linhas.append((dia.strftime("%d/%m"), n, v))
        dia += timedelta(days=1)
    return linhas


@dataclass(frozen=True)
class Esquecido:
    o_que: str
    nome: str
    loja: object
    desde: datetime


def esquecidos(empresa, lojas, agora: "datetime | None" = None) -> "list[Esquecido]":
    """O que ficou aberto de um dia para o outro (D7)."""
    hoje = inicio_do_dia(timezone.localdate(agora or timezone.now()))
    achados = []
    fontes = (
        ("Presença aberta", Presenca, "pessoa", "entrada", Q(saida__isnull=True)),
        ("Atendimento aberto", Atendimento, "vendedor", "inicio", Q(fim__isnull=True)),
        ("Pausa aberta", Pausa, "pessoa", "inicio", Q(fim__isnull=True)),
    )
    for rotulo, model, quem, comeco, aberto in fontes:
        for linha in (model.objects.da_empresa(empresa)
                      .filter(aberto, filial__in=lojas, **{f"{comeco}__lt": hoje})
                      .select_related(quem, "filial").defer(f"{quem}__avatar")):
            achados.append(Esquecido(rotulo, nome_de(getattr(linha, quem)),
                                     linha.filial, getattr(linha, comeco)))
    return sorted(achados, key=lambda e: e.desde)


def _cobre_relatorios(permissoes) -> bool:
    return "fila.relatorios" in permissoes or "fila.*" in permissoes


def lojas_com_relatorio(pessoa, empresa) -> list:
    """As lojas em que o cargo da pessoa traz `fila.relatorios`, pelo mesmo
    `contas.lugar` que decide a permissão em toda tela. O gerente de uma loja
    não tem a permissão em outra; supervisor e titular têm em todas."""
    from contas.lugar import filiais_da_pessoa, permissoes_em

    if pessoa is None or empresa is None:
        return []
    return [loja for loja in filiais_da_pessoa(pessoa, empresa)
            if pessoa.is_superuser
            or _cobre_relatorios(permissoes_em(pessoa, empresa, loja))]
```

Se o `TruncHour` devolver o instante em UTC em vez do local, as chaves de `achados` não casam com `recorte.periodo.de + timedelta(hours=h)` (que tem o fuso local): compare pelo `timezone.localtime(chave)` normalizando as duas pontas com `.replace(minute=0, second=0, microsecond=0)` e `timezone.localtime(...)` antes de montar o dicionário.

- [ ] **Step 7: Rodar e ver passar** — `.superpowers/pt tests/test_fila_indicadores.py` → PASS.

- [ ] **Step 8: Quebrar de propósito, uma de cada vez**
1. Em `_atendimentos`, trocar `fim__gte`/`fim__lt` por `inicio__gte`/`inicio__lt` → `test_conta_pelo_fim...` vermelho.
2. Em `Numeros.conversao`, devolver `0.0` sem atendimento → vermelho.
3. Em `pausa_por_tipo`, trocar `Least(...) - Greatest(...)` por `F("fim") - F("inicio")` → `test_pausa_fechada_cortada...` vermelho.
4. Em `lojas_com_relatorio`, devolver `list(filiais_da_pessoa(...))` → o do gerente e o da vendedora ficam vermelhos.
5. Em `variacao`, tirar o `if not anterior` → `test_variacao` vermelho.
Desfazer todas.

- [ ] **Step 9: Suíte inteira** em segundo plano; atualizar `N arquivos` no `CLAUDE.md`. Esperado: verde.

- [ ] **Step 10: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: as contas dos indicadores da fila

Nasce a permissão fila.relatorios (gerente, supervisor e titular), no fim da
lista do módulo para o fila.ver continuar sendo a do menu, e as contas da
tela de indicadores: atendimentos, vendas, conversão, vendido, ticket, a
parte do cliente pediu, vendido por grupo, motivos, tempo em pausa por tipo,
a série por dia (por hora num dia só) e o que ficou aberto de um dia para o
outro.

Atendimento entra pela hora do fim e aberto não entra. Conversão sem
atendimento é nada, e não 0%. A pausa conta só a parte que cai dentro do
período. As lojas de cada pessoa saem de contas.lugar, a mesma porta que
decide a permissão em toda tela. Dois índices cobrem os filtros por período."
```

---

### Task 3: O ranking e a posição do vendedor

**Files:**
- Modify: `fila/indicadores.py`, `tests/test_fila_indicadores.py`

**Interfaces:**
- Consumes: `Recorte`, `_atendimentos`, `numeros` (Task 2).
- Produces:
  - `ranking(recorte) -> QuerySet[Usuario]` com as anotações `atendimentos: int`, `vendas: int`, `vendido: Decimal`, `pediu: int`, `pausa: timedelta`, `conversao: float | None`, `ticket: Decimal | None`, sem `order_by` (quem ordena é `comum.listagem.montar_pagina`).
  - `ORDENAVEIS_DO_RANKING: dict[str, tuple[str, ...]]` e `PADRAO_DO_RANKING = "-vendido"`.
  - `Posicao(posicao: int, total: int)`; `posicao_no_mes(pessoa, loja, agora=None) -> Posicao | None`.

- [ ] **Step 1: Testes que falham** (acrescentar a `tests/test_fila_indicadores.py`)

```python
def test_ranking_e_de_quem_atendeu_e_nao_de_quem_fechou(loja):
    from fila.indicadores import ranking

    d = local(2026, 9, 10, 10)
    a = atendimento(loja, loja.ana, d, d, vendeu="400")
    a.fechado_por = loja.bia
    a.save(update_fields=["fechado_por"])
    linhas = {p.pk: p for p in ranking(_recorte(loja))}
    assert set(linhas) == {loja.ana.pk}
    assert linhas[loja.ana.pk].vendido == Decimal("400")


def test_ranking_anota_as_colunas(loja):
    from fila.indicadores import ranking
    from fila.models import Pausa

    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="300")
    atendimento(loja, loja.ana, d, d, vendeu="100", pediu=True)
    atendimento(loja, loja.ana, d, d)
    atendimento(loja, loja.ana, d, d)
    Pausa.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                             pessoa=loja.ana, presenca=_presenca(loja, loja.ana),
                             tipo=loja.cad.tipo, inicio=local(2026, 9, 10, 12),
                             fim=local(2026, 9, 10, 12, 45))
    ana = ranking(_recorte(loja)).get(pk=loja.ana.pk)
    assert (ana.atendimentos, ana.vendas, ana.vendido, ana.pediu) == (4, 2, Decimal("400"), 1)
    assert ana.conversao == 50.0
    assert ana.ticket == Decimal("200")
    assert ana.pausa == timedelta(minutes=45)


def test_ranking_ordena_por_vendido_e_soma_entre_lojas(loja):
    from fila.indicadores import PADRAO_DO_RANKING, ORDENAVEIS_DO_RANKING, ranking

    centro = nova_loja(loja.empresa, "Centro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="300")
    atendimento(loja, loja.ana, d, d, vendeu="300", filial=centro)
    atendimento(loja, loja.bia, d, d, vendeu="500")
    campos = tuple(f"-{c}" for c in ORDENAVEIS_DO_RANKING[PADRAO_DO_RANKING.lstrip("-")])
    ordem = ranking(_recorte(loja, lojas=[loja.matriz, centro])).order_by(*campos)
    assert [p.pk for p in ordem] == [loja.ana.pk, loja.bia.pk]


def test_posicao_no_mes_com_empate(loja):
    from fila.indicadores import posicao_no_mes

    caio = pessoa_na_loja("caio", loja.empresa, loja.matriz)
    agora = local(2026, 9, 20, 12)
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="500")
    atendimento(loja, loja.bia, d, d, vendeu="500")
    atendimento(loja, caio, d, d, vendeu="900")
    atendimento(loja, caio, local(2026, 8, 30, 10), local(2026, 8, 30, 10), vendeu="9999")
    assert posicao_no_mes(caio, loja.matriz, agora) == Posicao(1, 3)
    assert posicao_no_mes(loja.ana, loja.matriz, agora) == Posicao(2, 3)
    assert posicao_no_mes(loja.bia, loja.matriz, agora) == Posicao(2, 3)


def test_posicao_sem_venda_no_mes(loja):
    from fila.indicadores import posicao_no_mes

    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d)
    assert posicao_no_mes(loja.ana, loja.matriz, local(2026, 9, 20)) is None
```

com `from fila.indicadores import Posicao` no topo do arquivo.

- [ ] **Step 2: Rodar e ver falhar** — `.superpowers/pt tests/test_fila_indicadores.py -k "ranking or posicao"` → `ImportError`.

- [ ] **Step 3: Implementação** (acrescentar a `fila/indicadores.py`, e os nomes novos em `__all__`)

```python
from django.db.models import Case, F, FloatField, OuterRef, Subquery, When


def _por_pessoa(consulta, campo_da_pessoa: str, expressao, saida, zero):
    """Uma subconsulta que agrega `consulta` para a pessoa da linha de fora.

    Subconsulta, e não `annotate` pela relação: `Atendimento.vendedor` e
    `Pausa.pessoa` não têm relação reversa (`related_name="+"`), de propósito,
    para ninguém atravessar do usuário para o histórico sem passar pela
    empresa.
    """
    return Coalesce(
        Subquery(consulta.filter(**{campo_da_pessoa: OuterRef("pk")})
                 .order_by().values(campo_da_pessoa)
                 .annotate(x=expressao).values("x")[:1], output_field=saida),
        Value(zero, output_field=saida), output_field=saida)


ORDENAVEIS_DO_RANKING = {
    "nome": ("nome",),
    "vendido": ("vendido", "conversao", "nome"),
    "atendimentos": ("atendimentos", "nome"),
    "vendas": ("vendas", "nome"),
    "conversao": ("conversao", "nome"),
    "ticket": ("ticket", "nome"),
    "pediu": ("pediu", "nome"),
    "pausa": ("pausa", "nome"),
}
PADRAO_DO_RANKING = "-vendido"


def ranking(recorte: Recorte):
    """As pessoas que fecharam atendimento como vendedor no recorte, com as
    colunas do ranking. Quem fechou no lugar delas (`fechado_por`) não
    aparece por isso: a venda é de quem atendeu."""
    from contas.models import Usuario

    base = _atendimentos(recorte)
    venda = Q(resultado=Resultado.VENDEU)
    de, ate = recorte.periodo.de, recorte.periodo.ate
    pausas = (Pausa.objects.da_empresa(recorte.empresa)
              .filter(filial__in=recorte.lojas, fim__isnull=False,
                      inicio__lt=ate, fim__gt=de)
              .annotate(dentro=ExpressionWrapper(
                  Least("fim", Value(ate, output_field=DateTimeField()))
                  - Greatest("inicio", Value(de, output_field=DateTimeField())),
                  output_field=DurationField())))
    inteiro = DecimalField(max_digits=10, decimal_places=0)
    return (Usuario.objects.filter(pk__in=base.values("vendedor"))
            .defer("avatar")
            .annotate(
                atendimentos=_por_pessoa(base, "vendedor", Count("pk"), inteiro, 0),
                vendas=_por_pessoa(base, "vendedor", Count("pk", filter=venda), inteiro, 0),
                vendido=_por_pessoa(base, "vendedor", Sum("total", filter=venda), _DINHEIRO, ZERO),
                pediu=_por_pessoa(base, "vendedor", Count("pk", filter=Q(cliente_pediu=True)), inteiro, 0),
                pausa=_por_pessoa(pausas, "pessoa", Sum("dentro"), DurationField(), timedelta(0)),
            )
            .annotate(
                conversao=Case(When(atendimentos=0, then=Value(None)),
                               default=ExpressionWrapper(F("vendas") * 100.0 / F("atendimentos"),
                                                         output_field=FloatField()),
                               output_field=FloatField()),
                ticket=Case(When(vendas=0, then=Value(None)),
                            default=ExpressionWrapper(F("vendido") / F("vendas"),
                                                      output_field=_DINHEIRO),
                            output_field=_DINHEIRO),
            ))


@dataclass(frozen=True)
class Posicao:
    posicao: int
    total: int


def posicao_no_mes(pessoa, loja, agora: "datetime | None" = None) -> "Posicao | None":
    """A posição da pessoa no ranking de vendido da loja, no mês corrente,
    entre quem vendeu algo. Mesmo valor, mesma posição."""
    agora = agora or timezone.now()
    hoje = timezone.localdate(agora)
    mes = Periodo(inicio_do_dia(hoje.replace(day=1)),
                  inicio_do_dia(hoje + timedelta(days=1)), "mes", "Este mês")
    totais = dict(
        _atendimentos(Recorte(loja.empresa, (loja,), mes))
        .filter(resultado=Resultado.VENDEU)
        .values("vendedor").annotate(v=Sum("total"))
        .values_list("vendedor", "v"))
    meu = totais.get(pessoa.pk)
    if not meu:
        return None
    return Posicao(1 + sum(1 for v in totais.values() if v > meu), len(totais))
```

As contagens saem como `Decimal` por causa do `DecimalField` de saída do `Coalesce`: se o teste de `atendimentos == 4` falhar por tipo, troque `inteiro` por `IntegerField()` e o zero por `0` (o Postgres devolve `bigint` para `COUNT`, que casa com `IntegerField`).

- [ ] **Step 4: Rodar e ver passar** — `.superpowers/pt tests/test_fila_indicadores.py` → PASS.

- [ ] **Step 5: Quebrar de propósito**
1. Em `ranking`, trocar `filter(pk__in=base.values("vendedor"))` por `filter(pk__in=base.values("fechado_por"))` → o teste de quem fechou fica vermelho.
2. Em `posicao_no_mes`, trocar `v > meu` por `v >= meu` → o empate fica vermelho.
3. Tirar o `.filter(resultado=...)` de `posicao_no_mes` → o sem venda fica vermelho.
Desfazer.

- [ ] **Step 6: Commit**

```bash
git add fila/indicadores.py tests/test_fila_indicadores.py
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: o ranking de vendedores e a posição de cada um no mês

O ranking é uma consulta de pessoas com as colunas por subconsulta:
Atendimento.vendedor não tem relação reversa, de propósito, e ninguém
atravessa do usuário para o histórico sem passar pela empresa. A venda é de
quem atendeu, e não de quem fechou no lugar dele. A posição do vendedor é a
da loja em que ele está, no mês corrente, com empate na mesma posição."
```

---

### Task 4: A tela `/fila/indicadores`

**Files:**
- Create: `fila/views_indicadores.py`, `fila/static/fila/indicadores.css`, `tests/test_fila_tela_indicadores.py`
- Modify: `fila/urls.py`

**Interfaces:**
- Consumes: tudo de `fila.periodo` e `fila.indicadores`; `comum.listagem.montar_pagina`, `ColunaFiltravel`; componentes `nucleo.components` (`Alert`, `Button`, `Card`, `Cell`, `Chart`, `DataPoint`, `EmptyState`, `Form`, `FormGrid`, `Option`, `PageHeader`, `Raw`, `Select`, `Table`, `Column`, `TextInput`).
- Produces: rota `fila_indicadores` (`/fila/indicadores`), GET `?periodo=`, `?de=`, `?ate=`, `?loja=` (id).

- [ ] **Step 1: Testes que falham**

`tests/test_fila_tela_indicadores.py`:

```python
"""A tela de indicadores vista por quem a usa (spec, "Quem vê o quê")."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.fila_cenario import cadastros, logado, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


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


def _venda_hoje(rede, pessoa, loja, valor):
    from fila.models import Atendimento, Presenca

    agora = timezone.now()
    presenca = Presenca.irrestritos.create(empresa=rede.empresa, filial=loja,
                                          pessoa=pessoa, entrada=agora, saida=agora)
    return Atendimento.irrestritos.create(
        empresa=rede.empresa, filial=loja, vendedor=pessoa, presenca=presenca,
        inicio=agora - timedelta(minutes=5), fim=agora, resultado="vendeu",
        total=Decimal(valor))


def _html(cliente, **params):
    resposta = cliente.get(reverse("fila_indicadores"), params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_vendedor_nao_tem_a_tela(rede):
    assert logado("ana").get(reverse("fila_indicadores")).status_code == 404


def test_gerente_ve_so_a_loja_dele_e_a_forjada_e_descartada(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.ana, rede.matriz, "9000")
    gil = logado("gil")
    html = _html(gil, periodo="hoje")
    assert "Caio" in html and "Ana" not in html
    assert "R$ 700,00" in html
    forjada = _html(gil, periodo="hoje", loja=str(rede.matriz.pk))
    assert "Ana" not in forjada and "R$ 9.000,00" not in forjada


def test_supervisor_ve_todas_e_filtra_por_loja(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    _venda_hoje(rede, rede.ana, rede.matriz, "300")
    sara = logado("sara")
    assert "R$ 1.000,00" in _html(sara, periodo="hoje")
    so_matriz = _html(sara, periodo="hoje", loja=str(rede.matriz.pk))
    assert "R$ 300,00" in so_matriz and "Caio" not in so_matriz


def test_titular_ve_a_empresa(rede):
    _venda_hoje(rede, rede.caio, rede.centro, "700")
    assert "Caio" in _html(logado("sylvia"), periodo="hoje")


def test_ranking_tem_filtro_ordenacao_e_paginacao(rede):
    from tests.test_regra_tabela import (
        _MARCADOR_FILTRO, _MARCADOR_PAGINACAO, _PADRAO_CABECALHO_ORDENAVEL)

    _venda_hoje(rede, rede.caio, rede.centro, "700")
    html = _html(logado("sylvia"), periodo="hoje")
    assert "<table" in html
    assert _MARCADOR_FILTRO in html and _MARCADOR_PAGINACAO in html
    assert _PADRAO_CABECALHO_ORDENAVEL.search(html)


def test_aviso_de_esquecidos(rede):
    from fila.models import Presenca

    Presenca.irrestritos.create(empresa=rede.empresa, filial=rede.centro,
                                pessoa=rede.caio,
                                entrada=timezone.now() - timedelta(days=2))
    html = _html(logado("gil"), periodo="hoje")
    assert "Presença aberta" in html
    assert "Caio" in html


def test_sem_atendimento_mostra_traco_e_nao_zero_por_cento(rede):
    html = _html(logado("sylvia"), periodo="hoje")
    assert "0%" not in html
    assert "—" in html


def test_periodo_invalido_nao_estoura(rede):
    assert "Este mês" in _html(logado("sylvia"), de="2026-99-99", ate="x")


def test_menu_mostra_o_atalho_para_o_gerente_e_nao_para_o_vendedor(rede):
    assert 'href="/fila/indicadores"' in logado("gil").get("/").content.decode()
    ana = logado("ana").get("/fila").content.decode()
    assert 'href="/fila/indicadores"' not in ana
```

- [ ] **Step 2: Rodar e ver falhar** — `NoReverseMatch: 'fila_indicadores'`.

- [ ] **Step 3: A folha da tela**

`fila/static/fila/indicadores.css`:

```css
/* A tela de indicadores da fila. Só tokens do tema: é uma tela do dashboard
   como as outras. O que esta folha acrescenta é a variação ao lado do número,
   que o `StatCard` do design system não tem. */

.ind-numero { display: flex; flex-direction: column; gap: 4px; }
.ind-numero-l { font-size: 13px; font-weight: 600; color: var(--on-surface-2); }
.ind-numero-n {
  font-family: var(--font-display); font-size: 30px; font-weight: 800;
  letter-spacing: -.02em; font-variant-numeric: tabular-nums; line-height: 1.1;
}
.ind-numero-apoio { font-size: 12.5px; color: var(--on-surface-2); font-variant-numeric: tabular-nums; }
.ind-variacao { display: inline-flex; align-items: center; gap: 3px; font-size: 12.5px; font-weight: 700; font-variant-numeric: tabular-nums; }
.ind-variacao.sobe { color: var(--ok); }
.ind-variacao.desce { color: var(--danger); }
.ind-variacao.igual { color: var(--on-surface-2); }

.ind-filtros .formgrid { align-items: end; }
.ind-esquecidos ul { margin: 6px 0 0; padding-left: 18px; }
.ind-esquecidos li + li { margin-top: 2px; }
.ind-vazio { padding: 28px 12px; text-align: center; color: var(--on-surface-2); font-size: 13px; }
```

- [ ] **Step 4: A view**

`fila/views_indicadores.py`:

```python
"""A tela de indicadores da fila (spec 2026-09-15, entrega 2).

As lojas que a pessoa enxerga saem de `fila.indicadores.lojas_com_relatorio`,
e a `?loja=` da URL só filtra DENTRO delas: uma loja forjada não amplia o
recorte, ela é descartada e a tela mostra as permitidas.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.components import (Alert, Button, Card, Cell, Chart, Column,
                               DataPoint, EmptyState, Form, FormGrid, Option,
                               PageHeader, Raw, Select, Table, TextInput)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from . import indicadores as ind
from .periodo import ATALHOS, periodo_anterior, periodo_do_pedido
from .valores import em_reais

__all__ = ["indicadores"]


def _pct(valor) -> str:
    return "—" if valor is None else f"{valor:.1f}%".replace(".", ",")


def _dinheiro(valor) -> str:
    return "—" if valor is None else em_reais(valor)


def _variacao_html(v):
    if v is None:
        return ""
    classe = "sobe" if v.valor > 0 else "desce" if v.valor < 0 else "igual"
    seta = "↑" if v.valor > 0 else "↓" if v.valor < 0 else "="
    numero = f"{abs(v.valor):.1f}".replace(".", ",")
    return format_html('<span class="ind-variacao {}">{} {} {}</span>',
                       classe, seta, numero, v.unidade)


def _numero(rotulo, valor, variacao, apoio=""):
    return Card(body=Raw(html=format_html(
        '<div class="ind-numero"><span class="ind-numero-l">{}</span>'
        '<span class="ind-numero-n">{}</span>{}'
        '<span class="ind-numero-apoio">{}</span></div>',
        rotulo, valor, _variacao_html(variacao), apoio)))


def _grafico(titulo, pontos, tipo):
    corpo = (Chart(kind=tipo, points=pontos, legend="none" if tipo != "donut" else "right")
             if any(p.value for p in pontos)
             else Raw(html=format_html('<p class="ind-vazio">{}</p>',
                                       _("Nada no período."))))
    return Cell(span=6, children=Card(title=titulo, body=corpo))


def _lojas_do_pedido(request, permitidas):
    try:
        escolhida = int(request.GET.get("loja", ""))
    except ValueError:
        return permitidas, None
    uma = [loja for loja in permitidas if loja.pk == escolhida]
    return (uma, uma[0]) if uma else (permitidas, None)


def _filtros(request, periodo, permitidas, loja):
    campos = [
        Select(name="periodo", label=_("Período"), span=3,
               value=periodo.chave if periodo.chave != "intervalo" else "",
               empty_label=_("Intervalo"),
               options=[Option(chave, rotulo) for chave, rotulo in ATALHOS]),
        TextInput(name="de", label=_("De"), type="date", span=2,
                  value=request.GET.get("de", "")),
        TextInput(name="ate", label=_("Até"), type="date", span=2,
                  value=request.GET.get("ate", "")),
    ]
    if len(permitidas) > 1:
        campos.append(Select(
            name="loja", label=_("Loja"), span=3, value=str(loja.pk) if loja else "",
            empty_label=_("Todas as lojas"),
            options=[Option(str(l.pk), str(l)) for l in permitidas]))
    campos.append(Cell(span=2, children=Button(label=_("Aplicar"), variant="primary",
                                                type="submit")))
    return Card(body=Form(method="get", action=reverse("fila_indicadores"),
                          children=FormGrid(children=campos)))


def _esquecidos(lista):
    if not lista:
        return ""
    itens = format_html_join("", '<li>{}: {} em {}, desde {}. <a href="{}">{}</a></li>', (
        (e.o_que, e.nome, e.loja, e.desde.strftime("%d/%m %H:%M"),
         reverse("fila"), _("Abrir a fila")) for e in lista))
    return Alert(tone="warn", title=_("Ficou aberto de um dia para o outro"),
                 attrs={"class": "ind-esquecidos"},
                 message=Raw(html=format_html("<ul>{}</ul>", itens)))


_FILTRAVEIS = {"nome": ColunaFiltravel("nome", "Vendedor")}


def _colunas(pagina):
    return [
        Column("nome", pagina.cabecalho("nome", "Vendedor"), strong=True,
               render=lambda p: p.nome or p.email),
        Column("vendido", pagina.cabecalho("vendido", "Vendido"), align="num",
               render=lambda p: em_reais(p.vendido)),
        Column("atendimentos", pagina.cabecalho("atendimentos", "Atendimentos"), align="num"),
        Column("vendas", pagina.cabecalho("vendas", "Vendas"), align="num"),
        Column("conversao", pagina.cabecalho("conversao", "Conversão"), align="num",
               render=lambda p: _pct(p.conversao)),
        Column("ticket", pagina.cabecalho("ticket", "Ticket médio"), align="num",
               render=lambda p: _dinheiro(p.ticket)),
        Column("pediu", pagina.cabecalho("pediu", "Cliente pediu"), align="num"),
        Column("pausa", pagina.cabecalho("pausa", "Pausa"), align="num",
               render=lambda p: f"{int(p.pausa.total_seconds() // 60)} min"),
    ]


@exigir_permissao("fila.relatorios")
@exigir_modulo_ligado("fila")
def indicadores(request) -> HttpResponse:
    from plataforma.site import montar_site

    pessoa = usuario_de(request.usuario)
    empresa = empresa_atual(request)
    permitidas = ind.lojas_com_relatorio(pessoa, empresa)
    periodo = periodo_do_pedido(request.GET)

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        conteudo = [aviso_de_personificacao(request)]
        if not permitidas:
            conteudo.append(EmptyState(icon="store", title=_("Nenhuma loja para mostrar"),
                                       message=_("Os indicadores aparecem para as lojas em "
                                                 "que o seu cargo traz a permissão.")))
        else:
            lojas, loja = _lojas_do_pedido(request, permitidas)
            recorte = ind.Recorte(empresa, tuple(lojas), periodo)
            anterior = ind.Recorte(empresa, tuple(lojas), periodo_anterior(periodo))
            n, a = ind.numeros(recorte), ind.numeros(anterior)
            conteudo += [
                PageHeader(title=_("Indicadores da fila"),
                           subtitle=f"{periodo.rotulo}, {loja or _('todas as lojas')}"),
                _filtros(request, periodo, permitidas, loja),
                _esquecidos(ind.esquecidos(empresa, lojas)),
                FormGrid(children=[
                    Cell(span=3, children=_numero(_("Atendimentos"), n.atendimentos,
                                                  ind.variacao(n.atendimentos, a.atendimentos))),
                    Cell(span=3, children=_numero(
                        _("Conversão"), _pct(n.conversao),
                        ind.variacao(n.conversao, a.conversao, pontos=True),
                        f"Cliente pediu: {n.pediu}, {_pct(n.conversao_pediu)}")),
                    Cell(span=3, children=_numero(_("Vendido"), em_reais(n.vendido),
                                                  ind.variacao(n.vendido, a.vendido))),
                    Cell(span=3, children=_numero(_("Ticket médio"), _dinheiro(n.ticket),
                                                  ind.variacao(n.ticket, a.ticket))),
                ]),
            ]
            dias = ind.por_dia(recorte)
            conteudo.append(FormGrid(children=[
                _grafico(_("Atendimentos por hora") if periodo.dias == 1 else _("Atendimentos por dia"),
                         [DataPoint(r, n_) for r, n_, _v in dias], "bar"),
                _grafico(_("Vendido por hora") if periodo.dias == 1 else _("Vendido por dia"),
                         [DataPoint(r, float(v)) for r, _n, v in dias], "line"),
                _grafico(_("Vendido por grupo de item"),
                         [DataPoint(g, float(v)) for g, v in ind.por_grupo(recorte)], "bar_h"),
                _grafico(_("Motivos de não venda"),
                         [DataPoint(m, q) for m, q in ind.motivos(recorte)], "donut"),
                _grafico(_("Minutos em pausa por tipo"),
                         [DataPoint(t, m) for t, m in ind.pausa_por_tipo(recorte)], "bar_h"),
            ]))
            listagem = montar_pagina(request, ind.ranking(recorte),
                                     ordenaveis=ind.ORDENAVEIS_DO_RANKING,
                                     padrao=ind.PADRAO_DO_RANKING,
                                     filtraveis=_FILTRAVEIS)
            conteudo.append(Card(title=_("Ranking de vendedores"), padded=False, body=[
                listagem.barra,
                Table(columns=_colunas(listagem), rows=listagem.linhas),
                listagem.paginacao,
            ]))
        pagina = site.page(
            title=_("Indicadores da fila"), width="full",
            stylesheets=["/static/plataforma/listagem.css",
                         "/static/fila/indicadores.css"],
            content=conteudo, crumbs=[Crumb(_("Indicadores da fila"))],
            user=request.usuario)
        return render(pagina)
```

`fila/urls.py`: `path("fila/indicadores", views_indicadores.indicadores, name="fila_indicadores"),` e `views_indicadores` no import.

Pontos a conferir contra o design system, sem mudar a regra:
- `Alert` aceita `attrs`? (`grep -n "class Alert" -A12 nucleo/components/containers.py`). Se não aceitar, envolva o `Alert` num `Raw` com `<div class="ind-esquecidos">`.
- `Cell` dentro de `FormGrid` com `Button`: o botão precisa alinhar pela base dos campos; se ficar desalinhado, a regra `.ind-filtros .formgrid { align-items: end }` exige a classe `ind-filtros` no `Card` (use `Raw`/`attrs` como no item acima).
- `_("...")` com f-string: não é frase traduzível (é dado montado); o `Cliente pediu: …` fica em português até a tradução com `%(n)s`, e entra no §9 do `CLAUDE.md` junto com as frases de recusa.

- [ ] **Step 5: Rodar e ver passar** — `.superpowers/pt tests/test_fila_tela_indicadores.py` → PASS; depois `.superpowers/pt tests/test_guarda.py tests/test_guarda_modulo.py tests/test_personificacao.py tests/test_regra_tabela.py tests/test_id_do_post.py tests/test_variavel_de_cor_existe.py tests/test_sublinhado_e_o_gettext.py` → PASS. (O `_v`/`_n` nos `for` não usam `_` sozinho, por causa de `test_sublinhado_e_o_gettext.py`.)

- [ ] **Step 6: Quebrar de propósito**
1. Em `_lojas_do_pedido`, devolver a loja pedida mesmo fora de `permitidas` (buscar por `Filial.objects.filter(pk=escolhida)`) → o teste da loja forjada fica vermelho.
2. Tirar `listagem.barra` → o de R46 fica vermelho.
3. Em `_pct`, devolver `"0%"` para `None` → o do traço fica vermelho.
Desfazer.

- [ ] **Step 7: Conferir na tela** — com o servidor local, entrar como `sylvia@sylvia.test` e `gil@sylvia.test` e capturar `/fila/indicadores?periodo=mes` a 1366px e a 390px. Criticar como na página da fila (vãos, alinhamento dos filtros, gráfico vazio, tabela no celular) e corrigir antes do commit. A permissão nova só chega às contas criadas depois dela: no banco local, acrescentar `fila_relatorios` aos cargos `gerente` e `supervisor` da conta da Sylvia e rodar `aplicar(sylvia, Nivel.TITULAR)` pelo `manage.py shell`.

- [ ] **Step 8: Suíte inteira** em segundo plano; `N arquivos` no `CLAUDE.md`. Esperado: verde.

- [ ] **Step 9: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: a tela de indicadores da fila

/fila/indicadores mostra à gestão o período escolhido (atalhos ou
intervalo, na URL): o que ficou aberto de um dia para o outro, os quatro
números com a variação contra o período anterior, os gráficos por dia, por
grupo, por motivo e por tipo de pausa, e o ranking de vendedores com
filtro, ordenação e paginação.

As lojas saem do alcance do cargo, e a loja pedida na URL só filtra dentro
delas: uma forjada é descartada, e não amplia o recorte. Conversão sem
atendimento aparece como traço, e não como 0%."
```

---

### Task 5: "Seus números" na página da fila

**Files:**
- Create: `fila/templates/fila/_meus.html`
- Modify: `fila/tela.py` (`PEDACOS`, `_contexto`), `fila/templates/fila/pagina.html`, `fila/static/fila/fila.css`, `fila/static/fila/fila.js` (lista de pedaços), `tests/test_fila_pagina.py`

**Interfaces:**
- Consumes: `fila.indicadores.numeros(recorte, vendedor=...)`, `posicao_no_mes(pessoa, loja)`, `Recorte`, `fila.periodo.periodo_do_pedido`.
- Produces: `MeusNumeros(hoje: Numeros, mes: Numeros, posicao: Posicao | None)`; pedaço `meus` em `tela.PEDACOS` (`#fila-meus`); a resposta de `/fila/estado` e de `/fila/agir` passa a trazer `html.meus`.

- [ ] **Step 1: Testes que falham** (acrescentar a `tests/test_fila_pagina.py`)

```python
def test_seus_numeros_mostram_so_a_propria_pessoa(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="vendeu",
          grupo=[str(loja.cad.grupo.pk)], valor=["1.200"])
    bia = logado("bia")
    _agir(bia, acao="ponto")
    _agir(bia, acao="atender")
    _agir(bia, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk))
    html = _html(ana)
    assert "Seus números" in html
    assert "R$ 1.200,00" in html
    assert "1º de 1" in html
    bia_html = _html(bia)
    assert "R$ 1.200,00" not in bia_html
    assert "Sem vendas no mês" in bia_html


def test_quem_so_ve_nao_tem_seus_numeros(loja):
    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    assert "Seus números" not in _html(logado("sara"))


def test_a_consulta_traz_o_pedaco_dos_numeros(loja):
    ana = logado("ana")
    resposta = _agir_js(ana, acao="ponto")
    assert "meus" in resposta["html"]
```

e ajustar `test_acao_com_javascript_devolve_o_estado_novo`: o conjunto de pedaços passa a `{"painel", "lista", "barra", "lancamentos", "meus"}`.

- [ ] **Step 2: Rodar e ver falhar** — `.superpowers/pt tests/test_fila_pagina.py -k "numeros or pedaco or javascript"` → FAIL.

- [ ] **Step 3: O contexto**

Em `fila/tela.py`:

```python
PEDACOS = {"painel": "fila/_painel.html", "lista": "fila/_lista.html",
           "barra": "fila/_barra.html", "lancamentos": "fila/_lancamentos.html",
           "meus": "fila/_meus.html"}


@dataclass(frozen=True)
class MeusNumeros:
    """A faixa do vendedor (spec 2026-09-15 dos indicadores, decisão P-2 do
    plano): os números da loja em que ele está, hoje e no mês, e a posição."""

    hoje: object
    mes: object
    posicao: object


def _meus_numeros(pessoa, filial) -> "MeusNumeros | None":
    from .indicadores import Recorte, numeros, posicao_no_mes
    from .periodo import periodo_do_pedido

    if pessoa is None:
        return None
    lojas = (filial,)
    return MeusNumeros(
        hoje=numeros(Recorte(filial.empresa, lojas, periodo_do_pedido({"periodo": "hoje"})),
                     vendedor=pessoa),
        mes=numeros(Recorte(filial.empresa, lojas, periodo_do_pedido({"periodo": "mes"})),
                    vendedor=pessoa),
        posicao=posicao_no_mes(pessoa, filial))
```

e em `_contexto`, `"meus": _meus_numeros(pessoa, filial) if pode(request.usuario, "fila.participar") else None,`.

- [ ] **Step 4: O template**

`fila/templates/fila/_meus.html`:

```html
{# "Seus números": o dia e o mês de quem está na fila, na loja em que está. #}
{% macro coluna(titulo, n) %}
<div class="fila-meus-coluna">
  <p class="fila-meus-titulo">{{ titulo }}</p>
  <dl class="fila-meus-dl">
    <div><dt>{{ traduzir("Atendimentos") }}</dt><dd>{{ n.atendimentos }}</dd></div>
    <div><dt>{{ traduzir("Vendas") }}</dt><dd>{{ n.vendas }}</dd></div>
    <div><dt>{{ traduzir("Conversão") }}</dt><dd>{% if n.conversao is none %}—{% else %}{{ "%.0f"|format(n.conversao) }}%{% endif %}</dd></div>
    <div class="fila-meus-vendido"><dt>{{ traduzir("Vendido") }}</dt><dd>{{ n.vendido|reais }}</dd></div>
  </dl>
</div>
{% endmacro %}
{% if meus %}
<section class="card fila-meus">
  <header class="fila-secao-cab">
    <h2>{{ traduzir("Seus números") }}</h2>
    <span class="fila-meus-posicao">{% if meus.posicao %}{{ meus.posicao.posicao }}º {{ traduzir("de") }} {{ meus.posicao.total }} {{ traduzir("em vendas no mês") }}{% else %}{{ traduzir("Sem vendas no mês") }}{% endif %}</span>
  </header>
  <div class="fila-meus-corpo">
    {{ coluna(traduzir("Hoje"), meus.hoje) }}
    {{ coluna(traduzir("Este mês"), meus.mes) }}
  </div>
</section>
{% endif %}
```

`fila/templates/fila/pagina.html`: logo depois da `<section class="fila-hero">`, `<div id="fila-meus">{% include "fila/_meus.html" %}</div>`.

`fila/static/fila/fila.js`: na função `trocar`, a lista de pedaços passa a `["painel", "lista", "barra", "lancamentos", "meus"]`.

`fila/static/fila/fila.css` (antes do bloco "Tela média"):

```css
/* --- Seus números ----------------------------------------------------------- */
.fila-meus-posicao { font-size: 13px; font-weight: 700; color: var(--primary); }
.fila-meus-corpo { display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid var(--outline-2); }
.fila-meus-coluna { padding: 12px 20px 16px; }
.fila-meus-coluna + .fila-meus-coluna { border-left: 1px solid var(--outline-2); }
.fila-meus-titulo { margin: 0 0 8px; font-size: 12.5px; font-weight: 700; color: var(--on-surface-2); }
.fila-meus-dl { margin: 0; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.fila-meus-dl dt { font-size: 12px; color: var(--on-surface-2); }
.fila-meus-dl dd { margin: 2px 0 0; font-family: var(--font-display); font-size: 18px; font-weight: 800; font-variant-numeric: tabular-nums; }
.fila-meus-vendido dd { color: var(--ok); }
```

e, dentro do bloco `@media (max-width: 720px)`:

```css
  .fila-meus-corpo { grid-template-columns: 1fr; }
  .fila-meus-coluna + .fila-meus-coluna { border-left: 0; border-top: 1px solid var(--outline-2); }
  .fila-meus-dl { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fila-meus-coluna { padding: 10px 14px 14px; }
```

- [ ] **Step 5: Rodar e ver passar** — `.superpowers/pt tests/test_fila_pagina.py` → PASS.

- [ ] **Step 6: Quebrar de propósito** — em `_meus_numeros`, trocar `vendedor=pessoa` por `vendedor=None` no mês → `test_seus_numeros_mostram_so_a_propria_pessoa` vermelho (a Bia veria a venda da Ana). Desfazer.

- [ ] **Step 7: Conferir na tela** — capturar `/fila` como uma vendedora com vendas no mês, a 1366px e a 390px, e corrigir o que ficar apertado.

- [ ] **Step 8: Suíte inteira** em segundo plano. Esperado: verde.

- [ ] **Step 9: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "feat: o vendedor vê os próprios números na página da fila

Abaixo do cartão de status, a faixa 'Seus números' mostra hoje e o mês:
atendimentos, vendas, conversão, vendido e a posição no ranking de vendido
da loja. São só os números da própria pessoa, na loja em que ela está, e a
faixa é um pedaço da página trocado junto com a fila quando a versão muda."
```

---

### Task 6: Documentação e castelhano

**Files:**
- Modify: `CLAUDE.md` (§10 e §9), `locale/es/LC_MESSAGES/django.po` (e `.mo`), `docs/superpowers/specs/2026-09-15-fila-indicadores-design.md` (estado)

- [ ] **Step 1: CLAUDE.md** — no §10, depois de "O que custa esquecer", a subseção:

```markdown
### Os indicadores (entrega 2)

Spec `docs/superpowers/specs/2026-09-15-fila-indicadores-design.md`; plano
`docs/superpowers/plans/2026-09-15-fila-indicadores.md`.

- `fila.relatorios` abre `/fila/indicadores`; as lojas saem de
  `fila.indicadores.lojas_com_relatorio` (o cargo no lugar), e a `?loja=` só
  filtra dentro delas.
- `fila/periodo.py` resolve o período e o anterior (em andamento compara até
  o mesmo ponto); `fila/indicadores.py` faz as contas, na hora, sempre por
  `objects.da_empresa`.
- **Atendimento entra pela hora do fim**, e aberto não entra. Conversão sem
  atendimento é "—".
- **O ranking é por subconsulta**: `Atendimento.vendedor` e `Pausa.pessoa`
  não têm relação reversa, e é de propósito.
- "Seus números" na página da fila são os da loja em que a pessoa está.
- Permissão nova não chega sozinha às contas que já existem: a semeadura só
  cria cargo que falta.
```

No §9, acrescentar ao item das frases sem castelhano: "e as linhas de apoio montadas com número nos indicadores (`Cliente pediu: …`)". Estado do spec: `desenho aprovado e implementado na branch fila-da-vez`.

Rodar `.superpowers/pt tests/test_documentacao_nao_mente.py`.

- [ ] **Step 2: Castelhano** — extrair, atualizar e preencher como na entrega 1:

```bash
.venv/bin/python -m babel.messages.frontend extract -F babel.cfg -o locale/portal.pot \
  --no-location --omit-header -k _ -k gettext -k gettext_lazy -k "ngettext:1,2" \
  -k traduzir --input-dirs=contas,plataforma,comum,modulos,fila
.venv/bin/python -m babel.messages.frontend update -i locale/portal.pot -d locale \
  -D django --no-fuzzy-matching --ignore-obsolete
```

Preencher os `msgstr` vazios (tratamento "usted"; ex.: "Indicadores da fila" → "Indicadores de la fila", "Ranking de vendedores" → "Ranking de vendedores", "Seus números" → "Sus números", "Sem vendas no mês" → "Sin ventas en el mes", "Ficou aberto de um dia para o outro" → "Quedó abierto de un día para otro", "Todas as lojas" → "Todas las tiendas") e compilar com `.venv/bin/python -m babel.messages.frontend compile -d locale -D django`. Rodar `.superpowers/pt tests/test_idioma.py tests/test_entrada_em_castelhano.py`.

- [ ] **Step 3: Suíte inteira** em segundo plano. Esperado: verde.

- [ ] **Step 4: Commit**

```bash
git add -A
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit -m "docs: os indicadores da fila no CLAUDE.md, e o castelhano deles

O CLAUDE.md ganha a parte dos indicadores: onde mora cada conta, a regra do
fim do atendimento, o ranking por subconsulta e por que a permissão nova não
chega sozinha às contas que já existem. As frases da tela ganham castelhano;
as montadas com número ficam anotadas como em aberto."
```

---

## Self-review do plano

| spec | tarefa |
|---|---|
| D1 metas fora | fora do plano |
| D2 na hora, sem resumo | T2, T3 |
| D3 `fila.relatorios`; vendedor vê os próprios | T2 (permissão), T4 (tela), T5 (faixa) |
| D4 atalhos, intervalo, comparação | T1, T4 |
| D5 ranking por vendido, colunas, R46 | T3, T4 |
| D6 cliente pediu à parte | T2 (`Numeros`), T3 (`pediu`), T4 (linha de apoio) |
| D7 esquecidos | T2, T4 |
| Quem vê o quê / lojas forjadas | T2 (`lojas_com_relatorio`), T4 |
| Regras de cálculo (fim, aberto, "—", pausa cortada, grupo desativado) | T2 |
| Comparação (mesmo ponto, mês curto, p.p., anterior zero) | T1, T2 |
| Ranking (quem atendeu, soma entre lojas, desempate) | T3 |
| Posição (loja atual, mês, empate, sem venda) | T3, T5 |
| Índices | T2 |
| Varreduras | T4 |
| Castelhano, CLAUDE.md | T6 |

Nomes conferidos entre tarefas: `Recorte`, `Numeros.conversao/ticket/conversao_pediu`, `Variacao.valor/unidade/sobe`, `variacao(..., pontos=)`, `ranking`, `ORDENAVEIS_DO_RANKING`, `PADRAO_DO_RANKING`, `Posicao(posicao, total)`, `posicao_no_mes(pessoa, loja, agora)`, `Esquecido(o_que, nome, loja, desde)`, `lojas_com_relatorio(pessoa, empresa)`, `periodo_do_pedido(get, agora)`, `periodo_anterior(periodo, agora)`, rota `fila_indicadores`, pedaço `meus`.
