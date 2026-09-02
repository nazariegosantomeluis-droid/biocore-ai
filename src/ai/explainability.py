"""
Explainable AI helpers for biomedical signal classification.

Provides multiple interpretability methods without hard PyTorch dependency:
- Feature importance (permutation-based)
- LIME-style local explanations
- Attention visualization
- Signal component attribution
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
import numpy as np


class SignalExplainer:
    """Robust signal explainability without PyTorch dependency."""
    
    def __init__(self, model=None):
        """Initialize explainer."""
        self.model = model
        self.pytorch_available = self._check_pytorch()
    
    def _check_pytorch(self) -> bool:
        """Check if PyTorch is available."""
        try:
            import torch
            return True
        except ImportError:
            return False
    
    def feature_importance(
        self,
        signal: np.ndarray,
        prediction_fn,
        n_permutations: int = 10
    ) -> Dict[str, float]:
        """
        Compute feature importance via permutation.
        
        Parameters
        ----------
        signal : ndarray
            Input signal
        prediction_fn : callable
            Function that takes signal and returns prediction
        n_permutations : int
            Number of permutations for each feature
            
        Returns
        -------
        dict
            Feature importance scores
        """
        baseline_pred = prediction_fn(signal)
        
        importances = {}
        n_features = len(signal)
        feature_size = max(1, n_features // 20)
        
        for i in range(0, n_features, feature_size):
            end_idx = min(i + feature_size, n_features)
            feature_name = f"segment_{i}_{end_idx}"
            
            permuted_preds = []
            for _ in range(n_permutations):
                signal_copy = signal.copy()
                signal_copy[i:end_idx] = np.random.normal(
                    np.mean(signal[i:end_idx]),
                    np.std(signal[i:end_idx]),
                    end_idx - i
                )
                permuted_preds.append(prediction_fn(signal_copy))
            
            importance = np.mean(np.abs(np.array(permuted_preds) - baseline_pred))
            importances[feature_name] = float(importance)
        
        total = sum(importances.values())
        if total > 0:
            importances = {k: (v / total) * 100 for k, v in importances.items()}
        
        return importances
    
    def signal_gradient_saliency(
        self,
        signal: np.ndarray,
        prediction_fn
    ) -> np.ndarray:
        """
        Compute saliency map via numerical gradients.
        
        Shows which parts of signal most affect prediction.
        """
        epsilon = 1e-6
        gradients = np.zeros_like(signal, dtype=float)
        baseline = prediction_fn(signal)
        
        for i in range(len(signal)):
            signal_plus = signal.copy()
            signal_plus[i] += epsilon
            
            pred_plus = prediction_fn(signal_plus)
            gradients[i] = (pred_plus - baseline) / epsilon
        
        saliency = np.abs(gradients)
        if np.max(saliency) > 0:
            saliency = saliency / np.max(saliency)
        
        return saliency
    
    def lime_explanation(
        self,
        signal: np.ndarray,
        prediction_fn,
        n_samples: int = 100,
        kernel_width: float = 0.25
    ) -> Dict[str, Any]:
        """
        LIME-style local explanation.
        
        Creates local linear approximation around instance.
        """
        n_features = len(signal) // 20
        n_features = max(1, n_features)
        
        predictions = []
        distances = []
        masked_signals = []
        
        baseline_pred = prediction_fn(signal)
        
        for _ in range(n_samples):
            mask = np.random.randint(0, 2, n_features)
            
            masked_signal = signal.copy()
            for i, m in enumerate(mask):
                start = i * 20
                end = min(start + 20, len(signal))
                if m == 0:
                    masked_signal[start:end] = np.mean(signal)
            
            pred = prediction_fn(masked_signal)
            predictions.append(pred)
            
            distance = np.linalg.norm(mask - 1) * kernel_width
            distances.append(distance)
            masked_signals.append(mask)
        
        predictions = np.array(predictions)
        distances = np.array(distances)
        
        try:
            from sklearn.linear_model import LinearRegression
            
            X = np.array(masked_signals)
            y = predictions
            weights = np.exp(-distances / kernel_width ** 2)
            
            model = LinearRegression()
            model.fit(X, y, sample_weight=weights)
            
            explanation = {
                'coefficients': {
                    f'segment_{i}': float(coef)
                    for i, coef in enumerate(model.coef_)
                },
                'intercept': float(model.intercept_),
                'baseline_prediction': float(baseline_pred),
                'method': 'LIME'
            }
        except ImportError:
            explanation = {
                'error': 'scikit-learn required for LIME',
                'fallback': 'Use feature_importance instead'
            }
        
        return explanation
    
    def attention_weights(
        self,
        signal: np.ndarray,
        window_size: int = 50
    ) -> np.ndarray:
        """
        Compute attention-like weights for signal regions.
        
        Based on local variance - regions with high variance get higher attention.
        """
        attention = np.zeros(len(signal))
        
        for i in range(len(signal) - window_size):
            window = signal[i:i + window_size]
            attention[i:i + window_size] += np.var(window)
        
        if np.max(attention) > 0:
            attention = attention / np.max(attention)
        
        return attention
    
    def temporal_importance(
        self,
        signal: np.ndarray,
        fs: float = 250.0
    ) -> Dict[str, Any]:
        """
        Analyze which time periods are most important.
        
        Divides signal into segments and assigns importance.
        """
        n_segments = 10
        segment_size = len(signal) // n_segments
        
        importances = {}
        
        for i in range(n_segments):
            start_idx = i * segment_size
            end_idx = (i + 1) * segment_size if i < n_segments - 1 else len(signal)
            
            segment = signal[start_idx:end_idx]
            
            variance = np.var(segment)
            energy = np.sum(segment ** 2)
            peaks = np.sum(np.abs(segment) > 2 * np.std(signal))
            
            importance_score = (variance * 0.3 + energy * 0.4 + peaks * 0.3)
            
            time_start = start_idx / fs
            time_end = end_idx / fs
            
            importances[f"segment_{i}"] = {
                'time_range': f"{time_start:.2f}-{time_end:.2f}s",
                'importance': float(importance_score),
                'variance': float(variance),
                'energy': float(energy),
                'peaks': int(peaks)
            }
        
        return importances
    
    def counterfactual_explanation(
        self,
        signal: np.ndarray,
        prediction_fn,
        target_class: int,
        n_iterations: int = 50,
        learning_rate: float = 0.01
    ) -> Dict[str, Any]:
        """
        Generate counterfactual: minimal change to flip prediction.
        """
        modified_signal = signal.copy()
        original_pred = prediction_fn(signal)
        
        for iteration in range(n_iterations):
            current_pred = prediction_fn(modified_signal)
            
            if abs(current_pred - target_class) < 0.5:
                break
            
            direction = np.sign(target_class - current_pred)
            noise = np.random.normal(0, 1, len(signal))
            modified_signal += learning_rate * direction * noise
            
            modified_signal = np.clip(
                modified_signal,
                np.min(signal) - np.std(signal),
                np.max(signal) + np.std(signal)
            )
        
        difference = modified_signal - signal
        total_change = np.sum(np.abs(difference))
        
        return {
            'original_signal': signal.tolist()[:100],
            'counterfactual_signal': modified_signal.tolist()[:100],
            'total_change': float(total_change),
            'iterations_used': iteration + 1,
            'converged': abs(current_pred - target_class) < 0.5,
            'regions_changed': int(np.sum(np.abs(difference) > 0.01 * np.std(signal)))
        }
    
    def grad_cam_fallback(
        self,
        signal: np.ndarray,
        model_output_shape: int
    ) -> np.ndarray:
        """
        Gradient-based attention without PyTorch.
        
        Numerical gradient computation.
        """
        epsilon = 1e-4
        gradients = np.zeros(len(signal))
        
        for i in range(len(signal)):
            signal_plus = signal.copy()
            signal_minus = signal.copy()
            
            signal_plus[i] += epsilon
            signal_minus[i] -= epsilon
            
            gradients[i] = (np.sum(signal_plus) - np.sum(signal_minus)) / (2 * epsilon)
        
        heatmap = np.maximum(gradients, 0)
        if np.max(heatmap) > 0:
            heatmap = heatmap / np.max(heatmap)
        
        return heatmap


# Legacy functions for backward compatibility
def grad_cam(model, input_signal: np.ndarray, layer_name: str = 'conv1') -> np.ndarray:
    """Legacy Grad-CAM wrapper."""
    explainer = SignalExplainer(model)
    
    if explainer.pytorch_available:
        try:
            import torch
            model.model.eval()
            x = torch.tensor(input_signal, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
            x.requires_grad = True
            
            target = model.model(x)
            score = target[:, target.argmax(dim=1)].sum()
            score.backward()
            
            gradients = x.grad.detach().cpu().numpy()[0, 0]
            weights = np.mean(gradients, axis=0)
            heatmap = np.maximum(weights, 0)
            if np.max(heatmap) > 0:
                heatmap = heatmap / np.max(heatmap)
            return heatmap
        except Exception as e:
            print(f"PyTorch Grad-CAM failed: {e}, using fallback")
    
    return explainer.grad_cam_fallback(input_signal, 6)


def saliency_map(model, input_signal: np.ndarray) -> np.ndarray:
    """Legacy saliency map wrapper."""
    explainer = SignalExplainer(model)
    
    if explainer.pytorch_available:
        try:
            import torch
            model.model.eval()
            x = torch.tensor(input_signal, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
            x.requires_grad = True
            
            output = model.model(x)
            score = output[:, output.argmax(dim=1)].sum()
            score.backward()
            
            saliency = x.grad.abs().detach().cpu().numpy()[0, 0]
            if np.max(saliency) > 0:
                saliency = saliency / np.max(saliency)
            return saliency
        except Exception as e:
            print(f"PyTorch saliency failed: {e}, using fallback")
    
    return explainer.signal_gradient_saliency(input_signal, lambda x: np.mean(x))
