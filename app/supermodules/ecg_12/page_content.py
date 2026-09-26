import streamlit as st
import numpy as np
try:
    from scipy.signal import butter, filtfilt
except ImportError:
    butter = None
    filtfilt = None
import sys
import os
import io
from typing import Dict, List
# Rutas ajustadas (Tanda de eliminación de pages_legacy, Movimiento 1, 2026-07-13):
# este archivo vivía en app/pages_legacy/ (2 niveles bajo la raíz del repo) y ahora
# vive en app/supermodules/ecg_12/ (3 niveles) — un nivel más de profundidad, así
# que el cálculo de la raíz del repo necesita un salto más. Nada más cambió.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.signals.ecg.twelve_lead_generator import TwelveLeadEcgGenerator, EcgParameters, generate_12lead_example
from src.signals.ecg.twelve_lead_analyzer import TwelveLeadEcgAnalyzer, create_clinical_summary
from src.signals.ecg.advanced_patterns import AdvancedEcgPatterns

# Consolidación Visual Tanda 3 (2026-09-21): `PALETTE`/`BADGES`/
# `render_metric_card` -- fuente única de color y de tarjeta de métrica
# (`app/utils/design_system.py`), reemplaza el `<style>` propio de este
# archivo (retirado más abajo) y los hex sueltos de `.warning-box`/
# `.normal-box` (`#dc2626`/`#059669`, que ni siquiera coincidían con
# `PALETTE.CRITICAL`/`PALETTE.STABLE`).
from app.utils.design_system import BADGES, PALETTE, render_metric_card


def load_ecg_csv_file(uploaded_file) -> Dict[str, np.ndarray]:
    """Load ECG leads from a CSV file and normalize to 12-lead format."""
    raw = uploaded_file.getvalue().decode('utf-8', errors='replace')
    text = io.StringIO(raw)
    lines = raw.strip().splitlines()

    if len(lines) == 0:
        return {}

    header = lines[0].split(',')
    has_header = any(not item.replace('.', '', 1).replace('-', '', 1).isdigit() for item in header)

    try:
        if has_header:
            data = np.genfromtxt(text, delimiter=',', names=True, dtype=float, invalid_raise=False)
        else:
            text.seek(0)
            data = np.genfromtxt(text, delimiter=',', dtype=float)
    except Exception:
        return {}

    lead_names = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
    result: Dict[str, np.ndarray] = {}
    time = None

    if hasattr(data, 'dtype') and data.dtype.names is not None:
        names = list(data.dtype.names)
        if 'time' in names:
            time = data['time']
        elif len(names) > 12 and names[0].lower() in ['time', 't', 'timestamp']:
            time = data[names[0]]
        else:
            time = np.arange(len(data[names[0]])) / 500.0

        for lead in lead_names:
            if lead in names:
                result[lead] = np.asarray(data[lead], dtype=float)

        if len(result) == 0 and data.ndim == 1:
            result['II'] = np.asarray(data, dtype=float)
    elif isinstance(data, np.ndarray):
        if data.ndim == 1:
            result['II'] = data
            time = np.arange(len(data)) / 500.0
        elif data.ndim == 2:
            if data.shape[1] >= 13:
                time = data[:, 0]
                values = data[:, 1:13]
            elif data.shape[1] >= 12:
                time = np.arange(data.shape[0]) / 500.0
                values = data[:, :12]
            else:
                values = data
                time = np.arange(data.shape[0]) / 500.0

            for i, lead in enumerate(lead_names[: values.shape[1]]):
                result[lead] = values[:, i]

    if time is None:
        time = np.arange(len(next(iter(result.values())))) / 500.0 if len(result) else np.array([])

    result['time'] = time
    return result


def bandpass_filter_signal(signal: np.ndarray, fs: float, lowcut: float = 0.5, highcut: float = 40.0, order: int = 2) -> np.ndarray:
    if len(signal) < 10 or butter is None or filtfilt is None:
        return signal
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    try:
        return filtfilt(b, a, signal)
    except Exception:
        return signal


def simulate_device_capture(condition_short: str) -> Dict[str, np.ndarray]:
    """Simulate device acquisition and return a full 12-lead record."""
    if condition_short in ['af', 'flutter', 'wpw', 'long_qt']:
        if condition_short == 'af':
            signal, time = AdvancedEcgPatterns.generate_atrial_fibrillation(duration=10.0, sampling_rate=500, ventricular_rate=110)
        elif condition_short == 'flutter':
            signal, time = AdvancedEcgPatterns.generate_atrial_flutter(duration=10.0, sampling_rate=500, flutter_rate=300, ventricular_rate=150)
        elif condition_short == 'wpw':
            signal, time = AdvancedEcgPatterns.generate_wpw_pattern(duration=10.0, sampling_rate=500)
        else:
            signal, time = AdvancedEcgPatterns.generate_long_qt_pattern(duration=10.0, sampling_rate=500, qt_prolongation=1.7)

        return {
            'I': signal * 0.8,
            'II': signal,
            'III': signal * 0.9,
            'aVR': -signal,
            'aVL': signal * 0.7,
            'aVF': signal * 0.85,
            'V1': signal * 0.6,
            'V2': signal * 0.65,
            'V3': signal * 0.7,
            'V4': signal * 0.75,
            'V5': signal * 0.8,
            'V6': signal * 0.85,
            'time': time
        }
    else:
        generator = TwelveLeadEcgGenerator(sampling_rate=500)
        ecg_params = EcgParameters(
            heart_rate=75,
            p_amplitude=0.15,
            qrs_duration=0.08,
            st_segment=0.0,
            anterior_mi='anterior' in condition_short,
            inferior_mi='inferior' in condition_short,
            lateral_mi='lateral' in condition_short,
            rbbb_pattern='rbbb' in condition_short,
            lbbb_pattern='lbbb' in condition_short,
            lvh_pattern='lvh' in condition_short,
        )
        return generator.generate_ecg(duration=10.0, params=ecg_params)

# `st.set_page_config()` y `render_sidebar_navigation()` retirados
# (2026-08-20, Capa 2 Fase 2.1, cierre): vestigios de la arquitectura
# Streamlit multipágina anterior. Este archivo solo corre anidado bajo
# `app/main.py` (vía `runpy.run_path()` desde `ecg_12/pages.py`), que ya
# configuró la página una sola vez al inicio -- una segunda llamada aquí
# era redundante. Confirmado por grep/inventario de scripts de lanzamiento
# (`RUN_BIOCORE.bat`/`run_local.ps1`) que nada ejecuta este archivo standalone.
# Ver CHANGELOG.md.

# Consolidación Visual Tanda 3 (2026-09-21): `<style>` propio retirado --
# `inject_global_theme()` (`app/main.py`) ya cubre fondo/texto globales con
# los mismos tokens (`PALETTE.BACKGROUND`/`PALETTE.ACCENT_ON_DARK`);
# `.metric-card` no se usaba en ningún `<div>` de este archivo (CSS
# muerto), y `.warning-box`/`.normal-box` usaban hex propios
# (`#dc2626`/`#059669`) que ni siquiera coincidían con
# `PALETTE.CRITICAL`/`PALETTE.STABLE` -- las dos únicas aplicaciones reales
# de esas clases (el banner de diagnóstico principal, más abajo) ahora
# construyen su color inline desde `PALETTE` directamente. Ver CHANGELOG.md.
st.caption(
    "Elige un escenario clínico y genera el ECG de 12 derivaciones al instante — el análisis "
    "automático (eje QRS, ST, bloqueos, arritmias) se ejecuta apenas se genera la señal."
)

st.markdown(
    "##### 🎓 ¿Qué es un ECG de 12 derivaciones?\n"
    "Registra la actividad eléctrica del corazón desde **12 ángulos distintos**: "
    "**I, II, III** (miembros) · **aVR, aVL, aVF** (aumentadas) · **V1-V6** (precordiales, del "
    "lado derecho V1 al izquierdo V6 del corazón). Cada una lo mira desde un ángulo distinto, así "
    "que combinarlas permite **localizar** un problema, no solo detectarlo: una elevación ST en "
    "V1-V4 apunta a la arteria descendente anterior (territorio anterior); en II, III y aVF, a la "
    "coronaria derecha (territorio inferior)."
)

# Two column layout
col1, col2 = st.columns([2, 1])

with col1:
    condition = st.selectbox(
        "🩺 Escenario clínico",
        [
            "Normal - Ritmo sinusal normal",
            "Taquicardia sinusal - HR > 100 bpm",
            "Bradicardia sinusal - HR < 60 bpm",
            "🔴 STEMI Anterior - Infarto anterior (LAD)",
            "🔴 STEMI Inferior - Infarto inferior (RCA)",
            "🔴 STEMI Lateral - Infarto lateral (LCx)",
            "Bloqueo de rama derecha (RBBB)",
            "Bloqueo de rama izquierda (LBBB)",
            "Hipertrofia ventricular izquierda (LVH)",
            "💓 Fibrilación Auricular - Ritmo irregularmente irregular",
            "💓 Flutter Auricular - Ondas flutter regulares",
            "⚡ Síndrome WPW - Vía accesoria (PR corto, delta wave)",
            "⚠️ Síndrome QT largo - QT prolongado, riesgo de torsadas",
        ],
    )

    condition_map = {
        "Normal - Ritmo sinusal normal": "normal",
        "Taquicardia sinusal - HR > 100 bpm": "tachycardia",
        "Bradicardia sinusal - HR < 60 bpm": "bradycardia",
        "🔴 STEMI Anterior - Infarto anterior (LAD)": "anterior_stemi",
        "🔴 STEMI Inferior - Infarto inferior (RCA)": "inferior_stemi",
        "🔴 STEMI Lateral - Infarto lateral (LCx)": "lateral_stemi",
        "Bloqueo de rama derecha (RBBB)": "rbbb",
        "Bloqueo de rama izquierda (LBBB)": "lbbb",
        "Hipertrofia ventricular izquierda (LVH)": "lvh",
        "💓 Fibrilación Auricular - Ritmo irregularmente irregular": "af",
        "💓 Flutter Auricular - Ondas flutter regulares": "flutter",
        "⚡ Síndrome WPW - Vía accesoria (PR corto, delta wave)": "wpw",
        "⚠️ Síndrome QT largo - QT prolongado, riesgo de torsadas": "long_qt",
    }

    signal_source = "Generar señal sintética"
    heart_rate, p_amplitude, qrs_duration, st_elevation = 75, 0.15, 80, 0.0
    apply_filter = True
    uploaded_ecg = None

    with st.expander("⚙️ Parámetros avanzados y origen de la señal", expanded=False):
        col_cfg1, col_cfg2 = st.columns(2)

        with col_cfg1:
            # Key explícita (Fusión ECG Lab, 2026-07-14): near-miss con el
            # slider de FC de render_ecg_monitor_page (mismo tema, difieren
            # solo en mayúscula) — ver docstring de render_ecg_lab_page().
            heart_rate = st.slider(
                "Frecuencia Cardíaca (bpm)",
                min_value=30, max_value=200, value=75,
                help="Rango normal: 60-100 bpm",
                key="ecglab_12_hr_slider",
            )

        with col_cfg2:
            p_amplitude = st.slider(
                "Amplitud onda P (mV)",
                min_value=0.05, max_value=0.30, value=0.15, step=0.05
            )

            # Key explícita (Fusión ECG Lab, 2026-07-14): near-miss con el
            # slider "QRS (ms)" de render_ecg_monitor_page — ver docstring
            # de render_ecg_lab_page().
            qrs_duration = st.slider(
                "Duración QRS (ms)",
                min_value=60, max_value=180, value=80, step=10,
                help="Normal: 60-120 ms",
                key="ecglab_12_qrs_duration_slider",
            )

            st_elevation = st.slider(
                "Elevación ST (mV)",
                min_value=-0.5, max_value=0.5, value=0.0, step=0.05,
                help="Positivo: elevación ST (STEMI)\nNegativo: depresión ST"
            )

        signal_source = st.radio(
            "Origen de la señal:",
            [
                "Generar señal sintética",
                "Cargar ECG desde archivo CSV",
                "Simular captura de dispositivo"
            ],
            index=0
        )

        if 'last_signal_source' not in st.session_state or st.session_state.last_signal_source != signal_source:
            st.session_state.generate_ecg = False
            st.session_state.last_signal_source = signal_source

        apply_filter = st.checkbox(
            "Aplicar filtro banda (0.5-40 Hz)",
            value=True,
            help="Activa un filtro bandpass para limpiar el ECG antes de mostrar el 12-lead.",
        )

        uploaded_ecg = None
        if signal_source == "Cargar ECG desde archivo CSV":
            uploaded_ecg = st.file_uploader(
                "Cargar archivo ECG (.csv con 12 derivaciones o una sola señal)",
                type=['csv'],
                help="Si su dispositivo exporta CSV, cargue el archivo para análisis automático."
            )
            if uploaded_ecg is not None:
                st.session_state.generate_ecg = True

        if signal_source == "Simular captura de dispositivo":
            st.session_state.generate_ecg = True
            st.info("Se simulará una captura tipo dispositivo y se aplicarán todas las inferencias AI y métricas clínicas automáticamente.")
        elif signal_source == "Cargar ECG desde archivo CSV":
            st.info("Cuando cargue un archivo, el sistema extraerá las derivaciones disponibles y ejecutará el análisis automático de inmediato.")

        st.caption(
            "**Derivaciones:** I, II, III (estándar) · aVR, aVL, aVF (aumentadas) · "
            "V1-V6 (precordiales, septal → lateral)"
        )

    if st.button("🔄 Generar ECG de 12 derivaciones", type="primary", use_container_width=True):
        st.session_state.generate_ecg = True

# Generate and display ECG
if "generate_ecg" not in st.session_state:
    st.session_state.generate_ecg = False

if st.session_state.generate_ecg or "ecg_data" not in st.session_state:
    condition_short = condition_map.get(condition, "normal")
    ecg_data = {}

    if signal_source == "Cargar ECG desde archivo CSV" and uploaded_ecg is not None:
        ecg_data = load_ecg_csv_file(uploaded_ecg)
        if len(ecg_data) > 0:
            if 'II' in ecg_data and 'I' not in ecg_data:
                base = ecg_data['II']
                time = ecg_data.get('time', np.arange(len(base)) / 500.0)
                ecg_data = {
                    'I': base * 0.8,
                    'II': base,
                    'III': base * 0.9,
                    'aVR': -base,
                    'aVL': base * 0.7,
                    'aVF': base * 0.85,
                    'V1': base * 0.6,
                    'V2': base * 0.65,
                    'V3': base * 0.7,
                    'V4': base * 0.75,
                    'V5': base * 0.8,
                    'V6': base * 0.85,
                    'time': time
                }
            elif 'time' not in ecg_data:
                first_lead = next((lead for lead in ['I', 'II', 'III', 'V1'] if lead in ecg_data), None)
                length = len(ecg_data[first_lead]) if first_lead else 0
                ecg_data['time'] = np.arange(length) / 500.0

    if signal_source == "Simular captura de dispositivo" and len(ecg_data) == 0:
        ecg_data = simulate_device_capture(condition_short)

    if signal_source == "Generar señal sintética" or len(ecg_data) == 0:
        if condition_short in ["af", "flutter", "wpw", "long_qt"]:
            from src.signals.ecg.advanced_patterns import AdvancedEcgPatterns

            if condition_short == "af":
                signal, time = AdvancedEcgPatterns.generate_atrial_fibrillation(
                    duration=10.0, sampling_rate=500, ventricular_rate=110
                )
            elif condition_short == "flutter":
                signal, time = AdvancedEcgPatterns.generate_atrial_flutter(
                    duration=10.0, sampling_rate=500, flutter_rate=300, ventricular_rate=150
                )
            elif condition_short == "wpw":
                signal, time = AdvancedEcgPatterns.generate_wpw_pattern(
                    duration=10.0, sampling_rate=500
                )
            else:  # long_qt
                signal, time = AdvancedEcgPatterns.generate_long_qt_pattern(
                    duration=10.0, sampling_rate=500, qt_prolongation=1.7
                )

            ecg_data = {
                'I': signal * 0.8,
                'II': signal,
                'III': signal * 0.9,
                'aVR': -signal,
                'aVL': signal * 0.7,
                'aVF': signal * 0.85,
                'V1': signal * 0.6,
                'V2': signal * 0.65,
                'V3': signal * 0.7,
                'V4': signal * 0.75,
                'V5': signal * 0.8,
                'V6': signal * 0.85,
                'time': time
            }
        else:
            generator = TwelveLeadEcgGenerator(sampling_rate=500)
            ecg_params = EcgParameters(
                heart_rate=heart_rate,
                p_amplitude=p_amplitude,
                qrs_duration=qrs_duration/1000,  # Convert ms to seconds
                st_segment=st_elevation,
                anterior_mi="anterior" in condition_short,
                inferior_mi="inferior" in condition_short,
                lateral_mi="lateral" in condition_short,
                rbbb_pattern="rbbb" in condition_short,
                lbbb_pattern="lbbb" in condition_short,
                lvh_pattern="lvh" in condition_short,
            )
            ecg_data = generator.generate_ecg(duration=10.0, params=ecg_params)

    st.session_state.ecg_data = ecg_data
    st.session_state.condition = condition_short
    st.session_state.heart_rate = heart_rate
    st.session_state.signal_source = signal_source

# Display ECG if generated
if "ecg_data" in st.session_state:
    ecg_data = st.session_state.ecg_data
    time = ecg_data['time']

    # clinical.ecg12.plot_ecg_12_leads renders the standard clinical layout
    # (3x4 sequential leads + rhythm strip on real ECG-paper grid) and
    # already falls back to Matplotlib internally if Plotly is unavailable.
    from clinical.ecg12 import plot_ecg_12_leads

    leads = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
    signals = {lead: ecg_data.get(lead, np.zeros_like(time)) for lead in leads}
    if 'apply_filter' in locals() and apply_filter:
        signals = {lead: bandpass_filter_signal(signal, 500) for lead, signal in signals.items()}

    fig2 = plot_ecg_12_leads(signals, fs=500, title='ECG de 12 Derivaciones')
    if hasattr(fig2, 'to_dict'):
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.pyplot(fig2)

    # Analysis section
    st.markdown("---")
    st.markdown("## 📋 Interpretación Clínica Automática")

    if 'signal_source' in st.session_state:
        st.markdown(f"*Origen de la señal: {st.session_state.signal_source}*")

    analyzer = TwelveLeadEcgAnalyzer()
    interpretation = analyzer.analyze_12lead(ecg_data)

    # Narrative summary built directly from the analyzer's own computed
    # fields (axis degrees, rhythm, ST findings) — no invented text, just a
    # readable sentence stitched from the same data shown in detail below.
    st_summary = (
        f", con {len(interpretation.st_findings)} derivación(es) mostrando cambios del segmento ST"
        if interpretation.st_findings else ", sin cambios significativos del segmento ST"
    )
    block_summary = (
        f" y {len(interpretation.conduction_blocks)} bloqueo(s) de conducción detectado(s)"
        if interpretation.conduction_blocks else ""
    )
    st.markdown(
        f"> **{interpretation.rhythm}**, eje QRS de **{interpretation.qrs_axis.axis_degrees:.0f}°** "
        f"({interpretation.qrs_axis.category}){st_summary}{block_summary}. "
        f"{interpretation.clinical_significance}"
    )

    # Display clinical summary
    col_analysis1, col_analysis2 = st.columns([1.5, 1])

    with col_analysis1:
        # Primary findings
        st.markdown("### 🎯 Hallazgos Principales")

        # Diagnostic result -- Consolidación Visual Tanda 3 (2026-09-21):
        # `.warning-box`/`.normal-box` (hex propios `#dc2626`/`#059669`,
        # retirados con el `<style>` de arriba) -> mismo banner, color
        # inline desde `PALETTE.CRITICAL`/`PALETTE.STABLE` directamente.
        # NO se enruta por `render_metric_card`: `primary_diagnosis` es
        # texto de diagnóstico libre de `TwelveLeadEcgAnalyzer` (sin un
        # `classify_*()` de 3 niveles que lo respalde), y forzarlo por la
        # tarjeta de métrica sin `classification=` habría aplanado el color
        # a NEUTRAL siempre -- una regresión visual real (perder la
        # distinción crítico/normal), no solo un re-skin. Ver CHANGELOG.md.
        if "INFARCTION" in interpretation.primary_diagnosis:
            st.markdown(
                f'<div style="background:{PALETTE.CRITICAL}; padding:15px; border-radius:8px; color:white;">'
                f'🔴 CRÍTICO: {interpretation.primary_diagnosis}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="background:{PALETTE.STABLE}; padding:15px; border-radius:8px; color:white;">'
                f'✅ {interpretation.primary_diagnosis}</div>',
                unsafe_allow_html=True,
            )

        # QRS Axis
        st.markdown(f"**Eje QRS:** {interpretation.qrs_axis.description}")

        # Rhythm
        st.markdown(f"**Ritmo:** {interpretation.rhythm}")

        # ST Findings
        if interpretation.st_findings:
            st.markdown("**Elevaciones/Depresiones ST:**")
            for f in interpretation.st_findings:
                st.write(f"  • {f.lead}: {f.elevation_mv:+.2f} mV ({f.location})")

        # Conduction blocks
        if interpretation.conduction_blocks:
            st.markdown("**Bloqueos de Conducción:**")
            for b in interpretation.conduction_blocks:
                st.write(f"  • {b.block_type}: {b.description}")

        # Wave abnormalities
        if interpretation.wave_abnormalities:
            st.markdown("**Anomalías de Ondas:**")
            for w in interpretation.wave_abnormalities:
                st.write(f"  • {w.wave_type} wave in {', '.join(w.leads_affected)}: {w.abnormality}")

    with col_analysis2:
        st.markdown("### 📋 Recomendaciones Clínicas")

        # Clinical significance
        st.info(interpretation.clinical_significance)

        # Recommendations
        st.markdown("**Acciones Recomendadas:**")
        for rec in interpretation.recommendations[:3]:
            st.write(f"  {rec}")

        if len(interpretation.recommendations) > 3:
            with st.expander("Ver más recomendaciones"):
                for rec in interpretation.recommendations[3:]:
                    st.write(f"  {rec}")

    st.markdown("---")

    # Educational quiz
    st.markdown("## 🎓 Desafío Educativo")

    ECG_QUIZ_BANK: List[Dict[str, str]] = [
        {
            'question': '¿Cuál es la derivación que normalmente muestra mayor amplitud de R en un ECG estándar?',
            'options': ['V1', 'V2', 'V4', 'V6'],
            'correct': 'V4',
            'explanation': 'En la zona de transición, V4 suele mostrar R máxima en ECG normal.'
        },
        {
            'question': 'Elevación ST en V1-V4 sugiere infarto en territorio de:',
            'options': ['RCA', 'LAD', 'LCx', 'Posterior'],
            'correct': 'LAD',
            'explanation': 'V1-V4 corresponde a la porción anterior del ventrículo izquierdo.'
        },
        {
            'question': 'Un eje QRS de -45° se clasifica como:',
            'options': ['Normal', 'LAD', 'RAD', 'Indeterminado'],
            'correct': 'LAD',
            'explanation': 'Un eje entre -30° y -90° indica desviación izquierda.'
        },
        {
            'question': '¿Qué patrón es característico de RBBB?',
            'options': ['RSR’ en V1-V2', 'QS en V1', 'Delta wave', 'QT prolongado'],
            'correct': 'RSR’ en V1-V2',
            'explanation': 'RBBB muestra patrón RSR’ en las derivaciones precordiales derechas.'
        },
        {
            'question': 'Una onda delta y PR corto son signos de:',
            'options': ['AF', 'Flutter', 'WPW', 'LBBB'],
            'correct': 'WPW',
            'explanation': 'El síndrome de Wolff-Parkinson-White se caracteriza por delta wave y PR corto.'
        },
        {
            'question': 'Ausencia de ondas P y ritmo irregular indican:',
            'options': ['AF', 'Flutter', 'VT', 'QB'],
            'correct': 'AF',
            'explanation': 'La fibrilación auricular presenta ritmo irregularmente irregular sin P reconocible.'
        },
        {
            'question': 'Un QT corregido > 500 ms sugiere riesgo de:',
            'options': ['Bloqueo AV', 'Taquicardia ventricular polimórfica', 'Infarto inferior', 'Pericarditis'],
            'correct': 'Taquicardia ventricular polimórfica',
            'explanation': 'QT largo incrementa el riesgo de torsades de pointes.'
        },
        {
            'question': 'Territorio lateral incluye estas derivaciones:',
            'options': ['II, III, aVF', 'V1-V2', 'I, aVL, V5-V6', 'V3-V4'],
            'correct': 'I, aVL, V5-V6',
            'explanation': 'Las derivaciones laterales son I, aVL y V5-V6.'
        },
        {
            'question': '¿Cuál es el rango normal del PR?',
            'options': ['80-120 ms', '120-200 ms', '200-300 ms', '300-400 ms'],
            'correct': '120-200 ms',
            'explanation': 'El intervalo PR normal es 120-200 ms.'
        },
        {
            'question': 'La desviación derecha del eje se define en:',
            'options': ['-30° a +90°', '+90° a +180°', '-90° a -30°', '+180° a -180°'],
            'correct': '+90° a +180°',
            'explanation': 'RAD se encuentra entre +90° y +180°.'
        },
        {
            'question': 'Patrón de ST depresivo difuso con PR elevado sugiere:',
            'options': ['Pericarditis', 'Infarto anterior', 'WPW', 'LBBB'],
            'correct': 'Pericarditis',
            'explanation': 'Pericarditis aguda suele mostrar ST elevado difuso y PR deprimido.'
        },
        {
            'question': 'Una señal de ECG cargada desde dispositivo con solo derivación II puede:',
            'options': ['permitir análisis completo de todas las derivaciones', 'generar inferencias usando derivadas sintéticas', 'no servir para diagnóstico', 'ser útil solo para frecuencia'],
            'correct': 'generar inferencias usando derivadas sintéticas',
            'explanation': 'Se puede crear una representación 12-lead sintética a partir de una derivación de referencia.'
        },
        {
            'question': 'El parámetro QRS > 120 ms en V1-V6 sugiere:',
            'options': ['Bloqueo de rama', 'AF', 'Hipertrofia ventricular', 'Bradicardia'],
            'correct': 'Bloqueo de rama',
            'explanation': 'QRS ancho es característico de bloqueos de rama y aberrancia ventricular.'
        },
        {
            'question': 'En un ECG de dispositivo real, ¿qué valor de SNR es preferible?',
            'options': ['Mayor a 10', 'Menor a 1', 'Entre 0.1 y 0.5', 'Cero'],
            'correct': 'Mayor a 10',
            'explanation': 'Un SNR alto indica señal limpia para análisis clínico.'
        },
        {
            'question': '¿Qué representa el segmento ST?',
            'options': ['Tiempo entre QRS y comienzo de T', 'Duración de la onda P', 'Intervalo RR', 'Longitud de QRS'],
            'correct': 'Tiempo entre QRS y comienzo de T',
            'explanation': 'El segmento ST es el periodo isoeléctrico entre QRS y T.'
        },
        {
            'question': '¿Cuál es la utilidad de las inferencias IA en ECG 12-lead?',
            'options': ['Detectar patrones clínicos y recomendaciones', 'Sustituir completamente al médico', 'Reducir la frecuencia cardiaca', 'Medir la SpO2'],
            'correct': 'Detectar patrones clínicos y recomendaciones',
            'explanation': 'La IA ayuda a identificar diagnósticos y hallazgos, no a reemplazar la evaluación clínica.'
        },
        {
            'question': 'En un ECG normal, la onda T debe ser:',
            'options': ['Positiva en V5-V6', 'Negativa en V5-V6', 'Ausente', 'Delta'],
            'correct': 'Positiva en V5-V6',
            'explanation': 'La onda T suele ser positiva en las derivaciones laterales normales.'
        },
        {
            'question': 'Un pseudo-infarcto por LVH se identifica por:',
            'options': ['QRS alto con ST negativo en V5-V6', 'Delta wave', 'QT corto', 'RBBB'],
            'correct': 'QRS alto con ST negativo en V5-V6',
            'explanation': 'LVH puede causar altos voltajes y cambios secundarios de ST/T.'
        },
        {
            'question': 'La detección automática de arritmias en esta página incluye:',
            'options': ['AF, Flutter, WPW, Long QT', 'Solo bradicardia', 'Solo infartos', 'Solo hipertrofia'],
            'correct': 'AF, Flutter, WPW, Long QT',
            'explanation': 'El laboratorio incluye patrones avanzados y análisis IA para estas arritmias.'
        }
    ]

    question_index = st.selectbox(
        "Selecciona la pregunta:",
        list(range(1, len(ECG_QUIZ_BANK) + 1)),
        format_func=lambda x: f"Pregunta {x}"
    )
    current_question = ECG_QUIZ_BANK[question_index - 1]

    st.write(f"**Pregunta {question_index}:** {current_question['question']}")
    selected_answer = st.radio("Respuesta:", current_question['options'], key=f"quiz_{question_index}")

    if st.button("Verificar respuesta", key="verify_quiz"):
        if selected_answer == current_question['correct']:
            st.success(f"✅ Correcto! {current_question['explanation']}")
        else:
            st.error(f"❌ Incorrecto. {current_question['explanation']}")

with col2:
    st.markdown("## 📊 Métricas")

    if "heart_rate" in st.session_state:
        # Consolidación Visual Tanda 3 (2026-09-21): `st.metric` crudo ->
        # `render_metric_card`. `heart_rate` es el parámetro de generación
        # elegido por el usuario (slider), no una medición sobre la señal
        # -- `BADGES.HEURISTIC` (no hay `*_CITATION` que lo respalde; sin
        # `classification=`, no se fabrica un semáforo de 3 niveles).
        render_metric_card(
            "FC (bpm)", f"{st.session_state.heart_rate}",
            provenance=BADGES.HEURISTIC,
        )

    if "ecg_data" in st.session_state:
        analysis = st.session_state.ecg_data

        # Lead quality metrics -- Consolidación Visual Tanda 3 (2026-09-21):
        # `st.write` con SNR calculado en línea -> `render_metric_card`.
        # SNR = max(|señal|)/std(señal), cálculo real sin cita clínica --
        # `BADGES.HEURISTIC`.
        st.markdown("### 📡 Calidad de Señal")
        for lead in ['I', 'II', 'V1', 'V4']:
            signal = analysis.get(lead, np.zeros(1))
            snr = np.max(np.abs(signal)) / (np.std(signal) + 1e-6)
            render_metric_card(
                f"{lead} SNR", f"{snr:.1f}",
                provenance=BADGES.HEURISTIC,
            )

    st.markdown("---")

    st.markdown("### 📚 Información Clínica")

    st.info("""
    **Referencia Normal (Adulto):**
    - FC: 60-100 bpm
    - PR: 120-200 ms
    - QRS: 60-120 ms
    - QT: <440 ms (♂) <460 ms (♀)
    - Eje: -30° a +90°
    """)

    st.markdown("---")

    st.markdown("### 🔍 Territorios Vasculares")
    st.write("""
    - **LAD** (Anterior): V1-V4
    - **LCx** (Lateral): I, aVL, V5-V6
    - **RCA** (Inferior): II, III, aVF
    - **Posterior**: V1-V2 (reciprocal)
    """)

    st.markdown("---")

    st.markdown("### 💓 Patrones Avanzados")
    with st.expander("Arritmias Supraventriculares"):
        st.write("""
        **Fibrilación Auricular (AF)**
        - Ausencia de ondas P definidas
        - Baseline con fibrilación fina/gruesa
        - Ritmo irregularmente irregular
        - FC variable (100-160 típico)

        **Flutter Auricular**
        - Ondas flutter regulares (sawtooth)
        - FC > 250 bpm auricular
        - VR depende de AV bloqueo (2:1, 3:1, etc.)
        - Ritmo regular/regularizado
        """)

    with st.expander("Síndromes especiales"):
        st.write("""
        **WPW (Wolff-Parkinson-White)**
        - PR corto (<120 ms)
        - Delta wave (slurred QRS onset)
        - QRS prolongado (>120 ms)
        - ST depression secundaria
        - Riesgo de AF preexcitada

        **Long QT Syndrome**
        - QT muy prolongado (>500 ms)
        - T wave prominente/bífido
        - U waves visibles
        - Riesgo de torsades de pointes
        """)

    st.markdown("---")

    st.markdown("### 🎓 Desafíos de Aprendizaje")
    st.write("""
    1. Identifica todas las ondas (P, Q, R, S, T)
    2. Mide intervalos (PR, QRS, QT)
    3. Localiza territorios vasculares
    4. Reconoce patrones de bloqueo
    5. Detecta arritmias
    6. Genera diagnóstico diferencial
    """)

st.markdown("---")
st.markdown("*Sistema de Educación Electrocardiográfica Profesional | 12-Lead ECG Educational Lab*")
