"""La "tira de monitor" de cada encabezado de módulo (2026-10-19).

Cada módulo abre con SU señal -- ECG, EEG, respiración, EMG, tacograma --
sobre la retícula milimétrica del papel de registro, como la tira que
imprime un monitor de cabecera. Es la identidad visual de la app: el
elemento memorable; todo lo demás se mantiene sobrio.

Escalas reales donde aplica (retícula: 1 mm = 6 px de viewBox):
    ECG  25 mm/s,  5 mm/mV (ganancia N/2, estándar para trazos altos)
    EEG  30 mm/s
    Resp  5 mm/s

Desde el 2026-10-21 casi todas son REGISTROS REALES de PhysioNet
(`src/signals/reference_recordings.py`): ECG de la MIT-BIH, EEG de la CAP
Sleep Database, pulso del Challenge 2015 y el monitor de UCI de la base
MIMIC. Lo dicen en el `<title>` y en un rótulo visible. Quedan como esquema
ilustrativo la EMG (no hay EMG abierta en el paquete), el gemelo (es una
simulación por definición) y la línea de tiempo del pipeline.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

import numpy as np

from visualization.art import tokens as T
from visualization.art import waves
from visualization.art.svg import join, map_signal, mm_grid, path_from_xy, svg_root, text, trace

# kind -> (clave del registro, rótulo corto visible)
REAL_SOURCES: Dict[str, tuple] = {
    "ecg": ("mitdb_100", "Registro real: MIT-BIH 100, MLII"),
    "academia": ("mitdb_100", "Registro real: MIT-BIH 100, MLII"),
    "calculators": ("mitdb_100", "Registro real: MIT-BIH 100, MLII"),
    "eeg": ("cap_n16", "Registro real: CAP Sleep n16, P4-O2"),
    "respiratory": ("mimic_037", "Registro real: MIMIC 037, impedancia torácica"),
    "hrv": ("mitdb_100", "Registro real: RR de MIT-BIH 100"),
    "biomarkers": ("challenge2015_a103l", "Registro real: PPG de oxímetro, Challenge 2015"),
    "multisensor": ("mimic_037", "Registro real: MIMIC 037, ECG, presión arterial y respiración"),
}

W, H = 2400.0, 64.0   # alto = alto CSS de .bc-strip: nunca se recorta en vertical
MM = 6.0                 # px de viewBox por milímetro
PX_PER_S_ECG = 25 * MM   # 25 mm/s
PX_PER_S_EEG = 30 * MM   # 30 mm/s
PX_PER_S_RESP = 5 * MM   # 5 mm/s


def _draw(d: str, *, color: str = T.TRACE, width: float = 2.0, opacity: float = 1.0) -> str:
    # pathLength="1": la animación de "trazado" (CSS .bc-draw en
    # inject_global_theme) no necesita conocer la longitud real del trazo.
    return trace(d, color=color, width=width, opacity=opacity,
                 extra='pathLength="1" class="bc-draw"')


def _ecg_path(y_mid: float, mv_px: float, hr: float = 72.0, x0: float = 0.0) -> str:
    duration = W / PX_PER_S_ECG
    t = np.linspace(0, duration, 3200)
    v = waves.ecg(t, waves.regular_r_times(duration, hr, first_s=0.42))
    xs, ys = map_signal(t, v, x0=x0, width=W, y_mid=y_mid, px_per_unit=mv_px, t_start=0, t_end=duration)
    return path_from_xy(xs, ys)


def _real_ecg(start_s: float = 2.0) -> tuple:
    """(t, mV relativo a la línea de base) de MLII para llenar la tira a 25 mm/s."""
    from src.signals.reference_recordings import mitdb_100

    d = mitdb_100()
    fs = d["fs"]
    dur = W / PX_PER_S_ECG
    a, b = int(start_s * fs), int((start_s + dur) * fs)
    v = d["mlii"][a:b]
    return np.arange(v.size) / fs, v - np.median(v), d, a


def _strip_ecg() -> str:
    t, v, _, _ = _real_ecg()
    xs, ys = map_signal(t, v, x0=0, width=W, y_mid=44, px_per_unit=5 * MM, t_start=0, t_end=W / PX_PER_S_ECG)
    return _draw(path_from_xy(xs, ys))


def _beat_in_strip(d: dict, a: int, n: int) -> int:
    """Muestra (relativa al inicio de la tira) de la n-ésima R normal."""
    fs = d["fs"]
    rs = [int(b) - a for b, sym in zip(d["beats"], d["symbols"]) if sym == "N" and b >= a + 0.4 * fs]
    return rs[n]


def _strip_academia() -> str:
    # ECG real con las ondas rotuladas en un latido (posiciones medidas sobre
    # el latido mediano del mismo registro).
    from src.signals.ecg.beat_delineation import reference_beat

    mid, gain = 50.0, 4 * MM
    t, v, d, a = _real_ecg()
    xs, ys = map_signal(t, v, x0=0, width=W, y_mid=mid, px_per_unit=gain, t_start=0, t_end=W / PX_PER_S_ECG)
    body = [_draw(path_from_xy(xs, ys))]
    _, dl = reference_beat()
    r = _beat_in_strip(d, a, 2) / d["fs"]
    for label, t_ms, amp in (("P", dl.p_peak, dl.p_amp_mv), ("QRS", dl.r, dl.r_amp_mv), ("T", dl.t_peak, dl.t_amp_mv)):
        x = (r + t_ms / 1000.0) * PX_PER_S_ECG
        y = mid - amp * gain - 7
        body.append(text(x, max(y, 13), label, size=12, fill=T.INK, anchor="middle", weight=700, halo=T.STRIP_BG))
    return join(body)


def _strip_calipers() -> str:
    # ECG real con el compás midiendo QT (medido) y RR (entre dos R anotadas).
    from src.signals.ecg.beat_delineation import reference_beat

    mid, gain = 40.0, 4 * MM
    t, v, d, a = _real_ecg()
    xs, ys = map_signal(t, v, x0=0, width=W, y_mid=mid, px_per_unit=gain, t_start=0, t_end=W / PX_PER_S_ECG)
    body = [_draw(path_from_xy(xs, ys))]
    _, dl = reference_beat()
    fs = d["fs"]
    r3 = _beat_in_strip(d, a, 3) / fs
    q_on = (r3 + dl.qrs_on / 1000.0) * PX_PER_S_ECG
    t_off = (r3 + dl.t_off / 1000.0) * PX_PER_S_ECG
    r5, r6 = _beat_in_strip(d, a, 5) / fs, _beat_in_strip(d, a, 6) / fs
    x5, x6 = r5 * PX_PER_S_ECG, r6 * PX_PER_S_ECG
    ink = T.INK_2
    for x in (q_on, t_off):
        body.append(f'<path d="M{x:.1f} 12V52" stroke="{ink}" stroke-width="1.2" stroke-opacity="0.8"/>')
    body.append(f'<path d="M{q_on:.1f} 52H{t_off:.1f}" stroke="{ink}" stroke-width="1.4"/>')
    body.append(text((q_on + t_off) / 2, 62, f"QT {dl.qt_ms:.0f} ms", size=11, fill=ink, anchor="middle", weight=700))
    for x in (x5, x6):
        body.append(f'<path d="M{x:.1f} 50V58" stroke="{ink}" stroke-width="1.2"/>')
    body.append(f'<path d="M{x5:.1f} 54H{x6:.1f}" stroke="{ink}" stroke-width="1.4"/>')
    body.append(text((x5 + x6) / 2, 62.5, f"RR {(r6 - r5) * 1000:.0f} ms", size=11, fill=ink, anchor="middle",
                     weight=700))
    return join(body)


def _strip_eeg() -> str:
    from src.signals.reference_recordings import cap_n16

    d = cap_n16()
    fs = d["fs"]
    dur = W / PX_PER_S_EEG
    x = d["leads"]["P4-O2"][int(2 * fs):int((2 + dur) * fs)]
    x = x - np.mean(x)
    t = np.arange(x.size) / fs
    scale = 22.0 / (np.percentile(np.abs(x), 99.5) or 1.0)
    xs, ys = map_signal(t, x, x0=0, width=W, y_mid=32, px_per_unit=scale, t_start=0, t_end=dur)
    return _draw(path_from_xy(xs, ys), width=1.5)


def _strip_resp() -> str:
    from src.signals.reference_recordings import mimic_037

    d = mimic_037()
    fs = d["fs"]["resp"]
    dur = W / PX_PER_S_RESP
    x = d["resp"][:int(dur * fs)]
    x = x - np.median(x)
    t = np.arange(x.size) / fs
    scale = 20.0 / (np.percentile(np.abs(x), 99) or 1.0)
    xs, ys = map_signal(t, x, x0=0, width=W, y_mid=32, px_per_unit=scale, t_start=0, t_end=dur)
    return _draw(path_from_xy(xs, ys), width=2.2)


def _strip_emg() -> str:
    duration = W / PX_PER_S_ECG
    t = np.linspace(0, duration, 5200)
    v = waves.emg_bursts(t, burst_times=(1.4, 4.0, 6.6, 9.4, 12.2, 14.8))
    v = np.clip(v, -2.6, 2.6)
    xs, ys = map_signal(t, v, x0=0, width=W, y_mid=32, px_per_unit=10, t_start=0, t_end=duration)
    return _draw(path_from_xy(xs, ys), width=1.1)


def _strip_hrv() -> str:
    from src.signals.reference_recordings import normal_rr_ms

    n = 96
    rr = normal_rr_ms(max_beats=n)
    n = rr.size
    xs = np.linspace(14, W - 14, n)
    lo, hi = rr.min(), rr.max()
    ys = 54 - (rr - lo) / ((hi - lo) or 1.0) * 42
    body = [_draw(path_from_xy(xs, ys, tol=0), width=1.6, opacity=0.85)]
    body.extend(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{T.TRACE}" stroke="{T.STRIP_BG}" stroke-width="2"/>'
        for x, y in zip(xs, ys)
    )
    return join(body)


def _strip_ppg() -> str:
    from src.signals.reference_recordings import ppg_a103l

    d = ppg_a103l()
    fs = d["fs"]
    dur = W / PX_PER_S_ECG
    x = d["pleth"][:int(dur * fs)]
    x = x - np.median(x)
    t = np.arange(x.size) / fs
    scale = 22.0 / (np.percentile(np.abs(x), 99.5) or 1.0)
    xs, ys = map_signal(t, x, x0=0, width=W, y_mid=36, px_per_unit=scale, t_start=0, t_end=dur)
    return _draw(path_from_xy(xs, ys), width=2.0)


def _strip_multi() -> str:
    # Tres carriles de un mismo paciente de UCI, registrados a la vez.
    from src.signals.reference_recordings import mimic_037

    d = mimic_037()
    dur = W / PX_PER_S_ECG
    body = []
    for key, y_mid, half, op, sign in (("mcl1", 17, 11, 1.0, 1.0), ("abp", 38, 9, 0.85, 1.0),
                                        ("resp", 55, 6, 0.65, 1.0)):
        fs = d["fs"][key]
        x = d[key][:int(dur * fs)]
        x = x - np.median(x)
        t = np.arange(x.size) / fs
        scale = half / (np.percentile(np.abs(x), 99.5) or 1.0)
        xs, ys = map_signal(t, sign * x, x0=0, width=W, y_mid=y_mid, px_per_unit=scale, t_start=0, t_end=dur)
        body.append(_draw(path_from_xy(xs, ys), width=1.5, opacity=op))
    return join(body)


def _strip_twin() -> str:
    duration = W / PX_PER_S_ECG
    t = np.linspace(0, duration, 3200)
    ecg_v = waves.ecg(t, waves.regular_r_times(duration, 72, first_s=0.42))
    resp_v = waves.breathing(t, rate_rpm=15) - 0.5
    xs, ys = map_signal(t, ecg_v, x0=0, width=W, y_mid=34, px_per_unit=22, t_start=0, t_end=duration)
    xr, yr = map_signal(t, resp_v, x0=0, width=W, y_mid=54, px_per_unit=12, t_start=0, t_end=duration)
    return join([_draw(path_from_xy(xr, yr), width=1.6, opacity=0.55), _draw(path_from_xy(xs, ys))])


def _strip_pipeline() -> str:
    # Estados del paciente guardados en el tiempo: nodos sobre una tendencia.
    xs = np.arange(60.0, W, 120.0)
    k = np.arange(xs.size)
    ys = 32 - 11 * np.sin(k / 1.7) - 4 * np.cos(k / 0.9)
    t_dense = np.linspace(xs[0], xs[-1], 400)
    y_dense = np.interp(t_dense, xs, ys)
    body = [f'<path d="M0 56H{W:.0f}" stroke="{T.INK_3}" stroke-opacity="0.45" stroke-width="1"/>',
            _draw(path_from_xy(t_dense, y_dense), width=1.6, opacity=0.8)]
    for x, y in zip(xs, ys):
        body.append(f'<path d="M{x:.1f} {y + 6:.1f}V56" stroke="{T.INK_3}" stroke-opacity="0.5" stroke-width="1"/>')
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{T.STRIP_BG}" stroke="{T.TRACE}" stroke-width="2"/>')
    return join(body)


STRIP_KINDS: Dict[str, tuple] = {
    # kind: (función, descripción para lectores de pantalla)
    "ecg": (_strip_ecg, "ECG en ritmo sinusal, derivación MLII"),
    "academia": (_strip_academia, "ECG con las ondas P, QRS y T rotuladas"),
    "calculators": (_strip_calipers, "ECG con el compás midiendo QT y RR"),
    "eeg": (_strip_eeg, "EEG de vigilia relajada con ritmo alfa posterior"),
    "respiratory": (_strip_resp, "curva de respiración por impedancia torácica"),
    "emg": (_strip_emg, "EMG de superficie con tres contracciones"),
    "hrv": (_strip_hrv, "tacograma: un punto por cada intervalo RR"),
    "biomarkers": (_strip_ppg, "onda de pulso del oxímetro"),
    "multisensor": (_strip_multi, "tres carriles de monitor de UCI: ECG, presión arterial y respiración"),
    "twin": (_strip_twin, "ECG y respiración del gemelo digital"),
    "pipeline": (_strip_pipeline, "línea de tiempo de estados guardados del paciente"),
}


@lru_cache(maxsize=None)
def signal_strip_svg(kind: str) -> str:
    """SVG de la tira de monitor para `kind` (ver `STRIP_KINDS`); "" si no existe.
    Determinista, así que se calcula una vez por proceso (`lru_cache`)."""
    entry = STRIP_KINDS.get(kind)
    if entry is None:
        return ""
    fn, desc = entry
    real = REAL_SOURCES.get(kind)
    parts = [
        f'<rect width="{W:.0f}" height="{H:.0f}" fill="{T.STRIP_BG}"/>',
        mm_grid(0, 0, W, H, MM, key="strip"),
        fn(),
    ]
    if real:
        from src.signals.reference_recordings import load

        rec = load(real[0])
        parts.append(text(8, 11, real[1], size=9, fill=T.INK_3, halo=T.STRIP_BG))
        label = f"Registro real: {desc} ({rec.title})"
        long_desc = (f"Tramo de un registro real de otra persona, no del paciente: {rec.citation} "
                     f"Licencia {rec.license}.")
    else:
        label = f"Esquema ilustrativo: {desc}"
        long_desc = "Dibujo generado por código para identificar el módulo; no es un registro del paciente."
    return svg_root(W, H, join(parts), label=label, desc=long_desc, preserve="xMinYMid slice")
