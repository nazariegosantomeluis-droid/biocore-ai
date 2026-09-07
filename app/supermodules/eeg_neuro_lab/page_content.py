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

from app.utils.design_system import render_error_state

# Capa 5A, Sub-fase 1 (2026-08-30): cierre del círculo EEG->UPS->gemelo --
# mismo patrón que Respiratory/HRV/ECG Lab (Fase 2.4), aplicado al cuarto
# escritor. Imports incondicionales (no como EegAnalyzer/SensorManager de
# abajo) porque domain.physiology.state/app.engines/app.utils.patient_session
# son parte del núcleo de la app, no dependencias opcionales.
from domain.physiology.state import Provenance, from_digital_twin_organism, save_state
from domain.physiology.coupling import (
    VALIDATED_RULES,
    CouplingScenarioBlockedError,
    apply_couplings,
)
from app.engines.digital_twin_organism import DigitalTwinOrganism
from app.utils.patient_session import get_active_patient_id, get_active_session_factory

try:
    from src.signals.eeg import EegSignalGenerator, EegPattern, EegAnalyzer
    Eeg_import_error = None
except ImportError as e:
    EegSignalGenerator = None
    EegPattern = None
    EegAnalyzer = None
    Eeg_import_error = e

try:
    from hardware.sensor_manager import SensorManager
    SensorManager_import_error = None
except ImportError as e:
    SensorManager = None
    SensorManager_import_error = e

try:
    from src.signals.signal_sources import ESP32SignalSource
    ESP32SignalSource_import_error = None
except ImportError as e:
    ESP32SignalSource = None
    ESP32SignalSource_import_error = e

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


def expand_hardware_eeg_to_channels(reference_signal: np.ndarray, fs: float, channels: int):
    lead_names = ['Fp1', 'Fp2', 'C3', 'C4'][: max(1, min(channels, 4))]
    if reference_signal is None or len(reference_signal) == 0:
        return {lead: np.array([]) for lead in lead_names}, np.array([])

    cleaned = np.nan_to_num(reference_signal, nan=0.0)
    time = np.arange(len(cleaned), dtype=float) / float(fs or 250.0)
    data = {}
    base_std = max(np.std(cleaned), 1e-3)
    for idx, lead in enumerate(lead_names):
        shift = int(idx * len(cleaned) / 20)
        noise = np.random.normal(0, base_std * 0.03, size=cleaned.shape)
        data[lead] = np.roll(cleaned, shift) + noise
    data['time'] = time
    return data, time

# `st.set_page_config()` y `render_sidebar_navigation()` retirados
# (2026-08-20, Capa 2 Fase 2.1, cierre): vestigios de la arquitectura
# Streamlit multipágina anterior. Este archivo solo corre anidado bajo
# `app/main.py` (vía `runpy.run_path()` desde `eeg_neuro_lab/pages.py`), que
# ya configuró la página una sola vez al inicio. Ver CHANGELOG.md.

st.markdown("""
    <style>
        body { background-color: #0f172a; color: #e0e7ff; }
        .stButton>button { background-color: #1d4ed8; color: white; }
        h1, h2, h3, h4 { color: #8ecae6; }
        .metric-card { background-color: #1a2a4a; border-left: 4px solid #8ecae6; padding: 20px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

if Eeg_import_error is not None or EegSignalGenerator is None:
    render_error_state("El módulo de generación/análisis de EEG no se ha podido cargar.", exception=Eeg_import_error)
    st.stop()

st.markdown("# 🧠 EEG Neuro Lab")
st.markdown("*Laboratorio de señales electroencefalográficas y análisis de ondas cerebrales*")

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
    "La opción de hardware en vivo abre un flujo de análisis continuo pensado para dispositivos EEG reales. "
    "Si no hay un equipo físico conectado, la plataforma mantiene la experiencia con una señal de respaldo sintética y un análisis instantáneo. "
    "Cuando el hardware real esté disponible, el sistema podrá recibir datos de muestra en tiempo real, calcular la potencia de banda y actualizar las métricas al vuelo."
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
        "Artifact (parpadeo)"
    ]
)
channels = st.sidebar.selectbox("Número de canales", [2, 3, 4], index=2)

signal_source = st.sidebar.radio(
    "Origen de datos",
    ["Generar EEG sintético", "Cargar EEG desde CSV", "Hardware EEG en vivo"]
)

duration = st.sidebar.slider("Duración (segundos)", min_value=10, max_value=120, value=30, step=10)
fs = st.sidebar.selectbox("Frecuencia de muestreo (Hz)", [128, 256, 512], index=1)
noise = st.sidebar.slider("Nivel de ruido de fondo", min_value=0.0, max_value=0.5, value=0.18, step=0.02)

live_mode = st.sidebar.checkbox(
    "Habilitar análisis en tiempo real",
    value=False,
    help="Actualiza el análisis con cada interacción y permite activar la modalidad de hardware en vivo cuando esté disponible."
)

if live_mode:
    st.sidebar.markdown("### Modo en tiempo real activado")
    st.sidebar.write(
        "El laboratorio está listo para recibir y analizar datos continuamente. "
        "Si hay hardware conectado, se usará el flujo en vivo; de lo contrario, se conserva la simulación en tiempo real."
    )

uploaded_file = None
hardware_source = signal_source == "Hardware EEG en vivo"
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
    st.sidebar.markdown("### Hardware EEG en vivo")
    selected_port = None
    if SensorManager is not None:
        manager = SensorManager()
        port_options = manager.available_ports or ["Auto"]
        selected_port = st.sidebar.selectbox("Puerto serial / Bluetooth", port_options)
        st.sidebar.markdown("**Puertos detectados:**")
        st.sidebar.write(manager.describe_ports())
    else:
        selected_port = st.sidebar.text_input(
            "Puerto serial EEG manual",
            value=st.session_state.get('eeg_esp32_port', ''),
            help="En sistemas sin detección automática, escribe el puerto COM o /dev/ttyUSB0."
        )
        st.sidebar.warning("No se pudo cargar el gestor de hardware. Usa el puerto manual o la simulación de EEG en vivo.")

    esp32_port = st.sidebar.text_input(
        "Puerto ESP32 (opcional)",
        value=st.session_state.get('eeg_esp32_port', ''),
        help="Ej. COM3 o /dev/ttyUSB0. Dejar vacío para detección automática cuando esté disponible."
    )
    esp32_baud = st.sidebar.number_input(
        "Baudios ESP32",
        min_value=9600,
        value=st.session_state.get('eeg_esp32_baud', 115200),
        step=1,
        help="Velocidad de comunicación serial para el hardware ESP32."
    )
    connect_clicked = st.sidebar.button("Conectar hardware EEG", key="connect_eeg_hw")
    disconnect_clicked = st.sidebar.button("Desconectar hardware EEG", key="disconnect_eeg_hw")

    simulate_hardware = st.sidebar.checkbox(
        "Simular si no hay hardware conectado",
        value=True,
        help="Cuando no hay un dispositivo EEG real, se usa un generador sintético para mantener el flujo de análisis en tiempo real."
    )

    hw_source = st.session_state.get('eeg_esp32_source')
    if connect_clicked:
        st.session_state['eeg_esp32_port'] = esp32_port
        st.session_state['eeg_esp32_baud'] = esp32_baud
        if ESP32SignalSource is None:
            st.sidebar.error("ESP32SignalSource no está disponible. Instala pyserial y revisa hardware/esp32_stream.py")
        else:
            chosen_port = esp32_port or (selected_port if selected_port not in (None, "Auto", "No hay puertos detectados") else None)
            try:
                hw_source = ESP32SignalSource(port=chosen_port, baud=esp32_baud, fs=fs)
                connected = hw_source.connect(force_port=chosen_port)
                if connected:
                    hw_source.start()
                    st.session_state['eeg_esp32_source'] = hw_source
                    st.sidebar.success("EEG hardware conectado y listo para transmisión.")
                else:
                    st.sidebar.warning("No se pudo conectar el hardware EEG. Se usará la simulación de respaldo.")
            except Exception as exc:
                st.sidebar.error(f"Error conectando hardware EEG: {exc}")
                hw_source = None

    if disconnect_clicked and 'eeg_esp32_source' in st.session_state:
        try:
            st.session_state['eeg_esp32_source'].stop()
            st.session_state['eeg_esp32_source'].disconnect()
        except Exception:
            pass
        del st.session_state['eeg_esp32_source']
        hw_source = None
        st.sidebar.success("EEG hardware desconectado.")

    if hw_source is not None:
        st.sidebar.info(f"Estado hardware EEG: {hw_source.get_status()}")
        if hasattr(hw_source, 'last_error') and hw_source.last_error:
            st.sidebar.warning(f"Último error EEG: {hw_source.last_error}")
        if live_mode:
            st.sidebar.success("✅ Análisis EEG en vivo habilitado.")
    elif not simulate_hardware:
        st.sidebar.warning("No hay hardware EEG conectado y la simulación está desactivada.")

    if not simulate_hardware and SensorManager is not None and selected_port not in (None, "Auto", "No hay puertos detectados"):
        st.sidebar.info("Modo en vivo activado. Los datos de hardware EEG se integrarán cuando el dispositivo esté disponible.")

st.sidebar.markdown("---")
st.sidebar.markdown("### Configuración Avanzada")

if signal_source == "Generar EEG sintético":
    st.sidebar.markdown("### Síntesis EEG")
    st.sidebar.write("Se generará una señal EEG de laboratorio con el patrón seleccionado.")
elif signal_source == "Hardware EEG en vivo":
    st.sidebar.markdown("### EEG en vivo")
    st.sidebar.write("El análisis intentará usar datos de hardware en tiempo real. Si no hay hardware disponible, se usa una señal de respaldo sintética.")
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
}

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
elif signal_source == "Hardware EEG en vivo":
    data_source = "Hardware en vivo"
    eeg_data = {}
    time = np.array([])
    hw_source = st.session_state.get('eeg_esp32_source')
    use_synthetic = True

    if hw_source is not None and hasattr(hw_source, 'is_connected') and hw_source.is_connected():
        t_hw, signal_hw = hw_source.get_filtered_buffer()
        if len(signal_hw) >= 16 and not np.allclose(signal_hw, 0.0):
            eeg_data, time = expand_hardware_eeg_to_channels(signal_hw, hw_source.fs, channels)
            data_source += f" ({hw_source.port or 'auto'})"
            use_synthetic = False
        else:
            st.warning("Aún no hay suficientes datos reales del hardware EEG. Usando la señal de respaldo sintética.")

    if use_synthetic:
        if not simulate_hardware:
            st.warning("Hardware EEG no disponible y la simulación está desactivada. Se usará la configuración sintética por defecto.")
        data_source += " (simulado)"
        params = EegPattern(
            pattern_type=pattern_map[pattern],
            duration=duration,
            fs=fs,
            amplitude=40.0,
            noise_level=noise,
            channels=channels
        )
        generator = EegSignalGenerator(sampling_rate=fs)
        eeg_data, time = generator.generate_eeg(params)
else:
    params = EegPattern(
        pattern_type=pattern_map[pattern],
        duration=duration,
        fs=fs,
        amplitude=40.0,
        noise_level=noise,
        channels=channels
    )
    generator = EegSignalGenerator(sampling_rate=fs)
    eeg_data, time = generator.generate_eeg(params)

analyzer = EegAnalyzer(fs=fs)

# Main panels
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("## 📈 Señales EEG")
    st.markdown(f"**Fuente de datos:** {data_source}  ")
    if data_source == "CSV cargado":
        st.markdown(f"**Frecuencia de muestreo estimada:** {fs:.2f} Hz")

    lead_names = [k for k in eeg_data.keys() if k != 'time']
    display_leads = lead_names[:channels] if signal_source == "Cargar EEG desde CSV" else lead_names
    display_rows = max(len(display_leads), 1)

    if len(display_leads) == 0:
        st.warning("No hay datos EEG válidos. Cargue un archivo CSV o genere una señal sintética.")
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
            st.write(result.summary)
            band_table = {
                'Delta': f"{result.band_power['delta']:.2f}",
                'Theta': f"{result.band_power['theta']:.2f}",
                'Alpha': f"{result.band_power['alpha']:.2f}",
                'Beta': f"{result.band_power['beta']:.2f}",
                'Gamma': f"{result.band_power['gamma']:.2f}",
            }
            st.write(band_table)

with col2:
    st.markdown("## 📊 Métricas y Clasificación")
    overall = analysis_cards[0][1] if analysis_cards else None
    if overall is not None:
        st.metric("Banda dominante", overall.dominant_band.upper())
        st.metric("Clasificación", overall.classification)
        st.markdown("### Interpretación Clínica")
        st.write(
            "Este laboratorio simula ondas EEG típicas y las clasifica en patrones de alerta, relajación y sueño."
        )
        st.markdown("### Hallazgos clínicos EEG")
        for key, value in overall.findings.items():
            st.write(f"**{key}:** {value}")

        if export_lab_report is not None and st.button("Exportar informe EEG"):
            metrics = {
                'data_source': data_source,
                'fs': fs,
                'dominant_band': overall.dominant_band,
                'classification': overall.classification,
            }
            for bname, val in overall.band_power.items():
                metrics[f'band_{bname}'] = float(val)
            notes = f"EEG Neuro Lab autogenerated report. {overall.findings.get('Clinical Note', '')}"
            findings = overall.findings
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
                path = export_lab_report('EEG Neuro Lab', metrics, notes=notes, findings=findings, image_paths=image_paths)
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
        # recalcular nada). Con solo band power como entrada,
        # `_update_brain()` (`digital_twin_organism.py`) calcula
        # health_score/risk_score/detail desde `stress_level`/
        # `relaxation_level` DEFAULTEADOS (35/65 -- este lab no mide
        # ninguno de los dos) -- mismo nivel de tolerancia que ya acepta
        # `_cardiovascular_state()` (que tampoco exige que `hrv`/
        # `complexity` sean reales para escribir su health_score, solo que
        # `heart_rate` lo sea). El gate de `_neurological_state()`
        # (`alpha_power`/`beta_power` presentes) es lo que decide "hay
        # cerebro que escribir", no cada sub-entrada de la fórmula.
        #
        # Procedencia: `Provenance.SIMULACION` -- señal generada por
        # `EegSignalGenerator` (o CSV cargado, tampoco un sensor en vivo
        # verificado), nunca un sensor real.
        st.markdown("---")
        st.markdown("#### 🔗 Guardar estado al gemelo")
        eeg_lab_channel = analysis_cards[0][0]
        st.caption(
            f"Escribe la potencia de banda real (delta/theta/alpha/beta/gamma) del canal "
            f"**{eeg_lab_channel}** al Unified Physiological State, bajo el mismo paciente que "
            "renderiza Digital Twin OS -- su cerebro reaccionará a estos valores la próxima vez "
            "que abras esa página o pulses \"Guardar este momento\" ahí. Procedencia: simulación "
            "(señal generada, no un sensor real)."
        )
        if st.button("💾 Guardar estado al gemelo", key="eeg_lab_save_to_ups"):
            session_factory = get_active_session_factory()
            patient_id = get_active_patient_id()

            eeg_organism = DigitalTwinOrganism()
            eeg_organism.update_from_sensors({
                "eeg": {
                    "delta_power": float(overall.band_power["delta"]),
                    "theta_power": float(overall.band_power["theta"]),
                    "alpha_power": float(overall.band_power["alpha"]),
                    "beta_power": float(overall.band_power["beta"]),
                    "gamma_power": float(overall.band_power["gamma"]),
                }
            })
            eeg_ups_state = from_digital_twin_organism(
                eeg_organism, patient_id, provenance=Provenance.SIMULACION,
                source_detail=f"eeg_neuro_lab:canal={eeg_lab_channel}:banda_dominante={overall.dominant_band}",
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
            if bar_desc is not None:
                bar_txt = f"BAR = {bar_desc.value:.2f}" + (" ⚠️ >1.8 arousal" if bar_desc.value > 1.8 else "")
            else:
                bar_txt = "BAR indefinido (sin ritmo alfa)"
            st.caption(
                f"neurological: {len(eeg_ups_state.neurological.descriptors)} descriptores · {bar_txt}"
            )
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
    st.write("**Banda Delta:** sueño profundo, 0.5-4 Hz")
    st.write("**Banda Theta:** somnolencia, 4-8 Hz")
    st.write("**Banda Alpha:** relajación con ojos cerrados, 8-12 Hz")
    st.write("**Banda Beta:** alerta y concentración, 13-30 Hz")
    st.write("**Banda Gamma:** procesamiento cognitivo integrado, 30-45 Hz")

    with st.expander("🧪 Quiz interactivo EEG"):
        quiz_questions = [
            {
                "question": "¿Qué banda EEG se asocia con sueño profundo?",
                "options": ["Alpha", "Beta", "Theta", "Delta"],
                "answer": "Delta",
                "explanation": "Delta es la banda más lenta y se observa en sueño profundo."
            },
            {
                "question": "¿Qué banda es típica en un estado de concentración y alerta?",
                "options": ["Alpha", "Beta", "Theta", "Delta"],
                "answer": "Beta",
                "explanation": "Beta aumenta durante la atención activa y la cognición."
            },
            {
                "question": "¿Cuál es la banda predominante en relajación con los ojos cerrados?",
                "options": ["Alpha", "Beta", "Theta", "Gamma"],
                "answer": "Alpha",
                "explanation": "Alpha es común con ojos cerrados y estados relajados."
            },
            {
                "question": "¿Qué patrón EEG puede corresponder a una crisis epiléptica simulada?",
                "options": ["Alpha", "Sleep Spindle", "Seizure", "Artifact"],
                "answer": "Seizure",
                "explanation": "Las espigas de alto voltaje y frecuencia son típicas de crisis."
            },
            {
                "question": "¿Qué banda se relaciona con somnolencia ligera y transición al sueño?",
                "options": ["Alpha", "Beta", "Theta", "Delta"],
                "answer": "Theta",
                "explanation": "Theta se observa en somnolencia y sueño ligero."
            }
        ]

        user_answers = []
        for idx, item in enumerate(quiz_questions, start=1):
            user_answers.append(st.radio(item["question"], item["options"], key=f"quiz_{idx}"))

        if st.button("Calcular puntuación", key="submit_eeg_quiz"):
            score = sum(1 for answer, item in zip(user_answers, quiz_questions) if answer == item["answer"])
            st.success(f"Has respondido {score} de {len(quiz_questions)} correctamente.")
            for item, answer in zip(quiz_questions, user_answers):
                correct = item["answer"]
                st.write(f"**Pregunta:** {item['question']}")
                st.write(f"- Tu respuesta: {answer}")
                st.write(f"- Correcta: {correct}")
                st.write(f"- Explicación: {item['explanation']}")
                st.write("---")

st.markdown("---")
st.markdown("*Fase 3: EEG Neuro Lab - inicio del laboratorio de electroencefalografía clínica educativa en español.*")
