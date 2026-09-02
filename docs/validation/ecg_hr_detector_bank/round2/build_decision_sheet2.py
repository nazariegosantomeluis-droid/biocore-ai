import os
from fpdf import FPDF

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


class DecisionSheet(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f'Pagina {self.page_no()} -- Banco de validacion detector HR de ECG, 2a ronda -- Capa 2 / Capa 5B', align='C')


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


def critical_box(pdf, text):
    pdf.set_fill_color(254, 226, 226)
    pdf.set_draw_color(220, 38, 38)
    pdf.set_text_color(153, 27, 27)
    pdf.set_font('Helvetica', 'B', 10)
    x, y = pdf.get_x(), pdf.get_y()
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

    h1(pdf, "Hoja de decision, 2a ronda -- Detector de HR de ECG reparado")
    body(pdf,
         "Segunda tanda tras el rechazo del detector original. Se implemento la Solucion 1 (bidireccional + "
         "periodo refractario, la que usted recomendo) y la compuerta de calidad estructurada. El resultado NO "
         "es una victoria limpia -- ayuda mucho en algunos registros y empeora otros de forma seria. Este "
         "documento presenta ambos lados sin suavizarlos.")

    critical_box(pdf,
        "HALLAZGO CRITICO: la compuerta de calidad ACEPTO el registro 217 (marcapasos) con confianza=0.70 "
        "mientras que la sensibilidad REAL contra ground truth era de solo 0.147 (detecta 15% de los latidos "
        "reales). La metrica de confianza (que no usa ground truth, por diseno -- tiene que funcionar en "
        "produccion sobre PTB-XL) fue enganada por la regularidad mecanica de las espigas de marcapasos. "
        "Mecanismo exacto: la supresion refractaria elige la deflexion de MAYOR amplitud absoluta dentro de "
        "cada QRS ancho -- en el 217 eso es la parte negativa del complejo, no la posicion que el cardiologo "
        "anoto (la positiva). El desfase resultante (~60-70ms) cae justo fuera de la tolerancia de "
        "emparejamiento (+-50ms), asi que casi ningun latido cuenta como acierto pese a que el conteo total de "
        "picos es parecido al de latidos reales. Esta compuerta, tal como esta disenada HOY, NO es segura para "
        "producir un HR clinico sobre ritmos con marcapasos.")

    h2(pdf, "Que funciono de verdad (mejoras reales, confirmadas contra ground truth)")
    body(pdf,
        "- Registro 108 (bajo voltaje, QRS predominante negativo): sensibilidad 0.16-0.18 (viejo) -> 0.94-0.97 "
        "(reparado). El detector ahora SI encuentra estos latidos.\n"
        "- Registro 207 (fibrilacion/flutter ventricular + ruido): sensibilidad 0.28-0.36 -> 0.75-0.84. Mejora "
        "grande en el caso mas extremo del banco.\n"
        "- Registro 210 (fibrilacion auricular sostenida, nuevo en esta ronda): mejora modesta y consistente en "
        "sensibilidad y VPP en todo el barrido.\n"
        "- Registro 233 (ruidoso, la prueba del espejismo): sensibilidad 0.86 -> 0.997. A prominence_factor=2.0 "
        "la compuerta ACEPTA con sensibilidad=0.997 y VPP=0.963 -- aqui la compuerta acierta: solo acepta donde "
        "la calidad real es alta, rechaza en el resto del barrido.")

    h2(pdf, "Que empeoro (regresiones reales, no ruido de medicion)")
    body(pdf,
        "- Registro 217 (marcapasos): sensibilidad 0.94-1.0 (viejo, YA era buena) -> 0.147 (reparado) -- "
        "colapso severo. Ver la caja roja arriba para el mecanismo.\n"
        "- Registro 118 (bloqueo de rama derecha): sensibilidad 0.99 (viejo) -> 0.64-0.67 (reparado) -- misma "
        "familia de problema: QRS ancho, la supresion por amplitud elige mal.\n"
        "- Registros 100/103 (limpios): a prominence_factor bajo (0.3-0.7), el VPP EMPEORA (mas falsos "
        "positivos por deflexiones negativas espurias); se recupera igualando al viejo desde 1.5.\n"
        "- Registro 117: la sensibilidad YA era 1.0 con el detector viejo (hallazgo revisado de la 1a ronda -- "
        "el punto positivo que el viejo detector marcaba SI caia dentro de la tolerancia de 50ms del QRS "
        "anotado, pese a la lectura visual de la 1a ronda). El detector reparado no mejora sensibilidad y "
        "empeora el VPP (mas deflexiones negativas espurias).")

    pdf.add_page()
    h2(pdf, "Interpretacion honesta")
    body(pdf,
        "La Solucion 1 resuelve el problema que la motivo (QRS ciego a una polaridad) en los registros donde "
        "ese era el problema real (108, 207). Pero introduce un problema NUEVO en QRS anchos con componentes "
        "de amplitud comparable en ambas polaridades (marcapasos, bloqueos de rama): la regla de desempate "
        "'mayor amplitud absoluta' no siempre elige el punto que el cardiologo considera el latido. Esto NO se "
        "corrigio en esta tanda -- se instrumento (columna 'Competencias bifasicas' en la tabla, circulos "
        "naranjas en las tiras) para que usted lo vea y decida si la regla de desempate necesita cambiar (p.ej. "
        "preferir el componente MAS CERCANO EN TIEMPO a done el detector viejo ya acertaba, en vez del de mayor "
        "amplitud).")

    h1(pdf, "Las 4 preguntas para el experto, 2a ronda")

    h2(pdf, "1. Deteccion de QRS negativos")
    body(pdf, "¿El detector reparado detecta correctamente los QRS negativos ahora? Nota: 108 mejoro mucho; "
              "117 no mejoro en sensibilidad (ya estaba bien) pero empeoro en VPP -- ¿es este balance aceptable?")
    answer_box(pdf, lines=3)

    h2(pdf, "2. La supresion refractaria")
    body(pdf, "¿La supresion por 'mayor amplitud absoluta' acierta en los latidos bifasicos marcados, o elige "
              "mal sistematicamente en QRS anchos (marcapasos, bloqueos de rama)? Ver el hallazgo critico del "
              "registro 217 arriba. ¿Prefiere otro criterio de desempate?")
    answer_box(pdf, lines=4)

    h2(pdf, "3. Parametro y criterio de aceptacion")
    body(pdf, "¿Que prominence_factor bendice sobre el detector reparado? ¿Que sensibilidad/VPP minimos exige "
              "por registro? Dado el hallazgo critico, ¿la compuerta de calidad actual (regularidad RR + "
              "consistencia de amplitud, sin ground truth) es suficiente, o necesita una senal adicional que "
              "detecte especificamente ritmos de marcapasos/QRS anchos antes de confiar en la confianza sola?")
    answer_box(pdf, lines=5)

    h2(pdf, "4. Conjunto de registros")
    body(pdf, "Se anadieron 210 (FA sostenida, 98% de la duracion), 217 (marcapasos) y 100-V5 (misma senal, "
              "otra derivacion) tras su primera revision. ¿Basta este conjunto de 11, o falta algo mas antes de "
              "bendecir cualquier parametro?")
    answer_box(pdf, lines=3)

    h2(pdf, "Archivos de esta ronda")
    body(pdf,
         "- tiras_ecg_2a_ronda.pdf: 11 registros, detector viejo vs reparado, competencias bifasicas marcadas.\n"
         "- tabla_comparativa_2a_ronda.xlsx: 66 filas (11 registros x 6 prominence_factor), viejo vs reparado, "
         "confianza y decision de la compuerta; segunda hoja aislando el falso-aceptado critico.\n"
         "- Este documento.")

    out_path = os.path.join(OUT_DIR, 'hoja_decision_experto_2a_ronda.pdf')
    pdf.output(out_path)
    print(f"Hoja de decision (2a ronda) guardada en: {out_path}")


if __name__ == '__main__':
    build()
