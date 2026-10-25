"""Mapa 3D de una base de pacientes con aprendizaje automático (aporte auditado, Tanda 2D, 2026-10-24).

La persona sube su propia tabla (una fila por paciente, una columna por
variable) y aquí, sin ninguna IA externa ni clave:

1. Se toman las columnas numéricas útiles y se EXCLUYEN las que parecen un
   identificador (`id_like_columns`, ver abajo).
2. PCA a 3 componentes: cada paciente es un punto en 3D; pacientes
   parecidos quedan cerca (con la varianza que explica cada eje).
3. K-means con el k que maximiza la silueta (2 a 6): grupos de pacientes.
4. Isolation Forest: pacientes atípicos (posibles errores de captura o
   casos raros) para revisar.
5. Si hay una columna objetivo (p. ej., diagnóstico), un bosque aleatorio
   con validación cruzada estratificada: exactitud y AUC FUERA de la
   muestra de entrenamiento, e importancia por permutación en el pliegue de
   prueba. La imputación va DENTRO de cada pliegue (Pipeline); el bosque no
   necesita escala. Los pasos 2-4 son no supervisados, usan toda la tabla y
   no afirman nada fuera de la muestra.

Guardia anti-fuga por ID (Tanda 2D): en el aporte, un número de paciente
no declarado como ID, en una tabla ordenada por diagnóstico, daba AUC 1.000
con el ID como "variable más importante" y ningún aviso: el modelo aprendía
el orden de las filas, no la fisiología. Ahora esas columnas se excluyen y
se avisa, y un AUC casi perfecto o una variable principal que sigue el orden
de la tabla también generan un aviso (`CohortMap.warnings`).

Es análisis exploratorio y educativo, no validado: no diagnostica.
(El cuerpo 3D coloreado por NEWS2 del aporte no entró: ver CHANGELOG, Tanda 2D.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

PCA_CITATION = "Jolliffe IT, Cadima J. Principal component analysis: a review. Phil Trans R Soc A 2016;374:20150202."
KMEANS_CITATION = ("Rousseeuw PJ. Silhouettes: a graphical aid to the interpretation and validation of cluster "
                   "analysis. J Comput Appl Math 1987;20:53-65.")
IFOREST_CITATION = "Liu FT, Ting KM, Zhou ZH. Isolation Forest. ICDM 2008:413-422."
RF_CITATION = "Breiman L. Random forests. Mach Learn 2001;45:5-32."
WDBC_CITATION = ("Wolberg WH, Street WN, Mangasarian OL. Breast Cancer Wisconsin (Diagnostic). UCI Machine "
                 "Learning Repository 1995. doi:10.24432/C5DW2B (CC BY 4.0)")
EXPLORATORY_NOTE = "Análisis exploratorio, no validado: no es un diagnóstico ni un modelo para uso clínico."

MIN_ROWS = 8
MAX_CLASSES = 10
# Nombres típicos de un identificador (el índice que pandas escribe al guardar es "Unnamed: 0").
ID_NAME_PATTERN = re.compile(
    r"^(id|.+[_\s.-]id|id[_\s.-].+|n[ºo°.]?|num|numero|número|paciente|patient|record|registro|folio|"
    r"expediente|nhc|mrn|index|idx|unnamed:\s*\d+)$", re.IGNORECASE)
ORDER_RHO = 0.99            # |ρ de Spearman| con el número de fila para tratar una columna como ID
ORDER_LEAK_RHO = 0.9        # para avisar que la variable principal sigue el orden de la tabla
NEAR_PERFECT_AUC = 0.995    # heurístico: en datos clínicos un AUC así suele ser una fuga


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
    model_skipped: Optional[str] = None            # por qué no se entrenó el modelo, si se pidió
    id_excluded: Dict[str, str] = field(default_factory=dict)   # columna -> por qué parece un ID
    warnings: List[str] = field(default_factory=list)           # avisos de fuga: se muestran siempre
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


def _order_rho(values: pd.Series) -> float:
    """ρ de Spearman entre la columna y el número de fila (0 si no se puede calcular)."""
    ok = values.notna().to_numpy()
    if ok.sum() < 3:
        return 0.0
    rho = pd.Series(values.to_numpy()[ok]).corr(pd.Series(np.nonzero(ok)[0]), method="spearman")
    return 0.0 if pd.isna(rho) else float(rho)


def id_like_columns(X: pd.DataFrame) -> Dict[str, str]:
    """Columnas que parecen un identificador: por su nombre, o por su forma
    (enteras, únicas por fila y en el mismo orden que las filas). Un ID nunca
    es fisiología; en una tabla ordenada por diagnóstico, además, filtra la
    respuesta."""
    out = {}
    for c in X.columns:
        if ID_NAME_PATTERN.match(str(c).strip()):
            out[c] = "su nombre indica un identificador"
            continue
        v = X[c].dropna()
        if len(v) < MIN_ROWS or v.nunique() != len(v) or not np.allclose(v, np.round(v)):
            continue
        rho = _order_rho(X[c])
        if abs(rho) >= ORDER_RHO:
            out[c] = f"es entera, única por fila y sigue el orden de las filas (ρ de Spearman {rho:+.2f})"
    return out


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
    id_excluded = id_like_columns(X)
    warnings = [
        f"«{c}» se excluyó del análisis: {why}. Si el modelo la usara, aprendería el orden o el registro de la "
        "tabla, no la fisiología (posible fuga por ID)."
        for c, why in id_excluded.items()
    ]
    X = X.drop(columns=list(id_excluded))
    if X.shape[1] < 2:
        extra = f" (se excluyeron como identificador: {', '.join(id_excluded)})" if id_excluded else ""
        raise CohortError("se necesitan al menos 2 columnas numéricas con datos" + extra)
    imputed = int(X.isna().sum().sum())
    if imputed:
        notes.append(f"{imputed} valores faltantes se completaron con la mediana de su columna")
    Z = StandardScaler().fit_transform(SimpleImputer(strategy="median").fit_transform(X))
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
    model, skipped = (None, None)
    if target:
        model, skipped = _supervised(df, X, target, random_state)
        if model is not None:
            warnings += _leak_warnings(df, X, model)
    return CohortMap(coords=coords, explained=explained, clusters=labels, k=best_k, silhouette=best_s,
                     outlier=outlier, features=list(X.columns), loadings=loadings, row_ids=ids,
                     cluster_profiles=prof, model=model, model_skipped=skipped, id_excluded=id_excluded,
                     warnings=warnings, notes=notes)


def _supervised(df: pd.DataFrame, X: pd.DataFrame, target: str,
                random_state: int) -> Tuple[Optional[ModelReport], Optional[str]]:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline

    features = list(X.columns)
    mask = df[target].notna().to_numpy()
    y_txt = df[target][mask].astype(str).to_numpy()
    classes = sorted(set(y_txt))
    if len(classes) < 2:
        return None, f"No se entrenó un modelo: «{target}» tiene una sola categoría, no hay nada que predecir."
    if len(classes) > MAX_CLASSES:
        return None, (f"No se entrenó un modelo: «{target}» tiene {len(classes)} valores distintos y el modelo "
                      f"es un clasificador de hasta {MAX_CLASSES} categorías (diagnóstico, desenlace…). Si es una "
                      "medida continua o un identificador, no es una categoría; si de verdad son tantas "
                      "categorías, cada una queda con muy pocos pacientes para validar fuera de la muestra.")
    counts = pd.Series(y_txt).value_counts()
    n_splits = int(min(5, counts.min()))
    if n_splits < 2:
        return None, (f"No se entrenó un modelo: la categoría «{counts.idxmin()}» tiene un solo paciente y la "
                      "validación cruzada necesita al menos 2 por categoría.")
    y = np.array([classes.index(v) for v in y_txt])
    Xm = X.to_numpy(dtype=float)[mask]
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    pred = np.zeros_like(y)
    proba = np.zeros((len(y), len(classes)))
    imps = np.zeros(len(features))
    for tr, te in skf.split(Xm, y):
        # La imputación se ajusta solo con el pliegue de entrenamiento.
        rf = make_pipeline(SimpleImputer(strategy="median"),
                           RandomForestClassifier(n_estimators=120, random_state=random_state, n_jobs=1,
                                                  class_weight="balanced")).fit(Xm[tr], y[tr])
        pred[te] = rf.predict(Xm[te])
        proba[te] = rf.predict_proba(Xm[te])
        # Importancia medida con el AUC (continuo): con la exactitud, en un
        # pliegue de ~100 pacientes casi ninguna permutación cambia una
        # predicción y la mayoría de las variables salía en 0.
        pi = permutation_importance(rf, Xm[te], y[te], n_repeats=3, random_state=random_state, n_jobs=1,
                                    scoring="roc_auc" if len(classes) == 2 else "roc_auc_ovr")
        imps += pi.importances_mean
    imps /= n_splits
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
    ), None


def _leak_warnings(df: pd.DataFrame, X: pd.DataFrame, model: ModelReport) -> List[str]:
    """Segunda red, después de entrenar: una variable principal que sigue el
    orden de una tabla ordenada por el objetivo, o un AUC casi perfecto."""
    out = []
    top = next(iter(model.importances), None)
    y = df[model.target].dropna().astype(str).to_numpy()
    sorted_by_target = int((y[1:] != y[:-1]).sum()) == len(set(y)) - 1
    if top is not None and sorted_by_target and abs(_order_rho(X[top])) >= ORDER_LEAK_RHO:
        out.append(f"La tabla está ordenada por «{model.target}» y «{top}», la variable más importante, también "
                   f"sigue el orden de las filas (ρ de Spearman {_order_rho(X[top]):+.2f}): el modelo puede estar "
                   "aprendiendo el orden de la tabla, no la fisiología. Revisa esa columna.")
    if model.auc is not None and model.auc >= NEAR_PERFECT_AUC:
        out.append(f"AUC {model.auc:.3f}, casi perfecto. En datos clínicos eso suele indicar una fuga: un "
                   "identificador, un código del propio diagnóstico o una medida tomada después de conocerlo"
                   + (f". Revisa «{top}», la variable más importante." if top else "."))
    return out


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
