# Tarjeta del modelo: clasificador de latidos (`lgbm-8rasgos-ds1-v1`)

Fecha de la evaluación: 2026-11-17. Las cifras de esta tarjeta están copiadas de `results.json`, en esta misma carpeta. Si alguna no coincide, vale la de `results.json`, que es lo que lee el panel de la app.

**Estado: en evaluación.** Hay cuatro clases (S, V, F y Q) con sensibilidad menor que 0.80. Ese umbral es Criterio BIOCORE, sin cita.

## Uso previsto

Uso **educativo**: sirve para mostrar cuánto acierta un clasificador sencillo cuando se lo mide con honestidad. **No es apto para diagnóstico ni para decisiones clínicas.** Ninguna pantalla de BIOCORE lo usa para clasificar. Solo aparece como esta tarjeta, en ECG → Monitoreo → «Cómo se calcula».

## Qué es el modelo

- **Código.** `biomedical/arrhythmia_classifier.py`. Es una clase genérica que entrena RandomForest y, si están instalados, XGBoost y LightGBM, sobre segmentos que recibe ya cortados.
- **Lo que había antes de esta evaluación.** El repositorio no tenía ningún modelo entrenado ni métricas guardadas. La única prueba de la clase (`tests/test_arrhythmia_classifier_new.py`) la entrena con 20 senos y ondas cuadradas sintéticas.
- **Rasgos.** Son los 8 de `extract_features`, todos de amplitud del segmento: media, desviación, rango, máximo, mínimo, energía, mediana y entropía de Shannon (histograma de 32 intervalos). **No hay rasgos de intervalo RR.** Por eso no puede distinguir un latido prematuro supraventricular, que tiene forma casi normal y se reconoce por su adelanto.
- **Modelo evaluado.** `LGBMClassifier` con los parámetros por defecto de la clase. Solo se fijaron `random_state=42`, `deterministic=True` y `force_row_wise=True`. Sin el determinismo, dos corridas iguales dieron sensibilidad de N de 0.9047 y de 0.9003.
- **Nombres de columna.** Se entrena y se predice con un `DataFrame` que tiene los mismos nombres de columna, así que no aparece el aviso «X does not have valid feature names». Hay una prueba que lo exige.
- **Archivo del modelo.** Se guarda fuera de git, en `$BIOCORE_CACHE_DIR/models/lgbm-8rasgos-ds1-v1.joblib` (por defecto, `.cache/biocore` en la raíz del repositorio), con SHA-256 `2621b367…5e51024`. El hash completo está en `results.json`.

## Datos

- **Base.** MIT-BIH Arrhythmia Database, PhysioNet `mitdb`, versión 1.0.0, a 360 muestras/s. Se usa la derivación MLII, sin filtro.
- **Ventana del latido.** Va de 0.25 s antes a 0.45 s después de la anotación R del cardiólogo. Es Criterio BIOCORE: la clase no fija ventana.
- **Clases AAMI** (ANSI/AAMI EC57, agrupación de de Chazal 2004):

  | Clase | Anotaciones |
  |---|---|
  | N | N, L, R, e, j |
  | S | A, a, J, S |
  | V | V, E |
  | F | F |
  | Q | /, f, Q |

  Las anotaciones que no son latidos se descartan, por ejemplo `+`, `~`, `|` y `!`.

## Separación entre pacientes

Entrenamiento con DS1 y evaluación con DS2. Es el esquema de de Chazal P, O'Dwyer M, Reilly RB, IEEE Trans Biomed Eng 2004;51(7):1196–1206, doi:10.1109/TBME.2004.827359. Quedan fuera los 4 registros con marcapasos: 102, 104, 107 y 217.

- **DS1 (entrenamiento):** 101, 106, 108, 109, 112, 114, 115, 116, 118, 119, 122, 124, 201, 203, 205, 207, 208, 209, 215, 220, 223, 230.
- **DS2 (evaluación):** 100, 103, 105, 111, 113, 117, 121, 123, 200, 202, 210, 212, 213, 214, 219, 221, 222, 228, 231, 232, 233, 234.
- **De dónde salen las listas.** No se pudo leer la tabla del artículo original (es de pago); su resumen en PubMed confirma 44 registros sin marcapasos repartidos en dos grupos de 22. Las listas se verificaron en Farag MM, Sensors 2023;23(3):1365, doi:10.3390/s23031365, PMC9919183, tabla 2, que cita a de Chazal 2004. Coinciden con García G et al., Sci Rep 2017;7:10543, PMC5585360, tabla 3, que imprime «11» por 111, una errata. También coinciden con Zou C et al., IEEE J Transl Eng Health Med 2022;10:1900508, PMC9455809, tabla 1.
- **Prueba.** `tests/test_arrhythmia_model_card.py` exige que ningún registro de evaluación esté entre los de entrenamiento.

Latidos usados:

| Clase | DS1 (entrenamiento) | DS2 (evaluación) |
|---|---|---|
| N | 45 848 | 44 240 |
| S | 944 | 1 837 |
| V | 3 788 | 3 220 |
| F | 414 | 388 |
| Q | 8 | 7 |

## Fuga de datos en el protocolo original

`ArrhythmiaClassifier.train` separa con `train_test_split(test_size=0.2, stratify=y)` **por latido**. Para medir la fuga, ese mismo protocolo se aplicó a los latidos de DS1 y DS2 juntos. Resultado: los **44 de 44 registros** quedan a la vez en entrenamiento y en prueba, así que el modelo se evalúa con latidos de pacientes que ya vio.

| Métrica | Por latido (con fuga) | Entre pacientes (DS1 → DS2) |
|---|---|---|
| Exactitud | 0.944 | 0.843 |
| F1 macro | 0.531 | 0.299 |
| Sensibilidad S | 0.424 | 0.007 |
| Sensibilidad V | 0.820 | 0.644 |
| Sensibilidad F | 0.369 | 0.018 |

Las cifras por latido están infladas y no se usan. Se reportan solo como evidencia de la fuga.

## Métricas entre pacientes (DS2, latidos que el modelo no vio)

| Clase | Latidos | Sensibilidad | Valor predictivo positivo | F1 |
|---|---|---|---|---|
| N | 44 240 | 0.899 | 0.930 | 0.914 |
| S | 1 837 | 0.007 | 0.012 | 0.008 |
| V | 3 220 | 0.644 | 0.502 | 0.565 |
| F | 388 | 0.018 | 0.004 | 0.007 |
| Q | 7 | 0.000 | 0.000 | 0.000 |

- **F1 macro: 0.299.** Es la media del F1 de las 5 clases que tienen latidos en DS2.
- **Exactitud global: 0.843.** **Esta cifra engaña**, porque N es el 89 % de DS2 (44 240 de 49 692 latidos). Un modelo que siempre dijera N tendría 0.890, más que este modelo.
- **Matriz de confusión** (filas: verdad; columnas: predicción): `confusion_matrix.png`.

## Calibración

- **Puntaje de Brier: 0.291.** Es la forma multicategoría de Brier (1950): la media, sobre los latidos, de Σₖ (pₖ − oₖ)², con 5 clases. 0 es perfecto y 2 es el peor valor posible.
- **Curva de confiabilidad: `reliability_curve.png`.** Toma la clase elegida y, en 10 intervalos de confianza, compara la confianza media con la fracción de aciertos.
- **Lectura.** El 87 % de los latidos (43 138) cae en el intervalo de confianza 0.9–1.0, donde la confianza media es 0.986 y el acierto 0.860. El modelo está **sobreconfiado** justo donde concentra casi todas sus respuestas.

## Limitaciones

1. **Sin rasgos de RR.** S es prácticamente indetectable (sensibilidad 0.007). Este resultado es esperable y no es un error de la evaluación.
2. **Rasgos que dependen de la línea de base.** Media, mediana, máximo y mínimo cambian con la deriva de la línea de base y con la ganancia de cada registro, y la señal no se filtra. Eso favorece memorizar al paciente: es justo lo que la separación por latido premia y la separación entre pacientes castiga.
3. **Q tiene 7 latidos en DS2 y F tiene 388.** Sus cifras son muy inestables.
4. **Una sola base, una derivación y 44 personas.** Las cifras no se pueden trasladar a otra placa, a otra derivación ni a otra población.
5. **La clase entrena otros dos modelos.** RandomForest y XGBoost no se evaluaron aquí; esta tarjeta describe solo LightGBM.
6. **No hay modelo anterior que comparar.** El repositorio nunca guardó uno. `lgbm-8rasgos-ds1-v1` es la primera versión persistida y se guarda fuera de git, porque `*.pkl` está en `.gitignore`.

## Cómo reproducir

Todos los comandos se corren desde la raíz del repositorio. La base y el modelo viven fuera de git, en la carpeta `$BIOCORE_CACHE_DIR`; si la variable no está fijada, la carpeta es `.cache/biocore` en la raíz del repositorio (`.cache/` está en `.gitignore`).

1. **Elegir la carpeta** (opcional; sin este paso se usa `.cache/biocore`):

   ```bash
   # Git Bash
   export BIOCORE_CACHE_DIR="$HOME/biocore_cache"
   ```

   ```powershell
   # PowerShell
   $env:BIOCORE_CACHE_DIR = "$HOME\biocore_cache"
   ```

2. **Descargar la base** a `$BIOCORE_CACHE_DIR/mitdb` (unos 90 MB):

   ```bash
   python -c "from domain.physiology.ml.arrhythmia_evaluation import CACHE_DIR; import wfdb; wfdb.dl_database('mitdb', dl_dir=str(CACHE_DIR / 'mitdb'))"
   ```

3. **Correr la evaluación**, sin argumentos. Lee la base de `$BIOCORE_CACHE_DIR/mitdb`, guarda el modelo en `$BIOCORE_CACHE_DIR/models/lgbm-8rasgos-ds1-v1.joblib` y escribe `results.json` y los dos PNG en esta carpeta (unos 45 s):

   ```bash
   python -m domain.physiology.ml.arrhythmia_evaluation
   ```

4. **Correr las pruebas de la tarjeta:**

   ```bash
   python -m pytest tests/test_arrhythmia_model_card.py -q
   ```

Entorno de la corrida: Python 3.13.11, lightgbm 4.6.0, scikit-learn 1.9.0, NumPy 2.4.6 y wfdb 4.3.1. Con `deterministic=True`, dos corridas seguidas dieron un `results.json` idéntico byte a byte. No se probó con otras versiones de lightgbm.
