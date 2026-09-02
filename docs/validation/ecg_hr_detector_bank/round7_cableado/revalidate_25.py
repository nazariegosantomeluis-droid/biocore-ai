"""Re-validacion de la compuerta recalibrada a Vpp sobre los 25 registros de
la cohorte de la ronda 6 (Capa 2/5B, tanda de cableado, Parte B, con punto
de parada). Solo lectura sobre clinical.ecg_analyzer."""
import sys, os, json
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import numpy as np
import wfdb
from clinical.ecg_analyzer import ECGAnalyzer, ClinicalDataQualityError

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDS = ['100', '103', '117', '108', '228', '207', '233', '118', '210', '217',
           '101', '105', '109', '111', '112', '115', '122', '123', '102', '104',
           '200', '201', '203', '208', '221']

# Expectativa conocida por tipo de ritmo (de anotaciones/rondas previas) --
# solo para los casos donde hay una expectativa clara, no para todos.
EXPECTED = {
    '100': 'ACEPTA', '103': 'ACEPTA', '118': 'ACEPTA',   # sinusales limpios / BRD sinusal
    '210': 'DECLINA', '217': 'DECLINA', '104': 'DECLINA',  # FA / marcapasos / marcapasos
}

# Del gate_comparison.json de la ronda 6 (compuerta VIEJA de amplitud
# puntual, sobre picos TKEO) -- para la columna "antes" de la tabla.
with open(os.path.join(REPO_ROOT, 'docs', 'validation', 'ecg_hr_detector_bank',
                        'round6_robustez', 'gate_comparison.json')) as f:
    before = {r['rec']: r['verdict_tkeo'] for r in json.load(f)}

rows = []
stop_conditions = []
for rec_id in RECORDS:
    record = wfdb.rdrecord(rec_id, pn_dir='mitdb', sampto=int(180 * 360))
    ann = wfdb.rdann(rec_id, 'atr', pn_dir='mitdb', sampto=int(180 * 360))
    sig = record.p_signal[:, 0]
    fs = record.fs
    symbols = np.array(ann.symbol)
    n_total = int(np.sum(symbols != '+'))
    n_paced = int(np.sum(symbols == '/'))
    paced_frac = n_paced / n_total if n_total else 0.0

    analyzer = ECGAnalyzer(fs=fs)
    try:
        hr, conf = analyzer.estimate_heart_rate_with_confidence(sig)
        verdict, reason = 'ACEPTA', f'conf={conf:.2f}'
    except ClinicalDataQualityError as e:
        verdict = 'DECLINA'
        msg = str(e)
        if 'irregular no sinusal' in msg: reason = 'pRRx'
        elif 'variabilidad autonómica' in msg: reason = 'metronomo'
        elif 'banda fisiológica' in msg: reason = 'fuera_banda'
        elif 'Confianza' in msg: reason = 'calidad'
        elif 'picos detectados' in msg: reason = 'pocos_picos'
        else: reason = 'otro'

    expected = EXPECTED.get(rec_id)
    matches_expected = (expected is None) or (verdict == expected)
    before_verdict = before.get(rec_id, '?')
    changed = before_verdict != verdict

    row = {
        'rec': rec_id, 'before_vpp_amplitud_puntual': before_verdict,
        'after_vpp': verdict, 'reason': reason, 'changed': changed,
        'expected': expected, 'matches_expected': matches_expected,
        'paced_frac': round(paced_frac, 3),
    }
    rows.append(row)

    flag = ''
    if expected and not matches_expected:
        flag = '  <<<< PUNTO DE PARADA: no coincide con lo esperado'
        stop_conditions.append(row)
    elif changed:
        flag = '  (cambia respecto a la ronda 6)'
    print(f"{rec_id:>5}: antes(ronda6,Vpp-puntual)={before_verdict:8s}  ahora(Vpp-ventana)={verdict:8s}({reason}){flag}"
          + (f"  [esperado:{expected}]" if expected else ""))

with open(os.path.join(OUT_DIR, 'revalidation_25.json'), 'w') as f:
    json.dump(rows, f, indent=2)

print(f"\n{sum(1 for r in rows if r['changed'])} de {len(rows)} cambian de veredicto vs ronda 6.")
if stop_conditions:
    print(f"\n*** PUNTO DE PARADA: {len(stop_conditions)} registro(s) no coinciden con la expectativa clinica conocida ***")
    for r in stop_conditions:
        print(f"   {r['rec']}: esperaba {r['expected']}, dio {r['after_vpp']} ({r['reason']})")
else:
    print("\nSin puntos de parada -- los 6 casos con expectativa clara (100,103,118,210,217,104) coinciden.")
