"""Quem está logado, e o que essa pessoa pode.

`User` é deliberadamente pobre: um retrato do usuário para a requisição atual,
não a linha do banco. É o que permite ao `AuthBackend` de um cliente devolver
gente vinda de LDAP, de um ERP legado ou de uma tabela nossa sem que nada
acima precise saber a diferença.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["NivelDeContexto", "OpcaoDeContexto", "SENHA_MINIMA", "User", "pode"]

#: O tamanho mínimo de uma senha. Mora aqui, e não em `contas/`, porque a tela
#: de perfil (`layout.PerfilPage`) precisa dele para escrever a dica ao lado do
#: campo — e o layout não pode depender de um app que ainda nem existe.
SENHA_MINIMA = 8


@dataclass
class OpcaoDeContexto:
    """Uma empresa ou uma filial que a pessoa pode escolher."""

    valor: str
    rotulo: str


@dataclass
class NivelDeContexto:
    """Um nível do contexto — empresa, filial — do jeito que o backend o vê.

    Vive aqui, junto de `User`, e não em `kronos.py`: é o formato que
    `ContextoDoUsuario` (em `backend.py`) usa no contrato, e o contrato não
    pode depender de um backend concreto.
    """

    nivel: int
    rotulo: str
    atual: str
    opcoes: list[OpcaoDeContexto] = field(default_factory=list)


@dataclass(frozen=True)
class User:
    """O usuário logado, do ponto de vista de quem desenha a tela."""

    id: str
    name: str
    login: str = ""
    role_label: str = ""
    avatar: str = ""
    superuser: bool = False
    permissions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        # Aceita set, lista ou tupla na construção e congela: `User` é hashable
        # e viaja por toda a renderização, onde ninguém deveria conseguir
        # acrescentar uma permissão sem passar pelo backend.
        object.__setattr__(self, "permissions", frozenset(self.permissions))

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def first_name(self) -> str:
        return self.name.split()[0] if self.name.strip() else ""


def pode(user: "User | None", permission: str) -> bool:
    """Se `user` tem a permissão pedida.

    Sem permissão declarada, libera: é como o menu já se comporta hoje, e um
    item sem `permission` significa "todo mundo que entrou".

    `None` nunca pode nada — o caso mais comum em rota pública e o que mais
    dói errar.
    """
    if user is None:
        return False
    if not permission:
        return True
    if user.superuser:
        return True
    if permission in user.permissions:
        return True

    # "usuarios.*" cobre "usuarios.editar". Um papel costuma ser dito por
    # módulo, e escrever as quatro ações uma a uma envelhece mal: a ação nova
    # de amanhã não entraria em papel nenhum.
    modulo = permission.split(".")[0]
    return f"{modulo}.*" in user.permissions
