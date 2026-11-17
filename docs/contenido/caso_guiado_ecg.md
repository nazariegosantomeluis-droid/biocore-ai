# Caso guiado de ECG: elevación del ST en II, III y aVF (borrador para firma)

**Estado:** BORRADOR, sin firmar (17 de noviembre de 2026).
**Uso:** `educational/guided_case.py` contiene este caso y `app/supermodules/academia/guided_case_view.py` lo muestra. La pantalla **solo muestra el caso si este documento dice «FIRMADO»**; hasta entonces dice que está pendiente de firma. Montar la página en el menú (Practicar) también es decisión de Luis.
**Regla:** todo texto de enseñanza cita su línea firmada del tema 5 de `teoria_citada.md` («t1:N») con [W2009]. Los resultados de las pruebas no se escriben a mano: los mide el analizador de BIOCORE sobre el trazado simulado. `tests/test_guided_case.py` exige que cada pregunta, opción y motivo del código aparezca en este documento, y que cada línea citada exista en la teoría firmada.

---

## 1. El trazado

- **Simulado**, y así se declara en pantalla: `generate_twelve_lead("inferior_stemi", seed=7)`, 10 s a 500 muestras/s, 75 lpm, ritmo sinusal.
- **ST medido por el analizador** (`analyze_twelve_lead`, punto J, en mm):

| I | II | III | aVR | aVL | aVF | V1 | V2 | V3 | V4 | V5 | V6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -0.7 | +2.1 | +2.9 | -0.7 | -1.8 | +2.5 | +0.0 | +0.0 | +0.0 | +0.0 | +0.0 | +0.0 |

- No hay **derivaciones derechas** (V3R, V4R): el simulador solo genera las 12 estándar. Es la información incompleta del caso, a propósito.

## 2. Líneas firmadas que usa el caso

- **t1:72:** **Idea.** Los cambios del segmento ST en un grupo de derivaciones orientan hacia la región del ventrículo afectada y, con menos certeza, hacia la arteria responsable [W2009].
- **t1:78:** | Elevación del ST en V1–V4, I, aVL y a menudo aVR | Oclusión proximal de la descendente anterior | La isquemia de la pared anterior se debe a oclusión de la descendente anterior (DA). |
- **t1:81:** | Elevación del ST en II, III y aVF | Afectación inferior | Coronaria derecha (CD) o circunfleja (Cx), según cuál dé la descendente posterior (dominancia). Elevación mayor en III que en II sugiere CD. |
- **t1:82:** | Elevación en I y aVL junto con cambios inferiores | Puede acompañar la oclusión de la Cx | — |
- **t1:83:** | Elevación del ST en V3R y V4R (derivaciones derechas) | Afectación del ventrículo derecho | Oclusión proximal de la CD. |
- **t1:84:** | Descenso del ST en V1–V3 | Patrón llamado "posterior" o posterolateral | Puede deberse a CD o Cx; con cambios inferiores no es posible saber cuál. |

## 3. Decisiones (la correcta va primero)

**grupo.** Mira el trazado. ¿En qué grupo de derivaciones está más elevado el ST?
- ✅ II, III y aVF
- V1–V4
- I, aVL, V5 y V6
- En ninguno: el ST está en la línea de base

*Explicación:* El analizador mide la mayor elevación del ST en II, III y aVF. *Sale de la medición del caso.*

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**hipotesis_inicial.** Con solo ese dato, ¿qué arteria es la responsable?
- ✅ La coronaria derecha o la circunfleja: con este dato no se puede decir cuál
- La coronaria derecha, con seguridad
- La circunfleja, con seguridad
- La descendente anterior

*Explicación:* Una elevación del ST en II, III y aVF puede deberse a la coronaria derecha o a la circunfleja, según cuál dé la descendente posterior [W2009]. Hace falta otro dato para orientarse. *Línea firmada:* t1:81.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**hipotesis_final.** Con las pruebas que pediste, ¿qué sugiere el trazado?
- ✅ Sugiere coronaria derecha: la elevación es mayor en III que en II
- Sugiere circunfleja
- Sugiere descendente anterior
- Sigue sin poder distinguirse entre coronaria derecha y circunfleja

*Explicación:* Una elevación mayor en III que en II sugiere coronaria derecha [W2009]. «Sugiere» no es «demuestra». *Línea firmada:* t1:81.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**limite.** Antes de cerrar: ¿puedes afirmar que el ventrículo derecho está afectado?
- ✅ No: haría falta ver V3R y V4R, y este registro no las tiene
- Sí, porque hay elevación en II, III y aVF
- Sí, porque III es mayor que II
- No, porque la coronaria derecha no se relaciona con el ventrículo derecho

*Explicación:* La afectación del ventrículo derecho se ve como elevación del ST en V3R y V4R [W2009]. Sin esas derivaciones, no se puede afirmar ni descartar. *Línea firmada:* t1:83.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

## 4. Pruebas que el estudiante puede pedir (el motivo correcto va primero)

Para pedir una prueba, el estudiante elige por qué la pide. El resultado es el del caso medido.

**Medir el ST en II, III y aVF** (línea firmada t1:81)
- ✅ Comparar II con III: una elevación mayor en III que en II sugiere coronaria derecha
- Calcular la frecuencia cardiaca
- Buscar una onda delta

*Resultado:* II +2.1 mm · III +2.9 mm · aVF +2.5 mm. III es mayor que II.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**Revisar el ST en I y aVL** (línea firmada t1:82)
- ✅ Ver si hay elevación en I y aVL, que junto con cambios en II, III y aVF puede acompañar a la circunfleja
- Medir el intervalo PR
- Calcular el eje del QRS

*Resultado:* I -0.7 mm · aVL -1.8 mm: descenso, no elevación.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**Revisar el ST en V1–V3** (línea firmada t1:84)
- ✅ Buscar descenso del ST en V1–V3, el patrón llamado «posterior»
- Medir la duración del QRS
- Buscar una onda delta

*Resultado:* V1 +0.0 mm · V2 +0.0 mm · V3 +0.0 mm: no hay descenso.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**Revisar el ST en V1–V4** (línea firmada t1:78)
- ✅ Descartar la elevación en V1–V4 que orienta a la descendente anterior
- Calcular la frecuencia cardiaca
- Medir el intervalo QT

*Resultado:* V1 +0.0 mm · V2 +0.0 mm · V3 +0.0 mm · V4 +0.0 mm: no hay elevación.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

**Pedir V3R y V4R (derivaciones derechas)** (línea firmada t1:83)
- ✅ Buscar afectación del ventrículo derecho, que orienta a oclusión proximal de la coronaria derecha
- Mejorar la calidad del trazado
- Calcular el eje del QRS

*Resultado:* No disponible: este registro no tiene derivaciones derechas; el simulador solo genera las 12 estándar. Con lo que hay no se puede saber si el ventrículo derecho está afectado.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

## 5. Desafío a la hipótesis final (revisor crítico, por reglas, sin modelo de lenguaje)

Antes de cerrar, el caso cuestiona la respuesta con evidencia del propio caso. El estudiante puede mantenerla, cambiarla o pedir más pruebas. Texto según la respuesta y las pruebas pedidas (con las cifras de este trazado):

- **Coronaria derecha, sin haber comparado II con III:** ¿Qué dato te permite distinguir la coronaria derecha de la circunfleja? Con elevación en II, III y aVF las dos son posibles [W2009], y todavía no comparaste II con III.
- **Coronaria derecha, después de comparar II con III:** Tu conclusión se apoya en lo que mediste: III (+2.9 mm) mayor que II (+2.1 mm) sugiere coronaria derecha [W2009]. Sugerir no es demostrar: ¿qué no puedes afirmar todavía con este registro?
- **Circunfleja, habiendo revisado I y aVL:** Pediste I y aVL y tienen descenso (I -0.7 mm · aVL -1.8 mm), no elevación. La elevación en I y aVL junto con cambios en II, III y aVF es la que puede acompañar a la circunfleja [W2009]. ¿Qué dato apoya tu respuesta?
- **Circunfleja, sin revisar I y aVL:** ¿Qué dato apoya la circunfleja? La elevación en I y aVL junto con cambios en II, III y aVF puede acompañarla [W2009], y no la has revisado.
- **Descendente anterior:** La elevación en V1–V4 orienta a la descendente anterior [W2009], y en este trazado miden V1 +0.0 mm · V2 +0.0 mm · V3 +0.0 mm · V4 +0.0 mm. ¿Qué dato apoya tu respuesta?
- **«No se puede distinguir», después de comparar II con III:** Mediste III (+2.9 mm) mayor que II (+2.1 mm), y una elevación mayor en III que en II sugiere coronaria derecha [W2009]. ¿Mantienes que no se puede distinguir?
- **«No se puede distinguir», sin comparar II con III:** Hay un dato que puede orientar: comparar II con III [W2009]. ¿Quieres pedirlo antes de responder?

*Líneas firmadas:* t1:78, t1:81 y t1:82.

**Firma de Luis:** ☐ firmo ☐ corregir ☐ quitar

## 6. Qué se evalúa (además del acierto)

| Competencia | Cómo se decide |
|---|---|
| Reconoce lo que el primer dato no permite decidir | Con elevación en II, III y aVF, la coronaria derecha y la circunfleja son posibles [W2009]. |
| Pide la prueba que distingue las hipótesis | Comparar II con III es lo que orienta entre coronaria derecha y circunfleja [W2009]. |
| Justifica cada prueba que pide | Cada prueba pedida, con el motivo que la sostiene. |
| Evita concluir antes de tener el dato | Una arteria concreta solo se sostiene después de comparar II con III. |
| Actualiza la hipótesis con la nueva evidencia | De «coronaria derecha o circunfleja» a «sugiere coronaria derecha» al ver III mayor que II. |
| Reconoce la información que falta | Sin V3R y V4R no se puede afirmar ni descartar la afectación del ventrículo derecho [W2009]. |

Cada decisión lleva su **confianza** (opcional; 25, 50, 75 o 100 %) y se registra en la sesión con `log_session_answer(..., source="caso_guiado", concept="derivaciones_e_isquemia")`; entra al panel «Tu calibración en esta sesión».

## 7. Decisiones para Luis

| # | Decisión | Opciones |
|---|---|---|
| D1 | ¿Se firma el caso tal como está? | ☐ firmo ☐ con cambios |
| D2 | ¿Se monta la página «Caso guiado de ECG» en Practicar (`caso-guiado`)? | ☐ sí ☐ todavía no |
| D3 | La opción «La coronaria derecha no se relaciona con el ventrículo derecho» es un distractor falso según t1:83. ¿Se mantiene? | ☐ sí ☐ cambiar |
