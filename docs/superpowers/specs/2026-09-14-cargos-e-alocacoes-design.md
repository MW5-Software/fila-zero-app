# Cargos e alocações

**Data:** 14/09/2026
**Estado:** desenho aprovado, execução não começou.

## O problema

O portal foi construído em 09/09/2026 sobre "uma conta, uma empresa"
(`docs/superpowers/specs/2026-09-09-uma-conta-uma-empresa-design.md`): o
titular é dono de UMA empresa, a empresa de cada pessoa é derivada da conta, e
o que alguém pode fazer vem de `Perfil` — um conjunto de permissões com nome
que vale para a pessoa no sistema inteiro.

O negócio precisa de outra forma:

    Conta → Empresas → Filiais
    Conta → Usuários da conta
    Cargo → Permissões
    Usuário → (Empresa, Filial) → Cargo

Uma conta com várias empresas, cada empresa com várias filiais, e cada pessoa
alocada em lugares com um cargo — que diz o que ela pode fazer ali, e não no
sistema inteiro.

Três coisas de hoje não comportam isso:

1. **O perfil não sabe de lugar.** `contas.backend.permissoes_de` soma as
   permissões dos perfis num conjunto único da pessoa. Quem é "Vendedor" é
   vendedor em tudo.
2. **A trava `uma_empresa_por_conta`** (`UNIQUE` em `Empresa.dono`) proíbe a
   segunda empresa no banco.
3. **O papel comprador/vendedor mora no perfil** e decide carteira, preço,
   botão de compra e visibilidade de orçamento.

## Por que agora é seguro voltar a escolher empresa

A decisão de 09/09 tirou a empresa da sessão porque ela era a fronteira entre
**clientes**, e fronteira de cliente não pode morar numa variável de sessão.

Desde 14/09/2026 a fronteira entre clientes é a **conta**, gravada em cada
linha de negócio (`conta_guid`, ver `CLAUDE.md` §7). Escolher empresa dentro da
mesma conta deixa de ser atravessar para outro cliente: é escolher contexto
dentro dele. A sessão volta a guardar empresa e filial — e continua sendo
conferida contra o que a pessoa alcança a cada requisição.

## Decisões

### D1 — O cargo é da ALOCAÇÃO, não da pessoa

A mesma pessoa pode ter cargos diferentes em lugares diferentes: Ana é Gerente
na Filial Centro e Vendedora na Filial Norte. A permissão vale só onde ela está
trabalhando naquele momento.

### D2 — Cada empresa tem o próprio dado, como hoje

Catálogo, preço, ficha e orçamento continuam sendo de uma empresa. Trocar de
empresa no cabeçalho troca o que se vê. Nenhuma tabela de negócio muda de dono;
`empresa` diz de quem é, `conta_guid` continua sendo a fronteira entre clientes.

### D3 — O dono da conta não tem cargo

O titular alcança tudo da conta por ser dono: todas as empresas, todas as
filiais, todas as permissões de conta. Ele não é alocado, e por isso não
consegue trancar a si mesmo para fora editando o próprio cargo.

A MW5 (MASTER) continua como hoje.

### D4 — Os cargos de fábrica

Toda conta nasce com cinco: **Supervisor, Gerente, Vendedor, Representante e
Cliente**. O titular cria outros. "Comprador" passa a se chamar **Cliente**.

### D5 — O alcance do cargo é dado, não código

Além das permissões, cada cargo diz **quais registros enxerga**: os próprios, a
filial ou a empresa. Cargo criado depois escolhe o alcance numa caixa, e nenhuma
regra depende do nome do cargo.

### D6 — Não há carteira, por enquanto

Nenhum cargo fica ligado a clientes específicos. `Usuario.compradores` sai da
regra de visibilidade e **continua no banco sem uso** — o que foi cadastrado não
se perde enquanto a carteira não for redesenhada.

### D7 — Toda empresa tem a Matriz

A empresa nasce com a filial Matriz, e o titular cria as outras depois. O
módulo de filiais passa a nascer **ligado** — revertendo a decisão de 27/08/2026
de que filial não tinha papel neste produto. A semeadura da Matriz, que existia
no `post_migrate` e saiu em 09/09/2026 por criar filial pendurada em empresa sem
dono, volta no `post_save` da empresa.

### D8 — A alocação pode valer para a empresa inteira

Filial em branco na alocação é todas as filiais da empresa, inclusive as criadas
depois. Um Supervisor alocado na empresa enxerga a filial nova sem ninguém
lembrar de alocá-lo de novo.

### D9 — Abordagem: o cargo substitui o perfil, e a permissão é calculada pelo lugar

Rejeitadas:

- **Cargo ao lado do Perfil** — dois jeitos de dar permissão a alguém, que é o
  defeito que o `Group` do Django já causou aqui e o motivo de o `Perfil`
  existir.
- **Copiar as permissões do cargo para `user_permissions` ao trocar de lugar** —
  estado copiado que diverge: duas abas em filiais diferentes brigam pela mesma
  linha, e mudar o cargo não atualiza quem já está logado.

### D10 — Empresa com alocações não troca de titular

Trocar o titular reescreve a conta de todas as linhas da empresa. A alocação liga
uma pessoa e um cargo de UMA conta; reatribuí-la à conta nova criaria linhas que
misturam duas contas. Por isso a troca é recusada enquanto houver alocação — as
alocações saem antes. Decidido na revisão final do plano 1 (14/09/2026).

## O modelo de dados

### `Empresa`

- Sai a restrição `uma_empresa_por_conta`. `dono` e `conta` (`conta_guid`)
  continuam, e passam a significar "a conta dona desta empresa".
- `post_save` na criação cria a filial **Matriz**.

### `Filial`

- `empresa` passa a ser **obrigatória**, depois de a migração resolver as que
  não têm.
- O M2M `Filial.usuarios` sai: o que ele guardava vira alocação.
- A Matriz não se apaga; renomeia-se. Ela é o que garante que toda empresa tem
  pelo menos uma filial.

### `Cargo` (substitui `Perfil`)

| campo | o que é |
|---|---|
| `conta` | FK para `Usuario.guid` (`db_column="conta_guid"`), como toda linha de conta |
| `nome` | slug, único por conta |
| `rotulo` | o que a tela mostra |
| `permissoes` | M2M `Permission`, como no perfil hoje |
| `alcance` | `proprios` / `filial` / `empresa` |
| `e_cliente` | o cargo se comporta como cliente: preço, compra na vitrine, orçamento |
| `de_fabrica` | veio da semeadura; não se apaga |

`e_cliente` existe porque o alcance não basta para dizer quem é cliente: sem
carteira, Vendedor e Cliente poderiam ter o mesmo alcance, e o sistema pergunta
"esta pessoa é cliente?" em quatro lugares — `catalogo/preco.py`,
`catalogo/views_vitrine.py`, `orcamento/views.py` e `orcamento/visibilidade.py`.

**Os cargos de fábrica e o que eles trazem.** Estes são valores iniciais, e
**todos editáveis pelo titular** depois:

| cargo | alcance | cliente | permissões iniciais |
|---|---|---|---|
| Supervisor | empresa | não | `catalogo.ver`, `catalogo.editar`, `orcamentos.ver`, `orcamentos.acompanhar`, `usuarios.editar` |
| Gerente | filial | não | `catalogo.ver`, `catalogo.editar`, `orcamentos.ver`, `orcamentos.acompanhar`, `usuarios.editar` |
| Vendedor | filial | não | `catalogo.ver`, `orcamentos.ver`, `orcamentos.acompanhar` |
| Representante | filial | não | `catalogo.ver`, `orcamentos.ver`, `orcamentos.acompanhar` |
| Cliente | próprios | sim | `catalogo.ver`, `orcamentos.ver` |

Cliente traz o que `Nivel.COMPRADOR` dá hoje em `contas/fabrica.py`. Vendedor e
Representante nascem com alcance **filial** e com `orcamentos.acompanhar`: com
"os próprios" eles não veriam orçamento nenhum (o orçamento não tem responsável,
só `comprador`), e sem `orcamentos.acompanhar` o alcance não teria tela onde
valer. Isso reverte o "parado de propósito" que `contas/fabrica.py` registra para
o nível VENDEDOR em 09/09/2026.

### `Alocacao` (nova)

| campo | o que é |
|---|---|
| `conta` | `conta_guid` |
| `pessoa` | FK `Usuario` |
| `empresa` | FK `Empresa`, obrigatória |
| `filial` | FK `Filial`, **vazia = a empresa inteira** |
| `cargo` | FK `Cargo` |

**Unicidade com duas restrições parciais.** `(pessoa, empresa, filial)` quando a
filial existe, e `(pessoa, empresa)` quando ela é vazia. Com uma restrição só, o
Postgres deixaria duplicar a alocação na empresa inteira, porque `NULL` não é
igual a `NULL` numa unicidade.

As duas restrições permitem, de propósito, que a mesma pessoa tenha na mesma
empresa uma alocação na empresa inteira **e** outra numa filial específica — é o
que dá sentido à regra "a mais específica ganha" (ver adiante).

O `save` recusa: cargo de outra conta, pessoa de outra conta, empresa de outra
conta, e filial que não é da empresa.

### `Orcamento`

Ganha `filial` (FK `Filial`, obrigatória depois da migração), gravada com a
filial do contexto no momento em que o orçamento é aberto. Sem ela, o alcance
"a filial" não teria o que filtrar.

### `Usuario`

- `Nivel` fica **MASTER (0)**, **TITULAR (1)** e **MEMBRO (2)** — "membro da
  conta", para quem não é titular. VENDEDOR (2) e COMPRADOR (3) saem: o que eles
  diziam passa a ser o cargo da alocação.
- `Usuario.compradores` fica, sem uso (D6).
- O nível padrão de pessoa nova passa de COMPRADOR para MEMBRO.

### `contas/fabrica.py`

- TITULAR ganha `filiais.editar` — hoje ele não tem, e D7 manda o titular criar
  as filiais da empresa.
- MASTER troca `perfis.*` por `cargos.*`.
- Saem as entradas de VENDEDOR e COMPRADOR; o que elas davam passa a morar nos
  cargos de fábrica.

### O que some

`Perfil`, `Papel`, `Filial.usuarios`, `contas.papel.tem_papel` e `papel_de`, e as
entradas de VENDEDOR e COMPRADOR em `contas/fabrica.py`.

## Onde a pessoa está, e o que ela pode ali

Resolvido **uma vez por requisição** e memorizado, como `empresa_atual` já faz
(`comum.memoria`):

1. **A pessoa** — a sessão, como hoje.
2. **Os lugares que ela alcança:**
   - MASTER: todos;
   - TITULAR: todas as empresas e filiais **ativas** da conta dele;
   - MEMBRO: só onde tem alocação. Alocação na empresa inteira abre todas as
     filiais ativas dela.
3. **O lugar atual** — empresa e filial guardadas na sessão, **conferidas contra
   a lista do passo 2 a cada requisição**. Id que a pessoa deixou de alcançar é
   descartado e cai no primeiro permitido; nunca abre o lugar forjado, nunca dá
   500. É o mecanismo que `empresa_atual` e `filial_atual` já têm, e é o que faz
   tirar uma alocação valer na requisição seguinte, sem novo login.
4. **A alocação vigente** — a da filial exata, senão a da empresa inteira. **A
   mais específica ganha; as duas não somam.** Quem é Gerente da empresa e
   Vendedor na Norte é Vendedor quando está na Norte.
5. **As permissões** — as do cargo da alocação vigente. TITULAR e MASTER mantêm
   as de `contas/fabrica.py`.

**A ordem é imposta pela dependência.** Hoje o `User` da requisição nasce com as
permissões já calculadas (`contas/backend.py`). Agora as permissões dependem do
lugar, e o lugar depende da pessoa: o `User` nasce sem permissões, o lugar é
resolvido, e as permissões do cargo entram depois.

**Por fora nada muda para as telas:** `pode()`, `exigir_permissao` e
`do_contexto` continuam sendo as mesmas portas.

### O alcance vira filtro

Numa função só, em `orcamento.visibilidade`:

| alcance | filtro |
|---|---|
| os próprios | `comprador` = a pessoa |
| a filial | `filial` = a filial atual |
| a empresa | a empresa atual inteira |

TITULAR e MASTER enxergam a empresa atual inteira.

`e_cliente` do cargo vigente substitui `tem_papel(usuario, Papel.COMPRADOR)` nos
quatro lugares que perguntam isso.

### O cabeçalho

Seletor de empresa quando a pessoa alcança mais de uma; seletor de filial dentro
da empresa escolhida. Trocar a empresa leva a filial para a primeira permitida
dentro dela.

## As telas

- **`/empresa`** — volta o botão "Nova empresa" para o titular. Criar empresa
  cria a Matriz.
- **`/filiais`** — as filiais da empresa escolhida no cabeçalho. A Matriz se
  renomeia e não se apaga.
- **`/cargos`** (a tela `/perfis`, renomeada e refeita) — nome, alcance, "é
  cliente" e as permissões em caixas. Cargo de fábrica: permissões e alcance
  editáveis, não se apaga. Cargo com alocação não se apaga, e a tela diz quantas
  pessoas estão nele.
- **`/usuarios`** — o cadastro da pessoa ganha o bloco **Alocações**, uma linha
  por lugar (empresa, filial ou "todas", cargo), com "+ Acrescentar", no mesmo
  desenho das equivalências do cadastro de produto. Some a caixa de nível
  vendedor/comprador.

## Quem pode mexer em quê

- **MASTER e TITULAR** mexem em tudo da conta.
- **Cargos, só o titular edita**, e a trava é por `nivel`, não por permissão.
  Motivo: se editar cargo fosse uma permissão, ela poderia estar num cargo, e
  quem a tivesse marcaria permissão nova no **próprio** cargo e promoveria a si
  mesmo. `cargos.editar` na mão de um Supervisor valeria o mesmo que ser dono.
- **Alocar pessoas** é de quem tem `usuarios.editar`, com duas travas conferidas
  no POST, e não só escondendo opção na tela:
  1. só aloca em lugares que ela mesma alcança;
  2. só dá cargo cujas permissões ela também tem naquele lugar — um Gerente não
     cria um Supervisor.
- **Ninguém edita a própria alocação**, pelo mesmo motivo da trava de cargo.

Isto reverte uma regra escrita: `contas/fabrica.py` hoje não dá `perfis.editar`
ao titular ("permissão é da MW5"). Com Cargos, o titular gere os cargos da conta
dele. As telas `/mw5/*` continuam só da MW5.

### Auditoria

`PERFIL_CRIADO/EDITADO/REMOVIDO` viram `CARGO_CRIADO/EDITADO/REMOVIDO`; entram
`ALOCACAO_CRIADA`, `ALOCACAO_REMOVIDA` e `EMPRESA_CRIADA`. Cada ação entra junto
com o cenário que `tests/test_auditoria.py` exige.

## A migração do que existe hoje

A regra é a mesma do `conta_guid`: **preenche o que sabe deduzir, e para com erro
no que não sabe**. Numa instalação existente, migração parada é o portal fora do
ar (`migrate && gunicorn`), e por isso o README ganha a conferência.

Em ordem:

1. **Matriz.** Empresa sem filial ganha uma. **Filial sem empresa para a
   migração** e lista os ids — não há como deduzir de quem ela é.
2. **Cargos de fábrica** em cada conta.
3. **Perfis viram cargos**, com o mesmo nome, rótulo e permissões:
   - papel comprador → alcance "os próprios", `e_cliente`;
   - papel vendedor → alcance "a filial";
   - **sem papel → "os próprios"**, o mínimo. Pode esconder de alguém algo que
     ele via; é o erro seguro, e a conferência lista esses cargos;
   - perfil com o nome de um cargo de fábrica funde-se nele, e as permissões do
     perfil prevalecem.
4. **Alocações.** Cada pessoa não titular ganha uma alocação por perfil em que
   estava, na empresa da conta dela:
   - quem estava em `Filial.usuarios` é alocado naquelas filiais;
   - quem não estava, na empresa inteira;
   - quem não tinha perfil vai pelo nível: COMPRADOR → Cliente, VENDEDOR →
     Vendedor.
5. **Permissão direta.** No modelo novo a permissão vem só do cargo. Pessoa com
   permissão direta que o cargo dela não cobre **para a migração**, com a lista
   de quem é. Descartar em silêncio seria tirar acesso de alguém sem ninguém
   saber.
6. **`Orcamento.filial`** = a Matriz da empresa do orçamento.
7. **Nível** VENDEDOR e COMPRADOR → MEMBRO.
8. **Só depois de copiado:** saem `Perfil`, `Papel` e `Filial.usuarios`.

**Sem desfazer.** A fusão de perfis e a troca de nível apagam informação que não
volta. Voltar é restaurar o backup de antes.

**A conferência do README**, para rodar com a versão antiga no ar, lista:

- filiais sem empresa — **bloqueia**;
- pessoas com permissão direta fora do perfil — **bloqueia**;
- perfis sem papel que vão virar "os próprios" — **aviso**.

## Como se prova

Cada trava abaixo é testada, e o teste é quebrado de propósito para ver vermelho
antes de valer (`CLAUDE.md` §5):

- **Pessoa sem alocação** não vê empresa, dado de negócio nem permissão.
- **Lugar forjado** na sessão ou na URL é descartado e cai no primeiro permitido.
- **A mais específica ganha**: Gerente na empresa e Vendedor na Norte é Vendedor
  na Norte.
- **Tirar a alocação vale na requisição seguinte.**
- **Escalada:** quem tem `usuarios.editar` não dá cargo com permissão que não
  tem, não aloca fora do próprio alcance, não edita a própria alocação; só o
  titular edita cargo.
- **Alcance:** os próprios / a filial / a empresa, com orçamentos em duas filiais
  e de dois clientes.
- **Unicidade da alocação** na empresa inteira dá `IntegrityError` — a restrição
  parcial.
- **Matriz:** empresa nova nasce com ela; a Matriz não se apaga.
- **Isolamento entre contas:** cargo, alocação e lugar de uma conta não aparecem
  na outra, nem pedidos pelo id.

**A migração** é testada com o `Migrator` do `django-test-migrations`, como
`tests/test_migracao_uma_conta_uma_empresa.py` já faz: monta o banco antigo com
perfis, papéis, filiais e permissão direta, migra, e confere cada caso — inclusive
os dois que param com erro.

**As varreduras** passam a olhar `Cargo` e `Alocacao`: inquilino
(`test_regra_do_inquilino.py`), GUID (`test_regra_guid.py`), auditoria
(`test_auditoria.py`) e tabela (`test_regra_tabela.py`).

## Ordem de construção

Cada fase fecha com a suíte verde.

1. **Models** — `Cargo`, `Alocacao`, `Orcamento.filial`, a Matriz na empresa
   nova, os cargos de fábrica. Ainda sem ligar em nada.
2. **Lugar e permissões** — a resolução descrita acima, atrás das funções de
   hoje.
3. **Alcance e cliente** — a visibilidade de orçamento pelo alcance, e
   `e_cliente` no lugar do papel.
4. **Telas** — cargos, alocações no cadastro de usuário, nova empresa, filiais.
5. **Migração** dos dados de hoje, com a conferência do README.
6. **Limpeza** — saem `Perfil`, `Papel`, `Filial.usuarios` e os níveis antigos.
   `CLAUDE.md` §7 e README.

A migração vem depois do código novo de propósito: ela precisa saber para onde o
dado vai, e esse destino só existe depois da fase 4.

## Fora deste desenho

- **Carteira** (D6) — o vínculo entre um cargo e clientes específicos.
- **Responsável pelo orçamento** — sem ele, "os próprios" só tem sentido para o
  cliente.
- **O `performon-novo`** — foi copiado antes de `conta_guid` e não tem nada disto.
