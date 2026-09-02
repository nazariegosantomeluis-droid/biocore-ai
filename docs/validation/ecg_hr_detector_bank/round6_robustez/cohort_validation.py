"""Validacion sobre cohorte MIT-BIH ampliada (Capa 2/5B, Ronda de Robustez,
Parte C). Descarga en vivo desde PhysioNet, igual que las rondas
anteriores. Solo lectura sobre clinical.ecg_analyzer."""
import sys, os, json
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import numpy as np
import wfdb
from collections import Counter
from clinical.ecg_analyzer import ECGAnalyzer, ClinicalDataQualityError

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
DUR_S = 180

# 10 de las rondas anteriores + 15 nuevos, cubriendo variedad
EXISTING = ['100', '103', '117', '108', '228', '207', '233', '118', '210', '217']
NEW = ['101', '105', '109', '111', '112', '115', '122', '123',  # normales/BBB
       '102', '104',                                             # mas marcapasos
       '200', '201', '203', '208', '221']                        # PVC/AFib
ALL_RECORDS = EXISTING + NEW


def match_peaks(detected, ground_truth, fs, tolerance_s=0.05):
    tol = tolerance_s * fs
    detected = np.sort(detected); ground_truth = np.sort(ground_truth)
    used_det = np.zeros(len(detected), dtype=bool)
    tp = 0
    for g in ground_truth:
        if len(detected) == 0: break
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
    fp = len(detected) - int(used_det.sum())
    return tp, fp, fn


def run():
    rows = []
    failed = []
    for rec_id in ALL_RECORDS:
        try:
            record = wfdb.rdrecord(rec_id, pn_dir='mitdb', sampto=int(DUR_S * 360))
            ann = wfdb.rdann(rec_id, 'atr', pn_dir='mitdb', sampto=int(DUR_S * 360))
        except Exception as e:
            failed.append((rec_id, str(e)))
            print(f"{rec_id}: FALLO DE DESCARGA -- {e}")
            continue
        sig = record.p_signal[:, 0]
        fs = record.fs
        symbols = np.array(ann.symbol)
        gt = ann.sample[symbols != '+']
        symbol_counts = Counter(symbols[symbols != '+'])
        n_paced = symbol_counts.get('/', 0)
        n_pvc = symbol_counts.get('V', 0)
        n_total_beats = len(gt)
        paced_frac = n_paced / n_total_beats if n_total_beats else 0
        pvc_frac = n_pvc / n_total_beats if n_total_beats else 0

        analyzer = ECGAnalyzer(fs=fs)
        peaks = analyzer.detect_r_peaks_tkeo(sig)
        tp, fp, fn = match_peaks(peaks, gt, fs)
        sens = tp / n_total_beats if n_total_beats else float('nan')
        ppv = tp / (tp + fp) if (tp + fp) else float('nan')

        try:
            hr, conf = analyzer.estimate_heart_rate_with_confidence(sig, prominence_factor=1.5)
            gate_verdict, gate_reason = 'ACEPTA', f'conf={conf:.2f}'
        except ClinicalDataQualityError as e:
            gate_verdict = 'DECLINA'
            msg = str(e)
            if 'irregular no sinusal' in msg: gate_reason = 'pRRx'
            elif 'variabilidad autonómica' in msg: gate_reason = 'metronomo'
            elif 'banda fisiológica' in msg: gate_reason = 'fuera_banda'
            elif 'Confianza' in msg: gate_reason = 'calidad'
            elif 'picos detectados' in msg: gate_reason = 'pocos_picos'
            else: gate_reason = 'otro'

        row = {
            'rec': rec_id, 'n_beats_gt': n_total_beats, 'paced_frac': round(paced_frac, 3),
            'pvc_frac': round(pvc_frac, 3), 'sens_tkeo': round(sens, 3), 'ppv_tkeo': round(ppv, 3),
            'gate_verdict': gate_verdict, 'gate_reason': gate_reason,
            'is_new': rec_id in NEW,
        }
        rows.append(row)
        print(f"{rec_id}: n_beats={n_total_beats} paced={paced_frac:.1%} pvc={pvc_frac:.1%} "
              f"sens={sens:.3f} ppv={ppv:.3f} -> {gate_verdict}({gate_reason})")

    with open(os.path.join(OUT_DIR, 'cohort_results.json'), 'w') as f:
        json.dump({'rows': rows, 'failed': failed}, f, indent=2)
    print(f"\n{len(rows)} registros procesados, {len(failed)} fallaron.")
    return rows, failed


if __name__ == '__main__':
    run()
