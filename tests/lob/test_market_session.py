"""The session: two ways to the same statistics, and three ways to record it.

The reconciliation is the point.  One reads the book we simulated, the other reads only
the frame that book produced; they agree everywhere except where the frame's reported
levels do not span the grid window, and that exception is carried in a column of its own.
"""

import numpy as np
import pandas as pd
import pytest

from unito26.lob import config, frames
from unito26.lob.messages import (
    BUY, SELL, GridDepth, ReportedDepth, SweepSize, limit_order, market_order,
)
from unito26.lob.orderbook import AXIS_B_VARIANTS, AggregateBook
from unito26.lob.delta_log import DeltaLog
from unito26.lob.session import MarketSession, _book_buffer, _write_occupied_levels
from unito26.lob.statistics import SessionStatistics
from unito26.lob.simulate import OrderFlowSimulator

LEVELS = (GridDepth(1), GridDepth(2), GridDepth(5))
SWEEPS = (SweepSize(100), SweepSize(400))
WINDOWS = (1, 10)
SPEC = SessionStatistics(LEVELS, SWEEPS, WINDOWS)
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
    for n in session.statistics.imbalance_levels:
        uncovered = ~expected[f"QueueImbalance{n}Covered"].astype(bool)
        expected.loc[uncovered, f"QueueImbalance{n}"] = np.nan
    pd.testing.assert_frame_equal(expected, session.stats_from_frame(), check_dtype=False)


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestTheTwoRoutesAgree:
    def test_on_the_worked_example(self, book_cls):
        reconcile(MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, DEPTH, SPEC, PRICE_UNIT, True
        ))

    def test_on_a_simulated_session(self, book_cls):
        simulator = OrderFlowSimulator(
            config.example_order_flow_params(), config.example_mark_params(), 10000, rng=5
        )
        book = AggregateBook()
        simulator.warm_up(book, horizon=20.0)
        messages = list(simulator.stream(book, horizon=200.0))
        session = MarketSession.from_occupied_levels(
            book_cls.for_prices([m.price for m in messages]),
            messages, DEPTH, SPEC, PRICE_UNIT, True,
        )
        reconcile(session)
        # The test is only exercising the uncovered branch if some rows are uncovered.
        assert not session.stats["QueueImbalance5Covered"].all()


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestTheThreeRecordingStrategiesAgree:
    def test_top_of_book_equals_occupied_levels_at_depth_one(self, book_cls):
        top = MarketSession.from_top_of_book(
            opening(book_cls), MESSAGES, SPEC, PRICE_UNIT, True
        )
        occupied = MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, ReportedDepth(1), SPEC, PRICE_UNIT, True
        )
        pd.testing.assert_frame_equal(top.lobster_book, occupied.lobster_book)
        pd.testing.assert_frame_equal(top.stats, occupied.stats)
        pd.testing.assert_frame_equal(top.trades, occupied.trades)

    def test_they_agree_with_the_statistics_off_too(self, book_cls):
        """And neither records anything it will not return.

        The notebook times these two against each other on this path, so work done here
        and discarded is charged to one side of a comparison that reports them as the same
        session recorded two ways.  The buffers are None rather than unused, which turns
        recording into an ``AttributeError`` instead of a quiet cost.
        """
        top = MarketSession.from_top_of_book(
            opening(book_cls), MESSAGES, SPEC, PRICE_UNIT, False
        )
        occupied = MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, ReportedDepth(1), SPEC, PRICE_UNIT, False
        )
        pd.testing.assert_frame_equal(top.lobster_book, occupied.lobster_book)
        for session in (top, occupied):
            assert session.stats is None and session.trades is None

    def test_a_delta_log_rebuilds_the_dense_session(self, book_cls):
        log = DeltaLog.record(opening(book_cls), MESSAGES)
        deltas = MarketSession.from_delta_log(
            log, book_cls, DEPTH, SPEC, PRICE_UNIT, True
        )
        occupied = MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, DEPTH, SPEC, PRICE_UNIT, True
        )
        pd.testing.assert_frame_equal(deltas.lobster_book, occupied.lobster_book)
        pd.testing.assert_frame_equal(deltas.stats, occupied.stats)

    def test_a_delta_log_rebuilds_a_warmed_up_book(self, book_cls):
        """A delta names only what a message changed, so the reconstruction has to be
        seeded with the state the replay started from."""
        book = opening(book_cls)
        book.submit(limit_order(0.5, 77, 994, BUY), record=False)
        log = DeltaLog.record(book, MESSAGES)
        deltas = MarketSession.from_delta_log(log, book_cls, DEPTH, SPEC, PRICE_UNIT, True)
        fresh = opening(book_cls)
        fresh.submit(limit_order(0.5, 77, 994, BUY), record=False)
        occupied = MarketSession.from_occupied_levels(
            fresh, MESSAGES, DEPTH, SPEC, PRICE_UNIT, True
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
            ReportedDepth(2), SessionStatistics((GridDepth(2), GridDepth(3)), SWEEPS, WINDOWS), 1, True,
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
            opening(book_cls), MESSAGES, DEPTH, SPEC, PRICE_UNIT, False
        )
        online = MarketSession.from_occupied_levels(
            opening(book_cls), MESSAGES, DEPTH, SPEC, PRICE_UNIT, True
        )
        assert deferred.stats is None
        pd.testing.assert_frame_equal(deferred.lobster_book, online.lobster_book)
        pd.testing.assert_frame_equal(
            deferred.stats_from_frame(), online.stats_from_frame()
        )


def _record_occupied(book_cls, messages):
    return MarketSession.from_occupied_levels(
        opening(book_cls), messages, DEPTH, SPEC, PRICE_UNIT, True
    )


def _record_top_of_book(book_cls, messages):
    return MarketSession.from_top_of_book(
        opening(book_cls), messages, SPEC, PRICE_UNIT, True
    )


def _record_delta_log(book_cls, messages):
    log = DeltaLog.record(opening(book_cls), messages)
    return MarketSession.from_delta_log(log, book_cls, DEPTH, SPEC, PRICE_UNIT, True)


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
            ReportedDepth(2), SessionStatistics((GridDepth(2),), SWEEPS, WINDOWS), 1, True,
        )
        by_column = (40 + 60 - 10 - 20) / (40 + 60 + 10 + 20)
        assert session.column_sliced_imbalance(GridDepth(2)).iloc[0] == pytest.approx(by_column)
        assert session.stats["QueueImbalance2"].iloc[0] != pytest.approx(by_column)

    @pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
    def test_it_agrees_with_the_grid_where_the_levels_are_contiguous(self, book_cls):
        session = MarketSession.from_occupied_levels(
            book_cls.from_levels({1000: 100, 999: 200}, {1001: 120, 1002: 180}),
            [limit_order(1.0, 10, 998, BUY)],
            ReportedDepth(2), SessionStatistics((GridDepth(2),), SWEEPS, WINDOWS), 1, True,
        )
        assert session.column_sliced_imbalance(GridDepth(2)).iloc[0] == pytest.approx(
            session.stats["QueueImbalance2"].iloc[0]
        )


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("count", [1, 1023, 1024, 1025, 2049])
class TestGrowingAndPreallocatingAgree:
    """A list is sized exactly and never grows; a generator doubles.  Two code paths for
    the same session, so they are compared row for row rather than by length.

    The rows have a padded side -- every message here is a buy, so the ask side keeps two
    levels against a depth of three -- because padding is what a grown buffer can get
    wrong.  Growth allocates with `np.empty`, and a tail that was not repainted carries
    freed memory into the columns nothing writes.
    """

    @staticmethod
    def buys(count):
        return [limit_order(float(i), 10, 990 - (i % 5), BUY) for i in range(count)]

    @staticmethod
    def streamed(messages):
        """A genuine generator.  `iter(list)` will not do: `length_hint` reports the
        remaining length of a list iterator, so the buffer would be sized exactly and the
        growth path -- the whole subject here -- would never run."""
        return (message for message in messages)

    def test_the_frames_are_identical(self, book_cls, count):
        messages = self.buys(count)
        from_list = MarketSession.from_occupied_levels(
            opening(book_cls), messages, DEPTH, SPEC, PRICE_UNIT, True
        )
        from_stream = MarketSession.from_occupied_levels(
            opening(book_cls), self.streamed(messages), DEPTH, SPEC, PRICE_UNIT, True
        )
        assert len(from_stream.lobster_book) == count
        pd.testing.assert_frame_equal(from_list.lobster_book, from_stream.lobster_book)
        pd.testing.assert_frame_equal(from_list.stats, from_stream.stats)

    def test_the_padded_side_really_is_padded_throughout(self, book_cls, count):
        """The assertion the length check could not make: every row past every growth
        boundary still says 'no third ask level' rather than saying something plausible."""
        session = MarketSession.from_occupied_levels(
            opening(book_cls), self.streamed(self.buys(count)), DEPTH, SPEC, PRICE_UNIT, True
        )
        assert (session.lobster_book[f"AskPrice{DEPTH}"] == frames.ASK_PADDING).all()
        assert (session.lobster_book[f"AskSize{DEPTH}"] == 0).all()

    def test_the_deferred_route_agrees_across_the_boundary(self, book_cls, count):
        """`online_statistics=False` writes the whole row through `write_lobster_row`;
        with them on it writes only the occupied levels into a pre-padded row.  The two
        must not drift."""
        messages = self.buys(count)
        deferred = MarketSession.from_occupied_levels(
            opening(book_cls), self.streamed(messages), DEPTH, SPEC, PRICE_UNIT, False
        )
        online = MarketSession.from_occupied_levels(
            opening(book_cls), self.streamed(messages), DEPTH, SPEC, PRICE_UNIT, True
        )
        pd.testing.assert_frame_equal(deferred.lobster_book, online.lobster_book)


class TestTheRowBufferKeepsItsPadding:
    """`_write_occupied_levels` writes only the levels a book has, so what it does *not*
    write has to be padding already.  That is the buffer's contract, and it is the one
    thing a growth could quietly break."""

    def test_a_grown_tail_is_repainted(self):
        depth = ReportedDepth(3)
        buffer = _book_buffer(depth, 0)
        padding = frames.lobster_padding_row(depth)
        for _ in range(len(buffer.array) + 1):
            buffer.claim()
        assert (buffer.array[buffer.used - 1] == padding).all()
        assert (buffer.finished() == padding).all()

    def test_a_row_written_twice_keeps_no_trace_of_the_first(self):
        """Writing only the occupied levels is not idempotent against a stale row: a
        deep book followed by a shallow one would leave the deep book's levels standing
        as the shallow one's padding."""
        depth = ReportedDepth(3)
        deep = AggregateBook.from_levels({1000: 10, 999: 20, 998: 30}, {1001: 40})
        shallow = AggregateBook.from_levels({1000: 10}, {1001: 40})
        rows = _book_buffer(depth, 2)
        for book in (deep, shallow):
            index = rows.claim()
            _write_occupied_levels(
                rows.array[index],
                book.side_statistics(BUY, depth), book.side_statistics(SELL, depth),
                PRICE_UNIT, depth,
            )
        assert rows.array[1].tolist() == shallow.to_lobster_row(PRICE_UNIT, depth)


class TestABookEmptyOnBothSides:
    """Every level padded: the degenerate row the ratios divide by zero on.

    ``AggregateBook`` answers None or NaN here by construction, but the frame route
    reaches the same answers through array arithmetic, where a guarded quotient and an
    unguarded one are indistinguishable in the output and differ only in whether they
    raise the invalid-value flag on the way.  The flags are made fatal so they are.
    """

    @pytest.fixture
    def session(self):
        return MarketSession.from_occupied_levels(
            AggregateBook(), [market_order(1.0, 100, BUY)], DEPTH, SPEC, PRICE_UNIT, True
        )

    def test_the_recorded_row_is_all_padding(self, session):
        assert session.lobster_book.to_numpy().tolist() == [
            frames.lobster_padding_row(DEPTH).tolist()
        ]

    def test_the_frame_route_answers_nan_without_raising(self, session):
        with np.errstate(all="raise"):
            frame_route = session.stats_from_frame()
            vwap = session.vwap(1)
        for name in ("Spread", "MidPrice", "MicroPrice", "QueueImbalance1", "AverageDepth1"):
            assert np.isnan(frame_route[name].iloc[0])
        assert np.isnan(session.trades["VWAP1"].iloc[0])
        assert np.isnan(vwap.iloc[0])


class TestGapsThatDifferOnEverySide:
    """A fixture whose twelve gap statistics are pairwise distinct across the two sides.

    The reconciliation compares columns by name, so it catches a transposed pair only where
    the two disagree numerically.  On the fixtures above ``LargestGap`` equals
    ``FirstGapSize`` and ``FirstGapDistance`` equals ``LargestGapDistance`` on both sides,
    which leaves four of the twelve interchangeable without any test noticing.  Here no two
    of the six agree across sides.
    """

    DEPTH = ReportedDepth(5)
    SPEC = SessionStatistics((GridDepth(1),), (SweepSize(100),), (1,))

    @pytest.fixture
    def session(self):
        book = AggregateBook.from_levels(
            {1000: 100, 999: 200, 995: 50, 990: 30, 989: 40},
            {1002: 120, 1004: 60, 1010: 80, 1013: 40},
        )
        return MarketSession.from_occupied_levels(
            book, [limit_order(1.0, 10, 999, BUY)], self.DEPTH, self.SPEC, PRICE_UNIT, True
        )

    def test_the_two_sides_disagree_on_every_gap_statistic(self, session):
        row = session.stats.iloc[0]
        bid = [row[f"Bid{name}"] for name in (
            "OccupiedLevels", "GapCount", "LargestGap",
            "FirstGapDistance", "FirstGapSize", "LargestGapDistance",
        )]
        ask = [row[f"Ask{name}"] for name in (
            "OccupiedLevels", "GapCount", "LargestGap",
            "FirstGapDistance", "FirstGapSize", "LargestGapDistance",
        )]
        assert bid == [5, 2, 4, 2, 3, 6]
        assert ask == [4, 3, 5, 1, 1, 3]
        assert all(b != a for b, a in zip(bid, ask))

    def test_the_two_routes_agree_on_it(self, session):
        reconcile(session)
