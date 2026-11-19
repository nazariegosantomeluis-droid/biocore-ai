"""Página Ruta (T3 de la ruta integrada, 2026-11-18): la franja del paciente, el riel de la unidad, el hilo entre
estaciones y la estación actual, en una columna.

Diseño firmado, «Que no se sienta app genérica»: el paciente siempre presente (franja fija), una estación por pantalla
con «Siguiente», una línea que describe el estado del paciente que dejó la estación anterior y el zigzag de la ruta como
mapa de la unidad, con la estación actual marcada. Sin pestañas como estructura, sin emoji, sin «Lab».
"""

from __future__ import annotations

import streamlit as st

from app.supermodules.ruta import common, units
from app.supermodules.ruta import model as M

FRANJA_KEY = "ruta_franja"
UNIT_KEY = "ruta_unit"


def _vitals_line(vitals) -> str:
    from app.utils.patient_banner import UNIT_ES, VITALS, vital_provenance_text

    parts = []
    for key, label, *_rest in VITALS:
        d = vitals.values[key]
        parts.append(f"{label} sin dato" if d is None else
                     f"{label} {d.value:.0f} {UNIT_ES.get(d.unit, d.unit)} "
                     f"({vital_provenance_text(d, vitals.origins.get(key))})")
    return " · ".join(parts)


def _seal(descriptor, origin) -> str:
    """Sello compacto para la franja: la imagen del sello del kit ya lleva la palabra dibujada; el texto alternativo la
    dice para el lector de pantalla. Si el valor es de un guardado anterior o de una trayectoria, su edad u horizonte."""
    from app.supermodules.ui_home import NO_DATA_SEAL, PROVENANCE_SEAL, STATIC
    from app.utils.patient_banner import HORIZON_ES, origin_when_text
    from domain.physiology.state import horizon_of

    if descriptor is not None and origin is None and descriptor.provenance.name == "ARRASTRE_TEMPORAL":
        # T4: la FC que el compositor copia (Unidad Cerebro) es un arrastre dentro del último guardado; el sello del kit
        # para el arrastre sin origen dice «No disponible» dibujado, y aquí sí hay valor: se dice con palabras.
        return "<span class='bc-franja-when'>arrastre temporal del compositor</span>"
    if descriptor is None:
        kind, word, when = *NO_DATA_SEAL, None
    elif origin is not None:
        (kind, word), when = PROVENANCE_SEAL.get(origin.provenance.name, NO_DATA_SEAL), origin_when_text(origin)
    else:
        kind, word = PROVENANCE_SEAL.get(descriptor.provenance.name, NO_DATA_SEAL)
        horizon = horizon_of(descriptor.source_detail)
        when = None if horizon is None else f"horizonte {HORIZON_ES.get(horizon, horizon)}"
    img = f"<img class='bc-franja-seal' src='{STATIC}/sellos/biocore-sello-{kind}-monitor.svg' alt='{word}'>"
    return img + (f"<span class='bc-franja-when'>{when}</span>" if when else "")


def _render_franja(unit: M.Unit, p: dict) -> None:
    """La franja fija del paciente (CSS: fija abajo al centro). Se dibuja al FINAL de la pasada, así dice lo que una
    estación acaba de guardar."""
    from app.supermodules.ui_home import icon_html
    from app.supermodules import ui_catalog as C
    from app.utils.patient_banner import VITALS, read_active_vitals

    from app.utils.patient_banner import peek_active_patient_id

    vitals = read_active_vitals()
    parts = [icon_html(C.ORGAN_BY_KEY[unit.organ].icon_file, css="bc-franja-icon"),
             f"<span>Tu paciente · {unit.title}</span>"]
    # Revisión final de la T3 (Art. I): «Tu paciente» es el de la unidad. Si no hay, o si otra página cambió el
    # paciente activo, la franja lo dice y no pone los signos de otro paciente bajo ese nombre.
    if p["patient_id"] is None:
        parts.append("<span>sin paciente de la unidad: empieza en la estación 0</span>")
    elif peek_active_patient_id() != p["patient_id"]:
        parts.append("<span>el paciente activo no es el de esta unidad</span>")
    else:
        for key, label, *_rest in VITALS:
            d = vitals.values[key]
            parts.append(f"<span>{label} <b>{'—' if d is None else f'{d.value:.0f}'}</b></span>"
                         + _seal(d, vitals.origins.get(key)))
    saved = st.session_state.pop(common.SAVED_NOW_KEY, None)
    if saved:
        text = _saved_text(saved)
        if text:
            parts.append(f"<span class='bc-franja-saved'>{text}</span>")
    # Un solo bloque de HTML propio (clase `bc-franja`, fija por CSS): un contenedor de Streamlit con posición fija no
    # toma la altura de su contenido.
    with st.container(key=FRANJA_KEY):
        # El espacio de abajo evita que la franja tape el final de la página.
        st.markdown(f"<div class='bc-franja bc-mini'>{''.join(parts)}</div><div class='bc-franja-space'></div>",
                    unsafe_allow_html=True)


DOMAIN_ES = {"cardiovascular": "corazón", "respiratory": "respiración", "neurological": "cerebro",
             "muscular": "músculo"}


def _saved_text(snapshot_id: str) -> str:
    """Lo que se acaba de guardar, leído del snapshot (T4: antes decía siempre «Guardaste FC», también cuando una
    estación guardaba la respiración o el EEG). Las constantes vitales con su valor y su sello; lo demás, por sistema."""
    from app.utils.patient_banner import UNIT_ES, VITALS
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.state import get_state_by_snapshot_id

    with get_active_session_factory()() as session:
        state = get_state_by_snapshot_id(session, snapshot_id)
    if state is None:
        return ""
    vitals = []
    for _key, label, domain, name, _component in VITALS:
        d = getattr(state, domain).get(name)
        if d is not None:
            vitals.append(f"{label} {d.value:.0f} {UNIT_ES.get(d.unit, d.unit)} {_seal(d, None)}")
    if vitals:
        return "Guardaste " + " · ".join(vitals)
    domains = [DOMAIN_ES[dom] for dom in DOMAIN_ES if getattr(state, dom).descriptors]
    count = sum(len(getattr(state, dom).descriptors) for dom in DOMAIN_ES)
    return f"Guardaste {count} valores de {', '.join(domains)}" if domains else ""


def _render_rail(unit: M.Unit, p: dict) -> None:
    from app.utils.design_system import route_arrow_html

    st.markdown("#### Ruta de la unidad")
    for i, station in enumerate(unit.stations):
        side = "a" if i % 2 == 0 else "b"
        if i:
            st.markdown(route_arrow_html("derecha" if side == "b" else "izquierda"), unsafe_allow_html=True)
        current = i == p["station"]
        mark = " · aquí" if current else (" · visitada" if i in p["visited"] else "")
        with st.container(key=f"bc_node_{side}_ruta_{i}"):
            st.button(f"{i} · {M.KIND_LABELS[station.kind]}: {station.title}{mark}", key=f"ruta_node_{i}",
                      disabled=current, type="primary" if current else "secondary",
                      on_click=M.go_to, args=(unit.key, i))
    for title, missing in unit.pending:
        st.caption(f"Pendiente: {title} — falta {missing}.")


def _back_to_unit_patient(patient_id: str) -> None:
    from app.utils.patient_session import set_active_patient_id

    set_active_patient_id(patient_id)


def render_route_page() -> None:
    from app.utils.design_system import render_no_data
    from app.utils.patient_banner import peek_active_patient_id, read_active_vitals

    # T4: una unidad a la vez, cada una con su paciente y su avance (no se mezclan). Las que aún no se pueden recorrer
    # se listan como pendientes, con lo que les falta.
    unit_key = st.radio("Unidad", [u.key for u in units.UNITS], horizontal=True, key=UNIT_KEY,
                        format_func=lambda k: units.UNIT_BY_KEY[k].title)
    for title, missing in units.PENDING_UNITS:
        st.caption(f"{title} (pendiente): falta {missing}.")
    unit = units.UNIT_BY_KEY[unit_key]
    p = M.progress(unit.key)
    station = unit.stations[p["station"]]
    last = len(unit.stations) - 1

    st.markdown(f"<span class='bc-eyebrow'>Ruta · {unit.title}</span>"
                f"<div class='bc-hero'>{station.title}</div>", unsafe_allow_html=True)
    # La estación primero: en el celular las columnas se apilan y la ruta queda debajo, no antes de la estación.
    body, rail = st.columns([2, 1], gap="large")
    with rail:
        _render_rail(unit, p)
        st.caption(M.PROGRESS_NOTE)
    with body:
        st.markdown(f"**Estación {p['station']} de {last} · {M.KIND_LABELS[station.kind]}**")
        unit_pid, active = p["patient_id"], peek_active_patient_id()
        mismatch = unit_pid is not None and active != unit_pid
        if station.needs_patient and unit_pid is None:
            render_no_data("Paciente de la unidad", "empieza en la estación 0 «Tu paciente»")
            st.button("Ir a la estación 0", key="ruta_go_start", on_click=M.go_to, args=(unit.key, 0))
        else:
            if mismatch:
                st.warning("El paciente activo ya no es el de esta unidad (otra unidad o página cambió de paciente). Las "
                           "estaciones que leen al paciente esperan a que vuelvas al de la unidad, para no mezclar "
                           "sus datos.")
                st.button("Volver al paciente de la unidad", key="ruta_back_to_unit_patient",
                          on_click=_back_to_unit_patient, args=(unit_pid,))
            elif unit_pid is not None and p["station"] != 0:
                st.markdown(f"Tu paciente ahora: {_vitals_line(read_active_vitals())}")
            # Con otro paciente activo solo se dibujan las estaciones que no lo leen (teoría, registro real, preguntas)
            # y la estación 0, que puede empezar de nuevo.
            if not (mismatch and station.needs_patient):
                station.render()

        prev, nxt = st.columns(2)
        if p["station"] > 0:
            prev.button("Anterior", key="ruta_prev", on_click=M.go_to, args=(unit.key, p["station"] - 1))
        if p["station"] < last:
            following = unit.stations[p["station"] + 1]
            nxt.button(f"Siguiente: {following.title}", key="ruta_next", type="primary",
                       on_click=M.go_to, args=(unit.key, p["station"] + 1))
    _render_franja(unit, p)
