"""Sistema de diseño compartido de BIOCORE AI (2026-08-24, Capa 2, Fase
2.3, Tanda 1; consolidado 2026-09-20, Consolidación Visual Tanda 1).

CONSOLIDACIÓN VISUAL, TANDA 1 (2026-09-20): el diagnóstico de rediseño
visual (ver CHANGELOG.md) encontró que Fase 2.3 dejó cuatro cabos sin
resolver -- esta tanda los cierra, aditivamente, sin tocar ninguna
función de Fase 2.3:

1. Dos ejes de honestidad con vocabularios dispersos (`BIOMARKER_*_BADGE`
   en `app/main.py`, `PROVENANCE_*_BADGE` en `twin_shell/pages.py`, un
   literal `"🟢🔵"` suelto) que ya eran alias de `BADGES` en valor pero no
   en nombre -- y, más grave, una colisión semántica real entre los dos
   EJES de honestidad (ver `GRAMMAR_SEVERITY`/`GRAMMAR_NEUTRAL_STATE` más
   abajo).
2. Ninguna superficie compartida para la tarjeta de métrica+badge -- la
   pieza de UI más repetida de toda la app, sin helper (ver
   `render_metric_card()`).
3. `render_module_header()` daba el mismo peso visual de marca a todo
   módulo sin importar su nivel de validación -- la fachada visual que
   el diagnóstico señaló como el hallazgo central (ver el parámetro
   `validation` de `render_module_header()`).
4. CSS global paralelo (`inject_biocore_css()` en `app/main.py`, un
   degradado cian con clases muertas que ganaba visualmente sobre
   `.streamlit/config.toml`) -- ver `inject_global_theme()`.

El recon de la Fase 2.3 original encontró 52 colores hexadecimales distintos sin
ninguna fuente única en toda la app, 4 mecanismos distintos para declarar
el título de un módulo (`st.markdown("<h1>...")`, `st.markdown("<h2>...")`,
`st.header()`, `st.title()` -- ninguno acordado, y Digital Twin OS sin
ninguno de los cuatro), los badges de procedencia de la Capa 3 duplicados
como código en dos sitios (`BIOMARKER_*_BADGE` en `app/main.py` y
`PROVENANCE_*_BADGE` en `app/supermodules/twin_shell/pages.py`, mismos
valores, cero fuente compartida), y los 24 sitios que muestran un error
usando `st.error(f"...{e}")` -- la traza cruda de Python expuesta
directamente al usuario.

Este módulo NO rediseña desde cero: la paleta de estado (`STABLE`/
`WARNING`/`CRITICAL`/`NEUTRAL`) se PROMUEVE de
`app/supermodules/twin_shell/ups_body_visual.py`, que ya la usaba de forma
interna y coherente para colorear el corazón/pulmones del gemelo -- es,
sin haber sido declarado como tal, el diseño más consistente que ya existía
en el repo. Aquí se formaliza como fuente única para que el resto de la
app pueda usarla también, en vez de que cada módulo reinvente su propio
verde/amarillo/rojo.

Alcance de la Tanda 1 (Fase 2.3, Parte B): crea la fuente única y las 4
funciones de UI. NO migra los ~10 módulos que hoy tienen su propio patrón
-- eso son tandas posteriores, cada una verificada por ejecución antes de
tocar el siguiente lote (la lección de Respiratory: nunca asumir que un
cambio presentacional no puede romper el render). Solo 2 módulos piloto
(Digital Twin OS + un lab) usan este sistema en esta tanda -- ver
CHANGELOG.md para cuáles y su verificación.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Union

import streamlit as st

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# PALETA -- fuente única. Mismos 4 tokens que .streamlit/config.toml
# ([theme]), citados por nombre para que ningún valor se declare dos veces
# con la posibilidad de que diverjan. STABLE/WARNING/CRITICAL/NEUTRAL:
# promovidos tal cual de `twin_shell/ups_body_visual.py` (SEVERITY_COLOR/
# NEUTRAL_COLOR/STABLE_COLOR) -- ese archivo sigue siendo la fuente
# original citable; este módulo es ahora el punto de import compartido.
# ═══════════════════════════════════════════════════════════════════════

class PALETTE:
    """Colores de marca y de fondo. Ratios de contraste WCAG verificados
    por cálculo (fórmula de luminancia relativa estándar), no a ojo -- ver
    CHANGELOG.md para la tabla completa.

    `PRIMARY` es el `primaryColor` de `.streamlit/config.toml` -- pensado
    para los CONTROLES nativos de Streamlit (fondo de botones/sliders,
    donde el contraste que importa es con el texto que Streamlit dibuja
    encima, ~6.70:1 con texto blanco). NO usar `PRIMARY` como color de
    TEXTO directo sobre `BACKGROUND` -- da 2.66:1, reprueba incluso WCAG AA
    (mínimo 4.5:1 para texto normal). Para encabezados/íconos sobre fondo
    oscuro, usar `ACCENT_ON_DARK` (9.98:1, AAA)."""

    # Tanda 1 de la fase 1 (2026-11-15): ÚNICA fuente de color de la app (decisiones 4-6). `.streamlit/config.toml`
    # repite PRIMARY/BACKGROUND/SECONDARY_BACKGROUND/TEXT (Streamlit no puede leer Python) y una prueba exige que
    # coincidan; ningún otro archivo declara un color de estado ni un gris de «sin dato». Ratios WCAG por par en
    # `CONTRAST_PAIRS` (abajo), verificados por `tests/test_fase1_t1_diseno.py`.
    # Kit de marca v1.1 (docs/marca, tokens Monitor; 2026-11-17): Núcleo para lo que se toca, Trazo como único color vivo.
    PRIMARY = "#099fbd"           # token `nucleo`: botones, pestaña activa, controles. 5.70:1 sobre BACKGROUND
    ACCENT_ON_DARK = "#22d3ee"    # token `trazo`/`enlace`: enlaces, foco y primera serie de gráficas. 9.88:1
    TINTA_TITULO = "#f1f5ff"      # token `tinta-titulo`: títulos de módulo. 16.36:1
    TINTA_2 = "#b6c2e2"           # token `tinta-2`: texto secundario. 10.03:1
    PANEL = "#111d36"             # token `fondo-panel`
    RESALTE = "#133650"           # token `trazo-resalte` (Trazo al 14 %) ya compuesto sobre PANEL: fondo con el cursor encima
    BACKGROUND = "#0f172a"
    SECONDARY_BACKGROUND = "#1a2a4a"
    TEXT = "#e0e7ff"

    # Estado clínico: UNA paleta (decisión 4; se retiraron #39ffbe/#ff3333/#ffd700/#ff4d4d/#22c55e/#ef4444...). El color
    # de estado va SIEMPRE con una palabra; nunca solo.
    STABLE = "#39d98a"
    WARNING = "#ffc542"
    CRITICAL = "#ff6464"          # antes #ff4d4d: 4.92:1 sobre SECONDARY_BACKGROUND (AA); lejos del tejido arterial atenuado
    NEUTRAL = "#94a3c8"           # token `tinta-3` (rótulos): «sin dato», heurístico. El `estado-neutral` del kit
                                  # (#64748b) da 3.75:1 como texto, no AA; tinta-3 da 7.08:1
    ON_STATE = "#0f172a"          # texto SOBRE un relleno de estado (STABLE/WARNING/CRITICAL): nunca blanco

    # Gráficas (no son texto: contraste >= 3:1 de objeto gráfico)
    GRID = "#334155"
    # Acento de marca (2026-11-17, PROVISIONAL): el cian del trazo, único color vivo de cada vista según el manual de marca
    # v1.1. El kit todavía no está en el repositorio; el valor sale de `visualization/art/tokens.py` (TRACE, rama
    # respaldo-mezcla-20261021) y se reemplaza por el token `trazo` del kit en cuanto llegue. Texto encima: ON_STATE.
    TRAZO = "#22d3ee"             # token `trazo` del kit v1.1 (confirmado; antes provisional)
    SERIES_2 = "#c4b5fd"

    # Diagramas de cableado y marcas de ondas de los tutoriales de hardware (integración 2026-11-16): colores
    # categóricos para distinguir cables o puntos dibujados, siempre con su rótulo al lado; no son estado clínico.
    WIRE_ORANGE = "#fb923c"
    SENSOR_BOARD = "#7f1d1d"
    DIAGRAM_SERIES = (CRITICAL, NEUTRAL, STABLE, WARNING, WIRE_ORANGE, ACCENT_ON_DARK)

    # Papel ECG (pulido profesional, 2026-11-16; `app/utils/ecg_paper.py`). Se midieron dos variantes; queda la de papel
    # (fondo claro, cuadrícula rojiza, trazo oscuro) porque cumple AA con más margen: trazo/papel 17.99:1,
    # trazo/línea gruesa 4.96:1, línea gruesa/papel 3.62:1. La oscura (`*_DARK`) también cumple (15.20, 4.62, 3.29) y
    # queda medida en `CONTRAST_PAIRS` como alternativa. La línea fina (1 mm) subdivide la gruesa y no se lee sola.
    ECG_PAPER = "#fff8f6"
    ECG_GRID_MAJOR = "#d0605f"
    ECG_GRID_MINOR = "#f2c4c4"
    ECG_TRACE = "#111111"
    ECG_LABEL = "#7a1f1f"                # nombre de la derivación y rótulo de escala sobre el papel
    ECG_PAPER_DARK = "#0b1220"
    ECG_GRID_MAJOR_DARK = "#a14c58"
    ECG_GRID_MINOR_DARK = "#40283a"
    ECG_TRACE_DARK = TEXT
    ECG_LABEL_DARK = "#f2b8b8"


# Pares (frente, fondo, mínimo WCAG) que la prueba de contraste exige: 4.5 texto normal, 3.0 objeto gráfico.
CONTRAST_PAIRS = (
    ("TEXT", "BACKGROUND", 4.5), ("TEXT", "SECONDARY_BACKGROUND", 4.5),
    ("PRIMARY", "BACKGROUND", 4.5), ("ACCENT_ON_DARK", "BACKGROUND", 4.5), ("ACCENT_ON_DARK", "SECONDARY_BACKGROUND", 4.5),
    ("STABLE", "BACKGROUND", 4.5), ("STABLE", "SECONDARY_BACKGROUND", 4.5),
    ("WARNING", "BACKGROUND", 4.5), ("WARNING", "SECONDARY_BACKGROUND", 4.5),
    ("CRITICAL", "BACKGROUND", 4.5), ("CRITICAL", "SECONDARY_BACKGROUND", 4.5),
    ("NEUTRAL", "BACKGROUND", 4.5), ("NEUTRAL", "SECONDARY_BACKGROUND", 4.5),
    ("ON_STATE", "STABLE", 4.5), ("ON_STATE", "WARNING", 4.5), ("ON_STATE", "CRITICAL", 4.5),
    ("ON_STATE", "PRIMARY", 4.5), ("ON_STATE", "ACCENT_ON_DARK", 4.5),     # botón principal: reposo y cursor encima
    ("PRIMARY", "SECONDARY_BACKGROUND", 3.0), ("SERIES_2", "SECONDARY_BACKGROUND", 3.0),
    ("TRAZO", "BACKGROUND", 4.5), ("TRAZO", "SECONDARY_BACKGROUND", 4.5), ("ON_STATE", "TRAZO", 4.5),
    ("TINTA_TITULO", "BACKGROUND", 4.5), ("TINTA_TITULO", "SECONDARY_BACKGROUND", 4.5),
    ("TINTA_2", "BACKGROUND", 4.5), ("TINTA_2", "SECONDARY_BACKGROUND", 4.5), ("TEXT", "PANEL", 4.5),
    ("TEXT", "RESALTE", 4.5), ("TINTA_TITULO", "RESALTE", 4.5), ("TRAZO", "RESALTE", 3.0),   # cursor encima
    ("NEUTRAL", "PANEL", 4.5), ("TINTA_2", "PANEL", 4.5),   # menú lateral sobre PANEL (2026-11-18)
    # Papel ECG: trazo y rótulos son texto (4.5); la línea gruesa (5 mm) es el objeto gráfico con el que se lee (3.0) y
    # el trazo debe destacar sobre ella (3.0). Las dos variantes medidas.
    ("ECG_TRACE", "ECG_PAPER", 4.5), ("ECG_LABEL", "ECG_PAPER", 4.5),
    ("ECG_GRID_MAJOR", "ECG_PAPER", 3.0), ("ECG_TRACE", "ECG_GRID_MAJOR", 3.0),
    ("ECG_TRACE_DARK", "ECG_PAPER_DARK", 4.5), ("ECG_LABEL_DARK", "ECG_PAPER_DARK", 4.5),
    ("ECG_GRID_MAJOR_DARK", "ECG_PAPER_DARK", 3.0), ("ECG_TRACE_DARK", "ECG_GRID_MAJOR_DARK", 3.0),
)


def relative_luminance(hex_color: str) -> float:
    """Luminancia relativa WCAG 2.x de un color `#rrggbb`."""
    h = hex_color.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ═══════════════════════════════════════════════════════════════════════
# BADGES DE PROCEDENCIA -- fuente única (2026-08-24). Reemplazó las dos
# definiciones gemelas (`BIOMARKER_*_BADGE` en app/main.py,
# `PROVENANCE_*_BADGE` en twin_shell/pages.py) -- ambas son alias directos
# de esta clase desde Fase 2.3 (mismo valor, dos nombres -- la duplicación
# de VALOR ya no existe, la de nombre queda para una migración de rótulos
# futura, no bloqueante). Consolidación Visual Tanda 1 (2026-09-20): el
# único literal suelto que quedaba sin pasar ni siquiera por un alias
# (`"🟢🔵"` en `twin_shell/pages.py`) se corrigió para usar las constantes
# ya importadas ahí mismo.
# ═══════════════════════════════════════════════════════════════════════

class BADGES:
    """Etiquetas de procedencia (Eje A: de dónde viene el dato). Tanda 1 de la fase 1 (decisión 3): cada constante es
    TEXTO, nunca un círculo de color (antes, un emoji de color por nivel); el color queda para el estado clínico.
    `BADGES.label(b)` = nombre + qué significa (texto plano: captions, `help=`, exportes); `BADGES.tag(b)` = «[nombre]»
    para anteponer a una frase; `badge_html(b)` = la etiqueta visual (borde y texto neutros) de las tarjetas."""

    CLINICAL = "Validado por fuente"       # fórmula o criterio con cita verificable
    HEURISTIC = "Heurística"               # cálculo real con constante/ponderación de ingeniería
    GHOST = "Sin fuente"                   # entrada sin fuente real (Capa 3 los retiró de producción)
    METHOD = "Criterio BIOCORE"            # metodología propia declarada como tal
    PENDING = "Pendiente de validación"    # se calcula, el criterio no está validado (PENDING_VALIDATION)
    SIMULATION = "Simulación"              # señal o escenario simulado, no una medición de un paciente

    _LABELS = {
        CLINICAL: "fórmula o criterio con cita verificable",
        HEURISTIC: "de ingeniería, no de estudio de cohorte",
        GHOST: "entrada sin fuente real disponible",
        METHOD: "metodología propia o valor BIOCORE, no un estándar clínico",
        PENDING: "se calcula; el criterio no está validado",
        SIMULATION: "no es una medición de un paciente",
    }

    @classmethod
    def label(cls, badge: str) -> str:
        """Nombre + significado, en texto: «Heurística (de ingeniería, no de estudio de cohorte)»."""
        meaning = cls._LABELS.get(badge)
        return f"{badge} ({meaning})" if meaning else badge

    @classmethod
    def tag(cls, badge: str) -> str:
        """«[Validado por fuente]»: la etiqueta corta para anteponer a una frase o a una celda."""
        return f"[{badge}]"


def badge_html(badge: str) -> str:
    """La etiqueta de procedencia visual: texto (`BADGES.label`) con borde y color NEUTROS (decisión 3)."""
    return (f"<span class='biocore-prov' style='border:1px solid {PALETTE.NEUTRAL}; border-radius:999px; "
            f"padding:0 8px; color:{PALETTE.TEXT}; font-size:0.85em; white-space:normal;'>{BADGES.label(badge)}</span>")


# ═══════════════════════════════════════════════════════════════════════
# GRAMÁTICAS DE CLASIFICACIÓN CLÍNICA -- Eje B (2026-09-20, Consolidación
# Visual Tanda 1). `BADGES` de arriba es el Eje A (de dónde viene el
# dato). Este es un eje DISTINTO: qué significa clínicamente un valor ya
# calculado -- lo que devuelven `classify_dar()`/`classify_tbr()`
# (`src/signals/eeg/eeg_analyzer.py`) y `classify_chi()`
# (`src/signals/eeg/spectral_model.py`) como `(nivel, etiqueta, badge)`.
#
# El diagnóstico encontró una colisión real: DAR/TBR usan 🟢/🟡/🔴 como
# semáforo de peligro (verde=bien, rojo=mal); χ usa 🔴/🔵/💤 para un
# estado SIN valencia de peligro (🔴 ahí significa "excitación", no
# "alarma"). Mismo emoji rojo, significado opuesto. La solución NO toca
# ninguna función `classify_*()` -- sus badges (los emoji que ya citan
# DAR_CITATION/TBR_CITATION/CHI_CITATION) se quedan exactamente igual, en
# el mismo lugar de siempre. Lo que cambia es el MARCO que `render_metric_
# card()` dibuja alrededor: la gramática decide el color del borde, no el
# badge.
#
# GRAMMAR_SEVERITY ("severidad"): semáforo verde→ámbar→rojo. El color del
# marco SIGUE el nivel devuelto (normal/leve/severo -> STABLE/WARNING/
# CRITICAL) -- refuerza el badge, no lo contradice.
# GRAMMAR_NEUTRAL_STATE ("estado_neutro"): sin valencia de peligro. El
# marco es SIEMPRE `PALETTE.ACCENT_ON_DARK`, sin importar cuál de los
# niveles salga -- para que un 🔴 de "excitación cortical" nunca quede
# enmarcado como si fuera una alerta de isquemia.
#
# Mapa biomarcador -> gramática (documentado aquí porque es la ÚNICA
# fuente de esta decisión; no se repite en otro archivo):
#   - DAR (Delta/Alfa, Claassen 2004)            -> GRAMMAR_SEVERITY
#   - TBR (Theta/Beta, Boksem 2005)               -> GRAMMAR_SEVERITY
#   - χ / chi_aperiodic (Gao/Voytek 2017)          -> GRAMMAR_NEUTRAL_STATE
#   - Engagement β/(α+θ) relativo (Pope 1995)      -> GRAMMAR_NEUTRAL_STATE
#     (firma del experto 2026-10-18: estado operativo, no diagnóstico; su
#     classification es solo la dirección ↑/↓, ver `engagement_detector.py`)
#   - BAR (Beta/Alfa, Schutter 2006)               -> AMBIGUO, ver nota
#
# BAR queda marcado AMBIGUO a propósito, no forzado: hoy se renderiza como
# `"⚠️ >1.8 arousal"` o nada (`eeg_neuro_lab/page_content.py`), sin pasar
# por un `classify_*()` de 3 niveles. "Arousal" alto no es intrínsecamente
# malo (es un estado, como χ) pero el `⚠️` que ya usa sugiere que sí se
# lee como aviso. Antes de darle una de las dos gramáticas hace falta que
# alguien con criterio clínico (Luis) decida si el arousal cortical alto
# es "un estado a describir" o "un umbral a vigilar" -- esta tanda NO lo
# fuerza, solo dimensiona por qué es un caso aparte de los otros tres.
# ═══════════════════════════════════════════════════════════════════════

GRAMMAR_SEVERITY = "severidad"
GRAMMAR_NEUTRAL_STATE = "estado_neutro"

# `nivel` (primer elemento de la tupla que devuelven classify_dar/
# classify_tbr) -> color de marco, SOLO para GRAMMAR_SEVERITY. classify_chi
# usa nombres de nivel distintos (excitacion/indeterminado/inhibicion) a
# propósito -- bajo GRAMMAR_NEUTRAL_STATE ninguno de esos tres nombres
# pasa por este diccionario, así que no hace falta declararlos aquí.
_SEVERITY_LEVEL_COLOR = {
    "normal": PALETTE.STABLE,
    "leve": PALETTE.WARNING,
    "severo": PALETTE.CRITICAL,
    "no_disponible": PALETTE.NEUTRAL,
}


# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES DE UI
# ═══════════════════════════════════════════════════════════════════════

# Consolidación Visual, Tanda Final (2026-09-22): "VALIDATED"/"HEURISTIC"
# -- vocabulario FORMAL de la firma del experto (Luis), reemplaza los
# nombres provisionales en español minúscula de Tanda 1
# ("validado"/"heuristico") en TODO el repo -- transcripción, no una
# tercera convención en paralelo. Ver CHANGELOG.md para las 9 firmas.
_VALIDATION_TIER_STYLE = {
    # (color de marco, símbolo) -- deliberadamente NO usa STABLE/WARNING/
    # CRITICAL para "HEURISTIC": ser heurístico no es un aviso de peligro
    # (mismo criterio que separó GRAMMAR_SEVERITY de GRAMMAR_NEUTRAL_STATE
    # arriba) -- es un nivel de confianza distinto, no una alarma. Usa
    # NEUTRAL (el mismo tono ya reservado para "sin dato"/"sin alarma").
    "VALIDATED": (PALETTE.STABLE, "✓"),
    "HEURISTIC": (PALETTE.NEUTRAL, "◇"),
}


def render_module_header(
    title: str,
    icon: str = "",
    subtitle: Optional[str] = None,
    *,
    validation: Optional[str] = None,
    validation_detail: Optional[str] = None,
) -> None:
    """Título de módulo -- un solo estilo para todos, reemplaza los 4
    mecanismos encontrados en el recon (`<h1>`/`<h2>` a mano, `st.header()`,
    `st.title()`, o ninguno -- el caso de Digital Twin OS antes de esta
    tanda). `icon` es un emoji, igual que ya usa cada módulo en su título.

    `validation`/`validation_detail` (Consolidación Visual Tanda 1,
    2026-09-20; vocabulario formal transcrito en la Tanda Final,
    2026-09-22): la jerarquía visual de confianza -- el hallazgo central
    del diagnóstico fue que TODO módulo recibía el mismo peso de marca sin
    importar su madurez de validación (un combinador heurístico como
    Multisensor se veía tan autorizado como el detector TKEO de ECG,
    validado en 6 rondas contra 25 registros MIT-BIH). Ambos parámetros
    son `None` por default -- ningún llamador existente cambia de
    apariencia sin que alguien lo decida explícitamente. Cuando se pasan:
    `validation="VALIDATED"` (marco STABLE, ✓) para un módulo con firma
    del experto citando el estándar/cohorte que lo respalda;
    `validation="HEURISTIC"` (marco NEUTRAL, ◇ -- NUNCA un color de
    alarma, ser heurístico no es un peligro) para un módulo cuya firma
    declara explícitamente que NO está validado contra literatura/cohorte
    (cálculo real, sin esa validación). `validation_detail` es el texto
    VERBATIM de la firma del experto -- sin él, el nivel por sí solo
    (`validation` crudo) es la etiqueta, honesto pero menos útil que la
    cita real. `validation=None` explícito (no solo el default implícito)
    es su propio tercer estrato deliberado -- un módulo mixto donde una
    etiqueta única mentiría sobre alguna de sus partes (ver EEG Neuro Lab),
    o donde el concepto de validación clínica no aplica (ver Patient
    Pipeline, infraestructura ETL) -- SIEMPRE con un comentario en el
    sitio de la llamada que registre por qué, para que no se lea como un
    olvido. Valores fuera de `_VALIDATION_TIER_STYLE` se ignoran
    silenciosamente en vez de fallar -- un typo en `validation` no debe
    tirar la página completa."""
    header_text = f"{icon} {title}".strip()
    st.markdown(
        f"<h1 style='color:{PALETTE.TINTA_TITULO}; margin-bottom:0;'>{header_text}</h1>",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f"<p style='color:{PALETTE.TEXT}; opacity:0.75; margin-top:0;'>{subtitle}</p>",
            unsafe_allow_html=True,
        )
    render_validation_marker(validation, validation_detail)


def render_validation_marker(validation: Optional[str], validation_detail: Optional[str] = None) -> None:
    """La marca de validación de `render_module_header()`, sola -- para una
    SECCIÓN dentro de un módulo mixto cuya parte validada merece su marca sin
    que el módulo entero la lleve (p.ej. el brazo vascular del barorreflejo
    en Digital Twin OS). No dibuja nada si `validation` no es un nivel
    conocido."""
    marker = resolve_validation_marker(validation, validation_detail)
    if marker is not None:
        color, symbol, text = marker
        st.markdown(
            f"<div style='border-left:3px solid {color}; padding:4px 10px; margin:2px 0 12px 0; "
            f"color:{PALETTE.TEXT}; opacity:0.92; font-size:0.92rem;'>{symbol}&nbsp;&nbsp;{text}</div>",
            unsafe_allow_html=True,
        )


@dataclass(frozen=True)
class TheoryTopic:
    """Un tema de teoría en tres capas (tanda 2 de la fase 1). Toda capa es OPCIONAL: una capa sin contenido con
    fuente se omite, nunca se rellena. `detail` es texto Markdown o una función que dibuja (p. ej. una tabla)."""

    title: str
    idea: Optional[str] = None                                  # capa 1: la idea en una frase (siempre a la vista)
    mechanism: Optional[str] = None                             # capa 2: el mecanismo (a demanda)
    detail: Optional[Union[str, Callable[[], None]]] = None     # capa 3: el detalle (a demanda), con su fuente
    source: Optional[str] = None                                # cita o etiqueta del detalle
    image: Optional[str] = None                                 # solo una imagen que ya exista en el repositorio


THEORY_NO_SOURCE = "no citada en el repositorio (contenido pendiente de firma)"

# Pulido profesional (2026-11-16, Parte C): cada laboratorio es UNA página (sin «Capa de Exploración Cognitiva»):
# arriba el trazo y los valores clave; debajo, plegadas, estas secciones (las que el laboratorio tenga).
LAB_SECTION_HOW = "Cómo se calcula"
LAB_SECTION_SIMULATE = "Simular"
LAB_SECTION_THEORY = "Teoría"
LAB_SECTION_AI = "Narración con IA (opcional)"


def render_theory_topic(topic: TheoryTopic, inside_expander: bool = False) -> None:
    """El ÚNICO componente de teoría: idea (con su imagen si existe) a la vista; mecanismo y detalle a demanda.
    `inside_expander`: el tema ya está dentro de un expander (Streamlit no permite anidarlos); las capas 2 y 3 van
    seguidas, cada una con su rótulo."""
    import contextlib

    def layer(label):
        if inside_expander:
            st.markdown(f"**{label}**")
            return contextlib.nullcontext()
        return st.expander(label)

    st.markdown(f"#### {topic.title}")
    if topic.image:
        st.image(topic.image)
    if topic.idea:
        st.markdown(topic.idea)
    if topic.mechanism:
        with layer("¿Cómo funciona? — mecanismo"):
            st.markdown(topic.mechanism)
    if topic.detail:
        with layer("Detalle y fuente"):
            if callable(topic.detail):
                topic.detail()
            else:
                st.markdown(topic.detail)
            st.caption(f"Fuente: {topic.source or THEORY_NO_SOURCE}")
            if topic.source and re.search(r"\[[A-Z0-9]+\]", topic.source):
                # Pulido profesional: las claves firmadas ([K2007], [MCM]...) enlazan a la página Bibliografía.
                from app.utils import navigation as nav

                nav.link("bibliografia", "Referencias completas en Bibliografía", icon="📚")
    elif topic.source and re.search(r"\[[A-Z0-9]+\]", topic.source):
        # Teoría citada 2: un tema firmado sin capa de detalle también lleva su clave y el enlace a la Bibliografía.
        from app.utils import navigation as nav

        st.caption(f"Fuente: {topic.source}")
        nav.link("bibliografia", "Referencias completas en Bibliografía", icon="📚")


def render_section_header(title: str) -> None:
    """Encabezado de sección (Vista Clínica, etc.) -- `<h2>` sin acento de
    color, para que la jerarquía con `render_module_header()` (que sí lleva
    color) sea visible de un vistazo, no dos títulos compitiendo por
    atención."""
    st.markdown(f"<h2>{title}</h2>", unsafe_allow_html=True)


def render_empty_state(message: str, action: Optional[str] = None) -> None:
    """Estado de "aún no hay datos" -- extiende el patrón que
    `render_ups_body()` ya usa para "sin snapshot del UPS todavía"
    (`ups_body_visual.py`), formalizado para que cualquier módulo lo use
    igual en vez de un `st.info()` suelto por módulo."""
    icon_html = f"<span style='font-size:1.3em;'>○</span>"
    text = message if not action else f"{message} — {action}"
    st.markdown(
        f"<div style='border:1px solid {PALETTE.NEUTRAL}; border-radius:8px; padding:12px 16px; "
        f"color:{PALETTE.TEXT};'>{icon_html}&nbsp;&nbsp;{text}</div>",
        unsafe_allow_html=True,
    )


def no_data_html(what: str, reason: Optional[str] = None) -> str:
    """El ÚNICO «sin dato» de la plataforma, como HTML (para incrustarlo en tarjetas): dice QUÉ falta y, si se sabe,
    por qué. Texto en `PALETTE.NEUTRAL` con contraste AA y un «○» que no depende del color (tanda 1 de la fase 1)."""
    detail = f"Sin dato: falta {what}" + (f" — {reason}" if reason else "")
    return (f"<span class='biocore-no-data' style='color:{PALETTE.NEUTRAL};'>○ {detail}</span>")


def render_no_data(what: str, reason: Optional[str] = None) -> None:
    """`no_data_html` como bloque de la página (con borde neutro)."""
    st.markdown(
        f"<div style='border:1px solid {PALETTE.NEUTRAL}; border-radius:8px; padding:10px 14px; margin:4px 0;'>"
        f"{no_data_html(what, reason)}</div>",
        unsafe_allow_html=True,
    )


def render_error_state(message: str, exception: Optional[BaseException] = None) -> None:
    """Estado de error -- caja con el acento CRITICAL, mensaje limpio para
    el usuario. Si se pasa `exception`, la traza completa se manda al
    logger (`logging`, nivel ERROR, con stack trace) -- NUNCA se muestra al
    usuario. Reemplaza el patrón `st.error(f"Error: {e}")` (24 sitios en el
    repo, ver recon de la Fase 2.3) que hoy expone el mensaje crudo de la
    excepción de Python en pantalla -- exactamente lo que más delata
    "prototipo" en una demo. Migrar esos 24 sitios a esta función es una
    tanda posterior; aquí solo se crea la función, verificada de que
    loguea sin filtrar la traza a la UI."""
    if exception is not None:
        logger.error("render_error_state: %s", message, exc_info=exception)
    st.markdown(
        f"<div style='border-left:4px solid {PALETTE.CRITICAL}; border-radius:4px; "
        f"background:rgba(255,77,77,0.08); padding:12px 16px; color:{PALETTE.TEXT};'>"
        f"⚠️&nbsp;&nbsp;{message}</div>",
        unsafe_allow_html=True,
    )


AI_FEEDBACK_OFF_MESSAGE = (
    "Sin clave de IA: la calificación funciona igual (la decide el código, no la IA); solo el "
    "feedback narrado queda apagado. Para activarlo, pon tu clave en <b>Ajustes</b> (menú lateral), o tu "
    "<code>ANTHROPIC_API_KEY</code> en <code>.env</code>."
)


def render_ai_feedback_off_notice() -> None:
    """Aviso informativo (no de error) para flujos donde la IA es un EXTRA
    sobre un resultado determinista, como el quiz. Antes ese flujo no hacía
    nada sin clave aunque la respuesta correcta nunca dependió del modelo.
    Art. I intacto: sin clave no se muestra ningún texto "como si" fuera IA,
    solo este aviso."""
    st.markdown(
        f"<div style='border-left:3px solid {PALETTE.NEUTRAL}; padding:6px 12px; margin:4px 0 10px 0; "
        f"color:{PALETTE.TEXT}; font-size:0.92rem;'>{AI_FEEDBACK_OFF_MESSAGE}</div>",
        unsafe_allow_html=True,
    )
    from app.utils.navigation import link

    link("ajustes", "Ir a Ajustes para poner tu clave", icon="⚙️")


@dataclass(frozen=True)
class MetricCardData:
    """Resultado YA RESUELTO de aplicar las reglas de honestidad a una
    métrica -- Consolidación Visual Tanda 2 (2026-09-21). Es la ÚNICA
    fuente que consumen `render_metric_card()` (Streamlit, esta app) y
    `metric_card_to_html()` (`app/reporting.py`, el export que sale de la
    app sin runtime de Streamlit alrededor). Ninguno de los dos
    renderizadores decide badge/color/orden por su cuenta -- ambos solo
    formatean lo que `resolve_metric_card()` ya decidió. Si mañana cambia
    un umbral, una cita o un color de gramática, cambia en `resolve_
    metric_card()` y los DOS renderizadores lo heredan sin tocarlos."""

    label: str
    value: Optional[str]
    border_color: str
    detail_parts: Tuple[str, ...] = ()
    reason: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.value is not None


def resolve_metric_card(
    label: str,
    value: Optional[str] = None,
    *,
    provenance: Optional[str] = None,
    classification: Optional[Tuple[str, str, str]] = None,
    grammar: str = GRAMMAR_SEVERITY,
    citation: Optional[str] = None,
    unavailable_reason: Optional[str] = None,
) -> MetricCardData:
    """La lógica de honestidad de una tarjeta de métrica, SIN Streamlit ni
    HTML -- decide badge/color/orden a partir de valores YA calculados por
    el llamador (`value`, y opcionalmente la tupla que ya devolvió un
    `classify_*()`), misma separabilidad estilo/datos que ya demuestran
    `classify_dar()`/`classify_chi()` al no depender de cómo se pintan.
    `render_metric_card()` y `metric_card_to_html()` son capas de
    presentación finas sobre esto -- ver `MetricCardData`.

    Dos ejes de honestidad, cada uno OPCIONAL e independiente:

    - `provenance` (Eje A -- de dónde viene el dato): un valor de
      `BADGES` (`BADGES.CLINICAL`/`HEURISTIC`/`METHOD`/`GHOST`).
      Formateado con `BADGES.label()` -- el formateador que ya existía sin
      ningún llamador; aquí por fin se usa, para que ningún caption arma
      el texto a mano.
    - `classification` (Eje B -- qué significa clínicamente el valor): la
      tupla `(nivel, etiqueta, badge)` de un `classify_*()`, SIN
      modificar esa función. `grammar` (`GRAMMAR_SEVERITY` por default, o
      `GRAMMAR_NEUTRAL_STATE`) decide el color del MARCO alrededor del
      badge, no el badge en sí -- ver el mapa biomarcador->gramática
      arriba, junto a las constantes. Un `nivel="no_disponible"` (el que
      ya devuelven `classify_dar(None)`/`classify_tbr(None)`/
      `classify_chi(None)`) colorea el marco en `NEUTRAL` bajo cualquier
      gramática -- la ausencia se ve igual de neutra sin importar el eje.
      Sin `classification` (p.ej. BAR, que no tiene `classify_bar()` --
      ver CHANGELOG.md, decisión de no inventar zonas clínicas que
      Schutter 2006 no estableció), el marco por default ya es `NEUTRAL`
      -- la forma honesta de pintar "estado neutro" sin fabricar una
      clasificación de tres niveles que nadie validó.

    `citation`, si se da, se muestra COMPLETA, nunca truncada por espacio
    -- estándar tomado de `CHI_CITATION` (`spectral_model.py`), la cita
    que ya incluye su propia cláusula de alcance en el texto.

    `unavailable_reason`: cuando `value is None`, este es el único texto
    que se muestra -- preserva el motivo EXACTO que ya declara cada
    llamador honesto de la app hoy (p.ej. la duración exacta que le falta
    al PLV, o qué otra métrica falta para la que depende de ella) en vez
    de colapsar los 4 estilos distintos de "no disponible" que encontró
    el diagnóstico en uno solo genérico que perdería esa información. Si
    no se da, se señala en el propio texto (nunca se inventa un motivo) y
    se registra en el logger para que no pase desapercibido en
    desarrollo."""
    if value is None:
        reason = unavailable_reason
        if not reason:
            reason = "sin motivo declarado por quien llamó a resolve_metric_card"
            logger.warning("resolve_metric_card: '%s' sin valor y sin unavailable_reason", label)
        return MetricCardData(label=label, value=None, border_color=PALETTE.NEUTRAL, reason=reason)

    border = PALETTE.NEUTRAL
    parts: list = []

    if classification is not None:
        nivel, etiqueta, badge = classification
        if grammar == GRAMMAR_NEUTRAL_STATE:
            border = PALETTE.NEUTRAL if nivel == "no_disponible" else PALETTE.ACCENT_ON_DARK
        else:
            border = _SEVERITY_LEVEL_COLOR.get(nivel, PALETTE.NEUTRAL)
        if badge:
            parts.append(f"{badge} {etiqueta}")

    if provenance is not None:
        parts.append(badge_html(provenance))

    if citation:
        parts.append(citation)

    return MetricCardData(label=label, value=value, border_color=border, detail_parts=tuple(parts))


def render_metric_card(
    label: str,
    value: Optional[str] = None,
    *,
    provenance: Optional[str] = None,
    classification: Optional[Tuple[str, str, str]] = None,
    grammar: str = GRAMMAR_SEVERITY,
    citation: Optional[str] = None,
    unavailable_reason: Optional[str] = None,
    help: Optional[str] = None,
) -> None:
    """Tarjeta de métrica+badge, renderizada como elementos de Streamlit --
    Consolidación Visual Tanda 1 (2026-09-20). La superficie más repetida
    de toda la app (un valor con su honestidad de procedencia/
    clasificación) nunca había tenido un helper compartido; cada lab la
    resolvía a mano (`st.metric`, `st.caption` con f-strings, HTML
    propio). Delega TODA la lógica a `resolve_metric_card()` (ver ahí para
    el significado de cada parámetro) -- esta función solo formatea el
    `MetricCardData` resultante como HTML de Streamlit. `metric_card_to_
    html()`, más abajo, es el mismo dato formateado para `app/
    reporting.py` (Consolidación Visual Tanda 2, 2026-09-21) -- fuente
    única, dos renderizadores."""
    data = resolve_metric_card(
        label, value,
        provenance=provenance, classification=classification, grammar=grammar,
        citation=citation, unavailable_reason=unavailable_reason,
    )
    st.markdown(_metric_card_markup(data, help=help), unsafe_allow_html=True)


def _metric_card_markup(data: MetricCardData, extra_style: str = "", help: Optional[str] = None) -> str:
    """El HTML de la tarjeta, compartido por la app y el exporte. `data-label`/`data-value` permiten a las pruebas leer
    la tarjeta como leían `st.metric` (tanda 1 de la fase 1: la tarjeta absorbe `st.metric`)."""
    attrs = f"class='biocore-metric' data-label=\"{data.label}\" data-value=\"{data.value or ''}\""
    if help:
        attrs += f" title=\"{html.escape(help, quote=True)}\""
    if not data.available:
        return (
            f"<div {attrs} style='border:1px solid {PALETTE.NEUTRAL}; border-radius:8px; padding:10px 14px; "
            f"color:{PALETTE.TEXT}; background:rgba(255,255,255,0.03);{extra_style}'><strong>{data.label}</strong><br/>"
            f"{no_data_html(data.label, data.reason)}</div>"
        )
    body = " — ".join([f"<strong>{data.label}</strong>: {data.value}", *data.detail_parts])
    return (
        f"<div {attrs} style='border-left:4px solid {data.border_color}; border-radius:4px; padding:10px 14px; "
        f"color:{PALETTE.TEXT}; background:rgba(255,255,255,0.03);{extra_style}'>{body}</div>"
    )


def metric_card_to_html(data: MetricCardData) -> str:
    """`MetricCardData` -- el mismo dato que consume `render_metric_card()`
    -- formateado como HTML AUTÓNOMO (sin depender del runtime de
    Streamlit) para `app/reporting.py`. Consolidación Visual Tanda 2
    (2026-09-21): la superficie que viaja fuera de la app ahora reusa la
    MISMA resolución de honestidad que la app viva -- ver `resolve_metric_
    card()`, la única fuente. Mismo criterio visual que `render_metric_
    card()` (mismos colores de `PALETTE`, mismo orden de las partes) --
    el único cambio es el contenedor (`<div>` autónomo en vez de
    `st.markdown`)."""
    return _metric_card_markup(data, " margin-bottom:10px;")


def resolve_validation_marker(
    validation: Optional[str], validation_detail: Optional[str] = None
) -> Optional[Tuple[str, str, str]]:
    """La misma decisión que `render_module_header(validation=...)` toma
    internamente (Consolidación Visual Tanda 1), expuesta como función
    pura para que `app/reporting.py` (Tanda 2) pueda heredar la jerarquía
    de confianza en el encabezado del export, sin reimplementar
    `_VALIDATION_TIER_STYLE`. Devuelve `(color, símbolo, texto)` o `None`
    si `validation` no es un nivel reconocido -- mismo criterio permisivo
    que `render_module_header()`: un valor inválido se ignora, no rompe
    el render."""
    if validation is None or validation not in _VALIDATION_TIER_STYLE:
        return None
    color, symbol = _VALIDATION_TIER_STYLE[validation]
    return (color, symbol, validation_detail or validation)


CONTENT_KEY = "biocore_content"     # clave del contenedor de cada página (app/main.py::main)
CONTENT_MAX_PX = 1200                # ancho máximo del contenido, centrado (pulido profesional, Parte B)
MEASURE_CH = 75                      # largo de línea máximo de un párrafo, en caracteres


ICONS_URL = "app/static/marca/iconos"     # servida por Streamlit (server.enableStaticServing)
ROUTE_URL = "app/static/marca/ruta"

# Ícono de cada página del menú (2026-11-17). Los del kit v1.1 donde el kit trae uno; los «biocore-icono-app-*» se
# dibujaron con las reglas del manual (p. 21: línea de 1.75 en 24 x 24, puntas y uniones redondas, Trazo) y quedan
# pendientes de revisión de marca (LEEME-iconos-app.txt). Una prueba exige uno por página y que el archivo exista.
NAV_ICONS = {
    "inicio": "biocore-icono-app-inicio-monitor.svg",
    "temas": "biocore-icono-app-temas-monitor.svg",
    "teoria": "biocore-icono-academia-monitor.svg",
    "referencias": "biocore-icono-app-referencias-monitor.svg",
    "ecg-3d": "biocore-icono-app-ecg-3d-monitor.svg",
    "bibliografia": "biocore-icono-app-bibliografia-monitor.svg",
    "pregunta": "biocore-icono-app-pregunta-monitor.svg",
    "quiz": "biocore-icono-app-quiz-monitor.svg",
    "caso-ciego": "biocore-icono-app-caso-ciego-monitor.svg",
    "desafio-ecg": "biocore-icono-app-desafio-ecg-monitor.svg",
    "caso-guiado": "biocore-icono-app-caso-guiado-monitor.svg",
    "cuestionarios": "biocore-icono-app-cuestionarios-monitor.svg",
    "casos-simulador": "biocore-icono-app-casos-simulador-monitor.svg",
    "what-if": "biocore-icono-app-what-if-monitor.svg",
    "detective": "biocore-icono-app-detective-monitor.svg",
    "mi-sesion": "biocore-icono-app-mi-sesion-monitor.svg",
    "gemelo": "biocore-icono-gemelo-digital-monitor.svg",
    "ecg": "biocore-icono-ecg-monitor.svg",
    "multisensor": "biocore-icono-fusion-de-sensores-monitor.svg",
    "respiratorio": "biocore-icono-respiracion-monitor.svg",
    "eeg": "biocore-icono-eeg-monitor.svg",
    "emg": "biocore-icono-emg-monitor.svg",
    "hrv": "biocore-icono-variabilidad-cardiaca-monitor.svg",
    "biomarcadores": "biocore-icono-biomarcadores-monitor.svg",
    "calculadoras": "biocore-icono-calculadoras-monitor.svg",
    "pacientes": "biocore-icono-pacientes-monitor.svg",
    "comparar": "biocore-icono-app-comparar-monitor.svg",
    "modelo-3d": "biocore-icono-app-taller-3d-monitor.svg",
    "ajustes": "biocore-icono-app-ajustes-monitor.svg",
    "terminos": "biocore-icono-app-terminos-monitor.svg",
    "privacidad": "biocore-icono-app-privacidad-monitor.svg",
}


def _nav_icon_selectors(url: str) -> list:
    # Inicio es la página por defecto: Streamlit la enlaza a la raíz («/»), no a «/inicio».
    ends = ("/", "/inicio") if url == "inicio" else (f"/{url}",)
    return [f'[data-testid="stSidebarNav"] a[href$="{end}"]::before' for end in ends]


def nav_icon_css() -> str:
    """CSS de los íconos del menú. El espacio del ícono solo existe en los enlaces que tienen regla: antes una regla
    genérica (`a::before`) reservaba 20 px en todos y las páginas sin ícono quedaban con un hueco en blanco."""
    all_selectors = [sel for url in NAV_ICONS for sel in _nav_icon_selectors(url)]
    rules = [", ".join(all_selectors) + ' { content: ""; flex: 0 0 20px; width: 20px; height: 20px; '
             "margin-right: 10px; background: no-repeat center / contain; opacity: .8; "
             "transition: opacity .15s ease, transform .15s ease; }"]
    for url, file in NAV_ICONS.items():
        rules.append(", ".join(_nav_icon_selectors(url)) + f' {{ background-image: url("{ICONS_URL}/{file}"); }}')
    return "\n".join(rules)


def route_arrow_html(direction: str) -> str:
    """Flecha decorativa entre dos nodos de la ruta («derecha» o «izquierda»); el lector de pantalla la omite."""
    return (f'<div class="bc-arrow bc-arrow-{direction}" aria-hidden="true">'
            f'<img src="{ROUTE_URL}/biocore-ruta-flecha-{direction}.svg" alt=""></div>')


def inject_global_theme() -> None:
    """Estilo global de la app -- Consolidación Visual Tanda 1 (2026-09-20).
    Reemplaza `inject_biocore_css()` (antes en `app/main.py`), que inyectaba
    un degradado cian con valores hex propios (`#05101f`/`#040812`,
    glow `rgba(12,185,221,...)`) que GANABAN visualmente sobre el fondo
    plano de `.streamlit/config.toml` -- dos fuentes de "cuál es el fondo
    de la app" que nunca coincidían por diseño, desde antes de que este
    módulo existiera. Aquí el fondo/acento se construyen desde `PALETTE`,
    la misma fuente que ya usa el resto de este archivo.

    Las clases `.biocore-card`/`.biocore-panel`/`.status-pill`/
    `.pulse-dot` del bloque original se RETIRAN -- confirmado por grep en
    todo el repo que ningún elemento en ningún archivo las usa; eran CSS
    muerto desde que se escribieron."""
    st.markdown(
        f"""
        <style>
            :root {{ color-scheme: dark; }}
            html, body, [data-testid='stAppViewContainer'] {{
                background: radial-gradient(circle at top left, {PALETTE.PRIMARY}22, transparent 30%),
                            {PALETTE.BACKGROUND};
                color: {PALETTE.TEXT};
            }}
            /* Pulido profesional (Parte B): el contenido de cada página vive en `st.container(key=CONTENT_KEY)` y se
               limita a CONTENT_MAX_PX, centrado; los párrafos a MEASURE_CH caracteres. Selector por clave de
               contenedor (.st-key-*), el que recomienda la guía de Streamlit: no depende de la estructura interna del
               DOM. Las gráficas (tiras de ECG incluidas) usan todo el ancho del contenedor. */
            .st-key-{CONTENT_KEY} {{ max-width: {CONTENT_MAX_PX}px; margin-left: auto; margin-right: auto; }}
            .st-key-{CONTENT_KEY} p, .st-key-{CONTENT_KEY} li {{ max-width: {MEASURE_CH}ch; }}
            /* Tanda 2 de la fase 1: botón principal = texto ON_STATE sobre PRIMARY (5.56:1). Streamlit no expone el
               color del texto del botón en el tema y lo pinta blanco (3.21:1 sobre PRIMARY, no AA). */
            [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] *,
            [data-testid="stBaseButton-primaryFormSubmit"], [data-testid="stBaseButton-primaryFormSubmit"] * {{
                color: {PALETTE.ON_STATE} !important;
            }}
            /* Pasaporte de evidencia (2026-11-17): el botón de cada valor mide al menos 44 px de alto (WCAG 2.5.5, tamaño
               del objetivo), igual con el dedo que con el cursor. Selector por clave del popover (.st-key-*). */
            [class*="st-key-passport_"] button {{ min-height: 44px; }}
            /* Rediseño Duolingo + Apple (2026-11-17): tarjetas, franja de monitoreo, ruta, chips y carrusel. Solo tokens de
               PALETTE; el único color vivo es TRAZO. Selectores por clave de contenedor (.st-key-*). */
            [class*="st-key-bc_card"] {{ border-radius: 18px !important; background: {PALETTE.SECONDARY_BACKGROUND};
                border: 1px solid {PALETTE.GRID} !important; padding: 18px 20px !important; }}
            [class*="st-key-bc_monitor"] {{ border-radius: 18px !important; border: 1px solid {PALETTE.GRID} !important;
                border-top: 4px solid {PALETTE.TRAZO} !important; padding: 14px 20px !important; }}
            [class*="st-key-bc_node"] a, [class*="st-key-bc_node"] button {{ min-height: 56px; border-radius: 999px !important;
                border: 2px solid {PALETTE.TRAZO} !important; padding: 8px 22px !important; }}
            [class*="st-key-bc_node_b"] {{ margin-left: 22%; }}
            [class*="st-key-bc_node"] a, [class*="st-key-bc_node"] button {{ transition: background-color .15s ease, translate .15s ease; }}
            [class*="st-key-bc_node"] a:hover, [class*="st-key-bc_node"] button:hover {{ background: {PALETTE.RESALTE} !important;
                translate: 0 -2px; }}
            [class*="st-key-bc_node"] a:hover *, [class*="st-key-bc_node"] button:hover * {{ color: {PALETTE.TINTA_TITULO} !important; }}
            [class*="st-key-bc_node"] a:focus-visible, [class*="st-key-bc_node"] button:focus-visible,
            [class*="st-key-bc_card"] a:focus-visible, [class*="st-key-bc_card"] button:focus-visible {{
                outline: 2px solid {PALETTE.TRAZO} !important; outline-offset: 3px; }}
            /* Flechas de la ruta (`route_arrow_html`): la línea punteada avanza hacia el siguiente nodo; la animación vive
               en el SVG y se detiene con prefers-reduced-motion. Ocupan la franja entre el nodo izquierdo y el derecho. */
            .bc-arrow {{ width: 26%; margin: -12px 0 -12px 4%; line-height: 0; pointer-events: none; }}
            .bc-arrow img {{ display: block; width: 100%; height: auto; }}
            [class*="st-key-bc_cmp_col"] {{ border-right: 2px solid {PALETTE.TRAZO}; padding-right: 12px; }}
            [class*="st-key-bc_"] button {{ min-height: 44px; }}
            .bc-hero {{ font-size: 2.4rem; font-weight: 700; line-height: 1.1; letter-spacing: -0.02em; color: {PALETTE.TEXT};
                margin: 0 0 6px 0; }}
            .bc-eyebrow {{ color: {PALETTE.TRAZO}; font-weight: 600; font-size: 0.85rem; letter-spacing: 0.04em;
                text-transform: uppercase; }}
            .bc-chip {{ display: inline-flex; align-items: center; gap: 6px; border: 1px solid {PALETTE.GRID};
                border-radius: 999px; padding: 4px 12px; margin: 0 6px 6px 0; color: {PALETTE.TEXT}; font-size: 0.9rem; }}
            .bc-chip b {{ color: {PALETTE.TRAZO}; }}
            .bc-dots {{ display: flex; gap: 8px; justify-content: center; margin: 8px 0; }}
            .bc-dots span {{ width: 10px; height: 10px; border-radius: 999px; background: {PALETTE.GRID}; }}
            .bc-dots span.on {{ background: {PALETTE.TRAZO}; width: 26px; }}
            .bc-value {{ font-size: 1.6rem; font-weight: 700; color: {PALETTE.TEXT}; font-variant-numeric: tabular-nums; }}
            /* Kit de marca v1.1: Figtree en títulos y valores (cifras tabulares), Noto Sans en el texto (config.toml). */
            .bc-hero, .bc-value, .bc-mini b {{ font-family: Figtree, "Noto Sans", sans-serif; font-variant-numeric: tabular-nums; }}
            .bc-lema {{ display: inline-block; border: 1px solid {PALETTE.TRAZO}; border-radius: 999px; padding: 6px 18px;
                background: {PALETTE.PANEL}; color: {PALETTE.TINTA_TITULO}; font-family: Figtree, sans-serif;
                font-weight: 600; font-size: 1.15rem; margin: 6px 0 8px 0; }}
            .bc-logo img {{ height: 64px; width: auto; }}
            .bc-seal {{ display: inline-flex; align-items: center; gap: 6px; color: {PALETTE.TINTA_2}; font-size: 0.9rem; }}
            .bc-seal img {{ height: 20px; width: auto; }}
            .bc-illus {{ float: right; width: 72px; height: 72px; margin: 0 0 8px 12px; }}
            .bc-preview {{ border: 1px solid {PALETTE.GRID}; border-radius: 14px; overflow: hidden; background: #0b1426; }}
            .bc-preview img {{ display: block; width: 100%; height: auto; }}
            /* Menú lateral en píldoras con íconos dibujados (kit v1.1 y «biocore-icono-app-*», sin librería genérica).
               Cada página tiene su regla (`NAV_ICONS`, `nav_icon_css`): ningún enlace reserva un hueco sin ícono. */
            [data-testid="stSidebarNav"] a {{ border: 1px solid {PALETTE.GRID}; border-radius: 999px !important;
                margin: 3px 6px; padding-left: 12px; transition: background-color .15s ease, border-color .15s ease; }}
            [data-testid="stSidebarNav"] a[aria-current="page"] {{ border-color: {PALETTE.TRAZO}; background: {PALETTE.PANEL}; }}
            [data-testid="stSidebarNav"] a:hover {{ border-color: {PALETTE.TRAZO}; background: {PALETTE.RESALTE}; }}
            [data-testid="stSidebarNav"] a:hover *, [data-testid="stSidebarNav"] a[aria-current="page"] * {{
                color: {PALETTE.TINTA_TITULO}; }}
            [data-testid="stSidebarNav"] a:focus-visible {{ outline: 2px solid {PALETTE.TRAZO}; outline-offset: 2px; }}
            {nav_icon_css()}
            [data-testid="stSidebarNav"] a:hover::before, [data-testid="stSidebarNav"] a[aria-current="page"]::before {{
                opacity: 1; transform: scale(1.1); }}
            /* Al bajar, el logo y el monitoreo suben y se quedan arriba en pequeño (animación ligada al scroll, solo CSS). */
            [data-testid="stMain"] {{ scroll-timeline: --bcmain block; }}
            .st-key-bc_sticky {{ position: fixed; top: 0.7rem; left: 50%; transform: translateX(-50%); z-index: 1000;
                display: flex; align-items: center; gap: 14px; background: {PALETTE.PANEL}; border: 1px solid {PALETTE.GRID};
                border-radius: 999px; padding: 4px 16px; width: auto !important; max-width: 92vw; }}
            .bc-mini {{ display: flex; align-items: center; gap: 14px; color: {PALETTE.TEXT}; font-size: 0.9rem; white-space: nowrap; }}
            .bc-mini img {{ height: 22px; width: auto; }}
            @supports (animation-timeline: scroll()) {{
                .st-key-bc_sticky {{ animation: bc-reveal linear both; animation-timeline: --bcmain; animation-range: 160px 320px; }}
            }}
            /* Animaciones de scroll (2026-11-17): tarjetas, monitoreo, nodos y flechas aparecen al entrar en la vista.
               Solo donde el navegador soporta view(); sin soporte, todo se ve desde el inicio. */
            @supports (animation-timeline: view()) {{
                [class*="st-key-bc_card"], [class*="st-key-bc_monitor"], [class*="st-key-bc_node"], .bc-arrow {{
                    animation: bc-rise linear both; animation-timeline: view(); animation-range: entry 0% entry 55%; }}
            }}
            .bc-hero, .bc-lema, .bc-logo {{ animation: bc-rise .6s ease-out both; }}
            .bc-preview img {{ animation: bc-draw 1.6s ease-out both; }}
            [class*="st-key-bc_card"] {{ transition: border-color .2s ease, translate .2s ease, box-shadow .2s ease; }}
            [class*="st-key-bc_card"]:hover {{ border-color: {PALETTE.TRAZO} !important; translate: 0 -3px;
                box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35); }}
            @keyframes bc-rise {{ from {{ opacity: 0; transform: translateY(18px) scale(0.98); }} to {{ opacity: 1; transform: none; }} }}
            @keyframes bc-draw {{ from {{ clip-path: inset(0 100% 0 0); }} to {{ clip-path: inset(0 0 0 0); }} }}
            @keyframes bc-reveal {{ from {{ opacity: 0; visibility: hidden; }} to {{ opacity: 1; visibility: visible; }} }}
            @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
            /* Al pasar el cursor Streamlit oscurece el fondo (#0b5fef: 3.31:1 con texto oscuro). Se usa ACCENT_ON_DARK. */
            [data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primary"]:active,
            [data-testid="stBaseButton-primary"]:focus-visible,
            [data-testid="stBaseButton-primaryFormSubmit"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:active {{
                background-color: {PALETTE.ACCENT_ON_DARK} !important;
                border-color: {PALETTE.ACCENT_ON_DARK} !important;
            }}
            /* Pulido estético (2026-11-18): solo tokens de PALETTE; nada cambia de lugar ni de texto. */
            [data-testid="stHeader"] {{ background: rgba(15, 23, 42, 0.72) !important; backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px); }}
            [data-testid="stSidebar"] {{ background: {PALETTE.PANEL}; border-right: 1px solid {PALETTE.GRID}; }}
            [data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {PALETTE.RESALTE}; }}
            [data-testid="stNavSectionHeader"], [data-testid="stNavSectionHeader"] * {{ color: {PALETTE.TINTA_2} !important;
                text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.74rem !important; font-weight: 600; }}
            h1, h2, h3, h4 {{ letter-spacing: -0.015em; }}
            .st-key-{CONTENT_KEY} p, .st-key-{CONTENT_KEY} li {{ line-height: 1.6; }}
            [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"],
            [data-testid="stBaseButton-primaryFormSubmit"], [data-testid="stBaseButton-secondaryFormSubmit"] {{
                border-radius: 999px !important; padding-left: 18px; padding-right: 18px;
                transition: background-color .15s ease, border-color .15s ease, translate .15s ease; }}
            [data-testid="stBaseButton-secondary"] {{ border-color: {PALETTE.GRID} !important; }}
            /* Botón principal deshabilitado (p. ej. «Ingresar al laboratorio» sin la casilla): la regla ON_STATE de arriba
               dejaba su texto oscuro sobre fondo oscuro, invisible. Texto NEUTRAL sobre el fondo (medido en CONTRAST_PAIRS). */
            [data-testid="stBaseButton-primary"]:disabled, [data-testid="stBaseButton-primary"]:disabled * {{
                color: {PALETTE.NEUTRAL} !important; }}
            [data-testid="stBaseButton-primary"]:disabled {{ background: transparent !important;
                border: 1px solid {PALETTE.GRID} !important; }}
            [data-testid="stBaseButton-secondary"]:hover {{ border-color: {PALETTE.TRAZO} !important;
                background: {PALETTE.RESALTE} !important; translate: 0 -1px; }}
            [data-testid="stBaseButton-secondary"]:hover * {{ color: {PALETTE.TINTA_TITULO} !important; }}
            button:focus-visible, a:focus-visible, [role="tab"]:focus-visible, summary:focus-visible {{
                outline: 2px solid {PALETTE.TRAZO} !important; outline-offset: 2px; }}
            [data-testid="stExpander"] details {{ border-radius: 14px !important; border: 1px solid {PALETTE.GRID} !important;
                overflow: hidden; }}
            [data-testid="stExpander"] summary {{ transition: background-color .15s ease; }}
            [data-testid="stExpander"] summary:hover {{ background: {PALETTE.RESALTE}; }}
            [data-testid="stExpander"] details[open] > summary {{ border-bottom: 1px solid {PALETTE.GRID}; }}
            [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {PALETTE.GRID}; }}
            [data-baseweb="tab"] {{ border-radius: 10px 10px 0 0; padding: 8px 14px !important; }}
            [data-baseweb="tab"]:hover {{ background: {PALETTE.RESALTE}; }}
            [data-testid="stAlert"], [data-testid="stAlertContainer"] {{ border-radius: 14px !important; }}
            [data-testid="stDataFrame"], [data-testid="stTable"] {{ border: 1px solid {PALETTE.GRID}; border-radius: 12px;
                overflow: hidden; }}
            /* Campos por su data-testid (la palabra suelta en inglés la vigila el recorrido de «sin inglés visible»). */
            [data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"], [data-baseweb="select"] > div,
            [data-baseweb="textarea"] {{ border-radius: 12px !important; }}
            [data-testid="stPopover"] button {{ border-radius: 999px !important; }}
            hr {{ border-color: {PALETTE.GRID} !important; opacity: 0.8; }}
            ::selection {{ background: {PALETTE.RESALTE}; color: {PALETTE.TINTA_TITULO}; }}
            * {{ scrollbar-width: thin; scrollbar-color: {PALETTE.GRID} transparent; }}
            ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
            ::-webkit-scrollbar-thumb {{ background: {PALETTE.GRID}; border-radius: 999px; border: 2px solid transparent;
                background-clip: content-box; }}
            ::-webkit-scrollbar-thumb:hover {{ background-color: {PALETTE.NEUTRAL}; }}
            .st-key-{CONTENT_KEY} {{ animation: bc-fade .35s ease-out both; }}
            /* Solo opacidad: un transform en este contenedor haría que la barra fija del Inicio dejara de ser fija. */
            @keyframes bc-fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        </style>
        """,
        unsafe_allow_html=True,
    )
