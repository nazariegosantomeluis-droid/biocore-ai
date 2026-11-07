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

El texto exacto de esta licencia, descargado del archivo original del repositorio,
vive en el `THIRD_PARTY_NOTICES.md` de la raíz del proyecto (sección 1). Se dejó de
copiar aquí porque la copia anterior no era exacta (comillas rectas en lugar de las
curvas del original) y dos copias pueden divergir.

Fuente: https://github.com/SimVascular/svZeroDSolver/blob/master/LICENSE.txt

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

El texto exacto y completo de esa licencia también está en el `THIRD_PARTY_NOTICES.md`
de la raíz (sección 1). La versión que había aquí estaba truncada (le faltaba el resto del texto).

Fuente: https://github.com/SimVascular/svZeroDSolver-Archived/blob/master/LICENSE.md

**Ninguna línea de ese paquete archivado se copió al proyecto** — se usó
únicamente, de forma aislada (`pip install --target` en un directorio
fuera del repositorio), para generar datos de verificación durante esta
tanda. No es una dependencia de `requirements.txt` ni del módulo de
producción (`r_rcr.py`), que solo depende de `numpy`/`scipy`, ya
dependencias existentes del proyecto.
