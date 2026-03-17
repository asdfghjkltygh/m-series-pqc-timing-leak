# Black Hat CFP Abstracts

Three versions of the Call for Papers abstract (~300 words each). Select the version best suited to the review committee composition.

---

## Version A: "Compliance Crisis"

**Title:** When TVLA Lies: A FIPS 140-3 Compliance Crisis for Post-Quantum Cryptography

**Abstract:**

The industry-standard test for certifying post-quantum cryptography under FIPS 140-3 is broken, and it is about to delay PQC deployment across the entire federal supply chain.

NIST finalized ML-KEM (Kyber) as the post-quantum key encapsulation standard. Before any implementation ships in a FIPS-validated module, it must pass non-invasive side-channel evaluation per ISO 17825 — a test built on the Test Vector Leakage Assessment (TVLA) methodology. Every evaluation lab in the CMVP pipeline will run this test. Every one of them will get a failing result.

We ran ISO 17825 TVLA on liboqs, the most widely deployed open-source PQC library, across two major production platforms. Apple Silicon M-series produces |t| = 8.42 — nearly double the failure threshold. Intel x86 produces |t| = 12.95 — nearly triple. Taken at face value, these results block ML-KEM deployment for any FIPS-compliant organization. But the leakage is not real. We collected 12.2 million timing traces and applied every major side-channel attack technique — gradient-boosted classifiers, template attacks, convolutional neural networks, distributional tests, and information-theoretic bounds. Every technique, at every scale, on every target, performed at or below random guessing. The extractable secret information is exactly zero bits.

The root cause is an execution-context confound: TVLA's fixed-vs-random methodology confuses input-dependent microarchitectural optimization (DMP prefetching on Apple, cache replacement on Intel) with secret-dependent leakage. A positive control against the KyberSlash vulnerability (liboqs v0.9.0) confirms our pipeline detects real leakage when it exists — and that TVLA is broken in both directions, producing false positives on hardened code while the KyberSlash signal (d = 0.094) falls below its detection floor.

We release sca-triage, an open-source tool that automates TVLA false positive triage and generates auditor-ready HTML reports documenting the statistical justification for overriding a TVLA failure. If your company uses ML-KEM, an ignorant auditor will use ISO 17825, fail your product, and cost you six figures in remediation cycles. We are giving you the tool to prove the auditor wrong — and the two-stage evaluation protocol to make it standard practice. Organizations on CNSA 2.0 timelines cannot afford a compliance bottleneck built on a broken test.

**Prior Work and Differentiation:**

Prior work (Standaert et al., Whitnall & Oswald) documented the detection-exploitability gap in theory on evaluation boards. We systematically quantified the ISO 17825 failure rate specifically for the NIST ML-KEM standard under FIPS 140-3 testing conditions on shipping production hardware. Cross-platform replication (Apple ARM + Intel x86) with different root causes but identical TVLA failure modes is a systemic finding, not a platform curiosity. The positive control shows TVLA is broken in BOTH directions: false positives on hardened code AND the KyberSlash vulnerability (d = 0.094) falls below TVLA's detection floor while ML classification catches it. The FIPS 140-3 compliance angle transforms this from a research curiosity into a deployment-blocking problem with real-world consequences.

---

## Version B: "Broken Standard"

**Title:** The TVLA Mirage: Catastrophic False Positives in ISO 17825 on Modern Microarchitectures

**Abstract:**

ISO 17825 TVLA produces catastrophic false positives on modern processor architectures, and the root cause is fundamental to how the test interacts with speculative, out-of-order hardware.

We evaluated liboqs ML-KEM — the NIST-standardized post-quantum key encapsulation mechanism — using the fixed-vs-random Welch's t-test prescribed by ISO 17825. On Apple Silicon M-series, TVLA reports |t| = 8.42. On Intel Xeon x86, |t| = 12.95. Both results exceed the |t| > 4.5 failure threshold by wide margins. The industry-standard test for certifying post-quantum cryptography under FIPS 140-3 is broken: it reports critical timing leakage in ML-KEM where none exists.

We prove this through 100+ experiments spanning 14 independent lines of evidence across 12.2 million traces. Gradient-boosted trees, random forests, template attacks, CNNs, distributional tests, unsupervised clustering, and information-theoretic analyses all converge on the same result: zero exploitable information. Perceived Information is negative for all targets (-0.012 to -0.027 bits). KSG mutual information is 0.000 bits (p = 1.0). Vertical scaling to 15x the predicted minimum sample size shows flat accuracy curves. The signal TVLA detects cannot be converted into any form of key recovery.

The root cause is an execution-context confound present on both platforms. On Apple Silicon, the Data-Dependent Prefetcher synchronizes to fixed inputs, creating a deterministic timing signature. On Intel, cache replacement policies and speculative execution produce an inverted but analogous effect. In both cases, TVLA's fixed-vs-random design confuses input-dependent microarchitectural optimization with secret-dependent leakage. Pairwise decomposition by actual secret properties confirms: when the fixed-vs-random confound is removed, distributions are identical. A positive control against KyberSlash-vulnerable code validates our apparatus and demonstrates a cross-platform execution-context confound that will cause every evaluation lab to wrongly fail compliant implementations.

We propose a two-stage evaluation protocol with pairwise secret-group decomposition as a mandatory follow-up to TVLA failures, and release sca-triage, an open-source triage tool that distinguishes real leakage from microarchitectural mirages, preventing PQC deployment delays across the federal supply chain.

**Prior Work and Differentiation:**

Prior work (Standaert et al., Whitnall & Oswald) documented the detection-exploitability gap in theory on evaluation boards. We measured it at scale on shipping production hardware running the NIST-standardized PQC algorithm. Cross-platform replication (Apple ARM + Intel x86) with different root causes but identical TVLA failure modes is a systemic finding, not a platform curiosity. The positive control shows TVLA is broken in BOTH directions: false positives on hardened code AND the KyberSlash vulnerability (d = 0.094) falls below TVLA's detection floor while ML classification catches it. The FIPS 140-3 compliance angle transforms this from a research curiosity into a deployment-blocking problem with real-world consequences.

---

## Version C: "PQC Migration Under Threat"

**Title:** The False Positive Wall: Why Every PQC Migration Will Stall at Side-Channel Certification

**Abstract:**

Every organization migrating to post-quantum cryptography will hit the same wall: a mandatory side-channel test that fails correct, hardened code on every modern processor.

The post-quantum transition is underway. CNSA 2.0 mandates quantum-resistant algorithms by 2033. ML-KEM is shipping in browsers, operating systems, and cloud platforms. But before any implementation enters a FIPS-validated cryptographic module, it must pass ISO 17825 non-invasive side-channel evaluation — and on production hardware, it will fail. The industry-standard test for certifying post-quantum cryptography under FIPS 140-3 is broken. It reports critical timing leakage in ML-KEM where none exists, and it will do so for every evaluation lab running the test on Apple Silicon or Intel x86.

We quantified the problem: |t| = 8.42 on Apple M-series, |t| = 12.95 on Intel Xeon — both far above the failure threshold. We then spent 12.2 million traces and over 100 experiments trying to exploit the reported leakage. The result: zero extractable bits of secret information. No classifier, no statistical test, no information-theoretic bound found anything. The "leakage" is a microarchitectural mirage — an execution-context confound where TVLA's fixed-vs-random methodology confuses hardware optimization behavior (DMP prefetching, cache replacement) with secret-dependent timing variation. This confound is architectural, not algorithm-specific, meaning it will produce false positives for ML-DSA, SLH-DSA, BIKE, HQC, and any algorithm evaluated on modern hardware.

A positive control against the known KyberSlash vulnerability confirms our methods detect real leakage, and demonstrates a cross-platform execution-context confound that will cause every evaluation lab to wrongly fail compliant implementations. We release sca-triage, an open-source triage tool that distinguishes real leakage from microarchitectural mirages, preventing PQC deployment delays across the federal supply chain. We propose a two-stage evaluation protocol and call on evaluation labs, standards bodies, and CMVP to adopt it before false failures create an industry-wide bottleneck.

Program managers and CISOs: your PQC migration timeline depends on fixing this test. The algorithm is sound. The implementation is sound. The certification gate is not.

**Prior Work and Differentiation:**

Prior work (Standaert et al., Whitnall & Oswald) documented the detection-exploitability gap in theory on evaluation boards. We measured it at scale on shipping production hardware running the NIST-standardized PQC algorithm. Cross-platform replication (Apple ARM + Intel x86) with different root causes but identical TVLA failure modes is a systemic finding, not a platform curiosity. The positive control shows TVLA is broken in BOTH directions: false positives on hardened code AND the KyberSlash vulnerability (d = 0.094) falls below TVLA's detection floor while ML classification catches it. The FIPS 140-3 compliance angle transforms this from a research curiosity into a deployment-blocking problem with real-world consequences.
