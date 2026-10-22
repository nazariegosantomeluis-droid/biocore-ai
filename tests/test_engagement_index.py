"""
Engagement Index (2026-10-18) -- β/(α+θ), Pope, Bogart & Bartolome 1995,
relativo al baseline de reposo del propio sujeto, firmado por el experto.
Mismo patrón que el ERD/χ: el detector se valida midiendo si RECUPERA un
cambio de engagement conocido por construcción (patrón `engagement_task` del
generador), y declina con motivo cuando no hay baseline, cuando α+θ ≈ 0 o
cuando la señal es demasiado corta -- nunca un engagement de relleno.
"""

import re
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

import src.signals.eeg.engagement_detector as engagement_module
from src.signals.eeg.eeg_generator import EegPattern, EegSignalGenerator, EngagementTaskEvent
from src.signals.eeg.engagement_detector import (
    ENGAGEMENT_CITATION,
    ENGAGEMENT_SCOPE_NOTE,
    EngagementResult,
    classify_engagement_change,
    detect_engagement,
    engagement_index,
)

_FS = 256.0
_LABEL = "Engagement (reposo → tarea)"


def _generate(seed: int, change_pct: float, noise_level: float = 0.1, duration: float = 30.0, **event_kw) -> np.ndarray:
    np.random.seed(seed)
    event = EngagementTaskEvent(change_pct=change_pct, **event_kw)
    eeg, _ = EegSignalGenerator(sampling_rate=_FS).generate_eeg(EegPattern(
        pattern_type="engagement_task", duration=duration, fs=_FS, amplitude=40.0,
        noise_level=noise_level, channels=1, engagement_event=event,
    ))
    return eeg["Fp1"]


def _detect(signal: np.ndarray, event: EngagementTaskEvent = EngagementTaskEvent()) -> EngagementResult:
    w = event.measurement_windows()
    return detect_engagement(
        signal, _FS, t_task=event.t_task, baseline_duration_s=w.baseline_duration_s,
        task_offset_s=w.event_offset_s, task_duration_s=w.event_duration_s,
    )


# --- El test que importa: recuperación del cambio conocido ----------------

@pytest.mark.parametrize("change_pct", [-30.0, 30.0, 60.0, 100.0])
def test_recovers_known_change_exactly_without_noise(change_pct):
    """Sin ruido, generador y fórmula son inversas exactas (medido: error
    < 1e-4 pp) -- ningún sesgo estructural escondido detrás del ruido."""
    result = _detect(_generate(0, change_pct, noise_level=0.0))
    assert result.available, result.reason
    assert abs(result.engagement_relative_pct - change_pct) < 0.01


@pytest.mark.parametrize("change_pct", [-30.0, 30.0, 60.0])
def test_recovers_known_change_with_noise(change_pct):
    """20 semillas, `noise_level=0.1`. Calibrado empíricamente (30 semillas
    por cambio): sesgo medio <= 1.4 pp (el ruido blanco diluye la razón
    hacia 0) y error relativo de la razón por semilla <= 6.2 % -- la
    varianza del periodograma por ventana de 1s, no un sesgo. Tolerancias
    ~2x lo medido: sesgo < 2.5 pp, error relativo por semilla < 12 %."""
    measured = [_detect(_generate(seed, change_pct)).engagement_relative_pct for seed in range(20)]
    bias = float(np.mean(measured)) - change_pct
    assert abs(bias) < 2.5, f"cambio={change_pct}: sesgo medio {bias:.2f} pp"
    for value in measured:
        ratio_error = abs((1 + value / 100) / (1 + change_pct / 100) - 1)
        assert ratio_error < 0.12, f"cambio={change_pct}: medido {value:.1f}% (error relativo {ratio_error:.3f})"


def test_measures_the_real_change_not_a_plausible_constant():
    """+30 y +60 inyectados deben dar números distintos en la proporción
    correcta -- no un "engagement sube" genérico."""
    low = np.mean([_detect(_generate(s, 30.0)).engagement_relative_pct for s in range(10)])
    high = np.mean([_detect(_generate(s, 60.0)).engagement_relative_pct for s in range(10)])
    assert 22.0 < high - low < 38.0, f"+30 -> {low:.1f}, +60 -> {high:.1f}"


def test_measures_where_it_is_pointed():
    """Apuntando a dos tramos de reposo (antes de la tarea real) el cambio
    es ~0: el detector mide la ventana que se le pide."""
    signal = _generate(0, 60.0)
    result = detect_engagement(signal, _FS, t_task=6.0, baseline_duration_s=5.0, task_offset_s=0.0, task_duration_s=5.0)
    assert result.available, result.reason
    assert abs(result.engagement_relative_pct) < 10.0


# --- Degradación honesta ---------------------------------------------------

def test_declines_without_baseline_before_signal_start():
    result = detect_engagement(_generate(0, 40.0), _FS, t_task=1.0, baseline_duration_s=4.0)
    assert not result.available
    assert result.engagement_relative_pct is None
    assert "baseline" in result.reason and "antes del inicio de la señal" in result.reason


def test_declines_when_baseline_is_too_short_to_measure():
    """Baseline de 1.5s ([0.5, 2.0)): contiene una sola ventana completa de
    1s, menos que los 2s limpios de `MIN_CLEAN_EEG_DURATION_S` -- declina,
    no calcula sobre lo que hay."""
    event = EngagementTaskEvent(t_task=2.0)
    assert event.measurement_windows().baseline_duration_s == 1.5
    result = _detect(_generate(0, 40.0, t_task=2.0), event)
    assert not result.available
    assert result.reason.startswith("baseline: 1.0s limpios de 1.5s pedidos")
    assert result.engagement_curve is None


def test_declines_when_task_window_exceeds_signal():
    result = _detect(_generate(0, 40.0, duration=20.0))
    assert not result.available
    assert "tarea" in result.reason and "excede" in result.reason


def test_declines_on_zero_alpha_plus_theta_instead_of_dividing_by_zero():
    """β pura: la fuga del Welch deja α+θ ≈ 3e-6·β, por encima de un piso
    absoluto de 1e-9 -- el piso relativo lo declara indefinido."""
    t = np.arange(int(30 * _FS)) / _FS
    result = _detect(16.0 * np.sin(2 * np.pi * 16.0 * t))
    assert not result.available
    assert "α+θ indistinguible de cero" in result.reason
    assert engagement_index(10.0, 0.0, 0.0) is None
    assert engagement_index(0.0, 0.0, 0.0) is None


def test_declines_on_zero_baseline_engagement():
    """Reposo con solo alfa (β/(α+θ) ≈ 3e-9 por fuga): el cambio relativo
    sería ~1e10 % -- declina en vez de reportarlo."""
    t = np.arange(int(30 * _FS)) / _FS
    signal = 20.0 * np.sin(2 * np.pi * 10.0 * t) + np.where(t >= 12.0, 16.0 * np.sin(2 * np.pi * 16.0 * t), 0.0)
    result = _detect(signal)
    assert not result.available
    assert result.engagement_relative_pct is None
    assert "engagement de baseline indistinguible de cero" in result.reason


@pytest.mark.parametrize("n_samples", [0, 1, 15])
def test_declines_on_a_signal_too_short_to_filter(n_samples):
    from src.signals.eeg.preprocessing import MIN_FILTERABLE_SAMPLES

    result = detect_engagement(np.ones(n_samples), _FS, t_task=0.01, baseline_duration_s=0.01)
    assert not result.available
    assert f"{n_samples} muestras" in result.reason and str(MIN_FILTERABLE_SAMPLES) in result.reason


def test_artifact_in_baseline_is_excluded_not_averaged():
    """Un parpadeo en el baseline se rechaza dentro de esa ventana (rechazo
    de Arco 2A vía `EegAnalyzer`) -- el engagement relativo casi no cambia."""
    clean = _generate(0, 40.0)
    pulse = EegSignalGenerator(sampling_rate=_FS).generate_blink_artifact(duration=1.0, rate=1.0)
    contaminated = clean.copy()
    i = int(6.5 * _FS)
    contaminated[i:i + len(pulse)] += pulse
    r_clean, r_cont = _detect(clean), _detect(contaminated)
    assert r_clean.available and r_cont.available
    assert abs(r_cont.engagement_relative_pct - r_clean.engagement_relative_pct) < 5.0


def test_scope_note_travels_with_every_result():
    assert _detect(_generate(0, 40.0)).scope_note == ENGAGEMENT_SCOPE_NOTE
    assert _detect(np.zeros(10)).scope_note == ENGAGEMENT_SCOPE_NOTE
    assert "relativo al reposo del propio sujeto" in ENGAGEMENT_SCOPE_NOTE
    assert "varía entre sujetos" in ENGAGEMENT_SCOPE_NOTE


def test_citation_is_pope_1995_with_verified_journal():
    assert "Pope, A. T., Bogart, E. H., & Bartolome, D. S. (1995)" in ENGAGEMENT_CITATION
    assert "Biological Psychology, 40(1-2), 187-195" in ENGAGEMENT_CITATION


# --- Dirección y evento ----------------------------------------------------

def test_direction_is_sign_only_and_never_a_severity_level():
    assert classify_engagement_change(40.0)[2] == "↑"
    assert classify_engagement_change(-20.0)[2] == "↓"
    assert classify_engagement_change(0.0)[0] == "sin_cambio"
    assert classify_engagement_change(None)[0] == "no_disponible"
    severity_levels = {"normal", "leve", "severo"}
    for pct in (-50.0, -0.1, 0.0, 0.1, 150.0):
        assert classify_engagement_change(pct)[0] not in severity_levels


@pytest.mark.parametrize("bad", [
    dict(change_pct=-100.0), dict(t_task=-1.0), dict(transition_s=0.0), dict(task_s=0.0), dict(recovery_s=-1.0),
])
def test_engagement_event_rejects_invalid_parameters(bad):
    with pytest.raises(ValueError):
        EngagementTaskEvent(**bad)


def test_engagement_signal_stays_under_the_artifact_gradient_threshold():
    """Todas las ventanas de 1s del patrón (con el máximo cambio del slider)
    pasan el rechazo de Arco 2A -- la mezcla del generador no puede
    disfrazarse de artefacto."""
    from src.signals.eeg.eeg_analyzer import EegAnalyzer

    analysis = EegAnalyzer(fs=_FS).analyze(_generate(0, 150.0, noise_level=0.18))
    assert analysis.available and analysis.clean_fraction == 1.0


# --- Aislamiento del UPS ---------------------------------------------------

def test_engagement_stays_out_of_the_ups():
    for path in (
        "domain/physiology/state/builder.py",
        "domain/physiology/state/schema.py",
        "domain/physiology/state/repository.py",
        "app/supermodules/twin_shell/pages.py",
        "app/engines/digital_twin_organism.py",
    ):
        src = Path(path).read_text(encoding="utf-8")
        assert not re.search(r"engagement", src, re.IGNORECASE), f"{path} referencia engagement"
    assert "engagement" not in Path("src/signals/eeg/__init__.py").read_text(encoding="utf-8")


# --- UI: gramática neutra, alcance visible, degradación --------------------

@pytest.fixture
def eeg_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "eeg_engagement_test.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente Engagement (test)")
    return sf, pid


def _run_eeg_lab(eeg_ups, pattern=None):
    sf, pid = eeg_ups

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    at = AppTest.from_function(_script)
    at.session_state["twin_shell_ups_session_factory"] = sf
    at.session_state["twin_shell_ups_patient_id"] = pid
    at.run(timeout=30)
    if pattern is not None:
        next(s for s in at.sidebar.selectbox if s.label == "Patrón EEG").set_value(pattern)
        at.run(timeout=30)
    return at


def _engagement_card(at) -> str:
    return " ".join(md.value for md in at.main.markdown if "Engagement relativo al baseline" in md.value)


def test_panel_appears_only_for_the_engagement_pattern(eeg_ups):
    at = _run_eeg_lab(eeg_ups)
    assert "Engagement Index" not in " ".join(md.value for md in at.main.markdown)
    assert "Cambio de engagement (%)" not in [s.label for s in at.sidebar.slider]

    at = _run_eeg_lab(eeg_ups, _LABEL)
    assert at.exception == []
    assert "Engagement Index" in " ".join(md.value for md in at.main.markdown)
    assert "Cambio de engagement (%)" in [s.label for s in at.sidebar.slider]


def test_ui_card_uses_neutral_accent_frame_not_a_traffic_light(eeg_ups):
    from app.utils.design_system import PALETTE

    at = _run_eeg_lab(eeg_ups, _LABEL)
    card = _engagement_card(at)
    assert card, "no se encontró la tarjeta de engagement"
    assert re.search(r"[+-]\d+\.\d% respecto al reposo", card)
    assert f"border-left:4px solid {PALETTE.ACCENT_ON_DARK}" in card
    for alarm in (PALETTE.STABLE, PALETTE.WARNING, PALETTE.CRITICAL):
        assert alarm not in card, "el engagement no se enmarca como semáforo"
    assert "↑" in card and ENGAGEMENT_CITATION in card


def test_ui_scope_note_is_visible(eeg_ups):
    at = _run_eeg_lab(eeg_ups, _LABEL)
    warning_text = " ".join(w.value for w in at.main.warning)
    assert ENGAGEMENT_SCOPE_NOTE in warning_text
    assert "relativo al reposo del propio sujeto" in warning_text and "varía entre sujetos" in warning_text


def test_ui_value_follows_the_injected_change(eeg_ups):
    at = _run_eeg_lab(eeg_ups, _LABEL)
    values = {}
    for change, arrow in ((-40, "↓"), (120, "↑")):
        # Refetch del slider antes de cada set_value (ver nota de método en
        # test_mu_erd_eeg_lab_visualization.py).
        next(s for s in at.sidebar.slider if s.label == "Cambio de engagement (%)").set_value(change)
        at.run(timeout=30)
        assert at.exception == []
        card = _engagement_card(at)
        values[change] = float(re.search(r"([+-]\d+\.\d)% respecto al reposo", card).group(1))
        assert arrow in card, f"cambio {change}: falta la dirección {arrow}"
    assert values[-40] < -20.0 and values[120] > 80.0, values


def test_ui_declines_with_reason_not_a_number(eeg_ups):
    def _fake(signal, fs, **kwargs):
        return EngagementResult(
            available=False, baseline_window=(0.0, 1.0), task_window=(2.0, 3.0), reason="MOTIVO DE PRUEBA FORZADO",
        )

    with patch.object(engagement_module, "detect_engagement", _fake):
        at = _run_eeg_lab(eeg_ups, _LABEL)
        assert at.exception == []
        assert "Engagement no disponible: MOTIVO DE PRUEBA FORZADO" in " ".join(i.value for i in at.main.info)
        card = _engagement_card(at)
        assert "MOTIVO DE PRUEBA FORZADO" in card
        assert not re.search(r"\d+\.\d% respecto al reposo", card)
        assert ENGAGEMENT_SCOPE_NOTE in " ".join(w.value for w in at.main.warning)


# --- Gráfico temporal: dibujo = medición, una sola cadena ------------------

def test_drawn_windows_and_baseline_line_are_the_measured_ones():
    """Los rectángulos son exactamente `baseline_window`/`task_window` del
    resultado, la línea de referencia está en `baseline_value`, y ese valor
    es la media de los puntos de la curva dentro del tramo sombreado -- el
    dibujo no puede desviarse de la medición."""
    from app.supermodules.eeg_neuro_lab.engagement_panel import build_engagement_figure

    result = _detect(_generate(0, 60.0))
    assert result.available
    fig = build_engagement_figure(result, "Fp1")

    rects = [(s.x0, s.x1) for s in fig.layout.shapes if s.type == "rect"]
    assert rects == [result.baseline_window, result.task_window]
    assert result.baseline_window == (2.0, 12.0) and result.task_window == (13.0, 25.0)
    hlines = [s.y0 for s in fig.layout.shapes if s.type == "line"]
    assert hlines == [result.baseline_value]

    trace = fig.data[0]
    assert np.array_equal(np.asarray(trace.x), result.curve_time)
    assert np.array_equal(np.asarray(trace.y, dtype=float), result.engagement_curve, equal_nan=True)
    for window, value in ((result.baseline_window, result.baseline_value), (result.task_window, result.task_value)):
        inside = (result.curve_time - 0.5 >= window[0]) & (result.curve_time + 0.5 <= window[1])
        assert abs(float(np.nanmean(result.engagement_curve[inside])) - value) < 1e-12


@pytest.mark.parametrize("change_pct", [30.0, 60.0])
def test_curve_rises_in_the_task_window(change_pct):
    """Anti-placebo visual: la curva dibujada sube en el tramo de tarea
    respecto al baseline, en la proporción inyectada."""
    result = _detect(_generate(0, change_pct))
    t, curve = result.curve_time, result.engagement_curve
    in_baseline = (t > result.baseline_window[0]) & (t < result.baseline_window[1])
    in_task = (t > result.task_window[0]) & (t < result.task_window[1])
    ratio = np.nanmean(curve[in_task]) / np.nanmean(curve[in_baseline])
    expected = 1 + change_pct / 100
    assert ratio > 1 + change_pct / 200, f"la curva no sube en la tarea: razón {ratio:.3f}"
    assert abs(ratio - expected) < 0.12 * expected, f"razón {ratio:.3f}, inyectada {expected:.2f}"


def test_rejected_window_is_a_gap_in_the_curve_not_a_filled_value():
    clean = _generate(0, 40.0)
    pulse = EegSignalGenerator(sampling_rate=_FS).generate_blink_artifact(duration=1.0, rate=1.0)
    contaminated = clean.copy()
    contaminated[int(6.5 * _FS):int(6.5 * _FS) + len(pulse)] += pulse
    result = _detect(contaminated)
    assert result.available
    assert np.isnan(result.engagement_curve[6]) and np.isfinite(result.engagement_curve[5])


@pytest.mark.parametrize("signal_kind", ["no_baseline", "zero_alpha_theta", "too_short"])
def test_declined_result_has_no_curve(signal_kind):
    t = np.arange(int(30 * _FS)) / _FS
    if signal_kind == "no_baseline":
        result = detect_engagement(_generate(0, 40.0), _FS, t_task=1.0, baseline_duration_s=4.0)
    elif signal_kind == "zero_alpha_theta":
        result = _detect(16.0 * np.sin(2 * np.pi * 16.0 * t))
    else:
        result = detect_engagement(np.ones(10), _FS, t_task=0.01, baseline_duration_s=0.01)
    assert not result.available
    assert result.engagement_curve is None and result.curve_time is None


def test_detector_runs_one_spectral_chain_and_never_analyze(monkeypatch):
    """Curva + baseline + tarea salen de UNA pasada de `_windowed_welch()`
    (un solo `preprocess_eeg`), sin correr `analyze()` por tramo."""
    from src.signals.eeg import eeg_analyzer

    calls = {"welch": 0, "analyze": 0, "preprocess": 0}
    original_welch, original_analyze, original_pre = (
        eeg_analyzer.EegAnalyzer._windowed_welch, eeg_analyzer.EegAnalyzer.analyze, eeg_analyzer.preprocess_eeg,
    )

    def _count(key, fn):
        def wrapper(*a, **k):
            calls[key] += 1
            return fn(*a, **k)
        return wrapper

    monkeypatch.setattr(eeg_analyzer.EegAnalyzer, "_windowed_welch", _count("welch", original_welch))
    monkeypatch.setattr(eeg_analyzer.EegAnalyzer, "analyze", _count("analyze", original_analyze))
    monkeypatch.setattr(eeg_analyzer, "preprocess_eeg", _count("preprocess", original_pre))
    assert _detect(_generate(0, 40.0)).available
    assert calls == {"welch": 1, "analyze": 0, "preprocess": 1}, calls


def test_one_engagement_chain_per_page_render(eeg_ups):
    """En la página: cada `analyze()` del EEG Lab corre su propia pasada de
    `_windowed_welch()`, y el panel de engagement añade exactamente UNA."""
    from src.signals.eeg import eeg_analyzer

    calls = {"welch": 0, "analyze": 0}
    original_welch, original_analyze = eeg_analyzer.EegAnalyzer._windowed_welch, eeg_analyzer.EegAnalyzer.analyze

    def _welch(self, *a, **k):
        calls["welch"] += 1
        return original_welch(self, *a, **k)

    def _analyze(self, *a, **k):
        calls["analyze"] += 1
        return original_analyze(self, *a, **k)

    with patch.object(eeg_analyzer.EegAnalyzer, "_windowed_welch", _welch), \
            patch.object(eeg_analyzer.EegAnalyzer, "analyze", _analyze):
        at = _run_eeg_lab(eeg_ups)
        next(s for s in at.sidebar.selectbox if s.label == "Patrón EEG").set_value(_LABEL)
        calls.update(welch=0, analyze=0)
        at.run(timeout=30)
        assert at.exception == []
    assert calls["analyze"] >= 1
    assert calls["welch"] == calls["analyze"] + 1, calls


def test_ui_draws_the_curve_in_accent_without_traffic_light_colors(eeg_ups):
    from app.utils.design_system import PALETTE

    at = _run_eeg_lab(eeg_ups, _LABEL)
    # El EEG Lab tiene otros gráficos (señales, cabeza 3D): se identifica el del engagement por su contenido.
    engagement_specs = [c.proto.spec for c in at.get("plotly_chart") if "Baseline (reposo)" in c.proto.spec]
    assert len(engagement_specs) == 1
    spec = engagement_specs[0]
    assert PALETTE.ACCENT_ON_DARK in spec
    for alarm in (PALETTE.STABLE, PALETTE.WARNING, PALETTE.CRITICAL):
        assert alarm not in spec, "el gráfico de engagement no usa colores de semáforo"
    assert ENGAGEMENT_SCOPE_NOTE in " ".join(w.value for w in at.main.warning)
    assert _engagement_card(at), "la tarjeta sigue junto al gráfico"


def test_ui_declined_shows_reason_and_no_chart(eeg_ups):
    """Señal de 10s (mínimo del slider de duración): el bloque de tarea no
    cabe -> declina; ningún gráfico de engagement, motivo visible, vista en
    pie. Este test destapó que el slider de inicio quedaba con min == max
    (3.0) y Streamlit tumbaba la página -- corregido con
    `_LATEST_TASK_FLOOR_S`."""
    at = _run_eeg_lab(eeg_ups, _LABEL)
    next(s for s in at.sidebar.slider if s.label == "Duración (segundos)").set_value(10)
    at.run(timeout=30)
    assert at.exception == []
    assert not any("Baseline (reposo)" in c.proto.spec for c in at.get("plotly_chart")), (
        "declinado: ningún gráfico de engagement"
    )
    assert "Engagement no disponible:" in " ".join(i.value for i in at.main.info)
    assert ENGAGEMENT_SCOPE_NOTE in " ".join(w.value for w in at.main.warning)


def test_page_content_stays_under_900_lines():
    lines = Path("app/supermodules/eeg_neuro_lab/page_content.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) < 900, f"page_content.py tiene {len(lines)} líneas"
