#!/usr/bin/env python3
"""
experiment_template_attack.py

Gemini Recommendation B5: Template Attacks (Profiled SCA)

Gold standard in side-channel analysis. Build a multivariate
Gaussian template per class from training data, classify test
traces by maximum log-likelihood.

Also includes:
- Gemini B6: Wasserstein distance as a feature
- Gemini D9: SNR (Signal-to-Noise Ratio) calculation

ANTI-LEAKAGE: Templates built on train only. PCA fit on train only.
"""

import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from scipy.stats import multivariate_normal, wasserstein_distance
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score

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


def compute_snr(X, y, feature_names):
    """
    SCA Signal-to-Noise Ratio.
    SNR = Var_classes(E[X|class]) / E_classes(Var[X|class])
    """
    classes = np.unique(y)
    n_features = X.shape[1]
    snr = np.zeros(n_features)

    for i in range(n_features):
        class_means = []
        class_vars = []
        for c in classes:
            xi_c = X[y == c, i]
            class_means.append(np.mean(xi_c))
            class_vars.append(np.var(xi_c))

        signal = np.var(class_means)
        noise = np.mean(class_vars)
        snr[i] = signal / noise if noise > 0 else 0

    return dict(zip(feature_names, snr))


def compute_features_with_wasserstein(raw, key_ids, reference_dist, spike_threshold):
    """Compute tail features + Wasserstein distance to reference."""
    rows = []
    for kid in key_ids:
        key_data = raw[raw["key_id"] == kid]
        timings = key_data["timing_cycles"].values
        first = key_data.iloc[0]

        feats = {}
        feats["timing_min"] = float(np.min(timings))
        feats["timing_median"] = float(np.median(timings))
        feats["timing_mean"] = float(np.mean(timings))
        feats["timing_std"] = float(np.std(timings))
        feats["timing_max"] = float(np.max(timings))
        feats["timing_p95"] = float(np.percentile(timings, 95))
        feats["timing_p99"] = float(np.percentile(timings, 99))
        feats["timing_range"] = float(np.ptp(timings))
        feats["timing_iqr"] = float(np.percentile(timings, 75) - np.percentile(timings, 25))
        feats["timing_kurtosis"] = float(pd.Series(timings).kurtosis()) if len(timings) > 3 else 0
        feats["timing_skew"] = float(pd.Series(timings).skew()) if len(timings) > 2 else 0
        feats["timing_var"] = float(np.var(timings))

        spikes = timings[timings > spike_threshold]
        feats["spike_count"] = len(spikes)
        feats["spike_ratio"] = len(spikes) / len(timings)

        # Wasserstein distance to the reference distribution
        feats["wasserstein"] = float(wasserstein_distance(timings, reference_dist))

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


def template_attack(X_train, y_train, X_test, n_components=10):
    """
    Multivariate Gaussian Template Attack.
    1. PCA on training data (fit on train only)
    2. Per-class mean + covariance in PCA space
    3. Classify by maximum log-likelihood
    """
    # PCA (fit on train only)
    n_comp = min(n_components, X_train.shape[1], X_train.shape[0] - 1)
    pca = PCA(n_components=n_comp)
    X_train_pca = pca.fit_transform(X_train)
    X_test_pca = pca.transform(X_test)

    classes = np.unique(y_train)
    templates = {}

    for c in classes:
        X_c = X_train_pca[y_train == c]
        mean_c = np.mean(X_c, axis=0)
        # Regularized covariance (add small diagonal to prevent singularity)
        cov_c = np.cov(X_c.T) + np.eye(n_comp) * 1e-6
        templates[c] = (mean_c, cov_c)

    # Classify test traces
    y_pred = []
    for x in X_test_pca:
        log_likelihoods = {}
        for c, (mean_c, cov_c) in templates.items():
            try:
                ll = multivariate_normal.logpdf(x, mean=mean_c, cov=cov_c)
            except Exception:
                ll = -np.inf
            log_likelihoods[c] = ll
        y_pred.append(max(log_likelihoods, key=log_likelihoods.get))

    return np.array(y_pred)


def main():
    print("=" * 60)
    print("  EXPERIMENTS: TEMPLATE ATTACK + WASSERSTEIN + SNR")
    print("=" * 60)

    raw = pd.read_csv(os.path.join(DATA_DIR, "raw_timing_traces_v3.csv"))
    print(f"\n  Raw data: {len(raw):,} traces, {raw['key_id'].nunique()} keys")

    unique_keys = raw["key_id"].unique()
    keys_tv, keys_test = train_test_split(unique_keys, test_size=0.15, random_state=RANDOM_SEED)
    keys_train, keys_val = train_test_split(keys_tv, test_size=0.15/0.85, random_state=RANDOM_SEED)

    # Reference distribution: all training timings (for Wasserstein)
    train_raw = raw[raw["key_id"].isin(keys_train)]
    reference_dist = train_raw["timing_cycles"].values
    # Subsample for efficiency
    rng = np.random.RandomState(RANDOM_SEED)
    reference_dist = rng.choice(reference_dist, size=min(10000, len(reference_dist)), replace=False)
    spike_threshold = float(np.percentile(train_raw["timing_cycles"], 95))

    print(f"  Spike threshold: {spike_threshold:.0f}")
    print(f"  Reference distribution: {len(reference_dist)} samples")

    # Build features
    train_df = compute_features_with_wasserstein(raw, keys_train, reference_dist, spike_threshold)
    val_df = compute_features_with_wasserstein(raw, keys_val, reference_dist, spike_threshold)
    test_df = compute_features_with_wasserstein(raw, keys_test, reference_dist, spike_threshold)
    print(f"  Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    feature_cols = [c for c in train_df.columns
                    if c.startswith("timing_") or c.startswith("spike_") or c == "wasserstein"]
    print(f"  Features ({len(feature_cols)}): {feature_cols}")

    scaler = StandardScaler()
    X_train = np.nan_to_num(scaler.fit_transform(train_df[feature_cols].values))
    X_val = np.nan_to_num(scaler.transform(val_df[feature_cols].values))
    X_test = np.nan_to_num(scaler.transform(test_df[feature_cols].values))

    all_results = {}
    total_tests = 0

    for target_name, target_desc in TARGETS.items():
        print(f"\n{'='*50}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'='*50}")

        y_train = train_df[target_name].values
        y_val = val_df[target_name].values
        y_test = test_df[target_name].values
        majority = max(np.bincount(y_test)) / len(y_test)
        print(f"  Classes (test): {np.bincount(y_test)}, majority: {majority:.4f}")

        # --- SNR Calculation ---
        snr = compute_snr(X_train, y_train, feature_cols)
        sorted_snr = sorted(snr.items(), key=lambda x: x[1], reverse=True)
        max_snr = sorted_snr[0][1]
        print(f"\n  [SNR Analysis]")
        for f, s in sorted_snr[:7]:
            print(f"    {f:<25s} SNR={s:.8f}")

        # Theoretical traces needed (rough: N ~ 1/SNR for simple distinguisher)
        if max_snr > 0:
            traces_needed = int(1 / max_snr)
            print(f"  Max SNR: {max_snr:.8f}")
            print(f"  Theoretical traces needed per key for exploitation: ~{traces_needed:,}")
        else:
            print(f"  Max SNR: 0 (no detectable signal)")

        # --- Template Attack ---
        print(f"\n  [Template Attack] (PCA + Multivariate Gaussian)")
        for n_comp in [5, 10]:
            y_pred_ta = template_attack(X_train, y_train, X_test, n_components=n_comp)
            ta_acc = accuracy_score(y_test, y_pred_ta)
            p_val, _, _ = binomial_test(y_test, y_pred_ta, majority)
            total_tests += 1
            print(f"    PCA={n_comp}: test acc={ta_acc:.4f}, p={p_val:.6f}")
            all_results[f"{target_name}_template_pca{n_comp}"] = {
                "test_acc": float(ta_acc), "p_value": float(p_val), "majority": float(majority),
            }

        # --- XGBoost with Wasserstein feature ---
        print(f"\n  [XGBoost with Wasserstein + tail features]")
        import xgboost as xgb
        model = xgb.XGBClassifier(
            n_estimators=500, max_depth=4, learning_rate=0.01,
            subsample=0.8, colsample_bytree=0.7,
            use_label_encoder=False, eval_metric="logloss",
            random_state=42, n_jobs=-1
        )
        model.fit(X_train, y_train)
        y_pred_xgb = model.predict(X_test)
        xgb_acc = accuracy_score(y_test, y_pred_xgb)
        p_val, _, _ = binomial_test(y_test, y_pred_xgb, majority)
        total_tests += 1
        print(f"    test acc={xgb_acc:.4f}, p={p_val:.6f}")

        # Wasserstein feature importance
        imps = dict(zip(feature_cols, model.feature_importances_))
        wass_imp = imps.get("wasserstein", 0)
        print(f"    Wasserstein importance: {wass_imp:.4f}")

        all_results[f"{target_name}_xgb_wasserstein"] = {
            "test_acc": float(xgb_acc), "p_value": float(p_val), "majority": float(majority),
            "wasserstein_importance": float(wass_imp),
        }
        all_results[f"{target_name}_snr"] = {
            "max_snr": float(max_snr),
            "top_snr": {f: float(s) for f, s in sorted_snr[:10]},
        }

    # Grand summary
    bonf_alpha = 0.05 / max(total_tests, 1)
    print(f"\n{'='*60}")
    print(f"  COMBINED SUMMARY (Bonferroni α={bonf_alpha:.6f}, {total_tests} tests)")
    print(f"{'='*60}")

    for name, res in all_results.items():
        if "test_acc" in res:
            sig = "YES***" if res["p_value"] < bonf_alpha else "no"
            print(f"  {name:<45} acc={res['test_acc']:.4f}  p={res['p_value']:.6f}  {sig}")

    with open(os.path.join(DATA_DIR, "experiment_template_wasserstein_snr.json"), "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Saved to experiment_template_wasserstein_snr.json")


if __name__ == "__main__":
    main()
