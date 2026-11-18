"""Inicio con la estructura de Duolingo, la limpieza de Apple y el kit de marca v1.1 (2026-11-17).

Arriba, el logo, el lema y la franja de monitoreo del paciente activo con una vista previa de la tira; al bajar, el
logo y el monitoreo suben y se quedan arriba en pequeño (CSS de `inject_global_theme`). Debajo, el selector de órganos;
al centro, el gemelo (lo que el UPS tiene de ese órgano, con su sello) y la ruta del órgano; a la derecha, las tres
puertas de la decisión 2 como tarjetas (Aprender, Practicar y Explorar).

Art. I: la franja muestra el ÚLTIMO estado guardado en el UPS, no una señal en vivo; la vista previa es la tira del kit
(registro real MIT-BIH 100) con su rótulo de procedencia, no la señal del paciente. Cada valor lleva su sello (manual
de marca, p. 20: «Todo valor y toda figura llevan un sello»). Ningún texto médico nuevo.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.supermodules import ui_catalog as C

STATIC = "app/static/marca"          # ruta servida por Streamlit (server.enableStaticServing)
LEMA = "Equivócate aquí."            # manual de marca v1.1, p. 4
DESCRIPTOR = "Laboratorio digital de fisiología."
TIRA_LABEL = "Registro real: MIT-BIH 100, MLII · PhysioNet, ODC-By 1.0"   # 04-Elementos-graficos/FUENTES.txt

DESCRIPTOR_ES = {
    "heart_rate": "Frecuencia cardiaca", "respiratory_rate": "Frecuencia respiratoria", "spo2": "SpO₂",
    "news2_pulse_points": "Puntos NEWS2 del pulso", "news2_respiratory_rate_points": "Puntos NEWS2 de la FR",
    "news2_spo2_scale1_points": "Puntos NEWS2 de la SpO₂ (escala 1)", "hr_rr_ratio": "Razón FC:FR",
    "hrv": "HRV", "systolic_bp": "Presión sistólica", "diastolic_bp": "Presión diastólica", "mean_arterial_pressure": "PAM",
}

# Procedencia del UPS -> sello del kit (archivo, palabra). El color no distingue nada: la forma y la palabra sí.
PROVENANCE_SEAL = {
    "SENSOR_REAL": ("medido", "Medido"),
    "SIMULACION": ("simulado", "Simulado"),
    "DERIVADO": ("calculado-por-modelo", "Calculado por modelo"),
    "MODELO_HEMODINAMICO": ("calculado-por-modelo", "Calculado por modelo"),
    "DERIVADO_ACOPLAMIENTO": ("calculado-por-modelo", "Calculado por modelo"),
    "REFERENCIA_CLINICA": ("referencia-citada", "Referencia citada"),
    "ARRASTRE_TEMPORAL": ("medido", "Medido · arrastre temporal"),
}
NO_DATA_SEAL = ("no-disponible", "No disponible")


def descriptor_label(name: str) -> str:
    return DESCRIPTOR_ES.get(name, name.replace("_", " "))


def seal_html(kind: str, word: str) -> str:
    return (f"<span class='bc-seal'><img src='{STATIC}/sellos/biocore-sello-{kind}-monitor.svg' alt=''>"
            f"{word}</span>")


def seal_for(descriptor) -> str:
    if descriptor is None:
        return seal_html(*NO_DATA_SEAL)
    return seal_html(*PROVENANCE_SEAL.get(descriptor.provenance.name, NO_DATA_SEAL))


def icon_html(name: str, css: str = "bc-illus") -> str:
    """Ícono dibujado del kit (decorativo: `alt` vacío)."""
    return f"<img class='{css}' src='{STATIC}/iconos/biocore-icono-{name}-monitor.svg' alt=''>"


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


def _value_with_unit(descriptor) -> str:
    from app.utils.patient_banner import UNIT_ES

    return f"{descriptor.value:.0f} {UNIT_ES.get(descriptor.unit, descriptor.unit)}".strip()


# ───────────────────────────── secciones ─────────────────────────────

def _render_hero() -> None:
    st.markdown(f"<div class='bc-logo'><img src='{STATIC}/logos/biocore-logotipo-color-monitor.svg' alt='Biocore'></div>"
                f"<div class='bc-lema'>{LEMA}</div>", unsafe_allow_html=True)
    st.caption(f"{DESCRIPTOR} El gemelo digital es una simulación y se declara como tal.")


def _render_sticky(vitals) -> None:
    """Barra compacta: aparece arriba al bajar (animación ligada al scroll; sin ella, se queda visible)."""
    from app.utils.patient_banner import VITALS

    parts = [f"<img src='{STATIC}/logos/biocore-isotipo-color-monitor.svg' alt='Biocore'>"]
    if vitals.patient_id is None:
        parts.append("<span>Sin paciente activo</span>")
    else:
        for key, label, *_rest in VITALS:
            d = vitals.values[key]
            parts.append(f"<span>{label} <b>{'—' if d is None else f'{d.value:.0f}'}</b></span>")
        any_d = next((d for d in vitals.values.values() if d is not None), None)
        parts.append(seal_for(any_d))
    with st.container(key="bc_sticky"):
        st.markdown(f"<div class='bc-mini'>{''.join(parts)}</div>", unsafe_allow_html=True)


def _render_monitor(vitals) -> None:
    from app.utils import navigation as nav
    from app.utils.patient_banner import VITALS

    with st.container(key="bc_monitor"):
        st.markdown("<span class='bc-eyebrow'>Monitoreo del paciente activo</span>", unsafe_allow_html=True)
        values, preview = st.columns([3, 2], gap="large")
        with values:
            if vitals.patient_id is None:
                st.markdown("Sin paciente activo: abre el gemelo digital para crear el paciente que comparten las páginas.")
            else:
                for col, (key, label, *_rest) in zip(st.columns(len(VITALS)), VITALS):
                    d = vitals.values[key]
                    col.markdown(f"<span class='bc-value'>{label} {'—' if d is None else f'{d.value:.0f}'}</span>",
                                 unsafe_allow_html=True)
                    col.markdown(("" if d is None else f"{_value_with_unit(d)}<br>") + seal_for(d),
                                 unsafe_allow_html=True)
            st.caption("Último estado guardado en el UPS de esta sesión; no es una señal en vivo.")
        with preview:
            st.markdown(f"<div class='bc-preview'><img src='{STATIC}/tira/biocore-tira-ecg-monitor.svg' "
                        f"alt='Tira de ECG: registro real MIT-BIH 100'></div>", unsafe_allow_html=True)
            st.markdown(seal_html("registro-real", TIRA_LABEL), unsafe_allow_html=True)
            nav.link("ecg", "Monitoreo en vivo: laboratorio de ECG completo")


def _render_twin_card(organ: C.Organ) -> None:
    from app.utils import navigation as nav

    pid, state = _active_state()
    with st.container(key="bc_card_twin"):
        st.markdown(f"{icon_html(organ.icon_file)}<span class='bc-eyebrow'>Gemelo digital · simulación</span>",
                    unsafe_allow_html=True)
        st.markdown(f"#### {organ.label}")
        if organ.domain is None:
            st.caption("El UPS no tiene un dominio para este sistema; se estudia con la variabilidad cardiaca.")
        elif state is None:
            st.markdown(seal_html(*NO_DATA_SEAL) + " El paciente activo todavía no tiene un estado guardado en el UPS.",
                        unsafe_allow_html=True)
        else:
            descriptors = state.all_domains()[organ.domain].descriptors
            if not descriptors:
                st.markdown(seal_html(*NO_DATA_SEAL) + " El UPS del paciente activo no tiene valores de este sistema.",
                            unsafe_allow_html=True)
            for name, d in descriptors.items():
                st.markdown(f"**{descriptor_label(name)}** · {_value_with_unit(d)} &nbsp; {seal_for(d)}",
                            unsafe_allow_html=True)
        nav.link("gemelo", "Abrir el gemelo digital")


def _go_to_topic(topic_key: str) -> None:
    from app.utils import navigation as nav

    st.session_state[C.SELECTED_TOPIC_KEY] = topic_key
    target = nav.page("temas")
    if target is not None:
        st.switch_page(target)


def _render_path(organ: C.Organ) -> None:
    from app.utils import navigation as nav
    from app.utils.design_system import route_arrow_html

    st.markdown("#### Ruta")
    for i, (label, kind, target) in enumerate(C.PATHS[organ.key]):
        side = "a" if i % 2 == 0 else "b"
        if i:   # flecha desde el nodo anterior: a la derecha si este nodo va a la derecha (zigzag)
            st.markdown(route_arrow_html("derecha" if side == "b" else "izquierda"), unsafe_allow_html=True)
        with st.container(key=f"bc_node_{side}_{organ.key}_{i}"):
            if kind == "tema":
                st.button(label, key=f"bc_go_{organ.key}_{i}", on_click=_go_to_topic, args=(target,))
            else:
                nav.link(target, label)


@st.cache_data(show_spinner=False)
def _recording(key: str):
    from src.signals import reference_recordings as R

    data = R.ptb_s0010() if key == "ptb_s0010" else R.cap_n16()
    return data, R.source_line(key)


def render_recording_info(organ: C.Organ, key_prefix: str = "bc_info") -> None:
    """Un trazo REAL del repositorio para el órgano, con su procedencia; sin registro, lo dice (lo usa «Hallazgos»)."""
    st.markdown("#### Registro real")
    if organ.recording is None:
        st.markdown(seal_html(*NO_DATA_SEAL) + " Sin registro real en el repositorio para este sistema.",
                    unsafe_allow_html=True)
        return
    data, source = _recording(organ.recording)
    if organ.recording == "ptb_s0010":
        from app.utils import ecg_paper

        fig = ecg_paper.strip_figure(data["leads"]["II"], data["fs"], lead="II", duration_s=4.0,
                                     filter_label=ecg_paper.NO_FILTER_LABEL)
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
    st.markdown(seal_html("registro-real", source), unsafe_allow_html=True)


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
            st.button("Abrir el tema", key=f"bc_open_topic_{organ.key}", on_click=_go_to_topic, args=(topic.key,))
        nav.link("teoria", "Ir a Teoría")


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
        nav.link("cuestionarios", "Ir a Practicar")
        nav.link("mi-sesion", "Tu aprendizaje en esta sesión")


def _render_labs_card() -> None:
    from app.utils import navigation as nav
    from app.utils.patient_banner import peek_active_patient_id

    pid = peek_active_patient_id()
    with st.container(key="bc_card_clinical"):
        st.markdown("### Explorar")
        st.markdown("**Expediente**")
        if pid is None:
            st.caption("Sin paciente activo.")
        else:
            st.markdown(f"Paciente `{pid[:8]}` · {snapshot_count(pid)} estados guardados en el UPS")
        nav.link("gemelo", "Ir al gemelo digital")
        nav.link("comparar", "Comparar pacientes")
        nav.link("pacientes", "Pacientes")


def render_home_dashboard() -> None:
    from app.utils import navigation as nav
    from app.utils.patient_banner import read_active_vitals

    vitals = read_active_vitals()
    _render_sticky(vitals)
    _render_hero()
    _render_monitor(vitals)

    choice = st.pills("Órganos", [o.key for o in C.ORGANS], default=C.ORGANS[0].key, key=C.SELECTED_ORGAN_KEY,
                      format_func=lambda k: C.ORGAN_BY_KEY[k].label)
    organ = C.ORGAN_BY_KEY[choice or C.ORGANS[0].key]

    center, right = st.columns([2, 1], gap="large")
    with center:
        _render_twin_card(organ)
        _render_path(organ)
    with right:
        _render_learn_card(organ)
        _render_practice_card()
        _render_labs_card()

    st.caption("La IA (narrador y explicaciones) es opcional: sin clave, todo lo demás funciona igual.")
    nav.link("ajustes", "Ajustes: clave de IA")
