# Datos de ejemplo de "Crea tu modelo 3D"

## `tc_torax_s1397_2mm.nii.gz`

Tórax de una tomografía real, para probar la reconstrucción 3D sin tener un
estudio propio a mano (botón "Usar el ejemplo: TC real de tórax").

- **Fuente**: TotalSegmentator dataset v2.0.1, sujeto s1397 — Wasserthal J,
  et al. *Radiology: Artificial Intelligence* 2023;5(5):e230024. Zenodo,
  doi:10.5281/zenodo.10047292.
- **Licencia**: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
- **Cambios**: recortado al tórax (de 3 cm por debajo de las bases
  pulmonares hasta justo antes del cráneo, sin la camilla), remuestreado de
  1.5 a 2 mm (trilineal con un prefiltro gaussiano suave; 204 × 184 × 151
  vóxeles) y valores en unidades Hounsfield redondeados a pasos de 4 HU.
- Generado con `tools/build_samples.py` (ver `tools/README.md`).

La tomografía original viene anonimizada por sus autores.
