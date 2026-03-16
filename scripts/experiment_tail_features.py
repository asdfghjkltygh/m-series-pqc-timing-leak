#!/usr/bin/env python3
"""
experiment_tail_features.py

Gemini Recommendation A1: "Embrace the Right Tail"

Instead of filtering OUT the slow traces, use the RIGHT TAIL
as the primary signal source. The TVLA result shows the fixed
distribution has 10x higher variance — the information is in
the rare spikes, not the fast measurements.

Features: p95, p99, max, spike_count, spike_ratio, tail_mean,
tail_std, variance_ratio, range, kurtosis.

Uses the FULL v3 raw data (no quantile filtering).

ANTI-LEAKAGE: key-level split, spike threshold from train only.
"""

import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
import xgboost as xgb

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RANDOM_SEED = 42

TARGETS = {
    "target_rejection": "FO rejection (valid vs invalid CT)",
    "target_msg_hw_parity": "Message HW parity",
    "target_sk_lsb": "LSB of sk[0]",
}


def binomial_test(y_true, y_pred, null_p=0.5):
    n = len(y_true)
    k = int(np.sum(y_pred == y_true))
    result = sp_stats.binomtest(k, n, null_p, alternative="greater")
    return result.pvalue, k, n


def compute_tail_features(timings, spike_threshold):
    """Extract RIGHT-TAIL features from timing array. No filtering."""
    features = {}
    features["timing_min"] = float(np.min(timings))
    features["timing_median"] = float(np.median(timings))
    features["timing_mean"] = float(np.mean(timings))
    features["timing_std"] = float(np.std(timings))
    features["timing_max"] = float(np.max(timings))
    features["timing_p90"] = float(np.percentile(timings, 90))
    features["timing_p95"] = float(np.percentile(timings, 95))
    features["timing_p99"] = float(np.percentile(timings, 99))
    features["timing_range"] = float(np.max(timings) - np.min(timings))
    features["timing_iqr"] = float(np.percentile(timings, 75) - np.percentile(timings, 25))
    features["timing_kurtosis"] = float(pd.Series(timings).kurtosis()) if len(timings) > 3 else 0
    features["timing_skew"] = float(pd.Series(timings).skew()) if len(timings) > 2 else 0
    features["timing_var"] = float(np.var(timings))

    # Spike features: how many measurements exceed the spike threshold
    spikes = timings[timings > spike_threshold]
    features["spike_count"] = len(spikes)
    features["spike_ratio"] = len(spikes) / len(timings)
    features["spike_mean"] = float(np.mean(spikes)) if len(spikes) > 0 else 0
    features["spike_max"] = float(np.max(spikes)) if len(spikes) > 0 else 0

    # Tail heaviness: ratio of p99 to median
    features["tail_ratio_99_med"] = features["timing_p99"] / max(features["timing_median"], 1)
    features["tail_ratio_max_med"] = features["timing_max"] / max(features["timing_median"], 1)

    # Coefficient of variation
    features["cv"] = features["timing_std"] / max(features["timing_mean"], 1)

    return features


def main():
    print("=" * 60)
    print("  EXPERIMENT: RIGHT-TAIL FEATURES (Gemini A1)")
    print("=" * 60)

    # Load FULL raw v3 data (NO quantile filtering)
    raw = pd.read_csv(os.path.join(DATA_DIR, "raw_timing_traces_v3.csv"))
    print(f"\n  Raw data: {len(raw):,} traces, {raw['key_id'].nunique()} keys")
    print(f"  Using ALL traces (no quantile filtering)")

    # Key-level split
    unique_keys = raw["key_id"].unique()
    keys_tv, keys_test = train_test_split(unique_keys, test_size=0.15, random_state=RANDOM_SEED)
    keys_train, keys_val = train_test_split(keys_tv, test_size=0.15/0.85, random_state=RANDOM_SEED)

    assert len(set(keys_train) & set(keys_test)) == 0
    assert len(set(keys_val) & set(keys_test)) == 0

    # Compute spike threshold from TRAIN data only
    train_raw = raw[raw["key_id"].isin(keys_train)]
    spike_threshold = float(np.percentile(train_raw["timing_cycles"], 95))
    print(f"  Spike threshold (95th pctile of train): {spike_threshold:.0f} cycles")

    # Build features for each split
    def build_features(key_ids, split_name):
        rows = []
        for kid in key_ids:
            key_data = raw[raw["key_id"] == kid]
            timings = key_data["timing_cycles"].values
            first = key_data.iloc[0]

            feats = compute_tail_features(timings, spike_threshold)
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
        print(f"  {split_name}: {len(df)} keys")
        return df

    train_df = build_features(keys_train, "Train")
    val_df = build_features(keys_val, "Val")
    test_df = build_features(keys_test, "Test")

    feature_cols = [c for c in train_df.columns if c.startswith("timing_") or
                    c.startswith("spike_") or c.startswith("tail_") or c == "cv"]
    print(f"\n  Features ({len(feature_cols)}): {feature_cols}")

    scaler = StandardScaler()
    X_train = scaler.fit_transform(train_df[feature_cols].values)
    X_val = scaler.transform(val_df[feature_cols].values)
    X_test = scaler.transform(test_df[feature_cols].values)

    # Replace NaN/inf
    X_train = np.nan_to_num(X_train, nan=0, posinf=0, neginf=0)
    X_val = np.nan_to_num(X_val, nan=0, posinf=0, neginf=0)
    X_test = np.nan_to_num(X_test, nan=0, posinf=0, neginf=0)

    all_results = {}
    total_tests = 0

    for target_name, target_desc in TARGETS.items():
        print(f"\n{'-'*50}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'-'*50}")

        y_train = train_df[target_name].values
        y_val = val_df[target_name].values
        y_test = test_df[target_name].values
        majority = max(np.bincount(y_test)) / len(y_test)
        print(f"  Class balance (test): {np.bincount(y_test)}, majority: {majority:.4f}")

        # XGBoost
        best_acc = -1
        best_model = None
        for params in [
            {"n_estimators": 500, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.8},
            {"n_estimators": 800, "max_depth": 5, "learning_rate": 0.01, "subsample": 0.9},
            {"n_estimators": 1000, "max_depth": 4, "learning_rate": 0.01, "subsample": 0.8,
             "colsample_bytree": 0.7},
        ]:
            model = xgb.XGBClassifier(**params, use_label_encoder=False,
                                       eval_metric="logloss", random_state=42, n_jobs=-1)
            model.fit(X_train, y_train)
            acc = accuracy_score(y_val, model.predict(X_val))
            if acc > best_acc:
                best_acc = acc
                best_model = model

        # Test evaluation
        y_pred = best_model.predict(X_test)
        test_acc = accuracy_score(y_test, y_pred)
        p_val, k, n = binomial_test(y_test, y_pred, majority)
        total_tests += 1

        print(f"  Val acc: {best_acc:.4f}")
        print(f"  TEST acc: {test_acc:.4f}, p={p_val:.6f} (vs majority {majority:.4f})")

        # Feature importance
        imps = sorted(zip(feature_cols, best_model.feature_importances_),
                       key=lambda x: x[1], reverse=True)
        print(f"  Top features:")
        for f, i in imps[:7]:
            print(f"    {f:<25s} {i:.4f}")

        all_results[target_name] = {
            "test_acc": test_acc, "p_value": p_val, "majority": majority,
            "val_acc": best_acc, "top_features": {f: float(i) for f, i in imps[:10]},
        }

    # Summary
    bonf_alpha = 0.05 / max(total_tests, 1)
    print(f"\n{'='*60}")
    print(f"  TAIL FEATURES SUMMARY (Bonferroni α={bonf_alpha:.4f})")
    print(f"{'='*60}")
    for t, r in all_results.items():
        sig = "YES***" if r["p_value"] < bonf_alpha else "no"
        print(f"  {t:<25} acc={r['test_acc']:.4f}  p={r['p_value']:.6f}  {sig}")

    with open(os.path.join(DATA_DIR, "experiment_tail_results.json"), "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Saved to experiment_tail_results.json")


if __name__ == "__main__":
    main()
