"""«¿Qué pasa si…?» (Ruta › Práctica libre → `what-if`, antes Practicar): predecir y comprobar contra el motor hemodinámico de lazo cerrado.

El alumno elige un caso de una lista CERRADA, predice para cada salida si sube, baja o no cambia, y declara su
confianza (0–100) sin ver ningún número del motor. Al enviar, el motor de lazo cerrado de BIOCORE
(`domain.physiology.hemodynamics.run_closed_loop`) se corre dos veces (basal e intervención) y la respuesta correcta
es el SIGNO del cambio que calculó el motor. Cada predicción calificada se registra en la sesión
(`app/utils/session_learning.py`, fuente "what_if", concepto "hemodinamica"), una sola vez por intento.

Qué intervenciones hay, y por qué solo esas (Art. I, sin tocar `domain/`):
- `run_closed_loop(scenario, heart_rate_bpm)` solo deja variar la frecuencia cardiaca (barrido validado 40–220 lpm)
  y el escenario. La resistencia, el volumen/P_sf, la capacitancia, la ganancia del reflejo y la contractilidad son
  constantes del módulo: cambiarlas exigiría parchear variables globales (afectaría a todas las sesiones) o
  reimplementar física fuera de `domain/`. No se ofrecen.
- Sepsis no se ofrece: depende de valores en revisión clínica (capacitancia venosa 2×, gasto cardiaco del choque, FC
  150 sin cita). Un caso marcado `in_review` se mostraría con su etiqueta y NO se califica ni registra.
- Las FC de partida son los puntos fijos del panel del barorreflejo (`baroreflex_panel._FIXED_POINT_HR_BPM`); las de
  llegada se comprobaron: el lazo converge sin saturar el reflejo ni el piso de EDV.

Esta página es CAPA DE LECTURA: no agrega física ni texto fisiológico; la cadena del modelo se cita tal cual del código.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional, Tuple

import streamlit as st

PROVENANCE = "calculado por el motor de lazo cerrado de BIOCORE"
GRADED_AGAINST = "Se califica contra lo que calcula el modelo de BIOCORE, no contra un paciente real."

# Tanda de heurísticas (2026-11-19): antes, un cambio menor que el 2 % del basal contaba como «sin cambio» (Criterio
# BIOCORE, sin cita). Ahora cuenta como «sin cambio» lo que no se ve con los decimales de la tabla: el alumno ve los dos
# números iguales. No es un umbral clínico; es la misma resolución con que se muestran.
NO_CHANGE_LABEL = ("Un cambio que no se ve con los decimales de la tabla (PAM y volumen sistólico con 1, gasto "
                   "cardiaco con 2) cuenta como «sin cambio».")

# La cadena tal como la escribe el código (docstring de `domain/physiology/hemodynamics/closed_loop.py`).
MODEL_CHAIN = ("retorno venoso -> EDV (con techo diastólico, Módulo 4B-i) -> SV (Frank-Starling, eslabón 1) -> "
               "flujo -> R-RCR -> presión -> barórreflejo (Módulo 2/3) -> resistencia -> (de vuelta al retorno)")

UP, DOWN, SAME = "sube", "baja", "sin cambio"
DIRECTIONS = (UP, DOWN, SAME)

# (clave, nombre visible, unidad, decimales)
OUTPUTS: Tuple[Tuple[str, str, str, int], ...] = (
    ("pam", "PAM", "mmHg", 1),
    ("gc", "Gasto cardiaco (VS × FC)", "L/min", 2),
    ("vs", "Volumen sistólico", "mL", 1),
)


@dataclass(frozen=True)
class WhatIfCase:
    key: str                         # estable: forma parte del item_id registrado
    scenario: str                    # escenario de `run_closed_loop`
    label: str
    hr_base: float
    hr_new: float
    in_review: Optional[str] = None  # si no es None: se muestra con esta etiqueta y no se califica ni registra


def _base_hr(scenario: str) -> float:
    from app.supermodules.twin_shell.baroreflex_panel import _FIXED_POINT_HR_BPM

    return _FIXED_POINT_HR_BPM[scenario]


def _case(key: str, scenario: str, name: str, hr_new: float) -> WhatIfCase:
    hr = _base_hr(scenario)
    verb = "baja" if hr_new < hr else "sube"
    return WhatIfCase(key, scenario, f"{name} (FC {hr:g} lpm): la FC {verb} a {hr_new:g} lpm", hr, hr_new)


CASES: Tuple[WhatIfCase, ...] = (
    _case("sano_fc_50", "healthy", "Sano", 50.0),
    _case("sano_fc_120", "healthy", "Sano", 120.0),
    _case("hta_fc_60", "hypertension", "Hipertensión", 60.0),
    _case("hta_fc_130", "hypertension", "Hipertensión", 130.0),
)

EXCLUDED_NOTE = (
    "**No se ofrecen:** la sepsis (depende de la capacitancia venosa 2× — Criterio BIOCORE, sin cita (en revisión "
    "clínica) — y su gasto cardiaco está «calculado por el motor — en revisión clínica») ni cambios de resistencia, "
    "volumen, capacitancia o contractilidad: el motor solo deja variar la FC sin modificar su física."
)


@lru_cache(maxsize=64)
def engine_outputs(scenario: str, heart_rate_bpm: float) -> Dict[str, float]:
    """Una corrida del motor de lazo cerrado (determinista: sin azar; caché por (escenario, FC))."""
    from domain.physiology.hemodynamics import run_closed_loop

    r = run_closed_loop(scenario, heart_rate_bpm)
    return {
        "pam": r.final_map,
        "gc": r.final_stroke_volume_ml * heart_rate_bpm / 1000.0,     # VS × FC, como el panel del barorreflejo
        "vs": r.final_stroke_volume_ml,
        "converged": bool(r.converged and not r.oscillated),
    }


def direction(base: float, new: float, decimals: int) -> str:
    """Signo del cambio a la resolución con que se muestra (`decimals`): iguales en la tabla = «sin cambio»."""
    base_shown, new_shown = round(base, decimals), round(new, decimals)
    if base_shown == new_shown:
        return SAME
    return UP if new_shown > base_shown else DOWN


def grade(case: WhatIfCase, predictions: Dict[str, str]) -> Dict[str, dict]:
    """Corre el motor (basal e intervención) y compara cada predicción con el signo que calculó."""
    base, new = engine_outputs(case.scenario, case.hr_base), engine_outputs(case.scenario, case.hr_new)
    out = {}
    for key, _name, _unit, decimals in OUTPUTS:
        actual = direction(base[key], new[key], decimals)
        out[key] = {"base": base[key], "new": new[key], "actual": actual, "predicted": predictions[key],
                    "correct": predictions[key] == actual}
    out["_converged"] = base["converged"] and new["converged"]
    return out


def gradable(case: WhatIfCase, result: Dict[str, dict]) -> bool:
    return case.in_review is None and bool(result["_converged"])


_STATE = "what_if_state"
# Registro una sola vez por intento (mismo criterio que `app/utils/confidence.py`): la marca es (intento, caso) y el
# intento solo cambia con «Otra predicción». Volver a enviar el mismo caso sin pedir otro no registra de nuevo.
_ATTEMPT = "what_if_attempt"
_RECORDED = "what_if_recorded"


def _log_once(case: WhatIfCase, result: Dict[str, dict], confidences: Dict[str, int], ctx=None) -> None:
    from app.instruments.base import PAGE
    from app.utils.session_learning import log_session_answer

    ctx = ctx or PAGE
    mark = (st.session_state.get(ctx.k(_ATTEMPT), 0), case.key)
    recorded = st.session_state.setdefault(ctx.k(_RECORDED), set())
    if mark in recorded:
        return
    for out_key, *_ in OUTPUTS:
        log_session_answer(f"what_if:{case.key}:{out_key}", "what_if", "hemodinamica",
                           result[out_key]["correct"], confidences[out_key])
    recorded.add(mark)


def render_what_if_page(ctx=None, cases: Optional[Tuple[WhatIfCase, ...]] = None) -> None:
    """La página «¿Qué pasa si…?» o, con `ctx` de estación (T3, 2026-11-18), el mismo instrumento dentro de una
    estación de la ruta: todas las claves (widgets y estado del intento) pasan por `ctx.k`, así que no comparte estado
    con la página. `cases`: un subconjunto de la lista cerrada (p. ej. solo el escenario del paciente); por defecto,
    todos."""
    from app.instruments.base import PAGE
    from app.utils.design_system import BADGES, render_no_data

    ctx = ctx or PAGE
    cases = CASES if cases is None else cases
    st.caption(EXCLUDED_NOTE)
    labels = {c.key: c.label for c in cases}
    key = st.selectbox("Caso", list(labels), format_func=labels.get, key=ctx.k("what_if_case"))
    case = next(c for c in cases if c.key == key)
    state = st.session_state.get(ctx.k(_STATE))
    if state is None or state.get("case") != key:
        state = {"case": key, "submitted": False}
        st.session_state[ctx.k(_STATE)] = state

    if case.in_review:
        st.warning(f"En revisión clínica: {case.in_review}. Puedes ver lo que calcula el motor, pero no se califica "
                   "ni se registra.")
    st.caption(NO_CHANGE_LABEL)

    if not state["submitted"]:
        st.markdown("Predice qué le pasa a cada salida **antes** de ver lo que calcula el motor.")
        predictions, confidences = {}, {}
        for out_key, name, unit, _ in OUTPUTS:
            cols = st.columns([3, 2])
            predictions[out_key] = cols[0].radio(f"{name} ({unit})", DIRECTIONS, index=None, horizontal=True,
                                                 key=ctx.k(f"what_if_pred_{key}_{out_key}"))
            confidences[out_key] = cols[1].slider("Tu confianza (0–100)", 0, 100, 50,
                                                  key=ctx.k(f"what_if_conf_{key}_{out_key}"))
        ready = all(predictions.values())
        if st.button("Enviar predicción", key=ctx.k(f"what_if_send_{key}"), disabled=not ready):
            result = grade(case, predictions)
            state.update(submitted=True, predictions=predictions, confidences=confidences, result=result,
                         logged=gradable(case, result))
            if state["logged"]:
                _log_once(case, result, confidences, ctx)
            st.rerun()
        return

    result, confidences = state["result"], state["confidences"]
    if not result["_converged"]:
        render_no_data("Comparación con el motor", "el lazo no convergió en alguna de las dos corridas; no se califica")
    rows = []
    for out_key, name, unit, dec in OUTPUTS:
        r = result[out_key]
        rows.append({
            "Salida": f"{name} ({unit})",
            f"Basal (FC {case.hr_base:g} lpm)": f"{r['base']:.{dec}f}",
            f"Con la intervención (FC {case.hr_new:g} lpm)": f"{r['new']:.{dec}f}",
            "Cambio según el motor": r["actual"],
            "Tu predicción": r["predicted"],
            "Tu confianza": confidences[out_key],
            "Resultado": ("✓ acierto" if r["correct"] else "✗ no") if state["logged"] else "no se califica",
        })
    import pandas as pd

    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(GRADED_AGAINST)
    st.caption(f"Procedencia de los valores: {PROVENANCE} · {BADGES.label(BADGES.SIMULATION)}.")
    if state["logged"]:
        hits = sum(result[k]["correct"] for k, *_ in OUTPUTS)
        st.markdown(f"**{hits} de {len(OUTPUTS)}** predicciones coinciden con el motor.")
    else:
        st.info("No se califica ni se registra: " + (case.in_review or "el lazo no convergió") + ".")

    with st.expander("Cómo lo calcula el modelo", expanded=False):
        from app.supermodules.twin_shell.baroreflex_panel import CARDIAC_ARM_NOTE

        st.markdown(f"`{MODEL_CHAIN}`")
        st.caption("Cadena tal como está escrita en `domain/physiology/hemodynamics/closed_loop.py`.")
        st.markdown(CARDIAC_ARM_NOTE)

    if st.button("Otra predicción", key=ctx.k("what_if_again")):
        for k in [k for k in st.session_state if str(k).startswith((ctx.k("what_if_pred_"), ctx.k("what_if_conf_")))]:
            del st.session_state[k]
        st.session_state.pop(ctx.k(_STATE), None)
        st.session_state[ctx.k(_ATTEMPT)] = st.session_state.get(ctx.k(_ATTEMPT), 0) + 1
        st.rerun()
