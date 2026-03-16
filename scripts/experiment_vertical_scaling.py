#!/usr/bin/env python3
"""
experiment_vertical_scaling.py

Gemini Recommendation C7: Vertical Scaling
200 keys × 5000 repeats = 1M traces.

SNR analysis predicted ~331 repeats needed per key for target_msg_hw_parity.
With 5000 repeats, we have 15× the predicted minimum. If this still fails,
the leakage is definitively non-exploitable.

Includes:
- Right-tail features (A1)
- Wasserstein distance (B6)
- Template attacks (B5)
- SNR recalculation with richer data
- Progressive analysis: how does accuracy change with 50, 100, 500, 1000, 5000 repeats?

ANTI-LEAKAGE: key-level split, all thresholds from train.
"""

import json
import os

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from scipy.stats import multivariate_normal, wasserstein_distance
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from sklearn.dummy import DummyClassifier
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


def compute_features(timings, spike_threshold, reference_dist):
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

    # Wasserstein
    if reference_dist is not None:
        feats["wasserstein"] = float(wasserstein_distance(
            timings[:min(1000, len(timings))],
            reference_dist[:min(1000, len(reference_dist))]
        ))
    else:
        feats["wasserstein"] = 0
    return feats


def compute_snr(X, y, feature_names):
    classes = np.unique(y)
    snr = {}
    for i, feat in enumerate(feature_names):
        xi = X[:, i]
        class_means = [np.mean(xi[y == c]) for c in classes]
        class_vars = [np.var(xi[y == c]) for c in classes]
        signal = np.var(class_means)
        noise = np.mean(class_vars)
        snr[feat] = float(signal / noise) if noise > 0 else 0
    return snr


def template_attack(X_train, y_train, X_test, n_components=8):
    n_comp = min(n_components, X_train.shape[1], X_train.shape[0] - 1)
    pca = PCA(n_components=n_comp)
    X_train_pca = pca.fit_transform(X_train)
    X_test_pca = pca.transform(X_test)

    classes = np.unique(y_train)
    templates = {}
    for c in classes:
        X_c = X_train_pca[y_train == c]
        mean_c = np.mean(X_c, axis=0)
        cov_c = np.cov(X_c.T) + np.eye(n_comp) * 1e-6
        templates[c] = (mean_c, cov_c)

    y_pred = []
    for x in X_test_pca:
        lls = {}
        for c, (m, cov) in templates.items():
            try:
                lls[c] = multivariate_normal.logpdf(x, mean=m, cov=cov)
            except:
                lls[c] = -np.inf
        y_pred.append(max(lls, key=lls.get))
    return np.array(y_pred)


def run_experiment_at_repeat_count(raw, keys_train, keys_val, keys_test,
                                    max_repeats, reference_dist, spike_threshold):
    """Run full experiment using only first max_repeats repeats per key."""
    subset = raw[raw["repeat"] < max_repeats]

    def build(key_ids):
        rows = []
        for kid in key_ids:
            kd = subset[subset["key_id"] == kid]
            if len(kd) == 0:
                continue
            timings = kd["timing_cycles"].values
            first = kd.iloc[0]
            feats = compute_features(timings, spike_threshold, reference_dist)
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

    train_df = build(keys_train)
    val_df = build(keys_val)
    test_df = build(keys_test)

    feature_cols = [c for c in train_df.columns
                    if c.startswith("timing_") or c.startswith("spike_") or c == "cv" or c == "wasserstein"]

    scaler = StandardScaler()
    X_train = np.nan_to_num(scaler.fit_transform(train_df[feature_cols].values))
    X_val = np.nan_to_num(scaler.transform(val_df[feature_cols].values))
    X_test = np.nan_to_num(scaler.transform(test_df[feature_cols].values))

    results = {}
    for target_name in TARGETS:
        y_train = train_df[target_name].values
        y_test = test_df[target_name].values
        majority = max(np.bincount(y_test)) / len(y_test)

        # SNR
        snr = compute_snr(X_train, y_train, feature_cols)
        max_snr = max(snr.values())

        # XGBoost
        model = xgb.XGBClassifier(
            n_estimators=500, max_depth=4, learning_rate=0.01,
            subsample=0.8, use_label_encoder=False, eval_metric="logloss",
            random_state=42, n_jobs=-1, verbosity=0
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        pval, _, _ = binomial_test(y_test, y_pred, majority)

        # Template
        y_pred_ta = template_attack(X_train, y_train, X_test, n_components=8)
        ta_acc = accuracy_score(y_test, y_pred_ta)
        ta_pval, _, _ = binomial_test(y_test, y_pred_ta, majority)

        results[target_name] = {
            "xgb_acc": float(acc), "xgb_p": float(pval),
            "template_acc": float(ta_acc), "template_p": float(ta_pval),
            "majority": float(majority), "max_snr": float(max_snr),
            "n_train": len(train_df), "n_test": len(test_df),
        }

    return results


def main():
    print("=" * 60)
    print("  EXPERIMENT: VERTICAL SCALING (200 keys × 5000 repeats)")
    print("=" * 60)

    csv_path = os.path.join(DATA_DIR, "raw_timing_traces_v4_vertical.csv")
    raw = pd.read_csv(csv_path)
    print(f"\n  Raw data: {len(raw):,} traces, {raw['key_id'].nunique()} keys")
    print(f"  Repeats per key: {raw.groupby('key_id').size().describe()}")

    unique_keys = raw["key_id"].unique()
    keys_tv, keys_test = train_test_split(unique_keys, test_size=0.15, random_state=RANDOM_SEED)
    keys_train, keys_val = train_test_split(keys_tv, test_size=0.15/0.85, random_state=RANDOM_SEED)
    print(f"  Train: {len(keys_train)} keys, Val: {len(keys_val)} keys, Test: {len(keys_test)} keys")

    train_raw = raw[raw["key_id"].isin(keys_train)]
    spike_threshold = float(np.percentile(train_raw["timing_cycles"], 95))
    rng = np.random.RandomState(RANDOM_SEED)
    reference_dist = rng.choice(train_raw["timing_cycles"].values,
                                 size=min(10000, len(train_raw)), replace=False)
    print(f"  Spike threshold: {spike_threshold:.0f}")

    # Progressive analysis: test at increasing repeat counts
    repeat_counts = [50, 100, 250, 500, 1000, 2500, 5000]
    max_available = raw.groupby("key_id").size().min()
    repeat_counts = [r for r in repeat_counts if r <= max_available]

    print(f"\n  Progressive analysis across repeat counts: {repeat_counts}")

    progressive_results = {}
    for n_rep in repeat_counts:
        print(f"\n{'='*50}")
        print(f"  REPEATS PER KEY: {n_rep}")
        print(f"{'='*50}")
        res = run_experiment_at_repeat_count(
            raw, keys_train, keys_val, keys_test,
            n_rep, reference_dist, spike_threshold
        )
        progressive_results[n_rep] = res
        for t, r in res.items():
            print(f"  {t:<25} XGB={r['xgb_acc']:.4f}(p={r['xgb_p']:.4f}) "
                  f"Template={r['template_acc']:.4f}(p={r['template_p']:.4f}) "
                  f"SNR={r['max_snr']:.6f}")

    # Final summary
    print(f"\n{'='*60}")
    print(f"  PROGRESSIVE ANALYSIS: ACCURACY vs REPEATS PER KEY")
    print(f"{'='*60}")

    for target_name in TARGETS:
        print(f"\n  {target_name}:")
        print(f"  {'Repeats':>8} {'XGB Acc':>8} {'XGB p':>10} {'Tmpl Acc':>8} {'Tmpl p':>10} {'SNR':>10}")
        print(f"  {'-'*56}")
        for n_rep in repeat_counts:
            r = progressive_results[n_rep][target_name]
            print(f"  {n_rep:>8} {r['xgb_acc']:>8.4f} {r['xgb_p']:>10.4f} "
                  f"{r['template_acc']:>8.4f} {r['template_p']:>10.4f} {r['max_snr']:>10.6f}")

    with open(os.path.join(DATA_DIR, "experiment_vertical_scaling.json"), "w") as f:
        json.dump(progressive_results, f, indent=2, default=str)
    print(f"\n  Saved to experiment_vertical_scaling.json")


if __name__ == "__main__":
    main()
