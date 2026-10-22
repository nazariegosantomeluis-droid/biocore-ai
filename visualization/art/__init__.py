"""Ilustraciones SVG originales de BIOCORE AI (2026-10-19, rediseño visual).

Todo aquí es SVG generado por código, sin dependencias de Streamlit, sin
imágenes externas ni de stock: cada trazo sale de una fórmula (las mismas
ondas que estudian los laboratorios) o de un esquema anatómico dibujado a
mano. Funciona sin internet (Modo Rural) y pesa unos pocos KB por imagen.

Reglas (ver CLAUDE.md, "Ilustraciones"):

- Una ilustración NO es un dato del paciente. Toda lámina lleva la etiqueta
  "Esquema ilustrativo" y, cuando muestra valores de referencia, su cita.
- Los colores de estado (`PALETTE.STABLE/WARNING/CRITICAL`) quedan reservados
  para estado clínico real; el arte decorativo usa la tinta de señal
  (`tokens.TRACE`) y tintas neutras. Hay una prueba que lo verifica.
- Accesible: `role="img"`, `<title>` y `<desc>` en cada SVG.

Módulos:
    tokens   -- colores y tipografía de las ilustraciones
    svg      -- utilidades (raíz accesible, trazos, retícula milimétrica)
    waves    -- ondas fisiológicas sintéticas deterministas (ECG, EEG, ...)
    glyphs   -- íconos de módulo y de órgano (trazo, 24×24 / 48×48)
    strips   -- la "tira de monitor" de cada encabezado de módulo
    plates   -- láminas educativas + el índice del Atlas visual
"""

from visualization.art.glyphs import MODULE_GLYPHS, ORGAN_GLYPHS, module_glyph_svg, organ_glyph_svg
from visualization.art.plates import ATLAS, PLATES, Plate, get_plate, plate_figure_html
from visualization.art.strips import STRIP_KINDS, signal_strip_svg

__all__ = [
    "ATLAS",
    "MODULE_GLYPHS",
    "ORGAN_GLYPHS",
    "PLATES",
    "Plate",
    "STRIP_KINDS",
    "get_plate",
    "module_glyph_svg",
    "organ_glyph_svg",
    "plate_figure_html",
    "signal_strip_svg",
]
