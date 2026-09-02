"""Arrhythmia classifier under `biomedical` package (non-intrusive).

This module mirrors the functionality added under ml/ but lives in the
`biomedical` package to avoid colliding with existing project packages.
"""
from typing import List, Tuple, Dict, Any, Optional
import os
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import joblib

try:
    import xgboost as xgb  # type: ignore
except Exception:
    xgb = None

try:
    import lightgbm as lgb  # type: ignore
except Exception:
    lgb = None


def _shannon_entropy(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    hist, _ = np.histogram(x, bins=32, density=True)
    hist = hist[hist > 0]
    probs = hist / hist.sum()
    return -float(np.sum(probs * np.log2(probs)))


class ArrhythmiaClassifier:
    def __init__(self, model_dir: str = "models/trained_models"):
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        self.models: Dict[str, Any] = {}

    def extract_features(self, segment: np.ndarray) -> np.ndarray:
        if segment is None or len(segment) == 0:
            return np.zeros(8, dtype=float)
        x = np.asarray(segment, dtype=float)
        feats = [
            np.mean(x),
            np.std(x),
            np.max(x) - np.min(x),
            np.max(x),
            np.min(x),
            np.sum(x ** 2),
            np.median(x),
            _shannon_entropy(x),
        ]
        return np.array(feats, dtype=float)

    def prepare_dataset(self, segments: List[np.ndarray], labels: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        X = np.vstack([self.extract_features(s) for s in segments])
        y = np.array(labels)
        return X, y

    def train(self, segments: List[np.ndarray], labels: List[str], test_size: float = 0.2, random_state: int = 42) -> Dict[str, Dict[str, Any]]:
        X, y = self.prepare_dataset(segments, labels)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state, stratify=y if len(np.unique(y))>1 else None)

        results: Dict[str, Dict[str, Any]] = {}

        rf = RandomForestClassifier(n_estimators=50, random_state=random_state)
        rf.fit(X_train, y_train)
        self.models["random_forest"] = rf
        results["random_forest"] = self._evaluate_model(rf, X_test, y_test)
        self.save_model(rf, "random_forest.pkl")

        if xgb is not None:
            try:
                xgclf = xgb.XGBClassifier(use_label_encoder=False, eval_metric='mlogloss')
                xgclf.fit(X_train, y_train)
                self.models["xgboost"] = xgclf
                results["xgboost"] = self._evaluate_model(xgclf, X_test, y_test)
                self.save_model(xgclf, "xgboost.pkl")
            except Exception:
                results["xgboost"] = {"error": "training failed"}

        if lgb is not None:
            try:
                lgbclf = lgb.LGBMClassifier()
                lgbclf.fit(X_train, y_train)
                self.models["lightgbm"] = lgbclf
                results["lightgbm"] = self._evaluate_model(lgbclf, X_test, y_test)
                self.save_model(lgbclf, "lightgbm.pkl")
            except Exception:
                results["lightgbm"] = {"error": "training failed"}

        return results

    def _evaluate_model(self, model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        preds = model.predict(X_test)
        acc = float(accuracy_score(y_test, preds))
        prec = float(precision_score(y_test, preds, average='macro', zero_division=0))
        rec = float(recall_score(y_test, preds, average='macro', zero_division=0))
        f1 = float(f1_score(y_test, preds, average='macro', zero_division=0))
        cm = confusion_matrix(y_test, preds).tolist()
        return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "confusion_matrix": cm}

    def predict(self, segments: List[np.ndarray], model_name: str = "random_forest") -> List[str]:
        model = self.models.get(model_name)
        if model is None:
            path = os.path.join(self.model_dir, f"{model_name}.pkl")
            if os.path.exists(path):
                model = joblib.load(path)
                self.models[model_name] = model
            else:
                raise ValueError(f"Model {model_name} not available")
        X = np.vstack([self.extract_features(s) for s in segments])
        preds = model.predict(X)
        return preds.tolist()

    def save_model(self, model: Any, filename: str) -> str:
        path = os.path.join(self.model_dir, filename)
        joblib.dump(model, path)
        return path
