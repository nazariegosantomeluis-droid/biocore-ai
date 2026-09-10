"""
Capa 5A dominio muscular, Tanda 3 (cierre) -- el EMG Lab escribe al UPS por
PRIMERA VEZ. Verificado POR EJECUCIÓN vía AppTest hasta el final del render
(la barandilla de la Fase 2.2: el recon ha mentido antes -- Respiratory
rendía "funcional" mientras crasheaba).

El test que importa: `test_emg_lab_writes_analyzed_activation_not_slider` --
el botón alimenta el organismo con la `activation` MEDIDA por `EmgAnalyzer`
sobre señal filtrada, no con el default del slider "Fatiga muscular" de
Twin OS.
"""

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from domain.physiology.state import (
    Provenance,
    create_patient,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
)
from src.signals.emg import EmgAnalyzer

_SF_KEY = "twin_shell_ups_session_factory"
_PID_KEY = "twin_shell_ups_patient_id"

# Señal EMG determinista (el generador demo real usa np.random SIN semilla,
# así que lo parcheamos para poder recomputar exactamente lo que el
# EmgAnalyzer verá).
_FS = 1000
_RNG = np.random.default_rng(20260910)
_FIXED_EMG = (
    (0.6 + 0.2 * np.sin(2 * np.pi * 0.5 * np.arange(_FS * 15) / _FS))
    * _RNG.standard_normal(_FS * 15)
    + 0.05 * np.sin(100 * np.pi * np.arange(_FS * 15) / _FS)
).astype(float)


@pytest.fixture
def ups(tmp_path):
    engine = make_engine(tmp_path / "emg_lab_twin.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente EMG Lab (test)")
    return sf, pid


def _run_emg_page(sf, pid, *, monkeypatch, fixed_signal=_FIXED_EMG):
    """Renderiza `render_emg_page()` (Origen=Demo por default -> señal
    determinista parcheada, vista=Clínica por default) apuntando el paciente
    único a la BD de test. Devuelve el AppTest tras el render inicial,
    habiendo comprobado que llega al final SIN excepción."""
    import app.main as main_mod

    if fixed_signal is not None:
        monkeypatch.setattr(main_mod, "generate_demo_emg_signal", lambda fs, dur, pat: fixed_signal)

    def _script():
        import app.main as m
        m.render_emg_page()

    at = AppTest.from_function(_script)
    at.session_state[_SF_KEY] = sf
    at.session_state[_PID_KEY] = pid
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render inicial: {at.exception}"
    return at


def _find_save_button(at):
    for b in at.button:
        if b.key == "emg_lab_save_to_ups":
            return b
    raise AssertionError(f"botón emg_lab_save_to_ups no encontrado; botones: {[b.key for b in at.button]}")


# --- EL test que importa: escritura en vivo con activation analizada -------

def test_emg_lab_writes_analyzed_activation_not_slider(ups, monkeypatch):
    sf, pid = ups
    at = _run_emg_page(sf, pid, monkeypatch=monkeypatch)

    # sin snapshot antes de pulsar
    with sf() as s:
        assert get_latest_state(s, pid) is None

    _find_save_button(at).click().run(timeout=30)
    assert at.exception == [], f"excepción tras pulsar Guardar: {at.exception}"
    assert len(at.success) == 1
    assert "guardado al gemelo" in at.success[0].value.lower()

    with sf() as s:
        state = get_latest_state(s, pid)
    assert state is not None, "el lab no persistió ningún snapshot"

    muscular = state.muscular.descriptors
    expected = EmgAnalyzer(_FS).analyze(_FIXED_EMG)

    # activation persistida == la del analizador (señal filtrada), NO el
    # default 45 de `_update_muscles()` ni ningún slider.
    assert muscular["activation"].value == pytest.approx(expected.activation_pct)
    assert muscular["activation"].value != pytest.approx(45.0)
    assert muscular["activation"].provenance == Provenance.SIMULACION
    assert muscular["activation"].unit == "%"

    assert muscular["median_frequency"].value == pytest.approx(expected.median_frequency_hz)
    assert muscular["median_frequency"].provenance == Provenance.SIMULACION

    # derivados DERIVADO, sin fatigue_index, sin fantasma
    for d in ("health_score", "risk_score", "neuromuscular_efficiency", "movement_smoothness"):
        assert muscular[d].provenance == Provenance.DERIVADO
    assert "fatigue_index" not in muscular
    assert "recruitment_pattern" not in muscular
    assert "motor_symmetry" not in muscular
    assert "power_output" not in muscular

    # es un snapshot puramente muscular -- el lab no envía otro dominio
    assert state.cardiovascular.descriptors == {}
    assert state.respiratory.descriptors == {}
    assert state.neurological.descriptors == {}


# --- Gate honesto en vivo: CSV sin archivo -------------------------------

def test_emg_lab_declares_no_signal_instead_of_faking_save(ups, monkeypatch):
    sf, pid = ups

    import app.main as main_mod

    def _script():
        import app.main as m
        m.render_emg_page()

    at = AppTest.from_function(_script)
    at.session_state[_SF_KEY] = sf
    at.session_state[_PID_KEY] = pid
    # Origen=CSV, ningún archivo -> signal is None
    at.run(timeout=30)
    # cambiar el radio de Origen a CSV y re-render
    origen = next(r for r in at.radio if r.label == "Origen EMG")
    origen.set_value("CSV").run(timeout=30)
    assert at.exception == [], f"excepción con Origen=CSV: {at.exception}"

    # el botón declara "sin señal", no finge; no hay botón de guardar activo
    assert any("sin señal emg analizable" in i.value.lower() for i in at.info)
    assert not any(b.key == "emg_lab_save_to_ups" for b in at.button)

    # y nada se persistió
    with sf() as s:
        assert get_latest_state(s, pid) is None


# --- Regresión: el dominio muscular sobrevive el round-trip del lab ------

def test_emg_lab_snapshot_round_trips(ups, monkeypatch):
    sf, pid = ups
    at = _run_emg_page(sf, pid, monkeypatch=monkeypatch)
    _find_save_button(at).click().run(timeout=30)
    assert at.exception == []

    # sesión nueva -- simula proceso distinto releyendo lo que el lab escribió
    with sf() as s:
        latest = get_latest_state(s, pid)
    assert "muscular" in latest.all_domains()
    assert latest.muscular.get("activation") is not None
    assert latest.muscular.get("median_frequency") is not None
    assert "fatigue_index" not in latest.muscular.descriptors
