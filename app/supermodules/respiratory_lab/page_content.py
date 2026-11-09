"""
Respiratory Lab - Phase 2 of Biomedical Signal Visualizer
Comprehensive respiratory monitoring and sleep apnea education

Features:
- Multiple breathing patterns (normal, apnea, irregular, etc.)
- Real-time respiratory analysis
- SpO2 integration and monitoring
- Sleep apnea severity assessment
- Interactive educational content
- ECG-Respiratory correlation
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
        <p>Experimenta con patrones de respiración, monitorea SpO2 y aprende a reconocer señales de apnea y respiración irregular.</p>
        <ul>
            <li><strong>Normal:</strong> respiración estable y oxigenación saludable.</li>
            <li><strong>Apnea:</strong> pausas en el flujo de aire y desaturaciones.</li>
            <li><strong>Taquipnea:</strong> ritmo respiratorio acelerado.</li>
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
        help="Rango normal: 12-20 resp/min"
    )

with col2:
    tv = st.number_input(
        "Volumen Corriente (L)",
        min_value=0.1,
        max_value=1.5,
        value=0.5,
        step=0.1,
        help="Volumen de aire por respiración"
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
        help="Saturación de oxígeno en reposo"
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
        st.markdown("""
        #### 🫁 Parámetros Respiratorios Normales
        
        - **Frecuencia Respiratoria:** 12-20 respiraciones/minuto
        - **Volumen Corriente:** 400-600 mL (0.4-0.6 L)
        - **SpO2 Normal:** >95% en reposo
        - **Patrón:** Regular, rítmico
        
        #### 📊 Patrones Anormales
        
        - **Taquipnea:** >20 resp/min (fiebre, ansiedad, dolor)
        - **Bradipnea:** <12 resp/min (depresión SNC, fármacos)
        - **Apnea:** >10 segundos sin flujo de aire
        - **Cheyne-Stokes:** Ciclos periódicos de creciente-decreciente
        - **Atáxica:** Completamente irregular (lesión tronco cerebral)
        """)
    
    with col2:
        st.markdown("""
        #### 😴 Apnea del Sueño - Clasificación AASM
        
        **Central Sleep Apnea:**
        - SIN flujo de aire
        - SIN esfuerzo respiratorio
        - Asociada a: insuficiencia cardíaca, Parkinson
        
        **Obstructive Sleep Apnea:**
        - SIN flujo de aire pero CON esfuerzo
        - Oclusión de vía aérea superior
        - Movimiento paradójico pared-abdomen
        - Factor de riesgo: obesidad, edad, sexo masculino
        
        #### 📏 Severidad por índice de eventos por hora

        Se calcula con la calculadora de **Calculadoras Clínicas → Escalas** (Epstein 2009): es un índice por hora de
        sueño y este laboratorio solo registra minutos.
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
            "Correlación ECG-Respiratoria",
            "Frecuencia de esta señal",
            "Contar las apneas de esta señal",
        ]
    )
    
    # Fase 3 (2026-11-07): "Identificar Patrón" y la de severidad por índice siguen fuera (patrón oculto; la
    # severidad vive en la calculadora). Se reactivan dos preguntas cuya respuesta SALE de un valor con golden test
    # (FR y conteo de apneas); las otras tres son texto fijo.
    if quiz_type == "Frecuencia de esta señal":
        st.info("**Pregunta:** ¿Cuál es la frecuencia respiratoria de la señal actual (redondeada al entero)?")
        correct = analysis.respiratory_rate_rounded
        if correct is None:
            st.warning("La frecuencia no está disponible en este registro: no hay pregunta que responder.")
        else:
            options = sorted({correct, correct + 4, max(1, correct - 4), correct + 9})
            picked = st.radio("Tu respuesta (resp/min):", options, key="resp_quiz_fr")
            if picked == correct:
                st.success(f"✅ Correcto: {analysis.respiratory_rate:.1f}/min medida entre inspiraciones; {views.fr_band_text(analysis)}.")
            else:
                st.error("❌ Mide el tiempo entre dos inspiraciones consecutivas: FR = 60 / ese intervalo (s).")

    elif quiz_type == "Contar las apneas de esta señal":
        st.info("**Pregunta:** ¿Cuántas apneas (caída ≥ 90 % durante ≥ 10 s) hay en la señal actual?")
        correct = analysis.apnea_count
        if correct is None:
            st.warning("Este registro no tiene señal respiratoria evaluable: no hay pregunta que responder.")
        else:
            options = sorted({correct, correct + 1, correct + 2, max(0, correct - 1)})
            picked = st.radio("Tu respuesta:", options, key="resp_quiz_apneas")
            if picked == correct:
                st.success(f"✅ Correcto: {correct} apnea(s) de ≥ 10 s en {analysis.record_duration_s:.0f} s de registro.")
            else:
                st.error("❌ Busca los tramos con flujo casi ausente (≥ 90 % de caída) y mídelos: solo cuentan los de ≥ 10 s.")

    elif quiz_type == "Diferenciación Apnea":
        st.info("""
        **Pregunta:** ¿Cuál es la diferencia CLAVE entre apnea central y obstructiva?
        
        Pista: Mira la pared torácica y el movimiento abdominal durante las apneas.
        """)
        
        answer = st.radio("Tu respuesta:", [
            "✓ Central: SIN flujo + SIN esfuerzo | Obstructiva: SIN flujo + CON esfuerzo",
            "Central tiene apneas más largas",
            "Obstructiva es más común en niños"
        ])
        
        if answer.startswith("✓"):
            st.success("✅ ¡Correcto! Este es el hallazgo diagnóstico clave.")
        else:
            st.error("❌ La respuesta correcta es: Central tiene ausencia de esfuerzo respiratorio, Obstructiva tiene esfuerzo persistente")
    
    elif quiz_type == "Factores de Riesgo":
        st.info("""
        **Pregunta:** ¿Cuál es el factor de riesgo MODIFICABLE más importante para AOS?
        """)
        
        answer = st.radio("Tu respuesta:", [
            "✓ Obesidad (IMC >30)",
            "Edad avanzada",
            "Sexo masculino",
            "Genética familiar"
        ])
        
        if answer.startswith("✓"):
            st.success("✅ ¡Correcto! La pérdida de peso es el tratamiento más efectivo en la mayoría de casos.")
        else:
            st.error("❌ Aunque otros son factores de riesgo, la OBESIDAD es el modificable más importante")
    
    else:  # Correlación ECG-Respiratoria
        st.info("""
        **Pregunta:** Durante una apnea prolongada con desaturación importante, ¿qué cambios esperas en el ECG?
        """)
        
        answer = st.radio("Tu respuesta:", [
            "✓ Bradicardia, potencial aumento de arritmias, cambios ST",
            "Taquicardia sostenida",
            "Cambios isoelétricos sin importancia",
            "Alteraciones de onda P únicamente"
        ])
        
        if answer.startswith("✓"):
            st.success("✅ ¡Correcto! La hipoxia crónica causa bradicardia vagal e incrementa arritmias (incluyendo FA).")
        else:
            st.error("❌ La respuesta correcta incluye bradicardia y potencial para arritmias por hipoxia")

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
        "Correlación Cardio-Respiratoria"
    ], key="edu_sidebar")
    
    if edu_section == "Introducción":
        st.markdown("""
        #### ¿Qué es la Respiración?
        
        Es el proceso de intercambio gaseoso:
        - **Inspiración:** Entrada de O₂
        - **Espiración:** Salida de CO₂
        
        El flujo de aire se detecta con:
        - Sensor de flujo (termistor)
        - Correas de esfuerzo respiratorio
        - Pulsioximetría (SpO2)
        """)
    
    elif edu_section == "Patrones Clínicos":
        st.markdown("""
        #### 🫁 Patrones Respiratorios
        
        **Normal:**
        - 12-20 resp/min
        - Regular, rítmico
        
        **Taquipnea:**
        - >20 resp/min
        - Estrés, fiebre, dolor
        
        **Bradipnea:**
        - <12 resp/min
        - Depresión SNC
        
        **Cheyne-Stokes:**
        - Creciente-decreciente
        - Insuficiencia cardíaca
        """)
    
    elif edu_section == "Apnea del Sueño":
        st.markdown("""
        #### 😴 Datos Importantes
        
        - **Prevalencia:** 10-30% adultos
        - **No diagnosticada:** 80% casos
        - **Complicaciones:** ↑ CV 3-4x
        
        **Síntomas:**
        - Ronquido
        - Somnolencia
        - Pausas respiratorias
        - Despertar abrupto
        - Sudoración nocturna
        
        **Gold Standard:** Polisomnografía
        """)
    
    else:  # Correlación
        st.markdown("""
        #### 💓 ECG-Respiration
        
        **Arritmias por Apnea:**
        - Hipoxia → ↑ Simpático
        - Apnea → Bradicardia vagal
        - Reoxigenación → Taquicardia
        
        **Resultado:**
        - ↑ Variabilidad FC
        - ↑ Fibrilación Auricular
        - ↑ Muerte Súbita Nocturna
        
        **Conclusión:**
        Integrar análisis ECG y
        respiratorio es ESENCIAL
        """)
