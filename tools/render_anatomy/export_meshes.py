"""npz (data/anatomy3d) -> meshes/<asset>/<key>.bin (Float32 xyz en coords three.js + Uint32 idx)."""
import json, os, sys
import numpy as np

def load(path):
    z = np.load(path, allow_pickle=False)
    meta = json.loads(bytes(z["meta"]).decode("utf-8"))
    scale = meta["vertex_scale_mm"]; origin = np.asarray(meta["origin_mm"], np.float32)
    out = {}
    for k in z.files:
        if k.endswith("__v"):
            key = k[:-3]
            v = z[k].astype(np.float32) * scale + origin
            f = z[key + "__f"].astype(np.uint32)
            out[key] = (v, f)
    extra = {k: z[k] for k in z.files if "__" in k and not (k.endswith("__v") or k.endswith("__f"))}
    return meta, out, extra

def ras_to_three(v):
    # three.x = -RAS x (izquierda del paciente a la derecha de la pantalla vista de frente),
    # three.y = RAS z (arriba), three.z = RAS y (anterior hacia la cámara)
    return np.stack([-v[:, 0], v[:, 2], v[:, 1]], axis=1).astype(np.float32)

def main(npz, outdir):
    meta, meshes, extra = load(npz)
    os.makedirs(outdir, exist_ok=True)
    index = {"meta": meta, "meshes": {}}
    for key, (v, f) in meshes.items():
        t = ras_to_three(v)
        with open(os.path.join(outdir, key + ".bin"), "wb") as fh:
            fh.write(t.tobytes()); fh.write(f.ravel().tobytes())
        index["meshes"][key] = {"n_vertices": int(t.shape[0]), "n_indices": int(f.size),
                                "min": t.min(axis=0).tolist(), "max": t.max(axis=0).tolist()}
    origin = np.asarray(meta["origin_mm"], np.float32)
    if "landmarks__xyz" in extra:
        xyz = extra["landmarks__xyz"].astype(np.float32) + origin
        nrm = extra["landmarks__normal"].astype(np.float32)
        index["landmarks"] = {"names": [l["name"] for l in meta["landmarks"]],
                              "xyz": ras_to_three(xyz).tolist(), "normal": ras_to_three(nrm).tolist()}
    for k, arr in extra.items():
        if k == "electrodes__xyz":
            index["electrodes"] = {"names": meta["electrodes"], "xyz": ras_to_three(arr.astype(np.float32)).tolist()}
    with open(os.path.join(outdir, "index.json"), "w") as fh:
        json.dump(index, fh)
    print(outdir, len(meshes), "meshes")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
