#!/usr/bin/env python3
"""
Phase 1: Model-Free Mutual Information via KSG Estimator

Uses sklearn's mutual_info_classif (KSG k-NN estimator) to compute
a non-parametric, model-free bound on mutual information between
timing features and secret targets.

If KSG MI ≈ 0, this is the absolute mathematical proof that no
information is extractable — independent of any model's quality.

ANTI-LEAKAGE: key-level split, all features computed from train only.
"""

import json
import os

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RANDOM_SEED = 42


def compute_features(raw, key_ids, spike_threshold):
    """Compute per-key aggregate features from raw timing traces."""
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
        feats["timing_p90"] = float(np.percentile(timings, 90))
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
        feats["spike_mean"] = float(np.mean(spikes)) if len(spikes) > 0 else 0

        feats["cv"] = feats["timing_std"] / max(feats["timing_mean"], 1)

        feats["key_id"] = kid
        feats["valid_ct"] = int(first["valid_ct"])
        feats["message_hw"] = int(first["message_hw"])
        feats["coeff0_hw"] = int(first["coeff0_hw"])
        feats["sk_byte0"] = int(first["sk_byte0"])
        rows.append(feats)

    df = pd.DataFrame(rows)
    df["target_rejection"] = (df["valid_ct"] == 0).astype(int)
    df["target_msg_hw_parity"] = df["message_hw"].astype(np.int64) % 2
    df["target_sk_lsb"] = df["sk_byte0"].astype(np.int64) % 2
    return df


def main():
    print("=" * 60)
    print("  PHASE 1: MODEL-FREE MUTUAL INFORMATION (KSG ESTIMATOR)")
    print("=" * 60)

    csv_path = os.path.join(DATA_DIR, "raw_timing_traces_v4_vertical.csv")
    raw = pd.read_csv(csv_path)
    print(f"\n  Raw data: {len(raw):,} traces, {raw['key_id'].nunique()} keys")

    # Key-level split
    unique_keys = raw["key_id"].unique()
    keys_tv, keys_test = train_test_split(unique_keys, test_size=0.15, random_state=RANDOM_SEED)
    keys_train, keys_val = train_test_split(keys_tv, test_size=0.15/0.85, random_state=RANDOM_SEED)
    print(f"  Train: {len(keys_train)} keys, Val: {len(keys_val)} keys, Test: {len(keys_test)} keys")

    # Spike threshold from train only
    train_raw = raw[raw["key_id"].isin(keys_train)]
    spike_threshold = float(np.percentile(train_raw["timing_cycles"], 95))

    # Build features
    train_df = compute_features(raw, keys_train, spike_threshold)
    test_df = compute_features(raw, keys_test, spike_threshold)

    feature_cols = [c for c in train_df.columns
                    if c.startswith("timing_") or c.startswith("spike_") or c == "cv"]
    print(f"  Features ({len(feature_cols)}): {feature_cols}")

    # Scale (fit on train only)
    scaler = StandardScaler()
    X_train = np.nan_to_num(scaler.fit_transform(train_df[feature_cols].values))
    X_test = np.nan_to_num(scaler.transform(test_df[feature_cols].values))

    targets = {
        "target_sk_lsb": "LSB of sk[0]",
        "target_msg_hw_parity": "Message HW parity",
        "target_rejection": "FO rejection",
    }

    results = {}

    for target_name, target_desc in targets.items():
        print(f"\n{'='*50}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'='*50}")

        y_train = train_df[target_name].values

        # KSG Mutual Information (classification — discrete target)
        # Run multiple times with different random states for stability
        mi_runs = []
        for rs in range(10):
            mi = mutual_info_classif(
                X_train, y_train,
                discrete_features=False,
                n_neighbors=5,
                random_state=rs
            )
            mi_runs.append(mi)

        mi_mean = np.mean(mi_runs, axis=0)
        mi_std = np.std(mi_runs, axis=0)

        print(f"\n  [KSG Mutual Information — Classification (10 runs)]")
        print(f"  {'Feature':<25} {'MI (mean)':>12} {'MI (std)':>12}")
        print(f"  {'-'*50}")

        for i, feat in enumerate(feature_cols):
            print(f"  {feat:<25} {mi_mean[i]:>12.6f} {mi_std[i]:>12.6f}")

        total_mi = float(np.sum(mi_mean))
        max_mi = float(np.max(mi_mean))
        best_feat = feature_cols[np.argmax(mi_mean)]

        print(f"\n  Total MI (sum): {total_mi:.6f} nats")
        print(f"  Max MI (single feature): {max_mi:.6f} nats ({best_feat})")
        print(f"  Max MI in bits: {max_mi / np.log(2):.6f} bits")

        # Context: for a binary target with equal priors, H(Y) = ln(2) ≈ 0.693 nats
        h_y = -np.sum(p * np.log(p) for p in [np.mean(y_train == 0), np.mean(y_train == 1)] if p > 0)
        print(f"  H(Y) = {h_y:.6f} nats ({h_y/np.log(2):.6f} bits)")
        print(f"  Max MI / H(Y) = {max_mi/h_y:.6f} ({max_mi/h_y*100:.4f}%)")

        if max_mi < 0.01:
            print(f"\n  *** KSG MI effectively ZERO — no information in ANY feature.")
        elif max_mi < 0.05:
            print(f"\n  KSG MI very low — negligible information.")
        else:
            print(f"\n  KSG MI detectable — investigate further.")

        # Also compute MI for the continuous Hamming weight (regression)
        if target_name == "target_msg_hw_parity":
            y_cont = train_df["message_hw"].values.astype(float)
        elif target_name == "target_sk_lsb":
            y_cont = train_df["sk_byte0"].values.astype(float)
        else:
            y_cont = train_df["valid_ct"].values.astype(float)

        mi_reg = mutual_info_regression(
            X_train, y_cont,
            discrete_features=False,
            n_neighbors=5,
            random_state=RANDOM_SEED
        )

        print(f"\n  [KSG Mutual Information — Regression (continuous target)]")
        max_mi_reg = float(np.max(mi_reg))
        best_feat_reg = feature_cols[np.argmax(mi_reg)]
        print(f"  Max MI (regression): {max_mi_reg:.6f} nats ({best_feat_reg})")
        print(f"  Max MI in bits: {max_mi_reg / np.log(2):.6f} bits")

        results[target_name] = {
            "ksg_mi_classif_per_feature": {f: float(mi_mean[i]) for i, f in enumerate(feature_cols)},
            "ksg_mi_classif_max": max_mi,
            "ksg_mi_classif_max_bits": float(max_mi / np.log(2)),
            "ksg_mi_classif_best_feature": best_feat,
            "ksg_mi_regression_max": max_mi_reg,
            "ksg_mi_regression_max_bits": float(max_mi_reg / np.log(2)),
            "ksg_mi_regression_best_feature": best_feat_reg,
            "target_entropy_nats": float(h_y),
            "target_entropy_bits": float(h_y / np.log(2)),
            "mi_over_entropy_pct": float(max_mi / h_y * 100),
        }

    # Summary
    print(f"\n{'='*60}")
    print(f"  PHASE 1 SUMMARY: KSG MUTUAL INFORMATION")
    print(f"{'='*60}")
    for t, r in results.items():
        print(f"\n  {t}:")
        print(f"    Classif MI (max): {r['ksg_mi_classif_max']:.6f} nats "
              f"= {r['ksg_mi_classif_max_bits']:.6f} bits "
              f"({r['mi_over_entropy_pct']:.4f}% of H(Y))")
        print(f"    Regress MI (max): {r['ksg_mi_regression_max']:.6f} nats "
              f"= {r['ksg_mi_regression_max_bits']:.6f} bits")

    with open(os.path.join(DATA_DIR, "phase1_ksg_mi.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to phase1_ksg_mi.json")


if __name__ == "__main__":
    main()
