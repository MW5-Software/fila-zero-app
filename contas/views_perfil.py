"""Meu Perfil: a tela onde qualquer pessoa logada troca a própria senha e a
própria foto.

A seção de foto (`PerfilPage`) já vem desenhada pelo componente portado; esta
tela implementa as duas ações que o formulário dispara — `perfil_senha` e
`perfil_foto` —, e a rota `avatar` que serve os bytes de volta.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.urls import reverse
from django.utils import timezone
from markupsafe import Markup

from django.conf import settings
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _

from comum.idioma import idioma_da_requisicao
from nucleo.components import Card, Raw
from nucleo.images import CABECALHOS_SEGUROS, ImagemInvalida, validar
from nucleo.layout import Crumb, PerfilPage
from nucleo.permissoes import SENHA_MINIMA
from comum.ambiente import ambiente
from nucleo.rendering import use_environment
from nucleo.resposta import render

from comum.auditoria import ACOES, registrar
from comum.csrf import campo_csrf
from comum.guardas_de_acesso import exigir_login
from .models import Usuario
from comum.personificacao import aviso as aviso_de_personificacao

__all__ = ["avatar", "perfil", "perfil_foto", "perfil_senha"]

#: As frases fixas de sucesso. Vêm só da PRESENÇA do parâmetro na URL do
#: redirect — nunca do valor dele, que pode ser qualquer coisa que alguém
#: colar na barra de endereço. Ecoar o valor seria abrir um XSS refletido de
#: graça; a tela sempre mostra a frase fixa correspondente, ou nenhuma.
MENSAGEM_SENHA_TROCADA = "Senha alterada com sucesso."
MENSAGEM_FOTO_SALVA = "Foto salva com sucesso."
#: A frase quando o login caiu aqui porque a senha venceu (Bloco 7).
MENSAGEM_SENHA_EXPIRADA = "Sua senha expirou. Defina uma nova para continuar."

#: 1 MB, e não os 2 MB que `nucleo.images.validar` aceita por padrão. O
#: recorte chega em base64 (`request.POST["recorte"]`), que infla o corpo em
#: ~33%; o `DATA_UPLOAD_MAX_MEMORY_SIZE` padrão do Django é 2,5 MB, então uma
#: imagem de 2 MB viraria um corpo de ~2,7 MB e o Django derrubaria a
#: requisição com `RequestDataTooBig` — um 500 — antes mesmo do nosso
#: validador rodar e a pessoa ver a frase certa com o limite nela.
LIMITE_AVATAR = 1024 * 1024

#: Só raster: SVG é XML que pode carregar script, e o avatar é desenhado num
#: `<img>` no cabeçalho de toda página.
TIPOS_ACEITOS_NO_AVATAR = ("image/png", "image/jpeg", "image/gif", "image/webp")


@dataclass
class _PerfilComCsrf(PerfilPage):
    """`PerfilPage` com o token CSRF embutido nos campos de senha.

    Ao contrário da `LoginPage`, que expõe `fields` para a view prepender,
    `nucleo/templates/layout/perfil.html` não tem slot nenhum para o token —
    o formulário de senha é montado inteiro por `campos_da_senha()`. O
    caminho é chamar a implementação do pai (reusar o design, não recriá-lo) e
    só acrescentar o campo oculto na frente do que ela devolve.

    Recebe o HTML já pronto (`token_html`), e não a `HttpRequest`: esta é uma
    dataclass de renderização, e carregar um objeto do Django dentro dela
    vazaria a camada web para dentro do design system.
    """

    token_html: str = ""

    def campos_da_senha(self) -> list:
        campos = super().campos_da_senha()
        if not campos:
            # Sem `troca_de_senha`, o pai devolve lista vazia e não existe
            # `<form>` nenhum no HTML para este token entrar.
            return campos
        return [Raw(html=self.token_html), *campos]

    def template_context(self) -> dict:
        # O formulário da foto, ao contrário do de senha, não é montado por
        # este componente — ele já vem inteiro em `perfil.html`, que não tem
        # `{% csrf_token %}` nenhum. `token_foto` é a única variável nova que
        # o template porta pede (ver o `default("")` lá: sem ele, o
        # `PerfilPage` puro que `tests/test_components.py` renderiza direto,
        # sem passar por esta subclasse, quebraria contra o `StrictUndefined`
        # do ambiente).
        return {**super().template_context(), "token_foto": Markup(self.token_html)}


def _cartao_de_idioma(request):
    """O seletor de idioma da MOLDURA, aqui e não numa tela própria.

    É preferência de conta, do mesmo naipe da senha e da foto — e uma tela
    inteira para dois botões seria uma linha a mais no menu para uma escolha
    que se faz uma vez na vida.

    **Diz o que NÃO muda**, e isso não é excesso de zelo: a primeira
    pergunta de quem escolhe "Español" e continua vendo o cadastro em
    português é se o sistema quebrou. O dado é do cliente, cadastrado numa
    língua só.
    """
    atual = idioma_da_requisicao(request)
    opcoes = format_html_join("", (
        '<button class="btn {}" type="submit" name="idioma" value="{}">'
        "{}</button>"
    ), (("pri" if chave == atual else "", chave, rotulo)
        for chave, rotulo in settings.LANGUAGES))

    return Card(title=_("Idioma"), body=[Raw(html=Markup(format_html(
        '<p class="perfil-idioma-nota">{}</p>'
        '<form method="post" action="{}">{}'
        '<input type="hidden" name="voltar" value="{}">'
        '<div class="perfil-idioma">{}</div></form>',
        _("Vale para as telas do sistema. O que foi cadastrado aparece no "
          "idioma em que foi cadastrado."),
        reverse("idioma"), Markup(campo_csrf(request)),
        reverse("perfil"), opcoes)))])


def _desenhar(request, erro: "str | None" = None, ok: "str | None" = None) -> HttpResponse:
    from plataforma.site import montar_site

    env = ambiente()
    with use_environment(env):
        site = montar_site(request)
        # Os rótulos vão daqui, traduzidos, em vez de valerem os padrões do
        # componente: o `nucleo` é porte verbatim e não se emenda (CLAUDE.md
        # §2) — mas ele foi feito com esses textos como PARÂMETRO, e essa é a
        # porta que ele deixou aberta para quem precisa de outra língua.
        conteudo = _PerfilComCsrf(
            user=request.usuario, troca_de_senha=True,
            titulo=_("Meu Perfil"),
            rotulo_foto=_("Foto"),
            rotulo_senha=_("Senha"),
            token_html=campo_csrf(request),
            erro=erro or "", ok=ok or "",
        )
        pagina = site.page(
            # `full`: a tela usa a largura toda. Estas telas são tabela e
            # formulário — espremer uma tabela em 1400px num monitor largo
            # desperdiça a metade direita e ainda quebra coluna.
            title=_("Meu Perfil"),
            width="full",
            # O recorte da foto é feito no navegador (`mw5-recorte.js` em cima
            # do Cropper), e o formulário só manda o resultado. Sem estes três
            # arquivos, escolher a foto não gerava recorte nenhum, o campo ia
            # vazio e a foto nunca salvava — desde a cópia do KRONOS.net até
            # 15/09/2026. O Cropper vem antes: o recorte usa `window.Cropper`.
            stylesheets=["/static/nucleo/cropper.min.css"],
            scripts=["/static/nucleo/cropper.min.js",
                     "/static/nucleo/mw5-recorte.js"],
            content=[aviso_de_personificacao(request), conteudo,
                     _cartao_de_idioma(request)],
            crumbs=[Crumb(_("Meu Perfil"))],
            user=request.usuario,
        )
        # A renderização precisa acontecer AQUI dentro do `with` — ver o
        # comentário equivalente em `plataforma/views.py::_desenhar`. Fora
        # dele, cai no ambiente global e ignora em silêncio qualquer loader
        # extra do cliente.
        return render(pagina)


@exigir_login
def perfil(request) -> HttpResponse:
    """A tela Meu Perfil, aberta para qualquer pessoa que entrou.

    `?ok=` e `?foto=` na URL são só sinalizadores — a tela lê a PRESENÇA da
    chave, nunca o valor, e mostra sempre a frase fixa correspondente. São
    dois formulários independentes (senha e foto), então cada um precisa do
    seu próprio sinalizador — um só `?ok=` valeria para os dois e diria a
    coisa errada quando só um deles tivesse acabado de ser salvo.
    """
    if "expirada" in request.GET:
        return _desenhar(request, erro=MENSAGEM_SENHA_EXPIRADA)
    if "foto" in request.GET:
        ok = MENSAGEM_FOTO_SALVA
    elif "ok" in request.GET:
        ok = MENSAGEM_SENHA_TROCADA
    else:
        ok = None
    return _desenhar(request, ok=ok)


@exigir_login
def perfil_senha(request) -> HttpResponse:
    """Só por POST — mesmo motivo de `contas.views.sair`: um link qualquer
    não pode disparar a troca da senha de quem o abriu."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    atual = request.POST.get("senha_atual", "")
    nova = request.POST.get("senha_nova", "")
    confirma = request.POST.get("senha_confirma", "")

    # Vai direto no model do Django para chamar `check_password`/
    # `set_password`: `nucleo.permissoes.User` é só o retrato read-only que a
    # tela desenha, não guarda senha nenhuma.
    usuario = Usuario.objects.get(pk=int(request.usuario.id))

    if not usuario.check_password(atual):
        return _desenhar(request, erro=_("A senha atual não confere."))
    if len(nova) < SENHA_MINIMA:
        return _desenhar(
            request,
            erro=f"A senha nova precisa de pelo menos {SENHA_MINIMA} caracteres.",
        )
    if nova != confirma:
        return _desenhar(request, erro=_("A confirmação não bate com a senha nova."))

    with transaction.atomic():
        usuario.set_password(nova)
        # A contagem de expiração recomeça agora (Bloco 7), e a sessão desta
        # pessoa deixa de estar presa na troca.
        usuario.senha_definida_em = timezone.now()
        usuario.save(update_fields=["password", "senha_definida_em"])
        request.session.pop("senha_expirada", None)
        registrar(ACOES.SENHA_TROCADA, usuario, alvo=usuario.email, request=request)
    # A sessão deste projeto (`contas/sessao.py`, chave `usuario_id`) é
    # independente da de `django.contrib.auth` — nunca foi ela quem colocou a
    # pessoa aqui, então trocar a senha não a invalida. Continuar dentro é o
    # comportamento natural, não algo que precise ser forçado de volta (ver
    # `tests/test_meu_perfil.py::TestTrocarASenha::test_troca_e_continua_dentro`).
    #
    # Redireciona (não desenha aqui): redirect-after-POST é o que impede um
    # F5 na resposta de reenviar o POST da troca de senha — que agora falharia
    # com "a senha atual não confere" logo depois de um sucesso, uma
    # confusão pior que a tela silenciosa que este item resolve. `?ok=1` é só
    # o sinalizador que `perfil` lê para mostrar a frase fixa de confirmação.
    return HttpResponseRedirect(reverse("perfil") + "?ok=1")


def _bytes_da_url_de_dados(url: str) -> bytes:
    """O payload de uma data URL (`data:<tipo>;base64,<payload>`), decodificado.

    A parte antes da vírgula é o que o CLIENTE afirma sobre o conteúdo — e
    descartada aqui de propósito: quem decide o tipo de verdade é
    `nucleo.images.validar`, lendo os bytes já decodificados, não o rótulo que
    veio junto.

    Base64 malformado levanta `ImagemInvalida` com frase própria, em vez de
    devolver corpo vazio: virar `b""` cairia no "o arquivo está vazio" que
    `validar` já sabe dizer, e isso seria mentira — o arquivo não estava
    vazio, estava corrompido. A frase errada manda a pessoa procurar o
    arquivo sumido em vez do problema real (o recorte que não terminou de
    chegar). O `except ImagemInvalida` de `perfil_foto` já cobre este caminho
    junto do de `validar`, sem precisar de um segundo `try` na view.
    """
    _resto, _resto, payload = url.partition(",")
    try:
        return base64.b64decode(payload)
    except binascii.Error:
        raise ImagemInvalida("Não foi possível ler o arquivo enviado.") from None


@exigir_login
def perfil_foto(request) -> HttpResponse:
    """Só por POST — mesmo motivo de `perfil_senha`.

    O corpo não é um arquivo multipart: `mw5-recorte.js` grava o recorte já
    pronto (`canvas.toDataURL`) numa data URL dentro do campo oculto
    `recorte`. O que chega aqui é uma STRING como qualquer outro dado de
    entrada — o tipo declarado dentro dela é afirmação de quem enviou, não
    verificação.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        bruto = _bytes_da_url_de_dados(request.POST.get("recorte", ""))
        imagem = validar(bruto, tamanho_maximo=LIMITE_AVATAR,
                          aceitos=TIPOS_ACEITOS_NO_AVATAR)
    except ImagemInvalida as erro:
        return _desenhar(request, erro=str(erro))

    usuario = Usuario.objects.get(pk=int(request.usuario.id))
    with transaction.atomic():
        # Duas colunas do MESMO usuário, não mais uma linha à parte: gravar
        # por cima já É o "reenviar substitui" — não existe segunda linha
        # para duplicar.
        usuario.avatar = imagem.data
        usuario.avatar_tipo = imagem.media_type
        usuario.save(update_fields=["avatar", "avatar_tipo"])
        registrar(ACOES.FOTO_ALTERADA, usuario, alvo=usuario.email, request=request)
    # Mesmo padrão de `perfil_senha`: redirect-after-POST, com um
    # sinalizador próprio (`?foto=`) para a frase fixa desta ação.
    return HttpResponseRedirect(reverse("perfil") + "?foto=1")


@exigir_login
def avatar(request, usuario_id: int) -> HttpResponse:
    """Os bytes da foto de alguém, com o tipo que `validar` decidiu na hora do
    envio — nunca um que o cliente tenha afirmado depois.

    Atrás de `exigir_login` como qualquer outra tela: a foto de alguém não é
    dado público só porque a URL é previsível (`/avatar/<id>`).
    """
    # `avatar__isnull=False` no filtro, e não um `if not gravado.avatar` de
    # depois: filtra no banco quem TEM foto numa consulta só, em vez de trazer
    # a linha de quem não tem para descartar aqui.
    # **Só a foto de alguém da mesma conta** (ou a própria, ou qualquer uma
    # para a MW5). A rota só exigia login, e quem entrasse em qualquer conta
    # baixava as fotos das outras percorrendo os ids — que a fila do Fila Zero
    # publica no HTML (revisão final, 15/09/2026). Fora da conta é o mesmo
    # 404 de quem não tem foto: a resposta não diz se a pessoa existe.
    eu = Usuario.objects.filter(pk=int(request.usuario.id)).values(
        "pk", "conta_id", "is_superuser").first()
    alcance = Q(pk=usuario_id, avatar__isnull=False)
    if eu is None:
        return HttpResponseNotFound()
    if not eu["is_superuser"]:
        mesma_conta = Q(conta_id=eu["conta_id"]) if eu["conta_id"] else Q(pk__in=[])
        alcance &= Q(pk=eu["pk"]) | mesma_conta
    try:
        gravado = Usuario.objects.get(alcance)
    except Usuario.DoesNotExist:
        return HttpResponseNotFound()

    resposta = HttpResponse(bytes(gravado.avatar), content_type=gravado.avatar_tipo)
    # Bytes enviados por outra pessoa, servidos pela nossa origem: os mesmos
    # cabeçalhos que protegem o logo em `nucleo.images` valem aqui — `nosniff`
    # e a CSP com `sandbox` são a segunda tranca, para o caso de algo passar
    # da primeira.
    for chave, valor in CABECALHOS_SEGUROS.items():
        resposta[chave] = valor
    return resposta
