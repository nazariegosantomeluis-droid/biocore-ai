"""Explainability utilities for ECG models with graceful fallbacks.

This module provides lightweight, dependency-safe interpretability helpers that
work even when PyTorch is unavailable. It includes gradient-based saliency,
permutation importance, LIME-style local explanations, and coefficient-based
importance for linear models.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


def _safe_import_torch() -> Any:
    try:
        import torch
        return torch
    except ImportError:
        return None


def is_torch_available() -> bool:
    return _safe_import_torch() is not None


def normalize_importance(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    denom = np.max(np.abs(arr))
    return arr / denom if denom != 0 else arr


def grad_cam_placeholder(model: Any, signal: np.ndarray) -> np.ndarray:
    activation = np.abs(np.gradient(signal.astype(float)))
    activation = activation / (np.max(activation) + 1e-8)
    return activation


def simple_gradient_saliency(model: Any, input_signal: np.ndarray, target_index: Optional[int] = None) -> np.ndarray:
    torch = _safe_import_torch()
    if torch is None:
        raise RuntimeError("PyTorch is required for gradient-based saliency maps")

    model.eval()
    tensor = torch.tensor(input_signal.astype(np.float32)[None, None, :], requires_grad=True)
    output = model(tensor)
    if target_index is None:
        if output.numel() == 0:
            raise ValueError('Model output empty — no se puede calcular saliency target.')
        target_index = int(output.argmax(dim=-1).item())
    score = output[0, target_index]
    score.backward(retain_graph=False)
    saliency = tensor.grad.abs().squeeze().cpu().numpy()
    return normalize_importance(saliency)


def feature_importance_from_coefficients(model: Any, feature_names: Optional[List[str]] = None) -> Dict[str, float]:
    coefficients = None
    if hasattr(model, 'coef_'):
        coefficients = getattr(model, 'coef_')
    elif hasattr(model, 'feature_importances_'):
        coefficients = getattr(model, 'feature_importances_')
    else:
        raise ValueError('El modelo no expone coeficientes ni feature_importances_')

    coefficients = np.asarray(coefficients, dtype=float).flatten()
    normalized = normalize_importance(np.abs(coefficients))
    if feature_names is None:
        feature_names = [f'feature_{i}' for i in range(len(normalized))]
    return {name: float(value) for name, value in zip(feature_names, normalized.tolist())}


def permutation_feature_importance(
    predict_fn: Callable[[np.ndarray], np.ndarray],
    X: np.ndarray,
    y: Optional[np.ndarray] = None,
    n_repeats: int = 5,
    random_state: Optional[int] = None,
    scoring: Optional[Callable[[np.ndarray, np.ndarray], float]] = None,
) -> Dict[str, float]:
    if scoring is None:
        def scoring(y_true: np.ndarray, y_pred: np.ndarray) -> float:
            return float(np.mean(y_true == y_pred)) if y_true is not None else 0.0

    rng = np.random.default_rng(random_state)
    baseline_pred = predict_fn(X)
    if y is None:
        y = baseline_pred
    baseline_score = scoring(y, baseline_pred)

    importances = np.zeros(X.shape[1], dtype=float)
    for feature_idx in range(X.shape[1]):
        scores = []
        for _ in range(n_repeats):
            X_permuted = X.copy()
            rng.shuffle(X_permuted[:, feature_idx])
            pred = predict_fn(X_permuted)
            scores.append(scoring(y, pred))
        importances[feature_idx] = baseline_score - float(np.mean(scores))

    normalized = normalize_importance(importances)
    return {f'feature_{i}': float(normalized[i]) for i in range(X.shape[1])}


def lime_like_explanation(
    predict_fn: Callable[[np.ndarray], np.ndarray],
    input_sample: np.ndarray,
    feature_groups: int = 10,
    n_samples: int = 200,
    perturbation_strength: float = 0.1,
    random_state: Optional[int] = None,
) -> Dict[str, float]:
    rng = np.random.default_rng(random_state)
    input_sample = np.asarray(input_sample, dtype=float).flatten()
    n_features = len(input_sample)
    group_size = max(1, n_features // feature_groups)

    def make_perturbation(mask: np.ndarray) -> np.ndarray:
        noise = rng.normal(scale=perturbation_strength, size=n_features)
        perturbed = input_sample.copy()
        perturbed[mask == 0] = noise[mask == 0]
        return perturbed

    masks = rng.integers(0, 2, size=(n_samples, n_features), dtype=np.int8)
    predictions = []
    for mask in masks:
        sample = make_perturbation(mask)
        prediction = predict_fn(sample[None, :])
        predictions.append(float(prediction.ravel()[0]))

    predictions = np.asarray(predictions, dtype=float)
    weights = np.zeros(n_features, dtype=float)
    for feature_idx in range(n_features):
        contribution = np.mean(predictions[masks[:, feature_idx] == 1]) - np.mean(predictions[masks[:, feature_idx] == 0])
        weights[feature_idx] = contribution

    normalized = normalize_importance(weights)
    return {f'feature_{i}': float(normalized[i]) for i in range(n_features)}


def safe_predict_function(model: Any, X: np.ndarray) -> np.ndarray:
    if hasattr(model, 'predict'):
        return np.asarray(model.predict(X))
    if hasattr(model, '__call__'):
        return np.asarray(model(X))
    raise ValueError('El modelo no es predecible con predict() ni __call__()')
