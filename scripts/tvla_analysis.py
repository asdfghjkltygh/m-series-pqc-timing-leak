#!/usr/bin/env python3
"""
tvla_analysis.py

Test Vector Leakage Assessment (TVLA) for ML-KEM-768 decapsulation.

Implements the Fixed-vs-Random Welch's t-test methodology:
- Collects N traces with a FIXED (ct, sk) pair
- Collects N traces with RANDOM (ct, sk) pairs each time
- Computes Welch's t-statistic
- t > 4.5 indicates >99.999% confidence of timing leakage

This is the industry-standard first-line test for side-channel leakage
(FIPS 140-3 / ISO 17825 compliant methodology).

Usage: python3 tvla_analysis.py [--traces N]
"""

import argparse
import os
import subprocess
import sys
import time
import threading

import numpy as np
from scipy import stats as sp_stats

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TVLA_BIN = os.path.join(PROJECT_DIR, "src", "tvla_harness")
DATA_DIR = os.path.join(PROJECT_DIR, "data")


def background_load_worker(stop_event):
    x = 1.0001
    while not stop_event.is_set():
        for _ in range(100_000):
            x = (x * 1.0001) % 1e10
        time.sleep(0)


def collect_traces(mode, num_traces):
    """Run tvla_harness and return array of cycle counts."""
    proc = subprocess.run(
        [TVLA_BIN, mode, str(num_traces)],
        capture_output=True, text=True, timeout=7200
    )
    if proc.returncode != 0:
        print(f"tvla_harness [{mode}] failed: {proc.stderr}", file=sys.stderr)
        sys.exit(1)
    lines = proc.stdout.strip().split("\n")
    return np.array([int(line.strip()) for line in lines if line.strip()], dtype=np.int64)


def welch_t_test(fixed, random):
    """Compute Welch's t-statistic and p-value."""
    t_stat, p_value = sp_stats.ttest_ind(fixed, random, equal_var=False)
    return t_stat, p_value


def progressive_tvla(fixed, random, step=10000):
    """Compute TVLA t-statistic at increasing trace counts."""
    results = []
    max_n = min(len(fixed), len(random))
    for n in range(step, max_n + 1, step):
        t, p = welch_t_test(fixed[:n], random[:n])
        results.append({"n": n, "t_statistic": float(t), "p_value": float(p)})
    return results


def main():
    parser = argparse.ArgumentParser(description="TVLA for ML-KEM-768")
    parser.add_argument("--traces", type=int, default=500000,
                        help="Number of traces per class (default: 500000)")
    parser.add_argument("--load-threads", type=int, default=4,
                        help="Background load threads (default: 4)")
    args = parser.parse_args()

    n = args.traces
    print(f"[TVLA] Fixed-vs-Random Welch's T-Test for ML-KEM-768 Decapsulation")
    print(f"  Traces per class: {n:,}")
    print(f"  Total measurements: {2*n:,}")
    print(f"  Leakage threshold: |t| > 4.5")

    # Start background load
    stop_event = threading.Event()
    load_threads = []
    if args.load_threads > 0:
        print(f"  Background load threads: {args.load_threads}")
        for _ in range(args.load_threads):
            t = threading.Thread(target=background_load_worker, args=(stop_event,), daemon=True)
            t.start()
            load_threads.append(t)

    # Collect fixed traces
    print(f"\n[TVLA] Collecting {n:,} FIXED traces...")
    t0 = time.time()
    fixed = collect_traces("fixed", n)
    t1 = time.time()
    print(f"  Collected {len(fixed):,} fixed traces in {t1-t0:.1f}s")
    print(f"  Fixed stats: mean={np.mean(fixed):.1f}, median={np.median(fixed):.1f}, "
          f"std={np.std(fixed):.1f}")

    # Collect random traces
    print(f"\n[TVLA] Collecting {n:,} RANDOM traces...")
    t2 = time.time()
    random_traces = collect_traces("random", n)
    t3 = time.time()
    print(f"  Collected {len(random_traces):,} random traces in {t3-t2:.1f}s")
    print(f"  Random stats: mean={np.mean(random_traces):.1f}, median={np.median(random_traces):.1f}, "
          f"std={np.std(random_traces):.1f}")

    # Stop background load
    if load_threads:
        stop_event.set()
        for t in load_threads:
            t.join(timeout=5)

    # --- Main TVLA Result ---
    print(f"\n{'='*60}")
    print(f"  TVLA RESULT")
    print(f"{'='*60}")

    t_stat, p_value = welch_t_test(fixed, random_traces)
    print(f"\n  Welch's t-statistic: {t_stat:.6f}")
    print(f"  p-value:             {p_value:.2e}")
    print(f"  |t|:                 {abs(t_stat):.6f}")

    if abs(t_stat) > 4.5:
        print(f"\n  *** LEAKAGE DETECTED ***")
        print(f"  |t| = {abs(t_stat):.4f} > 4.5")
        print(f"  The fixed input produces STATISTICALLY DISTINGUISHABLE")
        print(f"  timing distributions from random inputs.")
        print(f"  Confidence: >99.999%")
        leakage_detected = True
    else:
        print(f"\n  NO LEAKAGE DETECTED")
        print(f"  |t| = {abs(t_stat):.4f} <= 4.5")
        print(f"  The implementation appears constant-time for this test.")
        leakage_detected = False

    # --- Progressive analysis (how t evolves with more traces) ---
    print(f"\n[TVLA] Progressive analysis (t-statistic vs trace count):")
    step = max(len(fixed) // 20, 1000)
    prog = progressive_tvla(fixed, random_traces, step=step)
    print(f"\n  {'Traces':>10} {'|t|':>10} {'Leakage?':>10}")
    print(f"  {'-'*30}")
    for r in prog:
        leak = "YES" if abs(r["t_statistic"]) > 4.5 else "no"
        print(f"  {r['n']:>10,} {abs(r['t_statistic']):>10.4f} {leak:>10}")

    # --- Quantile-filtered TVLA ---
    # Apply same filtering philosophy: keep only fastest timings
    # to see if leakage is clearer in the "clean" subset
    print(f"\n[TVLA] Quantile-filtered TVLA (bottom 10%, 25%, 50%):")
    for pct_label, pct in [("10%", 0.10), ("25%", 0.25), ("50%", 0.50)]:
        # Compute threshold from fixed set (or combined — doesn't matter for TVLA,
        # since we're not doing ML prediction, just statistical comparison)
        combined = np.concatenate([fixed, random_traces])
        thresh = np.percentile(combined, pct * 100)
        f_filt = fixed[fixed <= thresh]
        r_filt = random_traces[random_traces <= thresh]
        if len(f_filt) > 100 and len(r_filt) > 100:
            t_f, p_f = welch_t_test(f_filt, r_filt)
            print(f"  Bottom {pct_label}: thresh={thresh:.0f} cycles, "
                  f"n_fixed={len(f_filt):,}, n_random={len(r_filt):,}, "
                  f"|t|={abs(t_f):.4f}, leakage={'YES' if abs(t_f) > 4.5 else 'no'}")
        else:
            print(f"  Bottom {pct_label}: insufficient samples after filtering")

    # Save results
    import json
    results = {
        "methodology": "Fixed-vs-Random Welch's T-Test (TVLA)",
        "traces_per_class": int(n),
        "fixed_mean": float(np.mean(fixed)),
        "fixed_std": float(np.std(fixed)),
        "fixed_median": float(np.median(fixed)),
        "random_mean": float(np.mean(random_traces)),
        "random_std": float(np.std(random_traces)),
        "random_median": float(np.median(random_traces)),
        "t_statistic": float(t_stat),
        "abs_t": float(abs(t_stat)),
        "p_value": float(p_value),
        "leakage_threshold": 4.5,
        "leakage_detected": leakage_detected,
        "progressive": prog,
    }

    output_path = os.path.join(DATA_DIR, "tvla_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[TVLA] Results saved to {output_path}")

    # Save raw trace data for further analysis
    np.savez_compressed(
        os.path.join(DATA_DIR, "tvla_traces.npz"),
        fixed=fixed, random=random_traces
    )
    print(f"[TVLA] Raw traces saved to {os.path.join(DATA_DIR, 'tvla_traces.npz')}")


if __name__ == "__main__":
    main()
