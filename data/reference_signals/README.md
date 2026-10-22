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
