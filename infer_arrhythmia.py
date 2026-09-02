"""
Inference Script - Arrhythmia Classifier

Demonstrates real-time inference on ECG signals.
Shows single beat prediction and full signal analysis.

Usage:
    python infer_arrhythmia.py
"""

import sys
from pathlib import Path
import numpy as np
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from biomedical.arrhythmia_classifier import (
    ArrhythmiaInference,
    BeatSegmentation,
    ModelType,
    ArrhythmiaClassifier,
)
from train_arrhythmia_classifier import generate_synthetic_beats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_synthetic_ecg_signal(duration: float = 5.0, sampling_rate: int = 360) -> np.ndarray:
    """
    Generate synthetic ECG signal.
    
    Args:
        duration: Duration in seconds
        sampling_rate: Sampling rate in Hz
        
    Returns:
        ECG signal array
    """
    num_samples = int(duration * sampling_rate)
    t = np.linspace(0, duration, num_samples)
    
    # Heart rate 70 BPM
    heart_rate = 70
    freq = heart_rate / 60
    
    # Create several beats
    signal = []
    for i in range(int(duration * freq)):
        # Create a normal beat template
        beat_duration = 60 / heart_rate
        beat_samples = int(beat_duration * sampling_rate)
        beat_t = np.linspace(0, 1, beat_samples)
        
        # Standard PQRST complex
        p_wave = 0.1 * np.exp(-((beat_t - 0.2) ** 2) / 0.01)
        q_wave = -0.1 * np.exp(-((beat_t - 0.45) ** 2) / 0.001)
        r_wave = 1.0 * np.exp(-((beat_t - 0.5) ** 2) / 0.002)
        s_wave = -0.3 * np.exp(-((beat_t - 0.55) ** 2) / 0.002)
        t_wave = 0.2 * np.exp(-((beat_t - 0.75) ** 2) / 0.03)
        
        beat = p_wave + q_wave + r_wave + s_wave + t_wave
        beat += np.random.normal(0, 0.03, len(beat))
        
        signal.extend(beat)
    
    return np.array(signal[:num_samples])


def run_inference_demo():
    """Run complete inference demonstration."""
    logger.info("\n")
    logger.info("╔" + "="*58 + "╗")
    logger.info("║" + " ARRHYTHMIA CLASSIFIER - INFERENCE ".center(58) + "║")
    logger.info("╚" + "="*58 + "╝\n")
    
    classifier = ArrhythmiaClassifier()
    sampling_rate = 360
    
    # Check available models
    available_models = []
    for model_type in ModelType:
        model_path = classifier.model_dir / f"{model_type.value}_model.pkl"
        if model_path.exists():
            available_models.append(model_type)
            logger.info(f"✓ Found {model_type.value} model")
    
    if not available_models:
        logger.error("No trained models found!")
        logger.info("Run: python train_arrhythmia_classifier.py")
        return False
    
    # Use the first available model
    selected_model_type = available_models[0]
    logger.info(f"\nUsing model: {selected_model_type.value}\n")
    
    # Initialize inference engine
    model_path = classifier.model_dir / f"{selected_model_type.value}_model.pkl"
    inference_engine = ArrhythmiaInference(
        model_path=model_path,
        model_type=selected_model_type,
        sampling_rate=sampling_rate
    )
    
    # Test 1: Single beat prediction
    logger.info("="*60)
    logger.info("TEST 1: SINGLE BEAT CLASSIFICATION")
    logger.info("="*60)
    
    logger.info("\nGenerating test beats...")
    beats, labels = generate_synthetic_beats(num_samples_per_class=5)
    
    for i in range(min(3, len(beats))):
        beat = beats[i]
        true_label = labels[i]
        
        result = inference_engine.predict_single_beat(beat)
        summary = inference_engine.get_prediction_summary(result)
        
        logger.info(f"\nBeat {i+1}:")
        logger.info(f"  True class: {true_label}")
        logger.info(f"  Predicted: {summary['class_name']}")
        logger.info(f"  Confidence: {summary['confidence']}")
        logger.info(f"  Description: {summary['description']}")
        logger.info(f"  Top candidates:")
        for class_name, prob in summary['top_3_candidates']:
            logger.info(f"    - {class_name}: {prob*100:.1f}%")
    
    logger.info("\n" + "="*60)
    
    # Test 2: ECG signal analysis
    logger.info("TEST 2: FULL ECG SIGNAL ANALYSIS")
    logger.info("="*60)
    
    logger.info("\nGenerating 5-second ECG signal...")
    ecg_signal = generate_synthetic_ecg_signal(duration=5.0, sampling_rate=sampling_rate)
    logger.info(f"Signal shape: {ecg_signal.shape}")
    logger.info(f"Signal range: [{np.min(ecg_signal):.3f}, {np.max(ecg_signal):.3f}]\n")
    
    # Full analysis with beat-level predictions
    result_with_beats = inference_engine.predict_ecg_signal(
        ecg_signal,
        return_beat_predictions=True
    )
    
    overall_result = result_with_beats['overall_result']
    beat_predictions = result_with_beats['beat_predictions']
    
    summary = inference_engine.get_prediction_summary(overall_result)
    
    logger.info("OVERALL CLASSIFICATION:")
    logger.info(f"  Predicted class: {summary['class_name']}")
    logger.info(f"  Confidence: {summary['confidence']}")
    logger.info(f"  Total beats analyzed: {result_with_beats['total_beats']}")
    logger.info(f"\nBeat-level predictions:")
    logger.info(f"{'Beat':<6} {'Predicted':<20} {'Confidence':<12}")
    logger.info("-" * 38)
    
    for beat_pred in beat_predictions[:min(5, len(beat_predictions))]:
        beat_idx = beat_pred['beat_index']
        class_name = beat_pred['predicted_class']
        confidence = beat_pred['confidence']
        logger.info(f"{beat_idx:<6} {class_name:<20} {confidence*100:>10.1f}%")
    
    if len(beat_predictions) > 5:
        logger.info(f"... and {len(beat_predictions) - 5} more beats")
    
    logger.info("\n" + "="*60)
    
    # Test 3: Batch processing
    logger.info("TEST 3: BATCH PROCESSING")
    logger.info("="*60)
    
    logger.info("\nProcessing batch of beats...")
    batch_size = 10
    beats_batch = beats[:batch_size]
    
    results_batch = inference_engine.predict_batch(beats_batch)
    
    logger.info(f"Processed {len(results_batch)} beats\n")
    logger.info(f"{'Index':<6} {'Class':<20} {'Confidence':<12}")
    logger.info("-" * 38)
    
    for i, result in enumerate(results_batch):
        logger.info(f"{i:<6} {result.predicted_class.name:<20} {result.confidence*100:>10.1f}%")
    
    logger.info("\n" + "="*60)
    
    # Test 4: Input validation
    logger.info("TEST 4: INPUT VALIDATION")
    logger.info("="*60)
    
    test_cases = [
        ("Normal signal", generate_synthetic_ecg_signal(duration=3.0)),
        ("Short signal", np.array([1, 2, 3, 4, 5])),
        ("Empty signal", np.array([])),
        ("Signal with NaN", np.concatenate([ecg_signal, [np.nan]])),
    ]
    
    for test_name, test_signal in test_cases:
        success, result = inference_engine.validate_and_predict(test_signal)
        
        if success:
            logger.info(f"✓ {test_name}: {result.predicted_class.name} (confidence: {result.confidence*100:.1f}%)")
        else:
            logger.info(f"✗ {test_name}: {result}")
    
    logger.info("\n" + "="*60)
    
    # Test 5: Export predictions
    logger.info("TEST 5: EXPORTING PREDICTIONS")
    logger.info("="*60)
    
    result = inference_engine.predict_single_beat(beats[0])
    result_dict = result.to_dict()
    result_json = result.to_json()
    
    logger.info("\nPrediction as dictionary:")
    logger.info(str(result_dict)[:200] + "...")
    
    logger.info("\nPrediction as JSON:")
    logger.info(result_json[:300] + "...")
    
    logger.info("\n" + "="*60 + "\n")
    
    return True


if __name__ == "__main__":
    try:
        success = run_inference_demo()
        
        if success:
            logger.info("✅ INFERENCE DEMO COMPLETED SUCCESSFULLY\n")
        else:
            logger.error("Inference demo failed\n")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Inference demo failed: {e}", exc_info=True)
        sys.exit(1)
