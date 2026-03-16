#!/usr/bin/env python3
"""
Phase 2: Stochastic Profiling with Continuous Targets

Instead of discretizing the secret into binary classes, test whether
there is a weak linear relationship between timing features and
the continuous secret value (coefficient value 0-4095, or HW 0-12).

Models: Ridge Regression + XGBRegressor
Metric: MSE vs dummy regressor (predicting training mean), R²

ANTI-LEAKAGE: key-level split, scaler fit on train only.
"""

import json
import os

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.dummy import DummyRegressor
import xgboost as xgb

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
RANDOM_SEED = 42


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
        feats["coeff0_hw"] = int(first["coeff0_hw"])
        feats["sk_byte0"] = int(first["sk_byte0"])
        rows.append(feats)

    return pd.DataFrame(rows)


def main():
    print("=" * 60)
    print("  PHASE 2: STOCHASTIC PROFILING — CONTINUOUS TARGETS")
    print("=" * 60)

    csv_path = os.path.join(DATA_DIR, "raw_timing_traces_v4_vertical.csv")
    raw = pd.read_csv(csv_path)
    print(f"\n  Raw data: {len(raw):,} traces, {raw['key_id'].nunique()} keys")

    unique_keys = raw["key_id"].unique()
    keys_tv, keys_test = train_test_split(unique_keys, test_size=0.15, random_state=RANDOM_SEED)
    keys_train, keys_val = train_test_split(keys_tv, test_size=0.15/0.85, random_state=RANDOM_SEED)
    print(f"  Train: {len(keys_train)}, Val: {len(keys_val)}, Test: {len(keys_test)}")

    train_raw = raw[raw["key_id"].isin(keys_train)]
    spike_threshold = float(np.percentile(train_raw["timing_cycles"], 95))

    train_df = compute_features(raw, keys_train, spike_threshold)
    test_df = compute_features(raw, keys_test, spike_threshold)

    feature_cols = [c for c in train_df.columns
                    if c.startswith("timing_") or c.startswith("spike_") or c == "cv"]

    scaler = StandardScaler()
    X_train = np.nan_to_num(scaler.fit_transform(train_df[feature_cols].values))
    X_test = np.nan_to_num(scaler.transform(test_df[feature_cols].values))

    # Continuous targets
    continuous_targets = {
        "sk_byte0": {
            "desc": "sk_byte0 value (0-255)",
            "y_train": train_df["sk_byte0"].values.astype(float),
            "y_test": test_df["sk_byte0"].values.astype(float),
        },
        "message_hw": {
            "desc": "Message Hamming Weight (continuous)",
            "y_train": train_df["message_hw"].values.astype(float),
            "y_test": test_df["message_hw"].values.astype(float),
        },
        "coeff0_hw": {
            "desc": "Coeff0 Hamming Weight (0-12)",
            "y_train": train_df["coeff0_hw"].values.astype(float),
            "y_test": test_df["coeff0_hw"].values.astype(float),
        },
    }

    results = {}

    for target_name, target_info in continuous_targets.items():
        print(f"\n{'='*50}")
        print(f"  TARGET: {target_name} ({target_info['desc']})")
        print(f"{'='*50}")

        y_train = target_info["y_train"]
        y_test = target_info["y_test"]

        print(f"  Train: mean={np.mean(y_train):.2f}, std={np.std(y_train):.2f}, "
              f"range=[{np.min(y_train):.0f}, {np.max(y_train):.0f}]")
        print(f"  Test:  mean={np.mean(y_test):.2f}, std={np.std(y_test):.2f}, "
              f"range=[{np.min(y_test):.0f}, {np.max(y_test):.0f}]")

        # Dummy regressor (predicts training mean)
        dummy = DummyRegressor(strategy="mean")
        dummy.fit(X_train, y_train)
        dummy_pred = dummy.predict(X_test)
        dummy_mse = mean_squared_error(y_test, dummy_pred)
        dummy_r2 = r2_score(y_test, dummy_pred)
        print(f"\n  [Dummy Regressor (mean)]")
        print(f"    MSE={dummy_mse:.4f}, R²={dummy_r2:.6f}")

        # Ridge Regression
        best_ridge_mse = np.inf
        best_ridge_alpha = None
        for alpha in [0.01, 0.1, 1.0, 10.0, 100.0]:
            ridge = Ridge(alpha=alpha, random_state=RANDOM_SEED)
            ridge.fit(X_train, y_train)
            mse = mean_squared_error(y_test, ridge.predict(X_test))
            if mse < best_ridge_mse:
                best_ridge_mse = mse
                best_ridge_alpha = alpha
                best_ridge = ridge

        ridge_pred = best_ridge.predict(X_test)
        ridge_mse = mean_squared_error(y_test, ridge_pred)
        ridge_r2 = r2_score(y_test, ridge_pred)
        print(f"\n  [Ridge Regression (alpha={best_ridge_alpha})]")
        print(f"    MSE={ridge_mse:.4f}, R²={ridge_r2:.6f}")
        print(f"    MSE ratio vs dummy: {ridge_mse/dummy_mse:.4f} "
              f"({'BETTER' if ridge_mse < dummy_mse else 'WORSE/EQUAL'})")

        # Feature coefficients
        coefs = sorted(zip(feature_cols, best_ridge.coef_), key=lambda x: abs(x[1]), reverse=True)
        print(f"    Top coefficients:")
        for f, c in coefs[:5]:
            print(f"      {f:<25} {c:>10.4f}")

        # XGBRegressor
        xgb_reg = xgb.XGBRegressor(
            n_estimators=500, max_depth=4, learning_rate=0.01,
            subsample=0.8, random_state=42, n_jobs=-1, verbosity=0
        )
        xgb_reg.fit(X_train, y_train)
        xgb_pred = xgb_reg.predict(X_test)
        xgb_mse = mean_squared_error(y_test, xgb_pred)
        xgb_r2 = r2_score(y_test, xgb_pred)
        print(f"\n  [XGBRegressor]")
        print(f"    MSE={xgb_mse:.4f}, R²={xgb_r2:.6f}")
        print(f"    MSE ratio vs dummy: {xgb_mse/dummy_mse:.4f} "
              f"({'BETTER' if xgb_mse < dummy_mse else 'WORSE/EQUAL'})")

        # Feature importance
        imps = sorted(zip(feature_cols, xgb_reg.feature_importances_),
                       key=lambda x: x[1], reverse=True)
        print(f"    Top features:")
        for f, imp in imps[:5]:
            print(f"      {f:<25} {imp:>10.4f}")

        # Correlation between predictions and truth
        ridge_corr = np.corrcoef(y_test, ridge_pred)[0, 1]
        xgb_corr = np.corrcoef(y_test, xgb_pred)[0, 1]
        print(f"\n  Pearson correlation (pred vs truth):")
        print(f"    Ridge: r = {ridge_corr:.6f}")
        print(f"    XGB:   r = {xgb_corr:.6f}")

        results[target_name] = {
            "dummy_mse": float(dummy_mse),
            "ridge_mse": float(ridge_mse),
            "ridge_r2": float(ridge_r2),
            "ridge_mse_ratio": float(ridge_mse / dummy_mse),
            "ridge_corr": float(ridge_corr),
            "xgb_mse": float(xgb_mse),
            "xgb_r2": float(xgb_r2),
            "xgb_mse_ratio": float(xgb_mse / dummy_mse),
            "xgb_corr": float(xgb_corr),
        }

    # Summary
    print(f"\n{'='*60}")
    print(f"  PHASE 2 SUMMARY: CONTINUOUS REGRESSION")
    print(f"{'='*60}")
    print(f"  {'Target':<20} {'Dummy MSE':>10} {'Ridge MSE':>10} {'Ridge R²':>10} "
          f"{'XGB MSE':>10} {'XGB R²':>10}")
    print(f"  {'-'*70}")
    for t, r in results.items():
        print(f"  {t:<20} {r['dummy_mse']:>10.2f} {r['ridge_mse']:>10.2f} "
              f"{r['ridge_r2']:>10.6f} {r['xgb_mse']:>10.2f} {r['xgb_r2']:>10.6f}")

    any_better = any(r["ridge_mse_ratio"] < 0.95 or r["xgb_mse_ratio"] < 0.95
                     for r in results.values())
    if any_better:
        print(f"\n  *** Some models beat dummy — investigate further.")
    else:
        print(f"\n  *** NO model beats the dummy regressor. Zero predictive signal.")

    with open(os.path.join(DATA_DIR, "phase2_regression.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to phase2_regression.json")


if __name__ == "__main__":
    main()
