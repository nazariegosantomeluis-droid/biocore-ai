"""
Mu ERD Tanda 1 (2026-09-26) -- detector de desincronización relacionada a
evento (ERD) en banda mu (8-13 Hz), método de Hilbert (filtrado de banda +
envolvente analítica al cuadrado = potencia instantánea). Estándar de la
literatura ERD/BCI (Pfurtscheller & Lopes da Silva 1999, "Event-related
EEG/MEG synchronization and desynchronization: basic principles") -- más
simple que un CWT/Morlet completo, y sin dependencia nueva: el diagnóstico
de viabilidad confirmó que `scipy.signal.cwt`/`morlet2` fueron retirados de
scipy (1.17.1 instalado aquí) y que `pywt` no está instalado, pero
`scipy.signal.hilbert` sí, y es el método que la propia literatura ERD usa
con más frecuencia que Morlet para una sola banda bien definida.

GENÉRICO por diseño (mismo criterio que `spectral_model.py` en Arco 2B):
recibe una señal 1-D + `fs` genéricos, SIN importar `eeg_analyzer.py`
(salvo dos constantes de configuración del rechazo de artefactos, para no
duplicar el umbral calibrado de Arco 2A) ni acoplarse a un canal nombrado.
Un C3/C4 real futuro reutilizaría este módulo sin refactor -- el mismo
motivo por el que `spectral_model.py` toma `(freqs, power_spectrum)`
genéricos en vez de un `EegAnalyzer`. Tanda 1 (2026-09-26) lo dejó AISLADO
-- probado solo, sin importar desde ningún consumidor -- para validarlo
contra ground truth antes de mostrarlo. Tanda 2 (mismo día) lo conecta al
EEG Neuro Lab (`app/supermodules/eeg_neuro_lab/page_content.py`), import
directo por módulo (mismo patrón que `spectral_model.py` -- nunca
reexportado desde `src/signals/eeg/__init__.py`, ver ese archivo). Sigue
SIN importarse desde `builder.py`/el UPS -- es una demostración de
fenómeno (Parte D, Tanda 2: `validation=None` del módulo mixto, no una
métrica clínica), no un escritor del organismo.

Fórmula ERD% (Pfurtscheller): ERD% = (potencia_baseline - potencia_evento)
/ potencia_baseline * 100 -- una caída de potencia se reporta como ERD%
POSITIVO; un aumento de potencia (ERS, sincronización) sale NEGATIVO, sin
recortar el signo -- el signo es información, no un error a esconder.

El "no colapsar el tiempo" del diagnóstico: `_welch_with_artifact_rejection`
(Arco 2A, `eeg_analyzer.py`) promedia el PSD de TODAS las ventanas limpias
de la señal COMPLETA en un solo número -- destruiría la distinción
antes/durante que un ERD necesita. Aquí el rechazo de artefactos (mismo
umbral de gradiente que 2A) se aplica DENTRO de cada ventana (baseline,
evento) por separado, sobre sub-ventanas de `ARTIFACT_WINDOW_S` -- una
sub-ventana contaminada se excluye de SU promedio local (baseline o
evento), nunca de un promedio global que mezclaría las dos fases.

NOTA DE HONESTIDAD (Art. I): `detect_mu_erd()` declara `available=False`
con motivo explícito ante baseline/evento insuficiente tras el rechazo de
artefactos, banda mu sin potencia detectable, o ventanas que se salen de la
señal -- nunca fabrica un ERD% de relleno. Calibrado y validado contra el
patrón `motor_imagery` de `eeg_generator.py` (evento SINTÉTICO, profundidad
conocida por construcción) -- su generalización a captura EEG real de
imaginación motora es trabajo futuro, cuando exista esa captura contra la
que calibrar (mismo límite que Arco 2A ya declaró para su propio rechazo de
artefactos).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy.signal import butter, filtfilt, hilbert

from .eeg_analyzer import ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S, ARTIFACT_WINDOW_S
from .preprocessing import preprocess_eeg

# Banda mu -- el rango citado en toda la literatura ERD/BCI de mano
# (Pfurtscheller & Lopes da Silva 1999). No confundir con la banda "alpha"
# de `eeg_analyzer.py` (8.0-12.0 Hz, un poco más angosta, sin la connotación
# sensorimotora) -- son constructos distintos, aunque solapen en frecuencia.
MU_LOW_HZ: float = 8.0
MU_HIGH_HZ: float = 13.0

# Orden del pasa-banda mu -- más angosto que el 0.5-40Hz de
# `preprocessing.py` (orden 2), así que necesita más orden para separar la
# banda de 5Hz de ancho de sus vecinas sin una transición demasiado ancha.
_MU_FILTER_ORDER: int = 4

# Mínimo de señal limpia (tras rechazo de artefactos) requerido en baseline
# y en la ventana de evento, cada uno por separado -- mismo espíritu que
# `MIN_CLEAN_EEG_DURATION_S` (Arco 2A) / `MIN_PLV_DURATION_S`
# (`biomarkers.py`): "necesito al menos esto de señal utilizable en CADA
# fase, o declaro indisponible", nunca un ERD sobre una fase casi vacía.
MIN_CLEAN_BASELINE_S: float = 1.0
MIN_CLEAN_EVENT_S: float = 1.0

# Cláusula de alcance -- viaja con el resultado desde su origen (Parte C),
# para que una tanda futura que muestre este dato no tenga que redescubrir
# el límite. Mismo patrón que `CHI_CITATION` lleva su cláusula de alcance
# ("índice de E/I cortical por analogía LFP, sobre EEG de superficie").
MU_ERD_SCOPE_NOTE: str = (
    "ERD central temporal, sin localización espacial -- demuestra el fenómeno de "
    "desincronización, no discrimina lateralidad (requiere captura multi-canal real)."
)


@dataclass(frozen=True)
class ErdResult:
    """Salida de `detect_mu_erd()`. `available=False` -> `erd_percent` y las
    potencias son `None` o parciales (lo que se alcanzó a medir antes de
    declinar) -- `reason` siempre está poblado en ese caso. `scope_note` es
    la cláusula de alcance de Parte C, presente en TODO resultado
    (disponible o no) -- el límite no depende de si la medición salió bien."""

    available: bool
    erd_percent: Optional[float]
    baseline_power: Optional[float]
    event_power: Optional[float]
    t_event: Optional[float]
    reason: Optional[str]
    scope_note: str = MU_ERD_SCOPE_NOTE


def _bandpass_mu(signal: np.ndarray, fs: float) -> np.ndarray:
    nyquist = 0.5 * fs
    low = MU_LOW_HZ / nyquist
    high = MU_HIGH_HZ / nyquist
    b, a = butter(_MU_FILTER_ORDER, [low, high], btype="band")
    return filtfilt(b, a, signal)


def compute_mu_power_timeseries(signal: np.ndarray, fs: float) -> np.ndarray:
    """Mu ERD Tanda 2 (2026-09-26) -- la curva COMPLETA de potencia
    instantánea en banda mu, para visualización (la curva que el
    estudiante ve caer alrededor del evento). MISMO pipeline exacto que
    `detect_mu_erd()` (`preprocess_eeg` -> `_bandpass_mu` -> Hilbert) --
    una fuente, dos consumidores: esta función y `detect_mu_erd()` nunca
    deberían divergir en CÓMO se calcula la potencia, solo en qué hacen
    con ella (una la dibuja completa, la otra la resume en baseline/evento
    con rechazo de artefactos). Sin rechazo de artefactos ni ventaneo aquí
    -- es la curva cruda, para que el estudiante vea también dónde
    quedaría un artefacto si lo hubiera, no una versión ya depurada."""
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1:
        signal = signal.flatten()
    wideband = preprocess_eeg(signal, fs)[0]
    filtered_mu = _bandpass_mu(wideband, fs)
    return np.abs(hilbert(filtered_mu)) ** 2


def _clean_window_mean_power(
    raw_signal: np.ndarray,
    inst_power: np.ndarray,
    fs: float,
    t_start: float,
    t_end: float,
    window_s: float,
) -> Tuple[Optional[float], float]:
    """Segmenta `[t_start, t_end)` en sub-ventanas de `window_s`; descarta
    las que excedan `ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S` de gradiente
    (medido sobre la señal YA pasada por `preprocess_eeg()`, 0.5-40Hz --
    mismo criterio que Arco 2A: un artefacto de banda ancha sobrevive ese
    filtro y se ve en su gradiente, mientras que el ruido blanco muestra-a-
    muestra ya quedó atenuado, evitando falsos rechazos); promedia la
    potencia instantánea (Hilbert, señal filtrada además a banda mu) SOLO
    de las sub-ventanas limpias.

    Devuelve `(potencia_media_o_None, segundos_limpios)`. Este promedio es
    LOCAL a la ventana pedida (baseline o evento) -- nunca se mezcla con la
    otra fase ni con el resto de la señal (ver NOTA sobre "no colapsar el
    tiempo" en el docstring del módulo)."""
    i_start = max(0, int(round(t_start * fs)))
    i_end = min(len(raw_signal), int(round(t_end * fs)))
    if i_end <= i_start:
        return None, 0.0

    window_samples = max(1, int(round(window_s * fs)))
    n_windows = (i_end - i_start) // window_samples
    if n_windows == 0:
        return None, 0.0

    clean_powers = []
    for w in range(n_windows):
        s = i_start + w * window_samples
        e = s + window_samples
        raw_segment = raw_signal[s:e]
        gradient = float(np.max(np.abs(np.diff(raw_segment))) * fs) if raw_segment.shape[0] > 1 else 0.0
        if gradient > ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S:
            continue
        clean_powers.append(float(np.mean(inst_power[s:e])))

    if not clean_powers:
        return None, 0.0
    return float(np.mean(clean_powers)), len(clean_powers) * window_samples / fs


def detect_mu_erd(
    signal: np.ndarray,
    fs: float,
    t_event: float,
    baseline_duration_s: float = 2.0,
    event_offset_s: float = 0.5,
    event_duration_s: float = 2.0,
    window_s: float = ARTIFACT_WINDOW_S,
    min_clean_baseline_s: float = MIN_CLEAN_BASELINE_S,
    min_clean_event_s: float = MIN_CLEAN_EVENT_S,
) -> ErdResult:
    """Genérico 1-D: `signal` es cualquier traza de un solo canal + `fs` --
    NO depende de `EegAnalyzer` ni de un nombre de canal (ver docstring de
    módulo). `t_event` es el instante CONOCIDO del evento (un disparador
    real de ensayo en captura futura; el `motor_event_time` inyectado por
    `eeg_generator.EegSignalGenerator` en el banco de pruebas de esta
    tanda) -- este detector nunca lo descubre por sí mismo, igual que
    ningún análisis ERD real descubre el momento de la señal de aviso.

    Ventanas: baseline = `[t_event - baseline_duration_s, t_event)`
    (reposo inmediatamente antes del evento); evento =
    `[t_event + event_offset_s, t_event + event_offset_s +
    event_duration_s)` -- el `event_offset_s` por defecto (0.5s) deja fuera
    la transición del propio evento (que en captura real sería la latencia
    fisiológica de inicio del ERD, aquí la rampa del generador), para medir
    la meseta ya asentada, no la pendiente.

    Degradación honesta (`available=False`, nunca un ERD fabricado):
    baseline pedido antes del inicio de la señal; ventana de evento después
    del final de la señal; baseline o evento con menos de
    `min_clean_baseline_s`/`min_clean_event_s` de señal limpia tras el
    rechazo de artefactos; potencia mu de baseline indistinguible de cero
    (ERD% indefinido sobre un denominador nulo, mismo criterio que
    `beta_alpha_ratio()` declara `None` en vez de forzar un infinito)."""
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1:
        signal = signal.flatten()

    total_duration_s = len(signal) / fs
    baseline_start = t_event - baseline_duration_s
    baseline_end = t_event
    event_start = t_event + event_offset_s
    event_end = event_start + event_duration_s

    if baseline_start < 0.0:
        return ErdResult(
            False, None, None, None, t_event,
            f"la ventana de baseline pedida [{baseline_start:.2f}s, {baseline_end:.2f}s) "
            "empieza antes del inicio de la señal -- se necesita más reposo antes de t_event",
        )
    if event_end > total_duration_s:
        return ErdResult(
            False, None, None, None, t_event,
            f"la ventana de evento pedida [{event_start:.2f}s, {event_end:.2f}s) excede la "
            f"duración de la señal ({total_duration_s:.2f}s)",
        )

    # Mismo pipeline que Arco 2A (`EegAnalyzer.analyze()`): pasa-banda ancho
    # PRIMERO (`preprocess_eeg`, 0.5-40Hz), y el rechazo de artefactos por
    # gradiente corre sobre ESA señal, no sobre la cruda. `ARTIFACT_GRADIENT_
    # THRESHOLD_UV_PER_S` se calibró post-bandpass -- sobre la señal cruda,
    # el ruido blanco muestra-a-muestra (`noise_level` del generador, o
    # ruido de hardware real) infla el gradiente muy por encima del umbral
    # incluso sin ningún artefacto real, disparando falsos rechazos.
    #
    # `wideband` se recalcula aquí (en vez de reusar `compute_mu_power_
    # timeseries()` completo) porque el rechazo de artefactos necesita la
    # señal de banda ANCHA para su gradiente -- `compute_mu_power_
    # timeseries()` solo devuelve la potencia ya angosta a mu, no expone el
    # intermedio. Mismas dos llamadas (`preprocess_eeg` + `_bandpass_mu`),
    # sin fórmula duplicada.
    wideband = preprocess_eeg(signal, fs)[0]
    filtered_mu = _bandpass_mu(wideband, fs)
    inst_power = np.abs(hilbert(filtered_mu)) ** 2

    baseline_power, baseline_clean_s = _clean_window_mean_power(
        wideband, inst_power, fs, baseline_start, baseline_end, window_s
    )
    if baseline_power is None or baseline_clean_s < min_clean_baseline_s:
        return ErdResult(
            False, None, baseline_power, None, t_event,
            f"baseline insuficiente tras rechazo de artefactos: {baseline_clean_s:.1f}s limpios "
            f"de {baseline_duration_s:.1f}s pedidos (mínimo {min_clean_baseline_s:.1f}s)",
        )
    if baseline_power <= 0.0:
        return ErdResult(
            False, None, baseline_power, None, t_event,
            "potencia de banda mu en baseline indistinguible de cero -- ERD% indefinido sobre "
            "un denominador nulo",
        )

    event_power, event_clean_s = _clean_window_mean_power(
        wideband, inst_power, fs, event_start, event_end, window_s
    )
    if event_power is None or event_clean_s < min_clean_event_s:
        return ErdResult(
            False, None, baseline_power, event_power, t_event,
            f"ventana de evento insuficiente tras rechazo de artefactos: {event_clean_s:.1f}s "
            f"limpios de {event_duration_s:.1f}s pedidos (mínimo {min_clean_event_s:.1f}s)",
        )

    erd_percent = (baseline_power - event_power) / baseline_power * 100.0
    return ErdResult(True, erd_percent, baseline_power, event_power, t_event, None)
