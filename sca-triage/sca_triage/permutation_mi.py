"""Stage 3: KSG Mutual Information with permutation null.

Estimates the mutual information between per-key aggregated timing features
and binary secret labels using scikit-learn's KSG estimator, then assesses
statistical significance via a label-permutation test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
from sklearn.feature_selection import mutual_info_classif


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class MIResult:
    """Result of the permutation MI test for one secret target.

    Attributes
    ----------
    target_name : str
        Name of the secret label column.
    observed_mi : float
        Sum of MI across features for the observed (true) labelling.
    null_mean : float
        Mean MI under the permutation null.
    null_std : float
        Standard deviation of MI under the permutation null.
    p_value : float
        Empirical permutation p-value:
        ``(n_perm_with_MI_ge_observed + 1) / (n_shuffles + 1)``.
    n_shuffles : int
        Number of permutation rounds executed.
    significant : bool
        ``True`` when ``p_value < 0.05``.
    """

    target_name: str
    observed_mi: float
    null_mean: float
    null_std: float
    p_value: float
    n_shuffles: int
    significant: bool


# ---------------------------------------------------------------------------
# Core MI computation
# ---------------------------------------------------------------------------

def _compute_total_mi(
    features: np.ndarray,
    labels: np.ndarray,
    k: int = 5,
    random_state: Optional[int] = None,
) -> float:
    """Return the summed MI across all feature columns.

    Parameters
    ----------
    features : np.ndarray
        2-D array (n_samples, n_features).
    labels : np.ndarray
        1-D discrete label array.
    k : int
        Number of neighbours for the KSG estimator.
    random_state : int, optional
        Seed for reproducibility.

    Returns
    -------
    float
        Total MI (sum over features).
    """
    mi_per_feature = mutual_info_classif(
        features, labels,
        n_neighbors=k,
        discrete_features=False,
        random_state=random_state,
    )
    return float(np.sum(mi_per_feature))


# ---------------------------------------------------------------------------
# Single-target permutation MI test
# ---------------------------------------------------------------------------

def run_permutation_mi(
    features: np.ndarray,
    labels: np.ndarray,
    target_name: str,
    n_shuffles: int = 100,
    k: int = 5,
    random_seed: Optional[int] = 42,
) -> MIResult:
    """Estimate MI and test significance by permutation.

    Parameters
    ----------
    features : np.ndarray
        2-D array (n_keys, n_features) of aggregated timing statistics.
    labels : np.ndarray
        1-D binary label array aligned with the rows of *features*.
    target_name : str
        Human-readable name for this target.
    n_shuffles : int, optional
        Number of label-permutation rounds (default 100).
    k : int, optional
        Number of neighbours for the KSG estimator (default 5).
    random_seed : int, optional
        Base seed for reproducibility (default 42).

    Returns
    -------
    MIResult
    """
    features = np.asarray(features, dtype=np.float64)
    if features.ndim == 1:
        features = features.reshape(-1, 1)
    labels = np.asarray(labels).ravel()

    rng = np.random.default_rng(random_seed)

    # Observed MI.
    observed_mi = _compute_total_mi(features, labels, k=k, random_state=random_seed)

    # Permutation null distribution.
    null_mis = np.empty(n_shuffles, dtype=np.float64)
    for i in range(n_shuffles):
        shuffled = rng.permutation(labels)
        null_mis[i] = _compute_total_mi(
            features, shuffled, k=k,
            random_state=(random_seed + i + 1) if random_seed is not None else None,
        )

    null_mean = float(np.mean(null_mis))
    null_std = float(np.std(null_mis, ddof=1)) if n_shuffles > 1 else 0.0

    # Empirical p-value (with continuity correction).
    n_ge = int(np.sum(null_mis >= observed_mi))
    p_value = (n_ge + 1) / (n_shuffles + 1)

    return MIResult(
        target_name=target_name,
        observed_mi=observed_mi,
        null_mean=null_mean,
        null_std=null_std,
        p_value=p_value,
        n_shuffles=n_shuffles,
        significant=bool(p_value < 0.05),
    )


# ---------------------------------------------------------------------------
# Multi-target convenience wrapper
# ---------------------------------------------------------------------------

def run_all_mi(
    features: np.ndarray,
    labels_dict: Dict[str, np.ndarray],
    target_names: Optional[Sequence[str]] = None,
    n_shuffles: int = 100,
    k: int = 5,
    random_seed: Optional[int] = 42,
) -> List[MIResult]:
    """Run permutation MI tests for every specified target.

    Parameters
    ----------
    features : np.ndarray
        2-D array (n_keys, n_features).
    labels_dict : dict[str, np.ndarray]
        Mapping from target name to label array.
    target_names : sequence of str, optional
        Subset of keys to analyse.  If ``None``, all keys are used.
    n_shuffles : int, optional
        Number of permutation rounds per target.
    k : int, optional
        KSG neighbour count.
    random_seed : int, optional
        Base seed.

    Returns
    -------
    list[MIResult]
    """
    if target_names is None:
        target_names = list(labels_dict.keys())

    results: List[MIResult] = []
    for name in target_names:
        result = run_permutation_mi(
            features=features,
            labels=labels_dict[name],
            target_name=name,
            n_shuffles=n_shuffles,
            k=k,
            random_seed=random_seed,
        )
        results.append(result)

    return results
