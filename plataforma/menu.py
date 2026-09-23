"""O menu nasce do cruzamento: módulos ligados × permissão de quem olha.

Ninguém escreve menu. `modulos_ligados()` já devolve o módulo como ele está
nesta instalação — rótulo, grupo e ordem já mesclados com as sobrescritas do
banco. Este módulo não mescla nada de novo: só agrupa, filtra por permissão
e desenha.

**Esconder um item aqui não é proteger a rota.** O menu existe para não
poluir a tela com o que a pessoa não pode usar — quem tranca de verdade é a
rota, com `comum.guardas_de_acesso.exigir_permissao`. Alguém que digitar o endereço
direto na barra do navegador bate na mesma porta trancada, o item estando ou
não no menu.
"""

from __future__ import annotations

from django.utils.translation import gettext, gettext_lazy as _

from nucleo.layout import NavItem
from nucleo.permissoes import User, pode

from .catalogo import modulos_ligados

__all__ = ["montar"]


#: Os nomes de GRUPO do menu, aqui só para o extrator os enxergar.
#:
#: Eles não são escritos em lugar nenhum que o `xgettext`/Babel alcance: cada
#: módulo declara o grupo dele (`grupo="Vendas"`) e o valor é SEMEADO no
#: banco, que passa a mandar. Marcar a declaração seria pior — o valor
#: gravado na semeadura sairia na língua de quem rodou o `migrate`, e uma
#: instalação semeada em castelhano nasceria com "Registro" na coluna.
#:
#: Então a lista mora aqui, ao lado de quem traduz (`_traduzido`), e o
#: extrator a encontra. Nada lê esta tupla em tempo de execução.
#: O ícone do item que só ABRE. Ele não é um destino e não tem ícone próprio
#: declarado em lugar nenhum — e o `Sidebar` desenha ícone em todo item de
#: segundo nível, recusando nome vazio.
_ICONE_DO_PAI = "folder"

#: Os nomes de grupo de HOJE. O cliente renomeou dois e criou um em
#: 23/09/2026 — "Configuração" e "Gerenciar Fila" (`contas/modulo.py`,
#: `plataforma/modulo.py`) e "Metas" (`fila/modulo.py`) —, e "Geral" é o do
#: módulo de exemplo. Renomear um grupo é renomear esta lista também: é ela
#: que o extrator encontra, e sem ela o grupo sai em português na instalação
#: castelhana.
NOMES_DE_GRUPO = (
    _("Administração"), _("Configuração"), _("Gerenciar Fila"), _("Metas"),
    _("Geral"),
)


def _traduzido(rotulo: str) -> str:
    """O rótulo do menu na língua de quem olha — quando ele ainda é o nosso.

    **Rótulo de módulo é DADO, não código.** `ModuloSpec` só decide como o
    módulo NASCE; depois disso quem manda é a linha do banco, que a tela de
    Módulos edita — é uma das quatro alavancas que substituem o "branch por
    cliente". Marcar a constante para tradução, então, só alcançaria
    instalação nova.

    Traduzir aqui, na hora de desenhar, resolve os dois casos com uma regra
    só: "Catálogo" está no arquivo de tradução e sai na língua de quem olha;
    um rótulo que o cliente TROCOU ("Peças", "Reposição") não está lá e passa
    intacto — que é o certo, porque a palavra é dele e ninguém pediu para
    traduzi-la.
    """
    return gettext(rotulo) if rotulo else rotulo


def _atalhos_do_modulo(modulo, user) -> list[tuple[str, int, NavItem]]:
    """Os destinos a mais do módulo, já agrupados pelos que abrem.

    Um atalho sem `pai` entra solto no grupo, como sempre foi. Os que
    declaram um `pai` viram FILHOS de um item de segundo nível com esse
    rótulo — é o cadastro do catálogo (Segmentos, Linhas, Famílias, Marcas,
    Produtos) desde 10/09/2026.

    **O pai não é um destino.** Ele não tem rota nem permissão própria: quem
    decide se um filho aparece é a permissão DELE, e o pai só existe se
    sobrou algum filho. Um item que abre e não tem nada dentro é pior que
    item nenhum — parece defeito.

    A posição do pai é a do primeiro filho que apareceu, e a ordem dos filhos
    é a da declaração: em `catalogo/modulo.py` eles estão na ordem em que se
    cadastra de verdade (sem segmento não há linha, sem linha não há
    família), e essa ordem é informação.
    """
    soltos: list[tuple[str, int, NavItem]] = []
    #: `(grupo, pai) -> [posição, filhos]`. `dict` porque a ordem de inserção
    #: é a ordem em que os pais aparecem na barra.
    familias: dict[tuple[str, str], list] = {}

    for atalho in modulo.atalhos:
        if not pode(user, atalho.permissao):
            continue
        grupo = atalho.grupo or modulo.grupo
        ordem = modulo.ordem if atalho.ordem is None else atalho.ordem
        item = NavItem(label=_traduzido(atalho.rotulo), icon=atalho.icone,
                       href=atalho.rota, permission=atalho.permissao)
        if not atalho.pai:
            soltos.append((grupo, ordem, item))
            continue
        chave = (grupo, atalho.pai)
        if chave not in familias:
            familias[chave] = [ordem, []]
        familias[chave][0] = min(familias[chave][0], ordem)
        familias[chave][1].append(item)

    for (grupo, pai), (ordem, filhos) in familias.items():
        # `icon` no pai porque o `Sidebar` desenha ícone em todo item de
        # primeiro e segundo nível; sem um, `Icon` recusa o nome vazio.
        soltos.append((grupo, ordem, NavItem(
            label=_traduzido(pai), icon=_ICONE_DO_PAI, children=filhos)))
    return soltos


def _entradas_do_modulo(modulo, user) -> list[tuple[str, int, NavItem]]:
    """As entradas de menu que `modulo` dá a `user`: ele mesmo e os atalhos —
    ou nenhuma, se a pessoa não o alcança.

    Separado de `montar` porque são duas perguntas diferentes na mesma
    função: esta é "o que este módulo mostra a esta pessoa"; a de lá é "em
    que ordem os grupos saem".
    """
    # Tela da MW5 some para quem não é superusuário, e isso é a SEGUNDA
    # tranca — a permissão `mw5.*` não existe como linha no banco
    # (`contas/permissoes.py` pula os `so_mw5`), então não há o que
    # conceder num cargo. As duas juntas porque a fronteira aqui é a que
    # separa a MW5 do cliente, e ela não pode depender de um mecanismo só.
    if modulo.so_mw5 and not user.superuser:
        return []

    permissao = modulo.permissoes[0] if modulo.permissoes else None
    if not pode(user, permissao):
        return []

    item = NavItem(label=_traduzido(modulo.rotulo), icon=modulo.icone,
                   href=modulo.rota, permission=permissao)
    # Os destinos a mais do módulo entram ao lado dele, cada um com a
    # PRÓPRIA permissão — um módulo pode ter telas de naturezas
    # diferentes sob a mesma raiz (o Catálogo tem: a vitrine é de quem
    # compra, o cadastro é de quem mantém). Sem isto, quem cadastra
    # precisava abrir a tela de quem compra e caçar um botão.
    #
    # Depois do `pode(user, permissao)` acima de propósito: sem a
    # permissão da RAIZ o módulo inteiro some, e o atalho vai junto —
    # senão restaria um destino solto de um módulo que a pessoa não vê.
    atalhos = _atalhos_do_modulo(modulo, user)
    # O grupo do módulo nasce antes dos dos atalhos: assim o assunto
    # principal vem primeiro na barra, e um grupo criado só por atalho
    # (o "Cadastro" do Catálogo) aparece depois dele.
    return [(modulo.grupo, modulo.ordem, item), *atalhos]


def montar(user: "User | None") -> list[NavItem]:
    """Monta o menu lateral para `user`.

    Sem usuário, sem menu — `None` é o visitante que ainda não entrou, e ele
    não vê nem os itens que não exigem permissão nenhuma.

    Um módulo entra no menu pela primeira permissão que ele mesmo declara.
    Um módulo sem nenhuma permissão declarada é público a quem já entrou.

    Grupo que fica sem nenhum filho visível não é desenhado: um grupo vazio
    na barra lateral é pior do que nenhum grupo, porque parece defeito.
    """
    if user is None:
        return []

    grupos: dict[str, list[NavItem]] = {}
    #: `grupo -> (menor ordem entre os seus, quando apareceu)`. A ordem do
    #: grupo é a MENOR dos seus, e não a do primeiro que entrou: um grupo que
    #: reúne módulos de ordens diferentes sobe até o mais alto deles, que é o
    #: que se espera ao mandar um item para cima. O segundo número só desempata
    #: — com todos os módulos na mesma ordem (o estado de fábrica), a barra
    #: continua saindo na ordem de sempre.
    posicao: dict[str, tuple[int, int]] = {}

    for modulo in modulos_ligados():
        for grupo, ordem, entrada in _entradas_do_modulo(modulo, user):
            if grupo not in grupos:
                grupos[grupo] = []
                posicao[grupo] = (ordem, len(posicao))
            else:
                anterior, chegada = posicao[grupo]
                posicao[grupo] = (min(anterior, ordem), chegada)
            grupos[grupo].append(entrada)

    # `icon="folder"`: o primeiro nível do `Sidebar` sempre desenha ícone
    # (contrato do próprio componente — ver `nucleo/templates/layout/sidebar.html`,
    # que chama `icon(item.icon)` incondicionalmente em nível 1), e um grupo
    # não tem ícone próprio declarado em `ModuloSpec`. Sem isto, o primeiro
    # módulo ligado com grupo derrubava a home inteira: `Icon` recusa nome
    # vazio (`icons.get('')` levanta `KeyError`), e isso só aparecia na
    # primeira instalação que ligasse um módulo de verdade — nenhum teste de
    # `montar()` isolado renderiza o HTML do menu para pegar antes.

    # Aqui havia um bloco que criava um grupo "MW5" com as três telas da
    # casa. Ele existia porque elas não estavam no catálogo — e produzia uma
    # barra lateral com a base partida em DOIS grupos por cargo: o que o
    # cliente configura de um lado, o que nós configuramos do outro. São a
    # mesma coisa: o que se ajusta ao instalar um cliente. Hoje as três são
    # módulos declarados (`plataforma/modulo.py`) no grupo Administração, e
    # entram pelo laço acima como qualquer outro — quem separa quem vê o quê
    # continua sendo a permissão, não um grupo à parte na tela.

    itens: list[NavItem] = []
    for grupo in sorted(grupos, key=lambda g: posicao[g]):
        filhos = grupos[grupo]
        # **Grupo com UM destino que já tem o nome dele não é grupo.** O
        # rótulo sairia duas vezes na barra, uma abrindo para a outra, e o
        # degrau não diria nada que o filho já não diga — é o rótulo gasto à
        # toa que o teste do "Catálogo" recusa. O destino sobe inteiro
        # (rótulo, ícone, endereço) e passa a ser ele o item de primeiro
        # nível, que é o pedido do cliente de 23/09/2026 para as Metas:
        # "Metas é um menu de Nível 1 igual Configurações e Gerenciar Fila".
        #
        # Só quando os dois nomes são IGUAIS: o grupo de um filho com outro
        # nome continua sendo grupo, e é ele que separa "Consultas > Frete".
        if len(filhos) == 1 and filhos[0].label == _traduzido(grupo):
            unico = filhos[0]
            itens.append(NavItem(
                label=unico.label,
                # O primeiro nível desenha ícone SEMPRE, e o atalho pode não
                # ter um (no segundo nível ele é opcional). Sem o `or`, o
                # `Icon` recebe nome vazio e a home cai com 500 — o mesmo
                # defeito que o `icon="folder"` do grupo evita.
                icon=unico.icon or _ICONE_DO_PAI,
                href=unico.href,
                badge=unico.badge,
                permission=unico.permission,
                children=unico.children,
            ))
            continue
        itens.append(NavItem(label=_traduzido(grupo), icon="folder",
                             children=filhos))
    return itens
