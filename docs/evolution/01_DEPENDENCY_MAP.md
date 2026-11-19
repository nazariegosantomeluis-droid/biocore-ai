# 01 · Mapa de dependencias: qué módulos dependen de cuáles

**Fase 0, commit `db4b16b` (2026-11-19).** Medido con un análisis estático de las importaciones (`ast`) de todos los `.py` fuera de `tests/`, `docs/` y `data/`. No cuenta las importaciones dinámicas (`importlib`), que se revisaron a mano donde importaban.

## 1. Paquetes de primer nivel

| Paquete | Archivos `.py` | Qué es |
|---|---|---|
| `app/` | 107 | Interfaz Streamlit: páginas, supermódulos, instrumentos, motores (`app/engines`) y utilidades (`app/utils/`) |
| `domain/` | 54 | UPS, paciente compuesto, compositores, acoplamientos, escenarios, hemodinámica, narrador y ML heurístico |
| `src/` | 65 | Procesamiento de señal por modalidad (`src/signals/`), imagen (TC/RM → malla), mapa de cohortes, casos clínicos |
| `hardware/` | 31 | Adquisición: placa ECG ESP32 + AD8232, placa de biosensores (`BIO:`), EEG en vivo (BrainFlow/LSL), firmware |
| `clinical/` | 12 | Analizador de ECG, calculadoras clínicas, metadatos de PTB-XL |
| `educational/` | 12 | Bancos de preguntas, base de conocimiento, casos guiados, calibración, analítica de aprendizaje |
| `visualization/` | 9 | Componentes de gráfica (parte sin uso; ver §3) |
| `signals/` | 7 | Cargadores viejos de MIT-BIH; solo los importa el `app/utils.py` muerto |
| `biomedical/` | 3 | `BiomedicalReasoningEngine` y el clasificador de arritmias |
| `dashboards/` | 2 | `multisensor.py`; solo lo importa el `app/utils.py` muerto |
| `tools/` | 4 | Scripts (subconjunto de fuentes, etc.) |

## 2. Grafo de importaciones entre paquetes

Número de sentencias `import` de un paquete a otro:

```
app ──70──▶ domain        app ──70──▶ src         app ──30──▶ clinical
app ──28──▶ educational   app ──25──▶ hardware    app ──12──▶ visualization
app ───3──▶ signals*      app ───1──▶ dashboards*
domain ──16──▶ app   ◀── INVERSIÓN DE CAPAS
domain ───6──▶ src        domain ──3──▶ clinical    domain ──1──▶ biomedical
educational ──5──▶ src    educational ──3──▶ clinical   educational ──2──▶ domain
hardware ──5──▶ clinical  hardware ──1──▶ domain    hardware ──1──▶ src
src ──3──▶ clinical       src ──1──▶ hardware       src ──1──▶ signals
clinical ──1──▶ src       visualization ──1──▶ src
(* solo desde app/utils.py, que nunca se carga: ver §3)
```

### 2.1 La inversión `domain → app` (16 importaciones)

El dominio, que debería ser la capa de abajo, importa de la interfaz:

- `app.engines.digital_twin_organism.DigitalTwinOrganism`: lo usan `state/builder.py`, `scenarios/engine.py`, `scenarios/rich_engine.py`, `scenarios/case_bank.py` y cuatro módulos `hemodynamics/*_comparison.py`.
- `app.engines.simulation_engine.SimulationScenario` y `SimulationEngine`: los mismos módulos de escenarios y de hemodinámica.
- `app.utils.physiological_state.persist_current_state`: `scenarios/rich_engine.py`.

**Consecuencia:** `domain/` no se puede usar ni probar sin `app/` (y sin Streamlit importable). El organismo y el motor de escenarios son lógica de dominio que vive bajo `app/`. La propuesta está en `03_ARCHITECTURE_DECISIONS.md`, AD-3.

### 2.2 `domain → biomedical` (1 importación)

`domain/physiology/ml/arrhythmia_evaluation.py:73` importa `biomedical.arrhythmia_classifier` dentro de una función. `CLAUDE.md` dice que «`biomedical/` no lo importa la app». Eso sigue siendo cierto para `reasoning_engine.py`, pero el clasificador sí entra por esta vía.

## 3. Módulos que la app no alcanza

**Método:** se recorrieron las importaciones desde `app/main.py`. De los 302 archivos, 268 se alcanzan. De los 34 restantes, se revisó a mano cada uno: varios los cargan importaciones dinámicas o relativas que el análisis no sigue, como `ecg_12/page_content.py` o `respiratory_lab/page_content.py`. Los que se confirmaron sin uso:

| Módulo | Por qué no se ejecuta | Quién lo referencia |
|---|---|---|
| `app/utils.py` (560 líneas) | El paquete `app/utils/` lo tapa: `import app.utils` carga `app/utils/__init__.py` | `app/supermodules/__init__.py` hace `importlib.import_module('app.utils')`, que también carga el paquete |
| `signals/` (7 archivos) | Solo lo importa `app/utils.py` | — |
| `dashboards/multisensor.py` | Solo lo importa `app/utils.py` | — |
| `src/utils/`, `src/rural_health/` | Solo los importa `app/utils.py` | Pruebas: `test_tanda2b_reporting_pdf.py`, `test_fase1_t2_pulido.py` |
| `src/data/real_data_loader.py`, `src/education/learning.py` | Nadie los importa | — |
| `visualization/ecg_clinical_plot.py`, `ecg_annotations.py`, `educational_panel.py`, `medical_grid.py`, `medical/plotly_clinical.py` | Solo se importan entre sí o desde `app/utils.py` | — |
| `hardware/sensor_manager.py`, `hardware/emg_stream.py` | Solo aparecen en comentarios de `app/main.py` y `biosensors/emg.py` | — |
| `educational/ecg_academy.py` | La tabla de 12 derivaciones sin cita «ya no se muestra» | Comentarios de `academia/pages.py` |
| `clinical/ecg12.py` | Reemplazado por `src/signals/ecg/twelve_lead_measure.py` | Comentarios |
| `src/signals/ecg/advanced_patterns.py` | — | Solo `test_arrhythmia_unification.py` |
| `biomedical/reasoning_engine.py` | — | Solo `example_reasoning_engine.py` y `test_reasoning_engine_new.py` |
| `app/ecg_trainer.py` | — | Solo `test_fase1_t1_diseno.py` (excepción de color) |
| `app/streamlit_app.py` | Es un punto de entrada alterno: reejecuta `main.py` | Streamlit Cloud |
| `hardware/*/firmware/*.py` | MicroPython que corre en la ESP32, no en la app | — |

Ninguno se borra en la Fase 0. Borrar es la regla 7 de `CLAUDE.md`: requiere aprobación (AD-4).

## 4. Flujos de datos actuales

### 4.1 Del instrumento al paciente

```
Instrumento (app/instruments/*: ecg_trazo, hrv, respiracion, eeg, emg)
  │ guardar() → organismo.update_from_sensors(...)
  ▼
DigitalTwinOrganism (app/engines) ──▶ builder.from_digital_twin_organism()   ← única puerta al UPS
                                         │  DERIVED_CONTRACT (derivados solo con todas sus entradas)
                                         │  compuertas anti-órgano-fantasma
                                         ▼
                                     save_state() → SQLite (ups_snapshots, ups_values, ups_events)
                                         │
                       ┌─────────────────┼─────────────────────────┐
                       ▼                 ▼                         ▼
          get_composed_patient()   get_latest_state()        compositores (escriben)
          (banner, Hoy, gemelo,     (modo caso, Comparar,     · compose_neuro_cardiac_snapshot (gemelo)
           Ruta, calculadoras)       trayectoria)             · evaluate_rule_for_patient (Ruta, T6)
                                                                   └─▶ apply_couplings → heart_rate_acoplado
```

### 4.2 Escenarios y Ruta

`run_rich_scenario` (domain/scenarios) crea un paciente nuevo, corre el motor de escenarios (`app/engines/simulation_engine`) y persiste la trayectoria con `persist_current_state` (`app/utils`). Cada valor de la trayectoria lleva su horizonte. Las unidades de la Ruta parten de ahí.

### 4.3 Narrador

```
UPS (ventana antes/ahora) → narrator/context.py → privacy.classify_source → prompt → client (Anthropic) | gemini.py
```

Sin clave falla explícito. Un proveedor sin pago solo recibe datos simulados o de base pública.

### 4.4 Equipos en vivo

`hardware/ecg_plugplay` (AD8232) y `hardware/biosensors` + `hardware/eeg_live` (un mismo servicio) → vistas de `app/supermodules/ecg_live` y `biosensors` → «Guardar al gemelo» por el builder. La procedencia es `SENSOR_REAL` solo mientras un equipo real manda datos.
