import sys, os, json
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import numpy as np
import wfdb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from clinical.ecg_analyzer import ECGAnalyzer

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
cohort = json.load(open(os.path.join(OUT_DIR, 'cohort_results.json')))
rows = cohort['rows']

out_path = os.path.join(OUT_DIR, 'hoja_firma_final_ronda6.pdf')
with PdfPages(out_path) as pdf:
    # Portada
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.5, 0.94, "Hoja de firma FINAL — Ronda de Robustez", ha='center', fontsize=17, weight='bold')
    fig.text(0.5, 0.895, "Detector TKEO (fiducial estructural) + Z-score/curtosis + cohorte ampliada", ha='center', fontsize=11)
    fig.text(0.06, 0.83,
        "PRUEBA 1 — Fiducial estructural (registro 217, marcapasos):\n"
        "  SDNN bidireccional (ronda 5) = 175.24 ms\n"
        "  SDNN TKEO (esta ronda)       =  85.49 ms   (-51%, mejora real, NO colapso a ~0)\n"
        "  Sensibilidad/VPP bidireccional: 0.995 / 0.597  ->  TKEO: 0.986 / 1.000\n"
        "  Diagnóstico del experto CONFIRMADO PARCIALMENTE: el fiducial estructural mejoró\n"
        "  sustancialmente (VPP perfecto, SDNN a menos de la mitad) pero NO llegó al ≈0 esperado\n"
        "  de un ritmo mecánico puro. Los RR residuales (ver ronda) no muestran outliers erráticos\n"
        "  sino una dispersión suave ~780-910ms -- podría ser precisión residual del detector, o\n"
        "  variabilidad genuina de un marcapasos rate-responsive. Pregunta abierta para el experto,\n"
        "  no resuelta aquí.\n\n"
        "PRUEBA 2 — Sensibilidad de derivación (registro 100, lead V5):\n"
        "  Bidireccional: sens=1.000 VPP=0.751 SDNN=223.6ms  ->  TKEO: sens=1.000 VPP=1.000 SDNN=30.3ms\n"
        "  RESUELTO POR COMPLETO -- V5 queda prácticamente idéntico a su MLII (SDNN=30.1-30.5ms ambos).\n"
        "  Dato para la firma: TKEO SOLO resolvió V5, sin necesitar Z-score explícito -- confirmado\n"
        "  (3 de 223 picos difieren en 1 muestra entre TKEO directo y TKEO sobre señal Z-scoreada,\n"
        "  ruido de precisión numérica, no una diferencia sustantiva). Razón técnica: el umbral de\n"
        "  TKEO ya es adaptativo (media+z·std de la energía), auto-invariante a escala -- Z-score\n"
        "  sería redundante PARA ESTE detector. El SQI por curtosis SÍ funciona como mecanismo\n"
        "  independiente: curtosis MLII=26.70 > V5=17.78, elige MLII correctamente sin ver latidos.",
        fontsize=8.7, family='monospace', va='top')
    plt.axis('off')
    pdf.savefig(fig)
    plt.close(fig)

    # Tabla cohorte ampliada
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis('off')
    col_labels = ['Rec', 'N latidos\n(GT)', '%Paced', '%PVC', 'Sens\nTKEO', 'VPP\nTKEO', 'Veredicto\ncompuerta', 'Razón']
    cell_text = []
    colors = []
    for r in rows:
        cell_text.append([
            r['rec'] + (' *' if r['is_new'] else ''), str(r['n_beats_gt']),
            f"{r['paced_frac']:.0%}", f"{r['pvc_frac']:.0%}",
            f"{r['sens_tkeo']:.3f}", f"{r['ppv_tkeo']:.3f}",
            r['gate_verdict'], r['gate_reason'],
        ])
        if r['sens_tkeo'] < 0.85 or r['ppv_tkeo'] < 0.85:
            colors.append('#fed7d7')
        elif r['is_new']:
            colors.append('#dbeafe')
        else:
            colors.append('#ffffff')
    table = ax.table(cellText=cell_text, colLabels=col_labels, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(7.3)
    table.scale(1, 1.35)
    for j in range(len(col_labels)):
        table[(0, j)].set_facecolor('#1d4ed8')
        table[(0, j)].set_text_props(color='white', weight='bold')
    for i, c in enumerate(colors, start=1):
        for j in range(len(col_labels)):
            table[(i, j)].set_facecolor(c)
    ax.set_title(f'Cohorte MIT-BIH ampliada: {len(rows)} registros (10 de rondas previas + '
                 f'{sum(1 for r in rows if r["is_new"])} nuevos, marcados *) — detector TKEO,\n'
                 'compuerta whitelist a prominence_factor=1.5. Azul=registro nuevo · Rojo=sens o VPP < 0.85',
                 fontsize=10, weight='bold')
    pdf.savefig(fig)
    plt.close(fig)

    # Nota de generalizacion + discrepancias
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.5, 0.94, "Generalización y discrepancias — reportadas sin forzar umbrales", ha='center', fontsize=14, weight='bold')
    n_new = sum(1 for r in rows if r['is_new'])
    sens_new = [r['sens_tkeo'] for r in rows if r['is_new']]
    ppv_new = [r['ppv_tkeo'] for r in rows if r['is_new']]
    fig.text(0.06, 0.86,
        f"Cohorte: 25 registros procesados, 0 fallos de descarga (10 previos + {n_new} nuevos).\n"
        f"Sobre los {n_new} NUEVOS (nunca vistos por el detector en rondas anteriores):\n"
        f"  Sensibilidad: mediana={np.median(sens_new):.3f}, rango=[{min(sens_new):.3f}, {max(sens_new):.3f}]\n"
        f"  VPP:          mediana={np.median(ppv_new):.3f}, rango=[{min(ppv_new):.3f}, {max(ppv_new):.3f}]\n"
        "  -> el detector generaliza bien en la mayoría (9/15 nuevos con sens Y VPP >= 0.98) -- no\n"
        "     parece sobreajustado a los 11 casos de rondas anteriores.\n\n"
        "Casos que SÍ caen por debajo de 0.85 en sensibilidad o VPP (reportados, NO forzados):\n"
        "  • 104 (marcapasos, 62.7% latidos paced): sens=0.665 VPP=0.737 -- el peor del banco. TKEO\n"
        "    mejora mucho el registro 217 (89.9% paced) pero NO generaliza igual de bien a este otro\n"
        "    registro con marcapasos, con carga de latidos estimulados aún mayor.\n"
        "  • 208 (33.8% PVC): sens=0.749 VPP=0.835.\n"
        "  • 207 (29.3% PVC + ruido extremo, ya conocido de rondas previas): sens=0.775.\n"
        "  • 203 (13.7% PVC): sens=0.844.\n\n"
        "Discrepancias de la COMPUERTA en registros que parecen sinusales limpios (0% paced, 0% PVC)\n"
        "pero NO fueron aceptados:\n"
        "  • 123: DECLINA por pRRx (irregularidad aparente) pese a 0% paced/PVC según anotaciones --\n"
        "    caso no explicado por carga ectópica conocida, mérito de revisión aparte.\n"
        "  • 101, 111, 112: DECLINAN por la compuerta de CALIDAD genérica (confianza < 0.6), no por\n"
        "    los filtros de dinámica R-R -- la fórmula de confianza (heredada, sin cambios desde la\n"
        "    ronda 2: regularidad + consistencia de amplitud) sigue siendo un punto débil, ortogonal\n"
        "    a las reparaciones de esta ronda.\n\n"
        "No se ajustó ningún umbral para corregir estos casos -- son datos para la firma del experto.",
        fontsize=9, family='monospace', va='top')
    plt.axis('off')
    pdf.savefig(fig)
    plt.close(fig)

    # Tiras representativas: 217, 100-V5, un AFib (210)
    def load_lead(rec_id, lead, dur=8):
        record = wfdb.rdrecord(rec_id, pn_dir='mitdb', sampto=int(180 * 360))
        sig = record.p_signal[:, lead]
        fs = record.fs
        sig_name = record.sig_name[lead]
        return sig, fs, sig_name

    strip_cases = [('217', 0, '217 (marcapasos) — TKEO'), ('100', 1, '100-V5 — TKEO (antes fallaba)'),
                   ('210', 0, '210 (FA sostenida) — TKEO')]
    for rec_id, lead, title in strip_cases:
        sig, fs, sig_name = load_lead(rec_id, lead)
        analyzer = ECGAnalyzer(fs=fs)
        peaks = analyzer.detect_r_peaks_tkeo(sig)
        n_strip = int(8 * fs)
        t = np.arange(n_strip) / fs
        seg = sig[:n_strip]
        peaks_w = peaks[peaks < n_strip]
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(t, seg, color='#1d4ed8', linewidth=0.8)
        if len(peaks_w):
            ax.plot(peaks_w / fs, sig[peaks_w], 'v', color='#dc2626', markersize=10, label='Fiducial TKEO')
        ax.set_title(title, fontsize=11, weight='bold')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_xlabel('Tiempo (s)')
        ax.grid(alpha=0.2)
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    # HALLAZGO CRITICO: la compuerta re-apuntada a picos TKEO
    gate_cmp = json.load(open(os.path.join(OUT_DIR, 'gate_comparison.json')))
    n_flips = sum(1 for r in gate_cmp if r['flip'])
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.5, 0.95, "HALLAZGO CRÍTICO — la compuerta NO transfiere sin más a TKEO", ha='center', fontsize=13.5, weight='bold', color='#c0392b')
    lines = [f"{r['rec']:>5}: bidireccional={r['verdict_bidir']:8s}({r['reason_bidir']:10s})  "
             f"TKEO={r['verdict_tkeo']:8s}({r['reason_tkeo']:10s}){'  <<<< CAMBIA' if r['flip'] else ''}"
             + (f"  [esperado: {r['expected']}]" if r['expected'] else '')
             for r in gate_cmp]
    fig.text(0.05, 0.88,
        f"La MISMA lógica de la compuerta (pRR31/metrónomo/banda/calidad), re-aplicada sobre picos\n"
        f"TKEO en vez de picos bidireccionales (prominence_factor=1.5): {n_flips} de {len(gate_cmp)} registros "
        f"CAMBIAN de veredicto.\n\n"
        "REGRESIÓN CONCRETA: el registro 118 (BRD), que la ronda 5 aceptaba correctamente con el\n"
        "detector bidireccional, pasa a DECLINAR con TKEO -- por la compuerta de CALIDAD genérica,\n"
        "no por los filtros de dinámica R-R (que sí se mantienen estables entre detectores: 108, 228,\n"
        "207, 233, 210, 200-203, 208, 221, 104 declinan por pRRx en AMBOS casos, sin cambiar).\n\n"
        "Causa probable (no confirmada exhaustivamente): `amplitude_score` (parte de la fórmula de\n"
        "confianza, sin cambios desde la ronda 2) mide consistencia de amplitud en los puntos exactos\n"
        "que el detector marca. TKEO elige su fiducial por máxima pendiente DENTRO de una ventana de\n"
        "±50ms, no el máximo global -- introduce más variación beat-to-beat en la amplitud EXACTA del\n"
        "punto marcado que el detector bidireccional, aunque el punto sea clínicamente más correcto\n"
        "(ver PPV=1.000 de TKEO en records limpios). La fórmula de confianza penaliza esa variación\n"
        "como si fuera ruido de detección.\n\n"
        "CONCLUSIÓN: los filtros de dinámica R-R (pRR31/metrónomo/banda) SÍ generalizan entre\n"
        "detectores -- son robustos. La compuerta de CALIDAD genérica NO -- necesita recalibrarse (o\n"
        "rediseñarse) específicamente para las características del fiducial TKEO antes de que sea\n"
        "seguro apuntar la compuerta de producción a TKEO. Esto NO se resolvió en esta ronda -- se\n"
        "reporta como el bloqueo concreto que falta cerrar, no se forzó un ajuste para esconderlo.",
        fontsize=8.3, family='monospace', va='top')
    pdf.savefig(fig)
    plt.close(fig)

    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.5, 0.97, "Detalle: veredicto por registro, bidireccional vs. TKEO", ha='center', fontsize=12, weight='bold')
    fig.text(0.05, 0.92, "\n".join(lines), fontsize=7.3, family='monospace', va='top')
    pdf.savefig(fig)
    plt.close(fig)

    # Hoja de firma final
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.5, 0.95, "Pregunta de cierre", ha='center', fontsize=15, weight='bold')
    fig.text(0.06, 0.86,
        "Con el detector TKEO (fiducial estructural) + la compuerta whitelist (pRR31 / metrónomo /\n"
        "banda sinusal / calidad, prominence_factor=1.5) y la evidencia de esta ronda:\n\n"
        "  • Fiducial: mejorado sustancialmente, NO colapsado del todo en 217 (85ms residual)\n"
        "  • Derivación: V5 del 100 resuelto por completo con TKEO solo\n"
        "  • Cohorte: generaliza razonablemente en 25 registros, con 4 casos de sens/VPP < 0.85\n"
        "    (todos en carga alta de PVC/marcapasos) y 4 discrepancias de compuerta sin explicar\n"
        "    del todo (123, 101, 111, 112)\n"
        "  • CRÍTICO (página anterior): la compuerta re-apuntada a TKEO regresa el registro 118\n"
        "    (BRD) de aceptación correcta a rechazo incorrecto -- la fórmula de calidad genérica no\n"
        "    transfiere al fiducial TKEO sin recalibrarse. Los filtros pRR31/metrónomo/banda SÍ son\n"
        "    robustos entre detectores.\n\n"
        "Recomendación de Claude Code (no vinculante, el experto decide): NO cablear todavía la\n"
        "compuerta apuntada a TKEO tal cual -- el detector TKEO en sí (sensibilidad/VPP/generalización)\n"
        "está listo, pero la compuerta de calidad necesita recalibrarse contra sus fiduciales antes de\n"
        "confiar el veredicto sinusal/no-sinusal a esa combinación.\n\n"
        "¿Autoriza el cableado de la escritura de ECG al UPS con TKEO + esta compuerta tal cual?\n\n"
        "  SI, autorizo tal cual  ___\n\n"
        "  SI, pero primero recalibrar la fórmula de calidad para TKEO  ___\n\n"
        "  SI, pero con estas condiciones adicionales: ______________________________\n\n"
        "  NO todavía, falta: _________________________________________________________\n",
        fontsize=10, family='monospace', va='top')
    plt.axis('off')
    pdf.savefig(fig)
    plt.close(fig)

print(f"PDF guardado en: {out_path}")
