#!/usr/bin/env python3
"""
Phase 4: Distributional Tests & Natural FO Rejection

- KS (Kolmogorov-Smirnov) test between secret-dependent groups
- Anderson-Darling k-sample test
- Natural FO rejection target: compare valid vs invalid CT timing distributions
- Levene's test for variance differences
"""

import json
import os
import numpy as np
import pandas as pd
from scipy import stats

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CSV = os.path.join(PROJECT_DIR, "data", "raw_timing_traces_v4_vertical.csv")
OUTPUT_JSON = os.path.join(PROJECT_DIR, "data", "phase4_distributional_tests.json")


def anderson_darling_2sample(x, y):
    """Anderson-Darling 2-sample test."""
    try:
        result = stats.anderson_ksamp([x, y])
        return float(result.statistic), float(result.pvalue)
    except Exception:
        return None, None


def main():
    print("=" * 60)
    print("PHASE 4: Distributional Tests & Natural FO Rejection")
    print("=" * 60)

    df = pd.read_csv(DATA_CSV)
    print(f"  Loaded {len(df):,} traces, {df['key_id'].nunique()} keys")

    # Aggregate
    agg = df.groupby("key_id").agg(
        timing_mean=("timing_cycles", "mean"),
        timing_median=("timing_cycles", "median"),
        timing_std=("timing_cycles", "std"),
        timing_iqr=("timing_cycles", lambda x: np.percentile(x, 75) - np.percentile(x, 25)),
        valid_ct=("valid_ct", "first"),
        message_hw=("message_hw", "first"),
        coeff0_hw=("coeff0_hw", "first"),
        sk_byte0=("sk_byte0", "first"),
    ).reset_index()

    agg["sk_byte0_lsb"] = agg["sk_byte0"] % 2
    agg["sk_byte0_parity"] = agg["sk_byte0"].apply(lambda x: bin(x).count("1") % 2)
    agg["msg_hw_parity"] = agg["message_hw"] % 2

    targets = ["sk_byte0_lsb", "sk_byte0_parity", "valid_ct", "msg_hw_parity"]
    timing_features = ["timing_mean", "timing_median", "timing_std", "timing_iqr"]

    results = {"experiment": "distributional_tests"}

    # 1. KS Tests
    print("\n  --- Kolmogorov-Smirnov Tests ---")
    ks_results = {}
    for target in targets:
        ks_results[target] = {}
        g0 = agg.loc[agg[target] == 0]
        g1 = agg.loc[agg[target] == 1]
        for feat in timing_features:
            stat, pval = stats.ks_2samp(g0[feat].values, g1[feat].values)
            ks_results[target][feat] = {"statistic": float(stat), "p_value": float(pval)}
        best_feat = min(ks_results[target], key=lambda f: ks_results[target][f]["p_value"])
        best_p = ks_results[target][best_feat]["p_value"]
        sig = "SIG" if best_p < 0.05 else "ns"
        print(f"    {target}: best KS on {best_feat}, D={ks_results[target][best_feat]['statistic']:.4f}, "
              f"p={best_p:.4e} [{sig}]")
    results["ks_tests"] = ks_results

    # 2. Anderson-Darling 2-sample Tests
    print("\n  --- Anderson-Darling 2-Sample Tests ---")
    ad_results = {}
    for target in targets:
        g0 = agg.loc[agg[target] == 0, "timing_mean"].values
        g1 = agg.loc[agg[target] == 1, "timing_mean"].values
        ad_stat, ad_p = anderson_darling_2sample(g0, g1)
        ad_results[target] = {"statistic": ad_stat, "p_value": ad_p}
        sig = "SIG" if ad_p is not None and ad_p < 0.05 else "ns"
        print(f"    {target}: AD={ad_stat:.4f}, p={ad_p:.4e} [{sig}]" if ad_stat else f"    {target}: failed")
    results["anderson_darling"] = ad_results

    # 3. Levene's Test (variance equality)
    print("\n  --- Levene's Test (Variance Equality) ---")
    levene_results = {}
    for target in targets:
        g0 = agg.loc[agg[target] == 0, "timing_mean"].values
        g1 = agg.loc[agg[target] == 1, "timing_mean"].values
        stat, pval = stats.levene(g0, g1)
        levene_results[target] = {"statistic": float(stat), "p_value": float(pval)}
        sig = "SIG" if pval < 0.05 else "ns"
        print(f"    {target}: W={stat:.4f}, p={pval:.4e} [{sig}]")
    results["levene"] = levene_results

    # 4. Natural FO Rejection Analysis (raw trace level)
    print("\n  --- Natural FO Rejection (Raw Trace Level) ---")
    valid_times = df.loc[df["valid_ct"] == 1, "timing_cycles"].values
    invalid_times = df.loc[df["valid_ct"] == 0, "timing_cycles"].values
    print(f"    Valid CTs: n={len(valid_times):,}, mean={np.mean(valid_times):.1f}, "
          f"median={np.median(valid_times):.1f}")
    print(f"    Invalid CTs: n={len(invalid_times):,}, mean={np.mean(invalid_times):.1f}, "
          f"median={np.median(invalid_times):.1f}")

    ks_stat, ks_p = stats.ks_2samp(valid_times[:50000], invalid_times[:50000])
    t_stat, t_p = stats.ttest_ind(valid_times, invalid_times, equal_var=False)
    mw_stat, mw_p = stats.mannwhitneyu(valid_times[:50000], invalid_times[:50000],
                                         alternative='two-sided')

    fo_results = {
        "n_valid": int(len(valid_times)),
        "n_invalid": int(len(invalid_times)),
        "valid_mean": float(np.mean(valid_times)),
        "invalid_mean": float(np.mean(invalid_times)),
        "valid_median": float(np.median(valid_times)),
        "invalid_median": float(np.median(invalid_times)),
        "ks_statistic": float(ks_stat),
        "ks_p_value": float(ks_p),
        "welch_t": float(t_stat),
        "welch_p": float(t_p),
        "mann_whitney_stat": float(mw_stat),
        "mann_whitney_p": float(mw_p),
    }
    results["fo_rejection_raw"] = fo_results
    print(f"    KS: D={ks_stat:.4f}, p={ks_p:.4e}")
    print(f"    Welch's t: t={t_stat:.2f}, p={t_p:.4e}")
    print(f"    Mann-Whitney U: p={mw_p:.4e}")

    # Save
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
