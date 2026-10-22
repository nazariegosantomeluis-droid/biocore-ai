"""Láminas con datos reales (2026-10-21).

Sustituyen a los dibujos planos del Atlas:

- Complejo ECG, tacograma y bandas del EEG: registros reales de PhysioNet
  (`src/signals/reference_recordings.py`) medidos con el código de la app.
- Precordiales, 10-20 y sistema de conducción: renders de anatomía real
  (`visualization/art/renders.py`) con los rótulos dibujados encima en SVG
  sobre las anclas que calculó el renderizador.
- Cuerpo completo: el render de la tomografía, con los volúmenes medidos.

Cada constructor devuelve `(arte_html, detalles_html)`, igual que los de
`plates.py`; el registro de láminas vive allí.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from visualization.art import renders as R
from visualization.art import tokens as T
from visualization.art.svg import esc, fmt, join, map_signal, mm_grid, path_from_xy, svg_root, text, trace

PILL_BG = "#0b1426"


def _ul(items) -> str:
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def _ol(items, highlight_index: Optional[int] = None) -> str:
    rows = []
    for i, item in enumerate(items):
        cls = ' class="bc-on"' if highlight_index == i else ""
        rows.append(f"<li{cls}>{item}</li>")
    return '<ol class="bc-steps">' + "".join(rows) + "</ol>"


def _pill(x: float, y: float, label: str, *, k: float, on: bool = False, size: float = 13.0) -> str:
    """Rótulo en cápsula centrado en (x, y), escalado por `k`."""
    fs = size * k
    w = (len(label) * 0.62 * fs) + 14 * k
    h = fs + 10 * k
    fill = T.TRACE if on else PILL_BG
    ink = T.BACKGROUND if on else T.INK
    stroke = T.TRACE if on else "rgba(224,231,255,.55)"
    return (
        f'<rect x="{fmt(x - w / 2)}" y="{fmt(y - h / 2)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(h / 2)}" '
        f'fill="{fill}" fill-opacity="{0.96 if on else 0.86:g}" stroke="{stroke}" stroke-width="{fmt(1.2 * k)}"/>'
        + text(x, y + fs * 0.36, label, size=round(fs, 1), fill=ink, anchor="middle", weight=700,
               family=T.FONT_HEAD)
    )


def _leader(x0: float, y0: float, x1: float, y1: float, *, k: float, on: bool = False) -> str:
    color = T.TRACE if on else "rgba(224,231,255,.7)"
    return (f'<path d="M{fmt(x0)} {fmt(y0)}L{fmt(x1)} {fmt(y1)}" stroke="{color}" '
            f'stroke-width="{fmt((1.8 if on else 1.3) * k)}" stroke-linecap="round"/>')


def _ring(x: float, y: float, r: float, *, k: float) -> str:
    return (f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(r)}" fill="none" stroke="{T.TRACE}" '
            f'stroke-width="{fmt(3 * k)}"/>'
            f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(r + 5 * k)}" fill="none" stroke="{T.TRACE}" '
            f'stroke-opacity="0.35" stroke-width="{fmt(2 * k)}"/>')


def _ms(value_ms: float) -> str:
    return f"{value_ms:.0f} ms"


# ═══════════════════════════════════════════════════════════════════════
# 1. Complejo ECG: latido mediano real (MIT-BIH 100, MLII)
# ═══════════════════════════════════════════════════════════════════════

ECG_HIGHLIGHTS = ("P", "PR", "QRS", "ST", "T", "QT")


@lru_cache(maxsize=1)
def reference_ecg_beat():
    """(Beat, Delineation) del latido mediano real (se calcula una vez)."""
    from src.signals.ecg.beat_delineation import reference_beat

    return reference_beat()


def ecg_complex(highlight: Optional[str] = None) -> Tuple[str, str]:
    beat, d = reference_ecg_beat()
    mm = 16.0
    px_s, px_mv = 25 * mm, 10 * mm          # 25 mm/s, 10 mm/mV
    t0, t1 = -0.30, 0.56
    x0, top = 24.0, 46.0
    paper_w = (t1 - t0) * px_s
    up_mv, down_mv = 1.4, 0.4
    paper_h = (up_mv + down_mv) * px_mv
    base = top + up_mv * px_mv
    W, H = x0 * 2 + paper_w, top + paper_h + 3 * 30 + 44

    t_s = beat.t_ms / 1000.0
    v = beat.v - d.baseline_mv
    keep = (t_s >= t0) & (t_s <= t1)

    def X(t_ms: float) -> float:
        return x0 + (t_ms / 1000.0 - t0) * px_s

    spans = {
        "P": (d.p_on, d.p_off, "Onda P"),
        "PR": (d.p_on, d.qrs_on, "Intervalo PR"),
        "QRS": (d.qrs_on, d.qrs_off, "Complejo QRS"),
        "ST": (d.qrs_off, d.t_on, "Segmento ST"),
        "T": (d.t_on, d.t_off, "Onda T"),
        "QT": (d.qrs_on, d.t_off, "Intervalo QT"),
    }
    body: List[str] = [
        f'<rect x="{fmt(x0)}" y="{fmt(top)}" width="{fmt(paper_w)}" height="{fmt(paper_h)}" rx="6" '
        f'fill="{T.STRIP_BG}"/>',
        mm_grid(x0, top, paper_w, paper_h, mm, key="ecg-real"),
    ]
    if highlight in spans:
        a, b, _ = spans[highlight]
        body.append(f'<rect x="{fmt(X(a))}" y="{fmt(top)}" width="{fmt(X(b) - X(a))}" height="{fmt(paper_h)}" '
                    f'fill="{T.TRACE_FILL}"/>')
    xs, ys = map_signal(t_s[keep], v[keep], x0=x0, width=paper_w, y_mid=base, px_per_unit=px_mv,
                        t_start=t0, t_end=t1)
    body.append(trace(path_from_xy(xs, ys, tol=0.25), width=2.6))

    # Rótulos de las ondas en sus posiciones medidas.
    def at(t_ms: float) -> float:
        return float(np.interp(t_ms, beat.t_ms, v))

    seg = (beat.t_ms >= d.qrs_on) & (beat.t_ms <= d.r)
    q_t = float(beat.t_ms[seg][np.argmin(v[seg])]) if seg.any() else d.qrs_on
    seg = (beat.t_ms >= d.r) & (beat.t_ms <= d.qrs_off)
    s_t = float(beat.t_ms[seg][np.argmin(v[seg])]) if seg.any() else d.qrs_off
    labels = [("P", d.p_peak), ("R", d.r), ("T", d.t_peak)]
    if at(q_t) < -0.03:
        labels.append(("Q", q_t))
    if at(s_t) < -0.03:
        labels.append(("S", s_t))
    for name, tm in labels:
        y_peak = base - at(tm) * px_mv
        y = y_peak - 12 if at(tm) >= 0 else y_peak + 24
        dx = {"Q": -11, "S": 11}.get(name, 0)
        body.append(text(X(tm) + dx, y, name, size=19, fill=T.INK, anchor="middle", weight=700,
                         family=T.FONT_HEAD, halo=T.STRIP_BG))

    rows = ((("PR", 0), ("ST", 0)), (("QRS", 1),), (("QT", 2),))
    for row in rows:
        for key, level in row:
            a, b, _ = spans[key]
            y = top + paper_h + 22 + level * 30
            on = key == highlight
            color = T.TRACE if on else T.INK_2
            body.append(
                f'<path d="M{fmt(X(a))} {fmt(y - 6)}V{fmt(y)}H{fmt(X(b))}V{fmt(y - 6)}" fill="none" '
                f'stroke="{color}" stroke-width="{2.4 if on else 1.4:g}" stroke-linejoin="round"/>'
            )
            body.append(text((X(a) + X(b)) / 2, y + 17, f"{key} {_ms(b - a)}", size=14, fill=color,
                             anchor="middle", weight=700 if on else 500))
    sx, sy = x0 + 6, top - 12
    body.append(f'<path d="M{fmt(sx)} {fmt(sy)}H{fmt(sx + 5 * mm)}" stroke="{T.INK_3}" stroke-width="1.6"/>')
    body.append(text(sx + 5 * mm + 8, sy + 5, "0.20 s", size=13, fill=T.INK_3))
    body.append(text(x0 + paper_w - 4, sy + 5, "25 mm/s, 10 mm/mV", size=13, fill=T.INK_3, anchor="end"))

    hr = 60000.0 / beat.rr_ms
    from clinical.calculators import classify_qtc, qtc_bazett

    qtc = qtc_bazett(d.qt_ms, beat.rr_ms / 1000.0)
    qtc_level = classify_qtc(qtc, "M")[0]
    label = "Registro real: latido mediano del ECG (MIT-BIH 100, MLII) con sus ondas e intervalos medidos"
    if highlight in spans:
        label += f"; resaltado: {spans[highlight][2]}"
    svg = svg_root(W, H, join(body), label=label,
                   desc=f"Mediana de {beat.n_beats} latidos normales a {hr:.0f} lpm; intervalos medidos por el código.")
    details = (
        f"<p>Latido <em>real</em>: la mediana de {beat.n_beats} latidos normales del registro 100 de la "
        f"MIT-BIH (hombre de 69 años, derivación MLII, {hr:.0f} lpm). Los intervalos los mide el código "
        "sobre ese latido, no se escribieron a mano:</p>"
        + _ul([
            f"<strong>PR {_ms(d.pr_ms)}</strong>: del inicio de P al inicio del QRS; en el adulto, 120–200 ms.",
            f"<strong>QRS {_ms(d.qrs_ms)}</strong>: despolarización ventricular; ≥ 120 ms sugiere bloqueo de rama.",
            f"<strong>QT {_ms(d.qt_ms)}</strong> a {hr:.0f} lpm; corregido por la frecuencia (Bazett), "
            f"<strong>QTc {_ms(qtc)}</strong>: "
            + ("dentro de rango (AHA/ACCF/HRS 2009)." if qtc_level == "normal" else
               ("corto" if qtc <= 390 else "prolongado")
               + " (en hombres lo normal es menos de 450 ms; AHA/ACCF/HRS 2009). Es un rasgo de este registro "
                 "real: la onda T es baja, ancha y tardía.")
            + " El QTc de cualquier ECG se calcula en Calculadoras Clínicas.",
            "<strong>Papel</strong>: un cuadro pequeño = 0.04 s y 0.1 mV; uno grande = 0.20 s y 0.5 mV.",
        ])
        + "<p>Medición automática: QRS por la pendiente, P por umbral sobre la línea de base y fin de T por "
          "el método de la tangente, sobre el latido suavizado. Puede diferir unos milisegundos de la "
          "medición manual.</p>"
    )
    return svg, details


# ═══════════════════════════════════════════════════════════════════════
# 2. Tacograma: intervalos RR reales (MIT-BIH 100)
# ═══════════════════════════════════════════════════════════════════════

def hrv_metrics(rr_ms: Sequence[float]) -> Dict[str, float]:
    """SDNN, RMSSD y media con las MISMAS fórmulas de `render_hrv_page()`."""
    rr = np.asarray(rr_ms, dtype=float)
    return {"sdnn": float(np.std(rr, ddof=1)), "rmssd": float(np.sqrt(np.mean(np.diff(rr) ** 2))),
            "mean": float(np.mean(rr)), "n": int(rr.size)}


@lru_cache(maxsize=1)
def tachogram_window() -> dict:
    """Siete latidos normales consecutivos del registro 100: tramo de ECG,
    muestras R (refinadas al máximo local) e intervalos RR en ms."""
    from src.signals.reference_recordings import mitdb_100

    d = mitdb_100()
    fs, x, beats, sym = d["fs"], d["mlii"], d["beats"], d["symbols"]
    start = next(i for i in range(2, len(beats) - 8) if sym[i:i + 7] == "N" * 7 and beats[i] > 0.5 * fs)
    r = []
    for b in beats[start:start + 7]:
        lo, hi = int(b - 0.025 * fs), int(b + 0.025 * fs)
        r.append(lo + int(np.argmax(x[lo:hi])))
    r = np.asarray(r)
    a, b = int(r[0] - 0.30 * fs), int(r[-1] + 0.36 * fs)
    seg = x[a:b]
    return {"fs": fs, "ecg": seg - np.median(seg), "r": r - a, "rr_ms": np.diff(r) / fs * 1000.0,
            "start_s": a / fs}


def tachogram() -> Tuple[str, str]:
    from src.signals.reference_recordings import normal_rr_ms

    win = tachogram_window()
    fs, ecg, r, rr_ms = win["fs"], win["ecg"], win["r"], win["rr_ms"]
    W, H = 640.0, 420.0
    x0, w = 30.0, W - 60
    t_end = ecg.size / fs
    px_s = w / t_end
    ecg_mid, ecg_top, ecg_h = 150.0, 40.0, 150.0
    body: List[str] = [
        f'<rect x="{fmt(x0)}" y="{fmt(ecg_top)}" width="{fmt(w)}" height="{fmt(ecg_h)}" rx="6" fill="{T.STRIP_BG}"/>',
        mm_grid(x0, ecg_top, w, ecg_h, px_s * 0.04, key="tacho-real"),
    ]
    t = np.arange(ecg.size) / fs
    xs, ys = map_signal(t, ecg, x0=x0, width=w, y_mid=ecg_mid, px_per_unit=70, t_start=0, t_end=t_end)
    body.append(trace(path_from_xy(xs, ys, tol=0.25), width=2.0))
    r_x = x0 + (r / fs) * px_s
    for i, xr in enumerate(r_x):
        yr = ecg_mid - float(ecg[r[i]]) * 70
        body.append(f'<circle cx="{fmt(xr)}" cy="{fmt(yr)}" r="5" fill="{T.INK}" stroke="{T.STRIP_BG}" stroke-width="2"/>')
    for i, ms in enumerate(rr_ms):
        a, b = r_x[i], r_x[i + 1]
        yb = ecg_top + 14
        body.append(f'<path d="M{fmt(a)} {fmt(yb + 6)}V{fmt(yb)}H{fmt(b)}V{fmt(yb + 6)}" fill="none" '
                    f'stroke="{T.INK_2}" stroke-width="1.4"/>')
        body.append(text((a + b) / 2, yb - 4, f"{ms:.0f}", size=13, fill=T.INK_2, anchor="middle", weight=600))
    body.append(text(x0, 28, "ECG real: cada punto blanco es una onda R; entre dos R, el intervalo RR en ms",
                     size=13, fill=T.INK_3))
    g_top, g_h = 250.0, 130.0
    lo = float(np.floor((rr_ms.min() - 25) / 10) * 10)
    hi = float(np.ceil((rr_ms.max() + 25) / 10) * 10)
    body.append(f'<path d="M{fmt(x0)} {fmt(g_top + g_h)}H{fmt(x0 + w)}" stroke="{T.INK_3}" stroke-width="1.2"/>')
    for val in np.linspace(lo, hi, 4)[1:-1]:
        yv = g_top + g_h - (val - lo) / (hi - lo) * g_h
        body.append(f'<path d="M{fmt(x0)} {fmt(yv)}H{fmt(x0 + w)}" stroke="{T.LINE}" stroke-opacity="0.45"/>')
        body.append(text(x0 + w + 4, yv + 4, f"{val:.0f}", size=12, fill=T.INK_3))
    pts = []
    for i, ms in enumerate(rr_ms):
        xm = (r_x[i] + r_x[i + 1]) / 2
        ym = g_top + g_h - (ms - lo) / (hi - lo) * g_h
        pts.append((xm, ym))
        body.append(f'<path d="M{fmt(xm)} {fmt(ecg_top + ecg_h + 4)}V{fmt(ym - 9)}" stroke="{T.INK_3}" '
                    f'stroke-opacity="0.35" stroke-dasharray="3 5"/>')
    body.append(trace(path_from_xy([p[0] for p in pts], [p[1] for p in pts], tol=0), width=2))
    for xm, ym in pts:
        body.append(f'<circle cx="{fmt(xm)}" cy="{fmt(ym)}" r="6" fill="{T.TRACE}" stroke="{T.PANEL}" stroke-width="2"/>')
    body.append(text(x0, g_top - 10, "Tacograma: RR (ms) latido a latido", size=13, fill=T.INK_3))
    svg = svg_root(W, H, join(body),
                   label="Registro real: cómo los intervalos RR del ECG forman el tacograma de HRV (MIT-BIH 100)",
                   desc="Siete latidos normales consecutivos; las R son las anotaciones de los cardiólogos.")
    m = hrv_metrics(normal_rr_ms(max_beats=2000))
    details = (
        "<p>La HRV no mide la frecuencia cardiaca: mide <em>cuánto cambia</em> el intervalo entre latidos. "
        f"En los 5 minutos de este registro ({m['n']} intervalos entre latidos normales, según las "
        "anotaciones de la base MIT-BIH):</p>"
        + _ul([
            f"<strong>SDNN {m['sdnn']:.0f} ms</strong>: desviación estándar de todos los RR (variabilidad global).",
            f"<strong>RMSSD {m['rmssd']:.0f} ms</strong>: raíz cuadrática media de las diferencias sucesivas "
            "(tono vagal, corto plazo).",
            f"<strong>RR medio {m['mean']:.0f} ms</strong> ({60000 / m['mean']:.0f} lpm).",
            "Calculados con las mismas fórmulas que HRV Analysis aplica a tu serie.",
        ])
    )
    return svg, details


# ═══════════════════════════════════════════════════════════════════════
# 3. Bandas del EEG: EEG real (CAP Sleep n16, P4-O2) filtrado por banda
# ═══════════════════════════════════════════════════════════════════════

BAND_META = (
    ("delta", "δ", "Delta"), ("theta", "θ", "Theta"), ("alpha", "α", "Alfa"),
    ("beta", "β", "Beta"), ("gamma", "γ", "Gamma"),
)
EEG_REFERENCE_LEAD = "P4-O2"


@lru_cache(maxsize=1)
def reference_eeg_bands() -> dict:
    """Análisis del EEG real de referencia con el MISMO `EegAnalyzer` del
    laboratorio + 4 s filtrados en cada banda (`BAND_LIMITS_HZ`)."""
    from scipy.signal import butter, sosfiltfilt

    from src.signals.eeg.eeg_analyzer import BAND_LIMITS_HZ, EegAnalyzer
    from src.signals.reference_recordings import cap_n16

    d = cap_n16()
    fs = d["fs"]
    x = d["leads"][EEG_REFERENCE_LEAD]
    analysis = EegAnalyzer(fs=fs).analyze(x)
    total = sum(analysis.band_power.values()) or 1.0
    rel = {b: 100.0 * p / total for b, p in analysis.band_power.items()}
    a, b = int(10 * fs), int(14 * fs)
    raw = x[a:b] - np.mean(x[a:b])
    bands = {}
    for band, (lo, hi) in BAND_LIMITS_HZ.items():
        hi = min(hi, 0.45 * fs)
        sos = butter(4, [lo, hi], btype="band", fs=fs, output="sos")
        bands[band] = sosfiltfilt(sos, x)[a:b]
    return {"fs": fs, "raw": raw, "bands": bands, "relative": rel, "dominant": analysis.dominant_band,
            "limits": dict(BAND_LIMITS_HZ)}


def eeg_bands(dominant: Optional[str] = None) -> Tuple[str, str]:
    from src.signals.eeg.eeg_analyzer import BAND_CLASSIFICATION

    ref = reference_eeg_bands()
    fs = ref["fs"]
    row_h, top = 74.0, 96.0
    x_wave, w_wave = 168.0, 300.0
    W = 640.0
    H = top + row_h * len(BAND_META) + 30
    body: List[str] = [
        f'<rect x="{fmt(x_wave - 6)}" y="14" width="{fmt(w_wave + 12)}" height="66" rx="8" fill="{T.STRIP_BG}"/>',
        text(16, 40, "EEG real", size=16, fill=T.INK, weight=700, family=T.FONT_HEAD),
        text(16, 60, f"{EEG_REFERENCE_LEAD}, 4 s", size=13, fill=T.INK_2),
    ]
    t = np.arange(ref["raw"].size) / fs
    scale = 28.0 / (np.max(np.abs(ref["raw"])) or 1.0)
    xs, ys = map_signal(t, ref["raw"], x0=x_wave, width=w_wave, y_mid=47, px_per_unit=scale)
    body.append(trace(path_from_xy(xs, ys, tol=0.25), width=1.6))
    for i, (band, letter, name) in enumerate(BAND_META):
        y0 = top + i * row_h
        mid = y0 + row_h / 2
        on = dominant == band
        dim = dominant is not None and not on
        if on:
            body.append(f'<rect x="4" y="{fmt(y0 + 3)}" width="{fmt(W - 8)}" height="{fmt(row_h - 6)}" rx="10" '
                        f'fill="{T.TRACE_FILL}"/>')
        body.append(text(28, mid + 12, letter, size=34, fill=T.TRACE if on else T.INK, anchor="middle", weight=600))
        body.append(text(56, mid - 4, name, size=17, fill=T.INK, weight=700, family=T.FONT_HEAD))
        lo, hi = ref["limits"][band]
        body.append(text(56, mid + 18, f"{lo:g}–{hi:g} Hz", size=14, fill=T.INK_2))
        v = ref["bands"][band]
        sc = 26.0 / (np.max(np.abs(v)) or 1.0)
        xs, ys = map_signal(t, v, x0=x_wave, width=w_wave, y_mid=mid, px_per_unit=sc)
        body.append(trace(path_from_xy(xs, ys, tol=0.25), width=1.5 if dim else 1.9, opacity=0.45 if dim else 1.0))
        pct = ref["relative"].get(band, 0.0)
        body.append(text(W - 16, mid - 2, f"{pct:.0f} %", size=18, fill=T.TRACE if on else T.INK, anchor="end",
                         weight=700, family=T.FONT_HEAD))
        body.append(text(W - 16, mid + 17, "de la potencia", size=12, fill=T.INK_3, anchor="end"))
        if i < len(BAND_META) - 1:
            body.append(f'<path d="M16 {fmt(y0 + row_h)}H{fmt(W - 16)}" stroke="{T.LINE}" stroke-opacity="0.5"/>')
    body.append(text(x_wave, H - 8, "Cada banda escalada a su propio alto; el % es la potencia medida (Welch)",
                     size=12, fill=T.INK_3))
    label = "Registro real: EEG de vigilia descompuesto en sus cinco bandas (CAP Sleep Database n16)"
    if dominant:
        label += f"; banda dominante resaltada: {dominant}"
    svg = svg_root(W, H, join(body), label=label,
                   desc="Filtrado por banda con los límites exactos del analizador; potencia relativa medida.")
    ref_dom = ref["dominant"]
    ref_name = dict((b, n) for b, _, n in BAND_META).get(ref_dom, ref_dom)
    rows = []
    for band, letter, name in BAND_META:
        lo, hi = ref["limits"][band]
        state = BAND_CLASSIFICATION.get(band, "")
        mark = " — <strong>dominante en tu señal</strong>" if dominant == band else ""
        rows.append(f"<strong>{letter} {name}</strong> ({lo:g}–{hi:g} Hz): {esc(state)}{mark}")
    details = (
        f"<p>Arriba, 4 s de EEG <em>real</em> de una persona sana despierta y relajada (derivación "
        f"{EEG_REFERENCE_LEAD}, posterior). Analizado con el mismo método que EEG Neuro Lab, domina "
        f"<strong>{esc(ref_name)}</strong> ({ref['relative'].get(ref_dom, 0):.0f} % de la potencia): el ritmo "
        "alfa posterior típico de la vigilia tranquila.</p>" + _ul(rows)
        + "<p>Muchos textos redondean los rangos a 0.5–4, 4–8, 8–13 y 13–30 Hz; aquí van los exactos que "
          "integra el analizador.</p>"
    )
    return svg, details


# ═══════════════════════════════════════════════════════════════════════
# 4. Precordiales V1-V6 sobre el tórax real
# ═══════════════════════════════════════════════════════════════════════

PRECORDIAL_RULES = (
    ("V1", "4.º espacio intercostal (EIC), borde esternal derecho."),
    ("V2", "4.º EIC, borde esternal izquierdo."),
    ("V3", "a la mitad entre V2 y V4."),
    ("V4", "5.º EIC, línea medioclavicular izquierda."),
    ("V5", "línea axilar anterior izquierda, a la altura de V4."),
    ("V6", "línea axilar media izquierda, a la altura de V4."),
)
# Dirección del rótulo respecto al electrodo (en este render, vista
# oblicua anterior izquierda): repartidos para que no se pisen.
_PRECORDIAL_OFFSETS = {"V1": (-46, -50), "V2": (-6, -62), "V3": (58, -46), "V4": (66, 6),
                       "V5": (10, 64), "V6": (2, -62)}


def _landmark_drop_cm() -> Optional[Tuple[float, float]]:
    """(caída V2→V4, distancia V4→V6) en cm, medidas en la TC."""
    try:
        from visualization.anatomy3d import load_body

        p = load_body().landmarks
        return float(p["V2"][2] - p["V4"][2]) / 10.0, float(np.linalg.norm(p["V4"] - p["V6"])) / 10.0
    except Exception:
        return None


def precordial() -> Tuple[str, str]:
    name = "atlas_precordial"
    w, h = R.size(name)
    k = w / 600.0
    an = R.anchors(name)
    body: List[str] = []
    for lead, (dx, dy) in _PRECORDIAL_OFFSETS.items():
        if lead not in an:
            continue
        x, y, _ = an[lead]
        lx, ly = x + dx * k, y + dy * k
        body.append(_leader(x, y, lx, ly, k=k))
        body.append(_pill(lx, ly, lead, k=k, size=15))
    art = R.figure_html(
        name, join(body),
        label="Anatomía real: tórax de una tomografía con los electrodos precordiales V1 a V6",
        desc="Vista oblicua anterior izquierda; costillas, cartílagos, esternón, corazón y pulmones reales.")
    drop = _landmark_drop_cm()
    measured = ""
    if drop:
        measured = (f"<p>En esta tomografía, V4 quedó {drop[0]:.1f} cm más abajo que V2 y V6 a "
                    f"{drop[1]:.1f} cm de V4 por la pared lateral.</p>")
    details = (
        "<p>Tórax <em>real</em> reconstruido de una tomografía. Las posiciones se calcularon sobre esta "
        "persona con las reglas estándar: los cartílagos costales se cuentan en el borde del esternón (4.º "
        "espacio) y en la línea medioclavicular (5.º espacio), y cada punto se lleva a la piel.</p>"
        + _ul([f"<strong>{lead}</strong>: {rule}" for lead, rule in PRECORDIAL_RULES])
        + measured
        + "<p>Un electrodo un espacio más arriba o más abajo cambia la morfología del QRS: es el error más común. "
          "Las posiciones son aproximadas: en la práctica se palpan.</p>"
    )
    return art, details


# ═══════════════════════════════════════════════════════════════════════
# 5. Sistema 10-20 sobre una cabeza 3D
# ═══════════════════════════════════════════════════════════════════════

EEG_1020_NAMES = ("Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8", "T7", "C3", "Cz", "C4", "T8",
                  "P7", "P3", "Pz", "P4", "P8", "O1", "O2", "Fpz", "Oz")
EEG_DEFAULT_ACTIVE = ("Fp1", "Fp2", "C3", "C4")   # los que dibuja EEG Neuro Lab


def _head_overlay(name: str, active: Sequence[str], *, min_facing: float, radial: float) -> str:
    w, h = R.size(name)
    k = w / 600.0
    an = R.anchors(name)
    cx = float(np.mean([v[0] for v in an.values()]))
    cy = float(np.mean([v[1] for v in an.values()]))
    placed: List[np.ndarray] = []
    body: List[str] = []
    # Primero los del borde (mirada rasante): se quedan con el lugar de
    # fuera. Si un rótulo choca con otro ya puesto, se prueba hacia dentro
    # y luego girado.
    for el, (x, y, facing) in sorted(an.items(), key=lambda kv: kv[1][2]):
        if facing < min_facing:
            continue
        on = el in active
        p = np.array([x, y])
        d = p - np.array([cx, cy])
        d = d / (np.linalg.norm(d) or 1.0)
        options = [p + d * radial * k, p - d * radial * k, p + _rot(d, 90) * radial * k, p + _rot(d, -90) * radial * k]
        spot = next((o for o in options if all(np.linalg.norm(o - q) > 34 * k for q in placed)), options[0])
        placed.append(spot)
        if on:
            body.append(_ring(x, y, 11 * k, k=k))
        body.append(_pill(spot[0], spot[1], el, k=k, on=on, size=14))
    return join(body)


def eeg_1020(active: Sequence[str] = EEG_DEFAULT_ACTIVE) -> Tuple[str, str]:
    known = set(R.anchors("atlas_1020_top"))
    active = tuple(a for a in active if a in known)
    listed = ", ".join(active) if active else "ninguno"
    top = R.figure_html("atlas_1020_top", _head_overlay("atlas_1020_top", active, min_facing=-0.45, radial=30),
                        label=f"Cabeza 3D vista desde arriba con el sistema 10-20; resaltados {listed}",
                        desc="Nariz arriba; izquierda del paciente a la izquierda.")
    left = R.figure_html("atlas_1020_left", _head_overlay("atlas_1020_left", active, min_facing=-0.12, radial=26),
                         label="Cabeza 3D vista desde la izquierda con los electrodos visibles del sistema 10-20",
                         desc="Cara a la izquierda.")
    art = f'<div class="bc-render-pair">{top}{left}</div>'
    details = (
        f"<p>Resaltados (cian): <strong>{esc(listed)}</strong>, los canales que dibuja este laboratorio. "
        "Cabeza promedio (fsaverage) con las 21 posiciones estándar calculadas sobre ella.</p>"
        + _ul([
            "Letras: <strong>Fp</strong> frontopolar, <strong>F</strong> frontal, <strong>C</strong> central, "
            "<strong>T</strong> temporal, <strong>P</strong> parietal, <strong>O</strong> occipital.",
            "Números <strong>impares</strong> a la izquierda, <strong>pares</strong> a la derecha; "
            "<strong>z</strong> (cero) en la línea media.",
            "«10-20»: los electrodos se separan 10 % o 20 % de las distancias nasion–inion y entre los "
            "puntos preauriculares, así el mapa se adapta a cada cabeza.",
            "T7/T8/P7/P8 son los nombres actuales de T3/T4/T5/T6.",
        ])
    )
    return art, details


# ═══════════════════════════════════════════════════════════════════════
# 6. Sistema de conducción sobre un corazón real
# ═══════════════════════════════════════════════════════════════════════

CONDUCTION_PARTS = ("SA Node", "Atria", "AV Node", "His Bundle", "Purkinje")
CONDUCTION_TEXT = (
    "<strong>Nodo SA</strong>: marcapasos natural, donde la vena cava superior entra en la aurícula derecha; "
    "inicia la despolarización auricular (onda P).",
    "<strong>Aurículas</strong>: el impulso recorre ambas aurículas (vías internodales y haz de Bachmann) "
    "y llega al nodo AV.",
    "<strong>Nodo AV</strong>: retraso fisiológico para el llenado ventricular (segmento PR).",
    "<strong>Haz de His y ramas</strong>: conducen el impulso por el tabique (inicio del QRS).",
    "<strong>Fibras de Purkinje</strong>: distribución rápida que sincroniza la contracción ventricular (QRS).",
)


def _bez(p0, p1, p2) -> str:
    return f"M{fmt(p0[0])} {fmt(p0[1])}Q{fmt(p1[0])} {fmt(p1[1])} {fmt(p2[0])} {fmt(p2[1])}"


@lru_cache(maxsize=4)
def _alpha_mask(name: str) -> Optional[np.ndarray]:
    """Máscara de la silueta del render (alfa > 200), para que los trazos
    del esquema queden dentro del órgano."""
    try:
        from PIL import Image

        with Image.open(R.STATIC_DIR / R.entry(name)["file"]) as im:
            return np.asarray(im.convert("RGBA"))[..., 3] > 200
    except Exception:
        return None


def _inside(mask: Optional[np.ndarray], p: np.ndarray, margin: int = 6) -> bool:
    if mask is None:
        return True
    x, y = int(round(p[0])), int(round(p[1]))
    h, w = mask.shape
    if not (margin <= x < w - margin and margin <= y < h - margin):
        return False
    return bool(mask[y - margin:y + margin + 1, x - margin:x + margin + 1].all())


def _clip_to(mask, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Recorta el segmento a→b al último punto dentro de la silueta."""
    last = a
    for f in np.linspace(0, 1, 40):
        p = a + (b - a) * f
        if not _inside(mask, p):
            break
        last = p
    return last


def _rot(v: np.ndarray, deg: float) -> np.ndarray:
    r = np.radians(deg)
    return np.array([v[0] * np.cos(r) - v[1] * np.sin(r), v[0] * np.sin(r) + v[1] * np.cos(r)])


def conduction(highlight: Optional[str] = None) -> Tuple[str, str]:
    name = "atlas_heart"
    w, h = R.size(name)
    k = w / 600.0
    a = {key: np.array(v[:2]) for key, v in R.anchors(name).items()}
    mask = _alpha_mask(name)
    on_i = CONDUCTION_PARTS.index(highlight) if highlight in CONDUCTION_PARTS else None
    glow = "#fde68a"   # trazo del esquema: ámbar claro sobre el músculo rojo (no es un color de estado)

    def style(i: int, base_w: float) -> Tuple[str, float, float]:
        if on_i is None:
            return glow, base_w * k, 0.95
        return (T.TRACE, (base_w + 1.8) * k, 1.0) if i == on_i else (glow, base_w * k, 0.38)

    sa, av, his, apex, lv, la = (a[x] for x in ("SA", "AV", "His", "Apex", "LV", "LA"))
    shadow = 'stroke="#0b1426" stroke-opacity="0.55" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    body: List[str] = []
    paths: List[Tuple[int, str, float]] = []
    # 2) Vías internodales SA→AV y haz de Bachmann SA→AI.
    mid = (sa + av) / 2
    perp = np.array([-(av - sa)[1], (av - sa)[0]])
    perp = perp / (np.linalg.norm(perp) or 1.0)
    for off in (-30, 0, 26):
        paths.append((1, _bez(sa, mid + perp * off * k, av), 2.4))
    la_end = _clip_to(mask, sa, la)
    paths.append((1, _bez(sa, (sa + la_end) / 2 + np.array([0, -40 * k]), la_end), 2.4))
    # 4) Haz de His; rama derecha hacia el VD y rama izquierda hacia el VI, ambas hacia el ápex.
    paths.append((3, _bez(av, (av + his) / 2, his), 4.0))
    # En proyección frontal ambas ramas siguen el tabique; se separan para
    # leerlas: la derecha baja hacia la pared inferior del VD, la izquierda
    # va hacia la pared lateral del VI.
    rb_target = np.array([apex[0] - 150 * k, apex[1] + 8 * k])
    lb_target = lv + (apex - lv) * 0.55
    rb_end = _clip_to(mask, his, his + (rb_target - his) * 0.9)
    lb_end = _clip_to(mask, his, his + (lb_target - his) * 0.92)
    paths.append((3, _bez(his, (his + rb_end) / 2 + np.array([-14 * k, 10 * k]), rb_end), 3.2))
    paths.append((3, _bez(his, (his + lb_end) / 2 + np.array([0, -22 * k]), lb_end), 3.2))
    # 5) Purkinje: un abanico al final de cada rama, recortado a la silueta.
    span = float(np.linalg.norm(apex - his))
    for end in (rb_end, lb_end):
        d = apex - end
        n = np.linalg.norm(d)
        d = d / n if n > 1 else (apex - his) / (span or 1.0)
        for ang in (-75, -40, -10, 20, 50, 80):
            tip = _clip_to(mask, end, end + _rot(d, ang) * span * 0.32)
            if np.linalg.norm(tip - end) > 10 * k:
                ctrl = (end + tip) / 2 + _rot(d, ang + 90) * 6 * k
                paths.append((4, _bez(end, ctrl, tip), 1.7))
    for i, d, base_w in paths:
        col, wdt, op = style(i, base_w)
        body.append(f'<path d="{d}" {shadow} stroke-width="{fmt(wdt + 3.5 * k)}"/>')
        body.append(trace(d, color=col, width=round(wdt, 2), opacity=op))
    for i, p in ((0, sa), (2, av)):
        col, _, op = style(i, 3.0)
        body.append(f'<ellipse cx="{fmt(p[0])}" cy="{fmt(p[1])}" rx="{fmt(13 * k)}" ry="{fmt(9 * k)}" '
                    f'fill="{col}" fill-opacity="{op:g}" stroke="#0b1426" stroke-width="{fmt(2.5 * k)}"/>')
    marks = [sa + np.array([-42, -36]) * k, mid + perp * -64 * k, av + np.array([-46, 30]) * k,
             his + np.array([-34, 44]) * k, apex + np.array([-62, -26]) * k]
    for i, p in enumerate(marks):
        on = on_i == i
        r = 15 * k
        body.append(f'<circle cx="{fmt(p[0])}" cy="{fmt(p[1])}" r="{fmt(r)}" fill="{T.TRACE if on else PILL_BG}" '
                    f'stroke="{T.TRACE if on else T.INK_2}" stroke-width="{fmt(2 * k)}"/>')
        body.append(text(p[0], p[1] + 5.5 * k, i + 1, size=round(16 * k, 1), fill=T.BACKGROUND if on else T.INK,
                         anchor="middle", weight=700, family=T.FONT_HEAD))
    label = "Corazón real (tomografía) con el esquema del sistema de conducción en cinco pasos"
    if on_i is not None:
        label += f"; resaltado: paso {on_i + 1}"
    art = R.figure_html(name, join(body), label=label,
                        desc="Vista anterior; las vías son un esquema dibujado sobre la anatomía real, "
                             "no se ven en una tomografía.")
    details = ("<p>Corazón <em>real</em> reconstruido de una tomografía, de frente. El sistema de conducción "
               "no se ve en una tomografía: sus vías se dibujan encima, en el orden de activación:</p>"
               + _ol(CONDUCTION_TEXT, on_i))
    return art, details


# ═══════════════════════════════════════════════════════════════════════
# 7. El cuerpo completo (tomografía real)
# ═══════════════════════════════════════════════════════════════════════

_BODY_VOLUMES = (("heart", "Corazón"), ("lung_right", "Pulmón derecho"), ("lung_left", "Pulmón izquierdo"),
                 ("liver", "Hígado"), ("brain", "Encéfalo"), ("kidneys", "Riñones (ambos)"), ("spleen", "Bazo"))


def body() -> Tuple[str, str]:
    art = R.figure_html("atlas_body", "", cls="bc-render-tall")
    rows = []
    counts = ""
    try:
        from visualization.anatomy3d import body_counts, load_body

        anat = load_body()
        for key, label in _BODY_VOLUMES:
            if key in anat.meshes and anat[key].volume_ml:
                rows.append(f"<strong>{label}</strong>: {anat[key].volume_ml:,.0f} mL".replace(",", " "))
        n_surf, n_seg = body_counts()
        counts = f", con {n_seg} estructuras segmentadas que forman {n_surf} superficies 3D"
    except Exception:
        rows = []
    details = (
        "<p>Una persona <em>real</em>: tomografía de cuerpo completo anonimizada (sujeto s1397 del "
        f"TotalSegmentator dataset){counts}. Tenía "
        "los brazos levantados, como se pide en una tomografía de tórax y abdomen.</p>"
        + (("<p>Volúmenes medidos sobre sus segmentaciones:</p>" + _ul(rows)) if rows else "")
        + "<p>Puedes girarlo y explorarlo capa por capa en «Explorar en 3D».</p>"
    )
    return art, details
