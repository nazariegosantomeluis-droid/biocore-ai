# Caso guiado de ECG 2: elevación del ST en V1–V4 (FIRMADO)

**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome («Firmo el caso guiado 2»): todos los textos de este documento tal como están (C2-D1–D4, C2-P1–P4, C2-DS y C2-C).
**Uso:** `educational/guided_case_anterior.py` contiene este caso; `app/supermodules/academia/guided_case_view.py` lo muestra en Practicar → «Caso guiado de ECG» junto al caso 1, **solo si este documento dice «FIRMADO»**.
**Regla:** la misma del caso 1. Todo texto de enseñanza cita su línea firmada del tema 5 de `teoria_citada.md` («t1:N») con [W2009]; los resultados de las pruebas los mide el analizador sobre el trazado simulado; `tests/test_guided_case_2.py` exige que cada texto del código esté en este documento y que cada línea citada exista literal. «Se eleva» = la medición queda por encima de la línea de base al redondear a 0.1 mm (el criterio de signo del caso 1); no es el umbral diagnóstico de la ESC, que aplica el analizador en 12 Derivaciones.

---

## 1. El trazado

- **Simulado**, y así se declara en pantalla: `generate_twelve_lead("anterior_stemi", seed=7)`, 10 s a 500 muestras/s.
- **ST medido por el analizador** (`analyze_twelve_lead`, punto J, en mm; medido el 2026-11-17; las semillas 1, 2 y 42 dan lo mismo ±0.1 mm):

| I | II | III | aVR | aVL | aVF | V1 | V2 | V3 | V4 | V5 | V6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| +0.0 | -0.7 | -0.7 | +0.3 | +0.4 | -0.7 | +2.0 | +3.5 | +3.5 | +2.5 | +0.5 | +0.0 |

## 2. Líneas firmadas que usa el caso

- **t1:72:** **Idea.** Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada y, con menos certeza, hacia la arteria responsable [W2009].
- **t1:78:** | Elevación del ST en V1–V4, I, aVL y a menudo aVR | Oclusión proximal de la descendente anterior | La isquemia de la pared anterior se debe a oclusión de la descendente anterior (DA). |
- **t1:79:** | Elevación del ST sobre todo en V3–V6 | Oclusión distal de la DA | — |
- **t1:80:** | Oclusión de la DA entre la primera rama septal y la primera diagonal | Se respeta el tabique basal | El ST de V1 no se eleva. |

## 3. Decisiones (la correcta va primero)

**C2-D1 · grupo.** Mira el trazado. ¿En qué grupo de derivaciones está más elevado el ST?
- ✅ V1–V4
- II, III y aVF, las tres derivaciones que miran desde abajo
- I y aVL, junto con V5 y V6 del lado izquierdo
- En ninguno: el ST está en la línea de base en las doce

*Explicación:* El analizador mide la mayor elevación del ST en V1–V4. *Sale de la medición del caso.*

**Firma de Luis:** ☑ firmado (17-11-2026)

**C2-D2 · hipotesis_inicial.** Con solo ese dato, ¿hacia qué arteria orienta la tabla firmada?
- ✅ La descendente anterior; el sitio de la oclusión depende de qué otras derivaciones se eleven
- La coronaria derecha, porque es la arteria que más a menudo se ocluye en un infarto con elevación del ST
- La circunfleja, porque es la arteria que irriga a la vez la pared anterior y la lateral del ventrículo
- Ninguna: la elevación del ST en V1–V4 no orienta hacia una arteria responsable concreta en ningún caso

*Explicación:* Las tres filas de la tabla que tratan las precordiales (oclusión proximal, distal y entre la primera septal y la primera diagonal) son de la descendente anterior [W2009]. *Línea firmada:* t1:78.

**Firma de Luis:** ☑ firmado (17-11-2026)

**C2-D3 · hipotesis_final.** Con las pruebas que pediste, ¿qué sugiere el trazado sobre el sitio de la oclusión?
- ✅ Sugiere la descendente anterior, pero el sitio no se puede precisar: falta la elevación en I
- Oclusión proximal de la descendente anterior, con seguridad, porque V1–V4 están elevados en el trazado
- Oclusión distal de la descendente anterior, porque la elevación está sobre todo en V3–V6 de este trazado
- Oclusión entre la primera septal y la primera diagonal, porque el ST de V1 no se eleva en este trazado

*Explicación:* La oclusión proximal se acompaña de elevación en V1–V4, I, aVL y a menudo aVR; la distal, sobre todo en V3–V6; y entre la primera septal y la primera diagonal, el ST de V1 no se eleva [W2009]. Este trazado no cumple del todo ninguno de los tres. *Línea firmada:* t1:78.

**Firma de Luis:** ☑ firmado (17-11-2026)

**C2-D4 · limite.** Antes de cerrar: ¿puedes afirmar cuál es la arteria responsable?
- ✅ No: el ECG orienta hacia la arteria responsable, con menos certeza que hacia la región
- Sí: la tabla firmada lo demuestra con la elevación del ST en V1–V4 que mide el analizador en este trazado
- Sí, porque V2 y V3 son las derivaciones más elevadas de todo el registro simulado de doce derivaciones
- No, porque la elevación en V1–V4 orienta a la coronaria derecha y no a la descendente anterior del caso

*Explicación:* Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada y, con menos certeza, hacia la arteria responsable [W2009]. *Línea firmada:* t1:72.

**Firma de Luis:** ☑ firmado (17-11-2026)

## 4. Pruebas que el estudiante puede pedir (el motivo correcto va primero)

**C2-P1 · Revisar el ST en V1** (línea firmada t1:80)
- ✅ Ver si V1 se eleva: si no se eleva, la oclusión de la DA puede estar entre la primera septal y la primera diagonal
- Medir la duración del QRS en V1 para compararla con la de las demás derivaciones precordiales del trazado simulado
- Calcular la frecuencia cardiaca a partir de los intervalos RR que se ven en la tira de V1, latido por latido y en reposo

*Resultado:* V1 +2.0 mm: V1 se eleva.

**Firma de Luis:** ☑ firmado (17-11-2026)

**C2-P2 · Revisar el ST en I y aVL** (línea firmada t1:78)
- ✅ Ver si I y aVL se elevan, lo que junto con V1–V4 sugiere oclusión proximal de la descendente anterior
- Medir el intervalo PR en I y aVL, que son las derivaciones donde mejor se ve la onda P de este trazado simulado
- Calcular el eje del QRS con I y aVL, que es lo único que esas dos derivaciones del plano frontal permiten medir

*Resultado:* I +0.0 mm · aVL +0.4 mm: I no se eleva y aVL se eleva.

**Firma de Luis:** ☑ firmado (17-11-2026)

**C2-P3 · Revisar el ST en V3–V6** (línea firmada t1:79)
- ✅ Ver si la elevación está sobre todo en V3–V6, que sugiere oclusión distal de la DA
- Medir el intervalo QT en V5 y V6, donde la onda T termina con más claridad que en las demás
- Buscar descenso del ST en V5–V6, el patrón llamado «posterior» que describe la tabla del tema 5

*Resultado:* V3 +3.5 mm · V4 +2.5 mm · V5 +0.5 mm · V6 +0.0 mm: V5 y V6 se elevan menos que V3 y V4.

**Firma de Luis:** ☑ firmado (17-11-2026)

**C2-P4 · Revisar el ST en aVR** (línea firmada t1:78)
- ✅ Ver si aVR se eleva, como ocurre a menudo en la oclusión proximal de la descendente anterior
- Medir la duración del QRS en aVR para saber si hay un bloqueo de rama en el trazado del caso
- Calcular la frecuencia cardiaca con aVR, que es la derivación de referencia para contar los latidos

*Resultado:* aVR +0.3 mm: aVR se eleva.

**Firma de Luis:** ☑ firmado (17-11-2026)

## 5. Desafío a la hipótesis final (revisor crítico, por reglas, sin modelo de lenguaje)

- **C2-DS1:** ¿Qué dato te falta para precisar el sitio? La oclusión proximal se acompaña de elevación en V1–V4, I, aVL y a menudo aVR [W2009], y todavía no revisaste I y aVL.
- **C2-DS2:** Tu conclusión se apoya en lo que mediste: I +0.0 mm · aVL +0.4 mm. La oclusión proximal se acompaña de elevación en V1–V4, I, aVL y a menudo aVR [W2009]. ¿Qué te falta para precisar el sitio?
- **C2-DS3:** La oclusión proximal se acompaña de elevación en V1–V4, I, aVL y a menudo aVR [W2009], y en este trazado miden I +0.0 mm · aVL +0.4 mm · aVR +0.3 mm. ¿Se cumple el patrón completo?
- **C2-DS4:** La oclusión distal eleva el ST sobre todo en V3–V6 [W2009], y en este trazado miden V3 +3.5 mm · V4 +2.5 mm · V5 +0.5 mm · V6 +0.0 mm. ¿Dónde está la mayor elevación?
- **C2-DS5:** Entre la primera septal y la primera diagonal, el ST de V1 no se eleva [W2009], y en este trazado mide V1 +2.0 mm. ¿Qué dato apoya tu respuesta?

*Líneas firmadas:* t1:78, t1:79 y t1:80.

**Firma de Luis:** ☑ firmado (17-11-2026)

## 6. Qué se evalúa (además del acierto)

| ID | Competencia | Evidencia que ve el estudiante |
|---|---|---|
| C2-C1 | Reconoce hacia qué arteria orienta el primer dato | Las tres filas de la tabla que tratan las precordiales son de la descendente anterior [W2009]. |
| C2-C2 | Pide las pruebas que distinguen los tres patrones | V1 (t1:80), I y aVL (t1:78) y V3–V6 (t1:79) separan los tres patrones de la descendente anterior [W2009]. |
| C2-C3 | Justifica cada prueba que pide | Cada prueba pedida, con el motivo que la sostiene. |
| C2-C4 | No afirma más de lo que el trazado permite | Este trazado no cumple del todo ninguno de los tres patrones: el sitio no se puede precisar. |
| C2-C5 | Reconoce el límite del ECG | El ECG orienta hacia la arteria responsable con menos certeza que hacia la región [W2009]. |

Cada decisión se registra una vez por intento con `log_session_answer(..., "caso_guiado", "derivaciones_e_isquemia", ...)`, con el id `caso_guiado:st_v1_v4:<decisión>`, y entra al panel de calibración.

## 7. Hoja de firma

> Firmo el caso guiado 2. — Luis Nazariego Santome, 17/11/2026

| ID | Decisión de Luis |
|---|---|
| C2-D1 | ☑ firmado (17-11-2026) |
| C2-D2 | ☑ firmado (17-11-2026) |
| C2-D3 | ☑ firmado (17-11-2026) |
| C2-D4 | ☑ firmado (17-11-2026) |
| C2-P1 | ☑ firmado (17-11-2026) |
| C2-P2 | ☑ firmado (17-11-2026) |
| C2-P3 | ☑ firmado (17-11-2026) |
| C2-P4 | ☑ firmado (17-11-2026) |
| C2-DS (desafíos) | ☑ firmado (17-11-2026) |
| C2-C (competencias) | ☑ firmado (17-11-2026) |

