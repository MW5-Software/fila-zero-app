"""R47 (`docs/superpowers/decisoes-2026-08-20-fatia-fina.md`): o KRONOS.net é
de módulos fixos — particularidade de cliente vira módulo, permissão ou
parâmetro, nunca um `if` escrito com o nome dele espalhado pela matriz. No
dia em que existir `if cliente == "acme":` numa tela, a matriz volta a ser
vinte sistemas por dentro de um código só, e é exatamente o defeito que essa
decisão nasceu para impedir.

A varredura irmã de `tests/test_guarda.py`, `tests/test_guarda_modulo.py` e
`tests/test_regra_tabela.py`: caminha o Python que este projeto escreve —
nunca `nucleo/` (congelado, exceto `nucleo/views.py` — ver o comentário de
`ARQUIVOS_ADICIONAIS`, abaixo) nem `tests/` — e falha se algum comparador
(`==`, `!=`, `in`, `not in`) tiver de um lado um identificador que cheira a
"qual instalação é esta" e do outro um literal de texto.

Por que não uma busca por substring: "cliente" aparece centenas de vezes
neste projeto, em comentário e docstring, como prosa normal ("o admin do
CLIENTE decide", "particularidade de CLIENTE vira código") — uma busca de
texto afogaria num mar de acertos que não são o defeito, e a primeira
correção de alguém cansado seria desligar a varredura inteira, não só o
falso positivo. Por isso esta varredura lê a ÁRVORE do Python (`ast`), não o
texto do arquivo: só entra na conta um `ast.Compare` de verdade — código que
DECIDE algo comparando um identificador a uma string —, e um comentário não é
um nó de comparação, então nunca aparece aqui.

Por que não só "recusar toda comparação com string": comparar `acao ==
"criar"`, `tipo == "numero"`, `situacao == "1"` é o vocabulário normal deste
projeto inteiro (ver `plataforma/views_filiais.py`, `plataforma/
parametro_catalogo.py`...) — um discriminador de ação ou de tipo não é
particularidade de cliente, é a MESMA regra valendo para todo mundo. O que
distingue o defeito não é "comparar com string", é o NOME do identificador
comparado: só entra na lista quem parece guardar a IDENTIDADE da instalação
(`cliente`, `instalacao`, `tenant`...), nunca um verbo de ação ou um tipo.
Esta escolha é um meio-termo deliberado, não uma prova formal: um autor que
batizasse a variável de "empresa_x" em vez de "cliente_x" escaparia da
varredura — mas escaparia tendo que escrever um nome estranho o bastante
para chamar atenção na revisão, o que já é mais do que uma busca de texto
qualquer ofereceria.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: As pastas que este projeto escreve — ver o docstring do módulo para o
#: porquê de excluir `nucleo/` (congelado) e `tests/` (a própria varredura).
# `comum` entrou aqui junto com o pacote: a extração que criou
# `comum/` moveu sete arquivos para fora de `contas` e `plataforma`, e
# sem esta linha eles sairiam da varredura sem que nada acusasse — a
# suíte só ficaria 7 testes menor, o que ninguém lê como defeito.
PASTAS = ("contas", "plataforma", "modulos", "comum")

#: `nucleo/views.py` é a única exceção ao congelamento de `nucleo/` — este
#: projeto é o autor dela (ver `tests/test_personificacao.py`, comentário
#: sobre `demonstracao`), então ela entra na varredura como as outras.
ARQUIVOS_ADICIONAIS = ("nucleo/views.py",)

#: Pedaços de identificador que cheiram a "qual instalação/cliente é esta".
#: Case-insensitive e por substring (`client_name`, `nome_cliente`,
#: `instalacao_atual` todos batem) — de propósito, para não depender de
#: adivinhar toda variação de maiúscula ou de prefixo/sufixo.
SUSPEITOS = ("cliente", "client", "instalacao", "installation", "tenant")

#: Rotas/arquivos isentos, e o motivo de cada um — mesmo espírito de
#: `comum.guardas_de_acesso.TELAS_ABERTAS`: uma lista curta, com o motivo ao lado,
#: para "esqueci" nunca virar razão de um nome entrar aqui. Vazia hoje:
#: nenhum arquivo do projeto precisa comparar identidade de instalação a um
#: literal de texto.
EXEMPTAS: frozenset[str] = frozenset()


def _identificador_de(node: ast.AST) -> "str | None":
    """O nome "de identidade" de `node`, se ele for um `Name` (`cliente`) ou
    um `Attribute` (`request.cliente`, onde o que importa é o `cliente`
    final) — ou `None` para qualquer outra coisa (uma chamada, uma conta,
    etc., que não é isto que a varredura procura)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _e_suspeito(identificador: str) -> bool:
    identificador = identificador.lower()
    return any(pedaco in identificador for pedaco in SUSPEITOS)


def _e_literal_de_texto(node: ast.AST) -> bool:
    """Um literal que a comparação testa: uma string sozinha (`"acme"`), ou
    uma coleção só de strings (`("acme", "beta")`, o alvo de um `in`)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)) and node.elts:
        return all(
            isinstance(item, ast.Constant) and isinstance(item.value, str)
            for item in node.elts
        )
    return False


def _problemas_no_arquivo(caminho: Path) -> list[str]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    problemas = []

    for node in ast.walk(arvore):
        if not isinstance(node, ast.Compare):
            continue
        # `a == b == c` é um `Compare` só, com dois operadores e três
        # operandos — caminha par a par, e não só `left`/`comparators[0]`,
        # para uma comparação encadeada não escapar da varredura.
        operandos = [node.left, *node.comparators]
        for indice, operador in enumerate(node.ops):
            if not isinstance(operador, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                continue
            esquerda, direita = operandos[indice], operandos[indice + 1]
            for lado_nome, lado_literal in ((esquerda, direita), (direita, esquerda)):
                identificador = _identificador_de(lado_nome)
                if (identificador and _e_suspeito(identificador)
                        and _e_literal_de_texto(lado_literal)):
                    problemas.append(
                        f"{caminho}:{node.lineno}: comparação com "
                        f"{identificador!r} — particularidade de cliente "
                        f"pertence a um módulo, uma permissão ou um "
                        f"parâmetro, nunca a um `if` com o nome dele."
                    )
                    break
    return problemas


def _arquivos_do_projeto() -> list[Path]:
    raiz = Path(__file__).resolve().parent.parent

    arquivos = []
    for pasta in PASTAS:
        arquivos.extend(sorted((raiz / pasta).rglob("*.py")))
    for extra in ARQUIVOS_ADICIONAIS:
        arquivos.append(raiz / extra)

    return [
        a for a in arquivos
        if "__pycache__" not in a.parts
        and str(a.relative_to(raiz)) not in EXEMPTAS
    ]


@pytest.mark.parametrize("caminho", _arquivos_do_projeto(), ids=lambda p: str(p))
def test_nenhum_arquivo_compara_identidade_de_cliente_a_um_literal(caminho):
    problemas = _problemas_no_arquivo(caminho)
    assert not problemas, (
        f"{'; '.join(problemas)}. Particularidade de cliente entra pela "
        f"declaração de um módulo (`plataforma/declaracao.py`), por uma "
        f"permissão (`contas/guardas.py`) ou por um parâmetro "
        f"(`plataforma/parametro_declaracao.py`) — nunca por um `if` "
        f"escrito com o nome dele."
    )
