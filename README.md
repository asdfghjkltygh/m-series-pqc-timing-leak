# When TVLA Lies: ISO 17825 False Positives on ML-KEM

ISO 17825 TVLA reports catastrophic timing leakage in liboqs ML-KEM-768 on both Apple Silicon (|t|=8.42) and Intel x86 (|t|=12.95). **The leakage is not real.** We prove this with 12.2 million traces, 20+ experiments, and six independent information-theoretic methods converging on zero extractable bits.

The root cause is an execution-context confound: TVLA's fixed-vs-random methodology confuses input-dependent microarchitectural optimization with secret-dependent leakage. This confound produces false positives on every modern processor architecture we tested.

We release **sca-triage**, an open-source tool that triages TVLA false positives, and propose a two-stage evaluation protocol for ISO 17825.

## Quick Start

```bash
# Install the triage tool
cd sca-triage && pip install -e . && cd ..

# Run the dudect vs TVLA vs sca-triage comparison
python scripts/dudect_comparison.py

# Run the full sensitivity curve
python scripts/phase7_sensitivity_curve.py
```

## Key Results

| Method | Result | Verdict |
|--------|--------|---------|
| dudect / TVLA (ISO 17825) | \|t\|=8.42 (Apple), \|t\|=12.95 (Intel) | FAIL — "leakage detected" |
| sca-triage Stage 2 (pairwise) | All secret targets p>0.2 | No secret dependence |
| sca-triage Stage 3 (MI) | 0.000 bits, p=1.0 | Zero extractable information |
| Positive control (KyberSlash v0.9.0) | +3.8% accuracy lift | Real leakage detected |
| Raw trace analysis (100K traces) | Cohen's d=0.0003 | No trace-level signal |

## Repository Map

```
├── sca-triage/          # Open-source TVLA triage tool (pip install -e .)
├── submission/          # Black Hat submission materials
│   ├── whitepaper.md    # Full whitepaper
│   ├── cfp_abstracts.md # Three CFP abstract versions
│   └── slide_deck_outline.md
├── scripts/             # Experiment scripts (Python)
│   ├── dudect_comparison.py        # dudect vs TVLA vs sca-triage
│   ├── phase6_raw_trace_analysis.py # Aggregation masking test
│   ├── phase7_sensitivity_curve.py  # Tool sensitivity characterization
│   └── phase8_ml_detection_floor.py # ML detection floor
├── harnesses/           # C timing measurement harnesses
│   ├── tvla_harness.c   # Apple Silicon TVLA harness
│   └── timing_harness_v2.c
├── x86-replication/     # Intel x86 cross-platform replication
│   ├── tvla_harness_x86.c
│   └── tvla_analysis_x86.py
├── data/                # Experiment results (large CSVs gitignored)
├── figures/             # Generated plots
└── REPRODUCE.md         # Step-by-step reproduction guide
```

## Citation

If you use this work, please cite:

```bibtex
@misc{shenoy2026tvla,
  title={When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment},
  author={Shenoy, Saahil},
  year={2026},
  howpublished={Black Hat Briefings}
}
```

## License

sca-triage is released under the MIT License. See [sca-triage/LICENSE](sca-triage/LICENSE).
