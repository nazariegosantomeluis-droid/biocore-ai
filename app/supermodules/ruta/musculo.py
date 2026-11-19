"""Unidad Músculo (T4 de la ruta integrada, 2026-11-18).

Contenido firmado que ya existe: los temas A1–A9 de `teoria_citada_2.md`, el instrumento de EMG
(`app/instruments/emg.py`: la «activación muscular», que NO es %MVC, y el RMS con su tema A5) y el banco E1–E10.

Cierre (decisión 3 firmada: escenario de fatiga y contracción isométrica con la respuesta autonómica): el paciente
puede empezar en el escenario de fatiga del simulador (que fija su FC, FR y SpO₂; el simulador no genera EMG) y el EMG se
mide con la señal demo, patrón «Isométrica» o «Fatiga». La
respuesta de la FC a la contracción NO se calcula: su regla (músculo → autonómico) está en
`docs/contenido/fichas_acoplamientos.md` como borrador sin firmar, y la «activación» de hoy no es un % de la contracción
máxima. La estación lo dice en vez de mostrar una cifra.
"""

from __future__ import annotations

import streamlit as st

from app.supermodules.ruta import common
from app.supermodules.ruta import model as M

UNIT_KEY = "musculo"
UNIT_TITLE = "Unidad Músculo"
PREFIX = "ruta_musculo_"
SCENARIOS = ("healthy", "fatigue")

MIDE_NOTE = ("La señal EMG es la demo del laboratorio (o un CSV, que no se guarda). Al guardar, la «activación "
             "muscular» y la frecuencia mediana pasan a tu paciente como simulación.")
START_NOTE = ("El simulador no genera EMG: el escenario fija la FC, la FR y la SpO₂ de tu paciente, y su EMG lo mides en "
              "«Mide» con la señal demo (patrones «Isométrica», «Rápida» o «Fatiga»), igual en cualquier escenario.")
RESPONSE_PENDING = ("la regla músculo → frecuencia cardiaca espera su firma de experto (ficha en "
                    "docs/contenido/fichas_acoplamientos.md), y la «activación» de esta plataforma no es un porcentaje de "
                    "la contracción máxima: la plataforma no calcula esa respuesta")
MUSCLE_ROWS = (("activation", "Activación muscular", "%"), ("median_frequency", "Frecuencia mediana", "Hz"))


def station_patient() -> None:
    common.render_patient_station(UNIT_KEY, UNIT_TITLE, PREFIX, SCENARIOS, note=START_NOTE)


def station_concept_signal() -> None:
    from app.supermodules import learn_theory as LT

    common.render_theory(*LT.EMG_TOPICS[:5])


def station_concept_limits() -> None:
    from app.supermodules import learn_theory as LT

    common.render_theory(*LT.EMG_TOPICS[5:])


def station_measure() -> None:
    from app.instruments import emg as E
    from app.instruments.base import station_context

    ctx = station_context(f"{PREFIX}mide")
    sig = E.fuente(ctx)
    st.caption(MIDE_NOTE)
    analysis = E.trazo(ctx, sig)
    saved = E.guardar(ctx, sig, analysis)
    common.saved_now(saved.saved_snapshot_id)


def station_practice() -> None:
    from educational.quiz_bank import EMG_QUESTIONS

    st.markdown("#### Preguntas · EMG (E1–E10)")
    common.render_bank_practice(EMG_QUESTIONS, "emg", f"{PREFIX}emg_", UNIT_KEY)


def _render_muscle_now(patient_id: str) -> None:
    """Lo que el UPS tiene del músculo de tu paciente (paciente compuesto), con su procedencia."""
    from app.utils.design_system import render_no_data
    from app.utils.patient_banner import vital_provenance_text
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.state import get_composed_patient

    st.markdown("#### El músculo de tu paciente")
    with get_active_session_factory()() as session:
        composed = get_composed_patient(session, patient_id)
    state = composed.state if composed is not None else None
    for name, label, unit in MUSCLE_ROWS:
        d = None if state is None else state.muscular.get(name)
        if d is None:
            render_no_data(label, "todavía no guardaste el EMG de tu paciente (estación «Mide»)")
            continue
        origin = composed.origins.get(("muscular", name)) if composed is not None else None
        st.markdown(f"{label}: {d.value:.1f} {unit} · {vital_provenance_text(d, origin)}")
    st.caption("La «activación» es el cociente entre el promedio y el pico del EMG rectificado: describe la forma de la "
               "señal, no cuánto contrae el músculo (temas A1 y A9).")


def station_closing() -> None:
    from app.utils.design_system import render_no_data

    common.render_closing_summary(UNIT_KEY, UNIT_TITLE)
    _render_muscle_now(M.progress(UNIT_KEY)["patient_id"])
    st.markdown("#### La contracción y la frecuencia cardiaca")
    render_no_data("Respuesta de la FC a la contracción", RESPONSE_PENDING)


UNIT = M.Unit(UNIT_KEY, UNIT_TITLE, organ="musculo", stations=(
    M.Station("paciente", "paciente", "Tu paciente", station_patient, needs_patient=False),
    M.Station("concepto_senal", "concepto", "Qué registra el EMG de superficie", station_concept_signal,
              needs_patient=False),
    M.Station("concepto_limites", "concepto", "Normalización, fatiga y límites", station_concept_limits, needs_patient=False),
    M.Station("mide", "mide", "El EMG de tu paciente", station_measure),
    M.Station("practica", "practica", "Preguntas de EMG", station_practice, needs_patient=False),
    M.Station("cierre", "cierre", "Tu paciente al final", station_closing),
), pending=(
    ("La respuesta de la FC a la contracción", "la firma de la ficha músculo → autonómico y una calibración de la "
                                               "contracción máxima en el EMG"),
))
