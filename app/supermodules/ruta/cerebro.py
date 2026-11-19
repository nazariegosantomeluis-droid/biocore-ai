"""Unidad Cerebro (T4 de la ruta integrada, 2026-11-18).

Contenido firmado que ya existe: «Bandas del EEG» (glosario IFCN 2017, Kane 2017), el registro real CAP n16, el
instrumento de EEG (`app/instruments/eeg.py`: bandas y cocientes DAR/TBR/BAR con su cita) y el banco EEG.

Cierre (diseño, «Arousal → taquicardia»): el EEG medido de tu paciente y su FC pasan por el compositor de siempre
(`compose_neuro_cardiac_snapshot`), que evalúa la única regla firmada, `AROUSAL_TAQUICARDIA_BAR`. La estación dice qué
regla, con qué fuente y qué confianza; si no se puede componer, dice por qué. Bloqueada donde el escenario ya modela
la descarga simpática (`COUPLING_DISABLED_SCENARIOS`: estrés, ansiedad, convulsión), como en el catálogo.
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
COMPOSE_RESULT_KEY = f"{PREFIX}compose_result"

MIDE_NOTE = ("El EEG es una simulación (en la ruta no se ofrece un CSV: no se sabe de quién viene). Al guardar, las "
             "potencias de banda del primer canal y sus cocientes pasan a tu paciente como simulación.")
START_NOTE = ("El simulador no genera EEG: el escenario fija la FC, la FR y la SpO₂ de tu paciente, y su EEG lo mides en "
              "«Mide». En estrés y ansiedad la regla de arousal del cierre no se evalúa: esos escenarios ya modelan la "
              "descarga simpática.")
WINDOW_NOTE = ("El compositor solo une un BAR y una FC medidos con poca distancia: como mucho {window:.0f} s entre los "
               "dos guardados (ventana del compositor, Criterio BIOCORE). Lo que funciona: guarda el EEG en «Mide» y, "
               "en seguida, mide aquí la FC y compón.")
FC_NOTE = ("La FC se mide con la serie RR simulada que empieza en la FC de tu paciente (instrumento de variabilidad "
           "cardiaca). Al guardar, pasa a tu paciente como simulación.")
COMPOSED_NOTE = ("El compositor escribió un snapshot nuevo con el BAR (su procedencia de siempre) y la FC como arrastre "
                 "temporal, con su edad; la FC acoplada es un cálculo de la regla (DERIVADO_ACOPLAMIENTO), no una "
                 "medición. El banner y el gemelo siguen mostrando las potencias de banda del EEG; el BAR copiado en el "
                 "snapshot compuesto no viaja sin ellas (un derivado solo se muestra con sus entradas del mismo "
                 "guardado).")


# T4.1 (2026-11-18): con la señal sintética «Beta (activo)» el alfa casi desaparece y el BAR sale cerca de 100. La
# regla solo compara con el umbral y suma una cantidad fija; la estación lo dice con el rango que describe la fuente
# (`AROUSAL_TAQUICARDIA_BAR.source`: Schutter 2006, basal 0.8-1.2, arousal > 1.8).
SOURCE_RANGE_NOTE = ("Rango que describe la fuente (Schutter 2006): BAR basal 0.8–1.2 y de arousal > 1.8; el de tu "
                     "paciente es {bar:.2f}. La regla solo compara con el umbral y suma una cantidad fija: el aumento de "
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
        st.session_state.pop(COMPOSE_RESULT_KEY, None)        # un resultado viejo no queda bajo un EEG nuevo
    common.saved_now(saved.saved_snapshot_id)


def station_practice() -> None:
    from educational.quiz_bank import EEG_QUESTIONS

    st.markdown("#### Preguntas · EEG")
    st.caption("Estas preguntas cuentan en el cierre de la unidad; el EEG no es uno de los conceptos del panel «Tu "
               "aprendizaje en esta sesión».")
    common.render_bank_practice(EEG_QUESTIONS, "eeg", f"{PREFIX}eeg_", UNIT_KEY)


def _latest(session, patient_id, domain, name):
    """El último valor guardado de un descriptor, la hora de su snapshot y si ese snapshot es una composición anterior
    (su FC es un arrastre del compositor), o `(None, None, False)`."""
    from domain.physiology.state import get_latest_snapshot_id_with_descriptor, get_state_by_snapshot_id

    snap = get_latest_snapshot_id_with_descriptor(session, patient_id, domain, name)
    state = None if snap is None else get_state_by_snapshot_id(session, snap)
    if state is None:
        return None, None, False
    hr = state.cardiovascular.get("heart_rate")
    composed = hr is not None and hr.provenance.name == "ARRASTRE_TEMPORAL"
    return getattr(state, domain).get(name), state.timestamp, composed


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


def compose_blocker(patient_id: str) -> Optional[str]:
    """Por qué no se puede componer ahora (o `None` si se puede), y lo dibuja: el BAR y la FC de tu paciente con su
    procedencia y el tiempo entre ambos.

    Revisión final de la T4 (Art. I): el compositor de `domain/` toma el último BAR y la última FC tal como estén. Sin
    este filtro, componía la FC proyectada del escenario (horizonte 7 días) como si fuera de hace un segundo, y al
    componer otra vez tomaba sus propias copias: la FC arrastrada quedaba con «edad 0 s» y una FC vieja pasaba la
    ventana. Solo se compone un BAR y una FC medidos en la unidad, que no sean copias de una composición anterior."""
    from app.utils.design_system import render_no_data
    from app.utils.patient_banner import HORIZON_ES, vital_provenance_text
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.state import horizon_of
    from domain.physiology.state.composer import DEFAULT_MAX_HR_CARRY_AGE_S as WINDOW

    with get_active_session_factory()() as session:
        bar, bar_ts, bar_copy = _latest(session, patient_id, "neurological", "bar")
        hr, hr_ts, hr_copy = _latest(session, patient_id, "cardiovascular", "heart_rate")
    if bar is None:
        render_no_data("BAR de tu paciente", "todavía no guardaste su EEG (estación «Mide»)")
    else:
        st.markdown(f"BAR de tu paciente: {bar.value:.2f} · {vital_provenance_text(bar, None)}")
    if hr is None:
        render_no_data("FC de tu paciente", "el UPS no tiene una FC de tu paciente")
    else:
        st.markdown(f"FC de tu paciente: {hr.value:.0f} lpm · {vital_provenance_text(hr, None)}")
    st.caption(WINDOW_NOTE.format(window=WINDOW))
    if bar is None:
        return "falta el EEG de tu paciente"
    if hr is None:
        return "falta la FC de tu paciente: mídela aquí abajo"
    if bar_copy and hr_copy and bar_ts == hr_ts:
        return "ya compusiste este EEG con esta FC: guarda un EEG o una FC nuevos para volver a componer"
    if bar_copy:
        return ("el BAR más reciente es la copia de la composición anterior: guarda el EEG de nuevo en «Mide» (y "
                "después mide la FC aquí)")
    if hr_copy:
        return "la FC más reciente es la copia de la composición anterior: mide la FC de nuevo aquí abajo"
    horizon = horizon_of(hr.source_detail)
    if horizon is not None:
        return (f"la FC de tu paciente es la proyección del escenario (horizonte {HORIZON_ES.get(horizon, horizon)}), "
                "no una medición de este momento: mídela aquí abajo")
    gap = abs((bar_ts - hr_ts).total_seconds())
    st.markdown(f"Tiempo entre el EEG y la FC guardados: {gap:.0f} s.")
    if gap > WINDOW:
        older, newer = ("el EEG", "la FC") if bar_ts < hr_ts else ("la FC", "el EEG")
        return (f"{older} se guardó {gap:.0f} s antes que {newer} y la ventana es de {WINDOW:.0f} s: guarda de nuevo "
                f"{older} y compón en seguida")
    return None


def _measure_hr() -> None:
    from app.instruments import hrv
    from app.instruments.base import station_context
    from app.utils.patient_banner import read_active_vitals

    st.markdown("#### Mide la FC de tu paciente ahora")
    ctx = station_context(f"{PREFIX}fc")
    out_of_range = common.out_of_control_range(read_active_vitals(), (("hr", "FC", "lpm", hrv.HR_BASE_RANGE),
                                                                      ("rr", "FR", "rpm", hrv.RESP_RATE_RANGE)))
    series = hrv.rr_source(ctx)
    if series is None:
        return
    if series.source != hrv.MANUAL_SOURCE and out_of_range:
        common.render_out_of_range(out_of_range)
        return
    st.caption(FC_NOTE)
    temporal = hrv.tiempo(ctx, series).values
    saved = hrv.guardar(ctx, series, temporal["sdnn"], temporal["mean_nn"])
    if saved.saved_snapshot_id:
        st.session_state.pop(COMPOSE_RESULT_KEY, None)        # un resultado viejo no queda bajo una FC nueva
    common.saved_now(saved.saved_snapshot_id)


def _compose(patient_id: str) -> None:
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.state import compose_neuro_cardiac_snapshot

    with get_active_session_factory()() as session:
        result = compose_neuro_cardiac_snapshot(session, patient_id)
    coupled = [{"rule_id": c.rule_id, "base": c.base_value, "coupled": c.coupled_value, "confidence": c.confidence,
                "observed": c.observed_value} for c in result.coupled]
    st.session_state[COMPOSE_RESULT_KEY] = {"available": result.available, "reason": result.reason,
                                            "hr_age_s": result.hr_age_s, "coupled": coupled,
                                            "snapshot_id": result.snapshot_id}
    # Sin «Guardaste…» en la franja: componer copia el BAR y la FC que ya estaban; no mide nada nuevo.
    if result.available:
        st.rerun()


def _render_compose_result() -> None:
    from app.utils.design_system import render_no_data

    r = st.session_state.get(COMPOSE_RESULT_KEY)
    if r is None:
        return
    if not r["available"]:
        render_no_data("Acoplamiento", f"el compositor no unió el BAR y la FC: {r['reason']}")
        return
    if r["coupled"]:
        c = r["coupled"][0]
        st.success(f"La regla {c['rule_id']} se aplicó: BAR observado {c['observed']:.2f}; FC {c['base']:.0f} lpm → FC "
                   f"acoplada {c['coupled']:.0f} lpm (DERIVADO_ACOPLAMIENTO, confianza {c['confidence']:.2f}).")
    else:
        st.info("El BAR y la FC de tu paciente quedaron juntos en un snapshot, pero la regla no se aplicó: el BAR no "
                "supera su umbral.")
    st.caption(COMPOSED_NOTE + f" Edad de la FC arrastrada: {r['hr_age_s']:.0f} s.")
    if r["coupled"]:
        st.caption(SOURCE_RANGE_NOTE.format(bar=r["coupled"][0]["observed"]))


def station_closing() -> None:
    from app.utils.design_system import render_no_data
    from domain.physiology.coupling import COUPLING_DISABLED_SCENARIOS

    common.render_closing_summary(UNIT_KEY, UNIT_TITLE)
    p = M.progress(UNIT_KEY)
    st.markdown("#### Arousal y frecuencia cardiaca")
    _render_rule()
    if p["scenario"] in COUPLING_DISABLED_SCENARIOS:
        render_no_data("Acoplamiento", f"no se evalúa en el escenario {common.SCENARIO_LABELS[p['scenario']]}: el "
                                       "simulador ya modela la descarga simpática y la regla la contaría dos veces "
                                       "(escenarios bloqueados del catálogo)")
        return
    blocker = compose_blocker(p["patient_id"])
    _measure_hr()
    if blocker:
        render_no_data("Componer", blocker)
    if st.button("Componer el EEG y la FC y evaluar la regla", key=f"{PREFIX}compose", type="primary",
                 disabled=blocker is not None):
        _compose(p["patient_id"])
    _render_compose_result()


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
