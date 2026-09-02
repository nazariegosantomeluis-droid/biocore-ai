import os
from fpdf import FPDF

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


class DecisionSheet(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f'Pagina {self.page_no()} -- Banco de validacion detector HR de ECG, 3a ronda -- Capa 2 / Capa 5B', align='C')


def h1(pdf, text, color=(20, 20, 20)):
    pdf.set_font('Helvetica', 'B', 15)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 8, text)
    pdf.ln(1)


def h2(pdf, text, color=(29, 78, 216)):
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 7, text)
    pdf.ln(1)


def body(pdf, text):
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 5.5, text)
    pdf.ln(2)


def good_box(pdf, text):
    pdf.set_fill_color(198, 246, 213)
    pdf.set_text_color(20, 83, 45)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.multi_cell(0, 5.5, text, border=1, fill=True)
    pdf.ln(3)
    pdf.set_text_color(30, 30, 30)


def critical_box(pdf, text):
    pdf.set_fill_color(254, 226, 226)
    pdf.set_text_color(153, 27, 27)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.multi_cell(0, 5.5, text, border=1, fill=True)
    pdf.ln(3)
    pdf.set_text_color(30, 30, 30)


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

    h1(pdf, "Hoja de decision, 3a ronda -- hacia la bendicion final")
    body(pdf,
         "Tercera tanda: implementa el veredicto del experto sobre la frontera clinica (BRD dentro, marcapasos "
         "fuera). Parte A (desempate por pendiente) funciono segun lo esperado. Parte B (bandera de marcapasos) "
         "NO funciono -- se reporta la evidencia completa en vez de forzar un resultado.")

    good_box(pdf,
        "PARTE A -- EXITO: el registro 118 (bloqueo de rama derecha) recupera sensibilidad de 0.64 (ronda 2, "
        "desempate por amplitud) a 0.991 (ronda 3, desempate por pendiente maxima |dv/dt|) -- por encima del "
        "objetivo de 0.95 y de la sensibilidad original del detector viejo (0.99). VPP tambien mejora: 0.634 -> "
        "0.960. El mecanismo: en QRS anchos/aberrantes, la muesca de mayor amplitud dentro del complejo no "
        "siempre es el punto que el cardiologo marca -- la pendiente maxima si lo es, consistentemente. "
        "Verificado sin regresion en los registros que ya iban bien: 100/103 identicos, 233 se mantiene fuerte "
        "(sens 0.997). 108 tiene una caida menor (sens amplitud 0.96 -> pendiente 0.90) -- sigue siendo una "
        "mejora enorme frente al detector original (0.16-0.18).")

    critical_box(pdf,
        "PARTE B -- RESULTADO NEGATIVO, documentado con evidencia (no forzado): se implemento la bandera de "
        "marcapasos exactamente como se especifico (picos de pendiente extrema, angostos, aislados). Barrido "
        "de umbral (z de 10 a 30) sobre los 11 registros: a umbrales bajos (z=12-15), el registro 118 (BRD, que "
        "NUNCA debe marcarse como marcapasos) dispara MAS eventos 'espiga' que el propio 217 (118: 11-32 "
        "eventos vs 217: 1-10). A umbrales altos (z=20-25), 217 cae a 0 eventos -- deja de detectarse del todo. "
        "No existe una zona intermedia limpia: 108/207/228/233/210 (ruidosos o con ectopia) producen sus "
        "propios eventos de pendiente extrema, indistinguibles de una espiga real por amplitud/anchura/"
        "aislamiento solos. Inspeccion visual directa de 5 ubicaciones de maxima pendiente en el registro 217 "
        "(ambas derivaciones disponibles, MLII y V1) no muestra una espiga aislada separable del QRS -- solo "
        "una deflexion suave y fisiologica. La bandera NO esta cableada a la compuerta -- cablearla habria "
        "excluido BRD (violando el mandato de la Parte A) o dejado pasar el marcapasos (violando el mandato de "
        "la Parte B), segun el umbral elegido.")

    pdf.add_page()
    h2(pdf, "El insight incomodo que la Parte A destapo")
    body(pdf,
        "Con el detector reparado (pendiente), el registro 217 ahora se detecta con precision genuina: "
        "sensibilidad 0.94, VPP 0.89 a prominence_factor=2.0 -- la compuerta de calidad genérica lo ACEPTARIA "
        "con confianza 0.63, porque el detector ya no se equivoca. Esto no es un fallo de deteccion como en la "
        "2a ronda -- es un ritmo estimulado detectado con precision, pero clinicamente invalido para "
        "biometria autonoma de todas formas. La mejora de la Parte A hace la Parte B MAS urgente, no menos: "
        "sin una bandera de categoria de ritmo que funcione, un marcapasos bien detectado pasaria la compuerta "
        "de calidad generica sin ningun problema.")

    h2(pdf, "Parte C -- verificacion de la leccion transversal")
    body(pdf,
        "Con el detector de pendiente, no aparecio ningun NUEVO caso de 'confianza alta, deteccion mala' en el "
        "banco (la mejora de deteccion de la Parte A tambien limpio ese tipo especifico de espejismo en todos "
        "los registros probados). PERO surgio una pregunta analoga, no resuelta: el registro 210 (fibrilacion "
        "auricular sostenida) se detecta con precision (sensibilidad ~1.0, VPP 0.94-0.99) y la compuerta lo "
        "ACEPTA a prominence_factor>=1.5. El mismo principio que excluye el marcapasos ('solo son validos los "
        "ritmos cuyo R-R gobierna el sistema nervioso autonomo') podria aplicar tambien a la FA: en fibrilacion "
        "auricular, el R-R lo determina la conduccion caotica del nodo AV, no la modulacion autonomica del "
        "nodo sinusal -- HRV calculada sobre FA mide algo distinto (refractariedad del nodo AV), no tono "
        "autonomico. No se resuelve aqui -- es la pregunta abierta 4 de esta hoja.")

    h1(pdf, "Las 4 preguntas para la bendicion final")

    h2(pdf, "1. Parte A -- BRD recuperado")
    body(pdf, "¿El fix de pendiente recupero el BRD (118) a un nivel aceptable (0.991 sensibilidad, 0.960 VPP)? "
              "¿Algun otro registro se beneficio o regreso de forma que le preocupe?")
    answer_box(pdf, lines=3)

    h2(pdf, "2. Parte B -- bandera de marcapasos, resultado negativo")
    body(pdf, "Dada la evidencia (barrido de umbral sin zona limpia, inspeccion visual sin espiga separable): "
              "¿autoriza continuar sin deteccion automatica de marcapasos por ahora (excluyendo manualmente "
              "registros conocidos como 217), o prefiere una via distinta -- p.ej. ancho de QRS como señal "
              "secundaria (con el riesgo de confundir con BRD, ya evidenciado), metadatos del dispositivo "
              "(ESP32/dataset) en vez de la forma de onda, o un dataset con mayor fidelidad de captura?")
    answer_box(pdf, lines=5)

    h2(pdf, "3. La bendicion que desbloquea el cableado")
    body(pdf, "¿Que prominence_factor final autoriza sobre el detector de pendiente? ¿Que QUALITY_THRESHOLD? "
              "¿Que sensibilidad/VPP minimos por registro? Dado que Parte B no cierra el caso de marcapasos, "
              "¿el cableado a ECG->UPS procede ya (con marcapasos excluido manualmente/fuera de alcance de la "
              "automatizacion por ahora) o espera a resolver la Parte B primero?")
    answer_box(pdf, lines=5)

    h2(pdf, "4. Fibrilacion auricular -- ¿tambien fuera de alcance?")
    body(pdf, "¿El mismo principio autonomico que excluye el marcapasos aplica a la FA sostenida (210)? Si es "
              "asi, es una categoria adicional a excluir (mismo problema de deteccion-de-categoria que la Parte "
              "B, no resuelto aqui tampoco). Si no, ¿por que la FA si es valida para HRV en este contexto?")
    answer_box(pdf, lines=4)

    h2(pdf, "Archivos de esta ronda")
    body(pdf,
         "- tiras_ecg_3a_ronda.pdf: 11 registros, amplitud (r2) vs pendiente (r3), 118 y 217 con anotaciones "
         "especiales.\n"
         "- tabla_comparativa_3a_ronda.xlsx: 66 filas + hoja de recuperacion de 118 + hoja de evidencia del "
         "barrido de la Parte B.\n"
         "- Este documento.")

    out_path = os.path.join(OUT_DIR, 'hoja_decision_experto_3a_ronda.pdf')
    pdf.output(out_path)
    print(f"Hoja de decision (3a ronda) guardada en: {out_path}")


if __name__ == '__main__':
    build()
