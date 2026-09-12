"""
EEG Analyzer - Frequency band analysis and clinical pattern classification.

Arco 2A (2026-09-11): bandpass activado + rechazo de artefactos por
gradiente. `preprocess_eeg()` (`preprocessing.py`, butter 0.5-40 Hz) tenía
CERO llamadores en todo el repo -- `analyze()` iba directo de señal cruda
al PSD de Welch, así que BAR/DAR/TBR (Neuro Tanda 1/2, firmados sobre la
premisa de banda estándar Welch) corrían sobre una señal ni siquiera
filtrada. Confirmado por grep antes de tocar nada (mismo procedimiento que
el shadow `preprocess_emg` saneado en la Tanda 1 muscular): el único
llamador vivo de `EegAnalyzer.analyze()` es `eeg_neuro_lab/page_content.py`
(un bucle `analyzer.analyze(eeg_data[lead])` por canal), que solo lee
`band_power`/`dominant_band`/`bar`/`dar`/`tbr`/`findings` del resultado --
ninguno depende de que la entrada sea cruda.

El diagnóstico previo (mismo día) probó empíricamente que un parpadeo
(pulso Hann ~50ms, ~80µV, `EegSignalGenerator._blink_artifacts()`) añade un
piso de potencia a TODAS las bandas -- insignificante como % de una banda
grande, devastador como % de una banda pequeña. Como alpha es el
denominador de BAR y DAR, un parpadeo puede colapsar el BAR de 62 a 16 sin
que el estado cortical real cambie -- falso positivo/negativo clínico
sobre los umbrales firmados en Neuro Tanda 2. Mono-canal confirmado (sin
≥2 canales reales simultáneos ni referencia EOG en el repo -- RLS/ICA/
covarianza no tienen sustrato): el rechazo por gradiente de amplitud, tras
el bandpass y antes del Welch, es el único método honesto disponible.

Degradación tipo-PLV (espejo de `PLVResult` en `biomarkers.py`): si el
rechazo descarta suficientes ventanas como para que quede menos señal
limpia que `MIN_CLEAN_EEG_DURATION_S`, `analyze()` NO calcula band power
sobre lo que sobró -- devuelve `EegAnalysis(available=False, reason=...)`.
Como `beta_alpha_ratio`/`delta_alpha_ratio`/`theta_beta_ratio` ya declaran
`None` ante un band power inválido, y `_neurological_state()`
(`domain/physiology/state/builder.py`) ya no persiste lo que no está en
`signals`, la cadena hasta el gate no requiere tocar `builder.py` -- solo
que el llamador (el botón "Guardar estado al gemelo" del EEG Lab) respete
`available` antes de escribir al organismo.

NOTA DE HONESTIDAD (Art. I): el rechazo se calibró y se valida contra el
parpadeo MODELADO del generador demo (pulso Hann sintético, no un registro
EOG real). Su generalización a artefactos de parpadeo/movimiento REALES es
trabajo futuro, cuando exista captura de hardware real contra la que
calibrar -- no leer nada de esta tanda como "rechazo de artefactos
clínicamente validado".
"""

import numpy as np
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from scipy.signal import welch

from .preprocessing import preprocess_eeg

# Ratio Beta/Alfa (BAR) -- biomarcador de arousal cortical citado, NO una
# invención de esta app: BAR = P_beta / P_alpha del MISMO electrodo, así que
# el cociente cancela las variables anatómicas (grosor de cráneo, distancia
# fuente-sensor, ganancia) que hacen indefendible la potencia beta ABSOLUTA
# entre sujetos. Rangos de referencia: basal 0.8-1.2; arousal (Stroop /
# Trier Social Stress Test) BAR > 1.8. Fuente: Schutter DJLG 2006 /
# Handbook of Psychophysiology, 3a ed., cap. 10.
BAR_BASELINE_RANGE: Tuple[float, float] = (0.8, 1.2)
BAR_AROUSAL_THRESHOLD: float = 1.8
BAR_CITATION: str = "Schutter DJLG 2006 / Handbook of Psychophysiology 3a ed. cap.10 (Beta/Alpha Ratio, arousal cortical)"

# alpha_power por debajo de esto se trata como "sin ritmo alfa medible" -->
# el cociente es indefinido, NO infinito. Un ratio indefinido se declara
# indefinido (None), nunca se fuerza a un número.
_BAR_ALPHA_FLOOR: float = 1e-9

# DAR (Ratio Delta/Alfa) -- Neuro Tanda 2 (2026-09-10): FIRMA DEL EXPERTO
# APLICADA, `PENDING_VALIDATION` retirado. Cociente de dos band power del
# mismo electrodo, mismo criterio que el BAR (cancela variables anatómicas).
# Fuente: Claassen J et al. 2004, Clin Neurophysiol 115(12):2699-2710
# (monitorización EEG continua de UCI neurocrítica -- la razón INVERSA
# alfa/delta que cae sostenidamente predice isquemia cerebral diferida tras
# hemorragia subaracnoidea de mal grado; DAR es su inverso, sube cuando
# delta domina sobre alfa).
#
# Umbrales VALIDADOS_POR_FUENTE (firma del experto, 2026-09-10):
#   🟢 <1.5 tejido sano · 🟡 1.5-3.0 hipoperfusión leve ·
#   🔴 >=3.0 isquemia severa / sufrimiento cortical.
# Ver `classify_dar()` más abajo para la clasificación.
#
# BARANDILLA -- motor de cálculo: estos umbrales están definidos sobre
# POTENCIA ESPECTRAL ESTÁNDAR (PSD de Welch, `EegAnalyzer._band_power()`),
# el motor ACTUAL y el mismo que usa la literatura citada. Un cambio futuro
# de motor (p.ej. parametrización espectral FOOOF, o wavelets/CWT en vez de
# potencia de banda cruda) NO hereda esta validación automáticamente --
# reabriría la pregunta de si el umbral sigue aplicando sobre la nueva
# escala. Ese cambio de motor es un arco separado, registrado como futuro,
# no como deuda de esta tanda.
DAR_THRESHOLDS: Tuple[float, float] = (1.5, 3.0)  # (techo "leve", techo "severo": >= es severo)
DAR_CITATION: str = (
    "Claassen J et al. 2004, Clin Neurophysiol 115(12):2699-2710 (razón alfa/delta inversa, "
    "isquemia cerebral diferida post-HSA) -- VALIDADO_POR_FUENTE"
)
_DAR_ALPHA_FLOOR: float = 1e-9

# TBR (Ratio Theta/Beta) -- mismo cociente adimensional, banda frontal.
# FIRMA DEL EXPERTO APLICADA (2026-09-10): fuente Boksem MA, Meijman TF,
# Lorist MM. 2005 ("Effects of mental fatigue on attention") -- mide
# EXACTAMENTE el constructo que BIOCORE usa este ratio para (fatiga
# cognitiva en adultos durante una tarea sostenida).
#
# NOTA HONESTA (reemplaza la cita de la Tanda 1): la Tanda 1 citó Monastra
# VJ, Lubar JF, Linden M. 2001 (discriminante de TDAH pediátrico, cutoff
# que adoptó el sistema "NEBA" con autorización FDA) -- un estudio real,
# pero de una POBLACIÓN (niños con sospecha de TDAH) y un CONSTRUCTO
# (diagnóstico categórico) distintos del uso que le da BIOCORE, y además
# cuestionado por el meta-análisis posterior de Arns M, Conners CK, Kraemer
# HC. 2013 (J Atten Disord 17(5):374-383). El experto señaló que Boksem
# 2005 es la cita correcta para fatiga cognitiva -- no una corrección de
# fórmula, una corrección de qué estudio respalda qué afirmación.
#
# Umbrales VALIDADOS_POR_FUENTE (firma del experto, 2026-09-10):
#   🟢 <1.5 enganchado/aprendizaje activo · 🟡 1.5-3.0 inicio de fatiga ·
#   🔴 >=3.0 fatiga cognitiva severa.
# Ver `classify_tbr()` más abajo. Misma barandilla de motor Welch que el
# DAR (ver comentario arriba) -- un cambio de motor reabriría esta
# validación, arco futuro separado.
TBR_THRESHOLDS: Tuple[float, float] = (1.5, 3.0)
TBR_CITATION: str = (
    "Boksem MA, Meijman TF, Lorist MM. 2005 (Effects of mental fatigue on attention) -- "
    "VALIDADO_POR_FUENTE"
)
_TBR_BETA_FLOOR: float = 1e-9

# --- Arco 2A (2026-09-11): rechazo de artefactos por gradiente ------------
#
# Config nombrada, no constantes mágicas -- mismo espíritu que
# `MAX_HR_CARRY_AGE_S` (arco de acoplamiento) o `MIN_PLV_DURATION_S`
# (`biomarkers.py`): valores de ingeniería razonables, anotados para que un
# experto los ajuste contra ruido de hardware real, NO umbrales clínicos
# citados como DAR_THRESHOLDS/TBR_THRESHOLDS.
#
# `ARTIFACT_WINDOW_S` -- duración de cada ventana de análisis. El rechazo
# es de GRANO GRUESO: si una ventana de 1s contiene el pulso de ~50ms del
# parpadeo, se descarta la ventana completa (1s), no solo los 50ms
# contaminados -- simplicidad sobre precisión quirúrgica, mismo criterio
# que aceptó el diagnóstico.
ARTIFACT_WINDOW_S: float = 1.0

# `ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S` -- calibrado EMPÍRICAMENTE contra
# el generador demo (2026-09-11): sobre señal ya filtrada (0.5-40 Hz), el
# gradiente máximo (|Δx|·fs) de una ventana de 1s SIN parpadeo, para los 4
# patrones base del generador (alpha/beta/theta/delta, amplitud 40), no
# superó ~4300 unidades/s; toda ventana CON parpadeo superó ~6700. 5500 cae
# a medio camino, con margen hacia ambos lados. Es un default de
# ingeniería sobre señal SINTÉTICA -- pendiente de recalibrar contra el
# piso de ruido de hardware real cuando exista (ver nota de honestidad del
# módulo).
ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S: float = 5500.0

# `MIN_CLEAN_EEG_DURATION_S` -- mínimo de señal limpia (tras rechazo) para
# seguir calculando band power. Espejo directo de `MIN_PLV_DURATION_S`
# (ambos son "necesito al menos esto de señal utilizable, o declaro
# indisponible"), aunque la magnitud es mucho menor porque aquí no hay un
# requisito de fase citado -- solo que el promedio de Welch tenga más de 1
# ventana para no ser un solo periodograma disfrazado de PSD.
MIN_CLEAN_EEG_DURATION_S: float = 2.0


def beta_alpha_ratio(beta_power: float, alpha_power: float) -> Optional[float]:
    """BAR = beta_power / alpha_power. Adimensional -- su valor NO depende
    de la escala absoluta de la señal (por eso el experto lo eligió sobre
    `beta_power` crudo). Devuelve `None` si `alpha_power` es ~0 (cociente
    indefinido) -- honestidad de borde: no se inventa un infinito ni un
    tope arbitrario. Fuente: ver `BAR_CITATION`."""
    if alpha_power is None or beta_power is None:
        return None
    if not np.isfinite(alpha_power) or not np.isfinite(beta_power):
        return None
    if abs(alpha_power) < _BAR_ALPHA_FLOOR:
        return None
    return float(beta_power) / float(alpha_power)


def delta_alpha_ratio(delta_power: float, alpha_power: float) -> Optional[float]:
    """DAR = delta_power / alpha_power. Mismo criterio de honestidad de
    borde que `beta_alpha_ratio`: `None` si `alpha_power` es ~0 (indefinido,
    NO un infinito ni un tope arbitrario). Fuente: ver `DAR_CITATION`. El
    umbral clínico (`DAR_THRESHOLDS`) está VALIDADO_POR_FUENTE -- esta
    función solo calcula el ratio; usa `classify_dar()` para clasificarlo."""
    if delta_power is None or alpha_power is None:
        return None
    if not np.isfinite(delta_power) or not np.isfinite(alpha_power):
        return None
    if abs(alpha_power) < _DAR_ALPHA_FLOOR:
        return None
    return float(delta_power) / float(alpha_power)


def theta_beta_ratio(theta_power: float, beta_power: float) -> Optional[float]:
    """TBR = theta_power / beta_power. Mismo criterio de honestidad de
    borde: `None` si `beta_power` es ~0 (indefinido). Fuente: ver
    `TBR_CITATION`. El umbral clínico (`TBR_THRESHOLDS`) está
    VALIDADO_POR_FUENTE -- esta función solo calcula el ratio; usa
    `classify_tbr()` para clasificarlo."""
    if theta_power is None or beta_power is None:
        return None
    if not np.isfinite(theta_power) or not np.isfinite(beta_power):
        return None
    if abs(beta_power) < _TBR_BETA_FLOOR:
        return None
    return float(theta_power) / float(beta_power)


def classify_dar(dar: Optional[float]) -> Tuple[str, str, str]:
    """Clasifica un valor DAR según los umbrales VALIDADOS_POR_FUENTE (ver
    `DAR_THRESHOLDS`/`DAR_CITATION`). Devuelve `(nivel, etiqueta, badge)`.

    `None` (cociente indefinido -- denominador ~0, ya gateado antes de
    llegar aquí) -> `("no_disponible", "no disponible", "")` -- NUNCA un
    verde por default cuando falta el dato."""
    if dar is None:
        return ("no_disponible", "no disponible", "")
    leve, severo = DAR_THRESHOLDS
    if dar < leve:
        return ("normal", "tejido sano", "🟢")
    if dar < severo:
        return ("leve", "hipoperfusión leve", "🟡")
    return ("severo", "isquemia severa / sufrimiento cortical", "🔴")


def classify_tbr(tbr: Optional[float]) -> Tuple[str, str, str]:
    """Espejo de `classify_dar()` para TBR (ver `TBR_THRESHOLDS`/
    `TBR_CITATION`). `None` -> `("no_disponible", "no disponible", "")`."""
    if tbr is None:
        return ("no_disponible", "no disponible", "")
    leve, severo = TBR_THRESHOLDS
    if tbr < leve:
        return ("normal", "enganchado / aprendizaje activo", "🟢")
    if tbr < severo:
        return ("leve", "inicio de fatiga", "🟡")
    return ("severo", "fatiga cognitiva severa", "🔴")


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if y.size < 2 or x.size < 2:
        return 0.0
    return float(np.sum((x[1:] - x[:-1]) * 0.5 * (y[1:] + y[:-1])))


@dataclass
class EegAnalysis:
    # `None` únicamente cuando `available=False` (degradación tipo-PLV,
    # Arco 2A) -- ver `EegAnalyzer._welch_with_artifact_rejection()`.
    dominant_band: Optional[str]
    band_power: Dict[str, float]
    classification: Optional[str]
    summary: Optional[str]
    findings: Dict[str, Any]
    # BAR (Ratio Beta/Alfa) -- biomarcador de arousal cortical (ver
    # `beta_alpha_ratio` y `BAR_CITATION`). `None` si no hay ritmo alfa
    # medible (alpha_power ~0) -- indefinido, no forzado a un número.
    bar: Optional[float] = None
    # DAR (Ratio Delta/Alfa) -- enlentecimiento cortical (ver
    # `delta_alpha_ratio` y `DAR_CITATION`). `None` si alpha_power ~0.
    # Umbral clínico VALIDADO_POR_FUENTE -- ver `DAR_THRESHOLDS`/`classify_dar()`.
    dar: Optional[float] = None
    # TBR (Ratio Theta/Beta) -- carga/fatiga atencional (ver
    # `theta_beta_ratio` y `TBR_CITATION`). `None` si beta_power ~0.
    # Umbral clínico VALIDADO_POR_FUENTE -- ver `TBR_THRESHOLDS`/`classify_tbr()`.
    tbr: Optional[float] = None
    # Arco 2A -- degradación tipo-PLV (espejo de `PLVResult.available` en
    # `biomarkers.py`). `False` cuando el rechazo de artefactos dejó menos
    # de `MIN_CLEAN_EEG_DURATION_S` de señal limpia -- en ese caso
    # `band_power={}` (todo ausente, ningún `0.0` fabricado) y
    # `bar`/`dar`/`tbr` son `None` (los mismos que ya devuelven `None` ante
    # un band power inválido -- ninguna rama especial nueva en esas
    # funciones). Un llamador honesto (el botón "Guardar estado al gemelo"
    # del EEG Lab) debe comprobar `available` ANTES de escribir al
    # organismo -- si no escribe `alpha_power`/`beta_power`, el gate de
    # `_neurological_state()` (sin tocar) ya deja el dominio neuro vacío.
    available: bool = True
    # Motivo de no-disponibilidad, solo si `available=False` -- información
    # pedagógica ("cuánta señal limpia quedó vs. cuánta se necesitaba"),
    # nunca un error crudo.
    reason: Optional[str] = None
    # Fracción de ventanas de `ARTIFACT_WINDOW_S` que pasaron el rechazo
    # (0.0-1.0) -- diagnóstico de calidad de señal, disponible incluso
    # cuando `available=True` (útil para ver "casi se degrada").
    clean_fraction: Optional[float] = None


class EegAnalyzer:
    """Analyze EEG for band power, dominant rhythm, and clinical interpretation."""

    def __init__(self, fs: float = 256.0):
        self.fs = fs

    def analyze(self, signal: np.ndarray) -> EegAnalysis:
        if signal.ndim != 1:
            signal = signal.flatten()

        # Arco 2A: bandpass activado antes de cualquier otra cosa --
        # `preprocess_eeg()` ya no es un fantasma sin llamadores.
        filtered, _ = preprocess_eeg(signal, self.fs)

        freqs, psd, clean_fraction = self._welch_with_artifact_rejection(filtered)
        if freqs is None:
            total_s = len(filtered) / self.fs
            clean_s = clean_fraction * total_s
            reason = (
                f"señal EEG insuficiente tras rechazo de artefactos: {clean_s:.1f}s limpios de "
                f"{total_s:.1f}s totales (mínimo {MIN_CLEAN_EEG_DURATION_S:.0f}s) -- no se calcula "
                "band power sobre el fragmento que sobró"
            )
            return EegAnalysis(
                dominant_band=None,
                band_power={},
                classification=None,
                summary=None,
                findings={"Estado": f"no disponible: {reason}"},
                bar=None, dar=None, tbr=None,
                available=False, reason=reason, clean_fraction=clean_fraction,
            )

        band_power = {
            'delta': self._band_power(freqs, psd, 0.5, 3.5),
            'theta': self._band_power(freqs, psd, 4.0, 7.5),
            'alpha': self._band_power(freqs, psd, 8.0, 12.0),
            'beta': self._band_power(freqs, psd, 13.0, 30.0),
            'gamma': self._band_power(freqs, psd, 30.0, 45.0),
        }
        dominant_band = max(band_power, key=band_power.get)
        # DAR/TBR reusan los mismos band power ya calculados arriba para el
        # BAR -- no se recalcula el PSD, solo se toman otros dos cocientes
        # de los mismos 4 valores (delta/theta/alpha/beta).
        bar = beta_alpha_ratio(band_power['beta'], band_power['alpha'])
        dar = delta_alpha_ratio(band_power['delta'], band_power['alpha'])
        tbr = theta_beta_ratio(band_power['theta'], band_power['beta'])
        classification = self._classify_pattern(dominant_band, band_power)
        clinical_note = self._interpretation_text(dominant_band)
        summary = self._build_summary(dominant_band, band_power, classification, clinical_note)
        findings = self._build_findings(dominant_band, classification, clinical_note, band_power)
        findings['Beta/Alpha Ratio (BAR)'] = f"{bar:.2f}" if bar is not None else "indefinido (sin ritmo alfa)"
        _, dar_label, dar_badge = classify_dar(dar)
        _, tbr_label, tbr_badge = classify_tbr(tbr)
        findings['Delta/Alpha Ratio (DAR)'] = (
            f"{dar_badge} {dar:.2f} ({dar_label})" if dar is not None else "indefinido (sin ritmo alfa)"
        )
        findings['Theta/Beta Ratio (TBR)'] = (
            f"{tbr_badge} {tbr:.2f} ({tbr_label})" if tbr is not None else "indefinido (sin ritmo beta)"
        )

        return EegAnalysis(
            dominant_band=dominant_band,
            band_power=band_power,
            classification=classification,
            summary=summary,
            findings=findings,
            bar=bar,
            dar=dar,
            tbr=tbr,
            available=True,
            reason=None,
            clean_fraction=clean_fraction,
        )

    def _welch_with_artifact_rejection(
        self, filtered: np.ndarray
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], float]:
        """Arco 2A: rechazo de artefactos por gradiente, mono-canal, TRAS el
        bandpass y ANTES del PSD. Segmenta la señal filtrada en ventanas de
        `ARTIFACT_WINDOW_S`; descarta las que excedan
        `ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S` (gradiente de amplitud -- un
        parpadeo de ~50ms es una deflexión mucho más rápida que cualquier
        oscilación cortical de amplitud comparable); promedia el
        periodograma de Welch SOLO sobre las ventanas que pasaron --
        literalmente el mismo paso de promediado que ya hace
        `scipy.signal.welch()` internamente, con las ventanas contaminadas
        EXCLUIDAS del promedio en vez de zero-padded (que introduciría un
        escalón espectral propio, un artefacto nuevo para tapar el viejo).

        Devuelve `(freqs, psd_promediado, clean_fraction)`. `freqs=None` si
        la señal limpia resultante es menor que `MIN_CLEAN_EEG_DURATION_S`
        -- degradación tipo-PLV, nunca un PSD sobre fragmento insuficiente."""
        n_total = filtered.shape[0]
        if n_total == 0:
            return None, None, 0.0

        window_samples = max(1, int(round(ARTIFACT_WINDOW_S * self.fs)))
        if n_total < window_samples:
            # Señal más corta que una ventana -- se trata como una sola
            # ventana (mismo espíritu que el `nperseg = min(512, N)`
            # anterior a esta tanda para señales cortas de test).
            window_samples = n_total
        n_windows = n_total // window_samples

        clean_psds = []
        freqs = None
        for i in range(n_windows):
            segment = filtered[i * window_samples:(i + 1) * window_samples]
            gradient = float(np.max(np.abs(np.diff(segment))) * self.fs) if segment.shape[0] > 1 else 0.0
            if gradient > ARTIFACT_GRADIENT_THRESHOLD_UV_PER_S:
                continue
            f, psd = welch(segment, fs=self.fs, nperseg=segment.shape[0])
            freqs = f
            clean_psds.append(psd)

        clean_fraction = len(clean_psds) / n_windows if n_windows > 0 else 0.0
        clean_duration_s = len(clean_psds) * (window_samples / self.fs)
        if not clean_psds or clean_duration_s < MIN_CLEAN_EEG_DURATION_S:
            return None, None, clean_fraction

        return freqs, np.mean(clean_psds, axis=0), clean_fraction

    def _band_power(self, freqs: np.ndarray, psd: np.ndarray, low: float, high: float) -> float:
        mask = (freqs >= low) & (freqs <= high)
        return float(_trapz(psd[mask], freqs[mask])) if np.any(mask) else 0.0

    def _classify_pattern(self, dominant_band: str, band_power: Dict[str, float]) -> str:
        if dominant_band == 'alpha':
            return 'Despierto relajado'
        if dominant_band == 'beta':
            return 'Alerta / Enfocado'
        if dominant_band == 'theta':
            return 'Sueño ligero / Somnolencia'
        if dominant_band == 'delta':
            return 'Sueño profundo / Ritmo lento'
        if dominant_band == 'gamma':
            return 'Actividad cortical alta / Activación cognitiva'
        return 'Patrón no determinado'

    def _interpretation_text(self, dominant_band: str) -> str:
        mapping = {
            'alpha': 'Puede corresponder a relajación con ojos cerrados o estado de dominancia de la corteza occipital.',
            'beta': 'Sugiere atención, estrés mental o estado de alerta aumentada.',
            'theta': 'Suele aparecer en somnolencia, sueño ligero y estados de transición.',
            'delta': 'Indica actividad de sueño profundo o un ritmo cortical muy lento.',
            'gamma': 'Asociado con procesamiento cognitivo y actividad cortical sincronizada de alta frecuencia.',
        }
        return mapping.get(dominant_band, 'Patrón EEG no específico.')

    def _build_findings(
        self,
        dominant_band: str,
        classification: str,
        clinical_note: str,
        band_power: Dict[str, float]
    ) -> Dict[str, Any]:
        findings = {
            'Dominant Band': dominant_band.upper(),
            'Classification': classification,
            'Clinical Note': clinical_note,
            'Delta Power': f"{band_power['delta']:.3f}",
            'Theta Power': f"{band_power['theta']:.3f}",
            'Alpha Power': f"{band_power['alpha']:.3f}",
            'Beta Power': f"{band_power['beta']:.3f}",
            'Gamma Power': f"{band_power['gamma']:.3f}",
        }
        if dominant_band == 'delta':
            findings['Alert'] = 'Verificar estado de sueño profundo y descartar encefalopatía de onda lenta si procede.'
        elif dominant_band == 'theta':
            findings['Alert'] = 'Monitorizar somnolencia y potenciales patrones de transición de sueño.'
        elif dominant_band == 'beta':
            findings['Alert'] = 'Consultar estrés mental o estado de activación cortical elevada.'
        return findings

    def _build_summary(
        self,
        dominant_band: str,
        band_power: Dict[str, float],
        classification: str,
        clinical_note: str
    ) -> str:
        return (
            f"Dominante: {dominant_band.upper()} | Clasificación: {classification}. "
            f"Interpretación: {clinical_note} "
            f"Power: Δ={band_power['delta']:.2f}, θ={band_power['theta']:.2f}, "
            f"α={band_power['alpha']:.2f}, β={band_power['beta']:.2f}, γ={band_power['gamma']:.2f}."
        )
