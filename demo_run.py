import numpy as np
from visualization.ecg_clinical_plot import plot_ecg_clinical

# Synthetic ECG-like signal for demo
fs = 250.0
t = np.arange(0, 10, 1/fs)
# simple pseudo-ECG: sum of sinusoids + spikes for R
sig = 0.2 * np.sin(2 * np.pi * 1.0 * t) + 0.05 * np.random.randn(len(t))
# add R spikes every 1s
for r in range(1, 9):
    idx = int(r * fs)
    if idx < len(sig):
        sig[idx:idx+3] += 1.0

res = plot_ecg_clinical(sig, fs, rpeaks=None, outdir='figures', prefix='demo_run')
print('Generated:', res)
