"""A LOBSTER pair, and the one transformation that makes it a session.

The pair and the session are two types on purpose: a row of the first is the execution of
one resting order, a row of the second is one aggressive order.  These tests pin what the
crossing preserves and, just as deliberately, what it does not -- a coarsening that
preserved everything would be measuring nothing.
"""

import numpy as np
import pandas as pd
import pandera.errors as pe
import pytest
from pathlib import Path

from unito26.lob import frames, lobster
from unito26.lob.lobster import LobsterEvent
from unito26.lob.lobster_session import (
    LobsterMarketSession, coarsening_report, coarsening_totals, market_order_index,
)
from unito26.lob.messages import (
    BUY, SELL, GridDepth, ReportedDepth, SweepSize, TickGrid, limit_order,
)
from unito26.lob.orderbook import AggregateBook
from unito26.lob.session import MarketSession
from unito26.lob.statistics import SessionStatistics

DEPTH = ReportedDepth(2)
NAME = "TICK_2012-06-21_34200000_57600000_{kind}_2.csv"
SPEC = SessionStatistics((GridDepth(2),), (SweepSize(100),), (1,))
CENT = TickGrid(0.01)
WHOLE_DAY = lobster.NASDAQ_REGULAR_HOURS

# time, type, order id, size, price, direction
MESSAGES = frames.lobster_message_file_columns()


def pair(tmp_path, messages, book):
    """Write a hand-made pair and read it back as a raw session."""
    files = lobster.LobsterFiles.parse(tmp_path / NAME.format(kind="message"))
    lobster.write_pair(
        files,
        pd.DataFrame(messages, columns=MESSAGES),
        pd.DataFrame(book, columns=frames.lobster_book_columns(DEPTH)),
    )
    return LobsterMarketSession.from_files(files, SPEC, CENT, WHOLE_DAY)


def state(bid_size, bid=100000, ask=100200, ask_size=120, second=99900, second_size=10):
    return [ask, ask_size, bid, bid_size, frames.ASK_PADDING, 0, second, second_size]


QUEUE_SPLIT = (
    [
        (34200.0, 1, 1, 10, 99900, 1),
        (34201.5, 4, 11, 20, 100000, 1),
        (34201.5, 4, 12, 20, 100000, 1),
        (34201.5, 4, 13, 15, 100000, 1),
        (34202.0, 1, 2, 10, 99900, 1),
    ],
    [state(100), state(80), state(60), state(45), state(45, second_size=20)],
)

LEVEL_WALK = (
    [
        (34200.0, 1, 1, 10, 99900, 1),
        (34201.5, 4, 11, 100, 100000, 1),
        (34201.5, 4, 12, 30, 99900, 1),
    ],
    [
        state(100, second_size=200),
        [100200, 120, 99900, 200, frames.ASK_PADDING, 0, 99800, 10],
        [100200, 120, 99900, 170, frames.ASK_PADDING, 0, 99800, 10],
    ],
)


class TestOneAggressiveOrderIsOneRow:
    def test_three_fills_at_one_price_become_one(self, tmp_path):
        raw = pair(tmp_path, *QUEUE_SPLIT)
        coarse = raw.coarsened(True)
        assert len(raw.book) == 5
        assert len(coarse.lobster_book) == 3

    def test_the_row_kept_is_the_last(self, tmp_path):
        """The state after the whole order matched, which is the state a fold writes."""
        coarse = pair(tmp_path, *QUEUE_SPLIT).coarsened(False)
        assert coarse.lobster_book["BidSize1"].tolist() == [100, 45, 45]
        assert coarse.lobster_book.index.tolist() == [34200.0, 34201.5, 34202.0]

    def test_the_fills_are_summed_onto_it(self, tmp_path):
        coarse = pair(tmp_path, *QUEUE_SPLIT).coarsened(False)
        assert coarse.trades["Volume"].tolist() == [0.0, 55.0, 0.0]
        assert coarse.trades["TradedValue"].tolist() == [0.0, 55.0 * 1000, 0.0]

    def test_the_aggressor_is_the_side_that_did_not_rest(self, tmp_path):
        """Direction names the resting buy orders, so the trade is a sell."""
        coarse = pair(tmp_path, *QUEUE_SPLIT).coarsened(False)
        assert coarse.trades["SignedVolume"].tolist() == [0.0, -55.0, 0.0]

    def test_the_volume_is_the_one_the_file_carries(self, tmp_path):
        raw = pair(tmp_path, *QUEUE_SPLIT)
        assert raw.coarsened(False).trades["Volume"].sum() == (
            raw.trades_from_messages()["Volume"].sum()
        )


class TestWhatSurvivesTheCoarseningAndWhatDoesNot:
    def coarse_and_fine(self, tmp_path, fixture):
        raw = pair(tmp_path, *fixture)
        keep = raw.coarsened(True)
        return raw.stats_from_frame(), keep.stats

    def test_a_statistic_of_one_configuration_is_the_same_number(self, tmp_path):
        fine, coarse = self.coarse_and_fine(tmp_path, QUEUE_SPLIT)
        for column in ("Spread", "MidPrice", "MicroPrice", "QueueImbalance2", "TouchDepth"):
            np.testing.assert_array_equal(
                coarse[column].to_numpy(), fine[column].iloc[[0, 3, 4]].to_numpy()
            )

    def test_the_order_flow_survives_a_queue_split(self, tmp_path):
        """Three decrements at one price sum to the single decrement.  Exactly."""
        fine, coarse = self.coarse_and_fine(tmp_path, QUEUE_SPLIT)
        assert fine["OrderFlowContribution"].iloc[1:4].sum() == -55.0
        assert coarse["OrderFlowContribution"].iloc[1] == -55.0

    def test_and_does_not_survive_a_level_walk(self, tmp_path):
        """Asserted, not tolerated: it is the one thing the coarsening cannot preserve.

        The contribution reads the touch alone, so an order that walks registers only the
        queue it emptied first; the fills after that emptying are invisible to it.
        """
        fine, coarse = self.coarse_and_fine(tmp_path, LEVEL_WALK)
        assert fine["OrderFlowContribution"].iloc[1:].sum() == -130.0
        assert coarse["OrderFlowContribution"].iloc[1] == -100.0

    def test_a_per_row_average_moves(self, tmp_path):
        fine, coarse = self.coarse_and_fine(tmp_path, QUEUE_SPLIT)
        assert coarse["AverageDepth1"].iloc[1] != fine["AverageDepth1"].iloc[3]


class TestCoarseningWhatIsAlreadyCoarse:
    def test_a_pair_with_no_multi_fill_order_is_unchanged(self, tmp_path):
        messages = [
            (34200.0, 1, 1, 10, 99900, 1),
            (34201.0, 4, 11, 20, 100000, 1),
            (34202.0, 4, 12, 20, 100000, 1),
        ]
        raw = pair(tmp_path, messages, [state(100), state(80), state(60)])
        coarse = raw.coarsened(False)
        assert len(coarse.lobster_book) == len(raw.book)
        assert coarse.trades["Volume"].tolist() == [0.0, 20.0, 20.0]

    def test_it_is_idempotent(self, tmp_path):
        """Coarsening a coarse session again is the identity, which is what makes it one."""
        once = pair(tmp_path, *QUEUE_SPLIT).coarsened(False)
        again = LobsterMarketSession(
            files=lobster.LobsterFiles.parse(tmp_path / NAME.format(kind="message")),
            reported_depth=DEPTH,
            statistics=SPEC,
            price_unit=lobster.price_unit(CENT),
            truncated=True,
            messages=_messages_of(once),
            book=once.lobster_book.reset_index(drop=True).astype("int64"),
        ).coarsened(False)
        pd.testing.assert_frame_equal(
            once.lobster_book.reset_index(drop=True),
            again.lobster_book.reset_index(drop=True),
        )


def _messages_of(session):
    """The message rows a coarse session implies: one visible execution where it traded."""
    volume = session.trades["Volume"].to_numpy()
    return frames.lobster_message_schema().validate(
        pd.DataFrame(
            {
                "Time": session.lobster_book.index.to_numpy(),
                "TimeNanoseconds": np.round(
                    session.lobster_book.index.to_numpy() * 1e9
                ).astype("int64"),
                "Type": np.where(volume > 0, 4, 1),
                "OrderID": np.arange(1, len(volume) + 1),
                "Size": volume.astype("int64"),
                "Price": 100000,
                "Direction": 1,
            }
        )
    )


class TestHiddenPrints:
    def test_one_between_two_fills_is_absorbed(self, tmp_path):
        """An aggressor takes lit and hidden liquidity in one sweep; that is one order."""
        messages = [
            (34201.5, 4, 11, 20, 100000, 1),
            (34201.5, 5, 0, 30, 99950, 1),
            (34201.5, 4, 12, 15, 100000, 1),
        ]
        raw = pair(tmp_path, messages, [state(80), state(80), state(65)])
        assert market_order_index(raw.messages).tolist() == [0, 0, 0]
        assert len(raw.coarsened(False).lobster_book) == 1

    def test_one_beside_a_fill_is_not(self, tmp_path):
        """Nothing says a hidden print at the edge of a block belongs to that aggressor."""
        messages = [
            (34201.5, 4, 11, 20, 100000, 1),
            (34201.5, 5, 0, 30, 99950, 1),
        ]
        raw = pair(tmp_path, messages, [state(80), state(80)])
        assert market_order_index(raw.messages).tolist() == [0, -1]

    def test_a_print_belonging_to_no_order_is_dropped(self, tmp_path):
        messages = [
            (34200.0, 1, 1, 10, 99900, 1),
            (34201.5, 5, 0, 30, 99950, 1),
            (34202.0, 1, 2, 10, 99900, 1),
        ]
        raw = pair(tmp_path, messages, [state(100), state(100), state(100)])
        coarse = raw.coarsened(False)
        assert len(coarse.lobster_book) == 2
        assert coarse.lobster_book.index.tolist() == [34200.0, 34202.0]

    def test_one_at_the_opening_row_is_kept(self, tmp_path):
        """It repeats no state, having none before it, and a session begins with a state."""
        messages = [
            (34200.0, 5, 0, 30, 99950, 1),
            (34201.0, 1, 1, 10, 99900, 1),
        ]
        raw = pair(tmp_path, messages, [state(100), state(100)])
        coarse = raw.coarsened(False)
        assert len(coarse.lobster_book) == 2
        assert coarse.trades["Volume"].sum() == 0


class TestThePairAndTheSessionAreDifferentShapes:
    """The refusal is mutual, and that is the design: neither can be passed for the other."""

    def test_the_pair_is_indexed_by_position(self, tmp_path):
        raw = pair(tmp_path, *QUEUE_SPLIT)
        assert raw.book.index.name is None
        assert raw.messages.index.tolist() == list(range(5))

    def test_a_positional_book_is_refused_by_the_session_schema(self, tmp_path):
        raw = pair(tmp_path, *QUEUE_SPLIT)
        with pytest.raises(pe.SchemaError):
            frames.session_book_schema(DEPTH).validate(raw.book)

    def test_a_clocked_book_is_refused_by_the_file_schema(self, tmp_path):
        coarse = pair(tmp_path, *QUEUE_SPLIT).coarsened(False)
        with pytest.raises(pe.SchemaError):
            frames.lobster_orderbook_file_schema(DEPTH).validate(coarse.lobster_book)

    def test_the_statistics_carry_the_same_distinction(self, tmp_path):
        raw = pair(tmp_path, *QUEUE_SPLIT)
        SPEC.positional_statistics_schema().validate(raw.stats_from_frame())
        with pytest.raises(pe.SchemaError):
            SPEC.statistics_schema().validate(raw.stats_from_frame())


# ---- the fold and the file, read against each other -------------------------------------


def written(tmp_path, session, kinds=(1,)):
    """A folded session written out as the pair LOBSTER would have written for it."""
    times = session.lobster_book.index.to_numpy()
    files = lobster.LobsterFiles.parse(tmp_path / NAME.format(kind="message"))
    lobster.write_pair(
        files,
        pd.DataFrame(
            {
                "Time": times,
                "Type": [kinds[i % len(kinds)] for i in range(len(times))],
                "OrderID": np.arange(1, len(times) + 1),
                "Size": 10,
                "Price": 2238100,
                "Direction": 1,
            }
        ),
        session.lobster_book,
    )
    return files


def folded(bids, asks, messages):
    return MarketSession.from_occupied_levels(
        AggregateBook.from_levels(bids, asks), messages, DEPTH, SPEC,
        lobster.price_unit(CENT), True,
    )


def loaded(files, statistics):
    return LobsterMarketSession.from_files(files, SPEC, CENT, WHOLE_DAY).coarsened(
        statistics
    )


class TestTheLoaderInvertsTheRecorder:
    """A session written out as a pair, read back and coarsened, is the same session.

    Which is also the check that coarsening leaves alone what is already coarse: a folded
    session has one row per message, and nothing in it to group.

    The fixture keeps both sides occupied to the reported depth, so the truncation branch of
    the coverage rule cannot fire and the two routes are comparing like with like.
    """

    @pytest.fixture
    def both(self, tmp_path):
        fold = folded(
            {1000: 100, 999: 200, 998: 150},
            {1002: 120, 1003: 180, 1004: 90},
            [
                limit_order(34200.0, 10, 997, BUY),
                limit_order(34201.0, 10, 1005, SELL),
                limit_order(34202.0, 10, 996, BUY),
            ],
        )
        return fold, loaded(written(tmp_path, fold), True)

    def test_the_book_frames_are_the_same_object(self, both):
        fold, coarse = both
        pd.testing.assert_frame_equal(fold.lobster_book, coarse.lobster_book)

    def test_the_statistics_agree_column_by_column(self, both):
        fold, coarse = both
        pd.testing.assert_frame_equal(
            fold.stats_from_frame(), coarse.stats_from_frame(), check_dtype=False
        )

    def test_the_loaded_session_knows_it_is_truncated(self, both):
        _, coarse = both
        assert coarse.truncated
        assert coarse.price_unit == 100


class TestTruncationWeakensTheCoverage:
    """The same frame, two provenances, one column that disagrees -- and both are right.

    Coverage is a claim about what the *frame* determines.  A fold knows an ask side holding
    one level holds only one; a file says only that it saw one inside the visible price
    range.
    """

    @pytest.fixture
    def both(self, tmp_path):
        fold = folded({1000: 100, 999: 200}, {1002: 120}, [limit_order(34200.0, 5, 998, BUY)])
        return fold, loaded(written(tmp_path, fold), True)

    def test_the_frames_are_identical(self, both):
        fold, coarse = both
        pd.testing.assert_frame_equal(fold.lobster_book, coarse.lobster_book)

    def test_and_the_coverage_flag_is_not(self, both):
        fold, coarse = both
        assert fold.stats["QueueImbalance2Covered"].iloc[0] == 1.0
        assert coarse.stats["QueueImbalance2Covered"].iloc[0] == 0.0


class TestTheTradesAreTheLitTape:
    def build(self, tmp_path, kinds):
        fold = folded({1000: 100, 999: 200}, {1002: 120, 1003: 90},
                      [limit_order(34200.0 + i, 5, 998, BUY) for i in range(3)])
        return loaded(written(tmp_path, fold, kinds=kinds), False)

    def test_a_submission_trades_nothing(self, tmp_path):
        assert self.build(tmp_path, (1,)).trades["Volume"].sum() == 0

    def test_a_halt_is_not_counted(self, tmp_path):
        assert self.build(tmp_path, (7,)).trades["Volume"].sum() == 0

    def test_a_visible_execution_is(self, tmp_path):
        assert self.build(tmp_path, (4,)).trades["Volume"].sum() == 30

    def test_an_executed_sell_limit_order_is_a_buy(self, tmp_path):
        """LOBSTER's `Direction` names the resting side, so `+1` here would invert it."""
        assert (self.build(tmp_path, (4,)).trades["SignedVolume"] == -10).all()

    def test_a_tape_of_hidden_prints_alone_keeps_only_the_opening_state(self, tmp_path):
        """Every one of them repeats the state before it, and the first has none to repeat."""
        session = self.build(tmp_path, (5,))
        assert len(session.lobster_book) == 1
        assert session.trades["Volume"].sum() == 0

    def test_the_statistics_are_computed_only_when_asked(self, tmp_path):
        assert self.build(tmp_path, (1,)).stats is None


# ---- the shipped sample, when it is present ---------------------------------------------

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "lobster"
AMZN = SAMPLE / "AMZN_2012-06-21_34200000_57600000_message_10.csv"
AAPL50 = SAMPLE / "AAPL_2012-06-21_34200000_37800000_message_50.csv"
OPENING = lobster.TradingWindow(34200.0, 34500.0)
SAMPLE_SPEC = SessionStatistics((GridDepth(1),), (SweepSize(100),), (300,))

needs_sample = pytest.mark.skipif(
    not AMZN.exists(), reason="the LOBSTER sample files are not in the repository"
)


@needs_sample
class TestTheShippedSample:
    @pytest.fixture(scope="class")
    @classmethod
    def raw(cls):
        return LobsterMarketSession.from_files(
            lobster.LobsterFiles.parse(AMZN), SAMPLE_SPEC, CENT, OPENING
        )

    def test_the_pair_holds_one_state_per_message(self, raw):
        assert len(raw.book) == len(raw.messages)

    def test_the_coarse_session_holds_fewer(self, raw):
        """The equality above is what the coarsening exists to break."""
        coarse = raw.coarsened(False)
        assert len(coarse.lobster_book) < len(raw.book)

    def test_the_clock_is_non_decreasing_and_repeats(self, raw):
        stamps = raw.coarsened(False).lobster_book.index.to_numpy()
        assert (np.diff(stamps) >= 0).all()
        assert len(np.unique(stamps)) < len(stamps)

    def test_every_covered_statistic_is_finite(self, raw):
        stats = raw.coarsened(True).stats
        covered = stats["QueueImbalance1Covered"].astype(bool)
        assert stats.loc[covered, "QueueImbalance1"].notna().all()
        assert stats["Spread"].notna().all()
        assert (stats["Spread"] > 0).all()

    def test_every_visible_execution_prints_at_the_resting_side_best(self, raw):
        """Exact, not statistical: price-time priority fills the best price first."""
        assert raw.executions_off_the_touch().empty

    def test_the_lit_tape_excludes_the_hidden_prints(self, raw):
        visible = raw.messages["Type"] == LobsterEvent.EXECUTION_VISIBLE
        assert raw.coarsened(False).trades["Volume"].sum() == (
            raw.messages.loc[visible, "Size"].sum()
        )
        assert (raw.messages["Type"] == LobsterEvent.EXECUTION_HIDDEN).any()


@needs_sample
class TestWhatTheCoarseningCostsOnRealData:
    @pytest.fixture(scope="class")
    @classmethod
    def both(cls):
        raw = LobsterMarketSession.from_files(
            lobster.LobsterFiles.parse(AMZN), SAMPLE_SPEC, CENT, OPENING
        )
        return raw, raw.coarsened(True)

    def test_the_traded_totals_are_preserved_to_the_bit(self, both):
        raw, coarse = both
        fine = raw.trades_from_messages()
        for column in ("Volume", "SignedVolume", "TradedValue"):
            assert coarse.trades[column].sum() == fine[column].sum()

    def test_the_rows_lost_are_exactly_the_ones_the_rule_names(self, both):
        raw, coarse = both
        orders = raw.market_orders()
        execution = raw.messages["Type"].isin(
            (LobsterEvent.EXECUTION_VISIBLE, LobsterEvent.EXECUTION_HIDDEN)
        ).to_numpy()
        kept = (~execution).sum() + len(np.unique(orders[orders >= 0]))
        assert len(coarse.lobster_book) in (kept, kept + 1)

    def test_the_order_flow_survives_every_split_and_no_walk(self, both):
        raw, _ = both
        orders = raw.market_orders()
        fine = raw.stats_from_frame()["OrderFlowContribution"].to_numpy()
        price = raw.messages["Price"].to_numpy()
        visible = (raw.messages["Type"] == LobsterEvent.EXECUTION_VISIBLE).to_numpy()
        ask = raw.book["AskPrice1"].to_numpy() / raw.price_unit
        bid = raw.book["BidPrice1"].to_numpy() / raw.price_unit
        ask_size = raw.book["AskSize1"].to_numpy()
        bid_size = raw.book["BidSize1"].to_numpy()
        splits = walks = 0
        for order in np.unique(orders[orders >= 0]):
            rows = np.flatnonzero(orders == order)
            if len(rows) == 1 or rows[0] == 0:
                continue
            before, last = rows[0] - 1, rows[-1]
            coarse = (
                (bid[last] >= bid[before]) * bid_size[last]
                - (bid[last] <= bid[before]) * bid_size[before]
                - (ask[last] <= ask[before]) * ask_size[last]
                + (ask[last] >= ask[before]) * ask_size[before]
            )
            agrees = abs(fine[rows].sum() - coarse) < 1e-9
            if len(np.unique(price[rows[visible[rows]]])) == 1:
                splits += 1
                assert agrees
            else:
                walks += 1
                assert not agrees
        assert splits and walks


@pytest.mark.skipif(not AAPL50.exists(), reason="the depth-50 sample is not present")
class TestAPaddedSide:
    """Padding is an opening artefact: the book has not yet filled to fifty levels."""

    @pytest.fixture(scope="class")
    @classmethod
    def session(cls):
        return LobsterMarketSession.from_files(
            lobster.LobsterFiles.parse(AAPL50), SAMPLE_SPEC, CENT, OPENING
        ).coarsened(True)

    def test_the_deepest_ask_level_is_padded_on_some_rows(self, session):
        assert (session.lobster_book["AskPrice50"] == frames.ASK_PADDING).any()

    def test_a_padded_level_is_exactly_a_side_short_of_the_reported_depth(self, session):
        padded = (session.lobster_book["AskPrice50"] == frames.ASK_PADDING).to_numpy()
        short = (session.stats["AskOccupiedLevels"] < session.reported_depth).to_numpy()
        assert (padded == short).all()

    def test_the_touch_is_unharmed_by_padding_far_from_it(self, session):
        padded = (session.lobster_book["AskPrice50"] == frames.ASK_PADDING).to_numpy()
        assert session.stats.loc[padded, "Spread"].notna().all()


# ---- the report: what was promised, and what happened -----------------------------------


class TestTheCoarseningReport:
    def report(self, tmp_path, fixture):
        raw = pair(tmp_path, *fixture)
        return raw, coarsening_report(raw, raw.coarsened(True))

    def test_nothing_guaranteed_ever_differs(self, tmp_path):
        """The soundness check, and the only direction the theorem claims."""
        for fixture in (QUEUE_SPLIT, LEVEL_WALK):
            _, report = self.report(tmp_path, fixture)
            promised = report[report["Guaranteed"]]
            assert (promised["RowsDiffering"] == 0).all()

    def test_an_increment_is_promised_on_a_split_and_not_on_a_walk(self, tmp_path):
        _, split = self.report(tmp_path, QUEUE_SPLIT)
        _, walk = self.report(tmp_path, LEVEL_WALK)
        flow = "OrderFlowContribution"
        assert split.set_index("Statistic").loc[flow, "Guaranteed"]
        assert not walk.set_index("Statistic").loc[flow, "Guaranteed"]
        assert walk.set_index("Statistic").loc[flow, "RowsDiffering"] == 1

    def test_the_traded_quantities_are_compared_as_sums(self, tmp_path):
        """Comparing the last fill instead would report a difference on every split."""
        _, report = self.report(tmp_path, QUEUE_SPLIT)
        rows = report.set_index("Statistic")
        assert rows.loc["Volume", "Comparison"] == "summed over the order"
        assert rows.loc["Spread", "Comparison"] == "at the row"
        assert rows.loc["Volume", "RowsDiffering"] == 0

    def test_a_column_may_survive_more_than_the_theorem_promises(self, tmp_path):
        """VWAP is a ratio of two additive sums, which no dependence alone reaches."""
        _, report = self.report(tmp_path, LEVEL_WALK)
        vwap = report.set_index("Statistic").loc["VWAP1"]
        assert not vwap["Guaranteed"]
        assert vwap["RowsDiffering"] == 0

    def test_a_per_row_average_is_where_the_cost_shows(self, tmp_path):
        _, report = self.report(tmp_path, QUEUE_SPLIT)
        assert report.set_index("Statistic").loc["AverageDepth1", "RowsDiffering"] > 0


class TestTheTotals:
    def test_what_traded_is_preserved_and_what_a_trade_is_is_not(self, tmp_path):
        raw = pair(tmp_path, *QUEUE_SPLIT)
        totals = coarsening_totals(raw, raw.coarsened(False)).set_index("Quantity")
        for quantity in ("shares", "traded value in tick-shares", "VWAP in ticks"):
            assert totals.loc[quantity, "Fine"] == totals.loc[quantity, "Coarse"]
        assert totals.loc["rows", "Fine"] == 5
        assert totals.loc["rows", "Coarse"] == 3
        # The mean of the fine column is the mean execution; of the coarse, the mean trade.
        assert totals.loc["mean size of what trades", "Fine"] == pytest.approx(55 / 3)
        assert totals.loc["mean size of what trades", "Coarse"] == 55.0


@needs_sample
class TestTheReportOnRealData:
    @pytest.fixture(scope="class")
    @classmethod
    def report(cls):
        raw = LobsterMarketSession.from_files(
            lobster.LobsterFiles.parse(AMZN), SAMPLE_SPEC, CENT, OPENING
        )
        return raw, coarsening_report(raw, raw.coarsened(True))

    def test_nothing_guaranteed_differs(self, report):
        _, measured = report
        assert not ((measured["Guaranteed"]) & (measured["RowsDiffering"] > 0)).any()

    def test_the_order_flow_differs_on_exactly_the_level_walks(self, report):
        raw, measured = report
        orders = raw.market_orders()
        price = raw.messages["Price"].to_numpy()
        visible = (raw.messages["Type"] == LobsterEvent.EXECUTION_VISIBLE).to_numpy()
        fills = np.bincount(orders[orders >= 0])
        walks = sum(
            len(np.unique(price[(orders == order) & visible])) > 1
            for order in np.flatnonzero(fills > 1)
        )
        differing = measured.set_index("Statistic").loc[
            "OrderFlowContribution", "RowsDiffering"
        ]
        assert walks and differing == walks

    def test_every_window_average_moves_and_every_vwap_does_not(self, report):
        _, measured = report
        rows = measured.set_index("Statistic")
        assert rows.loc["AverageDepth300", "RowsDiffering"] > 0
        assert rows.loc["VWAP300", "RowsDiffering"] == 0
