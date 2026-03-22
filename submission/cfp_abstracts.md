# Black Hat CFP Abstracts

Three versions of the Call for Papers abstract (~300 words each). Select the version best suited to the review committee composition.

---

## Version A: "Compliance Crisis"

**Title:** When TVLA Lies: A FIPS 140-3 Compliance Crisis for Post-Quantum Cryptography

**Abstract:**

The industry-standard test for certifying post-quantum cryptography under FIPS 140-3 is broken, and it is about to delay PQC deployment across the entire federal supply chain.

NIST finalized ML-KEM (Kyber) as the post-quantum key encapsulation standard. Before any implementation ships in a FIPS-validated module, it must pass non-invasive side-channel evaluation per ISO 17825, a test built on the Test Vector Leakage Assessment (TVLA) methodology. Every evaluation lab in the CMVP pipeline will run this test. Every one of them will get a failing result.

We ran ISO 17825 TVLA on liboqs ML-KEM-768 across two major production platforms using a symmetric test harness that isolates the confound. Apple Silicon produces |t| = 62.49. Intel x86 produces |t| = 6.70. Both far exceed the |t| = 4.5 failure threshold. But the leakage is not real. We collected 12.2 million timing traces and applied every major side-channel attack technique: gradient-boosted classifiers, template attacks, convolutional neural networks, distributional tests, and information-theoretic bounds. Every technique, at every scale, on every target, performed at or below random guessing. The extractable secret information is exactly zero bits.

The root cause is temporal drift from sequential data collection: TVLA's standard protocol collects all fixed-input measurements in one block, then all random-input measurements in a second block. System state drifts between blocks, and TVLA misinterprets that drift as leakage. Switching to interleaved collection (alternating fixed and random on each iteration) drops |t| from 62.49 to 0.58 on Apple Silicon (100x reduction) and from 6.70 to 1.65 on Intel. Same hardware, same code, same inputs. Interleaving is common in hardware power analysis and is built into dudect's measurement loop, but is absent from the ISO 17825 protocol.

A positive control against the KyberSlash vulnerability (liboqs v0.9.0) confirms our pipeline detects real leakage, and that TVLA is broken in both directions: false positives on hardened code while KyberSlash (d = 0.094) falls below its detection floor.

We release sca-triage, an open-source tool that automates TVLA false positive triage, and propose a two-stage evaluation protocol for ISO 17825. Organizations on CNSA 2.0 timelines cannot afford a compliance bottleneck built on a broken test.

**Prior Work and Differentiation:**

Prior work (Schneider & Moradi, CHES 2015; Whitnall & Oswald) documented the detection-exploitability gap on evaluation boards. dudect (Reparaz et al., DATE 2017) already uses interleaved measurement. Dunsche et al. (USENIX Security 2024) and SILENT (arXiv 2025) reported TVLA failures on general-purpose CPUs. We go further: we isolate the root cause as temporal drift via a controlled sequential-vs-interleaved experiment replicated on two platforms, prove non-exploitability through 150+ converging experiments, and release a practical triage tool for FIPS evaluation labs.

---

## Version B: "Broken Standard"

**Title:** The TVLA Mirage: Catastrophic False Positives in ISO 17825 on Modern Microarchitectures

**Abstract:**

ISO 17825 TVLA produces catastrophic false positives on modern processor architectures, and the root cause is fundamental to how the protocol collects its measurements.

We evaluated liboqs ML-KEM-768 using the fixed-vs-random Welch's t-test prescribed by ISO 17825 with a symmetric test harness that eliminates harness-induced confounds. On Apple Silicon, TVLA reports |t| = 62.49. On Intel x86, |t| = 6.70. Both exceed the |t| > 4.5 failure threshold by wide margins.

We prove the leakage is not real through 150+ experiments across 12.2 million traces. Gradient-boosted trees, random forests, template attacks, CNNs, distributional tests, unsupervised clustering, and information-theoretic analyses all converge: zero exploitable information. KSG mutual information is 0.000 bits (p = 1.0). The signal TVLA detects cannot be converted into any form of key recovery.

The root cause is temporal drift from sequential data collection. The standard protocol collects fixed-input and random-input measurements in separate blocks. System state (thermal conditions, DVFS, OS scheduling) drifts between blocks, creating systematic timing differences correlated with group assignment. Switching to interleaved collection (alternating fixed[i] and random[i] within a single loop) eliminates the confound entirely: |t| drops from 62.49 to 0.58 on Apple Silicon (100x reduction) and from 6.70 to 1.65 on Intel. Cross-platform replication with identical results confirms a methodological, not architectural, root cause.

A positive control against KyberSlash-vulnerable code validates our apparatus. We propose a two-stage evaluation protocol with pairwise secret-group decomposition as a mandatory follow-up to TVLA failures, and release sca-triage, an open-source triage tool.

**Prior Work and Differentiation:**

Prior work (Schneider & Moradi, CHES 2015; Whitnall & Oswald) documented the detection-exploitability gap on evaluation boards. dudect (Reparaz et al., DATE 2017) already uses interleaved measurement. Dunsche et al. (USENIX Security 2024) and SILENT (arXiv 2025) reported TVLA failures on general-purpose CPUs. We isolate the root cause (temporal drift via sequential-vs-interleaved control), prove non-exploitability at scale, and provide a practical triage workflow for FIPS evaluation labs.

---

## Version C: "PQC Migration Under Threat"

**Title:** The False Positive Wall: Why Every PQC Migration Will Stall at Side-Channel Certification

**Abstract:**

Every organization migrating to post-quantum cryptography will hit the same wall: a mandatory side-channel test that fails correct, hardened code on every modern processor.

The post-quantum transition is underway. CNSA 2.0 mandates quantum-resistant algorithms by 2033. ML-KEM is shipping in browsers, operating systems, and cloud platforms. But before any implementation enters a FIPS-validated cryptographic module, it must pass ISO 17825 non-invasive side-channel evaluation, and on production hardware, it will fail.

We quantified the problem using a symmetric test harness: |t| = 62.49 on Apple Silicon, |t| = 6.70 on Intel x86, both far above the failure threshold. We then spent 12.2 million traces and 150+ experiments trying to exploit the reported leakage. The result: zero extractable bits of secret information.

The root cause is temporal drift from sequential data collection. The ISO 17825 protocol collects fixed and random measurements in separate blocks. System state drifts between blocks, and TVLA misinterprets that drift as leakage. Switching to interleaved collection drops |t| from 62.49 to 0.58 on Apple Silicon (a 100x reduction) and from 6.70 to 1.65 on Intel. Same hardware, same code, same inputs. This confound is methodological, not algorithm-specific, meaning it will produce false positives for ML-DSA, SLH-DSA, BIKE, HQC, and any algorithm evaluated with sequential collection.

A positive control against the known KyberSlash vulnerability confirms our methods detect real leakage. We release sca-triage, an open-source triage tool, and propose a two-stage evaluation protocol. Program managers and CISOs: your PQC migration timeline depends on fixing this test.

**Prior Work and Differentiation:**

Prior work (Schneider & Moradi, CHES 2015; Whitnall & Oswald) documented the detection-exploitability gap on evaluation boards. dudect (Reparaz et al., DATE 2017) already uses interleaved measurement. Dunsche et al. (USENIX Security 2024) and SILENT (arXiv 2025) reported TVLA failures on general-purpose CPUs. We isolate the root cause (temporal drift via sequential-vs-interleaved control), prove non-exploitability at scale, and provide a practical triage workflow for FIPS evaluation labs.
