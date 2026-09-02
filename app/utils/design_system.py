"""Sistema de diseño compartido de BIOCORE AI (2026-08-24, Capa 2, Fase
2.3, Tanda 1).

El recon de esta fase encontró 52 colores hexadecimales distintos sin
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

import logging
from typing import Optional

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

    PRIMARY = "#1d4ed8"           # controles nativos de Streamlit (botones/sliders) -- NO como texto sobre BACKGROUND
    ACCENT_ON_DARK = "#8ecae6"    # texto/íconos de marca sobre fondo oscuro -- 9.98:1 sobre BACKGROUND (AAA)
    BACKGROUND = "#0f172a"
    SECONDARY_BACKGROUND = "#1a2a4a"
    TEXT = "#e0e7ff"              # 14.49:1 sobre BACKGROUND, 11.56:1 sobre SECONDARY_BACKGROUND (AAA ambos)

    # Semántica de estado -- promovida de ups_body_visual.py (fuente
    # original). Contraste sobre BACKGROUND: STABLE 9.75:1 (AAA), WARNING
    # 11.32:1 (AAA), CRITICAL 5.46:1 (AA -- suficiente para badges/texto
    # grande, no para letra pequeña), NEUTRAL 3.75:1 (bajo el mínimo AA de
    # texto normal -- reservado para elementos grandes/decorativos, nunca
    # para texto de lectura).
    STABLE = "#39d98a"
    WARNING = "#ffc542"
    CRITICAL = "#ff4d4d"
    NEUTRAL = "#64748b"


# ═══════════════════════════════════════════════════════════════════════
# BADGES DE PROCEDENCIA -- fuente única (2026-08-24). Reemplaza las dos
# definiciones gemelas (`BIOMARKER_*_BADGE` en app/main.py,
# `PROVENANCE_*_BADGE` en twin_shell/pages.py) -- mismos valores, cero
# import compartido hasta ahora. Esta tanda SOLO crea la fuente; migrar
# esos dos sitios para que importen de aquí es una tanda posterior (tocar
# los dos archivos a la vez está fuera del alcance "2 pilotos" de esta
# tanda).
# ═══════════════════════════════════════════════════════════════════════

class BADGES:
    """Badges de procedencia de la Capa 3 (honestidad de dato). Cada
    constante es el emoji solo -- `BADGES.label(key)` da el emoji + texto
    para usar directo en un `st.caption`/`help=`."""

    CLINICAL = "🟢"    # dato/fórmula validada clínicamente (citable)
    HEURISTIC = "🔵"   # cálculo real, constante/ponderación heurística (no de estudio de cohorte)
    GHOST = "🔴"       # entrada sin fuente real disponible -- no debería verse en producción (Capa 3 los retiró)
    METHOD = "🟣"      # metodología propia declarada como tal (no un score clínico estándar)

    _LABELS = {
        CLINICAL: "validado clínicamente",
        HEURISTIC: "heurística de ingeniería, no de estudio de cohorte",
        GHOST: "sin fuente real disponible",
        METHOD: "metodología propia de BIOCORE",
    }

    @classmethod
    def label(cls, badge: str) -> str:
        """Emoji + texto corto, listo para mostrar."""
        return f"{badge} {cls._LABELS.get(badge, '')}".strip()


# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES DE UI
# ═══════════════════════════════════════════════════════════════════════

def render_module_header(title: str, icon: str = "", subtitle: Optional[str] = None) -> None:
    """Título de módulo -- un solo estilo para todos, reemplaza los 4
    mecanismos encontrados en el recon (`<h1>`/`<h2>` a mano, `st.header()`,
    `st.title()`, o ninguno -- el caso de Digital Twin OS antes de esta
    tanda). `icon` es un emoji, igual que ya usa cada módulo en su título."""
    header_text = f"{icon} {title}".strip()
    st.markdown(
        f"<h1 style='color:{PALETTE.ACCENT_ON_DARK}; margin-bottom:0;'>{header_text}</h1>",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f"<p style='color:{PALETTE.TEXT}; opacity:0.75; margin-top:0;'>{subtitle}</p>",
            unsafe_allow_html=True,
        )


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
        f"color:{PALETTE.TEXT}; opacity:0.85;'>{icon_html}&nbsp;&nbsp;{text}</div>",
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
