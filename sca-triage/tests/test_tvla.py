"""Unit tests for the TVLA module."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from sca_triage.tvla import run_tvla, run_progressive_tvla, GroupStats, TVLAResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(42)


@pytest.fixture
def identical_samples(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Two samples drawn from the same distribution."""
    base = rng.normal(loc=710, scale=50, size=5000)
    a = base[:2500]
    b = base[2500:]
    return a, b


@pytest.fixture
def different_samples(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Two samples with clearly different means."""
    a = rng.normal(loc=710, scale=50, size=5000)
    b = rng.normal(loc=750, scale=50, size=5000)
    return a, b


# ---------------------------------------------------------------------------
# Tests: run_tvla
# ---------------------------------------------------------------------------

class TestRunTVLA:
    def test_identical_distributions_pass(
        self, identical_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """Identical distributions should produce |t| < 4.5."""
        a, b = identical_samples
        result = run_tvla(a, b)
        assert result.passed is True
        assert abs(result.t_statistic) < 4.5

    def test_different_distributions_fail(
        self, different_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """Clearly different distributions should produce |t| > 4.5."""
        a, b = different_samples
        result = run_tvla(a, b)
        assert result.passed is False
        assert abs(result.t_statistic) > 4.5

    def test_variance_ratio_computation(self, rng: np.random.Generator) -> None:
        """Variance ratio should reflect actual variance difference."""
        a = rng.normal(loc=100, scale=10, size=1000)
        b = rng.normal(loc=100, scale=50, size=1000)
        result = run_tvla(a, b)
        # a has std=10, b has std=50 -> ratio ~ (10/50)^2 = 0.04
        assert result.variance_ratio < 0.1
        assert result.variance_ratio > 0.01

    def test_known_values(self) -> None:
        """Test with deterministic values to verify t-statistic."""
        # Two small groups with known means and variances
        a = np.array([10.0, 12.0, 14.0, 16.0, 18.0])
        b = np.array([20.0, 22.0, 24.0, 26.0, 28.0])
        result = run_tvla(a, b)

        # Verify against scipy directly
        expected_t, expected_p = stats.ttest_ind(a, b, equal_var=False)
        assert abs(result.t_statistic - expected_t) < 1e-10
        assert abs(result.p_value - expected_p) < 1e-10

    def test_descriptive_stats_computed(
        self, identical_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """Descriptive stats should be populated when compute_stats=True."""
        a, b = identical_samples
        result = run_tvla(a, b, compute_stats=True)
        assert result.fixed_stats is not None
        assert result.random_stats is not None
        assert result.fixed_stats.mean > 0
        assert result.random_stats.std > 0

    def test_no_stats_when_disabled(
        self, identical_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """Stats should be None when compute_stats=False."""
        a, b = identical_samples
        result = run_tvla(a, b, compute_stats=False)
        assert result.fixed_stats is None
        assert result.random_stats is None

    def test_custom_threshold(self, rng: np.random.Generator) -> None:
        """Custom threshold should be respected."""
        a = rng.normal(100, 10, 1000)
        b = rng.normal(101, 10, 1000)
        result = run_tvla(a, b, threshold=100.0)
        assert result.threshold == 100.0
        assert result.passed is True  # very lenient threshold

    def test_result_counts(self, rng: np.random.Generator) -> None:
        """n_fixed and n_random should match input sizes."""
        a = rng.normal(0, 1, 123)
        b = rng.normal(0, 1, 456)
        result = run_tvla(a, b)
        assert result.n_fixed == 123
        assert result.n_random == 456


# ---------------------------------------------------------------------------
# Tests: run_progressive_tvla
# ---------------------------------------------------------------------------

class TestProgressiveTVLA:
    def test_correct_number_of_steps(
        self, identical_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """Should return exactly the requested number of steps."""
        a, b = identical_samples
        results = run_progressive_tvla(a, b, steps=7)
        assert len(results) == 7

    def test_default_steps(
        self, identical_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """Default should produce 10 steps."""
        a, b = identical_samples
        results = run_progressive_tvla(a, b)
        assert len(results) == 10

    def test_increasing_trace_counts(
        self, identical_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """Each successive step should use more traces."""
        a, b = identical_samples
        results = run_progressive_tvla(a, b, steps=5)
        counts = [r.n_fixed + r.n_random for r in results]
        for i in range(1, len(counts)):
            assert counts[i] >= counts[i - 1]

    def test_last_step_uses_all_data(
        self, identical_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """The final step should use (close to) all traces."""
        a, b = identical_samples
        results = run_progressive_tvla(a, b, steps=10)
        last = results[-1]
        assert last.n_fixed == len(a)
        assert last.n_random == len(b)

    def test_only_last_step_has_full_stats(
        self, identical_samples: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """Only the final step should have descriptive stats."""
        a, b = identical_samples
        results = run_progressive_tvla(a, b, steps=5)
        # Intermediate steps have no stats
        for r in results[:-1]:
            assert r.fixed_stats is None
        # Last step does
        assert results[-1].fixed_stats is not None


# ---------------------------------------------------------------------------
# Tests: GroupStats
# ---------------------------------------------------------------------------

class TestGroupStats:
    def test_from_array(self) -> None:
        """Basic GroupStats computation."""
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        gs = GroupStats.from_array(arr)
        assert gs.mean == pytest.approx(3.0)
        assert gs.median == pytest.approx(3.0)
        assert gs.min == pytest.approx(1.0)
        assert gs.max == pytest.approx(5.0)
        assert gs.std > 0
        assert gs.iqr > 0
