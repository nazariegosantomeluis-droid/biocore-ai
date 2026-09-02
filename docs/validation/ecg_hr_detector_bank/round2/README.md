# Banco de validación — 2ª ronda

Preparado 2026-08-24, tras el rechazo del experto al banco de la 1ª ronda
(`../README.md`). Implementa la Solución 1 que el experto recomendó
(bidireccional + periodo refractario) como método **nuevo y aditivo** en
`clinical/ecg_analyzer.py` — `detect_r_peaks()` (el original) queda intacto,
usado sin cambios por el pipeline BBB/clínico ya validado.

## Empieza aquí

**`hoja_decision_experto_2a_ronda.pdf`** — trae el hallazgo crítico primero
(falso-aceptado de la compuerta de calidad en el registro 217, marcapasos)
y las 4 preguntas de esta ronda.

## Resultado, en una frase

El detector reparado **no es una mejora uniforme**: soluciona el problema
que lo motivó (108, 207 — antes ciegos a un QRS de polaridad opuesta) pero
introduce una regresión seria en QRS anchos con componentes de ambas
polaridades de amplitud comparable (217 marcapasos, 118 bloqueo de rama) —
la supresión refractaria por "mayor amplitud absoluta" elige el componente
equivocado. Instrumentado, no resuelto — el experto decide el criterio de
desempate.

## Archivos

- `hoja_decision_experto_2a_ronda.pdf` — el hallazgo crítico + 4 preguntas.
- `tiras_ecg_2a_ronda.pdf` — 11 registros, detector viejo vs reparado, competencias bifásicas marcadas.
- `tabla_comparativa_2a_ronda.xlsx` — 66 filas (11 registros × 6 `prominence_factor`), sensibilidad/VPP viejo vs reparado, confianza y decisión de la compuerta; segunda hoja aislando el falso-aceptado.
- `raw_results2.json` — datos en crudo.
- `build_bank2.py` / `build_strips2.py` / `build_table2.py` / `build_decision_sheet2.py` — scripts reproducibles (mismo orden de ejecución que la 1ª ronda).

## Qué cambió en el código de producción

`clinical/ecg_analyzer.py` — **solo adiciones**, nada modificado ni
eliminado:
- `ClinicalDataQualityError` (excepción) + `QUALITY_THRESHOLD` (constante, 0.6, PROVISIONAL).
- `ECGAnalyzer.detect_r_peaks_bidirectional()` — el detector reparado.
- `ECGAnalyzer.estimate_heart_rate_with_confidence()` — HR + confianza, lanza `ClinicalDataQualityError` en vez de adivinar.

Nada de esto está cableado a ningún flujo de producción todavía — la
escritura ECG→UPS sigue sin construirse.
