"""«Tu aprendizaje en esta sesión» (2026-11-17): aciertos por concepto, tramos de confianza, Brier y el mensaje de
calibración, con un registro sintético de la sesión. Sin respuestas, la página no muestra ningún número.

Un solo criterio de calibración en pantalla: el veredicto (Wilson 95 %) y el Brier salen de
`educational/confidence_calibration.py`, los mismos del panel del quiz; ya no hay margen heurístico de 10 puntos."""

from __future__ import annotations

import re

import pytest
from streamlit.testing.v1 import AppTest

from app.supermodules import session_learning_view as V
from app.utils import session_learning as SL
from educational import confidence_calibration as cc

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
    assert cc.brier([]) is None
    assert not hasattr(V, "brier_score")                 # una sola fórmula de Brier: la de confidence_calibration


def test_the_verdict_is_wilsons_not_a_heuristic_margin():
    summary = V.summarize(LOG)                      # 69 % de confianza, 4 de 7: dentro del intervalo de Wilson
    assert summary.mean_confidence == pytest.approx(485 / 7)
    assert summary.accuracy_confident == pytest.approx(4 / 7)
    assert summary.calibration == cc.calibrar(LOG).total.veredicto == cc.CALIBRADA
    assert V.calibration_message(summary) == cc.frase(cc.calibrar(LOG).total)
    assert not hasattr(V, "CALIBRATION_MARGIN_PTS") and not hasattr(V, "calibration_verdict")
    assert V.summarize([{"concept": "news2", "correct": True, "confidence": None}]).calibration is None


def test_overconfidence_and_underconfidence_follow_the_wilson_interval():
    over = [{"concept": "news2", "correct": i < 3, "confidence": 100} for i in range(10)]   # 3 de 10 a 100 %
    assert V.summarize(over).calibration == cc.EXCESO
    under = [{"concept": "hrv", "correct": True, "confidence": 25}] * 10                     # 10 de 10 a 25 %
    assert V.summarize(under).calibration == cc.FALTA
    # Antes, «95 contra 100 %» con 5 respuestas era «dentro del margen»; con Wilson tampoco se detecta nada.
    near = [{"concept": "hrv", "correct": True, "confidence": 95}] * 5
    assert V.summarize(near).calibration == cc.CALIBRADA


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
    assert cc.frase(cc.calibrar(LOG).total) in texts and "Heurística" not in texts
    assert V.PRIVACY_NOTICE in texts


# Registro de 10 respuestas con confianza (exceso de confianza claro: 3 de 10 aciertos con 80–100 %).
TEN = [{"item_id": f"t{i}", "source": "quiz", "concept": "frecuencia_cardiaca", "correct": i in (0, 4, 7),
        "confidence": (100, 75, 100, 75, 100, 100, 75, 100, 75, 100)[i]} for i in range(10)]


def _quiz_panel_script():
    from app.utils.confidence import render_calibration_panel

    render_calibration_panel(expanded=True)


def test_the_same_ten_answers_give_the_same_verdict_and_brier_on_both_screens():
    expected_verdict = cc.frase(cc.calibrar(TEN).total)
    assert cc.calibrar(TEN).total.veredicto == cc.EXCESO == V.summarize(TEN).calibration
    expected_brier = f"Puntaje de Brier de la sesión:** {cc.brier(TEN):.2f}"
    assert V.summarize(TEN).brier == pytest.approx(cc.brier(TEN))

    shown = []
    for script in (_page_script, _quiz_panel_script):
        at = AppTest.from_function(script, default_timeout=30)
        at.session_state[SL._KEY] = list(TEN)
        at.run()
        assert not at.exception
        texts = " ".join(_texts(at))
        assert expected_verdict in texts and expected_brier in texts, script.__name__
        assert "Heurística" not in texts and "10 puntos" not in texts
        verdicts = [t for t in _texts(at) if t.startswith("Con 10 respuestas")]
        briers = [t for t in _texts(at) if "Puntaje de Brier de la sesión" in t]
        shown.append((verdicts, briers))
    assert shown[0] == shown[1]                           # el mismo texto en las dos pantallas
