# Fila Zero — as metas da fila

**Data:** 15/09/2026
**Estado:** desenho aprovado pelo João em conversa (15/09/2026); falta o plano.
**Entrega:** 3 de 3. A entrega 1 é a fila
(`docs/superpowers/specs/2026-09-15-fila-da-vez-design.md`); a entrega 2 são
os indicadores (`docs/superpowers/specs/2026-09-15-fila-indicadores-design.md`).

## O problema

Os indicadores dizem quanto a loja e cada vendedor venderam, mas não dizem se
isso é bom. A Sylvia e os gerentes cobram um valor por mês, hoje numa planilha
ou de cabeça, e só sabem no fim do mês se ele fechou. A entrega 3 guarda esse
valor e responde, a qualquer dia do mês:

- **para a gestão**: quanto a loja e cada vendedor já fizeram da meta, quanto
  falta, quanto precisa vender por dia daqui até o fim, e onde o mês fecha no
  ritmo de agora;
- **para o vendedor**: a mesma resposta, só da meta dele.

## Decisões

### M1 — A meta é só de valor vendido

Em R$. É o número que o varejo cobra no fim do mês, e a fila já o tem exato
(a soma de `total` das vendas, regra dos indicadores). Rejeitados: meta de
conversão ou de ticket junto (cadastro pesado todo mês e painel carregado;
podem entrar depois sem mudar esta).

### M2 — Meta da loja e meta do vendedor, independentes

A loja tem a meta dela e cada vendedor tem a sua **naquela loja**. A da loja
é cadastrada à parte, e **não** é a soma das dos vendedores: gente entra e sai
no meio do mês, e a meta da loja não pode mudar sozinha por isso. O painel
mostra se a soma das metas dos vendedores cobre a da loja.

Quem trabalha em duas lojas pode ter uma meta em cada; cada uma é medida só
pelo que ele vendeu naquela loja.

Rejeitados: só a da loja (o vendedor ficava sem número dele); só a do vendedor
com a da loja somada (a meta da loja mudaria a cada alocação).

### M3 — Mensal, pelo mês do calendário

Uma meta por mês. Casa com o "Este mês" e o "Mês passado" dos indicadores e
com o jeito de o varejo pagar comissão. Rejeitados: semanas dentro do mês
(mais cadastro e a semana que cruza o mês) e período livre para campanha
(metas sobrepostas e acompanhamento ambíguo).

### M4 — Quem define: gerente, supervisor e titular, nunca a própria

Permissão nova, `fila.metas`. O gerente define as da loja dele (a da loja e as
de quem trabalha nela), pelo alcance da filial; supervisor e titular, as de
todas as lojas. **Ninguém define a própria meta**: o gerente que também
atende aparece na lista com o campo travado.

### M5 — Ritmo: quanto falta, por dia e projeção

Além de "quanto já fez", o acompanhamento diz quanto precisa vender por dia
que resta e onde o mês fecha no ritmo atual. Dias **corridos**: não há cadastro
de dias de funcionamento da loja (rejeitado por ser mais um cadastro para a
Sylvia manter; entra depois se o número enganar).

### M6 — Mês sem meta não mostra; copiar do anterior; passado travado

- Mês sem meta cadastrada: o acompanhamento simplesmente não aparece. Nada
  repete sozinho: meta errada repetida passaria despercebida.
- A tela tem **"Copiar metas do mês anterior"**, que preenche só o que está
  vazio no mês escolhido.
- **Mês encerrado não se edita.** A meta de agosto não muda depois de agosto:
  mudar a régua depois do resultado desmente o que já foi cobrado.
- Mês atual e meses futuros se editam (planejar o mês que vem).

## Quem vê o quê

| permissão | o que abre |
|---|---|
| `fila.metas` | a tela `/fila/metas`, nas lojas em que o cargo traz a permissão |
| `fila.relatorios` | a meta no painel do Início e as colunas no ranking (como já é) |
| `fila.participar` | a linha da própria meta em "Seus números", na `/fila` |

Cargos de fábrica e titular:

| quem | ganha `fila.metas` |
|---|---|
| Gerente | sim (a loja dele, pelo alcance da filial) |
| Supervisor | sim (a empresa) |
| Titular | sim (a empresa) |
| Vendedor, Representante, Cliente | não |

`fila.metas` entra no **fim** de `ModuloSpec.permissoes` (`fila.ver` continua
a primeira, que é a do menu) e ganha o atalho "Metas" no grupo Cadastro, sob
"Fila da vez".

**As lojas que alguém enxerga na tela de metas** saem do mesmo molde de
`fila.indicadores.lojas_com_relatorio`, com `fila.metas` no lugar de
`fila.relatorios`. Loja forjada na URL é descartada, e a tela abre na primeira
permitida, nunca num erro.

**Contas existentes.** Como na entrega 2: a semeadura só cria cargo que falta.
Sem instalação no ar em 15/09/2026, não há migração de dados; se houver antes
da execução, entra uma migração que acrescenta a permissão aos cargos de
fábrica que ninguém editou.

## O registro

Uma tabela, `fila.Meta` (herda `ModeloDaEmpresa`):

| campo | regra |
|---|---|
| `filial` | a loja, `PROTECT` |
| `pessoa` | o vendedor, `PROTECT`, **nula quando a meta é da loja** |
| `mes` | `DateField`, sempre o dia 1 do mês |
| `valor` | `Decimal(12, 2)`, maior que zero e até `fila.acoes.MAIOR_VALOR` |

Travas no banco, e não só na tela:

- uma meta de loja por loja e mês (`UNIQUE (filial, mes)` onde `pessoa` é nula);
- uma meta por pessoa, loja e mês (`UNIQUE (filial, pessoa, mes)` onde não é);
- `mes` no dia 1 e `valor > 0` (`CheckConstraint`).

Uma tabela, e não duas (loja e vendedor): a regra, a tela e as consultas são as
mesmas, e duas tabelas duplicariam cada uma. Rejeitado também guardar a meta na
alocação: a alocação não tem mês.

Apagar a meta é apagar a linha (campo vazio na tela). Toda gravação e toda
remoção vão para a auditoria (`comum.auditoria`, ações novas
`FILA_META_DEFINIDA` e `FILA_META_REMOVIDA`), com loja, pessoa, mês, valor
antigo e novo.

## As telas

### Cadastro — `/fila/metas`

1. **Escolha**: mês (`?mes=2026-09`, padrão o mês atual) e loja (`?loja=`,
   entre as permitidas). Setas de mês anterior e seguinte.
2. **A meta da loja**, na primeira linha.
3. **Uma linha por pessoa**: quem tem `fila.participar` na loja naquele lugar
   (alocação vigente), **mais** quem já tem meta naquele mês e não está mais
   na loja (marcado "não está mais nesta loja"). Nome, foto, e o campo de
   valor. A linha de quem está editando vem travada (M4).
4. **Soma das metas dos vendedores** ao lado da meta da loja: "Vendedores
   somam R$ 210.000,00 de R$ 250.000,00".
5. **Salvar** grava tudo de uma vez, numa transação; **Copiar metas do mês
   anterior** preenche só os campos vazios e não salva sozinho (a pessoa
   confere e salva).
6. **Mês encerrado**: os campos aparecem só para leitura, com a frase "Mês
   encerrado: as metas não se editam mais."

A tela não tem `<table>`: é um formulário de linhas, como a página da fila,
com os componentes do design system. A R46 vale para tabela que lista
registros; aqui cada linha é um campo do mesmo formulário, e uma loja tem
dezenas de pessoas, não milhares.

Valor digitado passa por `fila.valores.ler_valor` (o celular dá vírgula, o
computador às vezes ponto). Valor que não é número, zero, negativo ou acima de
`MAIOR_VALOR` recusa o formulário inteiro com a frase ao lado do campo, e nada
é gravado.

O POST confere de novo, no servidor, tudo o que a tela travou: a loja está
entre as permitidas, o mês não está encerrado, a pessoa é da loja (ou já tinha
meta nela naquele mês) e não é quem está editando. Id cru do POST passa por
`comum.pedido.id_do_post`.

### No Início — o painel dos indicadores

Só quando o período é um mês inteiro do calendário (**Este mês** ou **Mês
passado**) e existe meta. Em outro período nada muda.

1. **A faixa da meta**, dentro do painel, entre as abas e o gráfico:
   - barra de progresso do vendido contra a meta, com a porcentagem;
   - mês em andamento: "Faltam R$ 96.810,00", "R$ 6.454,00 por dia até 30/09"
     e "No ritmo atual, fecha em R$ 1.790.000,00";
   - meta batida: "Meta batida, R$ 12.300,00 acima";
   - mês encerrado: "Bateu a meta" ou "Ficou em 92% da meta, faltaram
     R$ 20.000,00", sem ritmo.
2. **Loja escolhida**: a meta da loja. **Todas as lojas**: a soma das metas das
   lojas que têm meta, contra o vendido **dessas** lojas, e a frase "3 de 4
   lojas com meta" quando alguma não tem. Comparar a soma parcial com o
   vendido de todas faria a meta parecer batida por causa de uma loja sem meta.
3. **O ranking** ganha as colunas **Meta** e **% da meta**, ordenáveis (R46).
   Meta do vendedor em "Todas as lojas" é a soma das metas dele nas lojas do
   recorte; % é o vendido dele nessas lojas sobre essa soma. Sem meta: "—".

### "Seus números" — na página `/fila`

Uma linha a mais na coluna "Este mês", só quando a pessoa tem meta na loja em
que está: "Meta: R$ 30.000,00, 62%", e embaixo "Faltam R$ 11.400,00, R$
760,00 por dia". Meta batida: "Meta batida". É o mesmo pedaço `meus`, trocado
junto quando a versão da fila muda; a versão passa a incluir a meta da pessoa
no mês, para uma meta alterada pelo gerente aparecer sem recarregar.

## As regras de cálculo

Todas em `fila/metas.py`, sem tela, com o relógio recebido (`agora`) para o
teste fixar o dia.

### O que conta

- O vendido é o dos indicadores: atendimento **fechado** como `vendeu`, pela
  hora do **fim**, no fuso da instalação, dentro do mês.
- **Loja**: o vendido de todos na loja.
- **Vendedor**: o vendido em que ele é o `vendedor`, **naquela loja**. Quem
  fechou no lugar dele (`fechado_por`) não ganha nada, como no ranking.

### O acompanhamento

Com `meta`, `vendido`, `hoje` (data local de `agora`) e o mês:

| número | regra |
|---|---|
| atingido | `vendido ÷ meta`, em %, com uma casa |
| falta | `meta − vendido`; zero ou menos é "meta batida" (e o excedente) |
| dias que restam | do dia de hoje (**inclusive**) ao último dia do mês |
| por dia | `falta ÷ dias que restam`; não aparece com a meta batida |
| dias fechados | dias do mês **antes** de hoje |
| projeção | `vendido até ontem ÷ dias fechados × dias do mês` |

- **A projeção usa só os dias fechados.** No dia 1 às 10h, uma venda de
  R$ 5.000 projetaria R$ 150.000; com os dias fechados, o dia 1 não tem
  projeção ("Projeção a partir de amanhã"), e o dia de hoje, pela metade, não
  puxa o número nem para cima nem para baixo.
- **Mês encerrado**: só atingido e falta (ou excedente). Sem por dia e sem
  projeção.
- **Mês futuro** (planejado): não aparece em acompanhamento nenhum; o painel
  só mostra mês atual e passado.

### O que se vê no cadastro

- **A soma dos vendedores** é a soma das metas de pessoa da loja no mês,
  incluindo quem não está mais nela.
- **Copiar do mês anterior** considera as metas de pessoa só de quem aparece
  hoje na lista (quem saiu da loja não volta a ter meta por cópia) e a da loja.

## Isolamento

- Toda consulta passa por `Meta.objects.da_empresa(empresa)` e pelas lojas
  permitidas. Nunca `irrestritos` numa tela.
- A pessoa de uma meta sai sempre da lista da loja (alocação vigente, ou meta
  já existente naquele mês): um id de pessoa de outra conta chegando pelo POST
  não está na lista e é recusado.

## Organização do código

| arquivo | responsabilidade |
|---|---|
| `fila/models.py` | `Meta`, com as travas do banco |
| `fila/metas.py` | `mes_do_pedido`, `pode_editar(mes, agora)`, `pessoas_da_lista`, `gravar(...)` (transação e auditoria), `copiar_do_anterior`, `Acompanhamento` e `acompanhar(meta, vendido, mes, agora)` |
| `fila/views_metas.py` | a tela de cadastro |
| `fila/views_indicadores.py`, `fila/static/fila/indicadores.css` | a faixa da meta no painel e as colunas do ranking |
| `fila/indicadores.py` | a meta e o % no `ranking` (subconsulta, como as outras colunas) |
| `fila/tela.py`, `fila/templates/fila/_meus.html`, `fila/estado.py` | a linha em "Seus números" e a versão |
| `fila/modulo.py`, `contas/cargos_de_fabrica.py`, `contas/fabrica.py` | `fila.metas` e o atalho |
| `comum/auditoria.py` | `FILA_META_DEFINIDA`, `FILA_META_REMOVIDA` |
| migração | a tabela e as travas |

## Como se prova

Cada trava é testada e quebrada de propósito uma vez:

- **Registro**: duas metas de loja no mesmo mês estouram no banco; duas da
  mesma pessoa na mesma loja também; a mesma pessoa em duas lojas pode; mês
  fora do dia 1 e valor zero são recusados pelo banco.
- **Cadastro**: grava, altera e apaga (campo vazio), com auditoria; valor
  inválido recusa tudo e não grava nada; mês encerrado recusa no POST mesmo
  forjado; a própria meta recusa no POST mesmo forjada; pessoa de outra loja
  forjada recusa; "copiar" preenche só o vazio e não traz quem saiu da loja.
- **Alcance**: sem `fila.metas` a tela responde 404; gerente só vê a loja dele
  e a forjada é descartada; supervisor e titular veem todas; outra empresa
  nunca entra.
- **Cálculo**, com relógio fixo: dia 1 (sem projeção), dia 15, último dia (um
  dia que resta), meta batida (sem por dia), mês passado (sem ritmo); o
  vendedor conta só a loja da meta; quem fechou no lugar não ganha.
- **Painel**: aparece em "Este mês" e "Mês passado", some em "7 dias"; em
  "Todas as lojas" compara só as lojas com meta e diz "3 de 4"; ranking com
  Meta e % ordenáveis, "—" sem meta.
- **Seus números**: só a meta da própria pessoa, da loja em que está; a versão
  muda quando o gerente altera a meta.
- **Varreduras**: guarda, módulo ligado, aviso de personificação, tabela do
  ranking, id do POST, castelhano.

## Fora desta entrega

- Meta de conversão, de ticket ou de atendimentos (M1).
- Semanas e campanhas (M3).
- Dias de funcionamento da loja (M5).
- Comissão ou premiação calculada a partir da meta.
- Aviso ativo (notificação) de meta em risco.
