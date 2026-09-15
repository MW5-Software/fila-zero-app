"""A memória de UMA requisição — e a invalidação que a torna segura.

**O problema medido em 09/09/2026.** Uma página do catálogo fazia 73
consultas, e 23 delas eram a MESMA linha de usuário. Não era N+1 de produto
(o número não muda com o tamanho do catálogo): era N+1 de PERGUNTA. Toda
guarda, todo menu, todo `do_contexto` chama `usuario_da_sessao(request)`, e
cada chamada reconstruía a identidade do zero — a linha do usuário, o
conjunto de permissões e o parâmetro do relógio de sessão, oito vezes.

**Por que não bastou memorizar.** A primeira tentativa guardou o resultado no
`request` e foi desfeita: a casa tem uma invariante que um memo ingênuo
quebra — *o banco decide a cada requisição, nunca o que a sessão gravou no
passado* (ver `comum.sessao.usuario_da_sessao`). Ela vale entre requisições,
e um memo por requisição a respeita — MENOS quando é a própria requisição que
muda a resposta: a tela que desativa alguém, a que rebaixa o titular, a que
começa ou encerra uma personificação. Nesses casos o memo serviria, depois da
escrita, a identidade de antes dela.

**A saída é uma geração global.** Qualquer escrita no banco — em qualquer
tabela, sem lista de exceção — avança um contador, e o memo de uma requisição
só vale enquanto a geração dele for a corrente. Escreveu, esqueceu.

Global e sem lista de propósito. A alternativa seria enumerar as tabelas que
decidem identidade (usuário, perfil, permissão, empresa, parâmetro, sessão) —
e essa lista é exatamente o tipo de coisa que envelhece calada: a tabela nova
de amanhã que também decide não estaria nela, e o defeito apareceria como
"uma tela mostrando dado velho", sem nada apontando para cá. Requisição que
escreve é minoria, e pagar consulta a mais nela é o lado certo de errar.
"""

from __future__ import annotations

import itertools

__all__ = ["esquecer", "geracao", "lembrar"]

#: Contador da geração. `itertools.count` porque o incremento dele é atômico
#: sob o GIL — não há dois pedidos disputando um `+= 1` com resultado perdido.
_RELOGIO = itertools.count()
_GERACAO = next(_RELOGIO)


def geracao() -> int:
    """A geração corrente. Existe para o teste conseguir afirmar que uma
    escrita a moveu, sem depender de qual consulta ela evitou."""
    return _GERACAO


def esquecer(*_args, **_kwargs) -> None:
    """Invalida toda memória de pedido que já foi guardada.

    Assinatura aberta porque quem chama é um sinal do Django (`post_save`,
    `post_delete`, `m2m_changed`), cada um com um jogo de argumentos
    diferente, e nenhum deles interessa: a resposta é a mesma para todos.
    """
    global _GERACAO
    _GERACAO = next(_RELOGIO)


def lembrar(request, chave: str, calcular):
    """`calcular()` uma vez por requisição, sob `chave`.

    Sem `request` — um comando de linha, uma tarefa do cron, um teste que
    chama a função direta — não há requisição de que lembrar, e a função
    simplesmente calcula. O mesmo vale para um objeto que não aceita
    atributo novo: uma consulta a mais é melhor que um erro.

    `None` é resposta legítima (a pessoa não existe mais, a empresa não foi
    escolhida), então a presença da CHAVE é o que decide se já foi calculado
    — nunca o valor guardado.
    """
    if request is None:
        return calcular()

    guardado = getattr(request, "_memoria_do_pedido", None)
    if guardado is None or guardado[0] != _GERACAO:
        guardado = (_GERACAO, {})
        try:
            request._memoria_do_pedido = guardado
        except (AttributeError, TypeError):
            return calcular()

    memo = guardado[1]
    if chave not in memo:
        memo[chave] = calcular()
    return memo[chave]
