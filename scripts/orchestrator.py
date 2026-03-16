#!/usr/bin/env python3
"""
orchestrator.py

Generates ML-KEM-768 timing traces under realistic system load.
Uses keygen_helper to produce valid (pk, sk, ct, ss) tuples,
then feeds each (ct, sk) pair to timing_harness and records
the decapsulation time alongside the target secret key byte.

Output: data/raw_timing_traces.csv

Realism: optionally spawns background worker threads performing
arithmetic to simulate a "dirty" host environment.
"""

import argparse
import csv
import multiprocessing
import os
import subprocess
import sys
import threading
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYGEN_BIN = os.path.join(PROJECT_DIR, "src", "keygen_helper")
TIMING_BIN = os.path.join(PROJECT_DIR, "src", "timing_harness")
OUTPUT_CSV = os.path.join(PROJECT_DIR, "data", "raw_timing_traces.csv")


def background_load_worker(stop_event: threading.Event):
    """Burn CPU with arithmetic to simulate noisy system load."""
    x = 1.0001
    while not stop_event.is_set():
        for _ in range(100_000):
            x = (x * 1.0001) % 1e10
        # Yield briefly to avoid total starvation
        time.sleep(0)


def generate_samples(num_samples: int):
    """Run keygen_helper and parse output into list of dicts."""
    proc = subprocess.run(
        [KEYGEN_BIN, str(num_samples)],
        capture_output=True, text=True, timeout=600
    )
    if proc.returncode != 0:
        print(f"keygen_helper failed: {proc.stderr}", file=sys.stderr)
        sys.exit(1)

    samples = []
    current = {}
    for line in proc.stdout.strip().split("\n"):
        line = line.strip()
        if line == "---":
            if current:
                samples.append(current)
                current = {}
        elif line.startswith("PK:"):
            current["pk"] = line[3:]
        elif line.startswith("SK:"):
            current["sk"] = line[3:]
        elif line.startswith("CT:"):
            current["ct"] = line[3:]
        elif line.startswith("SS:"):
            current["ss"] = line[3:]
        elif line.startswith("TARGET_BYTE:"):
            current["target_byte"] = int(line[12:])

    return samples


def measure_timings(samples: list, num_repeats: int = 10):
    """
    For each sample, run decapsulation num_repeats times and record
    all individual timings. This gives us multiple traces per key.
    """
    proc = subprocess.Popen(
        [TIMING_BIN],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    results = []
    total = len(samples) * num_repeats
    done = 0

    for sample in samples:
        ct_hex = sample["ct"]
        sk_hex = sample["sk"]
        target = sample["target_byte"]

        for rep in range(num_repeats):
            proc.stdin.write(f"{ct_hex} {sk_hex}\n")
            proc.stdin.flush()
            timing_line = proc.stdout.readline().strip()
            if not timing_line:
                print("WARNING: empty timing output", file=sys.stderr)
                continue
            ns = int(timing_line)
            results.append({
                "sample_id": len(results),
                "target_byte": target,
                "repeat": rep,
                "timing_ns": ns,
            })
            done += 1
            if done % 500 == 0:
                print(f"  Progress: {done}/{total} measurements", file=sys.stderr)

    proc.stdin.close()
    proc.wait()
    return results


def main():
    parser = argparse.ArgumentParser(description="PQC timing trace orchestrator")
    parser.add_argument("--num-keys", type=int, default=500,
                        help="Number of distinct keys to generate (default: 500)")
    parser.add_argument("--num-repeats", type=int, default=20,
                        help="Decap repeats per key (default: 20)")
    parser.add_argument("--load-threads", type=int, default=0,
                        help="Background load threads (0=clean, e.g. 4=dirty)")
    parser.add_argument("--output", type=str, default=OUTPUT_CSV,
                        help="Output CSV path")
    args = parser.parse_args()

    print(f"[Phase 1] Generating {args.num_keys} ML-KEM-768 key/CT pairs...")
    samples = generate_samples(args.num_keys)
    print(f"  Generated {len(samples)} valid samples.")

    # Start background load if requested
    stop_event = threading.Event()
    load_threads = []
    if args.load_threads > 0:
        print(f"[Phase 1] Spawning {args.load_threads} background load threads...")
        for _ in range(args.load_threads):
            t = threading.Thread(target=background_load_worker, args=(stop_event,), daemon=True)
            t.start()
            load_threads.append(t)

    print(f"[Phase 1] Measuring {args.num_keys * args.num_repeats} decapsulation timings...")
    results = measure_timings(samples, args.num_repeats)

    # Stop background load
    if load_threads:
        stop_event.set()
        for t in load_threads:
            t.join(timeout=5)

    # Write CSV
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["sample_id", "target_byte", "repeat", "timing_ns"])
        writer.writeheader()
        writer.writerows(results)

    print(f"[Phase 1] Saved {len(results)} timing traces to {args.output}")
    print(f"  Timing range: {min(r['timing_ns'] for r in results)} - {max(r['timing_ns'] for r in results)} ns")

    # Quick stats
    import statistics
    timings = [r["timing_ns"] for r in results]
    print(f"  Mean: {statistics.mean(timings):.1f} ns, Median: {statistics.median(timings):.1f} ns, Stdev: {statistics.stdev(timings):.1f} ns")


if __name__ == "__main__":
    main()
