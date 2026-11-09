"""Vistas compartidas del Respiratory Lab (arco respiratorio, fase 3, 2026-11-07, Art. I).

Solo muestran lo que tiene golden test: FR (con su banda NEWS2), variabilidad y duración del ciclo, apneas
(conteo, tiempo total, tabla con tipo y bordes declarados), tasa equivalente por hora de REGISTRO y la SpO2 del
modelo BIOCORE. Siguen ocultos: hipopneas, I:E, patrón, notas clínicas, ODI, severidad (vive en Calculadoras
Clínicas), "Guardar al gemelo" y la insignia de validado.
"""

from typing import Optional

import streamlit as st

from app.utils.design_system import BADGES, render_metric_card
from clinical.calculators import NEWS2_CITATION, _news2_rr

SPO2_PROVENANCE = "Simulación — modelo BIOCORE: Tc valor BIOCORE; r y recuperación, Howarth 2026"
EVENT_TYPE_LABELS = {
    "central": "central",
    "obstructive": "obstructiva",
    "mixed": "mixta (PENDING_VALIDATION)",
    "unknown": "sin canal de esfuerzo",
}
CALCULATOR_PAGE = "🧮 Calculadoras Clínicas"


def fr_band_text(analysis) -> Optional[str]:
    """Banda NEWS2 de la FR redondeada (.5 hacia arriba, ya hecho por el analizador). No es un diagnóstico."""
    n = analysis.respiratory_rate_rounded
    if n is None:
        return None
    points = _news2_rr(n)
    if points == 0:
        return f"dentro de 12–20 (NEWS2); {n}/min redondeada"
    return f"fuera de 12–20 (NEWS2): {points} punto(s); {n}/min redondeada"


def render_rate_cards(analysis) -> None:
    """FR, duración del ciclo, variabilidad: con su motivo cuando no están disponibles (nunca 0)."""
    if analysis.respiratory_rate is None:
        reason = analysis.signal_status_detail or "no hay suficientes respiraciones"
        render_metric_card("Frecuencia Respiratoria", None, unavailable_reason=reason)
        return
    render_metric_card(
        "Frecuencia Respiratoria", f"{analysis.respiratory_rate:.1f} resp/min — {fr_band_text(analysis)}",
        provenance=BADGES.METHOD, citation=NEWS2_CITATION,
    )


def render_apnea_cards(analysis) -> None:
    """Conteo, tiempo total y tasa equivalente por hora de registro (extrapolada, sin valor diagnóstico)."""
    if analysis.apnea_count is None:
        render_metric_card("Apneas (≥ 10 s, caída ≥ 90 %)", None,
                           unavailable_reason="no evaluable: sin señal respiratoria en este registro")
        return
    truncated = sum(1 for e in analysis.apnea_events if e["truncated"])
    detail = f" ({truncated} recortada(s) por el final del registro)" if truncated else ""
    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric_card("Apneas (≥ 10 s, caída ≥ 90 %)", f"{analysis.apnea_count}{detail}", provenance=BADGES.METHOD)
    with c2:
        render_metric_card("Tiempo total de apnea", f"{analysis.apnea_total_time_s:.1f} s", provenance=BADGES.METHOD)
    with c3:
        render_metric_card(
            "Tasa equivalente por hora de registro (extrapolada, sin valor diagnóstico)",
            f"{analysis.equivalent_rate_per_hour:.0f} /h", provenance=BADGES.METHOD,
        )


def render_events_table(analysis) -> None:
    """Tabla de eventos con tipo y bordes declarados; los no evaluables se listan aparte y no cuentan."""
    if analysis.apnea_count is None:
        st.info("Sin señal respiratoria evaluable: no se evalúan apneas (no es lo mismo que «0 apneas»).")
        return
    if analysis.apnea_events:
        rows = []
        for e in analysis.apnea_events:
            b = e["baseline"]
            rows.append({
                "Inicio (s)": round(e["start_time"], 1),
                "Duración (s)": round(e["duration"], 1),
                "Tipo (Criterio BIOCORE)": EVENT_TYPE_LABELS.get(e["type"], e["type"]),
                "Borde": "recortado por el final del registro" if e["truncated"] else "completo",
                "Línea basal": f"{b['n_breaths']} respiraciones previas, {b['window_s']:.0f} s; {b['rule']}"
                               + (" — registro corto: basal disponible declarada" if b["declared_short"] else ""),
            })
        st.dataframe(rows, hide_index=True, width="stretch")
        if any(e["mixed_pending"] for e in analysis.apnea_events):
            st.caption("Mixta: PENDING_VALIDATION (la definición del manual AASM no está verificada); se calcula y se marca.")
        st.caption(
            "Apnea = caída ≥ 90 % de la excursión respecto a la línea basal previa durante ≥ 10 s (Berry 2012, AASM). "
            "Tipo: «esfuerzo ausente» = caída ≥ 90 % del esfuerzo respecto a su basal (Criterio BIOCORE)."
        )
    else:
        st.success("No se detectaron apneas de ≥ 10 s en este registro (no descarta apneas en otros registros).")
    for e in analysis.non_evaluable_events:
        st.warning(f"No evaluable (no cuenta): evento de ~{e['duration']:.0f} s desde {e['start_time']:.0f} s — {e['reason']}.")


def render_calculator_link(key: str) -> None:
    """Enlace a la calculadora de severidad (el lab no categoriza: su registro dura minutos)."""
    st.caption(
        "La severidad de la apnea del sueño se calcula con un índice **por hora de sueño**; este laboratorio no la "
        "muestra porque su registro dura minutos."
    )
    if st.button("Abrir la calculadora de severidad (Calculadoras Clínicas → Escalas)", key=key):
        st.session_state["selected_hub"] = "Clinical Hub"
        st.session_state["selected_page"] = CALCULATOR_PAGE
        st.rerun()


def render_spo2_cards(analysis, *, include_below_85: bool = True) -> None:
    """SpO2 del modelo de eventos (fase 2b): se muestra con su procedencia de simulación."""
    kw = dict(provenance=BADGES.METHOD, citation=SPO2_PROVENANCE)
    cols = st.columns(4 if include_below_85 else 3)
    with cols[0]:
        render_metric_card("SpO2 Basal", f"{analysis.baseline_spo2:.1f}%", **kw)
    with cols[1]:
        render_metric_card("SpO2 Mínimo", f"{analysis.minimum_spo2:.1f}%", **kw)
    with cols[2]:
        render_metric_card("Tiempo <90%", f"{analysis.time_below_90:.1f}s", **kw)
    if include_below_85:
        with cols[3]:
            render_metric_card("Tiempo <85%", f"{analysis.time_below_85:.1f}s", **kw)


def render_hidden_notice() -> None:
    st.info(
        "**Todavía no se muestra** (sin golden test o sin criterio firmado): hipopneas, relación I:E, clasificación del "
        "patrón respiratorio, notas clínicas automáticas, ODI, categoría de severidad y «Guardar al gemelo»."
    )
