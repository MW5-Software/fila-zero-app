# Fila Zero — várias empresas por conta

**Data:** 17/09/2026
**Estado:** desenho aprovado na conversa de 17/09/2026; falta o plano.
**Depende de:** "uma conta, uma empresa"
(`2026-09-09-uma-conta-uma-empresa-design.md`), cargos e alocações
(`2026-09-14-cargos-e-alocacoes-design.md`, que já previa isto como "plano 3")
e o painel por loja (commit `881ec60`).

## O problema

A conta do cliente é dona de **uma** empresa, por uma trava no banco
(`uma_empresa_por_conta`). Quem tem duas pessoas jurídicas precisa de duas
instalações, com dois cadastros de gente, dois cadastros de cargos e nenhuma
visão do conjunto.

O cliente pediu: **conta → empresas → lojas**, com o cadastro de empresa e de
loja, e o painel do titular podendo somar as empresas ou olhar uma por vez.

Hoje o vocabulário da interface também mistura as duas ideias: o menu diz
"Empresa" para o que é a conta do cliente, e o seletor do cabeçalho diz
"Conta" para o que a MW5 escolhe.

## Decisões

### E1 — A conta tem várias empresas, e a empresa continua sendo a fronteira

Cai a trava `uma_empresa_por_conta`. `Empresa.dono` continua apontando para o
titular, e `Empresa.conta` (a coluna `conta_guid`) continua derivada dele.

**O `conta_guid` continua em toda tabela, e não muda nada nele**: coluna
obrigatória (`NOT NULL` nas tabelas de negócio), derivada da empresa no `save`
(`contas.inquilino.ModeloDaEmpresa`, `plataforma.models._conta_da_empresa`),
nunca escrita à mão, e a identidade estável do cliente para fora — é ela que
toda integração usa. `test_toda_linha_da_conta_leva_o_guid.py` e
`test_regra_do_inquilino.py` continuam cobrando isso de TODA tabela, sem
isenção nova.

**A fronteira do dado de negócio continua sendo a EMPRESA**, e não a conta:
toda consulta passa por `objects.da_empresa(...)`, como hoje. O que muda é só
o que o `conta_guid` responde sozinho: com duas empresas na mesma conta, ele
diz de quem é a linha, e não de qual empresa — quem diz a empresa é a coluna
`empresa`, que já existe ao lado dele em toda tabela.

### E2 — `da_conta` passa a ser uma escolha, e não um acidente

`contas.inquilino.GerenteDaEmpresa.da_conta(conta)` filtra só pela conta.
Com duas empresas, ele devolve as linhas das duas. **Isso continua valendo, e
passa a ser dito em voz alta**: o docstring explica que ele soma as empresas
da conta, e um teste prova a soma. Quem quer uma empresa usa `da_empresa`.

**Dois lugares olham a conta, e cada um por um motivo** (relido no código em
17/09/2026, depois do desenho):

- `contas.lugar.clientes_alcancados` já filtra as alocações **pela empresa**;
  o `dono_id=empresa.dono_id` que vem depois é só a segunda tranca contra
  alocação gravada por fora. **Não muda**, e ganha teste provando que o
  cliente de uma empresa não aparece na irmã.
- `contas.lugar.tem_cargo_de_cliente` responde "é cliente em algum lugar da
  CONTA", de propósito: é a pergunta feita fora de requisição, onde não há
  empresa atual. **Não muda**, e o docstring passa a dizer que, com várias
  empresas, "algum lugar" inclui todas elas.

### E3 — O cabeçalho mostra a empresa para quem alcança mais de uma

`plataforma.contexto.niveis_de_contexto` já desenha o seletor quando a pessoa
alcança mais de uma empresa; o que muda é que isso deixa de ser só a MW5.

- Para quem é de uma conta, o rótulo é **"Empresa"**: a pergunta é em qual das
  empresas dele ele está.
- Para a MW5, o rótulo continua **"Conta"**: a pergunta dela é qual cliente
  está olhando.
- Trocar de empresa leva a filial para a primeira permitida dentro dela (já é
  assim, `contexto.escolher_empresa`).
- `plataforma.contexto.empresa_atual` passa a ler a sessão também para quem é
  de uma conta. O atalho de "alcança uma só" continua, porque a maioria das
  contas tem uma empresa.

**A marca segue a empresa do cabeçalho.** `plataforma.marca.empresa_da_marca`
usa `contas.alcance.empresa_de`, que devolve "a primeira que a pessoa
alcança". Passa a usar `empresa_atual(request)`, com o mesmo cuidado de hoje
para a MW5 (sem empresa, a marca é a da instalação). `empresa_de` fica só
onde não há requisição, com o aviso de que ela é "a primeira", e não "a dela".

### E4 — As telas, e as palavras

| tela | quem | o que muda |
|---|---|---|
| **Conta** (nova) | titular e MW5 | Os dados do cliente e a lista das empresas dele. Leitura para o titular. |
| **Empresas** | MW5 | Volta o botão "Nova empresa" (a empresa nasce com a Matriz). |
| **Empresas** | titular | Passa a listar as várias empresas da conta, em vez de uma linha só. |
| **Lojas** (Filiais) | titular | O módulo passa a **nascer ligado** (hoje a MW5 liga em cada instalação), e a tela mostra as lojas da empresa do cabeçalho. |
| **Usuários** | quem aloca | A coluna "Empresa" passa a listar as empresas em que a pessoa está alocada. O bloco Alocações já é por empresa e loja. |
| **Cargos** | titular | Sem mudança: o cargo é da conta e vale em todas as empresas. |

O menu passa a dizer **Conta** no topo (os dados do cliente) e **Empresas**
dentro. "Filial" continua aparecendo como **Loja** no Fila Zero.

### E5 — A fila

- **A fila é sempre da loja da empresa do cabeçalho.** Nada muda para o
  vendedor.
- **Um ponto por vez, em qualquer empresa.** A restrição de uma presença
  aberta por pessoa já existe no banco
  (`fila_uma_presenca_aberta_por_pessoa`); o que muda é o motivo escrito ao
  lado: ela agora também impede a mesma pessoa de estar na fila de duas
  EMPRESAS ao mesmo tempo.
- **Os cadastros continuam por empresa** (grupos de item, motivos, tipos de
  pausa, metas): cada empresa tem os seus.
- **No painel do titular entra "Todas as empresas"**, no mesmo desenho do
  "Todas as lojas" de hoje: soma as empresas alcançadas, mostra o bloco "Por
  empresa" e o ranking ganha a coluna Empresa. O padrão continua sendo a
  empresa do cabeçalho.

### E6 — O que a suíte precisa deixar de afirmar

Cerca de vinte testes afirmam "uma conta, uma empresa" — o da trava
(`tests/test_acesso_alcance.py::test_o_banco_recusa_a_segunda_empresa_da_mesma_conta`),
os do cabeçalho sem seletor, os da tela de Empresas com uma linha só, e os do
menu no singular. Eles passam a afirmar o contrário, um a um.

**`tests/conftest.py` descarta em silêncio a segunda empresa** passada a
`dar_acesso` (`alvo = list(empresas)[:1]`). Isso é corrigido primeiro: sem
isso, um teste novo de duas empresas passaria sem provar nada.

## As peças

### Base (`plataforma/`, `contas/`)

- `plataforma/models.py`: cai a trava; `related_name` vira `empresas_da_conta`;
  o comentário de `dono` passa a dizer o que vale agora.
- `plataforma/contexto.py`: o seletor e o rótulo (E3).
- `plataforma/marca.py`: a marca pela empresa do cabeçalho (E3).
- `contas/lugar.py`: `clientes_alcancados` e `tem_cargo_de_cliente` por
  empresa (E2).
- `contas/inquilino.py`: o docstring de `da_conta` (E2).
- `contas/alcance.py`: `empresa_de` ganha o aviso de que é "a primeira".
- Migração: só a remoção da trava.

### Telas

- `plataforma/views_conta.py` (nova) e a entrada no menu.
- `plataforma/views_empresa.py`: "Nova empresa" de volta para a MW5; a lista
  do titular com várias linhas.
- `plataforma/modulo.py` (ou a declaração do módulo Filiais): nasce ligado.
- `contas/views_usuarios.py`: a coluna de empresas da pessoa, o dicionário por
  conta (`:376`) e a subconsulta `_com_empresa` (`:120`).

### Fila

- `fila/views_indicadores.py`: "Todas as empresas", o bloco "Por empresa" e a
  coluna Empresa no ranking.
- `fila/models.py`: o comentário da restrição de presença (E5).

### Castelhano e documentação

As frases novas da moldura entram no `django.po`. `CLAUDE.md` §7 troca a
seção "Uma conta, uma empresa" pela regra nova, e a §9 perde dois itens em
aberto (várias empresas e o módulo de Filiais desligado).

## Erros e bordas

| caso | resposta |
|---|---|
| `?empresa=` forjada na troca de contexto | a que a pessoa não alcança é descartada, como hoje |
| empresa sem loja ativa | a tela de Lojas diz o que falta; a fila diz "você não está em nenhuma loja" |
| pessoa alocada em duas empresas tenta bater o ponto na segunda | a recusa de hoje ("saia da loja atual"), com o motivo escrito |
| titular tenta criar empresa | não existe o botão, e o POST recusa: quem cria é a MW5 |
| conta sem empresa nenhuma | as telas dizem a frase que já existe hoje |
| duas empresas com o mesmo CNPJ | continua recusado (`cnpj_unico_por_instalacao`) |
| trocar o titular de uma empresa que tem alocação | continua recusado |

## Testes

- **Isolamento:** duas empresas na mesma conta não misturam fila, metas,
  cadastros, clientes nem aparência.
- **Cabeçalho:** o titular com duas empresas vê o seletor ("Empresa"); a MW5
  continua vendo "Conta"; trocar leva a filial junto.
- **Marca:** trocar de empresa troca o logo e as cores do menu.
- **Telas:** a de Empresas lista as várias para o titular e só a MW5 cria; a
  de Usuários mostra as empresas de cada pessoa; Lojas nasce ligada.
- **Fila:** a fila de uma empresa não enxerga a outra; um ponto por vez entre
  empresas; "Todas as empresas" no painel soma e separa.
- **`conta_guid`:** a linha de negócio criada em qualquer uma das duas
  empresas nasce com o `conta_guid` da conta, derivado da empresa, e o `save`
  continua recusando conta divergente.
- **Varreduras:** inquilino, `conta_guid`, guarda, tabela e personificação
  continuam passando sem isenção nova.
- **`conftest`:** `dar_acesso` com duas empresas dá as duas.

## Entregas

O plano separa isto em três, cada uma com a suíte verde no fim:

1. **A base:** a trava, o contexto, a marca, `lugar.py`, `conftest` e os
   testes que mudam de lado.
2. **As telas:** Conta, Empresas, Lojas ligada e Usuários.
3. **A fila:** "Todas as empresas" no painel e o comentário da presença.
