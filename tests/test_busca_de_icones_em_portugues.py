"""Buscar ícone em português numa biblioteca etiquetada em inglês.

A queixa era "tem pouco ícone". Não tinha: são 2007 do Lucide, mais 67 da casa.
O que faltava era chegar neles.

As 1756 etiquetas do arquivo do Lucide são todas em inglês — nenhuma com
acento. `caminhao`, `frete` e `mapa` devolviam ZERO, enquanto `truck` devolvia
três: as palavras `delivery`, `shipping` e `lorry` estavam no arquivo o tempo
todo, do outro lado de uma tradução que ninguém tinha escrito.
"""

import pytest
from nucleo import icons


class TestOAcervoJaEraGrande:
    def test_ha_milhares_de_icones(self):
        """A premissa: se um dia o arquivo do Lucide sair, isto vira um teste
        sobre uma biblioteca de 67 e o resto do arquivo perde o sentido."""
        assert len(icons.names()) > 1500

    def test_o_conjunto_da_casa_e_pequeno_de_proposito(self):
        """São os que combinam com o resto do sistema. Não é o acervo."""
        assert 50 < len(icons.ICONS) < 150


class TestOPortuguesAlcancaOInglês:
    #: Palavras que devolviam ZERO antes da tabela de tradução. Não é uma lista
    #: de exemplos: é a lista dos que quebraram na medição.
    QUEBRAVAM = ("caminhao", "frete", "mapa", "peso", "calendario", "senha")

    @pytest.mark.parametrize("termo", QUEBRAVAM)
    def test_nao_devolve_mais_vazio(self, termo):
        assert icons.buscar(termo), f"`{termo}` voltou a não achar nada"

    def test_o_acento_nao_muda_o_resultado(self):
        assert icons.buscar("caminhão") == icons.buscar("caminhao")

    def test_a_traducao_alcanca_alem_dos_nomes_curados(self):
        """`SINONIMOS` responde com uma lista escrita a dedo; a tradução
        alcança todo ícone cuja etiqueta em inglês tenha a palavra. Buscar
        "mapa" tem de trazer bem mais do que alguém teria listado."""
        assert len(icons.buscar("mapa")) > 20

    def test_chave_do_dicionario_sem_acento(self):
        """`buscar` normaliza antes de comparar: uma chave acentuada aqui
        nunca casaria."""
        for chave in icons.TRADUCOES:
            assert chave == icons._sem_acento(chave), (
                f"a chave `{chave}` tem acento e nunca vai casar")


class TestOQueOTermoNaoPodeTrazer:
    """Achar não basta. O ruído empurra para fora do limite justamente o ícone
    que a pessoa procurava."""

    def test_senha_nao_traz_despertador(self):
        """`lock` casava dentro de `clock`, e a busca por senha vinha com
        quarenta despertadores."""
        assert not [n for n in icons.buscar("senha") if "alarm" in n]

    def test_carro_nao_traz_cartao(self):
        """`car` dentro de `card`."""
        assert "card" not in icons.buscar("carro")

    def test_a_traducao_casa_palavra_inteira(self):
        assert icons._casa_palavra(["lock"], ["lock"])
        assert not icons._casa_palavra(["lock"], ["clock"])
        assert not icons._casa_palavra(["car"], ["card"])


class TestAOrdemEOResultado:
    def test_o_obvio_vem_primeiro(self):
        """Sem faixa nenhuma, `mapa` devolvia `arrow-down-to-dot` antes de
        `map`: tudo vinha por etiqueta, em ordem alfabética, e o ícone certo
        caía na terceira fileira — ou fora do limite."""
        assert icons.buscar("mapa")[0] == "map"
        assert icons.buscar("lixeira")[0] == "trash"
        assert icons.buscar("calendario")[0] == "calendar"

    def test_o_nome_curto_antes_do_composto(self):
        """Quem procura uma chave quer a chave; `book-key` é o caso raro."""
        r = icons.buscar("chave")
        assert r.index("key") < r.index("book-key")

    def test_o_nome_vence_a_etiqueta(self):
        """Casar no nome é sinal mais forte do que casar numa das onze
        etiquetas de um ícone."""
        r = icons.buscar("mapa")
        assert r.index("map-pin") < r.index("locate")

    def test_a_curadoria_vence_as_duas(self):
        """`SINONIMOS` é a resposta escolhida a dedo para a palavra."""
        assert icons.buscar("estoque")[:4] == list(icons.SINONIMOS["estoque"])


class TestOLimiteNaoCortaOProprioConjuntoDaCasa:
    def test_a_busca_vazia_mostra_pelo_menos_a_casa_inteira(self):
        """O limite era 60, e 60 é menos do que os 67 da casa: a grade abria
        cortando o próprio conjunto curado, e quem olhava concluía que a
        biblioteca inteira tinha aquilo."""
        assert len(icons.buscar("")) >= len(icons.ICONS)

    def test_e_o_limite_vale_para_todo_mundo(self):
        assert len(icons.buscar("a", limite=7)) == 7
