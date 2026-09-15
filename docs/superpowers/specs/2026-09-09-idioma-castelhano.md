# Idioma: a moldura em castelhano (09/09/2026)

O portal vai ser vendido também no Paraguai. Decidido com o João: **só a
moldura** muda de idioma nesta entrega.

## O que muda, e o que não muda

- **Muda**: menu, botões, rótulos, títulos, mensagens de erro e de sucesso —
  tudo que este projeto escreveu no código.
- **Não muda**: o catálogo. Nome de peça, família, linha, segmento, marca,
  aplicação e atributo são dado que o cliente digitou e moram em linha de
  tabela. Nenhum arquivo de tradução alcança linha de tabela. Um comprador
  paraguaio vê o sistema em castelhano e as peças em português até alguém
  traduzir o CONTEÚDO — o que é outro trabalho, com coluna por idioma em seis
  tabelas, tela de cadastro por idioma, busca nos dois e planilha de ida e
  volta para traduzir em massa.

## As decisões

1. **O idioma é coluna da pessoa** (`contas.Usuario.idioma`), não variável de
   sessão: a preferência tem que sobreviver ao logout, e a sessão é derrubada
   inteira ao trocar senha ou encerrar personificação.
2. **A escolha desta sessão vence a coluna.** "Escolhi agora, vale agora" — e
   é o que faz a escolha feita na TELA DE ENTRADA continuar valendo depois do
   login, quando a coluna ainda diz o padrão.
3. **Middleware da casa, não o `LocaleMiddleware` do Django**: o de lá decide
   por prefixo de URL, cookie e cabeçalho do navegador. Aqui quem decide é a
   pessoa. Um vendedor brasileiro num computador configurado em espanhol
   continua vendo português.
4. **Duas portas para trocar.** Logado: POST com CSRF, em Meu Perfil. Antes de
   entrar: link na tela de entrada (`?idioma=es`) — ali não há conta nem
   coluna, e exigir POST custaria uma tela a mais justamente para quem abriu o
   sistema pela primeira vez e não entende o que está escrito.
5. **Babel, e não `makemessages`.** O extrator do Django precisa do `xgettext`
   do sistema e não lê template Jinja2, que é o desta casa. O Babel é Python
   puro e entra como dependência.

## O `nucleo` — resolvido em 09/09/2026, e como

**As onze frases foram traduzidas sem emendar o design system.** O que faltava
não era mecanismo: era perceber que a porta já estava aberta. O
`create_environment(*extra_loaders)` do `nucleo` põe os loaders do projeto na
FRENTE dos dele — "a saída de emergência para quando um cliente precisa de uma
variação que não vale a pena generalizar", diz o docstring de lá.

Então `plataforma/templates/` sobrescreve dez templates: o cabeçalho, a barra
lateral, a trilha, a página, a entrada, a paginação, o modal, a gaveta, o
aviso, o campo, a caixa de seleção, o girador e a linha de item. Em cada um,
o texto fixo virou `{{ traduzir("...") }}` e o `lang="pt-BR"` virou
`{{ idioma_html() }}`.

`traduzir` e `idioma_html` são dois globais que `comum/ambiente.py` acrescenta
ao ambiente Jinja depois de criá-lo — de novo, sem tocar no `nucleo`.

**O custo é a cópia, e ele tem alarme.** Dez arquivos que não acompanham o
design system se ele mudar. `tests/test_cabecalho_da_casa.py` DESFAZ o que a
casa acrescentou (troca as chamadas de `traduzir` pelo texto, o
`idioma_html()` por `pt-BR`, remove o bloco do seletor) e exige que o
resultado seja idêntico ao arquivo do `nucleo`. Qualquer outra diferença fica
vermelha, e a correção é trazer a mudança à mão.

O gatilho de extrair o design system para pacote continua disparado (CLAUDE.md
§6.2) — e agora com mais um motivo: são dez templates a mais para
ressincronizar no dia em que alguém mexer lá.

## O que ficou de fora — histórico da decisão

O design system é porte verbatim e não se emenda (CLAUDE.md §2). A maior parte
do texto dele é PARÂMETRO com padrão em português, e isso já está resolvido:
o produto passa a frase traduzida (ver `SiteDoProduto._user_info` e o
`PerfilPage` em `contas/views_perfil.py`).

O que NÃO é parâmetro, e continua em português mesmo em castelhano:

- `title`/`aria-label` fixos nos templates: "Abrir menu", "Recolher menu",
  "Notificações", "Sair", "Início", "Menu principal", "Você está em".
- `<html lang="pt-BR">` em `page.html` e `login.html` — o leitor de tela vai
  anunciar a página como portuguesa.

São onze frases e um atributo. Três saídas, e a escolha é de produto:

1. Aceitar em português (só aparece em tooltip e leitor de tela);
2. Abrir exceção e marcar essas onze no `nucleo`, o que quebra o "porte
   verbatim" — e ele está em quatro cópias hoje;
3. Extrair o design system para pacote, que a própria CLAUDE.md já diz que
   virou obrigação ("o gatilho já disparou").

## Como mexer nas traduções

```bash
# 1. extrair as frases marcadas do código para o modelo
.venv/bin/pybabel extract -F babel.cfg -o locale/portal.pot --no-location \
  --omit-header -k _ -k gettext -k gettext_lazy -k "ngettext:1,2" \
  --input-dirs=contas,plataforma,comum,modulos

# 2. mesclar no catálogo espanhol, preservando o que já foi traduzido
.venv/bin/pybabel update -i locale/portal.pot -d locale -D django --no-fuzzy-matching

# 3. traduzir os `msgstr ""` em locale/es/LC_MESSAGES/django.po

# 4. compilar (é o `.mo` que o sistema lê, não o `.po`)
.venv/bin/pybabel compile -d locale -D django
```

**Português não tem arquivo, e não é esquecimento**: a frase escrita no código
JÁ é o português. `gettext` devolve o original quando não acha tradução, então
`pt-br` funciona com catálogo nenhum — e é o que faz os 1.939 testes, que
conferem frase em português, continuarem valendo sem tocar em nada.

## Estado (09/09/2026)

Marcadas e traduzidas: **175 frases** — menu, rótulos de formulário, títulos
de tela, botões e as mensagens de recusa.

Falta marcar: o texto que mora DENTRO de HTML montado à mão (`format_html`),
que é a maior parte do corpo das telas — a frase de ajuda da busca, os nomes
das abas de refino, os títulos das seções da peça. São ~760 frases, e cada uma
precisa de olho: `f"{n} produtos"` não vira `_()` direto, tem que virar
`_("%(n)s produtos") % {...}`, senão a tradução some no dia em que o número
mudar de lugar na frase.

**A revisão do castelhano continua pendente.** O que está no `.po` hoje é
tradução minha, formal (usted), rio-platense. Palavra de peça é onde mais se
erra: quem vende no Paraguai precisa passar o olho antes de a primeira visita
acontecer.
