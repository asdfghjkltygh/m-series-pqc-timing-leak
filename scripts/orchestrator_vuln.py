#!/usr/bin/env python3
"""
orchestrator_vuln.py — Positive Control Data Collection

Collects timing traces against VULNERABLE liboqs v0.9.0 (pre-KyberSlash fix).
Uses keygen_helper_vuln and timing_harness_vuln binaries.
Otherwise identical to orchestrator_v3.py.

Output: data/raw_timing_traces_vuln.csv
"""

import argparse
import csv
import os
import subprocess
import sys
import threading
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYGEN_BIN = os.path.join(PROJECT_DIR, "src", "keygen_helper_vuln")
TIMING_BIN = os.path.join(PROJECT_DIR, "src", "timing_harness_vuln")
OUTPUT_CSV = os.path.join(PROJECT_DIR, "data", "raw_timing_traces_vuln.csv")


def background_load_worker(stop_event):
    x = 1.0001
    while not stop_event.is_set():
        for _ in range(100_000):
            x = (x * 1.0001) % 1e10
        time.sleep(0)


def generate_samples(num_samples, mutation_rate=0.5):
    """Run keygen_helper_vuln and parse output."""
    proc = subprocess.run(
        [KEYGEN_BIN, str(num_samples), str(mutation_rate)],
        capture_output=True, text=True, timeout=3600
    )
    if proc.returncode != 0:
        print(f"keygen_helper_vuln failed: {proc.stderr}", file=sys.stderr)
        sys.exit(1)

    samples = []
    for line in proc.stdout.strip().split("\n"):
        parts = line.strip().split()
        if len(parts) < 6:
            continue
        samples.append({
            "ct": parts[0],
            "sk": parts[1],
            "valid_ct": int(parts[2]),
            "message_hw": int(parts[3]),
            "coeff0_hw": int(parts[4]),
            "sk_byte0": int(parts[5]),
        })
    return samples


def measure_timings(samples, num_repeats):
    """Measure decapsulation timings."""
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

    for key_id, sample in enumerate(samples):
        for rep in range(num_repeats):
            proc.stdin.write(f"{sample['ct']} {sample['sk']}\n")
            proc.stdin.flush()
            timing_line = proc.stdout.readline().strip()
            if not timing_line:
                continue
            results.append({
                "key_id": key_id,
                "repeat": rep,
                "timing_cycles": int(timing_line),
                "valid_ct": sample["valid_ct"],
                "message_hw": sample["message_hw"],
                "coeff0_hw": sample["coeff0_hw"],
                "sk_byte0": sample["sk_byte0"],
            })
            done += 1
            if done % 5000 == 0:
                print(f"  Progress: {done}/{total} ({done/total*100:.1f}%)",
                      file=sys.stderr)

    proc.stdin.close()
    proc.wait()
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Positive control: vulnerable liboqs v0.9.0 orchestrator")
    parser.add_argument("--num-keys", type=int, default=500)
    parser.add_argument("--num-repeats", type=int, default=50)
    parser.add_argument("--mutation-rate", type=float, default=0.5)
    parser.add_argument("--load-threads", type=int, default=4)
    parser.add_argument("--output", type=str, default=OUTPUT_CSV)
    args = parser.parse_args()

    total = args.num_keys * args.num_repeats
    print(f"[Orchestrator VULN] Positive Control — vulnerable liboqs v0.9.0")
    print(f"  {args.num_keys} keys x {args.num_repeats} repeats = {total:,} traces")
    print(f"  Mutation rate: {args.mutation_rate}")

    print(f"\n[Step 1] Generating {args.num_keys} samples with vulnerable Kyber-768...")
    samples = generate_samples(args.num_keys, args.mutation_rate)
    n_valid = sum(1 for s in samples if s["valid_ct"] == 1)
    n_invalid = sum(1 for s in samples if s["valid_ct"] == 0)
    print(f"  Generated {len(samples)} samples ({n_valid} valid, {n_invalid} invalid CTs)")

    # Background load
    stop_event = threading.Event()
    threads = []
    if args.load_threads > 0:
        print(f"[Step 2] Spawning {args.load_threads} background load threads...")
        for _ in range(args.load_threads):
            t = threading.Thread(target=background_load_worker,
                                 args=(stop_event,), daemon=True)
            t.start()
            threads.append(t)

    print(f"[Step 3] Measuring {total:,} timings...")
    t0 = time.time()
    results = measure_timings(samples, args.num_repeats)
    elapsed = time.time() - t0
    print(f"  Collected {len(results):,} traces in {elapsed:.1f}s "
          f"({len(results)/elapsed:.0f} traces/sec)")

    if threads:
        stop_event.set()
        for t in threads:
            t.join(timeout=5)

    fieldnames = ["key_id", "repeat", "timing_cycles", "valid_ct",
                  "message_hw", "coeff0_hw", "sk_byte0"]
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n[Done] Saved {len(results):,} traces to {args.output}")

    import statistics
    timings = [r["timing_cycles"] for r in results]
    print(f"  Range: {min(timings)} - {max(timings)} cycles")
    print(f"  Mean: {statistics.mean(timings):.1f}, Median: {statistics.median(timings):.1f}")


if __name__ == "__main__":
    main()
