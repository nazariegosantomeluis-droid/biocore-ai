import sys, os
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from build_bank3 import RECORDS, load_record, ANALYSIS_DURATION_S, STRIP_DURATION_S, _bidir_amplitude_tiebreak
from clinical.ecg_analyzer import ECGAnalyzer

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STRIP_PF = 1.0


def make_strips_pdf():
    out_path = os.path.join(OUT_DIR, 'tiras_ecg_3a_ronda.pdf')
    with PdfPages(out_path) as pdf:
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.5, 0.66, "Banco de validación — 3ª ronda", ha='center', fontsize=20, weight='bold')
        fig.text(0.5, 0.58, "Parte A: desempate por pendiente (recupera BRD) · Parte B: bandera de marcapasos (resultado negativo)", ha='center', fontsize=11)
        fig.text(0.5, 0.44,
                  "▽ rojo = pico detectado · X verde = anotación de cardiólogo (ground truth)\n\n"
                  "Registro 118 (BRD): compara AMPLITUD (ronda 2, regresión a 0.64) vs PENDIENTE (ronda 3, recuperado a ~0.99).\n"
                  "Registro 217 (marcapasos): con pendiente, el detector ahora es preciso (sens=0.94) -- pero DEBE excluirse\n"
                  "igual, por mandato clínico (R-R no gobernado por el nodo sinusal). La bandera de marcapasos NO logró\n"
                  "identificarlo de forma confiable -- ver hoja de decisión.",
                  ha='center', fontsize=9)
        fig.text(0.5, 0.12, "Preparado para la bendición final del experto — Capa 2/Capa 5B (2026-08-24)", ha='center', fontsize=8, style='italic')
        plt.axis('off')
        pdf.savefig(fig)
        plt.close(fig)

        for rec_id, lead_idx, label in RECORDS:
            sig, fs, sig_name, gt_samples = load_record(rec_id, lead_idx, ANALYSIS_DURATION_S)
            analyzer = ECGAnalyzer(fs=fs)
            n_strip = int(STRIP_DURATION_S * fs)
            start, end = 0, n_strip
            t = np.arange(start, min(end, len(sig))) / fs
            seg = sig[start:min(end, len(sig))]
            gt_w = gt_samples[(gt_samples >= start) & (gt_samples < end)]

            fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
            fig.suptitle(f"{rec_id} ({sig_name}) — {label}", fontsize=10, weight='bold')

            ax = axes[0]
            peaks_amp = _bidir_amplitude_tiebreak(analyzer, sig, STRIP_PF)
            peaks_amp_w = peaks_amp[(peaks_amp >= start) & (peaks_amp < end)]
            ax.plot(t, seg, color='#1d4ed8', linewidth=0.8)
            if len(peaks_amp_w):
                ax.plot(peaks_amp_w / fs, sig[peaks_amp_w], marker='v', color='#dc2626', linestyle='None', markersize=9, label='Detectado (amplitud, r2)')
            if len(gt_w):
                ax.plot(gt_w / fs, sig[gt_w], marker='x', color='#16a34a', linestyle='None', markersize=10, markeredgewidth=2, label='GT')
            ax.set_title('Ronda 2: desempate por AMPLITUD', fontsize=9, loc='left')
            ax.legend(loc='upper right', fontsize=7)
            ax.grid(alpha=0.2)

            ax = axes[1]
            peaks_slope, competitions = analyzer.detect_r_peaks_bidirectional(sig, prominence_factor=STRIP_PF)
            peaks_slope_w = peaks_slope[(peaks_slope >= start) & (peaks_slope < end)]
            ax.plot(t, seg, color='#1d4ed8', linewidth=0.8)
            if len(peaks_slope_w):
                ax.plot(peaks_slope_w / fs, sig[peaks_slope_w], marker='v', color='#dc2626', linestyle='None', markersize=9, label='Detectado (pendiente, r3)')
            if len(gt_w):
                ax.plot(gt_w / fs, sig[gt_w], marker='x', color='#16a34a', linestyle='None', markersize=10, markeredgewidth=2, label='GT')
            title_extra = ''
            if rec_id == '217':
                title_extra = ' -- preciso, pero DEBE excluirse por mandato clínico (bandera de marcapasos no confiable)'
            ax.set_title(f'Ronda 3: desempate por PENDIENTE{title_extra}', fontsize=9, loc='left')
            ax.legend(loc='upper right', fontsize=7)
            ax.grid(alpha=0.2)
            ax.set_xlabel('Tiempo (s)')

            plt.tight_layout(rect=[0, 0, 1, 0.93])
            pdf.savefig(fig)
            plt.close(fig)

    print(f"PDF de tiras (3a ronda) guardado en: {out_path}")


if __name__ == '__main__':
    make_strips_pdf()
