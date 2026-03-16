"""Stage 1: Standard TVLA (Fixed-vs-Random Welch's t-test per ISO 17825).

Implements the first stage of the sca-triage pipeline — a conventional TVLA
with progressive trace-count analysis, variance-ratio diagnostics, and
descriptive statistics for both groups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class GroupStats:
    """Descriptive statistics for one measurement group."""

    mean: float
    median: float
    std: float
    iqr: float
    min: float
    max: float
    skew: float
    kurtosis: float

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "GroupStats":
        """Compute all descriptive statistics from a 1-D array.

        Parameters
        ----------
        arr : np.ndarray
            1-D array of timing measurements.

        Returns
        -------
        GroupStats
        """
        q25, q75 = np.percentile(arr, [25, 75])
        return cls(
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            std=float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            iqr=float(q75 - q25),
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            skew=float(stats.skew(arr)) if len(arr) >= 3 else 0.0,
            kurtosis=float(stats.kurtosis(arr, fisher=True))
                     if len(arr) >= 4 else 0.0,
        )


@dataclass
class TVLAResult:
    """Result of a single TVLA evaluation.

    Attributes
    ----------
    t_statistic : float
        Welch's t-statistic.
    p_value : float
        Two-sided p-value from the Welch t-test.
    n_fixed : int
        Number of traces in the fixed group.
    n_random : int
        Number of traces in the random group.
    passed : bool
        ``True`` when ``|t| <= threshold`` (i.e. no leakage detected).
    threshold : float
        Absolute t-value threshold (default 4.5 per ISO 17825).
    variance_ratio : float
        ``var(fixed) / var(random)`` — a key confound diagnostic.
    fixed_stats : Optional[GroupStats]
        Descriptive statistics for the fixed group.
    random_stats : Optional[GroupStats]
        Descriptive statistics for the random group.
    """

    t_statistic: float
    p_value: float
    n_fixed: int
    n_random: int
    passed: bool
    threshold: float = 4.5
    variance_ratio: float = 0.0
    fixed_stats: Optional[GroupStats] = None
    random_stats: Optional[GroupStats] = None


# ---------------------------------------------------------------------------
# Core TVLA
# ---------------------------------------------------------------------------

def run_tvla(
    fixed: np.ndarray,
    random: np.ndarray,
    threshold: float = 4.5,
    compute_stats: bool = True,
) -> TVLAResult:
    """Run a standard Fixed-vs-Random TVLA (Welch's t-test).

    Parameters
    ----------
    fixed : np.ndarray
        1-D array of timing measurements collected under a fixed key.
    random : np.ndarray
        1-D array of timing measurements collected under random keys.
    threshold : float, optional
        Absolute t-value threshold for the pass/fail decision (default 4.5).
    compute_stats : bool, optional
        If ``True`` (default), compute full descriptive statistics for each
        group.

    Returns
    -------
    TVLAResult
    """
    fixed = np.asarray(fixed, dtype=np.float64).ravel()
    random = np.asarray(random, dtype=np.float64).ravel()

    t_stat, p_val = stats.ttest_ind(fixed, random, equal_var=False)

    var_fixed = float(np.var(fixed, ddof=1)) if len(fixed) > 1 else 0.0
    var_random = float(np.var(random, ddof=1)) if len(random) > 1 else 0.0
    variance_ratio = var_fixed / var_random if var_random != 0 else float("inf")

    fixed_stats: Optional[GroupStats] = None
    random_stats: Optional[GroupStats] = None
    if compute_stats:
        fixed_stats = GroupStats.from_array(fixed)
        random_stats = GroupStats.from_array(random)

    return TVLAResult(
        t_statistic=float(t_stat),
        p_value=float(p_val),
        n_fixed=len(fixed),
        n_random=len(random),
        passed=bool(abs(t_stat) <= threshold),
        threshold=threshold,
        variance_ratio=float(variance_ratio),
        fixed_stats=fixed_stats,
        random_stats=random_stats,
    )


# ---------------------------------------------------------------------------
# Progressive TVLA
# ---------------------------------------------------------------------------

def run_progressive_tvla(
    fixed: np.ndarray,
    random: np.ndarray,
    steps: int = 10,
    threshold: float = 4.5,
) -> List[TVLAResult]:
    """Compute TVLA at increasing fractions of the available traces.

    This lets the analyst observe how the t-statistic evolves as more data
    is included — a signature of genuine leakage is monotonic growth,
    whereas a confound often saturates or fluctuates.

    Parameters
    ----------
    fixed : np.ndarray
        Full 1-D array of fixed-key timing measurements.
    random : np.ndarray
        Full 1-D array of random-key timing measurements.
    steps : int, optional
        Number of evenly spaced evaluation points (default 10,
        corresponding to 10 %, 20 %, ..., 100 %).
    threshold : float, optional
        Pass/fail threshold forwarded to :func:`run_tvla`.

    Returns
    -------
    list[TVLAResult]
        One result per step, in ascending order of trace count.
    """
    fixed = np.asarray(fixed, dtype=np.float64).ravel()
    random = np.asarray(random, dtype=np.float64).ravel()

    results: List[TVLAResult] = []
    for i in range(1, steps + 1):
        frac = i / steps
        n_f = max(2, int(len(fixed) * frac))
        n_r = max(2, int(len(random) * frac))
        result = run_tvla(
            fixed[:n_f],
            random[:n_r],
            threshold=threshold,
            compute_stats=(i == steps),  # full stats only at 100 %
        )
        results.append(result)

    return results
