"""O que o titular e a MW5 já trazem de permissão, sem ninguém marcar caixa.

**Só os dois níveis que não têm cargo.** Desde a virada dos cargos (spec
2026-09-14), o que um membro da conta pode vem do CARGO da alocação dele, no
lugar em que está (`contas.lugar`). O titular e a MW5 não são alocados — um
cargo no dono permitiria trancá-lo para fora da própria conta —, e por isso as
permissões deles moram aqui, como permissão DIRETA, gravada quando o nível é
definido (`aplicar`).

O nível não é editável pelo cliente, e essa é a razão de a lista morar no
código: se o titular pudesse acrescentar `parametros.editar` ao próprio nível,
toda conta do portal ganharia junto.
"""

from __future__ import annotations

from .models import Nivel

__all__ = ["DE_FABRICA", "aplicar"]

#: As permissões de cada nível, no vocabulário do núcleo (`modulo.acao`).
#:
#: MASTER leva o coringa de cada módulo (`X.*`) em vez da lista de ações: é a
#: MW5 dentro do portal, e escrever ação por ação faria o nível envelhecer
#: sozinho — a ação nova de amanhã não entraria nele, e alguém descobriria
#: isso na tela, num dia ruim. `pode()` já trata `X.*` como cobrindo
#: `X.qualquer`.
#:
#: O TITULAR é lista fechada, e de propósito: ele não herda a ação nova de um
#: módulo só porque ela nasceu. Quem ganha por omissão é só quem já pode tudo.
DE_FABRICA: dict[int, tuple[str, ...]] = {
    Nivel.MASTER: (
        "auditoria.*", "cargos.*", "empresa.*", "filiais.*",
        "parametros.*", "usuarios.*",
    ),
    #: O titular cadastra e aloca a gente da conta dele e mexe no cadastro da
    #: empresa. Não tem `parametros.editar`: configuração da instalação é da
    #: MW5.
    #: **`filiais.editar` desde 14/09/2026**: o titular cadastra as filiais da
    #: empresa dele. Só pôde entrar depois de a tela de Filiais passar a
    #: enxergar apenas a empresa do contexto (`plataforma/views_filiais.py`,
    #: `_filiais_da_empresa`) — antes ela listava a instalação inteira, e esta
    #: permissão daria a um cliente as filiais de todos os outros.
    #:
    #: **Cada SaaS acrescenta aqui as permissões dos módulos de negócio dele**
    #: que o titular deve ter de nascença (no Portal de Vendas, catálogo e
    #: orçamentos).
    #:
    #: **`cargos.editar` desde 14/09/2026**: põe a tela de Cargos no menu do
    #: titular. Não é ela que tranca — é o nível, na view (ver
    #: `contas/views_cargos.py`) —, e ela nunca é oferecida numa caixa de
    #: cargo.
    Nivel.TITULAR: (
        "cargos.editar", "empresa.editar",
        "filiais.editar",
        "usuarios.editar",
    ),
}


def _codename(permissao: str) -> str:
    """`usuarios.editar` → `usuarios_editar`.

    A tradução inversa da que `contas.backend.permissoes_de` faz na leitura.
    Escrito com ponto aqui em cima porque é assim que a permissão é dita em
    todo o resto do código (`exigir_permissao("usuarios.editar")`); guardar com
    sublinhado obrigaria quem lesse esta tabela a traduzir de cabeça.
    """
    return permissao.replace(".", "_")


def aplicar(usuario, nivel: int) -> None:
    """Deixa as permissões DIRETAS de `usuario` iguais às do nível.

    Troca em bloco, não soma: promover alguém tem de RETIRAR o que o nível
    antigo dava. Somar deixaria um titular rebaixado a membro continuando a
    editar o catálogo — a promoção seria reversível e o rebaixamento não, que
    é exatamente o jeito errado de errar. Membro não tem entrada aqui: `aplicar`
    com o nível dele apaga todas as diretas.

    Silencioso quando a permissão não existe como linha: `materializar`
    (`contas/permissoes.py`) roda a cada `migrate`, mas um módulo declarado e
    ainda não materializado não pode derrubar um cadastro de usuário.
    """
    from django.contrib.auth.models import Permission

    nomes = DE_FABRICA.get(int(nivel), ())
    usuario.user_permissions.set(
        Permission.objects.filter(codename__in=[_codename(n) for n in nomes]))
