"""Unidad Corazón (T3 de la ruta integrada, 2026-11-18).

Cada estación usa contenido que ya existe y está firmado (diseño, tabla «Unidad · Contenido firmado que ya existe»):
los temas 1–5 de `teoria_citada.md`, el registro real PTB s0010, el instrumento `ecg_trazo`, la calculadora de QTc
(`clinical/calculators.py`), el quiz del tema «Frecuencia cardiaca» y «¿Qué pasa si…?». Lo único que se escribe aquí
son rótulos de interfaz y frases que describen los datos del paciente; ningún texto médico nuevo.

El paciente de la unidad sale de un escenario del simulador (`run_rich_scenario`, procedencia simulación) en un
paciente NUEVO que pasa a ser el paciente activo de toda la app: es el que late en el ECG, el que carga la calculadora
y el que se cierra al final.
"""

from __future__ import annotations

import streamlit as st

from app.supermodules.ruta import model as M

UNIT_KEY = "corazon"
UNIT_TITLE = "Unidad Corazón"
PREFIX = "ruta_corazon_"

from app.supermodules.ruta import common
from app.supermodules.ruta.common import SAVED_NOW_KEY, SCENARIOS  # noqa: F401  (la página y las pruebas los leen aquí)

MIDE_NOTE = ("Con la fuente «Paciente activo» esta estación solo lee: el trazo se dibuja a la FC que el UPS ya tiene de "
             "tu paciente, y guardarlo no añadiría ningún dato. Para guardar una FC medida, elige un caso clínico, "
             "MIT-BIH o PTB-XL: si la compuerta la acepta, esa FC pasa a ser la de tu paciente en las estaciones "
             "siguientes.")
ALTERA_NOTE = ("Los casos parten de la FC de referencia del motor de lazo cerrado para el escenario de tu paciente (no "
               "de su FC actual): así se califica contra lo que calcula el modelo.")
CLOSING_CASE_NOTE = "El caso guiado usa un trazado simulado propio, no el de tu paciente."


# ───────────────────────────── 0 · Tu paciente ─────────────────────────────

def station_patient() -> None:
    common.render_patient_station(UNIT_KEY, UNIT_TITLE, PREFIX)


# ───────────────────────────── estaciones ─────────────────────────────

_theory = common.render_theory


def station_concept_basics() -> None:
    from app.supermodules import learn_theory as LT

    _theory(LT.SIGNED_ECG_PAPER, LT.SIGNED_HEART_RATE, LT.SIGNED_WAVES)


def station_observe() -> None:
    from app.supermodules import ui_catalog as C
    from app.supermodules.ui_home import render_recording_info

    render_recording_info(C.ORGAN_BY_KEY["corazon"], key_prefix=f"{PREFIX}obs")
    st.caption("Un trazo real, con su procedencia. En la estación «Mide» verás el de tu paciente sobre el mismo papel.")


def station_measure() -> None:
    from app.instruments import ecg_trazo
    from app.instruments.base import station_context
    from app.utils.design_system import BADGES, render_metric_card, render_no_data
    from app.utils.patient_banner import read_active_vitals, vital_provenance_text
    from clinical import calculators as calc

    trace = ecg_trazo.render(station_context(f"{PREFIX}mide"))
    # La franja lo dice en la pasada siguiente; se vuelve a dibujar para que el hilo y el QTc ya usen la FC nueva.
    common.saved_now(None if trace is None else trace.saved_snapshot_id)
    st.caption(MIDE_NOTE)

    st.markdown("#### QTc con la FC de tu paciente")
    vitals = read_active_vitals()
    hr = vitals.values["hr"]
    if hr is None:
        render_no_data("FC del paciente", "el UPS no tiene una FC de este paciente")
        return
    st.markdown(f"FC del paciente: {hr.value:.0f} lpm · {vital_provenance_text(hr, vitals.origins.get('hr'))}")
    qt = st.number_input("QT (ms)", min_value=200.0, max_value=700.0, value=None, key=f"{PREFIX}qt",
                         help="Mídelo en el trazo de arriba o en cualquier ECG; la FC es la de tu paciente.")
    if qt is None:
        st.caption("Escribe el QT para calcular el QTc.")
        return
    citations = {"Bazett": calc.BAZETT_CITATION, "Fridericia": calc.FRIDERICIA_CITATION,
                 "Framingham": calc.FRAMINGHAM_QTC_CITATION, "Hodges": calc.HODGES_CITATION}   # las de Calculadoras
    for name, value in calc.qtc_all(qt, hr.value).items():
        render_metric_card(f"QTc {name}", f"{value:.0f} ms", provenance=BADGES.CLINICAL, citation=citations[name])


def station_practice() -> None:
    from app.supermodules import ui_catalog as C

    # Revisión final de la T4: las mismas preguntas del tema, con claves de la unidad (ya no comparten estado con Temas)
    # y cada una con su concepto (`CONCEPT_BY_PROMPT`).
    topic = C.TOPIC_BY_KEY["fc"]
    st.markdown(f"#### Preguntas · {topic.theory.title}")
    common.render_bank_practice(C.quiz_questions(topic), topic.quiz_bank, f"{PREFIX}fc_", UNIT_KEY)


def station_alter() -> None:
    from app.instruments.base import station_context
    from app.supermodules import what_if as W

    scenario = M.progress(UNIT_KEY)["scenario"]
    cases = tuple(c for c in W.CASES if c.scenario == scenario)
    if not cases:
        st.info(f"El escenario de tu paciente ({SCENARIOS.get(scenario, scenario)}) no está en la lista cerrada de "
                "«¿Qué pasa si…?».")
        st.caption(W.EXCLUDED_NOTE)
        return
    st.caption(ALTERA_NOTE)
    with M.track_answers(UNIT_KEY):
        W.render_what_if_page(station_context(f"{PREFIX}altera"), cases=cases)


def station_concept_twelve() -> None:
    from app.supermodules import learn_theory as LT

    _theory(LT.SIGNED_TWELVE_LEADS, LT.SIGNED_ISCHEMIA)


def station_closing() -> None:
    from app.utils import navigation as nav

    common.render_closing_summary(UNIT_KEY, UNIT_TITLE)
    st.markdown("#### Caso de cierre")
    st.caption(CLOSING_CASE_NOTE)
    nav.link("caso-guiado", "Caso guiado de ECG: elevación del ST (firmado)")
    nav.link("desafio-ecg", "Desafío ECG de 12 derivaciones")


UNIT = M.Unit(UNIT_KEY, UNIT_TITLE, organ="corazon", stations=(
    M.Station("paciente", "paciente", "Tu paciente", station_patient, needs_patient=False),
    M.Station("concepto", "concepto", "El ECG en papel, la frecuencia y las ondas", station_concept_basics,
              needs_patient=False),
    M.Station("observa", "observa", "Un ECG real", station_observe, needs_patient=False),
    M.Station("mide", "mide", "El ECG de tu paciente", station_measure),
    M.Station("practica", "practica", "Preguntas de frecuencia cardiaca", station_practice, needs_patient=False),
    M.Station("altera", "altera", "¿Qué pasa si cambia la FC?", station_alter),
    M.Station("concepto_12", "concepto", "Las 12 derivaciones y la isquemia", station_concept_twelve,
              needs_patient=False),
    M.Station("cierre", "cierre", "Tu paciente al final", station_closing),
))
