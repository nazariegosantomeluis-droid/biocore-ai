# Hoja de firma v2: banco de preguntas de EMG y HRV (E1–E10, H1–H8), 17 de noviembre de 2026

**Qué se revisó:** `docs/contenido/banco_preguntas_emg_hrv.md` en `2d567fd` (rama `origin/calibracion-confianza`), frente a `teoria_citada_2.md`. El archivo de la teoría es idéntico en `2d567fd` y en la punta de la rama, así que los números «t2:N» de la v2 apuntan a las líneas correctas. Revisión de solo lectura: no se modificó ningún repositorio.

**Cómo se empató con la hoja anterior:** pregunta por pregunta, por su contenido. Las 18 coinciden en número con la v1: la v2 solo renumeró las [N] y los casos, que pasaron al apéndice.

**Reglas aplicadas:**
- El enunciado, la respuesta correcta y la explicación solo afirman lo que dice una línea firmada.
- Los distractores son falsos por definición. Se aceptan si alguna línea firmada los refuta y si no meten un factor que la teoría excluye, como la temperatura en B7.
- La **explicación** se copia de la línea t2:N. Solo se quitan las marcas que no son texto: «Idea.», «Mecanismo.» y «Detalle.», los `**`, la viñeta y la clave entre corchetes (que va en `source`). En una fila de tabla, «| A | B |» se escribe «A: B.».
- La comprobación es por ejecución: `banco_v2_propuesto.py` (en este scratchpad) verifica que cada explicación es una subcadena de la línea t2:N indicada.

## Lo que la v2 no corrigió (y bloquea la integración)

1. **Explicaciones.** Solo E1 y E2 traen `*Explicación:*`. Las otras 16 traen la línea firmada como cita, pero no como explicación. `tests/test_quiz_bank.py:43` exige `q.explanation.strip()`, así que las 16 fallarían.
2. **La correcta es la opción más larga** en 10 de 10 preguntas de EMG y en 5 de 8 de HRV. `test_the_correct_answer_is_not_given_away_by_being_the_longest` (la siguiente prueba del mismo archivo) admite como máximo 40 % de cada banco: 4 en EMG y 3 en HRV. Con las correcciones de abajo quedan **3 en EMG (E1, E6, E9) y 3 en HRV (H4, H5, H7)**.
3. **Lo señalado en la hoja anterior que sigue igual:**
   - E3: «cuál de las dos ocurrió».
   - Distractores de E4 y E6.
   - H3: «influida por la temperatura».
   - H5: la respuesta generaliza.
   - H6: «Solo cambian en mujeres».
   - H7: «con menos sesgo y más fiabilidad».
   - E2: «sobre todo» y «no necesariamente».
4. **Lo que la v2 sí corrigió bien:** quitó «riesgo de lesión» de E2 y la cifra de SDNN de H8.

**Comprobado con `banco_v2_propuesto.py`:**
- Las 18 preguntas tienen 4 opciones distintas y ningún enunciado contiene la respuesta correcta.
- Las explicaciones de las 17 corregidas son literales.
- No aparece ningún término de `FORBIDDEN` ni de `TREATMENT` («se recomienda» no coincide con `recomendaci`).

## Resumen

| v2 | v1 (por contenido) | Veredicto | En una línea |
|---|---|---|---|
| E1 | E1 | FIRMAR TAL CUAL | Literal de t2:13; ya tiene explicación |
| E2 | E2 | FIRMAR CON CORRECCIÓN | «sobre todo» y «no necesariamente» fuera de t2:17; explicación no literal |
| E3 | E3 | FIRMAR CON CORRECCIÓN | Los dos mecanismos actúan juntos (t2:21, t2:25); falta explicación |
| E4 | E4 | FIRMAR CON CORRECCIÓN | Distractor del archivo; falta explicación |
| E5 | E5 | FIRMAR CON CORRECCIÓN | Falta explicación |
| E6 | E6 | FIRMAR CON CORRECCIÓN | Distractor de los microvoltios; falta explicación |
| E7 | E7 | FIRMAR CON CORRECCIÓN | Falta explicación |
| E8 | E8 | FIRMAR CON CORRECCIÓN | Falta explicación |
| E9 | E9 | FIRMAR CON CORRECCIÓN | Falta explicación |
| E10 | E10 | FIRMAR CON CORRECCIÓN | Falta explicación |
| H1 | H1 | FIRMAR CON CORRECCIÓN | Falta explicación |
| H2 | H2 | FIRMAR CON CORRECCIÓN | Distractores que no son medidas; falta explicación |
| H3 | H3 | FIRMAR CON CORRECCIÓN | Temperatura fuera de B7; falta explicación |
| H4 | H4 | FIRMAR CON CORRECCIÓN | Falta explicación |
| H5 | H5 | FIRMAR CON CORRECCIÓN | La respuesta generaliza t2:136; falta explicación |
| H6 | H6 | FIRMAR CON CORRECCIÓN | «Solo en mujeres»; falta explicación |
| H7 | H7 | FIRMAR CON CORRECCIÓN | Debe decir «menos sesgada y más fiable»; falta explicación |
| H8 | H8 | FIRMAR CON CORRECCIÓN | Falta explicación |

**QUITAR: ninguna.** Ninguna corrección necesita texto que no esté firmado.

**Además, al integrar:**
- **Barajar las opciones.** Hay que envolver `EMG_QUESTIONS` y `HRV_QUESTIONS` en `balance_positions(...)`, como los otros bancos.
- **Registrar el concepto.** `record_quiz_answer` solo registra una pregunta si su enunciado está en `CONCEPT_BY_PROMPT`. Además, `QUIZ_BANKS` de `app/utils/confidence.py` y la prueba `test_cada_pregunta_mapeada_existe_y_usa_el_vocabulario_de_luis` solo miran `academia` y `ecg12`. Hasta que se amplíen, las 18 preguntas no entran al registro de la sesión con `emg`/`hrv`.

---

## Parte 1. Cada pregunta

### E1 — FIRMAR TAL CUAL

**Motivo:** Respuesta literal de t2:13; la explicación de la v2 («el electrodo capta la suma de los potenciales de las unidades motoras que tiene debajo») resume t2:13 sin añadir nada.

Se integra tal como está en la v2 (enunciado, opciones y explicación).

### E2 — FIRMAR CON CORRECCIÓN

**Motivo:** La v2 quitó «riesgo de lesión», pero dejó «sobre todo» y «no necesariamente mayor fuerza», que no están en t2:17 (que dice «no su fuerza»). Su explicación no es literal y mete t2:66. El distractor del espectro se cambia por uno que t2:62 refuta.

- **Enunciado:** ¿Qué indica una amplitud más alta del EMG de superficie?
- **Opciones** (la correcta primero):
  1. ✅ Mayor excitación del músculo, no su fuerza
  1. Mayor fuerza muscular, en proporción directa
  1. Mayor fuerza muscular, siempre que la señal esté normalizada
  1. Mayor masa muscular
- **Explicación** (literal de t2:17, t2:62): La amplitud del EMG de superficie indica la excitación del músculo, no su fuerza. Incluso normalizada, la amplitud no permite deducir la fuerza del músculo.
- **Fuente:** [V2018] · **Concepto:** `emg`

### E3 — FIRMAR CON CORRECCIÓN

**Motivo:** Sin cambios desde la v1. «Cuál de las dos ocurrió» sugiere que se excluyen. El enunciado nuevo copia t2:21, y la pregunta sigue a t2:25 («cuánto se debe al reclutamiento y cuánto a la frecuencia de disparo»): los dos mecanismos actúan juntos. Faltaba la explicación.

- **Enunciado:** El músculo aumenta su fuerza de dos maneras: activando unidades motoras nuevas (reclutamiento) y haciendo que las ya activas disparen más rápido. ¿Puede la amplitud del EMG de superficie decir cuánto del aumento se debe a cada una?
- **Opciones** (la correcta primero):
  1. ✅ No: la amplitud no permite distinguir cuánto se debe a cada una
  1. Sí: si la amplitud sube, todo el aumento se debe al reclutamiento
  1. Sí: si la amplitud sube, todo el aumento se debe a la frecuencia de disparo
  1. Sí, siempre que la señal esté normalizada
- **Explicación** (literal de t2:25): Con la amplitud del EMG de superficie no se puede distinguir cuánto se debe al reclutamiento y cuánto a la frecuencia de disparo.
- **Fuente:** [DL1997][V2018] · **Concepto:** `emg`

### E4 — FIRMAR CON CORRECCIÓN

**Motivo:** La v2 conserva «Para reducir el tamaño del archivo» (no es plausible) y no tiene explicación. La correcta se acorta a su primera razón, para que no sea siempre la opción más larga; t2:45 refuta el distractor de la energía.

- **Enunciado:** ¿Por qué se recomienda un filtro pasa-altas de 20 Hz para el EMG de superficie?
- **Opciones** (la correcta primero):
  1. ✅ Porque el artefacto de movimiento concentra su energía en frecuencias bajas
  1. Para eliminar la interferencia de la red eléctrica
  1. Porque por debajo de 20 Hz está la mayor parte de la energía de la señal muscular
  1. Para eliminar la diafonía de los músculos vecinos
- **Explicación** (literal de t2:45): Pasa-altas de 20 Hz (Butterworth, 12 dB/octava) para uso general: el artefacto de movimiento concentra su energía en frecuencias bajas y cae rápidamente por encima de 20 Hz; la energía del EMG por debajo de 20 Hz es poca e inestable.
- **Fuente:** [DL2010] · **Concepto:** `emg`

### E5 — FIRMAR CON CORRECCIÓN

**Motivo:** Contenido correcto, pero la v2 perdió la explicación. El distractor del valor rectificado ahora es el espejo exacto de t2:54, así que la correcta deja de ser la más larga.

- **Enunciado:** Para medir la amplitud de una contracción voluntaria, ¿qué medida se recomienda y por qué?
- **Opciones** (la correcta primero):
  1. ✅ El RMS, porque representa la potencia de la señal y tiene un significado físico claro
  1. El valor medio rectificado, porque representa la potencia de la señal y tiene un significado físico claro
  1. El valor máximo, porque es el más estable
  1. La frecuencia mediana, porque no depende de la amplitud
- **Explicación** (literal de t2:54): El RMS representa la potencia de la señal y tiene un significado físico claro; el valor medio rectificado mide el área bajo la señal y no tiene un significado físico específico.
- **Fuente:** [DL1997] · **Concepto:** `emg`

### E6 — FIRMAR CON CORRECCIÓN

**Motivo:** La v2 conserva «los equipos no pueden medir microvoltios» y no tiene explicación. Ese distractor se cambia por uno que refutan t2:25 y t2:88.

- **Enunciado:** ¿Por qué suele normalizarse la amplitud del EMG, por ejemplo a la contracción voluntaria isométrica máxima?
- **Opciones** (la correcta primero):
  1. ✅ Porque los microvoltios no se pueden comparar entre personas, músculos o sesiones
  1. Porque así la amplitud se vuelve igual a la fuerza
  1. Porque así se elimina el artefacto de movimiento
  1. Porque así se puede distinguir el reclutamiento de la frecuencia de disparo
- **Explicación** (literal de t2:58, t2:62): La amplitud en microvoltios no se puede comparar entre personas, músculos o sesiones; por eso suele normalizarse, por ejemplo a la contracción voluntaria isométrica máxima. Incluso normalizada, la amplitud no permite deducir la fuerza del músculo.
- **Fuente:** [V2018] · **Concepto:** `emg`

### E7 — FIRMAR CON CORRECCIÓN

**Motivo:** Era FIRMAR, pero la v2 perdió la explicación. «Más altas; RMS» pasa a «más altas; frecuencia mediana»: solo cambia el sentido del desplazamiento, y la correcta deja de ser la más larga.

- **Enunciado:** Durante una contracción sostenida, ¿qué le ocurre al espectro del EMG y qué índice se usa para seguirlo?
- **Opciones** (la correcta primero):
  1. ✅ Se desplaza hacia frecuencias más bajas; se sigue con la frecuencia mediana
  1. Se desplaza hacia frecuencias más altas; se sigue con la frecuencia mediana
  1. No cambia; solo cambia la amplitud
  1. Se desplaza hacia frecuencias más bajas; se sigue con el valor máximo
- **Explicación** (literal de t2:66): Durante una contracción sostenida, el espectro del EMG se "comprime" hacia frecuencias más bajas, y la frecuencia mediana es el índice preferido para seguir ese cambio.
- **Fuente:** [DL1997] · **Concepto:** `emg`

### E8 — FIRMAR CON CORRECCIÓN

**Motivo:** Contenido correcto; falta la explicación. Al distractor del artefacto se le añade el mismo final que a la correcta, para que esta no sea la más larga.

- **Enunciado:** Un electrodo sobre un músculo capta también parte de la actividad de los músculos vecinos. ¿Cómo se llama esto y hasta cuánto puede llegar?
- **Opciones** (la correcta primero):
  1. ✅ Diafonía (crosstalk): hasta 17 % de la actividad de los músculos vecinos
  1. Artefacto de movimiento: hasta 17 % de la actividad de los músculos vecinos
  1. Diafonía: siempre menos de 1 %
  1. Fatiga: hasta 50 %
- **Explicación** (literal de t2:77): Diafonía (crosstalk): hasta 17 % de la actividad eléctrica de músculos vecinos puede detectarse en el electrodo.
- **Fuente:** [DL1997] · **Concepto:** `emg`

### E9 — FIRMAR CON CORRECCIÓN

**Motivo:** Contenido correcto; falta la explicación (con t2:86 y t2:87 refuta también los distractores). Se quitan los ** de «sí» del enunciado: ningún banco usa Markdown.

- **Enunciado:** ¿Cuál de estas conclusiones sí permite, con cautela, un EMG de superficie?
- **Opciones** (la correcta primero):
  1. ✅ Decir si un músculo está «encendido» o «apagado» en intervalos de más de unos 200 ms
  1. Calcular la fuerza del músculo en newtons
  1. Predecir cuánto crecerá el músculo con el entrenamiento
  1. Comparar la fuerza de dos personas por su amplitud en microvoltios
- **Explicación** (literal de t2:89, t2:86, t2:87): Sí permite, con cautela, decir si un músculo está "encendido" o "apagado" en intervalos de más de unos 200 ms, y hacer comparaciones dentro de la misma persona y el mismo músculo si se controlan las condiciones. No permite deducir la fuerza muscular. No predice la hipertrofia ni la adaptación a largo plazo.
- **Fuente:** [V2018] · **Concepto:** `emg`

### E10 — FIRMAR CON CORRECCIÓN

**Motivo:** Contenido correcto; falta la explicación. La correcta se acorta, porque la explicación ya da la frase completa, y así deja de ser la más larga.

- **Enunciado:** Un ejercicio produce más amplitud de EMG que otro en el mismo músculo. ¿Permite eso afirmar que producirá más hipertrofia?
- **Opciones** (la correcta primero):
  1. ✅ No: la amplitud no predice la hipertrofia
  1. Sí: más amplitud implica más hipertrofia a largo plazo
  1. Sí, si la diferencia es mayor de 20 %
  1. Solo si la señal está normalizada
- **Explicación** (literal de t2:87): No predice la hipertrofia ni la adaptación a largo plazo.
- **Fuente:** [V2018] · **Concepto:** `emg`

### H1 — FIRMAR CON CORRECCIÓN

**Motivo:** Era FIRMAR, pero la v2 perdió la explicación. t2:103 (mismo tema B1) refuta el distractor de las arritmias.

- **Enunciado:** ¿Qué es la variabilidad de la frecuencia cardiaca (HRV)?
- **Opciones** (la correcta primero):
  1. ✅ La variación del tiempo entre latidos consecutivos
  1. El número de latidos por minuto
  1. La diferencia entre la frecuencia cardiaca máxima y la mínima del día
  1. La irregularidad causada por arritmias
- **Explicación** (literal de t2:101, t2:103): La HRV es la variación del tiempo entre latidos consecutivos. Se calcula sobre intervalos NN ("normal a normal"): intervalos entre latidos sinusales de los que se han retirado los artefactos.
- **Fuente:** [SG2017] · **Concepto:** `hrv`

### H2 — FIRMAR CON CORRECCIÓN

**Motivo:** La v2 ya compara con la SDNN, pero sus distractores no son medidas del dominio del tiempo («número total de latidos», «duración del registro»): se descartan solos. Se vuelve a la forma de la hoja anterior; t2:110–111 refutan cada distractor. Faltaba la explicación.

- **Enunciado:** ¿Qué afirmación sobre la RMSSD y la SDNN es correcta?
- **Opciones** (la correcta primero):
  1. ✅ La RMSSD está más influida por el sistema nervioso parasimpático que la SDNN
  1. La SDNN está más influida por el sistema nervioso parasimpático que la RMSSD
  1. La RMSSD es la desviación estándar de los intervalos NN
  1. Las dos están igual de influidas por el sistema nervioso parasimpático
- **Explicación** (literal de t2:110, t2:111): SDNN: desviación estándar de los intervalos NN, en ms. RMSSD: está más influida por el sistema nervioso parasimpático que la SDNN.
- **Fuente:** [SG2017] · **Concepto:** `hrv`

### H3 — FIRMAR CON CORRECCIÓN

**Motivo:** La v2 conserva «influida por la temperatura», un factor fuera de B7 (decisión de Luis, t2:157). Se cambia por la respiración con el rango de la VLF. Faltaba la explicación. t2:124–125 son filas de tabla: «| A | B |» se escribe «A: B.».

- **Enunciado:** ¿Qué rango ocupa la banda HF y qué la modifica?
- **Opciones** (la correcta primero):
  1. ✅ 0.15–0.40 Hz; está influida por la respiración entre 9 y 24 respiraciones por minuto
  1. 0.04–0.15 Hz; está influida por la respiración
  1. 0.0033–0.04 Hz; está influida por la respiración entre 9 y 24 respiraciones por minuto
  1. 0.15–0.40 Hz; no depende de la respiración
- **Explicación** (literal de t2:124, t2:125, t2:127): LF: 0.04–0.15 Hz. HF ("banda respiratoria"): 0.15–0.40 Hz. La banda HF está influida por la respiración entre 9 y 24 respiraciones por minuto.
- **Fuente:** [SG2017] · **Concepto:** `hrv`

### H4 — FIRMAR CON CORRECCIÓN

**Motivo:** Cumple B3: el enunciado lleva el rótulo, [B2013] va en la fuente y ninguna opción presenta la razón como un balance válido. Solo faltaba la explicación. Va literal, así que su segunda mención dice «la razón LF/HF» sin el rótulo. El rótulo ya está en el enunciado de la misma pregunta.

- **Enunciado:** ¿Qué afirmación sobre la razón LF/HF (interpretación discutida) es correcta?
- **Opciones** (la correcta primero):
  1. ✅ No mide con exactitud el equilibrio entre simpático y parasimpático, porque la potencia LF mezcla varias influencias
  1. Mide directamente el impulso simpático cardiaco
  1. Un valor alto demuestra predominio simpático
  1. Es la medida de referencia del sistema nervioso autónomo
- **Explicación** (literal de t2:128): La razón LF/HF es discutida: la potencia LF no es un índice del impulso simpático cardiaco, sino una mezcla de influencias simpáticas, parasimpáticas y otras no identificadas; por eso la razón LF/HF no mide con exactitud el "equilibrio simpático-vagal".
- **Fuente:** [B2013][SG2017] · **Concepto:** `hrv`

### H5 — FIRMAR CON CORRECCIÓN

**Motivo:** La v2 conserva «los valores de registros de distinta duración no son intercambiables», que generaliza t2:136: el texto firmado solo habla de registros cortos y ultracortos frente a los de 24 horas. La respuesta nueva copia la segunda cláusula de t2:136. Faltaba la explicación.

- **Enunciado:** Una estudiante compara la SDNN de un registro de 5 minutos con la de un Holter de 24 horas. ¿Es correcto?
- **Opciones** (la correcta primero):
  1. ✅ No: no es apropiado comparar la SDNN calculada sobre periodos de distinta duración
  1. Sí, porque la SDNN no depende de la duración
  1. Sí, si se multiplica el valor de 5 minutos por 288
  1. Sí, si los dos registros son de la misma persona
- **Explicación** (literal de t2:136): Los valores de registros cortos y ultracortos no son intercambiables con los de 24 horas, y no es apropiado comparar métricas como la SDNN calculadas sobre periodos de distinta duración.
- **Fuente:** [SG2017] · **Concepto:** `hrv`

### H6 — FIRMAR CON CORRECCIÓN

**Motivo:** La v2 conserva «Solo cambian en mujeres», que mezcla el sexo de un modo que B7 no dice. Faltaba la explicación.

- **Enunciado:** ¿Qué les ocurre a las medidas de HRV del dominio del tiempo con la edad?
- **Opciones** (la correcta primero):
  1. ✅ Disminuyen
  1. Aumentan
  1. No cambian
  1. Solo dependen de la duración del registro, no de la edad
- **Explicación** (literal de t2:155): La duración del registro, la edad y el sexo influyen en los valores basales; las medidas del dominio del tiempo disminuyen con la edad.
- **Fuente:** [SG2017] · **Concepto:** `hrv`

### H7 — FIRMAR CON CORRECCIÓN

**Motivo:** La v2 conserva «con menos sesgo y más fiabilidad»; ahora dice «menos sesgada y más fiable», tal cual t2:150. El enunciado pasa a completar la frase («se diseñó como:»), como «…puede deberse a la oclusión de:» del ECG-12. Faltaba la explicación.

- **Enunciado:** La entropía muestral se diseñó como:
- **Opciones** (la correcta primero):
  1. ✅ Una medida menos sesgada y más fiable de la regularidad y la complejidad de la señal
  1. Una medida de la potencia de la banda HF
  1. Un método para detectar latidos ectópicos
  1. Una forma de calcular la frecuencia cardiaca media
- **Explicación** (literal de t2:150): Entropía muestral: se diseñó como una medida menos sesgada y más fiable de la regularidad y la complejidad de la señal.
- **Fuente:** [SG2017] · **Concepto:** `hrv`

### H8 — FIRMAR CON CORRECCIÓN

**Motivo:** La corrección de la v2 está bien: quitó la cifra de SDNN. Faltaba la explicación. A un distractor se le añaden sexo y duración, que t2:169 refuta, para que la correcta no sea la más larga del banco HRV.

- **Enunciado:** ¿Existe un único «valor normal» de HRV?
- **Opciones** (la correcta primero):
  1. ✅ No: depende de la duración del registro, la edad y el sexo
  1. Sí: el mismo para todas las edades, sexos y duraciones del registro
  1. Sí, pero solo para registros de 5 minutos
  1. Sí, el que calcula el equipo
- **Explicación** (literal de t2:169): No hay un único "valor normal": los valores de referencia dependen de la duración del registro, la edad y el sexo, y los de registros cortos no sirven para comparar con los de 24 horas.
- **Fuente:** [SG2017] · **Concepto:** `hrv`

---

## Parte 2. `CONCEPT_BY_PROMPT` (rama `calibracion-confianza`)

**Dónde está:** `educational/quiz_bank.py:529`. La consumen `app/utils/confidence.py:20` (`record_quiz_answer`) y `tests/test_confidence_calibration.py:54`. El vocabulario es `CONCEPTS` de `app/utils/session_learning.py:16`.

**Cobertura:** tiene 24 claves. Cubren 25 de las 35 preguntas (16 de la Academia y 19 del ECG-12), porque el enunciado «Una elevación del ST solo en II, III y aVF…» está en los dos bancos y una sola clave los cubre. Quedan fuera 10.

**Cómo leer la columna «¿Encaja?»:** todos los valores pertenecen a `CONCEPTS`, y la prueba lo exige. La columna juzga si el concepto describe bien el contenido de la pregunta.

| Enunciado (60 caracteres) | Concepto propuesto | ¿Encaja? |
|---|---|---|
| Por convención docente, la FC del adulto en reposo se toma c | frecuencia_cardiaca | Sí |
| ¿Qué representa el complejo QRS? | ritmo_y_conduccion | Sí, con reserva: es la morfología básica de la onda; vale si se lee como despolarización ventricular |
| Durante un infarto con elevación del ST, ¿qué puede signific | derivaciones_e_isquemia | Sí |
| En una persona con dolor torácico agudo, ¿qué diagnóstico de | derivaciones_e_isquemia | Sí |
| ¿Qué mide el intervalo PR? | ritmo_y_conduccion | Sí |
| ¿Qué es una PVC? | ritmo_y_conduccion | Sí |
| ¿Cómo se calcula la FC (en lpm) a partir del intervalo RR? | frecuencia_cardiaca | Sí |
| Una elevación del ST solo en II, III y aVF puede deberse a l | derivaciones_e_isquemia | Sí (cubre 2 preguntas: Academia y ECG-12) |
| ¿Cuál de estas condiciones causa bradicardia? | ritmo_y_conduccion | Sí. La respuesta es el bloqueo AV completo; también cabría en `frecuencia_cardiaca` |
| Un eje del QRS entre −45° y −90°, con qR en aVL y QRS < 120 | ritmo_y_conduccion | Sí |
| ¿Qué patrón corresponde a un bloqueo de rama derecha complet | ritmo_y_conduccion | Sí |
| ¿Cómo se reconoce la fibrilación auricular en el ECG? | ritmo_y_conduccion | Sí |
| Según la AHA/ACCF/HRS 2009, ¿desde qué QTc se considera prol | ritmo_y_conduccion | **Con reserva.** El QT es repolarización y ningún concepto la cubre. Además, la onda T normal (también repolarización) quedó fuera por no encajar: hay que decidir las dos igual |
| Una elevación del ST en V1–V4 orienta a la oclusión de: | derivaciones_e_isquemia | Sí |
| ¿Qué eje del QRS es criterio de bloqueo fascicular anterior | ritmo_y_conduccion | Sí |
| ¿Qué patrón es característico del bloqueo de rama derecha co | ritmo_y_conduccion | Sí |
| PR corto, onda delta y QRS ancho en ritmo sinusal son signos | ritmo_y_conduccion | Sí (conducción por una vía accesoria) |
| Sin ondas P discernibles ni otra actividad auricular regular | ritmo_y_conduccion | Sí |
| Un QTc de 500 ms o más se asocia con mayor riesgo de: | ritmo_y_conduccion | Sí: la respuesta es una arritmia (torsade de pointes) |
| Una oclusión proximal de la descendente anterior eleva el ST | derivaciones_e_isquemia | Sí |
| ¿Cuál es el rango habitual del PR en el adulto? | ritmo_y_conduccion | Sí |
| Un eje del QRS entre +90° y +180° en un adulto, con rS en I | ritmo_y_conduccion | Sí |
| Un QRS de 120 ms o más en un adulto, con la morfología típic | ritmo_y_conduccion | Sí |
| ¿Dónde se mide habitualmente el desplazamiento del segmento | derivaciones_e_isquemia | Sí (cómo se mide el ST) |

### Las 10 preguntas que quedan fuera

| Banco [índice] | Enunciado | Por qué queda fuera |
|---|---|---|
| Academia [7] | ¿Qué ritmo del EEG se ve mejor con los ojos cerrados…? | Es de EEG, y `CONCEPTS` no tiene concepto de EEG |
| Academia [9] | ¿Qué hallazgo del ECG apoya una hipertrofia ventricular izquierda? | Hipertrofia (voltajes): no es ritmo, ni frecuencia, ni isquemia |
| Academia [13] | Ante un IAMCEST con síntomas de 12 h o menos, ¿qué recomienda la guía ESC 2023? | Es una conducta terapéutica, no una lectura del ECG. Meterla en `derivaciones_e_isquemia` mezclaría el tratamiento con la interpretación |
| Academia [15] | ¿Qué mide principalmente una señal de fotopletismografía (PPG)? | Es de PPG, y no hay concepto de PPG |
| ECG-12 [10] | En una persona con dolor torácico de tipo pericárdico, ¿qué patrón del ECG apoya una pericarditis? | La elevación difusa del ST no es isquémica. Es la más cercana a `derivaciones_e_isquemia` (diagnóstico diferencial del ST): decisión de Luis |
| ECG-12 [11] | Con una sola derivación filtrada a 0.5–40 Hz…, ¿qué se puede estudiar? | Describe la placa y la app, no un concepto fisiológico |
| ECG-12 [15] | ¿Para qué sirve el análisis automático de esta página? | Describe la app |
| ECG-12 [16] | En un adulto sano (20 años o más), ¿cómo es la onda T en V3–V6? | Repolarización normal: ningún concepto. Ver la reserva del QTc arriba |
| ECG-12 [17] | En la hipertrofia ventricular izquierda, además de los voltajes altos, puede verse: | Hipertrofia; la depresión del ST de esta pregunta no es isquémica |
| ECG-12 [18] | ¿Qué escenarios puede simular esta página? | Describe la app |

---

## Parte 3. Línea de firma

```
Firmo E1–E10 y H1–H8 del banco de EMG y HRV tal como quedan en la hoja de firma v2 del 17-11-2026 (E1 tal cual; E2–E10 y H1–H8 con su corrección). Firmables hoy: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, H1, H2, H3, H4, H5, H6, H7, H8. Luis Nazariego Santome, 17-11-2026.
```
