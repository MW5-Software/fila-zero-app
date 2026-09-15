"""O seletor de idioma do cabeçalho — a bandeira de onde se está.

**O botão mostra o idioma ATUAL, não o próximo.** A primeira versão mostrava
para onde o clique levava ("ES" quando a tela estava em português), com a
ideia de que botão é saída. Estava errado do ponto de vista de quem olha: a
tela inteira já está em português, e um "ES" no canto faz a pessoa achar que
está em castelhano. Um indicador que mente sobre o estado é pior que
indicador nenhum — quem quer trocar descobre no `title`, que diz o que o
clique faz.

**Bandeira, e desenhada aqui.** Emoji de bandeira (🇧🇷) não desenha bandeira
no Windows — o navegador mostra as letras "BR" —, e é lá que este sistema é
usado. Arquivo de imagem seria uma requisição a mais no cabeçalho de toda
tela. SVG inline resolve os dois: desenha igual em todo lugar e não pede nada
ao servidor.

**São bandeiras de PAÍS, e país não é língua.** Brasil para o português,
Paraguai para o castelhano — porque é onde este produto é vendido. No dia em
que ele for vendido na Argentina, a bandeira do Paraguai passa a estar errada
para metade dos clientes, e aí o desenho certo é outro (as siglas, ou a
bandeira do país da INSTALAÇÃO). Fica escrito para a decisão ser tomada de
olhos abertos.

**Formulário, e não link.** Trocar idioma grava na conta, e mudança de estado
nesta casa não anda por link: um `<img src="/idioma">` numa página qualquer
trocaria o idioma de quem a abrisse.
"""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from comum.csrf import campo_csrf
from comum.idioma import idioma_da_requisicao
from nucleo.components import Raw

__all__ = ["seletor", "seletor_da_entrada"]

#: `viewBox` de 3x2 e nada de `width`/`height`: o tamanho vem da folha
#: (`kronos.css`), como no resto do design system. `rx` arredonda o retângulo
#: para a bandeira não brigar com os botões redondos ao lado.
_BRASIL = mark_safe(
    '<svg class="bandeira" viewBox="0 0 30 20" aria-hidden="true">'
    '<rect width="30" height="20" rx="2" fill="#009b3a"/>'
    '<path d="M15 2.6 27.2 10 15 17.4 2.8 10Z" fill="#fedf00"/>'
    '<circle cx="15" cy="10" r="4.2" fill="#002776"/>'
    '</svg>')

#: Paraguai: três faixas e o emblema central. O emblema de verdade é uma
#: estrela cercada por uma coroa de ramos — a 20px de largura isso vira um
#: borrão, então fica o disco com a estrela, que é o que se reconhece.
_PARAGUAI = mark_safe(
    '<svg class="bandeira" viewBox="0 0 30 20" aria-hidden="true">'
    '<rect width="30" height="20" rx="2" fill="#fff"/>'
    '<path d="M2 0h26a2 2 0 0 1 2 2v4.7H0V2a2 2 0 0 1 2-2Z" fill="#d52b1e"/>'
    '<path d="M0 13.3h30V18a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2Z" fill="#0038a8"/>'
    '<circle cx="15" cy="10" r="3" fill="#fff" stroke="#0038a8" '
    'stroke-width="0.6"/>'
    '<path d="m15 7.6.7 2.1h2.2l-1.8 1.3.7 2.1-1.8-1.3-1.8 1.3.7-2.1-1.8-1.3'
    'h2.2Z" fill="#009b3a"/>'
    '</svg>')

BANDEIRAS = {"pt-br": _BRASIL, "es": _PARAGUAI}

#: A seta do `summary`. Desenhada aqui e não pedida ao `icons.get`: o ícone
#: do design system nasce com a classe e o tamanho de ÍCONE, e aqui ela é um
#: acessório de 8px ao lado da bandeira.
_SETA = mark_safe(
    '<svg class="idioma-seta" viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" '
    'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
    '</svg>')


def seletor_da_entrada(request) -> "Raw | str":
    """O mesmo controle, na tela de entrada — em LINK, não em formulário.

    Ali não há conta, não há coluna e não há o que um pedido forjado consiga: a
    escolha vale para a sessão anônima e some com ela. Exigir POST antes do
    login custaria uma tela a mais justamente para quem abriu o sistema pela
    primeira vez e não entende o que está escrito.

    **Mostra a bandeira do idioma ATUAL e lista os outros**, igual ao do
    cabeçalho — e é por isso que ele não é só um link "Español" solto: o link
    de texto não dizia em que língua a tela estava, e quem chega em castelhano
    não sabe que o "Español" é o destino e não o estado.
    """
    atual = idioma_da_requisicao(request)
    if len([chave for chave, _rotulo in settings.LANGUAGES]) < 2:
        return ""

    nomes = dict(settings.LANGUAGES)
    opcoes = format_html_join("", (
        '<a class="idioma-opcao{}" href="{}?idioma={}"{}>{}<span>{}</span></a>'
    ), (
        (" e-atual" if codigo == atual else "",
         reverse("entrar"), codigo,
         mark_safe(' aria-current="true"') if codigo == atual else "",
         BANDEIRAS.get(codigo, ""), str(rotulo))
        for codigo, rotulo in settings.LANGUAGES
    ))

    frase = _("Idioma: %(atual)s") % {"atual": str(nomes.get(atual, atual))}
    return Raw(html=format_html(
        '<details class="idioma-menu idioma-na-entrada">'
        '<summary title="{}" aria-label="{}">{}{}</summary>'
        '<div class="idioma-opcoes">{}</div></details>',
        frase, frase, BANDEIRAS.get(atual, atual.upper()), _SETA, opcoes))


def seletor(request) -> "Raw | str":
    """O botão, ou nada.

    Nada para quem não entrou (sem conta não há onde gravar; a tela de
    entrada tem a escolha dela, em link) e nada numa instalação com um idioma
    só — botão que não faz nada é enfeite.

    **`<details>`, e não um botão que alterna.** A seta para baixo é o que
    diz que existem OUTRAS línguas: com dois idiomas, um botão que troca no
    clique funciona e não conta que há escolha. E seta sem menu seria pior
    que seta nenhuma — é a tela prometendo o que não cumpre.

    `<details>` nativo, como o "Estreitar" do catálogo: abre e fecha sem uma
    linha de JavaScript, funciona com teclado de graça, e não depende do
    `mw5.js` achar um id.
    """
    if request is None or not getattr(request, "usuario", None):
        return ""

    atual = idioma_da_requisicao(request)
    if len([chave for chave, _rotulo in settings.LANGUAGES]) < 2:
        return ""

    nomes = dict(settings.LANGUAGES)
    nome_atual = str(nomes.get(atual, atual))

    opcoes = format_html_join("", (
        '<button type="submit" name="idioma" value="{}" class="idioma-opcao'
        '{}"{}>{}<span>{}</span></button>'
    ), (
        (codigo,
         " e-atual" if codigo == atual else "",
         mark_safe(' aria-current="true"') if codigo == atual else "",
         BANDEIRAS.get(codigo, ""),
         str(rotulo))
        for codigo, rotulo in settings.LANGUAGES
    ))

    return Raw(html=format_html(
        '<form class="idioma-botao" method="post" action="{}">{}'
        '<input type="hidden" name="voltar" value="{}">'
        '<details class="idioma-menu">'
        # `title` no `summary` e não no `details`: é o `summary` que recebe o
        # ponteiro. Ele diz o ESTADO — a seta ao lado já diz que há escolha.
        '<summary class="iconbtn" title="{}" aria-label="{}">{}{}</summary>'
        '<div class="idioma-opcoes">{}</div>'
        '</details></form>',
        reverse("idioma"), campo_csrf(request), request.get_full_path(),
        _("Idioma: %(atual)s") % {"atual": nome_atual},
        _("Idioma: %(atual)s") % {"atual": nome_atual},
        BANDEIRAS.get(atual, atual.upper()), _SETA, opcoes))
