# 02 · Línea base de regresión: qué pruebas pasan y qué comportamiento hay que preservar

**Fase 0, commit `db4b16b` (2026-11-19).** Todo lo de este documento se midió por ejecución en el contenedor de la sesión:

- Python 3.13;
- Streamlit 1.67.0, el mismo que usa Luis;
- base temporal (`tests/conftest.py`);
- sin red a PhysioNet;
- sin equipos reales.

## 1. Resultado de la suite

| Corrida | Resultado | Tiempo |
|---|---|---|
| `pytest tests/ -q` con cobertura (`--cov` sobre `app`, `src`, `clinical`, `domain`, `educational`, `hardware` y `visualization`) | **3,047 passed, 10 skipped, 0 failed** | 18 min 40 s |
| La misma suite sin cobertura, con el `domain/` sin commitear (2026-11-19) | 3,044 passed, 10 skipped; fallaron la guardia de `domain/` (esperado) y dos pruebas del compositor, que se corrigieron antes del commit | 12 min 42 s |

- **Archivos de prueba:** 152 en `tests/`.
- **Guardia de `domain/`:** `test_ups_body_3d_paridad.py::test_ups_builder_schema_and_engine_untouched` corre `git diff --stat HEAD -- domain/` y exige salida vacía. Falla mientras haya cambios en `domain/` sin commitear. No es un fallo del código: es la guardia haciendo su trabajo.
- **Base de desarrollo:** la suite no escribe en `data/biocore_ups.db`. Si una revisión visual crea ese archivo, dos pruebas de la base de desarrollo se activan y fallan; hay que borrarlo.

### 1.1 Las 10 omitidas y por qué

Todas dependen del entorno, no del código.

| Prueba | Motivo |
|---|---|
| `test_ecg_hr_detector_consolidation.py` (corrida contra PhysioNet) | «omitida: requiere red a PhysioNet» |
| `test_bbb_detector_validation.py` (casos PTB-XL que se descargan) | PTB-XL no accesible sin red |
| `test_arrhythmia_model_card.py` | `lightgbm` no instalado en este entorno |
| `test_baroreflex_visible.py`, `test_docs_honest_tanda2.py` | git o el commit base no disponibles (según el entorno) |
| `test_eeg_live.py` (BrainFlow/LSL) | BrainFlow o pylsl no disponibles |
| `test_biosensors_*.py`, `test_ecg_plugplay_serial.py` | Los pseudo-terminales no existen en Windows: en Linux corren, en la máquina de Luis se omiten |

## 2. Cobertura de líneas por paquete

| Paquete | Sentencias | Cobertura | 2026-11-05 |
|---|---|---|---|
| `domain` | 2,710 | **87.9 %** | 89.7 % |
| `app` | 11,411 | **83.1 %** | 64 % |
| `hardware` | 3,759 | **82.0 %** | 19.2 % |
| `educational` | 1,306 | **79.6 %** | 36 % |
| `src` | 5,571 | **76.1 %** | 56.6 % |
| `clinical` | 1,247 | **70.6 %** | 69.6 % |
| `visualization` | 706 | **40.7 %** | 40.7 % |
| **Total** | **26,710** | **80 %** | 62 % |

**Con 0 % y más de 20 sentencias:** `app/ecg_trainer.py`, `clinical/ecg12.py`, `educational/ecg_academy.py`, `hardware/emg_stream.py`, `hardware/sensor_manager.py`, `visualization/ecg_annotations.py`, `ecg_clinical_plot.py`, `educational_panel.py` y `medical_grid.py`. Coinciden con los módulos sin uso de `01_DEPENDENCY_MAP.md` §3.

**Lección que sigue vigente (inventario del 5 de noviembre):** «líneas ejecutadas ≠ valores verificados». Una prueba de render que llega al final de la página sube la cobertura, pero no fija ningún número clínico. Las pruebas que sí fijan valores están en la tabla de la §3.

## 3. Comportamiento que hay que preservar (matriz mínima de regresión)

La matriz del documento nuevo (§9.3), con las pruebas que hoy la cubren.

| Área | Prueba obligatoria (documento) | Pruebas que la cubren hoy | Hueco |
|---|---|---|---|
| ECG | Procesamiento y resultados de referencia | `test_ecg_hr_detector_consolidation.py` (FC contra MIT-BIH; sin red, contra el generador), `test_bbb_detector_validation.py`, `test_twelve_lead_measure.py`, `test_pulido_profesional.py` (papel ECG) | La validación con registros reales se omite sin red |
| EEG | Procesamiento espectral y estado del equipo | `test_eeg_*.py` (bandas, FOOOF, en vivo con simulador), `test_t6_1_techo_bar.py` (BAR y vigilia) | Sin grabación real con artefactos conocidos |
| EMG | Filtrado, características y calibración declarada | `test_biosensors_emg.py`, `test_emg_analyzer.py`, `test_emg_lab_save_to_twin.py` | No hay calibración de la CVM; la prueba solo fija que se declara su ausencia |
| Respiración | Golden tests y valores no disponibles | `test_respiratory_detector_golden.py`, `test_respiratory_generator_ground_truth.py` y los demás `test_respiratory_*.py` (9 archivos; detector contra la verdad del generador, «no disponible» con menos de 3 respiraciones) | — |
| HRV | Métricas, requisitos y unidades | los archivos `test_hrv_*.py`, `test_rsa*.py` y `test_hrv_nonlinear*.py` | — |
| PPG | Calidad y limitaciones de la SpO₂ | `test_biosensors_ppg_temp.py` (la SpO₂ no se calcula: falta su curva de calibración) | — |
| Biosensores | Fuente real y desconexión | `test_biosensors_*.py`, `test_ecg_plugplay_serial.py` | Se omiten en Windows |
| UPS | Procedencia, derivación y datos ausentes | `test_ups_derived_contract.py`, `test_ups_phase1_frontier.py`, `test_ups_composed_patient.py`, `test_fase0_*.py` | — |
| Gemelo | Correspondencia con el UPS | `test_twin_paciente_compuesto.py`, `test_twin_os_phase1.py`, `test_ups_body_3d_paridad.py` | — |
| Simulación | Reproducibilidad y etiquetado | `test_scenario_simulator.py`, `test_case_bank_evaluable_horizons.py`, los generadores con semilla | El ruido del EEG simulado no usa semilla; su BAR varía entre corridas (`test_t6_1_techo_bar.py` lo acota) |
| Acoplamientos | Reglas firmadas, bloqueos, no combinar, copias | `test_coupling_*.py`, `test_t6_compositor_reglas.py`, `test_t6_acoplamientos_ruta.py`, `test_t6_1_techo_bar.py`, `test_composer.py` | — |
| Narrador | Privacidad, citas y ausencia de IA sin configurar | `test_narrator.py`, `test_narrator_gemini.py` (privacidad por proveedor), `test_citation_tutor.py` | Nunca se llamó a la API real |
| Navegación | Rutas antiguas y destinos actuales | `test_t5_navegacion.py`, `test_fase1_t1_navegacion.py` (12 entradas del menú del 2026-11-14) | — |
| Persistencia | Aislamiento de sesiones y pacientes | `tests/conftest.py` (base temporal), pruebas de la base de desarrollo | **Hueco:** en internet la base es compartida (opción B declarada); ninguna prueba aísla a dos personas |
| Investigación | Reproducibilidad de análisis | `test_tanda2d_eeg_map_cohort.py` (mapa de cohortes) | **No existe un Research Studio** |
| Contenido firmado | Cada texto médico sale de un documento firmado | `test_fase1_t2_teoria.py` (línea por línea), `test_banco_*.py`, `test_guided_case*.py`, `test_legal.py` | — |
| Lenguaje | Sin inglés visible, sin «bpm», sin tratamientos sin cita | `test_fase1_t2_pulido.py` (las 34 páginas y 7 fuentes), `test_integracion_contencion.py` | — |

## 4. Cómo repetir esta línea base

```bash
pip install -r requirements-dev.txt
pytest tests/ -q                                   # ≈ 13 min
pytest tests/ -q --cov=app --cov=src --cov=clinical --cov=domain \
       --cov=educational --cov=hardware --cov=visualization --cov-report=term   # ≈ 19 min
```

En Python 3.13, `COVERAGE_CORE=sysmon` reduce el costo de la cobertura (inventario del 5 de noviembre, §7).
