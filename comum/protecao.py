"""O que segura uma linha que alguém tentou apagar, dito por extenso.

**Existe porque a tela chutava a causa.** `plataforma.views_empresa`
capturava `ProtectedError` e respondia "tem filial cadastrada e não pode ser
removida. Apague as filiais dela primeiro" — verdade em agosto, quando
`Filial` era a única tabela que apontava para `Empresa`. Hoje são dezesseis,
e o catálogo inteiro nasceu depois: uma empresa segurada por dois segmentos e
três famílias recebia uma frase que citava filiais que não existiam, e mandava
apagar o que não estava no caminho. Errado nas duas metades — e uma mensagem
de erro que aponta para o lugar errado é pior que um erro sem mensagem,
porque manda alguém procurar onde não tem.

A resposta certa o banco já sabe. Aqui ela é perguntada ao model, e não
escrita à mão: percorrer `_meta.related_objects` faz a tabela filha nova ser
contada no dia em que nasce, sem ninguém lembrar de vir atualizar uma lista —
que é exatamente o tipo de lista que ninguém lembra.
"""

from __future__ import annotations

__all__ = ["frase_do_impedimento", "quem_segura"]


def _reversas(registro):
    """Todas as relações que apontam para `registro` — inclusive as OCULTAS.

    `_meta.related_objects` seria o caminho óbvio, e ele deixa a metade que
    importa de fora: `ModeloDaEmpresa.empresa` (`contas/inquilino.py`) declara
    `related_name="+"`, que suprime o acessor reverso — e o Django não conta
    como "related object" o que não tem acessor. Ou seja, as dezesseis tabelas
    de negócio deste produto, TODAS com a coluna do inquilino em `PROTECT`,
    eram invisíveis para a contagem.

    O sintoma foi bonito de tão enganoso: a empresa não podia ser removida, e
    a função dizia que nada a segurava. `include_hidden=True` é o que traz a
    relação sem acessor de volta.
    """
    return [
        campo for campo in registro._meta.get_fields(include_hidden=True)
        if campo.is_relation and campo.auto_created and not campo.concrete
    ]


def quem_segura(registro) -> list[tuple[int, str]]:
    """`[(quantos, "segmentos"), (3, "famílias")]` — vazio quando nada segura.

    Só relações com `PROTECT`. `CASCADE` não entra de propósito: o que cai
    junto não impede nada, e citá-lo faria a frase listar coisas que a pessoa
    não precisa resolver.
    """
    from django.db.models import PROTECT

    achados = []
    for relacao in _reversas(registro):
        if getattr(relacao, "on_delete", None) is not PROTECT:
            continue
        quantos = relacao.related_model._base_manager.filter(
            **{relacao.field.name: registro}).count()
        if not quantos:
            continue
        meta = relacao.related_model._meta
        achados.append((
            quantos,
            str(meta.verbose_name_plural if quantos > 1 else meta.verbose_name),
        ))
    return achados


def frase_do_impedimento(registro) -> "str | None":
    """A frase pronta, ou `None` quando dá para remover.

    Lista TODAS as tabelas que seguram, e não a primeira: quem lê precisa
    saber o tamanho do trabalho antes de começar, e descobrir mais um
    impedimento a cada tentativa é o jeito mais cansativo de apagar uma
    linha.
    """
    achados = quem_segura(registro)
    if not achados:
        return None
    partes = [f"{quantos} {nome}" for quantos, nome in achados]
    if len(partes) == 1:
        lista = partes[0]
    else:
        lista = ", ".join(partes[:-1]) + f" e {partes[-1]}"
    return (f'Não dá para remover "{registro}": ainda tem {lista}. '
            f"Remova {'esses itens' if sum(q for q, _ in achados) > 1 else 'esse item'} antes.")
