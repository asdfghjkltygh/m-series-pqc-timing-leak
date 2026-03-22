#!/usr/bin/env python3
"""
phase9_symmetric_harness_control.py

Symmetric harness control experiment: isolates the temporal drift confound
(DMP hypothesis disproved by interleaved control) from the harness-induced
cache pollution confound.

Compiles and runs tvla_harness_symmetric.c, which pre-generates all random
(ct, sk) pairs into memory arrays before measurement. Both fixed and random
modes execute identical code paths during the timed loop.

If the TVLA failure (|t| > 4.5) persists → the cause is temporal drift.
If it vanishes → the cause was harness asymmetry (keygen+encaps cache pollution).

Also runs the original asymmetric harness for direct comparison.

Requires: liboqs v0.15.0 installed at /usr/local (or adjust LIBOQS_PREFIX).
Must be run on Apple Silicon.
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
NUM_TRACES = 50000  # 50K per mode = 100K total per harness

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

def run_harness(binary, mode, num_traces):
    """Run a harness and return timing traces as numpy array."""
    print(f"  Running {binary.name} [{mode}] x {num_traces}...")
    result = subprocess.run(
        [str(binary), mode, str(num_traces)],
        capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0:
        print(f"  RUN ERROR: {result.stderr}")
        return None
    lines = result.stdout.strip().split('\n')
    traces = np.array([int(x) for x in lines if x.strip()], dtype=np.float64)
    print(f"  Got {len(traces)} traces. Mean={traces.mean():.1f}, Std={traces.std():.1f}")
    return traces

def compute_tvla(fixed, random):
    """Compute Welch's t-test and variance ratio."""
    t_stat, p_val = stats.ttest_ind(fixed, random, equal_var=False)
    var_ratio = np.var(fixed) / np.var(random)
    return {
        "t_statistic": float(abs(t_stat)),
        "p_value": float(p_val),
        "variance_ratio_fixed_over_random": float(var_ratio),
        "fixed_mean": float(np.mean(fixed)),
        "fixed_std": float(np.std(fixed)),
        "random_mean": float(np.mean(random)),
        "random_std": float(np.std(random)),
        "fixed_n": len(fixed),
        "random_n": len(random),
        "passes_tvla": bool(abs(t_stat) <= 4.5)
    }

def main():
    print("=" * 70)
    print("SYMMETRIC HARNESS CONTROL EXPERIMENT")
    print("Isolating temporal drift confound from harness cache pollution")
    print("=" * 70)

    # Compile both harnesses
    sym_src = HARNESS_DIR / "tvla_harness_symmetric.c"
    sym_bin = HARNESS_DIR / "tvla_harness_symmetric"
    asym_src = HARNESS_DIR / "tvla_harness.c"
    asym_bin = HARNESS_DIR / "tvla_harness"

    if not sym_src.exists():
        print(f"ERROR: {sym_src} not found")
        sys.exit(1)

    print("\n[Step 1] Compiling harnesses...")
    if not compile_harness(sym_src, sym_bin):
        print("Failed to compile symmetric harness. Is liboqs installed?")
        sys.exit(1)

    # Only compile asymmetric if binary doesn't exist
    if not asym_bin.exists():
        if not compile_harness(asym_src, asym_bin):
            print("Failed to compile asymmetric harness.")
            sys.exit(1)

    # Run symmetric harness
    print(f"\n[Step 2] Running SYMMETRIC harness ({NUM_TRACES} traces per mode)...")
    sym_fixed = run_harness(sym_bin, "fixed", NUM_TRACES)
    sym_random = run_harness(sym_bin, "random", NUM_TRACES)

    if sym_fixed is None or sym_random is None:
        print("ERROR: Symmetric harness failed to produce traces.")
        sys.exit(1)

    # Run asymmetric harness for comparison
    print(f"\n[Step 3] Running ASYMMETRIC harness ({NUM_TRACES} traces per mode)...")
    asym_fixed = run_harness(asym_bin, "fixed", NUM_TRACES)
    asym_random = run_harness(asym_bin, "random", NUM_TRACES)

    if asym_fixed is None or asym_random is None:
        print("ERROR: Asymmetric harness failed to produce traces.")
        sys.exit(1)

    # Compute TVLA for both
    print("\n[Step 4] Computing TVLA statistics...")
    sym_result = compute_tvla(sym_fixed, sym_random)
    asym_result = compute_tvla(asym_fixed, asym_random)

    # Print comparison table
    print("\n" + "=" * 70)
    print("RESULTS: SYMMETRIC vs ASYMMETRIC HARNESS")
    print("=" * 70)
    print(f"{'Metric':<35} {'Asymmetric':>15} {'Symmetric':>15}")
    print("-" * 70)
    print(f"{'|t| statistic':<35} {asym_result['t_statistic']:>15.2f} {sym_result['t_statistic']:>15.2f}")
    print(f"{'p-value':<35} {asym_result['p_value']:>15.2e} {sym_result['p_value']:>15.2e}")
    print(f"{'Variance ratio (fixed/random)':<35} {asym_result['variance_ratio_fixed_over_random']:>15.2f} {sym_result['variance_ratio_fixed_over_random']:>15.2f}")
    print(f"{'Fixed mean':<35} {asym_result['fixed_mean']:>15.1f} {sym_result['fixed_mean']:>15.1f}")
    print(f"{'Fixed std':<35} {asym_result['fixed_std']:>15.1f} {sym_result['fixed_std']:>15.1f}")
    print(f"{'Random mean':<35} {asym_result['random_mean']:>15.1f} {sym_result['random_mean']:>15.1f}")
    print(f"{'Random std':<35} {asym_result['random_std']:>15.1f} {sym_result['random_std']:>15.1f}")
    print(f"{'TVLA pass (|t| <= 4.5)?':<35} {'PASS' if asym_result['passes_tvla'] else 'FAIL':>15} {'PASS' if sym_result['passes_tvla'] else 'FAIL':>15}")
    print("-" * 70)

    # Interpretation
    print("\n[INTERPRETATION]")
    if not sym_result['passes_tvla']:
        print(f"  SYMMETRIC HARNESS STILL FAILS TVLA: |t| = {sym_result['t_statistic']:.2f}")
        print(f"  Variance ratio: {sym_result['variance_ratio_fixed_over_random']:.2f}")
        print("  → The TVLA false positive is caused by TEMPORAL DRIFT")
        print("    (disproved DMP via interleaved control),")
        print("    NOT caused by harness-induced cache pollution.")
        verdict = "TEMPORAL_DRIFT_CONFIRMED"
    else:
        print(f"  SYMMETRIC HARNESS PASSES TVLA: |t| = {sym_result['t_statistic']:.2f}")
        print("  → The TVLA false positive was caused by HARNESS ASYMMETRY,")
        print("    NOT by temporal drift.")
        print("  → The paper must be reframed as a software engineering critique.")
        verdict = "HARNESS_ASYMMETRY_ONLY"

    # Save results
    output = {
        "experiment": "symmetric_harness_control",
        "platform": "apple_silicon",
        "num_traces_per_mode": NUM_TRACES,
        "liboqs_version": "0.15.0",
        "compiler_flags": "-O2 -march=native",
        "asymmetric_harness": asym_result,
        "symmetric_harness": sym_result,
        "verdict": verdict,
        "interpretation": (
            "The symmetric harness eliminates keygen+encaps cache pollution from "
            "the measurement loop. If TVLA still fails, the cause is temporal drift "
            "from sequential collection. If TVLA passes, the original false positive "
            "was entirely due to harness asymmetry."
        )
    }

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "phase9_symmetric_control.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")

if __name__ == "__main__":
    main()
