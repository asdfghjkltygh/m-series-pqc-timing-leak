#!/usr/bin/env python3
"""
orchestrator_v2.py

Upgraded data collection with:
- CNTVCT_EL0 cycle-counter timing (sub-nanosecond precision)
- 2000 keys x 50 repeats = 100,000 traces
- Rich labeling: 16 secret key coefficients + Hamming weight
- Background load for realistic noise
- Outputs per-key aggregate statistics as features

Output: data/raw_timing_traces_v2.csv
"""

import argparse
import csv
import os
import subprocess
import sys
import threading
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYGEN_BIN = os.path.join(PROJECT_DIR, "src", "keygen_helper_v2")
TIMING_BIN = os.path.join(PROJECT_DIR, "src", "timing_harness_v2")
OUTPUT_CSV = os.path.join(PROJECT_DIR, "data", "raw_timing_traces_v2.csv")

NUM_TARGET_COEFFS = 16


def background_load_worker(stop_event: threading.Event):
    """Burn CPU with arithmetic to simulate noisy system load."""
    x = 1.0001
    while not stop_event.is_set():
        for _ in range(100_000):
            x = (x * 1.0001) % 1e10
        time.sleep(0)


def generate_samples(num_samples: int):
    """Run keygen_helper_v2 and parse output."""
    proc = subprocess.run(
        [KEYGEN_BIN, str(num_samples)],
        capture_output=True, text=True, timeout=1200
    )
    if proc.returncode != 0:
        print(f"keygen_helper_v2 failed: {proc.stderr}", file=sys.stderr)
        sys.exit(1)

    samples = []
    for line in proc.stdout.strip().split("\n"):
        parts = line.strip().split()
        if len(parts) < 2 + NUM_TARGET_COEFFS + 1:
            continue
        ct_hex = parts[0]
        sk_hex = parts[1]
        coeffs = [int(parts[2 + j]) for j in range(NUM_TARGET_COEFFS)]
        hw_sum = int(parts[2 + NUM_TARGET_COEFFS])
        samples.append({
            "ct": ct_hex,
            "sk": sk_hex,
            "coeffs": coeffs,
            "hw_sum": hw_sum,
        })
    return samples


def measure_timings(samples: list, num_repeats: int):
    """Measure decapsulation timings for all samples."""
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
        ct_hex = sample["ct"]
        sk_hex = sample["sk"]

        for rep in range(num_repeats):
            proc.stdin.write(f"{ct_hex} {sk_hex}\n")
            proc.stdin.flush()
            timing_line = proc.stdout.readline().strip()
            if not timing_line:
                continue
            cycles = int(timing_line)
            row = {
                "key_id": key_id,
                "repeat": rep,
                "timing_cycles": cycles,
                "hw_sum": sample["hw_sum"],
            }
            for j in range(NUM_TARGET_COEFFS):
                row[f"coeff_{j}"] = sample["coeffs"][j]
            results.append(row)
            done += 1
            if done % 5000 == 0:
                print(f"  Progress: {done}/{total} measurements ({done/total*100:.1f}%)",
                      file=sys.stderr)

    proc.stdin.close()
    proc.wait()
    return results


def main():
    parser = argparse.ArgumentParser(description="PQC timing trace orchestrator v2")
    parser.add_argument("--num-keys", type=int, default=2000,
                        help="Number of distinct keys (default: 2000)")
    parser.add_argument("--num-repeats", type=int, default=50,
                        help="Decap repeats per key (default: 50)")
    parser.add_argument("--load-threads", type=int, default=4,
                        help="Background load threads (default: 4)")
    parser.add_argument("--output", type=str, default=OUTPUT_CSV)
    args = parser.parse_args()

    total_traces = args.num_keys * args.num_repeats
    print(f"[Orchestrator v2] Collecting {total_traces} traces "
          f"({args.num_keys} keys x {args.num_repeats} repeats)")

    print(f"[Step 1] Generating {args.num_keys} ML-KEM-768 key/CT pairs...")
    samples = generate_samples(args.num_keys)
    print(f"  Generated {len(samples)} valid samples.")

    # Background load
    stop_event = threading.Event()
    load_threads = []
    if args.load_threads > 0:
        print(f"[Step 2] Spawning {args.load_threads} background load threads...")
        for _ in range(args.load_threads):
            t = threading.Thread(target=background_load_worker, args=(stop_event,),
                                 daemon=True)
            t.start()
            load_threads.append(t)

    print(f"[Step 3] Measuring {total_traces} decapsulation timings (CNTVCT_EL0)...")
    t0 = time.time()
    results = measure_timings(samples, args.num_repeats)
    elapsed = time.time() - t0
    print(f"  Collected {len(results)} traces in {elapsed:.1f}s "
          f"({len(results)/elapsed:.0f} traces/sec)")

    if load_threads:
        stop_event.set()
        for t in load_threads:
            t.join(timeout=5)

    # Build fieldnames
    fieldnames = ["key_id", "repeat", "timing_cycles", "hw_sum"]
    fieldnames += [f"coeff_{j}" for j in range(NUM_TARGET_COEFFS)]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"[Done] Saved {len(results)} traces to {args.output}")

    # Quick stats
    timings = [r["timing_cycles"] for r in results]
    import statistics
    print(f"  Timing range: {min(timings)} - {max(timings)} cycles")
    print(f"  Mean: {statistics.mean(timings):.1f}, Median: {statistics.median(timings):.1f}, "
          f"Stdev: {statistics.stdev(timings):.1f}")


if __name__ == "__main__":
    main()
