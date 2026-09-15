# Fila Zero — os indicadores da fila

**Data:** 15/09/2026
**Estado:** desenho aprovado e implementado na branch `fila-da-vez` (plano de 15/09/2026).
**Entrega:** 2 de 3. A entrega 1 é a fila
(`docs/superpowers/specs/2026-09-15-fila-da-vez-design.md`); a entrega 3 são as
metas, com spec próprio.

## O problema

A fila grava cada passo do salão: quem atendeu, quando, se vendeu, o quê, por
quanto, por que não vendeu, quanto tempo cada um ficou em pausa. A entrega 2
transforma isso em respostas para duas pessoas:

- **a gestão** (gerente, supervisor, titular): quantos clientes a loja
  atendeu, quantos compraram, o que se vendeu, quem vende mais, por que se
  perde venda, quanto tempo a equipe fica fora da fila, e o que ficou aberto
  esquecido;
- **o vendedor**: como está o dia e o mês dele, e onde ele está no ranking da
  loja.

## Decisões

### D1 — Metas ficam para a entrega 3

Meta é um cadastro novo (quanto cada vendedor ou loja deve vender no período)
mais o acompanhamento. Esta entrega só lê o que a fila já grava; cada uma sai
testada e usável sozinha.

### D2 — Calcular na hora, a partir do histórico

Cada tela faz as contas no banco ao abrir (contagens e somas agrupadas),
filtrando por período e loja, sobre `Atendimento`, `ItemVendido`, `Pausa` e
`Presenca`. O volume cabe: uma loja grava dezenas de atendimentos por dia.
Não há número atrasado: a correção do gerente na fila muda o indicador na
mesma hora.

Rejeitados: tabela de resumo diário (precisa de agendador em cada VPS, e
corrigir um dia fechado exige recalcular, senão o número mente) e views
materializadas do Postgres (o mesmo problema de atualização, com SQL fora do
ORM e fora das varreduras de isolamento). Se um dia o volume pesar, um resumo
entra por trás sem mudar as telas.

### D3 — Gestão pelo alcance; vendedor vê os próprios números

Uma permissão nova, `fila.relatorios`, abre a tela de indicadores. O vendedor
não entra nela; ele ganha a faixa "Seus números" na página da fila.

### D4 — Período por atalhos ou intervalo, com comparação

Hoje, Ontem, 7 dias, Este mês, Mês passado, ou um intervalo de datas livre.
Cada número mostra a variação em relação ao período anterior de mesmo tamanho.

### D5 — O ranking ordena por valor vendido

A tabela mostra também atendimentos, vendas, conversão, ticket médio,
"cliente pediu" e tempo em pausa, e reordena por qualquer coluna (R46).

### D6 — "Cliente pediu" conta na conversão e aparece à parte

A conversão principal é de todos os atendimentos. Ao lado, quantos foram
"cliente pediu" e a conversão só deles, para ver quem tem clientela própria.

### D7 — Esquecido é o que virou o dia aberto

Presença, atendimento ou pausa abertos com começo antes de hoje viram um aviso
no topo da tela de indicadores, com link para a fila da loja, onde o gerente
corrige. Sem parâmetro novo.

## Quem vê o quê

| permissão | o que abre |
|---|---|
| `fila.relatorios` | a tela `/fila/indicadores`, nas lojas em que o cargo traz a permissão |

Cargos de fábrica e titular:

| quem | ganha `fila.relatorios` |
|---|---|
| Gerente | sim (a loja dele, pelo alcance da filial) |
| Supervisor | sim (a empresa) |
| Titular | sim (a empresa) |
| Vendedor, Representante, Cliente | não |

A MW5 já tem pelo coringa `fila.*`.

**As lojas que alguém enxerga** são as filiais que ele alcança
(`contas.lugar.filiais_da_pessoa`) em que as permissões do lugar
(`contas.lugar.permissoes_em`, ou as diretas do titular) trazem
`fila.relatorios`. Uma loja fora dessa lista chegando pela URL é descartada, e
a tela mostra as lojas permitidas, nunca um erro.

`fila.relatorios` entra no **fim** de `ModuloSpec.permissoes`: `fila.ver`
continua primeiro, porque é por ela que o menu da base põe o módulo na barra.

**Contas existentes.** A semeadura de cargos só cria o que falta e não altera
cargo existente. O Fila Zero não tem instalação no ar em 15/09/2026, então
esta entrega não traz migração de dados. Se houver instalação no ar antes da
execução, entra uma migração que acrescenta a permissão aos cargos de fábrica
cujas permissões ninguém editou.

## As telas

### No Início (`/`) — gestão

**Mudou depois da entrega (15/09/2026, pedido do João):** o dashboard não tem
mais tela própria nem item de menu. Ele aparece no Início, abaixo do "Olá" e
da data, para quem tem `fila.relatorios`; `/fila/indicadores` redireciona para
lá com os mesmos filtros. O resto desta seção vale como está.

1. **Filtros**: período (atalhos e intervalo) e loja ("Todas as lojas" para
   quem alcança mais de uma). Tudo na URL: `?periodo=`, `?de=`, `?ate=`,
   `?loja=`, para o link poder ser compartilhado.
2. **Aviso de esquecidos** (só quando há): pessoa, o que ficou aberto, desde
   quando, a loja, e o link para a fila daquela loja.
3. **Quatro números**: Atendimentos, Conversão, Vendido, Ticket médio, cada um
   com a variação. Sob a conversão, a linha do "cliente pediu".
4. **Gráficos**: vendido por grupo de item (barras deitadas); atendimentos e
   vendas por dia (por hora quando o período é um dia só); motivos de não
   venda; tempo em pausa por tipo.
5. **Ranking de vendedores**: tabela da casa com filtro, ordenação e
   paginação.

### "Seus números" — vendedor, na página `/fila`

Uma faixa abaixo do cartão de status, para quem tem `fila.participar`, com
duas colunas, Hoje e Este mês: atendimentos, vendas, conversão, vendido; e a
posição no ranking de vendido da loja no mês. É um pedaço novo da página
(`meus`), trocado junto com os outros quando a versão da fila muda. Mostra só
os números da própria pessoa.

## As regras de cálculo

### O que entra num período

- Só atendimento **fechado**, pela hora do **fim**, no fuso da instalação
  (`TIME_ZONE`). O que começa às 21:50 e fecha às 22:10 conta no dia em que
  fechou: o lançamento é daquele momento.
- Atendimento aberto não entra: ainda não tem resultado.
- O que vale é o lançamento de agora: correção do gerente muda o número.

### Os números

| número | regra |
|---|---|
| Atendimentos | quantos fecharam no período |
| Vendas | quantos fecharam como `vendeu` |
| Conversão | vendas ÷ atendimentos; sem atendimento é "—", nunca 0% |
| Vendido | soma de `total` das vendas |
| Ticket médio | vendido ÷ vendas; sem venda é "—" |
| Cliente pediu | quantos atendimentos `cliente_pediu` e a conversão só deles |
| Por grupo | soma de `ItemVendido.valor` por grupo, com os grupos desativados depois |
| Motivos | quantas não vendas por motivo, com os motivos desativados depois |
| Tempo em pausa | pausas **fechadas**, com a parte de cada uma que cai dentro do período |

Pausa aberta não entra no tempo: ela aparece na fila (hoje) ou nos esquecidos
(de antes).

### A comparação

- O período anterior tem o mesmo tamanho e termina onde o atual começa.
- **Período em andamento compara até o mesmo ponto**: "Hoje até 14:30" contra
  "ontem até 14:30"; "Este mês até o dia 15, 14:30" contra "mês passado até o
  dia 15, 14:30". Comparar meio dia com um dia inteiro mostraria queda em todo
  começo de dia.
- Mês passado sem o dia correspondente (hoje é 31, o mês passado teve 30)
  compara até o último dia dele.
- Anterior igual a zero: sem seta e sem porcentagem.
- A variação da conversão é em pontos percentuais ("↑ 4 p.p."), e não em
  porcentagem de porcentagem.

### Ranking

- Quem aparece: quem fechou atendimento **como vendedor** no período, nas
  lojas do filtro. Quem fechou no lugar dele (`fechado_por`) não ganha nada.
- Ordem padrão: vendido, depois conversão, depois nome.
- Em "Todas as lojas", os números de uma pessoa alocada em mais de uma loja
  somam.

### Posição do vendedor

- Ranking de vendido da **loja em que a pessoa está** (`filial_atual`), no
  **mês corrente**, entre quem vendeu algo no mês.
- Aparece "3º de 8". Mesmo valor vendido, mesma posição.
- Sem venda no mês: "sem vendas no mês", sem posição.

### Esquecidos

Presença (`saida` nula), atendimento (`fim` nulo) ou pausa (`fim` nulo) com
começo antes do início de hoje, nas lojas que a pessoa enxerga.

### Isolamento e desempenho

- Toda consulta passa por `objects.da_empresa(empresa)` e pelas lojas
  permitidas. Nunca `irrestritos` numa tela.
- Índices novos: `Atendimento (empresa, filial, fim)` e `Pausa (filial,
  inicio)`.

## Organização do código

| arquivo | responsabilidade |
|---|---|
| `fila/periodo.py` | `Periodo(de, ate, chave, rotulo)`, `periodo_do_pedido(GET, agora)`, `periodo_anterior(periodo, agora)`. Sem banco. Data inválida ou invertida cai em "Este mês" |
| `fila/indicadores.py` | `Recorte(empresa, lojas, periodo)`; `numeros`, `variacao`, `por_grupo`, `por_dia`, `motivos`, `pausa_por_tipo`, `ranking` (consulta anotada para a tabela R46), `esquecidos`, `posicao_no_mes`, `lojas_com_relatorio` |
| `fila/views_indicadores.py` | a tela, com os componentes do design system |
| `fila/templates/fila/_meus.html` | a faixa "Seus números" |
| `fila/modulo.py` | `fila.relatorios` no fim das permissões; atalho "Indicadores" |
| `contas/cargos_de_fabrica.py`, `contas/fabrica.py` | a permissão nova |
| migração | os dois índices |

## Como se prova

Cada trava é testada e quebrada de propósito uma vez:

- **Período**: cada atalho; intervalo livre; data inválida ou invertida cai no
  padrão; o anterior de "Hoje às 14:30" termina ontem às 14:30; mês passado
  mais curto.
- **Números**: conta pelo fim, não pelo início; aberto não conta; conversão
  "—" sem atendimento; ticket; cliente pediu à parte; grupo desativado
  continua; pausa cortada na meia-noite; correção muda o número.
- **Comparação**: anterior zero sem seta; período em andamento até o mesmo
  ponto; conversão em pontos percentuais.
- **Ranking**: vendedor é quem atendeu e não quem fechou; soma entre lojas;
  desempate por conversão e nome.
- **Alcance**: sem `fila.relatorios` a tela responde 404; gerente só vê a loja
  dele, e a loja forjada na URL é descartada; supervisor e titular veem todas;
  outra empresa nunca entra.
- **Esquecidos**: aberto de ontem aparece; aberto de hoje não.
- **Seus números**: só a própria pessoa; "3º de 8"; empate na mesma posição;
  sem vendas no mês.
- **Varreduras**: guarda, módulo ligado, aviso de personificação, tabela com
  filtro, ordenação e paginação.

## Fora desta entrega

- Metas (entrega 3).
- Exportar os indicadores em Excel ou PDF.
- Comparação de lojas lado a lado.
- Tempo disponível na fila (presença menos atendimento e pausa).
