#!/usr/bin/env python3
"""
Intel x86 Symmetric Harness Control Experiment.

Runs both symmetric and asymmetric TVLA harnesses on Intel x86,
computes TVLA statistics, and outputs results formatted for
copy-paste into the whitepaper.
"""

import subprocess
import sys
import os
import numpy as np
from scipy import stats

NUM_TRACES = 50000  # 50K per mode

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
X86_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "x86-replication")
LIBOQS_LIB = os.path.join(X86_DIR, "liboqs-install", "lib")

# Set library path for liboqs
os.environ['LD_LIBRARY_PATH'] = LIBOQS_LIB + ':' + os.environ.get('LD_LIBRARY_PATH', '')

def run_harness(binary, mode, num_traces):
    print(f"  Running {binary} [{mode}] x {num_traces}...", file=sys.stderr)
    result = subprocess.run(
        [os.path.join(X86_DIR, binary), mode, str(num_traces)],
        capture_output=True, text=True, timeout=1200,
        cwd=X86_DIR,
        env={**os.environ, 'LD_LIBRARY_PATH': LIBOQS_LIB}
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}", file=sys.stderr)
        return None
    lines = result.stdout.strip().split('\n')
    traces = np.array([int(x) for x in lines if x.strip()], dtype=np.float64)
    print(f"  Got {len(traces)} traces. Mean={traces.mean():.1f}, Std={traces.std():.1f}", file=sys.stderr)
    return traces

def compute_tvla(fixed, random_traces):
    t_stat, p_val = stats.ttest_ind(fixed, random_traces, equal_var=False)
    var_ratio = np.var(fixed) / np.var(random_traces)
    return {
        "t_stat": abs(t_stat),
        "p_value": p_val,
        "var_ratio": var_ratio,
        "fixed_mean": np.mean(fixed),
        "fixed_std": np.std(fixed),
        "random_mean": np.mean(random_traces),
        "random_std": np.std(random_traces),
        "passes": abs(t_stat) <= 4.5
    }

print("=" * 70)
print("INTEL x86 SYMMETRIC HARNESS CONTROL EXPERIMENT")
print("=" * 70)

# --- Run Symmetric Harness ---
print("\n[1/4] Running SYMMETRIC harness (fixed)...")
sym_fixed = run_harness("tvla_harness_symmetric_x86", "fixed", NUM_TRACES)
print("[2/4] Running SYMMETRIC harness (random)...")
sym_random = run_harness("tvla_harness_symmetric_x86", "random", NUM_TRACES)

# --- Run Asymmetric Harness ---
print("[3/4] Running ASYMMETRIC harness (fixed)...")
asym_fixed = run_harness("tvla_harness_x86", "fixed", NUM_TRACES)
print("[4/4] Running ASYMMETRIC harness (random)...")
asym_random = run_harness("tvla_harness_x86", "random", NUM_TRACES)

if any(x is None for x in [sym_fixed, sym_random, asym_fixed, asym_random]):
    print("ERROR: One or more harness runs failed.")
    sys.exit(1)

sym = compute_tvla(sym_fixed, sym_random)
asym = compute_tvla(asym_fixed, asym_random)

# ============================================================
# OUTPUT — COPY EVERYTHING BELOW THIS LINE
# ============================================================
print("\n")
print("=" * 70)
print("COPY-PASTE RESULTS START HERE")
print("=" * 70)

print(f"""
INTEL x86 SYMMETRIC CONTROL RESULTS
====================================
Platform: Intel x86 (RDTSC + CPUID serialization)
liboqs: v0.15.0
Compiler: gcc -O2 -march=native
Traces per mode: {NUM_TRACES}

ASYMMETRIC HARNESS (original — keygen+encaps in random mode):
  |t| statistic:     {asym['t_stat']:.2f}
  Variance ratio:    {asym['var_ratio']:.2f}x (fixed/random)
  Fixed mean:        {asym['fixed_mean']:.1f} cycles
  Fixed std:         {asym['fixed_std']:.1f}
  Random mean:       {asym['random_mean']:.1f} cycles
  Random std:        {asym['random_std']:.1f}
  TVLA verdict:      {'PASS' if asym['passes'] else 'FAIL'}

SYMMETRIC HARNESS (pre-generated inputs, identical code paths):
  |t| statistic:     {sym['t_stat']:.2f}
  Variance ratio:    {sym['var_ratio']:.2f}x (fixed/random)
  Fixed mean:        {sym['fixed_mean']:.1f} cycles
  Fixed std:         {sym['fixed_std']:.1f}
  Random mean:       {sym['random_mean']:.1f} cycles
  Random std:        {sym['random_std']:.1f}
  TVLA verdict:      {'PASS' if sym['passes'] else 'FAIL'}
""")

# Determine verdict
if not sym['passes'] and not asym['passes']:
    verdict = "BOTH_FAIL"
    interpretation = "Both harnesses fail TVLA. The Intel confound is TEMPORAL DRIFT — harness asymmetry is not the sole cause."
elif sym['passes'] and not asym['passes']:
    verdict = "HARNESS_ASYMMETRY_ONLY"
    interpretation = "Symmetric harness passes, asymmetric fails. The Intel confound is HARNESS-INDUCED — eliminating keygen+encaps cache pollution resolves the false positive."
elif not sym['passes'] and asym['passes']:
    verdict = "ARCHITECTURAL_UNMASKED"
    interpretation = "Symmetric fails, asymmetric passes. Same pattern as Apple Silicon — harness asymmetry was MASKING the temporal drift confound."
else:
    verdict = "BOTH_PASS"
    interpretation = "Both harnesses pass TVLA. No confound detected on this hardware."

print(f"VERDICT: {verdict}")
print(f"INTERPRETATION: {interpretation}")

# Print the markdown table for the whitepaper
print(f"""
WHITEPAPER TABLE (markdown):

| Harness | |t| | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|----------------|--------------------|--------------------|-------------|
| Asymmetric | {asym['t_stat']:.2f} | {asym['var_ratio']:.2f}x | {asym['fixed_mean']:.1f} | {asym['random_mean']:.1f} | **{'PASS' if asym['passes'] else 'FAIL'}** |
| Symmetric | {sym['t_stat']:.2f} | {sym['var_ratio']:.2f}x | {sym['fixed_mean']:.1f} | {sym['random_mean']:.1f} | **{'PASS' if sym['passes'] else 'FAIL'}** |
""")

# Cross-platform comparison (include Apple results for context)
print(f"""CROSS-PLATFORM COMPARISON TABLE (include Apple Silicon results from prior experiment):

Apple Silicon (already confirmed):
  Asymmetric: |t|=3.00,  var_ratio=0.16x, PASS
  Symmetric:  |t|=62.49, var_ratio=7.71x, FAIL
  Verdict: TEMPORAL_DRIFT_CONFIRMED (asymmetric was masking temporal drift)

Intel x86 (THIS EXPERIMENT):
  Asymmetric: |t|={asym['t_stat']:.2f}, var_ratio={asym['var_ratio']:.2f}x, {'PASS' if asym['passes'] else 'FAIL'}
  Symmetric:  |t|={sym['t_stat']:.2f}, var_ratio={sym['var_ratio']:.2f}x, {'PASS' if sym['passes'] else 'FAIL'}
  Verdict: {verdict}
""")

print("=" * 70)
print("COPY-PASTE RESULTS END HERE")
print("=" * 70)
