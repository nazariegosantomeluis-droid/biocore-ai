"""
Biomarkers Lab -- PLV neurocardiaco (Fase 2, 2026-08-19).

Reemplaza `calculate_neurocardiac_coupling_score()` (retirado -- el
validador la califico de pseudocientifica: suma de potencias absolutas mas
un `signal_coherence` sin definicion algoritmica) por un Phase-Locking Value
real entre la fase de Theta Frontomedial (4-8Hz) del EEG y la fase de la
banda HF-HRV (0.15-0.40Hz) del tacograma R-R, con un minimo de 180s de
senal simultanea (criterio del validador, verbatim -- ver CHANGELOG.md).

Como en produccion el PLV casi siempre degrada a "no disponible" (el
pipeline no persiste ECG+EEG simultaneos hoy), estos tests verifican el
ALGORITMO con senales sinteticas de respuesta conocida, mas los guards de
degradacion honesta (disponibilidad, duracion, anti-bucle) uno por uno.
"""

import numpy as np
import pytest

from app.supermodules.biomarkers import BiocoreEngine, PLVResult


# ---------------------------------------------------------------------------
# Parte D -- nucleo matematico del PLV, con fases sinteticas de respuesta
# conocida. Aislado de filtrado/interpolacion (`_plv_from_phases`).
# ---------------------------------------------------------------------------

def test_plv_identical_phase_gives_one():
    rng = np.random.default_rng(0)
    phase = rng.uniform(-np.pi, np.pi, 2000)
    plv = BiocoreEngine._plv_from_phases(phase, phase)
    assert plv == pytest.approx(1.0, abs=1e-9)


def test_plv_independent_random_phase_gives_near_zero():
    rng = np.random.default_rng(1)
    a = rng.uniform(-np.pi, np.pi, 5000)
    b = rng.uniform(-np.pi, np.pi, 5000)
    plv = BiocoreEngine._plv_from_phases(a, b)
    assert plv < 0.05


def test_plv_constant_offset_gives_one_not_zero():
    """El PLV mide CONSTANCIA del desfase, no que el desfase sea cero --
    un offset fijo distinto de cero tambien debe dar PLV~1.0."""
    rng = np.random.default_rng(2)
    phase = rng.uniform(-np.pi, np.pi, 2000)
    offset = 1.3
    plv = BiocoreEngine._plv_from_phases(phase, phase - offset)
    assert plv == pytest.approx(1.0, abs=1e-9)


def test_plv_slowly_drifting_offset_reduces_plv():
    """Un desfase que varia (no constante) debe dar un PLV intermedio,
    claramente por debajo del caso de offset fijo."""
    rng = np.random.default_rng(3)
    n = 2000
    phase = rng.uniform(-np.pi, np.pi, n)
    drifting_offset = np.linspace(0, 4 * np.pi, n)  # desfase que crece con el tiempo
    plv_drift = BiocoreEngine._plv_from_phases(phase, phase - drifting_offset)
    plv_constant = BiocoreEngine._plv_from_phases(phase, phase - 1.3)
    assert plv_drift < plv_constant


# ---------------------------------------------------------------------------
# Parte C -- guards de degradacion honesta. Nunca un numero por defecto.
# ---------------------------------------------------------------------------

def test_plv_no_signal_is_unavailable_not_a_default_number():
    engine = BiocoreEngine()
    result = engine.calculate_neurocardiac_plv()
    assert isinstance(result, PLVResult)
    assert result.available is False
    assert result.value is None
    assert "ECG+EEG en vivo simultánea" in result.reason


def test_plv_partial_signal_is_unavailable():
    """Solo EEG, sin R-R -- tambien debe degradar (no calcular con lo que
    haya)."""
    engine = BiocoreEngine()
    eeg = np.random.default_rng(0).normal(0, 1, 256 * 200)
    result = engine.calculate_neurocardiac_plv(eeg, 256.0, None, None)
    assert result.available is False
    assert result.value is None


def test_plv_short_duration_rejected_with_measured_duration():
    engine = BiocoreEngine()
    rng = np.random.default_rng(4)
    fs_eeg = 256.0
    eeg = rng.normal(0, 1, int(30 * fs_eeg))  # solo 30s, muy por debajo de 180s
    rr = np.full(35, 0.8)
    rr_t = np.cumsum(rr)

    result = engine.calculate_neurocardiac_plv(eeg, fs_eeg, rr, rr_t)

    assert result.available is False
    assert result.value is None
    assert result.duration_s is not None and result.duration_s < BiocoreEngine.MIN_PLV_DURATION_S
    assert "180" in result.reason


def test_plv_looped_signal_rejected():
    """Advertencia del validador: una senal EEG repetida en bucle produce un
    PLV ~1.0 artefactual -- debe detectarse y rechazarse, no calcularse."""
    engine = BiocoreEngine()
    fs_eeg = 256.0
    duration = 200.0
    n_eeg = int(duration * fs_eeg)
    template_n = n_eeg // 4
    t_template = np.arange(template_n) / fs_eeg
    template = np.sin(2 * np.pi * 6.0 * t_template)
    eeg_looped = np.tile(template, 4)[:n_eeg]

    n_beats = int(duration / 0.8)
    rr = np.full(n_beats, 0.8)
    rr_t = np.cumsum(rr)

    result = engine.calculate_neurocardiac_plv(eeg_looped, fs_eeg, rr, rr_t)

    assert result.available is False
    assert result.value is None
    assert "bucle" in result.reason


def test_plv_sufficient_duration_runs_end_to_end_without_crashing():
    """>=180s de senal simultanea, sin bucle -- el pipeline completo
    (filtrado + Hilbert + interpolacion + PLV) debe correr sin excepciones y
    devolver un PLV numerico valido en [0,1]."""
    engine = BiocoreEngine()
    rng = np.random.default_rng(5)
    fs_eeg = 256.0
    duration = 200.0
    n_eeg = int(duration * fs_eeg)
    t_eeg = np.arange(n_eeg) / fs_eeg
    eeg = np.sin(2 * np.pi * 6.0 * t_eeg) + 0.3 * rng.normal(0, 1, n_eeg)

    n_beats = int(duration / 0.8)
    rr = 0.8 + 0.05 * rng.normal(0, 1, n_beats)
    rr_t = np.cumsum(rr)

    result = engine.calculate_neurocardiac_plv(eeg, fs_eeg, rr, rr_t)

    assert result.available is True
    assert result.value is not None
    assert 0.0 <= result.value <= 1.0
    assert result.duration_s >= BiocoreEngine.MIN_PLV_DURATION_S


# ---------------------------------------------------------------------------
# Parte A -- el score pseudocientifico viejo ya no existe.
# ---------------------------------------------------------------------------

def test_old_pseudoscientific_coupling_method_removed():
    assert not hasattr(BiocoreEngine, "calculate_neurocardiac_coupling_score")


# ---------------------------------------------------------------------------
# get_full_biomarker_suite -- forma del dict, cascada honesta de Learning
# Readiness, y confirmacion de que los otros scores no cambiaron.
# ---------------------------------------------------------------------------

_BASAL_PRESET = {
    'hrv_lf_hf_ratio': 1.5, 'current_resting_hr': 65.0, 'hrv_rmssd': 45.0,
    'sleep_hours': 7.5, 'eeg_alpha_power': 15.0, 'eeg_theta_power': 8.0,
    'hrv_hf_power': 350.0, 'hr_surge': 5.0, 'hr_recovery_rate': 25.0,
    'hrv_sdnn': 50.0, 'eeg_beta_attenuation': 5.0,
}


def test_suite_without_raw_signals_shows_neurocardiac_unavailable():
    """El caso de hoy: Biomarkers Lab no tiene ECG+EEG crudos simultaneos.
    NeuroCardiac PLV debe salir 'no disponible', nunca un numero."""
    engine = BiocoreEngine()
    suite = engine.get_full_biomarker_suite(_BASAL_PRESET)

    assert 'NeuroCardiac PLV' in suite
    plv_entry = suite['NeuroCardiac PLV']
    assert plv_entry['available'] is False
    assert plv_entry['plv'] is None
    assert plv_entry['reason'] is not None


def test_suite_learning_readiness_cascades_honestly_when_plv_unavailable():
    engine = BiocoreEngine()
    suite = engine.get_full_biomarker_suite(_BASAL_PRESET)

    readiness_entry = suite['Learning Readiness Index']
    assert readiness_entry['available'] is False
    assert 'PLV' in readiness_entry['reason']


def test_suite_other_five_scores_unchanged_by_plv_replacement():
    engine = BiocoreEngine()
    suite = engine.get_full_biomarker_suite(_BASAL_PRESET)

    assert suite['Stress Index'] == {'available': True, 'score': 22.22, 'status': 'Óptimo'}
    assert suite['Recovery Index'] == {'available': True, 'score': 50.22, 'status': 'Bueno'}
    assert suite['Cognitive Load Score'] == {'available': True, 'score': 5.67, 'status': 'Normal'}
    assert suite['Physiological Resilience Score'] == {'available': True, 'score': 27.42, 'status': 'Promedio'}


def test_suite_has_no_autonomic_stability_key():
    """Sigue latente (2026-08-15), no forma parte del dict devuelto."""
    engine = BiocoreEngine()
    suite = engine.get_full_biomarker_suite(_BASAL_PRESET)
    assert 'Autonomic Stability Score' not in suite


def test_suite_neurocardiac_available_when_sufficient_raw_signal_provided():
    """Si alguna vez se le pasan señales reales suficientes, la suite debe
    reflejarlo -- confirma el cableado end-to-end de
    get_full_biomarker_suite() -> calculate_neurocardiac_plv()."""
    engine = BiocoreEngine()
    rng = np.random.default_rng(6)
    fs_eeg = 256.0
    duration = 200.0
    n_eeg = int(duration * fs_eeg)
    t_eeg = np.arange(n_eeg) / fs_eeg
    eeg = np.sin(2 * np.pi * 6.0 * t_eeg) + 0.3 * rng.normal(0, 1, n_eeg)
    n_beats = int(duration / 0.8)
    rr = 0.8 + 0.05 * rng.normal(0, 1, n_beats)
    rr_t = np.cumsum(rr)

    suite = engine.get_full_biomarker_suite(
        _BASAL_PRESET, eeg_frontal_signal=eeg, eeg_fs=fs_eeg,
        rr_intervals_s=rr, rr_timestamps_s=rr_t,
    )

    assert suite['NeuroCardiac PLV']['available'] is True
    assert suite['Learning Readiness Index']['available'] is True
