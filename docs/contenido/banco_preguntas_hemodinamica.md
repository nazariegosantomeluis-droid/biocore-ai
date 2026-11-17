# Banco de preguntas para BIOCORE: Hemodinámica (FIRMADO)

**Estado:** FIRMADO 2026-11-17 por Luis Nazariego Santome («firmo todo, pero que salga de referencias verídicas»): G1–G10. Están en la app, en `educational/quiz_bank.py` como `HEMO_QUESTIONS` (lección «Hemodinámica» del Quiz de la Academia, banco `hemodinamica`, concepto `hemodinamica`).
**Regla:** cada pregunta se sostiene en una línea firmada de `docs/contenido/teoria_citada_3.md`, citada textual como «t3:N»; ese documento solo dice lo que dicen los resúmenes publicados de sus fuentes. La correcta va primero (en pantalla se reparte su lugar) y en ninguna pregunta es la opción más larga. `tests/test_banco_hemodinamica.py` vigila todo esto.

---

**G1 · ¿Qué es la presión arterial media (PAM)?**
¿Qué es la presión arterial media (PAM)?
- ✅ La presión arterial promedio a lo largo de un ciclo cardiaco, en sístole y en diástole
- La presión máxima que alcanza la arteria en cada sístole del ventrículo izquierdo, medida en el brazo
- La diferencia entre la presión sistólica y la diastólica de cada latido, también llamada pulso arterial
- La presión que queda en las venas al final de cada diástole, justo antes de la siguiente contracción

*Explicación:* la presión arterial media es la presión arterial promedio a lo largo de un ciclo cardiaco, en sístole y en diástole [DW2019].
*Línea firmada:* t3:11 — «**Idea.** La presión arterial media es la presión arterial promedio a lo largo de un ciclo cardiaco, en sístole y en diástole [DW2019].»

**G2 · ¿Con qué fórmula empírica se estima la PAM a partir de la presión arterial?**
¿Con qué fórmula empírica se estima la PAM a partir de la presión arterial?
- ✅ Diastólica + 1/3 de la presión de pulso
- (Sistólica + diastólica) / 2, el promedio aritmético simple de las dos cifras
- Sistólica − diastólica, que es la presión de pulso de ese mismo latido
- Sistólica + 1/3 de la presión de pulso, para corregir la sobrestimación del brazalete

*Explicación:* durante muchos años se ha usado una fórmula empírica: la PAM queda a un tercio de la distancia entre la presión diastólica y la sistólica, es decir, diastólica + 1/3 de la presión de pulso [ME2000].
*Línea firmada:* t3:19 — «- Durante muchos años se ha usado una fórmula empírica: la PAM queda a un tercio de la distancia entre la presión diastólica y la sistólica, es decir, diastólica + 1/3 de la presión de pulso [ME2000].»

**G3 · Con una presión de 110/80 mmHg, ¿cuánto da la estimación diastólica + 1/3 de la presión de pulso?**
Con una presión de 110/80 mmHg, ¿cuánto da la estimación diastólica + 1/3 de la presión de pulso?
- ✅ 90 mmHg
- 95 mmHg
- 100 mmHg
- 85 mmHg

*Explicación:* durante muchos años se ha usado una fórmula empírica: la PAM queda a un tercio de la distancia entre la presión diastólica y la sistólica, es decir, diastólica + 1/3 de la presión de pulso [ME2000].
*Línea firmada:* t3:19 — «- Durante muchos años se ha usado una fórmula empírica: la PAM queda a un tercio de la distancia entre la presión diastólica y la sistólica, es decir, diastólica + 1/3 de la presión de pulso [ME2000].»

**G4 · ¿Qué es el gasto cardiaco?**
¿Qué es el gasto cardiaco?
- ✅ La frecuencia cardiaca por el volumen sistólico
- El volumen sistólico dividido entre la frecuencia cardiaca de ese minuto
- La presión arterial media multiplicada por la resistencia vascular sistémica
- La suma de la frecuencia cardiaca y del volumen sistólico de cada latido

*Explicación:* el gasto cardiaco es el producto de la frecuencia cardiaca por el volumen sistólico [DW2019].
*Línea firmada:* t3:27 — «**Idea.** El gasto cardiaco es el producto de la frecuencia cardiaca por el volumen sistólico [DW2019].»

**G5 · Con una frecuencia de 70 lpm y un volumen sistólico de 70 mL, ¿cuál es el gasto cardiaco?**
Con una frecuencia de 70 lpm y un volumen sistólico de 70 mL, ¿cuál es el gasto cardiaco?
- ✅ 4.9 L/min
- 140 mL/min
- 0.49 L/min
- 49 L/min

*Explicación:* el gasto cardiaco es el producto de la frecuencia cardiaca por el volumen sistólico [DW2019].
*Línea firmada:* t3:27 — «**Idea.** El gasto cardiaco es el producto de la frecuencia cardiaca por el volumen sistólico [DW2019].»

**G6 · Si aumenta la poscarga, ¿qué le pasa al volumen sistólico?**
Si aumenta la poscarga, ¿qué le pasa al volumen sistólico?
- ✅ Disminuye
- Aumenta, porque el ventrículo se contrae con más fuerza contra la resistencia
- No cambia, porque solo depende de la frecuencia cardiaca
- Aumenta, porque la poscarga es lo mismo que la precarga

*Explicación:* un aumento de la poscarga disminuye el volumen sistólico [DW2019].
*Línea firmada:* t3:32 — «- Un aumento de la poscarga disminuye el volumen sistólico [DW2019].»

**G7 · Si aumenta el volumen de sangre, ¿qué pasa?**
Si aumenta el volumen de sangre, ¿qué pasa?
- ✅ Aumentan la precarga, el volumen sistólico y el gasto cardiaco
- Disminuye la precarga y, con ella, bajan el volumen sistólico y el gasto cardiaco del ventrículo
- Aumenta la poscarga y baja el volumen sistólico, aunque el gasto cardiaco se mantiene igual
- No cambia la precarga, porque las venas distensibles absorben todo el volumen que se añade

*Explicación:* aumentar el volumen de sangre aumenta la precarga, el volumen sistólico y, por lo tanto, el gasto cardiaco [DW2019].
*Línea firmada:* t3:31 — «- La precarga depende del volumen de sangre y de la distensibilidad de las venas: aumentar el volumen de sangre aumenta la precarga, el volumen sistólico y, por lo tanto, el gasto cardiaco [DW2019].»

**G8 · ¿Qué le pasa a la resistencia vascular sistémica si disminuye el radio de los vasos?**
¿Qué le pasa a la resistencia vascular sistémica si disminuye el radio de los vasos?
- ✅ Aumenta
- Disminuye, porque la sangre pasa más rápido por un vaso más angosto
- No cambia: la resistencia solo depende de la viscosidad de la sangre
- Disminuye primero y luego aumenta, según la presión arterial media

*Explicación:* la resistencia vascular sistémica depende sobre todo del radio de los vasos: disminuir el radio aumenta la resistencia [DW2019].
*Línea firmada:* t3:44 — «- La resistencia vascular sistémica depende sobre todo del radio de los vasos: disminuir el radio aumenta la resistencia [DW2019].»

**G9 · Según la analogía con la ley de Ohm, ¿de dónde puede venir un aumento de la PAM?**
Según la analogía con la ley de Ohm, ¿de dónde puede venir un aumento de la PAM?
- ✅ De más gasto cardiaco, más resistencia periférica o ambos
- Solo de una frecuencia cardiaca más alta, aunque el gasto cardiaco y la resistencia no cambien
- Solo de una menor resistencia periférica, que deja pasar más sangre a las arterias del cuerpo
- De la viscosidad de la sangre, que es lo que más determina la resistencia de los vasos

*Explicación:* un aumento de la PAM solo puede venir de un aumento del gasto cardiaco, de la resistencia periférica, o de ambos [MY2003].
*Línea firmada:* t3:41 — «**Idea.** La relación entre presión y flujo en la circulación es análoga a la ley de Ohm: un aumento de la PAM solo puede venir de un aumento del gasto cardiaco, de la resistencia periférica, o de ambos [MY2003].»

**G10 · ¿Qué describe la ley de Frank–Starling?**
¿Qué describe la ley de Frank–Starling?
- ✅ Que el corazón ajusta la eyección al llenado ventricular
- Que la frecuencia cardiaca sube cada vez que baja la presión arterial media del cuerpo
- Que la fuerza de contracción del ventrículo no depende de cuánto se llenó antes de contraerse
- Que el volumen sistólico cae cuando aumenta el llenado del ventrículo antes de la sístole

*Explicación:* el corazón ajusta la eyección a los cambios del llenado ventricular [SQ2015].
*Línea firmada:* t3:35 — «- Ley de Frank–Starling: el corazón ajusta la eyección a los cambios del llenado ventricular [SQ2015].»

**Cálculos comprobados:** G3, 110/80 mmHg → presión de pulso 30 → 80 + 30/3 = 90 mmHg. G5, 70 lpm × 70 mL = 4 900 mL/min = 4.9 L/min.

## Hoja de firma

> Firmo todo, pero que salga de referencias verídicas. — Luis Nazariego Santome, 17/11/2026

| ID | Línea | Decisión de Luis |
|---|---|---|
| G1 | t3:11 | ☑ firmado (17-11-2026) |
| G2 | t3:19 | ☑ firmado (17-11-2026) |
| G3 | t3:19 | ☑ firmado (17-11-2026) |
| G4 | t3:27 | ☑ firmado (17-11-2026) |
| G5 | t3:27 | ☑ firmado (17-11-2026) |
| G6 | t3:32 | ☑ firmado (17-11-2026) |
| G7 | t3:31 | ☑ firmado (17-11-2026) |
| G8 | t3:44 | ☑ firmado (17-11-2026) |
| G9 | t3:41 | ☑ firmado (17-11-2026) |
| G10 | t3:35 | ☑ firmado (17-11-2026) |
