"""Pantalla de los casos guiados de ECG (2026-11-17). La lógica y el contenido de cada caso viven en su módulo:
`educational/guided_case.py` (caso 1, II, III y aVF) y `educational/guided_case_anterior.py` (caso 2, V1–V4).

- Solo se muestran los casos cuyo documento está FIRMADO (C4: nada sin firmar en la app); con más de uno, se elige.
- El trazado es simulado y se declara con la etiqueta «Simulación».
- Cada decisión pide la confianza (opcional) y se registra en la sesión con source «caso_guiado».
- Fases: grupo → hipótesis inicial → pruebas → hipótesis final → desafío → límite → resumen.
"""
from __future__ import annotations

import streamlit as st

from app.utils import ecg_paper
from app.utils.confidence import record_answer, render_calibration_panel, render_confidence_input
from app.utils.design_system import BADGES
from educational import guided_case as g
from educational import guided_case_anterior as g2
from educational.quiz_bank import stable_shuffle

STATE, DATA, PHASE, FEEDBACK, ATTEMPT = ("guided_case_state", "guided_case_data", "guided_case_phase",
                                         "guided_case_feedback", "guided_case_attempt")
PENDING_SIGNATURE = ("Caso pendiente de firma: el caso guiado se muestra cuando Luis firme "
                     "`docs/contenido/caso_guiado_ecg.md`.")
INTRO = ("Interpreta un ECG de 12 derivaciones paso a paso. No basta con acertar: también cuenta reconocer lo que el "
         "trazado no permite decidir, pedir la prueba que distingue las hipótesis y justificarla.")
NEXT_PHASE = {"grupo": "hipotesis_inicial", "hipotesis_inicial": "pruebas", "limite": "fin"}
CASE_KEY = "guided_case_id"
CASE_TITLES = {g.CASE_ID: "Elevación del ST en II, III y aVF", g2.CASE_ID: g2.TITLE}
PENDING_OTHERS = "{n} caso(s) más pendiente(s) de firma: aparecen cuando Luis firme su documento."


def _cases():
    """Los módulos de caso, en orden (se leen aquí para que una prueba pueda simular la firma de cada uno)."""
    return (g, g2)


def _reset() -> None:
    st.session_state[STATE] = g.Estado()
    st.session_state.pop(DATA, None)
    st.session_state[PHASE] = "grupo"
    st.session_state[FEEDBACK] = None
    st.session_state[ATTEMPT] = st.session_state.get(ATTEMPT, 0) + 1


def _record(c, decision_id: str, correcto: bool, confianza) -> None:
    d = c.DECISION[decision_id]
    record_answer(f"{c.SOURCE}:{c.CASE_ID}:{decision_id}", c.CONCEPT, correcto, confianza,
                  mark=(c.SOURCE, c.CASE_ID, st.session_state[ATTEMPT], decision_id), label=d.pregunta,
                  source=c.SOURCE)


def _decision_form(c, decision_id: str):
    """Pregunta + opciones (barajadas, ninguna elegida) + confianza. Devuelve (opción, confianza) al responder."""
    d = c.DECISION[decision_id]
    st.markdown(f"**{d.pregunta}**")
    opciones = stable_shuffle(d.opciones, f"{c.CASE_ID}:{decision_id}")
    elegida = st.radio("Tu respuesta", opciones, index=None, key=f"guided_{decision_id}_{st.session_state[ATTEMPT]}")
    confianza = render_confidence_input(key=f"guided_{decision_id}_confidence_{st.session_state[ATTEMPT]}")
    if st.button("Responder", key=f"guided_{decision_id}_submit", disabled=elegida is None):
        return elegida, confianza
    return None


def _feedback(c, decision_id: str, correcto: bool) -> None:
    d = c.DECISION[decision_id]
    if correcto:
        st.success(f"✅ Correcto. {d.explicacion}")
    else:
        st.error(f"❌ La respuesta que mejor se sostiene es: **{d.correcta}**. {d.explicacion}")


def _tests(c, estado: g.Estado, data: g.CaseData) -> None:
    st.markdown("**Pide las pruebas que necesites.** Para cada una, elige por qué la pides.")
    for p in c.PRUEBAS:
        with st.expander(p.nombre, expanded=False):
            if p.id in estado.pruebas:
                ev = next(e for e in estado.recorrido if e.tipo == "prueba" and e.id == p.id)
                st.markdown(ev.texto.split(" → ", 1)[1])
                continue
            motivo = st.radio("¿Por qué la pides?", stable_shuffle(p.motivos, p.id), index=None,
                              key=f"guided_test_{p.id}_{st.session_state[ATTEMPT]}")
            if st.button("Pedir", key=f"guided_test_{p.id}_submit", disabled=motivo is None):
                c.pedir_prueba(estado, data, p.id, motivo)
                st.rerun()


def render_guided_case() -> None:
    st.caption(INTRO)
    cases = _cases()
    signed = [c for c in cases if c.case_signed()]
    if not signed:
        st.info(PENDING_SIGNATURE)
        return
    if len(signed) > 1:
        chosen = st.selectbox("Caso", [c.CASE_ID for c in signed], format_func=CASE_TITLES.get, key="guided_case_pick")
    else:
        chosen = signed[0].CASE_ID
    c = next(x for x in signed if x.CASE_ID == chosen)
    if len(signed) < len(cases):
        st.caption(PENDING_OTHERS.format(n=len(cases) - len(signed)))
    if STATE not in st.session_state or st.session_state.get(CASE_KEY) != c.CASE_ID:
        st.session_state[CASE_KEY] = c.CASE_ID
        _reset()
    if DATA not in st.session_state:
        st.session_state[DATA] = c.build_case_data()
    estado: g.Estado = st.session_state[STATE]
    data: g.CaseData = st.session_state[DATA]
    phase = st.session_state[PHASE]

    st.caption(f"{BADGES.label(BADGES.SIMULATION)}: trazado construido por el simulador de 12 derivaciones; las pruebas "
               "muestran lo que mide el analizador de BIOCORE sobre él.")
    ecg_paper.render(ecg_paper.twelve_lead_figure(data.leads, data.fs, filter_label=ecg_paper.NO_FILTER_LABEL),
                     key="guided_case_paper")

    for decision_id in ("grupo", "hipotesis_inicial"):           # decisiones ya respondidas, con su corrección
        if decision_id in estado.respuestas and phase != decision_id:
            st.markdown(f"**{c.DECISION[decision_id].pregunta}** Respondiste: {estado.respuestas[decision_id]}")

    if phase in ("grupo", "hipotesis_inicial", "limite"):
        respuesta = _decision_form(c, phase)
        if respuesta:
            correcto = c.responder(estado, phase, *respuesta)
            _record(c, phase, correcto, respuesta[1])
            st.session_state[FEEDBACK] = (phase, correcto)
            st.session_state[PHASE] = NEXT_PHASE[phase]
            st.rerun()
    if st.session_state[FEEDBACK]:
        _feedback(c, *st.session_state[FEEDBACK])

    if phase == "pruebas":
        _tests(c, estado, data)
        if st.button("Ya puedo concluir", key="guided_to_final"):
            st.session_state[PHASE], st.session_state[FEEDBACK] = "hipotesis_final", None
            st.rerun()

    if phase == "hipotesis_final":
        respuesta = _decision_form(c, "hipotesis_final")
        if respuesta:
            correcto = c.responder(estado, "hipotesis_final", *respuesta)
            _record(c, "hipotesis_final", correcto, respuesta[1])  # cuenta la PRIMERA respuesta (antes del desafío)
            c.desafio(estado, data)
            st.session_state[PHASE] = "desafio"
            st.rerun()

    if phase == "desafio":
        st.markdown(f"**Tu respuesta:** {estado.respuestas['hipotesis_final']}")
        st.warning(f"**Revisor crítico:** {estado.desafio}")
        col1, col2, col3 = st.columns(3)
        if col1.button("Mantengo mi respuesta", key="guided_keep"):
            correcto = estado.respuestas["hipotesis_final"] == c.DECISION["hipotesis_final"].correcta
            st.session_state[FEEDBACK] = ("hipotesis_final", correcto)
            st.session_state[PHASE] = "limite"
            st.rerun()
        if col2.button("Cambio mi respuesta", key="guided_change"):
            st.session_state[PHASE] = "hipotesis_final"
            st.rerun()
        if col3.button("Pido más pruebas", key="guided_more_tests"):
            st.session_state[PHASE] = "pruebas"
            st.rerun()

    if phase == "fin":
        _summary(c, estado)


def _summary(c, estado: g.Estado) -> None:
    st.markdown("### Tu razonamiento en este caso")
    for comp in c.competencias(estado):
        marca = "✔" if comp.lograda else ("✘" if comp.lograda is False else "·")
        st.markdown(f"- {marca} **{comp.nombre}.** {comp.evidencia}")
    st.markdown("### Tu recorrido")
    st.table([{"Paso": i, "Tipo": {"decision": "Decisión", "prueba": "Prueba", "desafio": "Desafío"}[e.tipo],
               "Qué pasó": e.texto,
               "Confianza": f"{e.confianza} %" if e.confianza is not None else "—",
               "Resultado": "—" if e.correcto is None else ("Correcto" if e.correcto else "Revisar")}
              for i, e in enumerate(estado.recorrido, 1)])
    render_calibration_panel()
    if st.button("Empezar de nuevo", key="guided_restart"):
        _reset()
        st.rerun()
