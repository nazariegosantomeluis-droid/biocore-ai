"""
Respiratory Signal Generator - Clinical Respiration Monitoring

Generates realistic respiratory signals including:
- Normal breathing
- Tachypnea / Bradypnea
- Apnea (central, obstructive)
- Cheyne-Stokes respiration
- Ataxic respiration
- SpO2 integration (oxygen desaturation)

Clinical References:
- Normal respiratory rate: 12-20 breaths/minute
- Airflow: measured in L/min (typically 0.3-3.0 L/min)
- SpO2 normal: >95%
- ApneaDefinition: >10 seconds without airflow

Arco Respiratory (2026-11-07, Art. I): el generador es el GROUND TRUTH contra el que se valida el
detector.

Fase 2a (ya vigente):
- `generate_respiration()` devuelve la clave `'ground_truth'` con lo que el generador REALMENTE produjo
  (FR efectiva por patrón, eventos con inicio/duración/tipo), no con lo que se pidió.
- Ruido con `np.random.default_rng(seed)`: la misma semilla produce la misma señal bit a bit.
- `apnea_duration`, `apnea_onset`, `apnea_period` y `expiration_time` tienen efecto real; con sus valores
  por defecto el flujo de los patrones normal, taquipnea, bradipnea y ambas apneas es el histórico.
- Los parámetros imposibles lanzan `ImpossibleParameters` (un `ValueError`).

Fase 2b (2026-11-07, criterios firmados por Luis):
- SpO2 fisiológica y estable sin eventos (basal + ruido): ya NO se deriva de |flujo|. Cada apnea anotada
  produce una desaturación en el dedo cuyo nadir llega al FIN del evento + `circulation_delay` (Tc), con
  profundidad `desaturation_rate · T` y recuperación en rampa a TASA CONSTANTE `resaturation_rate`
  (la duración de la recuperación resulta de la profundidad, por eso `recovery_time` se retiró).
  `desaturation_level` es el piso. Fuentes y estado de cada valor en `SPO2_MODEL_SOURCES`.
- Atáxica: duración y profundidad aleatorias por respiración (parámetro `irregularity`, HEURISTIC).
- Cheyne-Stokes: cada valle es una apnea CENTRAL anotada en el ground truth (esfuerzo ausente).

Unidades de la señal de flujo (verificado por ejecución, 2026-11-07): es FLUJO en L/min con pico =
volumen_corriente x FR (proporcional a pi·f·VT, como corresponde: crece con la FR). La escala absoluta es
la del generador, no está calibrada: el volumen inspirado integrado por respiración NO es el volumen
corriente (con los valores por defecto 0.08 L frente a 0.5 L). Todo umbral sobre esta señal debe ser relativo.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

KNOWN_PATTERNS = (
    "normal", "tachypnea", "bradypnea", "apnea_central", "apnea_obstructive", "cheyne_stokes", "ataxic",
)

AIRFLOW_UNITS = "L/min (escala del generador: pico = volumen_corriente x FR; el volumen integrado no es el corriente)"

# Estado de cada valor del modelo de SpO2 (criterios firmados por Luis, 2026-11-07).
SPO2_MODEL_SOURCES = {
    "circulation_delay_s": "Valor BIOCORE (Tc = 15 s; la fuente solo da el límite normal < 20 s: Hsia 2026, Sensors 26(15):4849)",
    "desaturation_rate_pct_s": "Howarth 2026 (Sleep Breath, SHHS: media 0.30 %/s)",
    "resaturation_rate_pct_s": "Howarth 2026 (Sleep Breath, SHHS: media 0.70 %/s)",
    "buffer_latency": "no modelada (L = 0)",
    "floor": "desaturation_level",
}


# Criterios firmados por Luis (Berry 2012, AASM) con los que el generador ANOTA los eventos que no salen de un
# calendario (atáxica y los bordes de Cheyne-Stokes). Son una copia deliberada de las constantes del
# analizador: el generador no importa NADA del detector (un ground truth calculado con el detector sería
# circular); un test fija que las dos copias coinciden.
APNEA_DROP_FRACTION = 0.90        # caída >= 90 % de la excursión pico respecto a la basal previa
APNEA_MIN_DURATION_S = 10.0       # durante >= 10 s
BASELINE_WINDOW_S = 120.0         # basal: respiraciones de los 120 s previos (consenso de Chicago)
STABLE_BREATHS_TO_AVERAGE = 3     # patrón inestable: media de las 3 mayores
BASELINE_STABILITY_CV = 0.30      # HEURISTIC: CV de las amplitudes a partir del cual el patrón es "inestable"
# HEURISTIC: un evento está "al límite" si una respiración somera interior llega a >= 95 % del umbral del 10 % de la
# basal, o si dura menos de 10.5 s. Calibrado con 360 registros atáxicos: los 3 eventos que el detector no ve tenían
# un margen de 0.1-0.6 %; el ruido de la señal y de la basal (~1 %) decide ahí, no el algoritmo.
NEAR_THRESHOLD_MARGIN = 0.05


class ImpossibleParameters(ValueError):
    """Combinación de parámetros imposible. `control` nombra el parámetro afectado (para que la UI
    muestre el error junto al control correspondiente)."""

    def __init__(self, message: str, control: str = ""):
        super().__init__(message)
        self.control = control


@dataclass
class RespiratoryPattern:
    """Configuration for respiratory signal generation"""
    respiratory_rate: float = 15  # breaths/minute
    tidal_volume: float = 0.5  # liters
    inspiration_time: float = 1.0  # seconds
    # seconds. None (por defecto) = la espiración ocupa el resto del ciclo (comportamiento histórico).
    # Un valor explícito acota el flujo espiratorio a esa duración y deja una pausa telespiratoria
    # (flujo cero) hasta el final del ciclo; inspiración + espiración no pueden superar el ciclo.
    expiration_time: Optional[float] = None

    # Pathological patterns
    pattern_type: str = "normal"  # "normal", "tachypnea", "bradypnea", "apnea_central", "apnea_obstructive", "cheyne_stokes", "ataxic"
    apnea_duration: float = 20.0  # seconds (apnea patterns y valle de Cheyne-Stokes)
    cheyne_stokes_cycle: float = 60.0  # seconds (for Cheyne-Stokes)

    # SpO2 related
    baseline_spo2: float = 98  # %
    desaturation_level: float = 85  # % PISO de la SpO2 durante un evento
    # Modelo de SpO2 (fase 2b). Tc = "Valor BIOCORE"; las tasas son medias de Howarth 2026 (SHHS).
    circulation_delay: float = 15.0  # s, rango 5-30
    desaturation_rate: float = 0.30  # %/s
    resaturation_rate: float = 0.70  # %/s

    # Calendario de eventos de apnea: un evento empieza `apnea_onset` s dentro de cada periodo de
    # `apnea_period` s y dura `apnea_duration` s (por defecto 40 s / 60 s / 20 s, como siempre).
    apnea_onset: float = 40.0
    apnea_period: float = 60.0

    # Atáxica: coeficiente de variación de la duración y la profundidad de cada respiración.
    # HEURISTIC: sin fuente clínica; 0.20 es una propuesta pendiente de confirmación. Medido (120 registros,
    # FR 8/15/30): con 0.20 el detector no ve ninguna falsa apnea y el CV realizado es 0.20 (mín. 0.15); con
    # 0.30 la regla de Berry para patrones inestables (basal = media de las 3 mayores) empieza a marcar tramos
    # someros como apnea (6/120) y con 0.40 llega a 25/120.
    irregularity: float = 0.20


class RespiratorySignalGenerator:
    """Generate realistic respiratory signals"""

    def __init__(self, sampling_rate: float = 100):
        """
        Initialize respiratory generator

        Args:
            sampling_rate: Samples per second
        """
        self.sampling_rate = sampling_rate
        self.sample_interval = 1.0 / sampling_rate

    # ------------------------------------------------------------------
    # Parametros efectivos, validacion y ground truth
    # ------------------------------------------------------------------
    @staticmethod
    def effective_params(params: RespiratoryPattern) -> RespiratoryPattern:
        """Parámetros con los que el generador respira de verdad. Taquipnea = FR x1.5 (tope 40) y
        bradipnea = FR x0.5 (piso 6), con volumen y tiempos escalados; el resto de patrones usa los
        parámetros tal cual. Única fuente de este escalado: lo usan la generación y el ground truth."""
        if params.pattern_type == "tachypnea":
            return RespiratoryPattern(
                respiratory_rate=min(params.respiratory_rate * 1.5, 40),  # Up to 40/min
                tidal_volume=params.tidal_volume * 0.6,  # Shallower
                inspiration_time=params.inspiration_time * 0.5,  # Faster
                expiration_time=None if params.expiration_time is None else params.expiration_time * 0.5,
            )
        if params.pattern_type == "bradypnea":
            return RespiratoryPattern(
                respiratory_rate=max(params.respiratory_rate * 0.5, 6),  # Down to 6/min
                tidal_volume=params.tidal_volume * 1.5,  # Deeper
                inspiration_time=params.inspiration_time * 1.5,  # Slower
                expiration_time=None if params.expiration_time is None else params.expiration_time * 1.5,
            )
        return params

    @staticmethod
    def _validate(params: RespiratoryPattern, eff: RespiratoryPattern, duration: float) -> None:
        """Rechaza combinaciones imposibles con un mensaje explícito (nunca una señal sin espiración)."""
        if not duration > 0:
            raise ImpossibleParameters(f"duration debe ser > 0 s (recibido {duration}).", "duration")
        if not eff.respiratory_rate > 0:
            raise ImpossibleParameters(f"respiratory_rate debe ser > 0 (recibido {eff.respiratory_rate}).", "respiratory_rate")
        if params.pattern_type != "ataxic":
            cycle = 60.0 / eff.respiratory_rate
            ctx = (f"patrón '{params.pattern_type}', FR efectiva {eff.respiratory_rate:g}/min "
                   f"(ciclo {cycle:.2f} s), inspiración efectiva {eff.inspiration_time:g} s")
            if not eff.inspiration_time > 0:
                raise ImpossibleParameters(f"inspiration_time debe ser > 0 ({ctx}).", "inspiration_time")
            if eff.inspiration_time >= cycle:
                raise ImpossibleParameters(
                    f"Parámetros imposibles: la inspiración ({eff.inspiration_time:g} s) no cabe en el ciclo "
                    f"({cycle:.2f} s) y no quedaría espiración ({ctx}). Baja el tiempo de inspiración o la FR.",
                    "inspiration_time",
                )
            if eff.expiration_time is not None:
                if not eff.expiration_time > 0:
                    raise ImpossibleParameters(f"expiration_time debe ser > 0 o None ({ctx}).", "expiration_time")
                if eff.inspiration_time + eff.expiration_time > cycle + 1e-9:
                    raise ImpossibleParameters(
                        f"Parámetros imposibles: inspiración ({eff.inspiration_time:g} s) + espiración "
                        f"({eff.expiration_time:g} s) superan el ciclo ({cycle:.2f} s) ({ctx}).",
                        "expiration_time",
                    )
        if params.pattern_type in ("apnea_central", "apnea_obstructive"):
            if not (params.apnea_duration > 0 and params.apnea_period > 0 and params.apnea_onset >= 0):
                raise ImpossibleParameters("apnea_duration y apnea_period deben ser > 0 y apnea_onset >= 0.", "apnea_duration")
            if params.apnea_onset + params.apnea_duration > params.apnea_period + 1e-9:
                raise ImpossibleParameters(
                    f"El evento de {params.apnea_duration:g} s que empieza en {params.apnea_onset:g} s no cabe en "
                    f"el periodo de {params.apnea_period:g} s: baja apnea_duration/apnea_onset o sube apnea_period.",
                    "apnea_duration",
                )
        if params.pattern_type == "cheyne_stokes":
            if params.apnea_duration < 10.0:
                raise ImpossibleParameters(
                    f"En Cheyne-Stokes cada valle es una apnea central: apnea_duration debe ser >= 10 s "
                    f"(recibido {params.apnea_duration:g}).", "apnea_duration")
            if params.cheyne_stokes_cycle <= params.apnea_duration:
                raise ImpossibleParameters(
                    f"El ciclo de Cheyne-Stokes ({params.cheyne_stokes_cycle:g} s) debe ser mayor que la apnea "
                    f"central de cada valle ({params.apnea_duration:g} s).", "cheyne_stokes_cycle")
        if not 5.0 <= params.circulation_delay <= 30.0:
            raise ImpossibleParameters(
                f"circulation_delay (Tc) debe estar entre 5 y 30 s (recibido {params.circulation_delay:g}).",
                "circulation_delay")
        if not (params.desaturation_rate > 0 and params.resaturation_rate > 0):
            raise ImpossibleParameters("desaturation_rate y resaturation_rate deben ser > 0 (%/s).", "desaturation_rate")
        if not params.desaturation_level < params.baseline_spo2:
            raise ImpossibleParameters(
                f"El piso de SpO2 ({params.desaturation_level:g} %) debe ser menor que la SpO2 basal "
                f"({params.baseline_spo2:g} %).", "desaturation_level")
        if params.pattern_type == "ataxic" and not 0.0 <= params.irregularity <= 1.0:
            raise ImpossibleParameters(
                f"irregularity (coeficiente de variación) debe estar entre 0 y 1 (recibido {params.irregularity:g}).",
                "irregularity")

    @classmethod
    def validate_parameters(cls, params: RespiratoryPattern, duration: float) -> None:
        """Comprobación pública (la UI la llama antes de generar para mostrar el error junto al control)."""
        cls._validate(params, cls.effective_params(params), duration)

    # -- calendario de eventos ----------------------------------------------------------------
    @staticmethod
    def _event_calendar(params: RespiratoryPattern) -> Optional[Tuple[float, float, float, str]]:
        """(inicio dentro del periodo, duración, periodo, tipo) de los eventos del patrón, o None."""
        if params.pattern_type == "apnea_central":
            return params.apnea_onset, params.apnea_duration, params.apnea_period, "central"
        if params.pattern_type == "apnea_obstructive":
            return params.apnea_onset, params.apnea_duration, params.apnea_period, "obstructive"
        if params.pattern_type == "cheyne_stokes":  # el valle de cada ciclo es una apnea central
            return (params.cheyne_stokes_cycle - params.apnea_duration, params.apnea_duration,
                    params.cheyne_stokes_cycle, "central")
        return None

    def _events(self, params: RespiratoryPattern, duration: float) -> List[Dict]:
        cal = self._event_calendar(params)
        if cal is None:
            return []
        onset, dur, period, kind = cal
        events = []
        k = 0
        while True:
            start = k * period + onset
            if start >= duration:
                break
            end = min(start + dur, duration)
            events.append({
                "start_s": float(start),
                "duration_s": float(end - start),
                "type": kind,
                "truncated": bool(end < start + dur),
                "origin": "calendario",
            })
            k += 1
        return events

    # -- anotación por regla (fase 4) ---------------------------------------------------------
    @staticmethod
    def _berry_baseline(crest_t: np.ndarray, crest_a: np.ndarray, t_a: float) -> Optional[float]:
        """Basal previa al instante `t_a` según Berry 2012 / Chicago, calculada de las amplitudes por respiración
        que el generador CONOCE: media de las respiraciones de los 120 s previos, o media de las 3 mayores si el
        patrón es inestable. None = no hay respiración previa (evento sin basal)."""
        amps = crest_a[(crest_t >= t_a - BASELINE_WINDOW_S) & (crest_t < t_a)]
        if len(amps) == 0:
            return None
        cv = float(np.std(amps) / np.mean(amps)) if len(amps) > 1 else 0.0
        if len(amps) > STABLE_BREATHS_TO_AVERAGE and cv > BASELINE_STABILITY_CV:
            return float(np.mean(np.sort(amps)[-STABLE_BREATHS_TO_AVERAGE:]))
        return float(np.mean(amps))

    def _crests_per_cycle(self, clean: np.ndarray, time: np.ndarray, cycle: float, insp_time: float):
        """(instante, amplitud) de la cresta inspiratoria de cada ciclo regular, leída de la señal limpia que el
        generador acaba de construir (antes del ruido). Un ciclo sin flujo no es una respiración: no se lista."""
        ts, amps = [], []
        for k in range(int(time[-1] / cycle) + 1):
            m = (time >= k * cycle) & (time < k * cycle + insp_time)
            if m.any() and clean[m].max() > 1e-12:
                ts.append(time[m][np.argmax(clean[m])])
                amps.append(clean[m].max())
        return np.array(ts), np.array(amps)

    def _annotate_events_by_rule(self, clean: np.ndarray, time: np.ndarray, crest_t: np.ndarray, crest_a: np.ndarray,
                                 calendar: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Anota los eventos que cumplen el criterio firmado (caída >= 90 % de la excursión respecto a la basal de
        Berry durante >= 10 s) aplicándolo a la señal LIMPIA y a las amplitudes por respiración de la construcción.
        Es el criterio, no el detector: no importa ni reutiliza código de `respiratory_analyzer`.

        Duración de un evento: el tramo contiguo en que la excursión queda por debajo del 10 % de la basal. Berry
        2012 §3.2 la define "desde el nadir previo a la primera respiración claramente reducida hasta el inicio de
        la primera que se aproxima a la basal"; esa frase no cuantifica 'claramente reducida' ni 'se aproxima', y
        el corte del 10 % la lleva al nivel de muestra: coincide con ella cuando el flujo cesa de golpe (todos los
        calendarios de apnea) y se desvía como mucho un ciclo respiratorio cuando decae gradualmente (las colas
        de Cheyne-Stokes).

        Eventos sin basal previa (ya en curso al inicio) no se anotan: van a la lista de no evaluables. Un evento
        que llega al final cuenta solo con >= 10 s dentro del registro y se marca `truncated`. `calendar` son las
        ventanas de flujo cero que el patrón pretendía; cada evento medido guarda la que contiene
        (`construction_*`), y si no contiene ninguna es "emergente"."""
        fs = self.sampling_rate
        n = len(clean)
        events: List[Dict] = []
        non_evaluable: List[Dict] = []
        if len(crest_a) == 0:
            return events, non_evaluable
        a_abs = np.abs(clean)
        candidates = a_abs < (1.0 - APNEA_DROP_FRACTION) * float(crest_a.max())  # superconjunto: la basal real es <= la mayor
        edges = np.diff(np.concatenate([[0], candidates.astype(np.int8), [0]]))
        for a, b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0]):
            if (b - a) / fs < APNEA_MIN_DURATION_S - 2.0:
                continue
            base = self._berry_baseline(crest_t, crest_a, a / fs) if a > 0 else None
            if base is None:
                non_evaluable.append({"start_s": float(time[a]), "duration_s": float((b - a) / fs),
                                      "reason": "ya en curso al inicio del registro (sin basal previa)"})
                continue
            # basal = la previa al tramo de baja excursión; cada tramo contiguo bajo el 10 % de ella es un evento
            # candidato (un tramo candidato puede contener varios)
            low = a_abs[a:b] < (1.0 - APNEA_DROP_FRACTION) * base
            edges = np.diff(np.concatenate([[0], low.astype(np.int8), [0]]))
            for r0, r1 in zip(np.where(edges == 1)[0], np.where(edges == -1)[0]):
                lo, hi = a + int(r0), a + int(r1) - 1
                dur = (hi + 1 - lo) / fs
                if dur < APNEA_MIN_DURATION_S:
                    continue
                start = float(time[lo])
                # Margen respecto al criterio, leído de la construcción: ¿alguna respiración somera DENTRO del evento
                # (sin contar 1 s en cada borde, donde la señal sube por definición) llega casi al 10 % de la basal?
                # ¿dura casi lo mínimo? Un evento así está al límite: el ruido de cualquier medición decide si se ve.
                interior = a_abs[lo + int(fs):hi + 1 - int(fs)]
                excursion_margin = 1.0 - float(interior.max()) / ((1.0 - APNEA_DROP_FRACTION) * base) if len(interior) else 1.0
                near_threshold = excursion_margin < NEAR_THRESHOLD_MARGIN or dur < APNEA_MIN_DURATION_S * (1.0 + NEAR_THRESHOLD_MARGIN)
                ev = {"start_s": start, "duration_s": float(dur), "type": "central", "truncated": bool(hi == n - 1),
                      "origin": "emergente", "baseline_amplitude": float(base),
                      "near_threshold": bool(near_threshold), "excursion_margin": float(excursion_margin)}
                window = next((c for c in calendar if c["start_s"] < start + dur and c["start_s"] + c["duration_s"] > start), None)
                if window is not None:
                    ev["origin"] = "calendario"
                    ev["construction_start_s"] = float(window["start_s"])
                    ev["construction_duration_s"] = float(window["duration_s"])
                events.append(ev)
        return events, non_evaluable

    # -- SpO2: curva del dedo por evento ----------------------------------------------------------
    @staticmethod
    def _spo2_event_curve(event: Dict, params: RespiratoryPattern) -> Dict:
        """Parámetros de la desaturación de un evento. El pulmón se desatura a `desaturation_rate` durante
        todo el evento (L = 0); el dedo lo ve con retardo Tc: empieza a caer en inicio + Tc, llega al nadir
        en fin + Tc y se recupera con rampa a `resaturation_rate`. El piso acota la profundidad."""
        base = float(params.baseline_spo2)
        floor = float(params.desaturation_level)
        t0, T = event["start_s"], event["duration_s"]
        depth = min(params.desaturation_rate * T, base - floor)
        t_on = t0 + params.circulation_delay
        t_nadir = t0 + T + params.circulation_delay
        return {
            "t_on": t_on,
            "t_nadir": t_nadir,
            "depth": depth,
            "t_recovered": t_nadir + depth / params.resaturation_rate,
            "nadir": base - depth,
        }

    def _ground_truth(self, params: RespiratoryPattern, eff: RespiratoryPattern, duration: float,
                      seed: Optional[int], events: List[Dict], schedule: Optional[Dict] = None,
                      non_evaluable: Optional[List[Dict]] = None) -> Dict:
        """Lo que la señal contiene REALMENTE, calculado de los mismos parámetros que la generan."""
        pattern = params.pattern_type if params.pattern_type in KNOWN_PATTERNS else "normal"
        out_events = []
        for ev in events:
            c = self._spo2_event_curve(ev, params)
            out_events.append({
                **ev,
                "spo2_nadir_time_s": float(c["t_nadir"]),
                "spo2_depth_points": float(c["depth"]),
                "spo2_nadir": float(c["nadir"]),
                "spo2_recovered_time_s": float(c["t_recovered"]),
            })
        gt = {
            "pattern": pattern,
            "requested_pattern": params.pattern_type,
            "requested_respiratory_rate": float(params.respiratory_rate),
            "effective_respiratory_rate": float(eff.respiratory_rate),
            "rate_is_regular": True,
            "events": out_events,
            # eventos en curso al inicio del registro (sin basal previa): no cuentan, igual que en el criterio firmado
            "non_evaluable_events": list(non_evaluable or []),
            "event_rule": {
                "criterion": "caída >= 90 % de la excursión respecto a la basal previa (Berry 2012) durante >= 10 s",
                "drop_fraction": APNEA_DROP_FRACTION,
                "min_duration_s": APNEA_MIN_DURATION_S,
                "baseline": "Berry 2012 / Chicago: media de las respiraciones de los 120 s previos, o de las 3 mayores si es inestable",
                "origins": {"calendario": "ventana pedida por el patrón", "emergente": "nacido del azar de cada respiración"},
            },
            "modulation_period_s": float(params.cheyne_stokes_cycle) if pattern == "cheyne_stokes" else None,
            "duration_s": float(duration),
            "sampling_rate_hz": float(self.sampling_rate),
            "seed": seed,
            "airflow_units": AIRFLOW_UNITS,
            # Modelo de SpO2 de la fase 2b: función determinista de los eventos anotados.
            "spo2": {
                "model": "BIOCORE_event_model_2b",
                "baseline": float(params.baseline_spo2),
                "floor": float(params.desaturation_level),
                "circulation_delay_s": float(params.circulation_delay),
                "desaturation_rate_pct_s": float(params.desaturation_rate),
                "resaturation_rate_pct_s": float(params.resaturation_rate),
                "buffer_latency_modeled": False,
                "sources": dict(SPO2_MODEL_SOURCES),
            },
        }
        if schedule is not None:  # atáxica: respiración a respiración
            onsets = schedule["onsets"]
            onsets = onsets[onsets < duration]
            intervals = np.diff(onsets)
            gt["breath_onsets_s"] = [float(t) for t in onsets]
            if len(intervals) >= 2:
                gt["effective_respiratory_rate"] = float(60.0 / np.mean(intervals))
                gt["cycle_cv"] = float(np.std(intervals, ddof=1) / np.mean(intervals))
            gt["rate_is_regular"] = bool(params.irregularity == 0.0)
            gt["irregularity"] = float(params.irregularity)
            gt["irregularity_label"] = "HEURISTIC"
        return gt

    @staticmethod
    def _event_window(phase: np.ndarray, onset: float, duration: float, period: float) -> np.ndarray:
        """Máscara de las muestras dentro de un evento. Con los valores por defecto de las apneas la
        aritmética es la histórica (fase >= 40/60 y fase < 60/60 = 1.0, siempre verdadera)."""
        onset_phase = onset / period
        end_phase = (onset + duration) / period
        return (phase >= onset_phase) & (phase < end_phase)

    @staticmethod
    def _expiration_fraction(params: RespiratoryPattern, cycle_duration: float) -> Optional[float]:
        return None if params.expiration_time is None else params.expiration_time / cycle_duration

    def generate_respiration(
        self,
        duration: float = 60.0,
        params: RespiratoryPattern = None,
        seed: Optional[int] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Generate complete respiratory waveform

        Args:
            duration: Recording length in seconds
            params: Respiratory parameters
            seed: semilla del ruido (misma semilla -> misma señal bit a bit). None = no reproducible.

        Returns:
            Dictionary with signals:
            {
                'airflow': array,  # L/min (escala del generador, ver AIRFLOW_UNITS)
                'chest_wall': array,  # Strain gauge (dimensionless)
                'abdomen': array,  # Abdominal movement
                'spo2': array,  # Oxygen saturation (%), modelo de eventos de la fase 2b
                'time': array,
                'ground_truth': dict  # FR efectiva, eventos (inicio, duración, tipo), patrón
            }
        """
        if params is None:
            params = RespiratoryPattern()

        eff = self.effective_params(params)
        self._validate(params, eff, duration)

        rng = np.random.default_rng(seed)
        n_samples = int(duration * self.sampling_rate)
        time = np.arange(n_samples) * self.sample_interval

        events = self._events(params, duration)  # calendario de los patrones de apnea
        non_evaluable: List[Dict] = []
        schedule = None

        # Generate base respiratory pattern
        if params.pattern_type == "normal":
            airflow, chest, abdomen = self._generate_normal_respiration(time, params)
        elif params.pattern_type == "tachypnea":
            airflow, chest, abdomen = self._generate_tachypnea(time, params)
        elif params.pattern_type == "bradypnea":
            airflow, chest, abdomen = self._generate_bradypnea(time, params)
        elif params.pattern_type == "apnea_central":
            airflow, chest, abdomen = self._generate_central_apnea(time, params)
        elif params.pattern_type == "apnea_obstructive":
            airflow, chest, abdomen = self._generate_obstructive_apnea(time, params)
        elif params.pattern_type == "cheyne_stokes":
            airflow, chest, abdomen = self._generate_cheyne_stokes(time, params)
            # los bordes de cada valle se miden con la regla firmada, no con la ventana de flujo cero que se pidió
            crest_t, crest_a = self._crests_per_cycle(airflow, time, 60.0 / params.respiratory_rate, params.inspiration_time)
            events, non_evaluable = self._annotate_events_by_rule(airflow, time, crest_t, crest_a, calendar=events)
            # Fase 4.1: un evento CENTRAL tiene el esfuerzo ausente durante TODO el evento (no solo en la ventana de
            # flujo cero): en las colas que añade la regla el esfuerzo (seno con otra fase que el flujo) llegaba al 16 %
            # de su basal y el detector lo leía 'mixta'. El flujo no cambia (el evento se midió con él); cambian tórax y
            # abdomen dentro de cada evento anotado.
            for ev in events:
                inside = (time >= ev["start_s"]) & (time < ev["start_s"] + ev["duration_s"])
                chest[inside] = 0.0
                abdomen[inside] = 0.0
                ev["effort"] = "ausente en todo el evento (construcción)"
        elif params.pattern_type == "ataxic":
            schedule = self._ataxic_schedule(duration, params, rng)
            airflow, chest, abdomen = self._generate_ataxic_respiration(time, params, schedule)
            # las apneas de la atáxica son EMERGENTES (nacen del azar de cada respiración): se anotan con la regla,
            # a partir de la amplitud por respiración que el generador sorteó, para no penalizar al estudiante
            mean_cycle = 60.0 / params.respiratory_rate
            insp_fraction = min(params.inspiration_time / mean_cycle, 0.9)
            crest_t = schedule["onsets"] + schedule["cycles"] * insp_fraction / 2.0
            crest_a = params.tidal_volume * schedule["depths"] * 60.0 / schedule["cycles"]
            inside = crest_t < duration
            events, non_evaluable = self._annotate_events_by_rule(
                airflow, time, crest_t[inside], crest_a[inside], calendar=[])
        else:
            airflow, chest, abdomen = self._generate_normal_respiration(time, params)

        # Generate SpO2 from the annotated events (not from the airflow)
        spo2 = self._generate_spo2(time, params, events, rng)

        # Add noise to signals
        airflow += rng.normal(0, 0.02, n_samples)
        chest += rng.normal(0, 0.01, n_samples)
        abdomen += rng.normal(0, 0.01, n_samples)

        result = {
            'airflow': airflow,  # Primary respiratory signal
            'chest_wall': chest,  # Thoracic movement
            'abdomen': abdomen,  # Abdominal movement
            'spo2': spo2,  # Pulse oximetry
            'time': time,
            'ground_truth': self._ground_truth(params, eff, duration, seed, events, schedule, non_evaluable),
        }

        return result

    def _generate_normal_respiration(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate normal quiet breathing (tidal breathing)"""

        airflow = np.zeros_like(time)
        chest = np.zeros_like(time)
        abdomen = np.zeros_like(time)

        # Calculate breathing cycle duration
        cycle_duration = 60.0 / params.respiratory_rate

        # Generate cycles
        cycles = time / cycle_duration
        phase = np.mod(cycles, 1.0)

        # Inspiration phase (0 to inspiration_fraction)
        inspiration_fraction = params.inspiration_time / cycle_duration
        exp_fraction = self._expiration_fraction(params, cycle_duration)

        # Generate sinusoidal airflow (positive during inspiration, negative during expiration)
        inspiration_mask = phase < inspiration_fraction
        expiration_mask = ~inspiration_mask
        if exp_fraction is not None:  # espiración acotada: el resto del ciclo es pausa telespiratoria (flujo 0)
            expiration_mask = expiration_mask & (phase < inspiration_fraction + exp_fraction)

        # Inspiration: gradual increase then decrease
        inspiration_phase = phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume *
            np.sin(inspiration_phase * np.pi) *
            (60.0 / cycle_duration)  # Convert to breaths/min scale
        )

        # Expiration: slower, longer phase
        exp_span = (1.0 - inspiration_fraction) if exp_fraction is None else exp_fraction
        expiration_phase = (phase[expiration_mask] - inspiration_fraction) / exp_span
        airflow[expiration_mask] = (
            -params.tidal_volume *
            0.5 *
            np.sin(expiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        # Chest wall movement (primarily ribcage)
        chest = np.sin(2 * np.pi * cycles) * params.tidal_volume

        # Abdominal movement (primarily diaphragm)
        abdomen = 1.2 * chest  # Slightly larger amplitude

        return airflow, chest, abdomen

    def _generate_tachypnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate tachypnea (fast, shallow breathing)"""
        return self._generate_normal_respiration(time, self.effective_params(params))

    def _generate_bradypnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate bradypnea (slow, deep breathing)"""
        return self._generate_normal_respiration(time, self.effective_params(params))

    def _generate_central_apnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Central Sleep Apnea
        - Complete cessation of airflow AND respiratory effort
        - No chest wall or abdominal movement during apnea
        """
        airflow = np.zeros_like(time)
        chest = np.zeros_like(time)
        abdomen = np.zeros_like(time)

        # Baseline breathing interrupted by apneas
        baseline_rr = params.respiratory_rate
        cycle_duration = 60.0 / baseline_rr
        apnea_cycle = params.apnea_period  # 60 s por defecto

        cycles = time / cycle_duration
        apnea_events = time / apnea_cycle
        phase_in_apnea_cycle = np.mod(apnea_events, 1.0)

        # Create breathing pattern
        base_phase = np.mod(cycles, 1.0)
        inspiration_fraction = params.inspiration_time / cycle_duration
        exp_fraction = self._expiration_fraction(params, cycle_duration)

        # Identify apnea windows (por defecto, los últimos 20 s de cada ciclo de 60 s)
        in_apnea = self._event_window(phase_in_apnea_cycle, params.apnea_onset, params.apnea_duration, apnea_cycle)

        # Generate breathing outside apnea
        breathing_mask = ~in_apnea
        inspiration_mask = (base_phase < inspiration_fraction) & breathing_mask
        expiration_mask = (base_phase >= inspiration_fraction) & breathing_mask
        if exp_fraction is not None:
            expiration_mask = expiration_mask & (base_phase < inspiration_fraction + exp_fraction)

        inspiration_phase = base_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume *
            np.sin(inspiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        exp_span = (1.0 - inspiration_fraction) if exp_fraction is None else exp_fraction
        expiration_phase = (base_phase[expiration_mask] - inspiration_fraction) / exp_span
        airflow[expiration_mask] = (
            -params.tidal_volume *
            0.5 *
            np.sin(expiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        # Chest and abdomen also stop during apnea (key feature of central apnea)
        chest = np.sin(2 * np.pi * cycles) * params.tidal_volume
        chest[in_apnea] = 0  # No movement during apnea

        abdomen = 1.2 * chest

        return airflow, chest, abdomen

    def _generate_obstructive_apnea(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Obstructive Sleep Apnea
        - NO airflow but PERSISTENT respiratory effort (chest/abdominal movement)
        - Key difference from central apnea
        """
        airflow = np.zeros_like(time)
        chest = np.zeros_like(time)
        abdomen = np.zeros_like(time)

        # Baseline breathing interrupted by obstructions
        cycle_duration = 60.0 / params.respiratory_rate
        apnea_cycle = params.apnea_period  # 60 s por defecto

        cycles = time / cycle_duration
        apnea_events = time / apnea_cycle
        phase_in_apnea_cycle = np.mod(apnea_events, 1.0)

        base_phase = np.mod(cycles, 1.0)
        inspiration_fraction = params.inspiration_time / cycle_duration
        exp_fraction = self._expiration_fraction(params, cycle_duration)

        # Identify obstruction windows
        in_obstruction = self._event_window(phase_in_apnea_cycle, params.apnea_onset, params.apnea_duration, apnea_cycle)

        # Generate airflow (normal breathing outside obstruction)
        breathing_mask = ~in_obstruction
        inspiration_mask = (base_phase < inspiration_fraction) & breathing_mask
        expiration_mask = (base_phase >= inspiration_fraction) & breathing_mask
        if exp_fraction is not None:
            expiration_mask = expiration_mask & (base_phase < inspiration_fraction + exp_fraction)

        inspiration_phase = base_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            params.tidal_volume *
            np.sin(inspiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        exp_span = (1.0 - inspiration_fraction) if exp_fraction is None else exp_fraction
        expiration_phase = (base_phase[expiration_mask] - inspiration_fraction) / exp_span
        airflow[expiration_mask] = (
            -params.tidal_volume *
            0.5 *
            np.sin(expiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        # Airflow goes to zero during obstruction but effort continues!
        airflow[in_obstruction] = 0

        # Key feature: chest and abdomen continue to move (paradoxical movement)
        chest = np.sin(2 * np.pi * cycles) * params.tidal_volume
        abdomen = 1.2 * chest

        # During obstruction, movements may become paradoxical
        abdomen[in_obstruction] *= -0.5  # Inward during obstruction attempt

        return airflow, chest, abdomen

    def _generate_cheyne_stokes(
        self,
        time: np.ndarray,
        params: RespiratoryPattern
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Cheyne-Stokes respiration
        - Periodic breathing: progressive increase then decrease in depth
        - Cycle length 40-90 s (Berry 2012 / AASM: >= 40 s, tipicamente 45-90 s)
        - Common in heart failure, CNS disease

        Fase 2b: cada valle es una APNEA CENTRAL (flujo y esfuerzo ausentes durante `apnea_duration`),
        anotada en el ground truth. El ciclo es: crescendo-decrescendo (ciclo - apnea_duration) y apnea.
        """
        airflow = np.zeros_like(time)
        chest = np.zeros_like(time)
        abdomen = np.zeros_like(time)

        cycle_duration = 60.0 / params.respiratory_rate
        cheyne_stokes_period = params.cheyne_stokes_cycle
        hyperpnea_len = cheyne_stokes_period - params.apnea_duration

        # Position within Cheyne-Stokes cycle
        cs_cycles = time / cheyne_stokes_period
        cs_phase = np.mod(cs_cycles, 1.0)
        in_apnea = self._event_window(cs_phase, hyperpnea_len, params.apnea_duration, cheyne_stokes_period)

        # Modulation: gradual increase then decrease in amplitude, dentro de la fase de hiperpnea
        # First half: amplitude increases (crescendo); second half: decreases (decrescendo); apnea: 0
        u = np.where(in_apnea, 0.0, (cs_phase * cheyne_stokes_period) / hyperpnea_len)
        amplitude_mod = np.where(in_apnea, 0.0, 1.0 - np.abs(2.0 * u - 1.0))

        # Regular breathing cycles but with varying amplitude
        breathing_cycles = time / cycle_duration
        breathing_phase = np.mod(breathing_cycles, 1.0)
        inspiration_fraction = params.inspiration_time / cycle_duration
        exp_fraction = self._expiration_fraction(params, cycle_duration)

        # Generate modulated breathing
        inspiration_mask = breathing_phase < inspiration_fraction
        expiration_mask = ~inspiration_mask
        if exp_fraction is not None:
            expiration_mask = expiration_mask & (breathing_phase < inspiration_fraction + exp_fraction)

        inspiration_phase = breathing_phase[inspiration_mask] / inspiration_fraction
        airflow[inspiration_mask] = (
            amplitude_mod[inspiration_mask] *
            params.tidal_volume *
            np.sin(inspiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        exp_span = (1.0 - inspiration_fraction) if exp_fraction is None else exp_fraction
        expiration_phase = (breathing_phase[expiration_mask] - inspiration_fraction) / exp_span
        airflow[expiration_mask] = (
            -amplitude_mod[expiration_mask] *
            params.tidal_volume *
            0.5 *
            np.sin(expiration_phase * np.pi) *
            (60.0 / cycle_duration)
        )

        airflow[in_apnea] = 0.0
        chest = amplitude_mod * np.sin(2 * np.pi * breathing_cycles) * params.tidal_volume  # esfuerzo ausente en la apnea
        abdomen = amplitude_mod * 1.2 * chest

        return airflow, chest, abdomen

    @staticmethod
    def _lognormal(rng: np.random.Generator, mean: float, cv: float, size: int) -> np.ndarray:
        """Muestras lognormales con media `mean` y coeficiente de variación `cv`."""
        sigma2 = np.log1p(cv * cv)
        return np.exp(rng.normal(np.log(mean) - sigma2 / 2.0, np.sqrt(sigma2), size))

    def _ataxic_schedule(self, duration: float, params: RespiratoryPattern, rng: np.random.Generator) -> Dict:
        """Respiración a respiración: duración y profundidad aleatorias (CV = `irregularity`, HEURISTIC)."""
        mean_cycle = 60.0 / params.respiratory_rate
        n = int(duration / (0.4 * mean_cycle)) + 8  # holgura: ciclo mínimo 1.2 s
        cycles = self._lognormal(rng, mean_cycle, params.irregularity, n)
        cycles = np.clip(cycles, 1.2, 4.0 * mean_cycle)
        depths = np.clip(self._lognormal(rng, 1.0, params.irregularity, n), 0.2, 3.0)
        onsets = np.concatenate([[0.0], np.cumsum(cycles)])[:-1]
        return {"onsets": onsets, "cycles": cycles, "depths": depths}

    def _generate_ataxic_respiration(
        self,
        time: np.ndarray,
        params: RespiratoryPattern,
        schedule: Dict,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate Ataxic respiration (Biot breathing)
        - Completely irregular breathing pattern
        - Variable depth and frequency
        - Associated with brainstem injury

        Fase 2b: cada respiración tiene su propia duración y profundidad (antes solo variaba la amplitud
        de una portadora a frecuencia fija). La forma de cada respiración es la de la respiración normal;
        la fracción inspiratoria se mantiene (inspiración / ciclo medio).
        """
        onsets, cycles, depths = schedule["onsets"], schedule["cycles"], schedule["depths"]
        idx = np.clip(np.searchsorted(onsets, time, side="right") - 1, 0, len(onsets) - 1)
        cyc = cycles[idx]
        phase = (time - onsets[idx]) / cyc
        mean_cycle = 60.0 / params.respiratory_rate
        insp_fraction = min(params.inspiration_time / mean_cycle, 0.9)

        airflow = np.zeros_like(time)
        amp = params.tidal_volume * depths[idx] * (60.0 / cyc)
        insp = phase < insp_fraction
        airflow[insp] = amp[insp] * np.sin(phase[insp] / insp_fraction * np.pi)
        exp_ = ~insp
        airflow[exp_] = -0.5 * amp[exp_] * np.sin((phase[exp_] - insp_fraction) / (1.0 - insp_fraction) * np.pi)

        chest = airflow * 0.8
        abdomen = airflow * 1.1

        return airflow, chest, abdomen

    def _generate_spo2(
        self,
        time: np.ndarray,
        params: RespiratoryPattern,
        events: List[Dict],
        rng: np.random.Generator,
    ) -> np.ndarray:
        """
        Generate SpO2 (oxygen saturation) from the annotated respiratory events (fase 2b).

        Sin eventos la SpO2 es la basal más ruido de oxímetro (sd 0.5; valor heredado, sin fuente).
        Cada evento (apnea) produce en el dedo: caída lineal a `desaturation_rate` desde inicio + Tc
        (Tc = `circulation_delay`) hasta el nadir en fin + Tc, y recuperación en rampa a `resaturation_rate`
        constante desde el nadir (su duración resulta de la profundidad). `desaturation_level` es el piso.
        La latencia de las reservas de O2 (L) no se modela. Eventos solapados se combinan por máximo.
        """
        base = float(params.baseline_spo2)
        deficit = np.zeros_like(time)
        for ev in events:
            c = self._spo2_event_curve(ev, params)
            if c["depth"] <= 0:
                continue
            fall = (time >= c["t_on"]) & (time < c["t_nadir"])
            rec = (time >= c["t_nadir"]) & (time < c["t_recovered"])
            d = np.zeros_like(time)
            d[fall] = np.minimum(params.desaturation_rate * (time[fall] - c["t_on"]), c["depth"])
            d[time >= c["t_nadir"]] = c["depth"]
            d[rec] = c["depth"] - params.resaturation_rate * (time[rec] - c["t_nadir"])
            d[time >= c["t_recovered"]] = 0.0
            deficit = np.maximum(deficit, d)

        spo2 = base - deficit

        # Add realistic noise (pulse oximetry noise); el piso acota la señal
        spo2 = spo2 + rng.normal(0, 0.5, len(spo2))
        spo2 = np.clip(spo2, max(50.0, params.desaturation_level), 100)

        return spo2


def demo_respiratory_patterns():
    """Demonstrate all respiratory patterns"""

    print("╔════════════════════════════════════════════════════════════╗")
    print("║        RESPIRATORY SIGNAL GENERATOR - DEMONSTRATION        ║")
    print("╚════════════════════════════════════════════════════════════╝\n")

    generator = RespiratorySignalGenerator(sampling_rate=100)

    patterns = [
        ("Normal", "normal"),
        ("Tachypnea", "tachypnea"),
        ("Bradypnea", "bradypnea"),
        ("Central Apnea", "apnea_central"),
        ("Obstructive Apnea", "apnea_obstructive"),
        ("Cheyne-Stokes", "cheyne_stokes"),
        ("Ataxic", "ataxic"),
    ]

    for name, pattern_type in patterns:
        params = RespiratoryPattern(
            respiratory_rate=15,
            tidal_volume=0.5,
            pattern_type=pattern_type
        )

        respiration = generator.generate_respiration(duration=30, params=params)

        # Calculate metrics
        airflow = respiration['airflow']
        spo2 = respiration['spo2']

        print(f"✅ {name.upper()}")
        print(f"   - Airflow range: {np.min(airflow):.2f} to {np.max(airflow):.2f} L/min")
        print(f"   - SpO2 range: {np.min(spo2):.1f}% to {np.max(spo2):.1f}%")
        print(f"   - Samples: {len(airflow)}\n")

    print("✅ Respiratory pattern generation completed successfully!")


if __name__ == "__main__":
    demo_respiratory_patterns()
