#!/usr/bin/env python3
"""
phase4_cnn_model.py

Phase 4: 1D-CNN for timing side-channel classification.

Builds a 1D Convolutional Neural Network to classify the LSB of the
secret key byte from timing traces. 1D-CNNs provide shift-invariance
which helps handle temporal jitter in timing measurements.

ANTI-LEAKAGE:
- Training uses ONLY the training set.
- Validation set used for early stopping (no test data involved).
- Scaler fit on training set only (loaded from Phase 3).
"""

import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")

# Check for PyTorch
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class TimingCNN1D(nn.Module):
    """1D-CNN for timing side-channel classification.

    Architecture:
    - Conv1d layers for shift-invariant feature extraction
    - MaxPool for downsampling and further shift invariance
    - Dense layers for classification
    - Dropout for regularization
    """
    def __init__(self, input_features=3):
        super().__init__()
        # Treat the features as channels on a length-1 signal,
        # or reshape timing as a 1D sequence.
        # Since we have scalar timing with engineered features,
        # we treat features as a 1D "image" of length=input_features with 1 channel.
        self.conv_block = nn.Sequential(
            # Input: (batch, 1, input_features)
            nn.Conv1d(in_channels=1, out_channels=32, kernel_size=1, padding=0),
            nn.ReLU(),
            nn.Conv1d(in_channels=32, out_channels=64, kernel_size=1, padding=0),
            nn.ReLU(),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * input_features, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 2),  # binary classification
        )

    def forward(self, x):
        # x shape: (batch, 1, features)
        x = self.conv_block(x)
        x = self.classifier(x)
        return x


def load_data():
    train = pd.read_csv(os.path.join(DATA_DIR, "train.csv"))
    val = pd.read_csv(os.path.join(DATA_DIR, "val.csv"))
    return train, val


def prepare_features(df, scaler=None):
    X = np.column_stack([
        df["timing_ns"].values,
        np.log1p(df["timing_ns"].values),
        df["timing_ns"].values ** 2,
    ])
    y = df["target_bit"].values
    if scaler is not None:
        X = scaler.transform(X)
    return X, y


def main():
    if not HAS_TORCH:
        print("[Phase 4] PyTorch not installed. Attempting install...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "torch", "--quiet"])
        print("[Phase 4] PyTorch installed. Please re-run this script.")
        sys.exit(0)

    print("[Phase 4] Loading filtered training and validation data...")
    train, val = load_data()

    # Load scaler from Phase 3 (fit on training data only)
    scaler = pickle.load(open(os.path.join(MODELS_DIR, "scaler.pkl"), "rb"))

    X_train, y_train = prepare_features(train, scaler)
    X_val, y_val = prepare_features(val, scaler)

    print(f"  Train: {len(X_train)} samples, Val: {len(X_val)} samples")
    print(f"  Features per sample: {X_train.shape[1]}")

    # Convert to PyTorch tensors
    # Shape: (batch, 1, features) for Conv1d
    X_train_t = torch.FloatTensor(X_train).unsqueeze(1)
    y_train_t = torch.LongTensor(y_train)
    X_val_t = torch.FloatTensor(X_val).unsqueeze(1)
    y_val_t = torch.LongTensor(y_val)

    train_ds = TensorDataset(X_train_t, y_train_t)
    val_ds = TensorDataset(X_val_t, y_val_t)
    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=len(val_ds))

    # Build model
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"  Device: {device}")

    model = TimingCNN1D(input_features=X_train.shape[1]).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

    # Training with early stopping
    best_val_acc = 0.0
    patience = 20
    patience_counter = 0
    num_epochs = 200

    print(f"\n[Phase 4] Training 1D-CNN for up to {num_epochs} epochs with early stopping (patience={patience})...")

    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(y_batch)
            train_correct += (outputs.argmax(1) == y_batch).sum().item()
            train_total += len(y_batch)

        # Validation
        model.eval()
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                val_outputs = model(X_batch)
                val_preds = val_outputs.argmax(1)
                val_acc = (val_preds == y_batch).float().mean().item()
                val_loss = criterion(val_outputs, y_batch).item()

        scheduler.step(val_loss)

        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}: Train loss={train_loss/train_total:.4f}, "
                  f"Train acc={train_correct/train_total:.4f}, "
                  f"Val loss={val_loss:.4f}, Val acc={val_acc:.4f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            patience_counter = 0
            torch.save(model.state_dict(), os.path.join(MODELS_DIR, "best_cnn.pt"))
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  Early stopping at epoch {epoch+1}")
                break

    print(f"\n[Phase 4] Best validation accuracy: {best_val_acc:.4f}")
    print(f"[Phase 4] Model saved to {os.path.join(MODELS_DIR, 'best_cnn.pt')}")

    # Save CNN config for Phase 5
    cnn_config = {
        "input_features": X_train.shape[1],
        "best_val_acc": best_val_acc,
        "device": str(device),
        "architecture": "TimingCNN1D: Conv1d(1->32)->ReLU->Conv1d(32->64)->ReLU->Flatten->FC(128)->FC(64)->FC(2)",
    }
    with open(os.path.join(MODELS_DIR, "cnn_config.json"), "w") as f:
        json.dump(cnn_config, f, indent=2)

    print("[Phase 4] REMINDER: Test set evaluation deferred to Phase 5.")


if __name__ == "__main__":
    main()
