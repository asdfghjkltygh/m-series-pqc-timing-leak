#!/usr/bin/env python3
"""
phase5_evaluation.py

Phase 5: Final Evaluation & Robustness Check.

Evaluates ALL models (Dummy, XGBoost, RandomForest, 1D-CNN) on the
UNTOUCHED test set. Reports statistical significance using binomial test.

ANTI-LEAKAGE: This is the FIRST and ONLY time test data is used for evaluation.
"""

import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, precision_recall_fscore_support)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")


def prepare_features(df, scaler):
    X = np.column_stack([
        df["timing_ns"].values,
        np.log1p(df["timing_ns"].values),
        df["timing_ns"].values ** 2,
    ])
    y = df["target_bit"].values
    X_scaled = scaler.transform(X)
    return X_scaled, y


def statistical_significance(y_true, y_pred, null_accuracy=0.5):
    """
    Binomial test: is the model's accuracy significantly better than chance?
    H0: accuracy = null_accuracy (random guessing)
    H1: accuracy > null_accuracy
    """
    n = len(y_true)
    k = np.sum(y_pred == y_true)
    # One-sided binomial test
    result = stats.binomtest(k, n, null_accuracy, alternative="greater")
    return result.pvalue, k, n


def main():
    print("=" * 70)
    print("  PHASE 5: FINAL EVALUATION ON UNTOUCHED TEST SET")
    print("=" * 70)

    # Load test data
    test = pd.read_csv(os.path.join(DATA_DIR, "test.csv"))
    scaler = pickle.load(open(os.path.join(MODELS_DIR, "scaler.pkl"), "rb"))
    X_test, y_test = prepare_features(test, scaler)

    print(f"\nTest set: {len(X_test)} samples")
    print(f"Class distribution: {np.bincount(y_test)}")
    print(f"Majority class baseline: {max(np.bincount(y_test)) / len(y_test):.4f}")

    results = {}

    # --- Dummy Classifier ---
    print("\n" + "-" * 50)
    print("DUMMY CLASSIFIER (Most Frequent)")
    print("-" * 50)
    dummy = pickle.load(open(os.path.join(MODELS_DIR, "dummy.pkl"), "rb"))
    y_pred_dummy = dummy.predict(X_test)
    acc = accuracy_score(y_test, y_pred_dummy)
    print(f"Accuracy: {acc:.4f}")
    print(f"Classification Report:\n{classification_report(y_test, y_pred_dummy, zero_division=0)}")
    results["dummy"] = {"accuracy": acc}

    # --- XGBoost ---
    print("-" * 50)
    print("XGBOOST (Best from Phase 3)")
    print("-" * 50)
    xgb_model = pickle.load(open(os.path.join(MODELS_DIR, "best_xgb.pkl"), "rb"))
    y_pred_xgb = xgb_model.predict(X_test)
    acc_xgb = accuracy_score(y_test, y_pred_xgb)
    prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_pred_xgb, average="binary", zero_division=0)
    cm = confusion_matrix(y_test, y_pred_xgb)
    p_val_xgb, k_xgb, n_xgb = statistical_significance(y_test, y_pred_xgb)
    print(f"Accuracy: {acc_xgb:.4f}")
    print(f"Precision: {prec:.4f}, Recall: {rec:.4f}, F1: {f1:.4f}")
    print(f"Confusion Matrix:\n{cm}")
    print(f"Binomial test: {k_xgb}/{n_xgb} correct, p-value = {p_val_xgb:.6f}")
    results["xgboost"] = {
        "accuracy": acc_xgb, "precision": prec, "recall": rec, "f1": f1,
        "confusion_matrix": cm.tolist(), "p_value": p_val_xgb,
    }

    # --- Random Forest ---
    print("-" * 50)
    print("RANDOM FOREST (Best from Phase 3)")
    print("-" * 50)
    rf_model = pickle.load(open(os.path.join(MODELS_DIR, "best_rf.pkl"), "rb"))
    y_pred_rf = rf_model.predict(X_test)
    acc_rf = accuracy_score(y_test, y_pred_rf)
    prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_pred_rf, average="binary", zero_division=0)
    cm = confusion_matrix(y_test, y_pred_rf)
    p_val_rf, k_rf, n_rf = statistical_significance(y_test, y_pred_rf)
    print(f"Accuracy: {acc_rf:.4f}")
    print(f"Precision: {prec:.4f}, Recall: {rec:.4f}, F1: {f1:.4f}")
    print(f"Confusion Matrix:\n{cm}")
    print(f"Binomial test: {k_rf}/{n_rf} correct, p-value = {p_val_rf:.6f}")
    results["random_forest"] = {
        "accuracy": acc_rf, "precision": prec, "recall": rec, "f1": f1,
        "confusion_matrix": cm.tolist(), "p_value": p_val_rf,
    }

    # --- 1D-CNN ---
    print("-" * 50)
    print("1D-CNN (Best from Phase 4)")
    print("-" * 50)
    try:
        import torch
        from phase4_cnn_model import TimingCNN1D

        cnn_config = json.load(open(os.path.join(MODELS_DIR, "cnn_config.json")))
        model = TimingCNN1D(input_features=cnn_config["input_features"])
        model.load_state_dict(torch.load(os.path.join(MODELS_DIR, "best_cnn.pt"),
                                          map_location="cpu", weights_only=True))
        model.eval()

        X_test_t = torch.FloatTensor(X_test).unsqueeze(1)
        with torch.no_grad():
            outputs = model(X_test_t)
            y_pred_cnn = outputs.argmax(1).numpy()

        acc_cnn = accuracy_score(y_test, y_pred_cnn)
        prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_pred_cnn, average="binary", zero_division=0)
        cm = confusion_matrix(y_test, y_pred_cnn)
        p_val_cnn, k_cnn, n_cnn = statistical_significance(y_test, y_pred_cnn)
        print(f"Accuracy: {acc_cnn:.4f}")
        print(f"Precision: {prec:.4f}, Recall: {rec:.4f}, F1: {f1:.4f}")
        print(f"Confusion Matrix:\n{cm}")
        print(f"Binomial test: {k_cnn}/{n_cnn} correct, p-value = {p_val_cnn:.6f}")
        results["cnn_1d"] = {
            "accuracy": acc_cnn, "precision": prec, "recall": rec, "f1": f1,
            "confusion_matrix": cm.tolist(), "p_value": p_val_cnn,
        }
    except Exception as e:
        print(f"  CNN evaluation failed: {e}")
        results["cnn_1d"] = {"error": str(e)}

    # --- Summary ---
    print("\n" + "=" * 70)
    print("  SUMMARY OF RESULTS")
    print("=" * 70)
    print(f"\n{'Model':<20} {'Accuracy':>10} {'P-value':>12} {'Significant?':>14}")
    print("-" * 56)

    for name, res in results.items():
        acc = res.get("accuracy", "N/A")
        pval = res.get("p_value", "N/A")
        if isinstance(acc, float):
            sig = "YES ***" if isinstance(pval, float) and pval < 0.001 else \
                  "YES **" if isinstance(pval, float) and pval < 0.01 else \
                  "YES *" if isinstance(pval, float) and pval < 0.05 else "NO"
            acc_str = f"{acc:.4f}"
            pval_str = f"{pval:.6f}" if isinstance(pval, float) else "N/A"
        else:
            acc_str = str(acc)
            pval_str = "N/A"
            sig = "N/A"
        print(f"{name:<20} {acc_str:>10} {pval_str:>12} {sig:>14}")

    # Core finding
    print("\n" + "=" * 70)
    best_model = max(
        [(k, v) for k, v in results.items() if isinstance(v.get("accuracy"), float) and k != "dummy"],
        key=lambda x: x[1]["accuracy"],
        default=None
    )
    if best_model:
        name, res = best_model
        pval = res.get("p_value", 1.0)
        if pval < 0.05:
            print(f"  *** CORE FINDING: {name} achieves {res['accuracy']:.4f} accuracy")
            print(f"      on the untouched test set (p={pval:.6f}), which is")
            print(f"      statistically significantly better than random guessing.")
            print(f"      This suggests timing leakage in ML-KEM-768 decapsulation.")
        else:
            print(f"  No model achieved statistically significant accuracy above chance.")
            print(f"  Best: {name} at {res['accuracy']:.4f} (p={pval:.6f})")
            print(f"  This may indicate:")
            print(f"    - The implementation is effectively constant-time")
            print(f"    - More data / finer-grained timing is needed")
            print(f"    - The target (LSB of sk[0]) may not correlate with decap timing")
    print("=" * 70)

    # Save final report
    with open(os.path.join(DATA_DIR, "final_report.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to {os.path.join(DATA_DIR, 'final_report.json')}")


if __name__ == "__main__":
    main()
