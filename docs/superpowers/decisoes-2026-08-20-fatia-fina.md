# Decisões da fatia fina (contas + plataforma) — 2026-08-20

Este documento existe pelo mesmo motivo do seu precedente
(`docs/superpowers/decisoes-2026-08-20-nucleo-visual.md`): `.superpowers/`
não é rastreado pelo git (`.gitignore:7`), e o registro completo das
decisões desta fatia — vinte rulings, `R1` a `R20`, no registro original
(`.superpowers/sdd/2026-08-20-fatia-fina/progress.md`) — moraria só ali. Das
vinte, esta seleção traz as que **mudam comportamento** do sistema, não as
que só reordenaram tarefas ou corrigiram texto de plano. Quem for entender
por que o código de `contas/` e `plataforma/` faz o que faz daqui a um ano
precisa desta lista, não do ledger inteiro.

## Como ler

Cada seção é uma decisão, na ordem em que as tarefas as produziram. Cito o
número da ruling entre parênteses para quem quiser o texto original em
`progress.md`. Onde a decisão foi revista mais de uma vez (o coringa de
permissão foi mexido cinco vezes ao longo desta fatia), narro a evolução
inteira — a versão final só faz sentido sabendo o que ela substituiu.

## Um vocabulário só de permissão, e o filtro pelo catálogo nas duas metades

**(R4, R5, R14 — Task 2 e Task 7; revisto nesta correção final, ver a última
seção deste documento)**

O plano original misturava dois vocabulários no mesmo conjunto de
permissões que `pode()` consulta: as permissões nativas do Django
(`auth.add_user`) entravam junto com as de módulo (`frete.ver`). Como
`pode()` trata `X.*` como cobrindo `X.qualquer`, um grupo chamado `auth`
passava a conceder `auth.add_user` e `auth.delete_user` — escalação de
privilégio por coincidência de nome. A R4 fechou isso: `permissoes_de`
passou a devolver só o vocabulário `modulo.acao`; permissões nativas do
Django continuam valendo por `user.has_perm`, mas não entram no conjunto
que o núcleo consulta.

A R5 precisou corrigir a R4: o coringa que o *nome do grupo* gerava
(`Group(name="frete")` → `frete.*`) nascia independente de `concedidas`, e
fechar só a mistura de vocabulário não fechava essa porta. Nesse momento a
decisão foi aceitar o risco residual — nenhum consumidor real de `pode()`
usava vocabulário do Django, então o coringa por nome de grupo, sem
restrição nenhuma, era "hoje inerte" — mas com uma obrigação explícita
carregada para a Task 7: restringir o coringa a nomes de grupo que
batessem com módulo *declarado* no catálogo (`declarados()`).

A Task 7 cumpriu essa obrigação, mas a revisão achou a porta gêmea: o
mesmo filtro de catálogo que passou a valer para o coringa **não** valia
para `concedidas` — uma `Permission` direta como `plataforma.mw5_aparencia`
ainda entrava sem checar se `mw5` era módulo de verdade. A R14 aplicou o
mesmo filtro nas duas metades: permissão de módulo, direta ou por coringa,
só vale se o módulo existir no catálogo.

O motivo de tratar essas três rulings como uma decisão só, e não três: elas
são a mesma pergunta ("o que impede um nome escolhido por acidente de virar
permissão?") respondida em camadas sucessivas, porque cada correção revelou
a porta seguinte. A correção final desta rodada (última seção) termina essa
linha — não remendando a quinta porta, mas arrancando o mecanismo que
todas elas estavam defendendo.

## `/tema.css` exige banco de pé

**(R7 — Task 5)**

Ligar a marca (`Marca`) ao banco — a peça central da Task 5 — quebrou 54
testes da entrega anterior, porque `/tema.css` e `/` passaram a consultar o
banco a cada requisição, e vários testes batiam nessas rotas sem
`@pytest.mark.django_db`. Não era defeito: era a consequência honesta da
funcionalidade — não existe forma de satisfazer "trocar a cor na tela muda
o sistema na hora" sem a rota tocar o banco toda vez.

A decisão foi marcar os testes afetados com `django_db`, sem mexer em
asserção nenhuma, e aceitar a consequência de arquitetura que fica valendo
desde então: **a tela de login depende do banco estar respondendo**, porque
`/tema.css` é carregada por ela. A alternativa descartada — cachear a marca
em memória — foi rejeitada porque quebraria a própria promessa da entrega
(trocar a cor e dar F5, sem build nem reinício). Esta é a razão de o
healthcheck do banco no `docker-compose.yml` (Task 11) não ser opcional:
sem ele, a primeira pessoa a abrir o sistema depois de um deploy veria erro
de conexão em vez da tela de entrada.

## O default de cor deriva do `Brand`, e a validação mudou de lugar duas vezes

**(R8 — Task 5; R12 — Task 6)**

R8: o plano mandou escrever `default="#1e40af"` e `default="#872d00"` como
literais nas colunas de `Marca` — os mesmos valores que `Brand` já define
como padrão, e reintroduzindo exatamente o defeito que a entrega anterior
já tinha corrigido (um comentário nesse sentido, em `nucleo/views.py`, foi
removido no mesmo diff que reintroduziu o problema). Se o padrão do
framework mudasse, o default da coluna divergiria em silêncio, sem teste
nenhum pegando. Corrigido para derivar do próprio `Brand`
(`Brand.__dataclass_fields__["primary"].default`), com a migração
congelando o valor resultante — migração é registro histórico; a fonte
única precisa estar no código, não na migração.

R12: `Marca.save()` passou a chamar a validação de cor (então
`para_brand()`, hoje `full_clean()` — ver a correção desta rodada, abaixo)
antes de gravar. Motivo: uma linha gravada por shell, migração ou admin com
cor inválida atravessava sem reclamar, e só explodia com 500 na **primeira
requisição** a `/tema.css` — inclusive na tela de login, que carrega essa
folha. A tela de Aparência já validava no POST, mas não é a única porta de
entrada; validar no `save()` fecha todas de uma vez, reusando a validação
que já existe em `Brand` em vez de duplicar regra.

## MW5 é superusuário — não um grupo, e não uma permissão especial

**(R13 — Task 7)**

Conflito real: endurecer o coringa de permissão para só aceitar módulos
declarados (obrigação da R5/R6) quebraria o acesso às telas da MW5, porque
`mw5` não é módulo — declará-lo no catálogo poluiria o menu com uma
entrada falsa. Três caminhos estavam na mesa:

1. **Manter o coringa por nome de grupo valendo para `mw5` sem
   restrição** (o comportamento antes desta ruling). Descartado: é
   exatamente a escalação que toda a linha R4→R14 existe para fechar — um
   admin de cliente que algum dia puder criar grupos cunharia para si o
   nome `mw5` e ganharia acesso à administração da matriz inteira.
2. **Lista de namespaces reservados** (tratar `mw5` como especial dentro
   do mecanismo de coringa). Descartado: mantém a ergonomia do coringa,
   mas deixa exatamente a mesma porta aberta — só muda o nome que
   escalaria privilégio.
3. **Permissão explícita `plataforma.mw5_aparencia` concedida ao grupo**.
   Mais segura que as duas anteriores, mas descartada porque ainda
   dependeria de o admin do cliente não poder conceder aquela permissão
   específica — mais frágil do que depender de ele não poder se conceder
   superusuário, que é uma ação que a gestão de usuários da entrega 2 não
   vai dar a ele.

Decisão: as telas da MW5 (`aparencia`, `modulos`) são só para
`is_superuser`. O nome da permissão que os decorators citam
(`mw5.aparencia`, `mw5.modulos`) documenta a *intenção* de quem acessa; quem
efetivamente passa é o superusuário, via `pode()`. Custo aceito: não há
granularidade dentro da MW5 — não dá para ter alguém que só mexe em
Aparência sem ser superusuário plena. A spec de hoje não pede isso; se
pedir, o caminho é permissão explícita, não coringa por nome de grupo.

## `ModuloLigado`, e a assimetria de quais campos o banco pode sobrescrever

**(R16 — Task 8)**

`modulos_ligados()` devolvia só `ModuloSpec` — perdendo a linha `Modulo`,
que é onde moram as sobrescritas de cliente (rótulo, grupo, ordem). A
decisão foi criar `ModuloLigado`, um dataclass com os valores **já
mesclados** (banco vence código quando preenchido), em vez de o menu (ou
qualquer outro consumidor) reimplementar a mesma mesclagem — o que criaria
duas verdades sobre "o que é um módulo nesta instalação", divergentes no
primeiro ajuste feito de um lado só.

A assimetria que fica registrada: `icone`, `rota` e `permissoes` **nunca**
vêm do banco — só `rotulo`, `grupo` e `ordem` podem ser sobrescritos por
instalação. Ícone e rótulo são aparência, e o cliente pode pedir; rota e
permissão são contrato, e deixar o banco redefini-los seria deixar o banco
redefinir o que o código faz. A revisão da Task 8 achou esta garantia mais
forte do que o desenho original supunha: o próprio *esquema* da tabela
`Modulo` não tem colunas para ícone, rota ou permissões — não é "o código
escolhe não ler esses campos", é "o banco não tem onde tentar sobrescrever".

## A semeadura sai da migração de tiro único e vira `post_migrate`

**(R18 — Task 10)**

O achado mais importante da fatia inteira. A migração original
(`0002_semear_modulos`) semeava a linha de cada módulo declarado **uma
vez**, no dia em que rodava. Um módulo declarado depois — que é o
propósito inteiro da arquitetura — nunca ganhava linha nas instalações que
já tinham essa migração aplicada: ligar pela tela de Módulos atualizava
zero linhas, sem erro nenhum, e o módulo simplesmente nunca aparecia.

Por que passou em todos os testes até então: o pytest cria banco novo e
roda todas as migrações em sequência, com o módulo de exemplo já declarado
antes da primeira migração rodar. Só o caminho de **atualização** — banco
que já existia, módulo declarado depois — expõe o defeito, e nenhum teste
exercitava atualização. Foi achado rodando contra o banco real já migrado
deste próprio repositório.

Decisão: mover o mecanismo para um receptor de `post_migrate`, conectado no
`ready()` de `PlataformaConfig`, que roda a cada `manage.py migrate` —
mesmo quando não há nenhuma migração nova para aplicar. Precedente forte:
`django.contrib.auth.apps` e `django.contrib.contenttypes.apps` usam
exatamente este mecanismo para semear `Permission` e `ContentType`, pelo
mesmo motivo — linhas que precisam existir depois de todo `migrate`, para
model que pode ter surgido a qualquer momento.

Alternativas descartadas: migração de dados por módulo (burocracia por
módulo, e pasta de migrações só para isto num app sem model próprio); ou
uma migração nova em `plataforma` a cada release (depende de alguém
lembrar — o mesmo modo de falha que motivou o achado).

Efeito prático: todo deploy roda `migrate` (já estava no plano), então todo
deploy semeia; um módulo novo ganha a linha sem burocracia por módulo — que
era o requisito original da spec ("aparece sozinho nas vinte bases").

## Esta rodada: o coringa por nome de grupo foi removido

**(correção final da revisão de branch, decisão desta rodada)**

A revisão da branch inteira provou, rodando, que o coringa por nome de
grupo (`Group(name="frete")` → `frete.*` em `permissoes_de`) era
**redundante**: uma `Permission` com `codename="frete_*"` no app
`plataforma` já produz o mesmo `frete.*`, pelo mesmo caminho de tradução
que qualquer outra permissão de módulo (`concedidas`), sem ajuda nenhuma do
nome do grupo. As rulings R4, R5, R6 e R14 remendaram, em sequência, uma
fechadura que podia simplesmente ser removida.

E enquanto o coringa por nome de grupo existisse, três coisas continuavam
verdadeiras, todas piores do que "redundante":

- Renomear um perfil de "frete" para "Frete" **revogava acesso em
  silêncio** — o nome de um grupo é rótulo cosmético que qualquer gestão de
  usuários deixa editar, e nada sinalizava que aquele nome também era, por
  baixo, uma concessão de acesso.
- A gestão de usuários da entrega 2 ganharia uma porta de concessão que
  **não passa por verificação de permissão nenhuma** — bastava batizar um
  grupo.
- Os três perfis que a spec descreve — `admin`, `gestor`, `usuario` — nunca
  batem com chave de módulo nenhuma, logo **nunca carregariam coringa**,
  que é justamente o mecanismo que a seção "Perfis e permissões" da spec
  diz que os perfis usam. O mecanismo implementado não expressava o que a
  spec descrevia.

Decisão: apagar o bloco do coringa por nome de grupo. `permissoes_de` passa
a devolver só `concedidas`. A forma canônica de conceder um módulo inteiro
passa a ser, exclusivamente, uma `Permission` com `codename="<modulo>_*"`
no app `plataforma`. Custo, se errado: as fixtures que concediam por grupo
nos testes passaram a conceder por `Permission` — mais verboso, mas é
exatamente o caminho que a entrega 2 vai usar de verdade, então o teste
passou a exercitar o caminho real em vez de um atalho.

## Onde estão as fontes primárias

- `.superpowers/sdd/2026-08-20-fatia-fina/progress.md` — o registro
  completo, com as vinte rulings e todos os achados de cada uma das onze
  tarefas (não rastreado).
- `.superpowers/sdd/2026-08-20-fatia-fina/correcao-final-report.md` — o
  relatório desta própria rodada de correção (não rastreado).
- `docs/superpowers/plans/2026-08-20-fatia-fina.md` — o plano original
  (rastreado).
- `docs/superpowers/specs/2026-08-20-kronos-net-matriz-design.md` — a
  spec, corrigida nesta mesma rodada nos dois pontos que o código já
  contradizia (semeadura por `post_migrate`, não por migração; MW5 como
  `is_superuser`, não como papel) e com dois itens novos em "Fora de
  escopo neste ciclo".

---

## R46 — Toda tabela tem filtro, ordenação e paginação (21/08/2026)

**Regra, pedida pelo cliente no teste local e vinculante daqui em diante:**
toda tela que lista registros numa tabela precisa de três coisas, sem
exceção — **filtro**, **ordenação por coluna** e **paginação**.

**Por quê:** uma tabela sem essas três funciona na instalação de demonstração,
com três linhas, e deixa de funcionar no primeiro cliente de verdade. O
custo de acrescentar depois é multiplicado pelo número de telas que já
existirem — hoje são duas.

**Como, sem tocar no port:**

- **Filtro:** `FilterBar` + `SearchInput`, que o design system já traz.
- **Paginação:** o componente `Pagination`, que já existe e recebe
  `url_for_page` — a tela só precisa preservar os outros parâmetros da
  consulta ao montar o link.
- **Ordenação:** o cabeçalho da coluna renderiza `{{ col.label }}` com
  autoescape ligado, então um `markupsafe.Markup` atravessa intacto. O
  rótulo vira o link de ordenar sem editar `nucleo/templates/components/table.html`.

**A regra precisa de dente, ou envelhece.** Vale o mesmo padrão que já
provou funcionar duas vezes neste projeto (a varredura de guarda de rota e a
do aviso de personificação): uma **varredura** que percorre as rotas, e para
toda resposta que contiver `<table>`, exige na mesma página o campo de
filtro, os controles de paginação e pelo menos um cabeçalho ordenável. Tela
nova que esquecer vira teste vermelho antes de virar reclamação de cliente.

**Padrão:** 25 linhas por página. O número mora num só lugar, não espalhado
por tela.

---

## R47 — O KRONOS.net é de módulos fixos (21/08/2026)

**Decisão do cliente**, tomada depois de comparar três níveis num mock
clicável, com o menu Administrativo do PORTAL+ (ERP de varejo) como
referência do que seria o nível 3:

1. **Módulos fixos, parâmetros configuráveis** — escolhido
2. Entidade e atributos configuráveis pelo cliente
3. Workflow e relatório também configuráveis

**O que isso significa na prática:** o código diz o que cada módulo é — quais
campos, quais regras, qual caminho o processo percorre. O banco diz **quais
módulos estão ligados**, quem pode o quê, e a aparência. Particularidade de
cliente vira código na matriz, desligado para os outros — nunca um segundo
sistema.

**Por que não os outros dois:** o nível 3 é um produto dentro do produto, e o
PORTAL+ pôde construí-lo porque atende **um segmento só** (varejo), onde as
formas que o processo pode ter são conhecidas. Aqui são segmentos
diferentes, o motor teria de ser mais genérico ainda, e meses se passariam
antes do primeiro módulo de negócio existir. O nível 2 é subida barata a
partir daqui e fica disponível quando um segundo cliente pedir o mesmo campo
de formas diferentes — não antes.

**O risco real desta escolha não é ela mesma, é o desvio para o fork.**
Enquanto a matriz for um código só com particularidade ligada por
configuração, o modelo se sustenta. No dia em que existir `if cliente ==
"..."` espalhado pelas telas, ou um branch por cliente, voltam a existir
vinte sistemas — exatamente o problema que a matriz nasceu para resolver.
Qualquer revisão que encontrar isso deve tratá-lo como defeito de
arquitetura, não como detalhe de implementação.

**Consequência a executar:** uma tabela de parâmetros por instalação (texto,
número, sim/não) resolve boa parte dos "este cliente é diferente" sem código
novo e sem subir de nível. Entra na base, junto de empresa/filial.

**O que NÃO muda com esta decisão:** empresa/filial continua sendo item de
base, independente do nível escolhido — é coluna em toda tabela e em toda
consulta, e é o item que mais encarece se adiado.

---

## R48 — O logo do rodapé é do produto, e não troca (26/08/2026)

**A regra:** toda instalação nasce com o logo do KRONOS em três lugares —
tela de entrada, menu lateral e rodapé. O cliente pode trocar os dois
primeiros pela marca dele. **O rodapé não.**

**Por quê:** o rodapé é a assinatura de quem FEZ o sistema, e ela é a mesma
nas vinte instalações. Enquanto ele esteve aberto ao envio, qualquer cliente
podia apagá-la sem querer — e a tela de Aparência oferecia o campo, o que
não era descuido dele, era convite nosso.

**Onde isso mora, e onde NÃO mora:**

- `plataforma/marca.py` — `ASSETS_DO_PRODUTO` é o piso: entrada e menu já
  nascem vestidos, e o que o cliente enviar cobre esses dois.
  `marca_da_instalacao()` fixa `footer_logo` DEPOIS do que veio do banco, e
  é essa ordem que faz a regra ser garantia em vez de coincidência.
- `plataforma/models.py` — `LUGARES_DA_IMAGEM` perdeu `"footer"`. É a lista
  do que o CLIENTE pode enviar, e o modelo recusa o resto na gravação.
- `nucleo/theme/brand.py` — **intocado**. `LUGARES_DO_LOGO` continua com os
  três: o design system sabe DESENHAR logo no rodapé, e essa capacidade não
  é nossa para tirar. Quem escolhe quais estão abertos é a plataforma.
- `plataforma/site.py` — `SiteDoProduto` troca só o `logo_alt` do rodapé
  pelo nome do produto. Sem isso, quem usa leitor de tela ouviria o nome do
  cliente descrevendo a imagem do KRONOS.

**Três arquivos do mesmo desenho**, um por lugar — a mesma divisão que o
`Assets` já faz. Vieram do painel GED, onde esta marca já estava resolvida
(ver o `brand.yaml` de lá). Não é a versão branca: a faixa da barra tem fundo
branco fixo no design system (`_SIDEBAR_BRAND_BG` em `tokens.py`, com o
porquê escrito ao lado), e sobre ela a versão branca sumiria.

**As medidas vêm junto, e não são detalhe.** A marca do KRONOS é EMPILHADA —
símbolo em cima, "Kronos" e "ERP | CRM" embaixo. Os 56px que o design system
reserva na barra e os 24px do rodapé foram pensados para marca deitada: neles
o nome sai com ~16px e ~7px, e a linha do ERP com 4px e 2px. O limite não é o
arquivo, é o espaço. `logo-side-h: 84px`, `logo-footer-h: 40px`,
`logo-footer-w: 72px` — números do GED, onde a conta já foi feita.

A do rodapé vale **sempre**, porque o logo de lá nunca troca. A da barra vale
**só enquanto o logo da barra for o do produto**: a marca deitada de um
cliente em 84px viraria um retângulo gordo no alto do menu, e aí a medida
volta a ser a do design system.

**Migração:** `0010_logo_do_rodape_e_do_produto` apaga a linha de rodapé que
alguma instalação já tenha gravado. Os bytes não voltam; reabrir o envio é
decisão de produto, não de migração.

**As cores vieram junto, e uma delas era uma herança errada.** O `accent`
padrão era `#872d00` — um marrom que entrou no `Brand` pelo Sementes Premix e
nunca teve nada a ver com o KRONOS. O menu vinha vazio ("herda do tema"), o
que dava um azul derivado da primária em vez do azul-marinho DO LOGO. As duas
coisas juntas produziam um efeito silencioso: **abrir a Aparência e salvar
sem mexer em nada trocava a cara do produto.** Agora os padrões da `Marca`
apontam para `plataforma/marca.py` — `#217598` (o ciano do símbolo escurecido
25%, porque o puro dá 3,12:1 sobre branco e o accent é texto de 10px) e
`#1f275d` (o marinho dominante do logo). Migração `0011`; linha já gravada
não é tocada, porque ali alguém escolheu.

**A nitidez é regra, não sorte.** `ferramentas/gerar_logos.py` gera cada
arquivo com **3× a caixa** em que ele aparece. O problema que isso resolve não
se vê na tela de quem faz o arquivo: um PNG de 138x96 numa caixa de 110x24
parece perfeito num monitor comum e sai borrado em qualquer tela retina.

**Um defeito do design system apareceu junto**, e a correção está em
`plataforma/static/plataforma/kronos.css` (folha da casa, carregada depois da
`mw5.css`): `.side-logo` pede `width: 100%; height: 100%` dentro de um grid
`place-items: center`, e ali o `height: 100%` não resolve — a altura do
`<img>` vira a largura da barra vezes a proporção do desenho. Com marca
deitada isso coube por coincidência; com a marca empilhada do KRONOS o logo
descia 36px para fora da faixa. A folha inverte quem manda: altura é a medida
reservada, largura acompanha. **Não é regra do KRONOS — é bug do
`mw5_admin`**, e esta folha é a ponte até a correção subir para lá.

**O que isto NÃO decide:** a marca do cliente na entrada e no menu continua
inteira — cor, logo, favicon, rótulos. A regra é sobre um lugar só.
