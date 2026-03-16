#!/usr/bin/env python3
"""
Phase 3: Higher-Order / Feature Interaction Analysis

Since we only have scalar cycle counts per decapsulation (not sequences
of sub-operations), we must look for second-order leakage via variance
modulation rather than mean shifts.

Engineers second-order interaction features (centered products) and
tests whether these capture any signal the first-order features miss.

ANTI-LEAKAGE: key-level split, all centering/scaling from train only.
"""

import json
import os
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import xgboost as xgb

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RANDOM_SEED = 42

TARGETS = {
    "target_rejection": "FO rejection",
    "target_msg_hw_parity": "Message HW parity",
    "target_sk_lsb": "LSB of sk[0]",
}


def binomial_test(y_true, y_pred, null_p=0.5):
    n = len(y_true)
    k = int(np.sum(y_pred == y_true))
    result = sp_stats.binomtest(k, n, null_p, alternative="greater")
    return result.pvalue, k, n


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
        feats["sk_byte0"] = int(first["sk_byte0"])
        rows.append(feats)

    df = pd.DataFrame(rows)
    df["target_rejection"] = (df["valid_ct"] == 0).astype(int)
    df["target_msg_hw_parity"] = df["message_hw"].astype(np.int64) % 2
    df["target_sk_lsb"] = df["sk_byte0"].astype(np.int64) % 2
    return df


def main():
    print("=" * 60)
    print("  PHASE 3: HIGHER-ORDER / FEATURE INTERACTION ANALYSIS")
    print("=" * 60)

    csv_path = os.path.join(DATA_DIR, "raw_timing_traces_v4_vertical.csv")
    raw = pd.read_csv(csv_path)
    print(f"\n  Raw data: {len(raw):,} traces, {raw['key_id'].nunique()} keys")

    unique_keys = raw["key_id"].unique()
    keys_tv, keys_test = train_test_split(unique_keys, test_size=0.15, random_state=RANDOM_SEED)
    keys_train, keys_val = train_test_split(keys_tv, test_size=0.15/0.85, random_state=RANDOM_SEED)

    train_raw = raw[raw["key_id"].isin(keys_train)]
    spike_threshold = float(np.percentile(train_raw["timing_cycles"], 95))

    train_df = compute_features(raw, keys_train, spike_threshold)
    test_df = compute_features(raw, keys_test, spike_threshold)

    first_order_cols = [c for c in train_df.columns
                        if c.startswith("timing_") or c.startswith("spike_") or c == "cv"]

    # Scale first-order features (fit on train only)
    scaler = StandardScaler()
    X_train_1st = np.nan_to_num(scaler.fit_transform(train_df[first_order_cols].values))
    X_test_1st = np.nan_to_num(scaler.transform(test_df[first_order_cols].values))

    # Generate second-order interaction features (centered products)
    # Select a subset of key features to avoid explosion
    key_features = ["timing_mean", "timing_var", "timing_std", "timing_p99",
                     "timing_kurtosis", "timing_skew", "spike_count", "spike_ratio",
                     "timing_max", "timing_iqr", "cv"]
    key_indices = [first_order_cols.index(f) for f in key_features if f in first_order_cols]

    interaction_names = []
    X_train_2nd_list = []
    X_test_2nd_list = []

    for i, j in combinations(range(len(key_indices)), 2):
        idx_i = key_indices[i]
        idx_j = key_indices[j]
        name_i = first_order_cols[idx_i]
        name_j = first_order_cols[idx_j]

        # Centered product (interaction)
        prod_train = X_train_1st[:, idx_i] * X_train_1st[:, idx_j]
        prod_test = X_test_1st[:, idx_i] * X_test_1st[:, idx_j]

        interaction_names.append(f"{name_i}×{name_j}")
        X_train_2nd_list.append(prod_train)
        X_test_2nd_list.append(prod_test)

    # Also add squared terms
    for i in range(len(key_indices)):
        idx_i = key_indices[i]
        name_i = first_order_cols[idx_i]
        sq_train = X_train_1st[:, idx_i] ** 2
        sq_test = X_test_1st[:, idx_i] ** 2
        interaction_names.append(f"{name_i}²")
        X_train_2nd_list.append(sq_train)
        X_test_2nd_list.append(sq_test)

    X_train_2nd = np.column_stack(X_train_2nd_list)
    X_test_2nd = np.column_stack(X_test_2nd_list)

    # Combine first-order + second-order
    X_train_all = np.hstack([X_train_1st, X_train_2nd])
    X_test_all = np.hstack([X_test_1st, X_test_2nd])

    all_feature_names = first_order_cols + interaction_names
    print(f"\n  First-order features: {len(first_order_cols)}")
    print(f"  Second-order features: {len(interaction_names)}")
    print(f"  Total features: {len(all_feature_names)}")

    results = {}
    total_tests = 0

    for target_name, target_desc in TARGETS.items():
        print(f"\n{'='*50}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'='*50}")

        y_train = train_df[target_name].values
        y_test = test_df[target_name].values
        majority = max(np.bincount(y_test)) / len(y_test)

        # Test 1: First-order features only (baseline)
        model_1st = xgb.XGBClassifier(
            n_estimators=500, max_depth=4, learning_rate=0.01,
            subsample=0.8, use_label_encoder=False, eval_metric="logloss",
            random_state=42, n_jobs=-1, verbosity=0
        )
        model_1st.fit(X_train_1st, y_train)
        pred_1st = model_1st.predict(X_test_1st)
        acc_1st = accuracy_score(y_test, pred_1st)
        p_1st, _, _ = binomial_test(y_test, pred_1st, majority)
        total_tests += 1
        print(f"\n  [First-order only]")
        print(f"    Acc={acc_1st:.4f}, p={p_1st:.4f}, majority={majority:.4f}")

        # Test 2: Second-order features only
        model_2nd = xgb.XGBClassifier(
            n_estimators=500, max_depth=4, learning_rate=0.01,
            subsample=0.8, use_label_encoder=False, eval_metric="logloss",
            random_state=42, n_jobs=-1, verbosity=0
        )
        model_2nd.fit(X_train_2nd, y_train)
        pred_2nd = model_2nd.predict(X_test_2nd)
        acc_2nd = accuracy_score(y_test, pred_2nd)
        p_2nd, _, _ = binomial_test(y_test, pred_2nd, majority)
        total_tests += 1
        print(f"\n  [Second-order only]")
        print(f"    Acc={acc_2nd:.4f}, p={p_2nd:.4f}, majority={majority:.4f}")

        # Test 3: Combined first + second order
        model_all = xgb.XGBClassifier(
            n_estimators=500, max_depth=4, learning_rate=0.01,
            subsample=0.8, use_label_encoder=False, eval_metric="logloss",
            random_state=42, n_jobs=-1, verbosity=0
        )
        model_all.fit(X_train_all, y_train)
        pred_all = model_all.predict(X_test_all)
        acc_all = accuracy_score(y_test, pred_all)
        p_all, _, _ = binomial_test(y_test, pred_all, majority)
        total_tests += 1
        print(f"\n  [First + Second order combined]")
        print(f"    Acc={acc_all:.4f}, p={p_all:.4f}, majority={majority:.4f}")

        # Top interaction features by importance
        imps = sorted(zip(all_feature_names, model_all.feature_importances_),
                       key=lambda x: x[1], reverse=True)
        print(f"\n    Top features (combined model):")
        for f, imp in imps[:10]:
            order = "2nd" if "×" in f or "²" in f else "1st"
            print(f"      [{order}] {f:<35} {imp:.4f}")

        results[target_name] = {
            "first_order_acc": float(acc_1st), "first_order_p": float(p_1st),
            "second_order_acc": float(acc_2nd), "second_order_p": float(p_2nd),
            "combined_acc": float(acc_all), "combined_p": float(p_all),
            "majority": float(majority),
            "top_features": {f: float(imp) for f, imp in imps[:15]},
        }

    # Summary
    bonf_alpha = 0.05 / max(total_tests, 1)
    print(f"\n{'='*60}")
    print(f"  PHASE 3 SUMMARY (Bonferroni α={bonf_alpha:.6f}, {total_tests} tests)")
    print(f"{'='*60}")
    print(f"  {'Target':<25} {'1st Acc':>8} {'2nd Acc':>8} {'Comb Acc':>8} {'Majority':>8}")
    print(f"  {'-'*57}")
    for t, r in results.items():
        print(f"  {t:<25} {r['first_order_acc']:>8.4f} {r['second_order_acc']:>8.4f} "
              f"{r['combined_acc']:>8.4f} {r['majority']:>8.4f}")

    any_sig = any(
        r["first_order_p"] < bonf_alpha or r["second_order_p"] < bonf_alpha or r["combined_p"] < bonf_alpha
        for r in results.values()
    )
    if any_sig:
        print(f"\n  *** SOME RESULTS SIGNIFICANT — investigate further")
    else:
        print(f"\n  *** NO significant results. Second-order features add nothing.")

    with open(os.path.join(DATA_DIR, "phase3_interactions.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to phase3_interactions.json")


if __name__ == "__main__":
    main()
