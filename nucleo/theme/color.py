"""Conversões de cor em OKLab/OKLCH.

Existe para uma coisa só: dado que um cliente informou apenas a cor primária,
derivar as variantes (hover mais escuro, versão legível no tema escuro, cor do
texto que vai por cima) sem que alguém precise escolher hex à mão. OKLab é usado
em vez de HSL porque em HSL clarear azul e clarear amarelo na mesma quantidade
produz resultados perceptualmente muito diferentes, e o design system depende de
que primary e accent se comportem igual.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "Color",
    "parse",
    "mix",
    "contrast_ratio",
    "readable_on",
]


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass(frozen=True)
class Color:
    """Uma cor sRGB, com componentes de 0 a 1."""

    r: float
    g: float
    b: float

    # ---------- construção ----------

    @classmethod
    def from_hex(cls, value: str) -> "Color":
        s = value.strip().lstrip("#")
        if len(s) == 3:
            s = "".join(ch * 2 for ch in s)
        if len(s) != 6:
            raise ValueError(f"cor hexadecimal inválida: {value!r}")
        try:
            n = int(s, 16)
        except ValueError as exc:
            raise ValueError(f"cor hexadecimal inválida: {value!r}") from exc
        return cls(((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255)

    @classmethod
    def from_oklch(cls, lightness: float, chroma: float, hue_deg: float) -> "Color":
        """Cor a partir de OKLCH, reduzindo o croma até caber no sRGB se preciso.

        Cortar cada canal em 0..1 separadamente — que é o reflexo óbvio — desloca
        matiz e luminosidade e desbota a cor. Preferimos abrir mão só do croma,
        que é o que o olho perdoa: o azul continua no mesmo tom e no mesmo brilho,
        apenas menos saturado do que o monitor não daria conta de mostrar mesmo.
        """
        big_l = _clamp(lightness)
        if chroma <= 0:
            return cls._from_oklab_raw(big_l, 0.0, 0.0)[0]

        color, in_gamut = cls._oklch_raw(big_l, chroma, hue_deg)
        if in_gamut:
            return color

        lo, hi = 0.0, chroma
        for _ in range(24):  # ~1e-7 de precisão, muito além do passo do hex
            mid = (lo + hi) / 2
            _, ok = cls._oklch_raw(big_l, mid, hue_deg)
            lo, hi = (mid, hi) if ok else (lo, mid)
        return cls._oklch_raw(big_l, lo, hue_deg)[0]

    @classmethod
    def _oklch_raw(cls, big_l: float, chroma: float, hue_deg: float) -> tuple["Color", bool]:
        h = math.radians(hue_deg)
        return cls._from_oklab_raw(big_l, chroma * math.cos(h), chroma * math.sin(h))

    @classmethod
    def _from_oklab(cls, big_l: float, a: float, b: float) -> "Color":
        return cls._from_oklab_raw(big_l, a, b)[0]

    @classmethod
    def _from_oklab_raw(cls, big_l: float, a: float, b: float) -> tuple["Color", bool]:
        """Converte e informa se o resultado coube no sRGB sem cortes."""
        l_ = big_l + 0.3963377774 * a + 0.2158037573 * b
        m_ = big_l - 0.1055613458 * a - 0.0638541728 * b
        s_ = big_l - 0.0894841775 * a - 1.2914855480 * b
        l, m, s = l_**3, m_**3, s_**3
        channels = (
            _linear_to_srgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
            _linear_to_srgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
            _linear_to_srgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s),
        )
        tolerance = 1e-6
        in_gamut = all(-tolerance <= c <= 1 + tolerance for c in channels)
        return cls(*(_clamp(c) for c in channels)), in_gamut

    # ---------- conversão ----------

    @property
    def hex(self) -> str:
        return "#{:02x}{:02x}{:02x}".format(
            round(_clamp(self.r) * 255),
            round(_clamp(self.g) * 255),
            round(_clamp(self.b) * 255),
        )

    def to_oklab(self) -> tuple[float, float, float]:
        lr, lg, lb = (
            _srgb_to_linear(self.r),
            _srgb_to_linear(self.g),
            _srgb_to_linear(self.b),
        )
        l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
        m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
        s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb
        l_, m_, s_ = _cbrt(l), _cbrt(m), _cbrt(s)
        return (
            0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
        )

    def to_oklch(self) -> tuple[float, float, float]:
        big_l, a, b = self.to_oklab()
        chroma = math.hypot(a, b)
        hue = math.degrees(math.atan2(b, a)) % 360
        return big_l, chroma, hue

    # ---------- manipulação ----------

    @property
    def lightness(self) -> float:
        return self.to_oklab()[0]

    def with_lightness(self, lightness: float) -> "Color":
        _, chroma, hue = self.to_oklch()
        return Color.from_oklch(_clamp(lightness), chroma, hue)

    def lighten(self, amount: float) -> "Color":
        big_l, chroma, hue = self.to_oklch()
        return Color.from_oklch(_clamp(big_l + amount), chroma, hue)

    def darken(self, amount: float) -> "Color":
        return self.lighten(-amount)

    def with_chroma(self, chroma: float) -> "Color":
        big_l, _, hue = self.to_oklch()
        return Color.from_oklch(big_l, max(0.0, chroma), hue)

    def scale_chroma(self, factor: float) -> "Color":
        big_l, chroma, hue = self.to_oklch()
        return Color.from_oklch(big_l, max(0.0, chroma * factor), hue)

    @property
    def relative_luminance(self) -> float:
        """Luminância relativa da WCAG — base do cálculo de contraste."""
        lr, lg, lb = (
            _srgb_to_linear(self.r),
            _srgb_to_linear(self.g),
            _srgb_to_linear(self.b),
        )
        return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb

    def __str__(self) -> str:  # pragma: no cover - conveniência
        return self.hex


def _cbrt(x: float) -> float:
    return math.copysign(abs(x) ** (1 / 3), x)


def parse(value: "str | Color") -> Color:
    return value if isinstance(value, Color) else Color.from_hex(value)


def mix(a: "str | Color", b: "str | Color", t: float) -> Color:
    """Mistura em OKLab, que evita as cores lamacentas do meio do caminho em sRGB."""
    ca, cb = parse(a), parse(b)
    la, aa, ba = ca.to_oklab()
    lb, ab, bb = cb.to_oklab()
    t = _clamp(t)
    return Color._from_oklab(
        la + (lb - la) * t, aa + (ab - aa) * t, ba + (bb - ba) * t
    )


def contrast_ratio(a: "str | Color", b: "str | Color") -> float:
    """Razão de contraste WCAG entre duas cores (1.0 a 21.0)."""
    la, lb = parse(a).relative_luminance, parse(b).relative_luminance
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def legivel_sobre(
    background: "str | Color",
    cor: "str | Color",
    minimo: float = 4.5,
) -> Color:
    """A cor dada, com a claridade ajustada até ficar legível sobre o fundo.

    Diferente de `readable_on`, que escolhe entre preto e branco: aqui a cor
    escolhida é preservada em matiz e croma, e só a claridade se move. É o que
    deixa o azul do item selecionado continuar azul tanto num menu escuro
    quanto num claro — em vez de virar branco num e preto no outro.

    Anda para o lado que tem para onde ir: fundo claro pede escurecer, fundo
    escuro pede clarear. Devolve a cor original quando ela já passa.
    """
    fundo, alvo = parse(background), parse(cor)
    if contrast_ratio(fundo, alvo) >= minimo:
        return alvo

    # Para longe do fundo. Passo pequeno e busca linear: são no máximo 100
    # tentativas, e uma busca binária aqui erraria — contraste não é monotônico
    # quando a claridade cruza a do fundo.
    subindo = fundo.lightness < 0.5
    claridade = alvo.to_oklch()[0]
    melhor = alvo
    for _ in range(100):
        claridade += 0.01 if subindo else -0.01
        if not 0.0 <= claridade <= 1.0:
            break
        candidata = alvo.with_lightness(claridade)
        melhor = candidata
        if contrast_ratio(fundo, candidata) >= minimo:
            return candidata

    # Não deu com a cor preservada: legibilidade ganha da fidelidade de matiz.
    return readable_on(fundo)


def readable_on(
    background: "str | Color",
    light: "str | Color" = "#ffffff",
    dark: "str | Color" = "#101014",
) -> Color:
    """A opção — clara ou escura — que tem mais contraste sobre o fundo dado."""
    bg = parse(background)
    cl, cd = parse(light), parse(dark)
    return cl if contrast_ratio(bg, cl) >= contrast_ratio(bg, cd) else cd
