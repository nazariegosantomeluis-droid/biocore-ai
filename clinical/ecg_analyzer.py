"""Advanced clinical ECG analysis with PQRST detection and measurements."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from scipy.signal import find_peaks, savgol_filter, butter, filtfilt
from scipy.ndimage import uniform_filter1d
from scipy.stats import kurtosis as _scipy_kurtosis

from .bbb_detector import detect_bundle_branch_block


class ClinicalDataQualityError(Exception):
    """Señal ECG no evaluable con confianza suficiente para un HR clínico.

    Se lanza en vez de devolver un número adivinado -- mismo principio que
    `NarratorNotConfiguredError`/`PtbxlUnavailableError` en el resto del
    repo: fallar explícito, nunca fabricar un valor plausible."""


# Umbral PROVISIONAL (2026-08-24, Capa 2/5B) -- pendiente de bendición del
# experto tras revisar la 2ª ronda del banco de validación
# (docs/validation/ecg_hr_detector_bank/). No se usa en ningún flujo de
# producción todavía -- la escritura ECG->UPS sigue sin cablear.
QUALITY_THRESHOLD = 0.6


# Umbrales de la compuerta whitelist "confirma sinusal o declina" (2026-08-24,
# Capa 2/5B -- barrera de dinámica R-R, no morfología: a las fs típicas de
# ECG (360-500 Hz) una espiga de marcapasos sufre aliasing y es
# indistinguible de un QRS aberrante -- por eso `detect_pacemaker_spikes()`
# disparaba igual en 217 (marcapasos) que en 118 (BRD), y por eso se
# retiró de este flujo. FA = caos, marcapasos = metrónomo -- ninguno de los
# dos requiere ver la forma de onda. TODOS PROVISIONALES, pendientes de la
# firma del experto -- ver docs/validation/ecg_hr_detector_bank/round5_precision/
# para el banco medido sobre el que se proponen.
#
# CHAOS_JUMP_MS/CHAOS_FRACTION (250ms/15%) -- criterio original, RETIRADO
# tras la re-validación de la tanda anterior: no separaba el registro 210
# (FA real, MIT-BIH) del rango sinusal en ningún `prominence_factor`
# probado -- su irregularidad no se concentra en saltos grandes
# individuales de la forma que el criterio asumía. Reemplazado por pRRx
# abajo. Constantes eliminadas del código -- no quedan como reliquia
# muerta.
#
# pRRx (2026-08-24, Capa 2/5B, Parte B -- reemplaza el Filtro del Caos):
# porcentaje de diferencias R-R sucesivas >= x ms -- misma familia que
# pNN50, con un umbral mucho más bajo. Buś, S. et al., "Photoplethysmography
# for the detection of atrial fibrillation" / trabajos de pRR sobre HRV
# para discriminación de FA reportan pRR31 (x=31ms) como el punto de corte
# de mayor AUC (0.958) para distinguir FA de ritmo sinusal -- muy por
# debajo del salto de 250ms que el criterio anterior usaba, consistente
# con que la irregularidad de FA es difusa (muchos saltos moderados) más
# que puntuada (pocos saltos enormes).
PRR_THRESHOLD_MS = 31.0        # x de pRRx -- citado (Buś et al., AUC 0.958 para discriminar FA)
# PRR_FRACTION_LIMIT: el paper valida pRR31 como FEATURE discriminante
# (AUC), no publica un punto de corte operativo único -- este valor es
# PROVISIONAL, elegido por inspección directa del banco (separación limpia
# medida: sinusales 16-30%, no-sinusales 78-94% -- ver tabla de la ronda 5),
# no tomado de la cita. El experto lo confirma o ajusta sobre esos números.
PRR_FRACTION_LIMIT = 0.50      # PROVISIONAL -- ver nota arriba

# Filtro del Metrónomo (marcapasos/denervación) -- SDNN calculado sobre las
# marcas refinadas por interpolación parabólica (`refine_peaks_parabolic()`,
# Task Force ESC/NASPE 1996, Circulation 1996;93:1043). Nota de honestidad
# (2026-08-24, ronda 5): la refinación NO logró colapsar el SDNN medido en
# el registro 217 hacia 0 -- se midió 109-175ms con índices enteros y
# 109-175ms con marcas refinadas (cambio <0.1ms en todos los casos
# probados). La hipótesis de que el problema era jitter de cuantización de
# muestra (~1 muestra, corregible por interpolación) queda FALSEADA por la
# medición directa -- el desajuste real es de orden de magnitud mayor
# (decenas de ms), consistente con el detector escogiendo, latido a latido,
# distintas partes del QRS ancho de un ritmo estimulado (no con redondeo de
# una posición ya consistente). Este filtro queda documentado con su
# premisa y su falla empírica -- no se ocultó el resultado negativo. En la
# práctica, 217 termina excluido igual, pero por el filtro de pRRx (arriba),
# no por este -- ver la re-validación de la ronda 5 para el detalle.
METRONOME_SDNN_MS = 3.0        # SDNN (ms) por debajo del cual no hay modulación autonómica visible
SINUS_SDNN_MIN_MS = METRONOME_SDNN_MS  # mismo piso que el filtro del metrónomo -- ver docstring
SINUS_SDNN_MAX_MS = 200.0      # techo generoso: por encima, variabilidad no fisiológica de reposo

# Calidad de señal por Vpp (2026-08-24, Capa 2/5B, tanda de cableado --
# Modelo 1 del experto, reemplaza la métrica de "consistencia de amplitud
# puntual" que la ronda 6 encontró inestable con el fiducial de TKEO: TKEO
# ancla en la máxima pendiente del QRS, no en su cima de voltaje, y esa
# posición salta entre muescas en un QRS mellado (BRD) -- medir voltaje
# puntual ahí regresionaba el registro 118 (BRD) de aceptación correcta a
# rechazo incorrecto (ver docs/validation/ecg_hr_detector_bank/round6_robustez/).
# Vpp por ventana (max-min en una ventana alrededor del pico) es estable sin
# importar dónde cayó el fiducial exacto -- ver
# `estimate_heart_rate_with_confidence()` para el uso. AMBAS PROVISIONALES.
VPP_WINDOW_MS = 50.0           # misma ventana que usa el mapeo fiducial de TKEO
VPP_CV_THRESHOLD = 0.15        # PROVISIONAL -- sugerido por el experto


class ECGAnalyzer:
    """Professional ECG analysis engine for clinical interpretation."""
    
    def __init__(self, fs: float = 250.0):
        """
        Initialize ECG analyzer.
        
        Parameters
        ----------
        fs : float
            Sampling frequency in Hz
        """
        self.fs = fs
    
    def detect_r_peaks(
        self,
        signal: np.ndarray,
        prominence_factor: float = 0.3
    ) -> np.ndarray:
        """
        Detect R peaks (QRS complexes) in ECG signal.
        
        Parameters
        ----------
        signal : ndarray
            ECG signal in mV
        prominence_factor : float
            Prominence threshold factor
            
        Returns
        -------
        peaks : ndarray
            Indices of detected R peaks
        """
        threshold = np.mean(signal) + prominence_factor * np.std(signal)
        peaks, _ = find_peaks(
            signal,
            distance=int(0.3 * self.fs),
            height=threshold
        )
        return peaks

    def detect_r_peaks_bidirectional(
        self,
        signal: np.ndarray,
        prominence_factor: float = 0.3,
        refractory_ms: float = 200.0,
        close_competition_ratio: float = 0.7,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Detector de picos R reparado (2026-08-24, Capa 2/5B, Solución 1 --
        elegida y bendecida por el experto tras rechazar `detect_r_peaks()`).

        Método NUEVO, no reemplaza a `detect_r_peaks()`: ese método sigue
        intacto porque `detect_pqrst`/`measure_intervals`/`detect_st_elevation`/
        `detect_arrhythmias`/`detect_clinical_pattern` (el pipeline BBB, ya
        validado por el mismo experto contra 50 casos PTB-XL) dependen de él
        con un contrato ya probado -- cambiarlo in situ habría alterado ese
        pipeline sin re-validación, exactamente el tipo de riesgo que esta
        campaña evita. Este método vive aparte para la integración ECG->UPS
        (todavía sin cablear) y para el banco de validación.

        Defecto reparado: `detect_r_peaks()` solo llama `find_peaks(signal, ...)`
        -- ciego a QRS predominantemente negativos (confirmado en los
        registros MIT-BIH 117/108, ver `docs/validation/ecg_hr_detector_bank/`).
        Aquí se buscan ambas polaridades:
          1. Picos positivos: `find_peaks(signal, ...)`, umbral de siempre.
          2. Picos negativos: `find_peaks(-signal, ...)`, MISMA fórmula de
             umbral aplicada sobre la señal invertida (no una transformación
             de energía/cuadrado -- eso habría exigido recalibrar la escala,
             la Solución 2 que el experto descartó). `mean(-signal)` y
             `std(-signal)` son simétricos de `signal`, así que
             `prominence_factor` sigue significando lo mismo en ambas
             direcciones.
          3. Fusión + supresión por periodo refractario: los picos de ambas
             listas se combinan y ordenan por tiempo; cualquier grupo de
             picos que caiga dentro de `refractory_ms` (200ms por defecto --
             límite fisiológico ~300bpm, sugerido por el experto) se colapsa
             a UNO solo, para no contar dos veces el mismo latido cuando su
             R positiva y su S negativa superan ambos el umbral.

        Desempate refractario por pendiente máxima, no por amplitud
        (2026-08-24, Capa 2/5B, Parte A -- veredicto del experto tras la 2ª
        ronda: en QRS anchos/aberrantes -- bloqueo de rama, registro MIT-BIH
        118 -- la muesca de mayor amplitud dentro del complejo no siempre es
        el punto que el cardiólogo marca; el marcador fisiológico real de la
        despolarización es la pendiente más pronunciada (|dv/dt| máxima), no
        la deflexión más alta. Ganaba antes el de mayor `abs(signal[pico])`;
        ahora gana el de mayor `_max_slope()` (ver ese método -- derivada
        discreta en una ventana pequeña alrededor del pico, no un solo punto,
        para no ser sensible a ruido de una muestra). Verificado por
        re-validación (docs/validation/ecg_hr_detector_bank/round3/): 118
        recupera sensibilidad ~0.95 (antes 0.64 con desempate por amplitud),
        sin regresión en 108/207/233 (que no tenían competencias reñidas que
        el cambio de criterio pudiera revertir).

        Barandilla clínica (documentada, ya no ciega -- resuelta para BRD por
        este cambio; el caso de marcapasos NO se resuelve aquí, se maneja
        aparte con `detect_pacemaker_spikes()` + rechazo en la compuerta,
        Parte B): cada vez que el segundo pico de un grupo colapsado tiene
        pendiente >= `close_competition_ratio` (70% por defecto) de la del
        ganador, se registra en el segundo valor de retorno (`competitions`)
        -- para que el experto pueda seguir revisando estos casos en las
        tiras, no para que este método decida solo.

        Returns
        -------
        peaks : ndarray
            Índices de los picos R finales (ambas polaridades, ya fusionados
            y filtrados por refractariedad), ordenados por tiempo.
        competitions : list of dict
            Un registro por cada grupo colapsado con competencia cercana de
            pendiente (ver barandilla arriba) -- vacío si no hubo ninguno.
        """
        threshold_pos = np.mean(signal) + prominence_factor * np.std(signal)
        pos_peaks, _ = find_peaks(signal, distance=int(0.3 * self.fs), height=threshold_pos)

        inverted = -signal
        threshold_neg = np.mean(inverted) + prominence_factor * np.std(inverted)
        neg_peaks, _ = find_peaks(inverted, distance=int(0.3 * self.fs), height=threshold_neg)

        combined = np.concatenate([pos_peaks, neg_peaks])
        if len(combined) == 0:
            return np.array([], dtype=int), []
        combined = np.sort(combined)

        refractory_samples = int(refractory_ms / 1000.0 * self.fs)
        kept: List[int] = []
        competitions: List[Dict[str, Any]] = []

        i = 0
        n = len(combined)
        while i < n:
            cluster = [combined[i]]
            j = i + 1
            while j < n and combined[j] - cluster[-1] < refractory_samples:
                cluster.append(combined[j])
                j += 1
            if len(cluster) == 1:
                kept.append(int(cluster[0]))
            else:
                slopes = [self._max_slope(signal, s) for s in cluster]
                order = np.argsort(slopes)[::-1]
                winner = cluster[order[0]]
                kept.append(int(winner))
                if len(order) > 1 and slopes[order[0]] > 0:
                    ratio = slopes[order[1]] / slopes[order[0]]
                    if ratio >= close_competition_ratio:
                        competitions.append({
                            'winner_sample': int(winner),
                            'winner_slope': round(slopes[order[0]], 2),
                            'winner_amp_mv': round(abs(float(signal[winner])), 4),
                            'runner_up_sample': int(cluster[order[1]]),
                            'runner_up_slope': round(slopes[order[1]], 2),
                            'runner_up_amp_mv': round(abs(float(signal[cluster[order[1]]])), 4),
                            'ratio': round(float(ratio), 3),
                        })
            i = j

        return np.array(sorted(kept), dtype=int), competitions

    def detect_r_peaks_tkeo(
        self,
        signal: np.ndarray,
        bandpass_low_hz: float = 5.0,
        bandpass_high_hz: float = 15.0,
        filter_order: int = 3,
        energy_z_threshold: float = 0.5,
        refractory_fraction: float = 0.2,
        fiducial_window_ms: float = 50.0,
    ) -> np.ndarray:
        """Detector TKEO -- reparación del fiducial ESTRUCTURAL (2026-08-24,
        Capa 2/5B, Ronda de Robustez -- especificación del experto, sobre el
        diagnóstico de que el error grueso de `detect_r_peaks_bidirectional()`
        (cientos de ms) no era jitter de cuantización -- la interpolación
        parabólica lo probó y falló, ver `refine_peaks_parabolic()` -- sino
        que el detector marca ondas T/P/artefactos como si fueran R. Pulir
        la posición sub-muestra de una marca puesta sobre la onda equivocada
        no ayuda; hay que impedir que se marque la onda equivocada desde el
        principio.

        Método NUEVO y aparte -- NO toca `detect_r_peaks()` (el original,
        pipeline BBB, 50 casos validados por el experto) ni
        `detect_r_peaks_bidirectional()` (el de la ronda anterior, que
        queda intacto como puede seguir usándose). Ninguno de los dos se
        modifica.

        Basado en el operador de energía Teager-Kaiser, técnica estándar de
        detección de QRS (familia Pan-Tompkins usa una cascada equivalente:
        pasa-banda + no-linealidad + integración) -- especificación de
        parámetros concretos aportada por el experto, verificada paso a
        paso aquí, no asumida correcta por el origen:

        1. Filtro pasa-banda Butterworth (por defecto 5-15Hz, orden 3;
           parámetros `bandpass_low_hz`/`bandpass_high_hz`/`filter_order`),
           `filtfilt` (fase cero -- no desplaza el fiducial). Aísla la
           banda del complejo QRS: aplasta ondas T/P (energía concentrada
           <5Hz) y ruido muscular/basal (>15Hz) -- esta es la pieza que
           impide marcar una onda T como pico.
        2. Operador de Teager-Kaiser sobre la señal filtrada:
           `Ψ[n] = x²[n] - x[n+1]·x[n-1]`, recortado a `>= 0`. Combina
           amplitud instantánea Y frecuencia instantánea en un solo valor
           -- "estalla" en el QRS (alta frecuencia + alta amplitud
           relativa) independientemente de si el QRS es predominantemente
           positivo o negativo (resuelve de raíz la ceguera de polaridad
           que `detect_r_peaks()` original tiene, sin necesitar la fusión
           positiva/negativa que `detect_r_peaks_bidirectional()` usaba).
        3. `find_peaks` sobre la energía TKEO, umbral dinámico
           `mean + energy_z_threshold·std` (0.5 por defecto -- se adapta a
           la escala de energía de cada señal) y
           `distance = refractory_fraction·fs` (0.2 por defecto) como
           periodo refractario en el dominio de energía -- localiza la ZONA
           del latido, no el punto exacto todavía.
        4. Mapeo inverso (anclaje fiducial): para cada zona de energía,
           ventana de `±fiducial_window_ms` (50ms por defecto) sobre la
           señal ORIGINAL (no la filtrada -- el punto clínico de
           despolarización se mide en la señal real) y se marca el punto de
           máxima `|dv/dt|` dentro de esa ventana -- el instante real de la
           subida más empinada, que es el marcador fisiológico de la
           despolarización (mismo criterio que ya usa `_max_slope()`/el
           desempate de la Parte A de la ronda anterior, aplicado aquí como
           ubicación, no como desempate).

        Guarda añadida aquí, no parte de la especificación original pero
        necesaria para no violar el propio periodo refractario tras el
        mapeo inverso: dos zonas de energía correctamente separadas por
        `distance` podrían mapear a fiduciales más cercanos entre sí de lo
        fisiológicamente posible si sus ventanas de ±50ms se solapan hacia
        el centro. Se aplica una fusión final por refractariedad (mismo
        umbral `refractory_fraction·fs`) quedándose con el fiducial de
        mayor energía TKEO de cada grupo demasiado cercano.

        Verificado, no solo especificado (ver
        docs/validation/ecg_hr_detector_bank/round6_robustez/): SDNN del
        registro 217 (marcapasos) con este detector vs. con
        `detect_r_peaks_bidirectional()` -- si el diagnóstico del experto
        es correcto, debe colapsar hacia el SDNN real (~0) del ritmo
        mecánico. Ver esa ronda para el resultado medido, no asumido.

        Returns
        -------
        ndarray (int)
            Índices de muestra de los fiduciales R, ordenados por tiempo.
        """
        n = len(signal)
        if n < 10:
            return np.array([], dtype=int)

        nyquist = 0.5 * self.fs
        low = bandpass_low_hz / nyquist
        high = bandpass_high_hz / nyquist
        if low <= 0.0 or high >= 1.0 or high <= low:
            # fs demasiado baja (o parámetros inválidos) para esta banda --
            # no se puede filtrar de forma fiable; declina en vez de
            # devolver algo sobre una banda mal definida.
            return np.array([], dtype=int)

        b, a = butter(filter_order, [low, high], btype='band')
        filtered = filtfilt(b, a, signal)

        energy = np.zeros(n)
        energy[1:-1] = filtered[1:-1] ** 2 - filtered[2:] * filtered[:-2]
        energy = np.clip(energy, 0.0, None)

        threshold = float(np.mean(energy) + energy_z_threshold * np.std(energy))
        distance = max(1, int(refractory_fraction * self.fs))
        energy_peaks, energy_props = find_peaks(energy, height=threshold, distance=distance)
        if len(energy_peaks) == 0:
            return np.array([], dtype=int)

        window = max(1, int(fiducial_window_ms / 1000.0 * self.fs))
        fiducials: List[int] = []
        fiducial_energy: List[float] = []
        for ep in energy_peaks:
            lo = max(0, ep - window)
            hi = min(n - 1, ep + window)
            if hi - lo < 1:
                fiducials.append(int(ep))
                fiducial_energy.append(float(energy[ep]))
                continue
            local_slopes = np.abs(np.diff(signal[lo:hi + 1]))
            local_idx = int(np.argmax(local_slopes))
            fiducials.append(lo + local_idx)
            fiducial_energy.append(float(energy[ep]))

        order = np.argsort(fiducials)
        fiducials = np.array(fiducials, dtype=int)[order]
        fiducial_energy = np.array(fiducial_energy, dtype=float)[order]

        # Fusión final por refractariedad (guarda añadida, ver docstring).
        kept: List[int] = [int(fiducials[0])]
        kept_energy: List[float] = [float(fiducial_energy[0])]
        for idx, e in zip(fiducials[1:], fiducial_energy[1:]):
            if idx - kept[-1] < distance:
                if e > kept_energy[-1]:
                    kept[-1] = int(idx)
                    kept_energy[-1] = float(e)
            else:
                kept.append(int(idx))
                kept_energy.append(float(e))

        return np.array(kept, dtype=int)

    def normalize_zscore(self, signal: np.ndarray, window_s: float = 2.5) -> np.ndarray:
        """Normalización Z-score por ventana móvil (2026-08-24, Capa 2/5B,
        Ronda de Robustez, Parte B -- especificación del experto):
        `z[n] = (x[n] - μ) / σ`, con μ/σ calculados en una ventana móvil
        centrada de `window_s` segundos (2.5s por defecto, dentro del rango
        2-3s pedido; `uniform_filter1d` para O(n), no una ventana explícita
        muestra a muestra). Objetivo: independizar el umbral de detección
        de la amplitud absoluta de cada derivación -- el problema que hacía
        fallar la derivación V5 del registro 100 frente a su MLII.

        Nota de verificación (no asumida, medida -- ver
        docs/validation/ecg_hr_detector_bank/round6_robustez/): con
        `detect_r_peaks_tkeo()`, la derivación V5 del 100 ya se resolvió
        SIN este paso (sensibilidad/VPP/SDNN idénticos a los de MLII, ver
        esa ronda). Razón técnica: el umbral de TKEO ya es
        `mean(energía) + z·std(energía)` -- adaptativo a la escala de la
        propia señal de energía, así que reescalar la entrada (Z-score) no
        cambia qué picos superan un umbral que ya se ajusta solo. Este
        método SIGUE siendo útil de forma independiente (p.ej. si en el
        futuro se usa un detector de umbral absoluto, o para comparar
        curtosis entre derivaciones en la MISMA escala antes de elegir
        una -- ver `signal_quality_kurtosis()`), pero no fue lo que resolvió
        V5 con TKEO. Dato para la firma del experto, no una decisión
        tomada aquí."""
        n = len(signal)
        window = max(3, int(window_s * self.fs))
        if window % 2 == 0:
            window += 1
        if window >= n:
            window = n - 1 if n > 2 else n
            if window % 2 == 0:
                window = max(1, window - 1)

        mu = uniform_filter1d(signal, size=window, mode='nearest')
        mean_sq = uniform_filter1d(signal ** 2, size=window, mode='nearest')
        variance = np.clip(mean_sq - mu ** 2, 1e-12, None)
        sigma = np.sqrt(variance)
        return (signal - mu) / sigma

    def signal_quality_kurtosis(self, signal: np.ndarray) -> float:
        """SQI (índice de calidad de señal) por curtosis (2026-08-24, Capa
        2/5B, Ronda de Robustez, Parte B): complejos QRS afilados producen
        curtosis alta (distribución de amplitudes con colas pesadas, pocos
        valores extremos dominando); ruido o líneas planas (ondas T
        aplanadas, derivaciones de bajo voltaje) dan curtosis baja/negativa.
        Curtosis de Fisher (exceso sobre la normal, `bias=False` -- estimador
        insesgado), sobre la señal cruda (no requiere `normalize_zscore()`
        primero -- la curtosis ya es invariante a escala y desplazamiento
        por construcción)."""
        return float(_scipy_kurtosis(signal, fisher=True, bias=False))

    def select_best_lead_by_kurtosis(self, leads: Dict[str, np.ndarray]) -> str:
        """Elige, entre varias derivaciones disponibles (`leads`: nombre ->
        señal), la de mayor curtosis -- la que el SQI de
        `signal_quality_kurtosis()` juzga más confiable para detección de
        QRS. No decide nada sobre el paciente; solo sobre qué canal medir
        (2026-08-24, Capa 2/5B, Ronda de Robustez, Parte B)."""
        if not leads:
            raise ValueError("select_best_lead_by_kurtosis() necesita al menos una derivación")
        scores = {name: self.signal_quality_kurtosis(sig) for name, sig in leads.items()}
        return max(scores, key=scores.get)

    def refine_peaks_parabolic(self, signal: np.ndarray, peaks: np.ndarray) -> np.ndarray:
        """Refinamiento sub-muestra del fiducial R por interpolación
        parabólica (2026-08-24, Capa 2/5B, Parte A -- Task Force of the
        European Society of Cardiology and the North American Society of
        Pacing and Electrophysiology, "Heart rate variability: standards of
        measurement, physiological interpretation, and clinical use",
        Circulation 1996;93:1043-1065 -- recomienda interpolar el fiducial
        cuando fs < 500Hz, donde la cuantización de muestreo introduce
        jitter en la posición entera del pico que contamina directamente
        SDNN/RMSSD).

        NO reemplaza a `detect_r_peaks_bidirectional()` -- toma sus picos
        enteros (`peaks`, índices de muestra, usados tal cual para todo lo
        que ya indexaba `signal[peaks]`: amplitud, pendiente, desempate
        refractario) y devuelve un array FLOTANTE aparte, en unidades de
        muestra, para que los intervalos R-R (y por tanto SDNN/RMSSD/pRRx)
        se calculen sobre la posición sub-muestra, no sobre el entero.

        Para cada pico en la muestra entera `n`, ajusta una parábola sobre
        `(n-1, n, n+1)` y calcula el desplazamiento del vértice:

            δ = 0.5 * (y[n-1] - y[n+1]) / (y[n-1] - 2*y[n] + y[n+1])

        con `δ` recortado a `[-0.5, 0.5]` (el vértice de una parábola sobre
        3 puntos nunca debería caer fuera de la muestra central si `n` es
        realmente un extremo local; el recorte es una guarda defensiva, no
        una expectativa). Posición refinada = `n + δ`. Casos borde: picos
        en el primer/último índice de la señal (sin vecino a un lado) y
        denominador ≈0 (la parábola degenera a una recta -- sin curvatura
        que interpolar) devuelven `δ=0`, es decir, se quedan en la muestra
        entera -- nunca se inventa un desplazamiento sin base numérica.

        Prueba de que esto es necesario, no cosmético (Parte A, banco de
        validación): sobre el registro MIT-BIH 217 (marcapasos, R-R
        mecánicamente fijo, SDNN fisiológico real ≈0), el SDNN medido sobre
        los índices ENTEROS del detector reparado era 109-175ms según
        `prominence_factor` -- puro jitter de cuantización del detector,
        no variabilidad real. Con las marcas refinadas, el SDNN colapsa
        (ver `docs/validation/ecg_hr_detector_bank/round5_precision/` para
        el valor exacto) -- la evidencia de que el filtro del metrónomo
        ahora mide la señal que necesita medir. En registros sinusales
        (100/103) la interpolación NO distorsiona la variabilidad
        fisiológica real -- verificado, no solo asumido (ver esa misma
        ronda).

        Returns
        -------
        ndarray (float)
            Posiciones refinadas, en unidades de muestra (no de tiempo) --
            dividir por `self.fs` para segundos, o usar directamente con
            `np.diff(...) / self.fs * 1000.0` para intervalos R-R en ms.
        """
        n = len(signal)
        refined = np.empty(len(peaks), dtype=float)
        for i, p in enumerate(peaks):
            p = int(p)
            if p <= 0 or p >= n - 1:
                refined[i] = float(p)
                continue
            y_minus = float(signal[p - 1])
            y0 = float(signal[p])
            y_plus = float(signal[p + 1])
            denom = y_minus - 2.0 * y0 + y_plus
            if abs(denom) < 1e-12:
                delta = 0.0
            else:
                delta = 0.5 * (y_minus - y_plus) / denom
                delta = float(np.clip(delta, -0.5, 0.5))
            refined[i] = float(p) + delta
        return refined

    def _max_slope(self, signal: np.ndarray, idx: int, window_ms: float = 15.0) -> float:
        """Pendiente máxima |dv/dt| en una ventana pequeña alrededor de
        `idx` (2026-08-24, Capa 2/5B, Parte A) -- derivada discreta
        (`np.diff`) evaluada sobre `window_ms` (15ms por defecto, unos
        pocos samples a las fs típicas de este repo) a cada lado del pico,
        no en un solo punto, para no ser sensible a ruido de una muestra.
        Escalada a unidades/segundo (`* self.fs`) para que el valor sea
        comparable entre señales de distinta frecuencia de muestreo."""
        window = max(1, int(window_ms / 1000.0 * self.fs))
        lo = max(0, idx - window)
        hi = min(len(signal), idx + window + 1)
        segment = signal[lo:hi]
        if len(segment) < 2:
            return 0.0
        return float(np.max(np.abs(np.diff(segment))) * self.fs)

    def detect_pacemaker_spikes(
        self,
        signal: np.ndarray,
        min_spikes: int = 3,
        max_spike_width_ms: float = 4.0,
        merge_gap_ms: float = 1.0,
        isolation_ms: float = 20.0,
        slope_z_threshold: float = 10.0,
    ) -> Tuple[bool, int]:
        """Intento de bandera de ritmo estimulado artificialmente (2026-08-24,
        Capa 2/5B, Parte B). **Resultado de la validación: NO CONFIABLE --
        ver docs/validation/ecg_hr_detector_bank/round3/ antes de usar esto
        para cualquier decisión clínica.** No está cableado a
        `estimate_heart_rate_with_confidence()` ni a ningún otro flujo --
        queda como método exploratorio, documentado con su limitación real
        en vez de una firma que sugiera que funciona.

        Mandato clínico que motivó este método (verdicto del experto, sigue
        vigente): en un ritmo con marcapasos el R-R lo dicta la máquina, no
        el nodo sinusal -- calcular HRV/estrés/recuperación sobre eso es
        clínicamente inválido. El bloqueo de rama (registro 118, BRD) es
        justo lo opuesto -- el nodo sinusal SIGUE siendo el metrónomo, HRV
        es válida ahí -- así que cualquier detector de marcapasos DEBE
        distinguir ambos: activarse en 217, nunca en 118.

        Insight de detección intentado (del experto): el impulso de un
        marcapasos es un transitorio eléctrico -- sube y baja en ~1-2ms --
        mucho más rápido que la subida de un QRS biológico real
        (típicamente 20-40ms). Esta función busca esa firma: picos de
        pendiente extrema (`slope_z_threshold` desviaciones absolutas
        medianas, MAD, sobre la mediana de |dv/dt|) agrupados en eventos
        contiguos (`merge_gap_ms`), aceptados como "espiga" solo si el
        evento es angosto (`max_spike_width_ms`) y está rodeado de
        pendiente normal en una ventana más amplia (`isolation_ms`).

        Por qué no es confiable (evidencia, no especulación): inspección
        directa de las 5 ubicaciones de mayor pendiente en el registro 217
        (ambas derivaciones, MLII y V1) muestra una deflexión suave,
        fisiológica -- sin una espiga aislada separable del QRS. Un barrido
        de `slope_z_threshold` de 10 a 30 confirma que NINGÚN umbral separa
        217 de forma limpia: en el extremo bajo (z=12-15), el registro 118
        (BRD) dispara MÁS eventos "espiga" que el propio 217 (118: 11-32
        eventos vs 217: 1-10) -- exactamente el falso positivo que el
        mandato clínico prohíbe. En el extremo alto (z=20-25), 217 cae a 0
        eventos -- el marcapasos deja de detectarse del todo. No existe una
        zona intermedia limpia: 108/207/228/233/210 (ruidosos o con
        ectopia) producen sus propios eventos "espiga" de ruido/artefacto
        en todo el rango, indistinguibles de una espiga real de marcapasos
        por amplitud/anchura/aislamiento solos. Conclusión: la firma
        dv/dt-angosto, tal como está especificada, no separa "estimulación
        artificial" de "ruido o QRS aberrante de alta pendiente" en los
        datos de MIT-BIH disponibles -- posiblemente porque la
        digitalización a 360Hz (o un filtro de adquisición previo) ya
        atenuó la espiga original antes de guardarse. Podría comportarse
        distinto sobre una captura de hardware en vivo (ESP32, sin ese
        filtrado) -- no verificable con este banco.

        Returns
        -------
        is_paced : bool
        n_spikes_found : int
            Cuántos eventos de pendiente extrema y angosta se encontraron
            -- diagnóstico, no una bandera confiable (ver arriba).
        """
        if len(signal) < 10:
            return False, 0

        d = np.abs(np.diff(signal)) * self.fs
        median_d = float(np.median(d))
        mad_d = float(np.median(np.abs(d - median_d))) or 1e-9
        threshold = median_d + slope_z_threshold * mad_d
        half_threshold = threshold / 2.0

        candidates = np.where(d > threshold)[0]
        if len(candidates) == 0:
            return False, 0

        merge_gap = max(1, int(merge_gap_ms / 1000.0 * self.fs))
        clusters: List[Tuple[int, int]] = []
        start = int(candidates[0])
        prev = int(candidates[0])
        for c in candidates[1:]:
            c = int(c)
            if c - prev <= merge_gap:
                prev = c
            else:
                clusters.append((start, prev))
                start, prev = c, c
        clusters.append((start, prev))

        isolation_samples = int(isolation_ms / 1000.0 * self.fs)
        n_spikes = 0
        for (s, e) in clusters:
            width_ms = (e - s + 1) / self.fs * 1000.0
            if width_ms > max_spike_width_ms:
                continue
            lo_out = d[max(0, s - isolation_samples):s]
            hi_out = d[e + 1: min(len(d), e + 1 + isolation_samples)]
            is_isolated = (
                (len(lo_out) == 0 or np.median(lo_out) < half_threshold)
                and (len(hi_out) == 0 or np.median(hi_out) < half_threshold)
            )
            if is_isolated:
                n_spikes += 1

        return n_spikes >= min_spikes, n_spikes

    def segment_qrs_complex(
        self,
        signal: np.ndarray,
        r_peak: int,
        window: float = 0.12
    ) -> Tuple[int, int]:
        """
        Segment QRS complex around R peak.
        
        Parameters
        ----------
        signal : ndarray
            ECG signal
        r_peak : int
            Index of R peak
        window : float
            Window width in seconds
            
        Returns
        -------
        q_idx : int
            Index of Q point (start of QRS)
        s_idx : int
            Index of S point (end of QRS)
        """
        half_window = int(window * self.fs / 2)
        start = max(0, r_peak - half_window)
        end = min(len(signal), r_peak + half_window)
        
        segment = signal[start:end]
        q_idx = np.argmin(segment)
        s_idx = np.argmin(segment[r_peak - start:]) + (r_peak - start)
        
        return start + q_idx, start + s_idx
    
    def detect_pqrst(
        self,
        signal: np.ndarray
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect P, QRS, and T waves in ECG signal.
        
        Uses template matching and morphological analysis.
        
        Returns
        -------
        dict
            Detected waves with indices, amplitudes, and durations
        """
        r_peaks = self.detect_r_peaks(signal)
        
        if len(r_peaks) == 0:
            return {}
        
        waves = {}
        
        for idx, r_peak in enumerate(r_peaks[:5]):
            beat_label = f'beat_{idx}'
            
            q_idx, s_idx = self.segment_qrs_complex(signal, r_peak)
            
            p_start = max(0, r_peak - int(0.16 * self.fs))
            p_end = q_idx
            p_segment = signal[p_start:p_end]
            p_idx = p_start + np.argmax(np.abs(p_segment))
            
            t_start = s_idx
            t_end = min(len(signal), r_peak + int(0.36 * self.fs))
            t_segment = signal[t_start:t_end]
            t_idx = t_start + np.argmax(np.abs(t_segment))
            
            waves[beat_label] = {
                'P': {'index': p_idx, 'amplitude': float(signal[p_idx])},
                'Q': {'index': q_idx, 'amplitude': float(signal[q_idx])},
                'R': {'index': r_peak, 'amplitude': float(signal[r_peak])},
                'S': {'index': s_idx, 'amplitude': float(signal[s_idx])},
                'T': {'index': t_idx, 'amplitude': float(signal[t_idx])}
            }
        
        return waves
    
    def measure_intervals(
        self,
        signal: np.ndarray
    ) -> Dict[str, float]:
        """
        Measure diagnostic ECG intervals in milliseconds.
        
        Returns
        -------
        dict
            PR, QRS, QT, QTc intervals
        """
        r_peaks = self.detect_r_peaks(signal)
        
        if len(r_peaks) < 1:
            return {}
        
        measurements = {}
        
        r_peak = r_peaks[0]
        q_idx, s_idx = self.segment_qrs_complex(signal, r_peak)
        
        p_start = max(0, r_peak - int(0.16 * self.fs))
        p_segment = signal[p_start:q_idx]
        p_idx = p_start + np.argmax(np.abs(p_segment))
        
        t_end = min(len(signal), r_peak + int(0.40 * self.fs))
        t_segment = signal[s_idx:t_end]
        t_idx = s_idx + np.argmax(np.abs(t_segment))
        
        pr_interval = (r_peak - p_idx) / self.fs * 1000
        qrs_duration = (s_idx - q_idx) / self.fs * 1000
        qt_interval = (t_idx - q_idx) / self.fs * 1000
        
        mean_rr = np.mean(np.diff(r_peaks) / self.fs) if len(r_peaks) > 1 else 1.0
        
        qtc = qt_interval / np.sqrt(mean_rr) if mean_rr > 0 else qt_interval
        
        measurements = {
            'PR_interval_ms': float(np.clip(pr_interval, 0, 300)),
            'QRS_duration_ms': float(np.clip(qrs_duration, 0, 200)),
            'QT_interval_ms': float(np.clip(qt_interval, 0, 600)),
            'QTc_ms': float(np.clip(qtc, 0, 600)),
            'RR_interval_ms': float(mean_rr * 1000)
        }
        
        return measurements
    
    def detect_st_elevation(
        self,
        signal: np.ndarray,
        threshold: float = 0.1
    ) -> Dict[str, Any]:
        """
        Detect ST segment elevation (STEMI indicator).
        
        Parameters
        ----------
        signal : ndarray
            ECG signal in mV
        threshold : float
            Elevation threshold in mV
            
        Returns
        -------
        dict
            ST elevation analysis results
        """
        r_peaks = self.detect_r_peaks(signal)
        
        if len(r_peaks) == 0:
            return {'st_elevation_detected': False, 'elevation_magnitude': 0.0}
        
        st_points = []
        for r_peak in r_peaks[:5]:
            st_idx = min(len(signal) - 1, r_peak + int(0.08 * self.fs))
            st_points.append(signal[st_idx])
        
        mean_st = np.mean(st_points)
        baseline = np.median(signal)
        elevation = mean_st - baseline
        
        return {
            'st_elevation_detected': elevation > threshold,
            'elevation_magnitude': float(elevation),
            'elevation_threshold': threshold
        }
    
    def estimate_heart_rate(self, r_peaks: np.ndarray) -> float:
        """Estimate heart rate from R peaks."""
        if len(r_peaks) < 2:
            return 0.0
        
        rr_intervals = np.diff(r_peaks) / self.fs
        return 60.0 / np.mean(rr_intervals) if len(rr_intervals) > 0 else 0.0

    def estimate_heart_rate_with_confidence(
        self,
        signal: np.ndarray,
        quality_threshold: float = QUALITY_THRESHOLD,
        patient_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, float]:
        """Compuerta whitelist "confirma sinusal o declina" (2026-08-24,
        Capa 2/5B, tanda de cableado -- detector TKEO ratificado por el
        experto como motor definitivo tras 6 rondas de validación;
        compuerta de calidad recalibrada a Vpp por ventana, Modelo 1 del
        experto).

        Principio rector, explícito: los filtros de abajo son criterios de
        RECHAZO, no de aceptación -- esquivarlos todos no prueba "sinusal",
        solo "no obviamente inválido". La aceptación exige ADEMÁS que la
        variabilidad caiga en la banda fisiológica sinusal y que la calidad
        de señal supere `quality_threshold`. Culpable de inválido hasta
        demostrar sinusal, no al revés.

        Detector (2026-08-24, cambio de esta tanda): usa
        `detect_r_peaks_tkeo()`, no `detect_r_peaks_bidirectional()` (el de
        la ronda 5) -- por eso ya no recibe `prominence_factor` (parámetro
        del detector viejo, sin sentido para TKEO; se retiró de la firma en
        vez de dejarlo como argumento muerto). R-R sobre
        `refine_peaks_parabolic()` (Task Force ESC/NASPE 1996), igual que
        antes.

        Orden de evaluación (cada paso puede terminar en
        `ClinicalDataQualityError`, ninguno devuelve nunca un HR adivinado):

        0. Bloqueo de metadatos (el override clínico) -- ver nota de
           `patient_metadata` abajo.

        1. pRRx (FA/alta carga ectópica): porcentaje de diferencias R-R
           sucesivas >= `PRR_THRESHOLD_MS` (31ms, citado -- Buś et al.). Si
           supera `PRR_FRACTION_LIMIT` (50%), declina. Sin cambios en esta
           tanda -- el experto confirmó que es robusto entre detectores
           (ver ronda 6, banco de 25: los mismos registros declinan por
           pRRx con picos bidireccionales o TKEO).

        2. Filtro del Metrónomo: SDNN bajo `METRONOME_SDNN_MS` (3ms) --
           declina sin diagnosticar causa. Sin cambios.

        3. Banda fisiológica sinusal: SDNN en
           [`SINUS_SDNN_MIN_MS`, `SINUS_SDNN_MAX_MS`]. Sin cambios.

        4. Calidad de señal -- RECALIBRADA esta tanda (Parte A, Modelo 1
           del experto): la ronda 6 encontró que medir consistencia de
           AMPLITUD PUNTUAL (`x[peak_i]`) regresionaba el registro 118
           (BRD) de aceptación correcta a rechazo incorrecto -- el fiducial
           de TKEO ancla en la máxima pendiente (mitad del ascenso del
           QRS), no en la cima de voltaje, y en un QRS mellado en "M" (BRD)
           ese punto de pendiente salta entre muescas -- medir voltaje ahí
           es inherentemente inestable, sin que la señal en sí sea mala.

           Reemplazo: Vpp por ventana. Para cada pico, ventana
           `±VPP_WINDOW_MS` (50ms, misma ventana que usa el mapeo fiducial
           de TKEO) sobre la señal ORIGINAL; `Vpp[i] = max(ventana) -
           min(ventana)` -- captura la amplitud de TODO el complejo QRS
           (las muescas del BRD caben en una ventana de 100ms), sin
           importar en qué punto exacto cayó el fiducial. Métrica:
           `CV_amp = σ(Vpp) / μ(Vpp)` -- CV bajo, Vpp consistente latido a
           latido, señal de calidad. `VPP_CV_THRESHOLD` (0.15, PROVISIONAL,
           sugerido por el experto) se incrusta en el denominador de
           `amplitude_score = clip(1 - CV_amp/VPP_CV_THRESHOLD, 0, 1)`: con
           esa escala, `CV_amp >= VPP_CV_THRESHOLD` fuerza
           `amplitude_score = 0`, y con la mezcla 50/50 con
           `regularity_score` (máximo posible entonces: 0.5), la
           confianza NUNCA alcanza `quality_threshold` (0.6) -- el umbral
           del experto queda embebido en la escala, no como un segundo
           chequeo redundante.

        Solo si los 5 pasos se superan, devuelve `(heart_rate, confidence)`."""
        if patient_metadata and patient_metadata.get('pacemaker'):
            raise ClinicalDataQualityError(
                "Escritura declinada: paciente marcado como portador de marcapasos en su perfil "
                "clínico -- biometría autonómica no aplicable, independientemente de la señal."
            )

        peaks = self.detect_r_peaks_tkeo(signal)
        if len(peaks) < 3:
            raise ClinicalDataQualityError(
                f"Solo {len(peaks)} picos detectados -- insuficiente para un HR confiable."
            )

        refined = self.refine_peaks_parabolic(signal, peaks)
        rr_ms = np.diff(refined) / self.fs * 1000.0
        hr = 60000.0 / np.mean(rr_ms)

        if len(rr_ms) > 1:
            rr_diffs = np.abs(np.diff(rr_ms))
            prrx = float(np.mean(rr_diffs >= PRR_THRESHOLD_MS))
            if prrx > PRR_FRACTION_LIMIT:
                raise ClinicalDataQualityError(
                    f"Ritmo irregular no sinusal (posible FA/arritmia) -- pRR{PRR_THRESHOLD_MS:.0f}="
                    f"{prrx:.0%} de las diferencias R-R sucesivas superan {PRR_THRESHOLD_MS:.0f}ms "
                    f"(umbral: {PRR_FRACTION_LIMIT:.0%}). Escritura declinada."
                )

        sdnn_ms = float(np.std(rr_ms))
        if sdnn_ms < METRONOME_SDNN_MS:
            raise ClinicalDataQualityError(
                f"Ausencia de variabilidad autonómica detectable (SDNN={sdnn_ms:.2f}ms < "
                f"{METRONOME_SDNN_MS:.0f}ms) -- biometría declinada. No se afirma la causa (puede ser "
                "ritmo estimulado, denervación u otra condición); se declina por lo que se observa, "
                "no por lo que se infiere."
            )

        if not (SINUS_SDNN_MIN_MS <= sdnn_ms <= SINUS_SDNN_MAX_MS):
            raise ClinicalDataQualityError(
                f"SDNN={sdnn_ms:.2f}ms fuera de la banda fisiológica sinusal "
                f"[{SINUS_SDNN_MIN_MS:.0f}, {SINUS_SDNN_MAX_MS:.0f}]ms -- no confirmable como ritmo "
                "sinusal autonómicamente evaluable. Escritura declinada."
            )

        rr = rr_ms / 1000.0
        rr_cv = float(np.std(rr) / np.mean(rr)) if np.mean(rr) > 0 else 1.0
        regularity_score = float(np.clip(1.0 - rr_cv / 0.5, 0.0, 1.0))

        vpp_window = max(1, int(VPP_WINDOW_MS / 1000.0 * self.fs))
        vpp_values = []
        for p in peaks:
            lo = max(0, p - vpp_window)
            hi = min(len(signal), p + vpp_window + 1)
            window_signal = signal[lo:hi]
            vpp_values.append(float(np.max(window_signal) - np.min(window_signal)))
        vpp_values = np.array(vpp_values)
        vpp_cv = float(np.std(vpp_values) / np.mean(vpp_values)) if np.mean(vpp_values) > 0 else 1.0
        amplitude_score = float(np.clip(1.0 - vpp_cv / VPP_CV_THRESHOLD, 0.0, 1.0))

        confidence = float(np.clip(0.5 * regularity_score + 0.5 * amplitude_score, 0.0, 1.0))

        if confidence < quality_threshold:
            raise ClinicalDataQualityError(
                f"Confianza {confidence:.2f} por debajo del umbral {quality_threshold:.2f} "
                f"(CV_amp de Vpp={vpp_cv:.3f}, umbral={VPP_CV_THRESHOLD:.2f}) -- señal con ruido/"
                "irregularidad excesiva, HR no confiable para escribir al gemelo."
            )

        return float(hr), confidence

    def detect_arrhythmias(self, signal: np.ndarray) -> Dict[str, Any]:
        """
        Detect common arrhythmias from ECG.

        Detects: tachycardia, bradycardia, irregular rhythm, PVC, AFib indicators

        Expone también los valores crudos que disparan cada regla (`rr_cv`,
        `rr_std_ms`, `max_rr_jump_pct`) -- 2026-08-06, para que
        `detect_clinical_pattern()` pueda citar el criterio medido exacto
        en vez de un porcentaje de confianza inventado (ver CHANGELOG.md).
        """
        r_peaks = self.detect_r_peaks(signal)

        if len(r_peaks) < 2:
            return {'status': 'insufficient_data'}

        rr_intervals = np.diff(r_peaks) / self.fs
        hr = 60.0 / np.mean(rr_intervals)

        rr_cv = np.std(rr_intervals) / np.mean(rr_intervals)
        rr_std_ms = np.std(rr_intervals) * 1000.0
        rr_jumps_pct = (
            np.diff(rr_intervals) / np.mean(rr_intervals) * 100.0 if len(rr_intervals) > 1 else np.array([])
        )
        max_rr_jump_pct = float(np.max(rr_jumps_pct)) if rr_jumps_pct.size > 0 else 0.0

        findings = {
            'heart_rate': float(hr),
            'arrhythmias': [],
            'rr_cv': float(rr_cv),
            'rr_std_ms': float(rr_std_ms),
            'max_rr_jump_pct': max_rr_jump_pct,
        }

        if hr > 100:
            findings['arrhythmias'].append('Tachycardia')
        elif hr < 60:
            findings['arrhythmias'].append('Bradycardia')

        if rr_cv > 0.15:
            findings['arrhythmias'].append('Irregular rhythm')

        if max_rr_jump_pct > 30.0:
            findings['arrhythmias'].append('Ectopic beats (possible PVC)')

        if rr_std_ms > 150.0 and hr > 90:
            findings['arrhythmias'].append('Possible atrial fibrillation')

        return findings

    def _classify_bbb(
        self,
        qrs: float,
        leads_v1_v6: Optional[Tuple[np.ndarray, np.ndarray]],
        reference_signal: Optional[np.ndarray] = None,
    ) -> Tuple[str, str]:
        """Bifurcación honesta del Detector BBB, Fase 3 (2026-08-12): con
        V1/V6 verificadas, usa el detector morfológico real
        (`clinical.bbb_detector.detect_bundle_branch_block`); sin ellas,
        cae al genérico de siempre, ahora honesto sobre POR QUÉ no
        distingue -- ver docstring de `detect_clinical_pattern()`.

        `reference_signal` (opcional, lead II si `leads` la trae): ancla la
        delineación de V1 y V6 al MISMO latido -- ver corrección de
        sincronización en `clinical/bbb_detector.py` (Fase 3, 2026-08-12)."""
        if leads_v1_v6 is None:
            return (
                "Bundle Branch Block",
                f"QRS ancho={qrs:.0f} ms (umbral > 120) -- solo 1 derivación disponible, no se puede "
                "distinguir la rama sin V1/V6 (ver clinical/bbb_detector.py)",
            )
        v1_signal, v6_signal = leads_v1_v6
        result = detect_bundle_branch_block(v1_signal, v6_signal, self.fs, reference_signal=reference_signal)
        if result.pattern is None:
            # El propio delineador (más estricto, ver clinical/bbb_detector.py) no
            # confirmó QRS>120ms sobre V1/V6 específicamente, o no encontró un
            # latido válido -- cae al genérico, honesto, sin afirmar normalidad
            # que este detector no midió.
            return (
                "Bundle Branch Block",
                f"QRS ancho={qrs:.0f} ms (umbral > 120) -- " + "; ".join(result.reasoning),
            )
        return (result.pattern, "; ".join(result.reasoning))

    def detect_clinical_pattern(
        self,
        signal: np.ndarray,
        leads: Optional[Dict[str, np.ndarray]] = None,
    ) -> Dict[str, Any]:
        """
        Detect a clinical ECG pattern and assign a multiclass cardiology label.

        Cada patrón es una regla determinista sobre valores medidos (QTc de
        Bazett, QRS, PR, FC, RR) -- no hay ninguna noción de probabilidad
        involucrada: una condición se cumple o no se cumple, no tiene un
        "porcentaje de certeza". Por eso este método NO devuelve un
        `confidence` (2026-08-06, retirado -- era una constante literal por
        rama, 0.95/0.92/.../0.60, con apariencia de métrica calculada sin
        serlo; violaba Art. I de la Constitución. Ver CHANGELOG.md). En su
        lugar, `reasoning` cita el criterio medido exacto -- valor + umbral
        -- que disparó el patrón: honesto y verificable.

        `leads` (opcional): mapping de nombre de derivación a señal (p.ej.
        `{"V1": arr, "V6": arr, ...}`), el mismo shape que usa
        `clinical/ecg12.py`. Detector BBB, Fase 3 (2026-08-12): reemplaza la
        sub-regla que distinguía LBBB de RBBB comparando el promedio de las
        primeras/últimas 10 muestras crudas de la señal -- un criterio sin
        respaldo clínico real, retirado por completo. Bifurcación honesta:
        si `leads` trae V1 Y V6 (verificadas por nombre, no por posición),
        se usa el detector morfológico real sobre esas derivaciones
        (`clinical.bbb_detector.detect_bundle_branch_block`, criterio
        validado + delineador de QRS de la Sub-Fase 2.5) -- puede devolver
        RBBB, LBBB, o "Bloqueo de rama indeterminado" (nunca fuerza una
        rama sin evidencia). Sin V1/V6, cae al genérico "Bundle Branch
        Block" de siempre, ahora honesto sobre POR QUÉ no distingue (antes
        forzaba L/R igual sin ellas). Si `leads` también trae "II" (el
        estándar de ritmo), se usa para anclar V1 y V6 al MISMO latido
        (corrección de sincronización, Fase 3, 2026-08-12 -- ver
        `clinical/bbb_detector.py::_select_reference_beat()`); sin ella, el
        detector sigue siendo correcto pero ancla en V6 como fallback.
        Validado contra 50 casos reales de PTB-XL -- ver CHANGELOG.md para
        la matriz de confusión completa y la interpretación honesta de los
        resultados.
        """
        r_peaks = self.detect_r_peaks(signal)
        intervals = self.measure_intervals(signal)
        st_info = self.detect_st_elevation(signal)
        arrhythmias = self.detect_arrhythmias(signal)

        leads_v1_v6 = None
        reference_lead_signal = None
        if leads:
            v1_key = next((k for k in leads if k.strip().upper() == "V1"), None)
            v6_key = next((k for k in leads if k.strip().upper() == "V6"), None)
            if v1_key is not None and v6_key is not None:
                leads_v1_v6 = (leads[v1_key], leads[v6_key])
            ii_key = next((k for k in leads if k.strip().upper() == "II"), None)
            if ii_key is not None:
                reference_lead_signal = leads[ii_key]

        pattern = "Normal Sinus Rhythm"
        details: List[str] = []

        hr = arrhythmias.get('heart_rate', 0.0)
        qrs = intervals.get('QRS_duration_ms', 0.0)
        pr = intervals.get('PR_interval_ms', 0.0)
        qtc = intervals.get('QTc_ms', 0.0)
        rr_intervals = np.diff(r_peaks) / self.fs if len(r_peaks) > 1 else np.array([])
        rr_cv = float(np.std(rr_intervals) / np.mean(rr_intervals)) if rr_intervals.size > 1 else 0.0

        if st_info.get('st_elevation_detected', False):
            pattern = "STEMI"
            details.append(
                f"ST elevado {st_info.get('elevation_magnitude', 0.0):.2f} mV "
                f"(umbral > {st_info.get('elevation_threshold', 0.0):.2f} mV)"
            )
        elif 'Possible atrial fibrillation' in arrhythmias.get('arrhythmias', []):
            pattern = "AFib"
            details.append(
                f"RR muy variable: desviación estándar {arrhythmias.get('rr_std_ms', 0.0):.0f} ms "
                f"con FC={hr:.0f} bpm (umbral: DE>150 ms y FC>90 bpm)"
            )
        elif any('Ectopic beats' in x for x in arrhythmias.get('arrhythmias', [])):
            pattern = "PVC"
            details.append(
                f"Salto de RR de {arrhythmias.get('max_rr_jump_pct', 0.0):.0f}% respecto al RR medio "
                "(umbral > 30%)"
            )
        elif hr > 120 and qrs > 110:
            pattern = "VT"
            details.append(f"FC={hr:.0f} bpm (umbral > 120) con QRS={qrs:.0f} ms (umbral > 110)")
        elif qrs > 120 and hr >= 40 and hr <= 110:
            if pr < 200:
                pattern, bbb_detail = self._classify_bbb(qrs, leads_v1_v6, reference_lead_signal)
                details.append(f"QRS ancho={qrs:.0f} ms (umbral > 120) con PR={pr:.0f} ms (< 200) -- {bbb_detail}")
            else:
                pattern = "AV Block"
                details.append(f"QRS ancho={qrs:.0f} ms (umbral > 120) con PR prolongado={pr:.0f} ms (≥ 200)")
        elif pr > 210:
            pattern = "AV Block"
            details.append(f"PR prolongado={pr:.0f} ms (umbral > 210)")
        elif qtc > 470:
            pattern = "Long QT / Risk"
            details.append(f"QTc={qtc:.0f} ms (umbral > 470 ms, fórmula de Bazett)")
        elif qrs > 120:
            pattern, bbb_detail = self._classify_bbb(qrs, leads_v1_v6, reference_lead_signal)
            details.append(bbb_detail)
        else:
            details.append(
                f"FC={hr:.0f} bpm, QRS={qrs:.0f} ms, PR={pr:.0f} ms, QTc={qtc:.0f} ms -- todos dentro de rango"
            )

        if len(r_peaks) < 3:
            details.append(f"Basado en pocos latidos: solo {len(r_peaks)} picos R detectados -- confiabilidad reducida")

        return {
            'pattern': pattern,
            'reasoning': details,
            'features': {
                'heart_rate': float(hr),
                'qrs_duration_ms': float(qrs),
                'pr_interval_ms': float(pr),
                'qtc_ms': float(qtc),
                'rr_cv': float(rr_cv)
            }
        }

    def compute_heart_rate_variability(
        self,
        r_peaks: np.ndarray
    ) -> Dict[str, float]:
        """
        Compute HRV metrics from R peaks.
        
        Returns temporal and frequency domain indices.
        """
        if len(r_peaks) < 2:
            return {}
        
        rr_intervals = np.diff(r_peaks) / self.fs
        
        sdnn = float(np.std(rr_intervals))
        rmssd = float(np.sqrt(np.mean(np.diff(rr_intervals) ** 2)))
        nn50 = float(np.sum(np.abs(np.diff(rr_intervals)) > 0.05))
        pnn50 = float(100 * nn50 / len(rr_intervals)) if len(rr_intervals) > 0 else 0.0
        
        from scipy.fft import fft
        
        frequencies = np.fft.fftfreq(len(rr_intervals), np.mean(np.diff(r_peaks)) / self.fs)
        power = np.abs(fft(rr_intervals)) ** 2
        
        power = power[frequencies > 0]
        frequencies = frequencies[frequencies > 0]
        
        vlf = float(np.sum(power[(frequencies >= 0.003) & (frequencies < 0.04)]))
        lf = float(np.sum(power[(frequencies >= 0.04) & (frequencies < 0.15)]))
        hf = float(np.sum(power[(frequencies >= 0.15) & (frequencies <= 0.4)]))
        
        lf_hf = float(lf / hf) if hf > 0 else 0.0
        
        return {
            'SDNN_s': sdnn,
            'RMSSD_s': rmssd,
            'pNN50_%': pnn50,
            'VLF_power': vlf,
            'LF_power': lf,
            'HF_power': hf,
            'LF_HF_ratio': lf_hf,
            'total_power': vlf + lf + hf
        }
    
    def clinical_summary(self, signal: np.ndarray) -> str:
        """Generate clinical ECG summary."""
        r_peaks = self.detect_r_peaks(signal)

        if len(r_peaks) < 1:
            return "ECG: Insufficient signal quality for analysis"

        hr = self.estimate_heart_rate(r_peaks)
        intervals = self.measure_intervals(signal)
        st_elevation = self.detect_st_elevation(signal)
        arrhythmias = self.detect_arrhythmias(signal)
        pattern_info = self.detect_clinical_pattern(signal)

        recommendations = "Correlacionar hallazgos ECG con datos clínicos y considerar derivación cardiológica."
        if pattern_info['pattern'] == 'STEMI':
            recommendations = "Activar protocolo STEMI y priorizar reperfusión inmediata."
        elif pattern_info['pattern'] == 'AFib':
            recommendations = "Evaluar control de frecuencia y considerar anticoagulación según CHA2DS2-VASc."
        elif pattern_info['pattern'] == 'PVC':
            recommendations = "Valorar ecocardiograma y seguimiento de ectopias si son frecuentes o sintomáticas."
        elif pattern_info['pattern'] == 'VT':
            recommendations = "Iniciar manejo urgente de taquiarritmia ventricular y considerar soporte avanzado."
        elif pattern_info['pattern'] in ('LBBB', 'RBBB'):
            recommendations = "Investigar enfermedad estructural subyacente y correlacionar con síntomas."
        elif pattern_info['pattern'] == 'AV Block':
            recommendations = "Evaluar grado de bloqueo y considerar marcapasos si es sintomático."

        findings = arrhythmias.get('arrhythmias', ['Regular sinus rhythm'])
        if findings == ['Regular sinus rhythm']:
            findings = ['Regular sinus rhythm']

        summary = f"""
╔════════════════════════════════════════════════╗
║         ECG CLINICAL SUMMARY                   ║
╚════════════════════════════════════════════════╝

RHYTHM & RATE:
  • Heart Rate: {hr:.0f} bpm

INTERVALS (normal ranges):
  • PR: {intervals.get('PR_interval_ms', 0):.0f} ms (120-200)
  • QRS: {intervals.get('QRS_duration_ms', 0):.0f} ms (<120)
  • QT: {intervals.get('QT_interval_ms', 0):.0f} ms
  • QTc: {intervals.get('QTc_ms', 0):.0f} ms (<440 male, <460 female)

ST SEGMENT:
  • Elevation: {st_elevation.get('elevation_magnitude', 0):.2f} mV
  • Status: {'ELEVATED' if st_elevation['st_elevation_detected'] else 'Normal'}

FINDINGS:
  • {', '.join(findings)}

CLASSIFICATION:
  • Pattern detected: {pattern_info['pattern']}
  • Confidence: {pattern_info['confidence']*100:.0f}%
  • Reasoning: {', '.join(pattern_info.get('reasoning', ['Revisión completa recomendada']))}

RECOMMENDATIONS:
  • {recommendations}

╔════════════════════════════════════════════════╗
"""
        return summary


