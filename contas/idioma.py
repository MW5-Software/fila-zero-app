"""Gravar o idioma escolhido — a regra, sem tela.

Mora aqui, e não em `views_idioma.py`, porque tem dois chamadores: o seletor
do cabeçalho da web (`views_idioma.idioma`) e o do app
(`contas.api.meu_idioma`). A API não importa view
(`tests/test_api_nao_importa_view.py`), e uma segunda cópia desta regra seria
a que alguém esquece de corrigir.
"""

from __future__ import annotations

from django.conf import settings

from comum.idioma import CHAVE_IDIOMA

__all__ = ["existe", "guardar_escolha"]


def existe(codigo: str) -> bool:
    """`codigo` é um dos idiomas declarados? Código de fora não vira idioma:
    `translation.activate("xx")` não falha — ativa um catálogo vazio, e a tela
    sai com as frases em branco em vez de dar erro."""
    return any(codigo == chave for chave, _rotulo in settings.LANGUAGES)


def guardar_escolha(request, escolhido: str) -> bool:
    """Grava a escolha. Devolve se ela valia.

    Na PESSOA quando há pessoa — a preferência sobrevive ao logout, que é o
    ponto: quem trabalha em castelhano não pode ter de escolher toda manhã. E
    na sessão sempre, porque é ela que vale ANTES de o banco ser lido de novo
    e é ela que atende quem ainda não entrou.
    """
    if not existe(escolhido):
        return False

    from .identidade import usuario_de

    # `request.usuario` é o retrato congelado da sessão, não a linha do ORM —
    # e `request.user` é anônimo, porque esta casa não usa o login do
    # `django.contrib.auth` (ver `comum/idioma.py`).
    pessoa = usuario_de(getattr(request, "usuario", None))
    if pessoa is not None:
        pessoa.idioma = escolhido
        pessoa.save(update_fields=["idioma"])
    request.session[CHAVE_IDIOMA] = escolhido
    return True
