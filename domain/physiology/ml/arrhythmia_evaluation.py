"""Evaluacion honesta del clasificador de arritmias (tarjeta del modelo, 2026-11-17; Art. I).

Que se mide: el clasificador de `biomedical/arrhythmia_classifier.py` tal como esta escrito
(sus 8 rasgos de amplitud de `extract_features` y un `LGBMClassifier` con los parametros por
defecto), porque el repositorio no guarda ningun modelo entrenado ni metricas previas.

Dos protocolos sobre la MIT-BIH Arrhythmia Database (PhysioNet `mitdb`, 360 muestras/s):

* **Por latido (el de `ArrhythmiaClassifier.train`)**: `train_test_split` al azar sobre los
  latidos de los 44 registros juntos. Los mismos pacientes quedan en entrenamiento y en prueba
  (fuga de datos entre pacientes): sus cifras se reportan SOLO como evidencia de la fuga.
* **Entre pacientes (de Chazal 2004)**: se entrena con DS1 y se evalua en DS2, registros que el
  modelo no vio. Estas son las cifras de la tarjeta.

Clases AAMI (ANSI/AAMI EC57, agrupacion de de Chazal 2004, tabla I). Ventana del latido:
0.25 s antes y 0.45 s despues de la anotacion R, derivacion MLII sin filtrar (Criterio BIOCORE:
la clase no fija ventana ni filtro; se declara aqui y en results.json).

Reproducir (el python del PATH, con la base descargada fuera de git):
    python -m domain.physiology.ml.arrhythmia_evaluation --mitdb C:/Users/luisn/biocore_cache/mitdb
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import platform
from pathlib import Path

import numpy as np

RESULTS_DIR = Path(__file__).resolve().parents[3] / "docs" / "validation" / "arrhythmia_classifier"
RESULTS_PATH = RESULTS_DIR / "results.json"
MODEL_VERSION = "lgbm-8rasgos-ds1-v1"

# de Chazal P, O'Dwyer M, Reilly RB. IEEE Trans Biomed Eng 2004;51(7):1196-1206.
# Sin los 4 registros con marcapasos (102, 104, 107, 217).
DS1 = (101, 106, 108, 109, 112, 114, 115, 116, 118, 119, 122,
       124, 201, 203, 205, 207, 208, 209, 215, 220, 223, 230)
DS2 = (100, 103, 105, 111, 113, 117, 121, 123, 200, 202, 210,
       212, 213, 214, 219, 221, 222, 228, 231, 232, 233, 234)
EXCLUDED_PACED = (102, 104, 107, 217)

CLASSES = ("N", "S", "V", "F", "Q")
AAMI = {
    "N": "N", "L": "N", "R": "N", "e": "N", "j": "N",
    "A": "S", "a": "S", "J": "S", "S": "S",
    "V": "V", "E": "V",
    "F": "F",
    "/": "Q", "f": "Q", "Q": "Q",
}
FS = 360
PRE_S, POST_S = 0.25, 0.45
FEATURE_NAMES = ("media", "desviacion", "rango", "maximo", "minimo", "energia", "mediana", "entropia")
# Criterio BIOCORE (sin cita): por debajo de esta sensibilidad en una clase, el modelo se
# rotula "en evaluacion".
LOW_SENSITIVITY = 0.80
RELIABILITY_BINS = 10
SEED = 42


def _feature_extractor():
    # Los rasgos del modelo, sin instanciarlo: su __init__ crea carpetas en disco.
    from biomedical.arrhythmia_classifier import ArrhythmiaClassifier

    return ArrhythmiaClassifier.__new__(ArrhythmiaClassifier).extract_features


def load_record_beats(mitdb_dir: Path, record: int):
    """Segmentos (MLII, mV) y clase AAMI de cada latido anotado de un registro."""
    import wfdb

    path = str(Path(mitdb_dir) / str(record))
    rec = wfdb.rdrecord(path)
    ann = wfdb.rdann(path, "atr")
    sig = rec.p_signal[:, rec.sig_name.index("MLII")]
    pre, post = int(PRE_S * FS), int(POST_S * FS)
    segments, labels = [], []
    for sample, symbol in zip(ann.sample, ann.symbol):
        cls = AAMI.get(symbol)
        if cls is None or sample - pre < 0 or sample + post > sig.size:
            continue
        segments.append(sig[sample - pre: sample + post])
        labels.append(cls)
    return segments, labels


def features_frame(segments):
    import pandas as pd

    extract = _feature_extractor()
    return pd.DataFrame([extract(s) for s in segments], columns=list(FEATURE_NAMES))


def _dataset(mitdb_dir, records):
    X, y, rec_of = [], [], []
    for r in records:
        segs, labs = load_record_beats(mitdb_dir, r)
        X.extend(segs)
        y.extend(labs)
        rec_of.extend([r] * len(labs))
    return features_frame(X), np.array(y), np.array(rec_of)


def _model():
    import lightgbm as lgb

    # Los parametros por defecto de la clase; se fija la semilla, se exige determinismo (sin el,
    # dos corridas identicas dieron sensibilidad de N 0.9047 y 0.9003) y se silencia el registro.
    return lgb.LGBMClassifier(random_state=SEED, verbose=-1, deterministic=True, force_row_wise=True)


def brier_multiclass(y_true, proba, classes=CLASSES) -> float:
    """Brier (1950), forma multicategoria: media de sum_k (p_k - o_k)^2; 0 es perfecto, 2 el peor."""
    onehot = (np.asarray(y_true)[:, None] == np.asarray(classes)[None, :]).astype(float)
    return float(np.mean(np.sum((np.asarray(proba) - onehot) ** 2, axis=1)))


def reliability(y_true, y_pred, proba, n_bins=RELIABILITY_BINS):
    """Curva de confiabilidad de la clase elegida: confianza media vs exactitud por intervalo."""
    conf = np.max(proba, axis=1)
    hit = (np.asarray(y_true) == np.asarray(y_pred)).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (conf >= lo) & ((conf < hi) if i < n_bins - 1 else (conf <= hi))
        n = int(m.sum())
        bins.append({
            "desde": round(float(lo), 2), "hasta": round(float(hi), 2), "latidos": n,
            "confianza_media": float(conf[m].mean()) if n else None,
            "exactitud": float(hit[m].mean()) if n else None,
        })
    return bins


def class_metrics(y_true, y_pred, classes=CLASSES):
    """Matriz de confusion (filas = verdad, columnas = prediccion) y Se, +P y F1 por clase."""
    from sklearn.metrics import confusion_matrix

    cm = confusion_matrix(y_true, y_pred, labels=list(classes))
    per_class = {}
    for i, c in enumerate(classes):
        tp, support, predicted = int(cm[i, i]), int(cm[i].sum()), int(cm[:, i].sum())
        se = tp / support if support else None
        ppv = tp / predicted if predicted else None
        f1 = (2 * se * ppv / (se + ppv)) if se is not None and ppv and (se + ppv) > 0 else (0.0 if support else None)
        per_class[c] = {"latidos": support, "predichos": predicted, "sensibilidad": se,
                        "valor_predictivo_positivo": ppv, "f1": f1}
    present = [c for c in classes if per_class[c]["latidos"]]
    macro_f1 = float(np.mean([per_class[c]["f1"] for c in present]))
    accuracy = float(np.trace(cm) / cm.sum())
    return cm.tolist(), per_class, macro_f1, accuracy


def _counts(y):
    return {c: int(np.sum(np.asarray(y) == c)) for c in CLASSES}


def per_beat_split_metrics(X, y, rec_of):
    """El protocolo de `ArrhythmiaClassifier.train`: 80/20 al azar por latido, estratificado."""
    from sklearn.model_selection import train_test_split

    idx = np.arange(len(y))
    tr, te = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=y)
    model = _model().fit(X.iloc[tr], y[tr])
    cm, per_class, macro_f1, acc = class_metrics(y[te], model.predict(X.iloc[te]))
    shared = sorted(set(rec_of[tr].tolist()) & set(rec_of[te].tolist()))
    return {
        "descripcion": "train_test_split(test_size=0.2, stratify) por latido sobre DS1 y DS2 juntos, como ArrhythmiaClassifier.train",
        "registros_en_entrenamiento_y_prueba": len(shared),
        "registros_totales": int(len(set(rec_of.tolist()))),
        "exactitud": acc, "f1_macro": macro_f1, "por_clase": per_class, "matriz_confusion": cm,
    }


def _save_pngs(cm, bins, out_dir):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cm = np.asarray(cm, dtype=float)
    frac = cm / np.where(cm.sum(axis=1, keepdims=True) == 0, 1, cm.sum(axis=1, keepdims=True))
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    ax.imshow(frac, cmap="Blues", vmin=0, vmax=1)
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            ax.text(j, i, f"{int(cm[i, j])}\n{frac[i, j]:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if frac[i, j] > 0.5 else "black")
    ax.set_xticks(range(5), CLASSES)
    ax.set_yticks(range(5), CLASSES)
    ax.set_xlabel("Clase predicha")
    ax.set_ylabel("Clase verdadera (anotación MIT-BIH)")
    ax.set_title("Matriz de confusión, DS2 (fracción por fila)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_matrix.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    xs = [b["confianza_media"] for b in bins if b["latidos"]]
    ys = [b["exactitud"] for b in bins if b["latidos"]]
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Calibración perfecta")
    ax.plot(xs, ys, marker="o", label="Modelo (DS2)")
    ax.set_xlabel("Confianza media de la clase elegida")
    ax.set_ylabel("Fracción de aciertos")
    ax.set_title("Curva de confiabilidad, DS2 (10 intervalos)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out_dir / "reliability_curve.png", dpi=130)
    plt.close(fig)


def evaluate(mitdb_dir: Path, out_dir: Path = RESULTS_DIR, model_path: Path | None = None) -> dict:
    import joblib
    import lightgbm
    import sklearn

    assert not set(DS1) & set(DS2), "DS1 y DS2 deben ser disjuntos"
    X1, y1, r1 = _dataset(mitdb_dir, DS1)
    X2, y2, r2 = _dataset(mitdb_dir, DS2)

    model = _model().fit(X1, y1)
    pred = model.predict(X2)
    proba_raw = model.predict_proba(X2)
    # Columnas de probabilidad en el orden CLASSES (una clase sin latidos en DS1 tendria 0).
    proba = np.zeros((len(y2), len(CLASSES)))
    for k, c in enumerate(model.classes_):
        proba[:, CLASSES.index(c)] = proba_raw[:, k]
    cm, per_class, macro_f1, acc = class_metrics(y2, pred)
    bins = reliability(y2, pred, proba)

    model_sha = None
    if model_path is not None:
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_path)
        model_sha = hashlib.sha256(Path(model_path).read_bytes()).hexdigest()

    low = [c for c in CLASSES if per_class[c]["latidos"] and (per_class[c]["sensibilidad"] or 0) < LOW_SENSITIVITY]
    results = {
        "fecha": _dt.date.today().isoformat(),
        "modelo": {
            "version": MODEL_VERSION,
            "codigo": "biomedical/arrhythmia_classifier.py (extract_features) + LGBMClassifier por defecto",
            "parametros": "LGBMClassifier(random_state=42, verbose=-1, deterministic=True, force_row_wise=True); el resto, por defecto",
            "rasgos": list(FEATURE_NAMES),
            "sha256_archivo_modelo": model_sha,
            "versiones": {"python": platform.python_version(), "lightgbm": lightgbm.__version__,
                          "scikit_learn": sklearn.__version__, "numpy": np.__version__},
        },
        "datos": {
            "base": "MIT-BIH Arrhythmia Database (PhysioNet mitdb), 360 muestras/s, derivación MLII",
            "separacion": "entre pacientes: entrenamiento con DS1, evaluación con DS2 (de Chazal 2004)",
            "cita_separacion": "de Chazal P, O'Dwyer M, Reilly RB. IEEE Trans Biomed Eng 2004;51(7):1196-1206",
            "registros_entrenamiento": list(DS1),
            "registros_evaluacion": list(DS2),
            "registros_excluidos_marcapasos": list(EXCLUDED_PACED),
            "clases_aami": "ANSI/AAMI EC57; N={N,L,R,e,j}, S={A,a,J,S}, V={V,E}, F={F}, Q={/,f,Q}",
            "ventana_latido": f"{PRE_S} s antes y {POST_S} s después de la anotación R, sin filtro (Criterio BIOCORE)",
            "latidos_entrenamiento": _counts(y1),
            "latidos_evaluacion": _counts(y2),
        },
        "evaluacion_entre_pacientes": {
            "clases": list(CLASSES),
            "matriz_confusion": cm,
            "por_clase": per_class,
            "f1_macro": macro_f1,
            "f1_macro_definicion": "media del F1 de las clases con al menos un latido en DS2",
            "exactitud": acc,
            "exactitud_advertencia": "Con clases desbalanceadas (la N domina), la exactitud global engaña: un modelo que siempre dijera N la tendría alta.",
            "brier": brier_multiclass(y2, proba),
            "brier_definicion": "Brier (1950), forma multicategoría: media de la suma de (p_k − o_k)² sobre 5 clases; 0 es perfecto y 2 el peor",
            "confiabilidad": bins,
        },
        "fuga_por_latido": per_beat_split_metrics(
            __import__("pandas").concat([X1, X2], ignore_index=True),
            np.concatenate([y1, y2]), np.concatenate([r1, r2])),
        "estado": "en evaluacion" if low else "evaluado",
        "clases_con_sensibilidad_baja": low,
        "umbral_sensibilidad_baja": LOW_SENSITIVITY,
        "umbral_sensibilidad_baja_origen": "Criterio BIOCORE (sin cita)",
        "uso_previsto": "Educativo. No apto para diagnóstico ni para decisiones clínicas.",
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _save_pngs(cm, bins, out_dir)
    return results


def load_results(path: Path = RESULTS_PATH) -> dict | None:
    """Lee results.json; None si no existe (la UI dice «no disponible» con el motivo)."""
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mitdb", required=True, type=Path, help="carpeta con los registros de mitdb")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    ap.add_argument("--model", type=Path, default=None, help="donde guardar el modelo entrenado (fuera de git)")
    a = ap.parse_args()
    r = evaluate(a.mitdb, a.out, a.model)
    print(json.dumps({k: r[k] for k in ("estado", "clases_con_sensibilidad_baja")}, ensure_ascii=False))
    for c, m in r["evaluacion_entre_pacientes"]["por_clase"].items():
        print(c, m)
    print("fuga:", r["fuga_por_latido"]["exactitud"], r["fuga_por_latido"]["f1_macro"])
