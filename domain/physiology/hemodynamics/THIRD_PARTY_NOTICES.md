# Atribución de terceros — módulo hemodinámico R-RCR

Este subpaquete (`domain/physiology/hemodynamics/`) implementa ecuaciones
publicadas por el proyecto **svZeroDSolver** (Stanford University /
SimVascular Consortium). No se copió código fuente C++ del proyecto
original — las ecuaciones se transcribieron desde su documentación pública
(comentarios Doxygen de `src/model/WindkesselBC.h` y `src/model/BloodVessel.cpp`)
y se reimplementaron en Python (`scipy.integrate.solve_ivp`), verificadas
contra los casos de prueba oficiales del propio proyecto (ver
`r_rcr.py` y `CHANGELOG.md` para el detalle de la verificación).

## svZeroDSolver (repositorio actual, C++/Python)

- Repositorio: https://github.com/SimVascular/svZeroDSolver
- Paper: Menon et al., (2025). svZeroDSolver: A modular package for
  lumped-parameter cardiovascular simulations. *Journal of Open Source
  Software*, 10(109), 7595. https://doi.org/10.21105/joss.07595
- Licencia: **BSD 3-Clause**

```
Copyright 2016-2025 Stanford University, The Regents of the University of California, and others.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

Fuente exacta del texto: https://github.com/SimVascular/svZeroDSolver/blob/master/LICENSE.txt

## Nota de transparencia — desviación respecto a lo pedido, marcada explícitamente

Se pidió "instala/integra svZeroDSolver (BSD-3-Clause)". El repositorio
actual está escrito en C++ con bindings de Python (pybind11) y requiere
compilar desde el código fuente (CMake + toolchain C++) — **no existe
paquete en PyPI**, y este entorno de desarrollo **no tiene compilador de
C++, CMake ni Visual Studio instalados** (confirmado explícitamente antes
de intentar cualquier otra cosa). Compilar el solver real no fue posible
aquí.

En su lugar, para la **verificación** (no para el módulo de producción en
sí) se instaló y ejecutó genuinamente `svzerodsolver` — la implementación
histórica en Python puro del **mismo proyecto/organización**
(`SimVascular/svZeroDSolver-Archived`, predecesora directa de la versión
C++ actual, mismos casos de prueba, misma física) — contra los casos de
prueba JSON oficiales reales, confirmando que reproduce la solución
analítica publicada. Esa corrida real fue la base para verificar también
mi propia reimplementación (ver `r_rcr.py`).

Ese repositorio archivado usa una licencia de texto distinto (estilo MIT,
también permisiva y comercialmente utilizable, pero no idéntica en su
redacción a "BSD-3-Clause"):

```
Copyright (c) Stanford University, The Regents of the University of
California, and others. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject
to the following conditions: [...]
```

Fuente: https://github.com/SimVascular/svZeroDSolver-Archived/blob/master/LICENSE.md

**Ninguna línea de ese paquete archivado se copió al proyecto** — se usó
únicamente, de forma aislada (`pip install --target` en un directorio
fuera del repositorio), para generar datos de verificación durante esta
tanda. No es una dependencia de `requirements.txt` ni del módulo de
producción (`r_rcr.py`), que solo depende de `numpy`/`scipy`, ya
dependencias existentes del proyecto.
