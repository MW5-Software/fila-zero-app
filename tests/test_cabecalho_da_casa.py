"""Os templates DESTA CASA são cópias dos do design system — e cópia envelhece.

`plataforma/templates/` sobrescreve alguns templates do `nucleo` por duas
razões, e as duas são de tradução ou de estrutura que o componente não expõe:

- o cabeçalho ganhou o seletor de idioma ao lado do sino (ver
  `plataforma/header.py`);
- onze frases estavam escritas em português DENTRO do template — "Sair",
  "Abrir menu", "Fechar", "Página anterior" —, e nenhuma delas é parâmetro:
  não havia como traduzi-las de fora;
- `<html lang="pt-BR">` era fixo, e uma página inteira em castelhano anunciada
  como portuguesa faz o leitor de tela ler com a pronúncia errada.

O `nucleo` é porte verbatim e não se emenda (CLAUDE.md §2). O próprio design
system deixou a porta: `create_environment(*extra_loaders)` põe os loaders do
projeto na frente dos dele.

**O custo é o de toda cópia: ela envelhece calada.** No dia em que o design
system mudar um desses templates — um botão novo, uma classe trocada, uma
correção de acessibilidade —, esta casa continua desenhando a versão de ontem
e nada quebra.

Este teste é o alarme. Ele DESFAZ o que a casa acrescentou (troca
`{{ traduzir("X") }}` por `X`, `{{ idioma_html() }}` por `pt-BR`, remove o
bloco do seletor) e exige que o resultado seja idêntico ao arquivo do
`nucleo`. Qualquer outra diferença deixa a suíte vermelha, e a correção é
trazer a mudança de lá para cá à mão.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DO_NUCLEO = RAIZ / "nucleo" / "templates"
DA_CASA = RAIZ / "plataforma" / "templates"

#: O bloco que só existe na casa: o seletor de idioma do cabeçalho. O
#: `\{# O seletor` ancora no COMEÇO do comentário dela — sem isso o `.*?`
#: casaria a partir do comentário anterior, que é do próprio design system.
SELETOR = re.compile(
    r"\{# O seletor de idioma.*?#\}\s*"
    r"\{% if c\.idioma is defined and c\.idioma %\}.*?\{% endif %\}\s*",
    re.S)

#: O mesmo, na tela de entrada — lá o campo se chama `idiomas` e o controle é
#: de LINKS, porque antes do login não há conta em que gravar.
SELETOR_DA_ENTRADA = re.compile(
    r"\{# O seletor de idioma da entrada.*?#\}\s*"
    r"\{% if c\.idiomas is defined and c\.idiomas %\}.*?\{% endif %\}\s*",
    re.S)

TRADUZIR = re.compile(r'\{\{ traduzir\("((?:[^"\\]|\\.)*)"\) \}\}')

#: Comentário Jinja, dos DOIS lados.
#:
#: O alarme guarda a MARCAÇÃO — o que a tela desenha. Comentário não desenha
#: nada, e compará-lo faria de cada anotação nossa um alarme falso: toda vez
#: que esta casa explicasse por que mudou algo na cópia, o teste acusaria a
#: própria explicação. O comentário do `nucleo` que mudar continua valendo a
#: leitura de quem for sincronizar; ele só não dispara o alarme sozinho.
COMENTARIO = re.compile(r"\{#.*?#\}", re.S)

#: As cópias que mudam a ORDEM do que o design system desenha, com o motivo.
#:
#: Para elas a comparação não pode ser linha a linha na sequência — a
#: reordenação é justamente a diferença que se quer. O que continua valendo é
#: que as LINHAS sejam as mesmas: uma classe nova, um atributo trocado ou uma
#: correção de acessibilidade lá em cima muda alguma linha, e isso o teste
#: pega igual. O que ele deixa de pegar é a ordem — e é o preço declarado
#: aqui, não um esquecimento.
REORDENADOS = {
    "components/table.html":
        "a coluna de Ações vem PRIMEIRO nesta casa, e é a última no `nucleo`",
}


def _desfazer(texto: str) -> str:
    """A cópia da casa de volta ao que ela era quando foi copiada."""
    texto = SELETOR.sub("", texto)
    texto = SELETOR_DA_ENTRADA.sub("", texto)
    texto = TRADUZIR.sub(lambda m: m.group(1), texto)
    texto = texto.replace("{{ idioma_html() }}", "pt-BR")
    texto = COMENTARIO.sub("", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _linhas(texto: str) -> list[str]:
    """As linhas com conteúdo, normalizadas e ORDENADAS.

    É a comparação das cópias que reordenam: mesma matéria-prima, arrumada de
    outro jeito.
    """
    return sorted(
        linha for linha in (l.strip() for l in texto.split("\n")) if linha)


def _copias():
    return sorted(p for p in DA_CASA.rglob("*.html"))


def test_ha_copias_e_o_teste_esta_vendo_todas():
    """Se a pasta ficar vazia por acidente, os testes abaixo passariam sem
    conferir nada."""
    assert len(_copias()) >= 10


def test_nenhuma_copia_envelheceu():
    velhas = []
    for copia in _copias():
        rel = copia.relative_to(DA_CASA)
        original = DO_NUCLEO / rel
        assert original.exists(), (
            f"{rel} não existe no design system — ou o nome está errado, ou "
            f"esta cópia virou um template próprio e deveria sair desta pasta")
        da_casa = SELETOR.sub("", copia.read_text(encoding="utf-8"))
        da_casa = SELETOR_DA_ENTRADA.sub("", da_casa)
        da_casa = TRADUZIR.sub(lambda m: m.group(1), da_casa)
        da_casa = da_casa.replace("{{ idioma_html() }}", "pt-BR")
        da_casa = COMENTARIO.sub("", da_casa)
        do_nucleo = COMENTARIO.sub("", original.read_text(encoding="utf-8"))

        if str(rel) in REORDENADOS:
            # Mesmas linhas, outra ordem — ver `REORDENADOS`.
            igual = _linhas(da_casa) == _linhas(do_nucleo)
        else:
            igual = _normalizar(da_casa) == _normalizar(do_nucleo)
        if not igual:
            velhas.append(str(rel))

    assert velhas == [], (
        "o design system mudou e a cópia desta casa não: "
        f"{velhas}. Traga a mudança de `nucleo/templates/` para "
        "`plataforma/templates/` à mão, preservando as chamadas de "
        "`traduzir(...)` e o bloco do seletor de idioma.")


def test_as_copias_ainda_traduzem():
    """A outra ponta: se alguém 'ressincronizar' colando o arquivo do `nucleo`
    por cima, as frases voltam ao português sem erro nenhum."""
    sem_traducao = [
        str(p.relative_to(DA_CASA)) for p in _copias()
        if "traduzir(" not in p.read_text(encoding="utf-8")
        and "idioma_html()" not in p.read_text(encoding="utf-8")]

    assert sem_traducao == [], (
        f"cópia sem nenhuma tradução — provavelmente colada por cima: "
        f"{sem_traducao}")


def test_o_cabecalho_ainda_desenha_o_seletor():
    cabecalho = (DA_CASA / "layout" / "header.html").read_text(encoding="utf-8")
    assert "c.idioma" in cabecalho


class TestAsCopiasQueReordenam:
    """`REORDENADOS` afrouxa a comparação — então ele precisa de trava.

    Sem estes dois testes, pôr um arquivo naquele dicionário viraria a
    maneira fácil de calar o alarme: ele deixaria de comparar a sequência, e
    ninguém lembraria de conferir se ainda compara alguma coisa.
    """

    def test_toda_isencao_tem_motivo_escrito(self):
        sem_motivo = [nome for nome, motivo in REORDENADOS.items()
                      if not (motivo or "").strip()]
        assert sem_motivo == [], (
            f"isenção sem motivo ao lado: {sem_motivo}. Isenção sem motivo "
            "vira gaveta, e gaveta ninguém relê.")

    def test_a_isencao_aponta_para_uma_copia_que_existe(self):
        fantasmas = [nome for nome in REORDENADOS
                     if not (DA_CASA / nome).exists()]
        assert fantasmas == [], (
            f"isenção de arquivo que não é mais cópia desta casa: {fantasmas}")

    def test_a_reordenacao_ainda_pega_linha_trocada(self):
        """A prova de que afrouxar a ORDEM não desligou o alarme: uma linha
        diferente continua sendo diferença."""
        original = "<a>\n<b>\n<c>"
        reordenado = "<c>\n<a>\n<b>"
        mexido = "<c>\n<a>\n<b class='novo'>"

        assert _linhas(reordenado) == _linhas(original)
        assert _linhas(mexido) != _linhas(original)


def test_a_coluna_de_acoes_vem_primeiro():
    """A decisão de 10/09/2026, presa no arquivo: no `nucleo` a coluna de
    Ações é a ÚLTIMA; aqui ela é a primeira.

    As duas posições têm defesa — à direita o olho lê o registro antes de agir
    sobre ele; à esquerda a mão acha o botão no mesmo lugar em toda tabela,
    sem depender de quantas colunas cada tela tem nem de onde a rolagem
    horizontal parou. Pesou a segunda: as tabelas deste portal variam muito de
    largura, e o catálogo rola na horizontal.
    """
    tabela = (DA_CASA / "components" / "table.html").read_text(encoding="utf-8")
    corpo = tabela[tabela.index("<tbody>"):]

    assert corpo.index("c.actions_for(row)") < corpo.index("col.value_of(row)"), (
        "a coluna de ações voltou para o fim da linha")
