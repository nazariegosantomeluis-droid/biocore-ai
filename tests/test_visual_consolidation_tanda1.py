"""
Consolidación Visual, Tanda 1 (2026-09-20) -- el sistema, no la migración.
Verificado POR EJECUCIÓN vía AppTest hasta el final del render (la
barandilla de siempre: el recon puede mentir, correr el render no).

Alcance de esta tanda (ver CHANGELOG.md): resuelve las dos gramáticas de
honestidad (Eje A procedencia / Eje B clasificación, con la colisión
severidad-vs-estado-neutro del χ resuelta a nivel de MARCO, sin tocar
`classify_chi()`), construye `render_metric_card()` (la superficie de
métrica+badge que no existía), define la jerarquía visual de confianza
(`validation=` en `render_module_header()`, probada en ECG Lab vs.
Multisensor Fusion Lab) y consolida el CSS global paralelo
(`inject_global_theme()` reemplaza `inject_biocore_css()`) + corrige el
título triplicado de EEG Neuro Lab / ECG-12. NINGÚN lab se migra a
`render_metric_card()` todavía -- eso son tandas paralelas.
"""

import pytest
from streamlit.testing.v1 import AppTest

# NOTA: estos imports de módulo son solo para las aserciones (comparar
# contra `PALETTE.STABLE`, llamar `classify_dar()` directo, etc.) -- cada
# `_script()` de abajo importa lo que necesita POR SU CUENTA, porque
# `AppTest.from_function()` re-ejecuta ese cuerpo como script aislado, sin
# heredar closures ni imports de este módulo.
from app.utils.design_system import BADGES, PALETTE
from src.signals.eeg.eeg_analyzer import classify_dar
from src.signals.eeg.spectral_model import classify_chi


# --- Parte D: render sin excepción, una forma de cada tipo físico --------

def test_ecg_lab_renders_without_exception_inline_plus_runpy():
    """`render_ecg_lab_page()` vive inline en `app/main.py` (una de las dos
    formas físicas de módulo) y anida ECG-12 (`app/supermodules/ecg_12/`,
    la otra forma -- paquete + `runpy`) en su segunda pestaña. Un solo
    render cubre ambas formas."""
    def _script():
        import app.main as m
        m.render_ecg_lab_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


def test_eeg_neuro_lab_renders_without_exception_via_runpy():
    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


def test_multisensor_renders_without_exception_inline():
    def _script():
        import app.main as m
        m.render_multisensor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render: {at.exception}"


# --- Parte D: título triplicado corregido ---------------------------------

def test_ecg_lab_title_renders_exactly_once():
    """Antes: `render_module_header("ECG Lab")` (h1) + `render_section_
    header("Vista Clínica — ECG 12 Derivaciones")` (h2) + el `# ECG de 12
    Derivaciones` propio de `ecg_12/page_content.py` (un tercer título).
    Ahora: un solo `<h1>` en toda la página."""
    def _script():
        import app.main as m
        m.render_ecg_lab_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    h1_titles = [md.value for md in at.main.markdown if "<h1" in md.value]
    assert len(h1_titles) == 1, f"se esperaba un único <h1>, hay {len(h1_titles)}: {h1_titles}"
    assert "ECG Lab" in h1_titles[0]
    # el título propio de ecg_12/page_content.py ya no existe en ningún lado
    assert not any(md.value.strip().startswith("# ") for md in at.main.markdown)


def test_eeg_neuro_lab_title_renders_exactly_once():
    """Antes: `render_module_header("EEG Neuro Lab")` (h1) + `render_
    section_header("Vista Clínica")` (h2) + `st.markdown("# 🧠 EEG Neuro
    Lab")` propio de `page_content.py` (un tercer título, con subtítulo
    duplicado además). El subtítulo se movió al `render_module_header()`
    del wrapper -- no se perdió contenido, solo se dejó de repetir."""
    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    h1_titles = [md.value for md in at.main.markdown if "<h1" in md.value]
    assert len(h1_titles) == 1, f"se esperaba un único <h1>, hay {len(h1_titles)}: {h1_titles}"
    assert "EEG Neuro Lab" in h1_titles[0]
    # ningún " # " crudo queda en el ÁREA PRINCIPAL (el st.sidebar.markdown
    # "# EEG Neuro Lab" es un encabezado de sidebar distinto, fuera de
    # alcance de este bug -- se confirma que sigue vivo y sin tocar).
    assert not any(md.value.strip().startswith("# ") for md in at.main.markdown)
    subtitle_hits = [md.value for md in at.main.markdown if "Laboratorio de señales electroencefalográficas" in md.value]
    assert len(subtitle_hits) == 1, "el subtítulo debe sobrevivir, una sola vez (movido al wrapper)"
    sidebar_titles = [md.value for md in at.sidebar.markdown if md.value.strip() == "# EEG Neuro Lab"]
    assert len(sidebar_titles) == 1, "el encabezado de sidebar es un elemento distinto -- no se tocó en esta tanda"


# --- Parte C: jerarquía visual de confianza, probada en los dos extremos --

def test_ecg_lab_shows_validated_confidence_marker():
    """NOTA (Tanda Final, 2026-09-22): el texto del marcador es ahora la
    firma VERBATIM del experto -- "MIT-BIH" es el fragmento estable entre
    la redacción provisional de Tanda 1 y el texto firmado (que ya no
    dice "TKEO", dice "Detección QRS")."""
    def _script():
        import app.main as m
        m.render_ecg_lab_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    markers = [md.value for md in at.main.markdown if "MIT-BIH" in md.value]
    assert len(markers) == 1
    assert PALETTE.STABLE in markers[0], "el marco de un módulo validado debe usar STABLE, no un color de alarma"
    assert "AHA" in markers[0]
    assert "✓" in markers[0]


def test_multisensor_shows_heuristic_confidence_marker():
    """NOTA (Tanda Final, 2026-09-22): la firma verbatim del experto ya no
    contiene la palabra "heurístico" -- se busca por "Health Score", el
    fragmento estable de su propio texto."""
    def _script():
        import app.main as m
        m.render_multisensor_page()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    markers = [md.value for md in at.main.markdown if "Health Score propietario" in md.value]
    assert len(markers) == 1
    assert PALETTE.NEUTRAL in markers[0], "heurístico no es una alarma -- debe ser NEUTRAL, no WARNING/CRITICAL"
    assert "no validado" in markers[0]
    assert "◇" in markers[0]


def test_confidence_markers_are_visually_distinguishable_between_extremes():
    """La prueba del lenguaje: ECG (validado) y Multisensor (heurístico)
    deben verse con autoridad distinta -- colores de marco distintos,
    símbolos distintos."""
    def _script_ecg():
        import app.main as m
        m.render_ecg_lab_page()

    def _script_multi():
        import app.main as m
        m.render_multisensor_page()

    at_ecg = AppTest.from_function(_script_ecg)
    at_ecg.run(timeout=30)
    at_multi = AppTest.from_function(_script_multi)
    at_multi.run(timeout=30)

    ecg_marker = next(md.value for md in at_ecg.main.markdown if "MIT-BIH" in md.value)
    multi_marker = next(md.value for md in at_multi.main.markdown if "Health Score propietario" in md.value)

    assert PALETTE.STABLE in ecg_marker and PALETTE.STABLE not in multi_marker
    assert PALETTE.NEUTRAL in multi_marker and PALETTE.NEUTRAL not in ecg_marker
    assert "✓" in ecg_marker and "✓" not in multi_marker
    assert "◇" in multi_marker and "◇" not in ecg_marker


# --- Parte A: la colisión de gramáticas, resuelta a nivel de marco --------
#
# NOTA DE MÉTODO: `AppTest.from_function()` re-ejecuta el cuerpo de
# `_script()` como un script AISLADO -- no hereda closures ni imports del
# scope que lo definió. Cada `_script()` de aquí en adelante importa todo
# lo que usa, siempre dentro de sí mismo (mismo patrón que
# `tests/test_emg_lab_save_to_twin.py`/`test_neuro_dar_tbr_badges.py`).

def test_severity_grammar_colors_frame_by_level():
    """DAR/TBR (GRAMMAR_SEVERITY): el marco SIGUE el nivel -- normal=STABLE,
    leve=WARNING, severo=CRITICAL. Refuerza el badge, no lo contradice."""
    def _script():
        from app.utils.design_system import GRAMMAR_SEVERITY, render_metric_card
        from src.signals.eeg.eeg_analyzer import classify_dar
        render_metric_card("DAR", "1.20", classification=classify_dar(1.2), grammar=GRAMMAR_SEVERITY)
        render_metric_card("DAR", "2.00", classification=classify_dar(2.0), grammar=GRAMMAR_SEVERITY)
        render_metric_card("DAR", "3.50", classification=classify_dar(3.5), grammar=GRAMMAR_SEVERITY)

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    cards = [md.value for md in at.main.markdown if "DAR" in md.value]
    assert len(cards) == 3
    assert PALETTE.STABLE in cards[0]     # normal
    assert PALETTE.WARNING in cards[1]    # leve
    assert PALETTE.CRITICAL in cards[2]   # severo


def test_neutral_state_grammar_never_uses_danger_colors_even_with_red_badge():
    """LA aserción que importa: χ con badge 🔴 (nivel 'excitacion') bajo
    GRAMMAR_NEUTRAL_STATE NO debe enmarcarse en CRITICAL -- ese es
    exactamente el punto de la colisión que esta tanda resuelve. El emoji
    🔴 sigue ahí (classify_chi() no se tocó); el marco alrededor no debe
    leerse como alarma."""
    def _script():
        from app.utils.design_system import GRAMMAR_NEUTRAL_STATE, render_metric_card
        from src.signals.eeg.spectral_model import classify_chi
        render_metric_card("χ", "0.80", classification=classify_chi(0.8), grammar=GRAMMAR_NEUTRAL_STATE)  # 🔴 excitación -- el caso de colisión real
        render_metric_card("χ", "1.30", classification=classify_chi(1.3), grammar=GRAMMAR_NEUTRAL_STATE)  # 🔵 indeterminado
        render_metric_card("χ", "1.80", classification=classify_chi(1.8), grammar=GRAMMAR_NEUTRAL_STATE)  # 💤 inhibición

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    cards = [md.value for md in at.main.markdown if "χ" in md.value]
    assert len(cards) == 3
    for card in cards:
        assert PALETTE.CRITICAL not in card, "un valor sin valencia de peligro no puede enmarcarse como alarma"
        assert PALETTE.WARNING not in card
        assert PALETTE.ACCENT_ON_DARK in card, "GRAMMAR_NEUTRAL_STATE siempre usa el mismo tono, sin importar el nivel"
    # el badge 🔴 de "excitación" SIGUE presente -- no se tocó classify_chi()
    assert "🔴" in cards[0]
    assert "excitación cortical" in cards[0]


def test_classify_chi_and_classify_dar_untouched_same_values_as_before():
    """No-regresión de datos: las funciones classify_*() no se tocaron en
    esta tanda -- solo cambió CÓMO se pintan sus resultados."""
    assert classify_dar(1.2) == ("normal", "tejido sano", "🟢")
    assert classify_dar(3.5) == ("severo", "isquemia severa / sufrimiento cortical", "🔴")
    assert classify_chi(0.8) == ("excitacion", "excitación cortical (hiperexcitabilidad)", "🔴")
    assert classify_chi(1.8) == ("inhibicion", "inhibición cortical (supresión/enlentecimiento)", "💤")


# --- Parte B: render_metric_card -- estándar del χ + los 4 "no disponible" -

def test_render_metric_card_shows_full_citation_never_truncated():
    from src.signals.eeg.spectral_model import CHI_CITATION

    def _script():
        from app.utils.design_system import GRAMMAR_NEUTRAL_STATE, render_metric_card
        from src.signals.eeg.spectral_model import CHI_CITATION, classify_chi
        render_metric_card(
            "χ", "0.80",
            classification=classify_chi(0.8), grammar=GRAMMAR_NEUTRAL_STATE, citation=CHI_CITATION,
        )

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    card = next(md.value for md in at.main.markdown if "χ" in md.value)
    assert CHI_CITATION in card, "la cita debe aparecer COMPLETA, nunca truncada"


def test_render_metric_card_provenance_axis_uses_badges_label():
    """Eje A vía `BADGES.label()` -- el formateador que existía sin
    llamador, ahora usado de verdad."""
    def _script():
        from app.utils.design_system import BADGES, render_metric_card
        render_metric_card("BAR", "0.95", provenance=BADGES.CLINICAL)

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    card = next(md.value for md in at.main.markdown if "BAR" in md.value)
    assert BADGES.label(BADGES.CLINICAL) in card


_UNAVAILABLE_CASES = [
    ("NeuroCardiac PLV", "el PLV requiere ≥180s de señal ECG+EEG simultánea. Muestra actual: 45s."),
    ("Learning Readiness Index", "depende del PLV neurocardíaco (arriba), que no está disponible."),
    ("Autonomic Stability", "requiere presión arterial y PPG-PTT que hoy no existen en el pipeline"),
    ("χ (aperiódico)", "señal insuficiente para χ: 10 ventanas < mínimo 30"),
]


@pytest.mark.parametrize("label, reason_fragment", _UNAVAILABLE_CASES)
def test_render_metric_card_preserves_each_unavailable_reason(label, reason_fragment):
    """Los 4 estilos de 'no disponible' que encontró el diagnóstico
    quedan unificados en FORMA -- pero cada `reason` textual específico
    (la duración exacta del PLV, la dependencia de Readiness, lo que le
    falta a Autonomic Stability, el motivo exacto de χ) se preserva
    completo. Unificar la forma sin perder el motivo es el punto -- lo
    contrario sería el retroceso que el diagnóstico advirtió (riesgo #2).

    `label`/`reason_fragment` viajan por `session_state`, no por closure --
    `AppTest.from_function()` re-ejecuta `_script()` como script aislado,
    sin acceso al scope de la función de test que lo definió."""
    def _script():
        import streamlit as st
        from app.utils.design_system import render_metric_card
        render_metric_card(st.session_state["_label"], None, unavailable_reason=st.session_state["_reason"])

    at = AppTest.from_function(_script)
    at.session_state["_label"] = label
    at.session_state["_reason"] = reason_fragment
    at.run(timeout=30)
    card = next(md.value for md in at.main.markdown if label in md.value)
    assert reason_fragment in card
    assert "no disponible" in card


def test_render_metric_card_logs_instead_of_fabricating_when_reason_missing(caplog):
    """Honestidad de borde: si un llamador olvida el motivo, la tarjeta NO
    inventa uno plausible -- lo señala y lo registra para desarrollo."""
    import logging

    def _script():
        from app.utils.design_system import render_metric_card
        render_metric_card("Métrica sin motivo", None)

    at = AppTest.from_function(_script)
    with caplog.at_level(logging.WARNING, logger="app.utils.design_system"):
        at.run(timeout=30)
    card = next(md.value for md in at.main.markdown if "Métrica sin motivo" in md.value)
    assert "no disponible" in card
    assert "sin motivo declarado" in card


# --- Parte D: CSS consolidado -- dead code retirado, PALETTE como fuente --
#
# NOTA DE MÉTODO: se verifica el COMPORTAMIENTO (qué existe como símbolo
# real, qué CSS sale efectivamente al renderizar), no el texto crudo del
# archivo -- un grep sobre el archivo completo falsea contra los propios
# comentarios que documentan qué se retiró y por qué (que citan los
# nombres viejos a propósito, como referencia para quien lea después).

def test_main_no_longer_defines_inject_biocore_css():
    import app.main as m
    assert not hasattr(m, "inject_biocore_css"), "inject_biocore_css() debía reemplazarse por inject_global_theme()"
    assert hasattr(m, "inject_global_theme"), "main.py debe importar inject_global_theme() de design_system.py"


def test_inject_global_theme_output_has_no_dead_classes_or_unrelated_hex():
    def _script():
        from app.utils.design_system import inject_global_theme
        inject_global_theme()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    style_output = "\n".join(md.value for md in at.main.markdown)
    for dead_class in (".biocore-card", ".biocore-panel", ".status-pill", ".pulse-dot"):
        assert dead_class not in style_output, f"{dead_class} debía retirarse (CSS muerto, cero consumidores)"
    # los hex cian originales del degradado viejo no deben sobrevivir en
    # la salida real -- el fondo ahora se construye desde PALETTE
    assert "#05101f" not in style_output and "#040812" not in style_output
    assert PALETTE.BACKGROUND in style_output


def test_inject_global_theme_renders_without_exception():
    def _script():
        from app.utils.design_system import inject_global_theme
        inject_global_theme()

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == []


def test_twin_shell_loose_literal_replaced_by_shared_constants():
    import pathlib
    src = pathlib.Path("app/supermodules/twin_shell/pages.py").read_text(encoding="utf-8")
    assert '"🟢🔵 "' not in src, "el literal suelto debía reemplazarse por PROVENANCE_CLINICAL_BADGE/PROVENANCE_HEURISTIC_BADGE"
