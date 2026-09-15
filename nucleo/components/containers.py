"""Componentes que agrupam conteúdo: cards, modais, avisos, listas, navegação."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..rendering import Component, Renderable
from .primitives import TONES, _validate

__all__ = [
    "Accordion",
    "AccordionItem",
    "ActionBar",
    "Alert",
    "ALINHAMENTOS",
    "Box",
    "Card",
    "DIRECOES",
    "Drawer",
    "Dropdown",
    "DropdownItem",
    "EmptyState",
    "ErrorState",
    "ESPACAMENTOS",
    "ItemRow",
    "Modal",
    "PageHeader",
    "SectionLabel",
    "StatCard",
    "Step",
    "Stepper",
    "Tab",
    "Tabs",
    "Timeline",
    "TimelineEvent",
    "Toast",
    "TRANSVERSAIS",
]

#: As direções que uma `Box` aceita. Duas, porque flex tem duas.
DIRECOES: tuple[str, ...] = ("column", "row")

#: O alinhamento no eixo da direção — o `justify-content` do CSS, com nomes
#: que não exigem saber CSS para escolher.
ALINHAMENTOS: tuple[str, ...] = ("start", "center", "end", "between", "around")

#: O alinhamento no eixo transversal — o `align-items`.
TRANSVERSAIS: tuple[str, ...] = ("start", "center", "end", "stretch")

#: Espaçamento e recheio. Quatro degraus, derivados dos tokens de densidade —
#: escolher "médio" tem que dar o mesmo médio em toda tela do sistema, e é
#: exatamente isso que pixel digitado perderia.
ESPACAMENTOS: tuple[str, ...] = ("none", "sm", "md", "lg")


@dataclass
class Card(Component):
    """A caixa branca que estrutura quase toda tela do sistema."""

    template: ClassVar[str] = "components/card.html"

    body: Renderable = ""
    title: str | None = None
    #: A linha embaixo do título. Existe porque metade dos cartões de gestão
    #: precisa dizer DE QUE é o número — "últimos 30 dias", "somente ativos",
    #: "atualizado às 14h". Sem ela, isso virava um `SectionLabel` solto dentro
    #: do corpo, com peso de título e afastado do título de verdade.
    #:
    #: Só aparece com título: subtítulo sozinho é um texto cinza flutuando no
    #: topo do cartão, sem nada a que se referir.
    subtitle: str | None = None
    icon: str | None = None
    header_actions: Renderable = ""
    footer: Renderable = ""
    padded: bool = True  # desligue para tabelas, que sangram até a borda
    css_class: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Box(Component):
    """Uma caixa flex: direção, alinhamento e espaçamento, com o que for dentro.

    É a peça que faltava para o construtor montar hierarquia. `Card` agrupa e
    desenha; `FormGrid` divide a página em colunas; não havia nada que só
    arrumasse um punhado de coisas numa fileira — título à esquerda e botão à
    direita, ambos centrados na vertical.

    **Não desenha moldura de propósito.** Quem quer cartão põe um `Card` em
    volta: ele já sabe título, ícone, ações no cabeçalho e rodapé, e repetir
    isso aqui daria dois jeitos de fazer a mesma caixa branca — e os dois
    divergiriam.
    """

    template: ClassVar[str] = "components/box.html"

    body: Renderable = ""
    direction: str = "column"
    align: str = "start"
    cross: str = "stretch"
    gap: str = "md"
    pad: str = "none"
    wrap: bool = True
    #: Só a prévia do construtor preenche: é como o arrastar-e-soltar acha a
    #: caixa certa dentro de outra. O projeto gerado sai sem isto — não tem
    #: construtor com quem conversar.
    path: str = ""
    css_class: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate(self.direction, DIRECOES, "direction", "Box")
        _validate(self.align, ALINHAMENTOS, "align", "Box")
        _validate(self.cross, TRANSVERSAIS, "cross", "Box")
        _validate(self.gap, ESPACAMENTOS, "gap", "Box")
        _validate(self.pad, ESPACAMENTOS, "pad", "Box")


@dataclass
class PageHeader(Component):
    """Título da página, com subtítulo, etiquetas e ação principal à direita."""

    template: ClassVar[str] = "components/page_header.html"

    title: str
    subtitle: str | None = None
    tags: Renderable = ""
    actions: Renderable = ""


@dataclass
class Heading(Component):
    """Um título com o texto de apoio embaixo.

    Existia dentro do cabeçalho de um `Card` e em nenhum outro lugar: solto na
    página, ou no topo de uma caixa, a única peça parecida era o
    `SectionLabel` — e ele é outra coisa, um rótulo minúsculo em maiúsculas com
    um risco atravessando a largura. Quem quisesse "Simular frete" e a frase
    embaixo tinha de pôr um cartão em volta só para conseguir o cabeçalho.

    Não reaproveita as classes do cabeçalho do cartão de propósito: `.ch` é o
    ARRANJO do cabeçalho — ícone à esquerda, ações à direita, linha embaixo — e
    herdá-lo aqui traria as três coisas junto. O que se repete é a proporção
    entre título e apoio, e ela mora nos tokens.
    """

    template: ClassVar[str] = "components/heading.html"

    SIZES: ClassVar[tuple[str, ...]] = ("secao", "pagina")

    title: str = ""
    #: A frase embaixo. Some quando vazia: um espaço reservado para um texto
    #: que não veio empurra o que está abaixo sem nada dentro.
    support: str = ""
    size: str = "secao"
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate(self.size, self.SIZES, "size", "Heading")


@dataclass
class SectionLabel(Component):
    """Rótulo de seção com a linha que atravessa o resto da largura."""

    template: ClassVar[str] = "components/section_label.html"

    label: str
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatCard(Component):
    """Número em destaque — os quatro contadores do topo da listagem."""

    template: ClassVar[str] = "components/stat_card.html"

    value: str
    label: str
    tone: str = "neutral"

    def __post_init__(self) -> None:
        _validate(self.tone, TONES, "tone", "StatCard")


@dataclass
class ModuleCard(Component):
    """Atalho para um módulo, no formato dos cards do início."""

    template: ClassVar[str] = "components/module_card.html"

    title: str
    #: Vazio: o cartão descreve alguma coisa que não tem rota, e sai como uma
    #: `div` em vez de um link morto.
    href: str
    icon: str
    description: str | None = None
    badge: str | None = None


@dataclass
class ModuleGrid(Component):
    """A grade que acomoda os `ModuleCard` e se reflui sozinha."""

    template: ClassVar[str] = "components/module_grid.html"

    cards: list[ModuleCard] = field(default_factory=list)
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Summary(Component):
    """A faixa de `StatCard` acima de uma listagem."""

    template: ClassVar[str] = "components/summary.html"

    stats: Renderable = ""
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Fact:
    """Um par rótulo→valor de uma `DefinitionList`."""

    label: str
    value: str


@dataclass
class DefinitionList(Component):
    """Rótulo à esquerda, valor à direita, e uma faixa de total embaixo.

    É o resumo de um cálculo: distância, peso, prazo, e o preço em destaque.
    Faltava, e montá-lo com o que havia dava três coisas soltas — um `Box` por
    linha, um `SectionLabel` fingindo de rótulo — que nenhuma tela seguinte
    repetiria igual.

    Sai como `<dl>` de verdade: o par rótulo/valor é o que a marcação de
    definição existe para dizer, e um leitor de tela ganha a associação sem
    nenhum `aria-` escrito à mão.

    O total é campo à parte, e não mais um `Fact`: ele não é "outra linha da
    lista" — é a conclusão dela, com peso visual próprio. Como item comum,
    quem montasse teria de lembrar de destacar o último toda vez, e metade das
    telas esqueceria.
    """

    template: ClassVar[str] = "components/definition_list.html"

    items: list[Fact] = field(default_factory=list)
    total_label: str = ""
    total_value: str = ""
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)

    @property
    def com_total(self) -> bool:
        """A faixa só aparece com rótulo E valor. Só um dos dois desenha uma
        faixa pela metade, que lê como defeito e não como escolha."""
        return bool(self.total_label and self.total_value)


@dataclass
class Alert(Component):
    """Aviso fixo no corpo da página."""

    template: ClassVar[str] = "components/alert.html"

    message: Renderable
    tone: str = "info"
    title: str | None = None
    icon: str | None = None
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)

    ICON_BY_TONE: ClassVar[dict[str, str]] = {
        "ok": "check-circle",
        "info": "info",
        "warn": "alert",
        "danger": "x-circle",
        "neutral": "info",
    }

    def __post_init__(self) -> None:
        _validate(self.tone, TONES, "tone", "Alert")
        if self.icon is None:
            self.icon = self.ICON_BY_TONE[self.tone]


@dataclass
class Toast(Component):
    """Aviso passageiro no canto inferior. Some sozinho após `duration` ms."""

    template: ClassVar[str] = "components/toast.html"

    message: str
    tone: str = "ok"
    title: str | None = None
    duration: int = 5000

    def __post_init__(self) -> None:
        _validate(self.tone, TONES, "tone", "Toast")


@dataclass
class Modal(Component):
    """Diálogo centralizado.

    Nasce fechado e é aberto por HTMX ou pelo JS do design system. O overlay
    fecha no clique fora e no Esc — comportamento que vem de graça em
    `mw5.js`, sem precisar de código por tela.
    """

    template: ClassVar[str] = "components/modal.html"

    id: str
    title: str
    body: Renderable = ""
    subtitle: str | None = None
    footer: Renderable = ""
    size: str = ""  # "" | "sm" | "lg"
    open: bool = False

    def __post_init__(self) -> None:
        _validate(self.size, ("", "sm", "lg"), "size", "Modal")


@dataclass
class Drawer(Component):
    """Painel que entra pela direita. Mesmo papel do modal para conteúdo longo."""

    template: ClassVar[str] = "components/drawer.html"

    id: str
    title: str
    body: Renderable = ""
    subtitle: str | None = None
    open: bool = False


@dataclass
class DropdownItem(Component):
    template: ClassVar[str] = "components/dropdown_item.html"

    label: str = ""
    icon: str | None = None
    href: str | None = None
    danger: bool = False
    divider: bool = False  # quando True, vira só uma linha separadora
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Dropdown(Component):
    """Menu flutuante — o das reticências em cada linha da tabela.

    A posição é calculada no clique pelo `mw5.js`, que também vira o menu para
    cima quando não há espaço abaixo. Por isso ele vive solto no fim do body e
    não dentro da linha: dentro da tabela, `overflow-x` o cortaria.
    """

    template: ClassVar[str] = "components/dropdown.html"

    id: str
    items: list[DropdownItem] = field(default_factory=list)
    title: str | None = None


@dataclass
class EmptyState(Component):
    """Quando não há nada para mostrar — e o que a pessoa pode fazer a respeito."""

    template: ClassVar[str] = "components/empty_state.html"

    title: str
    message: str | None = None
    icon: str = "inbox"
    actions: Renderable = ""
    inline: bool = False


@dataclass
class ErrorState(Component):
    """Quando algo falhou. Separado do vazio porque exige tom e ação diferentes."""

    template: ClassVar[str] = "components/error_state.html"

    title: str = "Não foi possível carregar"
    message: str | None = None
    icon: str = "alert"
    actions: Renderable = ""
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineEvent(Component):
    template: ClassVar[str] = "components/timeline_event.html"

    label: str
    when: str | None = None
    state: str = "done"  # done | cur | pending | void

    def __post_init__(self) -> None:
        _validate(self.state, ("done", "cur", "pending", "void"), "state", "TimelineEvent")

    @property
    def icon(self) -> str | None:
        return {"done": "check", "cur": "check", "void": "x"}.get(self.state)


@dataclass
class Timeline(Component):
    """Trilha vertical de eventos — o histórico de um registro."""

    template: ClassVar[str] = "components/timeline.html"

    events: list[TimelineEvent] = field(default_factory=list)
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Step:
    """Uma etapa. Só existe dentro de um `Stepper`, que precisa da posição dela
    para decidir se desenha a barra de ligação — por isso não se renderiza só."""

    label: str
    state: str = "pending"  # done | cur | pending

    def __post_init__(self) -> None:
        _validate(self.state, ("done", "cur", "pending"), "state", "Step")


@dataclass
class Stepper(Component):
    """Progresso de um processo em etapas."""

    template: ClassVar[str] = "components/stepper.html"

    steps: list[Step] = field(default_factory=list)
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Tab(Component):
    """Uma aba. Serve a dois usos, e o `body` decide qual.

    Com `href`, é navegação: a aba é um link para outra tela, e trocar de aba
    recarrega a página.

    Com `body`, é painel: o conteúdo mora aqui e trocar de aba não recarrega
    nada — é o que "abas" quer dizer dentro de um cadastro (Dados, Endereços,
    Financeiro). Os dois não se misturam numa mesma barra; ver `Tabs`.
    """

    template: ClassVar[str] = "components/tab.html"

    label: str
    href: str | None = None
    active: bool = False
    body: Renderable = ""
    attrs: dict[str, Any] = field(default_factory=dict)
    #: Só a prévia do construtor preenche, e quem o desenha é a `Tabs`, no
    #: PAINEL — não no botão. A barra e os painéis são irmãos no HTML, então
    #: nada dentro de um painel alcança o `path` da barra subindo o DOM: sem
    #: isto, uma aba vazia não recebia bloco nenhum (o `dragover` desiste sem
    #: alvo) e o convite dentro dela não dava para escolher.
    path: str = ""


@dataclass
class Tabs(Component):
    """A barra de abas, e os painéis quando há conteúdo.

    Painel só entra quando alguma aba tem `body` — uma barra de navegação
    continua saindo como uma `<nav>` e nada mais. Uma barra que misture os dois
    teria abas que recarregam ao lado de abas que não recarregam, e não há como
    quem usa adivinhar qual é qual.

    `id` liga o botão ao painel por `aria-controls`. Vem de fora porque a mesma
    tela pode ter duas barras, e dois painéis com o mesmo id fariam a segunda
    barra trocar os painéis da primeira.
    """

    template: ClassVar[str] = "components/tabs.html"

    tabs: list[Tab] = field(default_factory=list)
    id: str = "abas"
    #: Só a prévia do construtor preenche. É por ele que o arrastar acha onde
    #: soltar e a etiqueta acha o que remover.
    path: str = ""

    def __post_init__(self) -> None:
        # Quem abre por padrão se decide AQUI, e num lugar só. Enquanto o
        # template também tinha uma regra de reserva ("a primeira, se nenhuma
        # estiver ativa"), apagar o `active` de quem monta as abas não fazia
        # diferença nenhuma — e nenhum teste podia notar, porque o painel abria
        # de qualquer jeito enquanto o botão ficava sem destaque.
        if self.com_paineis and not any(t.active for t in self.tabs):
            self.tabs[0].active = True

    @property
    def com_paineis(self) -> bool:
        return any(t.body for t in self.tabs)


@dataclass
class AccordionItem(Component):
    template: ClassVar[str] = "components/accordion_item.html"

    title: str
    body: Renderable = ""
    icon: str | None = None
    open: bool = False
    #: Só a prévia do construtor preenche, e vai no PAINEL da seção — não no
    #: `.accordion`, que já carrega o caminho da sanfona inteira. Sem isto,
    #: soltar dentro de uma seção chegava ao endereço da sanfona e o bloco caía
    #: AO LADO dela. Mesma história das abas, por outro caminho.
    path: str = ""


@dataclass
class Accordion(Component):
    """Lista de seções que abrem e fecham.

    Com `group`, as seções passam a ser mutuamente exclusivas: abrir uma fecha
    as outras do mesmo grupo. O grupo é um nome, e não a própria lista, porque
    a exclusividade às vezes precisa atravessar acordeões vizinhos — no editor,
    cada área é uma lista própria mas todas se comportam como uma só.
    """

    template: ClassVar[str] = "components/accordion.html"

    items: list[AccordionItem] = field(default_factory=list)
    group: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)
    #: Só a prévia do construtor preenche. Ver `Tabs.path`.
    path: str = ""


@dataclass
class ItemRow(Component):
    """Linha de uma lista editável — beneficiários, anexos, participantes."""

    template: ClassVar[str] = "components/item_row.html"

    title: str
    subtitle: str | None = None
    icon: str = "user"
    tag: Renderable = ""
    actions: Renderable = ""
    remove_attrs: dict[str, Any] | None = None  # se dado, mostra o botão de remover


@dataclass
class DashedButton(Component):
    """Botão tracejado de largura total — o "incluir mais um" de listas editáveis."""

    template: ClassVar[str] = "components/dashed_button.html"

    label: str
    icon: str = "plus"
    href: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Cell(Component):
    """Uma célula da grade de 12, com qualquer coisa dentro.

    Os campos de formulário já sabem se posicionar sozinhos — cada um carrega
    o próprio `span`. Faltava a mesma coisa para o resto: sem isto, pôr um
    gráfico ao lado de uma tabela obrigava a escrever uma `div` com classe de
    grade à mão, dentro de um sistema que existe para não ter isso.
    """

    template: ClassVar[str] = "components/cell.html"

    span: int = 12
    children: Renderable = ""
    #: Como em `Box`: só a prévia do construtor preenche.
    path: str = ""


@dataclass
class Slot(Component):
    """Um contêiner vazio identificado, alvo de trocas do HTMX.

    Serve para o caso do modal carregado sob demanda: a página reserva o lugar,
    e a resposta do servidor preenche. Sem isto, cada tela escreveria uma `div`
    solta no meio da composição.
    """

    template: ClassVar[str] = "components/slot.html"

    id: str
    content: Renderable = ""
    css_class: str = ""
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor
    #: a usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria.
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionBar(Component):
    """Barra fixa no rodapé das telas de formulário.

    Fica fixa porque os formulários do sistema são longos: obrigar a rolar até o
    fim para achar "Salvar" é o tipo de atrito que aparece cem vezes por dia.
    """

    template: ClassVar[str] = "components/action_bar.html"

    actions: Renderable
    hint: Renderable = ""


#: Os hosts de onde um mapa pode vir.
#:
#: Lista fechada, e não "qualquer https": o ponto deste componente é justamente
#: não deixar um endereço arbitrário virar um `<iframe>` na página de quem está
#: logado. Um iframe é um documento inteiro de outra origem dentro do sistema —
#: ele não lê o cookie daqui, mas ocupa a tela, e uma página que finge ser a
#: nossa dentro de um retângulo é onde alguém digita a senha.
HOSTS_DE_MAPA: frozenset[str] = frozenset({
    "www.google.com", "google.com", "maps.google.com",
})


@dataclass
class Mapa(Component):
    """Um mapa do Google, embutido pela URL de embed.

    Recebe a URL, e não o `<iframe>` pronto: é essa a diferença que faz o
    componente valer a pena. Colar a tag inteira significaria aceitar HTML
    arbitrário — e HTML arbitrário vindo de um JSON que o sistema do cliente
    devolve é a receita de XSS armazenado, que roda com a sessão de quem está
    logado. Aqui o que entra é um endereço; quem monta a tag somos nós.

    URL que não passa vira um aviso na tela dizendo o que se esperava. Não
    levanta: isto é desenhado a cada tecla na prévia do construtor, e uma
    exceção no meio da digitação derrubaria a tela inteira.
    """

    template: ClassVar[str] = "components/mapa.html"

    url: str = ""
    #: Escotilha de atributos crus no elemento raiz. A prévia do construtor a
    #: usa para carimbar o `data-mw5-caminho` do bloco sem embrulhar o
    #: componente num `div` que só ela teria — e é por ele que arrastar,
    #: escolher e reordenar alcançam o mapa como alcançam qualquer outro bloco.
    attrs: dict[str, Any] = field(default_factory=dict)
    #: O que o leitor de tela anuncia. Um `<iframe>` sem título é anunciado
    #: como "quadro", e a pessoa não sabe se pulou um mapa ou um anúncio.
    titulo: str = "Mapa"
    altura: int = 360
    moldura: bool = True

    @property
    def valida(self) -> bool:
        from urllib.parse import urlparse

        try:
            partes = urlparse(self.url.strip())
        except ValueError:
            return False
        return (partes.scheme == "https"
                and partes.netloc in HOSTS_DE_MAPA
                and partes.path.startswith("/maps"))
