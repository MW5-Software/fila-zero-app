"""As telas que só a MW5 vê: Aparência e Módulos."""

from __future__ import annotations

from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from nucleo.components import (
    Alert, Box, Button, Card, Checkbox, Form, FormGrid, Option, PageHeader,
    Raw, SectionLabel, Select, TextInput,
)
from nucleo.layout import Crumb
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render
from nucleo.theme import render_theme_css

from .catalogo import semear
from .declaracao import declarados
from .marca import conferir_legibilidade, marca_da_instalacao
from .models import Marca, Modulo
from .site import montar_site
from .views_marca import MENSAGEM_LOGO_REMOVIDA, MENSAGEM_LOGO_SALVA, cartao_de_logos

__all__ = ["aparencia", "aparencia_previa", "modulos"]

#: O que fica na tela, do jeito que a pessoa procura.
#:
#: A tela nasceu com os dezessete campos numa grade só, sob um título só —
#: "Nome do cliente" ao lado de "Arredondamento dos controles". Cada campo
#: estava certo e o conjunto era ilegível: para achar a cor do menu era
#: preciso ler os dezessete.
#:
#: Agora a ordem é por ASSUNTO, e é ela que manda em tudo: os campos que a
#: tela desenha, os que o POST lê e os que a prévia consulta saem todos daqui
#: (`CAMPOS`, logo abaixo). Campo novo entra numa seção — não há como
#: acrescentá-lo à tela e esquecer de gravá-lo.
#:
#: Forma: (título do cartão, frase de apoio, seções), e cada seção é
#: (rótulo ou None, campos), com campo = (nome no model, rótulo, colunas,
#: ajuda).

#: A frase que explica o vazio. Repetida em toda cor de área de propósito:
#: quem está olhando um campo em branco precisa da explicação NAQUELE campo,
#: e não num aviso no alto que ele já passou.
_HERDA = "Vazio herda a cor do tema."

CARTOES = (
    ("Identidade",
     "Como o sistema se apresenta para este cliente.",
     ((None, (
         ("client_name", "Nome do cliente", 6,
          "Aparece no título da aba e como descrição do logo."),
         ("system_name", "Nome do sistema", 6,
          "Vazio usa o nome do cliente."),
     )),)),

    ("Cores",
     "A tela repinta enquanto você mexe: o que aparecer aqui é o que fica salvo.",
     ((None, (
         ("primary", "Cor primária", 6,
          "Botões, links e o que está selecionado."),
         ("accent", "Cor de destaque", 6,
          "Etiquetas e contadores, ao lado da primária."),
     )),
      ("Menu", (
          ("sidebar_bg", "Fundo", 6, _HERDA),
          ("sidebar_text", "Texto", 6, _HERDA),
      )),
      ("Cabeçalho", (
          ("header_bg", "Fundo", 6, _HERDA),
          ("header_text", "Texto", 6, _HERDA),
      )),
      ("Conteúdo e rodapé", (
          ("content_bg", "Fundo do conteúdo", 4, _HERDA),
          ("footer_bg", "Fundo do rodapé", 4, _HERDA),
          ("footer_text", "Texto do rodapé", 4, _HERDA),
      )))),

    ("Forma e densidade",
     "O quanto os cantos são arredondados e o quanto a tela respira.",
     ((None, (
         ("radius", "Arredondamento", 4,
          "Dos cartões e caixas. Ex.: 6px."),
         ("radius_control", "Arredondamento dos controles", 4,
          "Dos botões e campos, que costumam pedir menos que os cartões."),
         ("sidebar_width", "Largura do menu", 4,
          "Ex.: 256px."),
     )),)),

    ("Vocabulário",
     "Como este cliente chama as coisas — o seletor do cabeçalho segue estes nomes.",
     ((None, (
         ("rotulo_da_empresa", "Rótulo da empresa", 6,
          'Vazio usa "Empresa". Uma rede pode chamar de bandeira.'),
         ("rotulo_da_filial", "Rótulo da filial", 6,
          'Vazio usa "Filial". Um varejo pode chamar de loja.'),
     )),)),
)

#: Os campos de texto que a tela edita, achatados a partir de `CARTOES`.
#: Derivado, e não escrito de novo: duas listas do mesmo conjunto divergem no
#: dia em que alguém acrescentar um campo numa e esquecer da outra — e o
#: sintoma seria um campo que a tela mostra e o POST não grava.
CAMPOS = tuple(
    (nome, rotulo, colunas)
    for _resto, _resto, secoes in CARTOES
    for _resto, campos in secoes
    for nome, rotulo, colunas, _resto in campos
)

#: A ajuda de cada campo, pela mesma fonte.
AJUDA = {
    nome: ajuda
    for _resto, _resto, secoes in CARTOES
    for _resto, campos in secoes
    for nome, _resto, _resto, ajuda in campos
}

#: As três densidades que o design system conhece (`_tokens.DENSITIES`), com
#: o rótulo que a pessoa lê. A validação em si é do `Brand.from_dict` — aqui
#: só se oferece o vocabulário certo.
DENSIDADES = (
    ("compact", "Compacta"),
    ("normal", "Normal"),
    ("comfortable", "Confortável"),
)

#: As caixinhas: o banco já guardava, o CSS já consumia, a tela é que não
#: mostrava. Um checkbox desmarcado NÃO vem no POST — ausência significa
#: "não quero".
CAIXINHAS = (
    ("shadows", "Sombras"),
    ("zebra", "Tabela listrada"),
)

#: Pares fundo/texto que precisam ser legíveis um sobre o outro.
PARES_DE_CONTRASTE = (
    ("sidebar_bg", "sidebar_text", "menu"),
    ("header_bg", "header_text", "cabeçalho"),
    ("footer_bg", "footer_text", "rodapé"),
)


def _valores_de(linha: "Marca | None") -> dict[str, str]:
    """Os valores que a tela mostra: os da linha gravada, ou os de uma
    `Marca` em branco quando a instalação ainda não tem nenhuma."""
    origem = linha or Marca()
    valores = {nome: getattr(origem, nome) or "" for nome, _resto, _resto in CAMPOS}
    # A densidade viaja junto: é escolhida num `Select`, mas é um valor do
    # model como os outros — e o `Select` precisa saber qual vem selecionada.
    valores["density"] = getattr(origem, "density") or "normal"
    return valores


def _caixinhas_de(linha: "Marca | None") -> dict[str, bool]:
    """O estado das duas caixinhas: o que está valendo agora."""
    origem = linha or Marca()
    return {nome: bool(getattr(origem, nome)) for nome, _resto in CAIXINHAS}


def _validar(dados: dict[str, str]) -> "str | None":
    """A frase de recusa, ou `None` se os dados podem ser gravados.

    A cor passa por `Brand.from_dict` (via `Marca.para_brand`), que já sabe
    validar hex e já levanta `ValueError` — não há o que reimplementar aqui.
    O contraste é conferido depois, par a par: recusar na hora da escolha, e
    não depois de salvo.
    """
    try:
        Marca(**dados).para_brand()
    except ValueError as exc:
        return str(exc)

    for fundo, texto, area in PARES_DE_CONTRASTE:
        aviso = conferir_legibilidade(dados.get(fundo, ""), dados.get(texto, ""))
        if aviso:
            return f"{aviso} Área: {area}."
    return None


def _extras(valores: dict[str, str], caixinhas: dict[str, bool]) -> list:
    """Os controles que não são campo de texto: a caixa de densidade e as
    duas caixinhas de estrutura. Moram no cartão de forma, junto do
    arredondamento — é a mesma pergunta feita de outro jeito."""
    return [
        Select(name="density", label=_("Densidade"), span=4,
               value=valores.get("density", "normal"),
               help="O quanto a tela respira entre uma linha e outra.",
               options=[Option(valor, rotulo) for valor, rotulo in DENSIDADES]),
        Checkbox(name="shadows", label=_("Sombras"), span=4,
                 checked=caixinhas.get("shadows", False)),
        Checkbox(name="zebra", label=_("Tabela listrada"), span=4,
                 checked=caixinhas.get("zebra", False)),
    ]


def _cartao(titulo: str, apoio: str, secoes, valores: dict[str, str],
            depois: "list | None" = None) -> Card:
    """Um cartão da tela, com as suas seções.

    Cada seção vira uma grade própria, e o rótulo entre elas é o que separa
    "a cor do menu" de "a cor do cabeçalho" — antes eram oito campos seguidos
    cujo agrupamento só existia na cabeça de quem escreveu.
    """
    miolo: list = []
    for rotulo, campos in secoes:
        if rotulo:
            miolo.append(SectionLabel(label=rotulo))
        miolo.append(FormGrid(children=[
            TextInput(name=nome, label=texto, span=cols,
                      value=valores.get(nome, ""), help=ajuda)
            for nome, texto, cols, ajuda in campos
        ]))
    if depois:
        miolo.append(FormGrid(children=depois))
    return Card(title=titulo, subtitle=apoio, body=miolo)


def _desenhar(request, valores: dict[str, str], caixinhas: "dict[str, bool] | None" = None,
              erro: "str | None" = None, ok: "str | None" = None) -> HttpResponse:
    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        conteudo = [
            PageHeader(title=_("Aparência"),
                       subtitle=_("A cara desta instalação — muda a tela inteira, sem publicar versão nova.")),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))
        elif ok:
            conteudo.append(Alert(message=ok, tone="success"))
        marcadas = (caixinhas if caixinhas is not None
                    else _caixinhas_de(Marca.objects.first()))
        # Um formulário só, com um "Salvar" só, embrulhando vários cartões.
        # Os cartões são a leitura; o formulário é a gravação, e são coisas
        # diferentes: quem trocou a cor do menu e o rótulo da filial não
        # deveria precisar salvar duas vezes porque a tela desenhou dois
        # quadros. A `Box` é quem separa cartão de cartão fora do `main` —
        # ver o comentário de `.card` na `mw5.css`.
        cartoes = [
            _cartao(titulo, apoio, secoes, valores,
                    depois=_extras(valores, marcadas)
                    if titulo == "Forma e densidade" else None)
            for titulo, apoio, secoes in CARTOES
        ]
        conteudo.append(Form(action=reverse("aparencia"), attrs={
            # O script de prévia usa este endereço para recolorir a tela
            # enquanto o formulário é editado — a ligação vive na tela,
            # não num seletor solto dentro do script.
            "data-mw5-previa": reverse("aparencia_previa"),
        }, children=[
            Raw(html=campo_csrf(request)),
            Box(body=cartoes, gap="md"),
            Button(label=_("Salvar"), variant="primary", type="submit"),
        ]))
        conteudo.append(cartao_de_logos(request))
        # A prévia ao vivo: o script troca o `href` da folha de tema para a
        # rota da prévia enquanto o formulário é editado. O `<script>` entra
        # via `Raw` — mesmo caminho autorizado do campo CSRF: HTML cru já
        # confiável, porque o design system não tem slot para script extra.
        conteudo.append(Raw(html=format_html(
            '<script src="{}" defer></script>', static("plataforma/previa.js"))))
        pagina = site.page(
            # `full`: a tela usa a largura toda. Estas telas são tabela e
            # formulário — espremer uma tabela em 1400px num monitor largo
            # desperdiça a metade direita e ainda quebra coluna.
            title=_("Aparência"),
            width="full",
            content=conteudo,
            crumbs=[Crumb(_("Aparência"))],
            user=getattr(request, "usuario", None),
        )
        # A renderização acontece AQUI dentro: `Site.page()` só monta as
        # dataclasses da página, quem desenha é `render` (`.render()`). Fora
        # do `with`, a renderização cairia no ambiente global e um override
        # de template do cliente seria ignorado em silêncio.
        return render(pagina)


# Acesso da MW5 vem de `is_superuser`, e não de um grupo chamado `mw5`.
# O nome da permissão documenta a intenção; quem passa é o superusuário
# (ver `pode`). Conceder isso por nome de grupo seria escalação: o admin do
# cliente vai poder criar grupos, e cunharia para si a administração da MW5.
def _frase_do_logo(request) -> "str | None":
    """A frase de sucesso do card de logos, se a URL trouxer o sinalizador.

    A tela lê a PRESENÇA da chave, nunca o valor (mesmo padrão de Meu
    Perfil): `?logo=` e `?logorem=` só dizem qual gesto acabou de acontecer.
    """
    if "logo" in request.GET:
        return MENSAGEM_LOGO_SALVA
    if "logorem" in request.GET:
        return MENSAGEM_LOGO_REMOVIDA
    return None


def _dados_da_aparencia(request, linha) -> dict:
    """Os campos do POST, com as medidas em branco repostas.

    Medida em branco significa "mantém a de agora", e não "apaga": um
    `Brand` recusa medida vazia, e o navegador sempre reenvia o que a tela
    mostrou — só um POST parcial chega sem elas.
    """
    dados = {nome: request.POST.get(nome, "") for nome, _resto, _resto in CAMPOS}
    dados["density"] = request.POST.get("density", "")

    origem = linha or Marca()
    for campo in ("radius", "sidebar_width", "radius_control"):
        if not dados[campo]:
            dados[campo] = getattr(origem, campo)
    if not dados["density"]:
        dados["density"] = origem.density or "normal"
    return dados


@exigir_permissao("mw5.aparencia")
def aparencia(request) -> HttpResponse:
    """A tela onde a MW5 troca a cara de uma instalação.

    `?logo=` e `?logorem=` na URL são só sinalizadores das ações do card de
    logos — a tela lê a PRESENÇA da chave, nunca o valor, e mostra a frase
    fixa correspondente (mesmo padrão de Meu Perfil).
    """
    linha = Marca.objects.first()

    if request.method != "POST":
        return _desenhar(request, _valores_de(linha), _caixinhas_de(linha),
                         ok=_frase_do_logo(request))

    dados = _dados_da_aparencia(request, linha)
    caixinhas = {nome: request.POST.get(nome) == "on" for nome, _resto in CAIXINHAS}

    erro = _validar(dados)
    if erro:
        return _desenhar(request, dados, caixinhas, erro=erro)

    # Uma instalação, uma marca: sempre a mesma linha, nunca uma segunda.
    # `atomic()`: se `registrar` falhar, a troca de marca desfaz junto — não
    # fica uma aparência nova plantada sem ninguém saber quem trocou.
    with transaction.atomic():
        Marca.objects.update_or_create(pk=linha.pk if linha else None,
                                       defaults={**dados, **caixinhas})
        # "aparência": só existe uma linha de `Marca` por instalação — não
        # há um nome de entidade mais específico para identificar o que
        # mudou.
        registrar(ACOES.APARENCIA_ALTERADA, request.usuario, alvo="aparência")
    return HttpResponseRedirect(reverse("aparencia"))


def _candidata_da_previa(request, linha, atual) -> dict:
    """Os campos da marca CANDIDATA: o que está gravado, coberto pelo que a
    tela mandou na query.

    Separado de `aparencia_previa` porque são dois assuntos: montar o
    candidato é sobre precedência de valores; a view é sobre devolver CSS
    que nunca some.
    """
    origem = linha or Marca()

    base = {nome: getattr(origem, nome) for nome, _resto, _resto in CAMPOS}
    # Instalação sem linha gravada nenhuma: o `Marca()` em branco não tem
    # nome de cliente, e um `Brand` sem nome é recusado — vale o da marca
    # que está valendo agora.
    if not base.get("client_name"):
        base["client_name"] = atual.client_name
    base["density"] = getattr(origem, "density") or "normal"

    for nome, _resto, _resto in CAMPOS:
        valor = request.GET.get(nome)
        if valor:
            base[nome] = valor
    base["density"] = request.GET.get("density") or base["density"]
    for nome, _resto in CAIXINHAS:
        if request.GET.get(nome) is not None:
            base[nome] = request.GET.get(nome) == "1"
    return base


@exigir_permissao("mw5.aparencia")
def aparencia_previa(request) -> HttpResponse:
    """A folha de tema do CANDIDATO — o que valeria se salvar agora.

    Não é uma segunda implementação das cores: os parâmetros da tela são
    aplicados sobre a linha gravada e passam pela MESMA `Marca.para_brand()`
    (que valida, recusa e deriva os tokens) antes de virar CSS. Valor
    inválido — um hex digitado pela metade, por exemplo — não derruba a
    folha: cai no que está gravado, porque prévia que some é pior que
    prévia atrasada.

    GET de propósito: é leitura pura, chamada pelo script de prévia a cada
    edição, sem token e sem estado.
    """
    atual = marca_da_instalacao()
    base = _candidata_da_previa(request, Marca.objects.first(), atual)

    try:
        candidata = Marca(**base).para_brand()
    except ValueError:
        candidata = atual

    resposta = HttpResponse(render_theme_css(candidata), content_type="text/css")
    # Mesma regra da `/tema.css`: muda quando alguém mexe no formulário,
    # não quando uma versão sai.
    resposta["Cache-Control"] = "no-cache"
    return resposta


def _linhas_por_chave() -> dict[str, Modulo]:
    """As linhas de `Modulo` que já existem no banco, indexadas pela chave."""
    return {linha.chave: linha for linha in Modulo.objects.all()}


def _opcionais() -> tuple:
    """Os módulos que esta tela pode ligar e desligar.

    Tela da MW5 (`ModuloSpec.so_mw5`) fica de fora, e não é preciosismo: esta
    tela grava por AUSÊNCIA — o que não voltar marcado no POST é desligado.
    Se as três aparecessem aqui e alguém salvasse, elas sumiriam do menu; se
    não aparecessem mas continuassem no conjunto que o POST varre, o primeiro
    salvar as desligaria sem ninguém tocar em nada. A mesma lista serve ao
    desenho e à gravação por isso: uma só, e as duas pontas casam.
    """
    return tuple(spec for spec in declarados() if not spec.so_mw5)


def _checkboxes(linhas: dict[str, Modulo]) -> list[Checkbox]:
    """Um `Checkbox` por módulo declarado no código — **todos**, ligados ou
    não: é esta tela que liga e desliga, então o desligado precisa aparecer
    para poder ser marcado.

    Rótulo segue a mesma regra de `catalogo.modulos_ligados()`: o do banco
    vence quando preenchido, senão o do código. `checked` vem só do banco —
    módulo sem linha ainda (fora de ordem com a migração) nasce desmarcado.
    """
    caixas = []
    for spec in _opcionais():
        linha = linhas.get(spec.chave)
        rotulo = (linha.rotulo if linha and linha.rotulo else spec.rotulo)
        caixas.append(Checkbox(
            name="ligados", value=spec.chave, label=rotulo,
            checked=bool(linha and linha.ativo),
        ))
    return caixas


def _desenhar_modulos(request) -> HttpResponse:
    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        conteudo = [
            PageHeader(title=_("Módulos"),
                       subtitle=_("O que esta instalação tem ligado — o resto some do menu.")),
        ]
        if not _opcionais():
            conteudo.append(Alert(
                message=_("Nenhum módulo declarado no código desta instalação."),
                tone="info"))
        else:
            conteudo.append(Card(
                title=_("Módulos declarados"),
                body=Form(action=reverse("modulos"), children=[
                    Raw(html=campo_csrf(request)),
                    FormGrid(children=_checkboxes(_linhas_por_chave())),
                    Button(label=_("Salvar"), variant="primary", type="submit"),
                ]),
            ))
        pagina = site.page(
            # `full`: a tela usa a largura toda. Estas telas são tabela e
            # formulário — espremer uma tabela em 1400px num monitor largo
            # desperdiça a metade direita e ainda quebra coluna.
            title=_("Módulos"),
            width="full",
            content=conteudo,
            crumbs=[Crumb(_("Módulos"))],
            user=getattr(request, "usuario", None),
        )
        # Ver o comentário equivalente em `_desenhar` (Aparência, acima): a
        # renderização precisa acontecer AQUI dentro do `with`, ou cai no
        # ambiente global.
        return render(pagina)


# Acesso da MW5 vem de `is_superuser`, e não de um grupo chamado `mw5` — a
# mesma regra e o mesmo motivo da tela de Aparência, acima: o admin do
# cliente vai poder criar grupos quando a gestão de usuários existir, e
# cunharia por nome de grupo a própria promoção. Superusuário ele não cunha.
@exigir_permissao("mw5.modulos")
def modulos(request) -> HttpResponse:
    """A tela onde a MW5 liga o que o cliente comprou.

    Desligar não apaga a linha do módulo: só marca `ativo=False`. A linha
    guarda as sobrescritas do cliente (rótulo, grupo, ordem), e apagá-la para
    desligar custaria caro demais — perder tudo isso por uma chavinha.
    """
    if request.method != "POST":
        return _desenhar_modulos(request)

    # Sem isto, ligar um módulo que ainda não tem linha no banco (fora de
    # ordem com o `post_migrate` — ver R18) é um no-op silencioso:
    # `filter().update()` atualiza zero linhas, sem erro nenhum, e a
    # checkbox volta desmarcada no próximo carregamento sem explicação.
    # `semear()` só cria o que falta; nunca toca em linha existente.
    semear()

    ligados = set(request.POST.getlist("ligados"))
    # `_opcionais()`, e não `declarados()`: ver o docstring dela. Com
    # `declarados()` aqui, as telas da MW5 entrariam no conjunto que o POST
    # varre sem estarem na tela, e o primeiro salvar as desligaria.
    chaves = {spec.chave for spec in _opcionais()}
    # Lido ANTES do `.update()` abaixo: é o estado anterior que diz quais
    # módulos de fato MUDARAM — sem isso, reenviar a tela sem tocar em nada
    # registraria uma linha "ligado"/"desligado" por módulo a cada salvar,
    # mesmo quando nada mudou.
    ativos_antes = set(
        Modulo.objects.filter(chave__in=chaves, ativo=True)
        .values_list("chave", flat=True)
    )
    # As duas trocas e todo `registrar` do laço, num `atomic()` só: se
    # `registrar` falhar no meio do laço (o segundo módulo de três, por
    # exemplo), a transação inteira desfaz — nenhum módulo fica ligado sem
    # o registro correspondente, e nenhum registro fica sem o módulo que
    # deveria descrever.
    with transaction.atomic():
        Modulo.objects.filter(chave__in=chaves & ligados).update(ativo=True)
        Modulo.objects.filter(chave__in=chaves - ligados).update(ativo=False)

        for chave in sorted((chaves & ligados) - ativos_antes):
            registrar(ACOES.MODULO_LIGADO, request.usuario, alvo=chave)
        for chave in sorted((chaves - ligados) & ativos_antes):
            registrar(ACOES.MODULO_DESLIGADO, request.usuario, alvo=chave)

    return HttpResponseRedirect(reverse("modulos"))
