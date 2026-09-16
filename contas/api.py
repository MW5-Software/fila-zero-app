"""A API de `contas`: entrar, sair, quem sou. Casca fina sobre
`contas.entrada` e `contas.eu`."""

# Sem `from __future__ import annotations`, de propósito. Com ele, toda
# anotação vira texto, e o Ninja resolve o texto pelos `__globals__` da função
# da operação — que, embrulhada por uma guarda (`comum.guardas_da_api`), são
# os globais do módulo da GUARDA, onde o schema não existe. O corpo passava a
# ser lido como query string, e a operação respondia 500.

from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from ninja import Router, Schema

from comum.guardas_da_api import api_exigir_login
from comum.respostas_da_api import erro, nao_existe
from comum.sessao import CHAVE_SENHA_EXPIRADA

from .entrada import CREDENCIAIS_INVALIDAS, autenticar_e_entrar, sair_e_registrar
from .eu import retrato
from .idioma import guardar_escolha

__all__ = ["router"]

router = Router(tags=["sessão"])


class Credenciais(Schema):
    email: str
    senha: str


class Token(Schema):
    token: str
    senha_expirada: bool


class Pessoa(Schema):
    guid: str
    nome: str
    email: str
    tem_foto: bool


class Lugar(Schema):
    guid: str
    nome: str


class ItemDeMenu(Schema):
    rotulo: str
    icone: str
    rota: str
    filhos: list["ItemDeMenu"] = []


ItemDeMenu.model_rebuild()


class Marca(Schema):
    nome_do_cliente: str
    nome_do_sistema: str | None
    primaria: str
    destaque: str
    tema: str
    logo_lateral: str | None
    #: As cores do menu da EMPRESA de quem é visto, com os nomes dos tokens do
    #: tema (`sidebar-bg`…), ou `None` para a gaveta seguir o tema. Hover e
    #: selecionado já vêm calculados pelo mesmo tema da web.
    cores_do_menu: dict[str, str] | None


class Eu(Schema):
    pessoa: Pessoa
    de_verdade: Pessoa | None
    superusuario: bool
    empresa: Lugar | None
    filial: Lugar | None
    filiais: list[Lugar]
    permissoes: list[str]
    menu: list[ItemDeMenu]
    marca: Marca
    idioma: str
    senha_expirada: bool


@router.post("/sessao", response=Token, url_name="entrar")
def entrar(request, credenciais: Credenciais):
    """O token é a chave da sessão Django, já girada pelo login."""
    user = autenticar_e_entrar(request, credenciais.email, credenciais.senha)
    if user is None:
        return erro(401, "credenciais_invalidas", CREDENCIAIS_INVALIDAS)
    return {"token": request.session.session_key,
            "senha_expirada": bool(request.session.get(CHAVE_SENHA_EXPIRADA))}


@router.delete("/sessao", url_name="sair")
def sair(request):
    sair_e_registrar(request)
    return HttpResponse(status=204)


@router.get("/eu", response=Eu, url_name="eu")
@api_exigir_login
def eu(request):
    return retrato(request)


@router.get("/eu/avatar", url_name="meu_avatar")
@api_exigir_login
def meu_avatar(request):
    """A foto de quem se está vendo — personificando, a do alvo, como o avatar
    do cabeçalho da web. Sem foto, o 404 de sempre, e o app desenha as iniciais.

    Os bytes vão com os cabeçalhos seguros da web (`nosniff` e a CSP com
    `sandbox`): é arquivo enviado por outra pessoa, servido pela nossa origem —
    o mesmo motivo de `contas.views_perfil.avatar`.
    """
    from nucleo.images import CABECALHOS_SEGUROS

    from .identidade import usuario_de
    from .models import Usuario

    pessoa = usuario_de(request.usuario)
    gravado = None
    if pessoa is not None:
        gravado = Usuario.objects.filter(pk=pessoa.pk, avatar__isnull=False).only("avatar", "avatar_tipo").first()
    if gravado is None:
        return nao_existe()
    resposta = HttpResponse(bytes(gravado.avatar), content_type=gravado.avatar_tipo)
    for chave, valor in CABECALHOS_SEGUROS.items():
        resposta[chave] = valor
    return resposta


@router.get("/eu/logo-do-menu", url_name="logo_do_menu")
@api_exigir_login
def logo_do_menu(request):
    """O logo do menu da empresa de quem se está vendo — o da gaveta do app.

    Pela API, e não pela rota da web, porque o app não manda cookie. Sem nada
    na URL que diga a empresa: quem decide é o token, pela mesma regra da web
    (`plataforma.marca.logo_da_empresa_de`). Sem logo, o 404 de sempre, e o
    `/api/v1/eu` nem aponta para cá.
    """
    from nucleo.images import CABECALHOS_SEGUROS
    from plataforma.marca import logo_da_empresa_de

    achado = logo_da_empresa_de(request)
    if achado is None:
        return nao_existe()
    conteudo, tipo = achado
    resposta = HttpResponse(conteudo, content_type=tipo)
    for chave, valor in CABECALHOS_SEGUROS.items():
        resposta[chave] = valor
    return resposta


class TrocaDeIdioma(Schema):
    codigo: str


class IdiomaGravado(Schema):
    idioma: str


@router.post("/eu/idioma", response=IdiomaGravado, url_name="meu_idioma")
@api_exigir_login
def meu_idioma(request, troca: TrocaDeIdioma):
    """O seletor de idioma do cabeçalho do app: grava na conta, como o da web
    (`contas.idioma.guardar_escolha`), para a escolha valer também na web e na
    próxima abertura."""
    if not guardar_escolha(request, troca.codigo):
        return erro(422, "validacao", _("Idioma desconhecido."),
                    {"codigo": [_("Escolha um dos idiomas da instalação.")]})
    return {"idioma": troca.codigo}
