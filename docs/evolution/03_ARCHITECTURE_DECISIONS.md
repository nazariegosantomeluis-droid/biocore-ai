# 03 · Decisiones de arquitectura: qué decidir y por qué

**Fase 0, commit `db4b16b` (2026-11-19).** Cada decisión dice el problema, la propuesta, lo que cuesta y quién decide. Ninguna está implementada: la Fase 0 solo propone. Las marcadas «aprobación de Luis» tocan la regla 7 de `CLAUDE.md` (borrar módulos, cambiar de framework o de base de datos) o `domain/`.

## 1. Lo que no se negocia

Viene del documento nuevo, §3, y de `CLAUDE.md`:

- **Un solo estado:** el UPS (`UnifiedPhysiologicalState`) sigue siendo el único estado fisiológico. Ningún contrato nuevo crea un UPS paralelo.
- **Procedencia:** se declara al entrar el valor. «No disponible» siempre lleva su motivo. No hay valores por defecto mostrados como datos.
- **Pila tecnológica:** se mantienen Streamlit, SQLite y SQLAlchemy.
- **Cambios pequeños:** no hay reorganizaciones amplias de carpetas. Toda firma pública que cambie lleva su plan de compatibilidad.
- **Commits:** nada se sube sin aprobación de Luis y sin atribución a Claude.

## 2. Matriz de compatibilidad: contratos del documento ↔ lo que existe

El documento pide diseñar cinco contratos (§5) **sin reemplazar los esquemas actuales**. Esto es lo que ya existe para cada campo; el diseño fino es la Fase 1.

### 2.1 `BiomedicalSignal`

Hoy no hay un tipo común. Cada instrumento tiene su serie: `EegSeries` (`app/instruments/eeg.py`), `EmgSignal` (`emg.py`), `RRSeries` (`hrv.py`), y el ECG y la respiración como arreglos sueltos.

| Campo pedido | Dónde está hoy | Hueco |
|---|---|---|
| signal ID | — | Falta |
| patient ID / session ID | `patient_id` en el UPS; la sesión es `st.session_state` | Las señales no se persisten |
| modality, channel | Implícitos en cada `*Series` (canal en `EegSeries`) | Sin enumeración común |
| timestamps, sampling rate | `fs` y el arreglo de tiempo en cada serie | Sin un nombre común |
| physical unit | En el texto de la UI (mV, µV, cuentas) | No es un campo |
| source, provenance | Etiqueta de la fuente en cada instrumento; `Provenance` solo al guardar | Se declara tarde: al guardar, no al adquirir |
| quality | `hardware/*/quality.py` (equipos en vivo) | Solo en vivo |
| calibration | — (no hay CVM en el EMG ni curva de SpO₂) | Falta |

**Propuesta:** un `BiomedicalSignal` inmutable en un módulo nuevo y adaptadores `from_eeg_series()`, `from_rr_series()`… que no cambian los instrumentos (patrón de la T2).

### 2.2 `PhysiologicalFeature`

Casi todo existe en `PhysiologicalDescriptor` (`schema.py`): `name`, `value`, `unit`, `provenance`, `confidence` y `source_detail`.

| Campo pedido | Hueco |
|---|---|
| feature ID | Lo da el `rowid` en la base; no está en el objeto |
| source signals, time window | Solo como texto en `source_detail` |
| method ID and version | Solo como texto en `source_detail` (p. ej. «beta_alpha_ratio \| Schutter 2006») |
| quality status | Falta |
| confidence only when justified | Hoy hay una confianza numérica por banda de procedencia (`CONFIDENCE_REFERENCE`) |
| limitations | Falta |

**Propuesta:** extender `PhysiologicalDescriptor` con campos opcionales (`method_id`, `window_s`, `quality`, `limitations`) con valor por omisión `None`. No cambia el significado de los campos existentes y es compatible con las filas viejas.

### 2.3 `PhysiologicalRelationship`

El antecedente más cercano son los acoplamientos:

- `CouplingRule`: condición, efecto, fuente, estado de validación, escenarios bloqueados y ventana;
- `AppliedCoupling`: valor observado, base, acoplado y confianza;
- el compositor por regla de la T6.

| Campo pedido | Hueco |
|---|---|
| relationship type (asociación, precedencia temporal, modelo, hipótesis causal, evidencia causal) | Hoy todo es «regla de modelo firmada» |
| estimate, time lag, uncertainty | Las reglas aplican un delta fijo; no se estima ninguna relación a partir de datos |

**Propuesta:** un registro de relación *estimada* (nuevo), separado de la regla *firmada* (existente). Así el *Physiological Intelligence Graph* muestra asociaciones medidas sin que se confundan con reglas aplicadas al paciente.

### 2.4 `SimulationScenario`

Hoy existe:

- `SimulationScenario`: enum de 15 escenarios en `app/engines/simulation_engine.py`;
- `run_rich_scenario`: condiciones iniciales, trayectoria con horizonte y semilla (`domain/physiology/scenarios/`);
- `render_sepsis_model_declaration`: qué está prescrito y qué calcula el motor.

**Huecos:** versión del modelo, supuestos y variables no disponibles como datos (hoy son texto en pantalla).

### 2.5 `ExperimentRecord`

No existe. Lo más cercano es el mapa de cohortes (`src/ml/`), que es exploratorio. El documento lo pone en la Fase 5 (Research Studio).

## 3. Decisiones propuestas

### AD-1 · Contratos como adaptadores sobre el UPS (Fase 1)

- **Problema:** los cinco contratos podrían terminar siendo un segundo UPS.
- **Propuesta:** tipos nuevos en `domain/physiology/contracts/`, sin persistencia propia, con adaptadores desde y hacia lo existente, más pruebas de paridad (el mismo dato da el mismo resultado por las dos vías).
- **Costo:** bajo; no rompe nada.
- **Decide:** Luis, al aprobar la Fase 1.

### AD-2 · Campos opcionales en `PhysiologicalDescriptor`

- **Propuesta:** `method_id`, `window_s`, `quality` y `limitations`, opcionales, con columnas nuevas que admiten nulos en `ups_values`.
- **Costo:** toca `domain/` y la base. Las filas viejas quedan con `NULL` y una migración aditiva no borra nada.
- **Decide:** aprobación de Luis (cambio de esquema).

### AD-3 · Corregir la inversión de capas `domain → app`

- **Problema:** 16 importaciones de `domain/` a `app.engines` y a `app.utils.physiological_state` (`01_DEPENDENCY_MAP.md` §2.1).
- **Propuesta:**
  - mover `DigitalTwinOrganism` y el motor de escenarios a `domain/physiology/engines/`;
  - dejar en `app/engines/` módulos que reexportan, para que ninguna importación vieja se rompa;
  - mover `persist_current_state` (o la parte que usa el dominio) junto al builder.
- **Costo:** medio. Toca `domain/` y su guardia, y unas 30 importaciones.
- **Decide:** aprobación de Luis.

### AD-4 · Retirar el código sin uso

- **Problema:** unos 30 archivos confirmados sin uso (`01_DEPENDENCY_MAP.md` §3), entre ellos `app/utils.py`, que queda tapado por el paquete y confunde a quien lo lee.
- **Propuesta, en una tanda:**
  - mover lo que tiene pruebas a un lugar explícito, o retirar sus pruebas con su motivo;
  - borrar el resto;
  - dejar el historial en el CHANGELOG.
- **Costo:** bajo en riesgo, pero es borrar módulos.
- **Decide:** aprobación de Luis (regla 7).

### AD-5 · Vocabulario de procedencia sin «Heurística» visible

- **Problema:** la etiqueta «Heurística (de ingeniería, no de estudio de cohorte)» se reparte por toda la plataforma (88 textos visibles).
- **Propuesta (pedido de Luis del 2026-11-19), para lo que se ve:**
  - fuente citada (método o cifra publicada, con su clave);
  - criterio BIOCORE firmado (decisiones de Luis con su fundamento, como el techo del BAR);
  - simulación;
  - sin dato.

  Un umbral sin fuente pierde su juicio en pantalla y se queda la medida. La insignia `BADGES.HEURISTIC` sigue existiendo para lo que no se muestra (por ejemplo, umbrales internos de calidad de los equipos).
- **Costo:** muchas pruebas fijan los rótulos y se mueven a propósito.
- **Decide:** ya decidido por Luis; se ejecuta en la tanda de heurísticas (`00_BASELINE_AUDIT.md` §4).

### AD-6 · El *Physiological Intelligence Graph* parte de los acoplamientos

- **Propuesta:**
  - el grafo muestra dos capas que no se mezclan: las reglas firmadas (aristas de modelo, con su ficha) y las relaciones *estimadas* de datos sincronizados del paciente (AD-1, `PhysiologicalRelationship`);
  - una relación estimada nunca se aplica al paciente sin firma;
  - la sincronización temporal usa la ventana firmada de cada regla (120 s) como límite.
- **Decide:** Luis, en la Fase 3.

### AD-7 · La guardia de `domain/` se mantiene

`test_ups_builder_schema_and_engine_untouched` no se debilita. Todo cambio en `domain/` se commitea con la aprobación de su tanda, y la guardia pasa después del commit. Así trabajaron las tandas T0 a T6.1.

### AD-8 · Aislamiento de datos en internet

- **Problema:** en Streamlit Cloud, la base es compartida y temporal (opción B declarada).
- **Propuesta:** dejarlo así hasta que exista identidad. La opción A (base real con cuentas) es una decisión grande: framework de autenticación y base gestionada.
- **Decide:** Luis (regla 7); fuera de las Fases 1–3.

## 4. Siguiente tanda propuesta

Por orden:

1. **Tanda de heurísticas** (ya pedida por Luis): ejecutar el plan de `00_BASELINE_AUDIT.md` §4, por laboratorio, con pruebas, suite completa y revisión independiente.
2. **Fase 1 · Diseño de contratos:** AD-1 y AD-2, con la matriz de la §2 de este documento afinada y pruebas de paridad. Se detiene para aprobación antes de tocar `domain/`.
3. **AD-3 y AD-4:** en tandas propias, cada una con su aprobación.
