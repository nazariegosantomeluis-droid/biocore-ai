"""Rediseño visual (2026-10-19): ilustraciones SVG, tema y su integración.

Qué se protege:
- Cada SVG es XML válido y accesible (role="img" + <title> enlazado).
- La salida es determinista y segura para `st.markdown` (sin líneas en
  blanco ni signos de pesos, que Markdown/LaTeX reinterpretarían).
- Honestidad: cada lámina dice qué es (registro real, anatomía real de una
  tomografía, esquema o simulación), lleva fuentes, y los números que rotula
  salen del propio código (intervalos MEDIDOS sobre el latido real, límites
  de banda del analizador EEG, fórmulas de HRV sobre RR reales).
- Los colores de estado clínico no se usan como decoración.
- Contraste WCAG de los tokens de la interfaz, calculado.
- Integración: cada laboratorio dibuja su lámina (AppTest).
"""
from __future__ import annotations

import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from app.utils.design_system import PALETTE, global_theme_css, module_header_html
from visualization.art import (
    ATLAS, MODULE_GLYPHS, ORGAN_GLYPHS, PLATES, STRIP_KINDS, module_glyph_svg, organ_glyph_svg,
    plate_figure_html, signal_strip_svg,
)
from visualization.art import tokens as T
from visualization.art import waves
from visualization.art.meters import news2_meter_svg
from visualization.art.plates import hrv_metrics, respiratory_gallery_html, respiratory_traces
from visualization.art.strips import REAL_SOURCES
from visualization.art import renders as R

ROOT = Path(__file__).resolve().parents[1]
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)


def _svgs(html: str):
    found = SVG_RE.findall(html)
    assert found, "no se encontró ningún <svg>"
    return found


def _parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _assert_accessible(svg: str) -> None:
    root = _parse(svg)
    assert root.get("role") == "img"
    ids = (root.get("aria-labelledby") or "").split()
    assert ids, "falta aria-labelledby"
    titles = {el.get("id"): (el.text or "") for el in root.iter() if el.tag.endswith("title")}
    assert ids[0] in titles and titles[ids[0]].strip(), "el <title> enlazado debe existir y no estar vacío"


def _markdown_safe(html: str) -> None:
    assert "\n\n" not in html, "una línea en blanco cortaría el bloque HTML en Markdown"
    assert "$" not in html, "Streamlit interpreta $...$ como LaTeX"
    assert not re.search(r":[a-z_]+:", re.sub(r"https?://\S+", "", html)), "':nombre:' se vuelve emoji/ícono"


def _contrast(a: str, b: str) -> float:
    def lum(h):
        h = h.lstrip("#")
        r, g, bb = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bb)
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ─── Tiras de monitor ────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", sorted(STRIP_KINDS))
def test_every_strip_is_valid_accessible_and_safe(kind):
    svg = signal_strip_svg(kind)
    _assert_accessible(svg)
    _markdown_safe(svg)
    if kind in REAL_SOURCES:
        # 2026-10-21: registro real de PhysioNet, dicho en el título y visible.
        assert "Registro real" in svg and "ODC-By 1.0" in svg
        assert REAL_SOURCES[kind][1] in svg
    else:
        assert "Esquema ilustrativo" in svg
    assert signal_strip_svg(kind) == svg, "la tira debe ser determinista"


def test_strip_height_matches_css_so_it_never_crops_vertically():
    root = _parse(signal_strip_svg("ecg"))
    _, _, w, h = (float(v) for v in root.get("viewBox").split())
    assert h == 64 and w >= 2000
    from visualization.art.css import ART_CSS
    assert ".bc-strip{" in ART_CSS and "height:64px" in ART_CSS


def test_unknown_strip_kind_draws_nothing():
    assert signal_strip_svg("no-existe") == ""


# ─── Íconos ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", sorted(MODULE_GLYPHS))
def test_module_glyphs_are_valid_and_decorative(kind):
    root = _parse(module_glyph_svg(kind))
    assert root.get("aria-hidden") == "true"
    assert root.get("stroke") == "currentColor"


@pytest.mark.parametrize("organ_id", sorted(ORGAN_GLYPHS))
def test_organ_glyphs_take_the_given_color_without_global_css(organ_id):
    svg = organ_glyph_svg(organ_id, "#123456")
    root = _parse(svg)
    assert root.get("stroke") == "#123456"
    assert "<style" not in svg, "un <style> en SVG en línea sería CSS global de la página"
    labelled = _parse(organ_glyph_svg(organ_id, "#123456", label="Corazón"))
    assert labelled.get("role") == "img" and labelled.get("aria-label") == "Corazón"


# ─── Láminas ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", ATLAS)
def test_every_plate_renders_valid_svg_with_label_and_sources(key):
    html = plate_figure_html(key)
    _markdown_safe(html)
    assert html.startswith("<figure") and f'id="lamina-{key}"' in html
    plate = PLATES[key]
    assert plate.chip in ("Esquema ilustrativo", "Registro real", "Anatomía real (TC)", "Corazón real + esquema",
                          "Cabeza 3D (plantilla)", "Simulación del laboratorio")
    assert f'<span class="bc-chip">{plate.chip}</span>' in html, "la etiqueta dice qué es la imagen"
    assert "Fuentes" in html and plate.sources
    svgs = SVG_RE.findall(html)
    for svg in svgs:
        _assert_accessible(svg)
    if not svgs:  # render sin capa: la imagen lleva su texto alternativo
        assert re.search(r'<img [^>]*alt="[^"]{20,}"', html)
    assert plate_figure_html(key) == html, "la lámina debe ser determinista"


def test_decorative_art_never_uses_clinical_status_colors():
    """Los colores de estado (STABLE/WARNING/CRITICAL) significan estado
    clínico real; una ilustración no debe usarlos como adorno."""
    reserved = {c.lower() for c in T.STATUS_RESERVED}
    assert reserved == {PALETTE.STABLE.lower(), PALETTE.WARNING.lower(), PALETTE.CRITICAL.lower()}
    outputs = [signal_strip_svg(k) for k in STRIP_KINDS] + [plate_figure_html(k) for k in ATLAS]
    outputs += [module_glyph_svg(k) for k in MODULE_GLYPHS]
    for out in outputs:
        low = out.lower()
        for color in reserved:
            assert color not in low, f"{color} apareció en arte decorativo"


def test_ecg_plate_labels_intervals_measured_on_the_real_beat():
    from src.signals.ecg.beat_delineation import reference_beat

    from clinical.calculators import qtc_bazett

    beat, d = reference_beat()
    assert beat.n_beats >= 100, "latido mediano de muchos latidos normales anotados"
    # MIT-BIH 100 (MLII): T baja, ancha y tardía -- sin onda U según la
    # anotación de Elgendi et al. (Sensors 2015), así que el QT es largo.
    assert 120 <= d.pr_ms <= 220 and 50 <= d.qrs_ms < 120 and 450 <= d.qt_ms <= 560
    html = plate_figure_html("ecg_complex")
    for key, val in (("PR", d.pr_ms), ("QRS", d.qrs_ms), ("QT", d.qt_ms)):
        assert f"{key} {val:.0f} ms" in html, f"el rótulo de {key} debe ser el valor medido"
    qtc = qtc_bazett(d.qt_ms, beat.rr_ms / 1000.0)
    assert f"QTc {qtc:.0f} ms" in html and "prolongado" in html, "el QTc se dice, con la misma fórmula de la app"
    assert "MIT-BIH" in html and "Registro real" in html


def test_t_wave_end_does_not_depend_on_quantization_noise():
    """El fin de T sale de la pendiente de la onda, no del escalón de 0.005 mV
    del registro (antes, sin suavizar, salía 50 ms antes), y la onda T no
    salta a la muesca del ST desnivelado: con ruido del orden de la
    cuantización (0.005/√12 mV) el pico de T se queda en su lugar."""
    from dataclasses import replace

    from src.signals.ecg.beat_delineation import delineate, reference_beat

    beat, d = reference_beat()
    rng = np.random.default_rng(7)
    for _ in range(10):
        n = delineate(replace(beat, v=beat.v + rng.normal(0, 0.0015, beat.v.size)))
        assert abs(n.t_peak - d.t_peak) < 20
        assert abs(n.t_off - d.t_off) < 25
        assert abs(n.qrs_on - d.qrs_on) < 10


@pytest.mark.parametrize("part", ["P", "PR", "QRS", "ST", "T", "QT"])
def test_ecg_plate_highlight_changes_the_drawing(part):
    plain = plate_figure_html("ecg_complex")
    highlighted = plate_figure_html("ecg_complex", highlight=part)
    assert highlighted != plain and "resaltado" in highlighted
    assert T.TRACE_FILL in highlighted


@pytest.mark.parametrize("part", ["SA Node", "AV Node", "His Bundle", "Purkinje"])
def test_conduction_plate_accepts_the_ecg_lab_anatomy_keys(part):
    html = plate_figure_html("conduction", highlight=part)
    assert "resaltado: paso" in html
    assert 'class="bc-on"' in html, "el paso elegido se marca también en la lista"


def test_eeg_band_plate_uses_the_analyzer_limits_and_marks_the_dominant_band():
    from src.signals.eeg.eeg_analyzer import BAND_LIMITS_HZ
    html = plate_figure_html("eeg_bands", dominant="alpha")
    for lo, hi in BAND_LIMITS_HZ.values():
        assert f"{lo:g}–{hi:g} Hz" in html
    assert "dominante en tu señal" in html and "banda dominante resaltada: alpha" in html


def test_eeg_band_limits_refactor_kept_the_same_values():
    from src.signals.eeg.eeg_analyzer import BAND_CLASSIFICATION, BAND_LIMITS_HZ, EegAnalyzer
    assert BAND_LIMITS_HZ == {"delta": (0.5, 3.5), "theta": (4.0, 7.5), "alpha": (8.0, 12.0),
                              "beta": (13.0, 30.0), "gamma": (30.0, 45.0)}
    assert EegAnalyzer(fs=256)._classify_pattern("alpha", {}) == BAND_CLASSIFICATION["alpha"]
    assert EegAnalyzer(fs=256)._classify_pattern("nada", {}) == "Patrón no determinado"


def test_eeg_1020_plate_highlights_only_known_channels():
    html = plate_figure_html("eeg_1020", active=("Fp1", "C4", "canal_raro"))
    assert "resaltados Fp1, C4" in html
    anchors = R.anchors("atlas_1020_top")
    assert {"Fp1", "Fp2", "C3", "C4", "Cz", "O1", "O2"} <= set(anchors) and len(anchors) == 21


def test_tachogram_uses_real_rr_and_the_hrv_page_formulas():
    from src.signals.reference_recordings import normal_rr_ms

    rr = normal_rr_ms(max_beats=2000)
    m = hrv_metrics(rr)
    assert m["sdnn"] == pytest.approx(np.std(rr, ddof=1))
    assert m["rmssd"] == pytest.approx(np.sqrt(np.mean(np.diff(rr) ** 2)))
    assert 600 < m["mean"] < 1000 and m["n"] > 300
    html = plate_figure_html("tachogram")
    assert f"SDNN {m['sdnn']:.0f} ms" in html and f"RMSSD {m['rmssd']:.0f} ms" in html


def test_respiratory_gallery_reuses_the_lab_generator_without_touching_global_rng():
    before = np.random.get_state()[1].copy()
    t, flow, chest = respiratory_traces("apnea_obstructive")
    after = np.random.get_state()[1]
    assert np.array_equal(before, after), "la galería no debe alterar la aleatoriedad del resto de la app"
    assert t[-1] == pytest.approx(60.0, abs=0.2)
    # Obstructiva: sin flujo en la ventana de apnea (40-60 s) PERO con esfuerzo.
    window = t >= 41
    assert np.max(np.abs(flow[window])) < 0.2
    assert np.max(np.abs(chest[window])) > 0.2
    t2, flow_c, chest_c = respiratory_traces("apnea_central")
    assert np.max(np.abs(chest_c[t2 >= 41])) < 0.2, "central: el esfuerzo también se detiene"


def test_respiratory_gallery_marks_the_selected_pattern():
    html = respiratory_gallery_html("cheyne_stokes")
    assert html.count('class="bc-tile bc-on"') == 1
    assert "Elegido en el laboratorio" in html
    assert html.count('<div class="bc-tile">') + html.count('<div class="bc-tile bc-on">') == 7


def test_news2_meter_uses_status_colors_with_labels():
    svg = news2_meter_svg(6)
    _assert_accessible(svg)
    for label in ("Bajo 0–4", "Medio 5–6", "Alto ≥ 7", "6 puntos"):
        assert label in svg
    assert "respuesta urgente" in news2_meter_svg(3, any_single_3=True)


# ─── Encabezado y tema ───────────────────────────────────────────────────

def test_module_header_has_one_h1_glyph_crumb_and_strip():
    html = module_header_html("ECG Lab", "🫀", "sub", art="ecg", hub="Clinical Hub")
    _markdown_safe(html)
    assert html.count("<h1") == 1 and "<h1>ECG Lab</h1>" in html
    assert "Clinical Hub" in html and 'class="bc-strip"' in html and 'class="bc-glyph"' in html
    assert "🫀" not in html, "con ícono dibujado el emoji ya no va en el título"


def test_module_header_without_art_keeps_the_old_emoji_title():
    html = module_header_html("Algo", "🧪")
    assert "<h1>🧪 Algo</h1>" in html and "bc-strip" not in html


def test_global_theme_css_is_markdown_safe_and_accessible():
    css = global_theme_css()
    assert css.startswith("<style>") and css.endswith("</style>") and "\n" not in css
    assert ":focus-visible" in css and "prefers-reduced-motion" in css
    assert "min-height:44px" in css
    assert PALETTE.BACKGROUND in css
    for dead in (".biocore-card", ".biocore-panel", ".status-pill", ".pulse-dot"):
        assert dead not in css


def test_art_tokens_match_the_shared_palette():
    assert T.BACKGROUND == PALETTE.BACKGROUND
    assert T.INK == PALETTE.TEXT
    assert T.TEAL == PALETTE.PRIMARY
    assert T.TRACE == PALETTE.TRACE


def test_interface_colors_meet_wcag_contrast():
    bg, panel, side = PALETTE.BACKGROUND, T.PANEL, PALETTE.SECONDARY_BACKGROUND
    assert _contrast(PALETTE.PRIMARY, bg) >= 4.5        # pestaña activa / valor de slider
    assert _contrast(PALETTE.PRIMARY, side) >= 4.5      # lo mismo en la barra lateral
    assert _contrast("#ffffff", PALETTE.PRIMARY) >= 3.0  # palomita del checkbox (WCAG 1.4.11)
    assert _contrast(bg, PALETTE.PRIMARY) >= 4.5        # texto oscuro del botón primario
    assert _contrast(PALETTE.ACCENT_ON_DARK, bg) >= 7.0
    for ink in (T.INK, T.INK_2, T.INK_3, T.TRACE):
        assert _contrast(ink, panel) >= 4.5 and _contrast(ink, bg) >= 4.5


def test_streamlit_config_fonts_exist_and_theme_matches_palette():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    theme = cfg["theme"]
    assert cfg["server"]["enableStaticServing"] is True
    assert theme["primaryColor"] == PALETTE.PRIMARY
    assert theme["backgroundColor"] == PALETTE.BACKGROUND
    assert theme["textColor"] == PALETTE.TEXT
    # Plotly en Streamlit 1.66 exige exactamente 10 colores (si no, usa los
    # suyos); los 8 primeros son la paleta validada, 9-10 repiten 1-2.
    assert len(theme["chartCategoricalColors"]) == 10
    assert theme["chartCategoricalColors"][:8] == list(T.SERIES)
    assert theme["chartCategoricalColors"][8:] == list(T.SERIES[:2])
    families = {f["family"] for f in theme["fontFaces"]}
    assert {"Figtree", "Noto Sans"} <= families
    for face in theme["fontFaces"]:
        path = ROOT / "app" / face["url"].removeprefix("app/")
        assert path.is_file() and path.stat().st_size > 5000, face["url"]
    assert (ROOT / "app" / "static" / "fonts" / "LICENSE-Figtree-OFL.txt").is_file()
    assert (ROOT / "app" / "static" / "fonts" / "LICENSE-NotoSans-OFL.txt").is_file()


# ─── Integración en las páginas (AppTest) ────────────────────────────────

@pytest.fixture
def ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory
    engine = make_engine(tmp_path / "illustrations.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente Ilustraciones (test)")
    return sf, pid


def _run(fn_path: str, ups=None, **state):
    module, func = fn_path.rsplit(".", 1)

    def _script(module, func):
        import importlib
        getattr(importlib.import_module(module), func)()

    at = AppTest.from_function(_script, args=(module, func), default_timeout=120)
    if ups is not None:
        sf, pid = ups
        at.session_state["twin_shell_ups_session_factory"] = sf
        at.session_state["twin_shell_ups_patient_id"] = pid
        at.session_state["academia_case_session_factory"] = sf
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at, " ".join(m.value for m in at.markdown)


def test_ecg_lab_draws_header_strip_and_its_plates():
    _, html = _run("app.main.render_ecg_lab_page")
    assert 'class="bc-strip"' in html
    for key in ("ecg_complex", "precordial", "hexaxial"):
        assert f'id="lamina-{key}"' in html, key


def test_ecg_lab_educational_view_highlights_the_chosen_structure():
    at, _ = _run("app.main.render_ecg_lab_page", ecg_anatomy_part="AV Node")
    radio = next(r for r in at.radio if r.label == "Capa de Exploración Cognitiva")
    radio.set_value("Educativa").run()
    html = " ".join(m.value for m in at.markdown)
    assert 'id="lamina-conduction"' in html and "resaltado: paso 3" in html


def test_eeg_lab_shows_band_and_1020_plates(ups):
    _, html = _run("app.supermodules.eeg_neuro_lab.pages.run", ups)
    assert 'id="lamina-eeg_bands"' in html and 'id="lamina-eeg_1020"' in html
    assert "resaltados Fp1, Fp2, C3, C4" in html


def test_respiratory_lab_gallery_marks_the_sidebar_pattern():
    _, html = _run("app.supermodules.respiratory_lab.pages.run")
    assert 'id="lamina-respiratory_patterns"' in html
    assert html.count('class="bc-tile bc-on"') == 1


def test_academia_atlas_shows_every_plate(ups):
    at, html = _run("app.supermodules.academia.pages.run", ups)
    for key in ATLAS:
        assert f'id="lamina-{key}"' in html, key
    assert [t.label for t in at.tabs][:3] == [
        ":material/menu_book: Lecciones y Casos", ":material/photo_library: Atlas visual",
        ":material/smart_toy: Tutor IA"]


def test_twin_os_organ_cards_show_real_anatomy_with_status_colors(ups):
    at, html = _run("app.supermodules.twin_shell.pages.run", ups)
    cards = [m for m in re.findall(r"<div class='bc-organ'.*?</div></div>", html, re.S)]
    assert len(cards) == 5
    for card in cards:
        assert "<img" in card and ".webp" in card, "render de anatomía real, no un dibujo"
        assert any(c in card for c in (PALETTE.STABLE, PALETTE.WARNING, PALETTE.CRITICAL))
    assert 'id="lamina-conduction"' in html, "el panel del corazón muestra su lámina"
    assert len(at.get("plotly_chart")) >= 1, "el cuerpo 3D interactivo"


def test_calculators_mark_axis_on_hexaxial_plate_and_draw_news2_meter():
    _, html = _run("app.supermodules.calculators.pages.run")
    assert "eje marcado en" in html and 'id="lamina-hexaxial"' in html
    assert "Medidor NEWS2" in html
