"""Frente cardiovascular, Fase 1, PARTE D (2026-11-12, Art. I): lo que ve el estudiante en Twin OS.

AppTest con base TEMPORAL en tres casos: (1) sliders (estado normal), (2) organismo SIN alimentar (provocado solo dentro
de la prueba, sin tocar el repo) y (3) solo respiratorio. Regla: un dato faltante es «sin dato» en gris; ningún número
aparece sin su fuente (insignia o «Entrada: …»); nunca «BAJO», «0», «50» ni «Alerta» por falta de datos.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.engines.digital_twin_organism import NO_DATA, NO_DATA_COLOR, NOT_MODELED

PAGES = Path("app/supermodules/twin_shell/pages.py")


def _script():
    import streamlit as st
    import app.supermodules.twin_shell.pages as m

    if not hasattr(m, "_orig_sensor_controls"):
        m._orig_sensor_controls = m.render_sensor_controls
    feed = st.session_state.get("_feed")
    if feed == "none":
        m.render_sensor_controls = lambda organism: None
    elif feed == "resp":
        m.render_sensor_controls = lambda organism: organism.update_from_sensors(
            {"respiratory": {"respiratory_rate": 14.0, "spo2": 97.0}})
    else:
        m.render_sensor_controls = m._orig_sensor_controls
    m.run()


@pytest.fixture(scope="module", autouse=True)
def _restore_sensor_controls_after_the_module():
    """El AppTest de los casos 2 y 3 sustituye `render_sensor_controls` DENTRO del módulo de la página (solo para
    provocar el organismo sin alimentar); se restaura al terminar para no contaminar a las demás pruebas."""
    import app.supermodules.twin_shell.pages as pages

    original = pages.render_sensor_controls
    yield
    pages.render_sensor_controls = getattr(pages, "_orig_sensor_controls", original)


def _text(at):
    out = {"md": [], "cap": [], "metric": [], "warn": [], "code": [], "json": []}
    for e in at.markdown:
        out["md"].append(" ".join(re.sub(r"<[^>]+>", " ", str(e.value)).split()))
    for e in at.caption:
        out["cap"].append(" ".join(str(e.value).split()))
    for e in at.metric:
        out["metric"].append((e.label, e.value, e.help or ""))
    for e in at.warning:
        out["warn"].append(str(e.value))
    for e in at.code:
        out["code"].append(str(e.value))
    for e in at.json:
        out["json"].append(str(e.value))
    return out


def _run(tmp_path_factory, feed, organ="heart", mode="Researcher"):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path_factory.mktemp(f"twin_{feed}") / "twin.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name=f"twin {feed}")
    at = AppTest.from_function(_script, default_timeout=180)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.session_state["_feed"] = feed
    at.session_state["twin_shell_selected_organ"] = organ
    at.session_state["twin_shell_mode"] = mode
    at.run()
    assert at.exception == [], at.exception
    return at, _text(at)


@pytest.fixture(scope="module")
def sliders(tmp_path_factory):
    return _run(tmp_path_factory, "sliders")


@pytest.fixture(scope="module")
def unfed(tmp_path_factory):
    return _run(tmp_path_factory, "none")


@pytest.fixture(scope="module")
def respiratory_only(tmp_path_factory):
    return _run(tmp_path_factory, "resp")


def _card(texts, organ_name):
    return next(t for t in texts["md"] if t.startswith(organ_name))


def _header(texts):
    return next(t for t in texts["md"] if t.startswith("ESTADO FISIOLÓGICO GLOBAL"))


# --------------------------------------------------------------------------------------- (1) sliders (estado normal)
def test_with_sliders_the_heart_shows_hr_and_news2_points_with_their_source_and_no_health_score(sliders):
    at, t = sliders
    heart = _card(t, "❤️ Corazón")
    assert "FC 72 lpm" in heart and "NEWS2 pulso 0/3" in heart
    assert "NEWS2 (RCP 2017)" in heart and "simulación: sliders de Twin OS" in heart       # cada número, con su fuente
    assert "Óptimo" not in heart and "Alerta" not in heart and "100" not in heart            # el «100 saturado» ya no existe
    metrics = {label: (value, help_) for label, value, help_ in t["metric"]}
    assert metrics["🟢 Puntos NEWS2 del pulso"][0] == "0 de 3"
    assert metrics["Frecuencia cardíaca"] == ("72 lpm", "Entrada: simulación: sliders de Twin OS")
    assert metrics["Gasto cardíaco"][0] == NOT_MODELED
    assert "Parámetros de alta fidelidad" in " ".join(t["md"]) and NOT_MODELED in " ".join(t["cap"])
    assert "cardiac_output" not in " ".join(t["json"]) and "rhythm_stability" not in " ".join(t["json"])


def test_the_estres_slider_no_longer_fabricates_alpha_power(sliders):
    at, _ = sliders
    organism = at.session_state["twin_shell_organism"]
    assert organism.organs["brain"].metrics.signals == {"stress_level": 35}                   # solo lo que significa
    assert "alpha_power" not in organism.organs["brain"].metrics.signals
    assert organism.input_provenance == "simulación: sliders de Twin OS"
    assert "alpha_power = max(0, 70" not in PAGES.read_text(encoding="utf-8")


def test_the_global_indices_are_no_data_because_they_depend_on_a_retired_value(sliders):
    _, t = sliders
    header = _header(t)
    assert header.count(NO_DATA) == 4                                                       # estado, riesgo, coherencia, resiliencia
    assert "BAJO" not in header and "Baja" not in header and "Crítico" not in header
    metrics = {label: value for label, value, _ in t["metric"]}
    assert metrics["Riesgo global"] == NO_DATA
    assert any("escala distinta" in h for _, _, h in t["metric"] if "Promedio" in h)
    assert "Hoy están en «sin dato»" in " ".join(t["cap"])


def test_the_risk_panel_uses_news2_points_for_the_heart(sliders):
    _, t = sliders
    cardio = next(m for m in t["md"] if m.startswith("**🟢 Cardiovascular**"))
    assert "NEWS2 pulso: 0 punto(s)" in cardio and "/100" not in cardio and "BAJO" not in cardio


# ---------------------------------------------------------------------------------------- (2) organismo sin alimentar
def test_an_unfed_organism_shows_no_data_in_every_card_the_header_and_the_panels(unfed):
    _, t = unfed
    for name in ("❤️ Corazón", "🧠 Cerebro", "💨 Pulmones", "💪 Músculos", "⚡ Sistema Nervioso Autónomo"):
        card = _card(t, name)
        assert NO_DATA in card and not re.search(r"\d", card), card                          # ni 50, ni «Alerta», ni «Óptimo»
        for banned in ("Alerta", "Óptimo", "Normal", "Crítico", "BAJO"):
            assert banned not in card, (name, banned)
    header = _header(t)
    assert header.count(NO_DATA) == 4 and not re.search(r"\d", header)
    for label, value, _ in t["metric"]:
        assert value in (NO_DATA, NOT_MODELED), (label, value)                                # ningún número en ninguna métrica
    risk = [m for m in t["md"] if re.match(r"\*\*⚪ (Cardiovascular|Respiratorio|Neurológico|Muscular|Autonómico)\*\*", m)]
    assert len(risk) == 5 and all(m.endswith(f"— {NO_DATA}") for m in risk)
    assert not any("rutinario" in c.lower() or "adecuado" in c.lower() for c in t["cap"])
    code = t["code"][0]
    cardio = code.split("🫀 SISTEMA CARDIOVASCULAR:")[1].split("🧠")[0]
    assert not re.search(r"\d", cardio.replace("NEWS2", "")) and "0.0 bpm" not in code and "5.0 L/min" not in code


def test_the_grey_is_the_one_the_digital_body_uses():
    from app.supermodules.twin_shell import ups_body_visual

    assert NO_DATA_COLOR == ups_body_visual.NEUTRAL_COLOR


def test_the_pages_have_no_more_default_get_for_missing_organism_data():
    source = PAGES.read_text(encoding="utf-8")
    for pattern in (r"""state\.get\(\s*["']global_health_score["']\s*,\s*50""", r"""state\.get\(\s*["']risk_level["']\s*,\s*["']BAJO""",
                    r"""state\.get\(\s*["']system_coherence["']\s*,\s*0""", r"""state\.get\(\s*["']resilience_index["']\s*,\s*0""",
                    r"""coupling["']\s*,\s*0\.5"""):
        assert not re.search(pattern, source), pattern


# -------------------------------------------------------------------------------------------- (3) solo respiratorio
def test_with_only_respiratory_data_only_the_lungs_have_a_number(respiratory_only):
    _, t = respiratory_only
    for name in ("❤️ Corazón", "🧠 Cerebro", "💪 Músculos", "⚡ Sistema Nervioso Autónomo"):
        assert NO_DATA in _card(t, name) and not re.search(r"\d", _card(t, name)), name
    assert re.search(r"\d", _card(t, "💨 Pulmones"))                                         # los pulmones SÍ tienen entradas
    header = _header(t)
    assert header.count(NO_DATA) == 4 and not re.search(r"\d", header)
    metrics = {label: value for label, value, _ in t["metric"]}
    assert metrics["🟢🔵 Corazón ↔ Pulmones"] == NO_DATA                                    # FR sin FC actual: no hay acoplamiento
    assert metrics["🔵 Cerebro ↔ Corazón"] == NO_DATA and metrics["🔵 Cerebro ↔ Músculos"] == NO_DATA
    assert metrics["Riesgo global"] == NO_DATA and metrics["Frecuencia cardíaca"] == NO_DATA
    cardio = next(m for m in t["md"] if "Cardiovascular**" in m)
    assert cardio.endswith(f"— {NO_DATA}") and "rutinario" not in " ".join(t["cap"]).lower()
    resp = next(m for m in t["md"] if "Respiratorio**" in m)
    assert "BAJO" in resp                                                                    # evaluó SpO2 y FR reales: sí hay dato


# ---------------------------------------------------------------- comparación: ningún número sin fuente (3 casos)
def test_no_metric_or_card_shows_a_number_without_its_source_in_any_of_the_three_cases(sliders, unfed, respiratory_only):
    badges = ("🟢", "🔵")
    for _, t in (sliders, unfed, respiratory_only):
        for label, value, help_ in t["metric"]:
            if re.search(r"\d", value):
                assert any(b in label or b in help_ for b in badges) or help_.startswith("Entrada:"), (label, value, help_)
        for name in ("❤️ Corazón", "🧠 Cerebro", "💨 Pulmones", "💪 Músculos", "⚡ Sistema Nervioso Autónomo"):
            card = _card(t, name)
            if re.search(r"\d", card):
                assert any(b in card for b in badges), card
