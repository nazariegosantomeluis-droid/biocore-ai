"""
Acoplamientos (b) Tanda 2 -- el acoplamiento neuro->CV dispara EN VIVO
desde el botón 3a de Twin OS. Verificado POR EJECUCIÓN vía AppTest hasta
el final del render (la barandilla de la Fase 2.2: el recon ha mentido
antes -- "renderiza" cuando crasheaba).
"""

from datetime import datetime, timedelta, timezone

import pytest
from streamlit.testing.v1 import AppTest

from domain.physiology.state import (
    DomainState,
    PhysiologicalDescriptor,
    Provenance,
    UnifiedPhysiologicalState,
    create_patient,
    get_state_by_snapshot_id,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)
from domain.physiology.state import composer as composer_mod

_SF_KEY = "twin_shell_ups_session_factory"
_PID_KEY = "twin_shell_ups_patient_id"


@pytest.fixture
def seeded(tmp_path):
    """Devuelve (session_factory, patient_id, seed_fn). `seed_fn` persiste
    los snapshots que cada test necesita antes de renderizar el botón."""
    engine = make_engine(tmp_path / "composer_btn.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente continuo (test)")

    def _state(ts, *, cardio=None, neuro=None):
        return UnifiedPhysiologicalState(
            patient_id=pid, timestamp=ts,
            cardiovascular=DomainState(domain="cardiovascular", descriptors=cardio or {}),
            respiratory=DomainState(domain="respiratory", descriptors={}),
            neurological=DomainState(domain="neurological", descriptors=neuro or {}),
            events=[],
        )

    def seed_fn(*, hr=None, hr_age_s=None, bar=None):
        now = datetime.now(timezone.utc)
        with sf() as s:
            if hr is not None:
                d = PhysiologicalDescriptor("heart_rate", hr, "bpm", Provenance.SENSOR_REAL, 0.9, "ecg_lab:SENSOR_REAL")
                save_state(s, _state(now - timedelta(seconds=hr_age_s or 30), cardio={"heart_rate": d}))
            if bar is not None:
                d = PhysiologicalDescriptor(
                    "bar", bar, "ratio (adimensional)", Provenance.SIMULACION, 0.75,
                    "beta_alpha_ratio | Schutter DJLG 2006",
                )
                save_state(s, _state(now, neuro={"bar": d}))

    return sf, pid, seed_fn


def _run_button(sf, pid):
    """Renderiza `render_neuro_cardiac_composer()` con el paciente continuo
    apuntado a la BD de test, pulsa el botón, y devuelve el AppTest tras el
    re-render. Verifica que llega al final del render SIN excepción en
    ambas pasadas."""
    def _script():
        from app.supermodules.twin_shell.pages import render_neuro_cardiac_composer
        render_neuro_cardiac_composer()

    at = AppTest.from_function(_script)
    at.session_state[_SF_KEY] = sf
    at.session_state[_PID_KEY] = pid
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el primer render: {at.exception}"
    at.button[0].click().run(timeout=30)
    assert at.exception == [], f"excepción tras pulsar el botón: {at.exception}"
    return at


# --- EL test que importa: disparo en vivo ---------------------------------

def test_button_fires_the_coupling_live_end_to_end(seeded):
    sf, pid, seed = seeded
    seed(hr=72.0, hr_age_s=40, bar=2.6)  # BAR > 1.8, FC dentro de ventana

    at = _run_button(sf, pid)

    # la UI confirmó la composición, sin fingir
    assert len(at.success) == 1
    assert "compuesto" in at.success[0].value.lower()
    assert not at.info  # no hubo "no se pudo componer"

    # el snapshot combinado existe con las TRES procedencias distintas
    with sf() as s:
        # el compuesto es el más reciente
        from domain.physiology.state import get_latest_state
        composed = get_latest_state(s, pid)
    cv = composed.cardiovascular.descriptors
    assert cv["heart_rate"].value == pytest.approx(72.0)
    assert cv["heart_rate"].provenance == Provenance.ARRASTRE_TEMPORAL
    assert cv["heart_rate_acoplado"].value == pytest.approx(87.0)          # 72 + 15
    assert cv["heart_rate_acoplado"].provenance == Provenance.DERIVADO_ACOPLAMIENTO
    assert composed.neurological.descriptors["bar"].value == pytest.approx(2.6)
    assert composed.neurological.descriptors["bar"].provenance == Provenance.SIMULACION
    # y la caption honesta menciona el disparo
    assert any("AROUSAL_TAQUICARDIA_BAR" in c.value for c in at.caption)
    assert any("87" in c.value for c in at.caption)


# --- No-op honesto: arousal insuficiente -------------------------------

def test_button_composes_but_does_not_force_coupling_when_bar_low(seeded):
    sf, pid, seed = seeded
    seed(hr=70.0, hr_age_s=15, bar=1.1)  # BAR <= 1.8

    at = _run_button(sf, pid)

    assert len(at.success) == 1
    with sf() as s:
        from domain.physiology.state import get_latest_state
        composed = get_latest_state(s, pid)
    assert "heart_rate" in composed.cardiovascular.descriptors
    assert "heart_rate_acoplado" not in composed.cardiovascular.descriptors  # regla NO disparó
    assert any("sin acoplamiento" in c.value.lower() for c in at.caption)


# --- Los tres no-disponibles: reason en la UI, sin crash, sin éxito -----

@pytest.mark.parametrize(
    "seed_kwargs, expected_reason_fragment",
    [
        (dict(hr=72.0, hr_age_s=30),                 "sin BAR persistido"),
        (dict(bar=2.5),                              "sin FC medida persistida"),
        (dict(hr=72.0, hr_age_s=300, bar=2.5),       "demasiado vieja"),
    ],
)
def test_button_shows_reason_on_unavailable_without_crash(seeded, seed_kwargs, expected_reason_fragment):
    sf, pid, seed = seeded
    seed(**seed_kwargs)

    at = _run_button(sf, pid)

    assert at.success == []                                   # NO éxito fingido
    assert len(at.info) == 1
    assert "no se pudo componer" in at.info[0].value.lower()
    assert expected_reason_fragment in at.info[0].value
    # nada acoplado se persistió
    with sf() as s:
        from domain.physiology.state import get_latest_state
        latest = get_latest_state(s, pid)
    if latest is not None:
        assert "heart_rate_acoplado" not in latest.cardiovascular.descriptors


# --- scenario=None es estructural (verificado por ejecución) ------------

def test_composer_always_passes_scenario_none_to_apply_couplings(seeded, monkeypatch):
    """El paciente continuo nunca lleva un SimulationScenario (los 12 corren
    solo sobre pacientes efímeros). Se captura el kwarg real que el
    compositor le pasa a apply_couplings."""
    sf, pid, seed = seeded
    seed(hr=72.0, hr_age_s=20, bar=2.4)

    captured = {}
    # el compositor hace `from domain.physiology.coupling import apply_couplings`
    # PEREZOSO dentro de la función -> parchear el atributo del paquete basta.
    import domain.physiology.coupling as coupling_pkg
    orig = coupling_pkg.apply_couplings

    def spy(session, snapshot_id, rules, *, scenario):
        captured["scenario"] = scenario
        return orig(session, snapshot_id, rules, scenario=scenario)

    monkeypatch.setattr(coupling_pkg, "apply_couplings", spy)

    with sf() as s:
        composer_mod.compose_neuro_cardiac_snapshot(s, pid)

    assert "scenario" in captured
    assert captured["scenario"] is None
