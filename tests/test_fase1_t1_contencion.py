"""Fase 1 de la propuesta, tanda 1, PARTE A (2026-11-15, Art. I): contención.

Golden test común a TODOS los cuestionarios (respiratorio, Academia, ECG-12, EEG): al abrir, ninguna pregunta muestra
«Correcto» ni «Incorrecto» ni trae una opción preseleccionada, y responder mal muestra «Incorrecto» con la explicación.
Además: HRV sin el selector placebo, ECG-12 sin la pestaña que solo redirigía, explicaciones en capas sin relleno
genérico, Multisensor sin «Health Score», y la base de desarrollo sin filas de tipos retirados.
"""

import re
import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from domain.physiology.state import EventType

MAIN = str(Path("app/main.py").resolve())


def _feedback(at):
    return [s.value for s in at.success] + [e.value for e in at.error]


def _no_verdict(at):
    joined = " ".join(_feedback(at))
    return "Correcto" not in joined and "Incorrecto" not in joined


# --------------------------------------------------------------------------------------------- 1. respiratorio
def _resp(**kw):
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=120)
    at.run()
    assert at.exception == [], at.exception
    return at


def _quiz_type(at, option):
    next(r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")).set_value(option).run()


@pytest.fixture(scope="module")
def resp():
    return _resp()


@pytest.mark.parametrize("quiz", ["Diferenciación Apnea", "Factores de Riesgo", "Correlación cardiovascular (guía AASM)",
                                  "Frecuencia de esta señal", "Contar las apneas de esta señal"])
def test_the_respiratory_quiz_never_answers_itself(resp, quiz):
    at = resp
    _quiz_type(at, quiz)
    assert _no_verdict(at), (quiz, _feedback(at))
    answers = [r for r in at.radio if r.label.startswith("Tu respuesta")]
    assert len(answers) == 1 and answers[0].value is None, quiz                       # nada preseleccionado
    assert not any(str(o).startswith("✓") or "✓" in str(o) for o in answers[0].options), answers[0].options
    # responder mal -> «Incorrecto» con la explicación
    from app.supermodules.respiratory_lab import views

    if quiz in views.CONCEPT_QUIZ:
        item = views.CONCEPT_QUIZ[quiz]
        wrong = next(o for i, o in enumerate(item["options"]) if i != item["correct"])
        answers[0].set_value(wrong).run()
        err = " ".join(e.value for e in at.error)
        assert "Incorrecto:" in err and len(err) > 60, err
    else:
        correct = next(o for o in answers[0].options)  # cualquier opción sirve para probar que solo responde al elegir
        answers[0].set_value(correct).run()
        assert _feedback(at), quiz


def test_the_correct_option_is_not_always_the_first():
    from app.supermodules.respiratory_lab import views

    assert {item["correct"] for item in views.CONCEPT_QUIZ.values()} != {0}


# ------------------------------------------------------------------------------------------------- 2. Academia
def _academia_quiz():
    def _script():
        from app.supermodules.academia.pages import render_quiz_section
        render_quiz_section()

    at = AppTest.from_function(_script, default_timeout=120)
    at.run()
    assert at.exception == []
    return at


def test_the_academia_quiz_never_answers_itself():
    at = _academia_quiz()
    assert _no_verdict(at)
    at.button(key="academia_start_quiz").click().run()
    assert _no_verdict(at)
    choice = next(r for r in at.radio if r.label == "Opciones")
    assert choice.value is None                                                         # nada preseleccionado
    assert at.button(key="academia_quiz_submit_0").disabled                            # no se responde sin elegir
    quiz = at.session_state["academia_quiz"]
    q = quiz["questions"][0]
    wrong = next(c for i, c in enumerate(q.choices) if i != q.answer)
    choice.set_value(wrong).run()
    assert _no_verdict(at)                                                              # elegir no corrige: responder sí
    at.button(key="academia_quiz_submit_0").click().run()
    err = " ".join(e.value for e in at.error)
    assert "Incorrecto" in err and q.choices[q.answer] in err                           # dice cuál era la correcta


# --------------------------------------------------------------------------------------------------- 3. ECG-12
def test_the_ecg12_quiz_never_answers_itself():
    def _script():
        from app.supermodules.ecg_12.quiz import render_ecg12_quiz
        render_ecg12_quiz()

    from educational.quiz_bank import ECG12_QUESTIONS   # integración 2026-11-16: el banco con fuentes

    at = AppTest.from_function(_script, default_timeout=60)
    at.run()
    assert at.exception == [] and _no_verdict(at)
    radio = at.radio[0]
    assert radio.value is None and at.button(key="ecglab_12_quiz_verify").disabled
    q = ECG12_QUESTIONS[0]
    radio.set_value(next(o for o in q.display_choices() if not q.is_correct(o))).run()
    assert _no_verdict(at)
    at.button(key="ecglab_12_quiz_verify").click().run()
    err = " ".join(e.value for e in at.error)
    assert "Incorrecto" in err and q.explanation in err
    assert len(ECG12_QUESTIONS) == 19


# ------------------------------------------------------------------------------------------------------ 4. EEG
def test_the_eeg_quiz_never_answers_itself():
    def _script():
        from app.supermodules.eeg_neuro_lab.teaching import render_eeg_quiz
        render_eeg_quiz(expanded=True)

    from educational.quiz_bank import EEG_QUESTIONS   # integración 2026-11-16: el banco con fuentes

    at = AppTest.from_function(_script, default_timeout=60)
    at.run()
    assert at.exception == [] and _no_verdict(at)
    assert all(r.value is None for r in at.radio) and len(at.radio) == len(EEG_QUESTIONS)
    assert at.button(key="submit_eeg_quiz").disabled                                   # antes calificaba la 1ª opción
    for r, item in zip(at.radio, EEG_QUESTIONS):
        r.set_value(next(o for o in item.display_choices() if not item.is_correct(o)))
    at.run()
    at.button(key="submit_eeg_quiz").click().run()
    text = " ".join(m.value for m in at.markdown)
    assert text.count("Incorrecto") == len(EEG_QUESTIONS) and EEG_QUESTIONS[0].explanation in text
    assert not any(o in ("Sleep Spindle", "Seizure", "Artifact") for item in EEG_QUESTIONS for o in item.choices)


def test_case_modes_require_an_explicit_choice_before_confirming():
    for path in ("app/supermodules/academia/pages.py", "app/supermodules/twin_shell/pages.py"):
        src = Path(path).read_text(encoding="utf-8")
        block = src[src.index('"¿Cuál es tu diagnóstico?"'):]
        assert "index=None" in block[:300] and "disabled=choice is None" in block[:600], path


# ------------------------------------------------------------------------------- 5. HRV, ECG-12, capas, Multisensor
def test_hrv_has_no_placebo_view_selector_and_keeps_its_three_sections():
    src = Path("app/main.py").read_text(encoding="utf-8")
    body = src[src.index("def render_hrv_page"):src.index("def render_patient_pipeline_page")]
    assert "render_view_selector" not in body
    for kept in ("¿Qué afecta la HRV?", "Explicación con IA de estos valores", "Simulación de variabilidad"):
        assert kept in body, kept


def test_ecg12_no_longer_has_a_redirect_only_tab():
    src = Path("app/supermodules/ecg_12/pages.py").read_text(encoding="utf-8")
    assert "st.tabs" not in src and "Vista Educativa" not in src


def test_layered_explanations_show_only_layers_written_for_that_number():
    # T2 (2026-11-18): las llamadas de FC, SDNN, RMSSD y pNN50 viven en los instrumentos; la guardia mira los dos lugares.
    src = "\n".join(f.read_text(encoding="utf-8") for f in [Path("app/main.py"), *sorted(Path("app/instruments").glob("*.py"))])
    src = " ".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))      # el comentario las cita
    for filler in ("Valor clínico cuantitativo que resume", "Permite priorizar decisiones clínicas",
                   "Fármacos, estado hemodinámico, respiración", "Interacciona con ventilación, oxigenación",
                   "Un cambio significativo sugiere intervención", "parasympathetic tone proxy", "neurogenic factors"):
        assert filler not in src, filler

    # Pulido profesional (2026-11-16, extendida): las capas ya no se pueden escribir a mano en cada llamada; solo salen de
    # un tema firmado con su fuente, y sin tema no hay expander. Además, el texto genérico de la frecuencia cardiaca
    # (sustituido por el tema 2 firmado) no puede volver.
    for filler in ("Principal indicador de estado cardiovascular", "Ejercicio, arritmias, fármacos, volumen intravascular",
                   "Afecta perfusión, demanda metabólica", "Cambios bruscos pueden indicar arritmia o shock",
                   "Frecuencia cardíaca derivada del ECG."):
        assert filler not in src, filler

    def _script():
        from app.main import render_metric_explained
        from app.supermodules.learn_theory import SIGNED_HEART_RATE

        render_metric_explained("pNN50", "45.8", unit="%")
        render_metric_explained("Frecuencia cardíaca", "72", unit="lpm", topic=SIGNED_HEART_RATE)

    at = AppTest.from_function(_script, default_timeout=60)
    at.run()
    assert at.exception == []
    assert [e.label for e in at.expander] == ["¿Qué significa Frecuencia cardíaca?"]      # pNN50 sin tema: sin capas
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Fuente: [MCM] · [RCP2017]" in text
    assert "¿Por qué importa?" not in text and "¿Qué pasaría si cambia?" not in text


def test_multisensor_has_no_health_score_anywhere():
    src = Path("app/main.py").read_text(encoding="utf-8")
    body = src[src.index("def render_multisensor_page"):src.index("def render_hrv_page")]
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "health_score()" not in code and "'Health Score" not in code and "Health Score (" not in code
    assert "Heart Rate" not in code and " bpm" not in code


# --------------------------------------------------------------------------------- 7. eventos y base de desarrollo
def test_retired_event_types_left_the_catalog():
    assert {e.name for e in EventType} == {"PULSE_NEWS2_3_POINTS", "SPO2_NEWS2_3_POINTS"}
    builder = Path("domain/physiology/state/builder.py").read_text(encoding="utf-8")
    assert "SEVERE_MUSCLE_FATIGUE_EMG" not in builder and "fatigue_index > 80" not in builder


def test_the_dev_database_has_no_rows_of_retired_types_and_backups_exist():
    db = Path("data/biocore_ups.db")
    if not db.exists():
        pytest.skip("sin base de desarrollo en este entorno")
    c = sqlite3.connect(db)
    types = {t for (t,) in c.execute("select distinct event_type from ups_events")}
    lung_health = c.execute(
        "select count(*) from ups_values where domain='respiratory' and descriptor='health_score'").fetchone()[0]
    c.close()
    assert all(EventType(t) for t in types)                                            # toda fila se puede leer
    assert lung_health == 0
    assert Path("data/biocore_ups.backup-20261115-fase1-t1.db").exists()
