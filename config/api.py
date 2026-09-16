"""A API do app: um `NinjaAPI` só, montado em `/api/`.

Mora em `config/`, e não em `plataforma/`, porque junta os routers de TODAS as
camadas — inclusive os de negócio, a partir do subprojeto 3. A base nunca
importa negócio (`tests/test_camadas_nao_se_invertem.py`); `config` já fica
por cima de todos, como `config/urls.py`.
"""

from __future__ import annotations

from ninja import NinjaAPI

__all__ = ["api", "criar_api"]


def criar_api(*, urls_namespace: str = "api", routers=()) -> NinjaAPI:
    """Uma `NinjaAPI` com a configuração da casa.

    Função, e não só a instância lá embaixo, porque os testes de erro montam
    uma API própria com rotas que explodem de propósito
    (`tests/api_de_teste.py`) — e ela precisa sair com as MESMAS regras da de
    verdade, ou o teste prova outra coisa.

    `docs_url` e `openapi_url` desligados: a web responde 404 para não
    revelar a tela que a pessoa não pode, e um `/api/docs` aberto entregaria o
    mapa inteiro. O esquema sai por `python -m config.openapi`.
    """
    api = NinjaAPI(title="KRONOS base", version="1",
                   urls_namespace=urls_namespace,
                   docs_url=None, openapi_url=None)
    from plataforma.api_tratadores import instalar_tratadores

    instalar_tratadores(api)
    for prefixo, router in routers:
        api.add_router(prefixo, router)
    return api


def _routers():
    # Import DENTRO da função: os módulos das rotas importam models, e no topo
    # deste arquivo eles rodariam antes de o Django carregar os apps. Um SaaS
    # acrescenta aqui o router do negócio dele.
    from contas.api import router as contas
    from plataforma.api import router as plataforma, router_aberto

    return [("", router_aberto), ("v1/", contas), ("v1/", plataforma)]


api = criar_api(routers=_routers())
