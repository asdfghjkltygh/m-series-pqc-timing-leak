# Reproduce Core Results

## 1-Click Docker Reproduction (Recommended)

No host dependencies required. Docker builds liboqs, compiles harnesses, installs sca-triage, and runs all experiments:

```bash
docker-compose up --build run-all-experiments
```

Results are written to `data/` and `figures/` via volume mount. Total runtime: ~5 minutes.

To run a single experiment interactively:

```bash
docker-compose run --build run-all-experiments bash
python scripts/dudect_comparison.py
```

---

## Manual Reproduction

### Prerequisites

- Python 3.10+
- pip
- For harness compilation: a C compiler and liboqs v0.15.0 installed

### 1. Install sca-triage

```bash
cd sca-triage
pip install -e .
cd ..
```

### 2. Reproduce Key Experiments (pre-collected data)

These scripts use pre-collected timing data in `data/`. Large CSV files are gitignored; contact the authors for full datasets.

### dudect vs TVLA vs sca-triage comparison (~10 seconds)
```bash
python scripts/dudect_comparison.py
```
**Expected:** dudect and TVLA both report |t|>4.5 (FAIL). sca-triage triages as FALSE POSITIVE.

### Raw trace analysis — aggregation masking test (~30 seconds)
```bash
python scripts/phase6_raw_trace_analysis.py
```
**Expected:** All secret-dependent targets at chance (XGBoost ~50.5%, Cohen's d < 0.001, MI = 0.000).

### Sensitivity curve (~3 minutes)
```bash
python scripts/phase7_sensitivity_curve.py
```
**Expected:** Pipeline detection floor at d ≈ 0.275. Plot saved to `figures/fig_sensitivity_curve.png`.

### ML detection floor (~1 minute)
```bash
python scripts/phase8_ml_detection_floor.py
```
**Expected:** XGBoost floor at d ≈ 0.85. T-test floor at d = 0.398.

### Positive control — KyberSlash validation (~2 minutes)
```bash
python scripts/analysis_positive_control.py
```
**Expected:** Vulnerable liboqs v0.9.0 → +3.8% XGBoost lift. Patched v0.15.0 → +0.5% (chance). Validates pipeline can detect real secret-dependent leakage.

### 3. Compile and Run Harnesses (requires hardware)

### Apple Silicon
```bash
cd harnesses
# Requires liboqs v0.15.0 installed (adjust prefix as needed)
LIBOQS_PREFIX=/opt/homebrew  # or /usr/local
gcc -O2 -march=native -I${LIBOQS_PREFIX}/include -L${LIBOQS_PREFIX}/lib \
    -o tvla_harness tvla_harness.c -loqs -lssl -lcrypto -lm
./tvla_harness fixed 10000 > ../data/fixed_traces.txt
./tvla_harness random 10000 > ../data/random_traces.txt
cd ..

# Symmetric control experiment (~30 min)
python3 scripts/phase9_symmetric_harness_control.py

# Compiler flag sweep (~30 min)
python3 scripts/phase10_compiler_flags.py
```
**Expected (symmetric control):** Symmetric |t|=62.49 (FAIL), asymmetric |t|=3.00 (PASS). Confirms architectural confound.
**Expected (compiler flags):** All 5 flags exhibit the confound. -O0, -O1, -O2, -O3 fail outright. -Os shows run-to-run variability (|t| ranges from 1.73 to 11.47); Levene's test confirms variance asymmetry is always present.

### Intel x86
```bash
cd x86-replication
./build.sh  # Clones liboqs 0.15.0, compiles both harnesses + timer profiler

# Asymmetric TVLA (500K traces, ~1-2 hours)
python3 tvla_analysis_x86.py --traces 500000

# Symmetric control experiment (50K traces per mode, ~30 min)
python3 ../scripts/intel_symmetric_control.py

cd ..
```
**Expected (asymmetric):** |t|=12.95, variance ratio 0.47x (FAIL).
**Expected (symmetric control):** Both harnesses fail — asymmetric |t|=5.35, symmetric |t|=6.70. Confirms architectural confound.

### 4. Data Access

Large trace files (>1MB) are gitignored. Available datasets:
- `data/raw_timing_traces_v3.csv` (2.4MB, 100K traces) — included in repo
- `data/tvla_traces.npz` (874KB, TVLA fixed/random traces) — included in repo
- `data/raw_timing_traces_v4_vertical.csv` (25MB) — contact authors
- Full 12.2M trace dataset — contact authors

### Expected Runtimes

| Script | Runtime | Hardware |
|--------|---------|----------|
| dudect_comparison.py | ~10s | Any |
| phase6_raw_trace_analysis.py | ~30s | Any |
| phase7_sensitivity_curve.py | ~3min | Any |
| phase8_ml_detection_floor.py | ~1min | Any |
| analysis_positive_control.py | ~2min | Any |
| phase9_symmetric_harness_control.py | ~30min | Apple Silicon |
| phase10_compiler_flags.py | ~30min | Apple Silicon |
| intel_symmetric_control.py | ~30min | Intel x86 |
| tvla_analysis_x86.py (500K traces) | ~1-2hr | Intel x86 |
| tvla_harness (10K traces) | ~5min | Apple Silicon |
| tvla_harness_x86 (10K traces) | ~5min | Intel x86 |
