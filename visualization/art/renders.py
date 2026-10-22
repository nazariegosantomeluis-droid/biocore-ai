"""Renders de anatomía real (2026-10-21).

Imágenes generadas una sola vez (`tools/render_anatomy/`) a partir de las
mallas de `data/anatomy3d/` -- una tomografía real y plantillas MNI/fsaverage
-- y servidas como archivos estáticos (`app/static/anatomy/`). Sustituyen a
los dibujos planos de órganos y a las láminas anatómicas.

Cada imagen trae en `manifest.json` sus "anclas": la posición en píxeles de
los puntos 3D marcados al renderizar (electrodos 10-20, V1-V6, nodos del
sistema de conducción). Aquí se dibujan encima, en SVG, los rótulos y los
resaltados, para que el texto sea nítido, accesible y cambie con lo que la
persona elige sin volver a renderizar.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

from visualization.art.svg import esc, svg_root

STATIC_DIR = Path(__file__).resolve().parents[2] / "app" / "static" / "anatomy"
URL_PREFIX = "app/static/anatomy/"   # servido por server.enableStaticServing


@lru_cache(maxsize=1)
def manifest() -> Dict[str, dict]:
    path = STATIC_DIR / "manifest.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def available(name: str) -> bool:
    entry = manifest().get(name)
    return bool(entry) and (STATIC_DIR / entry["file"]).exists()


def entry(name: str) -> dict:
    return manifest()[name]


def size(name: str) -> Tuple[int, int]:
    e = entry(name)
    return int(e["width"]), int(e["height"])


def anchors(name: str) -> Dict[str, Tuple[float, float, float]]:
    """{id: (x, y, orientación)} en píxeles de la imagen; orientación > 0
    = el punto mira hacia la cámara (visible)."""
    return {k: (float(v[0]), float(v[1]), float(v[2])) for k, v in entry(name).get("anchors", {}).items()}


def url(name: str) -> str:
    return URL_PREFIX + entry(name)["file"]


def image_html(name: str, *, cls: str = "bc-render-img", alt: Optional[str] = None) -> str:
    """<img> del render, con su texto alternativo."""
    e = entry(name)
    return (f'<img class="{cls}" src="{url(name)}" width="{e["width"]}" height="{e["height"]}" '
            f'alt="{esc(e["alt"] if alt is None else alt)}" decoding="async">')


def figure_html(name: str, overlay: str = "", *, label: str = "", desc: str = "", cls: str = "") -> str:
    """Render + capa SVG del mismo tamaño encima (rótulos, resaltados).

    La capa usa el sistema de coordenadas de la imagen (viewBox = ancho ×
    alto en píxeles), así las anclas del manifiesto caen exactas a
    cualquier tamaño de pantalla."""
    w, h = size(name)
    layer = ""
    if overlay:
        layer = svg_root(w, h, overlay, label=label or entry(name)["alt"], desc=desc, cls="bc-render-layer")
    extra = f" {cls}" if cls else ""
    return (f'<div class="bc-render{extra}" style="aspect-ratio:{w}/{h}">'
            f'{image_html(name, alt="" if overlay else None)}{layer}</div>')


def source(name: str) -> str:
    return entry(name)["source"]
