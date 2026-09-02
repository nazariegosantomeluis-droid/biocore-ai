# Banco de validación — detector de HR de ECG

Preparado 2026-08-24, Capa 2 / Capa 5B (mini-arco). Cero cambios al código de
producción de ECG Lab — este banco solo **lee** `clinical/ecg_analyzer.py::ECGAnalyzer.detect_r_peaks()`
(el detector real del repo) y datos reales de PhysioNet (MIT-BIH), vía `wfdb`.

## Por qué existe

La Fase 2.4 (integración estrecha labs→UPS) dejó ECG diferido: escribir su
`heart_rate` exigía un `prominence_factor` que no está bendecido en ningún
otro lugar del repo (el default de la clase, 0.3, duplica ondas T). Este
banco corre el detector real contra anotaciones de cardiólogos (ground
truth objetivo, archivos `.atr` de MIT-BIH) en 8 registros × 6 valores de
`prominence_factor`, para que un experto humano decida el parámetro/criterio
— el mismo rol que ya validó el detector de BBB.

## Archivos

- **`hoja_decision_experto.pdf`** — empieza aquí. Resume el hallazgo principal, y trae las 3 preguntas que el experto necesita responder.
- **`tiras_ecg_picos_marcados.pdf`** — 8 registros × 2 parámetros (0.3 vs 1.0), señal con picos detectados (▽ rojo) y anotaciones de cardiólogo (X verde) superpuestos.
- **`tabla_comparativa_detector_hr.xlsx`** — 48 filas (registro × prominence_factor) con HR, error, sensibilidad, VPP, TP/FP/FN; segunda hoja de contraste 0.3 vs 1.0.
- **`raw_results.json`** — los mismos datos en crudo.
- **`build_bank.py` / `build_strips.py` / `build_table.py` / `build_decision_sheet.py`** — scripts que regeneran todo desde cero (descargan de PhysioNet, no requieren red local aparte de eso). Ejecutar en orden: `build_bank.py` → `build_strips.py` / `build_table.py` → `build_decision_sheet.py`.

## Hallazgo principal

Los registros 117 y 108 tienen QRS predominantemente **negativo** en la
derivación MLII. `ECGAnalyzer.detect_r_peaks()` usa `scipy.signal.find_peaks()`,
que solo busca máximos positivos — el detector nunca ve el latido real en
estos registros, sin importar el `prominence_factor` (VPP tope ~0.53 en el
117; sensibilidad 0.15–0.18 en el 108, en todo el barrido). No es un
problema de umbral — es una limitación estructural del detector, visible de
un vistazo en las tiras.

## Conjunto de registros (PROVISIONAL)

Elegido por cribado cuantitativo propio (no por criterio clínico experto)
sobre 23 candidatos de MIT-BIH: `100`/`103` (limpios), `117` (trampa T/R
prominente — en realidad QRS negativo), `108` (bajo voltaje + PACs), `228`
(arritmia real), `207` (caso extremo: fibrilación/flutter ventricular +
ruido), `233` (ruido/artefacto), `118` (bloqueo de rama derecha). Ver la
hoja de decisión para la pregunta abierta sobre si este conjunto basta.

## Ground truth

MIT-BIH sí trae anotaciones de latido descargables (`wfdb.rdann(rec, 'atr',
pn_dir='mitdb')`) — usadas como referencia objetiva. PTB-XL **no** trae
anotaciones de latido descargables (confirmado: 404 al pedir el `.atr`),
solo códigos diagnósticos a nivel de registro.
