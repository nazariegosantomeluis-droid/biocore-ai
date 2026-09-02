"""Entrenamiento y pipeline de validación para modelos ECG."""

import torch
from torch.utils.data import DataLoader


class ECGTrainer:
    def __init__(self, model, optimizer, loss_fn, device='cpu'):
        self.model = model.to(device)
        self.optimizer = optimizer
        self.loss_fn = loss_fn
        self.device = device

    def train_epoch(self, train_loader: DataLoader):
        self.model.train()
        running_loss = 0.0
        for batch in train_loader:
            inputs, labels = batch
            inputs = inputs.to(self.device)
            labels = labels.to(self.device)
            self.optimizer.zero_grad()
            outputs = self.model(inputs)
            loss = self.loss_fn(outputs, labels)
            loss.backward()
            self.optimizer.step()
            running_loss += loss.item()
        return running_loss / len(train_loader)

    def validate(self, val_loader: DataLoader):
        self.model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for batch in val_loader:
                inputs, labels = batch
                inputs = inputs.to(self.device)
                labels = labels.to(self.device)
                outputs = self.model(inputs)
                predictions = outputs.argmax(dim=1)
                correct += (predictions == labels).sum().item()
                total += labels.size(0)
        return correct / total if total > 0 else 0.0
