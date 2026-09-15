"""Validação das imagens enviadas (logo e favicon).

Regra: o tipo do arquivo é decidido pelo conteúdo, nunca pelo que o navegador
disse. O `Content-Type` do formulário e a extensão do nome são dados de entrada
como quaisquer outros — quem os controla é quem envia, e devolvê-los depois num
cabeçalho de resposta transforma um upload de logo em HTML servido pela origem
do painel.

SVG é aceito porque é o formato certo para uma marca vetorial, mas passa por uma
peneira: SVG é XML e pode carregar script. Rejeitamos os elementos e atributos
que executam código em vez de tentar limpá-los, porque uma lista de coisas
proibidas erra por excesso de confiança — recusar um logo estranho custa muito
menos do que deixar passar um que roda script.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["ImagemInvalida", "ImagemValidada", "validar"]


class ImagemInvalida(ValueError):
    """O arquivo enviado não é uma imagem que aceitamos."""


@dataclass(frozen=True)
class ImagemValidada:
    """O que sabemos sobre a imagem depois de olhar o conteúdo dela."""

    media_type: str
    extension: str
    data: bytes


#: Assinaturas de arquivo. A chave é o prefixo em bytes; o valor, o que servir.
_ASSINATURAS: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"GIF87a", "image/gif", ".gif"),
    (b"GIF89a", "image/gif", ".gif"),
    (b"\x00\x00\x01\x00", "image/x-icon", ".ico"),
)

#: O que torna um SVG perigoso. Buscamos no texto normalizado, sem depender de
#: parser: um documento malformado de propósito pode enganar o parser e ainda
#: assim ser executado pelo navegador, que é bem mais tolerante.
_SVG_PROIBIDO = re.compile(
    r"<\s*(script|foreignobject|iframe|embed|object|use\b[^>]*\bhref\s*=\s*[\"']?\s*http)"
    r"|\bon[a-z]+\s*="            # onload, onclick, onerror…
    r"|javascript\s*:"
    r"|data\s*:\s*text/html"
    r"|<!ENTITY",                  # expansão de entidade externa
    re.IGNORECASE,
)

_MAX_BYTES = 2 * 1024 * 1024


def validar(
    data: bytes,
    *,
    tamanho_maximo: int = _MAX_BYTES,
    aceitos: "tuple[str, ...] | None" = None,
) -> ImagemValidada:
    """Confere que os bytes são mesmo uma imagem aceita e diz o que servir.

    `aceitos` restringe os tipos. Sem ele, vale tudo que o validador conhece —
    é o caso do logo. Com ele, o chamador diz o que sabe tratar: um avatar
    aceita só raster, porque SVG é XML que pode carregar script e ele é
    renderizado em `<img>` no cabeçalho de toda página.

    Levanta `ImagemInvalida` com uma mensagem em português — ela vai direto para
    a tela de quem enviou o arquivo.
    """
    if not data:
        raise ImagemInvalida("O arquivo está vazio.")
    if len(data) > tamanho_maximo:
        raise ImagemInvalida(
            f"A imagem tem {len(data) // 1024} KB; o limite é "
            f"{tamanho_maximo // 1024} KB."
        )

    for assinatura, media_type, extensao in _ASSINATURAS:
        if data.startswith(assinatura):
            return _aceitar(ImagemValidada(media_type, extensao, data), aceitos)

    if _parece_webp(data):
        return _aceitar(ImagemValidada("image/webp", ".webp", data), aceitos)

    if _parece_svg(data):
        return _aceitar(_validar_svg(data), aceitos)

    raise ImagemInvalida(
        "Formato não reconhecido. Envie PNG, JPG, GIF, ICO, WEBP ou SVG."
    )


def _parece_webp(data: bytes) -> bool:
    """RIFF com o marcador WEBP no byte 8. Um WAV também começa com RIFF, então
    o prefixo sozinho não decide."""
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _parece_svg(data: bytes) -> bool:
    inicio = data[:1024].lstrip()
    return inicio.startswith(b"<?xml") or inicio.startswith(b"<svg") or b"<svg" in inicio


def _validar_svg(data: bytes) -> ImagemValidada:
    try:
        texto = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ImagemInvalida("O SVG precisa estar em UTF-8.") from None

    if "<svg" not in texto.lower():
        raise ImagemInvalida("O arquivo parece XML, mas não é um SVG.")

    achado = _SVG_PROIBIDO.search(texto)
    if achado:
        raise ImagemInvalida(
            f"O SVG contém {achado.group(0).strip()!r}, que pode executar código. "
            f"Exporte o logo sem script — ou envie em PNG."
        )
    return ImagemValidada("image/svg+xml", ".svg", data)


def _aceitar(imagem: ImagemValidada, aceitos: "tuple[str, ...] | None") -> ImagemValidada:
    if aceitos is not None and imagem.media_type not in aceitos:
        nomes = [t.split("/")[-1].upper() for t in aceitos]
        if len(nomes) == 1:
            legiveis = nomes[0]
        else:
            legiveis = ", ".join(nomes[:-1]) + " ou " + nomes[-1]
        raise ImagemInvalida(f"Envie uma imagem {legiveis}.")
    return imagem


#: Cabeçalhos para servir imagem enviada por terceiros.
#:
#: A CSP com `sandbox` (sem `allow-scripts`) é a segunda tranca: mesmo que algum
#: SVG escape da peneira acima e alguém abra a URL direto numa aba, o navegador
#: não executa nada. `nosniff` impede que o navegador ignore o tipo declarado e
#: adivinhe HTML a partir do conteúdo.
CABECALHOS_SEGUROS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-cache",
}
