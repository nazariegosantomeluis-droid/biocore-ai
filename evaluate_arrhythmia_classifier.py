"""
Evaluation Script - Arrhythmia Classifier

Evaluates trained models on test data with comprehensive metrics.
Generates confusion matrices and performance reports.

Usage:
    python evaluate_arrhythmia_classifier.py
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from biomedical.arrhythmia_classifier import (
    ArrhythmiaClassifier,
    FeatureExtraction,
    ArrhythmiaModelTrainer,
    ModelEvaluator,
    ModelType,
)
from train_arrhythmia_classifier import generate_synthetic_beats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def evaluate_models():
    """Complete evaluation pipeline."""
    logger.info("\n")
    logger.info("╔" + "="*58 + "╗")
    logger.info("║" + " ARRHYTHMIA CLASSIFIER - EVALUATION ".center(58) + "║")
    logger.info("╚" + "="*58 + "╝\n")
    
    # Initialize
    classifier = ArrhythmiaClassifier()
    evaluator = ModelEvaluator()
    feature_extractor = FeatureExtraction(sampling_rate=360)
    trainer = ArrhythmiaModelTrainer()
    
    # Generate test data
    logger.info("Generating test data...")
    beats_test, labels_test = generate_synthetic_beats(num_samples_per_class=25)
    
    # Extract features
    X_test = feature_extractor.extract_features_batch(beats_test)
    y_test = labels_test
    
    # Normalize using the same scaler
    if trainer.scaler:
        X_test_normalized = pd.DataFrame(
            trainer.scaler.fit_transform(X_test),
            columns=X_test.columns
        )
    else:
        X_test_normalized = X_test
    
    logger.info(f"Test set: {len(y_test)} samples, {X_test.shape[1]} features\n")
    
    # Load and evaluate models
    evaluations = {}
    
    logger.info("="*60)
    logger.info("LOADING AND EVALUATING MODELS")
    logger.info("="*60 + "\n")
    
    for model_type in ModelType:
        model = classifier.load_model(model_type)
        
        if model is None:
            logger.warning(f"{model_type.value} not found, skipping...")
            continue
        
        # Evaluate
        evaluation = evaluator.evaluate_model(
            model, X_test_normalized, y_test,
            model_name=model_type.value
        )
        evaluations[model_type.value] = evaluation
        
        # Store metrics in classifier
        from biomedical.arrhythmia_classifier import ModelMetrics
        metrics = ModelMetrics(
            accuracy=evaluation['accuracy'],
            precision={k: v for k, v in evaluation['precision']['per_class'].items()},
            recall={k: v for k, v in evaluation['recall']['per_class'].items()},
            f1={k: v for k, v in evaluation['f1']['per_class'].items()},
            macro_avg=evaluation['precision'] | evaluation['recall'] | evaluation['f1'],
            weighted_avg={},
        )
        classifier.metrics[model_type] = metrics
        classifier.save_metrics(metrics, model_type)
    
    # Model comparison
    if evaluations:
        logger.info("\n" + "="*60)
        comparison_df = evaluator.compare_models(evaluations)
        logger.info(comparison_df.to_string(index=False))
        logger.info("="*60 + "\n")
        
        # Save comparison
        comparison_df.to_csv(
            classifier.model_dir / "model_comparison.csv",
            index=False
        )
        logger.info(f"Comparison saved to {classifier.model_dir / 'model_comparison.csv'}\n")
    
    # Detailed reports for best model
    if evaluations:
        best_model_name = max(evaluations.keys(),
                            key=lambda x: evaluations[x]['accuracy'])
        best_evaluation = evaluations[best_model_name]
        
        logger.info("="*60)
        logger.info(f"DETAILED REPORT - {best_model_name.upper()}")
        logger.info("="*60)
        
        # Per-class metrics
        logger.info("\nPER-CLASS METRICS:")
        per_class_df = evaluator.get_per_class_metrics(best_evaluation)
        logger.info(per_class_df.to_string(index=False))
        
        # Confusion matrix
        logger.info("\nCONFUSION MATRIX:")
        cm_df = evaluator.get_confusion_matrix_df(
            np.array(best_evaluation['confusion_matrix'])
        )
        logger.info(cm_df)
        
        # Save confusion matrix
        cm_df.to_csv(
            classifier.model_dir / f"{best_model_name}_confusion_matrix.csv"
        )
        
        # Print classification report
        evaluator.print_classification_report(best_evaluation, best_model_name)
        
        logger.info("="*60 + "\n")
    
    # Export summary
    logger.info("Exporting summary...")
    summary_path = classifier.model_dir / f"evaluation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    classifier.export_summary(summary_path)
    
    logger.info("\n✅ EVALUATION COMPLETED SUCCESSFULLY\n")
    
    return evaluations, classifier


def generate_confusion_matrix_plot(evaluation, model_name, output_path=None):
    """Generate and save confusion matrix plot."""
    cm = np.array(evaluation['confusion_matrix'])
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=['Normal', 'PVC', 'PAC', 'AFib', 'LBBB', 'RBBB', 'VT', 'AFL'],
                yticklabels=['Normal', 'PVC', 'PAC', 'AFib', 'LBBB', 'RBBB', 'VT', 'AFL'])
    plt.title(f'Confusion Matrix - {model_name}')
    plt.ylabel('Actual')
    plt.xlabel('Predicted')
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved confusion matrix to {output_path}")
    
    plt.close()


if __name__ == "__main__":
    try:
        evaluations, classifier = evaluate_models()
        
        # Generate plots
        logger.info("\nGenerating visualizations...")
        for model_name, evaluation in evaluations.items():
            plot_path = classifier.model_dir / f"{model_name}_confusion_matrix.png"
            generate_confusion_matrix_plot(evaluation, model_name, plot_path)
        
        logger.info("\n" + "="*60)
        logger.info("EVALUATION RESULTS")
        logger.info("="*60)
        logger.info(f"Models evaluated: {len(evaluations)}")
        if evaluations:
            best_model = max(evaluations.items(),
                           key=lambda x: x[1]['accuracy'])
            logger.info(f"Best model: {best_model[0]} (Accuracy: {best_model[1]['accuracy']:.4f})")
        logger.info("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        sys.exit(1)
