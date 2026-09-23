# Fila Zero — o que você precisa saber antes de mexer

O **Fila Zero** é o SaaS da **fila da vez** das lojas: cada vendedor bate o
ponto, entra na fila, atende na sua vez e lança se vendeu (e o quê) ou por que
não vendeu. O primeiro cliente é a Sylvia Design (a conta é a Sylvia, a empresa
é a Sylvia Design, as lojas são as filiais). O negócio mora no app `fila/` e é
descrito no §10.

Ele nasceu da **KRONOS base** (commit `be166c4`, ver `PROVENIENCIA.md`): conta,
empresa, filial, usuário, cargos e alocações, permissão, auditoria, aparência,
módulos, parâmetros, backup e o design system vieram de lá, e as seções 1 a 9
continuam descrevendo essa base. A base, por sua vez, saiu do **Portal de
Vendas** (commit `d88fb33`), que saiu do KRONOS.net.

Quase tudo que parece estranho no código tem um motivo escrito ao lado, e o
motivo costuma ser um defeito que já aconteceu. **Leia o comentário antes de
reescrever qualquer peça.**

---

## 1. Como um SaaS nasce da base

O Fila Zero já seguiu este roteiro (identidade, app `fila/`, varreduras,
permissões de nascença). Ele fica aqui porque é o mapa do que a base espera de
um produto, e porque um módulo de negócio novo neste produto passa pelos
passos 3 a 5.

1. **Copiar a pasta** sem `.git`, `.venv`, `midia/` e `backups/`, e escrever um
   `PROVENIENCIA.md` dizendo de qual commit da base ele saiu.
2. **Trocar a identidade.** Isso inclui `MARCA_PADRAO` em `plataforma/marca.py`
   (hoje só `KRONOS`), o `name` do `pyproject.toml`, o nome da imagem em
   `.github/workflows/publicar-imagem.yml` e `deploy/docker-compose.vps.yml`,
   e as portas do `docker-compose.yml`.
3. **Criar os módulos de negócio** como apps próprios. A forma está em
   `modulos/exemplo/`. Registre-os em `INSTALLED_APPS` (`config/settings.py`)
   e em `config/urls.py`, e ponha as pastas deles nas varreduras que listam
   pastas (`test_camadas_nao_se_invertem.py`, `test_id_do_post.py`,
   `test_sublinhado_e_o_gettext.py`, `test_html_preguicoso_nao_e_seguro.py`,
   `test_regra_guid.py`, `test_esconder_vence_o_display.py`).
4. **Dar as permissões de negócio a quem nasce com elas**: os cargos de fábrica
   em `contas/cargos_de_fabrica.py` e o titular em `contas/fabrica.py`. Na base,
   só Supervisor e Gerente trazem permissão (`usuarios.editar`).
5. **Tabela de negócio herda `contas.inquilino.ModeloDaEmpresa`** (§7). Se ela
   precisar do alcance "a filial", guarda a filial em que aconteceu, como o
   orçamento do Portal.

**A base é uma pasta, e não um pacote.** Correção feita aqui não chega sozinha
nos SaaS que já nasceram, nem no Portal: cada um é uma cópia. Uma correção de
base precisa ser levada à mão a cada produto, ou a base precisa virar pacote.
Essa decisão ainda está em aberto (§9).

## 2. As quatro alavancas, e o que é proibido

A máquina nasceu para a MW5 ter **um** sistema por produto, e não um por
cliente. Todo cliente roda a **mesma imagem**, com VPS e banco próprios. O que
varia de um para outro é **dado no banco**, nunca código.

| alavanca | onde mora |
|---|---|
| módulo ligado/desligado | `plataforma/declaracao.py`, `plataforma/catalogo.py` |
| permissão | `contas/permissoes.py`, `nucleo/permissoes.py`, `contas/lugar.py` |
| parâmetro | `plataforma/parametro_declaracao.py`, `plataforma/parametro_catalogo.py` |
| aparência | `plataforma/marca.py`, `nucleo/theme/` |

(`plataforma/catalogo.py` é o catálogo **de módulos**, e não tem relação com
o catálogo de produtos do Portal.)

Se uma particularidade de cliente não cabe em nenhuma das quatro, **pare**. Ou
falta um mecanismo, e aí ele se constrói, ou a regra foi escrita com o nome de
um cliente dentro. `if cliente == "..."` é defeito de arquitetura, e
`test_sem_nome_de_cliente.py` o recusa.

## 3. As pastas, e o que cada uma pode

Camadas, de dentro para fora: `nucleo` ← `comum` ← `plataforma` ← `contas`.
Importar na direção contrária recria o ciclo que já foi quebrado uma vez.

**Os módulos de negócio ficam por cima de TODAS, e a base nunca importa um
deles.** No Portal de Vendas, o `backupar` passou a importar do catálogo sem
ninguém ver. Camada invertida não dói enquanto existe um consumidor só, e o
backup só quebrou na primeira cópia para outro produto (`No module named
'catalogo'`). `test_camadas_nao_se_invertem.py` cobra. **Esta pasta é a prova
de que a regra vale:** é a base sem módulo de negócio, e a suíte passa inteira.

- **`nucleo/`** — o design system. **É PORTE VERBATIM** do pacote `mw5_admin`
  e **não se emenda aqui**. Só `nucleo/views.py` é autoral. Correção de lá vai
  numa folha desta casa (`plataforma/static/plataforma/kronos.css`, que carrega
  depois da `mw5.css`), com o motivo ao lado da regra.
- **`comum/`** — o que mais de uma camada usa: guardas de acesso e de módulo,
  listagem (filtro, ordenação, paginação), CSRF, auditoria, sessão,
  personificação, exportação, confirmação.
- **`contas/`** — gente: entrar, sair, sessão, usuário, nível, cargos,
  alocações, lugar e permissão, "Meu Perfil", avatar, trilha de auditoria,
  personificação ("ver como").
- **`plataforma/`** — a instalação em si: empresa, filial e contexto do
  cabeçalho, marca, catálogo de módulos, parâmetros, falhas, menu, backup,
  mídia, `Site`.
- **`modulos/`** — onde mora módulo de negócio. Na base só existe
  `modulos/exemplo/`, que mostra a forma.
- **`fila/`** — o negócio do Fila Zero (§10). É app de primeiro nível, e não
  pasta dentro de `modulos/`, por ser o produto inteiro; para as varreduras
  ele é negócio como qualquer outro.
- **A API do app** mora em `api.py`, ao lado do `views.py` de cada pasta, e é
  juntada em `config/api.py`, sob `/api/`. Veio do Portal de Vendas em
  15/09/2026, sem a pasta `app/` (o Expo é de cada produto): a base entrega a
  moldura — entrar, sair, `/api/v1/eu`, tema, entrada, filial e a lista de
  filiais —, e cada SaaS acrescenta o router do negócio dele em
  `config/api.py::_routers`. As duas cascas chamam a mesma regra e não se
  importam (`test_api_nao_importa_view.py`). O token é a própria chave da
  sessão Django, lida do cabeçalho `Authorization` — em `/api/` o cookie é
  ignorado, e é isso que torna segura a isenção de CSRF
  (`comum/sessao_por_cabecalho.py`). A decisão de acesso é a MESMA da web
  (`comum.guardas_de_acesso.barreira`), traduzida em HTML ou JSON. O contrato
  sai por `python -m config.openapi`, e `FILA_APP_MINIMO` é a versão mínima
  do app que ainda abre.
- **`config/`**, **`deploy/`**, **`locale/`**, **`docs/`** — configuração,
  publicação, as traduções (§8) e as decisões escritas. Em `docs/`, os
  `plans/` e `specs/` são registros datados: descrevem o dia em que foram
  escritos, e alguns falam do Portal.
- **`midia/`** — onde a instalação guarda ARQUIVO (`plataforma/midia.py`).
  Quem grava lá dentro é o módulo de negócio. **Não é código e não entra no
  git**: é estado, como o banco, e sai no mesmo backup que ele. Avatar e logo
  continuam sendo bytes em tabela, porque são poucos e pequenos.
- **`tests/`** — 147 arquivos. Rodam em ~6 min (Postgres, `KRONOS_BANCO`
  obrigatório).

## 4. As regras com número

Estão em `docs/superpowers/decisoes-2026-08-20-fatia-fina.md`, com o raciocínio
inteiro:

- **R46 — toda tabela tem filtro por coluna, ordenação e paginação.**
  `test_regra_tabela.py` fica vermelho se uma tela nova esquecer.
- **R47 — módulos fixos.** O código declara o que um módulo é; o banco diz
  quais estão ligados. Módulo novo aparece sozinho em todas as instalações,
  desligado (salvo `ativo_por_padrao=True`, escrito com o motivo).
- **R48 — o logo do rodapé é do produto e não troca.** O cliente veste a
  entrada e o menu; o rodapé é a assinatura de quem fez. Se cada SaaS assina
  como KRONOS ou com a própria marca é decisão de produto (§9).

## 5. As varreduras — o que já é impossível esquecer

Cada uma existe porque o esquecimento correspondente já custou caro. Elas
falham na suíte, e não em produção:

| arquivo | o que recusa |
|---|---|
| `test_guarda.py` | rota ou operação de API sem guarda de acesso |
| `test_guarda_modulo.py` | rota de módulo sem `@exigir_modulo_ligado`; operação de API sem módulo nem motivo em `SEM_MODULO_NA_API` |
| `test_personificacao.py` | tela sem o aviso de "você está vendo como"; resposta de API sem `X-Vendo-Como` |
| `test_regra_tabela.py` | tabela ou lista da API sem filtro/ordenação/paginação |
| `test_api_ignora_cookie.py` | `/api/` aceitando sessão por cookie, ou gravando cookie |
| `test_api_nao_expoe_id.py` | esquema da API com `id`, `pk` ou `*_id` sequencial |
| `test_api_nao_importa_view.py` | `api.py` importando `views*` (ou o contrário), ou adiando anotações com `__future__` |
| `test_api_tema.py` | `/api/tema` diferente dos tokens do `/tema.css`, ou fechada |
| `test_falha_da_api_e_gravada.py` | exceção em rota de API sem linha em `Falha` |
| `test_barreira.py` | a decisão de acesso divergindo entre a web e a API |
| `test_sem_nome_de_cliente.py` | nome de cliente escrito no código |
| `test_regra_do_inquilino.py` | tabela de negócio sem a coluna da empresa e da conta (`conta_guid`) |
| `test_toda_linha_da_conta_leva_o_guid.py` | tabela sem `conta_guid` fora de `DA_INSTALACAO`, ou tabela de empresa cuja `conta` não é FK para `Usuario.guid` |
| `test_filial_em_ordem_de_dicionario.py` | filial com `ordem` de volta, ou fora da ordem de dicionário |
| `test_regra_guid.py` | tabela nossa sem GUID |
| `test_sublinhado_e_o_gettext.py` | `_` usado como descarte, sombreando o `gettext` |
| `test_html_preguicoso_nao_e_seguro.py` | `format_lazy` com HTML dentro (sai escapado na tela) |
| `test_esconder_vence_o_display.py` | classe escondida por script sem `[hidden] { display: none }` |
| `test_variavel_de_cor_existe.py` | folha citando `var(--token)` que ninguém declara |
| `test_id_do_post.py` | id cru do POST indo para a consulta (`<select>` vazio vira 500) |
| `test_documentacao_nao_mente.py` | CLAUDE.md ou README afirmando número, arquivo ou decisão que não confere |
| `test_camadas_nao_se_invertem.py` | base importando módulo de negócio |
| `test_o_perfil_saiu.py` | `Perfil`, `Papel`, `/perfis` ou os níveis antigos voltando |

**Na base, a varredura do inquilino olha para um app de mentira**
(`tests/app_do_inquilino`), porque não existe tabela de negócio de verdade.
Ele fica FORA da lista de exceção de propósito: isentá-lo para "fazer passar"
deixa a varredura cega.

Se você está prestes a acrescentar um nome a uma lista de isenção, escreva
**o motivo** ao lado. Uma isenção sem motivo vira gaveta, e gaveta ninguém
relê.

## 6. Como se trabalha aqui

- **Comentário diz POR QUÊ, não o quê.** O código já diz o que faz. O que se
  perde é a razão, e é ela que impede alguém de "simplificar" de volta para o
  defeito. Português, frase inteira.
- **Teste com dente.** Depois de escrever um teste, **quebre o código de
  propósito** e veja o teste ficar vermelho, depois desfaça. Teste que passa
  com o código quebrado é pior que teste nenhum.
- **Mensagem de commit longa, em português**, dizendo o que estava errado antes
  e por que a correção é essa. `feat:`/`fix:`/`refactor:`/`docs:`/`test:`.
- **Nunca** adicionar Claude como coautor, nem rodapé de "gerado com". Autor:
  `João Victor Vancim <developer1@kronos.net.br>`.
- **Nada de produção, servidor, FTP ou credencial** sem autorização explícita
  no pedido.

---

## 7. A conta, as empresas e a gente

Specs: `docs/superpowers/specs/2026-09-02-saas-identidade-e-acesso-design.md`,
`…/2026-09-09-uma-conta-uma-empresa-design.md` e
`…/2026-09-14-cargos-e-alocacoes-design.md`. Os planos dos cargos
(`docs/superpowers/plans/2026-09-14-cargos-*.md`) têm as decisões R1–R10 que o
spec não respondia.

### Os níveis

**Três níveis, num inteiro** (`contas.models.Nivel`), do mais poderoso para o
menos. É o que faz `nivel <= Nivel.TITULAR` significar "titular ou acima" sem
ninguém decorar lista:

| nível | quem é |
|---|---|
| `MASTER` (0) | a MW5. Não é cliente de conta nenhuma |
| `TITULAR` (1) | o dono da conta e da empresa dela — quem assina o SaaS |
| `MEMBRO` (2) | alguém da conta. O que faz vem do CARGO da alocação |

É inteiro, e não texto, porque uma coluna de texto vira `"titular"`, `"Titular"`
e `"ADMIN"` ao mesmo tempo. **Só a MW5 escolhe nível** na tela de Usuários. O
titular cadastra membros, e um titular criado por ele seria um cliente novo do
SaaS.

### Uma conta, várias empresas

A empresa aponta para o titular dono (`Empresa.dono`, `UNIQUE` no banco — trava,
não convenção), e a pessoa aponta para a conta a que pertence (`Usuario.dono`,
FK para `self`). A empresa de alguém é **derivada**, e não guardada na pessoa:
da conta, para o titular, e das alocações, para o membro
(`contas.alcance.empresa_de`).

- **`empresa_de` devolve `None` para o MASTER, nunca "todas".** Devolver
  "todas" faria um `filter(empresa=empresa_de(u))` escrito com pressa virar
  vazamento silencioso no dia em que a MW5 abrisse a tela.
- **`Usuario.dono` é nulo em dois casos**, os dois de propósito: o MASTER (não é
  de conta nenhuma) e o próprio titular (ele É a conta).
- **Várias empresas por conta existem desde 17/09/2026** (spec
  `2026-09-17-varias-empresas-por-conta`). A trava `uma_empresa_por_conta`
  caiu: a conta é o CLIENTE, e ele pode ter mais de uma pessoa jurídica. O
  que separa o dado de negócio continua sendo a coluna `empresa` de cada
  linha; o `conta_guid` continua obrigatório e derivado dela, e diz de QUEM
  é a linha. O cabeçalho mostra o seletor para quem alcança mais de uma — a
  MW5 (rótulo "Conta") e o titular com várias (rótulo da marca, "Empresa").
  A marca do menu segue a empresa escolhida
  (`plataforma.marca.empresa_da_marca`), e a MW5 por si mesma continua vendo
  a da instalação.

### A conta em cada linha: `conta_guid`

Toda tabela de negócio carrega, além da `empresa`, a **conta dona** na coluna
`conta_guid`: uma FK para `Usuario.guid`, `NOT NULL`. É o **GUID** da conta, e
não o id desta instalação, porque é a identidade estável do cliente, e toda
integração usa esta coluna. A empresa e o usuário também têm a sua.

- **Tabela de negócio herda `contas.inquilino.ModeloDaEmpresa`.** Ele traz a
  coluna, o manager que falha vazio (`do_contexto`, `da_empresa`, `da_conta`) e
  a passagem pela varredura. `ModeloDaEmpresa.save` preenche `conta` sozinho a
  partir da empresa, e recusa empresa **sem titular** e conta **diferente** da
  titular.
- **Não é só negócio** (16/09/2026). `Filial` e `AparenciaDaEmpresa` levam
  `conta_guid` (nulo só enquanto a empresa não tem titular, derivado em
  `plataforma.models._conta_da_empresa`), e a trilha de auditoria guarda o
  GUID da conta de quem agiu (`RegistroDeAuditoria.conta_guid`, valor e não
  FK — nulo para a MW5). `test_toda_linha_da_conta_leva_o_guid.py` cobra
  TODA tabela; as da instalação ficam numa lista com o motivo.
- **A filial não tem `ordem`** (16/09/2026): a Matriz vem na frente e as
  outras pelo nome, com colação ICU (`comum.alfabetica.DE_DICIONARIO`),
  porque o Postgres do Alpine ordena byte a byte.
- **`Empresa.conta` e `Usuario.conta` são derivadas no `save`**, de `dono`. Não
  se grava `conta` à mão. No usuário, o **titular aponta para o próprio GUID**:
  `filter(conta=<guid>)` traz a conta inteira, titular incluído. A MW5 fica
  nula.
- **`bulk_create` e `QuerySet.update(dono=...)` não passam pelo `save`.** Quem
  usar acerta `conta` junto. Numa tabela de negócio, esquecer não grava errado:
  o banco recusa, porque a coluna é `NOT NULL`.
- **Trocar o titular de uma empresa reescreve o `conta_guid` de todas as linhas
  dela**, na mesma transação. Empresa com alocação **não troca de titular**: a
  alocação liga pessoa e cargo de UMA conta.
- **Nos testes**, empresa que recebe dado de negócio precisa de titular antes:
  `tests/conftest.py` tem `abrir_conta(empresa, login)`.

### Cargos e alocações

**O cargo é da ALOCAÇÃO, e não da pessoa.** `contas.Alocacao` diz: esta pessoa,
nesta empresa (numa filial, ou na empresa inteira), com este `contas.Cargo`. A
mesma Ana é Gerente na Centro e Vendedora na Norte. O cargo carrega:
- as **permissões**;
- o **alcance**: só os registros da própria pessoa, os da filial ou os da
  empresa. O rótulo de cada opção diz o que se enxerga desde 18/09/2026 (o
  cliente: "não fica muito bem entendido o que seria os próprios"), e o campo
  tem uma frase de apoio com os três — antes era "Os próprios", "A filial" e
  "A empresa", e nenhum deles respondia "os próprios do quê";
- se é de **cliente** (`e_cliente`): quem compra da empresa, e não quem trabalha
  nela.

Toda conta nasce com **Supervisor, Gerente, Vendedor, Representante e Cliente**
(`contas/cargos_de_fabrica.py`), e o titular cria outros em `/cargos`.

**Cada cargo diz quais cargos pode conceder** (`Cargo.pode_conceder`,
17/09/2026): o Gerente de fábrica cria Vendedor, e o Supervisor cria Vendedor
e Gerente. Lista vazia é a regra de antes (só permissões e alcance), e por
isso a lista é uma trava A MAIS, nunca a menos — marcar Supervisor na lista
do Gerente não o faz poder dar Supervisor. A semeadura preenche a lista dos
cargos de fábrica que estiverem vazios, inclusive nas contas que já existem.

**A tela de Usuários procura por CARGO, e não por nível** (18/09/2026, pedido
do cliente): a coluna e o filtro eram NÍVEL, e como quase todo mundo é MEMBRO,
a lista inteira escrevia "Usuário" e não respondia "quem é o gerente aqui?". A
coluna mostra os cargos da pessoa (dois, se ela tem dois, e "—" para o titular
e a MW5, que não são alocados), e a ordenação usa a anotação
`cargo_ordem = Min("alocacoes__cargo__rotulo")`: ordenar pelo caminho da
relação devolveria a pessoa DUAS vezes, que é a linha repetida que a coluna
existe para evitar.

**A tela de Usuários tem coluna e filtro de FILIAL** (23/09/2026, pedido do
cliente: "falta filtrar por loja/filial"). É a filial da ALOCAÇÃO — o lugar em
que a pessoa trabalha —, e não a da ficha da pessoa, que morreu em 14/09/2026:
sem a coluna, só dava para saber em que loja alguém está abrindo o modal de
cada linha. A ordenação usa `loja_ordem = Min("alocacoes__filial__apelido")`,
pelo mesmo motivo do cargo (o caminho da relação devolveria a pessoa duas
vezes), e a alocação sem filial escreve "Todas as filiais", que é o que ela
significa.

**E o filtro de Cargo** (23/09/2026, com o print do cliente na mão: "o filtro
de cargo tá vindo errado"): `_cargos_para_escolha` devolvia a lista de rótulos
SOLTOS, e a caixa de escolha desempacota cada opção em `(valor, rótulo)` — uma
STRING se desempacota em CARACTERES, e o filtro oferecia "l", "e", "e", "u",
"e", que são a segunda letra de Cliente, Gerente, Representante, Supervisor e
Vendedor. O par é `(rotulo, rotulo)`, porque é o rótulo que a coluna compara.

**Titular e MW5 não têm cargo.** As permissões deles são diretas, de
`contas/fabrica.py`. Um cargo no dono permitiria trancá-lo para fora da própria
conta.

**`contas/lugar.py` é a porta de "onde a pessoa está e o que pode ali".** Ela
cobre:
- empresas e filiais alcançadas;
- a alocação vigente, em que **a mais específica ganha e as duas não somam**;
- permissões e alcance do cargo, `e_cliente` e `clientes_alcancados`;
- as travas contra escalada (`pode_dar`, `pode_administrar`).

O que custa quando se esquece:

- **Pessoa → lugar → permissões.** `comum.sessao.identidade_da_sessao` diz quem
  é; `usuario_da_sessao` acrescenta as permissões do cargo no lugar atual.
  **`plataforma.contexto` só lê a primeira.** O lugar depende da pessoa, e ler a
  segunda lá dentro fecharia um círculo. O backend já entrega o membro sem
  permissão nenhuma, como segunda tranca.
- **A permissão direta de membro não vale**, nem se estiver no banco. Nos
  testes, dê permissão a um membro com `tests.conftest.dar_permissoes` ou com
  `alocar(pessoa, empresa, cargo_com(...))`, e nunca com
  `user_permissions.add`.
- **Quem aloca é conferido no POST**, no bloco Alocações da tela de Usuários:
  - só aloca onde alcança;
  - só dá cargo com permissões E alcance que ele mesmo tem ali (Gerente e
    Supervisor de fábrica diferem só no alcance);
  - ninguém administra a si mesmo, e por isso ninguém edita a própria alocação;
  - quem não é titular só vê, em Usuários, quem ele poderia ter alocado.
- **Só o nível edita cargo.** A permissão `cargos.editar` só põe a tela no menu,
  e as caixas nunca oferecem as permissões de Cargos: com elas num cargo, quem
  o tivesse se promoveria.
- **O alcance é a segunda fronteira.** Vendedor e cliente alcançam a MESMA
  empresa, e mesmo assim um cliente não vê os registros do outro. Isolar o
  inquilino não isola nada DENTRO dele. A carteira (`Usuario.compradores`)
  está fora da regra e fica no banco, sem uso.

### Filial

- **Toda empresa tem a Matriz**, criada no `post_save` da empresa e marcada por
  campo (`Filial.e_matriz`), porque o titular pode renomeá-la. A Matriz não se
  remove.
- **`Filial.empresa` é obrigatória**, e a filial é o lugar da alocação. O
  cabeçalho mostra o seletor de filial para quem alcança mais de uma, e o id
  forjado na sessão cai na primeira filial permitida.
- **A tela de Filiais enxerga só a empresa do contexto**
  (`plataforma/views_filiais.py`, `_filiais_da_empresa`), e só por isso o
  titular tem `filiais.editar`. Uma filial não se remove em três casos, e
  "última filial ativa" é contada dentro da empresa (`plataforma/filiais.py`):
  - com alocação;
  - protegida por qualquer tabela de negócio com `PROTECT` — perguntado ao
    próprio Django, porque a base não conhece os módulos;
  - se for a última ativa da empresa.
- **A tela de Filiais tem o seletor de EMPRESA** (23/09/2026, pedido do
  cliente: "quando eu for criar filial num dono de conta com mais de uma
  empresa, preciso de um seletor para dizer de qual filial é aquela empresa").
  A lista, a exportação, as ações e a filial nova seguem a empresa escolhida
  (`?empresa=`, validada contra as empresas da CONTA — um id de fora cai na
  empresa do contexto, que é a trava de sempre), e a escolha viaja nos links da
  tabela (`preservar=("empresa",)`) e no POST das ações. No celular a faixa de
  contexto do cabeçalho está escondida, e sem este campo a tela só enxergava a
  empresa em que a sessão estava — a filial recém-criada na outra não aparecia.
- **O módulo de Filiais nasce ligado** desde 17/09/2026
  (`ativo_por_padrao=True`): a filial é A LOJA da fila, e a conta tem várias
  empresas, cada uma com as lojas dela — sem a tela, o titular não cadastra a
  loja da segunda.

### O menu de cada empresa (15/09/2026, vindo do Portal)

- `plataforma.AparenciaDaEmpresa` guarda **logo, fundo e texto do menu** de uma
  empresa. **Só a MW5 configura** (`mw5.aparencia`), num modal da tela de
  Empresas; o titular não mexe.
- **Toda tela logada usa `plataforma.marca.marca_da_requisicao(request)`** (via
  `montar_site`): a marca da instalação com o menu da empresa de quem é VISTO
  por cima — a MW5 vê a instalação, e em "ver como" vê a do cliente. Campo em
  branco herda; entrada, rodapé (R48) e o resto do tema não mudam. Com cor
  própria, hover e selecionado voltam a ser derivados dela.
- **O `/tema.css` continua da instalação e aberto.** As cores da empresa vêm de
  `/tema-da-empresa.css`, carregada depois da folha da casa, com
  `Cache-Control: private`. O logo sai por `/marca/empresa/menu`, sempre o da
  empresa de quem pede — nunca por id na URL.
- **O logo perde a margem na gravação** (`plataforma/logo.py`): a barra ajusta o
  arquivo inteiro à caixa, e borda branca no arquivo é desenho menor no menu.
  É por isso que o Pillow é dependência de PRODUÇÃO desta base.

### O cabeçalho: o lugar e o sair (18/09/2026)

- **O contexto é duas pílulas com ícone**, e não "Empresa [ ] Filial [ ]": os
  rótulos saem da TELA, não do HTML (continuam sendo o `<label>` que o leitor
  de tela lê). São os mesmos dois `<select>` do design system, e a troca
  continua funcionando sem JavaScript. Tudo em
  `plataforma/static/plataforma/kronos.css`, com `:has` como trava — num
  navegador que não o entende, o seletor fica o de antes, inteiro. O ícone é
  escolhido pelo id (`#ctx-empresa_id`, `#ctx-filial_id`), nunca pela ordem:
  quem alcança uma empresa só tem UM nível na faixa, e ele é o da filial.
- **Sair saiu do canto e foi para o menu do avatar**, em vermelho, junto de
  "Meu Perfil" (`plataforma/site.py::_user_info`; o ícone solto morreu com
  `logout_href=None` no cabeçalho). A pergunta é um diálogo POR CIMA da
  página (`plataforma/sair.py`, em `overlays` de toda tela do shell), aberto
  pelo `plataforma/static/plataforma/sair.js`.
- **Trocar de empresa ou de loja pergunta no mesmo diálogo** desde
  18/09/2026 (`plataforma/trocar.py`, `plataforma/static/plataforma/
  contexto.js`): o servidor desenha os DOIS formulários, e o script mostra o
  que vale, escreve o nome escolhido como TEXTO e põe o id no campo. O
  `change` é ouvido na fase de CAPTURA, senão o `data-auto-enviar` do design
  system navega antes. O campo volta na hora ao valor de agora — cancelar não
  pode deixar o cabeçalho mostrando um lugar onde a pessoa não está. O
  diálogo só existe para quem tem o que trocar, e quem age continua sendo o
  POST de `empresa_trocar`/`filial_trocar`.
- **A página `/sair` continua sendo a única que age**, e o item do menu é um
  `<a href="/sair">` de verdade: sem JavaScript cai na confirmação de sempre
  (`comum/confirmacao.py`), e o POST continua sendo o único jeito de sair.
  `tests/test_sair_sem_sair_da_pagina.py` cobra as duas pontas.
- **As pílulas ficam no CENTRO do cabeçalho, mais largas, e com o nome no meio
  da pílula** (18/09/2026, pedido do cliente — foram três pedidos, e o terceiro
  só ficou claro depois de o cliente ver o segundo: "não centralizou dentro da
  pílula").
  - **O par no centro:** o `.ctx` do design system já centra o par DENTRO da
    faixa do meio, e o problema era a faixa — numa linha flex, com a migalha de
    um tamanho e as ações de outro, o centro dela não é o do cabeçalho. O
    `header .wrap` virou uma grade de três colunas (1fr, 2fr, 1fr) na folha
    desta casa, com o botão do menu e a migalha dividindo a primeira. Os
    `minmax(0, …)` estão lá porque o `1fr` do CSS nunca encolhe abaixo do
    conteúdo, e o `.crumb` do design system se recusa a esticar: sem os dois, o
    par sai 35px à direita do centro.
  - **O nome no meio da pílula:** o ícone fica à esquerda e o chevron à
    direita, com o MESMO vão dos dois lados (`padding: 0 34px`). São dois
    caminhos e os dois precisam disto — o seletor nativo é caixa de texto
    (`text-align: center`) e o desenhado por nós (`appearance: base-select`) é
    caixa flex (`justify-content: center`), com o `::picker-icon` FORA do fluxo
    (absoluto): como item flex ele entraria na conta e centraria o grupo
    [texto + ícone], deixando o texto fora do centro.
  - **O `position` vai no `.ctx-nivel`, NUNCA no campo.** O ícone da esquerda é
    um `::before` do contêiner desenhado por baixo do campo, e um elemento
    posicionado pinta DEPOIS dos pseudo-elementos dele: pôr `position:
    relative` no `<select>` (foi o que eu fiz, para ancorar o chevron) faz o
    campo cobrir o ícone. Ele continua no documento, e a tela mostra a pílula
    sem ícone — foi assim que o cliente viu, e
    `test_o_campo_da_pilula_nao_e_posicionado` é o que impede a volta.

  As duas medidas saíram do navegador (Chrome headless, print lido por
  script): o par com +0px do centro do cabeçalho e a letra com +0px do centro
  da pílula.
- Abaixo de 1000px o design system esconde a faixa de contexto inteira
  (`.ctx-mid { display: none }`): no celular ninguém troca de empresa nem de
  loja pelo cabeçalho. É de lá, e continua como estava.

### As telas no celular (18/09/2026)

Três correções do mesmo dia, medidas no Chrome headless com 390px de largura:

- **O rodapé do diálogo centraliza os botões.** As telas de Usuário e de
  Empresa põem as ações em `.ct-rodape` e `.ep-rodape`, e no celular os botões
  ficam empilhados e de largura inteira desde sempre. Faltava o rótulo DENTRO
  do botão: `.btn` é caixa flex e o `justify-content` que ele herda é `normal`,
  que numa caixa flex quer dizer `flex-start` — o texto ficava colado na borda
  esquerda (medido: botão de 335px começando em x=43, texto a partir de x=60,
  centro do texto em 93 e do botão em 211). `justify-content: center` no
  `@media` de 620px de cada folha, com o motivo escrito nas duas.
- **O campo de arquivo do "Meu Perfil" não vaza mais do cartão.** O
  `<input type="file">` do `nucleo` não encolhe, e a largura mínima do conteúdo
  — o botão nativo mais "Nenhum arquivo escolhido" — é maior que a coluna ao
  lado do avatar: o campo ia até 399px numa tela de 390, e a página inteira
  ganhava rolagem horizontal (`scrollWidth` 399 contra `clientWidth` 390).
  `min-width: 0` na folha desta casa (`kronos.css`) resolve: item de flex nasce
  com `min-width: auto`, e `auto` quer dizer "nunca menor que o meu conteúdo".
- **A marca do rodapé não é mais recortada.** O `nucleo` trata todo `<span>` do
  rodapé como linha de texto (`footer > span { overflow: hidden; text-overflow:
  ellipsis }`), e a marca do rodapé TAMBÉM é um `<span>` (`.footer-marca`, em
  `nucleo/templates/layout/footer.html`): com o recorte, a caixa encolhe para a
  altura da linha e a imagem de 40px (`--logo-footer-h`, de
  `plataforma/marca.py`) perdia 8px em cima e 8px embaixo — o cliente viu o "K"
  e o "Kronos" fatiados. Medido: a caixa tinha 24,39px de altura com
  `overflow: hidden`, e volta aos 40px do desenho com `visible`, que é a regra
  desta casa. O recorte continua valendo para o TEXTO do rodapé, que é para
  quem ele foi escrito.

### O que sustenta a permissão

- Login por **e-mail**, pelo usuário deste projeto (`contas.models.Usuario`,
  `AUTH_USER_MODEL`), e não pelo `auth.User` do Django, que não aceita coluna
  nova.
- **Não existe `Perfil` nem `Group` como fonte de permissão.** Dois jeitos de
  conceder a mesma coisa foi o defeito que o `Group` já causou aqui. Coringa por
  módulo vale (`usuarios.*` cobre `usuarios.editar`).
- **Duas camadas, e não uma**: `pode()` decide o que APARECE, e quem TRANCA é a
  rota, com `exigir_permissao`. Esconder item de menu nunca é proteção.
- **A fronteira MW5 × cliente tem duas trancas independentes.**
  - A permissão `mw5.*` **não existe como linha no banco**: `ModuloSpec.so_mw5`
    faz `materializar` pular, e não há o que conceder num cargo.
  - O `is_superuser`.

  Não existe cargo chamado "mw5" de propósito, porque o titular cria cargos e
  cunharia para si a própria promoção.
- **Personificação** ("ver como"): a trilha registra quem agiu de verdade, e
  toda tela avisa.

### Migrações

**As migrações da base começaram do zero** (`0001_initial`). A base não tem
instalação nenhuma, e o histórico herdado dependia do orçamento do Portal.

Migração de DADOS que um SaaS escrever segue a regra da casa. Ela preenche o que
sabe deduzir e **para com erro** no que não sabe, listando todos os casos de uma
vez. Vem também com uma conferência no `README.md` para rodar com a versão
antiga no ar, porque a `app` sobe com `migrate && gunicorn`, e migração parada é
o sistema fora do ar.

`django-test-migrations` fica nas dependências de desenvolvimento para testar
essas migrações contra um banco antigo de verdade. A fixture do `Migrator` pede
`transactional_db` e devolve o esquema ao HEAD no fim (`reset()`). Sem isso, o
banco de teste fica no esquema antigo para o arquivo seguinte.

## 8. O castelhano

O sistema fala português e **castelhano do Paraguai**. Só a **moldura** é
traduzida — menu, formulários, telas da base, tela de entrada e as frases fixas
do design system. **Dado cadastrado não**: traduzir dado seria inventar nome.

- As frases saem por **Babel**, e não pelo `makemessages` do Django. O de lá
  precisa do `xgettext` no sistema e não lê template Jinja2, que é o desta casa.
  A receita completa está em
  `docs/superpowers/specs/2026-09-09-idioma-castelhano.md` (extrair só de
  `contas,plataforma,comum,modulos` e das pastas dos módulos de negócio).
- **Português não tem arquivo**, e não é esquecimento: a frase escrita no código
  É o português.
- `gettext_lazy` para constante de módulo, `gettext_noop` para gabarito de
  comparação, `%(nome)s` nomeado e nunca `{}`.
- O `nucleo` é porte verbatim e não se emenda. As frases dele são traduzidas por
  **template override** em `plataforma/templates/`, e
  `test_cabecalho_da_casa.py` avisa quando o original muda embaixo da cópia.

## 9. O que está em aberto

1. **A base é pasta ou pacote.** Hoje é pasta, e cada SaaS é uma cópia que vai
   divergir sozinha.
2. **O `nucleo` é mais uma cópia do design system** (`mw5_admin`). Uma correção
   do design system precisa ser feita em cada consumidor.
3. **A identidade e a R48.** A base assina como KRONOS no rodapé. Se cada SaaS
   mantém essa assinatura é decisão de produto.
4. **A tela de Conta é só leitura.** Editar os dados do cliente continua na
   tela de Empresas, e quem cadastra empresa é a MW5.

---

## 10. A fila da vez

Spec: `docs/superpowers/specs/2026-09-15-fila-da-vez-design.md`. Plano, com os
cinco ajustes que o spec não respondia (D-1 a D-5):
`docs/superpowers/plans/2026-09-15-fila-da-vez.md`.

### Quem pode o quê

| permissão | o que abre |
|---|---|
| `fila.ver` | a página `/fila` da loja e o item no menu |
| `fila.participar` | bater o ponto, atender, lançar, pausar, sair da loja |
| `fila.gerenciar` | corrigir a fila e os lançamentos da loja em que está |
| `fila.cadastros` | grupos de item, motivos de não venda e tipos de pausa |
| `fila.metas` | a tela `/fila/metas`, nas lojas em que o cargo traz a permissão |

Vendedor traz `ver` e `participar`; Gerente, `ver`, `participar` e
`gerenciar`; Supervisor, `ver` e `gerenciar`; o titular, as quatro
(`contas/cargos_de_fabrica.py`, `contas/fabrica.py`). **`fila.ver` vem primeiro
no `ModuloSpec`** porque o menu entra pela primeira permissão do módulo e some
com os atalhos de quem não a tem.

**Bater o ponto é só de quem atende** (18/09/2026, pedido do cliente): o
supervisor, o gerente e o dono da conta gerenciam a loja e não atendem. A regra
mora em `fila/quem_atende.py`, e **não** na ausência de `fila.participar` —
essa permissão continua no cargo do Gerente e nas do titular de propósito:
`contas.lugar.pode_dar` exige que quem aloca tenha as permissões do cargo, e
sem ela o gerente deixaria de poder conceder o cargo de Vendedor. Quem já está
na loja continua podendo fechar o atendimento que começou (`fila/tela.py` soma
`r.meu` à regra).

**A loja é a filial em que a sessão está** (`filial_atual`), e a permissão é a
do cargo NESSE lugar: o gerente de uma loja não tem `fila.gerenciar` em outra.

### Onde mora cada regra

- `fila/models.py` — os três cadastros, `Presenca`, `LugarNaFila` (o estado de
  agora, uma linha por pessoa presente), `Atendimento` com `ItemVendido`, e
  `Pausa`. **A ordem da fila é `na_fila_desde`**, e voltar para o fim é gravar
  a hora de agora. Os "um aberto por pessoa" são restrições parciais do banco.
- `fila/acoes.py` — o que o vendedor faz. Cada ação **tranca a linha da
  filial**, relê o lugar da pessoa depois da trava e grava tudo ou nada; o que
  não cabe levanta `Recusa` com a frase da tela.
- `fila/correcoes.py` — o que o gerente corrige, com auditoria. Confere que a
  pessoa e o atendimento são desta loja e que ninguém corrige a si mesmo.
  Desde 17/09/2026 ele também **exige o motivo** de toda correção
  (`ler_observacao`, 3 a 200 caracteres, campo `motivo_da_correcao` no POST),
  move de posição (`mover`) e põe em pausa (`por_em_pausa`), gravando cada
  uma em `CorrecaoNaFila` e na auditoria juntas. O histórico sai em
  `/fila/historico` (`fila/views_historico.py`), para `fila.gerenciar`.
- `fila/estado.py` — o retrato da loja e a versão que a tela consulta.
- `fila/views.py`, `fila/tela.py`, `fila/templates/fila/` — a página fora do
  shell, com ambiente Jinja próprio (`fila/ambiente.py`), a consulta
  `GET /fila/estado` e as ações em `POST /fila/agir`.
- `fila/modulo.py` — o que o módulo diz de si: `fila.ver` primeiro (é a
  permissão que põe a fila no menu), `ativo_por_padrao=True`, e **os nomes da
  barra** (23/09/2026, pedido do cliente: "Metas vai ser um Menu de Nível 1, em
  vez de Fila da Vez muda para Configuração/Fila e em vez do menu chamar Vendas
  vai chamar Gerenciar Fila"; e, com o print da barra na mão, "Metas é um menu
  de Nivel 1 igual Configurações e Gerenciar Fila"). A barra ficou:
  **Configuração** — Conta, Empresas, Filiais, Usuários, Cargos e
  **Configurações da Fila**, com os três cadastros dentro —; **Gerenciar
  Fila** — Fila da vez e Histórico da fila —; e **Metas**, sozinha, no mesmo
  degrau. O grupo dos cadastros do cliente se chamava "Cadastro" e virou
  "Configuração" nos cinco módulos da base (`contas/modulo.py`,
  `plataforma/modulo.py`): o nome antigo repetia o conceito que já é a palavra
  de cada tela. E o pai do cadastro da fila é "Configurações da Fila", e não
  "Fila": "Fila" dizia o mesmo que o item da página e não dizia que ali dentro
  se CONFIGURA — foi a segunda correção do cliente no mesmo assunto.
- **`plataforma/menu.py` desfaz o grupo de um destino só com o nome dele**
  (23/09/2026). Um destino chega ao primeiro nível por um grupo, e o grupo que
  o cliente pediu para as Metas diria "Metas" abrindo para "Metas": o rótulo
  gasto à toa que o teste do "Catálogo" recusa, e um clique a mais para chegar
  na tela. Quando o grupo tem UM filho e o rótulo é o mesmo, o filho sobe
  inteiro — rótulo, ícone e endereço — e é ele o item de primeiro nível; o
  atalho das Metas declara `icone="target"`, que no segundo nível não era
  desenhado. Grupo de um filho com OUTRO nome continua grupo, e é ele que
  separa "Consultas > Frete". Quem cobra é o
  `test_grupo_de_um_filho_com_o_nome_dele_sobe_para_o_primeiro_nivel`, e quem
  prende a barra da fila é o `test_o_menu_da_fila_como_o_cliente_pediu` — os
  dois olham o menu MONTADO.
- `fila/views_cadastros.py` — as três telas de cadastro, uma view para as três.
  **A coluna "Ordem" saiu da tabela** (18/09/2026, pedido do cliente): o campo
  continua no cadastro, e a lista continua saindo por ele (`padrao="ordem"`).
  E o NOME de cada item sai em CAIXA ALTA pela folha `fila/static/fila/
  cadastros.css` — pela folha, e não pelo dado: o cadastro continua gravado
  como a pessoa escreveu, e é assim que ele aparece na folha de venda da fila.

### O que custa esquecer

- **Ler o estado antes de trancar.** Dois toques em "Vou atender" leriam os
  dois "na fila", e o segundo estouraria na restrição do banco com 500.
  `tests/test_fila_concorrencia.py` força a demora entre ler e gravar para a
  trava ser provada, e não a sorte.
- **Um relógio só.** A hora das correções é lida pelo módulo das ações
  (`acoes._agora()`), e não importada por nome: com dois relógios, quem voltou
  pela mão do gerente passava na frente de quem já esperava.
- **`bulk_create` de `ItemVendido` pula a conta**: é o `save` do
  `ModeloDaEmpresa` que a preenche.
- **Cadastro usado é `PROTECT`.** Desativa; a tela diz isso em vez de 500.
- **A página funciona sem JavaScript.** O script só consulta, troca HTML que o
  servidor desenhou e abre as folhas como diálogo; nenhum HTML é montado nele.
- **A página veste o design system.** Ela é montada no shell da casa (o
  cabeçalho com filial, idioma, sair e avatar), sem a barra lateral e sem o
  rodapé (`fila.tela._no_shell`), e `fila/static/fila/fila.css` só usa os
  tokens do tema. A primeira versão, com paleta e fonte próprias, foi recusada
  por parecer outro produto. Todo estado tem rótulo e ícone, e a página não tem
  `<table>`.
- **Macro de template não pode ter o nome de variável do contexto.** O macro
  das folhas se chamava `folha`, como o `?folha=` da URL, e a folha nunca
  abria sem JavaScript.
- **Loja com presença aberta não se desativa.** A base pergunta pelo sinal
  `plataforma.filiais.antes_de_desativar` (ela não pode importar a fila), e
  `fila/sinais.py` responde com a frase, ligado no `ready()`. A tela de
  Filiais tranca a linha da loja antes de perguntar, e o ponto relê a loja
  depois da mesma trava: sem as duas pontas, alguém entrava na loja que
  acabava de ser desativada e ficava preso nela.
- **Mover não guarda número de posição.** Grava em `na_fila_desde` um
  instante ESTRITAMENTE entre os vizinhos, e reespaça a fila quando eles
  estão colados. Igual ao de um vizinho não serve: no empate quem decide é o
  `pk`, e a pessoa cai do lado errado. Por isso a versão da fila conta as
  correções — o maior `na_fila_desde` não muda quando alguém vai para o meio.
- **O motivo da correção se chama `motivo_da_correcao`**, e não `observacao`,
  que é o campo opcional da não venda na mesma folha de fechar: os dois iriam
  juntos no POST.
- **Quem só tem `fila.ver` e `fila.participar` entra por `/fila`**, mas a
  raiz é o painel dele. O desvio é do LOGIN, e não da raiz: a base pergunta
  pelo sinal `contas.entrada.destino_depois_de_entrar` e `fila/sinais.py`
  responde. Na raiz ele tornava o Início inalcançável para o vendedor.


### O fluxo da fila é da empresa (17/09/2026)

Spec `docs/superpowers/specs/2026-09-17-fluxo-da-fila-por-empresa-design.md`.

- **O fluxo da empresa** decide o que acontece depois de lançar o
  atendimento: *volta para o fim da fila* (o padrão, o fluxo da Sylvia) ou
  *fica em espera*. Na empresa, e não na loja: a rede trabalha do mesmo jeito
  nas lojas dela.
- **Ele mora na fila, e não na base** (21/09/2026): era a coluna
  `Empresa.fluxo_da_fila`, e virou a tabela `fila.FluxoDaEmpresa`, uma linha por
  empresa e só quando ela sai do padrão (`fila/0007` copiou o que havia, e
  `plataforma/0006` tirou a coluna). Quem lê e grava é `fila/fluxo.py`
  (`fluxo_de`, `definir_fluxo`). A caixa "Fila da vez" continua na tela de
  Empresas, registrada pela fila em `plataforma.caixas_da_empresa`, o ponto de
  extensão da base para módulo de negócio pôr uma escolha no cadastro da
  empresa. Da mesma forma, as ações da fila na trilha moram em
  `fila/auditoria.py` e são declaradas por `comum.auditoria.declarar_acoes`: a
  base não conhece a fila, e é isso que a deixa voltar limpa para cá.
- **`Estado.EM_ESPERA` não é pausa.** Não existe linha de `Pausa`, e o tempo
  em espera não entra em indicador de pausa nenhum — uma pausa com tipo
  "Espera" somaria o trabalho normal da loja ao almoço no relatório.
- **`acoes._depois_do_atendimento` é o único lugar que decide** para onde a
  pessoa vai quando o atendimento ou a pausa termina. Quem finaliza, quem
  encerra a pausa e o gerente que fecha no lugar do vendedor leem a mesma
  resposta.
- **Bater o ponto continua entrando na fila** nos dois fluxos, e
  `entrar_na_fila` põe no FIM, com a hora de agora.
- **Tirar da pausa pela mão do gerente manda para a FILA nos dois fluxos**: a
  ação é dele, e ele está decidindo que a pessoa atende agora.

### As empresas no painel (17/09/2026)

- **O painel abre na empresa do cabeçalho**, e "Todas as empresas"
  (`?empresa=todas`) é escolha de quem alcança mais de uma. Ela soma, mostra o
  bloco "Por empresa" e deixa o ranking com as pessoas das duas.
- **`indicadores.do_recorte(model, recorte)` é a porta das consultas**: com
  uma empresa é `da_empresa`; com várias, `da_conta` (pelo `conta_guid`)
  recortado por `empresa__in`. As empresas vêm sempre do alcance da pessoa
  (`empresas_com_relatorio`), nunca de um id do pedido.
- **Um ponto por vez, em qualquer empresa**: bater o ponto na loja de outra
  empresa fecha a presença anterior, e quem está atendendo recebe a recusa
  dizendo a loja E a empresa.

### Os indicadores (entrega 2)

Spec `docs/superpowers/specs/2026-09-15-fila-indicadores-design.md`; plano
`docs/superpowers/plans/2026-09-15-fila-indicadores.md`.

- **O dashboard mora no Início (`/`)**, abaixo do "Olá", para quem tem
  `fila.relatorios` em alguma loja (`fila.views.inicio` chama
  `views_indicadores.inicio_com_indicadores`). `/fila/indicadores` só
  redireciona para lá com os mesmos filtros. As lojas saem de
  `fila.indicadores.lojas_com_relatorio` (o cargo no lugar), e a `?loja=` só
  filtra dentro delas.
- **O painel abre em "Todas as lojas"** (18/09/2026, pedido do cliente:
  "aquela área de filtros de datas e loja, tem que vir todas as lojas como
  default"). Entre 17/09/2026 e esta data ele abria na loja do cabeçalho, e a
  decisão de então tinha o motivo dela — a Sylvia na Matriz via o vendedor do
  Centro no ranking —, mas o que ela custava é o que o cliente viu: a rede só
  aparecia trocando o filtro à mão. Em "Todas", o ranking é uma linha por
  pessoa EM CADA loja (`indicadores.ranking_por_loja`, com a coluna Loja) e o
  bloco "Por loja" põe as lojas lado a lado; com UMA loja não há escolha, e ela
  é o recorte. O histórico das correções segue a mesma regra — ele importa o
  mesmo `_lojas_do_pedido`.
- `fila/periodo.py` resolve o período e o anterior (em andamento compara até
  o mesmo ponto); `fila/indicadores.py` faz as contas, na hora, sempre por
  `objects.da_empresa`.
- **Atendimento entra pela hora do fim**, e aberto não entra. Conversão sem
  atendimento é "—".
- **Quem está em primeiro no ranking tem faixa amarela** (23/09/2026, pedido do
  cliente: "colocar uma faixa amarela para destacar o vendedor que está em
  primeiro"), e ela sai do VENDIDO do mês — calculada antes da listagem
  (`views_indicadores._primeiro_do_ranking`), e não da primeira linha da
  tabela: a ordem é a que a pessoa escolheu, e ordenar por nome ou por conversão
  não elege outro primeiro, que é a mesma regra de `posicoes_por_vendido`. Em
  "Todas as lojas" a faixa é de UMA linha, o par (pessoa, loja). O amarelo é o
  `--warn-bg` do tema, o mesmo dos alertas: legível nos dois temas e sem brigar
  com a marca de cada cliente.
- **O ranking é por subconsulta**: `Atendimento.vendedor` e `Pausa.pessoa`
  não têm relação reversa, e é de propósito.
- **Os gráficos do Início não usam o `Chart` do design system**: ele escala
  o texto junto com a caixa (ilegível num terço, enorme na largura toda).
  `fila/graficos.py` desenha colunas e listas em HTML, com escala redonda
  (inteira em contagem), e a troca de série entre as abas é CSS (`:has`).
- "Seus números" na página da fila são os da loja em que a pessoa está.
- Permissão nova não chega sozinha às contas que já existem: a semeadura só
  cria cargo que falta.

### As metas (entrega 3)

Spec `docs/superpowers/specs/2026-09-15-fila-metas-design.md`; plano
`docs/superpowers/plans/2026-09-15-fila-metas.md`.

- **Uma tabela, `MetaDeVenda`**, para a meta da loja (`pessoa` nula) e a do
  vendedor naquela loja, por mês. As travas moram no banco: uma meta por loja
  e mês, uma por pessoa, loja e mês, o mês no dia 1 e o valor positivo.
- **As regras moram em `fila/metas.py`**, e toda conta recebe `agora`. O
  painel, o ranking, "Seus números" e a tela de metas leem de lá.
- **Ninguém define a própria meta e mês encerrado não se edita**, conferidos
  em `gravar`, e não só na tela. O POST não carrega id de pessoa: o servidor
  lê só os campos da lista que ele mesmo monta, e campo ausente não mexe.
- **A projeção usa só os dias fechados**: com o dia de hoje pela metade, o
  dia 1 projetaria o mês com uma venda.
- **A tela foi refeita em 17/09/2026** (`fila/templates/fila/metas.html`):
  o mês com setas, a régua de cobertura da loja e uma linha por vendedor
  com vendido e ritmo. O script (`metas.js`) só recalcula o que o servidor
  desenhou; sem ele a tela funciona igual.
- **A meta é de quem atende** (18/09/2026): a lista sai de
  `fila/quem_atende.py`, e quem gerencia a loja fica de fora — o gerente e o
  supervisor. O parâmetro `meta_para_gestor` (`fila/parametro.py`, padrão NÃO)
  devolve a meta a quem gerencia, para a loja em que o gerente também vende: é
  decisão de operação, e por isso é parâmetro, e não código.
- **A meta da loja distribui sozinha, sem botão** (18/09/2026): ao salvar, quem
  ficou com o campo em branco recebe a parte igual (`meta da loja ÷ nº de
  vendedores ativos`, com o centavo da sobra indo para os primeiros), e quem
  tem valor digitado fica com o dele — dá para acertar um por um depois. A
  distribuição só acontece quando a meta da loja é DEFINIDA ou MUDA: com ela
  igual, campo em branco continua querendo dizer apagar, senão não haveria mais
  como tirar a meta de uma pessoa.
- **E o número aparece ENQUANTO se digita** (18/09/2026, pedido do cliente:
  "só atualiza depois que eu clico em salvar"). Quem adianta é `metas.js`, com
  a mesma conta do servidor — `tests/test_fila_metas_ao_vivo.py` roda as duas
  lado a lado no node, e é isso que impede um número na tela e outro no banco.
  Só o campo da LOJA dispara a distribuição (se qualquer digitação disparasse,
  apagar a meta de alguém a preencheria de volta), e o que a própria
  distribuição escreveu é reconhecido pelo `data-auto`; quem está fora da loja
  (`data-na-loja="0"`) não recebe parte.
- **A soma das metas individuais não passa a meta da loja** (23/09/2026, pedido
  do cliente: "quando eu vou manualmente destrinchar a meta dos vendedores
  individualizada e ela passar o valor da meta total, colocar um aviso e não
  deixar salvar"). A conta é a do que a gravação DEIXA — quem ficou em branco
  recebeu a parte da distribuição e quem o POST não tocou continua com o que
  está no banco —, e roda com a linha da loja já trancada (`_conferir_o_teto`).
  A recusa sai no campo da meta da loja, que é a referência da soma, e NADA é
  gravado: nem a loja, nem os vendedores. Cobrir exatamente a loja continua
  valendo.
- **Soma acima da meta da loja é AVISO, e não "cobre com folga"** (23/09/2026,
  com o print do cliente): "Cobre a loja, com R$ 25.000,00 de folga" era
  aritmética verdadeira e leitura errada — o cliente entendeu "está tudo
  certo" e pediu o bloqueio. O veredito passou a dizer o mesmo que a recusa do
  `gravar`, e a frase viaja para o `metas.js` (`data-acima`): o aviso aparece
  ENQUANTO se digita, antes de clicar em salvar.
- **O ranking do Início é sempre de um mês** (`?ranking_mes=`, escolhido numa
  lista desde 18/09/2026), e não do período dos números de cima.
- **No painel, a meta e o vendido saem das mesmas lojas**: em "Todas as
  lojas", uma loja sem meta não faz a meta das outras parecer batida.

### O turno da loja (23/09/2026)

- **O turno é por FILIAL** (`fila.TurnoDaLoja`, uma linha por loja que tenha
  turno; sem linha não há turno), e se cadastra na tela de Filiais pela caixa
  `fila.turno.caixa` — a base não conhece a fila, e é
  `plataforma.caixas_da_filial` que abre o buraco, do mesmo jeito que
  `caixas_da_empresa` abre o da empresa.
- **Uma hora depois do fim do turno, quem está NA FILA, EM ESPERA ou EM PAUSA
  sai sozinho** (o pedido do cliente: "se o vendedor não saiu da fila, depois de
  uma hora do turno ele sai sozinho"). **Quem está ATENDENDO fica**: fechar
  sozinho um atendimento aberto perderia a venda que o vendedor está lançando.
- **A regra roda na LEITURA**, e não num cron: não há relógio nesta instalação, e
  a página da fila consulta o estado a cada três segundos. `turno.aplicar` entra
  no caminho da página (`tela._contexto`) e no da consulta (`views.estado`), e é
  idempotente. A saída é gravada com a hora do PRAZO, e não com a hora em que
  alguém abriu a página: quem ficou até 00:00 não pode aparecer como tendo
  ficado até as 3h.
- **O prazo olha ontem também**: loja que fecha 23:30 tem prazo à 00:30 do dia
  seguinte, e às 00:15 quem ficou de ontem ainda está dentro dele. Quem ENTROU
  depois do prazo fica — é uma jornada nova.
- A saída automática entra na trilha com o autor `sistema`
  (`fila_saida_por_turno`): a pessoa some da fila, e sem a linha ninguém saberia
  por quê.

### O painel do vendedor

Spec `docs/superpowers/specs/2026-09-16-fila-painel-do-vendedor-design.md`;
plano `docs/superpowers/plans/2026-09-16-fila-painel-do-vendedor.md`.

- **O Início decide nesta ordem** (`fila.views.inicio`): `fila.relatorios` em
  alguma loja, o painel da gestão; `fila.participar` na loja do cabeçalho, o
  painel do vendedor (`fila/views_do_vendedor.py`); senão, a saudação.
- **É o painel da gestão recortado pela pessoa**, com as mesmas peças
  (`_filtros`, `_painel`, `_listas`) e as contas de `fila/indicadores.py`
  com `vendedor=`. A loja é a do cabeçalho, sem campo de loja.
- **O ranking da loja não mostra pausa, ticket, "cliente pediu" nem
  atendimentos.** A posição é sempre por vendido
  (`indicadores.posicoes_por_vendido`), calculada antes do filtro por nome:
  com `Rank()` na consulta, buscar "Ana" a faria virar a primeira.
- **A faixa da meta é só a meta dele** (`metas.meta_da_pessoa`); a meta da
  loja não é régua de ninguém em particular.
- A página da fila não tem menu: o caminho até o painel da raiz é o link "Meu
  painel", e ele é de quem TEM painel lá — o vendedor (o painel dele, por
  `fila.participar`) e também o dono, o supervisor e o gerente (o painel da
  gestão, por `fila.relatorios`). Era só de quem atende, e quem gerencia não
  atende: os três ficavam sem caminho nenhum até o Início (18/09/2026, pedido
  do cliente: "dono, supervisor e gerente não tem o meu painel na página da
  fila").
- **O NÚMERO sobe para ficar na linha do título** (23/09/2026; o cliente pediu
  "centraliza o 0 na fila agora", e corrigiu depois do primeiro ajuste: "não
  era centralizado no meio do trem, era centralizado na linha ali, era só
  subir ele um pouco"). O número é centrado contra o bloco de texto inteiro —
  título, apoio e a trilha da fila —, e com a trilha embaixo o cento do bloco
  cai abaixo da linha do "na fila agora": `translateY(-10px)` no
  `.fila-numeral` põe os dois na mesma altura (medido: o número nascia com o
  centro 12px abaixo do centro do título). **O estado NÃO é centralizado no
  cartão** — essa foi a primeira leitura, e ela está errada.
- **O nome e a loja ficam FORA do cartão, numa faixa acima dele, e maiores**
  (23/09/2026, pedido do cliente: "na página da fila o nome do usuário e filial
  tem que sair do cargo e aumentar o tamanho para melhor visualição"): o celular
  da loja passa de mão em mão, e é o que se lê antes de bater o ponto. Medido em
  393px: o nome a 19px e a loja a 15px, contra 14px e 13px dentro do cartão —
  que ficou com os links ("Histórico", "Meu painel", "Ao vivo") e os números.
- **E a faixa de cima da página tem DUAS linhas no celular** (18/09/2026, com o
  print do cliente na mão: "com o meu painel ali, tá ficando tudo muito
  apertado"): em cima quem está logado e a loja, e os links — "Histórico", "Meu
  painel" e "Ao vivo" — numa linha só deles, espalhados. Com o link novo, os
  quatro itens numa linha de 390px não tinham respiro: a loja quebrava em duas
  linhas e os links ficavam colados. A quebra automática continua valendo para
  nome ou loja compridos.

---

## Como rodar

```bash
uv sync --extra dev
docker compose up -d banco          # Postgres em 127.0.0.1:5440
export KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5440/kronos
DJANGO_DEBUG=1 .venv/bin/python manage.py migrate
DJANGO_DEBUG=1 .venv/bin/python manage.py runserver
DJANGO_DEBUG=1 .venv/bin/python -m pytest -q      # ~6 min, 147 arquivos
```

As portas são próprias de propósito: banco na **5440** e app na **8005** (a
tabela de todas as portas desta máquina está no `README.md`). Apontar para a
porta errada abre o banco de outro produto com as MESMAS tabelas da base, sem
aviso nenhum.

Os 9 testes do ciclo real de backup pulam sem `pg_dump`, `pg_restore`, `psql`,
`createdb` e `dropdb` no `PATH`. Scripts que chamam o `postgres:16-alpine` por
`docker run --network host` servem.

**Publicar é pela VPS MW5** (plugin `mw5`, em `.claude/settings.json`), e o
padrão de verdade é o que a própria VPS devolve (`mw5_padrao
preparar-repositorio`). O que este repositório já cumpre, e
`tests/test_preparo_da_vps.py` cobra: a imagem roda sem root, publica só pelo
commit (nunca `latest`), e o CI implanta em homologação o commit que a suíte
testou; produção nunca entra no CI. `deploy/docker-compose.vps.yml` e
`deploy/atualizar.sh` são do modelo antigo, anterior à VPS.

`config/settings.py` **falha fechado**: fora de `DJANGO_DEBUG=1`, esquecer
`DJANGO_SECRET_KEY` trava a subida em vez de cair num padrão conhecido. Ver o
`README.md` para a tabela de variáveis.
