"""
Mu ERD Tanda 2 (2026-09-26) -- el fenómeno ERD se vuelve visible en el EEG
Neuro Lab: patrón `motor_imagery` seleccionable, curva temporal de potencia
mu con la caída marcada, rótulo de alcance PROMINENTE (mismo peso que la
cláusula de χ), degradación honesta si el detector no puede medir. Cierra
el arco Mu ERD en su versión (c): demostrador del principio del BCI,
mono-canal, sin lateralidad.

Verificado por ejecución (AppTest hasta el final del render), la
barandilla de siempre -- incluida la aserción central de honestidad: la
cláusula de alcance debe aparecer COMPLETA, no truncada, en la UI.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

import src.signals.eeg.erd_detector as erd_detector_module
from src.signals.eeg.erd_detector import MU_ERD_SCOPE_NOTE, ErdResult


@pytest.fixture
def eeg_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "eeg_mu_erd_visualization_test.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente Mu ERD Tanda 2 (test)")
    return sf, pid


def _run_eeg_lab(eeg_ups):
    sf, pid = eeg_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    return at


def _select_pattern(at, label):
    selector = next(s for s in at.sidebar.selectbox if s.label == "Patrón EEG")
    selector.set_value(label)
    at.run(timeout=30)
    return at


# --- Parte A: el patrón seleccionable ---------------------------------------

def test_motor_imagery_pattern_is_selectable_and_renders_without_exception(eeg_ups):
    at = _run_eeg_lab(eeg_ups)
    options = next(s for s in at.sidebar.selectbox if s.label == "Patrón EEG").options
    assert "Motor Imagery (ERD)" in options

    at = _select_pattern(at, "Motor Imagery (ERD)")
    assert at.exception == [], f"excepción en el render: {at.exception}"


def test_motor_imagery_reveals_its_two_honest_controls(eeg_ups):
    """Profundidad y momento del evento -- los únicos dos parámetros que
    Parte A pidió exponer, y solo cuando el patrón está seleccionado (no
    ruido de control visible para los otros 7 patrones)."""
    at = _run_eeg_lab(eeg_ups)
    sidebar_labels_before = [s.label for s in at.sidebar.slider]
    assert "Profundidad del ERD (%)" not in sidebar_labels_before
    assert "Momento del evento (s)" not in sidebar_labels_before

    at = _select_pattern(at, "Motor Imagery (ERD)")
    sidebar_labels_after = [s.label for s in at.sidebar.slider]
    assert "Profundidad del ERD (%)" in sidebar_labels_after
    assert "Momento del evento (s)" in sidebar_labels_after


# --- Parte B: la visualización temporal -------------------------------------

def test_erd_section_appears_only_when_motor_imagery_is_selected(eeg_ups):
    at = _run_eeg_lab(eeg_ups)  # default pattern: Alpha (relajado)
    markdown_text = " ".join(md.value for md in at.main.markdown)
    assert "Desincronización de banda Mu" not in markdown_text, (
        "el panel de ERD no debe aparecer para un patrón que no es motor_imagery"
    )

    at = _select_pattern(at, "Motor Imagery (ERD)")
    markdown_text = " ".join(md.value for md in at.main.markdown)
    assert "Desincronización de banda Mu" in markdown_text
    assert at.exception == []


def test_erd_percent_responds_to_the_depth_slider_not_a_disconnected_number(eeg_ups):
    """Anti-placebo (mismo criterio que ya validó los sliders HR/SpO2 de
    Multisensor en la Consolidación Visual): el ERD% mostrado debe moverse
    de verdad cuando se mueve la profundidad inyectada, no ser un número
    fijo desconectado del cálculo real. El ruido del generador no está
    sembrado (sin `np.random.seed` expuesto en la UI) -- el margen de 30pp
    entre 20% y 85% de profundidad inyectada es muy holgado frente al
    error máximo medido en Tanda 1 (<3.2pp por depth, 15 semillas).

    NOTA DE MÉTODO: la referencia del slider se OBTIENE DE NUEVO antes de
    cada `set_value()` -- reusar la misma referencia entre dos reruns no
    propaga el segundo valor en esta versión de `AppTest` (confirmado
    empíricamente: la señal quedaba generada con la profundidad VIEJA en
    el segundo run, dando una falsa alarma de "no responde")."""
    at = _run_eeg_lab(eeg_ups)
    at = _select_pattern(at, "Motor Imagery (ERD)")

    depth_slider = next(s for s in at.sidebar.slider if s.label == "Profundidad del ERD (%)")
    depth_slider.set_value(20)
    at.run(timeout=30)
    assert at.exception == []
    # El ERD% vive en la tarjeta de métrica (markdown), no en el caption.
    metric_text_low = " ".join(md.value for md in at.main.markdown if "ERD (mu) recuperado" in md.value)
    assert metric_text_low, "no se encontró la tarjeta de ERD recuperado"

    depth_slider = next(s for s in at.sidebar.slider if s.label == "Profundidad del ERD (%)")
    depth_slider.set_value(85)
    at.run(timeout=30)
    assert at.exception == []
    metric_text_high = " ".join(md.value for md in at.main.markdown if "ERD (mu) recuperado" in md.value)

    import re
    low_value = float(re.search(r"(-?\d+\.\d+)%", metric_text_low).group(1))
    high_value = float(re.search(r"(-?\d+\.\d+)%", metric_text_high).group(1))
    assert high_value - low_value > 30.0, (
        f"el ERD% debe responder de verdad a la profundidad inyectada -- bajo={low_value}, alto={high_value}"
    )


def test_curve_renders_without_exception_for_several_event_times(eeg_ups):
    """Barrido del control de timing -- la curva (Plotly, sin accesor de
    inspección de datos en AppTest) debe construirse sin excepción en todo
    el rango del slider, incluidos los extremos."""
    at = _run_eeg_lab(eeg_ups)
    at = _select_pattern(at, "Motor Imagery (ERD)")
    bounds_slider = next(s for s in at.sidebar.slider if s.label == "Momento del evento (s)")
    values = (bounds_slider.min, (bounds_slider.min + bounds_slider.max) / 2, bounds_slider.max)

    for value in values:
        # Refetch antes de cada `set_value()` -- ver nota de método en
        # `test_erd_percent_responds_to_the_depth_slider_not_a_disconnected_number`.
        event_slider = next(s for s in at.sidebar.slider if s.label == "Momento del evento (s)")
        event_slider.set_value(value)
        at.run(timeout=30)
        assert at.exception == [], f"excepción con motor_event_time={value}: {at.exception}"


# --- Parte C: el rótulo de alcance, la aserción central de honestidad ------

def test_scope_note_appears_verbatim_and_not_truncated(eeg_ups):
    """LA aserción de honestidad de esta tanda: la cláusula de alcance
    debe aparecer en la UI COMPLETA -- ni truncada, ni parafraseada, ni
    relegada a un tooltip que nadie abre."""
    at = _run_eeg_lab(eeg_ups)
    at = _select_pattern(at, "Motor Imagery (ERD)")
    assert at.exception == []

    warning_text = " ".join(w.value for w in at.main.warning)
    assert MU_ERD_SCOPE_NOTE in warning_text, (
        "la cláusula de alcance completa debe aparecer, verbatim, en un elemento prominente (st.warning)"
    )
    assert "lateralidad" in warning_text

    # También viaja como citation de la tarjeta de métrica -- mismo peso
    # visual que ya recibe CHI_CITATION (Parte C: "mismo peso que la
    # cláusula de alcance del χ").
    metric_text = " ".join(md.value for md in at.main.markdown if "ERD (mu) recuperado" in md.value)
    assert MU_ERD_SCOPE_NOTE in metric_text


def test_scope_note_is_prominent_not_a_tiny_footnote():
    """Verificación de estilo (no solo de contenido): se usa `st.warning`,
    el mismo tipo de elemento con peso visual que el resto de la app usa
    para avisos que no deben perderse -- no `st.caption` (el texto
    pequeño ya usado para notas secundarias en esta misma página)."""
    src = open("app/supermodules/eeg_neuro_lab/page_content.py", encoding="utf-8").read()
    assert 'st.warning(f"**Alcance de esta demostración:** {MU_ERD_SCOPE_NOTE}")' in src


# --- Degradación honesta -----------------------------------------------------

def test_declines_honestly_instead_of_fabricating_a_curve(eeg_ups):
    """Detector forzado a `available=False` (monkeypatch sobre el módulo
    origen, no sobre `page_content` -- éste corre vía `runpy.run_path()`,
    en un namespace fresco que no es `sys.modules`, así que el punto de
    parcheo correcto es `src.signals.eeg.erd_detector.detect_mu_erd`, de
    donde `page_content.py` hace `from ... import detect_mu_erd` en cada
    ejecución). La UI debe mostrar el motivo, nunca una curva o un ERD%
    inventados."""

    def _fake_detect_mu_erd(*args, **kwargs):
        return ErdResult(False, None, None, None, kwargs.get("t_event"), "MOTIVO DE PRUEBA FORZADO")

    with patch.object(erd_detector_module, "detect_mu_erd", _fake_detect_mu_erd):
        at = _run_eeg_lab(eeg_ups)
        at = _select_pattern(at, "Motor Imagery (ERD)")
        assert at.exception == []

        info_text = " ".join(i.value for i in at.main.info)
        assert "ERD no disponible: MOTIVO DE PRUEBA FORZADO" in info_text

        metric_text = " ".join(md.value for md in at.main.markdown if "ERD (mu) recuperado" in md.value)
        assert "MOTIVO DE PRUEBA FORZADO" in metric_text, (
            "la tarjeta de métrica también debe declarar el motivo (unavailable_reason), no un número"
        )
        # Nunca un porcentaje inventado en el degradado.
        import re
        assert not re.search(r"ERD \(mu\) recuperado.*?\d+\.\d+%", metric_text)


def test_import_guard_exists_for_when_the_erd_module_itself_is_unavailable():
    """El otro camino de degradación (módulo entero sin importar, no solo
    un resultado declinado): mismo patrón defensivo que `spectral_model`
    (`SpectralModel_import_error`/`fit_aperiodic_component=None`) ya usa en
    este archivo -- confirmado por lectura de código, no por ejecución:
    forzar un `ImportError` real de un módulo ya cargado en `sys.modules`
    (por los tests de arriba, en el mismo proceso) no es representativo de
    un entorno donde `erd_detector` de verdad no resuelve."""
    src = open("app/supermodules/eeg_neuro_lab/page_content.py", encoding="utf-8").read()
    assert "ErdDetector_import_error" in src
    assert "except ImportError as e:\n    detect_mu_erd = None" in src
    assert "detect_mu_erd is None or compute_mu_power_timeseries is None" in src
    assert "render_error_state" in src.split("detect_mu_erd is None or compute_mu_power_timeseries is None")[1][:200]


# --- El resto del EEG Lab, intacto ------------------------------------------

def test_other_patterns_and_dar_tbr_chi_are_unaffected(eeg_ups):
    """Regresión de superficie: los otros patrones siguen sin el panel de
    ERD, y DAR/TBR/BAR/χ (que viven en col2, sin relación con esta tanda)
    siguen renderizando igual que antes."""
    at = _run_eeg_lab(eeg_ups)
    dur_slider = next(s for s in at.sidebar.slider if s.label == "Duración (segundos)")
    dur_slider.set_value(90)
    at.run(timeout=30)
    assert at.exception == []

    markdown_text = " ".join(md.value for md in at.main.markdown)
    assert "Desincronización de banda Mu" not in markdown_text
    assert "DAR (Delta" in markdown_text or "TBR (Theta" in markdown_text

    for label in ("Beta (activo)", "Seizure (espigas)", "Artifact (parpadeo)"):
        at = _select_pattern(at, label)
        assert at.exception == [], f"excepción con patrón {label}: {at.exception}"
        markdown_text = " ".join(md.value for md in at.main.markdown)
        assert "Desincronización de banda Mu" not in markdown_text
