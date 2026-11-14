"""
BIOCORE AI — Digital Twin Shell

Implements the first-principles UX redesign: the Digital Human Twin is not a
page among menus — it is the home screen. There is no "ECG lab" vs
"Respiratory lab" menu split here. There is only the organism; clicking an
organ reveals whatever physiology belongs to it.

Design rules this module follows (see documentation/Nivel 00 + the UX
redesign proposal):
  - Organ-click is the primary navigation verb, not a sidebar menu.
  - The organism's own color/glow state is the at-a-glance summary — no
    separate "dashboard" is needed above it.
  - Mode (Student / Clinician / Researcher) changes vocabulary and depth for
    the same organ-click, per Engineering Principle 16 (Progressive
    Complexity) — it is a toggle, not a destination.
  - AI-relevant findings (alerts/anomalies) surface directly on the organ
    they concern, not in a separate chat panel.
  - Everything here reads from the single canonical DigitalTwinOrganism —
    no duplicate physiological state.
"""

import random
import time
from datetime import datetime
from typing import Dict, FrozenSet, Optional

import streamlit as st
import pandas as pd
import numpy as np

from app.engines import (
    DigitalTwinOrganism,
    SimulationScenario,
    PredictionEngine,
)
from clinical.calculators import PRQ_REFERENCE, PRQ_REST_REFERENCE_TEXT
from app.engines.digital_twin_organism import NO_DATA, NO_DATA_COLOR, NOT_MODELED
from app.engines.simulation_engine import ARRHYTHMIA_SCENARIO_TYPE, SimulationEngine
from app.utils.design_system import render_module_header, render_error_state, BADGES
from app.supermodules.twin_shell.baroreflex_panel import pa_model_label, render_baroreflex_panel
from app.utils.patient_session import (
    get_active_patient_id,
    get_active_session_factory,
    set_active_patient_id,
)
from app.utils.physiological_state import get_current_physiological_state, persist_current_state
from domain.physiology.hemodynamics import (
    HEMODYNAMIC_MODEL_ENABLED_SCENARIOS,
    HemodynamicModelNotEnabledError,
    compute_and_attach_closed_loop_pressure,
)
from domain.physiology.ml import build_risk_features, build_synthetic_ecg_from_ups, classify_ecg_signal
from domain.physiology.narrator import (
    DepthLevel,
    Finding,
    FindingsContext,
    NarratorNotConfiguredError,
    build_causal_context,
    build_context,
    stream_causal_narration,
    stream_findings_narration,
)
# Clave de IA por sesión (2026-10-25): "configurado" = clave pegada en esta sesión o del entorno.
from app.utils.ai_session import AI_KEY_HINT, ai_client
from app.utils.ai_session import ai_configured as narrator_is_configured
from domain.physiology.narrator import stream_narration
from domain.physiology.scenarios.rich_engine import (
    create_ephemeral_basal_patient,
    create_ephemeral_case_patient,
    run_rich_scenario,
)
from domain.physiology.state import (
    EventSeverity,
    compose_neuro_cardiac_snapshot,
    get_clinical_references_for_patient,
    get_clinical_references_for_snapshot,
    get_events,
    get_latest_snapshot_id,
    get_latest_state,
    get_snapshot_id_at,
    get_state_by_snapshot_id,
    get_value_history,
)
from src.ai.patient_analytics import AnomalyDetector, PatientRiskPredictor
from src.clinical import sepsis_trajectory
from src.signals.ecg.arrhythmia_types import ARRHYTHMIA_TYPES
from src.signals.signal_sources import ESP32SignalSource

from .ups_body_visual import render_ups_body

ORGAN_ORDER = ["heart", "brain", "lungs", "muscles", "autonomic"]

# Keywords used to route a free-text alert/anomaly string to the organ it
# concerns. Fase 1 (idioma, 2026-08-30): traducidas junto con las frases de
# `digital_twin_organism.py::_detect_anomalies()` que enrutan -- son stems
# (sin sufijo de género) para que calcen con las variantes de la frase real
# ("respirator" calza con "respiratoria"/"respiratorio").
ORGAN_KEYWORDS = {
    "heart": ["cardiovascular", "corazón", "ritmo"],
    "brain": ["estrés", "somnolencia", "cognitiv"],
    "lungs": ["respirator", "spo", "respiraci", "pulmones"],
    "muscles": ["muscular", "fatiga"],
    "autonomic": ["autonóm"],
}

# Fase 1 (idioma, 2026-08-30): los valores INTERNOS siguen en inglés a
# propósito -- se comparan en `if mode == "Student":` (render_organ_panel,
# más abajo) y son el valor por defecto de session_state. Solo la ETIQUETA
# visible del radio se traduce, vía `format_func` en `render_mode_toggle()`.
MODES = ["Student", "Clinician", "Researcher"]
MODE_LABELS = {"Student": "Estudiante", "Clinician": "Clínico", "Researcher": "Investigador"}

# --- Procedencia de los datos del Digital Twin (Tanda 2, 2026-08-14) --------
# Firma: validador clínico, Digital Twin — Tanda 2, dictamen 2026-08-14. Hace visible en la UI la distinción entre
# umbrales con respaldo citado (Categoría A) y heurísticas de ingeniería propias de BIOCORE (Categoría B) — mismo
# principio que `Provenance`/`ClinicalReferenceValue` del UPS, adaptado como badge de UI. Alias de BADGES
# (design_system.py), la fuente única. Cierre de la fase 0 (2026-11-13): tras retirar los índices sin cita, en Twin OS
# quedan tres cosas: componentes NEWS2 (🟢), el índice de salud pulmonar (🔵, pesos propios) y entradas (sin badge,
# «Entrada: …»).
PROVENANCE_CLINICAL_BADGE = BADGES.CLINICAL
PROVENANCE_HEURISTIC_BADGE = BADGES.HEURISTIC
PROVENANCE_HEURISTIC_LABEL = "Índice heurístico BIOCORE — no es un score clínico validado"
PROVENANCE_SOURCE_NEWS2 = "NEWS2 (RCP 2017)"

# Fuente de las entradas del organismo (Parte D, fase 0): o los sliders, o un escenario/intervención aplicado con un
# botón. Mientras haya un escenario activo, los sliders NO se aplican en el siguiente rerun (antes lo sobrescribían).
INPUT_SOURCE_KEY = "twin_shell_input_source"


def _set_input_source(label: str) -> None:
    st.session_state[INPUT_SOURCE_KEY] = label


def _entrada(organism: DigitalTwinOrganism) -> str:
    return f"Entrada: {organism.input_provenance or 'sin declarar'}"


def init_session() -> None:
    if "twin_shell_organism" not in st.session_state:
        st.session_state.twin_shell_organism = DigitalTwinOrganism()
    if "twin_shell_selected_organ" not in st.session_state:
        st.session_state.twin_shell_selected_organ = "heart"
    if "twin_shell_mode" not in st.session_state:
        st.session_state.twin_shell_mode = "Student"

    # Fase 1.2: UPS persistido (SQLite), distinto de `twin_shell_organism`
    # (que sigue viviendo solo en session_state). Se crea una única vez por
    # sesión de navegador — el engine/sessionmaker se reutiliza en reruns.
    # Fase 3 (paciente único de sesión, 2026-08-30): el bootstrap de
    # session_factory/patient_id se movió a `app/utils/patient_session.py`
    # -- este era 1 de los 4 sitios que lo copiaban inline. Se llama aquí
    # una vez para garantizar que exista al entrar a Twin OS (el punto de
    # entrada más común), pero cualquier módulo puede llamarlo primero.
    get_active_patient_id()


def render_ambient_header(organism: DigitalTwinOrganism) -> None:
    """La cabecera es el NEWS2 PARCIAL (fase 0, decisión 2 de Luis): los puntos por parámetro disponible (pulso, FR,
    SpO₂ escala 1) y la lista explícita de lo que falta para el total. Nunca un total: un NEWS2 parcial no es un NEWS2.
    Retirados (decisión 1): estado fisiológico global, riesgo global como número, coherencia sistémica y resiliencia."""
    partial = organism.global_state["news2_partial"]
    if partial.available:
        components = " &nbsp;·&nbsp; ".join(f"{name} <b>{points}</b>" for name, points in partial.components.items())
        worst = max(partial.components.values())
        color = {0: "#39ffbe", 1: "#ffd700", 2: "#ffd700", 3: "#ff3333"}[worst]
    else:
        components, color = f"<b style='color:{NO_DATA_COLOR};'>{NO_DATA}</b>", NO_DATA_COLOR

    st.markdown(
        f"""
        <div style='text-align:center; padding: 20px; border-radius: 22px;
                    border: 1px solid {color}55; background: rgba(255,255,255,0.03); margin-bottom: 20px;'>
            <div style='font-size: 12px; letter-spacing: 3px; color: #9fb4c9;'>NEWS2 PARCIAL — SIN TOTAL</div>
            <div style='font-size: 22px; font-weight: 700; color: {color}; line-height: 1.4;'>
                {components}
            </div>
            <div style='font-size: 13px; color: #9fb4c9;'>
                Faltan para el total: <b>{", ".join(partial.missing)}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"{PROVENANCE_CLINICAL_BADGE} Componentes NEWS2 ({PROVENANCE_SOURCE_NEWS2}), cada uno con su única entrada actual. "
        "Nunca se suman: el total NEWS2 exige los 7 parámetros y el gemelo no tiene presión, temperatura, consciencia ni "
        "oxígeno suplementario. Retirados en la fase 0 (sin cita): estado fisiológico global, riesgo global numérico, "
        "coherencia sistémica y resiliencia."
    )

    for alert in organism.global_state.get("alerts", []):
        st.warning(alert)


def _card_lines(organism: DigitalTwinOrganism, organ_id: str) -> tuple:
    """(línea principal, pie) de la tarjeta de un órgano, SOLO con entradas de la actualización actual. Cada número
    lleva su fuente: 🟢 NEWS2 para los puntos, «entrada: …» para lo medido/simulado. Sin dato -> («sin dato», ⚪)."""
    organ = organism.organs[organ_id]
    signals = organism.current_signals(organ_id)
    source = organism.input_provenance or "sin declarar"
    if organ_id == "heart":
        hr = signals.get("heart_rate")
        if hr is None:
            return NO_DATA, "⚪ sin FC actual"
        return f"FC {hr:.0f} lpm · NEWS2 pulso {organ.metrics.risk_points}/3", f"🟢 {PROVENANCE_SOURCE_NEWS2} · entrada: {source}"
    if organ_id == "lungs":
        rr, spo2 = signals.get("respiratory_rate"), signals.get("spo2")
        if rr is None and spo2 is None:
            return NO_DATA, "⚪ sin FR ni SpO₂ actuales"
        parts, pts = [], []
        if rr is not None:
            parts.append(f"FR {rr:.0f}")
            pts.append(f"FR {organ.metrics.rr_points}/3")
        if spo2 is not None:
            parts.append(f"SpO₂ {spo2:.0f} %")
            pts.append(f"SpO₂ {organ.metrics.spo2_points}/3")
        return " · ".join(parts) + " · NEWS2 " + " · ".join(pts), f"🟢 {PROVENANCE_SOURCE_NEWS2} · entrada: {source}"
    if organ_id == "brain":
        stress = signals.get("stress_level")
        bands = [k for k in signals if k.endswith("_power")]
        parts = []
        if stress is not None:
            parts.append(f"Estrés {stress:.0f}/100")
        if bands:
            parts.append(f"EEG: {len(bands)} bandas")
        if not parts:
            return NO_DATA, "⚪ sin EEG actual"
        return " · ".join(parts), f"entrada: {source} · sin criterio con fuente"
    if organ_id == "muscles":
        parts = [f"{label} {signals[k]:.0f}{unit}" for k, label, unit in (
            ("fatigue_index", "Fatiga", "/100"), ("activation", "Activación", " %"), ("median_frequency", "MDF", " Hz"),
        ) if signals.get(k) is not None]
        if not parts:
            return NO_DATA, "⚪ sin EMG actual"
        return " · ".join(parts), f"entrada: {source} · sin criterio con fuente"
    hrv = signals.get("hrv")
    if hrv is None:
        return NO_DATA, "⚪ sin HRV actual"
    return f"HRV {hrv:.0f} ms", f"entrada: {source} · la HRV como HRV, sin índice autonómico"


def render_organ_grid(organism: DigitalTwinOrganism) -> None:
    """Organ-click is the primary verb — this replaces the menu.

    Fase 1 (Art. I, decisión 5): el órgano sin dato dice «sin dato» en gris (el MISMO gris del Cuerpo Digital); nunca
    «50», «Alerta» ni «Óptimo». Fase 0: ningún órgano muestra un índice de salud/riesgo sin cita; corazón y pulmones
    muestran sus puntos NEWS2 y los demás, sus entradas como lo que son."""
    st.markdown("#### Toca un órgano para explorar su fisiología")
    cols = st.columns(len(ORGAN_ORDER))

    for col, organ_id in zip(cols, ORGAN_ORDER):
        organ = organism.organs[organ_id]
        selected = st.session_state.twin_shell_selected_organ == organ_id
        border = f"3px solid {organ.color}" if selected else "1px solid rgba(255,255,255,0.14)"
        line, foot = _card_lines(organism, organ_id)
        color = NO_DATA_COLOR if line == NO_DATA else organ.color
        with col:
            st.markdown(
                f"""
                <div style='text-align:center; padding: 16px 8px; border-radius: 18px; border: {border};
                            background: rgba(255,255,255,0.03);'>
                    <div style='font-size: 34px;'>{organ.icon}</div>
                    <div style='font-weight: 600; font-size: 12px; margin-top: 4px;'>{organ.name}</div>
                    <div style='font-size: 15px; color: {color}; font-weight: 700; margin-top: 6px;'>{line}</div>
                    <div style='font-size: 10px; color: #9fb4c9;'>{foot}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Explorar", key=f"twin_shell_select_{organ_id}", use_container_width=True):
                st.session_state.twin_shell_selected_organ = organ_id
                st.rerun()

    st.caption(
        f"{PROVENANCE_CLINICAL_BADGE} Corazón y Pulmones: puntos NEWS2 (RCP 2017) de pulso, FR y SpO₂ "
        "(escala 1; la escala 2 no se modela). Cerebro, Músculos y Autonómico: solo sus entradas, como lo que son — la "
        "plataforma no tiene un criterio con fuente que los puntúe (los índices de salud/riesgo sin cita se retiraron en "
        "la fase 0). Un órgano sin dato se muestra en gris como «sin dato»; nunca como «50» ni «Alerta»."
    )


def render_sensor_controls(organism: DigitalTwinOrganism) -> None:
    """Lets the shell be explored/demoed live without real hardware attached.

    Fase 1 (Art. I): el slider «Estrés (EEG)» alimenta SOLO lo que significa (`stress_level`, simulación). Fase 0
    (Parte D): el slider de fatiga ya no fabrica `efficiency = 100 − fatiga`; y si hay un escenario o una intervención
    activos (`INPUT_SOURCE_KEY`), los sliders NO se aplican en este rerun: se ve qué fuente manda y hay un botón
    explícito para volver a los sliders."""
    active = st.session_state.get(INPUT_SOURCE_KEY)
    with st.expander("🎛️ Ajustar señales fisiológicas (simulación)", expanded=bool(active)):
        if active:
            st.info(
                f"**Fuente activa: {active}.** Los sliders no se aplican mientras esta fuente esté activa; el organismo "
                "conserva los valores que ella fijó."
            )
            if st.button("↩️ Volver a los sliders", key="twin_shell_back_to_sliders", use_container_width=True):
                del st.session_state[INPUT_SOURCE_KEY]
                st.rerun()
        else:
            st.caption("Fuente activa: sliders de Twin OS (simulación).")
        col1, col2, col3 = st.columns(3)
        with col1:
            hr = st.slider("Frecuencia cardíaca (bpm)", 40, 180, 72, key="twin_shell_hr", disabled=bool(active))
            hrv = st.slider("HRV (ms)", 5, 120, 50, key="twin_shell_hrv", disabled=bool(active))
        with col2:
            rr = st.slider("Frecuencia respiratoria (resp/min)", 8, 40, 16, key="twin_shell_rr", disabled=bool(active))
            spo2 = st.slider("SpO₂ (%)", 70, 100, 98, key="twin_shell_spo2", disabled=bool(active))
        with col3:
            stress = st.slider("Estrés (EEG)", 0, 100, 35, key="twin_shell_stress", disabled=bool(active))
            fatigue = st.slider("Fatiga muscular (EMG)", 0, 100, 20, key="twin_shell_fatigue", disabled=bool(active))

        if active:
            return
        organism.input_provenance = "simulación: sliders de Twin OS"
        organism.update_from_sensors({
            "ecg": {"heart_rate": hr, "hrv": hrv},
            "eeg": {"stress_level": stress},
            "respiratory": {"respiratory_rate": rr, "spo2": spo2},
            "emg": {"fatigue_index": fatigue},
        })


def render_mode_toggle() -> None:
    """Mode is a toggle over the same organ-click, not a separate destination."""
    st.session_state.twin_shell_mode = st.radio(
        "Nivel de detalle",
        MODES,
        format_func=lambda m: MODE_LABELS[m],
        horizontal=True,
        index=MODES.index(st.session_state.twin_shell_mode),
        label_visibility="collapsed",
    )


def _organ_related_findings(organism: DigitalTwinOrganism, organ_id: str) -> list:
    keywords = ORGAN_KEYWORDS.get(organ_id, [])
    findings = []
    for alert in organism.global_state.get("alerts", []) + organism.global_state.get("anomalies", []):
        if any(k.lower() in alert.lower() for k in keywords):
            findings.append(alert)
    return findings


_NEWS2_PULSE_HELP = (
    f"{PROVENANCE_CLINICAL_BADGE} Puntos NEWS2 del pulso (RCP 2017): ≤40 → 3; 41–50 → 1; 51–90 → 0; 91–110 → 1; "
    "111–130 → 2; ≥131 → 3. Es UN componente de un puntaje (no un diagnóstico) y su única entrada es la FC."
)
_NEWS2_RR_HELP = (
    f"{PROVENANCE_CLINICAL_BADGE} Puntos NEWS2 de la FR (RCP 2017): ≤8 → 3; 9–11 → 1; 12–20 → 0; 21–24 → 2; ≥25 → 3. "
    "Un componente del puntaje; su única entrada es la FR (redondeada, .5 hacia arriba)."
)
_NEWS2_SPO2_HELP = (
    f"{PROVENANCE_CLINICAL_BADGE} Puntos NEWS2 de la SpO₂, escala 1 (RCP 2017): ≤91 → 3; 92–93 → 2; 94–95 → 1; ≥96 → 0. "
    "La escala 2 (insuficiencia respiratoria hipercápnica) exige saber si hay oxígeno suplementario: no modelada."
)
_LUNG_HEALTH_HELP = (
    f"{PROVENANCE_HEURISTIC_BADGE} Índice de salud pulmonar: centros de referencia FR 16 y SpO₂ 100 %, AHI 30 = 100 %; los "
    f"pesos 0.5/0.3/0.4 son propios ({PROVENANCE_HEURISTIC_LABEL}). Solo se calcula con FR, SpO₂ y AHI, los tres actuales."
)
_NO_CRITERION_HELP = (
    "Sin criterio con fuente: la plataforma no tiene una escala publicada que puntúe este sistema; los índices propios "
    "sin cita se retiraron (fase 0). Lo medido se muestra como lo que es."
)


def _metric_value(value, fmt: str, unit: str = "") -> str:
    return NO_DATA if value is None else f"{value:{fmt}}{unit}"


def _points_value(points) -> str:
    return NO_DATA if points is None else f"{points} de 3"


def _render_signals(organism: DigitalTwinOrganism, organ_id: str, mode: str) -> None:
    signals = organism.current_signals(organ_id)
    st.markdown("**Señales de entrada:**" if mode == "Clinician" else "**Señales crudas:**")
    if signals:
        st.json(signals)
        st.caption(f"Procedencia de las entradas: {organism.input_provenance or 'sin declarar'}")
    else:
        st.caption(NO_DATA)


def render_organ_panel(organism: DigitalTwinOrganism) -> None:
    """Panel del órgano seleccionado. Fase 0: solo entradas actuales (con su procedencia) y componentes NEWS2 (con su
    cita); el único índice que sobrevive es el de salud pulmonar (🔵, con FR + SpO₂ + AHI). Lo que nadie calcula dice
    «no modelado»; lo que no llegó dice «sin dato»."""
    organ_id = st.session_state.twin_shell_selected_organ
    organ = organism.organs[organ_id]
    m = organ.metrics
    signals = organism.current_signals(organ_id)

    st.markdown(f"## {organ.icon} {organ.name}")
    render_mode_toggle()
    mode = st.session_state.twin_shell_mode
    entrada = _entrada(organism)

    if mode == "Student":
        st.info(organ.education.get("es", "Sin explicación disponible."))
    elif mode == "Clinician":
        st.info(organ.education.get("pathophysiology", ""))

    if organ_id == "heart":
        hr = signals.get("heart_rate")
        points = m.risk_points if hr is not None else None
        cols = st.columns(4 if mode == "Researcher" else 3)
        cols[0].metric("Frecuencia cardíaca", _metric_value(hr, ".0f", " lpm"), help=entrada)
        cols[1].metric("🟢 Puntos NEWS2 del pulso", _points_value(points), help=_NEWS2_PULSE_HELP)
        cols[2].metric("Gasto cardíaco", NOT_MODELED, help="Ningún cálculo del gemelo lo modela (decisión firmada).")
        if mode == "Researcher":
            cols[3].metric("HRV", _metric_value(signals.get("hrv"), ".0f", " ms"), help=entrada)
            st.markdown("**Parámetros de alta fidelidad:**")
            st.caption(
                f"{NOT_MODELED}: se eliminó `CardiacDetail` (10 campos que ningún cálculo asignaba: gasto, volumen "
                "sistólico, intervalos QRS/PR/QT, fracción de eyección...). Solo se muestra lo que alguien calcula de "
                "verdad, con su procedencia."
            )
    elif organ_id == "lungs":
        rr, spo2 = signals.get("respiratory_rate"), signals.get("spo2")
        cols = st.columns(4)
        cols[0].metric("Frecuencia respiratoria", _metric_value(rr, ".0f", " resp/min"), help=entrada)
        cols[1].metric("SpO₂", _metric_value(spo2, ".0f", " %"), help=entrada)
        cols[2].metric("🟢 NEWS2 FR", _points_value(m.rr_points if rr is not None else None), help=_NEWS2_RR_HELP)
        cols[3].metric("🟢 NEWS2 SpO₂ (escala 1)", _points_value(m.spo2_points if spo2 is not None else None), help=_NEWS2_SPO2_HELP)
        if mode != "Student":
            cols = st.columns(3)
            cols[0].metric("AHI", _metric_value(signals.get("ahi"), ".0f", " eventos/h"), help=entrada)
            cols[1].metric(
                "🔵 Índice de salud pulmonar",
                NO_DATA if m.health_score is None else f"{m.health_score:.0f}/100",
                help=_LUNG_HEALTH_HELP + ("" if m.health_score is not None else " Hoy: sin dato (falta el AHI)."),
            )
            cols[2].metric("SpO₂ escala 2", NOT_MODELED, help="Exige saber si el paciente recibe oxígeno suplementario.")
    elif organ_id == "brain":
        stress = signals.get("stress_level")
        bands = {k: v for k, v in signals.items() if k.endswith("_power")}
        cols = st.columns(3)
        cols[0].metric("Estrés (entrada)", _metric_value(stress, ".0f", "/100"), help=entrada)
        cols[1].metric("Potencias de banda EEG", NO_DATA if not bands else f"{len(bands)} bandas", help=entrada)
        cols[2].metric("Índice de salud / riesgo", "retirado", help=_NO_CRITERION_HELP)
    elif organ_id == "muscles":
        cols = st.columns(4)
        cols[0].metric("Índice de fatiga (entrada)", _metric_value(signals.get("fatigue_index"), ".0f", "/100"), help=entrada)
        cols[1].metric("Activación", _metric_value(signals.get("activation"), ".1f", " %"), help=entrada)
        cols[2].metric("Frecuencia mediana EMG", _metric_value(signals.get("median_frequency"), ".1f", " Hz"), help=entrada)
        cols[3].metric("Índice de salud / riesgo", "retirado", help=_NO_CRITERION_HELP)
    else:
        cols = st.columns(3)
        cols[0].metric("HRV", _metric_value(signals.get("hrv"), ".0f", " ms"), help=f"{entrada} (la HRV del corazón, como HRV)")
        cols[1].metric("Balance simpático/parasimpático", NOT_MODELED, help="Ninguna fórmula con fuente lo calcula.")
        cols[2].metric("Índice autonómico", "retirado", help=_NO_CRITERION_HELP + " Umbrales HRV < 15/30 retirados.")

    if mode != "Student":
        _render_signals(organism, organ_id, mode)
        if mode == "Researcher" and organ.pathologies:
            st.caption("Patologías relacionadas: " + ", ".join(organ.pathologies))

    # AI explanation surfaces directly on the organ, not in a separate chat panel.
    findings = _organ_related_findings(organism, organ_id)
    if findings:
        st.markdown("**🧠 Hallazgos relevantes para este órgano:**")
        for f in findings:
            st.error(f) if "⚠️" in f or "🔴" in f else st.info(f)


def render_couplings(organism: DigitalTwinOrganism) -> None:
    """Corazón↔Pulmones como razón FC:FR, número descriptivo (fase 0, decisión 3 de Luis); sin índice 0-100 %. La
    referencia en reposo (≈4:1) se muestra porque se verificó con texto completo (Scholkmann & Wolf 2019, ver
    `clinical.calculators.PRQ_REFERENCE`). Retirados (decisión 1): Cerebro↔Corazón y Cerebro↔Músculos (fórmulas
    inventadas; el acoplamiento neuro→cardiaco con fuente vive en `domain/physiology/coupling/`)."""
    ratio = organism.global_state.get("hr_rr_ratio")
    st.markdown("#### 🔗 Corazón ↔ Pulmones: razón FC:FR")
    st.metric(
        "Razón FC:FR", NO_DATA if ratio is None else f"{ratio:.1f} : 1",
        help=(
            f"{PROVENANCE_CLINICAL_BADGE} Referencia en reposo (PRQ): {PRQ_REST_REFERENCE_TEXT} — {PRQ_REFERENCE}. "
            "Número descriptivo: no es un índice de acoplamiento ni un porcentaje. "
            + (_entrada(organism) if ratio is not None else "Necesita FC y FR, ambas actuales.")
        ),
    )


def render_neuro_cardiac_composer() -> None:
    """Acoplamientos (b) Tanda 2 (2026-09-08): botón 3a -- el disparador de
    usuario del acoplamiento neuro->CV en el flujo del paciente único.

    Opt-in deliberado: el estudiante elige unir el BAR guardado (EEG Lab)
    con la FC medida guardada (ECG/HRV/Twin OS) en un snapshot combinado, y
    evaluar la regla validada `AROUSAL_TAQUICARDIA_BAR` (Guyton 14a cap.61 +
    Schutter 2006) sobre él. `compose_neuro_cardiac_snapshot()` compone
    valores REALES o declara por qué no puede -- nunca finge. Los tres
    desenlaces se muestran honestamente; un "no disponible" es información
    pedagógica ("aún no guardaste un EEG para este paciente"), no un fallo a
    esconder."""
    session_factory = get_active_session_factory()
    patient_id = get_active_patient_id()

    st.markdown("#### 🔗 Evaluar acoplamiento neuro-cardíaco (BAR → FC)")
    st.caption(
        "Une la última medición **neurológica** guardada (el BAR, Ratio Beta/Alfa del EEG Lab, "
        "una medida de activación cortical) con la última **frecuencia cardíaca medida** guardada "
        "(ECG/HRV/este panel) en un mismo momento, y evalúa la regla validada arousal→↑FC "
        "(`AROUSAL_TAQUICARDIA_BAR`: si el BAR pasa de 1.8, la FC sube +15 bpm; Guyton 14ª ed. "
        "cap.61 + Schutter 2006). **La FC no se vuelve a medir: se reutiliza la última lectura "
        "guardada**, indicando de qué momento viene y cuántos segundos hace. Si la activación no "
        "lo justifica (BAR ≤ 1.8), o esa FC previa es más vieja que la ventana (120 s, para no "
        "unir dos momentos sin relación), se explica por qué — no se fuerza un acoplamiento."
    )
    if st.button("Componer y evaluar", key="twin_shell_neuro_cardiac_compose"):
        with session_factory() as session:
            result = compose_neuro_cardiac_snapshot(session, patient_id)

        if not result.available:
            st.info(f"No se pudo componer: {result.reason}")
            return

        st.success(f"Estado combinado compuesto — snapshot: `{result.snapshot_id}`")
        if result.coupled:
            ac = result.coupled[0]
            st.caption(
                f"🔗 La regla **{ac.rule_id}** disparó: una FC previa de {ac.base_value:.0f} bpm "
                f"(medida hace {result.hr_age_s:.0f} s, reutilizada) → **FC acoplada "
                f"{ac.coupled_value:.0f} bpm** — un valor **calculado por la regla, no medido por "
                f"un sensor** (confianza {ac.confidence:.2f}). Disparo: BAR = {ac.observed_value:.2f} "
                "(> 1.8). Las tres cantidades conviven en el snapshot, cada una diciendo de dónde "
                "viene: el BAR es una medición neurológica real; la FC previa es una lectura "
                "cardíaca reutilizada (no se midió ahora); la FC acoplada la calcula la regla. "
                "Nombres internos de esas procedencias: `simulacion` · `arrastre_temporal` · "
                "`derivado_acoplamiento`."
            )
        else:
            st.caption(
                "Compuesto, **sin acoplamiento**: la activación cortical (BAR) no supera el umbral "
                f"(> 1.8). La medición neurológica y la FC previa (de hace {result.hr_age_s:.0f} s) "
                "conviven en el snapshot, pero la regla no disparó — no se fuerza un acoplamiento "
                "donde la activación no lo justifica."
            )


def render_scenario_and_interventions(organism: DigitalTwinOrganism) -> None:
    """Patient presets + simulated interventions — folded in from Digital Twin Profesional.

    Fase 5.2 (clarificar nombres, 2026-08-30): esta función muta `organism` en memoria al instante (sin `save_state`);
    el simulador SÍ persiste una trayectoria de 6 horizontes al UPS. Fase 0 (Parte D): cada botón declara su fuente en
    `INPUT_SOURCE_KEY`, así los sliders no sobrescriben el escenario en el siguiente rerun (ver
    `render_sensor_controls`)."""
    with st.expander("⚡ Ajustes rápidos e intervenciones (en memoria, sin persistir)"):
        st.markdown("**Preset rápido:**")
        scenarios = {
            "healthy": "🟢 Sano", "hypertension": "🟡 Hipertensión",
            "copd": "🔴 EPOC",
        }
        cols = st.columns(len(scenarios))
        for col, (key, label) in zip(cols, scenarios.items()):
            with col:
                if st.button(label, key=f"twin_shell_scenario_{key}", use_container_width=True):
                    organism.create_patient_scenario(key)
                    _set_input_source(f"preset {label}")
                    st.rerun()

        st.markdown("**Sepsis (punto de la trayectoria canónica):**")
        sep_col1, sep_col2 = st.columns([3, 2])
        sepsis_horizon = sep_col1.selectbox(
            "Horizonte", list(sepsis_trajectory.HORIZON_PHASES),
            format_func=lambda h: f"{h} — {sepsis_trajectory.phase_of(h)}",
            key="twin_shell_sepsis_horizon", label_visibility="collapsed",
        )
        if sep_col2.button("Aplicar punto", key="twin_shell_sepsis_apply", use_container_width=True):
            st.session_state.twin_shell_sepsis_declaration = organism.apply_sepsis(sepsis_horizon)
            _set_input_source(f"sepsis, horizonte {sepsis_horizon} (trayectoria canónica)")
            st.rerun()
        if st.session_state.get("twin_shell_sepsis_declaration"):
            st.info(st.session_state.twin_shell_sepsis_declaration)

        st.markdown("**Arritmia (tipo específico, fuente única):**")
        arr_col1, arr_col2, arr_col3 = st.columns([3, 1, 2])
        arrhythmia_key = arr_col1.selectbox(
            "Tipo", list(ARRHYTHMIA_TYPES), format_func=lambda k: ARRHYTHMIA_TYPES[k].label,
            key="twin_shell_arrhythmia_type", label_visibility="collapsed",
        )
        arrhythmia_seed = int(arr_col2.number_input(
            "Semilla", min_value=0, value=0, step=1, key="twin_shell_arrhythmia_seed",
            help="Fija la instancia dentro del rango declarado del tipo; otra semilla, otra instancia.",
        ))
        if arr_col3.button("Aplicar tipo", key="twin_shell_arrhythmia_apply", use_container_width=True):
            st.session_state.twin_shell_arrhythmia_declaration = organism.apply_arrhythmia(arrhythmia_key, arrhythmia_seed)
            _set_input_source(f"arritmia {ARRHYTHMIA_TYPES[arrhythmia_key].label} (semilla {arrhythmia_seed})")
            st.rerun()
        if st.session_state.get("twin_shell_arrhythmia_declaration"):
            st.info(st.session_state.twin_shell_arrhythmia_declaration)

        st.markdown("**Intervenciones simuladas:**")
        interventions = [
            ("🫁 Oxígeno", "oxygen", 0.7), ("💤 Sedación", "sedation", 0.6),
            ("🏃 Ejercicio", "exercise", 0.7), ("😴 Descanso", "rest", 0.8),
        ]
        cols2 = st.columns(len(interventions))
        for col, (label, key, intensity) in zip(cols2, interventions):
            with col:
                if st.button(label, key=f"twin_shell_int_{key}", use_container_width=True):
                    organism.simulate_intervention(key, intensity)
                    _set_input_source(f"intervención {label} (sobre el estado previo)")
                    st.rerun()


RICH_SCENARIO_LABELS = {
    SimulationScenario.HEALTHY: "🟢 Sano — línea base",
    SimulationScenario.EXERCISE: "🏃 Ejercicio",
    SimulationScenario.STRESS: "😰 Estrés psicológico",
    SimulationScenario.ANXIETY: "😨 Crisis de ansiedad",
    SimulationScenario.ARRHYTHMIA_AFIB: "🫀 Fibrilación auricular",
    SimulationScenario.ARRHYTHMIA_AFLUTTER: "🫀 Flutter auricular 2:1",
    SimulationScenario.ARRHYTHMIA_SVT: "🫀 Taquicardia supraventricular",
    SimulationScenario.ARRHYTHMIA_SBRADY: "🫀 Bradicardia sinusal",
    SimulationScenario.HYPOXIA: "💨 Hipoxia progresiva",
    SimulationScenario.APNEA: "😴 Apnea del sueño",
    SimulationScenario.FATIGUE: "🥱 Fatiga crónica",
    SimulationScenario.SEIZURE: "⚡ Crisis convulsiva",
    SimulationScenario.SEPSIS: "🆘 Sepsis",
    SimulationScenario.COPD: "🫁 EPOC",
    SimulationScenario.HYPERTENSION: "🩺 Hipertensión",
}

_PLATEAU_TOLERANCE = 0.01  # los escenarios que se aplanan (stress/hypoxia/sepsis, ver
# SimulationEngine._simulate_*) usan `min(1.0, minutes/X)` sin ruido gaussiano -- una vez
# capado, los horizontes largos dan el MISMO float, no uno "parecido"; la tolerancia es
# solo por seguridad de punto flotante, no porque el aplanado sea aproximado.


def _tail_is_plateaued(values: list, tail_len: int = 2) -> bool:
    """True si una serie de horizontes (now/5min/30min/2h/24h/7d, en orden)
    se movió en algún punto y luego se quedó fija en sus últimos `tail_len`
    valores -- no si simplemente fue constante desde el principio.

    Genérico, no una lista de escenarios hardcodeada: no sabe qué escenario
    produjo la serie, solo compara la cola contra el rango completo de la
    serie. Esa segunda condición (rango > 0) es la que separa un aplanado
    real -- el patrón de `_simulate_stress/_simulate_hypoxia/_simulate_sepsis`,
    cuyo `min(1.0, minutes/X)` se satura tras arrancar de un valor distinto
    -- de una FOTO constante por diseño (`_simulate_apnea`, `_simulate_copd`,
    `_simulate_hypertension`: los 6 horizontes son el mismo valor desde
    `now`, no un aplanado, ver CHANGELOG.md 2026-08-12); sin ella, esta
    función marcaría por igual ambos casos, que no son el mismo problema."""
    if len(values) < tail_len:
        return False
    tail = values[-tail_len:]
    if any(v is None for v in tail):
        return False
    tail_is_flat = (max(tail) - min(tail)) <= _PLATEAU_TOLERANCE
    if not tail_is_flat:
        return False
    clean_values = [v for v in values if v is not None]
    return (max(clean_values) - min(clean_values)) > _PLATEAU_TOLERANCE


def render_ups_scenario_simulator(organism: DigitalTwinOrganism) -> None:
    """Fase 1.2 + Tanda 3 (2026-07-03): simulador único conectado al UPS.

    Antes ofrecía 3 trayectorias hechas a mano
    (`domain/physiology/scenarios/definitions.py` — sin tocar, sigue
    existiendo y cubierta por `tests/test_scenario_simulator.py`, ya no
    expuesta en esta UI). Ahora los 15 escenarios reales de
    `SimulationEngine` (antes aislados en `render_simulation_lab`, sin
    persistencia — eliminada, 100% subsumida por esta función) alimentan el
    mismo pipeline de siempre — `organism.update_from_sensors` →
    `from_digital_twin_organism` → `save_state` — vía
    `domain.physiology.scenarios.rich_engine.run_rich_scenario`, un puente
    nuevo que no modifica ninguna función ya verificada del núcleo.

    Toggle estado actual/basal: "estado actual" arranca de las señales
    reales del organismo (continuidad, el narrador compara antes→ahora con
    historial genuino); "basal" crea un paciente efímero nuevo
    (`create_ephemeral_basal_patient`) para garantizar que el narrador no
    compare el caso típico contra un 'antes' ajeno — sin historial previo
    para ese paciente, `before_value` es `None` por construcción, no por
    ocultarlo."""

    with st.expander("🧬 Simulador de escenarios clínicos (persistido en el UPS)"):
        st.caption(
            "Los 15 escenarios reales de SimulationEngine persisten paso a paso en el Unified "
            "Physiological State — siempre etiquetados como simulación."
        )

        if "twin_shell_ups_canonical_patient_id" not in st.session_state:
            st.session_state.twin_shell_ups_canonical_patient_id = get_active_patient_id()

        scenario_key = st.selectbox(
            "Escenario clínico:",
            list(RICH_SCENARIO_LABELS.keys()),
            format_func=lambda s: RICH_SCENARIO_LABELS[s],
            key="twin_shell_rich_scenario_select",
        )
        arrhythmia_seed = 0
        if scenario_key in ARRHYTHMIA_SCENARIO_TYPE or scenario_key == SimulationScenario.HEALTHY:
            # Variabilidad DECLARADA (Unificación 1 arritmia, 4 sano): rango, semilla y valores de la instancia a la vista.
            arrhythmia_seed = int(st.number_input(
                "Semilla de la instancia", min_value=0, value=0, step=1, key="twin_shell_rich_arrhythmia_seed",
                help="Fija la instancia dentro del rango declarado; otra semilla, otra instancia.",
            ))
            st.info(SimulationEngine(seed=arrhythmia_seed).instance_declaration(scenario_key))
        if scenario_key == SimulationScenario.SEPSIS:
            st.info(sepsis_trajectory.declare_trajectory())
        start_mode = st.radio(
            "Punto de partida:",
            ["Estado actual del paciente", "Basal genérica (caso didáctico)"],
            horizontal=True,
            key="twin_shell_rich_scenario_mode",
        )
        start_from_current = start_mode == "Estado actual del paciente"
        st.caption(
            "**Estado actual:** el escenario continúa desde el organismo vigente — el narrador "
            "podrá comparar antes→ahora. **Basal:** arranca de un caso didáctico limpio, con un "
            "paciente efímero nuevo, sin historial previo que mezclar."
        )

        if get_active_patient_id() != st.session_state.twin_shell_ups_canonical_patient_id:
            st.info("Estás viendo un caso didáctico basal — el narrador y el cuerpo narran ese caso, no al paciente continuo.")
            if st.button("🔙 Volver al paciente continuo", key="twin_shell_back_to_canonical"):
                set_active_patient_id(st.session_state.twin_shell_ups_canonical_patient_id)
                st.rerun()

        if st.button("▶️ Ejecutar y persistir en el UPS", key="twin_shell_ups_run"):
            session_factory = get_active_session_factory()

            with session_factory() as session:
                if start_from_current:
                    patient_id = get_active_patient_id()
                else:
                    patient_id = create_ephemeral_basal_patient(session, scenario_key)
                    # Sustitución TEMPORAL y deliberada del paciente activo --
                    # ver docstring de `set_active_patient_id()` (Fase 3,
                    # app/utils/patient_session.py). El botón "Volver al
                    # paciente continuo" de arriba la deshace.
                    set_active_patient_id(patient_id)

                progress_bar = st.progress(0.0)
                chart_placeholder = st.empty()
                body_placeholder = st.empty()
                hr_trajectory: list = []
                spo2_trajectory: list = []
                total_steps = 1

                for step in run_rich_scenario(session, patient_id, scenario_key, organism, start_from_current, seed=arrhythmia_seed):
                    hr_val = step.state.all_domains()["cardiovascular"].get("heart_rate")
                    spo2_val = step.state.all_domains()["respiratory"].get("spo2")
                    hr_trajectory.append(hr_val.value if hr_val is not None else None)
                    spo2_trajectory.append(spo2_val.value if spo2_val is not None else None)
                    total_steps = step.total_steps
                    progress_bar.progress((step.index + 1) / step.total_steps)
                    chart_placeholder.line_chart(
                        pd.DataFrame({"FC (bpm)": hr_trajectory, "SpO₂ (%)": spo2_trajectory}),
                        use_container_width=True,
                    )
                    # Fase 1.4: el cuerpo se actualiza con el mismo `step.state` que se
                    # acaba de persistir — no relee el organismo ni el texto del narrador.
                    with body_placeholder.container():
                        render_ups_body(step.state)
                    time.sleep(0.12)

                # Conexión al UPS (2026-08-01): PA calculada por el lazo cerrado, SOLO para
                # los 3 escenarios con validación experta completa
                # (HEMODYNAMIC_MODEL_ENABLED_SCENARIOS) -- restricción estructural, no un
                # `if` evitable: compute_and_attach_closed_loop_pressure() lanza
                # HemodynamicModelNotEnabledError para cualquier otro escenario. Se adjunta
                # al MISMO último snapshot que ya tiene la ClinicalReferenceValue (si
                # existe) -- coexisten, ninguna sobrescribe a la otra.
                st.session_state.twin_shell_last_closed_loop_error = None
                if scenario_key.value in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS:
                    latest_state = get_latest_state(session, patient_id)
                    hr_descriptor = latest_state.cardiovascular.get("heart_rate") if latest_state else None
                    snapshot_id = get_latest_snapshot_id(session, patient_id)
                    if hr_descriptor is not None and snapshot_id is not None:
                        try:
                            compute_and_attach_closed_loop_pressure(
                                session,
                                snapshot_id=snapshot_id,
                                scenario=scenario_key.value,
                                heart_rate_bpm=hr_descriptor.value,
                                source_detail=f"twin_shell_scenario_simulator:{scenario_key.value}",
                            )
                        except HemodynamicModelNotEnabledError:
                            pass  # no debería ocurrir dado el filtro de arriba -- defensivo, no silencia un bug real
                        except Exception as exc:  # el lazo cerrado es estable en todo el rango de HR, pero no crashear la UI si algo inesperado pasa
                            st.session_state.twin_shell_last_closed_loop_error = str(exc)

            st.session_state.twin_shell_last_ups_scenario = scenario_key
            st.session_state.twin_shell_last_ups_mode = "estado_actual" if start_from_current else "basal"
            mode_txt = "continuando desde el estado actual" if start_from_current else "caso didáctico basal (paciente nuevo)"
            st.success(f"{total_steps} snapshots persistidos en el UPS para '{RICH_SCENARIO_LABELS[scenario_key]}' ({mode_txt}).")
            _set_input_source(f"escenario del simulador {RICH_SCENARIO_LABELS[scenario_key]} (último horizonte)")
            st.rerun()

        last_scenario = st.session_state.get("twin_shell_last_ups_scenario")
        if last_scenario:
            last_mode = st.session_state.get("twin_shell_last_ups_mode", "estado_actual")
            st.markdown(
                f"**Última trayectoria persistida:** {RICH_SCENARIO_LABELS.get(last_scenario, last_scenario)} "
                f"({'estado actual' if last_mode == 'estado_actual' else 'basal'})"
            )
            session_factory = get_active_session_factory()
            patient_id = get_active_patient_id()

            with session_factory() as session:
                hr_history = get_value_history(session, patient_id, "cardiovascular", "heart_rate")
                spo2_history = get_value_history(session, patient_id, "respiratory", "spo2")
                events = get_events(session, patient_id)
                latest_for_pa = get_latest_state(session, patient_id)
                references_for_pa = [
                    r for r in get_clinical_references_for_patient(session, patient_id)
                    if r.scenario == getattr(last_scenario, "value", last_scenario)
                ]

            closed_loop_error = st.session_state.get("twin_shell_last_closed_loop_error")
            if closed_loop_error:
                st.warning(f"No se pudo calcular la PA del lazo cerrado para este escenario: {closed_loop_error}")
            elif latest_for_pa is not None and latest_for_pa.cardiovascular.get("map_modelo") is not None:
                systolic_modelo = latest_for_pa.cardiovascular.get("systolic_bp_modelo")
                diastolic_modelo = latest_for_pa.cardiovascular.get("diastolic_bp_modelo")
                map_modelo = latest_for_pa.cardiovascular.get("map_modelo")
                ref_by_descriptor = {r.descriptor: r for r in references_for_pa}
                ref_map = ref_by_descriptor.get("map")
                st.markdown(
                    f"**🧮 PA calculada por el modelo hemodinámico ({pa_model_label()}):** "
                    f"{systolic_modelo.value:.0f}/{diastolic_modelo.value:.0f} mmHg "
                    f"(PAM {map_modelo.value:.0f} mmHg, confianza {map_modelo.confidence:.0%})"
                    + (f" — referencia clínica citada: PAM {ref_map.value:.0f} mmHg" if ref_map else "")
                )
                st.caption(
                    "Valor CALCULADO por el modelo de lazo cerrado a partir del heart_rate real de este "
                    "escenario -- no es una medición del paciente ni reemplaza la referencia clínica citada "
                    "(si aparece arriba); son dos fuentes distintas que coexisten en el mismo snapshot, útil "
                    "para comparar 'lo que predice el modelo' contra 'lo que dice la literatura'. Solo "
                    "disponible para sano/hipertensión/sepsis -- los 3 escenarios con validación experta "
                    "completa del motor hemodinámico."
                )

            if hr_history and spo2_history and len(hr_history) == len(spo2_history):
                moments = [ts.strftime("%H:%M:%S") for ts, _ in hr_history]
                hr_values = [v for _, v in hr_history]
                spo2_values = [v for _, v in spo2_history]
                df = pd.DataFrame({
                    "Momento": moments,
                    "FC (bpm)": hr_values,
                    "SpO₂ (%)": spo2_values,
                })
                st.line_chart(df.set_index("Momento"), use_container_width=True)
                st.caption(f"{len(moments)} snapshots consultados desde el UPS (SQLite) — no desde session_state.")
                if _tail_is_plateaued(hr_values) or _tail_is_plateaued(spo2_values):
                    st.info(
                        "📐 **Los últimos horizontes de esta trayectoria son idénticos.** El "
                        "simulador alcanzó su techo de progresión y dejó de evolucionar a partir "
                        "de ahí -- modela la fisiología aguda, no la evolución clínica con "
                        "tratamiento a lo largo de días. Esta meseta es la persistencia del estado "
                        "agudo tal como lo calcula el modelo, no un pronóstico de que el paciente "
                        "se mantendrá así."
                    )
            elif hr_history or spo2_history:
                series = hr_history or spo2_history
                label = "FC (bpm)" if hr_history else "SpO₂ (%)"
                series_values = [v for _, v in series]
                df = pd.DataFrame({
                    "Momento": [ts.strftime("%H:%M:%S") for ts, _ in series],
                    label: series_values,
                })
                st.line_chart(df.set_index("Momento"), use_container_width=True)
                if _tail_is_plateaued(series_values):
                    st.info(
                        "📐 **Los últimos horizontes de esta trayectoria son idénticos.** El "
                        "simulador alcanzó su techo de progresión y dejó de evolucionar a partir "
                        "de ahí -- modela la fisiología aguda, no la evolución clínica con "
                        "tratamiento a lo largo de días. Esta meseta es la persistencia del estado "
                        "agudo tal como lo calcula el modelo, no un pronóstico de que el paciente "
                        "se mantendrá así."
                    )

            if events:
                st.markdown("**Eventos detectados y persistidos:**")
                for evt in events[-10:]:
                    icon = "🔴" if evt.severity == EventSeverity.CRITICAL else "🟡"
                    st.caption(f"{icon} `{evt.event_type.value}` — {evt.description} ({evt.timestamp.strftime('%H:%M:%S')})")


def render_synced_digital_twin_body(organism: DigitalTwinOrganism) -> None:
    """Fase 1.4: cuerpo visual (SVG) del organismo — cierre de la Fase 1.
    Corazón y pulmones (los dos únicos dominios que el UPS modela) cambian
    de color/animación según la severidad de eventos y los descriptores del
    estado fisiológico.

    Fase 5.1 (punto único de verdad, 2026-08-30): antes leía pasivamente el
    último snapshot PERSISTIDO (`get_latest_state`) — así que mover un
    slider actualizaba las tarjetas de órgano al instante (leen `organism`
    en memoria) pero dejaba este cuerpo mostrando el estado de hace varios
    clics, hasta pulsar el botón de abajo. Ahora lee el estado ACTUAL en
    memoria (`get_current_physiological_state()`, mismo análogo que
    `get_active_patient_id()` de la Fase 3) — se actualiza en cada rerun,
    igual que el resto del panel. Ningún otro comportamiento cambia: sigue
    sin leer el texto del narrador (dos lectores independientes de la
    misma verdad fisiológica, ver `ups_body_visual.py`), y el botón de
    abajo sigue persistiendo al UPS exactamente igual que antes — solo que
    su propósito ya no es "ponerse al día" (el cuerpo ya está al día por
    construcción), sino crear un checkpoint permanente en la trayectoria
    del paciente."""

    session_factory = get_active_session_factory()
    patient_id = get_active_patient_id()

    st.markdown("### 🫀 Cuerpo Digital — tu estado actual")

    if st.button("💾 Guardar este momento en la historia del paciente", key="twin_shell_body_sync"):
        with session_factory() as session:
            persist_current_state(session, organism, patient_id, source_detail="twin_visual:checkpoint_manual")
        st.success("Momento guardado en la trayectoria del paciente.")

    # Pieza 2 (2026-10-22): un solo `state` alimenta el cuerpo SVG y el 3D.
    render_ups_body(get_current_physiological_state(organism, patient_id), with_3d=True, key="twin_actual")
    st.caption(
        "Color y animación se derivan de tu estado fisiológico ACTUAL (severidad de eventos por "
        "dominio + heart_rate/respiratory_rate/spo2 en memoria ahora mismo) — nunca del texto del "
        "narrador. Se actualiza solo mientras tengas esta página abierta; para conservarlo en la "
        "trayectoria permanente del paciente, usa el botón de arriba."
    )


NARRATOR_DEPTH_LABELS = {
    DepthLevel.ESTUDIANTE: "🎓 Estudiante",
    DepthLevel.RESIDENTE: "🩺 Residente",
    DepthLevel.EXPERTO: "🔬 Experto",
}


def render_clinical_narrator(organism: DigitalTwinOrganism) -> None:
    """Fase 1.3: narrador clínico en tiempo real — primera integración real
    de IA del proyecto (API de Anthropic, streaming). Refunde `app/ai_copilot.py`
    (JARVIS, muerto/sin uso) y `app/biomedical_tutor.py` (diccionario de
    keywords), ambos eliminados — este es el único punto de IA del proyecto.

    Antes de narrar, persiste un snapshot fresco del organismo actual en el
    UPS: así "si modifico el UPS, la narración cambia" es literal — mover un
    slider o cargar un escenario y volver a pulsar el botón produce un
    contexto distinto, porque `build_context()` siempre lee el snapshot que
    se acaba de guardar, nunca texto compuesto a mano."""

    with st.expander("🩺 Narrador clínico (IA real) — Fase 1.3", expanded=False):
        if not narrator_is_configured():
            st.warning(
                "`ANTHROPIC_API_KEY` no está configurada en el entorno. El narrador llama a la "
                "API real de Anthropic con streaming — no existe una narración simulada de "
                "respaldo. " + AI_KEY_HINT
            )
            return

        st.caption(
            "Lee el estado actual del UPS (descriptores con procedencia/confianza, eventos, "
            "comparación antes/ahora) y genera una explicación en streaming fundamentada en "
            "esos datos — no es un chat de propósito general."
        )

        depth = st.radio(
            "Profundidad",
            list(DepthLevel),
            format_func=lambda d: NARRATOR_DEPTH_LABELS[d],
            horizontal=True,
            key="twin_shell_narrator_depth",
        )

        if st.button("🗣️ Explicar estado actual", key="twin_shell_narrator_run"):
            session_factory = get_active_session_factory()
            patient_id = get_active_patient_id()

            with session_factory() as session:
                persist_current_state(session, organism, patient_id, source_detail="narrador:snapshot_bajo_demanda")
                context = build_context(session, patient_id)

            st.caption(
                f"Basado en {len(context.descriptors)} descriptores y {len(context.events)} "
                f"eventos del UPS, generados en {context.generated_at}."
            )
            try:
                st.write_stream(stream_narration(context, depth, client=ai_client()))
            except NarratorNotConfiguredError as exc:
                render_error_state(str(exc))
            except Exception as exc:  # llamada real a la API — puede fallar por red/cuota/etc.
                # Fase 2.3 Tanda 3 (2026-08-29): mismo patrón que
                # render_findings_narrator() en app/main.py -- antes exponía
                # `{exc}` crudo (puede incluir detalle interno de la
                # respuesta HTTP de la API).
                render_error_state(
                    "No se pudo completar la narración -- la llamada a la API de Anthropic falló "
                    "(red o cuota). Intenta de nuevo en unos segundos.",
                    exception=exc,
                )


def _dedupe_events(events: list) -> list:
    """Colapsa eventos idénticos (mismo `event_type`, `severity` y
    `description`), preservando el orden de la primera aparición.

    Causa raíz del duplicado visible en el modo caso clínico: el UPS
    detecta eventos por snapshot, no una sola vez por condición sostenida
    (`domain/physiology/state/builder.py::_detect_events` — sin tocar, es
    el diseño de Fase 1.1: "el evento se detecta en el momento en que el
    UPS se construye ... no se re-deriva más tarde inspeccionando la
    serie"). `run_rich_scenario` persiste 6 horizontes por escenario, así
    que una condición que se mantiene igual (p.ej. SpO2 estancado en el
    mismo valor redondeado) genera el mismo evento en varios horizontes
    consecutivos. Esto es correcto a nivel de datos — cada snapshot es una
    lectura verídica de ese instante — así que el arreglo es solo de
    presentación, aquí, no en el detector ni en la persistencia."""
    seen = set()
    deduped = []
    for evt in events:
        key = (evt.event_type, evt.severity, evt.description)
        if key not in seen:
            seen.add(key)
            deduped.append(evt)
    return deduped


# Trabajo 1 (2026-08-06) -- agrupación clínica para curar distractores por
# similitud real, en vez de random.sample puro sobre los otros 11.
#
# FIRMA DEL VALIDADOR: agrupación propuesta por Claude Code a partir de los
# datos reales del simulador (matriz de evaluabilidad del Trabajo 2) y
# APROBADA por el validador experto del usuario el 2026-08-06 -- ver
# CHANGELOG.md para el registro completo de la propuesta y su aprobación.
# Los 4 grupos son similitud clínica genuina (qué cuadros un estudiante
# podría razonablemente confundir), no una partición arbitraria:
#
#   A -- Activación simpática aguda: estrés, ansiedad, ejercicio, convulsión
#        (fase aguda), arritmia. Comparten taquicardia + tono simpático
#        alto; se distinguen por SpO2/signos neurológicos/autolimitación.
#   B -- Respiratorio/hipoxémico: hipoxia, apnea, EPOC. Se distinguen por
#        el patrón (progresivo / cíclico / crónico-estable).
#   C -- Hipotensión/bajo gasto/shock: sepsis, arritmia. Se distinguen por
#        mecanismo (progresivo-vasopléjico vs. errático-de-ritmo).
#   D -- Basales/crónicos leves: sano, fatiga, hipertensión. El par sano/
#        fatiga es el de mayor valor pedagógico -- distingue por una sola
#        variable sutil (fatigue_index/HRV), vitales por lo demás casi
#        idénticos.
#
# DECISIÓN CLAVE DEL VALIDADOR, explícita: la arritmia pertenece a DOS
# grupos (A y C) a la vez -- es distractor válido tanto contra ansiedad
# (castiga a quien solo mira la taquicardia sin fijarse en la variabilidad
# del ritmo) como contra sepsis (castiga a quien ve bajo gasto/riesgo alto
# sin notar que la causa es la FC errática, no la vasoplejía). No es un
# error de partición -- un mismo escenario puede ser el distractor correcto
# de más de un diferencial real.
# Unificación 1: "arrhythmia" genérico se retiró. Los tres tipos taquiarrítmicos heredan la
# pertenencia A+C que el validador decidió para el genérico; la bradicardia sinusal (bajo gasto si es
# sintomática, nunca activación simpática) solo entra en C. PENDIENTE DE FIRMA del validador.
_TACHYARRHYTHMIA_SCENARIOS = (
    SimulationScenario.ARRHYTHMIA_AFIB,
    SimulationScenario.ARRHYTHMIA_AFLUTTER,
    SimulationScenario.ARRHYTHMIA_SVT,
)
CLINICAL_GROUPS: Dict[str, FrozenSet[SimulationScenario]] = {
    "A_activacion_simpatica_aguda": frozenset({
        SimulationScenario.STRESS,
        SimulationScenario.ANXIETY,
        SimulationScenario.EXERCISE,
        SimulationScenario.SEIZURE,
        *_TACHYARRHYTHMIA_SCENARIOS,
    }),
    "B_respiratorio_hipoxemico": frozenset({
        SimulationScenario.HYPOXIA,
        SimulationScenario.APNEA,
        SimulationScenario.COPD,
    }),
    "C_hipotension_bajo_gasto_shock": frozenset({
        SimulationScenario.SEPSIS,
        *_TACHYARRHYTHMIA_SCENARIOS,
        SimulationScenario.ARRHYTHMIA_SBRADY,
    }),
    "D_basales_cronicos_leves": frozenset({
        SimulationScenario.HEALTHY,
        SimulationScenario.FATIGUE,
        SimulationScenario.HYPERTENSION,
    }),
}


def _clinical_neighbors(scenario: SimulationScenario) -> FrozenSet[SimulationScenario]:
    """Escenarios del/los mismo(s) grupo(s) clínico(s) que `scenario`, sin
    incluirlo a él mismo. La arritmia, al pertenecer a A y C, sale como
    vecina tanto de los cuadros de activación simpática como de los de
    shock -- exactamente la decisión del validador, no un caso especial
    aparte en el código."""
    neighbors: set = set()
    for group in CLINICAL_GROUPS.values():
        if scenario in group:
            neighbors |= group
    neighbors.discard(scenario)
    return frozenset(neighbors)


def _diagnostic_options(hidden: SimulationScenario, n_options: int = 4) -> list:
    """La opción correcta + `n_options - 1` distractores -- curados por
    similitud clínica (Trabajo 1, 2026-08-06, agrupación con firma del
    validador -- ver `CLINICAL_GROUPS`), ya no puramente al azar sobre los
    otros 11.

    Garantía de distractor cercano: se llena preferentemente con vecinos
    clínicos de `hidden` (`_clinical_neighbors()`); solo se completa con
    escenarios lejanos (fuera de cualquier grupo compartido) si el grupo no
    alcanza para llenar las `n_options - 1` opciones. Con grupos de 4-5
    miembros (A) puede llenarse enteramente de cercanos; con el grupo más
    chico (C, solo sepsis+arritmia) siempre hay como máximo un cercano
    disponible, y el resto se completa con lejanos.

    Los distractores son ETIQUETAS de diagnóstico, no casos generados -- no
    tienen horizonte propio, así que la restricción de horizontes
    evaluables (Trabajo 2, `case_bank.EVALUABLE_HORIZONS_BY_SCENARIO`) no
    aplica aquí: un distractor nunca se muestra como un caso con sus
    propios datos, solo como el nombre de una opción a elegir."""
    close_pool = sorted(_clinical_neighbors(hidden), key=lambda s: s.value)
    far_pool = [s for s in RICH_SCENARIO_LABELS if s != hidden and s not in close_pool]

    n_distractors = n_options - 1
    n_close = min(len(close_pool), n_distractors)
    chosen_close = random.sample(close_pool, n_close) if n_close else []
    n_far = n_distractors - len(chosen_close)
    chosen_far = random.sample(far_pool, n_far) if n_far > 0 else []

    options = chosen_close + chosen_far + [hidden]
    random.shuffle(options)
    return options


# --- PA calculada del motor hemodinámico en los modos de caso clínico ciego ---
# (2026-08-06, ver CHANGELOG.md) -- compartido entre los DOS modos que existen
# (este módulo, "🎓 Caso clínico interactivo" en Twin OS, y
# `app.supermodules.academia.pages::render_synthetic_case_section`, "🧪 Caso
# clínico sintético" en Academia). Se construyó primero en Academia y se
# extrajo aquí para que Academia lo importe -- mismo patrón ya establecido en
# este archivo para `_dedupe_events`/`_diagnostic_options`/`RICH_SCENARIO_LABELS`,
# que Academia ya importaba antes de esta tanda. Un solo lugar para la
# restricción estructural, la resolución de snapshot y el texto del prompt --
# ninguno de los dos modos duplica esta lógica.

_DIVERGENCE_THRESHOLD_MEANING_BY_SCENARIO = {
    "sepsis": "un umbral de shock: por debajo de él, el cuadro se clasifica como shock séptico",
    "hypertension": (
        "un umbral de entrada a la categoría diagnóstica de hipertensión -- no de shock ni de "
        "crisis hipertensiva"
    ),
    "healthy": (
        "el valor normal esperado para un adulto sano, no un umbral de ninguna categoría "
        "patológica -- si diverge del cálculo, probablemente refleje diferencias de calibración "
        "entre el modelo y el punto de referencia, no un hallazgo clínico"
    ),
}


def _attach_calculated_pa_to_case(session, patient_id: str, scenario_value: str, state, source_detail: str):
    """PA calculada por el motor hemodinámico de lazo cerrado, SOLO para los
    3 escenarios con validación experta completa
    (`HEMODYNAMIC_MODEL_ENABLED_SCENARIOS`) -- restricción estructural, no un
    `if` evitable: si `scenario_value` no está habilitado, devuelve `state`
    sin tocar y una lista de referencias vacía, sin calcular nada.

    Resuelve el snapshot EXACTO de `state.timestamp` (nunca "el más reciente
    del paciente") -- necesario en Academia, donde el caso puede mostrar
    cualquiera de los 6 horizontes reales, no siempre el último; en Twin OS
    el modo caso solo muestra el último horizonte, así que ambos coinciden
    siempre, pero resolver por timestamp exacto es correcto en los dos casos
    y evita que este helper compartido tenga que asumir cuál de los dos
    comportamientos tiene el llamador.

    Devuelve `(state_actualizado, referencias_pa)` -- `referencias_pa` es la
    `ClinicalReferenceValue` del escenario si coexiste en el MISMO snapshot
    (solo ocurre cuando el horizonte mostrado es el último de la corrida, ver
    docstring de `run_rich_scenario`), o `[]` si no hay ninguna."""
    if scenario_value not in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS:
        return state, []

    hr_descriptor = state.cardiovascular.get("heart_rate")
    snapshot_id = get_snapshot_id_at(session, patient_id, state.timestamp)
    if hr_descriptor is None or snapshot_id is None:
        return state, []

    # Sepsis: el motor solo modela el shock establecido. Fuera de esa fase la PA se DECLINA (regla firmada por
    # el experto, 2026-11-02): no se calcula ni se adjunta -- mismo resultado que apnea, `(state, [])`. Sin
    # fase identificable tampoco se asume shock.
    if scenario_value == "sepsis" and _sepsis_case_phase(state, scenario_value) not in sepsis_trajectory.PA_MODEL_PHASES:
        return state, []

    try:
        compute_and_attach_closed_loop_pressure(
            session,
            snapshot_id=snapshot_id,
            scenario=scenario_value,
            heart_rate_bpm=hr_descriptor.value,
            source_detail=source_detail,
        )
        refreshed = get_state_by_snapshot_id(session, snapshot_id)
        if refreshed is not None:
            state = refreshed
    except HemodynamicModelNotEnabledError:
        pass  # defensivo, no debería ocurrir dado el filtro de arriba

    references = get_clinical_references_for_snapshot(session, snapshot_id)
    return state, references


def _sepsis_case_phase(state, scenario_value: str) -> Optional[str]:
    """Para sepsis: en qué fase de la trayectoria canónica está este caso (leída del horizonte con que se
    persistió su FC). `None` para otros escenarios o si el estado no viene de un escenario rico."""
    if scenario_value != "sepsis":
        return None
    hr_descriptor = state.cardiovascular.get("heart_rate")
    horizon = sepsis_trajectory.horizon_from_source_detail(hr_descriptor.source_detail if hr_descriptor else None)
    return None if horizon is None else sepsis_trajectory.phase_of(horizon)


def _sepsis_pa_phase_note(state, scenario_value: str) -> str:
    """Qué representa la PA calculada en la fase de este caso de sepsis (solo se adjunta en shock; ver
    `_attach_calculated_pa_to_case`). Vacío para otros escenarios o si la fase no se identifica."""
    phase = _sepsis_case_phase(state, scenario_value)
    if phase is None:
        return ""
    return f" FASE DE ESTE CASO (trayectoria canónica de sepsis, {phase}): {sepsis_trajectory.pa_phase_note(phase)}"


def _sepsis_pa_declination_finding(state, scenario_value: str) -> list:
    """Sepsis fuera de shock: el narrador recibe la declinación (con su motivo) en lugar de una cifra de PA.
    Lista vacía para cualquier otro caso -- apnea y compañía siguen sin Finding de PA, como antes."""
    if scenario_value != "sepsis":
        return []
    phase = _sepsis_case_phase(state, scenario_value)
    if phase in sepsis_trajectory.PA_MODEL_PHASES:
        return []
    return [
        Finding(
            name="PA del modelo hemodinámico (declinada)",
            value=sepsis_trajectory.pa_declination(phase),
            meaning=(
                "El modelo NO calculó PA para este caso -- es un límite declarado del modelo, no un dato "
                f"omitido: {sepsis_trajectory.PA_DECLINATION_REASON} NO inventes, estimes ni insinúes una cifra "
                "de PA, y NO enseñes que la sepsis temprana es hipotensiva (Sepsis-3 define el shock séptico "
                "por la hipotensión que exige vasopresores para mantener PAM ≥ 65 pese a la reposición de "
                "volumen, no la sepsis temprana). Si la PA entra en la explicación, di que el modelo no la "
                "cubre en esta fase."
            ),
        )
    ]


def _build_pa_findings(state, references_pa: list, scenario_value: str) -> list:
    """`Finding`s de PA para el narrador -- calculada (siempre, si existe),
    referencia clínica (si coexiste) y la nota de divergencia entre ambas
    (SOLO cuando coexisten). La cita de la nota se lee en vivo de
    `ref_map.citation` -- nunca se reescribe a mano -- para que nunca cite
    la fuente de un escenario distinto al del caso (p.ej. Sepsis-3 en un
    caso de hipertensión)."""
    map_modelo = state.cardiovascular.get("map_modelo")
    pa_findings = []
    if map_modelo is None:
        return _sepsis_pa_declination_finding(state, scenario_value)

    systolic_modelo = state.cardiovascular.get("systolic_bp_modelo")
    diastolic_modelo = state.cardiovascular.get("diastolic_bp_modelo")
    pa_findings.append(
        Finding(
            name="PA calculada por el modelo hemodinámico",
            value=f"{systolic_modelo.value:.0f}/{diastolic_modelo.value:.0f} mmHg (PAM {map_modelo.value:.0f} mmHg)",
            meaning=(
                "CALCULADA por el modelo hemodinámico de lazo cerrado a partir del heart_rate real "
                "de este caso -- NUNCA la presentes como una medición del paciente ni como un valor "
                "de guía clínica; es un cálculo del modelo. Explica el POR QUÉ FISIOLÓGICO de este "
                "valor a partir del diagnóstico correcto de este caso (p.ej. en sepsis: la "
                "vasoplejía reduce el tono vascular y colapsa el retorno venoso, por lo que la "
                "presión cae pese a la taquicardia compensatoria; en hipertensión: el reseteo del "
                "barostato eleva el punto de equilibrio) -- no te limites a reportar el número."
                + _sepsis_pa_phase_note(state, scenario_value)
            ),
        )
    )
    ref_map = next((r for r in references_pa if r.descriptor == "map"), None)
    if ref_map is not None:
        pa_findings.append(
            Finding(
                name="PA de referencia clínica (guía citada)",
                value=f"PAM {ref_map.value:.0f} mmHg",
                meaning=(
                    "Valor de REFERENCIA transcrito de literatura clínica para este cuadro -- no es "
                    "una medición ni el cálculo del modelo de arriba; son dos fuentes distintas que "
                    "coexisten."
                ),
            )
        )
        threshold_meaning = _DIVERGENCE_THRESHOLD_MEANING_BY_SCENARIO.get(
            scenario_value, "un criterio de clasificación de guía clínica"
        )
        pa_findings.append(
            Finding(
                name="Nota sobre la posible divergencia entre las dos PA",
                value="Ver las dos métricas anteriores",
                meaning=(
                    "Si la PA calculada y la PA de referencia difieren, explícalo como una lección, no "
                    "como una contradicción -- NUNCA declares una 'correcta' y la otra 'incorrecta', y "
                    "NUNCA ajustes ninguna de las dos para que se acerquen; la divergencia es real y "
                    "fisiológicamente honesta, se explica, no se maquilla. La referencia citada aquí "
                    f"({ref_map.citation}) es {threshold_meaning}, no la presión real de este paciente. "
                    "La calculada es la estimación del modelo PARA ESTE paciente concreto, derivada de "
                    "su fisiología específica -- puede diferir del criterio de guía si el cuadro está "
                    "descompensado o si el modelo y la guía parten de supuestos distintos. Divergir no "
                    "es contradicción: la guía marca el criterio de clasificación; el modelo estima el "
                    "estado fisiológico real de este caso concreto."
                ),
            )
        )
    return pa_findings


def render_clinical_case_mode(organism: DigitalTwinOrganism) -> None:
    """Modo Caso Clínico Interactivo v1 (2026-07-12) — diagnóstico por
    opción múltiple. Convierte al estudiante de espectador en clínico,
    reutilizando TODO lo existente: los 15 escenarios reales
    (`domain.physiology.scenarios.rich_engine.run_rich_scenario`), el UPS
    persistido, el cuerpo visual (`render_ups_body`) y el narrador real
    (`stream_findings_narration` — misma disciplina de anclaje que
    `render_clinical_narrator`, reutilizada tal cual, sin tocar
    `narrator/*`).

    Regla rectora: la verdad de referencia es el escenario que este código
    efectivamente cargó en el UPS (`hidden_scenario`, decidido por
    `random.choice`) — nunca una opinión del modelo. El narrador solo
    explica, con los descriptores/eventos reales, por qué esos datos
    encajan con esa verdad y por qué no encajan con la hipótesis del
    estudiante si falló.

    Aislamiento del caso oculto: se genera con un `DigitalTwinOrganism()`
    efímero propio (no el `organism` compartido de la sesión) y un
    `patient_id` nuevo y desechable, para que cargar un caso ciego no
    salpique el encabezado ambiental ni el resto de paneles del Twin OS,
    que siguen leyendo el organismo/paciente continuo de siempre. El
    `display_name` del paciente efímero es genérico ("Caso clínico
    interactivo") — a propósito, nunca contiene el nombre del escenario,
    para que no se filtre por ningún listado de pacientes de otra página.

    Ocultamiento: el nombre del escenario (`RICH_SCENARIO_LABELS[hidden]`)
    solo se renderiza DESPUÉS de que el estudiante confirma su respuesta —
    antes de eso, todo lo que se muestra (cuerpo, descriptores, eventos)
    viene de `get_latest_state`/`get_events`, que nunca exponen el
    escenario que los generó (no es un campo del UPS)."""

    with st.expander("🎓 Caso clínico interactivo (diagnóstico ciego) — v1", expanded=False):
        st.caption(
            "Se carga uno de los 15 escenarios reales sin revelar cuál. Diagnostica eligiendo "
            "entre 4 opciones; el feedback lo genera el narrador real (Anthropic), fundamentado "
            "únicamente en los descriptores y eventos que el UPS realmente persistió."
        )

        if not narrator_is_configured():
            st.warning(
                "`ANTHROPIC_API_KEY` no está configurada — el feedback fundamentado requiere la "
                "API real de Anthropic, sin narración simulada de respaldo. " + AI_KEY_HINT
            )
            return

        if st.button("🆕 Nuevo caso clínico", key="clinical_case_new"):
            session_factory = get_active_session_factory()
            hidden_scenario = random.choice(list(RICH_SCENARIO_LABELS.keys()))
            case_organism = DigitalTwinOrganism()  # efímero: no toca el organismo de la sesión
            with session_factory() as session:
                # Fase 3 (2026-08-30): paciente efímero deliberado, nunca el
                # paciente único continuo -- mismo helper compartido con el
                # quiz de Academia (`case_bank.py`), antes cada uno tenía su
                # propio `create_patient()` inline sin declarar la intención.
                patient_id = create_ephemeral_case_patient(session, "Caso clínico interactivo")
                for step in run_rich_scenario(
                    session, patient_id, hidden_scenario, case_organism, start_from_current_state=False
                ):
                    pass

                # PA calculada del motor hemodinámico (2026-08-06, ver CHANGELOG.md) --
                # mismo helper compartido que usa Academia (`_attach_calculated_pa_to_case`),
                # restricción estructural a los 3 escenarios validados incluida. `step.state`
                # es el último horizonte (7d) -- este modo, a diferencia de Academia, siempre
                # muestra el último, nunca uno intermedio elegido al azar.
                _attach_calculated_pa_to_case(
                    session, patient_id, hidden_scenario.value, step.state,
                    source_detail="twin_shell_clinical_case_mode",
                )

            st.session_state.clinical_case_patient_id = patient_id
            st.session_state.clinical_case_hidden_scenario = hidden_scenario
            st.session_state.clinical_case_options = _diagnostic_options(hidden_scenario)
            st.session_state.clinical_case_answered = False
            st.session_state.clinical_case_selected = None
            st.session_state.clinical_case_feedback = None
            st.session_state.clinical_case_feedback_error = None
            st.rerun()

        patient_id = st.session_state.get("clinical_case_patient_id")
        if not patient_id:
            st.caption("Sin ningún caso activo todavía — pulsa 'Nuevo caso clínico' para empezar.")
            return

        session_factory = get_active_session_factory()
        with session_factory() as session:
            state = get_latest_state(session, patient_id)
            events = _dedupe_events(get_events(session, patient_id))
            # La PA calculada ya quedó persistida (si aplica) por "Nuevo caso clínico"
            # -- get_latest_state() de arriba ya la incluye. Solo falta resolver si
            # hay ClinicalReferenceValue coexistiendo en el mismo snapshot, para
            # mostrarla y para el Finding de divergencia del narrador más abajo.
            case_snapshot_id = get_snapshot_id_at(session, patient_id, state.timestamp)
            case_references = (
                get_clinical_references_for_snapshot(session, case_snapshot_id)
                if case_snapshot_id is not None
                else []
            )

        st.markdown("#### Estado del paciente — diagnóstico oculto")
        render_ups_body(state, with_3d=True, key="twin_caso")

        desc_rows = [
            {
                "Dominio": domain_state.domain,
                "Descriptor": d.name,
                "Valor": f"{d.value:.1f} {d.unit}",
                "Procedencia": d.provenance.value,
                "Confianza": f"{d.confidence:.0%}",
            }
            for domain_state in state.all_domains().values()
            for d in domain_state.descriptors.values()
        ]
        st.dataframe(pd.DataFrame(desc_rows), use_container_width=True, hide_index=True)

        map_modelo = state.cardiovascular.get("map_modelo")
        if map_modelo is not None:
            systolic_modelo = state.cardiovascular.get("systolic_bp_modelo")
            diastolic_modelo = state.cardiovascular.get("diastolic_bp_modelo")
            ref_map = next((r for r in case_references if r.descriptor == "map"), None)
            st.markdown(
                f"**🧮 PA calculada por el modelo hemodinámico ({pa_model_label()}):** "
                f"{systolic_modelo.value:.0f}/{diastolic_modelo.value:.0f} mmHg "
                f"(PAM {map_modelo.value:.0f} mmHg, confianza {map_modelo.confidence:.0%})"
                + (f" — referencia clínica citada: PAM {ref_map.value:.0f} mmHg" if ref_map else "")
            )
            st.caption(
                "Valor CALCULADO por el modelo a partir del heart_rate real de este caso -- no es una "
                "medición del paciente ni un valor de guía clínica. Solo disponible para sano/"
                "hipertensión/sepsis (los 3 escenarios con validación experta completa del motor "
                "hemodinámico); en el resto de los 15 escenarios este caso no muestra PA calculada."
            )

        if events:
            st.markdown("**Eventos detectados:**")
            for evt in events:
                icon = "🔴" if evt.severity == EventSeverity.CRITICAL else "🟡"
                st.caption(f"{icon} `{evt.event_type.value}` — {evt.description}")

        options = st.session_state.clinical_case_options

        if not st.session_state.clinical_case_answered:
            choice = st.radio(
                "¿Cuál es tu diagnóstico?",
                options,
                format_func=lambda s: RICH_SCENARIO_LABELS[s],
                key=f"clinical_case_radio_{patient_id}",
            )
            if st.button("✅ Confirmar diagnóstico", key=f"clinical_case_confirm_{patient_id}"):
                hidden = st.session_state.clinical_case_hidden_scenario

                with session_factory() as session:
                    context = build_context(session, patient_id)

                findings = [
                    Finding(
                        name=d.name,
                        value=f"{d.value} {d.unit}",
                        meaning=(
                            f"Dominio {d.domain}, procedencia {d.provenance}, "
                            f"confianza {d.confidence:.0%}."
                        ),
                    )
                    for d in context.descriptors
                ] + [
                    Finding(name=e.event_type, value=e.severity, meaning=e.description)
                    for e in _dedupe_events(context.events)
                ] + _build_pa_findings(state, case_references, hidden.value) + [
                    Finding(
                        name="Diagnóstico elegido por el estudiante",
                        value=RICH_SCENARIO_LABELS[choice],
                        meaning="Evalúalo contra los datos anteriores — no lo repitas como si fuera un campo técnico.",
                    ),
                    Finding(
                        name="Diagnóstico correcto (verdad de referencia del caso)",
                        value=RICH_SCENARIO_LABELS[hidden],
                        meaning=(
                            "Viene del escenario real que efectivamente cargó el UPS, no de tu "
                            "criterio. Explica por qué los descriptores/eventos anteriores encajan "
                            "con este diagnóstico y, si la hipótesis del estudiante es distinta, por "
                            "qué esos mismos datos no encajan con ella."
                        ),
                    ),
                ]
                findings_context = FindingsContext(lab_name="Caso Clínico Interactivo", findings=findings)

                try:
                    feedback_text = "".join(stream_findings_narration(findings_context, client=ai_client()))
                    st.session_state.clinical_case_feedback = feedback_text
                    st.session_state.clinical_case_feedback_error = None
                except NarratorNotConfiguredError as exc:
                    st.session_state.clinical_case_feedback = None
                    st.session_state.clinical_case_feedback_error = str(exc)
                except Exception as exc:  # llamada real a la API — puede fallar por red/cuota/etc.
                    st.session_state.clinical_case_feedback = None
                    st.session_state.clinical_case_feedback_error = f"Error llamando a la API de Anthropic: {exc}"

                st.session_state.clinical_case_selected = choice
                st.session_state.clinical_case_answered = True
                st.rerun()
        else:
            selected = st.session_state.clinical_case_selected
            hidden = st.session_state.clinical_case_hidden_scenario
            correct = selected == hidden

            if correct:
                st.success(f"✅ ¡Correcto! El caso era: {RICH_SCENARIO_LABELS[hidden]}")
            else:
                st.error(
                    f"❌ Elegiste {RICH_SCENARIO_LABELS[selected]} — el caso real era "
                    f"{RICH_SCENARIO_LABELS[hidden]}"
                )

            st.markdown("**Feedback del narrador (fundamentado en el UPS):**")
            if st.session_state.clinical_case_feedback:
                st.markdown(st.session_state.clinical_case_feedback)
            elif st.session_state.clinical_case_feedback_error:
                st.error(st.session_state.clinical_case_feedback_error)

            if st.button("➡️ Otro caso", key="clinical_case_next"):
                for k in [
                    "clinical_case_patient_id", "clinical_case_hidden_scenario", "clinical_case_options",
                    "clinical_case_answered", "clinical_case_selected", "clinical_case_feedback",
                    "clinical_case_feedback_error",
                ]:
                    st.session_state.pop(k, None)
                st.rerun()


_CAUSAL_UPS_ORGANS = {"heart", "lungs"}


def _ups_domain_names() -> list[str]:
    """Dominios que el UPS modela HOY, leídos del propio esquema (`all_domains()`),
    para que el texto de la UI no vuelva a caducar cuando se agregue un dominio."""
    from datetime import datetime, timezone

    from domain.physiology.state import DomainState, UnifiedPhysiologicalState

    vacio = UnifiedPhysiologicalState(
        patient_id="", timestamp=datetime.now(timezone.utc),
        cardiovascular=DomainState(domain="cardiovascular"), respiratory=DomainState(domain="respiratory"),
    )
    return list(vacio.all_domains())


def render_causal_reasoning(organism: DigitalTwinOrganism) -> None:
    """Consolidación (2026-07-13): antes usaba `CausalityEngine.find_root_cause()`
    — texto armado desde reglas fijas (`CAUSAL_RULES`), sin IA y con un final
    abrupto (no un bug de streaming/max_tokens: esa función nunca llamó a la
    API). `CausalityEngine` queda sin tocar, huérfano, fuera del alcance de
    esta tanda.

    Ahora responde el narrador causal real
    (`domain.physiology.narrator.causal`): reutiliza `build_context()` sin
    cambiarlo (la comparación antes→ahora y el orden temporal de eventos SON
    la evidencia causal) y razona el origen del estado, no solo lo describe.
    Solo tiene sentido para los dos órganos que el UPS modela (heart/lungs) —
    para el resto, se declara honestamente que no hay datos del UPS, en vez
    de razonar sobre el organismo en memoria sin fundamento persistido."""

    with st.expander("🧠 Razonamiento causal — ¿por qué está así este órgano? (IA real)"):
        organ_id = st.session_state.twin_shell_selected_organ
        organ = organism.organs[organ_id]

        if organ_id not in _CAUSAL_UPS_ORGANS:
            st.info(
                f"El razonamiento causal solo está habilitado para el corazón y los pulmones; "
                f"**{organ.name}** no está cableado a esta función. "
                f"El UPS modela hoy {len(_ups_domain_names())} dominios ({', '.join(_ups_domain_names())}). "
                "Selecciona el corazón o los pulmones para usar el razonamiento causal."
            )
            return

        if not narrator_is_configured():
            st.warning(
                "`ANTHROPIC_API_KEY` no está configurada — el razonamiento causal requiere la "
                "API real de Anthropic, sin narración simulada de respaldo. " + AI_KEY_HINT
            )
            return

        st.caption(
            f"Analiza el posible origen fisiológico del estado actual de {organ.name}, "
            "fundamentado en la trayectoria real del UPS (antes→ahora) y el orden temporal de "
            "sus eventos — no en reglas fijas ni en texto genérico."
        )

        if st.button("Explicar origen", key="twin_shell_explain_cause"):
            session_factory = get_active_session_factory()
            patient_id = get_active_patient_id()

            with session_factory() as session:
                persist_current_state(
                    session, organism, patient_id, source_detail="razonamiento_causal:snapshot_bajo_demanda"
                )
                causal_context = build_causal_context(session, patient_id, organ_id)

            st.caption(
                f"Basado en {len(causal_context.narrative.descriptors)} descriptores y "
                f"{len(causal_context.narrative.events)} eventos del UPS."
            )
            try:
                st.write_stream(stream_causal_narration(causal_context, client=ai_client()))
            except NarratorNotConfiguredError as exc:
                render_error_state(str(exc))
            except Exception as exc:  # llamada real a la API — puede fallar por red/cuota/etc.
                render_error_state(
                    "No se pudo completar la narración -- la llamada a la API de Anthropic falló "
                    "(red o cuota). Intenta de nuevo en unos segundos.",
                    exception=exc,
                )


# NOTA (Tanda 3, 2026-07-03): render_simulation_lab() — el navegador de 12
# escenarios en memoria, sin persistencia — se eliminó: quedó 100% subsumida
# por render_ups_scenario_simulator(), que ahora ofrece los mismos 12
# escenarios de SimulationEngine pero conectados al UPS (narrador + cuerpo
# visual incluidos). Mantener ambas habría dejado exactamente la duplicación
# "un simulador de 12 conectado, otro de 12 sin conectar" que esta tanda
# buscaba eliminar.


def render_ml_risk_panel(organism: DigitalTwinOrganism) -> None:
    """Tanda 4, Pieza 1 (2026-07-04): scoring de riesgo/anomalías real
    (`src.ai.patient_analytics.PatientRiskPredictor`/`AnomalyDetector`),
    antes huérfano y alcanzable solo con datos de paciente hardcodeados en
    `app/pages_legacy/4_👥_Patients.py` (ya archivado). Aquí se alimenta con
    el snapshot más reciente del UPS — vía
    `domain.physiology.ml.build_risk_features`, mismo patrón de solo-lectura
    que `build_context()` del narrador — nunca con literales fijos.

    Distinto de `render_risk_assessment()` (más abajo, `PredictionEngine`,
    sin tocar): es un motor real separado, con su propia metodología de
    scoring por factores ponderados. Lectura del estado actual, no una
    página nueva — vive junto al resto de "Herramientas avanzadas".

    Fase 5.1 (punto único de verdad, 2026-08-30): a diferencia del Cuerpo
    Digital y el clasificador de ECG, este panel NO se migró a
    `get_current_physiological_state()` -- `build_risk_features()`
    (`domain/physiology/ml/risk_context.py`) no solo lee el snapshot más
    reciente, también arma `trend_data` (`get_value_history`, historial
    real que solo existe persistido -- el organismo en memoria no lleva
    trayectoria) y `systolic_bp`/`diastolic_bp` (`ClinicalReferenceValue`
    atada a un `snapshot_id` concreto ya persistido -- no hay equivalente
    en memoria). Migrar este panel habría exigido degradar esos dos campos
    a `None` o reescribir `build_risk_features()` para mezclar memoria con
    consultas históricas -- un cambio de comportamiento real, no un cambio
    de "de dónde lee lo mismo". Sigue leyendo el último snapshot
    persistido, sin cambios; su desincronización frente a las tarjetas de
    órgano queda fuera del alcance de esta tanda -- ver CHANGELOG.md."""

    with st.expander("🧬 Índice de riesgo heurístico (pesos fijos, sin entrenamiento), desde el UPS"):
        st.caption(
            "PatientRiskPredictor (suma de factores con pesos fijos, sin entrenamiento) + AnomalyDetector "
            "(puntaje Z estadístico) de src/ai/patient_analytics.py, alimentados con los descriptores "
            "reales del snapshot más reciente del UPS — no es un modelo de aprendizaje automático."
        )
        # Fase 5.2 (honestidad de presentación, 2026-08-30): este panel lee
        # el ÚLTIMO PERSISTIDO a propósito (ver docstring de la función,
        # Fase 5.1) -- sin esta línea, mover un slider y ver que el Cuerpo
        # Digital/clasificador de ECG reaccionan al instante pero este panel
        # no, parece un bug. No lo es: se explica por qué.
        st.caption(
            "⏳ Este panel integra la **trayectoria** del paciente (tendencia real, no solo el "
            "instante) — por eso no cambia al mover un slider como el Cuerpo Digital o el "
            "clasificador de ECG. Se actualiza al guardar un momento en la historia del paciente "
            "o al ejecutar un escenario."
        )

        session_factory = get_active_session_factory()
        patient_id = get_active_patient_id()

        with session_factory() as session:
            features = build_risk_features(session, patient_id)

        if features is None:
            st.info(
                "No hay ningún snapshot del UPS todavía para este paciente — ajusta las señales "
                "o corre un escenario primero."
            )
            return

        include_age = st.checkbox(
            "Incluir edad ingresada en Biomarkers Lab (dato real ingresado por el usuario, no del UPS)",
            value=False,
            key="twin_shell_risk_include_age",
            help="El UPS no modela demografía — esta edad viene del campo 'Edad' de Clinical Hub → "
                 "Biomarkers Lab. Si no visitaste esa página todavía, no hay edad que incluir (el "
                 "checkbox simplemente no aporta nada, sin romperse). Se omite por defecto para no "
                 "mezclar fuentes sin que lo pidas.",
        )
        age = st.session_state.get("pac_edad") if include_age else None
        if features.systolic_bp is not None and features.diastolic_bp is not None:
            st.caption(
                f"🩺 Presión arterial: {features.systolic_bp:.0f}/{features.diastolic_bp:.0f} mmHg — "
                "**referencia clínica citada del cuadro** (no una medición del paciente ni una "
                "simulación dinámica; ver `domain/physiology/state/blood_pressure_references.py` "
                "para la fuente exacta de este escenario)."
            )
        else:
            st.caption(
                "Sin presión arterial disponible para el escenario más reciente de este paciente — "
                "ese factor queda omitido del score. Solo hay referencia de PA transcrita con fuente "
                "para 10 de los 15 escenarios (no para fatiga crónica ni EPOC) — nunca se rellena con "
                "un valor típico sin cita."
            )

        predictor = PatientRiskPredictor()
        result = predictor.calculate_risk_score(
            age=age,
            heart_rate=features.heart_rate,
            systolic_bp=features.systolic_bp,
            diastolic_bp=features.diastolic_bp,
            ecg_pattern=features.ecg_pattern,
            hrv_sdnn=features.hrv_sdnn,
            trend_data=features.trend_data,
        )

        if result["total_risk"] is None:
            st.warning(result["risk_level"])
        else:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(
                    f"""
                    <div style='text-align:center; padding:14px; border-radius:12px;
                                border:1px solid {result['color']}55; background: rgba(255,255,255,0.03);'>
                        <div style='font-size:11px; letter-spacing:1px; color:#9fb4c9;'>RIESGO CARDIOVASCULAR (DERIVADO)</div>
                        <div style='font-size:32px; font-weight:700; color:{result['color']};'>{result['total_risk']:.0%}</div>
                        <div style='font-size:13px; color:{result['color']};'>{result['risk_level']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(f"**Factores usados (dato real del UPS):** {', '.join(result['factors_used']) or 'ninguno'}")
                if result["factors_omitted"]:
                    st.caption(f"Factores omitidos (sin fuente real disponible): {', '.join(result['factors_omitted'])}")
                if result["recommendations"]:
                    st.markdown("**Recomendaciones:**")
                    for rec in result["recommendations"]:
                        st.write(f"- {rec}")

        # Detección de anomalías sobre el historial REAL de FC del UPS (no una señal sintética)
        st.markdown("---")
        if len(features.trend_data) >= 3:
            detector = AnomalyDetector()
            anomalies = detector.detect_anomalies(np.array(features.trend_data), parameter_name="heart_rate")
            st.markdown(
                f"**Detección de anomalías** (Z-score sobre {len(features.trend_data)} snapshots "
                f"reales de FC del UPS):"
            )
            if anomalies["anomalies_detected"]:
                st.warning(
                    f"⚠️ Anomalía detectada — severidad: {anomalies['severity']} "
                    f"(máx. {anomalies.get('max_deviation_std', '?')} desviaciones estándar)"
                )
            else:
                st.success(f"Sin anomalías detectadas en el historial reciente (severidad: {anomalies['severity']}).")
        else:
            st.caption(
                f"Se necesitan al menos 3 snapshots con historial de FC para detectar anomalías "
                f"(hay {len(features.trend_data)})."
            )


def render_ecg_classifier_panel(organism: DigitalTwinOrganism) -> None:
    """Tanda 4, Pieza 2 (2026-07-04): clasificador de ECG real
    (`clinical.ecg_analyzer.ECGAnalyzer.detect_clinical_pattern`) +
    explicación por contribución de pesos fijos (`src/interpretability.py`, heurística: no es SHAP ni LIME), integrado al
    Twin OS. Regla absoluta de esta pieza: ninguna señal de ECG cruda entra
    al clasificador sin procedencia veraz — la procedencia refleja lo que
    realmente ocurrió, no lo que el usuario pidió.

    Modo (A, por defecto): forma de onda sintética generada desde el
    `heart_rate` REAL del estado fisiológico ACTUAL
    (`get_current_physiological_state()`, Fase 5.1 — antes leía el último
    snapshot persistido, ver CHANGELOG.md) vía
    `domain.physiology.ml.build_synthetic_ecg_from_ups` — siempre
    `Provenance.SIMULACION`.

    Modo (B, opcional): hardware ESP32 real
    (`src.signals.signal_sources.ESP32SignalSource`). `Provenance.SENSOR_REAL`
    SOLO si `source.is_hardware_present()` confirma una conexión serial real
    en ESE MOMENTO — nunca por la sola intención de conectar
    (`is_connected()`/`.connected` siguen siendo `True` bajo
    `simulate_if_missing`, por eso no se usan aquí para esta decisión)."""

    with st.expander("🫀 Clasificador de ECG (real, desde tu estado actual)"):
        st.caption(
            "detect_clinical_pattern() (reglas por umbral, clinical/ecg_analyzer.py) + explicación por "
            "contribución de pesos fijos (src/interpretability.py) sobre la señal analizada — "
            "nunca ruido aleatorio ni un resultado fijo."
        )

        mode = st.radio(
            "Fuente de la señal ECG",
            ["Sintética desde tu estado actual (modo A)", "Hardware real ESP32 (modo B)"],
            key="twin_shell_ecg_source_mode",
        )

        signal = None
        fs: Optional[float] = None
        provenance_label = None
        meta_caption = None

        if mode == "Sintética desde tu estado actual (modo A)":
            # Fase 5.1 (2026-08-30): antes leía `get_latest_state()` (último
            # snapshot persistido) -- ahora lee el estado ACTUAL en memoria,
            # mismo punto único de verdad que el Cuerpo Digital. Un slider
            # movido se refleja aquí al instante, no solo tras "Sincronizar".
            patient_id = get_active_patient_id()
            state = get_current_physiological_state(organism, patient_id)
            synth = build_synthetic_ecg_from_ups(state)

            if synth is None:
                st.info(
                    "Todavía no hay heart_rate en tu estado actual — ajusta las señales o "
                    "corre un escenario primero."
                )
            else:
                signal, fs = synth.signal, synth.fs
                provenance_label = "SIMULACIÓN"
                arrhythmia_note = (
                    " — evento de arritmia activo en el estado actual (ARRHYTHMIA_RISK_HR_EXTREME)"
                    if synth.arrhythmia_event_active else ""
                )
                meta_caption = f"FC real de tu estado actual: {synth.heart_rate:.0f} bpm{arrhythmia_note}"

        else:
            st.caption(
                "Conecta un ESP32 real por puerto serial. Si no responde ningún dispositivo "
                "físico, el resultado se etiqueta SIMULACIÓN — nunca SENSOR_REAL por la sola "
                "intención de conectar."
            )
            port = st.text_input("Puerto ESP32 (o 'Auto')", value="Auto", key="twin_shell_ecg_hw_port")
            col_a, col_b = st.columns(2)
            with col_a:
                connect_clicked = st.button("🔌 Conectar hardware ECG", key="twin_shell_ecg_hw_connect")
            with col_b:
                disconnect_clicked = st.button("Desconectar", key="twin_shell_ecg_hw_disconnect")

            if connect_clicked:
                chosen_port = None if port.strip().lower() == "auto" else port.strip()
                try:
                    hw_source = ESP32SignalSource(port=chosen_port, fs=250, buffer_seconds=15, simulate_if_missing=True)
                    hw_source.connect(force_port=chosen_port)
                    hw_source.start()
                    st.session_state.twin_shell_ecg_hw_source = hw_source
                except Exception as exc:
                    render_error_state(
                        "No se pudo conectar al ESP32 -- verifica el puerto y que el dispositivo esté "
                        "encendido.",
                        exception=exc,
                    )

            if disconnect_clicked and st.session_state.get("twin_shell_ecg_hw_source") is not None:
                try:
                    st.session_state.twin_shell_ecg_hw_source.stop()
                    st.session_state.twin_shell_ecg_hw_source.disconnect()
                except Exception:
                    pass
                st.session_state.twin_shell_ecg_hw_source = None

            hw_source = st.session_state.get("twin_shell_ecg_hw_source")
            if hw_source is None:
                st.info("No hay ninguna fuente de hardware conectada todavía.")
            else:
                # Prueba de honestidad de procedencia: is_hardware_present() comprueba una
                # conexión serial real EN ESTE MOMENTO — no si alguna vez se intentó conectar.
                hardware_real = hw_source.is_hardware_present()
                _, buf_signal = hw_source.get_filtered_buffer()
                if len(buf_signal) < 5:
                    st.warning(
                        "El buffer de hardware está casi vacío todavía — espera unos segundos "
                        "o revisa la conexión."
                    )
                else:
                    signal, fs = buf_signal, hw_source.fs
                    if hardware_real:
                        provenance_label = "SENSOR_REAL"
                        meta_caption = "Dispositivo ESP32 real respondiendo por puerto serial."
                    else:
                        provenance_label = "SIMULACIÓN"
                        meta_caption = (
                            "⚠️ No se detectó ningún dispositivo físico — el software cayó a "
                            "modo simulado. Re-etiquetado explícitamente como SIMULACIÓN, nunca "
                            "como sensor real."
                        )

        if signal is None:
            return

        badge_color = "#39d98a" if provenance_label == "SENSOR_REAL" else "#ffc542"
        st.markdown(
            f"<span style='font-family:monospace; font-size:11px; font-weight:700; "
            f"padding:3px 9px; border-radius:999px; background:{badge_color}22; color:{badge_color};'>"
            f"PROCEDENCIA: {provenance_label}</span>",
            unsafe_allow_html=True,
        )
        if meta_caption:
            st.caption(meta_caption)

        result = classify_ecg_signal(signal, fs)

        # Pulido (2026-08-06): el "X% confianza" que vivía aquí era una constante
        # literal por rama de regla en detect_clinical_pattern() (0.95/0.92/.../0.60),
        # sin cálculo detrás -- un número con apariencia de métrica que en realidad no
        # se calculaba (Art. I de la Constitución). Se retiró el campo `confidence`
        # por completo (EcgClassificationResult ya no lo tiene). En su lugar se
        # muestra el criterio real que disparó la regla -- primer elemento de
        # `result.reasoning`, siempre presente y siempre citando el valor medido +
        # el umbral exacto (p.ej. "QTc=485 ms (umbral > 470 ms)"). Ver CHANGELOG.md.
        criterion = result.reasoning[0] if result.reasoning else "Sin criterio adicional"

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(
                f"""
                <div style='text-align:center; padding:14px; border-radius:12px;
                            border:1px solid rgba(255,255,255,0.14); background: rgba(255,255,255,0.03);'>
                    <div style='font-size:11px; letter-spacing:1px; color:#9fb4c9;'>CLASIFICACIÓN (DERIVADO)</div>
                    <div style='font-size:19px; font-weight:700; color:#e5e5e5;'>{result.pattern}</div>
                    <div style='font-size:13px; color:#9fb4c9;'>{criterion}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            if result.reasoning:
                st.markdown("**Hallazgos (criterio medido, no una probabilidad):**")
                for r in result.reasoning:
                    st.write(f"- {r}")
            st.caption(f"Picos R detectados: {result.r_peak_count}")

        st.markdown("---")
        st.markdown("**Explicación por contribución de pesos fijos (heurística, sobre la señal analizada):**")
        if result.shap_lime:
            tab_shap, tab_lime, tab_importance = st.tabs(["Contribución por desviación", "Dirección de riesgo", "Importancia"])
            with tab_shap:
                for line in result.shap_lime["shap"]:
                    st.write(line)
            with tab_lime:
                for line in result.shap_lime["lime"]:
                    st.write(line)
            with tab_importance:
                # Pulido rápido (2026-08-04): result.shap_lime["importance"] ya lo
                # calcula compute_feature_importance() (src/interpretability.py) para
                # alimentar las narrativas de las dos pestañas de arriba -- aquí solo
                # se dibuja ese mismo dato como barra, sin recalcular nada.
                st.caption(
                    "Importancia por desviación de baseline (|valor-baseline| normalizado a 100% "
                    "entre las features) -- heurística de pesos fijos; no es SHAP ni LIME, y es la "
                    "misma cuenta que narran las otras dos pestañas."
                )
                importance = result.shap_lime["importance"]
                importance_df = pd.DataFrame(
                    {"Importancia (%)": [item["percent"] for item in importance]},
                    index=[item["label"] for item in importance],
                )
                st.bar_chart(importance_df, use_container_width=True)
        else:
            st.caption(result.explainability_note or "Explicabilidad no disponible.")


# Etiquetas en español de las 5 claves de `system_risks` (prediction_engine.py); las claves no se tocan.
_SYSTEM_NAME_LABELS = {
    "cardiovascular": "Cardiovascular",
    "respiratory": "Respiratorio",
    "neurological": "Neurológico",
    "muscular": "Muscular",
    "autonomic": "Autonómico",
}

def render_risk_assessment(organism: DigitalTwinOrganism) -> None:
    """Evaluación por sistema con fuente (fase 0): cardiovascular y respiratorio = componentes NEWS2; neurológico,
    muscular y autonómico = «sin criterio con fuente» (sus umbrales propios se retiraron); el riesgo global = NEWS2
    parcial, nunca un total ni un promedio."""
    if "twin_shell_prediction" not in st.session_state:
        st.session_state.twin_shell_prediction = PredictionEngine()

    with st.expander("📊 Evaluación de riesgo detallada por sistema"):
        engine = st.session_state.twin_shell_prediction
        sensor_data = {
            "ecg": organism.current_signals("heart"), "respiratory": organism.current_signals("lungs"),
            "eeg": organism.current_signals("brain"), "emg": organism.current_signals("muscles"),
        }
        assessment = engine.assess_global_risk(organism, sensor_data, organism.timestamp.isoformat())
        partial = assessment.news2_partial
        st.metric(
            "NEWS2 parcial (sin total)",
            " · ".join(f"{n} {p}" for n, p in partial.components.items()) if partial.available else NO_DATA,
            help=f"{PROVENANCE_CLINICAL_BADGE} {assessment.reason}",
        )
        st.caption(f"Faltan para el total NEWS2: {', '.join(partial.missing)}. No se suma ni se categoriza.")
        for name, risk in assessment.system_risks.items():
            prefix = f"{PROVENANCE_CLINICAL_BADGE} " if risk.has_data else "⚪ "
            display_name = _SYSTEM_NAME_LABELS.get(name, name.capitalize())
            st.markdown(f"**{prefix}{display_name}** — {risk.risk_level}")
            st.caption(risk.recommendation)


def render_clinical_export(organism: DigitalTwinOrganism) -> None:
    """Clinical summary + JSON export — folded in from Digital Twin Profesional."""
    with st.expander("📋 Resumen clínico y exportación"):
        summary = organism.generate_clinical_summary()
        st.code(summary, language="text")
        col1, col2 = st.columns(2)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with col1:
            st.download_button(
                "📥 Descargar resumen (TXT)", data=summary,
                file_name=f"twin_summary_{stamp}.txt", mime="text/plain", key="twin_shell_dl_txt",
            )
        with col2:
            st.download_button(
                "📥 Exportar estado (JSON)", data=organism.to_json(),
                file_name=f"twin_state_{stamp}.json", mime="application/json", key="twin_shell_dl_json",
            )


def render_timeline(organism: DigitalTwinOrganism) -> None:
    """Past → Present: la FC y sus puntos NEWS2 de pulso en el tiempo (fase 0, decisión 4 de Luis). Sustituye a la línea
    de salud global/coherencia (índices retirados). Los momentos sin FC actual quedan vacíos, no en 0."""
    history = organism.history
    if len(history) < 2:
        st.caption("La línea de tiempo se irá construyendo a medida que el organismo reciba nuevas señales.")
        return

    st.markdown("#### 🕐 Línea de tiempo: FC y puntos NEWS2 del pulso")
    recent = history[-50:]
    df = pd.DataFrame({
        "Momento": list(range(len(recent))),
        "FC (lpm)": [h.get("heart_rate") for h in recent],
        "NEWS2 pulso (puntos)": [h.get("news2_pulse_points") for h in recent],
    })
    if not df["FC (lpm)"].notna().any():
        st.caption(f"FC: {NO_DATA} en todos los momentos; no se grafica una línea inventada.")
        return
    col1, col2 = st.columns(2)
    col1.line_chart(df.set_index("Momento")[["FC (lpm)"]], use_container_width=True)
    col2.line_chart(df.set_index("Momento")[["NEWS2 pulso (puntos)"]], use_container_width=True)
    st.caption(f"{PROVENANCE_CLINICAL_BADGE} Puntos NEWS2 del pulso ({PROVENANCE_SOURCE_NEWS2}); FC: {_entrada(organism)}.")


def main() -> None:
    # NOTE: st.set_page_config() is already called once by app/main.py at import
    # time — Streamlit allows only one call per script run, so it must not be
    # repeated here even though this module can also run standalone via `run()`.
    init_session()
    organism = st.session_state.twin_shell_organism

    # Piloto 1 de la Fase 2.3 Tanda 1 (2026-08-24): Digital Twin OS no tenía
    # NINGÚN título de módulo (confirmado por el recon -- ni <h1>/<h2> a
    # mano, ni st.header()/st.title()) pese a ser el módulo de la demo. Gana
    # identidad por primera vez, con el sistema de diseño compartido en vez
    # de un estilo ad-hoc.
    render_module_header("Digital Twin OS", icon="🧬", subtitle="El organismo, no un menú — clic en un órgano revela su fisiología.")

    render_sensor_controls(organism)
    render_ambient_header(organism)
    render_organ_grid(organism)
    render_couplings(organism)
    render_neuro_cardiac_composer()
    st.divider()
    render_organ_panel(organism)
    st.divider()

    st.markdown("### 🧭 Herramientas avanzadas")
    render_scenario_and_interventions(organism)
    render_ups_scenario_simulator(organism)
    render_baroreflex_panel({s.value: label for s, label in RICH_SCENARIO_LABELS.items()})
    render_synced_digital_twin_body(organism)
    render_clinical_narrator(organism)
    render_clinical_case_mode(organism)
    render_causal_reasoning(organism)
    render_ml_risk_panel(organism)
    render_ecg_classifier_panel(organism)
    render_risk_assessment(organism)
    render_clinical_export(organism)

    st.divider()
    render_timeline(organism)


def run() -> None:
    """Wrapper entrypoint compatible with importing as `run` from supermodules."""
    return main()
