"""Unit tests for the report module."""
from __future__ import annotations

import io

import pytest
from rich.console import Console

from sca_triage.tvla import TVLAResult, GroupStats
from sca_triage.pairwise import PairwiseResult
from sca_triage.permutation_mi import MIResult
from sca_triage.report import print_terminal_report, generate_html_report, _verdict


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tvla_fail() -> TVLAResult:
    """TVLA result that fails (|t| > 4.5)."""
    return TVLAResult(
        t_statistic=12.5,
        p_value=1e-30,
        n_fixed=5000,
        n_random=5000,
        passed=False,
        threshold=4.5,
        variance_ratio=9.8,
        fixed_stats=GroupStats(
            mean=710.0, median=708.0, std=500.0, iqr=200.0,
            min=600.0, max=10_000_000.0, skew=5.2, kurtosis=30.0,
        ),
        random_stats=GroupStats(
            mean=712.0, median=711.0, std=50.0, iqr=30.0,
            min=650.0, max=900.0, skew=0.3, kurtosis=0.1,
        ),
    )


@pytest.fixture
def tvla_pass() -> TVLAResult:
    """TVLA result that passes (|t| < 4.5)."""
    return TVLAResult(
        t_statistic=1.2,
        p_value=0.23,
        n_fixed=5000,
        n_random=5000,
        passed=True,
        threshold=4.5,
        variance_ratio=1.1,
    )


@pytest.fixture
def pairwise_not_sig() -> list[PairwiseResult]:
    """Pairwise results with no significance."""
    return [PairwiseResult(
        target_name="sk_lsb",
        n_group0=100, n_group1=100,
        welch_t=0.5, welch_p=0.62,
        levene_stat=0.3, levene_p=0.58,
        ks_stat=0.08, ks_p=0.72,
        ad_stat=-0.5, ad_p=0.75,
        mannwhitney_stat=4900.0, mannwhitney_p=0.65,
        cohens_d=0.07,
        any_significant=False,
    )]


@pytest.fixture
def pairwise_sig() -> list[PairwiseResult]:
    """Pairwise results with significance."""
    return [PairwiseResult(
        target_name="sk_lsb",
        n_group0=100, n_group1=100,
        welch_t=5.2, welch_p=1e-6,
        levene_stat=0.3, levene_p=0.58,
        ks_stat=0.35, ks_p=1e-5,
        ad_stat=8.0, ad_p=1e-4,
        mannwhitney_stat=3000.0, mannwhitney_p=1e-5,
        cohens_d=0.74,
        any_significant=True,
    )]


@pytest.fixture
def mi_not_sig() -> list[MIResult]:
    """MI results with no significance."""
    return [MIResult(
        target_name="sk_lsb",
        observed_mi=0.002,
        null_mean=0.003,
        null_std=0.002,
        p_value=0.65,
        n_shuffles=100,
        significant=False,
    )]


@pytest.fixture
def mi_sig() -> list[MIResult]:
    """MI results with significance."""
    return [MIResult(
        target_name="sk_lsb",
        observed_mi=0.15,
        null_mean=0.003,
        null_std=0.002,
        p_value=0.01,
        n_shuffles=100,
        significant=True,
    )]


# ---------------------------------------------------------------------------
# Tests: _verdict
# ---------------------------------------------------------------------------

class TestVerdict:
    def test_false_positive(
        self,
        tvla_fail: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
        mi_not_sig: list[MIResult],
    ) -> None:
        """TVLA fails but no secret dependence -> false positive."""
        label, detail, color = _verdict(tvla_fail, pairwise_not_sig, mi_not_sig)
        assert "FALSE POSITIVE" in label or "CONFOUND" in label
        assert color == "green"

    def test_real_leakage_pairwise(
        self,
        tvla_fail: TVLAResult,
        pairwise_sig: list[PairwiseResult],
        mi_not_sig: list[MIResult],
    ) -> None:
        """TVLA fails and pairwise is significant -> real leakage."""
        label, detail, color = _verdict(tvla_fail, pairwise_sig, mi_not_sig)
        assert "LEAKAGE" in label
        assert color == "red"

    def test_real_leakage_mi(
        self,
        tvla_fail: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
        mi_sig: list[MIResult],
    ) -> None:
        """TVLA fails and MI is significant -> real leakage."""
        label, detail, color = _verdict(tvla_fail, pairwise_not_sig, mi_sig)
        assert "LEAKAGE" in label
        assert color == "red"

    def test_no_leakage(
        self,
        tvla_pass: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
        mi_not_sig: list[MIResult],
    ) -> None:
        """TVLA passes and no secret dependence -> no leakage."""
        label, detail, color = _verdict(tvla_pass, pairwise_not_sig, mi_not_sig)
        assert "NO LEAKAGE" in label
        assert color == "green"


# ---------------------------------------------------------------------------
# Tests: print_terminal_report
# ---------------------------------------------------------------------------

class TestTerminalReport:
    def test_runs_without_error(
        self,
        tvla_fail: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
        mi_not_sig: list[MIResult],
    ) -> None:
        """Terminal report should run without raising any exception."""
        # Capture output by redirecting console to a string buffer
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=True)
        # The function creates its own Console, so we just verify no exception
        print_terminal_report(tvla_fail, pairwise_not_sig, mi_not_sig)

    def test_runs_with_quick_flag(
        self,
        tvla_fail: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
    ) -> None:
        """Terminal report with quick=True should not error."""
        print_terminal_report(tvla_fail, pairwise_not_sig, [], quick=True)

    def test_runs_with_empty_pairwise(
        self,
        tvla_fail: TVLAResult,
        mi_not_sig: list[MIResult],
    ) -> None:
        """Terminal report with no pairwise results should not error."""
        print_terminal_report(tvla_fail, [], mi_not_sig)


# ---------------------------------------------------------------------------
# Tests: generate_html_report
# ---------------------------------------------------------------------------

class TestHTMLReport:
    def test_returns_valid_html(
        self,
        tvla_fail: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
        mi_not_sig: list[MIResult],
    ) -> None:
        """HTML report should contain basic HTML structure."""
        html = generate_html_report(tvla_fail, pairwise_not_sig, mi_not_sig)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "sca-triage" in html.lower()

    def test_contains_verdict(
        self,
        tvla_fail: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
        mi_not_sig: list[MIResult],
    ) -> None:
        """HTML report should contain the verdict text."""
        html = generate_html_report(tvla_fail, pairwise_not_sig, mi_not_sig)
        assert "FALSE POSITIVE" in html or "CONFOUND" in html

    def test_contains_tvla_stats(
        self,
        tvla_fail: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
        mi_not_sig: list[MIResult],
    ) -> None:
        """HTML report should contain TVLA statistics."""
        html = generate_html_report(tvla_fail, pairwise_not_sig, mi_not_sig)
        assert "12.5" in html  # t-statistic
        assert "FAIL" in html

    def test_quick_mode_html(
        self,
        tvla_fail: TVLAResult,
        pairwise_not_sig: list[PairwiseResult],
    ) -> None:
        """HTML report with quick=True should note MI was skipped."""
        html = generate_html_report(
            tvla_fail, pairwise_not_sig, [], quick=True
        )
        assert "Skipped" in html

    def test_real_leakage_html(
        self,
        tvla_fail: TVLAResult,
        pairwise_sig: list[PairwiseResult],
        mi_sig: list[MIResult],
    ) -> None:
        """HTML report should show red verdict for real leakage."""
        html = generate_html_report(tvla_fail, pairwise_sig, mi_sig)
        assert "LEAKAGE" in html
        assert "#e74c3c" in html or "#c0392b" in html  # red color
