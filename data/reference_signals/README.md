# Registros reales de referencia (PhysioNet)

Tramos cortos de registros reales que reemplazan a los trazos dibujados: las
tiras de los encabezados, las láminas del Atlas (complejo ECG, tacograma,
bandas EEG) y el vectocardiograma de referencia. Se generan con
`tools/build_reference_signals.py` y se leen con
`src/signals/reference_recordings.py`.

Todos tienen licencia **Open Data Commons Attribution License v1.0
(ODC-By 1.0)** — https://opendatacommons.org/licenses/by/1-0/. Cita general
de PhysioNet: Pollard T, Moody BE, Lehman L, et al. PhysioNet as a global
platform for biomedical research. *Nature Health* 2026.
doi:10.1038/s44360-026-00096-z (la cita clásica era Goldberger AL, et al.
*Circulation* 2000;101(23):e215-e220).

| Archivo | Registro | Qué se guarda | Cita |
|---|---|---|---|
| `mitdb_100.npz` | MIT-BIH Arrhythmia Database, registro 100 (hombre, 69 años) | 5 min de MLII a 360 Hz + anotaciones de latido de los 30 min | Moody GB, Mark RG. *IEEE Eng Med Biol* 2001;20(3):45-50. doi:10.13026/C2F305 |
| `ptb_s0010.npz` | PTB Diagnostic ECG Database, s0010_re (mujer, 81 años, infarto agudo inferolateral) | 20 s de las 12 derivaciones + Frank (vx, vy, vz), remuestreado de 1000 a 500 Hz | Bousseljot R, et al. *Biomed Tech* 1995;40(S1):317. doi:10.13026/C28C71 |
| `cap_n16.npz` | CAP Sleep Database, n16 (control sano) | 30 s de EEG bipolar a 100 Hz, el tramo de vigilia con más alfa en P4-O2 | Terzano MG, et al. *Sleep Med* 2001;2(6):537-553 |
| `challenge2015_a103l.npz` | PhysioNet/CinC Challenge 2015, a103l | 30 s de pletismografía y ECG II a 250 Hz | Clifford GD, et al. *Comput Cardiol* 2015;42:273-276 |
| `mimic_037.npz` | MIMIC Database, 037 (segmento 03700181) | 120 s de ECG MCL1, presión arterial invasiva y respiración por impedancia | Moody GB, Mark RG. *Comput Cardiol* 1996;23:657-660 |

**Cambios**: recorte a los tramos indicados, cuantización a int16 con el paso
guardado en `meta.step` y, en el PTB, remuestreo a 500 Hz. Cada `npz` lleva en
`meta` el título, el detalle, la cita y la licencia, que la interfaz muestra
junto al trazo.
