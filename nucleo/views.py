"""As views do núcleo: a folha de tema, o início e a tela de demonstração.

A marca (`Brand`) e o menu (`Site.nav`) já vêm do banco a cada requisição:
a marca via `plataforma.marca.marca_da_instalacao`, o menu via
`plataforma.menu.montar`. O `Site` é montado de novo em cada view — nunca
mutado como um global compartilhado, porque um `Site` de módulo mutado a
cada requisição vira corrida no dia em que ele passar a variar por
instalação.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.timezone import localtime

from comum.ambiente import ambiente
from comum.guardas_de_acesso import exigir_login
from comum.personificacao import aviso as aviso_de_personificacao
from plataforma.marca import marca_da_instalacao
from plataforma.site import montar_site

from .components import (
    Accordion, AccordionItem, ActionBar, Alert, Avatar, Badge, Box, Button,
    Card, Cell, Chart, Checkbox, Column, DashedButton, DataPoint,
    DefinitionList, Drawer, Dropdown, DropdownItem, EmptyState, ErrorState,
    Fact, FileInput, FilterBar, Form, FormGrid, Heading, Icon, IconButton,
    InputGroup, ItemRow, Mapa, Modal, ModuleCard, ModuleGrid, Option,
    Pagination, PageHeader, Pill, Protected, SearchInput, SectionLabel,
    Select, Slot, Spinner, StatCard, Step, Stepper, Summary, Tab, Table,
    Tabs, TextInput, Textarea, Timeline, TimelineEvent, Toast,
)
from .layout import Crumb
from .rendering import use_environment
from .resposta import render as render_componente
from .theme import render_theme_css

__all__ = ["demonstracao", "home", "tema_css", "versao"]

#: Por extenso, e não via `strftime("%A")`/`"%B"`: aquele formato lê o nome do
#: mês e do dia da semana do locale do SISTEMA OPERACIONAL — variando (ou
#: caindo em inglês) conforme a máquina que serve a requisição, sem que nada
#: no código acuse o erro. Uma tupla fixa lê igual em qualquer ambiente.
_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
#: `date.weekday()`: segunda-feira é 0.
_DIAS_DA_SEMANA = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)


def _data_de_hoje() -> str:
    """A data de hoje por extenso, em português — "quinta-feira, 20 de
    agosto de 2026". `localtime()`, não `date.today()`: a segunda respeita o
    fuso configurado (`TIME_ZONE`), a primeira lê o relógio do servidor cru —
    e um servidor em UTC viraria o dia horas antes de meia-noite local.
    """
    agora = localtime()
    return (
        f"{_DIAS_DA_SEMANA[agora.weekday()]}, {agora.day} de "
        f"{_MESES[agora.month - 1]} de {agora.year}"
    )


def tema_css(request) -> HttpResponse:
    """A folha de tema do cliente, gerada na requisição.

    `no-cache` porque o conteúdo muda quando alguém mexe na cor, e não quando
    um arquivo é publicado: um navegador que guarda esta folha mostra a cor de
    ontem sem nenhum sinal de que está errado.
    """
    resposta = HttpResponse(render_theme_css(marca_da_instalacao()), content_type="text/css")
    resposta["Cache-Control"] = "no-cache"
    return resposta


def versao(request) -> JsonResponse:
    """O RG desta instalação: o commit que está rodando (ver
    tests/test_versao.py e a spec do painel).

    Aberta (ver `TELAS_ABERTAS`) e devolve o commit e NADA MAIS — nunca
    versão de framework, caminho ou ambiente. O repositório é privado, então
    um hash de 40 caracteres é opaco: diz que mudou, não diz o quê. É esse
    limite que sustenta a rota estar sem guarda; qualquer campo a mais
    transformaria um dado opaco em impressão digital da instalação.

    O `try` cobre arquivo ausente, sem permissão de leitura ou vazio: esta
    rota responde num servidor onde o passo de build pode nunca ter
    rodado, e nunca pode devolver 500 por causa disso.
    """
    arquivo = Path(settings.BASE_DIR) / "VERSAO"
    try:
        commit = arquivo.read_text(encoding="utf-8").strip() or "desenvolvimento"
    except OSError:
        commit = "desenvolvimento"
    return JsonResponse({"commit": commit})


def _miolo():
    """Todo componente do design system que é desenhável sozinho, uma vez cada.

    Os nomes de parâmetro saem das dataclasses de `components/`: o corpo de um
    contêiner é `body`, não `children`; o texto de um `Alert` é `message`; o de
    um `Pill` e de um `Badge` é `label`. As variantes de `Button` são as quatro
    de `Button.VARIANTS` — `default`, `primary`, `ghost`, `danger`. Os tons são
    os cinco de `TONES` — `neutral`, `ok`, `info`, `warn`, `danger`.

    Sete dos 58 exportados por `nucleo.components` não aparecem como cartão
    próprio porque não são desenháveis sozinhos — são peça de outro
    componente, ou utilitário sem forma visual fixa:

    - `Option` — as opções de um `Select` (usado no card "Campos").
    - `DataPoint` — os pontos de um `Chart` (card "Gráficos").
    - `Column` — as colunas de uma `Table` (card "Tabela").
    - `Cell` — célula avulsa de uma grade de 12; usada aqui dentro do
      `FormGrid` do card "Gráficos", posicionando cada `Chart` lado a lado.
    - `Slot` — um alvo de troca HTMX, um espaço reservado que a resposta do
      servidor preenche depois; mostrado com conteúdo estático no card
      "Itens", que é como ele aparece antes de qualquer troca acontecer.
    - `Protected` — não desenha nada por si: mostra ou esconde o que recebe
      conforme `allowed`. Demonstrado no card "Ações", em volta do botão
      "Aprovar solicitação" — com `allowed=True` o botão aparece; a marca
      dele é justamente não deixar marca própria no HTML.
    - `Raw` — injeta HTML literal, escapando a regra de que todo componente
      vem de um template; não há o que "demonstrar" nele além do próprio
      texto que alguém passasse, e nenhuma tela desta demonstração precisa
      de HTML cru.
    """
    return [
        PageHeader(title="Componentes",
                   subtitle="O design system inteiro, numa tela"),
        Card(title="Números", body=Box(body=[
            StatCard(label="Instalações", value="20"),
            StatCard(label="Módulos", value="7"),
        ])),
        Card(title="Avisos", body=[
            Alert(message="Um aviso informativo.", tone="info"),
            Alert(message="Um aviso de atenção.", tone="warn"),
            Alert(message="Um aviso de erro.", tone="danger"),
        ]),
        Card(title="Marcadores", body=Box(body=[
            Pill(label="Ativo", tone="ok"),
            Badge(label="Badge de teste"),
            Avatar(name="Rita Oliveira"),
        ])),
        Card(title="Ações", body=Box(body=[
            Button(label="Primário", variant="primary"),
            Button(label="Comum"),
            Button(label="Discreto", variant="ghost"),
            Button(label="Remover", variant="danger"),
            # `Protected` não desenha molde nenhum — só decide se o que está
            # dentro aparece. Com `allowed=True` o botão renderiza normal;
            # com `False` desenharia o `fallback` no lugar.
            Protected(allowed=True,
                      children=Button(label="Aprovar solicitação", variant="primary"),
                      fallback=Alert(message="Sem permissão para aprovar.", tone="warn")),
        ])),
        Card(title="Tabela", padded=False, body=Table(
            columns=[Column("cidade", "Cidade"), Column("uf", "UF")],
            rows=[{"cidade": "Campinas", "uf": "SP"},
                  {"cidade": "Ribeirão Preto", "uf": "SP"}],
        )),
        Card(title="Abas", body=Tabs(tabs=[
            Tab(label="Uma", body="Conteúdo da primeira.", active=True),
            Tab(label="Outra", body="Conteúdo da segunda."),
        ])),
        Card(title="Linha do tempo", body=Timeline(events=[
            TimelineEvent(label="Criado", when="Há dois dias", state="done"),
            TimelineEvent(label="Aprovado", when="Ontem"),
        ])),
        Card(title="Vazio", body=EmptyState(
            title="Nada por aqui", message="Nenhum registro ainda.")),
        Card(title="Erro", body=ErrorState(
            title="Não foi possível carregar as tarifas",
            message="Tentativa de leitura falhou — tente novamente.",
            actions=Button(label="Tentar de novo", variant="ghost"),
        )),
        Card(title="Textos e resumo", body=Box(body=[
            Heading(title="Resumo do cálculo",
                    support="Valores da última simulação de frete",
                    size="pagina"),
            SectionLabel(label="Detalhamento"),
            DefinitionList(
                items=[Fact("Distância", "320 km"), Fact("Peso", "180 kg")],
                total_label="Total estimado", total_value="R$ 842,00",
            ),
            Summary(stats=StatCard(label="Pedidos em aberto", value="12")),
        ])),
        Card(title="Itens", body=Box(body=[
            ItemRow(title="Carlos Mendes",
                    subtitle="Motorista credenciado", icon="truck"),
            DashedButton(label="Adicionar parada"),
            # `Slot` reserva o lugar; quem preenche de verdade é uma resposta
            # HTMX. Aqui, com `content` fixo, ele mostra como o placeholder
            # aparece antes de qualquer troca.
            Slot(id="painel-lateral-demo", content=Alert(
                message="Este bloco é o alvo de uma troca HTMX.", tone="info")),
        ])),
        Card(title="Menus", body=Box(body=[
            Dropdown(id="menu-exemplo", title="Ações rápidas", items=[
                DropdownItem(label="Duplicar", icon="copy"),
                DropdownItem(label="Arquivar", icon="folder"),
                DropdownItem(divider=True),
                DropdownItem(label="Excluir", icon="trash", danger=True),
            ]),
            Accordion(items=[
                AccordionItem(title="Perguntas frequentes",
                               body="Como funciona o cálculo de frete?",
                               open=True),
                AccordionItem(title="Política de cancelamento",
                               body="Cancelamentos até 24h antes."),
            ]),
        ])),
        Card(title="Progresso", body=Stepper(steps=[
            Step("Pedido criado", state="done"),
            Step("Em rota", state="cur"),
            Step("Entregue", state="pending"),
        ])),
        Card(title="Módulos", padded=False, body=ModuleGrid(cards=[
            ModuleCard(title="Fretes", href="/fretes", icon="truck",
                       description="Simulação e acompanhamento", badge="Beta"),
            ModuleCard(title="Clientes", href="/clientes", icon="users",
                       description="Cadastro e histórico"),
        ])),
        # Sem `url`: mostra o estado de aviso do próprio componente, não um
        # endereço de verdade. Testado com uma URL real também — o iframe
        # sobe, mas o conteúdo que o Google devolve para um `pb` inventado
        # não é confiável (variou entre vazio e um mapa genérico em duas
        # cargas seguidas nesta mesma máquina). Uma tela de demonstração não
        # pode depender da rede de terceiro para não parecer quebrada; o
        # estado sem endereço é 100% determinístico e é comportamento real do
        # componente, não um substituto artificial.
        Card(title="Mapa", body=Mapa()),
        # `duration=0` porque `mw5.js` arma o auto-esconder em TODO `.toast`
        # da página (`armToast`), não só nos que passam pelo host de toasts
        # (`#toasts`) — sem isto, o cartão esvaziava sozinho 5 segundos depois
        # de a página abrir. Achado renderizando de verdade e tirando
        # screenshot; ver o relatório desta correção.
        Card(title="Notificação", body=Toast(
            title="Feito", message="Registro salvo com sucesso.", tone="ok",
            duration=0)),
        Card(title="Buscar e filtrar", body=FilterBar(
            fields=TextInput(name="busca_filtro", label="Cidade de origem",
                              placeholder="Ex.: Campinas"),
            submit_label="Aplicar filtro",
            extra_actions=Button(label="Limpar filtros", variant="ghost"),
        )),
        Card(title="Paginação", body=Pagination(page=2, per_page=10, total=47)),
        Card(title="Campos", body=Form(action="#", children=FormGrid(children=[
            TextInput(name="nome_completo", label="Nome completo", span=6,
                      placeholder="Digite o nome"),
            Textarea(name="observacoes", label="Observações", span=6, rows=3,
                     placeholder="Anotações do pedido"),
            Select(name="uf_origem", label="UF de origem", span=4,
                   empty_label="Selecione…",
                   options=[Option("SP", "São Paulo"), Option("MG", "Minas Gerais")]),
            Checkbox(name="urgente", label="Entrega urgente", span=4),
            SearchInput(name="buscar_cliente", label="Buscar cliente", span=4,
                        placeholder="Nome ou CPF"),
            FileInput(name="anexo", label="Comprovante de endereço", span=6),
            InputGroup(name="cep", label="CEP de destino", span=6,
                       button_title="Buscar CEP"),
        ]))),
        # `Cell` posiciona cada gráfico na grade de 12 colunas — é o mesmo
        # mecanismo do `FormGrid` dos campos, só que ao lado de qualquer
        # coisa, não apenas de campo de formulário.
        Card(title="Gráficos", body=FormGrid(children=[
            Cell(span=6, children=Chart(kind="bar", title="Entregas por mês",
                 points=[DataPoint("Jan", 120), DataPoint("Fev", 95),
                         DataPoint("Mar", 140)])),
            Cell(span=6, children=Chart(kind="bar_h", title="Tempo médio por rota",
                 points=[DataPoint("Norte", 3.2), DataPoint("Sul", 2.4),
                         DataPoint("Leste", 4.1)])),
            Cell(span=6, children=Chart(kind="line", title="Custo por km",
                 points=[DataPoint("Sem 1", 1.8), DataPoint("Sem 2", 1.6),
                         DataPoint("Sem 3", 1.9)])),
            Cell(span=6, children=Chart(kind="pie", title="Modalidade de frete",
                 points=[DataPoint("Rodoviário", 60), DataPoint("Aéreo", 25),
                         DataPoint("Marítimo", 15)])),
            Cell(span=6, children=Chart(kind="donut", title="Status das entregas",
                 points=[DataPoint("Entregue", 70), DataPoint("Em trânsito", 20),
                         DataPoint("Atrasado", 10)])),
        ])),
        Card(title="Ícones e ações pequenas", body=Box(body=[
            IconButton(icon="bell", title="Ver notificações de teste"),
            Spinner(label="Carregando relatório..."),
            Icon(name="star", label="Favorito"),
        ])),
    ]


# `home` é a tela que qualquer um vê depois de entrar — só uma saudação e a
# data de hoje; indicadores entram numa entrega futura (ver o relatório desta
# correção). É view autoral desta base, então pode levar a guarda aqui dentro
# de `nucleo/`, e pelo mesmo motivo leva o aviso de personificação (Task 11):
# é o primeiro lugar onde alguém personificando pousa depois de
# `personificar` — o pior lugar do sistema para esquecer o aviso, porque é
# de lá que o "esqueci que estava personificando" começaria.
@exigir_login
def home(request):
    """O início: uma saudação com o primeiro nome de quem entrou, e a data
    de hoje. Nada além disso, de propósito — ver o docstring do módulo."""
    env = ambiente()
    with use_environment(env):
        # O `Site` nasce aqui, a cada requisição — nunca mutado como um
        # global de módulo (mesmo motivo do comentário em `demonstracao`,
        # abaixo). `montar_site` (`plataforma/site.py`) é o lugar único que
        # monta marca, menu e a linha de contexto do cabeçalho — nenhuma tela
        # reconstrói isso à mão.
        site = montar_site(request)
        pagina = site.page(
            # `full`: a tela usa a largura toda. Estas telas são tabela e
            # formulário — espremer uma tabela em 1400px num monitor largo
            # desperdiça a metade direita e ainda quebra coluna.
            title="Início",
            width="full",
            content=[
                aviso_de_personificacao(request),
                # `{nome}` é resolvido por `site.resolve_nome` — o mesmo
                # mecanismo de `{sistema}` e `{ano}` (ver `Site.resolve_nome`
                # e os testes em `test_components.py`), pensado exatamente
                # para esta saudação.
                PageHeader(
                    title=site.resolve_nome("Olá, {nome}!", request.usuario),
                    subtitle=_data_de_hoje(),
                ),
            ],
            crumbs=[Crumb("Início")],
            user=request.usuario,
        )
        # A renderização tem que acontecer AQUI dentro — ver o comentário
        # equivalente em `demonstracao`, abaixo.
        return render_componente(pagina)


# `demonstracao` também é autoral (criada na entrega 1) — a referência viva
# do design system, e a única tela que exercita os 58 componentes. Mudou de
# endereço (era "/", virou "/demonstracao") quando o cliente rejeitou uma
# vitrine de componentes como primeira tela depois do login; continua atrás
# de `exigir_login` e chamando o aviso de personificação pelo mesmo motivo de
# `home`, acima — ver `retrabalho-visual-report.md` para a decisão.
@exigir_login
def demonstracao(request):
    """A tela que prova a entrega 1."""
    env = ambiente()
    with use_environment(env):
        # O `Site` nasce aqui, a cada requisição — nunca mutado como um
        # global de módulo. `SITE.brand = ...; SITE.nav = ...` mutava um
        # objeto compartilhado por toda requisição: idempotente enquanto há
        # uma instalação só, mas vira corrida no dia em que o `Site` passar a
        # variar por cliente. `montar_site` é o mesmo lugar único usado por
        # `home`, acima — ver o comentário lá.
        site = montar_site(request)
        pagina = site.page(
            # `full`: a tela usa a largura toda. Estas telas são tabela e
            # formulário — espremer uma tabela em 1400px num monitor largo
            # desperdiça a metade direita e ainda quebra coluna.
            title="Componentes",
            width="full",
            # `aviso_de_personificacao` na FRENTE de `_miolo()`, mesmo molde
            # de toda outra tela que já chama este helper — "" fora de
            # personificação, o `Alert` de aviso durante.
            content=[aviso_de_personificacao(request), *_miolo()],
            crumbs=[Crumb("Componentes")],
            user=request.usuario,
            # `ActionBar` é da página, não do miolo: fica fixa no rodapé por
            # cima do conteúdo, então é `Site.page()` quem a recebe.
            action_bar=ActionBar(actions=Button(label="Salvar alterações", variant="primary"),
                                  hint="Alterações não salvas"),
            overlays=[
                Modal(id="exemplo", title="Um modal",
                      body="O conteúdo do modal."),
                Drawer(id="detalhe", title="Detalhes da entrega",
                       body="Informações completas do pedido selecionado."),
            ],
        )
        # A renderização tem que acontecer AQUI dentro: `site.page()` só monta
        # as dataclasses da página, quem desenha é `render_componente`
        # (`.render()`). Fora do `with`, o `env` criado acima já saiu de
        # cena e a renderização cai no ambiente global — inclusive
        # ignorando em silêncio qualquer loader extra passado a
        # `create_environment(*extra_loaders)`.
        return render_componente(pagina)
