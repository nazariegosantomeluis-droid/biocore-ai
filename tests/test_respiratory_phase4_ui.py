"""Arco respiratorio, fase 4 (2026-11-09, Art. I): decisiones 2-6 y «Guardar al gemelo» con procedencia.

Todo contra una base temporal (la de desarrollo no se toca). Las pruebas puras de texto no necesitan Streamlit.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy import text as sql
from streamlit.testing.v1 import AppTest

from src.signals.respiration import RespiratoryAnalyzer, RespiratoryPattern, RespiratorySignalGenerator
from app.supermodules.respiratory_lab import views

FS = 100


@pytest.fixture
def temp_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "resp_ui4.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente UI fase 4 (test)")
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


def _text(at):
    parts = []
    for tree in (at, at.sidebar):
        for coll in (tree.markdown, tree.caption, tree.info, tree.warning, tree.success, tree.error, tree.header, tree.subheader):
            parts.extend(str(e.value) for e in coll)
    parts.extend(b.label for b in at.button)
    return "\n".join(parts)


def _card(at, label):
    return " ".join(m.value for m in at.markdown if f"<strong>{label}</strong>" in m.value)


def _analysis(pattern, rr=15, duration=120, seed=0, **kw):
    d = RespiratorySignalGenerator(FS).generate_respiration(
        duration=duration, seed=seed, params=RespiratoryPattern(respiratory_rate=rr, pattern_type=pattern, **kw))
    a = RespiratoryAnalyzer(FS).analyze_respiration(d["airflow"], d["time"], d["spo2"], d["chest_wall"])
    return d, a


# ------------------------------------------------------------------------------- decisión 2: patrón (HEURISTIC)
def _fake(cv=None, period=None):
    cycle = 4.0
    return SimpleNamespace(rr_variability=None if cv is None else cv * cycle, cycle_duration_s=None if cv is None else cycle,
                           event_period_s=period)


@pytest.mark.parametrize("cv,head", [
    (0.00, "Intervalos entre respiraciones regulares (variación del 0 %)"),
    (0.05, "Intervalos entre respiraciones regulares (variación del 5 %)"),
    (0.0999, "Intervalos entre respiraciones regulares (variación del 10 %)"),   # CV < 10 % → regular, aunque el redondeo diga 10
    (0.10, "Intervalos entre respiraciones variables (variación del 10 %)"),
    (0.25, "Intervalos entre respiraciones variables (variación del 25 %)"),
])
def test_pattern_regular_below_10_percent_variable_from_10_percent(cv, head):
    out = views.pattern_description(_fake(cv))
    assert out.startswith(head) and out.endswith("Describe la señal; no es un diagnóstico.")
    assert "Eventos repetidos" not in out


def test_pattern_mentions_repeated_events_and_always_says_it_is_not_a_diagnosis():
    out = views.pattern_description(_fake(0.03, period=60.2))
    assert "Eventos repetidos cada ~60 s" in out and "no es un diagnóstico" in out
    assert "no disponibles" in views.pattern_description(_fake(None))               # sin FR: lo dice, no inventa un CV


def test_cheyne_stokes_notice_appears_with_repeated_events_or_the_simulated_pattern():
    _, normal = _analysis("normal")
    _, periodic = _analysis("apnea_central")
    assert views.cheyne_stokes_notice(normal) is None
    assert "Berry 2012" in views.cheyne_stokes_notice(periodic) and "2 horas" in views.cheyne_stokes_notice(periodic)
    assert views.cheyne_stokes_notice(normal, "cheyne_stokes") is not None


# ------------------------------------------------------------------------------- decisión 2: notas clínicas
def test_notes_for_a_normal_record():
    _, a = _analysis("normal")
    notes = views.clinical_notes(a, 15.0)
    assert notes[0] == "FR 15/min: dentro de 12–20 (NEWS2)"
    assert notes[1] == "No se detectaron apneas en este registro; no descarta apneas en otros"
    assert len(notes) == 2                                                          # sin desaturación: no hay nota de SpO2


@pytest.mark.parametrize("rr,expected", [
    (30, "FR 30/min: fuera de 12–20 (NEWS2): 3 punto(s)"),
    (8, "FR 8/min: fuera de 12–20 (NEWS2): 3 punto(s)"),
])
def test_notes_for_a_rate_outside_the_news2_band(rr, expected):
    _, a = _analysis("normal", rr)
    assert views.clinical_notes(a)[0] == expected


def test_notes_for_apneas_and_the_simulated_desaturation():
    _, a = _analysis("apnea_central", 15, 200)
    notes = views.clinical_notes(a, 15.0)
    assert notes[0] == "FR 15/min: dentro de 12–20 (NEWS2)"
    assert re.fullmatch(r"3 apnea\(s\) de ≥10 s en 200 s de registro; tasa equivalente 54/h de registro "
                        r"\(extrapolada, sin valor diagnóstico\)", notes[1]), notes[1]
    assert re.fullmatch(r"Desaturación simulada: nadir \d+\.\d % a los \d+ s \(modelo BIOCORE\)", notes[2]), notes[2]


def test_a_nadir_outside_the_record_is_declared_partial():
    _, a = _analysis("apnea_central", 15, 120)                 # el 2.º evento termina en 120 s: su nadir (135 s) queda fuera
    assert views.nadir_outside_record(a, 15.0) is True
    assert views.nadir_outside_record(a, None) is False        # sin Tc no se afirma nada
    assert views.nadir_outside_record(a, 0.0) is False         # con retardo 0 el nadir de ambos eventos cae dentro
    assert any(n.endswith("nadir fuera del registro; el valor mostrado es parcial") for n in views.clinical_notes(a, 15.0))
    _, long = _analysis("apnea_central", 15, 200)
    assert not any("fuera del registro" in n for n in views.clinical_notes(long, 15.0)[:3]) or views.nadir_outside_record(long, 15.0)


def test_notes_never_derive_treat_or_label_a_disease():
    for pattern in ("normal", "apnea_central", "apnea_obstructive", "cheyne_stokes", "ataxic", "tachypnea", "bradypnea"):
        _, a = _analysis(pattern, 15, 200)
        blob = " ".join(views.clinical_notes(a, 15.0) + [views.pattern_description(a)]).lower()
        for banned in ("cpap", "caracter", "deriv", "remit", "polisomno", "diagnóstico de", "sospecha", "tratamiento", "ahi", "odi"):
            if banned == "diagnóstico de":
                assert "diagnóstico de" not in blob
            else:
                assert banned not in blob.replace("no es un diagnóstico", ""), (pattern, banned)


def test_notes_without_a_rate_say_so_and_do_not_invent_one():
    a = SimpleNamespace(respiratory_rate_rounded=None, signal_status_detail="se detectaron 2 respiraciones", apnea_count=None,
                        baseline_spo2=98.0, minimum_spo2=97.0, spo2_nadir_time=3.0, apnea_events=[], record_duration_s=30.0)
    notes = views.clinical_notes(a)
    assert notes[0].startswith("FR no disponible: se detectaron 2 respiraciones") and "no evaluables" in notes[1]


# ------------------------------------------------------------------------------ decisiones 5 y 6: gráficos
def test_the_spo2_chart_has_no_unsourced_hypoxemia_lines_and_the_flow_axis_is_relative(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    assert at.exception == []
    specs = " ".join(str(c.proto.spec) for c in at.get("plotly_chart"))
    assert "Hipoxemia leve" not in specs and "Hipoxemia grave" not in specs
    assert "Normal" in specs                                                            # la línea de 95 % se conserva
    assert "unidades relativas: la escala absoluta no corresponde al volumen corriente elegido" in specs
    assert "L/min" not in specs
    for path in Path("app/supermodules/respiratory_lab").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "Hipoxemia leve" not in src and "Hipoxemia grave" not in src, path


# ------------------------------------------------------------------------------------- insignias por valor
def test_each_value_carries_its_own_badge_and_there_is_no_global_one(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    assert "🟢" in _card(at, "Banda NEWS2 de la FR")                                    # validado por fuente
    assert "🟢" in _card(at, "Apneas (≥ 10 s, caída ≥ 90 %)") and "Berry" in _card(at, "Apneas (≥ 10 s, caída ≥ 90 %)")
    assert "🟣" in _card(at, "Frecuencia Respiratoria")
    assert "🟣" in _card(at, "Tasa equivalente por hora de registro (extrapolada, sin valor diagnóstico)")
    assert "🟣" in _card(at, "SpO2 Basal") and "Howarth 2026" in _card(at, "SpO2 Basal")
    assert any("🟣" in c.value and "Tc" in c.value and "Valor BIOCORE" in c.value for c in at.sidebar.caption)
    assert "🔵" in _card(at, "Patrón (descripción de la señal)")
    assert "Insignias por valor" in _text(at) and "⏳" in _text(at)                       # la leyenda nombra el pendiente
    assert [m for m in at.main.markdown if "border-left:3px" in m.value] == []          # ni insignia global del módulo


def test_the_irregularity_is_shown_as_heuristic_only_for_the_ataxic_pattern(temp_ups):
    sf, pid = temp_ups
    ataxic = _app(sf, pid, "Respiración Atáxica")
    card = _card(ataxic, "Irregularidad pedida al generador (CV de duración y profundidad por respiración)")
    assert "0.20" in card and "🔵" in card
    assert _card(_app(sf, pid), "Irregularidad pedida al generador (CV de duración y profundidad por respiración)") == ""


def test_a_mixed_apnea_is_marked_pending_with_its_own_badge():
    def _script():
        import numpy as _np
        import streamlit as _st
        from app.supermodules.respiratory_lab import views as _v
        from src.signals.respiration import RespiratoryAnalyzer as _A

        t = _np.arange(12000) / 100.0
        cyc = 4.0
        ph = _np.mod(t / cyc, 1.0)
        x = _np.where(ph < 0.25, _np.sin(_np.pi * ph / 0.25), -0.5 * _np.sin(_np.pi * (ph - 0.25) / 0.75)) * 7.5
        chest = _np.sin(2 * _np.pi * t / cyc) * 0.5
        gap = (t >= 40) & (t < 60)
        x[gap] = 0.0
        chest[(t >= 50) & (t < 60)] = 0.0                                 # el esfuerzo cae a la mitad del evento
        rng = _np.random.default_rng(0)
        a = _A(100).analyze_respiration(x + rng.normal(0, 0.02, len(t)), t, _np.full_like(t, 98.0), chest + rng.normal(0, 0.01, len(t)))
        _v.render_events_table(a)

    at = AppTest.from_function(_script, default_timeout=60).run()
    assert at.exception == []
    row = at.dataframe[0].value.to_dict("records")[0]
    assert row["Tipo (Criterio BIOCORE)"] == "⏳ mixta (PENDING_VALIDATION)"
    assert any("⏳ Mixta: PENDING_VALIDATION" in c.value for c in at.caption)


def test_the_status_notice_replaces_the_in_correction_notice_and_names_the_badges(temp_ups):
    sf, pid = temp_ups
    notice = " ".join(i.value for i in _app(sf, pid).info)
    for token in ("Validado por fuente 🟢", "Con golden test, metodología propia 🟣", "Heurística 🔵",
                  "Pendiente de validación ⏳", "Sigue fuera"):
        assert token in notice, token


# -------------------------------------------------------------------------------------- Guardar al gemelo
def _snapshot_rows(sf):
    with sf() as s:
        snaps = s.execute(sql("select id from ups_snapshots")).fetchall()
        values = s.execute(sql("select domain, descriptor, value, unit, provenance, source_detail from ups_values")).fetchall()
        events = s.execute(sql("select event_type, domain from ups_events")).fetchall()
    return snaps, values, events


def test_save_to_twin_writes_only_fr_and_baseline_spo2_with_simulation_provenance(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Central")
    analysis = at.session_state["_respiratory_lab_analysis"]["analysis"]
    assert _snapshot_rows(sf)[0] == []                                                  # antes de pulsar: nada
    next(b for b in at.button if "Guardar FR y SpO₂ basal" in b.label).click().run()
    assert at.exception == []
    snaps, values, events = _snapshot_rows(sf)
    assert len(snaps) == 1
    assert {(v[0], v[1]) for v in values} == {("respiratory", "respiratory_rate"), ("respiratory", "spo2")}   # solo 2; ningún derivado
    by = {v[1]: v for v in values}
    assert by["respiratory_rate"][2] == pytest.approx(analysis.respiratory_rate) and by["respiratory_rate"][3] == "resp/min"
    assert by["spo2"][2] == pytest.approx(analysis.baseline_spo2) and by["spo2"][3] == "%"
    assert by["spo2"][2] != pytest.approx(analysis.minimum_spo2)                        # la basal, no el nadir
    from domain.physiology.state import Provenance
    assert all(v[4] == Provenance.SIMULACION.value for v in values)
    assert "60/media de los intervalos" in by["respiratory_rate"][5] and "no el nadir" in by["spo2"][5]
    assert "patron=Apnea Central" in by["spo2"][5]
    assert "ahi" not in {v[1] for v in values} and "apnea_risk" not in {v[1] for v in values}
    assert [e for e in events if e[1] != "respiratory"] == []                            # ni un evento de otro dominio
    assert "Estado guardado al gemelo" in " ".join(s.value for s in at.success)


def test_saved_state_passes_the_phantom_organ_gates_and_triggers_no_coupling_or_composition(temp_ups):
    from domain.physiology.coupling import VALIDATED_RULES, apply_couplings
    from domain.physiology.state import get_latest_state
    from domain.physiology.state.composer import compose_neuro_cardiac_snapshot

    sf, pid = temp_ups
    at = _app(sf, pid, "Apnea Obstructiva")
    next(b for b in at.button if "Guardar FR y SpO₂ basal" in b.label).click().run()
    with sf() as s:
        state = get_latest_state(s, pid)
        assert state.cardiovascular.descriptors == {} and state.neurological.descriptors == {} and state.muscular.descriptors == {}
        assert set(state.respiratory.descriptors) == {"respiratory_rate", "spo2"}
        assert apply_couplings(s, s.execute(sql("select id from ups_snapshots")).scalar_one(), VALIDATED_RULES, scenario=None) == []
        before = s.execute(sql("select count(*) from ups_snapshots")).scalar_one()
        composed = compose_neuro_cardiac_snapshot(s, pid)
        assert composed.available is False                                              # falta el EEG real y el pulso: no compone
        assert s.execute(sql("select count(*) from ups_snapshots")).scalar_one() == before


def test_saving_twice_appends_a_second_snapshot_and_never_overwrites(temp_ups):
    sf, pid = temp_ups
    at = _app(sf, pid)
    btn = lambda: next(b for b in at.button if "Guardar FR y SpO₂ basal" in b.label)  # noqa: E731
    btn().click().run()
    btn().click().run()
    assert len(_snapshot_rows(sf)[0]) == 2


def test_the_save_explains_what_it_does_not_write(temp_ups):
    sf, pid = temp_ups
    text = _text(_app(sf, pid))
    assert "Escribe **solo dos valores**" in text or "Escribe solo dos valores" in text.replace("**", "")
    assert "No escribe" in text.replace("**", "") and "tasa por hora de registro" in text


def test_the_save_is_unavailable_without_a_rate_and_never_writes_a_default():
    def _script():
        import numpy as _np
        import streamlit as _st
        from app.supermodules.respiratory_lab import views as _v
        from src.signals.respiration import RespiratoryAnalyzer as _A

        t = _np.arange(3000) / 100.0
        a = _A(100).analyze_respiration(_np.zeros_like(t), t, _np.full_like(t, 98.0), None)
        _v.render_save_to_twin(a, "plana", key="k")

    at = AppTest.from_function(_script, default_timeout=60).run()
    assert at.exception == [] and not at.button
    assert any("Desactivado" in w.value and "no se guarda un valor por defecto" in w.value for w in at.warning)


def test_build_twin_state_refuses_a_missing_rate():
    a = SimpleNamespace(respiratory_rate=None, baseline_spo2=98.0)
    with pytest.raises(ValueError, match="no hay nada que guardar"):
        views.build_twin_state(a, "p", "x")


def test_the_flow_axis_stays_relative_while_the_integrated_volume_is_not_the_tidal_volume():
    """Decisión 6: la etiqueta «unidades relativas» se puede retirar SOLO cuando el volumen inspirado integrado por
    respiración coincida con el volumen corriente elegido. Esta prueba falla el día que eso ocurra, para recordarlo."""
    for tv in (0.3, 0.5, 1.0):
        d = RespiratorySignalGenerator(FS).generate_respiration(
            duration=60, seed=0, params=RespiratoryPattern(respiratory_rate=15, tidal_volume=tv, pattern_type="normal"))
        inspired_l = np.sum(np.clip(d["airflow"], 0, None)) / FS / 60.0 / (60 * 15 / 60.0)   # L/min → L/s; por respiración
        assert abs(inspired_l - tv) > 0.1 * tv, (tv, inspired_l)
