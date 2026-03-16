#!/usr/bin/env python3
"""
phase2_v3.py

Phase 2 (v3): KDE-based feature engineering + KyberSlash-aware targets.

Key changes from v2:
1. KDE feature engineering: fit Gaussian KDE to each key's repeats,
   sample at fixed percentiles → smooth distributional features
2. KyberSlash-aware targets: valid_ct (rejection path), message_hw
3. Larger dataset, more repeats per key

ANTI-LEAKAGE:
- Key-level split (strict)
- KDE bandwidth estimated on TRAIN ONLY
- All thresholds from TRAIN ONLY
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from sklearn.model_selection import train_test_split

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RAW_CSV = os.path.join(DATA_DIR, "raw_timing_traces_v3.csv")

RANDOM_SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Fixed percentile grid for KDE sampling
KDE_PERCENTILES = np.linspace(0, 1, 21)[1:-1]  # 19 points from 0.05 to 0.95


def compute_kde_features(timings, bandwidth=None):
    """
    Fit Gaussian KDE to timing array, sample at fixed percentiles.
    Returns feature dict with KDE samples + traditional aggregate stats.
    """
    features = {}

    if len(timings) < 3:
        # Not enough data for KDE, fall back to basic stats
        for i, p in enumerate(KDE_PERCENTILES):
            features[f"kde_p{int(p*100):02d}"] = np.percentile(timings, p * 100) if len(timings) > 0 else 0
        features["timing_min"] = np.min(timings) if len(timings) > 0 else 0
        features["timing_median"] = np.median(timings) if len(timings) > 0 else 0
        features["timing_std"] = np.std(timings) if len(timings) > 1 else 0
        features["timing_iqr"] = 0
        features["timing_skew"] = 0
        features["timing_kurtosis"] = 0
        features["num_repeats"] = len(timings)
        return features

    # Fit KDE
    try:
        if bandwidth is not None:
            kde = gaussian_kde(timings, bw_method=bandwidth)
        else:
            kde = gaussian_kde(timings)  # Scott's rule

        # Sample KDE at fixed percentiles of the data range
        sorted_t = np.sort(timings)
        eval_points = np.percentile(sorted_t, KDE_PERCENTILES * 100)

        # KDE density at these points (captures distributional shape)
        kde_densities = kde(eval_points)
        for i, p in enumerate(KDE_PERCENTILES):
            features[f"kde_p{int(p*100):02d}"] = float(eval_points[i])
            features[f"kde_d{int(p*100):02d}"] = float(kde_densities[i])
    except Exception:
        for i, p in enumerate(KDE_PERCENTILES):
            features[f"kde_p{int(p*100):02d}"] = np.percentile(timings, p * 100)
            features[f"kde_d{int(p*100):02d}"] = 0.0

    # Traditional aggregate features (retained for comparison)
    features["timing_min"] = float(np.min(timings))
    features["timing_median"] = float(np.median(timings))
    features["timing_mean"] = float(np.mean(timings))
    features["timing_std"] = float(np.std(timings))
    features["timing_iqr"] = float(np.percentile(timings, 75) - np.percentile(timings, 25))
    features["timing_skew"] = float(pd.Series(timings).skew()) if len(timings) > 2 else 0
    features["timing_kurtosis"] = float(pd.Series(timings).kurtosis()) if len(timings) > 3 else 0
    features["num_repeats"] = len(timings)

    return features


def main():
    print("[Phase 2 v3] Loading raw timing traces...")
    df = pd.read_csv(RAW_CSV)
    print(f"  Raw dataset: {len(df):,} rows, {df['key_id'].nunique()} keys")
    print(f"  Timing: min={df['timing_cycles'].min()}, median={df['timing_cycles'].median():.0f}, "
          f"mean={df['timing_cycles'].mean():.0f}, max={df['timing_cycles'].max()}")
    print(f"  Valid CTs: {(df['valid_ct']==1).sum():,}, Invalid CTs: {(df['valid_ct']==0).sum():,}")

    # --- Key-level split ---
    unique_keys = df["key_id"].unique()
    print(f"\n[Phase 2 v3] Key-level split ({len(unique_keys)} keys)...")

    keys_train_val, keys_test = train_test_split(
        unique_keys, test_size=TEST_RATIO, random_state=RANDOM_SEED
    )
    keys_train, keys_val = train_test_split(
        keys_train_val, test_size=VAL_RATIO / (TRAIN_RATIO + VAL_RATIO),
        random_state=RANDOM_SEED
    )

    assert len(set(keys_train) & set(keys_val)) == 0
    assert len(set(keys_train) & set(keys_test)) == 0
    assert len(set(keys_val) & set(keys_test)) == 0
    print(f"  Train: {len(keys_train)} keys, Val: {len(keys_val)} keys, Test: {len(keys_test)} keys")

    train_raw = df[df["key_id"].isin(keys_train)]
    val_raw = df[df["key_id"].isin(keys_val)]
    test_raw = df[df["key_id"].isin(keys_test)]

    # --- Quantile filtering (TRAIN-derived threshold) ---
    print("\n[Phase 2 v3] Quantile filtering (train-derived)...")
    filter_pct = 0.25
    thresh = np.percentile(train_raw["timing_cycles"], filter_pct * 100)
    print(f"  Threshold: {thresh:.0f} cycles ({filter_pct*100:.0f}th pctile of train)")

    train_filt = train_raw[train_raw["timing_cycles"] <= thresh].copy()
    val_filt = val_raw[val_raw["timing_cycles"] <= thresh].copy()
    test_filt = test_raw[test_raw["timing_cycles"] <= thresh].copy()
    print(f"  After filtering: Train={len(train_filt):,}, Val={len(val_filt):,}, Test={len(test_filt):,}")

    # --- KDE bandwidth estimation on TRAIN ONLY ---
    print("\n[Phase 2 v3] Estimating KDE bandwidth on TRAINING SET ONLY...")
    # Use Scott's rule on a random subsample of training timings
    train_sample = train_filt["timing_cycles"].sample(
        min(10000, len(train_filt)), random_state=RANDOM_SEED
    ).values
    pilot_kde = gaussian_kde(train_sample)
    bandwidth = pilot_kde.factor
    print(f"  KDE bandwidth (Scott's rule): {bandwidth:.6f}")

    # --- Per-key KDE feature engineering ---
    print("\n[Phase 2 v3] Computing KDE features per key...")

    def process_split(raw_df, filt_df, split_name):
        rows = []
        key_ids = filt_df["key_id"].unique()
        for i, key_id in enumerate(key_ids):
            key_data = filt_df[filt_df["key_id"] == key_id]
            timings = key_data["timing_cycles"].values

            # Get labels (same for all repeats of a key)
            first_row = key_data.iloc[0]
            valid_ct = int(first_row["valid_ct"])
            message_hw = int(first_row["message_hw"])
            coeff0_hw = int(first_row["coeff0_hw"])
            sk_byte0 = int(first_row["sk_byte0"])

            # KDE features
            feats = compute_kde_features(timings, bandwidth=bandwidth)
            feats["key_id"] = key_id
            feats["valid_ct"] = valid_ct
            feats["message_hw"] = message_hw
            feats["coeff0_hw"] = coeff0_hw
            feats["sk_byte0"] = sk_byte0

            rows.append(feats)

            if (i + 1) % 500 == 0:
                print(f"  {split_name}: {i+1}/{len(key_ids)} keys processed")

        result = pd.DataFrame(rows)

        # Create target variables
        result["target_rejection"] = (result["valid_ct"] == 0).astype(int)
        result["target_msg_hw_parity"] = result["message_hw"].astype(np.int64) % 2
        result["target_coeff0_hw_bin"] = (result["coeff0_hw"] >= result["coeff0_hw"].median()).astype(int)
        result["target_sk_lsb"] = result["sk_byte0"].astype(np.int64) % 2

        print(f"  {split_name}: {len(result)} keys with KDE + aggregate features")
        return result

    train_agg = process_split(train_raw, train_filt, "Train")
    val_agg = process_split(val_raw, val_filt, "Val")
    test_agg = process_split(test_raw, test_filt, "Test")

    # Recompute target_coeff0_hw_bin using TRAIN median
    coeff0_hw_median = train_agg["coeff0_hw"].median()
    train_agg["target_coeff0_hw_bin"] = (train_agg["coeff0_hw"] >= coeff0_hw_median).astype(int)
    val_agg["target_coeff0_hw_bin"] = (val_agg["coeff0_hw"] >= coeff0_hw_median).astype(int)
    test_agg["target_coeff0_hw_bin"] = (test_agg["coeff0_hw"] >= coeff0_hw_median).astype(int)

    # Message HW binary using TRAIN median
    msg_hw_median = train_agg["message_hw"].median()
    train_agg["target_msg_hw_bin"] = (train_agg["message_hw"] >= msg_hw_median).astype(int)
    val_agg["target_msg_hw_bin"] = (val_agg["message_hw"] >= msg_hw_median).astype(int)
    test_agg["target_msg_hw_bin"] = (test_agg["message_hw"] >= msg_hw_median).astype(int)

    # Save
    train_agg.to_csv(os.path.join(DATA_DIR, "train_v3.csv"), index=False)
    val_agg.to_csv(os.path.join(DATA_DIR, "val_v3.csv"), index=False)
    test_agg.to_csv(os.path.join(DATA_DIR, "test_v3.csv"), index=False)

    # Save raw filtered for sequence models
    train_filt.to_csv(os.path.join(DATA_DIR, "train_v3_raw.csv"), index=False)
    val_filt.to_csv(os.path.join(DATA_DIR, "val_v3_raw.csv"), index=False)
    test_filt.to_csv(os.path.join(DATA_DIR, "test_v3_raw.csv"), index=False)

    # Feature names for ML
    kde_p_features = [f"kde_p{int(p*100):02d}" for p in KDE_PERCENTILES]
    kde_d_features = [f"kde_d{int(p*100):02d}" for p in KDE_PERCENTILES]
    agg_features = ["timing_min", "timing_median", "timing_mean",
                     "timing_std", "timing_iqr", "timing_skew", "timing_kurtosis"]
    all_features = kde_p_features + kde_d_features + agg_features

    metadata = {
        "random_seed": RANDOM_SEED,
        "split_level": "key_id (strict)",
        "filter_threshold_cycles": float(thresh),
        "filter_percentile": filter_pct,
        "kde_bandwidth": float(bandwidth),
        "kde_percentile_grid": KDE_PERCENTILES.tolist(),
        "coeff0_hw_median_from_train": float(coeff0_hw_median),
        "msg_hw_median_from_train": float(msg_hw_median),
        "sizes": {
            "train": len(train_agg), "val": len(val_agg), "test": len(test_agg),
        },
        "feature_names": all_features,
        "targets": [
            "target_rejection: valid(0) vs mutated(1) ciphertext",
            "target_msg_hw_parity: parity of message HW",
            "target_msg_hw_bin: message HW >= train median",
            "target_coeff0_hw_bin: coeff0 HW >= train median",
            "target_sk_lsb: LSB of sk[0] (legacy comparison)",
        ],
    }
    with open(os.path.join(DATA_DIR, "split_metadata_v3.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[Phase 2 v3] Complete.")
    print(f"  Features: {len(all_features)} ({len(kde_p_features)} KDE quantile + "
          f"{len(kde_d_features)} KDE density + {len(agg_features)} aggregate)")
    print(f"  Targets: 5 (rejection, msg_hw_parity, msg_hw_bin, coeff0_hw_bin, sk_lsb)")


if __name__ == "__main__":
    main()
