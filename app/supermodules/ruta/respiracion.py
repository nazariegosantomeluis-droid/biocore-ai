"""Unidad Respiración (T4 de la ruta integrada, 2026-11-18).

Contenido firmado que ya existe (diseño, tabla «Unidad · Contenido firmado que ya existe»): NEWS2 (tema 6 de
`teoria_citada.md`), cómo se mide la respiración, los patrones, Cheyne-Stokes, Biot y la apnea por esfuerzo (con su
fuente), el instrumento de Respiración (`app/instruments/respiracion.py`) y el banco NEWS2 N1–N9. Lo único que se
escribe aquí son rótulos de interfaz y frases que describen los datos del paciente.

Cierre: la SpO₂ y la FR de tu paciente mueven sus puntos NEWS2 (misma tabla de la plataforma, RCP 2017), y el
Detective con sus casos de hipoxia y apnea.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.supermodules.ruta import common
from app.supermodules.ruta import model as M

UNIT_KEY = "respiracion"
UNIT_TITLE = "Unidad Respiración"
PREFIX = "ruta_respiracion_"
SCENARIOS = ("healthy", "hypoxia", "apnea", "copd")

MIDE_NOTE = ("El patrón respiratorio es una simulación que empieza en la FR y la SpO₂ basal de tu paciente. Al guardar, "
             "su FR medida en la señal y la SpO₂ basal del modelo pasan a tu paciente como simulación.")
NEWS2_NOTE = ("Puntos de cada lectura con la tabla NEWS2 de la plataforma (RCP 2017), la misma del gemelo y de "
              "Calculadoras. Es un componente por lectura, nunca un total NEWS2.")
DETECTIVE_NOTE = ("El Detective usa sus propios casos del banco (entre ellos hipoxia y apnea), no a tu paciente: pide "
                  "pistas, mira los puntos NEWS2 de cada signo y propone un diagnóstico.")


def station_patient() -> None:
    common.render_patient_station(UNIT_KEY, UNIT_TITLE, PREFIX, SCENARIOS)


def station_concept_news2() -> None:
    from app.supermodules import learn_theory as LT

    common.render_theory(LT.SIGNED_NEWS2, LT.NEWS2_RESP)


def station_concept_patterns() -> None:
    from app.supermodules import learn_theory as LT

    common.render_theory(LT.HOW_MEASURED, LT.PATTERNS, LT.SIGNED_CHEYNE_STOKES, LT.SIGNED_BIOT, LT.APNEA_BY_EFFORT)


def _out_of_range(vitals) -> list:
    from app.instruments import respiracion as R

    return common.out_of_control_range(vitals, (("rr", "FR", "rpm", R.RR_RANGE),
                                                ("spo2", "SpO₂", "%", R.SPO2_BASAL_RANGE)))


def station_measure() -> None:
    from app.instruments import respiracion as R
    from app.instruments.base import station_context
    from app.utils.patient_banner import read_active_vitals

    ctx = station_context(f"{PREFIX}mide")
    out_of_range = _out_of_range(read_active_vitals())
    run = R.patron(ctx)
    if run is None:
        return
    if out_of_range:
        common.render_out_of_range(out_of_range)
    else:
        st.caption(MIDE_NOTE)
    R.valores(ctx, run)
    R.senales(ctx, run)
    R.spo2(ctx, run)
    R.apneas(ctx, run)
    if out_of_range:
        return
    saved = R.guardar(ctx, run.analysis, run.pattern_display)
    common.saved_now(saved.saved_snapshot_id)


def station_practice() -> None:
    from educational.quiz_bank import NEWS2_QUESTIONS

    st.markdown("#### Preguntas · NEWS2 (N1–N9)")
    common.render_bank_practice(NEWS2_QUESTIONS, "news2", f"{PREFIX}news2_", UNIT_KEY)


def scale2_signed_line() -> str:
    """La línea firmada del tema 6 sobre la escala 2 de la SpO₂ (`learn_theory.SIGNED_NEWS2`), sin texto nuevo."""
    from app.supermodules import learn_theory as LT

    return next(line for line in LT.SIGNED_NEWS2.detail.split("\n") if "escala 2" in line).lstrip("- ")


def render_news2_lines(vitals, scenario: Optional[str] = None) -> None:
    """Los puntos NEWS2 de cada signo de tu paciente, con la función de la plataforma (`news2_reading_note`).

    Revisión final de la T4: en la EPOC la SpO₂ no se puntúa con la escala 1 (el tema 6 firmado dice que ahí puede
    aplicar la escala 2, bajo indicación de un clínico) y la plataforma no modela la escala 2: queda sin puntos."""
    from app.utils.patient_banner import UNIT_ES, VITALS, vital_provenance_text
    from app.utils.design_system import render_no_data
    from clinical.calculators import news2_reading_note

    st.markdown("#### Puntos NEWS2 de tu paciente")
    arg = {"hr": "pulse", "rr": "respiratory_rate", "spo2": "spo2"}
    for key, label, *_rest in VITALS:
        d = vitals.values[key]
        if d is None:
            render_no_data(label, "el UPS no tiene este valor de tu paciente")
            continue
        if key == "spo2" and scenario == "copd":
            note = "sin puntos NEWS2: la plataforma no modela la escala 2 de la SpO₂"
        else:
            note = news2_reading_note(**{arg[key]: d.value}) or "sin puntos NEWS2 calculables"
        st.markdown(f"{label} {d.value:.0f} {UNIT_ES.get(d.unit, d.unit)} "
                    f"({vital_provenance_text(d, vitals.origins.get(key))}) · {note}")
    if scenario == "copd":
        st.caption(f"Tema 6 firmado [RCP2017]: {scale2_signed_line()}")
    st.caption(NEWS2_NOTE)


def station_closing() -> None:
    from app.utils import navigation as nav
    from app.utils.patient_banner import read_active_vitals

    common.render_closing_summary(UNIT_KEY, UNIT_TITLE)
    render_news2_lines(read_active_vitals(), M.progress(UNIT_KEY)["scenario"])
    st.markdown("#### Caso de cierre")
    st.caption(DETECTIVE_NOTE)
    nav.link("detective", "Detective fisiológico")


UNIT = M.Unit(UNIT_KEY, UNIT_TITLE, organ="respiracion", stations=(
    M.Station("paciente", "paciente", "Tu paciente", station_patient, needs_patient=False),
    M.Station("concepto_news2", "concepto", "NEWS2: la FR y la SpO₂", station_concept_news2, needs_patient=False),
    M.Station("concepto_patrones", "concepto", "Cómo se mide y sus patrones", station_concept_patterns,
              needs_patient=False),
    M.Station("mide", "mide", "La respiración de tu paciente", station_measure),
    M.Station("practica", "practica", "Preguntas de NEWS2", station_practice, needs_patient=False),
    M.Station("cierre", "cierre", "Tu paciente al final", station_closing),
), pending=(
    ("La explicación clínica por escenario del Detective", "su texto firmado (hoy dice que está pendiente)"),
))
