"""Usuários: a tela onde o titular administra quem existe na conta dele, e
onde cada pessoa está alocada, com qual cargo.

É a tela mais sensível de toda a entrega: é aqui que um admin do cliente
mal-intencionado tentaria cunhar a própria promoção. A defesa é dupla, e as
duas partes têm que valer sempre juntas — nunca só uma:

1. A lista NUNCA mostra `is_superuser=True` (a MW5).
2. TODA ação (editar, ativar, desativar, remover, resetar senha, alocações)
   recusa de novo, sozinha, se o alvo for superusuário.

A (2) existe porque a (1) sozinha não protege nada: quem preenche a tela é o
navegador, mas quem manda o POST é o cliente — e ele pode escrever à mão um
formulário com o id da MW5 dentro, sem passar pela tela nenhuma vez.
`_alcancavel`, abaixo, é o portão único por onde toda ação passa antes de
tocar em qualquer linha.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import ProtectedError, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from nucleo.components import (
    Alert, Badge, Box, Button, Card, Column, Form,
    FormGrid, IconButton, Modal, Option, PageHeader, Raw, SectionLabel,
    Select, Table, TextInput,
)
from nucleo.layout import Crumb
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render
from comum.exportacao import ColunaDeExportacao, botoes, preparar_exportacao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina

from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from .models import Nivel, Usuario
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.permissoes import SENHA_MINIMA

__all__ = ["usuarios"]

#: Bem acima de `nucleo.permissoes.SENHA_MINIMA` (8): a senha temporária não
#: pode, por azar do gerador aleatório, cair abaixo do próprio mínimo que a
#: tela de Meu Perfil exige na troca.
TAMANHO_DA_SENHA_TEMPORARIA = 16


def _rodape(rotulo: str) -> str:
    """As ações no fim, separadas por um fio e encostadas à direita.

    Num formulário desta altura o botão solto no fluxo se confunde com mais um
    campo — era o que acontecia aqui: "Criar usuário" nascia colado no último
    grupo de caixas, na largura de um controle qualquer, e quem rolava até o
    fim não via onde o formulário terminava.

    "Cancelar" fecha o modal por `data-modal-close`, do design system, e não
    envia nada.
    """
    from django.utils.html import format_html

    return format_html(
        '<div class="ct-rodape">'
        '<button type="button" class="btn ghost" data-modal-close>'
        'Cancelar</button>'
        '<button type="submit" class="btn primary">{}</button></div>',
        rotulo)


def _limite(campo: str) -> int:
    """O `max_length` da coluna do `contas.Usuario`, para o campo da tela não
    aceitar mais do que o banco guarda."""
    return Usuario._meta.get_field(campo).max_length


def _campo_oculto(nome: str, valor: str) -> str:
    """`nucleo/` não tem componente de campo oculto, só `Raw` para
    HTML cru já confiável. `valor` nunca é texto de fora sem controle: é
    sempre um `pk` ou uma constante fixa desta view.
    """
    from django.utils.html import format_html

    return format_html(
        '<input type="hidden" name="{}" value="{}">', nome, valor,
    )


def _pessoas_desta_pessoa(request):
    """A porta única: quem quem-está-logado pode administrar.

    Neste produto o portal atende VÁRIAS empresas, e a lista de usuários
    inteira seria vazamento — um admin da Alfa não pode nem saber que a
    equipe da Beta existe. Quem responde isso é
    `contas.alcance.pessoas_alcancadas`, e ela é a MESMA função nos três
    lugares desta tela que consultam gente: a listagem, a exportação e a
    busca do alvo de cada ação. Três consultas diferentes seriam três
    chances de uma delas divergir — e a que divergisse para mais seria o
    vazamento.
    """
    from contas.alcance import pessoas_alcancadas

    return pessoas_alcancadas(getattr(request, "usuario", None))


def _com_empresa(pessoas):
    """As empresas de cada pessoa, anotadas numa string — `empresa_nome`.

    **São VÁRIAS desde 17/09/2026** (spec
    `2026-09-17-varias-empresas-por-conta`): a conta pode ter mais de uma
    empresa, e a pessoa pode estar alocada em duas. Era uma subconsulta com
    `[:1]`, que mostrava a primeira e escondia o resto sem erro nenhum.

    **Pela CONTA**, que é de onde a empresa se deriva (CLAUDE.md §7): o titular
    é o dono das empresas, e o usuário pertence à conta desse dono. MW5 não é
    de conta nenhuma, e fica vazio (a tela escreve "—").

    `StringAgg`, e não subconsulta: a coluna, o filtro (`icontains` sobre o
    texto agregado), a ordenação e a exportação leem o mesmo valor, e ler as
    empresas na renderização seria uma consulta por pessoa.
    """
    from django.contrib.postgres.aggregates import StringAgg
    from django.db.models import OuterRef, Q, Subquery, Value
    from django.db.models.functions import Coalesce, NullIf

    from plataforma.models import Empresa

    nome = Coalesce(NullIf("nome_fantasia", Value("")), "razao_social")
    # As empresas da CONTA da pessoa (o dono dela, ou ela mesma quando é o
    # titular), juntas em texto, em ordem alfabética para a lista não trocar
    # de ordem entre duas leituras.
    da_conta = (Empresa.objects
                .filter(Q(dono=OuterRef("pk")) | Q(dono=OuterRef("dono")))
                .annotate(nome=nome).order_by()
                .values("dono")
                .annotate(nomes=StringAgg("nome", delimiter=", ",
                                          distinct=True, ordering="nome"))
                .values("nomes")[:1])
    return pessoas.annotate(empresa_nome=Subquery(da_conta))


def _alcancavel(request, id_bruto: str) -> "Usuario | None":
    """O usuário que quem está logado tem alcance para alterar, ou `None`.

    Esconder alguém da lista não é proteger — a lista é só o que o navegador
    desenha; o POST vem do cliente, que pode escrever à mão um id qualquer
    num formulário forjado, sem nunca ter visto aquela linha nesta tela. Por
    isso toda ação (editar, senha, ativar/desativar, remover, alocações) busca
    o alvo por AQUI, e não por `Usuario.objects.filter(pk=...)` direto:
    um id fora do alcance simplesmente não "existe" para quem chama — a mesma
    recusa de sempre, e não um caminho novo por ação que pudesse esquecer a
    checagem.

    O filtro de superusuário continua, dentro de `pessoas_alcancadas`: a
    conta que administra a instalação não se mexe por esta tela.
    """
    try:
        pk = int(id_bruto)
    except (TypeError, ValueError):
        return None
    return _pessoas_desta_pessoa(request).filter(pk=pk).first()


def _e_voce_mesmo(request, alvo: Usuario) -> bool:
    """Se `alvo` é a própria pessoa logada.

    Uma exigência que o brief desta tarefa não escreve, mas que precisa
    existir do mesmo jeito que a trava da MW5: desativar ou remover a
    própria conta tranca a instalação inteira por dentro — o mesmo defeito
    de trancar a MW5 do lado de fora, virado para dentro. Um clique e a
    instalação fica sem ninguém que possa administrar gente.
    """
    return str(alvo.pk) == str(request.usuario.id)


def _niveis_que_pode_conceder(request) -> list:
    """Os níveis que quem está logado pode DAR a alguém.

    **Só a MW5 escolhe nível** (14/09/2026). Desde a virada dos cargos o nível
    diz só QUEM a pessoa é na instalação — a MW5, o titular de uma conta ou um
    membro dela —, e o que ela faz vem do cargo da alocação. O titular cadastra
    membros da conta dele, e um membro nunca vira titular pela mão do titular:
    cada titular é uma conta, um cliente novo do portal, e quem vende conta é a
    MW5.

    A MW5 concede MASTER porque é uma equipe, e alguém precisa poder criar o
    segundo. Superusuário do Django concede o mesmo que ela.

    A lista serve para DESENHAR a caixa e para VALIDAR o POST — a mesma, nos
    dois lugares. Oferecer menos do que se aceita é o buraco clássico: a tela
    esconde e o formulário forjado passa.
    """
    from contas.models import Nivel

    if not _e_master(request):
        return []
    return [Nivel.MASTER, Nivel.TITULAR, Nivel.MEMBRO]


def _salvar_acesso(request, usuario, nivel_bruto: str, conta_bruta: str = "",
                   nascendo: bool = False) -> None:
    """Grava nível e conta, recusando o que não foi oferecido.

    Os dois passam pelo mesmo filtro do que a tela ofereceu, e por isso um
    POST forjado com `nivel=0` (MASTER) ou com o id de uma conta alheia não
    entra. Vale para criar e para editar.

    **A conta só muda se quem edita for a MW5.** Um Admin que pudesse enviar
    `conta=<outro admin>` mudaria uma pessoa de cliente — e levaria junto o
    que ela enxerga. É a fronteira que este trabalho inteiro existe para
    fechar, e ela se fecha aqui, no servidor, e não na tela que esconde o
    campo.

    Sem nível válido no POST, o nível **não muda** — em vez de cair num
    padrão. Cair num padrão silencioso rebaixaria alguém sem ninguém pedir.

    Gravar o nível de titular ou MW5 **traz as permissões dele**
    (`contas.fabrica.aplicar`). O membro não tem permissão direta: a dele é a
    do cargo da alocação (`_gravar_alocacoes`).

    `nascendo` existe porque o nível deixou de morar numa linha à parte.
    Enquanto morava, "esta pessoa acabou de ser cadastrada" era o `created`
    do `get_or_create` daquela linha, e era ele que decidia aplicar as
    permissões de fábrica a quem foi criado sem nível escolhido. Com `nivel`
    virando coluna com padrão, não há mais nada aqui que saiba se a pessoa
    nasceu agora — quem sabe é quem chama, e por isso ela conta.
    """
    permitidos = {int(n) for n in _niveis_que_pode_conceder(request)}
    try:
        pedido = int(nivel_bruto)
    except (TypeError, ValueError):
        pedido = None
    if pedido is not None and pedido in permitidos:
        usuario.nivel = pedido
        usuario.save(update_fields=["nivel"])
        _permissoes_do_nivel(usuario)
    elif nascendo:
        _permissoes_do_nivel(usuario)

    _salvar_conta(request, usuario, conta_bruta)


def _permissoes_do_nivel(usuario) -> None:
    """As permissões diretas que o nível dá — e só titular e MW5 as têm.

    Membro fica sem nenhuma, e é apagar, não só deixar de dar: uma permissão
    direta esquecida de antes da virada dos cargos não vale (o backend a
    ignora), mas continuaria no banco parecendo concessão.
    """
    from contas.fabrica import aplicar

    if usuario.nivel <= Nivel.TITULAR:
        aplicar(usuario, usuario.nivel)
    else:
        usuario.user_permissions.clear()


def _salvar_conta(request, usuario, conta_bruta: str) -> None:
    """A conta da pessoa, se quem edita pode escolhê-la.

    Vazio de quem PODE escolher significa "sem conta" e é gravado: é como a
    MW5 tira alguém de um cliente. Vazio de quem NÃO pode significa "a tela
    nem perguntou", e aí nada muda — sem esta distinção, todo Admin que
    salvasse um usuário o desligaria da própria conta.

    O ADMIN e o MASTER não recebem conta: o primeiro É a conta, o segundo não
    é cliente de nenhuma. Gravar uma aqui criaria o ciclo que `conta_de`
    existe para não ter de tratar.
    """
    from contas.models import Nivel

    if not _e_master(request):
        return
    if usuario.nivel in (Nivel.MASTER, Nivel.TITULAR):
        if usuario.dono_id is not None:
            usuario.dono = None
            usuario.save(update_fields=["dono"])
        return

    try:
        pk = int(conta_bruta)
    except (TypeError, ValueError):
        pk = None

    escolhida = (Usuario.objects.filter(pk=pk, nivel=Nivel.TITULAR).first()
                 if pk is not None else None)
    if escolhida is None and conta_bruta.strip():
        # Enviou algo que não é uma conta. Não muda nada em vez de desligar:
        # lixo no POST não pode ter o mesmo efeito que apagar o campo de
        # propósito.
        return
    usuario.dono = escolhida
    usuario.save(update_fields=["dono"])


def _seletor_de_nivel(request, atual=None) -> "Select | None":
    """A caixa de nível, com só os níveis que quem edita pode conceder.

    Devolve `None` quando não há nenhum — quem não pode conceder nível
    nenhum não vê a caixa, em vez de ver uma vazia que parece defeito.
    """
    from contas.models import Nivel

    niveis = _niveis_que_pode_conceder(request)
    if not niveis:
        return None
    return Select(
        name="nivel", label=_("Nível de acesso"), span=6,
        value=str(int(atual)) if atual is not None else str(int(_padrao(niveis))),
        help="Não é possível dar um nível acima do seu.",
        options=[Option(str(int(n)), n.label) for n in niveis])


def _padrao(niveis: list):
    """O nível que a caixa já vem marcando.

    **TITULAR quando ele está na lista, e o MENOR nível quando não está.**

    Era sempre o menor. Para a MW5 isso estava errado: o que ela faz nesta
    tela é abrir conta de cliente, e o cadastro abria marcando "Comprador" —
    o bloco da empresa nascia escondido, e quem ia cadastrar um titular
    precisava primeiro descobrir que existia um seletor a mexer.

    Para quem NÃO pode conceder TITULAR (o próprio titular, cadastrando a
    equipe dele) nada muda: ele continua caindo no menor, que é o que ele
    cadastra o dia inteiro.

    MASTER nunca é o padrão mesmo estando na lista: criar outra pessoa da MW5
    é raro, e um padrão que concede o nível mais alto é o tipo de descuido que
    só aparece depois.
    """
    from contas.models import Nivel

    if Nivel.TITULAR in niveis:
        return Nivel.TITULAR
    return niveis[-1]




def _e_master(request) -> bool:
    """Quem enxerga o portal inteiro — a MW5.

    Aqui, e não `_ve_tudo` de `contas.alcance`, porque a pergunta é outra:
    aquela é "o que esta pessoa alcança", esta é "esta pessoa escolhe a
    conta de alguém". Hoje as duas respondem igual; no dia em que
    divergirem, quem lê saberá qual mudou.
    """
    from contas.alcance import usuario_de
    from contas.models import Nivel

    if getattr(getattr(request, "usuario", None), "superuser", False):
        return True
    meu = usuario_de(getattr(request, "usuario", None))
    return bool(meu and (meu.is_superuser or meu.nivel == Nivel.MASTER))


def _seletor_de_conta(request, atual=None) -> "Select | None":
    """A CONTA de que a pessoa faz parte — e só a MW5 escolhe.

    Substitui as caixas de marcar empresa (09/09/2026). Elas existiam porque
    uma pessoa alcançava várias; agora ela alcança a empresa da conta dela, e
    não há o que marcar — só de quem ela é.

    **`None` para quem não é MASTER, e não é a tela escondendo uma opção**:
    um Admin só pode cadastrar dentro da própria conta, então a resposta é
    uma só e perguntá-la seria pedir a alguém que confirme o óbvio. Quem
    RECUSA continua sendo `_salvar_acesso`.

    Uma conta é um Admin, e o rótulo mostra a empresa dela: "Alfa Ltda —
    admin@alfa.com". Só o e-mail obrigaria quem escolhe a decorar de quem é
    cada empresa; só a empresa não distinguiria duas contas de uma órfã.
    """
    from contas.models import Nivel
    from plataforma.models import Empresa

    if not _e_master(request):
        return None

    # Uma LISTA por dono, e não uma empresa: a conta pode ter várias desde
    # 17/09/2026, e um dicionário `{dono: empresa}` deixava só a última.
    empresas: dict = {}
    for e in Empresa.objects.filter(dono__isnull=False).order_by("razao_social"):
        empresas.setdefault(e.dono_id, []).append(str(e))
    contas = Usuario.objects.filter(
        nivel=Nivel.TITULAR, is_active=True).order_by("email")
    if not contas:
        return None

    return Select(
        name="conta", label=_("Conta"), span=6,
        value=str(atual) if atual is not None else "",
        empty_label="—",
        help="De qual conta esta pessoa faz parte.",
        options=[Option(str(c.pk),
                        f"{', '.join(empresas[c.pk])} — {c.email}"
                        if c.pk in empresas else f"{c.email} (sem empresa)")
                 for c in contas])


def _com_cargo_ordem(pessoas):
    """O primeiro cargo de cada pessoa, para a coluna ordenar.

    **Anotação, e não o caminho da relação.** `order_by("alocacoes__cargo__rotulo")`
    faz JOIN com uma relação de VÁRIOS, e a pessoa com dois cargos volta duas
    vezes na lista — a linha repetida que a coluna Cargo existe para evitar. O
    `Min` agrega por pessoa (com o `GROUP BY` que a anotação cria), e a lista
    continua com uma linha por gente. A coluna mostra TODOS os cargos; o que
    ordena é o primeiro deles, em ordem alfabética.

    A empresa já vem anotada por `_com_empresa` (que também usa `StringAgg` e
    pelo mesmo motivo): as duas anotações convivem no mesmo `GROUP BY`.
    """
    from django.db.models import Min

    return pessoas.annotate(cargo_ordem=Min("alocacoes__cargo__rotulo"))


def _cargos_de(usuario) -> str:
    """Os cargos da pessoa, por extenso — um por alocação, sem repetir.

    **A coluna era NÍVEL**, e ela não respondia à pergunta que esta tela mais
    recebe ("quem é o gerente aqui?"): quase todo mundo é MEMBRO, e a lista
    inteira escrevia "Usuário". Quem diz o que a pessoa faz é o CARGO da
    alocação, no lugar em que ela está (18/09/2026, pedido do cliente).

    Vários cargos saem juntos, separados por vírgula: a mesma pessoa é Gerente
    numa loja e Vendedora noutra, e mostrar só um faria a tela mentir sobre
    ela. O titular e a MW5 não têm alocação e ficam com "—": o que eles podem
    não vem de cargo nenhum (`contas/fabrica.py`).
    """
    vistos: list[str] = []
    for alocacao in usuario.alocacoes.all():
        if alocacao.cargo.rotulo not in vistos:
            vistos.append(alocacao.cargo.rotulo)
    return ", ".join(vistos) if vistos else "—"


def _colunas_da_lista(pagina) -> list[Column]:
    """`pagina.cabecalho` transforma o rótulo em link de ordenar — ver
    `comum.listagem` e R46.

    **A coluna é CARGO** (18/09/2026, pedido do cliente): é ele que diz o que
    a pessoa faz, e é por ele que se procura nesta tela. O nível continua na
    ficha (e na coluna do modal), mas na lista ele só dizia "Usuário" para
    quase todo mundo.
    """
    return [
        Column("nome", pagina.cabecalho("nome", "Nome"), strong=True,
               render=lambda u: u.nome or "—"),
        Column("login", pagina.cabecalho("login", "Login"),
               render=lambda u: u.email),
        Column("cargo", pagina.cabecalho("cargo", "Cargo"),
               render=_cargos_de),
        Column("empresa", pagina.cabecalho("empresa", "Empresa"),
               render=lambda u: u.empresa_nome or "—"),
        Column("situacao", pagina.cabecalho("situacao", "Situação"),
               align="center", render=lambda u: Badge(
            label="Ativo" if u.is_active else "Inativo",
            tone="primary" if u.is_active else "neutral")),
    ]


def _id_do_modal(acao: str, usuario_pk: int) -> str:
    """Um id por (ação, pessoa) — compartilhado entre o gatilho na linha da
    tabela (`_acoes_da_linha`) e o `Modal` de verdade (`_modais_de_usuario`),
    para os dois nunca divergirem."""
    return f"usuario-{usuario_pk}-{acao}"


def _acoes_da_linha(request, usuario: Usuario) -> Box:
    """Os gatilhos da linha — cada um só abre o `Modal` correspondente
    (`_modais_de_usuario`); nenhum deles envia nada sozinho.

    Nenhuma ação dispara de um clique na linha em si: são botões explícitos,
    inclusive as duas destrutivas (ativar/desativar e remover) — o mesmo
    espírito da trava de sempre, agora sobre a interação, não só sobre o
    servidor.
    """
    botoes = [
        IconButton(icon="edit", title=_("Editar"),
                   attrs={"data-open-modal": _id_do_modal("editar", usuario.pk)}),
        IconButton(icon="lock", title=_("Nova senha"),
                   attrs={"data-open-modal": _id_do_modal("senha", usuario.pk)}),
        IconButton(
            icon="x-circle" if usuario.is_active else "check-circle",
            title="Desativar" if usuario.is_active else "Ativar",
            attrs={"data-open-modal": _id_do_modal("estado", usuario.pk)}),
        IconButton(icon="trash", title=_("Remover"),
                   attrs={"data-open-modal": _id_do_modal("remover", usuario.pk)}),
    ]
    # Só a MW5 personifica (`comum.personificacao.iniciar` recusa qualquer
    # outra pessoa) — o botão não pode aparecer para quem não pode usá-lo. O
    # próprio `_alcancavel` já garante que `usuario` aqui nunca é
    # superusuário, então nenhuma checagem extra sobre o ALVO é necessária.
    if request.usuario.superuser:
        botoes.append(IconButton(
            icon="eye", title=_("Ver como esta pessoa"),
            attrs={"data-open-modal": _id_do_modal("personificar", usuario.pk)}))
    # `wrap=False` e `align="end"`: a coluna de ações é estreita, e `.box`
    # nasce com `flex-wrap: wrap` — sem isto os ícones caem uns embaixo dos
    # outros e esticam a altura de toda linha da tabela.
    return Box(direction="row", gap="sm", wrap=False, align="end",
               cross="center", body=botoes)


def _miolo_do_acesso(seletor, conta) -> list:
    """Nível e conta, montados uma vez para os dois modais.

    Eram nível e uma lista de empresas para marcar. A lista morreu com o M2M
    (09/09/2026): a pessoa alcança a empresa da conta dela, e a única
    pergunta que sobrou — de quem ela é — só a MW5 responde. Para um Admin
    este miolo é o seletor de nível e mais nada, porque a conta dele é a
    única resposta possível.
    """
    if conta is None:
        return [FormGrid(children=[seletor])] if seletor is not None else []

    # **A conta some para quem não faz parte de uma.** O TITULAR *é* a conta e
    # o MASTER não é cliente de nenhuma — perguntar "de quem esta pessoa é"
    # para os dois é oferecer uma escolha que não existe, e a resposta que
    # alguém escolhesse seria descartada no servidor sem explicação.
    #
    # Quem RECUSA continua sendo `_salvar_conta`: ele já apaga o `dono` de
    # MASTER e TITULAR, forjado ou não. Isto aqui é a tela parando de
    # oferecer — e o `data-desligar-escondido` impede que uma conta escolhida
    # antes da troca de nível continue viajando no POST.
    sem_conta = ",".join(str(int(n)) for n in (Nivel.MASTER, Nivel.TITULAR))
    caixa = Box(attrs={"data-nivel-sem-conta": sem_conta,
                       "data-desligar-escondido": "1"},
                body=[FormGrid(children=[conta])])
    campos = [FormGrid(children=[seletor])] if seletor is not None else []
    return [*campos, caixa]


def _legenda(titulo: str, ajuda: str = "") -> str:
    """O nome de um grupo de caixas, e a frase que o explica.

    Menor e mais quieto que um `Alert`: um aviso azul de largura inteira dá a
    uma explicação de rodapé o mesmo peso visual de um erro, e a tela que
    grita em tudo não grita em nada. `SectionLabel` também não serve — ele
    traz a linha que atravessa a largura, e existe para separar SEÇÕES, não
    para nomear um punhado de caixas dentro de uma.
    """
    from django.utils.html import format_html

    return format_html(
        '<div class="ct-legenda"><b>{}</b>{}</div>', titulo,
        format_html('<span>{}</span>', ajuda) if ajuda else "")


def _bloco_de_acesso_de(request, usuario) -> list:
    """O mesmo bloco, com o nível e a conta que a pessoa já tem."""
    from contas.alcance import usuario_de

    dela = usuario_de(usuario)

    seletor = _seletor_de_nivel(request, atual=dela.nivel if dela else None)
    conta = _seletor_de_conta(request, atual=dela.dono_id if dela else None)
    if seletor is None and conta is None:
        return []

    return [Box(body=[SectionLabel(label=_("Acesso")),
                      *_miolo_do_acesso(seletor, conta)])]


def _bloco_de_acesso(request) -> list:
    """Nível e conta, juntos: são as duas metades da mesma pergunta — o que a
    pessoa é, e de quem.

    Nenhum dos dois aparece para quem não pode conceder: um vendedor não vê a
    caixa de nível, e só a MW5 vê a de conta. Esconder aqui é conveniência;
    quem RECUSA é `_salvar_acesso`.
    """
    seletor = _seletor_de_nivel(request)
    conta = _seletor_de_conta(request)
    if seletor is None and conta is None:
        return []

    return [Box(body=[SectionLabel(label=_("Acesso")),
                      *_miolo_do_acesso(seletor, conta)])]


def _bloco_da_empresa(request) -> list:
    """A empresa da conta, cadastrada JUNTO com o titular.

    **Conta e empresa nascem no mesmo ato** (09/09/2026). Uma conta tem uma
    empresa; separar os dois cadastros seria pedir para criar o titular,
    salvar, ir a Empresas, criar a empresa e ligar as duas — quatro passos
    para dizer uma coisa só, e três chances de parar no meio e deixar um
    titular sem empresa (que não enxerga nada) ou uma empresa sem titular
    (que ninguém abre).

    **Só para a MW5, e só quando o nível escolhido é TITULAR.** Um usuário
    comum entra numa conta que já existe; ele não traz empresa nenhuma. Quem
    mostra e esconde conforme o seletor é `contas/static/contas/usuarios.js`,
    pelo atributo `data-nivel-*` — e sem script o bloco aparece
    sempre, o que é o lado certo de falhar: campo visível a mais se ignora,
    campo escondido a menos não se preenche.

    Os campos vêm de `plataforma.views_empresa`, e não copiados: uma segunda
    lista aqui divergiria da primeira no dia em que um campo entrasse, e o
    campo novo apareceria numa tela e não na outra, sem erro nenhum.
    """
    from plataforma.views_empresa import campos_do_cadastro

    if not _e_master(request):
        return []
    return [Box(attrs={"data-nivel-titular": str(int(Nivel.TITULAR)),
                      # Escondido, os campos são DESLIGADOS. O
                      # que se evita é cadastrar uma empresa que ninguém
                      # pediu, com o que sobrou de antes da troca do seletor.
                      "data-desligar-escondido": "1"}, body=[
        SectionLabel(label=_("Empresa da conta")),
        Raw(html=_legenda(
            "Nasce junto",
            "O titular é o dono desta empresa. Ela aparece em Empresas "
            "assim que o cadastro for salvo.")),
        *campos_do_cadastro(request),
    ])]


def _pessoa_de(request) -> "Usuario | None":
    """A linha do ORM de quem está logado."""
    from contas.alcance import usuario_de

    return usuario_de(getattr(request, "usuario", None))


def _lugares_oferecidos(request) -> tuple[list, dict, dict]:
    """O que o bloco de Alocações oferece: `(empresas, filiais por empresa,
    cargos por conta)`.

    A tela OFERECE o que quem edita alcança (`contas.lugar`); quem RECUSA é o
    POST, por `pode_dar`, que também confere permissão e alcance do cargo. Por
    isso aqui não se filtra cargo por permissão: uma caixa que mostrasse menos
    cargos que o POST aceita seria a mesma regra escrita duas vezes, e as duas
    divergiriam na primeira mudança.
    """
    from contas.lugar import empresas_da_pessoa, filiais_da_pessoa
    from contas.models import Cargo

    editor = _pessoa_de(request)
    empresas = list(empresas_da_pessoa(editor).order_by("razao_social"))
    filiais = {e.pk: list(filiais_da_pessoa(editor, e)) for e in empresas}
    cargos: dict = {}
    for cargo in Cargo.objects.filter(
            conta_id__in={e.conta_id for e in empresas}).order_by("rotulo"):
        cargos.setdefault(cargo.conta_id, []).append(cargo)
    return empresas, filiais, cargos


def _linha_de_alocacao(oferta, alocacao=None) -> str:
    """Uma linha do bloco: empresa, filial (ou todas) e cargo, e o Remover.

    `<select>` cru e não `nucleo.components.Select`: o do design system desenha
    o próprio rótulo e ocupa uma faixa da grade de doze colunas, e esta é uma
    linha que repete, com a grade dela.

    A filial e o cargo listam os de TODAS as empresas oferecidas, com o nome da
    empresa entre parênteses quando há mais de uma. Filtrar pela empresa
    escolhida pediria script; sem ele, a escolha errada é recusada no POST
    ("Esta filial não é desta empresa") em vez de passar calada.
    """
    from django.utils.html import format_html, format_html_join
    from django.utils.safestring import mark_safe

    empresas, filiais, cargos = oferta
    varias = len(empresas) > 1
    empresa_atual = str(alocacao.empresa_id) if alocacao else ""
    filial_atual = str(alocacao.filial_id or "") if alocacao else ""
    cargo_atual = str(alocacao.cargo_id) if alocacao else ""

    def opcoes(pares, escolhido):
        return format_html_join("", '<option value="{}"{}>{}</option>', (
            (valor, mark_safe(" selected") if valor == escolhido else "", rotulo)
            for valor, rotulo in pares))

    def de(empresa, rotulo):
        return f"{rotulo} ({empresa})" if varias else rotulo

    pares_empresa = [("", "Empresa…")] + [(str(e.pk), str(e)) for e in empresas]
    pares_filial = [("", "Todas as filiais")] + [
        (str(f.pk), de(e, str(f))) for e in empresas for f in filiais[e.pk]]
    pares_cargo = [("", "Cargo…")] + [
        (str(c.pk), de(e, c.rotulo)) for e in empresas
        for c in cargos.get(e.conta_id, [])]
    return format_html(
        '<div class="ct-aloc-linha">'
        '<select name="aloc_empresa" aria-label="Empresa">{}</select>'
        '<select name="aloc_filial" aria-label="Filial">{}</select>'
        '<select name="aloc_cargo" aria-label="Cargo">{}</select>'
        '<button type="button" class="btn ghost ct-aloc-remover" '
        'aria-label="Remover esta alocação">Remover</button>'
        '</div>',
        opcoes(pares_empresa, empresa_atual),
        # A mesma lista de filiais e o valor vazio de "todas" em toda linha.
        opcoes(pares_filial, filial_atual),
        opcoes(pares_cargo, cargo_atual))


def _bloco_de_alocacoes(request, oferta, alvo=None) -> list:
    """Onde a pessoa trabalha, e com qual cargo: uma linha por lugar.

    Substitui a caixa de Perfis (14/09/2026). O que a pessoa pode fazer vem do
    cargo da alocação no lugar em que ela está, e é aqui que se diz isso.

    Uma linha em branco sempre vem no fim — sem script é ela que acrescenta —,
    e o campo oculto `alocacoes` diz ao POST que o bloco foi desenhado. Sem
    esse marcador, um POST que não veio desta tela (ou um formulário antigo)
    apagaria as alocações de alguém por não ter mandado nenhuma linha.
    """
    from django.utils.html import format_html, format_html_join

    existentes = list(alvo.alocacoes.all()) if alvo is not None else []
    linhas = format_html_join("", "{}", (
        (_linha_de_alocacao(oferta, a),) for a in [*existentes, None]))
    lista = f"aloc-lista-{alvo.pk if alvo is not None else 'nova'}"
    # **Some para titular e MW5** (15/09/2026): nenhum dos dois é alocado (D3)
    # — o titular alcança a conta toda, e a MW5 não é de conta nenhuma. Com o
    # bloco à vista, cadastrar um titular pedia um lugar e um cargo que o
    # servidor jogaria fora. O script esconde e DESLIGA (o marcador
    # `alocacoes` sai do POST junto), pelo mesmo par nível↔bloco da Conta.
    # Sem seletor de nível (quem não é MW5 cadastra só usuário), nada muda.
    sem_alocacao = ",".join(str(int(n)) for n in (Nivel.MASTER, Nivel.TITULAR))
    return [Box(attrs={"data-nivel-sem-alocacao": sem_alocacao,
                       "data-desligar-escondido": "1"}, body=[
        SectionLabel(label=_("Alocações")),
        Raw(html=_legenda(
            "Onde e com qual cargo",
            "Filial em branco é a empresa inteira, inclusive as filiais "
            "criadas depois. O titular não é alocado: ele alcança a conta toda.")),
        Raw(html=_campo_oculto("alocacoes", "1")),
        Raw(html=format_html(
            '<div class="ct-aloc-lista" id="{}">{}</div>'
            '<button type="button" class="btn ghost" data-aloc-mais="{}">'
            "+ Acrescentar alocação</button>", lista, linhas, lista)),
    ])]


class _CadastroRecusado(Exception):
    """Algo do cadastro não passou. Existe para desfazer a transação.

    Um `return` de dentro do `atomic()` COMITARIA o usuário — o bloco só
    desfaz quando sai por exceção. Já custou uma vez nesta base, no cadastro
    de produto: a peça ficava gravada e as equivalências não.
    """

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


def _ler_alocacoes(request) -> "tuple[dict, str | None]":
    """As linhas do POST, resolvidas e conferidas: `({lugar: (empresa, filial,
    cargo)}, frase de recusa ou None)`.

    Lidas ANTES de gravar qualquer coisa: uma linha recusada não pode deixar a
    pessoa criada pela metade. Cada linha passa por `contas.lugar.pode_dar`,
    que é a trava contra escalada (o lugar é um que quem edita alcança, o cargo
    não tem permissão nem alcance que ele não tenha ali). Linha repetida no
    mesmo lugar: a última vence, como numa planilha.
    """
    from contas.lugar import empresas_da_pessoa, pode_dar
    from contas.models import Cargo
    from plataforma.models import Filial

    editor = _pessoa_de(request)
    empresas = {e.pk: e for e in empresas_da_pessoa(editor)}
    linhas: dict = {}
    for bruto_empresa, bruto_filial, bruto_cargo in zip(
            request.POST.getlist("aloc_empresa"),
            request.POST.getlist("aloc_filial"),
            request.POST.getlist("aloc_cargo")):
        if not bruto_empresa.strip() and not bruto_cargo.strip():
            continue
        try:
            empresa = empresas.get(int(bruto_empresa))
            cargo_id = int(bruto_cargo)
            filial_id = int(bruto_filial) if bruto_filial.strip() else None
        except (TypeError, ValueError):
            return {}, _("Lugar ou cargo inválido.")
        if empresa is None:
            return {}, _("Lugar ou cargo inválido.")
        cargo = Cargo.objects.filter(pk=cargo_id, conta_id=empresa.conta_id).first()
        filial = (Filial.objects.filter(pk=filial_id, empresa=empresa).first()
                  if filial_id is not None else None)
        if cargo is None or (filial_id is not None and filial is None):
            return {}, _("Lugar ou cargo inválido.")
        if not pode_dar(editor, empresa, filial, cargo):
            return {}, (f'Você não pode dar o cargo "{cargo}" em '
                        f'{filial or empresa}.')
        linhas[(empresa.pk, filial.pk if filial else None)] = (empresa, filial, cargo)
    return linhas, None


def _exige_alocacao(request) -> bool:
    """Quem não é titular nem MW5 não cadastra gente sem lugar.

    Pessoa sem alocação só é administrada pelo titular (R6 do plano 2): se um
    Gerente pudesse criá-la sem lugar, ela sumiria da lista dele no mesmo
    instante, e ele não conseguiria nem corrigir o que acabou de fazer.
    """
    editor = _pessoa_de(request)
    return not (editor is None or editor.is_superuser
                or editor.nivel <= Nivel.TITULAR)


def _gravar_alocacoes(request, alvo, linhas: dict) -> None:
    """Deixa as alocações de `alvo` iguais às `linhas`, e registra cada mudança.

    Troca por lugar, e não apaga tudo para recriar: a alocação que continua no
    mesmo lugar só muda de cargo, e a trilha registra só o que de fato entrou
    ou saiu.

    Titular e MW5 não são alocados (D3): trocar alguém para titular leva junto
    as alocações que ele tinha.
    """
    from django.core.exceptions import ValidationError

    from contas.models import Alocacao

    atuais = {(a.empresa_id, a.filial_id): a for a in alvo.alocacoes.all()}
    if alvo.nivel <= Nivel.TITULAR or alvo.is_superuser:
        linhas = {}
    for lugar, alocacao in atuais.items():
        if lugar not in linhas:
            registrar(ACOES.ALOCACAO_REMOVIDA, request.usuario,
                      alvo=str(alocacao), request=request)
            alocacao.delete()
    for lugar, (empresa, filial, cargo) in linhas.items():
        try:
            if lugar in atuais:
                alocacao = atuais[lugar]
                if alocacao.cargo_id == cargo.pk:
                    continue
                alocacao.cargo = cargo
                alocacao.save()
            else:
                alocacao = Alocacao.objects.create(
                    pessoa=alvo, empresa=empresa, filial=filial, cargo=cargo)
        except ValidationError as recusa:
            # `Alocacao.clean` é a última porta (pessoa de outra conta, por
            # exemplo, quando a MW5 escolhe a conta e o lugar de clientes
            # diferentes). A frase dela vai para a tela em vez de um 500.
            raise _CadastroRecusado(" ".join(
                str(m) for msgs in recusa.message_dict.values() for m in msgs))
        registrar(ACOES.ALOCACAO_CRIADA, request.usuario,
                  alvo=str(alocacao), request=request)


def _modal_criar_usuario(request, oferta) -> Modal:
    """O formulário de cadastro, na ordem em que as perguntas se fazem:
    quem é a pessoa, o que ela é (só a MW5 escolhe), e onde trabalha, com qual
    cargo.

    **A filial saiu desta tela inteira** — a caixa do cadastro, a coluna da
    tabela, o filtro e a coluna do arquivo exportado. Filial é herança do
    KRONOS.net, onde a instalação era de UM cliente e o que variava dentro
    dela era a filial. Neste produto o inquilino é a EMPRESA, e a busca que
    autorizou esta remoção é curta: `usuario.filiais` não era lido em lugar
    nenhum fora deste arquivo — nem em `catalogo/`, nem em `orcamento/`, nem
    no que hoje é `contas/alcance.py`, nem na sessão. Duas caixas pediam a mesma coisa e a
    resposta de uma delas não ia a lugar nenhum, o que é pior que inútil:
    parecia que ia.

    Tirar só a caixa e deixar a coluna teria sido pior ainda — uma coluna
    "Filial" que ninguém mais consegue preencher, e um filtro que nunca acha
    nada. A tela de Filiais (`plataforma/views_filiais.py`) continua de pé; o
    que saiu foi a filial da ficha da PESSOA.
    """
    return Modal(id="usuario-criar", title=_("Novo usuário"), size="lg",
        body=Form(action=reverse("usuarios"), children=[
            Raw(html=campo_csrf(request)),
            Raw(html=_campo_oculto("acao", "criar")),
            # **O campo "Login" saiu.** Ele existia para inventar um apelido
            # de entrada, e o apelido deixou de existir quando o usuário
            # passou a ser nosso: `USERNAME_FIELD` é `email`. Manter os dois
            # seria pedir duas vezes a mesma coisa e deixar quem cadastra
            # escolher qual das duas é a verdadeira.
            #
            # As larguras seguem o que se digita em cada um, e não uma divisão
            # igual: o nome é o mais longo dos dois.
            #
            # `maxlength` do próprio model: um valor colado com 400 caracteres
            # dava HTTP 500 (o Postgres recusava a coluna, e a pessoa via
            # "Algo inesperado aconteceu"). Números lidos do model para não
            # divergirem dele.
            *[
                Box(body=[
                    SectionLabel(label=_("Quem é")),
                    FormGrid(children=[
                        TextInput(name="nome", label=_("Nome"), span=5,
                                  required=True,
                                  maxlength=_limite("nome")),
                        TextInput(name="email", label=_("E-mail"), span=4,
                                  type="email", required=True,
                                  maxlength=_limite("email")),
                        # **Em texto, e não `type="password"`.** Quem digita
                        # aqui está definindo a senha de OUTRA pessoa e vai
                        # ter de dizê-la a ela; escondida atrás de pontinhos,
                        # um erro de digitação só aparece quando a pessoa não
                        # consegue entrar. Não é a senha de quem está na tela.
                        # **`senha_da_pessoa`, e não `senha`.** O mesmo POST
                        # carrega o cadastro da EMPRESA, e lá já existe um
                        # campo `senha` — a do banco Oracle do cliente. Com o
                        # mesmo nome, criar um titular com empresa gravava uma
                        # senha no lugar da outra. A suíte pegou; o nome longo
                        # é o que impede de voltar.
                        TextInput(name="senha_da_pessoa", label=_("Senha"),
                                  span=3,
                                  help=_("Em branco, gera uma.")),
                    ]),
                ]),
                *_bloco_de_acesso(request),
                *_bloco_da_empresa(request),
                *_bloco_de_alocacoes(request, oferta),
            ],
            Raw(html=_rodape("Criar usuário")),
        ]))


def _modais_de_usuario(request, usuario: Usuario, oferta) -> list[Modal]:
    """Um `Modal` por ação desta pessoa — editar (nome, acesso e alocações), resetar
    senha, ativar/desativar e remover, e "ver como" só para a MW5 — cada um
    com o próprio `<form>` dentro, os mesmos campos ocultos e a mesma `acao`
    de sempre. Nasce tudo fechado (`Modal.open` é `False` por padrão) e vive
    em `overlays=`, não na linha: é isso que troca "um cartão por pessoa,
    empilhado na página" por "um clique na linha, o resto some depois".
    """
    nome = usuario.nome or usuario.email
    if usuario.is_active:
        acao_de_estado, rotulo_de_estado = "desativar", "Desativar"
        aviso_de_estado = Alert(
            tone="warn", message=f'Desativar "{nome}"? A pessoa deixa de '
                                  f'conseguir entrar até ser ativada de novo.')
    else:
        acao_de_estado, rotulo_de_estado = "ativar", "Ativar"
        aviso_de_estado = Alert(tone="info", message=f'Ativar "{nome}" de novo?')

    modais = [
        Modal(id=_id_do_modal("editar", usuario.pk), title=f"Editar {nome}",
              size="lg", body=Form(action=reverse("usuarios"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", "editar")),
                  Raw(html=_campo_oculto("id", str(usuario.pk))),
                  *[
                      Box(body=[
                          SectionLabel(label=_("Quem é")),
                          FormGrid(children=[
                              TextInput(name="nome", label=_("Nome"), span=6,
                                        value=usuario.nome,
                                        maxlength=_limite("nome")),
                              # Sem `required`, ao contrário do cadastro.
                              # Exigir aqui trancaria toda conta que nasceu
                              # ANTES desta regra: trocar o nome de alguém
                              # passaria a depender de descobrir o e-mail
                              # dessa pessoa. A exigência vale para a conta
                              # nova, que é onde ela impede o problema.
                              TextInput(name="email", label=_("E-mail"), span=6,
                                        type="email", value=usuario.email,
                                        maxlength=_limite("email")),
                          ]),
                      ]),
                      *_bloco_de_acesso_de(request, usuario),
                      *_bloco_de_alocacoes(request, oferta, usuario),
                  ],
                  Raw(html=_rodape("Salvar")),
              ])),
        Modal(id=_id_do_modal("senha", usuario.pk),
              title=_("Gerar nova senha temporária"),
              body=Form(action=reverse("usuarios"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", "senha")),
                  Raw(html=_campo_oculto("id", str(usuario.pk))),
                  Alert(tone="warn",
                        message=f'A senha atual de "{nome}" para de funcionar '
                                f'assim que a nova for gerada.'),
                  Button(label=_("Gerar nova senha"), variant="primary", type="submit"),
              ])),
        Modal(id=_id_do_modal("estado", usuario.pk), title=rotulo_de_estado,
              body=Form(action=reverse("usuarios"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", acao_de_estado)),
                  Raw(html=_campo_oculto("id", str(usuario.pk))),
                  aviso_de_estado,
                  Button(label=rotulo_de_estado,
                         variant="danger" if acao_de_estado == "desativar" else "primary",
                         type="submit"),
              ])),
        # Nomeia quem seria removido, como o brief pede. A recusa de servidor (própria conta, MW5)
        # continua valendo do mesmo jeito de sempre; este `Alert` é só a
        # confirmação da interface, não substitui nenhuma delas.
        Modal(id=_id_do_modal("remover", usuario.pk), title=_("Remover usuário"),
              body=Form(action=reverse("usuarios"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", "remover")),
                  Raw(html=_campo_oculto("id", str(usuario.pk))),
                  Alert(tone="danger",
                        message=f'Remover "{nome}"? Esta ação não pode ser desfeita.'),
                  Button(label=_("Remover"), variant="danger", type="submit"),
              ])),
    ]
    if request.usuario.superuser:
        modais.append(Modal(
            id=_id_do_modal("personificar", usuario.pk),
            title=_("Ver como esta pessoa"),
            body=Form(action=reverse("personificar"), children=[
                Raw(html=campo_csrf(request)),
                Raw(html=_campo_oculto("id", str(usuario.pk))),
                Alert(tone="info", message=f'Ver o sistema como "{nome}"?'),
                Button(label=_("Ver como esta pessoa"), variant="primary", type="submit"),
            ])))
    return modais


#: `chave da URL -> campo(s) do ORM` — só o que esta lista declara pode
#: entrar em `order_by` (ver `comum.listagem._resolver_ordenacao`).
#: "Nome" e "Situação" desempatam pelo login, para duas pessoas com o mesmo
#: nome (ou o mesmo estado) não trocarem de posição a cada requisição.
_ORDENAVEIS = {
    "nome": ("nome", "email"),
    "login": ("email",),
    # Pelo RÓTULO do cargo, que é o que a coluna mostra. `cargo_ordem` é a
    # anotação de `_com_cargo_ordem`: ordenar pelo caminho da relação
    # (`alocacoes__cargo__rotulo`) devolveria a pessoa DUAS vezes quando ela
    # tem dois cargos — a linha repetida que a própria coluna foi feita para
    # evitar. Desempata pelo login como as outras.
    "cargo": ("cargo_ordem", "email"),
    "empresa": ("empresa_nome", "email"),
    "situacao": ("is_active", "email"),
}

#: Quais colunas têm campo de busca, e em que campos do banco cada uma
#: procura. "Situação" fica de fora de propósito: é ativo ou inativo, e um
#: campo de texto para dois valores é pior que nenhum — quando existir um
#: componente de escolha na coluna, ela entra.
def _cargos_para_escolha() -> list[tuple[str, str]]:
    """Os cargos que existem HOJE nesta instalação, por rótulo.

    **Não é lista fechada como era a dos níveis**: o titular cria cargos em
    `/cargos`, e uma caixa fixa deixaria de achar quem tem o cargo novo. O
    `Callable` existe justamente para isto (`comum.listagem.ColunaFiltravel`):
    a lista é lida a cada desenho da barra, e não congelada na importação.
    """
    from contas.models import Cargo

    return list(Cargo.objects.order_by("rotulo")
                .values_list("rotulo", flat=True).distinct())


_FILTRAVEIS = {
    "nome": ColunaFiltravel("nome", "Nome"),
    "login": ColunaFiltravel("email", "Login"),
    # "Quem é o gerente aqui?" é a pergunta que esta tela mais recebe, e até
    # 18/09/2026 ela se respondia por NÍVEL — que devolve a lista inteira,
    # porque quase todo mundo é MEMBRO ("Usuário"). O filtro é o CARGO da
    # alocação, e o caminho da relação é de propósito: quem tem dois cargos
    # aparece na busca dos dois.
    "cargo": ColunaFiltravel("alocacoes__cargo__rotulo", "Cargo",
                             tipo="opcoes", opcoes=_cargos_para_escolha),
    # Ativo ou inativo: dois valores conhecidos. Era a coluna que eu tinha
    # deixado sem filtro por não existir caixa de escolha — agora existe.
    "situacao": ColunaFiltravel("is_active", "Situação", tipo="opcoes",
                                opcoes=lambda: [("1", "Ativo"), ("0", "Inativo")]),
    # A anotação de `_com_empresa`, e não um caminho de relação: a empresa do
    # titular e a do usuário chegam por lados diferentes da conta.
    "empresa": ColunaFiltravel("empresa_nome", "Empresa"),
}


def _desenhar(
    request, erro: "str | None" = None,
    senha_temporaria: "str | None" = None, login_da_senha: "str | None" = None,
) -> HttpResponse:
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        oferta = _lugares_oferecidos(request)

        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=_("Usuários"),
                       subtitle="Quem existe na conta, e onde cada pessoa "
                                "trabalha, com qual cargo.",
                       # Abre o modal de criação — não há mais formulário
                       # nenhum ocupando o topo da página em fluxo. Ao lado,
                       # a exportação (Bloco 4): leva o filtro da URL.
                       actions=[
                           Button(label=_("Novo usuário"), variant="primary",
                                  attrs={"data-open-modal": "usuario-criar"}),
                           *botoes(request),
                       ]),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))
        if senha_temporaria:
            # Mostrada UMA vez, nesta mesma resposta, e nunca de novo: não é
            # gravada em campo de model, log, sessão ou URL de redirect —
            # `_desenhar` é chamado direto aqui, sem passar por
            # `HttpResponseRedirect`, exatamente para o valor não precisar
            # viajar por lugar nenhum além desta renderização.
            conteudo.append(Alert(
                tone="ok", title=_("Senha temporária gerada"),
                message=f'Login "{login_da_senha}": {senha_temporaria}. '
                        f'Anote agora — esta tela não mostra de novo.',
            ))

        # `is_superuser=False`: a MW5 nunca entra nesta consulta — não é
        # filtrada depois de vir do banco, nunca chega a existir na variável
        # que o restante da view usa. Ver o docstring do módulo.
        # A coluna Nível não precisa mais de `select_related("acesso")`: o
        # nível é coluna da própria pessoa, e já vem no mesmo `SELECT`. Os
        # alocações vêm por `prefetch_related` porque o modal de cada linha
        # os lê e são coleção. Sem isto é uma
        # consulta por leitura por linha — medido: 43 consultas com 3 pessoas,
        # 131 com 25, ou seja ~4 por linha. Em SQLite local cada uma custa
        # décimos de milissegundo; em Postgres com rede, cada ida e volta é
        # ~1ms, e as 25 linhas do padrão viram +100ms de tela.
        pessoas = (_com_cargo_ordem(_com_empresa(_pessoas_desta_pessoa(request)))
                   .prefetch_related("alocacoes__empresa", "alocacoes__filial",
                                     "alocacoes__cargo"))

        listagem = montar_pagina(
            request, pessoas, ordenaveis=_ORDENAVEIS, padrao="login",
            filtraveis=_FILTRAVEIS)
        pessoas = listagem.linhas

        conteudo.append(Card(
            title=_("Usuários existentes"), padded=False,
            body=[
                # A busca mora no MESMO bloco da tabela, e não num
                # cartão à parte: são a mesma coisa — o que você
                # procura e o que achou. `.card .filters` na folha
                # deste projeto tira a moldura de cartão que a
                # `FilterBar` traz, para não virar caixa dentro de caixa.
                # Filtros salvos (item 27): os desta pessoa nesta tela.
                listagem.barra,
                Table(columns=_colunas_da_lista(listagem), rows=pessoas,
                      row_actions=lambda u: _acoes_da_linha(request, u)),
                listagem.paginacao,
            ],
        ))

        # Um `Modal` de criação, e um bloco de modais por pessoa — todos
        # fechados, todos em `overlays=`, nenhum no fluxo da página. Ver o
        # docstring de `_modais_de_usuario`.
        modais = [_modal_criar_usuario(request, oferta)]
        for pessoa in pessoas:
            modais.extend(_modais_de_usuario(request, pessoa, oferta))

        pagina = site.page(
            # `full`: a tela usa a largura toda. Estas telas são tabela e
            # formulário — espremer uma tabela em 1400px num monitor largo
            # desperdiça a metade direita e ainda quebra coluna.
            title=_("Usuários"),
            width="full",
            # A folha do trio de listagem (R46) — só as telas com tabela
            # precisam dela, e `stylesheets=` existe exatamente para isso.
            stylesheets=["/static/plataforma/listagem.css",
                         "/static/contas/usuarios.css"],
            # Mostra e esconde os blocos conforme o nível escolhido. A tela
            # inteira funciona sem ele — ver o cabeçalho do arquivo.
            scripts=["/static/contas/usuarios.js",
                     "/static/contas/alocacoes.js"],
            content=conteudo,
            crumbs=[Crumb(_("Usuários"))],
            user=getattr(request, "usuario", None),
            overlays=modais,
        )
        # A renderização acontece AQUI dentro — ver o comentário equivalente
        # em `plataforma/views.py::_desenhar`: fora do `with`, cai no
        # ambiente global e ignora em silêncio qualquer loader extra do
        # cliente.
        return render(pagina)


#: As colunas que saem no arquivo e no papel — as MESMAS da tabela, com o
#: valor em texto no lugar do Badge.
COLUNAS_DE_EXPORTACAO = (
    ColunaDeExportacao("nome", "Nome", lambda u: u.get_full_name() or ""),
    ColunaDeExportacao("login", "Login", lambda u: u.email),
    ColunaDeExportacao("cargo", "Cargo", _cargos_de),
    ColunaDeExportacao("empresa", "Empresa", lambda u: u.empresa_nome or ""),
    ColunaDeExportacao("situacao", "Situação",
                       lambda u: "Ativo" if u.is_active else "Inativo"),
)


# Mesma ordem e mesmo motivo de `modulos/exemplo/views.py`:
# `exigir_permissao` por fora, `exigir_modulo_ligado` por dentro. Faltava aqui
# até a revisão final do branch.
# ---------------------------------------------------------------------------
# As ações do POST, uma função cada.
#
# Antes era uma cadeia de `if acao == ...` dentro da própria view, que a
# auditoria mediu em complexidade ciclomática 18 — a mais alta do código
# autoral. Cada ação virou função, e o despacho virou tabela: a view voltou a
# ter uma responsabilidade só (ler a ação, resolver o alvo, chamar quem faz).
#
# A separação em DUAS tabelas não é enfeite: `criar` é a única ação que não
# mexe em ninguém existente. Todas as outras precisam do alvo, e o alvo passa
# por `_alcancavel` UMA vez, no despacho — nenhuma função de ação busca o
# próprio alvo. É o que impede que uma ação nova nasça esquecendo a checagem
# de superusuário, que é a metade da defesa descrita no docstring do módulo.
# ---------------------------------------------------------------------------


def _vincular_a_conta(request, novo) -> None:
    """Quem é criado nasce na conta de quem criou.

    **Cadastro é interno**: o Admin cadastra gente da conta dele. Sem este
    vínculo, o efeito seria absurdo e silencioso — o Admin cria alguém e na
    requisição seguinte não enxerga mais essa pessoa, porque ela ficaria fora
    de `pessoas_alcancadas`. Não seria um erro na tela; seria uma linha que
    some.

    Quem cria pode não ser o Admin: um vendedor que cadastre alguém põe a
    pessoa na conta DELE, não em si mesmo — por isso `conta_de` e não
    `de_quem_criou`.

    MASTER e superusuário criam sem conta nenhuma, de propósito: eles não são
    "de" um cliente, e escolher um por eles seria inventar um dado. A tela já
    pergunta, na caixa de Acesso, e só para eles.

    **Só preenche o vazio**, e roda DEPOIS de `_salvar_acesso`: o que a MW5
    escolheu na tela é escolha, e herdar por cima dela seria desfazê-la em
    silêncio.

    O ADMIN não recebe conta: ele É a conta.
    """
    from contas.alcance import conta_de, usuario_de
    from contas.models import Nivel

    if novo.dono_id is not None or novo.nivel in (Nivel.MASTER, Nivel.TITULAR):
        return

    conta = conta_de(usuario_de(getattr(request, "usuario", None)))
    if conta is None:
        return
    novo.dono = conta
    novo.save(update_fields=["dono"])


def _email_valido(bruto: str) -> "str | None":
    """O e-mail limpo, ou `None` se não for um e-mail.

    `validate_email` do próprio Django, e não uma expressão regular escrita
    aqui: e-mail é um formato que parece simples e não é, e toda regex de
    e-mail escrita à mão recusa endereço legítimo de alguém — normalmente o
    de um cliente, num dia ruim.
    """
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    limpo = (bruto or "").strip()
    try:
        validate_email(limpo)
    except ValidationError:
        return None
    return limpo


def _login_ocupado(email: str, menos: "int | None" = None) -> bool:
    """Se já existe alguém entrando por este e-mail.

    `email__iexact` e não `email=`: a coluna é única em caixa EXATA, então o
    banco deixaria `ana@empresa.com` e `Ana@empresa.com` conviverem como duas
    contas — e `GerenteDeUsuario.get_by_natural_key` acha as duas na hora de
    entrar, o que vira `MultipleObjectsReturned` na tela de login. A porta é
    insensível à caixa; a recusa de duplicata precisa ser também, ou uma
    contradiz a outra.

    `menos` é o pk de quem está sendo editado: reenviar a ficha com o próprio
    e-mail no campo não é duplicata nenhuma.
    """
    consulta = Usuario.objects.filter(email__iexact=email)
    if menos is not None:
        consulta = consulta.exclude(pk=menos)
    return consulta.exists()


def _criar_a_empresa_da_conta(request, novo) -> str:
    """A empresa do titular recém-criado. Devolve a frase de recusa, ou "".

    Só quando a MW5 cria um TITULAR: um usuário comum entra numa conta que já
    existe, e um titular criado por outra pessoa não seria titular de nada —
    só a MW5 abre conta.

    Roda DEPOIS de `_salvar_acesso`, que é quem grava o nível: perguntar
    antes leria o nível padrão da coluna e nunca criaria empresa nenhuma.
    """
    from plataforma.views_empresa import criar_do_post

    if not _e_master(request) or novo.nivel != Nivel.TITULAR:
        return ""
    # Formulário sem os campos da empresa (um POST antigo, um script que não
    # rodou) não é erro: o titular nasce sem empresa, que é um estado que o
    # banco aceita e a tela de Empresas mostra. Exigir aqui trancaria o
    # cadastro por causa de um campo que quem preenche pode não ter em mãos.
    if not request.POST.get("razao_social", "").strip():
        return ""
    _resto, erro = criar_do_post(request, dono=novo)
    return erro


def _acao_criar(request) -> HttpResponse:
    nome = request.POST.get("nome", "").strip()
    if not nome:
        return _desenhar(request, erro=_("Informe um nome."))
    # O `required` do HTML é conveniência do navegador, não regra: quem manda
    # o POST é o cliente, e um formulário forjado não passa por atributo
    # nenhum. Quem exige é esta linha.
    email = _email_valido(request.POST.get("email", ""))
    if email is None:
        return _desenhar(request, erro=_("Informe um e-mail válido."))
    # A frase fala em "login", e não em "e-mail": o e-mail É o login, e "já
    # existe este e-mail" soaria como um cadastro duplicado de contato em vez
    # de duas pessoas disputando a mesma porta.
    if _login_ocupado(email):
        return _desenhar(
            request, erro=f'Já existe alguém com o login "{email}".')
    # `is_superuser`/`is_staff` nunca são lidos do POST — mesmo que o
    # formulário nunca os ofereça, um POST forjado poderia trazê-los, e
    # `create_user` já nasce com os dois em `False` por padrão. Ver o
    # docstring do módulo: essa é a metade da defesa que cobre a criação.
    # **A senha pode vir digitada.** Antes, toda pessoa nova nascia com uma
    # aleatória que a tela mostrava uma vez — e quem cadastra tinha de
    # copiá-la e repassá-la. Na prática, quem cadastra já combinou a senha com
    # a pessoa (ou usa um padrão da casa), e o gerado virava um passo a mais
    # entre o cadastro e o primeiro login.
    #
    # Vazio continua gerando: é o caminho certo para quem cadastra em lote e
    # não quer inventar senha, e é o comportamento que estava lá.
    digitada = request.POST.get("senha_da_pessoa", "").strip()
    if digitada and len(digitada) < SENHA_MINIMA:
        return _desenhar(request, erro=_(
            "A senha precisa de pelo menos %(minimo)s caracteres.") % {
                "minimo": SENHA_MINIMA})
    senha_temporaria = digitada or get_random_string(TAMANHO_DA_SENHA_TEMPORARIA)
    # `atomic()` cerca a criação, as alocações e o registro juntos: se
    # `registrar` falhar, o usuário recém-criado (e as alocações que já
    # tinham sido salvas) desfazem junto — nunca um usuário criado sem
    # ninguém saber quem criou.
    # O model do Django não valida `max_length` no `save()` — quem recusa é o
    # Postgres, com HTTP 500 na cara de quem cadastra. Aqui a recusa vira
    # frase. Os limites saem do próprio model (`_limite`), então não há um
    # segundo número para divergir.
    for campo, rotulo, valor in (("nome", "nome", nome),
                                 ("email", "e-mail", email)):
        if len(valor) > _limite(campo):
            return _desenhar(request, erro=(
                f"O {rotulo} tem {len(valor)} caracteres e o limite é "
                f"{_limite(campo)}."))
    # As alocações são lidas e conferidas ANTES de criar a pessoa: uma linha
    # recusada (cargo que quem cadastra não pode dar, lugar fora do alcance
    # dele) não pode deixar alguém criado pela metade.
    linhas, erro = _ler_alocacoes(request)
    if erro:
        return _desenhar(request, erro=erro)
    if _exige_alocacao(request) and not linhas:
        return _desenhar(request, erro=_("Aloque a pessoa em pelo menos um lugar."))
    try:
        with transaction.atomic():
            novo = Usuario.objects.create_user(
                email=email, nome=nome, password=senha_temporaria)
            # `_salvar_acesso` PRIMEIRO: é ele que grava o nível e as permissões
            # de fábrica que vêm com ele.
            #
            # `nascendo=True`: é o que diz a `_salvar_acesso` que esta pessoa
            # acabou de ser criada, e portanto que um POST sem nível ainda assim
            # precisa aplicar as permissões do padrão. A informação vinha do
            # `created` do `get_or_create` da tabela ao lado, que não existe mais.
            _salvar_acesso(request, novo, request.POST.get("nivel", ""),
                           request.POST.get("conta", ""), nascendo=True)
            # Depois, e só para tapar o vazio — ver o docstring dele.
            _vincular_a_conta(request, novo)
            _gravar_alocacoes(request, novo, linhas)
            erro = _criar_a_empresa_da_conta(request, novo)
            if erro:
                # **A `ValidationError` desfaz o usuário junto.** Conta e empresa
                # nascem no mesmo ato; um titular gravado com a empresa recusada
                # seria alguém que entra no sistema e não enxerga nada — e nada
                # na tela dizendo por quê.
                # Vale inclusive para a chave de cifragem ausente: sem
                # `PORTAL_CHAVE_DE_CIFRAGEM` a senha do banco do cliente não
                # pode ser guardada, e gravar a empresa sem ela deixaria a
                # conexão pela metade.
                raise _CadastroRecusado(erro)
            registrar(ACOES.USUARIO_CRIADO, request.usuario, alvo=email, request=request)
    except _CadastroRecusado as recusa:
        return _desenhar(request, erro=recusa.frase)
    # O aviso da senha só faz sentido quando ela foi GERADA: quem a digitou já
    # a conhece, e repeti-la numa faixa amarela na tela é expor à toa o que
    # está na mão de quem cadastrou.
    if digitada:
        return _desenhar(request)
    return _desenhar(
        request, senha_temporaria=senha_temporaria, login_da_senha=email)


def _acao_editar(request, alvo) -> HttpResponse:
    nome = request.POST.get("nome", "").strip()
    if not nome:
        return _desenhar(request, erro=_("Informe um nome."))
    # `is_superuser` também não é lido aqui: editar nunca promove,
    # mesmo que o POST forjado traga o campo — a view simplesmente não
    # o consulta.
    # Vazio no editar é "não mexe", e não "apaga": ver o comentário no campo,
    # em `_modais_de_usuario`. Um e-mail escrito errado, porém, é recusado do
    # mesmo jeito que no cadastro — aceitar e guardar lixo seria pior que
    # recusar.
    email_bruto = request.POST.get("email", "").strip()
    email = _email_valido(email_bruto) if email_bruto else ""
    if email is None:
        return _desenhar(request, erro=_("Informe um e-mail válido."))
    # **A mesma recusa de duplicata do cadastro, e ela faltava aqui.**
    # Enquanto o e-mail era coluna comum do `auth.User`, dois iguais não
    # colidiam com nada; agora ele é `unique=True` e é o login, e gravar por
    # cima levantava `IntegrityError` dentro do `atomic()` — HTTP 500 na cara
    # de quem só estava corrigindo um erro de digitação. `exclude(pk=...)`
    # porque salvar a ficha com o PRÓPRIO e-mail no campo não é duplicata.
    if email and _login_ocupado(email, menos=alvo.pk):
        return _desenhar(
            request, erro=f'Já existe alguém com o login "{email}".')
    # Mesma recusa de `_acao_criar`, pelo mesmo motivo.
    for campo, rotulo, valor in (("nome", "nome", nome),
                                 ("email", "e-mail", email)):
        if len(valor) > _limite(campo):
            return _desenhar(request, erro=(
                f"O {rotulo} tem {len(valor)} caracteres e o limite é "
                f"{_limite(campo)}."))
    # Só mexe nas alocações quando o bloco veio no POST (campo `alocacoes`):
    # um POST que não passou pela tela não apaga o lugar de ninguém por não
    # ter mandado linha nenhuma. As mesmas travas de `_acao_criar` — editar não
    # pode ser a porta dos fundos do que criar tranca.
    mexe_nas_alocacoes = bool(request.POST.get("alocacoes"))
    linhas: dict = {}
    if mexe_nas_alocacoes:
        linhas, erro = _ler_alocacoes(request)
        if erro:
            return _desenhar(request, erro=erro)
        if _exige_alocacao(request) and not linhas:
            return _desenhar(
                request, erro=_("Aloque a pessoa em pelo menos um lugar."))
    try:
        with transaction.atomic():
            alvo.nome = nome
            campos = ["nome"]
            if email:
                alvo.email = email
                campos.append("email")
            alvo.save(update_fields=campos)
            _salvar_acesso(request, alvo, request.POST.get("nivel", ""),
                           request.POST.get("conta", ""))
            if mexe_nas_alocacoes or alvo.nivel <= Nivel.TITULAR:
                _gravar_alocacoes(request, alvo, linhas)
            registrar(ACOES.USUARIO_EDITADO, request.usuario, alvo=alvo.email, request=request)
    except _CadastroRecusado as recusa:
        return _desenhar(request, erro=recusa.frase)
    return HttpResponseRedirect(reverse("usuarios"))


def _acao_senha(request, alvo) -> HttpResponse:
    senha_temporaria = get_random_string(TAMANHO_DA_SENHA_TEMPORARIA)
    with transaction.atomic():
        alvo.set_password(senha_temporaria)
        # A temporária entregue pelo admin É a senha nova de verdade: a
        # contagem de expiração do alvo recomeça daqui.
        alvo.senha_definida_em = timezone.now()
        alvo.save(update_fields=["password", "senha_definida_em"])
        registrar(ACOES.SENHA_RESETADA, request.usuario, alvo=alvo.email, request=request)
    return _desenhar(
        request, senha_temporaria=senha_temporaria,
        login_da_senha=alvo.email)


def _trocar_estado(request, alvo, ativar: bool) -> HttpResponse:
    """Liga ou desliga a conta de `alvo`.

    Duas ações, uma função: o que muda entre ativar e desativar é um booleano
    e qual palavra vai para a trilha. O que NÃO muda é a trava — e ela vale
    só para desativar, porque reativar a própria conta não tranca ninguém
    para fora.
    """
    if not ativar and _e_voce_mesmo(request, alvo):
        return _desenhar(
            request, erro=_("Você não pode desativar a própria conta."))
    with transaction.atomic():
        alvo.is_active = ativar
        alvo.save(update_fields=["is_active"])
        registrar(
            ACOES.USUARIO_REATIVADO if ativar else ACOES.USUARIO_DESATIVADO,
            request.usuario, alvo=alvo.email, request=request,
        )
    return HttpResponseRedirect(reverse("usuarios"))


def _acao_ativar(request, alvo) -> HttpResponse:
    return _trocar_estado(request, alvo, ativar=True)


def _acao_desativar(request, alvo) -> HttpResponse:
    return _trocar_estado(request, alvo, ativar=False)


def _acao_remover(request, alvo) -> HttpResponse:
    if _e_voce_mesmo(request, alvo):
        return _desenhar(
            request, erro=_("Você não pode remover a própria conta."))

    # **A conta com gente dentro não se apaga por engano** (09/09/2026).
    # `Usuario.dono` e `Empresa.dono` são `PROTECT`: apagar o Admin levaria
    # junto o vínculo de toda a equipe dele e deixaria a empresa órfã — e o
    # banco recusa. Sem esta frase a recusa chegaria como `ProtectedError`,
    # que na tela é "Algo inesperado aconteceu".
    presos = alvo.pessoas_da_conta.count()
    if presos:
        return _desenhar(request, erro=(
            f"{alvo.email} é a conta de {presos} "
            f"{'pessoa' if presos == 1 else 'pessoas'}. Mova ou remova essas "
            f"pessoas antes."))
    if alvo.empresas_da_conta.exists():
        return _desenhar(request, erro=(
            f"{alvo.email} é a conta de uma empresa. Passe a empresa para "
            f"outra conta antes de remover."))

    try:
        with transaction.atomic():
            # Registrado ANTES do `delete()`: depois dele não sobra ninguém
            # para ler login e nome — e, dentro do mesmo `atomic()`, uma
            # falha aqui desfaz o registro junto com a remoção, então não há
            # risco de um registro de remoção sobreviver a uma remoção que
            # não aconteceu.
            registrar(ACOES.USUARIO_REMOVIDO, request.usuario, alvo=alvo.email, request=request)
            alvo.delete()
    except ProtectedError:
        # Um módulo de negócio guarda o histórico desta pessoa com `PROTECT`
        # (no Fila Zero, ponto, atendimentos e pausas). Apagar levaria o
        # histórico junto, e o banco
        # recusa; sem esta frase a recusa chegaria como "Algo inesperado
        # aconteceu". O `atomic` já desfez o registro.
        return _desenhar(request, erro=(
            f"{alvo.email} tem histórico gravado. Desative em vez de "
            f"remover."))
    return HttpResponseRedirect(reverse("usuarios"))


#: Ação que não mexe em ninguém existente.
ACOES_SEM_ALVO = {"criar": _acao_criar}

#: Ações sobre alguém que já existe. O alvo é resolvido no despacho, por
#: `_alcancavel`, antes de qualquer uma delas rodar.
ACOES_COM_ALVO = {
    "editar": _acao_editar,
    "senha": _acao_senha,
    "ativar": _acao_ativar,
    "desativar": _acao_desativar,
    "remover": _acao_remover,
}


@exigir_permissao("usuarios.editar")
@exigir_modulo_ligado("usuarios")
def usuarios(request) -> HttpResponse:
    """A tela de Usuários: uma rota, um `acao` no corpo do POST decide o quê."""
    if request.method != "POST":
        # A exportação roda aqui dentro, depois dos guardas. O queryset é o
        # da tela (a MW5 nunca entra nela).
        if request.GET.get("formato"):
            exportacao = preparar_exportacao(
                request,
                queryset=_com_cargo_ordem(_com_empresa(_pessoas_desta_pessoa(request))),
                colunas=COLUNAS_DE_EXPORTACAO,
                ordenaveis=_ORDENAVEIS, padrao="login",
                filtraveis=_FILTRAVEIS, titulo=_("Usuários"))
            if exportacao is not None:
                return exportacao
        return _desenhar(request)

    acao = request.POST.get("acao", "")

    sem_alvo = ACOES_SEM_ALVO.get(acao)
    if sem_alvo is not None:
        return sem_alvo(request)

    com_alvo = ACOES_COM_ALVO.get(acao)
    if com_alvo is None:
        return HttpResponseRedirect(reverse("usuarios"))

    # A partir daqui toda ação mexe num usuário JÁ existente — e o alvo
    # nunca vem direto do POST: passa por `_alcancavel`, que devolve `None`
    # para qualquer id que não exista OU que seja de um superusuário. Não é
    # um `filter(pk=...).first()` cru: essa é exatamente a segunda metade da
    # defesa que o docstring do módulo descreve.
    alvo = _alcancavel(request, request.POST.get("id", ""))
    if alvo is None:
        # Recusa de verdade — uma frase na tela — e não um redirect
        # silencioso que pareceria sucesso: quem tentou alterar a MW5 (ou um
        # id inexistente) precisa ver que nada aconteceu, não confundir com
        # "deu certo".
        return _desenhar(request, erro=_("Usuário não encontrado."))

    return com_alvo(request, alvo)
