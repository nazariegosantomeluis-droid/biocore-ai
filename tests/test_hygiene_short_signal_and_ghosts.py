"""
Tanda de higiene (2026-09-28): `EegAnalyzer.analyze()` declina con motivo
ante una señal demasiado corta para el bandpass (antes: `ValueError` crudo
de `filtfilt`), con la MISMA forma degradada que ya usa el rechazo de
artefactos -- los consumidores (BAR/DAR/TBR/χ, band power, guardado al
gemelo) la heredan como "no disponible" sin ninguna rama nueva. Más la
guarda de que los tres fantasmas metabólicos retirados no vuelvan.
"""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from src.signals.eeg import EegAnalyzer, EegSignalGenerator, classify_dar, classify_tbr
from src.signals.eeg.preprocessing import FILTER_ORDER, MIN_FILTERABLE_SAMPLES, min_filtfilt_samples

_FS = 256.0


def _short(n: int) -> np.ndarray:
    return np.random.default_rng(0).normal(0, 40.0, n)


def test_min_filterable_samples_is_derived_from_the_filter_order():
    assert MIN_FILTERABLE_SAMPLES == min_filtfilt_samples(FILTER_ORDER) == 16


@pytest.mark.parametrize("n", [0, 1, 14, 15])
def test_analyze_declines_below_the_filter_minimum_instead_of_crashing(n):
    result = EegAnalyzer(fs=_FS).analyze(_short(n))
    assert result.available is False
    assert f"{n} muestras" in result.reason and str(MIN_FILTERABLE_SAMPLES) in result.reason
    assert result.band_power == {}
    assert (result.bar, result.dar, result.tbr) == (None, None, None)
    assert result.psd_freqs is None and result.psd_power is None
    assert (result.clean_fraction, result.clean_window_count) == (0.0, 0)


def test_analyze_at_the_threshold_filters_and_degrades_by_the_existing_path():
    """16 muestras ya se filtran: declina por el camino que ya existía
    (señal limpia insuficiente), no por longitud -- y no crashea."""
    result = EegAnalyzer(fs=_FS).analyze(_short(16))
    assert result.available is False
    assert "muestras" not in result.reason
    assert "insuficiente tras rechazo de artefactos" in result.reason


def test_short_signal_propagates_as_unavailable_all_the_way_to_the_ratios_and_chi():
    """El camino completo que recorre la página: analyze() -> DAR/TBR
    (`classify_*`), BAR, band power, y χ (`fit_aperiodic_component` con el
    PSD ausente) -- todos leen "no disponible", ninguno lanza."""
    from src.signals.eeg.spectral_model import classify_chi, fit_aperiodic_component

    result = EegAnalyzer(fs=_FS).analyze(_short(10))
    assert classify_dar(result.dar)[0] == "no_disponible"
    assert classify_tbr(result.tbr)[0] == "no_disponible"
    assert result.bar is None
    assert result.findings == {"Estado": f"no disponible: {result.reason}"}

    chi = fit_aperiodic_component(
        result.psd_freqs, result.psd_power, clean_window_count=result.clean_window_count, bandpass_fs=_FS,
    )
    assert chi.available is False
    assert classify_chi(None)[0] == "no_disponible"


def test_normal_length_signal_is_unchanged():
    """Camino normal intacto: una señal de 20s sigue disponible con sus 5 bandas."""
    np.random.seed(0)
    from src.signals.eeg import EegPattern

    eeg, _ = EegSignalGenerator(sampling_rate=_FS).generate_eeg(
        EegPattern(pattern_type="alpha", duration=20.0, fs=_FS, noise_level=0.25, channels=1)
    )
    result = EegAnalyzer(fs=_FS).analyze(eeg["Fp1"])
    assert result.available is True
    assert set(result.band_power) == {"delta", "theta", "alpha", "beta", "gamma"}


@pytest.fixture
def eeg_ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(Path(str(tmp_path / "eeg_short_signal_test.db")))
    init_db(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        pid = create_patient(s, display_name="Paciente señal corta (test)")
    return sf, pid


def test_eeg_lab_degrades_honestly_with_a_short_signal(eeg_ups):
    """AppTest hasta el final del render con una señal de 10 muestras por
    canal (lo que un CSV diminuto produciría): la Vista Clínica sigue en
    pie, cada canal y la columna de métricas muestran el motivo, y ninguna
    tarjeta de ratio con número aparece."""
    sf, pid = eeg_ups
    n = 10

    def _short_eeg(self, params):
        time = np.arange(n) / self.fs
        leads = ["Fp1", "Fp2", "C3", "C4"][: params.channels]
        eeg = {lead: np.random.default_rng(i).normal(0, 40.0, n) for i, lead in enumerate(leads)}
        eeg["time"] = time
        return eeg, time

    def _script():
        import app.supermodules.eeg_neuro_lab.pages as m
        m.run()

    with patch.object(EegSignalGenerator, "generate_eeg", _short_eeg):
        at = AppTest.from_function(_script)
        at.session_state["twin_shell_ups_session_factory"] = sf
        at.session_state["twin_shell_ups_patient_id"] = pid
        at.run(timeout=30)

    assert at.exception == []
    all_text = " ".join(e.value for e in list(at.main.markdown) + list(at.main.info) + list(at.main.caption))
    assert "No se pudo renderizar la Vista Clínica" not in all_text, "la vista entera no debe caerse"
    # Col2 (métricas): el motivo en `st.info`, y ninguna tarjeta de
    # resultado (Banda dominante, DAR/TBR/BAR) -- viven en la rama disponible.
    info_text = " ".join(i.value for i in at.main.info)
    assert f"Canal Fp1: señal EEG de {n} muestras" in info_text
    markdown_text = " ".join(md.value for md in at.main.markdown)
    for card in ("Banda dominante", "DAR (Delta/Alfa)", "TBR (Theta/Beta)", "BAR (Beta/Alfa)"):
        assert card not in markdown_text, f"{card} no debe mostrarse sobre una señal corta"


# --- Los tres fantasmas metabólicos retirados no vuelven ---------------------

def test_retired_metabolic_ghosts_stay_retired():
    from app.engines import digital_twin_organism as dto
    import app.utils.data_generator as data_generator

    organism = dto.DigitalTwinOrganism()
    exported = json.loads(organism.to_json())
    assert "sleep" not in exported
    assert "metabolic_recovery" not in exported["recovery"]
    assert not hasattr(dto, "SleepState")
    assert not hasattr(data_generator, "generate_metabolic_profile")
    assert not hasattr(data_generator.DataGenerator, "generate_metabolic_profile")
