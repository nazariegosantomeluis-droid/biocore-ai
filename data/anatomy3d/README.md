# Anatomía 3D de referencia

Mallas de una persona real y de una plantilla promedio. En la app se usan como
**anatomía de referencia, no reactiva**: sirven para ubicar y enseñar, no
representan al paciente ni cambian con el estado del gemelo. Las lee
`visualization/anatomy3d.py` y se generan con `tools/build_anatomy3d.py`.

## `body_ts_s1397.npz`

- **Qué es**: 38 superficies de una tomografía real de cuerpo completo, con su
  volumen medido sobre la segmentación. El visor solo muestra los sistemas de
  órganos (corazón y vasos, pulmones y tráquea, encéfalo y médula, abdomen);
  esqueleto, músculos y piel siguen en el archivo pero no se muestran.
- **También sirve de referencia** para validar el preset de pulmón de "Crea tu
  modelo 3D" (`tests/test_reconstruction3d_validation.py`), porque la TC de
  ejemplo es del mismo sujeto. Es una segmentación automática publicada, no un
  trazado manual de un experto.
- **Fuente**: TotalSegmentator dataset v2.0.1, sujeto s1397 — Jakob
  Wasserthal (University Hospital Basel). Zenodo, doi:10.5281/zenodo.10047292.
- **Artículo**: Wasserthal J, et al. TotalSegmentator: Robust Segmentation of
  104 Anatomic Structures in CT Images. *Radiology: Artificial Intelligence*
  2023;5(5):e230024. doi:10.1148/ryai.230024.
- **Licencia**: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
- **Cambios**: superficies obtenidas con marching cubes sobre las máscaras
  suavizadas, decimadas y suavizadas (Taubin); coordenadas cuantizadas a
  0.05 mm, relativas a `meta["origin_mm"]`. La tomografía original viene con
  la cara anonimizada.
- El `meta` trae además posiciones V1–V6 y centroides vertebrales que la app
  **no usa**: no se auditaron.

## `head_mni152.npz`

- **Cabeza**: superficie del cuero cabelludo de fsaverage (FreeSurfer; Fischl
  et al., *NeuroImage* 1999;9:195-207), tal como la distribuye MNE-Python.
  Subdividida (Loop) a dos resoluciones. Licencia: FreeSurfer Software License
  Agreement, en `LICENSE-FreeSurfer.txt`.
- **Electrodos 10-20**: posiciones estándar de MNE-Python
  (`fsaverage_1020.tsv`, BSD-3-Clause), proyectadas sobre esa cabeza. Se
  muestran como referencia; no se dibuja ningún EEG sobre ellas.
- **Cerebro**: plantilla MNI ICBM 152 non-linear symmetric 2009a, la versión
  incluida en `nilearn`. Fonov VS, et al. *NeuroImage* 2009;47(S1):S102 y
  *NeuroImage* 2011;54(1):313-327.

Aviso de la plantilla MNI (se reproduce como pide su licencia):

> Copyright (C) 1993-2009 Louis Collins, McConnell Brain Imaging Centre,
> Montreal Neurological Institute, McGill University. Permission to use, copy,
> modify, and distribute this software and its documentation for any purpose
> and without fee is hereby granted, provided that the above copyright notice
> appear in all copies. The authors and McGill University make no
> representations about the suitability of this software for any purpose. It
> is provided "as is" without express or implied warranty.

## Formato

`npz` sin pickle: por cada estructura `k`, `k__v` (vértices int16 en unidades
de 0.05 mm relativas a `origin_mm`) y `k__f` (triángulos uint16), más `meta`
(JSON con etiquetas, sistema, volumen y la atribución completa).
