"""O que o script esconde precisa sumir de verdade.

**`[hidden]` é a regra mais fraca que existe para esconder algo**, e não por
especificidade: ela mora na folha do NAVEGADOR, e estilo de autor vence estilo
de navegador sempre. Qualquer `.minha-classe { display: grid }` escrita por
nós anula o `[hidden] { display: none }` que o navegador declara — e a
especificidade nem chega a ser consultada.

O resultado é o pior tipo de defeito de tela: o script roda, marca o elemento
como escondido, e nada acontece. O filtro "funciona" e não filtra.

O conserto é declarar de novo, do nosso lado: `.minha-classe[hidden] {
display: none }`. Aí são dois estilos de autor, e o do atributo ganha por
especificidade.

Já aconteceu TRÊS vezes nesta base — no filtro por marca da vitrine, nas abas
da página do produto, e na caixa de escolha com busca (10/09/2026, o painel
nascia aberto em cima do formulário) —, e nenhuma suíte pegaria: **os testes
desta casa não rodam JavaScript**. A regra mora na folha, então é a folha que
este arquivo lê.

**A terceira vez aconteceu porque a lista era só manual.** `ESCONDIDOS` cobria
o que alguém lembrou de escrever nela, e a classe nova não estava lá — que é
exatamente o destino de toda lista que depende de memória. Ela continua, para
os elementos que o SERVIDOR desenha; ao lado dela entrou uma varredura que lê
os scripts desta casa e descobre sozinha quem o script esconde.
"""

import re
from pathlib import Path

import pytest

#: As folhas e os scripts da BASE. Cada SaaS que acrescentar um módulo com
#: script próprio põe a pasta dele aqui — no Portal de Vendas, a do catálogo,
#: onde os três casos que deram nome a este arquivo aconteceram.
PASTAS_ESTATICAS = (Path("contas/static"), Path("plataforma/static"),
                    Path("modulos"), Path("fila/static"))

#: `(classe, quem esconde)`. Toda classe que o script marca com `hidden` E que
#: declara `display` na folha precisa estar aqui — e precisa ter a regra.
ESCONDIDOS: "list[tuple[str, str]]" = []

#: Onde moram os scripts desta casa. A varredura automática lê todos.
SCRIPTS = sorted(p for pasta in PASTAS_ESTATICAS for p in pasta.rglob("*.js"))


def _folha() -> str:
    """Todas as folhas da base juntas: a regra de `hidden` pode morar em
    qualquer uma que a página carregue."""
    return "\n".join(p.read_text(encoding="utf-8")
                     for pasta in PASTAS_ESTATICAS
                     for p in sorted(pasta.rglob("*.css")))


class TestOQueOScriptEscondeSome:
    @pytest.mark.parametrize("classe,quem", ESCONDIDOS)
    def test_tem_a_regra_de_hidden(self, classe, quem):
        assert re.search(
            re.escape(classe) + r"\[hidden\]\s*\{[^}]*display:\s*none",
            _folha()), (
            f"{classe} declara `display` e é escondida por {quem}: sem "
            f"`{classe}[hidden] {{ display: none }}` o script marca e o "
            f"elemento continua na tela")


def _classes_que_o_script_esconde(script: str) -> set[str]:
    """As classes dos elementos que ESTE script marca com `hidden`.

    Descobre pelo estilo da casa, que é sempre o mesmo: o elemento nasce em
    `var x = document.createElement(...)`, ganha `x.className = "alguma-coisa"`
    e em algum ponto recebe `x.hidden = ...`. Ligando os dois pelo NOME DA
    VARIÁVEL, a lista sai do próprio arquivo — e não da memória de quem
    escreveu.

    Não pega tudo (uma classe montada por concatenação escapa), e não precisa:
    o que ela pega é o caso comum, que é o que já falhou três vezes.
    """
    classe_de = dict(re.findall(
        r'(\w+)\.className\s*=\s*"([\w-]+)"', script))
    escondidas = set(re.findall(r'(\w+)\.hidden\s*=', script))
    return {classe_de[nome] for nome in escondidas if nome in classe_de}


def _declara_display(folha: str, classe: str) -> bool:
    """Se a folha declara `display` para esta classe — é isso que anula o
    `hidden` do navegador. Sem `display` declarado, não há o que anular."""
    for corpo in re.findall(
            r"\." + re.escape(classe) + r"\s*\{([^}]*)\}", folha):
        if re.search(r"(^|;)\s*display\s*:", corpo):
            return True
    return False


class TestAVarreduraAcha_SozinhaQuemOScriptEsconde:
    """A rede embaixo da lista manual: ela lê os scripts, não a memória."""

    @pytest.mark.parametrize(
        "caminho", SCRIPTS, ids=lambda c: c.name)
    def test_toda_classe_escondida_por_script_tem_a_regra(self, caminho):
        folha = _folha()
        faltando = []
        for classe in sorted(_classes_que_o_script_esconde(
                caminho.read_text(encoding="utf-8"))):
            if not _declara_display(folha, classe):
                continue
            if not re.search(re.escape("." + classe)
                             + r"\[hidden\]", folha):
                faltando.append(classe)
        assert not faltando, (
            f"{caminho.name} esconde estas classes com `hidden`, e a folha "
            f"declara `display` para elas: {faltando}. Sem "
            f"`.classe[hidden] {{ display: none }}` o script marca e o "
            f"elemento continua na tela.")

    def test_a_varredura_enxerga_o_caso_que_ja_falhou(self):
        """Prova de que ela não passa por passar: o `.cb-painel` da caixa com
        busca do Portal de Vendas (10/09/2026) é reconstruído aqui em
        miniatura — a base não tem aquele script, e a varredura precisa
        continuar achando o caso."""
        script = (
            'var painel = document.createElement("div");\n'
            'painel.className = "cb-painel";\n'
            'painel.hidden = true;\n')
        folha = ".cb-painel { display: grid; }"
        achadas = _classes_que_o_script_esconde(script)
        assert "cb-painel" in achadas
        assert _declara_display(folha, "cb-painel")
