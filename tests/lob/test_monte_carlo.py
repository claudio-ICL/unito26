"""Tests for the Monte Carlo estimates of the forward means.

Seeded, and with thresholds loose against the scores observed: a clock of horizons is read
on the same paths, so its scores are correlated and the largest of them is not one draw
from a normal.
"""

import numpy as np
import pytest

from unito26.lob import config
from unito26.lob.hawkes import Clock, ExponentialHawkes, decayed_counts_at
from unito26.lob.monte_carlo import (
    Contracted,
    Fan,
    ForwardCounts,
    ForwardState,
    ForwardStatistic,
    SampleMean,
)

PRESSURE = np.array([1.0, -1.0])
STATE = np.array([1.7, 0.4])
CLOCK = Clock(np.array([0.1, 0.4, 1.0, 2.0]))
HORIZON = 2.0
SIZE = 2000


class TestTheSampleMean:
    def test_it_is_the_mean_and_the_spread_over_the_root_of_the_size(self):
        sample = np.random.default_rng(0).normal(size=(400, 3))
        estimate = SampleMean.from_sample(sample)
        assert estimate.mean == pytest.approx(sample.mean(axis=0))
        assert estimate.standard_error == pytest.approx(sample.std(axis=0, ddof=1) / 20.0)
        assert estimate.z_scores(estimate.mean - estimate.standard_error) == pytest.approx(
            np.ones(3)
        )


class TestTheFan:
    def test_it_is_reproducible_from_a_seed(self):
        params = config.one_way_pair_params()
        first = Fan.sample(params, STATE, HORIZON, 20, 5)
        second = Fan.sample(params, STATE, HORIZON, 20, 5)
        assert first.size == 20
        for (times, types), (other_times, other_types) in zip(first.paths, second.paths):
            assert np.array_equal(times, other_times)
            assert np.array_equal(types, other_types)
            assert np.all((times > 0.0) & (times <= HORIZON))

    def test_the_state_it_starts_from_is_not_overwritten(self):
        state = STATE.copy()
        fan = Fan.sample(config.one_way_pair_params(), state, HORIZON, 5, 1)
        assert np.array_equal(state, STATE)
        assert np.array_equal(fan.state, STATE)

    def test_a_clock_past_its_horizon_is_refused(self):
        fan = Fan.sample(config.one_way_pair_params(), STATE, HORIZON, 2, 1)
        with pytest.raises(ValueError, match="the fan over"):
            ForwardCounts().read(fan, Clock(np.array([1.0, 2.5])))


class TestTheReadings:
    """One scripted path, with a clock time on an event."""

    PARAMS = config.one_way_pair_params()
    FAN = Fan(
        params=PARAMS,
        state=np.array([1.0, 0.0]),
        horizon=1.0,
        paths=((np.array([0.25, 0.5]), np.array([1, 0])),),
    )
    AT = Clock(np.array([0.0, 0.25, 0.5, 1.0]))

    def test_the_counts_include_an_event_on_the_clock(self):
        counts = ForwardCounts().read(self.FAN, self.AT)
        assert counts.shape == (1, 4, 2)
        assert np.array_equal(counts[0], [[0, 0], [0, 1], [1, 1], [1, 1]])

    def test_the_state_is_read_before_the_jump_of_an_event_on_the_clock(self):
        decay = np.exp(-self.PARAMS.decay * 0.25)
        states = ForwardState().read(self.FAN, self.AT)
        assert states.shape == (1, 4, 2)
        assert states[0, 0] == pytest.approx([1.0, 0.0])
        assert states[0, 1] == pytest.approx([decay, 0.0])
        assert states[0, 2] == pytest.approx([decay**2, decay])
        assert states[0, 3] == pytest.approx([(decay**2 + 1.0) * decay**2, decay**3])

    def test_a_path_without_events_decays_and_counts_nothing(self):
        fan = Fan(
            params=self.PARAMS,
            state=np.array([1.0, 2.0]),
            horizon=1.0,
            paths=((np.array([]), np.array([], dtype=int)),),
        )
        at = Clock(np.array([0.5, 1.0]))
        assert np.array_equal(ForwardCounts().read(fan, at), np.zeros((1, 2, 2)))
        assert ForwardState().read(fan, at)[0] == pytest.approx(
            np.exp(-self.PARAMS.decay * at)[:, None] * fan.state
        )

    def test_a_reading_every_path_agrees_on_has_no_score(self):
        fan = Fan(
            params=self.PARAMS, state=self.FAN.state, horizon=1.0, paths=self.FAN.paths * 2
        )
        scores = ForwardCounts().z_scores(fan, Clock(np.array([0.0])))
        assert np.all(np.isnan(scores))

    def test_a_contraction_reads_the_contraction(self):
        signed = Contracted(ForwardCounts(), PRESSURE)
        assert np.array_equal(signed.read(self.FAN, self.AT), [[0, -1, 0, 0]])
        assert signed.expectation(self.FAN, self.AT) == pytest.approx(
            ForwardCounts().expectation(self.FAN, self.AT) @ PRESSURE
        )

    def test_a_statistic_is_a_reading_and_its_expectation(self):
        with pytest.raises(TypeError):
            ForwardStatistic()


class TestTheFormulaeAreMet:
    @pytest.mark.parametrize(
        "params, seed",
        [(config.one_way_pair_params(), 11), (config.cross_exciting_pair_params(), 12)],
    )
    def test_the_state_the_counts_and_the_signed_count(self, params, seed):
        fan = Fan.sample(params, STATE, HORIZON, SIZE, seed)
        for statistic in (ForwardState(), ForwardCounts(), Contracted(ForwardCounts(), PRESSURE)):
            assert np.abs(statistic.z_scores(fan, CLOCK)).max() < 5.0

    def test_a_transposed_kernel_is_not(self):
        """The one-way pair with its excitation transposed has the same branching ratio and
        a different forward mean."""
        params = config.one_way_pair_params()
        transposed = type(params)(
            baseline=params.baseline, excitation=params.excitation.T, decay=params.decay
        )
        fan = Fan.sample(params, STATE, HORIZON, SIZE, 11)
        wrong = ForwardCounts().sample_mean(fan, CLOCK).z_scores(
            transposed.forward_mean_counts(STATE, CLOCK)
        )
        assert np.abs(wrong).max() > 10.0

    def test_the_mean_response_is_the_difference_of_two_fans(self):
        params = config.one_way_pair_params()
        base = ForwardState().read(Fan.sample(params, STATE, HORIZON, SIZE, 21), CLOCK)
        for event_type, seed in ((0, 22), (1, 23)):
            unit = np.eye(2)[event_type]
            more = ForwardState().read(
                Fan.sample(params, STATE + unit, HORIZON, SIZE, seed), CLOCK
            )
            response = params.mean_response(CLOCK)[:, :, event_type]
            scores = SampleMean.from_sample(more - base).z_scores(response)
            assert np.abs(scores).max() < 5.0


class TestTimeHomogeneity:
    def test_after_a_stopping_time_the_path_meets_the_forward_means_from_its_state(self):
        """Paths started empty are stopped at the first event after a warm-up at which the
        total state exceeds a level, and continued for ``h``.  The state and the counts over
        ``(s, s+h]`` have the means the formulae give from ``Z(s+)``, wherever ``s`` fell."""
        params = config.one_way_pair_params()
        rng = np.random.default_rng(31)
        warm_up, level, horizon = 3.0, 2.0, 0.8
        gaps = []
        for _ in range(1500):
            simulator = ExponentialHawkes(params, rng)
            for time, _ in simulator.events(np.inf):
                if time > warm_up and simulator.decayed_counts.sum() > level:
                    break
            stopped, state = time, simulator.decayed_counts.copy()
            after = list(simulator.events(stopped + horizon))
            times = np.array([time - stopped for time, _ in after])
            types = np.array([kind for _, kind in after], dtype=int)
            later = decayed_counts_at(
                params.decay, times, types, state, Clock(np.array([horizon]))
            )[0]
            gaps.append(
                np.r_[
                    np.bincount(types, minlength=2) - params.forward_mean_counts(state, horizon),
                    later - params.forward_mean_state(state, horizon),
                ]
            )
        assert np.abs(SampleMean.from_sample(gaps).z_scores(np.zeros(4))).max() < 5.0
