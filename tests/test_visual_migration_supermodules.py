"""
Consolidación Visual, Tanda 3 (2026-09-21) -- Agente A: migración de los 3
supermodules con `<style>` propio (`ecg_12`, `eeg_neuro_lab`,
`respiratory_lab`) sobre el sistema central (`app/utils/design_system.py`,
congelado desde Tandas 1/2 -- solo-lectura para esta tanda). Verificado
POR EJECUCIÓN vía AppTest hasta el final del render, la barandilla de
siempre.

Tres barandillas duras de esta tanda: `design_system.py` no se tocó;
`validation=None` en los tres `render_module_header()` (ningún nivel de
confianza asignado -- decisión que le corresponde al experto, aparte);
cero cambio de cálculo (solo se re-empaquetó CÓMO se pinta cada valor).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.utils.design_system import PALETTE
from src.signals.eeg.eeg_analyzer import classify_dar, classify_tbr
from src.signals.eeg.spectral_model import classify_chi


# --- Render sin excepción, los 3 labs ---------------------------------------

def test_ecg_12_renders_without_exception():
    def _script():
        import app.supermodules.ecg_12.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


def test_respiratory_lab_renders_without_exception():
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


@pytest.fixture
def eeg_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "eeg_migration_test.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente migración EEG (test)")
    return sf, pid


def test_eeg_neuro_lab_renders_without_exception(eeg_ups):
    sf, pid = eeg_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


# --- Título único por lab ---------------------------------------------------

def test_ecg_12_has_no_duplicate_title():
    """`ecg_12/pages.py` deliberadamente NO llama a `render_module_header`
    (el título "ECG Lab" vive en `main.py`, un nivel arriba) -- se confirma
    que `page_content.py` tampoco dibuja un `<h1>`/`# ` propio (el bug de
    título triplicado, corregido en Tanda 1, no reapareció con esta
    migración)."""
    def _script():
        import app.supermodules.ecg_12.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert not any("<h1" in md.value for md in at.main.markdown)
    assert not any(md.value.strip().startswith("# ") for md in at.main.markdown)
    h2 = [md.value for md in at.main.markdown if "<h2" in md.value]
    assert any("Vista Clínica" in h for h in h2)  # sanity, non-empty section header


def test_respiratory_lab_title_renders_exactly_once():
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    h1_titles = [md.value for md in at.main.markdown if "<h1" in md.value]
    assert len(h1_titles) == 1, f"se esperaba un único <h1>, hay {len(h1_titles)}: {h1_titles}"
    assert "Respiratory Lab" in h1_titles[0]
    assert not any(md.value.strip().startswith("# ") for md in at.main.markdown)


def test_eeg_neuro_lab_title_renders_exactly_once(eeg_ups):
    sf, pid = eeg_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    h1_titles = [md.value for md in at.main.markdown if "<h1" in md.value]
    assert len(h1_titles) == 1, f"se esperaba un único <h1>, hay {len(h1_titles)}: {h1_titles}"
    assert "EEG Neuro Lab" in h1_titles[0]
    assert not any(md.value.strip().startswith("# ") for md in at.main.markdown)


# --- Jerarquía de confianza en los 3 wrappers --------------------------
#
# NOTA (Consolidación Visual Tanda Final, 2026-09-22): en la migración
# original (Tanda 3), ninguno de los 3 supermodules tenía nivel asignado
# -- barandilla dura de esa tanda ("no fabricar una afirmación clínica").
# La Tanda Final transcribió la firma del experto: Respiratory Lab SÍ
# recibió `validation="VALIDATED"` (AASM real). ecg_12 sigue sin llamar a
# `render_module_header()` en absoluto (su título vive en "ECG Lab",
# `main.py`, con SU PROPIA firma). EEG Neuro Lab sigue mudo, pero ahora
# `validation=None` es EXPLÍCITO y firmado (contenedor mixto), no
# implícito por omisión.

def test_ecg_12_and_eeg_neuro_lab_still_declare_no_validation_tier():
    """Los dos que siguen sin nivel -- ecg_12 nunca llamó a `render_module_
    header()` (nada que asignar); eeg_neuro_lab tiene `validation=None`
    EXPLÍCITO y firmado (ver comentario en el archivo)."""
    ecg_12_src = Path("app/supermodules/ecg_12/pages.py").read_text(encoding="utf-8")
    ecg_12_code_lines = [
        line for line in ecg_12_src.splitlines() if not line.strip().startswith("#")
    ]
    assert not any("render_module_header(" in line for line in ecg_12_code_lines), (
        "ecg_12 no debe LLAMAR a render_module_header() -- una mención en comentario "
        "explicativo (como la de Tanda 3 sobre por qué no lo hace) no cuenta como llamada"
    )

    eeg_src = Path("app/supermodules/eeg_neuro_lab/pages.py").read_text(encoding="utf-8")
    assert "validation=None," in eeg_src
    assert "validation=\"VALIDATED\"" not in eeg_src
    assert "validation=\"HEURISTIC\"" not in eeg_src


def test_respiratory_lab_now_declares_validated_tier_per_expert_signature():
    src = Path("app/supermodules/respiratory_lab/pages.py").read_text(encoding="utf-8")
    assert 'validation="VALIDATED"' in src
    assert "American Academy of Sleep Medicine (AASM)" in src


def test_respiratory_lab_header_shows_validated_confidence_marker():
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    markers = [md.value for md in at.main.markdown if "border-left:3px" in md.value]
    assert len(markers) == 1, f"se esperaba exactamente un marcador VALIDATED: {markers}"
    assert PALETTE.STABLE in markers[0]
    assert "✓" in markers[0]
    assert "AASM" in markers[0], "el texto verbatim de la firma debe aparecer completo, no truncado"


def test_eeg_neuro_lab_header_shows_no_confidence_marker_deliberately(eeg_ups):
    """EEG Neuro Lab sigue mudo -- pero por firma explícita (contenedor
    mixto), no por omisión. Los badges por-métrica (DAR/TBR/BAR/χ, ya
    verificados en `test_eeg_dar_tbr_bar_chi_live_view_matches_expected_
    grammar` más abajo) siguen intactos y hacen el trabajo fino."""
    sf, pid = eeg_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    assert not any("✓" in md.value and "border-left:3px" in md.value for md in at.main.markdown)
    assert not any("◇" in md.value and "border-left:3px" in md.value for md in at.main.markdown)


# --- No-regresión de datos: classify_*() idénticos --------------------------

def test_classify_functions_unchanged_by_migration():
    """Las funciones `classify_*()` no se tocaron -- mismos valores de
    siempre para los mismos inputs (esta migración es solo presentación)."""
    assert classify_dar(1.2) == ("normal", "tejido sano", "🟢")
    assert classify_dar(3.5) == ("severo", "isquemia severa / sufrimiento cortical", "🔴")
    assert classify_tbr(1.2) == ("normal", "enganchado / aprendizaje activo", "🟢")
    assert classify_chi(0.8) == ("excitacion", "excitación cortical (hiperexcitabilidad)", "🔴")
    assert classify_chi(1.8) == ("inhibicion", "inhibición cortical (supresión/enlentecimiento)", "💤")


def test_eeg_dar_tbr_bar_chi_live_view_matches_expected_grammar(eeg_ups):
    """El test que importa de esta tanda para EEG: DAR/TBR (severidad) y
    BAR/χ (estado neutro) ahora se muestran EN VIVO (no solo en el export
    de Tanda 2) vía `render_metric_card`, con la colisión roja ausente --
    χ con badge 🔴 nunca se enmarca en CRITICAL/WARNING."""
    sf, pid = eeg_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    assert at.exception == []

    dur_slider = next(s for s in at.sidebar.slider if s.label == "Duración (segundos)")
    dur_slider.set_value(90)  # >= MIN_CHI_CLEAN_WINDOWS con margen -- χ disponible
    at.run(timeout=30)
    assert at.exception == []

    dar_cards = [md.value for md in at.main.markdown if "DAR (Delta" in md.value]
    assert dar_cards, "no se encontró la tarjeta de DAR en la vista en vivo"
    # severidad: el marco debe ser uno de los 3 colores de PALETTE de severidad
    assert any(c in dar_cards[0] for c in (PALETTE.STABLE, PALETTE.WARNING, PALETTE.CRITICAL))

    btn = next(b for b in at.main.button if b.label == "💾 Guardar estado al gemelo")
    btn.click()
    at.run(timeout=30)
    assert at.exception == []

    chi_cards = [md.value for md in at.main.markdown if "χ" in md.value]
    bar_cards = [md.value for md in at.main.markdown if "BAR" in md.value]
    assert chi_cards, "no se encontró ninguna tarjeta de χ"
    assert bar_cards, "no se encontró ninguna tarjeta de BAR"
    for card in chi_cards + bar_cards:
        assert PALETTE.CRITICAL not in card, "χ/BAR nunca deben enmarcarse como alarma"
        assert PALETTE.WARNING not in card, "χ/BAR nunca deben enmarcarse como alarma"


# --- <style> propios retirados ------------------------------------------

def test_no_local_style_blocks_remain():
    """NOTA DE MÉTODO: se busca el tag SIN comillas invertidas alrededor --
    un grep ingenuo de '<style>' falsea contra los propios comentarios que
    documentan qué se retiró (los citan a propósito, entre backticks,
    p.ej. `` `<style>` ``, como referencia para quien lea después)."""
    import re

    for path in (
        "app/supermodules/ecg_12/page_content.py",
        "app/supermodules/eeg_neuro_lab/page_content.py",
        "app/supermodules/respiratory_lab/page_content.py",
    ):
        src = Path(path).read_text(encoding="utf-8")
        assert not re.search(r"(?<!`)<style>(?!`)", src), f"{path} todavía tiene un <style> propio"


def test_respiratory_ahi_severity_provenance_is_clinical_consistent_with_twin_shell():
    """Consistencia entre-archivos: el AHI/Severidad de Respiratory Lab
    está respaldado por criterio AASM real (`_assess_severity()`,
    `src/signals/respiration/respiratory_analyzer.py`) -- mismo estándar
    que `twin_shell/pages.py::_RISK_SYSTEM_PROVENANCE` ya cita
    (`PROVENANCE_SOURCE_AASM`) para el mismo AHI. Debe llevar
    `BADGES.CLINICAL`, no `HEURISTIC`, en TODOS los sitios donde se
    muestra (fila de métricas principal, resumen clínico, pestaña
    Investigación)."""
    page_content = Path("app/supermodules/respiratory_lab/page_content.py").read_text(encoding="utf-8")
    pages = Path("app/supermodules/respiratory_lab/pages.py").read_text(encoding="utf-8")
    import re

    for src, label in ((page_content, "page_content.py"), (pages, "pages.py")):
        for m in re.finditer(r'render_metric_card\(\s*"([^"]*(?:AHI|Severidad)[^"]*)"', src):
            # find the provenance= on the same call (within next ~200 chars)
            window = src[m.end(): m.end() + 250]
            assert "BADGES.CLINICAL" in window, (
                f"{label}: la tarjeta '{m.group(1)}' debería usar BADGES.CLINICAL (AASM), "
                f"contexto: {window[:120]!r}"
            )
