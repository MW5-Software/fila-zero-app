"""`Brand` — a identidade visual inteira de um cliente, num objeto só.

Este é o único lugar do sistema onde uma cor, uma fonte ou um caminho de logo
pode ser escrito. Se um componente ou template de projeto precisar de um hex
literal, é sinal de que falta um token — e o certo é acrescentar o token, não
abrir exceção.

Na prática cada projeto gerado tem um `brand.yaml` e trocar o cliente inteiro de
cara é editar esse arquivo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml

from . import tokens as _tokens
from .color import Color

ThemePreference = Literal["system", "light", "dark"]

#: Medida CSS aceita nos campos de estrutura. Restrito de propósito: o valor vai
#: direto para dentro do CSS gerado, então nada além de número + unidade entra.
_CSS_LENGTH = re.compile(r"\d+(\.\d+)?(px|rem|em|%|vw|vh)")

FONT_DISPLAY = '"Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif'
FONT_BODY = 'Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif'

#: Pares de fonte oferecidos no construtor.
#:
#: Todos terminam em pilha do sistema de propósito: nenhum arquivo de fonte é
#: baixado de fora, então o sistema abre igual sem internet e sem depender de
#: CDN. Se a primeira fonte do par estiver instalada na máquina, ela aparece;
#: senão cai para a do sistema, que já é boa. Para uma fonte própria do cliente,
#: coloque o arquivo em `static/brand/` e declare a `@font-face` no CSS do
#: projeto — o `stylesheets` do Site existe para isso.
FONT_PAIRS: dict[str, tuple[str, str, str]] = {
    "padrao": (
        "Padrão MW5 (Jakarta + Inter)",
        FONT_DISPLAY,
        FONT_BODY,
    ),
    "sistema": (
        "Fonte do sistema",
        'system-ui,-apple-system,"Segoe UI",Roboto,sans-serif',
        'system-ui,-apple-system,"Segoe UI",Roboto,sans-serif',
    ),
    "classica": (
        "Clássica (títulos serifados)",
        'Georgia,"Times New Roman",serif',
        'system-ui,-apple-system,"Segoe UI",Roboto,sans-serif',
    ),
    "tecnica": (
        "Técnica (títulos monoespaçados)",
        'ui-monospace,"Cascadia Mono",Menlo,Consolas,monospace',
        'system-ui,-apple-system,"Segoe UI",Roboto,sans-serif',
    ),
}


#: Onde o logo aparece. Cada lugar tem o seu, e não há um logo "geral": a marca
#: que cabe num cartão de login de 220px não é a mesma que cabe numa faixa de
#: 34px na barra lateral — quase toda empresa tem uma versão reduzida.
LUGARES_DO_LOGO = ("login", "sidebar", "footer")

#: Onde um logo ausente ganha um provisório. No rodapé não: lá o logo é uma
#: alternativa ao texto, e um provisório apagaria o texto que a pessoa escreveu.
LUGARES_COM_PROVISORIO = ("login", "sidebar")


@dataclass(frozen=True)
class Assets:
    """Imagens da marca, servidas a partir de `static/brand/`."""

    login_logo: str = ""
    sidebar_logo: str = ""
    footer_logo: str = ""
    favicon: str | None = None
    institutional_image: str | None = None

    def logo_for(self, lugar: str) -> str:
        """O logo de um lugar. Vazio quando não foi enviado — o template decide
        o que fazer, em vez de cair no logo de outro lugar."""
        if lugar not in LUGARES_DO_LOGO:
            raise ValueError(
                f"lugar de logo inválido: {lugar!r} — use um de "
                f"{', '.join(LUGARES_DO_LOGO)}"
            )
        return getattr(self, f"{lugar}_logo") or ""


#: Onde um campo extra entra no formulário de login. Os nomes descrevem a
#: posição em relação aos dois campos que todo login tem.
POSICOES_CAMPO = ("antes", "apos-usuario", "apos-senha")


@dataclass(frozen=True)
class LoginField:
    """Um campo além dos dois obrigatórios.

    Existe porque "usuário e senha" não serve a todo cliente: a VetPlan pede o
    código da clínica antes do usuário, e um portal com múltiplas empresas pede
    o CNPJ. A posição é declarada em vez de deduzida da ordem da lista para que
    reordenar no editor não dependa de arrastar nada.
    """

    name: str
    label: str
    placeholder: str = ""
    type: str = "text"
    position: str = "antes"
    required: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("campo de login sem nome")
        if self.position not in POSICOES_CAMPO:
            raise ValueError(
                f"posição {self.position!r} inválida — use uma de "
                f"{', '.join(POSICOES_CAMPO)}"
            )


@dataclass(frozen=True)
class LoginBrand:
    """A tela de login inteira, do fundo ao texto de suporte.

    Tudo aqui é editável porque o login é a primeira tela que o cliente vê e a
    que ele mais quer chamar de sua — e porque é a única do sistema que não usa
    o shell, então não há um layout comum para segurá-la no lugar.
    """

    title: str = "Acessar Painel"
    subtitle: str | None = None
    tagline: str | None = None
    separator: str = ""

    #: Fundo da tela. Vazio usa a superfície do tema (branco no modo claro).
    background: str | None = None

    # os dois campos que todo login tem
    identifier_label: str = "Usuário"
    identifier_placeholder: str = "Seu usuário"
    password_label: str = "Senha"
    password_placeholder: str = "Sua senha"

    #: Campos além dos dois de cima, cada um com sua posição.
    extra_fields: tuple[LoginField, ...] = ()

    show_remember: bool = True
    remember_label: str = "Manter conectado"

    show_forgot: bool = True
    forgot_label: str = "Esqueceu a senha?"
    forgot_url: str = "#"

    submit_label: str = "Entrar"
    #: Cor do botão. Vazio usa a cor primária da marca.
    button_color: str | None = None
    #: Cor do texto do botão. Vazio deriva a partir da cor do botão, escolhendo
    #: entre claro e escuro pelo contraste — que é quase sempre o que se quer.
    button_text_color: str | None = None

    support_text: str = "Problemas para entrar?"
    support_label: str = "Fale com o suporte"
    support_url: str = "#"

    # --- a cor de cada texto da tela, um por um ---
    title_color: str | None = None
    subtitle_color: str | None = None
    tagline_color: str | None = None
    identifier_label_color: str | None = None
    identifier_hint_color: str | None = None
    password_label_color: str | None = None
    password_hint_color: str | None = None
    remember_color: str | None = None
    forgot_color: str | None = None
    support_color: str | None = None
    support_link_color: str | None = None

    # --- a caixa do campo, que não é texto ---
    field_bg: str | None = None
    field_border: str | None = None
    field_text: str | None = None

    #: Todo campo de cor desta classe, para validar num lugar só.
    CORES: ClassVar[tuple[str, ...]] = (
        "background", "button_color", "button_text_color",
        "title_color", "subtitle_color", "tagline_color",
        "identifier_label_color", "identifier_hint_color",
        "password_label_color", "password_hint_color",
        "remember_color", "forgot_color", "support_color", "support_link_color",
        "field_bg", "field_border", "field_text",
    )

    def cor(self, nome: str) -> str | None:
        """A cor de um texto pelo nome do token, sem o prefixo `login-`."""
        return getattr(self, f"{nome}_color", None)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "extra_fields",
            tuple(
                f if isinstance(f, LoginField) else LoginField(**f)
                for f in self.extra_fields
            ),
        )
        for campo in self.CORES:
            valor = getattr(self, campo)
            if not valor:
                continue
            try:
                Color.from_hex(valor)
            except ValueError:
                raise ValueError(
                    f"login.{campo}={valor!r} não é uma cor hexadecimal válida"
                ) from None

    def fields_at(self, position: str) -> tuple[LoginField, ...]:
        return tuple(f for f in self.extra_fields if f.position == position)


@dataclass(frozen=True)
class HeaderBrand:
    """O contexto no meio do cabeçalho: onde a pessoa está trabalhando.

    Os rótulos são configuráveis porque nem todo cliente chama as coisas de
    empresa e filial — uma rede diz bandeira e loja, uma prestadora diz contrato
    e posto. Guardamos os rótulos, e não os valores: os valores vêm dos dados do
    projeto, não da identidade visual.
    """

    show_context: bool = True
    context_labels: tuple[str, ...] = ("Empresa", "Filial")

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_labels", tuple(self.context_labels))
        if self.show_context and not any(r.strip() for r in self.context_labels):
            raise ValueError(
                "o contexto do cabeçalho está ligado mas sem nenhum rótulo — "
                "desligue-o em vez de deixá-lo vazio"
            )


#: As áreas que podem ter cor própria e o que cada uma vale quando nada é
#: escolhido — o nome de um token, para herdar dele, ou uma cor literal, para a
#: área que tem um padrão próprio.
#:
#: Herdar mantém o sistema parecendo um sistema só: mexer numa área é uma
#: decisão, não uma obrigação. O menu é a exceção, e de propósito: ele nasce
#: azul escuro com texto branco porque é assim que o padrão da casa começa. As
#: três cores continuam configuráveis como qualquer outra.
AREA_FALLBACKS: dict[str, str] = {
    "sidebar-bg": "#28467d",
    "sidebar-text": "#ffffff",
    # As quatro de interação. Ficam vazias aqui porque não são literais: são
    # calculadas em `tokens.py` a partir do fundo e do texto escolhidos, para
    # que trocar a cor do menu não exija reajustar hover e selecionado à mão.
    "sidebar-active-text": "#95bbff",
    "sidebar-hover-bg": "",
    "sidebar-hover-text": "",
    "sidebar-active-bg": "",
    "header-bg": "surface",
    "header-text": "on-surface-2",
    "content-bg": "bg",
    # Branco por padrão: o rodapé fecha a página, e sobre o fundo cinza da
    # área de trabalho ele desaparecia num degrau de contraste quase nulo.
    "footer-bg": "surface",
    "footer-text": "on-surface-2",
    "table-head-bg": "surface-2",
    "table-head-text": "on-surface-2",
}


@dataclass(frozen=True)
class AreaColors:
    """Cor própria de cada área do sistema.

    Campo vazio herda do tema — e é assim que quase tudo fica. Preencher é para
    o caso do cliente que quer a barra lateral escura enquanto o resto é claro,
    ou o cabeçalho na cor da marca.
    """

    sidebar_bg: str | None = None
    sidebar_text: str | None = None
    sidebar_hover_bg: str | None = None
    sidebar_hover_text: str | None = None
    sidebar_active_bg: str | None = None
    sidebar_active_text: str | None = None
    header_bg: str | None = None
    header_text: str | None = None
    content_bg: str | None = None
    footer_bg: str | None = None
    footer_text: str | None = None
    table_head_bg: str | None = None
    table_head_text: str | None = None

    def __post_init__(self) -> None:
        for campo in self.__dataclass_fields__:
            valor = getattr(self, campo)
            if not valor:
                continue
            try:
                Color.from_hex(valor)
            except ValueError:
                raise ValueError(
                    f"areas.{campo}={valor!r} não é uma cor hexadecimal válida"
                ) from None

    def as_tokens(self) -> dict[str, str]:
        """Só o que foi escolhido; o resto o tema resolve."""
        return {
            campo.replace("_", "-"): valor
            for campo in self.__dataclass_fields__
            if (valor := getattr(self, campo))
        }


@dataclass(frozen=True)
class FooterBrand:
    """Os dois cantos do rodapé.

    Texto livre dos dois lados porque o que vai ali muda por cliente e por
    contrato: o nome de quem desenvolveu, a versão, um aviso legal, um telefone
    de suporte. Campos com nome fixo — "empresa", "sufixo", "versão" — só
    produziam campos que a maioria dos projetos deixava em branco.

    `{ano}` no texto vira o ano corrente. É a única parte que não pode ser
    literal: escrita à mão, ela envelhece na virada do ano sem ninguém notar.
    """

    left_text: str = "MW5"
    right_text: str = "© {ano} MW5 · Todos os direitos reservados"


@dataclass(frozen=True)
class Brand:
    client_name: str
    system_name: str | None = None
    primary: str = "#1e40af"
    accent: str = "#872d00"
    neutral_hue: float | None = None
    font_display: str = FONT_DISPLAY
    font_body: str = FONT_BODY
    radius: str = "12px"
    default_theme: ThemePreference = "system"

    # --- estrutura, editável no construtor de template ---
    radius_control: str = "9px"
    density: str = "normal"  # compact | normal | comfortable
    sidebar_width: str = "256px"
    shadows: bool = True
    zebra: bool = False  # faixa alternada nas linhas da tabela

    #: Sobrescreve o espaço reservado ao logo, quando a marca do cliente pede
    #: uma proporção fora do comum (um brasão alto, por exemplo).
    logo_areas: dict[str, str] = field(default_factory=dict)
    footer: FooterBrand = field(default_factory=FooterBrand)
    assets: Assets = field(default_factory=Assets)
    login: LoginBrand = field(default_factory=LoginBrand)
    header: HeaderBrand = field(default_factory=HeaderBrand)
    areas: AreaColors = field(default_factory=AreaColors)
    #: As cores de série dos gráficos. Vazio é o caso normal: elas são
    #: derivadas da primária, distribuídas pelo círculo de matiz. Preencher é
    #: para o cliente que manda na paleta.
    chart_colors: tuple[str, ...] = ()
    overrides: dict[str, dict[str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.client_name.strip():
            raise ValueError("brand.client_name não pode ser vazio")
        # As cores são validadas aqui, e não na hora de derivar os tokens, para
        # que construir um Brand inválido falhe no ponto onde o erro nasceu.
        # Adiar isso fazia um hex incompleto escapar de quem tentava capturá-lo.
        for campo in ("primary", "accent"):
            try:
                Color.from_hex(getattr(self, campo))
            except ValueError:
                raise ValueError(
                    f"brand.{campo}={getattr(self, campo)!r} não é uma cor "
                    f"hexadecimal válida (ex.: '#1e40af')"
                ) from None
        object.__setattr__(self, "chart_colors", tuple(self.chart_colors))
        for i, valor in enumerate(self.chart_colors, start=1):
            if not valor:
                continue   # posição em branco segue automática
            try:
                Color.from_hex(valor)
            except ValueError:
                raise ValueError(
                    f"brand.chart_colors[{i - 1}]={valor!r} não é uma cor "
                    f"hexadecimal válida (ex.: '#1e40af')"
                ) from None
        if self.default_theme not in ("system", "light", "dark"):
            raise ValueError(
                f"default_theme deve ser system, light ou dark — recebido {self.default_theme!r}"
            )
        if self.density not in _tokens.DENSITIES:
            raise ValueError(
                f"density deve ser um de {', '.join(_tokens.DENSITIES)} — "
                f"recebido {self.density!r}"
            )
        for campo in ("radius", "radius_control", "sidebar_width"):
            valor = getattr(self, campo)
            if not _CSS_LENGTH.fullmatch(str(valor)):
                raise ValueError(
                    f"{campo}={valor!r} precisa ser uma medida CSS, como '12px' ou '1rem'"
                )
        desconhecidas = set(self.logo_areas) - set(_tokens.LOGO_AREAS)
        if desconhecidas:
            raise ValueError(
                f"logo_areas só aceita {', '.join(sorted(_tokens.LOGO_AREAS))} — "
                f"veio {sorted(desconhecidas)}"
            )
        for nome, valor in self.logo_areas.items():
            if not _CSS_LENGTH.fullmatch(str(valor)):
                raise ValueError(
                    f"logo_areas[{nome!r}]={valor!r} precisa ser uma medida CSS"
                )
        unknown = {
            name
            for mode in self.overrides.values()
            for name in mode
            if name not in _tokens.TOKEN_NAMES
        }
        if unknown:
            raise ValueError(
                f"overrides citam tokens inexistentes: {sorted(unknown)}. "
                f"Tokens válidos: {', '.join(_tokens.TOKEN_NAMES)}"
            )
        bad_modes = set(self.overrides) - {"light", "dark"}
        if bad_modes:
            raise ValueError(f"overrides só aceita 'light' e 'dark' — veio {sorted(bad_modes)}")

    # ---------- tokens ----------

    def tokens(self, mode: str = "light") -> dict[str, str]:
        if mode not in ("light", "dark"):
            raise ValueError(f"modo inválido: {mode!r}")
        return _tokens.build(self, mode)  # type: ignore[arg-type]

    def with_overrides(self, mode: str, **values: str) -> "Brand":
        merged = {m: dict(v) for m, v in self.overrides.items()}
        merged.setdefault(mode, {}).update(values)
        return replace(self, overrides=merged)

    # ---------- carregamento ----------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Brand":
        data = dict(data)
        nested = {
            "footer": FooterBrand,
            "assets": Assets,
            "login": LoginBrand,
            "header": HeaderBrand,
            "areas": AreaColors,
        }
        for key, factory in nested.items():
            value = data.get(key)
            if value is None:
                data.pop(key, None)
                continue
            if not isinstance(value, dict):
                raise ValueError(f"brand.{key} precisa ser um mapa, veio {type(value).__name__}")
            unknown = set(value) - {f.name for f in factory.__dataclass_fields__.values()}
            if unknown:
                raise ValueError(f"brand.{key} tem campos desconhecidos: {sorted(unknown)}")
            data[key] = factory(**value)

        unknown = set(data) - {f.name for f in cls.__dataclass_fields__.values()}
        if unknown:
            raise ValueError(
                f"brand.yaml tem campos desconhecidos: {sorted(unknown)}"
            )
        return cls(**data)

    @classmethod
    def from_yaml(cls, path: "str | Path") -> "Brand":
        path = Path(path)
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"brand.yaml não encontrado em {path} — todo projeto precisa de um"
            ) from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{path} deveria conter um mapa no topo")
        return cls.from_dict(raw)
