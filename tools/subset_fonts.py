"""Recorta las fuentes Noto Sans del kit de marca a lo que la app muestra (optimización, 2026-11-18).

Las fuentes del kit (`docs/marca/.../NotoSans[wdth,wght].woff2` y su itálica) pesan 0.89 MB y 1.02 MB: traen cirílico,
vietnamita y otros alfabetos que la app no usa, y un eje de ancho (`wdth`) que ninguna página cambia. Esta herramienta:

1. fija el ancho en 100 (normal) y conserva el eje de peso (`wght`, 100–900), que sí se usa;
2. conserva los rangos latinos, el griego (bandas del EEG) y los signos de puntuación, flechas y símbolos matemáticos,
   MÁS todo carácter que aparezca en los textos de la app (`TEXT_DIRS`), para no perder ninguno;
3. guarda el resultado en WOFF2 en `app/static/marca/fuentes/`, que es lo que sirve Streamlit.

Los originales del kit no se tocan. La licencia (SIL OFL 1.1, sin nombre reservado) permite el subconjunto.
`tests/test_fuentes_subconjunto.py` falla si un texto nuevo usa un carácter que el kit tiene y el subconjunto no:
en ese caso, vuelve a correr `python tools/subset_fonts.py`. Necesita `fonttools` y `brotli`.
"""

from __future__ import annotations

import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "docs/marca/Biocore-Kit-de-marca-v1.1/02-Tipografias/Noto-Sans/Web-WOFF2"
OUT = ROOT / "app/static/marca/fuentes"
FONTS = {
    "NotoSans[wdth,wght].woff2": "noto-sans-latin-wght.woff2",
    "NotoSans-Italic[wdth,wght].woff2": "noto-sans-italic-latin-wght.woff2",
}
# Carpetas cuyos textos llegan a la pantalla (interfaz, contenido firmado, textos legales, rótulos de las señales).
TEXT_DIRS = ("app", "educational", "clinical", "src", "domain", "docs/contenido", "docs/legal")
TEXT_SUFFIXES = (".py", ".md", ".json", ".toml")
RANGES = (
    (0x0020, 0x024F),   # latín básico, latín-1 (acentos, «», ¿¡, °, ±, ×, µ, ²) y latín extendido A y B
    (0x0300, 0x036F),   # diacríticos combinables
    (0x0370, 0x03FF),   # griego (α, β, θ, δ, µ...)
    (0x2000, 0x206F),   # puntuación general (— – … · ‘’ “” •)
    (0x2070, 0x209F),   # superíndices y subíndices (SpO₂)
    (0x20A0, 0x20CF),   # monedas
    (0x2100, 0x214F),   # símbolos de letra (℃, №, Ω)
    (0x2190, 0x21FF),   # flechas (→ ← ↑ ↓ ↻ ⇒)
    (0x2200, 0x22FF),   # operadores matemáticos (≈ ≤ ≥ ≠ − √)
    (0x25A0, 0x25FF),   # figuras geométricas
    (0x2700, 0x27BF),   # dingbats (✓)
    (0xFB00, 0xFB06),   # ligaduras latinas
)


def app_characters() -> set:
    """Todo carácter no ASCII que aparece en los textos de la app."""
    chars = set()
    for folder in TEXT_DIRS:
        for path in (ROOT / folder).rglob("*"):
            if path.suffix in TEXT_SUFFIXES and path.is_file():
                chars.update(c for c in path.read_text(encoding="utf-8", errors="ignore") if ord(c) > 0x7E)
    return chars


def wanted_codepoints() -> set:
    codepoints = {cp for lo, hi in RANGES for cp in range(lo, hi + 1)}
    return codepoints | {ord(c) for c in app_characters()}


def build() -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    unicodes = sorted(wanted_codepoints())
    for source, target in FONTS.items():
        font = instancer.instantiateVariableFont(TTFont(KIT / source), {"wdth": 100})   # ancho fijo; el peso sigue variable
        buffer = io.BytesIO()                     # se guarda y se vuelve a abrir: el subconjunto no lee tablas a medias
        font.flavor = None
        font.save(buffer)
        buffer.seek(0)
        font = TTFont(buffer)
        options = subset.Options()
        options.layout_features = ["*"]           # cifras tabulares, ligaduras, kerning: todo lo que traía
        options.name_IDs = ["*"]
        options.name_languages = ["*"]
        options.notdef_outline = True
        options.flavor = "woff2"
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=unicodes)
        subsetter.subset(font)
        font.flavor = "woff2"
        font.save(OUT / target)
        print(f"{target}: {(OUT / target).stat().st_size / 1024:.0f} KB (antes {(KIT / source).stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
