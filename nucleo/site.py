"""`Site` — o que uma tela precisa saber para se desenhar dentro do shell.

Uma tela recebe o `Site`, devolve o conteúdo do miolo e pronto: sidebar, header,
breadcrumb e rodapé são montados aqui. É esta classe que sustenta a regra de
nunca recriar header ou sidebar — a tela não tem como, porque não os constrói.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Sequence

from .permissoes import pode
from .components import Toast
from .layout import (
    Breadcrumb,
    Crumb,
    Footer,
    Header,
    NavItem,
    Page,
    Sidebar,
    UserInfo,
)
from .rendering import Renderable
from .theme.brand import Brand

__all__ = ["Site"]


@dataclass
class Site:
    """A configuração viva de um sistema gerado."""

    brand: Brand
    nav: Sequence[NavItem] = field(default_factory=list)
    home_href: str = "/"
    logout_href: str | None = "/sair"
    account_href: str = "/perfil"
    show_notifications: bool = True

    #: Folhas e scripts próprios do projeto, aplicados a todas as páginas.
    stylesheets: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)

    #: Caminho do CSS de tema. Só muda em cenário multi-marca, como a prévia
    #: do construtor de template.
    theme_href: str = "/static/theme.css"

    #: Recebe o usuário logado (ou None) e devolve o texto de contexto do meio
    #: do header — na VetPlan, a clínica e o credenciado ativos.
    context_line: Callable[[Any], Renderable] | None = None

    #: Decide se um item de menu aparece para este usuário.
    #:
    #: O padrão é a checagem real de permissão da camada de auth, e não um
    #: "mostra tudo": um projeto que declara `permission=` nos itens do menu
    #: espera que isso valha, e um padrão permissivo transforma esquecer de
    #: ligar a auth num vazamento silencioso de itens de menu.
    #:
    #: Item sem `permission` continua aparecendo para quem está logado — quem
    #: filtra o que fazer é a rota, com `Guarda.exigir`.
    can: Callable[[Any, str], bool] = staticmethod(pode)

    def page(
        self,
        *,
        title: str,
        content: Renderable,
        path: str = "/",
        crumbs: Sequence[Crumb] = (),
        user: Any = None,
        width: str = "wide",
        action_bar: Renderable = "",
        overlays: Renderable = "",
        toasts: Sequence[Toast] = (),
        chrome: bool = True,
        #: Arquivos que só esta página precisa. Acrescentados aos do site, não
        #: no lugar deles: o shell é o mesmo em toda tela, e uma página que
        #: carrega algo pesado — um recortador de imagem, por exemplo — não tem
        #: por que impor esse peso às outras.
        scripts: "Sequence[str]" = (),
        stylesheets: "Sequence[str]" = (),
    ) -> Page:
        """Monta a página inteira.

        `chrome=False` derruba sidebar, header e rodapé — é o que a tela de
        login usa, e a única situação em que o shell não se aplica.
        """
        return Page(
            brand=self.brand,
            title=title,
            content=content,
            width=width,
            action_bar=action_bar,
            overlays=overlays,
            toasts=list(toasts),
            stylesheets=[*self.stylesheets, *stylesheets],
            scripts=[*self.scripts, *scripts],
            theme_href=self.theme_href,
            sidebar=self.sidebar(path=path, user=user) if chrome else None,
            header=self.header(crumbs=crumbs, title=title, user=user) if chrome else None,
            footer=self.footer() if chrome else None,
        )

    # ---------- pedaços do shell ----------

    def sidebar(self, *, path: str = "/", user: Any = None) -> Sidebar:
        return Sidebar(
            items=self.visible_nav(path=path, user=user),
            logo=self.brand.assets.logo_for("sidebar"),
            logo_alt=self.brand.client_name,
            home_href=self.home_href,
        )

    def header(
        self,
        *,
        crumbs: Sequence[Crumb] = (),
        title: str = "",
        user: Any = None,
    ) -> Header:
        trail = list(crumbs) or ([Crumb(label=title)] if title else [])
        return Header(
            breadcrumb=Breadcrumb(crumbs=trail, home_href=self.home_href),
            context=self.context_line(user) if self.context_line else "",
            user=self._user_info(user),
            notifications=self.show_notifications,
            logout_href=self.logout_href,
        )

    def footer(self) -> Footer:
        rodape = self.brand.footer
        ano = str(date.today().year)
        return Footer(
            left_text=rodape.left_text,
            logo=self.brand.assets.logo_for("footer"),
            logo_alt=self.brand.client_name,
            # Resolvido aqui, e não no template: o ano é a única parte que não
            # pode ser literal, e quem escreve o texto não deveria precisar
            # saber que existe um lugar onde ele é trocado.
            right_text=rodape.right_text.replace("{ano}", ano),
        )

    def resolve_sistema(self, texto: str) -> str:
        """`{sistema}` no texto vira o nome do sistema.

        Mesmo mecanismo do `{ano}` do rodapé, acima: quem escreve o texto (no
        painel, ou na CLI) não deveria precisar saber que existe um lugar onde
        ele é trocado. Chamado tanto pela prévia quanto pelo módulo gerado —
        as duas têm um `Site` em mãos, então o texto sai igual dos dois lados.

        Sem `system_name` configurado, `client_name` serve de nome do sistema
        — o mesmo repasse que `ProjectSpec.title` já faz do lado do gerador.
        """
        sistema = self.brand.system_name or self.brand.client_name
        return texto.replace("{sistema}", sistema)

    def resolve_nome(self, texto: str, user: Any) -> str:
        """`{nome}` no texto vira o primeiro nome de quem está logado.

        Mesmo mecanismo do `{sistema}` acima e do `{ano}` do rodapé — a
        diferença é que este valor não vem da marca, vem de quem entrou, e por
        isso o método recebe o usuário em vez de lê-lo de `self.brand`. Um
        texto sem `{nome}` sai sem qualquer mudança: quem escreveu um "Bem-
        vindo(a)!" simples não precisa saber que a chave existe.
        """
        primeiro_nome = (getattr(user, "name", "") or "").split()
        return texto.replace("{nome}", primeiro_nome[0] if primeiro_nome else "")

    # ---------- menu ----------

    def visible_nav(self, *, path: str = "/", user: Any = None) -> list[NavItem]:
        """O menu filtrado por permissão e com o item da rota atual marcado.

        Um item que só existia para abrir os filhos some quando nenhum filho
        sobrou — seta abrindo para o vazio é o tipo de detalhe que faz o sistema
        parecer quebrado para quem tem acesso restrito.
        """
        return [
            marcado
            for item in self.nav
            if (marcado := self._prepare(item, path, user)) is not None
        ]

    def _prepare(self, item: NavItem, path: str, user: Any) -> NavItem | None:
        if item.permission and not self.can(user, item.permission):
            return None
        children = [
            prepared
            for child in item.children
            if (prepared := self._prepare(child, path, user)) is not None
        ]
        if item.children and not children:
            return None  # o pai só existia por causa dos filhos
        return NavItem(
            label=item.label,
            icon=item.icon,
            href=item.href,
            badge=item.badge,
            permission=item.permission,
            children=children,
            active=self._is_active(item.href, path),
        )

    @staticmethod
    def _is_active(href: str, path: str) -> bool:
        """A raiz só casa exata; as demais casam com as subrotas.

        Sem isso, "/" ficaria destacado em toda tela do sistema — e "/contratos"
        precisa continuar destacado em "/contratos/123/editar".
        """
        if not href or href == "#":
            return False
        if href == "/":
            return path == "/"
        return path == href or path.startswith(href.rstrip("/") + "/")

    def _user_info(self, user: Any) -> UserInfo | None:
        if user is None:
            return None
        if isinstance(user, UserInfo):
            return user
        return UserInfo(
            name=getattr(user, "display_name", None) or getattr(user, "name", "Usuário"),
            role=getattr(user, "role_label", None),
            avatar=getattr(user, "avatar", None),
            menu_href=self.account_href,
        )
