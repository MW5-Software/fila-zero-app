"""A moldura padrão dos relatórios (28/09/2026).

O cliente: "vamos padronizar os relatórios, começando com um foot, no canto
esquerdo a data que foi emitido, o usuário que emitiu, no centro a logo do
Kronos e no canto direito a paginação; no topo, logo do cliente, filtros à
mostra". Os dois relatórios — por mídia e gerais — saem com a mesma moldura.
"""

import pytest

from tests.test_fila_relatorios import _recorte, local, rede  # noqa: F401

pytestmark = pytest.mark.django_db

AGORA = (2026, 9, 15, 12)


def _os_dois(rede, **moldura):
    from fila import relatorio_midias
    from fila.relatorio import montar
    from fila.relatorio_saida import em_impressao

    agora = local(*AGORA)
    recorte = _recorte(rede, agora=agora)
    gerais = montar(recorte, rotulo_da_empresa="Sylvia Design", gerado_por="Sylvia", agora=agora)
    midias = relatorio_midias.montar(recorte, rotulo_da_empresa="Sylvia Design",
                                     gerado_por="Sylvia", agora=agora)
    return {"gerais": em_impressao(gerais, **moldura).content.decode(),
            "midias": relatorio_midias.em_impressao(midias, **moldura).content.decode()}


class TestORodape:
    def test_os_tres_cantos_em_toda_pagina(self, rede):
        """Na margem de cada folha, pelo próprio navegador: é o único jeito de
        numerar as páginas sem motor de PDF no servidor."""
        for nome, html in _os_dois(rede).items():
            assert "@bottom-left" in html, nome
            assert 'content: "Emitido em 15/09/2026 às 12:00 por Sylvia"' in html, nome
            assert "@bottom-center" in html and "data:image/svg+xml;base64," in html, nome
            assert 'content: "Página " counter(page) " de " counter(pages)' in html, nome

    def test_nome_de_quem_emitiu_nao_quebra_a_folha(self, rede):
        """O nome vai DENTRO de uma string de CSS: aspas e um "</style>" no
        nome fechariam a string e a folha, e o resto do nome viraria regra."""
        from fila.moldura import texto_de_css

        assert texto_de_css('Ana "A" \\ </style>') == '"Ana \\"A\\" \\\\ \\3C /style>"'

    def test_a_logo_do_kronos_esta_embutida(self):
        """Embutida, e não por endereço: na margem da folha o Chrome não
        buscou a imagem pelo endereço (medido na conferência), e embutida ela
        também não depende do cookie de quem imprime."""
        from fila.moldura import logo_do_kronos

        assert logo_do_kronos().startswith("data:image/svg+xml;base64,")


class TestOTopo:
    def test_logo_e_filtros_dentro_da_faixa_azul(self, rede):
        """ "Tudo isso tem que englobar a área azul, não ser algo de fora, o
        relatório é um só" (28/09/2026): a primeira versão pôs logo e filtros
        numa faixa branca POR CIMA da capa azul."""
        faixas = {"gerais": ('<header class="relatorio-capa">', "</header>"),
                  "midias": ('<div class="rm-topo">', '<div class="rm-moldura">')}
        for nome, html in _os_dois(rede, com_logo=True).items():
            abre, fecha = faixas[nome]
            faixa = html.split(abre)[1].split(fecha)[0]
            assert '<dl class="moldura-filtros">' in faixa, nome
            assert 'class="moldura-logo"' in faixa, nome
            assert "moldura-topo" not in html, nome

    def test_os_filtros_a_mostra(self, rede):
        for nome, html in _os_dois(rede).items():
            topo = html.split('<dl class="moldura-filtros">')[1].split("</dl>")[0]
            for rotulo in ("Período", "Empresa", "Lojas"):
                assert f"<dt>{rotulo}</dt>" in topo, (nome, rotulo)
            assert "Sylvia Design" in topo and "Matriz, Centro" in topo, nome

    def test_a_loja_escolhida_pelo_filtro(self, rede):
        html = _os_dois(rede, lojas="Todas as lojas")["midias"]
        assert "<dd>Todas as lojas</dd>" in html

    def test_logo_do_cliente_ou_o_nome(self, rede):
        com = _os_dois(rede, com_logo=True)
        sem = _os_dois(rede, com_logo=False)
        for nome in ("gerais", "midias"):
            assert 'class="moldura-logo" src="/marca/empresa/menu"' in com[nome], nome
            assert "/marca/empresa/menu" not in sem[nome], nome
            assert '<p class="moldura-empresa">Sylvia Design</p>' in sem[nome], nome
        # A logo saiu da capa azul do relatório geral: aparece uma vez só.
        assert com["gerais"].count("/marca/empresa/menu") == 1
