"""Quem está do outro lado da API, e em que moldura.

Tudo aqui vem das funções que a web já usa para desenhar o cabeçalho e o menu
— `plataforma.contexto`, `plataforma.menu.montar`, `contas.lugar` (por dentro
de `usuario_da_sessao`). O app monta a moldura a partir disto, e por isso não
reimplementa a regra de quem vê o quê.
"""

from __future__ import annotations

from django.conf import settings

from comum.personificacao import original_de, personificando
from comum.sessao import CHAVE_SENHA_EXPIRADA, identidade_da_sessao

from .identidade import usuario_de

__all__ = ["retrato"]


def _pessoa(linha):
    if linha is None:
        return None
    from .models import Usuario

    # Pergunta ao banco se há foto, sem trazer os bytes: o `/eu` roda a cada
    # volta do app, e a foto só é baixada por `GET /api/v1/eu/avatar` — que o
    # app nem chama quando a resposta aqui é "não".
    tem_foto = Usuario.objects.filter(pk=linha.pk, avatar__isnull=False).exists()
    return {"guid": str(linha.guid), "nome": linha.nome, "email": linha.email, "tem_foto": tem_foto}


def _lugar(linha):
    if linha is None:
        return None
    return {"guid": str(linha.guid), "nome": str(linha)}


def _item(item):
    return {"rotulo": str(item.label), "icone": item.icon, "rota": item.href,
            "filhos": [_item(filho) for filho in item.children]}


def retrato(request) -> dict:
    """`request.usuario` já é o de `usuario_da_sessao` (com as permissões do
    lugar), posto pela guarda."""
    from plataforma.contexto import empresa_atual, filial_atual, filiais_de
    from plataforma.marca import (
        CAMINHO_DO_LOGO_DA_EMPRESA, TOKENS_DO_MENU, aparencia_da_requisicao,
        marca_da_requisicao,
    )
    from plataforma.menu import montar

    usuario = request.usuario
    empresa = empresa_atual(request)

    de_verdade = None
    if personificando(request):
        original = original_de(request)
        # O original pode ter deixado de ser superusuário: aí
        # `identidade_da_sessao` já caiu de volta para ele, e não há "de
        # verdade" diferente de quem se vê.
        if original is not None and str(original.id) != str(usuario.id):
            de_verdade = _pessoa(usuario_de(original))

    # Da requisição (15/09/2026): a gaveta veste o menu da empresa de quem é
    # visto, como a barra da web.
    marca = marca_da_requisicao(request)
    aparencia = aparencia_da_requisicao(request)
    cores_do_menu = None
    if aparencia is not None and (aparencia.sidebar_bg or aparencia.sidebar_text):
        tokens = marca.tokens("light")
        cores_do_menu = {nome: tokens[nome] for nome in TOKENS_DO_MENU}
    logo_lateral = marca.assets.sidebar_logo
    if logo_lateral == CAMINHO_DO_LOGO_DA_EMPRESA:
        # O app não manda cookie, e a rota da web lê a sessão dele: o mesmo
        # logo sai pela API, com o token.
        logo_lateral = "/api/v1/eu/logo-do-menu"
    filiais = filiais_de(identidade_da_sessao(request), empresa) if empresa else []
    return {
        "pessoa": _pessoa(usuario_de(usuario)),
        "de_verdade": de_verdade,
        "superusuario": bool(usuario.superuser),
        "empresa": _lugar(empresa),
        "filial": _lugar(filial_atual(request)),
        "filiais": [_lugar(filial) for filial in filiais],
        "permissoes": sorted(usuario.permissions),
        "menu": [_item(item) for item in montar(usuario)],
        "marca": {
            "nome_do_cliente": marca.client_name,
            "nome_do_sistema": marca.system_name,
            "primaria": marca.primary,
            "destaque": marca.accent,
            "tema": marca.default_theme,
            # O logo da faixa branca no topo da barra lateral — o da gaveta do app.
            "logo_lateral": logo_lateral,
            "cores_do_menu": cores_do_menu,
        },
        "idioma": getattr(request, "idioma", settings.LANGUAGE_CODE),
        "senha_expirada": bool(request.session.get(CHAVE_SENHA_EXPIRADA)),
    }
