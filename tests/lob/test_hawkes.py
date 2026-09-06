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


class TestTheBranchingStructure:
    """The multivariate quantities that the scalar formulae get wrong."""

    def test_the_endogenous_fraction_is_not_the_branching_ratio(self):
        params = four_type_params()
        assert params.endogenous_fraction() != pytest.approx(params.branching_ratio, rel=1e-3)

    def test_the_two_coincide_under_constant_column_sums(self):
        """The hypothesis, made to hold: 1' is then the left Perron vector of Gamma."""
        excitation = np.array([[0.6, 0.2], [0.4, 0.8]])
        params = HawkesParams(baseline=np.array([1.0, 2.0]), excitation=excitation, decay=2.0)
        assert params.endogenous_fraction() == pytest.approx(params.branching_ratio)
        assert params.mean_cluster_size() == pytest.approx(1 / (1 - params.branching_ratio))

    def test_the_mean_cluster_size_accounts_for_every_event(self):
        """``mubar x mean_cluster_size == nu`` -- every event belongs to one cluster."""
        params = four_type_params()
        assert params.baseline.sum() * params.mean_cluster_size() == pytest.approx(
            params.stationary_intensity().sum()
        )


class TestTheStationaryConstructor:
    def test_it_rescales_a_shape_whose_own_radius_is_unusable(self):
        """The intermediate is supercritical, which ``__post_init__`` would refuse."""
        shape = 10.0 * np.ones((2, 2))
        decay = 2.0
        assert np.max(np.abs(np.linalg.eigvals(shape / decay))) > 1
        params = HawkesParams.from_stationary_intensity(
            np.array([2.0, 2.0]), shape, decay, 0.7
        )
        assert params.branching_ratio == pytest.approx(0.7)
        assert params.stationary_intensity() == pytest.approx(np.array([2.0, 2.0]))

    def test_it_refuses_an_unreachable_stationary_intensity(self):
        """A component that is heavily excited and small in share is the one that binds."""
        shape = np.array([[1.0, 4.0], [1.0, 1.0]])
        with pytest.raises(ValueError, match=r"negative on components \[0\]"):
            HawkesParams.from_stationary_intensity(np.array([0.1, 10.0]), shape, 2.0, 0.9)


class TestTheSignedContrasts:
    PRESSURE = np.array([1.0, -1.0, 1.0, -1.0])

    def test_it_is_not_a_spectral_radius(self):
        """``P Gamma P`` is similar to ``Gamma``, so nothing signed is in the spectrum."""
        params = four_type_params()
        signed = np.diag(self.PRESSURE) @ params.branching_matrix @ np.diag(self.PRESSURE)
        assert np.max(np.abs(np.linalg.eigvals(signed))) == pytest.approx(
            params.branching_ratio
        )
        assert params.signed_endogenous_fraction(self.PRESSURE) != pytest.approx(
            params.branching_ratio, rel=1e-3
        )

    def test_the_unsigned_fraction_bounds_it(self):
        params = four_type_params()
        assert params.signed_endogenous_fraction(self.PRESSURE) < params.endogenous_fraction()
        assert params.signed_endogenous_fraction(np.ones(4)) == pytest.approx(
            params.endogenous_fraction()
        )

    def test_they_coincide_when_no_offspring_crosses(self):
        """At ``cross = 0`` every offspring inherits its parent's sign, so the signed
        contrast has nothing to subtract."""
        from unito26.lob.hawkes import with_cross_pressure_scaled

        base = four_type_params()
        shape = with_cross_pressure_scaled(base.excitation, self.PRESSURE, 0.0)
        params = HawkesParams.from_stationary_intensity(
            base.stationary_intensity(), shape, base.decay, base.branching_ratio
        )
        assert params.signed_endogenous_fraction(self.PRESSURE) == pytest.approx(
            params.endogenous_fraction()
        )

    def test_the_cross_ladder_holds_the_total_branching(self):
        from unito26.lob.hawkes import with_cross_pressure_scaled

        base = four_type_params()
        previous = base.signed_endogenous_fraction(self.PRESSURE)
        for cross in (0.75, 0.5, 0.25):
            shape = with_cross_pressure_scaled(base.excitation, self.PRESSURE, cross)
            rung = HawkesParams.from_stationary_intensity(
                base.stationary_intensity(), shape, base.decay, base.branching_ratio
            )
            assert rung.branching_ratio == pytest.approx(base.branching_ratio)
            assert rung.signed_endogenous_fraction(self.PRESSURE) > previous
            previous = rung.signed_endogenous_fraction(self.PRESSURE)

    def test_descendants_are_weighted_by_the_stationary_intensity(self):
        """``signed_descendants`` counts the descendants of a random *event*, weighting by
        ``lambda*/nu``; ``mean_cluster_size`` counts those of an immigrant, weighting by
        ``mu/mubar``.  Two questions, and neither is the other's signed version."""
        params = four_type_params()
        descendants = np.linalg.solve(
            (np.eye(4) - params.branching_matrix).T, np.ones(4)
        )
        stationary = params.stationary_intensity()
        assert params.signed_descendants(np.ones(4)) == pytest.approx(
            descendants @ stationary / stationary.sum()
        )
        assert params.mean_cluster_size() == pytest.approx(
            descendants @ params.baseline / params.baseline.sum()
        )

    def test_the_two_weightings_part_company_where_the_shape_is_lopsided(self):
        """Equal here only by accident of a near-symmetric example."""
        params = HawkesParams(
            baseline=np.array([0.02, 4.0]),
            excitation=np.array([[3.0, 1.0], [3.0, 0.2]]),
            decay=4.0,
        )
        assert params.signed_descendants(np.ones(2)) == pytest.approx(22.02, rel=1e-3)
        assert params.mean_cluster_size() == pytest.approx(10.12, rel=1e-3)


class TestTheReplayedIntensity:
    def test_it_reproduces_the_state_the_simulator_ran_on(self):
        """Read pre-jump, as ``compensators_at_events`` reads it: the intensity that
        governs an event is the one standing when it arrives."""
        from unito26.lob.hawkes import intensities_at_events

        simulator = ExponentialHawkes(four_type_params(), rng=17)
        times, types, live = [], [], []
        for _ in range(400):
            live.append(simulator.intensities.copy())
            time, event_type = simulator.step()
            times.append(time)
            types.append(event_type)
        # ``intensities`` above is read *before* the step decays the state to the event
        # time, so replay it the same way: decay from the previous event, then read.
        replayed = intensities_at_events(four_type_params(), np.array(times), np.array(types))
        decayed = np.exp(-four_type_params().decay * np.diff([0.0] + times))
        expected = np.array(live)
        baseline = four_type_params().baseline
        assert replayed == pytest.approx(
            baseline + (expected - baseline) * decayed[:, None]
        )


class TestTheSeam:
    def test_the_crossing_event_is_not_swallowed(self):
        """``events`` must draw one event past the horizon to know it is past it.  That
        draw has already excited the state, so discarding it loses one event per call."""
        whole = ExponentialHawkes(four_type_params(), rng=5)
        in_one = list(whole.events(40.0))

        split = ExponentialHawkes(four_type_params(), rng=5)
        in_two = list(split.events(10.0)) + list(split.events(40.0))

        assert in_two == in_one
