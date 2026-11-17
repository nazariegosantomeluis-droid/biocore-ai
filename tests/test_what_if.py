"""«¿Qué pasa si…?» (Practicar → `what-if`): la respuesta correcta sale del motor de lazo cerrado, ningún número del
motor se ve antes de enviar, lo que está en revisión clínica no se califica ni se registra, y lo registrado usa la
fuente "what_if" y el concepto "hemodinamica". La base del UPS y la de aprendizaje van redirigidas por `conftest.py`."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app.supermodules.what_if as W

MAIN = str(Path("app/main.py").resolve())


def _fake_engine(values):
    """Motor falso: `values[(escenario, fc)]` = dict de salidas. Registra las llamadas."""
    calls = []

    def engine(scenario, hr):
        calls.append((scenario, hr))
        return dict(values[(scenario, hr)], converged=True)

    engine.calls = calls
    return engine


def _open(monkeypatch=None, engine=None):
    if engine is not None:
        monkeypatch.setattr(W, "engine_outputs", engine)
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "what-if"
    at.run()
    assert at.exception == [], at.exception
    return at


def _predict_all(at, choice):
    for r in [r for r in at.radio if r.key and r.key.startswith("what_if_pred_")]:
        r.set_value(choice)
    at.run()
    next(b for b in at.button if b.label == "Enviar predicción").click()
    at.run()
    assert at.exception == [], at.exception
    return at


# ── La respuesta correcta sale del motor ───────────────────────────────────────────────────────────────────────────
def test_the_correct_answer_is_the_sign_the_engine_computed_and_flips_with_it(monkeypatch):
    case = W.CASES[0]
    up = {(case.scenario, case.hr_base): {"pam": 90.0, "gc": 5.0, "vs": 70.0},
          (case.scenario, case.hr_new): {"pam": 100.0, "gc": 6.0, "vs": 80.0}}
    down = {(case.scenario, case.hr_base): up[(case.scenario, case.hr_base)],
            (case.scenario, case.hr_new): {"pam": 80.0, "gc": 4.0, "vs": 60.0}}
    predictions = {k: W.UP for k, *_ in W.OUTPUTS}

    monkeypatch.setattr(W, "engine_outputs", _fake_engine(up))
    assert all(W.grade(case, predictions)[k]["correct"] for k, *_ in W.OUTPUTS)
    monkeypatch.setattr(W, "engine_outputs", _fake_engine(down))              # el motor da el signo contrario
    result = W.grade(case, predictions)
    assert not any(result[k]["correct"] for k, *_ in W.OUTPUTS)
    assert all(result[k]["actual"] == W.DOWN for k, *_ in W.OUTPUTS)


def test_the_page_grades_against_the_engine_end_to_end(monkeypatch):
    case = W.CASES[0]
    engine = _fake_engine({(case.scenario, case.hr_base): {"pam": 90.0, "gc": 5.0, "vs": 70.0},
                           (case.scenario, case.hr_new): {"pam": 80.0, "gc": 4.0, "vs": 60.0}})
    at = _predict_all(_open(monkeypatch, engine), W.UP)
    df = at.dataframe[0].value
    assert list(df["Cambio según el motor"]) == [W.DOWN] * 3 and list(df["Resultado"]) == ["✗ no"] * 3


def test_the_real_engine_signs_and_the_no_change_threshold():
    """Sano, FC 72 → 50: el barorreflejo devuelve la PAM a su punto de ajuste (sin cambio), el gasto baja, el VS sube."""
    case = next(c for c in W.CASES if c.key == "sano_fc_50")
    result = W.grade(case, {k: W.SAME for k, *_ in W.OUTPUTS})
    assert [result[k]["actual"] for k, *_ in W.OUTPUTS] == [W.SAME, W.DOWN, W.UP] and result["_converged"]
    assert W.engine_outputs(case.scenario, case.hr_new) == W.engine_outputs(case.scenario, case.hr_new)  # determinista
    assert W.direction(100.0, 100.0 * (1 + W.NO_CHANGE_REL * 0.99)) == W.SAME
    assert W.direction(100.0, 100.0 * (1 + W.NO_CHANGE_REL * 1.01)) == W.UP
    for c in W.CASES:                                                       # toda la lista cerrada converge
        assert W.grade(c, {k: W.SAME for k, *_ in W.OUTPUTS})["_converged"], c.key


# ── Nada del motor antes de enviar ─────────────────────────────────────────────────────────────────────────────────
def test_no_engine_number_is_shown_before_submitting(monkeypatch):
    from test_fase1_t2_pulido import visible_texts

    case = W.CASES[0]
    engine = _fake_engine({(case.scenario, case.hr_base): {"pam": 93.33, "gc": 5.04, "vs": 70.0},
                           (case.scenario, case.hr_new): {"pam": 93.33, "gc": 4.42, "vs": 88.43}})
    at = _open(monkeypatch, engine)
    assert engine.calls == []                                                  # el motor ni se corrió
    assert not at.dataframe and not at.metric
    text = " ".join(visible_texts(at))
    for number in ("93.3", "5.04", "4.42", "88.4", "70.0"):
        assert number not in text, number
    assert W.NO_CHANGE_LABEL in " ".join(c.value for c in at.caption)        # el umbral, rotulado y visible
    send = next(b for b in at.button if b.label == "Enviar predicción")
    assert send.disabled                                                       # sin predicciones no se envía
    _predict_all(at, W.SAME)
    assert len(engine.calls) == 2 and at.dataframe                             # basal e intervención


# ── Revisión clínica: ni se califica ni se registra ────────────────────────────────────────────────────────────────
def test_what_is_in_clinical_review_is_neither_graded_nor_logged(monkeypatch):
    review = W.WhatIfCase("revision", "healthy", "Caso en revisión", 72.0, 50.0,
                          in_review="capacitancia venosa 2× — Criterio BIOCORE, sin cita (en revisión clínica)")
    monkeypatch.setattr(W, "CASES", (review,))
    at = _predict_all(_open(), W.SAME)
    assert "session_learning_log" not in at.session_state or at.session_state["session_learning_log"] == []
    assert set(at.dataframe[0].value["Resultado"]) == {"no se califica"}
    assert any("En revisión clínica" in w.value for w in at.warning)
    assert any("No se califica ni se registra" in i.value for i in at.info)


def test_the_closed_list_offers_nothing_that_depends_on_values_in_review():
    assert all(c.in_review is None and c.scenario in ("healthy", "hypertension") for c in W.CASES)
    assert all(40 <= c.hr_new <= 220 for c in W.CASES)                         # barrido validado del motor


# ── Lo registrado ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_each_graded_prediction_is_logged_as_what_if_hemodinamica():
    at = _open()
    for s in [s for s in at.slider if s.key and s.key.startswith("what_if_conf_")]:
        s.set_value(80)
    at = _predict_all(at, W.SAME)
    log = at.session_state["session_learning_log"]
    case = W.CASES[0]
    assert [e["item_id"] for e in log] == [f"what_if:{case.key}:{k}" for k, *_ in W.OUTPUTS]
    assert {e["source"] for e in log} == {"what_if"} and {e["concept"] for e in log} == {"hemodinamica"}
    assert [e["confidence"] for e in log] == [80, 80, 80]
    expected = W.grade(case, {k: W.SAME for k, *_ in W.OUTPUTS})
    assert [e["correct"] for e in log] == [expected[k]["correct"] for k, *_ in W.OUTPUTS]


def test_resending_the_same_case_without_asking_for_another_is_not_logged_again():
    """Una sola vez por intento: salir del caso y volver a enviarlo no registra; «Otra predicción» abre otro intento."""
    first, second = W.CASES[0], W.CASES[1]
    at = _predict_all(_open(), W.SAME)
    assert len(at.session_state["session_learning_log"]) == 3
    at.selectbox(key="what_if_case").set_value(second.key).run()
    at.selectbox(key="what_if_case").set_value(first.key).run()
    at = _predict_all(at, W.UP)                                                 # el mismo caso, otra vez
    assert len(at.session_state["session_learning_log"]) == 3
    next(b for b in at.button if b.label == "Otra predicción").click()
    at.run()
    at = _predict_all(at, W.SAME)                                               # intento nuevo: sí cuenta
    log = at.session_state["session_learning_log"]
    assert len(log) == 6 and {e["item_id"] for e in log[3:]} == {f"what_if:{first.key}:{k}" for k, *_ in W.OUTPUTS}


# ── Procedencia y cadena del modelo, sin texto nuevo ───────────────────────────────────────────────────────────────
def test_values_carry_their_provenance_and_the_chain_is_quoted_from_the_code():
    at = _predict_all(_open(), W.SAME)
    captions = " ".join(c.value for c in at.caption)
    assert W.PROVENANCE == "calculado por el motor de lazo cerrado de BIOCORE" and W.PROVENANCE in captions
    assert "Se califica contra lo que calcula el modelo de BIOCORE, no contra un paciente real" in captions
    chain = next(e for e in at.expander if e.label == "Cómo lo calcula el modelo")
    assert W.MODEL_CHAIN in " ".join(m.value for m in chain.markdown)
    src = " ".join(Path("domain/physiology/hemodynamics/closed_loop.py").read_text(encoding="utf-8").split())
    assert W.MODEL_CHAIN in src                                                # literal del código, no texto nuevo
    assert re.search(r"Criterio BIOCORE \(HEURISTIC\)", W.NO_CHANGE_LABEL)
