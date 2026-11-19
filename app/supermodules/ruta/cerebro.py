"""Unidad Cerebro (T4 de la ruta integrada, 2026-11-18).

Contenido firmado que ya existe: «Bandas del EEG» (glosario IFCN 2017, Kane 2017), el registro real CAP n16, el
instrumento de EEG (`app/instruments/eeg.py`: bandas y cocientes DAR/TBR/BAR con su cita) y el banco EEG.

Cierre (diseño, «Arousal → taquicardia»; T6, 2026-11-18): la regla firmada `AROUSAL_TAQUICARDIA_BAR` se evalúa sola
justo después de guardar el EEG (en «Mide») o la FC (en el cierre), con el compositor por regla
(`coupling_station`, `evaluate_rule_for_patient`): sin botón. La estación dice qué regla, con qué fuente y qué
confianza, y si no se evaluó, por qué. Bloqueada donde el escenario ya modela la descarga simpática
(`COUPLING_DISABLED_SCENARIOS`: estrés, ansiedad, convulsión), como en el catálogo.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.supermodules.ruta import common
from app.supermodules.ruta import model as M

UNIT_KEY = "cerebro"
UNIT_TITLE = "Unidad Cerebro"
PREFIX = "ruta_cerebro_"
SCENARIOS = ("healthy", "stress", "anxiety")

MIDE_NOTE = ("El EEG es una simulación (en la ruta no se ofrece un CSV: no se sabe de quién viene). Al guardar, las "
             "potencias de banda del primer canal y sus cocientes pasan a tu paciente como simulación.")
START_NOTE = ("El simulador no genera EEG: el escenario fija la FC, la FR y la SpO₂ de tu paciente, y su EEG lo mides en "
              "«Mide». En estrés y ansiedad la regla de arousal del cierre no se evalúa: esos escenarios ya modelan la "
              "descarga simpática.")
FLOW_NOTE = ("T6: la regla se evalúa sola cada vez que guardas el EEG de tu paciente (en «Mide») o su FC (aquí). "
             "Solo junta un BAR y una FC medidos, nunca la FC proyectada del escenario ni la copia de una evaluación "
             "anterior, y solo si los separa como mucho la ventana firmada de la regla.")

# T4.1 (2026-11-18): con la señal sintética «Beta (activo)» el alfa casi desaparece y el BAR sale cerca de 100. La
# regla solo compara con el umbral y suma una cantidad fija; la estación lo dice con el rango que describe la fuente
# (`AROUSAL_TAQUICARDIA_BAR.source`: Schutter 2006, basal 0.8-1.2, arousal > 1.8).
SOURCE_RANGE_NOTE = ("Rango que describe la fuente (Schutter 2006): BAR basal 0.8–1.2 y de arousal > 1.8; el de tu "
                     "paciente es {observed:.2f}. La regla solo compara con el umbral y suma una cantidad fija: el aumento de "
                     "la FC no crece con el BAR. Un BAR muy por encima de esos valores sale de una señal sintética con "
                     "casi nada de alfa (patrón «Beta (activo)»), no de una persona.")


def station_patient() -> None:
    common.render_patient_station(UNIT_KEY, UNIT_TITLE, PREFIX, SCENARIOS, note=START_NOTE)


def station_concept() -> None:
    from app.supermodules import learn_theory as LT

    common.render_theory(LT.EEG_BANDS)


def station_observe() -> None:
    from app.supermodules import ui_catalog as C
    from app.supermodules.ui_home import render_recording_info

    render_recording_info(C.ORGAN_BY_KEY["cerebro"], key_prefix=f"{PREFIX}obs")
    st.caption("Un registro real, con su procedencia. En la estación «Mide» analizarás el EEG de tu paciente.")


def station_measure() -> None:
    from app.instruments import eeg as E
    from app.instruments.base import station_context

    ctx = station_context(f"{PREFIX}mide")
    series = E.fuente(ctx)
    if series is None:
        return
    st.caption(MIDE_NOTE)
    E.senales(ctx, series)
    overall = E.metricas(ctx, series)
    saved = E.guardar(ctx, series, overall)
    if saved.saved_snapshot_id:
        _evaluate(M.progress(UNIT_KEY)["patient_id"])
    common.saved_now(saved.saved_snapshot_id)


def station_practice() -> None:
    from educational.quiz_bank import EEG_QUESTIONS

    st.markdown("#### Preguntas · EEG")
    st.caption("Estas preguntas cuentan en el cierre de la unidad; el EEG no es uno de los conceptos del panel «Tu "
               "aprendizaje en esta sesión».")
    common.render_bank_practice(EEG_QUESTIONS, "eeg", f"{PREFIX}eeg_", UNIT_KEY)


def _render_rule() -> None:
    from domain.physiology.coupling import AROUSAL_TAQUICARDIA_BAR as RULE
    from domain.physiology.coupling import confidence_for_validation_status

    c, e = RULE.condition, RULE.effect
    st.markdown(f"**Regla firmada `{RULE.rule_id}`:** si el BAR de tu paciente es mayor que {c.threshold:g}, su FC "
                f"aumenta {e.magnitude_delta:+.0f} lpm (rango de la fuente: {e.magnitude_hint.replace('bpm', 'lpm')}).")
    confidence = confidence_for_validation_status(RULE.validation_status)
    status = "validada por su fuente" if RULE.validation_status.name == "VALIDADO_POR_FUENTE" else "transcrita sin validar"
    st.caption(f"Fuente: {RULE.source}. Regla {status}; la FC acoplada se guarda como cálculo de la regla "
               f"(DERIVADO_ACOPLAMIENTO) con confianza {confidence:.2f}: sigue siendo un cálculo, no una medición.")


def _evaluate(patient_id: Optional[str]) -> None:
    """T6: tras guardar el EEG (en «Mide») o la FC (en el cierre), la regla se evalúa con el escenario de la unidad."""
    from app.supermodules.ruta import coupling_station as CS
    from domain.physiology.coupling import AROUSAL_TAQUICARDIA_BAR as RULE

    CS.evaluate_after_save(PREFIX, RULE, M.progress(UNIT_KEY)["scenario"], patient_id)


def station_closing() -> None:
    from app.supermodules.ruta import coupling_station as CS
    from domain.physiology.coupling import AROUSAL_TAQUICARDIA_BAR as RULE

    common.render_closing_summary(UNIT_KEY, UNIT_TITLE)
    p = M.progress(UNIT_KEY)
    st.markdown("#### Arousal y frecuencia cardiaca")
    _render_rule()
    st.caption(FLOW_NOTE)
    CS.render_station(PREFIX, RULE, p["patient_id"], p["scenario"], observed_note=SOURCE_RANGE_NOTE)


UNIT = M.Unit(UNIT_KEY, UNIT_TITLE, organ="cerebro", stations=(
    M.Station("paciente", "paciente", "Tu paciente", station_patient, needs_patient=False),
    M.Station("concepto", "concepto", "Las bandas del EEG", station_concept, needs_patient=False),
    M.Station("observa", "observa", "Un EEG real", station_observe, needs_patient=False),
    M.Station("mide", "mide", "El EEG de tu paciente", station_measure),
    M.Station("practica", "practica", "Preguntas de EEG", station_practice, needs_patient=False),
    M.Station("cierre", "cierre", "Arousal y frecuencia cardiaca", station_closing),
), pending=(
    ("Más conceptos de EEG", "más teoría firmada de EEG (hoy hay un solo tema: las bandas)"),
))
