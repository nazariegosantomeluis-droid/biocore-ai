"""Teoría en capas de la sección Aprender (fase 1 de la propuesta, tanda 2, 2026-11-15).

Cada tema se lee en tres capas (`design_system.render_theory_topic`): (1) la idea en una frase, (2) el mecanismo y
(3) el detalle con su fuente; las capas 2 y 3 se abren a demanda.

REGLA (firmada para esta tanda): aquí NO se escribe contenido médico. Cada texto es una frase que YA existe en el
repositorio con su cita o etiqueta (Referencias del Laboratorio respiratorio, información educativa, referencias de
EEG, teoría de la Academia, panel del VCG); `ORIGINS` dice de qué archivo sale cada tema y
`tests/test_fase1_t2_teoria.py` comprueba que cada capa aparece, literal, en ese archivo. Una capa sin contenido con
fuente se omite (sin relleno) y queda en `PENDING_LAYERS` como contenido pendiente para la firma de Luis.

Pulido profesional (2026-11-16): Luis firmó `docs/contenido/teoria_citada.md` (temas 1 a 10). Es la ÚNICA fuente de texto
médico nuevo: los temas `SIGNED_*` copian sus líneas tal cual, con su clave de cita ([K2007], [MCM]...) enlazada a la
página Bibliografía (`app/supermodules/bibliography.py`). La tabla de 12 derivaciones (sin cita) se sustituyó por la
tabla de isquemia del tema 5, con su advertencia.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import streamlit as st

from app.supermodules.respiratory_lab.views import APNEA_CITATION, EDUCATION_CITATION
from app.utils.design_system import TheoryTopic
from clinical.calculators import NEWS2_CITATION
from clinical.eeg_references import KANE_2017

BERRY_2012 = APNEA_CITATION.split(": caída")[0]          # «Berry RB et al. J Clin Sleep Med 2012;8(5):597–619 (AASM)»

RESP_VIEWS = "app/supermodules/respiratory_lab/views.py"
EEG_TEACHING = "app/supermodules/eeg_neuro_lab/teaching.py"
SIGNED_DOC = "docs/contenido/teoria_citada.md"


def _ischemia_table() -> None:
    st.markdown(ISCHEMIA_WARNING)
    st.markdown(
        "| Hallazgo | Qué sugiere | Arteria probable y advertencias |\n"
        "|---|---|---|\n"
        "| Elevación del ST en V1–V4, I, aVL y a menudo aVR | Oclusión proximal de la descendente anterior | La isquemia "
        "de la pared anterior se debe a oclusión de la descendente anterior (DA). |\n"
        "| Elevación del ST sobre todo en V3–V6 | Oclusión distal de la DA | — |\n"
        "| Oclusión de la DA entre la primera rama septal y la primera diagonal | Se respeta el tabique basal | El ST de "
        "V1 no se eleva. |\n"
        "| Elevación del ST en II, III y aVF | Afectación inferior | Coronaria derecha (CD) o circunfleja (Cx), según "
        "cuál dé la descendente posterior (dominancia). Elevación mayor en III que en II sugiere CD. |\n"
        "| Elevación en I y aVL junto con cambios inferiores | Puede acompañar la oclusión de la Cx | — |\n"
        "| Elevación del ST en V3R y V4R (derivaciones derechas) | Afectación del ventrículo derecho | Oclusión proximal "
        "de la CD. |\n"
        "| Descenso del ST en V1–V3 | Patrón llamado \"posterior\" o posterolateral | Puede deberse a CD o Cx; con cambios "
        "inferiores no es posible saber cuál. |\n"
        "| Elevación en aVR y V1 con descenso del ST en 8 o más derivaciones | Sugiere enfermedad de tronco o de tres "
        "vasos | — |"
    )


# ── Temas firmados (docs/contenido/teoria_citada.md, 2026-11-16). Cada línea está, tal cual, en ese documento. ──
SIGNED_ECG_PAPER = TheoryTopic(
    title="El ECG en papel: cómo se registra y se lee",
    idea="Un ECG estándar se registra a 25 mm/s y con una calibración de 10 mm por cada 1 mV, de modo que la cuadrícula "
         "permite leer tiempo y voltaje directamente [MCM].",
    mechanism="- Eje horizontal (tiempo): a 25 mm/s, cada cuadro pequeño (1 mm) equivale a 0.04 s y cada cuadro grande "
              "(5 mm) a 0.2 s [MCM].\n"
              "- Eje vertical (voltaje): la marca de calibración es una deflexión de 10 mm que representa 1 mV; por "
              "tanto, 1 mm equivale a 0.1 mV [MCM].\n"
              "- El formato tradicional de 12 derivaciones las muestra en 4 columnas (I, II, III · aVR, aVL, aVF · "
              "V1–V3 · V4–V6) y puede añadir una o más tiras de ritmo continuas de 10 segundos [K2007].",
    detail="- Para un ECG diagnóstico en adultos, la recomendación es una frecuencia de corte superior de al menos "
           "150 Hz; para lograrla con el error de amplitud por debajo de 1 %, se necesitan datos a 500 muestras por "
           "segundo [K2007].\n"
           "- La frecuencia de corte inferior recomendada es 0.05 Hz, que puede relajarse hasta 0.67 Hz con filtros "
           "digitales lineales de fase cero [K2007].\n"
           "- Un corte superior de 40 Hz invalida las mediciones de amplitud que se usan para clasificar diagnósticos; "
           "los equipos deberían avisar cuando se usa un filtro así [K2007]. Un filtro de 0.5–40 Hz es, por tanto, de "
           "**monitoreo**, no diagnóstico.",
    source="[MCM] · [K2007]",
)

SIGNED_HEART_RATE = TheoryTopic(
    title="Frecuencia cardiaca",
    idea="La frecuencia cardiaca es el número de latidos por minuto; en el ECG se obtiene dividiendo 60 segundos entre "
         "el intervalo RR [MCM].",
    mechanism="- Con ritmo regular: 60 / intervalo RR (en segundos), o contando los cuadros grandes entre dos ondas R "
              "[MCM].\n"
              "- Con ritmo irregular: se cuentan los complejos QRS en 6 segundos y se multiplican por 10 [MCM].",
    detail="En la escala NEWS2, el pulso puntúa: ≤40 lpm, 3 puntos; 41–50, 1; 51–90, 0; 91–110, 1; 111–130, 2; ≥131, "
           "3 [RCP2017].",
    source="[MCM] · [RCP2017]",
)

SIGNED_WAVES = TheoryTopic(
    title="Ondas e intervalos del ECG",
    idea="Cada onda del ECG corresponde a una fase eléctrica del corazón: la P a la despolarización auricular, el QRS a "
         "la despolarización ventricular y la T a la fase final de la repolarización ventricular [MCM].",
    detail="Valores de referencia en adultos [MCM]:\n\n"
           "| Medida | Referencia |\n"
           "|---|---|\n"
           "| Intervalo PR | 0.12 a 0.20 s |\n"
           "| Duración del QRS | 0.06 a 0.11 s |\n"
           "| QT prolongado (corregido con Bazett) | ≥ 0.45 s en hombres; ≥ 0.46 s en mujeres |\n"
           "| Eje eléctrico normal | de −30° a +90° |",
    source="[MCM]",
)

SIGNED_TWELVE_LEADS = TheoryTopic(
    title="Las 12 derivaciones: de dónde salen",
    idea="Las 12 derivaciones son 12 \"miradas\" a la misma actividad eléctrica, obtenidas con electrodos en las "
         "extremidades (plano frontal) y seis electrodos en el tórax (plano horizontal) [K2007].",
    mechanism="- **Derivaciones bipolares de Einthoven:** I = brazo izquierdo − brazo derecho; II = pierna izquierda − "
              "brazo derecho; III = pierna izquierda − brazo izquierdo.\n"
              "- **Terminal central de Wilson:** el promedio de los potenciales de brazo derecho, brazo izquierdo y "
              "pierna izquierda; sirve de referencia para las derivaciones precordiales.\n"
              "- **Derivaciones aumentadas de Goldberger (aVR, aVL, aVF):** cada electrodo de extremidad se compara "
              "con el promedio de los otros dos; su amplitud es 50 % mayor que si se refiriera a la terminal de Wilson.\n"
              "- **Precordiales:** V1, 4.º espacio intercostal en el borde esternal derecho; V2, 4.º espacio en el borde "
              "esternal izquierdo; V3, a medio camino entre V2 y V4; V4, 5.º espacio en la línea medioclavicular; V5, "
              "en el plano horizontal de V4 en la línea axilar anterior; V6, en ese mismo plano en la línea axilar "
              "media.",
    source="[K2007]",
)

# Advertencia del tema 5 (decisión de Luis): la tabla de isquemia sustituye a la tabla de 12 derivaciones sin cita.
ISCHEMIA_WARNING = (
    "La guía de la AHA/ACCF/HRS recomienda **no rotular derivaciones individuales como \"anterior\", \"inferior\" o "
    "\"lateral\"**, sino nombrarlas por su nombre original [W2009]; esta tabla describe qué *sugieren* los cambios del "
    "ST en cada grupo y declara la incertidumbre."
)

SIGNED_ISCHEMIA = TheoryTopic(
    title="Derivaciones e isquemia: qué sugiere cada grupo",
    idea="Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada y, "
         "con menos certeza, hacia la arteria responsable [W2009].",
    detail=_ischemia_table,
    source="[W2009]",
)

SIGNED_NEWS2 = TheoryTopic(
    title="NEWS2: qué es y por qué BIOCORE lo muestra \"parcial\"",
    idea="NEWS2 es una puntuación agregada que estandariza cómo se registran, puntúan y atienden las constantes vitales "
         "para detectar el deterioro agudo [RCP2017].",
    mechanism="- Puntúa seis parámetros: frecuencia respiratoria, SpO₂, presión arterial sistólica, pulso, nivel de "
              "consciencia o confusión nueva, y temperatura. Se suman 2 puntos si el paciente recibe oxígeno "
              "suplementario.\n"
              "- Cada parámetro recibe puntos según cuánto se aleja de lo normal, y los puntos se suman.\n"
              "- Un 3 en un solo parámetro (marcado en rojo) es poco frecuente y motiva una revisión urgente.",
    detail="- Total 0: vigilancia al menos cada 12 horas. Total 1–4 (bajo): valoración por enfermería. Total 5–6 "
           "(medio): revisión urgente por un clínico competente en enfermedad aguda. Total 7 o más (alto): valoración "
           "de emergencia por un equipo con competencia en cuidados críticos.\n"
           "- La escala 2 de SpO₂ se usa en insuficiencia respiratoria hipercápnica confirmada (por lo general EPOC), "
           "con objetivo de 88–92 %, bajo indicación de un clínico. En los demás casos se usa la escala 1.\n"
           "- **Por qué BIOCORE no calcula el total:** el gemelo no dispone de presión arterial en todos los casos, y "
           "no modela temperatura ni consciencia. Sin esos parámetros, un total sería falso; por eso la plataforma "
           "muestra los puntos de cada parámetro disponible y lista lo que falta.",
    source="[RCP2017]",
)

SIGNED_CHEYNE_STOKES = TheoryTopic(
    title="Cheyne-Stokes",
    idea="Es una forma de respiración periódica, con un patrón creciente y decreciente entre apneas o hipopneas "
         "centrales [CS2023].",
    mechanism="Se inicia y se mantiene por cambios en el umbral de apnea y por la fluctuación de la PCO₂: durante la "
              "hiperventilación, la PCO₂ cae por debajo del umbral de apnea y vuelve a provocar una apnea, lo que "
              "sostiene el ciclo. En la insuficiencia cardiaca, la reserva de CO₂ (la diferencia entre el umbral "
              "despierto y en sueño) está reducida [CS2023].",
    detail="Se asocia a insuficiencia cardiaca y a ictus (hasta 20 % de los pacientes con ictus) [CS2023]. La AASM exige "
           "al menos 3 apneas centrales consecutivas con ciclo de 40 s o más y 5 o más eventos por hora en al menos 2 "
           "horas de registro; puede reflejar insuficiencia cardiaca congestiva no reconocida [B2012].",
    source="[CS2023] · [B2012]",
)

SIGNED_BIOT = TheoryTopic(
    title="Biot",
    idea="Grupos de respiraciones profundas y regulares separados por periodos de apnea [AR2025].",
    detail="Se atribuye a daño pontino por ictus, trauma, herniación uncal o intoxicación por opioides [AR2025].",
    source="[AR2025]",
)

SIGNED_VCG = TheoryTopic(
    title="ECG en 3D (vectorcardiograma)",
    idea="El vectorcardiograma representa en el espacio las fuerzas eléctricas que genera el corazón, analizadas en "
         "tres planos [VZ2014].",
    mechanism="Las derivaciones de Frank pueden reconstruirse a partir del ECG de 12 derivaciones. Al comparar métodos, "
              "el de regresión (transformación de Kors) y el basado en un modelo dieron resultados equivalentes y "
              "mejores que el cuasiortogonal; solo 1 de 90 vectorcardiogramas reconstruidos por regresión se juzgó "
              "diagnósticamente distinto del original [KORS1990].",
    detail="La transformación de Kors es de uso común en clínica e investigación, con menor error cuadrático medio que "
           "la inversa de Dower en un estudio con la base PTB [VZ2014].",
    source="[VZ2014] · [KORS1990]",
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
    idea="En un estudio de sueño, el flujo se mide con un sensor térmico oronasal, el esfuerzo con cinturones "
         "toracoabdominales y la oxigenación con pulsioximetría [B2012].",                     # tema 10, firmado
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
    # Cheyne-Stokes pasó a su tema firmado (`SIGNED_CHEYNE_STOKES`, tema 7). La atáxica se queda como descripción de
    # la simulación, sin fisiopatología (decisión de Luis en el tema 7).
    detail="- **Atáxica (descripción de la simulación):** el generador sortea la duración y la profundidad de cada "
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

# Integración con main (2026-11-16): Miguel retiró de `teaching.py` los rangos sin fuente («Gamma: procesamiento
# cognitivo integrado»...) y puso la tabla del glosario IFCN 2017 junto a los bordes del laboratorio; el tema la toma tal
# cual, con su cita.
EEG_BANDS = TheoryTopic(
    title="Bandas del EEG",
    idea="El EEG se describe por bandas de frecuencia con nombre griego [IFCN2017].",           # tema 8, firmado
    detail="| Banda | Glosario IFCN 2017 | Este laboratorio |\n"
           "|---|---|---|\n"
           "| Delta | 0.1 a menos de 4 Hz | 0.5–3.5 Hz |\n"
           "| Theta | 4 a menos de 8 Hz | 4–7.5 Hz |\n"
           "| Alfa | 8–13 Hz | 8–12 Hz |\n"
           "| Beta | 14–30 Hz | 13–30 Hz |\n"
           "| Gamma | más de 30, hasta 80 Hz | 30–45 Hz |\n\n"
           "- **Delta:** el sueño profundo (NREM N3) está dominado (≥ 20 %) por ondas delta de 0.5–2 Hz y "
           "más de 75 µV. En la práctica, el límite inferior es 0.5 Hz.\n"
           "- **Alfa:** ritmo de vigilia sobre las regiones posteriores; se ve mejor con los ojos cerrados y se "
           "bloquea con la atención, sobre todo visual.\n"
           "- **Beta:** en vigilia, sobre todo fronto-central; si es difuso puede deberse a fármacos (alcohol, "
           "barbitúricos, benzodiacepinas, anestésicos intravenosos).",
    source=KANE_2017,
)

# El tema del VCG lo sustituye el firmado (`SIGNED_VCG`, tema 9). Las asas P/QRS/T y el ángulo QRS-T (Oehler 2014, ahora
# con su referencia completa) siguen en el panel del VCG, debajo, en la misma página.

# Tema -> archivo(s) de donde sale su texto (la prueba busca cada capa, literal, en alguno de ellos).
ORIGINS: Dict[str, Tuple[str, ...]] = {
    NEWS2_RESP.title: (RESP_VIEWS,), HOW_MEASURED.title: (RESP_VIEWS, SIGNED_DOC), PATTERNS.title: (RESP_VIEWS,),
    APNEA_BY_EFFORT.title: (RESP_VIEWS,), OSA_GUIDELINE.title: (RESP_VIEWS,), EEG_BANDS.title: (EEG_TEACHING, SIGNED_DOC),
    **{t.title: (SIGNED_DOC,) for t in (SIGNED_ECG_PAPER, SIGNED_HEART_RATE, SIGNED_WAVES, SIGNED_TWELVE_LEADS,
                                       SIGNED_ISCHEMIA, SIGNED_NEWS2, SIGNED_CHEYNE_STOKES, SIGNED_BIOT, SIGNED_VCG)},
}

LEARN_TOPICS = {
    "teoria": [SIGNED_ECG_PAPER, SIGNED_HEART_RATE, SIGNED_WAVES, SIGNED_TWELVE_LEADS, SIGNED_ISCHEMIA, SIGNED_NEWS2],
    "referencias": [NEWS2_RESP, HOW_MEASURED, PATTERNS, SIGNED_CHEYNE_STOKES, SIGNED_BIOT, APNEA_BY_EFFORT,
                    OSA_GUIDELINE, EEG_BANDS],
    "ecg-3d": [SIGNED_VCG],
}

# Capas omitidas por falta de contenido con fuente (para la firma de Luis): (tema, capa, qué haría falta).
PENDING_LAYERS: List[Tuple[str, str, str]] = [
    (SIGNED_WAVES.title, "mecanismo", "el teoria_citada.md firmado no trae mecanismo para este tema"),
    (SIGNED_ISCHEMIA.title, "mecanismo", "el teoria_citada.md firmado no trae mecanismo para este tema"),
    (SIGNED_BIOT.title, "mecanismo", "el teoria_citada.md firmado no trae mecanismo para este tema"),
    (NEWS2_RESP.title, "mecanismo", "por qué la FR y la SpO₂ alertan de deterioro, con cita"),
    (HOW_MEASURED.title, "mecanismo", "cómo funciona cada sensor (termistor, cinturones, pulsioximetría), con cita"),
    (PATTERNS.title, "mecanismo", "ninguno por decisión de Luis: el patrón atáxico queda como descripción de la "
                                  "simulación, sin fisiopatología ni origen anatómico (no hay fuente abierta verificada)"),
    (OSA_GUIDELINE.title, "idea", "una frase con fuente que resuma la apnea obstructiva del sueño"),
    (EEG_BANDS.title, "mecanismo", "origen de los ritmos (tálamo-corteza), con cita"),
]
