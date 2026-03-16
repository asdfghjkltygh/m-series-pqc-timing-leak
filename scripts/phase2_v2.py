#!/usr/bin/env python3
"""
phase2_v2.py

Phase 2 (upgraded): Strict data splitting, quantile filtering,
and per-key aggregate feature engineering.

Key improvements:
- Split at KEY level (strict anti-leakage)
- Multiple quantile thresholds explored
- Per-key aggregate features: min, median, Q10, Q25, variance, IQR of repeats
- Multiple target formulations: LSB, Hamming weight bins, individual coefficients

ANTI-LEAKAGE:
- ALL statistics (quantile thresholds, scaler params) computed on TRAIN ONLY.
- Val/test sets are transformed, never fit on.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RAW_CSV = os.path.join(DATA_DIR, "raw_timing_traces_v2.csv")

RANDOM_SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


def compute_per_key_features(group):
    """Compute aggregate timing features for one key's repeat measurements.
    These aggregate features reduce noise and capture the true timing signal.
    """
    t = group["timing_cycles"].values
    return pd.Series({
        "timing_min": np.min(t),
        "timing_q05": np.percentile(t, 5),
        "timing_q10": np.percentile(t, 10),
        "timing_q25": np.percentile(t, 25),
        "timing_median": np.median(t),
        "timing_mean": np.mean(t),
        "timing_std": np.std(t),
        "timing_iqr": np.percentile(t, 75) - np.percentile(t, 25),
        "timing_range": np.max(t) - np.min(t),
        "timing_skew": pd.Series(t).skew() if len(t) > 2 else 0,
        "num_repeats": len(t),
    })


def main():
    print("[Phase 2 v2] Loading raw timing traces...")
    df = pd.read_csv(RAW_CSV)
    print(f"  Raw dataset: {len(df)} rows")
    print(f"  Unique keys: {df['key_id'].nunique()}")
    print(f"  Timing stats (cycles): min={df['timing_cycles'].min()}, "
          f"median={df['timing_cycles'].median():.0f}, "
          f"mean={df['timing_cycles'].mean():.0f}, max={df['timing_cycles'].max()}")

    # --- STEP 1: Per-key outlier filtering (remove OS-interrupt spikes) ---
    # Compute per-key quantile thresholds on TRAINING keys only AFTER splitting.
    # But first, we need to split keys.

    coeff_cols = [c for c in df.columns if c.startswith("coeff_")]
    unique_keys = df["key_id"].unique()

    # --- STEP 2: Strict key-level split ---
    print("\n[Phase 2 v2] Strict train/val/test split at KEY level...")
    keys_train_val, keys_test = train_test_split(
        unique_keys, test_size=TEST_RATIO, random_state=RANDOM_SEED
    )
    keys_train, keys_val = train_test_split(
        keys_train_val, test_size=VAL_RATIO / (TRAIN_RATIO + VAL_RATIO),
        random_state=RANDOM_SEED
    )

    # Verify no overlap
    assert len(set(keys_train) & set(keys_val)) == 0
    assert len(set(keys_train) & set(keys_test)) == 0
    assert len(set(keys_val) & set(keys_test)) == 0
    print(f"  Train: {len(keys_train)} keys, Val: {len(keys_val)} keys, Test: {len(keys_test)} keys")
    print("  No key overlap (verified)")

    train_raw = df[df["key_id"].isin(keys_train)].copy()
    val_raw = df[df["key_id"].isin(keys_val)].copy()
    test_raw = df[df["key_id"].isin(keys_test)].copy()

    # --- STEP 3: Quantile filtering per repeat (TRAIN-derived threshold) ---
    # Compute the upper threshold from TRAINING data only.
    # We use multiple percentiles and keep several filtered versions.
    print("\n[Phase 2 v2] Computing quantile thresholds on TRAINING SET ONLY...")

    thresholds = {}
    for pct in [5, 10, 25, 50]:
        thresh = np.percentile(train_raw["timing_cycles"], pct)
        thresholds[f"p{pct}"] = float(thresh)
        print(f"  {pct}th percentile threshold: {thresh:.0f} cycles")

    # Primary filter: use 25th percentile (keep bottom quarter = cleanest timings)
    primary_threshold = thresholds["p25"]
    print(f"\n  Primary filter: keeping timing_cycles <= {primary_threshold:.0f} (25th pctile of train)")

    def filter_df(d, thresh):
        return d[d["timing_cycles"] <= thresh].copy()

    train_filt = filter_df(train_raw, primary_threshold)
    val_filt = filter_df(val_raw, primary_threshold)
    test_filt = filter_df(test_raw, primary_threshold)

    print(f"  After filtering: Train={len(train_filt)}, Val={len(val_filt)}, Test={len(test_filt)}")

    # --- STEP 4: Aggregate per-key features ---
    print("\n[Phase 2 v2] Computing per-key aggregate features...")

    def aggregate_split(d, split_name):
        # Get key-level labels (same for all repeats of a key)
        key_labels = d.groupby("key_id").first()[["hw_sum"] + coeff_cols].reset_index()

        # Compute aggregate timing features per key
        agg = d.groupby("key_id").apply(compute_per_key_features, include_groups=False).reset_index()

        # Merge labels back
        merged = agg.merge(key_labels, on="key_id")

        # Create multiple target formulations
        # 1. LSB of first coefficient
        merged["target_lsb_c0"] = merged["coeff_0"].astype(np.int64) % 2

        # 2. Hamming weight binned (low/high split at median)
        hw_values = merged["hw_sum"].values
        merged["target_hw_raw"] = hw_values

        # 3. Multi-bit: top 2 bits of coeff_0 (4 classes)
        merged["target_top2_c0"] = (merged["coeff_0"].astype(np.int64) // 1024) % 4

        # 4. Parity of hw_sum (even/odd)
        merged["target_hw_parity"] = merged["hw_sum"].astype(np.int64) % 2

        print(f"  {split_name}: {len(merged)} keys with aggregate features")
        return merged

    train_agg = aggregate_split(train_filt, "Train")
    val_agg = aggregate_split(val_filt, "Val")
    test_agg = aggregate_split(test_filt, "Test")

    # Hamming weight median threshold: compute on TRAIN ONLY
    hw_median_train = train_agg["target_hw_raw"].median()
    print(f"\n  HW median (from train): {hw_median_train}")
    train_agg["target_hw_bin"] = (train_agg["target_hw_raw"] >= hw_median_train).astype(int)
    val_agg["target_hw_bin"] = (val_agg["target_hw_raw"] >= hw_median_train).astype(int)
    test_agg["target_hw_bin"] = (test_agg["target_hw_raw"] >= hw_median_train).astype(int)

    # --- STEP 5: Save ---
    train_agg.to_csv(os.path.join(DATA_DIR, "train_v2.csv"), index=False)
    val_agg.to_csv(os.path.join(DATA_DIR, "val_v2.csv"), index=False)
    test_agg.to_csv(os.path.join(DATA_DIR, "test_v2.csv"), index=False)

    # Also save raw filtered (for CNN which may want individual traces)
    train_filt.to_csv(os.path.join(DATA_DIR, "train_v2_raw.csv"), index=False)
    val_filt.to_csv(os.path.join(DATA_DIR, "val_v2_raw.csv"), index=False)
    test_filt.to_csv(os.path.join(DATA_DIR, "test_v2_raw.csv"), index=False)

    metadata = {
        "random_seed": RANDOM_SEED,
        "split_ratios": {"train": TRAIN_RATIO, "val": VAL_RATIO, "test": TEST_RATIO},
        "split_level": "key_id (strict, no same key in multiple splits)",
        "quantile_thresholds_from_train": thresholds,
        "primary_filter_threshold_cycles": primary_threshold,
        "hw_median_threshold_from_train": float(hw_median_train),
        "sizes_raw": {
            "train": len(train_raw), "val": len(val_raw), "test": len(test_raw),
        },
        "sizes_filtered": {
            "train": len(train_filt), "val": len(val_filt), "test": len(test_filt),
        },
        "sizes_aggregated": {
            "train": len(train_agg), "val": len(val_agg), "test": len(test_agg),
        },
        "targets": [
            "target_lsb_c0: LSB of coeff_0 (binary)",
            "target_hw_bin: Hamming weight >= train median (binary)",
            "target_hw_parity: Parity of HW sum (binary)",
            "target_top2_c0: Top 2 bits of coeff_0 (4-class)",
        ],
        "features": [
            "timing_min", "timing_q05", "timing_q10", "timing_q25",
            "timing_median", "timing_mean", "timing_std", "timing_iqr",
            "timing_range", "timing_skew",
        ],
    }
    with open(os.path.join(DATA_DIR, "split_metadata_v2.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[Phase 2 v2] Complete. Files saved to {DATA_DIR}/")
    print(f"  Metadata: split_metadata_v2.json")


if __name__ == "__main__":
    main()
