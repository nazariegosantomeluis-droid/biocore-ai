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
# derivaciones), las del EEG en `clinical/eeg_references.py` (también las usa el EEG en vivo) y las de la PPG en
# `clinical/ppg_references.py` (también las usa el sensor de pulso en vivo).
from clinical.ecg_references import (  # noqa: E402
    AL_KHATIB_2017, BYRNE_2023, DREW_2010, KLIGFIELD_2007, KUSUMOTO_2018, RAUTAHARJU_2009, SCHULZ_MENGER_2025,
    SOKOLOW_LYON_1949, SURAWICZ_2009, VAN_GELDER_2024, WAGNER_2009,
)
from clinical.eeg_references import KANE_2017  # noqa: E402
from clinical.ppg_references import ALLEN_2007  # noqa: E402

BIGA_ANATOMY = (
    "Biga LM, et al. Anatomy & Physiology, cap. 19, «Conduction system of the heart and the ECG». "
    "Libro de texto abierto, licencia CC BY-SA 4.0"
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


# --- EMG y HRV (2026-11-17): E1–E10 y H1–H8, FIRMADOS por Luis el 2026-11-17 (bloque de firma del 17-11-2026) -------------------
# Redacción exacta de la hoja de firma v2 (`docs/contenido/hoja_firma_banco_emg_hrv_v2.md`): E1 tal cual, E2–E10 y
# H1–H8 con su corrección. Cada explicación es una subcadena literal de la línea «t2:N» de
# `docs/contenido/teoria_citada_2.md` que la sostiene (E1 conserva la explicación de la v2, firmada «tal cual»; H4 se
# corta antes de la segunda mención de «la razón LF/HF», que no lleva el rótulo). La fuente es la referencia completa
# de ese documento, con su clave. `tests/test_banco_emg_hrv.py` vigila todo esto.
_EMG = "EMG"
_HRV = "HRV"
_REF_B2013 = '[B2013] Billman GE. The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. Front Physiol. 2013;4:26. doi:10.3389/fphys.2013.00026.'
_REF_DL1997 = '[DL1997] De Luca CJ. The use of surface electromyography in biomechanics. J Appl Biomech. 1997;13(2):135–163.'
_REF_DL2010 = '[DL2010] De Luca CJ, Gilmore LD, Kuznetsov M, Roy SH. Filtering the surface EMG signal: movement artifact and baseline noise contamination. J Biomech. 2010;43:1573–1579. doi:10.1016/j.jbiomech.2010.01.027.'
_REF_SG2017 = '[SG2017] Shaffer F, Ginsberg JP. An overview of heart rate variability metrics and norms. Front Public Health. 2017;5:258. doi:10.3389/fpubh.2017.00258.'
_REF_V2018 = '[V2018] Vigotsky AD, Halperin I, Lehman GJ, Trajano GS, Vieira TM. Interpreting signal amplitudes in surface electromyography studies in sport and rehabilitation sciences. Front Physiol. 2018;8:985. doi:10.3389/fphys.2017.00985.'

EMG_QUESTIONS: List[QuizQuestion] = balance_positions([
    QuizQuestion(  # E1 · firmada 2026-11-17 · t2:13
        '¿Qué registra un electrodo de EMG de superficie?',
        ['La suma de los potenciales de acción de las unidades motoras activas bajo el electrodo',
         'La fuerza mecánica que produce el músculo',
         'La actividad de un único nervio periférico, aislada',
         'El potencial de reposo de las fibras musculares'],
        0, category=_EMG,
        explanation='el electrodo capta la suma de los potenciales de las unidades motoras que tiene debajo.',
        source=_REF_DL1997,
    ),
    QuizQuestion(  # E2 · firmada 2026-11-17 · t2:17, t2:62
        '¿Qué indica una amplitud más alta del EMG de superficie?',
        ['Mayor excitación del músculo, no su fuerza',
         'Mayor fuerza muscular, en proporción directa',
         'Mayor fuerza muscular, siempre que la señal esté normalizada',
         'Mayor masa muscular'],
        0, category=_EMG,
        explanation='La amplitud del EMG de superficie indica la excitación del músculo, no su fuerza. Incluso normalizada, la amplitud no permite deducir la fuerza del músculo.',
        source=_REF_V2018,
    ),
    QuizQuestion(  # E3 · firmada 2026-11-17 · t2:25
        'El músculo aumenta su fuerza de dos maneras: activando unidades motoras nuevas (reclutamiento) y haciendo que las ya activas disparen más rápido. ¿Puede la amplitud del EMG de superficie decir cuánto del aumento se debe a cada una?',
        ['No: la amplitud no permite distinguir cuánto se debe a cada una',
         'Sí: si la amplitud sube, todo el aumento se debe al reclutamiento',
         'Sí: si la amplitud sube, todo el aumento se debe a la frecuencia de disparo',
         'Sí, siempre que la señal esté normalizada'],
        0, category=_EMG,
        explanation='Con la amplitud del EMG de superficie no se puede distinguir cuánto se debe al reclutamiento y cuánto a la frecuencia de disparo.',
        source=_REF_DL1997 + " · " + _REF_V2018,
    ),
    QuizQuestion(  # E4 · firmada 2026-11-17 · t2:45
        '¿Por qué se recomienda un filtro pasa-altas de 20 Hz para el EMG de superficie?',
        ['Porque el artefacto de movimiento concentra su energía en frecuencias bajas',
         'Para eliminar la interferencia de la red eléctrica',
         'Porque por debajo de 20 Hz está la mayor parte de la energía de la señal muscular',
         'Para eliminar la diafonía de los músculos vecinos'],
        0, category=_EMG,
        explanation='Pasa-altas de 20 Hz (Butterworth, 12 dB/octava) para uso general: el artefacto de movimiento concentra su energía en frecuencias bajas y cae rápidamente por encima de 20 Hz; la energía del EMG por debajo de 20 Hz es poca e inestable.',
        source=_REF_DL2010,
    ),
    QuizQuestion(  # E5 · firmada 2026-11-17 · t2:54
        'Para medir la amplitud de una contracción voluntaria, ¿qué medida se recomienda y por qué?',
        ['El RMS, porque representa la potencia de la señal y tiene un significado físico claro',
         'El valor medio rectificado, porque representa la potencia de la señal y tiene un significado físico claro',
         'El valor máximo, porque es el más estable',
         'La frecuencia mediana, porque no depende de la amplitud'],
        0, category=_EMG,
        explanation='El RMS representa la potencia de la señal y tiene un significado físico claro; el valor medio rectificado mide el área bajo la señal y no tiene un significado físico específico.',
        source=_REF_DL1997,
    ),
    QuizQuestion(  # E6 · firmada 2026-11-17 · t2:58, t2:62
        '¿Por qué suele normalizarse la amplitud del EMG, por ejemplo a la contracción voluntaria isométrica máxima?',
        ['Porque los microvoltios no se pueden comparar entre personas, músculos o sesiones',
         'Porque así la amplitud se vuelve igual a la fuerza',
         'Porque así se elimina el artefacto de movimiento',
         'Porque así se puede distinguir el reclutamiento de la frecuencia de disparo'],
        0, category=_EMG,
        explanation='La amplitud en microvoltios no se puede comparar entre personas, músculos o sesiones; por eso suele normalizarse, por ejemplo a la contracción voluntaria isométrica máxima. Incluso normalizada, la amplitud no permite deducir la fuerza del músculo.',
        source=_REF_V2018,
    ),
    QuizQuestion(  # E7 · firmada 2026-11-17 · t2:66
        'Durante una contracción sostenida, ¿qué le ocurre al espectro del EMG y qué índice se usa para seguirlo?',
        ['Se desplaza hacia frecuencias más bajas; se sigue con la frecuencia mediana',
         'Se desplaza hacia frecuencias más altas; se sigue con la frecuencia mediana',
         'No cambia; solo cambia la amplitud',
         'Se desplaza hacia frecuencias más bajas; se sigue con el valor máximo'],
        0, category=_EMG,
        explanation='Durante una contracción sostenida, el espectro del EMG se "comprime" hacia frecuencias más bajas, y la frecuencia mediana es el índice preferido para seguir ese cambio.',
        source=_REF_DL1997,
    ),
    QuizQuestion(  # E8 · firmada 2026-11-17 · t2:77
        'Un electrodo sobre un músculo capta también parte de la actividad de los músculos vecinos. ¿Cómo se llama esto y hasta cuánto puede llegar?',
        ['Diafonía (crosstalk): hasta 17 % de la actividad de los músculos vecinos',
         'Artefacto de movimiento: hasta 17 % de la actividad de los músculos vecinos',
         'Diafonía: siempre menos de 1 %',
         'Fatiga: hasta 50 %'],
        0, category=_EMG,
        explanation='Diafonía (crosstalk): hasta 17 % de la actividad eléctrica de músculos vecinos puede detectarse en el electrodo.',
        source=_REF_DL1997,
    ),
    QuizQuestion(  # E9 · firmada 2026-11-17 · t2:89, t2:86, t2:87
        '¿Cuál de estas conclusiones sí permite, con cautela, un EMG de superficie?',
        ['Decir si un músculo está «encendido» o «apagado» en intervalos de más de unos 200 ms',
         'Calcular la fuerza del músculo en newtons',
         'Predecir cuánto crecerá el músculo con el entrenamiento',
         'Comparar la fuerza de dos personas por su amplitud en microvoltios'],
        0, category=_EMG,
        explanation='Sí permite, con cautela, decir si un músculo está "encendido" o "apagado" en intervalos de más de unos 200 ms, y hacer comparaciones dentro de la misma persona y el mismo músculo si se controlan las condiciones. No permite deducir la fuerza muscular. No predice la hipertrofia ni la adaptación a largo plazo.',
        source=_REF_V2018,
    ),
    QuizQuestion(  # E10 · firmada 2026-11-17 · t2:87
        'Un ejercicio produce más amplitud de EMG que otro en el mismo músculo. ¿Permite eso afirmar que producirá más hipertrofia?',
        ['No: la amplitud no predice la hipertrofia',
         'Sí: más amplitud implica más hipertrofia a largo plazo',
         'Sí, si la diferencia es mayor de 20 %',
         'Solo si la señal está normalizada'],
        0, category=_EMG,
        explanation='No predice la hipertrofia ni la adaptación a largo plazo.',
        source=_REF_V2018,
    ),
], 'emg')


HRV_QUESTIONS: List[QuizQuestion] = balance_positions([
    QuizQuestion(  # H1 · firmada 2026-11-17 · t2:101, t2:103
        '¿Qué es la variabilidad de la frecuencia cardiaca (HRV)?',
        ['La variación del tiempo entre latidos consecutivos',
         'El número de latidos por minuto',
         'La diferencia entre la frecuencia cardiaca máxima y la mínima del día',
         'La irregularidad causada por arritmias'],
        0, category=_HRV,
        explanation='La HRV es la variación del tiempo entre latidos consecutivos. Se calcula sobre intervalos NN ("normal a normal"): intervalos entre latidos sinusales de los que se han retirado los artefactos.',
        source=_REF_SG2017,
    ),
    QuizQuestion(  # H2 · firmada 2026-11-17 · t2:110, t2:111
        '¿Qué afirmación sobre la RMSSD y la SDNN es correcta?',
        ['La RMSSD está más influida por el sistema nervioso parasimpático que la SDNN',
         'La SDNN está más influida por el sistema nervioso parasimpático que la RMSSD',
         'La RMSSD es la desviación estándar de los intervalos NN',
         'Las dos están igual de influidas por el sistema nervioso parasimpático'],
        0, category=_HRV,
        explanation='SDNN: desviación estándar de los intervalos NN, en ms. RMSSD: está más influida por el sistema nervioso parasimpático que la SDNN.',
        source=_REF_SG2017,
    ),
    QuizQuestion(  # H3 · firmada 2026-11-17 · t2:124, t2:125, t2:127
        '¿Qué rango ocupa la banda HF y qué la modifica?',
        ['0.15–0.40 Hz; está influida por la respiración entre 9 y 24 respiraciones por minuto',
         '0.04–0.15 Hz; está influida por la respiración',
         '0.0033–0.04 Hz; está influida por la respiración entre 9 y 24 respiraciones por minuto',
         '0.15–0.40 Hz; no depende de la respiración'],
        0, category=_HRV,
        explanation='LF: 0.04–0.15 Hz. HF ("banda respiratoria"): 0.15–0.40 Hz. La banda HF está influida por la respiración entre 9 y 24 respiraciones por minuto.',
        source=_REF_SG2017,
    ),
    QuizQuestion(  # H4 · firmada 2026-11-17 · t2:128
        '¿Qué afirmación sobre la razón LF/HF (interpretación discutida) es correcta?',
        ['No mide con exactitud el equilibrio entre simpático y parasimpático, porque la potencia LF mezcla varias influencias',
         'Mide directamente el impulso simpático cardiaco',
         'Un valor alto demuestra predominio simpático',
         'Es la medida de referencia del sistema nervioso autónomo'],
        0, category=_HRV,
        explanation='La razón LF/HF es discutida: la potencia LF no es un índice del impulso simpático cardiaco, sino una mezcla de influencias simpáticas, parasimpáticas y otras no identificadas',
        source=_REF_B2013 + " · " + _REF_SG2017,
    ),
    QuizQuestion(  # H5 · firmada 2026-11-17 · t2:136
        'Una estudiante compara la SDNN de un registro de 5 minutos con la de un Holter de 24 horas. ¿Es correcto?',
        ['No: no es apropiado comparar la SDNN calculada sobre periodos de distinta duración',
         'Sí, porque la SDNN no depende de la duración',
         'Sí, si se multiplica el valor de 5 minutos por 288',
         'Sí, si los dos registros son de la misma persona'],
        0, category=_HRV,
        explanation='Los valores de registros cortos y ultracortos no son intercambiables con los de 24 horas, y no es apropiado comparar métricas como la SDNN calculadas sobre periodos de distinta duración.',
        source=_REF_SG2017,
    ),
    QuizQuestion(  # H6 · firmada 2026-11-17 · t2:155
        '¿Qué les ocurre a las medidas de HRV del dominio del tiempo con la edad?',
        ['Disminuyen',
         'Aumentan',
         'No cambian',
         'Solo dependen de la duración del registro, no de la edad'],
        0, category=_HRV,
        explanation='La duración del registro, la edad y el sexo influyen en los valores basales; las medidas del dominio del tiempo disminuyen con la edad.',
        source=_REF_SG2017,
    ),
    QuizQuestion(  # H7 · firmada 2026-11-17 · t2:150
        'La entropía muestral se diseñó como:',
        ['Una medida menos sesgada y más fiable de la regularidad y la complejidad de la señal',
         'Una medida de la potencia de la banda HF',
         'Un método para detectar latidos ectópicos',
         'Una forma de calcular la frecuencia cardiaca media'],
        0, category=_HRV,
        explanation='Entropía muestral: se diseñó como una medida menos sesgada y más fiable de la regularidad y la complejidad de la señal.',
        source=_REF_SG2017,
    ),
    QuizQuestion(  # H8 · firmada 2026-11-17 · t2:169
        '¿Existe un único «valor normal» de HRV?',
        ['No: depende de la duración del registro, la edad y el sexo',
         'Sí: el mismo para todas las edades, sexos y duraciones del registro',
         'Sí, pero solo para registros de 5 minutos',
         'Sí, el que calcula el equipo'],
        0, category=_HRV,
        explanation='No hay un único "valor normal": los valores de referencia dependen de la duración del registro, la edad y el sexo, y los de registros cortos no sirven para comparar con los de 24 horas.',
        source=_REF_SG2017,
    ),
], 'hrv')


# --- NEWS2 (2026-11-17): N1–N9, FIRMADOS por Luis el 2026-11-17 («Firmo todo»; D-N7: sí) ------------------------------
# Texto exacto de `docs/contenido/banco_preguntas_news2.md`. Cada explicación es la de esa hoja, que sale de la línea
# «t1:N» de `docs/contenido/teoria_citada.md` (temas 2 y 6). `tests/test_banco_news2.py` vigila todo esto.
_NEWS2 = "NEWS2"
_REF_RCP2017 = ('[RCP2017] Royal College of Physicians. National Early Warning Score (NEWS) 2: Standardising the '
                'assessment of acute-illness severity in the NHS. Updated report of a working party. Londres: RCP; 2017.')
_NEWS2_PULSE = 'en la escala NEWS2, el pulso puntúa: ≤40 lpm, 3 puntos; 41–50, 1; 51–90, 0; 91–110, 1; 111–130, 2; ≥131, 3 [RCP2017].'

NEWS2_QUESTIONS: List[QuizQuestion] = balance_positions([
    QuizQuestion(  # N1 · firmada 2026-11-17 · t1:91
        '¿Para qué sirve NEWS2?',
        ['Para estandarizar cómo se registran, puntúan y atienden las constantes vitales, y detectar el deterioro agudo',
         'Para diagnosticar la causa del deterioro de un paciente',
         'Para sustituir la valoración de un clínico',
         'Para medir la saturación de oxígeno sin pulsioxímetro'],
        0, category=_NEWS2,
        explanation=('NEWS2 es una puntuación agregada que estandariza cómo se registran, puntúan y atienden las '
                     'constantes vitales para detectar el deterioro agudo [RCP2017].'),
        source=_REF_RCP2017,
    ),
    QuizQuestion(  # N2 · firmada 2026-11-17 · t1:94
        '¿Cuántos parámetros puntúa NEWS2?',
        ['Seis: frecuencia respiratoria, SpO₂, presión arterial sistólica, pulso, nivel de consciencia o confusión '
         'nueva, y temperatura',
         'Cuatro: frecuencia respiratoria, SpO₂, pulso y temperatura',
         'Cinco: los mismos seis, sin la temperatura',
         'Tres: pulso, presión arterial y SpO₂'],
        0, category=_NEWS2,
        explanation=('puntúa seis parámetros: frecuencia respiratoria, SpO₂, presión arterial sistólica, pulso, nivel '
                     'de consciencia o confusión nueva, y temperatura [RCP2017].'),
        source=_REF_RCP2017,
    ),
    QuizQuestion(  # N3 · firmada 2026-11-17 · t1:94
        'Si el paciente recibe oxígeno suplementario, ¿qué pasa con su NEWS2?',
        ['Se suman 2 puntos', 'Se suma 1 punto', 'Se suman 3 puntos', 'No cambia: el oxígeno no se puntúa'],
        0, category=_NEWS2,
        explanation='se suman 2 puntos si el paciente recibe oxígeno suplementario [RCP2017].',
        source=_REF_RCP2017,
    ),
    QuizQuestion(  # N4 · firmada 2026-11-17 · t1:35
        'En NEWS2, ¿cuántos puntos da un pulso de 120 lpm?',
        ['2 puntos (tramo de 111 a 130 lpm)', '0 puntos', '1 punto', '3 puntos'],
        0, category=_NEWS2, explanation=_NEWS2_PULSE, source=_REF_RCP2017,
    ),
    QuizQuestion(  # N5 · firmada 2026-11-17 · t1:35
        'En NEWS2, ¿cuántos puntos da un pulso de 45 lpm?',
        ['1 punto (tramo de 41 a 50 lpm)', '0 puntos', '2 puntos', '3 puntos'],
        0, category=_NEWS2, explanation=_NEWS2_PULSE, source=_REF_RCP2017,
    ),
    QuizQuestion(  # N6 · firmada 2026-11-17 · t1:96
        '¿Qué significa un 3 en un solo parámetro de NEWS2?',
        ['Es poco frecuente y motiva una revisión urgente',
         'Nada mientras el total sea bajo',
         'Que el paciente recibe oxígeno suplementario',
         'Que hay que usar la escala 2 de SpO₂'],
        0, category=_NEWS2,
        explanation=('un 3 en un solo parámetro (marcado en rojo) es poco frecuente y motiva una revisión urgente '
                     '[RCP2017].'),
        source=_REF_RCP2017,
    ),
    QuizQuestion(  # N7 · firmada 2026-11-17 · t1:99 (D-N7: sí)
        'Un total de NEWS2 de 5 o 6 (riesgo medio), ¿qué respuesta indica?',
        ['Revisión urgente por un clínico competente en enfermedad aguda',
         'Vigilancia al menos cada 12 horas',
         'Valoración por enfermería',
         'Valoración de emergencia por un equipo con competencia en cuidados críticos'],
        0, category=_NEWS2,
        explanation=('total 0: vigilancia al menos cada 12 horas. Total 1–4 (bajo): valoración por enfermería. Total '
                     '5–6 (medio): revisión urgente por un clínico competente en enfermedad aguda. Total 7 o más '
                     '(alto): valoración de emergencia por un equipo con competencia en cuidados críticos [RCP2017].'),
        source=_REF_RCP2017,
    ),
    QuizQuestion(  # N8 · firmada 2026-11-17 · t1:100
        '¿Cuándo se usa la escala 2 de SpO₂ de NEWS2?',
        ['En insuficiencia respiratoria hipercápnica confirmada (por lo general EPOC), con objetivo de 88–92 %, bajo '
         'indicación de un clínico',
         'Siempre que la SpO₂ baje de 92 %',
         'En todo paciente que recibe oxígeno suplementario',
         'Nunca: NEWS2 tiene una sola escala de SpO₂'],
        0, category=_NEWS2,
        explanation=('la escala 2 de SpO₂ se usa en insuficiencia respiratoria hipercápnica confirmada (por lo general '
                     'EPOC), con objetivo de 88–92 %, bajo indicación de un clínico. En los demás casos se usa la '
                     'escala 1 [RCP2017].'),
        source=_REF_RCP2017,
    ),
    QuizQuestion(  # N9 · firmada 2026-11-17 · t1:101
        '¿Por qué BIOCORE muestra los puntos de cada parámetro de NEWS2 y no el total?',
        ['Porque el gemelo no dispone de presión arterial en todos los casos y no modela temperatura ni consciencia: '
         'un total sería falso',
         'Porque el total de NEWS2 no tiene utilidad clínica',
         'Porque el total solo se calcula en pacientes con oxígeno suplementario',
         'Porque el total requiere un electrocardiograma de 12 derivaciones'],
        0, category=_NEWS2,
        explanation=('el gemelo no dispone de presión arterial en todos los casos, y no modela temperatura ni '
                     'consciencia. Sin esos parámetros, un total sería falso; por eso la plataforma muestra los '
                     'puntos de cada parámetro disponible y lista lo que falta.'),
        source=_REF_RCP2017,
    ),
], 'news2')


# --- Concepto de cada pregunta (2026-11-17): FIRMADO por Luis el 2026-11-17 (bloque de firma del 17-11-2026) -----------------------
# Vocabulario: `CONCEPTS` de `app/utils/session_learning.py` (el contrato de Luis; no se inventan otros). Lo usa la
# calibración de la confianza (`educational/confidence_calibration.py`). Una pregunta que no encaja en ningún
# concepto del vocabulario NO está aquí y su respuesta no entra al registro de la sesión: quedan fuera 9 preguntas
# (EEG, PPG, HVI, pericarditis, manejo del IAMCEST y las que describen la propia app). Con la firma entraron la onda T
# normal (→ ritmo_y_conduccion) y las 18 de EMG y HRV (→ emg / hrv). La pericarditis sigue fuera.
CONCEPT_BY_PROMPT = {
    'Por convención docente, la FC del adulto en reposo se toma como normal entre 60 y 100 lpm. ¿Con qué valor define la bradicardia sinusal la guía ACC/AHA/HRS 2018?':
        'frecuencia_cardiaca',
    '¿Qué representa el complejo QRS?':
        'ritmo_y_conduccion',
    'Durante un infarto con elevación del ST, ¿qué puede significar una depresión del ST en V1 y V2?':
        'derivaciones_e_isquemia',
    'En una persona con dolor torácico agudo, ¿qué diagnóstico de trabajo plantea una elevación persistente del ST?':
        'derivaciones_e_isquemia',
    '¿Qué mide el intervalo PR?':
        'ritmo_y_conduccion',
    '¿Qué es una PVC?':
        'ritmo_y_conduccion',
    '¿Cómo se calcula la FC (en lpm) a partir del intervalo RR?':
        'frecuencia_cardiaca',
    'Una elevación del ST solo en II, III y aVF puede deberse a la oclusión de:':
        'derivaciones_e_isquemia',
    '¿Cuál de estas condiciones causa bradicardia?':
        'ritmo_y_conduccion',
    'Un eje del QRS entre −45° y −90°, con qR en aVL y QRS < 120 ms, cumple criterios de:':
        'ritmo_y_conduccion',
    '¿Qué patrón corresponde a un bloqueo de rama derecha completo en el adulto?':
        'ritmo_y_conduccion',
    '¿Cómo se reconoce la fibrilación auricular en el ECG?':
        'ritmo_y_conduccion',
    'Según la AHA/ACCF/HRS 2009, ¿desde qué QTc se considera prolongado el QT de un hombre adulto?':
        'ritmo_y_conduccion',
    'Una elevación del ST en V1–V4 orienta a la oclusión de:':
        'derivaciones_e_isquemia',
    '¿Qué eje del QRS es criterio de bloqueo fascicular anterior izquierdo?':
        'ritmo_y_conduccion',
    '¿Qué patrón es característico del bloqueo de rama derecha completo?':
        'ritmo_y_conduccion',
    'PR corto, onda delta y QRS ancho en ritmo sinusal son signos de:':
        'ritmo_y_conduccion',
    'Sin ondas P discernibles ni otra actividad auricular regular, y con intervalos RR sin patrón, el ritmo sugiere:':
        'ritmo_y_conduccion',
    'Un QTc de 500 ms o más se asocia con mayor riesgo de:':
        'ritmo_y_conduccion',
    'Una oclusión proximal de la descendente anterior eleva el ST en:':
        'derivaciones_e_isquemia',
    '¿Cuál es el rango habitual del PR en el adulto?':
        'ritmo_y_conduccion',
    'Un eje del QRS entre +90° y +180° en un adulto, con rS en I y aVL, qR en III y aVF y QRS < 120 ms, cumple criterios de:':
        'ritmo_y_conduccion',
    'Un QRS de 120 ms o más en un adulto, con la morfología típica, indica:':
        'ritmo_y_conduccion',
    '¿Dónde se mide habitualmente el desplazamiento del segmento ST?':
        'derivaciones_e_isquemia',
    'En un adulto sano (20 años o más), ¿cómo es la onda T en V3–V6?':
        'ritmo_y_conduccion',  # firmado 2026-11-17: onda T normal
    '¿Qué registra un electrodo de EMG de superficie?':
        'emg',  # E1
    '¿Qué indica una amplitud más alta del EMG de superficie?':
        'emg',  # E2
    'El músculo aumenta su fuerza de dos maneras: activando unidades motoras nuevas (reclutamiento) y haciendo que las ya activas disparen más rápido. ¿Puede la amplitud del EMG de superficie decir cuánto del aumento se debe a cada una?':
        'emg',  # E3
    '¿Por qué se recomienda un filtro pasa-altas de 20 Hz para el EMG de superficie?':
        'emg',  # E4
    'Para medir la amplitud de una contracción voluntaria, ¿qué medida se recomienda y por qué?':
        'emg',  # E5
    '¿Por qué suele normalizarse la amplitud del EMG, por ejemplo a la contracción voluntaria isométrica máxima?':
        'emg',  # E6
    'Durante una contracción sostenida, ¿qué le ocurre al espectro del EMG y qué índice se usa para seguirlo?':
        'emg',  # E7
    'Un electrodo sobre un músculo capta también parte de la actividad de los músculos vecinos. ¿Cómo se llama esto y hasta cuánto puede llegar?':
        'emg',  # E8
    '¿Cuál de estas conclusiones sí permite, con cautela, un EMG de superficie?':
        'emg',  # E9
    'Un ejercicio produce más amplitud de EMG que otro en el mismo músculo. ¿Permite eso afirmar que producirá más hipertrofia?':
        'emg',  # E10
    '¿Qué es la variabilidad de la frecuencia cardiaca (HRV)?':
        'hrv',  # H1
    '¿Qué afirmación sobre la RMSSD y la SDNN es correcta?':
        'hrv',  # H2
    '¿Qué rango ocupa la banda HF y qué la modifica?':
        'hrv',  # H3
    '¿Qué afirmación sobre la razón LF/HF (interpretación discutida) es correcta?':
        'hrv',  # H4
    'Una estudiante compara la SDNN de un registro de 5 minutos con la de un Holter de 24 horas. ¿Es correcto?':
        'hrv',  # H5
    '¿Qué les ocurre a las medidas de HRV del dominio del tiempo con la edad?':
        'hrv',  # H6
    'La entropía muestral se diseñó como:':
        'hrv',  # H7
    '¿Existe un único «valor normal» de HRV?':
        'hrv',  # H8
    '¿Para qué sirve NEWS2?':
        'news2',  # N1
    '¿Cuántos parámetros puntúa NEWS2?':
        'news2',  # N2
    'Si el paciente recibe oxígeno suplementario, ¿qué pasa con su NEWS2?':
        'news2',  # N3
    'En NEWS2, ¿cuántos puntos da un pulso de 120 lpm?':
        'news2',  # N4
    'En NEWS2, ¿cuántos puntos da un pulso de 45 lpm?':
        'news2',  # N5
    '¿Qué significa un 3 en un solo parámetro de NEWS2?':
        'news2',  # N6
    'Un total de NEWS2 de 5 o 6 (riesgo medio), ¿qué respuesta indica?':
        'news2',  # N7
    '¿Cuándo se usa la escala 2 de SpO₂ de NEWS2?':
        'news2',  # N8
    '¿Por qué BIOCORE muestra los puntos de cada parámetro de NEWS2 y no el total?':
        'news2',  # N9
}
