"""Stage 2: Pairwise Secret-Group Decomposition.

For each binary secret-label target, compare the per-key mean timings of
group 0 vs. group 1 using a battery of two-sample tests, apply Bonferroni
correction, and report effect sizes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class PairwiseResult:
    """Results of the pairwise comparison for one secret target.

    Attributes
    ----------
    target_name : str
        Name of the secret label column (e.g. ``"sk_lsb"``).
    n_group0 : int
        Number of keys in group 0.
    n_group1 : int
        Number of keys in group 1.
    welch_t : float
        Welch's t-statistic.
    welch_p : float
        Two-sided p-value from Welch's t-test.
    levene_stat : float
        Levene's test statistic for variance equality.
    levene_p : float
        p-value from Levene's test.
    ks_stat : float
        Two-sample Kolmogorov-Smirnov test statistic.
    ks_p : float
        p-value from KS test.
    ad_stat : float
        Anderson-Darling 2-sample test statistic.
    ad_p : float
        p-value from Anderson-Darling test.
    mannwhitney_stat : float
        Mann-Whitney U statistic.
    mannwhitney_p : float
        Two-sided p-value from Mann-Whitney U test.
    cohens_d : float
        Cohen's d effect size.
    any_significant : bool
        ``True`` if *any* test's Bonferroni-corrected p-value < 0.05.
    """

    target_name: str
    n_group0: int
    n_group1: int
    welch_t: float
    welch_p: float
    levene_stat: float
    levene_p: float
    ks_stat: float
    ks_p: float
    ad_stat: float
    ad_p: float
    mannwhitney_stat: float
    mannwhitney_p: float
    cohens_d: float
    any_significant: bool


# Number of statistical tests per target (used for Bonferroni).
_N_TESTS_PER_TARGET: int = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Cohen's d (pooled standard deviation variant).

    Parameters
    ----------
    a, b : np.ndarray
        1-D arrays for the two groups.

    Returns
    -------
    float
        Effect size.  Positive when mean(a) > mean(b).
    """
    n_a, n_b = len(a), len(b)
    if n_a < 2 or n_b < 2:
        return 0.0
    var_a = np.var(a, ddof=1)
    var_b = np.var(b, ddof=1)
    pooled_std = np.sqrt(
        ((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2)
    )
    if pooled_std == 0:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled_std)


# ---------------------------------------------------------------------------
# Single-target pairwise analysis
# ---------------------------------------------------------------------------

def run_pairwise(
    features: np.ndarray,
    labels: np.ndarray,
    target_name: str,
    bonferroni_factor: int = 1,
) -> PairwiseResult:
    """Run the full pairwise test battery for one binary target.

    Parameters
    ----------
    features : np.ndarray
        1-D array of per-key mean timing values (or any single scalar
        feature per key).
    labels : np.ndarray
        1-D binary array (0 or 1) aligned with *features*.
    target_name : str
        Human-readable name for this target.
    bonferroni_factor : int, optional
        Total number of hypothesis tests across all targets (for
        Bonferroni correction).  Defaults to 1 (no correction).

    Returns
    -------
    PairwiseResult
    """
    features = np.asarray(features, dtype=np.float64).ravel()
    labels = np.asarray(labels).ravel()

    mask0 = labels == 0
    mask1 = labels == 1
    g0 = features[mask0]
    g1 = features[mask1]

    # --- Welch's t-test ---------------------------------------------------
    t_stat, t_p = stats.ttest_ind(g0, g1, equal_var=False)

    # --- Levene's test for variance equality ------------------------------
    lev_stat, lev_p = stats.levene(g0, g1)

    # --- KS 2-sample test ------------------------------------------------
    ks_stat, ks_p = stats.ks_2samp(g0, g1)

    # --- Anderson-Darling 2-sample ----------------------------------------
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="scipy")
            ad_result = stats.anderson_ksamp([g0, g1])
        ad_stat = float(ad_result.statistic)
        ad_p = float(ad_result.pvalue)
    except Exception:
        # anderson_ksamp can fail with very small or degenerate samples.
        ad_stat = float("nan")
        ad_p = 1.0

    # --- Mann-Whitney U ---------------------------------------------------
    mw_stat, mw_p = stats.mannwhitneyu(g0, g1, alternative="two-sided")

    # --- Cohen's d --------------------------------------------------------
    d = _cohens_d(g0, g1)

    # --- Bonferroni correction --------------------------------------------
    raw_pvals = [t_p, lev_p, ks_p, ad_p, mw_p]
    corrected = [min(p * bonferroni_factor, 1.0) for p in raw_pvals]
    any_sig = any(p < 0.05 for p in corrected)

    return PairwiseResult(
        target_name=target_name,
        n_group0=int(mask0.sum()),
        n_group1=int(mask1.sum()),
        welch_t=float(t_stat),
        welch_p=float(t_p),
        levene_stat=float(lev_stat),
        levene_p=float(lev_p),
        ks_stat=float(ks_stat),
        ks_p=float(ks_p),
        ad_stat=ad_stat,
        ad_p=ad_p,
        mannwhitney_stat=float(mw_stat),
        mannwhitney_p=float(mw_p),
        cohens_d=d,
        any_significant=any_sig,
    )


# ---------------------------------------------------------------------------
# Multi-target convenience wrapper
# ---------------------------------------------------------------------------

def run_all_pairwise(
    features: np.ndarray,
    labels_dict: Dict[str, np.ndarray],
    target_names: Optional[Sequence[str]] = None,
) -> List[PairwiseResult]:
    """Run pairwise analysis for every specified target, with Bonferroni.

    Parameters
    ----------
    features : np.ndarray
        1-D array of per-key mean timing values.
    labels_dict : dict[str, np.ndarray]
        Mapping from target name to binary label array.
    target_names : sequence of str, optional
        Subset of keys in *labels_dict* to analyse.  If ``None``, all
        keys are used.

    Returns
    -------
    list[PairwiseResult]
        One result per target.
    """
    if target_names is None:
        target_names = list(labels_dict.keys())

    n_targets = len(target_names)
    bonferroni_factor = n_targets * _N_TESTS_PER_TARGET

    results: List[PairwiseResult] = []
    for name in target_names:
        labels = labels_dict[name]
        result = run_pairwise(
            features, labels, name,
            bonferroni_factor=bonferroni_factor,
        )
        results.append(result)

    return results
