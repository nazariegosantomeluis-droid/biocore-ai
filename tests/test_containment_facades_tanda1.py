"""Tanda 1 de contención de fachadas vivas (2026-11-05, Art. I).

Hallazgos del inventario `docs/INVENTARIO_BIOCORE_2026-11-05.md`:
- Respiratory Lab escribía al UPS FR = 60.0 y AHI = 0 constantes (el analizador no las calcula
  de la señal) bajo una insignia VALIDATED y con interpretaciones clínicas derivadas.
- "Analizar Entropía y Complejidad" calculaba |media(diff(x))|, la deriva neta.
- Etiquetas que prometían IA/ML inexistentes ("Tutor IA", "SHAP/LIME real", "ML real").

Estas pruebas fijan la CONTENCIÓN (retirar o marcar lo que afirma algo falso), no la reparación del
cálculo respiratorio, que es su propio arco. Todo corre contra una base temporal.
"""

import ast
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RESP_DIR = Path("app/supermodules/respiratory_lab")


@pytest.fixture
def temp_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "contencion_tanda1.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente contención (test)")
    return sf, pid


def _snapshot_count(sf) -> int:
    from sqlalchemy import text

    with sf() as s:
        return s.execute(text("select count(*) from ups_snapshots")).scalar_one()


def _respiratory_app(sf, pid, pattern=None):
    def _script():
        import app.supermodules.respiratory_lab.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=60)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    if pattern is not None:
        at.sidebar.selectbox[0].select(pattern).run()
    return at


def _all_text(at) -> str:
    parts = []
    for coll in (at.markdown, at.caption, at.info, at.warning, at.success, at.error, at.header, at.subheader):
        parts.extend(str(e.value) for e in coll)
    parts.extend(b.label for b in at.button)
    parts.extend(t.label for t in at.tabs)
    parts.extend(e.label for e in at.expander)
    return "\n".join(parts)


# --- Parte A: Respiratory Lab ------------------------------------------------

def test_respiratory_lab_ups_write_path_lives_only_in_views_and_only_for_fr_and_spo2():
    """Fase 4 (2026-11-09): «Guardar al gemelo» vuelve, pero con UN solo camino de escritura (views.py) y solo para los
    dos valores que significan lo mismo que un campo del UPS. page_content.py y pages.py no escriben nada."""
    for path in RESP_DIR.glob("*.py"):
        code = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
        tree = ast.parse(code)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
        }
        if path.name != "views.py":
            for forbidden in ("save_state", "from_digital_twin_organism", "update_from_sensors", "get_active_session_factory"):
                assert forbidden not in names, f"{path.name} escribe al UPS fuera de views.py ({forbidden})"
        else:
            strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
            assert "ahi" not in strings, "la tasa por hora de registro NO se escribe como AHI"
            assert {"respiratory_rate", "spo2"} <= strings


def test_respiratory_lab_pressing_any_button_but_the_explicit_save_writes_nothing_to_the_ups(temp_ups):
    sf, pid = temp_ups
    at = _respiratory_app(sf, pid)
    assert at.exception == []
    assert any("Guardar FR y SpO₂ basal al gemelo" in b.label for b in at.button), "la fase 4 reactiva el guardado explícito"
    for i in range(len(at.button)):
        if "Guardar FR y SpO₂ basal" in at.button[i].label:
            continue
        fresh = _respiratory_app(sf, pid)
        fresh.button[i].click().run()
        assert fresh.exception == []
    assert _snapshot_count(sf) == 0


def test_respiratory_quiz_no_longer_derives_answers_from_the_analyzer(temp_ups):
    sf, pid = temp_ups
    at = _respiratory_app(sf, pid)
    quiz = [r for r in at.radio if r.label.startswith("Seleccionar Tipo de Pregunta")]
    assert quiz, "el selector de tipo de pregunta debe existir"
    assert "Identificar Patrón" not in quiz[0].options and "AHI y Severidad" not in quiz[0].options


# --- Parte B: la "entropía" que no lo era ------------------------------------

def test_entropy_complexity_button_is_gone_from_every_page(temp_ups):
    import ast as _ast

    sf, pid = temp_ups
    src = Path("app/main.py").read_text(encoding="utf-8")
    hubs = _ast.literal_eval(re.search(r"^HUBS = (\{.*?^\})", src, re.S | re.M).group(1))
    pages = [(hub, page) for hub, ps in hubs.items() for page in ps]
    assert len(pages) >= 12
    for hub, page in pages:
        at = AppTest.from_file(str(Path("app/main.py").resolve()), default_timeout=120)
        at.session_state["biocore_ai_entry_done"] = True
        at.session_state["selected_hub"] = hub
        at.session_state["selected_page"] = page
        at.session_state["twin_shell_ups_session_factory"] = sf
        at.session_state["twin_shell_ups_patient_id"] = pid
        at.run()
        assert at.exception == [], f"{page}: {at.exception}"
        text = _all_text(at)
        # Solo la palabra en español: la cita en inglés de SampEn (Richman & Moorman 2000, "approximate
        # entropy and sample entropy") es la entropía REAL de HRV Analysis y debe seguir.
        assert not re.search(r"entrop[ií]a", text, re.I), f"{page}: aparece 'Entropía'"
        assert "Analizar Entrop" not in text, page
        assert "Complejidad Dinámica" not in text and "Descubrimiento Científico" not in text, page


def test_discovery_layer_function_is_not_defined_or_called_anywhere():
    for path in Path("app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
        }
        assert "render_scientific_discovery_layer" not in defined | used, path


# --- Parte C: etiquetas que prometían IA/ML inexistentes -----------------------

def test_academia_has_no_tutor_ia_tab(temp_ups):
    sf, pid = temp_ups

    def _script():
        import app.supermodules.academia.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=60)
    at.run()
    assert at.exception == []
    assert "Tutor IA" not in _all_text(at)
    assert not any("Tutor" in t.label for t in at.tabs)


def test_twin_os_labels_say_what_they_are(temp_ups):
    sf, pid = temp_ups

    def _script():
        import app.supermodules.twin_shell.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=120)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run()
    assert at.exception == []
    labels = " | ".join(e.label for e in at.expander)
    assert "ML real" not in labels
    assert "Índice de riesgo heurístico (pesos fijos, sin entrenamiento)" in labels


def test_shap_lime_narratives_no_longer_claim_a_perturbation_or_a_model():
    from src.interpretability import DEFAULT_FEATURE_BASELINES, lime_like_explanation, shap_like_explanation

    features = {k: v * 1.5 for k, v in DEFAULT_FEATURE_BASELINES.items()}
    text = "\n".join(shap_like_explanation(features, "Ritmo X") + lime_like_explanation(features, "Ritmo X"))
    assert text.strip()
    for forbidden in ("vecindario", "alteran", "el modelo combina", "estilo LIME"):
        assert forbidden not in text
    assert "no es SHAP" in text and "no es LIME" in text


def test_ui_source_has_no_shap_lime_real_or_ml_real_claims():
    for path in list(Path("app").rglob("*.py")) + [Path("domain/physiology/ml/ecg_classification.py")]:
        src = path.read_text(encoding="utf-8")
        assert "SHAP/LIME real" not in src and "ML real" not in src, path


# --- Tanda 1.5 (2026-11-05): cerrar la contencion + aislar la suite ------------

def test_ecg12_quiz_no_longer_claims_ai_that_does_not_exist():
    for path in list(Path("app").rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        assert "inferencias IA" not in src and "análisis IA" not in src, path


def test_dead_explainability_module_is_buried_and_no_lime_style_claim_survives():
    assert not Path("src/ai/explainability.py").exists()
    import src.ai as ai

    assert not hasattr(ai, "grad_cam") and not hasattr(ai, "saliency_map")
    for root in ("app", "src", "domain", "clinical"):
        for path in Path(root).rglob("*.py"):
            assert "LIME-style" not in path.read_text(encoding="utf-8"), path


def test_narrator_model_id_is_the_current_one_everywhere_in_code():
    from domain.physiology.narrator.client import DEFAULT_MODEL

    assert DEFAULT_MODEL == "claude-opus-5-5"
    for root in ("app", "src", "domain", "clinical", "tests"):
        for path in Path(root).rglob("*.py"):
            if path.name == "test_containment_facades_tanda1.py":
                continue
            assert "claude-opus-4-8" not in path.read_text(encoding="utf-8"), path


def test_suite_never_points_at_the_development_database():
    import domain.physiology.state.db as db

    dev = (Path(db.__file__).resolve().parents[3] / "data" / "biocore_ups.db").resolve()
    assert Path(db.DEFAULT_DB_PATH).resolve() != dev, "conftest.py debe redirigir la base de la suite"


# --- Tanda 2 (2026-11-07): textos de UI que caducaron ---------------------------

def test_twin_os_causal_message_lists_the_domains_the_schema_models(temp_ups):
    from domain.physiology.state import DomainState, UnifiedPhysiologicalState
    from datetime import datetime, timezone

    sf, pid = temp_ups

    def _script():
        import app.supermodules.twin_shell.pages as m
        m.run()

    at = AppTest.from_function(_script, default_timeout=120)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.session_state["twin_shell_selected_organ"] = "brain"
    at.run()
    assert at.exception == []
    modelados = list(UnifiedPhysiologicalState(
        patient_id="", timestamp=datetime.now(timezone.utc),
        cardiovascular=DomainState(domain="cardiovascular"), respiratory=DomainState(domain="respiratory"),
    ).all_domains())
    text = " ".join(str(e.value) for e in at.info)
    assert f"El UPS modela hoy {len(modelados)} dominios ({', '.join(modelados)})" in text
    assert "solo cardiovascular y respiratorio" not in text


# --- Contención 2 + fase 2a del arco respiratorio (2026-11-07, Art. I) -------------------------------------------

import base64  # noqa: E402
import json  # noqa: E402

import numpy as np  # noqa: E402

def _plotly_traces(chart):
    """{nombre: y} de un st.plotly_chart de AppTest (plotly puede codificar y en binario)."""
    spec = json.loads(chart.proto.spec)
    out = {}
    for t in spec["data"]:
        y = t["y"]
        if isinstance(y, dict):
            y = np.frombuffer(base64.b64decode(y["bdata"]), dtype=y["dtype"])
        out[t.get("name")] = np.array(y, dtype=float)
    return out, spec


def _number_input(at, label):
    return [n for n in at.sidebar.number_input if n.label == label][0]


def _clinical_flow(at):
    traces, _ = _plotly_traces(at.get("plotly_chart")[0])
    return traces["Flujo de Aire"]


def test_expiration_control_is_active_default_is_automatic_and_moves_the_signal(temp_ups):
    sf, pid = temp_ups
    at = _respiratory_app(sf, pid)
    exp = _number_input(at, "Tiempo Espiración (s)")
    assert exp.disabled is False and exp.value == 0.0  # 0 = automático = el comportamiento de siempre
    base = _clinical_flow(at)
    exp.set_value(1.0).run()
    assert at.exception == []
    moved = _clinical_flow(at)
    assert base.shape == moved.shape and not np.allclose(base, moved)
    assert "automático" in (exp.help or "")


@pytest.mark.parametrize("label,new_value", [
    ("Frecuencia Respiratoria (resp/min)", 25), ("Volumen Corriente (L)", 1.0), ("Tiempo Inspiración (s)", 1.5),
    ("Tiempo Espiración (s)", 1.0),
])
def test_every_clinical_control_that_claims_to_shape_the_signal_does(temp_ups, label, new_value):
    sf, pid = temp_ups
    at = _respiratory_app(sf, pid)
    base = _clinical_flow(at)
    _number_input(at, label).set_value(new_value).run()
    assert at.exception == []
    assert not np.allclose(base, _clinical_flow(at)), f"'{label}' no mueve la señal"


@pytest.mark.parametrize("key,new_value", [("resp_sim_rr", 30), ("resp_sim_tv", 1.2)])
def test_every_simulation_slider_moves_the_signal(temp_ups, key, new_value):
    sf, pid = temp_ups
    at = _respiratory_app(sf, pid)
    base, _ = _plotly_traces(at.get("plotly_chart")[-1])
    [s for s in at.slider if s.key == key][0].set_value(new_value).run()
    assert at.exception == []
    moved, _ = _plotly_traces(at.get("plotly_chart")[-1])
    assert not np.allclose(base["Flujo de aire"], moved["Flujo de aire"]), key
    assert not np.allclose(base["Pared torácica"], moved["Pared torácica"]), key


def test_cycles_card_is_labeled_as_a_computed_target_not_a_measurement(temp_ups):
    sf, pid = temp_ups
    at = _respiratory_app(sf, pid)
    text = _all_text(at)
    assert "Ciclos objetivo en 30 s (calculado de la FR elegida, no medido)" in text
    assert "Ciclos respiratorios en 30s" not in text
