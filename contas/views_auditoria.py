"""A tela de leitura da auditoria: o registro que só existia para ser escrito.

A trilha grava desde a entrega de contas (`comum.auditoria.registrar`), mas
não havia onde lê-la — só `manage.py shell`. Esta tela é SÓ DE LEITURA, e é
a única tela do sistema sem ação nenhuma: a tabela é append-only por
construção (`RegistroDeAuditoria.save`/`delete` recusam), então aqui não há
modal, botão nem POST — qualquer coisa que sugerisse editar o passado seria
mentira desenhada.

R46 vale em cheio: filtro (ação em caixa fechada, autor, alvo, detalhe,
período), ordenação por coluna e paginação por `comum.listagem`.
`montar_pagina` — com o padrão `-quando`, que é o sentido natural de uma
trilha e o sentido do índice que o model já carrega.
"""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseNotAllowed
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from nucleo.components import Card, Column, PageHeader, Table
from nucleo.layout import Crumb
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render
from comum.exportacao import ColunaDeExportacao, botoes, preparar_exportacao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.listagem import ColunaFiltravel, montar_pagina

from comum.auditoria import ROTULOS
from comum.guardas_de_acesso import exigir_permissao
from .models import RegistroDeAuditoria
from comum.personificacao import aviso as aviso_de_personificacao

__all__ = ["auditoria"]

#: As colunas que saem no arquivo e no papel — as MESMAS da tabela, mas
#: devolvendo valor, e não HTML.
COLUNAS_DE_EXPORTACAO = (
    ColunaDeExportacao("quando", "Quando",
                       lambda r: localtime(r.quando).strftime("%d/%m/%Y %H:%M:%S")),
    ColunaDeExportacao("acao", "Ação", lambda r: ROTULOS.get(r.acao, r.acao)),
    ColunaDeExportacao("autor", "Autor",
                       lambda r: (f"{r.autor_nome} ({r.autor_login})"
                                  if r.autor_nome and r.autor_nome != r.autor_login
                                  else r.autor_login)),
    ColunaDeExportacao("alvo", "Alvo", lambda r: r.alvo),
    ColunaDeExportacao("detalhe", "Detalhe", lambda r: r.detalhe),
)


def _opcoes_de_acao() -> "list[tuple[str, str]]":
    """As ações que EXISTEM gravadas, com o rótulo legível, na ordem alfabética
    de leitura.

    Do banco, e não do vocabulário inteiro: oferecer ação que esta instalação
    nunca registrou é ruído na caixa — e uma ação fora do dicionário de
    rótulos aparece como a chave crua, que é exatamente como falta de
    tradução deve aparecer.
    """
    valores = set(
        RegistroDeAuditoria.objects.values_list("acao", flat=True).distinct()
    )
    return sorted(
        ((valor, ROTULOS.get(valor, valor)) for valor in valores),
        key=lambda par: par[1],
    )


#: O que se pode ordenar, e por quais campos reais — nunca o `?ordenar=` cru
#: chega ao `order_by` (`comum.listagem._resolver_ordenacao`).
_ORDENAVEIS = {
    "quando": "quando",
    "acao": "acao",
    "autor": ("autor_login", "autor_nome"),
    "alvo": "alvo",
    "detalhe": "detalhe",
}

_FILTRAVEIS = {
    # Valores fechados e muitos? Muitos não: são as ações do vocabulário que
    # esta instalação já viveu — caixa de escolha, não campo de digitar.
    "acao": ColunaFiltravel("acao", "Ação", tipo="opcoes", opcoes=_opcoes_de_acao),
    # O autor pode ter sido removido depois (o registro sobrevive como
    # texto); buscar pelo login continua encontrando a linha dele.
    "autor": ColunaFiltravel(("autor_login", "autor_nome"), "Autor"),
    "alvo": ColunaFiltravel("alvo", "Alvo"),
    "detalhe": ColunaFiltravel("detalhe", "Detalhe"),
    # É o filtro que responde "o que aconteceu sexta-feira?" — coluna de data
    # ganha "de"/"até" (`OPERADORES["data"]`).
    "quando": ColunaFiltravel("quando", "Data", tipo="data"),
}


def _colunas_da_lista(pagina) -> list[Column]:
    """`pagina.cabecalho` transforma o rótulo em link de ordenar — R46."""
    def _quando(registro):
        return localtime(registro.quando).strftime("%d/%m/%Y %H:%M:%S")

    def _autor(registro):
        if not registro.autor_login:
            return "—"
        if registro.autor_nome and registro.autor_nome != registro.autor_login:
            return f"{registro.autor_nome} ({registro.autor_login})"
        return registro.autor_login

    return [
        Column("quando", pagina.cabecalho("quando", "Quando"),
               render=_quando),
        Column("acao", pagina.cabecalho("acao", "Ação"),
               render=lambda r: ROTULOS.get(r.acao, r.acao)),
        Column("autor", pagina.cabecalho("autor", "Autor"), render=_autor),
        Column("alvo", pagina.cabecalho("alvo", "Alvo"),
               render=lambda r: r.alvo or "—"),
        Column("detalhe", pagina.cabecalho("detalhe", "Detalhe"),
               render=lambda r: r.detalhe or "—"),
    ]


def _desenhar(request) -> HttpResponse:
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=_("Auditoria"),
                       subtitle="O que foi feito nesta instalação, por quem, "
                                "e quando. Registro à parte ninguém apaga.",
                       actions=botoes(request)),
        ]

        listagem = montar_pagina(
            request, RegistroDeAuditoria.objects.all(),
            ordenaveis=_ORDENAVEIS, padrao="-quando",
            filtraveis=_FILTRAVEIS)

        conteudo.append(Card(
            title=_("Registros"), padded=False,
            body=[
                # Mesmo desenho das outras listagens: busca e tabela são o
                # mesmo bloco (`.card .filters` tira a moldura dupla).
                # Filtros salvos (item 27): os desta pessoa nesta tela.
                listagem.barra,
                Table(columns=_colunas_da_lista(listagem),
                      rows=listagem.linhas),
                listagem.paginacao,
            ],
        ))

        pagina = site.page(
            title=_("Auditoria"),
            width="full",
            stylesheets=["/static/plataforma/listagem.css"],
            content=conteudo,
            crumbs=[Crumb(_("Auditoria"))],
            user=getattr(request, "usuario", None),
        )
        # Renderização dentro do `with` — ver o comentário equivalente em
        # `plataforma/views.py::_desenhar`.
        return render(pagina)


def _subtitulo_do_filtro(crus: dict[str, str]) -> str:
    """A frase que vai no papel dizendo qual filtro gerou aquilo — lida dos
    MESMOS valores que `preparar_consulta` aplicou, e não da URL crua."""
    if not crus:
        return "Sem filtro — a trilha inteira."
    partes = []
    for chave_crua, valor in sorted(crus.items()):
        coluna, operador = chave_crua.removeprefix("f:").rpartition(":")[::2]
        nome = _FILTRAVEIS.get(coluna).rotulo if coluna in _FILTRAVEIS else coluna
        sufixo = {"contem": " contém", "de": " de", "ate": " até"}.get(operador, "")
        partes.append(f"{nome}{sufixo} “{valor}”")
    return "Filtro: " + ", ".join(partes) + "."


# A mesma ordem de todas as telas com módulo: `exigir_permissao` por fora
# (cuida de sessão ausente e marca `.exige_login`), `exigir_modulo_ligado`
# por dentro (tranca sozinha com o módulo desligado — inclusive para a MW5).
@exigir_permissao("auditoria.ver")
@exigir_modulo_ligado("auditoria")
def auditoria(request) -> HttpResponse:
    """Leitura pura. Não existe `acao=` no corpo de nada: quem mandar POST
    recebe 405 — a trilha é append-only, e a rota também.

    A exportação (`?formato=xlsx|impressao`) roda aqui dentro, depois dos
    guardas: quem não vê a tela não baixa o arquivo dela.
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    exportacao = preparar_exportacao(
        request, queryset=RegistroDeAuditoria.objects.all(),
        colunas=COLUNAS_DE_EXPORTACAO,
        ordenaveis=_ORDENAVEIS, padrao="-quando", filtraveis=_FILTRAVEIS,
        titulo=_("Auditoria"), subtitulo_fn=_subtitulo_do_filtro)
    if exportacao is not None:
        return exportacao

    return _desenhar(request)
