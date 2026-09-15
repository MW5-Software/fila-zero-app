"""As regras que a tela de Filiais aplica antes de desativar ou remover uma
linha.

Moram à parte da view — não dentro de `views_filiais.py` — pelo mesmo motivo
de `contas.cargos.pode_remover`: a frase da recusa precisa existir num lugar
só, para nunca ser reescrita (com uma palavra diferente) em cada ponto que a
chama.
"""

from __future__ import annotations

from .models import Filial

__all__ = ["pode_desativar", "pode_remover"]


def pode_desativar(filial: Filial) -> "str | None":
    """A frase da recusa, se desativar (ou remover) `filial` deixaria a
    instalação sem NENHUMA filial ativa — ou `None`.

    A mesma frase serve às duas ações porque o defeito é idêntico nas duas:
    a instalação ficar sem filial usável. Uma pessoa sem filial nenhuma não
    opera (`comum.guardas_de_modulo.exigir_filial`) — isso é aceitável quando é
    ela que perdeu acesso a uma filial que ainda existe para outra pessoa;
    não é aceitável quando é a INSTALAÇÃO inteira que fica sem nenhuma, o que
    trancaria todo mundo de uma vez, sem meio de reabrir pela própria tela
    (ligar de volta a única filial dependeria de já ter uma filial ativa
    para acessar a tela que liga filial).

    Já inativa não entra nesta conta: desativar algo que já está desativado
    não piora nada, e removê-la (`pode_remover`, abaixo, que encadeia esta
    função) não muda quantas filiais ativas existem.
    """
    if not filial.ativa:
        return None
    # **Contada dentro da EMPRESA da filial**, e não na instalação
    # (14/09/2026). Com várias empresas na mesma instalação, contar a
    # instalação inteira deixava a Alfa desativar a única filial que tem só
    # porque a Beta tinha outras — e a Alfa ficava sem filial nenhuma.
    # `empresa_id=None` vira `IS NULL`: filial antiga sem empresa continua
    # contando entre as outras sem empresa, como antes.
    outras_ativas = Filial.objects.filter(
        empresa_id=filial.empresa_id, ativa=True).exclude(pk=filial.pk)
    if outras_ativas.exists():
        return None
    return ("Esta é a última filial ativa desta empresa. Ative outra "
            "antes de desativar ou remover esta.")


def _protegida(filial: Filial) -> bool:
    """Se algum `PROTECT` recusaria apagar esta filial."""
    from django.db import router
    from django.db.models.deletion import Collector, ProtectedError

    coletor = Collector(using=router.db_for_write(Filial, instance=filial))
    try:
        coletor.collect([filial])
    except ProtectedError:
        return True
    return False


def pode_remover(filial: Filial) -> "str | None":
    """A frase da recusa, se esta filial não pode ser removida — ou `None`.

    Mesmo molde de `contas.cargos.pode_remover`: devolve a frase, e não um
    booleano, porque a tela precisa dizer o motivo — e duas telas escrevendo
    a mesma frase à mão divergiriam com o tempo.
    """
    # A Matriz é o que garante que toda empresa tem pelo menos uma filial
    # (spec 2026-09-14, D7). Renomear pode; remover, não.
    if filial.e_matriz:
        return ("A Matriz não pode ser removida. Ela pode ser renomeada e "
                "editada como qualquer outra filial.")

    # A alocação aponta para a filial com `PROTECT`: sem esta frase, remover
    # daria erro 500 em vez de dizer o motivo. O lugar de trabalho de alguém
    # não some junto com a loja.
    if filial.alocacoes.exists():
        return ("Esta filial tem pessoas alocadas e não pode ser removida. "
                "Remova as alocações antes.")

    # **Qualquer outra tabela que proteja a filial**, dos módulos de negócio
    # que cada SaaS acrescenta (no Portal de Vendas, o orçamento). A base não
    # conhece esses módulos e não pode importá-los (`CLAUDE.md` §2), então
    # pergunta ao próprio Django o que um `delete()` recusaria — sem isto, a
    # primeira tabela de negócio com `PROTECT` para filial voltaria a dar 500.
    if _protegida(filial):
        return ("Esta filial tem registros ligados a ela e não pode ser "
                "removida. Desative-a em vez disso.")

    # Sem gente presa, o que resta é o mesmo risco de `pode_desativar`:
    # remover não pode ser o jeito de a instalação ficar sem filial ativa
    # nenhuma, do mesmo jeito que desativar não pode.
    return pode_desativar(filial)
