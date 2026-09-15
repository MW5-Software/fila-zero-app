"""Qual marca está valendo nesta instalação."""

from __future__ import annotations

from dataclasses import replace

from nucleo.theme import Brand
from nucleo.theme.brand import AreaColors, Assets

__all__ = [
    "ACCENT_DO_PRODUTO", "AREAS_DO_LOGO_DO_PRODUTO", "AREAS_DO_PRODUTO",
    "AREAS_DO_RODAPE", "ASSETS_DO_PRODUTO",
    "CAMINHO_DA_IMAGEM", "CONTRASTE_MINIMO", "FOLHA_DA_CASA",
    "LOGO_DO_PRODUTO_ENTRADA",
    "LOGO_DO_PRODUTO_MENU", "LOGO_DO_PRODUTO_RODAPE", "MARCA_PADRAO",
    "NOME_DO_PRODUTO",
    "assets_da_instalacao", "conferir_legibilidade", "marca_da_instalacao",
]

#: O prefixo fixo da rota que serve as imagens da marca. Constante e não
#: `reverse()`: esta função roda dentro do `settings` sendo importado nos
#: testes de projeto, onde carregar o URLconf cedo é pedir problema — e o
#: caminho é contrato público do sistema (ele aparece no HTML servido).
CAMINHO_DA_IMAGEM = "/marca/imagem/"

#: A folha desta casa, carregada DEPOIS da `mw5.css`. É onde mora correção do
#: design system que ainda não subiu para o `mw5_admin` — ver o cabeçalho do
#: arquivo. Caminho literal pelo mesmo motivo do `CAMINHO_DA_IMAGEM` acima.
FOLHA_DA_CASA = "/static/plataforma/kronos.css"

#: Como o logo do rodapé se chama para quem usa leitor de tela. É o nome do
#: PRODUTO, e não o do cliente: no rodapé a imagem é sempre a mesma.
NOME_DO_PRODUTO = "KRONOS ERP"

#: O logo do produto, servido do estático do `plataforma` (não do `nucleo`:
#: lá mora o design system, que é reusável e não tem dono; a marca do KRONOS
#: tem). Um arquivo por lugar, o mesmo desenho em três resoluções — mesma
#: divisão que o `Assets` já faz, e pelo mesmo motivo: o que cabe numa faixa
#: de 84px não é o que cabe num rodapé de 40px.
#:
#: Vieram do painel GED, onde esta marca já estava resolvida (ver o
#: `brand.yaml` de lá). Não é a versão branca: o desenho é azul-marinho com o
#: símbolo em ciano, e a faixa da barra tem fundo branco fixo no design
#: system — sobre ela, a versão branca sumiria.
#:
#: Caminho literal em vez de `static()` pelo mesmo motivo do
#: `CAMINHO_DA_IMAGEM` acima: este módulo é importado cedo, e o armazenamento
#: de estáticos aqui não versiona nome de arquivo (ver STORAGES em settings).
LOGO_DO_PRODUTO_ENTRADA = "/static/plataforma/marca/kronos-login.png"
LOGO_DO_PRODUTO_MENU = "/static/plataforma/marca/kronos-sidebar.png"
LOGO_DO_PRODUTO_RODAPE = "/static/plataforma/marca/kronos-footer.png"

#: A marca do KRONOS é EMPILHADA — símbolo em cima, "Kronos" e "ERP | CRM"
#: embaixo. O design system reserva 56px de altura na barra e 24px no rodapé,
#: medidas pensadas para marca deitada: nelas o nome sai com ~16px e ~7px, e a
#: linha do ERP com 4px e 2px — ilegível, e o limite não é o arquivo, é o
#: espaço. Estes números vêm do GED, onde a conta já foi feita.
AREAS_DO_LOGO_DO_PRODUTO = {
    "logo-side-h": "84px",
    "logo-footer-h": "40px",
    # A largura acompanha a proporção da marca (1,434) com folga: 40 × 1,434 = 58.
    "logo-footer-w": "72px",
}

#: O que vale para o rodapé em QUALQUER instalação, com ou sem marca de
#: cliente: o logo do rodapé não troca (ver `LUGARES_DA_IMAGEM` em
#: `plataforma/models.py`), então a medida dele também não pode trocar.
AREAS_DO_RODAPE = {
    chave: valor for chave, valor in AREAS_DO_LOGO_DO_PRODUTO.items()
    if chave.startswith("logo-footer")
}

#: O rodapé é a assinatura do produto, não do cliente: ele diz de quem é o
#: sistema, e isso não muda de instalação para instalação. Por isso o logo do
#: rodapé NÃO está em `LUGARES_DA_IMAGEM` — não há o que enviar, e uma tela
#: que oferecesse o envio estaria mentindo.
ASSETS_DO_PRODUTO = Assets(
    login_logo=LOGO_DO_PRODUTO_ENTRADA,
    sidebar_logo=LOGO_DO_PRODUTO_MENU,
    footer_logo=LOGO_DO_PRODUTO_RODAPE,
)

#: As cores da casa, tiradas do PRÓPRIO arquivo da marca: `#1f275d` é o
#: azul-marinho dominante do logo e `#2c9ccb` é o ciano do símbolo.
#:
#: O ciano não vira fundo de item: texto branco sobre ele dá 3,12:1, abaixo
#: dos 4,5:1 que a WCAG pede para texto normal. Hover e ativo são o próprio
#: marinho clareado — mantém a família e deixa os dois estados legíveis
#: (10,3:1 e 7,96:1). Mesma conta do painel GED, onde ela já foi feita.
AREAS_DO_PRODUTO = AreaColors(
    sidebar_bg="#1f275d",
    sidebar_text="#ffffff",
    sidebar_hover_bg="#353d6d",
    sidebar_hover_text="#ffffff",
    sidebar_active_bg="#474e7a",
    sidebar_active_text="#ffffff",
)

#: O ciano da marca escurecido em 25%. O `#2c9ccb` puro dá 3,12:1 sobre
#: branco, e o accent é usado como TEXTO (`.tag.accent`, contadores do menu)
#: em 10px. Escurecido chega a 5,17:1 e continua sendo reconhecidamente a cor
#: da marca. O padrão do design system é `#872d00`, um marrom que veio do
#: Sementes Premix e nunca teve nada a ver com o KRONOS.
ACCENT_DO_PRODUTO = "#217598"

#: A cara com que uma instalação nova nasce. Nada quebrado, nada em branco —
#: a MW5 troca a marca do cliente na tela de Aparência; o rodapé continua o
#: mesmo.
#:
#: **No Fila Zero, a marca de nascença é "Fila Zero".** Na base era só
#: KRONOS, e sem a troca toda instalação nova nasceria com a identidade da
#: base na tela de entrada, no menu e na aba do navegador. O cliente troca na
#: tela de Aparência.
MARCA_PADRAO = Brand(client_name="Fila Zero",
                     system_name="Fila Zero",
                     accent=ACCENT_DO_PRODUTO,
                     radius="6px", radius_control="4px",
                     assets=ASSETS_DO_PRODUTO,
                     areas=AREAS_DO_PRODUTO,
                     logo_areas=AREAS_DO_LOGO_DO_PRODUTO)


def assets_da_instalacao() -> dict[str, str]:
    """Os caminhos das imagens que ESTA instalação tem guardadas.

    Só entra o que existe: campo ausente fica de fora do dicionário, e não
    chega como string vazia — o `Assets` tem o próprio padrão, e o template
    decide o que desenhar quando não há logo (`{% if %}` em vez de `<img>`
    apontando para um 404).
    """
    from .models import LUGARES_DA_IMAGEM, ImagemDaMarca

    existentes = set(ImagemDaMarca.objects.values_list("lugar", flat=True))
    dados: dict[str, str] = {}
    for lugar in existentes & set(LUGARES_DA_IMAGEM) - {"favicon"}:
        dados[f"{lugar}_logo"] = f"{CAMINHO_DA_IMAGEM}{lugar}"
    if "favicon" in existentes:
        dados["favicon"] = f"{CAMINHO_DA_IMAGEM}favicon"
    return dados


#: O rótulo do campo de identificação na tela de entrada.
#:
#: **Só o rótulo.** O campo continua se chamando `usuario` no HTML porque é o
#: `name` que `nucleo/layout.py::LoginPage.campos_da_marca()` emite, e
#: `nucleo/` é porte verbatim que não se emenda aqui. O que a pessoa digita
#: passou a ser o e-mail quando o usuário virou nosso (`contas.models.Usuario`,
#: `USERNAME_FIELD = "email"`), e uma tela que pedisse "Usuário" e recusasse
#: "ana" seria a tela mentindo sobre o que ela quer.
ENTRADA_POR_EMAIL = {
    "identifier_label": "E-mail",
    "identifier_placeholder": "Seu e-mail",
}


def marca_da_instalacao() -> Brand:
    """A marca gravada, ou o padrão da MW5 se ninguém configurou ainda.

    As imagens entram por substituição da dataclass (`replace`), nunca por
    mutação: `Brand` é congelada, e é essa imutabilidade que deixa a mesma
    instância circular pela requisição sem sustos.
    """
    from .models import Marca

    linha = Marca.objects.first()
    brand = linha.para_brand() if linha else MARCA_PADRAO

    # O logo do produto é o piso, e não o teto: a instalação nova nasce
    # vestida, e o que o cliente enviar cobre a entrada e o menu. O rodapé
    # não entra nessa conta — `assets_da_instalacao()` nunca devolve
    # `footer_logo`, e é aqui que isso vira garantia em vez de coincidência.
    enviados = assets_da_instalacao()
    assets = {**enviados, "footer_logo": LOGO_DO_PRODUTO_RODAPE}

    # A medida acompanha o desenho, e não a instalação. A do rodapé vale
    # sempre, porque o logo de lá é sempre o mesmo. A da barra só vale
    # enquanto o logo da barra for o do produto: a marca do KRONOS é
    # empilhada e pede 84px, mas a marca deitada de um cliente nesses 84px
    # ficaria um retângulo largo e gordo no alto do menu.
    areas = dict(brand.logo_areas)
    if "sidebar_logo" in enviados:
        # `pop`, e não "deixar de somar": sem o cliente configurado, `brand`
        # É a `MARCA_PADRAO` e já traz os 84px dentro. Só não acrescentar
        # deixaria o logo do cliente na altura da marca do KRONOS.
        areas.pop("logo-side-h", None)
    else:
        areas["logo-side-h"] = AREAS_DO_LOGO_DO_PRODUTO["logo-side-h"]
    areas.update(AREAS_DO_RODAPE)

    return replace(
        brand,
        assets=replace(ASSETS_DO_PRODUTO, **assets),
        logo_areas=areas,
        # Aqui, e não em `MARCA_PADRAO`: a instalação que já configurou a
        # marca vem por `linha.para_brand()`, que não passa por lá. Posto nos
        # dois lugares, o rótulo divergiria no dia em que um deles mudasse.
        login=replace(brand.login, **ENTRADA_POR_EMAIL),
    )


#: O mínimo da WCAG AA para texto normal. Abaixo disso a pessoa não lê.
CONTRASTE_MINIMO = 4.5


def conferir_legibilidade(fundo: str, texto: str) -> "str | None":
    """A frase de recusa, ou `None` se o par é legível.

    Recusar na hora da escolha, e não depois de salvar: quem escolhe amarelo
    claro de fundo com texto branco descobre no momento, não quando o cliente
    liga dizendo que não enxerga o menu.
    """
    from nucleo.theme import contrast_ratio

    if not fundo or not texto:
        return None
    razao = contrast_ratio(fundo, texto)
    if razao >= CONTRASTE_MINIMO:
        return None
    return (
        f"O texto não fica legível sobre esse fundo "
        f"(contraste {razao:.1f}, o mínimo é {CONTRASTE_MINIMO})."
    )
