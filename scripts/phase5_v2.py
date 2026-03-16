#!/usr/bin/env python3
"""
phase5_v2.py

Phase 5 (upgraded): Final evaluation on untouched test set.

Evaluates ALL models across ALL targets with:
- Binomial significance tests
- Multiple comparison correction (Bonferroni)
- Confidence intervals
- Comprehensive summary report

ANTI-LEAKAGE: This is the FIRST and ONLY time test data is used.
"""

import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
                             confusion_matrix, classification_report)
from sklearn.dummy import DummyClassifier

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models_v2")

TIMING_FEATURES = [
    "timing_min", "timing_q05", "timing_q10", "timing_q25",
    "timing_median", "timing_mean", "timing_std", "timing_iqr",
    "timing_range", "timing_skew",
]

TARGETS = {
    "target_lsb_c0": "LSB of coeff_0",
    "target_hw_bin": "HW >= median",
    "target_hw_parity": "HW parity",
}

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


def binomial_test(y_true, y_pred, null_p=0.5):
    """One-sided binomial test: is accuracy significantly > chance?"""
    n = len(y_true)
    k = int(np.sum(y_pred == y_true))
    result = sp_stats.binomtest(k, n, null_p, alternative="greater")
    return result.pvalue, k, n


def wilson_ci(k, n, z=1.96):
    """Wilson score 95% confidence interval for a proportion."""
    p_hat = k / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2*n)) / denom
    spread = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4*n)) / n) / denom
    return max(0, center - spread), min(1, center + spread)


def evaluate_model(name, y_true, y_pred, null_p=0.5):
    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred)
    p_value, k, n = binomial_test(y_true, y_pred, null_p)
    ci_lo, ci_hi = wilson_ci(k, n)

    return {
        "name": name,
        "accuracy": float(acc),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "confusion_matrix": cm.tolist(),
        "p_value": float(p_value),
        "correct": int(k),
        "total": int(n),
        "ci_95": [float(ci_lo), float(ci_hi)],
    }


def main():
    print("=" * 70)
    print("  PHASE 5 v2: FINAL EVALUATION ON UNTOUCHED TEST SET")
    print("=" * 70)

    # Load test data
    test_agg = pd.read_csv(os.path.join(DATA_DIR, "test_v2.csv"))
    test_raw = pd.read_csv(os.path.join(DATA_DIR, "test_v2_raw.csv"))
    scaler = pickle.load(open(os.path.join(MODELS_DIR, "scaler_v2.pkl"), "rb"))

    X_test = scaler.transform(test_agg[TIMING_FEATURES].values)
    print(f"\nTest set: {len(test_agg)} keys")

    all_results = {}
    total_tests = 0  # For Bonferroni correction

    for target_name, target_desc in TARGETS.items():
        print(f"\n{'='*60}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'='*60}")

        y_test = test_agg[target_name].values
        class_dist = np.bincount(y_test)
        majority_rate = max(class_dist) / len(y_test)
        print(f"  Class distribution: {class_dist}")
        print(f"  Majority class rate: {majority_rate:.4f}")

        target_results = {}

        # --- Dummy ---
        try:
            dummy = pickle.load(open(os.path.join(MODELS_DIR, f"dummy_{target_name}.pkl"), "rb"))
            res = evaluate_model("Dummy", y_test, dummy.predict(X_test), majority_rate)
            target_results["dummy"] = res
            print(f"\n  Dummy:            acc={res['accuracy']:.4f}")
        except Exception as e:
            print(f"  Dummy failed: {e}")

        # --- XGBoost ---
        try:
            xgb_model = pickle.load(open(os.path.join(MODELS_DIR, f"best_xgb_{target_name}.pkl"), "rb"))
            res = evaluate_model("XGBoost", y_test, xgb_model.predict(X_test), majority_rate)
            target_results["xgboost"] = res
            total_tests += 1
            print(f"  XGBoost:          acc={res['accuracy']:.4f}  p={res['p_value']:.6f}  "
                  f"CI=[{res['ci_95'][0]:.3f}, {res['ci_95'][1]:.3f}]")
        except Exception as e:
            print(f"  XGBoost failed: {e}")

        # --- Random Forest ---
        try:
            rf_model = pickle.load(open(os.path.join(MODELS_DIR, f"best_rf_{target_name}.pkl"), "rb"))
            res = evaluate_model("RandomForest", y_test, rf_model.predict(X_test), majority_rate)
            target_results["random_forest"] = res
            total_tests += 1
            print(f"  RandomForest:     acc={res['accuracy']:.4f}  p={res['p_value']:.6f}  "
                  f"CI=[{res['ci_95'][0]:.3f}, {res['ci_95'][1]:.3f}]")
        except Exception as e:
            print(f"  RandomForest failed: {e}")

        # --- Gradient Boosting ---
        try:
            gb_model = pickle.load(open(os.path.join(MODELS_DIR, f"gb_{target_name}.pkl"), "rb"))
            res = evaluate_model("GradientBoosting", y_test, gb_model.predict(X_test), majority_rate)
            target_results["gradient_boosting"] = res
            total_tests += 1
            print(f"  GradientBoosting: acc={res['accuracy']:.4f}  p={res['p_value']:.6f}  "
                  f"CI=[{res['ci_95'][0]:.3f}, {res['ci_95'][1]:.3f}]")
        except Exception as e:
            print(f"  GradientBoosting failed: {e}")

        # --- DNN (aggregate features) ---
        if HAS_TORCH:
            try:
                sys.path.insert(0, os.path.dirname(__file__))
                from phase4_v2 import TimingAggCNN
                model = TimingAggCNN(num_features=len(TIMING_FEATURES))
                model.load_state_dict(torch.load(
                    os.path.join(MODELS_DIR, f"dnn_{target_name}.pt"),
                    map_location="cpu", weights_only=True
                ))
                model.eval()
                with torch.no_grad():
                    X_t = torch.FloatTensor(X_test)
                    y_pred = model(X_t).argmax(1).numpy()
                res = evaluate_model("DNN", y_test, y_pred, majority_rate)
                target_results["dnn"] = res
                total_tests += 1
                print(f"  DNN:              acc={res['accuracy']:.4f}  p={res['p_value']:.6f}  "
                      f"CI=[{res['ci_95'][0]:.3f}, {res['ci_95'][1]:.3f}]")
            except Exception as e:
                print(f"  DNN failed: {e}")

        # --- 1D-CNN (sequence) ---
        if HAS_TORCH:
            try:
                from phase4_v2 import TimingSeqCNN
                seq_norm = pickle.load(open(os.path.join(MODELS_DIR, "seq_norm.pkl"), "rb"))
                seq_len = seq_norm["seq_len"]
                seq_mean = seq_norm["mean"]
                seq_std = seq_norm["std"]

                # Build test sequences from FULL raw data (unfiltered, like Phase 4)
                full_raw = pd.read_csv(os.path.join(DATA_DIR, "raw_timing_traces_v2.csv"))
                test_raw_full = full_raw[full_raw["key_id"].isin(test_agg["key_id"])]
                sequences = []
                valid_test_indices = []
                for idx, row in test_agg.iterrows():
                    key_id = row["key_id"]
                    t = test_raw_full[test_raw_full["key_id"] == key_id]["timing_cycles"].values
                    t = np.sort(t)
                    if len(t) >= seq_len:
                        seq = np.sort(t)[:seq_len]
                        sequences.append(seq)
                        valid_test_indices.append(idx)
                    else:
                        seq = np.sort(t)
                        seq = np.pad(seq, (0, seq_len - len(seq)), mode="edge")
                        sequences.append(seq)
                        valid_test_indices.append(idx)
                X_seq = np.array(sequences, dtype=np.float32)
                X_seq = (X_seq - seq_mean) / (seq_std + 1e-8)

                y_test_seq = test_agg.loc[valid_test_indices, target_name].values

                model = TimingSeqCNN(seq_len=seq_len)
                model.load_state_dict(torch.load(
                    os.path.join(MODELS_DIR, f"cnn_seq_{target_name}.pt"),
                    map_location="cpu", weights_only=True
                ))
                model.eval()
                with torch.no_grad():
                    X_t = torch.FloatTensor(X_seq).unsqueeze(1)
                    y_pred = model(X_t).argmax(1).numpy()
                res = evaluate_model("CNN-Seq", y_test_seq, y_pred, majority_rate)
                target_results["cnn_seq"] = res
                total_tests += 1
                print(f"  CNN-Seq:          acc={res['accuracy']:.4f}  p={res['p_value']:.6f}  "
                      f"CI=[{res['ci_95'][0]:.3f}, {res['ci_95'][1]:.3f}]")
            except Exception as e:
                print(f"  CNN-Seq failed: {e}")

        # Full classification report for best model
        non_dummy = {k: v for k, v in target_results.items() if k != "dummy"}
        if non_dummy:
            best_name = max(non_dummy, key=lambda k: non_dummy[k]["accuracy"])
            best = non_dummy[best_name]
            print(f"\n  Best model: {best_name} (acc={best['accuracy']:.4f})")
            print(f"  Confusion matrix:\n    {best['confusion_matrix']}")

        all_results[target_name] = target_results

    # --- GRAND SUMMARY ---
    print("\n" + "=" * 70)
    print("  GRAND SUMMARY (Bonferroni-corrected for multiple comparisons)")
    print("=" * 70)
    alpha = 0.05
    bonferroni_alpha = alpha / max(total_tests, 1)
    print(f"\n  Total hypothesis tests: {total_tests}")
    print(f"  Bonferroni-corrected alpha: {bonferroni_alpha:.6f}")

    print(f"\n  {'Target':<20} {'Model':<18} {'Acc':>6} {'p-value':>12} {'95% CI':>18} {'Sig?':>8}")
    print("  " + "-" * 82)

    any_significant = False
    for target_name, target_results in all_results.items():
        for model_name, res in target_results.items():
            if model_name == "dummy":
                continue
            acc = res["accuracy"]
            pval = res["p_value"]
            ci = res["ci_95"]
            sig_raw = pval < alpha
            sig_bonf = pval < bonferroni_alpha
            sig_str = "YES***" if sig_bonf else "yes*" if sig_raw else "no"
            if sig_bonf:
                any_significant = True
            print(f"  {target_name:<20} {model_name:<18} {acc:>6.4f} {pval:>12.6f} "
                  f"[{ci[0]:.3f}, {ci[1]:.3f}] {sig_str:>8}")

    print("\n" + "=" * 70)
    if any_significant:
        print("  *** CORE FINDING: Statistically significant timing leakage detected")
        print("      after Bonferroni correction for multiple comparisons.")
        print("      This is evidence against constant-time implementation claims.")
    else:
        print("  FINDING: No model achieved statistical significance after")
        print("  Bonferroni correction. Possible interpretations:")
        print("    1. The implementation IS effectively constant-time on this platform")
        print("    2. The signal is below our measurement resolution")
        print("    3. More traces or finer instrumentation may be needed")
        print("    4. The target variables may not correlate with timing")
        print("\n  NOTE: Even a null result is publishable — it provides evidence")
        print("  that liboqs ML-KEM-768 resists timing attacks on Apple Silicon.")
    print("=" * 70)

    # Save
    with open(os.path.join(DATA_DIR, "final_report_v2.json"), "w") as f:
        json.dump({
            "total_tests": total_tests,
            "bonferroni_alpha": bonferroni_alpha,
            "any_significant": any_significant,
            "results": all_results,
        }, f, indent=2, default=str)

    print(f"\nFull results saved to {os.path.join(DATA_DIR, 'final_report_v2.json')}")


if __name__ == "__main__":
    main()
