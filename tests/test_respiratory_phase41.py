"""Arco respiratorio, tanda 4.1 (cierre, 2026-11-09, Art. I).

1. Duración a nivel de muestra («Criterio BIOCORE: operacionalización de Berry a nivel de muestra»); en los eventos de
   borde gradual la UI no da un número preciso sino «≈ X s, borde gradual ± U s». U NO es un número escrito a mano: es
   cuánto cambia la duración al mover la basal ±2 %, y ese 2 % es el p95 MEDIDO del error de la basal del detector
   (esta prueba repite la medición).
2. Cheyne-Stokes: esfuerzo ausente durante TODO el evento central; 0 de 72 valles «mixta».
3. Fuera los umbrales de SpO2 sin cita («Normal 95 %», «Tiempo <90 %», «Tiempo <85 %»).
4. El texto de CPAP dice solo lo que sostiene la guía citada (Epstein 2009).
"""

import re
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from app.supermodules.respiratory_lab import views
from src.signals.respiration import RespiratoryAnalyzer, RespiratoryPattern, RespiratorySignalGenerator
from src.signals.respiration.respiratory_analyzer import DURATION_CRITERION_LABEL, HEURISTICS

FS = 100
CS_GRID = [(rr, cycle) for rr in (8, 12, 15, 30) for cycle in (45.0, 60.0, 90.0)]


def _run(pattern, rr, duration, seed=0, **kw):
    d = RespiratorySignalGenerator(FS).generate_respiration(
        duration=duration, seed=seed, params=RespiratoryPattern(respiratory_rate=rr, pattern_type=pattern, **kw))
    a = RespiratoryAnalyzer(FS).analyze_respiration(d["airflow"], d["time"], d["spo2"], d["chest_wall"])
    return d, a


def _match(a, g):
    return next((e for e in a.apnea_events if e["start_time"] < g["start_s"] + g["duration_s"] and e["end_time"] > g["start_s"]), None)


def _matched_events():
    """(anotado, detectado) de la atáxica 0.30/0.40 (120 registros cada una) y de la rejilla de Cheyne-Stokes."""
    pairs = []
    for irr in (0.30, 0.40):
        for rr in (8, 15, 30):
            for seed in range(40):
                d, a = _run("ataxic", rr, 300, seed, irregularity=irr)
                pairs += [(g, _match(a, g)) for g in d["ground_truth"]["events"] if _match(a, g)]
    for rr, cycle in CS_GRID:
        d, a = _run("cheyne_stokes", rr, 360, 0, cheyne_stokes_cycle=cycle)
        pairs += [(g, _match(a, g)) for g in d["ground_truth"]["events"] if _match(a, g)]
    return pairs


@pytest.fixture(scope="module")
def pairs():
    return _matched_events()


# ----------------------------------------------------------------------------------- decisión 1: U medida, no escrita
def test_epsilon_of_the_edge_uncertainty_is_the_measured_p95_of_the_baseline_error(pairs):
    err = np.array([abs(e["baseline"]["amplitude"] - g["baseline_amplitude"]) / g["baseline_amplitude"] for g, e in pairs])
    eps = HEURISTICS["edge_baseline_relative_error"][0]
    p95 = float(np.percentile(err, 95))
    assert len(err) >= 120
    assert 0.015 < p95 <= eps <= 1.5 * p95          # medido 1.96 % -> 2 %: ni inventado a ojo ni holgado de más
    assert np.median(err) < 0.01 and err.max() < 0.05


def test_u_covers_the_real_duration_error_of_the_gradual_edge_events_and_flat_events_stay_precise(pairs):
    bord = [(g, e) for g, e in pairs if e["borderline"]]
    flat = [(g, e) for g, e in pairs if not e["borderline"]]
    assert len(bord) >= 3 and max(e["edge_uncertainty_s"] for _, e in bord) > 1.0      # la medición no es vacía
    for g, e in bord:
        # U es la sensibilidad medida; cubre el error real de la duración (con la resolución de una muestra)
        assert abs(e["duration"] - g["duration_s"]) <= e["edge_uncertainty_s"] + 2.0 / FS
    for g, e in flat:
        assert e["edge_uncertainty_s"] <= HEURISTICS["edge_borderline_uncertainty_s"][0]
        assert abs(e["duration"] - g["duration_s"]) <= 0.5          # lo no borderline conserva la precisión de E7


def test_calendar_apneas_have_abrupt_edges_and_negligible_u():
    for pattern in ("apnea_central", "apnea_obstructive"):
        for rr in (8, 15, 30):
            _, a = _run(pattern, rr, 300)
            assert a.apnea_events and all(not e["borderline"] and e["edge_uncertainty_s"] < 0.1 for e in a.apnea_events)
            assert all(e["duration_criterion"] == DURATION_CRITERION_LABEL for e in a.apnea_events)


def test_the_duration_criterion_label_is_the_signed_one():
    assert DURATION_CRITERION_LABEL == "Criterio BIOCORE: operacionalización de Berry a nivel de muestra"


def test_duration_text_shows_the_uncertainty_only_for_gradual_edges():
    assert views.duration_text({"duration": 20.04, "borderline": False}) == "20.0 s"
    assert views.duration_text({"duration": 24.86, "borderline": True, "edge_uncertainty_s": 2.45}) == "≈ 24.9 s, borde gradual ± 2.5 s"


def _events_table_app():
    def _script():
        import streamlit as _st
        from app.supermodules.respiratory_lab import views as _v
        from src.signals.respiration import RespiratoryAnalyzer as _A, RespiratoryPattern as _P, RespiratorySignalGenerator as _G

        d = _G(100).generate_respiration(
            duration=360, seed=0, params=_P(respiratory_rate=8, pattern_type="cheyne_stokes", cheyne_stokes_cycle=90.0))
        a = _A(100).analyze_respiration(d["airflow"], d["time"], d["spo2"], d["chest_wall"])
        _v.render_apnea_cards(a)
        _v.render_events_table(a)

    return AppTest.from_function(_script, default_timeout=60).run()


def test_the_events_table_shows_borderline_durations_as_approximate_with_u():
    at = _events_table_app()
    assert at.exception == []
    rows = at.dataframe[0].value.to_dict("records")
    approx = [r["Duración"] for r in rows if r["Duración"].startswith("≈")]
    normal = [r["Duración"] for r in rows if not r["Duración"].startswith("≈")]
    assert approx and normal
    assert all(re.fullmatch(r"≈ \d+\.\d s, borde gradual ± \d+\.\d s", t) for t in approx), approx
    assert all(re.fullmatch(r"\d+\.\d s", t) for t in normal), normal
    caps = " ".join(c.value for c in at.caption)
    assert DURATION_CRITERION_LABEL in caps and "No es un número preciso" in caps
    total = " ".join(m.value for m in at.markdown if "Tiempo total de apnea" in m.value)
    assert "≈ " in total                                                  # el total también es aproximado si hay un borde gradual


def test_a_record_without_gradual_edges_shows_plain_durations(tmp_path):
    def _script():
        from app.supermodules.respiratory_lab import views as _v
        from src.signals.respiration import RespiratoryAnalyzer as _A, RespiratoryPattern as _P, RespiratorySignalGenerator as _G

        d = _G(100).generate_respiration(duration=120, seed=0, params=_P(pattern_type="apnea_central"))
        _v.render_events_table(_A(100).analyze_respiration(d["airflow"], d["time"], d["spo2"], d["chest_wall"]))

    at = AppTest.from_function(_script, default_timeout=60).run()
    rows = at.dataframe[0].value.to_dict("records")
    assert len(rows) == 2 and all(re.fullmatch(r"\d+\.\d s", r["Duración"]) for r in rows)
    assert not any("No es un número preciso" in c.value for c in at.caption)


# ----------------------------------------------------------------------------------- decisión 2: CS sin «mixta» espuria
def test_cheyne_stokes_has_zero_mixed_valleys_in_the_72_valley_grid():
    total = 0
    for rr, cycle in CS_GRID:
        d, a = _run("cheyne_stokes", rr, 360, 0, cheyne_stokes_cycle=cycle)
        assert a.apnea_count == len(d["ground_truth"]["events"]) >= 3
        for det in a.apnea_events:
            total += 1
            assert det["type"] == "central" and det["mixed_pending"] is False, (rr, cycle, det["type_detail"])
    assert total == 72


def test_the_effort_is_absent_during_the_whole_central_event_and_the_flow_is_untouched():
    for rr, cycle in CS_GRID:
        d, _ = _run("cheyne_stokes", rr, 360, 0, cheyne_stokes_cycle=cycle)
        t = d["time"]
        for e in d["ground_truth"]["events"]:
            w = (t >= e["start_s"]) & (t < e["start_s"] + e["duration_s"])
            assert np.abs(d["chest_wall"][w]).max() < 0.1 and np.abs(d["abdomen"][w]).max() < 0.1   # solo el ruido del canal
            assert "ausente en todo el evento" in e["effort"]
    # el flujo es el de siempre: sin ruido, el flujo no depende del esfuerzo (huella fijada en test_respiratory_generator_ground_truth)


# ----------------------------------------------------------------------------------- decisión 3: sin umbrales de SpO2
@pytest.fixture
def temp_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "resp_41.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente 4.1 (test)")
    return sf, pid


def _app(sf, pid, pattern=None):
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=90)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    if pattern is not None:
        at.sidebar.selectbox[0].select(pattern).run()
    return at


def _all_text(at):
    parts = []
    for tree in (at, at.sidebar):
        for coll in (tree.markdown, tree.caption, tree.info, tree.warning, tree.success, tree.error, tree.header, tree.subheader):
            parts.extend(str(e.value) for e in coll)
    return "\n".join(parts)


@pytest.mark.parametrize("pattern", [None, "Apnea Central", "Cheyne-Stokes", "Respiración Atáxica"])
def test_unsourced_spo2_thresholds_are_gone_from_the_ui(temp_ups, pattern):
    sf, pid = temp_ups
    at = _app(sf, pid, pattern)
    assert at.exception == []
    text = _all_text(at)
    for gone in ("Tiempo <90", "Tiempo <85", "Normal 95", "Hipoxemia"):
        assert gone not in text, gone
    specs = " ".join(str(c.proto.spec) for c in at.get("plotly_chart"))
    assert "Normal" not in specs and "Hipoxemia" not in specs
    assert "SpO2 Basal" in text and "SpO2 Mínimo" in text                  # lo demás de la SpO2 sigue


def test_the_analysis_no_longer_carries_the_time_below_threshold_fields():
    _, a = _run("apnea_central", 15, 120)
    assert not hasattr(a, "time_below_90") and not hasattr(a, "time_below_85")
    for path in Path("app/supermodules/respiratory_lab").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "time_below" not in src, path


# ----------------------------------------------------------------------------------- decisión 4: CPAP con su cita
def test_the_cpap_text_says_only_what_the_cited_guideline_supports(temp_ups):
    sf, pid = temp_ups
    text = " ".join(_all_text(_app(sf, pid)).split())          # los párrafos de markdown vienen partidos en líneas
    assert "CPAP" in text
    assert "Epstein LJ" in text and "J Clin Sleep Med 2009;5(3):263–276" in text
    assert "la estrategia la decide un clínico" in text and "no se deriva de la señal simulada" in text
    for claim in ("hipertensión", "accidente cerebrovascular", "infarto de miocardio", "cor pulmonale", "accidentes de tráfico",
                  "dispositivos orales", "terapia posicional", "evitar alcohol y sedantes"):
        assert claim in text, claim
    # lo que el texto anterior afirmaba y la guía NO sostiene (o sostiene de otro modo) ya no está
    for gone in ("factor de riesgo independiente", "especialmente fibrilación", "Cirugía en casos seleccionados",
                 "Cardiopatía isquémica"):
        assert gone not in text, gone
    # ninguna recomendación dirigida a quien usa el lab ni derivada de su señal
    for banned in ("debería", "se recomienda iniciar", "usa CPAP", "necesita CPAP", "indicado para ti"):
        assert banned not in text, banned
