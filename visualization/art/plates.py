"""Láminas educativas del Atlas visual de BIOCORE AI (2026-10-19; datos reales 2026-10-21).

Desde el 2026-10-21 las láminas anatómicas y de señal usan datos reales
(`plates_real.py`): latido, tacograma y bandas del EEG de registros de
PhysioNet; precordiales, 10-20, conducción y cuerpo sobre renders de una
tomografía real y plantillas 3D. Aquí quedan los esquemas que son
diagramas por naturaleza (hexaxial, unidad motora) y la galería de
patrones respiratorios del simulador, y el registro de todas las láminas.

Cada lámina = un dibujo SVG + una explicación en HTML + su fuente. El texto
largo vive en HTML (no dentro del SVG) para que se lea igual en un teléfono
que en un monitor: el SVG se escala, el HTML se reacomoda.

Honestidad (CLAUDE.md, reglas 3 y 4): cada lámina dice qué es en su rótulo
(`Plate.chip`): registro real, anatomía real, plantilla, esquema o
simulación; ninguna es un dato del paciente. Los valores que rotulan son o
bien MEDIDOS por el código sobre el registro real (`beat_delineation`,
intervalos RR anotados, potencia de bandas del `EegAnalyzer`), o bien
constantes que la app ya usa para calcular (`BAND_LIMITS_HZ`, el generador
del Respiratory Lab, las fórmulas de HRV de `render_hrv_page`), o rangos de
referencia con su cita. Nada se escribe "a ojo".

Algunas láminas aceptan un resaltado (`highlight=`, `active=`, `selected=`,
`dominant=`) para responder a lo que la persona elige en el laboratorio:
la onda P/QRS/T del ECG Lab, la estructura de conducción, los canales EEG
en uso, la banda dominante calculada, el patrón respiratorio elegido.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

from visualization.art import plates_real
from visualization.art import tokens as T
from visualization.art.svg import (esc, fmt, join, map_signal, mm_grid, path_from_xy, smooth_path,
                                   svg_root, text, trace)

# ═══════════════════════════════════════════════════════════════════════
# Fuentes citadas por las láminas (las clínicas se importan de donde la app
# ya las usa para calcular -- una sola fuente por cita).
# ═══════════════════════════════════════════════════════════════════════

try:  # citas que ya viven en la capa clínica
    from clinical.calculators import ECG_PAPER_CITATION, QRS_AXIS_CITATION, QTC_THRESHOLDS_CITATION
except Exception:  # pragma: no cover - la app siempre tiene clinical/
    ECG_PAPER_CITATION = "Kligfield P, et al. Circulation 2007;115:1306–1324"
    QRS_AXIS_CITATION = "Surawicz B, Knilans TK. Chou's Electrocardiography in Clinical Practice, 6th ed. 2008"
    QTC_THRESHOLDS_CITATION = "Rautaharju PM, Surawicz B, Gettes LS. Circulation 2009;119:e241–e250"

CHOU_CITATION = (
    "Surawicz B, Knilans TK. Chou's Electrocardiography in Clinical Practice, 6th ed. "
    "Saunders Elsevier; 2008 (PR del adulto 0.12–0.20 s)"
)
QRS_WIDTH_CITATION = (
    "Surawicz B, Childers R, Deal BJ, Gettes LS. AHA/ACCF/HRS Recommendations for the "
    "Standardization and Interpretation of the Electrocardiogram, Part III. Circulation "
    "2009;119:e235–e240 (QRS ≥ 120 ms: bloqueo completo de rama en el adulto)"
)
GUYTON_CITATION = "Hall JE, Hall ME. Guyton y Hall. Tratado de fisiología médica, 14.ª ed. Elsevier; 2021"
JASPER_CITATION = (
    "Jasper HH. The ten-twenty electrode system of the International Federation. "
    "Electroencephalogr Clin Neurophysiol 1958;10:371–375"
)
ACNS_NOMENCLATURE_CITATION = (
    "Acharya JN, Hani A, Cheek J, Thirumala P, Tsuchida TN. American Clinical Neurophysiology "
    "Society Guideline 2: Guidelines for Standard Electrode Position Nomenclature. "
    "J Clin Neurophysiol 2016;33:308–311 (T7/T8/P7/P8 en lugar de T3/T4/T5/T6)"
)
KANE_GLOSSARY_CITATION = (
    "Kane N, Acharya J, Benickzy S, et al. A revised glossary of terms most commonly used by "
    "clinical electroencephalographers. Clin Neurophysiol Pract 2017;2:170–185"
)
AASM_CITATION = (
    "Berry RB, et al. The AASM Manual for the Scoring of Sleep and Associated Events. "
    "American Academy of Sleep Medicine (definiciones de apnea central, obstructiva y "
    "respiración de Cheyne-Stokes)"
)
TASK_FORCE_HRV_CITATION = (
    "Task Force of the European Society of Cardiology and the North American Society of Pacing "
    "and Electrophysiology. Heart rate variability: standards of measurement, physiological "
    "interpretation and clinical use. Circulation 1996;93:1043–1065"
)
DE_LUCA_CITATION = (
    "De Luca CJ. The use of surface electromyography in biomechanics. "
    "J Appl Biomech 1997;13:135–163"
)
HENNEMAN_CITATION = (
    "Henneman E. Relation between size of neurons and their susceptibility to discharge. "
    "Science 1957;126:1345–1347"
)


# ═══════════════════════════════════════════════════════════════════════
# Estructura común
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Plate:
    key: str
    title: str
    topic: str                      # agrupa el Atlas: Corazón, Cerebro, ...
    summary: str                    # una línea, para el índice del Atlas
    sources: Tuple[str, ...]
    build: Callable[..., Tuple[str, str]]  # (**kw) -> (arte_html, details_html)
    # Qué es la imagen (se muestra como etiqueta): un dibujo, un registro
    # real, anatomía real o una simulación. Nunca se omite.
    chip: str = "Esquema ilustrativo"


def _ul(items: Iterable[str], cls: str = "") -> str:
    cls_attr = f' class="{cls}"' if cls else ""
    return f"<ul{cls_attr}>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def _ol(items: Iterable[str], highlight_index: Optional[int] = None) -> str:
    rows = []
    for i, item in enumerate(items):
        cls = ' class="bc-on"' if highlight_index == i else ""
        rows.append(f"<li{cls}>{item}</li>")
    return '<ol class="bc-steps">' + "".join(rows) + "</ol>"


def _ms(seconds: float) -> str:
    return f"{seconds * 1000:.0f} ms"


def _marker(x: float, y: float, n: int, *, on: bool = False, r: float = 13) -> str:
    """Círculo numerado (para láminas cuyos pasos SÍ son una secuencia)."""
    fill = T.TRACE if on else T.PANEL
    stroke = T.TRACE if on else T.INK_3
    ink = T.BACKGROUND if on else T.INK
    return (
        f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{r:g}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        + text(x, y + 5, n, size=14, fill=ink, anchor="middle", weight=700)
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. Sistema hexaxial y eje eléctrico
# ═══════════════════════════════════════════════════════════════════════

HEXAXIAL_LEADS = (("I", 0), ("II", 60), ("III", 120), ("aVF", 90), ("aVL", -30), ("aVR", -150))


def _polar(cx: float, cy: float, r: float, deg: float) -> Tuple[float, float]:
    rad = np.deg2rad(deg)
    return cx + r * np.cos(rad), cy + r * np.sin(rad)


def _sector(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    x0, y0 = _polar(cx, cy, r, a0)
    x1, y1 = _polar(cx, cy, r, a1)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{fmt(cx)} {fmt(cy)}L{fmt(x0)} {fmt(y0)}A{fmt(r)} {fmt(r)} 0 {large} 1 {fmt(x1)} {fmt(y1)}Z"


def _hexaxial(axis_deg: Optional[float] = None) -> Tuple[str, str]:
    W, H = 600.0, 510.0
    cx, cy, r = 336.0, 250.0, 176.0
    body: List[str] = [
        f'<path d="{_sector(cx, cy, r, -30, 90)}" fill="{T.TRACE}" fill-opacity="0.16"/>',
        f'<path d="{_sector(cx, cy, r, -90, -30)}" fill="{T.INK_3}" fill-opacity="0.08"/>',
        f'<path d="{_sector(cx, cy, r, 90, 180)}" fill="{T.INK_3}" fill-opacity="0.08"/>',
        f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="none" stroke="{T.INK_3}" stroke-width="1.6"/>',
    ]
    for name, deg in HEXAXIAL_LEADS:
        xa, ya = _polar(cx, cy, r, deg)
        xb, yb = _polar(cx, cy, r, deg + 180)
        body.append(f'<path d="M{fmt(xb)} {fmt(yb)}L{fmt(xa)} {fmt(ya)}" stroke="{T.INK_2}" stroke-width="1.6"/>')
        body.append(f'<circle cx="{fmt(xa)}" cy="{fmt(ya)}" r="4" fill="{T.INK}"/>')
        lx, ly = _polar(cx, cy, r + 32, deg)
        sign = "+" if deg > 0 else ("−" if deg < 0 else "")
        body.append(text(lx, ly - 2, name, size=17, fill=T.INK, anchor="middle", weight=700, family=T.FONT_HEAD))
        body.append(text(lx, ly + 15, f"{sign}{abs(deg)}°", size=13, fill=T.INK_3, anchor="middle"))
    halo = T.PANEL
    # El rótulo del sector normal se aparta del eje marcado (si lo hay) para
    # que la flecha no lo tape.
    label_deg = 40.0
    if axis_deg is not None and np.isfinite(axis_deg) and abs(float(axis_deg) - label_deg) < 32:
        label_deg = 76.0 if float(axis_deg) < label_deg else 4.0
    lx, ly = _polar(cx, cy, r * 0.6, label_deg)
    body.append(text(lx, ly, "Eje normal", size=16, fill=T.INK, anchor="middle", weight=700,
                     family=T.FONT_HEAD, halo=halo))
    body.append(text(lx, ly + 20, "−30° a +90°", size=14, fill=T.INK_2, anchor="middle", halo=halo))
    body.append(text(cx + 70, cy - 118, "Desviación izquierda", size=14, fill=T.INK_2, anchor="middle", halo=halo))
    body.append(text(cx - 100, cy + 112, "Desviación derecha", size=14, fill=T.INK_2, anchor="middle", halo=halo))
    if axis_deg is not None and np.isfinite(axis_deg):
        xa, ya = _polar(cx, cy, r - 14, float(axis_deg))
        body.append(
            f'<path d="M{fmt(cx)} {fmt(cy)}L{fmt(xa)} {fmt(ya)}" stroke="{T.TRACE}" stroke-width="5" '
            f'stroke-linecap="round"/>'
        )
        body.append(f'<circle cx="{fmt(xa)}" cy="{fmt(ya)}" r="7" fill="{T.TRACE}"/>')
    # Triángulo de Einthoven (recuadro, abajo a la izquierda): de dónde
    # salen I, II y III.
    ra, la, ll = (34.0, 376.0), (134.0, 376.0), (84.0, 462.0)
    body.append(
        f'<path d="M{fmt(ra[0])} {fmt(ra[1])}L{fmt(la[0])} {fmt(la[1])}L{fmt(ll[0])} {fmt(ll[1])}Z" '
        f'fill="none" stroke="{T.INK_3}" stroke-width="1.8"/>'
    )
    for lab, (x, y), dy in (("BD", ra, -11), ("BI", la, -11), ("PI", ll, 22)):
        body.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="5" fill="{T.TRACE}"/>')
        body.append(text(x, y + dy, lab, size=13, fill=T.INK_2, anchor="middle", weight=600))
    for lab, x, y in (("I", 84, 368), ("II", 48, 426), ("III", 122, 426)):
        body.append(text(x, y, lab, size=15, fill=T.INK, anchor="middle", weight=700, family=T.FONT_HEAD))
    body.append(text(84, 502, "Triángulo de Einthoven", size=13, fill=T.INK_3, anchor="middle"))

    label = "Esquema ilustrativo: sistema hexaxial de las derivaciones de miembros y eje eléctrico normal"
    if axis_deg is not None:
        label += f"; eje marcado en {axis_deg:.0f}°"
    svg = svg_root(W, H, join(body), label=label,
                   desc="0° apunta a la izquierda del paciente y +90° hacia los pies.")
    details = (
        "<p>Las seis derivaciones de miembros forman una rueda: 0° es la izquierda del paciente y +90°, "
        "los pies. BD, BI y PI son los electrodos del brazo derecho, brazo izquierdo y pierna izquierda.</p>"
        + _ul([
            "<strong>Eje normal</strong> del adulto: −30° a +90°.",
            "<strong>Desviación izquierda</strong>: más negativo que −30°.",
            "<strong>Desviación derecha</strong>: más allá de +90°.",
            "Atajo: si el QRS es positivo en I y en aVF, el eje cae entre 0° y +90°.",
        ])
    )
    return svg, details


# ═══════════════════════════════════════════════════════════════════════
# 2. Patrones respiratorios (con el generador del Respiratory Lab)
# ═══════════════════════════════════════════════════════════════════════

RESPIRATORY_PATTERNS = (
    # pattern_type del generador, nombre, descripción
    ("normal", "Normal", "Ciclos regulares; en el adulto, 12–20 respiraciones por minuto."),
    ("tachypnea", "Taquipnea", "Más rápida (> 20/min) y más superficial."),
    ("bradypnea", "Bradipnea", "Más lenta (< 12/min) y más profunda."),
    ("apnea_central", "Apnea central", "Sin flujo y sin esfuerzo: el centro respiratorio no da la orden."),
    ("apnea_obstructive", "Apnea obstructiva", "Sin flujo pero con esfuerzo: la vía aérea está cerrada."),
    ("cheyne_stokes", "Cheyne-Stokes", "Crescendo-decrescendo periódico (insuficiencia cardiaca, lesión del SNC)."),
    ("ataxic", "Atáxica (Biot)", "Irregular en ritmo y profundidad (lesión del tronco encefálico)."),
)
_RESP_DURATION_S = 60.0
_RESP_CACHE: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}


def respiratory_traces(pattern_type: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(t, flujo, esfuerzo torácico) de 60 s, del MISMO `RespiratorySignalGenerator`
    del Respiratory Lab. El generador usa el RNG global de NumPy; aquí se
    siembra y se RESTAURA el estado, para que el dibujo sea siempre el mismo
    sin alterar la aleatoriedad del resto de la app."""
    if pattern_type in _RESP_CACHE:
        return _RESP_CACHE[pattern_type]
    from src.signals.respiration import RespiratoryPattern, RespiratorySignalGenerator

    state = np.random.get_state()
    try:
        np.random.seed(20261019)
        sig = RespiratorySignalGenerator(sampling_rate=12).generate_respiration(
            duration=_RESP_DURATION_S, params=RespiratoryPattern(pattern_type=pattern_type),
        )
    finally:
        np.random.set_state(state)
    out = (np.asarray(sig["time"]), np.asarray(sig["airflow"]), np.asarray(sig["chest_wall"]))
    _RESP_CACHE[pattern_type] = out
    return out


def _resp_tile_svg(pattern_type: str, name: str, scales: Tuple[float, float]) -> str:
    W, H = 300.0, 112.0
    t, flow, chest = respiratory_traces(pattern_type)
    flow_px, chest_px = scales
    body = [
        f'<rect width="{W:.0f}" height="{H:.0f}" rx="8" fill="{T.STRIP_BG}"/>',
        mm_grid(0, 0, W, H, 6, key="resp-tile"),
        f'<path d="M0 40H{W:.0f}M0 86H{W:.0f}" stroke="{T.INK_3}" stroke-opacity="0.25"/>',
    ]
    xs, ys = map_signal(t, flow, x0=6, width=W - 12, y_mid=40, px_per_unit=flow_px)
    body.append(trace(path_from_xy(xs, ys), color=T.SERIES[0], width=1.8))
    xs, ys = map_signal(t, chest, x0=6, width=W - 12, y_mid=86, px_per_unit=chest_px)
    body.append(trace(path_from_xy(xs, ys), color=T.SERIES[1], width=1.8))
    return svg_root(W, H, join(body), label=f"Esquema ilustrativo: patrón {name}, flujo y esfuerzo en 60 s")


def respiratory_gallery_html(selected: Optional[str] = None) -> str:
    """Galería de los 7 patrones (HTML con un SVG por patrón; se acomoda en
    columnas según el ancho). `selected` = `pattern_type` resaltado."""
    traces_all = [respiratory_traces(p) for p, _, _ in RESPIRATORY_PATTERNS]
    flow_max = max(float(np.max(np.abs(f))) for _, f, _ in traces_all) or 1.0
    chest_max = max(float(np.max(np.abs(c))) for _, _, c in traces_all) or 1.0
    scales = (34.0 / flow_max, 22.0 / chest_max)
    tiles = []
    for pattern_type, name, desc in RESPIRATORY_PATTERNS:
        on = pattern_type == selected
        badge = '<span class="bc-chip">Elegido en el laboratorio</span>' if on else ""
        tiles.append(
            f'<div class="bc-tile{" bc-on" if on else ""}">'
            f'<div class="bc-tile-head"><strong>{esc(name)}</strong>{badge}</div>'
            f'{_resp_tile_svg(pattern_type, name, scales)}'
            f'<p>{esc(desc)}</p></div>'
        )
    legend = (
        '<div class="bc-legend">'
        f'<span><i style="background:{T.SERIES[0]}"></i>Flujo aéreo</span>'
        f'<span><i style="background:{T.SERIES[1]}"></i>Esfuerzo torácico</span>'
        '<span>60 s por patrón, misma escala en todos</span></div>'
    )
    return legend + '<div class="bc-tiles">' + "".join(tiles) + "</div>"


def _respiratory(selected: Optional[str] = None) -> Tuple[str, str]:
    details = (
        "<p>La clave de las apneas está en el segundo trazo: en la <strong>obstructiva</strong> el tórax "
        "sigue intentando respirar; en la <strong>central</strong> también se detiene. Una apnea dura "
        "10 s o más.</p>"
    )
    return respiratory_gallery_html(selected), details


# ═══════════════════════════════════════════════════════════════════════
# 3. Unidad motora y EMG de superficie
# ═══════════════════════════════════════════════════════════════════════

def _motor_unit() -> Tuple[str, str]:
    W, H = 640.0, 430.0
    body: List[str] = []
    # Médula espinal en corte transversal (sustancia gris en mariposa).
    body.append(f'<circle cx="96" cy="112" r="62" fill="{T.PANEL}" stroke="{T.INK_3}" stroke-width="2.2"/>')
    # Sustancia gris en mariposa: astas posteriores (arriba, finas) y
    # anteriores (abajo, anchas), donde viven las motoneuronas.
    gray = smooth_path([
        (96, 98), (84, 82), (74, 84), (80, 100), (72, 112), (66, 128), (74, 142), (88, 140),
        (96, 128), (104, 140), (118, 142), (126, 128), (120, 112), (112, 100), (118, 84),
        (108, 82),
    ])
    body.append(f'<path d="{gray}" fill="{T.LINE}" fill-opacity="0.35" stroke="{T.INK_3}" stroke-width="1.4"/>')
    body.append(text(96, 194, "Médula espinal", size=14, fill=T.INK_3, anchor="middle"))
    # Motoneurona alfa en el asta anterior + axón por la raíz ventral.
    body.append(f'<circle cx="114" cy="132" r="8" fill="{T.TRACE}" stroke="{T.PANEL}" stroke-width="2"/>')
    axon = "M120 138C176 172 214 214 246 252C258 266 270 274 290 276"
    body.append(trace(axon, width=3))
    body.append(text(170, 150, "Motoneurona α", size=14, fill=T.INK, weight=600, halo=T.PANEL))
    body.append(text(196, 256, "Axón", size=14, fill=T.INK_2, halo=T.PANEL))

    # Piel y electrodos de superficie.
    body.append(f'<path d="M260 196H620" stroke="{T.INK_3}" stroke-width="2"/>')
    body.append(text(624, 190, "Piel", size=13, fill=T.INK_3, anchor="end"))
    for x in (380.0, 470.0):
        body.append(f'<rect x="{fmt(x - 18)}" y="184" width="36" height="12" rx="3" fill="{T.INK_2}"/>')
        body.append(f'<path d="M{fmt(x)} 184V120" stroke="{T.INK_3}" stroke-width="1.6"/>')
    body.append(text(425, 214, "Electrodos de superficie", size=13, fill=T.INK_2, anchor="middle"))

    # Fibras musculares: las de la unidad motora en cian, el resto tenues.
    unit_rows = {1, 3, 5, 6}
    branch_x = 290.0
    for i in range(8):
        y = 238 + i * 20
        on = i in unit_rows
        color = T.TRACE if on else T.LINE
        body.append(
            f'<path d="M300 {fmt(y)}H600" stroke="{color}" stroke-width="{9 if on else 8}" '
            f'stroke-linecap="round" stroke-opacity="{0.9 if on else 0.55}"/>'
        )
        if on:
            jx = 340 + (i % 3) * 60
            body.append(trace(f"M{fmt(branch_x)} 276C{fmt(branch_x + 20)} 276 {fmt(jx - 20)} {fmt(y)} {fmt(jx)} {fmt(y)}",
                              width=2))
            body.append(f'<circle cx="{fmt(jx)}" cy="{fmt(y)}" r="5" fill="{T.INK}" stroke="{T.PANEL}" stroke-width="2"/>')
    body.append(text(450, 414, "Fibras de una misma unidad motora (cian) entre otras fibras", size=13,
                     fill=T.INK_2, anchor="middle"))

    # Señal registrada: poca fuerza (pocas unidades) -> más fuerza (interferencia).
    box_x, box_y, box_w, box_h = 300.0, 30.0, 320.0, 86.0
    body.append(f'<rect x="{fmt(box_x)}" y="{fmt(box_y)}" width="{fmt(box_w)}" height="{fmt(box_h)}" rx="8" '
                f'fill="{T.STRIP_BG}"/>')
    rng = np.random.default_rng(42)
    t = np.linspace(0, 1, 900)
    env = 0.08 + 0.92 * np.clip((t - 0.15) / 0.7, 0, 1) ** 1.4
    emg = env * rng.standard_normal(t.size)
    xs, ys = map_signal(t, np.clip(emg, -2.4, 2.4), x0=box_x + 8, width=box_w - 16, y_mid=box_y + box_h / 2,
                        px_per_unit=15, t_start=0, t_end=1)
    body.append(trace(path_from_xy(xs, ys), width=1.1))
    body.append(text(box_x + 10, box_y - 6, "poca fuerza", size=13, fill=T.INK_3))
    body.append(text(box_x + box_w - 10, box_y - 6, "más fuerza", size=13, fill=T.INK_3, anchor="end"))
    body.append(f'<path d="M380 120V114M470 120V114" stroke="{T.INK_3}" stroke-width="1.6"/>')
    svg = svg_root(W, H, join(body),
                   label="Esquema ilustrativo: una unidad motora y cómo la registra la EMG de superficie",
                   desc="Motoneurona alfa de la médula, su axón y las fibras que inerva; arriba, la EMG al aumentar la fuerza.")
    details = (
        "<p>Una <strong>unidad motora</strong> es una motoneurona α y todas las fibras musculares que inerva. "
        "Para hacer más fuerza el sistema nervioso:</p>"
        + _ol([
            "<strong>Recluta más unidades</strong>, de las pequeñas a las grandes (principio del tamaño).",
            "<strong>Acelera la descarga</strong> de las que ya están activas.",
        ])
        + "<p>La EMG de superficie suma todos esos potenciales: por eso su amplitud RMS crece con la fuerza "
          "y, con la fatiga, el espectro se desplaza a frecuencias más bajas.</p>"
    )
    return svg, details


# ═══════════════════════════════════════════════════════════════════════
# Registro de láminas y Atlas
# ═══════════════════════════════════════════════════════════════════════

TS_CITATION = (
    "Wasserthal J, et al. TotalSegmentator: Robust Segmentation of 104 Anatomic Structures in CT Images. "
    "Radiology: Artificial Intelligence 2023;5(5):e230024. Datos: TotalSegmentator dataset v2.0.1, "
    "doi:10.5281/zenodo.10047292 (CC BY 4.0), sujeto s1397"
)
MITDB_CITATION = (
    "Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. IEEE Eng Med Biol 2001;20(3):45-50 "
    "(registro 100, PhysioNet, ODC-By 1.0)"
)
CAP_CITATION = (
    "Terzano MG, et al. Atlas, rules, and recording techniques for the scoring of cyclic alternating "
    "pattern (CAP) in human sleep. Sleep Med 2001;2(6):537-553 (CAP Sleep Database, registro n16, "
    "PhysioNet, ODC-By 1.0)"
)
FSAVERAGE_CITATION = (
    "Fischl B, Sereno MI, Tootell RB, Dale AM. High-resolution intersubject averaging and a coordinate "
    "system for the cortical surface. Hum Brain Mapp 1999;8:272-284 (cabeza fsaverage, vía MNE-Python; "
    "posiciones 10-20 de MNE-Python, BSD-3)"
)
POSTEMA_QT_CITATION = (
    "Postema PG, Wilde AAM. The measurement of the QT interval. Curr Cardiol Rev 2014;10(3):287-294 "
    "(método de la tangente)"
)

PLATES: Dict[str, Plate] = {
    p.key: p for p in (
        Plate("body3d", "El cuerpo humano, de una tomografía real", "Cuerpo",
              "Esqueleto, corazón, pulmones, encéfalo y órganos reconstruidos de una persona real.",
              (TS_CITATION,), plates_real.body, chip="Anatomía real (TC)"),
        Plate("ecg_complex", "Anatomía del complejo ECG", "Corazón",
              "Ondas P, QRS y T de un latido real, con sus intervalos medidos.",
              (MITDB_CITATION, ECG_PAPER_CITATION, CHOU_CITATION, QRS_WIDTH_CITATION, POSTEMA_QT_CITATION),
              plates_real.ecg_complex, chip="Registro real"),
        Plate("conduction", "Sistema de conducción cardiaco", "Corazón",
              "Del nodo SA a las fibras de Purkinje, sobre un corazón real.",
              (GUYTON_CITATION, TS_CITATION), plates_real.conduction, chip="Corazón real + esquema"),
        Plate("precordial", "Derivaciones precordiales V1–V6", "Corazón",
              "Dónde va cada electrodo, calculado sobre un tórax real.",
              (ECG_PAPER_CITATION, TS_CITATION), plates_real.precordial, chip="Anatomía real (TC)"),
        Plate("hexaxial", "Sistema hexaxial y eje eléctrico", "Corazón",
              "Las seis derivaciones de miembros y el eje normal −30° a +90°.",
              (QRS_AXIS_CITATION,), _hexaxial),
        Plate("tachogram", "Del ECG al tacograma", "Corazón",
              "Cómo los intervalos RR reales se convierten en variabilidad (HRV).",
              (MITDB_CITATION, TASK_FORCE_HRV_CITATION), plates_real.tachogram, chip="Registro real"),
        Plate("eeg_1020", "Sistema internacional 10-20", "Cerebro",
              "Los 21 electrodos del EEG sobre una cabeza 3D.",
              (JASPER_CITATION, ACNS_NOMENCLATURE_CITATION, FSAVERAGE_CITATION), plates_real.eeg_1020,
              chip="Cabeza 3D (plantilla)"),
        Plate("eeg_bands", "Bandas del EEG", "Cerebro",
              "Un EEG real descompuesto en delta, theta, alfa, beta y gamma.",
              (CAP_CITATION, "Rangos: BAND_LIMITS_HZ de src/signals/eeg/eeg_analyzer.py (lo que mide EEG Neuro Lab)",
               KANE_GLOSSARY_CITATION), plates_real.eeg_bands, chip="Registro real"),
        Plate("respiratory_patterns", "Patrones respiratorios", "Respiración",
              "Siete patrones con flujo y esfuerzo: normal, apneas, Cheyne-Stokes…",
              (AASM_CITATION, "Trazos: RespiratorySignalGenerator del Respiratory Lab (simulación)"),
              _respiratory, chip="Simulación del laboratorio"),
        Plate("motor_unit", "Unidad motora y EMG de superficie", "Músculo",
              "De la motoneurona a la señal: reclutamiento y frecuencia de descarga.",
              (DE_LUCA_CITATION, HENNEMAN_CITATION), _motor_unit),
    )
}

ATLAS_TOPICS = ("Cuerpo", "Corazón", "Cerebro", "Respiración", "Músculo")
ATLAS: Tuple[str, ...] = tuple(PLATES.keys())

# Reexportados (los usan el ECG Lab y las pruebas).
CONDUCTION_PARTS = plates_real.CONDUCTION_PARTS
ECG_HIGHLIGHTS = plates_real.ECG_HIGHLIGHTS
EEG_DEFAULT_ACTIVE = plates_real.EEG_DEFAULT_ACTIVE
hrv_metrics = plates_real.hrv_metrics


def get_plate(key: str) -> Plate:
    return PLATES[key]


def plate_figure_html(key: str, **kwargs) -> str:
    """<figure> completo de una lámina: etiqueta, dibujo, explicación y fuente.

    Pensado para `st.markdown(..., unsafe_allow_html=True)`: una sola línea
    lógica de HTML, sin líneas en blanco (ver la nota de `svg.py`). Las
    láminas son deterministas: se memorizan por (lámina, resaltado).
    """
    frozen = tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in kwargs.items()))
    return _plate_figure_html_cached(key, frozen)


@lru_cache(maxsize=256)
def _plate_figure_html_cached(key: str, frozen_kwargs: tuple) -> str:
    plate = PLATES[key]
    art, details = plate.build(**dict(frozen_kwargs))
    sources = "".join(f"<li>{esc(s)}</li>" for s in plate.sources)
    return (
        f'<figure class="bc-plate" id="lamina-{plate.key}">'
        f'<div class="bc-plate-top"><span class="bc-chip">{esc(plate.chip)}</span>'
        f'<span class="bc-plate-topic">{esc(plate.topic)}</span></div>'
        f'<div class="bc-plate-art">{art}</div>'
        f'<figcaption><strong class="bc-plate-title">{esc(plate.title)}</strong>{details}'
        f'<details class="bc-src"><summary>Fuentes</summary><ul>{sources}</ul></details></figcaption>'
        f"</figure>"
    )
