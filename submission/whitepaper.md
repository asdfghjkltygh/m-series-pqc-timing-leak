# When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment

**Saahil Shenoy**
Founding AI Scientist, Bedrock Data
saahil@bedrockdata.ai

March 2026

---

## Section 1: The Problem

Sequential |t| = 62.49. Interleaved |t| = 0.58. Same hardware, same code, same inputs. The FIPS side-channel test for post-quantum crypto is broken.

TVLA (Test Vector Leakage Assessment) is the mandatory side-channel evaluation for ISO 17825 / FIPS 140-3 certification. It works by collecting two sets of timing measurements — a "fixed" set using one repeated input and a "random" set using different inputs each time — then running a Welch's t-test to detect distributional differences. If |t| exceeds 4.5, the implementation fails. When we run TVLA on liboqs ML-KEM-768 — the most widely integrated open-source implementation of the NIST post-quantum key encapsulation standard (a protocol for securely exchanging symmetric keys) — it reports catastrophic leakage: |t| = 62.49 on Apple Silicon and |t| = 6.70 on Intel x86 — far above the failure threshold. Taken at face value, these results block ML-KEM deployment across the US federal government and any organization requiring FIPS compliance.

The leakage is not real. The signal comes from a temporal-drift confound: the standard protocol collects all fixed-input measurements in one block, then all random-input measurements in another. During these multi-minute collection runs, system state evolves — thermal throttling, OS scheduling, power management — and these environmental changes correlate perfectly with group assignment. TVLA interprets the resulting distributional difference as cryptographic leakage. Interleaved collection — alternating fixed and random traces within a single run — eliminates the confound entirely. TVLA passes on both platforms (|t| = 0.58 on Apple Silicon, |t| = 1.65 on Intel x86). We prove non-exploitability through 150+ converging experiments across 12.2 million traces and release sca-triage, a practical triage tool for evaluation labs.

### Key Result: Sequential vs. Interleaved Collection

| Platform | Collection | Harness | |t| | TVLA Verdict |
|----------|-----------|---------|-----|-------------|
| Apple Silicon | Sequential | Asymmetric | 3.00 | **PASS** |
| Apple Silicon | Sequential | Symmetric | 62.49 | **FAIL** |
| Apple Silicon | Interleaved | Asymmetric | 0.99 | **PASS** |
| Apple Silicon | Interleaved | Symmetric | 0.58 | **PASS** |
| Intel x86 | Sequential | Asymmetric | 5.35 | **FAIL** |
| Intel x86 | Sequential | Symmetric | 6.70 | **FAIL** |
| Intel x86 | Interleaved | Asymmetric | 8.10 | **FAIL** |
| Intel x86 | Interleaved | Symmetric | 1.65 | **PASS** |

Switching from sequential to interleaved collection reduces Apple Silicon's |t| from 62.49 to 0.58 — a 100x attenuation — with no change to the hardware, software, or cryptographic inputs. On Intel, the same switch drops |t| from 6.70 to 1.65. The remaining Intel asymmetric failure (|t| = 8.10) reflects a secondary confound from cache pollution by live keygen+encaps, not temporal drift.

### Background

There is no "borderline" TVLA failure — exceeding |t| = 4.5 triggers a remediation cycle costing months of engineering time and $50,000–$150,000 in lab fees. With NIST finalizing ML-KEM in August 2024 and CNSA 2.0 mandating quantum-resistant cryptography for national security systems by 2033, false TVLA failures directly impede PQC migration across government and regulated industries. Evaluation labs are running these tests on modern hardware today, and failures are being reported today.

---

## Related Work

TVLA's limitations on general-purpose hardware are documented: Schneider & Moradi (CHES 2015) showed environmental noise produces non-exploitable statistical significance; Bronchain & Standaert (TCHES 2021) introduced Perceived Information because TVLA detection does not imply exploitability; Dunsche et al. (USENIX Security 2024, SILENT 2025) proposed improved statistical tests with controlled type-1 error. Our work is complementary — Dunsche et al. address the *statistical test*; we address the *measurement methodology* and provide a practical triage tool.

dudect (Reparaz et al., DATE 2017) already interleaves fixed and random inputs by design, inherently preventing temporal drift — validating our diagnosis. Our contribution is not discovering that interleaving prevents drift; it is demonstrating that ISO 17825's implicit sequential protocol produces catastrophic false positives on production hardware (100x inflation on Apple Silicon), quantifying the effect across two ISAs, proving non-exploitability through 150+ experiments, and releasing sca-triage for the FIPS ecosystem.

---

## Section 2: The Investigation

We collected 12.2 million timing traces across both platforms trying to turn this TVLA result into an actual key recovery attack. We did not set out to prove TVLA wrong. We set out to exploit the leakage it reported. Every technique we tried — and we tried everything — came back empty.

### Measurement Setup

**Apple Silicon M-series.** Timing source: CNTVCT_EL0 at 24 MHz (~41.7 ns granularity), 99.2% zero-tick overhead. This conservative resolution means both the TVLA failure (|t| = 62.49) and the null pairwise result are robust to timer granularity. Performance governor pinned to high-performance; thermal throttling monitored.

**Intel Xeon x86.** Timing source: RDTSC with CPUID serialization for cycle-accurate measurement (~1,778 cycles overhead per read). The overhead is a constant additive bias affecting both groups identically; it cancels in the t-test. While this overhead acts as a stationary noise source, our 50-repetition per-key aggregation suppresses this variance sufficiently to push the detection floor down to 454 cycles — the minimum detectable *difference* in decapsulation time, not the absolute timer resolution. Performance governor pinned; hyperthreading accounted for.

**Data collection.** 500 distinct keys × 50 repetitions per key per condition = 12.2 million measurements across both platforms. Collection automated and SHA-256 checksummed. Full details in Appendix C.

### Bounding Exploitability

We applied the full side-channel analysis toolkit to 12.2 million traces: XGBoost, random forests, CNNs, template attacks, KS/AD distributional tests, PCA/t-SNE, Perceived Information, KSG mutual information, and MAD-based SNR — over 150 individual analyses across 2 platforms, 2 harness types, 5 compiler levels, 2 library versions, raw and aggregated granularities, and 9 synthetic effect sizes (full matrix in supplementary materials).

**Zero exploitable signal.** Every technique performed at or below random guessing. XGBoost achieves 50.2% on binary key-bit classification (majority baseline: 50.0%). KSG mutual information returns 0.000 bits (p = 1.0). Perceived Information is negative for all targets. At the single-trace level (100K unaggregated measurements), Cohen's d = 0.0003 for sk_lsb (Cohen's d measures effect size as the difference in means divided by pooled standard deviation; d < 0.2 is conventionally "small"). The null result holds at every granularity — aggregated summaries, raw traces, and cross-platform — ruling out aggregation masking. Higher-order analysis is inapplicable to scalar timing (one value per execution; no second sample to combine).

### The Positive Control

A negative result is only meaningful if the apparatus can detect a positive. We built the same measurement pipeline against liboqs v0.9.0, a version vulnerable to KyberSlash — a known timing side-channel where the decapsulation routine performs a variable-time division operation that leaks information about the secret key.

The results are unambiguous. On vulnerable code, our XGBoost classifier achieves +3.8% accuracy lift over random guessing. On the patched code (v0.15.0), the same classifier achieves +0.5% — consistent with statistical noise. For valid/invalid ciphertext classification (a simpler binary task), the classifier achieves 100% accuracy on both vulnerable and patched versions, confirming that the pipeline can detect input-dependent timing leakage regardless of whether secret-dependent leakage is present.

Our apparatus provably detects both secret-dependent and input-dependent timing leakage when they exist. The null result on patched ML-KEM is not a measurement failure. It is a measurement. Our pipeline's detection floor is d ≈ 0.275; effects below d ≈ 0.1 are below all detection mechanisms and unexploitable via userspace timing (full sensitivity characterization in Section 4).

**Information-theoretic confirmation.** Six independent methods — Perceived Information (negative for all targets), KSG MI (0.000 bits, p = 1.0), MAD-based SNR (zero), Winsorized SNR (zero), and vertical scaling analysis (flat accuracy curves at 15x predicted minimum sample) — all converge: zero extractable bits. Methodology details are in Appendix B. The TVLA result of |t| = 62.49 reports a signal that, by every other information-theoretic measure, does not exist — and that vanishes (|t| = 0.58) when collection is interleaved.

---

## Section 3: The Root Cause

If TVLA reports significant leakage and no attack can exploit it, the question is not "where is the leakage hiding?" but "what is TVLA actually detecting?"

### The Complete Picture

We isolated two independent confound sources by varying two experimental dimensions — collection order (sequential vs. interleaved) and harness design (asymmetric vs. symmetric) — across both platforms. Each cell in the following table shows the Welch |t| statistic:

|  | Sequential Asymmetric | Sequential Symmetric | Interleaved Asymmetric | Interleaved Symmetric |
|--|---|---|---|---|
| **Apple Silicon** | 3.00 (PASS) | 62.49 (FAIL) | 0.99 (PASS) | 0.58 (PASS) |
| **Intel x86** | 5.35 (FAIL) | 6.70 (FAIL) | 8.10 (FAIL) | 1.65 (PASS) |

Reading across columns isolates the effect of each fix:
- **Symmetric harness** (columns 1→2): Eliminates cache pollution but reveals temporal drift. On Apple, |t| *increases* from 3.00 to 62.49 because cache pollution was masking drift.
- **Interleaved collection** (columns 2→4): Eliminates temporal drift. On both platforms, |t| drops to non-significant (0.58 and 1.65).
- **Intel asymmetric interleaved** (column 3): Still fails (|t| = 8.10), confirming that live keygen+encaps cache pollution is a real secondary confound on Intel — independent of temporal drift.
- **Both fixes combined** (column 4): Symmetric + interleaved passes on both platforms. This is the definitive result.

Two confound sources produce this pattern. Here's how we isolated each one.

### The Harness Asymmetry Problem

Our TVLA harness — like virtually every software TVLA harness we have encountered in open-source PQC testing — executes different code paths in fixed vs random modes. In fixed mode, a single (ciphertext, secret key) pair is generated once during setup, and each iteration simply times `decaps()`. In random mode, each iteration generates a fresh keypair via `keygen()` and a fresh ciphertext via `encaps()` before timing `decaps()`. Although `keygen()` and `encaps()` execute *outside* the timing window, they pollute cache lines, branch predictor state, and prefetcher history before the timed operation begins.

This asymmetry is not a bug in our harness — it is the natural implementation of ISO 17825's fixed-vs-random protocol for software evaluations. The standard requires "random" inputs; generating them per-iteration is the obvious approach and the one most developers and evaluation labs adopt. A fully symmetric harness would pre-generate all random inputs into a memory array and index into it, ensuring identical cache footprints across both modes. We implemented this symmetric design (below) and found it eliminates the harness asymmetry confound — but sequential collection still fails due to temporal drift. We suspect most evaluation labs have not implemented symmetric harnesses, meaning they are observing false positives from both sources simultaneously.

### The Temporal Drift Confound

Even with a perfectly symmetric harness, TVLA fails catastrophically when fixed and random measurements are collected in separate sequential blocks. We initially attributed this to an architectural confound — adaptive microarchitecture responding differently to repeated vs. novel inputs. Our interleaved control experiment (below) disproves this attribution: when fixed and random measurements alternate within a single collection run, TVLA passes on both platforms. The confound is temporal drift between sequential collection blocks, not the CPU's response to data content.

In sequential collection, the fixed block runs first (e.g., 50,000 consecutive decapsulations on the same input), then the random block runs (50,000 decapsulations on distinct inputs). Between these blocks — and during each block — system state evolves through multiple mechanisms: thermal throttling changes CPU clock frequency as the die heats during sustained computation; the OS scheduler's CFS (Linux) or Grand Central Dispatch (macOS) quantum boundaries redistribute background work; DVFS (Dynamic Voltage and Frequency Scaling — the hardware mechanism that adjusts CPU clock speed and voltage based on workload) shifts power states; and memory controller scheduling changes as DRAM temperature increases. On our Apple Silicon test platform, a 50K-trace collection block runs for approximately 30 seconds — long enough for thermal management to trigger multiple P-state transitions. These environmental changes are systematic (not random noise) and correlate perfectly with group assignment because all fixed measurements occupy one contiguous time window and all random measurements occupy another.

### Apple Silicon: Sequential vs. Interleaved

The symmetric harness pre-generates all inputs so both modes execute identical code paths (array index → decaps → record timing). Despite this, sequential collection fails catastrophically:

| Harness (Sequential) | |t| | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|----------------|--------------------|--------------------|-------------|
| Asymmetric | 3.00 | 0.16x | 523.0 | 525.4 | **PASS** |
| Symmetric | 62.49 | 7.71x | 594.5 | 532.6 | **FAIL** |

The asymmetric harness passes because keygen+encaps cache pollution in random mode adds noise that masks the drift. We initially attributed the symmetric failure to Apple's Data-Dependent Prefetcher (DMP) responding differently to repeated vs. novel data.

The interleaved control disproves this. We alternate fixed[i] and random[i] within a single loop so both groups experience identical environmental conditions:

| Harness (Interleaved) | |t| | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|----------------|--------------------|--------------------|-------------|
| Asymmetric | 0.99 | 0.10x | 508.0 | 513.3 | **PASS** |
| Symmetric | 0.58 | 0.95x | 555.3 | 551.4 | **PASS** |

The t-statistic drops from 62.49 to 0.58 — a 100x reduction — solely by eliminating temporal drift. If the confound were DMP-driven, it would persist under interleaved collection: the DMP responds to data *content*, not collection order. The fact that interleaving eliminates the signal rules out any data-content-dependent mechanism and confirms temporal drift as the sole cause. Pairwise decomposition on the sequential data confirms: every t-test grouped by actual secret-key properties returns non-significant results.

### Apple Silicon: Compiler Optimization Level Independence

We recompiled the symmetric harness at five optimization levels (50,000 traces per mode):

| Flag | |t| | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|------|-----|----------------|--------------------|--------------------|-------------|
| -O0 | 10.40 | 0.07x | 559.9 | 544.4 | **FAIL** |
| -O1 | 8.71 | 0.60x | 530.3 | 536.8 | **FAIL** |
| -O2 | 19.07 | 0.02x | 535.9 | 605.0 | **FAIL** |
| -O3 | 5.27 | 1.10x | 741.9 | 658.9 | **FAIL** |
| -Os | 1.73 | 30.89x | 1529.0 | 995.4 | **PASS**\* |
| -Os (rerun) | 11.47 | 466x | — | — | **FAIL** |

\* Rerun fails; see text. All five optimization levels exhibit the confound.

All five levels fail TVLA. The variance ratio varies dramatically (0.02x to 466x), but the confound's *presence* is consistent — confirming it originates in temporal drift, not compiler-specific instruction scheduling. The -Os run-to-run instability (|t| = 1.73 then 11.47, same binary, same hardware) is itself diagnostic: real cryptographic leakage produces consistent results; environmental drift does not. Binary analysis confirms the ML-KEM decapsulation code is identical across flags (liboqs is statically linked). Levene's test on the -Os data confirms the variance asymmetry is significant (F = 128.25, p = 1.03 × 10⁻²⁹).

### Intel x86: Same Pattern, Same Fix

Intel Xeon shows the same confound:

| Harness (Sequential) | |t| | Variance Ratio | TVLA Verdict |
|---------|-----|----------------|-------------|
| Asymmetric | 5.35 | 1.84x | **FAIL** |
| Symmetric | 6.70 | 0.43x | **FAIL** |

| Harness (Interleaved) | |t| | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|-------|-------|-------------|
| Asymmetric | 8.10 | 58,172 | 58,430 | **FAIL** |
| Symmetric | 1.65 | 183,685 | 204,168 | **PASS** |

Symmetric interleaved passes (|t| = 1.65). The asymmetric interleaved failure (|t| = 8.10) confirms harness asymmetry — live keygen+encaps polluting cache state — is a real but secondary confound on Intel, independent of temporal drift. When both confounds are eliminated, TVLA passes. The cross-platform replication rules out any platform-specific architectural explanation.

### The Proof: Pairwise Decomposition

The definitive proof that the TVLA signal is not secret-dependent comes from pairwise decomposition. Instead of comparing fixed-vs-random (which confounds input repetition with secret identity), we compare timing distributions grouped by actual secret properties — individual key bits, Hamming weight classes, key byte values — while holding the fixed-vs-random structure constant.

When traces are split by actual secret properties instead of by TVLA group assignment, the distributions are identical. Every pairwise t-test, every distributional comparison, every classifier trained on actual secret labels performs at chance. The structure that TVLA detects vanishes entirely when the comparison is reframed around the secret rather than around input repetition.

The leakage is input-dependent, not secret-dependent. TVLA cannot distinguish between the two. This is not a subtle statistical argument — it is a complete decomposition that isolates the confound and shows that it accounts for 100% of the TVLA signal.

---

## Section 4: The Fix

The finding does not mean TVLA is useless. It means TVLA is incomplete. A TVLA pass is still meaningful — if the distributions are indistinguishable, there is no leakage of any kind to worry about. The problem is TVLA failures on modern hardware, which require a second stage of analysis to determine whether the detected signal is exploitable.

### The Two-Stage Evaluation Protocol

We propose a two-stage protocol for non-invasive side-channel evaluation of cryptographic implementations on general-purpose processors:

**Stage 1: Standard TVLA.** Run the fixed-vs-random Welch's t-test exactly as specified in ISO 17825. If |t| <= 4.5, the implementation passes. No further analysis required. A TVLA pass remains a valid certificate of conformance.

**Stage 2: Confound Triage.** If |t| > 4.5, do not immediately fail the implementation. Instead, run pairwise secret-group decomposition: split the collected traces by actual secret key properties (individual bits, byte values, Hamming weight — the number of 1-bits in the key) and recompute the t-test for each pairwise comparison. Compute permutation-validated mutual information between timing measurements and secret key material.

The decision logic is clear:
- If pairwise decomposition shows **no significant differences** between secret groups AND mutual information is **zero** (within permutation confidence): the TVLA failure is a **false positive** caused by temporal-drift confound. The implementation **passes**.
- If pairwise decomposition **detects significant differences** between secret groups OR mutual information is **positive**: the leakage is **real and secret-dependent**. The implementation **fails**.

This protocol preserves TVLA's role as a conservative first-pass screen while eliminating false positives that arise from temporal-drift confounds in sequential collection. It adds cost only when TVLA fails — which, with sequential collection on modern hardware, will be most of the time.

### The Tool: sca-triage

We release **sca-triage**, an open-source Python tool implementing the triage protocol (`pip install sca-triage`):

```bash
sca-triage analyze --timing-data traces.npz --secret-labels keys.csv \
    --targets sk_lsb,sk_byte_0,sk_hw --permutation-shuffles 10000
```

The tool runs three stages: (1) standard TVLA (Welch's t-test, pass/fail at |t| = 4.5), (2) pairwise secret-group decomposition (regroups traces by key bits, byte values, Hamming weight; runs t-tests within each partition), and (3) KSG mutual information validated by permutation test. Verdict: if TVLA fails but all pairwise tests are non-significant *and* MI is zero within the permutation confidence interval → FALSE_POSITIVE. Output includes JSON with full statistics suitable for CMVP submission.

**Worked example.** On our Apple Silicon asymmetric harness data (50,000 traces, |t| = 8.42 — representative of what evaluation labs encounter; symmetric data produces the same verdict at |t| = 62.49), the full pipeline (`python scripts/dudect_comparison.py`) produces:

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

Pairwise decomposition tests 13 secret-key properties; all return non-significant after Holm-Bonferroni correction. KSG MI provides a model-free backstop capturing nonlinear dependencies that pairwise tests might miss. A FALSE_POSITIVE verdict guarantees no secret-dependent leakage above the d ≈ 0.275 macro-timing noise floor — the limit of userspace exploitability. Below this threshold, hardware EM probing is required.

**Sensitivity and detection floors.** We validated detection capability by injecting synthetic timing leaks at Cohen's d = {0.005–1.0} across 20 trials per effect size: 90% detection at d = 0.3, 100% at d = 0.5. The per-experiment pipeline floor is d ≈ 0.275 (80% detection). The pairwise t-test floor alone is d = 0.398 (454 cycles at 80% power); the ML classification floor is d ≈ 0.85. The multi-method pipeline is more sensitive than any single test. KyberSlash (d = 0.094) falls below all per-experiment floors but was detected through a different mechanism — population-level aggregation across 500 keys, where XGBoost learns weak but consistent cross-key patterns (+3.8% lift). The per-experiment floor (d ≈ 0.275) and population-level detection (d = 0.094) characterize complementary mechanisms, not the same pathway. Effects below d ≈ 0.1 are below both and unexploitable via userspace macro-timing. Full triage completes in under 30 seconds on 50K traces.

### Why the Welch's t-Test Alone Is Insufficient

The core statistical test in both TVLA and dudect is a Welch's t-test comparing two timing distributions. dudect solves the temporal-drift problem by interleaving its measurement loop — if you run the actual dudect binary, it will not produce false positives from drift. But dudect does not protect against harness asymmetry (cache pollution from live keygen+encaps in random mode), and critically, FIPS evaluation labs running ISO 17825 do not use dudect's interleaved collection — they collect sequentially.

The question sca-triage answers is different from what dudect or TVLA answer. The Welch's t-test tells you whether two distributions differ. It cannot tell you *why* they differ — temporal drift, harness asymmetry, or real leakage all produce the same FAIL. sca-triage's pairwise decomposition and MI stages provide the missing diagnostic:

| Analysis | Patched v0.15.0 (no real leak) | Vulnerable v0.9.0 (KyberSlash) |
|------|------|------|
| **Welch's t-test (sequential data)** | |t| = 8.42 → FAIL | |t| = 1.04 → Underpowered |
| **sca-triage (three-stage)** | FALSE_POSITIVE (pairwise d=0.0003, MI=0.0 bits) | REAL_LEAKAGE (XGBoost 56.6% vs 52.8% chance) |

On the patched version, the t-test reports leakage that does not exist. On the vulnerable version, it is underpowered at 25K traces. sca-triage correctly triages both cases — identifying the false positive and detecting the real vulnerability via cross-key ML classification.

**Repository:** [https://github.com/asdfghjkltygh/m-series-pqc-timing-leak/tree/main/sca-triage](https://github.com/asdfghjkltygh/m-series-pqc-timing-leak/tree/main/sca-triage)

### Recommendations for Standards Bodies

1. **Mandate interleaved collection.** ISO 17825's implicit sequential protocol introduces temporal drift that produces false positives on general-purpose processors. Mandating interleaved collection — or requiring pairwise decomposition as a mandatory follow-up to any TVLA failure — eliminates the most common source of false positives.

2. **Acknowledge the confound in FIPS 140-3 guidance.** NIST's Implementation Guidance should describe the temporal-drift confound, its root cause, and available mitigations. Without this, evaluation labs independently discover the problem and reach inconsistent conclusions.

3. **Adopt pairwise decomposition in lab SOPs.** The marginal cost is small — the traces are already collected — and pairwise analysis provides a safety net even when interleaved collection is not feasible. Together, interleaving and pairwise decomposition eliminate the most common source of false positives on modern hardware.

---

## Section 5: Impact and Implications

### What This Means for PQC Migration

The bottom line for organizations deploying post-quantum cryptography: **ML-KEM deployment should not be delayed based on TVLA-only evaluations.** The TVLA failures reported on Apple Silicon and Intel x86 are false positives caused by temporal drift in sequential data collection, not by weaknesses in the algorithm or its implementation. Interleaved collection eliminates the confound entirely on both platforms.

**Threat model scope.** We do not claim liboqs is perfectly constant-time. Our strict per-key detection floor is d ≈ 0.275 (454 cycles) — no secret-dependent macro-timing leak exceeds this threshold for any individual key. Vulnerabilities affecting multiple keys (like KyberSlash) are detected well below this floor (d = 0.094) by aggregating weak signals across the 500-key population: sca-triage's ML classifiers learn consistent cross-key patterns that per-key tests miss. These are complementary detection mechanisms — the per-key floor is the strict upper bound on undetected leakage for any single key, while population-level aggregation extends sensitivity to smaller effects that are consistent across keys.

An attacker with kernel-level performance counter access could achieve cycle-accurate resolution, potentially detecting sub-threshold leakage. However, such an attacker already has ring-0 execution, placing them outside the remote/userspace threat model that FIPS 140-3 non-invasive evaluation targets.

The liboqs KyberSlash fix (v0.15.0 and later) is effective. Our positive control confirms that the known timing vulnerability in pre-patch versions is detectable and that the patch eliminates it. Organizations integrating liboqs at current versions can proceed with confidence that the implementation is timing-safe against remote and userspace adversaries constrained by OS scheduling noise and standard timer resolution.

For organizations already in FIPS evaluation: if your lab has reported a TVLA failure on ML-KEM running on Apple Silicon or Intel hardware, request a Stage 2 analysis. Point evaluators to this paper and the sca-triage tool. The TVLA failure is real in the statistical sense, but it does not represent exploitable leakage.

**Denial of Certification.** The temporal-drift confound implies a co-tenancy attack: an adversary on shared infrastructure could amplify drift between TVLA measurement blocks to inflate a competitor's |t| above 4.5, blocking their FIPS certification. We have not demonstrated this experimentally, but the mechanism is plausible given sequential collection alone produces |t| up to 62x above the threshold. Interleaved collection or pairwise decomposition would defeat such an attack.

### What This Means for Other PQC Algorithms

We demonstrate the confound for ML-KEM. Because the root cause is methodological — sequential collection introducing temporal drift between measurement groups — it is expected to affect any algorithm evaluated with sequential TVLA on any hardware where system state evolves during collection. This includes ML-DSA (Dilithium), SLH-DSA (SPHINCS+), BIKE, and HQC. This is a testable prediction: replicating the interleaved vs. sequential experiment with each algorithm's entry point would confirm or refute it. We have not yet performed this cross-algorithm validation; it is immediate future work. Pending that confirmation, evaluation labs should treat TVLA failures on any PQC algorithm collected sequentially as potentially confounded and either switch to interleaved collection or apply pairwise decomposition before concluding the leakage is real.

### Broader Implications

TVLA was designed for embedded hardware — smartcards, FPGAs, dedicated coprocessors — where timing is largely deterministic and trace collection completes before environmental drift matters. On general-purpose processors, collection runs take minutes to hours. System state evolves continuously, and sequential collection creates a perfect confound: fixed measurements occupy one time window, random measurements occupy another, and any drift between them becomes a systematic group difference that TVLA interprets as leakage.

The gap between "TVLA-detectable" and "exploitable" is wider on modern processors than FIPS evaluation practice assumes. A |t| of 62.49 on Apple Silicon contains zero bits of secret information and vanishes (|t| = 0.58) when collection is interleaved. TVLA's methodology assumes temporal stationarity between measurement groups — an assumption that fails on any system where environmental conditions evolve during collection. Side-channel evaluation standards must evolve alongside the hardware they evaluate.

### Limitations and Roadmap

Each limitation below includes what it would take to close the gap and why it does not undermine the current findings.

**Cross-platform interleaved control.** The interleaved harness experiment confirms the confound is temporal drift from sequential collection on both Apple Silicon (sequential |t| = 62.49 → interleaved |t| = 0.58) and Intel x86 (sequential |t| = 6.70 → interleaved |t| = 1.65). The cross-platform replication eliminates platform-specific explanations. See Section 3.

**Temporal drift mechanism is uncharacterized.** We demonstrate that sequential collection introduces temporal drift sufficient to produce catastrophic TVLA failures, but we have not isolated the specific physical mechanism (thermal drift, OS scheduling, power state transitions, etc.). *To close:* instrument collection runs with per-block thermal readings, CPU frequency logs, and OS scheduling counters to identify the dominant drift source. *Why the current findings stand:* the interleaved control proves temporal drift is the cause regardless of which physical mechanism drives it — the fix (interleaved collection or pairwise decomposition) is mechanism-agnostic.

**Compiler optimization levels.** The sequential symmetric harness fails TVLA at all five tested optimization levels (-O0 through -O3 and -Os). Initial -Os results showed run-to-run variability (|t| ranging from 1.73 to 11.47); Levene's test confirms the variance confound is present even when Welch's t happens to fall below threshold. Binary analysis confirms identical instruction counts across flags. The confound is not compiler-dependent. See Section 3.

**ML-KEM only.** Cross-algorithm validation (ML-DSA, SLH-DSA, BIKE, HQC) has not been performed. *To close:* replicate the symmetric harness experiment with each algorithm's decapsulation/signing entry point. *Why the current findings stand:* the confound is methodological (sequential collection introducing temporal drift), not algorithm-specific — but empirical confirmation across algorithms would strengthen the generalization claim.

**No NTT-internal intermediate targets.** We tested key-level and message-level properties but not butterfly outputs, Montgomery reduction intermediates, or CBD sampling. *To close:* instrument liboqs NTT internals and collect per-operation traces. *Why the current findings stand:* our raw-trace analysis bounds any per-execution timing signal at d < 0.001, constraining intermediate-value leakage — any NTT-internal dependency would need to propagate through hundreds of operations to affect macro-timing.

**Detection floor at d ≈ 0.275.** Effects below d ≈ 0.1 are below both per-experiment and population-level detection mechanisms. *To close:* complement sca-triage with dedicated profiled attacks or EM-based measurement for higher-assurance evaluations. *Why the current findings stand:* effects at d < 0.1 require >10,000 traces per key to detect and are unexploitable via userspace macro-timing within the FIPS 140-3 non-invasive threat model.

**ISO 17825:2024 untested.** The 2024 revision introduced percentile-based timing analysis and updated sample size requirements. We tested against the Goodwill (2011) methodology as widely implemented by CMVP labs. *To close:* obtain the 2024 standard and replicate. If it addresses the confound, our case strengthens (confirming the problem was recognized). If it does not, our triage protocol fills the gap.

---

## Appendix A: Full Experiment Results

The complete experiment matrix is organized into five categories:

**Classification experiments** — binary and multi-class classification of secret key material from timing traces. Columns: experiment ID, model (XGBoost, Random Forest, CNN, Logistic Regression), feature set, target variable (key bit, key byte, Hamming weight), accuracy, p-value vs. majority baseline, majority baseline, verdict (PASS/FAIL/INCONCLUSIVE).

**Regression experiments** — continuous prediction of secret key bytes and derived quantities. Columns: experiment ID, model, feature set, target, MSE, R-squared, baseline MSE (mean predictor), verdict.

**Template attack experiments** — Gaussian profiling attacks with maximum-likelihood classification. Columns: experiment ID, profiling traces, attack traces, number of classes, success rate, guessing entropy, random baseline, verdict.

**Unsupervised experiments** — PCA, t-SNE, and clustering analysis for latent structure discovery. Columns: experiment ID, method, number of components/clusters, explained variance, silhouette score, visual separation (Y/N), verdict.

**Information-theoretic experiments** — Perceived Information, KSG MI, MAD-SNR, Winsorized SNR, vertical scaling analysis. Columns: experiment ID, metric, value, permutation p-value, confidence interval, verdict.

Full tables are available in the supplementary materials repository. Each experiment includes reproducibility metadata: random seed, train/test split, hyperparameter configuration, and runtime.

---

## Appendix B: Information-Theoretic Methodology

**Perceived Information (PI).** Defined as:

PI = H(Y) - CE(Y | X)

where H(Y) is the entropy of the secret target variable Y and CE(Y | X) is the cross-entropy of the best-performing classifier's predicted distribution given timing observations X. When PI is negative, the classifier performs worse than a coin flip — the observations contain less information about the secret than the prior. We compute CE using calibrated XGBoost posterior probabilities with 5-fold cross-validation to avoid overfitting bias.

**KSG Mutual Information.** The Kraskov-Stogbauer-Grassberger estimator computes mutual information I(X; Y) using k-nearest-neighbor distances in joint and marginal spaces. It is nonparametric and makes no distributional assumptions. We use k=5 neighbors and validate the estimate with a permutation test: I(X; Y) is recomputed 10,000 times with Y randomly shuffled. The p-value is the fraction of permuted estimates exceeding the real estimate. A p-value of 1.0 means the real estimate is at or below the median of the null distribution.

**MAD-based SNR.** Signal-to-noise ratio using Median Absolute Deviation as a robust scale estimator:

SNR = MAD(group_medians) / median(within_group_MADs)

MAD is resistant to the heavy-tailed outliers that characterize timing distributions on modern processors. We compute SNR across secret-key-byte groups and across Hamming weight classes.

**Winsorized SNR.** SNR with 5% Winsorization (top and bottom 2.5% of each group's timing distribution clamped to the corresponding percentile). This bounds the influence of outliers while preserving more distributional information than MAD.

**Permutation test methodology.** For all information-theoretic metrics, significance is assessed via permutation testing rather than parametric assumptions. The secret labels are randomly shuffled 10,000 times, the metric is recomputed for each shuffle, and the p-value is the rank of the real metric within the permuted distribution. This controls for any systematic bias in the estimator.

**Vertical scaling convergence.** We compute classifier accuracy as a function of training set size from 10% to 150% of the theoretically predicted minimum (based on the TVLA-reported effect size and Gaussian power analysis). A real signal produces a monotonically increasing accuracy curve that converges to a value above the majority baseline. A false positive produces a flat line at the baseline. All targets show flat lines.

---

## Appendix C: Measurement Apparatus

**Timer characterization.**

*CNTVCT_EL0 (Apple Silicon):* ARM generic timer counter, 24 MHz tick rate. Overhead characterization: 99.2% of back-to-back reads return zero ticks elapsed, confirming sub-tick measurement granularity. Timer is monotonic and unaffected by frequency scaling (it runs on a fixed-frequency crystal, not the CPU clock).

*RDTSC + CPUID (Intel x86):* Timestamp counter read with pipeline serialization. CPUID before RDTSC forces all prior instructions to retire, ensuring the timestamp reflects actual completion. Measured overhead: approximately 1,778 cycles per serialized read pair. TSC is invariant (constant rate regardless of frequency scaling) on all tested processors.

**Data collection protocol.**

- 500 distinct secret keys, uniformly sampled
- 50 repetitions per key per measurement condition
- Two platforms (Apple M-series, Intel Xeon)
- Two conditions per platform (fixed input, random input)
- Total: approximately 12.2 million individual timing measurements
- All measurements checksummed (SHA-256) at collection time for reproducibility
- Collection scripts automated with retry logic for thermal throttling events

**Compilation and build environment.**

*Patched build:* liboqs v0.15.0, compiled with `-O2 -march=native`, standard constant-time flags enabled. This is the current recommended production build.

*Vulnerable build:* liboqs v0.9.0, compiled with identical flags. This version contains the KyberSlash vulnerability (variable-time division in decapsulation) and serves as the positive control.

Both builds use the same ML-KEM-768 parameter set. All measurements target the `OQS_KEM_kyber_768_decaps` entry point.
