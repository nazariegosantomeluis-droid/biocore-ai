# ECG Plug & Play (`hardware/ecg_plugplay/`)

Lee la placa de ECG (ESP32 DevKit V1 + AD8232) sin elegir puertos a mano. En la app lo usan la fuente «Hardware ESP32 en vivo» del Monitoreo y la pestaña «Placa en vivo (tutorial)» del ECG Lab (`app/supermodules/ecg_live/`). Las instrucciones para estudiantes están en esa pestaña; este archivo es para quien mantiene el código.

1. **Encuentra la placa sola**, en un hilo aparte: revisa los puertos cada segundo, se salta los de Bluetooth, prueba primero los chips USB conocidos (CP210x, CH340/CH9102, Espressif, FTDI, Arduino) y confirma que es un ECG por su saludo `ECG:HELLO` o por sus tramas `ECG:D`.
2. **Adquiere a 250 Hz** en un búfer circular y arma ventanas de 1000 muestras (4 s) con 50 % de solape.
3. **Revisa y limpia la señal al vuelo**: huecos de 1 o 2 muestras se interpolan y se marcan; si faltan más, no se inventan. Marca electrodo suelto y saturación del ADC; filtra 0.5–40 Hz (causal) y quita los 60 Hz.
4. **Pasa cada ventana válida al analizador en otro hilo**, quedándose solo con la más nueva, y avisa con la FC, las ondas, la señal limpia y, si no hay resultado, el motivo.
5. **Aguanta que se jale el cable**: si el puerto desaparece o pasan 2 s sin datos, cierra el puerto, vacía el búfer, avisa y vuelve a buscar.

**Procedencia (Art. I):** `SENSOR_REAL` solo mientras una placa real manda datos. La placa simulada, y cualquier placa que diga `sim=1` en su saludo, salen `SIMULACION`.

## Qué hay aquí

```
service.py         ECGAcquisitionService: el hilo que busca, adquiere y se recupera; latest_clean_segment()
ports.py           qué puertos se prueban y los errores en español
protocol.py        lectura de las líneas ECG:… que manda la placa
transport.py       lectura del puerto serial (pyserial)
preprocessing.py   huecos, saturación, electrodo suelto, filtro y calidad de cada ventana
ring_buffer.py     búfer circular: ventanas de 1000 con salto de 500
inference.py       puente al analizador (otro hilo); ModelAnalyzer, BiocoreAnalyzer, CompositeAnalyzer
simulator.py       placa simulada (suma de gaussianas por latido, propia y sin validar)
config.py          parámetros con sus valores por defecto; AD8232_GAIN_SOURCE
firmware/main.py   firmware de MicroPython para la ESP32
```

Pruebas: `tests/test_ecg_plugplay_unidad.py`, `_servicio.py`, `_serial.py` (puerto serial virtual y el firmware corriendo en la computadora con `machine` simulado; solo Linux y Mac), `_biocore.py` y `tests/test_ecg_live_app.py` (AppTest de la app completa).

## Cómo funciona

```
 placa ──USB──►  [hilo ecg-adquisicion]
                  buscando ──► verificando ──► conectado ──(cable fuera o 2 s sin datos)──► desconectado
                     ▲                            │                                            │
                     └────────────────────────────┼──── cierra el puerto y vacía el búfer ◄────┘
                                                  ▼
                 muestras ─► SamplePipeline ─► SlidingWindowBuffer ─► ventana + revisión de calidad
                                                                                │
                                                               [hilo ecg-inferencia] InferenceBridge
                                                               analizador ─► on_result / snapshot()
```

Los callbacks (`on_state`, `on_signal`, `on_result`, `on_warning`) corren en los hilos del servicio. En Streamlit no se llama `st.*` desde ellos: se lee `servicio.snapshot()`, como hacen `monitor_source.py` y `tutorial.py`.

## Uso desde código

```python
from hardware.ecg_plugplay import AcquisitionConfig, BiocoreAnalyzer, ECGAcquisitionService

servicio = ECGAcquisitionService(AcquisitionConfig(), BiocoreAnalyzer(fs=250.0),
                                 on_state=lambda e: print(e.state.value, '-', e.message))
servicio.start()          # no bloquea
snap = servicio.snapshot()
servicio.stop()           # cierra el puerto (también pasa solo al salir)
```

- `latest_clean_segment(snap, min_seconds=4.0)` devuelve el tramo más reciente sin electrodo suelto, pérdidas ni saturación (para pantallas que rechazan NaN, como `validate_signal`), o `None` y el motivo.
- Un modelo propio entra con `ModelAnalyzer(modelo, method='procesar_ventana')`: recibe `np.ndarray` float32 `(1, 1000)` entre 0 y 1. Con `CompositeAnalyzer([BiocoreAnalyzer(fs=250.0), ModelAnalyzer(...)])` la predicción es del modelo y la FC y las ondas, de BIOCORE.
- Un modelo lento no frena la lectura: el puente se queda con la ventana más nueva y cuenta las descartadas (`descartadas_por_lentitud`).

### Lo que entrega cada resultado (`WindowResult`)

| Campo | Qué es |
|---|---|
| `valid` / `reasons` | si la ventana pasó la revisión y el análisis no falló; si no, por qué, en español |
| `bpm` | FC, o `None` con el motivo en `notes` |
| `waves` | `{'beat_0': {'P': {'index', 'amplitude'}, 'Q': …, 'R': …, 'S': …, 'T': …, 'QRS': {'onset', 'offset', 'duration_ms'}}, …}`; una onda que no se detectó no aparece |
| `prediction` | lo que devuelva el modelo, si hay uno |
| `labels` | de dónde salió cada dato |
| `window` | `ecg_mv`, `raw` (cuentas del ADC), `flags` por muestra, `quality`, `model_input`, `provenance`, `source`, `start_seq` |

### `BiocoreAnalyzer`

- **FC**: `ECGAnalyzer.detect_r_peaks_tkeo` y 60·fs / RR medio, como el resto del ECG Lab. El módulo no trae otro detector a propósito: BIOCORE ya unificó la FC sobre TKEO (Bug 2).
- **Q, R, S y duración del QRS**: `clinical.qrs_delineation.delineate_qrs` sobre cada pico TKEO. No se usa `segment_qrs_complex` porque pone la Q encima de la S.
- **P y T**: heurística del módulo, no validada: la mayor desviación respecto a la línea isoeléctrica (R−120 a R−80 ms) en ventanas fisiológicas antes y después del QRS.
- **Patrón por reglas** (`pattern=True`, apagado por defecto): `classify_ecg_signal`, que son reglas, no ML. Solo se entrega si su detector y el TKEO coinciden (±50 ms) y sus intervalos son fisiológicos; hoy casi nunca pasa.
- Cada parte va por separado: si una falla en una ventana, las demás se entregan.

## La placa

| AD8232 | ESP32 |
|---|---|
| 3.3V | 3V3 (no a 5 V) |
| GND | GND |
| OUTPUT | GPIO34 |
| LO+ | GPIO35 |
| LO− | GPIO32 |
| SDN | sin conectar |

Firmware: guardar `firmware/main.py` en la placa como `main.py` con Thonny, cerrar Thonny y presionar EN. Placa simulada en un puerto virtual (Linux y Mac): `python -m hardware.ecg_plugplay.simulator --pty --hr 80`.

### Protocolo

```
placa → PC   ECG:HELLO,fw=1.0,fs=250,bits=12,vref=3.3,gain=1100,blk=10,tarde=0,perdidas=0
             ECG:D,<seq>,<lo>,<v1>,...,<v10>     seq = índice de la primera muestra; lo: 1 = LO+, 2 = LO−
             ECG:<v>[,<lo>]                      una muestra por línea (sin seq)
             ECG:E,<texto>                       mensaje de la placa
PC → placa   ECG?                                pide el HELLO
```

`sim=1` en el HELLO marca a la placa como simulador; `filt=1`, que la placa ya filtra. Con `ECG:D`, `seq` permite detectar muestras perdidas y un reinicio de la placa.

### Configuración (`AcquisitionConfig`)

| Parámetro | Por defecto | Para qué |
|---|---|---|
| `fs`, `window_size`, `overlap` | 250, 1000, 0.5 | frecuencia y ventanas |
| `port` | `None` | fija un puerto y salta la búsqueda |
| `data_timeout_s` | 2.0 | segundos sin datos para darla por desconectada |
| `bandpass_hz`, `notch_hz` | `(0.5, 40)`, 60 | filtro (red de 60 Hz en México) |
| `accept_legacy` | `False` | acepta el formato viejo `ts,valor` (las placas de EMG usan el mismo) |
| `wake_micropython`, `assert_dtr` | `False` | manda Ctrl-D si ve `>>>`; DTR para placas con USB nativo |

Los umbrales para descartar ventanas están en `QualityHeuristics` (heurísticos, sin criterio clínico citado).

## Límites

- **No se ha probado con la placa real.** Todo pasó con el simulador, con un puerto serial virtual y con el firmware corriendo en la computadora.
- Una sola derivación: ritmo y FC, no eje ni comparación con 12 derivaciones.
- 0.5–40 Hz es banda de monitoreo: un corte bajo de 0.5 Hz deforma el ST y el diagnóstico pide ≥150 Hz arriba (`FILTER_LIMITS_SOURCE`, Kligfield 2007).
- Los mV son aproximados: ganancia supuesta de 1100 (`AD8232_GAIN_SOURCE`, hoja de datos del AD8232), sin calibrar.
- En MicroPython el Timer puede atrasarse; el firmware cuenta las muestras tardías y las reporta en el HELLO (`tarde`).
