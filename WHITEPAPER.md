---
title: "When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment"
subtitle: "Black Hat Briefings: Technical White Paper"
author: "Saahil Shenoy | Founding AI Scientist, Bedrock Data | saahil@bedrockdata.ai"
date: "March 2026"
---

## Abstract

The mandatory side-channel evaluation for FIPS 140-3 certification, ISO 17825 TVLA (Test Vector Leakage Assessment), produces catastrophic false positives when applied to ML-KEM on modern general-purpose processors. We demonstrate that sequential data collection, the protocol implicitly prescribed by the standard, introduces temporal drift that TVLA misinterprets as cryptographic leakage. In a 2x2 experimental design spanning Apple Silicon and Intel x86 with 12.2 million traces and over 150 independent experiments, switching from sequential to interleaved collection reduces Apple Silicon's $\tval$ from 62.49 to 0.58, a two-order-of-magnitude drop in statistical significance, with no change to hardware, software, or inputs. Every attack technique applied to the sequential data, including ML classifiers, template attacks, and information-theoretic bounds, returns zero exploitable bits of secret information. We release sca-triage, an open-source triage tool that distinguishes real leakage from false positives using pairwise secret-group decomposition and permutation-validated mutual information. ML-KEM deployment should not be delayed based on TVLA-only evaluations.

---

## 1. The Problem

The mandatory government test for certifying cryptographic implementations, FIPS 140-3 (the US government's cryptographic module certification standard), includes a timing side-channel evaluation called TVLA (Test Vector Leakage Assessment). When we run this test on the new post-quantum encryption standard, ML-KEM, it produces catastrophic false positives.

Sequential collection: $\tval$ = 62.49 (FAIL). Interleaved collection: $\tval$ = 0.58 (PASS). Same hardware, same code, same inputs. The FIPS side-channel test for post-quantum cryptography (PQC) is broken.

TVLA is the mandatory side-channel evaluation for ISO 17825 / FIPS 140-3 certification. It collects two groups of timing measurements, "fixed" (one repeated input) and "random" (different inputs each time), then runs Welch's t-test to check whether the groups differ. If the test statistic $\tval$ exceeds 4.5, the implementation fails.

When we run TVLA on liboqs ML-KEM-768, the most widely integrated open-source implementation of the NIST post-quantum key exchange standard, it reports catastrophic leakage: $\tval$ = 62.49 on Apple Silicon and $\tval$ = 6.70 on Intel x86, both far above the 4.5 failure threshold. Taken at face value, these results block ML-KEM deployment across the US federal government and any organization requiring FIPS compliance.

The leakage is not real. The signal comes from temporal drift in the measurement process: the standard protocol collects all fixed-input measurements in one block, then all random-input measurements in another. During these multi-minute collection runs, system state evolves (thermal throttling, OS scheduling, power management) and these environmental changes correlate perfectly with group assignment. TVLA interprets the resulting distributional shift as cryptographic leakage.

The fix is simple: interleaved collection, alternating fixed and random traces within a single run, eliminates the drift entirely. TVLA passes on both platforms ($\tval$ = 0.58 on Apple Silicon, $\tval$ = 1.65 on Intel x86). We prove non-exploitability through 150+ converging experiments across our full dataset and release sca-triage, a practical triage tool for evaluation labs.

### 1.1 Key Result

We isolated two confound sources in a 2x2 experimental design across two platforms:

**Table 1:** 2x2 experimental design isolating temporal drift and harness asymmetry. Each cell shows the Welch $\tval$ statistic.

|  | Sequential Asymmetric | Sequential Symmetric | Interleaved Asymmetric | Interleaved Symmetric |
|--|---|---|---|---|
| **Apple Silicon** | 3.00 (PASS) | 62.49 (FAIL) | 0.99 (PASS) | 0.58 (PASS) |
| **Intel x86** | 5.35 (FAIL) | 6.70 (FAIL) | 8.10 (FAIL) | 1.65 (PASS) |

Reading across columns isolates the effect of each fix:

- **Symmetric harness** (columns 1 to 2): Eliminates cache pollution but reveals temporal drift. On Apple, $\tval$ *increases* from 3.00 to 62.49 because cache pollution was masking drift.
- **Interleaved collection** (columns 2 to 4): Eliminates temporal drift. On both platforms, $\tval$ drops to non-significant (0.58 and 1.65).
- **Intel asymmetric interleaved** (column 3): Still fails ($\tval$ = 8.10), confirming that live keygen+encaps cache pollution is a real secondary confound on Intel, independent of temporal drift.
- **Both fixes combined** (column 4): Symmetric + interleaved passes on both platforms. This is the definitive result.

### 1.2 Background

There is no "borderline" TVLA failure: exceeding $\tval$ = 4.5 triggers a remediation cycle costing months of engineering time and \$50,000 to \$150,000 in lab fees. With NIST finalizing ML-KEM in August 2024 and CNSA 2.0 (NSA's Commercial National Security Algorithm Suite timeline) mandating quantum-resistant cryptography for national security systems by 2033, false TVLA failures directly impede PQC migration across government and regulated industries. Evaluation labs are running these tests on modern hardware today, and failures are being reported today.

---

## 2. Related Work

TVLA's limitations on general-purpose hardware are well-documented: Schneider and Moradi [1] showed environmental noise produces non-exploitable statistical significance; Whitnall and Oswald [2] established fair evaluation frameworks for side-channel distinguishers; Mather et al. [3] provided a priori statistical power analysis for leakage detection; Bronchain and Standaert [4] introduced Perceived Information because TVLA detection does not imply exploitability; Dunsche et al. [6, 7] proposed improved statistical tests with controlled type-1 error. Our work is complementary: Dunsche et al. address the *statistical test*; we address the *measurement methodology* and provide a practical triage tool.

dudect (Reparaz et al. [5]) already interleaves fixed and random inputs by design, inherently preventing temporal drift, validating our diagnosis. Our contribution is not discovering that interleaving prevents drift; it is demonstrating that ISO 17825's implicit sequential protocol produces catastrophic false positives on production hardware ($\tval$ inflated from 0.58 to 62.49 on Apple Silicon), quantifying the effect across two instruction set architectures (ISAs), proving non-exploitability through 150+ experiments, and releasing sca-triage for the FIPS ecosystem.

---

## 3. The Investigation

We collected 12.2 million timing traces across both platforms trying to turn this TVLA result into an actual key recovery attack. We did not set out to prove TVLA wrong. We set out to exploit the leakage it reported. Every technique we tried (and we tried everything) came back empty.

### 3.1 Measurement Setup

**Apple Silicon M-series.** Timing source: CNTVCT_EL0 at 24 MHz (~41.7 ns granularity), 99.2% zero-tick overhead. Because ML-KEM decapsulation requires over 500 ticks (~20,000 ns), this 41.7 ns granularity is perfectly adequate for capturing the macro-timing variances (which swing by hundreds of ticks) responsible for TVLA failures, even though it cannot resolve single-instruction micro-timing. Performance governor pinned to high-performance; thermal throttling monitored.

**Intel Xeon x86.** Timing source: RDTSC with CPUID serialization for high-resolution cycle counting (~1,778 cycles overhead per read). While the serialization overhead introduces a variable noise source (pipeline state affects retirement latency), our 50-repetition per-key aggregation suppresses this variance by a factor of sqrt(50), approximately 7x (standard error of the mean), pushing the detection floor down to 454 Intel cycles (approximately 189 ns at 2.4 GHz), the minimum detectable *difference* in decapsulation time, accounting for both the attenuated timer overhead and residual OS scheduling noise. Performance governor pinned; hyperthreading accounted for.

**Data collection.** 500 distinct keys x 50 repetitions per key per condition = 12.2 million measurements across both platforms. Collection automated and SHA-256 checksummed. Full details in Appendix C.

### 3.2 Bounding Exploitability

We threw every attack in the side-channel toolkit at this data: gradient-boosted classifiers, neural networks, template attacks, information-theoretic bounds. Over 150 experiments across both platforms and multiple configurations. Every one came back empty.

**Zero exploitable signal.** Every technique performed at or below random guessing. XGBoost achieves 50.2% on binary key-bit classification (majority baseline: 50.0%). KSG mutual information returns 0.000 bits ($p = 1.0$). Perceived Information is negative for all targets. At the single-trace level (100K unaggregated measurements), Cohen's $d = 0.0003$ for sk_lsb ($d < 0.2$ is conventionally "small"). The null result holds at every granularity (aggregated summaries, raw traces, and cross-platform) ruling out aggregation masking. Higher-order analysis is inapplicable to scalar timing (one value per execution; no second sample to combine). See Appendix B for metric definitions and methodology.

### 3.3 The Positive Control

A negative result is only meaningful if the apparatus can detect a positive. We built the same measurement pipeline against liboqs v0.9.0, a version vulnerable to KyberSlash [10], a known timing side-channel where the decapsulation routine performs a variable-time division operation that leaks information about the secret key.

The results are unambiguous. On vulnerable code, our XGBoost classifier achieves +3.8% accuracy lift over chance ($p < 0.01$). On patched code (v0.15.0), +0.5%, consistent with noise. While KSG definitively bounds macro-timing leakage at zero, non-parametric estimators lack the statistical power to detect minute, sub-cycle micro-leaks like KyberSlash without millions of traces; targeted ML feature extraction (XGBoost) is required for sub-threshold hunting. For valid/invalid ciphertext classification (a simpler binary task), the classifier achieves 100% accuracy on both vulnerable and patched versions, confirming that the pipeline can detect input-dependent timing leakage regardless of whether secret-dependent leakage is present.

Our apparatus detects both secret-dependent and input-dependent timing leakage when they exist. The null result on patched ML-KEM is not a measurement failure; it is a measurement. Our pipeline's detection floor is $d \approx 0.275$; effects below $d \approx 0.1$ are below all detection mechanisms and unexploitable via userspace timing (full sensitivity characterization in Section 5).

**Information-theoretic confirmation.** Six independent methods all converge on zero extractable bits: Perceived Information (negative for all targets), KSG mutual information (0.000 bits, $p = 1.0$), MAD-based SNR (zero), Winsorized SNR (zero), and vertical scaling analysis (flat accuracy curves at 15x predicted minimum sample). Definitions and methodology in Appendix B. The TVLA result of $\tval$ = 62.49 reports a signal that, by every other information-theoretic measure, does not exist, and that vanishes ($\tval$ = 0.58) when collection is interleaved.

---

## 4. The Root Cause

If TVLA reports significant leakage and no attack can exploit it, the question is not "where is the leakage hiding?" but "what is TVLA actually detecting?"

### 4.1 The Complete Picture

Table 1 (Section 1.1) shows the complete 2x2 experimental design. Two confound sources produce this pattern. Here is how we isolated each one.

### 4.2 The Proof: Pairwise Decomposition

Pairwise decomposition is the definitive proof that the TVLA signal is not secret-dependent. Instead of comparing fixed-vs-random (which confounds input repetition with secret identity), we compare timing distributions grouped by actual secret properties (individual key bits, Hamming weight classes, key byte values) while holding the fixed-vs-random structure constant.

When we split traces by actual secret properties instead of TVLA group assignment, the distributions are identical. Every pairwise t-test, every distributional comparison, every classifier trained on actual secret labels performs at chance. The structure TVLA detects vanishes entirely when the comparison is reframed around the secret rather than around input repetition.

The leakage is input-dependent, not secret-dependent. TVLA cannot distinguish between the two. This is not a subtle statistical argument; it is a complete decomposition that isolates the confound and shows it accounts for 100% of the TVLA signal.

### 4.3 The Harness Asymmetry Problem

Our TVLA harness, like virtually every software TVLA harness we have encountered in open-source PQC testing, executes different code paths in fixed vs random modes. In fixed mode, a single (ciphertext, secret key) pair is generated once during setup, and each iteration simply times `decaps()`. In random mode, each iteration generates a fresh keypair via `keygen()` and a fresh ciphertext via `encaps()` before timing `decaps()`. Although `keygen()` and `encaps()` execute *outside* the timing window, they pollute cache lines, branch predictor state, and prefetcher history before the timed operation begins.

This asymmetry is not a bug in our harness; it is the natural implementation of ISO 17825's fixed-vs-random protocol for software evaluations. The standard requires "random" inputs; generating them per-iteration is the obvious approach and the one most developers and evaluation labs adopt. A fully symmetric harness would pre-generate all random inputs into a memory array and index into it, ensuring identical cache footprints across both modes. We implemented this symmetric design (below) and found it eliminates the harness asymmetry confound, but sequential collection still fails due to temporal drift. We suspect most evaluation labs have not implemented symmetric harnesses, meaning they are observing false positives from both sources simultaneously.

### 4.4 The Temporal Drift Confound

Even with a perfectly symmetric harness, TVLA fails catastrophically when fixed and random measurements are collected in separate sequential blocks. We initially blamed an architectural confound: adaptive microarchitecture responding differently to repeated vs. novel inputs. The interleaved control experiment disproves this: when fixed and random measurements alternate within a single collection run, TVLA passes on both platforms. The confound is temporal drift between sequential collection blocks, not the CPU's response to data content.

In sequential collection, the fixed block runs first (e.g., 50,000 consecutive decapsulations on the same input), then the random block runs (50,000 decapsulations on distinct inputs). Between these blocks, and during each block, system state evolves through multiple mechanisms:

- **Thermal throttling:** the CPU die heats during sustained computation, causing the clock frequency to drop mid-run.
- **OS scheduler jitter:** CFS (Linux) or Grand Central Dispatch (macOS) quantum boundaries redistribute background work unevenly across the two collection windows.
- **DVFS (Dynamic Voltage and Frequency Scaling):** the hardware shifts CPU clock speed and voltage based on workload, introducing measurement drift that tracks load history, not secret data.
- **Memory controller scheduling:** DRAM temperature rises over a long run, changing row-access latencies for later measurements.

On our Apple Silicon test platform, a 50K-trace collection block runs for approximately 30 seconds, long enough for thermal management to trigger multiple P-state transitions. These environmental changes are systematic (not random noise) and correlate perfectly with group assignment because all fixed measurements occupy one contiguous time window and all random measurements occupy another.

### 4.5 Per-Platform Evidence

**Apple Silicon.** The symmetric harness pre-generates all inputs so both modes execute identical code paths (array index, then decaps, then record timing). Despite this, sequential collection fails catastrophically:

**Table 2:** Apple Silicon sequential collection results.

| Harness (Sequential) | $\tval$ | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|----------------|--------------------|--------------------|-------------|
| Asymmetric | 3.00 | 0.16x | 523.0 | 525.4 | **PASS** |
| Symmetric | 62.49 | 7.71x | 594.5 | 532.6 | **FAIL** |

**Table 3:** Apple Silicon interleaved collection results.

| Harness (Interleaved) | $\tval$ | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|----------------|--------------------|--------------------|-------------|
| Asymmetric | 0.99 | 0.10x | 508.0 | 513.3 | **PASS** |
| Symmetric | 0.58 | 0.95x | 555.3 | 551.4 | **PASS** |

The t-statistic drops from 62.49 to 0.58 solely by eliminating temporal drift. If the confound were driven by Apple's Data Memory-Dependent Prefetcher (DMP [9]), it would persist under interleaved collection. The fact that interleaving eliminates the signal confirms temporal drift as the sole cause.

**Intel x86.** Intel Xeon shows the same confound:

**Table 4:** Intel x86 sequential collection results.

| Harness (Sequential) | $\tval$ | TVLA Verdict |
|---------|-----|-------------|
| Asymmetric | 5.35 | **FAIL** |
| Symmetric | 6.70 | **FAIL** |

**Table 5:** Intel x86 interleaved collection results.

| Harness (Interleaved) | $\tval$ | TVLA Verdict |
|---------|-----|-------------|
| Asymmetric | 8.10 | **FAIL** |
| Symmetric | 1.65 | **PASS** |

The symmetric harness's higher absolute cycle counts (183K vs 58K in the interleaved data) reflect the cost of indexing into a pre-generated array of 50,000 (ciphertext, key) pairs; this memory footprint introduces uniform cache pressure that inflates both groups equally without affecting the t-test comparison. The asymmetric interleaved failure ($\tval$ = 8.10) confirms cache pollution from live keygen+encaps is a real secondary confound on Intel, independent of temporal drift. Apple Silicon's interleaved asymmetric harness passes ($\tval$ = 0.99), likely because its large shared L2/SLC cache absorbs the pollution (see Limitations).

### 4.6 Compiler Optimization Level Independence

We recompiled the symmetric harness at five optimization levels (50,000 traces per mode):

**Table 6:** Compiler optimization sweep (Apple Silicon, symmetric harness, 50K traces).

| Flag | $\tval$ | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|------|-----|----------------|--------------------|--------------------|-------------|
| `-O0` | 10.40 | 0.07x | 559.9 | 544.4 | **FAIL** |
| `-O1` | 8.71 | 0.60x | 530.3 | 536.8 | **FAIL** |
| `-O2` | 19.07 | 0.02x | 535.9 | 605.0 | **FAIL** |
| `-O3` | 5.27 | 1.10x | 741.9 | 658.9 | **FAIL** |
| `-Os` | 1.73 | 30.89x | 1529.0 | 995.4 | **PASS** |
| `-Os` (rerun) | 11.47 | 466x | N/A | N/A | **FAIL** |

All five levels fail TVLA. The `-Os` run-to-run instability ($\tval$ = 1.73 then 11.47, same binary, same hardware) proves the signal is environmental, not cryptographic: real leakage produces consistent results. Binary analysis confirms identical ML-KEM decapsulation code across flags (liboqs is statically linked). Levene's test on the `-Os` data confirms the variance asymmetry is significant ($F = 128.25$, $p = 1.03 \times 10^{-29}$). Mean values for the `-Os` rerun were not recorded.

---

## 5. The Fix

The finding does not mean TVLA is useless. It means TVLA is incomplete. A TVLA pass is still meaningful: if the distributions are indistinguishable, there is no leakage of any kind to worry about. The problem is TVLA failures on modern hardware, which require a second stage of analysis to determine whether the detected signal is exploitable.

### 5.1 The Two-Stage Evaluation Protocol

We propose a two-stage protocol for non-invasive side-channel evaluation of cryptographic implementations on general-purpose processors:

**Stage 1: Standard TVLA.** Run the fixed-vs-random Welch's t-test exactly as specified in ISO 17825. If $\tval$ <= 4.5, the implementation passes FIPS 140-3 macro-timing requirements. Evaluators requiring higher assurance against sub-threshold vulnerabilities (like KyberSlash at $d = 0.094$) must proceed to ML-based population aggregation or hardware EM probing. If $\tval$ > 4.5, proceed to Stage 2.

**Stage 2: Confound Triage.** If $\tval$ > 4.5, run pairwise secret-group decomposition: split the collected traces by actual secret key properties (individual bits, byte values, Hamming weight, the number of 1-bits in the key) and recompute the t-test for each pairwise comparison. Compute permutation-validated mutual information between timing measurements and secret key material. sca-triage automates this and generates a formal justification artifact for CMVP (Cryptographic Module Validation Program) non-conformance review.

The decision logic is clear:

- If pairwise decomposition shows **no significant differences** between secret groups AND mutual information is **zero** (within permutation confidence): the TVLA failure is a **false positive** caused by temporal drift. The justification artifact demonstrates to the CMVP that the failure is non-exploitable.
- If pairwise decomposition **detects significant differences** between secret groups OR mutual information is **positive**: the leakage is **real and secret-dependent**. The implementation **fails**.

This protocol preserves TVLA's role as a conservative first-pass screen while eliminating false positives from temporal-drift confounds. It adds cost only when TVLA fails, which, with sequential collection on modern hardware, will be most of the time.

### 5.2 The Tool: sca-triage

We release **sca-triage**, an open-source Python tool implementing the triage protocol (`pip install sca-triage`):

```bash
sca-triage analyze --timing-data traces.npz --secret-labels keys.csv \
    --targets sk_lsb,sk_byte_0,sk_hw --permutation-shuffles 10000
```

The tool runs three stages: (1) standard TVLA (Welch's t-test, pass/fail at $\tval$ = 4.5), (2) pairwise secret-group decomposition (regroups traces by key bits, byte values, Hamming weight; runs t-tests within each partition), and (3) KSG mutual information validated by permutation test. If TVLA fails but all pairwise tests are non-significant *and* MI is zero within the permutation confidence interval, the verdict is FALSE_POSITIVE. Output is JSON with full statistics, suitable for CMVP submission.

**Worked example.** On our Apple Silicon asymmetric harness data (50,000 traces, $\tval$ = 8.42, representative of what evaluation labs encounter; symmetric data produces the same verdict at $\tval$ = 62.49), the full pipeline (`python scripts/dudect_comparison.py`) produces:

```
[Stage 1] Running Fixed-vs-Random TVLA...
  |t| = 8.42  (FAIL)  variance ratio = 10.19

[Stage 2] Running Pairwise Secret-Group Decomposition...
  sk_lsb:   t=0.59, p=0.553  (not significant)
  msg_hw:   t=0.84, p=0.402  (not significant)

[Stage 3] Running Permutation MI Test...
  MI = 0.000 bits, p=1.0  (not significant)

VERDICT: FALSE_POSITIVE
```

> **Warning:** Verdict bounded by macro-timing detection floor ($d \approx 0.275$). Does not guarantee zero leakage against hardware/EM probing or sub-threshold micro-architectural channels.

Pairwise decomposition tests 13 secret-key properties; all return non-significant. KSG MI provides a model-free backstop capturing nonlinear dependencies that pairwise tests might miss. A FALSE_POSITIVE verdict guarantees no secret-dependent leakage above the $d \approx 0.275$ macro-timing noise floor, the limit of userspace exploitability. Below this threshold, hardware EM probing is required.

**Sensitivity and detection floors.** We validated detection capability by injecting synthetic timing leaks at Cohen's $d \in [0.005, 1.0]$ across 20 trials per effect size: 90% detection at $d = 0.3$, 100% at $d = 0.5$. The per-experiment pipeline floor is $d \approx 0.275$ (80% detection). The pairwise t-test floor alone is $d = 0.398$ (454 Intel cycles at 80% power); the ML classification floor is $d \approx 0.85$. The multi-method pipeline is more sensitive than any single test. KyberSlash ($d = 0.094$) falls below all per-experiment floors but was detected through a different mechanism: population-level aggregation across 500 keys, where XGBoost learns weak but consistent cross-key patterns (+3.8% lift). The per-experiment floor ($d \approx 0.275$) and population-level detection ($d = 0.094$) characterize complementary mechanisms, not the same pathway. Effects below $d \approx 0.1$ are below both and unexploitable via userspace macro-timing. Full triage completes in under 30 seconds on 50K traces.

### 5.3 Why the Welch's t-Test Alone Is Insufficient

The core statistical test in both TVLA and dudect is a Welch's t-test comparing two timing distributions. dudect [5] solves the temporal-drift problem by interleaving its measurement loop; if you run the actual dudect binary, it will not produce false positives from drift. But dudect does not protect against harness asymmetry (cache pollution from live keygen+encaps in random mode), and critically, FIPS evaluation labs running ISO 17825 do not use dudect's interleaved collection; they collect sequentially.

The question sca-triage answers is different from what dudect or TVLA answer. The Welch's t-test tells you whether two distributions differ. It cannot tell you *why* they differ: temporal drift, harness asymmetry, or real leakage all produce the same FAIL. sca-triage's pairwise decomposition and MI stages provide the missing diagnostic:

**Table 7:** Welch's t-test vs. sca-triage three-stage pipeline.

| Analysis | Patched v0.15.0 (no real leak) | Vulnerable v0.9.0 (KyberSlash) |
|------|------|------|
| **Welch's t-test (sequential data)** | $\tval$ = 8.42, FAIL | $\tval$ = 1.04, Underpowered |
| **dudect (interleaved collection)** | PASS (solves temporal drift) | FALSE NEGATIVE (underpowered at 25K traces) |
| **dudect (interleaved asymmetric)** | FALSE POSITIVE on Intel ($\tval$ = 8.10, cache pollution);<br>PASS on Apple ($\tval$ = 0.99) | N/A |
| **sca-triage (three-stage)** | FALSE_POSITIVE (pairwise $d=0.0003$, MI=0.0 bits) | REAL_LEAKAGE (Stage 3 ML aggregation detects +3.8% lift; Stage 1 t-test underpowered) |

The Welch's t-test alone cannot distinguish temporal drift, cache pollution, or real leakage. sca-triage's three-stage pipeline correctly triages all three cases, including the platform-dependent cache-pollution false positive on Intel that dudect's interleaved collection cannot resolve.

**Repository:** [https://github.com/asdfghjkltygh/m-series-pqc-timing-leak/tree/main/sca-triage](https://github.com/asdfghjkltygh/m-series-pqc-timing-leak/tree/main/sca-triage)

### 5.4 Recommendations for Standards Bodies

1. **Mandate interleaved collection.** ISO 17825's implicit sequential protocol introduces temporal drift that produces false positives on general-purpose processors. Mandating interleaved collection, or requiring pairwise decomposition as a mandatory follow-up to any TVLA failure, eliminates the most common source of false positives.

2. **Acknowledge the confound in FIPS 140-3 guidance.** NIST's Implementation Guidance should describe the temporal-drift confound, its root cause, and available mitigations. Without explicit guidance, evaluation labs rediscover the problem independently and reach inconsistent conclusions.

3. **Adopt pairwise decomposition in lab SOPs.** The marginal cost is small (the traces are already collected) and pairwise analysis provides a safety net even when interleaved collection is not feasible. Together, interleaving and pairwise decomposition eliminate the most common source of false positives on modern hardware.

---

## 6. Impact and Implications

### 6.1 What This Means for PQC Migration

The bottom line for organizations deploying post-quantum cryptography: **ML-KEM deployment should not be delayed based on TVLA-only evaluations.** The TVLA failures reported on Apple Silicon and Intel x86 are false positives caused by temporal drift in sequential data collection, not by weaknesses in the algorithm or its implementation. Interleaved collection eliminates the confound entirely on both platforms.

**Threat model scope.** We do not claim liboqs is perfectly constant-time. Two complementary detection mechanisms set the sensitivity bounds:

- *Per-trace detection floor* at $d \approx 0.275$: no secret-dependent macro-timing leak exceeds this threshold for any individual key.
- *Population-aggregated detection floor* at $d = 0.094$: vulnerabilities affecting multiple keys (like KyberSlash) are detected by aggregating weak but consistent signals across the 500-key population via sca-triage's ML classifiers.

The per-trace floor is the strict upper bound on undetected leakage for any single key; population-level aggregation extends sensitivity to smaller effects that are consistent across keys.

An attacker with kernel-level performance counter access could achieve high-resolution cycle counting and potentially detect sub-threshold leakage. But that attacker already has ring-0 execution, placing them outside the remote/userspace threat model that FIPS 140-3 non-invasive evaluation targets.

The liboqs KyberSlash fix (v0.15.0 and later) is effective. Our positive control confirms the known timing vulnerability in pre-patch versions is detectable and the patch eliminates it. Organizations integrating liboqs at current versions can proceed with confidence that the implementation is timing-safe against remote and userspace adversaries constrained by OS scheduling noise and standard timer resolution. While our lab apparatus detects sub-threshold leaks like KyberSlash by aggregating 50,000 traces across 500 keys under controlled conditions, practical remote exploitation of such minute sub-cycle leaks against a single target key remains infeasible under realistic network and OS noise.

For organizations already in FIPS evaluation: if your lab has reported a TVLA failure on ML-KEM running on Apple Silicon or Intel hardware, request a Stage 2 analysis. Point evaluators to this paper and the sca-triage tool. The TVLA failure is real in the statistical sense, but it does not represent exploitable leakage.

### 6.2 What This Means for Other PQC Algorithms

The confound is demonstrated here for ML-KEM, but because the root cause is methodological (sequential collection introducing temporal drift between measurement groups), it will affect any algorithm evaluated with sequential TVLA on any hardware where system state evolves during collection. This includes ML-DSA (Dilithium), SLH-DSA (SPHINCS+), BIKE, and HQC. This is a testable prediction: replicating the interleaved vs. sequential experiment with each algorithm's entry point would confirm or refute it. We have not yet performed this cross-algorithm validation; it is immediate future work. Until then, evaluation labs should treat TVLA failures on any PQC algorithm collected sequentially as potentially confounded, and either switch to interleaved collection or apply pairwise decomposition before concluding the leakage is real.

### 6.3 Broader Implications

TVLA was designed for embedded hardware (smartcards, FPGAs, dedicated coprocessors [8]) where timing is largely deterministic and trace collection completes before environmental drift matters. On general-purpose processors, collection runs take minutes to hours. System state evolves continuously, and sequential collection creates a perfect confound: fixed measurements occupy one time window, random measurements occupy another, and any drift between them becomes a systematic group difference that TVLA reads as leakage.

The gap between "TVLA-detectable" and "exploitable" is wider on modern processors than FIPS evaluation practice assumes. A $\tval$ of 62.49 on Apple Silicon contains zero bits of secret information and vanishes ($\tval$ = 0.58) when collection is interleaved. TVLA assumes temporal stationarity between measurement groups, an assumption that fails on any system where environmental conditions evolve during collection. Side-channel evaluation standards must evolve alongside the hardware they evaluate.

### 6.4 Limitations

**Temporal drift mechanism uncharacterized.** We demonstrate that sequential collection introduces catastrophic temporal drift but have not isolated the specific physical mechanism (thermal throttling, OS scheduling, DVFS). The interleaved control proves drift is the cause regardless of mechanism; the fix is mechanism-agnostic.

**ML-KEM only.** We have not yet run cross-algorithm validation (ML-DSA, SLH-DSA, BIKE, HQC). The confound is methodological, not algorithm-specific, but empirical confirmation across algorithms would strengthen the generalization claim.

**Apple Silicon cache absorption hypothesis unverified.** We hypothesize that Apple Silicon's interleaved asymmetric harness passes ($\tval$ = 0.99) while Intel fails ($\tval$ = 8.10) because Apple's large shared L2/SLC cache absorbs keygen+encaps pollution. The symmetric interleaved result ($\tval$ = 0.58) is the definitive measurement regardless of mechanism.

**No NTT-internal intermediate targets.** We tested key-level and message-level properties but not butterfly outputs, Montgomery reduction intermediates, or CBD sampling. Our raw-trace analysis bounds any per-execution timing signal at $d < 0.001$, constraining intermediate-value leakage.

**ISO 17825:2024 untested.** We tested against the Goodwill (2011) methodology as widely implemented by CMVP labs. The 2024 revision introduced percentile-based timing analysis and updated sample size requirements; replicating against it is immediate future work.

---

## References

[1] Schneider, T. and Moradi, A., "Leakage Assessment Methodology: A Clear and Practical Approach," CHES 2015.

[2] Whitnall, C. and Oswald, E., "A Fair Evaluation Framework for Comparing Side-Channel Distinguishers," Journal of Cryptographic Engineering, 2011/2014.

[3] Mather, L. et al., "Does My Device Leak Information? An a priori Statistical Power Analysis of Leakage Detection Tests," ASIACRYPT 2019.

[4] Bronchain, O. and Standaert, F.-X., "Breaking Masked Implementations with Many Shares on 32-bit Software Platforms, or When the Security Order Does Not Matter," TCHES 2021.

[5] Reparaz, O. et al., "dude, is my code constant time?," DATE 2017.

[6] Dunsche, M. et al., "What's the Opposite of a Leakage? On TVLA's Limits and Improvements," USENIX Security 2024.

[7] Dunsche, M. et al., "SILENT: Advancing Side-channel Leakage Detection," arXiv 2025.

[8] Gaj, K. et al., "FOBOS: Flexible Open-source Board for Side-channel analysis," NIST Lightweight Cryptography Workshop 2019.

[9] Borah, P. et al., "GoFetch: Breaking Constant-Time Cryptographic Implementations Using Data Memory-Dependent Prefetchers," USENIX Security 2024.

[10] Bernstein, D.J. et al., "KyberSlash: Exploiting secret-dependent division timings in Kyber implementations," 2023.

---

## Appendix A: Full Experiment Results

The complete experiment matrix is organized into five categories:

**Classification experiments:** binary and multi-class classification of secret key material from timing traces. Columns: experiment ID, model (XGBoost, Random Forest, CNN, Logistic Regression), feature set, target variable (key bit, key byte, Hamming weight), accuracy, p-value vs. majority baseline, majority baseline, verdict (PASS/FAIL/INCONCLUSIVE).

**Regression experiments:** continuous prediction of secret key bytes and derived quantities. Columns: experiment ID, model, feature set, target, MSE, R-squared, baseline MSE (mean predictor), verdict.

**Template attack experiments:** Gaussian profiling attacks with maximum-likelihood classification. Columns: experiment ID, profiling traces, attack traces, number of classes, success rate, guessing entropy, random baseline, verdict.

**Unsupervised experiments:** PCA, t-SNE, and clustering analysis for latent structure discovery. Columns: experiment ID, method, number of components/clusters, explained variance, silhouette score, visual separation (Y/N), verdict.

**Information-theoretic experiments:** Perceived Information, KSG MI, MAD-SNR, Winsorized SNR, vertical scaling analysis. Columns: experiment ID, metric, value, permutation p-value, confidence interval, verdict.

Full tables are available in the supplementary materials repository. Each experiment includes reproducibility metadata: random seed, train/test split, hyperparameter configuration, and runtime.

---

## Appendix B: Information-Theoretic Methodology

We used four complementary metrics to bound information leakage. Each was chosen for a specific property; all were validated via 10,000-shuffle permutation tests rather than parametric assumptions.

- **Perceived Information (PI):** Measures exactly how many bits of secret information a machine learning classifier can extract above pure random guessing. Negative PI means the classifier performs worse than chance, meaning zero exploitable information. Computed with 5-fold cross-validation to prevent overfitting bias.
- **KSG Mutual Information:** A model-free mathematical bound that proves whether any statistical relationship exists between the timing and the key, regardless of the leak's shape. Returns 0.000 bits ($p = 1.0$) for all targets; the observed MI is at or below the permutation null median.
- **MAD-based and Winsorized SNR:** Robust signal-to-noise ratios that filter out the extreme, heavy-tailed OS scheduling outliers that break standard variance math on modern processors. Both return zero for all targets.
- **Vertical scaling convergence:** The "learning curve" test. Real leakage causes classifier accuracy to climb as training data grows; false positives produce a flat line because there is nothing to learn. All targets show flat lines.

---

## Appendix C: Measurement Apparatus

**Timer characterization.**

*CNTVCT_EL0 (Apple Silicon):* ARM generic timer counter, 24 MHz tick rate. Inline assembly uses ISB (Instruction Synchronization Barrier) before each MRS read to force all prior instructions to retire, preventing out-of-order execution from reordering timer reads across the decapsulation boundary. Overhead characterization: 99.2% of back-to-back reads return zero ticks elapsed, confirming sub-tick measurement granularity. Timer is monotonic and unaffected by frequency scaling (it runs on a fixed-frequency crystal, not the CPU clock).

*RDTSC + CPUID (Intel x86):* Timestamp counter read with pipeline serialization. CPUID before RDTSC forces all prior instructions to retire, ensuring the timestamp reflects actual completion. Measured overhead: approximately 1,778 cycles per serialized read pair. TSC is invariant (constant rate regardless of frequency scaling) on all tested processors.

**Data collection protocol.**

- 500 distinct secret keys, uniformly sampled
- 50 repetitions per key per measurement condition
- Two platforms (Apple M-series, Intel Xeon)
- Two conditions per platform (fixed input, random input)
- Total: approximately 12.2 million individual timing measurements
- The open-source repository contains representative sample datasets (1M TVLA traces, 100K raw traces, 25K vulnerable traces) for immediate, low-friction validation of the sca-triage pipeline. The full 12.2 million trace dataset is available from the authors upon request for exhaustive replication.
- All measurements checksummed (SHA-256) at collection time for reproducibility
- Collection scripts automated with retry logic for thermal throttling events

**Compilation and build environment.**

*Patched build:* liboqs v0.15.0, compiled with `-O2 -march=native`, standard constant-time flags enabled. This is the current recommended production build.

*Vulnerable build:* liboqs v0.9.0, compiled with identical flags. This version contains the KyberSlash vulnerability (variable-time division in decapsulation) and serves as the positive control.

Both builds use the same ML-KEM-768 parameter set. All measurements target the `OQS_KEM_kyber_768_decaps` entry point.
