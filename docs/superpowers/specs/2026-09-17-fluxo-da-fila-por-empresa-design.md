# Fila Zero — o fluxo da fila por empresa

**Data:** 17/09/2026
**Estado:** desenho aprovado na conversa de 17/09/2026; falta o plano.
**Depende de:** a fila (`2026-09-15-fila-da-vez-design.md`), as correções do
gerente (`2026-09-17-fila-correcoes-do-gerente-design.md`) e várias empresas
por conta (`2026-09-17-varias-empresas-por-conta-design.md`).

## O problema

A fila tem UM fluxo, escrito no código: quem lança o atendimento volta
automaticamente para o fim da fila. É o fluxo da Sylvia, e funciona lá.

Há lojas que trabalham de outro jeito: quem termina o atendimento **sai da
fila** e só volta a ela quando quiser — arruma o showroom, atende um telefone,
respira — e aí se recoloca no fim. Hoje isso não existe, e a única forma de
imitar seria bater o ponto de novo (que encerra a presença) ou entrar em pausa
(que é outra coisa, e conta como pausa nos indicadores).

Esse é o caso de "particularidade de cliente" que a casa resolve com uma das
quatro alavancas (`CLAUDE.md` §2), e não com `if cliente == "..."`.

## Decisões

### F1 — A escolha é da EMPRESA, e vale para as lojas dela

Campo novo em `plataforma.Empresa`:

| valor | o que acontece depois de lançar |
|---|---|
| `volta_para_a_fila` (padrão) | a pessoa volta ao fim da fila, como hoje |
| `espera` | a pessoa fica **em espera**, fora da fila, e entra quando quiser |

**Na empresa, e não na loja** (escolha do cliente): a rede trabalha do mesmo
jeito nas lojas dela, e um campo por loja seria a mesma resposta repetida em
cada uma — com a chance de duas lojas da mesma rede divergirem por
esquecimento. Quem edita é quem já edita a empresa (titular e MW5).

**O padrão é o fluxo de hoje.** Toda instalação que já existe continua igual
sem ninguém tocar em nada, e é isso que mantém a Sylvia funcionando.

### F2 — "Em espera" é um estado da fila, e não uma pausa

`fila.Estado` ganha `EM_ESPERA`. Quem está em espera:

- **continua com o ponto aberto** e aparece na tela, num bloco próprio;
- **não está na fila**: não é chamado, não tem posição;
- **não está em pausa**: o tempo em espera NÃO entra no tempo de pausa dos
  indicadores, e não existe `Pausa` aberta. Pausa continua sendo um ato
  deliberado, com tipo escolhido.

Uma `Pausa` com tipo "Espera" resolveria com menos código e mentiria no
relatório: o gerente que olha "tempo em pausa" veria o trabalho normal da loja
somado ao almoço.

### F3 — O que leva à espera, e o que tira dela

No fluxo `espera`:

- **lançar o atendimento** leva à espera — inclusive quando quem lança é o
  gerente pela folha de correção ("Fechar atendimento");
- **encerrar a pausa** leva à espera, e o botão passa a dizer "Encerrar
  pausa" em vez de "Voltar para a fila";
- **bater o ponto continua entrando na fila** (escolha do cliente): chegar na
  loja é dizer que está disponível;
- **"Entrar na fila"** é o botão de quem está em espera. Entra no FIM, com a
  hora de agora — a mesma regra de sempre, sem posição guardada.

No fluxo `volta_para_a_fila` nada muda: não há espera, e o estado nunca
aparece.

**O gerente tirando alguém da pausa manda para a FILA nos dois fluxos**, de
propósito: a ação é dele, e ele está decidindo que a pessoa atende agora. Se
ele quiser deixá-la fora da fila, tira da pausa e não a chama — ou usa a
correção de posição.

### F4 — O gerente e quem está em espera

Na folha **Corrigir**, quem está em espera ganha **"Pôr na fila"** (entra no
fim), e continua podendo ser **posto em pausa** e **tirado da loja**. Tudo com
o motivo obrigatório e gravado em `CorrecaoNaFila`, como as outras correções
(spec de 17/09/2026).

Mover de posição continua sendo só para quem está na fila: quem está em espera
não tem posição para mudar.

### F5 — A tela

- Um bloco **"Em espera"** ao lado de "Em pausa", com rótulo e ícone próprios
  — todo estado da fila tem os dois (regra da entrega 1).
- Para quem está em espera, o cartão de cima diz **"Você está em espera"** e o
  botão principal é **"Entrar na fila"**.
- **Funciona sem JavaScript**, como o resto da página: o botão é um POST.
- A versão da fila já muda (o `desde` do lugar), então as outras telas se
  atualizam sozinhas.

### F6 — Os indicadores não mudam

Nenhuma conta muda: a espera não é pausa, não é atendimento e não é venda.
Quem ficou em espera de um dia para o outro continua aparecendo no aviso de
"ficou aberto de um dia para o outro", pela presença aberta.

## As peças

- `plataforma/models.py`: `Empresa.fluxo_da_fila` (`TextChoices`, padrão
  `volta_para_a_fila`) e a migração de esquema.
- `plataforma/views_empresa.py`: o campo na tela de Empresas, com a frase que
  explica os dois fluxos.
- `fila/models.py`: `Estado.EM_ESPERA`.
- `fila/acoes.py`: `_depois_do_atendimento(lugar, filial, agora)` decide entre
  voltar ao fim e ir para a espera; `finalizar` e `voltar_para_a_fila` passam
  por ela; `entrar_na_fila(pessoa, filial)` é a ação nova.
- `fila/correcoes.py`: `por_na_fila(autor, filial, pessoa_id, *, observacao)`;
  `fechar_atendimento` segue o fluxo da empresa; `por_em_pausa` aceita quem
  está em espera.
- `fila/views.py`: `acao=entrar_na_fila` (vendedor) e `acao=por_na_fila`
  (gerente).
- `fila/estado.py`, `fila/tela.py`, `fila/templates/fila/`: o bloco, o cartão
  e o botão.
- `comum/auditoria.py`: `FILA_POSTO_NA_FILA`, com rótulo e cenário.
- Castelhano e `CLAUDE.md` §10.

## Erros e bordas

| caso | resposta |
|---|---|
| "Entrar na fila" de quem já está na fila | "Você já está na fila." |
| "Entrar na fila" de quem está atendendo | "Finalize o atendimento primeiro." |
| "Entrar na fila" na empresa de fluxo A | a ação não existe na tela, e o POST recusa: não há espera nesse fluxo |
| gerente põe na fila quem já está na fila | "Essa pessoa já está na fila." |
| gerente move de posição quem está em espera | "Essa pessoa não está na fila." (a recusa que já existe) |
| a empresa troca de fluxo com gente em espera | quem está em espera continua em espera e usa "Entrar na fila"; ninguém é movido pela troca |
| dois toques em "Entrar na fila" | a trava da loja serializa, e o segundo recebe "Você já está na fila." |

## Testes

- **Fluxo A (o de hoje) continua idêntico**: lançar volta ao fim, encerrar a
  pausa volta ao fim, e o estado `em_espera` nunca aparece. É o teste que
  impede a regressão da Sylvia.
- **Fluxo B**: lançar leva à espera; "Entrar na fila" põe no fim; encerrar a
  pausa leva à espera; o gerente fechando o atendimento também leva à espera.
- **A espera não é pausa**: nenhuma `Pausa` é criada, e o tempo em espera não
  aparece no "tempo em pausa" dos indicadores.
- **O gerente**: "Pôr na fila" com motivo grava a correção e o histórico;
  mover de posição continua recusando quem está em espera.
- **A tela**: o bloco e o botão aparecem no fluxo B e não no A; o POST
  funciona sem JavaScript.
- **A empresa**: o campo grava, o padrão é o fluxo de hoje, e a troca não
  mexe em quem já está na fila.
- **Varreduras**: guarda, módulo, personificação, tabela, inquilino e
  `conta_guid` continuam passando sem isenção nova.
