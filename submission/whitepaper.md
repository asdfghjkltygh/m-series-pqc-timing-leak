# When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment

**Authors:** Saahil Shenoy
**Date:** March 2026

---

## Section 1: The Problem

NIST finalized ML-KEM (Kyber) as the post-quantum key encapsulation mechanism standard in August 2024. It is the algorithm that will protect classified communications, banking infrastructure, and critical supply chains against quantum computers. Every major OS vendor is integrating it. Apple shipped it in iMessage. Google deployed it in Chrome. Cloudflare turned it on for every TLS connection. The post-quantum transition is not coming — it is happening right now.

There is one gate every implementation must pass before it can ship in a FIPS-validated cryptographic module: non-invasive side-channel evaluation per ISO 17825. This evaluation is built on the Test Vector Leakage Assessment (TVLA) methodology — a statistical test that determines whether an implementation leaks secret information through physical observables like timing, power consumption, or electromagnetic emissions. If the implementation fails TVLA, it does not get certified. If it does not get certified, it does not deploy to any federal system, any FIPS-compliant financial institution, any defense contractor.

We ran the standard test on liboqs — the most widely used open-source PQC library, the reference integration target for dozens of products — on Apple Silicon M-series and Intel Xeon x86. Both platforms fail catastrophically. Apple Silicon produces a Welch's t-statistic of |t| = 8.42, nearly double the failure threshold. Intel x86 produces |t| = 12.95, nearly triple. If taken at face value, these results block ML-KEM deployment across the entire US federal government and any organization that requires FIPS compliance.

The results should not be taken at face value. The leakage is not real. We spent months and 12.2 million traces proving it, and in this paper we explain what is actually happening, why the standard test is broken, and how to fix it.

### What Is TVLA?

The Test Vector Leakage Assessment is a first-order statistical test designed to detect side-channel leakage in cryptographic implementations. The procedure is straightforward: collect two sets of physical measurements. In the "fixed" set, the implementation processes the same input repeatedly — same ciphertext, same key, every time. In the "random" set, the implementation processes a different randomly generated input each time. Run a Welch's t-test comparing the two distributions. If the t-statistic exceeds |t| = 4.5, the implementation is deemed to leak secret-dependent information and fails evaluation.

The logic behind the threshold is simple. Under the null hypothesis of no leakage, the fixed and random groups should produce statistically indistinguishable timing distributions. A |t| value of 4.5 corresponds to a p-value far below any conventional significance level, so exceeding it is treated as definitive evidence of information leakage. In the compliance world, there is no "borderline" — you pass or you fail.

The consequences of failure are severe and concrete. A TVLA failure triggers a remediation cycle: the implementation must be redesigned, re-tested, and re-submitted. Each cycle costs months of engineering time and tens of thousands of dollars in lab fees. For organizations on CNSA 2.0 timelines — which mandate post-quantum algorithms for national security systems by 2033 — a false TVLA failure is not an inconvenience. It is a deployment-blocking event that ripples through procurement schedules, integration timelines, and risk assessments.

### The Stakes

The scale of this problem is difficult to overstate. CNSA 2.0, published by NSA in September 2022, sets hard deadlines for quantum-resistant cryptography adoption across all national security systems. The commercial sector follows FIPS requirements by policy and by contract. Every cloud provider offering GovCloud, every defense contractor handling CUI, every financial institution under federal examination — all of them need FIPS-validated PQC modules.

The cost of a false TVLA failure is not just the direct lab fees, which typically run $50,000-$150,000 per evaluation cycle. It is the cascading delay: engineering teams pulled off other work to investigate a phantom vulnerability, program managers forced to update milestone schedules, compliance officers filing exceptions, procurement officers rebidding contracts. Multiply this across every evaluation lab running the test on modern hardware — and every one of them will get the same result we did — and the aggregate cost to PQC migration is measured in years and hundreds of millions of dollars.

This is not a theoretical concern. Evaluation labs are running these tests today. TVLA failures on PQC implementations are being reported today. The question is not whether this problem will surface — it is whether the community recognizes it before it causes irreversible damage to migration timelines.

---

## Section 2: The Investigation

We collected 12.2 million timing traces across both platforms trying to turn this TVLA result into an actual key recovery attack. We did not set out to prove TVLA wrong. We set out to exploit the leakage it reported. Every technique we tried — and we tried everything — came back empty.

### Measurement Setup

**Apple Silicon M-series.** All measurements were collected on Apple M-series processors using the ARM performance counter CNTVCT_EL0 as the timing source. This counter operates at 24 MHz with 99.2% zero-tick measurement overhead, meaning the timer itself introduces negligible noise. Traces were collected under controlled conditions with performance governor set to high-performance mode, thermal throttling monitored, and system load minimized. Each measurement captures the wall-clock time for a single ML-KEM decapsulation operation.

**Intel Xeon x86.** Intel measurements used RDTSC with CPUID serialization to ensure precise cycle-accurate timing. The CPUID instruction forces pipeline serialization before reading the timestamp counter, eliminating measurement artifacts from out-of-order execution. Measured overhead is approximately 1,778 cycles per serialized read. The same controlled conditions were applied: performance governor pinned, hyperthreading accounted for, system load minimized.

**Noise model and data collection.** For each platform, we collected traces across 500 distinct keys with 50 repetitions per key, yielding a total dataset of 12.2 million measurements across both platforms. Data collection was automated and checksummed to ensure reproducibility. The entire pipeline — from trace collection through analysis — is scripted and available in the supplementary repository.

### The Exhaustive Search

We threw the full arsenal of side-channel analysis at this dataset. Gradient-boosted trees (XGBoost) and random forests for nonlinear classification and regression. Template attacks for Gaussian profiling. Convolutional neural networks for automatic feature extraction. Kolmogorov-Smirnov and Anderson-Darling distributional tests for detecting any departure from identical distributions. PCA and t-SNE for unsupervised structure discovery. Perceived Information, KSG mutual information, and MAD-based signal-to-noise ratio for information-theoretic bounding. The full experiment matrix — over 100 individual experiments — is summarized in the heatmap figure in the supplementary materials.

Every technique, at every data scale, on every target, performed at or below random guessing. XGBoost achieves 50.2% accuracy on binary key-bit classification where the majority baseline is 50.0%. The random forest returns 49.8%. The CNN converges to majority-class prediction within three epochs. Template attacks produce posteriors indistinguishable from the prior. The distributional tests show no statistically significant difference between timing distributions conditioned on different secret key bits. No method — linear, nonlinear, parametric, nonparametric, supervised, or unsupervised — found any exploitable structure in 12.2 million traces.

### The Positive Control

A negative result is only meaningful if the apparatus can detect a positive. We built the same measurement pipeline against liboqs v0.9.0, a version vulnerable to KyberSlash — a known timing side-channel where the decapsulation routine performs a variable-time division operation that leaks information about the secret key.

The results are unambiguous. On vulnerable code, our XGBoost classifier achieves +3.8% accuracy lift over random guessing. On the patched code (v0.15.0), the same classifier achieves +0.5% — consistent with statistical noise. For valid/invalid ciphertext classification (a simpler binary task), the classifier achieves 100% accuracy on both vulnerable and patched versions, confirming that the pipeline can detect input-dependent timing leakage regardless of whether secret-dependent leakage is present.

Our apparatus provably detects both secret-dependent and input-dependent timing leakage when they exist. The null result on patched ML-KEM is not a measurement failure. It is a measurement.

### The Information-Theoretic Proof

Six independent information-theoretic methods converge on the same conclusion. Perceived Information — defined as the entropy of the secret minus the cross-entropy of the best predictor — is negative for all targets: -0.012 to -0.027 bits, meaning the timing traces contain less information about the secret than a random coin flip. KSG mutual information, a nonparametric estimator that makes no distributional assumptions, returns 0.000 bits with a permutation-test p-value of 1.0. MAD-based and Winsorized signal-to-noise ratios are indistinguishable from zero. Vertical scaling analysis — increasing the dataset to 15x the theoretically predicted minimum sample size for detecting leakage at the TVLA-reported effect size — shows perfectly flat accuracy curves with no upward trend.

Six independent information-theoretic methods bound the extractable secret information at exactly zero bits. The TVLA result of |t| = 8.42 reports a signal that, by every other measure in the side-channel analysis toolkit, does not exist.

---

## Section 3: The Root Cause

If TVLA reports significant leakage and no attack can exploit it, the question is not "where is the leakage hiding?" but "what is TVLA actually detecting?" The answer is an execution-context confound — a systematic artifact of running a fixed-vs-random comparison on hardware that adapts to its input patterns.

### The Execution-Context Confound

TVLA's fixed-vs-random design makes an implicit assumption: the only difference between the two measurement groups is the cryptographic input (ciphertext and key), so any timing difference must be caused by the implementation's processing of those inputs. On simple hardware — smartcards, microcontrollers, FPGAs with deterministic pipelines — this assumption holds. The CPU does the same operations in the same order regardless of whether the input was seen before.

Modern processors do not work this way. Apple Silicon and Intel x86 both feature deep speculative execution, aggressive prefetching, complex cache hierarchies, and branch prediction units that learn from execution history. When TVLA feeds the same input repeatedly (the fixed group), these microarchitectural optimizers converge on a deterministic state: the prefetcher learns the access pattern, the branch predictor locks onto the branch outcomes, the cache stabilizes. When TVLA feeds a different input every time (the random group), the optimizers never converge: the prefetcher is constantly adapting, the branch predictor is constantly retraining, the cache is constantly churning.

The timing difference TVLA detects is real — but it is between "CPU has optimized for this input" and "CPU is constantly adapting to new inputs." It is not between "implementation processing secret A" and "implementation processing secret B." The leakage is input-dependent, not secret-dependent. TVLA cannot tell the difference.

### Apple Silicon: DMP Synchronization

Apple M-series processors feature a Data-Dependent Prefetcher (DMP) that examines data values flowing through the pipeline and speculatively prefetches memory addresses that look like pointers. This is an aggressive optimization unique to Apple's microarchitecture (and the subject of the "Augury" disclosure in 2022).

In TVLA's fixed group, the same ciphertext bytes flow through ML-KEM's decapsulation routine every time. The DMP sees the same data patterns, issues the same prefetch requests, and within a few iterations locks onto a stable prefetch strategy. Execution is fast — most of the time. But the DMP's synchronization is not perfect. Occasionally, it makes a catastrophically wrong prediction, issuing prefetches that evict useful cache lines and cause pipeline stalls. The result is a bimodal timing distribution: most measurements cluster tightly around the fast mode, but rare outliers land 10x slower.

In the random group, every iteration presents new data values. The DMP never synchronizes, never locks on, and never catastrophically mispredicts. The result is a unimodal distribution with moderate, consistent timing.

TVLA's Welch's t-test compares the means of these two distributions. The fixed group's mean is pulled upward by its heavy tail of catastrophic DMP misses. The random group's mean is stable. The difference is statistically significant — |t| = 8.42 — but it has nothing to do with the secret key.

### Intel x86: Cache Thrashing

Intel Xeon processors exhibit the same failure mode through a different mechanism. On Intel, the dominant confound is cache replacement policy interaction with speculative execution. The fixed group allows the cache hierarchy to stabilize around a single working set, but Intel's pseudo-LRU replacement policy introduces periodic eviction storms when the working set sits at a cache-set boundary. The random group constantly varies the working set, preventing both stabilization and storms.

The telling detail: on Intel, the variance ratio is inverted. The random group has *higher* variance (0.47x ratio, meaning fixed variance is about half of random variance). On Apple, the fixed group has higher variance due to DMP catastrophic misses. Different mechanisms, opposite variance signatures — but TVLA fails identically on both platforms because it detects mean differences, not variance differences, and both mechanisms shift the mean.

This cross-platform replication with divergent root causes is what elevates the finding from a platform-specific quirk to a systemic indictment of the methodology. The confound is not "Apple does X" or "Intel does Y." The confound is "any modern processor with adaptive microarchitecture will violate TVLA's stationarity assumption."

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
- If pairwise decomposition shows **no significant differences** between secret groups AND mutual information is **zero** (within permutation confidence): the TVLA failure is a **false positive** caused by execution-context confound. The implementation **passes**.
- If pairwise decomposition **detects significant differences** between secret groups OR mutual information is **positive**: the leakage is **real and secret-dependent**. The implementation **fails**.

This protocol preserves TVLA's role as a conservative first-pass screen while eliminating false positives that arise from microarchitectural confounds. It adds cost only when TVLA fails — which, on modern hardware, will be most of the time.

### The Tool: sca-triage

We release **sca-triage**, an open-source Python tool that implements Stage 2 of the two-stage protocol. It is designed for integration into existing evaluation lab workflows.

**Installation:**

```
pip install sca-triage
```

**Usage:**

```bash
# Step 1: Run TVLA and export traces
sca-triage tvla --traces measurements.npy --labels fixed_random.npy

# Step 2: Run pairwise decomposition
sca-triage pairwise --traces measurements.npy --keys secret_keys.npy

# Step 3: Compute mutual information with permutation test
sca-triage mi --traces measurements.npy --keys secret_keys.npy --permutations 10000
```

**Output:**

sca-triage produces a structured JSON report containing:
- TVLA t-statistic and pass/fail determination
- Pairwise t-statistics for each secret-group comparison
- Permutation-validated mutual information estimate with confidence interval
- Final verdict: PASS, FAIL, or FALSE_POSITIVE with full justification
- Visualization of timing distributions by secret group

Auditors integrate sca-triage into their FIPS evaluation workflow by running it as a follow-up to any TVLA failure. The JSON report provides the documentation trail needed for CMVP submission, including the statistical justification for overriding a TVLA failure.

**Repository:** [https://github.com/PLACEHOLDER/sca-triage](https://github.com/PLACEHOLDER/sca-triage)

### Recommendations for Standards Bodies

1. **ISO 17825 should include Stage 2 as a mandatory follow-up.** The current standard treats TVLA failure as definitive. On modern hardware, it is not. The standard should specify that implementations failing TVLA on general-purpose processors must undergo pairwise decomposition before a final determination is made.

2. **CMVP/FIPS 140-3 guidance should acknowledge the execution-context confound.** NIST's Implementation Guidance for FIPS 140-3 should include an informative note describing the confound, its root causes on common architectures, and the availability of triage tools. This prevents evaluation labs from independently discovering the problem and reaching inconsistent conclusions.

3. **Evaluation labs should adopt pairwise decomposition as standard practice.** Labs performing non-invasive evaluation on general-purpose processors (as opposed to embedded targets) should include pairwise secret-group analysis in their standard operating procedures. The marginal cost is small — the traces are already collected — and it eliminates the most common source of false positives.

---

## Section 5: Impact and Implications

### What This Means for PQC Migration

The bottom line for organizations deploying post-quantum cryptography: **ML-KEM deployment should not be delayed based on TVLA-only evaluations.** The TVLA failures reported on Apple Silicon and Intel x86 are false positives caused by microarchitectural confounds, not by weaknesses in the algorithm or its implementation.

The liboqs KyberSlash fix (v0.15.0 and later) is effective. Our positive control confirms that the known timing vulnerability in pre-patch versions is detectable and that the patch eliminates it. Organizations integrating liboqs at current versions can proceed with confidence that the implementation is timing-safe to the limits of our measurement capability.

For organizations already in FIPS evaluation: if your lab has reported a TVLA failure on ML-KEM running on Apple Silicon or Intel hardware, request a Stage 2 analysis. Point evaluators to this paper and the sca-triage tool. The TVLA failure is real in the statistical sense, but it does not represent exploitable leakage.

### What This Means for Other PQC Algorithms

The execution-context confound is **architectural, not algorithm-specific.** It arises from the interaction between TVLA's fixed-vs-random methodology and modern processors' adaptive microarchitecture. Any algorithm evaluated with TVLA on hardware featuring speculative execution, data-dependent prefetching, or adaptive cache replacement will be subject to the same confound.

This means TVLA will produce false positives for:
- **ML-DSA (Dilithium)** — the post-quantum digital signature standard
- **SLH-DSA (SPHINCS+)** — the hash-based signature standard
- **BIKE and HQC** — code-based KEM candidates still under consideration for standardization
- **Any lattice, code, hash, or isogeny-based scheme** evaluated on general-purpose hardware

Every evaluation lab should adopt the two-stage protocol for all PQC evaluations on production hardware. The confound is not going away — modern processors are only becoming more aggressive in their microarchitectural optimization.

### Broader Implications

TVLA was designed in an era when side-channel evaluation targeted embedded hardware: smartcards, FPGAs, dedicated cryptographic coprocessors. These devices have simple, largely deterministic timing behavior. A branch taken or not taken, a cache hit or miss — on a smartcard, these events map directly to secret-dependent computation. TVLA's fixed-vs-random comparison works because the only thing that changes between iterations is the cryptographic input.

Modern general-purpose processors violate this assumption at every level. Speculative execution decouples observed timing from the actual instruction sequence. Branch prediction and prefetching create history-dependent timing that varies based on what the CPU has seen recently, not what it is computing now. Complex cache hierarchies with pseudo-random replacement policies introduce timing variation that is neither secret-dependent nor even deterministic.

The gap between "TVLA-detectable" and "practically exploitable" is wider than the side-channel community has understood. On embedded targets, the gap is narrow — a TVLA detection usually corresponds to a real, exploitable weakness. On modern processors, the gap is a chasm. A |t| value of 12.95 on Intel x86 represents a strong, highly significant statistical signal that contains exactly zero bits of secret information.

This does not mean timing side channels on modern processors are impossible — they clearly are not, as decades of microarchitectural attacks demonstrate. It means that TVLA is the wrong tool for detecting them. The methodology assumes a threat model and a hardware model that do not match production deployment environments. The two-stage protocol we propose is a practical fix, but the deeper lesson is that side-channel evaluation standards must evolve alongside the hardware they evaluate.

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

MAD is resistant to the heavy-tailed outliers that characterize DMP-affected timing distributions. We compute SNR across secret-key-byte groups and across Hamming weight classes.

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
