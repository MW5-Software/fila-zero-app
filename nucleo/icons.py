"""Conjunto de ícones do design system.

Todos no mesmo desenho dos mocks: viewBox 24×24, traço de 1.9, sem preenchimento,
pontas arredondadas, herdando `currentColor`. São embutidos no HTML em vez de
virem de uma fonte ou sprite externo por dois motivos: um ícone que herda a cor
do texto acompanha a troca de tema de graça, e não há requisição extra nem flash
de ícone faltando no primeiro carregamento.

Os que vieram literalmente dos mocks da VetPlan estão marcados; o resto segue o
mesmo traço para o conjunto não parecer remendado.
"""

from __future__ import annotations

#: nome -> conteúdo interno do <svg>
ICONS: dict[str, str] = {
    # --- navegação e layout (dos mocks) ---
    "home": '<path d="M3 11l9-8 9 8M5 10v10h14V10"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "chevron-up": '<path d="M18 15l-6-6-6 6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
    "arrow-left": '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    "arrow-right": '<path d="M5 12h14M12 5l7 7-7 7"/>',
    "external": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3"/>',
    "panel-left": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',

    # --- ações (dos mocks) ---
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="M5 12l5 5L20 7"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "x-circle": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/>',
    "search-plus": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4M11 8v6M8 11h6"/>',
    "filter": '<path d="M3 5h18M6 12h12M10 19h4"/>',
    "edit": '<path d="M4 20h4l10-10-4-4L4 16v4zM13.5 6.5l4 4"/>',
    "trash": '<path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13"/>',
    "printer": '<path d="M6 9V3h12v6M6 18H4v-5h16v5h-2M8 14h8v7H8z"/>',
    "swap": '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
    "transfer": '<path d="M16 3h5v5M21 3l-8 8M8 21H3v-5M3 21l8-8"/>',
    "signature": '<path d="M4 20h4L18 10l-4-4L4 16v4zM13 5l4 4"/>',
    "dots-vertical": '<circle cx="12" cy="5" r="1.7" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.7" fill="currentColor" stroke="none"/><circle cx="12" cy="19" r="1.7" fill="currentColor" stroke="none"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5"/>',
    "download": '<path d="M12 3v12M7 11l5 5 5-5M4 20h16"/>',
    "upload": '<path d="M12 16V4M7 8l5-5 5 5M4 20h16"/>',
    "eye": '<path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6z"/><circle cx="12" cy="12" r="2.8"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',

    # --- documentos (dos mocks) ---
    "file": '<path d="M8 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-2M9 3h6v3H9z"/>',
    "file-lines": '<path d="M8 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-2M9 3h6v3H9zM9 12h6M9 16h4"/>',
    "contract": '<path d="M14 3v5h5M14 3l6 6v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM9 13h6M9 17h4"/>',
    "document": '<path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM8 8h8M8 12h5"/>',
    "document-lines": '<path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM8 8h8M8 12h8M8 16h5"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5z"/>',
    "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',

    # --- dados (dos mocks) ---
    "chart-bar": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "chart-line": '<path d="M3 3v18h18M7 14l4-4 3 3 5-6"/>',
    "table": '<path d="M3 3h18v6H3zM3 9v12h18V9M9 3v18"/>',
    "card": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 15h4M15 9h3M15 13h3"/>',
    "smartphone": '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
    "tablet": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M10.5 18.5h3"/>',
    "monitor": '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',

    # --- pessoas e acesso ---
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M17 5.2a3.5 3.5 0 0 1 0 6.6M18.5 20a6.5 6.5 0 0 0-2.5-5.1"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.6-3.3 8.2-8 9.5-4.7-1.3-8-4.9-8-9.5V6z"/>',
    "shield-check": '<path d="M12 3l8 3v6c0 4.6-3.3 8.2-8 9.5-4.7-1.3-8-4.9-8-9.5V6z"/><path d="M9 12l2 2 4-4"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    "logout": '<path d="M15 4h3a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-3M10 17l-5-5 5-5M5 12h11"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 9 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 9a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',

    # --- tema e avisos (dos mocks) ---
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.4 2.3c-.6.3-.9.8-.9 1.4v.3M12 17h.01"/>',

    # --- diversos ---
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "heart": '<path d="M12 21s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.6-7 10-7 10z"/>',
    "paw": '<path d="M10 5.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0zM19 5.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0zM12 21c-1.5-3-4-4-4-7a4 4 0 0 1 8 0c0 3-2.5 4-4 7z"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.4 5.5 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.4-6.5A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.8 1.5z"/>',
    "pin": '<path d="M12 21s-7-6.3-7-11a7 7 0 1 1 14 0c0 4.7-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
}

#: Ícone usado quando alguém pede um nome que não existe. Um "?" é melhor do que
#: quebrar a página — mas `Icon` avisa em modo estrito para não passar batido.
FALLBACK = ICONS["help"]


# --------------------------- a cauda longa (Lucide) ---------------------------
#
# Os de cima são a fonte do design system e não se mexe neles. Estes existem
# porque quem monta o menu de um sistema precisa de um ícone para "Faturamento",
# "Expedição" ou "Frota" — e desenhar um a um, sob demanda, não escala.
#
# Vendorizados por `scripts/vendorizar_icones.py`. Licença ISC; ver NOTICE.

_LUCIDE: "dict[str, str] | None" = None
_ETIQUETAS: "dict[str, list[str]] | None" = None


def _carregar_lucide() -> None:
    """Lê o arquivo vendorizado na primeira vez que alguém precisa dele.

    Preguiçoso porque são ~2000 ícones e a maioria das páginas usa uma dúzia:
    não faz sentido pagar isso no import de todo projeto gerado.
    """
    global _LUCIDE, _ETIQUETAS
    if _LUCIDE is not None:
        return

    import json
    from pathlib import Path

    arquivo = Path(__file__).parent / "icons_lucide.json"
    if not arquivo.is_file():
        _LUCIDE, _ETIQUETAS = {}, {}
        return
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    _LUCIDE = dados.get("icones", {})
    _ETIQUETAS = dados.get("etiquetas", {})


def get(name: str) -> str:
    """Conteúdo interno do SVG de um ícone. Levanta erro se o nome não existir.

    Os do design system vêm primeiro: um nome que existe nos dois conjuntos
    resolve para o desenho dos mocks, não para o do Lucide.
    """
    if name in ICONS:
        return ICONS[name]
    _carregar_lucide()
    try:
        return _LUCIDE[name]
    except KeyError:
        raise KeyError(
            f"ícone {name!r} não existe. São {len(names())} disponíveis — "
            f"use `nucleo.icons.buscar('palavra')` para achar pelo assunto."
        ) from None


def existe(name: str) -> bool:
    if name in ICONS:
        return True
    _carregar_lucide()
    return name in _LUCIDE


def names() -> list[str]:
    """Todos os nomes disponíveis, do design system e do Lucide."""
    _carregar_lucide()
    return sorted(set(ICONS) | set(_LUCIDE))


def nomes_do_design_system() -> list[str]:
    """Só os desenhados a partir dos mocks — os que definem o traço da casa."""
    return sorted(ICONS)


#: Ponte para o português. As etiquetas do Lucide são em inglês, e quem monta o
#: menu de um ERP brasileiro digita "estoque", não "inventory" — sem isto o
#: seletor devolve vazio justamente nas palavras mais prováveis.
#:
#: Não é dicionário: é a lista de termos que aparecem em menu de sistema de
#: gestão. Acrescente conforme aparecer o que ninguém achou.
#: Português → o vocabulário das etiquetas do Lucide, que é todo em inglês.
#:
#: `SINONIMOS` resolve por lista curada: "estoque" devolve os quatro escolhidos
#: a dedo. Isto resolve por TRADUÇÃO: "caminhao" vira `truck`, e a busca passa
#: a alcançar todo ícone cuja etiqueta em inglês tenha essa palavra — `van`,
#: `truck-electric`, `forklift`, `container`, o que vier. Uma entrada aqui abre
#: dezenas de ícones; uma entrada em `SINONIMOS` abre os que alguém listou.
#:
#: Os dois convivem porque respondem coisas diferentes: o sinônimo diz "para
#: estoque, USE estes"; a tradução diz "estoque em inglês é isto". O primeiro é
#: curadoria e vem antes; o segundo é alcance.
#:
#: Sem acento nas CHAVES: `buscar` normaliza o termo digitado antes de comparar,
#: então "caminhão" e "caminhao" chegam aqui iguais.
TRADUCOES: dict[str, tuple[str, ...]] = {
    # transporte e logística — o buraco que originou esta tabela
    "caminhao": ("truck", "lorry", "haulage"),
    "carro": ("car", "vehicle"),
    "moto": ("motorbike", "bike"),
    "onibus": ("bus",),
    "aviao": ("plane", "flight"),
    "navio": ("ship", "boat"),
    "frete": ("shipping", "delivery", "freight"),
    "rota": ("route", "navigation", "directions"),
    "mapa": ("map", "location", "navigation"),
    "local": ("location", "marker", "waypoint"),
    "endereco": ("location", "marker", "home"),
    "viagem": ("travel", "trip", "navigation"),
    "combustivel": ("fuel", "gas"),
    "peso": ("weight", "scale"),
    "caixa": ("box", "container", "package"),
    "pacote": ("package", "box", "parcel"),
    "deposito": ("warehouse", "storage"),
    # pessoas
    "pessoa": ("user", "person", "profile"),
    "grupo": ("users", "group", "team"),
    "equipe": ("team", "users", "group"),
    "perfil": ("profile", "account", "user"),
    "contato": ("contact", "phone", "address"),
    "cracha": ("badge", "id", "card"),
    # dinheiro
    "moeda": ("coin", "currency", "money"),
    "cartao": ("card", "credit", "payment"),
    "carteira": ("wallet", "money"),
    "cofre": ("safe", "vault", "lock"),
    "desconto": ("discount", "percent", "sale"),
    "recibo": ("receipt", "invoice", "bill"),
    "fatura": ("invoice", "bill", "receipt"),
    # documentos
    "arquivo": ("file", "document"),
    "pasta": ("folder", "directory"),
    "documento": ("document", "file", "paper"),
    "assinatura": ("signature", "sign", "pen"),
    "impressora": ("printer", "print"),
    "anexo": ("attachment", "paperclip", "clip"),
    "modelo": ("template", "layout"),
    # tempo
    "calendario": ("calendar", "date", "schedule"),
    "relogio": ("clock", "time", "watch"),
    "agenda": ("calendar", "schedule", "planner"),
    "historico": ("history", "time", "clock"),
    "prazo": ("deadline", "clock", "calendar"),
    # ações e estados
    "buscar": ("search", "find", "magnifier"),
    "filtro": ("filter", "funnel"),
    "editar": ("edit", "pencil", "write"),
    "apagar": ("delete", "trash", "remove"),
    "salvar": ("save", "disk", "check"),
    "enviar": ("send", "share", "upload"),
    "baixar": ("download", "save"),
    "atualizar": ("refresh", "reload", "sync"),
    "configuracao": ("settings", "config", "gear"),
    "ajuda": ("help", "question", "support"),
    "aviso": ("warning", "alert", "caution"),
    "erro": ("error", "cross", "danger"),
    "sucesso": ("success", "check", "done"),
    "bloqueado": ("lock", "locked", "secure"),
    "senha": ("password", "key", "lock"),
    "sair": ("logout", "exit", "sign-out"),
    "entrar": ("login", "sign-in", "enter"),
    # números e visualização
    "grafico": ("chart", "graph", "analytics"),
    "tabela": ("table", "grid", "spreadsheet"),
    "lista": ("list", "items"),
    "painel": ("dashboard", "panel"),
    "porcentagem": ("percent", "percentage"),
    "calculadora": ("calculator", "math"),
    "meta": ("target", "goal", "aim"),
    # lugares e coisas
    "empresa": ("company", "building", "office"),
    "predio": ("building", "office"),
    "loja": ("store", "shop", "market"),
    "fabrica": ("factory", "industry", "plant"),
    "casa": ("home", "house"),
    "chave": ("key", "unlock"),
    "etiqueta": ("tag", "label"),
    "codigo": ("code", "barcode", "qr"),
    "camera": ("camera", "photo"),
    "imagem": ("image", "picture", "photo"),
    "telefone": ("phone", "call"),
    "email": ("mail", "envelope", "message"),
    "mensagem": ("message", "chat", "comment"),
    "sino": ("bell", "notification"),
    "estrela": ("star", "favorite"),
    "coracao": ("heart", "like"),
    "lixeira": ("trash", "delete", "bin"),
    "seta": ("arrow", "chevron"),
    "olho": ("eye", "view", "visible"),
}

SINONIMOS: dict[str, tuple[str, ...]] = {
    "estoque": ("package", "boxes", "warehouse", "layers"),
    "almoxarifado": ("warehouse", "boxes", "forklift"),
    "produto": ("package", "tag", "barcode", "shopping-bag"),
    "compra": ("shopping-cart", "shopping-bag", "truck"),
    "venda": ("shopping-cart", "receipt", "trending-up", "handshake"),
    "pedido": ("clipboard-list", "shopping-cart", "receipt"),
    "entrega": ("truck", "package-check", "map-pin"),
    "frota": ("truck", "car", "van", "motorbike"),
    "transporte": ("truck", "van", "route", "map"),
    "financeiro": ("banknote", "wallet", "coins", "landmark"),
    "dinheiro": ("banknote", "coins", "wallet", "circle-dollar-sign"),
    "banco": ("landmark", "building-2", "credit-card"),
    "pagamento": ("credit-card", "banknote", "wallet"),
    "cobranca": ("receipt", "banknote-arrow-up", "calendar-clock"),
    "nota": ("receipt", "file-text", "scroll-text"),
    "fiscal": ("receipt", "file-text", "percent", "landmark"),
    "imposto": ("percent", "landmark", "receipt"),
    "contrato": ("file-signature", "scroll-text", "handshake"),
    "cliente": ("users", "user-round", "contact"),
    "fornecedor": ("truck", "building-2", "handshake"),
    "funcionario": ("id-card", "users", "briefcase"),
    "empresa": ("building-2", "landmark", "briefcase"),
    "filial": ("building", "map-pin", "store"),
    "loja": ("store", "shopping-bag", "building"),
    "relatorio": ("chart-column", "chart-pie", "file-text", "chart-line"),
    "grafico": ("chart-column", "chart-line", "chart-pie"),
    "meta": ("target", "trending-up", "flag"),
    "agenda": ("calendar", "calendar-days", "clock"),
    "ordem": ("clipboard-list", "wrench", "hard-hat"),
    "servico": ("wrench", "hard-hat", "headset"),
    "manutencao": ("wrench", "hammer", "settings"),
    "producao": ("factory", "cog", "hard-hat"),
    "usuario": ("user", "users", "id-card", "circle-user"),
    "senha": ("lock", "key", "key-round"),
    "documento": ("file-text", "files", "folder-open"),
    "qualidade": ("badge-check", "award", "star"),
    "permissao": ("key", "shield-check", "lock"),
    "acesso": ("key", "log-in", "shield"),
    "configuracao": ("settings", "sliders-horizontal", "cog"),
    "cadastro": ("folder", "list", "database"),
    "auditoria": ("file-search", "history", "scan-eye"),
    "suporte": ("headset", "life-buoy", "message-circle"),
}


def buscar(termo: str, limite: int = 120) -> list[str]:
    """Nomes que casam com o termo, por nome, por sinônimo ou por palavra-chave.

    Sem termo, devolve o conjunto da casa primeiro: são os que combinam com o
    resto do sistema, e quem não vai procurar nada deveria esbarrar neles.

    O limite era 60, e 60 é menos do que os 67 da casa: a grade abria cortando
    o próprio conjunto curado, e quem olhava concluía que a biblioteca inteira
    tinha aquilo. São 2007 ícones atrás dessa caixa de busca.
    """
    termo = _sem_acento((termo or "").strip().lower())
    if not termo:
        restantes = [n for n in names() if n not in ICONS]
        return (nomes_do_design_system() + restantes)[:limite]

    _carregar_lucide()

    # Sinônimo casa primeiro: quem digitou "estoque" quer os quatro escolhidos
    # a dedo, não os 40 que têm "stock" em alguma etiqueta.
    #
    # Palavra a palavra, porque a pessoa digita "nota fiscal" e as duas palavras
    # são chaves separadas — casar a frase inteira não acharia nenhuma delas.
    palavras = [p for p in termo.split() if p]
    sugeridos = [n
                 for palavra in palavras
                 for chave, nomes_ in SINONIMOS.items() if palavra in chave
                 for n in nomes_ if existe(n)]

    # O que o termo quer dizer em inglês. As etiquetas do Lucide são todas em
    # inglês: sem isto, "caminhao" não alcançava nenhuma das `delivery`,
    # `shipping`, `lorry` que já estavam no arquivo — e a biblioteca parecia
    # pequena quando o que faltava era o dicionário.
    traduzidos: list[str] = []
    for palavra in palavras:
        for chave, traducoes in TRADUCOES.items():
            if palavra in chave:
                traduzidos.extend(traducoes)

    # Quatro faixas, e a ordem entre elas é o resultado. Sem ela, buscar "mapa"
    # devolvia `arrow-down-to-dot` antes de `map`: as três primeiras vinham por
    # etiqueta, em ordem alfabética, e o ícone óbvio ficava na terceira fileira
    # — ou fora do limite. Achar não basta; tem que achar primeiro.
    por_nome, por_etiqueta = [], []
    traducao_no_nome, traducao_na_etiqueta = [], []
    for nome in names():
        if nome in sugeridos:
            continue
        # O que a PESSOA digitou casa por pedaço: ela digita "cami" e espera
        # ver caminhão antes de terminar a palavra.
        if termo in nome:
            por_nome.append(nome)
        elif any(termo in t for t in _ETIQUETAS.get(nome, ())):
            por_etiqueta.append(nome)
        # A TRADUÇÃO casa por palavra inteira. Por pedaço, `lock` casava dentro
        # de `clock` e buscar "senha" trazia quarenta despertadores; `car`
        # casava dentro de `card` e "carro" trazia os cartões todos. O ruído
        # não é um detalhe: ele empurra para fora do limite justamente os
        # ícones que a pessoa procurava.
        elif traduzidos and _casa_palavra(traduzidos, nome.split("-")):
            traducao_no_nome.append(nome)
        elif traduzidos and _casa_palavra(traduzidos, _palavras_da_etiqueta(nome)):
            traducao_na_etiqueta.append(nome)

    # Dentro da faixa, o nome mais curto primeiro: buscar "chave" trazia
    # `book-key` antes de `key`, porque a ordem era alfabética. Quem procura
    # uma chave quer a chave, e o desenho composto é o caso raro.
    traducao_no_nome.sort(key=lambda n: (n.count("-"), len(n), n))
    traducao_na_etiqueta.sort(key=lambda n: (n.count("-"), len(n), n))

    vistos, saida = set(), []
    for nome in (sugeridos + por_nome + por_etiqueta
                 + traducao_no_nome + traducao_na_etiqueta):
        if nome not in vistos:
            vistos.add(nome)
            saida.append(nome)
    return saida[:limite]


def _casa_palavra(alvos: "list[str]", partes: "list[str]") -> bool:
    """Alguma das palavras está inteira entre as partes dadas.

    Inteira, e não como pedaço: é o que faz `lock` casar `lock` e `unlock`, e
    não `clock`.
    """
    conjunto = set(partes)
    return any(a in conjunto for a in alvos)


def _palavras_da_etiqueta(nome: str) -> "list[str]":
    """As palavras de todas as etiquetas de um ícone.

    O Lucide separa por espaço (`shopping cart`) e às vezes por hífen
    (`e-mail`); as duas viram palavra.
    """
    palavras: list[str] = []
    for etiqueta in _ETIQUETAS.get(nome, ()):
        palavras.extend(etiqueta.replace("-", " ").split())
    return palavras


def _sem_acento(texto: str) -> str:
    """"relatório" e "relatorio" procuram a mesma coisa."""
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFKD", texto)
                   if not unicodedata.combining(c))
