#!/usr/bin/env python3
"""
phase5_v3.py

Phase 5 (v3): Final evaluation combining TVLA + ML results.

Reports:
1. TVLA results (if available)
2. All ML model results on test set with Bonferroni correction
3. NICV summary
4. Combined conclusion

ANTI-LEAKAGE: Test set used ONCE, here.
"""

import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
                             confusion_matrix)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models_v3")

TARGETS = {
    "target_rejection": "FO implicit rejection",
    "target_msg_hw_parity": "Message HW parity",
    "target_msg_hw_bin": "Message HW >= median",
    "target_coeff0_hw_bin": "Coeff0 HW >= median",
    "target_sk_lsb": "LSB of sk[0]",
}


def binomial_test(y_true, y_pred, null_p=0.5):
    n = len(y_true)
    k = int(np.sum(y_pred == y_true))
    result = sp_stats.binomtest(k, n, null_p, alternative="greater")
    return result.pvalue, k, n


def wilson_ci(k, n, z=1.96):
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
        "name": name, "accuracy": float(acc), "precision": float(prec),
        "recall": float(rec), "f1": float(f1),
        "confusion_matrix": cm.tolist(), "p_value": float(p_value),
        "correct": int(k), "total": int(n), "ci_95": [float(ci_lo), float(ci_hi)],
    }


def main():
    print("=" * 70)
    print("  PHASE 5 v3: COMBINED TVLA + ML EVALUATION")
    print("=" * 70)

    # --- Part 1: TVLA Results ---
    tvla_path = os.path.join(DATA_DIR, "tvla_results.json")
    if os.path.exists(tvla_path):
        tvla = json.load(open(tvla_path))
        print(f"\n{'='*60}")
        print(f"  TVLA RESULTS (Fixed-vs-Random Welch's T-Test)")
        print(f"{'='*60}")
        print(f"  Traces per class: {tvla['traces_per_class']:,}")
        print(f"  Fixed:  mean={tvla['fixed_mean']:.1f}, std={tvla['fixed_std']:.1f}")
        print(f"  Random: mean={tvla['random_mean']:.1f}, std={tvla['random_std']:.1f}")
        print(f"  |t| = {tvla['abs_t']:.4f}  (threshold: 4.5)")
        print(f"  Leakage detected: {'YES' if tvla['leakage_detected'] else 'NO'}")
    else:
        print(f"\n  TVLA results not yet available ({tvla_path})")
        tvla = None

    # --- Part 2: ML Results on Test Set ---
    print(f"\n{'='*60}")
    print(f"  ML MODEL EVALUATION ON UNTOUCHED TEST SET")
    print(f"{'='*60}")

    meta = json.load(open(os.path.join(DATA_DIR, "split_metadata_v3.json")))
    feature_names = meta["feature_names"]
    available_features = feature_names

    test = pd.read_csv(os.path.join(DATA_DIR, "test_v3.csv"))
    scaler = pickle.load(open(os.path.join(MODELS_DIR, "scaler_v3.pkl"), "rb"))

    feats_in_test = [f for f in available_features if f in test.columns]
    X_test = np.nan_to_num(scaler.transform(test[feats_in_test].values),
                            nan=0, posinf=0, neginf=0)

    print(f"  Test set: {len(test)} keys, {len(feats_in_test)} features")

    all_results = {}
    total_tests = 0

    for target_name, target_desc in TARGETS.items():
        if target_name not in test.columns:
            continue

        print(f"\n{'-'*50}")
        print(f"  TARGET: {target_name} ({target_desc})")
        print(f"{'-'*50}")

        y_test = test[target_name].values.astype(int)
        class_dist = np.bincount(y_test)
        majority_rate = max(class_dist) / len(y_test)
        print(f"  Classes: {class_dist}, majority rate: {majority_rate:.4f}")

        target_results = {}

        # Dummy
        try:
            dummy = pickle.load(open(os.path.join(MODELS_DIR, f"dummy_{target_name}.pkl"), "rb"))
            res = evaluate_model("Dummy", y_test, dummy.predict(X_test), majority_rate)
            target_results["dummy"] = res
            print(f"  Dummy:      acc={res['accuracy']:.4f}")
        except Exception as e:
            print(f"  Dummy: {e}")

        # XGBoost
        try:
            model = pickle.load(open(os.path.join(MODELS_DIR, f"best_xgb_{target_name}.pkl"), "rb"))
            res = evaluate_model("XGBoost", y_test, model.predict(X_test), majority_rate)
            target_results["xgboost"] = res
            total_tests += 1
            print(f"  XGBoost:    acc={res['accuracy']:.4f}  p={res['p_value']:.6f}  "
                  f"CI=[{res['ci_95'][0]:.3f},{res['ci_95'][1]:.3f}]")
        except Exception as e:
            print(f"  XGBoost: {e}")

        # RandomForest
        try:
            model = pickle.load(open(os.path.join(MODELS_DIR, f"best_rf_{target_name}.pkl"), "rb"))
            res = evaluate_model("RandomForest", y_test, model.predict(X_test), majority_rate)
            target_results["random_forest"] = res
            total_tests += 1
            print(f"  RF:         acc={res['accuracy']:.4f}  p={res['p_value']:.6f}  "
                  f"CI=[{res['ci_95'][0]:.3f},{res['ci_95'][1]:.3f}]")
        except Exception as e:
            print(f"  RF: {e}")

        # GradientBoosting
        try:
            model = pickle.load(open(os.path.join(MODELS_DIR, f"gb_{target_name}.pkl"), "rb"))
            res = evaluate_model("GradientBoosting", y_test, model.predict(X_test), majority_rate)
            target_results["gradient_boosting"] = res
            total_tests += 1
            print(f"  GB:         acc={res['accuracy']:.4f}  p={res['p_value']:.6f}  "
                  f"CI=[{res['ci_95'][0]:.3f},{res['ci_95'][1]:.3f}]")
        except Exception as e:
            print(f"  GB: {e}")

        all_results[target_name] = target_results

    # --- Grand Summary ---
    print(f"\n{'='*70}")
    print(f"  GRAND SUMMARY (Bonferroni-corrected)")
    print(f"{'='*70}")

    alpha = 0.05
    bonferroni_alpha = alpha / max(total_tests, 1)
    print(f"\n  Total hypothesis tests: {total_tests}")
    print(f"  Bonferroni alpha: {bonferroni_alpha:.6f}")

    print(f"\n  {'Target':<25} {'Model':<18} {'Acc':>6} {'p-value':>12} {'95% CI':>18} {'Sig?':>8}")
    print("  " + "-" * 87)

    any_significant = False
    for target_name, target_results in all_results.items():
        for model_name, res in target_results.items():
            if model_name == "dummy":
                continue
            acc = res["accuracy"]
            pval = res["p_value"]
            ci = res["ci_95"]
            sig_bonf = pval < bonferroni_alpha
            sig_raw = pval < alpha
            sig_str = "YES***" if sig_bonf else "yes*" if sig_raw else "no"
            if sig_bonf:
                any_significant = True
            print(f"  {target_name:<25} {model_name:<18} {acc:>6.4f} {pval:>12.6f} "
                  f"[{ci[0]:.3f},{ci[1]:.3f}] {sig_str:>8}")

    # --- Combined Conclusion ---
    print(f"\n{'='*70}")
    print(f"  COMBINED CONCLUSION")
    print(f"{'='*70}")

    tvla_leaks = tvla["leakage_detected"] if tvla else None
    ml_leaks = any_significant

    if tvla_leaks and ml_leaks:
        print(f"\n  STRONG EVIDENCE OF TIMING LEAKAGE:")
        print(f"    - TVLA confirms distinguishable timing distributions")
        print(f"    - ML models extract exploitable signal from timing data")
        print(f"    - This constitutes a side-channel vulnerability in ML-KEM-768")
    elif tvla_leaks and not ml_leaks:
        print(f"\n  WEAK/THEORETICAL LEAKAGE:")
        print(f"    - TVLA detects statistical distinguishability")
        print(f"    - But ML models cannot exploit it for key recovery")
        print(f"    - Leakage exists but may be below exploitation threshold")
    elif not tvla_leaks and ml_leaks:
        print(f"\n  UNEXPECTED: ML detects signal TVLA misses")
        print(f"    - Investigate for possible methodology error")
        print(f"    - ML may be capturing non-linear leakage invisible to TVLA")
    else:
        print(f"\n  NO TIMING LEAKAGE DETECTED:")
        if tvla:
            print(f"    - TVLA: |t|={tvla['abs_t']:.4f} < 4.5 (no distinguishability)")
        print(f"    - ML: No model beats majority-class baseline after Bonferroni")
        print(f"    - Conclusion: liboqs ML-KEM-768 decapsulation appears")
        print(f"      constant-time on Apple Silicon under realistic load")
        print(f"\n  This null result is publishable as evidence that:")
        print(f"    1. liboqs has mitigated KyberSlash on ARM/macOS")
        print(f"    2. FO transform implicit rejection is constant-time")
        print(f"    3. Compiler-generated code maintains timing guarantees")
    print(f"{'='*70}")

    # Save
    final = {
        "tvla": tvla,
        "ml_results": all_results,
        "total_ml_tests": total_tests,
        "bonferroni_alpha": bonferroni_alpha,
        "any_ml_significant": ml_leaks,
        "tvla_leakage": tvla_leaks,
    }
    with open(os.path.join(DATA_DIR, "final_report_v3.json"), "w") as f:
        json.dump(final, f, indent=2, default=str)
    print(f"\nSaved to {os.path.join(DATA_DIR, 'final_report_v3.json')}")


if __name__ == "__main__":
    main()
