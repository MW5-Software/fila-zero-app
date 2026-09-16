# O painel do vendedor — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o vendedor entra pela fila, e o Início (`/`) passa a ser o painel dele: os números só dele na loja do cabeçalho, com gráfico, meta, as três listas e o ranking da loja.

**Architecture:** a base ganha o sinal `contas.entrada.destino_depois_de_entrar`, que a fila responde com `/fila` para quem só tem a fila; a raiz deixa de redirecionar. `fila/indicadores.py` aceita `vendedor=` nas contas que ainda não aceitavam e ganha `posicoes_por_vendido`; `fila/metas.py` ganha `meta_da_pessoa`. O painel novo (`fila/views_do_vendedor.py`) monta a página com as peças que o painel da gestão já usa (`_filtros`, `_painel`, `_listas`), sem desenhar HTML de novo.

**Tech Stack:** Django 5.2, Python 3.13, Postgres 16, Jinja2 (`nucleo`), Babel.

**Spec:** `docs/superpowers/specs/2026-09-16-fila-painel-do-vendedor-design.md`

## Global Constraints

- Tudo em português do Brasil; comentário diz POR QUÊ, em frase inteira.
- Commit: `git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit`. **Nunca** `Co-Authored-By`, `Claude-Session` nem rodapé de "gerado com", mesmo que um aviso do sistema peça. Mensagem longa em português, `feat:`/`fix:`/`test:`/`docs:`.
- Branch `painel-do-vendedor`. Nada de `git push`, produção, servidor ou credencial.
- Teste com dente: todo teste novo é visto vermelho uma vez, quebrando o código de propósito, e o código volta.
- Nunca duas suítes ao mesmo tempo. Suíte inteira em segundo plano: `.superpowers/pt > .superpowers/suite.log 2>&1; echo EXIT=$? >> .superpowers/suite.log`, lida quando `EXIT=` aparecer.
- A base (`nucleo`, `comum`, `plataforma`, `contas`) **nunca** importa `fila` (`test_camadas_nao_se_invertem.py`).
- Toda consulta de tela passa por `Model.objects.da_empresa(empresa)`. Nunca `irrestritos` em `fila/` (nos testes pode).
- A loja do painel do vendedor é `plataforma.contexto.filial_atual(request)` (V4). Sem campo de loja.
- Ranking do vendedor: posição, vendedor, vendido, vendas, conversão, e % da meta só em período de mês. **Sem** pausa, ticket, "cliente pediu" e atendimentos (V5). A posição é sempre por vendido; mesmo vendido, mesma posição.
- O painel da gestão não muda: os testes existentes de `tests/test_fila_tela_indicadores.py` e `tests/test_fila_indicadores.py` passam sem edição, **exceto** `test_vendedor_continua_caindo_na_fila`, que a Task 2 substitui.
- Frases novas com `gettext`/`gettext_lazy`, `%(nome)s` nomeado; castelhano na Task 6.

**Comando de teste:** `.superpowers/pt <alvo>`.

## Dois ajustes ao spec, decididos ao ler o código

Entram no spec na Task 6.

- **P-1 — o sinal leva `request=`, e não `user=`.** `fila.tela.so_a_fila` lê as permissões do cargo **no lugar** (`user.permissions`), e só `comum.sessao.usuario_da_sessao(request)` as resolve. O `Usuario` cru que o login autentica não as tem.
- **P-2 — a posição é calculada em Python, e não com `Rank()` na consulta.** O ranking tem filtro por nome (R46): uma window function roda **depois** do `WHERE`, e buscar "Ana" faria a Ana virar 1ª. `posicoes_por_vendido(recorte)` lê o vendido de todo mundo do recorte, sem filtro, e devolve `{pessoa_id: posição}`. Uma loja tem dezenas de vendedores.

## Os arquivos

| arquivo | o que muda |
|---|---|
| `contas/entrada.py` | o sinal e `destino_depois_de_entrar_para(request)` |
| `contas/views.py` | `entrar` redireciona para o destino |
| `tests/test_destino_depois_de_entrar.py` | novo: a regra da base |
| `fila/sinais.py`, `fila/apps.py` | o receptor do vendedor, ligado no `ready()` |
| `fila/views.py` | `inicio` sem o redirecionamento, com o ramo do vendedor |
| `fila/indicadores.py` | `vendedor=` em quatro contas; `posicoes_por_vendido` |
| `fila/metas.py` | `meta_da_pessoa` e `_vendido_ate_ontem` |
| `fila/views_indicadores.py` | `_listas(recorte, n, vendedor=None)` |
| `fila/views_do_vendedor.py` | novo: o painel |
| `fila/static/fila/indicadores.css` | a linha do vendedor no ranking |
| `fila/templates/fila/pagina.html`, `fila/tela.py`, `fila/static/fila/fila.css` | o link "Meu painel"; sai `mostra_painel` |
| `tests/test_fila_painel_do_vendedor.py` | novo: a tela vista pelo vendedor |
| `tests/test_fila_indicadores.py`, `tests/test_fila_metas.py`, `tests/test_fila_pagina.py`, `tests/test_fila_tela_indicadores.py` | testes novos; um substituído |
| `locale/`, `CLAUDE.md`, o spec | castelhano e documentação |

---

### Task 1: A base pergunta para onde mandar depois de entrar

**Files:**
- Modify: `contas/entrada.py`
- Modify: `contas/views.py:73-98` (`entrar`)
- Create: `tests/test_destino_depois_de_entrar.py`

**Interfaces:**
- Produces: `contas.entrada.destino_depois_de_entrar: django.dispatch.Signal`, enviado com `sender=None, request=request`; o receptor devolve `str | None`. `contas.entrada.destino_depois_de_entrar_para(request) -> str`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_destino_depois_de_entrar.py`:

```python
"""Para onde a pessoa vai depois de entrar (spec 2026-09-16, V2).

A base não conhece os módulos de negócio e não pode importá-los: ela pergunta
por um sinal. Estes testes ligam um receptor de mentira, porque a regra que se
prova aqui é a da BASE (quem responde decide, resposta estranha é ignorada), e
não a da fila.
"""

import pytest
from django.test import Client
from django.urls import reverse

from contas.entrada import destino_depois_de_entrar
from contas.models import Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        email="ana@teste.com", password="segredo-de-teste", nome="Ana")


@pytest.fixture
def responder():
    """Liga um receptor que responde `destino`, e desliga no fim: um receptor
    esquecido ligado mandaria todo login da suíte para outro lugar."""
    ligados = []

    def ligar(destino):
        def receptor(sender, request, **kwargs):
            return destino
        uid = f"teste-destino-{len(ligados)}"
        destino_depois_de_entrar.connect(receptor, dispatch_uid=uid, weak=False)
        ligados.append(uid)

    yield ligar
    for uid in ligados:
        destino_depois_de_entrar.disconnect(dispatch_uid=uid)


def _entrar():
    return Client().post(reverse("entrar"), {
        "usuario": "ana@teste.com", "senha": "segredo-de-teste"})


def test_sem_resposta_vai_para_a_raiz(ana):
    assert _entrar()["Location"] == "/"


def test_o_caminho_respondido_decide(ana, responder):
    responder("/fila")
    assert _entrar()["Location"] == "/fila"


@pytest.mark.parametrize("fora", [
    "https://fora.example/", "//fora.example/", "/\\fora.example",
    "fila", "", 42])
def test_resposta_que_nao_e_caminho_interno_e_ignorada(ana, responder, fora):
    """O sinal nunca pode virar redirecionamento aberto."""
    responder(fora)
    assert _entrar()["Location"] == "/"


def test_o_receptor_ve_a_pessoa_ja_dentro_da_sessao(ana, responder):
    """O negócio decide pelas permissões de quem entrou: quando o sinal sai,
    a sessão já tem a pessoa."""
    from comum.sessao import identidade_da_sessao

    vistos = []

    def receptor(sender, request, **kwargs):
        vistos.append(identidade_da_sessao(request))
    destino_depois_de_entrar.connect(receptor, dispatch_uid="teste-ve", weak=False)
    try:
        _entrar()
    finally:
        destino_depois_de_entrar.disconnect(dispatch_uid="teste-ve")
    assert [p.pk for p in vistos] == [ana.pk]


def test_senha_errada_nao_pergunta_nada(ana, responder):
    responder("/fila")
    resposta = Client().post(reverse("entrar"), {
        "usuario": "ana@teste.com", "senha": "errada"})
    assert resposta.status_code == 200
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.superpowers/pt tests/test_destino_depois_de_entrar.py`
Expected: FAIL com `ImportError: cannot import name 'destino_depois_de_entrar'`.

- [ ] **Step 3: Implementar**

Em `contas/entrada.py`, acrescentar aos imports:

```python
from django.dispatch import Signal
from django.utils.http import url_has_allowed_host_and_scheme
```

Trocar o `__all__` por:

```python
__all__ = ["CREDENCIAIS_INVALIDAS", "autenticar_e_entrar", "destino_depois_de_entrar",
           "destino_depois_de_entrar_para", "sair_e_registrar"]
```

E acrescentar, depois de `CREDENCIAIS_INVALIDAS`:

```python
#: Perguntado depois de um login que deu certo, com `request=` (a pessoa já
#: está na sessão). Quem responder um caminho interno decide para onde ela vai.
#:
#: Existe porque a base não conhece os módulos de negócio e não pode
#: importá-los (`CLAUDE.md` §3), mas é o negócio que sabe qual é a primeira
#: tela de quem entra: no Fila Zero, o vendedor abre a fila para trabalhar, e a
#: raiz é o painel dele (spec 2026-09-16). O desvio morava na raiz, e isso
#: tornava o Início inalcançável justamente para quem ganhava o painel. Leva a
#: requisição, e não a pessoa, porque a decisão depende das permissões do cargo
#: NO LUGAR, que só `usuario_da_sessao(request)` resolve.
destino_depois_de_entrar = Signal()


def destino_depois_de_entrar_para(request) -> str:
    """O primeiro caminho interno respondido pelo sinal, ou a raiz."""
    for _receptor, destino in destino_depois_de_entrar.send(sender=None, request=request):
        if _caminho_interno(destino):
            return destino
    return "/"


def _caminho_interno(destino) -> bool:
    """Só caminho desta instalação. `//fora` e `/\\fora` são lidos pelo
    navegador como outro host, e um receptor com defeito (ou um valor vindo
    de dado cadastrado) não pode transformar o login num redirecionamento
    aberto."""
    return (isinstance(destino, str) and destino.startswith("/")
            and not destino.startswith("//") and "\\" not in destino
            and url_has_allowed_host_and_scheme(destino, allowed_hosts=None))
```

Em `contas/views.py`, no `entrar`, trocar a última linha `return HttpResponseRedirect("/")` por:

```python
    return HttpResponseRedirect(destino_depois_de_entrar_para(request))
```

E acrescentar `destino_depois_de_entrar_para` ao import que já traz `autenticar_e_entrar` de `.entrada` (conferir com `grep -n "autenticar_e_entrar" contas/views.py`; se o import for de `contas.entrada`, usar o mesmo caminho).

- [ ] **Step 4: Rodar e ver passar**

Run: `.superpowers/pt tests/test_destino_depois_de_entrar.py tests/test_login.py tests/test_camadas_nao_se_invertem.py`
Expected: PASS.

- [ ] **Step 5: Ver o dente**

Tirar `and not destino.startswith("//")` de `_caminho_interno`, rodar `.superpowers/pt tests/test_destino_depois_de_entrar.py` e ver `test_resposta_que_nao_e_caminho_interno_e_ignorada[//fora.example/]` falhar. Se o `url_has_allowed_host_and_scheme` segurar sozinho e o teste não ficar vermelho, tirar a chamada a ele também, ver vermelho, e anotar na mensagem de commit que as duas travas cobrem o mesmo caso por segurança. Restaurar.

Trocar `return destino` por `return "/"` em `destino_depois_de_entrar_para` e ver `test_o_caminho_respondido_decide` falhar. Restaurar.

- [ ] **Step 6: Commit**

```bash
git add contas/entrada.py contas/views.py tests/test_destino_depois_de_entrar.py
git -c user.name="João Victor Vancim" -c user.email="developer1@kronos.net.br" commit
```

Mensagem: `feat: a base pergunta ao negócio para onde mandar quem acabou de entrar`, com o corpo dizendo que o login sempre ia para `/`, que o desvio do vendedor morava na raiz e trancava o Início para ele, que a base não importa o negócio e por isso é um sinal, no molde de `antes_de_desativar`, e que resposta que não é caminho interno é ignorada para não virar redirecionamento aberto.

---

### Task 2: O vendedor entra pela fila, e a raiz para de redirecionar

**Files:**
- Modify: `fila/sinais.py`
- Modify: `fila/apps.py`
- Modify: `fila/views.py:38-62` (`inicio`)
- Modify: `tests/test_fila_pagina.py:231-244`
- Modify: `tests/test_fila_tela_indicadores.py:66-68`

**Interfaces:**
- Consumes: `contas.entrada.destino_depois_de_entrar` (Task 1).
- Produces: `fila.sinais.destino_do_vendedor(sender, request, **kwargs) -> str | None`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_fila_pagina.py`, substituir a seção `# --- Onde se cai depois de entrar (D-4) ---` inteira (os dois testes) por:

```python
# --- Onde se cai depois de entrar (spec 2026-09-16, V1) ------------------------

def _entrar(loja, pessoa):
    from django.test import Client

    return Client().post(reverse("entrar"), {
        "usuario": pessoa.email, "senha": "segredo-de-teste"})


def test_quem_so_tem_a_fila_entra_por_ela(loja):
    """Sem `follow`: é o LOGIN que manda para a fila, e não a raiz."""
    assert _entrar(loja, loja.ana)["Location"] == reverse("fila")


def test_quem_tem_mais_que_a_fila_entra_pela_raiz(loja):
    assert _entrar(loja, loja.gil)["Location"] == "/"


def test_o_vendedor_abre_a_raiz_sem_ser_mandado_para_a_fila(loja):
    resposta = logado("ana").get("/")
    assert resposta.status_code == 200


def test_quem_tem_mais_que_a_fila_cai_no_painel(loja):
    resposta = logado("gil").get("/")
    assert resposta.status_code == 200
```

Em `tests/test_fila_tela_indicadores.py`, apagar `test_vendedor_continua_caindo_na_fila` (a regra mudou: V1 do spec 2026-09-16; os testes novos estão em `test_fila_pagina.py`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `.superpowers/pt tests/test_fila_pagina.py -k "entra_por_ela or abre_a_raiz"`
Expected: `test_quem_so_tem_a_fila_entra_por_ela` FAIL (`'/' == '/fila'`); `test_o_vendedor_abre_a_raiz_sem_ser_mandado_para_a_fila` FAIL (302).

- [ ] **Step 3: Implementar**

Em `fila/sinais.py`, trocar o `__all__` por `__all__ = ["destino_do_vendedor", "recusar_desativar_loja_com_gente"]` e acrescentar no fim:

```python
def destino_do_vendedor(sender, request, **kwargs) -> "str | None":
    """Quem só tem a fila de vendedor entra direto nela (spec 2026-09-16, V1).

    O desvio morava na raiz, e o Início ficava inalcançável para o vendedor
    justamente quando passou a ser o painel dele. Aqui ele vale só na
    entrada: depois, `/` abre o painel.

    Lê `usuario_da_sessao`, e não a pessoa crua, porque `so_a_fila` decide
    pelas permissões do cargo no lugar em que a sessão está.
    """
    from django.urls import reverse

    from comum.sessao import usuario_da_sessao

    from .tela import so_a_fila

    return reverse("fila") if so_a_fila(usuario_da_sessao(request)) else None
```

Em `fila/apps.py`, no `ready()`, trocar os imports e as ligações por:

```python
        from contas.entrada import destino_depois_de_entrar
        from plataforma.declaracao import registrar
        from plataforma.filiais import antes_de_desativar

        from .modulo import MODULO
        from .sinais import destino_do_vendedor, recusar_desativar_loja_com_gente

        registrar(MODULO)
        # `dispatch_uid`: o `ready()` pode rodar mais de uma vez nos testes, e
        # o receptor ligado duas vezes responderia duas vezes.
        antes_de_desativar.connect(recusar_desativar_loja_com_gente,
                                   dispatch_uid="fila_loja_com_gente")
        destino_depois_de_entrar.connect(destino_do_vendedor,
                                         dispatch_uid="fila_destino_do_vendedor")
```

Em `fila/views.py`, trocar o corpo inteiro de `inicio` (docstring incluída) por:

```python
@exigir_login
def inicio(request) -> HttpResponse:
    """A raiz. A gestão vê os indicadores da fila abaixo da saudação; o
    vendedor, o painel dele (spec 2026-09-16), preenchido na Task 4 do plano.

    Quem só tem a fila de vendedor era mandado daqui para `/fila` (D-4), e
    por isso nunca via o Início. O desvio passou para a entrada
    (`fila.sinais.destino_do_vendedor`): ele continua entrando pela fila, e a
    raiz é dele quando quiser.
    """
    from nucleo.views import home
    from plataforma.contexto import empresa_atual
    from plataforma.models import Modulo

    from .indicadores import lojas_com_relatorio
    from .views_indicadores import inicio_com_indicadores

    if not Modulo.objects.filter(chave="fila", ativo=True).exists():
        return home(request)
    empresa = empresa_atual(request)
    permitidas = lojas_com_relatorio(usuario_de(request.usuario), empresa)
    if permitidas:
        return inicio_com_indicadores(request, empresa, permitidas)
    return home(request)
```

(O ramo do vendedor entra na Task 4. Até lá, ele recebe a saudação.)

- [ ] **Step 4: Rodar e ver passar**

Run: `.superpowers/pt tests/test_fila_pagina.py tests/test_fila_tela_indicadores.py tests/test_destino_depois_de_entrar.py tests/test_login.py`
Expected: PASS.

- [ ] **Step 5: Ver o dente**

Em `destino_do_vendedor`, trocar `so_a_fila(...)` por `False` e ver `test_quem_so_tem_a_fila_entra_por_ela` falhar. Restaurar. Tirar a linha `destino_depois_de_entrar.connect(...)` do `ready()` e ver o mesmo teste falhar. Restaurar.

- [ ] **Step 6: Commit**

Mensagem: `feat: o vendedor entra pela fila, e a raiz deixa de mandá-lo para lá`, com o corpo dizendo que o desvio D-4 passou da raiz para o login pelo sinal da base, que o Início fica livre para o painel do vendedor, e por que o receptor lê `usuario_da_sessao`.

---

### Task 3: As contas recortadas pelo vendedor e a posição por vendido

**Files:**
- Modify: `fila/indicadores.py` (`__all__`, `por_grupo`, `motivos`, `pausa_por_tipo`, `por_dia`; nova `posicoes_por_vendido`)
- Modify: `fila/metas.py` (`__all__` se houver; `meta_do_recorte`; novas `_vendido_ate_ontem` e `meta_da_pessoa`)
- Test: `tests/test_fila_indicadores.py`, `tests/test_fila_metas.py`

**Interfaces:**
- Produces:
  - `por_grupo(recorte, vendedor=None) -> list[tuple[str, Decimal]]`
  - `motivos(recorte, vendedor=None) -> list[tuple[str, int]]`
  - `pausa_por_tipo(recorte, vendedor=None) -> list[tuple[str, int]]`
  - `por_dia(recorte, vendedor=None) -> list[Fatia]`
  - `posicoes_por_vendido(recorte) -> dict[int, int]` (pk da pessoa → posição; todo mundo que fechou atendimento como vendedor no recorte; mesmo vendido, mesma posição)
  - `fila.metas.meta_da_pessoa(recorte, pessoa, agora=None) -> MetaDoRecorte | None` (com `lojas_com_meta == lojas == len(recorte.lojas)` e `soma_vendedores == ZERO`, para `_faixa_da_meta` não escrever as frases da gestão)

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_fila_indicadores.py`, acrescentar `posicoes_por_vendido` ao import de `fila.indicadores`, e acrescentar no fim do arquivo:

```python
# --- Recortado pelo vendedor (spec 2026-09-16) --------------------------------

def test_as_contas_de_um_vendedor_so_trazem_as_dele(loja):
    from fila.models import MotivoDeNaoVenda, Pausa

    caro = MotivoDeNaoVenda.irrestritos.create(empresa=loja.empresa, nome="Caro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="600", itens=[(loja.cad.grupo, "600")])
    atendimento(loja, loja.bia, d, d, vendeu="300", itens=[(loja.cad.grupo2, "300")])
    atendimento(loja, loja.ana, d, d, motivo=caro)
    atendimento(loja, loja.bia, d, d)
    for pessoa, minutos in ((loja.ana, 10), (loja.bia, 30)):
        Pausa.irrestritos.create(
            empresa=loja.empresa, filial=loja.matriz, pessoa=pessoa,
            presenca=_presenca(loja, pessoa), tipo=loja.cad.tipo,
            inicio=local(2026, 9, 10, 12), fim=local(2026, 9, 10, 12, minutos))
    r = _recorte(loja)
    assert por_grupo(r, vendedor=loja.ana) == [("Sofás", Decimal("600"))]
    assert motivos(r, vendedor=loja.ana) == [("Caro", 1)]
    assert pausa_por_tipo(r, vendedor=loja.ana) == [("Almoço", 10)]
    dia = Periodo(local(2026, 9, 10), local(2026, 9, 11), "intervalo", "10")
    assert por_dia(_recorte(loja, dia), vendedor=loja.ana)[10] == ("10h", 2, Decimal("600"), 1)
    # Sem vendedor, a loja inteira, como sempre foi.
    assert por_grupo(r) == [("Sofás", Decimal("600")), ("Tapetes", Decimal("300"))]
    assert pausa_por_tipo(r) == [("Almoço", 40)]


def test_posicoes_por_vendido_com_empate_e_quem_nao_vendeu(loja):
    caio = pessoa_na_loja("caio", loja.empresa, loja.matriz)
    dora = pessoa_na_loja("dora", loja.empresa, loja.matriz)
    d = local(2026, 9, 10, 10)
    atendimento(loja, caio, d, d, vendeu="900")
    atendimento(loja, loja.ana, d, d, vendeu="500")
    atendimento(loja, loja.bia, d, d, vendeu="500")
    atendimento(loja, dora, d, d)  # atendeu e não vendeu: entra, em último
    assert posicoes_por_vendido(_recorte(loja)) == {
        caio.pk: 1, loja.ana.pk: 2, loja.bia.pk: 2, dora.pk: 4}


def test_posicoes_so_do_recorte(loja):
    centro = nova_loja(loja.empresa, "Centro")
    d = local(2026, 9, 10, 10)
    atendimento(loja, loja.ana, d, d, vendeu="100")
    atendimento(loja, loja.bia, d, d, vendeu="999", filial=centro)
    assert posicoes_por_vendido(_recorte(loja)) == {loja.ana.pk: 1}
```

Em `tests/test_fila_metas.py`, acrescentar depois de `test_meta_do_recorte_so_em_mes_e_so_das_lojas_com_meta`:

```python
def test_meta_da_pessoa_e_so_a_dela_contra_o_vendido_dela(loja):
    from fila.indicadores import Recorte
    from fila.metas import ZERO, meta_da_pessoa, primeiro_do_mes

    centro = nova_loja(loja.empresa, "Centro")
    agora = timezone.now()
    mes = primeiro_do_mes(timezone.localdate(agora))
    hoje = timezone.localtime(agora).replace(minute=0, second=0, microsecond=0)
    atendimento(loja, loja.ana, hoje, hoje, vendeu="1000")
    atendimento(loja, loja.bia, hoje, hoje, vendeu="7000")
    atendimento(loja, loja.ana, hoje, hoje, vendeu="5000", filial=centro)
    so_matriz = Recorte(loja.empresa, (loja.matriz,), _periodo("mes"))

    # A meta da LOJA não é a meta dela.
    meta(loja, valor="10000", mes=mes)
    assert meta_da_pessoa(so_matriz, loja.ana, agora) is None

    meta(loja, pessoa=loja.ana, valor="4000", mes=mes)
    meta(loja, pessoa=loja.ana, valor="8000", mes=mes, filial=centro)
    m = meta_da_pessoa(so_matriz, loja.ana, agora)
    assert m.acompanhamento.meta == Decimal("4000")
    assert m.acompanhamento.vendido == Decimal("1000")
    assert (m.lojas_com_meta, m.lojas, m.soma_vendedores) == (1, 1, ZERO)
    assert meta_da_pessoa(Recorte(loja.empresa, (loja.matriz,), _periodo("7dias")),
                          loja.ana, agora) is None
```

(Se `ZERO` não for exportado por `fila.metas`, importar `from decimal import Decimal` e usar `Decimal("0")` no lugar.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.superpowers/pt tests/test_fila_indicadores.py tests/test_fila_metas.py -k "vendedor or posicoes or meta_da_pessoa"`
Expected: FAIL por `ImportError` (`posicoes_por_vendido`, `meta_da_pessoa`) ou `TypeError: unexpected keyword argument 'vendedor'`.

- [ ] **Step 3: Implementar em `fila/indicadores.py`**

Acrescentar `"posicoes_por_vendido"` ao `__all__`, na ordem alfabética.

Substituir `_atendimentos` por:

```python
def _atendimentos(recorte: Recorte, vendedor=None):
    consulta = (Atendimento.objects.da_empresa(recorte.empresa)
                .filter(filial__in=recorte.lojas, fim__gte=recorte.periodo.de,
                        fim__lt=recorte.periodo.ate))
    return consulta if vendedor is None else consulta.filter(vendedor=vendedor)
```

Em `numeros`, trocar as três primeiras linhas do corpo por `consulta = _atendimentos(recorte, vendedor)`.

Substituir `por_grupo` e `motivos` por:

```python
def por_grupo(recorte: Recorte, vendedor=None) -> "list[tuple[str, Decimal]]":
    itens = (ItemVendido.objects.da_empresa(recorte.empresa)
             .filter(atendimento__filial__in=recorte.lojas,
                     atendimento__fim__gte=recorte.periodo.de,
                     atendimento__fim__lt=recorte.periodo.ate))
    if vendedor is not None:
        itens = itens.filter(atendimento__vendedor=vendedor)
    return [(linha["grupo__nome"], linha["valor"]) for linha in (
        itens.values("grupo__nome").annotate(valor=Sum("valor"))
        .order_by("-valor", "grupo__nome"))]


def motivos(recorte: Recorte, vendedor=None) -> "list[tuple[str, int]]":
    return [(linha["motivo__nome"], linha["n"]) for linha in (
        _atendimentos(recorte, vendedor).filter(resultado=Resultado.NAO_VENDEU)
        .values("motivo__nome").annotate(n=Count("pk"))
        .order_by("-n", "motivo__nome"))]
```

Em `pausa_por_tipo`, mudar a assinatura para `def pausa_por_tipo(recorte: Recorte, vendedor=None) -> "list[tuple[str, int]]":` e, logo antes de `linhas = (...)`, separar a consulta:

```python
    pausas = (Pausa.objects.da_empresa(recorte.empresa)
              .filter(filial__in=recorte.lojas, fim__isnull=False,
                      inicio__lt=ate, fim__gt=de))
    if vendedor is not None:
        pausas = pausas.filter(pessoa=vendedor)
    linhas = (pausas.annotate(dentro=dentro)
              .values("tipo__nome").annotate(total=Sum("dentro"))
              .order_by("-total", "tipo__nome"))
```

Em `por_dia`, mudar a assinatura para `def por_dia(recorte: Recorte, vendedor=None) -> "list[Fatia]":` e trocar `_atendimentos(recorte).annotate(fatia=fatia)` por `_atendimentos(recorte, vendedor).annotate(fatia=fatia)`.

Acrescentar, logo antes de `@dataclass(frozen=True) class Posicao`:

```python
def posicoes_por_vendido(recorte: Recorte) -> "dict[int, int]":
    """A posição de cada pessoa do ranking pelo vendido, qualquer que seja a
    ordem em que a tabela está (spec 2026-09-16, V5): reordenar por conversão
    não pode fazer alguém "subir" para o primeiro lugar. Mesmo vendido, mesma
    posição, e quem atendeu sem vender entra, no fim.

    Em Python, e não com `Rank()` na consulta do ranking: a tabela filtra por
    nome, e uma window function roda DEPOIS do filtro — buscar "Ana" a faria
    virar a primeira. Uma loja tem dezenas de vendedores."""
    venda = Q(resultado=Resultado.VENDEU)
    totais = dict(
        _atendimentos(recorte).values("vendedor")
        .annotate(v=Coalesce(Sum("total", filter=venda), Value(ZERO),
                             output_field=_DINHEIRO))
        .values_list("vendedor", "v"))
    return {pessoa: 1 + sum(1 for outro in totais.values() if outro > v)
            for pessoa, v in totais.items()}
```

- [ ] **Step 4: Implementar em `fila/metas.py`**

Acrescentar `"meta_da_pessoa"` ao `__all__` (se o arquivo tiver um). Substituir `meta_do_recorte` e acrescentar as duas funções, na ordem abaixo:

```python
def _vendido_ate_ontem(empresa, lojas, periodo, agora, vendedor=None) -> "Decimal | None":
    """O vendido do período até o fim de ontem, para a projeção (M5). `None`
    em período terminado: mês encerrado não tem ritmo."""
    from .indicadores import Recorte, numeros
    from .periodo import Periodo, inicio_do_dia

    if periodo.ate <= agora:
        return None
    ontem = Periodo(periodo.de, inicio_do_dia(timezone.localdate(agora)), "intervalo", "")
    return numeros(Recorte(empresa, lojas, ontem), vendedor=vendedor).vendido


def meta_do_recorte(recorte, agora: "datetime | None" = None) -> "MetaDoRecorte | None":
    """A meta das lojas do recorte contra o vendido DESSAS lojas.

    Em "Todas as lojas" com uma loja sem meta, somar a meta das outras e
    comparar com o vendido de todas faria a meta parecer batida por causa da
    loja sem meta; por isso as duas pontas saem das mesmas lojas.
    """
    from .indicadores import Recorte, numeros
    from .models import MetaDeVenda

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
    ate_ontem = _vendido_ate_ontem(recorte.empresa, com_meta, recorte.periodo, agora)
    return MetaDoRecorte(
        acompanhar(sum(por_loja.values(), ZERO), vendido, mes, agora, ate_ontem),
        len(com_meta), len(recorte.lojas), soma_vendedores)


def meta_da_pessoa(recorte, pessoa, agora: "datetime | None" = None) -> "MetaDoRecorte | None":
    """A meta de `pessoa` nas lojas do recorte contra o vendido DELA nelas: o
    painel do vendedor (spec 2026-09-16). A meta da loja não entra: ela não é
    a régua de ninguém em particular.

    Devolve o mesmo `MetaDoRecorte` do painel da gestão, para a mesma faixa
    desenhar os dois, com as lojas todas "com meta" e sem soma de vendedores:
    as frases de cobertura e de "N de M lojas" são conversa da gestão.
    """
    from .indicadores import numeros
    from .models import MetaDeVenda

    agora = agora or timezone.now()
    mes = mes_do_periodo(recorte.periodo)
    if mes is None:
        return None
    valores = list(MetaDeVenda.objects.da_empresa(recorte.empresa)
                   .filter(filial__in=recorte.lojas, mes=mes, pessoa=pessoa)
                   .values_list("valor", flat=True))
    if not valores:
        return None
    vendido = numeros(recorte, vendedor=pessoa).vendido
    ate_ontem = _vendido_ate_ontem(recorte.empresa, recorte.lojas, recorte.periodo,
                                   agora, vendedor=pessoa)
    lojas = len(recorte.lojas)
    return MetaDoRecorte(acompanhar(sum(valores, ZERO), vendido, mes, agora, ate_ontem),
                         lojas, lojas, ZERO)
```

Atenção: a condição de `_vendido_ate_ontem` é o contrário da antiga (`if recorte.periodo.ate > agora` calculava). `periodo.ate <= agora` devolve `None`; o comportamento é o mesmo.

- [ ] **Step 5: Rodar e ver passar**

Run: `.superpowers/pt tests/test_fila_indicadores.py tests/test_fila_metas.py tests/test_fila_tela_indicadores.py`
Expected: PASS, os antigos inclusive.

- [ ] **Step 6: Ver o dente**

- Em `por_grupo`, apagar o `if vendedor is not None:` e a linha abaixo → `test_as_contas_de_um_vendedor_so_trazem_as_dele` FAIL. Restaurar.
- Em `pausa_por_tipo`, o mesmo → FAIL. Restaurar.
- Em `posicoes_por_vendido`, trocar `outro > v` por `outro >= v` → `test_posicoes_por_vendido_com_empate_e_quem_nao_vendeu` FAIL. Restaurar.
- Em `meta_da_pessoa`, trocar `pessoa=pessoa` por `pessoa__isnull=True` → `test_meta_da_pessoa_e_so_a_dela_contra_o_vendido_dela` FAIL. Restaurar.

- [ ] **Step 7: Commit**

Mensagem: `feat: as contas dos indicadores recortadas por vendedor, e a posição por vendido`, com o corpo dizendo que a gestão chama sem `vendedor=` e não muda, por que a posição é em Python (o filtro por nome e a window function), e que a meta da pessoa reaproveita `MetaDoRecorte` para a mesma faixa desenhar os dois painéis.

---

### Task 4: O painel do vendedor no Início

**Files:**
- Create: `fila/views_do_vendedor.py`
- Modify: `fila/views_indicadores.py` (`_listas`)
- Modify: `fila/views.py` (`inicio`)
- Modify: `fila/static/fila/indicadores.css`
- Create: `tests/test_fila_painel_do_vendedor.py`

**Interfaces:**
- Consumes: `ind.numeros(recorte, vendedor=)`, `ind.por_dia(recorte, vendedor=)`, `ind.ranking(recorte, mes)`, `ind.posicoes_por_vendido(recorte)`, `regras_de_meta.meta_da_pessoa(recorte, pessoa)`, `regras_de_meta.mes_do_periodo(periodo)` (Task 3); `views_indicadores._filtros(request, periodo, permitidas, loja)`, `_painel(periodo, loja, n, a, anterior, fatias, meta=None)`, `_pct(valor)`.
- Produces: `fila.views_do_vendedor.inicio_do_vendedor(request, empresa, loja, pessoa) -> HttpResponse`; `views_indicadores._listas(recorte, n, vendedor=None)`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_fila_painel_do_vendedor.py`:

```python
"""O painel do vendedor no Início, visto por ele (spec 2026-09-16)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from tests.fila_cenario import cadastros, logado, nova_loja, pessoa_na_loja, sylvia

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja():
    from types import SimpleNamespace

    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz, titular=titular,
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        gil=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        cad=cadastros(empresa))


def _atendimento(loja, pessoa, valor=None, filial=None, motivo=None, grupo=None):
    """Um atendimento fechado agora. `valor` None é não venda."""
    from fila.models import Atendimento, ItemVendido, Presenca

    agora = timezone.now()
    filial = filial or loja.matriz
    presenca = Presenca.irrestritos.create(empresa=loja.empresa, filial=filial,
                                          pessoa=pessoa, entrada=agora, saida=agora)
    a = Atendimento.irrestritos.create(
        empresa=loja.empresa, filial=filial, vendedor=pessoa, presenca=presenca,
        inicio=agora - timedelta(minutes=5), fim=agora,
        resultado="vendeu" if valor else "nao_vendeu",
        motivo=None if valor else (motivo or loja.cad.motivo),
        total=Decimal(valor or 0))
    if valor and grupo:
        ItemVendido.irrestritos.create(empresa=loja.empresa, atendimento=a,
                                       grupo=grupo, valor=Decimal(valor))
    return a


def _html(cliente, **params):
    resposta = cliente.get("/", params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def _antes_do_ranking(html):
    return html.split('data-ind="ranking-da-loja"')[0]


def test_o_vendedor_ve_o_painel_dele_abaixo_da_saudacao(loja):
    html = _html(logado("ana"), periodo="hoje")
    assert html.index("Olá, Ana!") < html.index('data-ind="painel"')
    assert "Ranking da loja" in html
    assert "Ranking de vendedores" not in html


def test_os_numeros_as_listas_e_o_grafico_sao_so_dele(loja):
    _atendimento(loja, loja.ana, "300", grupo=loja.cad.grupo)
    _atendimento(loja, loja.bia, "7000", grupo=loja.cad.grupo2)
    antes = _antes_do_ranking(_html(logado("ana"), periodo="hoje"))
    assert "R$ 300,00" in antes
    assert "R$ 7.000,00" not in antes and "R$ 7.300,00" not in antes
    assert "Sofás" in antes and "Tapetes" not in antes


def test_so_a_loja_do_cabecalho(loja):
    from contas.models import Alocacao, Cargo
    from plataforma.contexto import CHAVE

    centro = nova_loja(loja.empresa, "Centro")
    Alocacao.objects.create(pessoa=loja.ana, empresa=loja.empresa, filial=centro,
                            cargo=Cargo.objects.get(conta_id=loja.empresa.conta_id,
                                                    nome="vendedor"))
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.ana, "900", filial=centro)
    ana = logado("ana")
    for filial, aparece, some in ((loja.matriz, "R$ 300,00", "R$ 900,00"),
                                  (centro, "R$ 900,00", "R$ 300,00")):
        sessao = ana.session
        sessao[CHAVE] = filial.pk
        sessao.save()
        antes = _antes_do_ranking(_html(ana, periodo="hoje"))
        assert aparece in antes and some not in antes
        assert str(filial) in antes
    assert 'name="loja"' not in _html(ana, periodo="hoje")


def test_o_ranking_nao_mostra_o_que_e_do_gerente(loja):
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.bia, "500")
    ranking = _html(logado("ana"), periodo="hoje").split('data-ind="ranking-da-loja"')[1]
    for coluna in ("Vendido", "Vendas", "Conversão", "Posição"):
        assert coluna in ranking
    for coluna in ("Pausa", "Ticket médio", "Cliente pediu", "Atendimentos"):
        assert f">{coluna}<" not in ranking
    assert "Bia" in ranking and "R$ 500,00" in ranking


def test_a_posicao_e_por_vendido_mesmo_reordenado(loja):
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.bia, "500")
    _atendimento(loja, loja.bia)
    _atendimento(loja, loja.bia)
    # Por conversão, Ana (100%) vem antes de Bia (33%), mas Bia continua 1ª.
    html = _html(logado("ana"), periodo="hoje", ordenar="-conversao")
    ranking = html.split('data-ind="ranking-da-loja"')[1]
    assert ranking.index("Ana") < ranking.index("Bia")
    assert "Você está em 2º de 2." in html
    linha_da_ana = ranking.split("Ana")[0].rsplit("<tr", 1)[1]
    assert "2º" in linha_da_ana


def test_ordenar_por_pausa_nao_vale_para_o_vendedor(loja):
    """A coluna não existe para ele; a URL forjada cai na ordem padrão."""
    _atendimento(loja, loja.ana, "300")
    html = _html(logado("ana"), periodo="hoje", ordenar="-pausa")
    assert "Ranking da loja" in html


def test_a_linha_dele_vem_marcada(loja):
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.bia, "500")
    ranking = _html(logado("ana"), periodo="hoje").split('data-ind="ranking-da-loja"')[1]
    marcada = ranking.split('aria-current="true"')[1].split("</tr>")[0]
    assert "Ana" in marcada and "Bia" not in marcada
    assert ranking.count('aria-current="true"') == 1


def test_quem_nao_fechou_atendimento_ve_a_frase_e_nenhuma_linha_marcada(loja):
    _atendimento(loja, loja.bia, "500")
    html = _html(logado("ana"), periodo="hoje")
    assert "Você não fechou atendimento no período." in html
    assert 'aria-current="true"' not in html.split('data-ind="ranking-da-loja"')[1]


def test_o_ranking_tem_filtro_ordenacao_e_paginacao(loja):
    from tests.test_regra_tabela import (
        _MARCADOR_FILTRO, _MARCADOR_PAGINACAO, _PADRAO_CABECALHO_ORDENAVEL)

    _atendimento(loja, loja.ana, "300")
    html = _html(logado("ana"), periodo="hoje")
    assert _MARCADOR_FILTRO in html and _MARCADOR_PAGINACAO in html
    assert _PADRAO_CABECALHO_ORDENAVEL.search(html)


def test_buscar_no_ranking_nao_muda_a_posicao(loja):
    _atendimento(loja, loja.ana, "300")
    _atendimento(loja, loja.bia, "500")
    ranking = _html(logado("ana"), periodo="hoje", **{"f:nome": "Ana"}).split(
        'data-ind="ranking-da-loja"')[1]
    assert "Bia" not in ranking.split("</form>", 1)[-1]
    assert "2º" in ranking


def test_a_meta_dele_aparece_so_no_mes_e_nao_a_da_loja(loja):
    from fila.metas import primeiro_do_mes
    from fila.models import MetaDeVenda

    mes = primeiro_do_mes(timezone.localdate())
    _atendimento(loja, loja.ana, "250")
    MetaDeVenda.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                   pessoa=None, mes=mes, valor=Decimal("90000"))
    ana = logado("ana")
    assert 'data-ind="meta"' not in _html(ana, periodo="mes")
    MetaDeVenda.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                   pessoa=loja.ana, mes=mes, valor=Decimal("1000"))
    html = _html(ana, periodo="mes")
    assert 'data-ind="meta"' in html and "Faltam R$ 750,00" in html
    assert "R$ 90.000,00" not in _antes_do_ranking(html)
    assert "lojas com meta" not in html and "metas dos vendedores" not in html
    assert 'data-ind="meta"' not in _html(ana, periodo="7dias")
    assert "% da meta" in _html(ana, periodo="mes")
    assert "% da meta" not in _html(ana, periodo="hoje")


def test_sem_esquecidos_no_painel_do_vendedor(loja):
    from fila.models import Presenca

    Presenca.irrestritos.create(empresa=loja.empresa, filial=loja.matriz,
                                pessoa=loja.bia,
                                entrada=timezone.now() - timedelta(days=2))
    assert "Ficou aberto de um dia para o outro" not in _html(logado("ana"), periodo="hoje")


def test_o_gerente_continua_com_o_painel_da_gestao(loja):
    html = _html(logado("gil"), periodo="hoje")
    assert "Ranking de vendedores" in html and "Ranking da loja" not in html


def test_quem_so_ve_a_fila_recebe_a_saudacao(loja):
    from tests.conftest import alocar, cargo_com

    rui = pessoa_na_loja("rui", loja.empresa, loja.matriz)
    alocar(rui, loja.empresa, cargo_com(loja.empresa, "fila.ver", nome="so-ve",
                                        alcance="filial"), filial=loja.matriz)
    html = _html(logado("rui"))
    assert "Olá, Rui!" in html and 'data-ind="painel"' not in html


def test_vendedor_sem_loja_recebe_a_saudacao_e_nao_500(loja):
    from contas.models import Alocacao

    Alocacao.objects.filter(pessoa=loja.ana).delete()
    html = _html(logado("ana"))
    assert "Olá, Ana!" in html and 'data-ind="painel"' not in html


def test_sem_atendimento_mostra_traco(loja):
    html = _html(logado("ana"), periodo="hoje")
    assert "Nenhum atendimento fechado no período." in html
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.superpowers/pt tests/test_fila_painel_do_vendedor.py`
Expected: a maioria FAIL (`data-ind="painel"` ausente: o vendedor ainda recebe a saudação). `test_o_gerente_continua_com_o_painel_da_gestao`, `test_quem_so_ve_a_fila_recebe_a_saudacao`, `test_vendedor_sem_loja_recebe_a_saudacao_e_nao_500` e `test_sem_esquecidos_no_painel_do_vendedor` podem passar já; é esperado.

Se `test_quem_so_ve_a_fila_recebe_a_saudacao` falhar na montagem (a assinatura de `cargo_com` pede as permissões num formato diferente), ler `tests/conftest.py:272-290` e ajustar só a chamada.

- [ ] **Step 3: `_listas` aceita o vendedor**

Em `fila/views_indicadores.py`, trocar o começo de `_listas` por:

```python
def _listas(recorte, n, vendedor=None):
    grupos = ind.por_grupo(recorte, vendedor)
    motivos = ind.motivos(recorte, vendedor)
    pausas = ind.pausa_por_tipo(recorte, vendedor)
```

(O resto da função não muda.)

- [ ] **Step 4: Criar `fila/views_do_vendedor.py`**

```python
"""O painel do vendedor no Início (spec 2026-09-16).

É o painel da gestão recortado pela pessoa, montado com as MESMAS peças
(`views_indicadores._filtros`, `_painel`, `_listas`): o vendedor aprende a
ler um painel só, e uma correção no desenho vale para os dois.

A loja é a do cabeçalho (V4), e o ranking é o da loja, sem o que é conversa
do gerente (V5).
"""

from __future__ import annotations

from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import Card, Column, PageHeader, Table
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render

from . import indicadores as ind
from . import metas as regras_de_meta
from .periodo import periodo_anterior, periodo_do_pedido
from .valores import em_reais
from .views_indicadores import _filtros, _listas, _painel, _pct

__all__ = ["inicio_do_vendedor"]

#: O que o vendedor ordena no ranking. Pausa, ticket, "cliente pediu" e
#: atendimentos ficam de fora (V5): tempo de pausa do colega é conversa do
#: gerente, e não placar. Fora daqui, `?ordenar=` forjado cai no padrão.
ORDENAVEIS = {chave: campos for chave, campos in ind.ORDENAVEIS_DO_RANKING.items()
              if chave in ("nome", "vendido", "vendas", "conversao")}
ORDENAVEIS_COM_META = {**ORDENAVEIS,
                       "pct_meta": ind.ORDENAVEIS_DO_RANKING_COM_META["pct_meta"]}
_FILTRAVEIS = {"nome": ColunaFiltravel("nome", "Vendedor")}


def _colunas(pagina, posicoes, com_meta):
    colunas = [
        # Sem cabeçalho ordenável: a posição é sempre pelo vendido, e "ordenar
        # por posição" seria ordenar pelo vendido com outro nome.
        Column("posicao", str(_("Posição")), align="num",
               render=lambda p: f"{posicoes[p.pk]}º"),
        Column("nome", pagina.cabecalho("nome", str(_("Vendedor"))), strong=True,
               render=lambda p: p.nome or p.email),
        Column("vendido", pagina.cabecalho("vendido", str(_("Vendido"))), align="num",
               render=lambda p: em_reais(p.vendido)),
        Column("vendas", pagina.cabecalho("vendas", str(_("Vendas"))), align="num"),
        Column("conversao", pagina.cabecalho("conversao", str(_("Conversão"))),
               align="num", render=lambda p: _pct(p.conversao)),
    ]
    if com_meta:
        colunas.append(Column("pct_meta", pagina.cabecalho("pct_meta", str(_("% da meta"))),
                              align="num", render=lambda p: _pct(p.pct_meta)))
    return colunas


def _onde_estou(posicoes, pessoa) -> str:
    minha = posicoes.get(pessoa.pk)
    if minha is None:
        # Não há linha para destacar: dizer isso evita o vendedor procurar
        # por si numa tabela em que ele não está.
        return str(_("Você não fechou atendimento no período."))
    return str(_("Você está em %(posicao)sº de %(total)s.")
               % {"posicao": minha, "total": len(posicoes)})


def _blocos(request, empresa, loja, pessoa) -> list:
    periodo = periodo_do_pedido(request.GET)
    lojas = (loja,)
    recorte = ind.Recorte(empresa, lojas, periodo)
    anterior = ind.Recorte(empresa, lojas, periodo_anterior(periodo))
    n = ind.numeros(recorte, vendedor=pessoa)
    a = ind.numeros(anterior, vendedor=pessoa)
    mes = regras_de_meta.mes_do_periodo(periodo)
    # As posições saem do recorte inteiro, antes do filtro por nome da
    # tabela: buscar "Ana" não pode fazer a Ana virar a primeira.
    posicoes = ind.posicoes_por_vendido(recorte)
    listagem = montar_pagina(request, ind.ranking(recorte, mes),
                             ordenaveis=ORDENAVEIS_COM_META if mes else ORDENAVEIS,
                             padrao=ind.PADRAO_DO_RANKING,
                             filtraveis=_FILTRAVEIS,
                             preservar=("periodo", "de", "ate"))
    return [
        # Uma loja só nas "permitidas": `_filtros` não desenha o campo de loja.
        _filtros(request, periodo, [loja], None),
        _painel(periodo, loja, n, a, anterior, ind.por_dia(recorte, vendedor=pessoa),
                meta=regras_de_meta.meta_da_pessoa(recorte, pessoa)),
        _listas(recorte, n, vendedor=pessoa),
        Card(title=_("Ranking da loja"), subtitle=_onde_estou(posicoes, pessoa),
             padded=False, attrs={"data-ind": "ranking-da-loja"}, body=[
                 listagem.barra,
                 Table(columns=_colunas(listagem, posicoes, com_meta=mes is not None),
                       rows=listagem.linhas,
                       row_attrs=lambda p: ({"class": "ind-eu", "aria-current": "true"}
                                            if p.pk == pessoa.pk else {})),
                 listagem.paginacao,
             ]),
    ]


def inicio_do_vendedor(request, empresa, loja, pessoa) -> HttpResponse:
    """O Início do vendedor: o "Olá" com a data, como para todo mundo, e o
    painel dele logo abaixo."""
    from nucleo.views import _data_de_hoje
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        pagina = site.page(
            title="Início", width="full",
            stylesheets=["/static/plataforma/listagem.css",
                         "/static/fila/indicadores.css"],
            content=[
                aviso_de_personificacao(request),
                PageHeader(title=site.resolve_nome("Olá, {nome}!", request.usuario),
                           subtitle=_data_de_hoje()),
                *_blocos(request, empresa, loja, pessoa),
            ],
            crumbs=[Crumb("Início")],
            user=request.usuario)
        return render(pagina)
```

- [ ] **Step 5: O ramo do vendedor em `inicio`**

Em `fila/views.py::inicio`, trocar a docstring por:

```python
    """A raiz. A gestão vê os indicadores da fila abaixo da saudação; quem
    vende na loja do cabeçalho, o painel dele (spec 2026-09-16); o resto, a
    saudação.

    Quem só tem a fila de vendedor era mandado daqui para `/fila` (D-4), e
    por isso nunca via o Início. O desvio passou para a entrada
    (`fila.sinais.destino_do_vendedor`): ele continua entrando pela fila, e a
    raiz é dele quando quiser.
    """
```

Acrescentar ao bloco de imports da função `from .views_do_vendedor import inicio_do_vendedor`, e trocar o fim (`if permitidas: ... return home(request)`) por:

```python
    if permitidas:
        return inicio_com_indicadores(request, empresa, permitidas)
    # `pode` já traz as permissões do cargo NA loja do cabeçalho: o vendedor
    # de uma loja que só vê a outra não ganha painel na outra.
    loja = filial_atual(request)
    if loja is not None and pode(request.usuario, "fila.participar"):
        return inicio_do_vendedor(request, empresa, loja, usuario_de(request.usuario))
    return home(request)
```

(`filial_atual`, `pode` e `usuario_de` já estão importados no topo de `fila/views.py`.)

- [ ] **Step 6: A linha do vendedor no CSS**

No fim de `fila/static/fila/indicadores.css`:

```css
/* --- O ranking da loja, no painel do vendedor ---------------------------- */

/* A linha de quem está olhando: é o "você está aqui" do placar. Fundo do
   tema, e não cor nova, para funcionar no claro e no escuro. */
tr.ind-eu td { background: var(--surface-2); font-weight: 700; }
```

Conferir que `--surface-2` é declarado (`.superpowers/pt tests/test_variavel_de_cor_existe.py`).

- [ ] **Step 7: Rodar e ver passar**

Run: `.superpowers/pt tests/test_fila_painel_do_vendedor.py tests/test_fila_tela_indicadores.py tests/test_fila_pagina.py tests/test_variavel_de_cor_existe.py tests/test_regra_tabela.py tests/test_personificacao.py tests/test_guarda.py`
Expected: PASS.

Se `test_buscar_no_ranking_nao_muda_a_posicao` falhar porque o nome do campo de filtro não é `f:nome`, ler `_MARCADOR_FILTRO` em `tests/test_regra_tabela.py` e o `name=` que a barra desenha (`grep -o 'name="f:[a-z]*"'` no HTML) e corrigir só o teste.

- [ ] **Step 8: Ver o dente**

- Em `_blocos`, trocar `vendedor=pessoa` por nada em `ind.numeros(recorte, ...)` → `test_os_numeros_as_listas_e_o_grafico_sao_so_dele` FAIL. Restaurar.
- Em `_blocos`, trocar `_listas(recorte, n, vendedor=pessoa)` por `_listas(recorte, n)` → o mesmo teste FAIL ("Tapetes"). Restaurar.
- Em `_colunas`, trocar `posicoes[p.pk]` por `listagem.linhas.index(p) + 1`, ou algo que numere pela ordem da tabela (ex.: um contador) → `test_a_posicao_e_por_vendido_mesmo_reordenado` FAIL. Restaurar.
- Em `ORDENAVEIS`, acrescentar `"pausa"` à tupla → nenhum teste de coluna quebra (a coluna não é desenhada), mas `test_ordenar_por_pausa_nao_vale_para_o_vendedor` continua passando: aceitável, a coluna não aparece. Restaurar sem registrar como dente.
- Em `inicio`, trocar `pode(request.usuario, "fila.participar")` por `True` → `test_quem_so_ve_a_fila_recebe_a_saudacao` FAIL. Restaurar.
- Em `inicio`, tirar `loja is not None and` → `test_vendedor_sem_loja_recebe_a_saudacao_e_nao_500` FAIL (500). Restaurar.
- Em `_blocos`, trocar `meta_da_pessoa(recorte, pessoa)` por `meta_do_recorte(recorte)` → `test_a_meta_dele_aparece_so_no_mes_e_nao_a_da_loja` FAIL. Restaurar.

- [ ] **Step 9: Conferir na tela**

Subir o servidor (`DJANGO_DEBUG=1 KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5434/fila_zero .venv/bin/python manage.py runserver 8005`), entrar como um vendedor com atendimentos no mês e capturar `/` em 1366 e em 390 de largura (Playwright). Conferir: a linha marcada legível no claro e no escuro, a tabela sem rolagem horizontal da página no celular, o título do painel com o nome da loja. Parar o servidor pela porta (`ss -ltnp | grep 8005`), nunca `pkill -f`.

- [ ] **Step 10: Commit**

Mensagem: `feat: o painel do vendedor no Início`, com o corpo dizendo que é o painel da gestão recortado pela pessoa com as mesmas peças, que a loja é a do cabeçalho, que o ranking não mostra pausa, ticket, "cliente pediu" e atendimentos, que a posição é por vendido e não muda ao reordenar nem ao buscar, e que a faixa da meta é só a meta dele.

---

### Task 5: "Meu painel" na página da fila

**Files:**
- Modify: `fila/templates/fila/pagina.html`
- Modify: `fila/tela.py:239` (sai `mostra_painel`)
- Modify: `fila/static/fila/fila.css`
- Test: `tests/test_fila_pagina.py`

**Interfaces:**
- Consumes: `pode_participar` do contexto da página (já existe em `fila/tela.py::_contexto`).

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_fila_pagina.py`, acrescentar depois de `test_quem_tem_mais_que_a_fila_cai_no_painel`:

```python
def test_quem_participa_acha_o_painel_pela_fila(loja):
    """Sem menu na página da fila, o link é o caminho do vendedor até o
    painel dele (spec 2026-09-16)."""
    html = _html(logado("ana"))
    assert 'href="/" data-meu-painel' in html and "Meu painel" in html


def test_quem_so_ve_a_fila_nao_tem_o_link_do_painel(loja):
    # Supervisor de fábrica: fila.ver e fila.gerenciar, sem fila.participar.
    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    assert "data-meu-painel" not in _html(logado("sara"))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.superpowers/pt tests/test_fila_pagina.py -k "painel_pela_fila or link_do_painel"`
Expected: `test_quem_participa_acha_o_painel_pela_fila` FAIL; o outro passa (o link ainda não existe para ninguém), e só ganha dente no Step 5.

- [ ] **Step 3: Implementar**

Em `fila/templates/fila/pagina.html`, dentro de `<div class="fila-hero-topo">`, trocar a linha do "Ao vivo" por:

```html
      <span class="fila-hero-direita">
        {% if pode_participar %}<a class="fila-meu-painel" href="/" data-meu-painel>{{ icon("chart-column", "sm") }}<span>{{ traduzir("Meu painel") }}</span></a>{% endif %}
        <span class="fila-hero-vivo" data-ao-vivo><span class="fila-vivo-ponto"></span><span data-ao-vivo-texto>{{ traduzir("Ao vivo") }}</span></span>
      </span>
```

Em `fila/tela.py`, apagar a linha `"mostra_painel": not so_a_fila(request.usuario),` do contexto. Ela nunca foi lida por template, e o que diz é o contrário do link: esconderia o painel justamente de quem só tem a fila.

Em `fila/static/fila/fila.css`, logo depois de `.fila-hero-vivo { ... }`:

```css
/* "Meu painel": a página da fila não tem menu, e este é o caminho do
   vendedor até o Início (spec 2026-09-16). Na cor do link da loja ao lado. */
.fila-hero-direita { display: inline-flex; align-items: center; gap: 14px; }
.fila-meu-painel { display: inline-flex; align-items: center; gap: 6px; color: var(--primary); text-decoration: none; }
.fila-meu-painel:hover { text-decoration: underline; }
.fila-hero:has(.painel-sua-vez) .fila-meu-painel { color: inherit; }
```

Conferir o ícone: `.venv/bin/python -c "from nucleo.icons import *; import nucleo.icons as i; print('chart-column' in i._LUCIDE)"`. Se não for `True`, usar `bar-chart-3`.

- [ ] **Step 4: Rodar e ver passar**

Run: `.superpowers/pt tests/test_fila_pagina.py tests/test_variavel_de_cor_existe.py tests/test_esconder_vence_o_display.py`
Expected: PASS.

- [ ] **Step 5: Ver o dente**

Trocar `{% if pode_participar %}` por `{% if false %}` → `test_quem_participa_acha_o_painel_pela_fila` FAIL. Trocar por `{% if true %}` → `test_quem_so_ve_a_fila_nao_tem_o_link_do_painel` FAIL. Restaurar.

- [ ] **Step 6: Conferir na tela**

Captura de `/fila` como vendedor em 390 e 1366, na vez dele (fundo `painel-sua-vez`) e fora dela: o link legível nos dois, sem quebrar a linha do topo no celular. Se quebrar em 390, esconder só o texto (`.fila-meu-painel span`) abaixo de 420px com uma classe de texto oculto já existente, nunca o link.

- [ ] **Step 7: Commit**

Mensagem: `feat: o link "Meu painel" na página da fila`, com o corpo dizendo que a página da fila não tem menu e o vendedor não tinha caminho até o Início, e que `mostra_painel` saiu porque ninguém a lia e ela dizia o contrário do que o link precisa.

---

### Task 6: Castelhano, documentação e a suíte

**Files:**
- Modify: `locale/portal.pot`, `locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-09-16-fila-painel-do-vendedor-design.md`

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

Preencher em castelhano do Paraguai, registro "usted", no mesmo tom das frases vizinhas:

| português | castelhano |
|---|---|
| Ranking da loja | Ranking de la tienda |
| Posição | Posición |
| Você não fechou atendimento no período. | Usted no cerró ninguna atención en el período. |
| Você está em %(posicao)sº de %(total)s. | Usted está en el %(posicao)sº lugar de %(total)s. |
| Meu painel | Mi panel |

Antes de gravar, conferir como o `.po` já traduz "loja" e "atendimento" (`grep -n 'msgid "Loja"\|msgid "Atendimentos"' -A1 locale/es/LC_MESSAGES/django.po`) e usar as mesmas palavras. Compilar:

```bash
.venv/bin/python -m babel.messages.frontend compile -d locale -D django
```

Run: `ls tests | grep -i "idioma\|castelhano"` e rodar os que existirem com `.superpowers/pt` → PASS.

- [ ] **Step 2: Documentação**

`CLAUDE.md` §10, "O que custa esquecer": trocar o item

```
- **Quem só tem `fila.ver` e `fila.participar` cai em `/fila`** ao pedir a
  raiz (`fila.views.inicio`, antes do `nucleo` em `config/urls.py`). Teste da
  base que pede a raiz com um vendedor precisa de outro cargo.
```

por

```
- **Quem só tem `fila.ver` e `fila.participar` entra por `/fila`**, mas a
  raiz é o painel dele. O desvio é do LOGIN, e não da raiz: a base pergunta
  pelo sinal `contas.entrada.destino_depois_de_entrar` e `fila/sinais.py`
  responde. Na raiz ele virava o Início inalcançável para o vendedor.
```

E acrescentar, depois da subseção "As metas (entrega 3)":

```
### O painel do vendedor

Spec `docs/superpowers/specs/2026-09-16-fila-painel-do-vendedor-design.md`;
plano `docs/superpowers/plans/2026-09-16-fila-painel-do-vendedor.md`.

- **O Início decide nesta ordem** (`fila.views.inicio`): `fila.relatorios` em
  alguma loja, o painel da gestão; `fila.participar` na loja do cabeçalho, o
  painel do vendedor (`fila/views_do_vendedor.py`); senão, a saudação.
- **É o painel da gestão recortado pela pessoa**, com as mesmas peças
  (`_filtros`, `_painel`, `_listas`) e as contas de `fila/indicadores.py`
  com `vendedor=`. A loja é a do cabeçalho, sem campo de loja.
- **O ranking da loja não mostra pausa, ticket, "cliente pediu" nem
  atendimentos.** A posição é sempre por vendido
  (`indicadores.posicoes_por_vendido`), calculada antes do filtro por nome:
  com `Rank()` na consulta, buscar "Ana" a faria virar a primeira.
- **A faixa da meta é só a meta dele** (`metas.meta_da_pessoa`); a meta da
  loja não é régua de ninguém em particular.
```

No spec, aplicar os ajustes P-1 e P-2 deste plano: em "V2" e em "As peças › Base", `user=` vira `request=` (com a frase do motivo: as permissões do cargo no lugar); em "As peças › Fila", o item do `ranking` com `Rank()` vira `posicoes_por_vendido(recorte)` em Python, com o motivo do filtro por nome; `destino_do_vendedor(sender, user, **kwargs)` vira `destino_do_vendedor(sender, request, **kwargs)`; e o "Estado" do cabeçalho vira `desenho aprovado e implementado na branch painel-do-vendedor (plano de 16/09/2026).`

- [ ] **Step 3: A suíte inteira**

```bash
.superpowers/pt > .superpowers/suite.log 2>&1; echo EXIT=$? >> .superpowers/suite.log
```

Em segundo plano; ler `.superpowers/suite.log` quando `EXIT=` aparecer. Expected: `EXIT=0`. Se `test_documentacao_nao_mente.py` falhar, ler a mensagem: ela diz qual afirmação do CLAUDE.md não confere (número de arquivos de teste em §3 e em "Como rodar" inclusive: dois arquivos novos, `test_destino_depois_de_entrar.py` e `test_fila_painel_do_vendedor.py`, e corrigir o número onde ele aparecer).

- [ ] **Step 4: Commit**

Mensagem: `docs: o painel do vendedor no CLAUDE.md, no spec e em castelhano`, com o corpo listando os dois ajustes do spec (P-1 e P-2) e por quê.

---

## Cobertura do spec

| spec | task |
|---|---|
| V1 (entra pela fila, raiz livre) | 2, 4 |
| V2 (sinal da base, caminho interno) | 1, 2 |
| V3 (espelho com as mesmas peças) | 3, 4 |
| V4 (loja do cabeçalho) | 4 |
| V5 (colunas do ranking, posição por vendido, linha marcada) | 3, 4 |
| V6 (sem esquecidos) | 4 |
| Quem vê o quê (ordem, sem permissão nova) | 4 |
| O painel (filtros, números, gráfico, meta, listas, ranking) | 3, 4 |
| "Meu painel", sai `mostra_painel` | 5 |
| Castelhano, CLAUDE.md | 6 |
| Bordas: sem filial, só `fila.ver`, período vazio, não fechou atendimento, destino inválido | 1, 4 |
| Personificação | 4 (Step 7, `test_personificacao.py`) |
| Camadas | 1 (Step 4) |
