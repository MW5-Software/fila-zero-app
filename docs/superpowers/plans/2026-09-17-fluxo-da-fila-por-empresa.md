# O fluxo da fila por empresa — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a empresa escolhe o que acontece depois de lançar o atendimento — voltar ao fim da fila (o fluxo de hoje, padrão) ou ficar em espera e entrar na fila quando quiser.

**Architecture:** um campo em `plataforma.Empresa` decide o fluxo; `fila.Estado` ganha `EM_ESPERA`; as ações do vendedor e as correções do gerente passam a perguntar o fluxo da empresa da loja antes de mandar alguém de volta para a fila.

**Tech Stack:** Django 5.2, Postgres, Jinja2, pytest (`KRONOS_BANCO` obrigatório).

**Spec:** `docs/superpowers/specs/2026-09-17-fluxo-da-fila-por-empresa-design.md`

## Global Constraints

- **O padrão é o fluxo de hoje** (`volta_para_a_fila`): instalação que já existe continua idêntica sem ninguém tocar em nada.
- **Espera não é pausa:** nenhuma `Pausa` é criada, e o tempo em espera não entra em nenhum indicador de pausa.
- **Um relógio só** (`acoes._agora()`), e toda ação sob `acoes._travar(filial)`, relendo o lugar depois da trava.
- Toda correção do gerente continua exigindo o motivo (`correcoes.ler_observacao`) e gravando `CorrecaoNaFila` + auditoria juntas.
- A página da fila funciona sem JavaScript; nenhum HTML é montado no script.
- Todo estado da fila tem rótulo e ícone na tela (regra da entrega 1).
- Frases em português no código, castelhano no `django.po` (`.venv/bin/pybabel compile -d locale -D django`).
- Comentário diz POR QUÊ, em português. Commits longos, autor `João Victor Vancim <developer1@kronos.net.br>`, sem coautor.
- Testes: `export KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5436/kronos DJANGO_DEBUG=1`, `.venv/bin/python -m pytest -q -p no:warnings <arquivos>`.
- Teste com dente: depois de verde, quebre o código de propósito, veja vermelho, desfaça. **Quebre a regra que o teste diz provar** — se ele continuar verde, é outra coisa que o segura (aconteceu duas vezes nas entregas anteriores).
- Branch `fluxo-da-fila`; uma task por commit.

---

### Task 1: O campo na empresa

**Files:**
- Modify: `plataforma/models.py` (`Empresa`), `plataforma/views_empresa.py`
- Create: `plataforma/migrations/0005_fluxo_da_fila.py` (gerada)
- Test: `tests/test_tela_empresa.py`

**Interfaces:**
- Produces: `plataforma.models.FluxoDaFila` (`TextChoices`: `VOLTA = "volta_para_a_fila"`, `ESPERA = "espera"`); `Empresa.fluxo_da_fila` (padrão `VOLTA`).

- [ ] **Step 1: Write the failing tests** (em `tests/test_tela_empresa.py`, no molde da classe do titular)

```python
@pytest.mark.django_db
class TestOFluxoDaFilaDaEmpresa:
    """17/09/2026: a empresa escolhe o que acontece depois de lançar."""

    def test_o_padrao_e_o_fluxo_de_hoje(self, db):
        from plataforma.models import Empresa, FluxoDaFila

        nova = Empresa.objects.create(razao_social="Padrao Ltda")
        assert nova.fluxo_da_fila == FluxoDaFila.VOLTA

    def test_o_titular_troca_o_fluxo_pela_tela(self, titular):
        from plataforma.models import Empresa, FluxoDaFila

        alvo = Empresa.objects.get(razao_social="Normadin Ltda")
        titular.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Normadin Ltda", "fluxo_da_fila": "espera"})
        alvo.refresh_from_db()
        assert alvo.fluxo_da_fila == FluxoDaFila.ESPERA

    def test_valor_forjado_nao_troca_o_fluxo(self, titular):
        from plataforma.models import Empresa, FluxoDaFila

        alvo = Empresa.objects.get(razao_social="Normadin Ltda")
        titular.post(reverse("empresa"), {
            "acao": "salvar", "empresa": str(alvo.pk),
            "razao_social": "Normadin Ltda", "fluxo_da_fila": "voar"})
        alvo.refresh_from_db()
        assert alvo.fluxo_da_fila == FluxoDaFila.VOLTA
```

(A fixture `titular` já existe no arquivo e cria a empresa "Normadin Ltda".)

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_tela_empresa.py -k FluxoDaFila`
Expected: FAIL com `ImportError: cannot import name 'FluxoDaFila'`

- [ ] **Step 3: The model** (`plataforma/models.py`, perto de `Empresa`)

```python
class FluxoDaFila(models.TextChoices):
    """O que acontece com o vendedor depois que o atendimento é lançado
    (spec 2026-09-17-fluxo-da-fila-por-empresa).

    Mora na EMPRESA porque a rede trabalha do mesmo jeito nas lojas dela: um
    campo por loja seria a mesma resposta repetida, com a chance de duas
    divergirem por esquecimento.
    """

    VOLTA = "volta_para_a_fila", _("Volta para o fim da fila")
    ESPERA = "espera", _("Fica em espera e entra na fila quando quiser")
```

e, dentro de `Empresa`:

```python
    #: O padrão é o fluxo de hoje: toda instalação que já existe continua
    #: idêntica sem ninguém tocar em nada.
    fluxo_da_fila = models.CharField(
        _("fluxo da fila"), max_length=20, choices=FluxoDaFila.choices,
        default=FluxoDaFila.VOLTA,
        help_text=_("O que acontece com o vendedor depois de lançar o "
                    "atendimento."))
```

- [ ] **Step 4: The migration**

Run: `.venv/bin/python manage.py makemigrations plataforma -n fluxo_da_fila`
Expected: `AddField` de `fluxo_da_fila` com o padrão.

- [ ] **Step 5: The field on the screen** (`plataforma/views_empresa.py`)

`GRUPOS` monta `TextInput`; este campo é uma caixa de escolha, então entra à parte, como o `dono` do modal de criar. Em `_campos(...)`, depois dos grupos, acrescente:

```python
    from .models import FluxoDaFila

    # A caixa fica fora de `GRUPOS` porque aquela lista é de campos de texto
    # lidos direto do POST (`_dados_do_post`); esta é escolha fechada, e o
    # valor forjado tem de cair no padrão em vez de virar coluna.
    campos.append(FormGrid(children=[Select(
        name="fluxo_da_fila", label=_("Depois de lançar o atendimento"),
        span=8, value=valores.get("fluxo_da_fila", FluxoDaFila.VOLTA),
        options=[Option(v, r) for v, r in FluxoDaFila.choices],
        help=_("Vale para todas as lojas desta empresa."))]))
```

(Confira o nome real da variável que `_campos` acumula antes de escrever; ela monta uma lista de `Box`/`FormGrid`.)

Em `_valores_de(linha)`, acrescente `"fluxo_da_fila": getattr(linha, "fluxo_da_fila", FluxoDaFila.VOLTA)`.

Em `_dados_do_post(request)`, leia o campo com a lista fechada:

```python
    # Escolha fechada: valor fora das opções vira o padrão, e não erro nem
    # coluna com lixo.
    bruto = request.POST.get("fluxo_da_fila", "")
    dados["fluxo_da_fila"] = (bruto if bruto in FluxoDaFila.values
                              else FluxoDaFila.VOLTA)
```

- [ ] **Step 6: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_tela_empresa.py tests/test_empresa_esquema.py`
Expected: PASS. **Dente:** troque o `if bruto in FluxoDaFila.values` por `bruto or FluxoDaFila.VOLTA` e veja `test_valor_forjado_nao_troca_o_fluxo` vermelho; desfaça.

- [ ] **Step 7: Commit**

```bash
git add plataforma/ tests/test_tela_empresa.py
git commit -m "feat: a empresa escolhe o fluxo da fila"
```

---

### Task 2: O estado "em espera" e as ações do vendedor

**Files:**
- Modify: `fila/models.py` (`Estado`), `fila/acoes.py`, `fila/estado.py`
- Create: `fila/migrations/0005_estado_em_espera.py` (gerada)
- Test: `tests/test_fila_acoes.py`, `tests/test_fila_estado.py`

**Interfaces:**
- Consumes: `FluxoDaFila` (Task 1).
- Produces: `fila.models.Estado.EM_ESPERA = "em_espera"`; `acoes._depois_do_atendimento(lugar, filial, agora)`; `acoes.entrar_na_fila(pessoa, filial)`; `Retrato.em_espera` (lista).

- [ ] **Step 1: Write the failing tests** (fim de `tests/test_fila_acoes.py`)

```python
# --- O fluxo da empresa (spec 2026-09-17-fluxo-da-fila-por-empresa) ---------

def _com_espera(loja):
    from plataforma.models import FluxoDaFila

    loja.empresa.fluxo_da_fila = FluxoDaFila.ESPERA
    loja.empresa.save(update_fields=["fluxo_da_fila"])
    return loja


def test_no_fluxo_de_hoje_lancar_volta_para_o_fim(loja):
    """A regressão da Sylvia: o fluxo padrão não muda em nada."""
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.models import Estado, LugarNaFila

    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
    assert _ordem(loja.matriz) == [loja.bia.pk, loja.ana.pk]


def test_no_fluxo_de_espera_lancar_tira_da_fila(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.models import Estado, LugarNaFila, Pausa

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    lugar = LugarNaFila.irrestritos.get(pessoa=loja.ana)
    assert lugar.estado == Estado.EM_ESPERA
    assert _ordem(loja.matriz) == [loja.bia.pk]
    # Espera não é pausa: nenhuma linha de pausa, e nada a fechar depois.
    assert not Pausa.irrestritos.exists()


def test_entrar_na_fila_poe_no_fim(loja):
    from fila.acoes import bater_ponto, entrar_na_fila, finalizar, vou_atender
    from fila.models import Estado, LugarNaFila

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    entrar_na_fila(loja.ana, loja.matriz)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
    assert _ordem(loja.matriz) == [loja.bia.pk, loja.ana.pk]


@pytest.mark.parametrize("preparar, frase", [
    (lambda loja: None, "Você já está na fila."),
    (lambda loja: __import__("fila.acoes", fromlist=["vou_atender"])
     .vou_atender(loja.ana, loja.matriz), "Finalize o atendimento primeiro."),
])
def test_entrar_na_fila_quando_nao_cabe(loja, preparar, frase):
    from fila.acoes import Recusa, bater_ponto, entrar_na_fila

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    preparar(loja)
    with pytest.raises(Recusa) as recusa:
        entrar_na_fila(loja.ana, loja.matriz)
    assert recusa.value.frase == frase


def test_encerrar_a_pausa_segue_o_fluxo_da_empresa(loja):
    from fila.acoes import bater_ponto, pausar, voltar_para_a_fila
    from fila.models import Estado, LugarNaFila, Pausa

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    voltar_para_a_fila(loja.ana, loja.matriz)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_ESPERA
    # A pausa fecha do mesmo jeito: o que muda é só para onde a pessoa vai.
    assert Pausa.irrestritos.get(pessoa=loja.ana).fim is not None


def test_bater_o_ponto_continua_entrando_na_fila(loja):
    from fila.acoes import bater_ponto
    from fila.models import Estado, LugarNaFila

    _com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
```

E, em `tests/test_fila_estado.py`:

```python
def test_o_retrato_separa_quem_esta_em_espera(relogio):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.estado import retrato
    from plataforma.models import FluxoDaFila
    # monte a loja com o fixture do arquivo, ponha a empresa em ESPERA,
    # leve a Ana até a espera e confira:
    #   r.em_espera tem a Ana, r.fila não, e a Bia continua na fila.
```

(O arquivo já tem o fixture de loja e o `relogio`; siga o molde de
`test_retrato_separa_atendendo_fila_e_pausa_e_marca_quem_ve`.)

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_acoes.py -k "fluxo or espera or entrar_na_fila"`
Expected: FAIL (`AttributeError: EM_ESPERA`, `ImportError: entrar_na_fila`)

- [ ] **Step 3: The state** (`fila/models.py`)

```python
class Estado(models.TextChoices):
    NA_FILA = "na_fila", _("Na fila")
    ATENDENDO = "atendendo", _("Atendendo")
    EM_PAUSA = "em_pausa", _("Em pausa")
    #: Fora da fila por vontade da pessoa, com o ponto aberto: o fluxo em que
    #: quem lança o atendimento só volta à fila quando quiser (spec
    #: 2026-09-17-fluxo-da-fila-por-empresa). **Não é pausa**: não há linha de
    #: `Pausa`, e o tempo aqui não entra em nenhum indicador de pausa.
    EM_ESPERA = "em_espera", _("Em espera")
```

Run: `.venv/bin/python manage.py makemigrations fila -n estado_em_espera`

- [ ] **Step 4: The actions** (`fila/acoes.py`)

```python
def _depois_do_atendimento(lugar, filial, agora) -> None:
    """Para onde a pessoa vai quando o atendimento termina — ou a pausa dela.

    Depende do fluxo da EMPRESA da loja (spec 2026-09-17): no de sempre, o fim
    da fila; no outro, a espera, de onde ela entra quando quiser. Um lugar só
    decide isso, porque quem termina o atendimento, quem encerra a pausa e o
    gerente que fecha no lugar do vendedor precisam da MESMA resposta.
    """
    from plataforma.models import FluxoDaFila

    if filial.empresa.fluxo_da_fila == FluxoDaFila.ESPERA:
        lugar.estado = Estado.EM_ESPERA
        lugar.desde = agora
        lugar.save(update_fields=["estado", "desde"])
        return
    _voltar_ao_fim(lugar, agora)


def entrar_na_fila(pessoa, filial) -> None:
    """Quem está em espera volta à fila, no FIM — a mesma regra de sempre, e
    não uma posição guardada."""
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        if lugar.estado == Estado.NA_FILA:
            raise Recusa(_("Você já está na fila."))
        if lugar.estado == Estado.ATENDENDO:
            raise Recusa(_("Finalize o atendimento primeiro."))
        if lugar.estado == Estado.EM_PAUSA:
            raise Recusa(_("Encerre a pausa primeiro."))
        _voltar_ao_fim(lugar, _agora())
```

Em `finalizar` e em `voltar_para_a_fila`, troque `_voltar_ao_fim(lugar, agora)` por `_depois_do_atendimento(lugar, filial, agora)`.

Acrescente `"entrar_na_fila"` ao `__all__`.

- [ ] **Step 5: The retrato** (`fila/estado.py`)

`Retrato` ganha `em_espera: "list[Linha]"`; o `for` que separa os lugares ganha `Estado.EM_ESPERA: em_espera` no dicionário; `em_espera.sort(key=lambda l: l.desde)`; e o `meu` passa a procurar também nela. Comente que a ordem é por `desde`, como a pausa: não há posição.

- [ ] **Step 6: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_acoes.py tests/test_fila_estado.py tests/test_fila_concorrencia.py`
Expected: PASS. **Dente:** faça `_depois_do_atendimento` sempre chamar `_voltar_ao_fim` e veja os testes do fluxo de espera vermelhos; desfaça.

- [ ] **Step 7: Commit**

---

### Task 3: A tela do vendedor

**Files:**
- Modify: `fila/templates/fila/_painel.html`, `_barra.html`, `_lista.html`, `fila/static/fila/fila.css`, `fila/views.py`
- Test: `tests/test_fila_pagina.py`

**Interfaces:**
- Consumes: `entrar_na_fila` (Task 2).
- Produces: `acao=entrar_na_fila` no `POST /fila/agir`.

- [ ] **Step 1: Write the failing tests**

```python
def test_quem_esta_em_espera_ve_o_cartao_e_o_botao(loja):
    from plataforma.models import FluxoDaFila

    loja.empresa.fluxo_da_fila = FluxoDaFila.ESPERA
    loja.empresa.save(update_fields=["fluxo_da_fila"])
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk))
    html = _html(ana)
    assert "Você está em espera" in html
    assert 'value="entrar_na_fila"' in html
    assert "Em espera" in html          # o bloco da lista
    _agir(ana, acao="entrar_na_fila")
    assert "Você é o 1º da fila" in _html(ana)


def test_no_fluxo_de_hoje_nao_ha_espera_na_tela(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk))
    html = _html(ana)
    assert "Em espera" not in html and 'value="entrar_na_fila"' not in html


def test_entrar_na_fila_de_quem_nao_esta_em_espera_volta_com_a_frase(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="entrar_na_fila")
    assert "Você já está na fila." in _html(ana)
```

- [ ] **Step 2: Run to verify they fail**

- [ ] **Step 3: The view** (`fila/views.py`, em `_DO_VENDEDOR`)

```python
    "entrar_na_fila": lambda r, f, p: acoes.entrar_na_fila(p, f),
```

- [ ] **Step 4: The templates**

`_painel.html`: um `{% elif meu.estado == Estado.EM_ESPERA %}` antes do `{% else %}` da pausa:

```jinja
{% elif meu.estado == Estado.EM_ESPERA %}
<div class="fila-estado painel-espera">
  <span class="fila-estado-icone">{{ icon("hourglass") }}</span>
  <div class="fila-estado-txt">
    <p class="fila-estado-titulo">{{ traduzir("Você está em espera") }}</p>
    <p class="fila-estado-apoio">{{ traduzir("Desde") }} {{ meu.desde|hora }}. {{ traduzir("Entre na fila quando estiver pronto.") }}</p>
  </div>
</div>
```

(Confira o ícone em `nucleo/icons.py`; se `hourglass` não existir, use `clock`.)

`_barra.html`: no bloco de quem participa, um caso novo para `EM_ESPERA`,
com o botão principal e o "Sair da loja" ao lado:

```jinja
{% elif meu.estado == Estado.EM_ESPERA %}
  <div class="fila-secundarias">
    <button type="button" class="btn" data-folha="pausa">{{ icon("coffee", "sm") }}<span>{{ traduzir("Pausa") }}</span></button>
    {{ botao("sair", traduzir("Sair da loja"), "btn ghost", "log-out") }}
  </div>
  {{ botao("entrar_na_fila", traduzir("Entrar na fila"), "btn primary lg fila-principal", "log-in") }}
```

`_lista.html`: um bloco "Em espera" no molde do de pausa, com `r.em_espera`,
a frase vazia ("Ninguém em espera.") e o `corrigir(l)` na linha.

`fila.css`: `.painel-espera` e a marca de estado do bloco, nos tokens do
tema, ao lado das que já existem.

- [ ] **Step 5: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_pagina.py tests/test_variavel_de_cor_existe.py tests/test_esconder_vence_o_display.py`
Expected: PASS. **Dente:** tire o `{% elif %}` do painel e veja o teste do cartão vermelho; desfaça.

- [ ] **Step 6: Commit**

---

### Task 4: O gerente e quem está em espera

**Files:**
- Modify: `fila/correcoes.py`, `fila/views.py`, `fila/templates/fila/_folhas.html`, `comum/auditoria.py`, `fila/models.py` (`AcaoDeCorrecao`)
- Test: `tests/test_fila_correcoes.py`, `tests/test_fila_pagina.py`, `tests/test_auditoria.py`

**Interfaces:**
- Produces: `correcoes.por_na_fila(autor, filial, pessoa_id, *, observacao, request=None)`; `AcaoDeCorrecao.POR_NA_FILA = "por_na_fila"`; `ACOES.FILA_POSTO_NA_FILA = "fila_posto_na_fila"`.

- [ ] **Step 1: Write the failing tests** (`tests/test_fila_correcoes.py`)

```python
def _empresa_com_espera(loja):
    from plataforma.models import FluxoDaFila

    loja.empresa.fluxo_da_fila = FluxoDaFila.ESPERA
    loja.empresa.save(update_fields=["fluxo_da_fila"])


def test_o_gerente_poe_na_fila_quem_esta_em_espera(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.correcoes import por_na_fila
    from fila.models import CorrecaoNaFila, Estado, LugarNaFila

    _empresa_com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    por_na_fila(loja.gerente, loja.matriz, loja.ana.pk, observacao="cliente chegou")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
    correcao = CorrecaoNaFila.irrestritos.get()
    assert (correcao.acao, correcao.observacao) == ("por_na_fila", "cliente chegou")
    assert _ultima_trilha().acao == "fila_posto_na_fila"


def test_por_na_fila_recusa_quem_ja_esta_na_fila(loja):
    from fila.acoes import Recusa, bater_ponto
    from fila.correcoes import por_na_fila

    bater_ponto(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        por_na_fila(loja.gerente, loja.matriz, loja.ana.pk, observacao="teste ok")
    assert recusa.value.frase == "Essa pessoa já está na fila."


def test_o_gerente_fechando_o_atendimento_segue_o_fluxo(loja):
    from fila.acoes import bater_ponto, vou_atender
    from fila.correcoes import fechar_atendimento
    from fila.models import Estado, LugarNaFila

    _empresa_com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    fechar_atendimento(loja.gerente, loja.matriz, loja.ana.pk, _nao_venda(loja),
                       observacao="esqueceu de lançar")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_ESPERA


def test_tirar_da_pausa_manda_para_a_fila_nos_dois_fluxos(loja):
    """A ação é do GERENTE: ele está decidindo que a pessoa atende agora."""
    from fila.acoes import bater_ponto, pausar
    from fila.correcoes import tirar_da_pausa
    from fila.models import Estado, LugarNaFila

    _empresa_com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    tirar_da_pausa(loja.gerente, loja.matriz, loja.ana.pk, observacao="voltou")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA


def test_por_em_pausa_aceita_quem_esta_em_espera(loja):
    from fila.acoes import bater_ponto, finalizar, vou_atender
    from fila.correcoes import por_em_pausa
    from fila.models import Estado, LugarNaFila

    _empresa_com_espera(loja)
    bater_ponto(loja.ana, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    finalizar(loja.ana, loja.matriz, _nao_venda(loja))
    por_em_pausa(loja.gerente, loja.matriz, loja.ana.pk, loja.cad.tipo.pk,
                 observacao="foi ao banco")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_PAUSA
```

Em `tests/test_fila_pagina.py`, o caminho pela tela:

```python
def test_a_folha_corrigir_oferece_por_na_fila_para_quem_espera(loja):
    from plataforma.models import FluxoDaFila
    from fila.models import Estado, LugarNaFila

    loja.empresa.fluxo_da_fila = FluxoDaFila.ESPERA
    loja.empresa.save(update_fields=["fluxo_da_fila"])
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk))
    gil = logado("gil")
    corrigir = _html(gil, f"/fila?folha=corrigir&pessoa={loja.ana.pk}")
    assert "folha=por_na_fila" in corrigir
    folha = _html(gil, f"/fila?folha=por_na_fila&pessoa={loja.ana.pk}")
    aberta = folha[folha.index('id="folha-por_na_fila"'):]
    assert 'name="motivo_da_correcao"' in aberta[:aberta.index("</form>")]
    _agir(gil, acao="por_na_fila", pessoa=str(loja.ana.pk),
          motivo_da_correcao="cliente chegou")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
```

- [ ] **Step 2: Run to verify they fail**

- [ ] **Step 3: Implement**

`fila/models.py`, em `AcaoDeCorrecao`: `POR_NA_FILA = "por_na_fila", _("Pôs na fila")`.

`comum/auditoria.py`: `FILA_POSTO_NA_FILA = "fila_posto_na_fila"` e o rótulo `"Posto na fila pelo gerente"`. `tests/test_auditoria.py`: cenário no molde de `_cenario_fila_pausa_iniciada`, levando o Zeca à espera (empresa com fluxo `espera`) e chamando `por_na_fila`.

`fila/correcoes.py`:

```python
def por_na_fila(autor, filial, pessoa_id, *, observacao, request=None):
    """O gerente põe na fila quem está em espera (spec 2026-09-17). Entra no
    FIM, como quem entra sozinho."""
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado == Estado.NA_FILA:
            raise Recusa(_("Essa pessoa já está na fila."))
        if lugar.estado != Estado.EM_ESPERA:
            raise Recusa(NAO_ESTA_EM_ESPERA)
        agora = _agora()
        _voltar_ao_fim(lugar, agora)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.POR_NA_FILA,
                   observacao, "", agora,
                   auditoria=ACOES.FILA_POSTO_NA_FILA,
                   alvo=_alvo(lugar, filial), request=request)
```

com `NAO_ESTA_EM_ESPERA = gettext_lazy("Essa pessoa não está em espera.")`.

Em `fechar_atendimento`, troque `_voltar_ao_fim(lugar, agora)` por `_depois_do_atendimento(lugar, filial, agora)` (importe-o de `.acoes`). Em `por_em_pausa`, troque a trava `if lugar.estado != Estado.NA_FILA` por `if lugar.estado not in (Estado.NA_FILA, Estado.EM_ESPERA)`, com o comentário de por quê.

`fila/views.py`, em `_DO_GERENTE`:

```python
    "por_na_fila": lambda r, f, p: correcoes.por_na_fila(
        p, f, _pessoa_do_post(r), observacao=_motivo(r), request=r),
```

`_folhas.html`: na folha `corrigir`, um bloco `data-para="em_espera"` com o atalho para `?folha=por_na_fila`, e a folha nova no molde da de `tirar_pausa` (texto: "Entra no fim da fila.").

- [ ] **Step 4: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py tests/test_fila_pagina.py tests/test_auditoria.py`
Expected: PASS. **Dente:** faça `por_na_fila` aceitar qualquer estado e veja o teste da recusa vermelho; desfaça.

- [ ] **Step 5: Commit**

---

### Task 5: Castelhano, documentação, suíte e navegador

- [ ] **Step 1: Find the untranslated phrases** (o mesmo script dos planos anteriores, apontando para `fila/acoes.py`, `fila/correcoes.py`, `fila/templates/fila/*.html`, `plataforma/models.py` e `plataforma/views_empresa.py`)
- [ ] **Step 2: Translate and compile** (`.venv/bin/pybabel compile -d locale -D django`)
- [ ] **Step 3: `CLAUDE.md` §10** — uma seção curta: o fluxo é da empresa, "em espera" é estado e não pausa, o que leva e o que tira da espera, e o gerente tirando da pausa mandando para a fila nos dois fluxos. Atualize a contagem de arquivos de teste se um novo tiver nascido.
- [ ] **Step 4: Full suite** — `timeout 590 .venv/bin/python -m pytest -q -p no:warnings`
- [ ] **Step 5: Browser** — com o servidor local e a segunda empresa em fluxo de espera: lançar um atendimento, ver o cartão "Você está em espera", entrar na fila, e o gerente pondo na fila pela folha Corrigir. Em 390px e 1366px.
- [ ] **Step 6: Commit**
