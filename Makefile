.PHONY: install demo validate

install:
	pip install -e sca-triage

validate:
	python3 scripts/validate_paper_claims.py

demo:
	sca-triage demo \
		--timing-data data/raw_timing_traces_v3.csv \
		--vuln-data data/raw_timing_traces_vuln.csv \
		--targets sk_lsb --precomputed --dark
