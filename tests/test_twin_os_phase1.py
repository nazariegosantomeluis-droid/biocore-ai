"""Twin OS (Fase 1 cardiovascular, 2026-11-12, y cierre de la fase 0, 2026-11-13; Art. I): lo que ve el estudiante.

AppTest con base TEMPORAL en cuatro casos: (1) sliders (estado normal), (2) organismo SIN alimentar (provocado solo
dentro de la prueba, sin tocar el repo), (3) solo respiratorio y (4) sepsis activa que sobrevive a otro control
(Parte D). Regla: un dato faltante es «sin dato» en gris; ningún número aparece sin su fuente (insignia o
«Entrada: …»); nunca «BAJO», «0», «50» ni «Alerta» por falta de datos; nunca un total NEWS2.
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
    out = {"md": [], "cap": [], "metric": [], "warn": [], "code": [], "json": [], "info": []}
    for e in at.markdown:
        out["md"].append(" ".join(re.sub(r"<[^>]+>", " ", str(e.value)).split()))
    for e in at.caption:
        out["cap"].append(" ".join(str(e.value).split()))
    for e in at.metric:
        out["metric"].append((e.label, e.value, e.help or ""))
    for e in at.warning:
        out["warn"].append(str(e.value))
    for e in at.info:
        out["info"].append(str(e.value))
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
    return _run(tmp_path_factory, "resp", organ="lungs")


CARDS = ("❤️ Corazón", "🧠 Cerebro", "💨 Pulmones", "💪 Músculos", "⚡ Sistema Nervioso Autónomo")


def _card(texts, organ_name):
    return next(t for t in texts["md"] if t.startswith(organ_name))


def _header(texts):
    return next(t for t in texts["md"] if t.startswith("NEWS2 PARCIAL"))


# --------------------------------------------------------------------------------------- (1) sliders (estado normal)
def test_with_sliders_every_card_shows_its_inputs_with_their_source_and_no_index(sliders):
    at, t = sliders
    heart = _card(t, "❤️ Corazón")
    assert "FC 72 lpm" in heart and "NEWS2 pulso 0/3" in heart and "NEWS2 (RCP 2017)" in heart
    assert "simulación: sliders de Twin OS" in heart
    lungs = _card(t, "💨 Pulmones")
    assert "FR 16" in lungs and "SpO₂ 98" in lungs and "NEWS2 FR 0/3" in lungs and "SpO₂ 0/3" in lungs
    assert "Estrés 35/100" in _card(t, "🧠 Cerebro") and "sin criterio con fuente" in _card(t, "🧠 Cerebro")
    assert "Fatiga 20/100" in _card(t, "💪 Músculos")
    assert "HRV 50 ms" in _card(t, "⚡ Sistema Nervioso Autónomo") and "la HRV como HRV" in _card(t, "⚡ Sistema Nervioso Autónomo")
    for name in CARDS:
        for banned in ("Óptimo", "Alerta", "Normal", "Crítico", "BAJO", "heurística"):
            assert banned not in _card(t, name), (name, banned)
    metrics = {label: (value, help_) for label, value, help_ in t["metric"]}
    assert metrics["🟢 Puntos NEWS2 del pulso"][0] == "0 de 3"
    assert metrics["Frecuencia cardíaca"] == ("72 lpm", "Entrada: simulación: sliders de Twin OS")
    assert metrics["Gasto cardíaco"][0] == NOT_MODELED
    assert "cardiac_output" not in " ".join(t["json"]) and "efficiency" not in " ".join(t["json"])


def test_the_sliders_no_longer_fabricate_alpha_power_or_efficiency(sliders):
    at, _ = sliders
    organism = at.session_state["twin_shell_organism"]
    assert organism.organs["brain"].metrics.signals == {"stress_level": 35}
    assert organism.organs["muscles"].metrics.signals == {"fatigue_index": 20}             # sin efficiency = 100 - fatiga
    assert organism.input_provenance == "simulación: sliders de Twin OS"
    source = PAGES.read_text(encoding="utf-8")
    assert "alpha_power = max(0, 70" not in source and "100 - fatigue" not in source


def test_the_header_is_a_partial_news2_that_lists_what_is_missing_and_never_a_total(sliders):
    _, t = sliders
    header = _header(t)
    assert "SIN TOTAL" in header and "Pulso 0" in header and "Frecuencia respiratoria 0" in header and "SpO₂ (escala 1) 0" in header
    for missing in ("presión arterial sistólica", "temperatura", "nivel de consciencia (ACVPU)", "oxígeno suplementario"):
        assert missing in header, missing
    joined = " ".join(t["md"] + t["cap"] + [v for _, v, _ in t["metric"]])
    for gone in ("ESTADO FISIOLÓGICO GLOBAL", "Coherencia sistémica", "Resiliencia", "Riesgo global", "Cerebro ↔ Corazón",
                 "Cerebro ↔ Músculos", "Riesgo: BAJO", "/100)"):
        assert gone not in joined, gone
    assert not re.search(r"NEWS2[^|]{0,40}total[^|]{0,15}\d", joined)                      # ningún «total N»


def test_the_heart_lung_coupling_is_the_hr_rr_ratio_with_its_verified_source(sliders):
    _, t = sliders
    metrics = {label: (value, help_) for label, value, help_ in t["metric"]}
    value, help_ = metrics["Razón FC:FR"]
    assert value == "4.5 : 1" and "%" not in value
    assert "Scholkmann" in help_ and "3:1 y 4:1" in help_ and "Entrada: simulación: sliders de Twin OS" in help_
    assert "Corazón ↔ Pulmones: razón FC:FR" in " ".join(t["md"])


def test_the_risk_panel_shows_news2_components_and_declares_systems_without_a_sourced_criterion(sliders):
    _, t = sliders
    assert any(m.startswith("**🟢 Cardiovascular** — NEWS2 pulso: 0 punto(s)") for m in t["md"])
    assert any("**🟢 Respiratorio** — NEWS2 Frecuencia respiratoria: 0 punto(s) · NEWS2 SpO₂ (escala 1): 0 punto(s)" in m for m in t["md"])
    for system in ("Neurológico", "Muscular", "Autonómico"):
        assert any(m == f"**⚪ {system}** — sin criterio con fuente" for m in t["md"]), system
    metrics = {label: value for label, value, _ in t["metric"]}
    assert metrics["NEWS2 parcial (sin total)"] == "Pulso 0 · Frecuencia respiratoria 0 · SpO₂ (escala 1) 0"


# ---------------------------------------------------------------------------------------- (2) organismo sin alimentar
def test_an_unfed_organism_shows_no_data_in_every_card_the_header_and_the_panels(unfed):
    _, t = unfed
    for name in CARDS:
        card = _card(t, name)
        assert NO_DATA in card and not re.search(r"\d", card), card                          # ni 50, ni «Alerta», ni «Óptimo»
        for banned in ("Alerta", "Óptimo", "Normal", "Crítico", "BAJO"):
            assert banned not in card, (name, banned)
    header = _header(t)
    assert NO_DATA in header and not re.search(r"\d", header.replace("NEWS2", "").replace("O₂", ""))
    for label, value, _ in t["metric"]:
        assert value in (NO_DATA, NOT_MODELED, "retirado"), (label, value)                   # ningún número en ninguna métrica
    risk = [m for m in t["md"] if re.match(r"\*\*⚪ (Cardiovascular|Respiratorio|Neurológico|Muscular|Autonómico)\*\*", m)]
    assert len(risk) == 5 and all(m.endswith(f"— {NO_DATA}") for m in risk)
    assert not any("rutinario" in c.lower() or "adecuado" in c.lower() for c in t["cap"])
    code = t["code"][0]
    cardio = code.split("🫀 SISTEMA CARDIOVASCULAR:")[1].split("🧠")[0]
    assert not re.search(r"\d", cardio.replace("NEWS2", "")) and "0.0 bpm" not in code and "5.0 L/min" not in code


def test_the_grey_is_the_one_the_digital_body_uses():
    from app.supermodules.twin_shell import ups_body_visual

    assert NO_DATA_COLOR == ups_body_visual.NEUTRAL_COLOR


def test_the_pages_have_no_more_default_get_nor_retired_indices():
    source = PAGES.read_text(encoding="utf-8")
    for pattern in (r"""state\.get\(\s*["']global_health_score["']""", r"""state\.get\(\s*["']risk_level["']""", r"""["']system_coherence["']""",
                    r"""["']resilience_index["']""", r"neurocardiac_coupling", r"neuromuscular_coupling", r"cardiorespiratory_coupling",
                    r"OrganHealthStatus", r"ORGAN_STATUS_LABELS", r"metrics\.risk_score", r"activity_level", r"\.detail\b"):
        assert not re.search(pattern, source), pattern


# -------------------------------------------------------------------------------------------- (3) solo respiratorio
def test_with_only_respiratory_data_only_the_lungs_have_numbers_and_they_carry_their_source(respiratory_only):
    _, t = respiratory_only
    for name in ("❤️ Corazón", "🧠 Cerebro", "💪 Músculos", "⚡ Sistema Nervioso Autónomo"):
        assert NO_DATA in _card(t, name) and not re.search(r"\d", _card(t, name)), name
    lungs = _card(t, "💨 Pulmones")
    assert "FR 14" in lungs and "SpO₂ 97" in lungs and "NEWS2 FR 0/3" in lungs and "SpO₂ 0/3" in lungs
    header = _header(t)
    assert "Frecuencia respiratoria 0" in header and "SpO₂ (escala 1) 0" in header and "Pulso" not in header.split("Faltan")[0]
    assert "pulso" in header.split("Faltan para el total:")[1]
    metrics = {label: value for label, value, _ in t["metric"]}
    assert metrics["Razón FC:FR"] == NO_DATA                                                # FR sin FC actual
    assert metrics["🟢 NEWS2 FR"] == "0 de 3" and metrics["🟢 NEWS2 SpO₂ (escala 1)"] == "0 de 3"
    assert metrics["🔵 Índice de salud pulmonar"] == NO_DATA and metrics["AHI"] == NO_DATA     # sin AHI: no se calcula con 0
    assert metrics["SpO₂ escala 2"] == NOT_MODELED
    cardio = next(m for m in t["md"] if "Cardiovascular**" in m)
    assert cardio.endswith(f"— {NO_DATA}") and "rutinario" not in " ".join(t["cap"]).lower()
    resp = next(m for m in t["md"] if "Respiratorio**" in m)
    assert "NEWS2 Frecuencia respiratoria: 0 punto(s)" in resp and "BAJO" not in resp


# --------------------------------------------------------------------------- (4) sepsis activa sobrevive a otro control
def test_an_applied_scenario_is_not_overwritten_by_the_sliders_until_the_student_returns_to_them(tmp_path_factory):
    at, _ = _run(tmp_path_factory, "sliders")
    at.selectbox(key="twin_shell_sepsis_horizon").set_value("24h")
    at.button(key="twin_shell_sepsis_apply").click().run()
    assert at.exception == []
    organism = at.session_state["twin_shell_organism"]
    assert organism.organs["heart"].metrics.signals["heart_rate"] == pytest.approx(150.0)
    # interactuar con OTRO control (el modo de detalle) provoca un rerun: antes, los sliders volvían a 72 lpm
    at.radio[0].set_value("Clinician").run()
    assert at.exception == []
    organism = at.session_state["twin_shell_organism"]
    assert organism.organs["heart"].metrics.signals["heart_rate"] == pytest.approx(150.0)
    assert at.session_state["twin_shell_input_source"].startswith("sepsis, horizonte 24h")
    t = _text(at)
    assert any("Fuente activa: sepsis, horizonte 24h" in i for i in t["info"])
    heart = _card(t, "❤️ Corazón")
    assert "FC 150 lpm" in heart and "NEWS2 pulso 3/3" in heart and "trayectoria canónica de sepsis" in heart
    assert "Pulso 3" in _header(t) and "Frecuencia respiratoria 3" in _header(t) and "SpO₂ (escala 1) 3" in _header(t)
    assert any("3 puntos NEWS2" in w for w in t["warn"])
    # control explícito para volver a los sliders
    at.button(key="twin_shell_back_to_sliders").click().run()
    assert at.exception == [] and "twin_shell_input_source" not in at.session_state
    assert at.session_state["twin_shell_organism"].organs["heart"].metrics.signals["heart_rate"] == 72
    assert any("Fuente activa: sliders de Twin OS" in c for c in _text(at)["cap"])


# ---------------------------------------------------------------- comparación: ningún número sin fuente (3 casos)
def test_no_metric_or_card_shows_a_number_without_its_source_in_any_case(sliders, unfed, respiratory_only):
    badges = ("🟢", "🔵")
    for _, t in (sliders, unfed, respiratory_only):
        for label, value, help_ in t["metric"]:
            if re.search(r"\d", value):
                assert any(b in label or b in help_ for b in badges) or help_.startswith("Entrada:"), (label, value, help_)
        for name in CARDS:
            card = _card(t, name)
            if re.search(r"\d", card):
                assert any(b in card for b in badges) or "entrada:" in card, card
