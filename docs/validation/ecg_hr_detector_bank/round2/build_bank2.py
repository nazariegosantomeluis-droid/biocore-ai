"""Banco de validacion, 2a ronda (Capa 2/5B, 2026-08-24). Detector reparado
(bidireccional + refractario, Solucion 1) contra ground truth de MIT-BIH.
Solo lectura sobre clinical.ecg_analyzer -- se llama, no se modifica aqui."""
import sys, os
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import numpy as np
import wfdb
from clinical.ecg_analyzer import ECGAnalyzer, ClinicalDataQualityError, QUALITY_THRESHOLD

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# (record_id, lead_index, etiqueta)
RECORDS = [
    ('100', 0, 'Base limpia #1 (ritmo sinusal normal, MLII)'),
    ('103', 0, 'Base limpia #2 (ritmo sinusal normal, MLII)'),
    ('117', 0, 'QRS predominante negativo (MLII) -- ronda 1: sens ya era 1.0, VPP 0.51'),
    ('108', 0, 'Bajo voltaje + PACs (MLII) -- ronda 1: sens catastrofica 0.16-0.18'),
    ('228', 0, 'Arritmia real (PVCs, MLII)'),
    ('207', 0, 'Extremo: fibrilacion/flutter ventricular + ruido (MLII)'),
    ('233', 0, 'Ruido/artefacto (MLII) -- la prueba del espejismo de HR promedio'),
    ('118', 0, 'Bloqueo de rama derecha (MLII)'),
    ('210', 0, 'Fibrilacion auricular SOSTENIDA (98% de la duracion bajo (AFIB), MLII) -- anadido tras 1a revision'),
    ('217', 0, 'Ritmo con marcapasos (mayoria de latidos simbolo "/", MLII) -- anadido tras 1a revision'),
    ('100', 1, 'Registro 100, derivacion V5 (misma senal, otra derivacion) -- anadido tras 1a revision'),
]

PROMINENCE_FACTORS = [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
ANALYSIS_DURATION_S = 180
STRIP_DURATION_S = 8
TOLERANCE_S = 0.05

_cache = {}


def load_record(rec_id, lead_index, duration_s):
    key = (rec_id, lead_index, duration_s)
    if key in _cache:
        return _cache[key]
    record = wfdb.rdrecord(rec_id, pn_dir='mitdb', sampto=int(duration_s * 360))
    ann = wfdb.rdann(rec_id, 'atr', pn_dir='mitdb', sampto=int(duration_s * 360))
    fs = record.fs
    sig = record.p_signal[:, lead_index]
    sig_name = record.sig_name[lead_index]
    symbols = np.array(ann.symbol)
    samples = np.array(ann.sample)
    beat_mask = symbols != '+'
    gt_samples = samples[beat_mask]
    result = (sig, fs, sig_name, gt_samples)
    _cache[key] = result
    return result


def match_peaks(detected, ground_truth, fs, tolerance_s=TOLERANCE_S):
    tol = tolerance_s * fs
    detected = np.sort(detected)
    ground_truth = np.sort(ground_truth)
    used_det = np.zeros(len(detected), dtype=bool)
    tp = 0
    for g in ground_truth:
        if len(detected) == 0:
            break
        idx = np.searchsorted(detected, g)
        cands = [c for c in (idx - 1, idx) if 0 <= c < len(detected) and not used_det[c]]
        best, best_d = None, None
        for c in cands:
            d = abs(detected[c] - g)
            if d <= tol and (best_d is None or d < best_d):
                best, best_d = c, d
        if best is not None:
            used_det[best] = True
            tp += 1
    fn = len(ground_truth) - tp
    fp = len(detected) - int(np.sum(used_det))
    return tp, fp, fn


def analyze():
    rows = []
    for rec_id, lead_idx, label in RECORDS:
        sig, fs, sig_name, gt_samples = load_record(rec_id, lead_idx, ANALYSIS_DURATION_S)
        n_gt = len(gt_samples)
        gt_rr = np.diff(gt_samples) / fs
        hr_gt = 60.0 / np.mean(gt_rr) if len(gt_rr) > 0 else 0.0
        analyzer = ECGAnalyzer(fs=fs)

        rec_key = f"{rec_id}-{sig_name}"
        for pf in PROMINENCE_FACTORS:
            peaks_old = analyzer.detect_r_peaks(sig, prominence_factor=pf)
            tp_o, fp_o, fn_o = match_peaks(peaks_old, gt_samples, fs)
            sens_old = tp_o / n_gt if n_gt else float('nan')
            ppv_old = tp_o / (tp_o + fp_o) if (tp_o + fp_o) else float('nan')
            hr_old = analyzer.estimate_heart_rate(peaks_old) if len(peaks_old) > 1 else 0.0

            peaks_new, competitions = analyzer.detect_r_peaks_bidirectional(sig, prominence_factor=pf)
            tp_n, fp_n, fn_n = match_peaks(peaks_new, gt_samples, fs)
            sens_new = tp_n / n_gt if n_gt else float('nan')
            ppv_new = tp_n / (tp_n + fp_n) if (tp_n + fp_n) else float('nan')
            hr_new = analyzer.estimate_heart_rate(peaks_new) if len(peaks_new) > 1 else 0.0

            try:
                hr_gated, confidence = analyzer.estimate_heart_rate_with_confidence(sig, prominence_factor=pf)
                gate_decision = 'ACEPTA'
                gate_reason = ''
            except ClinicalDataQualityError as e:
                hr_gated, confidence = None, None
                gate_decision = 'RECHAZA'
                gate_reason = str(e)

            rows.append({
                'record': rec_key, 'record_id': rec_id, 'lead': sig_name, 'label': label,
                'prominence_factor': pf, 'n_gt_beats': n_gt,
                'hr_ground_truth': round(hr_gt, 1),
                'sens_old': round(sens_old, 3) if not np.isnan(sens_old) else None,
                'ppv_old': round(ppv_old, 3) if not np.isnan(ppv_old) else None,
                'hr_old': round(hr_old, 1), 'hr_error_old': round(hr_old - hr_gt, 1),
                'sens_new': round(sens_new, 3) if not np.isnan(sens_new) else None,
                'ppv_new': round(ppv_new, 3) if not np.isnan(ppv_new) else None,
                'hr_new': round(hr_new, 1), 'hr_error_new': round(hr_new - hr_gt, 1),
                'n_competitions': len(competitions),
                'confidence': round(confidence, 3) if confidence is not None else None,
                'gate_decision': gate_decision, 'gate_reason': gate_reason,
            })
        print(f"{rec_key} listo -- {n_gt} latidos GT, HR_gt={hr_gt:.1f}")
    return rows


if __name__ == '__main__':
    rows = analyze()
    import json
    with open(os.path.join(OUT_DIR, 'raw_results2.json'), 'w') as f:
        json.dump(rows, f, indent=2)
    print(f"\nGuardado {len(rows)} filas en raw_results2.json")
