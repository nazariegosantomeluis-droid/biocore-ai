"""Módulo de inferencia para modelos ECG y detección de arritmias."""

import torch
import numpy as np


def predict_ecg(model, signal: np.ndarray, device='cpu'):
    model.eval()
    tensor = torch.tensor(signal, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(device)
    with torch.no_grad():
        out = model(tensor)
        prob = torch.softmax(out, dim=1).cpu().numpy()
        if prob.size == 0:
            return None, np.array([])
        prob = prob[0]
        if prob.size == 0:
            return None, np.array([])
        pred = int(np.argmax(prob))
    return pred, prob
