#!/usr/bin/env python3
"""
phase3_tree_models.py

Phase 3: Baseline ML Modeling with Tree-based classifiers.

Trains XGBoost and RandomForest on quantile-filtered timing data
to predict the LSB of the secret key byte from timing traces.

ANTI-LEAKAGE: Hyperparameter search uses ONLY train + val sets.
Final evaluation is done in Phase 5 on the untouched test set.
"""

import json
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, precision_recall_fscore_support)
from sklearn.model_selection import ParameterGrid
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

warnings.filterwarnings("ignore")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")


def load_data():
    train = pd.read_csv(os.path.join(DATA_DIR, "train.csv"))
    val = pd.read_csv(os.path.join(DATA_DIR, "val.csv"))
    test = pd.read_csv(os.path.join(DATA_DIR, "test.csv"))
    return train, val, test


def prepare_features(df):
    """Extract features from timing data.
    For single-measurement data, timing_ns is the primary feature.
    We also add engineered features for robustness.
    """
    X = pd.DataFrame()
    X["timing_ns"] = df["timing_ns"].values
    X["timing_log"] = np.log1p(df["timing_ns"].values)
    X["timing_sq"] = df["timing_ns"].values ** 2
    y = df["target_bit"].values
    return X, y


def evaluate_model(name, model, X, y, verbose=True):
    """Evaluate a model and return metrics dict."""
    y_pred = model.predict(X)
    acc = accuracy_score(y, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(y, y_pred, average="binary", zero_division=0)
    cm = confusion_matrix(y, y_pred)
    if verbose:
        print(f"\n  [{name}] Accuracy: {acc:.4f}, Precision: {prec:.4f}, Recall: {rec:.4f}, F1: {f1:.4f}")
        print(f"  Confusion Matrix:\n{cm}")
    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1,
            "confusion_matrix": cm.tolist()}


def main():
    print("[Phase 3] Loading filtered data...")
    train, val, test = load_data()

    X_train, y_train = prepare_features(train)
    X_val, y_val = prepare_features(val)
    X_test, y_test = prepare_features(test)

    # Fit scaler on TRAINING DATA ONLY
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)

    print(f"  Train: {len(X_train)} samples, Val: {len(X_val)} samples, Test: {len(X_test)} samples")
    print(f"  Class balance (train): {np.bincount(y_train)}")
    print(f"  Class balance (val):   {np.bincount(y_val)}")

    # --- Dummy Baseline ---
    print("\n[Phase 3] Dummy classifier (most frequent) baseline:")
    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit(X_train_scaled, y_train)
    dummy_val_metrics = evaluate_model("Dummy (Val)", dummy, X_val_scaled, y_val)
    dummy_test_metrics = evaluate_model("Dummy (Test)", dummy, X_test_scaled, y_test)

    # --- XGBoost Grid Search ---
    print("\n[Phase 3] XGBoost hyperparameter search (validated on Val set)...")
    xgb_param_grid = [
        {"n_estimators": 100, "max_depth": 3, "learning_rate": 0.1},
        {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.05},
        {"n_estimators": 300, "max_depth": 7, "learning_rate": 0.01},
    ]

    best_xgb_acc = -1
    best_xgb_model = None
    best_xgb_params = None

    for params in xgb_param_grid:
        model = xgb.XGBClassifier(
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            learning_rate=params["learning_rate"],
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train_scaled, y_train)
        val_acc = accuracy_score(y_val, model.predict(X_val_scaled))
        print(f"  XGB {params} -> Val acc: {val_acc:.4f}")
        if val_acc > best_xgb_acc:
            best_xgb_acc = val_acc
            best_xgb_model = model
            best_xgb_params = params

    print(f"\n  Best XGBoost: {best_xgb_params} (Val acc: {best_xgb_acc:.4f})")
    xgb_val_metrics = evaluate_model("XGBoost (Val)", best_xgb_model, X_val_scaled, y_val)

    # --- Random Forest Grid Search ---
    print("\n[Phase 3] RandomForest hyperparameter search...")
    rf_param_grid = [
        {"n_estimators": 100, "max_depth": 5},
        {"n_estimators": 200, "max_depth": 10},
        {"n_estimators": 300, "max_depth": None},
    ]

    best_rf_acc = -1
    best_rf_model = None
    best_rf_params = None

    for params in rf_param_grid:
        model = RandomForestClassifier(
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train_scaled, y_train)
        val_acc = accuracy_score(y_val, model.predict(X_val_scaled))
        print(f"  RF {params} -> Val acc: {val_acc:.4f}")
        if val_acc > best_rf_acc:
            best_rf_acc = val_acc
            best_rf_model = model
            best_rf_params = params

    print(f"\n  Best RandomForest: {best_rf_params} (Val acc: {best_rf_acc:.4f})")
    rf_val_metrics = evaluate_model("RandomForest (Val)", best_rf_model, X_val_scaled, y_val)

    # --- Save models and results (for Phase 5) ---
    import pickle
    models_dir = os.path.join(PROJECT_DIR, "data", "models")
    os.makedirs(models_dir, exist_ok=True)

    pickle.dump(best_xgb_model, open(os.path.join(models_dir, "best_xgb.pkl"), "wb"))
    pickle.dump(best_rf_model, open(os.path.join(models_dir, "best_rf.pkl"), "wb"))
    pickle.dump(scaler, open(os.path.join(models_dir, "scaler.pkl"), "wb"))
    pickle.dump(dummy, open(os.path.join(models_dir, "dummy.pkl"), "wb"))

    results = {
        "dummy_val": {k: v for k, v in dummy_val_metrics.items()},
        "xgb_best_params": best_xgb_params,
        "xgb_val": {k: v for k, v in xgb_val_metrics.items()},
        "rf_best_params": {k: str(v) for k, v in best_rf_params.items()},
        "rf_val": {k: v for k, v in rf_val_metrics.items()},
    }
    with open(os.path.join(models_dir, "phase3_results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n[Phase 3] Models and results saved to {models_dir}")
    print("[Phase 3] REMINDER: Test set metrics will be computed in Phase 5 only.")


if __name__ == "__main__":
    main()
