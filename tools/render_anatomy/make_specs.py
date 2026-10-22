"""Genera specs/*.json (renders finales) desde las mallas exportadas en meshes/."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
B, H = "body", "head"


def load(asset, key):
    idx = json.load(open(os.path.join(HERE, "meshes", asset, "index.json")))
    info = idx["meshes"][key]
    raw = open(os.path.join(HERE, "meshes", asset, key + ".bin"), "rb").read()
    v = np.frombuffer(raw, np.float32, info["n_vertices"] * 3).reshape(-1, 3)
    return v


def spec(name, **kw):
    os.makedirs(os.path.join(HERE, "specs"), exist_ok=True)
    with open(os.path.join(HERE, "specs", name + ".json"), "w") as fh:
        json.dump(kw, fh, indent=1)


def o(key, material, asset=B, **kw):
    d = dict(asset=asset, key=key, material=material)
    d.update(kw)
    return d


GLASS = dict(color="#cdeffa", power=2.8, strength=0.9, base=0.012)

# ── Tarjetas de órganos (gemelo digital) ─────────────────────────────────
BACK_TOP = float(load(B, "back_muscles")[:, 1].max())
META = json.load(open(os.path.join(HERE, "meshes", B, "index.json")))["meta"]
ORIGIN = META["origin_mm"]
VERT_Y = {k: v[2] + ORIGIN[2] for k, v in META["vertebrae"].items()}  # three.y = RAS z
heart_clip = [-75, 100, 140, 100, 262, 290]
spec("organ_heart", size=[480, 480], envIntensity=0.45,
     camera=dict(azimuth=24, elevation=8, fov=24, margin=0.95),
     objects=[o("heart", "heart", override=dict(clearcoat=0.35, roughness=0.5)),
              o("artery_roots", "artery", frame=False), o("vein_roots", "vein", frame=False)])
spec("organ_lungs", size=[480, 480], envIntensity=0.45,
     camera=dict(azimuth=0, elevation=4, fov=24, margin=0.86),
     objects=[o("lung_right", "lung"), o("lung_left", "lung"), o("trachea", "trachea"),
              o("heart", "heart", frame=False)])
spec("organ_brain", size=[480, 480], envIntensity=0.42,
     camera=dict(azimuth=90, elevation=12, fov=24, margin=0.84),
     objects=[o("brain", "brain", asset=H, override=dict(color="#d9a196"))])
spec("organ_muscles", size=[480, 480], envIntensity=0.45,
     camera=dict(azimuth=180, elevation=10, fov=24, margin=0.86),
     objects=[o("back_muscles", "muscle"), o("iliopsoas", "muscle"), o("gluteals", "muscle"),
              o("pelvis", "bone", frame=False), o("femurs", "bone", frame=False),
              o("spine", "bone", frame=False, clip=[-400, -400, -400, 400, BACK_TOP, 600])])
# Sistema autónomo: la médula espinal con el tramo T1-L2 (salida simpática) resaltado.
t1, l2 = VERT_Y["T1"] + 8, VERT_Y["L2"] - 8
c7, l3 = VERT_Y["C7"], VERT_Y["L3"]
spec("organ_autonomic", size=[480, 480], envIntensity=0.45,
     camera=dict(azimuth=80, elevation=4, fov=24, distance=980, margin=1.0, up=[-0.62, 0.78, 0],
                 target=[0, (c7 + l3) / 2, 140]),
     objects=[o("spinal_cord", "cord", clip=[-400, t1, -400, 400, 900, 600]),
              o("spinal_cord", "cord", override=dict(color="#7fe7ff", emissive="#22d3ee", emissiveIntensity=0.55,
                                                     roughness=0.35, clearcoat=0.6), clip=[-400, l2, -400, 400, t1, 600]),
              o("spinal_cord", "cord", clip=[-400, -900, -400, 400, l2, 600]),
              o("spine", "bone_dim", frame=True, override=dict(opacity=0.22),
                clip=[-400, l3 - 15, -400, 400, c7 + 20, 600])])

# ── Atlas: cuerpo completo ───────────────────────────────────────────────
body_parts = [
    ("skull", "bone"), ("spine", "bone"), ("ribs", "bone"), ("sternum", "bone"),
    ("costal_cartilages", "cartilage"), ("shoulder_girdle", "bone"), ("humeri", "bone"),
    ("pelvis", "bone"), ("femurs", "bone"),
    ("heart", "heart"), ("arteries", "artery"), ("veins", "vein"), ("pulmonary_veins", "pulmvein"),
    ("lung_right", "lung_glass"), ("lung_left", "lung_glass"), ("trachea", "trachea"),
    ("brain", "brain"), ("spinal_cord", "cord"),
    ("liver", "liver"), ("gallbladder", "gall"), ("stomach", "stomach"), ("esophagus", "esophagus"),
    ("duodenum", "bowel"), ("small_bowel", "bowel"), ("colon", "colon"), ("pancreas", "pancreas"),
    ("spleen", "spleen"), ("kidneys", "kidney"), ("adrenals", "adrenal"), ("bladder", "bladder"),
    ("prostate", "prostate"), ("thyroid", "thyroid"),
]
spec("atlas_body", size=[720, 1100], envIntensity=0.45,
     camera=dict(azimuth=0, elevation=3, fov=22, margin=0.66),
     objects=[o(k, m) for k, m in body_parts] + [o("skin", "glass", override=GLASS)])

# ── Atlas: precordiales sobre el tórax real ──────────────────────────────
idx = json.load(open(os.path.join(HERE, "meshes", B, "index.json")))
lm = idx["landmarks"]
anchors = []
for n, p, nn in zip(lm["names"], lm["xyz"], lm["normal"]):
    p = np.asarray(p) + 1.0 * np.asarray(nn)
    anchors.append(dict(id=n, pos=p.tolist(), normal=nn, pad=9.5))
thorax_clip = [-400, 108, -400, 400, 600, 600]
spec("atlas_precordial", size=[900, 760], envIntensity=0.45,
     camera=dict(azimuth=34, elevation=10, fov=24, margin=0.5, target=[70, 175, 200]),
     objects=[o(k, m) for k, m in [("ribs", "bone"), ("sternum", "bone"), ("costal_cartilages", "cartilage"),
                                    ("shoulder_girdle", "bone"), ("spine", "bone"), ("heart", "heart"),
                                    ("pulmonary_veins", "pulmvein"), ("lung_right", "lung_glass"),
                                    ("lung_left", "lung_glass"), ("trachea", "trachea")]]
             + [o("arteries", "artery", clip=thorax_clip), o("veins", "vein", clip=thorax_clip),
                o("skin", "glass", frame=False, override=GLASS)],
     anchors=anchors)

# ── Atlas: 10-20 sobre la cabeza ─────────────────────────────────────────
for name, cam in (("atlas_1020_top", dict(azimuth=0, elevation=90, fov=24, margin=0.66, up=[0, 0, 1],
                                          target=[0, 20, -14])),
                  ("atlas_1020_left", dict(azimuth=90, elevation=6, fov=24, margin=0.8, target=[0, 4, -12]))):
    spec(name, size=[760, 760], envIntensity=0.42, exposure=0.82, camera=cam,
         objects=[o("scalp", "mannequin", asset=H, override=dict(color="#b3bfd2"),
                    clip=[-400, -95, -400, 400, 400, 400])],
         electrodes=dict(asset=H, pad=6.0, lift=0.0))

# ── Atlas: corazón real + anclas del sistema de conducción ───────────────
heart = load(B, "heart")
veins = load(B, "veins")
c = heart.mean(axis=0)
# Eje largo: componente principal orientada hacia izquierda-abajo-adelante (ápex).
u, s_, vt = np.linalg.svd(heart - c, full_matrices=False)
axis = vt[0]
if axis @ np.array([1.0, -1.0, 1.0]) < 0:
    axis = -axis
proj = (heart - c) @ axis
apex = heart[np.argmax(proj)]
base_c = c - axis * (proj.max() * 0.55)
# Unión vena cava superior - aurícula derecha: vértices venosos a < 12 mm del
# corazón, por encima del centro y a la derecha del paciente (three.x < c.x).
from scipy.spatial import cKDTree  # noqa: E402

d, _ = cKDTree(heart).query(veins)
near = veins[(d < 12)]
svc = near[(near[:, 1] > c[1]) & (near[:, 0] < c[0])]
ivc = near[(near[:, 1] < c[1]) & (near[:, 0] < c[0])]
sa = svc[np.argmin(svc[:, 1])] if len(svc) else base_c
ivc_c = ivc.mean(axis=0) if len(ivc) else base_c
av = ivc_c + (c - ivc_c) * 0.45
his = av + (apex - av) * 0.22
# Pared libre del VI (más a la izquierda) y del VD (más anterior-derecha) a 60 % del eje.
lvl = (heart - c) @ axis
band = heart[(lvl > proj.max() * 0.15) & (lvl < proj.max() * 0.55)]
lv = band[np.argmax(band[:, 0])]
rv = band[np.argmax(band[:, 2])]
la = heart[np.argmax((heart - c) @ np.array([1.0, 0.6, -0.8]))]
anch = [dict(id="SA", pos=sa.tolist()), dict(id="AV", pos=av.tolist()), dict(id="His", pos=his.tolist()),
        dict(id="Apex", pos=apex.tolist()), dict(id="LV", pos=lv.tolist()), dict(id="RV", pos=rv.tolist()),
        dict(id="LA", pos=la.tolist()), dict(id="Center", pos=c.tolist())]
spec("atlas_heart", size=[720, 720], envIntensity=0.45,
     camera=dict(azimuth=0, elevation=4, fov=24, margin=0.92),
     objects=[o("heart", "heart", override=dict(clearcoat=0.35, roughness=0.5)),
              o("artery_roots", "artery", frame=False), o("vein_roots", "vein", frame=False)],
     anchors=anch)
print("specs listos")
