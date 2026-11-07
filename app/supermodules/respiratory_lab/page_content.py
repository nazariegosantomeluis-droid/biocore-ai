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
    create_respiratory_summary
)

# Consolidación Visual Tanda 3 (2026-09-21): `PALETTE`/`BADGES`/
# `render_metric_card`/`render_section_header` -- fuente única de color y
# de tarjeta de métrica (`app/utils/design_system.py`), reemplaza el
# `<style>` propio de este archivo (retirado más abajo) y los ~24
# `st.metric()` a mano repartidos por las pestañas.
from app.utils.design_system import BADGES, PALETTE, render_metric_card, render_section_header

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

# SpO2 parameters
st.sidebar.markdown("### 🫀 Parámetros de Oxigenación")
st.sidebar.caption(
    "⛔ La SpO₂ simulada hoy es un artefacto del generador (cae en cada cruce por cero del flujo, "
    "incluso con respiración normal): estos dos parámetros solo mueven ese artefacto."
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
        help="Desaturación durante apnea"
    )

duration = st.sidebar.slider(
    "⏱️ Duración Grabación (s)",
    min_value=30,
    max_value=300,
    value=120,
    step=10
)

st.sidebar.markdown("---")

# ═══════════════════════════════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════════════════════════════

# Generate respiratory signal
@st.cache_data
def generate_respiration_data(pattern, rr, tv, insp, exp, baseline, desaturated, duration):
    generator = RespiratorySignalGenerator(sampling_rate=100)
    
    params = RespiratoryPattern(
        respiratory_rate=rr,
        tidal_volume=tv,
        inspiration_time=insp,
        expiration_time=(exp if exp > 0 else None),
        pattern_type=pattern,
        baseline_spo2=baseline,
        desaturation_level=desaturated,
        cheyne_stokes_cycle=60.0
    )
    
    respiration = generator.generate_respiration(duration=duration, params=params)
    return respiration


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


# Generate data
# Parámetros imposibles (p. ej. inspiración >= ciclo): el generador lanza ValueError y aquí se muestra
# explícito, en vez de la señal sin espiración que se dibujaba en silencio.
try:
    respiration_data = generate_respiration_data(
        selected_pattern, rr, tv, insp_time, exp_time, baseline_spo2, min_spo2, duration
    )
except ValueError as _err:
    st.error(f"⛔ Parámetros respiratorios imposibles: {_err}")
    st.stop()

airflow = respiration_data['airflow']
time_array = respiration_data['time']
spo2 = respiration_data['spo2']
chest = respiration_data['chest_wall']
abdomen = respiration_data['abdomen']

# Perform analysis
analysis = analyze_respiration_data(airflow, time_array, spo2, chest)

# Puente de sesión (2026-08-21, Capa 2 Fase 2.2, Ejecución 2): expone el AHI/
# eventos de apnea ya calculados aquí a la pestaña "Investigación" de
# respiratory_lab/pages.py -- sin recalcular nada. `with tabs[0]:` (Clínica)
# siempre corre en cada rerun de Streamlit, sea cual sea la pestaña activa, así
# que este bloque ya se ejecutó antes de que se renderice "Investigación" en
# el mismo run -- el dato existe garantizado cuando la otra pestaña lo lee.
st.session_state['_respiratory_lab_analysis'] = {
    'analysis': analysis,
    'pattern_display': selected_pattern_display,
    'duration': duration,
}

# Consolidación Visual Tanda 3 (2026-09-21): el `# 💨 Laboratorio
# Respiratorio` (h1) se retira -- duplicaba el `<h1>` que
# `respiratory_lab/pages.py::render_views()` ya dibuja vía
# `render_module_header("Respiratory Lab", icon="💨")` antes de invocar
# este archivo por `runpy` (mismo bug que ya se corrigió en ECG-12/EEG
# Neuro Lab, Tandas 1-2). "Patrón: X" sí es información genuina de
# sub-sección (cambia con la selección del sidebar) -- se conserva como
# `render_section_header()`, no un segundo título de módulo.
render_section_header(f"Patrón: {selected_pattern_display}")

# ═══════════════════════════════════════════════════════════════
# METRICS ROW
# ═══════════════════════════════════════════════════════════════

col1, col2, col3, col4, col5 = st.columns(5)

# Consolidación Visual Tanda 3 (2026-09-21): los 5 `st.metric()` de esta
# fila -> `render_metric_card`. Todos son cálculo real de
# `RespiratoryAnalyzer` sin un `classify_*()`/`*_CITATION` en
# `src/signals/respiration` que los respalde -- `BADGES.HEURISTIC`,
# criterio conservador por default. Sin `classification=`: no se fabrica
# un semáforo de 3 niveles que nadie validó; el emoji de severidad
# (`severity_colors`, cálculo ya existente, sin cambios) se conserva
# dentro del texto del valor, igual que antes.
# Tanda 1 de contención (2026-11-05, Art. I): FR y AHI se muestran marcados
# "no fiable" (el analizador devuelve FR = 60.0 constante y AHI = 0 con cualquier
# señal; ver RESPIRATORY_UNRELIABLE_NOTICE en pages.py) y se SUPRIMEN el patrón
# y la severidad, que son clasificaciones derivadas de esos números. Sin badge
# de procedencia en los valores no fiables: ni CLINICAL ni HEURISTIC les aplica.
with col1:
    render_metric_card(
        "Frecuencia Respiratoria — ⛔ no fiable", f"{analysis.respiratory_rate:.1f} r/min (no usar)",
    )

with col2:
    render_metric_card(
        "SpO2 Mínimo — ⛔ artefacto del generador", f"{analysis.minimum_spo2:.1f}% (no usar)",
    )

with col3:
    render_metric_card(
        "Índice AHI — ⛔ no fiable", f"{analysis.apnea_hypopnea_index:.1f} (no usar)",
    )

with col4:
    render_metric_card(
        "Patrón", None,
        unavailable_reason="clasificación suprimida: depende de la detección de respiraciones, en corrección",
    )

with col5:
    render_metric_card(
        "Severidad", None,
        unavailable_reason="suprimida: se deriva del AHI, que no es fiable todavía",
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
        subplot_titles=("Flujo de Aire (L/min)", "Pared Torácica", "Movimiento Abdominal"),
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
    fig.update_yaxes(title_text="L/min", row=1, col=1)
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
    
    # Consolidación Visual Tanda 3 (2026-09-21): `st.metric` crudo ->
    # `render_metric_card`, `BADGES.HEURISTIC` (cálculo real, sin cita
    # clínica). "N/A" (sin respiraciones detectadas) -> `value=None` +
    # `unavailable_reason` real, en vez de un string "N/A" opaco.
    # Tanda 1.5 (2026-11-05, Art. I): TODO valor que sale del detector de
    # respiraciones (conteo, duración, I:E) comparte el defecto de la FR: el
    # detector no es fiable. Se muestran marcados, sin badge de procedencia.
    with col1:
        render_metric_card(
            "Total Respiraciones — ⛔ no fiable", f"{len(analysis.breaths)} (no usar)",
        )

    with col2:
        if len(analysis.breaths) > 0:
            mean_duration = np.mean([b.duration_seconds for b in analysis.breaths])
            render_metric_card("Duración Promedio — ⛔ no fiable", f"{mean_duration:.2f}s (no usar)")
        else:
            render_metric_card(
                "Duración Promedio — ⛔ no fiable", None,
                unavailable_reason="sin respiraciones detectadas; el detector está en corrección",
            )

    with col3:
        if len(analysis.breaths) > 0:
            mean_ie = np.mean([b.i_e_ratio for b in analysis.breaths])
            render_metric_card("Ratio I:E Promedio — ⛔ no fiable", f"{mean_ie:.2f} (no usar)")
        else:
            render_metric_card(
                "Ratio I:E Promedio — ⛔ no fiable", None,
                unavailable_reason="sin respiraciones detectadas; el detector está en corrección",
            )

    with col4:
        # Misma línea defectuosa que la FR (diferencias de índices de respiración,
        # no de tiempos): siempre 0.00. Tanda 1 de contención, 2026-11-05.
        render_metric_card("Variabilidad RR — ⛔ no fiable", f"{analysis.rr_variability:.2f} (no usar)")

with tab2:
    st.markdown("### 🫀 Monitoreo de Oximetría (SpO2)")
    st.warning(
        "⛔ **Artefacto del generador, no fiable (no usar).** La SpO₂ de esta pestaña no es una medición ni "
        "un modelo fisiológico: el generador la deriva de |flujo| y por eso cae en cada cruce por cero de cada "
        "respiración, incluso en respiración normal (con los valores por defecto, 'Tiempo <90 %' marca más de "
        "50 s de 120). Se corrige en la fase 2b del arco respiratorio.",
        icon="⛔",
    )
    
    # Create SpO2 visualization
    fig_spo2 = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=("SpO2 simulada — ⛔ artefacto del generador, no fiable (no usar)", "Flujo de Aire (referencia)"),
        vertical_spacing=0.12,
        row_heights=[0.7, 0.3]
    )
    
    # SpO2 trace
    spo2_color = np.where(spo2 < 90, "#ff6b6b", "#51cf66")
    
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
    
    # Reference lines
    fig_spo2.add_hline(y=95, line_dash="dash", line_color="#51cf66", row=1, col=1, 
                       annotation_text="Normal")
    fig_spo2.add_hline(y=90, line_dash="dash", line_color="#ffa500", row=1, col=1,
                       annotation_text="Hipoxemia leve")
    fig_spo2.add_hline(y=85, line_dash="dash", line_color="#ff6b6b", row=1, col=1,
                       annotation_text="Hipoxemia grave")
    
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
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Consolidación Visual Tanda 3 (2026-09-21): `st.metric` crudo ->
    # `render_metric_card`, `BADGES.HEURISTIC` (cálculo real sobre la señal
    # de SpO2, sin cita clínica de umbral en este módulo).
    # Contención 2 (2026-11-07, Art. I): las cuatro tarjetas leen la SpO2 del generador,
    # que cae en cada cruce por cero del flujo (respiración normal, FR 15: media 90.2 %,
    # 54 s de 120 bajo 90 %). Son un artefacto, no una medición.
    with col1:
        render_metric_card("SpO2 Basal — ⛔ artefacto del generador", f"{analysis.baseline_spo2:.1f}% (no usar)")

    with col2:
        render_metric_card("SpO2 Mínimo — ⛔ artefacto del generador", f"{analysis.minimum_spo2:.1f}% (no usar)")

    with col3:
        render_metric_card("Tiempo <90% — ⛔ artefacto del generador", f"{analysis.time_below_90:.1f}s (no usar)")

    with col4:
        render_metric_card("Tiempo <85% — ⛔ artefacto del generador", f"{analysis.time_below_85:.1f}s (no usar)")

with tab3:
    st.markdown("### 📈 Análisis Avanzado")
    # Tanda 1 de contención (2026-11-05, Art. I): se suprimen la tabla de eventos
    # de apnea, la clasificación por AHI, el "✅ No se detectaron apneas" y la
    # descripción del patrón respiratorio. El detector no cuenta apneas aunque la
    # señal tenga pausas de ~20 s (mide 0 eventos en los patrones de apnea del
    # propio generador), así que tanto "hay apnea" como "no hay apnea" serían (1.5: igual el conteo de respiraciones)
    # afirmaciones sin respaldo. El cálculo no se tocó (arco propio).
    st.info(
        "Análisis avanzado **suprimido mientras el detector de apneas y de respiraciones está en "
        "corrección**: no se muestran eventos de apnea, clasificación por AHI ni descripción del "
        "patrón respiratorio. La señal (flujo, pared torácica, abdomen) se conserva; la oximetría es un "
        "artefacto del generador y figura marcada como tal."
    )

with tab4:
    st.markdown("### 📚 Referencias Clínicas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        #### 🫁 Parámetros Respiratorios Normales
        
        - **Frecuencia Respiratoria:** 12-20 respiraciones/minuto
        - **Volumen Corriente:** 400-600 mL (0.4-0.6 L)
        - **Ratio I:E Normal:** 1:2 a 1:3
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
        
        #### 📏 Índice AHI
        
        - **Normal:** AHI <5 eventos/hora
        - **Leve:** AHI 5-14 eventos/hora
        - **Moderada:** AHI 15-29 eventos/hora
        - **Severa:** AHI ≥30 eventos/hora
        """)
    
    st.markdown("---")
    
    st.markdown("""
    #### 💡 Implicaciones Clínicas
    
    La apnea del sueño es factor de riesgo independiente para:
    - Hipertensión arterial
    - Cardiopatía isquémica
    - Arritmias (especialmente fibrilación auricular)
    - Enfermedad cerebrovascular
    - Accidentes (somnolencia diurna)
    
    **Tratamiento:**
    - CPAP (Presión Positiva Continua en Vía Aérea)
    - Cambios de estilo de vida (peso, posición, alcohol)
    - Dispositivos orales
    - Cirugía en casos seleccionados
    """)

with tab5:
    st.markdown("### ❓ Cuestionario Interactivo - Apnea del Sueño")
    
    quiz_type = st.radio(
        "Seleccionar Tipo de Pregunta:",
        [
            "Diferenciación Apnea",
            "Factores de Riesgo",
            "Correlación ECG-Respiratoria"
        ]
    )
    
    # Tanda 1 de contención (2026-11-05): se quitaron "Identificar Patrón" y
    # "AHI y Severidad": su respuesta "correcta" salía de `analysis.breathing_pattern`
    # y `analysis.apnea_hypopnea_index`, es decir del analizador en corrección
    # (daba "✓ Periodic" para respiración normal). Las otras tres preguntas son
    # texto fijo, sin dependencia del analizador.
    if quiz_type == "Diferenciación Apnea":
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

# Tanda 1 de contención (2026-11-05, Art. I): el resumen conserva solo lo que no
# depende del detector de respiraciones/apneas (oximetría y conteo bruto de
# respiraciones detectadas, marcado "no fiable" en la Tanda 1.5). FR y AHI figuran como "no fiable"; patrón, eventos
# de apnea y severidad se suprimen; las "notas clínicas" automáticas del
# analizador ("Taquipnea…", "apnea del sueño…", "No apneas detected") no se
# renderizan porque se generan a partir de esos mismos valores.
col1, col2, col3 = st.columns(3)
with col1:
    render_metric_card("Frecuencia respiratoria — ⛔ no fiable", f"{analysis.respiratory_rate:.1f} breaths/min (no usar)")
    render_metric_card("Patrón respiratorio", None, unavailable_reason="suprimido: en corrección")
    render_metric_card("Eventos de apnea", None, unavailable_reason="suprimido: el detector no es fiable todavía")

with col2:
    render_metric_card("AHI estimado — ⛔ no fiable", f"{analysis.apnea_hypopnea_index:.1f} eventos/h (no usar)")
    render_metric_card("Severidad", None, unavailable_reason="suprimida: se deriva del AHI")
    render_metric_card("Respiraciones detectadas — ⛔ no fiable", f"{len(analysis.breaths)} (no usar)")

with col3:
    render_metric_card("SpO2 basal — ⛔ artefacto del generador", f"{analysis.baseline_spo2:.1f}% (no usar)")
    render_metric_card("SpO2 mínima — ⛔ artefacto del generador", f"{analysis.minimum_spo2:.1f}% (no usar)")
    render_metric_card("Tiempo <90% — ⛔ artefacto del generador", f"{analysis.time_below_90:.1f} s (no usar)")

st.markdown("**Notas clínicas automáticas:** suprimidas mientras el analizador respiratorio está en corrección.")

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
