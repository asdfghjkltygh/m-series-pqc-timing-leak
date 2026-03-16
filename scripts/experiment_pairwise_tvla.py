#!/usr/bin/env python3
"""
experiment_pairwise_tvla.py

Gemini Recommendation A2: Pairwise TVLA

Instead of fixed-vs-random, run Welch's t-test between SPECIFIC key
property groups to find which key properties cause distinguishable
timing distributions.

Groups tested:
- valid_ct=1 vs valid_ct=0 (FO rejection path)
- message_hw parity=0 vs parity=1
- sk_byte0 LSB=0 vs LSB=1
- sk_byte0 high (>=128) vs low (<128)
- coeff0_hw high (>=median) vs low (<median)

Also: per-key variance analysis to test if the leakage is in the
variance (as TVLA suggests), not the mean.

ANTI-LEAKAGE: All thresholds computed on train keys only.
"""

import json
import os

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.model_selection import train_test_split

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RANDOM_SEED = 42


def welch_ttest(a, b):
    """Welch's t-test (unequal variance)."""
    t, p = sp_stats.ttest_ind(a, b, equal_var=False)
    return float(t), float(p)


def levene_test(a, b):
    """Levene's test for equality of variances."""
    stat, p = sp_stats.levene(a, b)
    return float(stat), float(p)


def main():
    print("=" * 60)
    print("  EXPERIMENT: PAIRWISE TVLA (Gemini A2)")
    print("=" * 60)

    raw = pd.read_csv(os.path.join(DATA_DIR, "raw_timing_traces_v3.csv"))
    print(f"\n  Raw data: {len(raw):,} traces, {raw['key_id'].nunique()} keys")

    # Key-level split
    unique_keys = raw["key_id"].unique()
    keys_tv, keys_test = train_test_split(unique_keys, test_size=0.15, random_state=RANDOM_SEED)
    keys_train, keys_val = train_test_split(keys_tv, test_size=0.15/0.85, random_state=RANDOM_SEED)

    # Use TEST keys only for evaluation (train used only for threshold computation)
    test_raw = raw[raw["key_id"].isin(keys_test)]
    train_raw = raw[raw["key_id"].isin(keys_train)]

    # Get per-key metadata (first row per key)
    key_meta = test_raw.groupby("key_id").first().reset_index()

    results = {}
    total_tests = 0

    # ==== Test 1: Direct trace-level TVLA by group ====
    print(f"\n{'='*50}")
    print(f"  TRACE-LEVEL PAIRWISE TVLA")
    print(f"{'='*50}")

    groupings = {
        "valid_ct": lambda row: row["valid_ct"] == 1,
        "msg_hw_parity": lambda row: row["message_hw"] % 2 == 0,
        "sk_lsb": lambda row: row["sk_byte0"] % 2 == 0,
        "sk_byte0_high": lambda row: row["sk_byte0"] >= 128,
        "coeff0_hw_high": lambda row: row["coeff0_hw"] >= int(train_raw["coeff0_hw"].median()),
    }

    for name, group_fn in groupings.items():
        mask = test_raw.apply(group_fn, axis=1)
        group_a = test_raw.loc[mask, "timing_cycles"].values
        group_b = test_raw.loc[~mask, "timing_cycles"].values

        t_stat, p_val = welch_ttest(group_a, group_b)
        lev_stat, lev_p = levene_test(group_a, group_b)
        total_tests += 2

        print(f"\n  {name}:")
        print(f"    Group A: n={len(group_a):,}, mean={np.mean(group_a):.2f}, "
              f"std={np.std(group_a):.2f}, median={np.median(group_a):.1f}")
        print(f"    Group B: n={len(group_b):,}, mean={np.mean(group_b):.2f}, "
              f"std={np.std(group_b):.2f}, median={np.median(group_b):.1f}")
        print(f"    Welch t={t_stat:.4f}, p={p_val:.2e}  "
              f"{'*** LEAKAGE' if abs(t_stat) > 4.5 else '(not significant)'}")
        print(f"    Levene F={lev_stat:.4f}, p={lev_p:.2e}  "
              f"{'*** VARIANCE DIFFERS' if lev_p < 0.001 else '(variances similar)'}")

        results[f"trace_{name}"] = {
            "welch_t": t_stat, "welch_p": p_val,
            "levene_F": lev_stat, "levene_p": lev_p,
            "n_a": len(group_a), "n_b": len(group_b),
            "mean_a": float(np.mean(group_a)), "mean_b": float(np.mean(group_b)),
            "std_a": float(np.std(group_a)), "std_b": float(np.std(group_b)),
        }

    # ==== Test 2: Per-key aggregate TVLA ====
    print(f"\n{'='*50}")
    print(f"  PER-KEY AGGREGATE TVLA (mean timing per key)")
    print(f"{'='*50}")

    # Compute per-key statistics
    key_stats = test_raw.groupby("key_id").agg(
        timing_mean=("timing_cycles", "mean"),
        timing_std=("timing_cycles", "std"),
        timing_median=("timing_cycles", "median"),
        timing_max=("timing_cycles", "max"),
        timing_var=("timing_cycles", "var"),
    ).reset_index()
    key_stats = key_stats.merge(key_meta[["key_id", "valid_ct", "message_hw", "coeff0_hw", "sk_byte0"]])

    for stat_name in ["timing_mean", "timing_std", "timing_var", "timing_max", "timing_median"]:
        print(f"\n  --- Using {stat_name} as test statistic ---")
        for name, col, fn in [
            ("valid_ct", "valid_ct", lambda x: x == 1),
            ("msg_hw_parity", "message_hw", lambda x: x % 2 == 0),
            ("sk_lsb", "sk_byte0", lambda x: x % 2 == 0),
        ]:
            mask = fn(key_stats[col])
            a = key_stats.loc[mask, stat_name].values
            b = key_stats.loc[~mask, stat_name].values

            t_stat, p_val = welch_ttest(a, b)
            total_tests += 1

            sig = "*** SIGNIFICANT" if abs(t_stat) > 4.5 else "(not significant)"
            print(f"    {name:<20} t={t_stat:>8.4f}, p={p_val:.4e}  {sig}")

            results[f"key_{stat_name}_{name}"] = {
                "welch_t": t_stat, "welch_p": p_val,
                "n_a": len(a), "n_b": len(b),
                "mean_a": float(np.mean(a)), "mean_b": float(np.mean(b)),
            }

    # ==== Test 3: Variance-ratio analysis ====
    print(f"\n{'='*50}")
    print(f"  VARIANCE RATIO ANALYSIS (inspired by TVLA finding)")
    print(f"{'='*50}")
    print(f"  (TVLA showed fixed has 10x higher variance than random)")

    for name, col, fn in [
        ("valid_ct", "valid_ct", lambda x: x == 1),
        ("msg_hw_parity", "message_hw", lambda x: x % 2 == 0),
        ("sk_lsb", "sk_byte0", lambda x: x % 2 == 0),
    ]:
        mask = fn(key_stats[col])
        var_a = key_stats.loc[mask, "timing_var"].values
        var_b = key_stats.loc[~mask, "timing_var"].values
        ratio = np.mean(var_a) / max(np.mean(var_b), 1)

        # F-test (ratio of variances)
        f_stat = np.var(var_a) / max(np.var(var_b), 1)

        print(f"  {name}: mean_var_A={np.mean(var_a):.1f}, mean_var_B={np.mean(var_b):.1f}, "
              f"ratio={ratio:.4f}")

        results[f"var_ratio_{name}"] = {
            "mean_var_a": float(np.mean(var_a)),
            "mean_var_b": float(np.mean(var_b)),
            "ratio": ratio,
        }

    # ==== Test 4: Kolmogorov-Smirnov test on per-key distributions ====
    print(f"\n{'='*50}")
    print(f"  KS TEST ON PER-KEY TIMING DISTRIBUTIONS")
    print(f"{'='*50}")

    for name, col, fn in [
        ("valid_ct", "valid_ct", lambda x: x == 1),
        ("msg_hw_parity", "message_hw", lambda x: x % 2 == 0),
        ("sk_lsb", "sk_byte0", lambda x: x % 2 == 0),
    ]:
        mask_keys = fn(key_meta[col])
        keys_a = key_meta.loc[mask_keys, "key_id"].values
        keys_b = key_meta.loc[~mask_keys, "key_id"].values

        timings_a = test_raw[test_raw["key_id"].isin(keys_a)]["timing_cycles"].values
        timings_b = test_raw[test_raw["key_id"].isin(keys_b)]["timing_cycles"].values

        ks_stat, ks_p = sp_stats.ks_2samp(timings_a, timings_b)
        total_tests += 1

        sig = "*** SIGNIFICANT" if ks_p < 0.001 else "(not significant)"
        print(f"  {name}: KS={ks_stat:.6f}, p={ks_p:.4e}  {sig}")

        results[f"ks_{name}"] = {
            "ks_stat": ks_stat, "ks_p": ks_p,
            "n_a": len(timings_a), "n_b": len(timings_b),
        }

    # Summary
    bonf_alpha = 0.05 / max(total_tests, 1)
    print(f"\n{'='*60}")
    print(f"  SUMMARY (Bonferroni α={bonf_alpha:.6f}, {total_tests} tests)")
    print(f"{'='*60}")

    significant = []
    for name, res in results.items():
        if "welch_p" in res:
            if res["welch_p"] < bonf_alpha:
                significant.append((name, res["welch_t"], res["welch_p"]))
        if "ks_p" in res:
            if res["ks_p"] < bonf_alpha:
                significant.append((name, res["ks_stat"], res["ks_p"]))

    if significant:
        print(f"\n  SIGNIFICANT RESULTS:")
        for name, stat, p in significant:
            print(f"    {name}: stat={stat:.4f}, p={p:.2e}")
    else:
        print(f"\n  NO significant results after Bonferroni correction.")

    with open(os.path.join(DATA_DIR, "experiment_pairwise_tvla.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved to experiment_pairwise_tvla.json")


if __name__ == "__main__":
    main()
