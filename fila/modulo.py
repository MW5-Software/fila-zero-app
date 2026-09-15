"""O que o módulo da fila diz sobre si.

`ativo_por_padrao=True`, contra a regra geral da R47: a fila É o produto. Uma
instalação do Fila Zero com a fila desligada não serve para nada, e esperar a
MW5 ligar em cada instalação nova é um dia de loja sem fila.

`fila.ver` vem PRIMEIRO de propósito (desvio D-1 do plano de 15/09/2026): o
menu da base põe o módulo na barra pela primeira permissão e some com os
atalhos de quem não a tem. Com outra na frente, o supervisor, que só corrige,
não acharia a fila, e quem só cuida dos cadastros não veria os cadastros.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from plataforma.declaracao import Atalho, ModuloSpec

MODULO = ModuloSpec(
    chave="fila",
    rotulo=_("Fila da vez"),
    icone="users",
    grupo="Vendas",
    rota="/fila",
    # fila.relatorios (entrega 2) e fila.metas (entrega 3) no fim: fila.ver
    # continua a primeira, que é a do menu.
    permissoes=("fila.ver", "fila.participar", "fila.gerenciar",
                "fila.cadastros", "fila.relatorios", "fila.metas"),
    atalhos=(
        Atalho(rotulo=_("Grupos de item"), rota="/fila/grupos",
               permissao="fila.cadastros", grupo="Cadastro",
               pai="Fila da vez"),
        Atalho(rotulo=_("Motivos de não venda"), rota="/fila/motivos",
               permissao="fila.cadastros", grupo="Cadastro",
               pai="Fila da vez"),
        Atalho(rotulo=_("Tipos de pausa"), rota="/fila/pausas",
               permissao="fila.cadastros", grupo="Cadastro",
               pai="Fila da vez"),
        Atalho(rotulo=_("Metas"), rota="/fila/metas",
               permissao="fila.metas", grupo="Cadastro",
               pai="Fila da vez"),
    ),
    ativo_por_padrao=True,
)
