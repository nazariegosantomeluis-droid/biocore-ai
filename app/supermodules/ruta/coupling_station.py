"""La regla firmada de una unidad, evaluada en el flujo normal de la Ruta (T6 de la ruta integrada, 2026-11-18).

Diseño firmado, T6: «la estación de cierre de la Unidad Cerebro llama al compositor justo después de guardar el EEG, si
hay una FC del paciente dentro de la ventana. La regla dispara en el flujo normal y la estación lo declara: qué regla,
con qué cita, con qué confianza». Lo comparten Cerebro (`AROUSAL_TAQUICARDIA_BAR`) y Respiración
(`HIPOXIA_TAQUICARDIA`).

Sin botón «Componer»: cada guardado de la unidad que lleve una entrada de la regla (el EEG o la SpO₂ en «Mide», la FC
en el cierre) llama a `evaluate_after_save`, que evalúa SOLO la regla de la unidad con el escenario de la unidad (así
se aplican los bloqueos por regla) mediante `domain.physiology.coupling.evaluate_rule_for_patient`. El resultado se
guarda bajo el prefijo de la unidad («Empezar de nuevo» lo borra) y el cierre lo muestra.
"""

from __future__ import annotations

import re
from typing import Optional

import streamlit as st

from app.supermodules.ruta import common

FC_NOTE = ("La FC se mide con la serie RR simulada que empieza en la FC de tu paciente (instrumento de variabilidad "
           "cardiaca). Al guardar, pasa a tu paciente como simulación y la regla se evalúa sola.")
ALREADY_NOTE = ("Ya evaluaste la regla con estas dos mediciones; no se acopla dos veces lo mismo. Guarda una medición "
                "nueva para evaluarla otra vez.")
COUPLED_NOTE = ("La FC acoplada es un cálculo de la regla (derivado por acoplamiento), no una medición. Se guarda junto "
                "a las dos mediciones que la produjeron.")
DESCRIPTOR_ES = {"bar": "BAR", "spo2": "SpO₂", "heart_rate": "FC"}
UNIT_ES = {"bpm": "lpm", "%": "%", "": ""}
OPERATOR_ES = {"<": "<", "<=": "≤", ">": ">", ">=": "≥"}


def spanish(text: Optional[str]) -> Optional[str]:
    """Un motivo del compositor con los nombres internos de los descriptores en palabras («heart_rate» → «FC»)."""
    if text is None:
        return None
    return re.sub(r"\b(" + "|".join(DESCRIPTOR_ES) + r")\b", lambda m: DESCRIPTOR_ES[m.group(1)], text)


def result_key(prefix: str) -> str:
    return f"{prefix}coupling_result"


def blocked_reason(rule, scenario: Optional[str]) -> Optional[str]:
    """Por qué la regla no se evalúa en el escenario de la unidad, o `None`."""
    from domain.physiology.coupling import COUPLING_DISABLED_SCENARIOS

    if scenario is None:
        return None
    label = common.SCENARIO_LABELS.get(scenario, scenario)
    if scenario in COUPLING_DISABLED_SCENARIOS:
        return (f"no se evalúa en el escenario {label}: el simulador ya modela la descarga simpática y la regla la "
                "contaría dos veces (escenarios bloqueados del catálogo)")
    if scenario in rule.blocked_scenarios:
        return (f"no se evalúa en el escenario {label}: el simulador ya modela este efecto y la regla lo contaría dos "
                "veces (bloqueo firmado de la regla)")
    return None


def _value_text(value) -> str:
    """`MeasuredValue` → «BAR 3.10 · Simulación», con la procedencia en palabras."""
    from app.utils.patient_banner import vital_provenance_text

    d = value.descriptor
    unit = UNIT_ES.get(d.unit, d.unit)
    number = f"{d.value:.2f}" if d.name == "bar" else f"{d.value:.0f}"
    return f"{DESCRIPTOR_ES.get(d.name, d.name)} {number}{(' ' + unit) if unit else ''} · {vital_provenance_text(d)}"


def evaluate_after_save(prefix: str, rule, scenario: Optional[str], patient_id: Optional[str]) -> None:
    """Evalúa la regla de la unidad tras un guardado y deja el resultado para el cierre. No dibuja (la estación se
    vuelve a dibujar en seguida, `common.saved_now`). En un escenario bloqueado no evalúa nada."""
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.coupling import evaluate_rule_for_patient

    if patient_id is None or blocked_reason(rule, scenario) is not None:
        return
    with get_active_session_factory()() as session:
        r = evaluate_rule_for_patient(session, patient_id, rule, scenario=scenario)
    c = r.coupled
    st.session_state[result_key(prefix)] = {
        "rule_id": r.rule_id, "available": r.available, "reason": spanish(r.reason),
        "already": r.already_evaluated, "wrote": r.wrote_snapshot, "gap_s": r.gap_s,
        "condition": None if r.condition is None else _value_text(r.condition),
        "base": None if r.base is None else _value_text(r.base),
        "observed": None if r.condition is None else r.condition.descriptor.value,
        "coupled": None if c is None else {"base": c.base_value, "coupled": c.coupled_value,
                                           "confidence": c.confidence},
    }


def render_inputs(rule, patient_id: str, scenario: Optional[str]) -> None:
    """Las dos entradas de la regla tal como están ahora: la última medición de cada una (nunca la copia de una
    composición), con su procedencia, el tiempo entre ambas y la ventana firmada de la regla."""
    from app.utils.design_system import render_no_data
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.coupling import rule_input_check
    from domain.physiology.state import horizon_of

    with get_active_session_factory()() as session:
        cond, base, _reason = rule_input_check(session, patient_id, rule, scenario)
    for value, descriptor in ((cond, rule.condition.descriptor), (base, rule.effect.descriptor)):
        name = DESCRIPTOR_ES.get(descriptor, descriptor)
        if value is None:
            render_no_data(f"{name} de tu paciente", "todavía no hay una medición guardada")
        elif horizon_of(value.descriptor.source_detail) is not None:
            st.markdown(f"Último valor guardado: {_value_text(value)} (proyección del escenario, no cuenta como "
                        "medición)")
        else:
            st.markdown(f"Última medición: {_value_text(value)}")
    projected = any(v is not None and horizon_of(v.descriptor.source_detail) is not None for v in (cond, base))
    if cond is not None and base is not None and not projected:
        gap = abs((cond.timestamp - base.timestamp).total_seconds())
        st.caption(f"Tiempo entre las dos mediciones: {gap:.0f} s. Ventana firmada de la regla: {rule.window_s:.0f} s "
                   "(las dos deben venir de momentos así de cercanos).")


def render_result(prefix: str, rule, observed_note: Optional[str] = None) -> None:
    """Lo que pasó con la regla en el último guardado. `observed_note`: texto de la unidad que va con un acoplamiento
    aplicado (en Cerebro, el rango de la fuente con `{observed}`)."""
    from app.utils.design_system import render_no_data
    from domain.physiology.coupling import confidence_for_validation_status

    r = st.session_state.get(result_key(prefix))
    if r is None:
        st.caption("La regla se evalúa sola cada vez que guardas una de sus dos mediciones.")
        return
    if not r["available"]:
        render_no_data("Acoplamiento", f"la regla {r['rule_id']} no se evaluó: {r['reason']}")
        return
    if r["already"]:
        st.info(ALREADY_NOTE)
        return
    c = r["coupled"]
    if c is not None:
        st.success(f"La regla {r['rule_id']} se aplicó: {r['condition']}; FC {c['base']:.0f} lpm → FC acoplada "
                   f"{c['coupled']:.0f} lpm (derivado por acoplamiento, confianza {c['confidence']:.2f}).")
        st.caption(COUPLED_NOTE)
        if observed_note:
            st.caption(observed_note.format(observed=r["observed"]))
    else:
        confidence = confidence_for_validation_status(rule.validation_status)
        st.info(f"La regla {r['rule_id']} se evaluó y no se aplicó: {r['condition']} no cumple su condición "
                f"({DESCRIPTOR_ES.get(rule.condition.descriptor)} {OPERATOR_ES[rule.condition.operator.value]} "
                f"{rule.condition.threshold:g}). Confianza de la regla: {confidence:.2f}.")
    if r["wrote"]:
        st.caption(f"Las dos mediciones venían de guardados distintos ({r['gap_s']:.0f} s entre ambas): se guardaron "
                   "juntas en un momento nuevo, la más reciente tal cual y la más vieja como arrastre temporal con su "
                   "edad.")


def measure_hr(prefix: str, on_saved) -> None:
    """«Mide la FC de tu paciente ahora» con el instrumento de variabilidad cardiaca (claves `"<prefix>fc__…"`).
    `on_saved()` corre tras guardar y antes de volver a dibujar."""
    from app.instruments import hrv
    from app.instruments.base import station_context
    from app.utils.patient_banner import read_active_vitals

    st.markdown("#### Mide la FC de tu paciente ahora")
    ctx = station_context(f"{prefix}fc")
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
        on_saved()
    common.saved_now(saved.saved_snapshot_id)


def render_station(prefix: str, rule, patient_id: str, scenario: Optional[str],
                   observed_note: Optional[str] = None) -> None:
    """El bloque del cierre: escenario bloqueado (sin medir ni evaluar), o las entradas, la FC a medir y el resultado.
    La unidad dibuja antes el enunciado de su regla con su fuente y su confianza."""
    from app.utils.design_system import render_no_data

    blocked = blocked_reason(rule, scenario)
    if blocked is not None:
        render_no_data("Acoplamiento", blocked)
        return
    render_inputs(rule, patient_id, scenario)
    measure_hr(prefix, lambda: evaluate_after_save(prefix, rule, scenario, patient_id))
    render_result(prefix, rule, observed_note)
