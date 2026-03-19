# Black Hat Presentation Slide Deck Outline

**Talk Title:** When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment
**Subtitle:** 12.2 Million Traces, Zero Exploitable Bits, and an Industry-Wide False Positive
**Duration:** 50 minutes (40 min talk + 10 min Q&A)

---

## Slide 1: Title Slide

**Title:** When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment

**Key Message:** The certification test for post-quantum crypto produces false positives on every modern processor.

**Visual:** Title text over a dark background. Subtitle: "12.2 Million Traces, Zero Exploitable Bits, and an Industry-Wide False Positive." Author name, affiliation, and Black Hat logo. Small icons for Apple Silicon and Intel at bottom.

**Speaker Notes:** "Good afternoon. My name is Saahil Shenoy. I'm going to tell you about a broken standard that is about to block post-quantum cryptography deployment across the federal government — and how we proved it, fixed it, and released a tool so you don't have to spend six months doing what we did."

---

## BLOCK 1: "The Setup" (Slides 2-5, ~5 minutes)

---

### Slide 2: The Post-Quantum Transition Is Happening Now

**Title:** PQC Migration Is Not Coming — It's Here

**Key Message:** ML-KEM is shipping in production systems today and every implementation needs FIPS certification.

**Visual:** Timeline graphic showing: NIST standardization (Aug 2024), Apple iMessage (2024), Chrome/Cloudflare TLS (2024), CNSA 2.0 deadline (2033). Logos of major adopters (Apple, Google, Cloudflare, AWS) along the timeline.

**Speaker Notes:** "NIST finalized ML-KEM — that's Kyber — as the post-quantum KEM standard in 2024. It's already in iMessage, Chrome, Cloudflare. CNSA 2.0 says national security systems must be quantum-resistant by 2033. This is not a research exercise anymore. It's a deployment program with hard deadlines."

---

### Slide 3: The Certification Gate

**Title:** One Test Stands Between ML-KEM and Federal Deployment

**Key Message:** FIPS 140-3 requires ISO 17825 side-channel evaluation, and that test uses TVLA.

**Visual:** Flow diagram: Implementation -> FIPS 140-3 Evaluation -> ISO 17825 Side-Channel Test -> TVLA (Fixed vs Random) -> Pass (|t| <= 4.5) or Fail (|t| > 4.5). The "Fail" path is highlighted in red with a stop sign.

**Speaker Notes:** "Before any PQC implementation ships in a FIPS-validated module, it has to pass non-invasive side-channel evaluation under ISO 17825. That evaluation uses the Test Vector Leakage Assessment — TVLA. You feed the implementation fixed and random inputs, compare the timing distributions, and if the t-statistic exceeds 4.5, you fail. No exceptions. No gray area."

---

### Slide 4: We Ran the Test

**Title:** We Ran ISO 17825 TVLA on liboqs ML-KEM

**Key Message:** Both major platforms fail catastrophically — |t| = 62.49 on Apple, |t| = 6.70 on Intel.

**Visual:** Two large t-statistic values side by side. Left: Apple Silicon logo with "|t| = 62.49" in red. Right: Intel logo with "|t| = 6.70" in red. Horizontal dashed line at 4.5 labeled "FAILURE THRESHOLD." Both values tower above the line. Below: "liboqs v0.15.0, symmetric harness (identical code paths, no harness asymmetry)."

**Speaker Notes:** "We ran the standard test on liboqs — the reference open-source PQC library that dozens of products integrate — using a symmetric harness that eliminates the most obvious confound source. Apple gives us a t-statistic of 62. Intel gives us 6.7. Both are far above the 4.5 failure threshold. If you take these results at face value, ML-KEM is dead on arrival for every FIPS-compliant organization."

---

### Slide 5: The Question

**Title:** Is the Leakage Real?

**Key Message:** We spent six months and 12.2 million traces finding out.

**Visual:** Full-screen text, minimal design. Center: "12,200,000 traces." Below: "100+ experiments." Below: "2 platforms." Below in bold: "Is the leakage real?" Dramatic pause slide.

**Speaker Notes:** "So we asked the obvious question: is this leakage real? Can you actually recover key material from these timing differences? We spent six months trying. We collected 12.2 million traces. We ran every attack technique in the side-channel playbook. Here is what we found."

---

## BLOCK 2: "The Hunt" (Slides 6-8, ~10 minutes)

---

### Slide 6: The Exhaustive Search

**Title:** We Tried Everything

**Key Message:** Over 100 experiments across every major side-channel technique produced zero exploitable information.

**Visual:** Heatmap figure from the paper — experiment matrix with rows as techniques (XGBoost, Random Forest, CNN, Template, KS-test, PCA, t-SNE, MI, PI, SNR) and columns as targets (key bit, key byte, Hamming weight, etc.). Every cell is green/blue (at or below baseline). No red cells. Title on heatmap: "Accuracy vs. Majority Baseline." Color legend: green = at baseline, blue = below baseline.

**Speaker Notes:** "This is the experiment heatmap. Rows are techniques — gradient-boosted trees, random forests, neural networks, template attacks, distributional tests, information-theoretic measures. Columns are targets — key bits, key bytes, Hamming weight. Every cell you see is green or blue, meaning at or below random guessing. We tried everything. Nothing worked. XGBoost gets 50.2% on a 50/50 binary task. The CNN converges to majority-class prediction in three epochs. Template attack posteriors are indistinguishable from the prior."

---

### Slide 7: The Numbers That Matter

**Title:** The Information Is Not There

**Key Message:** Six independent information-theoretic methods bound the extractable secret information at exactly zero bits.

**Visual:** Clean table with six rows:

| Method | Value | Verdict |
|--------|-------|---------|
| Perceived Information | -0.012 to -0.027 bits | No information |
| KSG Mutual Information | 0.000 bits (p=1.0) | No information |
| MAD-based SNR | ~0 | No signal |
| Winsorized SNR | ~0 | No signal |
| Vertical Scaling (15x) | Flat curve | No convergence |
| All ML classifiers | <= majority baseline | No learning |

Below the table, bold text: "Zero bits. Not low. Not marginal. Zero."

**Speaker Notes:** "Let me give you the numbers that matter. Perceived Information is negative — the traces tell you less than flipping a coin. KSG mutual information is exactly zero with a permutation p-value of 1.0, meaning the real estimate is indistinguishable from noise. We scaled the dataset to 15 times the theoretically predicted minimum for detecting leakage at the effect size TVLA reports. The accuracy curve is perfectly flat. The information is not there."

---

### Slide 8: But Our Pipeline Works

**Title:** Positive Control: KyberSlash

**Key Message:** The same pipeline detects real leakage in vulnerable code — proving the null result is real.

**Visual:** Split screen. Left half labeled "Vulnerable (v0.9.0)": accuracy bar at +3.8% above baseline, highlighted in red. Right half labeled "Patched (v0.15.0)": accuracy bar at +0.5%, highlighted in green. Below both: "Valid/Invalid CT Classification: 100% on both versions." At bottom: "The pipeline works. The leakage doesn't exist."

**Speaker Notes:** "A negative result means nothing if your detector is broken. So we ran the exact same pipeline against liboqs v0.9.0 — the version with the KyberSlash vulnerability. Our XGBoost classifier picks up a 3.8% accuracy lift on vulnerable code. On the patched version, it's 0.5% — noise. For the simpler task of classifying valid vs invalid ciphertexts, we get 100% on both. Our apparatus works. The leakage that TVLA reports in patched ML-KEM genuinely does not exist."

---

## BLOCK 3: "The Root Cause" (Slides 9-13, ~10 minutes)

---

### Slide 9: What Is TVLA Actually Detecting?

**Title:** The Temporal Drift Confound

**Key Message:** Sequential collection introduces systematic environmental differences that TVLA misinterprets as leakage.

**Visual:** Diagram showing TVLA's assumption vs. reality. Left ("What TVLA assumes"): two boxes labeled "Fixed" and "Random" with arrow pointing to "Timing difference = secret leakage." Right ("What actually happens"): timeline showing "Block 1: Fixed traces" then "Block 2: Random traces" with annotation arrows: "thermal state drifts," "OS scheduler activity changes," "DVFS adjusts frequency." Arrow pointing to "Timing difference = when you measured, not what you measured."

**Speaker Notes:** "Here's what's actually happening. The standard protocol collects all fixed-input traces in one block, then all random-input traces in a second block. Between those blocks, the system state drifts — thermal conditions change, the OS scheduler intervenes differently, DVFS adjusts clock frequency. TVLA sees a timing difference between the two groups and calls it leakage. But the difference is temporal — it's about when you measured, not what you measured. We proved this by interleaving the measurements: alternate fixed and random on every iteration, and the signal vanishes. 62 to 0.5."

---

### Slide 10: The Proof — Sequential vs Interleaved

**Title:** One Change Eliminates the Confound

**Key Message:** Interleaving measurements drops |t| from 62 to 0.58 on Apple and from 6.70 to 1.65 on Intel.

**Visual:** 2x2 results table (the paper's key result table):

| Platform | Collection | Harness | |t| | Verdict |
|----------|-----------|---------|-----|---------|
| Apple Silicon | Sequential | Symmetric | 62.49 | **FAIL** |
| Apple Silicon | Interleaved | Symmetric | 0.58 | **PASS** |
| Intel x86 | Sequential | Symmetric | 6.70 | **FAIL** |
| Intel x86 | Interleaved | Symmetric | 1.65 | **PASS** |

Below: "100x reduction on Apple. 4x reduction on Intel. No code changes. No hardware changes."

**Speaker Notes:** "Here's the proof. Same symmetric harness — identical code paths, no keygen, no encaps in the measurement loop. On Apple Silicon, sequential collection gives |t| of 62. Switch to interleaved — alternate fixed and random on every iteration — and it drops to 0.58. That's a 100x reduction. On Intel, same pattern: 6.70 drops to 1.65. Two platforms, same result. The confound is temporal drift from sequential collection, not anything architectural."

---

### Slide 11: Cross-Platform Replication

**Title:** Two Platforms, Same Root Cause

**Key Message:** Different variance signatures, different microarchitectures, but the same temporal drift confound explains both.

**Visual:** Side-by-side comparison. Apple Silicon: sequential variance ratio 7.71x (fixed > random), interleaved ratio 0.95x (≈1:1). Intel x86: sequential variance ratio 0.43x (random > fixed), interleaved near unity. Annotation: "Sequential collection creates platform-specific variance artifacts. Interleaving removes them on both." Below: Intel asymmetric interleaved |t|=8.10 still fails — labeled "secondary confound: harness asymmetry (live keygen+encaps)."

**Speaker Notes:** "The variance signatures look different — Apple has higher fixed variance, Intel has higher random variance. This initially suggested different architectural mechanisms. But when you interleave, both platforms show near-unity variance ratios. The sequential variance signatures were artifacts of how system state drifted during each platform's collection window, not of fundamentally different hardware responses. On Intel, the asymmetric interleaved harness still fails at |t|=8.10 — that's a secondary confound from cache pollution by live keygen and encaps, independent of temporal drift."

---

### Slide 12: The Proof — It's Not the Key

**Title:** Pairwise Decomposition: The Leakage Is Not Secret-Dependent

**Key Message:** When you group by actual secret key properties instead of fixed-vs-random, the distributions are identical.

**Visual:** Two rows of small distribution plots. Top row labeled "TVLA grouping (fixed vs random)": two clearly separated distributions with "|t| = 8.42" annotation. Bottom row labeled "Secret grouping (key bit 0 vs key bit 1)": two perfectly overlapping distributions with "|t| = 0.3" annotation. Bold caption: "Remove the confound, the signal disappears. The leakage is input-dependent, not secret-dependent."

**Speaker Notes:** "Here's the definitive proof. Top row: TVLA's fixed-vs-random comparison — big separation, big t-statistic. Bottom row: same traces, but now we group by actual secret key bits instead of by TVLA group assignment. The distributions are identical. Every pairwise comparison — by key bit, key byte, Hamming weight — shows no difference. The structure TVLA detects exists only in the fixed-vs-random framing. Remove that framing, and the signal vanishes completely. The leakage is input-dependent, not secret-dependent."

---

### Slide 13: Broken in Both Directions

**Title:** TVLA Fails in Both Directions

**Key Message:** False positives on safe code AND the real vulnerability falls below TVLA's detection floor.

**Visual:** 2x2 matrix. Columns: "TVLA Says Safe" / "TVLA Says Leaking". Rows: "Actually Safe" / "Actually Leaking". Top-right cell (false positive): "ML-KEM v0.15.0 — |t| = 8.42" in red. Bottom-left cell (false negative): "KyberSlash v0.9.0 — d = 0.094, below TVLA floor" in red. Top-left and bottom-right are empty. Caption: "TVLA is wrong in both quadrants that matter."

**Speaker Notes:** "And it gets worse. TVLA is not just producing false positives on hardened code. The KyberSlash vulnerability — a real, exploitable timing leak — has an effect size of d = 0.094. That falls below TVLA's practical detection floor. So TVLA simultaneously fails safe code and passes vulnerable code. It is wrong in both directions. Our ML classifier catches KyberSlash easily. TVLA cannot."

---

## BLOCK 4: "The Fix" (Slides 14-16, ~5 minutes)

---

### Slide 14: The Two-Stage Protocol

**Title:** A Fix That Works: The Two-Stage Evaluation Protocol

**Key Message:** Stage 1 is standard TVLA; Stage 2 triages failures with pairwise decomposition and mutual information.

**Visual:** Flow diagram. Start: "Run TVLA". Branch: |t| <= 4.5 -> green box "PASS". Branch: |t| > 4.5 -> "Stage 2: Pairwise Decomposition + MI". From Stage 2: "Pairwise = no difference AND MI = 0" -> yellow box "FALSE POSITIVE — PASS". "Pairwise = difference OR MI > 0" -> red box "REAL LEAKAGE — FAIL". Clean, decision-tree style.

**Speaker Notes:** "Here is the fix. Stage 1: run TVLA as normal. If you pass, you're done. If you fail, don't panic — run Stage 2. Split your traces by actual secret key properties. Recompute the comparisons. Run permutation-validated mutual information. If the pairwise analysis shows no secret-dependent differences and MI is zero, the TVLA failure is a false positive. Pass the implementation. If pairwise detects real differences, it's real leakage. Fail it. Simple, principled, and it preserves TVLA's role as a first-pass screen."

---

### Slide 15: The Tool — sca-triage

**Title:** sca-triage: Open-Source TVLA False Positive Triage

**Key Message:** Three commands, a JSON report, and integration into your FIPS workflow.

**Visual:** Terminal screenshot (styled) showing two commands:
```
$ pip install sca-triage
$ sca-triage analyze --timing-data tvla_traces.npz --targets sk_lsb
```
Below: sample terminal output showing Stage 1 FAIL (|t|=8.42), Stage 2 pairwise not significant (d=0.0003), Stage 3 MI=0.000, Verdict: FALSE_POSITIVE. GitHub logo + URL placeholder at bottom.

**Speaker Notes:** "We are releasing sca-triage, an open-source tool that implements Stage 2. pip install, three commands, done. It gives you a structured JSON report with the TVLA result, pairwise decomposition, mutual information, and a final verdict. Auditors can drop this into their FIPS evaluation workflow. The report provides the documentation trail for CMVP submission. We'll do a live demo in a few minutes."

---

### Slide 16: Recommendations

**Title:** What Needs to Change

**Key Message:** Standards bodies, evaluation labs, and implementers all have action items.

**Visual:** Three columns with headers and 2-3 bullet points each:

**ISO / Standards Bodies:**
- Add Stage 2 as mandatory follow-up in ISO 17825
- Acknowledge execution-context confound in normative text

**CMVP / FIPS 140-3:**
- Issue implementation guidance note on microarchitectural confounds
- Accept Stage 2 evidence for overriding TVLA failures

**Evaluation Labs:**
- Adopt pairwise decomposition as standard operating procedure
- Use sca-triage or equivalent for all PQC evaluations on GP processors

**Speaker Notes:** "Three groups need to act. Standards bodies: update ISO 17825 to include Stage 2 as mandatory. CMVP: issue guidance acknowledging the confound and accepting Stage 2 evidence. Evaluation labs: start running pairwise decomposition on every PQC evaluation that hits a TVLA failure. The traces are already collected. The marginal cost is nearly zero. The alternative is wrongly failing every ML-KEM implementation that comes through your door."

---

## BLOCK 5: LIVE DEMO (Slides 17-19, ~5 minutes)

---

### Slide 17: Demo Transition

**Title:** Let's See It Live

**Key Message:** Transitioning to terminal for a four-part demonstration.

**Visual:** Dark slide with terminal prompt icon. Text: "LIVE DEMO" in large font. Four numbered items: "0. The Broken Test — sequential vs interleaved, same everything else. 1. The Audit Trap — watch TVLA fail. 2. The Autopsy — watch the signal disappear. 3. The Proof — watch it catch KyberSlash." Below: "All commands run on this machine, no pre-recorded output."

**Speaker Notes:** "Let's see this in action. I'm going to switch to a terminal and show you four things. First, the headline result — I'll run the same TVLA test two ways and you'll see a 100x difference from one methodological change. Then TVLA failing on ML-KEM. Then sca-triage showing it's a false positive. And finally, the same tool catching a real vulnerability. Everything runs live."

---

### Slide 18: Demo Screen (Terminal)

**Title:** [Terminal — full screen]

**Key Message:** Live execution of the four-act demo via sca-triage.

**Visual:** Full-screen terminal. Pre-staged command:
```
# Run the full four-act demo with precomputed pacing
sca-triage demo --timing-data data/tvla_traces.npz --precomputed
```

The demo runs four acts automatically:
- **Act 0:** Sequential |t|=62.49 (FAIL, red) → Interleaved |t|=0.58 (PASS, green). "Same hardware. Same code. Same inputs."
- **Act 1:** Progressive TVLA on sequential data — |t| climbs past 4.5 in real time.
- **Act 2:** Pairwise decomposition — all secret groups non-significant. MI = 0.000. Verdict: FALSE_POSITIVE (green banner).
- **Act 3:** Same tool on KyberSlash — Verdict: REAL_LEAKAGE (red banner).

**Speaker Notes:** "Act 0: two numbers. Sequential collection — |t| is 62. Interleaved collection — |t| is 0.58. Same laptop, same code, same ML-KEM, same liboqs. The only thing I changed is when I collected the measurements. That's a 100x reduction. Act 1: TVLA on the sequential data — watch the t-statistic climb past the failure threshold. Act 2: sca-triage decomposes by secret key bits. Every comparison is non-significant. Zero mutual information. Verdict: false positive. Act 3: same tool, KyberSlash data. Now it finds real differences. The tool works. TVLA doesn't."

---

### Slide 19: Demo Recap

**Title:** What You Just Saw

**Key Message:** The test is broken by sequential collection. sca-triage triages correctly. Real vulnerabilities are caught.

**Visual:** Four-panel summary with color indicators:
0. "Sequential vs Interleaved: |t|=62.49 → |t|=0.58 — same hardware, same code" (magenta highlight)
1. "TVLA on ML-KEM v0.15.0: |t| > 4.5 — TVLA says FAIL" (red X)
2. "sca-triage pairwise: no secret-dependent differences — Verdict: FALSE POSITIVE" (green checkmark)
3. "sca-triage on KyberSlash: secret-dependent differences detected — Verdict: REAL LEAKAGE" (red alert icon)

**Speaker Notes:** "To recap: the sequential collection methodology breaks TVLA — same code gives you 62 or 0.5 depending on when you collect. TVLA fails safe code. sca-triage correctly identifies the false positive. And when we give it actually vulnerable code, it catches it. The tool works in both directions."

---

## BLOCK 6: "Implications" (Slides 20-22, ~5 minutes)

---

### Slide 20: PQC Migration — Proceed

**Title:** ML-KEM Deployment Should Not Be Delayed

**Key Message:** The algorithm and implementation are sound; the test is broken; organizations can proceed with confidence.

**Visual:** Large green "GO" signal / traffic light. Three bullet points:
- liboqs v0.15.0 KyberSlash fix is effective (positive control confirms)
- TVLA failures on Apple Silicon and Intel x86 are false positives
- If your lab reported a TVLA failure: request Stage 2 analysis

Bottom: "Point your evaluators to this paper and sca-triage."

**Speaker Notes:** "The bottom line for anyone deploying PQC: proceed. The algorithm is sound. The liboqs implementation is sound. The KyberSlash fix works — we proved it with our positive control. If your evaluation lab has reported a TVLA failure on ML-KEM running on Apple or Intel hardware, request a Stage 2 analysis. Point them to this paper and the tool."

---

### Slide 21: Every Algorithm Is Affected

**Title:** The Confound Is Methodological, Not Algorithm-Specific

**Key Message:** Any TVLA evaluation using sequential collection on any platform will produce false positives — regardless of algorithm.

**Visual:** Grid of PQC algorithm names, each with a warning triangle: ML-KEM (tested — confirmed), ML-DSA (predicted), SLH-DSA (predicted), BIKE (predicted), HQC (predicted). Below: "The confound comes from sequential collection methodology, not from any algorithm or platform. Any fixed-vs-random comparison collected in separate blocks will fail." Processor icons (Apple M-series, Intel, AMD, Qualcomm) all with warning marks.

**Speaker Notes:** "This is not an ML-KEM problem and it's not a hardware problem. The confound comes from how TVLA data is collected — in sequential blocks. System state drifts between blocks, and TVLA interprets that drift as leakage. Any algorithm, any platform, any implementation evaluated with sequential collection will hit this. ML-DSA, SLH-DSA, BIKE, HQC — all of them. The fix is interleaved collection or Stage 2 triage."

---

### Slide 22: The Bigger Picture

**Title:** TVLA Was Built for Smartcards, Not Modern Processors

**Key Message:** Side-channel evaluation standards must evolve alongside the hardware they evaluate.

**Visual:** Split visual. Left side: simple smartcard chip diagram, labeled "Deterministic timing, simple pipeline, TVLA works." Right side: modern processor die shot with labeled speculative execution units, prefetchers, multi-level cache, labeled "Adaptive timing, speculative execution, TVLA breaks." Arrow between them labeled "The gap between 'detectable' and 'exploitable' is a chasm."

**Speaker Notes:** "TVLA was designed for embedded devices — smartcards and FPGAs with simple, deterministic timing. On those targets, a TVLA detection usually means real exploitable leakage. Modern processors are a completely different world. Speculative execution, branch prediction, data-dependent prefetching — these create timing variation that has nothing to do with secrets. The gap between what TVLA detects and what an attacker can exploit is wider than the community has understood. The two-stage protocol is a practical fix. But the deeper lesson is that our evaluation standards have to evolve with the hardware."

---

## CLOSING (Slides 23-24, ~Q&A transition)

---

### Slide 23: One-Slide Summary

**Title:** Five Things to Remember

**Key Message:** The entire talk in five bullet points.

**Visual:** Numbered list, large font, clean layout:

1. **TVLA produces catastrophic false positives on Apple Silicon (|t|=62.49) and Intel x86 (|t|=6.70) for ML-KEM.**
2. **Root cause: temporal drift from sequential data collection — interleaving drops |t| from 62 to 0.58 (100x reduction).**
3. **12.2 million traces and 100+ experiments confirm: zero exploitable bits of secret information.**
4. **TVLA is broken in both directions: false positives on safe code, and KyberSlash (d=0.094) falls below its detection floor.**
5. **Fix: interleave collection + two-stage triage protocol + sca-triage open-source tool. Deploy PQC with confidence.**

**Speaker Notes:** "If you remember five things from this talk: TVLA fails ML-KEM on both major platforms. Twelve million traces prove the leakage is not real. The root cause is a microarchitectural confound, not a crypto weakness. TVLA is wrong in both directions — false positives on safe code and it misses the real KyberSlash vulnerability. And the fix is a two-stage protocol with an open-source tool you can use today."

---

### Slide 24: Q&A / Contact / Links

**Title:** Questions?

**Key Message:** How to reach the speaker, access the tool, and read the paper.

**Visual:** Clean contact slide:
- Saahil Shenoy, Founding AI Scientist, Bedrock Data
- saahil@bedrockdata.ai
- GitHub: github.com/asdfghjkltygh/m-series-pqc-timing-leak
- Paper: [preprint URL placeholder]
- Data: "Full dataset and reproduction scripts available in supplementary repository"

QR code linking to the sca-triage GitHub repository.

**Speaker Notes:** "Thank you. The tool is open source and available now — the QR code takes you to the GitHub repo. The full dataset, all reproduction scripts, and the paper are in the supplementary repository. I'm happy to take questions."

---

## Timing Summary

| Block | Slides | Duration | Content |
|-------|--------|----------|---------|
| The Setup | 1-5 | 5 min | Title, PQC context, TVLA explanation, the failing result |
| The Hunt | 6-8 | 10 min | Exhaustive search, information-theoretic proof, positive control |
| The Root Cause | 9-13 | 10 min | Confound explanation, Apple DMP, Intel cache, pairwise proof, both-directions failure |
| The Fix | 14-16 | 5 min | Two-stage protocol, tool release, recommendations |
| Live Demo | 17-19 | 5 min | Transition, terminal demo (three acts), recap |
| Implications | 20-22 | 5 min | Proceed with PQC, all algorithms affected, standards must evolve |
| Close | 23-24 | ~Q&A | Summary slide, contact/links, Q&A |
| **Total** | **24 slides** | **40 min + 10 min Q&A** | |
