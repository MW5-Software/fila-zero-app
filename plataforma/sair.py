"""O diálogo de sair, que toda tela do shell carrega fechado (18/09/2026).

Sair era um ícone solto no canto do cabeçalho que levava embora da tela: a
página `/sair` é nua de propósito (`comum/confirmacao.py` explica por quê —
ela roda mesmo com sessão quebrada, e por isso não monta menu nenhum), e usá-la
como caminho NORMAL fazia todo dia parecer um erro. Agora ela é o caminho de
quem está sem JavaScript, e quem tem JavaScript responde a mesma pergunta em
cima da página em que estava.

**O formulário é o mesmo da página de confirmação**: POST em `/sair` com o
CSRF. Não há rota nova, não há segunda regra de sair, e o GET continua
perguntando em vez de agir — um `<img src="/sair">` numa página qualquer não
derruba sessão nenhuma.
"""

from __future__ import annotations

from django.utils.translation import gettext as _

from comum.csrf import campo_csrf
from nucleo.components import Button, Form, Modal, Raw

__all__ = ["ID_DO_DIALOGO", "modal_de_sair"]

#: O id do diálogo, e o que o `sair.js` procura. Fixo porque só existe um por
#: página — o mesmo raciocínio do `Header.MENU_DO_USUARIO`.
ID_DO_DIALOGO = "sair-dialogo"


def modal_de_sair(request, *, action: str, nome: str = "") -> Modal:
    """O diálogo fechado, pronto para entrar em `overlays`.

    `nome` é quem está logado, quando se sabe: a pergunta diz de qual sessão
    se está saindo, que é a única dúvida real de quem divide o computador do
    balcão com outra pessoa.
    """
    pergunta = (
        _("Você está conectado como %(nome)s e vai precisar entrar de novo.")
        % {"nome": nome} if nome else _("Você vai precisar entrar de novo.")
    )
    return Modal(
        id=ID_DO_DIALOGO,
        title=_("Sair do sistema?"),
        size="sm",
        body=pergunta,
        # O formulário no rodapé, e não no corpo: os dois botões precisam
        # estar DENTRO do `<form>` para o "Sair" ser um `submit` de verdade, e
        # o rodapé é onde o design system põe as ações do diálogo.
        footer=Form(action=action, children=[
            Raw(html=campo_csrf(request)),
            Button(label=_("Cancelar"), attrs={"data-modal-close": ""}),
            Button(label=_("Sair"), variant="danger", type="submit"),
        ]),
    )
