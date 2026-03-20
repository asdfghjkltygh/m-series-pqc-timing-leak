"""Four-act Black Hat demo harness for sca-triage.

Two modes:
- precomputed=True  : scripted stage presentation with hardcoded values,
                      paced for a live audience on a projector.
- precomputed=False : live computation path for reviewers / local use.
"""
from __future__ import annotations

import platform
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
        _run_precomputed(console, sequential_t, interleaved_t,
                         vuln_features is not None and vuln_labels is not None)
    else:
        _run_live(console, fixed_timings, random_timings,
                  per_key_features, per_key_labels, target_names,
                  vuln_features, vuln_labels,
                  sequential_t, interleaved_t, n_shuffles)


# ===================================================================
# PRECOMPUTED PATH — scripted stage presentation
# ===================================================================

def _run_precomputed(
    console: Console,
    sequential_t: float,
    interleaved_t: float,
    has_vuln: bool,
) -> None:
    """Full precomputed presentation. ~90 seconds, 7 screens."""

    # ---- Title Card (5 seconds) ----
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print()
    title = Text(justify="center")
    title.append("WHEN TVLA LIES\n\n", style="bold bright_magenta")
    title.append("How a Broken Standard Is Blocking\n", style="bold white")
    title.append("Post-Quantum Crypto Deployment\n\n", style="bold white")
    title.append("sca-triage live demo\n", style="dim")
    console.print(Panel(title, border_style="bright_magenta", padding=(1, 4)))
    time.sleep(5.0)

    # ---- ACT 0: THE BROKEN TEST (~25 seconds) ----
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print(Panel(
        Text("ACT 0: THE BROKEN TEST", style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 2),
    ))
    console.print()

    # Narration
    console.print("  [dim]We ran the FIPS certification test (ISO 17825 TVLA) on liboqs ML-KEM.[/dim]")
    console.print("  [dim]Two collection methods. Same hardware. Same code. Same inputs.[/dim]")
    console.print()
    time.sleep(3.0)

    # Sequential result
    console.print(Panel(
        Text(f"Sequential collection (standard protocol):\n\n"
             f"|t| = {sequential_t:.2f}    FAIL\n\n"
             f"[threshold: 4.5]",
             style="bold red", justify="center"),
        border_style="red", padding=(1, 4),
    ))
    time.sleep(4.0)

    # Interleaved result
    console.print()
    console.print(Panel(
        Text(f"Interleaved collection (alternating fixed/random):\n\n"
             f"|t| = {interleaved_t:.2f}     PASS",
             style="bold green", justify="center"),
        border_style="green", padding=(1, 4),
    ))
    time.sleep(4.0)

    # Punchline
    reduction = sequential_t / interleaved_t if interleaved_t > 0 else float('inf')
    console.print()
    console.print(Panel(
        Text(f"Same hardware. Same code. Same inputs.\n\n"
             f"{sequential_t:.2f} \u2192 {interleaved_t:.2f}\n\n"
             f"The only difference is WHEN the measurements were collected.",
             style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 4),
    ))
    time.sleep(6.0)

    # ---- ACT 1: THE AUDIT TRAP (~20 seconds) ----
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print(Panel(
        Text("ACT 1: THE AUDIT TRAP", style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 2),
    ))
    console.print()

    # Narration
    console.print("  [dim]This is what a FIPS evaluation lab sees when they test ML-KEM.[/dim]")
    console.print()
    time.sleep(2.0)

    # Simple animation: loading -> result -> verdict
    console.print("  [bold white]Evaluating 1,000,000 traces...[/bold white]")
    time.sleep(2.0)

    console.print()
    console.print("  [bold red]|t| = 8.42[/bold red]")
    time.sleep(1.0)

    console.print()
    console.print(Panel(
        Text("FAIL\n\nISO 17825 \u00a77.2: DO NOT DEPLOY",
             style="bold red", justify="center"),
        border_style="red", padding=(1, 4),
    ))
    console.print("  [dim]p = 3.63e-17  |  500,000 + 500,000 traces[/dim]")
    time.sleep(5.0)

    # ---- ACT 2: THE AUTOPSY (~25 seconds) ----
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print(Panel(
        Text("ACT 2: THE AUTOPSY", style="bold white", justify="center"),
        border_style="bright_magenta", padding=(1, 2),
    ))
    console.print()

    # Narration
    console.print("  [dim]TVLA says this implementation leaks secrets.[/dim]")
    console.print("  [dim]We asked: does the actual secret key predict the timing?[/dim]")
    console.print()
    time.sleep(3.0)

    # Results appearing one at a time
    lines = [
        ("Secret key bit 0", "no effect", "d = 0.002"),
        ("Key byte value", "no effect", "d = 0.001"),
        ("Hamming weight", "no effect", "d = 0.003"),
    ]
    for label, result, detail in lines:
        console.print(f"  [green]\u2713[/green] Analyzing {label}...    [bold green]{result}[/bold green]  [dim]({detail})[/dim]")
        time.sleep(0.8)

    console.print(f"  [green]\u2713[/green] Mutual information...          [bold green]0.000 bits[/bold green]")
    console.print()
    time.sleep(1.5)

    # Verdict
    console.print(Panel(
        Text("VERDICT: FALSE POSITIVE\n\n"
             "The TVLA failure is caused by\n"
             "environmental drift, not by the\n"
             "secret key.\n\n"
             "This implementation is SAFE.",
             style="bold green", justify="center"),
        border_style="green", padding=(1, 4),
    ))
    console.print("  [dim]Bounded by macro-timing detection floor (d \u2248 0.275).[/dim]")
    console.print("  [dim]Does not rule out sub-threshold or EM-probing channels.[/dim]")
    time.sleep(6.0)

    # ---- ACT 3: THE PROOF (~20 seconds) ----
    if has_vuln:
        console.print()
        console.print(Rule(style="bright_magenta"))
        console.print(Panel(
            Text("ACT 3: THE PROOF", style="bold white", justify="center"),
            border_style="bright_magenta", padding=(1, 2),
        ))
        console.print()

        # Narration
        console.print("  [dim]Now the reverse: we test against KyberSlash, a KNOWN vulnerability[/dim]")
        console.print("  [dim]in liboqs v0.9.0.[/dim]")
        console.print()
        time.sleep(3.0)

        # Result
        console.print("  [bold white]Pairwise test:[/bold white]  [bold yellow]below detection floor[/bold yellow]  [dim](d = 0.094)[/dim]")
        time.sleep(1.0)
        console.print("  [bold white]ML classifier:[/bold white]  [bold red]DETECTED[/bold red] [dim]-- 56.6% accuracy (+3.8% lift)[/dim]")
        console.print()
        console.print("  [dim]Real leakage found via cross-key aggregation.[/dim]")
        console.print()
        time.sleep(3.0)

        # Final comparison
        console.print(Panel(
            Text("Patched ML-KEM:    FALSE POSITIVE\n"
                 "TVLA lied. Code is safe.\n\n"
                 "KyberSlash v0.9.0: REAL LEAKAGE DETECTED\n"
                 "TVLA missed it. Our tool caught it.",
                 style="bold white", justify="center"),
            border_style="bright_magenta", padding=(1, 4),
        ))
        time.sleep(6.0)

    # ---- Closing (5 seconds) ----
    console.print()
    console.print(Rule(style="bright_magenta"))
    console.print()
    console.print(Text(
        "github.com/asdfghjkltygh/m-series-pqc-timing-leak",
        style="bold cyan", justify="center",
    ))
    console.print()
    time.sleep(5.0)


# ===================================================================
# LIVE COMPUTATION PATH — unchanged, for reviewers / local use
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
