# Banco de validación — ronda 5 (precisión temporal + métricas de literatura)

2026-08-24. Implementa interpolación parabólica del fiducial (Task Force
ESC/NASPE 1996) y reemplaza el Filtro del Caos por pRR31 (Buś et al.) sobre
`ECGAnalyzer.estimate_heart_rate_with_confidence()`. Re-valida el banco.

## Resultado, en una frase

**Parte A (interpolación parabólica) falló su propia hipótesis** — el SDNN
del registro 217 (marcapasos) NO colapsó (109-175ms enteros → 109-175ms
refinados, diferencia <0.1ms) — el desajuste real es órdenes de magnitud
mayor que el jitter de cuantización que la interpolación puede corregir.
Reportado sin suavizar. **Parte B (pRR31) sí funcionó**: a
`prominence_factor=1.5`, la compuerta reformada acierta los 5 casos
primarios (100/103/118 aceptan, 210/217 declinan). Discrepancia residual
reportada, no forzada: el lead V5 del registro 100 (mismo paciente,
misma sesión) se declina por pRRx cuando "debería" aceptar igual que su
lead MLII — el detector se comporta peor en esa derivación específica.

## Empieza aquí

`hoja_firma_experto_ronda5.pdf` — hipótesis del jitter falseada (con
tabla), frontera de 5 casos primarios acertada (con tabla + tiras), y la
hoja de firma de los 3 umbrales provisionales con su cita.

## Qué cambió en el código de producción

`clinical/ecg_analyzer.py` — solo adiciones/reemplazos dentro de métodos ya
no cableados a producción:
- `ECGAnalyzer.refine_peaks_parabolic()` — nuevo, aditivo.
- `estimate_heart_rate_with_confidence()` — el Filtro del Caos (250ms/15%)
  se reemplazó por pRR31; el resto de los pasos ahora opera sobre marcas
  refinadas en vez de índices enteros.
- Constantes `CHAOS_JUMP_MS`/`CHAOS_FRACTION` retiradas (no quedan como
  reliquia muerta); `PRR_THRESHOLD_MS`/`PRR_FRACTION_LIMIT` nuevas.

`detect_r_peaks()` original (el que alimenta el pipeline BBB) sigue
intacto. Nada de esto está cableado a la escritura del UPS todavía.
