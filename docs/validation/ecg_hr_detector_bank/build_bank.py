"""Banco de validacion del detector de HR de ECG (Capa 5B mini-arco, 2026-08-24).
Lee SOLO datos reales de PhysioNet (MIT-BIH) via wfdb, y llama a
clinical.ecg_analyzer.ECGAnalyzer.detect_r_peaks() en modo de solo lectura --
no modifica ningun codigo de produccion. Produce:
  - tabla comparativa (xlsx)
  - tiras de ECG con picos marcados (PDF)
  - hoja de decision para el experto (PDF)
"""
import sys
import os
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, REPO_ROOT)

import numpy as np
import wfdb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from clinical.ecg_analyzer import ECGAnalyzer

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

RECORDS = {
    '100': 'Base limpia #1 (ritmo sinusal normal, referencia clasica)',
    '103': 'Base limpia #2 (ritmo sinusal normal, morfologia QRS distinta)',
    '117': 'Trampa onda T prominente (T/R=0.79, ritmo por lo demas limpio)',
    '108': 'Bajo voltaje QRS + PACs (qrs pico-a-pico minimo del cribado)',
    '228': 'Arritmia real (PVCs frecuentes, rr_cv=0.385)',
    '207': 'Caso extremo: fibrilacion/flutter ventricular + ruido (rr_cv=0.639, el mas severo)',
    '233': 'Ruido/artefacto (noise_std mas alto del cribado, PVCs)',
    '118': 'Bloqueo de rama derecha -- BRD (morfologia QRS alterada, no arritmia de ritmo)',
}

PROMINENCE_FACTORS = [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
ANALYSIS_DURATION_S = 180  # 3 minutos por registro para las metricas cuantitativas
STRIP_DURATION_S = 8       # tiras visuales cortas y legibles
TOLERANCE_S = 0.05         # +-50ms para emparejar picos detectados con anotaciones

_cache = {}


def load_record(rec_id, duration_s):
    key = (rec_id, duration_s)
    if key in _cache:
        return _cache[key]
    record = wfdb.rdrecord(rec_id, pn_dir='mitdb', sampto=int(duration_s * 360))
    ann = wfdb.rdann(rec_id, 'atr', pn_dir='mitdb', sampto=int(duration_s * 360))
    fs = record.fs
    sig = record.p_signal[:, 0]
    sig_name = record.sig_name[0]
    symbols = np.array(ann.symbol)
    samples = np.array(ann.sample)
    beat_mask = symbols != '+'  # '+' es marcador de cambio de ritmo, no un latido
    gt_samples = samples[beat_mask]
    gt_symbols = symbols[beat_mask]
    result = (sig, fs, sig_name, gt_samples, gt_symbols)
    _cache[key] = result
    return result


def match_peaks(detected, ground_truth, fs, tolerance_s=TOLERANCE_S):
    """Empareja picos detectados con anotaciones de ground truth (barrido de dos
    punteros sobre arrays ordenados, emparejamiento 1:1 mas cercano dentro de
    la tolerancia). Devuelve (tp, fp, fn, matched_gt_idx, matched_det_idx)."""
    tol = tolerance_s * fs
    detected = np.sort(detected)
    ground_truth = np.sort(ground_truth)
    used_gt = np.zeros(len(ground_truth), dtype=bool)
    used_det = np.zeros(len(detected), dtype=bool)

    for gi, g in enumerate(ground_truth):
        # candidato detectado mas cercano no usado, dentro de tolerancia
        if len(detected) == 0:
            break
        idx = np.searchsorted(detected, g)
        candidates = []
        if idx < len(detected):
            candidates.append(idx)
        if idx > 0:
            candidates.append(idx - 1)
        best = None
        best_dist = None
        for c in candidates:
            if used_det[c]:
                continue
            dist = abs(detected[c] - g)
            if dist <= tol and (best_dist is None or dist < best_dist):
                best = c
                best_dist = dist
        if best is not None:
            used_gt[gi] = True
            used_det[best] = True

    tp = int(np.sum(used_gt))
    fn = int(len(ground_truth) - tp)
    fp = int(len(detected) - int(np.sum(used_det)))
    return tp, fp, fn


def analyze():
    rows = []
    for rec_id, label in RECORDS.items():
        sig, fs, sig_name, gt_samples, gt_symbols = load_record(rec_id, ANALYSIS_DURATION_S)
        n_gt = len(gt_samples)
        gt_rr = np.diff(gt_samples) / fs
        hr_gt = 60.0 / np.mean(gt_rr) if len(gt_rr) > 0 else 0.0
        analyzer = ECGAnalyzer(fs=fs)
        for pf in PROMINENCE_FACTORS:
            peaks = analyzer.detect_r_peaks(sig, prominence_factor=pf)
            hr_det = analyzer.estimate_heart_rate(peaks) if len(peaks) > 1 else 0.0
            interval_std = float(np.std(np.diff(peaks)) / fs * 1000.0) if len(peaks) > 2 else float('nan')
            tp, fp, fn = match_peaks(peaks, gt_samples, fs)
            sensitivity = tp / n_gt if n_gt > 0 else float('nan')
            ppv = tp / (tp + fp) if (tp + fp) > 0 else float('nan')
            hr_error = hr_det - hr_gt
            rows.append({
                'record': rec_id, 'label': label, 'prominence_factor': pf,
                'n_gt_beats': n_gt, 'n_detected': len(peaks),
                'hr_ground_truth': round(hr_gt, 1), 'hr_detected': round(hr_det, 1),
                'hr_error_bpm': round(hr_error, 1),
                'interval_std_ms': round(interval_std, 1) if not np.isnan(interval_std) else None,
                'tp': tp, 'fp': fp, 'fn': fn,
                'sensitivity': round(sensitivity, 3) if not np.isnan(sensitivity) else None,
                'ppv': round(ppv, 3) if not np.isnan(ppv) else None,
            })
        print(f"{rec_id} listo -- {n_gt} latidos GT, HR_gt={hr_gt:.1f}")
    return rows


if __name__ == '__main__':
    rows = analyze()
    import json
    with open(os.path.join(OUT_DIR, 'raw_results.json'), 'w') as f:
        json.dump(rows, f, indent=2)
    print(f"\nGuardado {len(rows)} filas en raw_results.json")
