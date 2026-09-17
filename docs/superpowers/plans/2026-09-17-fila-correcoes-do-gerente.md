# As correções do gerente — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o gerente move o vendedor de posição, põe em pausa e explica toda correção com um motivo obrigatório que fica num histórico consultável em `/fila/historico`.

**Architecture:** uma tabela nova `fila.CorrecaoNaFila` recebe uma linha por correção, gravada junto com a auditoria dentro da trava da loja (`fila/correcoes.py`). Mover grava em `na_fila_desde` um instante entre os vizinhos, sem número de posição guardado. As folhas novas seguem o padrão da página da fila (`?folha=`, funciona sem JavaScript), e a tela de histórico usa `comum.listagem.montar_pagina`.

**Tech Stack:** Django 5.2, Postgres, Jinja2 (templates da fila), pytest (`KRONOS_BANCO` obrigatório).

**Spec:** `docs/superpowers/specs/2026-09-17-fila-correcoes-do-gerente-design.md`

## Global Constraints

- Motivo da correção obrigatório em **toda** correção: 3 a 200 caracteres depois de juntar os espaços. Frases: "Escreva o motivo da correção." e "O motivo cabe em 200 caracteres.".
- Campo do POST: `motivo_da_correcao` (nunca `observacao`, que é o campo da não venda).
- Ações de correção no POST de `/fila/agir`: `tirar`, `fechar`, `tirar_pausa`, `editar` (existentes), `mover`, `por_em_pausa` (novas).
- Assinaturas com o motivo **só por nome** (`*, observacao`), para chamada antiga sem motivo quebrar com `TypeError` e não passar calada.
- Toda consulta de tela por `objects.da_empresa`; ações sob `acoes._travar(filial)`, relendo depois da trava.
- Hora sempre por `correcoes._agora()` (que lê `acoes._agora()`).
- Frases da moldura em português no código e em castelhano em `locale/es/LC_MESSAGES/django.po` (compilar com `.venv/bin/pybabel compile -d locale -D django`). O motivo digitado não se traduz.
- Comentário diz POR QUÊ, em português. Commits longos em português, autor `João Victor Vancim <developer1@kronos.net.br>`, **sem** coautor.
- Rodar testes: `export KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5436/kronos DJANGO_DEBUG=1` e `.venv/bin/python -m pytest -q -p no:warnings <arquivos>`.
- Teste com dente: depois de verde, quebre o código de propósito, veja vermelho, desfaça.

---

### Task 1: A tabela `CorrecaoNaFila` e a versão da fila

**Files:**
- Modify: `fila/models.py` (depois de `MetaDeVenda`)
- Create: `fila/migrations/0004_correcoes_na_fila.py` (gerada)
- Modify: `fila/estado.py` (`versao_da_fila`)
- Test: `tests/test_fila_correcoes.py`

**Interfaces:**
- Produces: `fila.models.AcaoDeCorrecao` (TextChoices: `MOVER="mover"`, `PAUSAR="pausar"`, `TIRAR_PAUSA="tirar_pausa"`, `FECHAR="fechar"`, `TIRAR="tirar"`, `EDITAR="editar"`); `fila.models.CorrecaoNaFila(empresa, filial, pessoa, autor, acao, observacao, detalhe, momento)`.

- [ ] **Step 1: Write the failing test** (fim de `tests/test_fila_correcoes.py`)

```python
# --- O histórico das correções (spec 2026-09-17) -----------------------------

def test_a_versao_da_fila_muda_com_uma_correcao(loja):
    """Mover grava um instante ENTRE os vizinhos: sem contar as correções, a
    versão não mudaria e as outras telas não veriam a ordem nova."""
    from django.utils import timezone

    from fila.estado import versao_da_fila
    from fila.models import CorrecaoNaFila

    antes = versao_da_fila(loja.matriz)
    CorrecaoNaFila.irrestritos.create(
        empresa=loja.empresa, filial=loja.matriz, pessoa=loja.ana,
        autor=loja.gerente, acao="mover", observacao="chegou antes",
        detalhe="de 2º para 1º", momento=timezone.now())
    assert versao_da_fila(loja.matriz) != antes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py -k versao_da_fila_muda`
Expected: FAIL com `ImportError: cannot import name 'CorrecaoNaFila'`

- [ ] **Step 3: Write the model** (em `fila/models.py`, depois de `MetaDeVenda`)

```python
class AcaoDeCorrecao(models.TextChoices):
    MOVER = "mover", _("Mudou de posição")
    PAUSAR = "pausar", _("Pôs em pausa")
    TIRAR_PAUSA = "tirar_pausa", _("Tirou da pausa")
    FECHAR = "fechar", _("Fechou o atendimento")
    TIRAR = "tirar", _("Tirou da loja")
    EDITAR = "editar", _("Corrigiu o lançamento")


class CorrecaoNaFila(ModeloDaEmpresa):
    """Uma correção do gerente, com o motivo (spec 2026-09-17, C2).

    Tabela própria, e não só a auditoria: o histórico é lido por loja,
    vendedor e período, e a auditoria não tem essas colunas; filtrar por elas
    viraria busca em texto. A auditoria continua recebendo a mesma correção.
    """

    filial = _loja()
    pessoa = _pessoa(_("vendedor"))
    #: Quem corrigiu como a ação o recebe: em "ver como", a pessoa vista. Quem
    #: agiu de verdade está na auditoria, que anota a personificação.
    autor = _pessoa(_("quem corrigiu"))
    acao = models.CharField(_("ação"), max_length=12, choices=AcaoDeCorrecao.choices)
    observacao = models.CharField(_("motivo"), max_length=200)
    #: O que mudou, escrito pelo sistema ("de 5º para 1º", "Almoço").
    detalhe = models.CharField(_("detalhe"), max_length=300, blank=True)
    momento = models.DateTimeField(_("quando"))

    class Meta(ModeloDaEmpresa.Meta):
        verbose_name = _("correção na fila")
        verbose_name_plural = _("correções na fila")
        # A tela de histórico filtra por loja e período.
        indexes = [models.Index(fields=["filial", "momento"],
                                name="fila_correcao_periodo")]
```

- [ ] **Step 4: Generate the migration**

Run: `.venv/bin/python manage.py makemigrations fila -n correcoes_na_fila`
Expected: `fila/migrations/0004_correcoes_na_fila.py` com `CreateModel` de `CorrecaoNaFila`. Abra o arquivo e confira que `conta` vem com `db_column='conta_guid'`.

- [ ] **Step 5: Count the corrections in the version** (`fila/estado.py`, dentro de `versao_da_fila`, antes do `return`)

```python
    # Mover grava um instante ENTRE os vizinhos, que não muda o maior
    # `na_fila_desde` nem o maior `desde`: sem contar as correções, as outras
    # telas não veriam a ordem nova (spec 2026-09-17).
    from .models import CorrecaoNaFila

    correcoes = (CorrecaoNaFila.objects.da_empresa(filial.empresa)
                 .filter(filial=filial)
                 .aggregate(n=Count("pk"), quando=Max("momento")))
```

e troque o `return` por:

```python
    return (f"{dados['linhas']}.{marca(dados['desde'])}.{marca(dados['fila'])}"
            f".{hoje['n']}.{hoje['total'] or 0}.{hoje['motivos'] or 0}"
            f".{metas['n']}.{marca(metas['quando'])}"
            f".{correcoes['n']}.{marca(correcoes['quando'])}")
```

- [ ] **Step 6: Run the test and the table sweeps**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py tests/test_regra_do_inquilino.py tests/test_toda_linha_da_conta_leva_o_guid.py tests/test_regra_guid.py tests/test_fila_estado.py`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add fila/models.py fila/migrations/0004_correcoes_na_fila.py fila/estado.py tests/test_fila_correcoes.py
git commit -m "feat: a tabela do histórico das correções da fila

(mensagem longa em português: o que faltava — o motivo da correção não
ficava em lugar nenhum consultável por loja e vendedor —, por que tabela
própria além da auditoria, e por que a versão da fila passa a contar as
correções)"
```

---

### Task 2: O motivo obrigatório nas quatro correções que já existem

**Files:**
- Modify: `fila/correcoes.py`
- Modify: `fila/views.py` (`_DO_GERENTE`)
- Modify: `fila/templates/fila/_folhas.html` (macro do motivo, folhas `fechar`, `tirar`, `editar`, e as novas `tirar_pausa` e `sair`)
- Modify: `fila/static/fila/fila.css` (o campo)
- Test: `tests/test_fila_correcoes.py`, `tests/test_fila_pagina.py`, `tests/test_auditoria.py`

**Interfaces:**
- Consumes: `CorrecaoNaFila`, `AcaoDeCorrecao` (Task 1).
- Produces:
  - `correcoes.ler_observacao(texto: str) -> str` (levanta `Recusa`);
  - `correcoes._registrar(autor, filial, pessoa_id: int, acao: str, observacao: str, detalhe: str, agora, *, auditoria: str, alvo: str, request=None) -> None`;
  - `tirar_da_loja(autor, filial, pessoa_id, lancamento=None, *, observacao, request=None)`;
  - `fechar_atendimento(autor, filial, pessoa_id, lancamento, *, observacao, request=None)`;
  - `tirar_da_pausa(autor, filial, pessoa_id, *, observacao, request=None)`;
  - `editar_lancamento(autor, filial, atendimento_id, lancamento, *, observacao, request=None)`;
  - `views._motivo(request) -> str` (lê `motivo_da_correcao`);
  - macro Jinja `motivo_da_correcao()` em `_folhas.html`.

- [ ] **Step 1: Write the failing tests** (fim de `tests/test_fila_correcoes.py`)

```python
MOTIVO = "esqueceu de sair"


@pytest.mark.parametrize("texto, frase", [
    ("", "Escreva o motivo da correção."),
    ("  a  ", "Escreva o motivo da correção."),
    ("x" * 201, "O motivo cabe em 200 caracteres."),
])
def test_sem_motivo_nenhuma_correcao_acontece(loja, texto, frase):
    from fila.acoes import Recusa, bater_ponto
    from fila.correcoes import tirar_da_loja
    from fila.models import CorrecaoNaFila, LugarNaFila

    bater_ponto(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, observacao=texto)
    assert recusa.value.frase == frase
    assert LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    assert not CorrecaoNaFila.irrestritos.exists()


def test_o_motivo_junta_os_espacos():
    from fila.correcoes import ler_observacao

    assert ler_observacao("  foi   ao\nbanco ") == "foi ao banco"


def test_cada_correcao_grava_o_historico_e_a_auditoria(loja):
    from fila.acoes import bater_ponto, finalizar, pausar, vou_atender
    from fila.correcoes import (editar_lancamento, fechar_atendimento,
                                tirar_da_loja, tirar_da_pausa)
    from fila.models import Atendimento, CorrecaoNaFila

    bater_ponto(loja.ana, loja.matriz)
    pausar(loja.ana, loja.matriz, loja.cad.tipo.pk)
    tirar_da_pausa(loja.gerente, loja.matriz, loja.ana.pk, observacao="voltou do almoço")
    vou_atender(loja.ana, loja.matriz)
    fechar_atendimento(loja.gerente, loja.matriz, loja.ana.pk,
                       _venda(loja, (loja.cad.grupo, "250")), observacao="esqueceu de lançar")
    editar_lancamento(loja.gerente, loja.matriz, Atendimento.irrestritos.get().pk,
                      _venda(loja, (loja.cad.grupo, "300")), observacao="valor errado")
    tirar_da_loja(loja.gerente, loja.matriz, loja.ana.pk, observacao="foi embora")
    linhas = list(CorrecaoNaFila.irrestritos.order_by("momento")
                  .values_list("acao", "observacao", "detalhe", "pessoa_id", "autor_id"))
    assert [l[:2] for l in linhas] == [
        ("tirar_pausa", "voltou do almoço"), ("fechar", "esqueceu de lançar"),
        ("editar", "valor errado"), ("tirar", "foi embora")]
    assert linhas[0][2] == "Almoço"
    assert all(l[3] == loja.ana.pk and l[4] == loja.gerente.pk for l in linhas)
    assert _ultima_trilha().detalhe == "motivo: foi embora"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py -k "motivo or historico_e_a_auditoria"`
Expected: FAIL (`TypeError: ... unexpected keyword argument 'observacao'` e `ImportError: ler_observacao`)

- [ ] **Step 3: Implement in `fila/correcoes.py`**

Imports: acrescente `from .models import AcaoDeCorrecao, Atendimento, CorrecaoNaFila, Estado, Pausa, Resultado` e `"ler_observacao"` em `__all__`. Depois de `NAO_ENCONTRADO`:

```python
MOTIVO_CURTO = gettext_lazy("Escreva o motivo da correção.")
MOTIVO_LONGO = gettext_lazy("O motivo cabe em 200 caracteres.")


def ler_observacao(texto) -> str:
    """O motivo da correção, obrigatório (spec 2026-09-17, C1). Três
    caracteres barram o "." digitado só para passar; duzentos cabem numa
    linha do histórico. Lido ANTES da trava: recusa barata não segura a fila
    da loja."""
    limpo = " ".join(str(texto or "").split())
    if len(limpo) < 3:
        raise Recusa(MOTIVO_CURTO)
    if len(limpo) > 200:
        raise Recusa(MOTIVO_LONGO)
    return limpo


def _registrar(autor, filial, pessoa_id, acao, observacao, detalhe, agora, *,
               auditoria, alvo, request=None) -> None:
    """O histórico e a auditoria juntos, na transação da correção: se um
    falhar, a correção desfaz inteira."""
    CorrecaoNaFila.irrestritos.create(
        empresa=filial.empresa, filial=filial, pessoa_id=pessoa_id, autor=autor,
        acao=acao, observacao=observacao, detalhe=detalhe[:300], momento=agora)
    trilha = f"{detalhe} | motivo: {observacao}" if detalhe else f"motivo: {observacao}"
    registrar(auditoria, autor, alvo=alvo, detalhe=trilha, request=request)
```

Troque as quatro correções (mesma lógica de hoje; mudam a assinatura, a primeira linha e o registro):

```python
def tirar_da_loja(autor, filial, pessoa_id, lancamento=None, *, observacao,
                  request=None):
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        agora = _agora()
        detalhe = ""
        if lugar.estado == Estado.ATENDENDO:
            # (comentário de hoje, mantido)
            if lancamento is None or lancamento.resultado != Resultado.NAO_VENDEU:
                raise Recusa(_("Ela está atendendo. Escolha o motivo da não "
                               "venda para fechar o atendimento."))
            atendimento = Atendimento.irrestritos.get(
                vendedor_id=pessoa_id, fim__isnull=True)
            _fechar_atendimento(atendimento, lancamento, agora,
                                fechado_por=autor)
            detalhe = f"atendimento fechado: {descrever(atendimento)}"
        alvo = _alvo(lugar, filial)
        _sair(lugar, agora, fechada_por=autor)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.TIRAR, observacao,
                   detalhe, agora, auditoria=ACOES.FILA_PESSOA_TIRADA, alvo=alvo,
                   request=request)


def fechar_atendimento(autor, filial, pessoa_id, lancamento, *, observacao,
                       request=None):
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.ATENDENDO:
            raise Recusa(_("Essa pessoa não está atendendo."))
        atendimento = Atendimento.irrestritos.get(vendedor_id=pessoa_id,
                                                  fim__isnull=True)
        agora = _agora()
        _fechar_atendimento(atendimento, lancamento, agora, fechado_por=autor)
        _voltar_ao_fim(lugar, agora)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.FECHAR, observacao,
                   descrever(atendimento), agora,
                   auditoria=ACOES.FILA_ATENDIMENTO_FECHADO,
                   alvo=_alvo(lugar, filial), request=request)


def tirar_da_pausa(autor, filial, pessoa_id, *, observacao, request=None):
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.EM_PAUSA:
            raise Recusa(_("Essa pessoa não está em pausa."))
        pausa = Pausa.irrestritos.select_related("tipo").get(
            pessoa_id=pessoa_id, fim__isnull=True)
        agora = _agora()
        pausa.fim = agora
        pausa.save(update_fields=["fim"])
        _voltar_ao_fim(lugar, agora)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.TIRAR_PAUSA, observacao,
                   pausa.tipo.nome, agora, auditoria=ACOES.FILA_PAUSA_ENCERRADA,
                   alvo=_alvo(lugar, filial), request=request)
```

Em `editar_lancamento`: assinatura `(autor, filial, atendimento_id, lancamento, *, observacao, request=None)`, primeira linha `observacao = ler_observacao(observacao)`, e troque o `registrar(...)` final por:

```python
        _registrar(autor, filial, atendimento.vendedor_id, AcaoDeCorrecao.EDITAR,
                   observacao, f"antes: {antes}; depois: {depois}", _agora(),
                   auditoria=ACOES.FILA_LANCAMENTO_CORRIGIDO,
                   alvo=f"Atendimento de {nome_de(atendimento.vendedor)} em {filial}",
                   request=request)
```

- [ ] **Step 4: Update the old callers in tests**

Em `tests/test_fila_correcoes.py`, acrescente `observacao=MOTIVO` a toda chamada de `tirar_da_loja`, `fechar_atendimento`, `tirar_da_pausa` e `editar_lancamento` (mova a constante `MOTIVO` para logo depois dos imports), e troque:

```python
    assert _ultima_trilha().detalhe == "Almoço"
```
por
```python
    assert _ultima_trilha().detalhe == f"Almoço | motivo: {MOTIVO}"
```

Em `tests/test_auditoria.py`, nos cenários `_cenario_fila_pessoa_tirada`, `_cenario_fila_atendimento_fechado`, `_cenario_fila_pausa_encerrada` e `_cenario_fila_lancamento_corrigido`, acrescente `observacao="motivo do teste"` à chamada da correção.

- [ ] **Step 5: Run the rules tests**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py tests/test_auditoria.py`
Expected: PASS

- [ ] **Step 6: Write the failing page tests** (fim de `tests/test_fila_pagina.py`)

```python
# --- O motivo da correção (spec 2026-09-17) ---------------------------------

def test_correcao_pela_pagina_sem_motivo_volta_com_a_frase(loja):
    from fila.models import LugarNaFila

    _agir(logado("ana"), acao="ponto")
    gil = logado("gil")
    _agir(gil, acao="tirar", pessoa=str(loja.ana.pk))
    assert LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    assert "Escreva o motivo da correção." in _html(gil)
    _agir(gil, acao="tirar", pessoa=str(loja.ana.pk), motivo_da_correcao="foi embora")
    assert not LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()


def test_as_folhas_de_correcao_pedem_o_motivo(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    gil = logado("gil")
    for folha in ("sair", "tirar_pausa", "fechar", "tirar"):
        html = _html(gil, f"/fila?folha={folha}&pessoa={loja.ana.pk}")
        aberta = html[html.index(f'id="folha-{folha}"'):]
        aberta = aberta[:aberta.index("</form>")]
        assert 'name="motivo_da_correcao"' in aberta and "required" in aberta, folha
```

Nos testes que já existem em `tests/test_fila_pagina.py` e corrigem pela página (`test_gerente_corrige_na_loja_dele`, `test_gerente_de_outra_loja_nao_corrige_a_matriz`, `test_supervisor_corrige_na_empresa`, `test_gerente_edita_lancamento_de_hoje_pela_pagina`, e qualquer outro `_agir(..., acao="tirar"|"fechar"|"tirar_pausa"|"editar")`), acrescente `motivo_da_correcao="motivo do teste"`.

- [ ] **Step 7: Run to verify the new page tests fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_pagina.py -k "motivo"`
Expected: FAIL

- [ ] **Step 8: Read the reason in the view** (`fila/views.py`)

```python
def _motivo(request) -> str:
    """O motivo da correção. `motivo_da_correcao`, e não `observacao`: a folha
    de fechar já tem a observação da não venda, e os dois iriam no POST."""
    return request.POST.get("motivo_da_correcao", "")


_DO_GERENTE = {
    "tirar": lambda r, f, p: correcoes.tirar_da_loja(
        p, f, _pessoa_do_post(r),
        _lancamento(r) if r.POST.get("resultado") else None,
        observacao=_motivo(r), request=r),
    "fechar": lambda r, f, p: correcoes.fechar_atendimento(
        p, f, _pessoa_do_post(r), _lancamento(r), observacao=_motivo(r), request=r),
    "tirar_pausa": lambda r, f, p: correcoes.tirar_da_pausa(
        p, f, _pessoa_do_post(r), observacao=_motivo(r), request=r),
    "editar": lambda r, f, p: correcoes.editar_lancamento(
        p, f, id_do_post(r, "atendimento"), _lancamento(r),
        observacao=_motivo(r), request=r),
}
```

- [ ] **Step 9: The field in the sheets** (`fila/templates/fila/_folhas.html`)

Depois do macro `motivos_de`:

```jinja
{# O motivo da correção, obrigatório (spec 2026-09-17). `required` é
   conveniência: quem decide é `correcoes.ler_observacao`. #}
{% macro motivo_da_correcao() %}
<label class="f fila-motivo-correcao"><span class="fila-rotulo">{{ traduzir("Motivo da correção") }}</span>
<textarea class="ctl" name="motivo_da_correcao" required minlength="3" maxlength="200" rows="2" placeholder="{{ traduzir('Ex.: foi ao banco e esqueceu de pausar') }}"></textarea></label>
{% endmacro %}
```

No macro `fechamento`, antes do `</div>` que fecha o `mbody`:

```jinja
    {% if acao != "finalizar" %}{{ motivo_da_correcao() }}{% endif %}
```

Na folha `tirar` (a de quem está atendendo), depois de `{{ motivos_de() }}`: `{{ motivo_da_correcao() }}`. Na folha `editar`, antes do `</div>` do `mbody`: `{{ motivo_da_correcao() }}`.

Na folha `corrigir`, troque os dois formulários de POST direto (o de `tirar_pausa` dentro de `data-para="em_pausa"` e o de `tirar` dentro de `data-para="na_fila em_pausa"`) por atalhos para folhas, no mesmo formato dos que já existem:

```jinja
  <div data-para="em_pausa"{% if alvo and alvo.estado != "em_pausa" %} hidden{% endif %}>
    <a class="fila-corrigir-item" href="{{ url_fila }}?folha=tirar_pausa&pessoa={{ alvo.pessoa_id if alvo else '' }}" data-folha="tirar_pausa" data-pessoa="{{ alvo.pessoa_id if alvo else '' }}" data-nome="{{ alvo.nome if alvo else '' }}">
      <span class="ci">{{ icon("arrow-left") }}</span><span><strong>{{ traduzir("Tirar da pausa") }}</strong><small>{{ traduzir("Encerra a pausa e põe no fim da fila.") }}</small></span></a>
  </div>
  <div data-para="na_fila em_pausa"{% if alvo and alvo.estado == "atendendo" %} hidden{% endif %}>
    <a class="fila-corrigir-item fila-corrigir-perigo" href="{{ url_fila }}?folha=sair&pessoa={{ alvo.pessoa_id if alvo else '' }}" data-folha="sair" data-pessoa="{{ alvo.pessoa_id if alvo else '' }}" data-nome="{{ alvo.nome if alvo else '' }}">
      <span class="ci">{{ icon("log-out") }}</span><span><strong>{{ traduzir("Tirar da loja") }}</strong><small>{{ traduzir("Para quem esqueceu de sair. Encerra o ponto.") }}</small></span></a>
  </div>
```

E as duas folhas novas, depois da folha `tirar`:

```jinja
{% call modal("tirar_pausa", traduzir("Tirar da pausa"), folha == "tirar_pausa" and alvo, alvo.nome if alvo else "") %}
<form method="post" action="{{ url_agir }}" data-acao>
  <div class="mbody">
    {{ csrf }}<input type="hidden" name="acao" value="tirar_pausa">
    <input type="hidden" name="pessoa" value="{{ alvo.pessoa_id if alvo else '' }}">
    <p class="muted">{{ traduzir("Encerra a pausa e põe no fim da fila.") }}</p>
    {{ motivo_da_correcao() }}
  </div>
  <div class="mfoot">
    <button type="button" class="btn" data-modal-close>{{ traduzir("Cancelar") }}</button>
    <button type="submit" class="btn primary">{{ traduzir("Tirar da pausa") }}</button>
  </div>
</form>
{% endcall %}

{% call modal("sair", traduzir("Tirar da loja"), folha == "sair" and alvo, alvo.nome if alvo else "") %}
<form method="post" action="{{ url_agir }}" data-acao>
  <div class="mbody">
    {{ csrf }}<input type="hidden" name="acao" value="tirar">
    <input type="hidden" name="pessoa" value="{{ alvo.pessoa_id if alvo else '' }}">
    <p class="muted">{{ traduzir("Para quem esqueceu de sair. Encerra o ponto.") }}</p>
    {{ motivo_da_correcao() }}
  </div>
  <div class="mfoot">
    <button type="button" class="btn" data-modal-close>{{ traduzir("Cancelar") }}</button>
    <button type="submit" class="btn primary">{{ traduzir("Tirar da loja") }}</button>
  </div>
</form>
{% endcall %}
```

Em `fila/static/fila/fila.css`, perto das regras de `.fila-corrigir-item`:

```css
/* O motivo da correção fecha a folha, logo antes dos botões. */
.fila-motivo-correcao { display: grid; gap: 6px; margin-top: 14px; }
.fila-motivo-correcao textarea { resize: vertical; }
```

- [ ] **Step 10: Run page + rules + sweeps**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_pagina.py tests/test_fila_correcoes.py tests/test_auditoria.py tests/test_id_do_post.py tests/test_variavel_de_cor_existe.py`
Expected: PASS. Quebre `ler_observacao` (retorne o texto sem conferir) e veja os testes de motivo ficarem vermelhos; desfaça.

- [ ] **Step 11: Commit**

```bash
git add fila/correcoes.py fila/views.py fila/templates/fila/_folhas.html fila/static/fila/fila.css tests/test_fila_correcoes.py tests/test_fila_pagina.py tests/test_auditoria.py
git commit -m "feat: toda correção do gerente pede o motivo e grava o histórico"
```
(mensagem longa: antes a correção não dizia por quê; o motivo é obrigatório e só por nome; tirar da pausa e tirar da loja passaram a abrir folha porque precisam do campo.)

---

### Task 3: Mover de posição

**Files:**
- Modify: `fila/correcoes.py` (`mover`, `_instante_entre`, `_espacar`)
- Modify: `comum/auditoria.py` (`FILA_POSICAO_MOVIDA` + rótulo)
- Modify: `tests/test_auditoria.py` (cenário)
- Modify: `fila/views.py` (`"mover"` em `_DO_GERENTE`)
- Modify: `fila/templates/fila/_folhas.html` (atalho em Corrigir, folha `mover`)
- Modify: `fila/static/fila/fila.js` (desabilitar a posição atual ao abrir)
- Test: `tests/test_fila_correcoes.py`, `tests/test_fila_pagina.py`

**Interfaces:**
- Consumes: `ler_observacao`, `_registrar`, `AcaoDeCorrecao.MOVER` (Tasks 1–2); `fila.estado.na_fila(filial)`.
- Produces: `correcoes.mover(autor, filial, pessoa_id, posicao: int | None, *, observacao, request=None) -> None`; `NAO_ESTA_NA_FILA` (gettext_lazy "Essa pessoa não está na fila."); `ACOES.FILA_POSICAO_MOVIDA = "fila_posicao_movida"`.

- [ ] **Step 1: Write the failing rules tests**

```python
def _ordem(loja):
    from fila.estado import na_fila

    return [l.pessoa_id for l in na_fila(loja.matriz)]


@pytest.fixture
def fila_de_quatro(loja):
    from fila.acoes import bater_ponto

    loja.caio = pessoa_na_loja("caio", loja.empresa, loja.matriz)
    loja.dora = pessoa_na_loja("dora", loja.empresa, loja.matriz)
    for p in (loja.ana, loja.bia, loja.caio, loja.dora):
        bater_ponto(p, loja.matriz)
    return loja


@pytest.mark.parametrize("quem, posicao, esperada", [
    ("dora", 1, ["dora", "ana", "bia", "caio"]),
    ("ana", 4, ["bia", "caio", "dora", "ana"]),
    ("dora", 2, ["ana", "dora", "bia", "caio"]),
    ("ana", 3, ["bia", "caio", "ana", "dora"]),
])
def test_mover_para_a_posicao_escolhida(fila_de_quatro, quem, posicao, esperada):
    from fila.correcoes import mover
    from fila.models import CorrecaoNaFila

    loja = fila_de_quatro
    pessoa = getattr(loja, quem)
    antes = _ordem(loja).index(pessoa.pk) + 1
    mover(loja.gerente, loja.matriz, pessoa.pk, posicao, observacao="chegou antes")
    assert _ordem(loja) == [getattr(loja, n).pk for n in esperada]
    correcao = CorrecaoNaFila.irrestritos.get()
    assert (correcao.acao, correcao.detalhe) == ("mover", f"de {antes}º para {posicao}º")
    assert _ultima_trilha().acao == "fila_posicao_movida"


def test_mover_com_vizinhos_no_mesmo_instante_reespaca_a_fila(fila_de_quatro):
    from fila.correcoes import mover
    from fila.models import LugarNaFila

    loja = fila_de_quatro
    instante = LugarNaFila.irrestritos.order_by("na_fila_desde").first().na_fila_desde
    LugarNaFila.irrestritos.update(na_fila_desde=instante)   # empate: o pk desempata
    ordem = _ordem(loja)
    mover(loja.gerente, loja.matriz, ordem[3], 2, observacao="chegou antes")
    assert _ordem(loja) == [ordem[0], ordem[3], ordem[1], ordem[2]]


@pytest.mark.parametrize("posicao, frase", [
    (None, "Escolha uma posição da fila."),
    (0, "Escolha uma posição da fila."),
    (5, "Escolha uma posição da fila."),
    (1, "Essa pessoa já está nessa posição."),
])
def test_mover_para_posicao_que_nao_serve(fila_de_quatro, posicao, frase):
    from fila.acoes import Recusa
    from fila.correcoes import mover

    loja = fila_de_quatro
    with pytest.raises(Recusa) as recusa:
        mover(loja.gerente, loja.matriz, loja.ana.pk, posicao, observacao="teste ok")
    assert recusa.value.frase == frase


def test_so_quem_esta_na_fila_se_move(fila_de_quatro):
    from fila.acoes import Recusa, vou_atender
    from fila.correcoes import mover

    loja = fila_de_quatro
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        mover(loja.gerente, loja.matriz, loja.ana.pk, 2, observacao="teste ok")
    assert recusa.value.frase == "Essa pessoa não está na fila."
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py -k "mover or move"`
Expected: FAIL (`ImportError: cannot import name 'mover'`)

- [ ] **Step 3: Implement** (`fila/correcoes.py`; `from .estado import na_fila, nome_de`; `"mover"` em `__all__`)

```python
NAO_ESTA_NA_FILA = gettext_lazy("Essa pessoa não está na fila.")
_MICRO = timedelta(microseconds=1)


def _instante_entre(outros, posicao):
    """O `na_fila_desde` que põe alguém na `posicao` (1…N) de uma fila que,
    sem ele, é `outros`. `None` quando não cabe um instante entre os vizinhos.

    Não há número de posição guardado (entrega 1): um número precisaria ser
    renumerado a cada saída, e renumerar sob concorrência é onde as filas se
    perdem. Estritamente entre os vizinhos, e não igual a um deles: no empate
    quem decide é o `pk`, e aí a pessoa podia cair do lado errado.
    """
    if posicao == 1:
        return outros[0].na_fila_desde - _MICRO
    if posicao == len(outros) + 1:
        return outros[-1].na_fila_desde + _MICRO
    antes, depois = outros[posicao - 2].na_fila_desde, outros[posicao - 1].na_fila_desde
    if depois - antes < 2 * _MICRO:
        return None
    return antes + (depois - antes) / 2


def _espacar(outros) -> None:
    """Dois microssegundos entre cada um, na ordem de agora, a partir do
    primeiro: abre lugar para encaixar quando os vizinhos estão colados.
    Só roda sob a trava da loja."""
    base = outros[0].na_fila_desde
    for i, lugar in enumerate(outros):
        lugar.na_fila_desde = base + 2 * i * _MICRO
        lugar.save(update_fields=["na_fila_desde"])


def mover(autor, filial, pessoa_id, posicao, *, observacao, request=None):
    """Põe quem está na fila na `posicao` escolhida pelo gerente (C3)."""
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.NA_FILA:
            raise Recusa(NAO_ESTA_NA_FILA)
        fila = list(na_fila(filial))
        if posicao is None or not 1 <= posicao <= len(fila):
            raise Recusa(_("Escolha uma posição da fila."))
        atual = next(i for i, l in enumerate(fila, 1) if l.pk == lugar.pk)
        if posicao == atual:
            raise Recusa(_("Essa pessoa já está nessa posição."))
        outros = [l for l in fila if l.pk != lugar.pk]
        instante = _instante_entre(outros, posicao)
        if instante is None:
            _espacar(outros)
            instante = _instante_entre(outros, posicao)
        lugar.na_fila_desde = instante
        lugar.save(update_fields=["na_fila_desde"])
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.MOVER, observacao,
                   f"de {atual}º para {posicao}º", _agora(),
                   auditoria=ACOES.FILA_POSICAO_MOVIDA, alvo=_alvo(lugar, filial),
                   request=request)
```

`comum/auditoria.py`: em `ACOES`, depois de `FILA_LANCAMENTO_CORRIGIDO`, `FILA_POSICAO_MOVIDA = "fila_posicao_movida"`; em `ROTULOS`, `ACOES.FILA_POSICAO_MOVIDA: "Posição na fila mudada pelo gerente",`.

`tests/test_auditoria.py`: cenário e entrada no dicionário. `_loja_com_gente_da_fila()` põe só o Zeca na fila; o cenário acrescenta a Yara, no mesmo molde, para o Zeca ter para onde ir:

```python
def _cenario_fila_posicao_movida():
    from contas.models import Usuario
    from fila.acoes import bater_ponto
    from fila.correcoes import mover

    dona, zeca, matriz, _cad = _loja_com_gente_da_fila()
    yara = Usuario.objects.create_user(email=email_de("yara"), password=SENHA,
                                       nome="Yara")
    alocar(yara, empresa_do_teste(), "vendedor", filial=matriz)
    bater_ponto(yara, matriz)
    mover(dona, matriz, yara.pk, 1, observacao="chegou antes")
    return email_de("dona-fila"), f"Yara em {matriz}"
```

e, no dicionário de cenários, `"FILA_POSICAO_MOVIDA": _cenario_fila_posicao_movida,`.

- [ ] **Step 4: Run rules + auditoria**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py tests/test_auditoria.py`
Expected: PASS

- [ ] **Step 5: Write the failing page test** (`tests/test_fila_pagina.py`)

```python
def test_gerente_move_pela_folha_sem_javascript(loja):
    from fila.estado import na_fila

    ana, bia = logado("ana"), logado("bia")
    _agir(ana, acao="ponto")
    _agir(bia, acao="ponto")
    gil = logado("gil")
    corrigir = _html(gil, f"/fila?folha=corrigir&pessoa={loja.bia.pk}")
    assert "?folha=mover&amp;pessoa=" in corrigir or "?folha=mover&pessoa=" in corrigir
    folha = _html(gil, f"/fila?folha=mover&pessoa={loja.bia.pk}")
    aberta = folha[folha.index('id="folha-mover"'):]
    aberta = aberta[:aberta.index("</form>")]
    assert 'name="posicao" value="1"' in aberta and 'name="motivo_da_correcao"' in aberta
    _agir(gil, acao="mover", pessoa=str(loja.bia.pk), posicao="1",
          motivo_da_correcao="chegou antes")
    assert [l.pessoa_id for l in na_fila(loja.matriz)] == [loja.bia.pk, loja.ana.pk]


def test_posicao_forjada_no_post_nao_derruba(loja):
    _agir(logado("ana"), acao="ponto")
    gil = logado("gil")
    resposta = _agir(gil, acao="mover", pessoa=str(loja.ana.pk), posicao="²",
                     motivo_da_correcao="teste ok")
    assert resposta.status_code == 302
    assert "Escolha uma posição da fila." in _html(gil)
```

- [ ] **Step 6: Run to verify it fails**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_pagina.py -k "move or posicao_forjada"`
Expected: FAIL

- [ ] **Step 7: View, sheet and script**

`fila/views.py`, em `_DO_GERENTE`:

```python
    "mover": lambda r, f, p: correcoes.mover(
        p, f, _pessoa_do_post(r), id_do_post(r, "posicao"),
        observacao=_motivo(r), request=r),
```

(`id_do_post` já transforma "²", vazio e número gigante em `None`, que `mover` recusa com frase.)

`fila/templates/fila/_folhas.html`, na folha `corrigir`, um bloco novo antes do `data-para="em_pausa"`:

```jinja
  <div data-para="na_fila"{% if alvo and alvo.estado != "na_fila" %} hidden{% endif %}>
    <a class="fila-corrigir-item" href="{{ url_fila }}?folha=mover&pessoa={{ alvo.pessoa_id if alvo else '' }}" data-folha="mover" data-pessoa="{{ alvo.pessoa_id if alvo else '' }}" data-nome="{{ alvo.nome if alvo else '' }}">
      <span class="ci">{{ icon("arrow-up-down") }}</span><span><strong>{{ traduzir("Mudar de posição") }}</strong><small>{{ traduzir("Escolha o lugar na fila.") }}</small></span></a>
  </div>
```

Folha nova, depois da `sair`:

```jinja
{% call modal("mover", traduzir("Mudar de posição"), folha == "mover" and alvo, alvo.nome if alvo else "") %}
<form method="post" action="{{ url_agir }}" data-acao>
  <div class="mbody">
    {{ csrf }}<input type="hidden" name="acao" value="mover">
    <input type="hidden" name="pessoa" value="{{ alvo.pessoa_id if alvo else '' }}">
    <fieldset class="fila-opcoes">
      <legend class="msec-title">{{ traduzir("Para qual posição?") }}</legend>
      {% for l in r.fila %}
      {# A posição de quem está sendo movido vem desabilitada: o servidor
         desenha para o alvo da URL, e o script acerta para o alvo do toque. #}
      <label class="fila-opcao"><input type="radio" name="posicao" value="{{ l.posicao }}" required data-posicao-de="{{ l.pessoa_id }}"{% if alvo and l.pessoa_id == alvo.pessoa_id %} disabled{% endif %}><span>{{ l.posicao }}º · {{ l.nome }}</span></label>
      {% endfor %}
    </fieldset>
    {{ motivo_da_correcao() }}
  </div>
  <div class="mfoot">
    <button type="button" class="btn" data-modal-close>{{ traduzir("Cancelar") }}</button>
    <button type="submit" class="btn primary">{{ traduzir("Mudar de posição") }}</button>
  </div>
</form>
{% endcall %}
```

`fila/static/fila/fila.js`, em `abrirFolha`, logo depois do bloco `if (dados.pessoa) { ... }`:

```js
    // Mudar de posição: a posição em que a pessoa já está não se escolhe.
    folha.querySelectorAll("[data-posicao-de]").forEach(function (opcao) {
      opcao.disabled = opcao.dataset.posicaoDe === dados.pessoa;
    });
```

- [ ] **Step 8: Run page + sweeps**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_pagina.py tests/test_fila_correcoes.py tests/test_html_preguicoso_nao_e_seguro.py tests/test_sublinhado_e_o_gettext.py`
Expected: PASS. Quebre `_instante_entre` (retorne sempre `outros[0].na_fila_desde`) e veja os testes de mover vermelhos; desfaça.

- [ ] **Step 9: Commit**

```bash
git add fila/correcoes.py fila/views.py fila/templates/fila/_folhas.html fila/static/fila/fila.js comum/auditoria.py tests/test_fila_correcoes.py tests/test_fila_pagina.py tests/test_auditoria.py
git commit -m "feat: o gerente muda o vendedor de posição na fila"
```
(mensagem longa: o pedido, por que instante entre vizinhos e não número, o reespaçamento no empate.)

---

### Task 4: Pôr em pausa pelo gerente

**Files:**
- Modify: `fila/acoes.py` (extrair `_abrir_pausa`)
- Modify: `fila/correcoes.py` (`por_em_pausa`)
- Modify: `comum/auditoria.py` (`FILA_PAUSA_INICIADA` + rótulo), `tests/test_auditoria.py` (cenário)
- Modify: `fila/views.py`, `fila/templates/fila/_folhas.html`
- Test: `tests/test_fila_correcoes.py`, `tests/test_fila_pagina.py`

**Interfaces:**
- Consumes: `ler_observacao`, `_registrar`, `NAO_ESTA_NA_FILA`, `AcaoDeCorrecao.PAUSAR`.
- Produces: `acoes._abrir_pausa(lugar, filial, tipo_id, agora) -> TipoDePausa`; `correcoes.por_em_pausa(autor, filial, pessoa_id, tipo_id: int | None, *, observacao, request=None) -> None`; `ACOES.FILA_PAUSA_INICIADA = "fila_pausa_iniciada"`.

- [ ] **Step 1: Write the failing rules tests**

```python
def test_gerente_poe_em_pausa_quem_esta_na_fila(loja):
    from fila.acoes import bater_ponto
    from fila.correcoes import por_em_pausa
    from fila.models import CorrecaoNaFila, Estado, LugarNaFila, Pausa

    bater_ponto(loja.ana, loja.matriz)
    por_em_pausa(loja.gerente, loja.matriz, loja.ana.pk, loja.cad.tipo.pk,
                 observacao="foi ao banco")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_PAUSA
    pausa = Pausa.irrestritos.get()
    assert (pausa.pessoa_id, pausa.tipo_id, pausa.fim) == (loja.ana.pk, loja.cad.tipo.pk, None)
    correcao = CorrecaoNaFila.irrestritos.get()
    assert (correcao.acao, correcao.detalhe) == ("pausar", "Almoço")
    assert _ultima_trilha().acao == "fila_pausa_iniciada"


def test_por_em_pausa_recusa_quem_atende_e_tipo_que_nao_serve(loja):
    from fila.acoes import Recusa, bater_ponto, vou_atender
    from fila.correcoes import por_em_pausa

    bater_ponto(loja.ana, loja.matriz)
    bater_ponto(loja.bia, loja.matriz)
    vou_atender(loja.ana, loja.matriz)
    with pytest.raises(Recusa) as recusa:
        por_em_pausa(loja.gerente, loja.matriz, loja.ana.pk, loja.cad.tipo.pk,
                     observacao="teste ok")
    assert recusa.value.frase == "Essa pessoa não está na fila."
    loja.cad.tipo.ativo = False
    loja.cad.tipo.save()
    for tipo_id in (loja.cad.tipo.pk, None, 999999):
        with pytest.raises(Recusa) as recusa:
            por_em_pausa(loja.gerente, loja.matriz, loja.bia.pk, tipo_id,
                         observacao="teste ok")
        assert recusa.value.frase == "Escolha o tipo de pausa."
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py -k "pausa_quem_esta_na_fila or por_em_pausa"`
Expected: FAIL (`ImportError: por_em_pausa`)

- [ ] **Step 3: Implement**

`fila/acoes.py`: substitua o miolo de `pausar` por um helper usado pelas duas:

```python
def _abrir_pausa(lugar, filial, tipo_id, agora):
    """Abre a pausa e muda o lugar. Um miolo para o "Pausa" do vendedor e o
    "Pôr em pausa" do gerente: duas cópias divergiriam no primeiro ajuste."""
    tipo = (TipoDePausa.objects.da_empresa(filial.empresa)
            .filter(pk=tipo_id, ativo=True).first()
            if tipo_id is not None else None)
    if tipo is None:
        raise Recusa(_("Escolha o tipo de pausa."))
    Pausa.irrestritos.create(empresa=filial.empresa, pessoa_id=lugar.pessoa_id,
                             filial=filial, presenca=lugar.presenca,
                             tipo=tipo, inicio=agora)
    lugar.estado = Estado.EM_PAUSA
    lugar.desde = agora
    lugar.save(update_fields=["estado", "desde"])
    return tipo


def pausar(pessoa, filial, tipo_id) -> None:
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_na_loja(pessoa.pk, filial)
        _exigir_na_fila(lugar)
        _abrir_pausa(lugar, filial, tipo_id, _agora())
```

`fila/correcoes.py` (importe `_abrir_pausa` de `.acoes`; `"por_em_pausa"` em `__all__`):

```python
def por_em_pausa(autor, filial, pessoa_id, tipo_id, *, observacao, request=None):
    """O vendedor foi ao banco e não apertou "Pausa" (C4). Só quem está na
    fila: quem atende tem o atendimento fechado antes, pela mesma folha."""
    observacao = ler_observacao(observacao)
    with transaction.atomic():
        _travar(filial)
        lugar = _lugar_de_outro(autor, filial, pessoa_id)
        if lugar.estado != Estado.NA_FILA:
            raise Recusa(NAO_ESTA_NA_FILA)
        agora = _agora()
        tipo = _abrir_pausa(lugar, filial, tipo_id, agora)
        _registrar(autor, filial, pessoa_id, AcaoDeCorrecao.PAUSAR, observacao,
                   tipo.nome, agora, auditoria=ACOES.FILA_PAUSA_INICIADA,
                   alvo=_alvo(lugar, filial), request=request)
```

`comum/auditoria.py`: `FILA_PAUSA_INICIADA = "fila_pausa_iniciada"` e rótulo `"Pausa iniciada pelo gerente"`. `tests/test_auditoria.py`: cenário no molde de `_cenario_fila_pausa_encerrada`, chamando `por_em_pausa(dona, matriz, zeca.pk, cad.tipo.pk, observacao="foi ao banco")`, retornando `(email_de("dona-fila"), f"Zeca em {matriz}")`, registrado como `"FILA_PAUSA_INICIADA"`.

- [ ] **Step 4: Run rules + auditoria + the vendor pause tests**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_correcoes.py tests/test_auditoria.py tests/test_fila_acoes.py`
Expected: PASS

- [ ] **Step 5: Write the failing page test**

```python
def test_gerente_poe_em_pausa_pela_folha(loja):
    from fila.models import Estado, LugarNaFila

    _agir(logado("ana"), acao="ponto")
    gil = logado("gil")
    folha = _html(gil, f"/fila?folha=por_em_pausa&pessoa={loja.ana.pk}")
    aberta = folha[folha.index('id="folha-por_em_pausa"'):]
    aberta = aberta[:aberta.index("</form>")]
    assert f'name="tipo" value="{loja.cad.tipo.pk}"' in aberta
    assert 'name="motivo_da_correcao"' in aberta
    _agir(gil, acao="por_em_pausa", pessoa=str(loja.ana.pk), tipo=str(loja.cad.tipo.pk),
          motivo_da_correcao="foi ao banco")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_PAUSA
```

- [ ] **Step 6: Run to verify it fails**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_pagina.py -k poe_em_pausa_pela_folha`
Expected: FAIL

- [ ] **Step 7: View and sheet**

`fila/views.py`, `_DO_GERENTE`:

```python
    "por_em_pausa": lambda r, f, p: correcoes.por_em_pausa(
        p, f, _pessoa_do_post(r), id_do_post(r, "tipo"),
        observacao=_motivo(r), request=r),
```

`_folhas.html`: no bloco `data-para="na_fila"` da folha `corrigir` (criado na Task 3), um segundo atalho:

```jinja
    <a class="fila-corrigir-item" href="{{ url_fila }}?folha=por_em_pausa&pessoa={{ alvo.pessoa_id if alvo else '' }}" data-folha="por_em_pausa" data-pessoa="{{ alvo.pessoa_id if alvo else '' }}" data-nome="{{ alvo.nome if alvo else '' }}">
      <span class="ci">{{ icon("coffee") }}</span><span><strong>{{ traduzir("Pôr em pausa") }}</strong><small>{{ traduzir("Para quem saiu e não apertou Pausa.") }}</small></span></a>
```

e a folha, fora do `{% if pode_participar %}` (o supervisor gerencia sem participar), dentro do `{% if pode_gerenciar %}`:

```jinja
{% call modal("por_em_pausa", traduzir("Pôr em pausa"), folha == "por_em_pausa" and alvo, alvo.nome if alvo else "") %}
<form method="post" action="{{ url_agir }}" data-acao>
  <div class="mbody">
    {{ csrf }}<input type="hidden" name="acao" value="por_em_pausa">
    <input type="hidden" name="pessoa" value="{{ alvo.pessoa_id if alvo else '' }}">
    <fieldset class="fila-opcoes">
      <legend class="msec-title">{{ traduzir("Pausa para quê?") }}</legend>
      {% for t in tipos %}
      <label class="fila-opcao"><input type="radio" name="tipo" value="{{ t.pk }}" required><span>{{ t.nome }}</span></label>
      {% endfor %}
    </fieldset>
    {{ motivo_da_correcao() }}
  </div>
  <div class="mfoot">
    <button type="button" class="btn" data-modal-close>{{ traduzir("Cancelar") }}</button>
    <button type="submit" class="btn primary">{{ traduzir("Pôr em pausa") }}</button>
  </div>
</form>
{% endcall %}
```

(`tipos` já está no contexto de `fila/tela.py::_contexto`.)

- [ ] **Step 8: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_pagina.py tests/test_fila_correcoes.py tests/test_fila_acoes.py`
Expected: PASS. Quebre `por_em_pausa` (tire o `if lugar.estado != Estado.NA_FILA`) e veja vermelho; desfaça.

- [ ] **Step 9: Commit**

```bash
git add fila/acoes.py fila/correcoes.py fila/views.py fila/templates/fila/_folhas.html comum/auditoria.py tests/test_fila_correcoes.py tests/test_fila_pagina.py tests/test_auditoria.py
git commit -m "feat: o gerente põe o vendedor em pausa"
```

---

### Task 5: Mover sob concorrência

**Files:**
- Test: `tests/test_fila_concorrencia.py`

**Interfaces:**
- Consumes: `correcoes.mover` (Task 3), `acoes.vou_atender`, `acoes._lugar_na_loja`.

- [ ] **Step 1: Write the test** (fim do arquivo)

```python
@pytest.mark.django_db(transaction=True)
def test_mover_e_vou_atender_ao_mesmo_tempo_nao_quebram_a_fila(monkeypatch):
    """O gerente move a Bia para o 1º enquanto a Ana, que é a 1ª, toca "Vou
    atender". A trava serializa: ou a Ana atende e a Bia fica sozinha na
    fila, ou a Bia passa na frente e a Ana é recusada. Nunca um 500, nunca
    dois atendimentos, nunca a Bia fora da fila."""
    import fila.acoes as acoes
    from fila.correcoes import mover
    from fila.estado import na_fila
    from fila.models import Atendimento

    empresa, matriz, _ = sylvia()
    gil = pessoa_na_loja("gil", empresa, matriz, cargo="gerente")
    ana = pessoa_na_loja("ana", empresa, matriz)
    bia = pessoa_na_loja("bia", empresa, matriz)
    acoes.bater_ponto(ana, matriz)
    acoes.bater_ponto(bia, matriz)

    ler_de_verdade = acoes._lugar_na_loja

    def ler_devagar(pessoa_id, filial):
        lugar = ler_de_verdade(pessoa_id, filial)
        time.sleep(0.3)
        return lugar

    monkeypatch.setattr(acoes, "_lugar_na_loja", ler_devagar)
    largada = threading.Barrier(2)
    resultados = {}

    def rodar(nome, acao):
        try:
            largada.wait()
            acao()
            resultados[nome] = "ok"
        except acoes.Recusa:
            resultados[nome] = "recusa"
        except Exception as erro:
            resultados[nome] = f"erro: {type(erro).__name__}"
        finally:
            connection.close()

    threads = [
        threading.Thread(target=rodar, args=("atender", lambda: acoes.vou_atender(ana, matriz))),
        threading.Thread(target=rodar, args=("mover", lambda: mover(
            gil, matriz, bia.pk, 1, observacao="chegou antes"))),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not any(v.startswith("erro") for v in resultados.values()), resultados
    assert Atendimento.irrestritos.count() <= 1
    assert bia.pk in [l.pessoa_id for l in na_fila(matriz)]
```

(`correcoes._lugar_de_outro` chama `_lugar_na_loja` importado por nome; para a demora valer também no mover, troque em `fila/correcoes.py` a chamada por `acoes._lugar_na_loja(pessoa_id, filial)` — o mesmo motivo de `_agora()` ler pelo módulo — e comente o porquê.)

- [ ] **Step 2: Run**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_concorrencia.py`
Expected: PASS. Dente: comente `_travar(filial)` em `mover` e rode de novo algumas vezes; deve aparecer falha (Ana atendendo e a Bia "passando" na frente de um lugar que já não está na fila, ou `resultados` com erro). Desfaça.

- [ ] **Step 3: Commit**

```bash
git add tests/test_fila_concorrencia.py fila/correcoes.py
git commit -m "test: mover e vou atender ao mesmo tempo passam pela trava"
```

---

### Task 6: A tela "Histórico da fila"

**Files:**
- Create: `fila/views_historico.py`
- Modify: `fila/urls.py`, `fila/modulo.py`
- Modify: `fila/templates/fila/pagina.html` (link "Histórico")
- Test: `tests/test_fila_historico.py`

**Interfaces:**
- Consumes: `CorrecaoNaFila`, `AcaoDeCorrecao`; `fila.indicadores.lojas_com_permissao(pessoa, empresa, "fila.gerenciar")`; `fila.periodo.periodo_do_pedido`, `ATALHOS`; `fila.views_indicadores._lojas_do_pedido(request, permitidas)` e `TODAS`; `comum.listagem.montar_pagina`, `ColunaFiltravel`.
- Produces: `views_historico.historico(request)` na rota `fila_historico` (`/fila/historico`).

- [ ] **Step 1: Write the failing tests** (`tests/test_fila_historico.py`)

```python
"""A tela do histórico das correções (spec 2026-09-17, C5)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.fila_cenario import logado, nova_loja, pessoa_na_loja, sylvia

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
        sara=pessoa_na_loja("sara", empresa, None, cargo="supervisor"))


def _correcao(rede, loja, pessoa, autor, observacao, acao="mover", quando=None):
    from fila.models import CorrecaoNaFila

    return CorrecaoNaFila.irrestritos.create(
        empresa=rede.empresa, filial=loja, pessoa=pessoa, autor=autor, acao=acao,
        observacao=observacao, detalhe="de 2º para 1º", momento=quando or timezone.now())


def _html(cliente, **params):
    resposta = cliente.get("/fila/historico", params)
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_vendedor_nao_abre(rede):
    assert logado("caio").get("/fila/historico").status_code == 404


def test_gerente_ve_so_a_loja_dele_e_a_forjada_cai_na_dele(rede):
    _correcao(rede, rede.centro, rede.caio, rede.gil, "chegou antes")
    _correcao(rede, rede.matriz, rede.ana, rede.sara, "foi ao banco")
    gil = logado("gil")
    html = _html(gil)
    assert "chegou antes" in html and "foi ao banco" not in html
    assert "foi ao banco" not in _html(gil, loja=str(rede.matriz.pk))


def test_supervisor_ve_todas_as_lojas(rede):
    _correcao(rede, rede.centro, rede.caio, rede.gil, "chegou antes")
    _correcao(rede, rede.matriz, rede.ana, rede.sara, "foi ao banco")
    html = _html(logado("sara"), loja="todas")
    assert "chegou antes" in html and "foi ao banco" in html


def test_periodo_padrao_e_hoje(rede):
    _correcao(rede, rede.centro, rede.caio, rede.gil, "de hoje")
    _correcao(rede, rede.centro, rede.caio, rede.gil, "da semana passada",
              quando=timezone.now() - timedelta(days=8))
    gil = logado("gil")
    html = _html(gil)
    assert "de hoje" in html and "da semana passada" not in html
    assert "da semana passada" in _html(gil, periodo="30dias")


def test_colunas_filtro_e_acao_por_extenso(rede):
    from tests.test_regra_tabela import (
        _MARCADOR_FILTRO, _MARCADOR_PAGINACAO, _PADRAO_CABECALHO_ORDENAVEL)

    _correcao(rede, rede.centro, rede.caio, rede.gil, "chegou antes")
    html = _html(logado("gil"))
    assert _MARCADOR_FILTRO in html and _MARCADOR_PAGINACAO in html
    assert _PADRAO_CABECALHO_ORDENAVEL.search(html)
    assert "Mudou de posição" in html and "de 2º para 1º" in html
    filtrado = _html(logado("gil"), **{"f:observacao:contem": "banco"})
    assert "chegou antes" not in filtrado


def test_a_pagina_da_fila_tem_o_link_so_para_a_gestao(rede):
    gil = logado("gil")
    assert 'href="/fila/historico"' in gil.get("/fila").content.decode()
    assert 'href="/fila/historico"' not in logado("caio").get("/fila").content.decode()
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_historico.py`
Expected: FAIL (404 na rota)

- [ ] **Step 3: Implement** (`fila/views_historico.py`)

Leia antes `fila/views_indicadores.py::_filtros` e `blocos_dos_indicadores` para ver como `Card`, `Form`, `FormGrid`, `Select` e `montar_pagina` são montados; a tela segue o mesmo molde.

```python
"""O histórico das correções do gerente (spec 2026-09-17, C5).

Mesma regra de loja do painel do Início: as lojas saem do cargo
(`fila.gerenciar` em cada uma), a tela abre na loja do cabeçalho, e "Todas as
lojas" é escolha explícita de quem alcança mais de uma. Uma `?loja=` forjada
não amplia o recorte.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.components import (Button, Card, Cell, Column, Form, FormGrid,
                               Option, PageHeader, Raw, Select, Table)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from .estado import nome_de
from .indicadores import lojas_com_permissao
from .models import AcaoDeCorrecao, CorrecaoNaFila
from .periodo import ATALHOS, periodo_do_pedido
from .views_indicadores import TODAS, _lojas_do_pedido

__all__ = ["historico"]

ORDENAVEIS = {
    "momento": ("momento", "pk"),
    "loja": ("filial__apelido", "momento"),
    "vendedor": ("pessoa__nome", "momento"),
    "acao": ("acao", "momento"),
    "autor": ("autor__nome", "momento"),
}
FILTRAVEIS = {
    "vendedor": ColunaFiltravel(("pessoa__nome", "pessoa__email"), "Vendedor"),
    "acao": ColunaFiltravel("acao", "Ação", tipo="opcoes",
                            opcoes=lambda: [(str(v), str(r)) for v, r in AcaoDeCorrecao.choices]),
    "observacao": ColunaFiltravel("observacao", "Motivo"),
}


def _filtros(request, periodo, permitidas, loja):
    # Período abrindo em "Hoje": o histórico é o que o gerente confere no fim
    # do dia, e "Este mês" (o padrão do painel) afogaria o de hoje.
    campos = [Select(name="periodo", label=_("Período"), span=3, value=periodo.chave,
                     options=[Option(c, r) for c, r in ATALHOS])]
    if len(permitidas) > 1:
        campos.append(Select(
            name="loja", label=_("Loja"), span=3, value=str(loja.pk) if loja else TODAS,
            options=[*(Option(str(l.pk), str(l)) for l in permitidas),
                     Option(TODAS, _("Todas as lojas"))]))
    campos.append(Cell(span=2, children=Button(label=_("Aplicar"), variant="primary",
                                                type="submit")))
    return Card(body=Form(method="get", action=reverse("fila_historico"),
                          children=FormGrid(children=campos)))


@exigir_permissao("fila.gerenciar")
@exigir_modulo_ligado("fila")
def historico(request) -> HttpResponse:
    from plataforma.site import montar_site

    empresa = empresa_atual(request)
    permitidas = lojas_com_permissao(usuario_de(request.usuario), empresa, "fila.gerenciar")
    pedido = request.GET.copy()
    pedido.setdefault("periodo", "hoje")
    periodo = periodo_do_pedido(pedido)
    lojas, loja = _lojas_do_pedido(request, permitidas) if permitidas else ([], None)
    consulta = (CorrecaoNaFila.objects.da_empresa(empresa)
                .filter(filial__in=lojas, momento__gte=periodo.de, momento__lt=periodo.ate)
                .select_related("filial", "pessoa", "autor")
                .defer("pessoa__avatar", "autor__avatar"))
    listagem = montar_pagina(request, consulta, ordenaveis=ORDENAVEIS, padrao="-momento",
                             filtraveis=FILTRAVEIS, preservar=("periodo", "loja"))
    colunas = [
        Column("momento", listagem.cabecalho("momento", str(_("Quando"))),
               render=lambda c: timezone.localtime(c.momento).strftime("%d/%m %H:%M")),
        Column("loja", listagem.cabecalho("loja", str(_("Loja"))), render=lambda c: str(c.filial)),
        Column("vendedor", listagem.cabecalho("vendedor", str(_("Vendedor"))), strong=True,
               render=lambda c: nome_de(c.pessoa)),
        Column("acao", listagem.cabecalho("acao", str(_("Ação"))),
               render=lambda c: format_html("{}<br><small>{}</small>",
                                            c.get_acao_display(), c.detalhe)),
        Column("observacao", str(_("Motivo")), render=lambda c: c.observacao),
        Column("autor", listagem.cabecalho("autor", str(_("Quem corrigiu"))),
               render=lambda c: nome_de(c.autor)),
    ]
    with use_environment(ambiente()):
        site = montar_site(request)
        pagina = site.page(
            title=_("Histórico da fila"), width="full",
            stylesheets=["/static/plataforma/listagem.css"],
            content=[
                aviso_de_personificacao(request),
                PageHeader(title=_("Histórico da fila"),
                           subtitle=_("As correções do gerente, com o motivo de cada uma.")),
                _filtros(request, periodo, permitidas, loja),
                Card(title=f"{periodo.rotulo}, {loja or _('todas as lojas')}", padded=False,
                     body=[listagem.barra, Table(columns=colunas, rows=listagem.linhas),
                           listagem.paginacao]),
            ],
            crumbs=[Crumb(_("Histórico da fila"))], user=request.usuario)
        return render(pagina)
```

`fila/urls.py`: `from . import ..., views_historico` e `path("fila/historico", views_historico.historico, name="fila_historico"),`.

`fila/modulo.py`, em `atalhos`:

```python
        # Solto no grupo Vendas, ao lado da fila, e não como submenu: um `pai`
        # "Fila da vez" criaria um segundo item com o nome do módulo.
        Atalho(rotulo=_("Histórico da fila"), rota="/fila/historico",
               permissao="fila.gerenciar", grupo="Vendas"),
```

`fila/templates/fila/pagina.html`, em `.fila-hero-direita`, antes de "Meu painel":

```jinja
        {% if pode_gerenciar %}<a class="fila-meu-painel" href="/fila/historico" data-historico>{{ icon("history", "sm") }}<span>{{ traduzir("Histórico") }}</span></a>{% endif %}
```

(Os ícones `arrow-up-down`, `coffee` e `history` existem no Lucide da casa. O filtro de texto se chama `f:<coluna>:contem`, e o de opções `f:<coluna>:igual`, por `comum/listagem.py::OPERADORES`.)

- [ ] **Step 4: Run tela + sweeps**

Run: `.venv/bin/python -m pytest -q -p no:warnings tests/test_fila_historico.py tests/test_guarda.py tests/test_guarda_modulo.py tests/test_regra_tabela.py tests/test_personificacao.py tests/test_fila_pagina.py`
Expected: PASS. Dente: troque `filter(filial__in=lojas, ...)` por `filter(...)` sem a loja e veja `test_gerente_ve_so_a_loja_dele` vermelho; desfaça.

- [ ] **Step 5: Commit**

```bash
git add fila/views_historico.py fila/urls.py fila/modulo.py fila/templates/fila/pagina.html tests/test_fila_historico.py
git commit -m "feat: a tela do histórico das correções da fila"
```

---

### Task 7: Castelhano, documentação e a suíte inteira

**Files:**
- Modify: `locale/es/LC_MESSAGES/django.po` (+ `.mo` compilado)
- Modify: `CLAUDE.md` (§10 e contagem de arquivos de teste)
- Modify: `docs/superpowers/specs/2026-09-17-fila-correcoes-do-gerente-design.md` (Estado)

- [ ] **Step 1: Find the untranslated phrases**

```bash
.venv/bin/python - <<'EOF'
import re
from pathlib import Path
po = Path("locale/es/LC_MESSAGES/django.po").read_text()
ids = set(re.findall(r'^msgid "(.*)"$', po, re.M))
fontes = "".join(Path(p).read_text() for p in [
    "fila/correcoes.py", "fila/models.py", "fila/views_historico.py", "fila/modulo.py",
    "fila/templates/fila/_folhas.html", "fila/templates/fila/pagina.html"])
achados = (set(re.findall(r'traduzir\([\'"](.+?)[\'"]\)', fontes))
           | set(re.findall(r'(?<![a-z])_\("(.+?)"\)', fontes))
           | set(re.findall(r'gettext_lazy\("(.+?)"\)', fontes)))
print("\n".join(sorted(achados - ids)))
EOF
```

- [ ] **Step 2: Add each one** ao fim do `django.po` (`#, python-format` antes das que têm `%(…)s`), com castelhano do Paraguai no mesmo tom das existentes (ex.: "Escreva o motivo da correção." → "Escriba el motivo de la corrección."; "Mudar de posição" → "Cambiar de posición"; "Pôr em pausa" → "Poner en pausa"; "Histórico da fila" → "Historial de la fila"). Compile:

Run: `.venv/bin/pybabel compile -d locale -D django`
Expected: `compiling catalog locale/es/LC_MESSAGES/django.po to ...django.mo`

- [ ] **Step 3: CLAUDE.md**

Em §10 "Onde mora cada regra", depois de `fila/correcoes.py`:

```markdown
- `fila/correcoes.py` também exige o **motivo** de toda correção
  (`ler_observacao`, 3 a 200 caracteres, campo `motivo_da_correcao`) e grava
  cada uma em `CorrecaoNaFila` e na auditoria juntas. O histórico sai em
  `/fila/historico` (`fila/views_historico.py`), para `fila.gerenciar`.
```

Em "O que custa esquecer":

```markdown
- **Mover não guarda número de posição.** Grava em `na_fila_desde` um
  instante ESTRITAMENTE entre os vizinhos (e reespaça a fila quando estão
  colados); igual a um deles, o `pk` desempataria e a pessoa podia cair do
  lado errado. Por isso a versão da fila conta as correções: o maior
  `na_fila_desde` não muda quando alguém vai para o meio.
- **O motivo da correção se chama `motivo_da_correcao`**, e não
  `observacao`, que é o campo da não venda na mesma folha.
```

A entrega cria um arquivo de teste (`tests/test_fila_historico.py`): troque "134 arquivos" por "135 arquivos" nas duas ocorrências e rode `tests/test_documentacao_nao_mente.py`, que confere o número.

No spec, troque `**Estado:** desenho aprovado na conversa de 17/09/2026; falta o plano.` por `**Estado:** implementado (plano 2026-09-17-fila-correcoes-do-gerente).`

- [ ] **Step 4: Full suite**

Run: `timeout 590 .venv/bin/python -m pytest -q -p no:warnings`
Expected: tudo verde (os testes de backup pulam sem `pg_dump`). Se algo falhar, **não** commite: investigue e corrija na task correspondente.

- [ ] **Step 5: Check in the browser**

Com o servidor local (`DJANGO_DEBUG=1 .venv/bin/python manage.py runserver 127.0.0.1:8005`) e dados locais, entre como gerente: bata o ponto de dois vendedores, abra Corrigir, mude de posição, ponha em pausa, tire da pausa (com motivo) e abra `/fila/historico`. Confira em 390px e 1366px de largura. Só local: nada de produção.

- [ ] **Step 6: Commit**

```bash
git add locale/es/LC_MESSAGES/django.po locale/es/LC_MESSAGES/django.mo CLAUDE.md docs/superpowers/specs/2026-09-17-fila-correcoes-do-gerente-design.md
git commit -m "docs: as correções do gerente no CLAUDE.md e em castelhano"
```
