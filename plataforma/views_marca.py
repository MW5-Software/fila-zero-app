"""As rotas da marca: servir o logo e o favicon gravados no banco.

A rota de servir é aberta de propósito (ver `TELAS_ABERTAS`): a tela de
entrada e o favicon precisam dela antes de qualquer sessão existir. O que
protege não é guarda de login — é a peneira na gravação
(`ImagemDaMarca.save`, que só aceita o que `nucleo.images.validar` aprova)
mais os cabeçalhos seguros na resposta, os mesmos do avatar.

O upload mora aqui também, atrás da mesma permissão da Aparência
(`mw5.aparencia`): é a mesma decisão — o que muda a cara da instalação é
assunto da MW5.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseNotAllowed
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from nucleo.components import Button, Card, FileInput, Form, Raw
from nucleo.images import CABECALHOS_SEGUROS

from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_permissao

from .models import LUGARES_DA_IMAGEM, ImagemDaMarca

__all__ = ["ROTULOS", "aparencia_logo", "cartao_de_logos", "marca_imagem"]

#: Os lugares abertos ao cliente, com o nome que a tela mostra. É também o `alvo` da
#: auditoria — quem lê o registro seis meses depois encontra "Menu lateral",
#: não um slug.
ROTULOS = {
    "login": "Tela de entrada",
    "sidebar": "Menu lateral",
    "favicon": "Favicon",
}

#: A caixa que cada lugar reserva, dita na tela. Sem isto a pessoa envia o
#: arquivo que tem e descobre o tamanho errado olhando o resultado — e a
#: medida certa não está em lugar nenhum que ela possa consultar.
#:
#: "3× a caixa" é a mesma regra de `ferramentas/gerar_logos.py`: o arquivo na
#: medida exata parece perfeito num monitor comum e sai borrado em tela
#: retina, que é a maioria dos notebooks.
MEDIDAS = {
    "login": "A caixa é de 220×72. Envie em 3× (660×216) para não sair borrado.",
    "sidebar": "A caixa é de 200×84. Envie em 3× (600×252) para não sair borrado.",
    "favicon": "Quadrado, 32×32 ou maior. É o ícone da aba do navegador.",
}

#: O que a tela diz quando o lugar está vazio. Nos dois logos não é "nenhum
#: arquivo": é o logo do KRONOS, e dizer isso evita a pergunta "então está
#: sem logo?". O favicon não tem padrão nenhum — dizer que tem seria mentira,
#: e a pessoa procuraria na aba um ícone que não existe.
SEM_ENVIO = {
    "login": "Sem envio: vale o logo do KRONOS.",
    "sidebar": "Sem envio: vale o logo do KRONOS.",
    "favicon": "Sem envio: a aba fica com o ícone padrão do navegador.",
}

MENSAGEM_LOGO_SALVA = "Imagem da marca salva com sucesso."
MENSAGEM_LOGO_REMOVIDA = "Imagem da marca removida."


def marca_imagem(request, lugar: str) -> HttpResponse:
    """Os bytes gravados para um lugar, com o tipo decidido NA GRAVAÇÃO.

    Um lugar que não existe no catálogo responde 404 antes de consultar o
    banco: não é "imagem que ainda não foi enviada", é caminho que nunca
    deveria ter sido pedido.
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if lugar not in LUGARES_DA_IMAGEM:
        return HttpResponseNotFound()

    try:
        gravado = ImagemDaMarca.objects.get(lugar=lugar)
    except ImagemDaMarca.DoesNotExist:
        return HttpResponseNotFound()

    resposta = HttpResponse(bytes(gravado.conteudo), content_type=gravado.tipo)
    # Bytes enviados por terceiro, servidos pela nossa origem — inclusive
    # para quem nem entrou: `nosniff` e a CSP com sandbox são a segunda
    # tranca, para o caso de algo passar da peneira da gravação.
    for chave, valor in CABECALHOS_SEGUROS.items():
        resposta[chave] = valor
    return resposta


def _campo_oculto(nome: str, valor: str) -> Raw:
    """Um `<input type="hidden">`, pelo mesmo caminho autorizado do
    `campo_csrf`: o design system não tem componente para campo oculto, e
    `Raw` existe exatamente para HTML cru já confiável."""
    return Raw(html=format_html(
        '<input type="hidden" name="{}" value="{}">', nome, valor))


def cartao_de_logos(request) -> Card:
    """O card da Aparência com um formulário por lugar.

    Um formulário por lugar, e não um só para todos: trocar o logo do menu
    não pode exigir reenviar (nem reescolher) os outros — o
    `<input type="file">` volta sempre vazio depois do POST, então um
    formulário único obrigaria a pessoa a procurar de novo todo arquivo que
    NÃO queria mudar.
    """
    gravados = {i.lugar: i for i in ImagemDaMarca.objects.all()}
    linhas = []
    for lugar in LUGARES_DA_IMAGEM:
        imagem = gravados.get(lugar)
        atual_url = f"/marca/imagem/{lugar}" if imagem else ""
        # O rótulo do lugar vira o `label` do campo, e não um `<h3>` solto: o
        # campo passa a se apresentar sozinho, e a ajuda embaixo dele diz a
        # medida — que antes não estava escrita em lugar nenhum da tela.
        linhas.append(Form(
            action=reverse("aparencia_logo"), multipart=True,
            children=[
                Raw(html=campo_csrf(request)),
                _campo_oculto("lugar", lugar),
                FileInput(
                    name="arquivo",
                    label=ROTULOS[lugar],
                    help=MEDIDAS[lugar] if imagem
                         else f"{SEM_ENVIO[lugar]} {MEDIDAS[lugar]}",
                    current_url=atual_url,
                    current_label=ROTULOS[lugar] if imagem else "",
                ),
                Button(label=_("Enviar"), variant="primary", type="submit"),
            ],
        ))
        if imagem:
            linhas.append(Form(
                action=reverse("aparencia_logo"),
                children=[
                    Raw(html=campo_csrf(request)),
                    _campo_oculto("lugar", lugar),
                    _campo_oculto("acao", "remover"),
                    Button(label=_("Remover"), variant="ghost", type="submit"),
                ],
            ))
    return Card(
        title=_("Logos e favicon"),
        # O motivo de estes botões serem separados do "Salvar" de cima, dito
        # na tela: um `<input type="file">` volta sempre vazio depois do POST,
        # então um formulário único obrigaria a reescolher todo arquivo que
        # NÃO se queria trocar.
        subtitle="Cada um envia na hora, separado do Salvar acima. "
                 "O rodapé não entra: ali o logo é do KRONOS e não troca.",
        body=linhas,
    )


@exigir_permissao("mw5.aparencia")
def aparencia_logo(request) -> HttpResponse:
    """Recebe o envio (ou a remoção) de UM lugar, e devolve para a Aparência.

    Redirect-after-POST como em toda ação deste projeto; a frase fixa de
    sucesso viaja como sinalizador na URL (`?logo=1` / `?logorem=1`) — o
    valor nunca é ecoado. Erro de validação redesenha a tela inteira com o
    `Alert` no topo, igual ao caminho da cores.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    lugar = request.POST.get("lugar", "")
    if lugar not in ROTULOS:
        return HttpResponseNotFound()
    alvo = ROTULOS[lugar]

    from .views import _desenhar, _valores_de

    # Nos dois caminhos de erro a tela é redesenhada inteira com os valores
    # QUE ESTÃO VALENDO — e não em branco: apagar o que a pessoa preencheu
    # nas cores porque o logo veio errado seria punição dupla.
    from .models import Marca

    valores = _valores_de(Marca.objects.first())

    if request.POST.get("acao") == "remover":
        try:
            imagem = ImagemDaMarca.objects.get(lugar=lugar)
        except ImagemDaMarca.DoesNotExist:
            return HttpResponseNotFound()
        with transaction.atomic():
            imagem.delete()
            registrar(ACOES.LOGO_REMOVIDO, request.usuario,
                      alvo=alvo, request=request)
        return HttpResponseRedirect(reverse("aparencia") + "?logorem=1")

    arquivo = request.FILES.get("arquivo")
    if arquivo is None:
        return _desenhar(request, valores, erro=_("Escolha um arquivo antes de enviar."))

    # Reenviar SUBSTITUI: a linha do lugar já existente é carregada e tem só
    # o conteúdo trocado — o `lugar` único proíbe a segunda linha, e criar
    # por cima dela seria um `IntegrityError` feio em vez deste caminho
    # normal. A validação (e a decisão do tipo) continua acontecendo dentro
    # do `save()` — a tela não é a única porta.
    try:
        with transaction.atomic():
            try:
                imagem = ImagemDaMarca.objects.get(lugar=lugar)
                imagem.conteudo = arquivo.read()
            except ImagemDaMarca.DoesNotExist:
                imagem = ImagemDaMarca(lugar=lugar, conteudo=arquivo.read())
            imagem.save()
            registrar(ACOES.LOGO_ALTERADO, request.usuario,
                      alvo=alvo, request=request)
    except ValidationError as erro:
        return _desenhar(request, valores, erro="; ".join(erro.messages))
    return HttpResponseRedirect(reverse("aparencia") + "?logo=1")
