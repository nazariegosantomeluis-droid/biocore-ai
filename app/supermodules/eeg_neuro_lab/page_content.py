"""
EEG Neuro Lab - Phase 3 of Biomedical Signal Visualizer

Interactive EEG education and analysis:
- Brainwave generation (delta/theta/alpha/beta/gamma)
- Spectral power analysis
- Sleep stage / activation classification
- Seizure and artifact pattern generation (synthetic; no detection algorithm)
- Clinical learning module in Spanish
"""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
import io
import tempfile
import shutil

# Ruta ajustada (Tanda de eliminación de pages_legacy, Movimiento 1, 2026-07-13):
# este archivo vivía en app/pages_legacy/ (2 niveles bajo la raíz del repo) y ahora
# vive en app/supermodules/eeg_neuro_lab/ (3 niveles) — un nivel más de
# profundidad, así que el cálculo de la raíz del repo necesita un salto más.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from app.supermodules.eeg_neuro_lab.teaching import render_eeg_quiz, render_eeg_references
from src.signals.eeg.eeg_analyzer import FINDING_LABELS_ES, band_label_es
from app.utils.design_system import BADGES, GRAMMAR_NEUTRAL_STATE, PALETTE, render_error_state, render_metric_card, resolve_metric_card

# Capa 5A, Sub-fase 1 (2026-08-30): cierre del círculo EEG->UPS->gemelo --
# mismo patrón que Respiratory/HRV/ECG Lab (Fase 2.4), aplicado al cuarto
# escritor. Imports incondicionales (no como EegAnalyzer de
# abajo) porque domain.physiology.state/app.engines/app.utils.patient_session
# son parte del núcleo de la app, no dependencias opcionales.
from domain.physiology.state import from_digital_twin_organism, save_state
from domain.physiology.coupling import (
    VALIDATED_RULES,
    CouplingScenarioBlockedError,
    apply_couplings,
)
from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.utils.patient_session import get_active_patient_id, get_active_session_factory

try:
    from src.signals.eeg import (
        EegSignalGenerator, EegPattern, EegAnalyzer,
        classify_dar, classify_tbr, DAR_CITATION, TBR_CITATION, BAR_CITATION,
    )
    from app.supermodules.eeg_neuro_lab import engagement_panel, mu_erd_panel
    Eeg_import_error = None
except ImportError as e:
    mu_erd_panel = None
    engagement_panel = None
    EegSignalGenerator = None
    EegPattern = None
    EegAnalyzer = None
    classify_dar = None
    classify_tbr = None
    DAR_CITATION = None
    TBR_CITATION = None
    BAR_CITATION = None
    Eeg_import_error = e

# Arco 2C (2026-09-14): motor de parametrización espectral (χ aperiódico),
# elevado desde el banco de pruebas aislado de Arco 2B
# (`src/signals/eeg/spectral_model.py`). Import guardado igual que
# `EegAnalyzer` arriba -- `fooof` es una dependencia nueva y más pesada que
# scipy/numpy; si no resolviera en algún entorno, el resto del EEG Lab
# (potencia de banda, BAR/DAR/TBR, guardado al gemelo) sigue funcionando sin
# χ, nunca crashea por su ausencia.
try:
    from src.signals.eeg.spectral_model import CHI_CITATION, classify_chi, fit_aperiodic_component
    SpectralModel_import_error = None
except ImportError as e:
    fit_aperiodic_component = None
    classify_chi = None
    CHI_CITATION = None
    SpectralModel_import_error = e

# 2026-11-14 (Art. I): la fuente en vivo ya no usa SensorManager/ESP32SignalSource (inventaba 4 canales a partir
# de una señal y caía en silencio a la sintética). Vive en `live_source.py`: OpenBCI, Muse, Unicorn, LSL y dos
# simuladores rotulados SIMULACIÓN; SENSOR_REAL solo mientras un equipo real manda datos.
from app.supermodules.eeg_neuro_lab import live_source as eeg_live_source

try:
    from app.reporting import export_lab_report
    import app.reporting as reporting
except Exception:
    export_lab_report = None
    reporting = None


def load_eeg_csv(uploaded_file):
    raw = uploaded_file.getvalue().decode('utf-8', errors='replace')
    text = io.StringIO(raw)
    try:
        data = np.genfromtxt(text, delimiter=',', names=True, dtype=float, invalid_raise=False)
    except ValueError:
        text.seek(0)
        data = np.genfromtxt(text, delimiter=',', dtype=float)

    result = {}
    time = None
    if data is None or (hasattr(data, 'size') and data.size == 0):
        return result, np.array([])

    if hasattr(data, 'dtype') and data.dtype.names is not None:
        names = list(data.dtype.names)
        time_keys = [name for name in names if name.lower() in ('time', 't', 'timestamp', 'ts')]
        if time_keys:
            time = np.asarray(data[time_keys[0]], dtype=float)
        else:
            first_name = names[0]
            time = np.arange(len(data[first_name]), dtype=float)
        for name in names:
            if name.lower() in ('time', 't', 'timestamp', 'ts'):
                continue
            result[name] = np.asarray(data[name], dtype=float)
    elif isinstance(data, np.ndarray):
        if data.ndim == 1:
            time = np.arange(data.shape[0], dtype=float)
            result['EEG1'] = data
        else:
            time = np.arange(data.shape[0], dtype=float)
            for idx in range(min(data.shape[1], 8)):
                result[f'EEG{idx + 1}'] = np.asarray(data[:, idx], dtype=float)

    if time is None and result:
        time = np.arange(len(next(iter(result.values()))), dtype=float)

    result['time'] = time
    return result, time


# `st.set_page_config()` y `render_sidebar_navigation()` retirados
# (2026-08-20, Capa 2 Fase 2.1, cierre): vestigios de la arquitectura
# Streamlit multipágina anterior. Este archivo solo corre anidado bajo
# `app/main.py` (vía `runpy.run_path()` desde `eeg_neuro_lab/pages.py`), que
# ya configuró la página una sola vez al inicio. Ver CHANGELOG.md.

# Consolidación Visual Tanda 3 (2026-09-21): `<style>` propio retirado --
# duplicaba `inject_global_theme()` (fondo/texto/acento globales, ya
# cableado en `app/main.py`) con los MISMOS 4 hex (`#0f172a`/`#e0e7ff`/
# `#1d4ed8`/`#8ecae6`, ver `PALETTE`), y `.metric-card` (el único selector
# no cubierto por el tema global) no se usaba en ningún `<div>` de este
# archivo -- CSS muerto, mismo patrón que `.biocore-card` que ya documentó
# `design_system.py::inject_global_theme()`. Ver CHANGELOG.md.

if Eeg_import_error is not None or EegSignalGenerator is None:
    render_error_state("El módulo de generación/análisis de EEG no se ha podido cargar.", exception=Eeg_import_error)
    st.stop()

# Consolidación Visual Tanda 1 (2026-09-20): título + subtítulo propios
# retirados -- duplicaban el `<h1>` que `pages.py::render_views()` ya
# dibuja vía `render_module_header("EEG Neuro Lab", ..., subtitle=...)`
# antes de invocar este archivo por `runpy`. Ver CHANGELOG.md.
# Tanda 2 de la fase 1: «Cómo funciona» e «interpretar» pasaron al final, en pestañas (a demanda).

# Sidebar
st.sidebar.markdown("# Laboratorio de EEG")

# T4 de la ruta integrada (2026-11-18): el código que estaba aquí (controles, señal, potencia de banda, métricas, informe
# y guardado al gemelo) se movió TAL CUAL a `app/instruments/eeg.py`; esta página es la composición de esos
# instrumentos con `PAGE`: mismos controles sin clave en la barra lateral, mismas columnas y mismos textos. Una estación
# de la Ruta monta los mismos instrumentos con `station_context`.
from app.instruments import eeg as E
from app.instruments.base import PAGE

series = E.fuente(PAGE)
if series is None:
    st.stop()
live = series.live

# Main panels
col1, col2 = st.columns([2, 1])

with col1:
    E.senales(PAGE, series)

with col2:
    overall = E.metricas(PAGE, series)
    E.guardar(PAGE, series, overall)

    st.markdown("---")
    tab_how, tab_refs, tab_quiz = st.tabs(["Cómo funciona", "Referencias EEG", "Quiz"])
    with tab_how:
        st.markdown("### Cómo funciona esta plataforma")
        st.write(
            "Este laboratorio estudia la señal EEG en dos fases: adquisición y espectro. "
            "Primero convertimos la señal temporal en densidad espectral usando el método de Welch. "
            "Luego integramos la potencia dentro de las bandas Delta, Theta, Alfa, Beta y Gamma para obtener una descripción cuantitativa del ritmo cerebral. "
            "La banda dominante no se traduce a un estado (relajación, alerta, sueño): BIOCORE no tiene una fuente para "
            "hacerlo. Los cocientes que sí la tienen (DAR, TBR, BAR) se muestran con su cita."
        )

        st.markdown('<a id="como-interpretar-eeg"></a>', unsafe_allow_html=True)
        st.markdown("### Cómo interpretar EEG")
        st.markdown(
            "- Potencia Delta alta sugiere sueño profundo o actividad cortical lenta.\n"
            "- Alfa dominante se asocia a relajación y ojos cerrados.\n"
            "- Beta elevada indica atención activa o estrés mental.\n"
            "- Picos rápidos pueden ser artefactos o actividad espigada en epilepsias.\n"
        )

        st.write(
            f"Con «{eeg_live_source.SOURCE_LABEL}» analizas tu propio EEG desde OpenBCI, Muse, Unicorn o un flujo LSL. Sin "
            "un equipo transmitiendo no hay análisis: no se usa una señal de respaldo. La pestaña "
            f"«{eeg_live_source.TUTORIAL_TAB}» explica cómo conectarlo y trae una práctica con simulador."
        )
    with tab_refs:
        render_eeg_references()
    with tab_quiz:
        render_eeg_quiz()

st.markdown("---")
st.markdown("*Fase 3: Laboratorio de EEG - inicio del laboratorio de electroencefalografía clínica educativa en español.*")
