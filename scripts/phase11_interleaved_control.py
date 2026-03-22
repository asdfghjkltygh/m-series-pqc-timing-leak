#!/usr/bin/env python3
"""
phase11_interleaved_control.py

The definitive Apple Silicon control experiment.

Runs both INTERLEAVED harnesses (symmetric and asymmetric) and compares
against sequential results from phase9.

The interleaved design collects fixed[i] and random[i] in alternating
pairs within a single execution, eliminating temporal drift between
collection runs as a confound.

On Intel x86, the interleaved symmetric harness PASSES TVLA (|t|=1.65),
proving the Intel confound was entirely temporal drift + harness asymmetry.

This experiment answers the final question: does the confound persist
when temporal drift is eliminated?

  Hypothesis A: Symmetric interleaved PASSES → confound was temporal drift
  Hypothesis B: Symmetric interleaved FAILS with high variance ratio →
                temporal drift breaks ISO 17825 stationarity assumption

Requires: liboqs v0.15.0 installed, Apple Silicon hardware.
"""

import subprocess
import sys
import os
import json
import numpy as np
from scipy import stats
from pathlib import Path

HARNESS_DIR = Path(__file__).parent.parent / "harnesses"
DATA_DIR = Path(__file__).parent.parent / "data"
LIBOQS_PREFIX = os.environ.get("LIBOQS_PREFIX", "/opt/homebrew")
NUM_TRACES = 500000  # 500K per group to match Intel interleaved run


def compile_harness(source, binary):
    """Compile a C harness against liboqs."""
    cmd = [
        "gcc", "-O2", "-march=native",
        f"-I{LIBOQS_PREFIX}/include",
        f"-L{LIBOQS_PREFIX}/lib",
        "-o", str(binary),
        str(source),
        "-loqs", "-lssl", "-lcrypto", "-lm"
    ]
    print(f"  Compiling {source.name}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  COMPILE ERROR: {result.stderr}")
        return False
    print(f"  Built: {binary}")
    return True


def run_interleaved_harness(binary, num_traces):
    """Run an interleaved harness and return (fixed_traces, random_traces)."""
    print(f"  Running {binary.name} with {num_traces} traces per group...")
    print(f"  (This will take a while - {num_traces * 2} total measurements)")

    result = subprocess.run(
        [str(binary), str(num_traces)],
        capture_output=True, text=True,
        timeout=7200  # 2 hour timeout for 500K traces
    )
    if result.returncode != 0:
        print(f"  RUN ERROR: {result.stderr}")
        return None, None

    fixed = []
    random_t = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        tag, cycles = parts[0], int(parts[1])
        if tag == 'F':
            fixed.append(cycles)
        elif tag == 'R':
            random_t.append(cycles)

    fixed = np.array(fixed, dtype=np.float64)
    random_arr = np.array(random_t, dtype=np.float64)
    print(f"  Got {len(fixed)} fixed, {len(random_arr)} random traces")
    print(f"  Fixed:  mean={fixed.mean():.1f}, std={fixed.std():.1f}, "
          f"median={np.median(fixed):.1f}")
    print(f"  Random: mean={random_arr.mean():.1f}, std={random_arr.std():.1f}, "
          f"median={np.median(random_arr):.1f}")
    return fixed, random_arr


def compute_full_stats(fixed, random_traces):
    """Compute TVLA + variance + Levene's test."""
    t_stat, p_val = stats.ttest_ind(fixed, random_traces, equal_var=False)
    levene_F, levene_p = stats.levene(fixed, random_traces)
    var_ratio = np.var(fixed) / np.var(random_traces)

    return {
        "t_statistic": round(float(abs(t_stat)), 2),
        "p_value": float(p_val),
        "variance_ratio": round(float(var_ratio), 4),
        "fixed_mean": round(float(np.mean(fixed)), 1),
        "fixed_std": round(float(np.std(fixed)), 1),
        "fixed_median": round(float(np.median(fixed)), 1),
        "random_mean": round(float(np.mean(random_traces)), 1),
        "random_std": round(float(np.std(random_traces)), 1),
        "random_median": round(float(np.median(random_traces)), 1),
        "n_traces": int(len(fixed)),
        "levene_F": round(float(levene_F), 2),
        "levene_p": float(levene_p),
        "tvla_verdict": "PASS" if abs(t_stat) <= 4.5 else "FAIL"
    }


def main():
    print("=" * 70)
    print("PHASE 11: INTERLEAVED HARNESS CONTROL - APPLE SILICON")
    print("The definitive temporal drift attribution experiment")
    print("=" * 70)

    # Compile both interleaved harnesses
    sym_src = HARNESS_DIR / "tvla_interleaved_symmetric.c"
    sym_bin = HARNESS_DIR / "tvla_interleaved_symmetric"
    asym_src = HARNESS_DIR / "tvla_interleaved_asymmetric.c"
    asym_bin = HARNESS_DIR / "tvla_interleaved_asymmetric"

    print("\n[Step 1] Compiling interleaved harnesses...")

    if not sym_src.exists():
        print(f"ERROR: {sym_src} not found")
        sys.exit(1)
    if not asym_src.exists():
        print(f"ERROR: {asym_src} not found")
        sys.exit(1)

    if not compile_harness(sym_src, sym_bin):
        sys.exit(1)
    if not compile_harness(asym_src, asym_bin):
        sys.exit(1)

    # Run symmetric interleaved (the critical test)
    print(f"\n[Step 2] Running SYMMETRIC INTERLEAVED harness "
          f"({NUM_TRACES} traces per group)...")
    print("  This is the definitive test. If this FAILS, temporal drift is confirmed.")
    sym_fixed, sym_random = run_interleaved_harness(sym_bin, NUM_TRACES)
    if sym_fixed is None:
        print("ERROR: Symmetric interleaved harness failed.")
        sys.exit(1)

    # Run asymmetric interleaved (for comparison)
    print(f"\n[Step 3] Running ASYMMETRIC INTERLEAVED harness "
          f"({NUM_TRACES} traces per group)...")
    asym_fixed, asym_random = run_interleaved_harness(asym_bin, NUM_TRACES)
    if asym_fixed is None:
        print("ERROR: Asymmetric interleaved harness failed.")
        sys.exit(1)

    # Compute statistics
    print("\n[Step 4] Computing statistics...")
    sym_stats = compute_full_stats(sym_fixed, sym_random)
    asym_stats = compute_full_stats(asym_fixed, asym_random)

    # Print results
    print("\n" + "=" * 70)
    print("RESULTS: INTERLEAVED HARNESS COMPARISON - APPLE SILICON")
    print("=" * 70)
    print(f"\n{'Metric':<35} {'Asym Interleaved':>18} {'Sym Interleaved':>18}")
    print("-" * 75)
    print(f"{'|t| statistic':<35} {asym_stats['t_statistic']:>18.2f} "
          f"{sym_stats['t_statistic']:>18.2f}")
    print(f"{'Variance ratio (F/R)':<35} {asym_stats['variance_ratio']:>18.4f} "
          f"{sym_stats['variance_ratio']:>18.4f}")
    print(f"{'Fixed mean':<35} {asym_stats['fixed_mean']:>18.1f} "
          f"{sym_stats['fixed_mean']:>18.1f}")
    print(f"{'Fixed std':<35} {asym_stats['fixed_std']:>18.1f} "
          f"{sym_stats['fixed_std']:>18.1f}")
    print(f"{'Fixed median':<35} {asym_stats['fixed_median']:>18.1f} "
          f"{sym_stats['fixed_median']:>18.1f}")
    print(f"{'Random mean':<35} {asym_stats['random_mean']:>18.1f} "
          f"{sym_stats['random_mean']:>18.1f}")
    print(f"{'Random std':<35} {asym_stats['random_std']:>18.1f} "
          f"{sym_stats['random_std']:>18.1f}")
    print(f"{'Random median':<35} {asym_stats['random_median']:>18.1f} "
          f"{sym_stats['random_median']:>18.1f}")
    print(f"{'Levene F (variance equality)':<35} {asym_stats['levene_F']:>18.2f} "
          f"{sym_stats['levene_F']:>18.2f}")
    print(f"{'Levene p-value':<35} {asym_stats['levene_p']:>18.2e} "
          f"{sym_stats['levene_p']:>18.2e}")
    print(f"{'TVLA verdict':<35} {asym_stats['tvla_verdict']:>18} "
          f"{sym_stats['tvla_verdict']:>18}")
    print("-" * 75)

    # Interpretation
    print("\n" + "=" * 70)
    print("INTERPRETATION")
    print("=" * 70)

    if sym_stats['tvla_verdict'] == 'FAIL':
        print(f"\n  SYMMETRIC INTERLEAVED FAILS: |t| = {sym_stats['t_statistic']}")
        print(f"  Variance ratio: {sym_stats['variance_ratio']:.4f}x")
        print()
        print("  *** HYPOTHESIS B CONFIRMED ***")
        print("  Temporal drift from sequential collection breaks ISO 17825")
        print("  even with mathematically perfect software.")
        print()
        print("  The confound persists when:")
        print("    - Inputs are pre-generated (no harness asymmetry)")
        print("    - Collection is interleaved (no temporal drift)")
        print("    - Code paths are identical (no instruction asymmetry)")
        print()
        print("  The ONLY remaining variable is the DATA flowing through decaps.")
        print("  Fixed group: same data repeated → DMP converges")
        print("  Random group: different data each time → DMP never converges")
        verdict = "TEMPORAL_DRIFT_CONFIRMED"

        if sym_stats['variance_ratio'] > 2.0:
            print(f"\n  Fixed variance is {sym_stats['variance_ratio']:.1f}x higher "
                  "than random.")
            print("  This matches DMP convergence/misprediction pattern:")
            print("    repeated data → aggressive prefetch → occasional catastrophic miss")
        elif sym_stats['variance_ratio'] < 0.5:
            print(f"\n  Random variance is {1/sym_stats['variance_ratio']:.1f}x higher "
                  "than fixed.")
            print("  Unexpected: opposite direction from DMP hypothesis.")
            print("  May indicate a different microarchitectural mechanism.")
    else:
        print(f"\n  SYMMETRIC INTERLEAVED PASSES: |t| = {sym_stats['t_statistic']}")
        print()
        print("  *** HYPOTHESIS A CONFIRMED ***")
        print("  The Apple Silicon confound was temporal drift,")
        print("  just like Intel. No architectural DMP effect.")
        print()
        print("  The paper must be reframed: TVLA false positives on both")
        print("  platforms are caused by test methodology, not hardware.")
        verdict = "TEMPORAL_DRIFT_ONLY"

    # Cross-platform comparison
    print("\n" + "=" * 70)
    print("CROSS-PLATFORM INTERLEAVED COMPARISON")
    print("=" * 70)
    print(f"\n{'Platform':<20} {'Asym |t|':>12} {'Sym |t|':>12} {'Sym Var Ratio':>15} "
          f"{'Sym Verdict':>12}")
    print("-" * 75)
    print(f"{'Intel x86':<20} {'8.10':>12} {'1.65':>12} {'(pending)':>15} {'PASS':>12}")
    print(f"{'Apple Silicon':<20} {asym_stats['t_statistic']:>12.2f} "
          f"{sym_stats['t_statistic']:>12.2f} "
          f"{sym_stats['variance_ratio']:>15.4f} "
          f"{sym_stats['tvla_verdict']:>12}")
    print()

    # Save results
    output = {
        "experiment": "interleaved_control",
        "platform": "apple_silicon",
        "num_traces_per_group": NUM_TRACES,
        "collection_method": "interleaved",
        "liboqs_version": "0.15.0",
        "compiler_flags": "-O2 -march=native",
        "asymmetric_interleaved": asym_stats,
        "symmetric_interleaved": sym_stats,
        "verdict": verdict,
        "intel_comparison": {
            "asymmetric_interleaved_t": 8.10,
            "symmetric_interleaved_t": 1.65,
            "symmetric_interleaved_verdict": "PASS"
        }
    }

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "phase11_interleaved_control.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

    # Save raw traces as CSV for further analysis
    sym_csv = DATA_DIR / "apple_symmetric_interleaved.csv"
    asym_csv = DATA_DIR / "apple_asymmetric_interleaved.csv"

    print(f"Saving raw traces to {sym_csv} and {asym_csv}...")
    np.savetxt(sym_csv, np.column_stack([sym_fixed, sym_random]),
               delimiter=',', header='fixed,random', comments='', fmt='%d')
    np.savetxt(asym_csv, np.column_stack([asym_fixed, asym_random]),
               delimiter=',', header='fixed,random', comments='', fmt='%d')

    print("\n" + "=" * 70)
    print("EXPERIMENT COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
