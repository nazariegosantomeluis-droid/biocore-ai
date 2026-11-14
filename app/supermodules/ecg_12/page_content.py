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
from typing import Dict
# Rutas ajustadas (Tanda de eliminación de pages_legacy, Movimiento 1, 2026-07-13):
# este archivo vivía en app/pages_legacy/ (2 niveles bajo la raíz del repo) y ahora
# vive en app/supermodules/ecg_12/ (3 niveles) — un nivel más de profundidad, así
# que el cálculo de la raíz del repo necesita un salto más. Nada más cambió.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 2026-11-14 (Art. I): el trazado sale de `twelve_lead_synth` (12 derivaciones de verdad, con la verdad aparte) y
# el análisis de `twelve_lead_measure` (mide y compara con criterios citados). Antes: `TwelveLeadEcgGenerator`
# (QRS de 160 ms aun en «Normal», bloqueos que solo escalaban amplitudes), FA/flutter/WPW/QT largo como UNA
# señal copiada a las 12 derivaciones, y `TwelveLeadEcgAnalyzer` (bloqueos por amplitud, «ST» donde había
# menos señal). Ver CHANGELOG.md.
from src.signals.ecg.twelve_lead_synth import generate_twelve_lead
from src.signals.ecg.twelve_lead_measure import POPULATIONS, analyze_twelve_lead
from app.supermodules.ecg_12.report_view import render_twelve_lead_report
from src.signals.ecg.arrhythmia_types import SINUS_NORMAL_RANGE_BPM, get_type
from clinical.calculators import QRS_AXIS_CITATION
from educational.quiz_bank import ECG12_QUESTIONS
from clinical.ecg_references import (
    DREW_2010, KUSUMOTO_2018, PAGE_2015, RAUTAHARJU_2009, SURAWICZ_2009, VAN_GELDER_2024, WAGNER_2009,
)

# Unificación 1 y 3: la FC de estas condiciones sale de la fuente única de tipos de ritmo, no de un
# número propio de esta página (antes: FA 112 fijo, flutter 150 fijo, y "Bradicardia"/"Taquicardia
# sinusal" dibujaban el slider -- 75 lpm por defecto -- con la etiqueta cambiada). La generación de la
# onda sigue siendo de este laboratorio; la fisiología (la FC) no.
_CANONICAL_RHYTHM_TYPE = {"af": "afib", "flutter": "aflutter", "bradycardia": "sbrady", "tachycardia": "stachy"}


def canonical_hr(condition_short: str):
    """FC del trazado (punto medio del rango declarado del tipo) o `None` si la condición no es un
    tipo de ritmo y manda el slider."""
    key = _CANONICAL_RHYTHM_TYPE.get(condition_short)
    return get_type(key).nominal_hr_bpm if key else None


def generation_hr(condition_short: str, slider_hr: float) -> float:
    """FC con la que se genera el trazado -- y la que muestra la métrica: la del tipo si la etiqueta lo es;
    "Normal" respeta el slider solo dentro del rango sinusal normal (60-100); el resto de condiciones
    (STEMI, bloqueos, LVH, WPW, QT largo) no nombran una FC y siguen al slider."""
    fixed = canonical_hr(condition_short)
    if fixed is not None:
        return fixed
    if condition_short == "normal":
        lo, hi = SINUS_NORMAL_RANGE_BPM
        return float(min(max(slider_hr, lo), hi))
    return float(slider_hr)


def declared_range_note(condition_short: str, slider_hr: float = None):
    """Aviso de FC para el trazado: rango declarado de un tipo, o el recorte de "Normal"; `None` si no aplica."""
    key = _CANONICAL_RHYTHM_TYPE.get(condition_short)
    if key is None:
        if condition_short == "normal" and slider_hr is not None and generation_hr("normal", slider_hr) != slider_hr:
            lo, hi = SINUS_NORMAL_RANGE_BPM
            return (
                f"Ritmo sinusal normal: FC {lo:.0f}-{hi:.0f} lpm. El slider pedía {slider_hr:g} lpm; "
                f"se limitó a {generation_hr('normal', slider_hr):g} lpm para que el trazado sea el que dice la etiqueta."
            )
        return None
    t = get_type(key)
    rango = f"{t.hr_min_bpm:.0f}" if t.hr_min_bpm == t.hr_max_bpm else f"{t.hr_min_bpm:.0f}-{t.hr_max_bpm:.0f}"
    return (
        f"{t.label}: rango declarado FC {rango} lpm, {t.regularity_label}. Este trazado usa "
        f"{t.nominal_hr_bpm:.0f} lpm (punto medio); el slider de FC no aplica a este tipo."
    )

# Consolidación Visual Tanda 3 (2026-09-21): `PALETTE`/`BADGES`/
# `render_metric_card` -- fuente única de color y de tarjeta de métrica
# (`app/utils/design_system.py`), reemplaza el `<style>` propio de este
# archivo (retirado más abajo) y los hex sueltos de `.warning-box`/
# `.normal-box` (`#dc2626`/`#059669`, que ni siquiera coincidían con
# `PALETTE.CRITICAL`/`PALETTE.STABLE`).
from app.utils.design_system import BADGES, render_metric_card


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


STEMI_SCENARIOS = ("anterior_stemi", "inferior_stemi", "lateral_stemi")
OWN_QRS_SCENARIOS = ("rbbb", "lbbb", "wpw")   # fijan su propio QRS (≥ 120 ms)


def simulate_device_capture(condition_short: str, hr: float = 75, **kwargs):
    """Captura simulada «tipo dispositivo»: el mismo generador con más ruido (0.025 mV) y deriva de la línea de
    base (0.05 mV a 0.25 Hz). Devuelve (derivaciones, verdad). `hr` es `generation_hr(...)`."""
    return generate_twelve_lead(condition_short, hr, 10.0, 500.0, noise_mv=0.025, baseline_wander_mv=0.05,
                                seed=1, **kwargs)

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
    "que combinarlas permite **localizar** un problema, no solo detectarlo: una elevación del ST en "
    "V1-V4 apunta a la arteria descendente anterior (cara anterior); solo en II, III y aVF, a la "
    "coronaria derecha o a la circunfleja (cara inferior), según la AHA/ACCF/HRS 2009 (parte VI)."
)

# Two column layout
col1, col2 = st.columns([2, 1])

with col1:
    condition = st.selectbox(
        "🩺 Escenario clínico",
        [
            "Normal - Ritmo sinusal normal",
            "Taquicardia sinusal - FC > 100 lpm",
            "Bradicardia sinusal - FC < 60 lpm por convención (< 50 según la guía de 2018)",
            "🔴 STEMI Anterior - Infarto anterior (DA)",
            "🔴 STEMI Inferior - Infarto inferior (CD o Cx)",
            "🔴 STEMI Lateral - Infarto lateral alto (I y aVL, V5-V6)",
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
        "Taquicardia sinusal - FC > 100 lpm": "tachycardia",
        "Bradicardia sinusal - FC < 60 lpm por convención (< 50 según la guía de 2018)": "bradycardia",
        "🔴 STEMI Anterior - Infarto anterior (DA)": "anterior_stemi",
        "🔴 STEMI Inferior - Infarto inferior (CD o Cx)": "inferior_stemi",
        "🔴 STEMI Lateral - Infarto lateral alto (I y aVL, V5-V6)": "lateral_stemi",
        "Bloqueo de rama derecha (RBBB)": "rbbb",
        "Bloqueo de rama izquierda (LBBB)": "lbbb",
        "Hipertrofia ventricular izquierda (LVH)": "lvh",
        "💓 Fibrilación Auricular - Ritmo irregularmente irregular": "af",
        "💓 Flutter Auricular - Ondas flutter regulares": "flutter",
        "⚡ Síndrome WPW - Vía accesoria (PR corto, delta wave)": "wpw",
        "⚠️ Síndrome QT largo - QT prolongado, riesgo de torsadas": "long_qt",
    }

    signal_source = "Generar señal sintética"
    heart_rate, p_amplitude, qrs_duration, st_elevation = 75, 0.15, 80, 0.3
    condition_short_ui = condition_map.get(condition, "normal")
    apply_filter = True
    uploaded_ecg = None

    with st.expander("⚙️ Parámetros avanzados y origen de la señal", expanded=False):
        col_cfg1, col_cfg2 = st.columns(2)

        with col_cfg1:
            # Key explícita (Fusión ECG Lab, 2026-07-14): near-miss con el
            # slider de FC de render_ecg_monitor_page (mismo tema, difieren
            # solo en mayúscula) — ver docstring de render_ecg_lab_page().
            # Unificación 3: si la etiqueta fija la FC (tipo de ritmo), el slider no aplica y se deshabilita.
            heart_rate = st.slider(
                "Frecuencia Cardíaca (bpm)",
                min_value=30, max_value=200, value=75,
                help="Rango normal: 60-100 bpm. No aplica a Taquicardia, Bradicardia, FA ni Flutter: "
                     "esa etiqueta fija la FC (fuente única de tipos de ritmo). En 'Normal' se limita a 60-100.",
                key="ecglab_12_hr_slider",
                disabled=canonical_hr(condition_map.get(condition, "normal")) is not None,
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
                help="Para los escenarios de QRS estrecho. Normal: hasta 110 ms (Surawicz 2009). Los bloqueos "
                     "de rama y el WPW fijan el suyo (≥ 120 ms). Con más de 110 ms el análisis lo dirá.",
                key="ecglab_12_qrs_duration_slider",
                disabled=condition_short_ui in OWN_QRS_SCENARIOS,
            )

            # 2026-11-14: antes -0.5 a 0.5 con 0 por defecto, así que los tres «STEMI» salían sin elevación.
            st_elevation = st.slider(
                "Elevación del ST en el punto J (mV, solo infartos)",
                min_value=0.0, max_value=0.6, value=0.3, step=0.05,
                help="0.3 mV = referencia del escenario. El umbral de la ESC 2023 es ≥ 0.1 mV en dos derivaciones "
                     "contiguas (más en V2-V3): bájalo para ver cuándo deja de cumplirse.",
                key="ecglab_12_st_slider",
                disabled=condition_short_ui not in STEMI_SCENARIOS,
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
            st.info("Se simulará una captura tipo dispositivo (el mismo trazado con más ruido y deriva de la línea "
                    "de base) y se le aplicará el mismo análisis por criterios.")
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
    hr = generation_hr(condition_short, heart_rate)  # la FC con que se genera Y la que muestra la métrica
    ecg_data = {}

    truth = None
    if signal_source == "Cargar ECG desde archivo CSV" and uploaded_ecg is not None:
        # 2026-11-14 (Art. I): antes, un archivo con solo II se «completaba» copiando II escalada a las otras 11
        # derivaciones. Ahora se analiza lo que trae; el análisis dice qué no puede evaluar sin las demás.
        ecg_data = load_ecg_csv_file(uploaded_ecg)
        if len(ecg_data) > 0 and 'time' not in ecg_data:
            first_lead = next((lead for lead in ['I', 'II', 'III', 'V1'] if lead in ecg_data), None)
            length = len(ecg_data[first_lead]) if first_lead else 0
            ecg_data['time'] = np.arange(length) / 500.0

    # Trazado cargado de archivo: no se generó con ninguna FC, así que la métrica no puede mostrar el slider.
    from_file = len(ecg_data) > 0

    generator_args = dict(qrs_ms=float(qrs_duration), p_amplitude_mv=float(p_amplitude),
                          st_elevation_mv=float(st_elevation))
    if signal_source == "Simular captura de dispositivo" and len(ecg_data) == 0:
        ecg_data, truth = simulate_device_capture(condition_short, hr, **generator_args)

    if signal_source == "Generar señal sintética" or len(ecg_data) == 0:
        ecg_data, truth = generate_twelve_lead(condition_short, hr, 10.0, 500.0, seed=0, **generator_args)

    st.session_state.ecg_data = ecg_data
    st.session_state.ecg_truth = truth
    st.session_state.condition = condition_short
    # FC del trazado realmente generado (`generation_hr`); `None` si el trazado vino de un archivo.
    st.session_state.heart_rate = None if from_file else hr
    st.session_state.heart_rate_note = None if from_file else declared_range_note(condition_short, heart_rate)
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
    absent = [lead for lead in leads if lead not in ecg_data]
    if absent:
        st.caption("No vienen en el registro (se dibujan planas, no son datos): " + ", ".join(absent) + ".")
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

    population_labels = {"Mostrar para quién se cumple": None}
    population_labels.update({label.capitalize(): key for key, label in POPULATIONS.items()})
    population_choice = st.radio(
        "Umbrales que dependen del sexo y la edad (ST en V2-V3 y QTc):", list(population_labels),
        horizontal=True, key="ecglab_12_population",
    )
    report = analyze_twelve_lead(ecg_data, population=population_labels[population_choice])
    render_twelve_lead_report(report, st.session_state.get("ecg_truth"))

    st.markdown("---")

    # Educational quiz
    st.markdown("## 🎓 Desafío Educativo")

    # 2026-11-14 (Art. I): el banco vive en `educational/quiz_bank.py`, cada pregunta con su
    # explicación y su fuente. Antes estaba aquí, sin fuentes y con errores (la pericarditis al revés,
    # «derivadas sintéticas» desde una sola derivación, un SNR sin unidades, el patrón de HVI llamado
    # «pseudo-infarto»): ver CHANGELOG.md. La respuesta empieza sin elegir (antes quedaba marcada la
    # primera opción) y las opciones salen en el orden de `display_choices()`.
    question_index = st.selectbox(
        "Selecciona la pregunta:",
        list(range(1, len(ECG12_QUESTIONS) + 1)),
        format_func=lambda x: f"Pregunta {x}",
        key="ecglab_12_quiz_question",
    )
    current_question = ECG12_QUESTIONS[question_index - 1]

    st.write(f"**Pregunta {question_index}:** {current_question.prompt}")
    selected_answer = st.radio(
        "Respuesta:", current_question.display_choices(), index=None, key=f"ecglab_12_quiz_{question_index}"
    )

    if st.button("Verificar respuesta", key="ecglab_12_quiz_verify"):
        if selected_answer is None:
            st.warning("Elige una respuesta antes de verificar.")
        else:
            if current_question.is_correct(selected_answer):
                st.success(f"✅ Correcto. {current_question.explanation}")
            else:
                st.error(
                    f"❌ Incorrecto: la respuesta es **{current_question.correct_choice}**. "
                    f"{current_question.explanation}"
                )
            st.caption(f"Fuente: {current_question.source}")

with col2:
    st.markdown("## 📊 Métricas")

    if st.session_state.get("heart_rate") is not None:
        # Consolidación Visual Tanda 3 (2026-09-21): `st.metric` crudo ->
        # `render_metric_card`. `heart_rate` es el parámetro de generación
        # (`generation_hr`: el del tipo de ritmo, o el slider), no una medición
        # sobre la señal -- pero es el MISMO con el que se generó el trazado
        # (Unificación 3). `BADGES.HEURISTIC` (no hay `*_CITATION` que lo
        # respalde; sin `classification=`, no se fabrica un semáforo de 3 niveles).
        render_metric_card(
            "FC (bpm)", f"{st.session_state.heart_rate:g}",
            provenance=BADGES.HEURISTIC,
        )
        if st.session_state.get("heart_rate_note"):
            st.caption(st.session_state.heart_rate_note)

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

    # 2026-11-14 (Art. I): antes «QT: <440 ms (♂) <460 ms (♀)» (no decía QTc y el corte de hombres no
    # era el de la AHA/ACCF/HRS 2009) y «QRS: 60-120 ms» (de 110 a 119 ms ya es bloqueo incompleto o
    # trastorno inespecífico). Cada valor lleva ahora su fuente.
    st.info("""
    **Referencia del adulto:**
    - FC: 60-100 lpm (convención docente; la guía ACC/AHA/HRS 2018 define la bradicardia sinusal como < 50 lpm)
    - PR: 120-200 ms (< 120 ms es criterio de preexcitación; > 200 ms, bloqueo AV de primer grado)
    - QRS: hasta 110 ms (110-119 ms: bloqueo incompleto o trastorno inespecífico; ≥ 120 ms: bloqueo de rama completo)
    - QTc prolongado: ≥ 450 ms (♂), ≥ 460 ms (♀); QT corto: ≤ 390 ms
    - Eje: -30° a +90°
    """)
    st.caption(f"Fuentes: {KUSUMOTO_2018}; {SURAWICZ_2009}; {RAUTAHARJU_2009}; {QRS_AXIS_CITATION}")

    st.markdown("---")

    st.markdown("### 🔍 Territorios Vasculares")
    # 2026-11-14 (Art. I): antes «LAD (Anterior): V1-V4 · LCx (Lateral): I, aVL, V5-V6 · RCA (Inferior):
    # II, III, aVF · Posterior: V1-V2 (reciprocal)», en inglés y sin fuente. La parte VI dice que II, III
    # y aVF solos pueden ser de la coronaria derecha o de la circunfleja, y no asigna la cara lateral a una
    # arteria; queda solo lo que dice.
    st.write("""
    - **Descendente anterior (DA), cara anterior:** elevación del ST en algunas o todas de V1–V6; si la oclusión es proximal, en V1–V4, I, aVL y a menudo aVR
    - **II, III y aVF solos (cara inferior):** coronaria derecha (CD) o circunfleja (Cx)
    - **Depresión del ST en V1–V2:** infarto posterior o lateral con elevación del ST
    """)
    st.caption(f"Fuente: {WAGNER_2009}")

    st.markdown("---")

    st.markdown("### 💓 Patrones Avanzados")
    # 2026-11-14 (Art. I): antes listas sin fuente («FC 100-160 típico», «ST depression secundaria», «U waves
    # visibles»...). Queda lo que dicen las fuentes, citadas.
    with st.expander("Arritmias supraventriculares"):
        st.markdown(
            "**Fibrilación auricular:** sin ondas P discernibles y regulares, con activación ventricular "
            "irregular (sin patrón en los RR). Un ECG de 12 derivaciones dura 10 s; con dispositivos de una o "
            "varias derivaciones, el consenso ha sido pedir 30 s o más.\n\n"
            "**Flutter auricular típico:** ondas F «en sierra», predominantemente negativas en II, III y aVF; "
            "frecuencia auricular típica de 300 lpm (ciclo de 200 ms), que puede ser menor con fármacos o "
            "cicatrices. Con conducción 2:1 la frecuencia ventricular queda en la mitad."
        )
        st.caption(f"Fuentes: {VAN_GELDER_2024} (secciones 3.1 y 3.2); {PAGE_2015} (tabla 3)")

    with st.expander("Síndromes especiales"):
        st.markdown(
            "**Preexcitación ventricular (patrón de Wolff-Parkinson-White):** PR < 120 ms en ritmo sinusal, "
            "empastamiento inicial del QRS (onda delta) y QRS > 120 ms.\n\n"
            "**QT largo:** QTc prolongado si es ≥ 450 ms en hombres o ≥ 460 ms en mujeres; con QTc ≥ 500 ms el "
            "riesgo de torsade de pointes es 2 a 3 veces mayor, sin un umbral a partir del cual ocurra con certeza."
        )
        st.caption(f"Fuentes: {SURAWICZ_2009}; {RAUTAHARJU_2009}; {DREW_2010}")

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
