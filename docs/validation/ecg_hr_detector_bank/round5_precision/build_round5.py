import sys, os
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import numpy as np
import wfdb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from clinical.ecg_analyzer import (
    ECGAnalyzer, ClinicalDataQualityError,
    PRR_THRESHOLD_MS, PRR_FRACTION_LIMIT, METRONOME_SDNN_MS,
    SINUS_SDNN_MIN_MS, SINUS_SDNN_MAX_MS, QUALITY_THRESHOLD,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PF = 1.5  # el parametro que logra la frontera correcta en los 5 casos primarios

RECORDS = [
    ('100', 0, 'sinusal limpio -- DEBE aceptar'),
    ('103', 0, 'sinusal limpio -- DEBE aceptar'),
    ('118', 0, 'BRD -- DEBE aceptar'),
    ('210', 0, 'FA sostenida -- DEBE declinar'),
    ('217', 0, 'marcapasos -- DEBE declinar'),
    ('233', 0, 'ruido severo -- DEBE declinar'),
    ('100', 1, '100, otra derivacion (V5) -- discrepancia residual'),
]

_cache = {}
def load(rec_id, lead, dur=180):
    key = (rec_id, lead, dur)
    if key in _cache: return _cache[key]
    record = wfdb.rdrecord(rec_id, pn_dir='mitdb', sampto=int(dur*360))
    sig = record.p_signal[:, lead]
    fs = record.fs
    sig_name = record.sig_name[lead]
    _cache[key] = (sig, fs, sig_name)
    return _cache[key]


def gather_rows():
    rows = []
    for rec_id, lead, label in RECORDS:
        sig, fs, sig_name = load(rec_id, lead)
        analyzer = ECGAnalyzer(fs=fs)
        peaks, _ = analyzer.detect_r_peaks_bidirectional(sig, prominence_factor=PF)
        rr_int = np.diff(peaks) / fs * 1000.0
        sdnn_int = float(np.std(rr_int))
        refined = analyzer.refine_peaks_parabolic(sig, peaks)
        rr_ref = np.diff(refined) / fs * 1000.0
        sdnn_ref = float(np.std(rr_ref))
        diffs = np.abs(np.diff(rr_ref))
        prr31 = float(np.mean(diffs >= PRR_THRESHOLD_MS))
        try:
            hr, conf = analyzer.estimate_heart_rate_with_confidence(sig, prominence_factor=PF)
            verdict, reason = 'ACEPTA', f'conf={conf:.2f}'
        except ClinicalDataQualityError as e:
            verdict = 'DECLINA'
            msg = str(e)
            if 'irregular no sinusal' in msg: reason = 'pRRx'
            elif 'variabilidad autonómica' in msg: reason = 'metronomo'
            elif 'banda fisiológica' in msg: reason = 'fuera_banda'
            elif 'Confianza' in msg: reason = 'calidad'
            else: reason = 'otro'
        rows.append({
            'rec': f'{rec_id}-{sig_name}', 'label': label,
            'sdnn_int': sdnn_int, 'sdnn_ref': sdnn_ref, 'prr31': prr31,
            'verdict': verdict, 'reason': reason,
        })
    return rows


def build_pdf(rows):
    out_path = os.path.join(OUT_DIR, 'hoja_firma_experto_ronda5.pdf')
    with PdfPages(out_path) as pdf:
        # Portada
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.5, 0.90, "Hoja de firma — ronda 5 (de confirmación, no de diseño)", ha='center', fontsize=17, weight='bold')
        fig.text(0.5, 0.84, "Precisión temporal del fiducial + filtros R-R validados por literatura", ha='center', fontsize=11)
        fig.text(0.06, 0.76,
            "PARTE A — Interpolación parabólica (Task Force ESC/NASPE 1996, Circulation 1996;93:1043)\n\n"
            "Hipótesis probada: el SDNN inflado del registro 217 (109-175ms medido con índices enteros) es\n"
            "jitter de cuantización de muestra, corregible refinando el fiducial a sub-muestra.\n\n"
            "RESULTADO: HIPÓTESIS FALSEADA por medición directa -- ver tabla abajo. El SDNN refinado es\n"
            "prácticamente idéntico al SDNN sobre índices enteros (diferencia <0.1ms en todos los casos,\n"
            "sinusales incluidos). La interpolación funciona (los deltas sub-muestra calculados no son cero,\n"
            "verificado) pero corrige un error dos órdenes de magnitud menor (~1ms) que el desajuste real\n"
            "observado (decenas a cientos de ms) -- consistente con que el detector escoge, latido a latido,\n"
            "puntos DISTINTOS del QRS ancho de un ritmo estimulado, no con redondeo de una posición ya\n"
            "consistente. Reportado sin suavizar -- no se forzó ni se escondió el resultado negativo.",
            fontsize=9.5, family='monospace', va='top')
        plt.axis('off')
        pdf.savefig(fig)
        plt.close(fig)

        # Tabla SDNN entero vs refinado
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.axis('off')
        col_labels = ['Registro', 'Descripción', 'SDNN entero (ms)', 'SDNN refinado (ms)', 'Δ (ms)']
        cell_text = []
        for r in rows:
            delta = r['sdnn_ref'] - r['sdnn_int']
            cell_text.append([r['rec'], r['label'][:38], f"{r['sdnn_int']:.2f}", f"{r['sdnn_ref']:.2f}", f"{delta:+.3f}"])
        table = ax.table(cellText=cell_text, colLabels=col_labels, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)
        for j in range(len(col_labels)):
            table[(0, j)].set_facecolor('#1d4ed8')
            table[(0, j)].set_text_props(color='white', weight='bold')
        ax.set_title('SDNN — índices enteros vs. marcas refinadas (prominence_factor=1.5)\n'
                      'La prueba del jitter: el 217 NO colapsa (Δ≈0 en todos los registros, no solo el 217)',
                      fontsize=11, weight='bold')
        pdf.savefig(fig)
        plt.close(fig)

        # Tabla frontera pRR31
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.axis('off')
        col_labels2 = ['Registro', 'Descripción', 'pRR31', 'SDNN refinado (ms)', 'Veredicto', 'Razón']
        cell_text2 = []
        for r in rows:
            expected_ok = ('DEBE aceptar' in r['label'] and r['verdict'] == 'ACEPTA') or \
                          ('DEBE declinar' in r['label'] and r['verdict'] == 'DECLINA')
            mark = '✓' if expected_ok else ('⚠' if 'DEBE' in r['label'] else '')
            cell_text2.append([r['rec'], r['label'][:34], f"{r['prr31']:.1%}", f"{r['sdnn_ref']:.1f}",
                                f"{mark} {r['verdict']}", r['reason']])
        table2 = ax.table(cellText=cell_text2, colLabels=col_labels2, loc='center', cellLoc='center')
        table2.auto_set_font_size(False)
        table2.set_fontsize(8.5)
        table2.scale(1, 2)
        for j in range(len(col_labels2)):
            table2[(0, j)].set_facecolor('#1d4ed8')
            table2[(0, j)].set_text_props(color='white', weight='bold')
        for i, r in enumerate(rows, start=1):
            expected_ok = ('DEBE aceptar' in r['label'] and r['verdict'] == 'ACEPTA') or \
                          ('DEBE declinar' in r['label'] and r['verdict'] == 'DECLINA')
            if 'DEBE' in r['label']:
                color = '#c6f6d5' if expected_ok else '#fed7d7'
                for j in range(len(col_labels2)):
                    table2[(i, j)].set_facecolor(color)
        ax.set_title(f'Frontera con pRR{PRR_THRESHOLD_MS:.0f} + Metrónomo + banda sinusal (prominence_factor={PF})\n'
                      'Verde = coincide con el veredicto clínico esperado · Rojo = discrepancia',
                      fontsize=11, weight='bold')
        pdf.savefig(fig)
        plt.close(fig)

        # Tiras con picos (marcas refinadas indicadas en el titulo por registro)
        for rec_id, lead, label in RECORDS:
            sig, fs, sig_name = load(rec_id, lead)
            analyzer = ECGAnalyzer(fs=fs)
            peaks, _ = analyzer.detect_r_peaks_bidirectional(sig, prominence_factor=PF)
            refined = analyzer.refine_peaks_parabolic(sig, peaks)
            n_strip = int(8 * fs)
            t = np.arange(n_strip) / fs
            seg = sig[:n_strip]
            peaks_w = peaks[peaks < n_strip]
            refined_w = refined[refined < n_strip]

            fig, ax = plt.subplots(figsize=(11, 4))
            ax.plot(t, seg, color='#1d4ed8', linewidth=0.8)
            if len(peaks_w):
                ax.plot(peaks_w / fs, sig[peaks_w], 'v', color='#dc2626', markersize=9, label='Pico (muestra entera)')
            if len(refined_w):
                ax.plot(refined_w / fs, np.interp(refined_w, np.arange(len(sig)), sig), '+', color='#f97316',
                        markersize=12, markeredgewidth=2, label='Posición refinada (sub-muestra)')
            ax.set_title(f'{rec_id}-{sig_name} — {label}\n'
                         f'pRR31={next(r["prr31"] for r in rows if r["rec"]==f"{rec_id}-{sig_name}"):.1%} · '
                         f'SDNN refinado={next(r["sdnn_ref"] for r in rows if r["rec"]==f"{rec_id}-{sig_name}"):.1f}ms',
                         fontsize=10)
            ax.legend(loc='upper right', fontsize=8)
            ax.set_xlabel('Tiempo (s)')
            ax.grid(alpha=0.2)
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

        # Hoja de firma
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.5, 0.95, "Hoja de firma — los 3 umbrales provisionales", ha='center', fontsize=15, weight='bold')
        y = 0.86
        entries = [
            ("pRR_THRESHOLD_MS (x de pRRx)", "31 ms", "Buś et al. — AUC 0.958 discriminando FA", "citado directamente"),
            ("PRR_FRACTION_LIMIT", "50%", "No publicado como corte único — calibrado sobre este banco: "
             "sinusales 16-30%, no-sinusales 73-94%", "PROVISIONAL, no de la cita"),
            ("METRONOME_SDNN_MS", "3 ms", "Umbral de ausencia de variabilidad — no colapsó a 0 en 217 con el "
             "detector actual (ver hipótesis falseada arriba)", "PROVISIONAL, premisa parcialmente falseada"),
            ("QUALITY_THRESHOLD", "0.6", "Confianza mínima (regularidad + consistencia de amplitud, sin "
             "ground truth)", "PROVISIONAL, sin cambios desde ronda 2"),
        ]
        fig.text(0.06, y, "Para cada uno: valor de literatura/origen, valor medido en el banco, ¿confirma o ajusta?\n", fontsize=9.5, style='italic')
        y -= 0.05
        for name, val, note, status in entries:
            fig.text(0.06, y, f"• {name} = {val}  [{status}]", fontsize=10, weight='bold')
            y -= 0.035
            fig.text(0.09, y, note, fontsize=8.5)
            y -= 0.03
            fig.text(0.09, y, "¿Confirma este valor?  SI ___   NO, ajustar a: _______", fontsize=9)
            y -= 0.06
        fig.text(0.06, y - 0.02, "Pregunta final: con estos umbrales, ¿autoriza el cableado de la escritura ECG→UPS?", fontsize=11, weight='bold')
        fig.text(0.06, y - 0.06, "SI ___     NO, falta: _________________________________", fontsize=10)
        plt.axis('off')
        pdf.savefig(fig)
        plt.close(fig)

    print(f"PDF guardado en: {out_path}")


if __name__ == '__main__':
    rows = gather_rows()
    for r in rows:
        print(r)
    build_pdf(rows)
