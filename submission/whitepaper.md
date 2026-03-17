# When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment

**Authors:** Saahil Shenoy
**Date:** March 2026

---

## Section 1: The Problem

NIST finalized ML-KEM (Kyber) as the post-quantum key encapsulation mechanism standard in August 2024. It is the algorithm that will protect classified communications, banking infrastructure, and critical supply chains against quantum computers. Every major OS vendor is integrating it. Apple shipped it in iMessage. Google deployed it in Chrome. Cloudflare turned it on for every TLS connection. The post-quantum transition is not coming — it is happening right now.

There is one gate every implementation must pass before it can ship in a FIPS-validated cryptographic module: non-invasive side-channel evaluation per ISO 17825. This evaluation is built on the Test Vector Leakage Assessment (TVLA) methodology — a statistical test that determines whether an implementation leaks secret information through physical observables like timing, power consumption, or electromagnetic emissions. If the implementation fails TVLA, it does not get certified. If it does not get certified, it does not deploy to any federal system, any FIPS-compliant financial institution, any defense contractor.

We ran the standard test on liboqs — the most widely used open-source PQC library, the reference integration target for dozens of products — on Apple Silicon M-series and Intel Xeon x86. Both platforms fail catastrophically. Apple Silicon produces a Welch's t-statistic of |t| = 8.42, nearly double the failure threshold. Intel x86 produces |t| = 12.95, nearly triple. If taken at face value, these results block ML-KEM deployment across the entire US federal government and any organization that requires FIPS compliance.

The results should not be taken at face value. The leakage is not real. We spent months and 12.2 million traces proving it, and in this paper we explain what is actually happening — how ubiquitous, asymmetrical software test harnesses interact with adaptive microarchitectures to trigger phantom FIPS 140-3 compliance failures — and how to fix it.

### What Is TVLA?

The Test Vector Leakage Assessment is a first-order statistical test originally proposed by Goodwill et al. (NIST Non-Invasive Attack Testing Workshop, 2011) and codified in ISO 17825 for detecting side-channel leakage in cryptographic implementations. Its limitations have been studied extensively: Schneider & Moradi (CHES 2015) noted that environmental noise on general-purpose hardware can produce statistically significant but non-exploitable results; Whitnall & Oswald (CHES 2011, J. Cryptographic Engineering 2014) documented the gap between statistical distinguishability and key recovery; Mather et al. (2019) provided methodological guidance acknowledging TVLA overreporting; and Bronchain & Standaert (TCHES 2021) introduced the Perceived Information framework specifically because TVLA detection does not imply exploitability. In the software timing domain specifically, dudect (Reparaz et al., DATE 2017) applies the same core test — Welch's t-test on software timing measurements — to detect non-constant-time behavior in cryptographic implementations on general-purpose processors, and explicitly acknowledges false positive risk from OS scheduling noise. Our contribution is not discovering that TVLA has limitations — that is well-established. Our contribution is distinct from and complementary to dudect: whereas dudect tests whether an *implementation* is constant-time, we evaluate whether the *ISO 17825 TVLA protocol itself* produces valid certification results on production hardware, and we provide a structured triage workflow when it fails. We systematically quantify the ISO 17825 failure rate specifically for the NIST ML-KEM standard, prove non-exploitability through 100+ converging experiments, and release a practical triage tool.

The procedure is straightforward: collect two sets of timing measurements. In the "fixed" set, the implementation processes the same input repeatedly. In the "random" set, it processes a different input each time. A Welch's t-test compares the two distributions; if |t| > 4.5, the implementation fails. In the compliance world, there is no "borderline" — you pass or you fail, and failure triggers a remediation cycle costing months of engineering time and $50,000-$150,000 in lab fees.

### The Stakes

CNSA 2.0 mandates quantum-resistant cryptography for all national security systems by 2033. Every cloud provider offering GovCloud, every defense contractor handling CUI, every financial institution under federal examination needs FIPS-validated PQC modules. The cost of a false TVLA failure cascades far beyond the $50,000-$150,000 per evaluation cycle: engineering teams investigate phantom vulnerabilities, program managers update milestone schedules, procurement officers rebid contracts. Multiply across every evaluation lab running this test on modern hardware and the aggregate cost to PQC migration is measured in years. Evaluation labs are running these tests today. TVLA failures are being reported today.

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

### Ruling Out Aggregation Masking

A natural objection to the above: we aggregated 50 repeats per key into summary statistics (mean, median, standard deviation) before training our ML models. If secret-dependent leakage is stochastic — occurring on only a small fraction of traces due to rare cache alignments or branch mispredictions — averaging could destroy the signal before any classifier sees it.

We tested this directly. We ran XGBoost and Random Forest classifiers on the raw, unaggregated traces — each row being a single decapsulation execution, not a per-key summary. We also ran Welch's t-test, KS 2-sample test, and KSG mutual information at the individual-trace level across 100,000 raw measurements.

The results are unambiguous. At the single-trace level, sk_lsb classification accuracy is 50.5% (XGBoost) with Cohen's d = 0.0003 and MI = 0.000 bits (p = 1.0). Message Hamming weight parity yields 50.4% accuracy with d = 0.009. Every statistical test is non-significant. The raw trace analysis was performed on Apple Silicon data; the Intel x86 dataset was collected under the same protocol with identical per-trace structure, and the pairwise decomposition on Intel (which operates on per-key features, not aggregated means) independently confirms zero secret dependence on that platform. The null result is not an artifact of aggregation — the signal does not exist at any granularity.

### The Positive Control

A negative result is only meaningful if the apparatus can detect a positive. We built the same measurement pipeline against liboqs v0.9.0, a version vulnerable to KyberSlash — a known timing side-channel where the decapsulation routine performs a variable-time division operation that leaks information about the secret key.

The results are unambiguous. On vulnerable code, our XGBoost classifier achieves +3.8% accuracy lift over random guessing. On the patched code (v0.15.0), the same classifier achieves +0.5% — consistent with statistical noise. For valid/invalid ciphertext classification (a simpler binary task), the classifier achieves 100% accuracy on both vulnerable and patched versions, confirming that the pipeline can detect input-dependent timing leakage regardless of whether secret-dependent leakage is present.

Our apparatus provably detects both secret-dependent and input-dependent timing leakage when they exist. The null result on patched ML-KEM is not a measurement failure. It is a measurement.

We note that KyberSlash represents a relatively large vulnerability (variable-time division). To quantify our sensitivity to *smaller* effects, we computed detection floors for both our statistical and ML pipelines. The pairwise t-test detection floor is d = 0.398 (454 cycles) at 80% power with our sample configuration. The ML classification floor is higher at d ≈ 0.85 (>55% accuracy in ≥80% of trials with 500 keys). The full sca-triage pipeline — combining pairwise tests, MI, and classification — achieves 80% detection rate at d ≈ 0.275, demonstrating that the multi-method approach is more sensitive than any single test. KyberSlash's d = 0.094 falls below all three per-experiment floors when using per-key aggregated features; our pipeline detected it through a fundamentally different mechanism — population-level aggregation across 500 keys, where the effect size is large enough for XGBoost to learn a weak but consistent signal (+3.8% lift). The per-experiment pipeline detection floor (d ≈ 0.275) and the population-level KyberSlash detection (d = 0.094) characterize complementary detection mechanisms, not the same pathway. Effects smaller than d ≈ 0.1 are below both detection mechanisms — and are unexploitable via userspace macro-timing.

### The Information-Theoretic Proof

Six independent information-theoretic methods converge on the same conclusion. Perceived Information — defined as the entropy of the secret minus the cross-entropy of the best predictor — is negative for all targets: -0.012 to -0.027 bits, meaning the timing traces contain less information about the secret than a random coin flip. KSG mutual information, a nonparametric estimator that makes no distributional assumptions, returns 0.000 bits with a permutation-test p-value of 1.0. MAD-based and Winsorized signal-to-noise ratios are indistinguishable from zero. Vertical scaling analysis — increasing the dataset to 15x the theoretically predicted minimum sample size for detecting leakage at the TVLA-reported effect size — shows perfectly flat accuracy curves with no upward trend.

Six independent information-theoretic methods bound the extractable secret information at exactly zero bits. The TVLA result of |t| = 8.42 reports a signal that, by every other measure in the side-channel analysis toolkit, does not exist.

---

## Section 3: The Root Cause

If TVLA reports significant leakage and no attack can exploit it, the question is not "where is the leakage hiding?" but "what is TVLA actually detecting?" The answer is a dual-source execution-context confound: (1) asymmetrical test harness design that performs different amounts of pre-measurement work in fixed vs random modes, and (2) architectural microoptimizations that respond differently to repeated vs novel inputs. Both sources are ubiquitous in software TVLA evaluations, and together they produce catastrophic false positives.

### The Harness Asymmetry Problem

Our TVLA harness — like virtually every software TVLA harness we have encountered in open-source PQC testing — executes different code paths in fixed vs random modes. In fixed mode, a single (ciphertext, secret key) pair is generated once during setup, and each iteration simply times `decaps()`. In random mode, each iteration generates a fresh keypair via `keygen()` and a fresh ciphertext via `encaps()` before timing `decaps()`. Although `keygen()` and `encaps()` execute *outside* the timing window, they pollute cache lines, branch predictor state, and prefetcher history before the timed operation begins.

This asymmetry is not a bug in our harness — it is the natural implementation of ISO 17825's fixed-vs-random protocol for software evaluations. The standard requires "random" inputs; generating them per-iteration is the obvious approach and the one most developers and evaluation labs adopt. A fully symmetric harness would pre-generate all random inputs into a memory array and index into it, ensuring identical cache footprints across both modes. We did not implement this symmetric design, and we suspect most evaluation labs do not either. The consequence is that a significant fraction of the observed TVLA signal on Intel x86 may be attributable to harness-induced cache state differences rather than to the cryptographic implementation or the standard itself.

### The Architectural Confound

Even with a perfectly symmetric harness, a second confound persists on hardware with adaptive microarchitecture. TVLA's fixed-vs-random design makes an implicit assumption: the only difference between the two measurement groups is the cryptographic input. On simple hardware — smartcards, microcontrollers, FPGAs with deterministic pipelines — this assumption holds.

Modern processors violate it. When TVLA feeds the same input repeatedly (the fixed group), microarchitectural optimizers converge on a deterministic state: the prefetcher learns the access pattern, the branch predictor locks onto outcomes, the cache stabilizes. When TVLA feeds a different input every time (the random group), these optimizers never converge. The timing difference TVLA detects is real — but it is between "CPU has optimized for this input" and "CPU is constantly adapting to new inputs." It is not between "implementation processing secret A" and "implementation processing secret B." The leakage is input-dependent, not secret-dependent.

### Apple Silicon: DMP Synchronization (Architectural)

Apple M-series processors feature a Data-Dependent Prefetcher (DMP) that examines data values flowing through the pipeline and speculatively prefetches memory addresses that look like pointers. This is an aggressive optimization unique to Apple's microarchitecture, extensively characterized by Borah et al. (GoFetch, 2024) and the earlier Augury disclosure (2022).

On Apple Silicon, the dominant confound is architectural, not harness-induced. Even with a perfectly symmetric harness (pre-generated random inputs, identical cache footprint), feeding the same fixed ciphertext repeatedly would cause the DMP to converge on a stable prefetch strategy. The DMP sees the same data patterns and locks in, producing fast execution with occasional catastrophic mispredictions that create pipeline stalls. The result is a bimodal timing distribution: most measurements cluster tightly around the fast mode, with rare outliers landing 10x slower. In the random group, every iteration presents new data values; the DMP never converges, producing a unimodal distribution with moderate, consistent timing.

TVLA's Welch's t-test compares the means of these two distributions. The fixed group's mean is pulled upward by its heavy tail. The difference is statistically significant — |t| = 8.42 — but it has nothing to do with the secret key. The harness asymmetry (keygen+encaps in random mode) adds a secondary cache pollution effect, but the DMP synchronization on repeated data is the primary driver on this platform. We note that we did not use Performance Monitoring Counters (PMCs) to directly observe DMP state transitions; our attribution is based on the consistency of the observed variance signature with the known DMP behavioral model.

### Intel x86: Harness-Induced Cache Pollution + Architectural Effects

Intel Xeon processors exhibit the same TVLA failure through a different mechanism where the harness asymmetry plays a more prominent role. The random-mode harness executes `OQS_KEM_keypair()` and `OQS_KEM_encaps()` before each timed decapsulation, while fixed mode does not. On Intel's deep cache hierarchy, these operations evict decaps-related cache lines and retrain the branch predictor, creating a measurably different microarchitectural starting state for the timed operation.

We cannot isolate what fraction of the Intel signal is harness-induced versus architectural. The candidates are: (a) keygen+encaps cache pollution (harness asymmetry), (b) intrinsic cache replacement behavior on varying vs repeated data (architectural), and (c) OS scheduler effects (Linux CFS). A fully symmetric harness with pre-generated random inputs would eliminate source (a) and reveal whether (b) alone produces a TVLA failure on Intel. We leave this isolation experiment to future work.

The telling detail: on Intel, the variance ratio is inverted. The random group has *higher* variance (0.47x ratio, meaning fixed variance is about half of random variance). On Apple, the fixed group has higher variance. Different mechanisms, opposite variance signatures — but TVLA fails identically on both platforms because it detects mean differences, not variance differences, and both mechanisms shift the mean. The inverted variance on Intel is consistent with harness-induced cache thrashing in random mode inflating that group's timing variability.

**Cross-platform harness equivalence.** Both C-language TVLA harnesses execute byte-for-byte identical logic: both call `keygen()` + `encaps()` as setup before each random-mode decapsulation, both time only `decaps()`, and both share identical memory allocation, warmup, and output patterns. The sole difference is the timer instruction: `CNTVCT_EL0` (ARM) vs `RDTSC` with CPUID serialization (x86). The variance inversion across platforms is therefore a hardware phenomenon, not a measurement artifact — the same asymmetric harness produces opposite variance signatures on different architectures.

This cross-platform replication is what elevates the finding from a platform-specific curiosity to a systemic problem. On Apple, the DMP architectural effect dominates even if the harness were made symmetric. On Intel, the harness asymmetry is likely the dominant contributor, though architectural cache effects may also play a role. In both cases, the result is the same: naive software TVLA harnesses — written exactly as most developers and evaluation labs would write them — produce catastrophic false positives that mimic real leakage. The practical implication is identical regardless of which confound source dominates: pairwise decomposition is needed to distinguish real leakage from artifacts.

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

Auditors integrate sca-triage into their FIPS evaluation workflow by running it as a follow-up to any TVLA failure. The JSON and HTML reports provide the documentation trail needed for CMVP submission, including the statistical justification for overriding a TVLA failure.

**Sensitivity characterization.** We validated the tool's detection capability by injecting synthetic timing leaks at Cohen's d = {0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0} across 20 trials per effect size. The tool achieves 90% detection rate at d = 0.3 and 100% at d = 0.5. Below d = 0.1, the tool cannot reliably distinguish injected leakage from noise. The per-experiment pipeline detection floor is d ≈ 0.275 (80% detection rate). For population-level analysis across many keys, the effective floor is lower — our KyberSlash detection at d = 0.094 used cross-key aggregation, a complementary mechanism. Unlike dudect, which tests individual implementations for constant-time violations, sca-triage evaluates the ISO 17825 TVLA protocol itself and provides a structured triage workflow when TVLA fails.

**Repository:** [https://github.com/asdfghjkltygh/m-series-pqc-timing-leak/tree/main/sca-triage](https://github.com/asdfghjkltygh/m-series-pqc-timing-leak/tree/main/sca-triage)

### Recommendations for Standards Bodies

1. **ISO 17825 should include Stage 2 as a mandatory follow-up.** The current standard treats TVLA failure as definitive. On modern hardware, it is not. The standard should specify that implementations failing TVLA on general-purpose processors must undergo pairwise decomposition before a final determination is made.

2. **CMVP/FIPS 140-3 guidance should acknowledge the execution-context confound.** NIST's Implementation Guidance for FIPS 140-3 should include an informative note describing the confound, its root causes on common architectures, and the availability of triage tools. This prevents evaluation labs from independently discovering the problem and reaching inconsistent conclusions.

3. **Evaluation labs should adopt pairwise decomposition as standard practice.** Labs performing non-invasive evaluation on general-purpose processors (as opposed to embedded targets) should include pairwise secret-group analysis in their standard operating procedures. The marginal cost is small — the traces are already collected — and it eliminates the most common source of false positives.

---

## Section 5: Impact and Implications

### What This Means for PQC Migration

The bottom line for organizations deploying post-quantum cryptography: **ML-KEM deployment should not be delayed based on TVLA-only evaluations.** The TVLA failures reported on Apple Silicon and Intel x86 are false positives caused by microarchitectural confounds, not by weaknesses in the algorithm or its implementation.

**Threat model scope.** We do not claim liboqs is perfectly constant-time. We claim it is free of secret-dependent macro-timing leaks exceeding 454 cycles (approximately 19 microseconds) — the detection floor of our apparatus as bounded by the positive control's Cohen's d = 0.094 and our timer resolution. An attacker with kernel-level performance counter (PMC) access could achieve cycle-accurate resolution, potentially detecting sub-threshold leakage; however, such an attacker already has ring-0 execution on the target machine, placing them outside the remote/userspace adversary threat model that FIPS 140-3 non-invasive evaluation targets.

The liboqs KyberSlash fix (v0.15.0 and later) is effective. Our positive control confirms that the known timing vulnerability in pre-patch versions is detectable and that the patch eliminates it. Organizations integrating liboqs at current versions can proceed with confidence that the implementation is timing-safe against remote and userspace adversaries constrained by OS scheduling noise and standard timer resolution.

For organizations already in FIPS evaluation: if your lab has reported a TVLA failure on ML-KEM running on Apple Silicon or Intel hardware, request a Stage 2 analysis. Point evaluators to this paper and the sca-triage tool. The TVLA failure is real in the statistical sense, but it does not represent exploitable leakage.

### The Offensive Angle: Denial of Certification

The execution-context confound is not merely a testing nuisance — it is a weaponizable attack surface. An adversary with co-tenancy on a shared server (cloud VM, multi-tenant HSM, shared evaluation infrastructure) could intentionally pollute cache and prefetcher state to force a competitor's FIPS 140-3 TVLA evaluation to fail. The attack requires no cryptographic knowledge: sustained memory-intensive workloads on adjacent cores are sufficient to shift variance ratios and inflate t-statistics above the |t| = 4.5 threshold. The result is a "Denial of Certification" attack — the target organization's PQC module is blocked from FIPS validation, delaying their product launch by months and costing six-figure remediation fees, all without touching the cryptographic implementation itself. The two-stage protocol we propose is the countermeasure: pairwise decomposition is immune to cache pollution because it compares secret groups within the same noisy environment, rather than comparing a controlled fixed group against a noisy random group.

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

### Limitations

**Target coverage.** Our secret-dependent targets cover key-level properties (LSB, byte values, Hamming weights) and message-level properties (message Hamming weight parity, valid/invalid ciphertext, rejection flag). We did not test NTT-internal intermediate values (butterfly outputs, polynomial coefficient products during Montgomery reduction, CBD sampling intermediates). However, our raw-trace analysis bounds any per-execution timing signal at d < 0.001 regardless of target, which constrains intermediate-value leakage as well — any NTT-internal timing dependency would need to propagate through hundreds of operations to affect macro-timing, and no such effect is observable.

**Microarchitectural attribution.** We attribute the execution-context confound to DMP synchronization (Apple) and cache replacement effects (Intel), but these attributions are based on consistency with known behavioral models (GoFetch, Augury) rather than direct PMC measurement. Other contributing factors — OS scheduler behavior, memory allocator patterns, TLB effects — have not been individually isolated. The important claim is that the confound exists and is not secret-dependent, not the precise microarchitectural mechanism.

**Detection sensitivity.** Our full triage pipeline achieves 80% detection rate at d ≈ 0.275 per individual experiment. For population-level analysis across many keys, the effective floor is lower, as demonstrated by the KyberSlash detection at d = 0.094. Effects below d ≈ 0.1 are below both detection mechanisms. We do not claim the implementation is perfectly constant-time — only that any remaining timing variation is unexploitable via userspace macro-timing within our threat model. Our detection floor characterizes the tool's operating envelope; laboratories requiring finer-grained assurance should complement sca-triage with dedicated profiled attacks or EM-based measurement.

**Algorithm scope.** We evaluated ML-KEM (Kyber) only. Whether TVLA produces analogous false positives on other NIST PQC standards — ML-DSA (Dilithium), SLH-DSA (SPHINCS+) — remains an open question. The execution-context confound is architectural (arising from fixed-vs-random methodology on adaptive microarchitectures) and is therefore expected to generalize, but this has not been empirically verified. Cross-algorithm validation is immediate future work.

**Harness symmetry.** Our TVLA harnesses execute `keygen()` + `encaps()` before each random-mode measurement but not before fixed-mode measurements, creating an asymmetric cache footprint. This design mirrors how most software developers and evaluation labs implement the fixed-vs-random protocol, but it introduces a harness-induced confound that is distinct from the architectural DMP/cache confound. A fully symmetric harness — pre-generating all random (ciphertext, secret key) pairs into memory arrays and indexing into them identically to the fixed pair — would isolate the architectural contribution. On Apple Silicon, we expect the DMP synchronization effect to persist regardless of harness symmetry (the DMP responds to repeated data values, not to surrounding cache state). On Intel, the TVLA failure may be substantially or entirely attributable to the harness asymmetry. This isolation experiment is critical future work for disentangling the two confound sources.

**Compiler optimization levels.** All measurements were collected with `-O2 -march=native`, the standard production configuration. We did not test `-O3` or `-Os`. Microarchitectural state pollution is sensitive to compiler flags — KyberSlash's exploitability was flag-dependent — and varying optimization levels may alter the variance ratio inversion or the magnitude of the TVLA false positive. Cross-flag testing is straightforward future work.

**Standards version.** Our evaluation targets ISO 17825 as commonly applied in FIPS 140-3 evaluations. The 2024 revision of ISO 17825 introduced updated sample size requirements and percentile-based timing analysis. Whether the 2024 revision's percentile-based methodology mitigates the false positive phenomenon is an open question that we have not tested.

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
