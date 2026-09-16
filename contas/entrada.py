"""Entrar e sair, num lugar só — a tela e a API chamam as mesmas funções.

Uma regra de entrada escrita duas vezes diverge na primeira correção: foi o
caso de `entrar_na_sessao`, que precisou fechar a personificação órfã, e só
ficou certo para todo caminho de login porque todo caminho passa por lá.
"""

from __future__ import annotations

from comum.auditoria import ACOES, registrar
from comum.personificacao import encerrar, personificando
from comum.sessao import entrar_na_sessao, sair_da_sessao, usuario_da_sessao

from .backend import BackendDjango

__all__ = ["CREDENCIAIS_INVALIDAS", "autenticar_e_entrar", "sair_e_registrar"]

#: A mesma frase para login inexistente, senha errada e usuário inativo.
#: Distinguir os três entrega a lista de quem existe a quem estiver tentando.
CREDENCIAIS_INVALIDAS = "Credenciais inválidas."


def autenticar_e_entrar(request, login: str, senha: str):
    """A pessoa, já dentro da sessão — ou `None`, sem dizer por quê."""
    user = BackendDjango().autenticar(login, senha)
    if user is None:
        # Só o login digitado, nunca a senha, e nunca distinguindo "não
        # existe" de "senha errada" — essa distinção é o que
        # `CREDENCIAIS_INVALIDAS` existe para não entregar. Um registro que a
        # escrevesse de outro jeito (por exemplo, só gravando quando o login
        # existe) recriaria a mesma informação por outra porta.
        registrar(ACOES.ENTRADA_RECUSADA, login, alvo=login)
        return None
    entrar_na_sessao(request, user)
    registrar(ACOES.ENTROU, user, alvo=user.login)
    return user


def sair_e_registrar(request) -> None:
    """Encerra a personificação, registra quem saiu e derruba a sessão.

    Quem sai, personificando ou não, é sempre o ORIGINAL — o alvo nunca chamou
    rota nenhuma. Encerrar ANTES de ler a pessoa grava
    `PERSONIFICACAO_ENCERRADA` em nome do original e faz a leitura abaixo
    devolver o original. Sem isto a trilha dizia que o ALVO saiu, e nenhum
    registro fechava o período em que se agiu em nome de outra pessoa.

    A pessoa é lida ANTES de derrubar a sessão: depois não haveria quem
    atribuir. Sessão órfã (conta apagada ou desativada depois do login) não
    reconstrói ninguém, e aí não há o que registrar.
    """
    if personificando(request):
        encerrar(request)
    usuario = usuario_da_sessao(request)
    if usuario is not None:
        registrar(ACOES.SAIU, usuario, alvo=usuario.login, request=request)
    sair_da_sessao(request)
