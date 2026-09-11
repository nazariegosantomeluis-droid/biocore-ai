"""
Capa 5A, dominio neurológico -- Neuro DAR+TBR.

Tanda 1 (2026-09-10): DAR (Delta/Alfa) y TBR (Theta/Beta) replican el arco
del BAR: cociente adimensional de dos band power del mismo electrodo, gate
individual (se persiste solo si ambas bandas están presentes y el cociente
no es indefinido), procedencia del llamador (no `DERIVADO`), y `None`
honesto cuando el denominador es ~0 -- nunca un infinito ni un cero
fabricado. Umbrales clínicos quedaron `PENDING_VALIDATION`.

Tanda 2 (2026-09-10, misma fecha, firma del experto aplicada): los umbrales
pasan a `VALIDADO_POR_FUENTE` -- `DAR_THRESHOLDS`/`TBR_THRESHOLDS = (1.5,
3.0)`, `DAR_CITATION` (Claassen et al. 2004) y `TBR_CITATION` (Boksem et
al. 2005, reemplaza la cita de Monastra 2001 de la Tanda 1 -- constructo
distinto, ver `eeg_analyzer.py`). `classify_dar()`/`classify_tbr()`
mapean el ratio a `(nivel, etiqueta, badge)` 🟢/🟡/🔴, con `None` ->
"no disponible" nunca un verde por default. El motor de cálculo (PSD de
Welch) NO cambió -- los umbrales están definidos sobre ESE motor.
"""

import numpy as np
import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism
from domain.physiology.state import (
    Provenance,
    create_patient,
    from_digital_twin_organism,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
    save_state,
)
from src.signals.eeg import (
    DAR_CITATION,
    DAR_THRESHOLDS,
    TBR_CITATION,
    TBR_THRESHOLDS,
    EegAnalyzer,
    classify_dar,
    classify_tbr,
    delta_alpha_ratio,
    theta_beta_ratio,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "ups_dar_tbr_test.db"


def _session_factory(path):
    engine = make_engine(path)
    init_db(engine)
    return make_session_factory(engine)


# --- Parte A: los ratios en el EegAnalyzer (reusa los band power del BAR) --

def test_delta_alpha_ratio_and_theta_beta_ratio_formulas():
    assert delta_alpha_ratio(4.0, 2.0) == pytest.approx(2.0)
    assert theta_beta_ratio(9.0, 3.0) == pytest.approx(3.0)


def test_delta_alpha_ratio_is_none_on_zero_or_missing_denominator():
    """Honestidad de borde: alpha_power ~0 -> indefinido, NO un infinito."""
    assert delta_alpha_ratio(4.0, 0.0) is None
    assert delta_alpha_ratio(4.0, None) is None
    assert delta_alpha_ratio(None, 2.0) is None


def test_theta_beta_ratio_is_none_on_zero_or_missing_denominator():
    assert theta_beta_ratio(9.0, 0.0) is None
    assert theta_beta_ratio(None, 3.0) is None


def test_eeg_analyzer_computes_bar_dar_tbr_from_the_same_band_power():
    """El analizador no recalcula el PSD tres veces -- `dar`/`tbr` reusan
    los `band_power` que el BAR ya deriva de la señal."""
    fs = 256.0
    t = np.arange(0, 4, 1 / fs)
    signal = 3.0 * np.sin(2 * np.pi * 10 * t) + 0.3 * np.sin(2 * np.pi * 20 * t)  # alfa-dominante
    result = EegAnalyzer(fs=fs).analyze(signal)

    assert result.bar is not None
    assert result.dar is not None
    assert result.tbr is not None
    assert result.dar == pytest.approx(result.band_power["delta"] / result.band_power["alpha"])
    assert result.tbr == pytest.approx(result.band_power["theta"] / result.band_power["beta"])
    # Tanda 2: el finding cita el badge + la etiqueta clínica del umbral
    # firmado, no un aviso de validación pendiente.
    assert "PENDING_VALIDATION" not in result.findings["Delta/Alpha Ratio (DAR)"]
    assert "PENDING_VALIDATION" not in result.findings["Theta/Beta Ratio (TBR)"]


def test_citations_are_validated_by_source_pending_validation_retired():
    """PENDING_VALIDATION retirado (Tanda 2): las citas ahora declaran
    VALIDADO_POR_FUENTE, con los umbrales firmados como tupla (leve, severo)."""
    assert DAR_THRESHOLDS == (1.5, 3.0)
    assert TBR_THRESHOLDS == (1.5, 3.0)
    assert "VALIDADO_POR_FUENTE" in DAR_CITATION
    assert "VALIDADO_POR_FUENTE" in TBR_CITATION
    assert "PENDING_VALIDATION" not in DAR_CITATION
    assert "PENDING_VALIDATION" not in TBR_CITATION
    assert "Claassen" in DAR_CITATION
    assert "Boksem" in TBR_CITATION
    assert "Monastra" not in TBR_CITATION  # cita reemplazada, no coexiste


# --- Parte B: clasificación por umbral 🟢/🟡/🔴 ------------------------------

def test_classify_dar_thresholds_and_boundaries():
    assert classify_dar(1.2) == ("normal", "tejido sano", "🟢")
    assert classify_dar(2.0) == ("leve", "hipoperfusión leve", "🟡")
    assert classify_dar(3.5) == ("severo", "isquemia severa / sufrimiento cortical", "🔴")
    # fronteras exactas, en el lado documentado: 1.5 -> leve, 3.0 -> severo
    assert classify_dar(1.5)[0] == "leve"
    assert classify_dar(3.0)[0] == "severo"


def test_classify_tbr_thresholds_and_boundaries():
    assert classify_tbr(1.2) == ("normal", "enganchado / aprendizaje activo", "🟢")
    assert classify_tbr(2.0) == ("leve", "inicio de fatiga", "🟡")
    assert classify_tbr(3.5) == ("severo", "fatiga cognitiva severa", "🔴")
    assert classify_tbr(1.5)[0] == "leve"
    assert classify_tbr(3.0)[0] == "severo"


def test_classify_dar_and_tbr_none_is_no_disponible_not_a_default_green():
    """La barandilla de siempre: `None` (denominador indefinido, ya gateado
    antes de llegar aquí) -> 'no disponible', NUNCA un verde por default."""
    assert classify_dar(None) == ("no_disponible", "no disponible", "")
    assert classify_tbr(None) == ("no_disponible", "no disponible", "")


# --- Parte B: DAR/TBR persistidos como descriptores neuro (patrón BAR) -----

def test_camino_feliz_bar_dar_tbr_persist_together(db_path):
    """Con las 4 band power necesarias presentes, el snapshot neurológico
    lleva bar + dar + tbr, los tres con la procedencia del llamador y
    unidad 'ratio (adimensional)' -- igual que el BAR."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente DAR+TBR feliz")
        o = DigitalTwinOrganism()
        o.update_from_sensors({
            "eeg": {"delta_power": 5.0, "theta_power": 6.0, "alpha_power": 10.0, "beta_power": 3.0}
        })
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)

        neuro = state.neurological.descriptors
        assert "bar" in neuro and "dar" in neuro and "tbr" in neuro

        assert neuro["dar"].value == pytest.approx(5.0 / 10.0)
        assert neuro["dar"].provenance == Provenance.SIMULACION
        assert neuro["dar"].unit == "ratio (adimensional)"

        assert neuro["tbr"].value == pytest.approx(6.0 / 3.0)
        assert neuro["tbr"].provenance == Provenance.SIMULACION
        assert neuro["tbr"].unit == "ratio (adimensional)"

        assert neuro["bar"].value == pytest.approx(3.0 / 10.0)  # BAR intacto, sin cambio de comportamiento


def test_gate_individual_dar_ausente_sin_delta_power(db_path):
    """Falta `delta_power` (pero hay alpha/beta/theta) -> `dar` ausente,
    `bar` y `tbr` presentes. Cada ratio gateado por SUS PROPIAS bandas, no
    todo-o-nada como el gate del dominio."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente sin delta")
        o = DigitalTwinOrganism()
        o.update_from_sensors({
            "eeg": {"theta_power": 6.0, "alpha_power": 10.0, "beta_power": 3.0}
        })
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)

        neuro = state.neurological.descriptors
        assert "dar" not in neuro          # sin delta_power, indeterminable
        assert "bar" in neuro              # bar solo necesita alpha+beta
        assert "tbr" in neuro              # tbr solo necesita theta+beta


def test_gate_individual_tbr_ausente_sin_beta_power(db_path):
    """Espejo: falta `beta_power` -> `tbr` Y `bar` ausentes (ambos necesitan
    beta), pero `dar` presente (solo necesita delta+alpha)."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente sin beta")
        o = DigitalTwinOrganism()
        o.update_from_sensors({
            "eeg": {"delta_power": 5.0, "theta_power": 6.0, "alpha_power": 10.0}
        })
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)

        neuro = state.neurological.descriptors
        assert "dar" in neuro
        assert "bar" not in neuro
        assert "tbr" not in neuro


def test_denominador_cero_dar_no_se_persiste(db_path):
    """alpha_power = 0 -> el cociente delta/alpha es indefinido -> `dar` NO
    se persiste (ni un inf ni un 0 fabricado). Mismo criterio que el BAR con
    alpha_power=0."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente alpha cero")
        o = DigitalTwinOrganism()
        o.update_from_sensors({
            "eeg": {"delta_power": 5.0, "theta_power": 6.0, "alpha_power": 0.0, "beta_power": 3.0}
        })
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)

        neuro = state.neurological.descriptors
        assert "alpha_power" in neuro      # band power sí (es 0.0, un valor real)
        assert "dar" not in neuro          # cociente indefinido -> no se persiste
        assert "bar" not in neuro          # mismo denominador -> tampoco
        assert "tbr" in neuro              # tbr no depende de alpha -> no afectado


def test_denominador_cero_tbr_no_se_persiste(db_path):
    """Espejo: beta_power = 0 -> `tbr` (theta/beta, beta es EL denominador)
    indefinido -> no se persiste. `bar` (beta/alpha) SÍ se persiste --
    beta_power=0 es su NUMERADOR, un valor real (0.0), no un denominador
    indefinido; `beta_alpha_ratio` solo declara `None` cuando el
    denominador (alpha_power) es ~0, no el numerador. `dar` (no depende de
    beta en absoluto) tampoco se ve afectado."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente beta cero")
        o = DigitalTwinOrganism()
        o.update_from_sensors({
            "eeg": {"delta_power": 5.0, "theta_power": 6.0, "alpha_power": 10.0, "beta_power": 0.0}
        })
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)

        neuro = state.neurological.descriptors
        assert "beta_power" in neuro
        assert "tbr" not in neuro
        assert neuro["bar"].value == pytest.approx(0.0)
        assert "dar" in neuro


def test_validado_por_fuente_visible_in_source_detail_pending_validation_gone(db_path):
    """Tanda 2: el source_detail de dar/tbr declara VALIDADO_POR_FUENTE y la
    cita firmada -- PENDING_VALIDATION ya no aparece. El BAR, con su propia
    validación independiente (arco de acoplamiento), no lleva ninguna de
    las dos marcas en su source_detail -- no le pertenece este vocabulario."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente VALIDADO_POR_FUENTE")
        o = DigitalTwinOrganism()
        o.update_from_sensors({
            "eeg": {"delta_power": 5.0, "theta_power": 6.0, "alpha_power": 10.0, "beta_power": 3.0}
        })
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)

        neuro = state.neurological.descriptors
        assert "VALIDADO_POR_FUENTE" in neuro["dar"].source_detail
        assert "PENDING_VALIDATION" not in neuro["dar"].source_detail
        assert "delta_alpha_ratio" in neuro["dar"].source_detail
        assert "Claassen" in neuro["dar"].source_detail

        assert "VALIDADO_POR_FUENTE" in neuro["tbr"].source_detail
        assert "PENDING_VALIDATION" not in neuro["tbr"].source_detail
        assert "theta_beta_ratio" in neuro["tbr"].source_detail
        assert "Boksem" in neuro["tbr"].source_detail
        assert "Monastra" not in neuro["tbr"].source_detail  # cita retirada, no coexiste

        # el BAR no lleva ninguna de las dos marcas -- validación independiente
        assert "PENDING_VALIDATION" not in neuro["bar"].source_detail
        assert "VALIDADO_POR_FUENTE" not in neuro["bar"].source_detail


def test_dar_tbr_survive_persistence_round_trip(db_path):
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente DAR+TBR Roundtrip")
        o = DigitalTwinOrganism()
        o.update_from_sensors({
            "eeg": {"delta_power": 5.0, "theta_power": 6.0, "alpha_power": 10.0, "beta_power": 3.0}
        })
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.9)
        save_state(session, state)

    with SessionLocal() as session:  # sesión distinta -- simula proceso nuevo
        latest = get_latest_state(session, patient_id)
    assert latest.neurological.get("dar").value == pytest.approx(0.5)
    assert latest.neurological.get("tbr").value == pytest.approx(2.0)
    assert "VALIDADO_POR_FUENTE" in latest.neurological.get("dar").source_detail


def test_no_neuro_input_still_yields_empty_domain_dar_tbr_included(db_path):
    """El gate del dominio (`has_real_neuro_input`) sin cambios -- sin
    alpha_power NI beta_power, el dominio entero (incluidos dar/tbr) queda
    vacío, nunca poblado parcialmente por sorpresa."""
    SessionLocal = _session_factory(db_path)
    with SessionLocal() as session:
        patient_id = create_patient(session, display_name="Paciente sin neuro")
        o = DigitalTwinOrganism()
        o.update_from_sensors({"ecg": {"heart_rate": 70.0}})
        state = from_digital_twin_organism(o, patient_id, Provenance.SIMULACION, 0.85)
        assert state.neurological.descriptors == {}
