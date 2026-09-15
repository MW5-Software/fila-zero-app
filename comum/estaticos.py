"""O endereço de um arquivo estático do PROJETO, com a versão junto.

**O problema, que é de implantação e não de código.** O `nucleo/` versiona as
folhas dele (`mw5.css?v=<mtime>`, ver `nucleo/rendering.estatico`), mas as
folhas que cada tela deste projeto acrescenta saem cruas. Depois de um deploy,
o navegador continua servindo a versão anterior do cache — e o sintoma é uma
tela com o layout quebrado que "funciona na minha máquina depois de um
Ctrl+Shift+R". É o tipo de defeito que vira chamado de suporte e não vira
correção, porque quem reporta não consegue reproduzir e quem recebe não
consegue ver.

**Por que aqui e não em `nucleo/`.** `nucleo/` é porte congelado. A correção
entra em `plataforma.site.SiteDoProduto.page`, que embrulha TODA página deste
projeto — um lugar, dezessete telas.

**Endereço que não é do projeto passa direto.** Um `//cdn...` ou um caminho já
com `?v=` sai como veio: esta função acrescenta versão, não reescreve
endereço.
"""

from __future__ import annotations

from django.conf import settings

__all__ = ["versionado"]

_PREFIXO = "/static/"

#: `caminho -> endereço versionado`, para não medir o mesmo arquivo em toda
#: requisição. Fora de `DEBUG` apenas: em desenvolvimento o arquivo muda a
#: cada salvamento, e um cache aqui devolveria a versão de antes da edição —
#: exatamente o problema que esta função existe para resolver.
_LEMBRADOS: dict[str, str] = {}


def versionado(endereco: str) -> str:
    """`/static/catalogo/catalogo.css` -> `/static/catalogo/catalogo.css?v=…`

    A versão é o `mtime` do arquivo: muda quando o arquivo muda, e não a cada
    deploy — assim um deploy que não mexeu na folha não invalida o cache de
    ninguém.
    """
    if not endereco.startswith(_PREFIXO) or "?" in endereco:
        return endereco

    if not settings.DEBUG and endereco in _LEMBRADOS:
        return _LEMBRADOS[endereco]

    marca = _mtime(endereco[len(_PREFIXO):])
    resposta = f"{endereco}?v={marca}" if marca else endereco
    if not settings.DEBUG:
        _LEMBRADOS[endereco] = resposta
    return resposta


def _mtime(relativo: str) -> "int | None":
    """O `mtime` do arquivo, ou `None` se ele não for encontrado.

    `None` faz o endereço sair sem versão, e é o comportamento certo para a
    falha: uma folha que existe e não é achada pelo finder continua carregando
    (só sem cache-buster), enquanto levantar aqui derrubaria a página inteira
    por causa de um detalhe de cache.
    """
    from pathlib import Path

    from django.contrib.staticfiles import finders

    # `STATIC_ROOT` primeiro: em produção é lá que o arquivo está depois do
    # `collectstatic`, e é uma leitura de disco em vez de uma varredura de
    # todos os apps.
    raiz = getattr(settings, "STATIC_ROOT", None)
    if raiz:
        candidato = Path(raiz) / relativo
        if candidato.is_file():
            return int(candidato.stat().st_mtime)

    achado = finders.find(relativo)
    if achado and Path(achado).is_file():
        return int(Path(achado).stat().st_mtime)
    return None
