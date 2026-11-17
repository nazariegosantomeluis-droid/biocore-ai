"""Comparar pacientes (Clinical Hub), con la estructura del comparador de Apple (2026-11-17).

Hasta tres columnas, cada una un estado guardado del UPS: pacientes distintos o el mismo paciente en distintos
momentos. Las filas van por sistema (los dominios del UPS) y cada celda trae el valor con su procedencia, o «Sin dato».
Solo lee la base (`SnapshotRecord` y `get_state_by_snapshot_id`); no escribe nada.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import streamlit as st

DOMAIN_ES = {"cardiovascular": "Cardiovascular", "respiratory": "Respiratorio", "neurological": "Neurológico",
             "muscular": "Muscular"}
NONE_OPTION = "ninguno"
NO_DATA = "Sin dato"
MAX_SNAPSHOTS = 40


def cell_text(descriptor) -> str:
    from app.utils.patient_banner import UNIT_ES, provenance_label

    if descriptor is None:
        return NO_DATA
    return f"{descriptor.value:.1f} {UNIT_ES.get(descriptor.unit, descriptor.unit)} · {provenance_label(descriptor)}"


def compare_rows(states: Sequence[Optional[object]]) -> List[Tuple[str, str, List[str]]]:
    """(sistema, variable, celdas) para cada variable que tenga al menos una columna; una columna vacía (None) da
    «Sin dato» en todas sus celdas."""
    from app.supermodules.ui_home import descriptor_label

    rows: List[Tuple[str, str, List[str]]] = []
    for domain, domain_label in DOMAIN_ES.items():
        per_state = [(s.all_domains()[domain].descriptors if s is not None else {}) for s in states]
        names = sorted({name for descriptors in per_state for name in descriptors})
        for name in names:
            rows.append((domain_label, descriptor_label(name), [cell_text(d.get(name)) for d in per_state]))
    return rows


def snapshot_options() -> List[Tuple[str, str, str]]:
    """(snapshot_id, patient_id, rótulo), del más reciente al más antiguo."""
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.state.models import SnapshotRecord

    with get_active_session_factory()() as session:
        rows = (session.query(SnapshotRecord).order_by(SnapshotRecord.timestamp.desc()).limit(MAX_SNAPSHOTS).all())
        return [(r.id, r.patient_id, f"Paciente {r.patient_id[:8]} · {r.timestamp:%d/%m %H:%M:%S}") for r in rows]


def _load(snapshot_id: Optional[str]):
    if snapshot_id in (None, NONE_OPTION):
        return None
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.state import get_state_by_snapshot_id

    with get_active_session_factory()() as session:
        return get_state_by_snapshot_id(session, snapshot_id)


def default_columns(options: Sequence[Tuple[str, str, str]], active_patient: Optional[str]) -> List[str]:
    """Columna 1: el estado más reciente del paciente activo; columna 2: el anterior del MISMO paciente (comparar en
    el tiempo); columna 3 vacía. Sin paciente activo, los dos estados más recientes."""
    mine = [sid for sid, pid, _ in options if pid == active_patient] or [sid for sid, _, _ in options]
    picks = (mine + [NONE_OPTION, NONE_OPTION])[:2]
    return [picks[0], picks[1], NONE_OPTION]


def render_compare_page() -> None:
    import pandas as pd

    from app.utils import navigation as nav
    from app.utils.design_system import render_empty_state
    from app.utils.patient_banner import peek_active_patient_id

    st.markdown("<span class='bc-eyebrow'>Clinical Hub</span><div class='bc-hero'>Comparar pacientes</div>",
                unsafe_allow_html=True)
    st.caption("Hasta tres estados guardados en el UPS: pacientes distintos o el mismo paciente en distintos momentos. "
               "Cada valor lleva su procedencia.")
    options = snapshot_options()
    if not options:
        render_empty_state("Todavía no hay estados guardados en el UPS",
                           action="abre el gemelo digital o guarda un estado desde un laboratorio")
        nav.link("gemelo", "Abrir el gemelo digital", icon=":material/body_system:")
        return

    labels = {sid: label for sid, _, label in options}
    labels[NONE_OPTION] = "Sin selección"
    ids = [NONE_OPTION] + [sid for sid, _, _ in options]
    defaults = default_columns(options, peek_active_patient_id())
    selected = []
    for i, col in enumerate(st.columns(3)):
        with col, st.container(key=f"bc_cmp_col_{i}"):
            key = f"bc_cmp_sel_{i}"
            if key in st.session_state:
                selected.append(st.selectbox(f"Columna {i + 1}", ids, key=key, format_func=labels.get))
            else:
                selected.append(st.selectbox(f"Columna {i + 1}", ids, index=ids.index(defaults[i]), key=key,
                                             format_func=labels.get))

    states = [_load(sid) for sid in selected]
    rows = compare_rows(states)
    if not rows:
        st.caption("Las columnas elegidas no tienen valores en el UPS.")
        return
    headers = [f"{i + 1} · {labels[sid]}" for i, sid in enumerate(selected)]   # numeradas: dos columnas pueden repetir
    for domain_label in DOMAIN_ES.values():
        domain_rows = [r for r in rows if r[0] == domain_label]
        if not domain_rows:
            continue
        st.markdown(f"#### {domain_label}")
        st.dataframe(pd.DataFrame([[name, *cells] for _, name, cells in domain_rows], columns=["Variable", *headers]),
                     hide_index=True, use_container_width=True)
