# KRONOS.net — matriz e filhas

Data: 2026-08-20
Status: desenho aprovado em conversa; aguardando revisão escrita antes do plano de implementação

## Objetivo

Um único sistema, em Django, que atende todos os clientes da MW5. Alterar o
código em um lugar altera todos os clientes. Cada cliente tem banco próprio e
VPS própria; o que varia entre um e outro mora no banco, nunca no código.

Substitui o modelo atual — um projeto gerado por cliente, cada um no seu
repositório — que cobra a mesma alteração vinte vezes.

## O problema que isto resolve

A MW5 tem mais de vinte clientes em sistemas PHP antigos, sendo reescritos em
Python/Django. No modelo de hoje, herdado do MW5 Application Builder, cada
cliente é um projeto gerado uma vez e depois vivido à parte: `sementes-premix`
tem cerca de 8.800 linhas de código próprio, incluindo o menu escrito à mão em
`app/nav.py` (320 linhas) e as telas de usuários e permissões (1.169 linhas).
Uma mudança de padrão visual, de regra de permissão ou de comportamento de tela
precisa ser repetida em cada projeto.

O builder resolve aparência e scaffolding. Não resolve herança: `mw5 new` copia
uma vez, e só o pacote `mw5_admin` propaga — por versão pinada, com rebuild
manual, projeto a projeto.

## Decisões fechadas

| # | Decisão | Escolha |
|---|---|---|
| 1 | Topologia | Uma matriz, N instalações. Cada cliente tem VPS e banco próprios; esquema idêntico, dados isolados |
| 2 | Stack | Django. O visual do `mw5_admin` é reaproveitado; auth, ORM e migrações passam a ser do Django |
| 3 | Distribuição dos módulos | Todos os módulos vão na imagem de todos os clientes. O banco liga e desliga |
| 4 | Quem configura | Só a MW5 liga módulo e mexe em aparência. O admin do cliente administra pessoas |
| 5 | Código específico de cliente | Mora na matriz, como app Django normal, desligado para quem não usa |
| 6 | Repositórios | Dois: `kronos-net` (código) e `kronos-net-clientes` (inventário). Nenhum repositório por cliente |
| 7 | Fonte da verdade do catálogo | O código diz quais módulos existem; o banco diz quais estão ligados |
| 8 | Propagação | Imagem única publicada por CI; rollout percorre as VPS em escada (homologação, piloto, todos) |
| 9 | Painel central de operação | Adiado. O dado que ele consome nasce desde já gravado no banco de cada cliente |

### Sobre a decisão 9

Com dois ou três clientes, conferir o estado de cada instalação na mão é
viável. Com vinte, não é. O painel é adiado, não descartado: como cada
instalação grava a própria versão e a própria configuração desde a primeira
implantação, construí-lo depois é desenhar uma tela sobre dado que já existe,
e não uma reescrita.

## Arquitetura

Um repositório, quatro camadas.

```
kronos-net/
├─ nucleo/          tema, componentes, layout, montagem do menu
├─ plataforma/      identidade da instalação, catálogo de módulos, marca, versão
├─ contas/          login, usuários, perfis, permissões, perfil pessoal
└─ modulos/         um app Django por módulo
   ├─ frete/
   ├─ vendas/
   └─ ...
```

### Regras de dependência

1. **Módulo não conhece módulo.** Se dois precisam da mesma peça, ela sobe para
   o `nucleo/`. Sem isso, desligar um módulo passa a quebrar outro e a
   decisão 3 deixa de valer.
2. **Módulo declara, não registra.** Rota, item de menu e permissão são criados
   pelo núcleo a partir da declaração do módulo. É o que faz um módulo novo
   aparecer sozinho em todas as bases.
3. **Nenhuma marca no código.** Cor, logo e nome de empresa vêm do banco. Uma
   cor que escape para um template transforma aquele cliente em exceção, e
   exceção é o "alterar um por um" voltando.

## Núcleo — o esqueleto visual

### O que é reaproveitado do `mw5_admin`

Dos 31 arquivos do pacote, quatro dependem de FastAPI (`app.py`,
`dados/resource.py`, `dados/sql.py`, `auth/guards.py`). Os demais são Jinja e
Python puro, e o Django renderiza Jinja nativamente.

| Peça | Linhas aproximadas | Conteúdo |
|---|---|---|
| `theme/` | 1.240 | A cor primária deriva a paleta inteira — superfícies, bordas, texto, modo escuro |
| `components/` | 1.700 | Card, Table, Form, Modal, Alert, Chart, FilterBar, Pagination, Button |
| `layout.py` + `site.py` | 630 | Sidebar, Header, Footer, Breadcrumb, esqueleto de página |
| `icons.py` | 440 | Ícones vendorizados, sem chamada externa |
| `campos.py` | 415 | Tipos de campo de formulário |

### O que é reescrito

| Hoje (FastAPI) | Vira |
|---|---|
| `app.py` | Configuração do projeto Django |
| `auth/guards.py` | Middleware e decorators do Django |
| `dados/sql.py` + `dados/resource.py` | ORM do Django, mais o padrão de tela já provado em `sementes-premix` |

O `Resource` é o trabalho real: 596 linhas de CRUD declarativo sobre SQLAlchemy,
das quais boa parte é `Model` e `ModelForm` no Django.

### Folha de estilo em tempo de execução

Os tokens são servidos como CSS custom properties geradas na requisição, não
compiladas — comportamento que o `mw5_admin` já tem. Trocar a cor de um cliente
é gravar no banco e recarregar a página: sem build, sem nova versão, sem
reinício.

## Plataforma — o que o banco governa

### Catálogo de módulos

Cada módulo tem um arquivo de declaração: nome, ícone, grupo padrão no menu,
telas e permissões que cria.

No banco de cada cliente, a tabela `modulo` guarda uma linha por módulo com o
estado ligado/desligado. **Um receptor de `post_migrate` semeia a linha do
módulo novo, desligada, a cada `migrate` que a instalação rodar** — não uma
migração de tiro único. A diferença importa: uma migração roda uma vez, no
dia em que é aplicada, e um módulo declarado depois dela nunca ganharia
linha numa instalação que já a tinha rodado; `post_migrate` roda a cada
`migrate`, inclusive quando não há nenhuma migração nova para aplicar, e é
exatamente o defeito que a correção da decisão 7 encontrou e fechou. É esta
semeadura que evita que um módulo novo custe vinte intervenções manuais.

Desligar um módulo com dado gravado não apaga nada — apenas o remove da tela.

### Montagem do menu

O menu não é escrito. Nasce do cruzamento de módulos ligados para a instalação
com as permissões do usuário logado. O `app/nav.py` do modelo atual deixa de
existir.

Ocultar item do menu não é controle de acesso: a rota verifica módulo ligado e
permissão de novo, e responde como inexistente quando falta qualquer um dos
dois.

### Menu ajustável por cliente

O `nav.py` de `sementes-premix` registra que a ordem dos grupos foi pedido do
cliente. Pedidos assim são recorrentes, e no código viram exceção por cliente.
O módulo declara o grupo padrão; o banco pode sobrescrever grupo, rótulo e
ordem por instalação. Cliente que não pediu nada usa o padrão.

### Marca

Uma tabela `marca`, uma linha por instalação, com os campos que hoje moram no
`brand.yaml` de `sementes-premix`: nome do cliente e do sistema, logos por
posição (login, lateral, rodapé), favicon, cor primária e de destaque, cores por
área (menu, cabeçalho, conteúdo, rodapé, cabeçalho de tabela), raio de canto,
densidade, sombra, zebra, largura da barra lateral, textos e cores da tela de
login, textos do rodapé.

Sai do arquivo e vai para o banco porque arquivo se troca com implantação e
banco se troca por tela. Mudar uma frase da tela de login não deve exigir uma
versão nova.

### Tela de Aparência

Restrita à MW5. Edita marca, cores, forma e textos, com prévia antes de salvar.
Não edita posição de elemento na tela: cor errada se conserta em segundos,
layout quebrado vira chamado de suporte multiplicado por vinte.

Validação obrigatória: combinação de cores que deixe texto ilegível é recusada
no momento da escolha, não descoberta depois.

### Versão implantada

Cada instalação grava a versão que está rodando e quando subiu. É o dado que o
painel adiado (decisão 9) vai consumir.

## Contas — pessoas e acesso

### Três níveis

| Quem | Alcance | Pode |
|---|---|---|
| MW5 (interno) | qualquer instalação | ligar módulo, mexer em aparência, personificar |
| Admin do cliente | a instalação dele | criar usuário, atribuir perfil, resetar senha |
| Usuário | o que o perfil permite | usar as telas liberadas |

O usuário MW5 é criado pela migração em toda instalação, não aparece na lista
de usuários do cliente e não pode ser removido nem editado pelo admin dele.

Na implementação, "MW5" não é um papel ou grupo à parte: o alcance da linha
acima vem de `is_superuser`, do próprio Django. As telas restritas à MW5
checam `is_superuser`, não pertencimento a grupo nenhum — de propósito: o
nome de um grupo é algo que o admin do cliente vai poder criar quando a
gestão de usuários existir, e se o acesso da MW5 viesse de um grupo chamado
`mw5`, o admin do cliente poderia cunhar para si a administração da matriz
inteira. Superusuário ele não consegue se conceder.

### Perfis e permissões

Perfil é a unidade de trabalho: as permissões são marcadas uma vez no perfil, e
a pessoa entra no perfil. Os três perfis do sistema — `admin`, `gestor`,
`usuario` — nascem com a instalação, como já acontece em `sementes-premix`.

O formato da permissão é `modulo.acao`, com coringa `modulo.*` cobrindo o
módulo inteiro. O coringa importa por envelhecimento: uma ação criada amanhã já
está contida em quem tem `frete.*`, e ausente em quem marcou as ações uma a
uma — o que exigiria reabrir perfis em vinte instalações. A função `pode()` do
`mw5_admin` já implementa e testa essa regra.

### Autenticação

**Padrão:** usuários na base da própria instalação, com senha em hash do
Django. Corrige de saída o problema conhecido do Perform ON, onde a senha está
em texto puro.

**Opcional:** usuários vindos do Oracle do cliente, para quem não quer manter
duas listas de gente. O contrato está desenhado em
`criadordesitesmw5/docs/kronos-identidade.md` — uma função `VALIDAR_LOGIN` e
três views do lado Oracle, com a senha nunca cruzando a rede — e a
implementação existe em `mw5_admin/auth/kronos.py`. Vai para o núcleo,
desligada.

### Personificação e auditoria

Personificar é exclusivo da MW5 e fica registrado: quem entrou como quem,
quando, e o que foi feito durante. `sementes-premix` já tem as duas peças
(`personificacao.py`, `auditoria.py`).

Ficam registrados: login, tentativa de login malsucedida, criação e alteração
de usuário, mudança de perfil, ligar e desligar módulo, alteração de aparência
e personificação.

### Empresa e filial

O seletor de contexto já existe no `mw5_admin` e está desligado em
`sementes-premix` (`show_context: false`). Fica no núcleo, ligado por
configuração. Trocar de contexto é permissão à parte (`contexto.trocar`).

## Publicação

### O ciclo

1. A versão é marcada no repositório `kronos-net`.
2. O CI roda os testes e, se passarem, publica uma imagem única no registry.
   Versão que falha teste não chega a existir.
3. O rollout percorre as instalações, uma de cada vez: baixa a imagem, faz
   backup do banco, aplica as migrações (inclusive a semeadura dos módulos
   novos), reinicia, grava a versão implantada e verifica que a aplicação
   responde.
4. Falha em uma instalação interrompe o rollout. O problema fica em uma, não em
   vinte.

O `kronos-api2` já publica por GitHub Actions sobre VPS; o mecanismo é
conhecido pela equipe.

### Escada

- **Homologação** — instalação da MW5 com dados fictícios; recebe toda versão.
- **Piloto** — um ou dois clientes reais; recebem antes do resto.
- **Todos** — as demais instalações.

O degrau de cada cliente é um campo do inventário.

### Retorno em caso de falha

Falha só de código: volta à imagem anterior, que continua no registry.

Falha após migração de esquema: código volta com facilidade, esquema nem
sempre. Duas regras não negociáveis sustentam o retorno:

1. Backup automático antes de qualquer migração, sem exceção.
2. Nenhuma migração remove coluna na mesma versão que para de usá-la. A remoção
   vem em uma versão posterior, com a frota estável.

## Repositórios

```
MW5-Software/
├─ kronos-net              código, inteiro
└─ kronos-net-clientes     inventário; nenhuma linha de programa
```

O inventário tem um arquivo por cliente com endereço da VPS, banco, degrau da
escada e versão corrente. Segredos não moram ali: ficam nos secrets do GitHub e
na própria VPS.

Não há repositório por cliente. O que distingue um cliente de outro são quatro
coisas, todas no banco dele: módulos ligados, aparência, ajustes de menu e
pessoas. Repositório por cliente reintroduziria exatamente o custo que este
desenho existe para eliminar.

Os repositórios atuais (`sementes-premix`, `vetplan`) continuam de pé e
congelados, como histórico, até que os clientes migrem.

## Provisionamento de cliente novo

1. Uma linha no inventário.
2. Provisionar a instalação: banco vazio, imagem na versão corrente, migrações.
3. As migrações preenchem a base: todos os módulos cadastrados e desligados, os
   três perfis com permissões, o usuário MW5, a aparência no padrão da MW5.
4. Ligar os módulos contratados e aplicar marca e cores.
5. Criar o admin do cliente, que monta a própria equipe.

Sem código escrito, sem repositório criado.

## Migração dos sistemas PHP existentes

Fora do escopo deste desenho, e tratada cliente a cliente. Registrada aqui
porque a diferença de custo é grande e não deve ficar implícita: cliente novo
nasce vazio e sobe em uma tarde; cliente existente exige carga do banco antigo,
que é trabalho próprio por sistema, e um período de convivência entre o PHP e o
KRONOS.net, com os módulos assumidos um de cada vez.

## Testes

Com uma base de código servindo vinte clientes, o custo de um erro é
multiplicado. Quatro testes existem por causa de modos de falha específicos
deste desenho:

1. **Isolamento de módulos** — combinações de módulos ligados e desligados, com
   verificação de que o sistema abre em todas. Protege a regra 1 das
   dependências.
2. **Tela nasce protegida** — varredura de todas as telas verificando exigência
   de permissão. `sementes-premix` já tem esse teste; ele vem para o núcleo.
3. **Semeadura de módulo novo** — a partir de um banco no esquema anterior,
   aplicar as migrações e verificar que a linha do módulo novo apareceu,
   desligada. É o teste da promessa central da decisão 7.
4. **Contraste da marca** — varredura de cores primárias verificando
   legibilidade do texto sobre cada uma.

Além destes, a regra de negócio de cada módulo é testada isoladamente, sem
banco, sem rede e sem aplicação de pé — padrão que `sementes-premix` já aplica
em `app/frete/`.

Nenhum teste substitui a escada de publicação: homologação e piloto existem
porque software com gente de verdade usando revela o que suíte nenhuma revela.

## Ordem de construção

Este desenho é grande demais para um único plano de implementação. Ele se
decompõe em quatro entregas, cada uma com plano próprio, e cada uma útil
sozinha.

**1. Núcleo visual.** Projeto Django de pé, Jinja configurado, `theme/`,
`components/`, `layout.py`, `icons.py` e `campos.py` portados, e uma tela de
demonstração que exercita todos os componentes em claro e escuro. Critério de
pronto: uma tela do KRONOS.net é visualmente equivalente à de
`sementes-premix`, sem CSS escrito à mão.

**2. Contas.** Login, sessão, usuários, perfis, permissões com coringa, perfil
pessoal com troca de senha e foto, auditoria e personificação. Critério de
pronto: duas pessoas com perfis diferentes enxergam telas diferentes, e a rota
recusa quem não tem permissão.

**3. Plataforma.** Declaração de módulo, tabela `modulo`, semeadura por
migração, montagem do menu, tabela `marca`, tela de Aparência e tela de
Módulos. Critério de pronto: um módulo novo criado no código aparece desligado
numa base existente após a migração, e ligá-lo o faz surgir no menu de quem tem
permissão.

**4. Publicação.** CI que testa e publica a imagem, inventário
`kronos-net-clientes`, rollout em escada com backup, gravação da versão
implantada e interrupção em caso de falha. Critério de pronto: uma versão nova
sobe em homologação e em uma segunda instalação por um comando, e uma falha
proposital interrompe o rollout.

Os módulos de negócio (frete, vendas, boletim, produção) vêm depois da 3, e
cada um é uma entrega própria.

## Fora de escopo neste ciclo

- Painel central de operação da MW5 (decisão 9)
- Migração dos sistemas PHP existentes
- Migração de `sementes-premix` e `vetplan` para a matriz
- Materializar `ModuloSpec.permissoes` como `Permission` do Django. Hoje a
  tradução de permissão (`permissoes_de`) só consulta o que já existe no
  banco — nada no código cria as permissões que um `ModuloSpec` declara. Quem
  concede uma permissão de módulo hoje faz isso à mão, via shell ou fixture.
- Criar o usuário MW5 por migração. A seção "Três níveis" já promete isso;
  hoje só existe o mecanismo de *reconhecer* superusuário (`pode()`,
  `is_superuser`), não a migração que cria a conta em toda instalação nova.
- Atualização automática por iniciativa da VPS — a publicação é comandada, para
  que uma versão defeituosa possa ser interrompida no meio do rollout
