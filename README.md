# BIOCORE AI

**Un laboratorio digital de fisiología humana para enseñar medicina, construido sobre una regla: nunca finge lo que no sabe.**

BIOCORE AI es una plataforma educativa de fisiología humana para estudiantes de medicina y ciencias de la salud. En lugar de enseñar con texto estático, enseña con un **gemelo digital reactivo**: un organismo virtual **simulado** (la plataforma lo declara así en pantalla) cuyo estado fisiológico se altera con escenarios clínicos y se explica con fundamento, junto a laboratorios que analizan señales reales.

La tesis: aprender medicina no es leer una buena explicación, es intentar, equivocarse y ser corregido con fundamento.

---

## Qué lo hace distinto

La mayoría de las plataformas educativas médicas *suenan* clínicas sin serlo: muestran números con apariencia de métrica que nadie calculó, etiquetas que parecen diagnósticos sin un algoritmo detrás. Para una herramienta que forma médicos, un dato falso que suena convincente es lo más peligroso que puede haber.

BIOCORE se construyó sobre la regla opuesta, que gobierna toda su arquitectura:

> **Cada dato declara su procedencia. Cuando el sistema no puede saber algo, lo dice — nunca rellena el hueco con algo plausible.**

Cada valor sabe de dónde viene y lo declara: **medido**, **simulado**, **referencia clínica citada**, **derivado** o **calculado por modelo**. Cuando falta señal para un cálculo, el sistema devuelve «no disponible» con el motivo. Cuando un módulo se sabe defectuoso, lo marca en pantalla en lugar de esconderlo: hoy, **Respiratory Lab está en corrección** y muestra su frecuencia respiratoria, su AHI y el conteo de respiraciones como «no fiable».

---

## Arquitectura

**UPS (Unified Physiological State) — el estado fisiológico unificado.** La fuente única de verdad del paciente, con procedencia y confianza por valor. Modela cuatro dominios: cardiovascular, respiratorio, neurológico y muscular.

**Motor hemodinámico.** Reimplementación analítica, en Python, de las ecuaciones del bloque RCR de svZeroDSolver (no es el solver ni lo usa como dependencia; ver [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)), con un lazo cerrado propio que hoy tiene habilitados tres escenarios. Modela el shock establecido: fuera de esa fase la presión arterial se declina con su motivo, no se inventa.

**Cuatro hubs, doce entradas de menú** (definidos en `HUBS`, `app/main.py`):
- **Digital Twin OS** — el organismo simulado: órganos que reaccionan al UPS, escenarios, casos clínicos, línea de tiempo.
- **Learning Hub** — Academia Clínica: quiz, casos clínicos ciegos y tabla de 12 derivaciones.
- **Clinical Hub** — ECG Lab, Multisensor Fusion Lab, Respiratory Lab (en corrección), EEG Neuro Lab, EMG Muscle Lab, HRV Analysis, Biomarkers Lab, Calculadoras Clínicas y Patient Pipeline.
- **Laboratorio 3D** — «Crea tu modelo 3D»: reconstrucción desde TC/RM, anatomía de referencia no reactiva, mapa EEG y vectocardiograma, cada pestaña con su nivel de evidencia declarado.

**Procesamiento de señal.** El detector de latidos del ECG Lab (frecuencia cardíaca por operador de Teager-Kaiser) se validó contra una cohorte de registros del MIT-BIH Arrhythmia Database en rondas con un experto; el detector de bloqueos de rama tiene una prueba contra 50 registros reales de PTB-XL. El EEG calcula potencia por bandas con cocientes citados y el exponente aperiódico (FOOOF). HRV sigue las métricas de la Task Force ESC/NASPE. En EMG, la frecuencia mediana es un cálculo real; la activación es la media/máximo de la señal filtrada (una heurística, no un porcentaje de la contracción máxima).

**IA.** Todo uso de un modelo de lenguaje (API de Anthropic) pasa por el paquete del narrador, `domain/physiology/narrator/`: narración clínica, razonamiento causal y retroalimentación de casos y quiz. Explica en palabras datos que ya están en el UPS; es opcional y está apagado sin clave, sin modo simulado de respaldo. Los índices de riesgo y las explicaciones por contribución son reglas y pesos fijos, y así se etiquetan; la única otra pieza de aprendizaje automático es el mapa de cohortes del Laboratorio 3D, un análisis exploratorio declarado como tal.

---

## Estado del proyecto

BIOCORE está en desarrollo activo. El registro de qué se hizo, qué se corrigió y qué se descartó es [`CHANGELOG.md`](CHANGELOG.md); el inventario de qué es real, heurístico, simulado o defectuoso está en [`docs/INVENTARIO_BIOCORE_2026-11-05.md`](docs/INVENTARIO_BIOCORE_2026-11-05.md) (fotografía del 5 de noviembre de 2026, anterior a las correcciones posteriores que cuenta el CHANGELOG). La suite de pruebas se ejecuta con `pytest` y no escribe en la base de datos de desarrollo.

---

## Instalación

Desarrollado y probado en Python 3.13; otras versiones no se han probado (el devcontainer usa 3.11).

```bash
git clone <url-del-repositorio>
cd biocore-public
pip install -r requirements.txt
streamlit run app/main.py
```

La aplicación se abre en el navegador. Los datos de señal se generan por escenario o se cargan desde archivos; no hace falta ninguna clave de API para el uso base. Detalles en [`SETUP.md`](SETUP.md).

---

## Licencia

Este proyecto se distribuye bajo una licencia de fuente disponible, no comercial. El código es visible para revisión, estudio y evaluación, pero su uso comercial requiere acuerdo con el titular. Ver [`LICENSE`](LICENSE) para los términos completos. Los componentes de terceros (ecuaciones, datos, librerías) conservan sus licencias y sus citas: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

© 2026 Luis Nazariego Santome.
