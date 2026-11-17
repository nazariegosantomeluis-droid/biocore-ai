"""Inicio con la estructura de Duolingo y la limpieza de Apple (2026-11-17).

Arriba, la franja de monitoreo del paciente activo; debajo, el selector de órganos; al centro, el gemelo (lo que el UPS
tiene de ese órgano), la ruta del órgano y la sección «Información» con un registro real; a la derecha, tres tarjetas
que son las tres puertas de la decisión 2 (Aprender, Practicar y Clinical Hub).

Art. I: la franja muestra el ÚLTIMO estado guardado en el UPS, no una señal en vivo (el monitoreo en vivo está en el
laboratorio de ECG); cada valor lleva su procedencia y lo que falta se dice «sin dato». Ningún texto médico nuevo: los
conceptos, pistas y fichas salen de los temas firmados y de los bancos de preguntas.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.supermodules import ui_catalog as C

DESCRIPTOR_ES = {
    "heart_rate": "Frecuencia cardiaca", "respiratory_rate": "Frecuencia respiratoria", "spo2": "SpO₂",
    "news2_pulse_points": "Puntos NEWS2 del pulso", "news2_respiratory_rate_points": "Puntos NEWS2 de la FR",
    "news2_spo2_scale1_points": "Puntos NEWS2 de la SpO₂ (escala 1)", "hr_rr_ratio": "Razón FC:FR",
    "systolic_bp": "Presión sistólica", "diastolic_bp": "Presión diastólica", "mean_arterial_pressure": "PAM",
}


def descriptor_label(name: str) -> str:
    return DESCRIPTOR_ES.get(name, name.replace("_", " "))


def _active_state():
    """(patient_id, último estado del UPS) sin crear paciente; (None, None) si no hay."""
    from app.utils.patient_banner import peek_active_patient_id
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.state import get_latest_state

    pid = peek_active_patient_id()
    if pid is None:
        return None, None
    with get_active_session_factory()() as session:
        return pid, get_latest_state(session, pid)


def snapshot_count(patient_id: Optional[str]) -> Optional[int]:
    if patient_id is None:
        return None
    from app.utils.patient_session import get_active_session_factory
    from domain.physiology.state.models import SnapshotRecord

    with get_active_session_factory()() as session:
        return session.query(SnapshotRecord).filter(SnapshotRecord.patient_id == patient_id).count()


def _value_text(descriptor) -> str:
    from app.utils.patient_banner import UNIT_ES, provenance_label

    unit = UNIT_ES.get(descriptor.unit, descriptor.unit)
    return f"{descriptor.value:.0f} {unit} · {provenance_label(descriptor)}".strip()


# ───────────────────────────── secciones ─────────────────────────────

def _render_monitor_strip() -> None:
    from app.utils import navigation as nav
    from app.utils.patient_banner import NO_DATA_TEXT, VITALS, read_active_vitals

    vitals = read_active_vitals()
    with st.container(key="bc_monitor"):
        st.markdown("<span class='bc-eyebrow'>Monitoreo del paciente activo</span>", unsafe_allow_html=True)
        if vitals.patient_id is None:
            st.markdown("Sin paciente activo: abre el gemelo digital para crear el paciente que comparten las páginas.")
        else:
            cols = st.columns(len(VITALS))
            for col, (key, label, *_rest) in zip(cols, VITALS):
                d = vitals.values[key]
                col.markdown(f"<span class='bc-value'>{label} {'—' if d is None else f'{d.value:.0f}'}</span>",
                             unsafe_allow_html=True)
                col.caption(NO_DATA_TEXT if d is None else _value_text(d))
        st.caption("Último estado guardado en el UPS de esta sesión. El monitoreo en vivo está en el laboratorio de ECG.")
        nav.link("ecg", "Monitoreo en vivo: laboratorio de ECG", icon=":material/monitor_heart:")


def _render_twin_card(organ: C.Organ) -> None:
    from app.utils import navigation as nav

    pid, state = _active_state()
    with st.container(key="bc_card_twin"):
        st.markdown(f"<span class='bc-eyebrow'>Gemelo digital · simulación</span>", unsafe_allow_html=True)
        st.markdown(f"#### {organ.label}")
        if organ.domain is None:
            st.caption("El UPS no tiene un dominio para este sistema; se estudia con la variabilidad cardíaca.")
        elif state is None:
            st.caption("Sin dato: el paciente activo todavía no tiene un estado guardado en el UPS.")
        else:
            descriptors = state.all_domains()[organ.domain].descriptors
            if not descriptors:
                st.caption("Sin dato: el UPS del paciente activo no tiene valores de este sistema.")
            for name, d in descriptors.items():
                st.markdown(f"**{descriptor_label(name)}** · {_value_text(d)}")
        nav.link("gemelo", "Abrir el gemelo digital", icon=":material/body_system:")


def _go_to_topic(topic_key: str) -> None:
    from app.utils import navigation as nav

    st.session_state[C.SELECTED_TOPIC_KEY] = topic_key
    target = nav.page("temas")
    if target is not None:
        st.switch_page(target)


def _render_path(organ: C.Organ) -> None:
    from app.utils import navigation as nav

    st.markdown("#### Ruta")
    for i, (label, kind, target) in enumerate(C.PATHS[organ.key]):
        with st.container(key=f"bc_node_{'a' if i % 2 == 0 else 'b'}_{organ.key}_{i}"):
            if kind == "tema":
                st.button(label, key=f"bc_go_{organ.key}_{i}", icon=":material/menu_book:",
                          on_click=_go_to_topic, args=(target,))
            else:
                nav.link(target, label, icon=":material/arrow_forward:")


@st.cache_data(show_spinner=False)
def _recording(key: str):
    from src.signals import reference_recordings as R

    data = R.ptb_s0010() if key == "ptb_s0010" else R.cap_n16()
    return data, R.source_line(key)


def render_recording_info(organ: C.Organ, key_prefix: str = "bc_info") -> None:
    """«Información»: un trazo REAL del repositorio, con su procedencia; sin registro, lo dice."""
    st.markdown("#### Información")
    if organ.recording is None:
        st.caption("Sin registro real en el repositorio para este sistema.")
        return
    data, source = _recording(organ.recording)
    if organ.recording == "ptb_s0010":
        from app.utils import ecg_paper

        fig = ecg_paper.strip_figure(data["leads"]["ii"] if "ii" in data["leads"] else data["leads"]["II"],
                                     data["fs"], lead="II", duration_s=4.0, filter_label=ecg_paper.NO_FILTER_LABEL)
        ecg_paper.render(fig, key=f"{key_prefix}_ecg")
    else:
        import numpy as np
        import plotly.graph_objects as go

        from app.utils.design_system import PALETTE

        lead = "P4-O2" if "P4-O2" in data["leads"] else next(iter(data["leads"]))
        y = np.asarray(data["leads"][lead][: int(5 * data["fs"])], dtype=float)
        fig = go.Figure(go.Scatter(x=np.arange(y.size) / data["fs"], y=y, mode="lines",
                                   line=dict(color=PALETTE.TRAZO, width=1.4), name=lead))
        fig.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=30), paper_bgcolor=PALETTE.BACKGROUND,
                          plot_bgcolor=PALETTE.BACKGROUND, font=dict(color=PALETTE.TEXT),
                          xaxis=dict(title="tiempo (s)", gridcolor=PALETTE.GRID),
                          yaxis=dict(title=f"{lead} (µV)", gridcolor=PALETTE.GRID))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_eeg")
    st.caption(source)


def _render_learn_card(organ: C.Organ) -> None:
    from app.utils import navigation as nav

    topics = C.topics_for(organ.key)
    with st.container(key="bc_card_learn"):
        st.markdown("### Aprender")
        if not topics:
            st.caption("Este sistema todavía no tiene un tema firmado; está en sus laboratorios.")
        else:
            topic = topics[0]
            st.markdown(f"**Concepto · {topic.theory.title}**")
            st.markdown(topic.theory.idea or "Sin idea firmada para este tema.")
            questions = C.quiz_questions(topic, limit=1)
            if questions:
                q = questions[0]
                st.markdown("**Ficha de estudio**")
                st.markdown(q.prompt)
                if st.toggle("Pista", key=f"bc_hint_{organ.key}"):
                    st.caption(f"De la teoría firmada: {topic.theory.idea}")
                if st.toggle("Ver respuesta", key=f"bc_answer_{organ.key}"):
                    st.markdown(f"**{q.correct_choice}**")
                    if q.explanation:
                        st.caption(q.explanation)
                    if q.source:
                        st.caption(f"Fuente: {q.source}")
            st.button("Abrir el tema", key=f"bc_open_topic_{organ.key}", icon=":material/menu_book:",
                      on_click=_go_to_topic, args=(topic.key,))
        nav.link("teoria", "Ir a Teoría", icon=":material/school:")


def _render_practice_card() -> None:
    from app.supermodules.session_learning_view import summarize
    from app.utils import navigation as nav
    from app.utils.session_learning import get_session_log

    summary = summarize(get_session_log())
    with st.container(key="bc_card_practice"):
        st.markdown("### Practicar")
        st.markdown("**Avance de esta sesión**")
        if summary.total == 0:
            st.caption("Todavía no hay respuestas registradas en esta sesión.")
        else:
            correct = sum(row.correct for row in summary.concepts)
            st.markdown(f"<span class='bc-value'>{correct} de {summary.total}</span>", unsafe_allow_html=True)
            st.caption("respuestas correctas en esta sesión")
        nav.link("cuestionarios", "Ir a Practicar", icon=":material/quiz:")
        nav.link("mi-sesion", "Tu aprendizaje en esta sesión", icon=":material/insights:")


def _render_clinical_card() -> None:
    from app.utils import navigation as nav
    from app.utils.patient_banner import peek_active_patient_id

    pid = peek_active_patient_id()
    with st.container(key="bc_card_clinical"):
        st.markdown("### Clinical Hub")
        st.markdown("**Expediente**")
        if pid is None:
            st.caption("Sin paciente activo.")
        else:
            st.markdown(f"Paciente `{pid[:8]}` · {snapshot_count(pid)} estados guardados en el UPS")
        nav.link("gemelo", "Ir al gemelo digital", icon=":material/body_system:")
        nav.link("comparar", "Comparar pacientes", icon=":material/compare_arrows:")
        nav.link("pacientes", "Flujo de pacientes", icon=":material/folder_shared:")


def render_home_dashboard() -> None:
    from app.utils import navigation as nav

    st.markdown("<span class='bc-eyebrow'>BIOCORE AI</span><p class='bc-hero'>Equivócate aquí.</p>",
                unsafe_allow_html=True)
    st.caption("Plataforma educativa de fisiología. El gemelo digital es una simulación y se declara como tal.")
    _render_monitor_strip()

    choice = st.pills("Órganos", [o.key for o in C.ORGANS], default=C.ORGANS[0].key, key=C.SELECTED_ORGAN_KEY,
                      format_func=lambda k: f"{C.ORGAN_BY_KEY[k].icon} {C.ORGAN_BY_KEY[k].label}")
    organ = C.ORGAN_BY_KEY[choice or C.ORGANS[0].key]

    center, right = st.columns([2, 1], gap="large")
    with center:
        _render_twin_card(organ)
        _render_path(organ)
        render_recording_info(organ)
    with right:
        _render_learn_card(organ)
        _render_practice_card()
        _render_clinical_card()

    st.caption("La IA (narrador y explicaciones) es opcional: sin clave, todo lo demás funciona igual.")
    nav.link("ajustes", "Ajustes: clave de IA", icon=":material/settings:")
