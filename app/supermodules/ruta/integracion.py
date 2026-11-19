"""Unidad Integración: el sistema autónomo (T4 de la ruta integrada, 2026-11-18; decisión 6 firmada).

La variabilidad cardiaca une corazón, respiración y cerebro. Las estaciones usan solo lo que ya existe y está firmado:
- los temas B1–B9 de `teoria_citada_2.md` (`HRV_TOPICS`);
- los instrumentos de HRV de la T2 en modo estación;
- los bancos HRV H1–H8 y Hemodinámica G1–G10;
- al cierre, la PA del lazo cerrado del escenario del paciente, con las mismas reglas y rótulos con que la muestra el
  Detective: «en revisión clínica» en sepsis y declinada fuera de la fase de shock (regla firmada del 2026-11-02).

Esa PA se calcula al mostrarla y NO se guarda. Así, abrir el cierre varias veces no escribe filas repetidas.
"""

from __future__ import annotations

import streamlit as st

from app.supermodules.ruta import common
from app.supermodules.ruta import model as M

UNIT_KEY = "integracion"
UNIT_TITLE = "Unidad Integración"
PREFIX = "ruta_integracion_"

MIDE_NOTE = ("La serie RR es una simulación con arritmia sinusal respiratoria (RSA) que empieza en la FC y la FR de tu "
             "paciente. Al guardar, su FC y su «hrv» (desde la SDNN) pasan a tu paciente como simulación.")
MANUAL_NOTE = "Serie RR pegada a mano: al guardar, su FC y su «hrv» (desde la SDNN) pasan a tu paciente como simulación."
PA_NOTE = ("Calculada ahora por el modelo de lazo cerrado a partir de la FC de tu paciente: no es una medición y no se "
           "guarda. Solo existe en sano, hipertensión y sepsis.")


def station_patient() -> None:
    common.render_patient_station(UNIT_KEY, UNIT_TITLE, PREFIX)


def station_concept() -> None:
    from app.supermodules import learn_theory as LT

    common.render_theory(*LT.HRV_TOPICS)


def station_measure() -> None:
    from app.instruments import hrv
    from app.instruments.base import station_context

    from app.utils.patient_banner import read_active_vitals

    ctx = station_context(f"{PREFIX}mide")
    out_of_range = _out_of_simulation_range(read_active_vitals())
    series = hrv.rr_source(ctx)
    if series is None:
        return
    if series.source == hrv.MANUAL_SOURCE:
        st.caption(MANUAL_NOTE)
        out_of_range = []
    elif out_of_range:
        # Revisión final de la T4: la serie no empezó en el paciente (p. ej. la FC de la sepsis, 150, no cabe en 40–140).
        st.warning("; ".join(out_of_range) + ". La serie empieza en otro valor, así que esta estación no ofrece guardar: "
                   "no se le escribe a tu paciente una FC que no es la suya.")
    else:
        st.caption(MIDE_NOTE)
    temporal = hrv.tiempo(ctx, series).values
    hrv.frecuencia(ctx, series)
    hrv.rsa(ctx, series)
    if out_of_range:
        return
    saved = hrv.guardar(ctx, series, temporal["sdnn"], temporal["mean_nn"])
    common.saved_now(saved.saved_snapshot_id)


def _out_of_simulation_range(vitals) -> list:
    """Qué valor del paciente no cabe en los controles de la simulación con RSA (entonces la serie no empieza en él)."""
    from app.instruments import hrv

    problems = []
    for key, label, unit, (lo, hi) in (("hr", "FC", "lpm", hrv.HR_BASE_RANGE),
                                       ("rr", "FR", "rpm", hrv.RESP_RATE_RANGE)):
        d = vitals.values[key]
        if d is not None and not lo <= round(d.value) <= hi:
            problems.append(f"La {label} de tu paciente ({d.value:.0f} {unit}) está fuera del rango de la simulación "
                            f"({lo}–{hi} {unit})")
    return problems


def station_practice_hrv() -> None:
    from educational.quiz_bank import HRV_QUESTIONS

    st.markdown("#### Preguntas · Variabilidad cardiaca (H1–H8)")
    common.render_bank_practice(HRV_QUESTIONS, "hrv", f"{PREFIX}hrv_", UNIT_KEY)


def station_practice_hemo() -> None:
    from educational.quiz_bank import HEMO_QUESTIONS

    st.markdown("#### Preguntas · Hemodinámica (G1–G10)")
    common.render_bank_practice(HEMO_QUESTIONS, "hemodinamica", f"{PREFIX}hemo_", UNIT_KEY)


def _render_closed_loop_pa(scenario: str) -> None:
    """La PA del escenario del paciente, con las reglas y los rótulos del Detective (`render_clue`, pista «pa»)."""
    from app.supermodules.detective.pages import PA_IN_REVIEW_LABEL, SEPSIS_PA_IN_REVIEW
    from app.supermodules.twin_shell.baroreflex_panel import pa_model_label
    from app.utils.design_system import render_no_data
    from app.utils.patient_banner import read_active_vitals, vital_provenance_text
    from domain.physiology.hemodynamics.closed_loop import run_closed_loop
    from domain.physiology.hemodynamics.closed_loop_ups_bridge import HEMODYNAMIC_MODEL_ENABLED_SCENARIOS
    from domain.physiology.state import horizon_of
    from src.clinical import sepsis_trajectory

    st.markdown("#### Presión arterial del lazo cerrado")
    vitals = read_active_vitals()
    hr = vitals.values["hr"]
    if scenario not in HEMODYNAMIC_MODEL_ENABLED_SCENARIOS:
        render_no_data("Presión arterial", "no modelada para este escenario: el lazo cerrado solo está habilitado en "
                                           "sano, hipertensión y sepsis")
        return
    if hr is None:
        render_no_data("Presión arterial", "el UPS no tiene una FC de tu paciente con la que calcularla")
        return
    if scenario == "sepsis":
        # La fase sale del horizonte con que se guardó la FC. Si la FC ya no viene de la trayectoria (otra estación
        # la guardó), la fase no se identifica y tampoco se asume shock.
        origin = vitals.origins.get("hr")
        horizon = origin.horizon if origin is not None and origin.horizon else horizon_of(hr.source_detail)
        phase = None if horizon is None else sepsis_trajectory.phase_of(horizon)
        if phase not in sepsis_trajectory.PA_MODEL_PHASES:
            render_no_data("Presión arterial",
                           "se declina fuera de la fase de shock de la sepsis o si la fase no se identifica: "
                           + sepsis_trajectory.PA_DECLINATION_REASON)
            return
    result = run_closed_loop(scenario, hr.value)
    in_review = scenario == "sepsis"
    st.markdown(f"**PA calculada ({pa_model_label()})" + (f" — {PA_IN_REVIEW_LABEL}" if in_review else "")
                + f":** {result.final_systolic_bp:.0f}/{result.final_diastolic_bp:.0f} mmHg "
                  f"(PAM {result.final_map:.0f} mmHg)")
    if in_review:
        st.caption(SEPSIS_PA_IN_REVIEW)
    st.caption(f"{PA_NOTE} FC usada: {hr.value:.0f} lpm · {vital_provenance_text(hr, vitals.origins.get('hr'))}.")


def station_closing() -> None:
    from app.utils import navigation as nav

    common.render_closing_summary(UNIT_KEY, UNIT_TITLE)
    _render_closed_loop_pa(M.progress(UNIT_KEY)["scenario"])
    st.markdown("#### Caso de cierre")
    st.caption("El Detective usa sus propios casos del banco (los 15 escenarios), no a tu paciente.")
    nav.link("detective", "Detective fisiológico")


UNIT = M.Unit(UNIT_KEY, UNIT_TITLE, organ="autonomo", stations=(
    M.Station("paciente", "paciente", "Tu paciente", station_patient, needs_patient=False),
    M.Station("concepto", "concepto", "La variabilidad cardiaca", station_concept, needs_patient=False),
    M.Station("mide", "mide", "La variabilidad de tu paciente", station_measure),
    M.Station("practica_hrv", "practica", "Preguntas de variabilidad cardiaca", station_practice_hrv,
              needs_patient=False),
    M.Station("practica_hemo", "practica", "Preguntas de hemodinámica", station_practice_hemo, needs_patient=False),
    M.Station("cierre", "cierre", "Tu paciente al final", station_closing),
))
