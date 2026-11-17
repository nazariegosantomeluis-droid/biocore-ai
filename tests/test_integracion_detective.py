"""Detective fisiológico (integración, 2026-11-17): pistas a demanda, diagnóstico con confianza y justificación,
corrección determinista, registro descriptivo de la sesión. Todo con la base de pruebas (`tests/conftest.py`).

Art. I: la pista que el caso no trae se dice «sin dato»; no hay ECG/EEG/EMG ni `ahi`; la justificación no se califica;
la PA calculada solo existe en los 3 escenarios con modelo validado."""

import random
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app.supermodules.detective.pages as dp
from app.engines.simulation_engine import SimulationScenario as S
from app.utils.session_learning import CONCEPTS
from domain.physiology.scenarios.case_bank import available_rich_scenarios, generate_case as real_generate_case

MAIN = str(Path("app/main.py").resolve())
LOG_KEY = "session_learning_log"


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _case(monkeypatch, scenario):
    """El caso es el escenario dado (el banco lo elige al azar); lo demás es el banco real."""
    monkeypatch.setattr(dp, "generate_case", lambda session: real_generate_case(session, scenario, random.Random(7)))


def _open():
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_start_page"] = "detective"
    at.run()
    assert at.exception == [], at.exception
    return at


def _click(at, label_part):
    next(b for b in at.button if label_part in b.label).click().run()
    assert at.exception == [], at.exception


def _text(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    parts += [s.value for s in at.success] + [e.value for e in at.error]
    return "\n".join(parts)


def _button(at, label_part):
    return next(b for b in at.button if label_part in b.label)


def _start(monkeypatch, scenario):
    _case(monkeypatch, scenario)
    at = _open()
    _click(at, "Nuevo caso")
    return at


def test_todo_escenario_tiene_un_concepto_valido():
    assert set(dp.SCENARIO_CONCEPT) == set(available_rich_scenarios()) == set(S)
    assert set(dp.SCENARIO_CONCEPT.values()) <= set(CONCEPTS)


def test_sin_caso_la_pagina_lo_dice_y_no_hay_pistas():
    at = _open()
    assert "Sin caso todavía" in _text(at)
    assert not [b for b in at.button if any(label in b.label for _, label in dp.CLUES)]


def test_las_pistas_se_piden_una_a_una_y_el_diagnostico_no_se_filtra(monkeypatch):
    at = _start(monkeypatch, S.SEPSIS)
    assert "Aún no pediste ninguna pista" in _text(at)
    assert "sepsis" not in _text(at).lower(), "el diagnóstico no debe verse antes de confirmar"
    _click(at, "Signos vitales")
    text = _text(at)
    assert "NEWS2" in text and "Simulación" in text
    assert "sepsis" not in text.lower()
    assert _button(at, "Signos vitales").disabled, "una pista pedida no se pide dos veces"
    assert not _button(at, "Presión arterial").disabled


def test_no_se_puede_diagnosticar_sin_pistas_ni_justificacion(monkeypatch):
    at = _start(monkeypatch, S.SEPSIS)
    assert _button(at, "Confirmar").disabled
    assert "al menos una pista" in _text(at)
    _click(at, "Signos vitales")
    at.radio[0].set_value(at.radio[0].options[0]).run()
    assert _button(at, "Confirmar").disabled, "sin justificación no se confirma"
    at.text_area[0].set_value("   ").run()
    assert _button(at, "Confirmar").disabled, "una justificación en blanco no cuenta"
    at.text_area[0].set_value("La FC y la FR suman puntos NEWS2.").run()
    assert not _button(at, "Confirmar").disabled


def _answer(at, scenario, correct, confidence=80):
    radio = at.radio[0]
    options = list(radio.options)
    pick = next(o for o in options if (_value_of(o) == scenario) == correct)
    radio.set_value(pick).run()
    at.slider[0].set_value(confidence).run()
    at.text_area[0].set_value("Me baso en los puntos NEWS2.").run()
    _click(at, "Confirmar")


def _value_of(option):
    # AppTest entrega la opción ya formateada (`RICH_SCENARIO_LABELS`): se devuelve el escenario que la tiene.
    return next((s for s, label in dp.RICH_SCENARIO_LABELS.items() if label == option or s == option), option)


@pytest.mark.parametrize("correct", [True, False])
def test_correccion_determinista_y_registro_descriptivo(monkeypatch, correct):
    at = _start(monkeypatch, S.SEPSIS)
    _click(at, "Signos vitales")
    _click(at, "Eventos")
    _answer(at, S.SEPSIS, correct, confidence=80)
    text = _text(at)
    assert ("Correcto" in text) == correct
    assert dp.RICH_SCENARIO_LABELS[S.SEPSIS] in text
    assert "Me baso en los puntos NEWS2." in text and "no se califica" in text
    assert "Pediste 2 de 4 pistas" in text
    assert dp.CASE_EXPLANATION_PENDING in text, "no hay explicación clínica por escenario con fuente: se dice"
    log = at.session_state[LOG_KEY]
    assert len(log) == 1
    entry = log[0]
    assert (entry["source"], entry["concept"], entry["correct"], entry["confidence"]) == \
        ("detective", "hemodinamica", correct, 80)
    assert "Tu sesión con el Detective" in text and "no una medida de dominio" in text


def test_pa_calculada_solo_donde_el_modelo_esta_validado(monkeypatch):
    sepsis = _start(monkeypatch, S.SEPSIS)
    _click(sepsis, "Presión arterial")
    assert "PA calculada" in _text(sepsis) and "no es una medición" in _text(sepsis)

    anxiety = _start(monkeypatch, S.ANXIETY)
    _click(anxiety, "Presión arterial")
    text = _text(anxiety)
    assert "PA calculada" not in text and "no modelada" in text


def test_ninguna_pista_inventa_ecg_ni_ahi_ni_bpm(monkeypatch):
    at = _start(monkeypatch, S.APNEA)
    for _, label in dp.CLUES:
        _click(at, label.split(" ", 1)[1][:12])
    text = _text(at)
    assert "bpm" not in text and "AHI" not in text and "ahi" not in text.lower().split()
    assert not any(b.label for b in at.button if "ECG" in b.label or "EEG" in b.label or "EMG" in b.label)


def test_las_pistas_no_pedidas_se_ven_solo_despues_de_responder(monkeypatch):
    at = _start(monkeypatch, S.HYPERTENSION)
    _click(at, "Signos vitales")
    assert not [e for e in at.expander if "no pediste" in e.label]
    _answer(at, S.HYPERTENSION, True)
    assert [e for e in at.expander if "no pediste" in e.label]


def test_la_pagina_no_toca_al_paciente_activo(monkeypatch):
    at = _start(monkeypatch, S.STRESS)
    assert "twin_shell_ups_patient_id" not in at.session_state


@pytest.mark.parametrize("scenario", list(S), ids=lambda s: s.value)
def test_cada_escenario_con_todas_las_pistas_y_su_respuesta_sin_ingles_ni_tratamiento(monkeypatch, scenario):
    """El mismo filtro de idioma/tratamiento que recorre las 23 páginas, pero con un caso abierto de cada escenario."""
    from tests.test_fase1_t2_pulido import FORBIDDEN, TREATMENT, _without_citations, visible_texts

    at = _start(monkeypatch, scenario)
    for _, label in dp.CLUES:
        _click(at, label.split(" ", 1)[1][:12])
    _answer(at, scenario, True)
    texts = [_without_citations(t) for t in visible_texts(at)]
    assert [(m.group(0), t[:100]) for t in texts for m in [FORBIDDEN.search(t)] if m] == []
    assert [(m.group(0), t[:100]) for t in texts for m in [TREATMENT.search(t)] if m] == []
    assert at.session_state[LOG_KEY][0]["concept"] == dp.SCENARIO_CONCEPT[scenario]
