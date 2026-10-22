"""Tokens de las ilustraciones (2026-10-19).

Contraste WCAG calculado (luminancia relativa), no a ojo:

    token        hex       sobre BACKGROUND  sobre PANEL  sobre STRIP_BG
    INK          #e0e7ff   14.49:1           13.60:1      14.92:1
    INK_2        #b6c2e2   10.03:1            9.42:1      10.33:1
    INK_3        #94a3c8    7.08:1            6.65:1       7.29:1
    TRACE        #22d3ee    9.88:1            9.28:1      10.17:1

`BACKGROUND`/`INK` son los mismos valores que `PALETTE.BACKGROUND`/
`PALETTE.TEXT` (`app/utils/design_system.py`); una prueba verifica que no
diverjan. Este módulo no importa Streamlit a propósito.
"""

BACKGROUND = "#0f172a"   # == PALETTE.BACKGROUND (fondo de la app)
PANEL = "#111d36"        # fondo de lámina (figura educativa)
STRIP_BG = "#0b1426"     # "vidrio de monitor" de la tira del encabezado

INK = "#e0e7ff"          # == PALETTE.TEXT -- texto principal
INK_2 = "#b6c2e2"        # texto secundario, etiquetas
INK_3 = "#94a3c8"        # líneas anatómicas, texto terciario (>= 6.6:1)
LINE = "#5d6b92"         # contornos tenues (solo decorativo, nunca texto)

TRACE = "#22d3ee"        # tinta de señal: el trazo que "se mide"
TRACE_SOFT = "#67e8f9"
TRACE_FILL = "rgba(34,211,238,0.14)"   # resaltado de la parte seleccionada
TEAL = "#099fbd"         # == PALETTE.PRIMARY (controles de la interfaz)

GRID = "#22d3ee"         # retícula milimétrica (se usa con opacidad baja)
GRID_MINOR_OPACITY = 0.07
GRID_MAJOR_OPACITY = 0.16

# Paleta categórica validada (skill de dataviz: CVD ΔE adyacente ≥ 8.4,
# visión normal ≥ 19.3, contraste ≥ 3:1 sobre #0f172a, modo oscuro). Mismo
# orden que `chartCategoricalColors` en `.streamlit/config.toml`. Solo para
# figuras con 2+ series (flujo vs. esfuerzo, etc.), siempre con leyenda.
SERIES = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")

# Colores de ESTADO clínico (PALETTE.STABLE/WARNING/CRITICAL): reservados.
# El arte decorativo nunca los usa -- prueba en tests/test_illustrations.py.
STATUS_RESERVED = ("#39d98a", "#ffc542", "#ff4d4d")

FONT_BODY = "'Noto Sans', 'Segoe UI', system-ui, sans-serif"
FONT_HEAD = "Figtree, 'Noto Sans', 'Segoe UI', system-ui, sans-serif"
