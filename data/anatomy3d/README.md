# Anatomía 3D real

Superficies 3D que usan el cuerpo interactivo del Digital Twin OS, el Atlas
de Academia, el mapa EEG sobre la cabeza y los renders de `app/static/anatomy/`.
Se generan con `tools/build_anatomy3d.py` (ver `tools/README.md`).

## `body_ts_s1397.npz`

- **Qué es**: 38 superficies de una tomografía real de cuerpo completo
  (esqueleto, corazón con raíz de la aorta y cavas, arterias, venas, venas
  pulmonares, pulmones, tráquea, encéfalo, médula espinal, músculos, órganos
  abdominales y piel), con su volumen medido sobre la segmentación, más las
  posiciones V1–V6 calculadas sobre esa misma tomografía y los centroides
  vertebrales.
- **Fuente**: TotalSegmentator dataset v2.0.1, sujeto s1397 — Jakob
  Wasserthal (University Hospital Basel). Zenodo, doi:10.5281/zenodo.10047292.
- **Artículo**: Wasserthal J, et al. TotalSegmentator: Robust Segmentation of
  104 Anatomic Structures in CT Images. *Radiology: Artificial Intelligence*
  2023;5(5):e230024. doi:10.1148/ryai.230024.
- **Licencia**: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
- **Cambios**: superficies obtenidas con marching cubes sobre las máscaras
  suavizadas, decimadas y suavizadas (Taubin); piel a 3 mm sin la camilla;
  coordenadas cuantizadas a 0.05 mm. La tomografía original viene con la cara
  anonimizada (defaced).

## `head_mni152.npz`

- **Cabeza**: superficie del cuero cabelludo de fsaverage (FreeSurfer; Fischl
  et al., *NeuroImage* 1999;9:195-207), tal como la distribuye MNE-Python en
  `mne/data/fsaverage/fsaverage-head.fif`. Modificada: subdividida (Loop) a dos
  resoluciones. Licencia: FreeSurfer Software License Agreement, incluida en
  `LICENSE-FreeSurfer.txt`.
- **Electrodos 10-20**: posiciones estándar de MNE-Python
  (`fsaverage_1020.tsv`, BSD-3-Clause), calculadas por MNE sobre esa misma
  cabeza y proyectadas sobre la superficie subdividida.
- **Cerebro**: plantilla MNI ICBM 152 non-linear symmetric 2009a (sustancia
  gris + blanca), la versión incluida en `nilearn`. Fonov VS, et al.
  *NeuroImage* 2009;47(S1):S102 y *NeuroImage* 2011;54(1):313-327.

Aviso de la plantilla MNI (se reproduce como pide su licencia):

> Copyright (C) 1993-2009 Louis Collins, McConnell Brain Imaging Centre,
> Montreal Neurological Institute, McGill University. Permission to use, copy,
> modify, and distribute this software and its documentation for any purpose
> and without fee is hereby granted, provided that the above copyright notice
> appear in all copies. The authors and McGill University make no
> representations about the suitability of this software for any purpose. It
> is provided "as is" without express or implied warranty.

## Formato

`npz` sin pickle: por cada estructura `k`, `k__v` (vértices int16 en
unidades de 0.05 mm relativas a `origin_mm`) y `k__f` (triángulos uint16),
más `meta` (JSON con etiquetas, sistema, volumen y la atribución completa).
Se leen con `visualization/anatomy3d.py` (`load_body()`, `load_head()`).

Son la anatomía de una persona y de una plantilla promedio: sirven para
ubicar y enseñar, no representan al paciente que se está estudiando.
