"""Empresas: o cadastro de clientes deste portal, com a conexão de cada um.

**Grid, e não uma linha só — divergência declarada do KRONOS.net.** Lá a
empresa é dado da instalação, como a marca: sessenta VPS, um cliente cada.
Aqui a instalação é UMA, da MW5, e as empresas são os clientes dela — então
a tela é cadastro, com criar, editar e remover.

Segue `plataforma/views_filiais.py`, que é a implementação de referência do
padrão: tabela dentro do cartão, barra de filtro no mesmo cartão, ações da
linha abrindo modal, "Nova" no cabeçalho. R46 vale em cheio — filtro por
coluna, ordenação e paginação por `comum.listagem.montar_pagina`.

A senha do Kronos legado entra por `Empresa.definir_senha()`, nunca pelo
dicionário de campos: ela tem modal próprio, como a senha de Usuários.
"""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.http import (
    HttpResponse, HttpResponseNotFound, HttpResponseRedirect,
)
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from comum.ambiente import ambiente
from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.exportacao import ColunaDeExportacao, botoes, preparar_exportacao
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import (
    Alert, Badge, Box, Button, Card, Column, Form, FormGrid, IconButton,
    Modal, PageHeader, Raw, SectionLabel, Table, TextInput,
)
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render

from .models import Empresa
from .site import montar_site

__all__ = ["campos_do_cadastro", "criar_do_post", "empresa",
           "senha_do_banco"]

#: Os campos do cadastro, na ordem em que aparecem: nome no model, rótulo, e
#: quantas colunas ocupa na grade.
#:
#: A SENHA NÃO ESTÁ AQUI, de propósito. Ela entra por `definir_senha()`, que
#: cifra; se viajasse neste dicionário, um dia alguém faria
#: `Empresa(**dados)` e gravaria a credencial do cliente em texto claro.
#: `Empresa.clean()` recusaria — mas a tela é o lugar de não tentar.
#: Os campos em TRÊS grupos, e não numa lista só.
#:
#: Eram dezessete campos seguidos, sem nada separando — e as fileiras caíam
#: onde a soma das larguras mandava, não onde o assunto mudava: "Host" e
#: "Porta" nasciam na mesma linha do "CEP". Quem preenchia lia endereço,
#: endereço, endereço, e de repente configuração de banco de dados.
#:
#: São três assuntos que nem sequer se preenchem juntos: a identidade sai do
#: contrato, o endereço sai da nota, e a conexão vem da equipe técnica —
#: muitas vezes semanas depois. O grupo é o que torna isso visível, e o que
#: permite ao terceiro dizer, em uma linha, que ele pode ficar vazio.
#:
#: As larguras somam 12 dentro de cada fileira, de propósito: campo que sobra
#: meia fileira vazia à direita parece campo faltando.
GRUPOS: tuple[tuple[str, tuple[tuple[str, str, int], ...]], ...] = (
    ("Identidade", (
        ("razao_social", "Razão social", 7),
        ("nome_fantasia", "Nome fantasia", 5),
        ("cnpj", "CNPJ", 6),
        ("inscricao_estadual", "Inscrição estadual", 6),
    )),
    #: Três fileiras, e a terceira é só UF e CEP.
    #:
    #: Eles vinham espremidos no fim da fileira do bairro — `1` e `2` de doze
    #: dentro de uma coluna que já é a estreita das duas, o que dava menos de
    #: 50px para a sigla e menos de 100 para o CEP. Campo em que não cabe o
    #: que ele pede é campo que parece quebrado, e o CEP ainda leva máscara.
    #:
    #: Bairro e município dividem a fileira ao meio: são dois nomes de
    #: comprimento parecido, e qualquer divisão desigual entre eles seria
    #: arbitrária.
    ("Endereço", (
        ("logradouro", "Logradouro", 7),
        ("numero", "Número", 2),
        ("complemento", "Complemento", 3),
        ("bairro", "Bairro", 6),
        ("municipio", "Município", 6),
        ("uf", "UF", 3),
        ("cep", "CEP", 4),
    )),
)

#: A conexão fica na COLUNA DA DIREITA, e não no fim da lista de campos.
#:
#: Ela é assunto de outra equipe e de outro dia — a empresa entra no cadastro
#: semanas antes de a conexão existir. Na fileira, ela era só "mais campos", e
#: "Host" nascia na mesma linha do "CEP". Numa coluna com fundo próprio, o
#: olho vê duas coisas diferentes sem precisar ler nenhuma.
#:
#: Larguras sobre 12 dentro da coluna estreita, que é mais apertada — daí
#: `Porta` e `Banco` dividindo uma fileira e o resto ocupando a largura toda.
#:
#: Nomes iguais aos de `api_conexao` no `kronos-api2` — ver
#: `tests/test_empresa_esquema.py`.
CONEXAO: tuple[tuple[str, str, int], ...] = (
    ("host", "Host", 12),
    ("porta", "Porta", 5),
    ("banco", "Banco", 7),
    ("tabela", "Tabela", 12),
    ("usuario", "Usuário do banco", 12),
)

#: A senha não entra em `CONEXAO` nem em `CAMPOS`, e a diferença não é
#: cosmética: tudo o que está nessas listas é lido do POST e atribuído à
#: coluna direto (`_dados_do_post`). A senha NUNCA pode entrar por aí — ela só
#: passa por `Empresa.definir_senha()`, que cifra, e o `clean()` do model
#: recusa qualquer valor que não tenha vindo de lá. Ela é desenhada à parte e
#: gravada à parte, no mesmo POST.
CAMPO_DA_SENHA = ("senha", "Senha do banco")

#: A lista achatada, para quem só precisa saber quais colunas a tela edita —
#: o POST, a validação e os valores de partida. Deriva das duas listas acima
#: para não existirem duas verdades divergindo no dia em que um campo entrar.
CAMPOS: tuple[tuple[str, str, int], ...] = tuple(
    campo for _resto, campos in GRUPOS for campo in campos) + CONEXAO

#: Único campo que o model exige. Os outros ficam opcionais porque um
#: cliente entra no cadastro antes de a conexão dele existir.
OBRIGATORIOS = frozenset({"razao_social"})

#: Os atributos que ligam a máscara do `mw5.js`. A validação de verdade mora
#: no model; isto só formata enquanto se digita.
ATRIBUTOS_DE_MASCARA = {
    "cnpj": {"data-mascara": "cnpj", "inputmode": "numeric"},
    "cep": {"data-mascara": "cep", "inputmode": "numeric"},
}

_ORDENAVEIS = {
    "empresa": ("razao_social",),
    "cnpj": ("cnpj",),
    "municipio": ("municipio", "uf"),
    "host": ("host", "porta"),
    "conexao": ("senha", "host"),
}

_FILTRAVEIS = {
    "empresa": ColunaFiltravel(("razao_social", "nome_fantasia"), "Empresa"),
    "cnpj": ColunaFiltravel("cnpj", "CNPJ"),
    "municipio": ColunaFiltravel("municipio", "Município"),
    "host": ColunaFiltravel("host", "Host"),
}


def _campo_oculto(nome: str, valor: str) -> str:
    return format_html('<input type="hidden" name="{}" value="{}">', nome, valor)


def _valores_de(linha: "Empresa | None") -> dict[str, str]:
    origem = linha or Empresa()
    return {nome: getattr(origem, nome) or "" for nome, _resto, _resto in CAMPOS}


def _validar(dados: dict[str, str]) -> "str | None":
    if not dados.get("razao_social", "").strip():
        return "Informe a razão social."
    return None


def _entrada(nome: str, rotulo: str, cols: int, valores: dict,
             exigir: bool = True) -> TextInput:
    """Um campo, com o tamanho lido do MODEL.

    Dois números para a mesma coluna divergem no dia em que um deles muda, e
    o que não muda é o que mente.

    **`exigir=False` quando este formulário está EMBUTIDO em outro** — o
    cadastro de usuário. Lá o bloco da empresa some quando o nível não é
    TITULAR, e um `required` num campo escondido trava o envio inteiro com
    "An invalid form control with name='razao_social' is not focusable": o
    navegador recusa a submissão e não consegue focar o campo para explicar.
    Quem tenta criar um vendedor fica preso numa tela sem nada dizendo o que
    houve.

    Quem RECUSA continua sendo o servidor, e a regra lá é outra e mais certa:
    sem razão social, o titular nasce sem empresa (`_criar_a_empresa_da_conta`).
    """
    return TextInput(
        name=nome, label=rotulo, span=cols, value=valores.get(nome, ""),
        required=exigir and nome in OBRIGATORIOS,
        maxlength=Empresa._meta.get_field(nome).max_length,
        attrs=ATRIBUTOS_DE_MASCARA.get(nome, {}))


def _campo_da_senha(alvo: "Empresa | None") -> Raw:
    """O campo da senha, com o olho que a busca e a esconde.

    O `<input>` nasce SEMPRE vazio, inclusive ao editar: a senha não viaja no
    HTML da lista — ver `senha_do_banco`. O olho só aparece quando há uma
    gravada, porque um olho que revela vazio é um botão que mente.

    `data-ep-senha` carrega o id da empresa, que é o que o script precisa para
    saber a quem pedir. Sem empresa (o modal de criar), não há o que ver.
    """
    from django.utils.html import format_html

    tem = bool(alvo and alvo.senha)
    olho = format_html(
        '<button type="button" class="ep-olho" data-ep-senha="{}" '
        'aria-label="Ver a senha gravada" title="Ver a senha gravada">'
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/>'
        '<circle cx="12" cy="12" r="3"/></svg></button>',
        alvo.pk) if tem else ""
    return Raw(html=format_html(
        '<div class="f c12 ep-senha"><label for="senha">Senha do banco</label>'
        '<input class="ctl" type="password" id="senha" name="senha" value="" '
        'autocomplete="new-password" placeholder="{}">{}'
        '<span class="help">{}</span></div>',
        "••••••••  já gravada" if tem else "nenhuma senha gravada",
        olho,
        "Em branco, mantém a que já está gravada."
        if tem else "Guardada cifrada — nunca em texto claro no banco."))


def _campos(valores: dict[str, str], alvo: "Empresa | None" = None,
            exigir: bool = True, conexao: bool = True) -> list:
    """O cadastro à ESQUERDA e a conexão à DIREITA — ver `GRUPOS` e `CONEXAO`.

    A mesma estrutura do modal de Usuários, e isso é o principal: as duas
    telas de cadastro do sistema passam a se parecer, e quem aprendeu uma não
    precisa reaprender a outra.

    Numa tela estreita as duas viram uma, com a conexão embaixo: ela é a parte
    que se preenche depois, então vir por último é a ordem certa de ler.

    **`conexao=False` some com a coluna inteira, e é o caso do TITULAR**
    (10/09/2026). Host, banco, usuário e senha do Oracle são a ligação da
    INSTALAÇÃO com o Kronos: quem a monta é a MW5, e quem erra ali derruba a
    carga do catálogo de um cliente. O titular edita os dados da empresa
    dele; a conexão não é dado dele.

    Ausente e não desabilitada, pela regra de sempre desta casa: campo que a
    pessoa vê e não pode usar é a tela prometendo o que não cumpre. Quem
    RECUSA de verdade é `_dados_do_post`, que nem lê esses campos do POST de
    quem não é MW5.
    """
    esquerda = [
        Box(body=[
            SectionLabel(label=titulo),
            FormGrid(children=[_entrada(nome, rotulo, cols, valores, exigir)
                               for nome, rotulo, cols in campos]),
        ])
        for titulo, campos in GRUPOS
    ]

    if not conexao:
        # Uma coluna só. Sem a `ep-duas` em volta, o formulário ocupa a
        # largura do modal em vez de deixar metade dela vazia.
        return esquerda

    return [Box(css_class="ep-duas", body=[
        Box(css_class="ep-form", body=esquerda),
        # Sem frase explicando o grupo: o rótulo "Conexão com o Kronos" e os
        # nomes dos campos (Host, Banco, Usuário do banco) já dizem o que é, e
        # a coluna própria já diz que é outro assunto. A frase só empurrava o
        # primeiro campo para baixo, desalinhando as duas colunas logo na
        # primeira linha. Que ela pode ficar em branco, quem diz é o `*` que
        # NÃO está em nenhum destes campos.
        Box(css_class="ep-lado", body=[
            SectionLabel(label=_("Conexão com o Kronos")),
            FormGrid(children=[_entrada(nome, rotulo, cols, valores, exigir)
                               for nome, rotulo, cols in CONEXAO]),
            # Fora do `FormGrid` porque leva o botão do olho por dentro, e o
            # `TextInput` do design system não tem onde encaixá-lo. Ver
            # `_campo_da_senha`.
            _campo_da_senha(alvo),
        ]),
    ])]


def _rodape(rotulo: str) -> str:
    """As ações no fim, com fio e à direita.

    O botão nascia colado no último campo, na largura de um controle qualquer
    e encostado à esquerda — num formulário de dezessete campos, quem rolava
    até o fim não via onde ele terminava. O par mora em
    `contas.views_usuarios._rodape`.
    """
    from django.utils.html import format_html

    return format_html(
        '<div class="ep-rodape">'
        '<button type="button" class="btn ghost" data-modal-close>'
        'Cancelar</button>'
        '<button type="submit" class="btn primary">{}</button></div>',
        rotulo)


def _endereco_do_banco(e: Empresa) -> str:
    """Host e porta juntos, como se escreve numa string de conexão."""
    if not e.host:
        return "—"
    return f"{e.host}:{e.porta}" if e.porta else e.host


def _colunas(pagina) -> list[Column]:
    """`pagina.cabecalho` transforma o rótulo em link de ordenar — R46."""
    return [
        Column("empresa", pagina.cabecalho("empresa", "Empresa"), strong=True,
               render=lambda e: str(e)),
        Column("cnpj", pagina.cabecalho("cnpj", "CNPJ"),
               render=lambda e: e.cnpj or "—"),
        Column("municipio", pagina.cabecalho("municipio", "Município/UF"),
               render=lambda e: f"{e.municipio}/{e.uf}" if e.municipio else "—"),
        Column("host", pagina.cabecalho("host", "Host"), render=_endereco_do_banco),
        # A senha NUNCA aparece, nem cifrada: o que a tela diz é se a conexão
        # está pronta para o cron. Mostrar o texto cifrado não ajudaria
        # ninguém e convidaria a copiar de uma tela para outra o que só
        # deveria passar por `definir_senha()`.
        Column("conexao", pagina.cabecalho("conexao", "Conexão"), align="center",
               render=lambda e: Badge(
                   label="Pronta" if (e.host and e.senha) else "Incompleta",
                   tone="primary" if (e.host and e.senha) else "neutral")),
    ]


def _id_do_modal(acao: str, pk: int) -> str:
    """O gatilho na linha e o `Modal` de verdade nunca podem divergir sobre o
    id, então os dois calculam pela mesma função."""
    return f"empresa-{pk}-{acao}"


def _acoes_da_linha(pode_remover: bool):
    """Editar e senha para quem alcança a empresa; REMOVER só para a MW5.

    O botão de remover não fica desabilitado, fica ausente: um ícone que
    abre um modal para depois recusar é um caminho que só existe para
    terminar em erro.
    """
    def acoes(e: Empresa) -> Box:
        # `wrap=False`: a coluna de ações é estreita, e `.box` nasce com
        # `flex-wrap: wrap` — sem isto os ícones caem um embaixo do outro e
        # esticam a altura de toda linha.
        botoes = [
            IconButton(icon="edit", title=_("Editar"),
                       attrs={"data-open-modal": _id_do_modal("editar", e.pk)}),
        ]
        if pode_remover:
            botoes.append(IconButton(
                icon="trash", title=_("Remover"),
                attrs={"data-open-modal": _id_do_modal("remover", e.pk)}))
        return Box(direction="row", gap="sm", wrap=False, align="end",
                   cross="center", body=botoes)
    return acoes


def _modais_da_empresa(request, e: Empresa,
                       mestre: bool) -> list[Modal]:
    modais = [
        Modal(id=_id_do_modal("editar", e.pk), title=f"Editar {e}", size="lg",
              body=Form(action=reverse("empresa"), children=[
                  Raw(html=campo_csrf(request)),
                  Raw(html=_campo_oculto("acao", "salvar")),
                  Raw(html=_campo_oculto("empresa", str(e.pk))),
                  *_campos(_valores_de(e), alvo=e, conexao=mestre),
                  Raw(html=_rodape("Salvar")),
              ])),
    ]
    if mestre:
        modais.append(Modal(
            id=_id_do_modal("remover", e.pk), title=_("Remover empresa"),
            body=Form(action=reverse("empresa"), children=[
                Raw(html=campo_csrf(request)),
                Raw(html=_campo_oculto("acao", "remover")),
                Raw(html=_campo_oculto("empresa", str(e.pk))),
                Alert(tone="danger",
                      message=f'Remover "{e}"? Esta ação não pode ser '
                              f'desfeita. Empresa com filial não é '
                              f'removida — apague as filiais antes.'),
                Button(label=_("Remover"), variant="danger", type="submit"),
            ])))
    return modais


#: As colunas que saem no Excel e no papel. Nem a senha nem o usuário do
#: banco saem: relatório é de onde o dado escapa mais fácil, e um Excel com
#: o usuário de acesso ao ERP do cliente circulando por e-mail é o pior
#: caminho possível para essa informação.
COLUNAS_DE_EXPORTACAO = (
    ColunaDeExportacao("empresa", "Empresa", lambda e: str(e)),
    ColunaDeExportacao("cnpj", "CNPJ", lambda e: e.cnpj or ""),
    ColunaDeExportacao("municipio", "Município",
                       lambda e: f"{e.municipio}/{e.uf}" if e.municipio else ""),
    ColunaDeExportacao("conexao", "Conexão",
                       lambda e: "Pronta" if (e.host and e.senha) else "Incompleta"),
)


def _desenhar(request, erro: "str | None" = None) -> HttpResponse:
    """A tabela, para os dois — e a diferença fica nas AÇÕES da linha.

    **O titular voltou para a tabela em 10/09/2026**, e é a segunda vez que
    esta tela troca de forma. Ela era tabela, virou formulário direto em
    09/09 com o argumento de que "abrir uma tabela de uma linha para clicar
    num lápis são três passos até o campo que a pessoa veio mudar", e volta
    agora por decisão de quem usa.

    O argumento de lá continua verdadeiro e não foi esquecido: uma conta tem
    UMA empresa, e a tabela do titular sempre terá uma linha. O que pesou mais
    é o resto do sistema: toda tela de cadastro desta casa é tabela com
    filtro, ordenação e paginação (regra R46), e uma que foge disso obriga
    quem já aprendeu o padrão a aprender uma exceção.

    Quem RECUSA criar e remover continua sendo o servidor: `ACOES_SEM_ALVO`
    está vazio (a empresa nasce no cadastro do titular) e o botão de remover
    só é desenhado para a MW5 (`_acoes_da_linha`).
    """
    mestre = _e_master(request)
    env = ambiente()
    with use_environment(env):
        site = montar_site(request)

        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=_("Empresas") if mestre else _("Empresa"),
                       subtitle=(
                           _("Os clientes deste portal, e de onde o cron lê "
                             "os dados de cada um.") if mestre else
                           _("Os dados da sua empresa, e de onde o cron lê o "
                             "catálogo dela no Kronos.")),
                       # **Sem "Nova empresa"** (09/09/2026). A empresa
                       # nasce no cadastro do TITULAR, junto com a conta:
                       # uma conta tem uma empresa, e criar uma aqui daria
                       # uma empresa sem dono — que ninguém abre, e que fica
                       # na lista sem nada explicando o que falta nela. Esta
                       # tela lista e edita; quem cria é `contas.usuarios`.
                       actions=[*botoes(request)]),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))

        listagem = montar_pagina(
            request, _alcancadas(request), ordenaveis=_ORDENAVEIS,
            padrao="empresa", filtraveis=_FILTRAVEIS)

        # **A conta sem empresa precisa de frase, e não de tabela vazia.** É
        # estado que a migração `0008` produz de verdade: dois titulares
        # disputavam a mesma empresa e o segundo ficou sem nenhuma. Sem isto
        # ele abre uma tabela vazia e não tem como saber que o problema não é
        # dele.
        if not mestre and not listagem.linhas:
            conteudo.append(Alert(tone="warn", message=_(
                "Esta conta ainda não tem empresa. Fale com a MW5 — a empresa "
                "é cadastrada junto com a conta, e esta ficou sem.")))

        conteudo.append(Card(
            # "existentes", como nas outras quatro listas da casa (Usuários,
            # Perfis, Filiais, e a de registros da auditoria). Esta dizia
            # "cadastradas" e era a única fora do vocabulário — palavra
            # diferente para a mesma coisa faz procurar a diferença.
            title=_("Empresas existentes") if mestre else _("Sua empresa"),
            padded=False,
            body=[
                listagem.barra,
                Table(columns=_colunas(listagem), rows=listagem.linhas,
                      row_actions=_acoes_da_linha(mestre)),
                listagem.paginacao,
            ],
        ))

        modais: list = []
        for linha in listagem.linhas:
            modais.extend(_modais_da_empresa(request, linha, mestre))

        pagina = site.page(
            title=_("Empresas") if mestre else _("Empresa"),
            width="full",
            stylesheets=["/static/plataforma/listagem.css",
                         "/static/plataforma/empresa.css"],
            scripts=["/static/plataforma/empresa.js"],
            content=conteudo,
            crumbs=[Crumb(_("Empresas") if mestre else _("Empresa"))],
            user=getattr(request, "usuario", None),
            overlays=modais,
        )
        return render(pagina)


def _dados_do_post(request) -> dict[str, str]:
    """Os campos que ESTA pessoa pode gravar.

    **A conexão é só da MW5** (10/09/2026), e a trava é aqui e não na tela:
    esconder os campos evita o engano, mas um POST forjado com `host=` e
    `senha=` chegaria igual — e trocar o host de um cliente é apontar a carga
    do catálogo dele para outro banco.

    Fora da lista, o campo simplesmente não é lido: o valor que está gravado
    fica onde está, e não há um `if` de permissão espalhado por quem grava.
    """
    editaveis = CAMPOS if _e_master(request) else tuple(
        campo for campo in CAMPOS if campo not in CONEXAO)
    return {nome: request.POST.get(nome, "").strip()
            for nome, _resto, _resto in editaveis}


def _frase_da_recusa(erro) -> str:
    """A `ValidationError` do model virada em uma frase para a tela.

    **Existe porque a tela devolvia HTTP 500 para um CNPJ digitado errado.**
    O model faz a coisa certa — recusa documento inválido no `save()`, porque
    a tela nunca é a única porta —, mas a view não capturava, e a exceção
    subia até a página de erro. Um dígito trocado dava "Algo inesperado
    aconteceu", que é ao mesmo tempo assustador e inútil: não diz qual campo,
    e sugere defeito do sistema quando é um erro de digitação.

    As mensagens do model já vêm escritas para gente ("O CNPJ precisa ter 14
    dígitos. Campo: CNPJ."), então aqui só se juntam. Mais de um campo errado
    vira mais de uma frase, na ordem em que o model as produziu.
    """
    mensagens = []
    for lista in getattr(erro, "message_dict", {}).values():
        mensagens.extend(lista)
    if not mensagens:
        mensagens = list(getattr(erro, "messages", []))
    return " ".join(mensagens) or "Não foi possível gravar."


def campos_do_cadastro(request=None) -> list:
    """O formulário de empresa, montado para OUTRA tela embutir.

    Existe porque o cadastro de Titular passou a criar a empresa junto
    (09/09/2026): conta e empresa nascem no mesmo ato, e pedir para cadastrar
    o titular, salvar, ir a Empresas e cadastrar de novo seria pedir duas
    vezes a mesma coisa.

    **Reusa, e não copia.** Uma segunda lista de campos aqui divergiria da
    primeira no dia em que um campo entrasse — e o campo novo apareceria numa
    tela e não na outra, sem erro nenhum.

    Sem `alvo`: quem embute está sempre CRIANDO. Editar continua sendo na
    tela de Empresas, que é onde a empresa mora.
    """
    return _campos(_valores_de(None), alvo=None, exigir=False)


def criar_do_post(request, dono=None) -> "tuple[Empresa | None, str]":
    """Cria a empresa com o que veio no POST. Devolve `(empresa, erro)`.

    A frase de recusa volta em vez de virar resposta HTTP: quem chama é outra
    tela, com o formulário dela para redesenhar, e um `HttpResponse` daqui
    jogaria fora o que a pessoa digitou do outro lado.

    **Sem `transaction.atomic()` próprio, de propósito.** Quem chama já está
    dentro de uma — a conta e a empresa nascem juntas ou não nascem — e um
    `atomic` aninhado aqui viraria savepoint, deixando a empresa gravada
    quando o usuário falhasse depois.
    """
    dados = _dados_do_post(request)
    erro = _validar(dados)
    if erro:
        return None, erro
    try:
        nova = Empresa.objects.create(dono=dono, **dados)
        _gravar_senha(request, nova)
    except ValidationError as recusa:
        return None, _frase_da_recusa(recusa)
    except ImproperlyConfigured as falta:
        return None, str(falta)
    return nova, ""


def _acao_salvar(request, alvo: Empresa) -> HttpResponse:
    dados = _dados_do_post(request)
    erro = _validar(dados)
    if erro:
        return _desenhar(request, erro=erro)
    try:
        with transaction.atomic():
            for nome, valor in dados.items():
                setattr(alvo, nome, valor)
            alvo.save()
            _gravar_senha(request, alvo)
            registrar(ACOES.EMPRESA_EDITADA, request.usuario,
                      alvo=str(alvo), request=request)
    except ValidationError as recusa:
        # `alvo` fica com os valores do POST em memória, mas o `atomic`
        # desfez o que foi ao banco — e a resposta é montada por `_desenhar`,
        # que relê da tabela. Nada do que foi recusado sobrevive.
        return _desenhar(request, erro=_frase_da_recusa(recusa))
    except ImproperlyConfigured as falta:
        return _desenhar(request, erro=str(falta))
    return HttpResponseRedirect(reverse("empresa"))


def _gravar_senha(request, alvo: Empresa) -> None:
    """A senha do banco, do mesmo formulário — e pela mesma porta de sempre.

    Ela morava num modal separado, e o motivo era bom: só entra por
    `definir_senha()`, que cifra, e um campo solto no meio dos outros
    convidava a atribuir a coluna direto. O que estava errado era a
    conclusão. A trava não é a tela separada — é o `clean()` do model, que
    recusa qualquer valor sem o prefixo do Fernet. Com ela de pé, o campo
    pode morar no formulário, e quem cadastra deixa de precisar salvar,
    procurar a linha na tabela e abrir um segundo modal para completar o que
    tinha em mãos.

    **Em branco MANTÉM a que está gravada**, e aqui a regra mudou de sentido:
    no modal separado, em branco apagava — o que fazia sentido lá, porque
    abrir aquele modal era um ato deliberado sobre a senha. Num formulário
    onde o campo aparece toda vez que alguém corrige o CEP, apagar por
    omissão destruiria a conexão de quem só queria arrumar o endereço. Para
    tirar a senha, existe o botão ao lado do campo.
    """
    # A senha do banco faz parte da CONEXÃO, e a conexão é da MW5 — mesma
    # regra de `_dados_do_post`, e escrita aqui também porque este campo entra
    # por outra porta (`definir_senha`, que cifra) e não pela lista de campos.
    if not _e_master(request):
        return
    nova = request.POST.get("senha", "")
    if not nova:
        return
    alvo.definir_senha(nova)
    alvo.save(update_fields=["senha"])


class _SemChave(Exception):
    """A instalação não tem `PORTAL_CHAVE_DE_CIFRAGEM`.

    Sem ela `definir_senha` levanta `ImproperlyConfigured`, e antes desta
    tradução isso subia até a página de erro: quem tentasse cadastrar uma
    empresa COM senha via "Algo inesperado aconteceu" e ficava sem a empresa
    — o `atomic()` desfaz tudo. Um erro de configuração da instalação não pode
    parecer defeito do sistema para quem está preenchendo um formulário.
    """


def _acao_remover(request, alvo: Empresa) -> HttpResponse:
    """A recusa de verdade vem do BANCO (`PROTECT`), e não de uma checagem que
    a tela poderia esquecer de fazer. O que mudou foi a explicação.

    A frase daqui dizia: "tem filial cadastrada e não pode ser removida.
    Apague as filiais dela primeiro." Era verdade em agosto, quando `Filial`
    era a única tabela apontando para `Empresa`. Hoje são dezesseis, e o
    catálogo inteiro nasceu depois: uma empresa segurada por dois segmentos e
    três famílias recebia uma frase que citava filiais inexistentes e mandava
    apagar o que não estava no caminho. Mensagem que aponta para o lugar
    errado é pior que erro sem mensagem — manda procurar onde não tem.

    `comum.protecao` pergunta ao MODEL o que segura, em vez de a view chutar.
    A tentativa continua sendo feita: perguntar antes e não tentar deixaria a
    porta aberta para o caso que a contagem não previu, e é o banco que
    decide. A frase é o consolo de quem tomou o não, nunca a trava.
    """
    from comum.protecao import frase_do_impedimento

    nome = str(alvo)
    try:
        with transaction.atomic():
            alvo.delete()
            registrar(ACOES.EMPRESA_EDITADA, request.usuario,
                      alvo=f"{nome} (removida)", request=request)
    except ProtectedError:
        return _desenhar(request, erro=frase_do_impedimento(alvo) or (
            f'"{nome}" não pode ser removida: ainda há registros ligados a '
            f"ela."))
    return HttpResponseRedirect(reverse("empresa"))


#: `acao` do POST -> o que fazer. Tabela em vez de cadeia de `if`: o
#: despacho fica legível e acrescentar uma ação não engorda uma função.
def _alcancadas(request):
    """As empresas que quem está olhando alcança.

    **Era `Empresa.objects.all()`, e isso era um vazamento.** A tela foi
    escrita quando a empresa era UMA linha por instalação — não havia o que
    recortar. Depois que a empresa virou cadastro de várias, a grade continuou
    mostrando todas: um ADMIN ligado a duas empresas via as quatro, com o CNPJ,
    o município e o HOST DO ORACLE das outras duas. O seletor do cabeçalho já
    respeitava o alcance; a grade abaixo dele, não.

    É a mesma função que decide o seletor, e de propósito: duas ideias
    diferentes de "minhas empresas" na MESMA tela divergem na primeira
    mudança de vínculo, e o defeito aparece como "o seletor mostra duas e a
    lista mostra quatro" — que é exatamente o que aconteceu.

    Import tardio pelo mesmo motivo de `plataforma/contexto.py`: `contas` é a
    camada de FORA, e `contas.alcance` importa `plataforma.models` — o import
    no topo daqui inverteria a direção e fecharia o ciclo.
    """
    from contas.alcance import empresas_alcancadas

    return empresas_alcancadas(getattr(request, "usuario", None))


def _e_master(request) -> bool:
    """Quem pode CRIAR e REMOVER empresa.

    Criar uma empresa é criar um inquilino, e isso é da MW5. Um ADMIN que
    criasse uma empresa não ficaria vinculado a ela — a linha nasceria e
    sumiria da lista dele no mesmo instante, que é o pior tipo de botão: o que
    funciona e parece não ter funcionado.
    """
    from contas.alcance import usuario_de
    from contas.models import Nivel

    usuario = getattr(request, "usuario", None)
    if getattr(usuario, "superuser", False):
        return True
    pessoa = usuario_de(usuario)
    return pessoa is not None and pessoa.nivel == Nivel.MASTER


#: **Vazio, e não uma linha esquecida.** Criar empresa saiu daqui em
#: 09/09/2026 e passou para o cadastro do titular (`contas.views_usuarios`):
#: a conta e a empresa dela nascem no mesmo ato. O dicionário fica porque o
#: despacho o consulta, e porque o dia em que existir uma ação sem alvo nesta
#: tela ela tem onde entrar.
ACOES_SEM_ALVO: dict = {}
ACOES_COM_ALVO = {
    "salvar": _acao_salvar,
    "remover": _acao_remover,
}


@exigir_permissao("empresa.editar")
@exigir_modulo_ligado("empresa")
def senha_do_banco(request, pk: int) -> HttpResponse:
    """Devolve a senha do banco de UMA empresa, quando o olho é clicado.

    **Por que uma rota, e não o valor no HTML.** A lista de empresas desenha
    um modal de edição por linha. Uma senha embutida no campo colocaria a
    credencial do Oracle de TODOS os clientes no código-fonte de cada
    carregamento da página — em `Ctrl+U`, no cache do navegador, em qualquer
    captura de tela da lista, e no histórico de quem só queria conferir um
    CEP. Buscada sob demanda, ela só existe no navegador de quem pediu, para a
    empresa que pediu.

    Três travas, e nenhuma delas é a tela:

    1. `empresa.editar` — a mesma permissão que já permite TROCAR a senha.
       Quem pode trocar já pode tornar a antiga inútil; ver não é uma
       escalada.
    2. O alcance: `_alcancadas` recorta pelas empresas da pessoa.
       Um `pk` de outra empresa devolve 404 — não 403, que confirmaria que
       ela existe.
    3. A trilha: ler credencial é um ATO, e fica registrado. Quem viu e
       quando é a pergunta que se faz depois de um vazamento, e ela precisa
       ter resposta.

    Devolve JSON com a senha em claro. É o único lugar do sistema que faz
    isso, de propósito — em qualquer outro, a coluna cifrada é o que existe.
    """
    from django.http import JsonResponse

    alvo = _alcancadas(request).filter(pk=pk).first()
    if alvo is None:
        return HttpResponseNotFound()
    if not alvo.senha:
        return JsonResponse({"senha": ""})

    registrar(ACOES.SENHA_DO_BANCO_VISTA, request.usuario,
              alvo=str(alvo), request=request)
    return JsonResponse({"senha": alvo.senha_clara})


@exigir_permissao("empresa.editar")
@exigir_modulo_ligado("empresa")
def empresa(request) -> HttpResponse:
    exportacao = preparar_exportacao(
        request, queryset=_alcancadas(request),
        colunas=COLUNAS_DE_EXPORTACAO,
        ordenaveis=_ORDENAVEIS, padrao="empresa",
        filtraveis=_FILTRAVEIS, titulo=_("Empresas"))
    if exportacao is not None:
        return exportacao

    if request.method != "POST":
        return _desenhar(request)

    acao = request.POST.get("acao", "")
    if acao in ACOES_SEM_ALVO or acao == "remover":
        if not _e_master(request):
            return _desenhar(request, erro=(
                "Criar e remover empresa é da MW5. Você pode editar as "
                "empresas às quais está vinculado."))
    if acao in ACOES_SEM_ALVO:
        return ACOES_SEM_ALVO[acao](request)
    if acao not in ACOES_COM_ALVO:
        return _desenhar(request, erro=_("Ação desconhecida."))

    # Pelo ALCANCE, e não `Empresa.objects.get`: um id forjado no corpo do
    # POST não pode editar nem apagar a empresa de outro admin.
    alvo = _alcancadas(request).filter(
        pk=_inteiro(request.POST.get("empresa", ""))).first()
    if alvo is None:
        return _desenhar(request, erro=_("Empresa não encontrada."))
    return ACOES_COM_ALVO[acao](request, alvo)


def _inteiro(bruto):
    """`""` e `"abc"` viram `None` em vez de levantar — um id lixo no POST é
    "não encontrada", não erro 500."""
    try:
        return int(bruto)
    except (TypeError, ValueError):
        return None
