"""Os parâmetros que a base já sabe usar.

Moram em `plataforma/`, e não num módulo de negócio, pelo mesmo critério de
`plataforma/modulo.py`: os dois resolvem "este cliente é diferente" para uma
peça da própria base (listagem, filial), não para uma regra de um segmento.
Só a declaração mora aqui — quem registra é `apps.PlataformaConfig.ready()`.

R47 (`docs/superpowers/decisoes-2026-08-20-fatia-fina.md`) pediu parâmetros
"genuinamente úteis hoje" — por isso os dois abaixo já são LIDOS por código
que já existia antes desta task (`comum.listagem`, `plataforma.
views_filiais`), e não uma tabela de configuração à espera de um consumidor.
"""

from __future__ import annotations

from comum.listagem import POR_PAGINA
from plataforma.parametro_declaracao import ParametroSpec
from django.utils.translation import gettext_lazy as _

#: "Eu sou o Itens por página. Meu tipo é número. Meu padrão é 25 — o mesmo
#: `POR_PAGINA` que `comum.listagem` já usava fixo. Eu moro no grupo
#: Listagens. Só a MW5 pode me mudar."
#:
#: `so_mw5=True`: é um número que pesa na consulta de TODA tela de tabela da
#: instalação (`comum.listagem.montar_pagina`) — um admin de cliente
#: apertando para 1000 "para ver tudo de uma vez" é exatamente o tipo de
#: decisão técnica que este projeto não delega, pelo mesmo raciocínio que já
#: mantém Aparência e Módulos fechados a `is_superuser`
#: (`plataforma/views.py`).
PARAMETRO_ITENS_POR_PAGINA = ParametroSpec(
    chave="itens_por_pagina",
    rotulo=_("Itens por página"),
    tipo="numero",
    padrao=POR_PAGINA,
    grupo="Listagens",
    ajuda="Quantas linhas cada tela de listagem mostra antes de paginar.",
    so_mw5=True,
)

#: "Eu sou a Nova filial nasce ativa. Meu tipo é sim/não. Meu padrão é sim —
#: o mesmo comportamento que `Filial.ativa` já tinha (default=True). Eu moro
#: no grupo Filiais. O admin do cliente pode me mudar."
#:
#: `so_mw5=False`: é uma escolha de processo, não de técnica — algumas
#: instalações cadastram a filial pronta para operar na hora; outras
#: preferem montar o cadastro primeiro e só ativar quando a unidade abrir
#: de fato. Nenhuma das duas é mais "certa"; é o admin do cliente quem
#: decide como a própria operação funciona.
PARAMETRO_NOVA_FILIAL_NASCE_ATIVA = ParametroSpec(
    chave="nova_filial_nasce_ativa",
    rotulo=_("Nova filial nasce ativa"),
    tipo="sim_nao",
    padrao=True,
    grupo="Filiais",
    ajuda="Se marcado, uma filial recém-criada já aparece no seletor. Se "
          "desmarcado, ela nasce desativada até alguém ativá-la nesta tela.",
    so_mw5=False,
)
