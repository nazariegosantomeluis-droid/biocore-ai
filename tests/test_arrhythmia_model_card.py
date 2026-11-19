"""Tarjeta del modelo del clasificador de arritmias (2026-11-17, Art. I).

El panel de «Cómo se calcula» del ECG muestra EXACTAMENTE las cifras de results.json (golden test), la
evaluación usa registros que el modelo no vio y se predice con los mismos nombres de columna del ajuste.
"""

import importlib
import json
import warnings
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from domain.physiology.ml import arrhythmia_evaluation as ae

RESULTS = json.loads(ae.RESULTS_PATH.read_text(encoding="utf-8"))


def _fmt(v):
    return "no disponible" if v is None else f"{v:.3f}"


def _card_script():
    from app.main import render_arrhythmia_model_card

    render_arrhythmia_model_card()


def _card_missing_script():
    from app.main import render_arrhythmia_model_card

    render_arrhythmia_model_card("no/existe/results.json")


def _texts(at):
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption] + [w.value for w in at.warning])


def test_the_panel_shows_exactly_the_numbers_of_results_json():
    at = AppTest.from_function(_card_script).run(timeout=60)
    assert not at.exception
    table = at.dataframe[0].value
    ev = RESULTS["evaluacion_entre_pacientes"]
    assert list(table["Clase AAMI"].str[0]) == list(ev["por_clase"])
    for row, (cls, m) in zip(table.to_dict("records"), ev["por_clase"].items()):
        assert row["Latidos en evaluación"] == str(m["latidos"])
        assert row["Sensibilidad"] == _fmt(m["sensibilidad"])
        assert row["Valor predictivo positivo"] == _fmt(m["valor_predictivo_positivo"])
        assert row["F1"] == _fmt(m["f1"])
    text = _texts(at)
    for v in (ev["f1_macro"], ev["exactitud"], ev["brier"],
              RESULTS["fuga_por_latido"]["exactitud"], RESULTS["fuga_por_latido"]["f1_macro"]):
        assert _fmt(v) in text
    assert "No apto para diagnóstico" in text
    # Tanda de heurísticas (2026-11-19): sin el juicio del corte de 0.80 (sin cita); la sensibilidad queda en la tabla.
    assert "En evaluación" not in text and "Criterio BIOCORE" not in text
    assert len(at.get("image")) == 2


def test_without_results_the_panel_says_not_available_and_does_not_fail():
    at = AppTest.from_function(_card_missing_script).run(timeout=60)
    assert not at.exception
    assert "Sin dato" in " ".join(m.value for m in at.markdown)
    assert not at.dataframe


def test_evaluation_records_are_not_in_the_training_records():
    d = RESULTS["datos"]
    train, test = set(d["registros_entrenamiento"]), set(d["registros_evaluacion"])
    assert train and test and not train & test
    assert train == set(ae.DS1) and test == set(ae.DS2)
    assert len(train) == len(test) == 22
    assert not (train | test) & set(ae.EXCLUDED_PACED)


def test_results_declare_date_version_and_beats_used():
    assert RESULTS["fecha"] and RESULTS["modelo"]["version"] == ae.MODEL_VERSION
    ev = RESULTS["evaluacion_entre_pacientes"]
    assert sum(sum(r) for r in ev["matriz_confusion"]) == sum(RESULTS["datos"]["latidos_evaluacion"].values())
    for name in ("confusion_matrix.png", "reliability_curve.png", "MODEL_CARD.md"):
        assert (ae.RESULTS_DIR / name).exists(), name


def test_class_metrics_and_brier_on_a_known_case():
    y = np.array(["N", "N", "V", "S"])
    p = np.array(["N", "V", "V", "N"])
    cm, per, macro, acc = ae.class_metrics(y, p)
    assert per["N"]["sensibilidad"] == 0.5 and per["V"]["valor_predictivo_positivo"] == 0.5
    assert per["S"]["sensibilidad"] == 0.0 and per["F"]["latidos"] == 0 and per["F"]["f1"] is None
    assert acc == 0.5 and macro == pytest.approx(np.mean([0.5, 2 / 3, 0.0]))
    onehot = (y[:, None] == np.array(ae.CLASSES)[None, :]).astype(float)
    assert ae.brier_multiclass(y, onehot) == 0.0
    worst = np.roll(onehot, 1, axis=1)          # toda la probabilidad en una clase equivocada
    assert ae.brier_multiclass(y, worst) == pytest.approx(2.0)


def test_prediction_uses_the_same_column_names_without_warning():
    pytest.importorskip("lightgbm")
    rng = np.random.default_rng(0)
    segs = [rng.normal(size=252) * (1 + (i % 2)) for i in range(60)]
    labels = np.array(["N" if i % 2 == 0 else "V" for i in range(60)])
    X = ae.features_frame(segs)
    assert list(X.columns) == list(ae.FEATURE_NAMES)
    model = ae._model().fit(X, labels)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        model.predict(ae.features_frame(segs))
        model.predict_proba(ae.features_frame(segs))


def test_cache_dir_comes_from_the_variable_or_defaults_inside_the_repo(monkeypatch, tmp_path):
    try:
        monkeypatch.setenv("BIOCORE_CACHE_DIR", str(tmp_path))
        importlib.reload(ae)
        assert ae.CACHE_DIR == tmp_path
        monkeypatch.delenv("BIOCORE_CACHE_DIR")
        importlib.reload(ae)
        assert ae.CACHE_DIR == Path(__file__).resolve().parents[1] / ".cache" / "biocore"
    finally:
        monkeypatch.undo()          # el entorno original, y el modulo recargado con el
        importlib.reload(ae)


def test_no_personal_paths_in_the_card_results_or_code():
    for path in (ae.RESULTS_DIR / "MODEL_CARD.md", ae.RESULTS_PATH, Path(ae.__file__)):
        text = path.read_text(encoding="utf-8")
        assert "C:/Users" not in text and "luisn" not in text, path
