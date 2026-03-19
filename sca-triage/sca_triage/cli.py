"""Click-based CLI entry point for sca-triage.

Provides two commands:

- ``sca-triage analyze`` -- full three-stage triage pipeline.
- ``sca-triage demo``    -- dramatic three-act stage presentation.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Dict, List, Optional

import click
import numpy as np

from .io import DataBundle, load_csv, load_npz
from .tvla import run_tvla, run_progressive_tvla, TVLAResult
from .pairwise import run_all_pairwise, PairwiseResult
from .permutation_mi import run_all_mi, MIResult
from .report import print_terminal_report, generate_html_report
from .visualizations import (
    plot_fixed_vs_random,
    plot_pairwise_distributions,
    plot_progressive_tvla,
    plot_permutation_mi,
    save_all_plots,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_data(
    timing_data: str,
    secret_labels: Optional[str],
    targets: List[str],
) -> DataBundle:
    """Dispatch to the correct loader based on file extension."""
    path = pathlib.Path(timing_data)
    label_path = pathlib.Path(secret_labels) if secret_labels else None

    if path.suffix == ".npz":
        return load_npz(path, label_path=label_path, target_cols=targets)
    else:
        return load_csv(path, label_path=label_path, target_cols=targets)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="sca-triage")
def main() -> None:
    """sca-triage: TVLA False-Positive Triage Tool."""


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--timing-data", required=True, type=click.Path(exists=True),
    help="Path to CSV or NPZ with timing traces.",
)
@click.option(
    "--secret-labels", default=None, type=click.Path(exists=True),
    help="Path to CSV with per-key secret labels (if not embedded in timing data).",
)
@click.option(
    "--targets", default="sk_lsb",
    help="Comma-separated list of target column names.",
)
@click.option(
    "--repeats-per-key", default=50, type=int,
    help="Number of measurement repeats per key.",
)
@click.option(
    "--permutation-shuffles", default=100, type=int,
    help="Number of MI permutation shuffles.",
)
@click.option(
    "--output", default=None, type=click.Path(),
    help="Path to save HTML report.",
)
@click.option(
    "--quick", is_flag=True, default=False,
    help="Skip Stage 3 (MI) for speed.",
)
@click.option(
    "--plot-dir", default=None, type=click.Path(),
    help="Directory to save plots.",
)
def analyze(
    timing_data: str,
    secret_labels: Optional[str],
    targets: str,
    repeats_per_key: int,
    permutation_shuffles: int,
    output: Optional[str],
    quick: bool,
    plot_dir: Optional[str],
) -> None:
    """Run the full three-stage triage pipeline."""
    target_list = [t.strip() for t in targets.split(",") if t.strip()]

    click.echo("Loading data...")
    data = _load_data(timing_data, secret_labels, target_list)

    # ---- Stage 1: TVLA ----------------------------------------------------
    click.echo("\n[Stage 1] Running Fixed-vs-Random TVLA...")
    tvla_result = run_tvla(data.fixed_timings, data.random_timings)
    progressive_results = run_progressive_tvla(data.fixed_timings, data.random_timings)

    click.echo(
        f"  |t| = {abs(tvla_result.t_statistic):.2f}  "
        f"({'FAIL' if not tvla_result.passed else 'PASS'})  "
        f"variance ratio = {tvla_result.variance_ratio:.2f}"
    )

    # ---- Stage 2: Pairwise -----------------------------------------------
    pairwise_results: List[PairwiseResult] = []
    if data.per_key_labels:
        click.echo("\n[Stage 2] Running Pairwise Secret-Group Decomposition...")
        available_targets = [t for t in target_list if t in data.per_key_labels]
        if not available_targets:
            available_targets = list(data.per_key_labels.keys())
        pairwise_results = run_all_pairwise(
            data.per_key_features[:, 2],  # mean column
            {k: data.per_key_labels[k] for k in available_targets},
            target_names=available_targets,
        )
        for pr in pairwise_results:
            sig_str = "SIGNIFICANT" if pr.any_significant else "not significant"
            click.echo(
                f"  {pr.target_name}: Cohen's d = {pr.cohens_d:.4f}, {sig_str}"
            )
    else:
        click.echo("\n[Stage 2] Skipped (no secret labels available).")

    # ---- Stage 3: Mutual Information --------------------------------------
    mi_results: List[MIResult] = []
    if quick:
        click.echo("\n[Stage 3] Skipped (--quick flag).")
    elif data.per_key_labels:
        click.echo("\n[Stage 3] Running Permutation MI Test...")
        available_targets = [t for t in target_list if t in data.per_key_labels]
        if not available_targets:
            available_targets = list(data.per_key_labels.keys())
        mi_results = run_all_mi(
            data.per_key_features,
            {k: data.per_key_labels[k] for k in available_targets},
            target_names=available_targets,
            n_shuffles=permutation_shuffles,
        )
        for mi in mi_results:
            click.echo(
                f"  {mi.target_name}: MI = {mi.observed_mi:.6f}, "
                f"p = {mi.p_value:.4f} "
                f"({'SIGNIFICANT' if mi.significant else 'not significant'})"
            )
    else:
        click.echo("\n[Stage 3] Skipped (no secret labels available).")

    # ---- Report -----------------------------------------------------------
    click.echo("")
    print_terminal_report(tvla_result, pairwise_results, mi_results, quick=quick)

    # ---- Plots ------------------------------------------------------------
    figures: Dict[str, object] = {}
    figures["fixed_vs_random"] = plot_fixed_vs_random(
        data.fixed_timings, data.random_timings,
        variance_ratio=tvla_result.variance_ratio,
    )
    figures["progressive_tvla"] = plot_progressive_tvla(progressive_results)

    if data.per_key_labels and pairwise_results:
        for pr in pairwise_results:
            if pr.target_name in data.per_key_labels:
                labels = data.per_key_labels[pr.target_name]
                means = data.per_key_features[:, 2]
                g0 = means[labels == 0]
                g1 = means[labels == 1]
                figures[f"pairwise_{pr.target_name}"] = plot_pairwise_distributions(
                    g0, g1, pr.target_name,
                )

    if mi_results:
        for mi in mi_results:
            # We don't have the raw null distribution stored in MIResult,
            # so we generate a synthetic one from null_mean/null_std for
            # visualisation purposes.
            null_dist = np.random.default_rng(42).normal(
                mi.null_mean, max(mi.null_std, 1e-9), mi.n_shuffles,
            )
            figures[f"mi_{mi.target_name}"] = plot_permutation_mi(
                mi.observed_mi, null_dist, mi.target_name,
            )

    plot_paths: Optional[Dict[str, str]] = None
    if plot_dir:
        plot_dir_path = pathlib.Path(plot_dir)
        plot_dir_path.mkdir(parents=True, exist_ok=True)
        save_all_plots(figures, str(plot_dir_path))
        plot_paths = {
            name: str(plot_dir_path / f"{name}.png") for name in figures
        }
        click.echo(f"\nPlots saved to {plot_dir_path}/")

    # ---- HTML report ------------------------------------------------------
    if output:
        html = generate_html_report(
            tvla_result, pairwise_results, mi_results,
            plot_paths=plot_paths, quick=quick,
        )
        pathlib.Path(output).write_text(html, encoding="utf-8")
        click.echo(f"HTML report saved to {output}")


# ---------------------------------------------------------------------------
# demo command
# ---------------------------------------------------------------------------

@main.command()
@click.option(
    "--timing-data", required=True, type=click.Path(exists=True),
    help="Path to main (patched) timing data.",
)
@click.option(
    "--vuln-data", default=None, type=click.Path(exists=True),
    help="Path to vulnerable version timing data for Act 3.",
)
@click.option(
    "--secret-labels", default=None, type=click.Path(exists=True),
    help="Path to secret labels CSV.",
)
@click.option(
    "--targets", default="sk_lsb",
    help="Comma-separated list of target column names.",
)
@click.option(
    "--precomputed", is_flag=True, default=False,
    help="Use cached results with realistic display pacing.",
)
@click.option(
    "--dark", is_flag=True, default=False,
    help="Use dark theme for stage presentation.",
)
def demo(
    timing_data: str,
    vuln_data: Optional[str],
    secret_labels: Optional[str],
    targets: str,
    precomputed: bool,
    dark: bool,
) -> None:
    """Run the dramatic four-act demo presentation."""
    try:
        from .demo import run_demo  # type: ignore[import-not-found]
    except ImportError:
        click.echo("Demo module not yet available.", err=True)
        sys.exit(1)

    target_list = [t.strip() for t in targets.split(",") if t.strip()]

    # Load main (patched) data
    click.echo("Loading timing data...")
    data = _load_data(timing_data, secret_labels, target_list)

    # Load vulnerable data if provided
    vuln_bundle = None
    if vuln_data:
        click.echo("Loading vulnerable data...")
        vuln_bundle = _load_data(vuln_data, secret_labels, target_list)

    run_demo(
        fixed_timings=data.fixed_timings,
        random_timings=data.random_timings,
        per_key_features=data.per_key_features,
        per_key_labels=data.per_key_labels,
        target_names=target_list,
        vuln_features=vuln_bundle.per_key_features if vuln_bundle else None,
        vuln_labels=vuln_bundle.per_key_labels if vuln_bundle else None,
        precomputed=precomputed,
        dark=dark,
    )
