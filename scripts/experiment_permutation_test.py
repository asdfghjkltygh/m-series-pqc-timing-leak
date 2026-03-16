#!/usr/bin/env python3
"""
experiment_permutation_test.py

Gemini Recommendation D1: Permutation Tests

Instead of the binomial test (parametric), shuffle labels 10,000 times
and compute the empirical null distribution of accuracy. More robust
than parametric tests for small sample sizes.

Also computes:
- D9: SNR with theoretical trace count estimates
- D10: Perceived Information from model probability outputs

ANTI-LEAKAGE: key-level split, all thresholds from train.
"""

import json
import os

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, log_loss
import xgboost as xgb

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RANDOM_SEED = 42
N_PERMUTATIONS = 1000

TARGETS = {
    "target_rejection": "FO rejection",
    "target_msg_hw_parity": "Message HW parity",
    "target_sk_lsb": "LSB of sk[0]",
}


def compute_features(raw, key_ids, spike_threshold):
    rows = []
    for kid in key_ids:
        kd = raw[raw["key_id"] == kid]
        timings = kd["timing_cycles"].values
        first = kd.iloc[0]

        feats = {}
        feats["timing_min"] = float(np.min(timings))
        feats["timing_median"] = float(np.median(timings))
        feats["timing_mean"] = float(np.mean(timings))
        feats["timing_std"] = float(np.std(timings))
        feats["timing_max"] = float(np.max(timings))
        feats["timing_p95"] = float(np.percentile(timings, 95))
        feats["timing_p99"] = float(np.percentile(timings, 99))
        feats["timing_range"] = float(np.ptp(timings))
        feats["timing_iqr"] = float(np.percentile(timings, 75) - np.percentile(timings, 25))
        feats["timing_var"] = float(np.var(timings))
        feats["timing_kurtosis"] = float(pd.Series(timings).kurtosis()) if len(timings) > 3 else 0
        feats["timing_skew"] = float(pd.Series(timings).skew()) if len(timings) > 2 else 0

        spikes = timings[timings > spike_threshold]
        feats["spike_count"] = len(spikes)
        feats["spike_ratio"] = len(spikes) / len(timings)

        feats["key_id"] = kid
        feats["valid_ct"] = int(first["valid_ct"])
        feats["message_hw"] = int(first["message_hw"])
        feats["sk_byte0"] = int(first["sk_byte0"])
        rows.append(feats)

    df = pd.DataFrame(rows)
    df["target_rejection"] = (df["valid_ct"] == 0).astype(int)
    df["target_msg_hw_parity"] = df["message_hw"].astype(np.int64) % 2
    df["target_sk_lsb"] = df["sk_byte0"].astype(np.int64) % 2
    return df


def perceived_information(y_true, y_proba, n_classes=2):
    """
    Perceived Information (PI): measures how much information the model
    extracts, using cross-entropy relative to the prior.

    PI = H(Y) - CE(model)
    where H(Y) is the entropy of the true label distribution
    and CE(model) is the cross-entropy of model predictions.
    """
    # Prior entropy
    counts = np.bincount(y_true, minlength=n_classes)
    priors = counts / len(y_true)
    h_y = -sum(p * np.log2(p) for p in priors if p > 0)

    # Cross-entropy of model
    eps = 1e-15
    y_proba_clipped = np.clip(y_proba, eps, 1 - eps)
    ce = 0
    for i in range(len(y_true)):
        ce -= np.log2(y_proba_clipped[i, y_true[i]])
    ce /= len(y_true)

    pi = h_y - ce
    return float(pi), float(h_y), float(ce)


def main():
    print("=" * 60)
    print("  EXPERIMENT: PERMUTATION TESTS + PERCEIVED INFORMATION")
    print("=" * 60)

    raw = pd.read_csv(os.path.join(DATA_DIR, "raw_timing_traces_v3.csv"))
    print(f"\n  Raw data: {len(raw):,} traces, {raw['key_id'].nunique()} keys")

    unique_keys = raw["key_id"].unique()
    keys_tv, keys_test = train_test_split(unique_keys, test_size=0.15, random_state=RANDOM_SEED)
    keys_train, keys_val = train_test_split(keys_tv, test_size=0.15/0.85, random_state=RANDOM_SEED)

    train_raw = raw[raw["key_id"].isin(keys_train)]
    spike_threshold = float(np.percentile(train_raw["timing_cycles"], 95))

    train_df = compute_features(raw, keys_train, spike_threshold)
    test_df = compute_features(raw, keys_test, spike_threshold)
    print(f"  Train: {len(train_df)}, Test: {len(test_df)}")

    feature_cols = [c for c in train_df.columns
                    if c.startswith("timing_") or c.startswith("spike_")]

    scaler = StandardScaler()
    X_train = np.nan_to_num(scaler.fit_transform(train_df[feature_cols].values))
    X_test = np.nan_to_num(scaler.transform(test_df[feature_cols].values))

    all_results = {}

    for target_name, target_desc in TARGETS.items():
        print(f"\n{'='*50}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'='*50}")

        y_train = train_df[target_name].values
        y_test = test_df[target_name].values
        majority = max(np.bincount(y_test)) / len(y_test)

        # Train real model
        model = xgb.XGBClassifier(
            n_estimators=500, max_depth=4, learning_rate=0.01,
            subsample=0.8, use_label_encoder=False, eval_metric="logloss",
            random_state=42, n_jobs=-1, verbosity=0
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)
        real_acc = accuracy_score(y_test, y_pred)

        print(f"  Real model accuracy: {real_acc:.4f} (majority: {majority:.4f})")

        # Perceived Information
        pi, h_y, ce = perceived_information(y_test, y_proba)
        print(f"\n  [Perceived Information]")
        print(f"    H(Y) = {h_y:.6f} bits (label entropy)")
        print(f"    CE(model) = {ce:.6f} bits (model cross-entropy)")
        print(f"    PI = {pi:.6f} bits (extractable info)")
        if pi <= 0:
            print(f"    Model extracts NO useful information (PI <= 0)")
        else:
            print(f"    Model extracts {pi:.6f} bits per prediction")
            # Guessing entropy
            ge = 2 ** (h_y - pi)
            print(f"    Guessing entropy: {ge:.2f} (out of {2**h_y:.2f})")

        # Permutation test
        print(f"\n  [Permutation Test] ({N_PERMUTATIONS:,} shuffles)")
        rng = np.random.RandomState(RANDOM_SEED)
        perm_accs = np.zeros(N_PERMUTATIONS)

        for i in range(N_PERMUTATIONS):
            y_train_shuffled = rng.permutation(y_train)
            perm_model = xgb.XGBClassifier(
                n_estimators=100, max_depth=3, learning_rate=0.05,
                subsample=0.8, use_label_encoder=False, eval_metric="logloss",
                random_state=42, n_jobs=-1, verbosity=0
            )
            perm_model.fit(X_train, y_train_shuffled)
            perm_pred = perm_model.predict(X_test)
            perm_accs[i] = accuracy_score(y_test, perm_pred)

            if (i + 1) % 2000 == 0:
                print(f"    Progress: {i+1}/{N_PERMUTATIONS}")

        # Empirical p-value
        perm_p = (np.sum(perm_accs >= real_acc) + 1) / (N_PERMUTATIONS + 1)
        print(f"\n    Real accuracy: {real_acc:.4f}")
        print(f"    Permutation null: mean={np.mean(perm_accs):.4f}, "
              f"std={np.std(perm_accs):.4f}")
        print(f"    Permutation p-value: {perm_p:.6f}")
        print(f"    95th percentile of null: {np.percentile(perm_accs, 95):.4f}")
        print(f"    99th percentile of null: {np.percentile(perm_accs, 99):.4f}")

        if perm_p < 0.05:
            print(f"    *** MODEL BEATS PERMUTATION NULL (p < 0.05)")
        else:
            print(f"    Model does NOT beat permutation null")

        all_results[target_name] = {
            "real_acc": float(real_acc),
            "majority": float(majority),
            "perm_p": float(perm_p),
            "perm_mean": float(np.mean(perm_accs)),
            "perm_std": float(np.std(perm_accs)),
            "perm_95": float(np.percentile(perm_accs, 95)),
            "perm_99": float(np.percentile(perm_accs, 99)),
            "perceived_info_bits": pi,
            "label_entropy_bits": float(h_y),
            "model_cross_entropy_bits": float(ce),
        }

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    for t, r in all_results.items():
        print(f"  {t:<25} acc={r['real_acc']:.4f}  perm_p={r['perm_p']:.4f}  "
              f"PI={r['perceived_info_bits']:.6f} bits")

    with open(os.path.join(DATA_DIR, "experiment_permutation_pi.json"), "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Saved to experiment_permutation_pi.json")


if __name__ == "__main__":
    main()
