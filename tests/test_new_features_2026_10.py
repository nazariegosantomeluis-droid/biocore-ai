"""Tanda 2026-10-19: Calculadoras Clínicas, Academia sin clave de IA,
Modo Rural, HRV desde archivo + Poincaré, organ grid alineado."""
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MAIN = str(Path(__file__).resolve().parents[1] / "app" / "main.py")


_TMP_SF = {}


@pytest.fixture(autouse=True)
def _isolated_ups(tmp_path):
    """BD temporal del UPS para cada prueba -- nunca tocar data/biocore_ups.db
    (mismo patrón que tests/test_hygiene_short_signal_and_ghosts.py)."""
    from domain.physiology.state import init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "ups_test.db")))
    init_db(engine)
    _TMP_SF["sf"] = make_session_factory(engine)
    yield
    engine.dispose()
    _TMP_SF.clear()


def _app(hub, page, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(MAIN, default_timeout=180)
    at.session_state["selected_hub"] = hub
    at.session_state["selected_page"] = page
    at.session_state["twin_shell_ups_session_factory"] = _TMP_SF["sf"]
    at.session_state["academia_case_session_factory"] = _TMP_SF["sf"]
    return at


# ─── Calculadoras Clínicas ───────────────────────────────────────────────

def test_calculators_page_renders_every_tab(monkeypatch):
    at = _app("Clinical Hub", "🧮 Calculadoras Clínicas", monkeypatch)
    at.run()
    assert not at.exception
    from app.supermodules.calculators.pages import CALC_TABS
    # Rediseño visual (2026-10-19): íconos Material en vez de emoji.
    assert [t.label for t in at.tabs][:6] == CALC_TABS
    assert [label.split(": ", 1)[1] for label in CALC_TABS] == [
        "ECG", "Hemodinamia", "Oxigenación", "Antropometría", "Escalas", "Informe"]
    html = " ".join(m.value for m in at.markdown)
    for label in ("QTc Bazett", "Eje del QRS", "PAM", "Índice de choque", "Índice cardiaco", "PAO₂ (alveolar)",
                  "PaO₂/FiO₂", "IMC", "ASC (Mosteller)", "NEWS2", "qSOFA", "Glasgow"):
        assert f"<strong>{label}</strong>" in html, label


def test_calculators_import_vitals_from_the_digital_twin(monkeypatch):
    at = _app("Digital Twin OS", "🧬 Digital Twin OS", monkeypatch)
    at.run()
    organism = at.session_state["twin_shell_organism"]
    twin_hr = organism.organs["heart"].metrics.signals["heart_rate"]
    twin_rr = organism.organs["lungs"].metrics.signals["respiratory_rate"]

    at.session_state["selected_hub"] = "Clinical Hub"
    at.session_state["selected_page"] = "🧮 Calculadoras Clínicas"
    at.run()
    assert not at.exception
    button = next(b for b in at.button if b.key == "calc_use_twin")
    button.click().run()
    assert not at.exception
    assert at.session_state["calc_news_pulse"] == pytest.approx(round(twin_hr))
    assert at.session_state["calc_qsofa_rr"] == pytest.approx(round(twin_rr))
    assert any("simulación" in m.value.lower() for m in list(at.markdown) + list(at.caption))


def test_calculators_report_is_generated(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # export_lab_report escribe en ./reports
    at = _app("Clinical Hub", "🧮 Calculadoras Clínicas", monkeypatch)
    at.run()
    next(b for b in at.button if b.key == "calc_report_build").click().run()
    assert not at.exception
    path = at.session_state["calc_report_path"]
    assert path.endswith((".pdf", ".html")) and (tmp_path / path).exists()


def test_invalid_blood_pressure_shows_error_and_leaves_report(monkeypatch):
    at = _app("Clinical Hub", "🧮 Calculadoras Clínicas", monkeypatch)
    at.run()
    assert "map" in at.session_state["calc_report_cards"]
    at.number_input(key="calc_hemo_dbp").set_value(150.0)
    at.number_input(key="calc_hemo_sbp").set_value(110.0)
    at.run()
    assert not at.exception
    assert "map" not in at.session_state["calc_report_cards"]
    assert any("diastólica debe ser menor" in m.value for m in at.markdown)


# ─── Academia sin ANTHROPIC_API_KEY ──────────────────────────────────────

def test_academia_lessons_module_is_available():
    from app.supermodules.academia import pages
    assert pages.LESSONS_AVAILABLE


def test_quiz_is_gradable_without_api_key(monkeypatch):
    at = _app("Learning Hub", "🏫 Academia Clinica", monkeypatch)
    at.run()
    assert not any("no está disponible" in w.value for w in at.warning)
    next(b for b in at.button if b.key == "academia_start_quiz").click().run()
    assert not at.exception
    next(b for b in at.button if b.key == "academia_quiz_submit_0").click().run()
    assert not at.exception
    verdicts = [s.value for s in at.success] + [e.value for e in at.error]
    assert any("Correcto" in v or "respuesta correcta" in v for v in verdicts)
    assert any("Sin motor de IA" in m.value for m in at.markdown)


def test_synthetic_case_works_without_api_key(monkeypatch):
    at = _app("Learning Hub", "🏫 Academia Clinica", monkeypatch)
    at.run()
    next(b for b in at.button if b.key == "academia_case_new").click().run()
    assert not at.exception
    confirm = next(b for b in at.button if b.key and b.key.startswith("academia_case_confirm_"))
    confirm.click().run()
    assert not at.exception
    assert any("caso" in v.value.lower() for v in list(at.success) + list(at.error))


def test_rural_mode_roundtrip(tmp_path):
    from educational import rural_mode
    path = rural_mode.save_progress("../../estudiante 1", {"ECG Básico": {"completed": True, "score": 80.0}},
                                    base_dir=tmp_path)
    assert path.parent == tmp_path  # el id no puede escapar del directorio
    assert rural_mode.load_progress("../../estudiante 1", base_dir=tmp_path) == {
        "ECG Básico": {"completed": True, "score": 80.0}}
    assert rural_mode.load_progress("nadie", base_dir=tmp_path) is None


def test_quiz_options_are_in_spanish():
    from educational.learning_engine import generate_quiz
    choices = [c for q in generate_quiz(level="advanced").values() for c in q.choices]
    assert "R predominante en V1" in choices
    assert not any(word in " ".join(choices) for word in ("predominant in", "Deep S", "Large R"))


# ─── HRV ─────────────────────────────────────────────────────────────────

def test_hrv_page_shows_spectrum_and_poincare(monkeypatch):
    at = _app("Clinical Hub", "📈 HRV Analysis", monkeypatch)
    at.run()
    assert not at.exception
    assert not any("No se pudo calcular espectro" in i.value for i in at.info)  # np.trapz retirado en NumPy 2
    html = " ".join(m.value for m in at.markdown)
    assert "Poincaré" in html and "<strong>SD1" in html and "<strong>SD2" in html


def test_hrv_demo_series_is_stable_across_reruns(monkeypatch):
    at = _app("Clinical Hub", "📈 HRV Analysis", monkeypatch)
    at.run()
    first = " ".join(m.value for m in at.markdown if "SDNN" in m.value)
    at.run()
    second = " ".join(m.value for m in at.markdown if "SDNN" in m.value)
    assert first == second


def test_hrv_file_source_without_upload_shows_empty_state(monkeypatch):
    at = _app("Clinical Hub", "📈 HRV Analysis", monkeypatch)
    at.run()
    radio = next(r for r in at.sidebar.radio if r.label == "HRV Source")
    radio.set_value("Archivo CSV/TXT de RR").run()
    assert not at.exception
    assert any("Sube un archivo" in m.value for m in at.markdown)


# ─── Digital Twin OS: tarjetas de órganos alineadas ──────────────────────

def test_organ_cards_have_fixed_height(monkeypatch):
    at = _app("Digital Twin OS", "🧬 Digital Twin OS", monkeypatch)
    at.run()
    cards = [m.value for m in at.markdown if "border-radius: 18px" in m.value]
    assert len(cards) == 5
    # Misma altura fija en las cinco (2026-10-21: 196 px, para la imagen
    # real del órgano); el valor exacto puede cambiar, la igualdad no.
    heights = {re.search(r"height: (\d+)px", c).group(1) for c in cards}
    assert len(heights) == 1
    assert not any("3px solid" in c for c in cards)  # la selección ya no engrosa el borde
