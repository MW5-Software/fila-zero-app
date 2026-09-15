"""A tela de Parâmetros: o que o código declara, valendo por instalação.

R47 (`docs/superpowers/decisoes-2026-08-20-fatia-fina.md`): módulo fixo,
parâmetro configurável — esta tela é o que faz essa decisão sobreviver ao
primeiro cliente diferente, sem `if` nenhum escrito com o nome dele (a
varredura de `tests/test_sem_nome_de_cliente.py` cobra isso).

Cada parâmetro é a própria linha, agrupado por `ParametroSpec.grupo` — sem
tabela nenhuma (R46, o padrão de busca/ordenação/paginação, não se aplica
aqui por não haver `<table>` para exigi-lo). Cada linha carrega DOIS
`<form>` independentes e nunca aninhados: um para salvar o valor, outro —
só quando o parâmetro já foi mudado nesta instalação — para apagar a linha
e voltar ao padrão do código.
"""

from __future__ import annotations

from itertools import groupby

from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from comum.personificacao import aviso as aviso_de_personificacao
from nucleo.components import (
    Alert, Badge, Box, Button, Card, Checkbox, Form, PageHeader, Raw,
    SectionLabel, TextInput,
)
from nucleo.layout import Crumb
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render

from comum.guardas_de_modulo import exigir_modulo_ligado
from .parametro_catalogo import ParametroEfetivo, converter, definir, normalizar, parametros_efetivos, restaurar
from .site import montar_site

__all__ = ["parametros"]


def _campo_oculto(nome: str, valor: str) -> str:
    """Ver o par exato em `contas.views_usuarios._campo_oculto` — mesma regra:
    `nucleo/` não tem componente de campo oculto, só `Raw` para HTML cru já
    confiável. `valor` nunca é texto de fora sem controle: é sempre a chave
    de um `ParametroSpec` declarado ou uma constante fixa desta view."""
    return format_html('<input type="hidden" name="{}" value="{}">', nome, valor)


def _visivel_para(efetivo: ParametroEfetivo, usuario) -> bool:
    """`so_mw5` é a fronteira entre o que é técnico (MW5) e o que é negócio
    (admin do cliente) — ver o docstring de `ParametroSpec.so_mw5`. Esconder
    a linha aqui NÃO substitui a recusa no POST, abaixo: as duas telas que
    este projeto já corrigiu por confundir "esconder" com "proteger" são o
    motivo de nunca repetir esse erro sozinho de novo."""
    return not efetivo.so_mw5 or bool(usuario and usuario.superuser)


def _texto_do_valor(tipo: str, valor) -> str:
    if tipo == "sim_nao":
        return "Sim" if valor else "Não"
    return str(valor)


def _controle(efetivo: ParametroEfetivo):
    if efetivo.tipo == "numero":
        return TextInput(name="valor", label=efetivo.rotulo, type="number",
                          value=str(efetivo.valor), help=efetivo.ajuda, span=6)
    if efetivo.tipo == "sim_nao":
        return Checkbox(name="valor", label=efetivo.rotulo,
                         checked=bool(efetivo.valor), help=efetivo.ajuda)
    return TextInput(name="valor", label=efetivo.rotulo, value=str(efetivo.valor),
                      help=efetivo.ajuda, span=6)


def _cartao_parametro(request, efetivo: ParametroEfetivo) -> Card:
    selo = Badge(label="Padrão" if efetivo.no_padrao else "Personalizado",
                 tone="neutral" if efetivo.no_padrao else "primary")

    corpo = [
        Form(action=reverse("parametros"), children=[
            Raw(html=campo_csrf(request)),
            Raw(html=_campo_oculto("acao", "salvar")),
            Raw(html=_campo_oculto("chave", efetivo.chave)),
            _controle(efetivo),
            Box(direction="row", gap="sm", align="center", cross="center", body=[
                selo, Button(label=_("Salvar"), variant="primary", size="sm", type="submit"),
            ]),
        ]),
    ]
    # O botão de restaurar só existe quando há o que restaurar: um
    # parâmetro já no padrão não tem linha nenhuma para apagar — mostrar o
    # botão mesmo assim seria oferecer uma ação que não faz nada.
    if not efetivo.no_padrao:
        corpo.append(Form(action=reverse("parametros"), children=[
            Raw(html=campo_csrf(request)),
            Raw(html=_campo_oculto("acao", "restaurar")),
            Raw(html=_campo_oculto("chave", efetivo.chave)),
            Button(label=_("Restaurar padrão"), variant="ghost", size="sm", type="submit"),
        ]))

    return Card(title=efetivo.rotulo, body=corpo)


def _agrupados(efetivos: "list[ParametroEfetivo]"):
    ordenados = sorted(efetivos, key=lambda e: (e.grupo, e.rotulo))
    return groupby(ordenados, key=lambda e: e.grupo)


def _desenhar(request, erro: "str | None" = None) -> HttpResponse:
    env = ambiente()
    with use_environment(env):
        site = montar_site(request)

        visiveis = [e for e in parametros_efetivos()
                    if _visivel_para(e, getattr(request, "usuario", None))]

        conteudo = [
            aviso_de_personificacao(request),
            PageHeader(title=_("Parâmetros"),
                       subtitle=_("O que esta instalação mudou do padrão do código.")),
        ]
        if erro:
            conteudo.append(Alert(message=erro, tone="danger"))

        for grupo, itens in _agrupados(visiveis):
            conteudo.append(SectionLabel(label=grupo))
            for efetivo in itens:
                conteudo.append(_cartao_parametro(request, efetivo))

        pagina = site.page(
            title=_("Parâmetros"),
            width="full",
            content=conteudo,
            crumbs=[Crumb(_("Parâmetros"))],
            user=getattr(request, "usuario", None),
        )
        # Ver o comentário equivalente em `plataforma.views_empresa._desenhar`:
        # a renderização precisa acontecer AQUI dentro do `with`, ou cai no
        # ambiente global e ignora em silêncio um loader extra do cliente.
        return render(pagina)


@exigir_permissao("parametros.editar")
@exigir_modulo_ligado("parametros")
def parametros(request) -> HttpResponse:
    """A tela de Parâmetros: um `acao` no corpo do POST decide salvar ou
    restaurar — sempre para UM parâmetro por vez, o que cada `<form>` da
    tela envia sozinho (ver `_cartao_parametro`)."""
    if request.method != "POST":
        return _desenhar(request)

    chave = request.POST.get("chave", "")
    acao = request.POST.get("acao", "")

    # A mesma checagem de visibilidade do GET, e não por acaso: um parâmetro
    # que a tela esconde de quem não é MW5 tem que continuar inalcançável
    # também aqui, ou esconder na tela seria só cosmético. Chave
    # desconhecida cai na MESMA frase que uma chave só-MW5 tentada por quem
    # não é MW5 — nenhuma delas pode dizer "existe, mas você não pode", que
    # denunciaria por texto o que a tela já esconde visualmente.
    visiveis = {e.chave: e for e in parametros_efetivos()
                if _visivel_para(e, getattr(request, "usuario", None))}
    efetivo = visiveis.get(chave)
    if efetivo is None:
        return _desenhar(request, erro=_("Parâmetro não encontrado."))

    if acao == "restaurar":
        with transaction.atomic():
            restaurar(chave)
            registrar(
                ACOES.PARAMETRO_RESTAURADO, request.usuario, alvo=efetivo.rotulo,
                detalhe=f"voltou ao padrão ({_texto_do_valor(efetivo.tipo, efetivo.padrao)})",
                request=request,
            )
        return HttpResponseRedirect(reverse("parametros"))

    if acao == "salvar":
        # `sim_nao` vem de um `Checkbox`: desmarcado é a chave AUSENTE do
        # POST, não uma string vazia — por isso não usa `.get(..., "")`
        # como os outros dois tipos.
        bruto = (request.POST.get("valor") if efetivo.tipo == "sim_nao"
                 else request.POST.get("valor", "").strip())
        valor_normalizado, erro = normalizar(efetivo.tipo, bruto)
        if erro:
            return _desenhar(request, erro=f'"{efetivo.rotulo}": {erro}')
        with transaction.atomic():
            definir(chave, valor_normalizado)
            novo = converter(efetivo.tipo, valor_normalizado)
            registrar(
                ACOES.PARAMETRO_ALTERADO, request.usuario, alvo=efetivo.rotulo,
                detalhe=f"novo valor: {_texto_do_valor(efetivo.tipo, novo)}",
                request=request,
            )
        return HttpResponseRedirect(reverse("parametros"))

    return HttpResponseRedirect(reverse("parametros"))
