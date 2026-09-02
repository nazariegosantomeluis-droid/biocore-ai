"""
Signal Processing Module for ECG Analysis

Handles ECG signal filtering, R-peak detection, and RR interval computation.
Optimized for MIT-BIH Arrhythmia Database signals.

Functions:
----------
bandpass_filter(signal, fs, lowcut=0.5, highcut=40, order=4)
    Apply bandpass Butterworth filter to ECG signal.
    
detect_r_peaks(filtered_signal, fs)
    Detect R-peaks in filtered ECG signal using peak detection.
    
compute_rr_intervals(peaks, fs)
    Calculate RR intervals (time between R-peaks) in seconds.
"""

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks


def bandpass_filter(
    signal,
    fs,
    lowcut=0.5,
    highcut=40,
    order=4
):
    """
    Apply bandpass Butterworth filter to ECG signal.
    
    Standard ECG frequency band: 0.5 - 40 Hz
    Removes baseline wander (<0.5 Hz) and high-frequency noise (>40 Hz).
    
    Parameters
    ----------
    signal : ndarray
        Raw ECG signal (mV).
    fs : float
        Sampling frequency (Hz).
    lowcut : float, optional
        Low cutoff frequency (Hz). Default: 0.5
    highcut : float, optional
        High cutoff frequency (Hz). Default: 40
    order : int, optional
        Filter order. Default: 4
        
    Returns
    -------
    filtered_signal : ndarray
        Bandpass filtered ECG signal.
        
    Notes
    -----
    Uses zero-phase filtfilt to avoid phase distortion.
    """
    
    # Normalize frequencies by Nyquist frequency
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    
    # Validate frequency bounds
    if low < 0 or high > 1:
        raise ValueError(
            f"Normalized frequencies must be in (0, 1). "
            f"Got low={low}, high={high}"
        )
    
    # Design Butterworth filter
    b, a = butter(
        order,
        [low, high],
        btype='band'
    )
    
    # Apply zero-phase filter (forward-backward)
    filtered_signal = filtfilt(b, a, signal)
    
    return filtered_signal


def detect_r_peaks(
    filtered_signal,
    fs,
    prominence_factor=0.5
):
    """
    Detect R-peaks in filtered ECG signal.
    
    Uses adaptive peak detection with distance constraint based on sampling rate.
    Typical heart rate range: 40-200 BPM → R-peak distance: 0.3-1.5 seconds.
    
    Parameters
    ----------
    filtered_signal : ndarray
        Bandpass filtered ECG signal.
    fs : float
        Sampling frequency (Hz).
    prominence_factor : float, optional
        Prominence factor for peak detection. Default: 0.5
        Controls sensitivity of R-peak detection.
        
    Returns
    -------
    peaks : ndarray
        Indices of detected R-peaks.
    properties : dict
        Peak properties (height, width, prominence).
        
    Notes
    -----
    Minimum distance between peaks: 0.3 seconds (200 BPM max)
    Peak height: mean + 0.5*std of filtered signal
    """
    
    # Minimum distance between R-peaks (0.3s = 200 BPM max)
    min_distance = int(fs * 0.3)
    
    # Peak height threshold: mean + 0.5*std
    signal_mean = np.mean(filtered_signal)
    signal_std = np.std(filtered_signal)
    height_threshold = signal_mean + prominence_factor * signal_std
    
    # Detect peaks
    peaks, properties = find_peaks(
        filtered_signal,
        distance=min_distance,
        height=height_threshold
    )
    
    return peaks, properties


def compute_rr_intervals(
    peaks,
    fs
):
    """
    Calculate RR intervals (time between consecutive R-peaks).
    
    RR intervals are fundamental for heart rate variability analysis.
    Normal resting RR interval: 0.6-1.0 seconds (60-100 BPM).
    
    Parameters
    ----------
    peaks : ndarray
        Indices of detected R-peaks.
    fs : float
        Sampling frequency (Hz).
        
    Returns
    -------
    rr_intervals : ndarray
        RR intervals in seconds.
        
    Notes
    -----
    RR intervals = successive differences in peak times
    Units: seconds
    """
    
    if len(peaks) < 2:
        raise ValueError(
            f"Need at least 2 R-peaks to compute RR intervals. Got {len(peaks)}"
        )
    
    # Convert sample indices to time differences
    rr_intervals = np.diff(peaks) / fs
    
    return rr_intervals