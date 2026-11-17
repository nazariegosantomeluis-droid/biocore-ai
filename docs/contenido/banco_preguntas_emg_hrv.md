# Banco de preguntas para BIOCORE: EMG y HRV (FIRMADO, versión 2)

**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome. Versión 2 del 17 de noviembre de 2026, con la redacción exacta de la hoja de firma v2 (`docs/contenido/hoja_firma_banco_emg_hrv_v2.md`): E1 tal cual; E2–E10 y H1–H8 con su corrección.

**Firma de Luis (textual):**

> «Firmo, el 17 de noviembre de 2026, Luis Nazariego Santome:
> (1) E1–E10 y H1–H8 del banco de EMG y HRV tal como quedan en la hoja de firma v2 del 17-11-2026 (E1 tal cual; E2–E10 y H1–H8 con su corrección). Firmables hoy: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, H1, H2, H3, H4, H5, H6, H7, H8. En H4, la explicación termina en «…y otras no identificadas» (literal de t2:128).
> (2) CONCEPT_BY_PROMPT tal como está propuesto, más: «onda T normal» → ritmo_y_conduccion (igual que el QTc); la pericarditis queda fuera hoy; E1–E10 → emg; H1–H8 → hrv.
> (3) El criterio de privacidad P1–P3 de «Pregunta a BIOCORE».
> No firmo hoy: las [N] del apéndice, H10–H12, C1.2 ni los casos C1–C6.»

**Lo que abarca la firma (IDs firmados):** E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, H1, H2, H3, H4, H5, H6, H7, H8. Nada más: los casos clínicos (Parte 3), el apéndice y las decisiones quedan para **después de hoy** y no entran a la app.
**Uso:** solo las preguntas que Luis marque «firmo» entran a la app, en `educational/quiz_bank.py` como `EMG_QUESTIONS` y `HRV_QUESTIONS`, con la convención de los bancos de ECG-12 y EEG (opción correcta primero, `answer=0`, explicación, fuente y categoría). Sus claves se resuelven contra `app/supermodules/bibliography.py`; las de EMG y HRV llegan con la rama `teoria-emg-hrv`. Una prueba exigirá que toda clave exista en la Bibliografía y que ninguna pregunta sin firmar esté en el banco. Cada respuesta se registra con `log_session_answer` de `app/utils/session_learning.py`: concepto `emg` para E1–E10 y C1–C3, `hrv` para H1–H8 y C4–C6.
**Regla:** cada pregunta se sostiene en una línea firmada de `teoria_citada_2.md`, citada textual como «t2:N» (N = número de línea). Una afirmación que no está firmada no entra en esta hoja: va al apéndice, para firmarla primero en la teoría.

**Total firmado:** 18 preguntas, 10 de EMG y 8 de HRV, en `educational/quiz_bank.py` (`EMG_QUESTIONS`, `HRV_QUESTIONS`). Los 6 casos clínicos (8 preguntas) quedan para después de hoy.

---

# Parte 0. Bases de datos con señal real

Las señales de los casos vienen de estas bases. Sus referencias ([IY1996], [SB2022], [MM2001], [RM2020], [EB2020], [EH2026]) son de la **señal**, no de la respuesta: ninguna respuesta se apoya en ellas. Todavía no están en la Bibliografía de la app (D5).

| Base | Qué contiene | Caso | Licencia | Cautelas |
|---|---|---|---|---|
| **Fantasia** (PhysioNet) [IY1996] | 20 personas jóvenes (21–34 años) y 20 mayores (68–85 años), sanas, en reposo supino durante 120 minutos; ECG con latidos anotados y respiración. | C5 | **Por verificar** | Comparar siempre tramos de la misma duración (t2:136). |
| **Autonomic Aging** (PhysioNet) [SB2022] | ECG y presión arterial continua en reposo de 1,121 voluntarios sanos, con sexo e índice de masa corporal. | C4 | Open Data Commons Open Database License v1.0 | Confirmar la duración de cada registro. |
| **MIT-BIH Arrhythmia** (PhysioNet) [MM2001] | La base que ya usa BIOCORE para validar su detector. | C6 | Ya citada en el repositorio | Elegir registros con latidos ectópicos anotados. |
| **HD-sEMG del codo** (figshare) [RM2020] | 12 hombres sanos; cinco músculos del codo; contracciones isométricas al 10, 30 y 50 % de la máxima; 2048 muestras/s, señal cruda. | C2 | **Por verificar** | — |
| **EMG de fatiga** (Zenodo) [EB2020] | 15 personas sanas con 6 kg y el codo a 90° durante 120 s; 8 canales; 200 muestras/s. | C1 | **Por verificar** | A 200 muestras/s no admite el filtro de 20–450 Hz de BIOCORE (ver el apéndice, C1.2). |
| **GRABMyoFlow** (PhysioNet) [EH2026] | EMG de muñeca y antebrazo de 63 participantes en varias sesiones, en formato WFDB. | C3 | Acceso abierto | Pensada para reconocer gestos; el caso solo usa la comparación entre días. |
| *No recomendada:* **Examples of Electromyograms** | EMG de aguja con uso diagnóstico. | — | — | Choca con A9 (D4). |

---

# Parte 1. Preguntas de EMG (10)

**E1 · Qué es el EMG** *(firmada tal cual)*
¿Qué registra un electrodo de EMG de superficie?
- ✅ La suma de los potenciales de acción de las unidades motoras activas bajo el electrodo
- La fuerza mecánica que produce el músculo
- La actividad de un único nervio periférico, aislada
- El potencial de reposo de las fibras musculares

*Explicación:* el electrodo capta la suma de los potenciales de las unidades motoras que tiene debajo. *Fuente:* [DL1997] · *Línea firmada:* t2:13

**Firma de Luis:** ☑ firmo

**E2 · Amplitud** *(firmada con la corrección de la hoja v2)*
¿Qué indica una amplitud más alta del EMG de superficie?
- ✅ Mayor excitación del músculo, no su fuerza
- Mayor fuerza muscular, en proporción directa
- Mayor fuerza muscular, siempre que la señal esté normalizada
- Mayor masa muscular

*Explicación:* La amplitud del EMG de superficie indica la excitación del músculo, no su fuerza. Incluso normalizada, la amplitud no permite deducir la fuerza del músculo. *Fuente:* [V2018] · *Línea firmada:* t2:17, t2:62

**Firma de Luis:** ☑ firmo

**E3 · Reclutamiento** *(firmada con la corrección de la hoja v2)*
El músculo aumenta su fuerza de dos maneras: activando unidades motoras nuevas (reclutamiento) y haciendo que las ya activas disparen más rápido. ¿Puede la amplitud del EMG de superficie decir cuánto del aumento se debe a cada una?
- ✅ No: la amplitud no permite distinguir cuánto se debe a cada una
- Sí: si la amplitud sube, todo el aumento se debe al reclutamiento
- Sí: si la amplitud sube, todo el aumento se debe a la frecuencia de disparo
- Sí, siempre que la señal esté normalizada

*Explicación:* Con la amplitud del EMG de superficie no se puede distinguir cuánto se debe al reclutamiento y cuánto a la frecuencia de disparo. *Fuente:* [DL1997][V2018] · *Línea firmada:* t2:25

**Firma de Luis:** ☑ firmo

**E4 · Filtro pasa-altas** *(firmada con la corrección de la hoja v2)*
¿Por qué se recomienda un filtro pasa-altas de 20 Hz para el EMG de superficie?
- ✅ Porque el artefacto de movimiento concentra su energía en frecuencias bajas
- Para eliminar la interferencia de la red eléctrica
- Porque por debajo de 20 Hz está la mayor parte de la energía de la señal muscular
- Para eliminar la diafonía de los músculos vecinos

*Explicación:* Pasa-altas de 20 Hz (Butterworth, 12 dB/octava) para uso general: el artefacto de movimiento concentra su energía en frecuencias bajas y cae rápidamente por encima de 20 Hz; la energía del EMG por debajo de 20 Hz es poca e inestable. *Fuente:* [DL2010] · *Línea firmada:* t2:45

**Firma de Luis:** ☑ firmo

**E5 · RMS** *(firmada con la corrección de la hoja v2)*
Para medir la amplitud de una contracción voluntaria, ¿qué medida se recomienda y por qué?
- ✅ El RMS, porque representa la potencia de la señal y tiene un significado físico claro
- El valor medio rectificado, porque representa la potencia de la señal y tiene un significado físico claro
- El valor máximo, porque es el más estable
- La frecuencia mediana, porque no depende de la amplitud

*Explicación:* El RMS representa la potencia de la señal y tiene un significado físico claro; el valor medio rectificado mide el área bajo la señal y no tiene un significado físico específico. *Fuente:* [DL1997] · *Línea firmada:* t2:54

**Firma de Luis:** ☑ firmo

**E6 · Por qué normalizar** *(firmada con la corrección de la hoja v2)*
¿Por qué suele normalizarse la amplitud del EMG, por ejemplo a la contracción voluntaria isométrica máxima?
- ✅ Porque los microvoltios no se pueden comparar entre personas, músculos o sesiones
- Porque así la amplitud se vuelve igual a la fuerza
- Porque así se elimina el artefacto de movimiento
- Porque así se puede distinguir el reclutamiento de la frecuencia de disparo

*Explicación:* La amplitud en microvoltios no se puede comparar entre personas, músculos o sesiones; por eso suele normalizarse, por ejemplo a la contracción voluntaria isométrica máxima. Incluso normalizada, la amplitud no permite deducir la fuerza del músculo. *Fuente:* [V2018] · *Línea firmada:* t2:58, t2:62

**Firma de Luis:** ☑ firmo

**E7 · Fatiga** *(firmada con la corrección de la hoja v2)*
Durante una contracción sostenida, ¿qué le ocurre al espectro del EMG y qué índice se usa para seguirlo?
- ✅ Se desplaza hacia frecuencias más bajas; se sigue con la frecuencia mediana
- Se desplaza hacia frecuencias más altas; se sigue con la frecuencia mediana
- No cambia; solo cambia la amplitud
- Se desplaza hacia frecuencias más bajas; se sigue con el valor máximo

*Explicación:* Durante una contracción sostenida, el espectro del EMG se "comprime" hacia frecuencias más bajas, y la frecuencia mediana es el índice preferido para seguir ese cambio. *Fuente:* [DL1997] · *Línea firmada:* t2:66

**Firma de Luis:** ☑ firmo

**E8 · Diafonía** *(firmada con la corrección de la hoja v2)*
Un electrodo sobre un músculo capta también parte de la actividad de los músculos vecinos. ¿Cómo se llama esto y hasta cuánto puede llegar?
- ✅ Diafonía (crosstalk): hasta 17 % de la actividad de los músculos vecinos
- Artefacto de movimiento: hasta 17 % de la actividad de los músculos vecinos
- Diafonía: siempre menos de 1 %
- Fatiga: hasta 50 %

*Explicación:* Diafonía (crosstalk): hasta 17 % de la actividad eléctrica de músculos vecinos puede detectarse en el electrodo. *Fuente:* [DL1997] · *Línea firmada:* t2:77

**Firma de Luis:** ☑ firmo

**E9 · Lo que sí se puede concluir** *(firmada con la corrección de la hoja v2)*
¿Cuál de estas conclusiones sí permite, con cautela, un EMG de superficie?
- ✅ Decir si un músculo está «encendido» o «apagado» en intervalos de más de unos 200 ms
- Calcular la fuerza del músculo en newtons
- Predecir cuánto crecerá el músculo con el entrenamiento
- Comparar la fuerza de dos personas por su amplitud en microvoltios

*Explicación:* Sí permite, con cautela, decir si un músculo está "encendido" o "apagado" en intervalos de más de unos 200 ms, y hacer comparaciones dentro de la misma persona y el mismo músculo si se controlan las condiciones. No permite deducir la fuerza muscular. No predice la hipertrofia ni la adaptación a largo plazo. *Fuente:* [V2018] · *Línea firmada:* t2:89, t2:86, t2:87

**Firma de Luis:** ☑ firmo

**E10 · Hipertrofia** *(firmada con la corrección de la hoja v2)*
Un ejercicio produce más amplitud de EMG que otro en el mismo músculo. ¿Permite eso afirmar que producirá más hipertrofia?
- ✅ No: la amplitud no predice la hipertrofia
- Sí: más amplitud implica más hipertrofia a largo plazo
- Sí, si la diferencia es mayor de 20 %
- Solo si la señal está normalizada

*Explicación:* No predice la hipertrofia ni la adaptación a largo plazo. *Fuente:* [V2018] · *Línea firmada:* t2:87

**Firma de Luis:** ☑ firmo

---

# Parte 2. Preguntas de HRV (8)

**H1 · Definición** *(firmada con la corrección de la hoja v2)*
¿Qué es la variabilidad de la frecuencia cardiaca (HRV)?
- ✅ La variación del tiempo entre latidos consecutivos
- El número de latidos por minuto
- La diferencia entre la frecuencia cardiaca máxima y la mínima del día
- La irregularidad causada por arritmias

*Explicación:* La HRV es la variación del tiempo entre latidos consecutivos. Se calcula sobre intervalos NN ("normal a normal"): intervalos entre latidos sinusales de los que se han retirado los artefactos. *Fuente:* [SG2017] · *Línea firmada:* t2:101, t2:103

**Firma de Luis:** ☑ firmo

**H2 · RMSSD** *(firmada con la corrección de la hoja v2)*
¿Qué afirmación sobre la RMSSD y la SDNN es correcta?
- ✅ La RMSSD está más influida por el sistema nervioso parasimpático que la SDNN
- La SDNN está más influida por el sistema nervioso parasimpático que la RMSSD
- La RMSSD es la desviación estándar de los intervalos NN
- Las dos están igual de influidas por el sistema nervioso parasimpático

*Explicación:* SDNN: desviación estándar de los intervalos NN, en ms. RMSSD: está más influida por el sistema nervioso parasimpático que la SDNN. *Fuente:* [SG2017] · *Línea firmada:* t2:110, t2:111

**Firma de Luis:** ☑ firmo

**H3 · Banda HF** *(firmada con la corrección de la hoja v2)*
¿Qué rango ocupa la banda HF y qué la modifica?
- ✅ 0.15–0.40 Hz; está influida por la respiración entre 9 y 24 respiraciones por minuto
- 0.04–0.15 Hz; está influida por la respiración
- 0.0033–0.04 Hz; está influida por la respiración entre 9 y 24 respiraciones por minuto
- 0.15–0.40 Hz; no depende de la respiración

*Explicación:* LF: 0.04–0.15 Hz. HF ("banda respiratoria"): 0.15–0.40 Hz. La banda HF está influida por la respiración entre 9 y 24 respiraciones por minuto. *Fuente:* [SG2017] · *Línea firmada:* t2:124, t2:125, t2:127

**Firma de Luis:** ☑ firmo

**H4 · Razón LF/HF** *(firmada con la corrección de la hoja v2)*
¿Qué afirmación sobre la razón LF/HF (interpretación discutida) es correcta?
- ✅ No mide con exactitud el equilibrio entre simpático y parasimpático, porque la potencia LF mezcla varias influencias
- Mide directamente el impulso simpático cardiaco
- Un valor alto demuestra predominio simpático
- Es la medida de referencia del sistema nervioso autónomo

*Explicación:* La razón LF/HF es discutida: la potencia LF no es un índice del impulso simpático cardiaco, sino una mezcla de influencias simpáticas, parasimpáticas y otras no identificadas; por eso la razón LF/HF no mide con exactitud el "equilibrio simpático-vagal". *Fuente:* [B2013][SG2017] · *Línea firmada:* t2:128

**Firma de Luis:** ☑ firmo

**H5 · Duración del registro** *(firmada con la corrección de la hoja v2)*
Una estudiante compara la SDNN de un registro de 5 minutos con la de un Holter de 24 horas. ¿Es correcto?
- ✅ No: no es apropiado comparar la SDNN calculada sobre periodos de distinta duración
- Sí, porque la SDNN no depende de la duración
- Sí, si se multiplica el valor de 5 minutos por 288
- Sí, si los dos registros son de la misma persona

*Explicación:* Los valores de registros cortos y ultracortos no son intercambiables con los de 24 horas, y no es apropiado comparar métricas como la SDNN calculadas sobre periodos de distinta duración. *Fuente:* [SG2017] · *Línea firmada:* t2:136

**Firma de Luis:** ☑ firmo

**H6 · Edad** *(firmada con la corrección de la hoja v2)*
¿Qué les ocurre a las medidas de HRV del dominio del tiempo con la edad?
- ✅ Disminuyen
- Aumentan
- No cambian
- Solo dependen de la duración del registro, no de la edad

*Explicación:* La duración del registro, la edad y el sexo influyen en los valores basales; las medidas del dominio del tiempo disminuyen con la edad. *Fuente:* [SG2017] · *Línea firmada:* t2:155

**Firma de Luis:** ☑ firmo

**H7 · Entropía muestral** *(firmada con la corrección de la hoja v2)*
La entropía muestral se diseñó como:
- ✅ Una medida menos sesgada y más fiable de la regularidad y la complejidad de la señal
- Una medida de la potencia de la banda HF
- Un método para detectar latidos ectópicos
- Una forma de calcular la frecuencia cardiaca media

*Explicación:* Entropía muestral: se diseñó como una medida menos sesgada y más fiable de la regularidad y la complejidad de la señal. *Fuente:* [SG2017] · *Línea firmada:* t2:150

**Firma de Luis:** ☑ firmo

**H8 · Valores de referencia** *(firmada con la corrección de la hoja v2)*
¿Existe un único «valor normal» de HRV?
- ✅ No: depende de la duración del registro, la edad y el sexo
- Sí: el mismo para todas las edades, sexos y duraciones del registro
- Sí, pero solo para registros de 5 minutos
- Sí, el que calcula el equipo

*Explicación:* No hay un único "valor normal": los valores de referencia dependen de la duración del registro, la edad y el sexo, y los de registros cortos no sirven para comparar con los de 24 horas. *Fuente:* [SG2017] · *Línea firmada:* t2:169

**Firma de Luis:** ☑ firmo

---

# Parte 3. Casos clínicos con señal real (6 casos, 8 preguntas)

> **Después de hoy.** No forma parte de la firma del 2026-11-17: no entra a la app.

> Las viñetas describen personas sanas en contextos de deporte, docencia o investigación. Ninguna plantea un diagnóstico ni una lesión (A9).

## C1. Brazo sostenido (EMG · fatiga)
**Señal:** EMG de fatiga [EB2020]. Bíceps, 6 kg, codo a 90°, 120 s.
**Viñeta:** Andrea, de 22 años y estudiante de fisioterapia, sostiene una pesa de 6 kg con el codo a 90° durante dos minutos mientras se registra su bíceps.

**C1.1** Si se compara el inicio con el final del registro, ¿qué cabe esperar?
- ✅ Que la frecuencia mediana del espectro baje
- Que la frecuencia mediana suba
- Que la señal desaparezca
- Que el espectro no cambie

*Fuente:* [DL1997]
> **Línea firmada (t2:66):** **Idea.** Durante una contracción sostenida, el espectro del EMG se "comprime" hacia frecuencias más bajas, y la frecuencia mediana es el índice preferido para seguir ese cambio [DL1997].

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

## C2. Tres esfuerzos y un día con dolor (EMG · normalización)
**Señal:** HD-sEMG del codo [RM2020]. Bíceps y tríceps al 10, 30 y 50 % de la contracción máxima.
**Viñeta:** Diego, de 28 años, participa en un estudio de fuerza. En la primera sesión hace contracciones al 10, 30 y 50 % de su máximo. En la segunda refiere dolor durante la prueba de contracción máxima, y sus valores normalizados salen más altos que en la primera.

**C2.1** ¿Cuál es la interpretación más prudente?
- ✅ Si no alcanzó su máximo real por el dolor, los valores normalizados quedan inflados
- Su músculo se volvió más fuerte entre sesiones
- El electrodo mide mejor cuando hay dolor
- Los valores son comparables porque están normalizados

*Fuente:* [V2018]
> **Línea firmada (t2:60):** **Mecanismo.** Si la persona no alcanza su máximo real durante la prueba de referencia (por dolor, por ejemplo), los valores normalizados quedan inflados [V2018].

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**C2.2** En la primera sesión, el bíceps dio más microvoltios que el tríceps. ¿Se puede concluir que el bíceps «trabajó más»?
- ✅ No: los microvoltios no se pueden comparar entre músculos
- Sí, porque son la misma persona y la misma sesión
- Sí, si se usa el RMS
- Sí, si la diferencia es mayor de 10 %

*Fuente:* [V2018]
> **Línea firmada (t2:58):** **Idea.** La amplitud en microvoltios no se puede comparar entre personas, músculos o sesiones; por eso suele normalizarse, por ejemplo a la contracción voluntaria isométrica máxima [V2018].

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

## C3. El mismo gesto en tres días (EMG · comparar sesiones)
**Señal:** GRABMyoFlow [EH2026]. EMG de muñeca y antebrazo de un participante en tres sesiones.
**Viñeta:** un equipo quiere saber si la activación del antebrazo de Sofía cambia entre tres días de práctica del mismo gesto.

**C3.1** ¿Qué condición es imprescindible para comparar los tres días?
- ✅ Que los electrodos vayan en el mismo sitio de la piel respecto al músculo
- Que Sofía haga el gesto más rápido cada día
- Que el registro dure exactamente 10 minutos
- Ninguna: el EMG de superficie no cambia entre días

*Fuente:* [V2018]
> **Línea firmada (t2:36):** - Para comparar registros, los electrodos deben ir en el mismo sitio de la piel respecto al músculo [V2018].

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**C3.2** Si se cumplen las condiciones, ¿qué tipo de comparación es la más defendible?
- ✅ Dentro de la misma persona y el mismo músculo, con las condiciones controladas
- Entre Sofía y otras personas, en microvoltios
- Entre el músculo de Sofía y uno vecino
- Ninguna comparación es posible

*Fuente:* [V2018]
> **Línea firmada (t2:89):** - **Sí** permite, con cautela, decir si un músculo está "encendido" o "apagado" en intervalos de más de unos 200 ms, y hacer comparaciones dentro de la misma persona y el mismo músculo si se controlan las condiciones.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

## C4. Dos voluntarios de edades distintas (HRV · edad)
**Señal:** Autonomic Aging [SB2022]. Un voluntario de 25 años y una voluntaria de 70 años, en reposo.
**Viñeta:** se registran en reposo un hombre de 25 años y una mujer de 70 años, los dos sanos. La RMSSD de ella sale más baja.

**C4.1** ¿Qué explica, al menos en parte, la diferencia?
- ✅ La edad y el sexo influyen en los valores basales de la HRV
- La diferencia demuestra que ella tiene una enfermedad
- La RMSSD no depende de la edad
- La diferencia se debe solo al equipo

*Fuente:* [SG2017]
> **Línea firmada (t2:155):** **Detalle.** La duración del registro, la edad y el sexo influyen en los valores basales; las medidas del dominio del tiempo disminuyen con la edad [SG2017]. La respiración modifica la banda HF (ver B3 y B5) [SG2017].

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

## C5. Respirar lento (HRV · respiración) *(corregido: la viñeta rotula la razón LF/HF como pide B3)*
**Señal:** Fantasia [IY1996], ECG con su canal de respiración para medir la frecuencia respiratoria.
**Viñeta:** Mateo, de 24 años, practica biofeedback y respira unas 6 veces por minuto. Su **razón LF/HF (interpretación discutida)** [B2013] sube mucho respecto a su respiración espontánea.

**C5.2** ¿Cómo se interpreta esa subida?
- ✅ No indica más actividad simpática: la respiración cambió la banda en la que aparece la variabilidad, y la razón LF/HF no mide con exactitud el equilibrio autonómico
- Indica que Mateo está estresado
- Indica predominio simpático
- Indica que el registro es erróneo

*Fuente:* [SG2017][B2013]
> **Líneas firmadas (t2:142):** **Detalle.** Por eso la frecuencia respiratoria cambia la banda en la que aparece esa variabilidad (ver B3) [SG2017].
> **(t2:128):** - **La razón LF/HF es discutida:** la potencia LF no es un índice del impulso simpático cardiaco, sino una mezcla de influencias simpáticas, parasimpáticas y otras no identificadas; por eso la razón LF/HF no mide con exactitud el "equilibrio simpático-vagal" [B2013][SG2017].

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

## C6. Latidos fuera de lugar (HRV · artefactos)
**Señal:** MIT-BIH Arrhythmia [MM2001], registro con latidos ectópicos anotados.
**Viñeta:** al calcular la HRV de un registro, la serie de intervalos muestra saltos bruscos que coinciden con latidos ectópicos.

**C6.1** *(corregida: se retiró de la explicación la frase de Laborde 2017, fuente no firmada, y se cambió el distractor de la razón LF/HF)* ¿Qué opciones hay antes de calcular las métricas?
- ✅ Elegir un tramo sin artefactos, editar los intervalos afectados o interpolar los latidos perdidos
- Calcular con todos los latidos, porque los ectópicos también son variabilidad
- Duplicar los latidos normales para compensar
- Calcular solo la frecuencia cardiaca media, que no se afecta

*Fuente:* [SG2017]
> **Línea firmada (t2:165):** **Detalle.** Editar los latidos ectópicos y las arritmias es difícil; se puede elegir un tramo sin artefactos, editar los intervalos afectados o interpolar los latidos perdidos [SG2017].

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

---

# Hoja de firma

| # | Enunciado | Respuesta correcta | Línea firmada | Clave | Estado | Firma de Luis (2026-11-17) |
|---|---|---|---|---|---|---|
| E1 | ¿Qué registra un electrodo de EMG de superficie? | La suma de los potenciales de acción de las unidades motoras activas bajo el electrodo | t2:13 | DL1997 | Tal cual | ☑ firmo |
| E2 | ¿Qué indica una amplitud más alta del EMG de superficie? | Mayor excitación del músculo, no su fuerza | t2:17, t2:62 | V2018 | Corregida (hoja v2) | ☑ firmo |
| E3 | El músculo aumenta su fuerza de dos maneras: activando unidades motoras nuevas (reclutamiento) y haciendo que las ya activas disparen más rápido. ¿Puede la amplitud del EMG de superficie decir cuánto del aumento se debe a cada una? | No: la amplitud no permite distinguir cuánto se debe a cada una | t2:25 | DL1997, V2018 | Corregida (hoja v2) | ☑ firmo |
| E4 | ¿Por qué se recomienda un filtro pasa-altas de 20 Hz para el EMG de superficie? | Porque el artefacto de movimiento concentra su energía en frecuencias bajas | t2:45 | DL2010 | Corregida (hoja v2) | ☑ firmo |
| E5 | Para medir la amplitud de una contracción voluntaria, ¿qué medida se recomienda y por qué? | El RMS, porque representa la potencia de la señal y tiene un significado físico claro | t2:54 | DL1997 | Corregida (hoja v2) | ☑ firmo |
| E6 | ¿Por qué suele normalizarse la amplitud del EMG, por ejemplo a la contracción voluntaria isométrica máxima? | Porque los microvoltios no se pueden comparar entre personas, músculos o sesiones | t2:58, t2:62 | V2018 | Corregida (hoja v2) | ☑ firmo |
| E7 | Durante una contracción sostenida, ¿qué le ocurre al espectro del EMG y qué índice se usa para seguirlo? | Se desplaza hacia frecuencias más bajas; se sigue con la frecuencia mediana | t2:66 | DL1997 | Corregida (hoja v2) | ☑ firmo |
| E8 | Un electrodo sobre un músculo capta también parte de la actividad de los músculos vecinos. ¿Cómo se llama esto y hasta cuánto puede llegar? | Diafonía (crosstalk): hasta 17 % de la actividad de los músculos vecinos | t2:77 | DL1997 | Corregida (hoja v2) | ☑ firmo |
| E9 | ¿Cuál de estas conclusiones sí permite, con cautela, un EMG de superficie? | Decir si un músculo está «encendido» o «apagado» en intervalos de más de unos 200 ms | t2:89, t2:86, t2:87 | V2018 | Corregida (hoja v2) | ☑ firmo |
| E10 | Un ejercicio produce más amplitud de EMG que otro en el mismo músculo. ¿Permite eso afirmar que producirá más hipertrofia? | No: la amplitud no predice la hipertrofia | t2:87 | V2018 | Corregida (hoja v2) | ☑ firmo |
| H1 | ¿Qué es la variabilidad de la frecuencia cardiaca (HRV)? | La variación del tiempo entre latidos consecutivos | t2:101, t2:103 | SG2017 | Corregida (hoja v2) | ☑ firmo |
| H2 | ¿Qué afirmación sobre la RMSSD y la SDNN es correcta? | La RMSSD está más influida por el sistema nervioso parasimpático que la SDNN | t2:110, t2:111 | SG2017 | Corregida (hoja v2) | ☑ firmo |
| H3 | ¿Qué rango ocupa la banda HF y qué la modifica? | 0.15–0.40 Hz; está influida por la respiración entre 9 y 24 respiraciones por minuto | t2:124, t2:125, t2:127 | SG2017 | Corregida (hoja v2) | ☑ firmo |
| H4 | ¿Qué afirmación sobre la razón LF/HF (interpretación discutida) es correcta? | No mide con exactitud el equilibrio entre simpático y parasimpático, porque la potencia LF mezcla varias influencias | t2:128 | B2013, SG2017 | Corregida (hoja v2) | ☑ firmo |
| H5 | Una estudiante compara la SDNN de un registro de 5 minutos con la de un Holter de 24 horas. ¿Es correcto? | No: no es apropiado comparar la SDNN calculada sobre periodos de distinta duración | t2:136 | SG2017 | Corregida (hoja v2) | ☑ firmo |
| H6 | ¿Qué les ocurre a las medidas de HRV del dominio del tiempo con la edad? | Disminuyen | t2:155 | SG2017 | Corregida (hoja v2) | ☑ firmo |
| H7 | La entropía muestral se diseñó como: | Una medida menos sesgada y más fiable de la regularidad y la complejidad de la señal | t2:150 | SG2017 | Corregida (hoja v2) | ☑ firmo |
| H8 | ¿Existe un único «valor normal» de HRV? | No: depende de la duración del registro, la edad y el sexo | t2:169 | SG2017 | Corregida (hoja v2) | ☑ firmo |
| C1.1 | Inicio frente a final del registro | Baja la frecuencia mediana | t2:66 | DL1997 | Lista | después de hoy |
| C2.1 | Normalizados altos con dolor en la prueba máxima | Quedan inflados | t2:60 | V2018 | Lista | después de hoy |
| C2.2 | Bíceps frente a tríceps en µV | No se comparan | t2:58 | V2018 | Lista | después de hoy |
| C3.1 | Condición para comparar tres días | Electrodos en el mismo sitio | t2:36 | V2018 | Lista | después de hoy |
| C3.2 | Comparación más defendible | Misma persona y músculo, condiciones controladas | t2:89 | V2018 | Lista | después de hoy |
| C4.1 | RMSSD más baja de ella | La edad y el sexo influyen | t2:155 | SG2017 | Lista | después de hoy |
| C5.2 | Sube la razón LF/HF (interpretación discutida) | La respiración cambió la banda | t2:142, t2:128 | SG2017, B2013 | Corregida | después de hoy |
| C6.1 | Ectópicos antes de calcular | Tramo limpio, editar o interpolar | t2:165 | SG2017 | Corregida | después de hoy |

---

# Apéndice. Fuera de esta hoja: primero hay que firmar la afirmación en la teoría

> **Después de hoy.** No forma parte de la firma del 2026-11-17: no entra a la app.

Estas 10 preguntas usan afirmaciones que no están en `teoria_citada_2.md`. Para recuperarlas, primero se redacta y se firma la afirmación como tema nuevo de la teoría, y después vuelve la pregunta.

| # | Afirmación que habría que firmar | Fuente propuesta | Depende de |
|---|---|---|---|
| C1.2 | Un registro a 200 muestras/s no contiene información por encima de 100 Hz (frecuencia de Nyquist) | Definición de muestreo; habría que firmarla | — |
| C4.2 | Preparación previa al registro: sin comida ni cafeína 2 h antes, sin alcohol 24 h antes y sin ejercicio intenso el día anterior | [L2017] | D1 y D2 (B7) |
| C5.1 | Respirar entre 4.5 y 7.5 veces por minuto concentra la oscilación cardiaca alrededor de 0.1 Hz, en la banda LF | [SG2017] | — |
| C6.2 | El sesgo de un solo artefacto puede superar los efectos que suele medir un estudio | [SG2017] | — |

---

# Decisiones para Luis

> **Después de hoy.** No forma parte de la firma del 2026-11-17: no entra a la app.

| # | Decisión | Opciones |
|---|---|---|
| D1 | ¿Se acepta la fuente **[L2017]** (Laborde, Mosley y Thayer 2017) para una teoría futura? Hoy no está en ninguna rama. | ☐ sí ☐ no |
| D2 | ¿Se amplía **B7** con la frecuencia cardiaca y con la preparación previa al registro? | ☐ ampliar ☐ dejar B7 como está |
| D3 | **B9:** [SG2017] da puntos de corte de SDNN en 24 horas. ¿Se firman como tema nuevo o se sigue sin cifras? | ☐ tema nuevo ☐ sin cifras |
| D4 | Excluir **Examples of Electromyograms** (EMG de aguja, uso diagnóstico) por A9. | ☐ excluir ☐ incluir con otro marco |
| D5 | Verificar las licencias de Fantasia, del EMG de fatiga (Zenodo) y del HD-sEMG (figshare), y llevar las referencias de las bases a la Bibliografía antes de guardar extractos de señal. | ☐ hecho |

---

# Bibliografía

**De las respuestas** (ya firmadas en `teoria_citada_2.md`; llegan a la Bibliografía de la app con la rama `teoria-emg-hrv`): [DL1997], [DL2010], [V2018], [SG2017] y [B2013].

**De las señales de los casos** (no sostienen ninguna respuesta):
- **[IY1996]** Iyengar N, Peng C-K, Morin R, Goldberger AL, Lipsitz LA. Age-related alterations in the fractal scaling of cardiac interbeat interval dynamics. *Am J Physiol*. 1996;271(4 Pt 2):R1078–R1084. doi:10.1152/ajpregu.1996.271.4.R1078. Describe la base Fantasia.
- **[SB2022]** Schumann A, Bär KJ. Autonomic aging – A dataset to quantify changes of cardiovascular autonomic function during healthy aging. *Sci Data*. 2022;9:95. doi:10.1038/s41597-022-01202-y.
- **[MM2001]** Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. *IEEE Eng Med Biol*. 2001;20(3):45–50. Ya citada en el repositorio.
- **[RM2020]** Rojas-Martínez M, Serna LY, Jordanic M, Marateb HR, Merletti R, Mañanas MÁ. High-density surface electromyography signals during isometric contractions of elbow muscles of healthy humans. *Sci Data*. 2020;7:397. doi:10.1038/s41597-020-00717-6.
- **[EB2020]** Ebied A, Awadallah AM, Abbass MA, El-Sharkawy Y. Upper limb muscle fatigue analysis using multi-channel surface EMG. *NILES 2020*. 2020:423–427. doi:10.1109/NILES50944.2020.9257909. Datos: Zenodo 5189275.
- **[EH2026]** Ehlert CL, Tung J, Pradhan A. GRABMyoFlow – Dataset extension (versión 1.0.0). *PhysioNet*. 2026. doi:10.13026/ah52-zq51.
- **Cita estándar de PhysioNet:** Goldberger AL, Amaral LAN, Glass L, et al. PhysioBank, PhysioToolkit, and PhysioNet: components of a new research resource for complex physiologic signals. *Circulation*. 2000;101(23):e215–e220.

**Propuesta para una teoría futura** (apéndice; no sostiene ninguna pregunta de esta hoja):
- **[L2017]** Laborde S, Mosley E, Thayer JF. Heart rate variability and cardiac vagal tone in psychophysiological research – Recommendations for experiment planning, data analysis, and data reporting. *Front Psychol*. 2017;8:213. doi:10.3389/fpsyg.2017.00213.
