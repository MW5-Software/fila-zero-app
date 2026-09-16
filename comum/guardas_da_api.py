"""As guardas da API — a mesma decisão das guardas da web, respondida em JSON.

Quem decide é `comum.guardas_de_acesso.barreira`. As marcas gravadas na
função (`exige_login`, `permissao`, `modulo`, `exige_filial`) são as mesmas da
web, e é por elas que as varreduras perguntam, depois do fato, se a guarda foi
posta (`tests/test_guarda.py`, `tests/test_guarda_modulo.py`).

Ordem de uso, de fora para dentro, igual à web:

    @router.get(...)
    @api_exigir_permissao("filiais.editar")
    @api_exigir_modulo_ligado("filiais")
    def listar_filiais(request): ...
"""

from __future__ import annotations

from functools import wraps

from .guardas_de_acesso import barreira
from .respostas_da_api import resposta_da_barreira
from .sessao import usuario_da_sessao

__all__ = [
    "ABERTAS_DA_API", "SEM_MODULO_NA_API", "api_exigir_filial", "api_exigir_login",
    "api_exigir_modulo_ligado", "api_exigir_permissao",
]

#: As operações que vivem sem guarda, e o motivo de cada uma — o mesmo
#: espírito de `comum.guardas_de_acesso.TELAS_ABERTAS`.
ABERTAS_DA_API: frozenset[str] = frozenset({
    # A primeira pergunta do app, antes de qualquer sessão existir — ver
    # `plataforma.api.versao`.
    "versao",
    # A porta: não há sessão antes dela.
    "entrar",
    # Precisa funcionar com sessão órfã (conta apagada ou desativada depois do
    # login) — a mesma razão de `sair` em `TELAS_ABERTAS`.
    "sair",
    # Os tokens da marca, para a tela de entrada do app se vestir antes de
    # haver sessão — a mesma razão de `tema` em `TELAS_ABERTAS`.
    "tema",
    # A tela de entrada do app, em dados: é a porta, e não diz nada que a
    # tela de entrada da web não mostre — a mesma razão de `entrar`.
    "entrada",
})

#: As operações que não pertencem a módulo nenhum, e o motivo de cada uma.
#: Tudo o que não está aqui precisa de `api_exigir_modulo_ligado`.
SEM_MODULO_NA_API: frozenset[str] = frozenset({
    # Não há módulo para desligar a pergunta "que API existe".
    "versao",
    # Entrar, sair e saber quem se é são a base: não existe módulo que, desligado,
    # devesse trancar alguém para fora da própria sessão.
    "entrar",
    "sair",
    "eu",
    # A filial do contexto existe com o módulo de Filiais desligado — ele
    # desliga a TELA de cadastro, não o seletor do cabeçalho. É o mesmo que
    # `filial_trocar` faz na web, só com login.
    "trocar_filial",
    # Os tokens da marca, para a tela de entrada do app se vestir antes de
    # haver sessão — a mesma razão de `tema` em `TELAS_ABERTAS`.
    "tema",
    # A tela de entrada do app, em dados: é a porta, e não diz nada que a
    # tela de entrada da web não mostre — a mesma razão de `entrar`.
    "entrada",
    # A foto e o idioma de quem está logado são do cabeçalho, que existe em
    # toda tela — a mesma razão de `eu`: módulo desligado nenhum tira alguém
    # do próprio avatar nem da própria língua.
    "meu_avatar",
    "meu_idioma",
    # O logo do menu da empresa (15/09/2026): é a moldura, como o avatar — e o
    # módulo de Empresas desligado não pode tirar do cliente a própria marca.
    "logo_do_menu",
})


def _guardar(view, **condicoes):
    @wraps(view)
    def guardada(request, *args, **kwargs):
        obstaculo = barreira(request, nome_da_rota=view.__name__, **condicoes)
        if obstaculo is not None:
            return resposta_da_barreira(obstaculo)
        request.usuario = usuario_da_sessao(request)
        return view(request, *args, **kwargs)

    return guardada


def api_exigir_login(view):
    guardada = _guardar(view)
    guardada.exige_login = True
    return guardada


def api_exigir_permissao(nome: str):
    def decorar(view):
        guardada = _guardar(view, permissao=nome)
        guardada.exige_login = True
        guardada.permissao = nome
        return guardada

    return decorar


def _sem_sessao(view, **condicoes):
    """Para as guardas que só se compõem por DENTRO de uma de login."""

    @wraps(view)
    def guardada(request, *args, **kwargs):
        obstaculo = barreira(request, exige_sessao=False, **condicoes)
        if obstaculo is not None:
            return resposta_da_barreira(obstaculo)
        return view(request, *args, **kwargs)

    return guardada


def api_exigir_modulo_ligado(chave: str):
    def decorar(view):
        guardada = _sem_sessao(view, modulo=chave)
        guardada.modulo = chave
        return guardada

    return decorar


def api_exigir_filial(view):
    guardada = _sem_sessao(view, exige_filial=True)
    guardada.exige_filial = True
    return guardada
