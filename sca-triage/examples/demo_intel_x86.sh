#!/bin/bash
# Demo: Run sca-triage on Intel x86_64 ML-KEM-768 timing data
# Note: Intel platforms may exhibit different confound patterns
# (e.g., TSX-related variance, RDTSC jitter) compared to Apple Silicon.
set -e
echo "Generating sample data..."
python -m sca_triage.generate_sample_data
echo "Running full demo..."
sca-triage demo \
  --timing-data examples/sample_data/traces.csv \
  --secret-labels examples/sample_data/labels.csv \
  --vuln-data examples/sample_data/vuln_traces.csv \
  --targets sk_lsb
