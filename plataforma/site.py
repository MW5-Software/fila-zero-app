"""O `Site` que toda tela deste projeto monta.

`nucleo.site.Site` nasce de novo em cada requisição — nunca mutado como um
global de módulo (ver o comentário de `nucleo/views.py`). Isso fez a mesma
construção (`brand=marca_da_requisicao(request)`, `nav=montar(request.usuario)`,
`theme_href="/tema.css"`) se repetir, igual, em oito lugares diferentes —
`contas/views_perfil.py`, a extinta tela de Perfis, `contas/views_usuarios.py`,
`plataforma/views.py` (duas vezes), `nucleo/views.py` (duas vezes) e
`modulos/exemplo/views.py`. `montar_site` é o lugar único: uma tela nova
chama, e não copia.

É também onde `Site.context_line` entra — o único jeito de o cabeçalho
mostrar a faixa de empresa/filial, e o motivo de existir este módulo agora,
com a chegada de `Filial`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from django.urls import reverse

from comum.estaticos import versionado
from nucleo.layout import ContextLevel, ContextOption, ContextSwitcher
from nucleo.site import Site

from .contexto import CHAVE, CHAVE_EMPRESA, niveis_de_contexto
from .marca import FOLHA_DA_CASA, NOME_DO_PRODUTO, marca_da_requisicao
from .menu import montar

if TYPE_CHECKING:
    from nucleo.permissoes import NivelDeContexto
    from nucleo.rendering import Renderable
    from nucleo.theme import Brand

__all__ = ["construir_context_switcher", "montar_site"]


def construir_context_switcher(
    marca: "Brand", niveis: "list[NivelDeContexto]", *, da_mw5: bool = False,
) -> "Renderable":
    """O `ContextSwitcher` do cabeçalho, a partir do nível de
    `plataforma.contexto.niveis_de_contexto`.

    **Até dois níveis, a empresa e a filial**, cada um só quando há o que
    escolher (`plataforma.contexto.niveis_de_contexto`).

    Função pura, à parte de `montar_site`, de propósito: testar "os rótulos
    seguem `Brand.context_labels`" não devia exigir subir sessão, banco nem
    `request` nenhum — só um `Brand` e uma lista de níveis.

    O rótulo vem de `marca.header.context_labels` — nunca de `nivel.rotulo`,
    que só carrega o nome genérico — porque é a marca quem sabe se este
    cliente troca os nomes.

    **Com uma exceção: a MW5** (`da_mw5`). A marca diz como o CLIENTE chama as
    coisas dele, e a MW5 não está dentro de cliente nenhum: para ela o nível 0
    não é "em que empresa estou trabalhando", é "qual conta estou olhando", e
    aí vale o rótulo do nível. Desde 17/09/2026 o seletor existe também para o
    titular com várias empresas, e para ele a marca continua mandando.
    """
    if not marca.header.show_context:
        # A mesma leitura que `Header.context` já faz de uma string vazia
        # (`{% if c.context %}` em `nucleo/templates/layout/header.html`):
        # devolver "" é o suficiente para a faixa inteira sumir.
        return ""

    # **Lista vazia é resposta, não erro** (09/09/2026). Quem alcança uma
    # empresa e uma filial não tem o que trocar, e é a maioria. Sem esta linha
    # era `IndexError` na primeira página que essa pessoa abrisse.
    if not niveis:
        return ""

    rotulos = marca.header.context_labels
    levels = []
    for nivel in niveis:
        # O nível diz o que é (0 empresa, 1 filial); a marca diz como o
        # cliente chama. O `name` é a mesma constante que a rota de troca lê.
        indice, nome = ((0, CHAVE_EMPRESA) if nivel.nivel == 0
                        else (1, CHAVE))
        da_marca = rotulos[indice] if len(rotulos) > indice else ""
        rotulo = nivel.rotulo if (da_mw5 and indice == 0) or not da_marca \
            else da_marca
        levels.append(ContextLevel(
            label=rotulo, value=nivel.atual, name=nome,
            options=[ContextOption(o.valor, o.rotulo) for o in nivel.opcoes],
        ))

    # **Um formulário só para os dois níveis** (o do design system): os dois
    # selects viajam juntos para UMA `action`. Com a empresa presente, é a
    # rota da empresa, que repassa para a de filial quando a empresa não mudou
    # (`views_empresa_contexto.empresa_trocar`).
    tem_empresa = any(nivel.nivel == 0 for nivel in niveis)
    return ContextSwitcher(
        levels=levels,
        action=reverse("empresa_trocar" if tem_empresa else "filial_trocar"),
    )


@dataclass
class SiteDoProduto(Site):
    """O `Site` desta casa: o rodapé e o cabeçalho.

    O design system dá ao logo do rodapé o `alt` do nome do cliente, e para
    os outros dois lugares isso está certo: lá o logo É o do cliente. No
    rodapé o logo é o do PRODUTO e não troca (ver `LUGARES_DA_IMAGEM` em
    `plataforma/models.py`), então anunciar "Sementes Premix" a quem usa
    leitor de tela seria descrever a imagem errada — a única pessoa que
    depende do `alt` receberia a informação falsa.

    Subclasse aqui, e não emenda no `nucleo`: o design system é porte
    verbatim, e esta é uma regra do KRONOS, não dele.
    """

    #: A requisição desta página. O `Site` do design system não conhece o
    #: Django de propósito — quem precisa dele é esta casa, para o seletor de
    #: idioma poder emitir o token CSRF do formulário dele.
    pedido: Any = None

    def header(self, **argumentos):
        """O cabeçalho da casa: o do design system, com o seletor de idioma.

        `replace` sobre o que o pai montou, e não um `Header` novo: os cinco
        campos que ele preenche (trilha, contexto, usuário, sino, sair) são
        decisão DELE, e recriá-los aqui seria a segunda cópia da mesma regra.
        """
        from .header import HeaderDaCasa
        from .idioma_no_cabecalho import seletor

        base = super().header(**argumentos)
        return HeaderDaCasa(
            breadcrumb=base.breadcrumb, context=base.context, user=base.user,
            notifications=base.notifications,
            # **Sem o ícone solto de sair** (18/09/2026): ele era o quarto
            # ícone do canto, o único sem rótulo escrito e o único que
            # derruba a sessão de quem clica sem querer. O "Sair" desceu para
            # o menu do avatar (`_user_info`), onde tem nome, cor de perigo e
            # um clique a mais na frente. `Site.logout_href` continua sendo o
            # endereço, e é de lá que o item do menu o lê.
            logout_href=None,
            idioma=seletor(self.pedido))

    def _user_info(self, user):
        """O `UserInfo` do cabeçalho, com o menu do avatar em português ou
        castelhano.

        O `nucleo` monta esse item sozinho quando ninguém passa `menu`, e o
        rótulo dele é fixo em português — mas o próprio componente diz, no
        comentário do campo, que "um projeto acrescenta itens aqui sem tocar
        no template do header". É por essa porta que a tradução entra, sem
        emendar o design system.
        """
        from django.utils.translation import gettext as _
        from nucleo.components import DropdownItem

        info = super()._user_info(user)
        if info is None:
            return None
        itens = [DropdownItem(label=_("Meu Perfil"), icon="user",
                              href=self.account_href)]
        if self.logout_href:
            # Link, e não botão: sem JavaScript ele leva à confirmação de
            # `/sair`, que é o caminho que sobra (ver `plataforma/sair.py`).
            # `data-sair` é o que o `sair.js` procura para abrir o diálogo em
            # vez de trocar de página.
            itens += [
                DropdownItem(divider=True),
                DropdownItem(label=_("Sair"), icon="logout", danger=True,
                             href=self.logout_href, attrs={"data-sair": ""}),
            ]
        return replace(info, menu=itens)

    def footer(self):
        return replace(super().footer(), logo_alt=NOME_DO_PRODUTO)

    def page(self, **argumentos):
        """A página, com as folhas e scripts do projeto já versionados.

        Um lugar para dezessete telas. Ver `comum/estaticos.py` para o
        motivo: sem a versão no endereço, o navegador serve a folha do cache
        depois de um deploy, e a tela sai quebrada para quem já tinha
        visitado — e só para essa pessoa.
        """
        for chave in ("stylesheets", "scripts"):
            if argumentos.get(chave):
                argumentos[chave] = [versionado(e) for e in argumentos[chave]]

        # **O `path` da requisição, e ninguém precisa lembrar de passá-lo.**
        # É ele que marca no menu a tela aberta (`Site._is_active`) e abre os
        # submenus do caminho (`NavItem.is_open`). O design system o recebe
        # como parâmetro com padrão `/`, e nenhuma das dezenove telas desta
        # casa o passava: o resultado era a barra lateral sem NADA destacado,
        # em toda tela, desde sempre. Não aparecia como defeito — aparecia
        # como um menu que simplesmente não destaca.
        #
        # Só apareceu em 10/09/2026, quando o cadastro do catálogo virou
        # submenu: aí a barra passou a nascer FECHADA em cima da tela onde a
        # pessoa está.
        if "path" not in argumentos and self.pedido is not None:
            argumentos["path"] = self.pedido.path

        pagina = super().page(**argumentos)

        # **Os dois diálogos do cabeçalho vão junto, em toda tela do shell**
        # (18/09/2026): o de sair e o de trocar de lugar. Os gatilhos deles
        # (o menu do avatar e os seletores de contexto) estão em todas as
        # telas, e gatilho sem destino é botão que não faz nada. Aqui, e não
        # em cada view, pelo mesmo motivo de `montar_site` existir: eram
        # dezenove cópias.
        #
        # **Depois de a página existir**, e não antes: é o cabeçalho que
        # resolve quais níveis de contexto essa pessoa tem, e resolvê-los de
        # novo aqui seria a mesma consulta duas vezes.
        if (argumentos.get("user") is not None and pagina.header is not None
                and self.logout_href and self.pedido is not None):
            from .sair import modal_de_sair

            # O nome de quem está logado é o mesmo que o cabeçalho mostra — o
            # retrato do design system (`display_name`/`name`), e não o
            # `Usuario` do banco: quem monta a página passa o retrato.
            quem = argumentos["user"]
            extras = [modal_de_sair(
                self.pedido, action=self.logout_href,
                nome=(getattr(quem, "display_name", "")
                      or getattr(quem, "name", "") or ""))]
            extras += self._dialogo_da_troca(pagina.header)

            # `overlays` já pode trazer as folhas da tela. Acrescentar, nunca
            # substituir: a folha da tela é dela.
            atual = pagina.overlays or []
            anteriores = list(atual) if isinstance(atual, (list, tuple)) \
                else [atual]
            pagina.overlays = [*anteriores, *extras]
        return pagina

    def _dialogo_da_troca(self, cabecalho) -> list:
        """O diálogo de trocar de lugar, com UM formulário por nível que a
        pessoa realmente pode trocar — nenhum, e ele não existe.

        Quem alcança uma empresa e uma loja não tem faixa de contexto no
        cabeçalho, e um diálogo sem gatilho seria peso morto em toda página.
        Quem alcança várias lojas de UMA empresa não recebe o formulário da
        empresa: um campo `empresa_id` numa página de quem não troca de
        empresa é um campo que ninguém esperava ali.
        """
        from .contexto import CHAVE, CHAVE_EMPRESA
        from .trocar import modal_de_troca

        niveis = getattr(cabecalho.context, "levels", ())
        # Mais de uma opção, e não "alguma": desde 25/09/2026 a filial aparece
        # no cabeçalho mesmo quando é uma só, e com uma só não há para onde
        # trocar — o diálogo seria peso morto do mesmo jeito.
        tem = {nivel.name for nivel in niveis if len(nivel.options) > 1}
        if not tem:
            return []
        return [modal_de_troca(self.pedido,
                               com_empresa=CHAVE_EMPRESA in tem,
                               com_filial=CHAVE in tem)]


def montar_site(request) -> Site:
    """O `Site` desta requisição, com marca, menu e contexto já resolvidos."""
    # Da REQUISIÇÃO, e não da instalação (15/09/2026): o menu veste a empresa
    # de quem é visto. Ver `plataforma.marca.marca_da_requisicao`.
    marca = marca_da_requisicao(request)

    def context_line(user: Any) -> "Renderable":
        from comum.sessao import identidade_da_sessao

        from .contexto import _e_da_mw5

        return construir_context_switcher(
            marca, niveis_de_contexto(request),
            da_mw5=_e_da_mw5(identidade_da_sessao(request)))

    return SiteDoProduto(
        pedido=request,
        brand=marca,
        nav=montar(request.usuario),
        theme_href="/tema.css",
        # A folha da empresa DEPOIS da casa: as duas declaram variáveis na
        # `:root`, e quem vem por último ganha. Só as do menu, e vazia para
        # quem não tem aparência própria.
        stylesheets=[versionado(FOLHA_DA_CASA), "/tema-da-empresa.css"],
        # Do site, e não de uma tela: o menu do avatar está em todas, e é ele
        # que abre o diálogo de sair.
        scripts=[versionado("/static/plataforma/sair.js"),
                 versionado("/static/plataforma/contexto.js")],
        context_line=context_line,
    )
