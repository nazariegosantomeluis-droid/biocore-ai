"""
Pieza 2 (2026-10-22): el cuerpo 3D del gemelo colorea por el UPS con la
MISMA función que el cuerpo SVG (`organ_visual_state`). El test central es
la paridad SVG = 3D en muchos estados, incluidas las 4 filas en las que el
3D del aporte externo (coloreado por `health_score` heurístico) contradecía
al SVG.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.engines.digital_twin_organism import DigitalTwinOrganism, OrganHealthStatus
from app.supermodules.twin_shell import ups_body_visual as U
from domain.physiology.state import (
    DomainState, EventSeverity, EventType, PhysiologicalEvent, Provenance, UnifiedPhysiologicalState,
    from_digital_twin_organism,
)
from visualization import anatomy3d as A3

ROOT = Path(__file__).resolve().parents[1]


def _state(sensors=None):
    org = DigitalTwinOrganism()
    if sensors:
        org.update_from_sensors(sensors)
    return from_digital_twin_organism(org, "paridad", provenance=Provenance.SIMULACION, source_detail="test")


def _events_without_data():
    now = datetime(2026, 10, 22, tzinfo=timezone.utc)

    def ev(et, dom, sev):
        return PhysiologicalEvent(event_type=et, domain=dom, severity=sev, description="t",
                                  provenance=Provenance.SIMULACION, confidence=0.5, timestamp=now)

    return UnifiedPhysiologicalState(
        patient_id="paridad", timestamp=now,
        cardiovascular=DomainState(domain="cardiovascular", descriptors={}),
        respiratory=DomainState(domain="respiratory", descriptors={}),
        neurological=DomainState(domain="neurological", descriptors={}),
        events=[ev(EventType.PULSE_NEWS2_3_POINTS, "cardiovascular", EventSeverity.CRITICAL)],
    )


CASES = {
    "sin_sensor": lambda: _state(),
    "fc130": lambda: _state({"ecg": {"heart_rate": 130, "hrv": 50}}),
    "fc60_hrv10": lambda: _state({"ecg": {"heart_rate": 60, "hrv": 10}}),
    "fc118_hrv15": lambda: _state({"ecg": {"heart_rate": 118, "hrv": 15}}),
    "fc72": lambda: _state({"ecg": {"heart_rate": 72, "hrv": 50}}),
    "fc160": lambda: _state({"ecg": {"heart_rate": 160, "hrv": 50}}),
    "spo2_93": lambda: _state({"respiratory": {"respiratory_rate": 18, "spo2": 93}}),
    "spo2_85": lambda: _state({"respiratory": {"respiratory_rate": 24, "spo2": 85}}),
    "eeg_estres": lambda: _state({"eeg": {"alpha_power": 20, "beta_power": 70, "stress_level": 85}}),
    "todo_critico": lambda: _state({"ecg": {"heart_rate": 160, "hrv": 15},
                                    "respiratory": {"respiratory_rate": 24, "spo2": 85},
                                    "eeg": {"alpha_power": 20, "beta_power": 70, "stress_level": 85}}),
    "eventos_sin_dato": _events_without_data,
    "none": lambda: None,
}
_SVG_CARD = {"heart": U._render_heart_card, "lungs": U._render_lungs_card, "brain": U._render_brain_card}


def _svg_color(organ, state):
    return re.search(r'fill="(#[0-9a-f]{6})"', _SVG_CARD[organ](state)).group(1)


def _figure_colors(state):
    visuals = U.organ_visual_state(state)
    fig = A3.body_figure(systems=A3.DEFAULT_SYSTEMS + ("abdominal",),
                         organ_colors={o: v.color for o, v in visuals.items()})
    by_label = {m.label: m for m in A3.load_body().meshes.values()}
    return {by_label[t.name].key: (t.color, t.opacity) for t in fig.data}


# --- La paridad: una fuente, dos renderizadores ----------------------------

@pytest.mark.parametrize("case", list(CASES))
def test_svg_and_3d_paint_each_modeled_organ_with_the_same_color(case):
    state = CASES[case]()
    visuals = U.organ_visual_state(state)
    colors3d = _figure_colors(state)
    for organ, parts in A3.UPS_ORGAN_PARTS.items():
        assert _svg_color(organ, state) == visuals[organ].color, (case, organ)
        for part in parts:
            assert colors3d[part][0] == visuals[organ].color, (case, organ, part)


@pytest.mark.parametrize("case, expected", [
    ("fc130", U.STABLE_COLOR),             # fase 0: 130 lpm = 2 puntos NEWS2, sin evento (antes WARNING por > 120)
    ("fc60_hrv10", U.STABLE_COLOR),        # fase 0: el evento por hrv < 20 se retiró
    ("fc118_hrv15", U.STABLE_COLOR),
    ("fc160", U.SEVERITY_COLOR[EventSeverity.WARNING]),   # 3 puntos NEWS2 (>= 131): el único evento de FC
    ("sin_sensor", U.NEUTRAL_COLOR),
])
def test_the_four_rows_that_used_to_diverge_now_match_the_ups(case, expected):
    """Antes, con el puntaje heurístico: FC 130, FC 60/HRV 10 y FC 118/HRV 15
    salían verdes en el 3D (ámbar en el SVG), y sin sensor salía ámbar. Fase 0: el evento de FC del UPS es la
    banda de 3 puntos NEWS2 (decisión 5), así que esas tres filas quedan verdes (con dato, sin evento) en ambos."""
    state = CASES[case]()
    assert _figure_colors(state)["heart"][0] == expected == _svg_color("heart", state)


def test_no_sensor_is_grey_no_data_not_the_fabricated_alert():
    org = DigitalTwinOrganism()
    # Fase 1: el organismo sin alimentar NO tiene puntaje (antes 50 = «alerta»): sin dato, en gris, sin estado.
    assert org.organs["heart"].metrics.health_score is None and org.organs["heart"].status is None
    assert org.organs["heart"].color == U.NEUTRAL_COLOR
    visual = U.organ_visual_state(_state())["heart"]
    assert visual == (U.NEUTRAL_COLOR, "sin dato", False, None)
    color, label = visual[:2]
    assert color == U.NEUTRAL_COLOR and label == "sin dato"


# --- Los dos neutros --------------------------------------------------------

@pytest.mark.parametrize("case", ["todo_critico", "fc160", "sin_sensor", "none"])
def test_unmodeled_anatomy_never_takes_a_state_color(case):
    state_colors = {U.STABLE_COLOR, U.NEUTRAL_COLOR, *U.SEVERITY_COLOR.values()}
    modeled = {p for parts in A3.UPS_ORGAN_PARTS.values() for p in parts}
    colors3d = _figure_colors(CASES[case]())
    unmodeled = {k: v for k, v in colors3d.items() if k not in modeled}
    assert {"arteries", "veins", "pulmonary_veins", "spinal_cord", "liver"} <= set(unmodeled)
    for key, (color, opacity) in unmodeled.items():
        assert color not in state_colors, key
        assert color == A3._blend(A3.TISSUE_COLOR[key], A3.UNMODELED_TOWARD, A3.UNMODELED_BLEND), key
        assert opacity == A3.UNMODELED_OPACITY, key


def test_arteries_are_attenuated_away_from_the_critical_red():
    attenuated = A3._blend(A3.TISSUE_COLOR["arteries"], A3.UNMODELED_TOWARD, A3.UNMODELED_BLEND)
    red = U.SEVERITY_COLOR[EventSeverity.CRITICAL]

    def rgb(h):
        return [int(h[i:i + 2], 16) for i in (1, 3, 5)]

    distance = sum((a - b) ** 2 for a, b in zip(rgb(attenuated), rgb(red))) ** 0.5
    assert distance > 100, f"{attenuated} demasiado parecido al rojo crítico {red}"


def test_reference_lab_stays_static_without_organ_colors():
    fig = A3.body_figure()
    by_label = {m.label: m for m in A3.load_body().meshes.values()}
    for t in fig.data:
        assert t.color == A3.TISSUE_COLOR[by_label[t.name].key]


# --- UI: estado None, leyenda, rótulo, Twin OS -----------------------------

def _render(state_factory_name):
    from streamlit.testing.v1 import AppTest

    def _script(name):
        import tests.test_ups_body_3d_paridad as T
        from app.supermodules.twin_shell.ups_body_visual import render_ups_body
        render_ups_body(T.CASES[name](), with_3d=True, key="t")

    at = AppTest.from_function(_script, args=(state_factory_name,), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def test_none_state_renders_three_grey_organs_with_notice_and_3d():
    at = _render("none")
    captions = " ".join(c.value for c in at.caption)
    assert "Sin snapshot del UPS todavía" in captions
    assert len(at.get("plotly_chart")) == 1
    md = " ".join(m.value for m in at.markdown)
    assert md.count(f'fill="{U.NEUTRAL_COLOR}"') >= 3


def test_3d_shows_five_entry_legend_and_its_label():
    from app.supermodules.twin_shell.ups_body_3d import UPS_BODY_3D_NOTE, legend_entries

    at = _render("fc130")
    md = " ".join(m.value for m in at.markdown)
    assert len(legend_entries()) == 5
    for color, text in legend_entries():
        assert color in md and text in md
    assert "Sin dato (órgano modelado" in md and "anatomía sin dominio en el UPS" in md
    assert UPS_BODY_3D_NOTE in " ".join(c.value for c in at.caption)
    assert UPS_BODY_3D_NOTE.startswith("Color según el estado del UPS; geometría de un sujeto de referencia")


def test_digital_twin_os_draws_svg_and_3d_from_one_state(tmp_path):
    from streamlit.testing.v1 import AppTest

    from app.supermodules.twin_shell.ups_body_3d import UPS_BODY_3D_NOTE
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "ups_3d.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente 3D (test)")

    def _script():
        import app.supermodules.twin_shell.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=120)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    assert not at.exception, at.exception
    assert UPS_BODY_3D_NOTE in " ".join(c.value for c in at.caption)
    src = (ROOT / "app/supermodules/twin_shell/pages.py").read_text(encoding="utf-8")
    assert 'render_ups_body(get_current_physiological_state(organism, patient_id), with_3d=True' in src


# --- La fuente heurística no existe; el UPS y el motor, intactos ------------

def test_3d_never_reads_the_heuristic_organ_status():
    for path in ("app/supermodules/twin_shell/ups_body_3d.py", "visualization/anatomy3d.py"):
        src = (ROOT / path).read_text(encoding="utf-8")
        for banned in ("organism", "health_score)", ".status", "ORGAN_STATUS_COLOR", "TWIN_ORGAN_PARTS"):
            code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
            code = re.sub(r'""".*?"""', "", code, flags=re.S)
            assert banned not in code, (path, banned)


def test_ups_builder_schema_and_engine_untouched():
    try:
        out = subprocess.run(["git", "diff", "--stat", "HEAD", "--", "domain/"],
                             capture_output=True, text=True, check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git no disponible")
    assert out.strip() == ""
