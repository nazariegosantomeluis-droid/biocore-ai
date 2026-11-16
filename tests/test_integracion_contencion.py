"""Integración tanda 2 + main (Miguel), PARTE B (2026-11-16): contención antes de la prueba con estudiantes.

- ECG-12: ninguna indicación de tratamiento en la lectura de ningún escenario (Miguel retiró las «recomendaciones» del
  analizador viejo; esta guardia impide que vuelvan).
- Caso clínico del gemelo: funciona SIN clave de IA; la corrección es determinista (escenario cargado + evidencia con
  fuente); la IA solo añade una narración opcional y rotulada.
"""

import re

import pytest
from streamlit.testing.v1 import AppTest

from src.signals.ecg.twelve_lead_synth import SCENARIOS

# Indicaciones de tratamiento o de conducta que aparecían en el analizador viejo («Activar protocolo STEMI», «iniciar
# aspirina, heparina»...) y en otros textos del repositorio sin cita (barrido del 2026-11-16).
TREATMENT = re.compile(
    r"aspirina|heparina|atropina|adenosina|cardiovers|trombol|fibrinol|anticoagul|betabloq|amiodaron|reperfusi|"
    r"cateterismo|angioplast|\bICP\b|\bPCI\b|desfibril|recomendaci|acci[oó]n cl[ií]nica|"
    r"iniciar (?:manejo|tratamiento)|activar protocolo|derivaci[oó]n cardiol|considere|considerar",
    re.IGNORECASE,
)


def _report_texts(at):
    out = [m.value for m in at.markdown] + [c.value for c in at.caption]
    out += [x.value for kind in ("info", "warning", "error", "success") for x in getattr(at, kind)]
    out += [e.label for e in at.expander]
    return " ".join(out)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_twelve_lead_reading_never_indicates_a_treatment(scenario):
    def _script(scenario):
        from app.supermodules.ecg_12.report_view import render_twelve_lead_report
        from src.signals.ecg.twelve_lead_measure import analyze_twelve_lead
        from src.signals.ecg.twelve_lead_synth import generate_twelve_lead

        leads, truth = generate_twelve_lead(scenario, 75.0)
        render_twelve_lead_report(analyze_twelve_lead(leads), truth)

    at = AppTest.from_function(_script, args=(scenario,), default_timeout=120).run()
    assert not at.exception, at.exception
    hits = TREATMENT.findall(_report_texts(at))
    assert hits == [], (scenario, hits)


def test_the_treatment_guard_catches_what_the_old_analyzer_said():
    for old in ("Activar protocolo STEMI y priorizar reperfusión inmediata.",
                "Evaluar control de frecuencia y considerar anticoagulación según CHA2DS2-VASc.",
                "Iniciar manejo urgente de taquiarritmia ventricular", "Recomendaciones Clínicas"):
        assert TREATMENT.search(old), old
