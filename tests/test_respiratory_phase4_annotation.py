"""Arco respiratorio, fase 4 (2026-11-09, Art. I): la anotación del generador sigue la regla firmada.

Decisión 1 (firmada por Luis): irregularidad 0.20 por defecto (HEURISTIC) y el ground truth se sincroniza con los
eventos que el generador produce al azar: todo tramo que cumple el criterio (caída >= 90 % respecto a la basal de
Berry durante >= 10 s) queda anotado, origen "emergente". La anotación se calcula desde la CONSTRUCCIÓN de la señal
(la amplitud por respiración que el generador sorteó) y NUNCA con el detector (sería circular).

Decisión 7: los bordes de los eventos de Cheyne-Stokes se miden con la misma regla en la anotación y en el
detector (ver las pruebas de Cheyne-Stokes de `test_respiratory_detector_golden.py`).
"""

import ast
import inspect

import numpy as np
import pytest

from src.signals.respiration import RespiratoryAnalyzer, RespiratoryPattern, RespiratorySignalGenerator
from src.signals.respiration import respiratory_analyzer, respiratory_generator

FS = 100
TOL = 0.5  # la misma tolerancia que E7 (inicio y duración de una apnea): no se amplía para los eventos emergentes


def _record(irregularity, rr, seed, duration=300):
    d = RespiratorySignalGenerator(FS).generate_respiration(
        duration=duration, seed=seed,
        params=RespiratoryPattern(respiratory_rate=rr, pattern_type="ataxic", irregularity=irregularity))
    a = RespiratoryAnalyzer(FS).analyze_respiration(d["airflow"], d["time"], d["spo2"], d["chest_wall"])
    return d, a


def _overlaps(det, ann):
    return det["start_time"] < ann["start_s"] + ann["duration_s"] and det["end_time"] > ann["start_s"]


@pytest.mark.parametrize("irregularity", [0.20, 0.30, 0.40])
def test_decision_1_detected_events_are_the_annotated_ones_in_120_records(irregularity):
    """120 registros por irregularidad (FR 8/15/30 x 40 semillas): ni un solo evento claro sin ver, ni una sola
    'falsa apnea' (todo lo detectado está anotado) y, en lo emparejado, inicio y duración a ±0.5 s."""
    annotated = near_threshold = clear_found = false_events = 0
    records = 0
    for rr in (8, 15, 30):
        for seed in range(40):
            d, a = _record(irregularity, rr, seed)
            records += 1
            truth = d["ground_truth"]["events"]
            annotated += len(truth)
            matched = set()
            for ann in truth:
                assert ann["origin"] == "emergente" and ann["type"] == "central"
                hits = [i for i, det in enumerate(a.apnea_events) if _overlaps(det, ann)]
                if ann["near_threshold"]:
                    near_threshold += 1
                if hits:
                    det = a.apnea_events[hits[0]]
                    matched.add(hits[0])
                    assert det["start_time"] == pytest.approx(ann["start_s"], abs=TOL), (irregularity, rr, seed)
                    assert det["duration"] == pytest.approx(ann["duration_s"], abs=TOL), (irregularity, rr, seed)
                    assert det["type"] == ann["type"], (irregularity, rr, seed)
                    clear_found += not ann["near_threshold"]
                else:
                    assert ann["near_threshold"], f"evento claro sin detectar: {(irregularity, rr, seed, ann)}"
            false_events += len(a.apnea_events) - len(matched)
            if not any(e["near_threshold"] for e in truth):
                assert a.apnea_count == len(truth), (irregularity, rr, seed)   # de aquí sale la respuesta del cuestionario
    assert records == 120 and false_events == 0
    assert clear_found == annotated - near_threshold
    if irregularity == 0.20:
        assert annotated == 0          # con el valor por defecto la atáxica no produce apneas: el ground truth lo dice
    else:
        assert annotated >= 5          # con más irregularidad nacen apneas EMERGENTES y quedan anotadas


def test_default_irregularity_is_0_20_and_labelled_heuristic():
    assert RespiratoryPattern().irregularity == 0.20
    gt = RespiratorySignalGenerator(FS).generate_respiration(
        duration=60, params=RespiratoryPattern(pattern_type="ataxic"), seed=0)["ground_truth"]
    assert gt["irregularity"] == 0.20 and gt["irregularity_label"] == "HEURISTIC"


def test_emergent_events_declare_their_origin_baseline_and_margin():
    d, _ = _record(0.40, 8, 22)
    events = d["ground_truth"]["events"]
    assert events and all(e["origin"] == "emergente" for e in events)
    assert all({"baseline_amplitude", "excursion_margin", "near_threshold", "spo2_nadir_time_s"} <= set(e) for e in events)
    assert all(e["duration_s"] >= 10.0 for e in events)
    rule = d["ground_truth"]["event_rule"]
    assert rule["drop_fraction"] == 0.90 and rule["min_duration_s"] == 10.0 and "emergente" in rule["origins"]


def test_emergent_events_drive_the_spo2_like_any_other_annotated_event(monkeypatch):
    class _Null:
        def normal(self, loc=0.0, scale=1.0, size=None):
            return np.zeros(size if size is not None else ())
    d = RespiratorySignalGenerator(FS).generate_respiration(
        duration=300, seed=22, params=RespiratoryPattern(respiratory_rate=8, pattern_type="ataxic", irregularity=0.40))
    events = d["ground_truth"]["events"]
    assert events and d["spo2"].min() < 98 - 2.5            # la desaturación existe porque el evento está anotado
    clean = RespiratorySignalGenerator(FS).generate_respiration(
        duration=300, seed=22, params=RespiratoryPattern(respiratory_rate=8, pattern_type="ataxic", irregularity=0.0))
    assert clean["ground_truth"]["events"] == [] and clean["spo2"].min() > 98 - 2.5


def test_the_annotation_is_computed_from_the_construction_and_never_with_the_detector():
    """Anti-circularidad: el generador no importa nada del analizador."""
    tree = ast.parse(inspect.getsource(respiratory_generator))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported += [n.name for n in node.names]
    assert not any("analyzer" in m for m in imported), imported
    assert "RespiratoryAnalyzer" not in inspect.getsource(respiratory_generator.RespiratorySignalGenerator)


def test_generator_and_detector_share_the_signed_criteria_but_not_the_code():
    assert respiratory_generator.APNEA_DROP_FRACTION == respiratory_analyzer.APNEA_DROP_FRACTION == 0.90
    assert respiratory_generator.APNEA_MIN_DURATION_S == respiratory_analyzer.APNEA_MIN_DURATION_S == 10.0
    assert respiratory_generator.BASELINE_WINDOW_S == respiratory_analyzer.BASELINE_WINDOW_S == 120.0
    assert respiratory_generator.STABLE_BREATHS_TO_AVERAGE == respiratory_analyzer.STABLE_BREATHS_TO_AVERAGE == 3
    assert respiratory_generator.BASELINE_STABILITY_CV == respiratory_analyzer.HEURISTICS["baseline_stability_cv"][0] == 0.30


@pytest.mark.parametrize("pattern", ["apnea_central", "apnea_obstructive"])
def test_calendar_patterns_keep_their_annotation_and_are_marked_as_calendar(pattern):
    d = RespiratorySignalGenerator(FS).generate_respiration(
        duration=120, params=RespiratoryPattern(pattern_type=pattern), seed=0)
    events = d["ground_truth"]["events"]
    assert [(e["start_s"], e["duration_s"]) for e in events] == [(40.0, 20.0), (100.0, 20.0)]
    assert all(e["origin"] == "calendario" for e in events)


def test_cheyne_stokes_event_at_the_start_without_baseline_is_not_evaluable_and_not_annotated():
    d = RespiratorySignalGenerator(FS).generate_respiration(
        duration=120, params=RespiratoryPattern(pattern_type="cheyne_stokes"), seed=0)
    gt = d["ground_truth"]
    assert all(e["start_s"] > 0 for e in gt["events"])
    assert isinstance(gt["non_evaluable_events"], list)
