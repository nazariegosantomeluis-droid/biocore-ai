"""Tanda 2D (2026-10-24): mapa EEG 3D con el rótulo corregido y ML de pacientes con guardia anti-fuga.

Verdad independiente donde se puede:
- spline: propiedad de interpolación, campo constante y un campo analítico
  conocido (armónico esférico de grado 1) muestreado en los 21 electrodos;
- gris >45 mm: distancias recalculadas aquí desde la geometría;
- tramo CAP: la señal es la del aporte bit a bit (sha256) y su alfa relativa
  se recalcula con Welch, no se lee del rótulo;
- fuga por ID: una tabla de RUIDO con un ID ordenado; sin guardia el aporte daba
  AUC 1.000 con el ID como variable principal y ningún aviso.
"""
import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CAP_SIGNALS_SHA256 = "bd45c85f5eb46270"  # prefijo del int16 del aporte (respaldo-mezcla-20261021)


def _unit(p, center):
    d = np.asarray(p, float) - center
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def _scalp_and_electrodes():
    from visualization import anatomy3d as A3

    head = A3.load_head()
    scalp = head["scalp_lo"] if "scalp_lo" in head.meshes else head["scalp"]
    return A3, scalp, np.asarray(head.electrode_xyz, float), list(head.electrode_names)


# ═══ Spline esférico (Perrin 1989) ═══════════════════════════════════════════

def test_spline_parameters_are_perrin_m4_50_terms_lambda_1e5():
    from visualization.anatomy3d import spherical_spline

    p = inspect.signature(spherical_spline).parameters
    assert (p["m"].default, p["n_terms"].default, p["smoothing"].default) == (4, 50, 1e-5)


def test_spline_interpolates_and_keeps_a_constant_field():
    A3, scalp, xyz, _ = _scalp_and_electrodes()
    vals = np.linspace(-3, 5, len(xyz))
    assert np.allclose(A3.spherical_spline(xyz, vals, xyz, smoothing=1e-9), vals, atol=1e-3)
    assert np.allclose(A3.spherical_spline(xyz, np.full(len(xyz), 7.0), scalp.vertices), 7.0, atol=1e-6)


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_spline_recovers_a_known_degree_one_harmonic(axis):
    """v = componente del vector unitario: se conoce su valor en TODO el cuero
    cabelludo, no solo en los electrodos. Medido: error máx 0.5 % del rango."""
    A3, scalp, xyz, _ = _scalp_and_electrodes()
    truth_e = _unit(xyz, A3.HEAD_CENTER)[:, axis]
    truth_v = _unit(scalp.vertices, A3.HEAD_CENTER)[:, axis]
    near = np.min(np.linalg.norm(scalp.vertices[:, None, :] - xyz[None], axis=2), axis=1) <= A3.MAP_REACH_MM
    err = np.abs(A3.spherical_spline(xyz, truth_e, scalp.vertices) - truth_v)[near]
    assert err.max() < 0.02 * np.ptp(truth_e)


def test_map_is_grey_beyond_45_mm_of_every_electrode():
    A3, scalp, _, _ = _scalp_and_electrodes()
    values = {"Fp1": 1.0, "Fp2": 2.0, "F3": 3.0, "F4": 4.0}
    fig = A3.head_figure(values=values, show_brain=False)
    assert fig.layout.meta["mapped"] and fig.layout.meta["points"] == 4
    src = np.stack([A3.electrode_point(n)[1] for n in values])
    dist = np.min(np.linalg.norm(scalp.vertices[:, None, :] - src[None], axis=2), axis=1)
    level = np.asarray(next(t for t in fig.data if t.name == "Mapa sobre el cuero cabelludo").intensity)
    assert np.all(level[dist > 45.0] == 0.0) and np.all(level[dist <= 45.0] >= 0.1)
    assert not A3.head_figure(values={"Fp1": 1, "Cz": 2}).layout.meta["mapped"], "con <4 puntos no se interpola"


def test_bipolar_midpoint_and_reference_outside_the_model():
    A3, _, xyz, names = _scalp_and_electrodes()
    pos = dict(zip(names, xyz))
    label, p = A3.electrode_point("P4-O2")
    assert label == "P4-O2"
    # "Punto medio llevado al cuero cabelludo": sobre el arco P4-O2, cerca de su mitad, al radio medio.
    u = _unit(np.stack([p, pos["P4"], pos["O2"]]), A3.HEAD_CENTER)
    ang = lambda a, b: float(np.arccos(np.clip(a @ b, -1, 1)))  # noqa: E731
    arc = ang(u[1], u[2])
    assert ang(u[0], u[1]) + ang(u[0], u[2]) == pytest.approx(arc, abs=1e-9)
    assert 0.4 * arc < ang(u[0], u[1]) < 0.6 * arc
    r = (np.linalg.norm(pos["P4"] - A3.HEAD_CENTER) + np.linalg.norm(pos["O2"] - A3.HEAD_CENTER)) / 2
    assert np.linalg.norm(p - A3.HEAD_CENTER) == pytest.approx(r, rel=1e-9)
    # El aporte dibujaba C4-A1 como "C4": A1 (oreja) no está en el modelo.
    label, p = A3.electrode_point("C4-A1")
    assert label == "C4-A1" and np.allclose(p, pos["C4"])
    assert A3.electrode_point("T3")[0] == "T7" and A3.electrode_point("XX") is None


def test_overshoot_is_measured_and_depends_on_the_montage():
    """El diagnóstico citaba 7 %: con el montaje 10-20 completo es ~0 %, con las
    5 derivaciones derechas del CAP es mucho más (casi todo es extrapolación)."""
    from app.supermodules.model3d.panels import relative_band_power
    from src.signals.reference_recordings import cap_n16

    A3, _, xyz, names = _scalp_and_electrodes()
    full = A3.head_figure(values=dict(zip(names, -xyz[:, 1] / 50.0)), show_brain=False)
    assert full.layout.meta["clipped_fraction"] < 0.02
    d = cap_n16()
    rel = relative_band_power(d["leads"], d["fs"])
    cap = A3.head_figure(values={ch: v["alpha"] for ch, v in rel.items()}, show_brain=False)
    assert cap.layout.meta["clipped_fraction"] > 0.10


# ═══ El tramo CAP n16 y su rótulo ════════════════════════════════════════════

def _cap_npz():
    with np.load(ROOT / "data" / "reference_signals" / "cap_n16.npz", allow_pickle=False) as z:
        return z["signals"].copy(), json.loads(bytes(z["meta"]).decode("utf-8"))


def test_cap_npz_is_the_aporte_signal_with_an_honest_label():
    sig, meta = _cap_npz()
    assert sig.dtype == np.int16 and hashlib.sha256(sig.tobytes()).hexdigest().startswith(CAP_SIGNALS_SHA256)
    assert "seleccionado por su contenido de alfa" in meta["detail"] and "no por el hipnograma" in meta["detail"]
    assert "vigilia tranquila" not in json.dumps(meta, ensure_ascii=False)
    assert "W (vigilia)" in meta["hypnogram_check"] and "no consta" in meta["hypnogram_check"]
    assert meta["segment_s"] == [660.0, 690.0]


def test_cap_segment_really_is_alpha_rich_recomputed_from_the_signal():
    """El criterio de selección, recalculado aquí con Welch (8-13 / 1-30 Hz)."""
    from scipy.signal import welch

    sig, meta = _cap_npz()
    x = sig[:, meta["leads"].index("P4-O2")] * meta["step"]
    f, p = welch(x - x.mean(), meta["fs"], nperseg=256)
    rel = p[(f >= 8) & (f < 13)].sum() / p[(f >= 1) & (f < 30)].sum()
    assert rel == pytest.approx(meta["alpha_relative_p4o2"], abs=0.02)


def test_build_tool_cannot_reintroduce_the_circular_label():
    """Lo que escribiría una regeneración del archivo (la herramienta, no el comentario que cita lo viejo)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_reference_signals", ROOT / "tools" / "build_reference_signals.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    detail = tool.SOURCES["cap_n16"]["detail"]
    assert "vigilia" not in detail and "no por el hipnograma" in detail
    _, meta = _cap_npz()
    assert meta["detail"] == detail and meta["hypnogram_check"] == tool.CAP_N16_HYPNOGRAM_CHECK


def _m3d_page():
    from app.supermodules.model3d.pages import run
    run()


def _text(at):
    return "\n".join([m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
                     + [w.value for w in at.warning])


def test_eeg_tab_renders_with_the_honest_label_and_no_circular_claim():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_m3d_page, default_timeout=180).run()
    assert not at.exception, at.exception
    text = _text(at)
    for honest in ("seleccionado por su contenido de alfa", "no por el hipnograma",
                   "criterio de selección, no un hallazgo", "queda en gris", "Sobreoscilación",
                   "buena parte del color es extrapolación", "C4-A1 va en C4"):
        assert honest in text, honest
    for circular in ("despierta y relajada", "persona sana, relajada", "vigilia tranquila", "alfa posterior"):
        assert circular not in text, circular
    # Abre en la primera banda, no en la del criterio de selección.
    assert at.session_state["m3d_eeg_ref_band"] == "delta"


# ═══ ML de pacientes: la guardia anti-fuga por ID ════════════════════════════

def _noise_table_sorted_by_diagnosis(n=200, id_name="codigo", id_values=None, seed=1):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(rng.normal(size=(n, 6)), columns=[f"medida_{i}" for i in range(6)])  # sin señal
    df.insert(0, id_name, np.arange(1001, 1001 + n) if id_values is None else id_values)
    df["diagnostico"] = ["A"] * (n // 2) + ["B"] * (n - n // 2)
    return df


def test_ordered_id_no_longer_gives_a_silent_auc_of_one():
    """EL test de la tanda. Con la guardia: el ID se excluye, se avisa y el AUC
    es el del ruido. (El aporte: AUC 1.000, «codigo» primera, cero avisos.)"""
    from src.ml.cohort_map import build_cohort_map

    cm = build_cohort_map(_noise_table_sorted_by_diagnosis(), target="diagnostico")
    assert "codigo" in cm.id_excluded and "codigo" not in cm.features
    assert any("codigo" in w and "posible fuga por ID" in w for w in cm.warnings)
    assert cm.model.auc < 0.8 and "codigo" not in cm.model.importances


@pytest.mark.parametrize("name", ["id", "ID_paciente", "patient_id", "Unnamed: 0", "folio", "NHC"])
def test_id_by_name_is_excluded_even_if_the_table_is_shuffled(name):
    from src.ml.cohort_map import build_cohort_map

    rng = np.random.default_rng(3)
    df = _noise_table_sorted_by_diagnosis(id_name=name, id_values=rng.permutation(200)).sample(frac=1, random_state=3)
    cm = build_cohort_map(df, target="diagnostico")
    assert name in cm.id_excluded and "nombre" in cm.id_excluded[name]


def test_second_net_flags_a_non_integer_column_that_follows_the_order():
    """Una columna decimal y ordenada (p. ej., una hora de registro) no tiene
    forma de ID, pero filtra igual: el aviso sale después de entrenar."""
    from src.ml.cohort_map import build_cohort_map

    df = _noise_table_sorted_by_diagnosis().drop(columns="codigo")
    df["hora_registro"] = np.arange(len(df)) * 0.5 + 0.25
    cm = build_cohort_map(df, target="diagnostico")
    assert "hora_registro" not in cm.id_excluded
    assert any("sigue el orden de las filas" in w and "hora_registro" in w for w in cm.warnings)
    assert any("casi perfecto" in w for w in cm.warnings)


def test_wdbc_still_gives_96_percent_out_of_sample_with_no_false_alarm():
    from src.ml.cohort_map import build_cohort_map, example_wdbc

    df, target = example_wdbc()
    cm = build_cohort_map(df, target=target, id_col="paciente")
    mr = cm.model
    assert mr.n_splits == 5 and 0.95 <= mr.accuracy <= 0.97 and mr.auc >= 0.985
    assert mr.accuracy > mr.baseline_accuracy + 0.2
    assert cm.id_excluded == {} and cm.warnings == [] and len(cm.features) == 30


def test_imputation_is_fitted_inside_each_fold_and_missing_values_work():
    from src.ml import cohort_map as C

    assert "make_pipeline(SimpleImputer" in inspect.getsource(C._supervised)
    df, target = C.example_wdbc()
    df.iloc[::7, 3] = np.nan
    cm = C.build_cohort_map(df, target=target, id_col="paciente")
    assert cm.model is not None and cm.model.auc > 0.95
    assert any("faltantes" in n for n in cm.notes)


@pytest.mark.parametrize("target_values,needle", [
    ([f"c{i % 15}" for i in range(60)], "15 valores distintos"),
    (["A"] * 60, "una sola categoría"),
    (["A"] * 59 + ["B"], "un solo paciente"),
])
def test_skipped_model_explains_why(target_values, needle):
    from src.ml.cohort_map import build_cohort_map

    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(size=(60, 4)), columns=list("abcd"))
    df["y"] = target_values
    cm = build_cohort_map(df, target="y")
    assert cm.model is None and needle in cm.model_skipped


def test_cohort_tab_shows_the_leak_warning_and_the_exploratory_label():
    from streamlit.testing.v1 import AppTest

    from src.ml.cohort_map import EXPLORATORY_NOTE

    assert "exploratorio, no validado" in EXPLORATORY_NOTE
    at = AppTest.from_function(_m3d_page, default_timeout=180)
    at.session_state["m3d_cohort_raw"] = _noise_table_sorted_by_diagnosis().to_csv(index=False).encode()
    at.session_state["m3d_cohort_name"] = "tabla.csv"
    at.run()
    next(s for s in at.selectbox if s.key == "m3d_cohort_target").set_value("diagnostico").run()
    assert not at.exception, at.exception
    assert any("posible fuga por ID" in w.value for w in at.warning)
    assert EXPLORATORY_NOTE in _text(at)


# ═══ Parte C: nada de lo que se quitó en la Pieza 2 volvió ═══════════════════

def test_news2_body_and_removed_names_did_not_come_back():
    from visualization import anatomy3d as A3

    assert not hasattr(A3, "TWIN_ORGAN_PARTS") and "part_colors" not in inspect.signature(A3.body_figure).parameters
    banned = ("TWIN_ORGAN_PARTS", "part_colors", "ORGAN_STATUS_COLOR", "news2_parameter_scores", "vital_columns",
              "_render_patient_body", "visualization.art", "ollama", "render_plate(")
    for folder in ("app", "src", "visualization", "clinical", "domain"):
        for path in (ROOT / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for word in banned:
                assert word not in text, (str(path.relative_to(ROOT)), word)
