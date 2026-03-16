#!/usr/bin/env python3
"""
phase4_v2.py

Phase 4 (upgraded): 1D-CNN on raw per-key timing sequences.

Instead of feeding aggregate features, we feed the raw timing trace
(all N repeats for a key) as a 1D "signal" to a CNN. This lets the
network learn its own shift-invariant features from the full timing
distribution per key.

ANTI-LEAKAGE:
- Scaler fit on TRAIN only (loaded from Phase 3 v2)
- Early stopping on VAL set
- Test set untouched
"""

import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models_v2")

TARGETS = ["target_lsb_c0", "target_hw_bin", "target_hw_parity"]

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    print("PyTorch required. Install with: pip install torch")
    sys.exit(1)


class TimingSeqCNN(nn.Module):
    """1D-CNN operating on the sorted timing sequence of a key's repeats.
    Input: (batch, 1, seq_len) where seq_len = number of repeats per key.
    """
    def __init__(self, seq_len, num_classes=2):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(2),

            nn.Conv1d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2),

            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(4),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 4, 128),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x


class TimingAggCNN(nn.Module):
    """1D-CNN operating on aggregate feature vector (10 features)."""
    def __init__(self, num_features=10, num_classes=2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(num_features, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        return self.net(x)


TIMING_FEATURES = [
    "timing_min", "timing_q05", "timing_q10", "timing_q25",
    "timing_median", "timing_mean", "timing_std", "timing_iqr",
    "timing_range", "timing_skew",
]


def build_sequence_data(raw_df, agg_df, seq_len):
    """Build fixed-length sorted timing sequences per key.
    For each key, sort its repeat timings and pad/truncate to seq_len.
    """
    sequences = []
    labels_by_target = {t: [] for t in TARGETS}

    for _, row in agg_df.iterrows():
        key_id = row["key_id"]
        key_timings = raw_df[raw_df["key_id"] == key_id]["timing_cycles"].values
        # Sort timings (makes the signal shift-invariant)
        key_timings = np.sort(key_timings)
        # Pad or truncate
        if len(key_timings) >= seq_len:
            seq = key_timings[:seq_len]
        else:
            seq = np.pad(key_timings, (0, seq_len - len(key_timings)), mode="edge")
        sequences.append(seq)
        for t in TARGETS:
            labels_by_target[t].append(int(row[t]))

    X = np.array(sequences, dtype=np.float32)
    return X, labels_by_target


def train_model(model, train_loader, val_loader, device, epochs=150, patience=25):
    """Train with early stopping."""
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

    best_val_acc = 0.0
    best_state = None
    patience_counter = 0

    for epoch in range(epochs):
        model.train()
        train_correct = 0
        train_total = 0
        train_loss = 0.0

        for X_b, y_b in train_loader:
            X_b, y_b = X_b.to(device), y_b.to(device)
            optimizer.zero_grad()
            out = model(X_b)
            loss = criterion(out, y_b)
            loss.backward()
            optimizer.step()
            train_correct += (out.argmax(1) == y_b).sum().item()
            train_total += len(y_b)
            train_loss += loss.item() * len(y_b)

        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for X_b, y_b in val_loader:
                X_b, y_b = X_b.to(device), y_b.to(device)
                out = model(X_b)
                val_correct += (out.argmax(1) == y_b).sum().item()
                val_total += len(y_b)
                val_loss = criterion(out, y_b).item()

        val_acc = val_correct / val_total
        scheduler.step(val_loss)

        if (epoch + 1) % 25 == 0 or epoch == 0:
            print(f"    Epoch {epoch+1:3d}: train_acc={train_correct/train_total:.4f}, "
                  f"val_acc={val_acc:.4f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"    Early stopping at epoch {epoch+1}")
                break

    if best_state:
        model.load_state_dict(best_state)
    return best_val_acc


def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"[Phase 4 v2] Device: {device}")

    # Load data
    train_agg = pd.read_csv(os.path.join(DATA_DIR, "train_v2.csv"))
    val_agg = pd.read_csv(os.path.join(DATA_DIR, "val_v2.csv"))
    train_raw = pd.read_csv(os.path.join(DATA_DIR, "train_v2_raw.csv"))
    val_raw = pd.read_csv(os.path.join(DATA_DIR, "val_v2_raw.csv"))

    scaler = pickle.load(open(os.path.join(MODELS_DIR, "scaler_v2.pkl"), "rb"))

    print(f"  Train: {len(train_agg)} keys, Val: {len(val_agg)} keys")

    # --- Model A: DNN on aggregate features ---
    print("\n[Phase 4 v2] Model A: DNN on aggregate features")
    X_train_agg = scaler.transform(train_agg[TIMING_FEATURES].values)
    X_val_agg = scaler.transform(val_agg[TIMING_FEATURES].values)

    for target_name in TARGETS:
        print(f"\n  Target: {target_name}")
        y_train = train_agg[target_name].values
        y_val = val_agg[target_name].values

        X_t = torch.FloatTensor(X_train_agg)
        y_t = torch.LongTensor(y_train)
        X_v = torch.FloatTensor(X_val_agg)
        y_v = torch.LongTensor(y_val)

        train_loader = DataLoader(TensorDataset(X_t, y_t), batch_size=64, shuffle=True)
        val_loader = DataLoader(TensorDataset(X_v, y_v), batch_size=len(X_v))

        model = TimingAggCNN(num_features=len(TIMING_FEATURES)).to(device)
        best_acc = train_model(model, train_loader, val_loader, device, epochs=150, patience=25)
        print(f"  Best val acc: {best_acc:.4f}")
        torch.save(model.state_dict(), os.path.join(MODELS_DIR, f"dnn_{target_name}.pt"))

    # --- Model B: 1D-CNN on raw timing sequences ---
    print("\n[Phase 4 v2] Model B: 1D-CNN on sorted timing sequences")

    # Use ALL raw repeats (unfiltered) for the CNN — let the network handle noise.
    # Load the full raw data, not the quantile-filtered subset.
    full_raw = pd.read_csv(os.path.join(DATA_DIR, "raw_timing_traces_v2.csv"))

    # Keep only keys that are in train/val aggregated sets
    train_raw_full = full_raw[full_raw["key_id"].isin(train_agg["key_id"])]
    val_raw_full = full_raw[full_raw["key_id"].isin(val_agg["key_id"])]

    # Filter to keys with at least min_repeats measurements
    min_repeats = 16
    repeats_per_key_train = train_raw_full.groupby("key_id").size()
    valid_train_keys = repeats_per_key_train[repeats_per_key_train >= min_repeats].index
    repeats_per_key_val = val_raw_full.groupby("key_id").size()
    valid_val_keys = repeats_per_key_val[repeats_per_key_val >= min_repeats].index

    train_agg_seq = train_agg[train_agg["key_id"].isin(valid_train_keys)]
    val_agg_seq = val_agg[val_agg["key_id"].isin(valid_val_keys)]

    seq_len = min_repeats
    print(f"  Sequence length: {seq_len}")
    print(f"  Keys with >= {min_repeats} repeats: train={len(train_agg_seq)}, val={len(val_agg_seq)}")

    X_train_seq, y_train_by_target = build_sequence_data(train_raw_full, train_agg_seq, seq_len)
    X_val_seq, y_val_by_target = build_sequence_data(val_raw_full, val_agg_seq, seq_len)

    # Normalize sequences using train statistics
    seq_mean = X_train_seq.mean()
    seq_std = X_train_seq.std()
    X_train_seq = (X_train_seq - seq_mean) / (seq_std + 1e-8)
    X_val_seq = (X_val_seq - seq_mean) / (seq_std + 1e-8)

    # Save normalization params
    pickle.dump({"mean": float(seq_mean), "std": float(seq_std), "seq_len": seq_len},
                open(os.path.join(MODELS_DIR, "seq_norm.pkl"), "wb"))

    # Reshape for Conv1d: (batch, 1, seq_len)
    X_train_seq_t = torch.FloatTensor(X_train_seq).unsqueeze(1)
    X_val_seq_t = torch.FloatTensor(X_val_seq).unsqueeze(1)

    cnn_results = {}

    for target_name in TARGETS:
        print(f"\n  Target: {target_name}")
        y_train = np.array(y_train_by_target[target_name])
        y_val = np.array(y_val_by_target[target_name])

        y_t = torch.LongTensor(y_train)
        y_v = torch.LongTensor(y_val)

        train_loader = DataLoader(
            TensorDataset(X_train_seq_t, y_t), batch_size=64, shuffle=True
        )
        val_loader = DataLoader(
            TensorDataset(X_val_seq_t, y_v), batch_size=len(X_val_seq_t)
        )

        model = TimingSeqCNN(seq_len=seq_len).to(device)
        best_acc = train_model(model, train_loader, val_loader, device, epochs=150, patience=25)
        print(f"  Best val acc: {best_acc:.4f}")
        torch.save(model.state_dict(), os.path.join(MODELS_DIR, f"cnn_seq_{target_name}.pt"))
        cnn_results[target_name] = {"best_val_acc": best_acc, "seq_len": seq_len}

    with open(os.path.join(MODELS_DIR, "phase4_v2_results.json"), "w") as f:
        json.dump(cnn_results, f, indent=2)

    print(f"\n[Phase 4 v2] Complete. Models saved to {MODELS_DIR}/")
    print("[Phase 4 v2] REMINDER: Test set evaluation deferred to Phase 5.")


if __name__ == "__main__":
    main()
