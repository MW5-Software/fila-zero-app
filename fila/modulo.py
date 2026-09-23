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
        # O cadastro da fila mora em "Configuração > Configurações da Fila"
        # (23/09/2026). Eram quatro itens pendurados num SEGUNDO "Fila da vez",
        # dentro do grupo "Cadastro": o módulo repetido na barra, e o cadastro
        # longe do nome dele. O grupo dos cadastros do cliente passou a se
        # chamar Configuração (`contas/modulo.py`, `plataforma/modulo.py`).
        #
        # "Configurações da Fila", e não "Fila" (o cliente corrigiu com o
        # print da barra na mão): "Fila" sozinho dizia o mesmo que o item da
        # página, e não dizia que ali dentro se CONFIGURA.
        Atalho(rotulo=_("Grupos de item"), rota="/fila/grupos",
               permissao="fila.cadastros", grupo="Configuração",
               pai="Configurações da Fila"),
        Atalho(rotulo=_("Motivos de não venda"), rota="/fila/motivos",
               permissao="fila.cadastros", grupo="Configuração",
               pai="Configurações da Fila"),
        Atalho(rotulo=_("Tipos de pausa"), rota="/fila/pausas",
               permissao="fila.cadastros", grupo="Configuração",
               pai="Configurações da Fila"),
        # Solto no grupo, ao lado da fila, e não como submenu: um `pai` com o
        # nome do módulo criaria um segundo item com o mesmo rótulo.
        Atalho(rotulo=_("Histórico da fila"), rota="/fila/historico",
               permissao="fila.gerenciar", grupo="Gerenciar Fila"),
        # **Metas é de primeiro nível** (23/09/2026; o cliente pediu "Metas vai
        # ser um Menu de Nível 1", e corrigiu com o print da barra: "igual
        # Configurações e Gerenciar Fila"). Era filha do "Fila da vez", e virou
        # o grupo dela — grupo que o menu DESFAZ, porque ele tem um destino só
        # e com o nome dele mesmo: com o degrau, a barra diria "Metas" duas
        # vezes (`plataforma/menu.py`). O que fica é o que o cliente pediu:
        # "Metas" no primeiro nível, ao lado de Configuração e Gerenciar Fila,
        # abrindo a tela num clique.
        #
        # O ícone é o do ATALHO, e só passou a importar aqui: no segundo nível
        # o `Sidebar` não desenha ícone, e no primeiro desenha em todo item.
        Atalho(rotulo=_("Metas"), rota="/fila/metas", icone="target",
               permissao="fila.metas", grupo="Metas"),
    ),
    ativo_por_padrao=True,
)
