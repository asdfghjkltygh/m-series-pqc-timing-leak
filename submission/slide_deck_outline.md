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

**Key Message:** Both major platforms fail catastrophically — |t| = 8.42 on Apple, |t| = 12.95 on Intel.

**Visual:** Two large t-statistic values side by side. Left: Apple Silicon logo with "|t| = 8.42" in red. Right: Intel logo with "|t| = 12.95" in red. Horizontal dashed line at 4.5 labeled "FAILURE THRESHOLD." Both values tower above the line. Below: "liboqs v0.15.0 — the most widely used open-source PQC library."

**Speaker Notes:** "We ran the standard test on liboqs — the reference open-source PQC library that dozens of products integrate — on Apple Silicon and Intel x86. Apple gives us a t-statistic of 8.42. Intel gives us 12.95. Both are far above the 4.5 failure threshold. If you take these results at face value, ML-KEM is dead on arrival for every FIPS-compliant organization."

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

**Title:** The Execution-Context Confound

**Key Message:** TVLA confuses input-dependent microarchitectural optimization with secret-dependent leakage.

**Visual:** Diagram showing TVLA's assumption vs. reality. Left ("What TVLA assumes"): two boxes labeled "Fixed" and "Random" with arrow pointing to "Timing difference = secret leakage." Right ("What actually happens"): "Fixed" box with sub-labels (prefetcher locked, branch predictor converged, cache stable), "Random" box with sub-labels (prefetcher adapting, branch predictor retraining, cache churning). Arrow pointing to "Timing difference = CPU optimization state."

**Speaker Notes:** "Here's what's actually happening. TVLA assumes the only difference between fixed and random groups is the cryptographic input. On a smartcard, that's true. On a modern processor, it is catastrophically false. When you feed the same input repeatedly, the CPU's prefetcher locks on, the branch predictor converges, the cache stabilizes. When you feed random inputs, everything is constantly adapting. TVLA is measuring the difference between an optimized CPU and an unoptimized CPU. It has nothing to do with the secret key."

---

### Slide 10: Apple Silicon — The DMP Trap

**Title:** Apple Silicon: Data-Dependent Prefetcher Synchronization

**Key Message:** Apple's DMP locks onto fixed inputs creating bimodal timing — fast with rare catastrophic misses.

**Visual:** Two overlaid timing histograms. Blue histogram (random group): single symmetric peak, moderate spread. Red histogram (fixed group): sharp tall peak at fast end, with a long right tail of slow outliers. Annotation arrows: "DMP locked on — fast" pointing to the main peak, "DMP catastrophic miss — slow" pointing to the tail. Inset: "|t| = 8.42 — driven by the tail."

**Speaker Notes:** "On Apple Silicon, the villain is the Data-Dependent Prefetcher — the DMP. It examines data values and speculatively prefetches what it thinks are pointers. In the fixed group, the same data flows through every time. The DMP synchronizes and execution is fast — usually. But occasionally it makes a catastrophically wrong prediction and you get a timing outlier 10 times slower. In the random group, the DMP never synchronizes, so you get moderate consistent timing. The t-test compares means. The fixed group's mean is pulled up by those catastrophic misses. That's your |t| = 8.42."

---

### Slide 11: Intel x86 — The Cache Trap

**Title:** Intel x86: Cache Replacement Policy Thrashing

**Key Message:** Intel shows the SAME failure through a DIFFERENT mechanism — with inverted variance.

**Visual:** Same two-histogram layout but with inverted shapes. Blue histogram (random group): wider spread, higher variance. Red histogram (fixed group): tighter, lower variance. Annotation: "Variance ratio: 0.47x (fixed < random) — OPPOSITE of Apple." Side-by-side comparison table: Apple = high fixed variance, DMP-driven; Intel = high random variance, cache-driven. Both = TVLA failure.

**Speaker Notes:** "Intel shows the exact same TVLA failure through a completely different mechanism. On Intel, the cache replacement policy interacts with speculative execution to create the confound. And here's the kicker — the variance signature is inverted. On Apple, the fixed group has higher variance. On Intel, the random group has higher variance. Different mechanisms, opposite signatures, identical TVLA failure. That's how you know this is systemic, not a quirk of one chip."

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

**Visual:** Terminal screenshot (styled) showing three commands:
```
$ pip install sca-triage
$ sca-triage pairwise --traces data.npy --keys keys.npy
$ sca-triage mi --traces data.npy --keys keys.npy --permutations 10000
```
Below: sample JSON output snippet showing `"verdict": "FALSE_POSITIVE"` with `"mi": 0.000` and `"pairwise_max_t": 1.2`. GitHub logo + URL placeholder at bottom.

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

**Key Message:** Transitioning to terminal for a three-part demonstration.

**Visual:** Dark slide with terminal prompt icon. Text: "LIVE DEMO" in large font. Three numbered items: "1. TVLA on ML-KEM — watch it fail. 2. sca-triage pairwise — watch the confound disappear. 3. Positive control — watch it catch KyberSlash." Below: "All commands run on this machine, no pre-recorded output."

**Speaker Notes:** "Let's see this in action. I'm going to switch to a terminal and run three things. First, TVLA on ML-KEM — you'll see the |t| value exceed 4.5. Second, sca-triage pairwise decomposition — you'll see the signal disappear when we group by actual secret properties. Third, the positive control against KyberSlash — you'll see real leakage get detected. Everything runs live on this machine."

---

### Slide 18: Demo Screen (Terminal)

**Title:** [Terminal — full screen]

**Key Message:** Live execution of TVLA, sca-triage pairwise, and sca-triage MI.

**Visual:** Full-screen terminal. Pre-staged commands ready to paste:
```
# Act 1: TVLA fails
sca-triage tvla --traces ml_kem_traces.npy --labels fixed_random.npy

# Act 2: Pairwise decomposition — confound disappears
sca-triage pairwise --traces ml_kem_traces.npy --keys secret_keys.npy

# Act 3: Positive control — real leakage detected
sca-triage pairwise --traces kyberslash_traces.npy --keys ks_keys.npy
```

**Speaker Notes:** "Act 1: TVLA on patched ML-KEM. There's the t-statistic — well above 4.5. Standard says this is a fail. Act 2: now we run pairwise decomposition on the same traces. Group by key bit 0 vs key bit 1... t-statistic drops to under 1. Group by key byte... same thing. The confound is gone. Act 3: same tool, KyberSlash traces. Now watch the pairwise result — there's the signal. The tool catches real leakage when it exists."

---

### Slide 19: Demo Recap

**Title:** What You Just Saw

**Key Message:** TVLA fails safe code, sca-triage correctly triages the false positive, and the same tool catches real vulnerabilities.

**Visual:** Three-panel summary with green/red indicators:
1. "TVLA on ML-KEM v0.15.0: |t| > 4.5 -- TVLA says FAIL" (red X)
2. "sca-triage pairwise: no secret-dependent differences -- Verdict: FALSE POSITIVE" (green checkmark)
3. "sca-triage on KyberSlash: secret-dependent differences detected -- Verdict: REAL LEAKAGE" (red alert icon)

**Speaker Notes:** "To recap what you just saw: TVLA fails safe code. sca-triage correctly identifies the false positive. And when we give it actually vulnerable code, it catches it. The tool works in both directions. That's the two-stage protocol in action."

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

**Title:** The Confound Is Architectural, Not Algorithm-Specific

**Key Message:** TVLA will produce false positives for ML-DSA, SLH-DSA, BIKE, HQC, and any PQC scheme on modern hardware.

**Visual:** Grid of PQC algorithm names, each with a warning triangle: ML-KEM (tested -- confirmed), ML-DSA (predicted), SLH-DSA (predicted), BIKE (predicted), HQC (predicted). Below: "The confound comes from the CPU, not the algorithm. Any fixed-vs-random comparison on adaptive hardware will fail." Processor icons (Apple M-series, Intel, AMD, Qualcomm) with "?" marks on untested platforms.

**Speaker Notes:** "This is not an ML-KEM problem. The confound comes from the processor's adaptive microarchitecture — speculative execution, prefetching, cache replacement. It has nothing to do with lattices or any specific algorithm. Every PQC scheme evaluated with TVLA on modern hardware will produce false positives. ML-DSA, SLH-DSA, BIKE, HQC — all of them. Every evaluation lab should adopt the two-stage protocol for all PQC evaluations, not just ML-KEM."

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

1. **TVLA produces catastrophic false positives on Apple Silicon (|t|=8.42) and Intel x86 (|t|=12.95) for ML-KEM.**
2. **12.2 million traces and 100+ experiments confirm: zero exploitable bits of secret information.**
3. **Root cause: execution-context confound (DMP on Apple, cache thrashing on Intel) — TVLA measures CPU optimization, not secret leakage.**
4. **TVLA is broken in both directions: false positives on safe code, and KyberSlash (d=0.094) falls below its detection floor.**
5. **Fix: two-stage evaluation protocol + sca-triage open-source tool. Deploy PQC with confidence.**

**Speaker Notes:** "If you remember five things from this talk: TVLA fails ML-KEM on both major platforms. Twelve million traces prove the leakage is not real. The root cause is a microarchitectural confound, not a crypto weakness. TVLA is wrong in both directions — false positives on safe code and it misses the real KyberSlash vulnerability. And the fix is a two-stage protocol with an open-source tool you can use today."

---

### Slide 24: Q&A / Contact / Links

**Title:** Questions?

**Key Message:** How to reach the speaker, access the tool, and read the paper.

**Visual:** Clean contact slide:
- Name and affiliation
- Email
- GitHub: [sca-triage repository URL placeholder]
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
