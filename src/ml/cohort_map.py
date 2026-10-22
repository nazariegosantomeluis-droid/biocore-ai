"""Mapa 3D de una base de pacientes con aprendizaje automático (2026-10-21).

La persona sube su propia tabla (una fila por paciente, una columna por
variable) y aquí, sin ninguna IA externa ni clave:

1. Se limpian las columnas numéricas (imputación por mediana, escala z).
2. PCA a 3 componentes: cada paciente es un punto en 3D; pacientes
   parecidos quedan cerca (con la varianza que explica cada eje).
3. K-means con el k que maximiza la silueta (2 a 6): grupos de pacientes.
4. Isolation Forest: pacientes atípicos (posibles errores de captura o
   casos raros) para revisar.
5. Si hay una columna objetivo (p. ej., diagnóstico), un bosque aleatorio
   con validación cruzada estratificada: exactitud y AUC FUERA de la
   muestra de entrenamiento, e importancia por permutación en cada pliegue.

Además, `news2_parameter_scores()` lee signos vitales de una fila (FC, FR,
SpO₂, PAS, temperatura) y los puntúa con NEWS2 parámetro a parámetro, para
colorear ese paciente en el cuerpo 3D.

Es análisis exploratorio y educativo: no diagnostica.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

PCA_CITATION = "Jolliffe IT, Cadima J. Principal component analysis: a review. Phil Trans R Soc A 2016;374:20150202."
KMEANS_CITATION = ("Rousseeuw PJ. Silhouettes: a graphical aid to the interpretation and validation of cluster "
                   "analysis. J Comput Appl Math 1987;20:53-65.")
IFOREST_CITATION = "Liu FT, Ting KM, Zhou ZH. Isolation Forest. ICDM 2008:413-422."
RF_CITATION = "Breiman L. Random forests. Mach Learn 2001;45:5-32."
WDBC_CITATION = ("Wolberg WH, Street WN, Mangasarian OL. Breast Cancer Wisconsin (Diagnostic). UCI Machine "
                 "Learning Repository 1995. doi:10.24432/C5DW2B (CC BY 4.0)")

MIN_ROWS = 8


class CohortError(ValueError):
    """La tabla no sirve para el análisis (pocas filas o columnas)."""


@dataclass
class ModelReport:
    target: str
    classes: List[str]
    n_splits: int
    accuracy: float
    balanced_accuracy: float
    auc: Optional[float]
    importances: Dict[str, float]      # AUC que se pierde al barajar cada variable (solo > 0)
    baseline_accuracy: float


@dataclass
class CohortMap:
    coords: np.ndarray
    explained: np.ndarray
    clusters: np.ndarray
    k: int
    silhouette: Optional[float]
    outlier: np.ndarray
    features: List[str]
    loadings: np.ndarray
    row_ids: List[str]
    cluster_profiles: pd.DataFrame
    model: Optional[ModelReport] = None
    notes: List[str] = field(default_factory=list)


def numeric_frame(df: pd.DataFrame, *, exclude: Sequence[str] = (), max_missing: float = 0.5) -> Tuple[pd.DataFrame, List[str]]:
    """Columnas numéricas útiles (convierte texto numérico, descarta las de
    demasiados faltantes o constantes)."""
    notes = []
    out = {}
    for c in df.columns:
        if c in exclude:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        miss = float(s.isna().mean())
        if miss > max_missing:
            if df[c].notna().any():
                notes.append(f"«{c}» no se usó: {miss:.0%} sin valor numérico")
            continue
        if s.nunique(dropna=True) <= 1:
            notes.append(f"«{c}» no se usó: es constante")
            continue
        out[c] = s
    return pd.DataFrame(out, index=df.index), notes


def build_cohort_map(df: pd.DataFrame, *, target: Optional[str] = None, id_col: Optional[str] = None,
                     k: Optional[int] = None, random_state: int = 0) -> CohortMap:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.ensemble import IsolationForest
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    if len(df) < MIN_ROWS:
        raise CohortError(f"se necesitan al menos {MIN_ROWS} filas (pacientes); hay {len(df)}")
    exclude = [c for c in (target, id_col) if c]
    X, notes = numeric_frame(df, exclude=exclude)
    if X.shape[1] < 2:
        raise CohortError("se necesitan al menos 2 columnas numéricas con datos")
    imputed = int(X.isna().sum().sum())
    if imputed:
        notes.append(f"{imputed} valores faltantes se completaron con la mediana de su columna")
    Xi = SimpleImputer(strategy="median").fit_transform(X)
    Z = StandardScaler().fit_transform(Xi)
    n_comp = min(3, Z.shape[1], Z.shape[0])
    pca = PCA(n_components=n_comp, random_state=random_state)
    coords = pca.fit_transform(Z)
    if coords.shape[1] < 3:
        coords = np.hstack([coords, np.zeros((coords.shape[0], 3 - coords.shape[1]))])
    explained = np.zeros(3)
    explained[:n_comp] = pca.explained_variance_ratio_
    loadings = np.zeros((3, Z.shape[1]))
    loadings[:n_comp] = pca.components_

    best_k, best_s, labels = 1, None, np.zeros(len(df), dtype=int)
    k_range = [k] if k else range(2, min(6, len(df) - 1) + 1)
    for kk in k_range:
        if kk < 2:
            continue
        km = KMeans(n_clusters=kk, n_init=10, random_state=random_state).fit(Z)
        s = float(silhouette_score(Z, km.labels_)) if len(set(km.labels_)) > 1 else -1.0
        if best_s is None or s > best_s:
            best_k, best_s, labels = kk, s, km.labels_
    iso = IsolationForest(contamination="auto", random_state=random_state).fit(Z)
    outlier = iso.predict(Z) == -1
    prof = pd.DataFrame(Z, columns=X.columns).groupby(labels).mean()
    prof.index = [f"Grupo {i + 1}" for i in prof.index]
    ids = df[id_col].astype(str).tolist() if id_col else [f"Fila {i + 1}" for i in range(len(df))]
    model = _supervised(df, Z, list(X.columns), target, random_state) if target else None
    return CohortMap(coords=coords, explained=explained, clusters=labels, k=best_k, silhouette=best_s,
                     outlier=outlier, features=list(X.columns), loadings=loadings, row_ids=ids,
                     cluster_profiles=prof, model=model, notes=notes)


def _supervised(df: pd.DataFrame, Z: np.ndarray, features: List[str], target: str,
                random_state: int) -> Optional[ModelReport]:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
    from sklearn.model_selection import StratifiedKFold

    y_raw = df[target]
    mask = y_raw.notna().to_numpy()
    y_txt = y_raw[mask].astype(str).to_numpy()
    classes = sorted(set(y_txt))
    if len(classes) < 2 or len(classes) > 10:
        return None
    counts = pd.Series(y_txt).value_counts()
    n_splits = int(min(5, counts.min()))
    if n_splits < 2:
        return None
    y = np.array([classes.index(v) for v in y_txt])
    Xm = Z[mask]
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    pred = np.zeros_like(y)
    proba = np.zeros((len(y), len(classes)))
    imps = np.zeros(len(features))
    for tr, te in skf.split(Xm, y):
        rf = RandomForestClassifier(n_estimators=120, random_state=random_state, n_jobs=1,
                                    class_weight="balanced").fit(Xm[tr], y[tr])
        pred[te] = rf.predict(Xm[te])
        proba[te] = rf.predict_proba(Xm[te])
        # Importancia medida con el AUC (continuo): con la exactitud, en un
        # pliegue de ~100 pacientes casi ninguna permutación cambia una
        # predicción y la mayoría de las variables salía en 0.
        pi = permutation_importance(rf, Xm[te], y[te], n_repeats=3, random_state=random_state, n_jobs=1,
                                    scoring="roc_auc" if len(classes) == 2 else "roc_auc_ovr")
        imps += pi.importances_mean
    imps /= n_splits
    auc = None
    try:
        auc = float(roc_auc_score(y, proba[:, 1])) if len(classes) == 2 else float(
            roc_auc_score(y, proba, multi_class="ovr"))
    except ValueError:
        auc = None
    order = np.argsort(imps)[::-1]
    return ModelReport(
        target=target, classes=classes, n_splits=n_splits, accuracy=float(accuracy_score(y, pred)),
        balanced_accuracy=float(balanced_accuracy_score(y, pred)), auc=auc,
        importances={features[i]: float(imps[i]) for i in order[:12] if imps[i] > 0},
        baseline_accuracy=float(counts.max() / counts.sum()),
    )


def top_loadings(cm: CohortMap, axis: int, n: int = 3) -> List[Tuple[str, float]]:
    w = cm.loadings[axis]
    order = np.argsort(np.abs(w))[::-1][:n]
    return [(cm.features[i], float(w[i])) for i in order]


def example_wdbc() -> Tuple[pd.DataFrame, str]:
    """Base real de ejemplo incluida en scikit-learn: Wisconsin Diagnostic
    Breast Cancer (569 pacientes, 30 medidas de núcleos celulares)."""
    from sklearn.datasets import load_breast_cancer

    data = load_breast_cancer(as_frame=True)
    df = data.frame.copy()
    df["diagnóstico"] = np.where(data.target == 0, "maligno", "benigno")
    df = df.drop(columns=["target"])
    df.insert(0, "paciente", [f"WDBC-{i + 1:03d}" for i in range(len(df))])
    return df, "diagnóstico"


# ─────────────────────────────────────────────────────────────────────────
# Signos vitales de una fila -> NEWS2 por parámetro
# ─────────────────────────────────────────────────────────────────────────

_VITAL_PATTERNS = {
    "pulse": r"^(fc|hr|pulso|pulse|heart.?rate|frecuencia.?card[ií]aca|bpm)$",
    "respiratory_rate": r"^(fr|resp|resp.?rate|respiratory.?rate|frecuencia.?respiratoria|rpm)$",
    "spo2": r"^(spo2|sato2|sat|saturaci[oó]n|o2.?sat|spo₂)$",
    "systolic_bp": r"^(pas|sbp|sys|systolic|presi[oó]n.?sist[oó]lica|tas|ta.?sist)$",
    "temperature_c": r"^(temp|temperatura|temperature|t.?c)$",
}
_PLAUSIBLE = {"pulse": (20, 250), "respiratory_rate": (3, 70), "spo2": (50, 100), "systolic_bp": (40, 260),
              "temperature_c": (30, 44)}


def vital_columns(columns: Sequence[str]) -> Dict[str, str]:
    """{parámetro: columna} para las columnas que parecen signos vitales."""
    out = {}
    for col in columns:
        key = re.sub(r"[\s_()\[\]%-]+", "", str(col).strip().lower())
        for param, pat in _VITAL_PATTERNS.items():
            if param not in out and re.match(pat, key.replace(".", "")):
                out[param] = col
    return out


def news2_parameter_scores(row: Mapping[str, object], columns: Mapping[str, str]) -> Dict[str, Optional[int]]:
    """Puntuación NEWS2 de cada signo vital presente (None si falta o no es
    plausible). Usa las mismas funciones de `clinical/calculators.py`."""
    from clinical import calculators as C

    fns = {"pulse": C._news2_pulse, "respiratory_rate": C._news2_rr, "spo2": C._news2_spo2_scale1,
           "systolic_bp": C._news2_sbp, "temperature_c": C._news2_temp}
    out: Dict[str, Optional[int]] = {}
    for param, fn in fns.items():
        col = columns.get(param)
        val = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0] if col else float("nan")
        lo, hi = _PLAUSIBLE[param]
        out[param] = int(fn(float(val))) if (col and math.isfinite(val) and lo <= val <= hi) else None
    return out
