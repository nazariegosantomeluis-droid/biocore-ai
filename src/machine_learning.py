"""
Machine Learning Module for Arrhythmia Classification

Trains and evaluates Logistic Regression models for binary classification:
- Class 0: Normal sinus rhythm
- Class 1: Abnormal rhythm (arrhythmia)

Features used:
    BPM, SDNN, RMSSD, LF_HF, Skewness, Kurtosis
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve
)


class ArrhythmiaClassifier:
    """
    Logistic Regression classifier for cardiac arrhythmia detection.
    
    Attributes
    ----------
    model : LogisticRegression
        Trained logistic regression model
    scaler : StandardScaler
        Feature scaler for normalization
    feature_names : list
        Names of input features
    """
    
    def __init__(self):
        """Initialize the classifier."""
        self.model = LogisticRegression(
            random_state=42,
            max_iter=1000,
            class_weight='balanced'  # Handle imbalanced classes
        )
        self.scaler = StandardScaler()
        self.feature_names = [
            'BPM', 'SDNN', 'RMSSD', 'LF_HF', 'Skewness', 'Kurtosis'
        ]
        self.is_fitted = False
    
    def fit(self, X_train, y_train):
        """
        Fit the classifier to training data.
        
        Parameters
        ----------
        X_train : ndarray or DataFrame
            Training features (n_samples, 6)
        y_train : ndarray
            Training labels (0=normal, 1=arrhythmia)
        """
        # Scale features
        X_scaled = self.scaler.fit_transform(X_train)
        
        # Train model
        self.model.fit(X_scaled, y_train)
        self.is_fitted = True
    
    def predict(self, X):
        """
        Predict class labels (0 or 1).
        
        Parameters
        ----------
        X : ndarray or DataFrame
            Features (n_samples, 6)
            
        Returns
        -------
        predictions : ndarray
            Predicted labels (0=normal, 1=arrhythmia)
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X):
        """
        Predict class probabilities.
        
        Parameters
        ----------
        X : ndarray or DataFrame
            Features (n_samples, 6)
            
        Returns
        -------
        probabilities : ndarray
            Probability estimates [P(normal), P(arrhythmia)]
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    def evaluate(self, X_test, y_test):
        """
        Evaluate model performance on test set.
        
        Parameters
        ----------
        X_test : ndarray or DataFrame
            Test features
        y_test : ndarray
            Test labels
            
        Returns
        -------
        metrics : dict
            Dictionary of performance metrics
        """
        predictions = self.predict(X_test)
        probabilities = self.predict_proba(X_test)
        
        metrics = {
            'accuracy': accuracy_score(y_test, predictions),
            'precision': precision_score(y_test, predictions),
            'recall': recall_score(y_test, predictions),
            'f1': f1_score(y_test, predictions),
            'roc_auc': roc_auc_score(y_test, probabilities[:, 1]),
            'confusion_matrix': confusion_matrix(y_test, predictions),
            'classification_report': classification_report(y_test, predictions)
        }
        
        return metrics


def train_model(df, test_size=0.25, random_state=42):
    """
    Train arrhythmia classifier on dataset.
    
    Parameters
    ----------
    df : DataFrame
        Dataset containing features and labels
        Columns: ['BPM', 'SDNN', 'RMSSD', 'LF_HF', 'Skewness', 'Kurtosis', 'Label']
    test_size : float, optional
        Fraction of data for testing. Default: 0.25
    random_state : int, optional
        Random seed. Default: 42
        
    Returns
    -------
    model : ArrhythmiaClassifier
        Trained classifier
    metrics : dict
        Performance metrics on test set
    """
    
    # Extract features and labels
    X = df[[
        'BPM', 'SDNN', 'RMSSD', 'LF_HF', 'Skewness', 'Kurtosis'
    ]].values
    
    y = df['Label'].values
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=random_state,
        stratify=y  # Maintain class distribution
    )
    
    # Train classifier
    classifier = ArrhythmiaClassifier()
    classifier.fit(X_train, y_train)
    
    # Evaluate
    metrics = classifier.evaluate(X_test, y_test)
    
    # Print results
    print("\n" + "="*60)
    print("MODEL PERFORMANCE METRICS")
    print("="*60)
    print(f"Accuracy:  {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall:    {metrics['recall']:.4f}")
    print(f"F1-Score:  {metrics['f1']:.4f}")
    print(f"ROC-AUC:   {metrics['roc_auc']:.4f}")
    
    print("\n" + "-"*60)
    print("CONFUSION MATRIX")
    print("-"*60)
    cm = metrics['confusion_matrix']
    if cm.shape == (2, 2):
        print(f"True Negatives:  {cm[0,0]} | False Positives: {cm[0,1]}")
        print(f"False Negatives: {cm[1,0]} | True Positives:  {cm[1,1]}")
    else:
        print(f"Confusion Matrix:\n{cm}")
        print("(Note: Limited class distribution in test set)")
    
    print("\n" + "-"*60)
    print("CLASSIFICATION REPORT")
    print("-"*60)
    print(metrics['classification_report'])
    
    return classifier, metrics


def predict_arrhythmia(model, features):
    """
    Predict arrhythmia status for a single ECG recording.
    
    Parameters
    ----------
    model : ArrhythmiaClassifier
        Trained classifier
    features : dict
        Feature dictionary with keys: 'BPM', 'SDNN', 'RMSSD', 'LF_HF', 'Skewness', 'Kurtosis'
        
    Returns
    -------
    prediction : str
        Classification result ('Normal Rhythm' or 'Possible Arrhythmia Detected')
    probability : ndarray
        [P(normal), P(arrhythmia)]
    prediction_confidence : float
        Confidence level (0-1) of the prediction
    """
    
    # Prepare feature vector
    feature_vector = np.array([[
        features['BPM'],
        features['SDNN'],
        features['RMSSD'],
        features['LF_HF'],
        features['Skewness'],
        features['Kurtosis']
    ]])
    
    # Get prediction and probabilities
    label = model.predict(feature_vector)[0]
    proba = model.predict_proba(feature_vector)[0]
    
    # Interpret result
    if label == 1:
        prediction = "⚠️  ABNORMAL - Possible Arrhythmia Detected"
        confidence = proba[1]
    else:
        prediction = "✓ NORMAL - Regular Sinus Rhythm Detected"
        confidence = proba[0]
    
    return prediction, proba, confidence