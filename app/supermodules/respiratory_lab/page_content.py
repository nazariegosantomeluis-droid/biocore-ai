"""
Respiratory Lab - Phase 2 of Biomedical Signal Visualizer
Comprehensive respiratory monitoring and sleep apnea education

Features:
- Multiple breathing patterns (normal, apnea, irregular, etc.)
- Real-time respiratory analysis
- SpO2 integration and monitoring
- Sleep apnea severity assessment
- Interactive educational content
- Cardiovascular correlation (only what the cited guidelines say)
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

# Add paths for imports
# Rutas ajustadas (Tanda de eliminación de pages_legacy, Movimiento 1, 2026-07-13):
# este archivo vivía en app/pages_legacy/ (2 niveles bajo la raíz del repo) y ahora
# vive en app/supermodules/respiratory_lab/ (3 niveles) — un nivel más de
# profundidad, así que el cálculo de la raíz del repo necesita un salto más.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.signals.respiration import (
    RespiratorySignalGenerator,
    RespiratoryPattern,
    RespiratoryAnalyzer,
    ImpossibleParameters,
)

# Consolidación Visual Tanda 3 (2026-09-21): `PALETTE`/`BADGES`/
# `render_metric_card`/`render_section_header` -- fuente única de color y
# de tarjeta de métrica (`app/utils/design_system.py`), reemplaza el
# `<style>` propio de este archivo (retirado más abajo) y los ~24
# `st.metric()` a mano repartidos por las pestañas.
from app.utils.design_system import BADGES, PALETTE, render_metric_card, render_section_header
from app.supermodules.respiratory_lab import views
from educational.quiz_bank import QuizQuestion, balance_positions, numeric_choices
from clinical.calculators import NEWS2_CITATION  # noqa: F401  (la banda de FR vive en views.fr_band_text)

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# `st.set_page_config()` y `render_sidebar_navigation()` retirados
# (2026-08-20, Capa 2 Fase 2.1, cierre): vestigios de la arquitectura
# Streamlit multipágina anterior. Este archivo solo corre anidado bajo
# `app/main.py` (vía `runpy.run_path()` desde `respiratory_lab/pages.py`),
# que ya configuró la página una sola vez al inicio. Ver CHANGELOG.md.

# Consolidación Visual Tanda 3 (2026-09-21): background/color de esta
# tarjeta decorativa migrados de hex propios a `PALETTE.BACKGROUND`/
# `PALETTE.ACCENT_ON_DARK` -- coinciden exactamente con los valores viejos
# (#0f172a/#8ecae6), ahora referenciando la fuente única en vez de
# repetirla. El borde (#1f2937) no corresponde a ningún token de
# `PALETTE` -- se deja igual, no se inventa una correspondencia.
st.markdown(f"""
    <div style='padding: 16px; border-radius: 16px; background: {PALETTE.BACKGROUND}; border: 1px solid #1f2937; margin-bottom: 24px;'>
        <h2 id="panel-respiratorio" style='color: {PALETTE.ACCENT_ON_DARK};'>💨 Laboratorio Respiratorio</h2>
        <p>Experimenta con patrones de una respiración <strong>simulada</strong>, mira la SpO2 del modelo BIOCORE y compara lo que
        mide el detector con lo que el generador sabe que produjo.</p>
        <ul>
            <li><strong>Normal (simulación):</strong> respiración regular con SpO2 estable.</li>
            <li><strong>Apnea (simulación):</strong> el flujo cae ≥ 90 % durante ≥ 10 s y el modelo BIOCORE produce una desaturación.</li>
            <li><strong>Taquipnea / Bradipnea (simulación):</strong> el generador multiplica la FR pedida por 1.5 (tope 40/min) o por 0.5 (piso 6/min).</li>
        </ul>
    </div>
""",
    unsafe_allow_html=True,
)

# Consolidación Visual Tanda 3 (2026-09-21): `<style>` propio retirado --
# `inject_global_theme()` (`app/main.py`) ya cubre fondo/texto globales con
# los mismos tokens; `.metric-card`/`.clinical-note`/`.normal-note` no se
# usaban en ningún `<div>` de este archivo (CSS muerto, confirmado por
# grep -- cero referencias a esas clases fuera de esta declaración). El
# acento de pestañas (`.stTabs`) se pierde con el retiro -- pérdida
# cosmética menor, consistente con el resto de la migración de Tanda 3
# (mismo criterio de retiro seguro que ECG-12/EEG Neuro Lab, ver
# CHANGELOG.md).

# ═══════════════════════════════════════════════════════════════
# SIDEBAR CONFIGURATION
# ═══════════════════════════════════════════════════════════════

st.sidebar.markdown("# 💨 LABORATORIO RESPIRATORIO")
st.sidebar.markdown("---")

# Pattern selection
respiratory_patterns = {
    "Normal (Quiet Breathing)": "normal",
    "Taquipnea (Breathing Fast)": "tachypnea",
    "Bradipnea (Breathing Slow)": "bradypnea",
    "Apnea Central": "apnea_central",
    "Apnea Obstructiva": "apnea_obstructive",
    "Cheyne-Stokes": "cheyne_stokes",
    "Respiración Atáxica": "ataxic",
}

selected_pattern_display = st.sidebar.selectbox(
    "🫁 Seleccionar Patrón Respiratorio",
    list(respiratory_patterns.keys()),
    index=0
)
selected_pattern = respiratory_patterns[selected_pattern_display]

st.sidebar.markdown("### ⚙️ Parámetros Respiratorios")

# Respiratory parameters
col1, col2 = st.sidebar.columns(2)

with col1:
    rr = st.number_input(
        "Frecuencia Respiratoria (resp/min)",
        min_value=6,
        max_value=40,
        value=15,
        step=1,
        help="12–20 resp/min puntúa 0 en NEWS2 (RCP 2017)"
    )

with col2:
    tv = st.number_input(
        "Volumen Corriente (L)",
        min_value=0.1,
        max_value=1.5,
        value=0.5,
        step=0.1,
        help="Volumen corriente que pide la simulación (la escala de la señal no está calibrada)"
    )

# Un ValueError por parámetros imposibles se muestra JUNTO al control afectado (sin st.stop(): las demás pestañas
# se siguen dibujando). Cada ranura se rellena más abajo si la validación falla.
slot_rr = st.sidebar.empty()

col3, col4 = st.sidebar.columns(2)

with col3:
    insp_time = st.number_input(
        "Tiempo Inspiración (s)",
        min_value=0.3,
        max_value=3.0,
        value=1.0,
        step=0.1
    )

with col4:
    # Arco respiratorio, fase 2a (2026-11-07): el control vuelve a estar activo porque el generador ya
    # lo usa. 0.0 = automático: la espiración ocupa el resto del ciclo (lo que el generador hacía siempre,
    # cuando este control no hacía nada). Un valor > 0 acota el flujo espiratorio a esa duración y deja
    # el resto del ciclo en pausa; inspiración + espiración no pueden superar el ciclo (60 / FR).
    exp_time = st.number_input(
        "Tiempo Espiración (s)",
        min_value=0.0,
        max_value=3.0,
        value=0.0,
        step=0.1,
        help="0 = automático (resto del ciclo). Un valor > 0 acota la espiración y deja pausa telespiratoria; "
             "inspiración + espiración deben caber en el ciclo (60 / FR).",
    )

slot_insp = st.sidebar.empty()

# SpO2 parameters
st.sidebar.markdown("### 🫀 Parámetros de Oxigenación")
st.sidebar.caption(
    f"{views.SPO2_PROVENANCE}. La SpO₂ es estable sin eventos; cada apnea produce una desaturación en el dedo "
    "con retardo Tc (la latencia de las reservas de O₂ no está modelada)."
)

col5, col6 = st.sidebar.columns(2)

with col5:
    baseline_spo2 = st.number_input(
        "SpO2 Basal (%)",
        min_value=90,
        max_value=100,
        value=98,
        step=1,
        help="SpO₂ basal que simula el modelo BIOCORE"
    )

with col6:
    min_spo2 = st.number_input(
        "SpO2 Mínimo (%)",
        min_value=50,
        max_value=95,
        value=85,
        step=1,
        help="Piso de la SpO₂ durante un evento (nunca baja de aquí)"
    )

circulation_delay = st.sidebar.number_input(
    "Retardo circulatorio Tc (s) — Valor BIOCORE",
    min_value=5.0,
    max_value=30.0,
    value=15.0,
    step=1.0,
    help="Tiempo pulmón-dedo: el nadir llega al FIN del evento + Tc. Valor BIOCORE: la fuente (Hsia 2026) solo da el "
         "límite normal < 20 s. Rango 5–30 s.",
)
st.sidebar.caption(f"{BADGES.METHOD} Tc: {views.TC_LABEL}")
slot_spo2 = st.sidebar.empty()

duration = st.sidebar.slider(
    "⏱️ Duración Grabación (s)",
    min_value=30,
    max_value=300,
    value=120,
    step=10
)
slot_dur = st.sidebar.empty()

st.sidebar.markdown("---")

# ═══════════════════════════════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════════════════════════════

def _build_params(pattern, rr, tv, insp, exp, baseline, floor, tc):
    return RespiratoryPattern(
        respiratory_rate=rr,
        tidal_volume=tv,
        inspiration_time=insp,
        expiration_time=(exp if exp > 0 else None),
        pattern_type=pattern,
        baseline_spo2=baseline,
        desaturation_level=floor,
        circulation_delay=tc,
        cheyne_stokes_cycle=60.0,
    )


# Generate respiratory signal
@st.cache_data
def generate_respiration_data(pattern, rr, tv, insp, exp, baseline, floor, tc, duration):
    generator = RespiratorySignalGenerator(sampling_rate=100)
    params = _build_params(pattern, rr, tv, insp, exp, baseline, floor, tc)
    return generator.generate_respiration(duration=duration, params=params)


# Generate analysis
@st.cache_data
def analyze_respiration_data(airflow, time, spo2, chest):
    analyzer = RespiratoryAnalyzer(sampling_rate=100)

    analysis = analyzer.analyze_respiration(
        airflow=airflow,
        time=time,
        spo2=spo2,
        respiratory_effort=chest
    )

    return analysis


# Validación ANTES de generar: el error sale junto al control afectado y la vista clínica se omite sin detener el
# resto de la página (ver VistaClinicaOmitida en pages.py).
_params = _build_params(selected_pattern, rr, tv, insp_time, exp_time, baseline_spo2, min_spo2, circulation_delay)
try:
    RespiratorySignalGenerator.validate_parameters(_params, duration)
except ImpossibleParameters as _err:
    _slot = {
        "respiratory_rate": slot_rr, "tidal_volume": slot_rr,
        "inspiration_time": slot_insp, "expiration_time": slot_insp,
        "circulation_delay": slot_spo2, "desaturation_level": slot_spo2, "desaturation_rate": slot_spo2,
        "resaturation_rate": slot_spo2, "duration": slot_dur,
    }.get(_err.control, slot_insp)
    _slot.error(f"⛔ {_err}")
    st.error("⛔ La vista clínica no se dibuja con estos parámetros: corrige el control marcado en la barra lateral.")
    st.session_state.pop('_respiratory_lab_analysis', None)  # que Investigación no muestre un análisis de OTROS parámetros
    from app.supermodules.respiratory_lab.pages import VistaClinicaOmitida
    raise VistaClinicaOmitida(str(_err))

respiration_data = generate_respiration_data(
    selected_pattern, rr, tv, insp_time, exp_time, baseline_spo2, min_spo2, circulation_delay, duration
)

airflow = respiration_data['airflow']
time_array = respiration_data['time']
spo2 = respiration_data['spo2']
chest = respiration_data['chest_wall']
abdomen = respiration_data['abdomen']

# Perform analysis
analysis = analyze_respiration_data(airflow, time_array, spo2, chest)

# Puente de sesión: expone el análisis ya calculado aquí a la pestaña "Investigación" de respiratory_lab/pages.py
# (sin recalcular). `with tabs[0]:` (Clínica) corre en cada rerun, así que el dato existe cuando la otra pestaña lo lee.
st.session_state['_respiratory_lab_analysis'] = {
    'analysis': analysis,
    'pattern_display': selected_pattern_display,
    'duration': duration,
}

render_section_header(f"Patrón: {selected_pattern_display}")
st.caption(f"Insignias por valor: {views.BADGE_LEGEND}")

# ═══════════════════════════════════════════════════════════════
# METRICS ROW
# ═══════════════════════════════════════════════════════════════

# Fase 3 (2026-11-07, Art. I): solo valores con golden test. Sin tarjetas de patrón ni severidad (ocultas).
col1, col2, col3, col4 = st.columns(4)

with col1:
    views.render_rate_cards(analysis)

with col2:
    if analysis.cycle_duration_s is None:
        render_metric_card("Duración del ciclo", None, unavailable_reason=analysis.signal_status_detail or "sin FR disponible")
    else:
        render_metric_card("Duración del ciclo", f"{analysis.cycle_duration_s:.2f} s", provenance=BADGES.METHOD)

with col3:
    if analysis.apnea_count is None:
        render_metric_card("Apneas (≥ 10 s)", None, unavailable_reason="no evaluable: sin señal respiratoria")
    else:
        render_metric_card("Apneas (≥ 10 s)", f"{analysis.apnea_count}", provenance=BADGES.METHOD)

with col4:
    render_metric_card(
        "SpO2 Mínimo", f"{analysis.minimum_spo2:.1f}%", provenance=BADGES.METHOD, citation=views.SPO2_PROVENANCE,
    )

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# VISUALIZATION TABS
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Señales Respiratorias",
    "🫀 SpO2 Oximetría",
    "📈 Análisis Avanzado",
    "📚 Referencias Clínicas",
    "❓ Cuestionario"
])

with tab1:
    st.markdown("### Señales Respiratorias (Flujo, Pared Torácica, Abdomen)")
    
    # Create respiratory signals visualization
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        subplot_titles=("Flujo de Aire (unidades relativas: la escala absoluta no corresponde al volumen corriente elegido)", "Pared Torácica", "Movimiento Abdominal"),
        vertical_spacing=0.1
    )
    
    # Airflow
    fig.add_trace(
        go.Scatter(
            x=time_array,
            y=airflow,
            name="Flujo de Aire",
            line=dict(color="#8ecae6", width=2),
            fill="tozeroy",
            fillcolor="rgba(142, 202, 230, 0.2)"
        ),
        row=1, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#666", row=1, col=1)
    
    # Chest wall
    fig.add_trace(
        go.Scatter(
            x=time_array,
            y=chest,
            name="Pared Torácica",
            line=dict(color="#1d4ed8", width=2),
            fill="tozeroy",
            fillcolor="rgba(29, 78, 216, 0.2)"
        ),
        row=2, col=1
    )
    
    # Abdomen
    fig.add_trace(
        go.Scatter(
            x=time_array,
            y=abdomen,
            name="Abdomen",
            line=dict(color="#7c3aed", width=2),
            fill="tozeroy",
            fillcolor="rgba(124, 58, 237, 0.2)"
        ),
        row=3, col=1
    )
    
    fig.update_xaxes(title_text="Tiempo (segundos)", row=3, col=1)
    fig.update_yaxes(title_text="Flujo (u. relativas)", row=1, col=1)
    fig.update_yaxes(title_text="Movimiento", row=2, col=1)
    fig.update_yaxes(title_text="Movimiento", row=3, col=1)
    
    fig.update_layout(
        height=700,
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#1a2a4a",
        font=dict(color="#e0e7ff"),
        showlegend=True,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Detected breaths summary
    st.markdown("#### 📊 Resumen de Respiraciones Detectadas")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_metric_card("Respiraciones detectadas", f"{len(analysis.breaths)}", provenance=BADGES.METHOD)

    with col2:
        if analysis.cycle_duration_s is None:
            render_metric_card("Duración del ciclo", None, unavailable_reason=analysis.signal_status_detail or "menos de 3 respiraciones")
        else:
            render_metric_card("Duración del ciclo (media de los intervalos entre inspiraciones)",
                               f"{analysis.cycle_duration_s:.2f} s", provenance=BADGES.METHOD)

    with col3:
        if analysis.rr_variability is None:
            render_metric_card("Variabilidad de los intervalos", None, unavailable_reason="menos de 3 respiraciones")
        else:
            render_metric_card("Variabilidad de los intervalos (desviación estándar, descriptiva)",
                               f"{analysis.rr_variability:.2f} s", provenance=BADGES.METHOD)

    with col4:
        views.render_band_card(analysis)

    st.caption("La relación I:E no se muestra: todavía no tiene golden test ni criterio firmado.")

with tab2:
    st.markdown("### 🫀 Monitoreo de Oximetría (SpO2)")
    st.info(
        f"**{views.SPO2_PROVENANCE}.** Estable sin eventos (basal + ruido); cada apnea anotada desatura el dedo con retardo Tc "
        "(nadir en el FIN del evento + Tc), profundidad r·T con r = 0.30 %/s y recuperación en rampa a 0.70 %/s. La latencia "
        "de las reservas de O₂ no está modelada. Es una simulación, no una medición de un paciente.",
        icon="🫀",
    )

    # Create SpO2 visualization
    fig_spo2 = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=("SpO2 simulada — modelo BIOCORE (Tc valor BIOCORE; r y recuperación, Howarth 2026)", "Flujo de Aire (referencia)"),
        vertical_spacing=0.12,
        row_heights=[0.7, 0.3]
    )
    
    fig_spo2.add_trace(
        go.Scatter(
            x=time_array,
            y=spo2,
            name="SpO2",
            line=dict(color="#8ecae6", width=3),
            fill="tozeroy",
            fillcolor="rgba(142, 202, 230, 0.3)"
        ),
        row=1, col=1
    )
    
    # Airflow reference
    fig_spo2.add_trace(
        go.Scatter(
            x=time_array,
            y=airflow / np.max(np.abs(airflow)) * 20 + 60 if np.max(np.abs(airflow)) > 0 else np.zeros_like(airflow),
            name="Flujo (normalizado)",
            line=dict(color="#666", width=1),
            opacity=0.5
        ),
        row=2, col=1
    )
    
    fig_spo2.update_yaxes(title_text="SpO2 (%)", range=[50, 100], row=1, col=1)
    fig_spo2.update_yaxes(title_text="Flujo", row=2, col=1)
    fig_spo2.update_xaxes(title_text="Tiempo (segundos)", row=2, col=1)
    
    fig_spo2.update_layout(
        height=600,
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#1a2a4a",
        font=dict(color="#e0e7ff"),
        showlegend=True,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_spo2, use_container_width=True)
    
    # SpO2 Statistics
    st.markdown("#### 📊 Estadísticas de Oxigenación")
    
    views.render_spo2_cards(analysis)

with tab3:
    st.markdown("### 📈 Análisis Avanzado")
    st.markdown("#### Apneas (≥ 10 s, caída ≥ 90 % respecto a la línea basal previa)")
    views.render_apnea_cards(analysis)
    views.render_events_table(analysis)
    if analysis.event_period_s is not None:
        st.caption(f"Los eventos se repiten cada ~{analysis.event_period_s:.0f} s (mediana de la separación entre inicios).")
    views.render_pattern_cards(analysis, selected_pattern, respiration_data["ground_truth"])
    views.render_clinical_notes(analysis, circulation_delay)
    views.render_calculator_link("resp_osa_link_clinical")
    views.render_hidden_notice()

with tab4:
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
        - **Mixta:** ⏳ PENDING_VALIDATION (se calcula y se marca; la definición del manual no está verificada)
        - **Obesidad:** Epstein 2009 incluye la obesidad (IMC > 35) entre los pacientes de alto riesgo que deben evaluarse
          para apnea obstructiva del sueño
        - **Obstructiva, mecanismo (Epstein 2009):** los signos, síntomas y consecuencias son resultado directo del colapso
          repetitivo de la vía aérea superior

        #### 📏 Severidad por índice de eventos por hora

        Se calcula con la calculadora de **Calculadoras Clínicas → Escalas** (Epstein 2009): es un índice por hora de
        sueño y este laboratorio solo registra minutos.

        *Fuente: {views.EDUCATION_CITATION}*
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

    *Fuente: {views.EDUCATION_CITATION}*
    """)

with tab5:
    st.markdown("### ❓ Cuestionario Interactivo - Apnea del Sueño")
    
    quiz_type = st.radio(
        "Seleccionar Tipo de Pregunta:",
        [
            "Diferenciación Apnea",
            "Factores de Riesgo",
            "Correlación cardiovascular (guía AASM)",
            "Frecuencia de esta señal",
            "Contar las apneas de esta señal",
        ]
    )
    
    # Fase 3 (2026-11-07): "Identificar Patrón" y la de severidad por índice siguen fuera (patrón oculto; la
    # severidad vive en la calculadora). Se reactivan dos preguntas cuya respuesta SALE de un valor con golden test
    # (FR y conteo de apneas); las otras tres son texto fijo.
    # 2026-11-14 (Art. I): ninguna respuesta viene elegida de inicio (antes la primera opción ya mostraba
    # «Correcto» o «Incorrecto» sin contestar); las de texto perdieron la marca «✓» que delataba la correcta,
    # siempre primera, y salen en el orden de `display_choices()`; en las numéricas el lugar de la correcta ya
    # no es siempre el segundo (`numeric_choices`). El contenido y sus citas no cambian.
    text_questions = balance_positions([
        QuizQuestion("Diferenciación Apnea", [
            "En el esfuerzo respiratorio",
            "En la duración: las centrales duran 10 s o más y las obstructivas menos",
            "En la caída del flujo: las centrales caen ≥ 90 % y las obstructivas ≥ 30 %",
        ], 0),
        QuizQuestion("Factores de Riesgo", [
            "Una persona con obesidad (IMC > 35)",
            "Una persona de 25 años con IMC 22, sin síntomas ni otras condiciones",
            "Una persona sana que viaja como pasajera",
        ], 0),
        QuizQuestion("Correlación cardiovascular (guía AASM)", [
            "Fibrilación auricular y disritmias nocturnas",
            "Ninguna: la guía no menciona alteraciones del ritmo cardíaco",
            "Solo la taquicardia sostenida",
        ], 0),
    ], "respiratory_lab")
    text_question = {q.prompt: q for q in text_questions}
    if quiz_type == "Frecuencia de esta señal":
        st.info("**Pregunta:** ¿Cuál es la frecuencia respiratoria de la señal actual (redondeada al entero)?")
        correct = analysis.respiratory_rate_rounded
        if correct is None:
            st.warning("La frecuencia no está disponible en este registro: no hay pregunta que responder.")
        else:
            options = numeric_choices(correct, 4, f"fr:{correct}", minimum=1)
            picked = st.radio("Tu respuesta (resp/min):", options, index=None, key="resp_quiz_fr")
            if picked is None:
                pass
            elif picked == correct:
                st.success(f"✅ Correcto: {analysis.respiratory_rate:.1f}/min medida entre inspiraciones; {views.fr_band_text(analysis)}.")
            else:
                st.error("❌ Mide el tiempo entre dos inspiraciones consecutivas: FR = 60 / ese intervalo (s).")

    elif quiz_type == "Contar las apneas de esta señal":
        st.info("**Pregunta:** ¿Cuántas apneas (caída ≥ 90 % durante ≥ 10 s) hay en la señal actual?")
        correct = analysis.apnea_count
        if correct is None:
            st.warning("Este registro no tiene señal respiratoria evaluable: no hay pregunta que responder.")
        else:
            options = numeric_choices(correct, 1, f"apneas:{correct}", minimum=0)
            picked = st.radio("Tu respuesta:", options, index=None, key="resp_quiz_apneas")
            if picked is None:
                pass
            elif picked == correct:
                st.success(f"✅ Correcto: {correct} apnea(s) de ≥ 10 s en {analysis.record_duration_s:.0f} s de registro.")
            else:
                st.error("❌ Busca los tramos con flujo casi ausente (≥ 90 % de caída) y mídelos: solo cuentan los de ≥ 10 s.")

    elif quiz_type == "Diferenciación Apnea":
        st.info("""
        **Pregunta:** Según Berry 2012 (AASM), ¿en qué se basa la clasificación de una apnea como obstructiva, mixta o central?

        Pista: mira la pared torácica y el movimiento abdominal durante las apneas.
        """)

        question = text_question["Diferenciación Apnea"]
        answer = st.radio("Tu respuesta:", question.display_choices(), index=None)

        if answer is None:
            pass
        elif question.is_correct(answer):
            st.success("✅ Correcto: Berry 2012 (§4.1.1) clasifica la apnea según el esfuerzo respiratorio. En este laboratorio, "
                       "central = esfuerzo ausente y obstructiva = esfuerzo presente (Criterio BIOCORE); la mixta queda "
                       "⏳ PENDING_VALIDATION.")
        else:
            st.error("❌ Todas las apneas cumplen la misma regla: caída ≥ 90 % de la excursión del flujo durante ≥ 10 s (Berry 2012); "
                     "una caída de ≥ 30 % es el criterio de hipopnea, no de apnea. Lo que las separa es el esfuerzo respiratorio.")

    elif quiz_type == "Factores de Riesgo":
        st.info("""
        **Pregunta:** Según la guía de la AASM (Epstein 2009), ¿cuál de estos pacientes pertenece a un grupo de ALTO RIESGO
        que debe evaluarse para apnea obstructiva del sueño?
        """)

        question = text_question["Factores de Riesgo"]
        answer = st.radio("Tu respuesta:", question.display_choices(), index=None)

        if answer is None:
            pass
        elif question.is_correct(answer):
            st.success("✅ Correcto: la guía de la AASM (Epstein 2009) lista como alto riesgo la obesidad (IMC > 35), la insuficiencia cardíaca congestiva, la "
                       "fibrilación auricular, la hipertensión refractaria al tratamiento, la diabetes tipo 2, el ACV, las "
                       "disritmias nocturnas, la hipertensión pulmonar, las poblaciones de conducción de alto riesgo y la "
                       "evaluación previa a cirugía bariátrica.")
        else:
            st.error("❌ Esa persona no figura en la lista de alto riesgo de la guía de la AASM (Epstein 2009: obesidad con IMC > 35, insuficiencia "
                     "cardíaca congestiva, fibrilación auricular, hipertensión refractaria, diabetes tipo 2, ACV, disritmias "
                     "nocturnas, hipertensión pulmonar, conducción de alto riesgo, cirugía bariátrica).")

    else:  # Correlación cardiovascular (antes «ECG-Respiratoria»: sus afirmaciones no tenían fuente)
        st.info("""
        **Pregunta:** ¿Qué condiciones del ritmo cardíaco figuran entre los pacientes de alto riesgo que la guía de la AASM
        (Epstein 2009) pide evaluar para apnea obstructiva del sueño?
        """)

        question = text_question["Correlación cardiovascular (guía AASM)"]
        answer = st.radio("Tu respuesta:", question.display_choices(), index=None)

        if answer is None:
            pass
        elif question.is_correct(answer):
            st.success("✅ Correcto: la fibrilación auricular y las disritmias nocturnas figuran en la lista de alto riesgo de la guía. "
                       "Berry 2012 añade que un estudio con la definición de hipopnea de ≥ 3 % de desaturación encontró asociación "
                       "entre el índice de eventos y la fibrilación auricular o la ectopia ventricular compleja en hombres mayores "
                       "sin insuficiencia cardíaca declarada.")
        else:
            st.error("❌ La guía de la AASM (Epstein 2009) sí las menciona: la fibrilación auricular y las disritmias nocturnas están en su lista de pacientes "
                     "de alto riesgo.")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# CLINICAL SUMMARY
# ═══════════════════════════════════════════════════════════════

st.markdown("### 📋 Resumen Clínico")

# Fase 3-4 (Art. I): el resumen muestra solo valores con golden test, cada uno con su insignia. Hipopneas, I:E y ODI
# siguen fuera (ver el aviso de la pestaña Análisis Avanzado); el patrón y las notas son HEURISTIC y no diagnostican.
col1, col2, col3 = st.columns(3)
with col1:
    views.render_rate_cards(analysis)
    if analysis.cycle_duration_s is not None:
        render_metric_card("Duración del ciclo", f"{analysis.cycle_duration_s:.2f} s", provenance=BADGES.METHOD)

with col2:
    if analysis.apnea_count is None:
        render_metric_card("Apneas (≥ 10 s)", None, unavailable_reason="no evaluable: sin señal respiratoria")
    else:
        render_metric_card("Apneas (≥ 10 s)", f"{analysis.apnea_count}  ·  tiempo total {analysis.apnea_total_time_s:.1f} s",
                           provenance=BADGES.METHOD)
        render_metric_card("Tasa equivalente por hora de registro (extrapolada, sin valor diagnóstico)",
                           f"{analysis.equivalent_rate_per_hour:.0f} /h", provenance=BADGES.METHOD)

with col3:
    render_metric_card("SpO2 basal", f"{analysis.baseline_spo2:.1f}%", provenance=BADGES.METHOD, citation=views.SPO2_PROVENANCE)
    render_metric_card("SpO2 mínima", f"{analysis.minimum_spo2:.1f}%", provenance=BADGES.METHOD, citation=views.SPO2_PROVENANCE)

st.markdown(f"**Patrón** ({BADGES.HEURISTIC} heurística): {views.pattern_description(analysis)}")
views.render_clinical_notes(analysis, circulation_delay)
st.caption("Hipopneas, relación I:E y ODI no se muestran (sin criterio firmado o sin golden test).")

# ═══════════════════════════════════════════════════════════════
# EDUCATIONAL SIDEBAR
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("---")
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
