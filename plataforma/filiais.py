"""As regras que a tela de Filiais aplica antes de desativar ou remover uma
linha.

Moram à parte da view — não dentro de `views_filiais.py` — pelo mesmo motivo
de `contas.cargos.pode_remover`: a frase da recusa precisa existir num lugar
só, para nunca ser reescrita (com uma palavra diferente) em cada ponto que a
chama.
"""

from __future__ import annotations

from django.dispatch import Signal

from comum.listagem import ColunaFiltravel

from .contexto import empresa_atual
from .models import Filial

__all__ = ["FILTRAVEIS", "ORDENAVEIS", "ROTULOS", "antes_de_desativar",
           "empresa_do_pedido", "empresas_da_conta", "filiais_da_empresa",
           "pode_desativar", "pode_remover"]

#: Perguntado antes de desativar uma filial, com `filial=`. Quem responder
#: uma frase recusa a desativação, e a tela mostra a frase.
#:
#: Existe porque a base não conhece os módulos de negócio e não pode
#: importá-los (`CLAUDE.md` §3), mas é o módulo que sabe se desativar prende
#: alguém: no Fila Zero, quem estava presente numa loja desativada ficava sem
#: conseguir bater o ponto em outra até alguém reativá-la (revisão final,
#: 15/09/2026). O módulo liga o receptor no `ready()` do app. Como
#: `pode_remover` encadeia `pode_desativar`, a recusa vale para remover também.
antes_de_desativar = Signal()


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
    if not outras_ativas.exists():
        return ("Esta é a última filial ativa desta empresa. Ative outra "
                "antes de desativar ou remover esta.")
    for _receptor, motivo in antes_de_desativar.send(sender=Filial, filial=filial):
        if motivo:
            return str(motivo)
    return None


def _o_que_protege(filial: Filial) -> list[str]:
    """O nome, no plural, de cada tabela cujo `PROTECT` recusaria apagar esta
    filial — lista vazia se nenhuma recusaria.

    Pergunta ao próprio `Collector` do Django, que é quem o `delete()` usa: a
    base não conhece os módulos de negócio e não pode importá-los (`CLAUDE.md`
    §3). Nomear aqui uma relação deles (`filial.orcamentos`, que esta função
    substituiu em 15/09/2026) é a mesma camada invertida sem o `import`: a
    varredura `test_camadas_nao_se_invertem.py` não vê, e a cópia desta base
    para um produto sem orçamento quebraria com `AttributeError` — o mesmo
    tipo de preço que o backup já pagou com `No module named 'catalogo'`.
    """
    from django.db import router
    from django.db.models.deletion import Collector, ProtectedError

    coletor = Collector(using=router.db_for_write(Filial, instance=filial))
    try:
        coletor.collect([filial])
    except ProtectedError as recusa:
        return sorted({str(type(obj)._meta.verbose_name_plural)
                       for obj in recusa.protected_objects})
    return []


def _protegida(filial: Filial) -> bool:
    """Se algum `PROTECT` recusaria apagar esta filial. O nome é o da base
    KRONOS, para o porte de lá para cá continuar batendo."""
    return bool(_o_que_protege(filial))


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
    # não some junto com a loja. Ela fica com frase própria, antes da
    # genérica, porque é da base e o remédio é outro (tirar a alocação, e não
    # desativar).
    if filial.alocacoes.exists():
        return ("Esta filial tem pessoas alocadas e não pode ser removida. "
                "Remova as alocações antes.")

    # **Qualquer outra tabela que proteja a filial**, dos módulos de negócio
    # que cada SaaS acrescenta. Sem isto, a primeira tabela de negócio com
    # `PROTECT` para filial voltaria a dar 500. A frase diz QUAIS registros,
    # pelo nome que o próprio model declara, porque "registros ligados"
    # sozinho deixaria a pessoa sem saber onde procurar.
    protegem = _o_que_protege(filial)
    if protegem:
        return (f"Esta filial tem registros ligados a ela "
                f"({', '.join(protegem)}) e não pode ser removida. "
                f"Desative-a em vez disso.")

    # Sem gente presa, o que resta é o mesmo risco de `pode_desativar`:
    # remover não pode ser o jeito de a instalação ficar sem filial ativa
    # nenhuma, do mesmo jeito que desativar não pode.
    return pode_desativar(filial)


def empresas_da_conta(empresa) -> list:
    """As empresas da MESMA conta de `empresa` — o que o seletor da tela de
    Filiais oferece (23/09/2026, pedido do cliente: "quando eu for criar filial
    num dono de conta com mais de uma empresa, preciso de um seletor para dizer
    de qual filial é aquela empresa").

    **Pela conta, e não pelo alcance da pessoa**: quem abre esta tela tem
    `filiais.editar`, que é do titular e da MW5, e a conta do titular são
    exatamente as empresas dele. Para o membro — que não tem a permissão — o
    seletor nem chega a existir.

    Sem empresa (ou empresa sem titular, o que só acontece antes da conta
    existir), a lista é vazia.
    """
    from .models import Empresa

    if empresa is None or empresa.dono_id is None:
        return []
    return list(Empresa.objects.filter(dono_id=empresa.dono_id)
                .order_by("razao_social"))


def empresa_do_pedido(request):
    """A empresa escolhida na TELA: `?empresa=` no GET ou `empresa` no POST,
    validada contra as empresas da conta.

    Um id de fora — de outra conta, ou inventado — é descartado, e a escolha
    cai na empresa do contexto, que é a mesma trava de sempre: o pedido nunca
    AMPLIA o alcance, só escolhe dentro dele.
    """
    from comum.pedido import inteiro_do_texto

    dona = empresa_atual(request)
    bruto = request.POST.get("empresa") or request.GET.get("empresa") or ""
    escolhida = inteiro_do_texto(bruto)
    for candidata in empresas_da_conta(dona):
        if candidata.pk == escolhida:
            return candidata
    return dona


def filiais_da_empresa(request, empresa=None):
    """As filiais que a tela e a API enxergam: as da empresa do contexto, e só elas.

    **É a trava da tela de Filiais, e é o que permitiu dar `filiais.editar` ao
    titular** (14/09/2026). Até ali ela listava `Filial.objects.all()` — as
    filiais da instalação inteira —, o que era aceitável enquanto só a MW5 a
    abria e seria vazamento na mão de um cliente: o titular da Alfa veria, e
    editaria, as lojas da Beta.

    Listagem, exportação, TODAS as ações da tela e a lista da API passam por
    aqui — e é por isso que mora aqui e não na view: a API não importa view
    (`tests/test_api_nao_importa_view.py`), e uma segunda cópia desta trava é
    a cópia que alguém esquece de corrigir.

    `empresa` é a escolha da TELA de Filiais (`?empresa=`, ver
    `empresa_do_pedido`), e só vale dentro da conta: um id de outra conta cai
    na empresa do contexto. A API chama sem `empresa`, e continua enxergando a
    empresa do cabeçalho — o alcance dela não muda por causa da tela.

    Sem empresa no contexto, nada: `none()` e não `all()`, porque o erro de
    faltar contexto não pode ser mostrar tudo.
    """
    dona = empresa_atual(request)
    if empresa is not None:
        dona = next((e for e in empresas_da_conta(dona) if e.pk == empresa.pk),
                    dona)
    if dona is None:
        return Filial.objects.none()
    return Filial.objects.filter(empresa=dona)


#: As colunas ordenáveis e filtráveis da lista de filiais — as mesmas na tela,
#: na exportação e na API. Moradas aqui pelo motivo de `filiais_da_empresa`.
#: `chave da URL -> campo(s) do ORM`: só o que esta lista declara pode entrar
#: em `order_by` (ver `comum.listagem._resolver_ordenacao`).
ORDENAVEIS = {
    "filial": ("apelido", "nome"),
    "cnpj": ("cnpj",),
    "municipio": ("municipio", "uf"),
    "situacao": ("ativa", "apelido"),
}

FILTRAVEIS = {
    "filial": ColunaFiltravel(("apelido", "nome"), "Filial"),
    # Caixa de escolha, não campo de digitar — mesmo raciocínio da coluna
    # "Situação" de `contas.views_usuarios`: ativa ou inativa são dois
    # valores conhecidos, e um campo de texto sobre eles convida ao erro.
    "situacao": ColunaFiltravel("ativa", "Situação", tipo="opcoes",
                                opcoes=lambda: [("1", "Ativa"), ("0", "Inativa")]),
}

#: Os rótulos das colunas, para a API descrever as que só ordenam — na tela,
#: eles vão direto no `pagina.cabecalho(...)`.
ROTULOS = {
    "filial": "Filial",
    "cnpj": "CNPJ",
    "municipio": "Município/UF",
    "situacao": "Situação",
}
