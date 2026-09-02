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

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# `st.set_page_config()` y `render_sidebar_navigation()` retirados
# (2026-08-20, Capa 2 Fase 2.1, cierre): vestigios de la arquitectura
# Streamlit multipágina anterior. Este archivo solo corre anidado bajo
# `app/main.py` (vía `runpy.run_path()` desde `respiratory_lab/pages.py`),
# que ya configuró la página una sola vez al inicio. Ver CHANGELOG.md.

st.markdown("""
    <div style='padding: 16px; border-radius: 16px; background: #0f172a; border: 1px solid #1f2937; margin-bottom: 24px;'>
        <h2 id="panel-respiratorio" style='color: #8ecae6;'>💨 Laboratorio Respiratorio</h2>
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

# Theme configuration
st.markdown("""
    <style>
        :root {
            --primary-color: #8ecae6;
            --background-color: #0f172a;
            --text-color: #e0e7ff;
        }
        
        body {
            background-color: #0f172a;
            color: #e0e7ff;
        }
        
        .main {
            background-color: #0f172a;
        }
        
        .stTabs [data-baseweb="tab-list"] button {
            color: #8ecae6;
            border-bottom: 2px solid transparent;
        }
        
        .stTabs [aria-selected="true"] {
            border-bottom: 2px solid #8ecae6;
        }
        
        h1, h2, h3 {
            color: #8ecae6;
        }
        
        .metric-card {
            background-color: #1a2a4a;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #8ecae6;
        }
        
        .clinical-note {
            background-color: #1a2a4a;
            border-left: 4px solid #ff6b6b;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        
        .normal-note {
            border-left: 4px solid #51cf66;
        }
    </style>
""", unsafe_allow_html=True)

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
    exp_time = st.number_input(
        "Tiempo Espiración (s)",
        min_value=0.3,
        max_value=3.0,
        value=1.5,
        step=0.1
    )

# SpO2 parameters
st.sidebar.markdown("### 🫀 Parámetros de Oxigenación")

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
        expiration_time=exp,
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
respiration_data = generate_respiration_data(
    selected_pattern, rr, tv, insp_time, exp_time, baseline_spo2, min_spo2, duration
)

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

# Main title
st.markdown(f"""
    # 💨 Laboratorio Respiratorio
    ## Patrón: {selected_pattern_display}
""")

# ═══════════════════════════════════════════════════════════════
# METRICS ROW
# ═══════════════════════════════════════════════════════════════

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Frecuencia Respiratoria",
        f"{analysis.respiratory_rate:.1f} r/min",
        delta=None,
        delta_color="off"
    )

with col2:
    st.metric(
        "SpO2 Mínimo",
        f"{analysis.minimum_spo2:.1f}%",
        delta=None,
        delta_color="off"
    )

with col3:
    st.metric(
        "Índice AHI",
        f"{analysis.apnea_hypopnea_index:.1f}",
        delta=None,
        delta_color="off"
    )

with col4:
    st.metric(
        "Patrón",
        analysis.breathing_pattern.capitalize(),
        delta=None,
        delta_color="off"
    )

with col5:
    severity_colors = {
        "normal": "🟢",
        "mild": "🟡",
        "moderate": "🟠",
        "severe": "🔴"
    }
    severity_emoji = severity_colors.get(analysis.severity, "⚪")
    st.metric(
        "Severidad",
        f"{severity_emoji} {analysis.severity.upper()}",
        delta=None,
        delta_color="off"
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
    
    with col1:
        st.metric(
            "Total Respiraciones",
            len(analysis.breaths),
            help="Número de ciclos respiratorios completos detectados"
        )
    
    with col2:
        if len(analysis.breaths) > 0:
            mean_duration = np.mean([b.duration_seconds for b in analysis.breaths])
            st.metric("Duración Promedio", f"{mean_duration:.2f}s")
        else:
            st.metric("Duración Promedio", "N/A")
    
    with col3:
        if len(analysis.breaths) > 0:
            mean_ie = np.mean([b.i_e_ratio for b in analysis.breaths])
            st.metric("Ratio I:E Promedio", f"{mean_ie:.2f}")
        else:
            st.metric("Ratio I:E Promedio", "N/A")
    
    with col4:
        st.metric(
            "Variabilidad RR",
            f"{analysis.rr_variability:.2f}",
            help="Desviación estándar (menor = más regular)"
        )

with tab2:
    st.markdown("### 🫀 Monitoreo de Oximetría (SpO2)")
    
    # Create SpO2 visualization
    fig_spo2 = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=("Saturación de Oxígeno (SpO2)", "Flujo de Aire (referencia)"),
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
    
    with col1:
        st.metric("SpO2 Basal", f"{analysis.baseline_spo2:.1f}%")
    
    with col2:
        st.metric("SpO2 Mínimo", f"{analysis.minimum_spo2:.1f}%")
    
    with col3:
        st.metric("Tiempo <90%", f"{analysis.time_below_90:.1f}s")
    
    with col4:
        st.metric("Tiempo <85%", f"{analysis.time_below_85:.1f}s")

with tab3:
    st.markdown("### 📈 Análisis Avanzado")
    
    # Apnea events
    if analysis.apnea_detected:
        st.markdown(f"#### 🔴 Eventos de Apnea Detectados ({len(analysis.apnea_events)})")
        
        apnea_df_data = []
        for i, event in enumerate(analysis.apnea_events[:10], 1):  # Show first 10
            apnea_df_data.append({
                "Evento": i,
                "Inicio (s)": f"{event['start_time']:.1f}",
                "Fin (s)": f"{event['end_time']:.1f}",
                "Duración (s)": f"{event['duration']:.1f}",
                "Tipo": event['type'].capitalize()
            })
        
        if apnea_df_data:
            import pandas as pd
            apnea_df = pd.DataFrame(apnea_df_data)
            st.dataframe(apnea_df, use_container_width=True, hide_index=True)
        
        # Severity classification
        ahi = analysis.apnea_hypopnea_index
        if ahi < 5:
            ahi_severity = "✅ Normal"
        elif ahi < 15:
            ahi_severity = "🟡 Leve (AOS leve)"
        elif ahi < 30:
            ahi_severity = "🟠 Moderada (AOS moderada)"
        else:
            ahi_severity = "🔴 Severa (AOS severa)"
        
        st.markdown(f"""
        **Índice AHI (Apnea-Hypopnea Index):** {ahi:.1f} eventos/hora
        
        **Clasificación:** {ahi_severity}
        """)
    else:
        st.success("✅ No se detectaron apneas")
    
    # Breathing pattern analysis
    st.markdown("#### 🫁 Análisis de Patrón Respiratorio")
    
    pattern_descriptions = {
        "regular": "Respiración regular y ordenada - Buen control respiratorio",
        "irregular": "Respiración irregular - Puede indicar inestabilidad del sueño",
        "periodic": "Respiración periódica - Característica de apnea del sueño",
        "insufficient_data": "Datos insuficientes para análisis"
    }
    
    pattern_desc = pattern_descriptions.get(analysis.breathing_pattern, "Patrón desconocido")
    st.info(f"**Patrón detectado:** {analysis.breathing_pattern.capitalize()}\n\n{pattern_desc}")

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
            "Identificar Patrón",
            "AHI y Severidad",
            "Diferenciación Apnea",
            "Factores de Riesgo",
            "Correlación ECG-Respiratoria"
        ]
    )
    
    if quiz_type == "Identificar Patrón":
        st.info("""
        **Pregunta:** ¿Cuál es el patrón respiratorio mostrado en la primera pestaña?
        
        Observa:
        1. La regularidad de los ciclos
        2. La amplitud (profundidad) de las respiraciones
        3. Los períodos sin flujo de aire (apneas)
        """)
        
        answer = st.radio("Tu respuesta:", [
            f"✓ {analysis.breathing_pattern.capitalize()}",
            "Otro patrón"
        ])
        
        if answer.startswith("✓"):
            st.success("✅ ¡Correcto!")
        else:
            st.error(f"❌ La respuesta correcta es: {analysis.breathing_pattern.capitalize()}")
    
    elif quiz_type == "AHI y Severidad":
        st.info(f"""
        **Pregunta:** ¿Cuál es la severidad de apnea basada en AHI = {analysis.apnea_hypopnea_index:.1f}?
        """)
        
        if analysis.apnea_hypopnea_index < 5:
            correct = "Normal"
        elif analysis.apnea_hypopnea_index < 15:
            correct = "Leve"
        elif analysis.apnea_hypopnea_index < 30:
            correct = "Moderada"
        else:
            correct = "Severa"
        
        answer = st.radio("Tu respuesta:", [
            f"✓ {correct}",
            "Otro grado"
        ])
        
        if answer.startswith("✓"):
            st.success("✅ ¡Correcto!")
        else:
            st.error(f"❌ La respuesta correcta es: {correct}")
    
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

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Frecuencia respiratoria", f"{analysis.respiratory_rate:.1f}", "breaths/min")
    st.metric("Patrón respiratorio", analysis.breathing_pattern.title())
    st.metric("Eventos de apnea", "Sí" if analysis.apnea_detected else "No")

with col2:
    st.metric("AHI estimado", f"{analysis.apnea_hypopnea_index:.1f}", "eventos/h")
    st.metric("Severidad", analysis.severity.title())
    st.metric("Respiraciones detectadas", len(analysis.breaths))

with col3:
    st.metric("SpO2 basal", f"{analysis.baseline_spo2:.1f}%")
    st.metric("SpO2 mínima", f"{analysis.minimum_spo2:.1f}%")
    st.metric("Tiempo <90%", f"{analysis.time_below_90:.1f}", "s")

st.markdown("**Notas clínicas clave:**")
for note in analysis.clinical_notes:
    st.markdown(f"- {note}")

st.markdown("**Interpretación rápida:**")
st.write(
    "Este análisis muestra el patrón respiratorio principal, el grado de desaturación y la presencia de apneas. "
    "Considere correlacionar estos resultados con síntomas clínicos, somnolencia diurna y factores de riesgo cardiopulmonar."
)

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
