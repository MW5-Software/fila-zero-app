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
    # "Gerenciar fila", e não "Vendas" (23/09/2026, pedido do cliente): o grupo
    # reúne as telas de quem TOCA a fila — a página da loja, o histórico das
    # correções e as metas —, e "Vendas" nomeava um assunto que a base não tem
    # aqui.
    grupo="Gerenciar Fila",
    rota="/fila",
    # fila.relatorios (entrega 2) e fila.metas (entrega 3) no fim: fila.ver
    # continua a primeira, que é a do menu.
    permissoes=("fila.ver", "fila.participar", "fila.gerenciar",
                "fila.cadastros", "fila.relatorios", "fila.metas"),
    atalhos=(
        # O cadastro da fila mora em "Configuração > Fila" (23/09/2026, pedido
        # do cliente: "em vez de Fila da Vez muda para Configuração/Fila").
        # Eram quatro itens pendurados num SEGUNDO "Fila da vez", dentro do
        # grupo "Cadastro": o módulo repetido na barra, e o cadastro longe do
        # nome dele. O grupo dos cadastros do cliente passou a se chamar
        # Configuração (`contas/modulo.py`, `plataforma/modulo.py`), e o pai
        # aqui é "Fila".
        Atalho(rotulo=_("Grupos de item"), rota="/fila/grupos",
               permissao="fila.cadastros", grupo="Configuração",
               pai="Fila"),
        Atalho(rotulo=_("Motivos de não venda"), rota="/fila/motivos",
               permissao="fila.cadastros", grupo="Configuração",
               pai="Fila"),
        Atalho(rotulo=_("Tipos de pausa"), rota="/fila/pausas",
               permissao="fila.cadastros", grupo="Configuração",
               pai="Fila"),
        # Solto no grupo, ao lado da fila, e não como submenu: um `pai` com o
        # nome do módulo criaria um segundo item com o mesmo rótulo.
        Atalho(rotulo=_("Histórico da fila"), rota="/fila/historico",
               permissao="fila.gerenciar", grupo="Gerenciar Fila"),
        # **Metas é de PRIMEIRO nível** (23/09/2026, pedido do cliente: "Metas
        # vai ser um Menu de Nível 1"): era filha do "Fila da vez", e a tela em
        # que a gestão mexe todo mês fica no mesmo degrau da página e do
        # histórico.
        Atalho(rotulo=_("Metas"), rota="/fila/metas",
               permissao="fila.metas", grupo="Gerenciar Fila"),
    ),
    ativo_por_padrao=True,
)
