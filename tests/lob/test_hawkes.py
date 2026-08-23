"""Tests for the Hawkes order-flow generator.

The simulator is not a fixture: it is code with a right answer, so it is tested like
code.  The tests are statistical, and every one of them is seeded -- a flaky test in
course material is worse than no test, because students cannot tell a real failure
from bad luck.  Thresholds are deliberately loose (p > 0.01) while the observed
values sit far above them, so the suite fails on a bug rather than on a draw.
"""

import numpy as np
import pytest
from scipy import stats

from unito26.lob.hawkes import (
    ExponentialHawkes,
    HawkesParams,
    OgataThinningHawkes,
    compensators_at_events,
)


def four_type_params() -> HawkesParams:
    """A 4-type flow with the documented asymmetry: market orders excite the limit
    order flow heavily (rows 2-3, columns 0-1), while limit orders barely excite the
    market order flow (rows 0-1, columns 2-3)."""
    baseline = np.array([0.5, 0.3, 1.0, 1.0])
    excitation = np.array(
        [
            [0.8, 0.1, 0.05, 0.05],
            [0.1, 0.8, 0.05, 0.05],
            [0.9, 0.2, 0.60, 0.10],
            [0.2, 0.9, 0.10, 0.60],
        ]
    )
    return HawkesParams(baseline=baseline, excitation=excitation, decay=2.5)


def event_arrays(simulator, horizon):
    events = list(simulator.events(horizon))
    times = np.array([t for t, _ in events])
    types = np.array([k for _, k in events], dtype=int)
    return times, types


class TestParameterValidation:
    def test_rejects_shape_mismatch(self):
        with pytest.raises(ValueError, match="excitation must be"):
            HawkesParams(baseline=[1.0, 1.0], excitation=np.zeros((3, 3)), decay=1.0)

    def test_rejects_non_positive_decay(self):
        with pytest.raises(ValueError, match="decay must be positive"):
            HawkesParams(baseline=[1.0], excitation=[[0.0]], decay=0.0)

    def test_rejects_negative_excitation(self):
        # Inhibition would break the monotone-decay bound the exact scheme relies on.
        with pytest.raises(ValueError, match="non-negative"):
            HawkesParams(baseline=[1.0], excitation=[[-0.5]], decay=1.0)

    def test_rejects_dead_process(self):
        with pytest.raises(ValueError, match="total baseline"):
            HawkesParams(baseline=[0.0, 0.0], excitation=np.zeros((2, 2)), decay=1.0)

    def test_rejects_unstable_process(self):
        # alpha / beta = 1.2 > 1: the process explodes.
        with pytest.raises(ValueError, match="branching ratio"):
            HawkesParams(baseline=[1.0], excitation=[[1.2]], decay=1.0)

    def test_branching_ratio_and_stationary_mean_in_one_dimension(self):
        # Scalar case has a closed form: Gamma = alpha/beta, E[lambda] = mu/(1-Gamma).
        params = HawkesParams(baseline=[0.5], excitation=[[1.0]], decay=2.0)
        assert params.branching_ratio == pytest.approx(0.5)
        assert params.stationary_intensity()[0] == pytest.approx(1.0)


class TestExactSimulation:
    def test_degenerate_case_is_homogeneous_poisson(self):
        # With no excitation the scheme must reduce to a Poisson process: the excited
        # part is empty and every draw comes from the baseline branch.
        params = HawkesParams(baseline=[1.0, 2.0], excitation=np.zeros((2, 2)), decay=1.0)
        times, _ = event_arrays(ExponentialHawkes(params, rng=0), horizon=2000.0)
        gaps = np.diff(np.r_[0.0, times])
        assert stats.kstest(gaps, stats.expon(scale=1 / 3.0).cdf).pvalue > 0.01

    def test_stationary_intensity_matches_theory(self):
        # (I - Gamma)^{-1} mu.  This is the sharp quantitative test: it catches almost
        # every transposition or indexing error in the excitation matrix.
        params = four_type_params()
        horizon = 8000.0
        _, types = event_arrays(ExponentialHawkes(params, rng=42), horizon)
        empirical = np.bincount(types, minlength=params.dimension) / horizon
        assert empirical == pytest.approx(params.stationary_intensity(), rel=0.05)

    def test_excitation_is_not_symmetric_under_transposition(self):
        # Guards the index convention itself: alpha[i, j] means "j excites i", so the
        # transposed matrix must produce a different stationary mix.
        params = four_type_params()
        transposed = HawkesParams(
            baseline=params.baseline, excitation=params.excitation.T, decay=params.decay
        )
        assert not np.allclose(
            params.stationary_intensity(), transposed.stationary_intensity()
        )

    def test_residuals_are_unit_exponential(self):
        # The random time change: transforming event times by their own compensator
        # must give a unit-rate Poisson process.  This is what certifies the reduction
        # of the multivariate case to the scalar exact scheme, which is derived rather
        # than quoted -- so this test is the argument, not a smoke check.
        params = four_type_params()
        times, types = event_arrays(ExponentialHawkes(params, rng=7), horizon=6000.0)
        compensators = compensators_at_events(params, times, types)

        for component in range(params.dimension):
            own = compensators[types == component, component]
            residuals = np.diff(np.r_[0.0, own])
            assert residuals.mean() == pytest.approx(1.0, rel=0.05)
            assert stats.kstest(residuals, stats.expon().cdf).pvalue > 0.01

    def test_reproducible_from_a_seed(self):
        params = four_type_params()
        first = event_arrays(ExponentialHawkes(params, rng=123), horizon=200.0)
        second = event_arrays(ExponentialHawkes(params, rng=123), horizon=200.0)
        assert np.array_equal(first[0], second[0])
        assert np.array_equal(first[1], second[1])


class TestAgreementAndClustering:
    def test_exact_agrees_with_thinning(self):
        # Two independent algorithms for the same law, on independent seeds.
        params = four_type_params()
        exact, _ = event_arrays(ExponentialHawkes(params, rng=1), horizon=3000.0)
        thinned, _ = event_arrays(OgataThinningHawkes(params, rng=2), horizon=3000.0)
        gaps_exact = np.diff(np.r_[0.0, exact])
        gaps_thinned = np.diff(np.r_[0.0, thinned])
        assert stats.ks_2samp(gaps_exact, gaps_thinned).pvalue > 0.01

    def test_flow_clusters_where_poisson_does_not(self):
        # The one-line demonstration of why any of this was worth doing: counts in
        # equal bins are over-dispersed (Fano factor well above 1), whereas the
        # Poisson control sits at 1.
        params = four_type_params()
        horizon = 6000.0
        clustered, _ = event_arrays(ExponentialHawkes(params, rng=11), horizon)
        poisson_params = HawkesParams(
            baseline=params.baseline,
            excitation=np.zeros_like(params.excitation),
            decay=params.decay,
        )
        control, _ = event_arrays(ExponentialHawkes(poisson_params, rng=11), horizon)

        def fano_factor(times):
            counts, _ = np.histogram(times, bins=1000, range=(0.0, horizon))
            return counts.var() / counts.mean()

        assert fano_factor(clustered) > 2.0
        assert fano_factor(control) == pytest.approx(1.0, abs=0.2)
