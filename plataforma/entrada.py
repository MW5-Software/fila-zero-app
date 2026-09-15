"""A tela de entrada em castelhano — e por que ela é o caso mais difícil.

**Nada que se lê naquela tela é texto nosso no código.** "Acessar Painel",
"E-mail", "Manter conectado", "Entrar", "Fale com o suporte" — tudo vem do
`LoginBrand` (`nucleo/theme/brand.py`), porque a entrada é a primeira tela que
o cliente vê e a que ele mais quer chamar de sua: ele edita cada uma dessas
frases na tela de Aparência, e o que ele escreveu fica no banco.

Isso fez o seletor de idioma da entrada mudar o idioma e a tela continuar
igual — defeito relatado em 10/09/2026, e a leitura de quem olha é a pior
possível: "o botão não funciona".

**A regra é a mesma do menu** (`plataforma.menu._traduzido`): traduz-se o que
ainda é NOSSO. Uma frase que continua igual ao padrão do produto passa pelo
arquivo de tradução; uma que o cliente trocou ("Entre no portal da Ferragem
Silva") passa intacta, porque a palavra é dele e ninguém pediu para
traduzi-la.

O preço disso é uma lista explícita de frases aqui embaixo, e ela é a parte
que envelhece: `LoginBrand` ganhar um campo novo não acrescenta nada aqui
sozinho. `tests/test_entrada_em_castelhano.py` compara as duas e fica vermelho
quando elas divergem.
"""

from __future__ import annotations

from dataclasses import replace

from django.utils.translation import gettext, gettext_noop as _

from nucleo.theme.brand import LoginBrand

__all__ = ["CAMPOS_DE_TEXTO", "traduzir_a_entrada"]

#: Os campos de `LoginBrand` que são TEXTO visível. Os outros são cor, URL e
#: booleano — e um `forgot_url` traduzido levaria a pessoa para uma página que
#: não existe.
CAMPOS_DE_TEXTO = (
    "title", "subtitle", "tagline", "separator",
    "identifier_label", "identifier_placeholder",
    "password_label", "password_placeholder",
    "remember_label", "forgot_label", "submit_label",
    "support_text", "support_label",
)

#: As frases que este produto escreve — o padrão do `LoginBrand` mais as duas
#: que `plataforma.marca.ENTRADA_POR_EMAIL` troca (a entrada é por e-mail
#: desde que o usuário passou a ser nosso).
#:
#: Existem aqui por um motivo mecânico: elas são literais do `nucleo`, e o
#: extrator não lê o `nucleo` — ele lê os apps deste projeto. Sem esta lista, o
#: `.po` não teria nenhuma delas e a tela ficaria em português mesmo com tudo
#: certo em volta.
#:
#: **`gettext_noop` e não `gettext_lazy`, e a diferença é o defeito de
#: 10/09/2026.** Esta lista é o GABARITO da comparação: ela precisa guardar o
#: português, sempre. Com a versão preguiçosa, cada entrada virava o texto no
#: idioma ATIVO — e com a tela em castelhano o gabarito também estava em
#: castelhano, então nada casava com a marca (que está em português no banco) e
#: nada era traduzido. O `noop` marca para o extrator e devolve o original.
NOSSAS = frozenset({
    _("Acessar Painel"), _("Usuário"), _("Seu usuário"),
    _("E-mail"), _("Seu e-mail"),
    _("Senha"), _("Sua senha"),
    _("Manter conectado"), _("Esqueceu a senha?"), _("Entrar"),
    _("Problemas para entrar?"), _("Fale com o suporte"),
})


def _e_nossa(frase: str) -> bool:
    """A frase ainda é a que o produto escreveu?

    Compara por TEXTO e não por "o cliente mexeu nesta tela": ele pode ter
    trocado o título e deixado o resto, e o resto continua nosso.
    """
    return frase in NOSSAS


def traduzir_a_entrada(login: LoginBrand) -> LoginBrand:
    """O `LoginBrand` com as frases do produto na língua de quem olha."""
    mudancas = {
        campo: gettext(valor)
        for campo in CAMPOS_DE_TEXTO
        if (valor := getattr(login, campo, None)) and _e_nossa(valor)
    }
    return replace(login, **mudancas) if mudancas else login
