"""Comparacion: verdictos de la compuerta whitelist alimentada con picos
BIDIRECCIONALES (deteccion actual del metodo de produccion) vs picos TKEO
(deteccion nueva, aun no cableada a la compuerta). Test-only -- no modifica
clinical/ecg_analyzer.py."""
import sys, os, json
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import numpy as np
import wfdb
from clinical.ecg_analyzer import (
    ECGAnalyzer, ClinicalDataQualityError,
    PRR_THRESHOLD_MS, PRR_FRACTION_LIMIT, METRONOME_SDNN_MS,
    SINUS_SDNN_MIN_MS, SINUS_SDNN_MAX_MS, QUALITY_THRESHOLD,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDS = ['100', '103', '117', '108', '228', '207', '233', '118', '210', '217',
           '101', '105', '109', '111', '112', '115', '122', '123', '102', '104',
           '200', '201', '203', '208', '221']
EXPECTED = {  # solo para los casos con expectativa clara del encargo
    '100': 'ACEPTA', '103': 'ACEPTA', '118': 'ACEPTA', '210': 'DECLINA', '217': 'DECLINA',
}


def gate_on_peaks(analyzer, signal, peaks):
    if len(peaks) < 3:
        return 'DECLINA', 'pocos_picos', None
    refined = analyzer.refine_peaks_parabolic(signal, peaks)
    rr_ms = np.diff(refined) / analyzer.fs * 1000.0
    if len(rr_ms) > 1:
        diffs = np.abs(np.diff(rr_ms))
        prrx = float(np.mean(diffs >= PRR_THRESHOLD_MS))
        if prrx > PRR_FRACTION_LIMIT:
            return 'DECLINA', 'pRRx', None
    sdnn = float(np.std(rr_ms))
    if sdnn < METRONOME_SDNN_MS:
        return 'DECLINA', 'metronomo', None
    if not (SINUS_SDNN_MIN_MS <= sdnn <= SINUS_SDNN_MAX_MS):
        return 'DECLINA', 'fuera_banda', None
    rr = rr_ms / 1000.0
    rr_cv = float(np.std(rr) / np.mean(rr)) if np.mean(rr) > 0 else 1.0
    regularity = float(np.clip(1.0 - rr_cv / 0.5, 0, 1))
    amps = np.abs(signal[peaks])
    amp_cv = float(np.std(amps) / np.mean(amps)) if np.mean(amps) > 0 else 1.0
    amplitude = float(np.clip(1.0 - amp_cv / 0.6, 0, 1))
    conf = float(np.clip(0.5 * regularity + 0.5 * amplitude, 0, 1))
    if conf < QUALITY_THRESHOLD:
        return 'DECLINA', 'calidad', conf
    return 'ACEPTA', 'ok', conf


rows = []
for rec_id in RECORDS:
    record = wfdb.rdrecord(rec_id, pn_dir='mitdb', sampto=int(180 * 360))
    sig = record.p_signal[:, 0]
    fs = record.fs
    analyzer = ECGAnalyzer(fs=fs)

    try:
        hr, conf_b = analyzer.estimate_heart_rate_with_confidence(sig, prominence_factor=1.5)
        verdict_b, reason_b = 'ACEPTA', f'conf={conf_b:.2f}'
    except ClinicalDataQualityError as e:
        verdict_b = 'DECLINA'
        msg = str(e)
        if 'irregular no sinusal' in msg: reason_b = 'pRRx'
        elif 'variabilidad autonómica' in msg: reason_b = 'metronomo'
        elif 'banda fisiológica' in msg: reason_b = 'fuera_banda'
        elif 'Confianza' in msg: reason_b = 'calidad'
        else: reason_b = 'otro'

    peaks_t = analyzer.detect_r_peaks_tkeo(sig)
    verdict_t, reason_t, conf_t = gate_on_peaks(analyzer, sig, peaks_t)

    flip = verdict_b != verdict_t
    rows.append({
        'rec': rec_id, 'verdict_bidir': verdict_b, 'reason_bidir': reason_b,
        'verdict_tkeo': verdict_t, 'reason_tkeo': reason_t, 'flip': flip,
        'expected': EXPECTED.get(rec_id),
    })
    flag = ' <<<< FLIP' if flip else ''
    exp = f" [esperado: {EXPECTED[rec_id]}]" if rec_id in EXPECTED else ''
    print(f"{rec_id:>5}: bidir={verdict_b}({reason_b})  tkeo={verdict_t}({reason_t}){flag}{exp}")

with open(os.path.join(OUT_DIR, 'gate_comparison.json'), 'w') as f:
    json.dump(rows, f, indent=2)

n_flips = sum(1 for r in rows if r['flip'])
print(f"\n{n_flips} de {len(rows)} registros CAMBIAN de veredicto al pasar de picos bidireccionales a picos TKEO.")
for r in rows:
    if r['expected'] and r['verdict_tkeo'] != r['expected']:
        print(f"REGRESION vs expectativa: {r['rec']} esperaba {r['expected']}, TKEO+compuerta da {r['verdict_tkeo']} ({r['reason_tkeo']})")
