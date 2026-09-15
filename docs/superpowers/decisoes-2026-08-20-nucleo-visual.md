# Decisões da entrega 1 (núcleo visual) — 2026-08-20

Este documento existe porque `.superpowers/` não é rastreado pelo git
(`.gitignore:7`). Dentro dele ficam as decisões que o controlador tomou
durante a execução das dez tarefas desta entrega — 19 rulings, numeradas
`R1` a `R19` no registro original (`.superpowers/sdd/2026-08-20-nucleo-visual/progress.md`).
Várias divergências do código portado contra a fonte
(`/home/mw5/projetos/criadordesitesmw5/packages/mw5_admin/mw5_admin/`) foram
autorizadas por essas decisões, não pelo plano escrito. Sem este registro,
quem for ressincronizar com o `mw5_admin` daqui a um ano encontra a
divergência — um import diferente, um índice de `parents[]` trocado, um
teste que fala de um pacote que não existe aqui — mas não a razão dela.

A propriedade que dá valor a este porte é que cada arquivo difere da
origem **só nos pontos autorizados**, verificável por `diff`. Este
documento é a lista dessas autorizações.

## Como ler

Cada seção agrupa decisões por tema, não pela ordem em que aconteceram.
Onde relevante, cito o número da ruling entre parênteses para quem quiser
achar o texto original em `progress.md`. "Custo se errado" é a estimativa
do controlador de quanto custaria desfazer a decisão, feita no momento em
que ela foi tomada — não uma avaliação posterior.

## Ordem de execução das tarefas

O plano previa a ordem 1 a 10; a execução real foi **1, 2, 3, 4, 6, 5, 7,
8, 9, 10** — a Task 5 (campos) trocou de lugar com a Task 6 (componentes).

- **Branch única, sem worktree separado** (R1). O repositório era novo,
  sem trabalho concorrente; um worktree teria custo sem isolamento
  adicional. Reversível a qualquer momento.
- **Task 2 ganhou `nucleo/templates/.gitkeep` cedo, em vez de propagar
  `xfail` por três tarefas** (R5). `create_environment()` levanta
  `ValueError` na própria construção se a pasta `templates/` não existir —
  não só no `get_template` — porque `PackageLoader` falha na
  inicialização. Sem a pasta, a fixture *autouse* de `test_campos.py`
  (Task 5) quebraria com `ERROR`, não com um `xfail` limpo. Com a pasta
  existindo desde a Task 2, os dois xfails prometidos pelo plano nunca
  precisaram existir.
- **Tasks 5 e 6 trocaram de ordem** (R6). `create_environment()` faz
  import tardio de `components.primitives.Icon` — é o truque que quebra o
  ciclo `rendering` ↔ `components` na fonte — então só funciona com
  `components/` presente. A fixture da Task 5 (campos) chama
  `create_environment()`; rodá-la antes da Task 6 (que traz
  `components/`) a deixaria sem base nenhuma. Alternativas descartadas:
  fazer `create_environment` tolerar a ausência de `Icon` (divergiria da
  fonte, que é a especificação do porte) ou adiantar um stub de
  `components/` (duas definições da mesma peça, uma delas descartável).
- **A cópia dos estáticos do tema (originalmente Task 9) foi antecipada
  para a Task 3** (R7). `test_theme.py` não é um arquivo de teste puro:
  17 dos 84 testes portados leem o CSS gerado direto do disco, para
  confirmar que os tokens que o tema calcula são de fato os que a folha
  consome. Adiar a cópia até a Task 9 deixaria 20% da suíte do tema sem
  verificação por seis tarefas — justamente os testes que ligam token a
  estilo. A alternativa descartada (`xfail` nesses 17 testes) foi
  rejeitada pelo mesmo motivo.

## O que se porta, e como se decide o que é "porte literal"

- **`nucleo/__init__.py` reexporta a mesma API pública que
  `mw5_admin/__init__.py`** (R8): `Brand`, `Component`, `Guarda`, `Site`,
  `User`, `auth`, `pode`, `create_app`, `create_environment`, `render`,
  `render_theme_css`, `use_environment`. A suíte portada já fazia
  `from nucleo import Brand` (herdado do `sed` sobre `from mw5_admin import
  Brand`), e o pacote estava vazio — o plano nunca disse o que o topo do
  pacote expõe. A decisão foi construir a superfície incrementalmente,
  cada tarefa acrescentando o que entrega, e não "corrigir" o teste
  portado para caber num empacotamento mais pobre: a suíte portada **é**
  a especificação do porte, e a superfície de topo é o contrato que os
  sistemas filhos (como `sementes-premix`) de fato consomem.
- **Regra geral: o porte é literal quanto a comportamento e estrutura —
  incluindo o idioma dos nomes de teste portados, mesmo quando a regra
  global deste repositório pede português** (R9). Cerca de 22 dos 79
  métodos portados de `test_theme.py` têm nome em inglês; ficaram assim.
  Traduzir destruiria a única propriedade que dá valor a este método de
  porte — a de que o arquivo diverge da fonte só nos pontos que o plano
  nomeia, verificável por `diff`. Essa mesma regra cobre o boilerplate do
  `django-admin startproject` (docstrings em inglês em `settings.py`,
  `urls.py`, `wsgi.py`, `asgi.py`, `manage.py`): é texto de vendor, não
  autoral.
- **`test_components.py` (158 testes) foi dividido em três grupos por
  dependência real, não portado ou descartado em bloco** (R12): 121 testam
  componente puro e entraram na Task 6; 35 dependem de `layout`/`site` e
  ganharam `xfail(strict=True)` até a Task 8 remover a marca; 2 dependem do
  gerador (`mw5_generator`) e **não foram portados** — ver a próxima
  seção. `strict=True` existe para que nenhum desses xfails vire
  esquecimento: qualquer um que passasse sem remover a marca quebraria a
  suíte como `XPASS`.
- **Um teste autoral pode conviver com um arquivo portado, desde que
  marcado como autoral** (R14, precedente aberto na Task 3 com
  `TestContrasteDaMarca`). Usado de novo em `test_campos.py`: o ramo de
  produção de `_opcoes_da_relacao` que roda quando o catálogo está vazio
  — **o único ramo que existe nesta entrega**, já que o catálogo só se
  popula na entrega 3 — não tinha teste nenhum. O teste existente de
  "relação" só verificava a presença de `<select`, o que passa pelos dois
  ramos igualmente. Um teste autoral fechou a lacuna sem tocar no
  arquivo portado.

## O que se remove — permanentemente, não por adiamento

- **`path("admin/", admin.site.urls)` saiu de `config/urls.py`** (R4).
  `django.contrib.admin` não está instalado nesta entrega, e a Task 9
  reescreve `config/urls.py` para incluir `nucleo.urls` de qualquer
  forma. Mesma lógica de remover os apps de `auth`/`messages` do
  `TEMPLATES` (R2): instalar agora traria migração e banco que nada
  nesta entrega usa. A rota volta na entrega 2, junto com o app admin.
- **Dois testes de `test_components.py` não foram portados**: os que
  importam `mw5_generator` (R12b) — `test_o_painel_do_gerador_tambem_poe_o_espacamento_na_camada_certa`
  e `test_a_faixa_nao_aparece_na_configuracao_de_cores` — mais um em
  `test_espacamento_do_formulario.py` que importa `mw5_generator.corpo`.
  **Isto não é adiamento — é fora de escopo permanente.**
  `mw5_generator` é a ferramenta que gera um projeto Python por cliente, e
  a premissa inteira do KRONOS.net é o oposto: uma matriz única para mais
  de 20 clientes, sem geração por cliente. Esse código nunca vai existir
  aqui. Um `xfail` eterno seria peso morto disfarçado de cobertura. Isto
  não contradiz "a suíte portada é a especificação" — especificação de um
  sistema que não se constrói não é especificação, é lixo. Os nomes
  removidos ficam registrados em comentário no topo dos dois arquivos,
  para o `diff` contra a fonte continuar explicável. `mw5_generator`
  entrou na lista de "não portar" das Global Constraints do plano.
- **Nenhum botão de alternar tema foi acrescentado ao header** (R15),
  apesar de o plano mandar conferi-lo. O botão não existe no design system
  de origem — foi removido de propósito, e `test_nao_ha_mais_botao_de_tema`
  guarda essa ausência como especificação ativa. O erro foi do plano, que
  citava uma versão anterior da spec do `mw5_admin`; o design evoluiu e o
  plano não acompanhou. Corrigir o plano, não o código, foi a decisão —
  acrescentar o botão teria quebrado um teste que é especificação.

## Ajustes de caminho e de nome — a exceção ao porte literal

Referência ao **próprio nome do pacote** acompanha a renomeação de
`mw5_admin` para `nucleo`, porque isso **é** a renomeação, não divergência
dela. Quatro casos:

- **`tests/test_icons.py`: `Path(nucleo.__file__).resolve().parents[3]` →
  `parents[1]`** (R10a). Na origem, `mw5_admin/__init__.py` mora em
  `packages/mw5_admin/mw5_admin/`, quatro níveis abaixo da raiz do
  repositório; aqui, `nucleo/__init__.py` mora dois níveis abaixo. Com o
  índice antigo, o teste do `NOTICE` ficava `SKIPPED` — silenciosamente,
  sem afirmar nada — que é exatamente o defeito que a rubrica de revisão
  marca como Important. O índice é artefato de onde o arquivo morava na
  árvore de origem, não parte da especificação; preservá-lo literalmente
  preservaria um ponteiro quebrado.
- **`nucleo/icons.py`: mensagem de erro `mw5_admin.icons.buscar(...)` →
  `nucleo.icons.buscar(...)`** (R10b).
- **9 testes de `test_components.py`: `from nucleo.auth import User` →
  `from nucleo.permissoes import User`** (R13), com
  `xfail(strict=True, reason="nucleo.permissoes chega na Task 7")` até a
  Task 7 remover a marca. `nucleo.auth` nunca vai existir — foi decisão do
  controlador, no plano, portar só `mw5_admin/auth/models.py` e chamá-lo
  `nucleo/permissoes.py` (dos 7 arquivos de `auth/` na origem, 6 não
  foram portados). Manter o nome `auth` para um pacote de um arquivo só
  seria mentira de estrutura, e colidiria de nome com
  `django.contrib.auth`, que a entrega 2 traz de verdade.
- **6 pontos de `test_theme.py`**: `Path(mw5_admin.__file__).parent /
  "static" / "mw5.css"` → `Path(nucleo.__file__).parent / "static" /
  "nucleo" / "mw5.css"` (parte da R7) — o caminho da convenção Django de
  arquivos estáticos por app, não um caminho arbitrário.

## Qualidade dos testes de demonstração

- **Os marcadores de `test_demonstracao.py` para Avatar e Badge eram
  falsos positivos** (R17, achado na revisão da Task 10). "Ana Paula"
  aparecia 5 vezes na página, inclusive no `title` do avatar do
  cabeçalho (`VISITANTE.name = "Ana Paula Souza"`) — remover o `Avatar`
  do miolo não derrubaria o teste. O marcador do `Badge` era só o dígito
  "3", que também aparece dentro do timestamp de cache-busting do CSS
  (`mw5.css?v=1787235793`). Trocados por texto que só o componente da
  demonstração emite, provado por remoção real (o teste ficando vermelho
  quando o componente sai do miolo), não por leitura do código.
- **A demonstração cobria 17 dos 58 componentes exportados, apesar da
  docstring dizer "todo componente, uma vez cada"** (achado #5 da revisão
  final da branch). **Ruling R18**: completar `_miolo()`, não estreitar a
  afirmação. Motivo: a tela de demonstração é a única verificação visual
  da entrega inteira — os testes unitários afirmam estrutura de HTML, e
  claro/escuro só é conferido no nível das variáveis CSS. Um componente
  que nunca desenhou dentro do shell pode estar quebrado no escuro sem
  que nada revele. As duas famílias com mais testes unitários e zero
  verificação visual eram exatamente as ausentes: os nove tipos de campo
  (47 testes) e `Chart` (64 testes). Executado na correção final desta
  mesma onda — ver `correcao-final-report.md` para o resultado (58/58
  componentes referenciados, 31 marcadores novos, dois defeitos reais
  achados renderizando de verdade: um `Toast` que se auto-escondia e um
  `Mapa` com URL fake dependente de rede de terceiro).

## Segurança e ambiente

- **`SECRET_KEY`, `DEBUG` e `ALLOWED_HOSTS` falham fechado, não
  abertos** (R19). Uma primeira correção (ainda na mesma onda) trocou o
  `SECRET_KEY` commitado por uma variável de ambiente com fallback fixo
  de desenvolvimento, e `DEBUG` por uma variável com padrão `"1"`
  (ligado). Uma revisão de segurança automática apontou os dois como
  falha aberta: esquecer `DJANGO_DEBUG` em produção entregaria
  `DEBUG=True` (traceback completo, settings expostos), e esquecer
  `DJANGO_SECRET_KEY` cairia no fallback conhecido em silêncio — trocando
  "chave commitada" por "chave commitada que ninguém percebe que está
  usando". Corrigido para falhar fechado: `DEBUG` padrão `False`,
  `SECRET_KEY` obrigatória fora de `DEBUG=True` (levanta
  `ImproperlyConfigured` na subida do processo). Argumento decisivo: o
  resto da base já falha fechado por padrão — `pode(None, x)` é `False`,
  `Protected` nasce com `allowed=False` — e um `settings.py` que falha
  aberto contradiria esse princípio. Custo: rodar local passa a exigir
  `DJANGO_DEBUG=1`, documentado em `README.md`.
- **Chave commitada não é defeito desta entrega pelo escopo** (nota da
  Task 9, antes da R19): a entrega 1 é local, sem deploy. Mas é semente
  ruim — sobrevive até produção sem ninguém reparar — e a decisão foi
  registrar o achado e levá-lo explicitamente à revisão final da branch,
  em vez de expandir o escopo da Task 9 ou da Task 10. Foi exatamente o
  que aconteceu: a revisão final gerou a correção da R19.

## Processo e histórico do git

- **`git commit --amend` foi usado uma vez (Task 4), apagando o commit
  que documentava o estado pré-correção** (R11). Julgado como achado real
  mas não retrabalhável: nenhum teste dependia do commit apagado, e
  desfazer a reescrita não recuperaria informação. Decisão prospectiva:
  **proibir `--amend` explicitamente daqui em diante** — correção
  pós-revisão vira sempre commit próprio. A correção final desta mesma
  onda opera sob essa proibição.
  - Correção sobre a R11: o controlador havia argumentado, ao aceitar a
    R11, que o rastro do commit apagado sobrevivia no relatório da
    tarefa "versionado junto". **Isso era factualmente errado** — o
    relatório não é versionado (mesmo problema que motiva este próprio
    documento). Registrado aqui para não repetir o argumento.

## Pendências com consequência para a entrega 3

Itens que não bloqueiam esta entrega, mas que quem trabalhar na entrega 3
precisa conhecer antes de tropeçar neles:

- **Truncamento de permissão de 3+ níveis.** `pode()` usa
  `f"{modulo}.*" in permissions` sobre só o primeiro segmento da string —
  `"a.b.c"` considera apenas `"a"` e ignora o resto em silêncio. Nenhum
  dos quatro casos testados libera permissão a mais, e o argumento é
  literal de código, não input de usuário digitado — mas se alguém
  desenhar permissão de três ou mais níveis na entrega 3, o comportamento
  atual trunca sem avisar.
- **Gancho morto `data-theme-toggle` em `mw5.js`.** Uma ocorrência, sem
  nenhum elemento HTML que a dispare — código herdado da fonte, de quando
  o botão de tema existia. Se a tela de Aparência da entrega 3
  reintroduzir um seletor de tema, o gancho já está lá pronto para uso,
  mas `test_nao_ha_mais_botao_de_tema` (que hoje garante a ausência) terá
  que ser revisto junto.
- **`SITE.nav = NAV_DEMO` muta um objeto de módulo compartilhado por
  requisição.** Sem race prático hoje — o valor é constante e a atribuição
  é idempotente — mas não escala para a entrega 3, quando `Site` passar a
  vir do banco por instalação. O próprio comentário no código já antecipa
  que este bloco inteiro (`SITE`, `NAV_DEMO`, `VISITANTE`) some junto com
  a entrega 2/3.
- **`rotulo_do_registro` e `Campo.nome` sem teste direto.** Na fonte, os
  dois são cobertos por `test_catalogo.py`, que depende de `Resource`
  (entrega 3, `dados/resource.py`). Reavaliar a cobertura quando esse
  módulo for portado.
- **`Site.theme_href` tem default que aponta para um caminho
  inexistente.** O default da dataclass é `"/static/theme.css"`
  (`nucleo/site.py:49`), mas a única rota que serve CSS de tema é
  `/tema.css` (`nucleo/urls.py`, view `tema_css`) — `SITE` em
  `nucleo/views.py` só funciona porque sobrescreve `theme_href="/tema.css"`
  explicitamente na construção. Qualquer `Site` novo que não fizer esse
  override (um teste, uma instalação de cliente na entrega 3) aponta para
  um caminho morto. Vale corrigir o default, ou documentar bem alto que
  ele precisa de override, antes que uma instalação real tropece nisso.

## Onde estão as fontes primárias

- `.superpowers/sdd/2026-08-20-nucleo-visual/progress.md` — o registro
  completo, com todos os achados, não só as decisões (não rastreado).
- `.superpowers/sdd/2026-08-20-nucleo-visual/task-*-brief.md` e
  `task-*-report.md` — briefs e relatórios de cada uma das dez tarefas
  (não rastreados).
- `.superpowers/sdd/2026-08-20-nucleo-visual/correcao-final-report.md` —
  o relatório da onda de correção que aplicou a R18 e a R19, entre outras
  (não rastreado).
- `docs/superpowers/plans/2026-08-20-nucleo-visual.md` — o plano
  original, já corrigido nos pontos que as rulings acima tocaram
  (rastreado).
