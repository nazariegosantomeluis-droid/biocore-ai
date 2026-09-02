import os
from fpdf import FPDF

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


class DecisionSheet(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f'Página {self.page_no()} -- Banco de validación detector HR de ECG -- Capa 2 / Capa 5B', align='C')


def h1(pdf, text):
    pdf.set_font('Helvetica', 'B', 15)
    pdf.set_text_color(20, 20, 20)
    pdf.multi_cell(0, 8, text)
    pdf.ln(1)


def h2(pdf, text):
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(29, 78, 216)
    pdf.multi_cell(0, 7, text)
    pdf.ln(1)


def body(pdf, text):
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 5.5, text)
    pdf.ln(2)


def answer_box(pdf, lines=4):
    pdf.set_draw_color(180, 180, 180)
    x, y = pdf.get_x(), pdf.get_y()
    h = 6 * lines
    pdf.rect(x, y, 180, h)
    pdf.set_y(y + h + 4)


def build():
    pdf = DecisionSheet()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    h1(pdf, "Hoja de decisión -- Banco de validación del detector de HR de ECG")
    body(pdf,
         "Preparado por Claude Code para revisión del validador humano -- mismo rol que jugó validando el "
         "detector de BBB (leyó 50 ECGs, encontró 2 erratas de PTB-XL). Este documento no toma decisiones: "
         "presenta la evidencia y pide 3 juicios clínicos concretos. El código de producción de ECG Lab NO "
         "se tocó en este mini-arco.")

    body(pdf,
         "Contexto: la Fase 2.4 (integración estrecha labs->UPS) dejó ECG diferido porque su heart_rate "
         "fiable requeria un prominence_factor no establecido en el repo. Este banco corre el detector real "
         "del repo (clinical.ecg_analyzer.ECGAnalyzer.detect_r_peaks()) sobre 8 registros MIT-BIH reales, "
         "contra las anotaciones de cardiologos (ground truth objetivo, PhysioNet .atr), en 6 valores de "
         "prominence_factor (0.3 default, 0.5, 0.7, 1.0, 1.5, 2.0).")

    h2(pdf, "Hallazgo principal (no esperado al iniciar el banco)")
    body(pdf,
         "Los registros 117 y 108 comparten una causa raiz: en esta derivacion (MLII), el QRS es "
         "predominantemente NEGATIVO. ECGAnalyzer.detect_r_peaks() usa scipy.signal.find_peaks(), que solo "
         "busca maximos POSITIVOS -- el algoritmo nunca ve el latido real en estos registros, sin importar "
         "el prominence_factor (VPP tope ~0.53 en el 117; sensibilidad 0.15-0.18 en el 108 en TODO el "
         "barrido). Esto no es un problema de umbral -- es una limitacion estructural del detector. Ver las "
         "tiras de estos dos registros en el PDF adjunto: el triangulo rojo (pico detectado) marca "
         "sistematicamente una onda positiva secundaria, nunca la X verde (el verdadero QRS, negativo).")

    h2(pdf, "Otros hallazgos")
    body(pdf,
         "- Registro 207 (fibrilacion/flutter ventricular + ruido): sensibilidad nunca supera ~0.36 en "
         "ningun prominence_factor probado -- caso fuera del alcance de este detector, cualquiera sea el "
         "parametro.\n"
         "- Registro 233 (ruidoso): el ERROR de HR promedio se ve enganosamente bueno (<3bpm en casi todo el "
         "barrido) pese a sensibilidad/VPP imperfectos -- falsos positivos y negativos se cancelan en el "
         "promedio. Advertencia: evaluar solo por error de HR promedio puede ocultar un detector poco "
         "fiable.\n"
         "- Registros limpios (100, 103) y BRD (118): prominence_factor=1.0 da resultados excelentes "
         "(sensibilidad/VPP >=0.98, error de HR <1bpm).\n"
         "- Registro 228 (arritmia real, PVCs): 1.0 minimiza el error de HR (0.3bpm) pero sensibilidad/VPP "
         "quedan en ~0.85-0.87 -- umbrales mas altos pierden latidos ectopicos de menor amplitud.")

    pdf.add_page()
    h1(pdf, "Las 3 preguntas para el experto")

    h2(pdf, "1. Conjunto de registros")
    body(pdf,
         "El conjunto (100, 103, 117, 108, 228, 207, 233, 118) se eligio por cribado cuantitativo propio "
         "(proporcion T/R, carga arritmica, voltaje QRS, ruido) sobre 23 registros candidatos de MIT-BIH -- "
         "PROVISIONAL, no una seleccion clinica experta. ¿Cubre las morfologias que de verdad rompen "
         "detectores de R, o falta alguna (p.ej. fibrilacion auricular sostenida, marcapasos/217, otras "
         "derivaciones ademas de MLII)?")
    answer_box(pdf, lines=4)

    h2(pdf, "2. Ground truth")
    body(pdf,
         "Las anotaciones .atr de MIT-BIH (picos de latido marcados por cardiologos, disponibles via "
         "wfdb.rdann) se usaron como referencia objetiva. PTB-XL NO tiene anotaciones de latido descargables "
         "(confirmado: 404 al pedir el .atr) -- solo codigos diagnosticos a nivel de registro. ¿Las "
         "anotaciones de MIT-BIH bastan como referencia para decidir el parametro, o hace falta que usted "
         "marque el HR a mano en algun caso (p.ej. para confirmar un limite dudoso)?")
    answer_box(pdf, lines=4)

    h2(pdf, "3. Criterio de aceptacion")
    body(pdf,
         "¿Que margen de error de HR (o que sensibilidad/VPP minimos) es tolerable para que ECG Lab escriba "
         "heart_rate al gemelo? ¿Que debe pasar con un registro que cae fuera de ese margen -- declinar la "
         "escritura de ese registro especifico, o un umbral de calidad de senal previo (p.ej. rechazar si "
         "VPP<X)? ¿Bendice prominence_factor=1.0 como el valor a usar, otro valor, o considera que el "
         "detector necesita un cambio estructural (p.ej. buscar tambien picos negativos, ver el hallazgo "
         "principal) antes de que CUALQUIER parametro sea aceptable para escribir al UPS?")
    answer_box(pdf, lines=6)

    h2(pdf, "Archivos de este banco")
    body(pdf,
         "- tiras_ecg_picos_marcados.pdf: 8 registros x 2 parametros (0.3 y 1.0), picos detectados vs "
         "anotaciones, con portada y leyenda.\n"
         "- tabla_comparativa_detector_hr.xlsx: 48 filas (8 registros x 6 prominence_factor) con HR, error, "
         "sensibilidad, VPP, TP/FP/FN; segunda hoja de contraste 0.3 vs 1.0 con veredicto por registro.\n"
         "- Este documento (hoja_decision_experto.pdf).")

    out_path = os.path.join(OUT_DIR, 'hoja_decision_experto.pdf')
    pdf.output(out_path)
    print(f"Hoja de decision guardada en: {out_path}")


if __name__ == '__main__':
    build()
