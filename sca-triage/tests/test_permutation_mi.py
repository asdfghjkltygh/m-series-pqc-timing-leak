"""Unit tests for the permutation MI module."""
from __future__ import annotations

import numpy as np
import pytest

from sca_triage.permutation_mi import run_permutation_mi, run_all_mi, MIResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(99)


# ---------------------------------------------------------------------------
# Tests: run_permutation_mi
# ---------------------------------------------------------------------------

class TestRunPermutationMI:
    def test_independent_features_not_significant(
        self, rng: np.random.Generator
    ) -> None:
        """Independent features and labels should produce p > 0.05."""
        n = 200
        features = rng.normal(0, 1, size=(n, 3))
        labels = rng.integers(0, 2, size=n)
        result = run_permutation_mi(
            features, labels, "independent",
            n_shuffles=10, random_seed=42,
        )
        assert result.p_value > 0.05
        assert result.significant is False

    def test_correlated_features_significant(
        self, rng: np.random.Generator
    ) -> None:
        """Perfectly correlated features and labels should produce p < 0.05."""
        n = 200
        labels = rng.integers(0, 2, size=n)
        # Feature is a noisy copy of the label -> strong MI
        features = labels.reshape(-1, 1).astype(float) + rng.normal(0, 0.1, (n, 1))
        result = run_permutation_mi(
            features, labels, "correlated",
            n_shuffles=10, random_seed=42,
        )
        assert result.observed_mi > 0
        assert result.p_value < 0.05
        assert result.significant is True

    def test_mi_near_zero_for_independent(
        self, rng: np.random.Generator
    ) -> None:
        """Observed MI should be close to the null mean for independent data."""
        n = 300
        features = rng.normal(0, 1, size=(n, 2))
        labels = rng.integers(0, 2, size=n)
        result = run_permutation_mi(
            features, labels, "independent",
            n_shuffles=10, random_seed=42,
        )
        # Observed MI should be within ~2 std devs of null mean
        if result.null_std > 0:
            z = abs(result.observed_mi - result.null_mean) / result.null_std
            assert z < 3.0

    def test_small_n_shuffles(self, rng: np.random.Generator) -> None:
        """Should work correctly with very few shuffles."""
        n = 50
        features = rng.normal(0, 1, size=(n, 1))
        labels = rng.integers(0, 2, size=n)
        result = run_permutation_mi(
            features, labels, "small_test",
            n_shuffles=10, random_seed=42,
        )
        assert result.n_shuffles == 10
        # p-value should be in valid range
        assert 0 < result.p_value <= 1.0

    def test_1d_features_reshaped(self, rng: np.random.Generator) -> None:
        """1-D feature array should be automatically reshaped to 2-D."""
        n = 100
        features = rng.normal(0, 1, size=n)  # 1-D
        labels = rng.integers(0, 2, size=n)
        result = run_permutation_mi(
            features, labels, "1d_test",
            n_shuffles=10, random_seed=42,
        )
        assert isinstance(result, MIResult)

    def test_target_name_preserved(self, rng: np.random.Generator) -> None:
        """Target name should be stored in the result."""
        features = rng.normal(0, 1, size=(50, 1))
        labels = rng.integers(0, 2, size=50)
        result = run_permutation_mi(
            features, labels, "my_target",
            n_shuffles=10, random_seed=42,
        )
        assert result.target_name == "my_target"


# ---------------------------------------------------------------------------
# Tests: run_all_mi
# ---------------------------------------------------------------------------

class TestRunAllMI:
    def test_multiple_targets(self, rng: np.random.Generator) -> None:
        """Should return one result per target."""
        n = 100
        features = rng.normal(0, 1, size=(n, 2))
        labels_dict = {
            "sk_lsb": rng.integers(0, 2, size=n),
            "msg_hw_parity": rng.integers(0, 2, size=n),
        }
        results = run_all_mi(
            features, labels_dict, n_shuffles=10, random_seed=42,
        )
        assert len(results) == 2
        names = {r.target_name for r in results}
        assert names == {"sk_lsb", "msg_hw_parity"}

    def test_target_filtering(self, rng: np.random.Generator) -> None:
        """Should only analyse specified targets."""
        n = 100
        features = rng.normal(0, 1, size=(n, 2))
        labels_dict = {
            "sk_lsb": rng.integers(0, 2, size=n),
            "msg_hw_parity": rng.integers(0, 2, size=n),
        }
        results = run_all_mi(
            features, labels_dict,
            target_names=["sk_lsb"],
            n_shuffles=10, random_seed=42,
        )
        assert len(results) == 1
        assert results[0].target_name == "sk_lsb"
