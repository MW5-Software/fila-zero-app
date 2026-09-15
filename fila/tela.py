"""O que a página da fila mostra, montado a partir do retrato da loja.

Separado da view para o POST com JavaScript, a consulta de 3 em 3 segundos e
a página inteira desenharem os MESMOS pedaços: se cada um montasse o próprio
HTML, a tela mudaria de cara depois da primeira consulta.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone
from markupsafe import Markup

from comum.csrf import campo_csrf
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.permissoes import pode
from nucleo.rendering import use_environment

from .ambiente import ambiente_da_fila
from .correcoes import lancamentos_de_hoje
from .estado import nome_de, retrato
from .models import (Atendimento, Estado, GrupoDeItem, LugarNaFila,
                     MotivoDeNaoVenda, TipoDePausa)

__all__ = ["PEDACOS", "ha_quanto", "hora_local", "iniciais", "minutos", "pagina",
           "pedacos", "pessoas_na_frente", "sem_loja", "so_a_fila"]

#: Os pedaços que a consulta troca, com o template de cada um.
PEDACOS = {"painel": "fila/_painel.html", "lista": "fila/_lista.html",
           "barra": "fila/_barra.html", "lancamentos": "fila/_lancamentos.html",
           "meus": "fila/_meus.html"}

#: O que o vendedor tem. Quem tem SÓ isto não tem o que fazer no dashboard.
_SO_DO_VENDEDOR = frozenset({"fila.ver", "fila.participar"})

@dataclass(frozen=True)
class Alvo:
    """A pessoa sobre quem o gerente abriu uma folha de correção."""

    pessoa_id: int
    nome: str
    estado: str


_POR_EXTENSO = ("", "uma", "duas", "três", "quatro", "cinco", "seis", "sete",
                "oito", "nove", "dez")


def so_a_fila(user) -> bool:
    """Desvio D-4: cai direto em `/fila` quem só tem a fila de vendedor."""
    if user is None or user.superuser:
        return False
    permissoes = frozenset(user.permissions)
    return "fila.participar" in permissoes and permissoes <= _SO_DO_VENDEDOR


def ha_quanto(instante, agora=None) -> str:
    minutos = int(((agora or timezone.now()) - instante).total_seconds() // 60)
    if minutos < 1:
        return "agora"
    if minutos < 60:
        return f"há {minutos} min"
    return f"há {minutos // 60} h {minutos % 60:02d} min"


def minutos(instante, agora=None) -> int:
    """Minutos inteiros desde `instante`: o cronômetro de quem atende ou pausa."""
    return max(0, int(((agora or timezone.now()) - instante).total_seconds() // 60))


def hora_local(instante) -> str:
    return timezone.localtime(instante).strftime("%H:%M")


def iniciais(nome: str) -> str:
    """"Ana Paula Souza" -> "AS"; "Ana" -> "A". Uma letra por nome, como o
    avatar do cabeçalho, para a pessoa se reconhecer na fila."""
    partes = [p for p in (nome or "").split("@")[0].replace(".", " ").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][0].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def pessoas_na_frente(posicao: int) -> str:
    frente = posicao - 1
    numero = _POR_EXTENSO[frente] if frente < len(_POR_EXTENSO) else str(frente)
    return f"{numero} {'pessoa' if frente == 1 else 'pessoas'} na sua frente"


def _lancamento_em_edicao(request, filial):
    if request.GET.get("folha") != "editar":
        return None
    try:
        atendimento_id = int(request.GET.get("atendimento", ""))
    except ValueError:
        return None
    return (Atendimento.objects.da_empresa(filial.empresa)
            .filter(pk=atendimento_id, filial=filial, fim__isnull=False)
            .select_related("vendedor", "motivo").first())


def _alvo_da_folha(request, filial):
    """A pessoa sobre quem o gerente abriu uma folha (`?pessoa=`), se ela está
    nesta loja. Id forjado ou de outra loja vira `None`, e a folha abre sem
    alvo — o POST confere de novo."""
    try:
        pessoa_id = int(request.GET.get("pessoa", ""))
    except ValueError:
        return None
    lugar = (LugarNaFila.objects.da_empresa(filial.empresa)
             .filter(filial=filial, pessoa_id=pessoa_id)
             .select_related("pessoa").first())
    return (Alvo(lugar.pessoa_id, nome_de(lugar.pessoa), lugar.estado)
            if lugar else None)


@dataclass(frozen=True)
class Resumo:
    """O dia da loja em quatro números, no topo dos lançamentos do gerente."""

    atendimentos: int
    vendas: int
    total: "Decimal"
    conversao: int


def _resumo(lancamentos) -> Resumo:
    from decimal import Decimal

    vendas = [a for a in lancamentos if a.resultado == "vendeu"]
    total = sum((a.total for a in vendas), Decimal("0"))
    conversao = round(100 * len(vendas) / len(lancamentos)) if lancamentos else 0
    return Resumo(len(lancamentos), len(vendas), total, conversao)


def _trilha(r) -> list:
    """Quem está na frente, até a própria pessoa (ou a fila inteira para quem
    não está nela), no máximo seis: a trilha mostra o caminho até a vez, e não
    a fila toda — essa está logo abaixo."""
    fila = r.fila
    ate = next((i for i, l in enumerate(fila) if l.e_voce), len(fila) - 1)
    caminho = fila[:ate + 1]
    if len(caminho) <= 6:
        return list(caminho)
    return [*caminho[:2], None, *caminho[-3:]]


@dataclass(frozen=True)
class MeusNumeros:
    """A faixa do vendedor (spec 2026-09-15 dos indicadores, decisão P-2 do
    plano): os números da loja em que ele está, hoje e no mês, e a posição."""

    hoje: object
    mes: object
    posicao: object


def _meus_numeros(pessoa, filial) -> "MeusNumeros | None":
    from .indicadores import Recorte, numeros, posicao_no_mes
    from .periodo import periodo_do_pedido

    if pessoa is None:
        return None
    lojas = (filial,)
    return MeusNumeros(
        hoje=numeros(Recorte(filial.empresa, lojas, periodo_do_pedido({"periodo": "hoje"})),
                     vendedor=pessoa),
        mes=numeros(Recorte(filial.empresa, lojas, periodo_do_pedido({"periodo": "mes"})),
                    vendedor=pessoa),
        posicao=posicao_no_mes(pessoa, filial))


def _contexto(request, filial, recusa=""):
    pessoa = usuario_de(request.usuario)
    empresa = filial.empresa
    pode_gerenciar = pode(request.usuario, "fila.gerenciar")
    r = retrato(filial, pessoa)
    lancamentos = list(lancamentos_de_hoje(filial)) if pode_gerenciar else []
    return {
        "r": r,
        "trilha": _trilha(r),
        "meus": (_meus_numeros(pessoa, filial)
                 if pode(request.usuario, "fila.participar") else None),
        "resumo": _resumo(lancamentos),
        "Estado": Estado,
        "filial": filial,
        "nome": nome_de(pessoa) if pessoa else "",
        "eu_id": pessoa.pk if pessoa else None,
        "agora": timezone.now(),
        "pode_participar": pode(request.usuario, "fila.participar"),
        "pode_gerenciar": pode_gerenciar,
        "mostra_painel": not so_a_fila(request.usuario),
        "csrf": Markup(campo_csrf(request)),
        "url_fila": reverse("fila"),
        "url_agir": reverse("fila_agir"),
        "url_estado": reverse("fila_estado"),
        "url_sair": reverse("sair"),
        "grupos": list(GrupoDeItem.objects.da_empresa(empresa).filter(ativo=True)),
        "motivos": list(MotivoDeNaoVenda.objects.da_empresa(empresa).filter(ativo=True)),
        "tipos": list(TipoDePausa.objects.da_empresa(empresa).filter(ativo=True)),
        "lancamentos": lancamentos,
        "folha": request.GET.get("folha", ""),
        "alvo": _alvo_da_folha(request, filial) if pode_gerenciar else None,
        "editando": _lancamento_em_edicao(request, filial) if pode_gerenciar else None,
        "recusa": recusa,
    }


def _no_shell(request, titulo: str, conteudo, overlays=""):
    """A página dentro do shell do sistema: o mesmo cabeçalho (seletor de
    filial, idioma, sair, avatar), as mesmas folhas e o mesmo `mw5.js`, sem a
    barra lateral e sem o rodapé.

    Sem menu porque a fila é a tela de quem está em pé no salão, no celular, e
    uma gaveta de módulos ali só disputa espaço com a ação. No lugar do
    caminho de migalhas entra o logo da marca, que no shell mora na barra
    lateral que esta página não tem.
    """
    from django.utils.html import format_html

    from comum.ambiente import ambiente
    from nucleo.components import Raw
    from nucleo.resposta import render
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        pagina = site.page(
            title=titulo, width="wide",
            content=[aviso_de_personificacao(request), conteudo],
            overlays=overlays, user=request.usuario,
            stylesheets=["/static/fila/fila.css"],
            scripts=["/static/fila/fila.js"])
        pagina.sidebar = None
        pagina.footer = None
        pagina.body_class = "fila-pagina"
        logo = site.brand.assets.logo_for("sidebar")
        pagina.header.breadcrumb = Raw(html=format_html(
            '<a class="fila-marca" href="/"><img src="{}" alt="{}"></a>',
            logo, site.brand.client_name)) if logo else None
        return render(pagina)


def pagina(request, filial, recusa=""):
    from nucleo.components import Raw

    env = ambiente_da_fila()
    contexto = _contexto(request, filial, recusa)
    return _no_shell(
        request, f"Fila da vez — {filial}",
        Raw(html=env.get_template("fila/pagina.html").render(**contexto)),
        Raw(html=env.get_template("fila/_folhas.html").render(**contexto)))


def pedacos(request, filial) -> "tuple[str, dict[str, str]]":
    """`(versao, {pedaço: html})` de UMA leitura: a versão devolvida é a do
    retrato que desenhou o HTML, e não uma lida antes ou depois."""
    env = ambiente_da_fila()
    contexto = _contexto(request, filial)
    html = {nome: env.get_template(template).render(**contexto)
            for nome, template in PEDACOS.items()}
    return contexto["r"].versao, html


def sem_loja(request):
    from nucleo.components import EmptyState

    return _no_shell(request, "Fila da vez", EmptyState(
        icon="store", title="Você ainda não está em nenhuma loja",
        message=("Peça a quem cuida da equipe para alocar você na loja em "
                 "que trabalha, na tela de Usuários.")))
