#!/usr/bin/env python3
"""
Phase 7: SCA-Triage Sensitivity Curve (False Negative Rate)

Injects synthetic timing leaks at varying Cohen's d effect sizes into
lognormal baseline data mimicking ML-KEM measurements, then runs the
full sca-triage pipeline to quantify the detection floor.
"""

import json
import os
import sys
import warnings
import numpy as np
from scipy import stats
from sklearn.model_selection import StratifiedKFold
from sklearn.feature_selection import mutual_info_classif
from sklearn.metrics import accuracy_score

try:
    from xgboost import XGBClassifier
    USE_XGB = True
except ImportError:
    from sklearn.ensemble import RandomForestClassifier
    USE_XGB = False

warnings.filterwarnings("ignore")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_JSON = os.path.join(PROJECT_DIR, "data", "phase7_sensitivity_curve.json")
OUTPUT_FIG = os.path.join(PROJECT_DIR, "figures", "fig_sensitivity_curve.png")

N_KEYS = 500
N_REPEATS = 50
EFFECT_SIZES = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0]
N_TRIALS = 20
N_MI_PERMS = 50
BONFERRONI_TESTS = 3  # Welch, KS, Levene
ALPHA = 0.05
XGB_LIFT_THRESH = 0.03  # 3% over chance


def generate_baseline(rng, n_keys=N_KEYS, n_repeats=N_REPEATS):
    """Generate lognormal timing data with median ~710 cycles, no leakage."""
    # lognormal: median = exp(mu), so mu = ln(710)
    mu = np.log(710)
    sigma = 0.03  # moderate right skew
    timings = rng.lognormal(mean=mu, sigma=sigma, size=(n_keys, n_repeats))
    # Assign random sk_lsb (roughly balanced)
    sk_lsb = rng.binomial(1, 0.5, size=n_keys)
    return timings, sk_lsb


def inject_leak(timings, sk_lsb, d, rng):
    """Add d * pooled_std to keys where sk_lsb=1."""
    timings_out = timings.copy()
    key_means = timings.mean(axis=1)
    pooled_std = np.std(key_means)
    mask = sk_lsb == 1
    shift = d * pooled_std
    timings_out[mask] += shift
    return timings_out


def aggregate_features(timings):
    """Compute per-key aggregated features."""
    feat_mean = timings.mean(axis=1)
    feat_median = np.median(timings, axis=1)
    feat_std = timings.std(axis=1)
    feat_iqr = np.percentile(timings, 75, axis=1) - np.percentile(timings, 25, axis=1)
    return np.column_stack([feat_mean, feat_median, feat_std, feat_iqr])


def welch_t_test(features, sk_lsb):
    """Welch's t-test on mean timing between groups."""
    means = features[:, 0]
    g0 = means[sk_lsb == 0]
    g1 = means[sk_lsb == 1]
    t_stat, p_val = stats.ttest_ind(g0, g1, equal_var=False)
    return float(abs(t_stat)), float(p_val)


def ks_test(features, sk_lsb):
    """KS test on mean timing between groups."""
    means = features[:, 0]
    g0 = means[sk_lsb == 0]
    g1 = means[sk_lsb == 1]
    stat, p_val = stats.ks_2samp(g0, g1)
    return float(stat), float(p_val)


def levene_test(features, sk_lsb):
    """Levene's test on mean timing between groups."""
    means = features[:, 0]
    g0 = means[sk_lsb == 0]
    g1 = means[sk_lsb == 1]
    stat, p_val = stats.levene(g0, g1)
    return float(stat), float(p_val)


def cohens_d(features, sk_lsb):
    """Compute observed Cohen's d."""
    means = features[:, 0]
    g0 = means[sk_lsb == 0]
    g1 = means[sk_lsb == 1]
    n0, n1 = len(g0), len(g1)
    pooled_std = np.sqrt(((n0 - 1) * np.var(g0, ddof=1) + (n1 - 1) * np.var(g1, ddof=1)) / (n0 + n1 - 2))
    if pooled_std == 0:
        return 0.0
    return float(abs(np.mean(g1) - np.mean(g0)) / pooled_std)


def ksg_mi(features, sk_lsb, n_perms=N_MI_PERMS, rng=None):
    """KSG MI on mean timing with permutation test."""
    X = features[:, 0].reshape(-1, 1)
    mi_obs = mutual_info_classif(X, sk_lsb, n_neighbors=5, random_state=42)[0]
    mi_nulls = []
    for i in range(n_perms):
        y_perm = rng.permutation(sk_lsb)
        mi_perm = mutual_info_classif(X, y_perm, n_neighbors=5, random_state=42)[0]
        mi_nulls.append(mi_perm)
    mi_nulls = np.array(mi_nulls)
    p_val = float(np.mean(mi_nulls >= mi_obs))
    return float(mi_obs), p_val


def xgb_accuracy(features, sk_lsb, rng):
    """3-fold CV accuracy of classifier on all features."""
    skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=int(rng.integers(0, 2**31)))
    accs = []
    for train_idx, test_idx in skf.split(features, sk_lsb):
        X_tr, X_te = features[train_idx], features[test_idx]
        y_tr, y_te = sk_lsb[train_idx], sk_lsb[test_idx]
        if USE_XGB:
            clf = XGBClassifier(
                n_estimators=50, max_depth=3, learning_rate=0.1,
                use_label_encoder=False, eval_metric="logloss",
                verbosity=0, random_state=42
            )
        else:
            clf = RandomForestClassifier(
                n_estimators=50, max_depth=3, random_state=42
            )
        clf.fit(X_tr, y_tr)
        preds = clf.predict(X_te)
        accs.append(accuracy_score(y_te, preds))
    return float(np.mean(accs))


def run_trial(d, seed):
    """Run one trial for a given effect size and seed. Returns dict of results."""
    rng = np.random.default_rng(seed)
    timings, sk_lsb = generate_baseline(rng)
    if d > 0:
        timings = inject_leak(timings, sk_lsb, d, rng)
    features = aggregate_features(timings)

    t_stat, t_p = welch_t_test(features, sk_lsb)
    ks_stat, ks_p = ks_test(features, sk_lsb)
    lev_stat, lev_p = levene_test(features, sk_lsb)
    obs_d = cohens_d(features, sk_lsb)
    mi_val, mi_p = ksg_mi(features, sk_lsb, rng=rng)
    xgb_acc = xgb_accuracy(features, sk_lsb, rng)

    # Bonferroni correction on 3 pairwise tests
    bonf_alpha = ALPHA / BONFERRONI_TESTS
    any_sig = (t_p < bonf_alpha) or (ks_p < bonf_alpha) or (lev_p < bonf_alpha)
    xgb_lift = xgb_acc - 0.5
    detected = any_sig or (xgb_lift > XGB_LIFT_THRESH)

    return {
        "detected": detected,
        "t_stat": t_stat, "t_p": t_p,
        "ks_stat": ks_stat, "ks_p": ks_p,
        "lev_stat": lev_stat, "lev_p": lev_p,
        "cohens_d": obs_d,
        "mi": mi_val, "mi_p": mi_p,
        "xgb_acc": xgb_acc,
    }


def main():
    print("=" * 65)
    print("SCA-TRIAGE SENSITIVITY CURVE (FALSE NEGATIVE RATE)")
    print("=" * 65)
    print(f"  Keys: {N_KEYS}, Repeats: {N_REPEATS}, Trials: {N_TRIALS}")
    print(f"  Effect sizes: {EFFECT_SIZES}")
    print(f"  Classifier: {'XGBoost' if USE_XGB else 'RandomForest'}")
    print()

    all_results = {}

    for d in EFFECT_SIZES:
        trial_results = []
        for trial in range(N_TRIALS):
            seed = int(d * 10000) + trial * 1000 + 42
            res = run_trial(d, seed)
            trial_results.append(res)
        all_results[str(d)] = trial_results
        n_det = sum(r["detected"] for r in trial_results)
        mean_acc = np.mean([r["xgb_acc"] for r in trial_results])
        mean_t = np.mean([r["t_stat"] for r in trial_results])
        mean_mi = np.mean([r["mi"] for r in trial_results])
        pct = 100.0 * n_det / N_TRIALS
        sys.stdout.write(
            f"  d={d:<6.3f} | det={n_det:>2}/{N_TRIALS} ({pct:5.1f}%) | "
            f"XGB={mean_acc:.3f} | t={mean_t:.2f} | MI={mean_mi:.4f}\n"
        )
        sys.stdout.flush()

    # Compute summary table
    print()
    print("=" * 65)
    print(f"{'Injected d':>10} | {'Detection Rate':>14} | {'Mean XGB Acc':>11} | {'Mean t-stat':>11} | {'Mean MI':>7}")
    print(f"{'-'*10}-+-{'-'*14}-+-{'-'*11}-+-{'-'*11}-+-{'-'*7}")

    detection_rates = {}
    summary_rows = []
    for d in EFFECT_SIZES:
        trials = all_results[str(d)]
        n_det = sum(r["detected"] for r in trials)
        rate = n_det / N_TRIALS
        detection_rates[d] = rate
        mean_acc = np.mean([r["xgb_acc"] for r in trials]) * 100
        mean_t = np.mean([r["t_stat"] for r in trials])
        mean_mi = np.mean([r["mi"] for r in trials])
        summary_rows.append({
            "d": d, "n_det": n_det, "rate": rate,
            "mean_acc": mean_acc, "mean_t": mean_t, "mean_mi": mean_mi,
        })
        print(
            f"{d:>10.3f} | {n_det:>2}/{N_TRIALS} ({rate*100:5.1f}%) "
            f"| {mean_acc:>10.1f}% | {mean_t:>11.2f} | {mean_mi:>7.4f}"
        )

    # Detection floor: smallest d with >= 80% detection
    floor_d = None
    for row in summary_rows:
        if row["rate"] >= 0.80:
            floor_d = row["d"]
            break

    if floor_d is not None:
        # Interpolate between the point just below 80% and this point
        idx = EFFECT_SIZES.index(floor_d)
        if idx > 0:
            d_lo = EFFECT_SIZES[idx - 1]
            r_lo = detection_rates[d_lo]
            d_hi = floor_d
            r_hi = detection_rates[d_hi]
            if r_hi > r_lo:
                interp_d = d_lo + (0.80 - r_lo) / (r_hi - r_lo) * (d_hi - d_lo)
            else:
                interp_d = floor_d
        else:
            interp_d = floor_d
        print(f"\nDetection Floor: d ~ {interp_d:.3f} (80% detection rate)")
    else:
        interp_d = None
        print(f"\nDetection Floor: NOT REACHED within tested range")

    print("=" * 65)

    # Save JSON
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    json_out = {
        "config": {
            "n_keys": N_KEYS, "n_repeats": N_REPEATS, "n_trials": N_TRIALS,
            "n_mi_perms": N_MI_PERMS, "alpha": ALPHA,
            "bonferroni_tests": BONFERRONI_TESTS,
            "xgb_lift_threshold": XGB_LIFT_THRESH,
            "classifier": "XGBoost" if USE_XGB else "RandomForest",
            "effect_sizes": EFFECT_SIZES,
        },
        "summary": summary_rows,
        "detection_floor_d": float(interp_d) if interp_d else None,
        "raw_trials": {
            str(d): all_results[str(d)] for d in EFFECT_SIZES
        },
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(json_out, f, indent=2)
    print(f"\nResults saved to {OUTPUT_JSON}")

    # Generate plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(os.path.dirname(OUTPUT_FIG), exist_ok=True)

        ds = [r["d"] for r in summary_rows]
        rates = [r["rate"] * 100 for r in summary_rows]
        accs = [r["mean_acc"] for r in summary_rows]

        fig, ax1 = plt.subplots(figsize=(9, 5.5))

        # Detection rate (primary axis)
        color1 = "#2563eb"
        ax1.plot(ds, rates, "o-", color=color1, linewidth=2, markersize=6,
                 label="Detection Rate", zorder=5)
        ax1.set_xscale("log")
        ax1.set_xlabel("Injected Cohen's d (log scale)", fontsize=12)
        ax1.set_ylabel("Detection Rate (%)", fontsize=12, color=color1)
        ax1.tick_params(axis="y", labelcolor=color1)
        ax1.set_ylim(-5, 105)
        ax1.set_xlim(min(ds) * 0.7, max(ds) * 1.5)

        # 80% threshold line
        ax1.axhline(80, color="gray", linestyle="--", linewidth=1, alpha=0.7,
                     label="80% power threshold")

        # Detection floor vertical line
        if interp_d is not None:
            ax1.axvline(interp_d, color="red", linestyle="--", linewidth=1, alpha=0.7)
            ax1.annotate(
                f"Detection floor\nd ~ {interp_d:.3f}",
                xy=(interp_d, 80), xytext=(interp_d * 2.5, 60),
                fontsize=9,
                arrowprops=dict(arrowstyle="->", color="red", lw=1.2),
                color="red", ha="left",
            )

        # XGBoost accuracy (secondary axis)
        ax2 = ax1.twinx()
        color2 = "#d97706"
        ax2.plot(ds, accs, "s--", color=color2, linewidth=1.5, markersize=5,
                 label="Mean XGB Accuracy", alpha=0.8)
        ax2.set_ylabel("Mean Classifier Accuracy (%)", fontsize=12, color=color2)
        ax2.tick_params(axis="y", labelcolor=color2)
        ax2.set_ylim(45, 105)

        # Combined legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="lower right", fontsize=9)

        ax1.set_title("sca-triage Detection Sensitivity vs. Effect Size", fontsize=13, pad=12)
        ax1.grid(True, alpha=0.3, which="both")
        fig.tight_layout()
        fig.savefig(OUTPUT_FIG, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"Figure saved to {OUTPUT_FIG}")

    except Exception as e:
        print(f"Warning: Could not generate plot: {e}")


if __name__ == "__main__":
    main()
