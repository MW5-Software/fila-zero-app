# Fila Zero — a fila da vez das lojas

**Data:** 15/09/2026
**Estado:** desenho aprovado, execução não começou.
**Entrega:** 1 de 2 — a fila. O dashboard (atendimentos, vendas, ranking,
metas) é a entrega 2, com spec próprio.

## O problema

A Sylvia Design tem a matriz e várias lojas, e cada loja tem os seus
vendedores. A ordem de atendimento no salão é a **fila da vez**: quem chega
entra no fim, o primeiro atende o próximo cliente, e quem termina volta para o
fim. Hoje essa fila não deixa rastro: não se sabe quantos clientes cada um
atendeu, quantos compraram, o que foi vendido, por que os outros não compraram
e quanto tempo cada vendedor ficou disponível.

O Fila Zero põe a fila na tela de cada vendedor, no navegador ou no celular, e
grava cada passo. A entrega 1 é a fila e os lançamentos; a entrega 2 lê o que
ela gravou.

## Sobre a base

O projeto nasceu da KRONOS base (`PROVENIENCIA.md`). O que a fila precisa de
estrutura já existe lá:

- **Conta:** Sylvia (titular).
- **Empresa:** Sylvia Design.
- **Lojas:** as filiais da empresa. A Matriz nasce com a empresa; a Sylvia
  cadastra as outras na tela de Filiais.
- **Vendedores:** pessoas da conta, cada uma **alocada** na loja dela com um
  **cargo**. A permissão vem do cargo da alocação no lugar em que a pessoa está
  (`contas/lugar.py`).
- **Login:** cada vendedor entra com a própria conta, no navegador ou no
  celular. Não há aparelho compartilhado.

## Decisões

### D1 — Bater o ponto é presença na fila, não controle de jornada

O ponto marca que a pessoa chegou na loja e a põe na fila; sair da loja fecha a
presença. Serve para medir tempo disponível. Não substitui o controle de
jornada da empresa e não tem relatório de horas.

### D2 — Saiu da fila, volta para o fim

Depois de um atendimento, com ou sem venda, e depois de uma pausa de qualquer
tipo, a pessoa volta para o **fim** da fila. Não existe "guardar a posição".

### D3 — O primeiro atende; o cliente pode pedir um vendedor

Só o primeiro da fila tem **Vou atender**. Qualquer pessoa na fila tem
**Cliente pediu por mim**, que abre um atendimento fora da vez marcado
`cliente_pediu`, para o dashboard não tratar como vez furada. Quem estava em
primeiro continua em primeiro.

### D4 — Venda com vários grupos, cada um com o seu valor

O atendimento que virou venda tem uma ou mais linhas de grupo de item e valor.
O total é a soma. O dashboard sabe quanto se vendeu de cada grupo, mesmo quando
o cliente leva sofá e tapete juntos.

### D5 — Não venda com um motivo

O atendimento sem venda tem **um** motivo, escolhido de uma lista cadastrada
pela Sylvia Design, e uma observação opcional.

### D6 — Pausa com tipo

Sair para pausa pede o tipo (banheiro, almoço, café...), de uma lista cadastrada
pela Sylvia Design. O dashboard mede o tempo em cada tipo.

### D7 — O gerente corrige a loja dele

O gerente corrige a fila e os lançamentos da loja dele: tirar da loja quem
esqueceu de sair, fechar atendimento aberto, tirar da pausa, corrigir grupo,
valor ou motivo. Supervisor e titular corrigem em qualquer loja. Toda correção
vai para a auditoria. **Não existe fechamento automático** no fim do dia.

### D8 — Atualização por consulta periódica

A tela pergunta ao servidor a cada 3 segundos como está a fila e só redesenha
quando algo mudou. Roda com o que a base já tem (Django + gunicorn), sem Redis
nem servidor ASGI em cada VPS, e aguenta celular que perde sinal. Rejeitados:
WebSocket (infraestrutura nova por instalação para ganhar poucos segundos) e
Server-Sent Events (uma conexão aberta por vendedor esgota os workers síncronos
do gunicorn).

### D9 — A vez é decidida no servidor, sob trava

Toda ação que mexe na fila tranca a fila da loja no banco durante a gravação e
confere o estado de novo antes de gravar. Dois "Vou atender" ao mesmo tempo
resultam em um atendimento e uma recusa ("a vez já foi"), nunca em dois.

## Permissões e cargos

O módulo é o app `fila/`, declarado como `ModuloSpec` com `ativo_por_padrao=True`
(é o produto; uma instalação do Fila Zero sem a fila não serve para nada).

| permissão | o que abre |
|---|---|
| `fila.participar` | bater o ponto, entrar e sair da fila, atender, lançar o resultado, pausar |
| `fila.gerenciar` | as correções de D7 na loja do alcance do cargo |
| `fila.cadastros` | as telas de grupos de item, motivos de não venda e tipos de pausa |

Cargos de fábrica (`contas/cargos_de_fabrica.py`) e titular (`contas/fabrica.py`):

| quem | alcance | permissões da fila (além das da base) |
|---|---|---|
| Vendedor | a filial | `fila.participar` |
| Gerente | a filial | `fila.participar`, `fila.gerenciar` |
| Supervisor | a empresa | `fila.gerenciar` |
| Representante | a filial | nenhuma |
| Cliente | os próprios | nenhuma |
| Titular | a conta | `fila.participar`, `fila.gerenciar`, `fila.cadastros` |

A Sylvia ajusta qualquer cargo depois, na tela de Cargos. A MW5 (MASTER) leva o
coringa `fila.*`.

**Regras de lugar:**

- A fila é a da **loja em que a pessoa está** (`filial_atual`). Quem está
  alocado em mais de uma loja escolhe no seletor do cabeçalho.
- **Uma presença aberta por pessoa.** Bater o ponto numa loja com presença
  aberta em outra fecha a outra (e tira a pessoa daquela fila) antes de abrir a
  nova. Se ela estiver **atendendo** na outra loja, o ponto é recusado até
  finalizar.
- O gerente corrige onde o alcance do cargo dele chega: a filial. Supervisor e
  titular, a empresa.

## O modelo de dados

Todo model herda `contas.inquilino.ModeloDaEmpresa` (empresa + `conta_guid`,
manager que falha vazio) e `ComGuid`.

### Cadastros

`GrupoDeItem`, `MotivoDeNaoVenda`, `TipoDePausa` — os três com:

| campo | o que é |
|---|---|
| `nome` | o que a tela mostra; único por empresa, sem diferença de caixa |
| `ordem` | a ordem nas opções |
| `ativo` | desativado some das opções e continua no histórico |

**Cadastro usado não se apaga, desativa.** A FK dos lançamentos é `PROTECT`, e a
tela diz "em uso, desative em vez de remover" em vez de estourar.

### O que acontece na loja

**`Presenca`** — o ponto.

| campo | o que é |
|---|---|
| `pessoa` | FK `Usuario` |
| `filial` | FK `Filial` (a loja) |
| `entrada` | quando bateu o ponto |
| `saida` | quando saiu; nula enquanto está na loja |
| `fechada_por` | FK `Usuario`, nula; preenchida quando quem fechou foi o gerente |

Restrição parcial: uma presença com `saida` nula por pessoa.

**`LugarNaFila`** — o estado de AGORA, uma linha por pessoa presente.

| campo | o que é |
|---|---|
| `pessoa` | FK `Usuario`, **única** |
| `filial` | FK `Filial` |
| `presenca` | FK `Presenca` |
| `estado` | `na_fila` / `atendendo` / `em_pausa` |
| `na_fila_desde` | quando entrou (ou voltou) para a fila — **é a ordem da fila** |
| `desde` | quando entrou no estado atual (para "há quanto tempo") |

**A ordem da fila é `na_fila_desde` crescente, entre quem está `na_fila`.** O
primeiro é o de menor `na_fila_desde`. Voltar para o fim é gravar a hora de
agora. A linha nasce no ponto e some quando a pessoa sai da loja.

Separado do histórico de propósito: a consulta de 3 em 3 segundos lê só esta
tabela — poucas linhas por loja, sempre rápidas.

**`Atendimento`**

| campo | o que é |
|---|---|
| `filial`, `vendedor` | a loja e quem atendeu |
| `presenca` | FK `Presenca` |
| `inicio`, `fim` | `fim` nulo enquanto aberto |
| `cliente_pediu` | abriu por "Cliente pediu por mim" (D3) |
| `resultado` | `vendeu` / `nao_vendeu`; vazio enquanto aberto |
| `motivo` | FK `MotivoDeNaoVenda`, `PROTECT`, só em não venda |
| `observacao` | texto curto opcional, só em não venda |
| `total` | decimal; soma dos itens em venda, zero em não venda |
| `fechado_por` | FK `Usuario`, nula; preenchida quando o gerente fechou |

Restrição parcial: um atendimento com `fim` nulo por vendedor.

**`ItemVendido`**

| campo | o que é |
|---|---|
| `atendimento` | FK `Atendimento`, `CASCADE` |
| `grupo` | FK `GrupoDeItem`, `PROTECT` |
| `valor` | decimal maior que zero |

**`Pausa`**

| campo | o que é |
|---|---|
| `pessoa`, `filial`, `presenca` | quem, onde, em qual presença |
| `tipo` | FK `TipoDePausa`, `PROTECT` |
| `inicio`, `fim` | `fim` nulo enquanto em pausa |

Restrição parcial: uma pausa com `fim` nulo por pessoa.

### Regras de gravação

- **Venda:** pelo menos um `ItemVendido`, todo valor > 0, grupos ativos no
  momento do lançamento, e `total` = soma. Sem motivo.
- **Não venda:** motivo ativo obrigatório, nenhum item, `total` = 0.
- **Fechado não reabre.** Atendimento, pausa e presença com fim gravado não
  voltam a abrir. Correção muda o que foi lançado (grupos, valores, motivo,
  observação), nunca reabre, e grava `ACOES` na auditoria com o antes e o
  depois no detalhe.
- As restrições de "um aberto por pessoa" são do banco (restrições parciais),
  não só da tela.

## As transições

Cada ação é uma função em `fila/acoes.py`, chamada pela view, que:

1. abre transação e tranca as linhas de `LugarNaFila` da loja
   (`select_for_update`);
2. relê o estado da pessoa e confere se a ação cabe;
3. grava tudo ou nada;
4. devolve o estado novo, ou uma recusa com a frase para a tela.

| ação | de → para | o que grava |
|---|---|---|
| bater o ponto | fora → `na_fila` | `Presenca` aberta; `LugarNaFila` com `na_fila_desde` = agora. Fecha presença aberta em outra loja (ver "Regras de lugar") |
| vou atender | `na_fila` e primeiro → `atendendo` | `Atendimento` aberto, `cliente_pediu=False` |
| cliente pediu por mim | `na_fila` → `atendendo` | `Atendimento` aberto, `cliente_pediu=True` |
| finalizar | `atendendo` → `na_fila` | fecha o atendimento com resultado; `na_fila_desde` = agora |
| pausa | `na_fila` → `em_pausa` | `Pausa` aberta com tipo |
| voltar para a fila | `em_pausa` → `na_fila` | fecha a pausa; `na_fila_desde` = agora |
| sair da loja | `na_fila` ou `em_pausa` → fora | fecha pausa aberta e presença; apaga `LugarNaFila`. Recusado se `atendendo` |

**Correções do gerente** (`fila.gerenciar`, loja no alcance):

| correção | o que faz |
|---|---|
| tirar da loja | fecha pausa e presença da pessoa, com `fechada_por`; se estiver atendendo, fecha o atendimento como não venda com o motivo que o gerente escolher |
| fechar atendimento | lança o resultado no lugar do vendedor, com `fechado_por`; a pessoa volta para o fim da fila |
| tirar da pausa | fecha a pausa; a pessoa volta para o fim da fila |
| editar lançamento | troca grupos e valores de uma venda, ou motivo e observação de uma não venda, de um atendimento FECHADO da loja |

Vendedor nunca corrige ninguém, nem a si mesmo depois de fechado.

## As telas

### `/fila` — fora do dashboard

Página própria, sem menu lateral, pensada primeiro para o celular. Usa o design
system (`nucleo`) com um layout enxuto: topo com a loja, o nome e o estado da
pessoa; embaixo a fila.

- **Quem tem só `fila.participar`** cai em `/fila` depois do login.
- **Quem tem também acesso ao dashboard** cai no dashboard como hoje, e tem um
  link para `/fila` no menu (e de volta, na página da fila).
- **Sem loja** (pessoa sem filial alcançável): a página diz que falta ser
  alocada numa loja, em vez de mostrar uma fila vazia.

A lista mostra, em ordem: quem está atendendo (com há quanto tempo), a fila (com
posição e há quanto tempo espera), e quem está em pausa (com o tipo e há quanto
tempo). A própria pessoa aparece destacada.

Os botões dependem do estado (tabela de transições). **Finalizar** abre o
fechamento: "Vendeu" com linhas de grupo e valor e "+ outro grupo", mostrando o
total somado; "Não vendeu" com a lista de motivos e a observação. **Pausa** abre
a escolha do tipo.

**Atualização (D8):** um endpoint `GET /fila/estado` devolve JSON com a versão
da fila da loja e o conteúdo. A versão muda a cada gravação na fila daquela loja
(o maior `desde`/`na_fila_desde` mais o número de linhas basta; não precisa de
tabela nova). A página consulta a cada 3 segundos e só redesenha quando a versão
mudou. As ações são POST com CSRF, e a resposta de cada uma já traz o estado
novo, para quem agiu não esperar a próxima consulta.

**O gerente** vê, em cada pessoa, o menu de correção, e uma aba "Lançamentos de
hoje" com os atendimentos fechados da loja no dia e **Editar** em cada um.

### Cadastros — no dashboard

Três telas no grupo Cadastro (`fila.cadastros`): Grupos de item, Motivos de não
venda, Tipos de pausa. Padrão da casa: filtro, ordenação e paginação (R46),
criar/editar em modal, desativar/ativar, remover só o que nunca foi usado.

### Auditoria

Entram em `comum.auditoria.ACOES`, cada uma com cenário em
`tests/test_auditoria.py`: `FILA_PESSOA_TIRADA`, `FILA_ATENDIMENTO_FECHADO`,
`FILA_PAUSA_ENCERRADA`, `FILA_LANCAMENTO_CORRIGIDO` (as correções) e
`FILA_CADASTRO_CRIADO/EDITADO/REMOVIDO` (os três cadastros, com o nome do
cadastro no alvo). As ações do próprio vendedor **não** vão para a auditoria: já
são o histórico da fila, e uma linha de trilha por clique afogaria o que a
auditoria existe para mostrar.

## Identidade do produto

Parte desta entrega, pelo roteiro do `CLAUDE.md` da base:

- `MARCA_PADRAO`: "Fila Zero".
- `pyproject.toml`: `fila-zero`; imagem `ghcr.io/mw5-software/fila-zero` no
  workflow e no `deploy/`.
- Portas próprias no `docker-compose.yml`: banco `127.0.0.1:5436`, app `8005`.
- Pastas do app `fila/` nas varreduras que listam pastas.
- `CLAUDE.md` passa a descrever o Fila Zero (a base continua descrita, e o
  negócio entra numa seção própria).

## Como se prova

Cada trava é testada e quebrada de propósito uma vez antes de valer:

- **A ordem:** quem bate o ponto entra no fim; finalizar e voltar da pausa
  mandam para o fim.
- **A vez:** só o primeiro tem "Vou atender" aceito; "Cliente pediu" funciona
  fora da vez e não mexe no primeiro.
- **Concorrência:** duas chamadas simultâneas de "Vou atender" (teste
  transacional com duas conexões) resultam em um atendimento e uma recusa.
- **Tela velha:** "Vou atender" de quem já não é o primeiro é recusado.
- **Venda:** sem item, com valor zero ou negativo, com grupo desativado ou de
  outra empresa — recusado. Total = soma.
- **Não venda:** sem motivo, com motivo desativado ou de outra empresa —
  recusado.
- **Lugar:** ponto numa loja fecha a presença em outra; recusado se atendendo;
  sair da loja recusado se atendendo.
- **Um aberto por pessoa:** a restrição parcial do banco dá `IntegrityError` na
  duplicata gravada por fora da tela.
- **Permissões:** vendedor não corrige; gerente não corrige fora da loja dele;
  supervisor corrige na empresa; sem `fila.participar` a página responde 404.
- **Isolamento:** id de loja, atendimento, grupo ou motivo de outra conta no POST
  é recusado; o estado da fila de uma loja nunca traz gente de outra.
- **Cadastro desativado** some das opções e continua nos lançamentos antigos;
  cadastro usado não se remove.
- **Auditoria:** cada correção e cada ação de cadastro registra autor e alvo.
- **`/fila/estado`:** a versão muda quando a fila muda e não muda quando nada
  mudou.

## Fora desta entrega

- **O dashboard** (entrega 2): atendimentos, conversão, vendas por grupo, ranking
  de vendedores, metas, tempo em pausa, presença esquecida.
- Ponto de jornada, fechamento automático no fim do dia, notificação e
  aplicativo nativo.
- Várias empresas por conta (herdado da base, ainda por fazer lá).
