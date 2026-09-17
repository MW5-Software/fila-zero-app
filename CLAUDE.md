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
- **`tests/`** — 135 arquivos. Rodam em ~2 min (Postgres, `KRONOS_BANCO`
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

### Uma conta, uma empresa

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
- **Várias empresas por conta ainda não existem.** A trava
  `uma_empresa_por_conta` continua, e "Nova empresa" e o seletor de empresa para
  o titular são o próximo passo (plano 3 do spec de cargos). O cabeçalho só
  mostra seletor de empresa para a MW5.

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
- o **alcance**: os próprios, a filial ou a empresa;
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
- **O módulo de Filiais nasce desligado** (`ativo_por_padrao=False`). Numa
  instalação, a MW5 liga em Módulos para o titular ver a tela.

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
4. **Várias empresas por conta** (§7) e **o módulo de Filiais nascendo ligado**
   continuam por fazer.

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
- `fila/views_cadastros.py` — as três telas de cadastro, uma view para as três.

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


### Os indicadores (entrega 2)

Spec `docs/superpowers/specs/2026-09-15-fila-indicadores-design.md`; plano
`docs/superpowers/plans/2026-09-15-fila-indicadores.md`.

- **O dashboard mora no Início (`/`)**, abaixo do "Olá", para quem tem
  `fila.relatorios` em alguma loja (`fila.views.inicio` chama
  `views_indicadores.inicio_com_indicadores`). `/fila/indicadores` só
  redireciona para lá com os mesmos filtros. As lojas saem de
  `fila.indicadores.lojas_com_relatorio` (o cargo no lugar), e a `?loja=` só
  filtra dentro delas.
- **O painel abre na loja do cabeçalho** (17/09/2026); "Todas as lojas"
  (`?loja=todas`) é escolha explícita de quem alcança mais de uma. Antes a
  soma era o padrão, e a Sylvia na Matriz via o vendedor do Centro no
  ranking. Em "Todas", o ranking é uma linha por pessoa EM CADA loja
  (`indicadores.ranking_por_loja`, com a coluna Loja) e o bloco "Por loja"
  põe as lojas lado a lado.
- `fila/periodo.py` resolve o período e o anterior (em andamento compara até
  o mesmo ponto); `fila/indicadores.py` faz as contas, na hora, sempre por
  `objects.da_empresa`.
- **Atendimento entra pela hora do fim**, e aberto não entra. Conversão sem
  atendimento é "—".
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
  com vendido e ritmo. "Dividir" reparte o que falta SÓ entre quem está
  sem meta, pelo que está digitado, e não grava (`metas.dividir_o_que_falta`).
  O script (`metas.js`) só recalcula o que o servidor desenhou; sem ele a
  tela funciona igual.
- **O ranking do Início é sempre de um mês** (`?ranking_mes=`), e não do
  período dos números de cima.
- **No painel, a meta e o vendido saem das mesmas lojas**: em "Todas as
  lojas", uma loja sem meta não faz a meta das outras parecer batida.

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
- A página da fila não tem menu: o caminho do vendedor até o painel é o link
  "Meu painel", para quem tem `fila.participar`.

---

## Como rodar

```bash
uv sync --extra dev
docker compose up -d banco          # Postgres em 127.0.0.1:5436
export KRONOS_BANCO=postgresql://kronos:kronos@127.0.0.1:5436/kronos
DJANGO_DEBUG=1 .venv/bin/python manage.py migrate
DJANGO_DEBUG=1 .venv/bin/python manage.py runserver
DJANGO_DEBUG=1 .venv/bin/python -m pytest -q      # ~2 min, 135 arquivos
```

As portas são próprias de propósito: banco na **5436** e app na **8005**. O
KRONOS.net usa 5433/8000/8001, o Portal de Vendas usa 5434/8003 e a KRONOS base
usa 5435/8004. Apontar para a porta errada abre o banco de outro produto com
as MESMAS tabelas da base, sem aviso nenhum.

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
