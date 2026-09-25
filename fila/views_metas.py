"""A tela das metas de venda (spec 2026-09-15-fila-metas, "Cadastro";
refeita em 17/09/2026 pela maquete A aprovada pelo cliente).

Um formulário de campos, e não uma tabela: cada linha é um valor do mesmo
formulário, e uma loja tem dezenas de pessoas, não milhares (a R46 vale para
tabela que lista registros). As regras moram em `fila/metas.py`; aqui só se
monta o contexto do template (`fila/templates/fila/metas.html`) e se lê o POST.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from markupsafe import Markup

from comum.ambiente import ambiente
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao
from comum.guardas_de_modulo import exigir_modulo_ligado
from comum.pedido import id_do_post
from comum.personificacao import aviso as aviso_de_personificacao
from contas.identidade import usuario_de
from nucleo.components import Alert, PageHeader, Raw
from nucleo.layout import Crumb
from nucleo.rendering import use_environment
from nucleo.resposta import render
from plataforma.contexto import empresa_atual

from . import metas as regras
from .acoes import Recusa
from .estado import nome_de
from .valores import em_reais

__all__ = ["metas"]


def _loja_escolhida(request, permitidas):
    """A loja da tela: a do CABEÇALHO, e no POST a que o formulário mostrava.

    Até 25/09/2026 a tela tinha um seletor "Loja" próprio, que abria na
    primeira loja da lista e não conversava com o do cabeçalho — o cliente viu
    as duas lojas escolhidas na mesma tela. Agora a meta é da loja em que a
    sessão está, como a página da fila, e a `?loja=` da URL não escolhe nada.

    O POST continua levando a loja no campo oculto: grava a que a pessoa
    estava VENDO, mesmo que o cabeçalho tenha mudado noutra aba. Nos dois
    casos, só entre as permitidas; fora delas cai na primeira.
    """
    from plataforma.contexto import filial_atual

    if request.method == "POST":
        pk = id_do_post(request, "loja")
    else:
        atual = filial_atual(request)
        pk = atual.pk if atual is not None else None
    return next((l for l in permitidas if l.pk == pk), permitidas[0])


def _endereco(mes) -> str:
    return reverse("fila_metas") + "?" + urlencode({"mes": f"{mes:%Y-%m}"})


def _trocar_e_voltar(loja, mes) -> str:
    """Troca a filial da sessão para `loja` e volta para as metas do mês. É o
    caminho do celular, onde o cabeçalho esconde o seletor de filial; a troca
    pede confirmação (`plataforma.views_filial.filial_trocar`), porque GET não
    muda estado nesta casa."""
    from plataforma.contexto import CHAVE

    return (reverse("filial_trocar") + "?"
            + urlencode({CHAVE: loja.pk, "voltar": _endereco(mes)}))


def _nome_do_mes(mes) -> str:
    """ "Setembro de 2026". A tupla fixa do `nucleo`, e não `strftime("%B")`,
    pelo motivo escrito lá: o nome do mês não pode depender do locale da
    máquina que serve a requisição."""
    from nucleo.views import _MESES

    return f"{_MESES[mes.month - 1].capitalize()} de {mes.year}"


def _curto(nome: str) -> str:
    return nome.split()[0] if nome.strip() else nome


def _andamento(mes, agora) -> tuple:
    """`(estado do mês, frase)`: "atual" com o dia, "encerrado" ou "futuro"."""
    hoje = timezone.localdate(agora)
    if regras.mes_encerrado(mes, agora):
        return "encerrado", _("Mês encerrado")
    if mes > regras.primeiro_do_mes(hoje):
        return "futuro", _("O mês ainda não começou")
    return "atual", (_("Dia %(dia)s de %(total)s") % {
        "dia": hoje.day, "total": regras.ultimo_do_mes(mes).day})


_ESTADOS = {"bateu": gettext_lazy("Bateu"), "no_ritmo": gettext_lazy("No ritmo"),
            "atras": gettext_lazy("Atrás"), "nao_bateu": gettext_lazy("Não bateu")}


def _estado(r) -> str:
    rotulo = _ESTADOS.get(r.estado)
    if rotulo is None:
        return "—"
    return f"{rotulo} · {r.pct:.0f}%".replace(".", ",")


def _regua(linhas, da_loja):
    """A régua de cobertura: cada vendedor com meta é um trecho, e a meta da
    loja é a linha. A escala é a maior das duas pontas, para a linha e os
    trechos caberem na mesma régua."""
    soma = sum((l["valor"] for l in linhas if l["valor"] is not None), regras.ZERO)
    base = max(soma, da_loja or regras.ZERO) or 1
    trechos = [{"pk": l["pk"], "nome": l["nome"], "curto": _curto(l["nome"]),
                "largura": float((l["valor"] or regras.ZERO) * 100 / base)}
               for l in linhas if not l["saiu_sem_meta"]]
    if da_loja is None:
        tom, veredito = "", _("Sem meta da loja neste mês.")
    elif soma < da_loja:
        tom, veredito = "warn", _("Faltam %(valor)s para cobrir a loja") % {
            "valor": em_reais(da_loja - soma)}
    elif soma == da_loja:
        tom, veredito = "ok", _("Cobre exatamente a meta da loja")
    else:
        # Soma ACIMA da meta da loja: é AVISO, e não "cobre com folga"
        # (23/09/2026). A frase antiga era aritmética verdadeira e operação
        # mentirosa — o cliente leu "cobre a loja, com R$ 25.000,00 de folga"
        # como "está tudo certo" e pediu o bloqueio; hoje `gravar` recusa essa
        # gravação (`_conferir_o_teto`), e a tela diz o mesmo que a recusa.
        tom, veredito = "warn", _(
            "As metas dos vendedores somam %(soma)s, acima da meta da loja "
            "(%(loja)s)") % {"soma": em_reais(soma), "loja": em_reais(da_loja)}
    return {"soma": em_reais(soma), "trechos": trechos, "tom": tom, "veredito": veredito,
            "linha_loja": None if da_loja is None else float(da_loja * 100 / base),
            "rotulo_loja": "" if da_loja is None else _("meta da loja %(valor)s") % {
                "valor": em_reais(da_loja)}}


def _desenhar(request, loja, mes, permitidas, editor, *, digitados=None,
              erros=None, aviso=None) -> HttpResponse:
    """A tela refeita em 17/09/2026 (maquete A aprovada pelo cliente): o mês
    como título, a meta da loja com a régua de cobertura, e uma linha por
    vendedor com o vendido e o ritmo. `digitados` são os campos como a pessoa
    deixou (erro ou copiar), e valem sobre o que está salvo."""
    from contas.models import Usuario
    from plataforma.site import montar_site

    from .ambiente import ambiente_da_fila
    from .valores import ler_valor

    agora = timezone.now()
    digitados, erros = digitados or {}, erros or {}
    encerrado = regras.mes_encerrado(mes, agora)
    estado_do_mes, andamento = _andamento(mes, agora)
    anterior = regras.mes_anterior(mes)
    salvas_antes = regras.metas_do_mes(loja, anterior)
    vendido = ({} if estado_do_mes == "futuro" else regras.vendido_no_mes(loja, mes))
    pessoas = regras.pessoas_da_lista(loja, mes, editor)
    com_foto = set(Usuario.objects.filter(pk__in=[l.pessoa.pk for l in pessoas],
                                          avatar__isnull=False).values_list("pk", flat=True))

    def campo(chave, salvo):
        return digitados.get(chave, regras.valor_do_campo(salvo))

    def do_campo(texto):
        valor = ler_valor(texto or "")
        return valor if valor is not None and valor > regras.ZERO else None

    nome_anterior = _nome_do_mes(anterior).split(" de ")[0]
    linhas = []
    for l in pessoas:
        # A própria linha é sempre o valor salvo: ela não vem no POST, e a
        # cópia devolveria o campo vazio por cima da meta que existe.
        texto = (regras.valor_do_campo(l.valor) if l.propria
                 else campo(str(l.pessoa.pk), l.valor))
        valor = l.valor if l.propria else do_campo(texto)
        if l.propria:
            ajuda = _("A sua meta é definida por outra pessoa.")
        elif not l.na_loja:
            ajuda = _("Não está mais nesta loja.")
        elif l.pessoa.pk in salvas_antes:
            ajuda = f"{nome_anterior}: {em_reais(salvas_antes[l.pessoa.pk])}"
        else:
            ajuda = _("Sem meta em %(mes)s") % {"mes": nome_anterior.lower()}
        do_mes = vendido.get(l.pessoa.pk, regras.ZERO)
        r = regras.ritmo(valor, do_mes, mes, agora)
        linhas.append({
            "pk": l.pessoa.pk, "nome": nome_de(l.pessoa), "tem_foto": l.pessoa.pk in com_foto,
            "campo": texto, "valor": valor, "erro": erros.get(str(l.pessoa.pk)),
            "travado": encerrado or l.propria, "ajuda": ajuda,
            # O script da tela distribui a meta da loja entre quem está NA
            # loja (`metas.js`); sem esta marca ele não sabe quem ficou de
            # fora, e daria parte a quem já saiu.
            "na_loja": l.na_loja,
            "saiu_sem_meta": not l.na_loja and valor is None,
            "vendido": do_mes, "vendido_centavos": int(do_mes * 100),
            "ritmo": r, "estado": _estado(r)})

    texto_loja = campo("loja", regras.meta_da_loja(loja, mes))
    da_loja = do_campo(texto_loja)
    total_vendido = sum(vendido.values(), regras.ZERO)
    info_vendido = None
    if estado_do_mes != "futuro":
        info_vendido = (_("Vendido no mês: %(valor)s") % {"valor": em_reais(total_vendido)})
        if da_loja:
            info_vendido += f" ({float(total_vendido * 100 / da_loja):.0f}%)".replace(".", ",")
    info_anterior = (f"{nome_anterior}: {em_reais(salvas_antes[None])}"
                     if None in salvas_antes else None)

    contexto = {
        "loja": loja, "encerrado": encerrado,
        "outras_lojas": [(l, _trocar_e_voltar(l, mes))
                         for l in permitidas if l.pk != loja.pk],
        "mes_titulo": _nome_do_mes(mes), "mes_valor": f"{mes:%Y-%m}",
        "andamento": andamento, "estado_do_mes": estado_do_mes,
        "url_metas": reverse("fila_metas"),
        "url_anterior": _endereco(anterior),
        "url_seguinte": _endereco(regras.mes_seguinte(mes)),
        "url_descartar": _endereco(mes),
        "csrf": Markup(campo_csrf(request)),
        "da_loja": {"campo": texto_loja, "erro": erros.get("loja"),
                    "vendido": info_vendido, "anterior": info_anterior},
        "regua": _regua(linhas, da_loja),
        "linhas": linhas,
        "texto_copiar": _("Copiar metas de %(mes)s") % {"mes": nome_anterior.lower()},
        # As frases que o script recalcula, no idioma de quem abriu a tela:
        # o script troca o número, e não escreve frase.
        "textos": {
            "falta": _("Faltam %(valor)s para cobrir a loja"),
            # A frase da soma acima da loja, para o aviso aparecer ANTES de
            # clicar em salvar (23/09/2026, pedido do cliente): o `metas.js`
            # recalcula o veredito enquanto se digita, e o servidor recusa a
            # gravação com a mesma frase.
            "acima": _("As metas dos vendedores somam %(soma)s, acima da meta "
                       "da loja (%(loja)s)"),
            "exata": _("Cobre exatamente a meta da loja"),
            "sem_loja": _("Sem meta da loja neste mês."),
            "rotulo_loja": _("meta da loja %(valor)s"),
            "uma_mudanca": _("1 meta alterada"),
            "varias_mudancas": _("%(n)s metas alteradas"),
            "bateu": _ESTADOS["bateu"], "no_ritmo": _ESTADOS["no_ritmo"],
            "atras": _ESTADOS["atras"]},
    }

    conteudo = [
        aviso_de_personificacao(request),
        PageHeader(title=_("Metas de venda"),
                   subtitle=_("Quanto cada loja e cada vendedor deve vender no mês.")),
    ]
    if encerrado:
        conteudo.append(Alert(tone="info", message=str(regras.MES_ENCERRADO)))
    if aviso:
        conteudo.append(aviso)
    conteudo.append(Raw(html=ambiente_da_fila().get_template("fila/metas.html").render(**contexto)))

    with use_environment(ambiente()):
        site = montar_site(request)
        pagina = site.page(title=_("Metas de venda"), width="full",
                           stylesheets=["/static/fila/metas.css"],
                           # A máscara antes da tela: o recálculo lê o valor já formatado.
                           scripts=["/static/fila/valor.js", "/static/fila/metas.js"],
                           content=conteudo, crumbs=[Crumb(_("Metas de venda"))],
                           user=request.usuario)
        return render(pagina)


@exigir_permissao("fila.metas")
@exigir_modulo_ligado("fila")
def metas(request) -> HttpResponse:
    editor = usuario_de(request.usuario)
    empresa = empresa_atual(request)
    permitidas = regras.lojas_com_metas(editor, empresa)
    if not permitidas:
        return _desenhar_sem_loja(request)
    loja = _loja_escolhida(request, permitidas)
    dados = request.POST if request.method == "POST" else request.GET
    mes = regras.mes_do_texto(dados.get("mes"))

    if request.method != "POST":
        return _desenhar(request, loja, mes, permitidas, editor,
                         aviso=_aviso_de_outra_loja(request, loja, permitidas))

    linhas = regras.pessoas_da_lista(loja, mes, editor)
    chaves = ["loja", *(str(l.pessoa.pk) for l in linhas)]
    campos = {"loja": "valor_loja", **{str(l.pessoa.pk): f"valor_{l.pessoa.pk}"
                                       for l in linhas}}
    valores = {c: request.POST.get(campos[c]) for c in chaves}
    if request.POST.get("acao") == "copiar":
        copia = regras.copiar_do_anterior(loja, mes, linhas)
        aviso = Alert(tone="info", message=(
            _("Metas do mês anterior copiadas nos campos vazios. Confira e salve.")
            if copia else _("O mês anterior não tem meta para copiar.")))
        return _desenhar(request, loja, mes, permitidas, editor,
                         digitados=copia, aviso=aviso)

    try:
        regras.gravar(loja, mes, editor, valores, request=request)
    except Recusa as recusa:
        return _desenhar(request, loja, mes, permitidas, editor,
                         aviso=Alert(tone="danger", message=str(recusa)))
    except regras.ValoresInvalidos as invalidos:
        digitados = {c: v for c, v in valores.items() if v is not None}
        return _desenhar(request, loja, mes, permitidas, editor,
                         digitados=digitados, erros=invalidos.erros,
                         aviso=Alert(tone="danger",
                                     message=_("Corrija os valores marcados. Nada foi salvo.")))
    # A loja gravada é a que a pessoa estava VENDO, e a tela depois do
    # redirecionamento é a do CABEÇALHO: com o cabeçalho trocado noutra aba,
    # a pessoa não via os valores que acabou de digitar e achava que não
    # tinha salvado (revisão de 25/09/2026). O aviso diz onde salvou, uma vez.
    from plataforma.contexto import filial_atual

    atual = filial_atual(request)
    if atual is None or atual.pk != loja.pk:
        request.session[_SALVO_EM_OUTRA] = loja.pk
    return HttpResponseRedirect(_endereco(mes))


#: A loja salva quando ela não era a do cabeçalho, lida uma vez pelo GET.
_SALVO_EM_OUTRA = "metas_salvas_em_outra_loja"


def _aviso_de_outra_loja(request, loja, permitidas):
    salva = request.session.pop(_SALVO_EM_OUTRA, None)
    outra = next((l for l in permitidas if l.pk == salva), None)
    if outra is None or outra.pk == loja.pk:
        return None
    return Alert(tone="info", message=_(
        "As metas de %(salva)s foram salvas. Esta tela mostra %(loja)s, a "
        "loja do cabeçalho.") % {"salva": outra, "loja": loja})


def _desenhar_sem_loja(request) -> HttpResponse:
    from plataforma.site import montar_site

    with use_environment(ambiente()):
        site = montar_site(request)
        pagina = site.page(title=_("Metas de venda"), width="full", content=[
            aviso_de_personificacao(request),
            PageHeader(title=_("Metas de venda")),
            Alert(tone="info", message=_("Nenhuma loja em que você define metas.")),
        ], crumbs=[Crumb(_("Metas de venda"))], user=request.usuario)
        return render(pagina)
