# Generadores de datos (fuera de la app)

Scripts que producen los datos de `data/` a partir de las fuentes públicas
originales, para que se puedan reproducir. La app nunca los importa.
Traídos del aporte externo auditado (2026-10-22) junto con los datos que usa
"Crea tu modelo 3D".

| Script | Genera | Necesita |
|---|---|---|
| `build_anatomy3d.py` | `data/anatomy3d/*.npz` (mallas TotalSegmentator s1397, cabeza fsaverage + cerebro MNI152 + electrodos 10-20) | `nibabel`, `scikit-image`, `fast-simplification`, `mne`, `nilearn` y los datos fuente descargados |
| `build_samples.py` | `data/samples/tc_torax_s1397_2mm.nii.gz` (TC de ejemplo) | `nibabel`, `scipy` |
| `build_reference_signals.py` | `data/reference_signals/*.npz` | `wfdb` y los registros de PhysioNet |

`build_reference_signals.py` sabe extraer cinco registros, pero el repo solo
trae y usa `ptb_s0010.npz` (ground truth del vectocardiograma). Las fuentes,
citas y licencias de cada archivo están en el `README.md` de su carpeta.
