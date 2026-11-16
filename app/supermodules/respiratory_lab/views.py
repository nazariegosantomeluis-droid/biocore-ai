"""Vistas compartidas del Respiratory Lab (arco respiratorio, fase 4, 2026-11-09, Art. I).

Solo muestran lo que tiene golden test, y cada valor lleva su insignia propia (no hay una insignia global de
"validado": la apnea mixta sigue PENDING_VALIDATION):

- [Validado por fuente]: banda NEWS2 de la FR, apnea (≥ 90 % de caída durante ≥ 10 s, Berry 2012, AASM).
- [Criterio BIOCORE] metodología propia / valor BIOCORE: FR (60 / media de intervalos), duración del ciclo, tipo por esfuerzo
  (Criterio BIOCORE), tasa equivalente por hora de registro, SpO₂ del modelo BIOCORE, Tc (Valor BIOCORE).
- [Heurística]: descripción del patrón respiratorio e irregularidad del generador atáxico.
- [Pendiente de validación]: apnea mixta.

Siguen fuera: hipopneas, relación I:E, ODI y la categoría de severidad (vive en Calculadoras Clínicas).
"""

from dataclasses import replace
from typing import List, Optional

import streamlit as st

from app.utils.design_system import BADGES, render_metric_card
from clinical.calculators import NEWS2_CITATION, news2_respiratory_rate_score
from educational.quiz_bank import numeric_choices
from src.signals.respiration.respiratory_analyzer import DURATION_CRITERION_LABEL

SPO2_PROVENANCE = "Simulación — modelo BIOCORE: Tc valor BIOCORE; r y recuperación, Howarth 2026"
EDUCATION_CITATION = (
    "Epstein LJ, Kristo D, Strollo PJ Jr, et al. Clinical guideline for the evaluation, management and long-term care of "
    "obstructive sleep apnea in adults. J Clin Sleep Med 2009;5(3):263–276 (AASM)"
)
APNEA_CITATION = "Berry RB et al. J Clin Sleep Med 2012;8(5):597–619 (AASM): caída ≥ 90 % de la excursión durante ≥ 10 s"
TC_LABEL = "Valor BIOCORE (la fuente, Hsia 2026, solo da el límite normal < 20 s)"
EVENT_TYPE_LABELS = {
    "central": "central",
    "obstructive": "obstructiva",
    "mixed": "mixta (PENDING_VALIDATION)",
    "unknown": "sin canal de esfuerzo",
}

# Por debajo de este coeficiente de variación de los intervalos entre inspiraciones el patrón se describe como regular.
# HEURISTIC (decisión firmada de la fase 4): sin fuente clínica.
PATTERN_REGULAR_CV = 0.10
# Una desaturación se muestra como tal a partir de 3 puntos bajo la basal (el 3 % de Berry 2012 para desaturación).
DESATURATION_NOTE_POINTS = 3.0

BADGE_LEGEND = " · ".join(BADGES.label(b) for b in (BADGES.CLINICAL, BADGES.METHOD, BADGES.HEURISTIC, BADGES.PENDING))


# ----------------------------------------------------------------------------------------------- texto (funciones puras)
def fr_band_text(analysis) -> Optional[str]:
    """Banda NEWS2 de la FR redondeada (.5 hacia arriba, ya hecho por el analizador). No es un diagnóstico."""
    n = analysis.respiratory_rate_rounded
    if n is None:
        return None
    points = news2_respiratory_rate_score(n)
    if points == 0:
        return f"dentro de 12–20 (NEWS2); {n}/min redondeada"
    return f"fuera de 12–20 (NEWS2): {points} punto(s); {n}/min redondeada"


def interval_cv(analysis) -> Optional[float]:
    """Coeficiente de variación de los intervalos entre inspiraciones (DE / media); None si no hay FR."""
    if analysis.rr_variability is None or not analysis.cycle_duration_s:
        return None
    return analysis.rr_variability / analysis.cycle_duration_s


def pattern_description(analysis) -> str:
    """Descripción HEURISTIC del patrón: SOLO describe la señal, no diagnostica."""
    cv = interval_cv(analysis)
    if cv is None:
        head = "Intervalos entre respiraciones: no disponibles (menos de 3 respiraciones)"
    elif cv < PATTERN_REGULAR_CV:
        head = f"Intervalos entre respiraciones regulares (variación del {cv * 100:.0f} %)"
    else:
        head = f"Intervalos entre respiraciones variables (variación del {cv * 100:.0f} %)"
    parts = [head]
    if analysis.event_period_s is not None:
        parts.append(f"Eventos repetidos cada ~{analysis.event_period_s:.0f} s")
    parts.append("Describe la señal; no es un diagnóstico")
    return ". ".join(parts) + "."


def cheyne_stokes_notice(analysis, selected_pattern: Optional[str] = None) -> Optional[str]:
    """Aviso de Cheyne-Stokes: aparece cuando hay eventos repetidos (el patrón periódico lo sugeriría) o cuando el
    patrón simulado es Cheyne-Stokes. Dice por qué un registro de minutos no puede evaluarlo."""
    if analysis.event_period_s is not None or selected_pattern == "cheyne_stokes":
        return analysis.cheyne_stokes_note
    return None


def nadir_outside_record(analysis, spo2_lag_s: Optional[float]) -> bool:
    """¿El nadir de SpO₂ de algún evento cae fuera del registro? Nadir = fin del evento + retardo Tc (modelo BIOCORE).
    Sin Tc no se puede afirmar nada: False."""
    if spo2_lag_s is None:
        return False
    return any(e["end_time"] + spo2_lag_s > analysis.record_duration_s for e in analysis.apnea_events)


def clinical_notes(analysis, spo2_lag_s: Optional[float] = None) -> List[str]:
    """Notas automáticas (decisión 2, fase 4). Sin derivaciones, sin tratamiento, sin «característico de»."""
    notes = []
    n = analysis.respiratory_rate_rounded
    if n is None:
        notes.append(f"FR no disponible: {analysis.signal_status_detail or 'menos de 3 respiraciones'}")
    else:
        points = news2_respiratory_rate_score(n)
        notes.append(f"FR {n}/min: dentro de 12–20 (NEWS2)" if points == 0
                     else f"FR {n}/min: fuera de 12–20 (NEWS2): {points} punto(s)")

    if analysis.apnea_count is None:
        notes.append("Apneas no evaluables: sin señal respiratoria en este registro")
    elif analysis.apnea_count == 0:
        notes.append("No se detectaron apneas en este registro; no descarta apneas en otros")
    else:
        notes.append(
            f"{analysis.apnea_count} apnea(s) de ≥10 s en {analysis.record_duration_s:.0f} s de registro; tasa equivalente "
            f"{analysis.equivalent_rate_per_hour:.0f}/h de registro (extrapolada, sin valor diagnóstico)"
        )

    partial = nadir_outside_record(analysis, spo2_lag_s)
    if analysis.baseline_spo2 - analysis.minimum_spo2 >= DESATURATION_NOTE_POINTS:
        note = (f"Desaturación simulada: nadir {analysis.minimum_spo2:.1f} % a los {analysis.spo2_nadir_time:.0f} s "
                "(modelo BIOCORE)")
        notes.append(note + ("; nadir fuera del registro; el valor mostrado es parcial" if partial else ""))
    elif partial:
        notes.append("Desaturación simulada: aún sin nadir en el registro; nadir fuera del registro; "
                     "el valor mostrado es parcial")
    return notes


def duration_text(event) -> str:
    """Duración de un evento. Con borde gradual (`gradual_edge`) NO se da un número preciso: «≈ X s, borde gradual ± U s»,
    con U = cuánto cambia la duración si la basal se mueve ±2 % (medido; ver `HEURISTICS` del analizador)."""
    if event.get("gradual_edge"):
        return f"≈ {event['duration']:.1f} s, borde gradual ± {event['edge_uncertainty_s']:.1f} s"
    return f"{event['duration']:.1f} s"


# ------------------------------------------------------------------------------------------------------------ tarjetas
def render_rate_cards(analysis) -> None:
    """FR y su banda NEWS2, cada una con su insignia; con su motivo cuando no están disponibles (nunca 0)."""
    if analysis.respiratory_rate is None:
        reason = analysis.signal_status_detail or "no hay suficientes respiraciones"
        render_metric_card("Frecuencia Respiratoria", None, unavailable_reason=reason)
        return
    render_metric_card(
        "Frecuencia Respiratoria", f"{analysis.respiratory_rate:.1f} resp/min",
        provenance=BADGES.METHOD, citation="60 / media de los intervalos entre inspiraciones (golden test)",
    )
    render_band_card(analysis)


def render_band_card(analysis) -> None:
    """Banda NEWS2 de la FR: validada por fuente (RCP 2017); no disponible, con motivo, si no hay FR."""
    band = fr_band_text(analysis)
    if band is None:
        render_metric_card("Banda NEWS2 de la FR", None,
                           unavailable_reason=analysis.signal_status_detail or "FR no disponible")
        return
    render_metric_card("Banda NEWS2 de la FR", band, provenance=BADGES.CLINICAL, citation=NEWS2_CITATION)


def render_apnea_cards(analysis) -> None:
    """Conteo y tiempo total (validados por fuente) y tasa equivalente por hora de registro (extrapolada)."""
    if analysis.apnea_count is None:
        render_metric_card("Apneas (≥ 10 s, caída ≥ 90 %)", None,
                           unavailable_reason="no evaluable: sin señal respiratoria en este registro")
        return
    truncated = sum(1 for e in analysis.apnea_events if e["truncated"])
    detail = f" ({truncated} recortada(s) por el final del registro)" if truncated else ""
    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric_card("Apneas (≥ 10 s, caída ≥ 90 %)", f"{analysis.apnea_count}{detail}",
                           provenance=BADGES.CLINICAL, citation=APNEA_CITATION)
    with c2:
        approx = "≈ " if any(e.get("gradual_edge") for e in analysis.apnea_events) else ""
        render_metric_card("Tiempo total de apnea", f"{approx}{analysis.apnea_total_time_s:.1f} s",
                           provenance=BADGES.CLINICAL, citation=APNEA_CITATION)
    with c3:
        render_metric_card(
            "Tasa equivalente por hora de registro (extrapolada, sin valor diagnóstico)",
            f"{analysis.equivalent_rate_per_hour:.0f} /h", provenance=BADGES.METHOD,
        )


def render_events_table(analysis) -> None:
    """Tabla de eventos con tipo y bordes declarados; los no evaluables se listan aparte y no cuentan."""
    if analysis.apnea_count is None:
        st.info("Sin señal respiratoria evaluable: no se evalúan apneas (no es lo mismo que «0 apneas»).")
        return
    if analysis.apnea_events:
        rows = []
        for e in analysis.apnea_events:
            b = e["baseline"]
            kind = EVENT_TYPE_LABELS.get(e["type"], e["type"])
            rows.append({
                "Inicio (s)": round(e["start_time"], 1),
                "Duración": duration_text(e),
                "Tipo (Criterio BIOCORE)": (f"{BADGES.tag(BADGES.PENDING)} {kind}" if e["mixed_pending"] else f"{BADGES.tag(BADGES.METHOD)} {kind}"),
                "Borde": "recortado por el final del registro" if e["truncated"] else "completo",
                "Línea basal": f"{b['n_breaths']} respiraciones previas, {b['window_s']:.0f} s; {b['rule']}"
                               + (" — registro corto: basal disponible declarada" if b["declared_short"] else ""),
            })
        st.dataframe(rows, hide_index=True, width="stretch")
        if any(e["mixed_pending"] for e in analysis.apnea_events):
            st.caption(f"{BADGES.tag(BADGES.PENDING)} Mixta: PENDING_VALIDATION (la definición del manual AASM no está verificada); "
                       "se calcula y se marca.")
        st.caption(
            f"{BADGES.tag(BADGES.CLINICAL)} Apnea = caída ≥ 90 % de la excursión respecto a la línea basal previa durante ≥ 10 s "
            "(Berry 2012, AASM). "
            f"{BADGES.tag(BADGES.METHOD)} Tipo: «esfuerzo ausente» = caída ≥ 90 % del esfuerzo respecto a su basal (Criterio BIOCORE)."
        )
        st.caption(f"{BADGES.tag(BADGES.METHOD)} Duración: {DURATION_CRITERION_LABEL} (excursión < 10 % de la basal, medida muestra a muestra).")
        if any(e.get("gradual_edge") for e in analysis.apnea_events):
            st.caption("«≈ X s, borde gradual ± U s»: U es cuánto cambia la duración del evento si la basal (y con ella el umbral "
                       "del 10 %) se mueve un 2 %, el p95 medido del error de la basal del detector. Puede ser grande en un borde "
                       "gradual: la señal cruza el 10 % de la basal muy despacio (cola de la modulación o respiración somera "
                       "cercana al umbral) y un cambio pequeño del umbral mueve el borde varios segundos. No es un número preciso.")
    else:
        st.success("No se detectaron apneas de ≥ 10 s en este registro (no descarta apneas en otros registros).")
    for e in analysis.non_evaluable_events:
        st.warning(f"No evaluable (no cuenta): evento de ~{e['duration']:.0f} s desde {e['start_time']:.0f} s — {e['reason']}.")


def render_pattern_cards(analysis, selected_pattern: Optional[str] = None, ground_truth: Optional[dict] = None) -> None:
    """Descripción del patrón (HEURISTIC), aviso de Cheyne-Stokes e irregularidad del generador atáxico (HEURISTIC)."""
    render_metric_card("Patrón (descripción de la señal)", pattern_description(analysis), provenance=BADGES.HEURISTIC,
                       citation=f"umbral de variación {PATTERN_REGULAR_CV:.0%} sin fuente clínica")
    notice = cheyne_stokes_notice(analysis, selected_pattern)
    if notice:
        st.warning(notice)
    if ground_truth and ground_truth.get("pattern") == "ataxic" and "irregularity" in ground_truth:
        render_metric_card("Irregularidad pedida al generador (CV de duración y profundidad por respiración)",
                           f"{ground_truth['irregularity']:.2f}", provenance=BADGES.HEURISTIC,
                           citation="0.20 por defecto; sin fuente clínica")


def render_clinical_notes(analysis, spo2_lag_s: Optional[float] = None) -> None:
    st.markdown("**Notas automáticas** (describen la señal simulada; no son un diagnóstico)")
    for note in clinical_notes(analysis, spo2_lag_s):
        st.markdown(f"- {note}")


def render_calculator_link() -> None:
    """Enlace a la calculadora de severidad (el lab no categoriza: su registro dura minutos)."""
    st.caption(
        "La severidad de la apnea del sueño se calcula con un índice **por hora de sueño** (Epstein 2009); este laboratorio no la "
        "muestra porque su registro dura minutos."
    )
    from app.utils import navigation as nav

    nav.link("calculadoras", "Abrir la calculadora de severidad (Calculadoras clínicas → Escalas)", icon="🧮")


def render_spo2_cards(analysis) -> None:
    """SpO2 basal y mínima del modelo de eventos (fase 2b): con su procedencia de simulación. Las métricas «Tiempo <90 %»
    y «<85 %» se retiraron (fase 4.1): sus umbrales no tenían cita."""
    kw = dict(provenance=BADGES.METHOD, citation=SPO2_PROVENANCE)
    cols = st.columns(2)
    with cols[0]:
        render_metric_card("SpO2 Basal", f"{analysis.baseline_spo2:.1f}%", **kw)
    with cols[1]:
        render_metric_card("SpO2 Mínimo", f"{analysis.minimum_spo2:.1f}%", **kw)


def render_hidden_notice() -> None:
    st.info(
        "**Sigue fuera** (sin golden test o sin criterio firmado): hipopneas, relación I:E, ODI y la categoría de "
        "severidad (vive en Calculadoras Clínicas). La apnea **mixta** se calcula y se marca [Pendiente de validación] (PENDING_VALIDATION)."
    )


# ------------------------------------------------------------------------------------------------- Guardar al gemelo
# Mapeo valor del laboratorio → campo del UPS respiratorio. Solo se escribe lo que significa EXACTAMENTE lo mismo.
TWIN_FIELDS_WRITTEN = ("respiratory_rate", "spo2")


def build_twin_state(analysis, patient_id: str, pattern_display: str):
    """`UnifiedPhysiologicalState` con SOLO los dos valores del laboratorio que coinciden en significado con un campo
    del UPS: `respiratory_rate` (FR = 60 / media de los intervalos entre inspiraciones, resp/min) y `spo2` (SpO₂ BASAL del
    registro, %, NO el nadir). Procedencia SIMULACION con su criterio en `source_detail`.

    Pasa por los gates anti-órgano-fantasma de `from_digital_twin_organism()` (sin dato cardíaco/neuro/muscular esos
    dominios quedan vacíos). Después se descartan los descriptores DERIVADOS del dominio respiratorio (health_score,
    risk_score, hypoxia_risk, apnea_risk, tissue_oxygenation): el organismo los calcula con una fórmula propia y con
    `ahi = 0` por defecto (`get(..., default)`), un dato que este laboratorio NO tiene — escribirlos sería presentar un
    valor por defecto como medición (Art. I). La tasa extrapolada de apneas NO va a `ahi`: es por hora de REGISTRO y
    el índice del UPS es por hora de sueño (con hipopneas)."""
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from domain.physiology.state import Provenance, from_digital_twin_organism
    from domain.physiology.state.schema import DomainState

    if analysis.respiratory_rate is None:
        raise ValueError("La FR no está disponible en este registro: no hay nada que guardar al gemelo.")
    organism = DigitalTwinOrganism()
    organism.update_from_sensors({"respiratory": {
        "respiratory_rate": float(analysis.respiratory_rate),
        "spo2": float(analysis.baseline_spo2),
    }})
    state = from_digital_twin_organism(
        organism, patient_id, provenance=Provenance.SIMULACION,
        source_detail=(f"respiratory_lab:patron={pattern_display}; respiratory_rate=60/media de los intervalos entre "
                       f"inspiraciones; spo2=SpO2 basal del registro (no el nadir), {SPO2_PROVENANCE}"),
    )
    kept = {k: v for k, v in state.respiratory.descriptors.items() if k in TWIN_FIELDS_WRITTEN}
    return replace(state, respiratory=DomainState(domain="respiratory", descriptors=kept))


def render_save_to_twin(analysis, pattern_display: str, key: str) -> None:
    """Botón explícito (nunca automático). Escribe solo FR y SpO₂ basal, con procedencia de simulación."""
    st.markdown("#### 🔗 Guardar estado al gemelo")
    st.caption(
        "Escribe **solo dos valores** al Unified Physiological State: la **FR** (60 / media de los intervalos entre "
        "inspiraciones) y la **SpO₂ basal** del registro (no el nadir), con procedencia «Simulación» y su criterio. "
        "**No escribe** el conteo de apneas ni la tasa por hora de registro (no hay un campo con ese significado: el índice "
        "de apneas-hipopneas del UPS es por hora de sueño e incluye hipopneas) ni los valores derivados del organismo."
    )
    if analysis.respiratory_rate is None:
        st.warning("Desactivado: la frecuencia respiratoria no está disponible en este registro (no se guarda un valor "
                   "por defecto).")
        return
    if st.button("💾 Guardar FR y SpO₂ basal al gemelo", key=key):
        from app.utils.patient_session import get_active_patient_id, get_active_session_factory
        from domain.physiology.state import save_state

        state = build_twin_state(analysis, get_active_patient_id(), pattern_display)
        with get_active_session_factory()() as session:
            snapshot_id = save_state(session, state)
        st.success(f"Estado guardado al gemelo -- snapshot: {snapshot_id}")
        st.caption(
            f"respiratory: {len(state.respiratory.descriptors)} descriptores "
            f"({', '.join(state.respiratory.descriptors)}); cardiovascular: {len(state.cardiovascular.descriptors)} "
            "(vacío esperado: este laboratorio no mide el corazón)."
        )


def render_clinical_references() -> None:
    """Pestaña «Referencias Clínicas» del laboratorio (tanda 1 de la fase 1: movida aquí SIN cambiar el texto, para
    que también se lea desde Aprender)."""
    st.markdown("### 📚 Referencias Clínicas")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        #### 🫁 Frecuencia respiratoria y SpO₂ según NEWS2

        Puntos NEWS2 de la FR: **12–20 resp/min: 0**; 9–11: 1; 21–24: 2; ≤ 8: 3; ≥ 25: 3. Puntos de la SpO₂ (escala 1):
        **≥ 96 %: 0**; 94–95: 1; 92–93: 2; ≤ 91: 3. Es una puntuación de alerta, no una etiqueta diagnóstica: fuera de 12–20
        se dice «fuera de 12–20 (NEWS2)».

        *Fuente: {NEWS2_CITATION}*

        #### 📊 Patrones

        - **Apnea (Berry 2012, AASM):** caída ≥ 90 % de la excursión del flujo respecto a la línea basal previa durante ≥ 10 s
        - **Cheyne-Stokes (Berry 2012):** ≥ 3 apneas/hipopneas centrales consecutivas separadas por un cambio creciente y decreciente
          de la amplitud, con ciclo ≥ 40 s (típicamente 45–90 s) y ≥ 5 por hora en ≥ 2 h de registro
        - **Atáxica (descripción de la simulación):** el generador sortea la duración y la profundidad de cada respiración
          (irregularidad 0.20, HEURISTIC); no hay afirmación clínica sobre su causa
        """)

    with col2:
        st.markdown(f"""
        #### 😴 Clasificación de la apnea por esfuerzo

        Berry 2012 (§4.1.1, AASM): la clasificación de una apnea como obstructiva, mixta o central **se basa en el esfuerzo
        respiratorio**. Todas cumplen la misma regla de apnea (caída ≥ 90 % de la excursión del flujo durante ≥ 10 s).

        - **Central (Criterio BIOCORE):** esfuerzo ausente (caída ≥ 90 % del esfuerzo respecto a su basal)
        - **Obstructiva (Criterio BIOCORE):** esfuerzo presente; Berry 2012 señala que el movimiento paradójico del tórax y el
          abdomen se observa a menudo durante una apnea u hipopnea obstructiva
        - **Mixta:** [Pendiente de validación] (PENDING_VALIDATION; se calcula y se marca; la definición del manual no está verificada)
        - **Obesidad:** Epstein 2009 incluye la obesidad (IMC > 35) entre los pacientes de alto riesgo que deben evaluarse
          para apnea obstructiva del sueño
        - **Obstructiva, mecanismo (Epstein 2009):** los signos, síntomas y consecuencias son resultado directo del colapso
          repetitivo de la vía aérea superior

        #### 📏 Severidad por índice de eventos por hora

        Se calcula con la calculadora de **Calculadoras Clínicas → Escalas** (Epstein 2009): es un índice por hora de
        sueño y este laboratorio solo registra minutos.

        *Fuente: {EDUCATION_CITATION}*
        """)

    st.markdown("---")

    st.markdown(f"""
    #### 💡 Implicaciones clínicas (texto educativo; no se deriva de la señal simulada)

    La guía de práctica clínica de la AASM pide evaluar, en una persona con apnea obstructiva del sueño, las condiciones
    secundarias que pueden aparecer como resultado de ella: hipertensión, accidente cerebrovascular, infarto de
    miocardio, cor pulmonale, menor alerta diurna y accidentes de tráfico.

    **Opciones de tratamiento que enumera la guía** (la estrategia la decide un clínico con la persona, caso a caso):
    dispositivos de presión positiva en la vía aérea (CPAP), dispositivos orales, tratamientos conductuales (pérdida de
    peso, ejercicio, terapia posicional, evitar alcohol y sedantes antes de dormir), cirugía y tratamientos adyuvantes.

    *Fuente: {EDUCATION_CITATION}*
    """)



# ------------------------------------------------------------------------------------------------- cuestionario
# Tanda 1 de la fase 1 (2026-11-15, Art. I): el cuestionario se respondía solo. Las tres preguntas conceptuales llevaban
# «✓» en el texto de la opción correcta, que además venía preseleccionada, y la corrección («✅ Correcto») aparecía antes
# de que el estudiante eligiera nada; las dos numéricas también preseleccionaban la primera opción. Ahora: ninguna opción
# preseleccionada (`index=None`), ningún «✓» en las opciones (la correcta se guarda aparte y no siempre es la primera) y
# ninguna corrección hasta que el estudiante responde. Los textos de las preguntas y de la corrección no cambiaron.
CONCEPT_QUIZ = {
    "Diferenciación Apnea": dict(
        question="""
        **Pregunta:** Según Berry 2012 (AASM), ¿en qué se basa la clasificación de una apnea como obstructiva, mixta o central?

        Pista: mira la pared torácica y el movimiento abdominal durante las apneas.
        """,
        options=[
            "En la duración: las centrales duran 10 s o más y las obstructivas menos",
            "En el esfuerzo respiratorio",
            "En la caída del flujo: las centrales caen ≥ 90 % y las obstructivas ≥ 30 %",
        ],
        correct=1,
        ok=("✅ Correcto: Berry 2012 (§4.1.1) clasifica la apnea según el esfuerzo respiratorio. En este laboratorio, "
            "central = esfuerzo ausente y obstructiva = esfuerzo presente (Criterio BIOCORE); la mixta queda "
            "[Pendiente de validación] (PENDING_VALIDATION)."),
        wrong=("❌ Incorrecto: todas las apneas cumplen la misma regla: caída ≥ 90 % de la excursión del flujo durante ≥ 10 s "
               "(Berry 2012); una caída de ≥ 30 % es el criterio de hipopnea, no de apnea. Lo que las separa es el esfuerzo "
               "respiratorio."),
    ),
    "Factores de Riesgo": dict(
        question="""
        **Pregunta:** Según la guía de la AASM (Epstein 2009), ¿cuál de estos pacientes pertenece a un grupo de ALTO RIESGO
        que debe evaluarse para apnea obstructiva del sueño?
        """,
        options=[
            "Una persona de 25 años con IMC 22, sin síntomas ni otras condiciones",
            "Una persona sana que viaja como pasajera",
            "Una persona con obesidad (IMC > 35)",
        ],
        correct=2,
        ok=("✅ Correcto: la guía de la AASM (Epstein 2009) lista como alto riesgo la obesidad (IMC > 35), la insuficiencia "
            "cardíaca congestiva, la fibrilación auricular, la hipertensión refractaria al tratamiento, la diabetes tipo 2, "
            "el ACV, las disritmias nocturnas, la hipertensión pulmonar, las poblaciones de conducción de alto riesgo y la "
            "evaluación previa a cirugía bariátrica."),
        wrong=("❌ Incorrecto: esa persona no figura en la lista de alto riesgo de la guía de la AASM (Epstein 2009: obesidad "
               "con IMC > 35, insuficiencia cardíaca congestiva, fibrilación auricular, hipertensión refractaria, diabetes "
               "tipo 2, ACV, disritmias nocturnas, hipertensión pulmonar, conducción de alto riesgo, cirugía bariátrica)."),
    ),
    "Correlación cardiovascular (guía AASM)": dict(
        question="""
        **Pregunta:** ¿Qué condiciones del ritmo cardíaco figuran entre los pacientes de alto riesgo que la guía de la AASM
        (Epstein 2009) pide evaluar para apnea obstructiva del sueño?
        """,
        options=[
            "Ninguna: la guía no menciona alteraciones del ritmo cardíaco",
            "Fibrilación auricular y disritmias nocturnas",
            "Solo la taquicardia sostenida",
        ],
        correct=1,
        ok=("✅ Correcto: la fibrilación auricular y las disritmias nocturnas figuran en la lista de alto riesgo de la guía. "
            "Berry 2012 añade que un estudio con la definición de hipopnea de ≥ 3 % de desaturación encontró asociación "
            "entre el índice de eventos y la fibrilación auricular o la ectopia ventricular compleja en hombres mayores "
            "sin insuficiencia cardíaca declarada."),
        wrong=("❌ Incorrecto: la guía de la AASM (Epstein 2009) sí las menciona: la fibrilación auricular y las disritmias "
               "nocturnas están en su lista de pacientes de alto riesgo."),
    ),
}
SIGNAL_QUIZ = ("Frecuencia de esta señal", "Contar las apneas de esta señal")


def render_quiz(analysis=None, key_prefix: str = "") -> None:
    """Cuestionario del laboratorio. Con `analysis` (la señal actual) incluye las dos preguntas cuya respuesta sale de un
    valor con golden test (FR y conteo de apneas); sin él (p. ej. desde Practicar) solo las tres conceptuales."""
    st.markdown("### ❓ Cuestionario Interactivo - Apnea del Sueño")
    options = list(CONCEPT_QUIZ)
    if analysis is not None:
        options += list(SIGNAL_QUIZ)
    quiz_type = st.radio("Seleccionar Tipo de Pregunta:", options, key=f"{key_prefix}resp_quiz_type" if key_prefix else None)
    if analysis is None:
        st.caption("Las dos preguntas sobre la señal (frecuencia y conteo de apneas) están en el laboratorio respiratorio, "
                   "porque su respuesta sale de la señal simulada que estás viendo.")

    if quiz_type == "Frecuencia de esta señal":
        st.info("**Pregunta:** ¿Cuál es la frecuencia respiratoria de la señal actual (redondeada al entero)?")
        correct = analysis.respiratory_rate_rounded
        if correct is None:
            st.warning("La frecuencia no está disponible en este registro: no hay pregunta que responder.")
            return
        # Integración 2026-11-16 (Art. I): con `sorted({c, c+4, c-4, c+9})` la correcta quedaba casi siempre segunda;
        # `numeric_choices` reparte su lugar (determinista por el valor, para que no cambie en cada rerun).
        choices = numeric_choices(correct, 4, f"fr:{correct}", minimum=1)
        picked = st.radio("Tu respuesta (resp/min):", choices, index=None, key=f"{key_prefix}resp_quiz_fr")
        if picked is None:
            return
        if picked == correct:
            st.success(f"✅ Correcto: {analysis.respiratory_rate:.1f}/min medida entre inspiraciones; {fr_band_text(analysis)}.")
        else:
            st.error("❌ Incorrecto: mide el tiempo entre dos inspiraciones consecutivas: FR = 60 / ese intervalo (s).")
        return

    if quiz_type == "Contar las apneas de esta señal":
        st.info("**Pregunta:** ¿Cuántas apneas (caída ≥ 90 % durante ≥ 10 s) hay en la señal actual?")
        correct = analysis.apnea_count
        if correct is None:
            st.warning("Este registro no tiene señal respiratoria evaluable: no hay pregunta que responder.")
            return
        choices = numeric_choices(correct, 1, f"apneas:{correct}", minimum=0)
        picked = st.radio("Tu respuesta:", choices, index=None, key=f"{key_prefix}resp_quiz_apneas")
        if picked is None:
            return
        if picked == correct:
            st.success(f"✅ Correcto: {correct} apnea(s) de ≥ 10 s en {analysis.record_duration_s:.0f} s de registro.")
        else:
            st.error("❌ Incorrecto: busca los tramos con flujo casi ausente (≥ 90 % de caída) y mídelos: solo cuentan los de "
                     "≥ 10 s.")
        return

    item = CONCEPT_QUIZ[quiz_type]
    st.info(item["question"])
    answer = st.radio("Tu respuesta:", item["options"], index=None, key=f"{key_prefix}resp_quiz_{quiz_type}")
    if answer is None:
        return
    if answer == item["options"][item["correct"]]:
        st.success(item["ok"])
    else:
        st.error(item["wrong"])


def render_education_topics() -> None:
    """«Información educativa» del laboratorio (tanda 1 de la fase 1: movida aquí SIN cambiar el texto; el
    laboratorio la sigue mostrando en su barra lateral y Aprender la muestra en la página)."""
    st.markdown("### 📚 INFORMACIÓN EDUCATIVA")

    edu_section = st.radio("Seleccionar Tema:", [
        "Introducción",
        "Patrones Clínicos",
        "Apnea del Sueño",
        "Correlación cardiovascular (guía AASM)"
    ], key="edu_sidebar")

    if edu_section == "Introducción":
        st.markdown("""
        #### ¿Cómo se mide? (Berry 2012, AASM)

        - **Flujo de aire:** sensor térmico oronasal (termistor, termopar o PVDF)
        - **Esfuerzo respiratorio:** cinturones toracoabdominales
        - **Oxígeno:** pulsioximetría (SpO2)

        En este laboratorio las tres señales son **simuladas**.
        """)

    elif edu_section == "Patrones Clínicos":
        st.markdown("""
        #### 🫁 Frecuencia respiratoria (NEWS2)

        - 12–20 resp/min: 0 puntos
        - 9–11 resp/min: 1 punto; 21–24: 2 puntos
        - ≤ 8 o ≥ 25 resp/min: 3 puntos
        - Fuera de 12–20 se dice «fuera de 12–20 (NEWS2)», sin etiqueta diagnóstica

        **Cheyne-Stokes (Berry 2012):**
        - Se puntúa con ≥ 3 apneas/hipopneas centrales consecutivas con ciclo ≥ 40 s y ≥ 5 por hora en ≥ 2 h de registro
        - Puede reflejar una insuficiencia cardíaca congestiva no reconocida
        """)

    elif edu_section == "Apnea del Sueño":
        st.markdown("""
        #### 😴 Datos de la guía AASM (Epstein 2009)

        - **Prevalencia:** al menos 2–4 % de la población adulta
        - **Condiciones secundarias que la guía pide evaluar:** hipertensión, ACV, infarto de miocardio, cor pulmonale,
          menor alerta diurna y accidentes de tráfico

        **Síntomas que la guía pide evaluar:**
        - Apneas presenciadas
        - Ronquido
        - Ahogo o asfixia nocturnos
        - Somnolencia excesiva no explicada por otros factores

        **Diagnóstico:** la guía acepta dos métodos objetivos: polisomnografía en laboratorio y monitores portátiles en casa
        """)

    else:  # Correlación
        st.markdown("""
        #### 💓 Correlación cardiovascular (guía AASM)

        - Epstein 2009: las consecuencias de la apnea obstructiva del sueño son resultado directo de las alteraciones que produce
          el colapso repetitivo de la vía aérea superior: fragmentación del sueño, hipoxemia, hipercapnia, grandes oscilaciones
          de la presión intratorácica y aumento de la actividad simpática
        - La fibrilación auricular y las disritmias nocturnas figuran entre los pacientes de alto riesgo que se evalúan para AOS
        - Berry 2012 cita un estudio que asoció el índice de eventos con fibrilación auricular o ectopia ventricular compleja
          en hombres mayores sin insuficiencia cardíaca declarada
        """)
