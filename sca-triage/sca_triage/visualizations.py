"""Publication-quality matplotlib visualisations for sca-triage results.

All public functions return a ``matplotlib.figure.Figure`` object so that
callers can display, save, or embed them as needed.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Sequence, Union

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless use

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from scipy import stats as sp_stats

from .tvla import TVLAResult


# ---------------------------------------------------------------------------
# Colour palette (consistent across all plots)
# ---------------------------------------------------------------------------

_RED = "#e74c3c"
_BLUE = "#3498db"
_ORANGE = "#e67e22"
_GREEN = "#2ecc71"
_GRAY = "#95a5a6"
_LIGHT_RED = "#fadbd8"


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _apply_style(dark: bool = False) -> None:
    """Set the matplotlib style for the current figure."""
    if dark:
        plt.style.use("dark_background")
    else:
        try:
            plt.style.use("seaborn-v0_8-darkgrid")
        except OSError:
            # Fallback for older matplotlib versions.
            plt.style.use("seaborn-darkgrid")


def _clip_outliers(arr: np.ndarray, percentile: float = 99.5) -> np.ndarray:
    """Clip values above the given percentile for visualisation."""
    threshold = np.percentile(arr, percentile)
    return arr[arr <= threshold]


# ---------------------------------------------------------------------------
# 1. Fixed-vs-Random distributions
# ---------------------------------------------------------------------------

def plot_fixed_vs_random(
    fixed: np.ndarray,
    random: np.ndarray,
    variance_ratio: Optional[float] = None,
    dark: bool = False,
) -> Figure:
    """Plot overlaid KDE curves for fixed and random timing groups.

    Parameters
    ----------
    fixed : np.ndarray
        1-D array of fixed-key timing measurements.
    random : np.ndarray
        1-D array of random-key timing measurements.
    variance_ratio : float, optional
        If provided, annotated on the plot.
    dark : bool
        Use dark background style.

    Returns
    -------
    Figure
    """
    _apply_style(dark)
    fig, ax = plt.subplots(figsize=(8, 5))

    fixed_c = _clip_outliers(np.asarray(fixed, dtype=np.float64))
    random_c = _clip_outliers(np.asarray(random, dtype=np.float64))

    # Histograms with KDE overlay
    ax.hist(fixed_c, bins=80, density=True, alpha=0.4, color=_RED, label="Fixed")
    ax.hist(random_c, bins=80, density=True, alpha=0.4, color=_BLUE, label="Random")

    # KDE curves
    if len(fixed_c) > 2:
        kde_f = sp_stats.gaussian_kde(fixed_c)
        xs = np.linspace(min(fixed_c.min(), random_c.min()),
                         max(fixed_c.max(), random_c.max()), 500)
        ax.plot(xs, kde_f(xs), color=_RED, linewidth=2)
    if len(random_c) > 2:
        kde_r = sp_stats.gaussian_kde(random_c)
        xs = np.linspace(min(fixed_c.min(), random_c.min()),
                         max(fixed_c.max(), random_c.max()), 500)
        ax.plot(xs, kde_r(xs), color=_BLUE, linewidth=2)

    if variance_ratio is not None:
        ax.annotate(
            f"Variance Ratio: {variance_ratio:.1f}\u00d7",
            xy=(0.97, 0.95), xycoords="axes fraction",
            ha="right", va="top",
            fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7),
        )

    ax.set_title("TVLA Input Distributions \u2014 Fixed vs Random", fontsize=14, fontweight="bold")
    ax.set_xlabel("Timing (cycles)", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)
    ax.legend(fontsize=11)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 2. Pairwise distributions
# ---------------------------------------------------------------------------

def plot_pairwise_distributions(
    group0: np.ndarray,
    group1: np.ndarray,
    target_name: str,
    cohens_d: Optional[float] = None,
    dark: bool = False,
) -> Figure:
    """Plot overlaid KDE curves for two secret-dependent groups.

    Parameters
    ----------
    group0 : np.ndarray
        1-D array of per-key mean timings for group 0.
    group1 : np.ndarray
        1-D array of per-key mean timings for group 1.
    target_name : str
        Name of the secret target for the title.
    cohens_d : float, optional
        If provided, annotated on the plot.
    dark : bool
        Use dark background style.

    Returns
    -------
    Figure
    """
    _apply_style(dark)
    fig, ax = plt.subplots(figsize=(8, 5))

    g0 = np.asarray(group0, dtype=np.float64)
    g1 = np.asarray(group1, dtype=np.float64)

    ax.hist(g0, bins=50, density=True, alpha=0.45, color=_BLUE, label="Group 0")
    ax.hist(g1, bins=50, density=True, alpha=0.45, color=_ORANGE, label="Group 1")

    all_vals = np.concatenate([g0, g1])
    xs = np.linspace(all_vals.min(), all_vals.max(), 500)

    if len(g0) > 2:
        ax.plot(xs, sp_stats.gaussian_kde(g0)(xs), color=_BLUE, linewidth=2)
    if len(g1) > 2:
        ax.plot(xs, sp_stats.gaussian_kde(g1)(xs), color=_ORANGE, linewidth=2)

    if cohens_d is not None:
        ax.annotate(
            f"Cohen's d: {cohens_d:.4f}",
            xy=(0.97, 0.95), xycoords="axes fraction",
            ha="right", va="top",
            fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7),
        )

    ax.set_title(
        f"Secret-Dependent Group Distributions \u2014 {target_name}",
        fontsize=14, fontweight="bold",
    )
    ax.set_xlabel("Timing (cycles)", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)
    ax.legend(fontsize=11)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 3. Progressive TVLA
# ---------------------------------------------------------------------------

def plot_progressive_tvla(
    progressive_results: List[TVLAResult],
    dark: bool = False,
) -> Figure:
    """Line plot of |t| vs trace count with threshold line.

    Parameters
    ----------
    progressive_results : list[TVLAResult]
        Results from :func:`run_progressive_tvla`, one per step.
    dark : bool
        Use dark background style.

    Returns
    -------
    Figure
    """
    _apply_style(dark)
    fig, ax = plt.subplots(figsize=(8, 5))

    trace_counts = [r.n_fixed + r.n_random for r in progressive_results]
    abs_t = [abs(r.t_statistic) for r in progressive_results]
    threshold = progressive_results[0].threshold if progressive_results else 4.5

    ax.plot(trace_counts, abs_t, marker="o", color=_BLUE, linewidth=2, markersize=5)
    ax.axhline(y=threshold, color=_RED, linestyle="--", linewidth=1.5, label=f"|t| = {threshold}")

    # Fill above threshold
    abs_t_arr = np.array(abs_t)
    trace_arr = np.array(trace_counts)
    ax.fill_between(
        trace_arr, threshold, abs_t_arr,
        where=(abs_t_arr >= threshold),
        color=_RED, alpha=0.12,
    )

    ax.set_title("Progressive TVLA \u2014 |t| vs Trace Count", fontsize=14, fontweight="bold")
    ax.set_xlabel("Number of Traces", fontsize=12)
    ax.set_ylabel("|t|", fontsize=12)
    ax.legend(fontsize=11)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 4. Permutation MI
# ---------------------------------------------------------------------------

def plot_permutation_mi(
    observed_mi: float,
    null_distribution: np.ndarray,
    target_name: str,
    p_value: Optional[float] = None,
    dark: bool = False,
) -> Figure:
    """Histogram of null MI distribution with observed MI line.

    Parameters
    ----------
    observed_mi : float
        The MI estimated on the true labels.
    null_distribution : np.ndarray
        1-D array of MI values from label-permutation rounds.
    target_name : str
        Name of the secret target.
    p_value : float, optional
        If provided, annotated on the plot.
    dark : bool
        Use dark background style.

    Returns
    -------
    Figure
    """
    _apply_style(dark)
    fig, ax = plt.subplots(figsize=(8, 5))

    null = np.asarray(null_distribution, dtype=np.float64)

    ax.hist(null, bins=40, density=True, alpha=0.6, color=_GRAY, label="Null distribution")
    ax.axvline(x=observed_mi, color=_RED, linestyle="--", linewidth=2, label="Observed MI")

    annotation = f"Observed MI: {observed_mi:.6f}"
    if p_value is not None:
        annotation += f"\np-value: {p_value:.4f}"
    ax.annotate(
        annotation,
        xy=(0.97, 0.95), xycoords="axes fraction",
        ha="right", va="top",
        fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7),
    )

    ax.set_title(
        f"Permutation MI Test \u2014 {target_name}",
        fontsize=14, fontweight="bold",
    )
    ax.set_xlabel("Mutual Information", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)
    ax.legend(fontsize=11)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# 5. Experiment heatmap
# ---------------------------------------------------------------------------

def plot_experiment_heatmap(
    results_matrix: np.ndarray,
    model_names: List[str],
    target_names: List[str],
    dark: bool = False,
) -> Figure:
    """Heatmap of accuracy values across models and targets.

    Parameters
    ----------
    results_matrix : np.ndarray
        2-D array of shape ``(n_models, n_targets)`` with accuracy values
        (0.0 -- 1.0).
    model_names : list[str]
        Row labels.
    target_names : list[str]
        Column labels.
    dark : bool
        Use dark background style.

    Returns
    -------
    Figure
    """
    _apply_style(dark)

    n_models = len(model_names)
    n_targets = len(target_names)
    fig, ax = plt.subplots(figsize=(max(6, n_targets * 1.8), max(4, n_models * 0.8)))

    # Custom colourmap: red (at/below chance) -> green (above chance)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "rg", [_RED, "#f5f5f5", _GREEN], N=256,
    )

    im = ax.imshow(results_matrix, cmap=cmap, vmin=0.4, vmax=0.7, aspect="auto")

    # Annotate cells
    for i in range(n_models):
        for j in range(n_targets):
            val = results_matrix[i, j]
            text_color = "white" if abs(val - 0.55) > 0.1 else "black"
            ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                    fontsize=10, fontweight="bold", color=text_color)

    ax.set_xticks(range(n_targets))
    ax.set_xticklabels(target_names, fontsize=10)
    ax.set_yticks(range(n_models))
    ax.set_yticklabels(model_names, fontsize=10)

    ax.set_title("Experiment Results \u2014 Model \u00d7 Target", fontsize=14, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Accuracy", shrink=0.8)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Save utility
# ---------------------------------------------------------------------------

def save_all_plots(
    figures_dict: Dict[str, Figure],
    output_dir: str,
    format: str = "png",
    dpi: int = 300,
) -> None:
    """Save all figures to the specified directory.

    Parameters
    ----------
    figures_dict : dict[str, Figure]
        Mapping of plot name to matplotlib Figure.
    output_dir : str
        Directory path (created if it does not exist).
    format : str
        Image format (default ``"png"``).
    dpi : int
        Resolution (default 300).
    """
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for name, fig in figures_dict.items():
        filepath = out / f"{name}.{format}"
        fig.savefig(str(filepath), format=format, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
