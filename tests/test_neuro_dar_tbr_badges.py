"""
Neuro Tanda 2 (firma del experto, 2026-09-10) -- badges clínicos 🟢/🟡/🔴
para DAR/TBR en el Cuerpo Digital (`ups_body_visual.py`). Verificado POR
EJECUCIÓN vía `AppTest` hasta el final del render, no por lectura.
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

_TEST_STATE_KEY = "test_state"


def _neuro_state(descriptors):
    return UnifiedPhysiologicalState(
        patient_id="paciente-badge-test",
        timestamp=datetime.now(timezone.utc),
        cardiovascular=DomainState(domain="cardiovascular"),
        respiratory=DomainState(domain="respiratory"),
        neurological=DomainState(domain="neurological", descriptors=descriptors),
        events=[],
    )


def _descriptor(name, value, unit="ratio (adimensional)"):
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


def test_dar_badge_renders_with_correct_color_and_citation():
    state = _neuro_state({"dar": _descriptor("dar", 3.5)})  # >=3.0 -> severo
    at = _run_body(state)
    captions = [c.value for c in at.caption]
    assert any("🔴" in c and "DAR" in c and "isquemia severa" in c for c in captions)
    assert any("Claassen" in c for c in captions)


def test_tbr_badge_renders_with_correct_color_and_citation():
    state = _neuro_state({"tbr": _descriptor("tbr", 1.2)})  # <1.5 -> normal
    at = _run_body(state)
    captions = [c.value for c in at.caption]
    assert any("🟢" in c and "TBR" in c and "enganchado" in c for c in captions)
    assert any("Boksem" in c for c in captions)


@pytest.mark.parametrize(
    "value, expected_badge, expected_fragment",
    [
        (1.2, "🟢", "tejido sano"),
        (2.0, "🟡", "hipoperfusión leve"),
        (3.5, "🔴", "isquemia severa"),
    ],
)
def test_dar_badge_color_matches_the_signed_threshold(value, expected_badge, expected_fragment):
    state = _neuro_state({"dar": _descriptor("dar", value)})
    at = _run_body(state)
    captions = [c.value for c in at.caption]
    assert any(expected_badge in c and expected_fragment in c for c in captions), captions


def test_no_badge_when_descriptor_absent_gate_vacio():
    """Sin `dar`/`tbr` en el dominio (gate individual no cumplido, o
    dominio neuro entero vacío) -- ningún badge, nunca un verde fabricado."""
    state = _neuro_state({})  # dominio neuro vacío
    at = _run_body(state)
    captions = [c.value for c in at.caption]
    assert not any("DAR" in c for c in captions)
    assert not any("TBR" in c for c in captions)


def test_no_state_at_all_renders_without_crash_and_without_badges():
    """`state=None` (paciente sin snapshot todavía) -- cuerpo neutro, sin
    excepción, sin badges de ratios que no existen."""
    at = _run_body(None)
    captions = [c.value for c in at.caption]
    assert not any("DAR" in c for c in captions)
    assert not any("TBR" in c for c in captions)
