#!/usr/bin/env python3
"""
Phase 6: Raw (Unaggregated) Trace Analysis
============================================
Addresses the critical reviewer objection:
  "If you aggregate 50 repeats per key into mean/median before running ML,
   you might destroy stochastic trace-level leakage that only appears on
   a small fraction of traces."

This script runs ML classification, Welch's t-test, KS test, and KSG MI
on every individual trace (no per-key averaging) to prove that no per-trace
secret-dependent timing signal exists.
"""

import json
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KDTree
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "raw_timing_traces_v3.csv"
OUT_JSON = PROJECT_ROOT / "data" / "phase6_raw_trace_results.json"

# ---------------------------------------------------------------------------
# Prior aggregated results (hardcoded from earlier experiments)
# ---------------------------------------------------------------------------
AGGREGATED_RESULTS = {
    "sk_lsb":        {"xgb_acc": 52.0, "baseline": 50.0, "lift": 2.0},
    "msg_hw_parity": {"xgb_acc": 52.0, "baseline": 50.0, "lift": 2.0},
    "valid_ct":      {"xgb_acc": 100.0, "baseline": 50.0, "lift": 50.0},
}

RANDOM_STATE = 42

# ===================================================================
# Utility: KSG mutual information estimator (k=3)
# ===================================================================

def _ksg_mi(x: np.ndarray, y_discrete: np.ndarray, k: int = 3) -> float:
    """KSG MI estimator between continuous x and discrete y."""
    from scipy.special import digamma

    n = len(x)
    classes = np.unique(y_discrete)
    x = x.reshape(-1, 1).astype(np.float64)

    # Build a KD-tree per class
    trees = {}
    nx = {}
    for c in classes:
        mask = y_discrete == c
        trees[c] = KDTree(x[mask], metric="chebyshev")
        nx[c] = mask.sum()

    # Full-data tree
    tree_all = KDTree(x, metric="chebyshev")

    mi = 0.0
    for c in classes:
        mask = y_discrete == c
        x_c = x[mask]
        nc = nx[c]
        if nc <= k:
            continue
        # k-th neighbour distance within class (exclude self -> k+1 then take k-th)
        dists, _ = trees[c].query(x_c, k=k + 1)
        eps = dists[:, -1]  # distance to k-th neighbour in class
        # Count neighbours in full dataset within eps (exclude self)
        for i in range(nc):
            r = eps[i]
            if r == 0:
                r = 1e-12
            m_i = tree_all.query_radius(x_c[i].reshape(1, -1), r=r, count_only=True)[0] - 1
            mi += digamma(nc) + digamma(k) - digamma(max(m_i, 1)) - digamma(n)
    mi /= n
    return max(mi, 0.0)


def _mi_permutation_pvalue(x, y, observed_mi, n_perm=100, k=3):
    """Permutation p-value for MI."""
    rng = np.random.RandomState(RANDOM_STATE)
    count = 0
    for _ in range(n_perm):
        y_shuf = rng.permutation(y)
        mi_shuf = _ksg_mi(x, y_shuf, k=k)
        if mi_shuf >= observed_mi:
            count += 1
    return (count + 1) / (n_perm + 1)


# ===================================================================
# Cohen's d
# ===================================================================

def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    pooled_std = np.sqrt(((na - 1) * a.std(ddof=1)**2 + (nb - 1) * b.std(ddof=1)**2) / (na + nb - 2))
    if pooled_std == 0:
        return 0.0
    return (a.mean() - b.mean()) / pooled_std


# ===================================================================
# Main analysis
# ===================================================================

def main():
    print("=" * 70)
    print("  PHASE 6: RAW (UNAGGREGATED) TRACE ANALYSIS")
    print("  Proving no per-trace secret-dependent timing signal exists")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Load raw traces
    # ------------------------------------------------------------------
    print(f"\n[1] Loading raw traces from {DATA_FILE.name} ...")
    df = pd.read_csv(DATA_FILE)
    n_traces = len(df)
    print(f"    Loaded {n_traces:,} individual decaps traces (no aggregation).")

    # ------------------------------------------------------------------
    # 2. Derive binary targets
    # ------------------------------------------------------------------
    print("\n[2] Deriving binary targets ...")
    df["sk_lsb"] = df["sk_byte0"] % 2
    df["msg_hw_parity"] = df["message_hw"] % 2
    # valid_ct already binary

    targets = ["sk_lsb", "msg_hw_parity", "valid_ct"]
    for t in targets:
        counts = df[t].value_counts()
        print(f"    {t}: {dict(counts)}")

    X_raw = df[["timing_cycles"]].values
    results = {}

    # ------------------------------------------------------------------
    # 3. Raw trace XGBoost classification
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[3] RAW TRACE XGBOOST CLASSIFICATION")
    print("-" * 70)
    xgb_results = {}
    if not HAS_XGBOOST:
        print("  XGBoost not available, skipping (install with: pip3 install xgboost, or use Docker).")
    else:
        for t in targets:
            y = df[t].values
            X_train, X_test, y_train, y_test = train_test_split(
                X_raw, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
            )
            clf = XGBClassifier(
                n_estimators=100, max_depth=6, use_label_encoder=False,
                eval_metric="logloss", verbosity=0, random_state=RANDOM_STATE
            )
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            acc = accuracy_score(y_test, y_pred) * 100
            baseline = max(y_test.mean(), 1 - y_test.mean()) * 100
            lift = acc - baseline
            xgb_results[t] = {"acc": round(acc, 2), "baseline": round(baseline, 2), "lift": round(lift, 2)}
            print(f"  {t:18s}  acc={acc:5.1f}%  baseline={baseline:5.1f}%  lift={lift:+5.1f}%")

    # ------------------------------------------------------------------
    # 4. Raw trace Random Forest classification
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[4] RAW TRACE RANDOM FOREST CLASSIFICATION")
    print("-" * 70)
    rf_results = {}
    for t in targets:
        y = df[t].values
        X_train, X_test, y_train, y_test = train_test_split(
            X_raw, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
        )
        clf = RandomForestClassifier(
            n_estimators=100, max_depth=6, random_state=RANDOM_STATE, n_jobs=-1
        )
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)
        acc = accuracy_score(y_test, y_pred) * 100
        baseline = max(y_test.mean(), 1 - y_test.mean()) * 100
        lift = acc - baseline
        rf_results[t] = {"acc": round(acc, 2), "baseline": round(baseline, 2), "lift": round(lift, 2)}
        print(f"  {t:18s}  acc={acc:5.1f}%  baseline={baseline:5.1f}%  lift={lift:+5.1f}%")

    # ------------------------------------------------------------------
    # 5. Raw trace Welch's t-test (pairwise)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[5] RAW TRACE WELCH'S T-TEST (PAIRWISE)")
    print("-" * 70)
    ttest_results = {}
    for t in targets:
        g0 = df.loc[df[t] == 0, "timing_cycles"].values.astype(np.float64)
        g1 = df.loc[df[t] == 1, "timing_cycles"].values.astype(np.float64)
        t_stat, p_val = stats.ttest_ind(g0, g1, equal_var=False)
        d = cohens_d(g0, g1)
        ttest_results[t] = {
            "t_stat": round(float(t_stat), 4),
            "p_value": float(f"{p_val:.4e}"),
            "cohens_d": round(float(d), 6),
            "n0": len(g0), "n1": len(g1),
        }
        print(f"  {t:18s}  t={t_stat:+8.4f}  p={p_val:.4e}  d={d:+.6f}  (n0={len(g0)}, n1={len(g1)})")

    # ------------------------------------------------------------------
    # 6. Raw trace KS test
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[6] RAW TRACE KS 2-SAMPLE TEST")
    print("-" * 70)
    ks_results = {}
    for t in targets:
        g0 = df.loc[df[t] == 0, "timing_cycles"].values.astype(np.float64)
        g1 = df.loc[df[t] == 1, "timing_cycles"].values.astype(np.float64)
        ks_stat, p_val = stats.ks_2samp(g0, g1)
        ks_results[t] = {"ks_stat": round(float(ks_stat), 6), "p_value": float(f"{p_val:.4e}")}
        print(f"  {t:18s}  D={ks_stat:.6f}  p={p_val:.4e}")

    # ------------------------------------------------------------------
    # 7. Raw trace KSG MI (subsample if needed)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[7] RAW TRACE KSG MUTUAL INFORMATION (with permutation test)")
    print("-" * 70)
    MI_SUBSAMPLE = 10_000
    mi_results = {}
    if n_traces > MI_SUBSAMPLE:
        rng = np.random.RandomState(RANDOM_STATE)
        idx = rng.choice(n_traces, MI_SUBSAMPLE, replace=False)
        x_mi = df["timing_cycles"].values[idx].astype(np.float64)
        print(f"  Subsampled to {MI_SUBSAMPLE:,} traces for MI estimation.")
    else:
        x_mi = df["timing_cycles"].values.astype(np.float64)
        idx = np.arange(n_traces)

    for t in targets:
        y_mi = df[t].values[idx]
        mi_obs = _ksg_mi(x_mi, y_mi)
        p_val = _mi_permutation_pvalue(x_mi, y_mi, mi_obs, n_perm=100)
        mi_results[t] = {"mi_bits": round(float(mi_obs), 6), "p_value": round(float(p_val), 4)}
        print(f"  {t:18s}  MI={mi_obs:.6f} bits  p={p_val:.4f}")

    # ------------------------------------------------------------------
    # 8. Comparison table
    # ------------------------------------------------------------------
    print("\n")
    print("=" * 70)
    print("  AGGREGATION MASKING ANALYSIS: RAW vs AGGREGATED TRACES")
    print("=" * 70)

    for t in targets:
        agg = AGGREGATED_RESULTS[t]
        xgb = xgb_results[t]
        rf = rf_results[t]
        tt = ttest_results[t]
        ks = ks_results[t]
        mi = mi_results[t]

        # Determine verdict
        secret_target = t in ("sk_lsb", "msg_hw_parity")
        if secret_target:
            # For secret targets: no signal expected
            signal = (
                abs(xgb["lift"]) > 3.0
                or abs(rf["lift"]) > 3.0
                or abs(tt["cohens_d"]) > 0.05
                or mi["p_value"] < 0.01
            )
            verdict = "SIGNAL DETECTED -- INVESTIGATE" if signal else "NO TRACE-LEVEL SIGNAL"
        else:
            # For valid_ct: signal expected
            signal = abs(xgb["lift"]) > 3.0 or abs(rf["lift"]) > 3.0
            verdict = "EXPECTED SIGNAL PRESENT (positive control)" if signal else "NO SIGNAL (unexpected)"

        print(f"\n  Target: {t}")
        print(f"    Raw XGBoost:        {xgb['acc']:5.1f}% (baseline {xgb['baseline']:5.1f}%, lift {xgb['lift']:+5.1f}%)")
        print(f"    Aggregated XGBoost: {agg['xgb_acc']:5.1f}% (baseline {agg['baseline']:5.1f}%, lift {agg['lift']:+5.1f}%)")
        print(f"    Raw RF:             {rf['acc']:5.1f}% (baseline {rf['baseline']:5.1f}%, lift {rf['lift']:+5.1f}%)")
        print(f"    Raw Welch's t:      t={tt['t_stat']:+8.4f}, p={tt['p_value']:.4e}, d={tt['cohens_d']:+.6f}")
        print(f"    Raw KS:             D={ks['ks_stat']:.6f}, p={ks['p_value']:.4e}")
        print(f"    Raw MI:             {mi['mi_bits']:.6f} bits, p={mi['p_value']:.4f}")
        print(f"    VERDICT: {verdict}")

    # ------------------------------------------------------------------
    # 9. Save results to JSON
    # ------------------------------------------------------------------
    all_results = {
        "n_raw_traces": n_traces,
        "analysis": "raw_unaggregated_traces",
        "targets": {},
    }
    for t in targets:
        all_results["targets"][t] = {
            "xgboost_raw": xgb_results[t],
            "random_forest_raw": rf_results[t],
            "welch_ttest": ttest_results[t],
            "ks_test": ks_results[t],
            "ksg_mi": mi_results[t],
            "aggregated_prior": AGGREGATED_RESULTS[t],
        }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[9] Results saved to {OUT_JSON}")

    print("\n" + "=" * 70)
    print("  PHASE 6 COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
