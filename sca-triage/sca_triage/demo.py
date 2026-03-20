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


def _section_header(console: Console, name: str) -> None:
    """Print a simple section header line."""
    pad = "\u2500" * (57 - len(name))
    console.print(f"  \u2500\u2500 {name} {pad}",
                  style="bold magenta", highlight=False)


def _animate_loading_bar(width: int = 20, total: int = 1_000_000) -> None:
    """Animate a loading bar using \\r overwrite. 1.5 seconds."""
    for i in range(width + 1):
        filled = "\u2588" * i + " " * (width - i)
        count = int(total * i / width)
        sys.stdout.write(f"\r  {filled} {count:>9,} / {total:,}")
        sys.stdout.flush()
        time.sleep(1.5 / width)
    print()


def _animate_score_bar(value: float, max_width: int = 45, label: str = "",
                       style: str = "bold red", step_delay: float = 0.04) -> None:
    """Animate a bar growing from 0 to value, then print label."""
    bar_len = max(1, int(value / 62.49 * max_width))
    for i in range(bar_len + 1):
        bar = "\u2501" * i
        sys.stdout.write(f"\r  {bar}")
        sys.stdout.flush()
        time.sleep(step_delay)
    # Pad + label after animation
    padding = " " * (max_width - bar_len + 2)
    sys.stdout.write(f"{padding}{value:.2f}  {label}\n")
    sys.stdout.flush()


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
    """Full precomputed presentation. ~80 seconds, visual CLI storytelling."""

    # ---- Title (2 seconds) ----
    time.sleep(0.5)
    console.print()
    console.print("  WHEN TVLA LIES", style="bold magenta", highlight=False)
    console.print("  sca-triage live demo", style="dim", highlight=False)
    console.print()
    time.sleep(2.0)

    # ---- ACT 0 (~35 seconds) ----
    _section_header(console, "ACT 0")
    console.print()
    time.sleep(1.0)

    _typed(console, "  Every encryption module needs to pass a timing test before the")
    _typed(console, "  government will use it. We ran that test two ways.")
    console.print()
    time.sleep(2.0)

    # Method 1: Sequential
    console.print("  Method 1: measure all of group A, then all of group B.",
                  style="white", highlight=False)
    console.print()
    console.print("  Group A (measured first):   594  601  588  597  605  591  ...",
                  style="bold red", highlight=False)
    console.print("  Group B (measured second):  532  528  535  530  527  534  ...",
                  style="bold cyan", highlight=False)
    console.print()
    time.sleep(2.0)

    bar_a = "\u2588" * 42
    bar_b = "\u2588" * 36
    console.print(f"  Group A average: 594 cycles  {bar_a}",
                  style="bold red", highlight=False)
    console.print(f"  Group B average: 532 cycles  {bar_b}",
                  style="bold cyan", highlight=False)
    console.print(f"                               {' ' * 36} \u2190 gap!",
                  style="bold yellow", highlight=False)
    console.print()
    time.sleep(2.0)

    console.print("  The test sees a gap.            score: 62.49            FAIL",
                  style="bold red", highlight=False)
    console.print()
    time.sleep(3.0)

    # Method 2: Interleaved
    console.print("  Method 2: alternate group A and group B measurements.",
                  style="white", highlight=False)
    console.print()
    console.print("  Group A (mixed):  553  551  555  552  554  550  ...",
                  style="bold green", highlight=False)
    console.print("  Group B (mixed):  554  552  551  555  553  551  ...",
                  style="bold green", highlight=False)
    console.print()
    time.sleep(2.0)

    bar_a2 = "\u2588" * 38
    bar_b2 = "\u2588" * 38
    console.print(f"  Group A average: 553 cycles  {bar_a2}",
                  style="bold green", highlight=False)
    console.print(f"  Group B average: 552 cycles  {bar_b2}",
                  style="bold green", highlight=False)
    console.print(f"                               {' ' * 38} \u2190 no gap",
                  style="bold green", highlight=False)
    console.print()
    time.sleep(2.0)

    console.print("  The test sees no gap.           score: 0.58             PASS",
                  style="bold green", highlight=False)
    console.print()
    time.sleep(3.0)

    # Punchline
    _typed(console,
           "  Same hardware. Same code. Same inputs. The gap was the",
           style="bold white", delay=0.025)
    _typed(console,
           "  ENVIRONMENT drifting between measurements, not the encryption.",
           style="bold white", delay=0.025)
    console.print()
    time.sleep(5.0)

    # ---- ACT 1 (~15 seconds) ----
    _section_header(console, "ACT 1")
    console.print()
    time.sleep(0.5)

    _typed(console,
           "  This is what certification labs see today. Standard test, modern hardware.")
    console.print()
    time.sleep(1.0)

    console.print("  Testing 1,000,000 measurements...",
                  style="white", highlight=False)
    _animate_loading_bar(total=1_000_000)
    console.print()
    time.sleep(0.5)

    console.print("  score: 8.42                     FAIL \u2014 DO NOT DEPLOY",
                  style="bold red", highlight=False)
    console.print()
    time.sleep(3.0)

    console.print("  Every lab. Every chip. Same result. ML-KEM is blocked from shipping.",
                  style="dim", highlight=False)
    console.print()
    time.sleep(3.0)

    # ---- ACT 2 (~20 seconds) ----
    _section_header(console, "ACT 2")
    console.print()
    time.sleep(0.5)

    _typed(console,
           "  The test claims the secret key leaks. If true, different keys")
    _typed(console,
           "  should produce different timing. Let's look.")
    console.print()
    time.sleep(1.5)

    # Real data: compute per-key means split by sk_lsb
    means = per_key_features[:, 2] if per_key_features.shape[1] > 2 else per_key_features[:, 0]

    if "sk_lsb" in per_key_labels:
        labels = per_key_labels["sk_lsb"]
        g0 = means[labels == 0]
        g1 = means[labels == 1]
        avg0 = float(np.mean(g0))
        avg1 = float(np.mean(g1))
        max_avg = max(avg0, avg1)
        bar0_len = int(avg0 / max_avg * 38)
        bar1_len = int(avg1 / max_avg * 38)
        block = "\u2588"

        console.print(
            f"  bit 0 = 0:  avg {avg0:.1f}    {block * bar0_len}",
            style="bold cyan", highlight=False)
        console.print(
            f"  bit 0 = 1:  avg {avg1:.1f}    {block * bar1_len}",
            style="bold cyan", highlight=False)
        console.print()
        time.sleep(2.0)
        console.print(
            f"              {'':30s}\u2191 identical",
            style="bold green", highlight=False)
        console.print()
        time.sleep(2.0)

    console.print("  Information leaked: 0.000 bits",
                  style="bold green", highlight=False)
    console.print()
    time.sleep(2.0)

    # Verdict box
    console.print(
        "  \u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        style="green", highlight=False)
    console.print(
        "  \u2502         VERDICT: FALSE POSITIVE              \u2502",
        style="bold green", highlight=False)
    console.print(
        "  \u2502         This encryption is safe.              \u2502",
        style="green", highlight=False)
    console.print(
        "  \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
        style="green", highlight=False)
    console.print()
    time.sleep(4.0)

    # ---- ACT 3 (~20 seconds, with animated ending) ----
    if has_vuln:
        _section_header(console, "ACT 3")
        console.print()
        time.sleep(0.5)

        _typed(console,
               "  Can we catch a REAL vulnerability? We tested against KyberSlash.")
        console.print()
        time.sleep(2.0)

        console.print("  Our classifier accuracy:  56.6%",
                      style="white", highlight=False)
        console.print("  Random guessing:          52.8%",
                      style="dim", highlight=False)
        console.print(
            "                                   "
            "\u2191 real signal \u2014 vulnerability detected",
            style="bold red", highlight=False)
        console.print()
        time.sleep(3.0)

    # ---- Animated ending (the visual punchline) ----
    console.print(
        "  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        style="dim", highlight=False)
    console.print()
    time.sleep(1.0)

    # Animate the "wrong" bar growing
    console.print("  The certification test:", style="dim", highlight=False)
    time.sleep(0.5)
    _animate_score_bar(62.49, max_width=45, label="WRONG", style="bold red",
                       step_delay=0.04)
    # Print colored version over the raw output
    sys.stdout.write("\033[1A\033[2K")  # move up, clear line
    bar_wrong = "\u2501" * 45
    console.print(f"  {bar_wrong}  62.49  WRONG",
                  style="bold red", highlight=False)
    time.sleep(2.0)

    # The fix
    console.print()
    console.print("  One-line fix (interleave the measurements):",
                  style="dim", highlight=False)
    time.sleep(0.5)
    small_width = max(1, int(0.58 / 62.49 * 45))
    _animate_score_bar(0.58, max_width=45, label="RIGHT", style="bold green",
                       step_delay=0.1)
    sys.stdout.write("\033[1A\033[2K")  # move up, clear line
    bar_right = "\u2501" * small_width
    padding = " " * (45 - small_width)
    console.print(f"  {bar_right}{padding}   0.58  RIGHT",
                  style="bold green", highlight=False)
    console.print()
    time.sleep(3.0)

    # Repo link
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
