"""`format_lazy` com HTML dentro é marcação crua na tela.

**O defeito, em 10/09/2026.** O crachá "Principal" da galeria era HTML fixo em
`mark_safe`. Ao ganhar tradução, virou:

    _SELO_PRINCIPAL = format_lazy('<span class="foto-selo">{}</span>',
                                  _("Principal"))

e a tela passou a mostrar `<span class="foto-selo">Principal</span>` escrito na
cara do usuário. `format_lazy` devolve texto PREGUIÇOSO, e texto preguiçoso não
é texto SEGURO: o template escapa, porque é exatamente o que ele deve fazer
com qualquer coisa que não se declarou segura.

É armadilha específica de quem está traduzindo, e por isso vale uma varredura:
`mark_safe` não serve (ele resolveria a tradução no import, congelando o
idioma de quem subiu o processo), e a saída certa — `format_html` dentro de uma
função — não é a primeira que ocorre.
"""

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTAS = ("contas", "plataforma", "comum", "modulos")

#: Uma marcação de verdade, e não um "<" solto numa frase ("< 10 unidades").
TEM_MARCACAO = re.compile(r"<[a-zA-Z/][^>]*>")


def _fontes():
    for pasta in PASTAS:
        for arquivo in (RAIZ / pasta).rglob("*.py"):
            if "migrations" not in arquivo.parts:
                yield arquivo


def test_nenhum_format_lazy_monta_html():
    culpados = []
    for arquivo in _fontes():
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            nome = getattr(no.func, "id", None) or getattr(no.func, "attr", None)
            if nome != "format_lazy" or not no.args:
                continue
            primeiro = no.args[0]
            if (isinstance(primeiro, ast.Constant)
                    and isinstance(primeiro.value, str)
                    and TEM_MARCACAO.search(primeiro.value)):
                culpados.append(f"{arquivo.relative_to(RAIZ)}:{no.lineno}")

    assert culpados == [], (
        "`format_lazy` montando HTML — o template vai escapar e a marcação "
        f"aparece na tela: {culpados}. Use `format_html` dentro de uma função, "
        "que devolve `SafeString` e roda na hora da tela (então a tradução "
        "sai no idioma de quem olha).")
