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

from app.utils.design_system import BADGES, GRAMMAR_NEUTRAL_STATE, render_error_state, render_metric_card, resolve_metric_card
from educational.quiz_bank import EEG_QUESTIONS, KANE_2017

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
st.markdown("### Cómo funciona esta plataforma")
st.write(
    "Este laboratorio estudia la señal EEG en tres fases: adquisición, espectro y clasificación clínica. "
    "Primero convertimos la señal temporal en densidad espectral usando el método de Welch. "
    "Luego integramos la potencia dentro de las bandas Delta, Theta, Alpha, Beta y Gamma para obtener una descripción cuantitativa del ritmo cerebral. "
    "Finalmente, el módulo de interpretación asocia la banda dominante con estados como relajación, alerta, somnolencia o sueño profundo."
)

st.markdown('<a id="como-interpretar-eeg"></a>', unsafe_allow_html=True)
st.markdown("### Cómo interpretar EEG")
st.markdown(
    "- Potencia Delta alta sugiere sueño profundo o actividad cortical lenta.\n"
    "- Alpha dominante se asocia a relajación y ojos cerrados.\n"
    "- Beta elevada indica atención activa o estrés mental.\n"
    "- Picos rápidos pueden ser artefactos o actividad espigada en epilepsias.\n"
)

st.write(
    f"Con «{eeg_live_source.SOURCE_LABEL}» analizas tu propio EEG desde OpenBCI, Muse, Unicorn o un flujo LSL. Sin "
    "un equipo transmitiendo no hay análisis: no se usa una señal de respaldo. La pestaña "
    f"«{eeg_live_source.TUTORIAL_TAB}» explica cómo conectarlo y trae una práctica con simulador."
)

st.markdown("---")

# Sidebar
st.sidebar.markdown("# EEG Neuro Lab")
st.sidebar.markdown("### Parámetros de generación")
pattern = st.sidebar.selectbox(
    "Patrón EEG",
    [
        "Alpha (relajado)",
        "Beta (activo)",
        "Theta (sueño ligero)",
        "Delta (sueño profundo)",
        "Sleep Spindle",
        "Seizure (espigas)",
        "Artifact (parpadeo)",
        mu_erd_panel.MOTOR_IMAGERY_LABEL,
        engagement_panel.ENGAGEMENT_TASK_LABEL,
    ]
)
channels = st.sidebar.selectbox("Número de canales", [2, 3, 4], index=2)

signal_source = st.sidebar.radio(
    "Origen de datos",
    ["Generar EEG sintético", "Cargar EEG desde CSV", eeg_live_source.SOURCE_LABEL]
)
hardware_source = signal_source == eeg_live_source.SOURCE_LABEL
# Con EEG real (CSV o en vivo) la banda dominante no se traduce a un estado (`live_source.REAL_EEG_NOTE`).
interpretation_applies = signal_source == "Generar EEG sintético"

duration = st.sidebar.slider("Duración (segundos)", min_value=10, max_value=120, value=30, step=10)
fs = st.sidebar.selectbox("Frecuencia de muestreo (Hz)", [128, 256, 512], index=1)
noise = st.sidebar.slider("Nivel de ruido de fondo", min_value=0.0, max_value=0.5, value=0.18, step=0.02)

# Los paneles de ERD y Engagement comparan el detector contra el evento que inyecta el generador; con señal en
# vivo no hay evento inyectado, así que no se ofrecen (2026-11-14).
motor_event = None if hardware_source else mu_erd_panel.render_mu_erd_sidebar(pattern, duration)
engagement_event = None if hardware_source else engagement_panel.render_engagement_sidebar(pattern, duration)
# 2026-11-14: la casilla «Habilitar análisis en tiempo real» se retiró: solo mostraba un texto y no cambiaba nada
# (fachada, Art. I). El tiempo real de verdad es el monitor de la fuente en vivo.

uploaded_file = None
live = None
if signal_source == "Cargar EEG desde CSV":
    uploaded_file = st.sidebar.file_uploader(
        "Sube un archivo CSV de EEG",
        type=['csv'],
        help="Las columnas pueden incluir datos de EEG y una columna de tiempo opcional."
    )
    if uploaded_file is not None:
        st.sidebar.success("Archivo EEG cargado correctamente.")
    else:
        st.sidebar.info("Cargue un CSV para visualizar datos reales de EEG.")
elif hardware_source:
    live = eeg_live_source.render_live_source(duration)    # None sin señal en vivo: no hay respaldo sintético

st.sidebar.markdown("---")
st.sidebar.markdown("### Configuración Avanzada")

if signal_source == "Generar EEG sintético":
    st.sidebar.markdown("### Síntesis EEG")
    st.sidebar.write("Se generará una señal EEG de laboratorio con el patrón seleccionado.")
elif hardware_source:
    st.sidebar.markdown("### EEG en vivo")
    st.sidebar.write("El análisis usa los últimos segundos del equipo conectado (control «Duración»). Sin señal en vivo no se analiza nada.")
else:
    st.sidebar.markdown("### EEG desde CSV")
    st.sidebar.write("El análisis usará los datos cargados desde el archivo CSV.")

# Generate or load EEG
pattern_map = {
    "Alpha (relajado)": "alpha",
    "Beta (activo)": "beta",
    "Theta (sueño ligero)": "theta",
    "Delta (sueño profundo)": "delta",
    "Sleep Spindle": "sleep_spindle",
    "Seizure (espigas)": "seizure",
    "Artifact (parpadeo)": "artifact",
    mu_erd_panel.MOTOR_IMAGERY_LABEL: "motor_imagery",
    engagement_panel.ENGAGEMENT_TASK_LABEL: "engagement_task",
}
synthetic_params = EegPattern(
    pattern_type=pattern_map[pattern],
    duration=duration,
    fs=fs,
    amplitude=40.0,
    noise_level=noise,
    channels=channels,
    motor_event=motor_event,
    engagement_event=engagement_event,
)

data_source = "Sintético"
if signal_source == "Cargar EEG desde CSV" and uploaded_file is not None:
    eeg_data, time = load_eeg_csv(uploaded_file)
    data_source = "CSV cargado"
    if len(time) > 1:
        fs = float(round(1.0 / np.median(np.diff(time)), 2))
    if not eeg_data or 'time' not in eeg_data:
        eeg_data = {}
        time = np.array([])
        data_source = "Error de carga CSV"
elif hardware_source:
    data_source, eeg_data, time = "Hardware en vivo: sin señal", {}, np.array([])
    if live is not None:
        eeg_data, time, fs, data_source = live.eeg, live.time, live.fs, live.label
else:
    eeg_data, time = EegSignalGenerator(sampling_rate=fs).generate_eeg(synthetic_params)

analyzer = EegAnalyzer(fs=fs)

# Main panels
analysis_cards = []    # sin canales (fuente en vivo sin señal, CSV vacío) la columna de métricas no tiene qué leer
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("## 📈 Señales EEG")
    st.markdown(f"**Fuente de datos:** {data_source}  ")
    if data_source == "CSV cargado":
        st.markdown(f"**Frecuencia de muestreo estimada:** {fs:.2f} Hz")
    elif live is not None:
        st.markdown(f"**Muestreo del equipo:** {fs:g} Hz · últimos {len(time) / fs:.0f} s recibidos")

    lead_names = [k for k in eeg_data.keys() if k != 'time']
    display_leads = lead_names[:channels] if signal_source == "Cargar EEG desde CSV" else lead_names
    display_rows = max(len(display_leads), 1)

    if len(display_leads) == 0:
        st.warning("No hay datos EEG válidos." + ("" if hardware_source else " Cargue un archivo CSV o genere una señal sintética."))
    else:
        fig = make_subplots(rows=display_rows, cols=1, shared_xaxes=True, vertical_spacing=0.06)
        for idx, lead in enumerate(display_leads, start=1):
            fig.add_trace(
                go.Scatter(x=time, y=eeg_data[lead], name=lead, line=dict(width=1.5)),
                row=idx, col=1
            )
            fig.update_yaxes(title_text=lead, row=idx, col=1)
            fig.update_yaxes(showgrid=True, gridcolor='#334155', gridwidth=1, row=idx, col=1)
        fig.update_xaxes(title_text='Tiempo (s)', row=display_rows, col=1)
        fig.update_xaxes(showgrid=True, gridcolor='#334155', gridwidth=1, row=display_rows, col=1)
        fig.update_layout(height=250 * display_rows, template='plotly_dark', paper_bgcolor='#0f172a', plot_bgcolor='#0f172a', font=dict(color='#e0e7ff'))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("## 🧠 Análisis de Potencia de Banda")
        analysis_cards = []
        for lead in display_leads:
            result = analyzer.analyze(eeg_data[lead])
            analysis_cards.append((lead, result))
            st.markdown(f"### Canal {lead}")
            # Arco 2A: `result.available=False` (degradación tipo-PLV) deja
            # `summary=None`/`band_power={}` -- mostrar el motivo en vez de
            # `.write(None)` o un KeyError sobre un dict vacío.
            if not result.available:
                st.caption(f"⚠️ {result.reason}")
                continue
            st.write(eeg_live_source.channel_summary(result, interpretation_applies))
            band_table = {
                'Delta': f"{result.band_power['delta']:.2f}",
                'Theta': f"{result.band_power['theta']:.2f}",
                'Alpha': f"{result.band_power['alpha']:.2f}",
                'Beta': f"{result.band_power['beta']:.2f}",
                'Gamma': f"{result.band_power['gamma']:.2f}",
            }
            st.write(band_table)

        if motor_event is not None:
            mu_erd_panel.render_mu_erd_panel(eeg_data[display_leads[0]], display_leads[0], fs, time, motor_event)
        if engagement_event is not None:
            engagement_panel.render_engagement_panel(eeg_data[display_leads[0]], display_leads[0], fs, engagement_event)

with col2:
    st.markdown("## 📊 Métricas y Clasificación")
    overall = analysis_cards[0][1] if analysis_cards else None
    # Arco 2A (2026-09-11): degradación tipo-PLV -- `overall.available`
    # puede ser `False` (rechazo de artefactos dejó menos de
    # `MIN_CLEAN_EEG_DURATION_S` de señal limpia). En ese caso
    # `dominant_band`/`classification` son `None` -- mostrar el motivo en
    # vez de crashear con `.upper()` sobre `None`, espejo del PLV
    # ("no disponible", nunca un número sobre lo que sobró).
    if overall is not None and not overall.available:
        st.info(f"Canal {analysis_cards[0][0]}: {overall.reason}")
    elif overall is not None:
        # Consolidación Visual Tanda 3 (2026-09-21): `st.metric` crudo ->
        # `render_metric_card`. `dominant_band`/`classification` son
        # cálculo real de `EegAnalyzer` (banda de potencia máxima + mapa de
        # texto interno) sin cita clínica externa que los respalde --
        # `BADGES.HEURISTIC`, criterio conservador por default cuando no
        # hay `*_CITATION` que aplicar (a diferencia de DAR/TBR/BAR/χ, que
        # sí tienen la suya, ver abajo). Sin `classification=`: no existe
        # un `classify_*()` para banda dominante/clasificación de patrón,
        # así que el marco queda NEUTRAL por default -- no se fabrica un
        # semáforo que nadie validó.
        render_metric_card(
            "Banda dominante", overall.dominant_band.upper(),
            provenance=BADGES.HEURISTIC,
        )
        if interpretation_applies:
            render_metric_card("Clasificación", overall.classification, provenance=BADGES.HEURISTIC)
        else:
            render_metric_card("Clasificación", None, unavailable_reason=eeg_live_source.REAL_EEG_NOTE)
        st.markdown("### Interpretación Clínica")
        st.write(
            "Este laboratorio simula ondas EEG típicas y las clasifica en patrones de alerta, relajación y sueño."
            if interpretation_applies else
            "Con EEG real se muestran las mediciones (potencias, cocientes con su fuente) sin traducirlas a un estado."
        )
        st.markdown("### Hallazgos clínicos EEG")
        # Consolidación Visual Tanda 3 (2026-09-21): DAR/TBR/BAR ya no se
        # leen desde `overall.findings` (donde llegaban como texto plano
        # pre-formateado con su badge incrustado a mano, p.ej.
        # `f"{dar_badge} {dar:.2f} ({dar_label})"` -- construido en
        # `eeg_analyzer.py`, sin marco de honestidad alrededor). Se
        # recalculan aquí exactamente como ya hace el botón "Exportar
        # informe EEG" más abajo (`classify_dar(overall.dar)`/
        # `classify_tbr(overall.tbr)`, MISMA expresión, cero cambio de
        # valor) y se renderizan con `render_metric_card` -- honestidad
        # visible también en la vista EN VIVO, no solo en el export. Las
        # tres claves de ratio se excluyen del loop genérico de abajo para
        # no mostrar el mismo valor dos veces con dos estilos distintos.
        _ratio_keys = {'Delta/Alpha Ratio (DAR)', 'Theta/Beta Ratio (TBR)', 'Beta/Alpha Ratio (BAR)'}
        if classify_dar is not None:
            if overall.dar is not None:
                render_metric_card(
                    'DAR (Delta/Alfa)', f'{overall.dar:.2f}',
                    classification=classify_dar(overall.dar), citation=DAR_CITATION,
                )
            else:
                render_metric_card(
                    'DAR (Delta/Alfa)', None,
                    unavailable_reason='indefinido -- sin ritmo alfa medible (alpha_power ~0)',
                )
        if classify_tbr is not None:
            if overall.tbr is not None:
                render_metric_card(
                    'TBR (Theta/Beta)', f'{overall.tbr:.2f}',
                    classification=classify_tbr(overall.tbr), citation=TBR_CITATION,
                )
            else:
                render_metric_card(
                    'TBR (Theta/Beta)', None,
                    unavailable_reason='indefinido -- sin ritmo beta medible (beta_power ~0)',
                )
        # BAR: sin `classify_bar()` a propósito (decisión firme, ver
        # `design_system.py`/CHANGELOG.md -- Schutter 2006 no establece
        # zonas clínicas de 3 niveles). `GRAMMAR_NEUTRAL_STATE` sin
        # `classification=`: el marco queda NEUTRAL, la forma honesta de
        # mostrar un estado sin fabricar un semáforo.
        if overall.bar is not None:
            render_metric_card(
                'BAR (Beta/Alfa)', f'{overall.bar:.2f}',
                provenance=BADGES.CLINICAL, grammar=GRAMMAR_NEUTRAL_STATE, citation=BAR_CITATION,
            )
        else:
            render_metric_card(
                'BAR (Beta/Alfa)', None,
                unavailable_reason='indefinido -- sin ritmo alfa medible (alpha_power ~0)',
            )
        shown_findings = eeg_live_source.visible_findings(overall.findings, interpretation_applies)
        for key, value in shown_findings.items():
            if key in _ratio_keys:
                continue
            st.write(f"**{key}:** {value}")

        if export_lab_report is not None and st.button("Exportar informe EEG"):
            metrics = {
                'data_source': data_source,
                'fs': fs,
                'dominant_band': overall.dominant_band,
                'classification': overall.classification if interpretation_applies else 'no se interpreta (EEG real)',
            }
            for bname, val in overall.band_power.items():
                metrics[f'band_{bname}'] = float(val)
            notes = f"EEG Neuro Lab autogenerated report. {shown_findings.get('Clinical Note', '')}"
            findings = shown_findings

            # Consolidación Visual Tanda 2 (2026-09-21): antes `findings`
            # llevaba el badge+etiqueta de DAR/TBR (heredado de
            # `EegAnalyzer.analyze()`) pero NUNCA la cita, y χ no aparecía
            # en este export en absoluto -- el hallazgo central del
            # diagnóstico anterior. `honesty_cards` arma cada valor desde
            # la MISMA fuente que la app viva (`resolve_metric_card()`,
            # `design_system.py`) -- DAR/TBR bajo su gramática de siempre
            # (severidad, sin cambios), BAR y χ bajo GRAMMAR_NEUTRAL_STATE
            # (decisión firme de esta tanda: son estados sin valencia de
            # peligro, no un semáforo). Ningún valor se fabrica: si DAR/
            # TBR/BAR son indefinidos (denominador ~0) o χ degrada por sus
            # guardianes (Arco 2C), la tarjeta lleva el motivo exacto, no
            # un número relleno.
            honesty_cards = []
            if classify_dar is not None:
                if overall.dar is not None:
                    honesty_cards.append(resolve_metric_card(
                        'DAR (Delta/Alfa)', f'{overall.dar:.2f}',
                        classification=classify_dar(overall.dar), citation=DAR_CITATION,
                    ))
                else:
                    honesty_cards.append(resolve_metric_card(
                        'DAR (Delta/Alfa)', None,
                        unavailable_reason='indefinido -- sin ritmo alfa medible (alpha_power ~0)',
                    ))
            if classify_tbr is not None:
                if overall.tbr is not None:
                    honesty_cards.append(resolve_metric_card(
                        'TBR (Theta/Beta)', f'{overall.tbr:.2f}',
                        classification=classify_tbr(overall.tbr), citation=TBR_CITATION,
                    ))
                else:
                    honesty_cards.append(resolve_metric_card(
                        'TBR (Theta/Beta)', None,
                        unavailable_reason='indefinido -- sin ritmo beta medible (beta_power ~0)',
                    ))
            if overall.bar is not None:
                honesty_cards.append(resolve_metric_card(
                    'BAR (Beta/Alfa)', f'{overall.bar:.2f}',
                    provenance=BADGES.CLINICAL, grammar=GRAMMAR_NEUTRAL_STATE, citation=BAR_CITATION,
                ))
            else:
                honesty_cards.append(resolve_metric_card(
                    'BAR (Beta/Alfa)', None,
                    unavailable_reason='indefinido -- sin ritmo alfa medible (alpha_power ~0)',
                ))
            # χ: mismo motor y mismas entradas reales que ya usa el botón
            # "Guardar estado al gemelo" (overall.psd_freqs/psd_power/
            # clean_window_count, fs) -- sin duplicar fit_aperiodic_
            # component(). Si `fooof` no resolvió en este entorno, χ
            # simplemente no se agrega, nunca se fabrica.
            if fit_aperiodic_component is not None and overall.psd_freqs is not None:
                chi_result = fit_aperiodic_component(
                    overall.psd_freqs, overall.psd_power,
                    clean_window_count=overall.clean_window_count, bandpass_fs=fs,
                )
                if chi_result.available:
                    honesty_cards.append(resolve_metric_card(
                        'χ (aperiódico)', f'{chi_result.exponent:.2f}',
                        classification=classify_chi(chi_result.exponent), grammar=GRAMMAR_NEUTRAL_STATE,
                        citation=CHI_CITATION,
                    ))
                else:
                    honesty_cards.append(resolve_metric_card('χ (aperiódico)', None, unavailable_reason=chi_result.reason))

            tmpdir = tempfile.mkdtemp(prefix='bsp_report_')
            try:
                bp_path = os.path.join(tmpdir, 'eeg_band_power.png')
                try:
                    labels = list(overall.band_power.keys())
                    values = [float(overall.band_power[k]) for k in labels]
                    reporting._save_bar_plot(bp_path, labels, values, title='EEG Band Power')
                except Exception:
                    pass
                image_paths = []
                if os.path.exists(bp_path):
                    image_paths.append(('EEG Band Power', bp_path))
                # Sin `validation=`: firmado explícitamente como mudo por
                # el experto (Tanda Final, ver `eeg_neuro_lab/pages.py`) --
                # contenedor mixto (DAR/TBR clínico, χ en observación), una
                # etiqueta de módulo única mentiría sobre alguna parte. Los
                # `honesty_cards` de arriba (DAR/TBR/BAR/χ, cada uno con su
                # propio badge) hacen el trabajo fino también en el export.
                path = export_lab_report(
                    'EEG Neuro Lab', metrics, notes=notes, findings=findings, image_paths=image_paths,
                    honesty_cards=honesty_cards,
                )
            finally:
                try:
                    shutil.rmtree(tmpdir)
                except Exception:
                    pass
            st.success(f"Informe exportado: {path}")

        # Capa 5A, Sub-fase 1 (2026-08-30): cuarto lab que escribe al UPS
        # real, mismo patrón que Respiratory/HRV/ECG Lab (Fase 2.4) --
        # botón explícito, nunca automático.
        #
        # Qué escribe: los 5 band power reales de `overall`
        # (`EegAnalyzer.analyze()` sobre el canal `analysis_cards[0][0]`,
        # el mismo que ya alimenta "Métricas y Clasificación" arriba -- sin
        # recalcular nada). Arco 2C (2026-09-14): + χ aperiódico (exponente
        # 1/f, `spectral_model.fit_aperiodic_component()`) sobre el MISMO
        # PSD de `overall` (`psd_freqs`/`psd_power`, aditivos desde 2C) --
        # solo si supera su propio gate de duración+calidad
        # (`MIN_CHI_CLEAN_WINDOWS` + R², más estricto que el de band power);
        # si degrada, la clave `chi_aperiodic` no se envía y el resto del
        # guardado no se ve afectado. Arco 2D (2026-09-18): χ se persiste
        # `VALIDADO_POR_FUENTE` con badge 🔴/🔵/💤 (`classify_chi()`) --
        # ver `builder.py::_neurological_state`.
        # Fase 0 (2026-11-13, Art. I): el organismo ya no deriva NADA del
        # cerebro (health_score/risk_score con defaults 35/65, mental_workload
        # = beta_power con otro nombre, stress_perception, attention...: todos
        # retirados). Al UPS llegan exactamente las 5 potencias de banda, los
        # cocientes BAR/DAR/TBR (identidades aritméticas con cita) y, si pasa
        # su gate, chi. El gate de `_neurological_state()` (`alpha_power`/
        # `beta_power` presentes) es lo que decide "hay cerebro que escribir".
        #
        # Procedencia (2026-11-14): `Provenance.SENSOR_REAL` solo con un equipo
        # real transmitiendo en este momento (`live_source.twin_provenance`);
        # todo lo demás (generador, CSV, simuladores, LSL no verificable) se
        # guarda como `Provenance.SIMULACION`, con el origen en `source_detail`.
        # Un canal en vivo con avisos de calidad no se guarda (`save_blocker`).
        st.markdown("---")
        st.markdown("#### 🔗 Guardar estado al gemelo")
        eeg_lab_channel = analysis_cards[0][0]
        twin_prov, twin_note = eeg_live_source.twin_provenance(live)
        st.caption(
            f"Escribe la potencia de banda real (delta/theta/alpha/beta/gamma) del canal "
            f"**{eeg_lab_channel}** al Unified Physiological State, bajo el mismo paciente que "
            "renderiza Digital Twin OS -- su cerebro reaccionará a estos valores la próxima vez "
            f"que abras esa página o pulses \"Guardar este momento\" ahí. {twin_note}"
        )
        if st.button("💾 Guardar estado al gemelo", key="eeg_lab_save_to_ups"):
            blocker = eeg_live_source.save_blocker(live, eeg_lab_channel)
            # Arco 2A (2026-09-11): `overall` puede llegar `available=False`
            # (degradación tipo-PLV -- rechazo de artefactos dejó menos
            # señal limpia que `MIN_CLEAN_EEG_DURATION_S`). El botón no
            # finge guardar: declara que no hay banda de potencia real que
            # persistir, y NO llama a `update_from_sensors()` -- el gate de
            # `_neurological_state()` (sin tocar) deja el dominio neuro
            # vacío porque nunca recibe `alpha_power`/`beta_power`.
            if not overall.available:
                st.info(
                    f"Sin señal EEG limpia suficiente para guardar al gemelo -- {overall.reason}. "
                    "No hay banda de potencia real que persistir."
                )
            elif blocker:
                st.warning(f"⛔ No se guarda al gemelo: {blocker}")
            else:
                session_factory = get_active_session_factory()
                patient_id = get_active_patient_id()

                # Arco 2C (2026-09-14): χ aperiódico, aditivo -- consume el
                # MISMO PSD que `overall` ya calculó (`psd_freqs`/`psd_power`,
                # expuestos aditivamente en Arco 2C, Parte A -- ningún
                # recálculo de band power). `clean_window_count` alimenta el
                # gate de duración propio del χ (`MIN_CHI_CLEAN_WINDOWS`,
                # más estricto que el de los ratios) -- si degrada (pocas
                # ventanas O R² bajo), `chi_result.available=False` y la
                # clave `chi_aperiodic` simplemente no se agrega abajo: el
                # resto del guardado (band power, BAR/DAR/TBR) sigue intacto.
                chi_result = None
                if fit_aperiodic_component is not None and overall.psd_freqs is not None:
                    # `bandpass_fs=fs`: el PSD de `overall` pasó por el
                    # bandpass de `preprocess_eeg()` dentro de `analyze()`
                    # (Arco 2A) -- sin corregir esa distorsión, chi queda
                    # sesgado ~+0.46 (hallazgo de Arco 2C, ver
                    # `spectral_model.py`). `fs` es la misma frecuencia de
                    # muestreo que ya se usó para instanciar `analyzer`.
                    chi_result = fit_aperiodic_component(
                        overall.psd_freqs, overall.psd_power,
                        clean_window_count=overall.clean_window_count,
                        bandpass_fs=fs,
                    )

                eeg_sensors = {
                    "delta_power": float(overall.band_power["delta"]),
                    "theta_power": float(overall.band_power["theta"]),
                    "alpha_power": float(overall.band_power["alpha"]),
                    "beta_power": float(overall.band_power["beta"]),
                    "gamma_power": float(overall.band_power["gamma"]),
                }
                if chi_result is not None and chi_result.available:
                    eeg_sensors["chi_aperiodic"] = float(chi_result.exponent)

                eeg_organism = DigitalTwinOrganism()
                eeg_organism.update_from_sensors({"eeg": eeg_sensors})
                eeg_ups_state = from_digital_twin_organism(
                    eeg_organism, patient_id, provenance=twin_prov,
                    source_detail=(f"eeg_neuro_lab:canal={eeg_lab_channel}:banda_dominante={overall.dominant_band}"
                                   f":fuente={data_source}"),
                )
                with session_factory() as eeg_ups_session:
                    eeg_snapshot_id = save_state(eeg_ups_session, eeg_ups_state)

                    # Acoplamientos Sub-fase B (2026-09-06): tras persistir, se
                    # evalúa el catálogo validado (`AROUSAL_TAQUICARDIA_BAR`:
                    # arousal cortical BAR>1.8 -> ↑FC +15 bpm, Guyton cap.61 +
                    # Schutter 2006). `scenario=None`: EEG Lab es un escritor
                    # neuro-sin-CV-correlacionada, NO un escenario de estrés
                    # (`COUPLING_DISABLED_SCENARIOS`). El puente solo escribe
                    # `heart_rate_acoplado` si el snapshot tiene una FC medida
                    # -- este lab no la envía, así que hoy es un no-op honesto
                    # aquí; la regla dispara en cuanto el snapshot lleve FC.
                    try:
                        coupled = apply_couplings(
                            eeg_ups_session, eeg_snapshot_id, VALIDATED_RULES, scenario=None
                        )
                    except CouplingScenarioBlockedError:
                        coupled = []  # inalcanzable con scenario=None; defensivo
                    bar_desc = eeg_ups_state.neurological.get("bar")

                st.success(f"Estado guardado al gemelo -- snapshot: {eeg_snapshot_id}")
                st.caption(f"neurological: {len(eeg_ups_state.neurological.descriptors)} descriptores")
                # Consolidación Visual Tanda 3 (2026-09-21): `bar_txt`/el
                # caption manual de χ (f-strings con el badge incrustado a
                # mano) -> `render_metric_card`, mismo criterio que la
                # sección "Hallazgos clínicos EEG" arriba -- BAR bajo
                # GRAMMAR_NEUTRAL_STATE sin classification (sin
                # `classify_bar()`), χ bajo GRAMMAR_NEUTRAL_STATE con
                # `classify_chi()` (idéntica llamada a la que ya usaba el
                # caption manual, cero cambio de valor).
                if bar_desc is not None:
                    render_metric_card(
                        'BAR (Beta/Alfa)', f'{bar_desc.value:.2f}',
                        provenance=BADGES.CLINICAL, grammar=GRAMMAR_NEUTRAL_STATE, citation=BAR_CITATION,
                    )
                else:
                    render_metric_card(
                        'BAR (Beta/Alfa)', None,
                        unavailable_reason='indefinido (sin ritmo alfa)',
                    )
                if chi_result is not None and chi_result.available:
                    render_metric_card(
                        'χ (aperiódico)', f'{chi_result.exponent:.2f}',
                        classification=classify_chi(chi_result.exponent), grammar=GRAMMAR_NEUTRAL_STATE,
                        citation=CHI_CITATION,
                    )
                elif chi_result is not None:
                    render_metric_card('χ (aperiódico)', None, unavailable_reason=chi_result.reason)
                if coupled:
                    ac = coupled[0]
                    st.caption(
                        f"🔗 Acoplamiento **{ac.rule_id}**: FC medida {ac.base_value:.0f} -> "
                        f"FC acoplada **{ac.coupled_value:.0f} bpm** (DERIVADO_ACOPLAMIENTO, "
                        f"confianza {ac.confidence:.2f}) -- BAR observado {ac.observed_value:.2f}"
                    )
                else:
                    st.caption(
                        "🔗 Acoplamiento AROUSAL_TAQUICARDIA_BAR: sin FC medida en este snapshot, "
                        "nada que modular (se aplicaría si el paciente tuviera FC medida y BAR>1.8)."
                    )
                st.caption(
                    f"cardiovascular: {len(eeg_ups_state.cardiovascular.descriptors)} descriptores "
                    "(vacío esperado -- este lab no envía dato cardíaco) · "
                    f"respiratory: {len(eeg_ups_state.respiratory.descriptors)} descriptores "
                    "(vacío esperado -- este lab no envía dato respiratorio)"
                )

    st.markdown("---")
    st.markdown("## 📚 Referencias EEG")
    # 2026-11-14 (Art. I): antes cinco líneas sin fuente («Gamma: procesamiento cognitivo integrado»,
    # «Beta: alerta y concentración»...). Ahora: el glosario IFCN 2017 al lado de los bordes que de verdad
    # usa este laboratorio (`EegAnalyzer._band_powers`), que difieren un poco del glosario.
    st.markdown(
        "| Banda | Glosario IFCN 2017 | Este laboratorio |\n"
        "|---|---|---|\n"
        "| Delta | 0.1 a menos de 4 Hz | 0.5–3.5 Hz |\n"
        "| Theta | 4 a menos de 8 Hz | 4–7.5 Hz |\n"
        "| Alfa | 8–13 Hz | 8–12 Hz |\n"
        "| Beta | 14–30 Hz | 13–30 Hz |\n"
        "| Gamma | más de 30, hasta 80 Hz | 30–45 Hz |"
    )
    st.markdown(
        "- **Delta:** el sueño profundo (NREM N3) está dominado (≥ 20 %) por ondas delta de 0.5–2 Hz y "
        "más de 75 µV. En la práctica, el límite inferior es 0.5 Hz.\n"
        "- **Alfa:** ritmo de vigilia sobre las regiones posteriores; se ve mejor con los ojos cerrados y se "
        "bloquea con la atención, sobre todo visual.\n"
        "- **Beta:** en vigilia, sobre todo fronto-central; si es difuso puede deberse a fármacos (alcohol, "
        "barbitúricos, benzodiacepinas, anestésicos intravenosos)."
    )
    st.caption(f"Fuente: {KANE_2017}")

    with st.expander("🧪 Quiz interactivo EEG"):
        # 2026-11-14 (Art. I): el banco vive en `educational/quiz_bank.py`, con su fuente. Antes: sin
        # fuentes, la pregunta de crisis se respondía sola («crisis epiléptica» → «Seizure») y cada radio
        # empezaba en la primera opción, así que «Calcular puntuación» sin contestar ya sumaba aciertos.
        user_answers = []
        for idx, item in enumerate(EEG_QUESTIONS, start=1):
            user_answers.append(st.radio(item.prompt, item.display_choices(), index=None, key=f"eeg_quiz_{idx}"))

        if st.button("Calcular puntuación", key="submit_eeg_quiz"):
            score = sum(1 for answer, item in zip(user_answers, EEG_QUESTIONS) if item.is_correct(answer))
            unanswered = sum(1 for answer in user_answers if answer is None)
            st.success(f"Has respondido {score} de {len(EEG_QUESTIONS)} correctamente.")
            if unanswered:
                st.warning(f"{unanswered} pregunta(s) sin responder: cuentan como no acertadas.")
            for item, answer in zip(EEG_QUESTIONS, user_answers):
                st.write(f"**Pregunta:** {item.prompt}")
                st.write(f"- Tu respuesta: {answer if answer is not None else 'sin responder'}")
                st.write(f"- Correcta: {item.correct_choice}")
                st.write(f"- Explicación: {item.explanation}")
                st.caption(f"Fuente: {item.source}")
                st.write("---")

st.markdown("---")
st.markdown("*Fase 3: EEG Neuro Lab - inicio del laboratorio de electroencefalografía clínica educativa en español.*")
