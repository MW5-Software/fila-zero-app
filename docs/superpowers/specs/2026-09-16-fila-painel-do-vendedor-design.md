# Fila Zero — o painel do vendedor

**Data:** 16/09/2026
**Estado:** desenho aprovado e implementado na branch `painel-do-vendedor` (plano de 16/09/2026).
**Depende de:** a fila (`2026-09-15-fila-da-vez-design.md`), os indicadores
(`2026-09-15-fila-indicadores-design.md`) e as metas
(`2026-09-15-fila-metas-design.md`), todas na `main`.

## O problema

O vendedor só tem "Seus números" na página da fila: hoje e o mês, a posição e
a meta. É o resumo de quem está no salão, e não responde "como foi a minha
semana", "o que eu mais vendo", "por que eu perco venda" nem "onde eu estou
contra os colegas".

A gestão tem esse painel no Início (`/`). O vendedor não chega lá: a raiz o
manda para `/fila` (D-4 da entrega 1), e a página da fila não tem caminho de
volta.

## Decisões

### V1 — O vendedor entra pela fila, e o Início é o painel dele

Ao **entrar**, quem só tem a fila de vendedor (`fila.tela.so_a_fila`) continua
caindo em `/fila`: é o que ele abre para trabalhar. Mas **a raiz deixa de
redirecionar**: `/` passa a ser o painel dele, aberto pelo link "Meu painel" na
página da fila.

O desvio sai da raiz e vai para o login. Deixá-lo na raiz faria o Início
inalcançável para justamente quem ganha o painel.

### V2 — A base pergunta ao negócio para onde mandar depois de entrar

O login é da base (`contas/views.py::entrar`), que redireciona para `/` e não
pode importar a fila (`CLAUDE.md` §3). Um sinal novo,
`contas.entrada.destino_depois_de_entrar`, no molde de
`plataforma.filiais.antes_de_desativar`: a base envia com `request=`, e o
primeiro receptor que responder um caminho interno decide. Sem resposta, `/`.
Vai a requisição, e não a pessoa, porque "só tem a fila" é decidido pelas
permissões do cargo no lugar em que a sessão está, e só
`usuario_da_sessao(request)` as resolve (ajuste P-1 do plano).

Resposta que não é caminho interno (não começa com `/`, ou começa com `//`, ou
traz esquema) é **ignorada**, para o sinal nunca virar redirecionamento aberto.

Rejeitados:
- **marca na sessão** ("acabou de entrar", a raiz redireciona só na primeira
  vez): quem recarrega ou abre `/` em outra aba cai em lugar diferente, e a
  regra fica escondida em estado;
- **configuração em `settings`** apontando para uma função da fila por texto:
  é a base citando o negócio, e `test_camadas_nao_se_invertem.py` não enxerga
  import por texto.

A API (`/api/v1/entrada`) fica fora: o app ainda não existe, e cada produto
decide a entrada dele quando existir.

### V3 — O espelho do painel da gestão, recortado pela pessoa

As mesmas peças (`views_indicadores._painel`, `_listas`, `_filtros`,
`fila/graficos.py`), com todos os números filtrados pelo vendedor. Não é outro
desenho: o vendedor aprende a ler um painel só, e a correção de um vale para
os dois.

### V4 — A loja é a do cabeçalho

Os números são os da filial em que a sessão está (`filial_atual`), a mesma
regra da fila e de "Seus números". O painel não tem campo de loja; para ver
outra, troca-se a filial no cabeçalho. Com "Todas as lojas", o ranking teria
que escolher uma loja ou somar lojas diferentes, e o placar deixaria de ser
claro.

### V5 — O ranking da loja aparece, sem o que é assunto do gerente

O vendedor vê os colegas da loja para estimular a venda (decisão do João,
16/09/2026). Colunas: **posição, vendedor, vendido, vendas, conversão** e
**% da meta** (só em período de mês). Ficam de fora pausa, ticket, "cliente
pediu" e atendimentos: tempo de pausa do colega é conversa do gerente, e não
placar.

**A posição é sempre por vendido**, qualquer que seja a coluna escolhida para
ordenar: reordenar por conversão não pode fazer o vendedor "subir" para o
primeiro lugar. A linha dele vem destacada.

### V6 — Esquecidos ficam fora

O aviso "Ficou aberto de um dia para o outro" é para quem corrige, e o
vendedor não corrige nada. Ele não aparece no painel do vendedor.

## Quem vê o quê no Início

Na ordem, para quem pede `/` com o módulo da fila ligado:

1. tem `fila.relatorios` em alguma loja: **o painel da gestão**, sem mudança;
2. senão, tem `fila.participar` na loja do cabeçalho: **o painel do vendedor**;
3. senão (só `fila.ver`, sem filial no contexto, ou nenhuma permissão da
   fila): **a saudação sozinha** (`nucleo.views.home`).

O Gerente participa da fila e tem `relatorios`: continua com o painel da
gestão, em cuja tabela ele já aparece.

Nenhuma permissão nova: `fila.participar` já é "esta pessoa vende nesta loja",
e é por ela que "Seus números" aparece hoje.

## O painel

De cima para baixo, no Início, abaixo do "Olá, {nome}!":

1. **Filtros**: período por atalho (Hoje, Ontem, 7 dias, Este mês, Mês
   passado) ou intervalo, como na gestão, sem o campo de loja. A ordenação e o
   filtro do ranking viajam junto na querystring, como lá.
2. **Os números**, com a variação contra o período anterior de mesmo tamanho
   (`fila/periodo.py`): atendimentos, vendas, conversão, ticket médio, vendido
   e "cliente pediu", **só dele, só nesta loja**. O cabeçalho do painel diz o
   período e o nome da loja.
3. **O gráfico** por dia (por hora quando o período é um dia), só com os
   atendimentos dele.
4. **A meta dele**, quando o período é um mês inteiro do calendário e ele tem
   meta nesta loja naquele mês: atingido, falta, valor por dia e projeção, pela
   mesma conta de "Seus números" (`fila/metas.py::acompanhar`). Sem meta, a
   faixa não aparece. Em outro período, também não.
5. **As três listas**: vendido por grupo de item, motivos de não venda e tempo
   em pausa por tipo, todas só dele.
6. **O ranking da loja** (V5), com filtro por nome, ordenação e paginação
   (R46).

Um atendimento entra pela hora do fim e aberto não entra, como na gestão.
"Seus números", na página da fila, continua como está.

## As peças

### Base (`contas/`)

- `contas/entrada.py`: o sinal `destino_depois_de_entrar` e uma função
  `destino_depois_de_entrar_para(request) -> str` que envia, descarta resposta
  que não é caminho interno e devolve `/` sem resposta válida.
- `contas/views.py::entrar`: redireciona para o que essa função devolve.

### Fila

- `fila/sinais.py`: `destino_do_vendedor(sender, request, **kwargs)` responde
  `reverse("fila")` quando `tela.so_a_fila(usuario_da_sessao(request))`;
  ligado no `ready()`.
- `fila/views.py::inicio`: sai o redirecionamento; a escolha segue a ordem de
  "Quem vê o quê no Início".
- `fila/indicadores.py`:
  - `por_grupo`, `motivos`, `pausa_por_tipo` e `por_dia` ganham `vendedor=None`,
    como `numeros` já tem. Sem ele, o resultado é o de hoje;
  - `posicoes_por_vendido(recorte) -> dict[int, int]`: a posição de cada
    pessoa pelo vendido, calculada em Python sobre o recorte inteiro. Não é
    `Rank()` na consulta do ranking porque a tabela filtra por nome, e a
    window function rodaria depois do filtro: buscar "Ana" a faria virar a
    primeira (ajuste P-2 do plano). Mesmo vendido, mesma posição (a regra de
    `posicao_no_mes`).
- `fila/views_indicadores.py`: `_painel`, `_listas` e `_filtros` recebem o que
  hoje leem do recorte da gestão (o vendedor, se o campo de loja aparece, se o
  aviso de esquecidos entra), sem duplicar HTML.
- `fila/views_do_vendedor.py` (novo): `inicio_do_vendedor(request, empresa,
  loja, pessoa)` monta a página, com as colunas do ranking do vendedor e a
  linha dele marcada.
- A página da fila ganha **"Meu painel"**, um link para `/`, para quem tem
  `fila.participar` (a `pode_participar` que a tela já calcula). A variável
  `mostra_painel` de `fila/tela.py`, que nenhum template lê, sai: ela diz o
  contrário do que o link precisa (esconderia o painel justamente do
  vendedor).
- As frases novas entram no castelhano (`locale/es`), pela receita do Babel.

### Documentação

- `CLAUDE.md` §10: a nota "quem só tem `fila.ver` e `fila.participar` cai em
  `/fila` ao pedir a raiz" é reescrita para o login, e o painel do vendedor
  ganha a sua subseção. `test_documentacao_nao_mente.py` cobra.

## Erros e bordas

- **Sem filial no contexto** (pessoa sem alocação em loja): a saudação, e não
  500.
- **Loja forjada na sessão**: já cai na primeira filial permitida
  (`plataforma.contexto`); o painel usa a que ficou.
- **Período sem atendimento**: os números saem "—" onde a conta não existe
  (conversão, ticket), zero onde existe; o ranking vazio mostra a frase de
  lista vazia do design system.
- **O vendedor não fechou atendimento no período**: ele não aparece no
  ranking (o ranking lista quem fechou atendimento como vendedor), e o painel
  diz isso acima da tabela em vez de destacar uma linha que não existe. Quem
  atendeu e não vendeu aparece, com vendido zero.
- **Personificação**: o MW5 "vendo como" um vendedor vê o painel dele, com o
  aviso de toda tela (`test_personificacao.py`).
- **Destino do sinal inválido**: ignorado, cai em `/`.

## Testes

Cada um visto vermelho com o código quebrado de propósito antes de passar.

- **Login:** o vendedor vai para `/fila`; gerente, supervisor e titular vão
  para `/`. Um receptor que responde `https://fora` ou `//fora` é ignorado.
  Sem receptor, `/`.
- **Raiz:** o vendedor em `/` recebe 200 com o painel dele, e não 302.
- **Só dele:** outro vendedor, na mesma loja e no mesmo período, não entra nos
  números, no gráfico nem nas três listas.
- **Só a loja do cabeçalho:** o atendimento do mesmo vendedor em outra loja
  não entra; trocar a filial troca os números.
- **Ranking:** as colunas não trazem pausa, ticket, "cliente pediu" nem
  atendimentos; a posição é por vendido mesmo ordenado por conversão; empate
  de vendido dá a mesma posição; a linha do vendedor vem marcada;
  `test_regra_tabela.py` passa.
- **Meta:** aparece só em período de mês e só com meta cadastrada para ele
  nesta loja; a meta da loja não aparece como se fosse dele.
- **Gestão intacta:** os testes de indicadores existentes passam sem mudança;
  `por_grupo`, `motivos`, `pausa_por_tipo` e `por_dia` sem `vendedor=`
  devolvem o mesmo que antes.
- **Quem não participa:** só com `fila.ver`, a saudação.
- **Sem filial:** a saudação, e não 500.
- **Página da fila:** "Meu painel" aparece para quem participa e não aparece
  para quem só vê.
- **Camadas:** `test_camadas_nao_se_invertem.py` continua passando (a base não
  importa a fila).
