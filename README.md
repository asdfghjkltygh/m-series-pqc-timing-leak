# When TVLA Lies: How a Broken Standard Is Blocking Post-Quantum Crypto Deployment

ISO 17825 TVLA — the mandatory side-channel test for FIPS 140-3 certification — produces catastrophic false positives on ML-KEM when run on modern hardware. The root cause is **temporal drift from sequential data collection**, not any weakness in the algorithm or its implementation.

**Headline result:** Switching from sequential to interleaved measurement collection reduces Apple Silicon's |t| from **62.49 to 0.58** — a 100x reduction — with no change to the hardware, software, or cryptographic inputs. Intel x86 shows the same pattern: |t| drops from **6.70 to 1.65**. 12.2 million traces and 150+ experiments confirm zero exploitable bits of secret information.

We release **sca-triage**, an open-source triage tool that distinguishes real side-channel leakage from false positives, and propose a two-stage evaluation protocol for ISO 17825.

## Verify All Claims (30 seconds)

```bash
pip install -e sca-triage
python scripts/validate_paper_claims.py
```

This checks all 28 numerical claims in the paper against the data files in the repo. Expected: 28/28 PASS.

## Run the Tool on Our Data

```bash
# Quick TVLA check
sca-triage analyze --timing-data data/tvla_traces.npz --targets sk_lsb --quick

# Full three-stage pipeline (TVLA + pairwise + MI → FALSE_POSITIVE)
python scripts/dudect_comparison.py
```

The quick check runs Stage 1 (TVLA: |t|=8.42, FAIL). The full pipeline via `dudect_comparison.py` runs all three stages and produces the FALSE_POSITIVE verdict.

## Full Reproduction (Docker)

```bash
docker-compose up --build run-all-experiments
```

Runs all experiments (~5 minutes), validates all claims, outputs results to `data/` and `figures/`.

## Key Results

| Collection | Platform | |t| | Verdict |
|-----------|----------|-----|---------|
| Sequential | Apple Silicon | 62.49 | **FAIL** |
| Interleaved | Apple Silicon | 0.58 | **PASS** |
| Sequential | Intel x86 | 6.70 | **FAIL** |
| Interleaved | Intel x86 | 1.65 | **PASS** |

Same hardware. Same code. Same inputs. The only difference is *when* the measurements were collected.

## Links

- **Whitepaper:** [submission/whitepaper.md](submission/whitepaper.md)
- **Reproduction guide:** [REPRODUCE.md](REPRODUCE.md)
- **sca-triage tool:** [sca-triage/](sca-triage/)

## License

sca-triage is released under the MIT License. See [sca-triage/LICENSE](sca-triage/LICENSE).
