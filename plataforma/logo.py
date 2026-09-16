"""O logo da empresa sem a margem em volta do desenho (15/09/2026).

A barra do menu ajusta o ARQUIVO inteiro à caixa do logo (`object-fit:
contain`). Logo exportado com borda — o da Normadin chegou num JPEG de
1280×905 com o desenho ocupando 24% da altura — sai com metade do tamanho que
cabia, e parece distante e borrado. Cortar a margem no envio é o que faz o
desenho preencher a caixa, sem pedir a quem envia que saiba recortar imagem.

Só raster (PNG, JPEG, WEBP). SVG é vetor e pode ter `viewBox` pensado; GIF
pode ser animado, e cortar só o primeiro quadro estragaria o resto.
"""

from __future__ import annotations

import io

from PIL import Image, ImageChops, UnidentifiedImageError

__all__ = ["sem_margem"]

#: Os tipos que se cortam, com o formato do Pillow para regravar no MESMO tipo
#: — o `logo_tipo` gravado continua dizendo a verdade sobre os bytes.
_FORMATOS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}

#: Quanto um pixel pode diferir do fundo e ainda contar como fundo. JPEG não
#: tem branco puro em volta do desenho: a compressão deixa ruído de alguns
#: tons, e sem tolerância a "margem" seria a imagem inteira.
_TOLERANCIA = 24

#: O respiro deixado em volta do desenho, em pixels. Colado na borda, o
#: contorno suavizado do traço seria cortado junto com o fundo.
_RESPIRO = 8


def _caixa_do_desenho(imagem: Image.Image) -> "tuple[int, int, int, int] | None":
    """Onde está o desenho: pela transparência quando há, e pela diferença para
    a cor do canto quando não há (o fundo de um logo exportado é uniforme)."""
    if imagem.mode in ("RGBA", "LA") or "transparency" in imagem.info:
        alfa = imagem.convert("RGBA").getchannel("A")
        caixa = alfa.point(lambda v: 255 if v > _TOLERANCIA else 0).getbbox()
        if caixa is not None and caixa != (0, 0, *imagem.size):
            return caixa
    rgb = imagem.convert("RGB")
    fundo = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diferenca = ImageChops.difference(rgb, fundo).convert("L")
    return diferenca.point(lambda v: 255 if v > _TOLERANCIA else 0).getbbox()


def sem_margem(dados: bytes, tipo: str) -> bytes:
    """Os bytes do logo com a margem cortada — ou os mesmos bytes, quando não
    há o que cortar (regravar um JPEG sem motivo só perderia qualidade)."""
    formato = _FORMATOS.get(tipo)
    if formato is None:
        return dados
    try:
        imagem = Image.open(io.BytesIO(dados))
        imagem.load()
    except (UnidentifiedImageError, OSError):
        # A peneira de verdade é `nucleo.images.validar`, que decide pela
        # assinatura. Um arquivo que passa por ela e o Pillow não decodifica
        # fica como veio: cortar margem é conforto, e não pode virar recusa.
        return dados
    caixa = _caixa_do_desenho(imagem)
    if caixa is None:
        # Imagem de uma cor só: não há desenho para achar, e cortar tudo
        # gravaria um logo de zero pixel.
        return dados

    esquerda, topo, direita, base = caixa
    largura, altura = imagem.size
    recorte = (max(esquerda - _RESPIRO, 0), max(topo - _RESPIRO, 0),
               min(direita + _RESPIRO, largura), min(base + _RESPIRO, altura))
    if recorte == (0, 0, largura, altura):
        return dados

    cortada = imagem.crop(recorte)
    saida = io.BytesIO()
    if formato == "JPEG":
        cortada.convert("RGB").save(saida, "JPEG", quality=92, optimize=True)
    else:
        cortada.save(saida, formato, optimize=True)
    return saida.getvalue()
