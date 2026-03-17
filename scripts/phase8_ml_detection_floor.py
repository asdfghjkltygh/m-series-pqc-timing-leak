#!/usr/bin/env python3
"""
Phase 8: ML Detection Floor

Determines the minimum Cohen's d at which ML classification (XGBoost or
RandomForest) reliably detects secret-dependent timing leakage, defined as
achieving >55% accuracy in >=80% of trials.

This complements Phase 7 (full triage pipeline sensitivity) by isolating
the ML classifier's detection capability.
"""

import json
import os
import sys
import time
import warnings
import numpy as np
from scipy import stats
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

try:
    from xgboost import XGBClassifier
    USE_XGB = True
except ImportError:
    from sklearn.ensemble import RandomForestClassifier
    USE_XGB = False

warnings.filterwarnings("ignore")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_JSON = os.path.join(PROJECT_DIR, "data", "phase8_ml_detection_floor.json")

# ── Configuration ──────────────────────────────────────────────────────
N_KEYS = 500
N_REPEATS = 50
EFFECT_SIZES = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5]
N_TRIALS = 30
ACC_THRESHOLD = 0.55       # >55% accuracy
RELIABILITY_THRESHOLD = 0.80  # in >=80% of trials
TTEST_FLOOR_D = 0.398      # from prior analysis
TTEST_FLOOR_CYCLES = 454
KYBERSLASH_D = 0.094


def generate_baseline(rng, n_keys=N_KEYS, n_repeats=N_REPEATS):
    """Generate lognormal timing data with median ~710 cycles, no leakage."""
    mu = np.log(710)
    sigma = 0.03  # moderate right skew
    timings = rng.lognormal(mean=mu, sigma=sigma, size=(n_keys, n_repeats))
    sk_lsb = rng.binomial(1, 0.5, size=n_keys)
    return timings, sk_lsb


def inject_leak(timings, sk_lsb, d):
    """Add d * pooled_std to keys where sk_lsb=1."""
    timings_out = timings.copy()
    key_means = timings.mean(axis=1)
    pooled_std = np.std(key_means)
    mask = sk_lsb == 1
    shift = d * pooled_std
    timings_out[mask] += shift
    return timings_out


def aggregate_features(timings):
    """Compute per-key aggregated features: mean, median, std, IQR, p99, kurtosis, skew."""
    feat_mean = timings.mean(axis=1)
    feat_median = np.median(timings, axis=1)
    feat_std = timings.std(axis=1)
    feat_iqr = np.percentile(timings, 75, axis=1) - np.percentile(timings, 25, axis=1)
    feat_p99 = np.percentile(timings, 99, axis=1)
    feat_kurtosis = stats.kurtosis(timings, axis=1)
    feat_skew = stats.skew(timings, axis=1)
    return np.column_stack([
        feat_mean, feat_median, feat_std, feat_iqr,
        feat_p99, feat_kurtosis, feat_skew,
    ])


def build_classifier(seed):
    """Build the ML classifier."""
    if USE_XGB:
        return XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            use_label_encoder=False, eval_metric="logloss",
            verbosity=0, random_state=seed,
        )
    else:
        return RandomForestClassifier(
            n_estimators=100, max_depth=4, random_state=seed,
        )


def run_trial(d, seed):
    """Run one trial: generate data, inject leak, train classifier, return accuracy."""
    rng = np.random.default_rng(seed)
    timings, sk_lsb = generate_baseline(rng)
    if d > 0:
        timings = inject_leak(timings, sk_lsb, d)
    features = aggregate_features(timings)

    # 80/20 stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        features, sk_lsb, test_size=0.20, stratify=sk_lsb,
        random_state=int(rng.integers(0, 2**31)),
    )

    clf = build_classifier(seed)
    clf.fit(X_train, y_train)
    preds = clf.predict(X_test)
    acc = accuracy_score(y_test, preds)
    return float(acc)


def main():
    t0 = time.time()
    clf_name = "XGBoost" if USE_XGB else "RandomForest"

    print("=" * 65)
    print("PHASE 8: ML DETECTION FLOOR")
    print("=" * 65)
    print(f"  Classifier:    {clf_name}")
    print(f"  Keys: {N_KEYS}, Repeats: {N_REPEATS}, Trials per d: {N_TRIALS}")
    print(f"  Threshold:     >{ACC_THRESHOLD*100:.0f}% accuracy in >={RELIABILITY_THRESHOLD*100:.0f}% of trials")
    print(f"  Effect sizes:  {EFFECT_SIZES}")
    print()

    all_results = {}
    summary_rows = []

    for d in EFFECT_SIZES:
        accs = []
        for trial in range(N_TRIALS):
            seed = int(d * 100000) + trial * 137 + 7
            acc = run_trial(d, seed)
            accs.append(acc)

        accs = np.array(accs)
        mean_acc = float(np.mean(accs))
        std_acc = float(np.std(accs))
        n_above = int(np.sum(accs > ACC_THRESHOLD))
        frac_above = n_above / N_TRIALS
        reliable = frac_above >= RELIABILITY_THRESHOLD

        row = {
            "d": d,
            "mean_acc": mean_acc,
            "std_acc": std_acc,
            "n_above_55": n_above,
            "frac_above_55": frac_above,
            "reliable": reliable,
            "all_accs": [float(a) for a in accs],
        }
        summary_rows.append(row)
        all_results[str(d)] = row

        tag = "  <<< RELIABLE" if reliable else ""
        sys.stdout.write(
            f"  d={d:<6.3f} | acc={mean_acc:.3f} +/- {std_acc:.3f} | "
            f">55%: {n_above:>2}/{N_TRIALS} ({frac_above*100:5.1f}%){tag}\n"
        )
        sys.stdout.flush()

    # ── Determine ML detection floor ──────────────────────────────────
    ml_floor_d = None
    for row in summary_rows:
        if row["reliable"]:
            ml_floor_d = row["d"]
            break

    # Interpolate between last non-reliable and first reliable
    interp_d = ml_floor_d
    if ml_floor_d is not None:
        idx = EFFECT_SIZES.index(ml_floor_d)
        if idx > 0:
            prev = summary_rows[idx - 1]
            curr = summary_rows[idx]
            f_lo = prev["frac_above_55"]
            f_hi = curr["frac_above_55"]
            d_lo = prev["d"]
            d_hi = curr["d"]
            if f_hi > f_lo:
                interp_d = d_lo + (RELIABILITY_THRESHOLD - f_lo) / (f_hi - f_lo) * (d_hi - d_lo)
            else:
                interp_d = ml_floor_d

    # ── Comparison output ─────────────────────────────────────────────
    print()
    print("=" * 61)
    print("ML vs T-TEST DETECTION FLOOR COMPARISON")
    print("=" * 61)
    print()

    if interp_d is not None:
        ratio = TTEST_FLOOR_D / interp_d
        # Estimate cycle shift at ML floor
        # pooled_std of key means for lognormal(ln(710), 0.03) with 50 repeats
        # std of key means ~ 710 * 0.03 / sqrt(50) ~ 3.01
        # But inject_leak uses np.std(key_means) which is the key-mean std ~ 710*0.03/sqrt(50)
        approx_pooled_std = 710 * 0.03 / np.sqrt(N_REPEATS)
        ml_floor_cycles = interp_d * approx_pooled_std

        print(f"  T-test detection floor:    d = {TTEST_FLOOR_D} ({TTEST_FLOOR_CYCLES} cycles at 80% power)")
        print(f"  ML detection floor:        d = {interp_d:.3f} (>{ACC_THRESHOLD*100:.0f}% acc in {RELIABILITY_THRESHOLD*100:.0f}% of trials)")
        print(f"  Positive control (KyberSlash): d = {KYBERSLASH_D}")
        print()
        if ratio > 1.0:
            print(f"  The ML pipeline detects leakage at {ratio:.1f}x smaller effect sizes")
            print(f"  than the statistical t-test floor.")
        else:
            inv_ratio = 1.0 / ratio
            print(f"  The t-test detects leakage at {inv_ratio:.1f}x smaller effect sizes")
            print(f"  than the ML classifier floor.")
            print(f"  ML requires {inv_ratio:.1f}x larger effects to achieve reliable detection.")
        if interp_d <= KYBERSLASH_D:
            print(f"  ML floor ({interp_d:.3f}) <= KyberSlash effect ({KYBERSLASH_D}) -- ML can detect real-world leaks.")
        else:
            print(f"  ML floor ({interp_d:.3f}) > KyberSlash effect ({KYBERSLASH_D}) -- ML misses KyberSlash-scale leaks.")
    else:
        print(f"  T-test detection floor:    d = {TTEST_FLOOR_D} ({TTEST_FLOOR_CYCLES} cycles at 80% power)")
        print(f"  ML detection floor:        NOT REACHED within tested range")
        print(f"  Positive control (KyberSlash): d = {KYBERSLASH_D}")
        print()
        print(f"  ML classification did not reliably exceed {ACC_THRESHOLD*100:.0f}% accuracy")
        print(f"  at any tested effect size.")

    print()
    print("=" * 61)

    elapsed = time.time() - t0
    print(f"\nCompleted in {elapsed:.1f}s")

    # ── Save JSON ─────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    json_out = {
        "config": {
            "n_keys": N_KEYS,
            "n_repeats": N_REPEATS,
            "n_trials": N_TRIALS,
            "acc_threshold": ACC_THRESHOLD,
            "reliability_threshold": RELIABILITY_THRESHOLD,
            "classifier": clf_name,
            "effect_sizes": EFFECT_SIZES,
        },
        "summary": [
            {k: v for k, v in row.items() if k != "all_accs"}
            for row in summary_rows
        ],
        "ml_detection_floor_d": float(interp_d) if interp_d is not None else None,
        "ml_detection_floor_d_raw": float(ml_floor_d) if ml_floor_d is not None else None,
        "ttest_detection_floor_d": TTEST_FLOOR_D,
        "ttest_detection_floor_cycles": TTEST_FLOOR_CYCLES,
        "kyberslash_d": KYBERSLASH_D,
        "ratio_ttest_over_ml": float(TTEST_FLOOR_D / interp_d) if interp_d else None,
        "raw_trials": {
            str(d): row["all_accs"] for d, row in zip(EFFECT_SIZES, summary_rows)
        },
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(json_out, f, indent=2)
    print(f"Results saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
