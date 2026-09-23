"""O menu nasce do cruzamento: módulos ligados × permissão de quem olha.

Ninguém escreve menu. O `nav.py` de 320 linhas escrito à mão do
`sementes-premix` deixa de existir aqui.
"""

import re
import pytest

from nucleo.permissoes import User
from plataforma.declaracao import ModuloSpec, registrar


@pytest.fixture
def catalogo_limpo():
    from plataforma import declaracao

    guardado = declaracao._DECLARADOS.copy()
    declaracao._DECLARADOS.clear()
    yield
    declaracao._DECLARADOS.clear()
    declaracao._DECLARADOS.update(guardado)


@pytest.fixture
def frete_ligado(catalogo_limpo, db):
    from plataforma.catalogo import semear
    from plataforma.models import Modulo

    registrar(ModuloSpec(chave="frete", rotulo="Frete", icone="truck",
                         grupo="Consultas", rota="/frete",
                         permissoes=("frete.ver",)))
    registrar(ModuloSpec(chave="vendas", rotulo="Vendas", icone="chart-bar",
                         grupo="Consultas", rota="/vendas",
                         permissoes=("vendas.ver",)))
    semear()
    Modulo.objects.filter(chave="frete").update(ativo=True)


@pytest.mark.django_db
class TestOMenu:
    def test_modulo_desligado_nao_aparece_nem_para_o_superusuario(self, frete_ligado):
        """Módulo que o cliente não comprou não existe. Nem para a MW5 dentro
        da instalação dele — para ligar, é a tela de Módulos."""
        from plataforma.menu import montar

        raiz = User(id="1", name="MW5", superuser=True)
        rotulos = _todos_os_rotulos(montar(raiz))
        assert "Frete" in rotulos
        assert "Vendas" not in rotulos

    def test_sem_a_permissao_o_item_some(self, frete_ligado):
        from plataforma.menu import montar

        ana = User(id="2", name="Ana", permissions=frozenset())
        assert "Frete" not in _todos_os_rotulos(montar(ana))

    def test_com_a_permissao_o_item_aparece(self, frete_ligado):
        from plataforma.menu import montar

        ana = User(id="2", name="Ana", permissions={"frete.ver"})
        assert "Frete" in _todos_os_rotulos(montar(ana))

    def test_o_coringa_do_modulo_tambem_serve(self, frete_ligado):
        from plataforma.menu import montar

        gestor = User(id="3", name="Bruno", permissions={"frete.*"})
        assert "Frete" in _todos_os_rotulos(montar(gestor))

    def test_sem_usuario_nao_sai_menu(self, frete_ligado):
        from plataforma.menu import montar

        assert montar(None) == []

    def test_os_itens_sao_agrupados_pelo_grupo_declarado(self, frete_ligado):
        from plataforma.menu import montar

        # Usuário COMUM de propósito: o superusuário ganha o grupo MW5 em
        # cima (ver `TestAsTelasDaMw5NoMenu`), e aqui o que se prova é só o
        # agrupamento dos módulos.
        ana = User(id="2", name="Ana", permissions={"frete.ver"})
        topo = montar(ana)
        assert [i.label for i in topo] == ["Consultas"]
        assert [f.label for f in topo[0].children] == ["Frete"]

    def test_o_rotulo_do_banco_vence_o_do_codigo(self, frete_ligado):
        """Cliente pede nome próprio; no código isso viraria exceção por
        cliente, que é o custo que a matriz elimina."""
        from plataforma.menu import montar
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="frete").update(rotulo="Transporte")
        raiz = User(id="1", name="MW5", superuser=True)
        assert "Transporte" in _todos_os_rotulos(montar(raiz))


def _todos_os_rotulos(itens):
    saida = []
    for item in itens:
        saida.append(item.label)
        saida.extend(_todos_os_rotulos(item.children))
    return saida


@pytest.mark.django_db
def test_o_menu_com_grupo_desenha_sem_quebrar(frete_ligado):
    """A regressão que este teste guarda: `montar()` devolvia grupo sem
    ícone, e o `Sidebar` chama `icon(item.icon)` incondicionalmente no
    primeiro nível — `icons.get('')` levanta `KeyError`. A home caía com 500
    na primeira instalação que ligasse um módulo agrupado.

    Os outros testes deste arquivo afirmam sobre a ÁRVORE de `NavItem` e
    nunca desenham. Este desenha: é a diferença entre "a função devolve o que
    eu espero" e "o sistema funciona".
    """
    from nucleo.layout import Sidebar
    from nucleo.rendering import create_environment, use_environment
    from plataforma.menu import montar

    raiz = User(id="1", name="MW5", superuser=True)
    with use_environment(create_environment()):
        html = str(Sidebar(items=montar(raiz)).render())

    assert "Consultas" in html
    assert "Frete" in html


@pytest.fixture
def base_e_frete(catalogo_limpo, db):
    """O catálogo como ele é numa instalação de verdade, no que importa aqui:
    as telas da MW5 declaradas, mais um módulo de negócio ligado.

    As três da MW5 vêm dos specs REAIS (`plataforma/modulo.py`), e não de
    cópias escritas aqui: um teste que redeclarasse "Aparência" passaria mesmo
    que o spec de verdade fosse apagado do código.
    """
    from plataforma.catalogo import semear
    from plataforma.models import Modulo
    from plataforma.modulo import (
        MODULO_APARENCIA, MODULO_FALHAS, MODULO_MODULOS,
    )

    registrar(MODULO_APARENCIA)
    registrar(MODULO_MODULOS)
    registrar(MODULO_FALHAS)
    registrar(ModuloSpec(chave="frete", rotulo="Frete", icone="truck",
                         grupo="Consultas", rota="/frete",
                         permissoes=("frete.ver",)))
    semear()
    Modulo.objects.filter(chave="frete").update(ativo=True)


@pytest.mark.django_db
class TestABaseEUmGrupoSo:
    """A barra lateral tinha DOIS grupos para a mesma coisa.

    "Administração" com o que o cliente configura, "MW5" com o que a MW5
    configura — partido por cargo, não por assunto, sendo que as duas metades
    são o mesmo trabalho: o que se ajusta ao instalar um cliente. E o efeito
    colateral era pior que a feiura: as quatro alavancas que substituem o
    branch por cliente (módulo, permissão, parâmetro, aparência) ficavam
    espalhadas entre os dois menus, e o que o sistema existe para fazer não
    aparecia como UMA coisa em lugar nenhum do produto.

    O grupo "MW5" existia porque as três telas não estavam no catálogo. Hoje
    estão (`plataforma/modulo.py`, com `so_mw5=True`), e entram pelo mesmo
    cruzamento de qualquer módulo.
    """

    def test_nao_existe_mais_um_grupo_chamado_mw5(self, base_e_frete):
        from plataforma.menu import montar

        raiz = User(id="1", name="MW5", superuser=True)
        assert "MW5" not in [i.label for i in montar(raiz)]

    def test_as_tres_telas_moram_na_administracao(self, base_e_frete):
        from plataforma.menu import montar

        raiz = User(id="1", name="MW5", superuser=True)
        topo = {i.label: [f.label for f in i.children] for i in montar(raiz)}
        assert {"Aparência", "Módulos", "Falhas"} <= set(topo["Administração"])

    def test_o_modulo_de_negocio_continua_no_grupo_dele(self, base_e_frete):
        """A base é um grupo; o que o cliente comprou é outro. Um Frete
        ligado no Sementes Premix e desligado na VetPlan é a mesma imagem
        rodando — muda a linha no banco, não o código."""
        from plataforma.menu import montar

        raiz = User(id="1", name="MW5", superuser=True)
        topo = {i.label: [f.label for f in i.children] for i in montar(raiz)}
        assert topo["Consultas"] == ["Frete"]

    def test_quem_nao_e_superusuario_nao_ve_as_tres(self, base_e_frete):
        """Duas trancas, e este teste força a primeira: mesmo com `mw5.*`
        forjado no bolso — o que o banco não permite, porque a permissão não
        existe como linha —, o item não é desenhado."""
        from plataforma.menu import montar

        esperta = User(id="2", name="Ana",
                       permissions=frozenset({"mw5.aparencia", "mw5.modulos",
                                              "mw5.falhas"}))
        rotulos = _todos_os_rotulos(montar(esperta))
        assert "Aparência" not in rotulos
        assert "Módulos" not in rotulos
        assert "Falhas" not in rotulos

    def test_a_permissao_da_mw5_nao_existe_para_conceder(self, base_e_frete):
        """A segunda tranca. `materializar` pula os `so_mw5`, então não há
        `Permission` para marcar num Perfil — a fronteira não depende de
        alguém lembrar de não conceder."""
        from django.contrib.auth.models import Permission

        from contas.permissoes import materializar

        materializar()
        nomes = set(Permission.objects.values_list("codename", flat=True))
        assert not [n for n in nomes
                    if n.startswith(("aparencia_", "modulos_", "falhas_"))]

    def test_a_administracao_desenha_sem_quebrar(self, base_e_frete):
        from nucleo.layout import Sidebar
        from nucleo.rendering import create_environment, use_environment
        from plataforma.menu import montar

        raiz = User(id="1", name="MW5", superuser=True)
        with use_environment(create_environment()):
            html = str(Sidebar(items=montar(raiz)).render())
        assert "Aparência" in html and "Módulos" in html


@pytest.mark.django_db
class TestOsAtalhosDoModulo:
    """Um módulo pode declarar **mais de um destino no menu**.

    O Catálogo tem duas telas de naturezas diferentes na mesma rota-raiz: a
    VITRINE, que o comprador abre para comprar, e o CADASTRO, que o vendedor
    abre para manter o catálogo em pé. Enquanto só a raiz entrava no menu, o
    vendedor precisava passar pela tela de compra e achar um botão para
    chegar ao trabalho dele — todo dia, várias vezes ao dia.

    Isso não é um segundo módulo: seriam duas linhas na tela de Módulos,
    duas permissões a mais e a chance de alguém desligar o cadastro e deixar
    a vitrine sem quem a alimente. É o MESMO módulo com dois destinos, cada
    um com a permissão que já existe — e a permissão continua sendo quem
    decide quem enxerga o quê.
    """

    @pytest.fixture
    def com_atalho(self, catalogo_limpo, db):
        from plataforma.catalogo import semear
        from plataforma.declaracao import Atalho
        from plataforma.models import Modulo

        registrar(ModuloSpec(
            chave="frete", rotulo="Frete", icone="truck", grupo="Consultas",
            rota="/frete", permissoes=("frete.ver", "frete.editar"),
            atalhos=(Atalho(rotulo="Tabelas", rota="/frete/tabelas",
                            permissao="frete.editar"),)))
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)

    def _rotas(self, user):
        from plataforma.menu import montar

        saida = []
        for grupo in montar(user):
            saida.extend(i.href for i in (grupo.children or [grupo]))
        return saida

    def test_quem_tem_a_permissao_do_atalho_ve_os_dois_destinos(self, com_atalho):
        quem = User(id=1, name="Vera", login="vera",
                    permissions=["frete.ver", "frete.editar"])
        assert self._rotas(quem) == ["/frete", "/frete/tabelas"]

    def test_quem_so_ve_o_modulo_nao_ve_o_atalho(self, com_atalho):
        """A permissão do atalho é dele, não do módulo: o comprador entra na
        vitrine e o cadastro não existe para ele — nem como item apagado."""
        quem = User(id=2, name="João", login="joao", permissions=["frete.ver"])
        assert self._rotas(quem) == ["/frete"]

    def test_sem_a_permissao_do_modulo_nao_sobra_nem_o_atalho(self, com_atalho):
        """Sem a permissão da RAIZ o módulo inteiro some — e o atalho vai
        junto, senão restaria um destino solto de um módulo invisível."""
        quem = User(id=3, name="Zé", login="ze", permissions=["frete.editar"])
        assert self._rotas(quem) == []


@pytest.mark.django_db
def test_nenhum_grupo_repete_o_nome_de_um_filho(db):
    """Grupo com o nome de um dos filhos é rótulo gasto à toa.

    Aconteceu: o grupo se chamava "Catálogo" e continha "Catálogo",
    "Cadastro" e "Orçamentos" — o primeiro nível repetindo o segundo, e o
    nome do grupo dizendo o assunto de UM filho em vez do que une os três.
    A pessoa lia "Catálogo" duas vezes e ainda ficava sem saber por que
    orçamento morava lá dentro.
    """
    from plataforma.catalogo import semear
    from plataforma.menu import montar

    semear()
    onividente = User(id=1, name="MW5", login="mw5", superuser=True,
                      permissions=["*"])
    repetidos = [
        f"{grupo.label} > {filho.label}"
        for grupo in montar(onividente)
        for filho in (grupo.children or [])
        if filho.label == grupo.label
    ]
    assert repetidos == [], f"grupo repetindo filho: {repetidos}"


@pytest.mark.django_db
def test_grupo_de_um_filho_com_o_nome_dele_sobe_para_o_primeiro_nivel(
        catalogo_limpo, db):
    """Grupo que só tem o destino com o nome dele mesmo não é grupo.

    O cliente pediu "Metas" como menu de PRIMEIRO nível (23/09/2026), e neste
    menu um destino só chega ao primeiro nível por um grupo: o degrau diria
    "Metas" e abriria para "Metas" — o rótulo gasto à toa que o teste acima já
    recusa, e um clique a mais para chegar na tela. O `montar` então desfaz o
    degrau quando os dois nomes são iguais, e o destino sobe inteiro.

    O grupo de um filho com OUTRO nome continua grupo: é ele que separa
    "Consultas > Frete", e o teste `test_os_itens_sao_agrupados_pelo_grupo_
    declarado` cobra.
    """
    from nucleo.layout import Sidebar
    from nucleo.rendering import create_environment, use_environment
    from plataforma.catalogo import semear
    from plataforma.declaracao import Atalho
    from plataforma.menu import montar
    from plataforma.models import Modulo

    registrar(ModuloSpec(
        chave="frete", rotulo="Frete", icone="truck", grupo="Consultas",
        rota="/frete", permissoes=("frete.ver",),
        atalhos=(Atalho(rotulo="Tabelas", rota="/frete/tabelas",
                        permissao="frete.ver", grupo="Tabelas"),)))
    semear()
    Modulo.objects.filter(chave="frete").update(ativo=True)

    quem = User(id="2", name="Ana", permissions={"frete.ver"})
    topo = {i.label: i for i in montar(quem)}
    assert topo["Tabelas"].href == "/frete/tabelas"
    assert not topo["Tabelas"].children
    assert [f.label for f in topo["Consultas"].children] == ["Frete"]

    # E desenha: o primeiro nível desenha ícone em TODO item, e o atalho não
    # tem um (no segundo nível ele é opcional). Sem a pasta de reserva, o
    # `Icon` recebe nome vazio — `icons.get('')` levanta `KeyError`, e a home
    # cai com 500.
    with use_environment(create_environment()):
        html = str(Sidebar(items=montar(quem)).render())
    assert "/frete/tabelas" in html


@pytest.mark.django_db
class TestOAtalhoEmOutroGrupo:
    """Um atalho pode morar num grupo diferente do módulo.

    O Catálogo é um módulo só, mas as duas telas dele são de ATIVIDADES
    diferentes: `/catalogo` é onde se compra, `/catalogo/produtos` é onde se
    mantém o catálogo em pé. Quem cadastra e quem compra abrem o sistema com
    intenções diferentes, e o menu deve refletir a intenção — não a árvore
    de rotas, que é detalhe de implementação.

    Continua sendo um módulo só: liga e desliga junto, permissão a mesma. O
    que muda é onde cada destino aparece.
    """

    @pytest.fixture
    def dois_grupos(self, catalogo_limpo, db):
        from plataforma.catalogo import semear
        from plataforma.declaracao import Atalho
        from plataforma.models import Modulo

        registrar(ModuloSpec(
            chave="frete", rotulo="Frete", icone="truck", grupo="Consultas",
            rota="/frete", permissoes=("frete.ver", "frete.editar"),
            atalhos=(Atalho(rotulo="Tabelas", rota="/frete/tabelas",
                            permissao="frete.editar", grupo="Cadastro"),)))
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)

    def _arvore(self, user):
        from plataforma.menu import montar

        return {g.label: [f.href for f in (g.children or [])]
                for g in montar(user)}

    def test_o_atalho_vai_para_o_grupo_que_ele_declara(self, dois_grupos):
        quem = User(id=1, name="Vera", login="vera",
                    permissions=["frete.ver", "frete.editar"])
        assert self._arvore(quem) == {"Consultas": ["/frete"],
                                      "Cadastro": ["/frete/tabelas"]}

    def test_grupo_do_atalho_nao_nasce_vazio_para_quem_nao_alcanca(
            self, dois_grupos):
        """Sem a permissão do atalho o grupo dele não é desenhado — grupo
        vazio na barra parece defeito, e é a mesma regra que já vale para
        módulo sem filho visível."""
        quem = User(id=2, name="João", login="joao", permissions=["frete.ver"])
        assert self._arvore(quem) == {"Consultas": ["/frete"]}


@pytest.mark.django_db
class TestAOrdemDosGrupos:
    """A ordem dos grupos é DECLARADA, não é efeito de quem apareceu antes.

    Enquanto ela saía da ordem de aparição, o grupo criado por um atalho vinha
    obrigatoriamente depois do grupo do módulo que o declarou — e no Catálogo
    isso punha "Vendas" acima de "Cadastro", contra a ordem em que o trabalho
    acontece: cadastra-se o produto para depois vendê-lo.

    O grupo assume a MENOR ordem entre os seus, e não a do primeiro que
    entrou: um grupo que reúne módulos de ordens diferentes sobe até o mais
    alto deles, que é o que a pessoa espera ao mandar um item para cima.
    """

    @pytest.fixture
    def com_ordem(self, catalogo_limpo, db):
        from plataforma.catalogo import semear
        from plataforma.declaracao import Atalho
        from plataforma.models import Modulo

        registrar(ModuloSpec(
            chave="frete", rotulo="Frete", icone="truck", grupo="Consultas",
            rota="/frete", permissoes=("frete.ver", "frete.editar"),
            atalhos=(Atalho(rotulo="Tabelas", rota="/frete/tabelas",
                            permissao="frete.editar", grupo="Cadastro",
                            ordem=-1),)))
        semear()
        Modulo.objects.filter(chave="frete").update(ativo=True)

    def test_o_atalho_pode_puxar_o_grupo_dele_para_cima(self, com_ordem):
        from plataforma.menu import montar

        quem = User(id=1, name="Vera", login="vera",
                    permissions=["frete.ver", "frete.editar"])
        assert [g.label for g in montar(quem)] == ["Cadastro", "Consultas"]

    def test_sem_a_permissao_do_atalho_o_grupo_dele_nao_desloca_nada(
            self, com_ordem):
        from plataforma.menu import montar

        quem = User(id=2, name="João", login="joao", permissions=["frete.ver"])
        assert [g.label for g in montar(quem)] == ["Consultas"]


@pytest.mark.django_db
def test_administracao_abre_a_barra(db):
    """A Administração é o PRIMEIRO grupo, e os de trabalho vêm depois dela.

    Ela já esteve no fim, com o argumento de que configuração não é trabalho
    do dia. Decisão revista: neste produto se entra por ela — empresa,
    usuários, perfis, parâmetros — e um grupo que se abre todo dia não pode
    ser o último da lista.

    O que este teste guarda não é a posição em si, é ela ser DECLARADA:
    antes de existir `ordem`, o topo saía do desempate por chave em ordem
    alfabética ("aparencia" antes de "catalogo") — o resto de uma conta, que
    ninguém tinha decidido e que mudava sozinho ao renomear um módulo.
    """
    from plataforma.catalogo import semear
    from plataforma.menu import montar

    semear()
    mw5 = User(id=1, name="MW5", login="mw5", superuser=True,
               permissions=["*"])
    grupos = [g.label for g in montar(mw5)]
    assert grupos[0] == "Administração", grupos
    # "Configuração" desde 23/09/2026: era "Cadastro" (ver
    # `plataforma/modulo.py`, no `MODULO_CONTA`).
    assert grupos.index("Configuração") > 0


@pytest.mark.django_db
def test_o_cadastro_reune_empresa_usuarios_e_produtos(db):
    """Os três são DADO DO CLIENTE, e por isso moram juntos.

    Usuários e Empresa estavam na Administração, ao lado de Aparência,
    Módulos e Falhas — que configuram a INSTALAÇÃO e se mexem uma vez por
    ano. Cadastrar gente e cadastrar a empresa é trabalho do dia de quem
    administra um cliente, e a barra passou a dizer isso.

    **Filiais e Cargos vieram depois** (14/09/2026, pedido do João: "tudo que
    for cadastro fica no menu Cadastro", que desde 23/09/2026 se chama
    Configuração). Os dois são cadastro do cliente — as
    unidades da empresa e os cargos da conta. Filiais estava na Administração
    por herança do KRONOS.net, onde a instalação era de UM cliente e cadastro
    de filial era configuração.
    """
    from plataforma.catalogo import semear
    from plataforma.menu import montar
    from plataforma.models import Modulo

    semear()
    # Filiais nasce desligado neste produto; ligado aqui porque a pergunta é
    # EM QUE GRUPO ele aparece, e desligado ele não aparece em grupo nenhum —
    # o teste passaria sem provar nada.
    Modulo.objects.filter(chave="filiais").update(ativo=True)
    mw5 = User(id=1, name="MW5", login="mw5", superuser=True,
               permissions=["*"])
    grupos = {g.label: [f.label for f in (g.children or [])]
              for g in montar(mw5)}
    # "Empresas" no PLURAL desde 17/09/2026: a conta tem várias, e a tela é
    # a lista delas. "Conta" é o topo da hierarquia (conta -> empresas ->
    # lojas), e por isso vem antes.
    assert {"Conta", "Empresas", "Usuários", "Filiais", "Cargos"} <= \
        set(grupos["Configuração"])
    for cadastro in ("Usuários", "Empresas", "Filiais", "Cargos"):
        assert cadastro not in grupos.get("Administração", []), cadastro
    # O que sobra na Administração é o que configura a instalação.
    assert {"Aparência", "Módulos", "Falhas"} <= set(grupos["Administração"])


@pytest.mark.django_db
def test_o_cadastro_nao_empata_com_a_administracao_no_topo(db):
    """A armadilha desta mudança, e o motivo da migração que a acompanha.

    O grupo assume a MENOR ordem entre os seus. Usuários e Empresa vinham com
    `-100`, a ordem da Administração — mudar só o grupo faria o Cadastro
    herdar essa ordem e empatar no topo, com o desempate caindo na ordem de
    chegada, que é ordem de leitura do código e não interessa a quem usa.

    **Afirma o NÚMERO, e não a posição na barra.** A primeira versão deste
    teste olhava `grupos.index("Cadastro") == 1` e passava verde com a
    migração desligada: empatados em `-100`, o desempate por chave punha
    "aparencia" na frente e a Administração vinha em primeiro do mesmo jeito —
    pelo motivo errado. O empate é o defeito, e é ele que precisa aparecer.
    """
    from plataforma.catalogo import semear
    from plataforma.models import Modulo

    semear()
    ordens = dict(Modulo.objects.values_list("chave", "ordem"))
    do_cadastro = min(ordens["usuarios"], ordens["empresa"])
    da_administracao = min(ordens["aparencia"], ordens["modulos"],
                           ordens["falhas"])
    assert da_administracao < do_cadastro, (
        f"Administração em {da_administracao} e Configuração em {do_cadastro}: "
        "empatados, quem vem primeiro passa a ser a ordem de leitura do "
        "código")


@pytest.mark.django_db
def test_a_linha_semeada_nasce_na_ordem_que_o_codigo_declara(db):
    """**Era um teste sobre a migração `0016`, e ela deixou de existir.**

    Aquela migração movia `usuarios` e `empresa` de `-100` para `-1` em quem
    JÁ estava instalado — o caso que a suíte não cobria, porque o banco de
    teste sempre nasceu do zero. Quando o `AUTH_USER_MODEL` passou a ser
    nosso, todas as migrações foram refeitas do zero, e com elas foi embora o
    histórico inteiro: não existe mais instalação anterior a esta, e portanto
    não existe mais o caso que aquela migração corrigia.

    O que continua precisando de prova é a outra metade, e ela é a que
    sobrevive: numa instalação NOVA, quem decide a ordem da linha é
    `ModuloSpec.ordem` do código, lido por `semear` **uma vez**, na criação.
    Depois disso quem manda é o banco (é o que deixa a tela de Módulos
    reordenar) — e é justamente por isso que o número do código precisa estar
    certo no nascimento: errado ali, ele fica errado para sempre naquela
    instalação.
    """
    from plataforma.catalogo import semear
    from plataforma.models import Modulo

    Modulo.objects.filter(chave__in=("usuarios", "empresa")).delete()
    semear()

    ordens = dict(Modulo.objects.filter(
        chave__in=("usuarios", "empresa")).values_list("chave", "ordem"))
    # -4 e -2 desde 14/09/2026: Empresa, Filiais, Usuários, Cargos na ordem do
    # trabalho do titular (ver `test_o_cadastro_segue_a_ordem_do_trabalho`).
    assert ordens == {"usuarios": -2, "empresa": -4}, ordens

    # E não mexe em quem alguém reordenou pela tela: decisão de cliente não se
    # desfaz numa atualização. `semear` só CRIA o que falta.
    Modulo.objects.filter(chave="usuarios").update(ordem=42)
    semear()
    assert Modulo.objects.get(chave="usuarios").ordem == 42


@pytest.mark.django_db
class TestOMenuMarcaOndeAPessoaEsta:
    """O `path` da requisição chega ao `Sidebar`, e é ele que destaca.

    **Nenhuma tela desta casa o passava.** O design system recebe `path` com
    padrão `/`, e o resultado era a barra lateral sem nada destacado, em toda
    tela, desde sempre — o tipo de defeito que não parece defeito: parece um
    menu que simplesmente não destaca.

    Só apareceu quando o cadastro do catálogo virou submenu (10/09/2026): aí a
    barra passou a nascer FECHADA em cima da tela onde a pessoa está, e a
    pessoa perde o caminho que a trouxe até ali.
    """

    @pytest.fixture
    def vendedor(self, db):
        from django.contrib.auth.models import Permission
        from django.test import Client
        from django.urls import reverse

        from contas.models import Nivel, Usuario
        from plataforma.models import Empresa
        from tests.conftest import por_na_conta

        senha = "segredo-de-teste"
        pessoa = Usuario.objects.create_user(
            email="vera@teste.com", password=senha, nivel=Nivel.TITULAR)
        from contas.fabrica import aplicar

        aplicar(pessoa, Nivel.TITULAR)
        Empresa.objects.create(razao_social="Normadin", dono=pessoa)
        cliente = Client()
        cliente.post(reverse("entrar"),
                     {"usuario": "vera@teste.com", "senha": senha})
        return cliente

    def _barra(self, cliente, rota):
        from django.urls import reverse

        html = cliente.get(reverse(rota)).content.decode()
        return html[html.index("side-nav"):html.index("side-foot")]

    def test_a_tela_aberta_vem_destacada(self, vendedor):
        barra = self._barra(vendedor, "usuarios")

        assert re.search(r'href="/usuarios"[^>]*aria-current="page"', barra)

    def test_a_tela_de_outro_assunto_nao_destaca_nada(self, vendedor):
        barra = self._barra(vendedor, "perfil")

        assert 'aria-current="page"' not in barra


@pytest.mark.django_db
def test_o_cadastro_segue_a_ordem_do_trabalho(db):
    """Conta, Empresas, Filiais, Usuários, Cargos — e os cadastros de negócio
    depois.

    É a ordem em que o titular trabalha (14/09/2026, pedido do João): recebe a
    empresa no cadastro inicial, cadastra as filiais (que já vêm com a Matriz),
    e depois as pessoas que pertencem a ela. A Conta entrou no topo em
    17/09/2026, porque é ela que contém as empresas. Alfabética, a barra poria
    Filiais antes de Empresas e Cargos antes de Usuários por acaso de letra.
    """
    from plataforma.catalogo import semear
    from plataforma.menu import montar
    from plataforma.models import Modulo

    semear()
    Modulo.objects.filter(chave="filiais").update(ativo=True)
    mw5 = User(id=1, name="MW5", login="mw5", superuser=True,
               permissions=["*"])
    grupos = {g.label: [f.label for f in (g.children or [])]
              for g in montar(mw5)}

    cadastro = grupos["Configuração"]
    ordem = [cadastro.index(nome) for nome in
             ("Conta", "Empresas", "Filiais", "Usuários", "Cargos")]
    assert ordem == sorted(ordem), cadastro
    # E o grupo continua no lugar: Administração primeiro.
    rotulos = [g.label for g in montar(mw5)]
    assert rotulos[0] == "Administração"


