"""
Arco 2B (2026-09-14) -- motor de parametrización espectral (exponente
aperiódico chi), banco de pruebas AISLADO envolviendo `fooof` 1.1.1
(Donoghue et al. 2020, Nature Neuroscience -- "Parameterizing neural power
spectra into periodic and aperiodic components"). Separa el componente
aperiódico 1/f^chi del PSD de las oscilaciones verdaderas; chi es candidato
a biomarcador de balance excitación/inhibición, pero NO lo es todavía en
este repo.

Por qué un banco de pruebas y no un swap: el diagnóstico de 2B estableció
que FOOOF SIEMPRE devuelve un número plausible para chi -- un ajuste sesgado
no se auto-denuncia. `chi` solo cuenta como "recuperado" cuando se mide
contra una señal de chi CONOCIDO por construcción y el error resulta bajo
(ver `tests/test_eeg_aperiodic_spectral_model.py`), igual que el PLV
neurocardíaco (`app/supermodules/biomarkers.py`) se verificó contra fase
sintética conocida antes de confiar en él.

Arco 2C (2026-09-14) -- ELEVADO a producción, aditivamente: `builder.py`
(`domain/physiology/state/`) y `app/supermodules/eeg_neuro_lab/
page_content.py` ahora SÍ importan este módulo (ver `CHI_APERIODIC_CITATION`
más abajo) -- el aislamiento de 2B era deliberadamente temporal, para
validar el motor antes de cablearlo, no una barrera permanente.
`eeg_analyzer.py`/`eeg_generator.py` siguen SIN importarlo (confirmado por
`tests/test_eeg_aperiodic_spectral_model.py`): el motor Welch/rechazo de
artefactos permanece desacoplado de `fooof`, solo expone el PSD que ya
calculaba (`EegAnalysis.psd_freqs`/`psd_power`/`clean_window_count`) para
que ESTE módulo lo consuma desde fuera.

El mini-diagnóstico de 2C (mismo día, previo a esta tanda) encontró que el
R² del ajuste FOOOF protege contra "ajuste de mala calidad" pero NO contra
"evidencia insuficiente" -- son ejes distintos. Con pocas ventanas (10s @
1Hz de producción = 10 ventanas), el ajuste puede reportar R²=0.97
(confiado) con un chi desviado 0.28 del real (fuera de la tolerancia de
0.095-0.14 medida con suficiente señal). `MIN_CHI_CLEAN_WINDOWS` (ver abajo)
es el segundo guardián que cierra esa trampa -- independiente del R².

SEGUNDO hallazgo, encontrado DURANTE la implementación de esta misma tanda
(no en el mini-diagnóstico previo -- su réplica de "PSD de producción" se
saltó `preprocess_eeg()` por error, así que nunca corrió el bandpass real):
sobre el pipeline de producción COMPLETO (bandpass Butterworth orden 2,
0.5-40Hz, + ventaneo), el chi recuperado llevaba un SESGO sistemático de
~+0.46 (15 semillas, grid completo, con y sin picos) -- el roll-off del
filtro dentro del propio rango de ajuste (1-45Hz) distorsiona la PENDIENTE
log-log que chi mide, algo que BAR/DAR/TBR nunca sufren porque integran
potencia por banda, no pendiente. `correct_bandpass_attenuation()` (ver
abajo) es la corrección PRINCIPIADA -- no un factor de ajuste empírico:
divide el PSD medido por la ganancia de potencia EXACTA del mismo filtro
`(b, a) = butter(FILTER_ORDER, ...)` que `preprocess_eeg()` usa (calculada
vía `scipy.signal.freqz` sobre los MISMOS coeficientes, elevada al cuadrado
una vez más para la doble pasada de `filtfilt`). Tras corregir: sesgo medio
~0.00 a -0.05, error máximo 0.174 (dur=40s) / 0.179 (dur=30s, el piso exacto
de `MIN_CHI_CLEAN_WINDOWS`) -- dentro de la tolerancia de 0.2 que 2B ya
había establecido como significativa, SIN necesidad de angostar
`DEFAULT_APERIODIC_FREQ_RANGE` (se probaron rangos más angostos como
mitigación antes de encontrar la corrección real -- todos con sesgo residual
o varianza alta; se abandonaron a favor de esta corrección, que sí elimina
la causa). El gate de ventanas (`MIN_CHI_CLEAN_WINDOWS`) sigue siendo
NECESARIO incluso con la corrección -- a 10s (por debajo del piso) el sesgo
desaparece pero la VARIANZA por pocas ventanas promediadas sigue empujando
el error fuera de tolerancia en el peor caso (hasta 0.29, R² igual de alto).
Son dos guardianes independientes -- ninguno reemplaza al otro.

Arco 2D (2026-09-18) -- CIERRA el aislamiento clínico: firma del experto
aplicada (fuente: Gao R, Peterson EJ, Voytek B. 2017, "Inferring synaptic
excitation/inhibition balance from field potentials"). `PENDING_VALIDATION`
se retira del chi; el descriptor persistido pasa a `VALIDADO_POR_FUENTE`
con la cláusula de alcance explícita ("índice de E/I cortical por analogía
LFP, sobre EEG de superficie") -- mismo patrón que DAR/TBR en Neuro
Tanda 2, salvo que aquí conviven DOS citas de ejes distintos: la
METODOLÓGICA (`CHI_APERIODIC_CITATION`, Donoghue et al. 2020 -- respalda el
ALGORITMO de ajuste FOOOF) y la CLÍNICA (`CHI_CITATION`, Gao et al. 2017 --
respalda la INTERPRETACIÓN del número ya ajustado). Ver `CHI_THRESHOLDS`/
`classify_chi()` más abajo, junto a la barandilla de holgura del instrumento
(`CHI_INSTRUMENT_ERROR`) que impide afilar esos umbrales por debajo del
piso que 2C midió.

Consume el PSD de Welch que `EegAnalyzer._welch_with_artifact_rejection()`
(Arco 2A) ya produce sobre señal limpia -- el diagnóstico de 2B confirmó
que el exponente aperiódico es una propiedad del espectro PROMEDIADO, no de
su evolución temporal: no requiere CWT/Morlet (eso es Mu ERD, un arco
separado, sin sustrato todavía en este repo). Este módulo no importa
`eeg_analyzer.py` -- toma `(freqs, power_spectrum)` genéricos como
parámetros, para no acoplarse a esa implementación.

NOTA DE HONESTIDAD (Art. I y IV): `generate_colored_noise()`/
`add_synthetic_peak()` construyen señal SINTÉTICA con chi prescrito
matemáticamente -- no un registro EEG real. El banco de pruebas valida que
el motor RECUPERA un chi conocido; no valida que un chi sobre EEG real
tenga el sentido clínico de balance E/I que la literatura le atribuye --
esa validación clínica es explícitamente trabajo de 2D, no de esta tanda.
Mismo criterio que `generate_blink_artifact` (Arco 2A): ground truth de
banco de pruebas, jamás presentado como dato de paciente.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple

from fooof import FOOOF
from scipy.signal import butter, freqz

from .preprocessing import DEFAULT_HIGHCUT_HZ, DEFAULT_LOWCUT_HZ, FILTER_ORDER

# --- Config nombrada (mismo espíritu que ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S
# en eeg_analyzer.py o MIN_PLV_DURATION_S en biomarkers.py): valores de
# ingeniería razonables, anotados para que un experto los ajuste -- NO
# umbrales clínicos citados como DAR_THRESHOLDS/TBR_THRESHOLDS. ------------

# R² mínimo del ajuste FOOOF para aceptar el chi como recuperado. Calibrado
# EMPÍRICAMENTE (Arco 2B, 2026-09-14) contra el banco de pruebas: sobre
# ruido blanco puro (sin estructura 1/f), 15 semillas dieron R² máximo
# ~0.72; sobre ruido 1/f^chi bien formado -- incluso el peor caso medido,
# chi=0.5 con picos alfa/beta superpuestos, 15 semillas -- el R² mínimo fue
# ~0.87. 0.80 separa ambas poblaciones con margen hacia los dos lados. Es
# un default de ingeniería sobre señal SINTÉTICA -- pendiente de recalibrar
# si este motor se cablea a EEG real (ver nota de honestidad del módulo).
MIN_APERIODIC_R_SQUARED: float = 0.80

# Rango de frecuencia sobre el que se ajusta el aperiódico -- excluye DC (el
# aperiódico 1/f^chi no está definido en f=0) y la cola por encima de la
# banda EEG estándar, donde el PSD de Welch de producción (ventanas de 1s,
# resolución de 1Hz -- ver Arco 2A) tiene pocos puntos fiables. Cubre las 5
# bandas que ya calcula `EegAnalyzer` (delta..gamma).
DEFAULT_APERIODIC_FREQ_RANGE: Tuple[float, float] = (1.0, 45.0)

# --- Arco 2C (2026-09-14): corrección PRINCIPIADA del sesgo del bandpass ---
#
# `preprocess_eeg()` (Arco 2A, `preprocessing.py`) filtra la señal ANTES de
# que `EegAnalyzer` calcule el PSD que este módulo consume. Un filtro
# Butterworth de orden `FILTER_ORDER` no es plano dentro de su propia banda
# de paso -- su roll-off distorsiona la PENDIENTE log-log que chi mide
# (a diferencia de BAR/DAR/TBR, que integran potencia por banda y no sufren
# esto). Descubierto DURANTE esta tanda (ver docstring del módulo): sobre el
# pipeline real, sin corregir, chi llevaba un sesgo sistemático de ~+0.46.
#
# La corrección es una DECONVOLUCIÓN exacta, no un factor empírico: divide
# el PSD medido por la ganancia de POTENCIA del mismo filtro
# `(b, a) = butter(FILTER_ORDER, [lowcut, highcut], btype='band')` que
# `preprocess_eeg()` aplica, calculada con `scipy.signal.freqz` sobre esos
# MISMOS coeficientes -- no una aproximación analítica separada que pueda
# desincronizarse si alguien cambia el filtro de producción.


def _bandpass_power_gain(
    freqs: np.ndarray,
    fs: float,
    lowcut_hz: float = DEFAULT_LOWCUT_HZ,
    highcut_hz: float = DEFAULT_HIGHCUT_HZ,
    order: int = FILTER_ORDER,
) -> np.ndarray:
    """Ganancia de POTENCIA del bandpass de `preprocess_eeg()` en cada
    frecuencia de `freqs`, tal como afecta al PSD que `EegAnalyzer` produce.
    Una sola pasada del filtro tiene ganancia de potencia `|H(f)|²`;
    `preprocess_eeg()` usa `filtfilt` (adelante + atrás), que ELEVA AL
    CUADRADO la ganancia de amplitud total (`|H(f)|²` en vez de `|H(f)|`) --
    así que la ganancia de POTENCIA de la doble pasada es `|H(f)|²` al
    cuadrado, `|H(f)|⁴`."""
    nyquist = 0.5 * fs
    b, a = butter(order, [lowcut_hz / nyquist, highcut_hz / nyquist], btype='band')
    _, h = freqz(b, a, worN=np.asarray(freqs, dtype=float), fs=fs)
    single_pass_power_gain = np.abs(h) ** 2
    return single_pass_power_gain ** 2  # doble pasada (filtfilt)


def correct_bandpass_attenuation(
    freqs: np.ndarray,
    power_spectrum: np.ndarray,
    fs: float,
    lowcut_hz: float = DEFAULT_LOWCUT_HZ,
    highcut_hz: float = DEFAULT_HIGHCUT_HZ,
    order: int = FILTER_ORDER,
) -> np.ndarray:
    """Corrige un PSD que pasó por `preprocess_eeg()` (`fs`, `lowcut_hz`,
    `highcut_hz`, `order` DEBEN coincidir con los que se usaron para
    filtrar) dividiendo por la ganancia de potencia exacta del filtro --
    recupera una estimación del PSD que el aperiódico 1/f^chi tendría SIN el
    filtro de por medio. Ganancia limitada a un piso de `1e-6`: lejos de la
    banda de paso el filtro ya eliminó la señal real -- corregir ahí solo
    amplificaría ruido de cuantización, no información recuperable (y esas
    frecuencias quedan fuera de `DEFAULT_APERIODIC_FREQ_RANGE` de todos
    modos)."""
    gain = _bandpass_power_gain(freqs, fs, lowcut_hz, highcut_hz, order)
    gain = np.maximum(gain, 1e-6)
    return np.asarray(power_spectrum, dtype=float) / gain


# --- Arco 2C (2026-09-14): gate de duración propio del chi -----------------
#
# Piso de ventanas limpias (de `ARTIFACT_WINDOW_S`=1.0s cada una, ver
# `eeg_analyzer.py`) para ACEPTAR el chi recuperado -- MÁS ESTRICTO que
# `MIN_CLEAN_EEG_DURATION_S` (2.0s, `eeg_analyzer.py`), que se calibró para
# BAR/DAR/TBR: esos ratios solo necesitan la ENERGÍA integrada por banda,
# no la FORMA fina del espectro que un ajuste log-log de pendiente exige.
#
# Calibrado EMPÍRICAMENTE sobre el pipeline de PRODUCCIÓN COMPLETO
# (`EegAnalyzer.analyze()` real -- bandpass + ventaneo 1Hz + rechazo de
# artefactos -- no una réplica aislada), CON `correct_bandpass_attenuation()`
# activa (ver más arriba), grid completo de chi (0.5/1.0/1.5/2.0), 15
# semillas por punto:
#
#   10 ventanas (10s) -> error máx. de recuperación 0.289, CON R² hasta
#     0.982 -- EXCEDE la tolerancia de 0.2 que 2B midió como significativa.
#     La corrección de bandpass elimina el SESGO (media ~0.00 a -0.06 a esta
#     duración), pero no la VARIANZA de promediar pocas ventanas -- son
#     problemas distintos; este gate cierra el segundo, no el primero.
#   30 ventanas (30s, el piso elegido) -> error máx. 0.179 -- dentro de
#     tolerancia, con margen.
#   40 ventanas (40s) -> error máx. 0.174.
#
# (Nota histórica: una primera calibración de este gate, sin la corrección
# de bandpass de más arriba, midió números parecidos por una razón distinta
# -- su réplica de "PSD de producción" nunca corrió `preprocess_eeg()`, así
# que medía solo varianza de ventaneo, no el sesgo real del filtro. Esta
# versión mide sobre el pipeline real, con la corrección puesta.)
#
# Coincide con el valor por defecto real del slider "Duración (segundos)"
# del EEG Lab (`page_content.py`), así que en uso normal de la UI el chi
# rara vez degrada por este gate; solo lo hace si el usuario baja el slider
# cerca de su mínimo (10s) o si el rechazo de artefactos de Arco 2A descarta
# suficientes ventanas de una captura más larga. Config nombrada, no mágica
# -- pendiente de recalibrar si este motor se valida contra EEG real (ver
# nota de honestidad del módulo).
MIN_CHI_CLEAN_WINDOWS: int = 30

# Cita METODOLÓGICA (Art. I y IV) -- respalda el ALGORITMO de ajuste
# (Donoghue et al. 2020), NO el significado clínico del número. A
# diferencia de `BAR_CITATION`/`DAR_CITATION`/`TBR_CITATION`
# (`eeg_analyzer.py`), que citan el valor DIAGNÓSTICO de cada ratio, esta
# cita respalda únicamente que FOOOF separa aperiódico/periódico
# correctamente. Qué chi indica qué balance excitación/inhibición es un eje
# DISTINTO, respaldado por `CHI_CITATION` (más abajo, Arco 2D) -- las dos
# citas coexisten en el `source_detail` que persiste `builder.py`, cada una
# defendiendo su propio alcance.
CHI_APERIODIC_CITATION: str = (
    "Donoghue T et al. 2020, Nature Neuroscience 23(12):1655-1665 "
    "(\"Parameterizing neural power spectra into periodic and aperiodic "
    "components\") -- cita METODOLÓGICA del ajuste FOOOF, NO de la "
    "interpretación clínica de chi (ver CHI_CITATION)"
)


# --- Arco 2D (2026-09-18): firma del experto -- interpretación clínica -----
#
# Fuente: Gao R, Peterson EJ, Voytek B. 2017, NeuroImage 158:70-78
# ("Inferring synaptic excitation/inhibition balance from field
# potentials"). Dirección: chi PLANO (bajo) -> mayor excitación relativa;
# chi EMPINADO (alto) -> mayor inhibición relativa -- el mismo sentido que
# la pendiente 1/f^chi mide sobre el campo local.
#
# CLÁUSULA DE ALCANCE (honestidad, Art. I): Gao 2017 valida chi como índice
# de balance E/I sobre POTENCIALES DE CAMPO LOCAL (LFP, registro
# intracraneal). Este repo lo aplica por ANALOGÍA sobre EEG de SUPERFICIE
# (`fit_aperiodic_component()` corre sobre el PSD de scalp que
# `EegAnalyzer` produce) -- una extrapolación razonable, no la misma
# medición. `CHI_CITATION` incluye esta cláusula en su propio texto --
# nunca "mide E/I" a secas, siempre "índice de E/I cortical por analogía
# LFP, sobre EEG de superficie".
#
# Umbrales VALIDADOS_POR_FUENTE (firma del experto, 2026-09-18) -- gruesos a
# propósito, ver barandilla de holgura debajo:
#   🔴 <1.0 excitación (tejido anómalamente activo/hiperexcitado)
#   🔵 1.0-1.6 indeterminado/línea base (el error del instrumento no
#      discrimina dentro de esta banda -- se reporta el valor, nunca se
#      asume un estado)
#   💤 >1.6 inhibición (tejido suprimido/enlentecimiento global)
# Ver `classify_chi()` más abajo.
#
# BARANDILLA DE HOLGURA (no negociable): Arco 2C midió, sobre el pipeline de
# producción completo, un error de recuperación de chi de hasta
# `CHI_INSTRUMENT_ERROR` = 0.175 (peor caso dentro del piso aceptado,
# `MIN_CHI_CLEAN_WINDOWS`=30 ventanas / 30s). La banda indeterminada
# (1.0->1.6 = 0.60) es >3x ese error -- las fronteras viven SOBRE la
# medición real, no sobre una precisión que no tenemos.
# `tests/test_eeg_chi_expert_signature.py` graba este piso en la suite: si
# alguien afila `CHI_THRESHOLDS` por debajo de él, el test falla.
CHI_INSTRUMENT_ERROR: float = 0.175
CHI_THRESHOLDS: Tuple[float, float] = (1.0, 1.6)  # (techo "excitación", piso "inhibición")
CHI_CITATION: str = (
    "Gao R, Peterson EJ, Voytek B. 2017, NeuroImage 158:70-78 (\"Inferring synaptic "
    "excitation/inhibition balance from field potentials\") -- índice de E/I cortical por "
    "analogía LFP, sobre EEG de superficie -- VALIDADO_POR_FUENTE"
)


def classify_chi(chi: Optional[float]) -> Tuple[str, str, str]:
    """Clasifica un valor chi según los umbrales VALIDADOS_POR_FUENTE (ver
    `CHI_THRESHOLDS`/`CHI_CITATION`). Mismo patrón que `classify_dar()`/
    `classify_tbr()` (`eeg_analyzer.py`): devuelve `(nivel, etiqueta,
    badge)`.

    `None` (chi no disponible -- degradado por cualquiera de los dos
    guardianes de Arco 2C, `MIN_CHI_CLEAN_WINDOWS`/R², o simplemente
    ausente) -> `("no_disponible", "no disponible", "")` -- NUNCA un estado
    por default.

    La banda `🔵` intermedia (1.0-1.6) es un estado clínico HONESTO, no una
    ausencia ni un "todo bien" verde: significa "cerca de línea base, no
    discriminable a esta resolución" -- `CHI_INSTRUMENT_ERROR` es demasiado
    grande para afirmar excitación o inhibición dentro de esa banda."""
    if chi is None:
        return ("no_disponible", "no disponible", "")
    excitacion_techo, inhibicion_piso = CHI_THRESHOLDS
    if chi < excitacion_techo:
        return ("excitacion", "excitación cortical (hiperexcitabilidad)", "🔴")
    if chi <= inhibicion_piso:
        return ("indeterminado", "indeterminado / línea base", "🔵")
    return ("inhibicion", "inhibición cortical (supresión/enlentecimiento)", "💤")


@dataclass(frozen=True)
class AperiodicComponent:
    """Resultado del ajuste espectral aperiódico (chi, offset) vía FOOOF.
    Mismo patrón honesto que `PLVResult` (`app/supermodules/biomarkers.py`)
    y `EegAnalysis` (`eeg_analyzer.py`, Arco 2A): `available` distingue
    explícitamente "no disponible (con motivo)" de "chi=x" -- NUNCA un
    número de relleno cuando el ajuste falla o es de mala calidad."""
    available: bool
    # chi -- el exponente aperiódico 1/f^chi. Solo presente si available.
    exponent: Optional[float] = None
    offset: Optional[float] = None
    # Calidad del ajuste FOOOF -- se reporta incluso cuando degrada (útil
    # para ver "qué tan cerca estuvo" de pasar el umbral), salvo que el PSD
    # de entrada estuviera vacío (ahí no hay ajuste que reportar).
    r_squared: Optional[float] = None
    # Motivo de no-disponibilidad, solo si available=False -- información
    # pedagógica, nunca un error crudo.
    reason: Optional[str] = None


def fit_aperiodic_component(
    freqs: np.ndarray,
    power_spectrum: np.ndarray,
    freq_range: Tuple[float, float] = DEFAULT_APERIODIC_FREQ_RANGE,
    clean_window_count: Optional[int] = None,
    bandpass_fs: Optional[float] = None,
) -> AperiodicComponent:
    """Ajusta `fooof.FOOOF` sobre un PSD ya calculado (p.ej. el que
    `EegAnalyzer._welch_with_artifact_rejection()` produce sobre señal
    limpia, reexpuesto en `EegAnalysis.psd_freqs`/`psd_power` desde Arco 2C)
    y extrae el componente aperiódico (chi, offset). Degrada honestamente
    (`available=False`) por CUALQUIERA de dos guardianes independientes:

    1. `clean_window_count` (si se provee) por debajo de
       `MIN_CHI_CLEAN_WINDOWS` -- evidencia insuficiente. Se comprueba
       ANTES de invocar FOOOF, a propósito: el mini-diagnóstico de 2C
       encontró que con pocas ventanas el ajuste puede reportar un R² alto
       (confiado) con un chi desviado muy por encima de la tolerancia
       medida -- el R² no protege contra esto, mide calidad de ajuste, no
       suficiencia de evidencia. `clean_window_count=None` (el caso del
       banco de pruebas de 2B, que no modela ventanas de producción) deja
       este guardián sin efecto -- no es una regresión del contrato de 2B.
    2. R² del ajuste FOOOF bajo `MIN_APERIODIC_R_SQUARED` -- ajuste de mala
       calidad, con evidencia suficiente pero un espectro que no se explica
       bien con un aperiódico+picos.

    Nunca fabrica un chi sobre un ajuste malo O insuficiente -- mismo
    criterio que la degradación tipo-PLV de `EegAnalyzer` (Arco 2A).

    `bandpass_fs`: si el PSD de entrada pasó por `preprocess_eeg()` (que es
    SIEMPRE el caso de `EegAnalysis.psd_freqs`/`psd_power` en producción --
    `EegAnalyzer.analyze()` filtra antes de calcular el PSD), pasar aquí el
    `fs` usado corrige el sesgo sistemático que ese bandpass introduce sobre
    chi (~+0.46 sin corregir, ver docstring del módulo) ANTES del ajuste,
    vía `correct_bandpass_attenuation()`. `None` (el default, y lo que usa
    el banco de pruebas de 2B con señal sintética SIN filtrar) deja el PSD
    sin corregir -- aplicar la corrección sobre un PSD que nunca pasó por
    ese filtro introduciría un sesgo nuevo en la dirección opuesta."""
    freqs = np.asarray(freqs, dtype=float)
    power_spectrum = np.asarray(power_spectrum, dtype=float)

    if freqs.size == 0 or power_spectrum.size == 0:
        return AperiodicComponent(
            available=False,
            reason="PSD vacío: no hay espectro sobre el que ajustar el componente aperiódico",
        )

    if bandpass_fs is not None:
        power_spectrum = correct_bandpass_attenuation(freqs, power_spectrum, bandpass_fs)

    if clean_window_count is not None and clean_window_count < MIN_CHI_CLEAN_WINDOWS:
        return AperiodicComponent(
            available=False,
            reason=(
                f"señal insuficiente para χ: {clean_window_count} ventanas < mínimo "
                f"{MIN_CHI_CLEAN_WINDOWS} -- el ajuste puede reportar R² alto con χ sesgado "
                "(evidencia insuficiente, no un ajuste de mala calidad -- ver MIN_CHI_CLEAN_WINDOWS)"
            ),
        )

    fm = FOOOF(verbose=False)
    try:
        fm.fit(freqs, power_spectrum, freq_range)
    except Exception as exc:
        return AperiodicComponent(available=False, reason=f"el ajuste FOOOF falló: {exc}")

    r_squared = getattr(fm, "r_squared_", None)
    if r_squared is None or not np.isfinite(r_squared):
        return AperiodicComponent(available=False, reason="el ajuste FOOOF no produjo un R² válido")

    if r_squared < MIN_APERIODIC_R_SQUARED:
        return AperiodicComponent(
            available=False,
            r_squared=float(r_squared),
            reason=(
                f"ajuste de baja calidad: R²={r_squared:.2f} < mínimo "
                f"{MIN_APERIODIC_R_SQUARED:.2f} -- la señal no muestra estructura 1/f clara"
            ),
        )

    exponent = float(fm.get_params("aperiodic_params", "exponent"))
    offset = float(fm.get_params("aperiodic_params", "offset"))

    return AperiodicComponent(
        available=True,
        exponent=exponent,
        offset=offset,
        r_squared=float(r_squared),
        reason=None,
    )


def generate_colored_noise(chi: float, duration: float, fs: float, seed: Optional[int] = None) -> np.ndarray:
    """Ground truth sintético (Art. I y IV -- NO es registro real): ruido
    con densidad espectral de potencia ~ 1/f^chi, chi PRESCRITO por
    construcción. Método estándar de filtrado espectral: ruido blanco ->
    FFT -> escalar magnitud por 1/f^(chi/2) (la potencia ~1/f^chi implica
    amplitud ~1/f^(chi/2)) -> IFFT. Sin esta función no hay forma de
    distinguir un chi recuperado correctamente de uno plausible pero
    sesgado -- es la pieza que hace honesto al banco de pruebas.

    Normaliza a desviación estándar unitaria: el llamador escala a la
    amplitud (µV) que necesite para su escenario."""
    if duration <= 0 or fs <= 0:
        raise ValueError("duration y fs deben ser positivos")

    rng = np.random.default_rng(seed)
    n = int(duration * fs)
    white = rng.normal(0, 1, n)

    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)

    scale = np.zeros_like(freqs)
    nonzero = freqs > 0
    scale[nonzero] = 1.0 / np.power(freqs[nonzero], chi / 2.0)
    # scale[0] (DC) queda en 0.0 -- el aperiódico 1/f^chi no está definido
    # en f=0, así que no se le asigna ninguna magnitud arbitraria.

    colored = np.fft.irfft(spectrum * scale, n=n)
    return colored / np.std(colored)


def add_synthetic_peak(signal: np.ndarray, time: np.ndarray, center_hz: float, amplitude: float) -> np.ndarray:
    """Superpone una oscilación sintética (Art. IV -- NO real) de
    frecuencia/amplitud conocidas sobre ruido aperiódico -- simula el pico
    cortical (alfa, beta) que se monta sobre el fondo 1/f, para probar que
    el motor no confunde PICO con PENDIENTE del aperiódico (la trampa
    central que motiva este arco). Deliberadamente no importa
    `EegSignalGenerator._band_signal()` (`eeg_generator.py`) para mantener
    este módulo aislado de la superficie que sí alimenta la UI en vivo."""
    return signal + amplitude * np.sin(2 * np.pi * center_hz * time)
