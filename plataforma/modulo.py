"""O que os módulos de Empresa e Filiais dizem sobre si.

Moram em `plataforma/`, e não em `contas/`, pelo mesmo critério que já separa
os dois pacotes: `contas` é sobre gente (quem entra, em que perfil); estes
dois são sobre a instalação em si — a empresa que ela é, as unidades que ela
tem —, o mesmo assunto de `plataforma.models.Empresa`/`Filial` e de
`plataforma.contexto`. Só a declaração mora aqui — quem registra é
`apps.PlataformaConfig.ready()`, pelo mesmo motivo do comentário em
`contas/apps.py`: registrar no corpo do módulo dependeria da ordem de import
entre apps.
"""

from __future__ import annotations

from plataforma.declaracao import ModuloSpec
from django.utils.translation import gettext_lazy as _

#: "Eu sou a Empresa. Meu ícone é o cartão. Eu moro no grupo Administração.
#: Minha rota é /empresa. Eu crio a permissão empresa.editar."
#:
#: `ativo_por_padrao=True`: pelo mesmo motivo de `MODULO_USUARIOS`
#: (`contas/modulo.py`) — uma instalação nova não pode nascer com a própria
#: tela de Empresa inalcançável até a MW5 lembrar de ligar a chavinha.
#:
#: **O motivo mudou em 09/09/2026.** Ele era "a empresa já vem semeada, então
#: a tela precisa existir para editá-la". A semeadura acabou (ver
#: `plataforma/apps.py`), e agora a razão é a inversa e mais forte: uma
#: instalação nova sobe com ZERO empresas, e a primeira aparece quando a MW5
#: cadastra o primeiro titular. É ela quem precisa da tela ligada desde o
#: primeiro dia para ver o que criou.
MODULO_EMPRESA = ModuloSpec(
    chave="empresa",
    #: **"Empresa", no singular — e a terceira vez que este rótulo muda.**
    #:
    #: Ele era singular quando a instalação era de UM cliente e a tela editava
    #: uma linha só. Virou plural quando o portal passou a atender várias e a
    #: tela virou lista, porque era o único item da barra que discordava da
    #: tela para onde aponta.
    #:
    #: Agora volta ao singular por um motivo diferente dos dois: **uma conta
    #: tem UMA empresa**. Para o titular — que é quase todo mundo que abre
    #: este menu — a tela é o cadastro da empresa dele, e não uma lista.
    #:
    #: A MW5 continua vendo várias, e para ela o plural continuaria certo.
    #: Um rótulo por nível seria mecanismo novo no menu para resolver uma
    #: palavra, e o singular é o que vale para quem mais lê.
    rotulo=_("Empresa"),
    icone="card",
    #: **Cadastro, e não Administração** — o par de `usuarios`, e pelo mesmo
#: motivo: o cadastro da empresa é dado do cliente, como o produto e a
#: gente dele. O que fica na Administração é o que configura a
#: INSTALAÇÃO: parâmetros, aparência, módulos e falhas.
    grupo="Cadastro",
    # A ordem DENTRO do Cadastro é a do trabalho do titular (14/09/2026):
    # Empresa (-4), Filiais (-3), Usuários (-2), Perfis (-1) — e o Catálogo,
    # que vem do módulo de vendas, depois. Empatadas, o desempate seria a
    # ordem alfabética da chave, que não é ordem de ninguém. Todas negativas e
    # maiores que -100: o grupo continua abaixo da Administração e acima de
    # Vendas. Instalações existentes: `plataforma/0007`.
    ordem=-4,
    rota="/empresa",
    permissoes=("empresa.editar",),
    ativo_por_padrao=True,
)

#: "Eu sou as Filiais. Meu ícone é a grade. Eu moro no grupo Cadastro.
#: Minha rota é /filiais. Eu crio a permissão filiais.editar."
#:
#: **No grupo Cadastro desde 14/09/2026** (pedido do João: "tudo que for
#: cadastro fica no menu Cadastro"). Estava na Administração por herança do
#: KRONOS.net, onde a instalação era de UM cliente e filial era configuração
#: dela; aqui filial é cadastro do cliente, ao lado da empresa a que pertence.
#: `ordem=-3`: depois de Empresa e antes de Usuários — o titular cadastra as
#: filiais da empresa antes das pessoas. Com `-100` o grupo inteiro subiria
#: para antes da Administração.
#:
#: `ativo_por_padrao=False` — e a "Matriz" deixou de ser semeada junto com a
#: empresa em 09/09/2026, então o comentário abaixo descreve um mundo que não
#: existe mais. Fica registrado porque explica por que a chave já esteve
#: ligada: a "Matriz"
#: já nasce semeada (`plataforma.empresa.garantir_matriz`), e sem esta tela
#: ligada desde o primeiro dia ninguém teria como cadastrar uma segunda
#: filial nem escolher quem trabalha em cada uma.
#: `ativo_por_padrao=False` NESTE PRODUTO — no KRONOS.net é `True`.
#:
#: Aqui a empresa é o cadastro de clientes e é ela que se escolhe no
#: cabeçalho. O model
#: e a FK `Filial.empresa` continuam de pé, e a Matriz continua sendo
#: semeada: no dia em que filial fizer sentido, é uma chavinha na tela de
#: Módulos — não uma migração para trazer de volta uma tabela apagada, com o
#: dado de quem já usava perdido no caminho.
MODULO_FILIAIS = ModuloSpec(
    chave="filiais",
    rotulo=_("Filiais"),
    icone="grid",
    grupo="Cadastro",
    ordem=-3,
    rota="/filiais",
    permissoes=("filiais.editar",),
    ativo_por_padrao=False,
)

#: "Eu sou os Parâmetros. Meu ícone é a engrenagem. Eu moro no grupo
#: Administração. Minha rota é /parametros. Eu crio a permissão
#: parametros.editar."
#:
#: `ativo_por_padrao=True` pelo mesmo motivo de `MODULO_EMPRESA` e
#: `MODULO_FILIAIS`: é a tela que resolve "este cliente é diferente" sem
#: código novo (R47) — uma instalação nova não pode nascer sem ela até a
#: MW5 lembrar de ligar a chavinha.
MODULO_PARAMETROS = ModuloSpec(
    chave="parametros",
    rotulo=_("Parâmetros"),
    icone="settings",
    grupo="Administração",
    ordem=-100,
    rota="/parametros",
    permissoes=("parametros.editar",),
    ativo_por_padrao=True,
)


# ---------------------------------------------------------------------------
# As três telas da MW5.
#
# Elas ficavam FORA do catálogo, e por isso fora do cruzamento
# `módulos ligados × permissão` que desenha o menu. Para aparecerem, o
# `menu.py` tinha um bloco à parte que criava um grupo "MW5" na barra
# lateral — e aí a base ficava partida em dois grupos por CARGO, não por
# assunto: "Administração" para o que o cliente configura, "MW5" para o que
# nós configuramos, sendo que as duas coisas são a mesma — o que se ajusta ao
# instalar um cliente.
#
# Declaradas aqui, entram pelo mesmo caminho de todo módulo. `so_mw5=True`
# guarda a fronteira (ver `ModuloSpec.so_mw5`): a permissão não vira linha no
# banco, então não há o que conceder num cargo.
# ---------------------------------------------------------------------------

#: "Eu sou a Aparência. Meu ícone é a paleta. Eu moro no grupo Administração.
#: Minha rota é /mw5/aparencia. Eu exijo mw5.aparencia."
#:
#: A permissão continua sendo `mw5.aparencia`, e não `aparencia.editar`: é a
#: guarda que a rota já usa, e trocá-la abriria a marca da instalação para
#: quem receber o perfil certo. Aqui só o LUGAR mudou — de um bloco solto no
#: menu para o catálogo.
MODULO_APARENCIA = ModuloSpec(
    chave="aparencia",
    rotulo=_("Aparência"),
    icone="palette",
    grupo="Administração",
    ordem=-100,
    rota="/mw5/aparencia",
    permissoes=("mw5.aparencia",),
    ativo_por_padrao=True,
    so_mw5=True,
)

#: "Eu sou o Módulos. Meu ícone é a chavinha. Eu moro no grupo Administração.
#: Minha rota é /mw5/modulos. Eu exijo mw5.modulos."
#:
#: É a tela que liga e desliga os outros — e é justamente por isso que ela
#: não pode aparecer na própria lista: desligá-la tiraria o meio de religar
#: qualquer coisa. `so_mw5` já cuida disso.
MODULO_MODULOS = ModuloSpec(
    chave="modulos",
    rotulo=_("Módulos"),
    icone="toggle-left",
    grupo="Administração",
    ordem=-100,
    rota="/mw5/modulos",
    permissoes=("mw5.modulos",),
    ativo_por_padrao=True,
    so_mw5=True,
)

#: "Eu sou as Falhas. Meu ícone é o inseto. Eu moro no grupo Administração.
#: Minha rota é /mw5/falhas. Eu exijo mw5.falhas."
#:
#: Erro em produção é assunto de quem mantém, não de quem usa: a tela mostra
#: rastro de exceção, e rastro conta caminho de arquivo e nome de função.
MODULO_FALHAS = ModuloSpec(
    chave="falhas",
    rotulo=_("Falhas"),
    icone="bug",
    grupo="Administração",
    ordem=-100,
    rota="/mw5/falhas",
    permissoes=("mw5.falhas",),
    ativo_por_padrao=True,
    so_mw5=True,
)
