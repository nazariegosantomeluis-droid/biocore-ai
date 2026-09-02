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

from build_bank2 import RECORDS, load_record, ANALYSIS_DURATION_S, STRIP_DURATION_S
from clinical.ecg_analyzer import ECGAnalyzer

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STRIP_PF = 1.0  # parametro de contraste unico para el antes/despues (viejo vs nuevo detector)


def make_strips_pdf():
    out_path = os.path.join(OUT_DIR, 'tiras_ecg_2a_ronda.pdf')
    with PdfPages(out_path) as pdf:
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.5, 0.62, "Banco de validación — 2ª ronda", ha='center', fontsize=20, weight='bold')
        fig.text(0.5, 0.54, "Detector VIEJO (find_peaks positivo) vs REPARADO (bidireccional + refractario)", ha='center', fontsize=13)
        fig.text(0.5, 0.46, f"clinical.ecg_analyzer.ECGAnalyzer.detect_r_peaks() [viejo] vs .detect_r_peaks_bidirectional() [reparado] — prominence_factor={STRIP_PF}", ha='center', fontsize=9)
        fig.text(0.5, 0.36,
                  "Leyenda: línea azul = ECG · ▽ rojo = pico detectado · X verde = anotación de cardiólogo (ground truth)\n"
                  "○ naranja = competencia bifásica marcada (dos picos de amplitud similar dentro del periodo refractario)\n\n"
                  "AVISO: el detector reparado NO es una mejora uniforme -- ayuda mucho en 108/207 (antes ciegos),\n"
                  "pero EMPEORA 118/217 (la supresión refractaria elige el pico equivocado). Ver hoja de decisión.",
                  ha='center', fontsize=9)
        fig.text(0.5, 0.12, "Preparado para la 2ª revisión del experto — Capa 2/Capa 5B (2026-08-24)", ha='center', fontsize=8, style='italic')
        plt.axis('off')
        pdf.savefig(fig)
        plt.close(fig)

        for rec_id, lead_idx, label in RECORDS:
            sig, fs, sig_name, gt_samples = load_record(rec_id, lead_idx, ANALYSIS_DURATION_S)
            analyzer = ECGAnalyzer(fs=fs)
            n_strip = int(STRIP_DURATION_S * fs)
            start = 0
            end = start + n_strip
            t = np.arange(start, min(end, len(sig))) / fs
            seg = sig[start:min(end, len(sig))]
            gt_in_window = gt_samples[(gt_samples >= start) & (gt_samples < end)]

            fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
            fig.suptitle(f"{rec_id} ({sig_name}) — {label}", fontsize=10, weight='bold')

            # Viejo
            ax = axes[0]
            peaks_old = analyzer.detect_r_peaks(sig, prominence_factor=STRIP_PF)
            peaks_old_w = peaks_old[(peaks_old >= start) & (peaks_old < end)]
            ax.plot(t, seg, color='#1d4ed8', linewidth=0.8)
            if len(peaks_old_w):
                ax.plot(peaks_old_w / fs, sig[peaks_old_w], marker='v', color='#dc2626', linestyle='None', markersize=9, label='Detectado (viejo)')
            if len(gt_in_window):
                ax.plot(gt_in_window / fs, sig[gt_in_window], marker='x', color='#16a34a', linestyle='None', markersize=10, markeredgewidth=2, label='GT')
            ax.set_title('Detector VIEJO (find_peaks positivo)', fontsize=9, loc='left')
            ax.legend(loc='upper right', fontsize=7)
            ax.grid(alpha=0.2)

            # Nuevo
            ax = axes[1]
            peaks_new, competitions = analyzer.detect_r_peaks_bidirectional(sig, prominence_factor=STRIP_PF)
            peaks_new_w = peaks_new[(peaks_new >= start) & (peaks_new < end)]
            ax.plot(t, seg, color='#1d4ed8', linewidth=0.8)
            if len(peaks_new_w):
                ax.plot(peaks_new_w / fs, sig[peaks_new_w], marker='v', color='#dc2626', linestyle='None', markersize=9, label='Detectado (reparado)')
            if len(gt_in_window):
                ax.plot(gt_in_window / fs, sig[gt_in_window], marker='x', color='#16a34a', linestyle='None', markersize=10, markeredgewidth=2, label='GT')
            comp_in_window = [c for c in competitions if start <= c['winner_sample'] < end]
            for c in comp_in_window:
                ax.plot(c['winner_sample'] / fs, sig[c['winner_sample']], marker='o', color='#f97316',
                        markersize=16, markerfacecolor='none', markeredgewidth=2)
            ax.set_title(f'Detector REPARADO (bidireccional + refractario) -- {len(comp_in_window)} competencia(s) bifásica(s) en esta ventana', fontsize=9, loc='left')
            ax.legend(loc='upper right', fontsize=7)
            ax.grid(alpha=0.2)
            ax.set_xlabel('Tiempo (s)')

            plt.tight_layout(rect=[0, 0, 1, 0.93])
            pdf.savefig(fig)
            plt.close(fig)

    print(f"PDF de tiras (2a ronda) guardado en: {out_path}")


if __name__ == '__main__':
    make_strips_pdf()
