# Registros reales de referencia (PhysioNet)

## `ptb_s0010.npz`

Ground truth del vectocardiograma de "Crea tu modelo 3D": las derivaciones de
Frank (vx, vy, vz) se grabaron a la vez que las 12 estándar, así que sirven
para comprobar la reconstrucción de Kors.

- **Registro**: PTB Diagnostic ECG Database, s0010_re (mujer, 81 años, infarto
  agudo inferolateral).
- **Qué se guarda**: 20 s de las 12 derivaciones + Frank, remuestreados de 1000
  a 500 Hz y cuantizados a int16 con el paso guardado en `meta.step`.
- **Cita**: Bousseljot R, Kreiseler D, Schnabel A. Nutzung der EKG-
  Signaldatenbank CARDIODAT der PTB über das Internet. *Biomed Tech*
  1995;40(S1):317. doi:10.13026/C28C71. PhysioNet: Goldberger AL, et al.
  *Circulation* 2000;101(23):e215-e220.
- **Licencia**: Open Data Commons Attribution License v1.0 (ODC-By 1.0),
  https://opendatacommons.org/licenses/by/1-0/.
- **Verificado** (auditoría 2026-10-22): II, V2, VX y VZ idénticos al original
  de PhysioNet tras el mismo remuestreo (r = 1.0000).
- Generado con `tools/build_reference_signals.py`.

## `cap_n16.npz` (Tanda 2D, 2026-10-24)

EEG real del mapa sobre la cabeza de "Crea tu modelo 3D".

- **Registro**: CAP Sleep Database, n16 (control sano). 5 derivaciones
  bipolares del lado derecho (Fp2-F4, F4-C4, C4-P4, P4-O2, C4-A1).
- **Qué se guarda**: 30 s (660–690 s del registro) a 100 Hz, int16 con el paso
  en `meta.step`.
- **Cómo se eligió el tramo**: por su contenido de alfa. Es la ventana con la
  mayor potencia alfa relativa en P4-O2 de los primeros 40 min, **no** se eligió
  por el hipnograma. Por eso que la alfa domine en ese tramo es el criterio de
  selección, no un hallazgo.
- **Comprobación aparte**: después de elegir el tramo se cotejó con el
  hipnograma de la base (`n16.txt`, inicio del EDF 22:34:47). 660–690 s cae en una
  época puntuada W (vigilia), y la primera época de sueño empieza a los 870 s.
  Que la persona estuviera relajada o con los ojos cerrados no consta.
- **Cita**: Terzano MG, et al. Atlas, rules, and recording techniques for the
  scoring of cyclic alternating pattern (CAP) in human sleep. *Sleep Med*
  2001;2(6):537-553. PhysioNet: Goldberger AL, et al. *Circulation*
  2000;101(23):e215-e220.
- **Licencia**: ODC-By 1.0.
- **Metadatos corregidos**: el aporte decía "tramo de vigilia tranquila". Se
  reescribieron solo `meta.detail` y `meta.hypnogram_check`; la señal es
  idéntica bit a bit a la del aporte.
