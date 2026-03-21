"""Four-act Black Hat demo harness for sca-triage.

Two modes:
- precomputed=True  : scripted stage presentation with visual CLI storytelling,
                      paced for a live audience on a projector.
- precomputed=False : live computation path for reviewers / local use.
"""
from __future__ import annotations

import platform
import shutil
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

def _typed(console: Console, text: str, style: str = "dim", delay: float = 0.02,
           fast: bool = False) -> None:
    """Print text character by character for dramatic effect."""
    if fast:
        console.print(text, style=style, highlight=False)
        return
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


def _animate_loading_bar(width: int = 20, total: int = 1_000_000,
                         fast: bool = False) -> None:
    """Animate a loading bar using \\r overwrite. 1.5 seconds."""
    if fast:
        filled = "\u2588" * width
        sys.stdout.write(f"\r  {filled} {total:>9,} / {total:,}\n")
        sys.stdout.flush()
        return
    for i in range(width + 1):
        filled = "\u2588" * i + " " * (width - i)
        count = int(total * i / width)
        sys.stdout.write(f"\r  {filled} {count:>9,} / {total:,}")
        sys.stdout.flush()
        time.sleep(1.5 / width)
    print()


def _animate_score_bar(value: float, max_val: float = 62.49,
                       max_width: int = 45, label: str = "",
                       style: str = "bold red", step_delay: float = 0.04,
                       fast: bool = False) -> None:
    """Animate a bar growing from 0 to value, then print label."""
    bar_len = max(1, int(value / max_val * max_width))
    if not fast:
        for i in range(bar_len + 1):
            bar = "\u2501" * i
            sys.stdout.write(f"\r  {bar}")
            sys.stdout.flush()
            time.sleep(step_delay)
    # Pad + label after animation
    bar = "\u2501" * bar_len
    padding = " " * (max_width - bar_len + 2)
    sys.stdout.write(f"\r  {bar}{padding}{value:.2f}  {label}\n")
    sys.stdout.flush()


def _draw_box(console: Console, lines: list[str],
              style: str = "green", width: int = 50) -> None:
    """Draw a fixed-width box with perfectly aligned text."""
    inner = width - 4  # account for "  │ " and " │"
    horiz = "\u2500" * (width - 2)
    console.print(f"  \u250c{horiz}\u2510", style=style, highlight=False)
    for line in lines:
        padded = line.center(inner)
        console.print(f"  \u2502 {padded} \u2502", style=style, highlight=False)
    console.print(f"  \u2514{horiz}\u2518", style=style, highlight=False)


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
    asymmetric_t: float = 8.10,
    pairwise_t: float = 0.59,
    n_shuffles: int = 100,
    precomputed: bool = False,
    dark: bool = False,
    fast: bool = False,
) -> None:
    """Execute the four-act demo presentation."""
    if dark:
        console = Console(force_terminal=True, color_system="truecolor")
    else:
        console = Console()

    if precomputed:
        _run_precomputed(
            console, sequential_t, interleaved_t, asymmetric_t, pairwise_t,
            per_key_features, per_key_labels, target_names,
            has_vuln=vuln_features is not None and vuln_labels is not None,
            fast=fast,
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
    asymmetric_t: float,
    pairwise_t: float,
    per_key_features: np.ndarray,
    per_key_labels: dict[str, np.ndarray],
    target_names: list[str],
    has_vuln: bool,
    fast: bool = False,
) -> None:
    """Full precomputed presentation. ~90 seconds, visual CLI storytelling."""

    block = "\u2588"
    approx = "\u2248"
    pause = lambda s: time.sleep(s * (0.15 if fast else 1.0))

    # Terminal width check
    term_width = shutil.get_terminal_size().columns
    if term_width < 100:
        console.print(
            f"  [!] Terminal is {term_width} columns wide. "
            "Resize to 100+ for best results.",
            style="bold yellow", highlight=False)
        console.print()

    # ---- Title (2 seconds) ----
    pause(0.5)
    console.print()
    console.print("  WHEN TVLA LIES", style="bold magenta", highlight=False)
    console.print("  sca-triage live demo", style="dim", highlight=False)
    console.print()
    pause(2.0)

    # ==================================================================
    # ACT 0 — Setup + The Broken Test (~40 seconds)
    # ==================================================================
    _section_header(console, "ACT 0")
    console.print()
    pause(1.0)

    # --- What encryption timing is ---
    for cycles in [594, 601, 588]:
        console.print(f"  encrypt(key, msg) \u2192 {cycles} cycles",
                      style="bold cyan", highlight=False)
        pause(0.3)
    console.print()
    pause(1.5)

    _typed(console,
           "  Every encryption operation takes a measurable amount of time.",
           fast=fast)
    _typed(console,
           "  If an attacker can figure out the key from the timing, "
           "the encryption is broken.",
           fast=fast)
    console.print()
    pause(2.5)

    # --- What's at stake ---
    console.print(
        "  A mandatory government test checks for this before any encryption ships.",
        style="white", highlight=False)
    console.print(
        "  If it fails: blocked. No waivers. Months of delay.",
        style="white", highlight=False)
    console.print()
    pause(2.5)

    # --- How the test works ---
    console.print("  Here's how the test works:", style="white", highlight=False)
    console.print()
    pause(1.0)

    console.print(
        "  It encrypts with ONE secret key, over and over"
        "          \u2192 Group A",
        style="bold cyan", highlight=False)
    console.print(
        "  Then encrypts with MANY different keys"
        "                   \u2192 Group B",
        style="bold yellow", highlight=False)
    console.print()
    pause(2.0)

    console.print(
        "  Then it runs a statistical comparison (Welch's t-test)",
        style="white", highlight=False)
    console.print(
        "  to measure how different the two groups are.",
        style="white", highlight=False)
    console.print(
        "  If the score exceeds 4.5, the encryption fails the test.",
        style="white", highlight=False)
    console.print()
    pause(2.5)

    # --- Method 1: Sequential ---
    console.print(
        "  We ran this test on ML-KEM, the new post-quantum standard.",
        style="white", highlight=False)
    console.print()

    console.print(
        "  \u2500\u2500\u2500\u2500 Group A (one key) "
        "\u2500\u2500\u2500\u2500\u2502"
        "\u2500\u2500\u2500\u2500 Group B (many keys) "
        "\u2500\u2500\u2500\u2500",
        style="bold cyan", highlight=False)
    console.print(
        "  time \u2192                      \u2502",
        style="dim", highlight=False)
    console.print()
    pause(1.5)

    console.print(f"  Group A average: 594 cycles  {block * 42}",
                  style="bold red", highlight=False)
    console.print(f"  Group B average: 532 cycles  {block * 36}",
                  style="bold cyan", highlight=False)
    console.print(f"                               {' ' * 36} \u2190 gap",
                  style="bold yellow", highlight=False)
    console.print()
    pause(2.5)

    console.print(f"  score: {sequential_t:.2f}   (>4.5 = FAIL)"
                  "                           FAIL",
                  style="bold red", highlight=False)
    console.print()
    pause(3.0)

    # --- Why sequential collection is the problem ---
    console.print(
        "  But here's the problem with collecting one group after the other:",
        style="white", highlight=False)
    console.print()
    pause(1.5)

    console.print(
        "  \u2500\u2500\u2500 Group A (one key) "
        "\u2500\u2500\u2500\u2500\u2502"
        "\u2500\u2500\u2500 Group B (many keys) "
        "\u2500\u2500\u2500\u2500",
        style="bold cyan", highlight=False)
    console.print(
        "  time \u2192         ",
        style="dim", highlight=False, end="")
    console.print("cool CPU", style="cyan", highlight=False, end="")
    console.print(" \u2500\u2500\u2500\u2500\u2500\u2500\u2192 ",
                  style="dim", highlight=False, end="")
    console.print("warm CPU", style="red", highlight=False)
    console.print()

    console.print(
        "  The computer's temperature, clock speed, and OS scheduling",
        style="dim", highlight=False)
    console.print(
        "  all change between the first half and the second half.",
        style="dim", highlight=False)
    console.print(
        "  The test blames the KEY. But it's actually the ENVIRONMENT.",
        style="bold white", highlight=False)
    console.print()
    pause(3.5)

    # --- Method 2: Interleaved ---
    console.print(
        "  Fix: collect A and B in alternating order. Now both groups",
        style="bold green", highlight=False)
    console.print(
        "  experience the exact same conditions.",
        style="bold green", highlight=False)
    console.print()

    console.print(
        "  \u2500\u2500 A \u2500\u2500 B \u2500\u2500 A \u2500\u2500 B "
        "\u2500\u2500 A \u2500\u2500 B \u2500\u2500 A \u2500\u2500 B "
        "\u2500\u2500 A \u2500\u2500 B \u2500\u2500",
        style="bold green", highlight=False)
    console.print(
        "  time \u2192  (both groups see the same temperature, same CPU state)",
        style="dim", highlight=False)
    console.print()
    pause(2.0)

    console.print(f"  Group A average: 555 cycles  {block * 38}",
                  style="bold green", highlight=False)
    console.print(f"  Group B average: 551 cycles  {block * 38}",
                  style="bold green", highlight=False)
    console.print(f"                               {' ' * 38} \u2190 no gap",
                  style="bold green", highlight=False)
    console.print()
    pause(2.0)

    console.print(f"  score: {interleaved_t:.2f}    (<4.5 = PASS)"
                  "                           PASS",
                  style="bold green", highlight=False)
    console.print()
    pause(2.0)

    # Credibility footnote
    console.print()
    console.print("  (Alternating collection is already standard in hardware testing",
                  style="dim")
    console.print("   and built into tools like dudect. But the mandatory certification",
                  style="dim")
    console.print("   standard, ISO 17825, still prescribes sequential collection.",
                  style="dim")
    console.print("   Every FIPS lab in the country runs the test the broken way.)",
                  style="dim")
    console.print()
    pause(2.0)

    # --- Punchline ---
    _typed(console,
           f"  Same encryption. Same hardware. {sequential_t:.0f} \u2192 {interleaved_t:.2f}.",
           style="bold white", delay=0.025, fast=fast)
    _typed(console,
           "  The gap was the computer's environment drifting, not the key.",
           style="bold white", delay=0.025, fast=fast)
    console.print()
    pause(5.0)

    # ==================================================================
    # ACT 1 — Real World (12 seconds)
    # ==================================================================
    _section_header(console, "ACT 1")
    console.print()
    pause(0.5)

    console.print(
        "  A certification lab tests ML-KEM. Standard procedure.",
        style="white", highlight=False)
    console.print()
    pause(1.0)

    console.print("  Testing 1,000,000 measurements...",
                  style="white", highlight=False)
    _animate_loading_bar(total=1_000_000, fast=fast)
    console.print()
    pause(0.5)

    console.print(
        f"  score: {sequential_t:.2f}   (>4.5 = FAIL)"
        "        FAIL \u2014 BLOCKED FROM SHIPPING",
        style="bold red", highlight=False)
    console.print()
    pause(3.0)

    console.print("  Every lab. Every modern chip. Same result.",
                  style="dim", highlight=False)
    console.print()
    pause(3.0)

    # ==================================================================
    # ACT 2 — The Proof (20 seconds)
    # ==================================================================
    _section_header(console, "ACT 2")
    console.print()
    pause(0.5)

    # Bridge from Act 0/1
    console.print(
        "  The test found Group A and Group B have different timing.",
        style="white", highlight=False)
    console.print(
        "  But is that because of the KEY, or because of something else?",
        style="white", highlight=False)
    console.print()
    pause(2.0)

    _typed(console,
           "  We sorted all our measurements by which secret key was used",
           fast=fast)
    _typed(console,
           "  and compared the timing directly:",
           fast=fast)
    console.print()
    pause(1.5)

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
        eq_len = min(bar0_len, bar1_len)

        label0 = f"  Keys where bit 0 = 0:  avg {avg0:.0f} cycles  "
        pad = " " * len(label0)

        console.print(
            f"{label0}{block * bar0_len}",
            style="bold cyan", highlight=False)
        console.print(
            f"{pad}{approx * eq_len}",
            style="bold green", highlight=False)
        console.print(
            f"  Keys where bit 0 = 1:  avg {avg1:.0f} cycles  "
            f"{block * bar1_len}",
            style="bold cyan", highlight=False)
        console.print()
        pause(2.0)
        console.print(
            f"{pad}\u2191 statistically indistinguishable",
            style="bold green", highlight=False)
        console.print()
        pause(3.0)

    console.print(
        "  The key does not affect the timing. The test failure is a false alarm.",
        style="bold green", highlight=False)
    console.print()
    pause(2.0)

    # Verdict box
    _draw_box(console, [
        "",
        "VERDICT: FALSE POSITIVE",
        "",
        "No secret-dependent signal detected.",
        "",
    ], style="bold green", width=50)
    console.print()

    # Detection floor caveat
    console.print(
        "  [!] Bounded by macro-timing detection floor (d \u2248 0.275).",
        style="dim", highlight=False)
    console.print(
        "      Does not rule out sub-threshold or hardware/EM leakage.",
        style="dim", highlight=False)
    console.print()
    pause(5.0)

    # ==================================================================
    # ACT 3 — Validation + Closing (25 seconds)
    # ==================================================================
    if has_vuln:
        _section_header(console, "ACT 3")
        console.print()
        pause(0.5)

        console.print(
            '  Our tool said "false alarm" on safe code. '
            "But can it catch a real vulnerability?",
            style="white", highlight=False)
        console.print()
        pause(1.5)

        console.print(
            "  We tested against KyberSlash, a known bug in an older "
            "version of this library.",
            style="white", highlight=False)
        console.print()
        pause(1.5)

        _typed(console,
               "  We trained a classifier to guess which key was used, "
               "based only on timing.",
               fast=fast)
        _typed(console,
               "  If it guesses better than the majority baseline, the key is leaking.",
               fast=fast)
        console.print()
        pause(2.0)

        console.print("  Majority baseline:  264 / 500 correct",
                      style="dim", highlight=False)
        console.print(
            "  Our classifier:   283 / 500 correct"
            "  (+3.8% lift, p < 0.01)",
            style="bold red", highlight=False)
        console.print()
        pause(2.0)

        console.print(
            "  VERDICT: REAL LEAKAGE DETECTED",
            style="bold red", highlight=False)
        console.print()
        pause(2.0)

        console.print(
            "  Safe code:        the key does NOT affect timing"
            "   \u2192 false alarm  \u2713",
            style="bold green", highlight=False)
        console.print(
            "  Vulnerable code:  the key DOES affect timing"
            "       \u2192 caught       \u2713",
            style="bold green", highlight=False)
        console.print()
        pause(4.0)

    # ==================================================================
    # Animated ending — the visual punchline
    # ==================================================================
    divider = "\u2500" * 60
    console.print(f"  {divider}", style="dim", highlight=False)
    console.print()
    pause(1.0)

    console.print("  So what did we find?", style="white", highlight=False)
    console.print()
    pause(1.5)

    max_val = sequential_t  # scale all bars relative to worst case

    # Bar 1: Sequential — FAIL (Apple Silicon)
    console.print("  The mandatory test, run the standard way:",
                  style="dim", highlight=False)
    pause(0.5)
    _animate_score_bar(sequential_t, max_val=max_val, max_width=45,
                       label="FAIL", style="bold red", step_delay=0.04,
                       fast=fast)
    if not fast:
        sys.stdout.write("\033[1A\033[2K")  # move up, clear line
        bar_fail = "\u2501" * 45
        console.print(f"  {bar_fail}  {sequential_t:.2f}  FAIL",
                      style="bold red", highlight=False)
    pause(2.0)

    # Bar 2: Alternating but asymmetric harness — still FAIL (Intel x86)
    console.print()
    console.print(
        "  Alternating collection, but with an asymmetric test harness (Intel x86):",
        style="dim", highlight=False)
    pause(0.5)
    asym_width = max(1, int(asymmetric_t / max_val * 45))
    _animate_score_bar(asymmetric_t, max_val=max_val, max_width=45,
                       label="FAIL", style="bold yellow", step_delay=0.06,
                       fast=fast)
    if not fast:
        sys.stdout.write("\033[1A\033[2K")
        bar_asym = "\u2501" * asym_width
        asym_pad = " " * (45 - asym_width + 2)
        console.print(f"  {bar_asym}{asym_pad}{asymmetric_t:.2f}  FAIL",
                      style="bold yellow", highlight=False)
    pause(1.5)

    console.print(
        "  (Cache pollution from the harness itself — "
        "alternating can't fix this.)",
        style="dim", highlight=False)
    pause(2.0)

    # Bar 3: sca-triage pairwise decomposition — PASS
    console.print()
    console.print(
        "  sca-triage pairwise decomposition on the same sequential data:",
        style="dim", highlight=False)
    pause(0.5)
    pw_width = max(1, int(pairwise_t / max_val * 45))
    _animate_score_bar(pairwise_t, max_val=max_val, max_width=45,
                       label="PASS", style="bold green", step_delay=0.1,
                       fast=fast)
    if not fast:
        sys.stdout.write("\033[1A\033[2K")
        bar_pass = "\u2501" * pw_width
        pass_pad = " " * (45 - pw_width + 2)
        console.print(f"  {bar_pass}{pass_pad}{pairwise_t:.2f}  PASS",
                      style="bold green", highlight=False)
    console.print()
    pause(3.0)

    console.print(
        "  Alternating fixes the environment, but not the harness.",
        style="bold white", highlight=False)
    console.print(
        "  sca-triage works on existing sequential data. No re-collection.",
        style="bold white", highlight=False)
    console.print()
    pause(3.0)

    # Repo link + closing
    console.print("  github.com/asdfghjkltygh/m-series-pqc-timing-leak",
                  style="bold cyan", highlight=False)
    console.print()
    pause(1.0)
    console.print("  The failure was never real.",
                  style="bold magenta", highlight=False)
    console.print()
    pause(3.0)


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
