"""Gera os logos de `plataforma/static/plataforma/marca/` a partir do arquivo
original da marca.

    uv run --with pillow python ferramentas/gerar_logos.py --origem CAMINHO

Existe porque o problema que ele resolve não se vê na tela do desenvolvedor:
um PNG de 138x96 exibido numa caixa de 110x24 parece perfeito num monitor
comum e sai borrado em qualquer tela retina, que é a maioria dos notebooks. O
olho não denuncia no lugar onde o arquivo é feito.

A regra é gerar cada logo com FATOR vezes a caixa em que ele aparece. Três
vezes cobre telas de 2x com folga e 3x sem esticar, e mantém o arquivo pequeno
— embarcar o original de 13890x13890 no rodapé resolveria o mesmo problema
gastando trinta vezes mais banda para o mesmo resultado visível.

As caixas vêm dos tokens do tema, e estão repetidas aqui de propósito: ler CSS
para gerar imagem seria um acoplamento pior que a duplicação. Se as medidas
mudarem em `plataforma/marca.py::AREAS_DO_LOGO_DO_PRODUTO`, mudam aqui junto.

Veio do painel GED, onde esta marca e esta conta já estavam resolvidas.
"""

import argparse
from pathlib import Path

from PIL import Image

# O arquivo da marca tem 13890x13890 — 193 milhões de pixels, acima do teto que
# a Pillow usa para recusar "bomba de descompressão". A proteção existe para
# imagem que CHEGA de fora; esta é nossa, versionada, e o script só roda à mão.
Image.MAX_IMAGE_PIXELS = None

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "plataforma" / "static" / "plataforma" / "marca"

#: Quantas vezes a caixa de exibição. Ver o porquê no topo do arquivo.
FATOR = 3

#: nome -> (largura, altura) da caixa em CSS.
#: `--logo-login-w/h` do design system; `--logo-side-h` e `--logo-footer-w/h`
#: de `AREAS_DO_LOGO_DO_PRODUTO`.
CAIXAS = {
    "kronos-login": (220, 72),
    # A barra tem só altura no token (`--logo-side-h`); a largura sai da
    # proporção da marca, e o `thumbnail` cuida disso sozinho.
    "kronos-sidebar": (200, 84),
    "kronos-footer": (72, 40),
}


def gerar(origem: Path, nome: str, caixa: tuple[int, int]) -> None:
    largura, altura = (medida * FATOR for medida in caixa)

    with Image.open(origem) as imagem:
        marca = imagem.convert("RGBA")

        # Corta a moldura transparente ANTES de redimensionar. Sem isso, o
        # `thumbnail` encolhe a imagem inteira — vazio incluso — para caber na
        # caixa, e a marca sai menor do que a caixa comporta, com sobra
        # invisível em volta.
        recorte = marca.getbbox()
        if recorte:
            marca = marca.crop(recorte)
        # `thumbnail` preserva a proporção e nunca AUMENTA — se o original for
        # menor que o alvo, ele fica como está em vez de virar borrão ampliado.
        marca.thumbnail((largura, altura), Image.LANCZOS)

        arquivo = DESTINO / f"{nome}.png"
        marca.save(arquivo, "PNG", optimize=True)

    print(
        f"{arquivo.name}: {marca.width}x{marca.height} "
        f"(caixa {caixa[0]}x{caixa[1]}, {FATOR}x) "
        f"{arquivo.stat().st_size // 1024} KB"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", required=True, type=Path, help="PNG da marca")
    args = parser.parse_args()

    if not args.origem.exists():
        raise SystemExit(f"origem não encontrada: {args.origem}")

    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, caixa in CAIXAS.items():
        gerar(args.origem, nome, caixa)


if __name__ == "__main__":
    main()
