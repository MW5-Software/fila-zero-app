"""Quem está olhando, traduzido para a linha do banco — nada além disso.

Existe abaixo de `contas.alcance` e `contas.lugar` de propósito: os dois
precisam da MESMA tradução ("isto é a linha do ORM, ou o retrato congelado
da sessão, e a resposta é a linha do ORM ou `None`"), e um dos dois
importando o outro para pegar essa função fechava um ciclo — mascarado por
import tardio dentro da função que precisava dele. Um módulo comum, abaixo
dos dois, é a saída que não depende de ORDEM de carga: nada aqui importa
`alcance` nem `lugar`, então os dois podem importar DAQUI no topo do
arquivo sem se cruzar.
"""

from __future__ import annotations

from .models import Usuario

__all__ = ["usuario_de"]


def _id_de(usuario) -> "int | None":
    """O id de quem está olhando, venha ele de onde vier.

    **Existem DOIS tipos de usuário nesta casa**, e confundi-los foi o
    primeiro defeito destas funções:

    - `contas.models.Usuario`, o do ORM, que as telas de cadastro manipulam;
    - `nucleo.permissoes.User`, uma dataclass congelada que é o contrato do
      design system — é o que `comum.sessao.usuario_da_sessao` devolve, e é
      o que chega em toda requisição.

    Filtrar `Usuario.objects.filter(pk=<dataclass>)` levanta
    `TypeError: Field 'id' expected a number but got User(...)`. Resolver
    pelo ID serve aos dois sem que ninguém precise saber qual está na mão.

    O id da dataclass é string (`id="2"`), porque ela é feita para não
    depender de backend concreto; por isso o `int()`.
    """
    if usuario is None:
        return None
    if getattr(usuario, "is_authenticated", True) is False:
        return None
    bruto = getattr(usuario, "pk", None) or getattr(usuario, "id", None)
    try:
        return int(bruto)
    except (TypeError, ValueError):
        return None


#: Sentinela do memo. `None` é resposta legítima de `usuario_de` — "esta
#: pessoa não existe mais" —, então usar `None` como "ainda não li" faria a
#: consulta ser refeita justamente no caso que mais se repete.
_NAO_LIDO = object()


def usuario_de(usuario) -> "Usuario | None":
    """A linha do ORM de quem está olhando, ou `None`.

    `None` NÃO é "alcança tudo" — é "não alcança nada". Uma pessoa que sumiu
    do banco entre uma requisição e a seguinte, ou um retrato de sessão com
    id que não existe mais, precisa de silêncio restritivo: liberar por
    ausência de cadastro é como se abre porta sem querer.

    Devolve a instância recebida quando ela JÁ é do ORM, para a tela que tem
    a pessoa na mão não pagar uma consulta por pergunta. O `nivel`, as
    empresas e a carteira estão nessa mesma linha desde que o usuário passou
    a ser nosso — não há mais uma tabela vizinha para buscar.
    """
    if isinstance(usuario, Usuario):
        return usuario
    id_ = _id_de(usuario)
    if id_ is None:
        return None

    # **Uma consulta por REQUISIÇÃO, e não por pergunta.**
    #
    # Medido em 09/09/2026: uma página do catálogo fazia 86 consultas, e 35
    # delas eram esta — a MESMA linha relida a cada pergunta de permissão, de
    # alcance ou de preço. Não era N+1 de produto (o número não cresce com o
    # catálogo): era N+1 de PERGUNTA.
    #
    # O memo mora no `User` do design system, que é um retrato construído uma
    # vez por requisição pelo middleware: a vida do cache é a vida do objeto,
    # e não há como uma requisição enxergar o que a outra guardou. Um cache
    # de módulo (`lru_cache`) daria o mesmo ganho e serviria linha velha para
    # a requisição seguinte — que é o jeito errado de acertar isto.
    #
    # `object.__setattr__` porque o `User` é `frozen=True`: o congelamento
    # existe para ninguém acrescentar PERMISSÃO no meio da renderização, e o
    # que se guarda aqui não é permissão, é a linha que o backend já leu.
    memoria = getattr(usuario, "_pessoa_memorizada", _NAO_LIDO)
    if memoria is not _NAO_LIDO:
        return memoria

    pessoa = Usuario.objects.filter(pk=id_).first()
    try:
        object.__setattr__(usuario, "_pessoa_memorizada", pessoa)
    except (AttributeError, TypeError):
        # Objeto sem `__dict__` (um `namedtuple`, um mock com `__slots__`):
        # sem lugar para guardar, e uma consulta a mais é melhor que um erro.
        pass
    return pessoa
