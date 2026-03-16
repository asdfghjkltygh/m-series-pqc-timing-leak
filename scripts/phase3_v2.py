#!/usr/bin/env python3
"""
phase3_v2.py

Phase 3 (upgraded): Tree-based models with:
- Per-key aggregate features (min, Q05, Q10, Q25, median, mean, std, IQR, range, skew)
- Multiple target formulations tested
- Expanded hyperparameter grid
- CPA-style correlation analysis as additional baseline
- Dummy classifier baseline per target

ANTI-LEAKAGE: All fitting on train, validation on val, test untouched.
"""

import json
import os
import pickle
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

warnings.filterwarnings("ignore")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models_v2")

TIMING_FEATURES = [
    "timing_min", "timing_q05", "timing_q10", "timing_q25",
    "timing_median", "timing_mean", "timing_std", "timing_iqr",
    "timing_range", "timing_skew",
]

TARGETS = {
    "target_lsb_c0": "LSB of coeff_0 (binary)",
    "target_hw_bin": "HW >= median (binary)",
    "target_hw_parity": "HW parity (binary)",
}


def evaluate(name, y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred)
    return {"name": name, "accuracy": acc, "precision": prec,
            "recall": rec, "f1": f1, "confusion_matrix": cm.tolist()}


def cpa_analysis(train_df, val_df):
    """
    Correlation Power Analysis (CPA) style:
    Compute Pearson correlation between each timing feature and each
    target variable. This is a non-ML baseline that detects linear
    timing-secret dependencies.
    """
    print("\n[CPA Analysis] Pearson correlations (TRAIN set only):")
    results = {}
    for target_name in TARGETS:
        if target_name not in train_df.columns:
            continue
        correlations = {}
        for feat in TIMING_FEATURES:
            r, p = sp_stats.pearsonr(train_df[feat], train_df[target_name])
            correlations[feat] = {"r": float(r), "p_value": float(p)}
        # Sort by absolute correlation
        sorted_corrs = sorted(correlations.items(), key=lambda x: abs(x[1]["r"]), reverse=True)
        print(f"\n  Target: {target_name}")
        for feat, vals in sorted_corrs[:5]:
            sig = "***" if vals["p_value"] < 0.001 else "**" if vals["p_value"] < 0.01 else "*" if vals["p_value"] < 0.05 else ""
            print(f"    {feat:<20s} r={vals['r']:+.6f}  p={vals['p_value']:.4e} {sig}")
        results[target_name] = correlations

    # Also check on validation set to see if correlations replicate
    print("\n[CPA Analysis] Cross-check on VAL set (must replicate to be real):")
    for target_name in TARGETS:
        if target_name not in val_df.columns:
            continue
        print(f"\n  Target: {target_name}")
        for feat in TIMING_FEATURES[:5]:
            if feat in results.get(target_name, {}):
                r_train = results[target_name][feat]["r"]
                r_val, p_val = sp_stats.pearsonr(val_df[feat], val_df[target_name])
                print(f"    {feat:<20s} r_train={r_train:+.6f}  r_val={r_val:+.6f}  p_val={p_val:.4e}")
                results[target_name][feat]["r_val"] = float(r_val)
                results[target_name][feat]["p_value_val"] = float(p_val)

    return results


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("[Phase 3 v2] Loading aggregated data...")
    train = pd.read_csv(os.path.join(DATA_DIR, "train_v2.csv"))
    val = pd.read_csv(os.path.join(DATA_DIR, "val_v2.csv"))
    test = pd.read_csv(os.path.join(DATA_DIR, "test_v2.csv"))

    print(f"  Train: {len(train)} keys, Val: {len(val)} keys, Test: {len(test)} keys")

    # Features
    X_train = train[TIMING_FEATURES].values
    X_val = val[TIMING_FEATURES].values
    X_test = test[TIMING_FEATURES].values

    # Fit scaler on TRAIN only
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    X_test_s = scaler.transform(X_test)
    pickle.dump(scaler, open(os.path.join(MODELS_DIR, "scaler_v2.pkl"), "wb"))

    # --- CPA Analysis ---
    cpa_results = cpa_analysis(train, val)
    with open(os.path.join(MODELS_DIR, "cpa_results.json"), "w") as f:
        json.dump(cpa_results, f, indent=2)

    # --- ML Models per target ---
    all_results = {}

    for target_name, target_desc in TARGETS.items():
        print(f"\n{'='*60}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'='*60}")

        y_train = train[target_name].values
        y_val = val[target_name].values
        y_test = test[target_name].values

        print(f"  Class balance (train): {np.bincount(y_train)}")
        print(f"  Class balance (val):   {np.bincount(y_val)}")

        target_results = {}

        # Dummy baseline
        dummy = DummyClassifier(strategy="most_frequent")
        dummy.fit(X_train_s, y_train)
        dummy_res = evaluate("Dummy", y_val, dummy.predict(X_val_s))
        print(f"\n  Dummy baseline (val): acc={dummy_res['accuracy']:.4f}")
        target_results["dummy"] = dummy_res

        # XGBoost grid
        print("\n  XGBoost grid search...")
        xgb_grid = [
            {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.1, "subsample": 0.8},
            {"n_estimators": 300, "max_depth": 5, "learning_rate": 0.05, "subsample": 0.8},
            {"n_estimators": 500, "max_depth": 7, "learning_rate": 0.01, "subsample": 0.9},
            {"n_estimators": 500, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.7, "colsample_bytree": 0.8},
        ]
        best_xgb_acc = -1
        best_xgb = None
        best_xgb_params = None

        for params in xgb_grid:
            model = xgb.XGBClassifier(
                **params, use_label_encoder=False, eval_metric="logloss",
                random_state=42, n_jobs=-1,
            )
            model.fit(X_train_s, y_train)
            acc = accuracy_score(y_val, model.predict(X_val_s))
            print(f"    {params} -> val acc: {acc:.4f}")
            if acc > best_xgb_acc:
                best_xgb_acc = acc
                best_xgb = model
                best_xgb_params = params

        xgb_res = evaluate("XGBoost", y_val, best_xgb.predict(X_val_s))
        print(f"  Best XGBoost: val acc={xgb_res['accuracy']:.4f}, params={best_xgb_params}")
        target_results["xgboost"] = xgb_res
        target_results["xgboost"]["params"] = {k: str(v) for k, v in best_xgb_params.items()}

        # Random Forest grid
        print("\n  RandomForest grid search...")
        rf_grid = [
            {"n_estimators": 200, "max_depth": 5, "min_samples_leaf": 5},
            {"n_estimators": 300, "max_depth": 10, "min_samples_leaf": 3},
            {"n_estimators": 500, "max_depth": None, "min_samples_leaf": 1},
            {"n_estimators": 500, "max_depth": 15, "min_samples_leaf": 2},
        ]
        best_rf_acc = -1
        best_rf = None
        best_rf_params = None

        for params in rf_grid:
            model = RandomForestClassifier(**params, random_state=42, n_jobs=-1)
            model.fit(X_train_s, y_train)
            acc = accuracy_score(y_val, model.predict(X_val_s))
            print(f"    {params} -> val acc: {acc:.4f}")
            if acc > best_rf_acc:
                best_rf_acc = acc
                best_rf = model
                best_rf_params = params

        rf_res = evaluate("RandomForest", y_val, best_rf.predict(X_val_s))
        print(f"  Best RF: val acc={rf_res['accuracy']:.4f}, params={best_rf_params}")
        target_results["random_forest"] = rf_res
        target_results["random_forest"]["params"] = {k: str(v) for k, v in best_rf_params.items()}

        # Gradient Boosting (additional model)
        print("\n  GradientBoosting...")
        gb = GradientBoostingClassifier(
            n_estimators=300, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42
        )
        gb.fit(X_train_s, y_train)
        gb_res = evaluate("GradientBoosting", y_val, gb.predict(X_val_s))
        print(f"  GB: val acc={gb_res['accuracy']:.4f}")
        target_results["gradient_boosting"] = gb_res

        # Feature importance from best XGBoost
        importances = best_xgb.feature_importances_
        feat_imp = sorted(zip(TIMING_FEATURES, importances), key=lambda x: x[1], reverse=True)
        print(f"\n  Feature importance (XGBoost):")
        for feat, imp in feat_imp:
            print(f"    {feat:<20s} {imp:.4f}")
        target_results["feature_importance"] = {f: float(i) for f, i in feat_imp}

        # Save best models for this target
        pickle.dump(best_xgb, open(os.path.join(MODELS_DIR, f"best_xgb_{target_name}.pkl"), "wb"))
        pickle.dump(best_rf, open(os.path.join(MODELS_DIR, f"best_rf_{target_name}.pkl"), "wb"))
        pickle.dump(gb, open(os.path.join(MODELS_DIR, f"gb_{target_name}.pkl"), "wb"))
        pickle.dump(dummy, open(os.path.join(MODELS_DIR, f"dummy_{target_name}.pkl"), "wb"))

        all_results[target_name] = target_results

    with open(os.path.join(MODELS_DIR, "phase3_v2_results.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n[Phase 3 v2] Complete. Models and results saved to {MODELS_DIR}/")
    print("[Phase 3 v2] REMINDER: Test set evaluation deferred to Phase 5.")


if __name__ == "__main__":
    main()
