"""A API de `plataforma`: a versão, a filial do contexto e a lista de filiais.
Casca fina — a regra mora em `contexto.py`, `filiais.py` e `comum.listagem`
(ver `tests/test_api_nao_importa_view.py`)."""

# Sem `from __future__ import annotations`, de propósito. Com ele, toda
# anotação vira texto, e o Ninja resolve o texto pelos `__globals__` da função
# da operação — que, embrulhada por uma guarda (`comum.guardas_da_api`), são
# os globais do módulo da GUARDA, onde o schema não existe. O corpo passava a
# ser lido como query string, e a operação respondia 500.

from django.conf import settings
from ninja import Router, Schema

from comum.auditoria import ACOES, registrar
from comum.esquemas_da_api import Pagina
from comum.guardas_da_api import (
    api_exigir_login, api_exigir_modulo_ligado, api_exigir_permissao,
)
from comum.listagem import listar_para_api
from comum.respostas_da_api import nao_existe

from .contexto import escolher, filial_permitida_por_guid
from .filiais import FILTRAVEIS, ORDENAVEIS, ROTULOS, filiais_da_empresa

__all__ = ["router", "router_aberto"]

#: Fora do `v1/`: é quem diz qual versão usar.
router_aberto = Router(tags=["versão"])

router = Router(tags=["filiais"])


class Versao(Schema):
    api: list[int]
    app_minimo: str


@router_aberto.get("/versao", response=Versao, url_name="versao")
def versao(request):
    """As versões de API que existem e o app mínimo que ainda funciona.

    Aberta: é a pergunta que o app faz antes de qualquer outra, inclusive
    antes de ter como entrar, e não diz nada que a loja de aplicativos já não
    diga.
    """
    return {"api": [1], "app_minimo": settings.APP_MINIMO}


class Tema(Schema):
    padrao: str
    claro: dict[str, str]
    escuro: dict[str, str]


@router_aberto.get("/tema", response=Tema, url_name="tema")
def tema(request):
    """Os tokens da marca nos dois modos — os mesmos que o `/tema.css` entrega.

    Aberta pelo motivo de `tema` em `TELAS_ABERTAS`: a tela de entrada do app
    precisa se vestir antes de haver sessão, e nada aqui é mais do que a tela
    de entrada da web já mostra.
    """
    from .marca import AJUSTES_DA_FOLHA_DA_CASA, marca_da_instalacao

    marca = marca_da_instalacao()
    # Com os ajustes da `kronos.css` por cima: é o que a web desenha de fato, e
    # sem eles o logo do app saía menor que o da web.
    return {"padrao": marca.default_theme,
            "claro": {**marca.tokens("light"), **AJUSTES_DA_FOLHA_DA_CASA},
            "escuro": {**marca.tokens("dark"), **AJUSTES_DA_FOLHA_DA_CASA}}

class Idioma(Schema):
    codigo: str
    nome: str


class Entrada(Schema):
    logo: str | None
    titulo: str
    subtitulo: str | None
    frase: str | None
    rotulo_email: str
    dica_email: str
    rotulo_senha: str
    dica_senha: str
    mostrar_manter: bool
    rotulo_manter: str
    mostrar_esqueceu: bool
    rotulo_esqueceu: str
    endereco_esqueceu: str
    rotulo_botao: str
    texto_suporte: str
    rotulo_suporte: str
    endereco_suporte: str
    idiomas: list[Idioma]


@router_aberto.get("/entrada", response=Entrada, url_name="entrada")
def entrada(request):
    """A tela de entrada da web, em dados: a marca que o cliente edita na
    Aparência, com as frases que ele não trocou já no idioma de quem pede
    (`Accept-Language`, pela mesma `traduzir_a_entrada` da web).

    Aberta pelo mesmo motivo de `entrar` em `TELAS_ABERTAS`: é a porta, e não
    diz nada que a tela de entrada da web não mostre a qualquer um. Os
    endereços não passam pelo tradutor — traduzido, o link levaria a uma página
    que não existe. Os campos extras do `LoginBrand` ainda não vão: o app não
    os desenha.
    """
    from django.conf import settings as configuracao

    from . import marca as modulo_da_marca
    from .entrada import traduzir_a_entrada

    marca = modulo_da_marca.marca_da_instalacao()
    login = traduzir_a_entrada(marca.login)
    return {
        "logo": marca.assets.login_logo,
        "titulo": login.title,
        "subtitulo": login.subtitle,
        "frase": login.tagline,
        "rotulo_email": login.identifier_label,
        "dica_email": login.identifier_placeholder,
        "rotulo_senha": login.password_label,
        "dica_senha": login.password_placeholder,
        "mostrar_manter": login.show_remember,
        "rotulo_manter": login.remember_label,
        "mostrar_esqueceu": login.show_forgot,
        "rotulo_esqueceu": login.forgot_label,
        "endereco_esqueceu": login.forgot_url,
        "rotulo_botao": login.submit_label,
        "texto_suporte": login.support_text,
        "rotulo_suporte": login.support_label,
        "endereco_suporte": login.support_url,
        "idiomas": [{"codigo": codigo, "nome": str(nome)} for codigo, nome in configuracao.LANGUAGES],
    }

class TrocaDeFilial(Schema):
    guid: str


class FilialEscolhida(Schema):
    guid: str
    nome: str


@router.post("/filial", response=FilialEscolhida, url_name="trocar_filial")
@api_exigir_login
def trocar_filial(request, troca: TrocaDeFilial):
    """O mesmo caminho de `views_filial.filial_trocar`: só uma filial que a
    pessoa alcança dentro da empresa atual, e a troca na trilha."""
    filial = filial_permitida_por_guid(request, troca.guid)
    if filial is None:
        return nao_existe()
    escolher(request, filial.pk)
    registrar(ACOES.FILIAL_TROCADA, request.usuario, alvo=str(filial), request=request)
    return {"guid": str(filial.guid), "nome": str(filial)}


class FilialDaLista(Schema):
    guid: str
    nome: str
    apelido: str
    cnpj: str
    municipio: str
    uf: str
    ativa: bool
    e_matriz: bool


class PaginaDeFiliais(Pagina):
    itens: list[FilialDaLista]


def _filial(filial) -> dict:
    return {"guid": str(filial.guid), "nome": filial.nome, "apelido": filial.apelido,
            "cnpj": filial.cnpj, "municipio": filial.municipio, "uf": filial.uf,
            "ativa": filial.ativa, "e_matriz": filial.e_matriz}


@router.get("/filiais", response=PaginaDeFiliais, url_name="listar_filiais")
@api_exigir_permissao("filiais.editar")
@api_exigir_modulo_ligado("filiais")
def listar_filiais(request):
    return listar_para_api(request, filiais_da_empresa(request),
                           ordenaveis=ORDENAVEIS, padrao="filial",
                           filtraveis=FILTRAVEIS, rotulos=ROTULOS, item=_filial)
