"""Noto Sans recortada a lo que la app muestra (optimización, 2026-11-18).

- La app sirve los subconjuntos (`tools/subset_fonts.py`), no las fuentes completas del kit (0.87 y 1.0 MB).
- Ningún carácter que aparece en los textos de la app y que la fuente del kit tenía falta en el subconjunto. Si esta
  prueba falla tras agregar un texto, vuelve a correr `python tools/subset_fonts.py`.
- El eje de peso (100–900) sigue variable: los títulos y las cifras usan varios pesos.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("brotli")                      # leer WOFF2 con fontTools necesita brotli (requirements-dev.txt)
from fontTools.ttLib import TTFont  # noqa: E402


def _tool():
    spec = importlib.util.spec_from_file_location("subset_fonts", ROOT / "tools/subset_fonts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_app_serves_the_subsets_and_they_are_light():
    tool = _tool()
    theme = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))["theme"]
    noto = {f["url"] for f in theme["fontFaces"] if f["family"] == "Noto Sans"}
    assert noto == {f"app/static/marca/fuentes/{name}" for name in tool.FONTS.values()}
    for url in noto:
        assert (ROOT / url).stat().st_size < 250 * 1024, url


def test_no_character_the_app_shows_is_lost():
    tool = _tool()
    chars = tool.app_characters()
    for source, target in tool.FONTS.items():
        kit = set(TTFont(tool.KIT / source).getBestCmap())
        served = set(TTFont(tool.OUT / target).getBestCmap())
        lost = sorted(chr(cp) for cp in ({ord(c) for c in chars} & kit) - served)
        assert lost == [], (target, lost)


def test_the_weight_axis_stays_variable():
    tool = _tool()
    for target in tool.FONTS.values():
        axes = {a.axisTag: (a.minValue, a.maxValue) for a in TTFont(tool.OUT / target)["fvar"].axes}
        assert axes == {"wght": (100, 900)}, (target, axes)
