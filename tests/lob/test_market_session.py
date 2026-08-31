"""The session: two ways to the same statistics, and three ways to record it.

The reconciliation is the point.  One reads the book we simulated, the other reads only
the frame that book produced; they agree everywhere except where the frame's reported
levels do not span the grid window, and that exception is carried in a column of its own.
"""

import numpy as np
import pandas as pd
import pytest

from unito26.lob import config
from unito26.lob.messages import BUY, SELL, GridDepth, ReportedDepth, limit_order, market_order
from unito26.lob.orderbook import AXIS_B_VARIANTS, AggregateBook
from unito26.lob.replay import DeltaLog, MarketSession
from unito26.lob.simulate import OrderFlowSimulator

LEVELS = (GridDepth(1), GridDepth(2), GridDepth(5))
PRICE_UNIT = 100
DEPTH = ReportedDepth(3)

MESSAGES = [
    limit_order(1.0, 50, 1001, BUY),
    market_order(2.0, 200, BUY),
    limit_order(3.0, 400, 999, SELL),
    limit_order(4.0, 30, 995, BUY),
]


def opening(book_cls):
    return book_cls.from_levels({1000: 100, 999: 200, 998: 150}, {1002: 120, 1003: 180})


def reconcile(session):
    """A book always answers I^n; a frame answers only where its levels span the window."""
    expected = session.stats.copy()
    for n in session.imbalance_levels:
        uncovered = ~expected[f"QueueImbalance{n}Covered"].astype(bool)
        expected.loc[uncovered, f"QueueImbalance{n}"] = np.nan
    pd.testing.assert_frame_equal(expected, session.stats_from_frame(), check_dtype=False)


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestTheTwoRoutesAgree:
    def test_on_the_worked_example(self, book_cls):
        reconcile(MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, DEPTH, LEVELS, PRICE_UNIT, True
        ))

    def test_on_a_simulated_session(self, book_cls):
        simulator = OrderFlowSimulator(
            config.example_order_flow_params(), config.example_mark_params(), 10000, rng=5
        )
        book = AggregateBook()
        simulator.warm_up(book, horizon=20.0)
        messages = list(simulator.stream(book, horizon=200.0))
        session = MarketSession.from_occupied_levels(
            book_cls.for_prices([m.price for m in messages if m.price < 10**9]),
            messages, DEPTH, LEVELS, PRICE_UNIT, True,
        )
        reconcile(session)
        # The test is only exercising the uncovered branch if some rows are uncovered.
        assert not session.stats["QueueImbalance5Covered"].all()


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestTheThreeRecordingStrategiesAgree:
    def test_top_of_book_equals_occupied_levels_at_depth_one(self, book_cls):
        top = MarketSession.from_top_of_book(
            opening(book_cls), MESSAGES, LEVELS, PRICE_UNIT, True
        )
        occupied = MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, ReportedDepth(1), LEVELS, PRICE_UNIT, True
        )
        pd.testing.assert_frame_equal(top.lobster_book, occupied.lobster_book)
        pd.testing.assert_frame_equal(top.stats, occupied.stats)

    def test_a_delta_log_rebuilds_the_dense_session(self, book_cls):
        log = DeltaLog.record(opening(book_cls), MESSAGES)
        deltas = MarketSession.from_delta_log(
            log, book_cls, DEPTH, LEVELS, PRICE_UNIT, True
        )
        occupied = MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, DEPTH, LEVELS, PRICE_UNIT, True
        )
        pd.testing.assert_frame_equal(deltas.lobster_book, occupied.lobster_book)
        pd.testing.assert_frame_equal(deltas.stats, occupied.stats)

    def test_a_delta_log_rebuilds_a_warmed_up_book(self, book_cls):
        """A delta names only what a message changed, so the reconstruction has to be
        seeded with the state the replay started from."""
        book = opening(book_cls)
        book.submit(limit_order(0.5, 77, 994, BUY))
        log = DeltaLog.record(book, MESSAGES)
        deltas = MarketSession.from_delta_log(log, book_cls, DEPTH, LEVELS, PRICE_UNIT, True)
        fresh = opening(book_cls)
        fresh.submit(limit_order(0.5, 77, 994, BUY))
        occupied = MarketSession.from_occupied_levels(
            fresh, MESSAGES, DEPTH, LEVELS, PRICE_UNIT, True
        )
        pd.testing.assert_frame_equal(deltas.lobster_book, occupied.lobster_book)


class TestTheGridVersusColumnTrap:
    """tau = 1; asks at 101..105, bids at 99 and 90 and nothing between.

    The case that separates the two indexings.  At reported depth 2 the bid side spans ten
    grid positions on two reported levels and the ask side spans two on two.
    """

    BIDS = {99: 40, 90: 60}
    ASKS = {101: 10, 102: 20, 103: 30, 104: 40, 105: 50}

    @pytest.fixture
    def session(self):
        return MarketSession.from_occupied_levels(
            AggregateBook.from_levels(self.BIDS, self.ASKS),
            [limit_order(1.0, 1, 80, BUY)],
            ReportedDepth(2), (GridDepth(2), GridDepth(3)), 1, True,
        )

    def test_the_two_sides_span_differently(self):
        book = AggregateBook.from_levels(self.BIDS, self.ASKS)
        assert book.grid_span(BUY, ReportedDepth(2)) == 10
        assert book.grid_span(SELL, ReportedDepth(2)) == 2

    def test_the_imbalance_selects_by_price_not_by_column(self, session):
        by_price = (40 - 10 - 20) / (40 + 10 + 20)
        by_column = (40 + 60 - 10 - 20) / (40 + 60 + 10 + 20)
        assert session.stats_from_frame()["QueueImbalance2"].iloc[0] == pytest.approx(by_price)
        # The column-sliced answer pairs the touch with a level nine ticks away.
        assert not by_price == pytest.approx(by_column)

    def test_the_ask_side_alone_makes_the_next_level_unanswerable(self, session):
        """The bid has span to spare; the ask ran out at 102."""
        frame_route = session.stats_from_frame()
        assert not session.stats["QueueImbalance3Covered"].iloc[0]
        assert np.isnan(frame_route["QueueImbalance3"].iloc[0])
        # Computed from the book, which holds the levels the frame does not report.
        assert not np.isnan(session.stats["QueueImbalance3"].iloc[0])


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestFoldingWithoutOnlineStatistics:
    def test_the_frame_is_the_same_and_the_statistics_are_deferred(self, book_cls):
        deferred = MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, DEPTH, LEVELS, PRICE_UNIT, False
        )
        online = MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, DEPTH, LEVELS, PRICE_UNIT, True
        )
        assert deferred.stats is None
        pd.testing.assert_frame_equal(deferred.lobster_book, online.lobster_book)
        pd.testing.assert_frame_equal(
            deferred.stats_from_frame(), online.stats_from_frame()
        )


def _record_occupied(book_cls, messages):
    return MarketSession.from_occupied_levels(
        opening(book_cls), messages, DEPTH, LEVELS, PRICE_UNIT, True
    )


def _record_top_of_book(book_cls, messages):
    return MarketSession.from_top_of_book(
        opening(book_cls), messages, LEVELS, PRICE_UNIT, True
    )


def _record_delta_log(book_cls, messages):
    log = DeltaLog.record(opening(book_cls), messages)
    return MarketSession.from_delta_log(log, book_cls, DEPTH, LEVELS, PRICE_UNIT, True)


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
@pytest.mark.parametrize(
    "record", [_record_occupied, _record_top_of_book, _record_delta_log],
    ids=["occupied_levels", "top_of_book", "delta_log"],
)
@pytest.mark.parametrize("count", [1, 1023, 1024, 1025, 2049])
def test_the_buffer_grows_to_exactly_the_number_of_messages(book_cls, record, count):
    """Every recorder sizes its buffers by doubling, so the boundaries are where an
    off-by-one would live -- separately for the book rows and for the statistics."""
    messages = [limit_order(float(i), 10, 990 - (i % 5), BUY) for i in range(count)]
    session = record(book_cls, messages)
    assert len(session.lobster_book) == count
    assert len(session.stats) == count


class TestTheColumnSlicedImbalance:
    """The named counterexample: it is not `I^n`, and on the 101-105 / 99, 90 book the
    two answers are both plausible and different."""

    def test_it_reproduces_the_column_answer_on_the_trap(self):
        session = MarketSession.from_occupied_levels(
            AggregateBook.from_levels(
                TestTheGridVersusColumnTrap.BIDS, TestTheGridVersusColumnTrap.ASKS
            ),
            [limit_order(1.0, 1, 80, BUY)],
            ReportedDepth(2), (GridDepth(2),), 1, True,
        )
        by_column = (40 + 60 - 10 - 20) / (40 + 60 + 10 + 20)
        assert session.column_sliced_imbalance(GridDepth(2)).iloc[0] == pytest.approx(by_column)
        assert session.stats["QueueImbalance2"].iloc[0] != pytest.approx(by_column)

    @pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
    def test_it_agrees_with_the_grid_where_the_levels_are_contiguous(self, book_cls):
        session = MarketSession.from_occupied_levels(
            book_cls.from_levels({1000: 100, 999: 200}, {1001: 120, 1002: 180}),
            [limit_order(1.0, 10, 998, BUY)],
            ReportedDepth(2), (GridDepth(2),), 1, True,
        )
        assert session.column_sliced_imbalance(GridDepth(2)).iloc[0] == pytest.approx(
            session.stats["QueueImbalance2"].iloc[0]
        )
