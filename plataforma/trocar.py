"""O diálogo de trocar de empresa ou de loja (18/09/2026).

Escolher outra empresa no cabeçalho levava para a mesma página nua do sair —
"Trabalhar em Sylvia Móveis?" num cartão encostado no canto, sem menu, sem
contexto, e o "Cancelar" devolvendo para a raiz em vez da tela de onde se
saiu. Agora a pergunta acontece por cima da página, como a de sair.

**O servidor desenha; o script só preenche.** O diálogo já vem com os DOIS
formulários prontos (o da empresa e o da loja), cada um com o seu CSRF, a sua
`action` e o campo do id vazio. O `contexto.js` mostra o que vale, escreve o
nome escolhido como TEXTO e põe o id no campo — nenhum HTML é montado no
navegador, a mesma regra da página da fila.

**Quem age continua sendo o POST** de `empresa_trocar`/`filial_trocar`, com
as mesmas validações: id que a pessoa não alcança é 404 nas duas pontas. O
caminho por URL (`/empresa/trocar?empresa_id=N`) continua existindo.
"""

from __future__ import annotations

from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _

from comum.csrf import campo_csrf
from nucleo.components import Button, Form, Modal, Raw

from .contexto import CHAVE, CHAVE_EMPRESA

__all__ = ["ID_DO_DIALOGO", "modal_de_troca"]

#: O id do diálogo, e o que o `contexto.js` procura. Fixo pelo mesmo motivo do
#: diálogo de sair: só existe um por página.
ID_DO_DIALOGO = "trocar-dialogo"


def _formulario(request, *, para: str, action: str, campo: str, extras=(),
                dados=None):
    """Um dos dois formulários do diálogo, nascendo escondido.

    `hidden` no `<form>`, e não `display:none` na folha: o navegador tira do
    foco e do envio o que está `hidden`, e o formulário errado nunca viaja
    junto — ver `test_esconder_vence_o_display.py` para o outro lado da mesma
    regra.
    """
    campos = [
        Raw(html=campo_csrf(request)),
        Raw(html=format_html(
            '<input type="hidden" name="{}" value="" data-id-escolhido>', campo)),
    ]
    campos += [Raw(html=format_html(
        '<input type="hidden" name="{}" value="{}">', nome, valor))
        for nome, valor in extras]
    campos.append(Button(label=_("Confirmar"), variant="primary", type="submit"))
    return Form(action=action, children=campos,
                attrs={"data-para": para, "hidden": True, **(dados or {})})


def _empresa_de_agora(request) -> str:
    """O nome da empresa desta sessão, para a troca de LOJA dizer "Empresa -
    Loja" (o script só conhece a loja que se escolheu)."""
    from .contexto import empresa_atual

    atual = empresa_atual(request)
    return str(atual) if atual is not None else ""


def _chegada_por_empresa(request) -> str:
    """`{id da empresa: nome da loja em que se cai}`, em JSON, para a troca de
    EMPRESA dizer "Empresa - Loja" antes de trocar. A loja sai da regra de
    `filial_de_entrada`, a mesma que a sessão usa depois da troca, e de uma
    vez para todas as empresas (`filiais_de_entrada`)."""
    import json

    from comum.sessao import identidade_da_sessao

    from .contexto import empresas_de, filiais_de_entrada

    pessoa = identidade_da_sessao(request)
    chegada = filiais_de_entrada(pessoa, empresas_de(pessoa))
    return json.dumps({str(pk): str(f) for pk, f in chegada.items()},
                      ensure_ascii=False)


def modal_de_troca(request, *, com_empresa: bool = True,
                   com_filial: bool = True) -> Modal:
    """O diálogo fechado, pronto para entrar em `overlays`.

    Um formulário por nível que a pessoa pode trocar de verdade: quem alcança
    várias lojas de uma empresa só não leva o campo `empresa_id` embutido em
    toda página.
    """
    # A frase fica montada, com o nome de destino em branco: o script escreve
    # o texto do `<option>` que a pessoa escolheu. `textContent`, e não HTML —
    # o nome é dado cadastrado, e dado cadastrado nunca vira marcação.
    #
    # A frase diz a empresa E a loja (25/09/2026, pedido do cliente: "Trocar
    # Empresa/Filial? Você vai passar a trabalhar na empresa - filial
    # selecionada"): o script junta o nome escolhido com o que o formulário
    # traz — a empresa de agora (`data-empresa`), ou a loja em que se cai
    # (`data-chegada`).
    pergunta = Raw(html=format_html(
        "<p>{} <strong data-alvo-da-troca></strong>.</p>",
        _("Você vai passar a trabalhar na")))
    return Modal(
        id=ID_DO_DIALOGO,
        title=_("Trocar Empresa/Filial?"),
        size="sm",
        body=pergunta,
        footer=[Button(label=_("Cancelar"), attrs={"data-modal-close": ""})]
        + ([_formulario(request, para="empresa",
                        action=reverse("empresa_trocar"), campo=CHAVE_EMPRESA,
                        dados={"data-chegada": _chegada_por_empresa(request)})]
           if com_empresa else [])
        # A loja volta para a página de onde se trocou — é o que a fila
        # precisa (`plataforma.views_filial._voltar_seguro` confere que o
        # caminho é desta instalação antes de devolver alguém para ele).
        + ([_formulario(request, para="filial",
                        action=reverse("filial_trocar"), campo=CHAVE,
                        extras=(("voltar", request.get_full_path()),),
                        dados={"data-empresa": _empresa_de_agora(request)})]
           if com_filial else []),
    )
