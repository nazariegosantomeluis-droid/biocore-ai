"""
Arco 2C (2026-09-14) -- el χ aperiódico elevado a descriptor del UPS,
ADITIVO. BAR/DAR/TBR intactos (Parte A: nuevos campos en `EegAnalysis` que
solo reexponen PSD ya calculado). χ se persiste `PENDING_VALIDATION`, sin
badge ni umbral clínico -- eso espera firma del experto (Arco 2D).

Dos guardianes INDEPENDIENTES protegen a χ de reportarse con confianza y
estar mal, ninguno redundante con el otro:

1. `MIN_CHI_CLEAN_WINDOWS` (evidencia insuficiente) -- con pocas ventanas
   promediadas, el ajuste puede reportar R² alto con χ desviado por encima
   de la tolerancia. El R² no lo detecta: mide calidad de ajuste, no
   suficiencia de evidencia.
2. `correct_bandpass_attenuation()` (sesgo del bandpass) -- hallazgo
   encontrado DURANTE esta misma tanda (no en el mini-diagnóstico previo,
   que por error nunca corrió `preprocess_eeg()` en su réplica de "PSD de
   producción"): el bandpass Butterworth de Arco 2A distorsiona la
   pendiente log-log que χ mide (~+0.46 de sesgo sistemático sin corregir).
   Corregido vía deconvolución exacta contra la ganancia de potencia real
   del mismo filtro -- no un factor de ajuste empírico.

El test que importa (`test_chi_gate_rejects_short_capture_despite_high_r_squared`)
reproduce el guardián 1 con un caso determinista: 10s (10 ventanas), R²
alto, χ desviado -- el gate de ventanas debe rechazarlo de todas formas.
"""

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from domain.physiology.state import (
    Provenance,
    create_patient,
    get_latest_state,
    init_db,
    make_engine,
    make_session_factory,
)
from src.signals.eeg.eeg_analyzer import EegAnalyzer
from src.signals.eeg.eeg_generator import EegPattern, EegSignalGenerator
from src.signals.eeg.spectral_model import (
    MIN_APERIODIC_R_SQUARED,
    MIN_CHI_CLEAN_WINDOWS,
    fit_aperiodic_component,
    generate_colored_noise,
)

_FS = 256.0
_SF_KEY = "twin_shell_ups_session_factory"
_PID_KEY = "twin_shell_ups_patient_id"


# --- El test que importa: el gate de ventanas cierra la trampa -------------

def test_chi_gate_rejects_short_capture_despite_high_r_squared():
    """Caso determinista (chi=1.5, seed=10, 10s -> 10 ventanas, hallado por
    búsqueda dirigida): incluso con la corrección de bandpass activa, el
    ajuste SIN el gate de ventanas reporta R²=0.971 (alto, confiado) sobre
    un χ desviado -0.289 del real -- por encima de la tolerancia de 0.2 que
    2B midió como significativa. El gate de `MIN_CHI_CLEAN_WINDOWS` debe
    rechazarlo de todas formas, por evidencia insuficiente, no por mala
    calidad de ajuste."""
    chi_true = 1.5
    raw = generate_colored_noise(chi_true, duration=10.0, fs=_FS, seed=10) * 15.0
    result = EegAnalyzer(fs=_FS).analyze(raw)

    assert result.available, f"el análisis de producción degradó antes de llegar al gate del chi: {result.reason}"
    assert result.clean_window_count == 10, (
        f"se esperaban 10 ventanas limpias para este caso determinista, se obtuvieron "
        f"{result.clean_window_count} -- si esto cambió, el caso ya no reproduce el hallazgo"
    )
    assert result.clean_window_count < MIN_CHI_CLEAN_WINDOWS

    # 1) SIN el gate de ventanas: demuestra que la trampa existe de verdad
    # sobre ESTA señal -- R² alto, χ desviado por encima de tolerancia.
    ungated = fit_aperiodic_component(result.psd_freqs, result.psd_power, bandpass_fs=_FS)
    assert ungated.available, "se esperaba que el ajuste sin gate reportara disponible (R² alto)"
    assert ungated.r_squared >= MIN_APERIODIC_R_SQUARED
    assert abs(ungated.exponent - chi_true) > 0.2, (
        "se esperaba que el chi sin el gate de ventanas se desviara por encima de la tolerancia -- "
        "si no lo hace, esta señal ya no reproduce el caso dirimente"
    )

    # 2) CON el gate: el mismo PSD (misma corrección de bandpass aplicada),
    # ahora rechazado por evidencia insuficiente -- independiente del R².
    gated = fit_aperiodic_component(
        result.psd_freqs, result.psd_power, clean_window_count=result.clean_window_count, bandpass_fs=_FS
    )
    assert gated.available is False
    assert gated.exponent is None
    assert "ventanas" in gated.reason and str(MIN_CHI_CLEAN_WINDOWS) in gated.reason


# --- chi fiel con duración suficiente (ambos guardianes satisfechos) -------

@pytest.mark.parametrize("chi_true", [0.5, 1.0, 1.5, 2.0])
def test_chi_recovers_within_tolerance_with_sufficient_duration(chi_true):
    """Duración >= la que exige `MIN_CHI_CLEAN_WINDOWS`, CON la corrección
    de bandpass activa -- chi debe recuperarse fiel Y disponible, sobre el
    pipeline de PRODUCCIÓN completo (`EegAnalyzer.analyze()`, bandpass +
    rechazo de artefactos reales, no una réplica aislada)."""
    duration_s = 40.0  # 40 ventanas > MIN_CHI_CLEAN_WINDOWS(30), con margen
    raw = generate_colored_noise(chi_true, duration=duration_s, fs=_FS, seed=7) * 15.0
    result = EegAnalyzer(fs=_FS).analyze(raw)
    assert result.available

    chi_result = fit_aperiodic_component(
        result.psd_freqs, result.psd_power,
        clean_window_count=result.clean_window_count, bandpass_fs=_FS,
    )
    assert chi_result.available, f"chi degradó con señal suficiente: {chi_result.reason}"
    assert chi_result.exponent == pytest.approx(chi_true, abs=0.2)


def test_uncorrected_fit_would_have_been_biased_same_signal():
    """Barandilla que prueba que la corrección de bandpass hace ALGO real
    (no es un no-op): sobre la MISMA señal/PSD del test anterior, SIN pasar
    `bandpass_fs`, el error de recuperación es sustancialmente peor -- el
    sesgo de ~+0.46 que motivó `correct_bandpass_attenuation()`."""
    chi_true = 1.5
    raw = generate_colored_noise(chi_true, duration=40.0, fs=_FS, seed=7) * 15.0
    result = EegAnalyzer(fs=_FS).analyze(raw)
    assert result.available

    corrected = fit_aperiodic_component(
        result.psd_freqs, result.psd_power, clean_window_count=result.clean_window_count, bandpass_fs=_FS
    )
    uncorrected = fit_aperiodic_component(
        result.psd_freqs, result.psd_power, clean_window_count=result.clean_window_count
    )
    assert corrected.available and uncorrected.available
    err_corrected = abs(corrected.exponent - chi_true)
    err_uncorrected = abs(uncorrected.exponent - chi_true)
    assert err_corrected < err_uncorrected, (
        f"la corrección de bandpass no mejoró la recuperación: corregido={err_corrected:.3f} "
        f"sin_corregir={err_uncorrected:.3f}"
    )
    assert err_uncorrected > 0.2, "se esperaba que el error SIN corregir excediera la tolerancia"


# --- Aditividad: el pipeline expone PSD nuevo sin tocar los ratios --------

def test_new_psd_fields_coexist_with_unchanged_ratios():
    """Barandilla de Parte A: `psd_freqs`/`psd_power`/`clean_window_count`
    (aditivos, Arco 2C) están presentes junto a `bar`/`dar`/`tbr` calculados
    exactamente como antes -- ninguna línea del cálculo de banda se tocó
    para exponerlos."""
    np.random.seed(5)
    gen = EegSignalGenerator(sampling_rate=_FS)
    p = EegPattern(pattern_type='beta', duration=20.0, fs=_FS, amplitude=40.0, noise_level=0.25, channels=1)
    eeg, t = gen.generate_eeg(p)

    result = EegAnalyzer(fs=_FS).analyze(eeg['Fp1'])
    assert result.available
    assert result.psd_freqs is not None and result.psd_power is not None
    assert result.clean_window_count is not None and result.clean_window_count > 0
    assert len(result.psd_freqs) == len(result.psd_power)
    assert result.bar is not None
    assert result.band_power['alpha'] >= 0.0


# --- PENDING_VALIDATION, cita metodológica, sin badge -----------------------

def test_chi_persisted_as_pending_validation_with_methodological_citation():
    """Bloque nuevo de `_neurological_state()` (Parte C): mismo patrón que
    bar/dar/tbr, `source_detail` marca PENDING_VALIDATION y cita a Donoghue
    et al. 2020 como respaldo METODOLÓGICO, no clínico. bar/dar/tbr,
    presentes en el mismo dict de señales, no se ven afectados."""
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from domain.physiology.state import from_digital_twin_organism

    organism = DigitalTwinOrganism()
    organism.update_from_sensors({
        "eeg": {
            "delta_power": 5.0, "theta_power": 8.0, "alpha_power": 20.0,
            "beta_power": 15.0, "gamma_power": 3.0,
            "chi_aperiodic": 1.35,
        }
    })
    state = from_digital_twin_organism(organism, "paciente-2c-test", Provenance.SIMULACION, 0.85)
    neuro = state.neurological.descriptors

    assert "chi_aperiodic" in neuro
    assert neuro["chi_aperiodic"].value == pytest.approx(1.35)
    assert "PENDING_VALIDATION" in neuro["chi_aperiodic"].source_detail
    assert "Donoghue" in neuro["chi_aperiodic"].source_detail
    assert neuro["chi_aperiodic"].provenance == Provenance.SIMULACION
    assert "bar" in neuro and "dar" in neuro and "tbr" in neuro


def test_chi_absent_when_signal_key_missing_same_gate_pattern_as_ratios():
    """Sin `chi_aperiodic` en `signals` (p.ej. porque el gate de duración o
    R² degradó antes) -> sin descriptor, mismo criterio honesto que
    bar/dar/tbr."""
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from domain.physiology.state import from_digital_twin_organism

    organism = DigitalTwinOrganism()
    organism.update_from_sensors({
        "eeg": {
            "delta_power": 5.0, "theta_power": 8.0, "alpha_power": 20.0,
            "beta_power": 15.0, "gamma_power": 3.0,
        }
    })
    state = from_digital_twin_organism(organism, "paciente-2c-test-2", Provenance.SIMULACION, 0.85)
    assert "chi_aperiodic" not in state.neurological.descriptors


def test_no_clinical_badge_or_threshold_exists_for_chi_yet():
    """Confirma la frontera de 2C: a diferencia de `classify_dar()`/
    `classify_tbr()` (`eeg_analyzer.py`), no existe todavía un
    `classify_chi()` ni un umbral clínico para chi -- ninguna interpretación
    clínica hasta la firma del experto (Arco 2D)."""
    import src.signals.eeg.spectral_model as spectral_model
    assert not hasattr(spectral_model, "classify_chi")
    assert not hasattr(spectral_model, "CHI_THRESHOLDS")


# ---------------------------- AppTest: producción real ----------------------

@pytest.fixture
def ups(tmp_path):
    engine = make_engine(tmp_path / "eeg_lab_chi_2c.db")
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente EEG Lab Chi (test)")
    return sf, pid


def _run_eeg_page(sf, pid, *, monkeypatch, colored_signal):
    def _fixed_generate_eeg(self, params):
        n = int(params.duration * self.fs)
        t = np.arange(n) / self.fs
        sig = colored_signal(params.duration, self.fs)
        leads = ['Fp1', 'Fp2', 'C3', 'C4'][:params.channels]
        eeg = {lead: sig.copy() for lead in leads}
        eeg['time'] = t
        return eeg, t

    monkeypatch.setattr(EegSignalGenerator, "generate_eeg", _fixed_generate_eeg)

    def _script():
        import os
        import runpy
        import app.supermodules.eeg_neuro_lab.pages as eeg_pages_mod
        module_path = os.path.join(os.path.dirname(eeg_pages_mod.__file__), "page_content.py")
        runpy.run_path(module_path, run_name="__main__")

    at = AppTest.from_function(_script)
    at.session_state[_SF_KEY] = sf
    at.session_state[_PID_KEY] = pid
    at.run(timeout=30)
    assert at.exception == [], f"excepción en el render inicial: {at.exception}"
    return at


def _find_duration_slider(at):
    return next(s for s in at.slider if "Duraci" in (s.label or ""))


def _find_save_button(at):
    for b in at.button:
        if b.key == "eeg_lab_save_to_ups":
            return b
    raise AssertionError(f"botón eeg_lab_save_to_ups no encontrado; botones: {[b.key for b in at.button]}")


def test_eeg_lab_short_duration_chi_not_persisted_rest_of_save_intact(ups, monkeypatch):
    """Degradación en la UI, señal corta: con Duración=10s (mínimo del
    slider), el chi degrada por el gate de ventanas -- no se persiste --
    mientras el resto del guardado (band power/BAR/DAR/TBR) funciona igual
    que antes de 2C."""
    sf, pid = ups
    signal_fn = lambda duration, fs: generate_colored_noise(1.5, duration, fs, seed=321) * 15.0
    at = _run_eeg_page(sf, pid, monkeypatch=monkeypatch, colored_signal=signal_fn)

    _find_duration_slider(at).set_value(10).run(timeout=30)
    assert at.exception == []

    _find_save_button(at).click().run(timeout=30)
    assert at.exception == [], f"excepción tras pulsar Guardar: {at.exception}"
    assert len(at.success) >= 1

    with sf() as s:
        state = get_latest_state(s, pid)
    assert state is not None
    neuro = state.neurological.descriptors
    assert "chi_aperiodic" not in neuro
    assert "alpha_power" in neuro  # el resto del guardado no se vio afectado


def test_eeg_lab_long_duration_chi_persisted(ups, monkeypatch):
    """Degradación en la UI, señal larga: con Duración=90s (>= el piso de
    `MIN_CHI_CLEAN_WINDOWS` con margen), el chi se persiste junto al resto,
    PENDING_VALIDATION."""
    sf, pid = ups
    signal_fn = lambda duration, fs: generate_colored_noise(1.5, duration, fs, seed=321) * 15.0
    at = _run_eeg_page(sf, pid, monkeypatch=monkeypatch, colored_signal=signal_fn)

    _find_duration_slider(at).set_value(90).run(timeout=30)
    assert at.exception == []

    _find_save_button(at).click().run(timeout=30)
    assert at.exception == [], f"excepción tras pulsar Guardar: {at.exception}"

    with sf() as s:
        state = get_latest_state(s, pid)
    assert state is not None
    neuro = state.neurological.descriptors
    assert "chi_aperiodic" in neuro
    assert "PENDING_VALIDATION" in neuro["chi_aperiodic"].source_detail
