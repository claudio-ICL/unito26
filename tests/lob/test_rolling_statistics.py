"""Order flow imbalance and VWAP: what a window makes of a recorded series.

Two statistics of consecutive states and of the trades, against the one-state statistics
everywhere else in the module.  The distinction that matters is the last class here: a
record of book configurations determines the order flow and cannot determine a volume,
because a level shrinks by cancellation as well as by execution.
"""

import numpy as np
import pandas as pd
import pytest

from unito26.lob.messages import (
    BUY, SELL, GridDepth, ReportedDepth, SweepSize, limit_order, market_order, withdrawal,
)
from unito26.lob.orderbook import AXIS_B_VARIANTS, AggregateBook
from unito26.lob.delta_log import DeltaLog
from unito26.lob.session import MarketSession, _rolling_sum, _window_start
from unito26.lob.statistics import SessionStatistics

LEVELS = (GridDepth(1), GridDepth(2))
SWEEPS = (SweepSize(100),)
WINDOWS = (1, 1000)
SPEC = SessionStatistics(LEVELS, SWEEPS, WINDOWS)
DEPTH = ReportedDepth(4)
PRICE_UNIT = 100

#: Section 8: bid 10.00 x 100, 9.99 x 200, 9.98 x 150; ask 10.02 x 120, 10.03 x 180.
BIDS = {1000: 100, 999: 200, 998: 150}
ASKS = {1002: 120, 1003: 180}


def session(messages, book_cls=AggregateBook, spec=SPEC, depth=DEPTH):
    return MarketSession.from_occupied_levels(
        book_cls.from_levels(dict(BIDS), dict(ASKS)), messages, depth, spec, PRICE_UNIT, True
    )


class TestTheContributionOfOneEvent:
    """``e_n``, one elementary event at a time.  Values derived from the formula."""

    def test_a_limit_buy_joining_the_best_bid_adds_its_size(self):
        flow = session([
            limit_order(1.0, 10, 995, BUY),      # away from the touch; e is NaN anyway
            limit_order(2.0, 60, 1000, BUY),
        ])
        assert flow.stats["OrderFlowContribution"].iloc[1] == 60

    def test_an_event_that_moves_nothing_contributes_nothing(self):
        """Both bid indicators fire when the price is unchanged, giving S^b_n - S^b_{n-1}.

        A single ``where`` on ``P^b_n >= P^b_{n-1}`` loses exactly this case, and it is
        most of the events in a session.
        """
        flow = session([
            limit_order(1.0, 10, 990, BUY),
            limit_order(2.0, 10, 991, BUY),      # deep: the touch is untouched
        ])
        assert flow.stats["OrderFlowContribution"].iloc[1] == 0

    def test_a_cancellation_at_the_best_bid_removes_its_size(self):
        flow = session([
            limit_order(1.0, 10, 990, BUY),
            withdrawal(2.0, 40, 1000, BUY),
        ])
        assert flow.stats["OrderFlowContribution"].iloc[1] == -40

    def test_a_cancellation_that_empties_the_best_bid_removes_the_whole_queue(self):
        flow = session([
            limit_order(1.0, 10, 990, BUY),
            withdrawal(2.0, 100, 1000, BUY),
        ])
        assert flow.stats["OrderFlowContribution"].iloc[1] == -100

    def test_a_market_buy_clearing_the_best_ask_is_positive(self):
        """And it registers the *previous queue size*, not the volume it traded.

        The order takes 200 shares; 120 of them were the best ask.  OFI reads the touch, so
        the 80 it took from the level behind are invisible to it.  Asserting 200 here would
        be asserting a different statistic.
        """
        flow = session([limit_order(1.0, 10, 990, BUY), market_order(2.0, 200, BUY)])
        assert flow.stats["OrderFlowContribution"].iloc[1] == 120

    def test_the_first_row_is_undefined_rather_than_zero(self):
        flow = session([limit_order(1.0, 60, 1000, BUY)])
        assert np.isnan(flow.stats["OrderFlowContribution"].iloc[0])

    def test_an_empty_side_makes_the_event_undefined(self):
        """``NaN >= NaN`` is False, so both indicators fall silent and the expression
        evaluates to an ordinary zero.  The mask has to be written."""
        flow = session([
            limit_order(1.0, 10, 990, BUY),
            market_order(2.0, 5000, BUY),        # clears the ask side outright
            limit_order(3.0, 10, 1050, SELL),
        ])
        contribution = flow.stats["OrderFlowContribution"]
        assert np.isnan(contribution.iloc[1])    # the ask side went
        assert np.isnan(contribution.iloc[2])    # and its predecessor had none

    def test_it_reads_the_touch_and_so_does_not_depend_on_the_reported_depth(self):
        """The property that separates it from ``I^n``, which needs the window reported."""
        messages = [
            limit_order(1.0, 60, 1000, BUY), market_order(2.0, 200, BUY),
            limit_order(3.0, 400, 999, SELL), withdrawal(4.0, 30, 998, BUY),
        ]
        shallow = session(messages, depth=ReportedDepth(1))
        deep = session(messages, depth=ReportedDepth(10))
        pd.testing.assert_series_equal(
            shallow.stats["OrderFlowContribution"], deep.stats["OrderFlowContribution"]
        )


class TestTheWindowedSum:
    MESSAGES = [
        limit_order(1.0, 60, 1000, BUY),
        limit_order(2.0, 40, 1000, BUY),
        withdrawal(3.0, 25, 1000, BUY),
    ]

    def test_a_window_containing_an_undefined_event_is_undefined(self):
        rolling = session(self.MESSAGES).stats
        assert np.isnan(rolling["OrderFlowImbalance1000"].iloc[0])
        assert rolling["OrderFlowImbalance1000Covered"].iloc[0] == 0.0

    def test_a_window_clear_of_it_sums_the_contributions(self):
        """The one-second window at t = 3 sees only the event at t = 3."""
        rolling = session(self.MESSAGES).stats
        assert rolling["OrderFlowImbalance1"].iloc[2] == -25
        assert rolling["OrderFlowImbalance1Covered"].iloc[2] == 1.0

    def test_the_window_is_half_open_on_the_left(self):
        """At t = 3 with w = 1 the event at t = 2 is exactly one second old, so it is out."""
        rolling = session(self.MESSAGES).stats
        assert rolling["OrderFlowImbalance1"].iloc[2] == -25
        assert rolling["OrderFlowImbalance1"].iloc[2] != 40 - 25

    def test_the_average_depth_is_the_mean_touch_over_the_window(self):
        rolling = session(self.MESSAGES).stats
        depths = rolling["TouchDepth"].to_numpy()
        assert rolling["AverageDepth1000"].iloc[2] == pytest.approx(depths.mean() / 2)


class TestVWAP:
    MESSAGES = [
        market_order(1.0, 200, BUY),          # 120 at 1002, 80 at 1003
        limit_order(2.0, 150, 999, SELL),     # 100 at 1000, 50 at 999
        limit_order(3.0, 10, 990, BUY),       # nothing trades
    ]
    FILLS = [(1002, 120), (1003, 80), (1000, 100), (999, 50)]

    def test_over_the_whole_session_it_is_the_value_over_the_volume(self):
        traded = session(self.MESSAGES).trades
        value = sum(price * size for price, size in self.FILLS)
        volume = sum(size for _, size in self.FILLS)
        assert traded["VWAP1000"].iloc[-1] == pytest.approx(value / volume)

    def test_it_lies_between_the_extreme_fill_prices(self):
        traded = session(self.MESSAGES).trades
        prices = [price for price, _ in self.FILLS]
        assert min(prices) <= traded["VWAP1000"].iloc[-1] <= max(prices)

    def test_the_two_sides_are_split_by_the_aggressor(self):
        traded = session(self.MESSAGES).trades
        assert traded["VWAPBuy1000"].iloc[-1] == pytest.approx((120 * 1002 + 80 * 1003) / 200)
        assert traded["VWAPSell1000"].iloc[-1] == pytest.approx((100 * 1000 + 50 * 999) / 150)

    def test_the_buy_side_prints_above_the_sell_side(self):
        """An uncrossed book: buyers lift the ask, sellers hit the bid."""
        traded = session(self.MESSAGES).trades
        assert traded["VWAPBuy1000"].iloc[-1] > traded["VWAPSell1000"].iloc[-1]

    def test_a_window_that_traded_nothing_has_no_price(self):
        """NaN and not zero.  Zero is a price."""
        traded = session(self.MESSAGES).trades
        assert np.isnan(traded["VWAP1"].iloc[2])

    def test_the_signed_volume_is_section_sevens_V(self):
        traded = session(self.MESSAGES).trades
        assert list(traded["SignedVolume"]) == [200.0, -150.0, 0.0]
        assert list(traded["Volume"]) == [200.0, 150.0, 0.0]

    def test_the_accessor_answers_a_window_the_specification_did_not_name(self):
        folded = session(self.MESSAGES)
        pd.testing.assert_series_equal(
            folded.vwap(1000), folded.trades["VWAP1000"], check_names=False
        )


class TestAVolumeIsNotRecoverableFromConfigurations:
    """The size-versus-volume distinction of section 3, in the shape of the data."""

    MESSAGES = [
        limit_order(1.0, 60, 1000, BUY), market_order(2.0, 200, BUY),
        limit_order(3.0, 400, 999, SELL), withdrawal(4.0, 30, 998, BUY),
    ]

    @pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
    def test_a_delta_log_has_no_trades(self, book_cls):
        log = DeltaLog.record(book_cls.from_levels(dict(BIDS), dict(ASKS)), self.MESSAGES)
        rebuilt = MarketSession.from_delta_log(
            log, book_cls, DEPTH, SPEC, PRICE_UNIT, True
        )
        assert rebuilt.trades is None
        with pytest.raises(ValueError, match="cancellation"):
            rebuilt.vwap(1000)

    @pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
    def test_but_it_does_have_the_order_flow_and_the_sweep_costs(self, book_cls):
        """Both are functions of the configurations, which is exactly what a log records."""
        log = DeltaLog.record(book_cls.from_levels(dict(BIDS), dict(ASKS)), self.MESSAGES)
        rebuilt = MarketSession.from_delta_log(log, book_cls, DEPTH, SPEC, PRICE_UNIT, True)
        dense = session(self.MESSAGES, book_cls)
        for column in ("OrderFlowContribution", "OrderFlowImbalance1000", "SweepCostBuy100"):
            pd.testing.assert_series_equal(rebuilt.stats[column], dense.stats[column])


class TestTheWindowItself:
    def brute_force(self, times, values, window):
        return np.array([
            sum(v for t, v in zip(times, values) if row - window < t <= row)
            for row in times
        ])

    def rolling(self, times, values, window):
        times = np.asarray(times, dtype=float)
        return _rolling_sum(_window_start(times, window), np.asarray(values, dtype=float))

    def test_it_matches_a_brute_force_walk(self):
        """On distinct timestamps, where the two definitions coincide.

        The brute force sums every row inside the window; the rolling form stops at the
        current row.  They differ only where timestamps repeat, which is the next test.
        """
        rng = np.random.default_rng(0)
        times = np.sort(rng.choice(400, 200, replace=False)).astype(float)
        values = rng.integers(1, 100, 200).astype(float)
        for window in (1, 3, 10, 1000):
            got = self.rolling(times, values, window)
            want = self.brute_force(times, values, window)
            assert np.array_equal(got, want), window

    def test_simultaneous_rows_do_not_see_each_other(self):
        """Row i sums ``[start, i]``, so the second of two rows at one timestamp sees the
        first and not the reverse.  A hand-check that assumes otherwise will not
        reproduce the column, and LOBSTER has repeated timestamps in quantity."""
        got = self.rolling([1.0, 1.0, 1.0], [10.0, 20.0, 30.0], 5)
        assert list(got) == [10.0, 30.0, 60.0]

    def test_a_window_longer_than_the_session_sums_everything(self):
        got = self.rolling([1.0, 2.0, 3.0], [10.0, 20.0, 30.0], 1000)
        assert list(got) == [10.0, 30.0, 60.0]

    def test_a_session_of_one_row(self):
        assert list(self.rolling([1.0], [7.0], 10)) == [7.0]

    def test_the_left_edge_is_open(self):
        """An event exactly ``window`` old is outside."""
        assert list(self.rolling([0.0, 1.0, 2.0], [100.0, 10.0, 1.0], 2)) == [100.0, 110.0, 11.0]

    def test_a_window_of_zero_or_less_is_refused_by_the_specification(self):
        with pytest.raises(ValueError):
            SessionStatistics(LEVELS, SWEEPS, (0,))
        with pytest.raises(ValueError):
            SessionStatistics(LEVELS, (SweepSize(0),), WINDOWS)


class TestWhatTheSpecificationRefuses:
    """The column names are built from these values, so a value that names a bad column has
    to be refused here rather than discovered in a frame."""

    @pytest.mark.parametrize("field", ["imbalance_levels", "sweep_sizes", "windows"])
    def test_a_float_is_not_a_count(self, field):
        """1.5 names `QueueImbalance1.5`, and the dot defeats `query` and attribute access.
        A whole-valued float is refused too: one that has arrived at 1.0 by arithmetic will
        arrive at 1.0000000001 next time, and the two name different columns."""
        argument = {"imbalance_levels": LEVELS, "sweep_sizes": SWEEPS, "windows": WINDOWS}
        for value in (1.5, 2.0):
            with pytest.raises(ValueError, match="whole number"):
                SessionStatistics(**{**argument, field: (value,)})

    def test_a_numpy_integer_is_a_count(self):
        """A depth read off a frame arrives as np.int64, and refusing it would be a trap of
        its own."""
        spec = SessionStatistics((np.int64(2),), (np.int64(100),), (np.int64(5),))
        assert spec.imbalance_levels == (2,) and spec.windows == (5,)

    def test_the_accessor_refuses_what_the_specification_refuses(self):
        """`vwap` is offered as the way to ask for a window the spec did not name, so it
        cannot be laxer than the spec.  Unscreened, `vwap(0)` returns an all-NaN series:
        the window start runs past the current row and the sums come out non-positive."""
        folded = session(TestVWAP.MESSAGES)
        for window in (0, -3, 1.5):
            with pytest.raises(ValueError, match="whole number"):
                folded.vwap(window)


class TestTheCountersDescribeTheLastMessage:
    def test_a_withdrawal_clears_what_the_previous_submission_traded(self):
        """`submit` and `withdraw` are public and the tests call them directly, so the
        counters cannot rely on `apply` to reset them."""
        book = AggregateBook.from_levels({1000: 100}, {1002: 120})
        book.submit(market_order(1.0, 50, BUY), record=False)
        assert (book.last_fill_count, book.last_traded_size) == (1, 50)
        book.withdraw(withdrawal(2.0, 10, 1000, BUY), record=False)
        assert (book.last_fill_count, book.last_traded_size, book.last_traded_value) == (0, 0, 0)
