"""O ambiente Jinja do design system, criado uma vez por processo.

`nucleo.rendering.create_environment()` monta um `Environment` novo a cada
chamada — e cada tela chamava isso a cada requisição. Um `Environment` novo
nasce com o cache de template VAZIO, então todo template era lido do disco,
tokenizado, parseado e compilado outra vez, para toda pessoa, em toda tela.

Medido num perfil de `/usuarios` (5 requisições): 140 chamadas a
`builtins.compile`, 22 mil passagens pelo lexer do Jinja e 13.820 `stat` de
arquivo. Sob carga, o `gunicorn` consumia 228% de CPU enquanto o Postgres
ficava em 0% — o gargalo não era o banco, era recompilar o design system a
cada tela.

Guardar o ambiente é seguro: o Jinja trata `Environment` e `Template` como
imutáveis depois de criados, e os documenta como seguros para uso por várias
linhas de execução ao mesmo tempo. E o desenvolvimento não perde nada: o
`auto_reload` do Jinja continua conferindo a data do arquivo, então mexer num
template continua valendo sem reiniciar.

**Menos num caso, e ele custou meia hora em 10/09/2026**: criar em
`plataforma/templates/` um arquivo que SOMBREIA um do `nucleo` já em uso não
vale sem reiniciar. O `auto_reload` confere a data do arquivo que o ambiente
CARREGOU — e ele carregou o do `nucleo`, que não mudou; o nome não é procurado
de novo. O arquivo novo existe, o `runserver` até reinicia por causa do `.py`
ao lado, e a tela continua saindo com o desenho antigo, sem erro nenhum.
Editar uma cópia que JÁ existe vale na hora, como sempre.

**Só a chamada sem loaders extras é guardada.** Quem passar loaders próprios
(a saída de emergência para o template que um cliente sobrescreve) recebe um
ambiente novo, porque aí o conteúdo depende de quem chamou — guardar um só
faria o primeiro cliente decidir o template de todos.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from nucleo.rendering import create_environment

__all__ = ["ambiente"]


@lru_cache(maxsize=1)
def _ambiente_padrao():
    """O ambiente com os templates DESTA CASA na frente dos do design system.

    `create_environment` põe os loaders extras antes do dele de propósito —
    é a saída documentada para o template que um projeto precisa variar sem
    emendar o `nucleo`. Hoje há um: `layout/header.html`, que ganhou o
    seletor de idioma ao lado do sino (ver `plataforma/header.py`).

    Continua guardado, e é o que importa para o custo: o problema medido no
    topo deste módulo era criar ambiente por requisição, não ter dois
    loaders.
    """
    from django.conf import settings
    from jinja2 import FileSystemLoader

    da_casa = settings.BASE_DIR / "plataforma" / "templates"
    env = create_environment(FileSystemLoader(str(da_casa)))
    _ensinar_a_traduzir(env)
    return env


def _ensinar_a_traduzir(env) -> None:
    """Dá ao ambiente as duas funções que os templates DESTA CASA usam.

    `traduzir` e não `_`: o sublinhado é convenção do Django, e num template
    Jinja ele já é o descarte de vários idiomas de template. Nome inteiro
    custa seis caracteres e não colide com nada.

    Elas ficam aqui e não em `nucleo.rendering` porque tradução é assunto
    deste projeto: o design system é porte verbatim, e um `global` novo lá
    dentro seria emenda igual a qualquer outra.

    **Extensão `i18n` do Jinja não entra.** Ela existe para `{% trans %}`, que
    é sintaxe de bloco com regra própria de espaço e de plural; uma função
    global faz o que estas telas precisam — traduzir uma frase — e é lida por
    quem conhece Django sem aprender um segundo mecanismo.
    """
    from django.utils.translation import get_language, gettext

    def idioma_html() -> str:
        """O idioma da requisição no formato do atributo `lang`.

        `pt-br` vira `pt-BR`: o padrão HTML quer a região em maiúsculas, e é
        isso que faz o leitor de tela escolher a voz certa. Uma página inteira
        em castelhano anunciada como `lang="pt-BR"` é lida com a pronúncia
        errada, palavra por palavra.
        """
        codigo = get_language() or "pt-br"
        if "-" not in codigo:
            return codigo
        lingua, regiao = codigo.split("-", 1)
        return f"{lingua}-{regiao.upper()}"

    env.globals["traduzir"] = gettext
    env.globals["idioma_html"] = idioma_html


def ambiente(*extra_loaders: Any):
    """O ambiente de renderização desta requisição."""
    if extra_loaders:
        return create_environment(*extra_loaders)
    return _ambiente_padrao()
