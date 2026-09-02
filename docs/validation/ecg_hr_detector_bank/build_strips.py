import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from build_bank import RECORDS, load_record, ANALYSIS_DURATION_S, STRIP_DURATION_S
from clinical.ecg_analyzer import ECGAnalyzer

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STRIP_PFS = [0.3, 1.0]  # contraste: default de la clase vs candidato del diagnostico


def make_strips_pdf():
    out_path = os.path.join(OUT_DIR, 'tiras_ecg_picos_marcados.pdf')
    with PdfPages(out_path) as pdf:
        # Portada
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.5, 0.6, "Banco de validación — Detector de HR de ECG", ha='center', fontsize=20, weight='bold')
        fig.text(0.5, 0.52, "Tiras de ECG con picos detectados vs anotaciones de cardiólogos (MIT-BIH)", ha='center', fontsize=13)
        fig.text(0.5, 0.44, f"clinical.ecg_analyzer.ECGAnalyzer.detect_r_peaks() — prominence_factor = {STRIP_PFS[0]} (default de la clase) vs {STRIP_PFS[1]} (candidato)", ha='center', fontsize=10)
        fig.text(0.5, 0.36,
                  "Leyenda: línea azul = señal ECG (derivación MLII) · triángulo rojo = pico detectado por el algoritmo\n"
                  "· X verde = anotación de cardiólogo (ground truth, MIT-BIH .atr)\n"
                  "Coincidencia dentro de ±50ms se considera acierto; un triángulo sin X cerca es falso positivo (típicamente onda T duplicada);\n"
                  "una X sin triángulo cerca es un latido real perdido.",
                  ha='center', fontsize=9)
        fig.text(0.5, 0.15, "Preparado para revisión del experto — Capa 2/Capa 5B, mini-arco de validación (2026-08-24)", ha='center', fontsize=8, style='italic')
        plt.axis('off')
        pdf.savefig(fig)
        plt.close(fig)

        for rec_id, label in RECORDS.items():
            sig, fs, sig_name, gt_samples, gt_symbols = load_record(rec_id, ANALYSIS_DURATION_S)
            analyzer = ECGAnalyzer(fs=fs)
            n_strip = int(STRIP_DURATION_S * fs)
            # elegir una ventana con al menos 3 anotaciones dentro, empezando cerca del inicio
            start = 0
            window_gt = gt_samples[(gt_samples >= start) & (gt_samples < start + n_strip)]
            if len(window_gt) < 3 and len(gt_samples) > 0:
                start = max(0, int(gt_samples[len(gt_samples) // 4]) - n_strip // 2)
            end = start + n_strip
            t = np.arange(start, min(end, len(sig))) / fs
            seg = sig[start:min(end, len(sig))]

            fig, axes = plt.subplots(len(STRIP_PFS), 1, figsize=(11, 7), sharex=True)
            fig.suptitle(f"Registro MIT-BIH {rec_id} — {label}\nDerivación: {sig_name} · fs={fs}Hz", fontsize=11, weight='bold')

            gt_in_window = gt_samples[(gt_samples >= start) & (gt_samples < end)]

            for ax, pf in zip(axes, STRIP_PFS):
                peaks = analyzer.detect_r_peaks(sig, prominence_factor=pf)
                peaks_in_window = peaks[(peaks >= start) & (peaks < end)]
                ax.plot(t, seg, color='#1d4ed8', linewidth=0.8, label='ECG')
                if len(peaks_in_window) > 0:
                    ax.plot(peaks_in_window / fs, sig[peaks_in_window], marker='v', color='#dc2626',
                            linestyle='None', markersize=9, label='Pico detectado')
                if len(gt_in_window) > 0:
                    ax.plot(gt_in_window / fs, sig[gt_in_window], marker='x', color='#16a34a',
                            linestyle='None', markersize=10, markeredgewidth=2, label='Anotación cardiólogo (GT)')
                ax.set_ylabel('mV')
                ax.set_title(f'prominence_factor = {pf}', fontsize=9, loc='left')
                ax.legend(loc='upper right', fontsize=7, ncol=3)
                ax.grid(alpha=0.2)

            axes[-1].set_xlabel('Tiempo (s)')
            plt.tight_layout(rect=[0, 0, 1, 0.94])
            pdf.savefig(fig)
            plt.close(fig)

    print(f"PDF de tiras guardado en: {out_path}")


if __name__ == '__main__':
    make_strips_pdf()
