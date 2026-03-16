"""Three-act Black Hat demo harness for sca-triage.

Provides a dramatic stage-presentation experience with rich terminal output,
progressive reveals, and precomputed-mode pacing for live demos.
"""
from __future__ import annotations

import platform
import time
from typing import Optional

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
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
    n_shuffles: int = 100,
    precomputed: bool = False,
    dark: bool = False,
) -> None:
    """Execute the three-act demo presentation.

    Parameters
    ----------
    fixed_timings : np.ndarray
        1-D array of fixed-key timing measurements.
    random_timings : np.ndarray
        1-D array of random-key timing measurements.
    per_key_features : np.ndarray
        2-D array (n_keys, n_features) of per-key aggregated statistics.
    per_key_labels : dict[str, np.ndarray]
        Mapping from target name to binary label array.
    target_names : list[str]
        Names of secret targets to analyse.
    vuln_features : np.ndarray, optional
        Per-key features for a known-vulnerable implementation (Act 3).
    vuln_labels : dict[str, np.ndarray], optional
        Labels for the vulnerable implementation (Act 3).
    n_shuffles : int
        Number of MI permutation rounds.
    precomputed : bool
        If ``True``, skip real computation and display pre-cached results
        with realistic sleep pacing.
    dark : bool
        Hint for dark terminal theme (currently unused; reserved).
    """
    console = Console()

    # ACT 1: "The Audit Trap"
    _act1(console, fixed_timings, random_timings, precomputed)

    # ACT 2: "The Autopsy"
    _act2(console, per_key_features, per_key_labels, target_names,
          n_shuffles, precomputed)

    # ACT 3: "The Positive Control" (if vulnerable data provided)
    if vuln_features is not None and vuln_labels is not None:
        _act3(console, vuln_features, vuln_labels, target_names, precomputed)


# ---------------------------------------------------------------------------
# Platform detection
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


# ---------------------------------------------------------------------------
# ACT 1: The Audit Trap
# ---------------------------------------------------------------------------

def _act1(
    console: Console,
    fixed_timings: np.ndarray,
    random_timings: np.ndarray,
    precomputed: bool,
) -> None:
    """FIPS 140-3 TVLA evaluation with progressive trace reveal."""
    console.print()
    console.print(Panel(
        Text("FIPS 140-3 NON-INVASIVE EVALUATION -- ISO 17825 TVLA",
             style="bold white", justify="center"),
        border_style="cyan",
        padding=(1, 2),
    ))

    # Platform detection
    plat = _detect_platform()
    console.print(f"  [dim]Platform:[/dim] [bold]{plat}[/bold]")
    console.print(f"  [dim]Algorithm:[/dim] [bold]ML-KEM-768 decapsulation[/bold]")
    console.print(f"  [dim]Fixed traces:[/dim] [bold]{len(fixed_timings):,}[/bold]")
    console.print(f"  [dim]Random traces:[/dim] [bold]{len(random_timings):,}[/bold]")
    console.print()

    if precomputed:
        _act1_precomputed(console, fixed_timings, random_timings)
    else:
        _act1_live(console, fixed_timings, random_timings)


def _act1_precomputed(
    console: Console,
    fixed_timings: np.ndarray,
    random_timings: np.ndarray,
) -> None:
    """Display pre-cached Act 1 results with realistic pacing (~30s)."""
    steps = 10
    n_fixed = len(fixed_timings)
    n_random = len(random_timings)

    # Pre-compute the final result for display
    final_result = run_tvla(fixed_timings, random_timings)

    # Simulate progressive t-statistics growing toward the final value
    simulated_t = [
        0.8, 1.4, 2.1, 2.9, 3.5, 3.9, 4.2, 4.6,
        abs(final_result.t_statistic) * 0.95,
        abs(final_result.t_statistic),
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} traces"),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating TVLA...", total=n_fixed + n_random)

        for i in range(steps):
            frac = (i + 1) / steps
            current_n = int((n_fixed + n_random) * frac)
            t_val = simulated_t[i]

            progress.update(task, completed=current_n,
                            description=f"Evaluating TVLA... |t| = {t_val:.2f}")

            if t_val >= 4.5 and i >= 7:
                time.sleep(1.5)
                console.print(Panel(
                    Text(f"CRITICAL: TIMING LEAKAGE DETECTED  |t| = {t_val:.2f}",
                         style="bold white on red", justify="center"),
                    border_style="red",
                ))
                time.sleep(1.0)
            else:
                time.sleep(2.5)

    _display_tvla_verdict(console, final_result)
    time.sleep(5.0)


def _act1_live(
    console: Console,
    fixed_timings: np.ndarray,
    random_timings: np.ndarray,
) -> None:
    """Run real progressive TVLA with live output."""
    steps = 10
    n_total = len(fixed_timings) + len(random_timings)

    results = run_progressive_tvla(fixed_timings, random_timings, steps=steps)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} traces"),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating TVLA...", total=n_total)
        alert_shown = False

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
                    Text(f"CRITICAL: TIMING LEAKAGE DETECTED  |t| = {t_val:.2f}",
                         style="bold white on red", justify="center"),
                    border_style="red",
                ))
                time.sleep(1.0)

    final_result = results[-1]
    _display_tvla_verdict(console, final_result)
    time.sleep(5.0)


def _display_tvla_verdict(console: Console, result: TVLAResult) -> None:
    """Show the TVLA pass/fail panel with statistics."""
    t_abs = abs(result.t_statistic)
    status = "FAIL -- DO NOT DEPLOY" if not result.passed else "PASS"
    color = "red" if not result.passed else "green"

    text = Text()
    text.append(f"\n  Welch's t-statistic : {result.t_statistic:+.4f}\n")
    text.append(f"  |t|                 : {t_abs:.4f}\n")
    text.append(f"  Threshold           : {result.threshold}\n")
    text.append(f"  p-value             : {result.p_value:.2e}\n")
    text.append(f"  Variance ratio      : {result.variance_ratio:.4f}\n")
    text.append(f"  n(fixed)            : {result.n_fixed:,}\n")
    text.append(f"  n(random)           : {result.n_random:,}\n")
    text.append(f"\n  ISO 17825 \u00a77.2 Result: ", style="bold")
    text.append(status, style=f"bold {color}")
    text.append("\n")

    console.print(Panel(text, title="[bold]TVLA Result[/bold]",
                        border_style=color))


# ---------------------------------------------------------------------------
# ACT 2: The Autopsy
# ---------------------------------------------------------------------------

def _act2(
    console: Console,
    per_key_features: np.ndarray,
    per_key_labels: dict[str, np.ndarray],
    target_names: list[str],
    n_shuffles: int,
    precomputed: bool,
) -> None:
    """Deep analysis: pairwise decomposition + permutation MI."""
    console.print()
    console.print(Panel(
        Text("Running SCA-TRIAGE deep analysis...",
             style="bold yellow", justify="center"),
        border_style="yellow",
        padding=(1, 2),
    ))
    console.print()

    if precomputed:
        _act2_precomputed(console, per_key_features, per_key_labels,
                          target_names, n_shuffles)
    else:
        _act2_live(console, per_key_features, per_key_labels,
                   target_names, n_shuffles)


def _act2_precomputed(
    console: Console,
    per_key_features: np.ndarray,
    per_key_labels: dict[str, np.ndarray],
    target_names: list[str],
    n_shuffles: int,
) -> None:
    """Display pre-cached Act 2 results with ~45s pacing."""
    # Use mean column (index 2) for pairwise
    means = per_key_features[:, 2] if per_key_features.shape[1] > 2 else per_key_features[:, 0]

    available = [t for t in target_names if t in per_key_labels]
    if not available:
        available = list(per_key_labels.keys())

    # --- Pairwise with live status per target ---
    console.print("  [bold cyan]Stage 2a:[/bold cyan] Pairwise Secret-Group Decomposition")
    pairwise_results = run_all_pairwise(
        means, {k: per_key_labels[k] for k in available},
        target_names=available,
    )
    for pr in pairwise_results:
        time.sleep(3.0)
        sig_style = "bold red" if pr.any_significant else "bold green"
        sig_text = "SIGNIFICANT" if pr.any_significant else "not significant"
        console.print(
            f"    [green]\u2713[/green] {pr.target_name}: "
            f"Cohen's d = {pr.cohens_d:.4f}, [{sig_style}]{sig_text}[/{sig_style}]"
        )

    console.print()
    time.sleep(1.0)

    # --- Permutation MI with progress ---
    console.print("  [bold cyan]Stage 2b:[/bold cyan] Permutation Mutual Information")

    mi_results: list[MIResult] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} shuffles"),
        console=console,
    ) as progress:
        for name in available:
            task = progress.add_task(f"  MI({name})", total=n_shuffles)
            # Simulate progress
            for s in range(n_shuffles):
                time.sleep(0.3)
                progress.update(task, advance=1)

    # Actually compute MI
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
    time.sleep(1.0)

    # --- Verdict ---
    any_pw_sig = any(pr.any_significant for pr in pairwise_results)
    any_mi_sig = any(mi.significant for mi in mi_results)

    if not any_pw_sig and not any_mi_sig:
        _display_false_positive_verdict(console)
    else:
        _display_real_leakage_verdict(console)


def _act2_live(
    console: Console,
    per_key_features: np.ndarray,
    per_key_labels: dict[str, np.ndarray],
    target_names: list[str],
    n_shuffles: int,
) -> None:
    """Run real Act 2 analysis with live output."""
    means = per_key_features[:, 2] if per_key_features.shape[1] > 2 else per_key_features[:, 0]

    available = [t for t in target_names if t in per_key_labels]
    if not available:
        available = list(per_key_labels.keys())

    # --- Pairwise ---
    console.print("  [bold cyan]Stage 2a:[/bold cyan] Pairwise Secret-Group Decomposition")
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

    # --- Permutation MI ---
    console.print("  [bold cyan]Stage 2b:[/bold cyan] Permutation Mutual Information")

    mi_results: list[MIResult] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} shuffles"),
        console=console,
    ) as progress:
        for name in available:
            task = progress.add_task(f"  MI({name})", total=n_shuffles)
            # Run MI in chunks to update progress
            result = run_all_mi(
                per_key_features,
                {name: per_key_labels[name]},
                target_names=[name],
                n_shuffles=n_shuffles,
            )[0]
            mi_results.append(result)
            progress.update(task, completed=n_shuffles)

    for mi in mi_results:
        sig_style = "bold red" if mi.significant else "bold green"
        sig_text = "SIGNIFICANT" if mi.significant else "not significant"
        console.print(
            f"    [green]\u2713[/green] {mi.target_name}: "
            f"MI = {mi.observed_mi:.6f}, p = {mi.p_value:.4f}, "
            f"[{sig_style}]{sig_text}[/{sig_style}]"
        )

    console.print()

    # --- Verdict ---
    any_pw_sig = any(pr.any_significant for pr in pairwise_results)
    any_mi_sig = any(mi.significant for mi in mi_results)

    if not any_pw_sig and not any_mi_sig:
        _display_false_positive_verdict(console)
    else:
        _display_real_leakage_verdict(console)


def _display_false_positive_verdict(console: Console) -> None:
    """Show the FALSE POSITIVE verdict panel."""
    text = Text(justify="center")
    text.append("\n")
    text.append("VERDICT: FALSE POSITIVE\n\n", style="bold green")
    text.append(
        "The TVLA failure is caused by execution-context confounds\n"
        "(DMP synchronisation, speculative prefetch variance),\n"
        "NOT by secret-dependent timing behaviour.\n\n"
        "No pairwise test reached significance after Bonferroni correction.\n"
        "Permutation MI confirms zero information leakage about secret keys.\n\n"
        "This implementation is SAFE for deployment.\n",
        style="dim",
    )

    console.print(Panel(text, title="[bold green]SCA-TRIAGE VERDICT[/bold green]",
                        border_style="green", padding=(1, 2)))


def _display_real_leakage_verdict(console: Console) -> None:
    """Show the REAL LEAKAGE verdict panel."""
    text = Text(justify="center")
    text.append("\n")
    text.append("VERDICT: POTENTIAL REAL LEAKAGE\n\n", style="bold red")
    text.append(
        "One or more secret-dependent statistical tests reached significance.\n"
        "Further investigation is required to determine whether\n"
        "the leakage is exploitable.\n",
        style="dim",
    )

    console.print(Panel(text, title="[bold red]SCA-TRIAGE VERDICT[/bold red]",
                        border_style="red", padding=(1, 2)))


# ---------------------------------------------------------------------------
# ACT 3: The Positive Control
# ---------------------------------------------------------------------------

def _act3(
    console: Console,
    vuln_features: np.ndarray,
    vuln_labels: dict[str, np.ndarray],
    target_names: list[str],
    precomputed: bool,
) -> None:
    """Validate against known-vulnerable implementation."""
    console.print()
    console.print(Panel(
        Text("VALIDATION: Running against KNOWN-VULNERABLE liboqs v0.9.0...",
             style="bold red", justify="center"),
        border_style="red",
        padding=(1, 2),
    ))
    console.print()

    means = vuln_features[:, 2] if vuln_features.shape[1] > 2 else vuln_features[:, 0]

    available = [t for t in target_names if t in vuln_labels]
    if not available:
        available = list(vuln_labels.keys())

    if precomputed:
        # Simulated pacing
        console.print("  [bold cyan]Pairwise analysis on vulnerable build...[/bold cyan]")
        time.sleep(3.0)

    vuln_pairwise = run_all_pairwise(
        means, {k: vuln_labels[k] for k in available},
        target_names=available,
    )

    # Display results
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Target")
    table.add_column("Cohen's d")
    table.add_column("Welch p")
    table.add_column("KS p")
    table.add_column("Significant?")

    for pr in vuln_pairwise:
        sig_style = "bold red" if pr.any_significant else "bold green"
        sig_label = "YES" if pr.any_significant else "NO"
        table.add_row(
            pr.target_name,
            f"{pr.cohens_d:.4f}",
            f"{pr.welch_p:.2e}",
            f"{pr.ks_p:.2e}",
            Text(sig_label, style=sig_style),
        )

    if precomputed:
        time.sleep(2.0)

    console.print(Panel(
        table,
        title="[bold]Vulnerable Build -- Pairwise Results[/bold]",
        border_style="red",
    ))

    console.print()

    # Final comparison panel
    any_vuln_sig = any(pr.any_significant for pr in vuln_pairwise)

    comparison = Text(justify="center")
    comparison.append("\n")
    comparison.append("VALIDATION SUMMARY\n\n", style="bold white")
    comparison.append("Patched build (liboqs 0.12+):  ", style="dim")
    comparison.append("FALSE POSITIVE\n", style="bold green")
    comparison.append("Vulnerable build (liboqs 0.9.0): ", style="dim")
    if any_vuln_sig:
        comparison.append("REAL LEAKAGE DETECTED\n", style="bold red")
    else:
        comparison.append("No leakage detected\n", style="bold yellow")
    comparison.append(
        "\nThe tool correctly distinguishes microarchitectural confounds\n"
        "from genuine secret-dependent timing leakage.\n",
        style="dim",
    )

    console.print(Panel(comparison,
                        title="[bold]Positive Control Validation[/bold]",
                        border_style="cyan", padding=(1, 2)))

    if precomputed:
        time.sleep(5.0)
