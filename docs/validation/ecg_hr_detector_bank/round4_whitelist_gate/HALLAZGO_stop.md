# Compuerta whitelist — hallazgo que detiene el cableado (Parte B, tanda final)

2026-08-24, Capa 2/5B. Implementada la compuerta whitelist tal como el
experto la especificó (Filtro del Caos, Filtro del Metrónomo, banda
fisiológica sinusal, bloqueo de metadatos como gancho documentado — sobre
`ECGAnalyzer.estimate_heart_rate_with_confidence()`, `clinical/ecg_analyzer.py`).
Re-validada contra el banco de 11 registros MIT-BIH antes de cablear la
escritura al UPS, según lo pedido explícitamente ("si algún registro cae
del lado equivocado, detente y repórtalo").

**Resultado: ningún `prominence_factor` probado (1.0 / 1.5 / 2.0) logra la
frontera correcta (118 aceptado; 210 y 217 declinados) simultáneamente.**
No se ajustaron los umbrales del experto (250ms/15%, 3ms, banda sinusal)
para forzar un resultado que coincidiera con el banco — eso habría sido
sobreajustar a los 11 casos conocidos, exactamente lo que esta campaña evita.

## Tabla completa (11 registros × 3 `prominence_factor`)

| Registro | Descripción | pf=1.0 | pf=1.5 | pf=2.0 |
|---|---|---|---|---|
| 100-0 | sinusal limpio | DECLINA (CAOS) ❌ | ACEPTA (0.89) ✅ | ACEPTA (0.89) ✅ |
| 103-0 | sinusal limpio | ACEPTA (0.77) ✅ | ACEPTA (0.92) ✅ | ACEPTA (0.92) ✅ |
| 117-0 | QRS negativo | DECLINA (CAOS) | DECLINA (CAOS) | DECLINA (CAOS) |
| 108-0 | bajo voltaje | DECLINA (CAOS) | DECLINA (CAOS) | DECLINA (CAOS) |
| 228-0 | PVCs | DECLINA (CAOS) | DECLINA (CAOS) | DECLINA (CAOS) |
| 207-0 | VT/VFib+ruido | DECLINA (CAOS) | DECLINA (CAOS) | DECLINA (CAOS) |
| 233-0 | ruido severo | DECLINA (CAOS) | DECLINA (CAOS) | DECLINA (CAOS) |
| **118-0** | **BRD — DEBE aceptar** | DECLINA (calidad genérica) ❌ | **ACEPTA (0.63) ✅** | DECLINA (calidad genérica) ❌ |
| **210-0** | **FA sostenida — DEBE declinar** | DECLINA (calidad genérica) ✅* | **ACEPTA (0.65) ❌** | **ACEPTA (0.69) ❌** |
| **217-0** | **marcapasos — DEBE declinar** | DECLINA (calidad genérica) ✅* | DECLINA (CAOS) ✅* | **ACEPTA (0.63) ❌** |
| 100-1 | 100, otra derivación | DECLINA (CAOS) | DECLINA (CAOS) | ACEPTA (0.68) |

`*` = declina por la razón correcta en el resultado final, pero NO por el
mecanismo clínico que se supone debía detectarlo (ver diagnóstico abajo) —
el rechazo es un efecto colateral del ruido del detector, no la lógica de
Caos/Metrónomo funcionando como se diseñó.

**Ningún `pf` logra las 3 filas en negrita correctas a la vez**: pf=1.5 es
la más cercana (118 y 217 correctos) pero acepta 210 (FA) por error — el
fallo más grave posible, dado que excluir ritmos no-autonómicos es el
propósito central de esta compuerta.

## Diagnóstico de causa raíz (evidencia directa, no especulación)

Medí SDNN y fracción-de-saltos-caóticos directamente sobre los picos que
el detector reparado produce (no sobre el ground truth) en cada caso:

| Registro | pf=1.0 | pf=1.5 | pf=2.0 |
|---|---|---|---|
| 100 (sinusal) | SDNN=161.0ms, caos=21.1% | SDNN=30.1ms, caos=0.45% | SDNN=30.1ms, caos=0.45% |
| 118 (BRD) | SDNN=113.6ms, caos=8.0% | SDNN=68.5ms, caos=3.65% | SDNN=68.7ms, caos=3.65% |
| 210 (FA real) | SDNN=143.5ms, caos=**12.7%** | SDNN=133.7ms, caos=**12.3%** | SDNN=133.3ms, caos=**14.0%** |
| 217 (marcapasos) | SDNN=109.3ms, caos=9.4% | SDNN=175.2ms, caos=**21.4%** | SDNN=155.1ms, caos=**13.7%** |

Dos mecanismos distintos, ambos reales:

1. **El Filtro del Caos no separa 210 (FA real) del rango sinusal en
   ninguno de los 3 `pf`.** Su fracción de saltos >250ms (12.3-14.0%)
   queda SIEMPRE por debajo del umbral del 15%, en los tres parámetros
   probados — pese a que su SDNN (133-144ms) es 2-4× el de un sinusal
   limpio (30-68ms), la irregularidad de esta FA concreta no se concentra
   en saltos individuales grandes y frecuentes de la forma que el criterio
   asume; se distribuye más difusamente. El criterio "250ms/15%" tal como
   está especificado no la detecta.

2. **La premisa del Filtro del Metrónomo (SDNN≈0 para marcapasos) no se
   sostiene con el detector actual sobre el registro 217.** El detector
   reparado (pendiente, Parte A de la tanda anterior) no reproduce el
   intervalo mecánicamente fijo del marcapasos con precisión de muestra —
   introduce suficiente imprecisión temporal propia (SDNN observado:
   109-175ms según `pf`) como para enmascarar la variabilidad casi nula
   que el ritmo real tiene. El filtro de 3ms nunca se activa porque el
   SDNN medido no se parece al SDNN fisiológico real del marcapasos — se
   parece al ruido del propio detector.

3. **Efecto colateral, no cazado por los filtros nuevos**: la compuerta de
   calidad genérica (heredada de la ronda 2, `regularity_score`/
   `amplitude_score`, sin tocar en esta tanda) es sensible a `pf` de forma
   independiente — rechaza 118 en pf=2.0 por razones ajenas a Caos/
   Metrónomo/banda sinusal. Esto añade una tercera fuente de varianza al
   resultado final, dificultando aún más encontrar un `pf` único que
   funcione para los 11 casos.

## Lo que esto significa

La barrera clínica (dinámica R-R en vez de morfología) sigue siendo el
diseño correcto — el problema no es el principio, es que **los umbrales
numéricos específicos, aplicados sobre la SALIDA del detector actual (no
sobre el ground truth), no producen la separación esperada** en este
banco. Dos caminos posibles para la próxima tanda, ninguno decidido aquí:

- Recalibrar los umbrales (250ms/15%, 3ms) específicamente contra la
  distribución SDNN/caos que el detector *real* produce (no contra la
  intuición fisiológica de un ground truth limpio) — el experto decide los
  números nuevos.
- Aceptar que el detector necesita una mejora adicional (más allá de la
  Parte A) antes de que sus salidas sean lo bastante estables para que
  filtros de dinámica R-R funcionen con fiabilidad.

## Qué NO se hizo en esta tanda

- **No se cableó la escritura de ECG al UPS** (Parte C) — bloqueada
  explícitamente detrás de la validación de la Parte B, que no pasó.
- **No se tocaron los umbrales del experto** para forzar un ajuste al banco.
- **No se tocó `detect_r_peaks()` original** — el pipeline BBB sigue intacto
  (45 tests dirigidos, ver verificación).
- El bloqueo de metadatos (Parte A.0, pacemaker) SÍ se implementó como
  gancho documentado — `PatientRecord` no tiene ese campo hoy
  (`domain/physiology/state/models.py`); añadirlo es una migración de
  schema aparte, no ejecutada aquí.

Integración estrecha: **2/3 completa** (Respiratory, HRV). ECG sigue sin
cerrar — esperando la recalibración del experto sobre esta evidencia.
