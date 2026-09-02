"""
Feature Extraction Module for Heart Rate Variability (HRV) Analysis

Computes temporal, frequency-domain, and nonlinear HRV features.
Following guidelines from Heart Rate Variability Standards of Measurement (ESC/NASPE 1996).

Features:
---------
Temporal Domain:
    BPM : Heart rate (beats per minute)
    SDNN : Standard deviation of NN intervals
    RMSSD : Root mean square of successive differences
    
Frequency Domain:
    LF : Low frequency power (0.04-0.15 Hz) - sympathetic activity
    HF : High frequency power (0.15-0.4 Hz) - parasympathetic activity
    LF_HF : LF/HF ratio - sympathetic/parasympathetic balance
    
Nonlinear:
    Skewness : Distribution asymmetry of RR intervals
    Kurtosis : Distribution tail behavior
"""

import numpy as np
from scipy.signal import welch
from scipy.integrate import trapezoid
from scipy.stats import skew, kurtosis


def compute_psd(
    rr_intervals,
    method='welch',
    nperseg=None
):
    """
    Compute Power Spectral Density (PSD) of RR intervals.
    
    Uses Welch method for robust frequency domain analysis.
    Standard frequency bands:
    - VLF: 0.0033-0.04 Hz (very low frequency)
    - LF: 0.04-0.15 Hz (low frequency, sympathetic)
    - HF: 0.15-0.4 Hz (high frequency, parasympathetic)
    
    Parameters
    ----------
    rr_intervals : ndarray
        RR intervals in seconds.
    method : str, optional
        PSD computation method. Default: 'welch'
    nperseg : int, optional
        Segment length for Welch method. Default: len(rr_intervals)
        
    Returns
    -------
    frequencies : ndarray
        Frequency values (Hz).
    power_spectrum : ndarray
        Power spectral density (ms²/Hz).
        
    Notes
    -----
    Sampling frequency estimated as 1/mean(RR_interval)
    """
    
    if len(rr_intervals) < 4:
        raise ValueError(
            f"Need at least 4 RR intervals for PSD. Got {len(rr_intervals)}"
        )
    
    # Estimate sampling frequency from RR intervals
    mean_rr = np.mean(rr_intervals)
    fs_rr = 1 / mean_rr  # Sampling frequency in RR interval domain
    
    # Set segment length if not provided
    if nperseg is None:
        nperseg = len(rr_intervals)
    
    # Compute PSD using Welch method
    frequencies, power_spectrum = welch(
        rr_intervals,
        fs=fs_rr,
        nperseg=min(nperseg, len(rr_intervals)),
        window='hamming'
    )
    
    return frequencies, power_spectrum


def extract_features(
    rr_intervals,
    power_spectrum,
    frequencies
):
    """
    Extract comprehensive HRV feature set from RR intervals and PSD.
    
    Computes temporal, frequency-domain, and nonlinear features
    suitable for arrhythmia classification and clinical assessment.
    
    Parameters
    ----------
    rr_intervals : ndarray
        RR intervals in seconds.
    power_spectrum : ndarray
        Power spectral density (ms²/Hz).
    frequencies : ndarray
        Frequency values (Hz).
        
    Returns
    -------
    features : dict
        Dictionary containing all extracted HRV features:
        {
            'BPM': Heart rate (beats/min),
            'SDNN': Std dev of RR intervals (ms),
            'RMSSD': Root mean square of successive diffs (ms),
            'LF_HF': LF/HF power ratio,
            'Skewness': RR interval distribution skewness,
            'Kurtosis': RR interval distribution kurtosis
        }
        
    Clinical Interpretation Ranges
    ==============================
    BPM:
        < 60 : Bradycardia (abnormally slow)
        60-100 : Normal resting (sinus rhythm)
        > 100 : Tachycardia (abnormally fast)
        
    SDNN (indicates overall HRV):
        < 50 ms : Very low HRV (pathological)
        50-100 ms : Low HRV
        > 100 ms : Normal/high HRV (healthy)
        
    RMSSD (parasympathetic activity):
        < 30 ms : Low parasympathetic tone
        30-50 ms : Moderate
        > 50 ms : High parasympathetic tone
        
    LF/HF ratio (autonomic balance):
        < 1 : Parasympathetic dominance
        1-2 : Balanced
        > 3 : Sympathetic dominance (stress/arrhythmia)
    """
    
    features = {}
    
    # ============================================
    # TEMPORAL DOMAIN FEATURES
    # ============================================
    
    # Heart rate (BPM)
    features['BPM'] = 60 / np.mean(rr_intervals)
    
    # Standard deviation of NN intervals (SDNN)
    # Measure of overall HRV
    features['SDNN'] = np.std(rr_intervals)
    
    # Root mean square of successive differences (RMSSD)
    # Reflects high-frequency HRV component (parasympathetic activity)
    rr_diffs = np.diff(rr_intervals)
    features['RMSSD'] = np.sqrt(np.mean(rr_diffs ** 2))
    
    # ============================================
    # FREQUENCY DOMAIN FEATURES
    # ============================================
    
    # Low frequency band: 0.04-0.15 Hz (sympathetic + parasympathetic)
    lf_band = (frequencies >= 0.04) & (frequencies < 0.15)
    
    # High frequency band: 0.15-0.4 Hz (parasympathetic/vagal activity)
    hf_band = (frequencies >= 0.15) & (frequencies < 0.4)
    
    # LF power
    lf_power = trapezoid(
        power_spectrum[lf_band],
        frequencies[lf_band]
    ) if np.any(lf_band) else 0
    
    # HF power
    hf_power = trapezoid(
        power_spectrum[hf_band],
        frequencies[hf_band]
    ) if np.any(hf_band) else 0
    
    # LF/HF ratio: Sympathetic/Parasympathetic balance
    # Safe division: avoid division by zero
    if hf_power > 0:
        features['LF_HF'] = lf_power / hf_power
    else:
        features['LF_HF'] = np.nan
    
    # ============================================
    # NONLINEAR FEATURES
    # ============================================
    
    # Skewness: Asymmetry of RR interval distribution
    # Positive skew: right tail (longer intervals)
    # Negative skew: left tail (shorter intervals)
    features['Skewness'] = skew(rr_intervals)
    
    # Kurtosis: Tail behavior of RR interval distribution
    # Positive kurtosis: heavier tails (more extreme values)
    # Negative kurtosis: lighter tails (fewer extremes)
    features['Kurtosis'] = kurtosis(rr_intervals)
    
    return features