# Relatórios da fila — desenho

Data: 28/09/2026. Pedido do cliente: "um relatório que pode ser tirado pelo
dono da conta, supervisor ou gerente, e cada um é focado em uma coisa: o dono
de tudo, o supervisor do que ele é cadastrado, e o gerente no que ele é
cadastrado — relatório diário, semanal, mensal, mês passado".

## O que é

Uma tela **Relatórios** (`/fila/relatorios`, no menu Gerenciar Fila) em que
quem gerencia escolhe o período e a loja e baixa o relatório em **PDF** ou
**Excel**. Não é agendado nem enviado por e-mail: é o gestor quem gera, quando
quer.

## Quem tira, e o que enxerga

- A tela abre com **`fila.relatorios`**, a mesma permissão que dá o painel da
  gestão no Início. Não há permissão nova: quem lê os indicadores na tela lê
  os mesmos no papel.
- As lojas saem de **`fila.indicadores.lojas_com_relatorio`**, a mesma porta do
  painel. É ela que faz "cada um focado em uma coisa":
  - o **dono** alcança todas as lojas das empresas dele;
  - o **supervisor**, as lojas da empresa em que está alocado;
  - o **gerente**, as lojas em que está alocado.
- As empresas saem de **`empresas_com_relatorio`**. Quem alcança mais de uma
  escolhe uma, ou "Todas as empresas" — a mesma regra do painel
  (`views_indicadores._empresas_do_pedido`).
- A `?loja=` e a `?empresa=` do pedido só **escolhem dentro** do que a pessoa
  alcança; um id forjado cai no padrão e nunca amplia o alcance.
  Reaproveitam-se `_lojas_do_pedido` e `_empresas_do_pedido`.

## A tela

Um formulário com:

- **Período** — cinco opções, chaves do `fila.periodo.ATALHOS` que já existem:
  | rótulo na tela | chave |
  |---|---|
  | Diário (hoje) | `hoje` |
  | Ontem | `ontem` |
  | Semanal (últimos 7 dias) | `7dias` |
  | Mensal (este mês) | `mes` |
  | Mês passado | `mes_passado` |

  O padrão é **Mensal**. Chave fora dessa lista cai no padrão.
- **Loja** — "Todas as lojas" ou uma das alcançadas; com uma loja só, não há
  campo, e ela é o recorte (como no painel).
- **Empresa** — só para quem alcança mais de uma.
- Dois botões: **Gerar PDF** e **Gerar Excel**. Os dois são `GET` com
  `?formato=impressao` e `?formato=xlsx` (os formatos de
  `comum.exportacao.FORMATOS`), para o link poder ser salvo e aberto de novo.

A tela funciona sem JavaScript.

## O conteúdo

**Todo número sai das contas que o painel já usa** (`fila/indicadores.py`,
`fila/metas.py`), pelo mesmo `Recorte`. Não se escreve conta nova para o
relatório: se o papel e a tela discordassem, ninguém saberia em qual
acreditar.

1. **Resumo**
   - total do recorte: atendimentos, vendas, conversão, vendido e ticket
     médio (`indicadores.numeros`), com a variação contra o período anterior
     (`periodo.periodo_anterior`, `indicadores.variacao`);
   - uma linha por loja (`indicadores.por_loja`), e uma por empresa em "Todas
     as empresas" (`indicadores.por_empresa`).
2. **Por vendedor** — uma linha por vendedor EM CADA loja
   (`indicadores.ranking_por_loja`): atendimentos, vendas, conversão, vendido,
   ticket médio, "cliente pediu", tempo em pausa e % da meta.
   - O **% da meta só nos períodos de mês** (`mes`, `mes_passado`): a meta é
     mensal, e dividir o vendido de 7 dias pela meta do mês seria número
     errado com cara de certo. Nos outros períodos a coluna sai "—".
   - A **pausa não conta as pausas da gestão**, como no ranking do painel.
3. **Motivos, mídias, grupos e pausas**
   - motivos de não venda (`indicadores.motivos`, com "Fechado sem
     lançamento");
   - por mídia, com atendimentos, vendas e conversão (`indicadores.midias`,
     com "Sem mídia");
   - vendido por grupo de item (`indicadores.por_grupo`);
   - tempo em pausa por tipo (`indicadores.pausa_por_tipo`), com as pausas da
     gestão pelo nome delas.
4. **Lançamento a lançamento** — uma linha por atendimento FECHADO no período
   (a mesma regra do painel: entra pela hora do fim, aberto não entra):
   data e hora do fim, loja, vendedor, resultado, valor, grupos (com valor de
   cada um), motivo, observação, mídia, "cliente pediu" e quem fechou (quando
   não foi o próprio vendedor). Ordem: do mais antigo para o mais novo.
   A consulta é uma função nova em `fila/indicadores.py`
   (`lancamentos_do_recorte`), pelo `do_recorte`, com `select_related` e
   `prefetch_related` dos itens — uma consulta por tabela, e não por linha.

## Os formatos

- **Excel** (`openpyxl`, já dependência): um arquivo com uma aba por seção —
  Resumo, Vendedores, Motivos, Mídias, Grupos, Pausas, Lançamentos. Valores
  numéricos saem como número (e não texto), com formato de moeda nas colunas de
  dinheiro e de porcentagem na conversão, para quem abre poder somar e filtrar.
  Nome do arquivo: `relatorio-<empresa>-<período>-<data>.xlsx`.
- **PDF**: a página de impressão, como as listas (`comum.exportacao`): sem
  shell e sem menu, chama `window.print()`, e o navegador salva em PDF — sem
  motor de PDF na imagem, pelo mesmo motivo escrito em `comum/exportacao.py`.
  As quatro seções em ordem, os lançamentos por último (num mês da rede
  inteira é a seção longa). Cada tabela repete o cabeçalho na quebra de página.
- **O cabeçalho dos dois** diz: o nome do relatório, a empresa (ou "Todas as
  empresas"), as lojas do recorte, o período com as datas por extenso
  ("01/09/2026 a 30/09/2026"), quem gerou e quando.

## O menu

"Relatórios" entra no grupo **Gerenciar Fila**, depois de "Histórico da fila",
com `fila.relatorios`. O teste que prende a barra
(`test_o_menu_da_fila_como_o_cliente_pediu`) passa a esperar o item.

## O castelhano

A moldura (títulos, rótulos, cabeçalhos das colunas, nomes das abas) sai por
`gettext`, com as frases no `django.po`. Dado cadastrado (nomes de loja, de
vendedor, de motivo) não se traduz.

## Testes

- quem entra: o dono, o supervisor e o gerente abrem; o vendedor toma 404;
- o recorte: o gerente só vê a loja dele, e uma `?loja=` de outra loja cai na
  dele; o supervisor não vê a loja de outra empresa; o dono vê todas;
- os números do relatório batem com os do painel para o mesmo recorte;
- o % da meta sai só em `mes` e `mes_passado`;
- a pausa da gestão fica fora da pausa do vendedor;
- o Excel abre (`openpyxl.load_workbook`) com as sete abas, e as células de
  dinheiro são número;
- o PDF traz as quatro seções e o cabeçalho com período e lojas;
- os lançamentos: fechados no período entram, abertos não, e a consulta não
  cresce com o número de lançamentos (`CaptureQueriesContext`);
- o menu com o item novo; a tela sem JavaScript.

Conferência no navegador: a tela em 390px e 1280px, o PDF salvo pelo Chrome
headless e o Excel aberto por script.

## Fora do escopo

- envio por e-mail e relatório agendado;
- intervalo de datas livre (o painel também não tem desde 17/09/2026);
- gráficos no PDF — o relatório é de números; os gráficos continuam no painel.
