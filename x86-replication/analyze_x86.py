#!/usr/bin/env python3
import numpy as np
from scipy import stats
import platform
import json

print("=" * 70)
print("  x86-64 TVLA CONTROL EXPERIMENT - RESULTS")
print("=" * 70)

# System info
print(f"\n  Platform:     {platform.platform()}")
print(f"  Processor:    {platform.processor()}")
print(f"  Architecture: {platform.machine()}")
try:
    with open("/proc/cpuinfo") as f:
        for line in f:
            if "model name" in line:
                print(f"  CPU:          {line.split(':')[1].strip()}")
                break
except:
    pass

# Load traces
fixed = np.loadtxt("fixed_traces.txt", dtype=np.int64)
random = np.loadtxt("random_traces.txt", dtype=np.int64)
print(f"\n  Fixed traces:  {len(fixed):,}")
print(f"  Random traces: {len(random):,}")

# Basic stats
print(f"\n  --- Fixed Distribution ---")
print(f"  Mean:   {np.mean(fixed):.1f}")
print(f"  Median: {np.median(fixed):.1f}")
print(f"  Std:    {np.std(fixed):.1f}")
print(f"  Min:    {np.min(fixed)}")
print(f"  Max:    {np.max(fixed)}")

print(f"\n  --- Random Distribution ---")
print(f"  Mean:   {np.mean(random):.1f}")
print(f"  Median: {np.median(random):.1f}")
print(f"  Std:    {np.std(random):.1f}")
print(f"  Min:    {np.min(random)}")
print(f"  Max:    {np.max(random)}")

# Welch's t-test
t_stat, p_value = stats.ttest_ind(fixed, random, equal_var=False)
variance_ratio = float(np.std(fixed) / np.std(random))

print(f"\n  --- TVLA Result ---")
print(f"  Welch's t-statistic: {t_stat:.6f}")
print(f"  |t|:                 {abs(t_stat):.6f}")
print(f"  p-value:             {p_value:.2e}")
print(f"  Variance ratio:      {variance_ratio:.4f}x")

if abs(t_stat) > 4.5:
    print(f"  RESULT: *** LEAKAGE DETECTED ON x86 ***")
else:
    print(f"  RESULT: NO LEAKAGE ON x86")

# Progressive analysis
print(f"\n  --- Progressive Analysis ---")
print(f"  {'Traces':>10} {'|t|':>12} {'Leak?':>8}")
for n in [25000, 50000, 100000, 150000, 200000, 300000, 500000]:
    if n <= min(len(fixed), len(random)):
        t, p = stats.ttest_ind(fixed[:n], random[:n], equal_var=False)
        leak = "YES" if abs(t) > 4.5 else "no"
        print(f"  {n:>10,} {abs(t):>12.4f} {leak:>8}")

# Quantile-filtered TVLA
print(f"\n  --- Quantile-Filtered TVLA ---")
for pct_label, pct in [("10%", 0.10), ("25%", 0.25), ("50%", 0.50)]:
    combined = np.concatenate([fixed, random])
    thresh = np.percentile(combined, pct * 100)
    f_filt = fixed[fixed <= thresh]
    r_filt = random[random <= thresh]
    if len(f_filt) > 100 and len(r_filt) > 100:
        t_f, _ = stats.ttest_ind(f_filt, r_filt, equal_var=False)
        vr = np.std(f_filt) / max(np.std(r_filt), 1)
        print(f"  Bottom {pct_label}: n_f={len(f_filt):,}, n_r={len(r_filt):,}, |t|={abs(t_f):.4f}, var_ratio={vr:.2f}")

# Comparison with Apple Silicon
apple_t = 8.4247
apple_var_ratio = 10.0
print(f"\n  --- APPLE SILICON vs x86 COMPARISON ---")
print(f"  {'Metric':<35} {'Apple M-series':>15} {'x86-64':>15}")
print(f"  {'-'*65}")
print(f"  {'|t| statistic':<35} {apple_t:>15.4f} {abs(t_stat):>15.4f}")
print(f"  {'Variance ratio (fixed/random)':<35} {apple_var_ratio:>15.2f} {variance_ratio:>15.4f}")
print(f"  {'Leakage detected?':<35} {'YES':>15} {'YES' if abs(t_stat) > 4.5 else 'NO':>15}")
print(f"  {'Fixed mean (cycles)':<35} {'534.6':>15} {np.mean(fixed):>15.1f}")
print(f"  {'Random mean (cycles)':<35} {'520.0':>15} {np.mean(random):>15.1f}")
print(f"  {'Fixed std (cycles)':<35} {'1216.3':>15} {np.std(fixed):>15.1f}")
print(f"  {'Random std (cycles)':<35} {'121.6':>15} {np.std(random):>15.1f}")

# Verdict
print(f"\n  {'='*65}")
if abs(t_stat) < 4.5:
    print(f"  VERDICT: APPLE-SPECIFIC ARTIFACT CONFIRMED")
    print(f"  The |t|=8.42 TVLA false positive does NOT reproduce on x86.")
    print(f"  The variance asymmetry is caused by Apple Silicon's")
    print(f"  microarchitecture (DMP/speculative execution), not by liboqs.")
    verdict = "APPLE_ARTIFACT_CONFIRMED"
else:
    print(f"  VERDICT: EFFECT PERSISTS ON x86")
    print(f"  The TVLA anomaly is NOT Apple-specific.")
    print(f"  It may be an algorithmic property of liboqs or the C runtime.")
    verdict = "PERSISTS_ON_X86"
print(f"  {'='*65}")

# Save to JSON
results = {
    "platform": platform.platform(),
    "processor": platform.processor(),
    "architecture": platform.machine(),
    "n_fixed": int(len(fixed)),
    "n_random": int(len(random)),
    "fixed_mean": float(np.mean(fixed)),
    "fixed_std": float(np.std(fixed)),
    "fixed_median": float(np.median(fixed)),
    "random_mean": float(np.mean(random)),
    "random_std": float(np.std(random)),
    "random_median": float(np.median(random)),
    "t_statistic": float(t_stat),
    "abs_t": float(abs(t_stat)),
    "p_value": float(p_value),
    "variance_ratio": float(variance_ratio),
    "leakage_detected": bool(abs(t_stat) > 4.5),
    "verdict": verdict,
    "apple_t": apple_t,
    "apple_variance_ratio": apple_var_ratio,
}
with open("tvla_x86_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\n  Results saved to tvla_x86_results.json")

# ============================================================
# THIS IS THE COPY-PASTE BLOCK
# ============================================================
print("\n\n")
print("=" * 70)
print("COPY-PASTE BLOCK START (copy everything between the START and END lines)")
print("=" * 70)
print(f"PLATFORM: {platform.platform()}")
try:
    with open("/proc/cpuinfo") as f:
        for line in f:
            if "model name" in line:
                print(f"CPU: {line.split(':')[1].strip()}")
                break
except:
    pass
print(f"TRACES: {len(fixed)} fixed, {len(random)} random")
print(f"FIXED: mean={np.mean(fixed):.1f}, median={np.median(fixed):.1f}, std={np.std(fixed):.1f}")
print(f"RANDOM: mean={np.mean(random):.1f}, median={np.median(random):.1f}, std={np.std(random):.1f}")
print(f"WELCH_T: {t_stat:.6f}")
print(f"ABS_T: {abs(t_stat):.6f}")
print(f"P_VALUE: {p_value:.2e}")
print(f"VARIANCE_RATIO: {variance_ratio:.4f}")
print(f"LEAKAGE_DETECTED: {'YES' if abs(t_stat) > 4.5 else 'NO'}")
print(f"PROGRESSIVE: ", end="")
prog_parts = []
for n in [25000, 50000, 100000, 200000, 500000]:
    if n <= min(len(fixed), len(random)):
        t, _ = stats.ttest_ind(fixed[:n], random[:n], equal_var=False)
        prog_parts.append(f"{n}={abs(t):.4f}")
print(", ".join(prog_parts))
print(f"VERDICT: {verdict}")
print("=" * 70)
print("COPY-PASTE BLOCK END")
print("=" * 70)
