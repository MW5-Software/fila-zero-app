"""Os design tokens e como eles são derivados da identidade do cliente.

A calibração abaixo saiu da medição direta dos mocks da VetPlan. Os neutros de
lá não são cinzas puros: todos ficam no matiz ~275 (o mesmo do azul primário)
com croma baixíssimo, crescendo conforme se afastam do branco e do preto. É isso
que dá o ar "frio" do redesign. Derivando com essas mesmas constantes, um
cliente de marca verde ganha neutros levemente esverdeados e o sistema continua
parecendo desenhado de propósito, não recolorido às pressas.

Cores semânticas (ok/info/warn/danger) não derivam da marca: verde é sucesso e
vermelho é perigo independentemente do logo do cliente. Elas vêm com os valores
do mock e só mudam se alguém sobrescrever explicitamente.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .color import Color, legivel_sobre, mix, readable_on

if TYPE_CHECKING:  # pragma: no cover
    from .brand import Brand

Mode = Literal["light", "dark"]

# Nome do token -> (lightness, chroma) no matiz neutro. Medido dos mocks.
_NEUTRALS: dict[Mode, dict[str, tuple[float, float]]] = {
    "light": {
        "bg": (0.977, 0.005),
        "surface": (1.000, 0.000),
        "surface-2": (0.962, 0.008),
        "surface-3": (0.941, 0.011),
        "on-surface": (0.224, 0.014),
        "on-surface-2": (0.467, 0.025),
        "outline": (0.880, 0.017),
        "outline-2": (0.932, 0.012),
    },
    "dark": {
        "bg": (0.175, 0.015),
        "surface": (0.219, 0.016),
        "surface-2": (0.253, 0.019),
        "surface-3": (0.287, 0.022),
        "on-surface": (0.933, 0.011),
        "on-surface-2": (0.731, 0.025),
        "outline": (0.343, 0.027),
        "outline-2": (0.300, 0.024),
    },
}

# Como primary e accent se transformam em cada modo.
_PRIMARY_LIGHT_STRONG_DELTA = 0.085  # #1e40af -> #00288e
_PRIMARY_LIGHT_STRONG_CHROMA = 0.95
_PRIMARY_DARK_L = 0.751  # #93a8ff
_PRIMARY_DARK_CHROMA = 0.71
_PRIMARY_DARK_STRONG_L = 0.832  # #b8c4ff
_PRIMARY_DARK_STRONG_CHROMA = 0.46
_ACCENT_DARK_L = 0.836  # #872d00 -> #ffb59a
_ACCENT_DARK_CHROMA = 0.71

# Semânticos: valores do mock, iguais para qualquer marca.
_SEMANTIC: dict[Mode, dict[str, str]] = {
    "light": {
        "ok": "#0f7b4f",
        "ok-bg": "#dff3e8",
        "info": "#1e5fd6",
        "info-bg": "#dfe9ff",
        "warn": "#9a6400",
        "warn-bg": "#fdf0d5",
        "danger": "#ba1a1a",
        "danger-bg": "#ffe3e0",
    },
    "dark": {
        "ok": "#5fd39a",
        "ok-bg": "#12331f",
        "info": "#9cc0ff",
        "info-bg": "#152238",
        "warn": "#e8c07a",
        "warn-bg": "#33280f",
        "danger": "#ff9a90",
        "danger-bg": "#3a1512",
    },
}

_SHADOW: dict[Mode, str] = {
    "light": "0 1px 2px rgba(16,22,48,.06),0 4px 12px rgba(16,22,48,.05)",
    "dark": "0 1px 2px rgba(0,0,0,.4),0 4px 14px rgba(0,0,0,.35)",
}

#: Densidade: quanto ar a interface respira. Os valores de "normal" são os
#: medidos nos mocks da VetPlan. "Compacta" serve para telas de operação, onde
#: caber mais linhas na tela vale mais do que o conforto; "confortável" para
#: sistemas de uso esporádico, onde a pessoa não tem intimidade com a tela.
DENSITIES: dict[str, dict[str, str]] = {
    "compact": {
        "control-h": "38px",
        "button-h": "36px",
        "cell-pad-y": "6px",
        "card-pad": "16px",
        "grid-gap": "12px",
        "nav-item-pad": "7px 10px",
    },
    "normal": {
        "control-h": "44px",
        "button-h": "42px",
        "cell-pad-y": "9px",
        "card-pad": "20px",
        "grid-gap": "16px",
        "nav-item-pad": "9px 12px",
    },
    "comfortable": {
        "control-h": "50px",
        "button-h": "48px",
        "cell-pad-y": "13px",
        "card-pad": "26px",
        "grid-gap": "20px",
        "nav-item-pad": "11px 14px",
    },
}

#: Todo token que o design system garante existir. Componentes só podem usar
#: nomes desta lista — é o contrato que mantém tudo trocável de uma vez.
TOKEN_NAMES: tuple[str, ...] = (
    "font-display",
    "font-body",
    "primary",
    "primary-strong",
    "on-primary",
    "accent",
    "on-accent",
    "bg",
    "surface",
    "surface-2",
    "surface-3",
    "on-surface",
    "on-surface-2",
    "outline",
    "outline-2",
    "ok",
    "ok-bg",
    "info",
    "info-bg",
    "warn",
    "warn-bg",
    "danger",
    "danger-bg",
    "shadow",
    "radius",
    # --- estrutura: o que o construtor de template deixa ajustar ---
    "radius-control",
    "sidebar-w",
    "header-h",
    "footer-h",
    "control-h",
    "button-h",
    "cell-pad-y",
    "card-pad",
    "grid-gap",
    "nav-item-pad",
    "zebra",
    # --- tela de login: fundo e botão têm cor própria, editável ---
    "login-bg",
    "login-button",
    "on-login-button",
    "login-title",
    "login-subtitle",
    "login-tagline",
    "login-identifier-label",
    "login-identifier-hint",
    "login-password-label",
    "login-password-hint",
    "login-remember",
    "login-forgot",
    "login-support",
    "login-support-link",
    "login-field-bg",
    "login-field-border",
    "login-field-text",
    # --- faixa da logo na barra lateral: região própria, separada do menu ---
    "sidebar-brand-h",
    "sidebar-brand-pad",
    "sidebar-brand-bg",
    # --- área reservada ao logo em cada lugar onde ele aparece ---
    "logo-login-w",
    "logo-login-h",
    "logo-side-w",
    "logo-side-h",
    "logo-footer-w",
    "logo-footer-h",
    # --- cor própria por área; vazio herda do tema ---
    "sidebar-bg",
    "sidebar-text",
    "sidebar-hover-bg",
    "sidebar-hover-text",
    "sidebar-active-bg",
    "sidebar-active-text",
    "header-bg",
    "header-text",
    "content-bg",
    "footer-bg",
    "footer-text",
    "table-head-bg",
    "table-head-text",
    "chart-1", "chart-2", "chart-3", "chart-4",
    "chart-5", "chart-6", "chart-7", "chart-8",
)

#: Espaço reservado ao logo. A ALTURA é fixa de propósito: a imagem se ajusta
#: dentro dela, e não o contrário — assim o layout fica igual para todo cliente,
#: independentemente de o logo dele ser largo, quadrado ou alto.
#:
#: A largura da faixa lateral acompanha a barra em vez de ser um número solto.
#: Presa em 184px numa barra de 256, ela deixava 40px de folga sem uso: um logo
#: largo — que é a maioria — parava de crescer por causa desse teto e nunca
#: chegava a encostar na altura, ficando pequeno no meio de uma faixa alta. Os
#: 32px são o recheio horizontal da faixa, no `mw5.css`, dos dois lados.
#:
#: A `.side-logo` ainda tem `min(..., 100%)`: numa barra estreita quem manda é a
#: caixa, não a conta.
LOGO_AREAS: dict[str, str] = {
    "logo-login-w": "220px",
    "logo-login-h": "72px",
    "logo-side-w": "calc(var(--sidebar-w) - 32px)",
    "logo-side-h": "56px",
    "logo-footer-w": "110px",
    "logo-footer-h": "24px",
}

#: O respiro acima e abaixo da caixa do logo do rodapé — mesma conta da faixa
#: lateral, e pelo mesmo motivo: a altura acompanha a caixa em vez de ser um
#: número solto que um logo maior estoura.
_FOOTER_PAD = "20px"

#: O respiro acima e abaixo da caixa do logo na barra lateral. A altura da faixa
#: é uma conta a partir dele, e não um número solto: aumentar o logo não come a
#: folga. Essa mesma altura é a do cabeçalho, para que as duas linhas horizontais
#: sob a marca sejam uma linha só.
_SIDEBAR_BRAND_PAD = "24px"

#: O fundo da faixa é branco constante e não entra na configuração de cores.
#: Logo de cliente vem em PNG com fundo branco, em SVG com cor chapada, em versão
#: única sem variante para fundo escuro — sobre uma barra colorida, uma parte dos
#: clientes ficaria com um retângulo branco no meio da lateral e outra com o logo
#: sumindo. Fundo branco fixo é o único que serve para todos.
_SIDEBAR_BRAND_BG = "#ffffff"

#: Quantas cores de série a paleta oferece. Oito cobre qualquer gráfico de
#: gestão; acima disso a paleta cicla, e o gráfico já estava ilegível antes.
CHART_COLORS = 8

#: A claridade das séries em cada tema, e o croma mínimo. O croma existe para o
#: cliente de marca quase cinza não receber oito cinzas.
_CHART_L = {"light": 0.62, "dark": 0.72}
_CHART_CROMA_MINIMO = 0.11


def _interacao_do_menu(fundo: str, texto: str, ativo: str) -> dict[str, str]:
    """Hover e selecionado, derivados do fundo e do texto do menu.

    O fundo do hover é um passo do fundo do menu na direção do texto: sutil o
    bastante para não competir com o item selecionado, visível o bastante para
    responder ao mouse. Um passo maior para o selecionado, que precisa se
    sustentar sem o cursor em cima.

    Vai na direção do texto, e não "mais claro": num menu de fundo claro com
    texto escuro, clarear faria o hover sumir.
    """
    # O azul do item selecionado foi escolhido para o menu azul escuro padrão.
    # Num menu branco ele fica em 1.9 de contraste — ilegível. Ajustar a
    # claridade mantém a cor sendo aquela cor e a torna legível nos dois.
    ativo = legivel_sobre(fundo, ativo).hex
    return {
        "sidebar-hover-bg": mix(fundo, texto, 0.10).hex,
        "sidebar-hover-text": texto,
        "sidebar-active-bg": mix(fundo, ativo, 0.18).hex,
        "sidebar-active-text": ativo,
    }


def _paleta_de_graficos(brand: "Brand", mode: Mode, fundo: str) -> list[str]:
    """As cores de série: a da marca, e mais sete distribuídas pelo matiz.

    A secundária não entra. Série de gráfico precisa se distinguir da vizinha, e
    ancorar em duas cores de marca arbitrárias não garante isso — com a primária
    em 275° e a secundária em 45°, a terceira cor cairia em cima da segunda.
    Distribuir garante, e a paleta continua sendo a do cliente porque começa na
    cor dele e mantém o croma dele.
    """
    _, croma, matiz = Color.from_hex(brand.primary).to_oklch()
    croma = max(croma, _CHART_CROMA_MINIMO)
    passo = 360.0 / CHART_COLORS
    escolhidas = brand.chart_colors

    saida = []
    for i in range(CHART_COLORS):
        if i < len(escolhidas) and escolhidas[i]:
            saida.append(escolhidas[i])
            continue
        cor = Color.from_oklch(_CHART_L[mode], croma, (matiz + i * passo) % 360)
        # 3:1 é o mínimo do WCAG para objeto gráfico — uma barra é isso.
        saida.append(legivel_sobre(fundo, cor, minimo=3.0).hex)
    return saida


def build(brand: "Brand", mode: Mode) -> dict[str, str]:
    """Resolve todos os tokens para um modo, aplicando os overrides da marca."""
    primary = Color.from_hex(brand.primary)
    accent = Color.from_hex(brand.accent)
    hue = brand.neutral_hue if brand.neutral_hue is not None else primary.to_oklch()[2]

    tokens: dict[str, str] = {
        "font-display": brand.font_display,
        "font-body": brand.font_body,
        "radius": brand.radius,
        "radius-control": brand.radius_control,
        "shadow": _SHADOW[mode] if brand.shadows else "none",
        "sidebar-w": brand.sidebar_width,
        # A faixa alternada da tabela é um token e não uma classe para que
        # ligá-la e desligá-la seja só trocar uma cor por transparente.
        "zebra": "transparent",
    }
    tokens.update(DENSITIES[brand.density])
    tokens.update(LOGO_AREAS)
    tokens.update(brand.logo_areas)
    # Depois dos overrides da marca, e não antes: a faixa da logo não é
    # configurável, então nada que venha do formulário pode reescrevê-la. A
    # altura sai da caixa do logo já resolvida, com o respiro somado dos dois
    # lados — a folga fica igual seja qual for o tamanho da caixa.
    tokens["sidebar-brand-pad"] = _SIDEBAR_BRAND_PAD
    tokens["sidebar-brand-bg"] = _SIDEBAR_BRAND_BG
    tokens["sidebar-brand-h"] = (
        f"calc({tokens['logo-side-h']} + {_SIDEBAR_BRAND_PAD} * 2)"
    )
    # O topo tem a altura da faixa da logo, e não uma sua. Assim a linha embaixo
    # do logo e a linha embaixo do cabeçalho são a mesma linha, atravessando a
    # tela inteira — com alturas separadas, elas quase sempre desencontravam.
    tokens["header-h"] = tokens["sidebar-brand-h"]
    tokens["footer-h"] = f"calc({tokens['logo-footer-h']} + {_FOOTER_PAD} * 2)"

    if mode == "light":
        strong = primary.darken(_PRIMARY_LIGHT_STRONG_DELTA).scale_chroma(
            _PRIMARY_LIGHT_STRONG_CHROMA
        )
        tokens["primary"] = primary.hex
        tokens["primary-strong"] = strong.hex
        tokens["accent"] = accent.hex
    else:
        primary = primary.with_lightness(_PRIMARY_DARK_L).scale_chroma(
            _PRIMARY_DARK_CHROMA
        )
        strong = Color.from_hex(brand.primary).with_lightness(
            _PRIMARY_DARK_STRONG_L
        ).scale_chroma(_PRIMARY_DARK_STRONG_CHROMA)
        tokens["primary"] = primary.hex
        tokens["primary-strong"] = strong.hex
        tokens["accent"] = accent.with_lightness(_ACCENT_DARK_L).scale_chroma(
            _ACCENT_DARK_CHROMA
        ).hex

    # Texto que vai POR CIMA das cores de marca — no claro costuma ser branco;
    # no escuro elas clareiam tanto que passam a pedir texto escuro. Derivar em
    # vez de fixar é o que faz um selo continuar legível seja qual for a marca.
    tokens["on-primary"] = readable_on(
        tokens["primary"], light="#ffffff", dark=_deep_shade(brand.primary)
    ).hex
    tokens["on-accent"] = readable_on(
        tokens["accent"], light="#ffffff", dark=_deep_shade(brand.accent)
    ).hex

    for name, (lightness, chroma) in _NEUTRALS[mode].items():
        tokens[name] = Color.from_oklch(lightness, chroma, hue).hex

    if brand.zebra:
        tokens["zebra"] = tokens["surface-2"]

    # A tela de login pode ter fundo e botão próprios. Sem escolha explícita
    # ela segue o tema: fundo na superfície, botão na cor primária. Passar por
    # token — em vez de estilo inline no template — é o que mantém a promessa
    # de que nenhuma cor vive fora daqui.
    login_bg = brand.login.background
    tokens["login-bg"] = login_bg or tokens["surface"]
    tokens["login-button"] = brand.login.button_color or tokens["primary"]
    # Cada texto do login pode ter cor própria; vazio herda do tema, que é o
    # que mantém a tela coerente sem obrigar a escolher nove cores.
    # Cada texto do login tem cor própria. Vazio ainda cai no tema — o editor
    # sempre manda uma cor, mas um brand.yaml escrito à mão pode omitir.
    login = brand.login
    tokens["login-title"] = login.cor("title") or tokens["on-surface"]
    tokens["login-subtitle"] = login.cor("subtitle") or tokens["on-surface-2"]
    tokens["login-tagline"] = login.cor("tagline") or tokens["on-surface-2"]
    tokens["login-identifier-label"] = login.cor("identifier_label") or tokens["on-surface-2"]
    tokens["login-identifier-hint"] = login.cor("identifier_hint") or tokens["on-surface-2"]
    tokens["login-password-label"] = login.cor("password_label") or tokens["on-surface-2"]
    tokens["login-password-hint"] = login.cor("password_hint") or tokens["on-surface-2"]
    tokens["login-remember"] = login.cor("remember") or tokens["on-surface-2"]
    tokens["login-forgot"] = login.cor("forgot") or tokens["primary"]
    tokens["login-support"] = login.cor("support") or tokens["on-surface-2"]
    tokens["login-support-link"] = login.cor("support_link") or tokens["primary"]
    tokens["login-field-bg"] = login.field_bg or tokens["surface"]
    tokens["login-field-border"] = login.field_border or tokens["outline"]
    tokens["login-field-text"] = login.field_text or tokens["on-surface"]

    tokens["on-login-button"] = brand.login.button_text_color or readable_on(
        tokens["login-button"],
        light="#ffffff",
        dark=_deep_shade(tokens["login-button"]),
    ).hex

    tokens.update(_SEMANTIC[mode])

    for i, cor in enumerate(_paleta_de_graficos(brand, mode, tokens["surface"]), start=1):
        tokens[f"chart-{i}"] = cor

    # Cada área herda do tema, e só depois a escolha explícita entra. A ordem
    # importa: é ela que faz "não mexi nessa área" significar "segue o padrão".
    from .brand import AREA_FALLBACKS

    for area, origem in AREA_FALLBACKS.items():
        if not origem:
            continue   # calculada logo abaixo
        tokens[area] = origem if origem.startswith("#") else tokens[origem]

    # A escolha da pessoa entra ANTES do cálculo: as cores de interação saem do
    # menu que ela montou, não do menu padrão. Com a ordem invertida, escolher
    # um menu branco deixava o hover na cor calculada para o azul escuro.
    escolhidas = brand.areas.as_tokens()
    tokens.update(escolhidas)

    # Hover e selecionado, derivados do fundo e do texto finais. Assim trocar a
    # cor do menu não obriga a reajustar os dois à mão — e uma escolha
    # explícita continua ganhando, logo abaixo.
    #
    # Em hexadecimal, e não em `color-mix`: o seletor de cor do editor precisa
    # de um valor que ele saiba abrir, senão o campo aparece vazio.
    calculadas = _interacao_do_menu(tokens["sidebar-bg"], tokens["sidebar-text"],
                                    tokens["sidebar-active-text"])
    tokens.update(calculadas)
    tokens.update({k: v for k, v in escolhidas.items() if k in calculadas})

    tokens.update(brand.overrides.get(mode, {}))

    missing = set(TOKEN_NAMES) - set(tokens)
    if missing:  # pragma: no cover - proteção contra edição incompleta acima
        raise RuntimeError(f"tokens não resolvidos: {sorted(missing)}")
    return tokens


def _deep_shade(primary_hex: str) -> str:
    """Um tom bem escuro da marca, para texto sobre a primária clara do modo escuro."""
    return mix(Color.from_hex(primary_hex).with_lightness(0.22), "#000000", 0.15).hex
