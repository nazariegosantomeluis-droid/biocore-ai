"""Fase 1 de la propuesta, tanda 1, PARTE B (2026-11-15): sistema de diseño mínimo.

- Tokens: `PALETTE` es la única fuente; `.streamlit/config.toml` la copia y debe coincidir.
- Contraste WCAG de cada par de `CONTRAST_PAIRS` (4.5:1 texto, 3:1 objeto gráfico).
- Ningún color hexadecimal fuera de `design_system.py` en la app (salvo la lista explícita de abajo).
- Etiquetas de procedencia con TEXTO (decisión 3); un solo «sin dato» que dice qué falta (decisión 5).
"""

import re
import tomllib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.utils import design_system as DS
from app.utils.design_system import BADGES, CONTRAST_PAIRS, PALETTE, contrast_ratio

APP = Path("app")
# Paletas que NO son de estado ni de la interfaz: anatomía del laboratorio 3D (colores de tejido), el exporte
# autónomo (papel blanco) y el entrenador de ECG huérfano (no se enruta; no se borra por decisión firmada).
HEX_ALLOWLIST = {"app/utils/design_system.py", "app/reporting.py", "app/ecg_trainer.py"}
HEX_ALLOWLIST_DIRS = ("app/supermodules/model3d/",)


@pytest.mark.parametrize("fg, bg, minimum", CONTRAST_PAIRS)
def test_every_token_pair_meets_its_wcag_minimum(fg, bg, minimum):
    ratio = contrast_ratio(getattr(PALETTE, fg), getattr(PALETTE, bg))
    assert ratio >= minimum, f"{fg} sobre {bg}: {ratio:.2f}:1 < {minimum}:1"


def test_the_contrast_formula_matches_the_wcag_reference_values():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


def test_config_toml_is_a_copy_of_the_palette_and_there_is_one_theme():
    theme = tomllib.loads(Path(".streamlit/config.toml").read_text(encoding="utf-8"))["theme"]
    assert theme["base"] == "dark"
    assert theme["primaryColor"].lower() == PALETTE.PRIMARY
    assert theme["backgroundColor"].lower() == PALETTE.BACKGROUND
    assert theme["secondaryBackgroundColor"].lower() == PALETTE.SECONDARY_BACKGROUND
    assert theme["textColor"].lower() == PALETTE.TEXT
    assert theme["codeTextColor"].lower() == PALETTE.TEXT      # el verde por defecto no llegaba a AA (medido renderizado)
    assert theme["font"] == "sans-serif"                                   # la de Streamlit, sin servicio externo
    assert not any(k in theme for k in ("light", "dark"))                  # un solo tema


def test_one_state_palette_no_second_green_or_red_anywhere_in_the_app():
    offenders = []
    for path in APP.rglob("*.py"):
        rel = path.as_posix()
        if rel in HEX_ALLOWLIST or rel.startswith(HEX_ALLOWLIST_DIRS):
            continue
        code = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        found = re.findall(r"(?<![\w&])#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", code)
        if found:
            offenders.append((rel, sorted(set(found))))
    assert offenders == [], offenders


def test_the_heuristic_risk_predictor_does_not_carry_its_own_colors():
    src = Path("src/ai/patient_analytics.py").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{6}", src)


def test_no_primary_buttons_because_white_on_primary_would_fail_aa():
    assert contrast_ratio("#ffffff", PALETTE.PRIMARY) < 4.5                # la razón de la regla
    for path in APP.rglob("*.py"):
        assert 'type="primary"' not in path.read_text(encoding="utf-8"), path


def test_provenance_badges_are_text_never_a_colored_circle():
    for name in ("CLINICAL", "HEURISTIC", "GHOST", "METHOD", "PENDING", "SIMULATION"):
        badge = getattr(BADGES, name)
        assert re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúñ ]+", badge), badge          # solo palabras
        assert BADGES.label(badge).startswith(badge) and BADGES.tag(badge) == f"[{badge}]"
    assert BADGES.CLINICAL == "Validado por fuente" and BADGES.METHOD == "Criterio BIOCORE"
    html = DS.badge_html(BADGES.HEURISTIC)
    assert PALETTE.NEUTRAL in html and BADGES.label(BADGES.HEURISTIC) in html
    for color in (PALETTE.STABLE, PALETTE.WARNING, PALETTE.CRITICAL):
        assert color not in html                                            # el color es del estado clínico


def test_no_provenance_circle_left_in_the_ui_code():
    for path in APP.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            # 🟣 y ⏳ solo existían como insignias de procedencia; 🟢/🔵 siguen en clasificaciones con su palabra
            assert "🟣" not in line and "⏳ PENDING" not in line, (path, n, line)


def test_badge_aliases_and_dead_duplicates_are_gone():
    main = Path("app/main.py").read_text(encoding="utf-8")
    assert "BIOMARKER_CLINICAL_BADGE" not in main and "def render_metrics_grid" not in main
    assert "PROVENANCE_CLINICAL_BADGE" not in Path("app/supermodules/twin_shell/pages.py").read_text(encoding="utf-8")
    legacy = Path("app/utils.py").read_text(encoding="utf-8")
    assert "def render_metric_explained" not in legacy and "def render_view_selector" not in legacy
    from app.engines import digital_twin_organism, prediction_engine

    assert prediction_engine.NO_DATA is digital_twin_organism.NO_DATA


def test_state_colors_elsewhere_read_the_tokens():
    from app.engines import digital_twin_organism as dto
    from app.supermodules.twin_shell import ups_body_visual as U

    assert dto.NO_DATA_COLOR == U.NEUTRAL_COLOR == PALETTE.NEUTRAL
    assert set(dto.NEWS2_POINTS_COLOR.values()) == {PALETTE.STABLE, PALETTE.WARNING, PALETTE.CRITICAL}
    assert set(U.SEVERITY_COLOR.values()) | {U.STABLE_COLOR} == {PALETTE.STABLE, PALETTE.WARNING, PALETTE.CRITICAL}


def test_one_no_data_component_says_what_is_missing():
    html = DS.no_data_html("FC actual", "no llegó")
    assert "Sin dato: falta FC actual — no llegó" in html and PALETTE.NEUTRAL in html and "biocore-no-data" in html

    def _script():
        from app.utils.design_system import render_metric_card
        render_metric_card("Frecuencia cardíaca", None, unavailable_reason="el detector no encontró picos R")

    at = AppTest.from_function(_script)
    at.run()
    (card,) = [m.value for m in at.markdown]
    assert "Sin dato: falta Frecuencia cardíaca — el detector no encontró picos R" in card
    assert "biocore-no-data" in card and 'data-label="Frecuencia cardíaca"' in card


def test_the_global_theme_does_not_ask_for_an_unloaded_font():
    import inspect

    assert "Inter" not in inspect.getsource(DS.inject_global_theme)
