"""
Biomedical Signal Visualizer - Main Pipeline

A comprehensive ECG analysis and arrhythmia detection system using
explainable AI for cardiovascular health assessment.

Pipeline:
=========
1. ECG Signal Loading (PhysioNet MIT-BIH or synthetic)
2. Signal Filtering (bandpass: 0.5-40 Hz)
3. R-Peak Detection (QRS complex identification)
4. RR Interval Analysis (beat-to-beat timing)
5. HRV Feature Extraction (temporal + frequency domain)
6. Machine Learning Classification (Logistic Regression)
7. Explainable AI Interpretation (physiological reasoning)

Usage:
======
    python main.py
    streamlit run app/ecg_trainer.py (Interactive Trainer Mode)

Requirements:
=============
    pip install -r requirements.txt

For PhysioNet data access:
    wfdb >= 4.1.1
"""

import argparse
import os
import socket
import subprocess
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

# Ensure terminal output supports UTF-8 on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


def open_saved_figures(paths):
    """Open or print saved figure files so they are accessible from terminal."""
    absolute_paths = [os.path.abspath(path) for path in paths]

    print("\n[>] Gráficas guardadas en:")
    for path in absolute_paths:
        print(f"  {path}")

    if sys.platform.startswith('win'):
        for path in absolute_paths:
            try:
                os.startfile(path)
            except Exception as open_error:
                print(f"[!] No se pudo abrir automáticamente: {path}")
                print(f"    {open_error}")
    else:
        print("[i] Ejecuta manualmente los enlaces anteriores para ver las figuras.")


def parse_arguments():
    parser = argparse.ArgumentParser(description='Biomedical Signal Visualizer launcher')
    parser.add_argument(
        '--mode',
        choices=['pipeline', 'dashboard', 'trainer'],
        default='pipeline',
        help='Selecciona el modo de ejecución: pipeline, dashboard, trainer',
    )
    parser.add_argument('--record', default='100', help='MIT-BIH record identifier para el pipeline')
    return parser.parse_args()


def launch_streamlit_dashboard():
    print('[*] Lanzando la interfaz Streamlit...')
    try:
        subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'app/streamlit_app.py'], check=False)
    except FileNotFoundError:
        print('[!] No se encontró Streamlit en el entorno actual.')
        print('    Instala Streamlit con: pip install streamlit')
    except Exception as exc:
        print(f'[!] Error al iniciar Streamlit: {exc}')

# ============================================================================
# IMPORT BIOMEDICAL SIGNAL MODULES
# ============================================================================

from src import (
    bandpass_filter,
    detect_r_peaks,
    compute_rr_intervals,
    compute_psd,
    extract_features,
    train_model,
    predict_arrhythmia,
    interpret_features,
    generate_clinical_report,
    plot_ecg_signal,
    plot_rr_intervals,
    plot_psd,
    plot_feature_comparison,
    ECGEducationPlatform,
    create_educational_report,
    AnalisisRiesgoClinico,
    generar_reporte_riesgo_completo,
    AnalisisHRVAvanzado,
    generar_reporte_hrv_completo,
)
from src.visualization import show_plots

# Optional clinical visualization module (non-blocking)
try:
    from visualization.ecg_clinical_plot import plot_ecg_clinical
except Exception:
    plot_ecg_clinical = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_mitbih_record(record_id='100'):
    """
    Attempt to load MIT-BIH ECG record from PhysioNet.
    
    Parameters
    ----------
    record_id : str
        MIT-BIH record identifier (e.g., '100', '101', '102')
        
    Returns
    -------
    signal : ndarray or None
        ECG signal (first lead)
    fs : float or None
        Sampling frequency (Hz)
    """
    try:
        import wfdb
        import concurrent.futures
        
        print(f"[*] Attempting to load MIT-BIH record {record_id} from PhysioNet...")

        def load_record():
            return wfdb.rdrecord(record_id, pn_dir='mitdb')

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(load_record)
            try:
                record = future.result(timeout=10)
            except concurrent.futures.TimeoutError:
                print(f"[X] PhysioNet request timed out after 10 seconds.")
                print(f"    Usando datos sintéticos en su lugar.")
                return None, None

        signal = record.p_signal[:, 0]  # First lead (MLII)
        fs = record.fs
        
        print(f"[OK] Successfully loaded MIT-BIH record {record_id}")
        print(f"    Duration: {len(signal)/fs:.1f} seconds")
        print(f"    Sampling rate: {fs} Hz")
        
        return signal, fs
        
    except Exception as e:
        print(f"[X] Failed to load MIT-BIH record: {str(e)}")
        print(f"    Usando datos sintéticos en su lugar.")
        return None, None


def generate_synthetic_ecg(duration=10, fs=250, noise_level=0.1):
    """
    Generate synthetic ECG signal for demonstration.
    
    Parameters
    ----------
    duration : float
        Duration in seconds
    fs : float
        Sampling frequency (Hz)
    noise_level : float
        Gaussian noise standard deviation
        
    Returns
    -------
    signal : ndarray
        Synthetic ECG signal
    fs : float
        Sampling frequency
    """
    
    print("[*] Generating synthetic ECG signal...")
    
    t = np.linspace(0, duration, int(duration * fs))
    
    # Simulate heart rate (70 BPM) using sinusoidal components
    # QRS complex pattern
    qrs_freq = 70 / 60  # Heart rate in Hz
    
    # Complex ECG waveform with multiple components
    p_wave = 0.15 * np.sin(2 * np.pi * qrs_freq * t)
    qrs_complex = 1.2 * np.exp(-((t % (1/qrs_freq) - 0.3/(1/qrs_freq))**2) / (2 * 0.01**2))
    t_wave = 0.3 * np.sin(2 * np.pi * qrs_freq * t + np.pi/3)
    
    # Baseline wander (very low frequency)
    baseline = 0.2 * np.sin(2 * np.pi * 0.1 * t)
    
    # Combine components
    signal = p_wave + qrs_complex + t_wave + baseline
    
    # Add realistic noise
    signal += noise_level * np.random.randn(len(signal))
    
    print(f"[OK] Generated {duration}s synthetic ECG at {fs} Hz")
    
    return signal, fs


def create_synthetic_dataset(base_features, n_samples=100):
    """
    Create synthetic dataset by adding noise to extracted features.
    
    Parameters
    ----------
    base_features : dict
        Base HRV features to perturb
    n_samples : int
        Number of synthetic samples to generate
        
    Returns
    -------
    df : DataFrame
        Synthetic dataset with features and labels
    """
    
    print(f"[*] Generating synthetic dataset with {n_samples} samples...")
    
    dataset = []
    
    # Create a balanced dataset with both normal and arrhythmia examples.
    n_arrhythmia = n_samples // 2
    n_normal = n_samples - n_arrhythmia
    
    for _ in range(n_normal):
        simulated_features = {
            'BPM': max(40, base_features['BPM'] + np.random.normal(-5, 5)),
            'SDNN': max(0.01, base_features['SDNN'] + np.random.normal(0.01, 0.01)),
            'RMSSD': max(0.01, base_features['RMSSD'] + np.random.normal(0.01, 0.01)),
            'LF_HF': max(0.1, base_features['LF_HF'] + np.random.normal(-0.2, 0.3)),
            'Skewness': base_features['Skewness'] + np.random.normal(0, 0.2),
            'Kurtosis': base_features['Kurtosis'] + np.random.normal(0, 0.5),
            'Label': 0
        }
        dataset.append(simulated_features)
    
    for _ in range(n_arrhythmia):
        simulated_features = {
            'BPM': max(40, base_features['BPM'] + np.random.normal(20, 8)),
            'SDNN': max(0.01, base_features['SDNN'] + np.random.normal(-0.05, 0.02)),
            'RMSSD': max(0.01, base_features['RMSSD'] + np.random.normal(-0.02, 0.02)),
            'LF_HF': max(0.1, base_features['LF_HF'] + np.random.normal(4.0, 0.7)),
            'Skewness': base_features['Skewness'] + np.random.normal(0.5, 0.3),
            'Kurtosis': base_features['Kurtosis'] + np.random.normal(1.0, 0.7),
            'Label': 1
        }
        dataset.append(simulated_features)
    
    np.random.shuffle(dataset)
    df = pd.DataFrame(dataset)
    
    # Print dataset statistics
    normal_count = len(df[df['Label'] == 0])
    arrhythmia_count = len(df[df['Label'] == 1])
    
    print(f"[OK] Dataset created:")
    print(f"    Normal samples:     {normal_count} ({100*normal_count/n_samples:.1f}%)")
    print(f"    Arrhythmia samples: {arrhythmia_count} ({100*arrhythmia_count/n_samples:.1f}%)")
    
    return df


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main(record_id='100'):
    """Execute the complete biomedical signal analysis pipeline."""
    
    print("\n" + "="*80)
    print("BIOMEDICAL SIGNAL VISUALIZER - ECG ANALYSIS PIPELINE")
    print("="*80)
    
    # ========================================================================
    # STAGE 1: LOAD ECG SIGNAL
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 1: ECG SIGNAL LOADING")
    print("="*80)
    
    # Try to load real data from PhysioNet
    signal, fs = load_mitbih_record(record_id)
    ecg_prefix = f"mitbih_{record_id}"
    
    # Fall back to synthetic data if unavailable
    if signal is None or fs is None:
        signal, fs = generate_synthetic_ecg(duration=30, fs=250)
        ecg_prefix = 'synthetic_ecg'
    
    # ========================================================================
    # STAGE 2: SIGNAL FILTERING
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 2: SIGNAL FILTERING")
    print("="*80)
    
    print("[*] Applying bandpass filter (0.5-40 Hz)...")
    filtered_signal = bandpass_filter(signal, fs, lowcut=0.5, highcut=40, order=4)
    print("[OK] Signal filtering completed")

    if not os.path.isdir('figures'):
        os.makedirs('figures', exist_ok=True)
    
    # ========================================================================
    # STAGE 3: R-PEAK DETECTION
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 3: R-PEAK DETECTION")
    print("="*80)
    
    print("[*] Detecting R-peaks using adaptive peak detection...")
    peaks, properties = detect_r_peaks(filtered_signal, fs)
    
    if len(peaks) < 10:
        print(f"[!] Warning: Only {len(peaks)} R-peaks detected (expected >10)")
        print("[!] ECG signal may be too short or have poor signal quality")
    
    print(f"[OK] Detected {len(peaks)} R-peaks")
    
    # ========================================================================
    # STAGE 4: RR INTERVAL COMPUTATION
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 4: RR INTERVAL ANALYSIS")
    print("="*80)
    
    print("[*] Computing RR intervals (beat-to-beat timing)...")
    rr_intervals = compute_rr_intervals(peaks, fs)
    
    mean_rr = np.mean(rr_intervals)
    std_rr = np.std(rr_intervals)
    min_rr = np.min(rr_intervals)
    max_rr = np.max(rr_intervals)
    
    print(f"[OK] RR Interval Statistics:")
    print(f"    Mean:   {mean_rr:.4f} s ({60/mean_rr:.1f} BPM)")
    print(f"    Std:    {std_rr:.4f} s")
    print(f"    Min:    {min_rr:.4f} s ({60/max_rr:.1f} BPM max)")
    print(f"    Max:    {max_rr:.4f} s ({60/min_rr:.1f} BPM min)")
    
    # ========================================================================
    # STAGE 5: POWER SPECTRAL DENSITY
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 5: POWER SPECTRAL DENSITY ANALYSIS")
    print("="*80)
    
    print("[*] Computing PSD using Welch method...")
    frequencies, power_spectrum = compute_psd(rr_intervals)
    print("[OK] PSD analysis completed")
    
    # ========================================================================
    # STAGE 6: HRV FEATURE EXTRACTION
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 6: HEART RATE VARIABILITY FEATURE EXTRACTION")
    print("="*80)
    
    print("[*] Extracting comprehensive HRV feature set...")
    features = extract_features(rr_intervals, power_spectrum, frequencies)
    
    print("[OK] Extracted HRV Features:")
    print(f"    BPM (Heart Rate):              {features['BPM']:.2f} bpm")
    print(f"    SDNN (Overall HRV):            {features['SDNN']:.4f} s")
    print(f"    RMSSD (Parasympathetic Tone):  {features['RMSSD']:.4f} s")
    print(f"    LF/HF (Autonomic Balance):     {features['LF_HF']:.2f}")
    print(f"    Skewness (RR Distribution):    {features['Skewness']:.4f}")
    print(f"    Kurtosis (RR Distribution):    {features['Kurtosis']:.4f}")
    
    # ========================================================================
    # STAGE 7: MACHINE LEARNING MODEL TRAINING
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 7: MACHINE LEARNING MODEL TRAINING")
    print("="*80)
    
    print("[*] Creating synthetic training dataset...")
    df = create_synthetic_dataset(features, n_samples=150)
    
    print("[*] Training Logistic Regression classifier...")
    model, metrics = train_model(df, test_size=0.25, random_state=42)
    
    # ========================================================================
    # STAGE 8: ARRHYTHMIA PREDICTION
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 8: ARRHYTHMIA PREDICTION")
    print("="*80)
    
    print("[*] Making prediction on test recording...")
    prediction, probability, confidence = predict_arrhythmia(model, features)
    
    print(f"\n{prediction}")
    print(f"Confidence:  {confidence:.1%}")
    print(f"P(Normal):   {probability[0]:.1%}")
    print(f"P(Arrhythmia): {probability[1]:.1%}")
    
    # ========================================================================
    # STAGE 9: EXPLAINABLE AI INTERPRETATION
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 9: EXPLAINABLE AI INTERPRETATION")
    print("="*80)
    
    print("[*] Generating clinical interpretation...")
    interpretations = interpret_features(features)
    
    print("\n[OK] Clinical Interpretation:")
    for i, interpretation in enumerate(interpretations, 1):
        print(f"\n{interpretation}")
    
    # ========================================================================
    # STAGE 10: COMPREHENSIVE CLINICAL REPORT
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 10: COMPREHENSIVE CLINICAL REPORT")
    print("="*80)
    
    recording_duration = len(signal) / fs
    
    clinical_report = generate_clinical_report(
        features=features,
        prediction=prediction,
        probability=probability,
        confidence=confidence,
        recording_duration=recording_duration,
        patient_info={
            'id': 'MIT-BIH-100-Demo',
            'age': 'N/A',
            'sex': 'N/A'
        }
    )
    
    print(clinical_report)
    
    # ========================================================================
    # OPTIONAL: GENERATE VISUALIZATIONS
    # ========================================================================
    
    print("\n" + "="*80)
    print("GENERATING VISUALIZATIONS")
    print("="*80)
    
    try:
        print("[*] Creating ECG signal plots...")
        fig1 = plot_ecg_signal(signal, fs, peaks=peaks, filtered_signal=filtered_signal)
        fig1.savefig('figures/ecg_signal.png', dpi=300, bbox_inches='tight')
        print("[OK] Saved: figures/ecg_signal.png")
        
        print("[*] Creating RR interval plots...")
        fig2 = plot_rr_intervals(rr_intervals)
        fig2.savefig('figures/rr_intervals.png', dpi=300, bbox_inches='tight')
        print("[OK] Saved: figures/rr_intervals.png")
        
        print("[*] Creating PSD plot...")
        fig3 = plot_psd(frequencies, power_spectrum)
        fig3.savefig('figures/power_spectral_density.png', dpi=300, bbox_inches='tight')
        print("[OK] Saved: figures/power_spectral_density.png")

        # Do not block on GUI display by default.
        backend = matplotlib.get_backend().lower()
        print(f"[i] Backend actual: {backend}. No se abrirá ventana gráfica automática.")

        # Print saved figure file paths so VS Code terminal puede usarlos como enlaces
        figure_paths = [
            'figures/ecg_signal.png',
            'figures/rr_intervals.png',
            'figures/power_spectral_density.png'
        ]
        open_saved_figures(figure_paths)
        
        # Close figures to save memory
        plt.close('all')
        # Optional: clinical-style ECG visualizations (hospital-paper, annotations, report)
        try:
            if plot_ecg_clinical is not None:
                print('[*] Creating clinical-style ECG visualizations...')
                vis_res = plot_ecg_clinical(filtered_signal, fs, rpeaks=peaks, outdir='figures', prefix=ecg_prefix)
                # Open primary outputs
                open_saved_figures([p for p in (vis_res.get('clinical'), vis_res.get('annotated'), vis_res.get('report')) if p])
                print('[OK] Clinical visualizations saved to figures/')
            else:
                print('[i] Clinical visualization module not installed or failed to import. Skipping.')
        except Exception as e:
            print(f"[!] Clinical visualization failed: {e}")
        
    except Exception as e:
        print(f"[!] Visualization error (non-critical): {str(e)}")
    
    # ========================================================================
    # STAGE 11: EDUCATIONAL MODE (TEACHING PLATFORM)
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 11: EDUCATIONAL ANALYSIS")
    print("="*80)
    
    try:
        platform = ECGEducationPlatform()
        edu_data = platform.modo_ensenanza(
            bpm=features['BPM'],
            variabilidad_rr=features['SDNN'],
            lf_hf=features['LF_HF']
        )
        
        print("[*] Generating educational content...")
        print(f"\n📚 {edu_data['titulo_leccion']}")
        print(f"Concepto clave: {edu_data['concepto_clave']}\n")
        print(edu_data['fisiologia'])
        
        print("\n[*] Clinical findings for this pattern:")
        for hallazgo in edu_data['hallazgos']:
            print(f"  • {hallazgo}")
        
        print("\n[*] Study questions:")
        for i, pregunta in enumerate(edu_data['preguntas_estudio'], 1):
            print(f"  {i}. {pregunta}")
        
        edu_report = create_educational_report(
            bpm=features['BPM'],
            sdnn=features['SDNN'],
            rmssd=features['RMSSD'],
            lf_hf=features['LF_HF'],
            prediccion=prediction
        )
        print(edu_report)
        
    except Exception as e:
        print(f"[!] Educational analysis error: {str(e)}")

    # ========================================================================
    # STAGE 12: ADVANCED HRV ANALYSIS
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 12: ADVANCED HRV ANALYSIS (CLINICAL)")
    print("="*80)
    
    try:
        print("[*] Computing advanced HRV metrics...")
        hrv_report = generar_reporte_hrv_completo(rr_intervals, fs=4.0)
        print(hrv_report)
        
    except Exception as e:
        print(f"[!] Advanced HRV analysis error: {str(e)}")

    # ========================================================================
    # STAGE 13: CLINICAL RISK ANALYSIS
    # ========================================================================
    
    print("\n" + "="*80)
    print("STAGE 13: CLINICAL RISK ASSESSMENT")
    print("="*80)
    
    try:
        print("[*] Analyzing clinical risk patterns...")
        riesgo_report = generar_reporte_riesgo_completo(
            bpm=features['BPM'],
            sdnn=features['SDNN'],
            rmssd=features['RMSSD'],
            lf_hf=features['LF_HF'],
            skewness=features['Skewness'],
            kurtosis=features['Kurtosis'],
            intervalos_rr=rr_intervals.tolist()
        )
        print(riesgo_report)
        
    except Exception as e:
        print(f"[!] Risk analysis error: {str(e)}")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    print("\n" + "="*80)
    print("PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
    print("="*80)
    print(f"\nAnalysis Summary:")
    print(f"  Recording Duration: {recording_duration:.1f} seconds")
    print(f"  R-Peaks Detected:   {len(peaks)}")
    print(f"  Heart Rate:         {features['BPM']:.0f} bpm")
    print(f"  Classification:     {prediction}")
    print(f"  Confidence:         {confidence:.1%}")
    print(f"\nFiles generated in 'figures/' directory:")
    print(f"  - ecg_signal.png (raw and filtered signal with R-peaks)")
    print(f"  - rr_intervals.png (RR interval time series and histogram)")
    print(f"  - power_spectral_density.png (frequency domain analysis)")
    print("\n" + "="*80)


if __name__ == "__main__":
    args = parse_arguments()
    try:
        if args.mode == 'dashboard':
            launch_streamlit_dashboard()
        elif args.mode == 'trainer':
            print('[*] Ejecuta: streamlit run app/ecg_trainer.py')
        else:
            main(args.record)
    except KeyboardInterrupt:
        print("\n\n[!] Pipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)