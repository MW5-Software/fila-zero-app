# Roadmap da base do KRONOS.net

> Escrito em 21/08/2026, depois da decisão R47 (módulos fixos — ver
> `decisoes-2026-08-20-fatia-fina.md`). Este documento é sobre a **base**: o
> que todo módulo de negócio vai pressupor. Módulo de negócio em si não entra
> aqui.

A ordem não é preferência, é dependência. Os itens de cima mudam o formato do
que vem depois; adiá-los multiplica o custo pelo número de módulos que já
existirem.

---

## Pronto

1. Login, sessão, troca da própria senha, foto de perfil
2. Permissão por módulo e ação, com coringa por módulo
3. `Perfil` como conjunto de permissões, somando com as permissões diretas
4. Telas de Usuários e Perfis, com a fronteira MW5 × cliente testada por ataque
5. Usuário da MW5 nascendo com a instalação, sem senha utilizável
6. Auditoria gravando — 19 ações, append-only, autor guardado como texto
7. Personificação, com aviso em toda tela e trilha dizendo quem agiu de verdade
8. Catálogo de módulos: o código declara, o banco liga; módulo novo aparece
   sozinho nas vinte instalações
9. Marca por instalação — **cores** (menu, cabeçalho, conteúdo, rodapé),
   arredondamento, largura do menu, densidade. Tela de Aparência funcionando
10. Padrão de tabela: busca por coluna, ordenação, paginação — com varredura
    que deixa o teste vermelho se uma tela nova esquecer (R46)
11. Imagem Docker, migrações, 884 testes em ~18s

---

## Falta na base, em ordem de dependência

### Bloco 1 — Empresa e filial (mexe em tudo que vier depois)

12. `Empresa` e `Filial` como tabelas, e a coluna em toda tabela de dado
13. Seletor no topo e o contexto viajando na sessão
14. Permissão por empresa/filial — a pessoa vê a filial A e não a B
15. Toda consulta filtrando por contexto, com varredura que cobre isso

### Bloco 2 — O que sustenta a decisão de módulos fixos (R47)

16. Parâmetros por instalação, com tela — texto, número, sim/não
17. Campo opcional declarado no código e ligado por parâmetro, sumindo também
    do relatório, da exportação e do filtro quando desligado
18. Limite de oito campos opcionais por tabela — não é regra técnica, é o
    alarme que avisa **com dado** quando o nível 2 (campos configuráveis)
    passou a se pagar
19. Varredura: nenhum nome de cliente no código. É o que impede a matriz de
    virar vinte sistemas por dentro sem ninguém perceber

### Bloco 3 — Marca, completando o que falta

20. **Logo e favicon no banco** — hoje não existe campo nenhum; o design
    system já sabe desenhar (as áreas de logo existem em `nucleo/theme`), só
    não há onde guardar. Mesmo caminho do `Avatar`: bytes no banco, validação
    por conteúdo com `nucleo/images.py`, rota que serve
21. Logo por área (menu, cabeçalho, rodapé, tela de entrada) — o design
    system já prevê tamanhos diferentes para cada uma
22. Expor na tela de Aparência o que o banco já guarda e a tela ainda não
    mostra: `radius_control`, `density`, `shadows`, `zebra`
23. Prévia ao vivo na tela de Aparência

### Bloco 4 — O que toda tela vai pedir

24. Tela de leitura da auditoria (hoje ela só grava)
25. Exportar — Excel, PDF, impressão — levando o filtro que está na tela
26. Anexos em qualquer registro
27. Filtros salvos e favoritos

### Bloco 5 — Brasil

28. Máscara e validação: CPF, CNPJ, Inscrição Estadual, CEP
29. Cidades e UF por IBGE
30. Moeda, casas decimais, arredondamento

### Bloco 6 — Documento e período

31. Numeração de documento por empresa e por série
32. Período e fechamento de competência

### Bloco 7 — Operação

33. E-mail e notificação
34. Tarefas de fundo e agendamento
35. Erro em produção: onde cai, quem vê
36. Backup e restauração
37. Política de senha, expiração, tempo de sessão
38. Importação dos legados

---

## Fechar o que está aberto

39. Merge do branch `contas`
40. Roteiro de aceite — o cliente clicando, no container
41. As 11 pendências parqueadas na revisão final (ver `progress.md` do plano
    de contas)

---

## Depois da base

42. Primeiro módulo de negócio real
43. Segundo módulo, de **outro segmento** — é ele que revela a variação de
    verdade, e é com ele que a decisão de subir para campos configuráveis
    deixa de ser palpite

---

## Estado em 22/08/2026 — releitura do repositório

O branch `contas` foi mergeado; o trabalho agora vive em `main`, com 116
commits e **1320 testes**, sem deriva de migração. O que este documento
listava como "falta" mudou bastante desde 21/08 — releitura item a item:

### Fechado desde a escrita deste roadmap

- **Bloco 1 inteiro** — empresa, filial, contexto na sessão, seletor no
  cabeçalho, telas e filial por pessoa.
- **Bloco 2, itens 16 e 19** — parâmetros por instalação (declarados no
  código, valorados no banco) e a varredura que recusa nome de cliente no
  código.
- **Bloco 3 inteiro** — `ImagemDaMarca` guarda logo e favicon no banco,
  logo por área, a Aparência passou a expor o que o banco já guardava,
  prévia ao vivo, e o cliente nomeia o contexto (filial pode virar "loja").
- **Bloco 4, três de quatro** — tela de leitura da auditoria, exportar
  (Excel e impressão) levando o filtro, e filtros salvos e favoritos nas
  quatro listagens.
- **Bloco 5, dois de três** — CPF, CNPJ, IE e CEP validados e normalizados;
  UF pelo IBGE e a política da moeda em pt-BR.
- **Bloco 7, quatro itens** — política de acesso (sessão por inatividade e
  senha que expira, via `MarcaDeSenha`), erro em produção (`Falha` e a tela
  `/mw5/falhas`), backup e restauração testados no ciclo inteiro, e os
  estáticos servidos em produção por whitenoise.

### O que continua faltando

1. **Bloco 2, itens 17 e 18** — campo opcional ligado por parâmetro, e o
   alarme dos oito campos por tabela. Adiados de propósito: sem um campo real
   para esconder, o mecanismo seria máquina sem usuário. Nascem com o
   primeiro pedido de verdade.
2. **Anexos em qualquer registro** (Bloco 4). Não existe model de anexo. O
   caminho já foi trilhado duas vezes — `Avatar` e `ImagemDaMarca` guardam
   bytes no banco com validação por conteúdo.
3. **Cidades pelo IBGE** (Bloco 5). A UF foi validada; a tabela de municípios
   não existe.
4. **Bloco 6 inteiro** — numeração de documento por empresa e série;
   período e fechamento de competência. Nenhum dos dois tem model.
5. **Bloco 7, o que sobra** — e-mail e notificação; tarefas de fundo e
   agendamento; importação dos legados.
6. **Roteiro de aceite executado** — o roteiro está escrito no `README.md`
   até o Bloco 5; falta o cliente percorrê-lo clicando.
7. **As 11 pendências parqueadas** da revisão final da entrega 2, listadas em
   `.superpowers/sdd/2026-08-21-contas/progress.md`.

### Observação de dependência

Os itens 4 e 5 (numeração, período, e-mail, agendamento) são os únicos que um
módulo de negócio pode precisar antes de existir. Anexos e cidades podem
nascer junto do primeiro módulo que os pedir, sem custo de retrabalho — não
mudam o formato de tabela nenhuma, ao contrário do que empresa/filial mudava.
