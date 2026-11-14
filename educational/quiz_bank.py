"""Bancos de preguntas de los cuestionarios, con la fuente de cada respuesta (Art. I).

Un solo lugar para revisar el contenido clínico de los cuestionarios: Academia
(`learning_engine.generate_quiz`), la pestaña 12 Derivaciones del ECG Lab y el EEG
Neuro Lab. Cada pregunta trae la opción correcta, una explicación y la fuente de
donde sale, leída del documento original el 2026-11-14 (ver CHANGELOG.md). Cuando
la respuesta describe la propia app y no la clínica, la fuente lo dice.

Convención: la opción correcta se escribe PRIMERO (`answer=0`), así un índice mal
puesto no puede pasar desapercibido; el orden en pantalla lo decide
`display_choices()`, con semilla fija (no cambia entre recargas de Streamlit) y con
el lugar de la correcta repartido por igual dentro de cada banco
(`balance_positions`). `tests/test_quiz_bank.py` vigila todo esto.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence


def stable_shuffle(items: Sequence, seed_text: str) -> list:
    """Baraja `items` siempre igual para el mismo `seed_text`."""
    seed = int.from_bytes(hashlib.sha256(seed_text.encode("utf-8")).digest()[:8], "big")
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    return shuffled


def numeric_choices(correct: int, step: int, seed_text: str, minimum: int = 0) -> List[int]:
    """Opciones numéricas ordenadas: la correcta y 3 distractores separados por `step`.

    Antes los distractores eran simétricos y la correcta salía casi siempre en el
    segundo lugar. Aquí la semilla decide cuántos distractores van por debajo, así
    que el lugar de la correcta cambia de una señal a otra.
    """
    below = [correct - step * i for i in (1, 2, 3) if correct - step * i >= minimum]
    n_below = random.Random(seed_text).randint(0, len(below))
    above = [correct + step * i for i in range(1, 4 - n_below)]
    return sorted(below[:n_below] + [correct] + above)


@dataclass
class QuizQuestion:
    prompt: str
    choices: List[str]
    answer: int  # índice de la opción correcta en `choices` (en los bancos de aquí, siempre 0)
    category: str = "General"
    explanation: str = ""
    source: str = ""
    display_position: Optional[int] = None  # lugar en pantalla de la correcta; lo fija `balance_positions`

    @property
    def correct_choice(self) -> str:
        return self.choices[self.answer]

    def display_choices(self) -> List[str]:
        """Las opciones en el orden en que se muestran."""
        others = stable_shuffle([c for i, c in enumerate(self.choices) if i != self.answer], self.prompt)
        position = self.display_position
        if position is None:
            digest = hashlib.sha256(self.prompt.encode("utf-8")).digest()
            position = int.from_bytes(digest[8:16], "big") % len(self.choices)
        others.insert(position, self.correct_choice)
        return others

    def is_correct(self, selected: Optional[str]) -> bool:
        """Sin respuesta (`None`) no cuenta como acierto."""
        return selected is not None and selected == self.correct_choice


def balance_positions(bank: List[QuizQuestion], seed_text: str) -> List[QuizQuestion]:
    """Reparte por igual el lugar en pantalla de la opción correcta dentro de un banco.

    Cada lugar recibe la misma cantidad de respuestas correctas (± 1), en un orden
    barajado con semilla fija: ni el primero ni ningún otro delata la respuesta."""
    slots = [i % len(q.choices) for i, q in enumerate(bank)]
    random.Random(seed_text).shuffle(slots)
    for question, slot in zip(bank, slots):
        question.display_position = slot % len(question.choices)
    return bank


# --- Fuentes (leídas del documento original el 2026-11-14) -------------------------------------
# Las del ECG viven en `clinical/ecg_references.py` (una sola copia; también las usa el analizador de 12
# derivaciones).
from clinical.ecg_references import (  # noqa: E402
    AL_KHATIB_2017, BYRNE_2023, DREW_2010, KLIGFIELD_2007, KUSUMOTO_2018, RAUTAHARJU_2009, SCHULZ_MENGER_2025,
    SOKOLOW_LYON_1949, SURAWICZ_2009, VAN_GELDER_2024, WAGNER_2009,
)

BIGA_ANATOMY = (
    "Biga LM, et al. Anatomy & Physiology, cap. 19, «Conduction system of the heart and the ECG». "
    "Libro de texto abierto, licencia CC BY-SA 4.0"
)
ALLEN_2007 = (
    "Allen J. Photoplethysmography and its application in clinical physiological measurement. "
    "Physiol Meas 2007;28(3):R1–R39. doi:10.1088/0967-3334/28/3/R01"
)
KANE_2017 = (
    "Kane N, Acharya J, Beniczky S, et al. A revised glossary of terms most commonly used by clinical "
    "electroencephalographers and updated proposal for the report format of the EEG findings. Revision 2017. "
    "Clin Neurophysiol Pract 2017;2:170–185. doi:10.1016/j.cnp.2017.07.002"
)
HIRSCH_2021 = (
    "Hirsch LJ, Fong MWK, et al. American Clinical Neurophysiology Society's Standardized Critical Care EEG "
    "Terminology: 2021 Version. J Clin Neurophysiol 2021;38(1):1–29"
)
UNIT_DEFINITION = "Definición por unidades (60 s por minuto ÷ segundos por latido); no necesita cita"
ECG12_LAB_DESCRIPTION = (
    "Descripción de este laboratorio (pestaña 12 Derivaciones de BIOCORE): `twelve_lead_measure` mide sobre el "
    "latido mediano y compara con criterios publicados; no es un modelo entrenado"
)


# --- Academia (Learning Hub → Academia Clínica) -------------------------------------------------
# Mismo orden y categorías que el banco anterior (el nivel básico toma las primeras de cada lección).
ACADEMIA_QUESTIONS: List[QuizQuestion] = balance_positions([
    QuizQuestion(
        "Por convención docente, la FC del adulto en reposo se toma como normal entre 60 y 100 lpm. "
        "¿Con qué valor define la bradicardia sinusal la guía ACC/AHA/HRS 2018?",
        ["Frecuencia sinusal < 50 lpm", "Frecuencia sinusal < 60 lpm", "Frecuencia sinusal < 40 lpm",
         "Frecuencia sinusal < 70 lpm"],
        0, category="ECG Básico",
        explanation="La guía de 2018 (tabla 3) define la bradicardia sinusal como una frecuencia sinusal < 50 lpm. "
                    "El corte de 60 lpm es la convención docente, y es el que usan los laboratorios de BIOCORE.",
        source=KUSUMOTO_2018 + " (tabla 3)",
    ),
    QuizQuestion(
        "¿Qué representa el complejo QRS?",
        ["La despolarización de los ventrículos", "La repolarización de los ventrículos",
         "La despolarización de las aurículas", "La contracción del músculo esquelético"],
        0, category="ECG Básico",
        explanation="El QRS es la despolarización ventricular. La onda P es la despolarización auricular y la onda T, "
                    "la repolarización ventricular.",
        source=BIGA_ANATOMY,
    ),
    QuizQuestion(
        "Durante un infarto con elevación del ST, ¿qué puede significar una depresión del ST en V1 y V2?",
        ["Un infarto posterior o lateral con elevación del ST", "Un bloqueo AV de primer grado",
         "Nada: el ST de V1 y V2 no cambia con la isquemia",
         "Una oclusión proximal de la descendente anterior, que deprime el ST en V1–V4"],
        0, category="ECG 12-derivaciones",
        explanation="La parte VI señala que la depresión del ST en V1 y V2 es una manifestación común de un infarto "
                    "posterior o lateral con elevación del ST, y recomienda conservar el término «posterior» para "
                    "describirla. La oclusión proximal de la descendente anterior ELEVA el ST en V1–V4, I, aVL y a "
                    "menudo aVR.",
        source=WAGNER_2009,
    ),
    QuizQuestion(
        "En una persona con dolor torácico agudo, ¿qué diagnóstico de trabajo plantea una elevación persistente "
        "del ST?",
        ["Infarto agudo de miocardio con elevación del ST (IAMCEST)",
         "Angina crónica estable, que no requiere estudio urgente",
         "Crisis hipertensiva sin daño miocárdico",
         "Repolarización precoz benigna, sin más estudio"],
        0, category="ECG Básico",
        explanation="La guía ESC 2023 llama IAMCEST al diagnóstico de trabajo de quien tiene dolor torácico agudo y "
                    "elevación persistente del ST (o sus equivalentes): elevación nueva del ST en el punto J en al "
                    "menos dos derivaciones contiguas. La prioridad es la reperfusión lo antes posible.",
        source=BYRNE_2023 + " (secciones 3.2 y 3.2.1)",
    ),
    QuizQuestion(
        "¿Qué mide el intervalo PR?",
        ["Del inicio de la onda P al inicio del QRS", "La duración del complejo QRS",
         "Del final del QRS hasta el inicio de la onda T", "Del inicio del QRS al final de la onda T"],
        0, category="ECG Básico",
        explanation="El PR va del inicio de la onda P al inicio del QRS. En el adulto, un PR < 120 ms en ritmo "
                    "sinusal es criterio de preexcitación y uno > 200 ms define el bloqueo AV de primer grado.",
        source=f"{BIGA_ANATOMY}; {SURAWICZ_2009}; {KUSUMOTO_2018} (tabla 3)",
    ),
    QuizQuestion(
        "¿Qué es una PVC?",
        ["Un complejo ventricular prematuro", "Una taquicardia supraventricular por reentrada nodal",
         "Un bloqueo auriculoventricular de segundo grado", "Una fibrilación auricular con respuesta rápida"],
        0, category="Arritmias",
        explanation="PVC es la sigla en inglés de complejo ventricular prematuro (extrasístole ventricular). La guía "
                    "AHA/ACC/HRS 2017 lo pone en el extremo leve del espectro de las arritmias ventriculares, que "
                    "llega hasta la fibrilación ventricular.",
        source=AL_KHATIB_2017,
    ),
    QuizQuestion(
        "¿Cómo se calcula la FC (en lpm) a partir del intervalo RR?",
        ["60 / RR medio en segundos", "RR medio en segundos / 60", "60 × RR medio en segundos",
         "Suma de los RR / número de latidos"],
        0, category="ECG Básico",
        explanation="Un minuto tiene 60 s; si cada latido dura RR segundos, caben 60 / RR latidos por minuto. "
                    "Ejemplo: RR = 0.8 s → 75 lpm.",
        source=UNIT_DEFINITION,
    ),
    QuizQuestion(
        "¿Qué ritmo del EEG se ve mejor con los ojos cerrados, en relajación física y relativa inactividad mental?",
        ["El ritmo alfa posterior (8–13 Hz)", "Las ondas delta del sueño profundo",
         "El ritmo beta fronto-central (14–30 Hz)", "Los husos de sueño (11–16 Hz)"],
        0, category="Otras señales",
        explanation="El glosario IFCN 2017 define el ritmo alfa: 8–13 Hz, en vigilia, sobre las regiones posteriores; "
                    "se ve mejor con los ojos cerrados y se bloquea o atenúa con la atención (sobre todo visual) y el "
                    "esfuerzo mental.",
        source=KANE_2017,
    ),
    QuizQuestion(
        "Una elevación del ST solo en II, III y aVF puede deberse a la oclusión de:",
        ["La coronaria derecha o la circunfleja", "Solo la descendente anterior",
         "Ninguna arteria: II, III y aVF no muestran isquemia", "El tronco de la coronaria izquierda, siempre"],
        0, category="ECG 12-derivaciones",
        explanation="La parte VI indica que un infarto inferior con elevación del ST solo en II, III y aVF puede "
                    "deberse a la oclusión de la coronaria derecha o de la circunfleja.",
        source=WAGNER_2009,
    ),
    QuizQuestion(
        "¿Qué hallazgo del ECG apoya una hipertrofia ventricular izquierda?",
        ["S en V1 + R en V5 o V6 ≥ 35 mm", "Voltajes bajos en todas las precordiales",
         "Elevación difusa del ST con descenso del PR", "Onda delta con PR corto"],
        0, category="ECG 12-derivaciones",
        explanation="El criterio de Sokolow-Lyon pide S en V1 + R en V5 o V6 ≥ 35 mm, o R en aVL ≥ 11 mm. La elevación "
                    "difusa del ST con descenso del PR es un criterio de pericarditis, y la onda delta con PR corto, "
                    "de preexcitación.",
        source=f"{SOKOLOW_LYON_1949}; {SCHULZ_MENGER_2025}; {SURAWICZ_2009}",
    ),
    QuizQuestion(
        "¿Cuál de estas condiciones causa bradicardia?",
        ["El bloqueo AV completo", "El hipertiroidismo no tratado", "La fiebre", "La deshidratación grave"],
        0, category="Arritmias",
        explanation="La guía ACC/AHA/HRS 2018 trata la bradicardia junto con los trastornos de la conducción; en el "
                    "bloqueo AV completo (de tercer grado) no hay evidencia de conducción auriculoventricular.",
        source=KUSUMOTO_2018 + " (tabla 3)",
    ),
    QuizQuestion(
        "Un eje del QRS entre −45° y −90°, con qR en aVL y QRS < 120 ms, cumple criterios de:",
        ["Bloqueo fascicular anterior izquierdo", "Bloqueo de rama derecha completo",
         "Bloqueo fascicular posterior izquierdo", "Eje normal del adulto"],
        0, category="ECG 12-derivaciones",
        explanation="La parte III define el bloqueo fascicular anterior izquierdo con eje frontal entre −45° y −90°, qR "
                    "en aVL, tiempo al pico de R en aVL ≥ 45 ms y QRS < 120 ms. El posterior lleva el eje entre +90° "
                    "y +180°.",
        source=SURAWICZ_2009,
    ),
    QuizQuestion(
        "¿Qué patrón corresponde a un bloqueo de rama derecha completo en el adulto?",
        ["QRS ≥ 120 ms, rsR′ en V1–V2 y S ancha en I y V6", "QRS ≥ 120 ms con R ancha y sin onda q en I, aVL y V6",
         "PR < 120 ms con onda delta y QRS ancho en sinusal", "QRS de 110 a 119 ms con rsR′ en V1"],
        0, category="Arritmias",
        explanation="Criterios de la parte III: QRS ≥ 120 ms; rsr′, rsR′ o rSR′ en V1 o V2; S más larga que la R o "
                    "> 40 ms en I y V6. Deben estar los tres. Con QRS de 110 a 120 ms se habla de bloqueo incompleto; "
                    "R ancha en I y V6 con QRS ≥ 120 ms es el patrón del bloqueo de rama izquierda.",
        source=SURAWICZ_2009,
    ),
    QuizQuestion(
        "Ante un IAMCEST con síntomas de 12 h o menos, ¿qué recomienda la guía ESC 2023?",
        ["Reperfusión: ICP primaria si es posible en < 120 min desde el diagnóstico; si no, fibrinólisis",
         "Esperar el resultado de la troponina antes de decidir la reperfusión",
         "Observar 24 h con ECG seriados y decidir la reperfusión según la evolución",
         "Fibrinólisis solo si los síntomas llevan más de 12 h de evolución"],
        0, category="ECG Básico",
        explanation="Tabla de recomendaciones 4 (clase I): reperfusión en todo diagnóstico de trabajo de IAMCEST con "
                    "síntomas de ≤ 12 h; ICP primaria si el tiempo previsto del diagnóstico a la ICP es < 120 min y, "
                    "si no puede hacerse a tiempo, fibrinólisis dentro de las 12 h del inicio de los síntomas, sin "
                    "contraindicaciones.",
        source=BYRNE_2023 + " (tabla de recomendaciones 4)",
    ),
    QuizQuestion(
        "¿Cómo se reconoce la fibrilación auricular en el ECG?",
        ["Sin ondas P discernibles y regulares, con intervalos RR sin patrón",
         "Ondas P normales antes de cada QRS, con RR regulares",
         "Ondas auriculares regulares en «dientes de sierra», con conducción fija",
         "PR < 120 ms con onda delta, en ritmo sinusal"],
        0, category="Arritmias",
        explanation="La guía ESC 2024 describe la FA en el ECG como ausencia de ondas P discernibles y regulares, con "
                    "activación ventricular irregular (sin patrón en los RR). Un ECG de 12 derivaciones dura 10 s; con "
                    "dispositivos de una o varias derivaciones, el consenso ha sido pedir 30 s o más.",
        source=VAN_GELDER_2024 + " (secciones 3.1 y 3.2)",
    ),
    QuizQuestion(
        "¿Qué mide principalmente una señal de fotopletismografía (PPG)?",
        ["Cambios del volumen de sangre del lecho microvascular",
         "La actividad eléctrica del corazón en una sola derivación",
         "La presión arterial, medida de forma directa", "La temperatura de la piel bajo el sensor"],
        0, category="Otras señales",
        explanation="La PPG es una técnica óptica sencilla y de bajo costo que detecta cambios del volumen de sangre en "
                    "el lecho microvascular del tejido; suele medirse sobre la piel, sin invasión.",
        source=ALLEN_2007,
    ),
], "academia")


# --- ECG Lab → 12 Derivaciones (Desafío Educativo) ----------------------------------------------
_ECG12 = "ECG 12 derivaciones"
ECG12_QUESTIONS: List[QuizQuestion] = balance_positions([
    QuizQuestion(
        "Según la AHA/ACCF/HRS 2009, ¿desde qué QTc se considera prolongado el QT de un hombre adulto?",
        ["450 ms o más", "400 ms o más", "500 ms o más", "390 ms o más"],
        0, category=_ECG12,
        explanation="La parte IV recomienda considerar prolongado un QT ajustado de 450 ms o más en hombres y de 460 ms "
                    "o más en mujeres, y corto uno de 390 ms o menos.",
        source=RAUTAHARJU_2009,
    ),
    QuizQuestion(
        "Una elevación del ST en V1–V4 orienta a la oclusión de:",
        ["La descendente anterior (DA)", "La coronaria derecha (CD)", "La circunfleja (Cx)",
         "Ninguna: V1–V4 no reflejan isquemia"],
        0, category=_ECG12,
        explanation="La parte VI atribuye la isquemia o el infarto de la cara anterior a la oclusión de la descendente "
                    "anterior, con elevación del ST en algunas o todas las derivaciones de V1 a V6.",
        source=WAGNER_2009,
    ),
    QuizQuestion(
        "¿Qué eje del QRS es criterio de bloqueo fascicular anterior izquierdo?",
        ["Entre −45° y −90°", "Entre −30° y +90°", "Entre +90° y +180°", "Entre −90° y ±180°"],
        0, category=_ECG12,
        explanation="Parte III: eje frontal entre −45° y −90°, qR en aVL, tiempo al pico de R en aVL ≥ 45 ms y "
                    "QRS < 120 ms. El rango de +90° a +180° es criterio del bloqueo fascicular posterior izquierdo.",
        source=SURAWICZ_2009,
    ),
    QuizQuestion(
        "¿Qué patrón es característico del bloqueo de rama derecha completo?",
        ["rsR′ en V1 o V2 con QRS ≥ 120 ms", "QS en V1 y V2 con QRS estrecho", "Onda delta con PR menor de 120 ms",
         "R ancha sin q en I y V6"],
        0, category=_ECG12,
        explanation="Parte III: QRS ≥ 120 ms en el adulto; rsr′, rsR′ o rSR′ en V1 o V2; S más larga que la R o "
                    "> 40 ms en I y V6.",
        source=SURAWICZ_2009,
    ),
    QuizQuestion(
        "PR corto, onda delta y QRS ancho en ritmo sinusal son signos de:",
        ["Preexcitación ventricular (patrón WPW)", "Fibrilación auricular de respuesta rápida",
         "Flutter auricular con conducción 2:1", "Bloqueo de rama izquierda completo"],
        0, category=_ECG12,
        explanation="Criterios de preexcitación de la parte III en el adulto: PR < 120 ms en ritmo sinusal, "
                    "empastamiento inicial del QRS (onda delta) y QRS > 120 ms. Es el patrón de Wolff-Parkinson-White.",
        source=SURAWICZ_2009,
    ),
    QuizQuestion(
        "Sin ondas P discernibles ni otra actividad auricular regular, y con intervalos RR sin patrón, el ritmo "
        "sugiere:",
        ["Fibrilación auricular", "Flutter auricular", "Taquicardia ventricular", "Ritmo sinusal"],
        0, category=_ECG12,
        explanation="La guía ESC 2024 describe la FA en el ECG como ausencia de ondas P discernibles y regulares, con "
                    "activación ventricular irregular y sin patrón en los RR.",
        source=VAN_GELDER_2024 + " (sección 3.1)",
    ),
    QuizQuestion(
        "Un QTc de 500 ms o más se asocia con mayor riesgo de:",
        ["Torsade de pointes", "Bloqueo AV de primer grado", "Infarto inferior", "Pericarditis aguda"],
        0, category=_ECG12,
        explanation="En el síndrome de QT largo congénito, un QTc ≥ 500 ms se asocia con un riesgo de torsade de "
                    "pointes (una taquicardia ventricular polimórfica) 2 a 3 veces mayor. No hay un umbral a partir "
                    "del cual ocurra con certeza.",
        source=DREW_2010,
    ),
    QuizQuestion(
        "Una oclusión proximal de la descendente anterior eleva el ST en:",
        ["V1–V4, I, aVL y a menudo aVR", "Solo II, III y aVF", "Solo V5 y V6",
         "Ninguna: deprime el ST en todas las derivaciones"],
        0, category=_ECG12,
        explanation="Parte VI: la oclusión proximal de la DA compromete las caras anterior y lateral y el septo, con "
                    "elevación del ST en V1–V4, I, aVL y a menudo aVR.",
        source=WAGNER_2009,
    ),
    QuizQuestion(
        "¿Cuál es el rango habitual del PR en el adulto?",
        ["120–200 ms", "80–120 ms", "200–300 ms", "300–400 ms"],
        0, category=_ECG12,
        explanation="Un PR < 120 ms en ritmo sinusal es criterio de preexcitación (parte III) y uno > 200 ms define el "
                    "bloqueo AV de primer grado (guía ACC/AHA/HRS 2018); entre ambos queda el rango habitual.",
        source=f"{SURAWICZ_2009}; {KUSUMOTO_2018} (tabla 3)",
    ),
    QuizQuestion(
        "Un eje del QRS entre +90° y +180° en un adulto, con rS en I y aVL, qR en III y aVF y QRS < 120 ms, cumple "
        "criterios de:",
        ["Bloqueo fascicular posterior izquierdo", "Bloqueo fascicular anterior izquierdo",
         "Bloqueo de rama izquierda completo", "Eje normal del adulto, sin bloqueo"],
        0, category=_ECG12,
        explanation="Parte III, bloqueo fascicular posterior izquierdo: eje frontal entre 90° y 180° en el adulto, rS "
                    "en I y aVL, qR en III y aVF y QRS < 120 ms.",
        source=SURAWICZ_2009,
    ),
    QuizQuestion(
        "En una persona con dolor torácico de tipo pericárdico, ¿qué patrón del ECG apoya una pericarditis?",
        ["Elevación del ST difusa con descenso del PR", "Depresión difusa del ST con elevación del PR",
         "Onda delta con PR corto", "rsR′ en V1 con QRS ≥ 120 ms"],
        0, category=_ECG12,
        explanation="La guía ESC 2025 cuenta como criterio adicional del ECG el descenso del PR con elevación del ST "
                    "difusa. El diagnóstico definitivo pide el cuadro clínico y más de un criterio adicional (frote "
                    "pericárdico, ECG, PCR elevada, derrame nuevo o que empeora, o hallazgos de resonancia).",
        source=SCHULZ_MENGER_2025 + " (tabla 4 y sección 3.3.2)",
    ),
    QuizQuestion(
        "Con una sola derivación filtrada a 0.5–40 Hz (como la placa del tutorial), ¿qué se puede estudiar?",
        ["El ritmo y la FC; no el ST ni el eje", "Las 12 derivaciones completas, sintetizadas desde esa",
         "El ST, con la misma validez que un ECG diagnóstico", "El eje eléctrico del QRS"],
        0, category=_ECG12,
        explanation="Un corte bajo de 0.5 Hz distorsiona mucho el nivel del ST (para el ST se pide 0.05 Hz, o hasta "
                    "0.67 Hz con filtros digitales lineales, y al menos 150 Hz arriba en el adulto). El eje se calcula "
                    "con dos derivaciones del plano frontal (este laboratorio usa I y aVF). Para el ritmo sí sirve: "
                    "para la FA, el consenso ha sido pedir 30 s o más con dispositivos de una o varias derivaciones.",
        source=f"{KLIGFIELD_2007}; {VAN_GELDER_2024} (sección 3.2)",
    ),
    QuizQuestion(
        "Un QRS de 120 ms o más en un adulto, con la morfología típica, indica:",
        ["Bloqueo de rama completo (derecho o izquierdo)", "Fibrilación auricular con respuesta ventricular lenta",
         "Ritmo sinusal normal, sin trastorno de conducción", "Bradicardia sinusal"],
        0, category=_ECG12,
        explanation="Parte III: el bloqueo completo de rama derecha o izquierda pide QRS ≥ 120 ms en el adulto; con QRS "
                    "de 110 a 120 ms se habla de bloqueo incompleto, y con QRS > 110 ms sin esa morfología, de "
                    "trastorno inespecífico de la conducción intraventricular.",
        source=SURAWICZ_2009,
    ),
    QuizQuestion(
        "¿Dónde se mide habitualmente el desplazamiento del segmento ST?",
        ["En el punto J, la unión con el final del QRS", "En el pico de la onda T, donde es más visible",
         "En el inicio de la onda P del latido siguiente", "En el pico de la onda R de cada complejo"],
        0, category=_ECG12,
        explanation="Parte IV: el desplazamiento del ST suele medirse en su unión con el final del QRS, el punto J. La "
                    "guía ESC 2023 define el IAMCEST con elevación nueva del ST en el punto J en al menos dos "
                    "derivaciones contiguas.",
        source=f"{RAUTAHARJU_2009}; {BYRNE_2023} (sección 3.2.1)",
    ),
    QuizQuestion(
        "Una elevación del ST solo en II, III y aVF puede deberse a la oclusión de:",
        ["La coronaria derecha (CD) o la circunfleja (Cx)", "Solo la descendente anterior (DA)",
         "Ninguna: II, III y aVF no muestran isquemia", "Siempre el tronco de la coronaria izquierda"],
        0, category=_ECG12,
        explanation="Parte VI: un infarto inferior con elevación del ST solo en II, III y aVF puede deberse a la "
                    "oclusión de la coronaria derecha o de la circunfleja.",
        source=WAGNER_2009,
    ),
    QuizQuestion(
        "¿Para qué sirve el análisis automático de esta página?",
        ["Para señalar patrones que debe confirmar un clínico", "Para dar un diagnóstico definitivo sin revisión médica",
         "Para reducir la frecuencia cardiaca", "Para medir la SpO₂ a partir del trazado del ECG"],
        0, category=_ECG12,
        explanation="El laboratorio mide intervalos, ondas y el ST sobre el latido mediano y los compara con criterios "
                    "publicados (no es un modelo de aprendizaje entrenado): señala hallazgos que debe confirmar un "
                    "clínico y no reemplaza la evaluación clínica.",
        source=ECG12_LAB_DESCRIPTION,
    ),
    QuizQuestion(
        "En un adulto sano (20 años o más), ¿cómo es la onda T en V3–V6?",
        ["Positiva", "Negativa", "Ausente", "Siempre bifásica"],
        0, category=_ECG12,
        explanation="Parte IV: desde los 20 años, la onda T es positiva en I y II y en las precordiales V3 a V6.",
        source=RAUTAHARJU_2009,
    ),
    QuizQuestion(
        "En la hipertrofia ventricular izquierda, además de los voltajes altos, puede verse:",
        ["Depresión del ST asociada a la hipertrofia", "Onda delta con PR menor de 120 ms en ritmo sinusal",
         "QTc de 390 ms o menos", "rsR′ en V1 con QRS ≥ 120 ms"],
        0, category=_ECG12,
        explanation="La parte IV incluye la depresión del ST asociada a la hipertrofia entre las causas de depresión "
                    "del ST. El voltaje se valora, por ejemplo, con Sokolow-Lyon (S en V1 + R en V5 o V6 ≥ 35 mm).",
        source=f"{RAUTAHARJU_2009}; {SOKOLOW_LYON_1949}",
    ),
    QuizQuestion(
        "¿Qué escenarios puede simular esta página?",
        ["Arritmias, infartos, bloqueos, HVI, WPW y QT largo", "Solo bradicardia sinusal, a distintas frecuencias",
         "Solo infartos con elevación del ST, en sus distintas localizaciones",
         "Solo hipertrofias, de cualquiera de los dos ventrículos"],
        0, category=_ECG12,
        explanation="El selector «Escenario clínico» genera trazados sintéticos de ritmo sinusal, taquicardia y "
                    "bradicardia sinusal, infartos con elevación del ST, bloqueos de rama, HVI, FA, flutter, WPW y QT "
                    "largo; el análisis los mide y los compara con criterios publicados. No usa un modelo de IA "
                    "entrenado.",
        source=ECG12_LAB_DESCRIPTION + " (selector «Escenario clínico»)",
    ),
], "ecg12")


# --- EEG Neuro Lab (Quiz interactivo EEG) --------------------------------------------------------
_EEG = "EEG"
EEG_QUESTIONS: List[QuizQuestion] = balance_positions([
    QuizQuestion(
        "Según el glosario IFCN 2017, ¿qué domina el sueño profundo (NREM N3)?",
        ["Ondas delta de 0.5–2 Hz y más de 75 µV", "El ritmo alfa posterior de 8–13 Hz",
         "Husos de sueño de 11–16 Hz", "Actividad beta de 14–30 Hz"],
        0, category=_EEG,
        explanation="El glosario define el sueño profundo (NREM N3, sueño de ondas lentas) como dominado (≥ 20 %) por "
                    "ondas delta lentas de 0.5 a 2 Hz y amplitud pico a pico > 75 µV, medidas sobre las regiones "
                    "frontales.",
        source=KANE_2017,
    ),
    QuizQuestion(
        "Una actividad beta difusa y prominente en el EEG puede deberse a:",
        ["Fármacos como benzodiacepinas, barbitúricos o alcohol", "El sueño profundo NREM N3",
         "Cerrar los ojos en reposo", "Una crisis electrográfica, en todos los casos sin excepción"],
        0, category=_EEG,
        explanation="El glosario IFCN 2017 describe el ritmo beta (14–30 Hz) como más característico de las regiones "
                    "fronto-centrales en vigilia; otros ritmos beta son difusos y pueden deberse a fármacos (alcohol, "
                    "barbitúricos, benzodiacepinas y anestésicos intravenosos).",
        source=KANE_2017,
    ),
    QuizQuestion(
        "¿Cuándo se ve mejor el ritmo alfa posterior?",
        ["Con los ojos cerrados, en relajación física", "Con los ojos abiertos y con atención visual sostenida",
         "Durante el sueño profundo NREM N3", "Durante un esfuerzo mental intenso"],
        0, category=_EEG,
        explanation="Glosario IFCN 2017: ritmo de 8–13 Hz en vigilia sobre las regiones posteriores; se ve mejor con "
                    "los ojos cerrados, en relajación física y relativa inactividad mental, y se bloquea o atenúa con "
                    "la atención (sobre todo visual) y el esfuerzo mental.",
        source=KANE_2017,
    ),
    QuizQuestion(
        "Según la terminología ACNS 2021, ¿qué define una crisis electrográfica?",
        ["Descargas epileptiformes > 2.5 Hz durante ≥ 10 s, o evolución definida ≥ 10 s",
         "Una sola espiga aislada de alto voltaje, sin importar su duración ni su frecuencia",
         "Husos de sueño de 11–16 Hz que aparecen en trenes durante el sueño NREM",
         "Un ritmo alfa posterior que se bloquea al abrir los ojos y vuelve al cerrarlos"],
        0, category=_EEG,
        explanation="ACNS 2021: crisis electrográfica = descargas epileptiformes con promedio > 2.5 Hz durante ≥ 10 s, o "
                    "cualquier patrón con evolución definida (al menos dos cambios sucesivos e inequívocos de "
                    "frecuencia, morfología o localización) que dure ≥ 10 s. Si dura ≥ 10 min seguidos, o ≥ 20 % de "
                    "cualquier hora de registro, es un estado epiléptico electrográfico.",
        source=HIRSCH_2021,
    ),
    QuizQuestion(
        "¿Qué caracteriza al sueño ligero (NREM N1 y N2) en el glosario IFCN 2017?",
        ["Ondas agudas del vértex, complejos K y husos de sueño",
         "Ondas delta de más de 75 µV en al menos el 20 % del registro",
         "Un ritmo alfa posterior que se bloquea al abrir los ojos",
         "Descargas epileptiformes a más de 2.5 Hz durante 10 s o más"],
        0, category=_EEG,
        explanation="El glosario describe las etapas N1 y N2 con movimientos oculares sinusoidales, actividad de baja "
                    "amplitud y frecuencias mixtas, ondas agudas del vértex, complejos K y husos de sueño (trenes de "
                    "11–16 Hz).",
        source=KANE_2017,
    ),
], "eeg")
