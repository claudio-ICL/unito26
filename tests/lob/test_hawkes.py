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
from scipy.integrate import quad_vec
from scipy.linalg import expm

from unito26.lob import config
from unito26.lob.hawkes import (
    Clock,
    ExponentialHawkes,
    HawkesParams,
    OgataThinningHawkes,
    compensators_at_events,
    decayed_counts_at,
    mean_response,
    mean_response_integral,
)
from unito26.lob.simulate import EventType


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
        # alpha / beta = 1.2 > 1: the mean intensity grows exponentially.
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


def path_statistics(simulator_cls, params, horizon, paths, seed):
    """Per-path counts by type, type switches and second gap, over independent paths.

    One number per path, so that a two-sample test sees independent draws: the gaps along
    one path are serially dependent, and a test that treats them as a sample overstates
    its own evidence.  The second gap and not the first, because from an empty state the
    first wait is the immigration clock alone in both schemes.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(paths):
        times, types = event_arrays(simulator_cls(params, rng=rng), horizon)
        assert times.size >= 2
        counts = np.bincount(types, minlength=params.dimension)
        switches = int(np.count_nonzero(np.diff(types)))
        rows.append([*counts, switches, times[1] - times[0]])
    return np.array(rows, dtype=float)


class TestAgreementAndClustering:
    def test_exact_agrees_with_thinning(self):
        """Two independent algorithms for the same law, compared over independent paths.

        The two share the type draw, so this compares their waiting times; the residual
        test below, whose compensator shares nothing with either, is the one that carries
        the law of the waits and of the types.  Six tests, so each is held to a sixth of
        the level.
        """
        params = four_type_params()
        horizon = 20 * params.relaxation_time()
        exact = path_statistics(ExponentialHawkes, params, horizon, paths=1500, seed=1)
        thinned = path_statistics(OgataThinningHawkes, params, horizon, paths=1500, seed=2)
        level = 0.01 / exact.shape[1]
        for column in range(exact.shape[1] - 1):
            assert stats.ttest_ind(exact[:, column], thinned[:, column]).pvalue > level
        assert stats.ks_2samp(exact[:, -1], thinned[:, -1]).pvalue > level

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


def asymmetric() -> HawkesParams:
    return config.asymmetric_pair_params()


class TestTheSecondOrder:
    """``V`` from the Lyapunov equation, against two other routes to it."""

    def test_it_solves_the_lyapunov_equation_and_is_positive_definite(self):
        params = four_type_params()
        covariance = params.stationary_covariance()
        hurwitz = params.hurwitz_matrix
        residual = (
            hurwitz @ covariance
            + covariance @ hurwitz.T
            + np.diag(params.stationary_intensity())
        )
        assert np.abs(residual).max() < 1e-12
        assert np.allclose(covariance, covariance.T)
        assert np.linalg.eigvalsh(covariance).min() > 0

    def test_it_is_the_integral_of_the_propagated_arrivals(self):
        params = asymmetric()
        hurwitz = params.hurwitz_matrix
        arrivals = np.diag(params.stationary_intensity())
        integral, _ = quad_vec(
            lambda s: expm(hurwitz * s) @ arrivals @ expm(hurwitz.T * s), 0.0, np.inf
        )
        assert params.stationary_covariance() == pytest.approx(integral, rel=1e-8)

    @pytest.mark.parametrize(
        "params",
        [
            config.self_exciting_pair_params(),
            config.cross_exciting_pair_params(),
            HawkesParams(
                baseline=np.array([1.0, 2.0]),
                excitation=np.array([[0.6, 0.2], [0.4, 0.8]]),
                decay=2.0,
            ),
        ],
    )
    def test_the_scalar_formula_holds_under_constant_column_sums(self, params):
        ones = np.ones(params.dimension)
        total = params.stationary_intensity().sum()
        scalar = total / (2 * params.decay * (1 - params.branching_ratio))
        assert ones @ params.stationary_covariance() @ ones == pytest.approx(scalar)

    def test_the_scalar_formula_errs_without_them(self):
        params = asymmetric()
        ones = np.ones(2)
        scalar = params.stationary_intensity().sum() / (
            2 * params.decay * (1 - params.branching_ratio)
        )
        assert ones @ params.stationary_covariance() @ ones == pytest.approx(1.2405303)
        assert scalar == pytest.approx(0.9375)

    def test_one_long_path_meets_it(self):
        """Sampled on a clock after a burn-in, the variance of ``1' Z`` lands on the
        Lyapunov value, 32% above what the scalar formula says."""
        params = asymmetric()
        times, types = event_arrays(ExponentialHawkes(params, rng=3), horizon=20_000.0)
        clock = Clock(np.arange(50.0, 20_000.0, 0.5))
        states = decayed_counts_at(params.decay, times, types, np.zeros(2), clock)
        ones = np.ones(2)
        assert (states @ ones).var() == pytest.approx(
            ones @ params.stationary_covariance() @ ones, rel=0.1
        )


class TestTheMeanResponse:
    def test_phi_is_the_closed_form_where_k_is_invertible(self):
        params = four_type_params()
        for horizon in (0.1, 1.0, 5.0):
            closed = np.linalg.solve(
                params.hurwitz_matrix, params.mean_response(horizon) - np.eye(4)
            )
            assert params.mean_response_integral(horizon) == pytest.approx(closed, abs=1e-12)

    def test_phi_is_the_integral_of_the_response(self):
        params = asymmetric()
        integral, _ = quad_vec(lambda s: expm(params.hurwitz_matrix * s), 0.0, 1.3)
        assert params.mean_response_integral(1.3) == pytest.approx(integral, rel=1e-10)

    def test_phi_starts_as_h_times_the_identity_and_ends_at_minus_k_inverse(self):
        params = asymmetric()
        assert params.mean_response_integral(1e-6) / 1e-6 == pytest.approx(
            np.eye(2), abs=1e-5
        )
        assert params.mean_response_integral(200.0) == pytest.approx(
            -np.linalg.inv(params.hurwitz_matrix)
        )

    def test_phi_needs_no_inverse_at_the_critical_point(self):
        """At a branching ratio of 1, ``K`` is singular and the closed form is undefined;
        the integral itself is not."""
        excitation = 4.0 * np.array([[0.5, 0.5], [0.5, 0.5]])
        hurwitz = excitation - 4.0 * np.eye(2)
        assert abs(np.linalg.det(hurwitz)) < 1e-12
        integral, _ = quad_vec(lambda s: expm(hurwitz * s), 0.0, 2.0)
        assert mean_response_integral(excitation, 4.0, 2.0) == pytest.approx(integral)
        assert mean_response(excitation, 4.0, 2.0) == pytest.approx(expm(hurwitz * 2.0))

    def test_the_forward_mean_runs_from_the_state_to_the_stationary_mean(self):
        params = asymmetric()
        state = np.array([0.0, 3.0])
        stationary_mean = params.stationary_intensity() / params.decay
        assert params.forward_mean_state(state, 0.0) == pytest.approx(state)
        assert params.forward_mean_state(state, 60.0) == pytest.approx(stationary_mean)
        assert params.forward_mean_state(stationary_mean, 0.7) == pytest.approx(
            stationary_mean
        )

    def test_the_forward_counts_grow_at_the_forward_intensity(self):
        params = asymmetric()
        state = np.array([1.0, 0.5])
        horizon, step = 0.8, 1e-6
        slope = (
            params.forward_mean_counts(state, horizon + step)
            - params.forward_mean_counts(state, horizon - step)
        ) / (2 * step)
        intensity = params.baseline + params.excitation @ params.forward_mean_state(
            state, horizon
        )
        assert slope == pytest.approx(intensity, rel=1e-6)

    def test_monte_carlo_from_one_state_meets_both_forward_means(self):
        params = asymmetric()
        state = params.stationary_intensity() / params.decay + np.array([0.0, 1.0])
        horizon = 0.5
        rng = np.random.default_rng(8)
        paths = 4000
        states = np.empty((paths, 2))
        counts = np.empty((paths, 2))
        for k in range(paths):
            simulator = ExponentialHawkes.from_state(params, state, rng=rng)
            times, types = event_arrays(simulator, horizon)
            counts[k] = np.bincount(types, minlength=2)
            states[k] = decayed_counts_at(
                params.decay, times, types, state, Clock(np.array([horizon]))
            )[0]
        for sample, expected in (
            (states, params.forward_mean_state(state, horizon)),
            (counts, params.forward_mean_counts(state, horizon)),
        ):
            error = sample.std(axis=0, ddof=1) / np.sqrt(paths)
            assert np.all(np.abs(sample.mean(axis=0) - expected) < 4 * error)

    def test_the_response_rises_before_it_falls_where_a_column_sum_exceeds_one(self):
        """``1' R_j`` starts with slope ``beta ((1' Gamma)_j - 1)``: positive for the
        second type, whose column sum is 1.4, and negative for the first, at 0.4."""
        params = asymmetric()
        ones = np.ones(2)
        early, late = params.mean_response(0.137), params.mean_response(3.0)
        assert ones @ early[:, 1] > 1.09
        assert ones @ late[:, 1] < 1.0
        assert ones @ early[:, 0] < 1.0
        total_intensity = ones @ params.excitation @ early
        assert total_intensity[1] < ones @ params.excitation[:, 1]

    def test_the_relaxation_time_is_the_slowest_mode(self):
        for params in (asymmetric(), config.self_exciting_pair_params(), four_type_params()):
            slowest = -np.linalg.eigvals(params.hurwitz_matrix).real.max()
            assert params.relaxation_time() == pytest.approx(1 / slowest)


class TestTheSignedExcitation:
    """Statements of section 1.4 of the notes, on the two shipped six-type regimes."""

    PRESSURE = np.array([event.pressure for event in EventType], dtype=float)
    REGIMES = [config.example_order_flow_params(), config.trending_order_flow_params()]

    @pytest.mark.parametrize("params", REGIMES)
    def test_it_takes_one_value_on_each_pair(self, params):
        for theta in (
            params.signed_excitation(self.PRESSURE),
            params.signed_excitation_at_horizon(self.PRESSURE, 0.7),
        ):
            assert theta[0::2] == pytest.approx(theta[1::2])

    @pytest.mark.parametrize("params", REGIMES)
    def test_it_starts_as_h_times_theta(self, params):
        horizon = 1e-6
        assert params.signed_excitation_at_horizon(
            self.PRESSURE, horizon
        ) / horizon == pytest.approx(params.signed_excitation(self.PRESSURE), rel=1e-4)

    @pytest.mark.parametrize("params", REGIMES)
    def test_it_ends_at_the_whole_expected_progeny(self, params):
        branching = params.branching_matrix
        progeny = self.PRESSURE @ branching @ np.linalg.inv(np.eye(6) - branching)
        assert params.signed_excitation_at_horizon(
            self.PRESSURE, 100.0
        ) == pytest.approx(progeny / self.PRESSURE)

    @pytest.mark.parametrize("params", REGIMES)
    def test_the_perron_mode_is_absent_from_every_contrast(self, params):
        values, vectors = np.linalg.eig(params.branching_matrix)
        perron = np.real(vectors[:, np.argmax(values.real)])
        assert abs(self.PRESSURE @ params.excitation @ perron) < 1e-10

    def test_the_two_regimes_carry_opposite_signs_on_the_market_pair(self):
        example, trending = self.REGIMES
        market = EventType.MARKET_BUY
        for horizon in (0.05, 1.0, 5.0):
            assert example.signed_excitation_at_horizon(self.PRESSURE, horizon)[market] < 0
            assert trending.signed_excitation_at_horizon(self.PRESSURE, horizon)[market] > 0


class TestStartingFromAState:
    def test_the_state_is_copied(self):
        params = asymmetric()
        state = np.array([0.5, 0.25])
        simulator = ExponentialHawkes.from_state(params, state, rng=0)
        list(simulator.events(5.0))
        assert state == pytest.approx(np.array([0.5, 0.25]))

    def test_the_intensity_at_the_start_is_read_off_the_state(self):
        params = asymmetric()
        state = np.array([1.0, 2.0])
        for simulator_cls in (ExponentialHawkes, OgataThinningHawkes):
            simulator = simulator_cls.from_state(params, state, rng=0)
            assert simulator.intensities == pytest.approx(
                params.baseline + params.excitation @ state
            )

    def test_a_state_that_is_not_one_is_refused(self):
        with pytest.raises(ValueError, match="non-negative"):
            ExponentialHawkes.from_state(asymmetric(), np.array([1.0, -0.5]))
        with pytest.raises(ValueError, match="non-negative"):
            ExponentialHawkes.from_state(asymmetric(), np.array([1.0, 0.5, 0.0]))


class TestTheStateOnAClock:
    def test_it_is_the_sum_over_the_past(self):
        params = four_type_params()
        times, types = event_arrays(ExponentialHawkes(params, rng=4), horizon=30.0)
        initial = np.array([0.3, 0.0, 1.2, 0.5])
        clock = Clock(np.sort(np.random.default_rng(5).uniform(0.0, 30.0, 200)))
        direct = np.array(
            [
                initial * np.exp(-params.decay * now)
                + np.array(
                    [
                        np.exp(-params.decay * (now - times[(times < now) & (types == e)])).sum()
                        for e in range(4)
                    ]
                )
                for now in clock
            ]
        )
        read = decayed_counts_at(params.decay, times, types, initial, clock)
        assert read == pytest.approx(direct, abs=1e-12)

    def test_a_clock_time_at_an_event_reads_before_its_jump(self):
        times = np.array([1.0, 2.0])
        types = np.array([0, 1])
        read = decayed_counts_at(1.0, times, types, np.zeros(2), Clock(times))
        assert read[0] == pytest.approx([0.0, 0.0])
        assert read[1] == pytest.approx([np.exp(-1.0), 0.0])
