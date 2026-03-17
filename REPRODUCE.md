# Reproduce Core Results

## Prerequisites

- Python 3.10+
- pip
- For harness compilation: a C compiler and liboqs v0.15.0 installed

## 1. Install sca-triage

```bash
cd sca-triage
pip install -e .
cd ..
```

## 2. Reproduce Key Experiments (pre-collected data)

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

## 3. Compile and Run Harnesses (requires hardware)

### Apple Silicon
```bash
cd harnesses
# Requires liboqs v0.15.0 installed at /usr/local
gcc -O2 -march=native -o tvla_harness tvla_harness.c -I/usr/local/include -L/usr/local/lib -loqs
./tvla_harness 1 10000 > ../data/fixed_traces.txt   # Fixed mode
./tvla_harness 0 10000 > ../data/random_traces.txt   # Random mode
cd ..
```

### Intel x86
```bash
cd x86-replication
./build.sh  # Clones liboqs 0.15.0, compiles harness
./tvla_harness_x86 1 10000 > fixed_traces.txt
./tvla_harness_x86 0 10000 > random_traces.txt
python tvla_analysis_x86.py
cd ..
```

## 4. Data Access

Large trace files (>1MB) are gitignored. Available datasets:
- `data/raw_timing_traces_v3.csv` (2.4MB, 100K traces) — included in repo
- `data/tvla_traces.npz` (874KB, TVLA fixed/random traces) — included in repo
- `data/raw_timing_traces_v4_vertical.csv` (25MB) — contact authors
- Full 12.2M trace dataset — contact authors

## Expected Runtimes

| Script | Runtime | Hardware |
|--------|---------|----------|
| dudect_comparison.py | ~10s | Any |
| phase6_raw_trace_analysis.py | ~30s | Any |
| phase7_sensitivity_curve.py | ~3min | Any |
| phase8_ml_detection_floor.py | ~1min | Any |
| tvla_harness (10K traces) | ~5min | Apple Silicon |
| tvla_harness_x86 (10K traces) | ~5min | Intel x86 |
