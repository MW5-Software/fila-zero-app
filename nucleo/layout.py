"""O shell fixo: sidebar, header, footer e a página que os junta.

Esta é a parte que nenhum módulo recria. Uma tela do sistema declara o que vai
no miolo e mais nada — quem monta o resto é a `Page`. Foi a exigência mais dura
do briefing e também a mais fácil de furar sem querer, então o shell é montado
num lugar só e as telas nem recebem os pedaços para poder remontá-los.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from .components.containers import Alert, Dropdown, DropdownItem
from .components.primitives import Avatar, _validate
from .rendering import Component, Renderable
from .theme.brand import Brand

__all__ = [
    "Breadcrumb",
    "ContextLevel",
    "ContextOption",
    "ContextSwitcher",
    "Crumb",
    "Footer",
    "Header",
    "LoginPage",
    "NavItem",
    "Page",
    "PerfilPage",
    "Sidebar",
    "UserInfo",
]


@dataclass
class NavItem:
    """Um item do menu lateral.

    `permission` é só o nome da permissão exigida — quem decide se o usuário a
    tem é a camada de autenticação, na hora de montar o menu.
    """

    label: str
    #: Só o primeiro nível desenha ícone — é o que sobra na tela com a barra
    #: recolhida. Mais fundo ele não cabe, então o padrão é não ter.
    icon: str = ""
    href: str = "#"
    badge: str | None = None
    active: bool = False
    permission: str | None = None
    children: list["NavItem"] = field(default_factory=list)

    @property
    def has_active_child(self) -> bool:
        """Se a tela atual está em qualquer lugar abaixo deste item.

        Desce a árvore inteira, e não só os filhos diretos: com três níveis, o
        avô também precisa abrir, senão a pessoa chega numa tela e vê o menu
        fechado em cima do caminho que a trouxe até ali.
        """
        return any(child.active or child.has_active_child
                   for child in self.children)

    @property
    def is_open(self) -> bool:
        return self.active or self.has_active_child


@dataclass
class Crumb:
    label: str
    href: str | None = None


@dataclass
class Breadcrumb(Component):
    """O caminho no topo. O primeiro item é sempre a casinha do início."""

    template: ClassVar[str] = "layout/breadcrumb.html"

    crumbs: list[Crumb] = field(default_factory=list)
    home_href: str = "/"


@dataclass
class UserInfo:
    """O que o header precisa saber sobre quem está logado."""

    name: str
    role: str | None = None
    avatar: str | None = None
    #: Para onde vai "Meu Perfil". Vazio, e sem `menu` próprio, o avatar deixa
    #: de ser clicável — botão que abre menu vazio é pior do que enfeite.
    menu_href: str = "/perfil"
    #: O que aparece ao clicar no avatar. Um projeto acrescenta itens aqui
    #: (trocar senha, preferências) sem tocar no template do header.
    menu: list[DropdownItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.menu and self.menu_href:
            self.menu = [DropdownItem(label="Meu Perfil", icon="user",
                                      href=self.menu_href)]


@dataclass
class Sidebar(Component):
    template: ClassVar[str] = "layout/sidebar.html"

    items: list[NavItem] = field(default_factory=list)
    logo: str = ""
    logo_alt: str = ""
    home_href: str = "/"


@dataclass
class ContextOption:
    """Uma opção de troca de contexto."""

    value: str
    label: str


@dataclass
class ContextLevel:
    """Um nível do contexto: em que empresa, em que filial.

    Sem opções, o nível é texto: é o que o usuário comum vê, porque ele não
    escolhe — ele está onde está. Com opções, vira um seletor, que é a visão de
    quem administra e precisa entrar no lugar de outro para conferir o sistema
    como aquela pessoa o vê.
    """

    label: str
    value: str = ""
    name: str = ""
    options: list[ContextOption] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.options and not self.name:
            raise ValueError(
                f"o nível {self.label!r} tem opções mas não tem `name` — sem ele "
                f"a escolha não chega ao servidor"
            )


@dataclass
class ContextSwitcher(Component):
    """O contexto no meio do cabeçalho, um nível ao lado do outro.

    Os rótulos vêm da marca porque nem todo cliente chama as coisas de empresa e
    filial: uma rede chama de bandeira e loja, uma prestadora de contrato e
    posto. O componente não sabe o que os níveis significam.
    """

    template: ClassVar[str] = "layout/context_switcher.html"

    levels: list[ContextLevel] = field(default_factory=list)
    #: Para onde a troca é enviada. Vazio deixa os seletores sem efeito — é o
    #: estado do projeto recém-gerado, antes de existir de onde trocar.
    action: str = ""

    @property
    def switchable(self) -> bool:
        return any(level.options for level in self.levels)


@dataclass
class Header(Component):
    template: ClassVar[str] = "layout/header.html"

    breadcrumb: Breadcrumb | None = None
    context: Renderable = ""  # em que empresa e em que filial se está
    user: UserInfo | None = None
    #: O sino vem ligado: o canto direito é notificações, sair e o avatar.
    notifications: bool = True
    logout_href: str | None = "/sair"

    #: O id do menu do avatar. Fixo porque só existe um por página, e o
    #: `mw5.js` acha o menu por id a partir do gatilho.
    MENU_DO_USUARIO: ClassVar[str] = "mw5-menu-usuario"

    def template_context(self) -> dict[str, Any]:
        avatar = (
            Avatar(name=self.user.name, image=self.user.avatar) if self.user else None
        )
        return {"c": self, "avatar": avatar, "user_menu": self.user_menu()}

    def user_menu(self) -> "Dropdown | None":
        """O menu que abre no avatar, ou nada quando não há o que abrir."""
        if not self.user or not self.user.menu:
            return None
        return Dropdown(
            id=self.MENU_DO_USUARIO,
            title=self.user.name,
            items=list(self.user.menu),
        )


@dataclass
class Footer(Component):
    template: ClassVar[str] = "layout/footer.html"

    #: O canto esquerdo: um texto, ou o logo quando ele foi enviado.
    left_text: str = ""
    logo: str = ""
    logo_alt: str = ""
    #: O canto direito, texto livre. `{ano}` já vem resolvido daqui.
    right_text: str = ""


@dataclass
class Page(Component):
    """Um documento HTML completo com o shell montado em volta do conteúdo."""

    template: ClassVar[str] = "layout/page.html"

    brand: Brand = None  # type: ignore[assignment]
    title: str = ""
    content: Renderable = ""
    sidebar: Sidebar | None = None
    header: Header | None = None
    footer: Footer | None = None
    width: str = "wide"  # wide | narrow | full
    action_bar: Renderable = ""
    overlays: Renderable = ""  # modais, drawers e dropdowns vão soltos no fim
    toasts: Renderable = ""
    body_class: str = ""

    #: Folhas e scripts próprios do projeto, carregados depois dos do design
    #: system. É o ponto de extensão para o que é específico de um cliente —
    #: sem ele, a alternativa seria estilo inline espalhado pelas telas, que é
    #: exatamente o que o design system existe para evitar.
    stylesheets: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)

    #: De onde vem o CSS de tema. Parametrizável porque nem sempre há um tema só
    #: por aplicação: o construtor de template renderiza a prévia de OUTRA marca
    #: dentro do próprio painel, e sem isto a prévia herdaria as cores erradas.
    theme_href: str = "/static/theme.css"

    def __post_init__(self) -> None:
        if self.brand is None:
            raise ValueError("Page precisa de um Brand — é dele que sai todo o tema")
        _validate(self.width, ("wide", "narrow", "full"), "width", "Page")

    @property
    def document_title(self) -> str:
        system = self.brand.system_name or self.brand.client_name
        return f"{self.title} — {system}" if self.title else system

    @property
    def main_classes(self) -> str:
        parts = ["is-wide" if self.width == "wide" else ""]
        if self.width == "narrow":
            parts = ["is-narrow"]
        if self.action_bar:
            parts.append("has-actionbar")
        return " ".join(p for p in parts if p)


@dataclass
class LoginPage(Component):
    """A tela de entrada.

    É a única do sistema fora do shell, e por isso a única que precisa da marca
    por inteiro em vez de só dos tokens: logo grande, imagem institucional e os
    textos que o cliente escolheu. Os campos vêm de fora porque variam — a
    VetPlan pede clínica, usuário e senha; outro cliente pede só e-mail e senha.
    """

    template: ClassVar[str] = "layout/login.html"

    brand: Brand = None  # type: ignore[assignment]
    fields: Renderable = ""
    action: str = "/entrar"
    error: str | None = None
    theme_href: str = "/static/theme.css"
    stylesheets: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.brand is None:
            raise ValueError("LoginPage precisa de um Brand")
        if not self.fields:
            self.fields = self.campos_da_marca()

    def campos_da_marca(self) -> list[Renderable]:
        """Monta os campos declarados no `brand.yaml`, na ordem certa.

        Os dois campos obrigatórios ficam no meio; os extras entram nas posições
        que declararam. Quem precisar de um formulário que o editor não descreve
        passa `fields` e ignora tudo isto.
        """
        from .components.forms import TextInput

        login = self.brand.login

        def montar(campo) -> TextInput:
            return TextInput(
                name=campo.name,
                label=campo.label,
                placeholder=campo.placeholder,
                type=campo.type,
                required=campo.required,
            )

        campos: list[Renderable] = [montar(f) for f in login.fields_at("antes")]
        campos.append(
            TextInput(
                name="usuario",
                label=login.identifier_label,
                placeholder=login.identifier_placeholder,
                required=True,
                autocomplete="username",
            )
        )
        campos += [montar(f) for f in login.fields_at("apos-usuario")]
        campos.append(
            TextInput(
                name="senha",
                label=login.password_label,
                placeholder=login.password_placeholder,
                type="password",
                required=True,
                autocomplete="current-password",
            )
        )
        campos += [montar(f) for f in login.fields_at("apos-senha")]
        return campos

    @property
    def document_title(self) -> str:
        system = self.brand.system_name or self.brand.client_name
        return f"{self.brand.login.title} — {system}"

    @property
    def error_alert(self) -> "Alert | str":
        return Alert(message=self.error, tone="danger") if self.error else ""


@dataclass
class PerfilPage(Component):
    """O corpo da tela Meu Perfil: a foto e a senha.

    Aqui, e não no módulo gerado, porque a prévia do painel desenha esta mesma
    tela. Escrita nos dois lugares ela diverge, e aí o painel promete uma coisa
    e o cliente recebe outra — é o motivo de o `LoginPage` existir também.

    `troca_de_senha` é booleano de propósito: este componente desenha, não
    decide. Quem pergunta ao backend se ele sabe trocar senha é quem monta a
    rota, e assim isto se testa sem backend nenhum.
    """

    template: ClassVar[str] = "layout/perfil.html"

    user: Any = None
    troca_de_senha: bool = False
    titulo: str = "Meu Perfil"
    subtitulo: str = ""
    rotulo_foto: str = "Foto"
    ajuda_foto: str = ""
    rotulo_senha: str = "Senha"
    acao_foto: str = "/perfil/foto"
    acao_senha: str = "/perfil/senha"
    erro: str = ""
    ok: str = ""

    def __post_init__(self) -> None:
        if self.user is None:
            raise ValueError("PerfilPage precisa de um usuário")

    def template_context(self) -> "dict[str, Any]":
        return {
            "c": self,
            "avatar": Avatar(name=self.user.name,
                             image=getattr(self.user, "avatar", "") or None),
            "erro_alert": Alert(message=self.erro, tone="danger") if self.erro else "",
            "ok_alert": Alert(message=self.ok, tone="ok") if self.ok else "",
            "campos_senha": self.campos_da_senha(),
        }

    def campos_da_senha(self) -> "list[TextInput]":
        """Os três campos da troca de senha, ou nenhum quando a seção não existe.

        Componentes, e não marcação escrita à mão: `TextInput` já sabe as
        classes certas de campo e rótulo, e repeti-las aqui seria o mesmo erro
        que este componente inteiro existe para evitar.
        """
        from .permissoes import SENHA_MINIMA
        from .components.forms import TextInput

        if not self.troca_de_senha:
            return []
        return [
            TextInput(name="senha_atual", label="Senha atual", type="password",
                      required=True, span=12, autocomplete="current-password"),
            TextInput(name="senha_nova", label="Senha nova", type="password",
                      required=True, span=6, autocomplete="new-password",
                      help=f"Mínimo de {SENHA_MINIMA} caracteres."),
            TextInput(name="senha_confirma", label="Repita a senha nova",
                      type="password", required=True, span=6,
                      autocomplete="new-password"),
        ]
