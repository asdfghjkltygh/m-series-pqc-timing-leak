#!/usr/bin/env python3
"""
phase2_split_and_filter.py

Phase 2: Strict Train/Val/Test split and quantile-based filtering.

CRITICAL ANTI-LEAKAGE CONSTRAINTS:
- Split is performed FIRST, before any analysis.
- Quantile thresholds are computed ONLY on the training set.
- Thresholds are then applied blindly to val/test sets.
- No information from val/test ever flows back.

Input:  data/raw_timing_traces.csv
Output: data/train.csv, data/val.csv, data/test.csv (filtered)
        data/split_metadata.json (thresholds, sizes, random seed)
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_CSV = os.path.join(PROJECT_DIR, "data", "raw_timing_traces.csv")
DATA_DIR = os.path.join(PROJECT_DIR, "data")

RANDOM_SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Quantile filtering: keep only measurements below this percentile
# (filters out OS-interrupt outliers from the right tail)
UPPER_QUANTILE = 0.10  # Keep bottom 10% = purest/fastest timings


def main():
    print("[Phase 2] Loading raw timing traces...")
    df = pd.read_csv(RAW_CSV)
    print(f"  Raw dataset: {len(df)} rows, columns: {list(df.columns)}")
    print(f"  Target byte value distribution: {df['target_byte'].nunique()} unique values")
    print(f"  Timing stats: min={df['timing_ns'].min()}, median={df['timing_ns'].median():.0f}, "
          f"mean={df['timing_ns'].mean():.0f}, max={df['timing_ns'].max()}")

    # --- STEP 1: Bin the target byte into classes ---
    # For ML-KEM-768, target_byte is 0-255. With 500 keys, many values are sparse.
    # We bin into a manageable number of classes. Use the LSB (bit 0) as a binary target
    # for initial experiments (easier classification problem).
    df["target_bit"] = df["target_byte"] & 1  # LSB of first secret key byte
    print(f"\n  Binary target (LSB of sk[0]): {df['target_bit'].value_counts().to_dict()}")

    # --- STEP 2: Strict train/val/test split ---
    # Split at the KEY level to prevent the same key's repeats from appearing in
    # both train and test (would be a form of data leakage).
    print("\n[Phase 2] Performing strict train/val/test split at KEY level...")

    # Create a key-level dataframe
    # Each unique (target_byte) represents one key's repeats
    # Actually, we need to group by the actual key identity.
    # Since each key has a unique sample_id range (sample_id = key_index * num_repeats + repeat),
    # we derive key_id.
    df["key_id"] = df["sample_id"] // df.groupby("target_byte")["sample_id"].transform("count").iloc[0]
    # More robust: use sample_id // num_repeats
    num_repeats = df.groupby(df["sample_id"] // 20)["sample_id"].count().mode().iloc[0]
    df["key_id"] = df["sample_id"] // num_repeats

    unique_keys = df["key_id"].unique()
    print(f"  Unique keys: {len(unique_keys)}")

    # Split keys, not individual measurements
    keys_train_val, keys_test = train_test_split(
        unique_keys, test_size=TEST_RATIO, random_state=RANDOM_SEED
    )
    keys_train, keys_val = train_test_split(
        keys_train_val, test_size=VAL_RATIO / (TRAIN_RATIO + VAL_RATIO),
        random_state=RANDOM_SEED
    )

    train_df = df[df["key_id"].isin(keys_train)].copy()
    val_df = df[df["key_id"].isin(keys_val)].copy()
    test_df = df[df["key_id"].isin(keys_test)].copy()

    print(f"  Train: {len(train_df)} rows ({len(keys_train)} keys)")
    print(f"  Val:   {len(val_df)} rows ({len(keys_val)} keys)")
    print(f"  Test:  {len(test_df)} rows ({len(keys_test)} keys)")

    # Verify no key overlap
    assert len(set(keys_train) & set(keys_val)) == 0, "LEAKAGE: train/val key overlap!"
    assert len(set(keys_train) & set(keys_test)) == 0, "LEAKAGE: train/test key overlap!"
    assert len(set(keys_val) & set(keys_test)) == 0, "LEAKAGE: val/test key overlap!"
    print("  ✓ No key overlap between splits (anti-leakage verified)")

    # --- STEP 3: Quantile filtering (TRAINING SET ONLY for threshold computation) ---
    print(f"\n[Phase 2] Computing quantile thresholds on TRAINING SET ONLY...")
    upper_threshold = train_df["timing_ns"].quantile(UPPER_QUANTILE)
    print(f"  Upper quantile threshold ({UPPER_QUANTILE*100:.0f}th percentile): {upper_threshold:.0f} ns")

    # We keep measurements BELOW the threshold (fastest/purest timings)
    train_filtered = train_df[train_df["timing_ns"] <= upper_threshold].copy()
    val_filtered = val_df[val_df["timing_ns"] <= upper_threshold].copy()
    test_filtered = test_df[test_df["timing_ns"] <= upper_threshold].copy()

    print(f"\n  After filtering (keeping timing_ns <= {upper_threshold:.0f} ns):")
    print(f"  Train: {len(train_filtered)} rows (kept {len(train_filtered)/len(train_df)*100:.1f}%)")
    print(f"  Val:   {len(val_filtered)} rows (kept {len(val_filtered)/len(val_df)*100:.1f}%)")
    print(f"  Test:  {len(test_filtered)} rows (kept {len(test_filtered)/len(test_df)*100:.1f}%)")

    # --- STEP 4: Save outputs ---
    train_filtered.to_csv(os.path.join(DATA_DIR, "train.csv"), index=False)
    val_filtered.to_csv(os.path.join(DATA_DIR, "val.csv"), index=False)
    test_filtered.to_csv(os.path.join(DATA_DIR, "test.csv"), index=False)

    metadata = {
        "random_seed": RANDOM_SEED,
        "split_ratios": {"train": TRAIN_RATIO, "val": VAL_RATIO, "test": TEST_RATIO},
        "split_level": "key_id (no same key in train and test)",
        "quantile_filtering": {
            "upper_quantile_percentile": UPPER_QUANTILE,
            "upper_threshold_ns": float(upper_threshold),
            "computed_on": "training set ONLY",
        },
        "sizes_raw": {
            "train": len(train_df), "val": len(val_df), "test": len(test_df)
        },
        "sizes_filtered": {
            "train": len(train_filtered), "val": len(val_filtered), "test": len(test_filtered)
        },
        "target": "target_bit (LSB of sk[0])",
        "num_unique_keys": int(len(unique_keys)),
    }
    with open(os.path.join(DATA_DIR, "split_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[Phase 2] Saved: train.csv, val.csv, test.csv, split_metadata.json")
    print(f"  Metadata: {json.dumps(metadata, indent=2)}")


if __name__ == "__main__":
    main()
