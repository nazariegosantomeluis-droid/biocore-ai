"""Extrae los registros reales de referencia que usa la app (2026-10-21).

Lee registros de PhysioNet (formato WFDB; los mismos que trae como muestra
el repositorio de `wfdb-python`) y guarda tramos cortos y compactos en
`data/reference_signals/`. Todos tienen licencia Open Data Commons
Attribution v1.0 (ODC-By): se citan en `SOURCES` y en la interfaz.

Uso:
    python tools/build_reference_signals.py --raw CARPETA_CON_LOS_REGISTROS --out data/reference_signals

La carpeta debe contener: 100.hea/.dat/.atr (MIT-BIH), s0010_re.hea/.dat/.xyz
(PTB), n16.hea/.dat (CAP Sleep), a103l.hea/.mat (Challenge 2015) y
03700181.hea/.dat (MIMIC). Necesita `wfdb` (ya es dependencia de la app).
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Dict

import numpy as np

SOURCES: Dict[str, dict] = {
    "mitdb_100": {
        "title": "MIT-BIH Arrhythmia Database, registro 100",
        "detail": "Hombre de 69 años; derivaciones MLII y V5 a 360 Hz; anotaciones de latido revisadas por cardiólogos.",
        "citation": "Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. IEEE Eng Med Biol. "
                    "2001;20(3):45-50. PhysioNet doi:10.13026/C2F305.",
        "license": "ODC-By 1.0",
    },
    "ptb_s0010": {
        "title": "PTB Diagnostic ECG Database, registro s0010_re",
        "detail": "Mujer de 81 años con infarto agudo inferolateral; 12 derivaciones + derivaciones de Frank "
                  "(vx, vy, vz) a 1000 Hz.",
        "citation": "Bousseljot R, Kreiseler D, Schnabel A. Nutzung der EKG-Signaldatenbank CARDIODAT der PTB über "
                    "das Internet. Biomed Tech. 1995;40(S1):317. PhysioNet doi:10.13026/C28C71.",
        "license": "ODC-By 1.0",
    },
    "cap_n16": {
        "title": "CAP Sleep Database, registro n16 (control sano)",
        "detail": "EEG bipolar a 100 Hz; tramo de vigilia tranquila elegido por la mayor potencia alfa relativa "
                  "en P4-O2.",
        "citation": "Terzano MG, et al. Atlas, rules, and recording techniques for the scoring of cyclic "
                    "alternating pattern (CAP) in human sleep. Sleep Med. 2001;2(6):537-553.",
        "license": "ODC-By 1.0",
    },
    "challenge2015_a103l": {
        "title": "PhysioNet/CinC Challenge 2015, registro a103l",
        "detail": "Pletismografía (PPG) de oxímetro y ECG II a 250 Hz en UCI; tramo sin artefacto.",
        "citation": "Clifford GD, et al. The PhysioNet/Computing in Cardiology Challenge 2015: reducing false "
                    "arrhythmia alarms in the ICU. Comput Cardiol. 2015;42:273-276.",
        "license": "ODC-By 1.0",
    },
    "mimic_037": {
        "title": "MIMIC Database, registro 037 (segmento 03700181)",
        "detail": "Monitor de UCI: ECG MCL1, presión arterial invasiva (ABP) y respiración por impedancia, "
                  "registrados a la vez.",
        "citation": "Moody GB, Mark RG. A database to support development and evaluation of intelligent "
                    "intensive care monitoring. Comput Cardiol. 1996;23:657-660.",
        "license": "ODC-By 1.0",
    },
}


def _q(x: np.ndarray, step: float) -> np.ndarray:
    """Cuantiza a int16 con paso `step` (unidades físicas por cuenta)."""
    q = np.round(np.asarray(x, dtype=float) / step)
    if np.nanmax(np.abs(q)) >= 32767:
        raise ValueError("fuera de rango int16; aumenta el paso")
    return np.nan_to_num(q).astype(np.int16)


def _save(out_dir: str, key: str, arrays: dict, meta: dict) -> None:
    meta = dict(meta, **SOURCES[key])
    arrays["meta"] = np.frombuffer(json.dumps(meta, ensure_ascii=False).encode("utf-8"), dtype=np.uint8)
    path = os.path.join(out_dir, f"{key}.npz")
    np.savez_compressed(path, **arrays)
    print(f"- {key}: {os.path.getsize(path) / 1024:.0f} KB")


def build(raw: str, out_dir: str) -> None:
    import wfdb
    from scipy.signal import resample_poly, welch

    os.makedirs(out_dir, exist_ok=True)

    # MIT-BIH 100: 5 min de MLII (360 Hz) + anotaciones de todo el registro.
    rec = wfdb.rdrecord(os.path.join(raw, "100"), sampto=360 * 300)
    ann = wfdb.rdann(os.path.join(raw, "100"), "atr")
    mlii = rec.p_signal[:, rec.sig_name.index("MLII")]
    beats = np.array([s for s, sym in zip(ann.sample, ann.symbol) if sym in "NLRBAaJSVrFejnE/fQ?"])
    syms = "".join(sym for sym in ann.symbol if sym in "NLRBAaJSVrFejnE/fQ?")
    _save(out_dir, "mitdb_100", {
        "mlii": _q(mlii, 0.005), "beat_sample": beats.astype(np.int32),
        "beat_symbol": np.frombuffer(syms.encode("ascii"), dtype=np.uint8),
    }, {"fs": 360.0, "units": "mV", "step": 0.005, "segment_s": [0, 300],
        "beats_note": "Anotaciones de latido de todo el registro (30 min); N = normal."})

    # PTB s0010_re: 20 s, 12 derivaciones + Frank, remuestreado a 500 Hz.
    rec = wfdb.rdrecord(os.path.join(raw, "s0010_re"), sampto=1000 * 20)
    names = [n.upper() for n in rec.sig_name]
    sig = resample_poly(rec.p_signal, 1, 2, axis=0)
    _save(out_dir, "ptb_s0010", {"signals": _q(sig, 0.001)},
          {"fs": 500.0, "units": "mV", "step": 0.001, "leads": names, "segment_s": [0, 20],
           "resampled_from_hz": 1000.0})

    # CAP n16: 30 s de las 5 derivaciones en el tramo de mayor alfa relativa (primeros 40 min).
    rec = wfdb.rdrecord(os.path.join(raw, "n16"), sampto=100 * 60 * 40)
    x = rec.p_signal
    fs = float(rec.fs)
    idx = rec.sig_name.index("P4-O2")
    best = None
    for w0 in range(0, x.shape[0] - int(30 * fs), int(10 * fs)):
        seg = x[w0:w0 + int(30 * fs), idx]
        f, p = welch(seg - seg.mean(), fs, nperseg=256)
        rel = p[(f >= 8) & (f < 13)].sum() / p[(f >= 1) & (f < 30)].sum()
        if np.ptp(seg) < 200 and (best is None or rel > best[0]):
            best = (rel, w0)
    w0 = best[1]
    _save(out_dir, "cap_n16", {"signals": _q(x[w0:w0 + int(30 * fs)], 0.05)},
          {"fs": fs, "units": "uV", "step": 0.05, "leads": list(rec.sig_name),
           "segment_s": [w0 / fs, w0 / fs + 30], "alpha_relative_p4o2": round(float(best[0]), 3)})

    # Challenge 2015 a103l: 30 s sin artefacto (13-43 s) de PPG y ECG II.
    rec = wfdb.rdrecord(os.path.join(raw, "a103l"), sampfrom=250 * 13, sampto=250 * 43)
    _save(out_dir, "challenge2015_a103l", {
        "pleth": _q(rec.p_signal[:, rec.sig_name.index("PLETH")], 1e-4),
        "ii": _q(rec.p_signal[:, rec.sig_name.index("II")], 0.002),
    }, {"fs": float(rec.fs), "units": {"pleth": "NU", "ii": "mV"}, "step": {"pleth": 1e-4, "ii": 0.002},
        "segment_s": [13, 43]})

    # MIMIC 037: 120 s; ECG MCL1 a 500 Hz y ABP/RESP a 125 Hz (frecuencias originales).
    rec = wfdb.rdrecord(os.path.join(raw, "03700181"), sampto=125 * 120, smooth_frames=False)
    sig = {n: np.asarray(s) for n, s in zip(rec.sig_name, rec.e_p_signal)}
    _save(out_dir, "mimic_037", {
        "mcl1": _q(sig["MCL1"], 0.002), "abp": _q(sig["ABP"], 0.1), "resp": _q(sig["RESP"], 0.001),
    }, {"fs": {"mcl1": 500.0, "abp": 125.0, "resp": 125.0}, "units": {"mcl1": "mV", "abp": "mmHg", "resp": "u.a."},
        "step": {"mcl1": 0.002, "abp": 0.1, "resp": 0.001}, "segment_s": [0, 120]})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    build(args.raw, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
