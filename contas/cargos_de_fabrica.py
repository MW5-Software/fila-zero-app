"""Os cinco cargos com que toda conta nasce, e como eles chegam lá.

Os valores vêm do spec 2026-09-14 ("Os cargos de fábrica e o que eles trazem").
São **iniciais**: o titular edita permissões e alcance de qualquer um depois, e
por isso a semeadura só CRIA o que falta e nunca toca no que já existe —
rodá-la de novo desfaria o ajuste que o titular fez.

**Por que dois caminhos de semeadura, e não um.**

- `post_save` do titular (`contas/apps.py`): a conta nova nasce com os cargos.
  Titular nasce por mais de um caminho — a tela de usuários, o shell, um teste —,
  e cada caminho que lembrasse de semear seria um que um dia esquece.
- `post_migrate` (`plataforma/apps.py`): o titular que já existia antes desta
  mudança ganha os cargos na primeira `migrate` da atualização. Não é migração
  de dados de propósito: as `Permission` de módulo só existem depois de
  `contas.permissoes.materializar`, que também roda no `post_migrate` — numa
  migração elas podem ainda não estar lá, e o cargo nasceria vazio para sempre.

**Permissão que não existe é pulada, e não é erro.** Um módulo desligado do
código deixa de ter a permissão materializada; o cargo nasce sem ela em vez de
derrubar o cadastro de um titular.
"""

from __future__ import annotations

__all__ = ["DE_FABRICA", "garantir_cargos_de_fabrica", "semear_cargos"]

#: Quem cada cargo de fábrica pode conceder numa alocação (17/09/2026, pedido
#: do cliente): o gerente cria vendedor, e o supervisor é o gerente com
#: alcance maior — cria vendedor e gerente. Por NOME de cargo de fábrica, que
#: é o identificador estável; a lista de um cargo criado pelo titular é
#: marcada por ele em `/cargos`.
CONCEDE: "dict[str, tuple[str, ...]]" = {
    "supervisor": ("vendedor", "gerente"),
    "gerente": ("vendedor",),
}

#: `(nome, rotulo, alcance, e_cliente, permissoes)`. Alcance em texto e
#: permissões no vocabulário do núcleo (`modulo.acao`), para esta lista não
#: depender de model nenhum.
#:
#: **Na base, só as permissões que a base tem.** Os nomes, alcances e a marca
#: de cliente são os do Portal de Vendas, de onde a base saiu, e servem a
#: qualquer SaaS de venda. As permissões de negócio (catálogo, orçamentos no
#: Portal) são de cada produto: ele as acrescenta aqui ao nascer da base.
#: Permissão que o código não declara seria pulada em silêncio pela semeadura
#: — e uma lista com nome de módulo que não existe é o jeito de ninguém notar
#: um erro de digitação.
#:
#: **No Fila Zero, as permissões da fila** (spec 2026-09-15, "Permissões e
#: cargos", e o desvio D-1 do plano: `fila.ver` acompanha toda permissão da
#: fila, porque é ela que põe a fila no menu). Representante e Cliente não
#: estão na loja atendendo, e por isso não trazem nada da fila.
#: `fila.relatorios` (entrega 2): gerente e supervisor leem os indicadores do
#: alcance deles. `fila.metas` (entrega 3): gerente e supervisor definem as
#: metas do alcance deles.
DE_FABRICA: "tuple[tuple[str, str, str, bool, tuple[str, ...]], ...]" = (
    ("supervisor", "Supervisor", "empresa", False,
     ("usuarios.editar", "fila.ver", "fila.gerenciar", "fila.relatorios",
      "fila.metas")),
    ("gerente", "Gerente", "filial", False,
     ("usuarios.editar", "fila.ver", "fila.participar", "fila.gerenciar",
      "fila.relatorios", "fila.metas")),
    ("vendedor", "Vendedor", "filial", False,
     ("fila.ver", "fila.participar")),
    ("representante", "Representante", "filial", False, ()),
    ("cliente", "Cliente", "proprios", True, ()),
)

#: Nível TITULAR congelado como literal: esta função roda com modelos
#: históricos no `post_migrate`, e a escala de `Nivel` já mudou duas vezes.
_TITULAR = 1


def _modelos(apps):
    if apps is None:
        from django.apps import apps as apps_reais

        apps = apps_reais
    return (apps.get_model("contas", "Cargo"),
            apps.get_model("auth", "Permission"))


def semear_cargos(conta, apps=None, using=None) -> int:
    """Dá à `conta` os cargos de fábrica que ela ainda não tem. Devolve quantos
    criou."""
    from .permissoes import CONTENT_TYPE

    Cargo, Permission = _modelos(apps)
    cargos = Cargo.objects.db_manager(using) if using else Cargo.objects
    permissoes = (Permission.objects.db_manager(using) if using
                  else Permission.objects)

    tem = set(cargos.filter(conta_id=conta.guid)
              .values_list("nome", flat=True))
    app_label, model = CONTENT_TYPE
    criados = 0
    for nome, rotulo, alcance, e_cliente, chaves in DE_FABRICA:
        if nome in tem:
            continue
        cargo = cargos.create(conta_id=conta.guid, nome=nome, rotulo=rotulo,
                              alcance=alcance, e_cliente=e_cliente,
                              de_fabrica=True)
        cargo.permissoes.set(permissoes.filter(
            content_type__app_label=app_label, content_type__model=model,
            codename__in=[chave.replace(".", "_") for chave in chaves]))
        criados += 1
    _ligar_quem_concede_quem(cargos, conta)
    return criados


def _ligar_quem_concede_quem(cargos, conta) -> None:
    """A lista `pode_conceder` dos cargos de fábrica desta conta.

    Só preenche o que está VAZIO, pelo mesmo motivo de a semeadura só criar o
    que falta: quem apagou a lista de propósito não a vê voltar na próxima
    `migrate`. Roda depois de criar todos, porque o gerente pode ser criado
    antes do vendedor que ele concede.
    """
    da_conta = {c.nome: c for c in cargos.filter(conta_id=conta.guid)}
    for nome, concedidos in CONCEDE.items():
        cargo = da_conta.get(nome)
        if cargo is None or cargo.pode_conceder.exists():
            continue
        cargo.pode_conceder.set([da_conta[n] for n in concedidos
                                 if n in da_conta])


def garantir_cargos_de_fabrica(apps=None, using=None) -> int:
    """Semeia todo titular desta instalação. Devolve quantos cargos criou.

    Chamado no `post_migrate`. Numa `migrate` parcial, ou revertendo para antes
    de `contas.0013`, o model histórico ainda não tem `Cargo` — e aí não há o
    que semear.
    """
    try:
        _modelos(apps)
    except LookupError:
        return 0
    if apps is None:
        from django.apps import apps as apps_reais

        apps = apps_reais
    Usuario = apps.get_model("contas", "Usuario")
    pessoas = Usuario.objects.db_manager(using) if using else Usuario.objects
    return sum(semear_cargos(titular, apps=apps, using=using)
               for titular in pessoas.filter(nivel=_TITULAR))
