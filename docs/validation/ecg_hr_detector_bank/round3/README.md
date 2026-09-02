# Banco de validación — 3ª ronda (hacia la bendición final)

Preparado 2026-08-24, implementando el veredicto del experto sobre la
frontera clínica: bloqueo de rama (118) **dentro** de alcance (el nodo
sinusal sigue siendo el metrónomo, HRV es válida), marcapasos (217)
**fuera** (el R-R lo dicta la máquina, no el sistema nervioso autónomo).

## Empieza aquí

**`hoja_decision_experto_3a_ronda.pdf`** — Parte A (éxito, caja verde) +
Parte B (resultado negativo documentado, caja roja) + Parte C + las 4
preguntas de la bendición final.

## Resultado, en una frase

**Parte A funcionó**: el desempate refractario cambió de "mayor amplitud
absoluta" a "mayor pendiente máxima (|dv/dt|)" — el registro 118 (BRD)
recupera sensibilidad de 0.64 a 0.991, sin regresión en los registros que
ya iban bien. **Parte B no funcionó**: la bandera de marcapasos (picos de
pendiente extrema, angostos, aislados), implementada exactamente como se
especificó, no separa el registro 217 (marcapasos) de 118 (BRD) ni del
ruido en ningún umbral probado (barrido de z=10 a 30) — evidencia completa
en la hoja de decisión, no forzado a "funcionar".

## Archivos

- `hoja_decision_experto_3a_ronda.pdf` — empieza aquí.
- `tiras_ecg_3a_ronda.pdf` — 11 registros, amplitud (ronda 2) vs pendiente (ronda 3); 118 y 217 con anotaciones especiales.
- `tabla_comparativa_3a_ronda.xlsx` — 66 filas + hoja de recuperación de 118 + hoja de evidencia del barrido de la Parte B.
- `raw_results3.json` — datos en crudo.
- `build_bank3.py` / `build_strips3.py` / `build_table3.py` / `build_decision_sheet3.py` — scripts reproducibles.

## Qué cambió en el código de producción

`clinical/ecg_analyzer.py`:
- `detect_r_peaks_bidirectional()` — el desempate refractario ahora usa `_max_slope()` (pendiente máxima en una ventana de 15ms) en vez de amplitud absoluta. Método existente modificado en su lógica interna (no su firma), no `detect_r_peaks()` original (sigue intacto).
- `_max_slope()` — nuevo método privado.
- `detect_pacemaker_spikes()` — nuevo método, corregido de un bug de clustering de la implementación inicial, documentado honestamente como **no confiable** tras la validación (ver docstring y la hoja de decisión). No cableado a ningún flujo.
- `estimate_heart_rate_with_confidence()` — docstring actualizado explicando por qué el rechazo de marcapasos NO se cableó (`detect_pacemaker_spikes()` no es confiable). Comportamiento sin cambios respecto a la 2ª ronda.

Nada de esto está cableado a la escritura ECG→UPS todavía.
