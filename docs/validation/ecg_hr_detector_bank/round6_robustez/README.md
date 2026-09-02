# Banco de validación — Ronda de Robustez (condición de la firma del experto)

2026-08-24. Implementa el detector TKEO (fiducial estructural, spec del
experto) + normalización Z-score/curtosis + validación sobre cohorte
MIT-BIH ampliada (25 registros), como condición previa al cableado que el
experto puso tras firmar la ronda 5 como checkpoint seguro.

## Resultado, en una frase

**El diagnóstico del experto se confirmó parcialmente**: el TKEO reparó
casi por completo la sensibilidad de derivación (V5 del 100: SDNN
223.6→30.3ms, idéntico a su MLII) y mejoró sustancialmente — sin
colapsar del todo — el fiducial estructural del marcapasos (217: SDNN
175.2→85.5ms, -51%, VPP 0.597→1.000). Sobre la cohorte ampliada de 25
registros (10 previos + 15 nuevos, 0 fallos de descarga), el detector
generaliza razonablemente (mediana de sensibilidad/VPP ≥0.98 en los
nuevos) con 4 excepciones honestas (todas en carga alta de PVC/marcapasos).

**Hallazgo crítico, no resuelto aquí**: re-apuntar la MISMA compuerta
whitelist a picos TKEO (en vez de bidireccionales) hace que 6/25
registros cambien de veredicto — incluida una regresión concreta: el
registro 118 (BRD), que la ronda 5 aceptaba correctamente, pasa a
declinar por la compuerta de calidad genérica (no por los filtros de
dinámica R-R, que sí son estables entre detectores). La fórmula de
confianza heredada no transfiere a los fiduciales TKEO sin recalibrarse
-- bloqueo concreto para cablear, reportado, no forzado ni escondido.

## Empieza aquí

`hoja_firma_final_ronda6.pdf` — las dos pruebas de reparación (fiducial,
derivación), la tabla de la cohorte ampliada con generalización y
discrepancias, tiras representativas, y la pregunta de cierre que
autoriza (o no) el cableado.

## Qué cambió en el código de producción

`clinical/ecg_analyzer.py` — solo adiciones, ningún método existente se
modificó:
- `ECGAnalyzer.detect_r_peaks_tkeo()` — nuevo, el detector estructural.
- `ECGAnalyzer.normalize_zscore()` / `signal_quality_kurtosis()` /
  `select_best_lead_by_kurtosis()` — nuevos, utilidades de Parte B.

`detect_r_peaks()` (BBB) y `detect_r_peaks_bidirectional()` (ronda
anterior) quedan intactos. `estimate_heart_rate_with_confidence()` (la
compuerta whitelist) NO se tocó en esta ronda — sigue usando
`detect_r_peaks_bidirectional()` internamente, no el TKEO nuevo; cablear
la compuerta sobre TKEO es parte de lo que la firma del experto autoriza
o no. Nada cableado a la escritura del UPS.
