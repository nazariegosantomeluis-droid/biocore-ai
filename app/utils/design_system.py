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

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

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
        f"<h1 style='color:{PALETTE.ACCENT_ON_DARK}; margin-bottom:0;'>{header_text}</h1>",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f"<p style='color:{PALETTE.TEXT}; opacity:0.75; margin-top:0;'>{subtitle}</p>",
            unsafe_allow_html=True,
        )
    marker = resolve_validation_marker(validation, validation_detail)
    if marker is not None:
        color, symbol, text = marker
        st.markdown(
            f"<div style='border-left:3px solid {color}; padding:4px 10px; margin:2px 0 12px 0; "
            f"color:{PALETTE.TEXT}; opacity:0.92; font-size:0.92rem;'>{symbol}&nbsp;&nbsp;{text}</div>",
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
        parts.append(BADGES.label(provenance))

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
    if not data.available:
        st.markdown(
            f"<div style='border:1px solid {PALETTE.NEUTRAL}; border-radius:8px; padding:12px 16px; "
            f"color:{PALETTE.TEXT};'><strong>{data.label}</strong><br/>"
            f"<span style='opacity:0.85;'>○ no disponible — {data.reason}</span></div>",
            unsafe_allow_html=True,
        )
        return

    body = " — ".join([f"<strong>{data.label}</strong>: {data.value}", *data.detail_parts])
    st.markdown(
        f"<div style='border-left:4px solid {data.border_color}; border-radius:4px; padding:10px 14px; "
        f"color:{PALETTE.TEXT}; background:rgba(255,255,255,0.03);'>{body}</div>",
        unsafe_allow_html=True,
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
    if not data.available:
        return (
            f"<div class='biocore-metric' style='border:1px solid {PALETTE.NEUTRAL}; border-radius:8px; "
            f"padding:10px 14px; margin-bottom:10px; color:{PALETTE.TEXT}; background:rgba(255,255,255,0.03);'>"
            f"<strong>{data.label}</strong><br/>"
            f"<span style='opacity:0.85;'>○ no disponible — {data.reason}</span></div>"
        )
    body = " — ".join([f"<strong>{data.label}</strong>: {data.value}", *data.detail_parts])
    return (
        f"<div class='biocore-metric' style='border-left:4px solid {data.border_color}; border-radius:4px; "
        f"padding:10px 14px; margin-bottom:10px; color:{PALETTE.TEXT}; background:rgba(255,255,255,0.03);'>{body}</div>"
    )


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
            :root {{ color-scheme: dark; font-family: 'Inter', 'Segoe UI', sans-serif; }}
            html, body, [data-testid='stAppViewContainer'] {{
                background: radial-gradient(circle at top left, {PALETTE.PRIMARY}22, transparent 30%),
                            {PALETTE.BACKGROUND};
                color: {PALETTE.TEXT};
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
