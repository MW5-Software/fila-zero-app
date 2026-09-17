# Fila Zero — as correções do gerente, com observação e histórico

**Data:** 17/09/2026
**Estado:** implementado (plano `2026-09-17-fila-correcoes-do-gerente.md`).
**Depende de:** a fila (`2026-09-15-fila-da-vez-design.md`, D7 e o desvio D-3
do plano), os indicadores (`2026-09-15-fila-indicadores-design.md`, os
atalhos de período) e a loja do cabeçalho no painel (commit `881ec60`).

## O problema

O gerente já corrige a fila da loja dele pela folha **Corrigir**
(`fila/correcoes.py`): fecha o atendimento no lugar do vendedor, tira da loja
quem esqueceu de sair e tira da pausa. Faltam três coisas que o cliente pediu:

1. **mover alguém de posição** na fila (o vendedor que chegou e esqueceu de
   bater o ponto, o que foi passado para trás por engano);
2. **pôr alguém em pausa** (o vendedor foi ao banco e não apertou "Pausa");
3. **dizer por quê**, e isso ficar num **histórico** que o gerente consulta
   depois. Hoje a correção só deixa rastro na auditoria, que diz o que foi
   feito, mas não o motivo, e que ninguém da loja abre.

## Decisões

### C1 — Toda correção pede observação, e ela é obrigatória

Mover, pôr em pausa, tirar da pausa, fechar atendimento, tirar da loja e
editar lançamento pedem uma observação curta ("foi ao banco", "chegou antes
e esqueceu o ponto"). Sem ela a ação não acontece e a folha diz "Escreva o
motivo da correção.".

Obrigatória, e não opcional (escolha do cliente): um histórico em que metade
das linhas não diz o porquê não serve para a conversa que o gerente vai ter
com o vendedor. O custo é um campo a mais na folha, que já é um passo
deliberado.

A observação tem de 3 a 200 caracteres depois de tirar os espaços das pontas.
Três caracteres barram o "." e o "a" digitados só para passar; duzentos
cabem numa linha da tabela e numa folha de celular.

A observação é texto do gerente e **não é traduzida** (`CLAUDE.md` §8: dado
cadastrado não se traduz).

### C2 — Uma tabela própria para o histórico, além da auditoria

`fila.CorrecaoNaFila` (herda `contas.inquilino.ModeloDaEmpresa`): uma linha
por correção.

| coluna | o quê |
|---|---|
| `filial` | a loja (`PROTECT`, como as outras tabelas da fila) |
| `pessoa` | quem foi corrigido |
| `autor` | quem corrigiu, como a ação o recebe (em "ver como", a pessoa vista; quem agiu de verdade fica na auditoria, que já anota a personificação) |
| `acao` | `mover`, `pausar`, `tirar_pausa`, `fechar`, `tirar`, `editar` |
| `observacao` | o motivo, até 200 caracteres |
| `detalhe` | o que mudou, escrito pelo sistema ("de 5º para 1º", "Almoço", "Vendeu R$ 1.500,00") |
| `momento` | a hora da correção, pelo relógio das ações (`acoes._agora()`) |

Índices: `(filial, momento)` para a tela, que filtra por loja e período.

**Por que não só a auditoria.** A auditoria (`RegistroDeAuditoria`) continua
recebendo a correção, com a observação no `detalhe`, na mesma transação. Mas
ela não tem a loja nem o vendedor como coluna: filtrar "as correções do Caio
no Centro" viraria busca em texto, e a tela ficaria presa ao formato de uma
frase. O histórico é dado do negócio, que o gerente lê; a auditoria é rastro
técnico, que a MW5 lê.

`pessoa` e `autor` são FK para o usuário com `related_name="+"`, como
`Atendimento.vendedor`: ninguém atravessa do usuário para o histórico sem
passar pela empresa.

### C3 — Mover de posição escolhendo o lugar

A folha lista a fila como está e oferece "1º, 2º, … último", com a posição
atual marcada e desabilitada. Um toque leva a pessoa a qualquer lugar.

A ordem da fila é `na_fila_desde` (entrega 1): não há número de posição
guardado. Mover é **gravar em `na_fila_desde` um instante entre os dois
vizinhos do lugar escolhido**:

- para o 1º, um microssegundo antes do atual primeiro;
- para o último, um microssegundo depois do atual último;
- no meio, o ponto médio entre o anterior e o seguinte.

Se não houver microssegundo livre entre os vizinhos (dois instantes iguais
ou colados), a ação reescreve `na_fila_desde` de toda a fila da loja com um
microssegundo entre cada um, mantendo a ordem, e então encaixa a pessoa.
Tudo dentro da trava da linha da filial que as ações já usam
(`acoes._travar`), relendo a fila depois da trava.

Só quem está `na_fila` se move. Posição fora de 1…N, ou a posição em que a
pessoa já está, recusa com frase.

Quem volta ao fim depois (atender, voltar da pausa) grava a hora de agora,
como sempre: mover não cria uma segunda regra de ordem.

### C4 — Pôr em pausa pelo gerente

Só quem está `na_fila`: quem está atendendo precisa ter o atendimento fechado
antes, e a folha de Corrigir já oferece isso. O gerente escolhe um tipo de
pausa ativo, e a ação faz o mesmo que o "Pausa" do vendedor
(`acoes.pausar`): abre a `Pausa` e muda o lugar para `em_pausa`. O detalhe do
histórico é o nome do tipo.

### C5 — A tela "Histórico da fila"

`/fila/historico`, guardada por `fila.gerenciar` e pelo módulo `fila`.

- **Lojas:** as que o cargo alcança com `fila.gerenciar`
  (`indicadores.lojas_com_permissao`). Abre na loja do cabeçalho; "Todas as
  lojas" existe para quem alcança mais de uma, como no painel.
- **Período:** os mesmos atalhos do painel (`fila.periodo.ATALHOS`), abrindo
  em "Hoje".
- **Tabela (R46):** data e hora, loja, vendedor, ação, observação e quem fez,
  ordenável por data, loja, vendedor, ação e autor; filtro por vendedor,
  ação e observação; paginação. Padrão: mais recente primeiro.
- **Entrada:** item "Histórico da fila" no menu do módulo (grupo da Fila da
  vez), e um link "Histórico" na página da fila para quem tem
  `fila.gerenciar`.

O vendedor não vê o histórico, nem o dele: a observação é conversa da gestão
(escolha do cliente para esta entrega).

## As peças

### `fila/models.py` e migração

`CorrecaoNaFila` (C2), com `TextChoices` para `acao`. Migração só de
esquema: a tabela nasce vazia, e as correções antigas continuam só na
auditoria.

### `fila/correcoes.py`

- `ler_observacao(texto) -> str`: tira as pontas e recusa (`Recusa`) fora de
  3…200.
- `mover(autor, filial, pessoa_id, posicao, *, observacao, request=None)`.
- `por_em_pausa(autor, filial, pessoa_id, tipo_id, *, observacao, request=None)`
  (não `pausar`, para não confundir com `acoes.pausar`; as duas usam o mesmo
  miolo, `acoes._abrir_pausa`).
- `tirar_da_loja`, `fechar_atendimento`, `tirar_da_pausa` e
  `editar_lancamento` ganham `observacao` obrigatória, só por nome.
- `_registrar(autor, lugar_ou_atendimento, acao, observacao, detalhe,
  request)`: grava `CorrecaoNaFila` e a auditoria juntas.
- A observação é lida e validada **antes** da trava: recusa barata não
  segura a fila da loja.

### `fila/estado.py`

`versao_da_fila` passa a contar as correções da loja (quantas e a última):
mover grava um instante ENTRE os vizinhos, que não muda o maior
`na_fila_desde` nem o maior `desde`, e as outras telas não veriam a nova
ordem.

### `comum/auditoria.py`

Duas ações novas: `FILA_POSICAO_MOVIDA` e `FILA_PAUSA_INICIADA`, com rótulo.

### `fila/views.py` (`POST /fila/agir`)

`acao=mover` (lê `pessoa`, `posicao`, `motivo_da_correcao`) e
`acao=por_em_pausa` (lê `pessoa`, `tipo`, `motivo_da_correcao`), com
`id_do_post` para os ids, como as outras. As ações de correção existentes
passam a ler `motivo_da_correcao`.

O campo se chama `motivo_da_correcao`, e não `observacao`: `observacao` já é
o campo opcional da não venda na mesma folha de fechar, e os dois iriam
juntos no POST.

### `fila/templates/fila/_folhas.html` e `fila/tela.py`

- Na folha **Corrigir**, para quem está na fila: **Mover de posição** e
  **Pôr em pausa**, cada um abrindo a própria folha (`?folha=mover`,
  `?folha=por_em_pausa`), que funciona sem JavaScript como as de hoje.
- Um macro `observacao()` com o campo obrigatório (`required`,
  `maxlength=200`), usado em toda folha de correção.
- A folha de mover recebe a fila (`r.fila`) e a posição atual do alvo.
- Link "Histórico" no topo da página, ao lado de "Meu painel", para quem tem
  `fila.gerenciar`.

### `fila/views_historico.py`, `fila/urls.py`, `fila/modulo.py`

A tela C5, montada com `comum.listagem.montar_pagina`, e o atalho no menu.

### Castelhano

As frases novas da moldura entram no `django.po`. A observação não.

### Documentação

`CLAUDE.md` §10, "Onde mora cada regra" e "O que custa esquecer": a
observação obrigatória, a tabela do histórico e o mover por instante entre
vizinhos.

## Erros e bordas

| caso | resposta |
|---|---|
| observação vazia, só espaços ou com menos de 3 caracteres | "Escreva o motivo da correção." |
| observação com mais de 200 caracteres | "O motivo cabe em 200 caracteres." |
| mover quem não está na fila | "Essa pessoa não está na fila." |
| posição fora de 1…N, ou não numérica | "Escolha uma posição da fila." |
| posição igual à atual | "Essa pessoa já está nessa posição." |
| pôr em pausa quem atende ou já está em pausa | "Essa pessoa não está na fila." |
| tipo de pausa inativo, de outra empresa ou forjado | "Escolha o tipo de pausa." |
| corrigir a si mesmo | "Você não corrige a si mesmo." (já existe) |
| pessoa de outra loja | a recusa que já existe (`NAO_ENCONTRADO`) |
| dois gerentes movendo ao mesmo tempo, ou mover enquanto o vendedor toca "Vou atender" | a trava da filial serializa; a segunda ação relê a fila e age sobre o estado novo, ou recusa |
| histórico com `?loja=` forjada | cai na loja do cabeçalho, como o painel |

## Testes

- **Regras (`tests/test_fila_correcoes.py`):**
  - mover para o 1º, para o meio e para o último, e a ordem resultante;
  - mover com vizinhos no mesmo instante (reescreve e encaixa);
  - posição inválida, a atual e quem não está na fila;
  - pôr em pausa: abre a pausa, recusa quem atende e o tipo inativo;
  - observação vazia e longa demais recusam **todas** as correções, sem
    mexer na fila;
  - toda correção grava uma linha de `CorrecaoNaFila` e uma da auditoria, com
    a observação;
  - ninguém corrige a si mesmo nem pessoa de outra loja (continua).
- **Concorrência (`tests/test_fila_concorrencia.py`):** mover e "Vou atender"
  ao mesmo tempo, com a demora forçada entre ler e gravar, no mesmo molde dos
  testes que já existem.
- **Página (`tests/test_fila_pagina.py`):** as folhas de mover e de pôr em
  pausa abrem sem JavaScript e têm o campo de observação obrigatório; o POST
  sem observação volta com a frase; o link "Histórico" só para a gestão.
- **Tela (`tests/test_fila_historico.py`):** o gerente vê só a loja dele; a
  loja forjada cai na do cabeçalho; "Todas as lojas" para o supervisor; os
  filtros; o vendedor toma 404.
- **Varreduras:** guarda, módulo, tabela (R46), personificação, inquilino,
  `conta_guid` e GUID passam com a rota e a tabela novas, sem isenção.
