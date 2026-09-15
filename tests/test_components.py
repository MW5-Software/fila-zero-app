"""Cada componente renderiza o que promete — e recusa o que não sabe fazer.

Removidos no porte: `TestTransicaoDoAcordeao.test_o_painel_do_gerador_tambem_poe_o_espacamento_na_camada_certa`
e `TestFaixaDaLogoNaBarra.test_a_faixa_nao_aparece_na_configuracao_de_cores`
testavam o painel do `mw5_generator` (o construtor de sites, um projeto por
cliente). O KRONOS.net é uma matriz única — não há geração por cliente —,
então esse código nunca vai existir aqui. Decisão de arquitetura registrada
nas Global Constraints do plano (commit `375bbcd`).

Os imports `from mw5_admin.auth import ...` viraram `from nucleo.permissoes
import ...`, e não `from nucleo.auth import ...`: de `mw5_admin/auth/` (7
arquivos), esta entrega porta só `models.py`, que vira `nucleo/permissoes.py`
(Task 7). Os outros seis (`backend.py`, `banco.py`, `kronos.py`, `session.py`,
`passwords.py`, `guards.py`) são entrega 2 — `nucleo.auth` nunca existe sob
esse nome. `site.py` e `layout.py` fazem o mesmo ajuste na Task 8.
"""

import pytest

from nucleo import icons
from nucleo.components import (
    Alert,
    Avatar,
    Button,
    Card,
    Column,
    EmptyState,
    IconButton,
    Modal,
    Pagination,
    Pill,
    Protected,
    Select,
    Option,
    Table,
    TextInput,
    Timeline,
    TimelineEvent,
)
from nucleo.components.containers import (
    ALINHAMENTOS, Box, Cell, DIRECOES, ESPACAMENTOS, TRANSVERSAIS,
)
from nucleo.rendering import create_environment, html_attrs, render_all, use_environment


@pytest.fixture(autouse=True)
def env():
    environment = create_environment()
    with use_environment(environment):
        yield environment


def html(component) -> str:
    return str(component.render())


class TestBotao:
    def test_com_href_vira_link(self):
        assert "<a " in html(Button(label="Ver", href="/x"))

    def test_sem_href_vira_botao(self):
        assert "<button" in html(Button(label="Salvar"))

    def test_variante_aplica_a_classe(self):
        assert 'class="btn primary"' in html(Button(label="Salvar", variant="primary"))

    def test_variante_desconhecida_falha_na_construcao(self):
        with pytest.raises(ValueError, match="variant"):
            Button(label="X", variant="ciano")

    def test_botao_invisivel_e_rejeitado(self):
        with pytest.raises(ValueError, match="label"):
            Button()

    def test_botao_so_de_icone_exige_rotulo_acessivel(self):
        with pytest.raises(ValueError, match="leitor de tela"):
            Button(icon="plus")
        assert "title" in html(Button(icon="plus", title="Adicionar"))

    def test_atributos_extras_passam_adiante(self):
        assert 'hx-get="/x"' in html(Button(label="Ir", attrs={"hx-get": "/x"}))


class TestPill:
    def test_estatica_e_span(self):
        assert html(Pill(label="Ativo")).strip().startswith("<span")

    def test_interativa_e_button(self):
        assert html(Pill(label="Ativo", interactive=True)).strip().startswith("<button")

    def test_tom_invalido_falha(self):
        with pytest.raises(ValueError, match="tone"):
            Pill(label="X", tone="roxo")


class TestAvatar:
    @pytest.mark.parametrize(
        "nome,esperado",
        [("Ana Paula Souza", "AS"), ("Tatiane", "T"), ("  ", "?"), ("a b", "AB")],
    )
    def test_iniciais(self, nome, esperado):
        assert Avatar(name=nome).initials == esperado

    def test_imagem_substitui_as_iniciais(self):
        saida = html(Avatar(name="Ana", image="/a.png"))
        assert "<img" in saida and ">A<" not in saida


class TestCampos:
    def test_span_vira_classe_da_grade(self):
        assert 'class="f c8"' in html(TextInput(name="n", label="Nome", span=8))

    def test_span_fora_da_grade_e_rejeitado(self):
        with pytest.raises(ValueError, match="span"):
            TextInput(name="n", span=13)

    def test_obrigatorio_marca_visual_e_semanticamente(self):
        saida = html(TextInput(name="n", label="Nome", required=True))
        assert 'class="req"' in saida and " required" in saida

    def test_erro_marca_o_campo_e_liga_a_mensagem(self):
        saida = html(TextInput(name="cpf", label="CPF", error="CPF inválido"))
        assert "invalid" in saida
        assert 'aria-invalid="true"' in saida
        assert 'aria-describedby="cpf-error"' in saida
        assert "CPF inválido" in saida

    def test_select_marca_a_opcao_atual(self):
        saida = html(Select(name="uf", options=[Option("SP", "SP"), Option("MG", "MG")], value="MG"))
        assert '<option value="MG" selected>' in saida

    def test_select_aceita_tuplas(self):
        saida = html(Select(name="uf", options=[("SP", "São Paulo")]))
        assert "São Paulo" in saida

    def test_valor_do_usuario_nao_vira_html(self):
        saida = html(TextInput(name="n", value='"><script>alert(1)</script>'))
        assert "<script>" not in saida


class TestTabela:
    COLUNAS = [Column("nome", "Nome"), Column("idade", "Idade", align="num")]

    def test_le_dicionarios_e_objetos(self):
        from types import SimpleNamespace

        saida = html(Table(columns=self.COLUNAS, rows=[{"nome": "Ana", "idade": 30}]))
        assert "Ana" in saida
        saida = html(Table(columns=self.COLUNAS, rows=[SimpleNamespace(nome="Bia", idade=4)]))
        assert "Bia" in saida

    def test_coluna_com_render_proprio(self):
        coluna = Column("x", "X", render=lambda r: Pill(label=r["x"], tone="ok"))
        assert "pill ok" in html(Table(columns=[coluna], rows=[{"x": "Pago"}]))

    def test_vazia_mostra_estado_vazio_e_nao_cabecalho(self):
        saida = html(Table(columns=self.COLUNAS, rows=[]))
        assert "<thead" not in saida
        assert "Nenhum registro" in saida

    def test_tabela_sem_coluna_e_erro(self):
        with pytest.raises(ValueError, match="coluna"):
            Table(rows=[])

    def test_conteudo_de_celula_e_escapado(self):
        saida = html(Table(columns=[Column("n", "N")], rows=[{"n": "<b>x</b>"}]))
        assert "<b>x</b>" not in saida


class TestPaginacao:
    def test_intervalo_exibido(self):
        p = Pagination(page=2, per_page=10, total=95)
        assert (p.first_item, p.last_item, p.pages) == (11, 20, 10)

    def test_sem_registros(self):
        p = Pagination(page=1, per_page=10, total=0)
        assert (p.first_item, p.last_item, p.pages) == (0, 0, 1)

    def test_poucas_paginas_aparecem_todas(self):
        assert Pagination(page=1, per_page=10, total=50).numbers() == [1, 2, 3, 4, 5]

    def test_muitas_paginas_colapsam_no_meio(self):
        numeros = Pagination(page=10, per_page=10, total=300).numbers()
        assert numeros[0] == 1 and numeros[-1] == 30
        assert None in numeros
        assert 10 in numeros

    def test_pagina_zero_e_rejeitada(self):
        with pytest.raises(ValueError):
            Pagination(page=0, per_page=10, total=10)


class TestProtected:
    def test_esconde_quando_nao_permitido(self):
        assert html(Protected(allowed=False, children=Button(label="Excluir"))) == ""

    def test_mostra_quando_permitido(self):
        assert "Excluir" in html(Protected(allowed=True, children=Button(label="Excluir")))

    def test_usa_o_alternativo(self):
        assert "sem acesso" in html(Protected(allowed=False, fallback="sem acesso"))


class TestComposicao:
    def test_card_renderiza_filhos_componentes(self):
        saida = html(Card(title="T", icon="user", body=[Button(label="A"), Button(label="B")]))
        assert "A" in saida and "B" in saida and "<h2>T</h2>" in saida

    def test_texto_solto_dentro_de_componente_e_escapado(self):
        assert "<script>" not in html(Card(body="<script>alert(1)</script>"))

    def test_timeline_marca_os_estados(self):
        saida = html(Timeline(events=[
            TimelineEvent(label="Criado", when="hoje"),
            TimelineEvent(label="Pendente", state="pending"),
        ]))
        assert 'class="ev done"' in saida and 'class="ev pending"' in saida

    def test_modal_nasce_fechado(self):
        assert "open" not in html(Modal(id="m", title="T")).split("\n")[0]

    def test_alerta_escolhe_o_icone_pelo_tom(self):
        assert Alert(message="x", tone="danger").icon == "x-circle"
        assert Alert(message="x", tone="ok").icon == "check-circle"


class TestIcones:
    def test_nome_inexistente_falha_com_lista_de_opcoes(self):
        with pytest.raises(KeyError, match="não existe"):
            icons.get("dinossauro")

    def test_icone_decorativo_e_escondido_de_leitores(self):
        assert 'aria-hidden="true"' in html(IconButton(icon="plus", title="Novo"))

    def test_todos_os_icones_renderizam(self):
        from nucleo.components import Icon

        for nome in icons.names():
            assert "<svg" in html(Icon(name=nome))


class TestAtributos:
    def test_underscore_vira_hifen(self):
        assert html_attrs({"hx_get": "/x"}) == ' hx-get="/x"'

    def test_booleano_verdadeiro_vira_atributo_sozinho(self):
        assert html_attrs({"disabled": True}) == " disabled"

    def test_nulo_e_falso_somem(self):
        assert html_attrs({"a": None, "b": False}) == ""

    def test_valor_e_escapado(self):
        assert '"' not in html_attrs({"data-x": '"><script>'}).split("=")[1][1:-1]

    def test_vazio_nao_gera_espaco(self):
        assert html_attrs({}) == "" and html_attrs(None) == ""


class TestRenderAll:
    def test_lista_aninhada(self):
        assert render_all([["a"], ["b"]]) == "ab"

    def test_none_e_false_viram_vazio(self):
        assert render_all(None) == "" and render_all(False) == ""

    def test_string_e_escapada(self):
        assert render_all("<b>") == "&lt;b&gt;"


class TestEstados:
    def test_estado_vazio_com_acao(self):
        saida = html(EmptyState(title="Nada aqui", actions=Button(label="Criar")))
        assert "Nada aqui" in saida and "Criar" in saida


class TestCampoDeArquivo:
    """O input de arquivo nativo não aceita o estilo dos outros campos — o
    componente existe para isso, e não pode custar acessibilidade."""

    def test_o_input_real_continua_no_html(self):
        from nucleo.components import FileInput

        saida = html(FileInput(name="logo", label="Logo"))
        assert 'type="file"' in saida
        assert 'name="logo"' in saida

    def test_o_rotulo_aponta_para_o_input(self):
        """É o `for` que faz o gatilho abrir o seletor e o teclado alcançá-lo."""
        from nucleo.components import FileInput

        saida = html(FileInput(name="logo", label="Logo"))
        assert 'for="logo"' in saida
        assert 'id="logo"' in saida

    def test_nao_e_escondido_com_display_none(self):
        """`display:none` tiraria o campo do teclado e do `required`."""
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )
        regra = css.split(".filefield-input {")[1].split("}")[0]
        assert "display: none" not in regra
        assert "clip:" in regra

    def test_accept_e_repassado(self):
        from nucleo.components import FileInput

        saida = html(FileInput(name="logo", label="Logo", accept="image/png"))
        assert 'accept="image/png"' in saida

    def test_textos_sao_configuraveis(self):
        from nucleo.components import FileInput

        saida = html(FileInput(name="x", label="X", button_label="Procurar",
                               empty_label="Nada ainda"))
        assert "Procurar" in saida and "Nada ainda" in saida

    def test_erro_e_ajuda_funcionam_como_nos_outros_campos(self):
        from nucleo.components import FileInput

        saida = html(FileInput(name="logo", label="Logo", error="Formato inválido"))
        assert "invalid" in saida
        assert 'aria-describedby="logo-error"' in saida


class TestAcordeaoExclusivo:
    """Com grupo, abrir uma seção fecha as outras — inclusive de listas vizinhas."""

    def test_sem_grupo_nao_marca_nada(self):
        from nucleo.components import Accordion, AccordionItem

        saida = html(Accordion(items=[AccordionItem(title="A")]))
        assert "data-accordion-group" not in saida

    def test_com_grupo_marca_a_lista(self):
        from nucleo.components import Accordion, AccordionItem

        saida = html(Accordion(group="ajustes", items=[AccordionItem(title="A")]))
        assert 'data-accordion-group="ajustes"' in saida

    def test_o_js_fecha_as_irmas_pelo_grupo(self):
        """A exclusividade tem que atravessar acordeões vizinhos: no editor cada
        área é uma lista própria, mas todas se comportam como uma só."""
        from pathlib import Path

        import nucleo

        js = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.js").read_text(
            encoding="utf-8"
        )
        assert "fecharIrmas" in js
        assert 'data-accordion-group="' in js  # busca no documento, não no pai


class TestTransicaoDoAcordeao:
    """A abertura é animada, e `display` não anima."""

    def _css(self) -> str:
        from pathlib import Path

        import nucleo

        return (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )

    def test_o_painel_anima_a_altura_e_nao_alterna_display(self):
        regra = self._css().split(".accordion .panel {")[1].split("}")[0]
        assert "grid-template-rows: 0fr" in regra
        assert "transition:" in regra
        assert "display: none" not in regra

    def test_a_secao_fechada_recorta_na_grade_tambem(self):
        """Dois recortes: um no filho, outro na grade. Só o do filho depende de
        `min-height: 0`, e conteúdo que entre sem essa propriedade vazaria a
        primeira linha para fora da seção fechada."""
        regra = self._css().split(".accordion .panel {")[1].split("}")[0]
        assert "overflow: hidden" in regra

    def test_o_conteudo_tem_invólucro_que_pode_encolher(self):
        """Sem `min-height: 0` o filho recusa encolher abaixo do conteúdo e a
        animação não sai do lugar."""
        regra = self._css().split(".accordion .panel-conteudo {")[1].split("}")[0]
        assert "overflow: hidden" in regra
        assert "min-height: 0" in regra

    def test_o_elemento_que_colapsa_nao_tem_espacamento(self):
        """`min-height: 0` zera a altura do conteúdo, mas padding continua
        contando: sobrava uma faixa mostrando a primeira linha do formulário
        através da seção fechada. O espaçamento vive na camada de dentro."""
        regra = self._css().split(".accordion .panel-conteudo {")[1].split("}")[0]
        assert "padding" not in regra
        interno = self._css().split(".accordion .panel-interno {")[1].split("}")[0]
        assert "padding:" in interno

    def test_o_submenu_da_barra_lateral_anima_igual(self):
        regra = self._css().split(".side .submenu {")[1].split("}")[0]
        assert "grid-template-rows: 0fr" in regra
        assert "display: none" not in regra

    def test_quem_pediu_menos_movimento_e_atendido(self):
        css = self._css()
        assert "prefers-reduced-motion" in css
        bloco = css.split("prefers-reduced-motion")[1].split("}")[1]
        assert "transition-duration: .01ms" in css.split("prefers-reduced-motion")[1]

    def test_o_item_renderiza_as_tres_camadas(self):
        from nucleo.components import Accordion, AccordionItem

        saida = html(Accordion(items=[AccordionItem(title="A", body="conteúdo")]))
        assert 'class="panel"' in saida
        assert 'class="panel-conteudo"' in saida
        assert 'class="panel-interno"' in saida


class TestResponsividade:
    """Em tela estreita a barra lateral vira gaveta. Antes ela simplesmente
    sumia, e o sistema virava uma tela só — sem forma alguma de trocar de
    módulo."""

    def _css(self) -> str:
        from pathlib import Path

        import nucleo

        return (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )

    def test_a_barra_lateral_nao_some_mais(self):
        estreito = self._css().split("@media (max-width: 820px) {")[1].split("\n}")[0]
        assert ".side { display: none" not in estreito
        assert "translateX(-100%)" in estreito, "a barra deveria virar gaveta"

    def test_o_botao_de_menu_so_existe_em_tela_estreita(self):
        css = self._css()
        assert ".iconbtn.menu-btn { display: none" in css
        estreito = css.split("@media (max-width: 820px) {")[1].split("\n}")[0]
        assert ".iconbtn.menu-btn { display: grid" in estreito

    def test_o_botao_qualifica_a_classe_para_vencer_o_iconbtn(self):
        """`.menu-btn` sozinho tem o mesmo peso de `.iconbtn`, que vem depois no
        arquivo e ganhava — o botão aparecia no desktop."""
        css = self._css()
        assert ".menu-btn { display" not in css.replace(".iconbtn.menu-btn { display", "")

    def test_o_caminho_encolhe_antes_de_empurrar_as_acoes(self):
        """O grupo de ações do cabeçalho estourava 46px em 390px de largura."""
        crumb = self._css().split(".crumb {")[1].split("}")[0]
        assert "min-width: 0" in crumb
        acoes = self._css().split(".h-actions {")[1].split("}")[0]
        assert "flex: none" in acoes

    def test_o_header_traz_o_botao_de_menu(self):
        from nucleo.layout import Breadcrumb, Crumb, Header

        saida = html(Header(breadcrumb=Breadcrumb(crumbs=[Crumb(label="X")])))
        assert "data-menu-toggle" in saida
        assert 'aria-expanded="false"' in saida

    def test_a_gaveta_fecha_de_tres_formas(self):
        from pathlib import Path

        import nucleo

        js = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.js").read_text(
            encoding="utf-8"
        )
        assert "data-menu-fechar" in js          # fundo escuro
        assert 'key === "Escape"' in js          # teclado
        assert '.side a[href]' in js             # escolher um módulo


class TestFaixaDaLogoNaBarra:
    """A logo e o menu são duas regiões, não uma lista com a marca no topo."""

    def _css(self) -> str:
        from pathlib import Path

        import nucleo

        return (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )

    def _html(self) -> str:
        from nucleo.layout import NavItem, Sidebar
        from nucleo.rendering import render_all

        return render_all(
            Sidebar(
                logo="/static/brand/logo-sidebar.svg",
                logo_alt="Cliente",
                items=[NavItem(label="Início", href="/", icon="home")],
            )
        )

    def test_o_menu_fica_fora_da_faixa_da_logo(self):
        html = self._html()
        faixa = html.split('class="side-brand"')[1].split("</div>")[0]
        assert "side-logo" in faixa
        assert "Início" not in faixa, "o menu está dentro da faixa da logo"
        assert 'class="side-nav"' in html

    def test_so_o_menu_rola(self):
        """A marca some ao rolar quando o `overflow` está na barra inteira."""
        css = self._css()
        barra = css.split(".side {")[1].split("}")[0]
        assert "overflow: hidden" in barra
        menu = css.split(".side-nav {")[1].split("}")[0]
        assert "overflow-y: auto" in menu

    def test_a_faixa_tem_altura_fixa(self):
        """Altura fixa é o que faz o menu começar sempre na mesma linha, com
        logo alto, baixo ou nenhum."""
        faixa = self._css().split(".side-brand {")[1].split("}")[0]
        assert "height: var(--sidebar-brand-h)" in faixa

    def test_o_fundo_da_faixa_e_sempre_branco(self):
        from nucleo import Brand
        from nucleo.theme.brand import AreaColors
        from nucleo.theme.tokens import build

        marca = Brand(
            client_name="X",
            primary="#146c43",
            areas=AreaColors(sidebar_bg="#101014", sidebar_text="#ffffff"),
        )
        for modo in ("light", "dark"):
            tokens = build(marca, modo)
            assert tokens["sidebar-bg"] == "#101014"
            assert tokens["sidebar-brand-bg"] == "#ffffff", (
                f"a faixa da logo mudou de cor no modo {modo}"
            )

    def test_a_faixa_tem_respiro_alem_da_caixa_do_logo(self):
        """A altura é uma conta, não um número solto: mexer no tamanho do logo
        não pode comer a folga de cima e de baixo."""
        from nucleo import Brand

        for altura, esperado in (("56px", "104px"), ("80px", "128px")):
            tokens = Brand(
                client_name="X", logo_areas={"logo-side-h": altura}
            ).tokens("light")
            faixa = tokens["sidebar-brand-h"]
            assert altura in faixa and tokens["sidebar-brand-pad"] in faixa, faixa
            assert _resolver_calc(faixa) == esperado

    def test_o_logo_ocupa_a_faixa_inteira_para_ficar_no_centro(self):
        """Encolhendo até a imagem, o link centralizava o que sobrou — não a
        faixa. Ocupando tudo, o centro do logo é o centro da faixa."""
        link = self._css().split(".side-brand > a {")[1].split("}")[0]
        assert "width: 100%" in link and "height: 100%" in link
        assert "place-items: center" in link

    def test_o_logo_nao_acende_como_item_de_menu(self):
        """Ele também é um link, e as regras do menu estavam escritas na barra
        inteira (`.side a`): passar o mouse no logo pintava fundo colorido
        atrás dele, como se a marca fosse mais um módulo da lista.

        Escritas em `.side-nav`, elas param na faixa da marca — a outra região
        da barra, que não tem estado de passagem nenhum."""
        import re

        alvos = []
        for bloco in re.sub(r"/\*.*?\*/", "", self._css(), flags=re.S).split("}"):
            if "{" not in bloco:
                continue
            # `split("{")[-1]` descarta a abertura de um `@media`, que fica
            # colada no primeiro seletor de dentro dele.
            cabeca = bloco.rsplit("{", 1)[0]
            alvos += [s.split("{")[-1].strip() for s in cabeca.split(",")]

        assert ".side-nav a:hover" in alvos, "as regras do menu sumiram"
        for alvo in alvos:
            assert not re.match(r"\.side(-collapsed \.side)? a\b", alvo), (
                f"`{alvo}` alcança o link do logo junto com o menu")


def _resolver_calc(valor: str) -> str:
    """Resolve `calc(56px + 24px * 2)` — só o suficiente para o teste acima."""
    import re

    numeros = [int(n) for n in re.findall(r"(\d+)px", valor)]
    return f"{numeros[0] + numeros[1] * 2}px"


class TestEstadosDoMenu:
    """Hover, item ativo e divisórias se medem a partir da cor do próprio menu.

    Fixos nos cinzas do tema, eles viravam um lampejo claro no meio de um menu
    escuro — e o menu agora nasce escuro."""

    def _regra(self, seletor: str) -> str:
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )
        return css.split(seletor)[1].split("}")[0]

    def test_o_hover_usa_as_cores_do_menu_e_nao_as_do_tema(self):
        """A derivação saiu do CSS e virou token calculado, para poder ser
        escolhida. O que não pode mudar é isto: o hover é do menu, e cores
        genéricas do tema ali dentro brigam com um menu de cor própria."""
        regra = self._regra(
            ".side-nav a:hover, .side-nav .submenu-toggle:hover, .side-toggle:hover {")
        assert "var(--sidebar-hover-bg)" in regra
        assert "var(--sidebar-hover-text)" in regra
        assert "--surface-2" not in regra and "--on-surface)" not in regra

    def test_a_divisoria_do_submenu_sai_da_cor_do_texto_do_menu(self):
        assert "var(--sidebar-text)" in self._regra(".side .submenu > * {")

    def test_o_topo_tem_a_altura_da_faixa(self):
        """Com alturas separadas, a linha sob o logo e a linha sob o cabeçalho
        quase sempre desencontravam. Agora são a mesma linha."""
        from nucleo import Brand

        for altura in ("56px", "72px"):
            tokens = Brand(
                client_name="X", logo_areas={"logo-side-h": altura}
            ).tokens("light")
            assert tokens["header-h"] == tokens["sidebar-brand-h"]
            assert altura in tokens["header-h"]


class TestMenuPorNiveis:
    """O menu não tem rótulo de seção: quem agrupa é o item que abre."""

    def _html(self, itens) -> str:
        from nucleo.layout import Sidebar
        from nucleo.rendering import render_all

        return render_all(Sidebar(items=itens, logo="/x.svg", logo_alt="X"))

    def test_item_de_primeiro_nivel_leva_direto(self):
        from nucleo.layout import NavItem

        html = self._html([NavItem(label="Início", icon="home", href="/")])
        assert '<a href="/"' in html
        assert "submenu-toggle" not in html

    def test_item_com_filhos_abre_em_vez_de_navegar(self):
        from nucleo.layout import NavItem

        html = self._html([
            NavItem(label="Administração", icon="shield", children=[
                NavItem(label="Usuários", icon="users", href="/usuarios"),
                NavItem(label="Configurações", icon="settings", href="/config"),
            ])
        ])
        assert "submenu-toggle" in html
        assert 'href="/usuarios"' in html and 'href="/config"' in html
        # O pai é botão, não link: ele não tem para onde levar.
        assert '<a href="#"' not in html

    def test_nao_existe_mais_rotulo_de_secao(self):
        from pathlib import Path

        import nucleo

        template = (
            Path(nucleo.__file__).parent / "templates" / "layout" / "sidebar.html"
        ).read_text(encoding="utf-8")
        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )
        assert 'class="grp"' not in template
        assert ".side .grp" not in css

    def test_o_pai_abre_quando_um_filho_esta_na_tela(self):
        from nucleo import Brand
        from nucleo.layout import NavItem
        from nucleo.site import Site

        site = Site(brand=Brand(client_name="X"), nav=[
            NavItem(label="Administração", icon="shield", children=[
                NavItem(label="Usuários", icon="users", href="/usuarios"),
            ])
        ])
        pai = site.visible_nav(path="/usuarios")[0]
        assert pai.is_open and pai.children[0].active


class TestMenuDeTresNiveis:
    """A barra lateral desenha até três níveis.

    Só o primeiro tem ícone: é o que sobra na tela com a barra recolhida.
    Mais fundo, o ícone não caberia e não é desenhado.
    """

    def _arvore(self):
        from nucleo.layout import NavItem

        return [
            NavItem(label="Início", icon="home", href="/"),
            NavItem(label="Cadastros", icon="folder", children=[
                NavItem(label="Pessoas", children=[
                    NavItem(label="Físicas", href="/fisicas"),
                    NavItem(label="Jurídicas", href="/juridicas"),
                ]),
                NavItem(label="Produtos", href="/produtos"),
            ]),
        ]

    def _html(self, path="/"):
        from nucleo import Brand
        from nucleo.permissoes import User
        from nucleo.site import Site

        site = Site(brand=Brand(client_name="X"), nav=self._arvore())
        return _render(site.sidebar(path=path, user=User(id="1", name="Ana")))

    def test_o_terceiro_nivel_aparece(self):
        """Sem recursão no template, os netos somem em silêncio: o pai desenha
        e os itens de dentro nunca chegam ao HTML."""
        html = self._html()
        assert "Físicas" in html and "Jurídicas" in html

    def test_o_item_sem_icone_nao_quebra(self):
        """Do segundo nível para baixo não há ícone declarado."""
        assert "Pessoas" in self._html()

    def test_so_o_primeiro_nivel_desenha_icone(self):
        """Um ícone no segundo nível empurraria o texto e desalinharia a
        coluna inteira."""
        html = self._html()
        pessoas = html.split("Pessoas")[0].rsplit("<button", 1)[-1]
        assert "<svg" not in pessoas.split(">", 1)[0]

    def test_o_avo_abre_quando_o_neto_esta_na_tela(self):
        """Estando em /fisicas, "Cadastros" e "Pessoas" precisam estar
        abertos — senão a pessoa vê o menu fechado na tela em que está."""
        html = self._html(path="/fisicas")
        assert html.count('class="submenu open"') == 2

    def test_fora_da_arvore_nada_abre(self):
        assert 'class="submenu open"' not in self._html(path="/")


class TestMenuDoAvatar:
    """Clicar no avatar abre um menu ali mesmo, sem sair da tela.

    Sair da tela para ver "meu perfil" custa o contexto de quem estava no meio
    de alguma coisa — e a volta é o botão do navegador, que ninguém garante
    para onde leva depois de um POST.
    """

    def _html(self, **kwargs) -> str:
        from nucleo.layout import Header, UserInfo

        base = dict(name="Marina Vieira")
        return _render(Header(user=UserInfo(**{**base, **kwargs})))

    def test_o_avatar_nao_leva_para_outra_tela(self):
        html = self._html()
        assert '<a class="userchip"' not in html
        assert '<button class="userchip"' in html

    def test_o_avatar_abre_um_menu_que_existe(self):
        """Gatilho apontando para um id que não está na página é um botão que
        não faz nada — e ninguém percebe até alguém clicar."""
        import re

        html = self._html()
        alvo = re.search(r'data-dropdown-open="([^"]+)"', html).group(1)
        assert f'id="{alvo}"' in html

    def test_meu_perfil_esta_no_menu(self):
        html = self._html()
        assert "Meu Perfil" in html
        assert 'href="/perfil"' in html

    def test_o_destino_do_perfil_e_configuravel(self):
        assert 'href="/minha-area"' in self._html(menu_href="/minha-area")

    def test_o_projeto_pode_acrescentar_itens(self):
        from nucleo.components import DropdownItem

        html = self._html(menu=[
            DropdownItem(label="Meu Perfil", icon="user", href="/conta"),
            DropdownItem(label="Trocar senha", icon="lock", href="/senha"),
        ])
        assert "Trocar senha" in html and "Meu Perfil" in html

    def test_o_gatilho_anuncia_que_abre_menu(self):
        """Sem `aria-haspopup`, quem usa leitor de tela ouve "botão" e não tem
        como saber que ali abre um menu."""
        html = self._html()
        assert 'aria-haspopup="menu"' in html
        assert 'aria-expanded="false"' in html

    def test_o_menu_diz_de_quem_e(self):
        assert "Marina Vieira" in self._html()

    def test_sem_usuario_nao_sai_menu(self):
        from nucleo.layout import Header

        html = _render(Header(user=None))
        assert "userchip" not in html and "data-dropdown-open" not in html

    def test_sem_destino_o_avatar_nao_vira_botao(self):
        """Um menu vazio não deve virar um botão que abre o nada."""
        html = self._html(menu_href="")
        assert "data-dropdown-open" not in html

    def test_o_js_marca_o_gatilho_como_aberto(self):
        """`aria-expanded` precisa mudar quando o menu abre, senão o estado
        anunciado fica mentindo depois do primeiro clique."""
        js = _asset("mw5.js")
        assert "aria-expanded" in js


def _render(componente) -> str:
    from nucleo.rendering import create_environment, use_environment

    env = create_environment()
    with use_environment(env):
        return str(componente.render(env))


def _asset(nome: str) -> str:
    from pathlib import Path

    import nucleo

    return (Path(nucleo.__file__).parent / "static" / "nucleo" / nome).read_text(
        encoding="utf-8")


class TestMenuPorPermissao:
    """O menu filtrado pelo que a pessoa pode.

    Esconder o item é conforto, não controle de acesso — quem fecha a porta é
    `Guarda.exigir` na rota. Mas oferecer a alguém uma tela que vai responder
    403 é um defeito de produto, e o padrão precisa ser o seguro: um projeto
    que declara `permission=` e esquece de ligar a auth não pode acabar
    mostrando tudo para todo mundo.
    """

    def _site(self):
        from nucleo import Brand
        from nucleo.layout import NavItem
        from nucleo.site import Site

        return Site(brand=Brand(client_name="X"), nav=[
            NavItem(label="Início", icon="home", href="/"),
            NavItem(label="Usuários", icon="users", href="/usuarios",
                    permission="usuarios.ver"),
        ])

    def _rotulos(self, site, user):
        return [i.label for i in site.visible_nav(path="/", user=user)]

    def test_item_sem_permissao_aparece_para_quem_entrou(self):
        from nucleo.permissoes import User

        assert "Início" in self._rotulos(self._site(), User(id="1", name="Ana"))

    def test_item_com_permissao_some_de_quem_nao_tem(self):
        from nucleo.permissoes import User

        assert "Usuários" not in self._rotulos(self._site(), User(id="1", name="Ana"))

    def test_item_com_permissao_aparece_para_quem_tem(self):
        from nucleo.permissoes import User

        ana = User(id="1", name="Ana", permissions={"usuarios.ver"})
        assert "Usuários" in self._rotulos(self._site(), ana)

    def test_o_padrao_nao_e_mostrar_tudo(self):
        """Sem usuário nenhum, item protegido não vaza."""
        assert "Usuários" not in self._rotulos(self._site(), None)

    def test_o_projeto_pode_trocar_a_regra(self):
        """`can` continua substituível — é o gancho para uma base legada que
        responde permissão de outro jeito."""
        site = self._site()
        site.can = lambda user, permission: True
        assert "Usuários" in self._rotulos(site, None)


class TestRecolherAMenu:
    """A seta que fecha e abre a barra."""

    def _css(self) -> str:
        from pathlib import Path

        import nucleo

        return (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )

    def _js(self) -> str:
        from pathlib import Path

        import nucleo

        return (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.js").read_text(
            encoding="utf-8"
        )

    def test_a_barra_traz_o_botao(self):
        from nucleo.layout import NavItem, Sidebar
        from nucleo.rendering import render_all

        html = render_all(Sidebar(items=[NavItem("Início", "home", "/")], logo="/x.svg"))
        assert "data-sidebar-toggle" in html
        assert 'class="side-foot"' in html

    def test_o_botao_fica_fora_do_menu_que_rola(self):
        """Dentro dele, sumiria embaixo com a lista de módulos longa."""
        from nucleo.layout import NavItem, Sidebar
        from nucleo.rendering import render_all

        html = render_all(Sidebar(items=[NavItem("Início", "home", "/")], logo="/x.svg"))
        menu = html.split('class="side-nav"')[1].split("</nav>")[0]
        assert "data-sidebar-toggle" not in menu

    def test_o_estado_e_aplicado_antes_da_primeira_pintura(self):
        """No `.app` a barra abria larga e saltava para estreita a cada página."""
        from pathlib import Path

        import nucleo

        page = (
            Path(nucleo.__file__).parent / "templates" / "layout" / "page.html"
        ).read_text(encoding="utf-8")
        assert "mw5-menu-recolhido" in page
        assert 'documentElement.classList.add("side-collapsed")' in page
        # Por isso o seletor não pode exigir o `.app`, que ainda não existe ali.
        assert ".app.side-collapsed" not in self._css()

    def test_a_escolha_sobrevive_a_navegacao(self):
        assert "localStorage.setItem(MENU_KEY" in self._js()

    def test_clicar_num_item_que_abre_expande_a_barra(self):
        """Recolhida, os filhos estão escondidos: abrir não mostraria nada."""
        js = self._js()
        assert "if (menuRecolhido()) recolherMenu(false);" in js


class TestContextoDoCabecalho:
    """Duas visões do mesmo dado: quem administra escolhe, quem usa vê."""

    def _render(self, **kwargs) -> str:
        from nucleo.layout import ContextSwitcher
        from nucleo.rendering import render_all

        return render_all(ContextSwitcher(**kwargs))

    def test_a_visao_de_quem_usa_e_texto(self):
        from nucleo.layout import ContextLevel

        html = self._render(levels=[
            ContextLevel(label="Empresa", value="Transportes Aurora"),
            ContextLevel(label="Filial", value="Matriz"),
        ])
        assert "<select" not in html and "<form" not in html
        assert "Empresa:" in html and "<b class=\"ctx-valor\">Transportes Aurora</b>" in html

    def test_a_visao_de_quem_administra_e_seletor(self):
        from nucleo.layout import ContextLevel, ContextOption

        html = self._render(action="/contexto", levels=[
            ContextLevel(label="Empresa", value="B", name="nivel1", options=[
                ContextOption("A", "Alfa"), ContextOption("B", "Beta"),
            ]),
        ])
        assert '<form class="ctx" action="/contexto"' in html
        assert '<option value="B" selected>' in html
        assert 'value="A"' in html and "selected" not in html.split('value="A"')[1][:20]

    def test_o_rotulo_vem_da_marca_e_nao_do_componente(self):
        """Nem todo cliente chama de empresa e filial."""
        from nucleo.layout import ContextLevel

        html = self._render(levels=[ContextLevel(label="Bandeira", value="X")])
        assert "Bandeira:" in html
        assert "Empresa" not in html

    def test_opcao_sem_nome_e_recusada(self):
        """Sem `name`, a escolha não chega ao servidor — falha calada."""
        from nucleo.layout import ContextLevel, ContextOption

        with pytest.raises(ValueError, match="name"):
            ContextLevel(label="Empresa", options=[ContextOption("a", "A")])

    def test_sem_destino_nao_ha_formulario(self):
        """Um <form> sem action prometeria uma troca que não acontece."""
        from nucleo.layout import ContextLevel, ContextOption

        html = self._render(levels=[
            ContextLevel(label="Empresa", name="n1", options=[ContextOption("a", "A")])
        ])
        assert "<form" not in html and "<select" in html

    def test_a_marca_recusa_contexto_ligado_e_sem_rotulo(self):
        from nucleo.theme.brand import HeaderBrand

        with pytest.raises(ValueError, match="rótulo"):
            HeaderBrand(show_context=True, context_labels=("", " "))


class TestCantoDireitoDoCabecalho:
    """Notificações, sair e o avatar — nesta ordem, e nada além."""

    def _html(self, **kwargs) -> str:
        from nucleo.layout import Header, UserInfo
        from nucleo.rendering import render_all

        base = dict(user=UserInfo(name="Marina Duarte"), logout_href="/sair")
        return render_all(Header(**{**base, **kwargs}))

    def test_a_ordem_e_sino_sair_avatar(self):
        acoes = self._html().split('class="h-actions"')[1]
        posicoes = [acoes.find(m) for m in ("Notificações", "Sair", "userchip")]
        assert all(p > 0 for p in posicoes), posicoes
        assert posicoes == sorted(posicoes), "a ordem do canto direito mudou"

    def test_nao_ha_mais_botao_de_tema(self):
        """Esta versão não tem seletor de tema — o botão sobrou dele."""
        from nucleo.layout import Header

        assert "theme_toggle" not in Header.__dataclass_fields__
        assert "data-theme-toggle" not in self._html()

    def test_o_sino_vem_ligado(self):
        from nucleo.layout import Header
        from nucleo.site import Site

        assert Header.__dataclass_fields__["notifications"].default is True
        assert Site.__dataclass_fields__["show_notifications"].default is True

    def test_o_sino_pode_ser_desligado(self):
        assert "Notificações" not in self._html(notifications=False)


class TestRodape:
    """Dois cantos de texto livre, e o da esquerda aceita logo no lugar."""

    def _html(self, **kwargs) -> str:
        from nucleo.layout import Footer
        from nucleo.rendering import render_all

        return render_all(Footer(**kwargs))

    def test_o_fundo_e_branco_por_padrao(self):
        from nucleo import Brand

        assert Brand(client_name="X").tokens("light")["footer-bg"] == "#ffffff"

    def test_o_fundo_segue_configuravel(self):
        from nucleo import Brand
        from nucleo.theme.brand import AreaColors

        marca = Brand(client_name="X", areas=AreaColors(footer_bg="#101014"))
        assert marca.tokens("light")["footer-bg"] == "#101014"

    def test_os_dois_cantos_sao_texto_livre(self):
        html = self._html(left_text="Acme Software", right_text="fale com o suporte")
        assert "Acme Software" in html and "fale com o suporte" in html

    def test_o_logo_substitui_o_texto_da_esquerda(self):
        """Os dois juntos seriam a marca duas vezes lado a lado."""
        html = self._html(left_text="Acme", logo="/logo.svg", logo_alt="Acme")
        assert '<img src="/logo.svg"' in html
        assert ">Acme<" not in html

    def test_o_ano_e_resolvido_antes_de_chegar_ao_template(self):
        """Escrito à mão, ele envelhece na virada do ano sem ninguém notar."""
        from datetime import date

        from nucleo import Brand
        from nucleo.site import Site
        from nucleo.theme.brand import FooterBrand

        site = Site(brand=Brand(
            client_name="X", footer=FooterBrand(right_text="© {ano} Acme")
        ))
        assert site.footer().right_text == f"© {date.today().year} Acme"

    def test_o_sistema_e_resolvido_pelo_mesmo_mecanismo_do_ano(self):
        """`{sistema}` é o segundo placeholder de texto livre — mesma ideia
        do `{ano}` do rodapé, sem inventar uma segunda convenção."""
        from nucleo import Brand
        from nucleo.site import Site

        site = Site(brand=Brand(client_name="Acme", system_name="Kronos Vet"))
        assert site.resolve_sistema("Seus dados dentro de {sistema}.") == (
            "Seus dados dentro de Kronos Vet.")

    def test_o_sistema_sem_nome_proprio_usa_o_nome_do_cliente(self):
        """Sem `system_name`, `client_name` é o nome que sobra — o mesmo
        repasse que `ProjectSpec.title` já faz do lado do gerador."""
        from nucleo import Brand
        from nucleo.site import Site

        site = Site(brand=Brand(client_name="Acme"))
        assert site.resolve_sistema("Dentro de {sistema}.") == "Dentro de Acme."

    def test_o_nome_e_resolvido_pelo_mesmo_mecanismo_do_sistema(self):
        """`{nome}` é o placeholder da saudação do Início — mesma ideia do
        `{sistema}` do Meu Perfil e do `{ano}` do rodapé, só que o valor vem
        de quem está logado, e não da marca."""
        from nucleo import Brand
        from nucleo.layout import UserInfo
        from nucleo.site import Site

        site = Site(brand=Brand(client_name="Acme"))
        usuario = UserInfo(name="Marina Duarte")
        assert site.resolve_nome("Olá, {nome}", usuario) == "Olá, Marina"

    def test_saudacao_sem_placeholder_nao_muda(self):
        """Quem digitou um "Bem-vindo(a)!" simples não deveria precisar saber
        que a chave `{nome}` existe."""
        from nucleo import Brand
        from nucleo.layout import UserInfo
        from nucleo.site import Site

        site = Site(brand=Brand(client_name="Acme"))
        usuario = UserInfo(name="Marina Duarte")
        assert site.resolve_nome("Bem-vindo(a)!", usuario) == "Bem-vindo(a)!"

    def test_o_rodape_nao_e_lugar_de_logo_provisorio(self):
        """Um marcador ali apagaria o texto que a pessoa escreveu."""
        from nucleo.theme.brand import LUGARES_COM_PROVISORIO, LUGARES_DO_LOGO

        assert "footer" in LUGARES_DO_LOGO
        assert "footer" not in LUGARES_COM_PROVISORIO

    def test_a_altura_e_fixa(self):
        """Fecha a página na mesma linha com logo, sem logo, ou com texto longo."""
        from pathlib import Path

        import nucleo
        from nucleo import Brand

        regra = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8").split("\nfooter {")[1].split("}")[0]
        assert "height: var(--footer-h)" in regra
        assert "flex-wrap: nowrap" in regra, "quebrar linha desfaz a altura fixa"

        tokens = Brand(client_name="X").tokens("light")
        assert tokens["logo-footer-h"] in tokens["footer-h"], (
            "a altura tem que acompanhar a caixa do logo, senão um logo maior a estoura"
        )

    def test_o_texto_corta_em_vez_de_quebrar(self):
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8")
        regra = css.split("footer > span {")[1].split("}")[0]
        assert "text-overflow: ellipsis" in regra and "nowrap" in regra


class TestArquivosDaPagina:
    """`Site.scripts`/`stylesheets` default a lista vazia — quem quer um
    arquivo do site inteiro declara no `Site`; o teste usa um explícito para
    verificar que o pedido da página se soma a ele, e não o substitui."""

    def _site(self):
        from nucleo import Brand, Site

        return Site(brand=Brand(client_name="X"), scripts=["/static/mw5.js"])

    def test_a_pagina_acrescenta_sem_substituir(self):
        pagina = self._site().page(title="X", content="", scripts=["/static/x.js"])
        assert "/static/x.js" in pagina.scripts
        assert "/static/mw5.js" in pagina.scripts  # o do site continua

    def test_sem_pedir_nada_a_lista_e_a_do_site(self):
        site = self._site()
        assert site.page(title="X", content="").scripts == list(site.scripts)

    def test_o_mesmo_vale_para_css(self):
        from nucleo import Brand, Site

        site = Site(brand=Brand(client_name="X"), stylesheets=["/static/tema.css"])
        pagina = site.page(title="X", content="", stylesheets=["/static/x.css"])
        assert "/static/x.css" in pagina.stylesheets
        assert "/static/tema.css" in pagina.stylesheets

    def test_o_pedido_de_uma_pagina_nao_vaza_para_a_seguinte(self):
        """A lista do site é copiada, não estendida no lugar."""
        site = self._site()
        site.page(title="A", content="", scripts=["/static/x.js"])
        assert "/static/x.js" not in site.page(title="B", content="").scripts


class TestPerfilPage:
    def _user(self, avatar=""):
        from nucleo.permissoes import User
        return User(id="1", name="Marina Duarte", avatar=avatar)

    def test_desenha_a_secao_da_foto(self):
        from nucleo.layout import PerfilPage
        marcacao = html(PerfilPage(user=self._user()))
        assert 'data-recorte="foto"' in marcacao
        assert 'data-recorte-palco="foto"' in marcacao
        assert 'data-recorte-alvo="foto"' in marcacao
        assert 'name="recorte"' in marcacao

    def test_sem_capacidade_a_secao_de_senha_nao_existe(self):
        from nucleo.layout import PerfilPage
        marcacao = html(PerfilPage(user=self._user(), troca_de_senha=False))
        assert "senha_atual" not in marcacao

    def test_com_capacidade_a_secao_de_senha_aparece_inteira(self):
        from nucleo.layout import PerfilPage
        marcacao = html(PerfilPage(user=self._user(), troca_de_senha=True))
        for campo in ("senha_atual", "senha_nova", "senha_confirma"):
            assert campo in marcacao

    def test_o_minimo_da_senha_aparece_para_quem_le(self):
        from nucleo.permissoes import SENHA_MINIMA
        from nucleo.layout import PerfilPage
        assert str(SENHA_MINIMA) in html(PerfilPage(user=self._user(),
                                                    troca_de_senha=True))

    def test_os_textos_sao_os_que_recebeu(self):
        from nucleo.layout import PerfilPage
        # `rotulo_senha` só existe na marcação quando a seção de senha existe
        # — daí `troca_de_senha=True` aqui: sem isso o teste checaria um
        # rótulo que o próprio design manda omitir.
        marcacao = html(PerfilPage(user=self._user(), titulo="Minha Conta",
                                   rotulo_foto="Retrato", rotulo_senha="Acesso",
                                   troca_de_senha=True))
        for texto in ("Minha Conta", "Retrato", "Acesso"):
            assert texto in marcacao

    def test_as_acoes_vao_para_onde_mandaram(self):
        from nucleo.layout import PerfilPage
        marcacao = html(PerfilPage(user=self._user(), troca_de_senha=True,
                                   acao_foto="/x/foto", acao_senha="/x/senha"))
        assert 'action="/x/foto"' in marcacao and 'action="/x/senha"' in marcacao

    def test_o_erro_e_o_aviso_aparecem(self):
        from nucleo.layout import PerfilPage
        assert "não confere" in html(PerfilPage(user=self._user(),
                                                erro="A senha atual não confere."))
        assert "Foto atualizada" in html(PerfilPage(user=self._user(),
                                                    ok="Foto atualizada."))

    def test_texto_de_erro_com_html_nao_escapa(self):
        from nucleo.layout import PerfilPage
        assert "<script>" not in html(PerfilPage(user=self._user(),
                                                 erro="<script>x</script>"))

    def test_sem_usuario_falha_na_construcao(self):
        from nucleo.layout import PerfilPage
        with pytest.raises(ValueError, match="PerfilPage"):
            PerfilPage()


class TestBox:
    def test_padrao_e_o_empilhamento_de_hoje(self):
        """Caixa nova nasce igual ao que o construtor ja fazia. Quem nao mexer
        em nada nao pode ver diferenca."""
        html = render_all(Box(body="oi"))
        assert "box-column" in html
        assert "box-main-start" in html
        assert "box-cross-stretch" in html
        assert "box-gap-md" in html
        assert "box-pad-none" in html
        assert "box-nowrap" not in html

    def test_direcao_linha(self):
        assert "box-row" in render_all(Box(body="", direction="row"))

    def test_alinhamento_no_eixo(self):
        assert "box-main-between" in render_all(Box(body="", align="between"))

    def test_alinhamento_transversal(self):
        assert "box-cross-center" in render_all(Box(body="", cross="center"))

    def test_espacamento(self):
        assert "box-gap-lg" in render_all(Box(body="", gap="lg"))

    def test_recheio(self):
        assert "box-pad-sm" in render_all(Box(body="", pad="sm"))

    def test_sem_quebra(self):
        assert "box-nowrap" in render_all(Box(body="", wrap=False))

    def test_caminho_so_aparece_quando_pedido(self):
        assert "data-mw5-caminho" not in render_all(Box(body=""))
        assert 'data-mw5-caminho="0.1"' in render_all(Box(body="", path="0.1"))

    def test_nao_emite_style_inline(self):
        """Medida em pixel num `style` sairia do sistema de tokens, e a
        primeira caixa com 13px seria o fim da garantia de padrao visual."""
        html = render_all(Box(body="", direction="row", gap="lg", pad="lg"))
        assert "style=" not in html

    @pytest.mark.parametrize("campo,valor", [
        ("direction", "diagonal"), ("align", "space-evenly"),
        ("cross", "baseline"), ("gap", "xl"), ("pad", "enorme"),
    ])
    def test_valor_invalido_levanta(self, campo, valor):
        with pytest.raises(ValueError):
            render_all(Box(body="", **{campo: valor}))

    def test_toda_classe_possivel_existe_no_css(self):
        """Teste de contrato: toda classe que o template pode emitir existe
        no CSS, com regra propria — nao so um pedaco do nome de outra classe.

        As classes esperadas vem de renderizar de verdade (uma `Box` por
        valor de cada enum, mais `wrap=False`) e nao de digitar os prefixos
        `box-main-`/`box-cross-`/... a mao: assim o teste prova a classe que
        o template emite, e nao a que a concatenacao do teste imagina que
        ele emite. A busca no CSS exige que o nome termine ali — `.box`
        sozinho nao pode passar so porque `.box-column` existe.
        """
        import re
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo"
               / "mw5.css").read_text(encoding="utf-8")

        renders = [Box(body="")]
        renders += [Box(body="", direction=d) for d in DIRECOES]
        renders += [Box(body="", align=a) for a in ALINHAMENTOS]
        renders += [Box(body="", cross=c) for c in TRANSVERSAIS]
        renders += [Box(body="", gap=g) for g in ESPACAMENTOS]
        renders += [Box(body="", pad=p) for p in ESPACAMENTOS]
        renders += [Box(body="", wrap=False)]

        esperadas: set[str] = set()
        for box in renders:
            classe_attr = re.search(r'class="([^"]*)"', render_all(box)).group(1)
            esperadas.update(classe_attr.split())

        for classe in sorted(esperadas):
            # Limite de nome, e nao "termina em virgula ou chave": exigir a
            # pontuacao logo depois daria falso-negativo em `.box-row:hover` ou
            # `.box-row.compact`, que sao seletores legitimos e o padrao usado
            # em outras partes deste CSS. Um teste que falha com codigo certo e
            # um teste que alguem enfraquece na primeira vez que atrapalha.
            assert re.search(rf"\.{re.escape(classe)}(?![\w-])", css), \
                f"falta `.{classe}` no mw5.css"


class TestCellCaminho:
    def test_caminho_so_aparece_quando_pedido(self):
        assert "data-mw5-caminho" not in render_all(Cell(span=6, children=""))
        assert 'data-mw5-caminho="2.0"' in render_all(
            Cell(span=6, children="", path="2.0"))
