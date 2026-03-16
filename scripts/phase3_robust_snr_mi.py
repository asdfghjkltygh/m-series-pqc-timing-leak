#!/usr/bin/env python3
"""
Phase 3: Robust SNR & Permutation MI

- MAD-based (Median Absolute Deviation) SNR — robust to outliers
- Winsorized SNR (clip at 1st/99th percentile)
- KSG Mutual Information with permutation test (100 shuffles)
"""

import json
import os
import numpy as np
import pandas as pd
from scipy import stats

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CSV = os.path.join(PROJECT_DIR, "data", "raw_timing_traces_v4_vertical.csv")
OUTPUT_JSON = os.path.join(PROJECT_DIR, "data", "phase3_robust_snr_mi.json")


def mad(x):
    """Median Absolute Deviation."""
    return np.median(np.abs(x - np.median(x)))


def mad_snr(df, target_col):
    """Signal = MAD of group medians, Noise = median of within-group MADs."""
    grouped = df.groupby(target_col)["timing_mean"]
    group_medians = grouped.median()
    signal = mad(group_medians.values)
    group_mads = grouped.apply(lambda x: mad(x.values))
    noise = np.median(group_mads.values)
    return float(signal / noise) if noise > 0 else 0.0


def winsorized_snr(df, target_col, pct=0.01):
    """SNR after winsorizing timing at pct and 1-pct."""
    t = df["timing_mean"].values
    lo, hi = np.percentile(t, [pct * 100, (1 - pct) * 100])
    t_win = np.clip(t, lo, hi)
    df_win = df.copy()
    df_win["timing_mean"] = t_win
    grouped = df_win.groupby(target_col)["timing_mean"]
    group_means = grouped.mean()
    signal_var = np.var(group_means.values)
    noise_var = np.mean(grouped.var().values)
    return float(signal_var / noise_var) if noise_var > 0 else 0.0


def ksg_mi_permutation(X, y, n_permutations=100, k=5):
    """KSG MI with permutation test."""
    from sklearn.feature_selection import mutual_info_classif

    # Observed MI
    mi_obs = mutual_info_classif(X.reshape(-1, 1), y, n_neighbors=k, random_state=42)[0]

    # Permutation null
    mi_null = []
    for i in range(n_permutations):
        y_perm = np.random.RandomState(i).permutation(y)
        mi_perm = mutual_info_classif(X.reshape(-1, 1), y_perm, n_neighbors=k, random_state=42)[0]
        mi_null.append(mi_perm)

    mi_null = np.array(mi_null)
    p_value = float(np.mean(mi_null >= mi_obs))
    return float(mi_obs), float(np.mean(mi_null)), float(np.std(mi_null)), p_value


def main():
    print("=" * 60)
    print("PHASE 3: Robust SNR & Permutation MI")
    print("=" * 60)

    df = pd.read_csv(DATA_CSV)
    print(f"  Loaded {len(df):,} traces, {df['key_id'].nunique()} keys")

    # Aggregate
    agg = df.groupby("key_id").agg(
        timing_mean=("timing_cycles", "mean"),
        timing_median=("timing_cycles", "median"),
        valid_ct=("valid_ct", "first"),
        message_hw=("message_hw", "first"),
        coeff0_hw=("coeff0_hw", "first"),
        sk_byte0=("sk_byte0", "first"),
    ).reset_index()

    agg["sk_byte0_lsb"] = agg["sk_byte0"] % 2
    agg["sk_byte0_parity"] = agg["sk_byte0"].apply(lambda x: bin(x).count("1") % 2)
    agg["msg_hw_parity"] = agg["message_hw"] % 2

    targets = ["sk_byte0_lsb", "sk_byte0_parity", "valid_ct", "msg_hw_parity"]

    results = {"experiment": "robust_snr_permutation_mi"}

    # 1. MAD-based SNR
    print("\n  --- MAD-based SNR ---")
    mad_results = {}
    for t in targets:
        snr = mad_snr(agg, t)
        mad_results[t] = snr
        print(f"    {t}: MAD-SNR = {snr:.6f}")
    results["mad_snr"] = mad_results

    # 2. Winsorized SNR
    print("\n  --- Winsorized SNR (1st/99th percentile) ---")
    win_results = {}
    for t in targets:
        snr = winsorized_snr(agg, t, pct=0.01)
        win_results[t] = snr
        print(f"    {t}: Winsorized-SNR = {snr:.6f}")
    results["winsorized_snr"] = win_results

    # 3. KSG MI with permutation test
    print("\n  --- KSG MI with Permutation Test (100 shuffles) ---")
    mi_results = {}
    X = agg["timing_mean"].values
    for t in targets:
        y = agg[t].values
        mi_obs, mi_null_mean, mi_null_std, p_val = ksg_mi_permutation(X, y, n_permutations=100)
        mi_results[t] = {
            "mi_observed": mi_obs,
            "mi_null_mean": mi_null_mean,
            "mi_null_std": mi_null_std,
            "p_value": p_val,
            "significant_005": bool(p_val < 0.05),
        }
        sig = "SIGNIFICANT" if p_val < 0.05 else "not significant"
        print(f"    {t}: MI_obs={mi_obs:.6f}, MI_null={mi_null_mean:.6f}±{mi_null_std:.6f}, "
              f"p={p_val:.3f} [{sig}]")
    results["ksg_mi_permutation"] = mi_results

    # Save
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
