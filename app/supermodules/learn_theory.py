"""Teoría en capas de la sección Aprender (fase 1 de la propuesta, tanda 2, 2026-11-15).

Cada tema se lee en tres capas (`design_system.render_theory_topic`): (1) la idea en una frase, (2) el mecanismo y
(3) el detalle con su fuente; las capas 2 y 3 se abren a demanda.

REGLA (firmada para esta tanda): aquí NO se escribe contenido médico. Cada texto es una frase que YA existe en el
repositorio con su cita o etiqueta (Referencias del Laboratorio respiratorio, información educativa, referencias de
EEG, teoría de la Academia, panel del VCG); `ORIGINS` dice de qué archivo sale cada tema y
`tests/test_fase1_t2_teoria.py` comprueba que cada capa aparece, literal, en ese archivo. Una capa sin contenido con
fuente se omite (sin relleno) y queda en `PENDING_LAYERS` como contenido pendiente para la firma de Luis.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import streamlit as st

from app.supermodules.respiratory_lab.views import APNEA_CITATION, EDUCATION_CITATION
from app.utils.design_system import TheoryTopic
from clinical.calculators import NEWS2_CITATION

BERRY_2012 = APNEA_CITATION.split(": caída")[0]          # «Berry RB et al. J Clin Sleep Med 2012;8(5):597–619 (AASM)»

RESP_VIEWS = "app/supermodules/respiratory_lab/views.py"
EEG_TEACHING = "app/supermodules/eeg_neuro_lab/teaching.py"
ACADEMIA = "app/supermodules/academia/pages.py"
VCG_PANEL = "app/supermodules/model3d/panels.py"


def _lead_table() -> None:
    import pandas as pd

    from educational.ecg_academy import lead_explanations

    rows = [{"Derivación": name, "Qué observa": info["observes"], "Pared": info["wall"], "Arteria típica": info["artery"]}
            for name, info in lead_explanations().items()]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


TWELVE_LEADS = TheoryTopic(
    title="Las 12 derivaciones del ECG",
    idea="La tabla de las 12 derivaciones del ECG: qué observa cada una, qué pared representa, qué arteria coronaria "
         "suele comprometerse.",
    detail=_lead_table,
    source="`educational.ecg_academy.lead_explanations()` — tabla interna del repositorio, sin cita bibliográfica",
)

NEWS2_RESP = TheoryTopic(
    title="Frecuencia respiratoria y SpO₂ según NEWS2",
    idea="Es una puntuación de alerta, no una etiqueta diagnóstica: fuera de 12–20 se dice «fuera de 12–20 (NEWS2)».",
    detail="Puntos NEWS2 de la FR: **12–20 resp/min: 0**; 9–11: 1; 21–24: 2; ≤ 8: 3; ≥ 25: 3. Puntos de la SpO₂ "
           "(escala 1): **≥ 96 %: 0**; 94–95: 1; 92–93: 2; ≤ 91: 3.",
    source=NEWS2_CITATION,
)

HOW_MEASURED = TheoryTopic(
    title="¿Cómo se mide la respiración?",
    detail="- **Flujo de aire:** sensor térmico oronasal (termistor, termopar o PVDF)\n"
           "- **Esfuerzo respiratorio:** cinturones toracoabdominales\n"
           "- **Oxígeno:** pulsioximetría (SpO2)\n\n"
           "En este laboratorio las tres señales son **simuladas**.",
    source=BERRY_2012,
)

PATTERNS = TheoryTopic(
    title="Patrones respiratorios",
    idea="**Apnea (Berry 2012, AASM):** caída ≥ 90 % de la excursión del flujo respecto a la línea basal previa "
         "durante ≥ 10 s",
    detail="- **Cheyne-Stokes (Berry 2012):** ≥ 3 apneas/hipopneas centrales consecutivas separadas por un cambio "
           "creciente y decreciente de la amplitud, con ciclo ≥ 40 s (típicamente 45–90 s) y ≥ 5 por hora en ≥ 2 h de "
           "registro\n"
           "- Puede reflejar una insuficiencia cardíaca congestiva no reconocida\n"
           "- **Atáxica (descripción de la simulación):** el generador sortea la duración y la profundidad de cada "
           "respiración (irregularidad 0.20, HEURISTIC); no hay afirmación clínica sobre su causa",
    source=BERRY_2012,
)

APNEA_BY_EFFORT = TheoryTopic(
    title="Clasificación de la apnea por esfuerzo",
    idea="Berry 2012 (§4.1.1, AASM): la clasificación de una apnea como obstructiva, mixta o central **se basa en el "
         "esfuerzo respiratorio**.",
    mechanism="**Obstructiva, mecanismo (Epstein 2009):** los signos, síntomas y consecuencias son resultado directo "
              "del colapso repetitivo de la vía aérea superior",
    detail="Todas cumplen la misma regla de apnea (caída ≥ 90 % de la excursión del flujo durante ≥ 10 s).\n\n"
           "- **Central (Criterio BIOCORE):** esfuerzo ausente (caída ≥ 90 % del esfuerzo respecto a su basal)\n"
           "- **Obstructiva (Criterio BIOCORE):** esfuerzo presente; Berry 2012 señala que el movimiento paradójico "
           "del tórax y el abdomen se observa a menudo durante una apnea u hipopnea obstructiva\n"
           "- **Mixta:** [Pendiente de validación] (PENDING_VALIDATION; se calcula y se marca; la definición del manual "
           "no está verificada)\n"
           "- **Obesidad:** Epstein 2009 incluye la obesidad (IMC > 35) entre los pacientes de alto riesgo que deben "
           "evaluarse para apnea obstructiva del sueño",
    source=f"{BERRY_2012} · {EDUCATION_CITATION}",
)

OSA_GUIDELINE = TheoryTopic(
    title="Apnea obstructiva del sueño: lo que pide la guía AASM",
    mechanism="Epstein 2009: las consecuencias de la apnea obstructiva del sueño son resultado directo de las "
              "alteraciones que produce el colapso repetitivo de la vía aérea superior: fragmentación del sueño, "
              "hipoxemia, hipercapnia, grandes oscilaciones de la presión intratorácica y aumento de la actividad "
              "simpática",
    detail="- **Prevalencia:** al menos 2–4 % de la población adulta\n"
           "- **Condiciones secundarias que la guía pide evaluar:** hipertensión, ACV, infarto de miocardio, cor "
           "pulmonale, menor alerta diurna y accidentes de tráfico\n"
           "\n**Síntomas que la guía pide evaluar:**\n"
           "- Apneas presenciadas\n- Ronquido\n- Ahogo o asfixia nocturnos\n"
           "- Somnolencia excesiva no explicada por otros factores\n\n"
           "- **Diagnóstico:** la guía acepta dos métodos objetivos: polisomnografía en laboratorio y monitores "
           "portátiles en casa\n"
           "- La fibrilación auricular y las disritmias nocturnas figuran entre los pacientes de alto riesgo que se "
           "evalúan para AOS\n"
           "- Berry 2012 cita un estudio que asoció el índice de eventos con fibrilación auricular o ectopia "
           "ventricular compleja en hombres mayores sin insuficiencia cardíaca declarada\n\n"
           "**Opciones de tratamiento que enumera la guía** (la estrategia la decide un clínico con la persona, caso a "
           "caso): dispositivos de presión positiva en la vía aérea (CPAP), dispositivos orales, tratamientos "
           "conductuales (pérdida de peso, ejercicio, terapia posicional, evitar alcohol y sedantes antes de dormir), "
           "cirugía y tratamientos adyuvantes.",
    source=f"{EDUCATION_CITATION} · {BERRY_2012}",
)

EEG_BANDS = TheoryTopic(
    title="Bandas del EEG",
    detail="- **Banda Delta:** sueño profundo, 0.5-4 Hz\n"
           "- **Banda Theta:** somnolencia, 4-8 Hz\n"
           "- **Banda Alfa:** relajación con ojos cerrados, 8-12 Hz\n"
           "- **Banda Beta:** alerta y concentración, 13-30 Hz\n"
           "- **Banda Gamma:** procesamiento cognitivo integrado, 30-45 Hz",
    source=None,                         # el repositorio no cita fuente para estos rangos: se declara, no se inventa
)

VCG = TheoryTopic(
    title="El ECG en 3D (vectocardiograma)",
    idea="Cada asa es la trayectoria de la punta del vector cardiaco durante el latido mediano: P (verde), QRS (azul) "
         "y T (naranja)",
    mechanism="El VCG se reconstruye de sus 12 derivaciones con la matriz de Kors",
    detail="- Ángulo entre los vectores medios de despolarización (QRS) y repolarización (T). Ángulos amplios se "
           "asocian a mayor riesgo cardiovascular (Oehler et al., 2014).\n"
           "- La reconstrucción de Kors (Kors et al., 1990) se comparó con el VCG de Frank grabado a la vez en esa "
           "paciente; un solo caso no es una validación clínica.",
    source="Kors et al., 1990 · Oehler et al., 2014 (citas abreviadas, como aparecen en el panel del VCG)",
)

# Tema -> archivo de donde sale su texto (la prueba busca cada capa, literal, en ese archivo).
ORIGINS: Dict[str, str] = {
    TWELVE_LEADS.title: ACADEMIA, NEWS2_RESP.title: RESP_VIEWS, HOW_MEASURED.title: RESP_VIEWS,
    PATTERNS.title: RESP_VIEWS, APNEA_BY_EFFORT.title: RESP_VIEWS, OSA_GUIDELINE.title: RESP_VIEWS,
    EEG_BANDS.title: EEG_TEACHING, VCG.title: VCG_PANEL,
}

LEARN_TOPICS = {
    "teoria": [TWELVE_LEADS],
    "referencias": [NEWS2_RESP, HOW_MEASURED, PATTERNS, APNEA_BY_EFFORT, OSA_GUIDELINE, EEG_BANDS],
    "ecg-3d": [VCG],
}

# Capas omitidas por falta de contenido con fuente (para la firma de Luis): (tema, capa, qué haría falta).
PENDING_LAYERS: List[Tuple[str, str, str]] = [
    (TWELVE_LEADS.title, "mecanismo", "por qué cada derivación «ve» una pared (vector, eje de la derivación), con cita"),
    (TWELVE_LEADS.title, "fuente de la tabla", "cita bibliográfica de la correspondencia derivación-pared-arteria"),
    (NEWS2_RESP.title, "mecanismo", "por qué la FR y la SpO₂ alertan de deterioro, con cita"),
    (HOW_MEASURED.title, "idea", "una frase con fuente que resuma cómo se registran flujo, esfuerzo y SpO₂"),
    (HOW_MEASURED.title, "mecanismo", "cómo funciona cada sensor (termistor, cinturones, pulsioximetría), con cita"),
    (PATTERNS.title, "mecanismo", "fisiopatología de Cheyne-Stokes y de la respiración atáxica, con cita"),
    (OSA_GUIDELINE.title, "idea", "una frase con fuente que resuma la apnea obstructiva del sueño"),
    (EEG_BANDS.title, "idea", "una frase con fuente sobre qué es una banda del EEG"),
    (EEG_BANDS.title, "mecanismo", "origen de los ritmos (tálamo-corteza), con cita"),
    (EEG_BANDS.title, "fuente", "cita de los rangos de frecuencia de cada banda (hoy sin fuente en el repositorio)"),
    (VCG.title, "fuente completa", "referencias completas de Kors 1990 y Oehler 2014 (hoy abreviadas)"),
]
