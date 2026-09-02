"""
BIOCORE AI — Academia (unificada)

Fusiona las dos páginas de Academia que existían por separado:
- academia_clinica: su único contenido real eran lecciones/quizzes/casos
  clínicos + modo rural offline (las otras 5 pestañas eran placeholders
  vacíos sin funcionalidad — no se conservan).
- academia_inteligente: de sus pestañas, solo el tutor IA sobrevivió (refundido
  en el narrador clínico real de Digital Twin OS). "Misiones", "Pacientes
  Virtuales" y "Gemelo Digital" se retiraron el 2026-08-09 (Bloque 2, Parte C):
  Pacientes Virtuales y Gemelo Digital eran cáscaras placebo — sin conexión al
  UPS, con generadores de señal demo cuyo parámetro HR no tenía ningún efecto
  real en la salida (confirmado por ejecución: HR=40 y HR=180 producían señal
  idéntica) — y "Gemelo Digital" colisionaba de nombre con el Digital Twin OS
  real. Misiones era honesta pero redundante con "Lecciones y Casos". El
  seguimiento de progreso/XP ya se había retirado antes (ver más abajo).

Consolidado 2026-07-01 a petición del usuario para eliminar la duplicación
entre ambas páginas de Academia.
"""

import streamlit as st
import pandas as pd

from app.utils.design_system import render_module_header, render_error_state
from domain.physiology.narrator import (
    Finding,
    FindingsContext,
    NarratorNotConfiguredError,
    stream_findings_narration,
)
from domain.physiology.narrator import is_configured as narrator_is_configured
from domain.physiology.scenarios.case_bank import generate_case
from domain.physiology.state import (
    EventSeverity,
    init_db,
    make_engine,
    make_session_factory,
)

# Banco de casos sintéticos (Paso 2, 2026-07-14): reutiliza el patrón de
# ocultar->elegir->revelar, los distractores y la deduplicación de eventos
# del modo caso clínico de Twin OS tal cual (`_diagnostic_options`,
# `RICH_SCENARIO_LABELS`, `_dedupe_events`) — sin reconstruir esa mecánica
# aquí. `render_ups_body` viene de su módulo real, no de `twin_shell.pages`,
# para no arrastrar toda esa página como dependencia solo por un símbolo.
# PA calculada (2026-08-06, ver CHANGELOG.md): `_attach_calculated_pa_to_case`/
# `_build_pa_findings` se construyeron primero aquí, luego se EXTRAJERON a
# twin_shell/pages.py al replicar esta conexión al modo caso de Twin OS --
# un solo lugar para la restricción estructural, la resolución de snapshot
# y el texto del prompt, ninguno de los dos modos lo duplica.
from app.supermodules.twin_shell.pages import (
    RICH_SCENARIO_LABELS,
    _attach_calculated_pa_to_case,
    _build_pa_findings,
    _dedupe_events,
    _diagnostic_options,
)
from app.supermodules.twin_shell.ups_body_visual import render_ups_body

try:
    from educational.learning_engine import LearningEngine, LESSON_CATEGORIES, generate_quiz
    LESSONS_AVAILABLE = True
except ImportError:
    LESSONS_AVAILABLE = False

try:
    from educational.ecg_academy import lead_explanations
    THEORY_AVAILABLE = True
except ImportError:
    THEORY_AVAILABLE = False


def render_theory_section() -> None:
    """Teoría — capa de teoría del módulo de aprendizaje (2026-07-14).

    Resurfacea la única teoría real que existía huérfana en el código:
    `educational.ecg_academy.lead_explanations()` — la tabla de las 12
    derivaciones del ECG (qué observa cada una, qué pared representa, qué
    arteria coronaria suele comprometerse). El diccionario se muestra tal
    cual: ningún valor se reescribió ni se generó contenido nuevo. Antes de
    esta tanda, nada en la app viva la llamaba — solo un archivo de
    `_archive/` (código muerto, no ejecutado).

    Se presenta honestamente como lo que es — la tabla de las 12
    derivaciones — no como un "curso completo". Las tarjetas de curso de
    otros temas (Neurofisiología, Fisiología Respiratoria, Músculo y EMG,
    Interpretación Clínica) que vivían en `render_education_page()`
    (`app/main.py`) con una barra de progreso ficticia (`learning_progress`,
    números fijos que subían con cada clic, iguales para cualquier usuario
    — Art. I de la Constitución) se limpiaron aparte, en ese mismo archivo;
    esta lección no las reemplaza ni finge cubrir esos temas.

    Actualización (Fase 4, 2026-08-30): `render_education_page()` (y las
    tarjetas "🚧 en desarrollo" que quedaron tras esta limpieza) se retiró
    por completo del Learning Hub -- ver CHANGELOG.md. Esta función y su
    contenido no cambiaron."""
    with st.expander("📖 Teoría — Las 12 derivaciones del ECG", expanded=False):
        if not THEORY_AVAILABLE:
            st.warning("El módulo de teoría (`educational.ecg_academy`) no está disponible.")
            return

        st.caption(
            "Fuente: `educational.ecg_academy.lead_explanations()` — tabla real ya "
            "existente en el código, mostrada aquí tal cual (nada generado ni inventado "
            "para esta lección)."
        )
        leads = lead_explanations()
        rows = [
            {
                "Derivación": name,
                "Qué observa": info["observes"],
                "Pared": info["wall"],
                "Arteria típica": info["artery"],
            }
            for name, info in leads.items()
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            f"{len(rows)} derivaciones documentadas. Esta es, hoy, la única lección de "
            "teoría con contenido real en el módulo de aprendizaje — ampliar a otros temas "
            "(EEG, EMG, respiratorio, interpretación clínica integrada) requiere escribir "
            "contenido nuevo; no está hecho en esta tanda."
        )


def render_lessons_quizzes_tab() -> None:
    """Lecciones, quizzes y casos clínicos — contenido real portado de la antigua Academia Clínica.

    Fusión Education+Academia, Capa 1 (2026-07-13): el quiz ya no califica en
    bloque al final — cada pregunta sigue el mismo patrón ocultar→elegir→revelar
    del modo caso clínico de Twin OS. La verdad de referencia (¿cuál opción es
    correcta?) la decide `QuizQuestion.answer` — código, nunca el modelo. Al
    responder, el acierto/error se calcula primero por código; el narrador real
    (`stream_findings_narration`, sin tocar `domain/physiology/narrator/*`)
    solo explica el porqué, anclado en la pregunta, la opción elegida y la
    respuesta correcta — mismo motor que ya usa Twin OS, sin construir uno
    nuevo.

    Banco de casos sintéticos, Paso 2 (2026-07-14): la vieja sección "Casos
    clínicos de ejemplo" (`educational.clinical_cases.sample_cases()`)
    filtraba el diagnóstico en la propia etiqueta del botón — lo opuesto de
    un caso ciego. Se reemplazó por `render_synthetic_case_section()`, que
    reutiliza el generador del banco de casos (`case_bank.generate_case`,
    Paso 1) y el mismo patrón ocultar→elegir→revelar del modo caso clínico
    de Twin OS, incluyendo sus distractores y deduplicación de eventos.

    Capa de teoría (2026-07-14): `render_theory_section()` resurfacea la
    única teoría real que existía huérfana en el código —
    `educational.ecg_academy.lead_explanations()`, la tabla de las 12
    derivaciones del ECG — sin generar ni inventar contenido nuevo. Con
    esto el módulo de aprendizaje queda completo: teoría + casos + quizzes."""
    render_theory_section()
    st.markdown("---")

    if not LESSONS_AVAILABLE:
        st.warning("El módulo de lecciones (`educational.learning_engine`) no está disponible.")
        return

    student_id = st.text_input("ID del estudiante", value="estudiante_demo", key="academia_student_id")
    rural_mode_enabled = st.checkbox(
        "Modo Rural (offline, guardar progreso localmente)", value=False, key="academia_rural_mode"
    )

    engine = st.session_state.get("academia_learning_engine")
    if engine is None or getattr(engine, "student_id", None) != student_id:
        engine = LearningEngine(student_id=student_id)
        st.session_state["academia_learning_engine"] = engine
        if rural_mode_enabled:
            try:
                engine.load_progress_local()
                st.success("Progreso cargado desde almacenamiento local (Modo Rural)")
            except Exception:
                st.warning("No se encontró progreso local o falló la carga.")

    # Fusión Education+Academia, Capa 1 (2026-07-13): antes se guardaba el
    # progreso real (rural_mode) pero nunca se mostraba de vuelta. Ahora sí.
    if engine.get_progress():
        with st.expander("📊 Tu progreso guardado", expanded=False):
            for lesson_id, data in engine.get_progress().items():
                estado = "✅ completada" if data.get("completed") else "⏳ en curso"
                st.markdown(f"- **{lesson_id}** — {estado}, puntuación {data.get('score', 0):.1f}%")

    col1, col2 = st.columns([1, 2])

    with col1:
        lesson = st.selectbox("Lección", LESSON_CATEGORIES, key="academia_lesson")
        level = st.radio("Nivel", ["basic", "intermediate", "advanced"], key="academia_level")
        if st.button("Iniciar Quiz", key="academia_start_quiz"):
            questions = generate_quiz(topic="ecg_basics", level=level, lesson=lesson)
            st.session_state["academia_quiz"] = {
                "lesson_id": lesson, "questions": questions, "responses": {}, "current_q": 0,
                "answered_current": False, "feedback": None, "feedback_error": None,
            }
            st.rerun()

    with col2:
        quiz_state = st.session_state.get("academia_quiz")
        if not quiz_state:
            st.info("Inicia un quiz para comenzar.")
        elif not quiz_state["questions"]:
            st.warning(f"No hay preguntas reales todavía para la lección '{quiz_state['lesson_id']}'.")
        else:
            questions = quiz_state["questions"]
            current = quiz_state["current_q"]
            total = len(questions)
            q = questions[current]
            st.write(f"Pregunta {current + 1} de {total} — {quiz_state['lesson_id']}")
            st.markdown(f"**{q.prompt}**")
            choice_key = f"academia_quiz_choice_{current}"

            if not quiz_state["answered_current"]:
                selected = st.radio("Opciones", q.choices, key=choice_key)

                if not narrator_is_configured():
                    st.warning(
                        "`ANTHROPIC_API_KEY` no está configurada — el feedback fundamentado "
                        "requiere la API real de Anthropic, sin narración simulada de respaldo."
                    )

                if st.button("Responder", key=f"academia_quiz_submit_{current}") and narrator_is_configured():
                    idx = q.choices.index(selected)
                    quiz_state["responses"][current] = idx

                    findings = [
                        Finding(name="Pregunta", value=q.prompt, meaning="Enunciado de la pregunta del quiz."),
                        Finding(
                            name="Opción elegida por el estudiante", value=q.choices[idx],
                            meaning="Respuesta que el estudiante seleccionó — evalúala contra la correcta.",
                        ),
                        Finding(
                            name="Respuesta correcta (verdad de referencia)", value=q.choices[q.answer],
                            meaning=(
                                q.explanation
                                or "Respuesta correcta según el banco de preguntas — verdad de referencia "
                                   "decidida por código, no por el modelo."
                            ),
                        ),
                    ]
                    findings_context = FindingsContext(lab_name=f"Quiz — {quiz_state['lesson_id']}", findings=findings)
                    try:
                        quiz_state["feedback"] = "".join(stream_findings_narration(findings_context))
                        quiz_state["feedback_error"] = None
                    except NarratorNotConfiguredError as exc:
                        quiz_state["feedback"] = None
                        quiz_state["feedback_error"] = str(exc)
                    except Exception as exc:  # llamada real a la API — puede fallar por red/cuota/etc.
                        quiz_state["feedback"] = None
                        quiz_state["feedback_error"] = f"Error llamando a la API de Anthropic: {exc}"

                    quiz_state["answered_current"] = True
                    st.rerun()
            else:
                idx = quiz_state["responses"][current]
                correct = idx == q.answer
                if correct:
                    st.success(f"✅ Correcto — {q.choices[q.answer]}")
                else:
                    st.error(f"❌ Elegiste **{q.choices[idx]}** — la respuesta correcta es **{q.choices[q.answer]}**")

                st.markdown("**Feedback del narrador (fundamentado):**")
                if quiz_state["feedback"]:
                    st.markdown(quiz_state["feedback"])
                elif quiz_state["feedback_error"]:
                    render_error_state(quiz_state["feedback_error"])

                is_last = current + 1 >= total
                if st.button("Finalizar quiz" if is_last else "➡️ Siguiente pregunta", key=f"academia_quiz_next_{current}"):
                    if is_last:
                        score = engine.submit_quiz(quiz_state["lesson_id"], questions, quiz_state["responses"])
                        st.session_state["academia_result"] = {"score": score, "responses": dict(quiz_state["responses"])}
                        if rural_mode_enabled:
                            try:
                                engine.save_progress_local()
                                st.success("Progreso guardado localmente (Modo Rural)")
                            except Exception:
                                st.warning("No se pudo guardar el progreso localmente.")
                        st.session_state["academia_quiz"] = None
                    else:
                        quiz_state["current_q"] = current + 1
                        quiz_state["answered_current"] = False
                        quiz_state["feedback"] = None
                        quiz_state["feedback_error"] = None
                    st.rerun()

        if "academia_result" in st.session_state:
            res = st.session_state["academia_result"]
            st.success(f"Quiz finalizado — Puntuación: {res['score']:.1f}%")
            st.write("Respuestas enviadas:")
            st.json(res["responses"])

    st.markdown("---")
    render_synthetic_case_section()


def render_synthetic_case_section() -> None:
    """Casos clínicos sintéticos (Paso 2, 2026-07-14) — capa de casos del
    módulo de aprendizaje, sobre el banco de casos (`case_bank.generate_case`,
    Paso 1). Reutiliza el mismo patrón ocultar→elegir→revelar, los mismos
    distractores y la misma deduplicación de eventos del modo caso clínico
    de Twin OS (`_diagnostic_options`, `RICH_SCENARIO_LABELS`,
    `_dedupe_events` — importados, no reescritos) y el mismo
    `stream_findings_narration` — ninguna mecánica nueva.

    Reemplaza la sección pasiva "Casos clínicos de ejemplo" (basada en
    `educational.clinical_cases.sample_cases()`), que filtraba el
    diagnóstico en la propia etiqueta del botón ("Cargar caso ...:
    <diagnóstico>") — lo opuesto de un caso ciego. Los patrones generables
    son exactamente los 12 reales de `SimulationScenario`; ampliar la
    variedad de patologías requiere ampliar el simulador
    (`app/engines/simulation_engine.py`), no este banco (ver docstring de
    `domain/physiology/scenarios/case_bank.py`).

    Ocultamiento: el nombre del escenario (`RICH_SCENARIO_LABELS[hidden]`)
    solo se renderiza DESPUÉS de confirmar — antes de eso, todo lo que se
    muestra (cuerpo, descriptores, eventos) viene de `ClinicalCase.state`/
    `.events`, que no exponen el escenario que los generó.

    Nota deliberada: a diferencia del modo caso clínico de Twin OS, el
    feedback NO se arma con `build_context()` — ese helper siempre lee el
    último snapshot persistido (`get_latest_state`), pero `generate_case()`
    puede elegir CUALQUIERA de los 6 horizontes reales como "el caso"
    (Paso 1: variación honesta del punto de la evolución). Si el horizonte
    elegido no es el último, `build_context()` alimentaría al narrador con
    datos de un momento distinto al que el estudiante realmente vio —
    desanclado. Por eso las `Finding` se arman directamente desde el mismo
    `state`/`events` guardados en sesión (los que efectivamente se
    mostraron), no desde una relectura de "lo último" en el UPS."""
    with st.expander("🧪 Caso clínico sintético (diagnóstico ciego)", expanded=False):
        st.caption(
            "🧪 Caso **simulado** por el banco de casos de BIOCORE — no es un paciente real. "
            "Es una variación honesta de uno de los 12 escenarios reales del simulador "
            "(distinto punto de partida, distinto punto de la evolución), sin revelar cuál. "
            "Diagnostica eligiendo entre 4 opciones; el feedback lo genera el narrador real "
            "(Anthropic), fundamentado en los descriptores y eventos que este caso contiene."
        )

        if not narrator_is_configured():
            st.warning(
                "`ANTHROPIC_API_KEY` no está configurada — el feedback fundamentado requiere la "
                "API real de Anthropic, sin narración simulada de respaldo."
            )
            return

        if "academia_case_session_factory" not in st.session_state:
            engine = make_engine()
            init_db(engine)
            st.session_state["academia_case_session_factory"] = make_session_factory(engine)
        session_factory = st.session_state["academia_case_session_factory"]

        if st.button("🆕 Nuevo caso sintético", key="academia_case_new"):
            with session_factory() as session:
                case = generate_case(session)

                # Conexión a la PA calculada del motor hemodinámico validado
                # (2026-08-06, ver CHANGELOG.md) -- `_attach_calculated_pa_to_case()`
                # (compartida con Twin OS, definida en twin_shell/pages.py) aplica la
                # restricción ESTRUCTURAL a los 3 escenarios validados y resuelve el
                # snapshot EXACTO del horizonte que generate_case() eligió (no
                # necesariamente el último -- get_latest_snapshot_id() daría el
                # snapshot equivocado aquí). Para los otros 9 escenarios, devuelve el
                # caso intacto sin calcular nada.
                case_state, case_references = _attach_calculated_pa_to_case(
                    session, case.patient_id, case.scenario.value, case.state,
                    source_detail="academia_synthetic_case",
                )

            st.session_state["academia_case_patient_id"] = case.patient_id
            st.session_state["academia_case_hidden_scenario"] = case.scenario
            st.session_state["academia_case_state"] = case_state
            st.session_state["academia_case_events"] = _dedupe_events(case.events)
            st.session_state["academia_case_parametros"] = case.parametros
            st.session_state["academia_case_reference_pa"] = case_references
            st.session_state["academia_case_options"] = _diagnostic_options(case.scenario)
            st.session_state["academia_case_answered"] = False
            st.session_state["academia_case_selected"] = None
            st.session_state["academia_case_feedback"] = None
            st.session_state["academia_case_feedback_error"] = None
            st.rerun()

        patient_id = st.session_state.get("academia_case_patient_id")
        if not patient_id:
            st.caption("Sin ningún caso activo todavía — pulsa 'Nuevo caso sintético' para empezar.")
            return

        state = st.session_state["academia_case_state"]
        events = st.session_state["academia_case_events"]

        st.markdown("#### Estado del paciente — diagnóstico oculto")
        render_ups_body(state)

        desc_rows = [
            {
                "Dominio": domain_state.domain,
                "Descriptor": d.name,
                "Valor": f"{d.value:.1f} {d.unit}",
                "Procedencia": d.provenance.value,
                "Confianza": f"{d.confidence:.0%}",
            }
            for domain_state in state.all_domains().values()
            for d in domain_state.descriptors.values()
        ]
        st.dataframe(pd.DataFrame(desc_rows), use_container_width=True, hide_index=True)

        map_modelo = state.cardiovascular.get("map_modelo")
        if map_modelo is not None:
            systolic_modelo = state.cardiovascular.get("systolic_bp_modelo")
            diastolic_modelo = state.cardiovascular.get("diastolic_bp_modelo")
            references_pa = st.session_state.get("academia_case_reference_pa") or []
            ref_map = next((r for r in references_pa if r.descriptor == "map"), None)
            st.markdown(
                f"**🧮 PA calculada por el modelo hemodinámico (lazo cerrado, validado):** "
                f"{systolic_modelo.value:.0f}/{diastolic_modelo.value:.0f} mmHg "
                f"(PAM {map_modelo.value:.0f} mmHg, confianza {map_modelo.confidence:.0%})"
                + (f" — referencia clínica citada: PAM {ref_map.value:.0f} mmHg" if ref_map else "")
            )
            st.caption(
                "Valor CALCULADO por el modelo a partir del heart_rate real de este caso -- no es una "
                "medición del paciente ni un valor de guía clínica. Solo disponible para sano/"
                "hipertensión/sepsis (los 3 escenarios con validación experta completa del motor "
                "hemodinámico); en el resto de los 12 escenarios este caso no muestra PA calculada."
            )

        if events:
            st.markdown("**Eventos detectados:**")
            for evt in events:
                icon = "🔴" if evt.severity == EventSeverity.CRITICAL else "🟡"
                st.caption(f"{icon} `{evt.event_type.value}` — {evt.description}")

        options = st.session_state["academia_case_options"]

        if not st.session_state["academia_case_answered"]:
            choice = st.radio(
                "¿Cuál es tu diagnóstico?",
                options,
                format_func=lambda s: RICH_SCENARIO_LABELS[s],
                key=f"academia_case_radio_{patient_id}",
            )
            if st.button("✅ Confirmar diagnóstico", key=f"academia_case_confirm_{patient_id}"):
                hidden = st.session_state["academia_case_hidden_scenario"]

                # PA calculada (2026-08-06, ver CHANGELOG.md): `_build_pa_findings()`
                # (compartida con Twin OS, definida en twin_shell/pages.py) arma el
                # Finding con instrucción explícita de porqué fisiológico, el de la
                # referencia clínica si coexiste, y la nota de divergencia con la cita
                # adaptada al escenario -- nada de esto se reescribe aquí.
                references_pa = st.session_state.get("academia_case_reference_pa") or []
                pa_findings = _build_pa_findings(state, references_pa, hidden.value)

                findings = [
                    Finding(
                        name=d.name,
                        value=f"{d.value} {d.unit}",
                        meaning=(
                            f"Dominio {domain_state.domain}, procedencia {d.provenance.value}, "
                            f"confianza {d.confidence:.0%}."
                        ),
                    )
                    for domain_state in state.all_domains().values()
                    for d in domain_state.descriptors.values()
                ] + [
                    Finding(name=e.event_type.value, value=e.severity.value, meaning=e.description)
                    for e in events
                ] + pa_findings + [
                    Finding(
                        name="Diagnóstico elegido por el estudiante",
                        value=RICH_SCENARIO_LABELS[choice],
                        meaning="Evalúalo contra los datos anteriores — no lo repitas como si fuera un campo técnico.",
                    ),
                    Finding(
                        name="Diagnóstico correcto (verdad de referencia del caso)",
                        value=RICH_SCENARIO_LABELS[hidden],
                        meaning=(
                            "Viene del escenario real que efectivamente generó este caso sintético en "
                            "el banco de casos, no de tu criterio. Explica por qué los "
                            "descriptores/eventos anteriores encajan con este diagnóstico y, si la "
                            "hipótesis del estudiante es distinta, por qué esos mismos datos no "
                            "encajan con ella."
                        ),
                    ),
                ]
                findings_context = FindingsContext(lab_name="Caso Clínico Sintético", findings=findings)

                try:
                    feedback_text = "".join(stream_findings_narration(findings_context))
                    st.session_state["academia_case_feedback"] = feedback_text
                    st.session_state["academia_case_feedback_error"] = None
                except NarratorNotConfiguredError as exc:
                    st.session_state["academia_case_feedback"] = None
                    st.session_state["academia_case_feedback_error"] = str(exc)
                except Exception as exc:  # llamada real a la API — puede fallar por red/cuota/etc.
                    st.session_state["academia_case_feedback"] = None
                    st.session_state["academia_case_feedback_error"] = f"Error llamando a la API de Anthropic: {exc}"

                st.session_state["academia_case_selected"] = choice
                st.session_state["academia_case_answered"] = True
                st.rerun()
        else:
            selected = st.session_state["academia_case_selected"]
            hidden = st.session_state["academia_case_hidden_scenario"]
            correct = selected == hidden

            if correct:
                st.success(f"✅ ¡Correcto! El caso era: {RICH_SCENARIO_LABELS[hidden]}")
            else:
                st.error(
                    f"❌ Elegiste {RICH_SCENARIO_LABELS[selected]} — el caso real era "
                    f"{RICH_SCENARIO_LABELS[hidden]}"
                )

            parametros = st.session_state["academia_case_parametros"]
            st.caption(
                "🧪 Recordatorio: este caso es una simulación generada por el banco de casos de "
                f"BIOCORE (`{parametros['escenario']}`, horizonte `{parametros['horizonte_elegido']}`), "
                "no un paciente real."
            )

            st.markdown("**Feedback del narrador (fundamentado):**")
            if st.session_state["academia_case_feedback"]:
                st.markdown(st.session_state["academia_case_feedback"])
            elif st.session_state["academia_case_feedback_error"]:
                render_error_state(st.session_state["academia_case_feedback_error"])

            if st.button("➡️ Otro caso", key="academia_case_next"):
                for k in [
                    "academia_case_patient_id", "academia_case_hidden_scenario", "academia_case_state",
                    "academia_case_events", "academia_case_parametros", "academia_case_reference_pa",
                    "academia_case_options", "academia_case_answered", "academia_case_selected",
                    "academia_case_feedback", "academia_case_feedback_error",
                ]:
                    st.session_state.pop(k, None)
                st.rerun()


def render_tutor_tab() -> None:
    """Fase 1.3: el chatbot de keywords (`app/biomedical_tutor.py`) fue
    eliminado — refundido en el narrador clínico real de `Digital Twin OS`,
    que lee el UPS en vez de responder desde un diccionario hardcodeado. No
    se recrea un chat aquí (evitaría el patrón de chatbot aislado, Art. I de
    la Constitución). Consolidación, Tanda 3 (2026-07-13): el AI Hub que
    exponía ese mismo narrador por una segunda puerta se eliminó — queda un
    único lugar."""
    st.header("🩺 Tutor IA Biomédico")
    st.info(
        "El tutor de preguntas y respuestas se consolidó en el **Narrador Clínico**, "
        "dentro de **Digital Twin OS** — ahí la explicación se genera con IA real, "
        "fundamentada en el estado fisiológico actual del paciente, no desde un "
        "diccionario de palabras clave."
    )


# Consolidación, Tanda 1 (2026-07-13): render_progress_tab() se eliminó — "Nivel"
# (5), "XP Total" (1250), "Misiones Completadas" (8) y la lista de "Habilidades
# Desbloqueadas" eran literales fijos, iguales para cualquier usuario en
# cualquier sesión (Art. I de la Constitución). No había ningún progreso real
# que mostrar de otra forma, así que se quitó la pestaña completa en vez de
# dejarla vacía con un disclaimer.


def main() -> None:
    # NOTE: st.set_page_config() is already called once by app/main.py — must
    # not be repeated here (this was the root cause of the old Academia
    # Clínica "Clínica" tab silently failing every render).
    render_module_header("Academia BIOCORE AI", icon="🏫")
    st.caption("Lecciones, casos clínicos y tutor IA.")

    tabs = st.tabs(["📝 Lecciones y Casos", "📖 Tutor IA"])

    with tabs[0]:
        render_lessons_quizzes_tab()
    with tabs[1]:
        render_tutor_tab()


def run() -> None:
    """Wrapper entrypoint compatible with importing as `run` from supermodules."""
    return main()
