# x86-64 TVLA Control Experiment

**Purpose:** Determine whether the Apple Silicon TVLA false positive (|t|=8.42)
is a microarchitectural artifact specific to Apple's DMP/speculative execution,
or a software-level property of liboqs.

## Quick Start

On an x86-64 Linux machine:

```bash
# 1. Install prerequisites
sudo apt-get install -y build-essential cmake git libssl-dev python3-numpy python3-scipy
# OR: sudo yum install -y gcc cmake git openssl-devel python3-numpy python3-scipy

# 2. Build everything (clones + compiles liboqs 0.15.0 from source)
chmod +x build.sh
./build.sh

# 3. Run the experiment (~1-2 hours for 500K traces per class)
python3 tvla_analysis_x86.py --traces 500000

# For a quick test (5 minutes):
python3 tvla_analysis_x86.py --traces 50000
```

## What This Does

1. **Builds liboqs 0.15.0** from source with `-O2` (same flags as Apple Silicon)
2. **Profiles RDTSC** timer resolution (equivalent to CNTVCT_EL0 profiling)
3. **Collects 500K fixed + 500K random** ML-KEM-768 decapsulation traces
4. **Computes Welch's t-test** with progressive analysis
5. **Compares results** with Apple Silicon |t|=8.42

## Expected Outcomes

- **If |t| < 4.5 on x86:** The Apple false positive is a DMP/microarch artifact → paper thesis confirmed
- **If |t| > 4.5 on x86:** The effect is algorithmic → need to revise hypothesis

## Files

- `tvla_harness_x86.c` — C harness using RDTSC (replaces CNTVCT_EL0)
- `timer_profile_x86.c` — RDTSC resolution profiler
- `tvla_analysis_x86.py` — Full analysis with Apple comparison
- `build.sh` — One-command build script
- `tvla_x86_results.json` — Output (created after running)
- `tvla_x86_traces.npz` — Raw trace data (created after running)
