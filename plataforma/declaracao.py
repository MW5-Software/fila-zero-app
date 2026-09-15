"""O que um módulo diz sobre si.

Um módulo **declara**; ele não registra rota, não escreve menu e não cria
permissão. Quem faz isso é a plataforma, lendo esta declaração. É o que faz
um módulo novo aparecer sozinho nas vinte instalações.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["ModuloSpec", "declarados", "registrar"]


@dataclass(frozen=True)
class Atalho:
    """Um destino a mais do mesmo módulo, no menu, com permissão própria.

    Existe porque um módulo pode ter telas de NATUREZAS diferentes sob a
    mesma raiz. O Catálogo é o caso: a vitrine é onde se compra, o cadastro é
    onde se mantém o catálogo em pé — mesmo assunto, gente diferente. Sem
    isto, quem cadastra precisava abrir a tela de quem compra e caçar um
    botão, todo dia.

    Não é um segundo `ModuloSpec` de propósito: seriam duas linhas na tela de
    Módulos, uma permissão a mais, e a chance de alguém desligar o cadastro
    deixando a vitrine sem quem a alimente. Ligar e desligar continua sendo
    por MÓDULO; quem separa quem vê o quê continua sendo a permissão.
    """

    rotulo: str
    rota: str
    permissao: str
    #: O ícone é opcional: no segundo nível o `Sidebar` não exige um, e um
    #: ícone por destino dentro do mesmo assunto vira ruído.
    icone: str = ""
    #: Onde este destino fica na barra. `None` é a mesma posição do módulo.
    #:
    #: Serve para o grupo criado por um atalho não ficar preso ATRÁS do
    #: módulo que o declarou. No Catálogo é o caso: quem declara o cadastro
    #: é o módulo do catálogo, mas cadastra-se o produto para depois
    #: vendê-lo — e a barra tem de sair na ordem em que o trabalho acontece,
    #: não na ordem em que o código foi lido.
    ordem: "int | None" = None
    #: Em que grupo do menu este destino aparece. Vazio é o do módulo.
    #:
    #: Existe porque as duas telas de um módulo podem ser de ATIVIDADES
    #: diferentes. No Catálogo são: `/catalogo` é onde se compra,
    #: `/catalogo/produtos` é onde se mantém o catálogo em pé. Quem abre o
    #: sistema para cadastrar e quem abre para comprar chegam com intenções
    #: diferentes, e o menu tem de refletir a INTENÇÃO — não a árvore de
    #: rotas, que é detalhe de implementação e não interessa a ninguém do
    #: lado de fora.
    #:
    #: Continua sendo um módulo só: liga e desliga junto, permissão a mesma.
    #: O que muda é onde cada destino aparece.
    grupo: str = ""

    #: O item de SEGUNDO nível que abre e mostra este destino dentro dele.
    #: Vazio deixa o atalho solto no grupo, como sempre foi.
    #:
    #: Existe desde 10/09/2026, quando o cadastro do catálogo deixou de ser
    #: uma tela de abas e virou cinco telas — Segmentos, Linhas, Famílias,
    #: Marcas e Produtos. Cinco itens soltos na barra esconderiam a relação
    #: entre eles (quem abre "Marcas" não veria que marca existe por causa de
    #: equivalência), e era esse o argumento das abas. Como submenu, a
    #: hierarquia continua visível e cada tela ganha endereço próprio.
    #:
    #: É RÓTULO e não chave: o pai não é um destino, não tem rota nem
    #: permissão própria — ele existe só para abrir. Atalhos com o mesmo
    #: `pai` no mesmo grupo caem no mesmo submenu, na ordem em que forem
    #: declarados.
    pai: str = ""


@dataclass(frozen=True)
class ModuloSpec:
    """A apresentação de um módulo, em português claro.

    "Eu sou o Frete. Meu ícone é o caminhão. Eu moro no grupo Consultas. Minha
    rota é /frete. Eu crio as permissões frete.ver e frete.editar."
    """

    chave: str
    rotulo: str
    icone: str = ""
    grupo: str = "Geral"
    rota: str = ""
    permissoes: tuple[str, ...] = field(default_factory=tuple)
    #: Destinos a mais deste módulo no menu — ver `Atalho`. Vazio é o normal:
    #: quase todo módulo é uma tela só.
    atalhos: tuple["Atalho", ...] = field(default_factory=tuple)
    #: A posição de nascença na barra. Só vale quando a linha é CRIADA
    #: (`semear`); depois disso quem manda é o banco, que a tela de Módulos
    #: edita — a mesma regra de rótulo e grupo.
    #:
    #: Existe porque a ordem de fábrica era acidental: todo módulo nascia em
    #: zero e o desempate virava a chave em ordem alfabética, o que punha
    #: "Aparência" no topo da barra de todo mundo. Ninguém decidiu isso; era
    #: o resto de uma conta.
    #:
    #: Hoje a barra sai assim: **Administração** (`-100`), depois Cadastro
    #: (`-1`) e Vendas (`0`). A Administração já esteve no fim, com o
    #: argumento de que configuração não é trabalho do dia — decisão
    #: revista: quem usa este produto entra por ela, e um grupo que se abre
    #: todo dia não pode ser o último da lista. Número negativo e não uma
    #: reordenação de todos: assim um módulo de negócio novo continua
    #: nascendo em zero, sem precisar saber que existe uma escada.
    ordem: int = 0
    #: Se `semear` deve criar a linha faltante já ligada. Regra geral é
    #: `False`: módulo de negócio é o que o cliente comprou, e não vem junto
    #: da instalação sem a MW5 decidir. A exceção é um módulo da própria
    #: plataforma sem o qual a instalação nasce manca — ver `contas/modulo.py`.
    ativo_por_padrao: bool = False

    #: Se a tela é decisão de DENTRO da MW5, e não do cliente.
    #:
    #: Existe porque, sem ele, as telas da MW5 não cabiam no catálogo e
    #: precisavam de um bloco à parte no menu — e esse bloco virava um
    #: segundo grupo na barra lateral, partindo a base em duas por CARGO em
    #: vez de por assunto. Com ele, elas entram pelo mesmo cruzamento que
    #: todo módulo usa, e a fronteira continua de pé por outro caminho:
    #:
    #: - a permissão **não é materializada** (`contas/permissoes.py`): sem
    #:   linha no banco não há o que marcar num cargo, e só superusuário
    #:   passa. É a mesma garantia de antes, agora declarada em vez de
    #:   depender de a chave `mw5` não existir por acaso;
    #: - o módulo **não aparece na tela de Módulos**: não é algo que o
    #:   cliente compra, e desligar a própria tela de Módulos tiraria o meio
    #:   de religá-la.
    so_mw5: bool = False

    def __post_init__(self) -> None:
        if not self.chave.strip():
            raise ValueError("módulo sem chave")
        if not self.rotulo.strip():
            raise ValueError(f"módulo {self.chave!r} sem rótulo")
        if "_" in self.chave:
            raise ValueError(
                f"a chave {self.chave!r} tem sublinhado, e isso quebraria a "
                f"permissão do módulo: ela se escreve `{self.chave}_acao` no "
                f"banco e é cortada no primeiro sublinhado, então "
                f"`{self.chave}_ver` viraria "
                f"`{self.chave.split('_')[0]}.{self.chave.split('_', 1)[1]}_ver`. "
                f"Use hífen: `{self.chave.replace('_', '-')}`."
            )


#: O que o código declarou. Preenchido quando cada `modulo.py` é importado.
_DECLARADOS: dict[str, ModuloSpec] = {}


def registrar(spec: ModuloSpec) -> None:
    """Põe um módulo no catálogo do código.

    Chave repetida quebra na subida, de propósito: duas pastas com a mesma
    chave dariam item de menu duplicado e permissão ambígua, e descobrir isso
    em produção é bem pior.
    """
    if spec.chave in _DECLARADOS:
        raise ValueError(f"o módulo {spec.chave!r} já foi declarado")
    _DECLARADOS[spec.chave] = spec


def declarados() -> tuple[ModuloSpec, ...]:
    """Todos os módulos que existem no código, em ordem de chave."""
    return tuple(_DECLARADOS[c] for c in sorted(_DECLARADOS))
