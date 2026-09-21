# De onde este projeto veio

O **Fila Zero** é uma cópia da **KRONOS base** (`/home/mw5/projetos/kronos-base`)
no commit **be166c4** (15/09/2026), seguindo o roteiro do `CLAUDE.md` da base:
conta, empresa, filial, usuário, cargos e alocações, permissão, auditoria,
aparência, módulos, parâmetros, backup e o design system vieram prontos. O
negócio deste produto — a fila da vez das lojas — é construído por cima.

Não vieram o `.git` da base (repositório próprio, sem caminho acidental de push
para o lugar errado), a `.venv`, `midia/`, `backups/` e os caches.

O que veio da base continua descrito nas seções 1 a 9 do `CLAUDE.md`.

## O que o Fila Zero pôs por cima (entrega 1, 15/09/2026)

- A identidade: marca "Fila Zero", `pyproject` `fila-zero`, imagem
  `ghcr.io/mw5-software/fila-zero`, portas 5436/8005 (o banco foi para a
  5440 em 21/09/2026: o kronos-api2 tinha tomado a 5436).
- O app `fila/`, com as permissões `fila.ver`, `fila.participar`,
  `fila.gerenciar` e `fila.cadastros` nos cargos de fábrica e no titular.
- A raiz `/` passa por `fila.views.inicio`, que manda para `/fila` quem só tem a
  fila de vendedor.
- **Mudança de base que vale levar de volta à KRONOS base:** a tela de Usuários
  responde com frase ("tem histórico gravado; desative em vez de remover")
  quando um módulo de negócio protege a pessoa com `PROTECT`, em vez de 500.
