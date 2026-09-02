"""Convolutional neural network model for ECG arrhythmia detection."""

from typing import Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    torch = None  # type: ignore
    nn = None  # type: ignore
    DataLoader = None  # type: ignore
    TensorDataset = None  # type: ignore


class ECGCNNModel:
    def __init__(self, input_length: int = 500, num_classes: int = 2):
        self.input_length = input_length
        self.num_classes = num_classes
        self.model = self._build_model() if torch is not None else None
        self.is_trained = False

    def _build_model(self):
        class SimpleCNN(nn.Module):
            def __init__(self, length: int, classes: int):
                super().__init__()
                self.conv1 = nn.Conv1d(1, 16, kernel_size=7, padding=3)
                self.bn1 = nn.BatchNorm1d(16)
                self.conv2 = nn.Conv1d(16, 32, kernel_size=5, padding=2)
                self.bn2 = nn.BatchNorm1d(32)
                self.pool = nn.MaxPool1d(2)
                self.fc1 = nn.Linear((length // 2) * 32, 64)
                self.fc2 = nn.Linear(64, classes)

            def forward(self, x):
                x = self.pool(nn.functional.relu(self.bn1(self.conv1(x))))
                x = nn.functional.relu(self.bn2(self.conv2(x)))
                x = x.view(x.size(0), -1)
                x = nn.functional.relu(self.fc1(x))
                return self.fc2(x)

        return SimpleCNN(self.input_length, self.num_classes)

    def train(self, X: np.ndarray, y: np.ndarray, epochs: int = 10, batch_size: int = 32, lr: float = 1e-3):
        if torch is None:
            raise ImportError('PyTorch no está instalado. Instala torch para entrenar el modelo.')
        if self.model is None:
            raise RuntimeError('No se pudo construir el modelo CNN.')

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(device)
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)

        X_tensor = torch.tensor(X, dtype=torch.float32).unsqueeze(1)
        y_tensor = torch.tensor(y, dtype=torch.long)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        self.model.train()
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                optimizer.zero_grad()
                outputs = self.model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            print(f'Epoch {epoch+1}/{epochs} - Loss: {epoch_loss/len(loader):.4f}')

        self.is_trained = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        if torch is None or self.model is None:
            raise ImportError('PyTorch no está instalado. Instalalo para hacer predicciones.')
        self.model.eval()
        X = np.asarray(X)
        if X.size == 0:
            return np.array([])
        X_tensor = torch.tensor(X, dtype=torch.float32).unsqueeze(1)
        with torch.no_grad():
            logits = self.model(X_tensor)
            if logits.numel() == 0:
                return np.array([])
            return torch.argmax(logits, dim=1).cpu().numpy()

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if torch is None or self.model is None:
            raise ImportError('PyTorch no está instalado. Instalalo para hacer predicciones.')
        self.model.eval()
        X = np.asarray(X)
        if X.size == 0:
            return np.array([])
        X_tensor = torch.tensor(X, dtype=torch.float32).unsqueeze(1)
        with torch.no_grad():
            logits = self.model(X_tensor)
            if logits.numel() == 0:
                return np.array([])
            return nn.functional.softmax(logits, dim=1).cpu().numpy()


def train_ecg_cnn(X: np.ndarray, y: np.ndarray, **kwargs) -> ECGCNNModel:
    model = ECGCNNModel(input_length=X.shape[1], num_classes=len(np.unique(y)))
    model.train(X, y, **kwargs)
    return model
