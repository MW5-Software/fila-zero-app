# Empresa e filial — desenho

> 21/08/2026. Primeiro bloco do `roadmap-base.md`. Vem antes de qualquer
> módulo de negócio porque muda o formato de toda tabela que vier depois:
> feito agora é uma migração, feito depois de dez módulos são dez.

## Decisões do cliente

**Uma empresa por instalação, com filiais dentro dela.** Cada cliente tem
VPS e banco próprios, e naquele banco existe **uma** empresa. O que varia é a
filial — unidade, loja, depósito.

Consequência que simplifica tudo: **não existe coluna de empresa em tabela
nenhuma.** A empresa é dado da instalação, como a marca. Só a filial vira
coluna.

**A pessoa escolhe entre as filiais que pode, e troca durante o dia.** Tem
acesso a um conjunto, escolhe uma no cabeçalho, e o que ela vê e o que ela
grava seguem a filial escolhida naquele momento.

## O que o design system já resolve

Nada disto precisa ser inventado nem desviado do port:

- `Brand.context_labels` — `("Empresa", "Filial")` por padrão, e trocável por
  cliente: uma rede chama de bandeira e loja, uma prestadora de contrato e
  posto. `Brand.show_context` desliga a faixa inteira.
- `ContextLevel` (`nucleo/layout.py`) — **sem opções vira texto, com opções
  vira seletor**. É exatamente o nosso caso: empresa é texto (ninguém
  escolhe), filial é seletor.
- `ContextSwitcher` + `Site.context_line` — o lugar no meio do cabeçalho já
  existe e já é alimentado por um `Callable` que recebe o usuário.
- `NivelDeContexto` / `OpcaoDeContexto` (`nucleo/permissoes.py`) — o contrato
  que o backend preenche, já pensado para não depender de backend concreto.

## Modelo

- **`Empresa`** — uma linha por instalação, como `Marca`. Razão social, nome
  fantasia, CNPJ, inscrição estadual, endereço. Semeada no `post_migrate`
  junto dos outros quatro passos, para a instalação nova não nascer manca.
- **`Filial`** — nome, apelido (o que aparece no seletor), CNPJ próprio (no
  Brasil filial tem o seu), endereço, `ativa`. Uma "Matriz" semeada.
- **Acesso** — M2M entre usuário e filial. Superusuário alcança todas sem
  precisar de linha, mesma regra do resto do sistema.

## Contexto na requisição

A sessão guarda `filial_id`, do mesmo jeito que guarda `usuario_id`: só o id,
e a filial é reconstruída a cada requisição. É o que faz **tirar o acesso de
alguém a uma filial valer na hora**, não no próximo login — a mesma
propriedade que `buscar` já dá para o usuário.

Regras:

- Sem filial escolhida, vale a primeira a que a pessoa tem acesso.
- Filial escolhida à qual a pessoa **deixou** de ter acesso é descartada, e
  cai na primeira válida. Nunca 500, nunca dado de filial alheia.
- Pessoa sem filial nenhuma não opera: vê uma tela dizendo isso, com o que
  fazer. Não é erro dela, é cadastro faltando.
- A troca é **POST**, nunca GET: um `<img src="/filial/trocar?id=9">` numa
  página qualquer não pode mudar o contexto de quem a abriu. Mesma razão de
  `sair` ser POST.

## A regra que o primeiro módulo vai herdar

Hoje não existe tabela de negócio, então não há coluna de filial em lugar
nenhum. O que este bloco entrega é o **mecanismo** e a **regra**, para o
primeiro módulo já nascer certo:

- toda tabela de dado de negócio carrega `filial`;
- toda consulta de tela filtra pela filial do contexto;
- o que se grava nasce na filial do contexto.

E a regra precisa de dente, como as outras três varreduras deste projeto
(guarda de rota, guarda de módulo, aviso de personificação): uma varredura
que exija a coluna de filial em todo model de negócio declarado por módulo.
Model de plataforma — usuário, perfil, marca, parâmetro, auditoria — é
global de propósito e fica de fora, com o motivo escrito ao lado.

## O que NÃO entra agora

- Permissão por filial no nível de ação ("edita em Cuiabá, só lê em
  Sorriso"). Primeiro o contexto; refinar permissão por filial é outra
  conversa, e sem módulo de negócio no ar seria desenho no vazio.
- Empresa como tabela de várias linhas. A decisão é uma por instalação; o dia
  em que um cliente for grupo econômico de verdade, a conversa é essa e o
  custo é conhecido — acrescentar a coluna de empresa em `Filial`, não
  reescrever o modelo.
