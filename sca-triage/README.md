# sca-triage

**TVLA False Positive Triage Tool** -- Distinguishes real side-channel timing leakage from microarchitectural confounds in post-quantum cryptographic implementations.

When you run a standard TVLA (Test Vector Leakage Assessment) on modern CPUs -- especially Apple Silicon -- the test often *fails* even when the cryptographic implementation is perfectly constant-time. This tool figures out whether that failure is a real security problem or just the CPU's speculative execution and memory subsystem creating noise that looks like leakage. It does this by running the standard TVLA first, then decomposing the timing differences by secret key bits and checking whether any secret actually predicts the timing variation.

## Why This Matters

FIPS 140-3 and ISO 17825 require TVLA-style non-invasive testing for cryptographic module certification. Post-quantum algorithms like ML-KEM are now entering FIPS certification pipelines, and evaluators are discovering that Apple M-series chips (and some Intel platforms) produce systematic TVLA failures due to microarchitectural features like the Data Memory-Dependent Prefetcher (DMP) and speculative execution side effects.

These false positives have real costs:

- **Certification delays**: implementations get flagged as non-compliant, triggering expensive re-evaluation cycles
- **Wasted engineering effort**: developers spend weeks chasing phantom leaks that don't exist
- **Slowed PQC migration**: organizations delay adopting post-quantum cryptography because their hardware fails compliance testing

sca-triage provides a principled, three-stage statistical protocol to resolve these ambiguities in minutes rather than weeks.

## Installation

```bash
pip install sca-triage
```

For development:

```bash
git clone https://github.com/saahilshenoy/sca-triage.git
cd sca-triage
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1. Generate sample data (synthetic ML-KEM-768 timing traces)
python -m sca_triage.generate_sample_data

# 2. Run the full triage analysis
sca-triage analyze \
  --timing-data examples/sample_data/traces.csv \
  --secret-labels examples/sample_data/labels.csv \
  --targets sk_lsb \
  --output report.html

# 3. View the HTML report
open report.html
```

## How It Works

sca-triage runs a three-stage protocol:

**Stage 1: Standard TVLA** -- Runs the conventional Fixed-vs-Random Welch's t-test (ISO 17825). If |t| exceeds the 4.5 threshold, the implementation "fails" TVLA. But this failure might be a false positive, so we continue.

**Stage 2: Pairwise Secret-Group Decomposition** -- Groups the per-key mean timings by each bit of the secret key and runs a battery of two-sample tests (Welch's t, Mann-Whitney U, Kolmogorov-Smirnov, Anderson-Darling, Levene's) with Bonferroni correction. If the timing difference were caused by real leakage, at least one secret bit should show a statistically significant difference. If none do, the TVLA failure is likely a confound.

**Stage 3: Permutation Mutual Information** -- Estimates the mutual information between all aggregated timing features and secret labels using a KSG estimator, then tests significance via a label-permutation null distribution. This catches nonlinear or multi-feature dependencies that pairwise tests might miss.

## How to Interpret Results

### EXECUTION-CONTEXT CONFOUND (FALSE POSITIVE)

TVLA failed, but neither pairwise tests nor MI found any secret-dependent timing difference. The timing variation is caused by the measurement environment (DMP, speculative execution, cache state), not by secret-dependent computation. **The implementation is safe.** You can proceed with certification by documenting the confound source and attaching the sca-triage report.

### POTENTIAL REAL LEAKAGE -- INVESTIGATE

At least one secret-dependent test reached statistical significance. This could indicate genuine timing leakage that needs remediation. Check the per-target breakdown to identify which secret bits are leaking and at what effect size (Cohen's d). Small effect sizes (d < 0.2) with borderline significance may warrant additional measurement campaigns.

### NO LEAKAGE DETECTED

TVLA passed and no secret-dependent differences were found. The implementation shows no evidence of timing side-channel leakage.

## Demo Mode

For conference presentations and live demonstrations:

```bash
# Generate sample data first
python -m sca_triage.generate_sample_data

# Run the three-act demo (with dramatic pacing)
sca-triage demo \
  --timing-data examples/sample_data/traces.csv \
  --secret-labels examples/sample_data/labels.csv \
  --vuln-data examples/sample_data/vuln_traces.csv \
  --targets sk_lsb \
  --dark

# Use --precomputed for reliable stage timing (skips real computation)
sca-triage demo \
  --timing-data examples/sample_data/traces.csv \
  --secret-labels examples/sample_data/labels.csv \
  --targets sk_lsb \
  --precomputed
```

## Citation

If you use sca-triage in your research, please cite:

```bibtex
@inproceedings{shenoy2025tvla,
  title     = {The {TVLA} Mirage on Speculative Microarchitectures:
               Why {Apple Silicon} Fails {ISO}~17825 and What To Do About It},
  author    = {Shenoy, Saahil},
  booktitle = {Proceedings of the USENIX Security Symposium},
  year      = {2025},
  note      = {To appear}
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Links

- Paper: *Coming soon*
- Issue tracker: https://github.com/saahilshenoy/sca-triage/issues
