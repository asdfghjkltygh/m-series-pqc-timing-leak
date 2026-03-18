# x86-64 TVLA Control Experiment

**Purpose:** Replicate the TVLA false positive analysis on Intel x86-64 and run the
symmetric harness control experiment to confirm the confound is architectural.

**Result:** Both asymmetric (|t|=5.35) and symmetric (|t|=6.70) harnesses fail TVLA
on Intel x86, confirming the confound is architectural on both platforms.

## Quick Start

On an x86-64 Linux machine:

```bash
# 1. Install prerequisites
sudo apt-get install -y build-essential cmake git libssl-dev python3-pip
pip3 install numpy scipy

# 2. Build everything (clones + compiles liboqs 0.15.0, compiles all harnesses)
chmod +x build.sh
./build.sh

# 3. Run the symmetric control experiment (~30 min)
python3 ../scripts/intel_symmetric_control.py

# 4. Run the full asymmetric TVLA analysis (~1-2 hours for 500K traces)
python3 tvla_analysis_x86.py --traces 500000
```

## Files

### C Harnesses

| File | Description |
|------|-------------|
| `tvla_harness_x86.c` | **Asymmetric** TVLA harness. Random mode runs keygen+encaps before each timed decaps. Fixed mode reuses one (ct, sk) pair. Uses RDTSC with CPUID serialization. |
| `tvla_harness_symmetric_x86.c` | **Symmetric** TVLA harness. Pre-generates ALL random (ct, sk) pairs into memory arrays before measurement. Both modes execute identical code paths during the timed loop. Isolates architectural confound from harness-induced cache pollution. |
| `timer_profile_x86.c` | RDTSC timer resolution profiler. Measures back-to-back overhead (10M samples). Validates timer is sufficient for crypto timing measurement. |

Usage for both harnesses:
```bash
./tvla_harness_x86 <fixed|random> <num_traces>
./tvla_harness_symmetric_x86 <fixed|random> <num_traces>
# Outputs one cycle count per line to stdout, progress to stderr.
```

### Python Scripts

| File | Description |
|------|-------------|
| `../scripts/intel_symmetric_control.py` | **Symmetric control experiment.** Runs both harnesses (50K traces per mode), computes TVLA, outputs formatted results with markdown tables and cross-platform comparison. |
| `tvla_analysis_x86.py` | Full asymmetric TVLA analysis with progressive sample sizes, quantile filtering, and Apple Silicon comparison. |
| `analyze_x86.py` | Standalone trace analyzer. Loads `fixed_traces.txt` / `random_traces.txt`, computes Welch's t-test, progressive analysis, and cross-platform comparison. |

### Build

| File | Description |
|------|-------------|
| `build.sh` | One-command build. Clones liboqs 0.15.0, compiles it, then compiles all three C harnesses. |

### Data (in `../data/`)

| File | Description |
|------|-------------|
| `tvla_x86_results.json` | 500K-trace asymmetric TVLA results (\|t\|=12.95, variance ratio 0.47x) |
| `x86_fixed_traces.txt` | 500K raw fixed-mode timing traces (gitignored, 2.9MB) |
| `x86_random_traces.txt` | 500K raw random-mode timing traces (gitignored, 2.9MB) |

## Key Results

### Asymmetric Harness (500K traces)

|t| = 12.95, variance ratio = 0.47x (random > fixed). TVLA **FAIL**.

### Symmetric Control (50K traces)

| Harness | |t| | Variance Ratio | TVLA Verdict |
|---------|-----|----------------|--------------|
| Asymmetric | 5.35 | 1.84x | **FAIL** |
| Symmetric | 6.70 | 0.43x | **FAIL** |

Both harnesses fail. The symmetric harness produces a *higher* t-statistic, confirming the Intel confound is **architectural**, not solely harness-induced.

### Cross-Platform Comparison

| Platform | Asymmetric |t| | Symmetric |t| | Variance Signature |
|----------|----------------|----------------|-------------------|
| Apple Silicon | 3.00 (PASS) | 62.49 (FAIL) | Fixed > Random (7.71x) |
| Intel x86 | 5.35 (FAIL) | 6.70 (FAIL) | Random > Fixed (0.43x) |

Different mechanisms, opposite variance signatures, same conclusion: TVLA produces false positives on production hardware regardless of harness design.

## Compilation (Manual)

If not using `build.sh`:

```bash
# Adjust LIBOQS_PREFIX to your liboqs install location
LIBOQS_PREFIX=./liboqs-install

gcc -O2 -march=native \
    -I${LIBOQS_PREFIX}/include \
    -o tvla_harness_x86 tvla_harness_x86.c \
    ${LIBOQS_PREFIX}/lib/liboqs.a \
    -lssl -lcrypto -lm -lpthread

gcc -O2 -march=native \
    -I${LIBOQS_PREFIX}/include \
    -o tvla_harness_symmetric_x86 tvla_harness_symmetric_x86.c \
    ${LIBOQS_PREFIX}/lib/liboqs.a \
    -lssl -lcrypto -lm -lpthread

gcc -O2 -march=native -o timer_profile_x86 timer_profile_x86.c -lm
```

## Troubleshooting

- **"ML-KEM-768 not available"**: liboqs wasn't built with ML-KEM. Rebuild without disabling it.
- **Linker errors**: Ensure `-lssl -lcrypto -lm -lpthread` are all present.
- **Noisy results**: Set CPU governor to performance (`sudo cpupower frequency-set -g performance`), disable turbo (`echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo`), pin to single core (`taskset -c 0 ./tvla_harness_symmetric_x86 fixed 50000`).
