import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union

from scipy.signal import butter, filtfilt, hilbert


@dataclass(frozen=True)
class PLVResult:
    """Resultado del Phase-Locking Value neurocardíaco (theta frontomedial
    EEG <-> banda HF del HRV). `available` distingue explícitamente
    "no disponible (con motivo)" de "PLV=x" -- NUNCA cae a un número por
    defecto cuando falta señal o hay poca señal. Ese patrón de default
    silencioso (`raw_metrics.get(key, valor)`) fue el origen de los 3
    fantasmas retirados el 2026-08-15 -- no se repite aquí. Ver
    CHANGELOG.md 2026-08-19 para el dictamen del validador."""
    available: bool
    value: Optional[float] = None       # PLV crudo en [0,1], solo si available
    reason: Optional[str] = None        # motivo de no-disponibilidad
    duration_s: Optional[float] = None  # segundos de señal simultánea detectados


class BiocoreEngine:
    """
    Motor de Análisis Fisiológico Avanzado para BIOCORE.
    Calcula índices fisiológicos integrados basados en fusión de señales (ECG, EEG).

    Renombrado desde "biomarcadores propietarios" (2026-08-15): el nombre
    "propietario" no tenía metodología ni cita detrás -- ver CHANGELOG.md.
    "EDA" se retiró de esta lista el mismo día: no hay ningún módulo de señal
    EDA en el repo, y el único consumidor (Stress Index) se recortó a su
    único componente real (LF/HF de HRV).

    `calculate_neurocardiac_coupling_score()` (suma de potencias absolutas +
    `signal_coherence` placeholder) se retiró el 2026-08-19 -- el validador
    la calificó de pseudocientífica en su conjunto. La reemplaza
    `calculate_neurocardiac_plv()`, un Phase-Locking Value real que casi
    siempre reportará "no disponible" porque requiere >=180s de señal
    ECG+EEG simultánea que el pipeline hoy no produce -- ver PLVResult.
    """
    # Criterio del validador (2026-08-19, dictamen verbatim) para el PLV
    # neurocardíaco -- ver CHANGELOG.md. Reemplaza la construcción original
    # (alfa EEG + potencia HF + "signal_coherence" placeholder) que el
    # validador calificó como pseudocientífica.
    MIN_PLV_DURATION_S = 180.0       # "mínimo 120-180s de señal simultánea"
    PLV_THETA_BAND_HZ = (4.0, 8.0)   # "Theta Frontomedial (4-8Hz)", NO alfa
    PLV_HF_HRV_BAND_HZ = (0.15, 0.40)  # "banda HF-HRV (0.15-0.40Hz)", NO R-R crudo
    PLV_RR_INTERP_FS = 4.0           # mismo patrón que render_hrv_page()/advanced_hrv.py

    def __init__(self):
        self.baselines = {
            'resting_hr_target': 60.0,    
            'sdnn_target': 50.0,          
            'rmssd_target': 45.0,         
            'vo2_max_proxy_target': 50.0  
        }

    def _normalize(self, value: float, min_val: float, max_val: float, invert: bool = False) -> float:
        if max_val == min_val:
            return 50.0
        norm = (value - min_val) / (max_val - min_val) * 100
        norm = np.clip(norm, 0, 100)
        return round(100 - norm if invert else norm, 2)

    def calculate_stress_index(self, hrv_lf_hf_ratio: float) -> float:
        """Recortado (2026-08-15) a su único componente real y citado --
        Task Force ESC/NASPE 1996. Los componentes EDA (picos SCR,
        conductancia tónica) se retiraron: no hay módulo de señal EDA en el
        repo, eran constantes de preset sin sensor detrás -- ver CHANGELOG.md."""
        hrv_score = self._normalize(hrv_lf_hf_ratio, 0.5, 5.0)
        return round(np.clip(hrv_score, 0, 100), 2)

    def calculate_recovery_index(self, current_resting_hr: float, hrv_rmssd: float, sleep_hours: float) -> float:
        hr_component = self._normalize(current_resting_hr, 45.0, 90.0, invert=True)
        rmssd_component = self._normalize(hrv_rmssd, 10.0, 100.0)
        sleep_component = self._normalize(sleep_hours, 4.0, 9.0)
        recovery_score = (hr_component * 0.40) + (rmssd_component * 0.45) + (sleep_component * 0.15)
        return round(np.clip(recovery_score, 0, 100), 2)

    @staticmethod
    def _bandpass(signal: np.ndarray, fs: float, low: float, high: float, order: int = 4) -> np.ndarray:
        """Butterworth pasa-banda, fase cero (filtfilt) -- primitivo compartido
        por las dos ramas del PLV (theta EEG, HF-HRV)."""
        nyq = fs / 2.0
        b, a = butter(order, [low / nyq, high / nyq], btype='band')
        return filtfilt(b, a, signal)

    @staticmethod
    def _looks_looped(signal: np.ndarray, min_corr: float = 0.995) -> bool:
        """Guard anti-bucle (advertencia del validador): una señal generada
        repitiendo el mismo tramo produce un PLV ~1.0 artefactual. Heurística:
        divide la señal en 4 tramos y busca pares con correlación casi
        perfecta -- una señal fisiológica real/independiente no repite tramos
        no adyacentes casi exactos."""
        n = len(signal)
        quarter = n // 4
        if quarter < 4:
            return False
        chunks = [signal[i * quarter:(i + 1) * quarter] for i in range(4)]
        for i in range(4):
            for j in range(i + 1, 4):
                a, b = chunks[i], chunks[j]
                if np.std(a) == 0 or np.std(b) == 0:
                    continue
                if np.corrcoef(a, b)[0, 1] > min_corr:
                    return True
        return False

    def calculate_neurocardiac_plv(
        self,
        eeg_frontal_signal: Optional[np.ndarray] = None,
        eeg_fs: Optional[float] = None,
        rr_intervals_s: Optional[np.ndarray] = None,
        rr_timestamps_s: Optional[np.ndarray] = None,
    ) -> PLVResult:
        """Phase-Locking Value neurocardíaco -- criterio del validador
        (2026-08-19, verbatim): PLV entre la fase de Theta Frontomedial
        (4-8Hz) del EEG y la fase de la banda HF-HRV (0.15-0.40Hz) del
        tacograma R-R, con un mínimo de 180s de señal ECG+EEG simultánea.
        Reemplaza `calculate_neurocardiac_coupling_score()` (retirado
        2026-08-19): esa función sumaba potencias absolutas con un
        `signal_coherence` sin definición algorítmica -- el validador la
        calificó de pseudocientífica en su conjunto, no solo ese componente.

        Nunca devuelve un número por defecto: si falta señal, hay menos de
        180s de solape, o la señal EEG parece un bucle repetido, devuelve
        `PLVResult(available=False, reason=...)` -- ver CHANGELOG.md.
        """
        if eeg_frontal_signal is None or eeg_fs is None or rr_intervals_s is None or rr_timestamps_s is None:
            return PLVResult(available=False, reason="requiere señal ECG+EEG en vivo simultánea")

        eeg_frontal_signal = np.asarray(eeg_frontal_signal, dtype=float).flatten()
        rr_intervals_s = np.asarray(rr_intervals_s, dtype=float).flatten()
        rr_timestamps_s = np.asarray(rr_timestamps_s, dtype=float).flatten()

        if eeg_frontal_signal.size < 8 or rr_intervals_s.size < 8 or rr_timestamps_s.size != rr_intervals_s.size:
            return PLVResult(available=False, reason="señal insuficiente para estimar PLV")

        eeg_duration = eeg_frontal_signal.size / float(eeg_fs)
        overlap_start = max(0.0, float(rr_timestamps_s[0]))
        overlap_end = min(eeg_duration, float(rr_timestamps_s[-1]))
        duration_s = max(0.0, overlap_end - overlap_start)

        if duration_s < self.MIN_PLV_DURATION_S:
            return PLVResult(
                available=False,
                reason=(
                    f"señal insuficiente: se requieren >={self.MIN_PLV_DURATION_S:.0f}s de ECG+EEG "
                    f"simultáneos, hay {duration_s:.0f}s"
                ),
                duration_s=duration_s,
            )

        if self._looks_looped(eeg_frontal_signal):
            return PLVResult(
                available=False,
                reason=(
                    "la señal EEG parece repetirse en bucle (patrón no independiente) -- PLV no "
                    "calculado para evitar un valor artefactual (~1.0 espurio)"
                ),
                duration_s=duration_s,
            )

        t_grid = np.arange(overlap_start, overlap_end, 1.0 / self.PLV_RR_INTERP_FS)
        if t_grid.size < 8:
            return PLVResult(
                available=False,
                reason="ventana común insuficiente tras alinear ECG y EEG",
                duration_s=duration_s,
            )

        # HF-HRV: tacograma interpolado a rejilla uniforme, filtrado 0.15-0.40Hz, Hilbert.
        rr_uniform = np.interp(t_grid, rr_timestamps_s, rr_intervals_s)
        rr_filtered = self._bandpass(rr_uniform - np.mean(rr_uniform), self.PLV_RR_INTERP_FS, *self.PLV_HF_HRV_BAND_HZ)
        phase_hf = np.angle(hilbert(rr_filtered))

        # Theta frontomedial: filtrado 4-8Hz en fs nativa del EEG, Hilbert; la señal
        # analítica (no la fase cruda) se interpola a la rejilla común para evitar
        # artefactos de wraparound de fase en la interpolación.
        theta_filtered = self._bandpass(
            eeg_frontal_signal - np.mean(eeg_frontal_signal), eeg_fs, *self.PLV_THETA_BAND_HZ
        )
        analytic_theta = hilbert(theta_filtered)
        t_eeg = np.arange(eeg_frontal_signal.size) / float(eeg_fs)
        theta_real = np.interp(t_grid, t_eeg, analytic_theta.real)
        theta_imag = np.interp(t_grid, t_eeg, analytic_theta.imag)
        phase_theta = np.angle(theta_real + 1j * theta_imag)

        plv = self._plv_from_phases(phase_theta, phase_hf)

        return PLVResult(available=True, value=round(plv, 4), duration_s=duration_s)

    @staticmethod
    def _plv_from_phases(phase_a: np.ndarray, phase_b: np.ndarray) -> float:
        """Núcleo matemático del PLV, aislado de filtrado/interpolación para
        poder verificarse con fases sintéticas de respuesta conocida (ver
        tests): `|mean(exp(i*(phase_a - phase_b)))|`. Mide la CONSTANCIA de
        la diferencia de fase a través del tiempo -- 1.0 si el desfase es
        constante (aunque no sea cero), 0.0 si la diferencia de fase es
        independiente/aleatoria en cada muestra."""
        delta_phase = np.asarray(phase_a) - np.asarray(phase_b)
        return float(np.abs(np.mean(np.exp(1j * delta_phase))))

    def calculate_cognitive_load_score(self, eeg_theta_power: float, eeg_alpha_power: float, hr_surge: float) -> float:
        theta_alpha_ratio = eeg_theta_power / max(eeg_alpha_power, 0.1)
        ratio_norm = self._normalize(theta_alpha_ratio, 0.5, 4.0)
        hr_surge_norm = self._normalize(hr_surge, 0.0, 30.0)
        cognitive_load = (ratio_norm * 0.7) + (hr_surge_norm * 0.3)
        return round(np.clip(cognitive_load, 0, 100), 2)

    def calculate_physiological_resilience_score(self, hr_recovery_rate: float, hrv_sdnn: float) -> float:
        """`metabolic_efficiency` se retiró (2026-08-15): su rango 0.5-1.5 es
        fisiológicamente imposible como RER (RER real nunca <0.7 ni >1.5) --
        constructo fantasma sin sensor real detrás, dictamen del validador.
        Pesos originales 0.45/0.35 renormalizados sobre 0.80 para sumar 1.0:
        0.45/0.80=0.5625, 0.35/0.80=0.4375 -- ver CHANGELOG.md."""
        hrr_norm = self._normalize(hr_recovery_rate, 15.0, 50.0)
        sdnn_norm = self._normalize(hrv_sdnn, 15.0, 150.0)
        resilience = (hrr_norm * 0.5625) + (sdnn_norm * 0.4375)
        return round(np.clip(resilience, 0, 100), 2)

    def calculate_autonomic_stability_score(self, bp_variance: float, ppg_pulse_transit_time_var: float) -> float:
        """No expuesta en UI (2026-08-15) -- inputs sin fuente real: no hay
        generador de presión arterial en el repo, y el módulo PPG existente
        (`src/signals/ppg/`) no calcula pulse transit time. 0 de 2 inputs
        reales -- a diferencia de Stress/Resilience, no hay componente que
        recortar ni cita clínica que preservar. Sin reemplazo algorítmico
        identificado (a diferencia de NeuroCardiac->PLV). Se deja el método
        latente, sin llamarse desde `get_full_biomarker_suite()`, por si
        algún día hay instrumentación real de PA/PPG-PTT -- ver
        CHANGELOG.md."""
        bp_score = self._normalize(bp_variance, 2.0, 25.0, invert=True)
        ptt_score = self._normalize(ppg_pulse_transit_time_var, 5.0, 50.0, invert=True)
        stability = (bp_score * 0.5) + (ptt_score * 0.5)
        return round(np.clip(stability, 0, 100), 2)

    def calculate_learning_readiness_index(self, neurocardiac_coupling: float, sleep_recovery_score: float, eeg_beta_attenuation: float) -> float:
        """Score compuesto -- `neurocardiac_coupling` (0-100) es ahora el PLV
        escalado (`plv_result.value*100`), no el viejo score pseudocientífico.
        `get_full_biomarker_suite()` solo llama a esta función cuando el PLV
        está disponible (2026-08-19); si no, Learning Readiness se marca
        `available=False` en cascada, en vez de rellenar este parámetro con
        un valor inventado."""
        beta_norm = self._normalize(eeg_beta_attenuation, 1.0, 10.0)
        readiness = (neurocardiac_coupling * 0.4) + (sleep_recovery_score * 0.4) + (beta_norm * 0.2)
        return round(np.clip(readiness, 0, 100), 2)

    def get_full_biomarker_suite(
        self,
        raw_metrics: Dict[str, float],
        eeg_frontal_signal: Optional[np.ndarray] = None,
        eeg_fs: Optional[float] = None,
        rr_intervals_s: Optional[np.ndarray] = None,
        rr_timestamps_s: Optional[np.ndarray] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """`eeg_frontal_signal`/`eeg_fs`/`rr_intervals_s`/`rr_timestamps_s`
        son opcionales (2026-08-19) -- solo el PLV neurocardíaco los usa.
        Si se omiten (el caso de hoy: Biomarkers Lab no lee `session_state`
        de ECG Lab/EEG Lab, ver auditoría de viabilidad), el PLV se marca
        `available=False` explícitamente -- nunca cae a un preset."""
        hrv_lf_hf = raw_metrics.get('hrv_lf_hf_ratio', 1.5)
        resting_hr = raw_metrics.get('current_resting_hr', 70.0)
        rmssd = raw_metrics.get('hrv_rmssd', 35.0)
        sleep = raw_metrics.get('sleep_hours', 7.0)
        eeg_alpha = raw_metrics.get('eeg_alpha_power', 12.0)
        eeg_theta = raw_metrics.get('eeg_theta_power', 8.0)
        hr_surge = raw_metrics.get('hr_surge', 5.0)
        hr_recovery = raw_metrics.get('hr_recovery_rate', 25.0)
        sdnn = raw_metrics.get('hrv_sdnn', 45.0)
        beta_atten = raw_metrics.get('eeg_beta_attenuation', 4.0)

        stress = self.calculate_stress_index(hrv_lf_hf)
        recovery = self.calculate_recovery_index(resting_hr, rmssd, sleep)
        cognitive = self.calculate_cognitive_load_score(eeg_theta, eeg_alpha, hr_surge)
        resilience = self.calculate_physiological_resilience_score(hr_recovery, sdnn)
        # Autonomic Stability Score: no se calcula aquí (2026-08-15) -- ver
        # docstring de `calculate_autonomic_stability_score()`, 0/2 inputs
        # reales, sin reemplazo identificado.
        plv_result = self.calculate_neurocardiac_plv(eeg_frontal_signal, eeg_fs, rr_intervals_s, rr_timestamps_s)

        if plv_result.available:
            coupling_component = round(plv_result.value * 100, 2)
            readiness = self.calculate_learning_readiness_index(coupling_component, recovery, beta_atten)
            readiness_entry = {
                'available': True,
                'score': readiness,
                'status': 'Listo' if readiness > 65 else 'Fatigado',
            }
        else:
            # Cascada honesta: Learning Readiness depende estructuralmente del
            # PLV (antes, del NeuroCardiac Coupling pseudocientífico) -- no se
            # renormaliza para "seguir mostrando un número" sin ese componente,
            # eso sería la misma decisión de fórmula que solo el usuario toma
            # (ver metabolic_efficiency/Stress Index, 2026-08-15).
            readiness_entry = {
                'available': False,
                'reason': f"depende del PLV neurocardíaco -- {plv_result.reason}",
                'duration_s': plv_result.duration_s,
            }

        return {
            'Stress Index': {'available': True, 'score': stress, 'status': 'Alto' if stress > 65 else 'Moderado' if stress > 35 else 'Óptimo'},
            'Recovery Index': {'available': True, 'score': recovery, 'status': 'Bajo' if recovery < 45 else 'Bueno' if recovery < 75 else 'Excelente'},
            'NeuroCardiac PLV': {
                'available': plv_result.available,
                'plv': plv_result.value,
                'duration_s': plv_result.duration_s,
                'reason': plv_result.reason,
            },
            'Cognitive Load Score': {'available': True, 'score': cognitive, 'status': 'Sobrecarga' if cognitive > 70 else 'Normal'},
            'Physiological Resilience Score': {'available': True, 'score': resilience, 'status': 'Excelente' if resilience > 75 else 'Promedio'},
            'Learning Readiness Index': readiness_entry,
        }
    