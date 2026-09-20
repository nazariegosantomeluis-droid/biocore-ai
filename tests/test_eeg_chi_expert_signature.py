"""
Arco 2D (2026-09-18) -- firma del experto aplicada al χ aperiódico: cierra
el Arco 2 (2B motor aislado -> 2C elevado al UPS sin interpretar -> 2D
interpretado clínicamente). Transcripción de regla validada, idéntica en
forma al cierre de DAR/TBR en Neuro Tanda 2 (`test_neuro_dar_tbr.py`).

Firma del experto (fuente: Gao R, Peterson EJ, Voytek B. 2017, NeuroImage
158:70-78, "Inferring synaptic excitation/inhibition balance from field
potentials"): χ plano (bajo) -> mayor excitación relativa; χ empinado
(alto) -> mayor inhibición relativa. Cláusula de alcance (honestidad,
Art. I): "índice de E/I cortical por analogía LFP, sobre EEG de
superficie" -- NO "mide E/I" a secas, porque Gao 2017 valida esto sobre
potenciales de campo local (registro intracraneal), no EEG de scalp.

Umbrales VALIDADOS_POR_FUENTE: 🔴 <1.0 excitación · 🔵 1.0-1.6
indeterminado/línea base (el error del instrumento no discrimina) ·
💤 >1.6 inhibición.

BARANDILLA CRÍTICA (no negociable): Arco 2C midió un error de recuperación
de χ de hasta `CHI_INSTRUMENT_ERROR`=0.175 sobre el pipeline de producción
real. Los umbrales firmados respetan ese piso por diseño -- la banda
indeterminada (0.60) es >3x el error. `test_chi_thresholds_never_narrower_
than_instrument_error` graba esto en la suite: nadie puede afilar
`CHI_THRESHOLDS` por debajo del piso del instrumento sin que la suite lo
cace.
"""

from datetime import datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

from domain.physiology.state import (
    DomainState,
    PhysiologicalDescriptor,
    Provenance,
    UnifiedPhysiologicalState,
)
from src.signals.eeg.spectral_model import (
    CHI_APERIODIC_CITATION,
    CHI_CITATION,
    CHI_INSTRUMENT_ERROR,
    CHI_THRESHOLDS,
    classify_chi,
)

_TEST_STATE_KEY = "test_state"


# --- Parte B: clasificación por umbral 🔴/🔵/💤 -------------------------------

def test_classify_chi_thresholds_and_boundaries():
    assert classify_chi(0.8) == ("excitacion", "excitación cortical (hiperexcitabilidad)", "🔴")
    assert classify_chi(1.3) == ("indeterminado", "indeterminado / línea base", "🔵")
    assert classify_chi(1.8) == ("inhibicion", "inhibición cortical (supresión/enlentecimiento)", "💤")
    # fronteras exactas, en el lado documentado: 1.0 -> indeterminado, 1.6 -> indeterminado
    assert classify_chi(1.0)[0] == "indeterminado"
    assert classify_chi(1.6)[0] == "indeterminado"
    # justo fuera de cada frontera
    assert classify_chi(0.999)[0] == "excitacion"
    assert classify_chi(1.601)[0] == "inhibicion"


def test_classify_chi_indeterminate_band_is_an_honest_state_not_a_default_green():
    """La banda 🔵 (1.0-1.6) es un estado clínico legítimo -- "cerca de
    línea base, no discriminable a esta resolución" -- no un verde de
    "todo bien" ni una ausencia disfrazada."""
    nivel, etiqueta, badge = classify_chi(1.3)
    assert nivel == "indeterminado"
    assert badge == "🔵"
    assert "línea base" in etiqueta or "indeterminado" in etiqueta


def test_classify_chi_none_is_no_disponible_not_a_default_state():
    """`None` (χ degradado por los guardianes de 2C, o ausente) ->
    'no disponible', NUNCA un badge por default."""
    assert classify_chi(None) == ("no_disponible", "no disponible", "")


# --- Parte A: VALIDADO_POR_FUENTE, cláusula de alcance, dos citas ----------

def test_citation_is_validated_by_source_pending_validation_retired():
    assert CHI_THRESHOLDS == (1.0, 1.6)
    assert "VALIDADO_POR_FUENTE" in CHI_CITATION
    assert "PENDING_VALIDATION" not in CHI_CITATION
    assert "Gao" in CHI_CITATION
    # cláusula de alcance explícita en el propio texto de la cita -- nunca
    # "mide E/I" a secas
    assert "analogía LFP" in CHI_CITATION
    assert "EEG de superficie" in CHI_CITATION
    assert "mide E/I" not in CHI_CITATION
    # la cita metodológica sigue viva, en su propio eje
    assert "Donoghue" in CHI_APERIODIC_CITATION


# --- Parte D: la barandilla de holgura, grabada en la suite -----------------

def test_chi_thresholds_never_narrower_than_instrument_error():
    """No negociable: ninguna frontera de `CHI_THRESHOLDS` puede quedar
    separada de la siguiente por menos de `CHI_INSTRUMENT_ERROR` -- ese es
    el piso real medido por Arco 2C sobre el pipeline de producción. Si
    alguien afila los umbrales por debajo de este piso, este test debe
    fallar."""
    excitacion_techo, inhibicion_piso = CHI_THRESHOLDS
    gap = inhibicion_piso - excitacion_techo
    assert gap > CHI_INSTRUMENT_ERROR, (
        f"la banda indeterminada ({gap:.3f}) es menor o igual al error del instrumento "
        f"({CHI_INSTRUMENT_ERROR}) -- los umbrales dejarían de vivir sobre la medición real"
    )
    # la firma actual del experto deja margen >3x el error -- documenta la
    # holgura real, no solo el piso absoluto, para que una erosión silenciosa
    # (afilar sin cruzar el piso duro) también se note.
    assert gap >= 3 * CHI_INSTRUMENT_ERROR, (
        f"la banda indeterminada firmada por el experto ({gap:.3f}) ya no guarda el margen "
        f">3x el error de instrumento ({3 * CHI_INSTRUMENT_ERROR:.3f}) -- confirmar que el "
        f"cambio de umbral fue intencional, no una erosión silenciosa"
    )


def test_chi_instrument_error_is_the_2c_measured_floor():
    """`CHI_INSTRUMENT_ERROR` no es un número inventado -- es el error
    máximo de recuperación que Arco 2C midió sobre el pipeline de
    producción real, en el piso exacto de `MIN_CHI_CLEAN_WINDOWS`."""
    assert CHI_INSTRUMENT_ERROR == pytest.approx(0.175)


# --- Persistencia: source_detail lleva VALIDADO_POR_FUENTE + ambas citas ---

def test_chi_persisted_with_scope_clause_in_source_detail():
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from domain.physiology.state import from_digital_twin_organism

    organism = DigitalTwinOrganism()
    organism.update_from_sensors({
        "eeg": {
            "delta_power": 5.0, "theta_power": 8.0, "alpha_power": 20.0,
            "beta_power": 15.0, "gamma_power": 3.0,
            "chi_aperiodic": 0.85,
        }
    })
    state = from_digital_twin_organism(organism, "paciente-2d-test", Provenance.SIMULACION, 0.85)
    detail = state.neurological.descriptors["chi_aperiodic"].source_detail

    assert "VALIDADO_POR_FUENTE" in detail
    assert "PENDING_VALIDATION" not in detail
    assert "Gao" in detail
    assert "Donoghue" in detail
    assert "analogía LFP" in detail


# ---------------------------- AppTest: badge en vivo -------------------------
#
# Mismo patrón que `tests/test_neuro_dar_tbr_badges.py` (Neuro Tanda 2):
# verificado POR EJECUCIÓN vía `AppTest` hasta el final del render, no por
# lectura.

def _neuro_state(descriptors):
    return UnifiedPhysiologicalState(
        patient_id="paciente-chi-badge-test",
        timestamp=datetime.now(timezone.utc),
        cardiovascular=DomainState(domain="cardiovascular"),
        respiratory=DomainState(domain="respiratory"),
        neurological=DomainState(domain="neurological", descriptors=descriptors),
        events=[],
    )


def _descriptor(name, value, unit="exponente (adimensional)"):
    return PhysiologicalDescriptor(name, value, unit, Provenance.SIMULACION, 0.85, "test")


def _run_body(state):
    def _script():
        import streamlit as st
        from app.supermodules.twin_shell.ups_body_visual import render_ups_body
        render_ups_body(st.session_state["test_state"])

    at = AppTest.from_function(_script)
    at.session_state[_TEST_STATE_KEY] = state
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"
    return at


@pytest.mark.parametrize(
    "value, expected_badge, expected_fragment",
    [
        (0.8, "🔴", "excitación cortical"),
        (1.3, "🔵", "indeterminado"),
        (1.8, "💤", "inhibición cortical"),
    ],
)
def test_chi_badge_color_matches_the_signed_threshold(value, expected_badge, expected_fragment):
    state = _neuro_state({"chi_aperiodic": _descriptor("chi_aperiodic", value)})
    at = _run_body(state)
    captions = [c.value for c in at.caption]
    assert any(expected_badge in c and expected_fragment in c for c in captions), captions
    assert any("Gao" in c for c in captions)


def test_chi_indeterminate_band_renders_as_legitimate_state_not_absence():
    """La banda 🔵 se renderiza como CUALQUIER otro badge -- no hay rama
    especial que la esconda o la trate como "sin dato"."""
    state = _neuro_state({"chi_aperiodic": _descriptor("chi_aperiodic", 1.3)})
    at = _run_body(state)
    captions = [c.value for c in at.caption]
    assert any("🔵" in c and "χ" in c for c in captions), captions
    assert not any("no disponible" in c.lower() for c in captions if "χ" in c)


def test_no_chi_badge_when_descriptor_absent_gate_vacio():
    """Sin `chi_aperiodic` en el dominio (gate individual no cumplido, o
    dominio neuro entero vacío) -- ningún badge, nunca un badge fabricado."""
    state = _neuro_state({})  # dominio neuro vacío
    at = _run_body(state)
    captions = [c.value for c in at.caption]
    assert not any("χ" in c for c in captions)


def test_no_state_at_all_renders_without_crash_and_without_chi_badge():
    at = _run_body(None)
    captions = [c.value for c in at.caption]
    assert not any("χ" in c for c in captions)


def test_dar_tbr_badges_intact_alongside_chi():
    """Regresión: el badge nuevo de χ no desplaza ni rompe los de DAR/TBR --
    los tres pueden coexistir en el mismo render."""
    state = _neuro_state({
        "dar": _descriptor("dar", 3.5, unit="ratio (adimensional)"),
        "tbr": _descriptor("tbr", 1.2, unit="ratio (adimensional)"),
        "chi_aperiodic": _descriptor("chi_aperiodic", 1.8),
    })
    at = _run_body(state)
    captions = [c.value for c in at.caption]
    assert any("🔴" in c and "DAR" in c for c in captions)
    assert any("🟢" in c and "TBR" in c for c in captions)
    assert any("💤" in c and "χ" in c for c in captions)
