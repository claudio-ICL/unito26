"""Alignment, predictors and estimators for the imbalance regressions.

The alignment tests are the ones that matter.  An off-by-one at either edge does not
raise and does not look wrong: it turns the predictive regression into the
contemporaneous one, which fits far better, so the failure mode is a *good* result.

Fixtures are constructed rather than simulated wherever a branch has to be exercised.
At the example parametrization no side of the book ever empties, so the study's own data
never reaches the segment-masking code at all, and a test that sampled it would certify
nothing.
"""

import numpy as np
import pandas as pd
import pytest

from unito26.lob import estimation as est
from unito26.lob import imbalance_regression as ir
from unito26.lob.messages import (
    BUY, SELL, GridDepth, Horizon, ReportedDepth, SweepSize, Window,
    limit_order, market_order, withdrawal,
)
from unito26.lob.orderbook import AggregateBook
from unito26.lob.session import MarketSession
from unito26.lob.statistics import SessionStatistics

LEVELS = (GridDepth(1), GridDepth(2))
SPEC = SessionStatistics(LEVELS, (SweepSize(100),), (1, 10))
DEPTH = ReportedDepth(4)
PRICE_UNIT = 100
BIDS = {1000: 100, 999: 200, 998: 150}
ASKS = {1002: 120, 1003: 180}


def series(times, values, segments=None) -> ir.AlignedSeries:
    times = np.asarray(times, dtype=float)
    return ir.AlignedSeries(
        times=times,
        values=np.asarray(values, dtype=float),
        segments=np.zeros(times.size, dtype=int) if segments is None else np.asarray(segments),
    )


def session(messages, spec=SPEC):
    return MarketSession.from_occupied_levels(
        AggregateBook.from_levels(dict(BIDS), dict(ASKS)),
        messages, DEPTH, spec, PRICE_UNIT, True,
    )


class TestTheAlignedSeries:
    def test_the_three_arrays_travel_together(self):
        with pytest.raises(ValueError, match="must agree"):
            ir.AlignedSeries(np.zeros(3), np.zeros(2), np.zeros(3, dtype=int))


class TestBackwardChange:
    """The base is ``window_start - 1``.  At ``window_start`` the event opening the window
    sits inside ``OFI`` while its price effect sits outside the change, and the slope is
    biased toward zero by an amount growing as the window shrinks."""

    PRICES = series([1.0, 2.0, 3.0, 4.0], [10.0, 11.0, 13.0, 16.0])

    def test_it_bases_the_change_before_the_window_opened(self):
        changed = ir.backward_change(self.PRICES, Window(1.5))
        # At t = 4 the window is (2.5, 4]; it opens at row 2, so the base is row 1.
        assert changed[3] == 16.0 - 11.0

    def test_it_is_undefined_where_the_window_reaches_the_first_row(self):
        changed = ir.backward_change(self.PRICES, Window(2.5))
        assert np.isnan(changed[0])
        assert np.isnan(changed[2])
        assert not np.isnan(changed[3])


class TestForwardChange:
    """Ties at ``t + h`` belong to the outcome, which is measured *at* that instant; the
    base is the row itself and never a lookup on its own timestamp, several rows being
    able to share one."""

    TIED = series([0.0, 1.0, 1.0, 1.0, 2.0], [10.0, 11.0, 12.0, 13.0, 14.0])

    def test_the_right_edge_takes_the_last_row_at_the_horizon(self):
        changed = ir.forward_change(self.TIED, Horizon(1.0))
        assert changed[0] == 13.0 - 10.0

    def test_the_base_is_the_row_and_not_its_timestamp(self):
        """Rows 1, 2 and 3 share a clock reading and hold three different states."""
        changed = ir.forward_change(self.TIED, Horizon(1.0))
        assert changed[1] == 14.0 - 11.0
        assert changed[2] == 14.0 - 12.0
        assert changed[3] == 14.0 - 13.0

    def test_it_is_undefined_where_nothing_lies_strictly_ahead(self):
        assert np.isnan(ir.forward_change(self.TIED, Horizon(1.0))[4])

    def test_the_next_event_horizon_is_not_a_small_duration(self):
        stepped = ir.forward_change_to_next_event(self.TIED)
        assert stepped[:4].tolist() == [1.0, 1.0, 1.0, 1.0]
        assert np.isnan(stepped[4])


class TestSegmentMasking:
    """A difference spanning a row where a side emptied is undefined, not zero.  The
    study's own data has one segment, so this fixture is the only thing that exercises it."""

    BROKEN = series([0.0, 1.0, 2.0, 3.0], [10.0, 11.0, 12.0, 13.0], [0, 0, 1, 1])

    def test_a_forward_difference_does_not_cross_a_boundary(self):
        changed = ir.forward_change(self.BROKEN, Horizon(1.0))
        assert np.isnan(changed[1])
        assert changed[2] == 1.0

    def test_the_next_event_difference_does_not_cross_it_either(self):
        stepped = ir.forward_change_to_next_event(self.BROKEN)
        assert np.isnan(stepped[1])
        assert stepped[0] == 1.0

    def test_a_backward_difference_does_not_cross_it(self):
        assert np.isnan(ir.backward_change(self.BROKEN, Window(2.5))[3])

    def test_an_emptied_side_opens_a_segment(self):
        """Read off ``Spread``, NaN exactly where the mid does not exist."""
        messages = [market_order(1.0, 1000, BUY), limit_order(2.0, 50, 1002, SELL)]
        recorded = session(messages)
        assert int(ir.aligned_mid_price(recorded).segments.max()) >= 1


class TestBackwardSum:
    MESSAGES = [
        limit_order(1.0, 60, 1000, BUY),
        limit_order(2.0, 40, 1000, BUY),
        withdrawal(3.0, 25, 1000, BUY),
        market_order(3.5, 30, BUY),
    ]

    def test_it_reproduces_the_declared_column_at_a_whole_window(self):
        """Without this the package carries two definitions of ``OFI`` that can drift."""
        recorded = session(self.MESSAGES)
        flow = ir.aligned_order_flow(recorded)
        for window in (1, 10):
            assert np.array_equal(
                ir.backward_sum(flow, Window(float(window))),
                recorded.stats[f"OrderFlowImbalance{window}"].to_numpy(dtype=float),
                equal_nan=True,
            )

    def test_a_window_holding_an_undefined_contribution_is_undefined(self):
        """``e_0`` is undefined, so the opening ``w`` of a session is lost -- and that,
        not a run-off at the array's edge, is the only NaN clause here."""
        flow = ir.aligned_order_flow(session(self.MESSAGES))
        assert np.isnan(ir.backward_sum(flow, Window(3.0))[3])
        assert not np.isnan(ir.backward_sum(flow, Window(2.4))[3])


class TestThePredictors:
    MESSAGES = [
        limit_order(1.0, 60, 1000, BUY),
        limit_order(2.0, 40, 1000, BUY),
        withdrawal(3.0, 25, 1000, BUY),
        market_order(3.5, 30, BUY),
        limit_order(4.0, 20, 1001, BUY),
    ]

    def test_the_depth_divisor_reproduces_the_declared_average(self):
        """The declared column exists only for whole windows; the study needs floats, and
        two mean depths in one package would drift."""
        recorded = session(self.MESSAGES)
        computed = ir.predictors(recorded, Window(10.0), GridDepth(1)).mean_depth
        assert computed == pytest.approx(
            recorded.stats["AverageDepth10"].to_numpy(dtype=float), nan_ok=True
        )

    def test_the_row_set_is_common_to_every_predictor(self):
        got = ir.predictors(session(self.MESSAGES), Window(1.0), GridDepth(2))
        for values in (got.order_flow_imbalance, got.last_contribution,
                       got.queue_imbalance, got.normalised_imbalance):
            assert np.isfinite(values[got.defined]).all()


class TestTheLogScoreSkill:
    """Three properties the naive version gets wrong, and the shrinkage that fixes one."""

    def setup_method(self):
        rng = np.random.default_rng(3)
        self.n = 20000
        self.outcome = rng.choice(3, size=self.n, p=[0.05, 0.90, 0.05])
        self.noise = rng.normal(size=self.n)
        self.half = self.n // 2

    def test_a_constant_predictor_scores_exactly_zero(self):
        """What pins the convention that model and climatology are fitted on the same
        training fold and both scored out of fold."""
        constant = np.zeros(self.n)
        skill = est.log_score_skill(
            constant[: self.half], self.outcome[: self.half],
            constant[self.half :], self.outcome[self.half :], 10, 10.0,
        )
        assert skill == pytest.approx(0.0, abs=1e-12)

    def test_an_independent_predictor_scores_the_finite_sample_penalty(self):
        """Not zero: a ``k``-bin three-class model carries an expected out-of-sample
        excess of about ``k (J-1) / (2 n_train)`` nats, which is the size of the effects
        this study reports."""
        skill = est.log_score_skill(
            self.noise[: self.half], self.outcome[: self.half],
            self.noise[self.half :], self.outcome[self.half :], 10, 10.0,
        )
        frequencies = np.bincount(self.outcome[: self.half], minlength=3) / self.half
        entropy = -np.mean(np.log(frequencies[self.outcome[self.half :]]))
        predicted = -10 * 2 / (2 * self.half * entropy)
        assert skill < 0
        assert skill == pytest.approx(predicted, rel=0.5)

    def test_an_informative_predictor_scores_positive(self):
        rng = np.random.default_rng(4)
        latent = rng.normal(size=4000)
        rate = np.clip(0.05 + 0.10 * latent, 0.002, 0.49)
        outcome = np.array([rng.choice(3, p=[q, 1 - 2 * q, q]) for q in rate])
        skill = est.log_score_skill(
            latent[:2000], outcome[:2000], latent[2000:], outcome[2000:], 10, 10.0
        )
        assert skill > 0.05

    def test_the_shrinkage_keeps_an_empty_training_cell_finite(self):
        """Guaranteed at the extreme quantiles of a signed flow: one held-out row in a bin
        whose training frequency for its class is zero would otherwise score minus
        infinity."""
        predictor = np.arange(200.0)
        train = np.ones(200, dtype=int)
        train[:100] = 0
        test = np.full(200, 2)
        skill = est.log_score_skill(predictor, train, predictor, test, 10, 1.0)
        assert np.isfinite(skill)


class TestTheIncrementalSkill:
    """The confirmatory statistic: nested, so it needs no separate null."""

    def setup_method(self):
        rng = np.random.default_rng(11)
        self.n = 40000
        self.half = self.n // 2
        self.base = rng.normal(size=self.n)
        self.extra = rng.normal(size=self.n)
        self.noise = rng.normal(size=self.n)
        rate = np.clip(0.03 + 0.05 * self.base, 0.002, 0.45)
        self.outcome = np.array([rng.choice(3, p=[q, 1 - 2 * q, q]) for q in rate])
        joint = np.clip(0.03 + 0.04 * self.base + 0.04 * self.extra, 0.002, 0.45)
        self.joint_outcome = np.array([rng.choice(3, p=[q, 1 - 2 * q, q]) for q in joint])

    def skill(self, extra, outcome):
        h = self.half
        return est.incremental_log_score_skill(
            self.base[:h], extra[:h], outcome[:h],
            self.base[h:], extra[h:], outcome[h:], 6, 20.0,
        )

    def test_a_redundant_predictor_adds_nothing(self):
        """The shrinkage target is the base model itself, so a second copy of the base
        predictor lands back on it rather than on climatology."""
        assert self.skill(self.base, self.outcome) == pytest.approx(0.0, abs=1e-3)

    def test_an_irrelevant_predictor_pays_the_finite_sample_penalty(self):
        assert -0.02 < self.skill(self.noise, self.outcome) < 0.0

    def test_an_informative_predictor_scores_positive(self):
        assert self.skill(self.extra, self.joint_outcome) > 0.02


class TestTheNestedFit:
    def test_it_recovers_a_planted_pair_of_coefficients(self):
        rng = np.random.default_rng(5)
        last = rng.normal(size=8000)
        rest = rng.normal(size=8000)
        change = 0.3 * last + 0.7 * rest + 0.1 * rng.normal(size=8000)
        got = ir.nested_fit(last, last + rest, change, lag=0)
        assert got.last == pytest.approx(0.3, abs=0.01)
        assert got.window == pytest.approx(0.7, abs=0.01)

    def test_the_one_degree_of_freedom_test_misses_a_weighting_it_cannot_express(self):
        """``b2 = 0`` restricts the window to an equally weighted boxcar.  Where the true
        weighting is not one, the sum can carry nothing while the lags carry a great deal
        -- which is the whole reason the confirmatory test is the joint ``F``."""
        rng = np.random.default_rng(6)
        early, late = rng.normal(size=6000), rng.normal(size=6000)
        change = 0.5 * (late - early) + 0.2 * rng.normal(size=6000)
        boxcar = ir.nested_fit(np.zeros(6000), early + late, change, lag=0)
        assert abs(boxcar.window) < 3 * boxcar.window_error

        design = np.column_stack([np.ones(6000), early, late])
        statistic, degrees = ir.joint_f(design, change, slice(1, 3), 0)
        assert degrees == 2
        assert statistic > 100


class TestTuningTheWindow:
    def test_it_recovers_a_planted_optimum(self):
        rng = np.random.default_rng(7)
        n = 30000
        times = np.cumsum(rng.exponential(0.01, size=n))
        flow = rng.normal(size=n)
        truth = ir.backward_sum(ir.AlignedSeries(times, flow, np.zeros(n, int)), Window(0.5))
        prices = np.cumsum(np.nan_to_num(truth) * 0.001 + rng.normal(0, 0.01, size=n))
        mid = ir.AlignedSeries(times, prices, np.zeros(n, dtype=int))
        grid = np.array([0.05, 0.1, 0.25, 0.5, 1.0, 2.0])
        curve, best = ir.tune_window(
            lambda x, y: abs(np.corrcoef(x, y)[0, 1]), grid,
            ir.AlignedSeries(times, flow, np.zeros(n, dtype=int)), mid, Horizon(0.02)
        )
        assert curve.size == grid.size
        assert best == pytest.approx(0.5, abs=0.3)


class TestTheRecords:
    def test_the_result_table_round_trips(self):
        table = pd.DataFrame([{
            "Configuration": "base", "Predictor": "OFI", "Window": 0.0208, "Horizon": None,
            "Seed": 0, "EventsPerWindow": 0.63, "EventsPerTimescale": 0.5,
            "WindowOccupancy": 4.84, "Rows": 100, "EffectiveRows": 42.0,
            "SurvivingRows": 1.0, "Slope": 1e-5, "SlopeError": 2e-6, "RSquared": 0.001,
            "ParticipationRatio": 1900.0, "SignedCovariance": 0.0038,
            "SignedCovarianceLow": 0.003, "SignedCovarianceHigh": 0.004,
            "LogScoreSkill": 0.006, "BrierSkill": 0.004, "KendallTau": 0.029,
            "SignAccuracy": 0.57, "Coverage": 0.04, "BaseRate": 0.51,
        }])
        results = ir.RegressionResults(table)
        assert ir.RegressionResults.from_records(results.to_records()).table.equals(
            results.to_frame()
        )

    def test_the_nested_table_round_trips(self):
        table = pd.DataFrame([{
            "Configuration": "base", "Window": 0.0208, "Horizon": None, "Seed": 0,
            "Rows": 100, "LastCoefficient": 4.5e-5, "WindowCoefficient": 5.5e-5,
            "LastError": 3.8e-5, "WindowError": 2.1e-5, "Covariance": -1e-10,
            "BucketF": 3.49, "BucketDegreesOfFreedom": 4, "IncrementalSkill": 0.0015,
            "IncrementalSkillLow": 0.0005, "IncrementalSkillHigh": 0.0025,
        }])
        fits = ir.NestedFits(table)
        assert ir.NestedFits.from_records(fits.to_records()).table.equals(fits.to_frame())


class TestTheBlockBootstrap:
    def test_it_resamples_blocks_of_time_and_not_of_rows(self):
        """Rows arrive in clusters, so a fixed row count spans a wildly variable duration
        and it is the duration that has to exceed the dependence length."""
        rng = np.random.default_rng(8)
        times = np.sort(rng.uniform(0, 100, size=5000))
        rows = est.block_indices(times, 2.0, rng)
        assert rows.size == times.size
        runs = np.split(rows, np.flatnonzero(np.diff(rows) != 1) + 1)
        assert max(times[run[-1]] - times[run[0]] for run in runs) <= 2.0 + 1e-9

    def test_the_paired_resample_shares_one_index_set(self):
        rng = np.random.default_rng(9)
        times = np.sort(rng.uniform(0, 100, size=2000))
        scores = np.column_stack([np.ones(2000), np.ones(2000)])
        means = est.bootstrap_means(times, scores, 2.0, 20, rng)
        assert means == pytest.approx(1.0)


class TestTheInformationMeasures:
    """The estimators the atom forces on us, and the four ways they are misused."""

    def test_the_in_sample_identity_with_the_log_score(self):
        """Unshrunk and in sample, the binned skill is ``I`` over the climatological entropy.

        This is why the mutual information looks free, and the next test is why it is not.
        """
        rng = np.random.default_rng(0)
        rows = 40_000
        predictor = rng.normal(size=rows)
        outcome = np.digitize(0.05 * predictor + rng.normal(size=rows), [-0.3, 0.3])
        model = est.ThreeClassModel.fit(predictor, outcome, 6, 0.0)
        probabilities = model.predict(predictor)
        cross_entropy = -np.mean(np.log(probabilities[np.arange(rows), outcome]))
        entropy = -np.sum(model.climatology * np.log(model.climatology))
        information = est.mutual_information(predictor, outcome, 6)
        assert information.plug_in / entropy == pytest.approx(
            1.0 - cross_entropy / entropy, abs=1e-12
        )

    def test_the_correction_subtracts_the_theoretical_bias(self):
        """Miller-Madow for a mutual information removes ``(mx-1)(my-1)/2N``, downward.

        The entropy correction has the other sign; applied here it would double the bias.
        """
        rng = np.random.default_rng(1)
        rows, bins = 100_000, 6
        predictor = rng.normal(size=rows)
        outcome = np.digitize(rng.normal(size=rows), [-0.3, 0.3])
        information = est.mutual_information(predictor, outcome, bins)
        assert information.removed > 0
        assert information.removed == pytest.approx((bins - 1) * 2 / (2 * rows), rel=1e-9)
        assert abs(information.miller_madow) < information.plug_in

    def test_it_finds_a_dependence_that_is_there(self):
        rng = np.random.default_rng(2)
        rows = 40_000
        predictor = rng.normal(size=rows)
        outcome = np.digitize(predictor + 0.5 * rng.normal(size=rows), [-0.5, 0.5])
        assert est.mutual_information(predictor, outcome, 6).miller_madow > 0.1

    def test_the_outcome_must_never_be_quantile_binned(self):
        """With an atom, every interior quantile is zero and the bins collapse to two --
        and the surviving split puts flat with up, so the estimate measures the wrong thing.

        Pinned by a test rather than by a comment, because the failure is silent.
        """
        rng = np.random.default_rng(3)
        outcome = np.where(rng.random(100_000) < 0.93, 0.0, rng.choice([-0.5, 0.5], 100_000))
        for bins in (3, 6, 10, 20):
            assigned = est.quantile_bins(outcome, bins)
            assert assigned.max() + 1 == 2
        assigned = est.quantile_bins(outcome, 6)
        assert set(np.unique(assigned[outcome == 0.0])) == set(np.unique(assigned[outcome > 0.0]))

    def test_the_realised_bin_count_is_reported(self):
        rng = np.random.default_rng(4)
        tied = np.where(rng.random(10_000) < 0.8, 0.0, rng.normal(size=10_000))
        information = est.mutual_information(tied, np.zeros(10_000, dtype=int), 10)
        assert information.realised_bins < 10
        assert information.rows == 10_000


class TestTheCircularShiftNull:
    """Why the null is a rotation and not a permutation."""

    @staticmethod
    def _ar1(rows, phi, rng):
        noise = rng.normal(size=rows)
        out = np.empty(rows)
        out[0] = noise[0]
        for i in range(1, rows):
            out[i] = phi * out[i - 1] + noise[i]
        return out

    def test_it_centres_on_the_bias_and_not_on_zero(self):
        """A serially dependent but *independent* pair has a positive null mean."""
        rng = np.random.default_rng(5)
        rows = 8_000
        predictor = self._ar1(rows, 0.95, rng)
        outcome = np.digitize(self._ar1(rows, 0.95, rng), [-1.0, 1.0])
        statistic = lambda p, o: est.mutual_information(p, o, 6).plug_in
        null = est.circular_shift_null(statistic, predictor, outcome, 400, 60, rng)
        assert null.mean() > (6 - 1) * 2 / (2 * rows)

    def test_a_permutation_null_would_be_anti_conservative(self):
        """The reason the rotation exists, asserted rather than asserted about.

        On the same independent pair the permutation null sits well below the rotation
        null, so a true null crosses its upper tail and is called significant.
        """
        rng = np.random.default_rng(6)
        rows = 8_000
        predictor = self._ar1(rows, 0.95, rng)
        outcome = np.digitize(self._ar1(rows, 0.95, rng), [-1.0, 1.0])
        statistic = lambda p, o: est.mutual_information(p, o, 6).plug_in
        rotated = est.circular_shift_null(statistic, predictor, outcome, 400, 60, rng)
        permuted = np.array(
            [statistic(rng.permutation(predictor), outcome) for _ in range(60)]
        )
        assert rotated.mean() > 2 * permuted.mean()
        assert rotated.std(ddof=1) > 2 * permuted.std(ddof=1)

    def test_it_refuses_a_guard_that_leaves_no_room(self):
        rng = np.random.default_rng(7)
        with pytest.raises(ValueError, match="guard"):
            est.circular_shift_null(
                lambda p, o: 0.0, np.zeros(100), np.zeros(100, dtype=int), 60, 5, rng
            )


class TestTransferEntropy:
    """One lag, both directions reported separately, never their difference."""

    def test_it_is_one_way_on_a_one_way_chain(self):
        """``y`` is driven by the previous ``x``; ``x`` is driven by nothing.

        The reverse direction is a separate call with a forward increment of the *source*,
        not this one with its arguments swapped -- swapping would pair ``y_{t+1}`` against
        ``x_t`` where ``y_{t+1}`` is a function of ``x_t``, and report a flow in both
        directions on a chain that has one.
        """
        rng = np.random.default_rng(8)
        rows = 60_000
        x = rng.normal(size=rows)
        y = np.empty(rows)
        y[0] = rng.normal()
        y[1:] = 0.9 * x[:-1] + 0.4 * rng.normal(size=rows - 1)
        cut = [-0.5, 0.5]
        forward = est.transfer_entropy(
            x[:-1], np.digitize(y[1:], cut), np.digitize(y[:-1], cut), 6
        )
        reverse = est.transfer_entropy(
            y[:-1], np.digitize(x[1:], cut), np.digitize(x[:-1], cut), 6
        )
        assert forward.miller_madow > 0.1
        assert forward.miller_madow > 20 * abs(reverse.miller_madow)

    def test_it_is_near_zero_when_nothing_flows(self):
        rng = np.random.default_rng(9)
        rows = 60_000
        estimate = est.transfer_entropy(
            rng.normal(size=rows),
            np.digitize(rng.normal(size=rows), [-0.5, 0.5]),
            np.digitize(rng.normal(size=rows), [-0.5, 0.5]),
            6,
        )
        assert abs(estimate.miller_madow) < 5e-3


class TestBucketSeries:
    """Aggregation to a fixed clock, for the coarse-bucket regression."""

    def test_it_keeps_the_last_state_of_each_bucket(self):
        source = series([0.0, 0.4, 0.9, 1.2, 2.7], [10.0, 11.0, 12.0, 13.0, 14.0])
        bucketed = ir.bucket_series(source, Horizon(1.0))
        assert bucketed.values.tolist() == [12.0, 13.0, 14.0]
        assert bucketed.times.tolist() == [1.0, 2.0, 3.0]

    def test_an_empty_bucket_is_dropped_and_not_filled(self):
        """A bucket that saw no event has no state; inventing one puts a zero change
        into a regression that never happened."""
        source = series([0.0, 0.5, 5.5], [1.0, 2.0, 3.0])
        bucketed = ir.bucket_series(source, Horizon(1.0))
        assert bucketed.times.tolist() == [1.0, 6.0]
        assert bucketed.values.tolist() == [2.0, 3.0]

    def test_it_carries_the_segment_in_force_at_the_end(self):
        source = series([0.0, 0.5, 1.5], [1.0, 2.0, 3.0], segments=[0, 1, 1])
        assert ir.bucket_series(source, Horizon(1.0)).segments.tolist() == [1, 1]

    def test_the_row_count_matches_the_grid_arithmetic(self):
        """``T / b`` rows, which is why half-hour buckets on an hour-long session are two."""
        times = np.linspace(0.0, 3600.0, 100_000, endpoint=False)
        source = series(times, np.arange(times.size, dtype=float))
        assert ir.bucket_series(source, Horizon(1800.0)).values.size == 2
        assert ir.bucket_series(source, Horizon(60.0)).values.size == 60


class TestForwardJumpCounts:
    """Up and down moves in ``(t, t + h]``: an outcome the atom does not flatten."""

    def test_it_counts_each_direction(self):
        source = series([0.0, 1.0, 2.0, 3.0, 4.0], [10.0, 11.0, 11.0, 10.5, 12.0])
        ups, downs = ir.forward_jump_counts(source, Horizon(3.0))
        assert ups[0] == 1.0 and downs[0] == 1.0
        assert ups[1] == 1.0 and downs[1] == 1.0

    def test_it_distinguishes_a_quiet_window_from_a_round_trip(self):
        """The point of the statistic: a net change of zero is two different states."""
        quiet = series([0.0, 1.0, 2.0], [10.0, 10.0, 10.0])
        round_trip = series([0.0, 1.0, 2.0], [10.0, 11.0, 10.0])
        assert ir.forward_change(quiet, Horizon(2.0))[0] == ir.forward_change(round_trip, Horizon(2.0))[0]
        assert ir.forward_jump_counts(quiet, Horizon(2.0))[0][0] == 0.0
        assert ir.forward_jump_counts(round_trip, Horizon(2.0))[0][0] == 1.0

    def test_a_move_across_a_segment_boundary_counts_for_neither(self):
        source = series([0.0, 1.0, 2.0], [10.0, 99.0, 99.0], segments=[0, 1, 1])
        ups, downs = ir.forward_jump_counts(source, Horizon(2.0))
        assert ups[0] == 0.0 and downs[0] == 0.0

    def test_it_is_nan_where_nothing_lies_ahead(self):
        source = series([0.0, 1.0], [10.0, 11.0])
        ups, downs = ir.forward_jump_counts(source, Horizon(1.0))
        assert np.isnan(ups[-1]) and np.isnan(downs[-1])


class TestForwardVwap:
    """VWAP over ``(t, t + h]`` minus the mid, and the missingness that comes with it."""

    def test_it_is_the_volume_weighted_price_ahead(self):
        messages = [
            market_order(1.0, 50, BUY),
            market_order(2.0, 70, BUY),
            limit_order(3.0, 10, 995, BUY),
        ]
        book = session(messages)
        ahead = ir.forward_vwap(book, Horizon(2.5))
        traded = book.trades["TradedValue"].to_numpy(float)
        volume = book.trades["Volume"].to_numpy(float)
        mid = ir.aligned_mid_price(book).values
        expected = traded[1:3].sum() / volume[1:3].sum() - mid[0]
        assert ahead[0] == pytest.approx(expected)

    def test_a_window_that_traded_nothing_is_nan(self):
        """And the *rate* of that is reportable: it conditions the sample on activity."""
        messages = [limit_order(1.0, 10, 995, BUY), limit_order(2.0, 10, 994, BUY)]
        ahead = ir.forward_vwap(session(messages), Horizon(1.5))
        assert np.isnan(ahead).all()

    def test_it_refuses_a_session_that_determines_no_volume(self):
        book = session([market_order(1.0, 50, BUY)])
        book.trades = None
        with pytest.raises(ValueError, match="no VWAP"):
            ir.forward_vwap(book, Horizon(1.0))
