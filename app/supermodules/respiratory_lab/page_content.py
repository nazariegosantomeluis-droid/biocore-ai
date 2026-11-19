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
    <div style='padding: 16px; border-radius: 16px; background: {PALETTE.BACKGROUND}; border: 1px solid {PALETTE.GRID}; margin-bottom: 24px;'>
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

# T4 de la ruta integrada (2026-11-18): el código que estaba aquí se movió TAL CUAL a `app/instruments/respiracion.py`
# (controles, generación, análisis y vistas); esta página es la composición de esos instrumentos con `PAGE`: mismos
# controles sin clave en la barra lateral, mismas pestañas, mismos textos. Una estación de la Ruta monta los mismos
# instrumentos con `station_context`.
from app.instruments import respiracion as R
from app.instruments.base import PAGE

run = R.patron(PAGE)
st.sidebar.markdown("---")
if run is None:
    from app.supermodules.respiratory_lab.pages import VistaClinicaOmitida
    raise VistaClinicaOmitida("parámetros imposibles")

analysis = run.analysis

# Puente de sesión: expone el análisis ya calculado aquí a la pestaña "Investigación" de respiratory_lab/pages.py
# (sin recalcular). `with tabs[0]:` (Clínica) corre en cada rerun, así que el dato existe cuando la otra pestaña lo lee.
st.session_state['_respiratory_lab_analysis'] = {
    'analysis': analysis,
    'pattern_display': run.pattern_display,
    'duration': run.duration,
}

R.valores(PAGE, run)

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
    R.senales(PAGE, run)

with tab2:
    R.spo2(PAGE, run)

with tab3:
    R.apneas(PAGE, run)

with tab4:
    views.render_clinical_references()

with tab5:
    views.render_quiz(analysis)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# CLINICAL SUMMARY
# ═══════════════════════════════════════════════════════════════

R.resumen(PAGE, run)

# ═══════════════════════════════════════════════════════════════
# EDUCATIONAL SIDEBAR
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("---")
    views.render_education_topics()
