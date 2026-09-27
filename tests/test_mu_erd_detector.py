"""
Mu ERD Tanda 1 (2026-09-26) -- validación aislada del generador de evento
motor (`EegSignalGenerator`, patrón nuevo `motor_imagery`) y del detector
de ERD por Hilbert-en-banda-mu (`src/signals/eeg/erd_detector.py`), mismo
patrón de disciplina que χ (Arco 2B): el detector se valida midiendo si
RECUPERA una profundidad de ERD conocida por construcción, no si "se ve
razonable" -- un ajuste sesgado no se auto-denuncia.

Aislamiento (mismo criterio que `spectral_model.py` en 2B, vigente durante
Tanda 1): este módulo no se importaba desde ningún consumidor -- vivía y se
probaba solo aquí. Mu ERD Tanda 2 (mismo día) lo conecta al EEG Neuro Lab
(`app/supermodules/eeg_neuro_lab/page_content.py`) -- el test de
aislamiento de abajo se actualizó para reflejar eso: sigue confirmando que
NUNCA se importa desde el UPS (`builder.py`/`schema.py`/`repository.py`),
que es la separación que de verdad importa (demostración de fenómeno, no
escritor del organismo -- Parte D de Tanda 2).
"""

import re

import numpy as np
import pytest

from src.signals.eeg.eeg_generator import EegSignalGenerator, EegPattern
from src.signals.eeg.erd_detector import (
    MU_ERD_SCOPE_NOTE,
    ErdResult,
    detect_mu_erd,
)

_FS = 256.0


def _generate_motor_imagery(seed: int, depth_pct: float, **overrides) -> np.ndarray:
    np.random.seed(seed)
    gen = EegSignalGenerator(sampling_rate=_FS)
    params = dict(
        pattern_type="motor_imagery", duration=20.0, fs=_FS, amplitude=40.0,
        noise_level=0.1, channels=1, motor_event_time=10.0, motor_erd_depth_pct=depth_pct,
        motor_transition_s=1.0, motor_event_duration_s=3.0, motor_recovery_s=3.0,
    )
    params.update(overrides)
    eeg, _ = gen.generate_eeg(EegPattern(**params))
    return eeg["Fp1"]


# Ventana de evento por defecto en estos tests: `event_offset_s=1.0` salta
# la transición completa (1.0s, mismo valor que `motor_transition_s`) para
# medir la meseta ya asentada, no la pendiente -- coherente con cómo
# `detect_mu_erd()` documenta su propio `event_offset_s`.
_EVENT_KW = dict(baseline_duration_s=4.0, event_offset_s=1.0, event_duration_s=2.0)


# --- El test que importa: recuperación de la caída conocida ---------------

@pytest.mark.parametrize("depth_pct", [40.0, 60.0, 80.0])
def test_detector_recovers_known_erd_depth(depth_pct):
    """Calibrado empíricamente (15 semillas por profundidad, `noise_level`
    realista de 0.1): error máximo observado 3.15pp (depth=40). Margen
    holgado a <6.0pp -- no ajustado a la cuarta cifra decimal, solo a que
    el detector siga siendo el correcto (mismo criterio que el banco de
    HR: <0.5bpm sobre un 0.12bpm medido)."""
    signal = _generate_motor_imagery(seed=0, depth_pct=depth_pct)
    result = detect_mu_erd(signal, _FS, t_event=10.0, **_EVENT_KW)
    assert result.available, result.reason
    assert abs(result.erd_percent - depth_pct) < 6.0, (
        f"depth={depth_pct}: medido {result.erd_percent}, error > 6.0pp"
    )


def test_detector_recovers_known_erd_depth_with_zero_noise_exactly():
    """Sin ruido, la envolvente es exacta por construcción -- el detector
    debe recuperar la profundidad casi al bit (confirma que la fórmula de
    la envolvente del generador y la fórmula ERD% de Pfurtscheller del
    detector son inversas exactas, sin sesgo estructural escondido detrás
    del ruido)."""
    signal = _generate_motor_imagery(seed=0, depth_pct=60.0, noise_level=0.0)
    result = detect_mu_erd(signal, _FS, t_event=10.0, **_EVENT_KW)
    assert result.available, result.reason
    assert abs(result.erd_percent - 60.0) < 0.1


# --- El timing: la caída se localiza en t_event, no en cualquier lado -----

def test_detector_localizes_the_drop_near_true_t_event_not_elsewhere():
    """Mismo generador, dos llamadas al detector: una con el `t_event`
    VERDADERO (debe ver la caída inyectada), otra con un `t_event` falso
    apuntando a una región de reposo plano ANTES del evento real (debe ver
    ~0, sin caída) -- confirma que el detector mide DONDE se le apunta, no
    que siempre reporta un número fijo sin importar el timing."""
    signal = _generate_motor_imagery(seed=0, depth_pct=60.0)

    r_true = detect_mu_erd(signal, _FS, t_event=10.0, **_EVENT_KW)
    assert r_true.available
    assert r_true.erd_percent > 40.0, "sobre el evento real, se espera una caída grande"

    r_fake_early = detect_mu_erd(
        signal, _FS, t_event=5.0,
        baseline_duration_s=3.0, event_offset_s=0.5, event_duration_s=1.5,
    )
    assert r_fake_early.available
    assert abs(r_fake_early.erd_percent) < 10.0, (
        "apuntando a una región de reposo plano, no debe verse una caída -- "
        f"midió {r_fake_early.erd_percent}"
    )


# --- Degradación honesta, nunca un ERD de relleno --------------------------

def test_no_event_signal_gives_near_zero_erd_not_a_fabricated_value():
    """`motor_erd_depth_pct=0.0` -- la envolvente queda en 1.0 todo el
    tiempo (sin caída real inyectada). El detector debe medir ~0%, un
    resultado genuino (ruido, no fabricación) -- disponible, porque SÍ hay
    suficiente señal para medir, solo que no hay nada que reportar."""
    signal = _generate_motor_imagery(seed=0, depth_pct=0.0)
    result = detect_mu_erd(signal, _FS, t_event=10.0, **_EVENT_KW)
    assert result.available
    assert abs(result.erd_percent) < 10.0, f"sin evento inyectado, se esperaba ~0%, midió {result.erd_percent}"


def test_declines_honestly_when_baseline_window_falls_before_signal_start():
    """Señal corta, `t_event` cerca del inicio -- la ventana de baseline
    pedida se sale antes de la muestra 0. `available=False` con motivo,
    nunca un ERD calculado sobre una ventana que no existe."""
    signal = _generate_motor_imagery(
        seed=0, depth_pct=60.0, duration=5.0, motor_event_time=2.0,
        motor_transition_s=0.5, motor_event_duration_s=1.0, motor_recovery_s=1.0,
    )
    result = detect_mu_erd(
        signal, _FS, t_event=2.0,
        baseline_duration_s=4.0, event_offset_s=0.5, event_duration_s=1.0,
    )
    assert not result.available
    assert result.erd_percent is None
    assert "baseline" in result.reason and "antes del inicio de la señal" in result.reason


def test_declines_honestly_when_event_window_exceeds_signal_end():
    """Ventana de evento pedida más allá del final de la señal --
    `available=False` con motivo, no un índice fuera de rango silenciado."""
    signal = _generate_motor_imagery(seed=0, depth_pct=60.0, duration=10.0, motor_event_time=8.0)
    result = detect_mu_erd(
        signal, _FS, t_event=8.0,
        baseline_duration_s=2.0, event_offset_s=1.0, event_duration_s=5.0,
    )
    assert not result.available
    assert result.erd_percent is None
    assert "evento" in result.reason and "excede la" in result.reason


def test_declines_honestly_on_zero_baseline_power():
    """Señal plana (silencio) -- potencia mu de baseline ~0, ERD%
    indefinido sobre un denominador nulo. Nunca se fuerza un número."""
    flat = np.zeros(int(_FS * 20))
    result = detect_mu_erd(flat, _FS, t_event=10.0, **_EVENT_KW)
    assert not result.available
    assert result.erd_percent is None


# --- Artefacto excluido SIN colapsar la serie temporal ---------------------

def test_artifact_in_baseline_excluded_without_collapsing_the_time_series():
    """Un parpadeo (mismo pulso Hann de `generate_blink_artifact()`, Arco
    2A) inyectado DENTRO de la ventana de baseline, en una sola
    sub-ventana de 1s (de las 4 que forman la baseline de 4s) -- el
    detector debe excluir esa sub-ventana contaminada y promediar solo las
    3 limpias, sin que el ERD% recuperado se distorsione. La comparación es
    contra el MISMO caso sin contaminar (misma semilla) -- si el rechazo
    fallara y se promediara el artefacto junto con el resto, la potencia de
    baseline (y por tanto el ERD%) cambiaría de forma notoria."""
    gen = EegSignalGenerator(sampling_rate=_FS)
    signal_clean = _generate_motor_imagery(seed=0, depth_pct=60.0)

    pulse = gen.generate_blink_artifact(duration=1.0, rate=1.0)
    insert_idx = int(7.5 * _FS)  # dentro de la ventana de baseline [6,10)s
    signal_contaminated = signal_clean.copy()
    signal_contaminated[insert_idx:insert_idx + len(pulse)] += pulse

    r_clean = detect_mu_erd(signal_clean, _FS, t_event=10.0, **_EVENT_KW)
    r_contaminated = detect_mu_erd(signal_contaminated, _FS, t_event=10.0, **_EVENT_KW)

    assert r_clean.available and r_contaminated.available, (
        "el rechazo debe EXCLUIR la sub-ventana contaminada, no declinar la baseline entera "
        "(quedan 3 de 4 sub-ventanas limpias, por encima de min_clean_baseline_s)"
    )
    assert abs(r_contaminated.erd_percent - r_clean.erd_percent) < 3.0, (
        "el ERD% no debe distorsionarse por un artefacto correctamente excluido -- "
        f"limpio={r_clean.erd_percent}, contaminado={r_contaminated.erd_percent}"
    )
    assert abs(r_contaminated.baseline_power - r_clean.baseline_power) / r_clean.baseline_power < 0.05, (
        "la potencia de baseline no debe moverse más de un poco de ruido -- "
        "el pulso quedó fuera del promedio"
    )


def test_artifact_actually_trips_the_gradient_rejection_threshold():
    """Confirma que el pulso inyectado arriba SÍ dispara el criterio real
    de exclusión (gradiente sobre la señal de banda ancha, el mismo de
    Arco 2A) -- no que "se ve distinto" en potencia de banda mu (un
    parpadeo es de banda ANCHA; tras el filtro angosto 8-13Hz, buena parte
    de su energía ya se atenuó -- por eso el rechazo ocurre ANTES del
    filtrado a mu, sobre la señal de `preprocess_eeg()`, no después). Si
    esta aserción fallara, el test de exclusión de arriba no probaría nada
    -- el pulso tendría que ser más grande para disparar el rechazo."""
    gen = EegSignalGenerator(sampling_rate=_FS)
    signal_clean = _generate_motor_imagery(seed=0, depth_pct=60.0)
    pulse = gen.generate_blink_artifact(duration=1.0, rate=1.0)
    insert_idx = int(7.5 * _FS)
    signal_contaminated = signal_clean.copy()
    signal_contaminated[insert_idx:insert_idx + len(pulse)] += pulse

    from src.signals.eeg.eeg_analyzer import ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S
    from src.signals.eeg.preprocessing import preprocess_eeg

    wideband = preprocess_eeg(signal_contaminated, _FS)[0]
    window_samples = int(_FS)
    baseline_start = int(6.0 * _FS)

    def gradient(sub_window_idx):
        s = baseline_start + sub_window_idx * window_samples
        e = s + window_samples
        return float(np.max(np.abs(np.diff(wideband[s:e]))) * _FS)

    contaminated_gradient = gradient(1)  # [7,8)s contiene el pulso insertado en 7.5s
    clean_gradients = [gradient(i) for i in (0, 2, 3)]

    assert contaminated_gradient > ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S, (
        f"el pulso debe disparar el umbral de rechazo ({ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S}) -- "
        f"midió {contaminated_gradient}"
    )
    assert all(g < ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S for g in clean_gradients), (
        "las 3 sub-ventanas sin pulso no deben disparar el umbral -- si lo hicieran, la "
        "prueba de exclusión de arriba no distinguiría contaminado de limpio"
    )


# --- Genérico 1-D, sin acoplamiento a EegAnalyzer/canal nombrado -----------

def test_detector_is_generic_1d_not_coupled_to_a_named_channel():
    """Cualquier señal 1-D + fs -- se prueba aquí con ruido blanco puro
    filtrado a mano (sin pasar por `EegSignalGenerator` en absoluto), para
    confirmar que el detector no asume nada sobre el origen de la señal más
    allá de "un array 1-D + fs"."""
    rng = np.random.default_rng(0)
    arbitrary_signal = rng.normal(0, 40.0, int(_FS * 20))
    result = detect_mu_erd(arbitrary_signal, _FS, t_event=10.0, **_EVENT_KW)
    assert isinstance(result, ErdResult)
    # No se afirma nada sobre el valor -- ruido puro no tiene un ERD
    # "correcto" conocido; el punto es que la función acepta y procesa
    # cualquier señal 1-D sin lanzar excepción ni requerir un canal nombrado.


def test_compute_mu_power_timeseries_matches_the_detectors_own_pipeline():
    """Una fuente, dos consumidores: la curva completa (`compute_mu_power_
    timeseries()`, Tanda 2 -- la visualización) y la potencia por ventana
    que usa `detect_mu_erd()` internamente deben coincidir en las MISMAS
    muestras -- confirmado indirectamente: la media de la curva completa
    sobre la ventana de baseline exacta debe ser igual (mismo pipeline
    preprocess_eeg -> _bandpass_mu -> Hilbert, sin rechazo de artefactos de
    por medio en un caso limpio) a `baseline_power` del `ErdResult`."""
    from src.signals.eeg.erd_detector import compute_mu_power_timeseries

    signal = _generate_motor_imagery(seed=0, depth_pct=60.0)
    curve = compute_mu_power_timeseries(signal, _FS)
    assert curve.shape == signal.shape
    assert np.all(curve >= 0.0), "la potencia instantánea nunca es negativa"

    result = detect_mu_erd(signal, _FS, t_event=10.0, **_EVENT_KW)
    assert result.available
    i0, i1 = int(6.0 * _FS), int(10.0 * _FS)  # la ventana de baseline exacta, sin artefactos que excluir
    baseline_from_curve = float(np.mean(curve[i0:i1]))
    assert abs(baseline_from_curve - result.baseline_power) < 1e-6, (
        "la curva completa y el detector deben coincidir en la misma ventana, sin ningún rechazo "
        "de artefactos de por medio en este caso limpio"
    )


def test_erd_detector_stays_out_of_the_ups_even_after_ui_wiring():
    """Mu ERD Tanda 2: el módulo se conecta al EEG Lab (esperado, ver
    `page_content.py`) pero NUNCA al UPS -- es una demostración de
    fenómeno (`validation=None` del módulo mixto, Parte D de la tanda), no
    un escritor del organismo. Confirmado por grep que `erd_detector` no
    aparece en ninguna ruta que construya/persista `UnifiedPhysiologicalState`."""
    forbidden_paths = [
        "domain/physiology/state/builder.py",
        "domain/physiology/state/schema.py",
        "domain/physiology/state/repository.py",
        "app/supermodules/twin_shell/pages.py",
    ]
    for path in forbidden_paths:
        try:
            src = open(path, encoding="utf-8").read()
        except FileNotFoundError:
            continue
        assert not re.search(r"\berd_detector\b", src), f"{path} referencia erd_detector -- no debería escribir al UPS"

    init_src = open("src/signals/eeg/__init__.py", encoding="utf-8").read()
    assert "erd_detector" not in init_src, (
        "erd_detector no debe reexportarse desde __init__.py todavía -- mismo aislamiento que "
        "spectral_model.py (fooof) en 2B, aunque aquí la razón sea 'aún no validado en vivo', "
        "no una dependencia pesada"
    )


def test_scope_note_travels_with_every_result_available_or_not():
    """La cláusula de alcance (Parte C) viaja con el dato desde su origen --
    presente tanto en un resultado disponible como en uno que declina."""
    signal = _generate_motor_imagery(seed=0, depth_pct=60.0)
    r_ok = detect_mu_erd(signal, _FS, t_event=10.0, **_EVENT_KW)
    assert r_ok.scope_note == MU_ERD_SCOPE_NOTE
    assert "lateralidad" in r_ok.scope_note

    flat = np.zeros(int(_FS * 20))
    r_declined = detect_mu_erd(flat, _FS, t_event=10.0, **_EVENT_KW)
    assert r_declined.scope_note == MU_ERD_SCOPE_NOTE
