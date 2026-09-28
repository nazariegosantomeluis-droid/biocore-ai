"""
Arco 2A (2026-09-11) -- bandpass activado + rechazo de artefactos por
gradiente en el EEG, con degradación tipo-PLV.

Contexto: `preprocess_eeg()` (bandpass 0.5-40 Hz) tenía CERO llamadores --
`EegAnalyzer.analyze()` iba directo de señal cruda al PSD de Welch. El
diagnóstico probó que un parpadeo (pulso Hann ~50ms/~80µV,
`EegSignalGenerator._blink_artifacts()`) añade un piso de potencia a todas
las bandas -- devastador sobre alfa (denominador de BAR/DAR): un solo
parpadeo puede colapsar el BAR de ~62 a ~16 sin que el estado cortical real
cambie. Mono-canal confirmado (sin ≥2 canales reales ni referencia EOG en
el repo) -- el rechazo por gradiente de amplitud, tras el bandpass y antes
del Welch, es el método honesto.

NOTA DE HONESTIDAD (Art. I, igual que en `eeg_analyzer.py`): esta suite
valida el rechazo contra el parpadeo MODELADO del generador demo (pulso
Hann sintético), no contra un registro EOG real. Su generalización a
artefactos reales es trabajo futuro.
"""

import numpy as np
import pytest
from scipy.signal import welch
from streamlit.testing.v1 import AppTest

from src.signals.eeg.eeg_generator import EegPattern, EegSignalGenerator
from src.signals.eeg.eeg_analyzer import (
    ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S,
    MIN_CLEAN_EEG_DURATION_S,
    EegAnalyzer,
)

_FS = 256.0


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    """Misma fórmula que `EegAnalyzer._trapz` privada -- reimplementada
    aquí solo para construir la referencia RAW (sin filtrar, sin rechazo)
    que existía ANTES de esta tanda, y así medir el efecto del bandpass/
    rechazo por comparación, no por asunción."""
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if y.size < 2 or x.size < 2:
        return 0.0
    return float(np.sum((x[1:] - x[:-1]) * 0.5 * (y[1:] + y[:-1])))


def _raw_band_power(signal: np.ndarray, fs: float) -> dict:
    """Reproduce EXACTAMENTE el pipeline anterior a esta tanda: Welch
    directo sobre señal cruda, sin `preprocess_eeg()` ni rechazo -- el
    oráculo de "cómo era antes", no una implementación de producción."""
    freqs, psd = welch(signal, fs=fs, nperseg=min(512, len(signal)))

    def bp(lo, hi):
        mask = (freqs >= lo) & (freqs <= hi)
        return float(_trapz(psd[mask], freqs[mask])) if np.any(mask) else 0.0

    return {
        'delta': bp(0.5, 3.5), 'theta': bp(4.0, 7.5), 'alpha': bp(8.0, 12.0),
        'beta': bp(13.0, 30.0), 'gamma': bp(30.0, 45.0),
    }


@pytest.fixture
def clean_beta_signal():
    """Base 'beta' (alerta/enfocado) del generador demo, amplitud 40,
    20s -- la misma clase de señal que ya usa `test_coupling_subfase_b.py`
    para BAR alto."""
    np.random.seed(1)
    gen = EegSignalGenerator(sampling_rate=_FS)
    p = EegPattern(pattern_type='beta', duration=20.0, fs=_FS, amplitude=40.0, noise_level=0.25, channels=1)
    eeg, t = gen.generate_eeg(p)
    return gen, eeg['Fp1'], t


# --- Parte A: el bandpass activado ------------------------------------------

def test_preprocess_eeg_now_has_a_live_caller_inside_analyze(clean_beta_signal):
    """Barandilla directa: una frecuencia FUERA de 0.5-40 Hz debe atenuarse
    en el resultado -- si `preprocess_eeg()` no corriera, no lo haría.
    Un drift de 0.05 Hz (muy por debajo del corte de 0.5 Hz) inflaría
    `delta_power` sin filtrar; con el bandpass activo, se atenúa."""
    gen, clean, t = clean_beta_signal
    analyzer = EegAnalyzer(fs=_FS)

    drift = 200.0 * np.sin(2 * np.pi * 0.05 * t)  # 0.05 Hz, fuera de banda
    contaminated_by_drift = clean + drift

    raw_delta = _raw_band_power(contaminated_by_drift, _FS)['delta']
    filtered_delta = analyzer.analyze(contaminated_by_drift).band_power['delta']

    assert filtered_delta < raw_delta * 0.2, (
        f"el bandpass no atenuó el drift fuera de banda: cruda={raw_delta:.1f} filtrada={filtered_delta:.1f}"
    )


# --- Parte B/D: rechazo por gradiente + wrapper público del parpadeo -------

def test_generate_blink_artifact_is_public_and_matches_the_modeled_pulse():
    """Wrapper público (Parte D) -- expone EXACTAMENTE la señal que ya
    alimenta el patrón 'Artifact (parpadeo)' del EEG Lab, sin depender de
    `_blink_artifacts()` (privado) de otra clase."""
    gen = EegSignalGenerator(sampling_rate=_FS)
    blink = gen.generate_blink_artifact(duration=5.0, rate=0.5)
    assert isinstance(blink, np.ndarray)
    assert len(blink) == int(5.0 * _FS)
    assert blink.max() == pytest.approx(80.0, rel=0.05)  # pico del pulso Hann modelado
    assert np.count_nonzero(blink) > 0  # hay pulsos, no todo-cero


# --- Parte C: EL TEST QUE IMPORTA -- convergencia --------------------------

def test_convergence_contaminated_bar_returns_close_to_clean_with_rejection_active(clean_beta_signal):
    """El test que importa: `analyze(base_limpia + parpadeo)` con rechazo
    activo converge de vuelta a `analyze(base_limpia)` dentro de tolerancia
    -- prueba que el rechazo RECUPERA el estado real, no que solo "hace
    algo". Referencia: sin rechazo (pipeline crudo, welch directo) el BAR
    contaminado se desploma a una fracción minúscula del limpio (el
    diagnóstico midió 62->16); CON rechazo debe quedarse mucho más cerca."""
    gen, clean, t = clean_beta_signal
    analyzer = EegAnalyzer(fs=_FS)

    blink = gen.generate_blink_artifact(duration=20.0, rate=0.5)
    contaminated = clean + blink

    bar_clean = analyzer.analyze(clean).bar
    bar_contaminated_with_rejection = analyzer.analyze(contaminated).bar

    # oráculo "cómo hubiera sido SIN el Arco 2A" -- welch crudo, sin filtrar
    # ni rechazar, sobre la misma señal contaminada.
    raw_contaminated_bp = _raw_band_power(contaminated, _FS)
    from src.signals.eeg.eeg_analyzer import beta_alpha_ratio
    bar_contaminated_raw = beta_alpha_ratio(raw_contaminated_bp['beta'], raw_contaminated_bp['alpha'])

    assert bar_clean is not None and bar_contaminated_with_rejection is not None and bar_contaminated_raw is not None

    # 1) el rechazo deja el BAR mucho más cerca del limpio que el crudo
    dist_with_rejection = abs(bar_contaminated_with_rejection - bar_clean)
    dist_raw = abs(bar_contaminated_raw - bar_clean)
    assert dist_with_rejection < dist_raw, (
        f"el rechazo no mejoró la cercanía al BAR real: con_rechazo={bar_contaminated_with_rejection:.1f} "
        f"(dist {dist_with_rejection:.1f}) vs. crudo={bar_contaminated_raw:.1f} (dist {dist_raw:.1f}), "
        f"limpio={bar_clean:.1f}"
    )
    # 2) y queda dentro de una tolerancia razonable del BAR real (no solo
    # "mejor", sino CERCA) -- el diagnóstico midió el crudo colapsando a
    # ~25% del limpio; con rechazo debe recuperar la mayoría del valor real.
    assert bar_contaminated_with_rejection == pytest.approx(bar_clean, rel=0.35), (
        f"BAR contaminado+rechazo ({bar_contaminated_with_rejection:.1f}) no convergió al limpio "
        f"({bar_clean:.1f}) dentro de tolerancia"
    )
    # el crudo, en cambio, SÍ se desploma muy por debajo de esa tolerancia
    # -- confirma que la tolerancia es significativa, no trivialmente ancha.
    assert bar_contaminated_raw < bar_clean * 0.5


# --- Señal limpia pasa intacta ---------------------------------------------

def test_clean_signal_passes_through_rejection_unharmed(clean_beta_signal):
    """Crítico: un rechazo demasiado agresivo que recorta señal REAL sería
    su propia distorsión. Sobre una señal limpia, NINGUNA ventana debe
    rechazarse (`clean_fraction == 1.0`), y el resultado debe quedar cerca
    del pipeline sin rechazo (solo bandpass + ventaneo, sin artefacto que
    excluir)."""
    gen, clean, t = clean_beta_signal
    analyzer = EegAnalyzer(fs=_FS)

    result = analyzer.analyze(clean)
    assert result.available is True
    assert result.clean_fraction == pytest.approx(1.0)

    raw_bp = _raw_band_power(clean, _FS)
    # tolerancia amplia (40%): el ventaneo cambia la resolución en frecuencia
    # del PSD promediado respecto al Welch de una sola pasada -- el punto
    # de esta prueba es "no se dañó la señal", no "idéntico bit a bit".
    for band in ('delta', 'theta', 'alpha', 'beta'):
        assert result.band_power[band] == pytest.approx(raw_bp[band], rel=0.4), (
            f"banda {band}: nueva={result.band_power[band]:.2f} vs. cruda={raw_bp[band]:.2f}"
        )


# --- Degradación tipo-PLV ---------------------------------------------------

def test_degrades_to_unavailable_when_signal_is_mostly_artifact():
    """Señal toda-artefacto (o casi): un parpadeo por ventana (rate=1.0)
    sobre una base real -- cada ventana de 1s queda contaminada -> menos de
    `MIN_CLEAN_EEG_DURATION_S` de señal limpia -> `available=False` con
    motivo, band powers ausentes, sin un número sobre el fragmento que
    sobró."""
    np.random.seed(11)
    gen = EegSignalGenerator(sampling_rate=_FS)
    analyzer = EegAnalyzer(fs=_FS)

    p = EegPattern(pattern_type='beta', duration=5.0, fs=_FS, amplitude=40.0, noise_level=0.25, channels=1)
    eeg, t = gen.generate_eeg(p)
    base = eeg['Fp1']
    blink = gen.generate_blink_artifact(duration=5.0, rate=1.0)  # >=1 parpadeo por ventana de 1s

    result = analyzer.analyze(base + blink)

    assert result.available is False
    assert result.reason is not None and "insuficiente" in result.reason
    assert result.band_power == {}
    assert result.dominant_band is None
    assert result.classification is None
    assert result.summary is None
    assert result.bar is None
    assert result.dar is None
    assert result.tbr is None
    assert result.clean_fraction is not None and result.clean_fraction < 1.0


def test_ratio_functions_return_none_on_empty_band_power_no_special_case_needed():
    """La cadena que el diagnóstico predijo: `beta_alpha_ratio`/
    `delta_alpha_ratio`/`theta_beta_ratio` YA declaran `None` ante un band
    power inválido (`None`) -- ninguna rama especial nueva hizo falta en
    esas funciones para heredar la degradación."""
    from src.signals.eeg.eeg_analyzer import beta_alpha_ratio, delta_alpha_ratio, theta_beta_ratio
    empty_band_power = {}
    assert beta_alpha_ratio(empty_band_power.get('beta'), empty_band_power.get('alpha')) is None
    assert delta_alpha_ratio(empty_band_power.get('delta'), empty_band_power.get('alpha')) is None
    assert theta_beta_ratio(empty_band_power.get('theta'), empty_band_power.get('beta')) is None


def test_degradation_chain_reaches_the_gate_without_touching_builder(monkeypatch):
    """Verifica la cadena completa HASTA el gate, SIN tocar
    `domain/physiology/state/builder.py`: un `EegAnalyzer.analyze()`
    degradado (`available=False`) es la señal para que un llamador honesto
    (el botón del EEG Lab) NO llame a `update_from_sensors()` con band
    power -- y el gate YA EXISTENTE de `_neurological_state()`
    (`"alpha_power" in signals or "beta_power" in signals`) deja el dominio
    neuro vacío porque esas claves nunca llegaron, no porque builder.py
    aprendiera a reconocer `None`."""
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from domain.physiology.state import Provenance, from_digital_twin_organism

    np.random.seed(13)
    gen = EegSignalGenerator(sampling_rate=_FS)
    analyzer = EegAnalyzer(fs=_FS)
    p = EegPattern(pattern_type='beta', duration=5.0, fs=_FS, amplitude=40.0, noise_level=0.25, channels=1)
    eeg, t = gen.generate_eeg(p)
    base = eeg['Fp1']
    blink = gen.generate_blink_artifact(duration=5.0, rate=1.0)

    degraded = analyzer.analyze(base + blink)
    assert degraded.available is False  # precondición del test

    organism = DigitalTwinOrganism()
    # el llamador honesto: NO escribe eeg al organismo cuando available=False
    # (mismo patrón que el botón "Guardar estado al gemelo" ahora aplica).
    if degraded.available:
        organism.update_from_sensors({"eeg": {"alpha_power": degraded.band_power.get("alpha")}})

    state = from_digital_twin_organism(organism, "paciente-2a-test", Provenance.SIMULACION, 0.85)
    assert state.neurological.descriptors == {}  # gate intacto, sin tocar builder.py
    assert "bar" not in state.neurological.descriptors
    assert "dar" not in state.neurological.descriptors
    assert "tbr" not in state.neurological.descriptors


# --- Regresión: patrones limpios de siempre no degradan, config visible ---

@pytest.mark.parametrize("pattern", ["alpha", "beta", "theta", "delta"])
def test_all_four_base_patterns_stay_available_when_clean(pattern):
    """Los 4 patrones base del generador, sin artefacto, nunca degradan --
    el rechazo no es tan agresivo como para dañar señal limpia real.

    Semilla fija (antes `hash(pattern)`, que varía por proceso con
    PYTHONHASHSEED y volvía el test flaky). Medido sobre 300 semillas por
    patrón (2026-09-28): `available` es True en las 1200 corridas, pero
    `clean_fraction` baja a 0.95 (1 ventana de 20 rechazada por la cola del
    ruido gaussiano) en 5/300 alpha, 13/300 beta, 1/300 theta, 1/300 delta
    -- tasa real de falso rechazo del umbral, no del test. La semilla 0 no
    cae en ninguno de esos casos."""
    np.random.seed(0)
    gen = EegSignalGenerator(sampling_rate=_FS)
    analyzer = EegAnalyzer(fs=_FS)
    p = EegPattern(pattern_type=pattern, duration=20.0, fs=_FS, amplitude=40.0, noise_level=0.25, channels=1)
    eeg, t = gen.generate_eeg(p)
    result = analyzer.analyze(eeg['Fp1'])
    assert result.available is True, f"{pattern} degradó sin artefacto: {result.reason}"
    assert result.clean_fraction == pytest.approx(1.0)


def test_named_config_constants_are_documented_not_magic():
    """Config nombrada (Parte B/C), no constantes mágicas -- deben existir
    y ser positivas."""
    assert ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S > 0
    assert MIN_CLEAN_EEG_DURATION_S > 0


# --- AppTest: el EEG Lab con el patrón "Artifact" seleccionado -------------

def test_eeg_lab_renders_with_artifact_pattern_selected_no_crash():
    """AppTest hasta el final del render (barandilla de ejecución): con el
    patrón 'Artifact (parpadeo)' del EEG Lab seleccionado, la página no
    crashea -- degrada honestamente si el rechazo deja señal insuficiente,
    en vez de un `AttributeError`/`KeyError` sobre `None`/`{}`."""
    # `page_content.py` es un script de nivel de módulo (patrón
    # runpy.run_path), no expone una función `render()` -- se ejecuta
    # corriéndolo directamente, exactamente como `pages.py` lo hace.
    def _script():
        import os
        import runpy
        import app.supermodules.eeg_neuro_lab.pages as eeg_pages_mod
        module_path = os.path.join(os.path.dirname(eeg_pages_mod.__file__), "page_content.py")
        runpy.run_path(module_path, run_name="__main__")

    at = AppTest.from_function(_script)
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render inicial: {at.exception}"

    # Cambiar el patrón a "Artifact (parpadeo)" si el selector existe.
    pattern_radio = next((r for r in at.radio if "atrón" in (r.label or "")), None)
    if pattern_radio is not None and "Artifact (parpadeo)" in pattern_radio.options:
        pattern_radio.set_value("Artifact (parpadeo)").run(timeout=30)
        assert at.exception == [], f"excepción con patrón Artifact: {at.exception}"
