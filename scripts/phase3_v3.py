#!/usr/bin/env python3
"""
phase3_v3.py

Phase 3 (v3): ML models with KDE features + KyberSlash-aware targets.

Key changes:
- 45 features (19 KDE quantiles + 19 KDE densities + 7 aggregate stats)
- 5 target variables including FO rejection and message HW
- XGBoost with broader grid search
- Mutual information analysis
- NICV (Normalized Inter-Class Variance) from SCA literature
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
from sklearn.feature_selection import mutual_info_classif
import xgboost as xgb

warnings.filterwarnings("ignore")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models_v3")

TARGETS = {
    "target_rejection": "FO implicit rejection (valid vs invalid CT)",
    "target_msg_hw_parity": "Message HW parity",
    "target_msg_hw_bin": "Message HW >= train median",
    "target_coeff0_hw_bin": "Coeff0 HW >= train median",
    "target_sk_lsb": "LSB of sk[0] (legacy)",
}


def load_feature_names():
    meta = json.load(open(os.path.join(DATA_DIR, "split_metadata_v3.json")))
    return meta["feature_names"]


def nicv_analysis(X, y, feature_names):
    """
    Normalized Inter-Class Variance (NICV).
    NICV = Var(E[X|Y]) / Var(X)
    Values close to 0 = no leakage. Values close to 1 = strong leakage.
    Standard SCA metric from Bhasin et al. (2014).
    """
    nicv_values = {}
    classes = np.unique(y)
    for i, feat in enumerate(feature_names):
        xi = X[:, i]
        class_means = np.array([np.mean(xi[y == c]) for c in classes])
        class_sizes = np.array([np.sum(y == c) for c in classes])
        global_mean = np.mean(xi)
        # Var(E[X|Y]) = weighted variance of class means
        var_cond_mean = np.sum(class_sizes * (class_means - global_mean) ** 2) / len(y)
        var_total = np.var(xi)
        nicv_values[feat] = float(var_cond_mean / var_total) if var_total > 0 else 0.0
    return nicv_values


def evaluate(name, y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred)
    return {"name": name, "accuracy": acc, "precision": prec,
            "recall": rec, "f1": f1, "confusion_matrix": cm.tolist()}


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    feature_names = load_feature_names()

    print("[Phase 3 v3] Loading KDE-featurized data...")
    train = pd.read_csv(os.path.join(DATA_DIR, "train_v3.csv"))
    val = pd.read_csv(os.path.join(DATA_DIR, "val_v3.csv"))
    test = pd.read_csv(os.path.join(DATA_DIR, "test_v3.csv"))

    # Ensure all feature columns exist
    available_features = [f for f in feature_names if f in train.columns]
    print(f"  Features: {len(available_features)}")
    print(f"  Train: {len(train)} keys, Val: {len(val)} keys, Test: {len(test)} keys")

    X_train = train[available_features].values
    X_val = val[available_features].values
    X_test = test[available_features].values

    # Replace NaN/inf
    X_train = np.nan_to_num(X_train, nan=0, posinf=0, neginf=0)
    X_val = np.nan_to_num(X_val, nan=0, posinf=0, neginf=0)
    X_test = np.nan_to_num(X_test, nan=0, posinf=0, neginf=0)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    X_test_s = scaler.transform(X_test)
    pickle.dump(scaler, open(os.path.join(MODELS_DIR, "scaler_v3.pkl"), "wb"))

    all_results = {}

    for target_name, target_desc in TARGETS.items():
        if target_name not in train.columns:
            print(f"\n  Skipping {target_name} (not in data)")
            continue

        print(f"\n{'='*60}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'='*60}")

        y_train = train[target_name].values.astype(int)
        y_val = val[target_name].values.astype(int)
        y_test = test[target_name].values.astype(int)

        print(f"  Class balance (train): {np.bincount(y_train)}")
        print(f"  Class balance (val):   {np.bincount(y_val)}")

        target_results = {}

        # --- NICV Analysis ---
        print(f"\n  [NICV Analysis] (train set)")
        nicv = nicv_analysis(X_train_s, y_train, available_features)
        sorted_nicv = sorted(nicv.items(), key=lambda x: x[1], reverse=True)
        print(f"  Top 10 NICV values:")
        for feat, val_nicv in sorted_nicv[:10]:
            print(f"    {feat:<25s} NICV={val_nicv:.6f}")
        max_nicv = sorted_nicv[0][1]
        print(f"  Max NICV: {max_nicv:.6f} {'(significant)' if max_nicv > 0.01 else '(negligible)'}")
        target_results["nicv_top10"] = {f: v for f, v in sorted_nicv[:10]}

        # --- Mutual Information ---
        print(f"\n  [Mutual Information] (train set)")
        mi = mutual_info_classif(X_train_s, y_train, random_state=RANDOM_SEED,
                                  n_neighbors=5)
        mi_dict = dict(zip(available_features, mi))
        sorted_mi = sorted(mi_dict.items(), key=lambda x: x[1], reverse=True)
        print(f"  Top 10 MI values:")
        for feat, mi_val in sorted_mi[:10]:
            print(f"    {feat:<25s} MI={mi_val:.6f}")
        target_results["mi_top10"] = {f: float(v) for f, v in sorted_mi[:10]}

        # --- Dummy ---
        dummy = DummyClassifier(strategy="most_frequent")
        dummy.fit(X_train_s, y_train)
        dummy_res = evaluate("Dummy", y_val, dummy.predict(X_val_s))
        print(f"\n  Dummy baseline (val): acc={dummy_res['accuracy']:.4f}")
        target_results["dummy"] = dummy_res
        pickle.dump(dummy, open(os.path.join(MODELS_DIR, f"dummy_{target_name}.pkl"), "wb"))

        # --- XGBoost ---
        print(f"\n  XGBoost grid search...")
        xgb_grid = [
            {"n_estimators": 300, "max_depth": 3, "learning_rate": 0.1, "subsample": 0.8},
            {"n_estimators": 500, "max_depth": 5, "learning_rate": 0.05, "subsample": 0.8},
            {"n_estimators": 500, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.7,
             "colsample_bytree": 0.8},
            {"n_estimators": 800, "max_depth": 7, "learning_rate": 0.01, "subsample": 0.9},
            {"n_estimators": 1000, "max_depth": 4, "learning_rate": 0.01, "subsample": 0.8,
             "colsample_bytree": 0.7, "reg_alpha": 0.1, "reg_lambda": 1.0},
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
        print(f"  Best XGBoost: val acc={xgb_res['accuracy']:.4f}")
        target_results["xgboost"] = xgb_res
        pickle.dump(best_xgb, open(os.path.join(MODELS_DIR, f"best_xgb_{target_name}.pkl"), "wb"))

        # Feature importance
        importances = best_xgb.feature_importances_
        top_feats = sorted(zip(available_features, importances),
                           key=lambda x: x[1], reverse=True)[:10]
        print(f"  Top XGBoost features:")
        for feat, imp in top_feats:
            print(f"    {feat:<25s} {imp:.4f}")
        target_results["feature_importance"] = {f: float(i) for f, i in top_feats}

        # --- Random Forest ---
        print(f"\n  RandomForest...")
        rf = RandomForestClassifier(n_estimators=500, max_depth=None,
                                     min_samples_leaf=2, random_state=42, n_jobs=-1)
        rf.fit(X_train_s, y_train)
        rf_res = evaluate("RandomForest", y_val, rf.predict(X_val_s))
        print(f"  RF: val acc={rf_res['accuracy']:.4f}")
        target_results["random_forest"] = rf_res
        pickle.dump(rf, open(os.path.join(MODELS_DIR, f"best_rf_{target_name}.pkl"), "wb"))

        # --- Gradient Boosting ---
        print(f"\n  GradientBoosting...")
        gb = GradientBoostingClassifier(
            n_estimators=500, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42
        )
        gb.fit(X_train_s, y_train)
        gb_res = evaluate("GradientBoosting", y_val, gb.predict(X_val_s))
        print(f"  GB: val acc={gb_res['accuracy']:.4f}")
        target_results["gradient_boosting"] = gb_res
        pickle.dump(gb, open(os.path.join(MODELS_DIR, f"gb_{target_name}.pkl"), "wb"))

        all_results[target_name] = target_results

    with open(os.path.join(MODELS_DIR, "phase3_v3_results.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n[Phase 3 v3] Complete. Results saved to {MODELS_DIR}/")


RANDOM_SEED = 42

if __name__ == "__main__":
    main()
