"""Compatibility layer providing the API expected by the application.

This module exposes:
- ArrhythmiaClass, ModelType
- ClassificationResult
- FeatureExtraction
- BeatSegmentation
- ArrhythmiaInference

Internally it uses the simpler `biomedical.arrhythmia_classifier.ArrhythmiaClassifier`
for class names/descriptions and model storage.
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import numpy as np
import os
import pickle
import logging

from .arrhythmia_classifier import ArrhythmiaClassifier

logger = logging.getLogger(__name__)


class ArrhythmiaClass(Enum):
    NORMAL = 0
    PVC = 1
    PAC = 2
    AFIB = 3
    LBBB = 4
    RBBB = 5
    VT = 6
    ATRIAL_FLUTTER = 7


class ModelType(Enum):
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"


@dataclass
class ClassificationResult:
    predicted_class: ArrhythmiaClass
    confidence: float
    probabilities: Dict[str, float]
    features_used: int
    model_type: ModelType
    timestamp: datetime

    def to_dict(self):
        return {
            'predicted_class': self.predicted_class.name,
            'confidence': float(self.confidence),
            'probabilities': {k: float(v) for k, v in self.probabilities.items()},
            'features_used': self.features_used,
            'model_type': self.model_type.value,
            'timestamp': self.timestamp.isoformat(),
        }

    def to_json(self):
        import json

        return json.dumps(self.to_dict(), indent=2)


class FeatureExtraction:
    def __init__(self, sampling_rate: int = 360):
        self.sampling_rate = sampling_rate

    def extract_all_features(self, beat: np.ndarray) -> List[float]:
        x = np.asarray(beat, dtype=float)
        if x.size == 0:
            return [0.0] * 8
        feats = [
            float(np.mean(x)),
            float(np.std(x)),
            float(np.max(x) - np.min(x)),
            float(np.max(x)),
            float(np.min(x)),
            float(np.sum(x ** 2)),
            float(np.median(x)),
            float(np.sum(np.histogram(x, bins=32, density=True)[0] * np.log2(np.clip(np.histogram(x, bins=32, density=True)[0], 1e-8, None)))) if x.size>0 else 0.0,
        ]
        return feats


class BeatSegmentation:
    def __init__(self, sampling_rate: int = 360, beat_length_ms: int = 600):
        self.sampling_rate = sampling_rate
        self.beat_length = int((beat_length_ms / 1000.0) * sampling_rate)

    def detect_r_peaks(self, signal: np.ndarray) -> List[int]:
        x = np.asarray(signal, dtype=float)
        if x.size == 0:
            return []
        mean = x.mean()
        std = x.std()
        threshold = mean + 0.5 * std
        peaks = []
        for i in range(1, len(x) - 1):
            if x[i] > x[i - 1] and x[i] > x[i + 1] and x[i] > threshold:
                peaks.append(i)
        return peaks

    def segment_ecg(self, signal: np.ndarray) -> Tuple[List[np.ndarray], List[int]]:
        r_peaks = self.detect_r_peaks(signal)
        beats = []
        half = self.beat_length // 2
        for r in r_peaks:
            start = max(0, r - half)
            end = min(len(signal), r + half)
            beats.append(signal[start:end])
        return beats, r_peaks


class ArrhythmiaInference:
    def __init__(self, model_path: Optional[str] = None, model_type: ModelType = ModelType.RANDOM_FOREST, sampling_rate: int = 360):
        self.model_type = model_type
        self.sampling_rate = sampling_rate
        self.model = None
        self.beat_segmentation = BeatSegmentation(sampling_rate=sampling_rate)
        self.feature_extraction = FeatureExtraction(sampling_rate=sampling_rate)
        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str):
        if not os.path.exists(str(model_path)):
            raise FileNotFoundError(f"Model not found at {model_path}")
        with open(str(model_path), 'rb') as f:
            self.model = pickle.load(f)

    def predict_single_beat(self, beat: np.ndarray) -> ClassificationResult:
        if self.model is None:
            raise ValueError("No model loaded. Call load_model() first.")
        features = self.feature_extraction.extract_all_features(beat)
        import numpy as _np
        X = _np.array([features])
        if hasattr(self.model, 'predict'):
            y_pred = int(self.model.predict(X)[0])
        else:
            y_pred = 0
        y_proba = self.model.predict_proba(X)[0] if hasattr(self.model, 'predict_proba') else None
        confidence = float(y_proba.max()) if y_proba is not None else 1.0
        if y_proba is not None:
            probabilities = {ArrhythmiaClass(i).name: float(prob) for i, prob in enumerate(y_proba)}
        else:
            probabilities = {ArrhythmiaClass(y_pred).name: 1.0}
        return ClassificationResult(predicted_class=ArrhythmiaClass(int(y_pred)), confidence=confidence, probabilities=probabilities, features_used=len(features), model_type=self.model_type, timestamp=datetime.now())

    def predict_ecg_signal(self, signal: np.ndarray, return_beat_predictions: bool = False) -> Any:
        beats, r_peaks = self.beat_segmentation.segment_ecg(signal)
        if not beats:
            raise ValueError("No beats detected in signal")
        beat_results = []
        class_votes = {}
        for i, beat in enumerate(beats):
            try:
                res = self.predict_single_beat(beat)
                beat_results.append({'beat_index': i, 'r_peak': int(r_peaks[i]) if i < len(r_peaks) else None, 'predicted_class': res.predicted_class.name, 'confidence': res.confidence, 'probabilities': res.probabilities})
                class_votes[res.predicted_class.name] = class_votes.get(res.predicted_class.name, 0) + res.confidence
            except Exception as e:
                logger.warning(f"Error classifying beat {i}: {e}")
        if class_votes:
            overall_class_name = max(class_votes, key=class_votes.get)
            overall_class = ArrhythmiaClass[overall_class_name]
            overall_confidence = class_votes[overall_class_name] / len(beats)
        else:
            overall_class = ArrhythmiaClass.NORMAL
            overall_confidence = 0.0
        overall_result = ClassificationResult(predicted_class=overall_class, confidence=overall_confidence, probabilities={k: v / len(beats) for k, v in class_votes.items()}, features_used=len(beat_results), model_type=self.model_type, timestamp=datetime.now())
        if return_beat_predictions:
            return {'overall_result': overall_result, 'beat_predictions': beat_results, 'total_beats': len(beats)}
        return overall_result

    def predict_batch(self, beat_list: List[np.ndarray]) -> List[ClassificationResult]:
        results = []
        for i, beat in enumerate(beat_list):
            try:
                res = self.predict_single_beat(beat)
                results.append(res)
            except Exception as e:
                logger.warning(f"Error classifying beat {i}: {e}")
        return results

    def get_prediction_summary(self, result: ClassificationResult) -> Dict:
        classifier = ArrhythmiaClassifier()
        predicted_class = result.predicted_class
        summary = {
            'predicted_class': predicted_class.name,
            'class_name': classifier.get_class_name(predicted_class),
            'description': classifier.get_class_description(predicted_class),
            'confidence': f"{result.confidence * 100:.1f}%",
            'model_used': result.model_type.value,
            'timestamp': result.timestamp.isoformat(),
            'top_3_candidates': sorted(result.probabilities.items(), key=lambda x: x[1], reverse=True)[:3],
        }
        return summary

    def validate_and_predict(self, signal: np.ndarray) -> Tuple[bool, Any]:
        if signal is None or len(signal) == 0:
            return False, "Signal is empty"
        if not np.isfinite(signal).all():
            return False, "Signal contains NaN or infinite values"
        if len(signal) < 360:
            return False, "Signal too short (minimum 1 second)"
        try:
            result = self.predict_ecg_signal(signal)
            return True, result
        except Exception as e:
            return False, f"Prediction error: {str(e)}"
