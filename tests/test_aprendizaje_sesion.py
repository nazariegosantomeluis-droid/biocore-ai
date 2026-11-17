"""«Tu aprendizaje en esta sesión» (2026-11-17): aciertos por concepto, tramos de confianza, Brier y el mensaje de
calibración, con un registro sintético de la sesión. Sin respuestas, la página no muestra ningún número."""

from __future__ import annotations

import re

import pytest
from streamlit.testing.v1 import AppTest

from app.supermodules import session_learning_view as V
from app.utils import session_learning as SL

# Registro sintético (las mismas claves que escribe `log_session_answer`).
LOG = [
    {"item_id": "q1", "source": "quiz", "concept": "frecuencia_cardiaca", "correct": True, "confidence": 90},
    {"item_id": "q2", "source": "quiz", "concept": "frecuencia_cardiaca", "correct": False, "confidence": 95},
    {"item_id": "q3", "source": "detective", "concept": "news2", "correct": True, "confidence": 60},
    {"item_id": "q4", "source": "detective", "concept": "news2", "correct": True, "confidence": 55},
    {"item_id": "q5", "source": "what_if", "concept": "hrv", "correct": False, "confidence": 30},
    {"item_id": "q6", "source": "what_if", "concept": "hrv", "correct": True, "confidence": None},
    {"item_id": "q7", "source": "caso_guiado", "concept": "emg", "correct": True, "confidence": 80},
    {"item_id": "q8", "source": "caso_guiado", "concept": "emg", "correct": False, "confidence": 75},
]


def test_the_labels_cover_exactly_the_eight_concepts_of_the_contract():
    assert set(V.CONCEPT_LABELS) == set(SL.CONCEPTS) and len(SL.CONCEPTS) == 8


def test_hits_per_concept_count_answers_and_correct_ones():
    rows = {r.concept: (r.answers, r.correct) for r in V.summarize(LOG).concepts}
    assert rows == {
        "frecuencia_cardiaca": (2, 1), "ritmo_y_conduccion": (0, 0), "derivaciones_e_isquemia": (0, 0),
        "news2": (2, 2), "respiracion_y_apnea": (0, 0), "hemodinamica": (0, 0), "emg": (2, 1), "hrv": (2, 1),
    }


def test_confidence_bands_average_confidence_and_real_accuracy():
    bands = {b.label: (b.answers, b.mean_confidence, b.accuracy) for b in V.summarize(LOG).bands}
    assert bands == {
        "0–49": (1, 30.0, 0.0),
        "50–69": (2, 57.5, 1.0),
        "70–89": (2, 77.5, 0.5),
        "90–100": (2, 92.5, 0.5),
    }


def test_band_edges_are_inclusive():
    for conf, label in ((0, "0–49"), (49, "0–49"), (50, "50–69"), (69, "50–69"), (70, "70–89"), (89, "70–89"),
                        (90, "90–100"), (100, "90–100")):
        log = [{"concept": "news2", "correct": True, "confidence": conf}]
        assert {b.label: b.answers for b in V.summarize(log).bands}[label] == 1


def test_brier_score_is_the_mean_squared_gap_over_answers_with_confidence():
    expected = (0.01 + 0.9025 + 0.16 + 0.2025 + 0.09 + 0.04 + 0.5625) / 7
    summary = V.summarize(LOG)
    assert summary.confident_answers == 7
    assert summary.brier == pytest.approx(expected)
    assert V.brier_score([]) is None


def test_overconfidence_needs_five_answers_with_confidence_and_uses_the_heuristic_margin():
    summary = V.summarize(LOG)                      # 69.3 de confianza contra 57.1 % de acierto: más de 10 puntos
    assert summary.mean_confidence == pytest.approx(485 / 7)
    assert summary.accuracy_confident == pytest.approx(4 / 7)
    assert summary.calibration == "exceso"
    assert V.calibration_message(summary).startswith("Exceso de confianza")

    four = [{"concept": "news2", "correct": False, "confidence": 100}] * 4
    assert V.summarize(four).calibration is None and V.calibration_message(V.summarize(four)) is None


def test_underconfidence_and_within_margin():
    under = [{"concept": "hrv", "correct": True, "confidence": 50}] * 5
    assert V.summarize(under).calibration == "falta"
    near = [{"concept": "hrv", "correct": True, "confidence": 95}] * 5     # 95 contra 100 %: dentro del margen
    assert V.summarize(near).calibration == "dentro"


def _page_script():
    from app.supermodules.session_learning_view import render_session_learning_page

    render_session_learning_page()


def _texts(at) -> list:
    return [e.value for e in (*at.markdown, *at.caption, *at.title, *at.header, *at.subheader)]


def test_page_without_answers_shows_the_notice_and_no_numbers():
    at = AppTest.from_function(_page_script, default_timeout=30)
    at.run()
    assert not at.exception
    texts = _texts(at)
    assert any(V.PRIVACY_NOTICE in t for t in texts)
    assert any(V.EMPTY_MESSAGE in t for t in texts)
    assert not at.dataframe
    visible = [re.sub(r"<[^>]+>", "", t) for t in texts]          # los estilos HTML llevan cifras; el texto no
    assert not any(re.search(r"\d", t) for t in visible), visible


def test_page_with_a_synthetic_log_shows_hits_bands_brier_and_the_message():
    at = AppTest.from_function(_page_script, default_timeout=30)
    at.session_state[SL._KEY] = list(LOG)
    at.run()
    assert not at.exception
    concepts, bands = (df.value for df in at.dataframe)
    fc = concepts[concepts["Concepto"] == "Frecuencia cardiaca"].iloc[0]
    assert (fc["Respuestas"], fc["Aciertos"]) == ("2", "1 de 2")
    assert concepts[concepts["Concepto"] == "Hemodinámica"].iloc[0]["Aciertos"] == "Sin respuestas"
    top = bands[bands["Confianza declarada"] == "90–100"].iloc[0]
    assert (top["Respuestas"], top["Confianza promedio"], top["Acierto real"]) == ("2", "92 %", "50 %")
    texts = " ".join(_texts(at))
    assert "Puntaje de Brier de la sesión:** 0.28" in texts
    assert "Exceso de confianza" in texts and "Heurística" in texts
    assert V.PRIVACY_NOTICE in texts
