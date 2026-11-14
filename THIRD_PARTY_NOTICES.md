# Avisos de terceros — BIOCORE AI

Este archivo lista lo que BIOCORE usa de terceros: ecuaciones, datos, librerías y métodos publicados, con su licencia y su cita. El código y los datos propios de BIOCORE se rigen por [`LICENSE`](LICENSE); cada componente de terceros conserva la suya.

**Cómo se verificó (2026-11-07).** Los textos de licencia de svZeroDSolver se descargaron de los archivos originales del repositorio y se insertaron sin reescribirlos. Las licencias y citas de PhysioNet se leyeron de las páginas oficiales de cada base. Las licencias de las librerías se leyeron de los metadatos instalados en el entorno de desarrollo (`importlib.metadata`). Lo que no se pudo obtener de su fuente original figura como **PENDIENTE** en la última sección; no se completó con texto aproximado.

---

## 1. svZeroDSolver (ecuaciones del módulo hemodinámico)

- Proyecto: svZeroDSolver, Stanford University / SimVascular Consortium. Repositorio: https://github.com/SimVascular/svZeroDSolver
- Artículo: Menon et al. (2025). svZeroDSolver: A modular package for lumped-parameter cardiovascular simulations. *Journal of Open Source Software*, 10(109), 7595. https://doi.org/10.21105/joss.07595
- Licencia: BSD 3-Clause.

**Qué partes de BIOCORE derivan de él.** `domain/physiology/hemodynamics/r_rcr.py` implementa en Python (`scipy.integrate.solve_ivp`) las ecuaciones del bloque Windkessel RCR y del resistor de Poiseuille, transcritas de la documentación pública del solver (comentarios Doxygen de `src/model/WindkesselBC.h` y `src/model/BloodVessel.cpp`). **No se copió código C++ del solver.** Los módulos que importan `r_rcr.py` (`baroreflex.py`, `physiological_flow.py`, `ups_bridge.py`, `context_comparison.py`) heredan esas ecuaciones. Las extensiones de lazo cerrado y los parámetros fisiológicos son desarrollo propio, con sus propias citas en cada módulo. svZeroDSolver **no es una dependencia** de BIOCORE (no figura en `requirements*.txt`) y BIOCORE no es el solver: es una reimplementación analítica de esas ecuaciones. Detalle de la verificación contra los casos de prueba del solver: `domain/physiology/hemodynamics/THIRD_PARTY_NOTICES.md` y `CHANGELOG.md`.

Texto de la licencia, tal como está en https://raw.githubusercontent.com/SimVascular/svZeroDSolver/master/LICENSE.txt:

```
Copyright 2016-2025 Stanford University, The Regents of the University of California, and others.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS” AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

**Repositorio archivado (solo para verificación).** Para comprobar la reimplementación se ejecutó, aislada y fuera de este repositorio, la versión histórica en Python puro del mismo proyecto (`SimVascular/svZeroDSolver-Archived`). Ninguna línea suya se copió a BIOCORE ni es dependencia. Su licencia es de redacción distinta (estilo MIT). Texto, tal como está en https://raw.githubusercontent.com/SimVascular/svZeroDSolver-Archived/master/LICENSE.md:

```
Copyright (c) Stanford University, The Regents of the University of
              California, and others.

All Rights Reserved.

See Copyright-SimVascular.txt for additional details.

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject
to the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER
OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

Ese texto remite a un archivo `Copyright-SimVascular.txt` del repositorio archivado que no se obtuvo (ver PENDIENTE).

---

## 2. Bases de datos de PhysioNet que se descargan en ejecución (no se distribuyen)

BIOCORE las lee con `wfdb` desde PhysioNet; ningún registro de estas dos bases está dentro del repositorio.

### PTB-XL v1.0.3

- Uso: catálogo de registros del ECG Lab (`clinical/ptbxl_metadata.py`, `app/main.py`) y set de validación del detector de bloqueos de rama (`tests/ptbxl_bbb_validation_set.py`).
- Licencia (según https://physionet.org/content/ptb-xl/1.0.3/): Creative Commons Attribution 4.0 International Public License. Texto: https://physionet.org/content/ptb-xl/view-license/1.0.3/
- Citas que pide la página oficial:
  - Wagner, P., Strodthoff, N., Bousseljot, R., Samek, W., & Schaeffter, T. (2022). PTB-XL, a large publicly available electrocardiography dataset (version 1.0.3). *PhysioNet*. RRID:SCR_007345. https://doi.org/10.13026/kfzx-aw45
  - Wagner, P., Strodthoff, N., Bousseljot, R.-D., Kreiseler, D., Lunze, F.I., Samek, W., Schaeffter, T. (2020), PTB-XL: A Large Publicly Available ECG Dataset. *Scientific Data*. https://doi.org/10.1038/s41597-020-0495-6

### MIT-BIH Arrhythmia Database v1.0.0

- Uso: fuente del ECG Lab y banco de validación del detector de FC/QRS (`docs/validation/ecg_hr_detector_bank/`).
- Licencia (según https://physionet.org/content/mitdb/1.0.0/): Open Data Commons Attribution License v1.0. Texto: https://physionet.org/content/mitdb/view-license/1.0.0/
- Citas que pide la página oficial:
  - Moody, G., & Mark, R. (2005). MIT-BIH Arrhythmia Database (version 1.0.0). *PhysioNet*. RRID:SCR_007345. https://doi.org/10.13026/C2F305
  - Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. IEEE Eng in Med and Biol 20(3):45-50 (May-June 2001). (PMID: 11446209)

### Cita estándar de PhysioNet (la piden las páginas de las cuatro bases de esta sección y la siguiente)

Pollard, T., Moody, B. E., Lehman, L., Gow, B., Fernandes, C., Xie, C., Johnson, A., Mark, R. G., & Heldt, T. (2026). PhysioNet as a global platform for biomedical research. *Nature Health*. https://doi.org/10.1038/s44360-026-00096-z

---

## 3. Datos de terceros incluidos en este repositorio

Procedencia, licencia y cambios, tal como los documentan `data/anatomy3d/README.md`, `data/reference_signals/README.md` y `data/samples/README.md`. Las licencias de PhysioNet de esta sección se contrastaron con sus páginas oficiales.

| Archivo | Origen | Licencia |
|---|---|---|
| `data/anatomy3d/body_ts_s1397.npz`, `data/samples/tc_torax_s1397_2mm.nii.gz` | TotalSegmentator dataset v2.0.1, sujeto s1397. Wasserthal J, et al. *Radiology: Artificial Intelligence* 2023;5(5):e230024. Zenodo, doi:10.5281/zenodo.10047292. Cambios (mallas por marching cubes, decimado y suavizado; recorte y remuestreo de la TC): ver los README de cada carpeta | CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/ |
| `data/anatomy3d/head_mni152.npz` (cabeza) | Superficie fsaverage de FreeSurfer (Fischl et al., *NeuroImage* 1999;9:195-207), tal como la distribuye MNE-Python | FreeSurfer Software License Agreement, texto completo en `data/anatomy3d/LICENSE-FreeSurfer.txt` |
| `data/anatomy3d/head_mni152.npz` (electrodos 10-20) | Posiciones `fsaverage_1020.tsv` de MNE-Python | BSD-3-Clause según `data/anatomy3d/README.md` (texto y copyright: PENDIENTE) |
| `data/anatomy3d/head_mni152.npz` (cerebro) | Plantilla MNI ICBM 152 non-linear symmetric 2009a, incluida en `nilearn`. Fonov VS, et al. *NeuroImage* 2009;47(S1):S102 y *NeuroImage* 2011;54(1):313-327 | Aviso de copyright de la plantilla reproducido en `data/anatomy3d/README.md` (no se re-contrastó con la fuente original en esta fecha) |
| `data/reference_signals/ptb_s0010.npz` | PTB Diagnostic ECG Database v1.0.0, registro s0010_re. Bousseljot R, Kreiseler D, Schnabel A. Nutzung der EKG-Signaldatenbank CARDIODAT der PTB über das Internet. *Biomedizinische Technik*, Band 40, Ergänzungsband 1 (1995) S 317. DOI de la base: 10.13026/C28C71 | Open Data Commons Attribution License v1.0 (según https://physionet.org/content/ptbdb/) |
| `data/reference_signals/cap_n16.npz` | CAP Sleep Database v1.0.0, registro n16. Terzano MG, Parrino L, Sherieri A, Chervin R, Chokroverty S, Guilleminault C, Hirshkowitz M, Mahowald M, Moldofsky H, Rosa A, Thomas R, Walters A. Atlas, rules, and recording techniques for the scoring of cyclic alternating pattern (CAP) in human sleep. *Sleep Med* 2001 Nov; 2(6):537-553. DOI de la base: 10.13026/C2VC79 | Open Data Commons Attribution License v1.0 (según https://physionet.org/content/capslpdb/) |

Los dos registros de PhysioNet de la tabla fueron remuestreados y cuantizados (ver `data/reference_signals/README.md`); son derivados, no los archivos originales.

---

## 4. Librerías de Python (dependencias directas de `requirements.txt`)

Versión y licencia leídas de los metadatos instalados en el entorno de desarrollo el 2026-11-07. La columna «Declarado» es el rango que pide `requirements.txt`. Donde el metadato no trae una licencia corta se muestra el clasificador de PyPI (en esta fecha todas las dependencias tenían una de las dos). Es información de licencia de cada paquete, no una opinión legal sobre su combinación.

| Paquete | Declarado | Versión instalada | Licencia (metadatos) |
|---|---|---|---|
| numpy | `numpy>=1.23.0` | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| scipy | `scipy>=1.10.0` | 1.18.1 | BSD License (clasificador) |
| pandas | `pandas>=1.5.0` | 3.1.0 | BSD-3-Clause |
| wfdb | `wfdb>=4.1.1` | 4.3.1 | MIT License |
| scikit-learn | `scikit-learn>=1.3.0` | 1.9.1 | BSD-3-Clause |
| matplotlib | `matplotlib>=3.7.0` | 3.11.2 | Python Software Foundation License (clasificador) |
| jupyter | `jupyter>=1.0.0` | 1.1.1 | BSD License (clasificador) |
| seaborn | `seaborn>=0.12.0` | 0.13.2 | BSD License (clasificador) |
| plotly | `plotly>=5.10.0` | 7.1.0 | MIT |
| streamlit | `streamlit>=1.25.0` | 1.66.1 | Apache-2.0 |
| pyserial | `pyserial>=3.5.0` | 3.5 | BSD License (clasificador) |
| anthropic | `anthropic>=0.40.0` | 2.3.0 | Apache Software License (clasificador) |
| SQLAlchemy | `sqlalchemy>=2.0.0` | 2.1.6 | MIT |
| fooof | `fooof==1.1.1` | 1.1.1 | Apache Software License (clasificador) |
| shap | `shap>=0.42.0` | 0.54.1 | MIT License (clasificador) |
| lime | `lime>=0.2.0` | 0.2.0.1 | BSD |
| scikit-image | `scikit-image>=0.21.0` | 0.26.0 | BSD License (clasificador) |
| nibabel | `nibabel>=5.0.0` | 5.4.2 | MIT |
| pydicom | `pydicom>=2.4.0` | 3.0.2 | MIT License (clasificador) |
| fast_simplification | `fast-simplification>=0.1.7` | 0.2.0 | MIT |
| fpdf2 | `fpdf2>=2.7.0` | 2.9.0 | LGPL-3.0-only |
| brainflow | `brainflow>=5.24.0` | 5.24.0 | MIT (sin campo de licencia en los metadatos; leída del `LICENSE.txt` del paquete: «MIT License, Copyright (c) 2018 Andrey Parfenov»), 2026-11-14 |
| pylsl | `pylsl>=1.18.6` | 1.18.6 | MIT License (clasificador), 2026-11-14 |
| pytest | `pytest>=7.0.0` | 9.2.0 | MIT |
| pytest-cov | `pytest-cov>=4.1.0` | 7.1.0 | MIT |
| mypy | `mypy>=1.5.0` | 2.4.1 | MIT |
| pylint | `pylint>=2.17.0` | 4.1.3 | GPL-2.0-or-later |
| black | `black>=23.0.0` | 26.10.1 | MIT |
| flake8 | `flake8>=6.0.0` | 7.5.0 | MIT |

Notas:
- `fpdf2` se declara bajo LGPL-3.0 y `pylint` bajo GPL-2.0-or-later. `pylint` figura en la sección «Development tools (optional)» de `requirements.txt`.
- `shap` y `lime` están en `requirements.txt` pero **ningún archivo del repositorio los importa** (verificado 2026-11-07); se listan por transparencia y son candidatos a retirarse de las dependencias.
- `fooof` 1.1.1 implementa el método de Donoghue et al. (sección 5) y es la dependencia que `src/signals/eeg/spectral_model.py` envuelve.
- `brainflow` y `pylsl` (2026-11-14) son las dos fuentes del EEG en vivo (`hardware/eeg_live/`). El paquete `brainflow` trae las bibliotecas nativas de BrainFlow para Windows, Linux y macOS. `pylsl` trae `liblsl`, cuyo repositorio (github.com/sccn/liblsl) dice: «The library and example applications are licensed under the MIT license», y avisa que usa código bajo la Boost Software License. Si alguno de los dos no se instala, el EEG Neuro Lab dice qué falta y lo demás sigue funcionando.
- Los archivos `requirements_extra.txt` y `requirements_arrhythmia.txt` declaran además `kaleido`, `xgboost`, `lightgbm`, `pytz`, `scikit-plot` y `optuna`, que **no están instalados** en este entorno: su licencia no se leyó (PENDIENTE).

---

## 5. Modelos y métodos publicados (se usa el método, no código de terceros)

Referencias tal como las cita el código. Estos métodos se implementaron en BIOCORE; una búsqueda de marcas de copia («copied from», «adapted from», «ported from», «transcrito de») en los `*.py` solo encontró portes internos entre módulos propios, y no se identificó código de terceros copiado. Es una búsqueda por texto, no una auditoría de similitud de código.

| Método | Referencia | Dónde se usa |
|---|---|---|
| Generador dinámico de ECG sintético | McSharry et al. 2003, *IEEE Transactions on Biomedical Engineering*, «A dynamical model for generating synthetic electrocardiogram signals» | `src/signals/ecg/dynamic_ecg_generator.py` |
| Reconstrucción del vectocardiograma de Frank | Kors JA, van Herpen G, Sittig AC, van Bemmel JH. Reconstruction of the Frank vectorcardiogram from standard electrocardiographic leads: diagnostic comparison of different methods. *Eur Heart J*. 1990;11(12):1083-1092 | `src/signals/ecg/vcg.py` |
| Splines esféricos para el mapa EEG | Perrin F, Pernier J, Bertrand O, Echallier JF. *Electroencephalogr Clin Neurophysiol* 1989;72:184-187 | `visualization/anatomy3d.py` |
| Parametrización espectral (componente aperiódico) | Donoghue et al. 2020, *Nature Neuroscience*, «Parameterizing neural power spectra into periodic and aperiodic components» (vía la librería `fooof`) | `src/signals/eeg/spectral_model.py` |
| Variabilidad de la FC, bandas y RSA | Task Force of the ESC and NASPE (1996). Heart rate variability: standards of measurement, physiological interpretation and clinical use. *Circulation* 93(5):1043-1065 | `src/signals/ecg/rsa.py`, `app/supermodules/biomarkers.py` |
| Entropía muestral (SampEn) | Richman JS, Moorman JR (2000). Physiological time-series analysis using approximate entropy and sample entropy. *Am J Physiol Heart Circ Physiol* 278(6):H2039-H2049 | `src/signals/ecg/hrv_nonlinear.py` |
| DFA (alfa1) | Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. *Chaos* 5(1):82-87 | `src/signals/ecg/hrv_nonlinear.py` |
| Gráfico de Poincaré | Brennan M, Palaniswami M, Kamen P (2001). Do existing measures of Poincare plot geometry reflect nonlinear features of heart rate variability? *IEEE Trans Biomed Eng* 48(11):1342-1347 | `src/signals/ecg/hrv_nonlinear.py` |
| Detector de QRS por operador de energía Teager-Kaiser | Técnica estándar mencionada en el código sin referencia bibliográfica (ver PENDIENTE) | `clinical/ecg_analyzer.py` |
| Ganancia de la placa ECG (1100, supuesto para estimar mV) | Analog Devices. AD8232 Data Sheet, Rev. D (3/2020, D10866-3/20(D)): configuración de monitor cardiaco, Figura 66 (op amp con ganancia 11, ganancia total del sistema 1100; pasa-altas de dos polos a 0.5 Hz y pasa-bajas de dos polos a 40 Hz). Leída del PDF del fabricante el 2026-11-13 | `hardware/ecg_plugplay/config.py` (`AD8232_GAIN_SOURCE`), `hardware/ecg_plugplay/firmware/main.py` |
| Por qué la banda de 0.5–40 Hz no sirve para el ST | Kligfield P, Gettes LS, Bailey JJ, et al. Recommendations for the Standardization and Interpretation of the Electrocardiogram: Part I: The Electrocardiogram and Its Technology. *Circulation*. 2007;115:1306-1324. doi:10.1161/CIRCULATIONAHA.106.180200. Leída del texto completo el 2026-11-13 | `hardware/ecg_plugplay/preprocessing.py` (`FILTER_LIMITS_SOURCE`), `app/supermodules/ecg_live/tutorial.py` |
| Montaje 10-20 y 10-10 sobre una cabeza esférica (diagrama del tutorial de EEG en vivo) | Kane N, Acharya J, Beniczky S, et al. A revised glossary of terms most commonly used by clinical electroencephalographers... Revision 2017. *Clin Neurophysiol Pract* 2017;2:170-185 (sistemas 10-20 y 10-10); Seeck M, Koessler L, Bast T, et al. The standardized EEG electrode array of the IFCN. *Clin Neurophysiol* 2017;128:2070-2077 (porcentajes de nasion a inion y nombres de los electrodos). Leídas el 2026-11-14 | `hardware/eeg_live/montage.py`, `app/supermodules/eeg_neuro_lab/live_tutorial.py` |
| Simulador de práctica de EEG (alfa posterior reactivo, parpadeo, electrodo flojo) | Kane 2017 (definición del ritmo alfa); Tatum WO, Dworetzky BA, Schomer DL. Artifact and recording concepts in EEG. *J Clin Neurophysiol* 2011;28(3):252-263 (origen del artefacto ocular, artefacto de un solo canal, ruido de red); el pulso del parpadeo es el de `EegSignalGenerator`. Leídas el 2026-11-14 | `hardware/eeg_live/simulator.py`, `hardware/eeg_live/quality.py` |

Las fórmulas y escalas clínicas de `clinical/calculators.py` llevan su propia cita en la constante `*_CITATION` de cada una; no se repiten aquí.

Las preguntas de los cuestionarios (`educational/quiz_bank.py`) llevan su fuente en el campo `source` de cada una, leída del documento original el 2026-11-14; no se repiten aquí.

Las referencias clínicas del EEG (`clinical/eeg_references.py`: Kane 2017, Seeck 2017 y Tatum 2011) las comparten el banco de preguntas, el EEG en vivo y su tutorial; no se repiten aquí. Las referencias clínicas del ECG (`clinical/ecg_references.py`) las comparten el banco de preguntas y el analizador de 12 derivaciones (`src/signals/ecg/twelve_lead_measure.py`), con la misma fecha de lectura; no se repiten aquí.

---

## 6. PENDIENTE (no se pudo obtener de su fuente original)

1. **Archivo `Copyright-SimVascular.txt`** del repositorio `svZeroDSolver-Archived`, al que remite su `LICENSE.md`. No se descargó.
2. **BSD-3-Clause y copyright de MNE-Python** (`fsaverage_1020.tsv`, posiciones de electrodos de `head_mni152.npz`): no se tiene el texto original.
3. **Aviso de copyright de la plantilla MNI ICBM 152**: se conserva el que ya estaba en `data/anatomy3d/README.md`, sin re-contrastarlo con la fuente original (`nilearn`/MNI).
4. **Licencias de `kaleido`, `xgboost`, `lightgbm`, `pytz`, `scikit-plot` y `optuna`**: paquetes de los `requirements_*.txt` secundarios, no instalados en este entorno.
5. **Referencia bibliográfica del detector Teager-Kaiser** (sección 5): el código no la trae.
6. **Cita completa de McSharry et al. 2003** (autores, volumen y páginas): el código solo da «McSharry et al. 2003», la revista y el título.
