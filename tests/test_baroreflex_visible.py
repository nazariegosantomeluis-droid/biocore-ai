"""
Cardiovascular profundo, sub-arco A (2026-10-19): el barorreflejo (brazo
vascular) hecho visible como CAPA sobre el motor -- traza del lazo cerrado,
saturación, convergencia; rótulos de honestidad (iteraciones, no segundos;
compliancia PENDING); motor intacto.
"""

import dataclasses
import json
import subprocess
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from domain.physiology.hemodynamics import (
    BAROREFLEX_MAX_RD,
    PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION,
    PHYSIOLOGICAL_RRCR_PARAMETERS,
    SEPSIS_MAX_RD_MMHG_S_ML,
    run_baroreflex,
    run_closed_loop,
    run_pathological_baroreflex,
)
from app.supermodules.twin_shell import baroreflex_panel as panel

_LABELS = {"healthy": "Sano", "hypertension": "Hipertensión", "sepsis": "Sepsis"}


def _run_panel(scenario=None, hr=None):
    def _script():
        from app.supermodules.twin_shell.baroreflex_panel import render_baroreflex_panel
        render_baroreflex_panel({"healthy": "Sano", "hypertension": "Hipertensión", "sepsis": "Sepsis"})

    at = AppTest.from_function(_script)
    at.run(timeout=60)
    if scenario is not None:
        at.selectbox(key="baroreflex_scenario").set_value(scenario)
        at.run(timeout=60)
    if hr is not None:
        at.slider(key=f"baroreflex_hr_{scenario}").set_value(hr)
        at.run(timeout=60)
    return at


def _markdown(at) -> str:
    return " ".join(m.value for m in at.markdown)


# --- La traza para los 3 escenarios ------------------------------------------

@pytest.mark.parametrize("scenario", ["healthy", "hypertension", "sepsis"])
def test_loop_trace_renders_for_each_enabled_scenario(scenario):
    at = _run_panel(scenario)
    assert at.exception == [], at.exception
    assert len(at.get("plotly_chart")) == 1
    assert "Comportamiento del lazo:" in _markdown(at)


def test_figure_draws_exactly_the_engine_trace_and_its_limits():
    """Dibujo = medición: los puntos son los ticks del motor; las líneas de
    referencia son los límites del escenario y la PAM objetivo del reflejo."""
    loop = run_closed_loop("sepsis", 150.0)
    target = run_pathological_baroreflex("sepsis", 150.0).target_map
    rd_min, rd_max = panel.rd_limits("sepsis")
    fig = panel.build_loop_figure(loop, target, rd_min, rd_max)

    rd, pam, gasto = fig.data[0], fig.data[1], fig.data[2]
    assert list(rd.x) == [t.tick for t in loop.ticks]
    assert list(rd.y) == [t.rd_after for t in loop.ticks]
    assert list(pam.y) == [t.map for t in loop.ticks]
    assert list(gasto.y) == pytest.approx([t.stroke_volume_ml * 150.0 / 1000 for t in loop.ticks])
    hlines = sorted(s.y0 for s in fig.layout.shapes if s.type == "line")
    assert hlines == sorted([rd_min, rd_max, target])
    assert rd_max == SEPSIS_MAX_RD_MMHG_S_ML and panel.rd_limits("healthy")[1] == BAROREFLEX_MAX_RD
    assert fig.layout.xaxis3.title.text == "Iteración hacia el equilibrio (no segundos)"


# --- El caso pedagógico de sepsis --------------------------------------------

def test_sepsis_shows_saturated_effector_and_shock_equilibrium():
    """Medido antes de construir: sepsis CONVERGE (no oscila) -- a un
    equilibrio de shock con Rd clavada en su techo séptico y la PAM muy por
    debajo del objetivo. La vista muestra eso, no un "no converge" que el
    motor no produce."""
    loop = run_closed_loop("sepsis", 150.0)
    assert loop.converged and not loop.oscillated and loop.clamped_at_max_rd
    assert loop.final_map < 65.0

    at = _run_panel("sepsis")
    md = _markdown(at)
    assert "Equilibrio con el efector saturado: Rd clavada en su techo de vasoconstricción" in md
    assert "descompensación" in md
    assert "saturada en el techo" in md
    marks = [c for c in at.get("plotly_chart") if "reflejo comanda el l" in c.proto.spec]
    assert marks, "las iteraciones saturadas se marcan en la traza"


def test_healthy_closes_the_error_without_saturating():
    at = _run_panel("healthy", hr=110)
    md = _markdown(at)
    assert "Equilibrio alcanzado" in md and "el reflejo cerró el error" in md
    assert "dentro de sus límites" in md


def test_isolated_reflex_vs_full_loop_contrast_comes_from_the_engine():
    """Con SV fijo el reflejo séptico compensa; al cerrar el lazo con
    retorno venoso cae a shock -- ambos números salen del motor."""
    isolated = run_pathological_baroreflex("sepsis", 150.0)
    loop = run_closed_loop("sepsis", 150.0)
    assert isolated.final_map > 85.0 > 65.0 > loop.final_map
    md = _markdown(_run_panel("sepsis"))
    assert f"**{isolated.final_map:.1f} mmHg**" in md and f"**{loop.final_map:.1f} mmHg**" in md


@pytest.mark.parametrize("converged, oscillated, expected", [
    (False, True, "Sin equilibrio: el lazo oscila"),
    (False, False, "Sin equilibrio en"),
])
def test_non_convergence_would_be_described_honestly(converged, oscillated, expected):
    loop = dataclasses.replace(run_closed_loop("healthy", 72.0), converged=converged, oscillated=oscillated)
    assert panel.describe_loop_outcome(loop, 93.3).startswith(expected)


# --- Los dos rótulos de honestidad -------------------------------------------

def test_iteration_label_and_compliance_pending_are_visible():
    at = _run_panel("sepsis")
    assert "iteración (no segundos)" in " ".join(i.value for i in at.info)
    assert PHYSIOLOGICAL_PARAMETERS_PENDING_VALIDATION is True
    warning = " ".join(w.value for w in at.warning)
    assert "Compliancia C pendiente de validación" in warning
    assert "S/D hereda el PENDING de la compliancia" in _markdown(at)
    # Streamlit 1.66 escapa los no-ASCII del JSON del gráfico: se lee el JSON, no se busca el texto crudo.
    layout = json.loads(at.get("plotly_chart")[0].proto.spec)["layout"]
    assert layout["xaxis3"]["title"]["text"] == "Iteración hacia el equilibrio (no segundos)"


def test_compliance_scope_claim_is_true_map_and_rd_do_not_depend_on_c():
    """El rótulo afirma que PAM y Rd no dependen de C -- se verifica, no se
    supone: C x0.5 / x2 deja PAM y Rd iguales; S/D sí cambian."""
    base = PHYSIOLOGICAL_RRCR_PARAMETERS
    runs = [run_baroreflex(110.0, base_params=dataclasses.replace(base, c=base.c * f)) for f in (0.5, 1.0, 2.0)]
    assert max(r.final_map for r in runs) - min(r.final_map for r in runs) < 0.05
    assert max(r.final_rd for r in runs) - min(r.final_rd for r in runs) < 1e-3
    assert runs[0].final_systolic_bp - runs[2].final_systolic_bp > 10.0


def test_vascular_arm_carries_validated_marker_and_cardiac_arm_is_declared_absent():
    at = _run_panel()
    md = _markdown(at)
    assert "✓" in md and "Guyton & Hall, Cap. 18" in md
    captions = " ".join(c.value for c in at.caption)
    assert "brazo cardíaco" in captions and "sub-arco B" in captions


def test_no_traffic_light_colors_in_the_loop_figure():
    from app.utils.design_system import PALETTE

    spec = _run_panel("sepsis").get("plotly_chart")[0].proto.spec
    for alarm in (PALETTE.STABLE, PALETTE.WARNING, PALETTE.CRITICAL):
        assert alarm not in spec


def test_pa_label_elsewhere_no_longer_claims_validated_while_compliance_is_pending():
    assert "compliancia C pendiente" in panel.pa_model_label()
    for path in ("app/supermodules/twin_shell/pages.py", "app/supermodules/academia/pages.py"):
        assert "(lazo cerrado, validado)" not in Path(path).read_text(encoding="utf-8")


# --- Página completa ----------------------------------------------------------

def test_digital_twin_os_renders_to_the_end_with_the_panel(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "baroreflex_page.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente barorreflejo (test)")

    def _script():
        import app.supermodules.twin_shell.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=60)
    assert at.exception == [], at.exception
    assert "Barorreflejo: el lazo cerrado por dentro" in _markdown(at)


# --- El motor, intacto ---------------------------------------------------------

_ENGINE_FILES = [
    "domain/physiology/hemodynamics/baroreflex.py",
    "domain/physiology/hemodynamics/r_rcr.py",
    "domain/physiology/hemodynamics/closed_loop.py",
    "domain/physiology/hemodynamics/pathological_tone.py",
    "domain/physiology/hemodynamics/physiological_flow.py",
]


def test_panel_is_a_read_layer_that_never_writes_to_the_ups():
    src = Path("app/supermodules/twin_shell/baroreflex_panel.py").read_text(encoding="utf-8")
    for forbidden in ("save_state", "append_descriptors", "compute_and_attach", "session_factory"):
        assert forbidden not in src


def test_engine_files_untouched_against_the_subarc_baseline():
    """Contra el commit base de este sub-arco (fc43fc5): el diff de los
    archivos del motor está vacío."""
    try:
        out = subprocess.run(
            ["git", "diff", "--stat", "fc43fc5", "--", *_ENGINE_FILES], capture_output=True, text=True, check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git o el commit base no disponibles en este entorno")
    assert out.strip() == "", f"el motor cambió:\n{out}"
