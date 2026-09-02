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
    OrganHealthStatus,
    SimulationScenario,
    PredictionEngine,
)
from app.utils.design_system import render_module_header, render_error_state, BADGES
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
from domain.physiology.narrator import is_configured as narrator_is_configured
from domain.physiology.narrator import stream_narration
from domain.physiology.scenarios.rich_engine import (
    create_ephemeral_basal_patient,
    create_ephemeral_case_patient,
    run_rich_scenario,
)
from domain.physiology.state import (
    EventSeverity,
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
from src.signals.signal_sources import ESP32SignalSource

from .ups_body_visual import render_ups_body

ORGAN_ORDER = ["heart", "brain", "lungs", "muscles", "autonomic"]

# Keywords used to route a free-text alert/anomaly string to the organ it
# concerns. Fase 1 (idioma, 2026-08-30): traducidas junto con las frases de
# `digital_twin_organism.py::_detect_anomalies()` que enrutan -- son stems
# (sin sufijo de género) para que calcen con las variantes de la frase real
# ("respirator" calza con "respiratoria"/"respiratorio"). Verificado que
# producen el mismo conjunto de coincidencias que las keywords en inglés
# tenían con el texto en inglés (incluida la coincidencia sobre palabras
# compuestas, p.ej. "respirator" dentro de "cardiorrespiratoria") -- ver
# CHANGELOG.md para la tabla caso por caso.
ORGAN_KEYWORDS = {
    "heart": ["cardiovascular", "corazón", "ritmo"],
    "brain": ["estrés", "somnolencia", "cognitiv", "alerta"],
    "lungs": ["respirator", "spo", "respiraci"],
    "muscles": ["muscular", "fatiga"],
    "autonomic": ["coordinaci", "desacopl", "sincroniz", "autonóm"],
}

# Fase 1 (idioma, 2026-08-30): los valores INTERNOS siguen en inglés a
# propósito -- se comparan en `if mode == "Student":` (render_organ_panel,
# más abajo) y son el valor por defecto de session_state. Traducir el valor
# obligaría a tocar esas comparaciones sin ninguna ganancia (nadie los ve).
# Solo la ETIQUETA visible del radio se traduce, vía `format_func` en
# `render_mode_toggle()`.
MODES = ["Student", "Clinician", "Researcher"]
MODE_LABELS = {"Student": "Estudiante", "Clinician": "Clínico", "Researcher": "Investigador"}

# Fase 1 (idioma, 2026-08-30) + Fase 2 (honestidad, 2026-08-30): `trend`
# nunca se asigna en ningún sitio de `digital_twin_organism.py` (confirmado
# por grep) -- se queda para siempre en su default de dataclass ("stable"),
# nunca "rising"/"falling" en la práctica hoy. Se traducen los 3 por si
# algún día se activa, no solo el que se ve hoy.
TREND_LABELS = {"stable": "Estable", "rising": "Subiendo", "falling": "Bajando"}

# `OrganHealthStatus` (digital_twin_organism.py) ya es una clasificación
# cualitativa REAL de `health_score` (propiedad `organ.status`, 4 niveles,
# umbrales 80/60/40/<40) -- se reutiliza tal cual como la banda cualitativa
# de Fase 2 para Cerebro/Músculos/Autonómico en vez de inventar un tercer
# esquema de cortes para lo mismo. También traduce el campo "Estado" que ya
# se mostraba en inglés (Researcher mode, Fase 1 pendiente).
ORGAN_STATUS_LABELS = {
    OrganHealthStatus.OPTIMAL: "Óptimo",
    OrganHealthStatus.NORMAL: "Normal",
    OrganHealthStatus.ALERT: "Alerta",
    OrganHealthStatus.CRITICAL: "Crítico",
}

# Fase 2 (honestidad de presentación, 2026-08-30): Corazón y Pulmones citan
# un punto de referencia clínico real (PROVENANCE_SOURCE_HEALTHY_ADULT) para
# su health score, aunque los pesos de la fórmula sean heurísticos -- se
# quedan como NÚMERO (con procedencia visible). Cerebro/Músculos/Autonómico
# no citan ninguna referencia -- pasan a banda cualitativa (`organ.status`
# arriba). Ver `_health_score_help()`/`_HEALTH_SCORE_REFERENCE_ORGANS` para
# la misma distinción, ya existente en el código de Tanda 2 (2026-08-14).
ORGANS_WITH_CITED_HEALTH_SCORE = {"heart", "lungs"}


def _qualitative_band(value: float, labels: tuple, high: float = 70.0, low: float = 40.0) -> tuple:
    """Convierte un score 0-100 SIN ancla clínica citada (pesos heurísticos
    puros) en una banda cualitativa de 3 niveles + color. Reutiliza los
    cortes 70/40 que `render_ambient_header()` ya usaba para colorear el
    número de Estado Fisiológico Global -- no se inventa un tercer par de
    umbrales para lo mismo. `labels` = (bajo, medio, alto)."""
    if value >= high:
        return labels[2], "#39ffbe"
    if value >= low:
        return labels[1], "#ffd700"
    return labels[0], "#ff3333"


def _coupling_band(value: float) -> tuple:
    """value 0-1. Corte bajo (<30%) reutiliza el umbral que YA dispara la
    alerta de 'desacoplamiento'/'desincronización' en
    `_detect_anomalies()` (digital_twin_organism.py, `< 0.3`) -- no se
    inventa un umbral nuevo para 'Bajo'. Corte alto (70%) simétrico, mismo
    criterio que el resto de bandas de esta página."""
    return _qualitative_band(value * 100, ("Bajo", "Medio", "Alto"))


# --- Procedencia de los datos del Digital Twin (Tanda 2, 2026-08-14) --------
# Firma: validador clínico, Digital Twin — Tanda 2, dictamen 2026-08-14.
# Puramente aditivo: NINGÚN cálculo de `DigitalTwinOrganism`/`PredictionEngine`
# cambia en esta tanda (ver Tanda 1, CHANGELOG.md, para lo que sí se tocó:
# el `confidence` fachada, ya retirado). Esto solo hace visible en la UI la
# distinción que el validador ya dictaminó entre umbrales con respaldo citado
# (Categoría A) y heurísticas de ingeniería propias de BIOCORE, sin
# validación clínica externa (Categoría B) — mismo principio que
# `Provenance`/`ClinicalReferenceValue` del UPS, adaptado aquí como badge de
# UI en vez de campo persistido, porque estos valores (health scores,
# acoplamientos, PredictionEngine) viven en `DigitalTwinOrganism`/
# `PredictionEngine`, fuera del esquema del UPS — no se inventa un tercer
# sistema de procedencia, se extiende el mismo VOCABULARIO (citado vs. no
# validado) al único lugar donde estos datos realmente viven hoy.
# Fase 2.3 Tanda 3 (2026-08-29): antes 2 literales duplicados 1:1 con
# `BIOMARKER_*_BADGE` de app/main.py -- mismos valores, cero fuente
# compartida (ver design_system.py docstring). Ahora alias de BADGES
# (design_system.py), la fuente única -- ningún valor ni ningún sitio de
# uso más abajo cambia, solo de dónde viene el literal.
PROVENANCE_CLINICAL_BADGE = BADGES.CLINICAL
PROVENANCE_HEURISTIC_BADGE = BADGES.HEURISTIC
PROVENANCE_HEURISTIC_LABEL = "Índice heurístico BIOCORE — no es un score clínico validado"

# Categoría A -- fuentes citadas por el validador para umbrales/constantes
# específicos (verbatim, no parafraseadas). Cada una se usa SOLO donde el
# número en el código coincide exactamente con el umbral citado -- p.ej. la
# HRV<10ms citada aquí es la de `PredictionEngine.assess_cardiovascular_risk`
# (que sí usa 10ms); NO se aplica a `assess_autonomic_risk` (que usa 15/30ms,
# un umbral distinto, no cubierto por este dictamen) ni al `risk_score`
# propio de `DigitalTwinOrganism` (que usa sus propios umbrales, tampoco
# cubiertos -- ver CHANGELOG.md, Tanda 2, para el detalle de por qué no se
# etiquetan como citados).
PROVENANCE_SOURCE_NEWS2 = "NEWS2"
PROVENANCE_SOURCE_ACLS_ATLS = "ACLS/ATLS"
PROVENANCE_SOURCE_AASM = "criterio AASM"
PROVENANCE_SOURCE_AUTONOMIC_DEPRESSION = "depresión autonómica"
PROVENANCE_SOURCE_PRQ = "Pulse-Respiration Quotient (PRQ) en reposo"
PROVENANCE_SOURCE_HEALTHY_ADULT = "valores de referencia de adulto sano"
PROVENANCE_SOURCE_TRIAGE = "filosofía de triaje clínico (el órgano más crítico determina el riesgo vital)"


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
    """The organism's own state IS the dashboard — no separate summary view."""
    state = organism.global_state
    health = state.get("global_health_score", 50.0)
    # Fase 1 (idioma, 2026-08-30): default alineado al vocabulario español
    # de `DigitalTwinOrganism._compute_risk_level()` (BAJO/MODERADO/ALTO/
    # CRÍTICO) -- antes decía "Low" en inglés. En la práctica casi nunca se
    # usa (global_state ya trae risk_level calculado desde el primer
    # render_sensor_controls()), pero si algún día se lee antes de la
    # primera actualización, debe hablar el mismo idioma que el resto.
    risk = state.get("risk_level", "BAJO")
    coherence = state.get("system_coherence", 0.0)
    resilience = state.get("resilience_index", 0.0)
    color = "#39ffbe" if health >= 70 else ("#ffd700" if health >= 40 else "#ff3333")

    # Fase 2 (honestidad de presentación, 2026-08-30): estos 3 números
    # (health/coherence/resilience) son heurística pura sin ancla clínica
    # citada (ver PROVENANCE_HEURISTIC_LABEL más abajo) -- mostrarlos como
    # "64/100"/"74%" en letra grande finge una precisión de medición que no
    # tienen. El CÁLCULO no cambia (sigue siendo el mismo número, usado aquí
    # solo para decidir la banda) -- ver CHANGELOG.md.
    global_label, _ = _qualitative_band(health, ("Crítico", "En observación", "Estable"))
    coherence_label, coherence_color = _qualitative_band(coherence, ("Baja", "Media", "Alta"))
    resilience_label, resilience_color = _qualitative_band(resilience, ("Baja", "Media", "Alta"))

    st.markdown(
        f"""
        <div style='text-align:center; padding: 20px; border-radius: 22px;
                    border: 1px solid {color}55; background: rgba(255,255,255,0.03); margin-bottom: 20px;'>
            <div style='font-size: 12px; letter-spacing: 3px; color: #9fb4c9;'>ESTADO FISIOLÓGICO GLOBAL</div>
            <div style='font-size: 34px; font-weight: 700; color: {color}; line-height: 1.2;'>
                {global_label}
            </div>
            <div style='font-size: 13px; color: #9fb4c9;'>
                Riesgo: <b style='color:{color};'>{risk}</b>
                &nbsp;·&nbsp; Coherencia sistémica: <b style='color:{coherence_color};'>{coherence_label}</b>
                &nbsp;·&nbsp; Resiliencia: <b style='color:{resilience_color};'>{resilience_label}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"{PROVENANCE_CLINICAL_BADGE} Riesgo global = máximo por sistema: {PROVENANCE_SOURCE_TRIAGE} "
        f"· {PROVENANCE_HEURISTIC_BADGE} Estado global, Coherencia sistémica y Resiliencia: "
        f"{PROVENANCE_HEURISTIC_LABEL} -- por eso se muestran como banda cualitativa, no como número "
        f"(valores internos: salud {health:.0f}/100, coherencia {coherence:.0f}%, resiliencia {resilience:.0f}/100)."
    )

    for alert in state.get("alerts", []):
        st.warning(alert)


def render_organ_grid(organism: DigitalTwinOrganism) -> None:
    """Organ-click is the primary verb — this replaces the menu."""
    st.markdown("#### Toca un órgano para explorar su fisiología")
    cols = st.columns(len(ORGAN_ORDER))

    for col, organ_id in zip(cols, ORGAN_ORDER):
        organ = organism.organs[organ_id]
        selected = st.session_state.twin_shell_selected_organ == organ_id
        border = f"3px solid {organ.color}" if selected else "1px solid rgba(255,255,255,0.14)"

        # Fase 2 (honestidad de presentación, 2026-08-30): Corazón/Pulmones
        # citan un punto de referencia clínico real -- se quedan como
        # número, con el badge de procedencia VISIBLE junto al número (antes
        # solo en el caption de abajo). Cerebro/Músculos/Autonómico no citan
        # ninguna referencia -- pasan a la banda cualitativa que
        # `organ.status` (OrganHealthStatus, ya calculado) ya representa, en
        # vez de un número de falsa precisión. El health_score SIGUE
        # calculándose igual en ambos casos -- solo cambia qué se muestra.
        if organ_id in ORGANS_WITH_CITED_HEALTH_SCORE:
            value_html = (
                f"<div style='font-size: 22px; color: {organ.color}; font-weight: 700;'>"
                f"{organ.metrics.health_score:.0f}</div>"
                f"<div style='font-size: 10px; color: #9fb4c9;'>🟢🔵 con ancla</div>"
            )
        else:
            status_label = ORGAN_STATUS_LABELS[organ.status]
            value_html = (
                f"<div style='font-size: 15px; color: {organ.color}; font-weight: 700; margin-top: 6px;'>"
                f"{status_label}</div>"
                f"<div style='font-size: 10px; color: #9fb4c9;'>🔵 heurística</div>"
            )

        with col:
            st.markdown(
                f"""
                <div style='text-align:center; padding: 16px 8px; border-radius: 18px; border: {border};
                            background: rgba(255,255,255,0.03);'>
                    <div style='font-size: 34px;'>{organ.icon}</div>
                    <div style='font-weight: 600; font-size: 12px; margin-top: 4px;'>{organ.name}</div>
                    {value_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Explorar", key=f"twin_shell_select_{organ_id}", use_container_width=True):
                st.session_state.twin_shell_selected_organ = organ_id
                st.rerun()

    st.caption(
        f"{PROVENANCE_HEURISTIC_BADGE} Health scores: {PROVENANCE_HEURISTIC_LABEL} "
        f"(Corazón y Pulmones citan sus centros de referencia — {PROVENANCE_SOURCE_HEALTHY_ADULT} — "
        "pero los pesos de la fórmula no; por eso se muestran como número con procedencia visible. "
        "Cerebro/Músculos/Autonómico no citan ninguna referencia -- se muestran como banda cualitativa, "
        "no como número, para no fingir precisión.)"
    )


def render_sensor_controls(organism: DigitalTwinOrganism) -> None:
    """Lets the shell be explored/demoed live without real hardware attached."""
    with st.expander("🎛️ Ajustar señales fisiológicas (simulación)"):
        col1, col2, col3 = st.columns(3)
        with col1:
            hr = st.slider("Frecuencia cardíaca (bpm)", 40, 180, 72, key="twin_shell_hr")
            hrv = st.slider("HRV (ms)", 5, 120, 50, key="twin_shell_hrv")
        with col2:
            rr = st.slider("Frecuencia respiratoria (resp/min)", 8, 40, 16, key="twin_shell_rr")
            spo2 = st.slider("SpO₂ (%)", 70, 100, 98, key="twin_shell_spo2")
        with col3:
            stress = st.slider("Estrés (EEG)", 0, 100, 35, key="twin_shell_stress")
            fatigue = st.slider("Fatiga muscular (EMG)", 0, 100, 20, key="twin_shell_fatigue")

        organism.update_from_sensors({
            "ecg": {"heart_rate": hr, "hrv": hrv},
            "eeg": {"stress_level": stress, "alpha_power": max(0, 70 - stress * 0.5)},
            "respiratory": {"respiratory_rate": rr, "spo2": spo2},
            "emg": {"fatigue_index": fatigue, "efficiency": max(0, 100 - fatigue)},
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


_HEALTH_SCORE_REFERENCE_ORGANS = {
    "heart": "Centro de referencia (FC 70bpm)",
    "lungs": "Centros de referencia (FR 16, SpO2 100%)",
}


def _health_score_help(organ_id: str) -> str:
    reference = _HEALTH_SCORE_REFERENCE_ORGANS.get(organ_id)
    if reference:
        return (
            f"{PROVENANCE_CLINICAL_BADGE} {reference}: {PROVENANCE_SOURCE_HEALTHY_ADULT} · "
            f"{PROVENANCE_HEURISTIC_BADGE} pesos de la fórmula: {PROVENANCE_HEURISTIC_LABEL}"
        )
    return f"{PROVENANCE_HEURISTIC_BADGE} {PROVENANCE_HEURISTIC_LABEL}"


_ORGAN_RISK_SCORE_HELP = (
    f"{PROVENANCE_HEURISTIC_BADGE} Umbrales propios de DigitalTwinOrganism, distintos de los de "
    f"PredictionEngine (ver 'Evaluación de riesgo detallada por sistema') — {PROVENANCE_HEURISTIC_LABEL}"
)


def _health_score_metric_args(organ_id: str, organ, base_label: str = "Salud") -> tuple:
    """Fase 2 (honestidad de presentación, 2026-08-30): (label, value, help)
    para el st.metric de salud de un órgano -- mismo criterio que
    `render_organ_grid()`. Corazón/Pulmones citan un punto de referencia
    real: número con el badge de procedencia integrado en la ETIQUETA
    (visible, no solo en el tooltip). Cerebro/Músculos/Autonómico no citan
    nada: banda cualitativa (`organ.status`, ya calculado) en vez de un
    número de falsa precisión -- el `health_score` real queda en el help,
    no escondido, solo no es lo que se lee primero."""
    help_text = _health_score_help(organ_id)
    if organ_id in ORGANS_WITH_CITED_HEALTH_SCORE:
        return f"🟢🔵 {base_label}", f"{organ.metrics.health_score:.0f}/100", help_text
    status_label = ORGAN_STATUS_LABELS[organ.status]
    return (
        f"🔵 {base_label}",
        status_label,
        f"{help_text} (valor interno: {organ.metrics.health_score:.0f}/100 -- se muestra como banda, "
        "no como número, para no fingir precisión)",
    )


def render_organ_panel(organism: DigitalTwinOrganism) -> None:
    organ_id = st.session_state.twin_shell_selected_organ
    organ = organism.organs[organ_id]

    st.markdown(f"## {organ.icon} {organ.name}")
    render_mode_toggle()
    mode = st.session_state.twin_shell_mode

    if mode == "Student":
        st.info(organ.education.get("es", "Sin explicación disponible."))
        label, value, help_text = _health_score_metric_args(organ_id, organ, "Salud general")
        st.metric(label, value, help=help_text)

    elif mode == "Clinician":
        col1, col2, col3 = st.columns(3)
        label, value, help_text = _health_score_metric_args(organ_id, organ)
        col1.metric(label, value, help=help_text)
        col2.metric("Riesgo", f"{organ.metrics.risk_score:.0f}/100", help=_ORGAN_RISK_SCORE_HELP)
        # Fase 1 (idioma, pendiente) + Fase 2 (2026-08-30): trend nunca se
        # asigna en ningún sitio del engine (siempre "stable") -- se
        # traduce por completitud, no porque hoy muestre otra cosa.
        col3.metric("Tendencia", TREND_LABELS.get(organ.metrics.trend, organ.metrics.trend))
        st.info(organ.education.get("pathophysiology", ""))
        if organ.metrics.signals:
            st.markdown("**Señales de entrada:**")
            st.json(organ.metrics.signals)

    else:  # Researcher
        col1, col2, col3, col4 = st.columns(4)
        label, value, help_text = _health_score_metric_args(organ_id, organ)
        col1.metric(label, value, help=help_text)
        col2.metric("Riesgo", f"{organ.metrics.risk_score:.0f}/100", help=_ORGAN_RISK_SCORE_HELP)
        col3.metric("Actividad", f"{organ.metrics.activity_level:.0f}/100")
        # Fase 1 (idioma, pendiente): "Estado" mostraba el enum en inglés
        # (organ.status.value.capitalize() -- "Optimal"/"Normal"/"Alert"/
        # "Critical"). Mismo ORGAN_STATUS_LABELS usado arriba para la banda.
        col4.metric("Estado", ORGAN_STATUS_LABELS[organ.status])
        if organ.detail is not None:
            st.markdown("**Parámetros de alta fidelidad:**")
            st.json(organ.detail.__dict__)
        if organ.metrics.signals:
            st.markdown("**Señales crudas:**")
            st.json(organ.metrics.signals)
        if organ.pathologies:
            st.caption("Patologías relacionadas: " + ", ".join(organ.pathologies))

    # AI explanation surfaces directly on the organ, not in a separate chat panel.
    findings = _organ_related_findings(organism, organ_id)
    if findings:
        st.markdown("**🧠 Hallazgos relevantes para este órgano:**")
        for f in findings:
            st.error(f) if "⚠️" in f or "🔴" in f else st.info(f)


def render_couplings(organism: DigitalTwinOrganism) -> None:
    """Cross-system coupling — folded in from the retired Command Center."""
    state = organism.global_state
    st.markdown("#### 🔗 Acoplamientos entre sistemas")
    col1, col2, col3 = st.columns(3)

    # Fase 2 (honestidad de presentación, 2026-08-30): Cerebro↔Corazón y
    # Cerebro↔Músculos son fórmulas propias sin ningún punto de referencia
    # citado -- pasan a banda cualitativa (`_coupling_band`), ya no un "74%"
    # de falsa precisión. Corazón↔Pulmones SÍ cita una razón real (PRQ,
    # 4:1) -- se queda como número, con el badge de procedencia ahora
    # VISIBLE en la etiqueta misma, no solo en el `help=`. El cálculo del
    # acoplamiento (0.0-1.0) no cambia en ningún caso.
    neurocardiac = state.get("neurocardiac_coupling", 0.5)
    nc_label, _ = _coupling_band(neurocardiac)
    col1.metric(
        "🔵 Cerebro ↔ Corazón", nc_label,
        help=f"{PROVENANCE_HEURISTIC_BADGE} {PROVENANCE_HEURISTIC_LABEL} "
             f"(valor interno: {neurocardiac:.0%} -- se muestra como banda, no como número, "
             "para no fingir precisión)",
    )
    col2.metric(
        "🟢🔵 Corazón ↔ Pulmones", f"{state.get('cardiorespiratory_coupling', 0.5):.0%}",
        help=(
            f"{PROVENANCE_CLINICAL_BADGE} Razón HR:RR objetivo (4:1): {PROVENANCE_SOURCE_PRQ} · "
            f"{PROVENANCE_HEURISTIC_BADGE} el índice de acoplamiento en sí (0-100%): {PROVENANCE_HEURISTIC_LABEL}"
        ),
    )
    neuromuscular = state.get("neuromuscular_coupling", 0.5)
    nm_label, _ = _coupling_band(neuromuscular)
    col3.metric(
        "🔵 Cerebro ↔ Músculos", nm_label,
        help=f"{PROVENANCE_HEURISTIC_BADGE} {PROVENANCE_HEURISTIC_LABEL} "
             f"(valor interno: {neuromuscular:.0%} -- se muestra como banda, no como número, "
             "para no fingir precisión)",
    )


def render_scenario_and_interventions(organism: DigitalTwinOrganism) -> None:
    """Patient presets + simulated interventions — folded in from Digital Twin Profesional.

    Fase 5.2 (clarificar nombres, 2026-08-30): antes se llamaba "Escenarios
    de paciente e intervenciones simuladas" -- colisionaba léxicamente con
    "Simulador de escenarios clínicos (persistido en el UPS)"
    (`render_ups_scenario_simulator()`, más abajo), aunque son de naturaleza
    distinta: esta función muta `organism` en memoria al instante (mismo
    botón → `st.rerun()`, sin ningún `save_state`, confirmado por grep) --
    misma familia que los sliders de `render_sensor_controls()`. El
    simulador SÍ persiste una trayectoria de 6 horizontes al UPS. El nombre
    nuevo deja "Escenarios" exclusivamente para el simulador."""
    with st.expander("⚡ Ajustes rápidos e intervenciones (en memoria, sin persistir)"):
        st.markdown("**Preset rápido:**")
        scenarios = {
            "healthy": "🟢 Sano", "hypertension": "🟡 Hipertensión",
            "copd": "🔴 EPOC", "arrhythmia": "⚠️ Arritmia", "sepsis": "🆘 Sepsis",
        }
        cols = st.columns(len(scenarios))
        for col, (key, label) in zip(cols, scenarios.items()):
            with col:
                if st.button(label, key=f"twin_shell_scenario_{key}", use_container_width=True):
                    organism.create_patient_scenario(key)
                    st.rerun()

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
                    st.rerun()


RICH_SCENARIO_LABELS = {
    SimulationScenario.HEALTHY: "🟢 Sano — línea base",
    SimulationScenario.EXERCISE: "🏃 Ejercicio",
    SimulationScenario.STRESS: "😰 Estrés psicológico",
    SimulationScenario.ANXIETY: "😨 Crisis de ansiedad",
    SimulationScenario.ARRHYTHMIA: "🫀 Arritmia cardíaca",
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
    expuesta en esta UI). Ahora los 12 escenarios reales de
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
            "Los 12 escenarios reales de SimulationEngine persisten paso a paso en el Unified "
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

                for step in run_rich_scenario(session, patient_id, scenario_key, organism, start_from_current):
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
                    f"**🧮 PA calculada por el modelo hemodinámico (lazo cerrado, validado):** "
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

    render_ups_body(get_current_physiological_state(organism, patient_id))
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
                "respaldo. Define la variable de entorno para activarlo."
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
                st.write_stream(stream_narration(context, depth))
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
CLINICAL_GROUPS: Dict[str, FrozenSet[SimulationScenario]] = {
    "A_activacion_simpatica_aguda": frozenset({
        SimulationScenario.STRESS,
        SimulationScenario.ANXIETY,
        SimulationScenario.EXERCISE,
        SimulationScenario.SEIZURE,
        SimulationScenario.ARRHYTHMIA,
    }),
    "B_respiratorio_hipoxemico": frozenset({
        SimulationScenario.HYPOXIA,
        SimulationScenario.APNEA,
        SimulationScenario.COPD,
    }),
    "C_hipotension_bajo_gasto_shock": frozenset({
        SimulationScenario.SEPSIS,
        SimulationScenario.ARRHYTHMIA,
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
        return pa_findings

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
    reutilizando TODO lo existente: los 12 escenarios reales
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
            "Se carga uno de los 12 escenarios reales sin revelar cuál. Diagnostica eligiendo "
            "entre 4 opciones; el feedback lo genera el narrador real (Anthropic), fundamentado "
            "únicamente en los descriptores y eventos que el UPS realmente persistió."
        )

        if not narrator_is_configured():
            st.warning(
                "`ANTHROPIC_API_KEY` no está configurada — el feedback fundamentado requiere la "
                "API real de Anthropic, sin narración simulada de respaldo."
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
        render_ups_body(state)

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
                f"**🧮 PA calculada por el modelo hemodinámico (lazo cerrado, validado):** "
                f"{systolic_modelo.value:.0f}/{diastolic_modelo.value:.0f} mmHg "
                f"(PAM {map_modelo.value:.0f} mmHg, confianza {map_modelo.confidence:.0%})"
                + (f" — referencia clínica citada: PAM {ref_map.value:.0f} mmHg" if ref_map else "")
            )
            st.caption(
                "Valor CALCULADO por el modelo a partir del heart_rate real de este caso -- no es una "
                "medición del paciente ni un valor de guía clínica. Solo disponible para sano/"
                "hipertensión/sepsis (los 3 escenarios con validación experta completa del motor "
                "hemodinámico); en el resto de los 12 escenarios este caso no muestra PA calculada."
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
                    feedback_text = "".join(stream_findings_narration(findings_context))
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
                f"El UPS todavía no modela el dominio de **{organ.name}** (solo cardiovascular y "
                "respiratorio) — no hay datos reales sobre los que fundamentar una causa. "
                "Selecciona el corazón o los pulmones para usar el razonamiento causal."
            )
            return

        if not narrator_is_configured():
            st.warning(
                "`ANTHROPIC_API_KEY` no está configurada — el razonamiento causal requiere la "
                "API real de Anthropic, sin narración simulada de respaldo."
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
                st.write_stream(stream_causal_narration(causal_context))
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

    with st.expander("🧬 Riesgo cardiovascular (ML real, desde el UPS)"):
        st.caption(
            "PatientRiskPredictor + AnomalyDetector (src/ai/patient_analytics.py), alimentados "
            "con los descriptores reales del snapshot más reciente del UPS — nunca con datos de "
            "paciente hardcodeados."
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
                "para 10 de los 12 escenarios (no para fatiga crónica ni EPOC) — nunca se rellena con "
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
    explicabilidad SHAP/LIME real (`src/interpretability.py`), integrado al
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
            "detect_clinical_pattern() + SHAP/LIME reales (clinical/ecg_analyzer.py + "
            "src/interpretability.py) sobre una señal real — nunca ruido aleatorio ni un "
            "resultado fijo."
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
        st.markdown("**Explicabilidad (SHAP/LIME real, sobre la señal analizada):**")
        if result.shap_lime:
            tab_shap, tab_lime, tab_importance = st.tabs(["SHAP", "LIME", "Importancia"])
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
                    "Importancia por desviación de baseline (estilo SHAP: |valor-baseline| "
                    "normalizado a 100% entre las features) -- NO es SHAP/LIME real de una "
                    "librería, es la misma heurística que ya narran las pestañas SHAP/LIME."
                )
                importance = result.shap_lime["importance"]
                importance_df = pd.DataFrame(
                    {"Importancia (%)": [item["percent"] for item in importance]},
                    index=[item["label"] for item in importance],
                )
                st.bar_chart(importance_df, use_container_width=True)
        else:
            st.caption(result.explainability_note or "Explicabilidad no disponible.")


# Procedencia por sistema de PredictionEngine (Tanda 2, 2026-08-14) -- solo
# cita el/los factor(es) cuyo umbral en el código coincide EXACTAMENTE con lo
# que el validador citó (ver constantes PROVENANCE_SOURCE_* más arriba).
# Neurological y Muscular no tienen ningún umbral citado por el validador --
# 100% heurística interna. Autonomic usa HRV<15/30ms (no HRV<10ms, el único
# umbral de HRV que sí se citó, y que pertenece a Cardiovascular) -- por
# eso Autonomic tampoco recibe la cita de HRV, se documenta explícitamente
# para que no se confunda con un descuido.
# Bonus (hallazgo de Fase 1, 2026-08-30): "respiratory" es el único de los
# 5 nombres de sistema (claves de `system_risks`, prediction_engine.py) que
# NO es cognado del español -- name.capitalize() mostraba "Respiratory" sin
# traducir. Solo la etiqueta se traduce aquí; las claves de `system_risks`/
# `_RISK_SYSTEM_PROVENANCE` no se tocan.
_SYSTEM_NAME_LABELS = {
    "cardiovascular": "Cardiovascular",
    "respiratory": "Respiratorio",
    "neurological": "Neurológico",
    "muscular": "Muscular",
    "autonomic": "Autonómico",
}

_RISK_SYSTEM_PROVENANCE = {
    "cardiovascular": (
        f"{PROVENANCE_CLINICAL_BADGE} FC extrema: {PROVENANCE_SOURCE_ACLS_ATLS} · "
        f"{PROVENANCE_CLINICAL_BADGE} HRV<10ms: {PROVENANCE_SOURCE_AUTONOMIC_DEPRESSION} · "
        f"{PROVENANCE_HEURISTIC_BADGE} complejidad cardíaca, puntaje combinado y nivel: {PROVENANCE_HEURISTIC_LABEL}"
    ),
    "respiratory": (
        f"{PROVENANCE_CLINICAL_BADGE} SpO2 baja: {PROVENANCE_SOURCE_NEWS2} · "
        f"{PROVENANCE_CLINICAL_BADGE} FR extrema: {PROVENANCE_SOURCE_NEWS2} · "
        f"{PROVENANCE_CLINICAL_BADGE} AHI: {PROVENANCE_SOURCE_AASM} · "
        f"{PROVENANCE_HEURISTIC_BADGE} puntaje combinado y nivel: {PROVENANCE_HEURISTIC_LABEL}"
    ),
    "neurological": f"{PROVENANCE_HEURISTIC_BADGE} {PROVENANCE_HEURISTIC_LABEL} (sin umbral citado por el validador)",
    "muscular": f"{PROVENANCE_HEURISTIC_BADGE} {PROVENANCE_HEURISTIC_LABEL} (sin umbral citado por el validador)",
    "autonomic": (
        f"{PROVENANCE_HEURISTIC_BADGE} {PROVENANCE_HEURISTIC_LABEL} "
        "(usa HRV<15/30ms, distinto del HRV<10ms citado en Cardiovascular)"
    ),
}


def render_risk_assessment(organism: DigitalTwinOrganism) -> None:
    """Detailed per-system risk assessment — folded in from Digital Twin Control."""
    if "twin_shell_prediction" not in st.session_state:
        st.session_state.twin_shell_prediction = PredictionEngine()

    with st.expander("📊 Evaluación de riesgo detallada por sistema"):
        engine = st.session_state.twin_shell_prediction
        heart, brain, lungs, muscles = (
            organism.organs["heart"], organism.organs["brain"],
            organism.organs["lungs"], organism.organs["muscles"],
        )
        sensor_data = {
            "ecg": heart.metrics.signals, "respiratory": lungs.metrics.signals,
            "eeg": brain.metrics.signals, "emg": muscles.metrics.signals,
        }
        assessment = engine.assess_global_risk(organism, sensor_data, organism.timestamp.isoformat())
        st.metric(
            "Riesgo global", f"{assessment.global_risk_score:.0f}/100", delta=assessment.risk_level,
            help=f"{PROVENANCE_HEURISTIC_BADGE} Promedio de los 5 sistemas: {PROVENANCE_HEURISTIC_LABEL}",
        )
        for name, risk in assessment.system_risks.items():
            # Fase 2 (honestidad de presentación, 2026-08-30): Cardiovascular
            # y Respiratorio citan umbrales clínicos reales (ACLS/ATLS,
            # NEWS2, AASM) para sus componentes extremos -- el badge de
            # procedencia ahora va VISIBLE junto al nombre del sistema, no
            # solo en el caption de abajo (que se conserva, con el detalle
            # completo). Neurológico/Muscular/Autonómico no citan ningún
            # umbral (documentado en `_RISK_SYSTEM_PROVENANCE` desde Tanda 2,
            # 2026-08-14) -- fuera del alcance de esta tanda, sin tocar.
            prefix = "🟢🔵 " if name in ("cardiovascular", "respiratory") else ""
            # Bonus (hallazgo de Fase 1, no barrido exhaustivo): "respiratory"
            # es una clave interna en inglés (system_risks, prediction_engine.py)
            # -- name.capitalize() mostraba "Respiratory" sin traducir. Se
            # traduce solo la etiqueta, la clave `name` sigue intacta (se usa
            # para el lookup de `_RISK_SYSTEM_PROVENANCE` dos líneas abajo).
            display_name = _SYSTEM_NAME_LABELS.get(name, name.capitalize())
            st.markdown(f"**{prefix}{display_name}** — {risk.risk_level} ({risk.risk_score:.0f}/100)")
            st.caption(risk.recommendation)
            st.caption(_RISK_SYSTEM_PROVENANCE.get(name, f"{PROVENANCE_HEURISTIC_BADGE} {PROVENANCE_HEURISTIC_LABEL}"))


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
    """Past → Present scrubbing over accumulated history (real, not decorative)."""
    history = organism.history
    if len(history) < 2:
        st.caption("La línea de tiempo se irá construyendo a medida que el organismo reciba nuevas señales.")
        return

    st.markdown("#### 🕐 Línea de tiempo fisiológica")
    recent = history[-50:]
    df = pd.DataFrame({
        "Momento": list(range(len(recent))),
        "Salud Global": [h["global_state"]["global_health_score"] for h in recent],
        "Coherencia": [h["global_state"]["system_coherence"] for h in recent],
    })
    st.line_chart(df.set_index("Momento"), use_container_width=True)


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
    st.divider()
    render_organ_panel(organism)
    st.divider()

    st.markdown("### 🧭 Herramientas avanzadas")
    render_scenario_and_interventions(organism)
    render_ups_scenario_simulator(organism)
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
