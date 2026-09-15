import pytest

from nucleo.theme import (
    TOKEN_NAMES,
    Brand,
    Color,
    contrast_ratio,
    readable_on,
    render_theme_css,
)

VETPLAN = Brand(client_name="VETPLAN", primary="#1e40af", accent="#872d00")


class TestColor:
    def test_hex_roundtrip_is_exact(self):
        for value in ("#1e40af", "#872d00", "#f6f7fb", "#000000", "#ffffff"):
            assert Color.from_hex(value).hex == value

    def test_oklch_roundtrip_preserves_the_color(self):
        original = Color.from_hex("#1e40af")
        assert Color.from_oklch(*original.to_oklch()).hex == original.hex

    def test_short_hex_expands(self):
        assert Color.from_hex("#abc").hex == "#aabbcc"

    @pytest.mark.parametrize("bad", ["", "#12", "#12345", "nope", "#zzzzzz"])
    def test_invalid_hex_is_rejected(self, bad):
        with pytest.raises(ValueError):
            Color.from_hex(bad)

    def test_out_of_gamut_keeps_hue_and_lightness(self):
        """Um azul saturado demais deve perder croma, não virar outra cor."""
        wanted_l, wanted_h = 0.75, 265.6
        got = Color.from_oklch(wanted_l, 0.30, wanted_h)
        got_l, got_c, got_h = got.to_oklch()
        assert got_l == pytest.approx(wanted_l, abs=0.01)
        assert got_h == pytest.approx(wanted_h, abs=1.0)
        assert got_c < 0.30  # foi reduzido para caber

    def test_gamut_mapping_beats_naive_clipping(self):
        """A cor mapeada tem que ser mais saturada do que o corte por canal daria."""
        mapped = Color.from_oklch(0.751, 0.128, 265.6)
        assert mapped.to_oklch()[1] > 0.11

    def test_readable_on_picks_the_stronger_contrast(self):
        assert readable_on("#1e40af").hex == "#ffffff"
        assert readable_on("#f6f7fb").hex != "#ffffff"

    def test_contrast_ratio_bounds(self):
        assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=0.01)
        assert contrast_ratio("#1e40af", "#1e40af") == pytest.approx(1.0)


class TestTokens:
    def test_every_declared_token_is_resolved(self):
        for mode in ("light", "dark"):
            resolved = VETPLAN.tokens(mode)
            assert set(TOKEN_NAMES) <= set(resolved)
            assert all(resolved[name] for name in TOKEN_NAMES)

    def test_primary_is_used_literally_in_light_mode(self):
        assert VETPLAN.tokens("light")["primary"] == "#1e40af"

    def test_neutrals_match_the_vetplan_mocks(self):
        """A derivação tem que reproduzir os neutros do redesign, não algo parecido."""
        light = VETPLAN.tokens("light")
        for name, expected in [
            ("bg", "#f6f7fb"),
            ("surface", "#ffffff"),
            ("surface-2", "#f1f2f8"),
            ("surface-3", "#e9ebf3"),
            ("on-surface", "#1a1b22"),
            ("on-surface-2", "#565968"),
            ("outline", "#d4d7e3"),
            ("outline-2", "#e6e8f1"),
        ]:
            assert _close(light[name], expected), f"{name}: {light[name]} != {expected}"

    def test_dark_mode_inverts_the_surfaces(self):
        light, dark = VETPLAN.tokens("light"), VETPLAN.tokens("dark")
        assert Color.from_hex(dark["bg"]).lightness < 0.3
        assert Color.from_hex(light["bg"]).lightness > 0.9
        assert Color.from_hex(dark["on-surface"]).lightness > 0.8

    def test_text_over_primary_is_legible_in_both_modes(self):
        """O par primary/on-primary precisa passar em AA para texto grande."""
        for mode in ("light", "dark"):
            tokens = VETPLAN.tokens(mode)
            assert contrast_ratio(tokens["primary"], tokens["on-primary"]) >= 4.5

    def test_body_text_is_legible_in_both_modes(self):
        for mode in ("light", "dark"):
            tokens = VETPLAN.tokens(mode)
            assert contrast_ratio(tokens["surface"], tokens["on-surface"]) >= 7.0
            assert contrast_ratio(tokens["surface"], tokens["on-surface-2"]) >= 4.5

    def test_neutrals_follow_the_brand_hue(self):
        """Marca verde não pode receber cinzas azulados."""
        green = Brand(client_name="Verde", primary="#146c43")
        hue = Color.from_hex(green.tokens("light")["surface-3"]).to_oklch()[2]
        assert 130 < hue < 190

    def test_semantic_colors_ignore_the_brand(self):
        other = Brand(client_name="Outro", primary="#6b21a8")
        assert other.tokens("light")["danger"] == VETPLAN.tokens("light")["danger"]

    def test_overrides_win(self):
        pinned = VETPLAN.with_overrides("dark", primary="#93a8ff")
        assert pinned.tokens("dark")["primary"] == "#93a8ff"
        assert pinned.tokens("light")["primary"] == "#1e40af"


class TestBrand:
    def test_empty_client_name_is_rejected(self):
        with pytest.raises(ValueError, match="client_name"):
            Brand(client_name="  ")

    def test_unknown_token_in_overrides_is_rejected(self):
        with pytest.raises(ValueError, match="inexistentes"):
            Brand(client_name="X", overrides={"light": {"cor-principal": "#fff"}})

    def test_unknown_mode_in_overrides_is_rejected(self):
        with pytest.raises(ValueError, match="light"):
            Brand(client_name="X", overrides={"sepia": {"primary": "#fff"}})

    def test_invalid_default_theme_is_rejected(self):
        with pytest.raises(ValueError, match="default_theme"):
            Brand(client_name="X", default_theme="escuro")  # type: ignore[arg-type]

    def test_from_yaml_reads_nested_sections(self, tmp_path):
        path = tmp_path / "brand.yaml"
        path.write_text(
            "client_name: ACME\n"
            "system_name: Portal\n"
            "primary: '#6b21a8'\n"
            "footer:\n"
            "  left_text: MW5\n"
            "  right_text: '© {ano} MW5'\n"
            "login:\n"
            "  tagline: Bem-vindo\n",
            encoding="utf-8",
        )
        brand = Brand.from_yaml(path)
        assert brand.client_name == "ACME"
        assert brand.footer.right_text == "© {ano} MW5"
        assert brand.login.tagline == "Bem-vindo"

    def test_typo_in_yaml_is_caught_not_ignored(self, tmp_path):
        path = tmp_path / "brand.yaml"
        path.write_text("client_name: ACME\nprimaria: '#fff'\n", encoding="utf-8")
        with pytest.raises(ValueError, match="desconhecidos"):
            Brand.from_yaml(path)

    def test_missing_file_says_what_to_do(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="brand.yaml"):
            Brand.from_yaml(tmp_path / "ausente.yaml")

    def test_cada_lugar_tem_seu_logo_e_nao_cai_no_do_outro(self):
        """Não existe logo "geral": a marca do cartão de login não é a mesma que
        cabe na faixa da barra lateral."""
        from nucleo.theme.brand import Assets

        assets = Assets(login_logo="/completo.png")
        assert assets.logo_for("login") == "/completo.png"
        assert assets.logo_for("sidebar") == ""  # não herda de outro lugar

    def test_o_cabecalho_nao_e_mais_um_lugar_de_logo(self):
        """A marca já está na faixa da barra lateral, à esquerda e maior."""
        from nucleo.theme.brand import LUGARES_DO_LOGO

        assert "header" not in LUGARES_DO_LOGO
        with pytest.raises(ValueError, match="lugar de logo"):
            VETPLAN.assets.logo_for("header")

    def test_lugar_inexistente_e_recusado(self):
        with pytest.raises(ValueError, match="lugar de logo"):
            VETPLAN.assets.logo_for("rodape")

    def test_from_dict_le_a_secao_areas(self):
        """`areas:` é uma seção aninhada como `footer` ou `login` — sem
        entrar em `nested`, o valor ficava um `dict` cru e `as_tokens()`
        quebrava na primeira chamada."""
        brand = Brand.from_dict({
            "client_name": "X",
            "areas": {"sidebar_bg": "#ff0000"},
        })
        assert brand.areas.sidebar_bg == "#ff0000"
        assert brand.tokens("light")["sidebar-bg"] == "#ff0000"

    def test_campo_desconhecido_em_areas_e_recusado(self):
        with pytest.raises(ValueError, match="sidebar_bgg"):
            Brand.from_dict({
                "client_name": "X",
                "areas": {"sidebar_bgg": "#ff0000"},
            })


class TestThemeCss:
    def test_emits_the_three_layers(self):
        css = render_theme_css(VETPLAN)
        assert ":root{" in css
        assert "@media (prefers-color-scheme:dark)" in css
        assert ':root[data-theme="light"]' in css
        assert ':root[data-theme="dark"]' in css

    def test_declares_every_token(self):
        css = render_theme_css(VETPLAN)
        for name in TOKEN_NAMES:
            assert f"--{name}:" in css

    def test_fixed_light_theme_does_not_follow_the_os(self):
        css = render_theme_css(Brand(client_name="X", default_theme="light"))
        assert "prefers-color-scheme" not in css
        assert ':root[data-theme="dark"]' in css  # o botão ainda funciona

    def test_fixed_dark_theme_starts_dark(self):
        brand = Brand(client_name="X", default_theme="dark")
        css = render_theme_css(brand)
        base = css.split(':root[data-theme="light"]')[0]
        assert f"--bg:{brand.tokens('dark')['bg']}" in base


def _close(got: str, expected: str, tolerance: int = 3) -> bool:
    """Dois hex são equivalentes se cada canal difere no máximo `tolerance`."""
    a, b = got.lstrip("#"), expected.lstrip("#")
    return all(
        abs(int(a[i : i + 2], 16) - int(b[i : i + 2], 16)) <= tolerance
        for i in (0, 2, 4)
    )


class TestCorSecundaria:
    """A cor secundária existia como token sem ninguém consumi-la — mexer nela
    não mudava nada na tela. Estes testes existem para isso não voltar."""

    def test_o_css_do_design_system_usa_a_secundaria(self):
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )
        assert "var(--accent)" in css, (
            "nenhuma regra consome --accent: o controle de cor secundária "
            "não teria efeito visível"
        )

    def test_texto_sobre_a_secundaria_e_legivel_em_qualquer_marca(self):
        for accent in ("#872d00", "#0f766e", "#eab308", "#db2777", "#000000"):
            for mode in ("light", "dark"):
                tokens = Brand(client_name="X", accent=accent).tokens(mode)
                assert (
                    contrast_ratio(tokens["accent"], tokens["on-accent"]) >= 4.5
                ), f"{accent} em {mode} não passa em AA"

    def test_secundaria_nao_afeta_a_primaria(self):
        a = Brand(client_name="X", accent="#0f766e").tokens("light")
        b = Brand(client_name="X", accent="#db2777").tokens("light")
        assert a["primary"] == b["primary"]
        assert a["accent"] != b["accent"]


class TestAreaDoLogo:
    """O espaço do logo é fixo e a imagem se ajusta dentro dele.

    Sem isso, cada cliente que envia um logo de proporção diferente desloca o
    resto da tela — o cartão de login sobe ou desce, o menu escorrega.
    """

    TOKENS = ("logo-login-w", "logo-login-h", "logo-side-w",
              "logo-side-h")

    def test_as_areas_existem_como_token(self):
        tokens = VETPLAN.tokens("light")
        for nome in self.TOKENS:
            assert tokens[nome], f"{nome} não foi resolvido"

    def test_sao_iguais_nos_dois_modos(self):
        """Medida de layout não muda com o tema."""
        claro, escuro = VETPLAN.tokens("light"), VETPLAN.tokens("dark")
        for nome in self.TOKENS:
            assert claro[nome] == escuro[nome]

    def test_o_css_limita_pelo_token_e_nao_por_porcentagem(self):
        """`max-height: 100%` num <img> dentro de grid não resolve de forma
        confiável — a imagem escapava da caixa. O limite tem que ser o token."""
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )
        for seletor, token in [
            (".login-logo {", "--logo-login-h"),
            (".side-logo {", "--logo-side-h"),
        ]:
            regra = css.split(seletor)[1].split("}")[0]
            assert f"var({token})" in regra, f"{seletor} sem limite fixo"
            # `min(var(--token), 100%)` continua valendo: o token é o teto, e a
            # porcentagem só entra quando o espaço é menor que ele. O que não
            # pode é a porcentagem sozinha, sem teto nenhum.
            assert "max-height: 100%" not in regra

    def test_area_pode_ser_ajustada_pela_marca(self):
        brand = Brand(client_name="X", logo_areas={"logo-login-h": "110px"})
        assert brand.tokens("light")["logo-login-h"] == "110px"
        assert brand.tokens("light")["logo-login-w"] == "220px"  # o resto fica

    def test_token_inexistente_e_recusado(self):
        with pytest.raises(ValueError, match="logo_areas"):
            Brand(client_name="X", logo_areas={"logo-gigante": "10px"})

    def test_medida_invalida_e_recusada(self):
        with pytest.raises(ValueError, match="medida CSS"):
            Brand(client_name="X", logo_areas={"logo-login-h": "grande"})


class TestCoresPorArea:
    """Cada área pode ter cor própria, e herda do tema quando não tem.

    A herança é o que mantém o sistema parecendo um sistema só: mexer numa área
    é uma decisão, não uma obrigação.
    """

    def test_sem_escolha_a_area_herda_do_tema(self):
        tokens = VETPLAN.tokens("light")
        assert tokens["header-bg"] == tokens["surface"]
        assert tokens["content-bg"] == tokens["bg"]
        assert tokens["table-head-bg"] == tokens["surface-2"]

    def test_o_menu_nasce_azul_escuro_com_texto_branco(self):
        """A exceção à herança, e de propósito: é assim que o padrão da casa
        começa. Continua configurável como qualquer outra área."""
        from nucleo.theme.color import contrast_ratio

        for modo in ("light", "dark"):
            tokens = VETPLAN.tokens(modo)
            assert tokens["sidebar-bg"] == "#28467d"
            assert tokens["sidebar-text"] == "#ffffff"
            assert contrast_ratio(tokens["sidebar-bg"], tokens["sidebar-text"]) > 7
            assert contrast_ratio(tokens["sidebar-bg"], tokens["sidebar-active-text"]) > 4.5

    def test_o_menu_segue_sendo_configuravel(self):
        from nucleo.theme.brand import AreaColors

        tokens = Brand(
            client_name="X",
            areas=AreaColors(sidebar_bg="#ffffff", sidebar_text="#333333"),
        ).tokens("light")
        assert (tokens["sidebar-bg"], tokens["sidebar-text"]) == ("#ffffff", "#333333")

    def test_escolha_de_uma_area_nao_afeta_as_outras(self):
        from nucleo.theme.brand import AreaColors

        brand = Brand(client_name="X", areas=AreaColors(sidebar_bg="#0f172a"))
        tokens = brand.tokens("light")
        assert tokens["sidebar-bg"] == "#0f172a"
        assert tokens["header-bg"] == tokens["surface"]  # seguiu o tema

    def test_a_heranca_acompanha_o_modo(self):
        """No escuro, a área sem escolha tem que seguir a superfície escura."""
        claro, escuro = VETPLAN.tokens("light"), VETPLAN.tokens("dark")
        assert claro["header-bg"] != escuro["header-bg"]
        assert escuro["header-bg"] == escuro["surface"]

    def test_cor_invalida_e_recusada(self):
        from nucleo.theme.brand import AreaColors

        with pytest.raises(ValueError, match="sidebar_bg"):
            AreaColors(sidebar_bg="azul")

    def test_o_css_consome_os_tokens_de_area(self):
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8"
        )
        for token in ("--sidebar-bg", "--sidebar-text", "--sidebar-active-text", "--sidebar-hover-bg",
                      "--header-bg", "--header-text", "--content-bg",
                      "--footer-text", "--table-head-bg", "--table-head-text"):
            assert f"var({token})" in css, f"{token} não é usado por nenhuma regra"


class TestCoresDeInteracaoDoMenu:
    """Passar o mouse e estar selecionado são quatro cores, não duas.

    Antes o CSS derivava tudo de `--sidebar-text` e `--sidebar-active` por
    `color-mix`. Funcionava, mas não era escolhível: um cliente que quisesse o
    hover na cor da marca não tinha onde dizer isso.
    """

    def tokens(self, **kwargs):
        from nucleo import Brand
        from nucleo.theme.brand import AreaColors

        return Brand(client_name="X", areas=AreaColors(**kwargs)).tokens("light")

    def test_os_quatro_tokens_existem(self):
        t = self.tokens()
        for nome in ("sidebar-hover-bg", "sidebar-hover-text",
                     "sidebar-active-bg", "sidebar-active-text"):
            assert t[nome], f"{nome} veio vazio"

    def test_todos_sao_cor_de_verdade(self):
        """Precisam ser hexadecimal: o seletor de cor do editor não sabe abrir
        um `color-mix`, e o campo apareceria em branco."""
        from nucleo.theme.color import Color

        t = self.tokens()
        for nome in ("sidebar-hover-bg", "sidebar-hover-text",
                     "sidebar-active-bg", "sidebar-active-text"):
            Color.from_hex(t[nome])   # levanta se não for

    def test_o_padrao_nao_muda_a_cara_de_quem_ja_existe(self):
        """O menu azul com texto branco continua igual: o hover é o mesmo
        clareado de antes, agora resolvido em hexadecimal."""
        t = self.tokens()
        assert t["sidebar-active-text"] == "#95bbff"
        # Fundos de interação são sutis — perto do fundo do menu, não do texto.
        from nucleo.theme.color import contrast_ratio

        assert contrast_ratio(t["sidebar-bg"], t["sidebar-hover-bg"]) < 1.6

    def test_cada_um_e_escolhivel(self):
        t = self.tokens(sidebar_hover_bg="#ff0000", sidebar_hover_text="#00ff00",
                        sidebar_active_bg="#0000ff", sidebar_active_text="#ffff00")
        assert t["sidebar-hover-bg"] == "#ff0000"
        assert t["sidebar-hover-text"] == "#00ff00"
        assert t["sidebar-active-bg"] == "#0000ff"
        assert t["sidebar-active-text"] == "#ffff00"

    def test_o_texto_do_hover_continua_legivel_no_padrao(self):
        from nucleo.theme.color import contrast_ratio

        t = self.tokens()
        assert contrast_ratio(t["sidebar-hover-bg"], t["sidebar-hover-text"]) > 4.5

    def test_o_css_usa_os_tokens_e_nao_color_mix_do_texto(self):
        """Derivado do texto, escolher a cor do hover não teria efeito nenhum."""
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo" / "mw5.css").read_text(
            encoding="utf-8")
        regra = css.split(".side-nav a:hover")[1].split("}")[0]
        assert "--sidebar-hover-bg" in regra and "--sidebar-hover-text" in regra

    def test_o_menu_escuro_de_fundo_claro_tambem_funciona(self):
        """Fundo claro pede hover escurecido, não clareado — senão ele some."""
        from nucleo.theme.color import contrast_ratio

        t = self.tokens(sidebar_bg="#ffffff", sidebar_text="#1a1a2e")
        assert contrast_ratio(t["sidebar-bg"], t["sidebar-hover-bg"]) > 1.02
        assert contrast_ratio(t["sidebar-hover-bg"], t["sidebar-hover-text"]) > 4.5


class TestLegivelSobre:
    """Ajusta a claridade de uma cor até ela ser legível sobre um fundo.

    Diferente de `readable_on`, que escolhe entre preto e branco: aqui a cor
    escolhida é preservada em matiz e croma, e só a claridade se move. É o que
    permite o azul do item selecionado continuar azul num menu claro e num
    menu escuro.
    """

    def test_cor_ja_legivel_nao_muda(self):
        from nucleo.theme.color import legivel_sobre

        assert legivel_sobre("#28467d", "#95bbff").hex == "#95bbff"

    @pytest.mark.parametrize("fundo", ["#ffffff", "#f6f7fb", "#28467d", "#101014"])
    def test_sempre_chega_a_legivel(self, fundo):
        from nucleo.theme.color import legivel_sobre

        ajustada = legivel_sobre(fundo, "#95bbff")
        assert contrast_ratio(fundo, ajustada) >= 4.5

    def test_a_cor_continua_sendo_a_mesma_cor(self):
        """Escurecer o azul não pode devolver cinza nem outro matiz."""
        from nucleo.theme.color import legivel_sobre

        origem = Color.from_hex("#95bbff")
        ajustada = legivel_sobre("#ffffff", origem)
        assert abs(ajustada.to_oklch()[2] - origem.to_oklch()[2]) < 8
        assert ajustada.to_oklch()[1] > 0.04   # não virou cinza

    def test_o_item_selecionado_e_legivel_em_qualquer_menu(self):
        from nucleo import Brand
        from nucleo.theme.brand import AreaColors

        for fundo, texto in [("#28467d", "#ffffff"), ("#ffffff", "#1a1a2e"),
                             ("#101014", "#e8e8ef"), ("#146c43", "#ffffff")]:
            t = Brand(client_name="X", areas=AreaColors(
                sidebar_bg=fundo, sidebar_text=texto)).tokens("light")
            assert contrast_ratio(t["sidebar-bg"], t["sidebar-active-text"]) >= 4.5, fundo


class TestPaletaDeGraficos:
    """As oito cores de série: da marca, distinguíveis, e legíveis nos dois temas."""

    def _paleta(self, brand, modo):
        tokens = brand.tokens(modo)
        return [tokens[f"chart-{i}"] for i in range(1, 9)]

    def test_existem_oito(self):
        brand = Brand(client_name="X")
        for modo in ("light", "dark"):
            assert len(self._paleta(brand, modo)) == 8

    def test_sao_todas_diferentes(self):
        brand = Brand(client_name="X")
        for modo in ("light", "dark"):
            assert len(set(self._paleta(brand, modo))) == 8

    def test_os_matizes_se_separam(self):
        """Série vizinha com matiz parecido é gráfico ilegível."""
        from nucleo.theme.color import Color

        matizes = [Color.from_hex(c).to_oklch()[2] % 360
                   for c in self._paleta(Brand(client_name="X"), "light")]
        for i, a in enumerate(matizes):
            for b in matizes[i + 1:]:
                distancia = abs(a - b) % 360
                distancia = min(distancia, 360 - distancia)
                assert distancia >= 40, f"{a:.0f}° e {b:.0f}° estão perto demais"

    def test_aparecem_sobre_o_fundo_nos_dois_temas(self):
        """3:1 é o mínimo do WCAG para objeto gráfico, que é o que uma barra é."""
        from nucleo.theme.color import contrast_ratio

        brand = Brand(client_name="X")
        for modo in ("light", "dark"):
            tokens = brand.tokens(modo)
            for i in range(1, 9):
                razao = contrast_ratio(tokens["surface"], tokens[f"chart-{i}"])
                assert razao >= 3.0, f"chart-{i} some no tema {modo} ({razao:.2f})"

    def test_a_primeira_segue_o_matiz_da_marca(self):
        from nucleo.theme.color import Color

        brand = Brand(client_name="X", primary="#146c43")
        _, _, matiz_marca = Color.from_hex("#146c43").to_oklch()
        _, _, matiz_serie = Color.from_hex(brand.tokens("light")["chart-1"]).to_oklch()
        assert abs((matiz_marca - matiz_serie) % 360) < 1

    def test_a_escolha_explicita_ganha(self):
        brand = Brand(client_name="X", chart_colors=("#ff0000", "#00ff00"))
        tokens = brand.tokens("light")
        assert tokens["chart-1"] == "#ff0000"
        assert tokens["chart-2"] == "#00ff00"

    def test_o_resto_continua_automatico(self):
        """Mexer numa cor não obriga a preencher as outras sete."""
        escolhida = Brand(client_name="X", chart_colors=("#ff0000",)).tokens("light")
        automatica = Brand(client_name="X").tokens("light")
        assert escolhida["chart-3"] == automatica["chart-3"]

    def test_cor_invalida_falha_na_construcao(self):
        with pytest.raises(ValueError, match="chart_colors"):
            Brand(client_name="X", chart_colors=("azul",))

    def test_uma_marca_quase_cinza_ainda_da_cor(self):
        """Croma mínimo: sem ele, um cliente de marca cinza teria oito cinzas."""
        from nucleo.theme.color import Color

        brand = Brand(client_name="X", primary="#555555")
        for i in range(1, 9):
            _, croma, _ = Color.from_hex(brand.tokens("light")[f"chart-{i}"]).to_oklch()
            assert croma >= 0.05


class TestOLogoLateralPreencheAFaixa:
    """A faixa da marca reserva a barra inteira menos o recheio — nem um pixel
    a menos.

    Presa num numero solto (184px numa barra de 256), ela deixava 40px de folga
    sem uso: um logo largo — que e a maioria — parava de crescer por causa desse
    teto e nunca chegava a encostar na altura, ficando pequeno no meio de uma
    faixa alta.
    """

    def _css(self) -> str:
        from pathlib import Path

        import nucleo

        return (Path(nucleo.__file__).parent / "static" / "nucleo"
                / "mw5.css").read_text(encoding="utf-8")

    def _recheio_lateral_da_faixa(self) -> int:
        """Os 16px que o `.side-brand` reserva de cada lado, lidos do CSS."""
        import re

        regra = re.search(r"\.side-brand\s*\{([^}]*)\}", self._css())
        assert regra, "a faixa da marca perdeu a regra propria"
        achado = re.search(r"padding:\s*[^;]*?\s(\d+)px\s*;", regra.group(1))
        assert achado, f"o recheio da faixa mudou de forma: {regra.group(1)}"
        return int(achado.group(1))

    def test_a_area_do_logo_acompanha_a_largura_da_barra(self):
        """Numero fixo aqui volta a sobrar folga no dia em que a barra mudar de
        largura — e ela e configuravel."""
        largura = VETPLAN.tokens("light")["logo-side-w"]
        assert "var(--sidebar-w)" in largura, (
            f"a area do logo lateral voltou a ser um numero solto: {largura}")

    def test_a_folga_descontada_e_exatamente_o_recheio_da_faixa(self):
        """O desconto no token e o recheio do CSS, escrito duas vezes. Se um dos
        dois mudar sozinho, ou sobra faixa vazia ou o logo encosta na borda."""
        import re

        largura = VETPLAN.tokens("light")["logo-side-w"]
        achado = re.search(r"-\s*(\d+)px", largura)
        assert achado, f"a conta da area do logo mudou de forma: {largura}"
        assert int(achado.group(1)) == self._recheio_lateral_da_faixa() * 2, (
            f"o token desconta {achado.group(1)}px e a faixa reserva "
            f"{self._recheio_lateral_da_faixa()}px de cada lado")

    def test_a_barra_estreita_ainda_manda(self):
        """A conta pode dar mais do que cabe se alguem estreitar muito a barra.
        O `min(..., 100%)` do `.side-logo` e o que impede o logo de vazar."""
        import re

        regra = re.search(r"\.side-logo\s*\{([^}]*)\}", self._css())
        assert regra and "min(var(--logo-side-w), 100%)" in regra.group(1), (
            "o `min` saiu do `.side-logo`: numa barra estreita o logo vaza")

    def test_a_altura_continua_fixa(self):
        """So a largura passou a acompanhar. A altura e o que mantem a faixa —
        e o cabecalho, que copia a altura dela — igual para todo cliente."""
        assert VETPLAN.tokens("light")["logo-side-h"].endswith("px")


class TestOLogoPreencheACaixaReservada:
    """`max-width` so LIMITA — nunca faz crescer.

    Os tres lugares onde o logo aparece reservavam uma caixa e mandavam a
    imagem em `width: auto`: um arquivo menor que a caixa ficava no tamanho
    natural, pequeno no meio dela, e nada no CSS dizia o contrario. A caixa
    existia e a imagem a ignorava.

    Quem preenche e uma dimensao mandada — `width: 100%` onde a caixa tem
    tamanho proprio, `height` reservada onde ela nao tem — e quem preserva a
    proporcao e centraliza o que sobra e o `object-fit: contain`.
    """

    #: seletor -> a dimensao que faz a imagem crescer naquele lugar.
    LUGARES = {
        ".side-logo": "width: 100%",
        ".login-logo": "width: 100%",
        # O rodape e um flex, sem caixa de tamanho proprio: quem manda ali e a
        # altura reservada, e a largura acompanha.
        ".footer-marca img": "height: var(--logo-footer-h)",
    }

    def _regra(self, seletor: str) -> str:
        import re
        from pathlib import Path

        import nucleo

        css = (Path(nucleo.__file__).parent / "static" / "nucleo"
               / "mw5.css").read_text(encoding="utf-8")
        achado = re.search(r"(?m)^" + re.escape(seletor) + r"\s*\{([^}]*)\}", css)
        assert achado, f"a regra de `{seletor}` sumiu"
        return achado.group(1)

    def test_a_imagem_cresce_ate_a_caixa(self):
        for seletor, dimensao in self.LUGARES.items():
            regra = self._regra(seletor)
            assert dimensao in regra, (
                f"`{seletor}` nao manda a imagem crescer: com `{dimensao}` "
                f"faltando, um arquivo pequeno fica no tamanho natural")

    def test_nenhum_deles_volta_para_o_auto(self):
        """`width: auto` e o estado antigo: a imagem no tamanho do arquivo."""
        for seletor in self.LUGARES:
            regra = self._regra(seletor)
            assert "width: auto" not in regra or seletor == ".footer-marca img", (
                f"`{seletor}` voltou a deixar a largura no tamanho do arquivo")

    def test_a_proporcao_e_preservada(self):
        """Sem `contain`, crescer vira esticar — e um logo esticado e pior do
        que um logo pequeno."""
        for seletor in self.LUGARES:
            assert "object-fit: contain" in self._regra(seletor), (
                f"`{seletor}` cresce sem preservar a proporcao")

    def test_o_teto_da_caixa_continua(self):
        """Crescer nao pode virar vazar: a caixa reservada e o que mantem o
        layout igual para todo cliente."""
        for seletor in self.LUGARES:
            assert "max-width" in self._regra(seletor), (
                f"`{seletor}` perdeu o teto e o logo passa a empurrar o layout")


class TestContrasteDaMarca:
    """Cor escolhida no painel não pode deixar texto ilegível.

    A tela de Aparência (entrega 3) recusa a combinação no momento da escolha.
    O que se garante aqui é que a função que ela vai consultar diz a verdade
    para as cores que um cliente realmente escolheria.

    `test_text_over_primary_is_legible_in_both_modes`, já na suíte, cobre o
    mesmo par para UMA marca — a VetPlan. O que falta é a varredura: a cor vem
    de um seletor no painel, e o amarelo que alguém vai escolher amanhã nunca
    passou por teste nenhum.
    """

    #: Cores primárias plausíveis, do azul da MW5 ao verde do Sementes, mais
    #: dois extremos: um amarelo claríssimo e um quase-preto.
    CORES = [
        "#1e40af", "#276b2e", "#872d00", "#0f766e",
        "#b91c1c", "#facc15", "#f8fafc", "#111827",
    ]

    @pytest.mark.parametrize("modo", ["light", "dark"])
    @pytest.mark.parametrize("primaria", CORES)
    def test_o_texto_escolhido_para_a_primaria_e_legivel(self, primaria, modo):
        """`contrast_ratio` aceita string ou `Color` — aqui os tokens já são
        string, e envolvê-los em `Color(...)` seria erro: o construtor pede
        r, g, b separados. De hex se constrói com `Color.from_hex`."""
        tokens = Brand(client_name="Teste", primary=primaria).tokens(modo)
        assert contrast_ratio(tokens["primary"], tokens["on-primary"]) >= 4.5

    @pytest.mark.parametrize("modo", ["light", "dark"])
    @pytest.mark.parametrize("primaria", CORES)
    def test_o_texto_do_corpo_e_legivel_sobre_a_superficie(self, primaria, modo):
        tokens = Brand(client_name="Teste", primary=primaria).tokens(modo)
        assert contrast_ratio(tokens["surface"], tokens["on-surface"]) >= 7.0
