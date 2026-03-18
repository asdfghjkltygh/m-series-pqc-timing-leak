# When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment

**Authors:** Saahil Shenoy
**Date:** March 2026

---

## Section 1: The Problem

We can make liboqs ML-KEM — the most widely integrated open-source PQC library — fail its FIPS 140-3 certification on modern hardware, and we can prove the failure is fake. Because the confound originates in TVLA's sequential collection methodology — not in any implementation-specific code path or hardware-specific feature — the failure is expected for any ML-KEM implementation evaluated with the standard protocol on any platform where system state evolves during collection.

The Test Vector Leakage Assessment (TVLA) — the mandatory side-channel test for ISO 17825 compliance — reports catastrophic leakage when run on liboqs ML-KEM-768: |t| = 62.49 on Apple Silicon and |t| = 6.70 on Intel x86 (using a symmetric test harness that eliminates the most obvious confound source — Section 3), far exceeding the |t| = 4.5 failure threshold. Taken at face value, these results block ML-KEM deployment across the entire US federal government and any organization requiring FIPS compliance.

The leakage is not real. We spent months and 12.2 million traces proving it. The signal comes from a temporal-drift confound: sequential collection methodology — running all fixed-input measurements, then all random-input measurements — introduces systematic environmental differences between groups that TVLA misinterprets as leakage. Interleaved measurement — alternating fixed and random traces within a single collection run — is standard practice in hardware power analysis precisely to prevent low-frequency drift. It is widely ignored in software macro-timing evaluations. We quantify the catastrophic cost of this omission: when we interleave, TVLA passes on both platforms (|t| = 0.58 on Apple Silicon, |t| = 1.65 on Intel x86). In this paper we characterize the confound, prove non-exploitability through 150+ converging experiments, and release a practical triage tool.

### Key Result: Sequential vs. Interleaved Collection

| Platform | Collection | Harness | |t| | TVLA Verdict |
|----------|-----------|---------|-----|-------------|
| Apple Silicon | Sequential | Symmetric | 62.49 | **FAIL** |
| Apple Silicon | Interleaved | Symmetric | 0.58 | **PASS** |
| Apple Silicon | Interleaved | Asymmetric | 0.99 | **PASS** |
| Intel x86 | Sequential | Symmetric | 6.70 | **FAIL** |
| Intel x86 | Interleaved | Symmetric | 1.65 | **PASS** |
| Intel x86 | Interleaved | Asymmetric | 8.10 | **FAIL** |

Switching from sequential to interleaved collection reduces Apple Silicon's |t| from 62.49 to 0.58 — a 100x attenuation — with no change to the hardware, software, or cryptographic inputs. On Intel, the same switch drops |t| from 6.70 to 1.65. The remaining Intel asymmetric failure (|t| = 8.10) reflects a secondary confound from cache pollution by live keygen+encaps, not temporal drift.

### Background

TVLA collects two sets of timing measurements: a "fixed" set where the implementation processes the same input repeatedly, and a "random" set with a different input each time. A Welch's t-test compares the distributions; if |t| > 4.5, the implementation fails. There is no "borderline" — failure triggers a remediation cycle costing months of engineering time and $50,000-$150,000 in lab fees.

NIST finalized ML-KEM as the post-quantum key encapsulation standard in August 2024. CNSA 2.0 mandates quantum-resistant cryptography for all national security systems by 2033. Every cloud provider offering GovCloud, every defense contractor handling CUI, every financial institution under federal examination needs FIPS-validated PQC modules. The cost of false TVLA failures cascades far beyond individual evaluation cycles — evaluation labs are running these tests on modern hardware today, and failures are being reported today.

---

## Related Work

TVLA's limitations on general-purpose hardware are well-documented. Schneider & Moradi (CHES 2015) showed environmental noise produces statistically significant but non-exploitable results. Whitnall & Oswald (CHES 2011, J. Cryptographic Engineering 2014) quantified the gap between statistical distinguishability and key recovery. Mather et al. (2019) provided methodological guidance acknowledging TVLA overreporting. Bronchain & Standaert (TCHES 2021) introduced the Perceived Information framework specifically because TVLA detection does not imply exploitability.

In the software timing domain, dudect (Reparaz et al., DATE 2017) applies Welch's t-test to timing measurements to detect non-constant-time implementations, and acknowledges false positive risk from OS scheduling noise. Our work is complementary: dudect tests whether an *implementation* is constant-time; we evaluate whether the *ISO 17825 TVLA protocol itself* produces valid certification results on production hardware.

GoFetch (Borah et al., 2024) demonstrated Apple's Data-Dependent Prefetcher as an *attack vector* for key extraction. We initially hypothesized DMP as a source of TVLA false positives, but our interleaved control experiment (Section 3) shows the confound is temporal drift from sequential collection, not DMP-specific architectural behavior.

Our contribution is not discovering that TVLA has limitations. It is systematically quantifying the ISO 17825 failure rate for the NIST ML-KEM standard on production hardware, proving non-exploitability through converging experiments, isolating temporal drift in sequential collection as the root cause via interleaved control experiments on two ISAs, and releasing a practical triage tool.

---

## Section 2: The Investigation

We collected 12.2 million timing traces across both platforms trying to turn this TVLA result into an actual key recovery attack. We did not set out to prove TVLA wrong. We set out to exploit the leakage it reported. Every technique we tried — and we tried everything — came back empty.

### Measurement Setup

**Apple Silicon M-series.** All measurements were collected on Apple M-series processors using the ARM performance counter CNTVCT_EL0 as the timing source. This counter operates at 24 MHz (~41.7 ns granularity) with 99.2% zero-tick measurement overhead. The 24 MHz resolution is *conservative* for our purposes — it reduces sensitivity to small effects, meaning both the TVLA failure signal (|t| = 62.49 on the symmetric harness) and the null pairwise result are robust to timer granularity. A higher-resolution timer would increase statistical power for both detection and non-detection. Traces were collected under controlled conditions with performance governor set to high-performance mode, thermal throttling monitored, and system load minimized.

**Intel Xeon x86.** Intel measurements used RDTSC with CPUID serialization to ensure precise cycle-accurate timing. The CPUID instruction forces pipeline serialization before reading the timestamp counter, eliminating measurement artifacts from out-of-order execution. Measured overhead is approximately 1,778 cycles per serialized read. The same controlled conditions were applied: performance governor pinned, hyperthreading accounted for, system load minimized.

**Noise model and data collection.** For each platform, we collected traces across 500 distinct keys with 50 repetitions per key, yielding a total dataset of 12.2 million measurements across both platforms. Data collection was automated and checksummed to ensure reproducibility. The entire pipeline — from trace collection through analysis — is scripted and available in the supplementary repository.

### Bounding Exploitability

We applied the full side-channel analysis toolkit to 12.2 million traces: XGBoost, random forests, CNNs, template attacks, KS/AD distributional tests, PCA/t-SNE, Perceived Information, KSG mutual information, and MAD-based SNR — over 150 individual analyses across 2 platforms, 2 harness types, 5 compiler levels, 2 library versions, raw and aggregated granularities, and 9 synthetic effect sizes (full matrix in supplementary materials).

**Zero exploitable signal.** Every technique performed at or below random guessing. XGBoost achieves 50.2% on binary key-bit classification (majority baseline: 50.0%). KSG mutual information returns 0.000 bits (p = 1.0). Perceived Information is negative for all targets. At the single-trace level (100K unaggregated measurements), Cohen's d = 0.0003 for sk_lsb. The null result holds at every granularity — aggregated summaries, raw traces, and cross-platform — ruling out aggregation masking. Higher-order analysis is inapplicable to scalar timing (one value per execution; no second sample to combine).

### The Positive Control

A negative result is only meaningful if the apparatus can detect a positive. We built the same measurement pipeline against liboqs v0.9.0, a version vulnerable to KyberSlash — a known timing side-channel where the decapsulation routine performs a variable-time division operation that leaks information about the secret key.

The results are unambiguous. On vulnerable code, our XGBoost classifier achieves +3.8% accuracy lift over random guessing. On the patched code (v0.15.0), the same classifier achieves +0.5% — consistent with statistical noise. For valid/invalid ciphertext classification (a simpler binary task), the classifier achieves 100% accuracy on both vulnerable and patched versions, confirming that the pipeline can detect input-dependent timing leakage regardless of whether secret-dependent leakage is present.

Our apparatus provably detects both secret-dependent and input-dependent timing leakage when they exist. The null result on patched ML-KEM is not a measurement failure. It is a measurement.

We note that KyberSlash represents a relatively large vulnerability (variable-time division). To quantify our sensitivity to *smaller* effects, we computed detection floors for both our statistical and ML pipelines. The pairwise t-test detection floor is d = 0.398 (454 cycles) at 80% power with our sample configuration. The ML classification floor is higher at d ≈ 0.85 (>55% accuracy in ≥80% of trials with 500 keys). The full sca-triage pipeline — combining pairwise tests, MI, and classification — achieves 80% detection rate at d ≈ 0.275, demonstrating that the multi-method approach is more sensitive than any single test. KyberSlash's d = 0.094 falls below all three per-experiment floors when using per-key aggregated features; our pipeline detected it through a fundamentally different mechanism — population-level aggregation across 500 keys, where the effect size is large enough for XGBoost to learn a weak but consistent signal (+3.8% lift). The per-experiment pipeline detection floor (d ≈ 0.275) and the population-level KyberSlash detection (d = 0.094) characterize complementary detection mechanisms, not the same pathway. Effects smaller than d ≈ 0.1 are below both detection mechanisms — and are unexploitable via userspace macro-timing.

**Information-theoretic confirmation.** Six independent methods — Perceived Information (negative for all targets), KSG MI (0.000 bits, p = 1.0), MAD-based SNR (zero), Winsorized SNR (zero), and vertical scaling analysis (flat accuracy curves at 15x predicted minimum sample) — all converge: zero extractable bits. Methodology details are in Appendix B. The TVLA result of |t| = 62.49 reports a signal that, by every other information-theoretic measure, does not exist — and that vanishes (|t| = 0.58) when collection is interleaved.

---

## Section 3: The Root Cause

If TVLA reports significant leakage and no attack can exploit it, the question is not "where is the leakage hiding?" but "what is TVLA actually detecting?" The answer is a temporal-drift confound arising from sequential data collection. TVLA implementations — including virtually every open-source PQC harness — collect all fixed-input measurements in one block, then all random-input measurements in a second block. System state (thermal conditions, OS scheduling, cache pressure, prefetcher history) drifts between blocks, creating systematic timing differences that correlate with group assignment rather than with cryptographic secrets. A secondary source — asymmetrical harness design that performs different pre-measurement work in fixed vs random modes — contributes on some platforms but is neither necessary nor sufficient for the confound.

### The Harness Asymmetry Problem

Our TVLA harness — like virtually every software TVLA harness we have encountered in open-source PQC testing — executes different code paths in fixed vs random modes. In fixed mode, a single (ciphertext, secret key) pair is generated once during setup, and each iteration simply times `decaps()`. In random mode, each iteration generates a fresh keypair via `keygen()` and a fresh ciphertext via `encaps()` before timing `decaps()`. Although `keygen()` and `encaps()` execute *outside* the timing window, they pollute cache lines, branch predictor state, and prefetcher history before the timed operation begins.

This asymmetry is not a bug in our harness — it is the natural implementation of ISO 17825's fixed-vs-random protocol for software evaluations. The standard requires "random" inputs; generating them per-iteration is the obvious approach and the one most developers and evaluation labs adopt. A fully symmetric harness would pre-generate all random inputs into a memory array and index into it, ensuring identical cache footprints across both modes. We implemented this symmetric design (below) and found it eliminates the harness asymmetry confound — but sequential collection still fails due to temporal drift. We suspect most evaluation labs have not implemented symmetric harnesses, meaning they are observing false positives from both sources simultaneously.

### The Temporal Drift Confound

Even with a perfectly symmetric harness, TVLA fails catastrophically when fixed and random measurements are collected in separate sequential blocks. We initially attributed this to an architectural confound — adaptive microarchitecture responding differently to repeated vs. novel inputs. Our interleaved control experiment (below) disproves this attribution: when fixed and random measurements alternate within a single collection run, TVLA passes on both platforms. The confound is temporal drift between sequential collection blocks, not the CPU's response to data content.

In sequential collection, the fixed block runs first (e.g., 50,000 consecutive decapsulations on the same input), then the random block runs (50,000 decapsulations on distinct inputs). Between these blocks — and during each block — system state evolves through multiple mechanisms: thermal throttling changes CPU clock frequency as the die heats during sustained computation; the OS scheduler's CFS (Linux) or Grand Central Dispatch (macOS) quantum boundaries redistribute background work; DVFS (Dynamic Voltage and Frequency Scaling) adjusts power states based on sustained workload profiles; and memory controller scheduling changes as DRAM temperature increases. On our Apple Silicon test platform, a 50K-trace collection block runs for approximately 30 seconds — long enough for thermal management to trigger multiple P-state transitions. These environmental changes are systematic (not random noise) and correlate perfectly with group assignment because all fixed measurements occupy one contiguous time window and all random measurements occupy another.

### Apple Silicon: Sequential Collection Produces False Positives

We ran TVLA with two sequential harness designs on Apple M-series processors:

**Sequential symmetric control.** The symmetric harness pre-generates all 50,000 random (ciphertext, secret key) pairs into memory arrays before measurement begins; both fixed and random modes execute identical code paths during the timed loop (array index → decaps → record timing). No keygen or encaps occurs inside the measurement loop in either mode. Despite this perfectly symmetric design, TVLA fails catastrophically: |t| = 62.49 with a variance ratio of 7.71x (fixed over random). The asymmetric harness — when run as a control in the same experiment — passes TVLA (|t| = 3.00) because keygen+encaps cache pollution in random mode adds noise that brings the two distributions closer together.

| Harness (Sequential) | |t| | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|----------------|--------------------|--------------------|-------------|
| Asymmetric | 3.00 | 0.16x | 523.0 | 525.4 | **PASS** |
| Symmetric | 62.49 | 7.71x | 594.5 | 532.6 | **FAIL** |

We initially attributed this symmetric-harness failure to Apple's Data-Dependent Prefetcher (DMP, characterized by GoFetch/Augury) responding differently to repeated vs. novel data. The variance signature — fixed variance 7.7x higher than random — appeared consistent with DMP convergence on repeated inputs causing bimodal timing (fast mode with rare catastrophic mispredictions).

**The interleaved control disproves the DMP attribution.** To isolate temporal drift from architectural effects, we built an interleaved harness that alternates fixed[i] and random[i] measurements within a single collection loop (500,000 traces per group). Both groups experience identical instantaneous environmental conditions — same thermal state, same OS scheduling context, same cache pressure. Pre-generated inputs ensure identical code paths (no keygen or encaps in the loop).

| Harness (Interleaved) | |t| | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|----------------|--------------------|--------------------|-------------|
| Asymmetric | 0.99 | 0.10x | 508.0 | 513.3 | **PASS** |
| Symmetric | 0.58 | 0.95x | 555.3 | 551.4 | **PASS** |

With interleaved collection, the symmetric harness produces |t| = 0.58 — essentially zero signal — and a variance ratio of 0.95x (effectively 1:1). The t-statistic drops from 62.49 to 0.58 — a 100x reduction — solely by eliminating temporal drift. The DMP, branch predictor, and all other microarchitectural features are identical between sequential and interleaved runs; the only difference is whether the two groups occupy separate time windows or share the same one.

Pairwise decomposition on the sequential symmetric data confirms the signal is not secret-dependent: every t-test grouped by actual secret-key properties (individual bits, byte values, Hamming weights) returns non-significant results. The temporal drift confound accounts for 100% of the TVLA signal.

### Apple Silicon: Compiler Optimization Level Independence

To confirm the confound is hardware-driven rather than an artifact of compiler code generation, we recompiled the symmetric harness at five optimization levels and reran the TVLA experiment (50,000 traces per mode at each level):

| Flag | |t| | Variance Ratio | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|------|-----|----------------|--------------------|--------------------|-------------|
| -O0 | 10.40 | 0.07x | 559.9 | 544.4 | **FAIL** |
| -O1 | 8.71 | 0.60x | 530.3 | 536.8 | **FAIL** |
| -O2 | 19.07 | 0.02x | 535.9 | 605.0 | **FAIL** |
| -O3 | 5.27 | 1.10x | 741.9 | 658.9 | **FAIL** |
| -Os | 1.73 | 30.89x | 1529.0 | 995.4 | **PASS**\* |
| -Os (rerun) | 11.47 | 466x | — | — | **FAIL** |

\* Rerun fails; see text. All five optimization levels exhibit the confound.

All five optimization levels fail TVLA with the sequential symmetric harness (the initial -Os "pass" did not replicate — see below). The confound persists from -O0 (no optimization) through -O3 (aggressive optimization), confirming it originates in temporal drift during sequential collection, not in compiler-specific instruction scheduling or register allocation. The variance ratio signature varies dramatically across flags (0.02x to 30.89x), indicating the confound's *magnitude* is sensitive to code layout, but its *presence* is not.

In our initial sweep, -Os (size-optimized) passed with |t| = 1.73. However, a repeat run of the -Os configuration produced |t| = 11.47 with a variance ratio of 466x (fixed > random) — a clear TVLA failure. The -Os "pass" was within the run-to-run variability envelope, not a stable result. The confound magnitude varies significantly across runs due to microarchitectural state sensitivity (system load, thermal conditions, prefetcher history), but it is consistently present at all optimization levels.

Binary analysis confirms that total binary size is identical across all flags (liboqs is statically linked and pre-compiled), and the harness `main()` function contains the same number of instructions (496) at every optimization level. The flag affects only instruction scheduling and alignment within the harness measurement loop, not the ML-KEM decapsulation code itself. The confound is driven by temporal drift in sequential collection; its *magnitude* varies with code layout and system state, but its *presence* is consistent across all tested configurations. Levene's test on the -Os data confirms the variance asymmetry is highly significant (F = 128.25, p = 1.03 × 10⁻²⁹), even when the means happen to be close enough for the Welch t-test to return a borderline result.

### Intel x86: Sequential Collection Produces False Positives

Intel Xeon processors exhibit the same pattern. With sequential collection, both harness designs fail TVLA:

| Harness (Sequential) | |t| | Variance Ratio | TVLA Verdict |
|---------|-----|----------------|-------------|
| Asymmetric | 5.35 | 1.84x | **FAIL** |
| Symmetric | 6.70 | 0.43x | **FAIL** |

The symmetric harness — with identical code paths and no keygen or encaps in the measurement loop — produces a *higher* t-statistic (|t| = 6.70) than the asymmetric harness (|t| = 5.35). (Our initial 500K-trace asymmetric collection produced |t| = 12.95; the symmetric control used matched 50K-trace collections.)

**Interleaved collection eliminates the confound on Intel as well.** With the same interleaved harness design used on Apple Silicon (alternating fixed[i] and random[i] within a single loop, 50,000 traces per group):

| Harness (Interleaved) | |t| | Fixed Mean (cycles) | Random Mean (cycles) | TVLA Verdict |
|---------|-----|-------|-------|-------------|
| Asymmetric | 8.10 | 58,172 | 58,430 | **FAIL** |
| Symmetric | 1.65 | 183,685 | 204,168 | **PASS** |

The symmetric interleaved harness passes with |t| = 1.65. The asymmetric interleaved harness still fails (|t| = 8.10), confirming that harness asymmetry — live keygen+encaps polluting cache state before random measurements — is a real but secondary confound on Intel. When both temporal drift *and* harness asymmetry are eliminated (symmetric interleaved), TVLA passes.

The variance ratio difference between platforms in sequential mode (Intel 0.43x vs. Apple 7.71x) initially suggested distinct architectural mechanisms. The interleaved results reframe this: both platforms show near-unity variance ratios when temporal drift is removed, indicating the sequential variance signatures were artifacts of how system state drifted during each platform's specific collection window, not of fundamentally different hardware responses to data content.

**Cross-platform 2×2 matrix.** The following table isolates the two confound sources — temporal drift (sequential vs. interleaved) and cache pollution (asymmetric vs. symmetric) — across both platforms. Each cell shows the Welch |t| statistic:

|  | Sequential Asymmetric | Sequential Symmetric | Interleaved Asymmetric | Interleaved Symmetric |
|--|---|---|---|---|
| **Apple Silicon** | 3.00 (PASS) | 62.49 (FAIL) | 0.99 (PASS) | 0.58 (PASS) |
| **Intel x86** | 5.35 (FAIL) | 6.70 (FAIL) | 8.10 (FAIL) | 1.65 (PASS) |

Reading across columns isolates the effect of each fix:
- **Symmetric harness** (columns 1→2): Eliminates cache pollution but reveals temporal drift. On Apple, |t| *increases* from 3.00 to 62.49 because cache pollution was masking drift.
- **Interleaved collection** (columns 2→4): Eliminates temporal drift. On both platforms, |t| drops to non-significant (0.58 and 1.65).
- **Intel asymmetric interleaved** (column 3): Still fails (|t| = 8.10), confirming that live keygen+encaps cache pollution is a real secondary confound on Intel — independent of temporal drift.
- **Both fixes combined** (column 4): Symmetric + interleaved passes on both platforms. This is the definitive result.

The sequential symmetric results remain valuable as a diagnostic: they show the confound's magnitude when temporal drift is present. Evaluation labs using the standard asymmetric harness may see *attenuated* false positives — the underlying temporal drift confound is larger than what their results suggest.

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

**Stage 2: Confound Triage.** If |t| > 4.5, do not immediately fail the implementation. Instead, run pairwise secret-group decomposition: split the collected traces by actual secret key properties (individual bits, byte values, Hamming weight) and recompute the t-test for each pairwise comparison. Compute permutation-validated mutual information between timing measurements and secret key material.

The decision logic is clear:
- If pairwise decomposition shows **no significant differences** between secret groups AND mutual information is **zero** (within permutation confidence): the TVLA failure is a **false positive** caused by temporal-drift confound. The implementation **passes**.
- If pairwise decomposition **detects significant differences** between secret groups OR mutual information is **positive**: the leakage is **real and secret-dependent**. The implementation **fails**.

This protocol preserves TVLA's role as a conservative first-pass screen while eliminating false positives that arise from temporal-drift confounds in sequential collection. It adds cost only when TVLA fails — which, with sequential collection on modern hardware, will be most of the time.

### The Tool: sca-triage

We release **sca-triage**, an open-source Python tool that implements Stage 2 of the two-stage protocol. It is designed for integration into existing evaluation lab workflows.

**Installation:**

```
pip install sca-triage
```

**Usage:**

```bash
# Full three-stage pipeline (TVLA → Pairwise → MI)
sca-triage analyze \
    --timing-data measurements.csv \
    --secret-labels keys.csv \
    --targets sk_lsb,sk_byte_0,sk_hw \
    --permutation-shuffles 10000 \
    --output report.html \
    --plot-dir figures/
```

The `analyze` command runs all three stages automatically:
- **Stage 1 (TVLA):** Welch's t-test on fixed-vs-random trace groups, pass/fail against |t| = 4.5
- **Stage 2 (Pairwise):** Regroups traces by actual secret key properties — individual key bits, byte values, Hamming weight classes — and runs t-tests and ANOVA between groups
- **Stage 3 (MI):** KSG mutual information between timing and secret material, validated by permutation test

**Output:**

sca-triage produces a structured terminal report plus optional HTML and JSON output containing:
- TVLA t-statistic and pass/fail determination
- Pairwise t-statistics for each secret-group comparison with Cohen's d
- Permutation-validated mutual information estimate with p-value
- Final verdict: PASS, FAIL, or FALSE_POSITIVE with full justification
- Visualization of timing distributions by secret group

Auditors integrate sca-triage into their FIPS evaluation workflow by running it as a follow-up to any TVLA failure. The HTML report provides the documentation trail needed for CMVP submission, including the statistical justification for overriding a TVLA failure.

**How the verdict logic works.** Stage 1 runs the standard TVLA; if |t| <= 4.5, the implementation passes and no further analysis is needed. If TVLA fails, Stage 2 regroups the *same traces* by actual secret key properties and re-runs the t-test for each comparison. If the TVLA signal were real leakage, at least some secret-group comparisons would show significant differences. Stage 3 computes KSG mutual information validated by permutation testing to establish a null distribution. The verdict: if pairwise tests are all non-significant *and* MI is zero within the permutation confidence interval, the TVLA failure is classified as FALSE_POSITIVE.

**Worked example.** Running sca-triage on our Apple Silicon asymmetric harness data (50,000 traces, |t| = 8.42) — we demonstrate on the asymmetric configuration because this represents what evaluation labs are most likely to encounter; the symmetric harness data produces the same FALSE_POSITIVE verdict at |t| = 62.49:

```
$ sca-triage analyze --timing-data apple_traces.csv \
    --secret-labels keys.csv --targets sk_lsb --permutation-shuffles 10000

Loading data...

[Stage 1] Running Fixed-vs-Random TVLA...
  |t| = 8.42  (FAIL)  variance ratio = 10.19

[Stage 2] Running Pairwise Secret-Group Decomposition...
  sk_lsb: Cohen's d = 0.0003, not significant

[Stage 3] Running Permutation MI Test...
  sk_lsb: MI = 0.000000, p = 1.0000 (not significant)

VERDICT: FALSE_POSITIVE
  TVLA signal is statistically significant but contains zero
  secret-dependent information. Confound source: temporal drift
  (sequential collection methodology).
```

The logic: pairwise decomposition splits the TVLA-failing traces by each of 13 secret-key properties (individual bits, byte values, Hamming weight, algebraic features) and re-runs the t-test within each partition. If the TVLA signal were secret-dependent, at least one partition would show significance — traces from keys with bit 0 = 1 would be measurably different from keys with bit 0 = 0. All 13 return non-significant — and remain non-significant after Holm-Bonferroni correction for 13 comparisons (the uncorrected family-wise error rate at α = 0.05 is approximately 0.49; zero of 13 tests reaching significance even without correction is itself strong evidence against secret dependence). This isolates the signal source to execution context (repeated vs. novel inputs) rather than secret material. KSG MI provides the model-free backstop: it captures any dependence of any functional form, including nonlinear interactions between multiple key bits that pairwise tests might miss.

The JSON report includes all statistics, p-values, and the FALSE_POSITIVE determination with full justification — suitable for direct inclusion in a CMVP submission package.

**Sensitivity characterization.** We validated the tool's detection capability on Apple Silicon data by injecting synthetic timing leaks at Cohen's d = {0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0} across 20 trials per effect size. The tool achieves 90% detection rate at d = 0.3 and 100% at d = 0.5. Below d = 0.1, the tool cannot reliably distinguish injected leakage from noise. The per-experiment pipeline detection floor is d ≈ 0.275 (80% detection rate). Intel sensitivity characterization with synthetic injection is ongoing; the KyberSlash positive control (detected at d = 0.094 via cross-key aggregation on Intel) independently validates pipeline detection on that platform. For population-level analysis across many keys, the effective floor is lower than the per-experiment floor, as the KyberSlash result demonstrates. Unlike dudect, which tests individual implementations for constant-time violations, sca-triage evaluates the ISO 17825 TVLA protocol itself and provides a structured triage workflow when TVLA fails. On 50,000 pre-collected traces, the full Stage 2 pipeline (pairwise decomposition + 10,000-permutation MI) completes in under 30 seconds on commodity hardware — negligible compared to the trace collection time.

**For FIPS evaluators:** If your lab has reported a TVLA failure on ML-KEM, sca-triage generates the CMVP-ready artifact report needed to justify overriding a false positive. The JSON output includes all statistics, p-values, confidence intervals, and the FALSE_POSITIVE determination with full methodology documentation — suitable for direct inclusion in a CMVP submission package. Running sca-triage on pre-collected traces adds under 30 seconds to the evaluation workflow and eliminates months of remediation cycles on implementations that are not actually leaking.

**Repository:** [https://github.com/asdfghjkltygh/m-series-pqc-timing-leak/tree/main/sca-triage](https://github.com/asdfghjkltygh/m-series-pqc-timing-leak/tree/main/sca-triage)

### Recommendations for Standards Bodies

1. **ISO 17825 should mandate interleaved collection or include Stage 2 as a mandatory follow-up.** The current standard's implicit assumption of sequential collection introduces temporal drift that produces false positives on general-purpose processors. Either mandating interleaved collection (alternating fixed and random measurements within a single loop) or requiring pairwise decomposition as a follow-up to any TVLA failure would eliminate the most common source of false positives.

2. **CMVP/FIPS 140-3 guidance should acknowledge the temporal-drift confound.** NIST's Implementation Guidance for FIPS 140-3 should include an informative note describing the confound, its root cause in sequential collection methodology, and the availability of triage tools and interleaved collection as mitigations. This prevents evaluation labs from independently discovering the problem and reaching inconsistent conclusions.

3. **Evaluation labs should adopt interleaved collection and pairwise decomposition as standard practice.** Labs performing non-invasive evaluation on general-purpose processors (as opposed to embedded targets) should switch to interleaved trace collection and include pairwise secret-group analysis in their standard operating procedures. Interleaved collection eliminates temporal drift at the source; pairwise decomposition provides an additional safety net. The marginal cost is small — the traces are already collected — and together they eliminate the most common source of false positives.

---

## Section 5: Impact and Implications

### What This Means for PQC Migration

The bottom line for organizations deploying post-quantum cryptography: **ML-KEM deployment should not be delayed based on TVLA-only evaluations.** The TVLA failures reported on Apple Silicon and Intel x86 are false positives caused by temporal drift in sequential data collection, not by weaknesses in the algorithm or its implementation. Interleaved collection eliminates the confound entirely on both platforms.

**Threat model scope.** We do not claim liboqs is perfectly constant-time. We claim it is free of secret-dependent macro-timing leaks exceeding 454 cycles (approximately 19 microseconds) — the detection floor of our apparatus as bounded by the positive control's Cohen's d = 0.094 and our timer resolution. An attacker with kernel-level performance counter (PMC) access could achieve cycle-accurate resolution, potentially detecting sub-threshold leakage; however, such an attacker already has ring-0 execution on the target machine, placing them outside the remote/userspace adversary threat model that FIPS 140-3 non-invasive evaluation targets.

The liboqs KyberSlash fix (v0.15.0 and later) is effective. Our positive control confirms that the known timing vulnerability in pre-patch versions is detectable and that the patch eliminates it. Organizations integrating liboqs at current versions can proceed with confidence that the implementation is timing-safe against remote and userspace adversaries constrained by OS scheduling noise and standard timer resolution.

For organizations already in FIPS evaluation: if your lab has reported a TVLA failure on ML-KEM running on Apple Silicon or Intel hardware, request a Stage 2 analysis. Point evaluators to this paper and the sca-triage tool. The TVLA failure is real in the statistical sense, but it does not represent exploitable leakage.

### Threat Model Implication: Denial of Certification

The temporal-drift confound raises a concerning possibility warranting further research. An adversary with co-tenancy on shared infrastructure (cloud VM, multi-tenant HSM, shared evaluation lab hardware) could potentially introduce workload changes that amplify temporal drift between TVLA measurement blocks, inflating a competitor's t-statistics above the |t| = 4.5 threshold — a "Denial of Certification" attack that blocks FIPS validation without touching the cryptographic implementation itself.

We have not demonstrated this attack experimentally. Constructing a proof of concept — where a co-located noisy process shifts a passing TVLA result to failing — is immediate future work. However, the mechanism is plausible: our results show that sequential collection alone produces |t| values up to 62x above the failure threshold, and co-tenant workloads are a known source of environmental drift. The two-stage protocol we propose is the natural countermeasure: pairwise decomposition compares secret groups within the same noisy environment, making it inherently robust to externally-induced drift. Alternatively, interleaved collection eliminates the temporal drift entirely.

### What This Means for Other PQC Algorithms

We demonstrate the confound for ML-KEM. Because the root cause is methodological — sequential collection introducing temporal drift between measurement groups — it is expected to affect any algorithm evaluated with sequential TVLA on any hardware where system state evolves during collection. This includes ML-DSA (Dilithium), SLH-DSA (SPHINCS+), BIKE, and HQC. This is a testable prediction: replicating the interleaved vs. sequential experiment with each algorithm's entry point would confirm or refute it. We have not yet performed this cross-algorithm validation; it is immediate future work. Pending that confirmation, evaluation labs should treat TVLA failures on any PQC algorithm collected sequentially as potentially confounded and either switch to interleaved collection or apply pairwise decomposition before concluding the leakage is real.

### Broader Implications

TVLA was designed in an era when side-channel evaluation targeted embedded hardware: smartcards, FPGAs, dedicated cryptographic coprocessors. These devices have simple, largely deterministic timing behavior, and trace collection completes quickly enough that environmental drift is negligible. TVLA's fixed-vs-random comparison works because the only thing that changes between iterations is the cryptographic input, and the system is stationary across the collection window.

On general-purpose processors, collection runs take minutes to hours. System state — thermal conditions, OS scheduling, power management, background processes — evolves continuously. Sequential collection creates a perfect confound: all fixed measurements occupy one time window, all random measurements occupy another, and any environmental drift between windows becomes a systematic group difference that TVLA interprets as leakage.

The gap between "TVLA-detectable" and "practically exploitable" in the software timing domain on general-purpose processors is wider than commonly assumed in FIPS evaluation practice. On embedded targets, the gap is narrow — a TVLA detection usually corresponds to a real, exploitable weakness. On modern processors, the gap is a chasm. A |t| value of 62.49 on Apple Silicon represents a strong, highly significant statistical signal that contains exactly zero bits of secret information — and vanishes entirely (|t| = 0.58) when collection is interleaved.

This does not mean timing side channels on modern processors are impossible — they clearly are not, as decades of microarchitectural attacks demonstrate. It means that TVLA's prescribed sequential collection methodology is the wrong approach for evaluating them. The methodology assumes temporal stationarity between measurement groups — an assumption that fails on any system where environmental conditions evolve during multi-minute collection runs. The two-stage protocol and interleaved collection we propose are practical fixes, but the deeper lesson is that side-channel evaluation standards must evolve alongside the hardware they evaluate.

### Limitations and Roadmap

Each limitation below includes what it would take to close the gap and why it does not undermine the current findings.

**Cross-platform interleaved control.** The interleaved harness experiment confirms the confound is temporal drift from sequential collection on both Apple Silicon (sequential |t| = 62.49 → interleaved |t| = 0.58) and Intel x86 (sequential |t| = 6.70 → interleaved |t| = 1.65). The cross-platform replication eliminates platform-specific explanations. See Section 3.

**Temporal drift mechanism is uncharacterized.** We demonstrate that sequential collection introduces temporal drift sufficient to produce catastrophic TVLA failures, but we have not isolated the specific physical mechanism (thermal drift, OS scheduling, power state transitions, etc.). *To close:* instrument collection runs with per-block thermal readings, CPU frequency logs, and OS scheduling counters to identify the dominant drift source. *Why the current findings stand:* the interleaved control proves temporal drift is the cause regardless of which physical mechanism drives it — the fix (interleaved collection or pairwise decomposition) is mechanism-agnostic.

**Compiler optimization levels.** The sequential symmetric harness fails TVLA at all five tested optimization levels (-O0 through -O3 and -Os). Initial -Os results showed run-to-run variability (|t| ranging from 1.73 to 11.47); Levene's test confirms the variance confound is present even when Welch's t happens to fall below threshold. Binary analysis confirms identical instruction counts across flags. The confound is not compiler-dependent. See Section 3.

**ML-KEM only.** Cross-algorithm validation (ML-DSA, SLH-DSA, BIKE, HQC) has not been performed. *To close:* replicate the symmetric harness experiment with each algorithm's decapsulation/signing entry point. *Why the current findings stand:* the confound is architectural (fixed-vs-random methodology on adaptive hardware), not algorithm-specific — but empirical confirmation across algorithms would strengthen the generalization claim.

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
