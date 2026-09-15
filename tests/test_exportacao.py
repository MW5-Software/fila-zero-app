"""A exportação de listagens — Bloco 4 do roadmap (item 25).

O contrato é um só: o que está na tela é o que sai no arquivo. O filtro e
a ordenação da URL (`f:*`, `ordenar`) são aplicados EXATAMENTE pelos mesmos
caminhos da listagem (`comum.listagem.preparar_consulta`), então não
existe uma segunda implementação de filtro para divergir entre tela e
planilha.

Dois formatos, decisões diferentes:

- **xlsx de verdade** (`openpyxl`): é o que o roadmap pede, e CSV aberto no
  Excel brasileiro tropeça em acento e separador — planilha certa ou nada.
- **PDF pela impressão**: a rota devolve uma página limpa de papel (sem
  shell, sem menu) que chama `window.print()`; o navegador gera o PDF. Uma
  engine de PDF na imagem seria peso nas vinte instalações para refazer
  pior o que o navegador já faz melhor (margens, cabeçalho de página).
"""

from io import BytesIO

import openpyxl
import pytest


@pytest.fixture(autouse=True)
def _com_filiais(modulo_filiais_ligado):
    """Este arquivo testa a tela de filiais, e neste produto o módulo nasce
    desligado — ver `tests/conftest.py`."""
from django.test import RequestFactory

from contas.models import Cargo, RegistroDeAuditoria
from comum.exportacao import (
    FORMATOS, ColunaDeExportacao, em_impressao, em_xlsx, preparar_exportacao,
)
from comum.listagem import ColunaFiltravel

SENHA = "segredo-de-teste"

COLUNAS = (
    ColunaDeExportacao("rotulo", "Rótulo", lambda p: p.rotulo),
    ColunaDeExportacao("nome", "Nome interno", lambda p: p.nome),
)


def _get(**params):
    return RequestFactory().get("/perfis", params)


def _conta():
    """Uma conta para os cargos. Qualquer tabela serviria para testar a
    exportação; `Cargo` tem rótulo e nome, que é o que as colunas leem. Era
    `Perfil`, que saiu em 14/09/2026."""
    from contas.models import Nivel, Usuario

    conta, _ = Usuario.objects.get_or_create(
        email="conta-exportacao@teste.com", defaults={"nivel": Nivel.TITULAR})
    return conta


@pytest.fixture
def perfis(db):
    return [
        Cargo.objects.create(conta=_conta(), nome=f"perfil-{n}", rotulo=rotulo)
        for n, rotulo in enumerate(("Zeca", "Ana"))
    ]


class TestEmXlsx:
    def test_a_primeira_linha_sao_os_rotulos(self, perfis):
        resposta = em_xlsx(COLUNAS, perfis, titulo="Perfis")
        planilha = openpyxl.load_workbook(BytesIO(resposta.content))
        celulas = [c.value for c in planilha.active[1]]
        assert celulas == ["Rótulo", "Nome interno"]

    def test_uma_linha_por_registro_com_o_valor_da_funcao(self, perfis):
        resposta = em_xlsx(COLUNAS, perfis, titulo="Perfis")
        planilha = openpyxl.load_workbook(BytesIO(resposta.content))
        linhas = list(planilha.active.iter_rows(min_row=2, values_only=True))
        assert linhas == [("Zeca", "perfil-0"), ("Ana", "perfil-1")]

    def test_o_content_type_e_o_nome_do_arquivo(self, perfis):
        resposta = em_xlsx(COLUNAS, perfis, titulo="Perfis")
        assert resposta["Content-Type"] == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert 'filename="perfis.xlsx"' in resposta["Content-Disposition"]

    def test_lista_vazia_sai_com_os_cabecalhos(self, perfis):
        """Exportar um filtro sem resultado não é erro: sai a planilha com
        o cabeçalho, para quem recebeu saber o que ELA teria."""
        resposta = em_xlsx(COLUNAS, [], titulo="Perfis")
        planilha = openpyxl.load_workbook(BytesIO(resposta.content))
        assert planilha.active.max_row == 1


class TestEmImpressao:
    def test_traz_o_titulo_a_tabela_e_as_linhas(self, perfis):
        resposta = em_impressao(COLUNAS, perfis, titulo="Perfis",
                                subtitulo="filtro: rótulo contém Z")
        html = resposta.content.decode()
        assert "<table" in html
        assert "Rótulo" in html
        assert "Zeca" in html
        assert "Ana" in html

    def test_traz_quando_foi_emitido_e_quantos_vieram(self, perfis):
        html = em_impressao(COLUNAS, perfis, titulo="Perfis").content.decode()
        assert "2026" in html          # o ano corrente, no carimbo
        assert "2 registros" in html   # a contagem, para o papel contar sozinho

    def test_nao_traz_shell_nem_menu(self, perfis):
        """Página de papel: sem sidebar, sem cabeçalho do sistema, sem
        navegação — é isso que a distingue de printar a tela comum."""
        html = em_impressao(COLUNAS, perfis, titulo="Perfis").content.decode()
        assert 'class="sidebar"' not in html
        assert "window.print()" in html

    def test_valor_none_e_vazio_nao_quebram_a_celula(self, perfis):
        colunas = (ColunaDeExportacao("x", "X", lambda p: None),)
        resposta = em_impressao(colunas, perfis[:1], titulo="T")
        assert "<td>—" in resposta.content.decode() or "<td></td>" in \
            resposta.content.decode()


class TestPrepararExportacao:
    """`preparar_exportacao` é a porta única da view: lê `?formato=` da
    MESMA URL da tela e devolve a resposta pronta — ou `None`, e aí a view
    desenha a tela normal como sempre."""

    ORDENAVEIS = {"perfil": "rotulo"}
    FILTRAVEIS = {
        "rotulo": ColunaFiltravel("rotulo", "Rótulo"),
    }

    def _responder(self, request, linhas):
        return preparar_exportacao(
            request, queryset=Cargo.objects.all(), colunas=COLUNAS,
            ordenaveis=self.ORDENAVEIS, padrao="perfil",
            filtraveis=self.FILTRAVEIS, titulo="Perfis")

    def test_sem_formato_e_nada(self, db):
        assert self._responder(_get(), None) is None

    def test_formato_desconhecido_e_a_tela_normal(self, db):
        """`formato=pdf` digitado à mão não pode derrubar nem baixar lixo:
        entrada ruim vira a tela normal, mesma postura de `?ordenar=` ruim."""
        assert self._responder(_get(formato="pdf"), None) is None

    def test_xlsx_leva_o_filtro_e_a_ordem_da_url(self, perfis):
        # Os cinco cargos DE FÁBRICA da conta também estão no banco — o filtro
        # tem que ser fino o bastante para provar que só o que bate na URL
        # entra na planilha.
        Cargo.objects.create(conta=_conta(), nome="perfil-dois", rotulo="Filtro Dois")
        Cargo.objects.create(conta=_conta(), nome="perfil-um", rotulo="Filtro Um")
        resposta = self._responder(
            _get(formato="xlsx",
                 **{"f:rotulo:contem": "filtro", "ordenar": "-perfil"}), None)
        planilha = openpyxl.load_workbook(BytesIO(resposta.content))
        valores = [linha[0] for linha in
                   planilha.active.iter_rows(min_row=2, values_only=True)]
        assert valores == ["Filtro Um", "Filtro Dois"]

    def test_impressao_responde_html_de_papel(self, perfis):
        resposta = self._responder(_get(formato="impressao"), None)
        assert resposta["Content-Type"].startswith("text/html")
        assert "<table" in resposta.content.decode()

    def test_os_formatos_conhecidos_estam_no_vocabulario(self, db):
        """O conjunto fechado de formatos — é o que impede um `elif` solto
        numa view futura de inventar um quarto formato fora do padrão."""
        assert FORMATOS == frozenset({"xlsx", "impressao"})


class TestNaTelaDaAuditoria:
    """A prova integrada: a rota da tela, com os guardas dela, exportando."""

    @pytest.fixture
    def raiz_logado(self, db):
        from contas.models import Usuario
        from django.test import Client
        from django.urls import reverse

        Usuario.objects.create_superuser(
            email="raiz@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
        return c

    def _duas_acoes(self):
        from comum.auditoria import registrar

        registrar("usuario_criado", None, alvo="zeca")
        registrar("entrada_recusada", None, alvo="ana@teste.com")

    def test_xlsx_na_rota_da_tela_leva_o_filtro(self, raiz_logado):
        from django.urls import reverse

        self._duas_acoes()
        resposta = raiz_logado.get(
            reverse("auditoria"),
            {"formato": "xlsx", "f:alvo:contem": "zec"})
        planilha = openpyxl.load_workbook(BytesIO(resposta.content))
        alvos = [linha[3] for linha in
                 planilha.active.iter_rows(min_row=2, values_only=True)]
        assert alvos == ["zeca"]

    def test_impressao_na_rota_da_tela(self, raiz_logado):
        from django.urls import reverse

        self._duas_acoes()
        resposta = raiz_logado.get(reverse("auditoria"), {"formato": "impressao"})
        html = resposta.content.decode()
        assert "<table" in html and "Auditoria" in html

    def test_formato_invalido_desenha_a_tela_normal(self, raiz_logado):
        from django.urls import reverse

        resposta = raiz_logado.get(reverse("auditoria"), {"formato": "pdf"})
        assert resposta["Content-Type"].startswith("text/html")
        assert 'name="f:' in resposta.content.decode()

    def test_quem_nao_pode_ver_nem_exporta(self, db):
        from contas.models import Usuario
        from django.test import Client
        from django.urls import reverse

        Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        assert c.get(reverse("auditoria"), {"formato": "xlsx"}).status_code == 404


class TestOsBotoesNaTela:
    """O gatilho: Excel e Imprimir no cabeçalho da tela, levando a
    querystring do momento — o filtro que está valendo é o que viaja."""

    @pytest.fixture
    def raiz_logado(self, db):
        from contas.models import Usuario
        from django.test import Client
        from django.urls import reverse

        Usuario.objects.create_superuser(
            email="raiz@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
        return c

    def test_a_tela_da_auditoria_oferece_os_dois(self, raiz_logado):
        from django.urls import reverse

        html = raiz_logado.get(reverse("auditoria")).content.decode()
        assert "formato=xlsx" in html
        assert "formato=impressao" in html
        assert ">Exportar Excel</a>" in html and ">Imprimir</a>" in html

    def test_o_link_leva_o_filtro_ja_aplicado(self, raiz_logado):
        """Filtro na URL, tela redesenhada: os links de exportar preservam
        os parâmetros — é isso que faz "o arquivo sair igual à tela"."""
        from urllib.parse import quote

        from django.urls import reverse

        html = raiz_logado.get(
            reverse("auditoria"),
            {"f:alvo:contem": "zec"}).content.decode()
        esperado = quote("zec")
        assert f"f%3Aalvo%3Acontem={esperado}" in html \
            or f"f:alvo:contem={esperado}" in html

    @pytest.mark.parametrize("rota", ["filiais", "cargos", "usuarios"])
    def test_as_outras_listagens_tambem_oferecem(self, raiz_logado, rota):
        """Mesma oferta nas quatro listagens — infraestrutura do Bloco 4,
        e não privilégio da tela nova."""
        from django.urls import reverse

        html = raiz_logado.get(reverse(rota)).content.decode()
        assert "formato=xlsx" in html, rota
