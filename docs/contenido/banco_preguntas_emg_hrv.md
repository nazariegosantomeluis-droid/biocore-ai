# Banco de preguntas para BIOCORE: EMG y HRV (borrador para firma)

**Estado:** BORRADOR, sin firmar (17 de noviembre de 2026).
**Uso:** una vez firmado, Claude Code lo integra en `educational/quiz_bank.py` como dos bancos nuevos, `EMG_QUESTIONS` y `HRV_QUESTIONS`, con la misma convención que los bancos de ECG-12 y EEG: la opción correcta va **primero** (`answer=0`), y cada pregunta lleva explicación, fuente y categoría. Las fuentes nuevas se añaden a `clinical/emg_references.py` y a un `clinical/hrv_references.py`.
**Regla:** cada respuesta lleva su fuente entre corchetes. Lo que no encontré en una fuente verificada no está escrito.

**Cómo leer las marcas:**
- **[F]**: la pregunta solo usa lo que ya está en `teoria_citada_2.md`, firmado el 17 de noviembre de 2026. Basta con revisar la redacción.
- **[N]**: la pregunta usa una afirmación nueva, sea de una fuente nueva o de una fuente ya firmada. **Necesita firma.** Si choca con alguna «Decisión de Luis», se indica.

**Total:** 24 preguntas sueltas (12 de EMG y 12 de HRV) y 6 casos clínicos con 2 preguntas cada uno, es decir, **36 preguntas**. 26 son [F] y 10 son [N].

---

# Parte 0. Bases de datos con señal real

| Base | Qué contiene | Para qué caso | Licencia | Cautelas |
|---|---|---|---|---|
| **Fantasia** (PhysioNet) [IY1996] | 20 personas jóvenes (21–34 años) y 20 mayores (68–85 años), sanas, en reposo supino durante 120 minutos mientras veían la película *Fantasia*. ECG con latidos anotados y respiración; la mitad incluye presión arterial no calibrada. Cada grupo tiene el mismo número de hombres y de mujeres. | C5 (respiración) y, de forma secundaria, C4 (edad) | **Por verificar** en la página de PhysioNet | Registros largos: para preguntas de 5 minutos hay que extraer tramos. Comparar siempre tramos de la misma duración (B4). |
| **Autonomic Aging** (PhysioNet) [SB2022] | ECG y presión arterial continua no invasiva en reposo de 1,121 voluntarios sanos, con datos demográficos como el sexo y el índice de masa corporal. | C4 (edad y sexo) | Open Data Commons Open Database License v1.0 | Hay que confirmar la duración de cada registro antes de redactar valores. |
| **MIT-BIH Arrhythmia** (PhysioNet) [MM2001] | La misma base que ya usa BIOCORE para validar su detector de latidos. | C6 (latidos ectópicos) | Ya citada en el repositorio | Para HRV hay que elegir registros con latidos ectópicos anotados. |
| **HD-sEMG del codo** (figshare) [RM2020] | 12 hombres sanos; bíceps, tríceps, ancóneo, braquiorradial y pronador redondo; flexión, extensión, supinación y pronación isométricas al 10, 30 y 50 % de la contracción máxima, 10 s cada una. 2048 muestras/s, señal cruda sin filtrar. | C2 (normalización) | **Por verificar** en figshare | La fuerza se midió, así que sirve para mostrar que la amplitud no es fuerza. |
| **EMG de fatiga** (Zenodo) [EB2020] | 15 personas sanas sosteniendo 6 kg con el codo a 90° durante 120 s; 8 canales, 200 muestras/s, 8 bits, con filtro de 50 Hz ya aplicado. | C1 (fatiga) | **Por verificar** en Zenodo | **A 200 muestras/s no se puede aplicar el filtro de 20–450 Hz de BIOCORE**, porque el registro no contiene nada por encima de 100 Hz. Se convierte en pregunta del caso C1. |
| **GRABMyoFlow** (PhysioNet) [EH2026] | EMG de superficie de muñeca y antebrazo de 63 participantes en varias sesiones, en formato WFDB, que ya lee la librería `wfdb` de BIOCORE. | C3 (comparar sesiones) | Acceso abierto en PhysioNet | Está pensada para reconocer gestos, no para fisiología: el caso solo usa la comparación entre días. |
| *Candidata:* **Autoinforme, palpación y sEMG** [LI2024] | 30 hombres sanos; nueve músculos de la parte superior del cuerpo en contracción isométrica, con fatiga percibida, palpación de un fisioterapeuta y sEMG. | Alternativa para C1 | Por verificar | No verifiqué su frecuencia de muestreo. |
| *No recomendada:* **Examples of Electromyograms** (PhysioNet) | EMG **de aguja** (no de superficie) en el tibial anterior de tres personas: una sana, una con neuropatía y una con miopatía. | — | ODC Attribution v1.0 | Es EMG de aguja y su uso es diagnóstico; choca con la decisión de A9 («no se afirma nada sobre diagnósticos ni lesiones»). |

**Nota técnica:** `wfdb` ya está en `requirements.txt`. Para no depender de la red durante la clase, conviene guardar extractos pequeños en `data/reference_signals/`, como ya se hace con `ptb_s0010.npz`.

---

# Parte 1. Preguntas de EMG (12)

**E1 [F] · Qué es el EMG**
¿Qué registra un electrodo de EMG de superficie?
- ✅ La suma de los potenciales de acción de las unidades motoras activas bajo el electrodo
- La fuerza mecánica que produce el músculo
- La actividad de un único nervio periférico, aislada
- El potencial de reposo de las fibras musculares

*Explicación:* el electrodo capta la suma de los potenciales de las unidades motoras que tiene debajo; cuántas y con qué peso depende del volumen que «ve». *Fuente:* [DL1997]

**E2 [F] · Amplitud**
Una amplitud de EMG de superficie más alta indica sobre todo…
- ✅ Mayor excitación del músculo, no necesariamente mayor fuerza
- Mayor fuerza muscular, en proporción directa
- Mayor masa muscular
- Mayor riesgo de lesión

*Explicación:* la amplitud refleja la excitación. La fuerza depende además de otros factores, así que no se puede deducir de la amplitud. *Fuente:* [V2018]

**E3 [F] · Reclutamiento**
Un músculo aumenta su fuerza reclutando unidades motoras nuevas y haciendo que las activas disparen más rápido. ¿Puede la amplitud del EMG de superficie decir cuál de las dos ocurrió?
- ✅ No: con la amplitud no se distingue el reclutamiento de la frecuencia de disparo
- Sí: si la amplitud sube, fue por reclutamiento
- Sí: si la amplitud sube, fue por frecuencia de disparo
- Sí, siempre que la señal esté normalizada

*Fuente:* [DL1997] (los dos mecanismos) y [V2018] (no se distinguen)

**E4 [F] · Filtro pasa-altas**
¿Por qué se recomienda un filtro pasa-altas de 20 Hz para el EMG de superficie?
- ✅ Porque el artefacto de movimiento concentra su energía en frecuencias bajas, y la energía del EMG por debajo de 20 Hz es poca e inestable
- Para eliminar la interferencia de la red eléctrica
- Porque por debajo de 20 Hz está la mayor parte de la señal muscular
- Para reducir el tamaño del archivo

*Explicación:* un corte en 10 Hz puede dejar pasar demasiado ruido de movimiento. *Fuente:* [DL2010]

**E5 [F] · RMS**
Para medir la amplitud de una contracción voluntaria, ¿qué medida se recomienda y por qué?
- ✅ El RMS, porque representa la potencia de la señal y tiene un significado físico claro
- El valor medio rectificado, porque mide la potencia de la señal
- El valor máximo, porque es el más estable
- La frecuencia mediana, porque no depende de la amplitud

*Explicación:* el valor medio rectificado mide el área bajo la señal y no tiene un significado físico específico. *Fuente:* [DL1997]

**E6 [F] · Por qué normalizar**
¿Por qué suele normalizarse la amplitud del EMG, por ejemplo al porcentaje de la contracción voluntaria isométrica máxima?
- ✅ Porque los microvoltios no se pueden comparar entre personas, músculos o sesiones
- Porque así la amplitud se vuelve igual a la fuerza
- Porque así se elimina el artefacto de movimiento
- Porque los equipos no pueden medir microvoltios

*Explicación:* aun normalizada, la amplitud no permite deducir la fuerza. *Fuente:* [V2018]

**E7 [F] · Fatiga**
Durante una contracción sostenida, ¿qué le ocurre al espectro del EMG y qué índice se usa para seguirlo?
- ✅ Se desplaza hacia frecuencias más bajas; se sigue con la frecuencia mediana
- Se desplaza hacia frecuencias más altas; se sigue con el RMS
- No cambia; solo cambia la amplitud
- Se desplaza hacia frecuencias más bajas; se sigue con el valor máximo

*Explicación:* los potenciales duran más; alrededor de 65 % de ese alargamiento se explica por la caída de la velocidad de conducción de las fibras. *Fuente:* [DL1997]

**E8 [F] · Diafonía**
Un electrodo sobre un músculo capta también parte de la actividad de los músculos vecinos. ¿Cómo se llama esto y hasta cuánto puede llegar?
- ✅ Diafonía (crosstalk): hasta 17 % de la actividad de los músculos vecinos
- Artefacto de movimiento: hasta 17 %
- Diafonía: siempre menos de 1 %
- Fatiga: hasta 50 %

*Fuente:* [DL1997]

**E9 [F] · Lo que sí se puede concluir**
¿Cuál de estas conclusiones **sí** permite, con cautela, un EMG de superficie?
- ✅ Decir si un músculo está «encendido» o «apagado» en intervalos de más de unos 200 ms
- Calcular la fuerza del músculo en newtons
- Predecir cuánto crecerá el músculo con el entrenamiento
- Comparar la fuerza de dos personas por su amplitud en microvoltios

*Fuente:* [V2018]

**E10 [F] · Hipertrofia**
Un ejercicio produce más amplitud de EMG que otro en el mismo músculo. ¿Permite eso afirmar que producirá más hipertrofia?
- ✅ No: la amplitud del EMG de superficie no predice la hipertrofia ni la adaptación a largo plazo
- Sí: más amplitud implica más crecimiento
- Sí, si la diferencia es mayor de 20 %
- Solo si la señal está normalizada

*Fuente:* [V2018]

**E11 [N] · Fuerza sin señal**
¿Puede un músculo producir fuerza aunque su EMG de superficie sea prácticamente cero?
- ✅ Sí, por sus propiedades pasivas
- No: sin señal eléctrica no hay fuerza
- Solo si el electrodo está despegado
- Solo durante la fatiga

*Explicación:* otro motivo por el que la amplitud no equivale a fuerza. La longitud del músculo también cambia la relación: según la revisión, 70 % de activación con la fibra más corta puede dar más o menos la misma fuerza que 60 % con la fibra a su longitud de referencia. *Fuente:* [V2018]
> *Nueva afirmación de una fuente ya firmada. Es coherente con A1, A6 y A9.*

**E12 [N] · Comparar ejercicios**
Un entrenador compara la amplitud del EMG del glúteo en dos ejercicios distintos, sin controlar la longitud del músculo, la velocidad ni la posición del electrodo. ¿Qué dice la evidencia?
- ✅ Esa comparación debe evitarse si no se controlan esas variables
- Es válida si se usa el RMS
- Es válida si los dos ejercicios duran lo mismo
- Es válida siempre que sea la misma persona

*Fuente:* [V2018]
> *Nueva afirmación de una fuente ya firmada. Matiza A9: la comparación dentro de la misma persona solo vale si se controlan las condiciones.*

---

# Parte 2. Preguntas de HRV (12)

**H1 [F] · Definición**
¿Qué es la variabilidad de la frecuencia cardiaca (HRV)?
- ✅ La variación del tiempo entre latidos consecutivos
- El número de latidos por minuto
- La diferencia entre la frecuencia cardiaca máxima y la mínima del día
- La irregularidad causada por arritmias

*Explicación:* se calcula sobre intervalos NN, es decir, entre latidos sinusales, después de retirar los artefactos. *Fuente:* [SG2017]

**H2 [F] · RMSSD**
¿Qué medida del dominio del tiempo está más influida por el sistema nervioso parasimpático?
- ✅ RMSSD
- SDNN
- La frecuencia cardiaca media
- El número total de latidos

*Fuente:* [SG2017]

**H3 [F] · Banda HF**
¿Qué rango ocupa la banda HF y qué la modifica?
- ✅ 0.15–0.40 Hz; está influida por la respiración entre 9 y 24 respiraciones por minuto
- 0.04–0.15 Hz; está influida por la respiración
- 0.0033–0.04 Hz; está influida por la temperatura
- 0.15–0.40 Hz; no depende de la respiración

*Fuente:* [SG2017]

**H4 [F] · Razón LF/HF**
¿Qué afirmación sobre la **razón LF/HF (interpretación discutida)** es correcta?
- ✅ No mide con exactitud el equilibrio entre simpático y parasimpático, porque la potencia LF mezcla varias influencias
- Mide directamente el impulso simpático cardiaco
- Un valor alto demuestra predominio simpático
- Es la medida de referencia del sistema nervioso autónomo

*Fuente:* [B2013][SG2017]
> *Cumple la decisión de B3: el rótulo es «razón LF/HF (interpretación discutida)» y ninguna opción la presenta como balance válido.*

**H5 [F] · Duración del registro**
Una estudiante compara la SDNN de un registro de 5 minutos con la de un Holter de 24 horas. ¿Es correcto?
- ✅ No: los valores de registros de distinta duración no son intercambiables
- Sí, porque la SDNN no depende de la duración
- Sí, si se multiplica el valor de 5 minutos por 288
- Sí, si los dos registros son de la misma persona

*Fuente:* [SG2017]

**H6 [F] · Edad**
¿Qué les ocurre a las medidas de HRV del dominio del tiempo con la edad?
- ✅ Disminuyen
- Aumentan
- No cambian
- Solo cambian en mujeres

*Fuente:* [SG2017]

**H7 [F] · Entropía muestral**
¿Para qué se diseñó la entropía muestral?
- ✅ Para medir la regularidad y la complejidad de la señal con menos sesgo y más fiabilidad
- Para medir la potencia de la banda HF
- Para detectar latidos ectópicos
- Para calcular la frecuencia cardiaca media

*Fuente:* [SG2017]

**H8 [F] · Valores de referencia**
¿Existe un único «valor normal» de HRV?
- ✅ No: depende de la duración del registro, la edad y el sexo
- Sí: 50 ms de SDNN para todos
- Sí, pero solo para registros de 5 minutos
- Sí, el que calcula el equipo

*Fuente:* [SG2017]
> *Cumple la decisión de B9: no se da ninguna cifra. El «50 ms» es un distractor y nunca aparece como respuesta correcta.*

**H9 [N] · Duración mínima por banda**
¿Cuál es el registro mínimo convencional para cada banda?
- ✅ HF, 1 minuto; LF, 2 minutos; ULF, al menos 24 horas
- HF, 24 horas; LF, 2 minutos; ULF, 1 minuto
- Las tres bandas, 10 segundos
- Las tres bandas, 5 minutos

*Fuente:* [SG2017]
> *Nueva afirmación de una fuente ya firmada. Amplía B4.*

**H10 [N] · Frecuencia cardiaca**
Si la frecuencia cardiaca en reposo es más alta, ¿qué le pasa a la HRV y por qué?
- ✅ Tiende a bajar, porque hay menos tiempo entre latidos para que los intervalos varíen
- Tiende a subir, porque hay más latidos que pueden variar
- No cambia: son independientes
- Sube solo en la banda HF

*Explicación:* se llama dependencia de la longitud del ciclo. *Fuente:* [SG2017]
> **Choca con B7**, que restringe los factores modificantes a edad, sexo, duración del registro y respiración. Solo entra si Luis amplía B7.

**H11 [N] · Más no siempre es mejor**
¿Una HRV más alta es siempre señal de buena salud?
- ✅ No: algunas alteraciones, como las de la conducción cardiaca, pueden elevar la HRV, y en ese caso se asocian a más riesgo
- Sí, siempre
- Sí, salvo durante el ejercicio
- No, porque la HRV no tiene relación con la salud

*Explicación:* revisar la morfología del ECG ayuda a saber si un valor alto viene, por ejemplo, de una fibrilación auricular. *Fuente:* [SG2017]
> *Nueva afirmación de una fuente ya firmada. Habla de riesgo; Luis decide si encaja en una plataforma educativa.*

**H12 [N] · RMSSD y respiración**
¿Por qué la RMSSD suele preferirse a la potencia HF cuando la frecuencia respiratoria no está controlada?
- ✅ Porque la RMSSD se ve menos afectada por la frecuencia respiratoria
- Porque la RMSSD mide el sistema simpático
- Porque la RMSSD no necesita intervalos NN limpios
- Porque la potencia HF no cambia con la respiración

*Fuente:* [L2017] (fuente nueva)

---

# Parte 3. Casos clínicos con señal real (6 casos, 12 preguntas)

> Las viñetas describen personas sanas en contextos de deporte, docencia o investigación. Ninguna plantea un diagnóstico ni una lesión (decisión de A9).

## C1. Brazo sostenido (EMG · fatiga)
**Señal:** EMG de fatiga [EB2020]. Bíceps, 6 kg, codo a 90°, 120 s.
**Viñeta:** Andrea, de 22 años y estudiante de fisioterapia, sostiene una pesa de 6 kg con el codo a 90° durante dos minutos mientras se registra su bíceps.

**C1.1 [F]** Si se compara el inicio con el final del registro, ¿qué cabe esperar?
- ✅ Que la frecuencia mediana del espectro baje
- Que la frecuencia mediana suba
- Que la señal desaparezca
- Que el espectro no cambie

*Fuente:* [DL1997]

**C1.2 [N]** El registro se tomó a 200 muestras/s. ¿Por qué BIOCORE no puede aplicarle su filtro de 20–450 Hz?
- ✅ Porque a 200 muestras/s el registro no contiene información por encima de 100 Hz (la mitad de la frecuencia de muestreo)
- Porque el filtro solo funciona con señales de ECG
- Porque el registro ya tiene un filtro de 50 Hz
- Porque 200 muestras/s es demasiado rápido

*Explicación:* el EMG captado con sensores comunes llega hasta unos 400 Hz [DL2010], así que este registro pierde parte del espectro y su frecuencia mediana no es comparable con la de un registro de banda completa. *Fuente:* definición de muestreo (frecuencia de Nyquist; no necesita cita, igual que `UNIT_DEFINITION` en `quiz_bank.py`), [DL2010] y [EB2020]

## C2. Tres esfuerzos y un día con dolor (EMG · normalización)
**Señal:** HD-sEMG del codo [RM2020]. Bíceps y tríceps al 10, 30 y 50 % de la contracción máxima.
**Viñeta:** Diego, de 28 años, participa en un estudio de fuerza. En la primera sesión hace contracciones al 10, 30 y 50 % de su máximo. En la segunda sesión refiere dolor durante la prueba de contracción máxima, y sus valores normalizados salen más altos que en la primera.

**C2.1 [F]** ¿Cuál es la interpretación más prudente?
- ✅ Si no alcanzó su máximo real por el dolor, los valores normalizados quedan inflados
- Su músculo se volvió más fuerte entre sesiones
- El electrodo mide mejor cuando hay dolor
- Los valores son comparables porque están normalizados

*Fuente:* [V2018]

**C2.2 [F]** En la primera sesión, el bíceps dio más microvoltios que el tríceps. ¿Se puede concluir que el bíceps «trabajó más»?
- ✅ No: los microvoltios no se pueden comparar entre músculos
- Sí, porque son la misma persona y la misma sesión
- Sí, si se usa el RMS
- Sí, si la diferencia es mayor de 10 %

*Fuente:* [V2018]

## C3. El mismo gesto en tres días (EMG · comparar sesiones)
**Señal:** GRABMyoFlow [EH2026]. EMG de muñeca y antebrazo de un participante en tres sesiones.
**Viñeta:** un equipo quiere saber si la activación del antebrazo de Sofía cambia entre tres días de práctica del mismo gesto.

**C3.1 [F]** ¿Qué condición es imprescindible para comparar los tres días?
- ✅ Que los electrodos vayan en el mismo sitio de la piel respecto al músculo
- Que Sofía haga el gesto más rápido cada día
- Que el registro dure exactamente 10 minutos
- Ninguna: el EMG de superficie no cambia entre días

*Fuente:* [V2018]

**C3.2 [F]** Si se cumplen las condiciones, ¿qué tipo de comparación es la más defendible?
- ✅ Dentro de la misma persona y el mismo músculo, con las condiciones controladas
- Entre Sofía y otras personas, en microvoltios
- Entre el músculo de Sofía y uno vecino
- Ninguna comparación es posible

*Fuente:* [V2018]

## C4. Dos voluntarios de edades distintas (HRV · edad y preparación)
**Señal:** Autonomic Aging [SB2022]. Un voluntario de 25 años y una voluntaria de 70 años, en reposo.
**Viñeta:** se registran en reposo un hombre de 25 años y una mujer de 70 años, los dos sanos. La RMSSD de ella sale más baja.

**C4.1 [F]** ¿Qué explica, al menos en parte, la diferencia?
- ✅ La edad y el sexo influyen en los valores basales de la HRV
- La diferencia demuestra que ella tiene una enfermedad
- La RMSSD no depende de la edad
- La diferencia se debe solo al equipo

*Fuente:* [SG2017]

**C4.2 [N]** Antes de repetir los registros, ¿qué preparación recomienda la literatura?
- ✅ No comer ni tomar cafeína en las 2 horas previas, no beber alcohol en las 24 horas previas y no hacer ejercicio intenso el día anterior
- Tomar un café para estar despiertos
- Hacer ejercicio intenso justo antes para «activar» el corazón
- No hace falta ninguna preparación

*Explicación:* también conviene controlar la hora del día y registrar en la misma postura que la tarea. *Fuente:* [L2017] (fuente nueva)
> **Choca con B7**: introduce factores (comida, cafeína, alcohol, ejercicio, hora y postura) que B7 dejó «sin fuente verificada». Ahora tienen fuente; Luis decide si amplía B7.

## C5. Respirar lento (HRV · respiración y razón LF/HF)
**Señal:** Fantasia [IY1996], ECG con su canal de respiración para medir la frecuencia respiratoria.
**Viñeta:** Mateo, de 24 años, practica biofeedback y respira unas 6 veces por minuto. Su razón LF/HF sube mucho respecto a su respiración espontánea.

**C5.1 [N]** ¿En qué banda cae ahora la oscilación respiratoria de su frecuencia cardiaca?
- ✅ En la banda LF, alrededor de 0.1 Hz
- En la banda HF, como siempre
- En la banda ULF
- En ninguna: la respiración lenta elimina la variabilidad

*Explicación:* respirar entre 4.5 y 7.5 veces por minuto concentra las oscilaciones de la frecuencia cardiaca alrededor de 0.1 Hz, dentro de la banda LF. *Fuente:* [SG2017]
> *Nueva afirmación de una fuente ya firmada. Amplía B3 y B5.*

**C5.2 [F]** ¿Cómo se interpreta la subida de su **razón LF/HF (interpretación discutida)**?
- ✅ No indica más actividad simpática: la respiración trasladó la variabilidad a otra banda, y la razón LF/HF no mide con exactitud el equilibrio autonómico
- Indica que Mateo está estresado
- Indica predominio simpático
- Indica que el registro es erróneo

*Fuente:* [SG2017][B2013]

## C6. Latidos fuera de lugar (HRV · artefactos)
**Señal:** MIT-BIH Arrhythmia [MM2001], registro con latidos ectópicos anotados.
**Viñeta:** al calcular la HRV de un registro, la serie de intervalos muestra saltos bruscos que coinciden con latidos ectópicos.

**C6.1 [F]** ¿Qué opciones hay antes de calcular las métricas?
- ✅ Elegir un tramo sin artefactos, editar los intervalos afectados o interpolar los latidos perdidos
- Calcular con todos los latidos, porque los ectópicos también son variabilidad
- Duplicar los latidos normales para compensar
- Usar solo la razón LF/HF, que no se afecta

*Explicación:* también se recomienda revisar visualmente el ECG en vez de confiar solo en la corrección automática [L2017]. *Fuente:* [SG2017]

**C6.2 [N]** ¿Por qué importa incluso un solo artefacto?
- ✅ Porque el sesgo de un solo artefacto puede superar los efectos que suele medir un estudio, y los artefactos aumentan la potencia en todas las bandas
- No importa: un latido no cambia nada
- Porque borra la banda HF
- Porque solo afecta a la frecuencia cardiaca media

*Explicación:* los latidos no detectados aumentan la potencia más que los latidos extra. *Fuente:* [SG2017]
> *Nueva afirmación de una fuente ya firmada. Amplía B8.*

---

# Hoja de decisiones para Luis

| # | Decisión | Opciones |
|---|---|---|
| D1 | ¿Se acepta la fuente nueva **[L2017]** (Laborde, Mosley y Thayer 2017)? | ☐ sí ☐ no |
| D2 | ¿Se amplía **B7** con la frecuencia cardiaca (H10) y con la preparación previa (C4.2)? | ☐ ampliar ☐ dejar B7 como está y retirar H10 y C4.2 |
| D3 | **B9:** [SG2017] da puntos de corte de SDNN en 24 horas (menos de 50 ms, de 50 a 100 ms y más de 100 ms). Ya están verificados en la fuente. | ☐ seguir sin cifras ☐ añadirlas como tema nuevo |
| D4 | Excluir **Examples of Electromyograms** (EMG de aguja, uso diagnóstico) por A9. | ☐ excluir ☐ incluir con otro marco |
| D5 | Verificar las licencias de Fantasia, del EMG de fatiga (Zenodo) y del HD-sEMG (figshare) antes de guardar extractos en el repositorio. | ☐ hecho |
| D6 | Firma de las preguntas [F] (26) | ☐ firmadas |
| D7 | Firma de las preguntas [N] (10): E11, E12, H9, H10, H11, H12, C1.2, C4.2, C5.1 y C6.2 (H10 y C4.2 dependen además de D2) | ☐ firmadas ☐ firmadas con cambios |

---

# Bibliografía

**Ya firmadas (de `teoria_citada_2.md`):** [DL1997], [DL2010], [V2018], [SG2017] y [B2013], con las referencias completas de ese documento.

**Nuevas:**
- **[L2017]** Laborde S, Mosley E, Thayer JF. Heart rate variability and cardiac vagal tone in psychophysiological research – Recommendations for experiment planning, data analysis, and data reporting. *Front Psychol*. 2017;8:213. doi:10.3389/fpsyg.2017.00213. PMID 28265249. [Artículo](https://pmc.ncbi.nlm.nih.gov/articles/PMC5316555)
- **[IY1996]** Iyengar N, Peng C-K, Morin R, Goldberger AL, Lipsitz LA. Age-related alterations in the fractal scaling of cardiac interbeat interval dynamics. *Am J Physiol*. 1996;271(4 Pt 2):R1078–R1084. doi:10.1152/ajpregu.1996.271.4.R1078. Describe la base Fantasia.
- **[SB2022]** Schumann A, Bär KJ. Autonomic aging – A dataset to quantify changes of cardiovascular autonomic function during healthy aging. *Sci Data*. 2022;9:95. doi:10.1038/s41597-022-01202-y. Datos: doi:10.13026/2hsy-t491.
- **[MM2001]** Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. *IEEE Eng Med Biol*. 2001;20(3):45–50. Ya está citada en el repositorio.
- **[RM2020]** Rojas-Martínez M, Serna LY, Jordanic M, Marateb HR, Merletti R, Mañanas MÁ. High-density surface electromyography signals during isometric contractions of elbow muscles of healthy humans. *Sci Data*. 2020;7:397. doi:10.1038/s41597-020-00717-6.
- **[EB2020]** Ebied A, Awadallah AM, Abbass MA, El-Sharkawy Y. Upper limb muscle fatigue analysis using multi-channel surface EMG. *2020 2nd Novel Intelligent and Leading Emerging Sciences Conference (NILES)*. 2020:423–427. doi:10.1109/NILES50944.2020.9257909. Datos: [Zenodo 5189275](https://zenodo.org/records/5189275).
- **[EH2026]** Ehlert CL, Tung J, Pradhan A. GRABMyoFlow – Dataset extension (versión 1.0.0). *PhysioNet*. 2026. doi:10.13026/ah52-zq51.
- **[LI2024]** Lim J, Lu L, Goonewardena K, Liu JZ, Tan Y. Assessment of self-report, palpation, and surface electromyography dataset during isometric muscle contraction. *Sci Data*. 2024;11:208. doi:10.1038/s41597-024-03030-8. *(Candidata; no se usa en ninguna pregunta.)*
- **Cita estándar de PhysioNet** (para Fantasia, Autonomic Aging, MIT-BIH y GRABMyoFlow): Goldberger AL, Amaral LAN, Glass L, et al. PhysioBank, PhysioToolkit, and PhysioNet: components of a new research resource for complex physiologic signals. *Circulation*. 2000;101(23):e215–e220.
