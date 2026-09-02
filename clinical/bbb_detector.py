"""Detector morfológico de Bloqueo de Rama (RBBB/LBBB) -- Detector BBB, Fase 3
(2026-08-12).

Junta las piezas de apoyo ya construidas y aisladas:
- El delineador de QRS de la Sub-Fase 2.5 (`clinical/qrs_delineation.py::
  delineate_qrs`) -- NUNCA `ECGAnalyzer.segment_qrs_complex()` (el método
  viejo, auditado y descartado para este propósito en esa sub-fase: amputa
  QRS anchos y no puede reportar "no hay Q").
- Un buscador de latido de referencia LOCAL a este módulo
  (`_detect_reference_peaks()`/`_reference_r_peak_idx()`) -- NO
  `ECGAnalyzer.detect_r_peaks()` (sin tocar, compartido por el resto de la
  app): ese método solo ve picos POSITIVOS, incapaz de localizar un QRS
  predominantemente negativo -- justo el patrón QS/rS que este detector
  necesita reconocer en V1 para LBBB. Ver la sección de decisiones de
  implementación más abajo para el hallazgo real que motivó esto.

CRITERIO VERBATIM DEL VALIDADOR (firma: validador clínico, Detector BBB,
Fase 3, aprobación 2026-08-12) -- umbrales exactos, sin ajuste:

- Umbral de disparo: QRS > 120 ms (reutiliza el umbral ya existente de
  `ECGAnalyzer.detect_clinical_pattern`).
- RBBB, dos morfologías válidas -- CUALQUIERA de las dos (con su propia
  salvaguarda V6, cada una AMBOS obligatorios):
    A. RSR' clásico:
       1. R' en V1 con prominencia >=0.1 mV sobre el nadir precedente Y
          siendo la deflexión terminal/dominante.
       2. S en V6 con duración >=40 ms y amplitud <=-0.1 mV, polaridad
          final negativa.
    B. qR atípico (firma: validador clínico, Detector BBB, Fase 4,
       aprobación 2026-08-12 -- fuente citada: Chou's Electrocardiography
       in Clinical Practice / Marriott's Practical Electrocardiography):
       1. En V1: deflexión negativa inicial q (<=-0.1 mV) + R única
          prominente (>=0.5 mV) + SIN S posterior (nada negativo sigue a
          la R).
       2. Salvaguarda V6 OBLIGATORIA (AND, más estricta que la del RSR'
          clásico): S ancha en V6, duración >=40 ms Y amplitud <=-0.15 mV.
          Sin esta S en V6, el patrón qR de V1 NO basta -> indeterminado.
          Esta salvaguarda es lo que distingue un qR de RBBB genuino de un
          qR por infarto/necrosis septal u otro trastorno de conducción con
          V6 atípico -- nunca se relaja para "rescatar" un caso.
  (RSR' en V1 sin S ancha en V6 -> NO es RBBB confirmado -> indeterminado.
  qR en V1 sin la salvaguarda V6 -> tampoco -> indeterminado. Ninguna de
  las dos morfologías, sola, sin su V6 correspondiente, confirma RBBB.)
- LBBB, AMBOS obligatorios:
    1. QS o rS (r muy pequeña) en V1.
    2. R ancha/muescada en V6 SIN Q septal (ninguna deflexión inicial
       < -0.05 mV).
- Indeterminado/IVCD: cualquier QRS>120ms que no cumpla los criterios duros
  de ninguna rama -- NUNCA se fuerza L o R (conflicto entre derivaciones,
  amplitud insuficiente, morfología ambigua -> indeterminado).

DECISIONES DE IMPLEMENTACIÓN -- no dictadas por el validador, documentadas
explícitamente aquí (mismo patrón que la ambigüedad ya resuelta y anotada en
`qrs_delineation._isoelectric_baseline`, para no confundir "cita clínica"
con "elección de ingeniería"):

- "R' con prominencia >=0.1 mV" ya viene garantizado por el propio
  delineador (`SUBPEAK_MIN_PROMINENCE_MV=0.1` en `qrs_delineation.py`) --
  cualquier R' que `delineate_qrs()` reporte ya cumple ese piso; no se
  vuelve a medir aquí.
- "Terminal/dominante" (R') se interpreta como: es la última deflexión del
  complejo (`peaks[-1]`) Y su amplitud absoluta es >= la de R.
- "Duración de S" se mide por CRUCE DE CERO (no del baseline isoeléctrico
  del delineador, que es local y puede no ser exactamente 0) desde el pico
  R hasta el fin de la ventana de QRS -- el validador dio el umbral clínico
  (40 ms / -0.1 mV) pero no el método de medición operacional.
- La UBICACIÓN del latido de referencia NO usa `ECGAnalyzer.detect_r_peaks()`
  -- ese método busca picos únicamente por ENCIMA de un umbral POSITIVO
  (`mean+0.3*std`), lo cual no puede ver un QRS predominantemente NEGATIVO.
  Confirmado contra datos reales (Fase 3, 2026-08-12): sobre V1 en las 25
  LBBB confirmadas, el QRS real es una deflexión negativa profunda (p.ej.
  -2.7 mV en un caso verificado) -- exactamente el patrón QS que este
  detector necesita reconocer -- pero `detect_r_peaks()` no la ve nunca;
  ancla ~200ms más tarde, en la onda T (positiva, ~300ms de ancho, mucho
  más ancha que cualquier QRS real), y el delineador termina delineando la
  onda T pensando que es el QRS. Este módulo usa en su lugar un buscador
  LOCAL por amplitud ABSOLUTA (`_detect_reference_peaks()`, sobre
  `abs(señal)`) -- no se modifica `ECGAnalyzer.detect_r_peaks()` (compartido
  por el resto de la app, fuera de alcance).
- **Sincronización V1/V6 al MISMO latido** (corrección de plomería,
  2026-08-12, posterior a la integración inicial de esta fase -- ver
  CHANGELOG.md): la primera versión de este módulo llamaba al buscador de
  latido POR DERIVACIÓN, independientemente para V1 y para V6. Auditoría de
  los 12 casos RBBB reales que no cruzaban el umbral de 120ms encontró que,
  en los 50/50 casos de validación, el latido elegido en V1 y el elegido en
  V6 caían en puntos del registro separados entre 262ms y 5368ms -- nunca
  el mismo complejo, a veces ni siquiera latidos consecutivos. El criterio
  de RBBB ("R' en V1 Y S ancha en V6") describe DOS VISTAS DEL MISMO
  COMPLEJO, no dos latidos distintos -- comparar latidos diferentes invalida
  la premisa del criterio y además subestima el ancho de QRS medido (la
  investigación de re-medición manual confirmó QRS real >=120ms en 9 de los
  12 casos "narrow", contra el ancla independiente por derivación).
  `detect_bundle_branch_block()` ahora elige UN latido compartido
  (`_select_reference_beat()`, ver su docstring para el criterio completo de
  selección) y delinea V1 Y V6 en la MISMA ventana temporal -- mismo
  instante cardíaco, medido en cada derivación. El delineador de la
  Sub-Fase 2.5 (`delineate_qrs()`) no cambia -- solo el índice que se le
  pasa para cada derivación.
- "Dominante" en V1 (LBBB) / V6 (RBBB, sub-check no exigido explícitamente
  pero usado para localizar R) se interpreta como la deflexión de mayor
  amplitud ABSOLUTA del complejo.
- **Criterio qR (Fase 4, 2026-08-12)** -- decisiones de implementación NO
  dictadas por el validador:
    - "R única" se interpreta como EXACTAMENTE una deflexión positiva en
      el complejo (`_positive_peaks_in_order()` de longitud 1) -- si hay
      una segunda deflexión positiva, es candidata a R' y el patrón es
      RSR' (morfología A), no qR.
    - "Sin S posterior" se interpreta como: la R es la última deflexión
      del complejo (`delineation.peaks[-1]`) -- nada negativo la sigue.
    - "q inicial" se interpreta como la deflexión INMEDIATAMENTE anterior
      a la R (`delineation.peaks[-2]`, dado que la R ya es la última) --
      debe existir (si la R es la ÚNICA deflexión del complejo, sin nada
      antes, no hay q que medir, y el patrón NO cumple qR: es "R sola",
      una morfología distinta, no mencionada por el validador. Confirmado
      contra datos reales, Fase 4: 2 de los 6 casos que el inventario
      previo esperaba rescatar -- `ecg_id=826`/`1066` -- resultan ser
      exactamente esto: el trazo sube limpio desde el baseline plano hasta
      la R sin ningún descenso previo medible, verificado visualmente
      sobre la señal cruda. No se relajó el criterio para incluirlos --
      ver CHANGELOG.md para el detalle completo de esta discrepancia.
    - La salvaguarda V6 del qR reutiliza `_check_rbbb_v6()` (misma lógica
      de par R/S, misma medición de duración por cruce de cero) con un
      umbral de amplitud distinto y más estricto (`RBBB_QR_V6_S_MAX_
      AMPLITUDE_MV=-0.15` en vez de `RBBB_S_V6_MAX_AMPLITUDE_MV=-0.1`) --
      parametrizado, no duplicado.

AISLADO hasta esta fase: antes de esta tanda, ningún call site de
`ECGAnalyzer.detect_clinical_pattern()` pasaba V1/V6 -- la bifurcación se
integra en esta misma tanda (ver CHANGELOG.md)."""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.signal import find_peaks

from .qrs_delineation import QrsDelineation, delineate_qrs

QRS_WIDE_THRESHOLD_MS: float = 120.0
RBBB_S_V6_MIN_DURATION_MS: float = 40.0
RBBB_S_V6_MAX_AMPLITUDE_MV: float = -0.1
LBBB_SEPTAL_Q_MAX_AMPLITUDE_MV: float = -0.05

# --- Criterio qR atípico (Fase 4, 2026-08-12) -------------------------------
# Firma: validador clínico, Detector BBB, Fase 4, aprobación 2026-08-12.
# Fuente citada: Chou's Electrocardiography in Clinical Practice / Marriott's
# Practical Electrocardiography -- el patrón qR en V1 (sin el notch RSR'
# clásico) es una morfología de RBBB reconocida, distinta del RSR' pero con
# la MISMA exigencia de S ancha en V6 como salvaguarda -- lo que la separa de
# un qR por infarto/necrosis septal u otro trastorno de conducción con V6
# atípico. Umbrales verbatim, sin ajuste.
RBBB_QR_INITIAL_Q_MAX_AMPLITUDE_MV: float = -0.1
RBBB_QR_R_MIN_AMPLITUDE_MV: float = 0.5
RBBB_QR_V6_S_MIN_DURATION_MS: float = 40.0
RBBB_QR_V6_S_MAX_AMPLITUDE_MV: float = -0.15

INDETERMINATE_LABEL = "Bloqueo de rama indeterminado"


@dataclasses.dataclass(frozen=True)
class BbbMorphologyResult:
    """`pattern` es `None` cuando el propio delineador mide QRS<=120ms (o no
    encuentra un latido válido) -- en ese caso el llamador NO debe tratarlo
    como "no BBB" definitivo si otro método (p.ej. `measure_intervals()`
    sobre otra derivación) sí superó el umbral; debe caer al genérico, no
    afirmar normalidad que este detector no midió."""

    pattern: Optional[str]
    qrs_duration_ms: float
    reasoning: List[str]


def _dominant_peak(peaks: List[Dict]) -> Optional[Dict]:
    return max(peaks, key=lambda p: abs(p["amplitude"])) if peaks else None


def _detect_reference_peaks(signal: np.ndarray, fs: float) -> np.ndarray:
    """Picos de referencia por amplitud ABSOLUTA -- ve un QRS
    predominantemente negativo (p.ej. el patrón QS de LBBB en V1), a
    diferencia de `ECGAnalyzer.detect_r_peaks()` (umbral solo positivo, ver
    nota de procedencia en el docstring del módulo). Local a este módulo --
    no reemplaza ni modifica `detect_r_peaks()`."""
    abs_signal = np.abs(signal)
    threshold = np.mean(abs_signal) + 0.3 * np.std(abs_signal)
    peaks, _ = find_peaks(abs_signal, distance=int(0.3 * fs), height=threshold)
    return peaks


REFERENCE_BEAT_RR_TOLERANCE: float = 0.25
"""Un latido cuyo hueco RR (al vecino anterior O al siguiente) se desvía más
de este porcentaje de la mediana de RR del registro se considera sospechoso
de latido ectópico (p.ej. una PVC) o artefacto puntual, y se descarta como
candidato a latido de referencia compartido -- ver `_select_reference_beat()`.
25% es una elección de este módulo (no una cita clínica): suficientemente
laxo para no descartar variabilidad sinusal normal, suficientemente
estricto para excluir el acoplamiento corto característico de una
extrasístole."""

QRS_MAX_HALF_AMPLITUDE_WIDTH_MS: float = 80.0
"""Ancho MÁXIMO, a media amplitud, que se considera compatible con un pico
de QRS -- ver `_looks_like_qrs()`. NO es el umbral de 120ms del CRITERIO
clínico de bloqueo de rama (que mide el COMPLEJO completo, onset a offset,
y puede legítimamente superar 120ms en un BBB real); esto mide una
propiedad geométrica del PICO individual -- incluso en un QRS ancho
patológico, el componente R/R'/S que se usa como ancla tiene una subida y
bajada de unas pocas decenas de ms. Calibrado empíricamente (Fase 3,
2026-08-12) contra picos de QRS conocidos (16-62ms, verificados a mano
contra los 50 casos de validación) y picos de onda T conocidos que el
selector anterior había elegido por error (88-112ms, `ecg_id=1123`/`1232`)
-- 80ms cae limpio en la brecha entre ambos grupos."""


def _half_amplitude_width_ms(
    signal: np.ndarray, peak_idx: int, fs: float, search_half_window_ms: float = 150.0,
) -> float:
    """Ancho del pico en `peak_idx`, medido a media amplitud respecto a un
    baseline local (estimado en los BORDES de la ventana de búsqueda, lejos
    del propio pico) -- ver `_looks_like_qrs()` para por qué esto distingue
    QRS de onda T. Si la deflexión es más ancha que la ventana de búsqueda
    (`search_half_window_ms` a cada lado), el ancho queda acotado por la
    ventana -- sigue siendo, correctamente, "más ancho que un QRS"."""
    half_window = int(search_half_window_ms / 1000.0 * fs)
    start = max(0, peak_idx - half_window)
    end = min(len(signal) - 1, peak_idx + half_window)
    edge_samples = 5
    baseline_segment = np.concatenate([
        signal[start:start + edge_samples],
        signal[max(start, end - edge_samples):end + 1],
    ])
    baseline = float(np.median(baseline_segment))
    peak_amplitude = signal[peak_idx] - baseline
    if peak_amplitude == 0:
        return 0.0
    half_level = baseline + 0.5 * peak_amplitude

    left = right = peak_idx
    if peak_amplitude > 0:
        while left > start and signal[left] >= half_level:
            left -= 1
        while right < end and signal[right] >= half_level:
            right += 1
    else:
        while left > start and signal[left] <= half_level:
            left -= 1
        while right < end and signal[right] <= half_level:
            right += 1
    return (right - left) / fs * 1000.0


def _looks_like_qrs(signal: np.ndarray, peak_idx: int, fs: float) -> bool:
    """True si el pico en `peak_idx` es lo bastante ANGOSTO como para ser
    un componente de QRS, no una onda T.

    Necesario porque la regularidad de RR (`REFERENCE_BEAT_RR_TOLERANCE`)
    NO distingue QRS de onda T por sí sola -- una T ocurre una vez por
    latido, igual que el QRS, así que un patrón RR-regular lo cumplen
    ambas por igual. Confirmado contra datos reales (Fase 3, 2026-08-12):
    los anclajes automáticos que caían en onda T en `ecg_id=1123`/`1232`
    (encontrados en la investigación de solo-lectura previa a esta tanda)
    pasaban el filtro de regularidad sin problema -- la selección de
    latido necesitaba una segunda señal, independiente de la posición en
    el tiempo, para descartarlos.

    El QRS es una deflexión de alta frecuencia (subida/bajada de unas
    pocas decenas de ms); la onda T es una deflexión redondeada de baja
    frecuencia (~160ms+ de ancho total) -- la misma propiedad que usa la
    literatura de detección de QRS (p.ej. Pan-Tompkins: filtro pasa-banda
    + derivada + integración, que resalta el contenido de alta frecuencia
    del QRS frente a P/T) para separarlas. Aquí se mide directamente como
    ancho a media amplitud (`_half_amplitude_width_ms()`) contra
    `QRS_MAX_HALF_AMPLITUDE_WIDTH_MS` -- más simple que replicar todo el
    pipeline de Pan-Tompkins, y suficiente para el propósito (elegir un
    ancla, no detectar cada latido del registro)."""
    return _half_amplitude_width_ms(signal, peak_idx, fs) <= QRS_MAX_HALF_AMPLITUDE_WIDTH_MS


def _select_reference_beat(reference_signal: np.ndarray, fs: float) -> Optional[int]:
    """Elige UN latido representativo y limpio de la derivación de
    referencia para anclar la delineación de TODAS las derivaciones al
    MISMO instante cardíaco -- ver `detect_bundle_branch_block()` para por
    qué esto es necesario (corrección de sincronización V1/V6, Fase 3,
    2026-08-12).

    Criterio de selección -- decisión de diseño de este módulo, explícita:
    1. Detecta picos por amplitud ABSOLUTA (`_detect_reference_peaks()`) --
       ve tanto QRS predominantemente positivos como negativos.
    2. Descarta los picos que PARECEN onda T, no QRS (`_looks_like_qrs()`,
       por anchura a media amplitud) -- corrección posterior a la
       sincronización (misma fecha): sin este filtro, una T periódica podía
       ganarle al QRS real en el paso de regularidad de RR de abajo. Si
       este filtro eliminara TODOS los picos (caso degenerado), cae a la
       lista sin filtrar -- preferible a no tener ningún candidato.
    3. Excluye el primer y el último pico QRS-like detectado -- riesgo de
       truncamiento en los bordes del registro (`delineate_qrs()` necesita
       margen de ±120ms a ambos lados del latido).
    4. De los picos interiores restantes, descarta cualquiera cuyo hueco RR
       (al vecino anterior O al siguiente, calculado SOLO entre los picos
       QRS-like -- no entre la lista mixta original, que alternaría R/T y
       distorsionaría la mediana de RR) se desvíe más de
       `REFERENCE_BEAT_RR_TOLERANCE` de la mediana -- sospechoso de latido
       ectópico o artefacto. Varios de los 50 casos de validación tienen
       extrasístoles documentadas en el reporte original de PTB-XL (p.ej.
       `ecg_id=1157`, "premature ventricular contraction(s)").
    5. Entre los picos "regulares" que sobreviven, elige el más cercano al
       CENTRO temporal del registro -- ni el primero ni el último de los
       regulares tampoco, para mantenerse lejos de ambos bordes.
    Si ningún pico interior sobrevive el filtro de regularidad, cae a los
    picos interiores sin filtrar por RR -- preferible a no analizar ningún
    latido."""
    peaks = _detect_reference_peaks(reference_signal, fs)
    if len(peaks) == 0:
        return None

    qrs_like = [p for p in peaks if _looks_like_qrs(reference_signal, p, fs)]
    working_peaks = qrs_like if qrs_like else list(peaks)

    if len(working_peaks) <= 2:
        return int(working_peaks[len(working_peaks) // 2])

    interior = working_peaks[1:-1]
    if len(interior) == 1:
        return int(interior[0])

    rr = np.diff(working_peaks)
    median_rr = float(np.median(rr))
    regular = [
        working_peaks[i]
        for i in range(1, len(working_peaks) - 1)
        if abs(rr[i - 1] - median_rr) <= REFERENCE_BEAT_RR_TOLERANCE * median_rr
        and abs(rr[i] - median_rr) <= REFERENCE_BEAT_RR_TOLERANCE * median_rr
    ]
    candidates = regular if regular else list(interior)

    center = len(reference_signal) / 2.0
    return int(min(candidates, key=lambda idx: abs(idx - center)))


def _s_wave_duration_ms(signal: np.ndarray, r_idx: int, s_idx: int, offset_idx: int, fs: float) -> float:
    """Duración de S por cruce de cero: desde donde la señal cae por debajo
    de 0 tras R hasta donde vuelve a cruzar 0 (o el fin de la ventana de QRS
    si no vuelve a cruzar dentro de ella)."""
    s_onset = r_idx
    for i in range(r_idx, s_idx):
        if signal[i] >= 0 and signal[i + 1] < 0:
            s_onset = i + 1
            break
    s_offset = offset_idx
    for i in range(s_idx, offset_idx):
        if signal[i] < 0 and signal[i + 1] >= 0:
            s_offset = i + 1
            break
    return (s_offset - s_onset) / fs * 1000.0


def _positive_peaks_in_order(peaks: List[Dict]) -> List[Dict]:
    return [p for p in peaks if p["amplitude"] > 0]


def _check_rbbb_v1(delineation: QrsDelineation) -> Tuple[bool, str]:
    """R' = la SEGUNDA deflexión positiva del complejo, por posición -- no el
    peak que el delineador etiquetó internamente "R_prime". Ese label
    (`qrs_delineation._find_subpeaks`) llama "R" al candidato de mayor
    AMPLITUD ABSOLUTA sin importar el orden -- correcto para un QRS de un
    solo lóbulo, pero en el patrón rsR'/RSR' de RBBB la R' terminal suele
    ser MÁS ALTA que la r inicial, así que el delineador la etiqueta "R" a
    ELLA (no a la r inicial), y entonces `_peak_of_type(peaks, "R_prime")`
    nunca encuentra nada -- confirmado contra los 50 casos reales (Fase 3,
    2026-08-12): con la lógica por TYPE, 0/25 RBBB detectaba una R'. Esta
    versión no depende del label del delineador, solo de signo y orden."""
    positives = _positive_peaks_in_order(delineation.peaks)
    if len(positives) < 2:
        return False, "V1: no hay una segunda deflexión positiva distinguible (candidata a R') -- no cumple RBBB"

    first_positive, terminal_positive = positives[0], positives[-1]
    is_terminal = delineation.peaks[-1] is terminal_positive
    is_dominant = abs(terminal_positive["amplitude"]) >= abs(first_positive["amplitude"])

    if is_terminal and is_dominant:
        return True, (
            f"V1: segunda deflexión positiva terminal y dominante "
            f"(R'={terminal_positive['amplitude']:.2f} mV >= R={first_positive['amplitude']:.2f} mV)"
        )
    problems = []
    if not is_terminal:
        problems.append("la segunda deflexión positiva no es la deflexión terminal del complejo")
    if not is_dominant:
        problems.append(
            f"la segunda deflexión positiva ({terminal_positive['amplitude']:.2f} mV) no domina "
            f"sobre la primera ({first_positive['amplitude']:.2f} mV)"
        )
    return False, "V1: " + "; ".join(problems)


def _check_rbbb_qr_v1(delineation: QrsDelineation) -> Tuple[bool, str]:
    """Patrón qR atípico en V1 -- morfología B de RBBB (Fase 4, ver
    docstring del módulo para la cita/procedencia y las decisiones de
    implementación). Requiere, en este orden:
    1. Exactamente UNA deflexión positiva (R única) -- una segunda positiva
       es candidata a R', eso es RSR' (morfología A), no qR.
    2. Esa R es la deflexión TERMINAL del complejo -- nada negativo la
       sigue ("sin S posterior").
    3. R >= `RBBB_QR_R_MIN_AMPLITUDE_MV`.
    4. Existe una deflexión INMEDIATAMENTE anterior a la R (la "q") con
       amplitud <= `RBBB_QR_INITIAL_Q_MAX_AMPLITUDE_MV`. Si la R es la
       ÚNICA deflexión del complejo (nada antes tampoco), NO hay q que
       medir -- ver nota de procedencia en el docstring del módulo: esto
       NO se relaja a "R sola" para forzar un rescate."""
    positives = _positive_peaks_in_order(delineation.peaks)
    if len(positives) != 1:
        return False, "V1 (qR): requiere exactamente una deflexión positiva (R única) -- no cumple qR"

    r_peak = positives[0]
    if delineation.peaks[-1] is not r_peak:
        return False, "V1 (qR): hay una deflexión posterior a la R -- no cumple 'sin S posterior'"

    if r_peak["amplitude"] < RBBB_QR_R_MIN_AMPLITUDE_MV:
        return False, (
            f"V1 (qR): R ({r_peak['amplitude']:.2f} mV) no alcanza el umbral "
            f">={RBBB_QR_R_MIN_AMPLITUDE_MV} mV"
        )

    if len(delineation.peaks) < 2:
        return False, "V1 (qR): no hay una deflexión q antes de la R (R sola, no qR) -- no cumple qR"

    q_candidate = delineation.peaks[-2]  # inmediatamente antes de la R (que ya es la última, ver arriba)
    if q_candidate["amplitude"] > RBBB_QR_INITIAL_Q_MAX_AMPLITUDE_MV:
        return False, (
            f"V1 (qR): la deflexión antes de la R ({q_candidate['amplitude']:.2f} mV) no alcanza "
            f"el umbral q<={RBBB_QR_INITIAL_Q_MAX_AMPLITUDE_MV} mV"
        )

    return True, (
        f"V1: patrón qR (q={q_candidate['amplitude']:.2f} mV, R={r_peak['amplitude']:.2f} mV, "
        "sin S posterior)"
    )


def _check_rbbb_v6(
    signal: np.ndarray,
    delineation: QrsDelineation,
    fs: float,
    max_amplitude_mv: float = RBBB_S_V6_MAX_AMPLITUDE_MV,
    min_duration_ms: float = RBBB_S_V6_MIN_DURATION_MS,
) -> Tuple[bool, str]:
    """Par R/S en V6 -- salvaguarda compartida por las dos morfologías de
    RBBB (RSR' clásico y qR atípico, Fase 4). Los umbrales por defecto son
    los del RSR' clásico; el criterio qR llama esta misma función con
    umbrales propios y más estrictos (`RBBB_QR_V6_S_MAX_AMPLITUDE_MV`) --
    parametrizado en vez de duplicado, misma lógica de detección de
    par R/S y misma medición de duración por cruce de cero."""
    positives = _positive_peaks_in_order(delineation.peaks)
    negatives = [p for p in delineation.peaks if p["amplitude"] < 0 and p["idx"] > positives[0]["idx"]] if positives else []
    if not positives or not negatives:
        return False, "V6 sin par R/S identificable -- no cumple RBBB"

    r_peak = positives[0]
    s_peak = min(negatives, key=lambda p: p["amplitude"])  # más negativa = la S real, no un notch menor

    if s_peak["amplitude"] > max_amplitude_mv:
        return False, (
            f"V6: S ({s_peak['amplitude']:.2f} mV) no alcanza el umbral "
            f"<={max_amplitude_mv} mV"
        )

    duration_ms = _s_wave_duration_ms(signal, r_peak["idx"], s_peak["idx"], delineation.offset_idx, fs)
    if duration_ms < min_duration_ms:
        return False, f"V6: S dura {duration_ms:.0f} ms (< {min_duration_ms:.0f} ms)"

    terminal = delineation.peaks[-1]
    if terminal["amplitude"] >= 0:
        return False, "V6: la deflexión terminal no es negativa"

    return True, f"V6: S ancha ({duration_ms:.0f} ms, {s_peak['amplitude']:.2f} mV), polaridad final negativa"


def _check_lbbb_v1(delineation: QrsDelineation) -> Tuple[bool, str]:
    """QS/rS = a lo sumo UNA deflexión positiva (una "r" pequeña, o
    ninguna) y la deflexión dominante del complejo es negativa -- misma
    razón que `_check_rbbb_v1` para no depender del label "R_prime" del
    delineador."""
    positives = _positive_peaks_in_order(delineation.peaks)
    if len(positives) >= 2:
        return False, "V1: presenta una segunda deflexión positiva (candidata a R') -- no compatible con QS/rS de LBBB"
    dominant = _dominant_peak(delineation.peaks)
    if dominant is None or dominant["amplitude"] >= 0:
        amp = f"{dominant['amplitude']:.2f} mV" if dominant else "ninguna deflexión"
        return False, f"V1: la deflexión dominante ({amp}) no es negativa -- no es QS/rS"
    return True, f"V1: patrón predominantemente negativo (dominante {dominant['type']}, {dominant['amplitude']:.2f} mV)"


def _check_lbbb_v6(delineation: QrsDelineation) -> Tuple[bool, str]:
    """Por amplitud/signo, no por el `type` que asignó el delineador -- misma
    razón documentada en `_check_rbbb_v1`."""
    dominant = _dominant_peak(delineation.peaks)
    if dominant is None or dominant["amplitude"] <= 0:
        amp = f"{dominant['amplitude']:.2f} mV" if dominant else "ninguna deflexión"
        return False, f"V6: la deflexión dominante ({amp}) no es positiva -- no hay R dominante"
    first_peak = delineation.peaks[0]
    if first_peak["amplitude"] < LBBB_SEPTAL_Q_MAX_AMPLITUDE_MV:
        return False, (
            f"V6: Q septal presente ({first_peak['amplitude']:.2f} mV < "
            f"{LBBB_SEPTAL_Q_MAX_AMPLITUDE_MV} mV) -- no compatible con LBBB"
        )
    return True, f"V6: R dominante ({dominant['amplitude']:.2f} mV), sin Q septal"


def detect_bundle_branch_block(
    v1_signal: np.ndarray,
    v6_signal: np.ndarray,
    fs: float,
    reference_signal: Optional[np.ndarray] = None,
) -> BbbMorphologyResult:
    """Detector morfológico RBBB/LBBB/indeterminado sobre V1/V6 -- ver
    docstring del módulo para el criterio verbatim y las decisiones de
    implementación documentadas.

    `reference_signal` (opcional, idealmente lead II -- el estándar de
    ritmo, ver `_select_reference_beat()`): deriva el ÚNICO latido
    compartido con el que se ancla la delineación de V1 Y V6 -- mismo
    instante cardíaco, medido en cada derivación (corrección de
    sincronización, Fase 3, 2026-08-12: antes, V1 y V6 elegían su latido de
    referencia CADA UNA por su cuenta, y podían terminar describiendo
    complejos distintos, separados hasta 5368ms en los 50 casos de
    validación -- ver CHANGELOG.md). Sin `reference_signal`, se usa V6 como
    ancla (fallback documentado: morfología típicamente más estándar/menos
    ambigua que V1 para localizar el latido, y sigue siendo UNA sola señal
    para las dos delineaciones -- preserva la sincronización aunque no haya
    una derivación de ritmo dedicada disponible)."""
    anchor_signal = reference_signal if reference_signal is not None else v6_signal
    r_idx = _select_reference_beat(anchor_signal, fs)
    if r_idx is None:
        return BbbMorphologyResult(
            pattern=None, qrs_duration_ms=0.0,
            reasoning=["No se detectó un latido de referencia válido"],
        )

    v1_delineation = delineate_qrs(v1_signal, r_idx, fs)
    v6_delineation = delineate_qrs(v6_signal, r_idx, fs)

    qrs_duration_ms = max(v1_delineation.qrs_duration_ms, v6_delineation.qrs_duration_ms)
    if qrs_duration_ms <= QRS_WIDE_THRESHOLD_MS:
        return BbbMorphologyResult(
            pattern=None, qrs_duration_ms=qrs_duration_ms,
            reasoning=[f"QRS={qrs_duration_ms:.0f} ms no supera el umbral > {QRS_WIDE_THRESHOLD_MS:.0f} ms"],
        )

    # Morfología A -- RSR' clásico
    rbbb_v1, rbbb_v1_reason = _check_rbbb_v1(v1_delineation)
    rbbb_v6, rbbb_v6_reason = _check_rbbb_v6(v6_signal, v6_delineation, fs)
    is_rbbb_classic = rbbb_v1 and rbbb_v6

    # Morfología B -- qR atípico (Fase 4), con SU PROPIA salvaguarda V6 más estricta
    qr_v1, qr_v1_reason = _check_rbbb_qr_v1(v1_delineation)
    qr_v6, qr_v6_reason = _check_rbbb_v6(
        v6_signal, v6_delineation, fs,
        max_amplitude_mv=RBBB_QR_V6_S_MAX_AMPLITUDE_MV,
        min_duration_ms=RBBB_QR_V6_S_MIN_DURATION_MS,
    )
    is_rbbb_qr = qr_v1 and qr_v6

    is_rbbb = is_rbbb_classic or is_rbbb_qr

    lbbb_v1, lbbb_v1_reason = _check_lbbb_v1(v1_delineation)
    lbbb_v6, lbbb_v6_reason = _check_lbbb_v6(v6_delineation)
    is_lbbb = lbbb_v1 and lbbb_v6

    header = f"QRS={qrs_duration_ms:.0f} ms (umbral > {QRS_WIDE_THRESHOLD_MS:.0f} ms)"

    if is_rbbb and is_lbbb:
        # No debería ocurrir dado que RBBB exige dominante positivo en V1 y
        # LBBB exige dominante negativo en V1 -- red de seguridad, no un
        # camino esperado: nunca se fuerza una rama sobre la otra.
        return BbbMorphologyResult(
            pattern=INDETERMINATE_LABEL, qrs_duration_ms=qrs_duration_ms,
            reasoning=[header, "Conflicto: cumple criterios duros de RBBB y LBBB a la vez -- no se fuerza ninguna"],
        )
    if is_rbbb_classic:
        return BbbMorphologyResult(
            pattern="RBBB", qrs_duration_ms=qrs_duration_ms,
            reasoning=[header, rbbb_v1_reason, rbbb_v6_reason],
        )
    if is_rbbb_qr:
        return BbbMorphologyResult(
            pattern="RBBB", qrs_duration_ms=qrs_duration_ms,
            reasoning=[header, "Morfología qR atípica (Fase 4):", qr_v1_reason, qr_v6_reason],
        )
    if is_lbbb:
        return BbbMorphologyResult(
            pattern="LBBB", qrs_duration_ms=qrs_duration_ms,
            reasoning=[header, lbbb_v1_reason, lbbb_v6_reason],
        )

    return BbbMorphologyResult(
        pattern=INDETERMINATE_LABEL, qrs_duration_ms=qrs_duration_ms,
        reasoning=[
            header,
            rbbb_v1_reason, rbbb_v6_reason,
            "qR: " + qr_v1_reason, "qR-V6: " + qr_v6_reason,
            lbbb_v1_reason, lbbb_v6_reason,
        ],
    )
