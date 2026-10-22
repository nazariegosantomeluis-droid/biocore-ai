# Herramientas: regenerar la anatomía 3D y los registros reales

Nada de esto corre dentro de la app. La app solo lee los resultados compactos
que ya están en el repositorio:

| Resultado (en el repo) | Lo genera | A partir de |
|---|---|---|
| `data/anatomy3d/body_ts_s1397.npz` (38 superficies + V1–V6) | `build_anatomy3d.py body` y `landmarks` | Tomografía real del TotalSegmentator, sujeto s1397 |
| `data/anatomy3d/head_mni152.npz` (cabeza, cerebro, 21 electrodos) | `build_anatomy3d.py head` | fsaverage (FreeSurfer, vía MNE) y MNI152 2009a (vía nilearn) |
| `data/reference_signals/*.npz` (5 registros) | `build_reference_signals.py` | PhysioNet (MIT-BIH, PTB, CAP, Challenge 2015, MIMIC) |
| `data/samples/tc_torax_s1397_2mm.nii.gz` | `build_samples.py` | La misma tomografía del TotalSegmentator |
| `app/static/anatomy/*.webp` + `manifest.json` | `render_anatomy/` (three.js) | Las mallas de `data/anatomy3d/` |

Las fuentes, licencias y citas de cada archivo están en el `README.md` de su
carpeta y, además, dentro de cada `.npz` (clave `meta`), de donde las lee la
interfaz.

## 1. Datos de partida (se descargan a mano; ningún script descarga nada)

- **TotalSegmentator dataset v2.0.1** — Zenodo, doi:10.5281/zenodo.10047292
  (CC BY 4.0). Hace falta la carpeta del sujeto `s1397`, con `ct.nii.gz` y
  `segmentations/*.nii.gz`.
- **MNI ICBM 152 2009a** — los archivos
  `mni_icbm152_gm_tal_nlin_sym_09a_converted.nii.gz` y
  `mni_icbm152_wm_tal_nlin_sym_09a_converted.nii.gz` que vienen dentro del
  paquete `nilearn` (`nilearn/datasets/data/`).
- **fsaverage y 10-20** — vienen dentro del paquete `mne`:
  `mne/data/fsaverage/fsaverage-head.fif` y
  `mne/channels/data/montages/fsaverage_1020.tsv`.
- **PhysioNet** — los registros `100`, `s0010_re`, `n16`, `a103l` y
  `03700181` (los mismos de la carpeta `sample-data` de `wfdb-python`).

Los archivos descargados son datos: guárdalos en una carpeta aparte y pasa
su ruta como argumento.

## 2. Mallas y registros

```bash
pip install -r requirements.txt -r requirements-dev.txt   # nibabel, scikit-image, fast-simplification, mne

python tools/build_anatomy3d.py body --ts-dir RUTA/s1397 --out data/anatomy3d/body_ts_s1397.npz
python tools/build_anatomy3d.py landmarks --ts-dir RUTA/s1397 --npz data/anatomy3d/body_ts_s1397.npz
python tools/build_anatomy3d.py head --mni-dir RUTA/mni \
    --montage RUTA/fsaverage_1020.tsv --head-fif RUTA/fsaverage-head.fif \
    --out data/anatomy3d/head_mni152.npz

python tools/build_reference_signals.py --raw RUTA/physionet --out data/reference_signals
python tools/build_samples.py --ts-dir RUTA/s1397 --out data/samples
```

`body` tarda unos minutos (marching cubes sobre 117 segmentaciones). Las
posiciones V1–V6 se calculan sobre esa misma tomografía contando los
cartílagos costales en el borde esternal (4.º y 5.º espacio intercostal) y la
línea medioclavicular; los detalles están en `precordial_landmarks()`.

## 3. Renders de la anatomía (Atlas, tarjetas de órganos)

Necesita Node.js (para `three`) y Playwright con Chromium.

```bash
cd tools/render_anatomy
npm install                        # three 0.186.1
python export_meshes.py ../../data/anatomy3d/body_ts_s1397.npz meshes/body
python export_meshes.py ../../data/anatomy3d/head_mni152.npz meshes/head
python make_specs.py               # cámaras, materiales y anclas de cada imagen
python drive.py organ_heart organ_lungs organ_brain organ_muscles organ_autonomic \
    atlas_body atlas_precordial atlas_1020_top atlas_1020_left atlas_heart
python publish.py                  # -> app/static/anatomy/*.webp + manifest.json
```

`drive.py` dibuja cada escena con WebGL por software (SwiftShader), a doble
resolución, y guarda la posición en píxeles de cada punto marcado (electrodos,
V1–V6, nodos de conducción). La app dibuja encima los rótulos en SVG, así el
texto queda nítido, accesible y en español. `node_modules/`, `meshes/`,
`specs/` y `out/` son intermedios y no se suben al repositorio.

## 4. Comprobar

```bash
python -m pytest tests/test_real_data_3d_2026_10_21.py tests/test_illustrations.py -q
```
