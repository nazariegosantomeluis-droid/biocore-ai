"""
Streamlit utilities and helpers for Biomedical Signal Platform.

Provides:
- Signal generation and caching
- Import wrappers with fallbacks
- Visualization helpers
- Error handling utilities
"""

from __future__ import annotations

import os
import time
import sys
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import streamlit as st

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# ============================================================================
# SAFE IMPORTS WITH FALLBACKS
# ============================================================================

def safe_import_plotly():
    """Import plotly with graceful fallback."""
    try:
        import plotly.graph_objects as go
        import plotly.subplots as sp
        return go, sp, True
    except ImportError:
        st.warning("⚠️ Plotly not installed. Install with: pip install plotly")
        return None, None, False


# `render_sidebar_navigation()` retirada (2026-08-20, Capa 2 Fase 2.1,
# cierre) -- vestigio de la arquitectura Streamlit multipágina anterior:
# 13 enlaces `localhost:8501/NombrePágina` que no resuelven a nada en la
# arquitectura actual (un solo script, navegación por `session_state`, sin
# directorio `app/pages/` vivo). Confirmado por AppTest que renderizaba de
# verdad en el sidebar de ECG-12/EEG Neuro Lab/Respiratory Lab, apilado
# debajo de la navegación real -- una trampa de UX activa: al hacer clic,
# el usuario perdía su `session_state` y volvía a la app en blanco, no una
# simple redundancia inofensiva. El sidebar real (`app/main.py`, por
# `session_state`) nunca dependió de este widget. Ver CHANGELOG.md.
    st.sidebar.markdown("---")
    st.sidebar.markdown("Usa estos enlaces para cambiar rápidamente entre páginas y secciones del panel.")


def safe_import_ecg_modules():
    """Import ECG analysis modules with error handling."""
    ECGAnalyzer = None
    create_clinical_ecg_figure = None
    load_mitbih_record = None
    get_mitbih_records = None

    try:
        from clinical.ecg_analyzer import ECGAnalyzer
    except ImportError as e:
        st.warning(f"⚠️ ECG analysis engine not available: {e}")

    try:
        from visualization.medical.plotly_clinical import create_clinical_ecg_figure
    except ImportError as e:
        st.warning(f"⚠️ Clinical ECG plot module not available: {e}")

    try:
        from signals.loaders import load_mitbih_record, get_mitbih_records
    except ImportError as e:
        st.warning(f"⚠️ MIT-BIH loader import failed: {e}")
        try:
            import signals.loaders.wfdb_loader as wfdb_loader
            load_mitbih_record = wfdb_loader.load_mitbih_record
            get_mitbih_records = wfdb_loader.get_mitbih_records
            st.info("Usando loader MIT-BIH alternativo desde signals.loaders.wfdb_loader")
        except Exception as fallback_exc:
            st.warning(f"⚠️ Fallback MIT-BIH loader no disponible: {fallback_exc}")

    ecg_ok = bool(load_mitbih_record and get_mitbih_records)
    return ECGAnalyzer, create_clinical_ecg_figure, load_mitbih_record, get_mitbih_records, ecg_ok


def safe_import_src_modules():
    """Import source platform modules with safe fallback."""
    try:
        from src.clinical import interpret_ecg
        from src.data import load_biomedical_signal, assess_signal_quality, validate_signal as validate_signal_src
        from src.education import create_quiz, explain_waveform, clinical_case
        from src.rural_health import LocalPatientDatabase, generate_pdf_report
        from src.signals.ecg import preprocess_ecg, extract_ecg_features
        from src.utils.config import AppConfig
        from src.signal_processing import bandpass_filter, detect_r_peaks, compute_rr_intervals
        from src.feature_extraction import compute_psd, extract_features

        return {
            'interpret_ecg': interpret_ecg,
            'load_biomedical_signal': load_biomedical_signal,
            'assess_signal_quality': assess_signal_quality,
            'validate_signal': validate_signal_src,
            'create_quiz': create_quiz,
            'explain_waveform': explain_waveform,
            'clinical_case': clinical_case,
            'LocalPatientDatabase': LocalPatientDatabase,
            'generate_pdf_report': generate_pdf_report,
            'preprocess_ecg': preprocess_ecg,
            'extract_ecg_features': extract_ecg_features,
            'AppConfig': AppConfig,
            'bandpass_filter': bandpass_filter,
            'detect_r_peaks': detect_r_peaks,
            'compute_rr_intervals': compute_rr_intervals,
            'compute_psd': compute_psd,
            'extract_features': extract_features,
        }, True
    except ImportError as e:
        st.warning(f"⚠️ Source platform modules not available: {e}")
        return {}, False


def safe_import_multisensor():
    """Import multisensor modules with error handling and fallback classes."""
    try:
        from dashboards.multisensor import BiosignalChannel, MultisensoralRecord
        return BiosignalChannel, MultisensoralRecord, True
    except ImportError as e:
        st.warning(f"⚠️ Multisensor modules unavailable; usando fallback ligero: {e}")
        return FallbackBiosignalChannel, FallbackMultisensoralRecord, False


class FallbackBiosignalChannel:
    def __init__(self, name: str, signal: np.ndarray, fs: float, unit: str = '', signal_type: str = ''):
        self.name = name
        self.signal = np.asarray(signal, dtype=float)
        self.fs = fs
        self.unit = unit
        self.signal_type = signal_type


class FallbackMultisensoralRecord:
    def __init__(self, channels: List[FallbackBiosignalChannel], patient_id: str = 'DEMO_001'):
        self.channels = channels
        self.patient_id = patient_id

    def compute_physiological_indices(self) -> Dict[str, float]:
        return {
            'heart_rate': float(self._estimate_heart_rate()),
            'spo2_mean': float(self._mean_channel('SpO2', 98.0)),
            'temperature': float(self._mean_channel('Temperature', 37.0)),
            'respiration_rate': float(self._estimate_respiration_rate())
        }

    def health_score(self) -> Dict[str, float]:
        indices = self.compute_physiological_indices()
        hr_score = np.clip(100 - abs(indices['heart_rate'] - 72), 0, 100)
        o2_score = np.clip((indices['spo2_mean'] - 90) * 4, 0, 100)
        temp_score = np.clip(100 - abs(indices['temperature'] - 37.0) * 40, 0, 100)
        rr_score = np.clip(100 - abs(indices['respiration_rate'] - 16) * 5, 0, 100)
        overall = float(np.clip(np.mean([hr_score, o2_score, temp_score, rr_score]), 0, 100))
        return {
            'cardiovascular': float(hr_score),
            'autonomic': float(rr_score),
            'oxygenation': float(o2_score),
            'recovery': float(temp_score),
            'overall': overall
        }

    def detect_physiological_inconsistencies(self) -> List[str]:
        issues: List[str] = []
        indices = self.compute_physiological_indices()
        if indices['heart_rate'] < 60 or indices['heart_rate'] > 100:
            issues.append('Frecuencia cardíaca anormal')
        if indices['spo2_mean'] < 90:
            issues.append('SpO2 baja')
        if indices['temperature'] < 36.5 or indices['temperature'] > 37.5:
            issues.append('Temperatura corporal fuera de rango')
        if indices['respiration_rate'] < 12 or indices['respiration_rate'] > 22:
            issues.append('Frecuencia respiratoria irregular')
        return issues

    def _mean_channel(self, name: str, fallback: float = 0.0) -> float:
        for channel in self.channels:
            if channel.name.lower() == name.lower() and channel.signal.size > 0:
                return float(np.nanmean(channel.signal))
        return float(fallback)

    def _estimate_heart_rate(self) -> float:
        for channel in self.channels:
            if channel.signal_type == 'ecg' and channel.signal.size > 0:
                return float(estimate_ecg_heart_rate(channel.signal, channel.fs))
        return 72.0

    def _estimate_respiration_rate(self) -> float:
        for channel in self.channels:
            if channel.signal_type in ('respiration', 'resp') and channel.signal.size > 0:
                return float(estimate_respiration_rate(channel.signal, channel.fs))
        return 16.0


def estimate_ecg_heart_rate(signal: np.ndarray, fs: float) -> float:
    signal = np.asarray(signal, dtype=float)
    if signal.size < fs:
        return 0.0
    threshold = np.mean(signal) + 0.35 * np.std(signal)
    peaks = np.where(
        (signal[1:-1] > threshold) &
        (signal[1:-1] > signal[:-2]) &
        (signal[1:-1] > signal[2:])
    )[0] + 1
    n_beats = len(peaks)
    duration_s = len(signal) / fs
    return float(np.clip((n_beats / duration_s) * 60.0, 0, 220))


def estimate_respiration_rate(signal: np.ndarray, fs: float) -> float:
    signal = np.asarray(signal, dtype=float)
    if signal.size < fs:
        return 0.0
    kernel = max(1, int(fs * 0.3))
    smoothed = np.convolve(signal, np.ones(kernel) / kernel, mode='same')
    threshold = np.mean(smoothed)
    crossings = np.where((smoothed[:-1] <= threshold) & (smoothed[1:] > threshold))[0]
    n_cycles = len(crossings) / 2.0 if len(crossings) >= 2 else 0.0
    duration_s = len(signal) / fs
    return float(np.clip((n_cycles / duration_s) * 60.0, 0, 60))


def validate_time_window(start: float, end: float) -> Tuple[float, float]:
    if start < 0:
        start = 0.0
    if end <= start:
        end = start + 1.0
    return start, end


# ============================================================================
# SIGNAL GENERATION AND CACHING
# ============================================================================

# generate_demo_ecg_signal() retirada (Fase 5B, 2026-08-30, ver
# CHANGELOG.md) -- reemplazada por DynamicECGGenerator (McSharry et al.
# 2003, oscilador de fase + gaussianas + restitución QT de Bazett),
# `src/signals/ecg/dynamic_ecg_generator.py`. Esta función tenía 3 bugs
# confirmados por ejecución: ignoraba el `hr` pedido (QRS con ciclo fijo
# `t % 1`, `hr_rad` calculado y nunca usado), su HR se medía con un
# detector saturado en 220bpm, y su QRS no toleraba período variable.
# Confirmado por grep antes de retirar: cero llamadores vivos (los 3
# consumidores -- ECG Monitor modo demo, Multisensor Fusion Lab Clínica y
# Vista Simulación -- migrados a DynamicECGGenerator en la misma tanda).


@st.cache_data
def generate_demo_ppg_signal(fs: float = 250, duration: float = 30, hr: float = 72) -> np.ndarray:
    """Generate demo PPG signal (cached)."""
    n_samples = int(fs * duration)
    t = np.arange(n_samples) / fs
    
    # PPG waveform (lower frequency than ECG)
    ppg_freq = hr / 60
    ppg = 0.5 * np.sin(2 * np.pi * ppg_freq * t)
    ppg += 0.2 * np.sin(4 * np.pi * ppg_freq * t)  # Harmonic
    
    # Baseline drift
    ppg += 0.03 * np.sin(2 * np.pi * 0.05 * t)
    
    # Noise
    ppg += 0.05 * np.random.normal(0, 1, n_samples)
    
    return ppg


@st.cache_data
def generate_demo_spo2_signal(fs: float = 250, duration: float = 30, baseline: float = 98.0) -> np.ndarray:
    """Generate demo SpO2 signal (cached).

    `baseline` añadido (2026-08-20, Capa 2 Fase 2.2) -- mismo patrón que
    `hr` en `generate_demo_ecg_signal()`/`rr` en
    `generate_demo_respiration_signal()`, sus dos funciones hermanas, que ya
    tomaban su parámetro objetivo. Antes esta era la única de las tres sin
    uno -- el rango de clip se ajusta alrededor de `baseline` en vez de
    quedar fijo en 95-100, para que un valor bajo (p.ej. 80) se refleje de
    verdad en la señal generada."""
    n_samples = int(duration)  # 1 Hz sampling for SpO2
    baseline = float(baseline)  # un slider entero (p.ej. Multisensor) da int -- np.full heredaría
    # dtype int64 y el += con ruido float fallaría al castear in-place.

    spo2 = np.full(n_samples, baseline)
    spo2 += np.random.normal(0, 0.3, n_samples)
    spo2 = np.clip(spo2, max(0.0, baseline - 3), min(100.0, baseline + 2))

    return spo2


@st.cache_data
def generate_demo_respiration_signal(fs: float = 250, duration: float = 30, rr: float = 16) -> np.ndarray:
    """Generate demo respiration signal (cached)."""
    n_samples = int(fs * duration)
    t = np.arange(n_samples) / fs
    
    # Respiration (0.2-0.4 Hz typically)
    resp_freq = rr / 60
    resp = 2.0 * np.sin(2 * np.pi * resp_freq * t)
    
    # Add some noise
    resp += 0.1 * np.random.normal(0, 1, n_samples)
    
    return resp


@st.cache_data
def generate_demo_temperature_signal(fs: float = 250, duration: float = 30, base_temp: float = 37.0) -> np.ndarray:
    """Generate demo temperature signal (cached)."""
    n_samples = int(duration)  # 1 Hz sampling for temperature
    
    temp = np.full(n_samples, base_temp)
    temp += 0.1 * np.random.normal(0, 1, n_samples)
    temp = np.clip(temp, 36.5, 37.5)
    
    return temp


@st.cache_data
def generate_demo_bp_signal(fs: float = 250, duration: float = 30, sys: float = 120) -> np.ndarray:
    """Generate demo blood pressure signal (cached)."""
    n_samples = int(duration)  # 1 Hz sampling for BP
    
    bp = np.full(n_samples, sys, dtype=float)
    bp += 1.5 * np.sin(2 * np.pi * np.linspace(0, duration, n_samples) / duration)
    bp = np.clip(bp, 100, 140)
    return bp

# ============================================================================
# VISUALIZATION HELPERS
# ============================================================================

def plot_signal_matplotlib(signal: np.ndarray, fs: float = 250, title: str = "Signal", unit: str = "mV"):
    """Fallback visualization using Matplotlib (when Plotly unavailable)."""
    try:
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(12, 3))
        time = np.arange(len(signal)) / fs
        ax.plot(time, signal, 'b-', linewidth=1)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel(f'Amplitude ({unit})')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        
        st.pyplot(fig)
    except ImportError:
        st.error("❌ Neither Plotly nor Matplotlib available")


def plot_clinical_ecg_safe(signal: np.ndarray, fs: float, r_peaks: Optional[np.ndarray] = None):
    """Safely plot clinical ECG with fallback."""
    go, sp, plotly_ok = safe_import_plotly()
    
    if plotly_ok:
        try:
            from visualization.medical.plotly_clinical import create_clinical_ecg_figure
            
            fig = create_clinical_ecg_figure(signal, fs, r_peaks=r_peaks)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"⚠️ Plotly rendering failed: {e}")
            plot_signal_matplotlib(signal, fs, title="ECG Signal (Matplotlib Fallback)")
    else:
        plot_signal_matplotlib(signal, fs, title="ECG Signal (Matplotlib Fallback)")


# ============================================================================
# ERROR HANDLING
# ============================================================================

def display_error_message(error: Exception, context: str = ""):
    """Display formatted error message."""
    st.error(f"❌ Error in {context}: {str(error)}")


def display_info_message(message: str, icon: str = "ℹ️"):
    """Display formatted info message."""
    st.info(f"{icon} {message}")


def display_success_message(message: str, icon: str = "✅"):
    """Display formatted success message."""
    st.success(f"{icon} {message}")


def display_warning_message(message: str, icon: str = "⚠️"):
    """Display formatted warning message."""
    st.warning(f"{icon} {message}")


# ============================================================================
# SESSION STATE HELPERS
# ============================================================================

def init_session_state_key(key: str, default_value: Any = None):
    """Initialize session state key if not exists."""
    if key not in st.session_state:
        st.session_state[key] = default_value


def cache_signal_in_session(key: str, signal: np.ndarray):
    """Cache signal in session state."""
    st.session_state[key] = signal


def get_cached_signal(key: str) -> Optional[np.ndarray]:
    """Get cached signal from session state."""
    return st.session_state.get(key)


# ============================================================================
# COGNITIVE EXPLORATION HELPERS
# ============================================================================

def render_metric_explained(title: str, value: Any, unit: str = '', meaning: Optional[str] = None,
                            importance: Optional[str] = None, affects: Optional[str] = None,
                            relations: Optional[str] = None, consequences: Optional[str] = None) -> None:
    """Render a metric with an explanation answering the five key questions for the user."""
    try:
        display_value = f"{value} {unit}" if unit else f"{value}"
    except Exception:
        display_value = str(value)

    st.markdown(f"**{title}** — {display_value}")
    with st.expander(f"¿Qué significa {title}?", expanded=False):
        st.markdown(f"- **¿Qué significa?**  {meaning or 'Valor clínico cuantitativo que resume un aspecto fisiológico.'}")
        st.markdown(f"- **¿Por qué importa?**  {importance or 'Permite priorizar decisiones clínicas y educativas.'}")
        st.markdown(f"- **¿Qué la afecta?**  {affects or 'Fármacos, estado hemodinámico, respiración, ejercicio y artefactos técnicos.'}")
        st.markdown(f"- **¿Cómo se relaciona con otros sistemas?**  {relations or 'Interacciona con ventilación, oxigenación y estado neurológico.'}")
        st.markdown(f"- **¿Qué pasaría si cambia?**  {consequences or 'Un cambio significativo sugiere intervención, más pruebas o monitorización intensiva.'}")


def render_view_selector() -> str:
    """Standardized view selector for all exploration labs."""
    return st.radio(
        'Capa de Exploración Cognitiva',
        ['Clínica', 'Educativa', 'Investigación', 'IA', 'Simulación', 'Gemelo Digital'],
        horizontal=True,
        key=f"view_selector_{st.session_state.get('selected_page', 'default')}"
    )


def render_scientific_discovery_layer(signals: Dict[str, np.ndarray]):
    """Adds a layer of scientific discovery to the current lab context.

    Consolidación, Tanda 1 (2026-07-13): el botón "Identificar Patrones Ocultos"
    se eliminó — tras un time.sleep(1) siempre imprimía el mismo texto fijo
    ("...acoplamientos sutiles entre bandas de baja frecuencia"), sin leer
    `signals` en absoluto (Art. I de la Constitución). "Analizar Entropía y
    Complejidad" sí calcula algo real sobre la señal recibida — se conserva
    intacto."""
    st.markdown("---")
    st.markdown("### 🧪 Capa de Descubrimiento Científico")
    if st.button("Analizar Entropía y Complejidad"):
        for name, sig in signals.items():
            if len(sig) > 0:
                # Simple entropy proxy (mean absolute difference)
                ent = float(np.abs(np.mean(np.diff(sig))))
                st.write(f"• **{name}** - Índice de Complejidad Dinámica: {ent:.4f}")


def render_discovery_lab(name: str, signals: Dict[str, np.ndarray]):
    """Small interactive discovery panel that computes correlations and gives hypotheses."""
    with st.expander(f"🔬 Discovery Lab — {name}", expanded=False):
        st.write('Exploración de correlaciones y sensibilidad inter-sistema.')
        if len(signals) < 2:
            st.info('Se requieren al menos 2 señales para explorar correlaciones.')
            return
        if st.button(f'Ejecutar descubrimiento para {name}'):
            keys = list(signals.keys())
            mat = np.zeros((len(keys), len(keys)))
            for i in range(len(keys)):
                for j in range(len(keys)):
                    a = signals[keys[i]]
                    b = signals[keys[j]]
                    mn = min(len(a), len(b))
                    if mn > 1:
                        # Handle constant signals to avoid NaN in correlation
                        if np.std(a[:mn]) == 0 or np.std(b[:mn]) == 0:
                            mat[i, j] = 0.0
                        else:
                            mat[i, j] = float(np.corrcoef(a[:mn], b[:mn])[0, 1])
                    else:
                        mat[i, j] = 0.0
            
            # Display correlation results
            cols = st.columns(len(keys))
            for i, k in enumerate(keys):
                cols[i].markdown(f"**{k}**")
                for j, kk in enumerate(keys):
                    if i != j:
                        cols[i].write(f"vs {kk}: {mat[i,j]:.2f}")
            
            strongest = np.unravel_index(np.argmax(np.abs(mat - np.eye(len(keys))*2)), mat.shape)
            k1, k2 = keys[strongest[0]], keys[strongest[1]]
            st.write(f'Interpretación rápida: mayor acoplamiento observado entre **{k1}** y **{k2}** ({mat[strongest]:.2f}).')


# ============================================================================
# DATA VALIDATION
# ============================================================================

def validate_signal(signal: np.ndarray, min_length: int = 100, max_length: int = 1000000) -> Tuple[bool, str]:
    """
    Validate signal integrity.
    
    Returns
    -------
    is_valid : bool
        Whether signal is valid
    message : str
        Validation message
    """
    if signal is None:
        return False, "Signal is None"
    
    if len(signal) < min_length:
        return False, f"Signal too short: {len(signal)} < {min_length} samples"
    
    if len(signal) > max_length:
        return False, f"Signal too long: {len(signal)} > {max_length} samples"
    
    if np.isnan(signal).any():
        return False, f"Signal contains {np.isnan(signal).sum()} NaN values"
    
    if np.isinf(signal).any():
        return False, "Signal contains infinite values"
    
    return True, "Signal valid"


# ============================================================================
# PAGE LAYOUT HELPERS
# ============================================================================

def create_metric_row(metrics: Dict[str, Tuple[str, str]], columns: int = 4):
    """Create a row of metrics."""
    cols = st.columns(columns)
    for idx, (label, (value, unit)) in enumerate(metrics.items()):
        with cols[idx % columns]:
            st.metric(label, value, unit)


def create_section(title: str, level: int = 2):
    """Create a formatted section."""
    if level == 1:
        st.markdown(f"# {title}")
    elif level == 2:
        st.markdown(f"## {title}")
    elif level == 3:
        st.markdown(f"### {title}")
    else:
        st.markdown(f"#### {title}")


def create_two_column_layout(left_weight: float = 1.0, right_weight: float = 3.0):
    """Create a two-column layout."""
    return st.columns([left_weight, right_weight])


# ============================================================================
# PERFORMANCE HELPERS
# ============================================================================

@st.cache_resource
def get_analyzer_singleton():
    """Get ECGAnalyzer singleton (cached resource)."""
    try:
        from clinical.ecg_analyzer import ECGAnalyzer
        return ECGAnalyzer(fs=250)
    except ImportError:
        return None


@st.cache_data(ttl=3600)
def cache_mitbih_record_list():
    """Cache MIT-BIH record list."""
    try:
        from signals.loaders import get_mitbih_records
        return get_mitbih_records()
    except ImportError:
        return []
