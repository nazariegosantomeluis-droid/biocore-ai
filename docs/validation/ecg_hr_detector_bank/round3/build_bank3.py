"""Banco de validacion, 3a ronda (Capa 2/5B, 2026-08-24). Desempate refractario
por pendiente (Parte A) + intento de bandera de marcapasos (Parte B, resultado
negativo documentado) + verificacion de Parte C. Solo lectura sobre
clinical.ecg_analyzer -- se llama, no se modifica aqui."""
import sys, os
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import numpy as np
import wfdb
from clinical.ecg_analyzer import ECGAnalyzer, ClinicalDataQualityError

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

RECORDS = [
    ('100', 0, 'Base limpia #1'),
    ('103', 0, 'Base limpia #2'),
    ('117', 0, 'QRS predominante negativo'),
    ('108', 0, 'Bajo voltaje + PACs'),
    ('228', 0, 'Arritmia real (PVCs)'),
    ('207', 0, 'Extremo: fibrilacion/flutter ventricular + ruido'),
    ('233', 0, 'Ruido/artefacto -- prueba del espejismo de HR promedio'),
    ('118', 0, 'Bloqueo de rama derecha -- EN ALCANCE (nodo sinusal = metronomo)'),
    ('210', 0, 'Fibrilacion auricular sostenida (98% de la duracion)'),
    ('217', 0, 'Marcapasos -- FUERA DE ALCANCE (maquina = metronomo, no el SNA)'),
    ('100', 1, 'Registro 100, derivacion V5'),
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
    gt_samples = samples[symbols != '+']
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

        is_paced, n_spikes = analyzer.detect_pacemaker_spikes(sig)

        for pf in PROMINENCE_FACTORS:
            # Round 2: desempate por amplitud (reconstruido localmente para comparar -- no existe ya en produccion)
            peaks_amp = _bidir_amplitude_tiebreak(analyzer, sig, pf)
            tp_a, fp_a, fn_a = match_peaks(peaks_amp, gt_samples, fs)
            sens_amp = tp_a / n_gt if n_gt else float('nan')
            ppv_amp = tp_a / (tp_a + fp_a) if (tp_a + fp_a) else float('nan')

            # Round 3: desempate por pendiente (produccion actual)
            peaks_slope, competitions = analyzer.detect_r_peaks_bidirectional(sig, prominence_factor=pf)
            tp_s, fp_s, fn_s = match_peaks(peaks_slope, gt_samples, fs)
            sens_slope = tp_s / n_gt if n_gt else float('nan')
            ppv_slope = tp_s / (tp_s + fp_s) if (tp_s + fp_s) else float('nan')
            hr_slope = analyzer.estimate_heart_rate(peaks_slope) if len(peaks_slope) > 1 else 0.0

            try:
                hr_gated, confidence = analyzer.estimate_heart_rate_with_confidence(sig, prominence_factor=pf)
                gate_decision = 'ACEPTA'
            except ClinicalDataQualityError:
                confidence = None
                gate_decision = 'RECHAZA'

            rows.append({
                'record': rec_key, 'record_id': rec_id, 'label': label,
                'prominence_factor': pf, 'n_gt_beats': n_gt, 'hr_ground_truth': round(hr_gt, 1),
                'sens_amplitud_r2': round(sens_amp, 3) if not np.isnan(sens_amp) else None,
                'ppv_amplitud_r2': round(ppv_amp, 3) if not np.isnan(ppv_amp) else None,
                'sens_pendiente_r3': round(sens_slope, 3) if not np.isnan(sens_slope) else None,
                'ppv_pendiente_r3': round(ppv_slope, 3) if not np.isnan(ppv_slope) else None,
                'hr_error_r3': round(hr_slope - hr_gt, 1),
                'n_competitions': len(competitions),
                'confidence': round(confidence, 3) if confidence is not None else None,
                'gate_decision': gate_decision,
                'is_paced_flag': is_paced, 'n_spikes': n_spikes,
            })
        print(f"{rec_key} listo -- {n_gt} latidos GT, HR_gt={hr_gt:.1f}, pacing_flag={is_paced}(n={n_spikes})")
    return rows


def _bidir_amplitude_tiebreak(analyzer, signal, prominence_factor):
    """Reconstruccion LOCAL del desempate por amplitud de la ronda 2 (ya no
    existe en produccion, reemplazado por pendiente) -- solo para poder
    graficar la comparacion antes/despues en esta ronda."""
    from scipy.signal import find_peaks
    fs = analyzer.fs
    threshold_pos = np.mean(signal) + prominence_factor * np.std(signal)
    pos_peaks, _ = find_peaks(signal, distance=int(0.3 * fs), height=threshold_pos)
    inverted = -signal
    threshold_neg = np.mean(inverted) + prominence_factor * np.std(inverted)
    neg_peaks, _ = find_peaks(inverted, distance=int(0.3 * fs), height=threshold_neg)
    combined = np.concatenate([pos_peaks, neg_peaks])
    if len(combined) == 0:
        return np.array([], dtype=int)
    combined = np.sort(combined)
    refractory_samples = int(200.0 / 1000.0 * fs)
    kept = []
    i = 0
    n = len(combined)
    while i < n:
        cluster = [combined[i]]
        j = i + 1
        while j < n and combined[j] - cluster[-1] < refractory_samples:
            cluster.append(combined[j])
            j += 1
        if len(cluster) == 1:
            kept.append(int(cluster[0]))
        else:
            amps = [abs(float(signal[s])) for s in cluster]
            winner = cluster[int(np.argmax(amps))]
            kept.append(int(winner))
        i = j
    return np.array(sorted(kept), dtype=int)


if __name__ == '__main__':
    rows = analyze()
    import json
    with open(os.path.join(OUT_DIR, 'raw_results3.json'), 'w') as f:
        json.dump(rows, f, indent=2)
    print(f"\nGuardado {len(rows)} filas en raw_results3.json")
