"""Instrumentos de Respiración (T4 de la ruta integrada, 2026-11-18).

El código se movió tal cual desde `app/supermodules/respiratory_lab/page_content.py`: ningún cálculo, texto, cita ni
compuerta cambió. La página de siempre es ahora la composición de estos instrumentos con `PAGE` (mismos controles sin
clave en el menú lateral, misma identidad de widget); una estación de la ruta los monta con `station_context(prefijo)`.

- `patron`: controles, validación, generación y análisis (el generador es el ground truth). `None` con parámetros
  imposibles (el error ya está junto al control).
- `valores`: la fila de valores clave con su insignia.
- `senales`, `spo2`, `apneas`, `resumen`: las vistas de siempre.
- `guardar`: el único camino de escritura al UPS (`views.render_save_to_twin` → `views.build_twin_state`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app.instruments.base import InstrumentContext, InstrumentResult
from app.supermodules.respiratory_lab import views
from app.utils.design_system import BADGES, PALETTE, render_metric_card, render_section_header
from src.signals.respiration import (
    ImpossibleParameters,
    RespiratoryAnalyzer,
    RespiratoryPattern,
    RespiratorySignalGenerator,
)

RESPIRATORY_PATTERNS = {
    "Normal (respiración tranquila)": "normal",
    "Taquipnea (respiración rápida)": "tachypnea",
    "Bradipnea (respiración lenta)": "bradypnea",
    "Apnea Central": "apnea_central",
    "Apnea Obstructiva": "apnea_obstructive",
    "Cheyne-Stokes": "cheyne_stokes",
    "Respiración Atáxica": "ataxic",
}
# Rangos de los controles (con nombre para que una estación los lea). T4.1 (2026-11-18, decisión de Luis): la SpO₂ basal
# baja hasta 70 % para que el instrumento empiece en la SpO₂ de los escenarios de hipoxia (80 %), apnea (82 %) y EPOC
# (85 %); antes empezaba en 90 % y la estación no podía guardar. El generador solo exige que el piso quede por debajo.
RR_RANGE = (6, 40)
SPO2_BASAL_RANGE = (70, 100)
SPO2_FLOOR_DEFAULT = 85            # el piso de siempre; con una basal ≤ 85 % empieza 5 puntos por debajo de la basal


@dataclass
class RespRun:
    pattern: str
    pattern_display: str
    circulation_delay: float
    duration: int
    data: Any
    analysis: Any


def _build_params(pattern, rr, tv, insp, exp, baseline, floor, tc):
    return RespiratoryPattern(
        respiratory_rate=rr,
        tidal_volume=tv,
        inspiration_time=insp,
        expiration_time=(exp if exp > 0 else None),
        pattern_type=pattern,
        baseline_spo2=baseline,
        desaturation_level=floor,
        circulation_delay=tc,
        cheyne_stokes_cycle=60.0,
    )


# Generate respiratory signal
@st.cache_data
def generate_respiration_data(pattern, rr, tv, insp, exp, baseline, floor, tc, duration):
    generator = RespiratorySignalGenerator(sampling_rate=100)
    params = _build_params(pattern, rr, tv, insp, exp, baseline, floor, tc)
    return generator.generate_respiration(duration=duration, params=params)


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


def patron(ctx: InstrumentContext) -> Optional[RespRun]:
    panel = ctx.panel
    k = ctx.auto_key

    # Pattern selection
    selected_pattern_display = panel.selectbox(
        f"{ctx.deco('🫁')}Seleccionar Patrón Respiratorio",
        list(RESPIRATORY_PATTERNS.keys()),
        index=0,
        key=k("resp_pattern"),
    )
    selected_pattern = RESPIRATORY_PATTERNS[selected_pattern_display]

    panel.markdown(f"### {ctx.deco('⚙️')}Parámetros Respiratorios")

    # Respiratory parameters
    col1, col2 = panel.columns(2)

    # Integración (2026-11-17): la FR y la SpO₂ basal EMPIEZAN en las del paciente activo del UPS (si las tiene y caben
    # en el rango del control); sin paciente, el laboratorio se ve como siempre. Ver `patient_start_value`.
    from app.utils.patient_banner import patient_start_value
    _rr_start, _rr_note = patient_start_value("rr", *RR_RANGE, 15, "FR")
    _spo2_start, _spo2_note = patient_start_value("spo2", *SPO2_BASAL_RANGE, 98, "SpO₂ basal")

    with col1:
        rr = st.number_input(
            "Frecuencia Respiratoria (resp/min)",
            min_value=RR_RANGE[0],
            max_value=RR_RANGE[1],
            value=int(_rr_start),
            step=1,
            help="12–20 resp/min puntúa 0 en NEWS2 (RCP 2017)",
            key=k("resp_rr"),
        )

    with col2:
        tv = st.number_input(
            "Volumen Corriente (L)",
            min_value=0.1,
            max_value=1.5,
            value=0.5,
            step=0.1,
            help="Volumen corriente que pide la simulación (la escala de la señal no está calibrada)",
            key=k("resp_tv"),
        )

    # Un ValueError por parámetros imposibles se muestra JUNTO al control afectado (sin st.stop(): las demás pestañas
    # se siguen dibujando). Cada ranura se rellena más abajo si la validación falla.
    slot_rr = panel.empty()
    if _rr_note:
        panel.caption(_rr_note)

    col3, col4 = panel.columns(2)

    with col3:
        insp_time = st.number_input(
            "Tiempo Inspiración (s)",
            min_value=0.3,
            max_value=3.0,
            value=1.0,
            step=0.1,
            key=k("resp_insp"),
        )

    with col4:
        # Arco respiratorio, fase 2a (2026-11-07): el control vuelve a estar activo porque el generador ya
        # lo usa. 0.0 = automático: la espiración ocupa el resto del ciclo (lo que el generador hacía siempre,
        # cuando este control no hacía nada). Un valor > 0 acota el flujo espiratorio a esa duración y deja
        # el resto del ciclo en pausa; inspiración + espiración no pueden superar el ciclo (60 / FR).
        exp_time = st.number_input(
            "Tiempo Espiración (s)",
            min_value=0.0,
            max_value=3.0,
            value=0.0,
            step=0.1,
            help="0 = automático (resto del ciclo). Un valor > 0 acota la espiración y deja pausa telespiratoria; "
                 "inspiración + espiración deben caber en el ciclo (60 / FR).",
            key=k("resp_exp"),
        )

    slot_insp = panel.empty()

    # SpO2 parameters
    panel.markdown(f"### {ctx.deco('🫀')}Parámetros de Oxigenación")
    panel.caption(
        f"{views.SPO2_PROVENANCE}. La SpO₂ es estable sin eventos; cada apnea produce una desaturación en el dedo "
        "con retardo Tc (la latencia de las reservas de O₂ no está modelada)."
    )

    col5, col6 = panel.columns(2)

    with col5:
        baseline_spo2 = st.number_input(
            "SpO2 Basal (%)",
            min_value=SPO2_BASAL_RANGE[0],
            max_value=SPO2_BASAL_RANGE[1],
            value=int(_spo2_start),
            step=1,
            help="SpO₂ basal que simula el modelo BIOCORE",
            key=k("resp_spo2_basal"),
        )

    with col6:
        min_spo2 = st.number_input(
            "SpO2 Mínimo (%)",
            min_value=50,
            max_value=95,
            value=SPO2_FLOOR_DEFAULT if _spo2_start > SPO2_FLOOR_DEFAULT else int(_spo2_start) - 5,
            step=1,
            help="Piso de la SpO₂ durante un evento (nunca baja de aquí)",
            key=k("resp_spo2_min"),
        )

    if _spo2_note:
        panel.caption(_spo2_note)

    circulation_delay = panel.number_input(
        "Retardo circulatorio Tc (s) — Valor BIOCORE",
        min_value=5.0,
        max_value=30.0,
        value=15.0,
        step=1.0,
        help="Tiempo pulmón-dedo: el nadir llega al FIN del evento + Tc. Valor BIOCORE: la fuente (Hsia 2026) solo da el "
             "límite normal < 20 s. Rango 5–30 s.",
        key=k("resp_tc"),
    )
    panel.caption(f"{BADGES.tag(BADGES.METHOD)} Tc: {views.TC_LABEL}")
    slot_spo2 = panel.empty()

    duration = panel.slider(
        f"{ctx.deco('⏱️')}Duración Grabación (s)",
        min_value=30,
        max_value=300,
        value=120,
        step=10,
        key=k("resp_duration"),
    )
    slot_dur = panel.empty()

    # Validación ANTES de generar: el error sale junto al control afectado y la vista clínica se omite sin detener el
    # resto de la página (ver VistaClinicaOmitida en pages.py).
    _params = _build_params(selected_pattern, rr, tv, insp_time, exp_time, baseline_spo2, min_spo2, circulation_delay)
    try:
        RespiratorySignalGenerator.validate_parameters(_params, duration)
    except ImpossibleParameters as _err:
        _slot = {
            "respiratory_rate": slot_rr, "tidal_volume": slot_rr,
            "inspiration_time": slot_insp, "expiration_time": slot_insp,
            "circulation_delay": slot_spo2, "desaturation_level": slot_spo2, "desaturation_rate": slot_spo2,
            "resaturation_rate": slot_spo2, "duration": slot_dur,
        }.get(_err.control, slot_insp)
        _slot.error(f"{ctx.deco('⛔')}{_err}")
        where = "en esta estación" if ctx.in_station else "en la barra lateral"
        st.error(f"{ctx.deco('⛔')}La vista clínica no se dibuja con estos parámetros: corrige el control marcado {where}.")
        if not ctx.in_station:
            st.session_state.pop('_respiratory_lab_analysis', None)  # que Investigación no muestre OTROS parámetros
        return None

    respiration_data = generate_respiration_data(
        selected_pattern, rr, tv, insp_time, exp_time, baseline_spo2, min_spo2, circulation_delay, duration
    )
    # Perform analysis
    analysis = analyze_respiration_data(respiration_data['airflow'], respiration_data['time'],
                                        respiration_data['spo2'], respiration_data['chest_wall'])
    return RespRun(selected_pattern, selected_pattern_display, circulation_delay, duration, respiration_data, analysis)


def valores(ctx: InstrumentContext, run: RespRun) -> None:
    analysis = run.analysis
    render_section_header(f"Patrón: {run.pattern_display}")
    st.caption(f"Insignias por valor: {views.BADGE_LEGEND}")

    # Fase 3 (2026-11-07, Art. I): solo valores con golden test. Sin tarjetas de patrón ni severidad (ocultas).
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        views.render_rate_cards(analysis)

    with col2:
        if analysis.cycle_duration_s is None:
            render_metric_card("Duración del ciclo", None, unavailable_reason=analysis.signal_status_detail or "sin FR disponible")
        else:
            render_metric_card("Duración del ciclo", f"{analysis.cycle_duration_s:.2f} s", provenance=BADGES.METHOD)

    with col3:
        if analysis.apnea_count is None:
            render_metric_card("Apneas (≥ 10 s)", None, unavailable_reason="no evaluable: sin señal respiratoria")
        else:
            render_metric_card("Apneas (≥ 10 s)", f"{analysis.apnea_count}", provenance=BADGES.METHOD)

    with col4:
        render_metric_card(
            "SpO2 Mínimo", f"{analysis.minimum_spo2:.1f}%", provenance=BADGES.METHOD, citation=views.SPO2_PROVENANCE,
        )


def senales(ctx: InstrumentContext, run: RespRun) -> None:
    analysis = run.analysis
    time_array, airflow = run.data['time'], run.data['airflow']
    chest, abdomen = run.data['chest_wall'], run.data['abdomen']
    st.markdown("### Señales Respiratorias (Flujo, Pared Torácica, Abdomen)")

    # Create respiratory signals visualization
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        subplot_titles=("Flujo de Aire (unidades relativas: la escala absoluta no corresponde al volumen corriente elegido)", "Pared Torácica", "Movimiento Abdominal"),
        vertical_spacing=0.1
    )

    # Airflow
    fig.add_trace(
        go.Scatter(
            x=time_array,
            y=airflow,
            name="Flujo de Aire",
            line=dict(color=PALETTE.ACCENT_ON_DARK, width=2),
            fill="tozeroy",
            fillcolor="rgba(142, 202, 230, 0.2)"
        ),
        row=1, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color=PALETTE.NEUTRAL, row=1, col=1)

    # Chest wall
    fig.add_trace(
        go.Scatter(
            x=time_array,
            y=chest,
            name="Pared Torácica",
            line=dict(color=PALETTE.PRIMARY, width=2),
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
            line=dict(color=PALETTE.SERIES_2, width=2),
            fill="tozeroy",
            fillcolor="rgba(124, 58, 237, 0.2)"
        ),
        row=3, col=1
    )

    fig.update_xaxes(title_text="Tiempo (segundos)", row=3, col=1)
    fig.update_yaxes(title_text="Flujo (u. relativas)", row=1, col=1)
    fig.update_yaxes(title_text="Movimiento", row=2, col=1)
    fig.update_yaxes(title_text="Movimiento", row=3, col=1)

    fig.update_layout(
        height=700,
        template="plotly_dark",
        paper_bgcolor=PALETTE.BACKGROUND,
        plot_bgcolor=PALETTE.SECONDARY_BACKGROUND,
        font=dict(color=PALETTE.TEXT),
        showlegend=True,
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True, key=ctx.auto_key("resp_signals_chart"))

    # Detected breaths summary
    st.markdown(f"#### {ctx.deco('📊')}Resumen de Respiraciones Detectadas")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_metric_card("Respiraciones detectadas", f"{len(analysis.breaths)}", provenance=BADGES.METHOD)

    with col2:
        if analysis.cycle_duration_s is None:
            render_metric_card("Duración del ciclo", None, unavailable_reason=analysis.signal_status_detail or "menos de 3 respiraciones")
        else:
            render_metric_card("Duración del ciclo (media de los intervalos entre inspiraciones)",
                               f"{analysis.cycle_duration_s:.2f} s", provenance=BADGES.METHOD)

    with col3:
        if analysis.rr_variability is None:
            render_metric_card("Variabilidad de los intervalos", None, unavailable_reason="menos de 3 respiraciones")
        else:
            render_metric_card("Variabilidad de los intervalos (desviación estándar, descriptiva)",
                               f"{analysis.rr_variability:.2f} s", provenance=BADGES.METHOD)

    with col4:
        views.render_band_card(analysis)

    st.caption("La relación I:E no se muestra: todavía no tiene golden test ni criterio firmado.")


def spo2(ctx: InstrumentContext, run: RespRun) -> None:
    time_array, airflow, spo2_arr = run.data['time'], run.data['airflow'], run.data['spo2']
    st.markdown(f"### {ctx.deco('🫀')}Monitoreo de Oximetría (SpO2)")
    st.info(
        f"**{views.SPO2_PROVENANCE}.** Estable sin eventos (basal + ruido); cada apnea anotada desatura el dedo con retardo Tc "
        "(nadir en el FIN del evento + Tc), profundidad r·T con r = 0.30 %/s y recuperación en rampa a 0.70 %/s. La latencia "
        "de las reservas de O₂ no está modelada. Es una simulación, no una medición de un paciente.",
        icon=None if ctx.in_station else "🫀",
    )

    # Create SpO2 visualization
    fig_spo2 = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=("SpO2 simulada — modelo BIOCORE (Tc valor BIOCORE; r y recuperación, Howarth 2026)", "Flujo de Aire (referencia)"),
        vertical_spacing=0.12,
        row_heights=[0.7, 0.3]
    )

    fig_spo2.add_trace(
        go.Scatter(
            x=time_array,
            y=spo2_arr,
            name="SpO2",
            line=dict(color=PALETTE.ACCENT_ON_DARK, width=3),
            fill="tozeroy",
            fillcolor="rgba(142, 202, 230, 0.3)"
        ),
        row=1, col=1
    )

    # Airflow reference
    fig_spo2.add_trace(
        go.Scatter(
            x=time_array,
            y=airflow / np.max(np.abs(airflow)) * 20 + 60 if np.max(np.abs(airflow)) > 0 else np.zeros_like(airflow),
            name="Flujo (normalizado)",
            line=dict(color=PALETTE.NEUTRAL, width=1),
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
        paper_bgcolor=PALETTE.BACKGROUND,
        plot_bgcolor=PALETTE.SECONDARY_BACKGROUND,
        font=dict(color=PALETTE.TEXT),
        showlegend=True,
        hovermode="x unified"
    )

    st.plotly_chart(fig_spo2, use_container_width=True, key=ctx.auto_key("resp_spo2_chart"))

    # SpO2 Statistics
    st.markdown(f"#### {ctx.deco('📊')}Estadísticas de Oxigenación")

    views.render_spo2_cards(run.analysis)


def apneas(ctx: InstrumentContext, run: RespRun) -> None:
    analysis = run.analysis
    st.markdown(f"### {ctx.deco('📈')}Análisis Avanzado")
    st.markdown("#### Apneas (≥ 10 s, caída ≥ 90 % respecto a la línea basal previa)")
    views.render_apnea_cards(analysis)
    views.render_events_table(analysis)
    if analysis.event_period_s is not None:
        st.caption(f"Los eventos se repiten cada ~{analysis.event_period_s:.0f} s (mediana de la separación entre inicios).")
    views.render_pattern_cards(analysis, run.pattern, run.data["ground_truth"])
    views.render_clinical_notes(analysis, run.circulation_delay)
    views.render_calculator_link(decorated=not ctx.in_station)
    views.render_hidden_notice()


def resumen(ctx: InstrumentContext, run: RespRun) -> None:
    analysis = run.analysis
    st.markdown(f"### {ctx.deco('📋')}Resumen Clínico")

    # Fase 3-4 (Art. I): el resumen muestra solo valores con golden test, cada uno con su insignia. Hipopneas, I:E y ODI
    # siguen fuera (ver el aviso de la pestaña Análisis Avanzado); el patrón y las notas son HEURISTIC y no diagnostican.
    col1, col2, col3 = st.columns(3)
    with col1:
        views.render_rate_cards(analysis)
        if analysis.cycle_duration_s is not None:
            render_metric_card("Duración del ciclo", f"{analysis.cycle_duration_s:.2f} s", provenance=BADGES.METHOD)

    with col2:
        if analysis.apnea_count is None:
            render_metric_card("Apneas (≥ 10 s)", None, unavailable_reason="no evaluable: sin señal respiratoria")
        else:
            render_metric_card("Apneas (≥ 10 s)", f"{analysis.apnea_count}  ·  tiempo total {analysis.apnea_total_time_s:.1f} s",
                               provenance=BADGES.METHOD)
            render_metric_card("Tasa equivalente por hora de registro (extrapolada, sin valor diagnóstico)",
                               f"{analysis.equivalent_rate_per_hour:.0f} /h", provenance=BADGES.METHOD)

    with col3:
        render_metric_card("SpO2 basal", f"{analysis.baseline_spo2:.1f}%", provenance=BADGES.METHOD, citation=views.SPO2_PROVENANCE)
        render_metric_card("SpO2 mínima", f"{analysis.minimum_spo2:.1f}%", provenance=BADGES.METHOD, citation=views.SPO2_PROVENANCE)

    st.markdown(f"**Patrón** {BADGES.tag(BADGES.HEURISTIC)}: {views.pattern_description(analysis)}")
    views.render_clinical_notes(analysis, run.circulation_delay)
    st.caption("Hipopneas, relación I:E y ODI no se muestran (sin criterio firmado o sin golden test).")


def guardar(ctx: InstrumentContext, analysis, pattern_display: str) -> InstrumentResult:
    """El botón explícito de siempre (`views.render_save_to_twin`). Con `PAGE`, la clave es la de siempre
    (`respiratory_lab_save_to_ups`). `saved_snapshot_id` dice qué snapshot se escribió en este rerun (o `None`)."""
    snapshot_id = views.render_save_to_twin(analysis, pattern_display, key=ctx.k("respiratory_lab_save_to_ups"),
                                            decorated=not ctx.in_station)
    return InstrumentResult(saved_snapshot_id=snapshot_id)
