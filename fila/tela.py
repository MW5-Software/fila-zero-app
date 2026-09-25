"""O que a página da fila mostra, montado a partir do retrato da loja.

Separado da view para o POST com JavaScript, a consulta de 3 em 3 segundos e
a página inteira desenharem os MESMOS pedaços: se cada um montasse o próprio
HTML, a tela mudaria de cara depois da primeira consulta.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from markupsafe import Markup

from comum.csrf import campo_csrf
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from plataforma.contexto import filiais_de
from nucleo.permissoes import pode
from nucleo.rendering import use_environment

from . import quem_atende
from .ambiente import ambiente_da_fila
from .correcoes import lancamentos_de_hoje
from .estado import nome_de, retrato
from .models import (Atendimento, Estado, GrupoDeItem, LugarNaFila,
                     Midia, MotivoDeNaoVenda, PausaFixa, TipoDePausa)

__all__ = ["PEDACOS", "atende", "ha_quanto", "hora_local", "iniciais", "minutos",
           "pagina", "pedacos", "pessoas_na_frente", "sem_loja", "so_a_fila"]

#: Os pedaços que a consulta troca, com o template de cada um.
PEDACOS = {"painel": "fila/_painel.html", "lista": "fila/_lista.html",
           "barra": "fila/_barra.html", "lancamentos": "fila/_lancamentos.html",
           "meus": "fila/_meus.html",
           # As posições do "Recolocar na fila" (25/09/2026): mudam com a fila.
           "posicoes": "fila/_posicoes.html",
           # E as do "Mudar de posição", pelo mesmo motivo.
           "mover": "fila/_mover.html"}

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


def trocar_e_abrir_a_fila(loja) -> str:
    """O endereço que troca a filial da sessão para `loja` e volta para a
    fila. A troca pede confirmação (`plataforma.views_filial.filial_trocar`),
    porque GET não muda estado nesta casa."""
    from urllib.parse import urlencode

    from plataforma.contexto import CHAVE

    return f"{reverse('filial_trocar')}?{urlencode({CHAVE: loja.pk, 'voltar': reverse('fila')})}"


def so_a_fila(user) -> bool:
    """Desvio D-4: entra direto em `/fila` quem só tem a fila de vendedor.
    Vale só na entrada (`fila.sinais.destino_do_vendedor`): a raiz é o painel
    dele (spec 2026-09-16)."""
    if user is None or user.superuser:
        return False
    permissoes = frozenset(user.permissions)
    return "fila.participar" in permissoes and permissoes <= _SO_DO_VENDEDOR


def _tem_numeros(usuario, r) -> bool:
    """Se a página mostra "Seus números": a quem atende, a quem já está na
    loja, e a quem gerencia só com o parâmetro `meta_para_gestor` ligado — a
    MESMA gente que tem meta (`fila.metas._participa`).

    Era `fila.participar`, e desde 25/09/2026 o Supervisor também a traz, só
    para poder conceder Vendedor e Gerente (`contas/cargos_de_fabrica.py`):
    com a regra antiga ele passaria a ver um bloco de números que nunca terá.
    """
    from plataforma.parametro_catalogo import valor_de

    if atende(usuario) or r.meu is not None:
        return True
    return (pode(usuario, "fila.participar") and pode(usuario, "fila.gerenciar")
            and bool(valor_de("meta_para_gestor")))


def atende(usuario) -> bool:
    """Se `usuario` bate ponto nesta loja — e quem gerencia a loja não atende.

    A fila é de quem está no salão atendendo (18/09/2026, pedido do cliente): o
    supervisor, o gerente e o dono da conta não atendem, e por isso não entram
    na fila. Quem atende é quem tem `fila.participar` e NÃO tem
    `fila.gerenciar` — o que separa as duas coisas é gerenciar.

    **A regra é esta, e não a ausência de `fila.participar` no cargo**, por um
    motivo prático: `contas.lugar.pode_dar` exige que quem aloca tenha as
    permissões do cargo que concede. Um gerente sem `fila.participar` deixaria
    de poder cadastrar Vendedor, e a loja ficaria sem vendedor nenhum — o
    remédio seria pior que a doença.

    Quem já está na loja continua podendo agir (`fila.tela._contexto` soma
    `r.meu` a isto): o gerente que estava atendendo quando esta regra entrou no
    ar precisa fechar o atendimento dele, e não ficar preso na fila.

    A regra em si mora em `fila.quem_atende`, junto com a lista de metas, para
    não haver duas versões dela; aqui só se traduz o usuário da requisição para
    o conjunto de permissões. Nem `None` nem o superusuário (a MW5, que não é
    de conta nenhuma) atendem.
    """
    if usuario is None or usuario.superuser:
        return False
    return quem_atende.atende(usuario.permissions)


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
            .select_related("vendedor", "motivo", "midia").first())


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
    if lugar is None:
        return None
    return Alvo(lugar.pessoa_id, nome_de(lugar.pessoa),
                estado_da_folha(lugar.estado, _em_pausa_fixa(lugar)))


#: O "estado" que as folhas do gerente leem para quem está numa pausa da
#: GESTÃO (25/09/2026). Não é um estado da fila — a pessoa continua
#: `EM_PAUSA` —, é o que decide, no "Corrigir", "Recolocar na fila" no lugar
#: de "Tirar da pausa". O cartão (`data-estado`) e a folha sem script
#: (`Alvo.estado`) dizem o mesmo, e por isso a regra mora aqui.
EM_PAUSA_FIXA = "em_pausa_fixa"


def estado_da_folha(estado: str, pausa_fixa: bool) -> str:
    return EM_PAUSA_FIXA if estado == Estado.EM_PAUSA and pausa_fixa else estado


def _em_pausa_fixa(lugar) -> bool:
    from .models import Pausa

    return (lugar.estado == Estado.EM_PAUSA
            and Pausa.irrestritos.filter(pessoa_id=lugar.pessoa_id,
                                         fim__isnull=True).exclude(fixa="").exists())


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
    plano): os números da loja em que ele está, hoje e no mês, a posição e a
    meta do mês, se houver."""

    hoje: object
    mes: object
    posicao: object
    #: A meta do mês na loja em que a pessoa está, se houver (entrega 3).
    meta: object = None


def _meus_numeros(pessoa, filial) -> "MeusNumeros | None":
    from .indicadores import Recorte, numeros, posicao_no_mes
    from .metas import acompanhar, primeiro_do_mes
    from .models import MetaDeVenda
    from .periodo import periodo_do_pedido

    if pessoa is None:
        return None
    lojas = (filial,)
    mes = numeros(Recorte(filial.empresa, lojas, periodo_do_pedido({"periodo": "mes"})),
                  vendedor=pessoa)
    # A meta da loja em que a pessoa está, como os números ao lado (P-2 do
    # plano dos indicadores). Sem projeção: o vendedor precisa do "quanto por
    # dia", e a projeção é conversa da gestão.
    minha = (MetaDeVenda.objects.da_empresa(filial.empresa)
             .filter(filial=filial, pessoa=pessoa,
                     mes=primeiro_do_mes(timezone.localdate()))
             .first())
    return MeusNumeros(
        hoje=numeros(Recorte(filial.empresa, lojas, periodo_do_pedido({"periodo": "hoje"})),
                     vendedor=pessoa),
        mes=mes,
        posicao=posicao_no_mes(pessoa, filial),
        meta=acompanhar(minha.valor, mes.vendido, minha.mes) if minha else None)


def _contexto(request, filial, recusa=""):
    pessoa = usuario_de(request.usuario)
    empresa = filial.empresa
    # O turno da loja passa por aqui, e não num cron: a página e a consulta de
    # 3 em 3 segundos desenham por este caminho, e o sistema não tem relógio.
    # Ver `fila/turno.py` — é idempotente.
    from .turno import aplicar as aplicar_o_turno

    aplicar_o_turno(filial)
    pode_gerenciar = pode(request.usuario, "fila.gerenciar")
    r = retrato(filial, pessoa)
    editando = _lancamento_em_edicao(request, filial) if pode_gerenciar else None
    # Os cadastros oferecidos são os ativos, e na correção também o grupo e o
    # motivo do PRÓPRIO lançamento, mesmo desativados depois: sem eles a folha
    # abria sem o grupo marcado e a correção de um valor exigia trocar o grupo
    # (revisão final, 15/09/2026). `_validar` já aceita os que o atendimento usa.
    ativos = Q(ativo=True)
    grupos_do_lancamento = motivo_do_lancamento = midia_do_lancamento = Q(pk__in=[])
    if editando is not None:
        grupos_do_lancamento = Q(pk__in=editando.itens.values("grupo_id"))
        motivo_do_lancamento = Q(pk=editando.motivo_id)
        midia_do_lancamento = Q(pk=editando.midia_id)
    lancamentos = list(lancamentos_de_hoje(filial)) if pode_gerenciar else []
    # Quem tem painel na RAIZ vê o link, e não só quem atende. A raiz é o
    # painel da GESTÃO para quem lê indicadores em alguma loja, e o painel do
    # vendedor para quem atende na loja do cabeçalho — a MESMA decisão de
    # `fila.views.inicio`, e é por isso que ela vem de lá, e não de um `if`
    # novo aqui (18/09/2026, pedido do cliente: "dono, supervisor e gerente não
    # tem o meu painel na página da fila").
    from .indicadores import lojas_com_relatorio

    pode_ver_painel = (bool(lojas_com_relatorio(pessoa, empresa))
                       or atende(request.usuario) or r.meu is not None)
    return {
        "r": r,
        "trilha": _trilha(r),
        # As outras lojas da pessoa, para trocar pela própria fila: no celular
        # o cabeçalho do sistema esconde o seletor de filial.
        "outras_lojas": [(loja, trocar_e_abrir_a_fila(loja))
                         for loja in filiais_de(request.usuario, empresa)
                         if loja.pk != filial.pk],
        "meus": (_meus_numeros(pessoa, filial)
                 if _tem_numeros(request.usuario, r) else None),
        "resumo": _resumo(lancamentos),
        "Estado": Estado,
        "filial": filial,
        "nome": nome_de(pessoa) if pessoa else "",
        "eu_id": pessoa.pk if pessoa else None,
        "eu_tem_foto": bool(pessoa) and type(pessoa).objects.filter(
            pk=pessoa.pk, avatar__isnull=False).exists(),
        "agora": timezone.now(),
        # Quem gerencia não atende (`tela.atende`), e por isso vê o retrato da
        # loja em vez do próprio estado na fila. `r.meu` abre a exceção de quem
        # JÁ está na loja: quem estava atendendo quando a regra entrou no ar
        # precisa poder fechar o atendimento.
        "pode_participar": atende(request.usuario) or r.meu is not None,
        "pode_ver_painel": pode_ver_painel,
        "pode_gerenciar": pode_gerenciar,
        "csrf": Markup(campo_csrf(request)),
        "url_fila": reverse("fila"),
        "url_agir": reverse("fila_agir"),
        "url_estado": reverse("fila_estado"),
        "url_sair": reverse("sair"),
        "grupos": list(GrupoDeItem.objects.da_empresa(empresa)
                       .filter(ativos | grupos_do_lancamento)),
        "motivos": list(MotivoDeNaoVenda.objects.da_empresa(empresa)
                        .filter(ativos | motivo_do_lancamento)),
        "tipos": list(TipoDePausa.objects.da_empresa(empresa).filter(ativo=True)),
        # As pausas da GESTÃO (25/09/2026): só a folha do gerente as oferece.
        "pausas_fixas": PausaFixa.choices,
        # Vazia quando a empresa não tem mídia ativa: a folha não desenha o
        # campo, e `acoes._validar_midia` não o cobra (25/09/2026).
        "midias": list(Midia.objects.da_empresa(empresa)
                       .filter(ativos | midia_do_lancamento)),
        "lancamentos": lancamentos,
        "folha": request.GET.get("folha", ""),
        "alvo": _alvo_da_folha(request, filial) if pode_gerenciar else None,
        "editando": editando,
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
            # A máscara antes da fila: a soma do total lê o valor já formatado.
            scripts=["/static/fila/valor.js", "/static/fila/fila.js"])
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
