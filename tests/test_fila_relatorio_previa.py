"""A prévia dos relatórios na tela (05/10/2026).

O cliente: "em vez de aparecer gerar PDF, Excel, eu escolho o filtro e clico
em filtrar, o relatório aparece em HTML primeiro embaixo do filtro para o
cara ver, passar o mouse, ver os dados, daí se ele quiser vai ter os dois
botões gerar PDF e Excel em cima pra ele fazer isso".
"""

import pytest
from django.urls import reverse

from tests.fila_cenario import logado
from tests.test_fila_relatorio_midias import _midia
from tests.test_fila_relatorios import atendimento, local, rede  # noqa: F401

pytestmark = pytest.mark.django_db

TELAS = ("fila_relatorios_midias", "fila_relatorios_gerais")


def _get(cliente, rota, **params):
    return cliente.get(reverse(rota), params)


def _na_loja(cliente, loja):
    from plataforma.contexto import CHAVE

    sessao = cliente.session
    sessao[CHAVE] = loja.pk
    sessao.save()
    return cliente


class TestATela:
    def test_sem_filtrar_so_o_filtro(self, rede):
        for rota in TELAS:
            html = _get(logado("sylvia"), rota).content.decode()
            assert 'name="ver" value="1"' in html and ">Filtrar<" in html, rota
            assert "<iframe" not in html, rota
            assert "Gerar PDF" not in html and "Gerar Excel" not in html, rota

    def test_filtrado_mostra_o_relatorio_e_os_dois_botoes(self, rede):
        for rota in TELAS:
            endereco = reverse(rota)
            html = _get(logado("sylvia"), rota, ver="1", periodo="ontem").content.decode()
            assert f'<iframe class="relatorio-quadro" src="{endereco}?periodo=ontem&amp;formato=previa"' in html, rota
            pdf = html.index("Gerar PDF")
            assert pdf < html.index("<iframe"), "os botões vêm em cima do relatório"
            assert f'href="{endereco}?periodo=ontem&amp;formato=impressao"' in html, rota
            assert f'href="{endereco}?periodo=ontem&amp;formato=xlsx"' in html, rota
            assert 'target="_blank"' in html[pdf - 200:pdf], "o PDF abre noutra aba"

    def test_o_filtro_volta_marcado(self, rede):
        html = _get(logado("sylvia"), TELAS[0], ver="1", periodo="ontem").content.decode()
        assert '<option value="ontem" selected>' in html


class TestAPrevia:
    def test_a_previa_nao_imprime_e_pode_ficar_no_quadro(self, rede):
        for rota in TELAS:
            resposta = _get(logado("sylvia"), rota, formato="previa")
            html = resposta.content.decode()
            assert resposta.status_code == 200, rota
            assert "window.print" not in html, rota
            # O middleware nega toda página dentro de quadro (DENY); a prévia
            # é a única que a própria casa põe num quadro, e só na mesma origem.
            assert resposta["X-Frame-Options"] == "SAMEORIGIN", rota
        assert _get(logado("sylvia"), TELAS[0], formato="impressao")["X-Frame-Options"] == "DENY"

    def test_o_pdf_continua_imprimindo(self, rede):
        for rota in TELAS:
            html = _get(logado("sylvia"), rota, formato="impressao").content.decode()
            assert "window.print()" in html, rota

    def test_o_gerente_continua_so_com_a_loja_dele(self, rede):
        gil = _na_loja(logado("gil"), rede.centro)
        html = _get(gil, TELAS[0], formato="previa", loja=str(rede.matriz.pk)).content.decode()
        assert '<body class="papel relatorio-midias">' in html, "é a página do relatório"
        assert "Centro" in html and "Matriz" not in html

    def test_quem_nao_tira_relatorio_nao_ve_a_previa(self, rede):
        assert _get(logado("ana"), TELAS[0], formato="previa").status_code == 404


class TestOMouse:
    def test_cada_numero_de_midia_se_explica(self, rede):
        """Passar o mouse no número diz o que ele é."""
        instagram = _midia(rede, "Instagram")
        dia = local(2026, 9, 10, 10)
        atendimento(rede, rede.ana, rede.matriz, dia, valor="10", midia=instagram)
        atendimento(rede, rede.ana, rede.matriz, dia)
        from fila import relatorio_midias
        from tests.test_fila_relatorio_midias import _montar

        html = relatorio_midias.em_impressao(_montar(rede)).content.decode()
        assert 'title="Instagram em Matriz: 1 de 2 atendimentos (50,0%)"' in html
        assert 'title="Matriz: 1 venda de 2 atendimentos"' in html
