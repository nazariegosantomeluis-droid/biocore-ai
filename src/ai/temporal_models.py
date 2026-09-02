"""Temporal models for biomedical sequence analysis, including LSTM."""

from typing import Optional

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    torch = None  # type: ignore
    nn = None  # type: ignore
    DataLoader = None  # type: ignore
    TensorDataset = None  # type: ignore


class LSTMTemporalModel:
    def __init__(self, input_size: int = 1, hidden_size: int = 64, num_layers: int = 2, num_classes: int = 2):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.num_classes = num_classes
        self.model = self._build_model() if torch is not None else None
        self.is_trained = False

    def _build_model(self):
        class SimpleLSTM(nn.Module):
            def __init__(self, input_size, hidden_size, num_layers, num_classes):
                super().__init__()
                self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
                self.fc = nn.Linear(hidden_size, num_classes)

            def forward(self, x):
                output, _ = self.lstm(x)
                return self.fc(output[:, -1, :])

        return SimpleLSTM(self.input_size, self.hidden_size, self.num_layers, self.num_classes)

    def train(self, X, y, epochs: int = 10, batch_size: int = 32, lr: float = 1e-3):
        if torch is None:
            raise ImportError('PyTorch no está instalado. Instala torch para entrenar.')
        if self.model is None:
            raise RuntimeError('No se pudo construir el modelo LSTM.')

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(device)
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)

        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.long)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        self.model.train()
        for epoch in range(epochs):
            total_loss = 0.0
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                optimizer.zero_grad()
                outputs = self.model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            print(f'Epoch {epoch+1}/{epochs}: loss={total_loss/len(loader):.4f}')

        self.is_trained = True

    def predict(self, X):
        if torch is None or self.model is None:
            raise ImportError('PyTorch no está instalado. Instalalo para predicción.')
        self.model.eval()
        X = np.asarray(X)
        if X.size == 0:
            return np.array([])
        X_tensor = torch.tensor(X, dtype=torch.float32)
        with torch.no_grad():
            logits = self.model(X_tensor)
            if logits.numel() == 0:
                return np.array([])
            return torch.argmax(logits, dim=1).cpu().numpy()
