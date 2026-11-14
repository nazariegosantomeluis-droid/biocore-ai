"""Cierre de la fase 0, PARTE E (2026-11-13, Art. I): labs de EEG y EMG.

`stress_perception`, `neuromuscular_efficiency` (copias con otro nombre de `stress_level` y `efficiency`) y
`mental_workload` (= min(100, beta_power), una potencia presentada como escala 0-100) NUNCA en el contrato y retirados
como métricas propias. Lo que depende de un default o de una señal demo de espectro plano no se muestra como número.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from domain.physiology.state.derived_contract import DERIVED_CONTRACT, derived_is_writable

MAIN = str(Path("app/main.py").resolve())


@pytest.mark.parametrize("domain, field", [("neurological", "stress_perception"), ("neurological", "mental_workload"),
                                           ("muscular", "neuromuscular_efficiency")])
def test_the_renamed_copies_are_never_in_the_contract(domain, field):
    rule = DERIVED_CONTRACT[domain][field]
    assert rule.never_reason and rule.inputs == ()
    assert not derived_is_writable(domain, field, {"stress_level", "beta_power", "efficiency", field})


def _emg(view, source="Demo"):
    at = AppTest.from_file(MAIN, default_timeout=240)
    at.session_state["biocore_ai_entry_done"] = True
    at.session_state["selected_hub"] = "Clinical Hub"
    at.session_state["selected_page"] = "🦾 EMG Muscle Lab"
    at.run()
    [r for r in at.sidebar.radio if r.label == "Origen EMG"][0].set_value(source).run()
    radios = [r for r in list(at.radio) + list(at.sidebar.radio) if view in r.options]
    assert radios, "no se encontró el selector de vista"
    radios[0].set_value(view).run()
    assert at.exception == [], at.exception
    return at


def test_emg_lab_demo_signal_does_not_show_a_fatigue_index_number():
    """Sin clave de IA el narrador no dibuja los hallazgos (solo avisa), así que el valor se verifica en la fuente: con
    `source == 'Demo'` el hallazgo `fatigue_index` dice «no disponible con la señal demo», nunca `0/100`."""
    at = _emg("IA")
    text = " ".join(" ".join(str(e.value).split()) for e in list(at.markdown) + list(at.caption) + list(at.info))
    assert not re.search(r"fatigue_index[^a-z]{0,20}\d+/100", text)
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "if source != 'Demo' else 'no disponible con la señal demo'" in source
    assert "Activación muscular" in " ".join(str(e.value) for e in _emg("Clínica").markdown)   # lo medido sí se muestra


def test_emg_lab_save_caption_no_longer_claims_derived_values():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert '"health_score / risk_score / neuromuscular_efficiency / movement_smoothness "' not in source
    assert "sin derivados del organismo (fase 0" in source
    eeg = Path("app/supermodules/eeg_neuro_lab/page_content.py").read_text(encoding="utf-8")
    assert "DEFAULTEADOS (35/65" not in eeg and "ya no deriva NADA del" in eeg
    for lab in (source, eeg):
        for name in ("stress_perception", "mental_workload", "neuromuscular_efficiency"):
            # el nombre solo puede aparecer en comentarios/docstrings que digan que se retiró, nunca en una llamada que
            # lo muestre o lo guarde
            for line in lab.splitlines():
                if name in line:
                    assert "st." not in line and "render_" not in line and "update_from_sensors" not in line, line
