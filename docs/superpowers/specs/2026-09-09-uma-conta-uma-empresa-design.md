# Uma conta, uma empresa

**Data:** 09/09/2026
**Estado:** ~~desenho aprovado, execução não começou~~ → **EXECUTADO** (09/09/2026).

> Este cabeçalho ficou dizendo "execução não começou" depois de a execução
> terminar, e um estado errado é pior que estado nenhum: quem lê planeja
> fazer de novo o que já está no banco. O que está abaixo descreve o sistema
> de hoje. Conferível no código: `Empresa.dono` e `Usuario.dono` existem com
> as unicidades descritas, o M2M `Usuario.empresas` saiu, e
> `contas.alcance.empresa_de` é quem deriva a empresa da conta.

## O problema

Hoje uma pessoa alcança VÁRIAS empresas (`Usuario.empresas`, M2M) e escolhe
no cabeçalho em qual está trabalhando. A empresa do momento mora na SESSÃO
(`plataforma.contexto.empresa_atual`), e o inquilino
(`contas.inquilino.GerenteDaEmpresa.do_contexto`) lê dali.

Isso põe a fronteira entre dois clientes numa variável de sessão. A trava
existe e funciona, mas ela depende de a tela lembrar de chamar `do_contexto`
— e "não misturar dados de clientes diferentes" é a única classe de defeito
que este produto não pode ter.

## A decisão

**Uma conta tem UMA empresa, e a empresa é da conta.** Não existe mais
escolher empresa: a pessoa tem a empresa da conta dela, e ponto.

A conta, neste branch, é o **Admin** — é o que `Perfil.dono` já diz.

## Decisões

### D1 — `Empresa.dono` → `Usuario`, com unicidade

A empresa aponta para o Admin dono. `UNIQUE` na coluna: um Admin, uma
empresa. É trava de BANCO e não convenção — convenção some no dia em que uma
tela nova esquecer dela.

Nulo é permitido, e significa "empresa sem conta ainda" — o estado em que a
MW5 cadastra a empresa antes de existir o Admin dela.

### D2 — `Usuario.dono` → `Usuario` (o Admin)

É como se sabe de qual conta a pessoa é. Nulo para o MASTER (a MW5 não é
cliente de conta nenhuma) e nulo para o próprio Admin (ele É a conta —
apontar para si mesmo seria um ciclo que toda consulta teria de tratar).

### D3 — `Usuario.empresas` (M2M) morre

A empresa da pessoa deixa de ser dado guardado e passa a ser DERIVADA:

    empresa_de(pessoa) =
        MASTER  -> None (alcança todas; escolhe qual conta olha)
        ADMIN   -> a empresa cujo dono é ele
        demais  -> a empresa cujo dono é o `dono` dela

Derivar em vez de guardar é o que impede os dois lados divergirem: com M2M,
mudar a empresa da conta e esquecer de mexer nas pessoas deixa gente
apontando para a empresa antiga, sem erro e sem aviso.

### D4 — O seletor de empresa some para quem não é MASTER

Não é a tela escondendo uma opção: não há opção. Para o MASTER ele continua,
com outro significado — "qual CONTA estou olhando" —, porque é o único que
tem mais de uma.

### D5 — O inquilino lê a CONTA, não a sessão

`GerenteDaEmpresa.do_contexto(request)` passa a resolver a empresa por
`empresa_de(pessoa)`. Sessão remendada e URL forjada deixam de ser caminhos:
não há o que forjar quando o valor não vem do pedido.

O `CHAVE_EMPRESA` da sessão continua existindo só para o MASTER.

### D6 — Admin com mais de uma empresa, na migração

A migração de dado precisa de uma regra para quem hoje alcança duas. Ela:

1. Para cada Admin, a empresa de MENOR id vira a dele.
2. As demais ficam **sem dono** — visíveis só para a MW5, que decide.
3. O que sobrou é escrito no log da migração, com nome e id.

Não apaga nada e não escolhe em silêncio: uma empresa órfã aparece na tela da
MW5, e uma empresa apagada não aparece em lugar nenhum.

### D7 — Quem cria usuário não escolhe empresa

`views_usuarios` deixa de ter o campo de empresas. O usuário novo nasce com
`dono` = o Admin que o criou (ou o `dono` de quem o criou, se um vendedor
criar alguém). O MASTER, ao criar, escolhe a CONTA.

## O que NÃO muda

- `Filial` continua M2M com usuário: filial é subdivisão DENTRO da empresa, e
  uma pessoa atende mais de uma.
- O `guid` de empresa nas tabelas de negócio continua onde está.
- Nível, papel e perfil: assunto de outro dia.
