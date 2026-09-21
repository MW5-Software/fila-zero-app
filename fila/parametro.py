"""Os parâmetros do Fila Zero.

Moram aqui, e não em `plataforma/parametro.py`, pelo mesmo critério que separa
`fila/modulo.py` do módulo da base: o que a base declara resolve "este cliente
é diferente" para uma peça da própria base (listagem, filial); o que está aqui
resolve para uma regra deste produto. Só a declaração mora aqui — quem registra
é `apps.FilaConfig.ready()`.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from plataforma.parametro_declaracao import ParametroSpec

__all__ = ["PARAMETRO_META_PARA_GESTOR"]

#: "Eu sou a Meta para quem gerencia a loja. Meu tipo é sim/não. Meu padrão é
#: NÃO. Eu moro no grupo Metas. O admin do cliente pode me mudar."
#:
#: **Por que a meta de gestor é parâmetro, e não código** (18/09/2026): o
#: cliente decidiu que a meta é de quem atende, e a lista de metas passou a
#: deixar de fora quem gerencia a loja (`fila/quem_atende.py`). "Quem gerencia
#: também tem meta" é decisão de OPERAÇÃO, e não de arquitetura: a loja em que
#: o gerente também vende é a mesma imagem com esta caixa marcada. Escrever
#: `if` com o nome do cliente é o que a varredura de
#: `tests/test_sem_nome_de_cliente.py` recusa.
#:
#: `so_mw5=False`: é regra de negócio, e não decisão técnica — o mesmo critério
#: de `PARAMETRO_NOVA_FILIAL_NASCE_ATIVA`. Quem alcança a tela de Parâmetros
#: hoje é só a MW5 (`parametros.editar` não está nas permissões do titular,
#: `contas/fabrica.py`), e mudar isso é uma linha naquela tabela, não aqui.
PARAMETRO_META_PARA_GESTOR = ParametroSpec(
    chave="meta_para_gestor",
    rotulo=_("Meta para quem gerencia a loja"),
    tipo="sim_nao",
    padrao=False,
    grupo="Metas",
    ajuda="Se marcado, quem gerencia a loja (gerente e supervisor) também "
          "entra na lista de metas, como um vendedor. Desmarcado — o padrão — "
          "a meta é só de quem atende.",
    so_mw5=False,
)