"""Prepara los datos de ejemplo de "Crea tu modelo 3D" (2026-10-21).

Recorta el tórax de la tomografía real del TotalSegmentator (sujeto s1397,
CC BY 4.0) y lo guarda a 2 mm como NIfTI, para que cualquiera pueda probar
la reconstrucción 3D sin tener su propio estudio a mano.

    python tools/build_samples.py --ts-dir RUTA/s1397 --out data/samples

- El corte superior se detiene antes del cráneo: este sujeto tiene la cabeza
  flexionada y la mandíbula queda a la altura de las clavículas (si se
  incluye, el hueso muestra un "disco" plano arriba, que es la mandíbula
  cortada por el borde del volumen).
- El cambio de 1.5 a 2 mm es un remuestreo trilineal con un prefiltro
  gaussiano suave (antialias). Tomar un vóxel de cada dos, como antes,
  partía las costillas en trozos.
"""

from __future__ import annotations

import argparse
import os

import numpy as np

TARGET_MM = 2.0
FILE_NAME = "tc_torax_s1397_2mm.nii.gz"


def main() -> int:
    import nibabel as nib
    from scipy import ndimage

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ts-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    img = nib.load(os.path.join(args.ts_dir, "ct.nii.gz"))
    ct = np.asanyarray(img.dataobj).astype(np.float32)
    zooms = np.asarray(img.header.get_zooms()[:3], dtype=float)
    seg = os.path.join(args.ts_dir, "segmentations")

    def mask(name: str) -> np.ndarray:
        return np.asanyarray(nib.load(os.path.join(seg, f"{name}.nii.gz")).dataobj) > 0

    lungs = np.zeros(ct.shape, bool)
    for n in ("lung_upper_lobe_left", "lung_lower_lobe_left", "lung_upper_lobe_right",
              "lung_middle_lobe_right", "lung_lower_lobe_right"):
        lungs |= mask(n)
    k = np.nonzero(lungs.any(axis=(0, 1)))[0]
    skull = np.nonzero(mask("skull").any(axis=(0, 1)))[0]
    top = min(int(k.max()) + 25, int(skull.min()) if skull.size else ct.shape[2], ct.shape[2])
    k0, k1 = max(int(k.min()) - 20, 0), top
    # Recorte en x/y a la caja del cuerpo (sin la camilla ni el aire de alrededor).
    body = (ct[:, :, k0:k1] > -500).sum(axis=2) > 10
    ii, jj = np.nonzero(body)
    i0, i1 = max(int(np.percentile(ii, 0.5)) - 6, 0), min(int(np.percentile(ii, 99.5)) + 7, ct.shape[0])
    j0, j1 = max(int(np.percentile(jj, 0.5)) - 6, 0), min(int(np.percentile(jj, 99.5)) + 7, ct.shape[1])
    sub = ct[i0:i1, j0:j1, k0:k1]

    step = TARGET_MM / zooms                       # vóxeles de entrada por vóxel de salida
    shape = tuple(int(np.floor((n - 1) / s)) + 1 for n, s in zip(sub.shape, step))
    smooth = ndimage.gaussian_filter(sub, sigma=0.35 * step)
    res = ndimage.affine_transform(smooth, np.diag(step), output_shape=shape, order=1, mode="nearest")
    aff = img.affine.copy()
    aff[:3, 3] = aff[:3, 3] + aff[:3, :3] @ np.array([i0, j0, k0], dtype=float)
    aff[:3, :3] = aff[:3, :3] @ np.diag(step)
    # HU en pasos de 4 (sin pérdida visible para umbrales de hueso/piel/pulmón): comprime mucho mejor.
    res = (np.round(np.clip(res, -1024, 3000) / 4.0) * 4).astype(np.int16)
    out = nib.Nifti1Image(res, aff)
    out.header["descrip"] = b"TotalSegmentator s1397 CC BY 4.0 torax 2 mm"
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, FILE_NAME)
    nib.save(out, path)
    print(path, res.shape, f"{os.path.getsize(path) / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
