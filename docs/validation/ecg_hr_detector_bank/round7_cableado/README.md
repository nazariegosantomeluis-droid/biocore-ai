# Cierre — compuerta recalibrada a Vpp + cableado ECG→UPS

2026-08-24. Última tanda: recalibra la compuerta de calidad (Modelo 1 del
experto — Vpp por ventana en vez de amplitud puntual), re-valida los 25
registros de la cohorte de la ronda 6 con punto de parada, y cablea la
escritura de ECG al UPS. Integración estrecha 3/3.

## Resultado, en una frase

**Recalibración exitosa, sin puntos de parada**: el registro 118 (BRD)
pasa de rechazo incorrecto (ronda 6) a aceptación correcta; los 6 casos
con expectativa clínica clara (100/103/118 aceptan, 210/217/104 declinan)
coinciden todos; solo 2/25 registros cambian de veredicto respecto a la
ronda 6 (118 y 122, ambos correcciones, ninguna regresión). Con la
compuerta validada, se cableó la escritura de ECG al UPS —
`clinical/ecg_analyzer.py::estimate_heart_rate_with_confidence()` ahora
usa `detect_r_peaks_tkeo()` internamente (no `detect_r_peaks_bidirectional()`),
gobernando el botón "💾 Guardar estado al gemelo" de ECG Lab
(`app/main.py::_render_ecg_save_to_twin()`).

## Qué cambió en el código de producción

`clinical/ecg_analyzer.py`:
- `VPP_WINDOW_MS`/`VPP_CV_THRESHOLD` (constantes nuevas, provisionales).
- `estimate_heart_rate_with_confidence()`: la métrica de calidad ahora usa
  Vpp por ventana (`max-min` en ±50ms) en vez de amplitud puntual; el
  detector interno pasa de `detect_r_peaks_bidirectional()` a
  `detect_r_peaks_tkeo()` — por eso se retiró `prominence_factor` de la
  firma (parámetro del detector viejo, sin sentido para TKEO). Filtros
  pRR31/metrónomo/banda sinusal sin cambios.

`app/main.py`:
- `_render_ecg_save_to_twin()` (nuevo) + llamada desde la Vista Clínica de
  `render_ecg_monitor_page()` — tercer y último lab de la integración
  estrecha (Respiratory, HRV, ahora ECG).

`detect_r_peaks()` (BBB) y `detect_r_peaks_bidirectional()` (ronda 5)
quedan intactos, ya no usados por la compuerta pero disponibles.
