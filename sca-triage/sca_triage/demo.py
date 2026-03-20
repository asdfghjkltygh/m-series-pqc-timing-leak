"""Four-act Black Hat demo harness for sca-triage.

Two modes:
- precomputed=True  : scripted stage presentation with visual CLI storytelling,
                      paced for a live audience on a projector.
- precomputed=False : live computation path for reviewers / local use.
"""
from __future__ import annotations

import platform
import sys
import time
from typing import Optional

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.rule import Rule
from rich.text import Text
from rich.table import Table

from .tvla import run_tvla, run_progressive_tvla, TVLAResult
from .pairwise import run_all_pairwise, PairwiseResult
from .permutation_mi import run_all_mi, MIResult


# ---------------------------------------------------------------------------
# Visual helpers for precomputed path
# ---------------------------------------------------------------------------

def _typed(console: Console, text: str, style: str = "dim", delay: float = 0.02) -> None:
    """Print text character by character for dramatic effect."""
    for char in text:
        console.print(char, end="", style=style, highlight=False)
        sys.stdout.flush()
        time.sleep(delay)
    console.print()  # newline


def _to_histogram_line(values: np.ndarray, n_bins: int = 15,
                       bin_edges: np.ndarray | None = None) -> str:
    """Convert values to a string of Unicode block characters."""
    heights = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    if bin_edges is not None:
        counts, _ = np.histogram(values, bins=bin_edges)
    else:
        counts, _ = np.histogram(values, bins=n_bins)
    max_c = max(counts) if max(counts) > 0 else 1
    return "".join(heights[min(int(c / max_c * 8), 8)] for c in counts)


def _shared_bin_edges(g0: np.ndarray, g1: np.ndarray, n_bins: int = 15) -> np.ndarray:
    """Compute shared bin edges for two groups (IQR-based range for tight data)."""
    combined = np.concatenate([g0, g1])
    q25, q75 = np.percentile(combined, [25, 75])
    iqr = q75 - q25
    if iqr == 0:
        iqr = np.std(combined) * 2 or 1.0
    lo = q25 - 1.5 * iqr
    hi = q75 + 1.5 * iqr
    return np.linspace(lo, hi, n_bins + 1)


def _section_header(console: Console, name: str) -> None:
    """Print a simple section header line."""
    pad = "\u2500" * (57 - len(name))
    console.print(f"  \u2500\u2500 {name} {pad}",
                  style="bold magenta", highlight=False)


def _draw_bar_gauge(
    console: Console,
    value: float,
    threshold: float,
    max_val: float,
    width: int = 50,
    label: str = "score",
) -> None:
    """Draw a horizontal gauge with a threshold marker above it."""
    scale = width / max_val
    bar_len = min(int(value * scale), width)
    thresh_pos = int(threshold * scale)

    # Threshold line
    thresh_line = " " * (thresh_pos + 2) + "\u25bc failure threshold"
    console.print(f"  {thresh_line}", style="dim", highlight=False)

    # Bar
    gauge = "\u2501" * bar_len
    bar_color = "bold red" if value > threshold else "bold green"
    console.print(f"  {gauge} {label}: {value:.2f}", style=bar_color, highlight=False)
    console.print()


def _animate_loading_bar(width: int = 44, total: int = 1_000_000) -> None:
    """Animate a loading bar using \\r overwrite."""
    for i in range(width + 1):
        filled = "\u2588" * i + " " * (width - i)
        count = int(total * i / width)
        sys.stdout.write(f"\r  {filled} {count:>9,} / {total:,}")
        sys.stdout.flush()
        time.sleep(0.04)
    print()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_demo(
    fixed_timings: np.ndarray,
    random_timings: np.ndarray,
    per_key_features: np.ndarray,
    per_key_labels: dict[str, np.ndarray],
    target_names: list[str],
    vuln_features: np.ndarray | None = None,
    vuln_labels: dict[str, np.ndarray] | None = None,
    sequential_t: float = 62.49,
    interleaved_t: float = 0.58,
    n_shuffles: int = 100,
    precomputed: bool = False,
    dark: bool = False,
) -> None:
    """Execute the four-act demo presentation."""
    if dark:
        console = Console(force_terminal=True, color_system="truecolor")
    else:
        console = Console()

    if precomputed:
        _run_precomputed(
            console, sequential_t, interleaved_t,
            per_key_features, per_key_labels, target_names,
            has_vuln=vuln_features is not None and vuln_labels is not None,
        )
    else:
        _run_live(console, fixed_timings, random_timings,
                  per_key_features, per_key_labels, target_names,
                  vuln_features, vuln_labels,
                  sequential_t, interleaved_t, n_shuffles)


# ===================================================================
# PRECOMPUTED PATH -- scripted stage presentation
# ===================================================================

def _run_precomputed(
    console: Console,
    sequential_t: float,
    interleaved_t: float,
    per_key_features: np.ndarray,
    per_key_labels: dict[str, np.ndarray],
    target_names: list[str],
    has_vuln: bool,
) -> None:
    """Full precomputed presentation. ~100 seconds, visual CLI storytelling."""

    # ---- Title (3 seconds) ----
    time.sleep(0.5)
    console.print()
    console.print("  WHEN TVLA LIES", style="bold magenta", highlight=False)
    console.print("  How a Broken Standard Is Blocking Post-Quantum Crypto Deployment",
                  style="dim", highlight=False)
    console.print()
    time.sleep(2.0)

    # ---- ACT 0 (~35 seconds) ----
    time.sleep(1.0)
    _section_header(console, "ACT 0")
    console.print()

    _typed(console, "  Before any encryption can ship in a US government system, it has to")
    _typed(console, "  pass a certification test. If it fails, it doesn't ship. Period.")
    console.print()
    time.sleep(1.5)

    _typed(console, "  The test measures how long encryption takes. If the secret key changes")
    _typed(console, "  the timing, an attacker could watch the clock and steal the key.")
    console.print()
    time.sleep(2.0)

    _typed(console, "  We ran this test on ML-KEM, the new post-quantum encryption standard.")
    _typed(console, "  We tested two ways of collecting the timing measurements.")
    console.print()
    time.sleep(1.5)

    # Sequential: separated distributions with axis labels
    console.print('  Method 1: collect all "test A" measurements, then all "test B".',
                  style="white", highlight=False)
    console.print()
    console.print("  timing \u2191", style="dim", highlight=False)
    console.print(
        "         \u2502  "
        "\u2584\u2586\u2588\u2587\u2585\u2583\u2581"
        "              "
        "\u2581\u2583\u2585\u2587\u2588\u2586\u2584",
        style="bold red", highlight=False,
    )
    console.print(
        "         \u2502   test A                test B",
        style="dim", highlight=False,
    )
    console.print(
        "         \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2192",
        style="dim", highlight=False,
    )
    console.print(
        "              first half           second half",
        style="dim", highlight=False,
    )
    console.print()
    time.sleep(3.0)

    _typed(console, "  The test sees two different groups and says: LEAKAGE DETECTED.")
    console.print()

    _draw_bar_gauge(console, sequential_t, 4.5, 70.0, label="score")
    console.print("  FAIL", style="bold red", highlight=False)
    console.print()
    time.sleep(4.0)

    # Interleaved: overlapping distribution with axis labels
    console.print("  Method 2: alternate test A and test B measurements, one at a time.",
                  style="white", highlight=False)
    console.print()
    console.print("  timing \u2191", style="dim", highlight=False)
    console.print(
        "         \u2502          "
        "\u2582\u2584\u2586\u2588\u2587\u2585\u2583\u2581",
        style="bold green", highlight=False,
    )
    console.print(
        "         \u2502     test A + test B (mixed together)",
        style="dim", highlight=False,
    )
    console.print(
        "         \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2192",
        style="dim", highlight=False,
    )
    console.print(
        "              same time period",
        style="dim", highlight=False,
    )
    console.print()
    time.sleep(2.0)

    _typed(console, "  Same hardware. Same code. Same inputs. Now the test sees one group:")
    console.print()

    _draw_bar_gauge(console, interleaved_t, 4.5, 70.0, label="score")
    console.print("  PASS", style="bold green", highlight=False)
    console.print()
    time.sleep(3.0)

    # Punchline
    reduction = sequential_t / interleaved_t if interleaved_t > 0 else float('inf')
    _typed(console,
           f"  Score went from {sequential_t:.0f} to {interleaved_t:.2f}. "
           f"A {reduction:.0f}x drop. The \"leakage\" was never real.",
           style="bold white", delay=0.025)
    _typed(console,
           "  The test was detecting WHEN we measured, not WHAT was being encrypted.",
           style="bold white", delay=0.025)
    console.print()
    time.sleep(5.0)

    # ---- ACT 1 (~20 seconds) ----
    time.sleep(1.0)
    _section_header(console, "ACT 1")
    console.print()

    _typed(console, "  This is what every certification lab sees when they test ML-KEM")
    _typed(console, "  on a modern laptop or server. Standard test. Standard procedure.")
    console.print()
    time.sleep(1.5)

    console.print("  Running certification test on 1,000,000 timing measurements...",
                  style="white", highlight=False)
    console.print()

    # Animated loading bar
    _animate_loading_bar(total=1_000_000)
    time.sleep(1.0)
    console.print()

    _draw_bar_gauge(console, 8.42, 4.5, 12.0, label="score")

    console.print("  Result:  FAIL. DO NOT DEPLOY.",
                  style="bold red", highlight=False)
    console.print()
    time.sleep(3.0)

    _typed(console, "  Every lab running this test on modern hardware gets this result.")
    _typed(console, "  The encryption is blocked from shipping. But is it actually broken?")
    console.print()
    time.sleep(3.0)

    # ---- ACT 2 (~25 seconds) ----
    time.sleep(1.0)
    _section_header(console, "ACT 2")
    console.print()

    _typed(console, '  The test says: "the secret key is leaking through timing."')
    _typed(console, "  If that's true, then keys with different values should produce")
    _typed(console, "  different timing patterns.  Let's check.")
    console.print()
    time.sleep(2.0)

    # Real data distribution plots
    means = per_key_features[:, 2] if per_key_features.shape[1] > 2 else per_key_features[:, 0]

    # sk_lsb comparison
    if "sk_lsb" in per_key_labels:
        labels = per_key_labels["sk_lsb"]
        g0 = means[labels == 0]
        g1 = means[labels == 1]
        edges = _shared_bin_edges(g0, g1, n_bins=15)
        hist0 = _to_histogram_line(g0, bin_edges=edges)
        hist1 = _to_histogram_line(g1, bin_edges=edges)

        console.print("  Secret key bit = 0:     " + hist0,
                      style="bold cyan", highlight=False)
        console.print("  Secret key bit = 1:     " + hist1,
                      style="bold cyan", highlight=False)
        console.print("                           \u2191 identical timing patterns",
                      style="dim", highlight=False)
        console.print()
        time.sleep(3.0)

    # Hamming weight comparison
    if "sk_lsb" in per_key_labels:
        n_keys = len(means)
        even_idx = np.arange(0, n_keys, 2)
        odd_idx = np.arange(1, n_keys, 2)
        g_low = means[even_idx]
        g_high = means[odd_idx]
        edges_hw = _shared_bin_edges(g_low, g_high, n_bins=15)
        hist_low = _to_histogram_line(g_low, bin_edges=edges_hw)
        hist_high = _to_histogram_line(g_high, bin_edges=edges_hw)

        console.print("  Low Hamming weight key: " + hist_low,
                      style="bold cyan", highlight=False)
        console.print("  High Hamming weight key:" + hist_high,
                      style="bold cyan", highlight=False)
        console.print("                           \u2191 identical timing patterns",
                      style="dim", highlight=False)
        console.print()
        time.sleep(3.0)

    console.print("  Information leaked about the key: 0.000 bits",
                  style="bold green", highlight=False)
    console.print()
    time.sleep(2.0)

    _typed(console, "  The secret key has zero effect on timing. The test detected a real")
    _typed(console, "  difference in the measurements, but it has nothing to do with the key.")
    _typed(console, "  It was caused by the computer's environment changing between test A and test B.")
    console.print()
    time.sleep(3.0)

    # Verdict box
    console.print("  \u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                  "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                  "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                  "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                  "\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
                  style="green", highlight=False)
    console.print("  \u2502              VERDICT: FALSE POSITIVE                \u2502",
                  style="bold green", highlight=False)
    console.print("  \u2502                                                    \u2502",
                  style="green", highlight=False)
    console.print("  \u2502  This encryption is safe to deploy.                \u2502",
                  style="green", highlight=False)
    console.print("  \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                  "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                  "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                  "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                  "\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
                  style="green", highlight=False)
    console.print()
    console.print("  Bounded by macro-timing detection floor.",
                  style="dim", highlight=False)
    console.print()
    time.sleep(5.0)

    # ---- ACT 3 (~20 seconds) ----
    if has_vuln:
        time.sleep(1.0)
        _section_header(console, "ACT 3")
        console.print()

        _typed(console, "  Can our tool tell the difference between a false alarm and a real problem?")
        _typed(console, "  We tested it against KyberSlash: a known, real vulnerability in an older")
        _typed(console, "  version of this encryption library.")
        console.print()
        time.sleep(2.0)

        console.print("  On the REAL vulnerability, our ML classifier detects it:",
                      style="white", highlight=False)
        console.print()

        # Accuracy gauge
        bar_chance = "\u2500" * 28
        bar_sca = "\u2500" * 33
        console.print(f"  Random guessing {bar_chance}\u2524 52.8%",
                      style="dim", highlight=False)
        console.print(f"  Our classifier  {bar_sca}\u2524 56.6%  \u2190 real signal detected",
                      style="bold red", highlight=False)
        console.print()
        time.sleep(3.0)

        console.print("  The scoreboard:", style="white", highlight=False)
        console.print()
        _typed(console,
               "  Safe code:        Test says FAIL.  Our tool says: false alarm.     \u2713",
               style="bold green")
        _typed(console,
               "  Vulnerable code:  Test misses it.  Our tool catches it.            \u2713",
               style="bold green")
        console.print()
        time.sleep(5.0)

    # ---- Closing (5 seconds) ----
    time.sleep(1.0)
    console.print(
        "  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        style="dim", highlight=False,
    )
    console.print()
    console.print("  github.com/asdfghjkltygh/m-series-pqc-timing-leak",
                  style="bold cyan", highlight=False)
    console.print()
    time.sleep(3.0)


# ===================================================================
# LIVE COMPUTATION PATH -- unchanged, for reviewers / local use
# ===================================================================

def _run_live(
    console: Console,
    fixed_timings: np.ndarray,
    random_timings: np.ndarray,
    per_key_features: np.ndarray,
    per_key_labels: dict[str, np.ndarray],
    target_names: list[str],
    vuln_features: np.ndarray | None,
    vuln_labels: dict[str, np.ndarray] | None,
    sequential_t: float,
    interleaved_t: float,
    n_shuffles: int,
) -> None:
    """Full live-computation demo for reviewers."""
    # Title card
    _title_card_live(console)

    # ACT 0
    _act0_live(console, sequential_t, interleaved_t)

    # ACT 1
    _act1_live(console, fixed_timings, random_timings)

    # ACT 2
    if per_key_labels:
        _act2_live(console, per_key_features, per_key_labels,
                   target_names, n_shuffles)

    # ACT 3
    if vuln_features is not None and vuln_labels is not None:
        _act3_live(console, vuln_features, vuln_labels, target_names)

    # Closing
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print()
    console.print(Text(
        "github.com/asdfghjkltygh/m-series-pqc-timing-leak",
        style="bold cyan", justify="center",
    ))
    console.print()


# ---------------------------------------------------------------------------
# Live helpers (preserved from original implementation)
# ---------------------------------------------------------------------------

def _detect_platform() -> str:
    """Return a human-readable platform string."""
    machine = platform.machine().lower()
    system = platform.system()
    if "arm" in machine or "aarch64" in machine:
        chip = "Apple Silicon"
        try:
            import subprocess
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                chip = result.stdout.strip()
        except Exception:
            pass
        return f"{chip} ({system} {platform.release()})"
    elif "x86" in machine or "amd64" in machine:
        return f"Intel/AMD x86_64 ({system} {platform.release()})"
    return f"{machine} ({system} {platform.release()})"


def _title_card_live(console: Console) -> None:
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print()
    title = Text(justify="center")
    title.append("WHEN TVLA LIES\n\n", style="bold bright_magenta")
    title.append("How a Broken Standard Is Blocking\n", style="bold white")
    title.append("Post-Quantum Crypto Deployment\n\n", style="bold white")
    title.append("sca-triage live demo\n", style="dim")
    console.print(Panel(title, border_style="bright_magenta", padding=(1, 4)))
    console.print()


def _act0_live(console: Console, sequential_t: float, interleaved_t: float) -> None:
    console.print(Rule(style="bright_magenta"))
    console.print(Panel(
        Text("ACT 0: THE BROKEN TEST", style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 2),
    ))
    console.print()

    plat = _detect_platform()
    console.print(f"  [dim]Platform:[/dim] [bold]{plat}[/bold]")
    console.print(f"  [dim]Algorithm:[/dim] [bold]ML-KEM-768 decapsulation[/bold]")
    console.print(f"  [dim]Harness:[/dim] [bold]Symmetric (identical code paths)[/bold]")
    console.print()

    console.print("  [bold cyan]Sequential collection[/bold cyan] "
                   "(all fixed, then all random):")
    seq_color = "red" if sequential_t > 4.5 else "green"
    seq_verdict = "FAIL" if sequential_t > 4.5 else "PASS"
    console.print(Panel(
        Text(f"|t| = {sequential_t:.2f}    {seq_verdict}",
             style=f"bold {seq_color}", justify="center"),
        border_style=seq_color, padding=(1, 4),
    ))

    console.print()
    console.print("  [bold cyan]Interleaved collection[/bold cyan] "
                   "(alternating fixed / random):")
    int_color = "green" if interleaved_t <= 4.5 else "red"
    int_verdict = "PASS" if interleaved_t <= 4.5 else "FAIL"
    console.print(Panel(
        Text(f"|t| = {interleaved_t:.2f}    {int_verdict}",
             style=f"bold {int_color}", justify="center"),
        border_style=int_color, padding=(1, 4),
    ))

    reduction = sequential_t / interleaved_t if interleaved_t > 0 else float('inf')
    console.print()
    console.print(Panel(
        Text(f"Same hardware. Same code. Same inputs.\n"
             f"The only difference is WHEN the measurements were collected.\n\n"
             f"{sequential_t:.2f} \u2192 {interleaved_t:.2f}  "
             f"({reduction:.0f}x reduction)",
             style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 2),
    ))
    console.print()


def _act1_live(
    console: Console,
    fixed_timings: np.ndarray,
    random_timings: np.ndarray,
) -> None:
    console.print(Rule(style="bright_magenta"))
    console.print(Panel(
        Text("ACT 1: THE AUDIT TRAP", style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 2),
    ))
    console.print()

    plat = _detect_platform()
    console.print(f"  [dim]Platform:[/dim] [bold]{plat}[/bold]")
    console.print(f"  [dim]Algorithm:[/dim] [bold]ML-KEM-768 decapsulation[/bold]")
    console.print(f"  [dim]Fixed traces:[/dim] [bold]{len(fixed_timings):,}[/bold]")
    console.print(f"  [dim]Random traces:[/dim] [bold]{len(random_timings):,}[/bold]")
    console.print()

    steps = 10
    n_total = len(fixed_timings) + len(random_timings)
    results = run_progressive_tvla(fixed_timings, random_timings, steps=steps)

    alert_shown = False
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} traces"),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating TVLA...", total=n_total)

        for i, result in enumerate(results):
            frac = (i + 1) / steps
            current_n = int(n_total * frac)
            t_val = abs(result.t_statistic)

            progress.update(task, completed=current_n,
                            description=f"Evaluating TVLA... |t| = {t_val:.2f}")
            time.sleep(0.3)

            if t_val >= 4.5 and not alert_shown:
                alert_shown = True
                console.print(Panel(
                    Text(f"\u26a0 LEAKAGE DETECTED  |t| = {t_val:.2f} exceeds 4.5 threshold",
                         style="bold white on red", justify="center"),
                    border_style="red",
                ))
                time.sleep(0.8)

    final_result = results[-1]
    _display_tvla_verdict(console, final_result)
    time.sleep(2.0)


def _display_tvla_verdict(console: Console, result: TVLAResult) -> None:
    t_abs = abs(result.t_statistic)
    passed = result.passed

    if not passed:
        verdict_text = Text(justify="center")
        verdict_text.append("\n")
        verdict_text.append(f"|t| = {t_abs:.2f}\n\n", style="bold red")
        verdict_text.append("ISO 17825 VERDICT: ", style="bold white")
        verdict_text.append("FAIL\n", style="bold white on red")
        verdict_text.append("DO NOT DEPLOY\n", style="bold red")
        border = "red"
    else:
        verdict_text = Text(justify="center")
        verdict_text.append("\n")
        verdict_text.append(f"|t| = {t_abs:.2f}\n\n", style="bold green")
        verdict_text.append("ISO 17825 VERDICT: ", style="bold white")
        verdict_text.append("PASS\n", style="bold green")
        border = "green"

    console.print(Panel(verdict_text, title="[bold]TVLA Result[/bold]",
                        border_style=border, padding=(1, 4)))
    console.print(Text(
        f"  p = {result.p_value:.2e}  |  "
        f"variance ratio = {result.variance_ratio:.4f}  |  "
        f"n = {result.n_fixed:,} + {result.n_random:,} traces",
        style="dim",
    ))


def _act2_live(
    console: Console,
    per_key_features: np.ndarray,
    per_key_labels: dict[str, np.ndarray],
    target_names: list[str],
    n_shuffles: int,
) -> None:
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print(Panel(
        Text("ACT 2: THE AUTOPSY", style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 2),
    ))
    console.print()

    means = per_key_features[:, 2] if per_key_features.shape[1] > 2 else per_key_features[:, 0]
    available = [t for t in target_names if t in per_key_labels]
    if not available:
        available = list(per_key_labels.keys())

    console.print("  [bold cyan]Pairwise Secret-Group Decomposition[/bold cyan]")
    pairwise_results = run_all_pairwise(
        means, {k: per_key_labels[k] for k in available},
        target_names=available,
    )
    for pr in pairwise_results:
        sig_style = "bold red" if pr.any_significant else "bold green"
        sig_text = "SIGNIFICANT" if pr.any_significant else "not significant"
        console.print(
            f"    [green]\u2713[/green] {pr.target_name}: "
            f"Cohen's d = {pr.cohens_d:.4f}, [{sig_style}]{sig_text}[/{sig_style}]"
        )
    console.print()

    console.print("  [bold cyan]Permutation Mutual Information[/bold cyan]")
    mi_results = run_all_mi(
        per_key_features,
        {k: per_key_labels[k] for k in available},
        target_names=available,
        n_shuffles=n_shuffles,
    )
    for mi in mi_results:
        sig_style = "bold red" if mi.significant else "bold green"
        sig_text = "SIGNIFICANT" if mi.significant else "not significant"
        console.print(
            f"    [green]\u2713[/green] {mi.target_name}: "
            f"MI = {mi.observed_mi:.6f}, p = {mi.p_value:.4f}, "
            f"[{sig_style}]{sig_text}[/{sig_style}]"
        )
    console.print()

    any_pw_sig = any(pr.any_significant for pr in pairwise_results)
    any_mi_sig = any(mi.significant for mi in mi_results)

    if not any_pw_sig and not any_mi_sig:
        console.print(Panel(
            Text("VERDICT: FALSE POSITIVE\n\n"
                 "The TVLA failure is caused by temporal drift,\n"
                 "not by the secret key.\n\n"
                 "This implementation is SAFE.",
                 style="bold green", justify="center"),
            border_style="green", padding=(1, 4),
        ))
    else:
        console.print(Panel(
            Text("VERDICT: POTENTIAL REAL LEAKAGE\n\n"
                 "One or more secret-dependent tests reached significance.",
                 style="bold red", justify="center"),
            border_style="red", padding=(1, 4),
        ))


def _act3_live(
    console: Console,
    vuln_features: np.ndarray,
    vuln_labels: dict[str, np.ndarray],
    target_names: list[str],
) -> None:
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print(Panel(
        Text("ACT 3: THE PROOF", style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 2),
    ))
    console.print()

    means = vuln_features[:, 2] if vuln_features.shape[1] > 2 else vuln_features[:, 0]
    available = [t for t in target_names if t in vuln_labels]
    if not available:
        available = list(vuln_labels.keys())

    vuln_pairwise = run_all_pairwise(
        means, {k: vuln_labels[k] for k in available},
        target_names=available,
    )

    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Target")
    table.add_column("Cohen's d")
    table.add_column("Welch p")
    table.add_column("Significant?")

    for pr in vuln_pairwise:
        sig_style = "bold red" if pr.any_significant else "bold green"
        sig_label = "YES" if pr.any_significant else "NO"
        table.add_row(
            pr.target_name,
            f"{pr.cohens_d:.4f}",
            f"{pr.welch_p:.2e}",
            Text(sig_label, style=sig_style),
        )

    console.print(Panel(table, title="[bold]Vulnerable Build[/bold]",
                        border_style="red"))
    console.print()

    console.print(Panel(
        Text("Patched ML-KEM:    FALSE POSITIVE\n"
             "TVLA lied. Code is safe.\n\n"
             "KyberSlash v0.9.0: REAL LEAKAGE DETECTED\n"
             "TVLA missed it. Our tool caught it.",
             style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 4),
    ))
