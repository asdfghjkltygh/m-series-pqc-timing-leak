# sca-triage

**TVLA False Positive Triage Tool.** Distinguishes real side-channel timing leakage from temporal-drift confounds in post-quantum cryptographic implementations.

When you run a standard TVLA (Test Vector Leakage Assessment) on modern CPUs, the test often *fails* even when the cryptographic implementation is perfectly constant-time. The root cause is temporal drift from sequential data collection: the ISO 17825 protocol collects fixed and random measurements in separate blocks, and system state drifts between blocks. sca-triage runs TVLA, then decomposes the timing differences by secret key bits and checks whether any secret actually predicts the timing variation.

## Why This Matters

FIPS 140-3 and ISO 17825 require TVLA-style non-invasive testing for cryptographic module certification. Post-quantum algorithms like ML-KEM are entering FIPS certification pipelines, and evaluators are discovering that both Apple Silicon and Intel x86 produce systematic TVLA failures due to temporal drift in sequential measurement collection.

These false positives have real costs:

- **Certification delays**: implementations get flagged as non-compliant, triggering expensive re-evaluation cycles
- **Wasted engineering effort**: developers spend weeks chasing phantom leaks that don't exist
- **Slowed PQC migration**: organizations delay adopting post-quantum cryptography because their hardware fails compliance testing

sca-triage provides a principled, three-stage statistical protocol to resolve these ambiguities in minutes rather than weeks.

## Installation

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# Run on the repo's pre-collected TVLA traces
sca-triage analyze --timing-data ../data/tvla_traces.npz --targets sk_lsb --quick

# Full pipeline with all three stages
sca-triage analyze \
  --timing-data ../data/tvla_traces.npz \
  --targets sk_lsb \
  --output report.html
```

## How It Works

sca-triage runs a three-stage protocol:

**Stage 1: Standard TVLA.** Runs the conventional Fixed-vs-Random Welch's t-test (ISO 17825). If |t| exceeds the 4.5 threshold, the implementation "fails" TVLA. But this failure might be a false positive from temporal drift, so we continue.

**Stage 2: Pairwise Secret-Group Decomposition.** Groups the per-key mean timings by each bit of the secret key and runs a battery of two-sample tests (Welch's t, Mann-Whitney U, Kolmogorov-Smirnov, Anderson-Darling, Levene's) with Bonferroni correction. If the timing difference were caused by real leakage, at least one secret bit should show a statistically significant difference. If none do, the TVLA failure is a temporal-drift false positive.

**Stage 3: Permutation Mutual Information.** Estimates the mutual information between all aggregated timing features and secret labels using a KSG estimator, then tests significance via a label-permutation null distribution. This catches nonlinear or multi-feature dependencies that pairwise tests might miss.

## How to Interpret Results

### FALSE POSITIVE (Temporal Drift Confound)

TVLA failed, but neither pairwise tests nor MI found any secret-dependent timing difference. The timing variation is caused by temporal drift in sequential data collection, not by secret-dependent computation. **The implementation is safe.** You can proceed with certification by documenting the confound source and attaching the sca-triage report.

### POTENTIAL REAL LEAKAGE: INVESTIGATE

At least one secret-dependent test reached statistical significance. This could indicate genuine timing leakage that needs remediation.

### NO LEAKAGE DETECTED

TVLA passed and no secret-dependent differences were found. The implementation shows no evidence of timing side-channel leakage.

## Demo Mode

For conference presentations and live demonstrations:

```bash
# Run the four-act demo (with dramatic pacing)
sca-triage demo \
  --timing-data ../data/tvla_traces.npz \
  --precomputed
```

## License

MIT License. See [LICENSE](LICENSE) for details.
