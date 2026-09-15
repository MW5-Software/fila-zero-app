# Portal de Vendas — identidade e acesso no SaaS

> 02/09/2026. Substitui a hierarquia desenhada em
> `2026-08-27-portal-de-vendas-estrutura.md`, que pressupunha um portal
> instalado por distribuidora. O produto passa a ser vendido por assinatura, e
> a conta — não a instalação — vira a unidade.
>
> **Escopo desta spec: identidade e acesso.** Catálogo, orçamento e a
> integração com o Kronos ficam de fora e ganham conversa própria. O que esta
> spec obriga a tocar neles está nomeado em "A cirurgia no catálogo".

## O que muda, em uma frase

Deixa de existir "a instalação de um cliente" e passa a existir **a conta**, e
a conta é uma PESSOA: o Admin. Ele paga, ele é dono das empresas, e os
usuários que ele cadastra são dele.

---

## As decisões

### 1. A conta é o usuário Admin

Não existe tabela `conta`. O Admin **é** a assinatura: o plano é coluna dele, e
as empresas e os usuários apontam para ele.

```
mw5            nivel 0   dono ∅                     ← MW5, dona do sistema
 │
 └─ joao       nivel 1   dono ∅   plano OURO        ← paga, é a conta
     │
     ├── empresa Metalúrgica     dono → joao
     │     └── filial Matriz · filial Sorriso
     ├── empresa Distribuidora   dono → joao
     │
     ├─ ana    nivel 2   dono → joao   perfil Vendedor
     │            empresas: Metalúrgica
     │            carteira: pedro
     └─ pedro  nivel 2   dono → joao   perfil Comprador
                  empresas: Metalúrgica, Distribuidora
```

**`dono` é nulo no Admin, e não aponta para si mesmo.** "Sem dono" é o que
define ser uma conta; um Admin apontando para si é um ciclo que toda consulta
precisa lembrar de cortar, e a primeira que esquecer devolve o próprio dono
misturado com os subordinados dele.

**Três níveis, e só três:**

| nível | quem é | o que tem por sê-lo |
|---|---|---|
| 0 Master | a MW5, dona do sistema | tudo |
| 1 Admin | o assinante, dono da conta | tudo dentro das empresas dele |
| 2 Usuário | quem o Admin cadastra | nada — só o que o perfil der |

Vendedor e comprador **deixam de ser níveis** e viram perfis. Ver a decisão 5.

### 2. Usuário próprio (`contas.Usuario`), herdando `AbstractUser`

`auth_user` é criado por uma migração dentro do pacote do Django, no `.venv`.
Não é possível acrescentar coluna nela: editar o arquivo do Django some no
próximo `uv sync`; `ALTER TABLE` cru dá uma coluna que o ORM não conhece;
reabrir a classe em tempo de execução quebra na próxima versão. O Django
oferece dois caminhos, e só dois — tabela 1:1 ao lado, ou usuário próprio.

`acesso_acesso` **é** a tabela 1:1, e ela existe porque este projeto escolheu
o primeiro caminho quando precisou de duas colunas. Com `plano`, `guid` e
`dono` chegando, seriam mais três num lugar onde já há três tabelas 1:1
(`acesso_acesso`, `contas_avatar`, `contas_marcadesenha`) e toda consulta
sobre uma pessoa junta quatro tabelas.

**As quatro viram uma.** É a decisão que o projeto adiou de propósito
(`acesso/models.py` diz por quê) e que só é barata enquanto não há cliente
instalado.

**Igual ao `kronos-api2`**, que já fez esta troca (`AUTH_USER_MODEL =
'accounts.Usuario'`): `nome` em vez de `first_name`/`last_name`, `telefone`, e
login por e-mail. A diferença é herdar `AbstractUser` em vez de
`AbstractBaseUser`: o Portal já tem tela de perfil, avatar, auditoria e
personificação em cima do encanamento do Django, e `AbstractUser` o preserva
inteiro.

```python
class Usuario(ComGuid, AbstractUser):
    username = None
    first_name = None
    last_name = None

    email = EmailField(unique=True)
    nome = CharField(max_length=255)
    telefone = CharField(max_length=20, blank=True, default="")

    nivel = IntegerField(choices=Nivel, default=Nivel.USUARIO)
    dono = ForeignKey("self", null=True, blank=True, on_delete=PROTECT,
                      related_name="subordinados")
    plano = CharField(max_length=20, blank=True, default="")

    senha_definida_em = DateTimeField(null=True, blank=True)
    avatar = BinaryField(null=True, blank=True)
    avatar_tipo = CharField(max_length=40, blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]
```

**Custo medido, para não ser surpresa:** 248 usos de `username` no código e
207 nos testes; 128 e 126 de `create_user(`; 29 e 16 de `first_name`. Quase
tudo mecânico. Os 1739 testes apontam cada ponto.

### 3. GUID em toda tabela nossa, como coluna — não como chave

```python
class ComGuid(models.Model):
    guid = UUIDField(unique=True, default=uuid4, editable=False)
    class Meta:
        abstract = True
```

Toda tabela nossa herda: `Usuario`, `Empresa`, `Filial`, `Perfil`, `Modulo`, e
as 16 de negócio por `ModeloDaEmpresa`. As do Django (`auth_permission`,
`django_content_type`, `django_session`) ficam como estão — não são nossas.

**Por que coluna e não chave primária.** O pedido é "um GUID para relacionar,
em todas as tabelas". Como chave primária isso é impossível de cumprir: as
tabelas do Django continuariam `bigint`, e o banco ficaria metade em UUID e
metade em inteiro — justo a falta de uniformidade que o pedido quer evitar.
Como coluna, **toda linha nossa tem GUID, sem exceção**.

O custo do outro caminho cai no lugar mais quente: `empresa_id` está em quase
todo índice do sistema, e trocá-la por UUID multiplica por quatro o tamanho
dela em cada um. `uuid4` é aleatório, e chave aleatória fragmenta o índice a
cada inserção; `uuidv7` resolveria, e é nativo só no Postgres 18 (aqui é
16.14).

O que o GUID existe para resolver, ele resolve como coluna: id sequencial não
aparece mais na URL, dados de duas instalações não colidem ao juntar, e a
integração passa a citar um id estável nosso. Nenhum dos três precisa que a
JUNÇÃO seja por GUID — precisam que a linha tenha um.

E não fecha porta: com o GUID já lá e preenchido, virar chave primária um dia
é decisão com dado real na mão.

**Nas URLs:** o GUID entra nas rotas que esta spec toca (empresa, avatar). As
sete rotas do catálogo seguem com inteiro até o catálogo ser refeito — e vão
encontrar a coluna pronta quando for.

**Varredura:** model novo sem `guid` deixa a suíte vermelha, na forma das
cinco que já existem.

### 4. Filial é cadastro, não fronteira

Empresa e filial se cadastram; a filial pertence à empresa. **O vínculo do
usuário é com a empresa inteira.** A coluna de inquilino segue `empresa_id`
nas 16 tabelas, e nenhuma tabela de negócio ganha `filial_id`.

Quando o escopo por filial for preciso, o caminho é: o **movimento** passa a
dizer de qual filial saiu (orçamento e item), o catálogo continua da empresa, e
o vínculo do usuário ganha a alternativa "esta filial" ao lado de "esta
empresa". Duas tabelas, não dezesseis.

### 5. Perfil carrega o papel, e é da conta

`contas_perfil` ganha `dono` e `papel`, e o nome passa a ser único **dentro da
conta** — dois clientes podem ter "vendedor" sem colidir.

```python
class Perfil(ComGuid, models.Model):
    dono = ForeignKey(Usuario, on_delete=CASCADE, related_name="perfis_criados")
    nome = SlugField(max_length=60)
    rotulo = CharField(max_length=120)
    papel = CharField(choices=Papel, blank=True, default="")   # comprador · vendedor · ∅
    permissoes = ManyToManyField(Permission)

    class Meta:
        constraints = [UniqueConstraint(fields=("dono", "nome"),
                                        name="perfil_unico_por_conta")]
```

**Por que o papel mora no perfil e não na pessoa.** Linhas do banco apontam
para compradores: `catalogo_preco.comprador_id` e `orcamento.comprador_id` são
FK para pessoa. O sistema precisa responder "quem são os compradores desta
empresa?" para montar uma tabela de preço negociado ou uma carteira — e isso
não sai de permissão, que diz o que se ABRE, não o que se É.

No perfil, quem dá o perfil "Comprador" a alguém está dizendo que ela é
compradora, e as duas coisas não podem discordar. Se o papel fosse coluna da
pessoa, nada impediria papel de vendedor com perfil de comprador, e os seis
lugares que decidem visibilidade divergiriam da tela.

**Duas regras que vêm junto:**

- **Comprador vence.** Alguém com dois perfis de papéis diferentes é tratado
  como comprador — é o papel que mais restringe o que se vê, e errar para o
  lado restritivo é o único jeito seguro de errar.
- **Os pré-determinados são CÓPIAS por conta**, feitas quando a conta nasce:
  Comprador, Vendedor, Financeiro. Cópia e não perfil compartilhado, porque o
  Admin edita — um perfil compartilhado e editável mudaria o "Vendedor" de
  todas as contas de uma vez.

### 6. Duas naturezas de poder

O **nível** dá o poder estrutural: criar empresa, criar usuário, criar e editar
perfil. Não é editável por ninguém dentro do produto.

O **perfil** dá o poder operacional: ver catálogo, montar orçamento,
precificar, ver relatório.

O catálogo de permissões parte em dois:

| grupo | quem tem | exemplos |
|---|---|---|
| **de sistema** | só o Master | Aparência, Módulos, Falhas, Parâmetros, criar contas |
| **de conta** | Admin, e o que ele delegar | catálogo, orçamentos, usuários, empresa, perfis |

**O Admin pode tudo do grupo "de conta", dentro das empresas dele**, sem
precisar de perfil. Perfil existe para a equipe.

**A trava do teto:** o Admin monta perfil só com permissões que ele mesmo tem.
Ele organiza a equipe à vontade, e nada que ele monte é maior que ele. Sem
isso, "o Admin edita perfis" e "o Admin não alcança o sistema" seriam
contraditórios — bastaria montar um perfil com tudo.

Isto mantém a arquitetura de hoje (duas vias: permissão direta e perfil),
redefinindo o que cada via carrega. A tabela `DE_FABRICA` sobrevive — muda de
endereço para `contas/fabrica.py` junto com o resto do app `acesso/` — com
três níveis em vez de quatro, e o que era de vendedor e de comprador migra
para os perfis pré-determinados.

### 7. Planos, preparados e desligados

`plano` é coluna do Admin. Os limites são declarados em código, na forma dos
parâmetros que já existem:

```python
PLANOS = {
    "prata": Plano(empresas=1, usuarios=5),
    "ouro":  Plano(empresas=5, usuarios=25),
}
```

**"5 usuários" são 5 ALÉM do dono.** O Admin não ocupa vaga.

Uma função só responde `cabe_mais_uma_empresa(conta)` e `cabe_mais_um_usuario(conta)`,
e hoje as duas respondem sempre que sim. Quando a cobrança entrar, é essa
função que muda; as duas telas que a chamam já estarão chamando.

---

## O esquema

De **11 tabelas para 8**.

```
contas_usuario                      ← auth_user + acesso_acesso
  id, guid                            + contas_avatar + contas_marcadesenha
  email (único), password, nome, telefone
  is_active, is_staff, is_superuser, last_login, date_joined
  nivel, dono_id → contas_usuario, plano
  senha_definida_em, avatar, avatar_tipo

contas_usuario_empresas       quais empresas o nível 2 alcança
contas_usuario_compradores    a carteira do vendedor
contas_usuario_perfis         quais perfis a pessoa tem

contas_perfil                 id, guid, dono_id, nome, rotulo, papel
contas_perfil_permissoes      perfil_id, permission_id

plataforma_empresa            id, guid, dono_id → contas_usuario, …
plataforma_filial             id, guid, empresa_id, …
```

| some | vira |
|---|---|
| `auth_user` | `contas_usuario` |
| `acesso_acesso` | colunas `nivel`, `dono`, `plano` |
| `contas_avatar` | colunas `avatar`, `avatar_tipo` |
| `contas_marcadesenha` | coluna `senha_definida_em` |
| `acesso_acesso_empresas` | `contas_usuario_empresas` |
| `acesso_acesso_compradores` | `contas_usuario_compradores` |
| `contas_perfil_usuarios` | `contas_usuario_perfis` |

O app `acesso/` deixa de existir: `alcance.py`, `inquilino.py` e `fabrica.py`
mudam de endereço para `contas/`; `models.py` é absorvido pelo `Usuario`.

---

## A cirurgia no catálogo

Seis lugares decidem hoje quem vê qual dado perguntando `nivel == COMPRADOR` ou
`e_vendedor`. Com vendedor e comprador saindo dos níveis, esses seis param de
funcionar no mesmo dia — e por isso entram nesta spec, mesmo com o catálogo
fora dela:

| arquivo | o que decide | vira |
|---|---|---|
| `orcamento/visibilidade.py` | quais orçamentos a pessoa vê | `tem_papel(…, COMPRADOR)` |
| `catalogo/preco.py` | qual preço ela vê | idem |
| `catalogo/views_vitrine.py` | o que a vitrine mostra | idem |
| `orcamento/views.py` | quem pode cancelar | idem |
| `acesso/alcance.py` | a carteira do vendedor | `tem_papel(…, VENDEDOR)` |
| `plataforma/views_empresa.py` | quem cria empresa | `nivel <= ADMIN` |

É troca de pergunta, não redesenho.

---

## A migração

**Migrações do zero.** As 45 existentes são apagadas e uma inicial é gerada
com o desenho novo; o banco de desenvolvimento é recriado e semeado.

É possível porque **não há nada em produção** — confirmado com o João em
02/09. Trocar `AUTH_USER_MODEL` num projeto com migrações existentes é a
operação mais dolorosa do Django; com uma inicial nova, é uma linha. Depois da
primeira instalação de cliente este caminho desaparece para sempre.

Quem tiver o banco na máquina recria. O dado de teste se perde, e a semeadura
o repõe.

---

## Como se prova

A suíte inteira, de propósito: 1739 testes, e a maior parte da mudança é
mecânica. São eles que apontam cada um dos ~450 pontos de `username`.

**Três varreduras**, na forma das cinco que já existem:

| varredura | recusa |
|---|---|
| GUID | model nosso sem a coluna |
| inquilino | model de negócio sem `empresa_id` (já existe; ganha o GUID junto) |
| teto do perfil | perfil que concede permissão de sistema |

**O ataque que prova a fronteira nova:** um Admin monta um perfil com tudo o
que consegue e o dá a si mesmo — e continua sem alcançar Aparência, Módulos,
Falhas, e sem enxergar empresa da conta vizinha. Pedir o id de fora devolve
404, nunca 403.

**A prova da fatia**, na forma da spec de 27/08: um usuário nível 2 pede o id
de uma empresa que não é do dono dele e recebe 404.

---

## O que fica de fora

- Catálogo, orçamento e vitrine — só a troca de pergunta acima
- As sete rotas do catálogo com id inteiro na URL
- Integração com o Kronos
- Cobrança, gateway de pagamento, autocadastro
- Escopo por filial
- Reaplicar níveis em massa quando a regra mudar (existe hoje e continua
  faltando — ver "em aberto")

## Em aberto, e nomeado

**Mudar a regra de um perfil pré-determinado não reescreve quem já existe.** É
o mesmo buraco que o nível tem hoje: as permissões de alguém só são regravadas
quando o perfil daquela pessoa é salvo de novo, e não há comando para
reaplicar em massa. Com poucos usuários não dói; com uma conta de 25, dói. Um
`manage.py reaplicar_perfis` resolve, e não está nesta spec.

**Autocadastro não existe.** O Master cria a conta (o Admin); o Admin cria a
equipe dele. Vale estar escrito para ninguém reintroduzir por hábito — quando
a cobrança entrar, o autocadastro vem com ela e traz junto confirmação por
e-mail, que também não existe.
