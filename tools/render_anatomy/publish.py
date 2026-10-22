"""Publica los renders en la app: out/*.png -> app/static/anatomy/*.webp + manifest.json.

El manifiesto guarda, por imagen, su tamaño, el texto alternativo, la
fuente de los datos y las "anclas": la posición en píxeles de cada punto
3D marcado en la escena (electrodos, V1-V6, nodos del sistema de
conducción), calculada por el propio renderizador con la cámara real.
La app dibuja encima los rótulos con SVG, así el texto queda nítido,
accesible y en español.
"""

from __future__ import annotations

import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DEST = os.path.join(REPO, "app", "static", "anatomy")

TS = ("Tomografía real de cuerpo completo: TotalSegmentator dataset v2, sujeto s1397 "
      "(Wasserthal et al., Radiology: AI 2023; CC BY 4.0)")
MNI = ("Cerebro: plantilla MNI ICBM 152 2009a (Fonov et al., NeuroImage 2009/2011; "
       "© McConnell Brain Imaging Centre, MNI)")
FS = ("Cabeza: superficie de fsaverage (FreeSurfer, Fischl et al. 1999) distribuida por MNE-Python; "
      "posiciones 10-20 de MNE-Python (BSD-3)")

IMAGES = {
    "organ_heart": ("Corazón real reconstruido de una tomografía, con la raíz de la aorta y las venas cavas", TS),
    "organ_lungs": ("Pulmones y tráquea reales reconstruidos de una tomografía", TS),
    "organ_brain": ("Cerebro de la plantilla MNI152, vista lateral izquierda, con sus circunvoluciones", MNI),
    "organ_muscles": ("Músculos erectores de la columna, glúteos e iliopsoas reales, vista posterior", TS),
    "organ_autonomic": ("Médula espinal real con el tramo T1-L2, de donde sale la vía simpática, resaltado", TS),
    "atlas_body": ("Cuerpo reconstruido de una tomografía real: esqueleto, corazón, vasos, pulmones, "
                   "encéfalo y órganos abdominales bajo la piel translúcida", TS),
    "atlas_precordial": ("Tórax real (costillas, cartílagos, esternón, corazón y pulmones) con los electrodos "
                         "V1 a V6 en las posiciones calculadas sobre esa tomografía", TS),
    "atlas_1020_top": ("Cabeza vista desde arriba con los 21 electrodos del sistema 10-20", FS),
    "atlas_1020_left": ("Cabeza vista desde la izquierda con los electrodos del sistema 10-20", FS),
    "atlas_heart": ("Corazón real reconstruido de una tomografía, vista anterior", TS),
}


def main(quality: int = 86) -> int:
    os.makedirs(DEST, exist_ok=True)
    manifest = {}
    for name, (alt, source) in IMAGES.items():
        png = os.path.join(HERE, "out", f"{name}.png")
        if not os.path.exists(png):
            print(f"falta {png}", file=sys.stderr)
            return 1
        img = Image.open(png).convert("RGBA")
        out = os.path.join(DEST, f"{name}.webp")
        img.save(out, "WEBP", quality=quality, method=6)
        anchors_path = os.path.join(HERE, "out", f"{name}.anchors.json")
        anchors = json.load(open(anchors_path)) if os.path.exists(anchors_path) else []
        manifest[name] = {
            "file": f"{name}.webp", "width": img.width, "height": img.height, "alt": alt, "source": source,
            "anchors": {a["id"]: [round(a["x"], 1), round(a["y"], 1), round(a.get("facing", 1.0), 3)]
                        for a in anchors},
        }
        print(f"- {name}.webp  {os.path.getsize(out) / 1024:.0f} KB  ({len(anchors)} anclas)")
    with open(os.path.join(DEST, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
