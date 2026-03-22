"""Generate realistic synthetic TVLA timing data for testing.

Produces CSV files mimicking real ML-KEM-768 decapsulation measurements
on Apple Silicon, including the temporal-drift-induced variance confound
that causes TVLA false positives.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Tuple

import numpy as np


def generate_sample_data(
    n_keys: int = 200,
    repeats_per_key: int = 50,
    output_dir: str = "examples/sample_data",
    seed: int = 42,
) -> Tuple[str, str]:
    """Generate synthetic timing traces and secret labels.

    Mimics real ML-KEM-768 measurements:
    - Median ~710 cycles (CNTVCT_EL0 ticks)
    - Right-skewed with heavy tail (occasional spikes to 10M+ cycles)
    - Fixed traces: 10x variance (sequential collection drift effect)
    - Random traces: moderate, consistent variance
    - NO secret-dependent timing difference (null result)

    Parameters
    ----------
    n_keys : int
        Number of distinct keys to simulate.
    repeats_per_key : int
        Number of measurement repeats per key.
    output_dir : str
        Directory to write output CSV files.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    tuple[str, str]
        Paths to the generated traces CSV and labels CSV.
    """
    rng = np.random.default_rng(seed)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # --- Generate base timings ---
    # Lognormal with median ~710 cycles: ln(710) ~ 6.565
    mu_log = 6.565
    sigma_log_fixed = 0.6    # high variance for fixed (temporal drift effect)
    sigma_log_random = 0.07  # low variance for random

    total_fixed = n_keys * repeats_per_key
    total_random = n_keys * repeats_per_key

    # Fixed traces: high variance, occasional extreme outliers
    fixed_base = rng.lognormal(mean=mu_log, sigma=sigma_log_fixed,
                               size=total_fixed)
    # Add extreme spikes (1 in 1000 chance -> ~1M-10M cycles)
    spike_mask = rng.random(total_fixed) < 0.001
    n_spikes = spike_mask.sum()
    if n_spikes > 0:
        fixed_base[spike_mask] = rng.uniform(1_000_000, 10_000_000,
                                             size=n_spikes)

    # Random traces: lower variance, fewer outliers
    random_base = rng.lognormal(mean=mu_log, sigma=sigma_log_random,
                                size=total_random)
    spike_mask_r = rng.random(total_random) < 0.0001
    n_spikes_r = spike_mask_r.sum()
    if n_spikes_r > 0:
        random_base[spike_mask_r] = rng.uniform(1_000_000, 5_000_000,
                                                size=n_spikes_r)

    # --- Build traces CSV ---
    # Columns: key_id, repeat_id, timing_ticks, group
    traces_path = out / "traces.csv"
    with open(traces_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["key_id", "repeat_id", "timing_ticks", "group"])

        idx = 0
        for key_id in range(n_keys):
            for rep in range(repeats_per_key):
                writer.writerow([
                    key_id, rep,
                    f"{fixed_base[idx]:.2f}",
                    "fixed",
                ])
                idx += 1

        idx = 0
        for key_id in range(n_keys, 2 * n_keys):
            for rep in range(repeats_per_key):
                writer.writerow([
                    key_id, rep,
                    f"{random_base[idx]:.2f}",
                    "random",
                ])
                idx += 1

    # --- Generate per-key secret labels ---
    # These are RANDOM and uncorrelated with timing (null result)
    labels_path = out / "labels.csv"
    all_key_ids = list(range(2 * n_keys))
    sk_lsb = rng.integers(0, 2, size=2 * n_keys)
    msg_hw_parity = rng.integers(0, 2, size=2 * n_keys)
    sk_byte0 = rng.integers(0, 256, size=2 * n_keys)

    with open(labels_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["key_id", "sk_lsb", "msg_hw_parity", "sk_byte0"])
        for i, kid in enumerate(all_key_ids):
            writer.writerow([kid, sk_lsb[i], msg_hw_parity[i], sk_byte0[i]])

    # --- Generate vulnerable dataset ---
    # sk_lsb=1 keys have ~3.8% slower median timing (real leakage)
    _generate_vulnerable_data(rng, n_keys, repeats_per_key, out)

    return str(traces_path), str(labels_path)


def _generate_vulnerable_data(
    rng: np.random.Generator,
    n_keys: int,
    repeats_per_key: int,
    out: Path,
) -> Tuple[str, str]:
    """Generate timing data with real secret-dependent leakage.

    Keys with sk_lsb=1 have a ~3.8% slower median timing, simulating
    a vulnerable implementation (e.g., liboqs v0.9.0 with non-constant-time
    comparison).

    Parameters
    ----------
    rng : np.random.Generator
        Random number generator.
    n_keys : int
        Number of keys per group.
    repeats_per_key : int
        Repeats per key.
    out : Path
        Output directory.

    Returns
    -------
    tuple[str, str]
        Paths to vulnerable traces and labels.
    """
    mu_log = 6.565
    sigma_log = 0.07  # same moderate variance for both

    # Assign sk_lsb labels
    sk_lsb = rng.integers(0, 2, size=n_keys)

    vuln_traces_path = out / "vuln_traces.csv"
    vuln_labels_path = out / "vuln_labels.csv"

    with open(vuln_traces_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["key_id", "repeat_id", "timing_ticks", "group"])

        for key_id in range(n_keys):
            # 3.8% timing penalty for sk_lsb=1
            bias = 1.038 if sk_lsb[key_id] == 1 else 1.0
            for rep in range(repeats_per_key):
                timing = rng.lognormal(mean=mu_log, sigma=sigma_log) * bias
                writer.writerow([
                    key_id, rep,
                    f"{timing:.2f}",
                    "fixed",
                ])

    with open(vuln_labels_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["key_id", "sk_lsb", "msg_hw_parity", "sk_byte0"])
        for key_id in range(n_keys):
            writer.writerow([
                key_id,
                sk_lsb[key_id],
                rng.integers(0, 2),
                rng.integers(0, 256),
            ])

    return str(vuln_traces_path), str(vuln_labels_path)


if __name__ == "__main__":
    traces, labels = generate_sample_data(
        n_keys=200,
        repeats_per_key=50,
        output_dir="examples/sample_data",
        seed=42,
    )
    print(f"Generated traces: {traces}")
    print(f"Generated labels: {labels}")
    print("Done.")
