"""Integración tanda 2 + main (Miguel), PARTE B (2026-11-16): contención antes de la prueba con estudiantes.

- ECG-12: ninguna indicación de tratamiento en la lectura de ningún escenario (Miguel retiró las «recomendaciones» del
  analizador viejo; esta guardia impide que vuelvan).
- Caso clínico del gemelo: funciona SIN clave de IA; la corrección es determinista (escenario cargado + evidencia con
  fuente); la IA solo añade una narración opcional y rotulada.
"""

import re

import pytest
from streamlit.testing.v1 import AppTest

from src.signals.ecg.twelve_lead_synth import SCENARIOS

# Indicaciones de tratamiento o de conducta que aparecían en el analizador viejo («Activar protocolo STEMI», «iniciar
# aspirina, heparina»...) y en otros textos del repositorio sin cita (barrido del 2026-11-16).
TREATMENT = re.compile(
    r"aspirina|heparina|atropina|adenosina|cardiovers|trombol|fibrinol|anticoagul|betabloq|amiodaron|reperfusi|"
    r"cateterismo|angioplast|\bICP\b|\bPCI\b|desfibril|recomendaci|acci[oó]n cl[ií]nica|"
    r"iniciar (?:manejo|tratamiento)|activar protocolo|derivaci[oó]n cardiol|considere|considerar",
    re.IGNORECASE,
)


def _report_texts(at):
    out = [m.value for m in at.markdown] + [c.value for c in at.caption]
    out += [x.value for kind in ("info", "warning", "error", "success") for x in getattr(at, kind)]
    out += [e.label for e in at.expander]
    return " ".join(out)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_twelve_lead_reading_never_indicates_a_treatment(scenario):
    def _script(scenario):
        from app.supermodules.ecg_12.report_view import render_twelve_lead_report
        from src.signals.ecg.twelve_lead_measure import analyze_twelve_lead
        from src.signals.ecg.twelve_lead_synth import generate_twelve_lead

        leads, truth = generate_twelve_lead(scenario, 75.0)
        render_twelve_lead_report(analyze_twelve_lead(leads), truth)

    at = AppTest.from_function(_script, args=(scenario,), default_timeout=120).run()
    assert not at.exception, at.exception
    hits = TREATMENT.findall(_report_texts(at))
    assert hits == [], (scenario, hits)


def test_the_treatment_guard_catches_what_the_old_analyzer_said():
    for old in ("Activar protocolo STEMI y priorizar reperfusión inmediata.",
                "Evaluar control de frecuencia y considerar anticoagulación según CHA2DS2-VASc.",
                "Iniciar manejo urgente de taquiarritmia ventricular", "Recomendaciones Clínicas"):
        assert TREATMENT.search(old), old


# ------------------------------------------------------------------------------- caso clínico del gemelo sin IA
@pytest.fixture
def case_without_ai(tmp_path, monkeypatch):
    """El caso clínico del gemelo con una base temporal, sin ninguna clave de IA y con el narrador vigilado."""
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory
    import app.supermodules.twin_shell.pages as twin

    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    def _no_ai(*a, **k):
        raise AssertionError("la corrección no debe llamar a ningún modelo de lenguaje")

    monkeypatch.setattr(twin, "stream_findings_narration", _no_ai)
    engine = make_engine(tmp_path / "caso.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="caso sin IA")

    def _script():
        from app.engines.digital_twin_organism import DigitalTwinOrganism
        from app.supermodules.twin_shell.pages import render_clinical_case_mode

        render_clinical_case_mode(DigitalTwinOrganism(), expanded=True)

    at = AppTest.from_function(_script, default_timeout=180)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    assert at.exception == [], at.exception
    next(b for b in at.button if b.key == "clinical_case_new").click().run()
    assert at.exception == [], at.exception
    return at


def _answer(at, pick):
    hidden = at.session_state["clinical_case_hidden_scenario"]
    options = at.session_state["clinical_case_options"]
    choice = hidden if pick == "correct" else next(o for o in options if o != hidden)
    from app.supermodules.twin_shell.pages import RICH_SCENARIO_LABELS

    next(r for r in at.radio if r.label == "¿Cuál es tu diagnóstico?").set_value(RICH_SCENARIO_LABELS[choice]).run()
    next(b for b in at.button if b.key.startswith("clinical_case_confirm_")).click().run()
    assert at.exception == [], at.exception
    return hidden, choice, RICH_SCENARIO_LABELS


def test_the_twin_case_is_corrected_without_an_ai_key_when_right(case_without_ai):
    at = case_without_ai
    assert not any(w.value.startswith("La IA está apagada") for w in at.warning)      # ya no bloquea el caso
    hidden, _, labels = _answer(at, "correct")
    assert [s.value for s in at.success] == [f"¡Correcto! El caso era: {labels[hidden]}"]    # el ✅ va de ícono
    text = " ".join(m.value for m in at.markdown)
    assert "Qué mostró el caso, con su criterio citado:" in text
    from clinical.calculators import NEWS2_CITATION

    assert any(NEWS2_CITATION in c.value for c in at.caption)
    assert "Narración con IA (opcional; no es la corrección):" in text
    assert not any(b.key.startswith("clinical_case_narrate_") for b in at.button)    # sin clave, ni el botón
    assert at.error == []


def test_the_twin_case_is_corrected_without_an_ai_key_when_wrong(case_without_ai):
    at = case_without_ai
    hidden, choice, labels = _answer(at, "wrong")
    assert [e.value for e in at.error] == [f"Elegiste {labels[choice]} — el caso real era {labels[hidden]}"]
    assert any(m.value.startswith("- ") for m in at.markdown)                         # la evidencia del caso


def test_case_evidence_uses_only_cited_criteria():
    from datetime import datetime, timezone

    from domain.physiology.state import DomainState, Provenance, UnifiedPhysiologicalState
    from domain.physiology.state.schema import PhysiologicalDescriptor
    from app.supermodules.twin_shell.pages import case_evidence

    cv = DomainState(domain="cardiovascular")
    for name, value, unit in (("heart_rate", 145.0, "lpm"), ("news2_pulse_points", 3.0, "puntos NEWS2 (0-3)")):
        cv.descriptors[name] = PhysiologicalDescriptor(name=name, value=value, unit=unit,
                                                       provenance=Provenance.SIMULACION, confidence=0.5)
    state = UnifiedPhysiologicalState(patient_id="p", timestamp=datetime.now(timezone.utc), cardiovascular=cv,
                                      respiratory=DomainState(domain="respiratory"))
    assert case_evidence(state, []) == ["Pulso: 145 lpm → 3 puntos NEWS2"]
    empty = UnifiedPhysiologicalState(patient_id="p", timestamp=datetime.now(timezone.utc),
                                      cardiovascular=DomainState(domain="cardiovascular"),
                                      respiratory=DomainState(domain="respiratory"))
    assert case_evidence(empty, []) == ["El caso no trae valores con un criterio citado con qué compararlos."]
