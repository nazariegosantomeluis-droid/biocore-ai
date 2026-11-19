"""T6.1 (2026-11-19): techo de la regla BAR.

Decisión de Luis (2026-11-19): «Si el BAR ya está cerca de 100 (como ocurre con «Beta (activo)»), sumar +15 lpm a
ciegas es un error de saturación […] Hay que acotar la regla con un límite superior explícito […] declarando
explícitamente el tope y su naturaleza heurística/de modelo. Tu pon ese límite con la literatura que encuentres».

Techo: BAR ≤ 3.0, Criterio BIOCORE (heurística), con su motivo en `docs/contenido/fichas_acoplamientos.md`: la fuente
describe basal 0.8–1.2 y arousal > 1.8 y no da valores más altos; con una tarea, la fracción de beta a lo sumo se
duplica (Li 2020: 15 → 28 %) y el estrés baja el alfa de forma moderada (Vanhollebeke 2022, g = 0.6); un BAR muy
alto es más compatible con un alfa casi ausente (sueño, una señal sintética de una sola banda) o con artefacto
muscular en beta (Goncharova 2003) que con arousal.
"""

import dataclasses
from datetime import timedelta

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.coupling import AROUSAL_TAQUICARDIA_BAR, evaluate_rule_for_patient
from domain.physiology.state import (
    Provenance,
    create_patient,
    from_digital_twin_organism,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)


@pytest.fixture
def sf(tmp_path):
    engine = make_engine(tmp_path / "t61.db")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture
def pid(sf):
    with sf() as s:
        return create_patient(s, display_name="t61")


def _save(sf, pid, sensors, age_s=0.0):
    o = DigitalTwinOrganism()
    o.update_from_sensors(sensors)
    state = from_digital_twin_organism(o, pid, Provenance.SIMULACION, 0.85, source_detail="prueba")
    if age_s:
        state = dataclasses.replace(state, timestamp=state.timestamp - timedelta(seconds=age_s))
    with sf() as s:
        return save_state(s, state)


def test_la_regla_bar_declara_su_techo_y_su_naturaleza():
    c = AROUSAL_TAQUICARDIA_BAR.condition
    assert c.upper_limit == 3.0
    assert "Criterio BIOCORE" in c.upper_limit_basis and "Goncharova" in c.upper_limit_basis


@pytest.mark.parametrize("value,fires", [(1.8, False), (1.81, True), (2.5, True), (3.0, True), (3.01, False),
                                         (119.0, False)])
def test_la_condicion_respeta_el_umbral_y_el_techo(value, fires):
    assert AROUSAL_TAQUICARDIA_BAR.condition.is_triggered_by(value) is fires


def test_la_regla_de_hipoxia_no_tiene_techo():
    from domain.physiology.coupling import HIPOXIA_TAQUICARDIA

    assert HIPOXIA_TAQUICARDIA.condition.upper_limit is None
    assert HIPOXIA_TAQUICARDIA.condition.is_triggered_by(60.0)


@pytest.mark.parametrize("alpha,beta,coupled", [(10.0, 25.0, True), (0.25, 30.0, False)])
def test_el_compositor_no_acopla_por_encima_del_techo(sf, pid, alpha, beta, coupled):
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}}, age_s=10)
    _save(sf, pid, {"eeg": {"alpha_power": alpha, "beta_power": beta, "theta_power": 0.2, "delta_power": 0.2}})
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario="healthy")
    assert r.available and (r.coupled is not None) is coupled
    assert r.above_limit is (not coupled)


# ── En la Ruta (Unidad Cerebro) ────────────────────────────────────────────────────────────────────────────────────
def test_el_patron_de_vigilia_con_arousal_da_un_bar_dentro_del_rango():
    from app.instruments.eeg import AROUSAL_PATTERN, BASE_PATTERNS
    from tests.test_ruta_unidades_t4 import _composed, _save_eeg, _start

    assert AROUSAL_PATTERN in BASE_PATTERNS
    at = _save_eeg(_start("cerebro"), AROUSAL_PATTERN)
    bar = _composed(at).state.neurological.get("bar")
    assert 1.8 < bar.value <= 3.0


def test_con_beta_activo_la_estacion_dice_que_el_bar_pasa_el_techo():
    from tests.test_ruta_unidades_t4 import _composed, _go, _save_eeg, _start, _texts
    from tests.test_t6_acoplamientos_ruta import _measure_hr

    at = _go(_save_eeg(_start("cerebro"), "Beta (activo)"), "cerebro", "cierre")
    _measure_hr(at, "cerebro")
    assert _composed(at).state.cardiovascular.get("heart_rate_acoplado") is None
    text = _texts(at)
    assert "pasa el techo de la regla (3.0" in text and "Criterio BIOCORE" in text


def test_la_estacion_muestra_el_techo_con_la_regla():
    from tests.test_ruta_unidades_t4 import _go, _start, _texts

    text = _texts(_go(_start("cerebro"), "cerebro", "cierre"))
    assert "techo" in text and "3.0" in text and "Goncharova" in text


# ── Revisión final de la T6.1 ───────────────────────────────────────────────────────────────────────────────────────
SLEEP = {"alpha_power": 10.0, "beta_power": 25.0, "theta_power": 50.0, "delta_power": 5.0}     # BAR 2.5, domina theta
WAKE = {"alpha_power": 10.0, "beta_power": 25.0, "theta_power": 1.0, "delta_power": 1.0}       # BAR 2.5, vigilia


def test_la_regla_bar_exige_un_eeg_de_vigilia_y_lo_declara():
    from domain.physiology.coupling import WAKE_EEG_BASIS, wake_eeg_reason

    assert AROUSAL_TAQUICARDIA_BAR.requires_wake_eeg and "Kane 2017" in WAKE_EEG_BASIS
    assert wake_eeg_reason(WAKE) is None
    assert "no es de vigilia" in wake_eeg_reason(SLEEP)
    assert "bandas" in wake_eeg_reason({"alpha_power": 10.0, "beta_power": 25.0})


def test_un_eeg_de_sueno_con_bar_en_rango_no_acopla_en_la_ruta(sf, pid):
    """Hallazgo de la revisión: «Theta (sueño ligero)» da BAR 2.8–4.1 y 1 de cada 5 veces caía bajo el techo."""
    _save(sf, pid, {"ecg": {"heart_rate": 70.0}}, age_s=10)
    _save(sf, pid, {"eeg": SLEEP})
    with sf() as s:
        r = evaluate_rule_for_patient(s, pid, AROUSAL_TAQUICARDIA_BAR, scenario="healthy")
    assert not r.available and "no es de vigilia" in r.reason


def test_el_motor_no_aplica_la_regla_bar_a_un_eeg_de_sueno(sf, pid):
    from domain.physiology.coupling import VALIDATED_RULES, apply_couplings

    snap = _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "eeg": SLEEP})
    with sf() as s:
        assert apply_couplings(s, snap, VALIDATED_RULES, scenario=None) == []
    snap = _save(sf, pid, {"ecg": {"heart_rate": 70.0}, "eeg": WAKE})
    with sf() as s:
        assert [a.rule_id for a in apply_couplings(s, snap, VALIDATED_RULES, scenario=None)] == [
            "AROUSAL_TAQUICARDIA_BAR"]


@pytest.mark.parametrize("eeg,word", [({"alpha_power": 0.25, "beta_power": 30.0, "theta_power": 1.0,
                                         "delta_power": 1.0}, "techo"), (SLEEP, "vigilia")])
def test_el_compositor_del_gemelo_dice_por_que_no_acopla(sf, pid, eeg, word):
    """Hallazgo de la revisión: con BAR 119 el gemelo decía «el BAR no supera el umbral»."""
    from domain.physiology.state import compose_neuro_cardiac_snapshot

    _save(sf, pid, {"ecg": {"heart_rate": 70.0}}, age_s=10)
    _save(sf, pid, {"eeg": eeg})
    with sf() as s:
        r = compose_neuro_cardiac_snapshot(s, pid)
    assert not r.available and word in r.reason


def test_el_techo_no_se_presenta_como_firmado_y_tiene_su_naturaleza_corta():
    c = AROUSAL_TAQUICARDIA_BAR.condition
    assert c.upper_limit_nature == "Criterio BIOCORE, heurística"
    assert "firmado por Luis" not in c.upper_limit_basis and "pendiente de que Luis confirme" in c.upper_limit_basis
    assert "a lo sumo" not in c.upper_limit_basis


def test_en_la_ruta_un_eeg_de_sueno_dice_que_no_es_de_vigilia():
    from tests.test_ruta_unidades_t4 import _composed, _go, _save_eeg, _start, _texts
    from tests.test_t6_acoplamientos_ruta import _measure_hr

    at = _go(_save_eeg(_start("cerebro"), "Theta (sueño ligero)"), "cerebro", "cierre")
    _measure_hr(at, "cerebro")
    assert _composed(at).state.cardiovascular.get("heart_rate_acoplado") is None
    assert "no es de vigilia" in _texts(at)


def test_el_mensaje_del_techo_se_lee_bien_y_la_nota_avisa_del_ruido():
    from tests.test_ruta_unidades_t4 import _go, _save_eeg, _start, _texts
    from tests.test_t6_acoplamientos_ruta import _measure_hr

    at = _go(_save_eeg(_start("cerebro"), "Beta (activo)"), "cerebro", "cierre")
    _measure_hr(at, "cerebro")
    text = _texts(at)
    assert "(3.0, Criterio BIOCORE, heurística)" in text and "heurística))" not in text and "Test))" not in text
    assert "ratio (adimensional)" not in text
    assert "ruido" in text and "vigilia" in text


def test_la_leyenda_del_eeg_menciona_el_techo_y_la_vigilia():
    import inspect

    import app.instruments.eeg as E

    src = inspect.getsource(E)
    assert "BAR>1.8)" not in src and "techo" in src
