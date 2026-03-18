#!/usr/bin/env python3
"""
phase10_compiler_flags.py

Tests whether the TVLA false positive persists across compiler optimization
levels (-O0, -O1, -O2, -O3, -Os) using the symmetric harness on Apple Silicon.

Uses 20K traces per mode — the symmetric confound is so large (|t|≈62 at 50K)
that 20K is more than sufficient for statistical clarity while saving ~60% runtime.
"""

import subprocess
import sys
import os
import tempfile
import numpy as np
from scipy import stats
from pathlib import Path

HARNESS_SRC = Path(__file__).parent.parent / "harnesses" / "tvla_harness_symmetric.c"
LIBOQS_PREFIX = os.environ.get("LIBOQS_PREFIX", "/opt/homebrew")
NUM_TRACES = 50000
FLAGS = ["-O0", "-O1", "-O2", "-O3", "-Os"]

def compile_harness(flag, binary_path):
    cmd = [
        "gcc", flag, "-march=native",
        f"-I{LIBOQS_PREFIX}/include",
        f"-L{LIBOQS_PREFIX}/lib",
        "-o", str(binary_path),
        str(HARNESS_SRC),
        "-loqs", "-lssl", "-lcrypto", "-lm"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  COMPILE FAILED ({flag}): {r.stderr}", file=sys.stderr)
        return False
    return True

def run_harness(binary, mode):
    r = subprocess.run(
        [str(binary), mode, str(NUM_TRACES)],
        capture_output=True, text=True, timeout=600
    )
    if r.returncode != 0:
        return None
    lines = r.stdout.strip().split('\n')
    return np.array([int(x) for x in lines if x.strip()], dtype=np.float64)

# Compile all binaries first
print("Compiling symmetric harness at 5 optimization levels...", file=sys.stderr)
binaries = {}
with tempfile.TemporaryDirectory() as tmpdir:
    for flag in FLAGS:
        bpath = Path(tmpdir) / f"harness_{flag.replace('-', '')}"
        if compile_harness(flag, bpath):
            binaries[flag] = bpath
            print(f"  {flag} OK", file=sys.stderr)
        else:
            print(f"  {flag} FAILED — skipping", file=sys.stderr)

    if not binaries:
        print("No binaries compiled. Check liboqs install.", file=sys.stderr)
        sys.exit(1)

    # Run all experiments
    results = {}
    total = len(binaries)
    for i, (flag, bpath) in enumerate(binaries.items(), 1):
        print(f"\n[{i}/{total}] Running {flag} ({NUM_TRACES} traces per mode)...", file=sys.stderr)
        fixed = run_harness(bpath, "fixed")
        random = run_harness(bpath, "random")
        if fixed is None or random is None:
            print(f"  {flag} run failed — skipping", file=sys.stderr)
            continue
        t, p = stats.ttest_ind(fixed, random, equal_var=False)
        vr = np.var(fixed) / np.var(random)
        results[flag] = {
            "t": abs(t), "vr": vr, "passes": abs(t) <= 4.5,
            "fixed_mean": np.mean(fixed), "random_mean": np.mean(random),
            "fixed_std": np.std(fixed), "random_std": np.std(random),
        }
        print(f"  {flag}: |t|={abs(t):.2f}, var_ratio={vr:.2f}x, {'PASS' if abs(t)<=4.5 else 'FAIL'}", file=sys.stderr)

# Output
print("\n")
print("=" * 70)
print("COPY-PASTE RESULTS START HERE")
print("=" * 70)

print(f"""
COMPILER FLAG EXPERIMENT — Apple Silicon Symmetric Harness
==========================================================
Platform: Apple Silicon M-series (CNTVCT_EL0)
Harness: Symmetric (pre-generated inputs, identical code paths)
liboqs: v0.15.0
Traces per mode: {NUM_TRACES}
""")

print("| Flag | |t| | Var Ratio | Fixed Mean | Random Mean | TVLA |")
print("|------|-----|-----------|------------|-------------|------|")
for flag in FLAGS:
    if flag in results:
        r = results[flag]
        print(f"| {flag} | {r['t']:.2f} | {r['vr']:.2f}x | {r['fixed_mean']:.1f} | {r['random_mean']:.1f} | **{'PASS' if r['passes'] else 'FAIL'}** |")
    else:
        print(f"| {flag} | — | — | — | — | COMPILE FAILED |")

all_fail = all(not r["passes"] for r in results.values())
print(f"""
VERDICT: {'CONFOUND PERSISTS ACROSS ALL FLAGS' if all_fail else 'FLAG-DEPENDENT — SEE TABLE'}
{'The architectural confound is independent of compiler optimization level.' if all_fail else 'Some flags alter the confound magnitude — investigate.'}
""")

print("=" * 70)
print("COPY-PASTE RESULTS END HERE")
print("=" * 70)
