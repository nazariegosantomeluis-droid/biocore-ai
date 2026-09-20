"""
Arco 2B (2026-09-14) -- banco de pruebas del motor de parametrización
espectral (exponente aperiódico chi), aislado en
`src/signals/eeg/spectral_model.py`.

Disciplina rectora: FOOOF SIEMPRE devuelve un número plausible para chi --
un ajuste sesgado no se auto-denuncia. `chi` solo cuenta como "recuperado"
si, contra una señal de chi CONOCIDO por construcción
(`generate_colored_noise()`), el error medido es bajo -- ese error medido
ES la validación, sin él el chi es plausible pero no probado. El caso "con
picos superpuestos" es el que importa de verdad: es donde un motor sesgado
confundiría pico con pendiente sin que nada lo delate.

NOTA DE HONESTIDAD (Art. I y IV, igual que en `spectral_model.py`): esta
suite valida contra ruido SINTÉTICO de chi prescrito matemáticamente, no
contra un registro EEG real -- la generalización clínica es trabajo de
Arco 2D.
"""

import numpy as np
import pytest
from scipy.signal import welch

from src.signals.eeg.spectral_model import (
    DEFAULT_APERIODIC_FREQ_RANGE,
    MIN_APERIODIC_R_SQUARED,
    AperiodicComponent,
    add_synthetic_peak,
    fit_aperiodic_component,
    generate_colored_noise,
)

_FS = 256.0
_DURATION_S = 60.0
_WELCH_NPERSEG = 1024  # ventanas de 4s @ 256Hz -- resolución de 0.25Hz, suficiente para separar picos del aperiódico

_CHI_GRID = [0.5, 1.0, 1.5, 2.0]  # rango fisiológicamente plausible de EEG cortical (~1-3), con margen hacia abajo
_SEEDS = [0, 1, 2]  # varias realizaciones por chi -- el error se mide sobre el PEOR caso de la muestra, no el promedio

# Tolerancia de recuperación de chi -- calibrada EMPÍRICAMENTE (2026-09-14)
# contra este mismo banco: sobre la grilla completa (puro y con picos), 15
# semillas por condición, el error máximo observado |chi_recuperado -
# chi_verdadero| fue ~0.095 (peor caso: chi=0.5 con picos). 0.2 deja margen
# de ~2x sobre lo medido -- suficiente para no ser frágil ante la varianza
# de semilla en CI, sin ser tan ancha que deje de probar algo (el pipeline
# CRUDO -- sin FOOOF, comparando potencia absoluta de banda -- se desviaría
# en un orden de magnitud mayor que esto, no en un 20%).
CHI_RECOVERY_TOLERANCE: float = 0.2


def _welch_psd(signal: np.ndarray, fs: float = _FS):
    return welch(signal, fs=fs, nperseg=min(_WELCH_NPERSEG, len(signal)))


# --- Parte D.1: recuperación aperiódico-puro -------------------------------

@pytest.mark.parametrize("chi_true", _CHI_GRID)
def test_pure_aperiodic_recovery_within_tolerance(chi_true):
    """Sin nada que confunda al motor: ruido 1/f^chi puro, chi conocido.
    El motor debe recuperar chi dentro de `CHI_RECOVERY_TOLERANCE` en TODAS
    las semillas probadas -- no solo en promedio."""
    max_err = 0.0
    for seed in _SEEDS:
        signal = generate_colored_noise(chi_true, _DURATION_S, _FS, seed=seed) * 40.0
        freqs, psd = _welch_psd(signal)
        result = fit_aperiodic_component(freqs, psd, DEFAULT_APERIODIC_FREQ_RANGE)

        assert result.available, f"chi={chi_true} seed={seed}: motor degradó sin motivo -- {result.reason}"
        err = abs(result.exponent - chi_true)
        max_err = max(max_err, err)

    assert max_err < CHI_RECOVERY_TOLERANCE, (
        f"chi={chi_true}: error máximo de recuperación {max_err:.3f} excede la tolerancia "
        f"{CHI_RECOVERY_TOLERANCE} (caso puro, sin picos)"
    )


# --- Parte D.2: EL TEST QUE IMPORTA -- recuperación con picos superpuestos -

@pytest.mark.parametrize("chi_true", _CHI_GRID)
def test_aperiodic_recovery_with_overlapping_peaks_within_tolerance(chi_true):
    """El test que expone el sesgo que motivó este arco: los mismos chi,
    ahora con picos alfa (10Hz) y beta (20Hz) superpuestos, como en EEG
    real. Si el motor confundiera pico con pendiente, chi se sesgaría aquí
    aunque el caso puro (arriba) pasara limpio -- por eso se separa
    explícitamente del caso puro en vez de fusionarse en un solo test."""
    max_err = 0.0
    for seed in _SEEDS:
        n = int(_DURATION_S * _FS)
        t = np.arange(n) / _FS
        signal = generate_colored_noise(chi_true, _DURATION_S, _FS, seed=seed) * 40.0
        signal = add_synthetic_peak(signal, t, center_hz=10.0, amplitude=15.0)  # alfa
        signal = add_synthetic_peak(signal, t, center_hz=20.0, amplitude=8.0)   # beta

        freqs, psd = _welch_psd(signal)
        result = fit_aperiodic_component(freqs, psd, DEFAULT_APERIODIC_FREQ_RANGE)

        assert result.available, f"chi={chi_true} seed={seed}: motor degradó sin motivo -- {result.reason}"
        err = abs(result.exponent - chi_true)
        max_err = max(max_err, err)

    assert max_err < CHI_RECOVERY_TOLERANCE, (
        f"chi={chi_true}: error máximo de recuperación {max_err:.3f} excede la tolerancia "
        f"{CHI_RECOVERY_TOLERANCE} CON picos superpuestos -- el motor podría estar confundiendo "
        f"pico con pendiente"
    )


# --- Degradación honesta -----------------------------------------------------

def test_white_noise_degrades_to_unavailable_no_fabricated_chi():
    """Ruido blanco puro no tiene estructura 1/f real (chi≈0 sin pendiente
    consistente sobre el rango ajustado) -- el R² del ajuste debe caer bajo
    `MIN_APERIODIC_R_SQUARED` y el motor debe declarar `available=False`,
    NUNCA fabricar un chi sobre un ajuste que no representa nada."""
    rng = np.random.default_rng(42)
    n = int(_DURATION_S * _FS)
    signal = rng.normal(0, 1, n) * 5.0

    freqs, psd = _welch_psd(signal)
    result = fit_aperiodic_component(freqs, psd, DEFAULT_APERIODIC_FREQ_RANGE)

    assert result.available is False
    assert result.exponent is None
    assert result.reason is not None and "R²" in result.reason
    assert result.r_squared is not None and result.r_squared < MIN_APERIODIC_R_SQUARED


def test_empty_psd_degrades_honestly_without_calling_fooof():
    """Borde: PSD vacío (p.ej. si un llamador futuro pasa el resultado
    degradado de `EegAnalyzer` -- `band_power={}` -- sin comprobar
    `available` primero). Debe declarar no-disponible sin intentar ajustar
    nada, mismo espíritu que el gate de `_neurological_state()`."""
    result = fit_aperiodic_component(np.array([]), np.array([]))
    assert result.available is False
    assert result.reason is not None


def test_named_config_constants_are_documented_not_magic():
    """Config nombrada (ver comentarios de calibración en
    `spectral_model.py`), no constantes mágicas -- deben existir y ser
    razonables."""
    assert 0.0 < MIN_APERIODIC_R_SQUARED < 1.0
    assert DEFAULT_APERIODIC_FREQ_RANGE[0] > 0.0
    assert DEFAULT_APERIODIC_FREQ_RANGE[1] > DEFAULT_APERIODIC_FREQ_RANGE[0]


def test_generate_colored_noise_matches_prescribed_chi_via_log_log_slope():
    """Barandilla directa del propio generador de ground truth, SIN pasar
    por FOOOF -- confirma por regresión log-log simple que
    `generate_colored_noise()` de verdad produce la pendiente prescrita,
    para que un fallo de `fit_aperiodic_component()` no pueda esconderse
    detrás de un generador roto (ambos se validan por separado)."""
    chi_true = 1.5
    signal = generate_colored_noise(chi_true, _DURATION_S, _FS, seed=7) * 40.0
    freqs, psd = _welch_psd(signal)

    mask = (freqs >= 2.0) & (freqs <= 40.0)  # evita DC y el borde de Nyquist
    log_f = np.log10(freqs[mask])
    log_p = np.log10(psd[mask])
    slope, _intercept = np.polyfit(log_f, log_p, 1)

    # PSD ~ 1/f^chi => pendiente log-log == -chi
    assert slope == pytest.approx(-chi_true, abs=0.3)


# --- Aislamiento: confirmado por grep de IMPORTS reales, no por asunción ---

def test_spectral_model_import_surface_matches_arco_2c_wiring():
    """Arco 2B mantenía `spectral_model.py` sin ningún importador de
    producción. Arco 2C lo eleva DELIBERADAMENTE -- `builder.py` (Parte C)
    y `page_content.py` del EEG Lab (Parte D) ahora SÍ lo importan para
    persistir/gatear el χ. Esta prueba ya no confirma "cero importadores"
    (dejó de ser cierto a propósito) sino la frontera que SIGUE vigente:

    1. `eeg_analyzer.py`/`eeg_generator.py` (el motor Welch/rechazo de
       artefactos de Arco 2A) NUNCA importan `spectral_model` -- el motor de
       señal permanece desacoplado de `fooof`; solo expone el PSD que ya
       calculaba para que OTRO módulo lo consuma.
    2. Solo los dos archivos explícitamente cableados en 2C lo importan --
       ningún otro archivo de `app/`/`domain/` debería hacerlo sin que este
       test se actualice a propósito (igual que se actualizó de 2B a 2C).

    Nota de diseño: la versión de 2B usaba una búsqueda de substring
    ("spectral_model" en cualquier parte del texto), que daba falso
    positivo sobre comentarios que MENCIONAN el módulo sin importarlo (p.ej.
    el docstring de `EegAnalysis` en `eeg_analyzer.py`, que documenta que
    NO lo importa). Esta versión busca declaraciones de import reales."""
    import pathlib
    import re

    repo_root = pathlib.Path(__file__).resolve().parent.parent
    import_pattern = re.compile(
        r"^\s*(from\s+\S*\bspectral_model\b\s+import|import\s+\S*\bspectral_model\b)",
        re.MULTILINE,
    )

    never_importers = [
        repo_root / "src" / "signals" / "eeg" / "eeg_analyzer.py",
        repo_root / "src" / "signals" / "eeg" / "eeg_generator.py",
    ]
    for path in never_importers:
        assert path.exists(), f"archivo esperado no encontrado: {path}"
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not import_pattern.search(text), (
            f"{path.relative_to(repo_root)} importa spectral_model -- el motor Welch/rechazo "
            f"de artefactos de Arco 2A debe permanecer desacoplado de fooof"
        )

    allowed_importers = {
        (repo_root / "domain" / "physiology" / "state" / "builder.py").resolve(),
        (repo_root / "app" / "supermodules" / "eeg_neuro_lab" / "page_content.py").resolve(),
    }

    actual_importers = set()
    for directory in (repo_root / "app", repo_root / "domain"):
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if import_pattern.search(text):
                actual_importers.add(path.resolve())

    unexpected = actual_importers - allowed_importers
    assert unexpected == set(), (
        f"archivos de producción NO previstos por Arco 2C importan spectral_model: "
        f"{[str(p.relative_to(repo_root)) for p in unexpected]}"
    )
    missing = allowed_importers - actual_importers
    assert missing == set(), (
        f"el cableado de Arco 2C todavía no está completo -- faltan imports en: "
        f"{[str(p.relative_to(repo_root)) for p in missing]}"
    )
