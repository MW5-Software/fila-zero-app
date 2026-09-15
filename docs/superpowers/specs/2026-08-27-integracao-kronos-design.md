# Integração com o Kronos legado — desenho

> 27/08/2026. O primeiro módulo de negócio de verdade do KRONOS.net, e o
> primeiro caso real de "este cliente é diferente" resolvido pelo mecanismo
> em vez de por código.

## O problema

Depois que o KRONOS.net e o Portal de Vendas estiverem prontos, um **cron**
vai manter os dois atualizados a partir do **Kronos legado** (o ERP em
Oracle). Para isso, cada instalação que fizer essa sincronia precisa saber
**de onde ler**: host, porta, banco, tabela, usuário e senha do Oracle do
cliente.

Isso já existe e está em produção: é o cadastro do **kronos-api2**
(`api_conexao` e `api_config`). O esquema de lá é a fonte, e é copiado com
os **mesmos nomes de tabela e de coluna** — não por preguiça, mas porque o
cron vai mover dado entre os dois lados, e nome igual torna o mapeamento
trivial em vez de uma tabela de-para que envelhece.

**Nem toda instalação vai ter isso.** É por isso que nasce como MÓDULO
(R47): declarado no código, desligado por padrão, ligado por cliente na tela
de Módulos. É o mecanismo funcionando pela primeira vez para o que ele foi
feito.

## O que se copia, e o que não

Das seis tabelas de negócio do `kronos_api`:

| tabela | vem? | por quê |
|---|---|---|
| `api_conexao` | **sim** | o cadastro de host: de onde a rotina lê |
| `api_config` | **sim** | a rotina em si: nome, tipo, `tempo_processo`, urls, token, ambiente |
| `api_empresa` | não | o KRONOS.net já tem `Empresa` (uma por instalação) e `Filial` |
| `api_tela_grid` | não agora | é do Grid KAPI, outro assunto |
| `apiconfig_consultachave` | não | idem |
| `accounts_usuario` | não | é a autenticação, e ela fica fora de propósito |

## Três desvios deliberados da origem

Copiar o esquema não é copiar os defeitos dele. Cada desvio abaixo está aqui
para ser discutido, não para ser descoberto depois.

**1. A senha do Oracle é cifrada em repouso.** Na API já é (AES-GCM, com
`definir_senha()`/`senha_clara`, e o comentário do model proíbe atribuir
`senha` direto). O KRONOS.net não tem cifragem em repouso hoje — o painel de
versões tem, com Fernet e chave por variável de ambiente. Trago o mesmo: a
coluna copia nome e tamanho, o conteúdo é cifrado, e a instalação **recusa
subir** sem a chave, em vez de guardar senha de Oracle de cliente em texto
claro. Falha fechado como `DJANGO_SECRET_KEY` e `KRONOS_BANCO`.

**2. `created_at`/`updated_at` ficam em inglês**, contra a convenção do
KRONOS.net (`atualizada_em`, `quando`). A razão do cron vence a da
convenção, e este parágrafo existe para ninguém "corrigir" depois.

**3. `ativa` vira `boolean` nos dois lados.** Na origem é `integer` em
`api_config` e `boolean` em `api_tela_grid` — incoerência do próprio
esquema. Herdar uma incoerência porque ela existe é o pior motivo possível.

## As telas

**A mesma ideia da API, com as peças da casa.** Não é o Django Admin nem
template HTML solto: são componentes (`Card`, `FormGrid`, `TextInput`),
renderizados por Jinja, com R46 valendo (filtro por coluna, ordenação e
paginação em toda tabela), guarda de rota, confirmação em ação destrutiva e
trilha de auditoria — como toda tela deste sistema.

| tela | o que faz |
|---|---|
| Conexões | lista as conexões cadastradas; filtro, ordenação, paginação |
| Conexão (cadastro) | criar e alterar, com `Form` + `FormGrid` |
| Senha da conexão | trocar a senha do Oracle à parte, como Usuários já faz |
| Rotinas | as `api_config` de uma conexão |
| **Testar conexão** | conecta e diz se respondeu — **a API tem, o KRONOS não** |

A tela de teste é a que mais vale trazer. Cadastro de conexão sem prova é
cadastro que só se descobre errado quando o cron falha às três da manhã.

## O que este desenho NÃO decide

- **O cron em si.** Aqui nasce o cadastro; quem lê e sincroniza é outra
  entrega, e ela vai precisar do Bloco 7 do roadmap (tarefas de fundo e
  agendamento), que não existe.
- **O Portal de Vendas.** Ele precisa do mesmo, e hoje é um código separado
  — então isto vai ser escrito duas vezes ou a base vira pacote. É a segunda
  vez que essa pergunta aparece (a primeira foi o design system); ela não
  fica de graça muito mais tempo.
