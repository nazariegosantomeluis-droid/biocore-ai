# CLAUDE.md — BIOCORE AI

Guía operativa para cualquier sesión de Claude Code en este repo. Es la referencia vigente: si otro documento la contradice, este gana. La historia del proyecto vive en `CHANGELOG.md`, no aquí. El estado real de cada módulo (real, heurístico, simulado, defectuoso) está en `docs/INVENTARIO_BIOCORE_2026-11-05.md`.

## Qué es

Plataforma educativa de fisiología en Python + Streamlit. Un gemelo digital **simulado** (declarado como simulación) y varios laboratorios que analizan señal, todos alimentando un estado fisiológico unificado (UPS) donde cada valor declara su procedencia. Un narrador con IA (API de Anthropic, opcional) explica en palabras los datos del UPS.

**Art. I, regla rectora:** nunca presentar como real, medido, validado o inteligente lo que no lo es. Cuando algo no se puede saber, se dice «no disponible» con el motivo; no se rellena con algo plausible. Esto aplica al código, a la UI y a los documentos.

## Mapa real

- **Entrada:** `streamlit run app/main.py` (en Windows también `RUN_BIOCORE.bat` / `run_local.ps1`, vía `run_biocore.py`). `app/streamlit_app.py` solo reejecuta `main.py`. El `main.py` de la raíz es un pipeline CLI de ECG, aparte de la app.
- **Navegación:** el diccionario `HUBS` de `app/main.py` define 4 hubs y 12 entradas; `render_page_content()` enruta por substring del nombre.

| Hub | Entrada | Dónde vive |
|---|---|---|
| Digital Twin OS | Digital Twin OS | `app/supermodules/twin_shell/` (`pages.py`, `ups_body_visual.py`, `ups_body_3d.py`) |
| Learning Hub | Academia Clínica | `app/supermodules/academia/` |
| Clinical Hub | ECG Lab | `render_ecg_lab_page()` en `app/main.py`: pestaña Monitoreo (`render_ecg_monitor_page()`, también en `main.py`) + pestaña 12 Derivaciones (`app/supermodules/ecg_12/`) |
| Clinical Hub | Multisensor Fusion Lab | `render_multisensor_page()` en `app/main.py` |
| Clinical Hub | Respiratory Lab | `app/supermodules/respiratory_lab/` (detector reparado, **sin insignia de validado**; ver abajo) |
| Clinical Hub | EEG Neuro Lab | `app/supermodules/eeg_neuro_lab/` |
| Clinical Hub | EMG Muscle Lab | `render_emg_page()` en `app/main.py` |
| Clinical Hub | HRV Analysis | `render_hrv_page()` en `app/main.py` (+ `app/supermodules/hrv_nonlinear_panel.py`, `rsa_panel.py`) |
| Clinical Hub | Biomarkers Lab | `render_biomarkers_page()` en `app/main.py` (+ `app/supermodules/biomarkers.py`) |
| Clinical Hub | Calculadoras Clínicas | `app/supermodules/calculators/` + `clinical/calculators.py` |
| Clinical Hub | Patient Pipeline | `render_patient_pipeline_page()` en `app/main.py` |
| Laboratorio 3D | Crea tu modelo 3D | `app/supermodules/model3d/` |

- **Capas de código:** `src/signals/` (procesamiento por modalidad), `clinical/` (analizador de ECG, calculadoras, metadatos PTB-XL), `domain/physiology/` (UPS, escenarios, hemodinámica, acoplamientos, narrador, ML heurístico), `visualization/`, `app/engines/` (organismo simulado y motor de escenarios), `src/imaging/` (TC/RM → malla), `src/ml/` (mapa de cohortes, exploratorio).
- `biomedical/` (el `BiomedicalReasoningEngine`) **no lo importa la app**; solo `example_reasoning_engine.py`. No construyas sobre él.

## El UPS (`domain/physiology/state/`)

- **Cuatro dominios:** `cardiovascular`, `respiratory`, `neurological`, `muscular`. Son campos nombrados de `UnifiedPhysiologicalState` en `schema.py`; `all_domains()` los lista (la UI lee de ahí, no los repitas en textos).
- **`Provenance`** (enum en `schema.py`, 7 valores): `SENSOR_REAL`, `SIMULACION`, `DERIVADO`, `REFERENCIA_CLINICA`, `MODELO_HEMODINAMICO`, `DERIVADO_ACOPLAMIENTO`, `ARRASTRE_TEMPORAL`. Se declara al entrar el valor, nunca después. `CONFIDENCE_REFERENCE` da una banda de confianza a cinco procedencias; `REFERENCIA_CLINICA` y `ARRASTRE_TEMPORAL` no tienen banda a propósito (`default_confidence()` lanza `KeyError` con ellas). La referencia clínica usa su propio tipo (`ClinicalReferenceValue`, con cita obligatoria, sin confianza numérica); el arrastre temporal hereda tal cual la confianza del valor de origen.
- **Gates anti-órgano-fantasma** (`builder.py`: `_cardiovascular_state`, `_respiratory_state`, `_neurological_state`, `_muscular_state`): sin dato real, el dominio queda vacío. Un laboratorio que mide solo una cosa no escribe valores por defecto de las demás. `from_digital_twin_organism()` es la única forma soportada de poblar el UPS desde el organismo.
- **Compositor** (`composer.py`, `compose_neuro_cardiac_snapshot`): une el último `bar` (EEG) y el último `heart_rate` reales en un snapshot, con el `heart_rate` como `ARRASTRE_TEMPORAL` y su edad declarada. Si falta alguno, o el `heart_rate` es más viejo que `max_hr_carry_age_s`, devuelve `ComposeResult(available=False, reason=...)` y no compone nada. Tras guardar llama a `apply_couplings(..., scenario=None)`.
- **Acoplamientos** (`coupling/`): `VALIDATED_RULES` (en `catalog.py`) tiene **una** regla activa, `AROUSAL_TAQUICARDIA_BAR`: `bar` > 1.8 ⇒ +15 bpm en `heart_rate`, confianza 0.70. Dispara en el snapshot del compositor (donde coexisten `bar` y `heart_rate`). En el EEG Neuro Lab la llamada a `apply_couplings` es un **no-op honesto**: ese snapshot no trae `heart_rate`. `COUPLING_DISABLED_SCENARIOS` (`stress`, `anxiety`, `seizure`) bloquea el acoplamiento donde el escenario ya modela la descarga simpática. No agregues reglas «por simetría»: cada una necesita su firma de experto.
- **Hemodinámica** (`hemodynamics/`): reimplementación analítica de las ecuaciones RCR de svZeroDSolver (atribución en `THIRD_PARTY_NOTICES.md`); lazo cerrado propio, habilitado en 3 escenarios (`healthy`, `hypertension`, `sepsis`). Solo modela el shock establecido; fuera de esa fase la PA se declina con motivo. `SimulationScenario` tiene 15 escenarios.
- **Persistencia:** SQLite + SQLAlchemy en `data/biocore_ups.db` (ignorado por git). La ruta sale del global `domain.physiology.state.db.DEFAULT_DB_PATH`, que `make_engine(None)` lee al llamarse; la app comparte un engine vía `app/utils/patient_session.py::get_shared_ups_engine()`.
- **Narrador** (`domain/physiology/narrator/`): `client.py` (`DEFAULT_MODEL = "claude-opus-5-5"`, **no verificado por ejecución**: sin clave en el entorno no se hizo ninguna llamada real), `context.py`, `prompt.py`, `findings.py`, `causal.py`. Sin clave falla explícito (`NarratorNotConfiguredError`); no hay modo simulado. La clave pegada por la persona vive solo en `st.session_state` (`app/utils/ai_session.py`), nunca en `os.environ`. Toda llamada a un modelo de lenguaje debe pasar por este paquete.
- **Cuerpo visual:** el color de cada órgano sale de `organ_visual_state(state)` en `ups_body_visual.py`, que consumen las tarjetas SVG y el cuerpo 3D. Nunca colorees desde `organism.organs[...].status`.

## Reglas de trabajo

1. **Diagnostica antes de tocar.** Mide, localiza la causa y repórtala antes de cambiar nada. Un síntoma no es una causa.
2. **Verifica por ejecución**, no por lectura: corre `pytest` y, para la UI, un `AppTest` que llegue al final del render. Contra una base temporal, nunca la de desarrollo.
3. **Lee las funciones completas** y confirma los llamadores con `git grep` antes de editar o borrar.
4. **Diferido no es roto; archivado no es pendiente.** No «arregles» lo que se difirió a propósito, ni resucites lo archivado.
5. **Prohibido `get(key, default)` disfrazado de medición.** Un valor por defecto que se muestra o se persiste como si fuera un dato es una fachada. Si falta el dato: «no disponible», con motivo.
6. **Simulación ≠ dato falso:** lo sintético se etiqueta siempre como simulación. Una etiqueta de validación (`VALIDATED`, citas, «real», «IA», «ML») solo se pone si el código hace eso; una heurística se llama heurística.
7. **Pregunta antes de decisiones grandes** (borrar módulos, cambiar de framework o de base de datos).
8. **Sin commits sin aprobación de Luis, y sin atribución a Claude** (ni `Co-Authored-By` ni mensajes «generado con»): todo va solo a nombre de Luis Nazariego Santome. Luis revisa y commitea.
9. **Todo elemento nuevo justifica su existencia** frente al UPS, el gemelo o el valor educativo; si no, no entra.
10. **Documenta en `CHANGELOG.md`** cada tanda, citando el Art. I cuando corrija una fachada. No existen `PLAN.md` ni un plan maestro en este repo.

## Comandos

```bash
source .venv/Scripts/activate          # Windows + Git Bash; Python 3.13 (única versión probada)
pytest tests/ -q                       # suite completa; varios minutos
pytest tests/test_containment_facades_tanda1.py -q    # contención de fachadas (AppTest)
streamlit run app/main.py
```

- **Aislamiento de la base:** `tests/conftest.py` tiene un fixture `autouse` de sesión que redirige `domain.physiology.state.db.DEFAULT_DB_PATH` a un archivo temporal. La suite no debe escribir en `data/biocore_ups.db`; compruébalo contando pacientes antes y después.
- **Guardia de `domain/`:** `tests/test_ups_body_3d_paridad.py::test_ups_builder_schema_and_engine_untouched` corre `git diff --stat HEAD -- domain/` y exige salida vacía. Falla mientras haya cambios de `domain/` sin commitear; no es un fallo del código.
- **Recetas de AppTest** (`streamlit.testing.v1`):
  - Un supermódulo: `AppTest.from_function(script)` con `m.run()`, e inyectar `twin_shell_ups_session_factory` y `twin_shell_ups_patient_id` en `session_state` para que escriba en una base temporal.
  - La app completa: `AppTest.from_file(str(Path("app/main.py").resolve()))` con `biocore_ai_entry_done=True`, `selected_hub` y `selected_page`.
  - `at.exception` **no** ve los errores que pasan por `render_error_state()` (solo los registra y dibuja una caja): comprueba también el texto de la página.
- **Archivos:** muchos son CRLF; conserva los finales de línea al editar. Los comentarios y la UI van en español.

## En corrección o no fiable hoy

- **Respiratory Lab (detector reparado, sin insignia de validado):** `RespiratoryAnalyzer` se reescribió contra golden tests (`tests/test_respiratory_detector_golden.py`). Muestra solo lo validado: FR = 60 / media de los intervalos entre inspiraciones (≥ 3 respiraciones o «no disponible»; redondeo .5 hacia arriba antes de NEWS2, banda de `clinical.calculators._news2_rr`), duración del ciclo, variabilidad, apneas (Berry 2012: caída ≥ 90 % durante ≥ 10 s; tipo por esfuerzo = Criterio BIOCORE; mixta PENDING_VALIDATION), tasa equivalente por hora de **registro** (extrapolada, sin categoría) y la SpO₂ del modelo BIOCORE. **Ocultos:** hipopneas, I:E, patrón, notas clínicas, ODI, «Guardar al gemelo» e insignia (severidad solo como calculadora pura en Calculadoras Clínicas). La sigla del índice por hora de sueño está prohibida en el lab. Todo umbral técnico fuera de los criterios firmados es HEURISTIC (`HEURISTICS` en el analizador); las compuertas son relativas (la señal de flujo tiene la escala del generador).
- **Generador respiratorio** (`src/signals/respiration/respiratory_generator.py`): es el ground truth del arco. `generate_respiration()` devuelve `'ground_truth'` (FR efectiva, eventos con inicio/duración/tipo, inicios de respiración en la atáxica), usa `np.random.default_rng(seed)` y rechaza con `ImpossibleParameters` los parámetros imposibles. La SpO₂ es un modelo de eventos (nadir en fin + Tc, Tc = 15 s «Valor BIOCORE»; r = 0.30 %/s y recuperación a 0.70 %/s de Howarth 2026; piso = `desaturation_level`; `recovery_time` se retiró). Atáxica: duración y profundidad aleatorias (`irregularity`, HEURISTIC); Cheyne-Stokes: cada valle es una apnea central anotada. Señal de flujo en L/min con pico = VT × FR (escala del generador).
- **Heurístico o demo, declarado así en pantalla:** Biomarkers Lab («modo demostración»), Multisensor Fusion Lab (solo canales demo), activación del EMG (media/máximo de la señal filtrada, no % de contracción máxima), fatiga del EMG con la señal demo, índice de riesgo de Digital Twin OS y sus «explicaciones» (pesos fijos, sin entrenamiento; no son SHAP ni LIME).
- **Lo que no existe:** un dominio metabólico en el UPS, `PLAN.md`, `pages_legacy/`, `_archive/`.
- **`shap` y `lime`** figuran en `requirements.txt` pero ningún archivo los importa.

## Datos de terceros

Ecuaciones, datos incluidos en el repo, librerías y métodos publicados están atribuidos en `THIRD_PARTY_NOTICES.md`. Si agregas uno, agrégalo ahí con su licencia y su cita, tomadas de la fuente original y no de memoria.
