#!/bin/bash
# Validate tool against known-vulnerable liboqs v0.9.0
set -e
sca-triage analyze \
  --timing-data examples/sample_data/vuln_traces.csv \
  --secret-labels examples/sample_data/vuln_labels.csv \
  --targets sk_lsb \
  --output positive_control_report.html
